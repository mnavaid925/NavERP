"""Projects 7.3 Resource Management - VIEW tests.

The HTTP layer of the sub-module: 25 routes, the three registers + the computed capacity board
they render, every context key the test contract pins, search/filter/junk/pagination behaviour,
the CRUD round-trips through real POSTs, and the nine POST verbs' state machines (assign,
substitute, commit, complete, cancel on allocations; submit, approve, reject, approve_week on
time entries). Model invariants belong to ``test_resource_models.py`` and form validation to
``test_resource_forms.py``; role gating (403), cross-tenant IDOR (404), CSRF and anonymous
access belong to ``test_resource_security.py``. Every request here is made by a TENANT ADMIN
(root conftest's ``client_a`` - there is deliberately no ``resource_client``), so the only thing
that can refuse a verb in this lane is its own state gate.

What this lane exists to catch:

* **A blank region that returns 200.** A mismatched context key renders nothing and reports
  success (L8), so every page asserts CONTENT - the row's own ``RSP-``/``RAL-``/``RTE-`` number
  in the body - and then asserts each pinned key by name, including the as-built
  ``actuals_year``/``actuals_week`` pair on ``rte_list`` and the ``successor``/``resources``
  pair on ``ral_detail``.
* **A filter that silently empties a register.** Every documented control on all three registers
  (plus the hand-parsed ``?placeholder=`` / ``?is_live=`` lenses) is compared against the ORM's
  own answer for the same narrowing, and the junk values (``?status=nope``, ``?resource=0``, an
  over-range pk) must return the FULL register at 200 - never a 500, never an empty page
  (L9/L11). ``rte_list``'s non-pk ``?year=``/``?week=`` are the documented exception: ``?year=0``
  / ``?year=9999`` are special-cased up front (``qs.none()`` + the actuals-window fallback) and
  ``?week=0`` legitimately matches no row.
* **A verb that writes when it should refuse.** All nine are exercised on both sides: the happy
  path with its audit row, then every now-forbidden source state, each of which must answer
  with a message, a redirect, and leave the row byte-for-byte as it was - ``updated_at``
  included, because a refusal that still calls ``save()`` is a refusal that lies. Three gates
  here are regression guards for the review pass's fixes: ``ral_commit`` refuses a soft
  PLACEHOLDER going to firm (I3), ``ral_substitute`` re-runs its state checks INSIDE the
  ``select_for_update`` transaction (a row that already has a successor refuses), and
  ``rte_approve_week`` bulk-updates the person-week with ONE audit row on the RESOURCE.
* **A form edit that touches verb state.** The create/edit forms exclude ``booking_status``,
  ``requested_by``, ``status`` and the approval stamps; a smuggled value in an edit POST must be
  ignored (L20), and the approved/rejected edit/delete locks must hold before ``crud_edit`` /
  ``crud_delete`` ever run.

Determinism (L16): every date basis is ``timezone.localdate()`` (via the conftest's
``_resource_today``) and every datetime basis is ``timezone.now()`` - the same bases
``ResourceAllocation.is_live``, the capacity horizon and the actuals window use.
``datetime.date.today()`` never appears. Nothing here touches the network or the demo seeder -
every board expectation is computed from the fixture rows the test itself built via
``planned_hours``, never hardcoded.

Naming (mandatory): every test is ``test_resource_*`` and every module-level helper
``_resource_*`` / ``_RESOURCE_*``, so no other lane of this package can shadow either.

This file is pure ASCII on purpose. Several 7.3 messages carry U+2014 (and the board's window
labels carry U+00B7), so every message/content assertion below matches an ASCII SUBSTRING - a
copy edit must not turn into a red suite.
"""
import datetime
from decimal import Decimal
from datetime import date

import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.projects.models import ResourceAllocation, ResourceProfile, ResourceTimeEntry
from apps.projects.tests.conftest import (
    RESOURCE_PAGE_SIZE,
    _resource_allocation,
    _resource_entry,
    _resource_fill_allocations,
    _resource_fill_profiles,
    _resource_profile,
    _resource_today,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Module-level helpers - every one ``_resource_*`` for the same reason the tests are (Python binds
# the LAST module-level definition, so an unprefixed helper here would silently rebind a sibling
# lane's). Record factories come from the conftest, which OWNS them.
# ==================================================================================================

#: Every url name the sub-module owns, with the args each one reverses with. 25 is the contract's
#: headline number (the five CRUD stems x3, the nine verbs, the weekly bulk route, the board).
_RESOURCE_ALL_ROUTES = (
    ("rsp_list", ()),
    ("rsp_create", ()),
    ("rsp_detail", (7,)),
    ("rsp_edit", (7,)),
    ("rsp_delete", (7,)),
    ("ral_list", ()),
    ("ral_create", ()),
    ("ral_detail", (7,)),
    ("ral_edit", (7,)),
    ("ral_delete", (7,)),
    ("ral_assign", (7,)),
    ("ral_substitute", (7,)),
    ("ral_commit", (7,)),
    ("ral_complete", (7,)),
    ("ral_cancel", (7,)),
    ("rte_list", ()),
    ("rte_create", ()),
    ("rte_approve_week", (7, 2025, 37)),
    ("rte_detail", (7,)),
    ("rte_edit", (7,)),
    ("rte_delete", (7,)),
    ("rte_submit", (7,)),
    ("rte_approve", (7,)),
    ("rte_reject", (7,)),
    ("capacity_demand", ()),
)

#: The 12 POST-only routes (three deletes + nine verbs). A GET on any of them is 405 for an actor
#: who clears the decorators stacked ABOVE ``@require_POST`` - which, for the five admin-gated
#: verbs, means an ADMIN GET. (Role gating itself belongs to the security lane.)
_RESOURCE_POST_ONLY_ROUTES = (
    ("rsp_delete", (1,)),
    ("ral_delete", (1,)),
    ("rte_delete", (1,)),
    ("ral_assign", (1,)),
    ("ral_substitute", (1,)),
    ("ral_commit", (1,)),
    ("ral_complete", (1,)),
    ("ral_cancel", (1,)),
    ("rte_submit", (1,)),
    ("rte_approve", (1,)),
    ("rte_reject", (1,)),
    ("rte_approve_week", (1, 2025, 37)),
)


def _resource_url(name, *args):
    return reverse(f"projects:{name}", args=args)


def _resource_get(client, name, /, *args, follow=False, **params):
    return client.get(_resource_url(name, *args), params, follow=follow)


def _resource_post(client, name, /, *args, data=None, follow=False):
    """POST one 7.3 route. CSRF is off on the ordinary test client - the enforced-CSRF pair
    belongs to the security lane."""
    return client.post(_resource_url(name, *args), data or {}, follow=follow)


def _resource_messages(response):
    """Every message queued on the request that produced ``response``, as plain strings.

    Read off the REQUEST rather than the rendered page: the verbs all redirect, so nothing has
    rendered - and therefore consumed - the storage yet.
    """
    return [str(message) for message in get_messages(response.wsgi_request)]


def _resource_levels(response):
    return [message.level_tag for message in get_messages(response.wsgi_request)]


def _resource_said(response, fragment):
    """True when any queued message contains ``fragment`` (ASCII substrings only - several 7.3
    messages carry U+2014, and matching a whole sentence would turn a copy edit into a red suite)."""
    return any(fragment in message for message in _resource_messages(response))


def _resource_body(response):
    return response.content.decode()


def _resource_templates(response):
    """Every template name that rendered, including ``base.html`` and the widget partials."""
    return [template.name for template in response.templates if template.name]


def _resource_pks(response, key="object_list"):
    """The primary keys the page actually rendered, in order."""
    return [row.pk for row in response.context[key]]


def _resource_snapshot(obj):
    """Every concrete column of ``obj``, read FRESH from the database. ``updated_at`` is
    ``auto_now``, so it is in here deliberately: a refusal that still reaches ``save()`` moves it,
    and a snapshot comparison is the only thing that catches a "refusal" which writes nothing
    visible but writes."""
    fresh = type(obj)._default_manager.get(pk=obj.pk)
    return {field.attname: getattr(fresh, field.attname)
            for field in fresh._meta.concrete_fields}


def _resource_unchanged(obj, before):
    """Assert ``obj``'s row is byte-for-byte what ``before`` recorded."""
    after = _resource_snapshot(obj)
    deltas = {name: (before[name], after[name]) for name in before if before[name] != after[name]}
    assert deltas == {}, f"a refused verb wrote to the row: {deltas}"


def _resource_audits(obj, action=None):
    """The audit rows written against ``obj``, newest first."""
    qs = AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)), object_id=obj.pk)
    if action is not None:
        qs = qs.filter(action=action)
    return list(qs.order_by("-id"))


def _resource_assert_narrows(client, route, model, tenant, params, lookups):
    """The register's answer for ``params`` must equal the ORM's answer for ``lookups`` - and be
    strictly smaller than the unfiltered register, so a control that does nothing fails too."""
    expected = set(model.objects.filter(tenant=tenant, **lookups).values_list("pk", flat=True))
    total = model.objects.filter(tenant=tenant).count()
    assert expected, "the scenario has no row for this filter value - the test proves nothing"
    assert len(expected) < total, "this filter value matches every row - it cannot narrow"
    resp = _resource_get(client, route, **params)
    assert resp.status_code == 200
    assert set(_resource_pks(resp)) == expected
    return resp


def _resource_rsp_payload(**overrides):
    """The minimum valid ``ResourceProfileForm`` POST - its five required fields plus one identity
    (the exactly-one-of rule is the model clean's; the caller picks employee or party)."""
    payload = {
        "resource_type": "contractor",
        "default_role": "Field auditor",
        "weekly_capacity_hours": "40.00",
        "utilization_target_pct": "80",
        "status": "active",
    }
    payload.update(overrides)
    return payload


def _resource_ral_payload(project=None, **overrides):
    """The minimum valid ``ResourceAllocationForm`` POST - role, unit, one matching magnitude and
    a start date. ``project=None`` omits the attach so the model clean's guard fires."""
    payload = {
        "role_name": "Field auditor",
        "allocation_unit": "hours_per_week",
        "hours_per_week": "16.00",
        "start_date": _resource_today().isoformat(),
    }
    if project is not None:
        payload["project"] = str(project.pk)
    payload.update(overrides)
    return payload


