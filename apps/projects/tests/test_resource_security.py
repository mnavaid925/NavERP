"""Projects 7.3 Resource Management - SECURITY tests.

The fourth and last 7.3 lane. ``test_resource_models.py`` owns the invariants,
``test_resource_forms.py`` the field lists and validation, ``test_resource_views.py`` the
functional HTTP layer (happy paths, filters, state gates, the capacity board, query budgets) -
every request in that lane is made by a tenant ADMIN of the row's OWN workspace, so the only
thing that can refuse a verb there is its own state gate. This file owns the three questions
those three never ask: **who may reach it, whose workspace is it, and what does the answer
disclose.**

What it locks down, finding by finding:

* **The login wall.** All 25 routes, GET and POST, redirect an anonymous caller to ``/login/``
  before any database work - and, more to the point, before any write: the nine verbs are
  re-posted against REAL tenant-A rows and the rows survive byte-for-byte, while the three
  create routes mint nothing.
* **The verb gating matrix (contract section 5, cell by cell).** Exactly five verbs are
  ``@tenant_admin_required`` (``ral_assign``, ``ral_substitute``, ``rte_approve``,
  ``rte_reject``, ``rte_approve_week``); the other four (``ral_commit``, ``ral_complete``,
  ``ral_cancel``, ``rte_submit``) are login-only. A member POSTs all nine at rows whose state
  gates ACCEPT: the 403 set must be exactly the five, with ZERO field deltas, and an admin
  replay proves each 403 is about the ROLE and not the row. The GET half follows the decorator
  stack ``login_required(tenant_admin_required(require_POST(view)))``: an admin GET is 405 on
  every verb; a member GET is **403 on the gated five** (the role check sits BETWEEN
  ``login_required`` and ``require_POST``, so role beats method) and **405 on the open four**
  (no role decorator, so the method check is the outermost thing left). 403-vs-404 depends on
  the ACTOR: the role check runs before ``get_object_or_404``, so IDOR-404 assertions use
  ``client_a`` (an admin) and member assertions never claim a 404 on a gated verb.
* **Cross-tenant IDOR - the highest-value class.** Every detail/edit GET and every delete/verb
  POST aimed by ``client_a`` at a tenant-B pk answers **404** (never 403, which would confirm
  the row exists, and never 500), with B's row byte-for-byte unchanged and NO audit row written
  for the foreign attempt. The three deletes are in here, so a scoping slip would DESTROY
  another workspace's row rather than merely read it. ``rte_approve_week`` is probed with a
  tenant-B RESOURCE pk - the person resolves first, so a foreign person 404s before any week
  check. Isolation is also asserted from B's side.
* **Tenant scoping of the registers and the computed pages.** A's registers never list B's
  rows, A's search never reaches B's text, a valid-but-foreign pk in an int filter yields a
  200 EMPTY register (a narrowing that matches nothing - not junk to skip, not the whole
  register), and the capacity/demand board never renders B's supply or demand.
* **Cross-tenant FK smuggling at the ROUTE.** A valid own-tenant create/edit POST carrying
  another workspace's ``employee`` / ``party`` / ``org_unit`` / ``project`` / ``resource`` pk
  is rejected as a FIELD ERROR and nothing lands, each paired with a same-tenant control that
  DOES create, so a malformed payload cannot read as a security win. The assertion is that the
  FIELD HAS AN ERROR - never the wording, because ``TenantModelForm`` narrows the queryset
  first and Django's own "Select a valid choice" message pre-empts ``_reject_foreign``'s
  "belongs to another workspace" sentence on every reachable path.
* **Verb-state tampering at the route (L20 / L22).** ``booking_status``, ``substitute_of``,
  ``requested_by``, the RTE ``status`` and its stamps are NOT form fields, so an edit POST
  smuggling them must be ignored - the edit's OWN fields land (proving the POST went through)
  while the verb-driven columns survive byte-for-byte, and a create POST cannot mint a firm
  booking, a false provenance or a foreign tenant.
* **CSRF (L44).** An admin-gated verb and a member verb are refused 403 on a token-enforcing
  client with a valid admin session (a token failure, not a login failure - the same client
  still reads), and the same POST succeeds once it carries the token.
* **``rte_approve_week`` hardening.** Weeks outside 1..53 and weeks the year does not have
  answer the polite message + redirect - never a 500 - and an empty queue writes nothing.
  Junk ``year``/``week`` are impossible by construction: the route declares ``<int:...>``
  converters, so a non-numeric year never resolves a route at all.
* **The ``tenant=None`` user.** The three create views turn the superuser shape away on their
  FIRST line (302 to ``dashboard:home``, nothing written) and every register renders EMPTY -
  the failure being guarded against is a view that special-cased the missing tenant into
  "show everything".

Conventions: every test is ``test_resource_*`` and every module-level helper
``_resource_*`` / ``_RESOURCE_*``, so no sibling lane appending into this package can shadow
either. Dates derive from ``timezone.localdate()`` (via the conftest's ``_resource_today``)
and datetimes from ``timezone.now()`` (L16); ``datetime.date.today()`` never appears. Nothing
here touches the network, the demo seeder or ``bulk_create``. The file is pure ASCII on
purpose: several 7.3 refusal messages carry U+2014, so every message assertion matches an
ASCII SUBSTRING and a copy edit cannot turn into a red suite.
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.core.models import AuditLog, Party
from apps.hrm.models import EmployeeProfile
from apps.projects.models import ResourceAllocation, ResourceProfile, ResourceTimeEntry
from apps.projects.tests.conftest import _resource_today

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Route tables and module-level helpers - every name ``_resource_*`` / ``_RESOURCE_*`` so a sibling
# lane appending nearby cannot rebind one and so a failure names its own lane.
# ==================================================================================================

#: The seven routes that take no pk.
_RESOURCE_PK_LESS_ROUTES = (
    "rsp_list", "rsp_create",
    "ral_list", "ral_create",
    "rte_list", "rte_create",
    "capacity_demand",
)

#: The seventeen routes that take one pk (three deletes + five ral verbs + three rte verbs and
#: their detail/edit pairs). 7 + 17 + 1 = the 25 routes the sub-module owns.
_RESOURCE_PK_ROUTES = (
    "rsp_detail", "rsp_edit", "rsp_delete",
    "ral_detail", "ral_edit", "ral_delete", "ral_assign", "ral_substitute",
    "ral_commit", "ral_complete", "ral_cancel",
    "rte_detail", "rte_edit", "rte_delete", "rte_submit", "rte_approve", "rte_reject",
)

#: The bulk week verb - the one route whose arguments are NOT a single pk.
_RESOURCE_WEEK_ROUTE = "rte_approve_week"

_RESOURCE_ALL_ROUTES = _RESOURCE_PK_LESS_ROUTES + _RESOURCE_PK_ROUTES + (_RESOURCE_WEEK_ROUTE,)

#: THE ROLE MATRIX. Five verbs answer a non-admin member with 403; the other four are
#: login-only. Pinned as a set because the failure that matters is a verb JOINING or LEAVING
#: the gate - that must be a visible decision, not a silent production change.
_RESOURCE_ADMIN_VERBS = (
    "ral_assign", "ral_substitute", "rte_approve", "rte_reject", "rte_approve_week",
)

#: ...and the four member-level ones: commit/complete/cancel move a booking a member owns the
#: day-to-day of, and submit hands the entry UP to the gated approvers.
_RESOURCE_MEMBER_VERBS = ("ral_commit", "ral_complete", "ral_cancel", "rte_submit")

_RESOURCE_ALL_VERBS = _RESOURCE_ADMIN_VERBS + _RESOURCE_MEMBER_VERBS

#: The tenant-A row each verb is exercised against - one row per verb, in a state the verb
#: ACCEPTS, so a "not 403" is never vacuous (a state refusal would be a 302, not a 403) and so
#: the admin landing tests below actually mutate something. The two approval verbs share the
#: one submitted entry; the week verb is handled separately below.
_RESOURCE_VERB_TARGETS = {
    "ral_assign": "resource_allocation_placeholder_requested",
    "ral_substitute": "resource_allocation_named_soft",
    "rte_approve": "resource_entry_submitted",
    "rte_reject": "resource_entry_submitted",
    "ral_commit": "resource_allocation_placeholder_requested",
    "ral_complete": "resource_allocation_named_firm",
    "ral_cancel": "resource_allocation_request_placeholder",
    "rte_submit": "resource_entry_draft",
}

#: Tenant B's row for each verb, keyed by the entity prefix the url name carries. The week verb
#: aims at ``resource_profile_b`` (the PERSON is the route argument).
_RESOURCE_FOREIGN_FIXTURES = {
    "rsp": "resource_profile_b",
    "ral": "resource_allocation_b",
    "rte": "resource_entry_b",
}

#: Cross-tenant GET probes: every rendering route that takes a pk, on all three models.
_RESOURCE_FOREIGN_GET_PROBES = (
    ("rsp_detail", "resource_profile_b"),
    ("rsp_edit", "resource_profile_b"),
    ("ral_detail", "resource_allocation_b"),
    ("ral_edit", "resource_allocation_b"),
    ("rte_detail", "resource_entry_b"),
    ("rte_edit", "resource_entry_b"),
)

#: Cross-tenant POST probes: the three deletes and all eight pk-addressed verbs (the week verb
#: gets its own test - its tenant-B probe aims at the PERSON). Every one of the three deletes is
#: in here, so a scoping slip would DESTROY another workspace's row rather than merely read it.
_RESOURCE_FOREIGN_POST_PROBES = (
    ("rsp_delete", "resource_profile_b"),
    ("ral_delete", "resource_allocation_b"),
    ("ral_assign", "resource_allocation_b"),
    ("ral_substitute", "resource_allocation_b"),
    ("ral_commit", "resource_allocation_b"),
    ("ral_complete", "resource_allocation_b"),
    ("ral_cancel", "resource_allocation_b"),
    ("rte_delete", "resource_entry_b"),
    ("rte_submit", "resource_entry_b"),
    ("rte_approve", "resource_entry_b"),
    ("rte_reject", "resource_entry_b"),
)


def _resource_url(name, *args):
    return reverse(f"projects:{name}", args=args)


def _resource_login_url():
    return reverse("accounts:login")


def _resource_route_args(name):
    """``(1, 2025, 37)`` for the week route, ``(1,)`` for the other pk routes, ``()`` for the
    pk-less ones. The login wall fires before any database work, so a dummy pk=1 is fine here."""
    if name == _RESOURCE_WEEK_ROUTE:
        return (1, 2025, 37)
    return () if name in _RESOURCE_PK_LESS_ROUTES else (1,)


def _resource_verb_target_fixtures(verb, foreign=False):
    """The fixture name(s) a verb acts on: the week verb resolves a PERSON plus the entry whose
    ISO week names the target week; every other verb resolves one row."""
    if verb == _RESOURCE_WEEK_ROUTE:
        if foreign:
            return "resource_profile_b", "resource_entry_b"
        return "resource_profile_internal", "resource_entry_submitted"
    if foreign:
        return _RESOURCE_FOREIGN_FIXTURES[verb.split("_")[0]], None
    return _RESOURCE_VERB_TARGETS[verb], None


def _resource_verb_rows(request, verb, foreign=False):
    """The rows a verb must leave byte-for-byte alone - for the week verb, the person AND the
    week's entry (the person is the audit target, the entry is what the verb would stamp)."""
    row_fixture, extra_fixture = _resource_verb_target_fixtures(verb, foreign)
    rows = [request.getfixturevalue(row_fixture)]
    if extra_fixture is not None:
        rows.append(request.getfixturevalue(extra_fixture))
    return rows


def _resource_verb_url(request, verb, foreign=False):
    """The URL one verb POSTs to, resolved against its own-tenant (or foreign) target."""
    row_fixture, extra_fixture = _resource_verb_target_fixtures(verb, foreign)
    target = request.getfixturevalue(row_fixture)
    if verb == _RESOURCE_WEEK_ROUTE:
        owner = request.getfixturevalue(extra_fixture)
        return _resource_url(verb, target.pk, owner.iso_year, owner.iso_week)
    return _resource_url(verb, target.pk)


def _resource_messages(response):
    """Every message queued on the request that produced ``response``, as plain strings.

    Read off the REQUEST rather than the rendered page: the verbs redirect, so nothing has
    rendered - and therefore consumed - the storage yet.
    """
    return [str(message) for message in get_messages(response.wsgi_request)]


def _resource_said(response, fragment):
    """True when any queued message contains ``fragment``. ASCII substrings only."""
    return any(fragment in message for message in _resource_messages(response))


def _resource_body(response):
    return response.content.decode()


def _resource_pks(response, key="object_list"):
    """The primary keys the page actually rendered, in order."""
    return [row.pk for row in response.context[key]]


def _resource_snapshot(obj):
    """Every stored column of one row, read back from the database.

    A refused POST has to leave the row byte-for-byte as it was, and a status-only comparison
    would miss a stamped ``approved_by``, a moved ``updated_at`` or a re-minted ``number``.
    Comparing the whole row is what makes "nothing changed" mean nothing at all. Returns
    ``None`` once the row is gone, which is itself a loud failure signal in an "unchanged"
    assertion.
    """
    return type(obj)._default_manager.filter(pk=obj.pk).values().first()


def _resource_deltas(before, after):
    if before is None or after is None:
        return {"__row__": (before, after)}
    return {name: (before[name], after[name])
            for name in before if before[name] != after[name]}


def _resource_unchanged(obj, before, label=""):
    deltas = _resource_deltas(before, _resource_snapshot(obj))
    assert deltas == {}, f"a refused request wrote to the row {label}: {deltas}"