def _resource_rte_payload(resource=None, **overrides):
    """The minimum valid ``ResourceTimeEntryForm`` POST - resource, entry date, hours.
    ``resource=None`` omits the FK so the required-field error fires."""
    payload = {
        "entry_date": _resource_today().isoformat(),
        "hours": "6.00",
    }
    if resource is not None:
        payload["resource"] = str(resource.pk)
    payload.update(overrides)
    return payload


def _resource_iso_monday(today=None):
    """The Monday that opens the current ISO week - where the capacity horizon starts."""
    iso = (today or _resource_today()).isocalendar()
    return date.fromisocalendar(iso[0], iso[1], 1)


def _resource_iso_window(today=None):
    """The current ISO week's (start, end) - the default actuals window."""
    start = _resource_iso_monday(today)
    return start, start + datetime.timedelta(days=6)


# ==================================================================================================
# 1. Routing - the 25 names, their published paths, and nothing unpinned
# ==================================================================================================

def test_resource_the_sub_module_owns_exactly_twenty_five_routes():
    """25 distinct names. A route added without its ``urlpatterns`` entry is a NoReverseMatch in a
    template (L7), which renders as a 500 on a page nobody tested."""
    assert len({name for name, _args in _RESOURCE_ALL_ROUTES}) == 25


@pytest.mark.parametrize("name,args", _RESOURCE_ALL_ROUTES)
def test_resource_every_route_reverses(name, args):
    reverse(f"projects:{name}", args=args)


@pytest.mark.parametrize("name,path", [
    ("rsp_list", "/projects/resource-profiles/"),
    ("rsp_create", "/projects/resource-profiles/add/"),
    ("ral_list", "/projects/allocations/"),
    ("ral_create", "/projects/allocations/add/"),
    ("rte_list", "/projects/time-entries/"),
    ("rte_create", "/projects/time-entries/add/"),
    ("rte_approve_week", "/projects/time-entries/week/7/2025/w37/approve/"),
    ("capacity_demand", "/projects/capacity-demand/"),
])
def test_resource_literal_routes_keep_their_published_paths(name, path):
    """These are linked from the sidebar and bookmarked, and every one of them must stay AHEAD of
    its module's ``<int:pk>`` routes in the concatenated urlpatterns - Django is first-match-wins,
    so ``/projects/allocations/add/`` resolving to ``ral_detail`` is one reorder away."""
    args = (7, 2025, 37) if name == "rte_approve_week" else ()
    assert _resource_url(name, *args) == path


@pytest.mark.parametrize("name,path", [
    ("rsp_detail", "/projects/resource-profiles/7/"),
    ("rsp_edit", "/projects/resource-profiles/7/edit/"),
    ("rsp_delete", "/projects/resource-profiles/7/delete/"),
    ("ral_detail", "/projects/allocations/7/"),
    ("ral_edit", "/projects/allocations/7/edit/"),
    ("ral_delete", "/projects/allocations/7/delete/"),
    ("ral_assign", "/projects/allocations/7/assign/"),
    ("ral_substitute", "/projects/allocations/7/substitute/"),
    ("ral_commit", "/projects/allocations/7/commit/"),
    ("ral_complete", "/projects/allocations/7/complete/"),
    ("ral_cancel", "/projects/allocations/7/cancel/"),
    ("rte_detail", "/projects/time-entries/7/"),
    ("rte_edit", "/projects/time-entries/7/edit/"),
    ("rte_delete", "/projects/time-entries/7/delete/"),
    ("rte_submit", "/projects/time-entries/7/submit/"),
    ("rte_approve", "/projects/time-entries/7/approve/"),
    ("rte_reject", "/projects/time-entries/7/reject/"),
])
def test_resource_pk_routes_keep_their_published_paths(name, path):
    assert _resource_url(name, 7) == path


@pytest.mark.parametrize("name", (
    "rsp_submit", "ral_approve", "ral_reopen", "rte_convert", "rte_export"))
def test_resource_no_unpinned_verb_route_exists(name):
    """7.3 ships no verb beyond the nine (plus CRUD deletes). Asserting the ABSENCE keeps a later
    edit from quietly adding an ungated verb into this namespace."""
    with pytest.raises(NoReverseMatch):
        reverse(f"projects:{name}", args=[1])


# ==================================================================================================
# 2. The resource pool register - context keys, content, search, filters
# ==================================================================================================

def test_resource_rsp_register_renders_context_keys_and_content(
        client_a, resource_org_unit_a, resource_profile_internal, resource_profile_contractor):
    resp = _resource_get(client_a, "rsp_list")
    assert resp.status_code == 200
    assert "projects/resource/resourceprofile/list.html" in _resource_templates(resp)
    for key in ("object_list", "page_obj", "q", "resource_type_choices", "status_choices",
                "org_units"):
        assert key in resp.context, f"rsp_list dropped its pinned key: {key}"
    assert resp.context["resource_type_choices"] == ResourceProfile.RESOURCE_TYPE_CHOICES
    assert resp.context["status_choices"] == ResourceProfile.STATUS_CHOICES
    assert resp.context["page_obj"].paginator.per_page == RESOURCE_PAGE_SIZE
    assert resource_org_unit_a in list(resp.context["org_units"])
    body = _resource_body(resp)
    # CONTENT, not just status: a mis-named key renders an empty <div> at 200.
    assert resource_profile_internal.number in body
    assert resource_profile_internal.default_role in body
    assert resource_profile_contractor.number in body
    assert "{#" not in body and "{% comment" not in body


def test_resource_rsp_register_search_narrows(client_a, resource_profile_internal,
                                              resource_profile_contractor):
    """``?q=`` hits the party names, the number, the role and the skill summary (icontains OR)."""
    contractor = resource_profile_contractor
    resp = _resource_get(client_a, "rsp_list", q="Priya")
    assert resp.status_code == 200
    assert _resource_pks(resp) == [contractor.pk]
    assert resp.context["q"] == "Priya"
    assert _resource_pks(_resource_get(client_a, "rsp_list", q=contractor.number)) == [contractor.pk]
    assert _resource_pks(_resource_get(client_a, "rsp_list", q="data engineer")) == [
        resource_profile_internal.pk]
    assert _resource_pks(_resource_get(client_a, "rsp_list", q="playwright")) == [contractor.pk]
    resp = _resource_get(client_a, "rsp_list", q="zzz-no-such-resource-zzz")
    assert resp.status_code == 200
    assert list(resp.context["object_list"]) == []


def test_resource_rsp_register_filters_narrow_to_the_orm_answer(
        client_a, tenant_a, resource_org_unit_a, resource_org_unit_b,
        resource_profile_internal, resource_profile_contractor):
    """The type/status lenses and the org_unit pk lens narrow to the ORM's own answer; a
    valid-but-FOREIGN org unit pk is a legitimate narrowing that matches nothing (200 empty)."""
    _resource_profile(tenant_a, default_role="Retired consultant",
                      resource_type="consultant", status="inactive")
    _resource_assert_narrows(client_a, "rsp_list", ResourceProfile, tenant_a,
                             {"resource_type": "internal"}, {"resource_type": "internal"})
    _resource_assert_narrows(client_a, "rsp_list", ResourceProfile, tenant_a,
                             {"resource_type": "contractor"}, {"resource_type": "contractor"})
    _resource_assert_narrows(client_a, "rsp_list", ResourceProfile, tenant_a,
                             {"status": "inactive"}, {"status": "inactive"})
    _resource_assert_narrows(client_a, "rsp_list", ResourceProfile, tenant_a,
                             {"org_unit": str(resource_org_unit_a.pk)},
                             {"org_unit_id": resource_org_unit_a.pk})
    resp = _resource_get(client_a, "rsp_list", org_unit=str(resource_org_unit_b.pk))
    assert resp.status_code == 200
    assert list(resp.context["object_list"]) == []


def test_resource_rsp_register_skips_junk_params(client_a, tenant_a, resource_profile_internal,
                                                 resource_profile_contractor):
    """Junk enum values and junk pks are SKIPPED, not matched: every row stays listed at 200
    (L11) - a stale bookmark must never silently empty a register."""
    _resource_profile(tenant_a, default_role="Junk filler role", resource_type="freelancer",
                      status="inactive")
    expected = set(ResourceProfile.objects.filter(tenant=tenant_a).values_list("pk", flat=True))
    assert len(expected) == 3
    for params in ({"resource_type": "nope", "status": "zzz", "org_unit": "abc"},
                   {"resource_type": "nope", "status": "zzz", "org_unit": "0"},
                   {"resource_type": "nope", "status": "zzz",
                    "org_unit": "999999999999999999999"}):
        resp = client_a.get(_resource_url("rsp_list"), params)
        assert resp.status_code == 200
        assert set(_resource_pks(resp)) == expected, f"junk params {params} emptied the register"


# ==================================================================================================
# 3. The allocations register - context keys, content, search, filters, lenses
# ==================================================================================================

def test_resource_ral_register_renders_context_keys_and_content(
        client_a, tenant_a, resource_project, resource_profile_internal,
        resource_allocation_named_firm, resource_allocation_named_soft,
        resource_allocation_placeholder_requested):
    resp = _resource_get(client_a, "ral_list")
    assert resp.status_code == 200
    assert "projects/resource/resourceallocation/list.html" in _resource_templates(resp)
    for key in ("object_list", "page_obj", "q", "booking_status_choices", "projects",
                "project_requests", "resources"):
        assert key in resp.context, f"ral_list dropped its pinned key: {key}"
    assert resp.context["booking_status_choices"] == ResourceAllocation.BOOKING_STATUS_CHOICES
    assert resp.context["page_obj"].paginator.per_page == RESOURCE_PAGE_SIZE
    assert resource_project in list(resp.context["projects"])
    assert resource_profile_internal in list(resp.context["resources"])
    body = _resource_body(resp)
    assert resource_allocation_named_firm.number in body
    assert resource_allocation_named_soft.role_name in body
    assert "Placeholder" in body      # a resource-less booking renders the placeholder badge