def _resource_audits(obj, action=None):
    """The audit rows written against ``obj``, newest first."""
    qs = AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)), object_id=obj.pk)
    if action is not None:
        qs = qs.filter(action=action)
    return list(qs.order_by("-id"))


def _resource_rsp_payload(**overrides):
    """A valid ``ResourceProfileForm`` POST - its five required fields plus one identity."""
    payload = {
        "resource_type": "contractor",
        "default_role": "Crafted pool row",
        "weekly_capacity_hours": "40.00",
        "utilization_target_pct": "80",
        "status": "active",
        "skill_summary": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _resource_ral_create_payload(project, resource, **overrides):
    """A valid ``ResourceAllocationForm`` POST - the three required fields plus the attach."""
    payload = {
        "project": str(project.pk),
        "project_request": "",
        "project_task": "",
        "resource": str(resource.pk),
        "role_name": "Crafted booking",
        "skill_requirements": "",
        "allocation_unit": "hours_per_week",
        "hours_per_week": "16.00",
        "pct_capacity": "",
        "total_hours": "",
        "start_date": _resource_today().isoformat(),
        "end_date": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _resource_ral_edit_payload(target, **overrides):
    """A VALID ``ResourceAllocationForm`` edit body for ``target``, read off the row itself so
    the model clean's one-magnitude rule passes - ready to have a smuggled key added."""
    payload = {
        "project": str(target.project_id or ""),
        "project_request": str(target.project_request_id or ""),
        "project_task": str(target.project_task_id or ""),
        "resource": str(target.resource_id or ""),
        "role_name": target.role_name,
        "skill_requirements": target.skill_requirements,
        "allocation_unit": target.allocation_unit,
        "hours_per_week": str(target.hours_per_week) if target.hours_per_week is not None else "",
        "pct_capacity": str(target.pct_capacity) if target.pct_capacity is not None else "",
        "total_hours": str(target.total_hours) if target.total_hours is not None else "",
        "start_date": target.start_date.isoformat(),
        "end_date": target.end_date.isoformat() if target.end_date else "",
        "notes": target.notes,
    }
    payload.update(overrides)
    return payload


def _resource_rte_edit_payload(target, **overrides):
    """A VALID ``ResourceTimeEntryForm`` edit body for ``target``, ready for a smuggled key."""
    payload = {
        "resource": str(target.resource_id or ""),
        "project": str(target.project_id or ""),
        "project_task": str(target.project_task_id or ""),
        "entry_date": target.entry_date.isoformat(),
        "hours": str(target.hours),
        "task_description": target.task_description,
        "notes": target.notes,
    }
    payload.update(overrides)
    return payload


# ==================================================================================================
# 1. The login wall - anonymous reaches nothing and mutates nothing
# ==================================================================================================

@pytest.mark.parametrize("name", _RESOURCE_ALL_ROUTES)
def test_resource_anonymous_get_is_redirected_to_login_on_every_route(resource_anon_client, name):
    """All 25 routes, GET. ``login_required`` fires before any database work, so the pk need not
    exist - what is asserted is that no route in this sub-module is reachable logged out."""
    resp = resource_anon_client.get(_resource_url(name, *_resource_route_args(name)))
    assert resp.status_code == 302, name
    assert resp["Location"].startswith(_resource_login_url()), name


@pytest.mark.parametrize("name", _RESOURCE_ALL_ROUTES)
def test_resource_anonymous_post_is_redirected_to_login_on_every_route(resource_anon_client, name):
    """All 25 routes, POST. A verb must not answer 405 (which would prove it exists and is
    POST-only) or 403 ahead of the login wall: the decorators stack
    ``login_required((tenant_admin_required)(require_POST(view)))``, so the redirect comes
    first, every time and on every route."""
    resp = resource_anon_client.post(_resource_url(name, *_resource_route_args(name)), {})
    assert resp.status_code == 302, name
    assert resp["Location"].startswith(_resource_login_url()), name


def test_resource_an_anonymous_post_never_reaches_a_real_row(resource_anon_client, request):
    """The same nine POSTs against REAL tenant-A rows: redirected, and the rows are untouched.

    The route-table test above proves the redirect; this one proves the redirect happens BEFORE
    the write, which is the property that actually matters.
    """
    for verb in _RESOURCE_ALL_VERBS:
        rows = _resource_verb_rows(request, verb)
        befores = [_resource_snapshot(row) for row in rows]

        resp = resource_anon_client.post(_resource_verb_url(request, verb), {})

        assert resp.status_code == 302, verb
        assert resp["Location"].startswith(_resource_login_url()), verb
        for row, before in zip(rows, befores):
            _resource_unchanged(row, before, verb)


@pytest.mark.parametrize("route,fixture", (
    ("rsp_detail", "resource_profile_internal"),
    ("ral_detail", "resource_allocation_named_soft"),
    ("rte_detail", "resource_entry_submitted"),
))
def test_resource_an_anonymous_get_carries_no_row_data(resource_anon_client, request, route,
                                                       fixture):
    """A redirect body is empty: the row's number and every other column must not ride out on
    the 302. Asserted rather than assumed, because a view that rendered first and redirected
    afterwards would still be a 302."""
    obj = request.getfixturevalue(fixture)

    resp = resource_anon_client.get(_resource_url(route, obj.pk))

    assert resp.status_code == 302, route
    assert resp.content == b"", route
    assert obj.number.encode() not in resp.content, route


def test_resource_an_anonymous_create_post_saves_nothing(resource_anon_client, resource_project):
    """The create routes are where an unauthenticated POST would plant a row rather than read
    one. Nothing is minted, in any workspace."""
    before = {model: model.objects.count()
              for model in (ResourceProfile, ResourceAllocation, ResourceTimeEntry)}

    for route in ("rsp_create", "ral_create", "rte_create"):
        resp = resource_anon_client.post(_resource_url(route), {})
        assert resp.status_code == 302, route
        assert resp["Location"].startswith(_resource_login_url()), route

    assert {model: model.objects.count()
            for model in (ResourceProfile, ResourceAllocation, ResourceTimeEntry)} == before


# ==================================================================================================
# 2. The role gate - five admin-only verbs, four login-only, asserted as a matrix
# ==================================================================================================

def test_resource_the_admin_gate_is_exactly_these_five_verbs(member_client, request):
    """THE matrix. A tenant-A member POSTs all nine verbs at rows their gates ACCEPT; the set
    that answers 403 must be exactly the five ``@tenant_admin_required`` ones, and each refusal
    leaves ZERO field deltas.

    Pinned as a set rather than one test per verb because the failure that matters is a verb
    JOINING or LEAVING the gate: a peer session that gates a member verb (or ungates a staffing
    verb) fails HERE, as a visible decision, instead of silently in production. The member-level
    verbs are then asserted to RUN for the same actor - the other half of the split.
    """
    refused = set()
    rows_by_verb = {}
    for verb in _RESOURCE_ADMIN_VERBS:
        rows = _resource_verb_rows(request, verb)
        rows_by_verb[verb] = [(row, _resource_snapshot(row)) for row in rows]

    for verb in _RESOURCE_ADMIN_VERBS:
        resp = member_client.post(_resource_verb_url(request, verb), {})
        assert resp.status_code == 403, f"{verb} answered {resp.status_code}"
        refused.add(verb)
        for row, before in rows_by_verb[verb]:
            _resource_unchanged(row, before, verb)

    assert refused == set(_RESOURCE_ADMIN_VERBS)

    for verb in _RESOURCE_MEMBER_VERBS:
        resp = member_client.post(_resource_verb_url(request, verb), {})
        assert resp.status_code == 302, f"{verb} answered {resp.status_code}"


@pytest.mark.parametrize("verb,fixture,landed", (
    ("ral_commit", "resource_allocation_placeholder_requested", "soft"),
    ("ral_complete", "resource_allocation_named_firm", "completed"),
    ("ral_cancel", "resource_allocation_request_placeholder", "cancelled"),
    ("rte_submit", "resource_entry_draft", "submitted"),
))
def test_resource_a_member_runs_the_member_level_verbs(member_client, request, verb, fixture,
                                                       landed):
    """The other half of the split, asserted as-built: an ordinary member commits, completes and
    cancels bookings and submits time entries. This is house style, not an oversight, so it is
    pinned - a future decision to gate one of these will change this test and be visible in the
    diff rather than silently tightening production."""
    target = request.getfixturevalue(fixture)

    resp = member_client.post(_resource_url(verb, target.pk), {})

    assert resp.status_code == 302, verb
    target.refresh_from_db()
    if verb == "rte_submit":
        assert target.status == landed, verb
        assert target.submitted_at is not None, verb
    else:
        assert target.booking_status == landed, verb


def test_resource_an_admin_assign_names_a_placeholder(client_a,
                                                      resource_allocation_placeholder_requested,
                                                      resource_profile_minimal):
    """The control for the ``ral_assign`` 403s: same verb, same row state, admin actor - and the
    placeholder comes back named and soft-booked, with the ``assign`` audit row."""
    target = resource_allocation_placeholder_requested

    resp = client_a.post(_resource_url("ral_assign", target.pk),
                         {"resource": str(resource_profile_minimal.pk)})

    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.resource_id == resource_profile_minimal.pk
    assert target.booking_status == "soft"
    assert _resource_audits(target, action="assign")


def test_resource_an_admin_substitute_releases_and_books_a_successor(
        client_a, resource_allocation_named_soft, resource_profile_minimal):
    """The control for the ``ral_substitute`` 403s: the original is released, the successor is
    booked on the replacement with the copied window and provenance, the redirect lands on the
    SUCCESSOR's detail, and exactly ONE ``substitute`` audit row is written on the released row."""
    original = resource_allocation_named_soft
    window = (original.start_date, original.end_date)

    resp = client_a.post(_resource_url("ral_substitute", original.pk),
                         {"resource": str(resource_profile_minimal.pk)})

    assert resp.status_code == 302
    original.refresh_from_db()
    assert original.booking_status == "released"
    successor = ResourceAllocation.objects.get(substitute_of=original)
    assert successor.resource_id == resource_profile_minimal.pk
    assert successor.booking_status == "soft"
    assert successor.role_name == original.role_name
    assert (successor.start_date, successor.end_date) == window
    assert successor.requested_by_id == original.requested_by_id
    assert resp["Location"] == _resource_url("ral_detail", successor.pk)
    audits = _resource_audits(original, action="substitute")
    assert len(audits) == 1
    assert audits[0].changes["successor"] == successor.number


def test_resource_an_admin_approve_and_reject_stamp_the_decision(
        client_a, resource_admin, resource_entry_submitted, resource_entry_draft):
    """The controls for the ``rte_approve`` / ``rte_reject`` 403s: the submitted entry comes back
    approved with the admin's stamps; a second entry is queued through the member verb and then
    rejected with the reason carried into ``decision_note`` AND the audit trail."""
    resp = client_a.post(_resource_url("rte_approve", resource_entry_submitted.pk), {})
    assert resp.status_code == 302
    resource_entry_submitted.refresh_from_db()
    assert resource_entry_submitted.status == "approved"
    assert resource_entry_submitted.approved_by_id == resource_admin.pk
    assert resource_entry_submitted.approved_at is not None

    assert client_a.post(
        _resource_url("rte_submit", resource_entry_draft.pk), {}).status_code == 302
    resp = client_a.post(_resource_url("rte_reject", resource_entry_draft.pk),
                         {"reason": "Duplicate of an approved day."})
    assert resp.status_code == 302
    resource_entry_draft.refresh_from_db()
    assert resource_entry_draft.status == "rejected"
    assert resource_entry_draft.decision_note == "Duplicate of an approved day."
    audits = _resource_audits(resource_entry_draft, action="reject")
    assert len(audits) == 1
    assert audits[0].changes["reason"] == "Duplicate of an approved day."


def test_resource_an_admin_approve_week_bulk_approves_and_audits_once(client_a, request,
                                                                      resource_admin):
    """The control for the ``rte_approve_week`` 403s: the person-week comes back approved with
    the admin's stamps, and the batch writes exactly ONE audit row - on the RESOURCE, with the
    week and the count in ``changes``."""
    person = request.getfixturevalue("resource_profile_internal")
    entry = request.getfixturevalue("resource_entry_submitted")
    year, week = entry.iso_year, entry.iso_week

    resp = client_a.post(_resource_url("rte_approve_week", person.pk, year, week), {})

    assert resp.status_code == 302
    assert resp["Location"] == _resource_url("rte_list")
    entry.refresh_from_db()
    assert entry.status == "approved"
    assert entry.approved_by_id == resource_admin.pk
    assert entry.approved_at is not None
    audits = _resource_audits(person, action="approve")
    assert len(audits) == 1
    assert audits[0].changes == {"verb": "approve_week", "week": f"{year}-W{week:02d}",
                                 "count": 1}


def test_resource_an_admin_get_on_any_verb_is_405(client_a, request):
    """For an admin the role gate passes, so ``@require_POST`` is the outermost thing left: a
    GET on any of the nine POST-only routes is 405 - a link, a prefetch or a crawler cannot
    mutate anything."""
    for verb in _RESOURCE_ALL_VERBS:
        resp = client_a.get(_resource_verb_url(request, verb))
        assert resp.status_code == 405, verb


def test_resource_a_member_get_on_a_gated_verb_is_403_role_beats_method(member_client, request):
    """The subtle half of the GET matrix: ``tenant_admin_required`` sits BETWEEN
    ``login_required`` and ``require_POST``, so for a member the ROLE check is reached before
    the method check - 403, not 405. A 405 here would mean the member cleared the gate and was
    stopped only by the HTTP method, a much weaker claim."""
    for verb in _RESOURCE_ADMIN_VERBS:
        rows = _resource_verb_rows(request, verb)
        befores = [_resource_snapshot(row) for row in rows]

        resp = member_client.get(_resource_verb_url(request, verb))

        assert resp.status_code == 403, verb
        for row, before in zip(rows, befores):
            _resource_unchanged(row, before, verb)


def test_resource_a_member_get_on_a_member_verb_is_405(member_client, request):
    """...and on the four login-only verbs there is no role decorator, so the method check is
    the outermost thing left and a GET is 405. Nothing is written."""
    for verb in _RESOURCE_MEMBER_VERBS:
        rows = _resource_verb_rows(request, verb)
        befores = [_resource_snapshot(row) for row in rows]

        resp = member_client.get(_resource_verb_url(request, verb))

        assert resp.status_code == 405, verb
        for row, before in zip(rows, befores):
            _resource_unchanged(row, before, verb)


# ==================================================================================================
# 3. Cross-tenant IDOR - 404 on every pk route, with the row untouched and no audit row
# ==================================================================================================

@pytest.mark.parametrize("route,fixture", _RESOURCE_FOREIGN_GET_PROBES)
def test_resource_cross_tenant_get_is_404_and_discloses_nothing(client_a, request, route, fixture):
    """Tenant A's ADMIN GETs tenant B's detail and edit pages. 404 each - never 403 (which would
    confirm the row exists) and never 500. The admin actor is deliberate: on a gated route the
    role check runs first, so only an admin actually reaches the tenant scope check that a
    broken scoping would defeat. The 404 body must not carry the row it refused to serve."""
    obj = request.getfixturevalue(fixture)

    resp = client_a.get(_resource_url(route, obj.pk))
    body = _resource_body(resp)

    assert resp.status_code == 404, route
    assert obj.number not in body, route
    assert str(obj) not in body, route


@pytest.mark.parametrize("verb,fixture", _RESOURCE_FOREIGN_POST_PROBES)
def test_resource_cross_tenant_post_is_404_and_changes_nothing(client_a, request, verb, fixture):
    """All eleven pk-addressed writes, aimed by tenant A's admin at tenant B's row: 404, B's row
    is byte-for-byte what it was, still exists, and NO audit row was written for the foreign
    attempt - a scoping slip that merely logged would still be an oracle."""
    target = request.getfixturevalue(fixture)
    before = _resource_snapshot(target)

    resp = client_a.post(_resource_url(verb, target.pk), {})

    assert resp.status_code == 404, verb
    assert type(target)._default_manager.filter(pk=target.pk).exists(), verb
    _resource_unchanged(target, before, verb)
    assert _resource_audits(target) == [], verb


def test_resource_approve_week_on_a_foreign_resource_is_404(client_a, resource_profile_b,
                                                            resource_entry_b):
    """The week verb's route argument is a RESOURCE pk, and the person resolves FIRST
    (``get_object_or_404`` before any week check) - so a foreign person 404s regardless of the
    year/week pair, B's person and entry are untouched, and no audit row lands on B's resource."""
    before = _resource_snapshot(resource_profile_b)

    resp = client_a.post(_resource_url("rte_approve_week", resource_profile_b.pk,
                                       resource_entry_b.iso_year, resource_entry_b.iso_week), {})

    assert resp.status_code == 404
    _resource_unchanged(resource_profile_b, before, "rte_approve_week")
    assert _resource_audits(resource_profile_b) == []


def test_resource_a_member_on_a_foreign_pk_of_a_gated_verb_is_403(request, member_client):
    """The other side of the actor split, pinned so a future reader does not "fix" the 404 test
    into a member one and quietly weaken it: the role check raises ``PermissionDenied`` BEFORE
    ``get_object_or_404`` runs, so a tenant-A member aimed at a tenant-B row is refused on ROLE
    and never reaches the scope check. Either refusal is correct - what must not happen is a
    200, or a write."""
    for verb in _RESOURCE_ADMIN_VERBS:
        rows = _resource_verb_rows(request, verb, foreign=True)
        befores = [_resource_snapshot(row) for row in rows]

        resp = member_client.post(_resource_verb_url(request, verb, foreign=True), {})

        assert resp.status_code == 403, verb
        for row, before in zip(rows, befores):
            _resource_unchanged(row, before, verb)


def test_resource_a_member_on_a_foreign_pk_of_a_member_verb_is_404(request, member_client):
    """...and on the four login-only verbs there is no role gate to fire first, so the same
    member falls through to the tenant scope check and gets the 404. Nothing is deleted."""
    for verb in _RESOURCE_MEMBER_VERBS:
        rows = _resource_verb_rows(request, verb, foreign=True)
        befores = [_resource_snapshot(row) for row in rows]

        resp = member_client.post(_resource_verb_url(request, verb, foreign=True), {})

        assert resp.status_code == 404, verb
        for row, before in zip(rows, befores):
            _resource_unchanged(row, before, verb)


def test_resource_isolation_is_symmetric(client_b, resource_profile_internal,
                                         resource_allocation_named_soft,
                                         resource_entry_submitted, resource_entry_b):
    """Isolation is symmetric or it is not isolation. Tenant B's admin is 404 on tenant A's
    detail pages and on a member-level verb aimed at A's row, and B's own register shows B's
    rows only."""
    for route, obj in (("rsp_detail", resource_profile_internal),
                       ("ral_detail", resource_allocation_named_soft),
                       ("rte_detail", resource_entry_submitted)):
        assert client_b.get(_resource_url(route, obj.pk)).status_code == 404, route

    assert client_b.post(
        _resource_url("ral_commit", resource_allocation_named_soft.pk), {}).status_code == 404

    resp = client_b.get(_resource_url("rte_list"))
    assert resp.status_code == 200
    pks = _resource_pks(resp)
    assert resource_entry_b.pk in pks
    assert resource_entry_submitted.pk not in pks


# ==================================================================================================
# 4. Tenant scoping - registers, filters, and the computed capacity board
# ==================================================================================================

def test_resource_registers_never_list_another_workspaces_rows(
        client_a, resource_profile_internal, resource_allocation_named_soft,
        resource_entry_submitted, resource_profile_b, resource_allocation_b, resource_entry_b):
    """Each register shows the workspace's OWN rows and never tenant B's - asserted against a
    NON-empty register, so a scoping slip that emptied the page cannot read as a pass. Search is
    an oracle too: ``?q=`` runs after the tenant filter, so B's role text answers nothing."""
    for route, own, foreign in (
            ("rsp_list", resource_profile_internal, resource_profile_b),
            ("ral_list", resource_allocation_named_soft, resource_allocation_b),
            ("rte_list", resource_entry_submitted, resource_entry_b)):
        resp = client_a.get(_resource_url(route))
        assert resp.status_code == 200, route
        pks = _resource_pks(resp)
        assert own.pk in pks, route
        assert foreign.pk not in pks, route
        assert "Globex booking" not in _resource_body(resp), route

    resp = client_a.get(_resource_url("ral_list"), {"q": "Globex booking"})
    assert resp.status_code == 200
    assert _resource_pks(resp) == []


def test_resource_a_foreign_pk_filter_yields_an_empty_register(
        client_a, resource_profile_internal, resource_allocation_named_soft,
        resource_entry_submitted, resource_org_unit_b, resource_project_b, resource_profile_b):
    """A real, in-range, valid pk that belongs to ANOTHER workspace is a narrowing request the
    register must honour - and honouring it yields nothing, because the tenant filter is applied
    first. It must not be treated as junk and SKIPPED (that returns the whole register and turns
    the parameter into an existence oracle), and it must not 500."""
    cases = (
        ("rsp_list", "org_unit", resource_org_unit_b, resource_profile_internal),
        ("ral_list", "project", resource_project_b, resource_allocation_named_soft),
        ("ral_list", "resource", resource_profile_b, resource_allocation_named_soft),
        ("rte_list", "resource", resource_profile_b, resource_entry_submitted),
        ("rte_list", "project", resource_project_b, resource_entry_submitted),
    )
    for route, param, foreign, own in cases:
        unfiltered = client_a.get(_resource_url(route))
        assert own.pk in _resource_pks(unfiltered), (route, param)

        resp = client_a.get(_resource_url(route), {param: str(foreign.pk)})

        assert resp.status_code == 200, (route, param)
        assert _resource_pks(resp) == [], (route, param)


def test_resource_the_capacity_board_never_renders_another_workspaces_rows(
        client_a, resource_profile_internal, resource_allocation_named_soft,
        resource_allocation_placeholder_requested, resource_profile_b, resource_allocation_b):
    """The computed board scopes BOTH sections: A's active pool is the capacity table, A's
    requested/soft bookings are the demand rows (the project-linked placeholder is the one gap),
    and no tenant-B supply or demand row renders no matter how well its window overlaps."""
    resp = client_a.get(_resource_url("capacity_demand"))

    assert resp.status_code == 200
    capacity_pks = [row.pk for row in resp.context["capacity_rows"]]
    demand_pks = [row.pk for row in resp.context["demand_rows"]]
    assert resource_profile_internal.pk in capacity_pks
    assert resource_profile_b.pk not in capacity_pks
    assert resource_allocation_named_soft.pk in demand_pks
    assert resource_allocation_placeholder_requested.pk in demand_pks
    assert resource_allocation_b.pk not in demand_pks
    assert resp.context["gap_count"] == 1


# ==================================================================================================
# 5. Cross-tenant FK smuggling at the ROUTE - every scoped FK, each with a same-tenant control
# ==================================================================================================
#
# The forms lane proves the FIELD rejects a foreign pk. These prove the same thing where an
# attacker actually stands: a valid own-tenant create/edit POST with a foreign FK in it. The
# assertion is that the FIELD HAS AN ERROR and nothing landed - never the wording, because
# ``TenantModelForm`` narrows the queryset first and Django's own "Select a valid choice"
# message pre-empts ``_reject_foreign``'s "belongs to another workspace" on every reachable path.


def test_resource_a_crafted_profile_create_rejects_foreign_people(client_a, tenant_a, tenant_b,
                                                                  resource_party_a,
                                                                  resource_party_b):
    """``employee`` and ``party`` are the two identities a pool row can carry; neither may point
    at another workspace's person. Each smuggle is refused as a field error, and each
    same-tenant control DOES create - so the refusals are the tenant scoping, not the payload."""
    foreign_party = Party.objects.create(tenant=tenant_b, kind="person", name="Globex Staff")
    foreign_employee = EmployeeProfile(tenant=tenant_b, party=foreign_party)
    foreign_employee.save()
    local_party = Party.objects.create(tenant=tenant_a, kind="person", name="Local Control Staff")
    local_employee = EmployeeProfile(tenant=tenant_a, party=local_party)
    local_employee.save()
    before = ResourceProfile.objects.count()

    resp = client_a.post(_resource_url("rsp_create"),
                         _resource_rsp_payload(employee=str(foreign_employee.pk)))
    assert resp.status_code == 200
    assert "employee" in resp.context["form"].errors

    resp = client_a.post(_resource_url("rsp_create"),
                         _resource_rsp_payload(party=str(resource_party_b.pk)))
    assert resp.status_code == 200
    assert "party" in resp.context["form"].errors
    assert ResourceProfile.objects.count() == before

    resp = client_a.post(_resource_url("rsp_create"),
                         _resource_rsp_payload(party=str(resource_party_a.pk),
                                               default_role="Local control party row"))
    assert resp.status_code == 302
    created = ResourceProfile.objects.get(default_role="Local control party row")
    assert created.tenant_id == tenant_a.pk
    assert created.party_id == resource_party_a.pk

    resp = client_a.post(_resource_url("rsp_create"),
                         _resource_rsp_payload(employee=str(local_employee.pk),
                                               default_role="Local control staff row"))
    assert resp.status_code == 302
    created = ResourceProfile.objects.get(default_role="Local control staff row")
    assert created.tenant_id == tenant_a.pk
    assert created.employee_id == local_employee.pk


def test_resource_a_crafted_profile_create_rejects_a_foreign_org_unit(
        client_a, tenant_a, resource_party_a, resource_org_unit_a, resource_org_unit_b):
    """The org-unit FK is the pool register's team lens; a row filed under another workspace's
    team would appear on (and be lens-filtered by) their register."""
    before = ResourceProfile.objects.count()

    resp = client_a.post(
        _resource_url("rsp_create"),
        _resource_rsp_payload(party=str(resource_party_a.pk),
                              org_unit=str(resource_org_unit_b.pk)))

    assert resp.status_code == 200
    assert "org_unit" in resp.context["form"].errors
    assert ResourceProfile.objects.count() == before

    resp = client_a.post(
        _resource_url("rsp_create"),
        _resource_rsp_payload(party=str(resource_party_a.pk),
                              default_role="Local control org row",
                              org_unit=str(resource_org_unit_a.pk)))

    assert resp.status_code == 302
    created = ResourceProfile.objects.get(default_role="Local control org row")
    assert created.tenant_id == tenant_a.pk
    assert created.org_unit_id == resource_org_unit_a.pk


def test_resource_a_crafted_allocation_create_rejects_foreign_project_and_resource(
        client_a, tenant_a, resource_project, resource_profile_minimal, resource_project_b,
        resource_profile_b):
    """``project`` is the sharp one - a booking hung off another workspace's project would put
    tenant A's demand on tenant B's plan - and ``resource`` would spend B's capacity."""
    before = ResourceAllocation.objects.count()

    resp = client_a.post(_resource_url("ral_create"),
                         _resource_ral_create_payload(resource_project_b, resource_profile_b))

    assert resp.status_code == 200
    assert "project" in resp.context["form"].errors
    assert "resource" in resp.context["form"].errors
    assert ResourceAllocation.objects.count() == before

    resp = client_a.post(_resource_url("ral_create"),
                         _resource_ral_create_payload(resource_project,
                                                      resource_profile_minimal,
                                                      role_name="Local control booking"))
    assert resp.status_code == 302
    created = ResourceAllocation.objects.get(role_name="Local control booking")
    assert created.tenant_id == tenant_a.pk
    assert created.project_id == resource_project.pk
    assert created.resource_id == resource_profile_minimal.pk


def test_resource_a_crafted_entry_create_rejects_a_foreign_resource(
        client_a, tenant_a, resource_profile_internal, resource_project, resource_project_b,
        resource_profile_b):
    """``resource`` is required and CASCADEs - an entry logged against another workspace's
    person would write actuals onto their record (and ``project`` onto their plan)."""
    payload = {
        "resource": str(resource_profile_b.pk),
        "project": str(resource_project_b.pk),
        "project_task": "",
        "entry_date": _resource_today().isoformat(),
        "hours": "6.00",
        "task_description": "Smuggled timesheet row",
        "notes": "",
    }
    before = ResourceTimeEntry.objects.count()

    resp = client_a.post(_resource_url("rte_create"), payload)

    assert resp.status_code == 200
    assert "resource" in resp.context["form"].errors
    assert "project" in resp.context["form"].errors
    assert ResourceTimeEntry.objects.count() == before

    resp = client_a.post(_resource_url("rte_create"), dict(
        payload, resource=str(resource_profile_internal.pk), project=str(resource_project.pk),
        task_description="Local control timesheet row"))

    assert resp.status_code == 302
    created = ResourceTimeEntry.objects.get(task_description="Local control timesheet row")
    assert created.tenant_id == tenant_a.pk
    assert created.resource_id == resource_profile_internal.pk
    assert created.project_id == resource_project.pk


def test_resource_an_allocation_edit_cannot_move_onto_another_workspaces_project(
        client_a, resource_allocation_named_soft, resource_project_b):
    """The same smuggle on the EDIT route, where the row already exists and only the pointer
    would move - a quieter and more useful attack than creating one."""
    target = resource_allocation_named_soft
    before = _resource_snapshot(target)

    resp = client_a.post(_resource_url("ral_edit", target.pk),
                         _resource_ral_edit_payload(target, project=str(resource_project_b.pk)))

    assert resp.status_code == 200
    assert "project" in resp.context["form"].errors
    _resource_unchanged(target, before, "ral_edit")


# ==================================================================================================
# 6. Verb-state tampering at the route - the L20/L22 shape
# ==================================================================================================
#
# The forms lane pins the field LISTS (``booking_status`` / ``substitute_of`` / ``requested_by``
# / the RTE stamps are not form fields). These assert the same claim where it is defended in
# production: a POST that smuggles the key must still be processed for the fields the form DOES
# own, and the verb-driven columns must survive byte-for-byte.

def test_resource_an_allocation_edit_cannot_smuggle_verb_state(
        client_a, tenant_a, resource_admin, resource_allocation_named_soft,
        resource_allocation_b, tenant_b, admin_b):
    """``booking_status='firm'`` + a foreign ``substitute_of`` + a foreign ``requested_by`` +
    a foreign ``tenant`` + a re-minted ``number`` in one edit POST: the edit's OWN field lands
    (the role is renamed, proving the POST went through) and every smuggled column is ignored."""
    target = resource_allocation_named_soft
    original_number, original_pk = target.number, target.pk

    resp = client_a.post(_resource_url("ral_edit", target.pk), _resource_ral_edit_payload(
        target, role_name="Renamed by the edit", booking_status="firm",
        substitute_of=str(resource_allocation_b.pk), requested_by=str(admin_b.pk),
        tenant=str(tenant_b.pk), number="RAL-99999"))

    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.role_name == "Renamed by the edit"
    assert target.booking_status == "soft"
    assert target.substitute_of_id is None
    assert target.requested_by_id == resource_admin.pk
    assert target.tenant_id == tenant_a.pk
    assert target.number == original_number
    assert target.pk == original_pk


def test_resource_an_entry_edit_cannot_touch_the_approval_stamps(
        member_client, resource_entry_draft, tenant_b, admin_b):
    """``rte_edit`` is login-only, so a MEMBER reaches it - and a smuggled
    ``status='approved'`` with a full forged stamp set must change nothing: the form cannot
    touch the stamps at all, which is why the approval verbs are the only writers."""
    target = resource_entry_draft

    resp = member_client.post(_resource_url("rte_edit", target.pk), _resource_rte_edit_payload(
        target, task_description="Edited by a member", status="approved",
        submitted_at="2020-01-01T00:00", approved_at="2020-01-01T00:00",
        approved_by=str(admin_b.pk), decision_note="forged", tenant=str(tenant_b.pk)))

    assert resp.status_code == 302
    target.refresh_from_db()
    assert target.task_description == "Edited by a member"
    assert target.status == "draft"
    assert target.submitted_at is None
    assert target.approved_at is None
    assert target.approved_by_id is None
    assert target.decision_note == ""


def test_resource_a_create_post_cannot_smuggle_verb_state_or_provenance(
        client_a, tenant_a, tenant_b, resource_admin, resource_project, resource_profile_minimal,
        resource_party_a, resource_allocation_b, admin_b):
    """A create POST cannot mint verb state either: the allocation comes back ``requested`` with
    ``requested_by`` stamped by the VIEW (the actor), a minted (not POSTed) number, no
    ``substitute_of``, and tenant A - and the same holds for the pool row's ``tenant``/``number``."""
    resp = client_a.post(_resource_url("ral_create"), _resource_ral_create_payload(
        resource_project, resource_profile_minimal, booking_status="firm",
        requested_by=str(admin_b.pk), tenant=str(tenant_b.pk), number="RAL-99999",
        substitute_of=str(resource_allocation_b.pk), id="4242"))

    assert resp.status_code == 302
    created = ResourceAllocation.objects.get(role_name="Crafted booking")
    assert created.tenant_id == tenant_a.pk
    assert created.booking_status == "requested"
    assert created.requested_by_id == resource_admin.pk
    assert created.number.startswith("RAL-") and created.number != "RAL-99999"
    assert created.substitute_of_id is None
    assert created.pk != 4242

    resp = client_a.post(_resource_url("rsp_create"), _resource_rsp_payload(
        party=str(resource_party_a.pk), default_role="Crafted pool row",
        tenant=str(tenant_b.pk), number="RSP-99999"))

    assert resp.status_code == 302
    created = ResourceProfile.objects.get(default_role="Crafted pool row")
    assert created.tenant_id == tenant_a.pk
    assert created.number.startswith("RSP-") and created.number != "RSP-99999"


# ==================================================================================================
# 7. CSRF (L44)
# ==================================================================================================

def test_resource_a_post_without_a_csrf_token_is_refused(resource_csrf_client, request):
    """An admin-gated verb and a member verb, each with a valid ADMIN session and no token:
    403, row untouched. This is a genuinely different refusal from the role gate - the actor
    here would otherwise be allowed - so the gated verb is covered twice on purpose, once for
    who and once for how. The same client still READS, which makes the 403 a token failure and
    not a login failure."""
    for verb in ("ral_assign", "rte_submit"):
        rows = _resource_verb_rows(request, verb)
        befores = [_resource_snapshot(row) for row in rows]

        resp = resource_csrf_client.post(_resource_verb_url(request, verb), {})

        assert resp.status_code == 403, verb
        for row, before in zip(rows, befores):
            _resource_unchanged(row, before, verb)

    assert resource_csrf_client.get(_resource_url("rsp_list")).status_code == 200


def test_resource_a_csrf_post_that_carries_the_token_succeeds(resource_csrf_client,
                                                              resource_entry_draft):
    """...and the completing half: with the token taken off the rendered detail page, the same
    POST works. Without this, a view that answered 403 for some unrelated reason would look
    secure."""
    page = resource_csrf_client.get(_resource_url("rte_detail", resource_entry_draft.pk))
    token = str(page.context["csrf_token"])

    resp = resource_csrf_client.post(_resource_url("rte_submit", resource_entry_draft.pk),
                                     {"csrfmiddlewaretoken": token})

    assert resp.status_code == 302
    resource_entry_draft.refresh_from_db()
    assert resource_entry_draft.status == "submitted"


# ==================================================================================================
# 8. rte_approve_week hardening - junk weeks answer politely, never a 500
# ==================================================================================================
#
# Junk ``year``/``week`` VALUES cannot even reach this view: the route declares
# ``<int:resource>/<int:year>/w<int:week>``, so a non-numeric year fails URL resolution (404)
# before any code runs. What CAN arrive is an int outside the valid ranges - pinned below.

def test_resource_approve_week_refuses_an_impossible_or_fake_week_politely(
        client_a, resource_profile_internal, resource_entry_submitted):
    """week 0 / 99 / 999 fail the 1..53 range check, and week 53 of a 52-week year (2025) is
    not a real ISO week - each answers the polite message + redirect to the register, never a
    500, and the queued entry is untouched."""
    cases = (
        (2025, 0, "Week must be between 1 and 53."),
        (2025, 99, "Week must be between 1 and 53."),
        (2025, 999, "Week must be between 1 and 53."),
        (2025, 53, "is not a real ISO week."),
    )
    for year, week, fragment in cases:
        resp = client_a.post(
            _resource_url("rte_approve_week", resource_profile_internal.pk, year, week), {})

        assert resp.status_code == 302, (year, week)
        assert resp["Location"] == _resource_url("rte_list"), (year, week)
        assert _resource_said(resp, fragment), (year, week)

    resource_entry_submitted.refresh_from_db()
    assert resource_entry_submitted.status == "submitted"
    assert resource_entry_submitted.approved_at is None


def test_resource_approve_week_reports_an_empty_queue_without_writing(
        client_a, resource_profile_contractor, resource_entry_submitted):
    """A real person-week with zero submitted rows is an INFO, not an error and not a write -
    the honest 'nothing to approve' that must never fall through to approving something else."""
    year, week = resource_entry_submitted.iso_year, resource_entry_submitted.iso_week

    resp = client_a.post(
        _resource_url("rte_approve_week", resource_profile_contractor.pk, year, week), {})

    assert resp.status_code == 302
    assert _resource_said(resp, "No submitted entries")
    resource_entry_submitted.refresh_from_db()
    assert resource_entry_submitted.status == "submitted"
    assert _resource_audits(resource_profile_contractor) == []


# ==================================================================================================
# 9. Disclosure - refusals are owned by the row's own workspace
# ==================================================================================================

def test_resource_a_state_refusal_is_owned_by_the_rows_workspace(
        client_a, resource_allocation_named_firm, resource_allocation_b):
    """A state refusal SPEAKS on the workspace's own row (the admin is told why nothing was
    staffed) but says NOTHING about a foreign pk: the 404 queues no message at all, so error
    text can never confirm, characterize or deny another workspace's row. The foreign attempt
    runs FIRST because Django's message storage carries unread messages into the next response -
    an empty read after the 404 is only meaningful on a fresh session."""
    resp = client_a.post(_resource_url("ral_assign", resource_allocation_b.pk), {})
    assert resp.status_code == 404
    assert _resource_messages(resp) == []

    resp = client_a.post(_resource_url("ral_assign", resource_allocation_named_firm.pk), {})
    assert resp.status_code == 302
    assert _resource_said(resp, "already names a resource")


# ==================================================================================================
# 10. The tenant=None user - reads nothing, writes nothing
# ==================================================================================================

def test_resource_a_tenantless_session_reads_nothing(
        resource_tenantless_client, resource_profile_internal, resource_allocation_named_soft,
        resource_entry_submitted, resource_profile_b, resource_allocation_b, resource_entry_b):
    """The superuser shape (``tenant=None``) gets 200 on every register with an EMPTY
    ``object_list`` and an empty board - ``filter(tenant is None)`` matches nothing, and the
    failure being guarded against is a view that special-cased the missing tenant into "show
    everything". A pk route is 404 on every row in every workspace, not just the ones it
    happens not to own."""
    for route in ("rsp_list", "ral_list", "rte_list"):
        resp = resource_tenantless_client.get(_resource_url(route))
        assert resp.status_code == 200, route
        assert _resource_pks(resp) == [], route

    resp = resource_tenantless_client.get(_resource_url("capacity_demand"))
    assert resp.status_code == 200
    assert resp.context["capacity_rows"] == []
    assert resp.context["demand_rows"] == []

    for route, obj in (("rsp_detail", resource_profile_internal),
                       ("ral_detail", resource_allocation_named_soft),
                       ("rte_detail", resource_entry_submitted)):
        assert resource_tenantless_client.get(
            _resource_url(route, obj.pk)).status_code == 404, route


def test_resource_the_create_views_turn_a_tenantless_session_away(resource_tenantless_client):
    """The three create views guard ``request.tenant is None`` on their FIRST line - before any
    form is bound, because an unscoped ``TenantModelForm`` would render every workspace's FK
    dropdowns. Each answers 302 to ``dashboard:home`` and nothing is minted."""
    before = {model: model.objects.count()
              for model in (ResourceProfile, ResourceAllocation, ResourceTimeEntry)}

    for route in ("rsp_create", "ral_create", "rte_create"):
        resp = resource_tenantless_client.post(_resource_url(route), {})
        assert resp.status_code == 302, route
        assert resp["Location"] == reverse("dashboard:home"), route

    assert {model: model.objects.count()
            for model in (ResourceProfile, ResourceAllocation, ResourceTimeEntry)} == before