def test_resource_ral_register_search_narrows(client_a, resource_allocation_named_soft,
                                              resource_allocation_request_placeholder):
    """``?q=`` hits role_name, number, skill_requirements and the linked project's name."""
    soft = resource_allocation_named_soft
    request_row = resource_allocation_request_placeholder
    assert _resource_pks(_resource_get(client_a, "ral_list", q="data engineer")) == [soft.pk]
    assert _resource_pks(_resource_get(client_a, "ral_list", q=soft.number)) == [soft.pk]
    assert _resource_pks(_resource_get(client_a, "ral_list", q="airflow")) == [soft.pk]
    assert _resource_pks(_resource_get(client_a, "ral_list", q="Resource host Alpha")) == [soft.pk]
    assert _resource_pks(_resource_get(client_a, "ral_list", q="django")) == [request_row.pk]
    resp = _resource_get(client_a, "ral_list", q="zzz-no-such-booking-zzz")
    assert resp.status_code == 200
    assert list(resp.context["object_list"]) == []


def test_resource_ral_register_filters_narrow_to_the_orm_answer(
        client_a, tenant_a, resource_project, resource_project_b, resource_request,
        resource_profile_internal, resource_profile_b, resource_allocation_named_firm,
        resource_allocation_named_soft, resource_allocation_request_placeholder):
    """The project/request/resource pk lenses and the status lens narrow to the ORM's own answer;
    valid-but-FOREIGN pks are legitimate narrowings that match nothing (200 empty - never skip)."""
    _resource_assert_narrows(client_a, "ral_list", ResourceAllocation, tenant_a,
                             {"booking_status": "firm"}, {"booking_status": "firm"})
    _resource_assert_narrows(client_a, "ral_list", ResourceAllocation, tenant_a,
                             {"project": str(resource_project.pk)},
                             {"project_id": resource_project.pk})
    _resource_assert_narrows(client_a, "ral_list", ResourceAllocation, tenant_a,
                             {"project_request": str(resource_request.pk)},
                             {"project_request_id": resource_request.pk})
    _resource_assert_narrows(client_a, "ral_list", ResourceAllocation, tenant_a,
                             {"resource": str(resource_profile_internal.pk)},
                             {"resource_id": resource_profile_internal.pk})
    for params in ({"project": str(resource_project_b.pk)},
                   {"resource": str(resource_profile_b.pk)}):
        resp = _resource_get(client_a, "ral_list", **params)
        assert resp.status_code == 200
        assert list(resp.context["object_list"]) == []


def test_resource_ral_register_placeholder_and_live_lenses(
        client_a, tenant_a, resource_allocation_named_firm, resource_allocation_named_soft,
        resource_allocation_soft_pct, resource_allocation_placeholder_requested,
        resource_allocation_placeholder_soft, resource_allocation_request_placeholder):
    """The hand-parsed lenses: ``?placeholder=`` on resource__isnull, ``?is_live=`` on the exact
    live predicate (and its exact negation), the COMPOUND lens, and junk values ignored.

    The load-bearing shape: a soft PLACEHOLDER whose window covers today IS live."""
    rows = [resource_allocation_named_firm, resource_allocation_named_soft,
            resource_allocation_soft_pct, resource_allocation_placeholder_requested,
            resource_allocation_placeholder_soft, resource_allocation_request_placeholder]
    everything = {row.pk for row in rows}
    placeholders = {row.pk for row in rows if row.resource_id is None}
    named = everything - placeholders
    live = {row.pk for row in rows if row.is_live}
    assert placeholders == {resource_allocation_placeholder_requested.pk,
                            resource_allocation_placeholder_soft.pk,
                            resource_allocation_request_placeholder.pk}
    assert live == {resource_allocation_named_firm.pk, resource_allocation_named_soft.pk,
                    resource_allocation_soft_pct.pk, resource_allocation_placeholder_soft.pk}
    assert live & placeholders == {resource_allocation_placeholder_soft.pk}

    assert set(_resource_pks(_resource_get(client_a, "ral_list", placeholder="True"))) \
        == placeholders
    assert set(_resource_pks(_resource_get(client_a, "ral_list", placeholder="False"))) == named
    assert set(_resource_pks(_resource_get(client_a, "ral_list", is_live="True"))) == live
    assert set(_resource_pks(_resource_get(client_a, "ral_list", is_live="False"))) \
        == everything - live
    # the compound lens narrows on both axes at once
    assert set(_resource_pks(_resource_get(client_a, "ral_list", placeholder="True",
                                           is_live="True"))) == {resource_allocation_placeholder_soft.pk}
    assert set(_resource_pks(_resource_get(client_a, "ral_list", placeholder="False",
                                           is_live="True"))) == live - placeholders
    # any other value (junk, 0, 1) is IGNORED - the lens never fires
    for params in ({"placeholder": "1"}, {"placeholder": "yes"}, {"is_live": "0"},
                   {"placeholder": "1", "is_live": "0"}):
        resp = _resource_get(client_a, "ral_list", **params)
        assert resp.status_code == 200
        assert set(_resource_pks(resp)) == everything, \
            f"junk lens {params} emptied the register"


def test_resource_ral_register_skips_junk_params(client_a, tenant_a,
                                                 resource_allocation_named_soft):
    expected = set(ResourceAllocation.objects.filter(tenant=tenant_a).values_list("pk", flat=True))
    assert expected
    for params in ({"booking_status": "nope", "project": "abc", "resource": "0",
                    "project_request": "999999999999999999999"},
                   {"booking_status": "nope", "project": "0", "resource": "abc"}):
        resp = client_a.get(_resource_url("ral_list"), params)
        assert resp.status_code == 200
        assert set(_resource_pks(resp)) == expected, f"junk params {params} emptied the register"


# ==================================================================================================
# 4. The time entries register - context keys, content, search, filters, the year/week guards
# ==================================================================================================

def test_resource_rte_register_renders_context_keys_and_the_actuals_window(
        client_a, resource_project, resource_profile_internal, resource_entry_draft,
        resource_entry_submitted, resource_entry_approved, resource_entry_approved_nonproject):
    resp = _resource_get(client_a, "rte_list")
    assert resp.status_code == 200
    assert "projects/resource/resourcetimeentry/list.html" in _resource_templates(resp)
    for key in ("object_list", "page_obj", "q", "status_choices", "resources", "projects",
                "actuals_rows", "actuals_year", "actuals_week"):
        assert key in resp.context, f"rte_list dropped its pinned key: {key}"
    assert resp.context["status_choices"] == ResourceTimeEntry.STATUS_CHOICES
    assert resp.context["page_obj"].paginator.per_page == RESOURCE_PAGE_SIZE
    assert resource_profile_internal in list(resp.context["resources"])
    iso = _resource_today().isocalendar()
    # the as-built resolved window: current ISO week when no ?year=/?week= is given
    assert resp.context["actuals_year"] == iso[0]
    assert resp.context["actuals_week"] == iso[1]
    body = _resource_body(resp)
    assert resource_entry_draft.number in body
    assert "Internal training" in body


def test_resource_rte_register_search_narrows(
        client_a, resource_profile_internal, resource_entry_draft, resource_entry_submitted,
        resource_entry_approved, resource_entry_approved_nonproject):
    """``?q=`` hits number, description, the linked project's name and the resource's person name
    (via either the employee walk or the party walk)."""
    assert set(_resource_pks(_resource_get(client_a, "rte_list", q="implementation"))) == {
        resource_entry_draft.pk, resource_entry_submitted.pk, resource_entry_approved.pk}
    assert _resource_pks(_resource_get(client_a, "rte_list",
                                       q=resource_entry_draft.number)) == [resource_entry_draft.pk]
    assert _resource_pks(_resource_get(client_a, "rte_list", q="Internal training")) == [
        resource_entry_approved_nonproject.pk]
    assert set(_resource_pks(_resource_get(client_a, "rte_list", q="Alex"))) == {
        resource_entry_draft.pk, resource_entry_submitted.pk, resource_entry_approved.pk}
    assert _resource_pks(_resource_get(client_a, "rte_list", q="Priya")) == [
        resource_entry_approved_nonproject.pk]
    resp = _resource_get(client_a, "rte_list", q="zzz-no-such-entry-zzz")
    assert resp.status_code == 200
    assert list(resp.context["object_list"]) == []


def test_resource_rte_register_filters_narrow_to_the_orm_answer(
        client_a, tenant_a, admin_user, resource_project, resource_project_b,
        resource_profile_internal, resource_profile_contractor, resource_profile_b,
        resource_entry_draft, resource_entry_submitted, resource_entry_approved,
        resource_entry_approved_nonproject):
    """The status lens and the resource/project pks narrow to the ORM's own answer; the NON-pk
    ``?year=``/``?week=`` int filters narrow by ISO bucket. A valid-but-foreign resource pk is a
    legitimate narrowing that matches nothing."""
    old = _resource_entry(
        tenant_a, resource_profile_internal, project=resource_project,
        # 400 days back always lands in a DIFFERENT ISO year, so the ?year= lens has a needle
        entry_date=_resource_today() - datetime.timedelta(days=400), status="approved",
        hours=Decimal("3.00"), submitted_at=timezone.now() - datetime.timedelta(days=401),
        approved_by=admin_user, approved_at=timezone.now() - datetime.timedelta(days=400))
    iso = _resource_today().isocalendar()
    _resource_assert_narrows(client_a, "rte_list", ResourceTimeEntry, tenant_a,
                             {"status": "submitted"}, {"status": "submitted"})
    _resource_assert_narrows(client_a, "rte_list", ResourceTimeEntry, tenant_a,
                             {"resource": str(resource_profile_contractor.pk)},
                             {"resource_id": resource_profile_contractor.pk})
    _resource_assert_narrows(client_a, "rte_list", ResourceTimeEntry, tenant_a,
                             {"project": str(resource_project.pk)},
                             {"project_id": resource_project.pk})
    _resource_assert_narrows(client_a, "rte_list", ResourceTimeEntry, tenant_a,
                             {"year": str(iso[0])}, {"entry_date__iso_year": iso[0]})
    _resource_assert_narrows(client_a, "rte_list", ResourceTimeEntry, tenant_a,
                             {"week": str(iso[1])}, {"entry_date__week": iso[1]})
    for params in ({"resource": str(resource_profile_b.pk)},
                   {"project": str(resource_project_b.pk)}):
        resp = _resource_get(client_a, "rte_list", **params)
        assert resp.status_code == 200
        assert list(resp.context["object_list"]) == []


def test_resource_rte_register_skips_junk_params(client_a, tenant_a, resource_entry_draft,
                                                 resource_entry_submitted):
    expected = set(ResourceTimeEntry.objects.filter(tenant=tenant_a).values_list("pk", flat=True))
    assert expected
    for params in ({"status": "nope", "resource": "abc", "project": "0"},
                   {"status": "nope", "resource": "0", "project": "abc",
                    "year": "999999999999999999999", "week": "zz"}):
        resp = client_a.get(_resource_url("rte_list"), params)
        assert resp.status_code == 200
        assert set(_resource_pks(resp)) == expected, f"junk params {params} emptied the register"


def test_resource_rte_register_year_and_week_edge_params_cannot_500(
        client_a, tenant_a, resource_entry_draft, resource_entry_submitted):
    """Divergence note 5, as built: ``?year=0`` / ``?year=9999`` are special-cased BEFORE
    ``crud_list`` (Django's year-lookup bounds would otherwise RAISE inside .count()) - the
    register empties at 200 AND the actuals window falls back to the current ISO week.
    ``?week=0`` / ``?week=99`` are non-pk int filters and legitimately match no row."""
    iso = _resource_today().isocalendar()
    for params in ({"year": "0"}, {"year": "9999"}):
        resp = _resource_get(client_a, "rte_list", **params)
        assert resp.status_code == 200
        assert list(resp.context["object_list"]) == []
        assert resp.context["actuals_year"] == iso[0]
        assert resp.context["actuals_week"] == iso[1]
    for params in ({"week": "0"}, {"week": "99"}):
        resp = _resource_get(client_a, "rte_list", **params)
        assert resp.status_code == 200
        assert list(resp.context["object_list"]) == []
        assert resp.context["actuals_year"] == iso[0]
        assert resp.context["actuals_week"] == iso[1]
    # ?year=abc is junk for both the view's parse and crud_list - the FULL register stays
    resp = _resource_get(client_a, "rte_list", year="abc")
    assert resp.status_code == 200
    assert set(_resource_pks(resp)) == {resource_entry_draft.pk, resource_entry_submitted.pk}


# ==================================================================================================
# 5. Pagination - a full page plus one, and filters parsed BEFORE the page is cut
# ==================================================================================================

def test_resource_registers_paginate_to_a_second_page(client_a, tenant_a):
    """PAGE_SIZE + 1 pool rows: page 1 is full, page 2 holds the one leftover, junk and
    past-the-end page numbers fall to page 1 / the last page instead of erroring (L9)."""
    fills = _resource_fill_profiles(tenant_a, RESOURCE_PAGE_SIZE + 1)

    resp = _resource_get(client_a, "rsp_list")
    assert resp.status_code == 200
    page_obj = resp.context["page_obj"]
    assert page_obj.paginator.per_page == RESOURCE_PAGE_SIZE
    assert page_obj.number == 1
    assert len(list(resp.context["object_list"])) == RESOURCE_PAGE_SIZE
    assert fills[-1].pk not in _resource_pks(resp)

    resp = _resource_get(client_a, "rsp_list", page="2")
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 2
    assert _resource_pks(resp) == [fills[-1].pk]

    resp = _resource_get(client_a, "rsp_list", page="abc")
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 1
    assert len(list(resp.context["object_list"])) == RESOURCE_PAGE_SIZE

    resp = _resource_get(client_a, "rsp_list", page="99")
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == resp.context["page_obj"].paginator.num_pages
    assert _resource_pks(resp) == [fills[-1].pk]


def test_resource_filters_apply_before_pagination(client_a, tenant_a, resource_project,
                                                  resource_profile_internal):
    """16 soft bookings + 1 firm: ``?booking_status=soft`` must narrow FIRST and paginate SECOND,
    so page 2 carries the leftover SOFT row and the firm row never appears on either page - and
    the pagination links carry the filter forward."""
    softs = _resource_fill_allocations(tenant_a, RESOURCE_PAGE_SIZE + 1,
                                       project=resource_project,
                                       resource=resource_profile_internal,
                                       booking_status="soft")
    firm = _resource_allocation(tenant_a, project=resource_project,
                                resource=resource_profile_internal, booking_status="firm")

    resp = _resource_get(client_a, "ral_list", booking_status="soft")
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 1
    page1 = set(_resource_pks(resp))
    assert len(page1) == RESOURCE_PAGE_SIZE
    assert firm.pk not in page1

    resp2 = _resource_get(client_a, "ral_list", booking_status="soft", page="2", follow=True)
    assert resp2.status_code == 200
    page2 = set(_resource_pks(resp2))
    assert len(page2) == 1
    assert firm.pk not in page2
    assert page1 | page2 == {row.pk for row in softs}
    assert "booking_status=soft" in _resource_body(resp)


# ==================================================================================================
# 6. The detail pages
# ==================================================================================================

def test_resource_rsp_detail_renders_the_person_and_the_skills_lens(
        client_a, resource_employee_a, resource_profile_internal, resource_profile_contractor):
    resp = _resource_get(client_a, "rsp_detail", resource_profile_internal.pk)
    assert resp.status_code == 200
    assert "projects/resource/resourceprofile/detail.html" in _resource_templates(resp)
    assert resp.context["obj"].pk == resource_profile_internal.pk
    body = _resource_body(resp)
    assert resource_profile_internal.number in body
    assert "Alex Rivera" in body
    # the employee-keyed row deep-links the HRM skills lens with its own employee filter
    assert f"employee={resource_employee_a.pk}" in body

    resp = _resource_get(client_a, "rsp_detail", resource_profile_contractor.pk)
    assert resp.status_code == 200
    body = _resource_body(resp)
    assert resource_profile_contractor.number in body
    assert "Priya Raman" in body


def test_resource_ral_detail_surfaces_resources_and_the_successor(
        client_a, resource_profile_internal, resource_allocation_named_soft,
        resource_allocation_released, resource_allocation_successor,
        resource_allocation_placeholder_requested):
    resp = _resource_get(client_a, "ral_detail", resource_allocation_released.pk)
    assert resp.status_code == 200
    assert "projects/resource/resourceallocation/detail.html" in _resource_templates(resp)
    assert resp.context["obj"].pk == resource_allocation_released.pk
    # the substitution chain: the released row surfaces its hand-built successor
    assert resp.context["successor"].pk == resource_allocation_successor.pk
    assert resource_profile_internal in list(resp.context["resources"])
    body = _resource_body(resp)
    assert resource_allocation_released.number in body
    assert resource_allocation_successor.number in body

    resp = _resource_get(client_a, "ral_detail", resource_allocation_named_soft.pk)
    assert resp.status_code == 200
    assert resp.context["successor"] is None

    resp = _resource_get(client_a, "ral_detail", resource_allocation_placeholder_requested.pk)
    assert resp.status_code == 200
    assert "Placeholder" in _resource_body(resp)


def test_resource_rte_detail_renders_the_row(client_a, resource_entry_rejected):
    resp = _resource_get(client_a, "rte_detail", resource_entry_rejected.pk)
    assert resp.status_code == 200
    assert "projects/resource/resourcetimeentry/detail.html" in _resource_templates(resp)
    assert resp.context["obj"].pk == resource_entry_rejected.pk
    body = _resource_body(resp)
    assert resource_entry_rejected.number in body
    assert "re-log the extra hour under support." in body   # the decision note renders


# ==================================================================================================
# 7. The creates - form pages, saves with tenant + audit + provenance, prefill, refusals
# ==================================================================================================

def test_resource_every_create_page_renders_an_unbound_form(client_a):
    for route in ("rsp_create", "ral_create", "rte_create"):
        resp = _resource_get(client_a, route)
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False
        assert "obj" not in resp.context
        assert not resp.context["form"].is_bound


def test_resource_rsp_create_saves_the_row_with_tenant_and_audit(
        client_a, tenant_a, resource_party_a):
    resp = _resource_post(client_a, "rsp_create", data=_resource_rsp_payload(
        party=str(resource_party_a.pk), skill_summary="pytest, selenium"))
    assert resp.status_code == 302
    obj = ResourceProfile.objects.get(default_role="Field auditor")
    assert resp["Location"] == _resource_url("rsp_detail", obj.pk)
    assert obj.number.startswith("RSP-") and obj.tenant_id == tenant_a.pk
    assert obj.name == "Priya Raman"
    assert _resource_said(resp, f"Resource {obj.number} created.")
    audits = _resource_audits(obj)
    assert [audit.action for audit in audits] == ["create"]


def test_resource_ral_create_stamps_requested_by_and_audits(client_a, tenant_a, admin_user,
                                                            resource_project):
    resp = _resource_post(client_a, "ral_create", data=_resource_ral_payload(
        resource_project, skill_requirements="Python"))
    assert resp.status_code == 302
    obj = ResourceAllocation.objects.get(role_name="Field auditor")
    assert resp["Location"] == _resource_url("ral_detail", obj.pk)
    assert obj.number.startswith("RAL-") and obj.tenant_id == tenant_a.pk
    # provenance is stamped from the POSTing user, and booking_status is verb-driven, never a form
    assert obj.requested_by_id == admin_user.pk
    assert obj.booking_status == "requested"
    assert _resource_said(resp, f"Allocation {obj.number} created.")
    assert [audit.action for audit in _resource_audits(obj)] == ["create"]


def test_resource_rte_create_saves_the_row_and_audits(client_a, tenant_a, resource_project,
                                                      resource_profile_internal):
    resp = _resource_post(client_a, "rte_create", data=_resource_rte_payload(
        resource_profile_internal, project=str(resource_project.pk),
        task_description="Day one"))
    assert resp.status_code == 302
    obj = ResourceTimeEntry.objects.get(task_description="Day one")
    assert resp["Location"] == _resource_url("rte_detail", obj.pk)
    assert obj.number.startswith("RTE-") and obj.tenant_id == tenant_a.pk
    # status and the stamps are verb-driven - a fresh entry is born draft and stamp-less
    assert obj.status == "draft" and obj.submitted_at is None
    assert _resource_said(resp, f"Time entry {obj.number} created.")
    assert [audit.action for audit in _resource_audits(obj)] == ["create"]


def test_resource_create_prefills_from_the_query_string(
        client_a, resource_project, resource_profile_internal):
    """As-built: ``ral_create`` reads BOTH ``?project=`` and ``?resource=``, ``rte_create`` reads
    ``?resource=`` - the initial lands on the unbound form's values."""
    resp = _resource_get(client_a, "ral_create", project=str(resource_project.pk),
                         resource=str(resource_profile_internal.pk))
    assert resp.status_code == 200
    assert resp.context["form"].initial["project"] == str(resource_project.pk)
    assert resp.context["form"].initial["resource"] == str(resource_profile_internal.pk)

    resp = _resource_get(client_a, "rte_create", resource=str(resource_profile_internal.pk))
    assert resp.status_code == 200
    assert resp.context["form"].initial["resource"] == str(resource_profile_internal.pk)

    # without the query string there is no prefill
    resp = _resource_get(client_a, "ral_create")
    assert resp.context["form"].initial["project"] == ""
    assert resp.context["form"].initial["resource"] == ""


def test_resource_create_redisplays_the_form_on_an_invalid_post(client_a, tenant_a):
    resp = _resource_post(client_a, "rsp_create", data=_resource_rsp_payload())
    assert resp.status_code == 200
    form = resp.context["form"]
    assert form.is_bound and form.errors
    # neither identity given - the exactly-one-of rule surfaces as a non-field error
    assert any("exactly one of the two" in error for error in form.non_field_errors())
    assert ResourceProfile.objects.filter(tenant=tenant_a).count() == 0

    resp = _resource_post(client_a, "ral_create", data=_resource_ral_payload(None))
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert any("project or a project request" in error
               for error in resp.context["form"].non_field_errors())
    assert ResourceAllocation.objects.filter(tenant=tenant_a).count() == 0

    resp = _resource_post(client_a, "rte_create", data=_resource_rte_payload(None))
    assert resp.status_code == 200
    assert "resource" in resp.context["form"].errors
    assert ResourceTimeEntry.objects.filter(tenant=tenant_a).count() == 0


def test_resource_create_pages_turn_a_tenantless_user_away(resource_tenantless_client):
    """All three create views guard ``request.tenant is None`` on their FIRST line - redirect to
    the dashboard with the pinned message, never a form with unscoped dropdowns."""
    for route in ("rsp_create", "ral_create", "rte_create"):
        resp = resource_tenantless_client.get(_resource_url(route))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard:home")
        assert _resource_said(resp, "Select a tenant workspace before creating records.")


# ==================================================================================================
# 8. The edits - saves with audit, smuggled verb state ignored, the approved/rejected lock
# ==================================================================================================

def test_resource_every_edit_page_renders_the_row_it_edits(
        client_a, resource_profile_internal, resource_allocation_named_soft, resource_entry_draft):
    for route, obj in (("rsp_edit", resource_profile_internal),
                       ("ral_edit", resource_allocation_named_soft),
                       ("rte_edit", resource_entry_draft)):
        resp = _resource_get(client_a, route, obj.pk)
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True
        assert resp.context["obj"].pk == obj.pk
        assert resp.context["form"].instance.pk == obj.pk


def test_resource_edits_save_audit_and_never_touch_verb_state(
        client_a, tenant_a, admin_user, resource_org_unit_a, resource_project,
        resource_profile_internal, resource_allocation_named_soft, resource_entry_submitted):
    """A valid edit POST changes its fields, audits an ``update``, and ignores every smuggled
    verb-driven value: ``booking_status`` on the allocation, ``status`` and the approval stamps
    on the time entry (L20 - none of them are form fields)."""
    # -- rsp: values change and the audit carries the changed field
    resp = _resource_post(client_a, "rsp_edit", resource_profile_internal.pk, data={
        "employee": str(resource_profile_internal.employee_id), "party": "",
        "resource_type": "internal", "default_role": "Senior data engineer",
        "org_unit": str(resource_org_unit_a.pk), "skill_summary": "Python, Django, Airflow",
        "weekly_capacity_hours": "40.00", "utilization_target_pct": "80",
        "available_from": "", "available_to": "", "status": "active", "notes": ""})
    assert resp.status_code == 302
    assert resp["Location"] == _resource_url("rsp_list")
    resource_profile_internal.refresh_from_db()
    assert resource_profile_internal.default_role == "Senior data engineer"
    audits = _resource_audits(resource_profile_internal, "update")
    assert len(audits) == 1
    assert audits[0].changes == {"default_role": "Senior data engineer"}

    # -- ral: booking_status/substitute_of/requested_by are untouchable through the form
    before = _resource_snapshot(resource_allocation_named_soft)
    resp = _resource_post(client_a, "ral_edit", resource_allocation_named_soft.pk, data={
        "project": str(resource_project.pk), "project_request": "", "project_task": "",
        "resource": str(resource_profile_internal.pk), "role_name": "Data engineer, rescoped",
        "skill_requirements": "Python, Airflow", "allocation_unit": "hours_per_week",
        "hours_per_week": "16.00", "pct_capacity": "", "total_hours": "",
        "start_date": before["start_date"].isoformat(),
        "end_date": (before["end_date"] or "").isoformat() if before["end_date"] else "",
        "notes": "",
        "booking_status": "firm", "substitute_of": "1", "requested_by": "999"})
    assert resp.status_code == 302
    assert resp["Location"] == _resource_url("ral_list")
    resource_allocation_named_soft.refresh_from_db()
    assert resource_allocation_named_soft.role_name == "Data engineer, rescoped"
    assert resource_allocation_named_soft.booking_status == "soft"
    assert resource_allocation_named_soft.substitute_of_id == before["substitute_of_id"]
    assert resource_allocation_named_soft.requested_by_id == before["requested_by_id"]

    # -- rte: the stamps survive a normal edit POST untouched
    entry = resource_entry_submitted
    before = _resource_snapshot(entry)
    resp = _resource_post(client_a, "rte_edit", entry.pk, data={
        "resource": str(entry.resource_id), "project": str(resource_project.pk),
        "project_task": "", "entry_date": before["entry_date"].isoformat(),
        "hours": "7.50", "task_description": "Project implementation work", "notes": "",
        "status": "approved", "submitted_at": "2020-01-01T00:00",
        "approved_at": "2020-01-01T00:00", "approved_by": "999",
        "decision_note": "forged note"})
    assert resp.status_code == 302
    assert resp["Location"] == _resource_url("rte_list")
    entry.refresh_from_db()
    assert entry.hours == Decimal("7.50")
    assert entry.status == "submitted"
    assert entry.decision_note == ""
    assert entry.submitted_at == before["submitted_at"]
    assert entry.approved_by_id == before["approved_by_id"] is None
    assert entry.approved_at == before["approved_at"] is None


def test_resource_rte_edit_is_locked_once_approved_or_rejected(
        client_a, resource_entry_approved, resource_entry_rejected):
    """The lock runs BEFORE crud_edit (double fetch accepted): GET and POST both redirect to the
    detail page with the pinned refusal, and the row stays byte-for-byte."""
    for entry in (resource_entry_approved, resource_entry_rejected):
        before = _resource_snapshot(entry)
        resp = _resource_get(client_a, "rte_edit", entry.pk)
        assert resp.status_code == 302
        assert resp["Location"] == _resource_url("rte_detail", entry.pk)
        assert _resource_said(resp, "cannot be edited")
        resp = _resource_post(client_a, "rte_edit", entry.pk,
                              data=_resource_rte_payload(entry.resource, hours="9.99"))
        assert resp.status_code == 302
        assert _resource_said(resp, "cannot be edited")
        _resource_unchanged(entry, before)


# ==================================================================================================
# 9. The deletes - POST-only, audited, and locked for decided entries
# ==================================================================================================

def test_resource_delete_removes_the_row_on_post_and_audits(
        client_a, resource_profile_contractor, resource_allocation_named_soft,
        resource_entry_draft):
    for route, list_route, obj in (("rsp_delete", "rsp_list", resource_profile_contractor),
                                   ("ral_delete", "ral_list", resource_allocation_named_soft),
                                   ("rte_delete", "rte_list", resource_entry_draft)):
        resp = _resource_post(client_a, route, obj.pk)
        assert resp.status_code == 302
        assert resp["Location"] == _resource_url(list_route)
        audits = _resource_audits(obj)
        assert [audit.action for audit in audits] == ["delete"]
        detail_route = route.replace("_delete", "_detail")
        assert _resource_get(client_a, detail_route, obj.pk).status_code == 404


def test_resource_rte_delete_is_locked_once_approved_or_rejected(
        client_a, resource_entry_approved, resource_entry_rejected):
    for entry in (resource_entry_approved, resource_entry_rejected):
        before = _resource_snapshot(entry)
        resp = _resource_post(client_a, "rte_delete", entry.pk)
        assert resp.status_code == 302
        assert resp["Location"] == _resource_url("rte_detail", entry.pk)
        assert _resource_said(resp, "cannot be deleted")
        _resource_unchanged(entry, before)
        assert ResourceTimeEntry.objects.filter(pk=entry.pk).exists()


def test_resource_every_post_only_route_refuses_a_get(client_a):
    """Admin GET on all 12 POST-only routes: the role gate passes, so ``@require_POST`` is what
    fires - 405, never a mutation, never a rendered page."""
    for name, args in _RESOURCE_POST_ONLY_ROUTES:
        resp = client_a.get(_resource_url(name, *args))
        assert resp.status_code == 405, f"{name} answered a GET with {resp.status_code}"


# ==================================================================================================
# 10. ral_assign - the staffing verb (admin-gated; state machine + refusals)
# ==================================================================================================

def test_resource_ral_assign_names_a_placeholder_and_walks_it_to_soft(
        client_a, resource_profile_contractor, resource_allocation_placeholder_requested):
    obj = resource_allocation_placeholder_requested
    resp = _resource_post(client_a, "ral_assign", obj.pk,
                          data={"resource": str(resource_profile_contractor.pk)})
    assert resp.status_code == 302
    assert resp["Location"] == _resource_url("ral_detail", obj.pk)
    assert _resource_said(resp, f"Assigned Priya Raman to allocation {obj.number}.")
    obj.refresh_from_db()
    assert obj.resource_id == resource_profile_contractor.pk
    assert obj.booking_status == "soft"     # requested walked to soft by the assign
    audits = _resource_audits(obj, "assign")
    assert len(audits) == 1
    assert audits[0].changes == {"verb": "assign", "resource": "Priya Raman",
                                 "was": "requested"}


def test_resource_ral_assign_on_a_soft_placeholder_keeps_it_soft(
        client_a, resource_profile_internal, resource_allocation_placeholder_soft):
    obj = resource_allocation_placeholder_soft
    resp = _resource_post(client_a, "ral_assign", obj.pk,
                          data={"resource": str(resource_profile_internal.pk)})
    assert resp.status_code == 302
    assert _resource_said(resp, f"Assigned Alex Rivera to allocation {obj.number}.")
    obj.refresh_from_db()
    assert obj.resource_id == resource_profile_internal.pk
    assert obj.booking_status == "soft"     # already soft - the assign must not re-grade it
    assert _resource_audits(obj, "assign")[0].changes["was"] == "soft"


def test_resource_ral_assign_refusals(
        client_a, tenant_a, resource_profile_internal, resource_profile_b,
        resource_allocation_named_firm, resource_allocation_placeholder_requested):
    """Already-named, terminal-state, and no/bad/foreign resource POSTs all refuse with a message
    and a byte-identical row - a foreign resource pk is just another unassignable value.

    The as-built check ORDER matters for the terminal-state case: the view refuses an
    already-named row BEFORE its status gate, so the status refusal is only reachable on a
    resource-less row - here a factory-built completed placeholder."""
    named = resource_allocation_named_firm
    before = _resource_snapshot(named)
    resp = _resource_post(client_a, "ral_assign", named.pk,
                          data={"resource": str(resource_profile_internal.pk)})
    assert resp.status_code == 302
    assert _resource_said(resp, "already names a resource")
    assert "error" in _resource_levels(resp)
    _resource_unchanged(named, before)

    done = _resource_allocation(tenant_a, project=resource_allocation_named_firm.project,
                                resource=None, booking_status="completed")
    before = _resource_snapshot(done)
    resp = _resource_post(client_a, "ral_assign", done.pk,
                          data={"resource": str(resource_profile_internal.pk)})
    assert _resource_said(resp, "allocation cannot be staffed")
    _resource_unchanged(done, before)

    fresh = resource_allocation_placeholder_requested
    before = _resource_snapshot(fresh)
    for data in ({}, {"resource": ""}, {"resource": "abc"}, {"resource": "0"},
                 {"resource": str(resource_profile_b.pk)}):
        resp = _resource_post(client_a, "ral_assign", fresh.pk, data=data)
        assert resp.status_code == 302
        assert _resource_said(resp, "Choose a resource to assign")
        _resource_unchanged(fresh, before)
    fresh.refresh_from_db()
    assert fresh.resource_id is None and fresh.booking_status == "requested"


# ==================================================================================================
# 11. ral_substitute - release + successor inside the transaction
# ==================================================================================================

def test_resource_ral_substitute_releases_and_books_the_successor(
        client_a, tenant_a, admin_user, resource_project, resource_profile_contractor,
        resource_allocation_named_soft):
    original = resource_allocation_named_soft
    resp = _resource_post(client_a, "ral_substitute", original.pk,
                          data={"resource": str(resource_profile_contractor.pk)})
    assert resp.status_code == 302
    successor = ResourceAllocation.objects.get(substitute_of=original)
    assert resp["Location"] == _resource_url("ral_detail", successor.pk)
    assert _resource_said(resp, f"Released {original.number}; Priya Raman booked on successor "
                          f"{successor.number}.")

    original.refresh_from_db()
    assert original.booking_status == "released"

    # the successor copies the booking, carries the ORIGINAL status, and points back
    assert successor.number.startswith("RAL-")
    assert successor.tenant_id == tenant_a.pk
    assert successor.resource_id == resource_profile_contractor.pk
    assert successor.booking_status == "soft"
    assert successor.project_id == resource_project.pk
    assert successor.role_name == original.role_name
    assert successor.skill_requirements == original.skill_requirements
    assert successor.allocation_unit == original.allocation_unit
    assert successor.hours_per_week == original.hours_per_week
    assert successor.start_date == original.start_date
    assert successor.end_date == original.end_date
    assert successor.requested_by_id == admin_user.pk
    assert successor.substitute_of_id == original.pk

    audits = _resource_audits(original, "substitute")
    assert len(audits) == 1      # ONE row, on the released allocation
    assert audits[0].changes == {"verb": "substitute", "released": original.number,
                                 "successor": successor.number, "resource": "Priya Raman"}


def test_resource_ral_substitute_refuses_placeholders_and_terminal_states(
        client_a, tenant_a, resource_profile_internal, resource_profile_b,
        resource_allocation_named_firm, resource_allocation_completed,
        resource_allocation_placeholder_requested, resource_allocation_placeholder_soft):
    for placeholder in (resource_allocation_placeholder_requested,
                        resource_allocation_placeholder_soft):
        before = _resource_snapshot(placeholder)
        resp = _resource_post(client_a, "ral_substitute", placeholder.pk,
                              data={"resource": str(resource_profile_internal.pk)})
        assert resp.status_code == 302
        assert _resource_said(resp, "is a placeholder")
        _resource_unchanged(placeholder, before)

    done = resource_allocation_completed
    before = _resource_snapshot(done)
    resp = _resource_post(client_a, "ral_substitute", done.pk,
                          data={"resource": str(resource_profile_internal.pk)})
    assert _resource_said(resp, "this one is completed")
    _resource_unchanged(done, before)

    firm = resource_allocation_named_firm
    before = _resource_snapshot(firm)
    for data in ({}, {"resource": ""}, {"resource": "abc"},
                 {"resource": str(resource_profile_b.pk)}):
        resp = _resource_post(client_a, "ral_substitute", firm.pk, data=data)
        assert resp.status_code == 302
        assert _resource_said(resp, "Choose the replacement resource")
        _resource_unchanged(firm, before)
    firm.refresh_from_db()
    assert firm.booking_status == "firm"
    assert not firm.substituted_by.exists()


def test_resource_ral_substitute_rechecks_state_inside_the_transaction(
        client_a, tenant_a, resource_project, resource_profile_internal,
        resource_profile_contractor):
    """The as-built in-transaction re-check (``select_for_update``): a row that PASSES the
    pre-transaction checks (named, soft/firm, a valid different replacement) but ALREADY has a
    successor must still refuse inside the lock - one booking can never release into two."""
    original = _resource_allocation(tenant_a, project=resource_project,
                                    resource=resource_profile_internal, booking_status="firm",
                                    hours_per_week=Decimal("8.00"))
    _resource_allocation(tenant_a, project=resource_project,
                         resource=resource_profile_contractor, booking_status="firm",
                         substitute_of=original, hours_per_week=Decimal("8.00"))
    before = _resource_snapshot(original)
    resp = _resource_post(client_a, "ral_substitute", original.pk,
                          data={"resource": str(resource_profile_contractor.pk)})
    assert resp.status_code == 302
    assert _resource_said(resp, "Only a soft or firm booking can be substituted")
    _resource_unchanged(original, before)
    assert ResourceAllocation.objects.filter(substitute_of=original).count() == 1


def test_resource_ral_substitute_rejects_the_same_resource(
        client_a, resource_profile_internal, resource_allocation_named_soft):
    obj = resource_allocation_named_soft
    before = _resource_snapshot(obj)
    resp = _resource_post(client_a, "ral_substitute", obj.pk,
                          data={"resource": str(resource_profile_internal.pk)})
    assert resp.status_code == 302
    assert _resource_levels(resp) == ["info"]
    assert _resource_said(resp, "That is already the assigned resource")
    _resource_unchanged(obj, before)


# ==================================================================================================
# 12. ral_commit / ral_complete / ral_cancel - the member-level booking verbs
# ==================================================================================================

def test_resource_ral_commit_walks_requested_to_soft_and_soft_to_firm(
        client_a, resource_allocation_placeholder_requested, resource_allocation_named_soft):
    placeholder = resource_allocation_placeholder_requested
    resp = _resource_post(client_a, "ral_commit", placeholder.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _resource_url("ral_detail", placeholder.pk)
    assert _resource_said(resp, f"Allocation {placeholder.number} soft-booked.")
    placeholder.refresh_from_db()
    assert placeholder.booking_status == "soft"   # requested -> soft IS the pipeline signal
    audits = _resource_audits(placeholder, "commit")
    assert audits[0].changes == {"verb": "commit", "from": "requested", "to": "soft"}

    soft = resource_allocation_named_soft
    resp = _resource_post(client_a, "ral_commit", soft.pk)
    assert _resource_said(resp, f"Allocation {soft.number} committed.")
    soft.refresh_from_db()
    assert soft.booking_status == "firm"
    audits = _resource_audits(soft, "commit")
    assert audits[0].changes == {"verb": "commit", "from": "soft", "to": "firm"}


def test_resource_ral_commit_refuses_a_placeholder_and_a_firm_booking(
        client_a, resource_allocation_placeholder_soft, resource_allocation_named_firm):
    """The I3 fix: a soft PLACEHOLDER cannot be firmed (a firm placeholder would vanish from BOTH
    the capacity board and the demand section) - and the refusal text is pinned verbatim."""
    placeholder = resource_allocation_placeholder_soft
    before = _resource_snapshot(placeholder)
    resp = _resource_post(client_a, "ral_commit", placeholder.pk)
    assert resp.status_code == 302
    assert _resource_said(resp, "Assign a resource before committing a placeholder to firm")
    _resource_unchanged(placeholder, before)
    placeholder.refresh_from_db()
    assert placeholder.booking_status == "soft"

    # the {display.lower()} two-word form: "Firm Booked" -> "this one is firm booked."
    firm = resource_allocation_named_firm
    before = _resource_snapshot(firm)
    resp = _resource_post(client_a, "ral_commit", firm.pk)
    assert _resource_said(resp, "this one is firm booked")
    _resource_unchanged(firm, before)


def test_resource_ral_complete_walks_soft_and_firm_to_completed(
        client_a, resource_allocation_named_soft, resource_allocation_named_firm):
    for obj in (resource_allocation_named_soft, resource_allocation_named_firm):
        resp = _resource_post(client_a, "ral_complete", obj.pk)
        assert resp.status_code == 302
        assert resp["Location"] == _resource_url("ral_detail", obj.pk)
        assert _resource_said(resp, f"Allocation {obj.number} completed.")
        obj.refresh_from_db()
        assert obj.booking_status == "completed"
        assert [audit.action for audit in _resource_audits(obj, "complete")] == ["complete"]


def test_resource_ral_complete_refuses_a_requested_booking(
        client_a, resource_allocation_placeholder_requested):
    obj = resource_allocation_placeholder_requested
    before = _resource_snapshot(obj)
    resp = _resource_post(client_a, "ral_complete", obj.pk)
    assert resp.status_code == 302
    assert _resource_said(resp, "this one is requested")
    _resource_unchanged(obj, before)


def test_resource_ral_cancel_walks_requested_and_firm_to_cancelled(
        client_a, resource_allocation_placeholder_requested, resource_allocation_named_firm):
    for obj in (resource_allocation_placeholder_requested, resource_allocation_named_firm):
        resp = _resource_post(client_a, "ral_cancel", obj.pk)
        assert resp.status_code == 302
        assert resp["Location"] == _resource_url("ral_detail", obj.pk)
        assert _resource_said(resp, f"Allocation {obj.number} cancelled.")
        obj.refresh_from_db()
        assert obj.booking_status == "cancelled"
        assert [audit.action for audit in _resource_audits(obj, "cancel")] == ["cancel"]


def test_resource_ral_cancel_refusals(client_a, resource_allocation_cancelled,
                                      resource_allocation_completed,
                                      resource_allocation_released):
    cancelled = resource_allocation_cancelled
    before = _resource_snapshot(cancelled)
    resp = _resource_post(client_a, "ral_cancel", cancelled.pk)
    assert resp.status_code == 302
    assert _resource_levels(resp) == ["info"]
    assert _resource_said(resp, "That allocation is already cancelled")
    _resource_unchanged(cancelled, before)

    done = resource_allocation_completed
    before = _resource_snapshot(done)
    resp = _resource_post(client_a, "ral_cancel", done.pk)
    assert _resource_said(resp, "A completed booking cannot be cancelled")
    _resource_unchanged(done, before)

    released = resource_allocation_released
    before = _resource_snapshot(released)
    resp = _resource_post(client_a, "ral_cancel", released.pk)
    assert _resource_said(resp, "A released booking cannot be cancelled")
    _resource_unchanged(released, before)


# ==================================================================================================
# 13. rte_submit / rte_approve / rte_reject - the day-entry workflow
# ==================================================================================================

def test_resource_rte_submit_stamps_submitted_at_once(client_a, resource_entry_draft):
    obj = resource_entry_draft
    resp = _resource_post(client_a, "rte_submit", obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _resource_url("rte_detail", obj.pk)
    assert _resource_said(resp, f"Entry {obj.number} submitted for approval.")
    obj.refresh_from_db()
    assert obj.status == "submitted"
    assert obj.submitted_at is not None
    assert [audit.action for audit in _resource_audits(obj, "submit")] == ["submit"]

    before = _resource_snapshot(obj)
    resp = _resource_post(client_a, "rte_submit", obj.pk)
    assert resp.status_code == 302
    # messages queue up in the session across the test's requests - pin the LEVEL, not the list
    assert "info" in _resource_levels(resp)
    assert _resource_said(resp, "already awaiting approval")
    _resource_unchanged(obj, before)


def test_resource_rte_submit_refuses_approved_and_rejected(
        client_a, resource_entry_approved, resource_entry_rejected):
    """A rejected entry can NEVER be resubmitted - re-log instead (the evidence ruling)."""
    for entry in (resource_entry_approved, resource_entry_rejected):
        before = _resource_snapshot(entry)
        resp = _resource_post(client_a, "rte_submit", entry.pk)
        assert resp.status_code == 302
        assert _resource_said(resp, "An approved or rejected entry cannot be submitted")
        _resource_unchanged(entry, before)


def test_resource_rte_approve_stamps_once(client_a, admin_user, resource_entry_submitted):
    obj = resource_entry_submitted
    resp = _resource_post(client_a, "rte_approve", obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _resource_url("rte_detail", obj.pk)
    assert _resource_said(resp, f"Entry {obj.number} approved.")
    obj.refresh_from_db()
    assert obj.status == "approved"
    assert obj.approved_by_id == admin_user.pk
    assert obj.approved_at is not None
    assert [audit.action for audit in _resource_audits(obj, "approve")] == ["approve"]

    before = _resource_snapshot(obj)
    resp = _resource_post(client_a, "rte_approve", obj.pk)
    assert resp.status_code == 302
    assert _resource_said(resp, "this one is approved")
    _resource_unchanged(obj, before)      # a replay re-stamps nothing


def test_resource_rte_approve_refuses_a_draft(client_a, resource_entry_draft):
    obj = resource_entry_draft
    before = _resource_snapshot(obj)
    resp = _resource_post(client_a, "rte_approve", obj.pk)
    assert resp.status_code == 302
    assert _resource_said(resp, "this one is draft")
    _resource_unchanged(obj, before)
    obj.refresh_from_db()
    assert obj.status == "draft" and obj.approved_by_id is None


def test_resource_rte_reject_records_the_reason_and_the_decision_stamps(
        client_a, admin_user, resource_entry_submitted):
    obj = resource_entry_submitted
    resp = _resource_post(client_a, "rte_reject", obj.pk,
                          data={"reason": "  Client call overran.  "})
    assert resp.status_code == 302
    assert resp["Location"] == _resource_url("rte_detail", obj.pk)
    assert _resource_said(resp, f"Entry {obj.number} rejected.")
    obj.refresh_from_db()
    assert obj.status == "rejected"
    assert obj.decision_note == "Client call overran."   # the reason is stripped, not echoed raw
    assert obj.approved_by_id == admin_user.pk
    assert obj.approved_at is not None
    audits = _resource_audits(obj, "reject")
    assert audits[0].changes == {"verb": "reject", "reason": "Client call overran."}


def test_resource_rte_reject_refuses_a_draft(client_a, resource_entry_draft):
    obj = resource_entry_draft
    before = _resource_snapshot(obj)
    resp = _resource_post(client_a, "rte_reject", obj.pk, data={"reason": "nope"})
    assert resp.status_code == 302
    assert _resource_said(resp, "can be rejected")
    _resource_unchanged(obj, before)


# ==================================================================================================
# 14. rte_approve_week - the bulk person-week verb (one audit row on the RESOURCE)
# ==================================================================================================

def test_resource_rte_approve_week_bulk_approves_the_person_week(
        client_a, tenant_a, admin_user, resource_project, resource_profile_internal,
        resource_entry_submitted, resource_entry_draft):
    person = resource_profile_internal
    week_entry = resource_entry_submitted
    year, week = week_entry.iso_year, week_entry.iso_week
    extras = [
        _resource_entry(tenant_a, person, project=resource_project, status="submitted",
                        hours=Decimal("7.00"), submitted_at=timezone.now())
        for _index in range(2)
    ]
    resp = _resource_post(client_a, "rte_approve_week", person.pk, year, week)
    assert resp.status_code == 302
    assert resp["Location"] == _resource_url("rte_list")
    assert _resource_said(resp, f"Approved 3 entries for {person.name}, week {week}.")
    for entry in [week_entry] + extras:
        entry.refresh_from_db()
        assert entry.status == "approved"
        assert entry.approved_by_id == admin_user.pk
        assert entry.approved_at is not None
    resource_entry_draft.refresh_from_db()
    assert resource_entry_draft.status == "draft"   # drafts are not the approval queue
    audits = _resource_audits(person, "approve")
    assert len(audits) == 1                         # ONE row for the whole batch
    assert audits[0].changes == {"verb": "approve_week", "week": f"{year}-W{week:02d}",
                                 "count": 3}


def test_resource_rte_approve_week_reports_a_week_with_no_queue(
        client_a, resource_profile_contractor, resource_entry_submitted):
    week_entry = resource_entry_submitted
    resp = _resource_post(client_a, "rte_approve_week", resource_profile_contractor.pk,
                          week_entry.iso_year, week_entry.iso_week)
    assert resp.status_code == 302
    assert _resource_levels(resp) == ["info"]
    assert _resource_said(resp, "No submitted entries for "
                          f"{resource_profile_contractor.name} in week {week_entry.iso_week}.")


def test_resource_rte_approve_week_guards_the_week_range(client_a, resource_profile_internal):
    for week in (0, 99):
        resp = _resource_post(client_a, "rte_approve_week", resource_profile_internal.pk,
                              2025, week)
        assert resp.status_code == 302
        assert _resource_said(resp, "Week must be between 1 and 53")


def test_resource_rte_approve_week_refuses_a_fake_iso_week(client_a, resource_profile_internal):
    """2025 has 52 ISO weeks - ``date.fromisocalendar`` raises and the view answers with the
    pinned message instead of a 500."""
    resp = _resource_post(client_a, "rte_approve_week", resource_profile_internal.pk, 2025, 53)
    assert resp.status_code == 302
    assert _resource_said(resp, "2025 week 53 is not a real ISO week")


# ==================================================================================================
# 15. The capacity & demand board - computed on read, expectations computed in the tests
# ==================================================================================================

def test_resource_capacity_board_renders_context_keys_and_the_fixture_baseline(
        client_a, resource_allocation_named_firm, resource_allocation_named_soft,
        resource_allocation_soft_pct, resource_allocation_placeholder_requested,
        resource_allocation_placeholder_soft, resource_allocation_request_placeholder):
    """The default fixture set's pinned baseline: over_count 0 (16<=40, 12<=40, 12<=24), five
    demand rows (4 project-linked by start_date, then 1 request-linked), three gaps."""
    resp = _resource_get(client_a, "capacity_demand")
    assert resp.status_code == 200
    assert "projects/resource/capacity_demand.html" in _resource_templates(resp)
    for key in ("weeks", "week_windows", "capacity_rows", "over_count", "demand_rows",
                "gap_count"):
        assert key in resp.context, f"capacity_demand dropped its pinned key: {key}"
    assert resp.context["weeks"] == 8
    assert len(resp.context["week_windows"]) == 8
    assert resp.context["over_count"] == 0
    for profile in resp.context["capacity_rows"]:
        assert not any(cell["over"] for cell in profile.cells)
    assert len(resp.context["demand_rows"]) == 5
    assert resp.context["gap_count"] == 3
    body = _resource_body(resp)
    assert "leave and absence" in body and "not deducted yet" in body   # the caveat, verbatim


def test_resource_capacity_horizon_follows_the_weeks_param(client_a):
    """``?weeks=`` clamps to 4..13 (default 8); every window opens on an ISO Monday and carries
    year/week/start/end/label."""
    monday = _resource_iso_monday()
    resp = _resource_get(client_a, "capacity_demand")
    assert resp.context["weeks"] == 8
    windows = resp.context["week_windows"]
    assert len(windows) == 8
    for offset, window in enumerate(windows):
        assert window["start"] == monday + datetime.timedelta(weeks=offset)
        assert window["end"] == window["start"] + datetime.timedelta(days=6)
        assert window["year"] == window["start"].isocalendar()[0]
        assert window["week"] == window["start"].isocalendar()[1]
        assert window["label"].startswith(f"W{window['week']}")

    assert _resource_get(client_a, "capacity_demand", weeks="2").context["weeks"] == 4
    assert _resource_get(client_a, "capacity_demand", weeks="99").context["weeks"] == 13
    for junk in ("abc", "0", "-3"):
        assert _resource_get(client_a, "capacity_demand", weeks=junk).context["weeks"] == 8


def test_resource_capacity_over_count_matches_the_computed_expectation(
        client_a, tenant_a, resource_project):
    """A 48h/wk firm booking against a 40.00h capacity overBOOKS every window of the horizon:
    ``over_count`` must equal the computed number of over cells, each cell's planned must equal
    the booking's own ``planned_hours`` for that window, and the red badge must render."""
    resource = _resource_profile(tenant_a, default_role="Overbooked engineer")
    alloc = _resource_allocation(
        tenant_a, project=resource_project, resource=resource, hours_per_week=Decimal("48.00"),
        booking_status="firm", start_date=_resource_today() - datetime.timedelta(days=7),
        end_date=_resource_today() + datetime.timedelta(days=100))

    resp = _resource_get(client_a, "capacity_demand", weeks="4")
    windows = resp.context["week_windows"]
    # one booking: each cell's planned is exactly that booking's own planned_hours
    expected = [alloc.planned_hours(window["start"], window["end"]) for window in windows]
    assert len(expected) == 4
    for planned in expected:
        assert planned > Decimal("40.00")     # the scenario really is over capacity
    assert resp.context["over_count"] == len(windows)
    rows = {profile.pk: profile for profile in resp.context["capacity_rows"]}
    cells = rows[resource.pk].cells
    assert [cell["planned"] for cell in cells] == expected
    assert all(cell["over"] for cell in cells)
    body = _resource_body(resp)
    assert "Over" in body and "badge-red" in body


def test_resource_demand_rows_order_project_linked_first_and_flag_gaps(
        client_a, resource_project, resource_request, resource_allocation_named_soft,
        resource_allocation_soft_pct, resource_allocation_placeholder_requested,
        resource_allocation_placeholder_soft, resource_allocation_request_placeholder):
    project_rows = [resource_allocation_placeholder_soft, resource_allocation_named_soft,
                    resource_allocation_soft_pct, resource_allocation_placeholder_requested]
    expected_order = sorted(project_rows, key=lambda alloc: (alloc.start_date, -alloc.pk))
    resp = _resource_get(client_a, "capacity_demand")
    demand = resp.context["demand_rows"]
    assert [alloc.pk for alloc in demand] == ([alloc.pk for alloc in expected_order]
                                              + [resource_allocation_request_placeholder.pk])
    for alloc in demand:
        if alloc.project_id:
            assert alloc.demand_label == resource_project.name
            assert alloc.demand_url_name == "projects:prj_detail"
            assert alloc.demand_url_pk == resource_project.pk
        else:
            assert alloc.demand_label == resource_request.title
            assert alloc.demand_url_name == "projects:prq_detail"
            assert alloc.demand_url_pk == resource_request.pk
        assert alloc.is_gap == (alloc.resource_id is None)
    gap_rows = [alloc for alloc in demand if alloc.is_gap]
    assert {alloc.pk for alloc in gap_rows} == {
        resource_allocation_placeholder_requested.pk, resource_allocation_placeholder_soft.pk,
        resource_allocation_request_placeholder.pk}
    assert resp.context["gap_count"] == 3


def test_resource_demand_hours_sum_the_horizon_windows(client_a, tenant_a, resource_project):
    """A soft booking whose window fully covers a 4-week horizon plans exactly 16h in each window
    - 64.00h of demand in total (computed from the pinned math, not hardcoded per-cell)."""
    weeks = 4
    monday = _resource_iso_monday()
    horizon_end = monday + datetime.timedelta(weeks=weeks - 1, days=6)
    resource = _resource_profile(tenant_a, default_role="Covered engineer")
    alloc = _resource_allocation(
        tenant_a, project=resource_project, resource=resource, hours_per_week=Decimal("16.00"),
        booking_status="soft", start_date=monday - datetime.timedelta(days=1),
        end_date=horizon_end + datetime.timedelta(days=1))
    resp = _resource_get(client_a, "capacity_demand", weeks=str(weeks))
    row = next(a for a in resp.context["demand_rows"] if a.pk == alloc.pk)
    assert row.demand_hours == Decimal("16.00") * weeks


# ==================================================================================================
# 16. The actuals-to-plan section - approved time vs live plan, per (resource, project)
# ==================================================================================================

def test_resource_actuals_pair_approved_time_with_live_plan(
        client_a, resource_project, resource_allocation_named_soft, resource_entry_draft,
        resource_entry_approved, resource_entry_approved_nonproject):
    """The pinned two-row section: the non-project pair (planned 0.00) first by variance, then
    the internal/project pair whose planned side is the live booking's ``planned_hours`` over
    the current ISO week - and every Decimal is quantized to the 0.01 the template renders."""
    resp = _resource_get(client_a, "rte_list")
    rows = resp.context["actuals_rows"]
    assert len(rows) == 2

    win_start, win_end = _resource_iso_window()
    planned = resource_allocation_named_soft.planned_hours(win_start, win_end)
    nonproject, project_row = rows[0], rows[1]
    assert nonproject["resource"].pk == resource_entry_approved_nonproject.resource_id
    assert nonproject["project"] is None
    assert nonproject["actual_hours"] == Decimal("4.00")
    assert nonproject["planned_hours"] == Decimal("0.00")
    assert nonproject["variance"] == Decimal("4.00")
    assert project_row["resource"].pk == resource_entry_approved.resource_id
    assert project_row["project"].pk == resource_project.pk
    assert project_row["actual_hours"] == Decimal("6.00")
    assert project_row["planned_hours"] == planned
    assert project_row["variance"] == Decimal("6.00") - planned
    for row in rows:
        for key in ("actual_hours", "planned_hours", "variance"):
            assert row[key].as_tuple().exponent == -2     # "0h" must never render next to "2.00h"
    assert "Non-project time" in _resource_body(resp)

    # the actuals window ignores ?q=/?status= - the register narrows, the pair stays
    resp = _resource_get(client_a, "rte_list", status="draft", q="zzz-nothing-zzz")
    assert resp.status_code == 200
    assert list(resp.context["object_list"]) == []
    assert len(resp.context["actuals_rows"]) == 2


def test_resource_actuals_window_follows_the_year_and_week_params(
        client_a, tenant_a, admin_user, resource_project, resource_profile_internal,
        resource_entry_approved):
    """``?year=``+``?week=`` switch both the register lens and the actuals window: an approved
    entry 200 days back only pairs against plan when its own ISO week is requested."""
    old = _resource_entry(
        tenant_a, resource_profile_internal, project=resource_project,
        entry_date=_resource_today() - datetime.timedelta(days=400), status="approved",
        hours=Decimal("3.00"), submitted_at=timezone.now() - datetime.timedelta(days=401),
        approved_by=admin_user, approved_at=timezone.now() - datetime.timedelta(days=400))

    resp = _resource_get(client_a, "rte_list")
    rows = resp.context["actuals_rows"]
    assert len(rows) == 1          # only the current week's approved pair
    assert rows[0]["actual_hours"] == Decimal("6.00")

    resp = _resource_get(client_a, "rte_list", year=str(old.iso_year), week=str(old.iso_week))
    assert _resource_pks(resp) == [old.pk]     # the register narrows to that week too
    rows = resp.context["actuals_rows"]
    assert len(rows) == 1
    assert rows[0]["actual_hours"] == Decimal("3.00")
    assert rows[0]["planned_hours"] == Decimal("0.00")   # no live booking reaches 200 days back
    assert rows[0]["variance"] == Decimal("3.00")


# ==================================================================================================
# 17. The register's query budget - the select_related pin (I6/I7)
# ==================================================================================================

def test_resource_ral_register_query_budget_stays_flat(
        client_a, tenant_a, resource_project, resource_profile_internal,
        django_assert_max_num_queries):
    """A full page of named bookings must render in a FLAT number of queries: the register's
    ``select_related`` covers project/request/task/resource->party, and the three dropdown
    querysets are one query each. Without it, 15 rows cost 3+ queries EACH (L20's N+1 shape)."""
    _resource_fill_allocations(tenant_a, RESOURCE_PAGE_SIZE, project=resource_project,
                               resource=resource_profile_internal, booking_status="soft")
    with django_assert_max_num_queries(22):
        resp = _resource_get(client_a, "ral_list")
    assert resp.status_code == 200
    assert len(list(resp.context["object_list"])) == RESOURCE_PAGE_SIZE
