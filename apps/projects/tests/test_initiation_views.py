"""Projects 7.1 Project Initiation & Charter - VIEW tests.

The HTTP layer of the sub-module: 32 routes, the templates they render, **every context key the
test contract pins**, the four registers' search/filter/pagination behaviour, the 15 POST verbs'
state machines and the measured query budgets. Model invariants belong to
``test_initiation_models.py`` and form validation to ``test_initiation_forms.py``; role gating
(403), cross-tenant IDOR (404), CSRF and anonymous access belong to
``test_initiation_security.py``. Every request here is made by a TENANT ADMIN, so the only thing
that can refuse a verb in this lane is its own state gate.

What this lane exists to catch:

* **A blank region that returns 200.** A mismatched context key renders nothing and reports
  success (L8), so every page asserts CONTENT - the row's own ``PRQ-``/``PRJ-``/``PST-``/``PKO-``
  number in the body - and then asserts each pinned key by name. The keys the fix pass changed are
  pinned explicitly: ``attendee_total`` (NOT ``attendee_count``) on ``pko_list`` and
  ``prj_detail`` (I16), ``source_request`` on ``prj_detail``, ``decision_form`` on ``prq_detail``,
  and the ABSENCE of ``obj`` from all four create views.
* **A filter that silently empties a register.** Every documented control on all four registers is
  compared against the ORM's own answer for the same narrowing, and the junk values
  (``?status=zzz``, ``?page=abc``, ``?org_unit=abc``, ``?project=0``, an over-range pk) must
  return the FULL register at 200 - never a 500, never an empty page (L9/L11).
* **A verb that writes when it should refuse.** All 15 are exercised on both sides: the happy
  path down the whole chain (submit -> approve -> convert -> submit charter -> approve charter ->
  schedule -> mark held -> complete -> baseline), and then every now-forbidden source state, each
  of which must answer with a message, redirect, and leave the row byte-for-byte as it was -
  ``updated_at`` included, because a refusal that still calls ``save()`` is a refusal that lies.
  Four gates here are regression guards for real defects the review pass closed: ``pko_complete``
  needs ``held`` AND an approved charter (C2), ``pko_mark_held`` needs ``scheduled``,
  ``pko_mark_baseline_set`` refuses ``planned``/``scheduled``, and both charter verbs refuse a
  terminal project.
* **A replayed POST.** Every verb is posted twice; the second must be refused cleanly with ZERO
  field deltas (the deletes 404, which is the same claim for a row that is gone).
* **An N+1 that comes back.** ``pko_list``'s cost is pinned FLAT - measured at 2 rows, asserted
  unchanged at a full 15-row page. It was 25 queries at 15 rows before the annotation landed, and
  the annotation's ``.order_by()`` is load-bearing: an aggregate over a multi-valued relation
  makes Django drop ``Meta.ordering`` entirely, so the register would silently flip out of
  newest-first while every status assertion still passed.

Determinism (L16): every date basis is ``timezone.localdate()`` (via the conftest's
``_projectinitiation_today``) and every datetime basis is ``timezone.now()`` - the same bases the
views and ``Project.is_overdue`` use. ``datetime.date.today()`` never appears. Nothing here
touches the network.

Naming (mandatory): every test is ``test_projectinitiation_*`` and every module-level helper
``_projectinitiation_*`` / ``_PROJECTINITIATION_*``, so 7.2's lane appending into this package
cannot shadow either.

This file is pure ASCII on purpose. Several 7.1 messages carry U+2014 and curly quotes, so every
message assertion below matches an ASCII SUBSTRING - a copy edit must not turn into a red suite.
"""
import datetime

import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.projects.models import Project, ProjectKickoff, ProjectRequest, ProjectStakeholder
from apps.projects.tests.conftest import (
    PROJECTINITIATION_PAGE_SIZE,
    _projectinitiation_activity,
    _projectinitiation_fill_kickoffs,
    _projectinitiation_fill_projects,
    _projectinitiation_fill_requests,
    _projectinitiation_fill_stakeholders,
    _projectinitiation_kickoff,
    _projectinitiation_project,
    _projectinitiation_request,
    _projectinitiation_stakeholder,
    _projectinitiation_today,
)
from apps.projects.views.ProjectInitiation.Projects import TERMINAL_STATUSES

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Module-level helpers - every one ``_projectinitiation_*`` for the same reason the tests are
# (Python binds the LAST module-level definition, so an unprefixed helper here would silently
# rebind a sibling lane's). Record factories come from the conftest, which OWNS them.
# ==================================================================================================

#: Every url name the sub-module owns, grouped by entity. 32 is the contract's headline number.
_PROJECTINITIATION_REQUEST_ROUTES = (
    "prq_list", "prq_create", "prq_detail", "prq_edit", "prq_delete", "prq_submit",
    "prq_approve", "prq_reject", "prq_return_for_information", "prq_convert")
_PROJECTINITIATION_PROJECT_ROUTES = (
    "prj_list", "prj_create", "prj_detail", "prj_edit", "prj_delete", "prj_submit_charter",
    "prj_approve_charter")
_PROJECTINITIATION_STAKEHOLDER_ROUTES = (
    "pst_list", "pst_create", "pst_detail", "pst_edit", "pst_delete")
_PROJECTINITIATION_KICKOFF_ROUTES = (
    "pko_list", "pko_create", "pko_detail", "pko_edit", "pko_delete", "pko_schedule",
    "pko_mark_held", "pko_complete", "pko_mark_baseline_set")
_PROJECTINITIATION_ALL_ROUTES = (
    ("overview",)
    + _PROJECTINITIATION_REQUEST_ROUTES
    + _PROJECTINITIATION_PROJECT_ROUTES
    + _PROJECTINITIATION_STAKEHOLDER_ROUTES
    + _PROJECTINITIATION_KICKOFF_ROUTES)

#: The 15 POST-only verbs. A GET on any of them is 405 for an actor who clears the decorators
#: stacked ABOVE ``@require_POST`` - which for the eight admin-gated ones means an ADMIN GET.
_PROJECTINITIATION_POST_VERBS = (
    "prq_submit", "prq_approve", "prq_reject", "prq_return_for_information", "prq_convert",
    "prq_delete", "prj_submit_charter", "prj_approve_charter", "prj_delete", "pst_delete",
    "pko_schedule", "pko_mark_held", "pko_complete", "pko_mark_baseline_set", "pko_delete")

#: The four registers, with the model each one lists and the template it must render.
_PROJECTINITIATION_REGISTERS = (
    ("prq_list", ProjectRequest, "projects/initiation/projectrequest/list.html"),
    ("prj_list", Project, "projects/initiation/project/list.html"),
    ("pst_list", ProjectStakeholder, "projects/initiation/projectstakeholder/list.html"),
    ("pko_list", ProjectKickoff, "projects/initiation/projectkickoff/list.html"),
)


def _projectinitiation_url(name, *args):
    return reverse(f"projects:{name}", args=args)


def _projectinitiation_get(client, name, /, *args, **params):
    """GET one 7.1 route with an optional query string.

    ``client`` and ``name`` are POSITIONAL-ONLY on purpose: ``prj_list`` has a filter literally
    called ``client``, and without the ``/`` ``?client=<pk>`` binds to the argument instead of the
    query string ("got multiple values for argument 'client'").
    """
    return client.get(_projectinitiation_url(name, *args), params)


def _projectinitiation_post(client, name, /, *args, data=None, follow=False):
    """POST one 7.1 route. CSRF is off on the ordinary test client - the enforced-CSRF pair
    belongs to the security lane."""
    return client.post(_projectinitiation_url(name, *args), data or {}, follow=follow)


def _projectinitiation_messages(response):
    """Every message queued on the request that produced ``response``, as plain strings.

    Read off the REQUEST rather than the rendered page: the verbs all redirect, so nothing has
    rendered - and therefore consumed - the storage yet.
    """
    return [str(message) for message in get_messages(response.wsgi_request)]


def _projectinitiation_levels(response):
    return [message.level_tag for message in get_messages(response.wsgi_request)]


def _projectinitiation_said(response, fragment):
    """True when any queued message contains ``fragment``.

    ASCII substrings only - several 7.1 messages carry U+2014 and curly quotes, and matching a
    whole sentence would turn a copy edit into a failing test.
    """
    return any(fragment in message for message in _projectinitiation_messages(response))


def _projectinitiation_body(response):
    return response.content.decode()


def _projectinitiation_templates(response):
    """Every template name that rendered, including ``base.html`` and the widget partials."""
    return [template.name for template in response.templates if template.name]


def _projectinitiation_pks(response, key="object_list"):
    """The primary keys the page actually rendered, in order."""
    return [row.pk for row in response.context[key]]


def _projectinitiation_snapshot(obj):
    """Every concrete column of ``obj``, read FRESH from the database.

    ``updated_at`` is ``auto_now``, so it is in here deliberately: a refusal that still reaches
    ``save()`` moves it, and a snapshot comparison is the only thing that catches a "refusal"
    which writes nothing visible but writes.
    """
    fresh = type(obj)._default_manager.get(pk=obj.pk)
    return {field.attname: getattr(fresh, field.attname)
            for field in fresh._meta.concrete_fields}


def _projectinitiation_deltas(before, after):
    """The columns that changed between two snapshots, as ``{name: (before, after)}``."""
    return {name: (before[name], after[name])
            for name in before if before[name] != after[name]}


def _projectinitiation_unchanged(obj, before):
    """Assert ``obj``'s row is byte-for-byte what ``before`` recorded."""
    deltas = _projectinitiation_deltas(before, _projectinitiation_snapshot(obj))
    assert deltas == {}, f"a refused verb wrote to the row: {deltas}"


def _projectinitiation_audits(obj, action=None):
    """The audit rows written against ``obj``, newest first."""
    qs = AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)), object_id=obj.pk)
    if action is not None:
        qs = qs.filter(action=action)
    return list(qs.order_by("-id"))


def _projectinitiation_minute(days=7):
    """An aware datetime with zero seconds - the precision a ``datetime-local`` input carries.

    Derived from ``timezone.now()`` (L16), never ``datetime.datetime.now()``.
    """
    return (timezone.now() + datetime.timedelta(days=days)).replace(second=0, microsecond=0)


def _projectinitiation_local_minute_string(value):
    """``value`` as the ``%Y-%m-%dT%H:%M`` string the form's ``datetime-local`` widget accepts."""
    return timezone.localtime(value).strftime("%Y-%m-%dT%H:%M")


def _projectinitiation_request_payload(**overrides):
    """The MINIMUM valid ``ProjectRequestForm`` POST - exactly its 10 required fields."""
    payload = {
        "title": "Replace the depot scheduling spreadsheet",
        "description": "The depot still schedules 40 vans from one shared workbook.",
        "request_type": "new_project",
        "source": "internal",
        "priority": "medium",
        "strategic_alignment": "4",
        "estimated_cost": "120000.00",
        "estimated_benefit": "300000.00",
        "risk_rating": "medium",
        "feasibility": "feasible",
    }
    payload.update(overrides)
    return payload


def _projectinitiation_project_payload(**overrides):
    """The MINIMUM valid ``ProjectForm`` POST - name and methodology, nothing else."""
    payload = {"name": "Depot scheduling replacement", "methodology": "hybrid"}
    payload.update(overrides)
    return payload


def _projectinitiation_stakeholder_payload(project, **overrides):
    """The minimum valid ``ProjectStakeholderForm`` POST for ``project`` (the identity is added by
    the caller - the party-or-user rule belongs to the forms lane)."""
    payload = {
        "project": str(project.pk),
        "stakeholder_type": "sponsor",
        "raci_role": "a",
        "raci_scope": "charter approval",
        "influence": "high",
        "interest": "high",
        "comms_preference": "email",
        "comms_frequency": "weekly",
    }
    payload.update(overrides)
    return payload


def _projectinitiation_kickoff_payload(project, **overrides):
    """The minimum valid ``ProjectKickoffForm`` POST for ``project``."""
    payload = {"project": str(project.pk), "agenda_template": "standard"}
    payload.update(overrides)
    return payload


# ==================================================================================================
# 1. The route surface - all 32 names, and the published paths behind them
# ==================================================================================================

def test_projectinitiation_the_sub_module_owns_exactly_thirty_two_routes():
    """32 distinct names. A route added without its ``urlpatterns`` entry is a NoReverseMatch in a
    template (L7), which renders as a 500 on a page nobody tested."""
    assert len(set(_PROJECTINITIATION_ALL_ROUTES)) == 32


@pytest.mark.parametrize("name", _PROJECTINITIATION_ALL_ROUTES)
def test_projectinitiation_every_route_reverses(name):
    try:
        reverse(f"projects:{name}")
    except NoReverseMatch:
        reverse(f"projects:{name}", args=[1])


@pytest.mark.parametrize("name,path", [
    ("overview", "/projects/"),
    ("prq_list", "/projects/project-requests/"),
    ("prq_create", "/projects/project-requests/add/"),
    ("prj_list", "/projects/projects/"),
    ("prj_create", "/projects/projects/add/"),
    ("pst_list", "/projects/stakeholders/"),
    ("pst_create", "/projects/stakeholders/add/"),
    ("pko_list", "/projects/kickoffs/"),
    ("pko_create", "/projects/kickoffs/add/"),
])
def test_projectinitiation_literal_routes_keep_their_published_paths(name, path):
    """These are linked from the sidebar and bookmarked, and every one of them must stay AHEAD of
    its module's ``<int:pk>`` routes in the concatenated urlpatterns - Django is first-match-wins,
    so ``/projects/project-requests/add/`` resolving to ``prq_detail`` is one reorder away.

    ``prj_list`` at ``/projects/projects/`` is the one that looks wrong and is not: the app is
    mounted at ``projects/`` and the charter register lives at ``projects/`` inside it.
    """
    assert _projectinitiation_url(name) == path


@pytest.mark.parametrize("name,path", [
    ("prq_detail", "/projects/project-requests/7/"),
    ("prq_edit", "/projects/project-requests/7/edit/"),
    ("prq_delete", "/projects/project-requests/7/delete/"),
    ("prq_submit", "/projects/project-requests/7/submit/"),
    ("prq_approve", "/projects/project-requests/7/approve/"),
    ("prq_reject", "/projects/project-requests/7/reject/"),
    ("prq_return_for_information", "/projects/project-requests/7/return/"),
    ("prq_convert", "/projects/project-requests/7/convert/"),
    ("prj_detail", "/projects/projects/7/"),
    ("prj_edit", "/projects/projects/7/edit/"),
    ("prj_delete", "/projects/projects/7/delete/"),
    ("prj_submit_charter", "/projects/projects/7/submit-charter/"),
    ("prj_approve_charter", "/projects/projects/7/approve-charter/"),
    ("pst_detail", "/projects/stakeholders/7/"),
    ("pst_edit", "/projects/stakeholders/7/edit/"),
    ("pst_delete", "/projects/stakeholders/7/delete/"),
    ("pko_detail", "/projects/kickoffs/7/"),
    ("pko_edit", "/projects/kickoffs/7/edit/"),
    ("pko_delete", "/projects/kickoffs/7/delete/"),
    ("pko_schedule", "/projects/kickoffs/7/schedule/"),
    ("pko_mark_held", "/projects/kickoffs/7/mark-held/"),
    ("pko_complete", "/projects/kickoffs/7/complete/"),
    ("pko_mark_baseline_set", "/projects/kickoffs/7/baseline/"),
])
def test_projectinitiation_pk_routes_keep_their_published_paths(name, path):
    assert _projectinitiation_url(name, 7) == path


def test_projectinitiation_there_is_no_stakeholder_or_kickoff_workflow_route_that_is_not_pinned():
    """7.1 ships no ``pst_*`` verb beyond CRUD and no fifth kickoff ceremony. Asserting the
    ABSENCE keeps a later sub-module from quietly adding an ungated verb into this namespace."""
    for missing in ("pst_approve", "pst_submit", "pko_cancel", "pko_reopen", "prj_cancel",
                    "prj_reject_charter"):
        with pytest.raises(NoReverseMatch):
            reverse(f"projects:{missing}", args=[1])


# ==================================================================================================
# 2. The module landing page - seven stats, and the four aggregates behind them
# ==================================================================================================

def _projectinitiation_overview_scenario(tenant):
    """A workspace with a known answer for every one of the seven overview cards.

    Six requests (three of them in ``DECISION_STATUSES``, one approved-and-unconverted), two
    projects (one active), three stakeholders and one kickoff. Nothing here is converted, so
    ``approved_unconverted`` is exactly the one approved row.
    """
    _projectinitiation_request(tenant, title="Overview draft", status="draft")
    _projectinitiation_request(tenant, title="Overview submitted", status="submitted")
    _projectinitiation_request(tenant, title="Overview screening", status="screening")
    _projectinitiation_request(tenant, title="Overview assessment", status="assessment")
    _projectinitiation_request(tenant, title="Overview approved", status="approved",
                               decision="go")
    _projectinitiation_request(tenant, title="Overview rejected", status="rejected",
                               decision="no_go")
    live = _projectinitiation_project(tenant, name="Overview active", code="OVA-01",
                                      status="active")
    _projectinitiation_project(tenant, name="Overview draft project", code="OVD-01")
    _projectinitiation_fill_stakeholders(live, 3)
    _projectinitiation_kickoff(live)
    return live


def test_projectinitiation_overview_renders_its_seven_stats(client_a, tenant_a):
    _projectinitiation_overview_scenario(tenant_a)
    resp = _projectinitiation_get(client_a, "overview")
    assert resp.status_code == 200
    assert "projects/overview.html" in _projectinitiation_templates(resp)
    assert resp.context["request_count"] == 6
    assert resp.context["awaiting_decision"] == 3     # submitted + screening + assessment
    assert resp.context["approved_unconverted"] == 1
    assert resp.context["project_count"] == 2
    assert resp.context["active_projects"] == 1
    assert resp.context["stakeholder_count"] == 3
    assert resp.context["kickoff_count"] == 1
    body = _projectinitiation_body(resp)
    # CONTENT, not just status: a mis-named stat key renders an empty <div> at 200 (L8).
    assert "Awaiting decision" in body and "Ready to convert" in body
    assert "{{" not in body and "{%" not in body


def test_projectinitiation_overview_counts_only_the_requesting_workspace(
        client_a, tenant_a, tenant_b):
    _projectinitiation_overview_scenario(tenant_a)
    _projectinitiation_fill_requests(tenant_b, 4)
    _projectinitiation_fill_projects(tenant_b, 3, status="active")
    resp = _projectinitiation_get(client_a, "overview")
    assert resp.context["request_count"] == 6
    assert resp.context["project_count"] == 2
    assert resp.context["active_projects"] == 1


def test_projectinitiation_overview_stops_counting_a_request_once_it_is_converted(
        client_a, projectinitiation_request_approved):
    """``approved_unconverted`` is the "ready to convert" queue, so the moment the convert verb
    lands a project the card must drop it - otherwise the queue never empties."""
    before = _projectinitiation_get(client_a, "overview")
    assert before.context["approved_unconverted"] == 1

    _projectinitiation_post(client_a, "prq_convert", projectinitiation_request_approved.pk)

    after = _projectinitiation_get(client_a, "overview")
    assert after.context["approved_unconverted"] == 0
    assert after.context["project_count"] == 1


def test_projectinitiation_overview_is_an_empty_workspace_without_error(client_a):
    resp = _projectinitiation_get(client_a, "overview")
    assert resp.status_code == 200
    assert resp.context["request_count"] == 0
    assert "Nothing seeded yet" in _projectinitiation_body(resp)


def test_projectinitiation_overview_costs_one_query_per_table(client_a, tenant_a):
    """Fix M15 collapsed seven counts into four aggregates - one per TABLE. The five
    request/project cards are conditional counts over the same two row sets, so anything above
    four here means a card went back to its own round trip.
    """
    _projectinitiation_overview_scenario(tenant_a)
    _projectinitiation_get(client_a, "overview")  # warm the session / auth caches
    with CaptureQueriesContext(connection) as ctx:
        assert _projectinitiation_get(client_a, "overview").status_code == 200
    # Quoted identifiers, because "projects_project" is a PREFIX of "projects_projectrequest".
    tables = ('"projects_projectrequest"', '"projects_project"',
              '"projects_projectstakeholder"', '"projects_projectkickoff"')
    counted = {table: sum(1 for query in ctx.captured_queries if table in query["sql"])
               for table in tables}
    assert counted == {table: 1 for table in tables}


def test_projectinitiation_overview_has_no_pagination_or_filter_context(client_a, tenant_a):
    """It is a landing page, not a register: pinning the ABSENCE stops a later edit from bolting
    a half-built dashboard onto it (7.16 owns project analytics)."""
    _projectinitiation_overview_scenario(tenant_a)
    resp = _projectinitiation_get(client_a, "overview")
    for absent in ("object_list", "page_obj", "q", "status_choices"):
        assert absent not in resp.context, f"overview leaked a register key: {absent}"


# ==================================================================================================
# 3. The four registers render their rows - CONTENT, not status
# ==================================================================================================

@pytest.mark.parametrize("route,model,template", _PROJECTINITIATION_REGISTERS)
def test_projectinitiation_every_register_renders_its_contracted_template(
        client_a, route, model, template):
    """Two folder levels under the app, page as the bare filename."""
    resp = _projectinitiation_get(client_a, route)
    assert resp.status_code == 200
    assert template in _projectinitiation_templates(resp)


@pytest.mark.parametrize("route,model,template", _PROJECTINITIATION_REGISTERS)
def test_projectinitiation_every_register_carries_the_base_crud_context(
        client_a, route, model, template):
    """``object_list`` + ``page_obj`` + ``q`` is ``apps.core.crud``'s pinned contract; a register
    that renames any of them renders an empty table at 200."""
    resp = _projectinitiation_get(client_a, route, q="nothing matches this")
    assert resp.context["q"] == "nothing matches this"
    assert list(resp.context["object_list"]) == []
    assert resp.context["page_obj"].number == 1


def test_projectinitiation_request_register_renders_every_row_and_its_filter_context(
        client_a, projectinitiation_request_draft, projectinitiation_request_submitted,
        projectinitiation_request_approved, projectinitiation_request_rejected,
        projectinitiation_request_b, projectinitiation_org_unit_a):
    resp = _projectinitiation_get(client_a, "prq_list")
    assert resp.status_code == 200
    body = _projectinitiation_body(resp)
    for row in (projectinitiation_request_draft, projectinitiation_request_submitted,
                projectinitiation_request_approved, projectinitiation_request_rejected):
        assert row.number in body, f"{row.number} missing from the register"
        assert row.title in body
    # The workspace boundary is a register property, not only an IDOR one. Checked by PK and by
    # title, never by number: ``number`` is unique per TENANT, so Globex's request is also
    # ``PRQ-00001`` and a substring test would pass for the wrong reason.
    assert projectinitiation_request_b.pk not in _projectinitiation_pks(resp)
    assert projectinitiation_request_b.title not in body

    assert resp.context["status_choices"] == ProjectRequest.STATUS_CHOICES
    assert resp.context["request_type_choices"] == ProjectRequest.REQUEST_TYPE_CHOICES
    assert resp.context["priority_choices"] == ProjectRequest.PRIORITY_CHOICES
    assert resp.context["risk_rating_choices"] == ProjectRequest.RISK_RATING_CHOICES
    assert resp.context["feasibility_choices"] == ProjectRequest.FEASIBILITY_CHOICES
    assert resp.context["decision_choices"] == ProjectRequest.DECISION_CHOICES
    assert list(resp.context["org_units"]) == [projectinitiation_org_unit_a]
    assert "{{" not in body and "{%" not in body


def test_projectinitiation_project_register_renders_every_row_and_its_filter_context(
        client_a, projectinitiation_project_draft, projectinitiation_project_charter_approved,
        projectinitiation_project_cancelled, projectinitiation_project_b,
        projectinitiation_org_unit_a, projectinitiation_party_a):
    resp = _projectinitiation_get(client_a, "prj_list")
    assert resp.status_code == 200
    body = _projectinitiation_body(resp)
    for row in (projectinitiation_project_draft, projectinitiation_project_charter_approved,
                projectinitiation_project_cancelled):
        assert row.number in body and row.name in body
    assert projectinitiation_project_b.pk not in _projectinitiation_pks(resp)
    assert projectinitiation_project_b.name not in body

    assert resp.context["status_choices"] == Project.STATUS_CHOICES
    assert resp.context["charter_status_choices"] == Project.CHARTER_STATUS_CHOICES
    assert resp.context["methodology_choices"] == Project.METHODOLOGY_CHOICES
    assert list(resp.context["org_units"]) == [projectinitiation_org_unit_a]
    assert projectinitiation_party_a in list(resp.context["clients"])


def test_projectinitiation_stakeholder_register_renders_every_row_and_its_filter_context(
        client_a, projectinitiation_stakeholder_a, projectinitiation_stakeholder_monitor,
        projectinitiation_stakeholder_user_only, projectinitiation_stakeholder_b,
        projectinitiation_project_draft):
    resp = _projectinitiation_get(client_a, "pst_list")
    assert resp.status_code == 200
    body = _projectinitiation_body(resp)
    for row in (projectinitiation_stakeholder_a, projectinitiation_stakeholder_monitor,
                projectinitiation_stakeholder_user_only):
        assert row.number in body
    assert projectinitiation_stakeholder_b.pk not in _projectinitiation_pks(resp)
    # get_engagement_strategy_display() is HAND-WRITTEN (engagement_strategy is a property, so
    # Django generates no get_FOO_display) - without it this column is blank at 200.
    assert "Manage Closely" in body and "Monitor" in body

    assert list(resp.context["projects"]) == [projectinitiation_project_draft]
    assert resp.context["stakeholder_type_choices"] == ProjectStakeholder.STAKEHOLDER_TYPE_CHOICES
    assert resp.context["raci_role_choices"] == ProjectStakeholder.RACI_ROLE_CHOICES
    assert resp.context["influence_choices"] == ProjectStakeholder.INFLUENCE_CHOICES
    assert resp.context["interest_choices"] == ProjectStakeholder.INTEREST_CHOICES


def test_projectinitiation_kickoff_register_renders_every_row_and_its_filter_context(
        client_a, projectinitiation_kickoff_planned, projectinitiation_kickoff_scheduled,
        projectinitiation_kickoff_completed, projectinitiation_kickoff_b):
    resp = _projectinitiation_get(client_a, "pko_list")
    assert resp.status_code == 200
    body = _projectinitiation_body(resp)
    for row in (projectinitiation_kickoff_planned, projectinitiation_kickoff_scheduled,
                projectinitiation_kickoff_completed):
        assert row.number in body
        assert row.project.name in body
    assert projectinitiation_kickoff_b.pk not in _projectinitiation_pks(resp)
    assert projectinitiation_kickoff_b.project.name not in body

    assert resp.context["status_choices"] == ProjectKickoff.STATUS_CHOICES
    assert resp.context["agenda_template_choices"] == ProjectKickoff.AGENDA_TEMPLATE_CHOICES
    project_names = {project.name for project in resp.context["projects"]}
    assert projectinitiation_kickoff_planned.project.name in project_names


def test_projectinitiation_stakeholder_register_orders_by_the_influence_power_ranking(
        client_a, projectinitiation_project_draft, projectinitiation_party_a,
        projectinitiation_person_a, member_user):
    """``Meta.ordering`` is NOT the ranking: ``influence`` is a CharField, so ``-influence``
    sorts alphabetically (medium, low, high) - the exact inverse. The view annotates a numeric
    rank instead, and this asserts high before medium before low.
    """
    low = _projectinitiation_stakeholder(
        projectinitiation_project_draft, party=projectinitiation_party_a,
        raci_scope="low scope", influence="low")
    high = _projectinitiation_stakeholder(
        projectinitiation_project_draft, party=projectinitiation_person_a,
        raci_scope="high scope", influence="high")
    medium = _projectinitiation_stakeholder(
        projectinitiation_project_draft, user=member_user, raci_scope="medium scope",
        influence="medium")
    resp = _projectinitiation_get(client_a, "pst_list")
    assert _projectinitiation_pks(resp) == [high.pk, medium.pk, low.pk]
    assert [row.influence_rank for row in resp.context["object_list"]] == [3, 2, 1]


# ==================================================================================================
# 4. The four detail pages - every pinned context key present AND populated
# ==================================================================================================

def test_projectinitiation_request_detail_renders_its_object_and_decision_form(
        client_a, projectinitiation_request_submitted):
    obj = projectinitiation_request_submitted
    resp = _projectinitiation_get(client_a, "prq_detail", obj.pk)
    assert resp.status_code == 200
    assert "projects/initiation/projectrequest/detail.html" in _projectinitiation_templates(resp)
    assert resp.context["obj"].pk == obj.pk
    # `decision_form` is what renders the reason textarea BOTH gated verbs require; without it the
    # Return-for-Information form posts an empty reason and always bounces.
    assert "reason" in resp.context["decision_form"].fields
    body = _projectinitiation_body(resp)
    assert obj.number in body and obj.title in body
    assert "Business case" in body and "Risk-adjusted ROI" in body
    assert "{{" not in body and "{%" not in body


def test_projectinitiation_request_detail_renders_the_derived_economics(
        client_a, projectinitiation_request_draft):
    """cost 120000 / benefit 300000 / medium risk -> ROI 150.00% and 255000.00 risk-adjusted.
    These are PROPERTIES, so a template typo shows a blank cell at 200, not an error."""
    body = _projectinitiation_body(
        _projectinitiation_get(client_a, "prq_detail", projectinitiation_request_draft.pk))
    assert "150.00%" in body
    assert "255000.00" in body


def test_projectinitiation_request_detail_says_so_when_roi_has_no_cost_basis(
        client_a, tenant_a):
    """``roi_pct`` is None at zero cost - the page must say why, not print an empty percent."""
    obj = _projectinitiation_request(tenant_a, title="Zero cost idea", estimated_cost="0.00")
    body = _projectinitiation_body(_projectinitiation_get(client_a, "prq_detail", obj.pk))
    assert "Needs a cost estimate" in body


def test_projectinitiation_project_detail_renders_all_four_of_its_context_keys(
        client_a, projectinitiation_project_draft, projectinitiation_stakeholder_a,
        projectinitiation_kickoff_planned):
    obj = projectinitiation_project_draft
    resp = _projectinitiation_get(client_a, "prj_detail", obj.pk)
    assert resp.status_code == 200
    assert "projects/initiation/project/detail.html" in _projectinitiation_templates(resp)
    assert resp.context["obj"].pk == obj.pk
    assert [row.pk for row in resp.context["stakeholders"]] == [projectinitiation_stakeholder_a.pk]
    assert [row.pk for row in resp.context["kickoffs"]] == [projectinitiation_kickoff_planned.pk]
    # Created directly, so there is no source request - and the page must SAY that rather than
    # render a dead link.
    assert resp.context["source_request"] is None
    body = _projectinitiation_body(resp)
    assert obj.number in body and obj.name in body
    assert "Created directly" in body
    assert projectinitiation_kickoff_planned.number in body
    assert "{{" not in body and "{%" not in body


def test_projectinitiation_project_detail_links_back_to_the_request_it_came_from(
        client_a, projectinitiation_request_converted):
    project = projectinitiation_request_converted.converted_project
    resp = _projectinitiation_get(client_a, "prj_detail", project.pk)
    assert resp.context["source_request"].pk == projectinitiation_request_converted.pk
    body = _projectinitiation_body(resp)
    assert projectinitiation_request_converted.number in body
    assert _projectinitiation_url("prq_detail", projectinitiation_request_converted.pk) in body


def test_projectinitiation_project_detail_caps_its_stakeholder_block_at_fifty(
        client_a, projectinitiation_project_draft):
    """The charter page is a summary; the full grid is the stakeholder register's job. The cap is
    pinned so a later edit cannot turn a 500-person programme's charter into a 500-row page."""
    _projectinitiation_fill_stakeholders(projectinitiation_project_draft, 55)
    resp = _projectinitiation_get(client_a, "prj_detail", projectinitiation_project_draft.pk)
    assert len(list(resp.context["stakeholders"])) == 50
    assert "Full register" in _projectinitiation_body(resp)


def test_projectinitiation_stakeholder_detail_renders_its_object(
        client_a, projectinitiation_stakeholder_a, projectinitiation_party_a):
    obj = projectinitiation_stakeholder_a
    resp = _projectinitiation_get(client_a, "pst_detail", obj.pk)
    assert resp.status_code == 200
    assert ("projects/initiation/projectstakeholder/detail.html"
            in _projectinitiation_templates(resp))
    assert resp.context["obj"].pk == obj.pk
    body = _projectinitiation_body(resp)
    assert obj.number in body
    assert projectinitiation_party_a.name in body
    assert "Manage Closely" in body      # the hand-written display method, high + high
    assert "{{" not in body and "{%" not in body


def test_projectinitiation_kickoff_detail_renders_all_three_of_its_context_keys(
        client_a, projectinitiation_kickoff_planned, projectinitiation_stakeholder_a,
        projectinitiation_stakeholder_monitor, projectinitiation_activity_a):
    obj = projectinitiation_kickoff_planned
    resp = _projectinitiation_get(client_a, "pko_detail", obj.pk)
    assert resp.status_code == 200
    assert ("projects/initiation/projectkickoff/detail.html"
            in _projectinitiation_templates(resp))
    assert resp.context["obj"].pk == obj.pk
    # `attending` is exactly the stakeholders who opted in - the monitor row did not.
    assert [row.pk for row in resp.context["attending"]] == [projectinitiation_stakeholder_a.pk]
    assert [row.pk for row in resp.context["activities"]] == [projectinitiation_activity_a.pk]
    body = _projectinitiation_body(resp)
    assert obj.number in body
    assert projectinitiation_activity_a.subject in body
    assert "{{" not in body and "{%" not in body


def test_projectinitiation_kickoff_detail_activities_are_scoped_to_its_own_project(
        client_a, tenant_a, projectinitiation_kickoff_planned, projectinitiation_activity_a):
    """The activities block is a GFK read - it must key on THIS project, not on every Activity in
    the workspace."""
    other = _projectinitiation_project(tenant_a, name="Other project", code="OTH-01")
    stray = _projectinitiation_activity(other, subject="Unrelated onboarding item")
    resp = _projectinitiation_get(client_a, "pko_detail", projectinitiation_kickoff_planned.pk)
    assert stray.pk not in [row.pk for row in resp.context["activities"]]
    assert "Unrelated onboarding item" not in _projectinitiation_body(resp)


# ==================================================================================================
# 5. The create and edit pages - `form` + `is_edit`, and NO `obj` on a create
# ==================================================================================================

_PROJECTINITIATION_CREATE_PAGES = (
    ("prq_create", "projects/initiation/projectrequest/form.html", "New Project Request"),
    ("prj_create", "projects/initiation/project/form.html", "New Project"),
    ("pst_create", "projects/initiation/projectstakeholder/form.html", "Add Stakeholder"),
    ("pko_create", "projects/initiation/projectkickoff/form.html", "Plan Kickoff"),
)


@pytest.mark.parametrize("route,template,heading", _PROJECTINITIATION_CREATE_PAGES)
def test_projectinitiation_every_create_page_renders_an_unbound_form(
        client_a, route, template, heading):
    resp = _projectinitiation_get(client_a, route)
    assert resp.status_code == 200
    assert template in _projectinitiation_templates(resp)
    assert resp.context["is_edit"] is False
    assert not resp.context["form"].is_bound
    # `obj` on a create page would make the shared form template render an edit breadcrumb for a
    # row that does not exist yet.
    assert "obj" not in resp.context
    body = _projectinitiation_body(resp)
    assert heading in body
    assert "csrfmiddlewaretoken" in body
    assert "{{" not in body and "{%" not in body


@pytest.mark.parametrize("route,fixture,template", [
    ("prq_edit", "projectinitiation_request_draft",
     "projects/initiation/projectrequest/form.html"),
    ("prj_edit", "projectinitiation_project_draft", "projects/initiation/project/form.html"),
    ("pst_edit", "projectinitiation_stakeholder_a",
     "projects/initiation/projectstakeholder/form.html"),
    ("pko_edit", "projectinitiation_kickoff_planned",
     "projects/initiation/projectkickoff/form.html"),
])
def test_projectinitiation_every_edit_page_renders_the_row_it_edits(
        client_a, request, route, fixture, template):
    obj = request.getfixturevalue(fixture)
    resp = _projectinitiation_get(client_a, route, obj.pk)
    assert resp.status_code == 200
    assert template in _projectinitiation_templates(resp)
    assert resp.context["is_edit"] is True
    assert resp.context["obj"].pk == obj.pk
    assert resp.context["form"].instance.pk == obj.pk
    assert obj.number in _projectinitiation_body(resp)


def test_projectinitiation_stakeholder_create_preselects_the_project_from_the_query_string(
        client_a, projectinitiation_project_draft):
    """The charter page links here as ``?project=<pk>``; without the initial the user has to find
    the project again in a dropdown they just came from."""
    resp = _projectinitiation_get(client_a, "pst_create",
                                  project=str(projectinitiation_project_draft.pk))
    assert resp.context["form"]["project"].value() == str(projectinitiation_project_draft.pk)
    assert f'value="{projectinitiation_project_draft.pk}" selected' in _projectinitiation_body(
        resp)


def test_projectinitiation_kickoff_create_preselects_the_project_from_the_query_string(
        client_a, tenant_a):
    project = _projectinitiation_project(tenant_a, name="Kickoff target", code="KTG-01")
    resp = _projectinitiation_get(client_a, "pko_create", project=str(project.pk))
    assert resp.context["form"]["project"].value() == str(project.pk)


def test_projectinitiation_kickoff_create_offers_only_projects_without_a_kickoff(
        client_a, tenant_a, projectinitiation_kickoff_planned):
    """One kickoff per project (``unique_together``), so a project that already has one is not
    selectable and the charter page hides its Plan Kickoff button."""
    free = _projectinitiation_project(tenant_a, name="Still free", code="FRE-01")
    resp = _projectinitiation_get(client_a, "pko_create")
    offered = set(resp.context["form"].fields["project"].queryset.values_list("pk", flat=True))
    assert free.pk in offered
    assert projectinitiation_kickoff_planned.project_id not in offered


def test_projectinitiation_kickoff_edit_still_offers_its_own_project(
        client_a, projectinitiation_kickoff_planned):
    """The exclusion above would otherwise make every kickoff un-editable - its own project is
    "taken" by itself."""
    resp = _projectinitiation_get(client_a, "pko_edit", projectinitiation_kickoff_planned.pk)
    offered = set(resp.context["form"].fields["project"].queryset.values_list("pk", flat=True))
    assert projectinitiation_kickoff_planned.project_id in offered


@pytest.mark.parametrize("route", ["prq_create", "prj_create", "pst_create", "pko_create"])
def test_projectinitiation_create_pages_turn_a_tenantless_user_away(
        projectinitiation_tenantless_client, route):
    """The guard is on the FIRST line of each create view, before the form is built:
    ``TenantModelForm`` only scopes its FK dropdowns when ``tenant is not None``, so rendering the
    form for a tenant-less user lists every workspace's parties, org units and user emails.
    """
    resp = _projectinitiation_get(projectinitiation_tenantless_client, route)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("dashboard:home")
    assert _projectinitiation_said(resp, "Select a tenant workspace before creating records.")


def test_projectinitiation_request_edit_is_locked_once_a_decision_is_stamped(
        client_a, projectinitiation_request_approved):
    """The lock follows the EVIDENCE stamp, not a status list: ``decided_by``/``decided_at``
    attest that an admin weighed this business case, so leaving ``estimated_cost`` writable
    afterwards means the ROI on the page is not the ROI that was approved."""
    obj = projectinitiation_request_approved
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_get(client_a, "prq_edit", obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _projectinitiation_url("prq_detail", obj.pk)
    assert _projectinitiation_said(resp, "cannot be edited")
    assert "error" in _projectinitiation_levels(resp)
    _projectinitiation_unchanged(obj, before)


def test_projectinitiation_request_edit_refuses_a_post_to_a_decided_row(
        client_a, projectinitiation_request_approved):
    """The lock must survive a hand-crafted POST that never rendered the form."""
    obj = projectinitiation_request_approved
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(
        client_a, "prq_edit", obj.pk,
        data=_projectinitiation_request_payload(title="Rewritten after approval"))
    assert resp.status_code == 302
    assert resp["Location"] == _projectinitiation_url("prq_detail", obj.pk)
    _projectinitiation_unchanged(obj, before)


def test_projectinitiation_request_edit_is_locked_on_a_converted_row(
        client_a, projectinitiation_request_converted):
    """``converted`` is locked separately from the decision stamp: its business case is now a
    project's charter."""
    resp = _projectinitiation_get(client_a, "prq_edit",
                                  projectinitiation_request_converted.pk)
    assert resp.status_code == 302
    assert _projectinitiation_said(resp, "cannot be edited")


@pytest.mark.parametrize("fixture", ["projectinitiation_request_draft",
                                     "projectinitiation_request_submitted",
                                     "projectinitiation_request_needs_information",
                                     "projectinitiation_request_deferred"])
def test_projectinitiation_request_edit_stays_open_while_nothing_is_decided(
        client_a, request, fixture):
    obj = request.getfixturevalue(fixture)
    resp = _projectinitiation_get(client_a, "prq_edit", obj.pk)
    assert resp.status_code == 200
    assert resp.context["obj"].pk == obj.pk


def test_projectinitiation_project_edit_is_locked_once_the_charter_is_approved(
        client_a, projectinitiation_project_charter_approved):
    obj = projectinitiation_project_charter_approved
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_get(client_a, "prj_edit", obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _projectinitiation_url("prj_detail", obj.pk)
    assert _projectinitiation_said(resp, "An approved charter cannot be edited")
    _projectinitiation_unchanged(obj, before)


def test_projectinitiation_project_edit_refuses_a_post_to_an_approved_charter(
        client_a, projectinitiation_project_charter_approved):
    obj = projectinitiation_project_charter_approved
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(
        client_a, "prj_edit", obj.pk,
        data=_projectinitiation_project_payload(name="Rewritten under the signature"))
    assert resp.status_code == 302
    _projectinitiation_unchanged(obj, before)


@pytest.mark.parametrize("fixture", ["projectinitiation_project_draft",
                                     "projectinitiation_project_charter_submitted",
                                     "projectinitiation_project_charter_rejected",
                                     "projectinitiation_project_cancelled"])
def test_projectinitiation_project_edit_stays_open_until_the_charter_is_approved(
        client_a, request, fixture):
    obj = request.getfixturevalue(fixture)
    resp = _projectinitiation_get(client_a, "prj_edit", obj.pk)
    assert resp.status_code == 200
    assert resp.context["obj"].pk == obj.pk


# ==================================================================================================
# 6. Create / edit / delete - the rows actually land, in the REQUEST's workspace
# ==================================================================================================

def test_projectinitiation_request_create_saves_the_row_in_the_request_tenant(
        client_a, tenant_a, admin_user, projectinitiation_org_unit_a):
    resp = _projectinitiation_post(
        client_a, "prq_create",
        data=_projectinitiation_request_payload(
            title="Fleet telematics refresh", org_unit=str(projectinitiation_org_unit_a.pk)))
    obj = ProjectRequest.objects.get(title="Fleet telematics refresh")
    assert resp.status_code == 302
    assert resp["Location"] == _projectinitiation_url("prq_detail", obj.pk)
    assert obj.tenant_id == tenant_a.pk
    assert obj.created_by_id == admin_user.pk          # stamped by the view, never by the form
    assert obj.number.startswith("PRQ-")
    assert obj.status == "draft"                        # verb-driven, so it starts at the default
    assert obj.decision == "" and obj.submitted_at is None and obj.decided_at is None
    assert _projectinitiation_said(resp, f"Request {obj.number} created.")
    assert _projectinitiation_audits(obj, action="create")


def test_projectinitiation_request_create_redisplays_the_form_on_an_invalid_post(client_a):
    resp = _projectinitiation_post(
        client_a, "prq_create", data=_projectinitiation_request_payload(title=""))
    assert resp.status_code == 200
    assert "title" in resp.context["form"].errors
    assert resp.context["is_edit"] is False
    assert ProjectRequest.objects.count() == 0


def test_projectinitiation_project_create_saves_the_row_in_the_request_tenant(
        client_a, tenant_a, admin_user):
    resp = _projectinitiation_post(
        client_a, "prj_create",
        data=_projectinitiation_project_payload(name="Northern plant second shift"))
    obj = Project.objects.get(name="Northern plant second shift")
    assert resp["Location"] == _projectinitiation_url("prj_detail", obj.pk)
    assert obj.tenant_id == tenant_a.pk and obj.created_by_id == admin_user.pk
    assert obj.number.startswith("PRJ-")
    # Both workflow columns are verb-driven, so a create lands on the defaults whatever it POSTs.
    assert obj.status == "draft" and obj.charter_status == "draft"
    assert obj.charter_approved_by_id is None and obj.charter_approved_at is None
    assert obj.request_id is None                       # provenance is the convert verb's alone
    assert _projectinitiation_said(resp, f"Project {obj.number} created.")


def test_projectinitiation_project_create_redisplays_the_form_on_an_invalid_post(client_a):
    resp = _projectinitiation_post(
        client_a, "prj_create", data=_projectinitiation_project_payload(name=""))
    assert resp.status_code == 200
    assert "name" in resp.context["form"].errors
    assert Project.objects.count() == 0


def test_projectinitiation_stakeholder_create_saves_the_row_in_the_request_tenant(
        client_a, tenant_a, admin_user, projectinitiation_project_draft,
        projectinitiation_party_a):
    resp = _projectinitiation_post(
        client_a, "pst_create",
        data=_projectinitiation_stakeholder_payload(
            projectinitiation_project_draft, party=str(projectinitiation_party_a.pk),
            raci_scope="budget sign-off"))
    obj = ProjectStakeholder.objects.get(raci_scope="budget sign-off")
    assert resp["Location"] == _projectinitiation_url("pst_detail", obj.pk)
    assert obj.tenant_id == tenant_a.pk and obj.created_by_id == admin_user.pk
    assert obj.number.startswith("PST-")
    assert obj.project_id == projectinitiation_project_draft.pk
    assert _projectinitiation_said(resp, f"Stakeholder {obj.number} added.")


def test_projectinitiation_stakeholder_create_rejects_a_row_naming_nobody(
        client_a, projectinitiation_project_draft):
    """Neither party nor user is a non-field (``__all__``) error from the MODEL's ``clean()`` -
    the view must redisplay it, not save a stakeholder that identifies no one."""
    resp = _projectinitiation_post(
        client_a, "pst_create",
        data=_projectinitiation_stakeholder_payload(projectinitiation_project_draft))
    assert resp.status_code == 200
    assert resp.context["form"].non_field_errors()
    assert ProjectStakeholder.objects.count() == 0


def test_projectinitiation_kickoff_create_saves_the_row_in_the_request_tenant(
        client_a, tenant_a, admin_user):
    project = _projectinitiation_project(tenant_a, name="Kickoff host", code="KHX-01")
    meeting = _projectinitiation_minute(days=10)
    resp = _projectinitiation_post(
        client_a, "pko_create",
        data=_projectinitiation_kickoff_payload(
            project, meeting_date=_projectinitiation_local_minute_string(meeting),
            location_or_link="Depot boardroom"))
    obj = ProjectKickoff.objects.get(project=project)
    assert resp["Location"] == _projectinitiation_url("pko_detail", obj.pk)
    assert obj.tenant_id == tenant_a.pk and obj.created_by_id == admin_user.pk
    assert obj.number.startswith("PKO-")
    assert obj.status == "planned"                      # every ceremony starts unplanned-for
    assert obj.completed_at is None and obj.baseline_acknowledged_at is None
    assert obj.meeting_date == meeting
    assert _projectinitiation_said(resp, f"Kickoff {obj.number} planned.")


def test_projectinitiation_kickoff_create_refuses_a_second_kickoff_for_one_project(
        client_a, projectinitiation_kickoff_planned):
    """``unique_together = ("tenant", "project")``. The dropdown already hides the project, so
    this is the crafted-POST half - it must be a form error, never an IntegrityError 500."""
    resp = _projectinitiation_post(
        client_a, "pko_create",
        data=_projectinitiation_kickoff_payload(projectinitiation_kickoff_planned.project))
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert ProjectKickoff.objects.filter(
        project=projectinitiation_kickoff_planned.project).count() == 1


def test_projectinitiation_request_edit_saves_and_returns_to_the_register(
        client_a, projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    resp = _projectinitiation_post(
        client_a, "prq_edit", obj.pk,
        data=_projectinitiation_request_payload(title="Depot scheduling, revised"))
    assert resp.status_code == 302
    assert resp["Location"] == _projectinitiation_url("prq_list")
    obj.refresh_from_db()
    assert obj.title == "Depot scheduling, revised"
    assert _projectinitiation_said(resp, "Updated successfully.")
    assert _projectinitiation_audits(obj, action="update")


def test_projectinitiation_project_edit_saves_and_returns_to_the_register(
        client_a, projectinitiation_project_draft):
    obj = projectinitiation_project_draft
    resp = _projectinitiation_post(
        client_a, "prj_edit", obj.pk,
        data=_projectinitiation_project_payload(name="Depot scheduling, rescoped",
                                                methodology="agile"))
    assert resp["Location"] == _projectinitiation_url("prj_list")
    obj.refresh_from_db()
    assert obj.name == "Depot scheduling, rescoped" and obj.methodology == "agile"
    # The excluded columns survive an edit untouched - they are not on the form at all.
    assert obj.charter_status == "draft" and obj.status == "draft"


def test_projectinitiation_stakeholder_edit_saves_and_returns_to_the_register(
        client_a, projectinitiation_stakeholder_a, projectinitiation_party_a):
    obj = projectinitiation_stakeholder_a
    resp = _projectinitiation_post(
        client_a, "pst_edit", obj.pk,
        data=_projectinitiation_stakeholder_payload(
            obj.project, party=str(projectinitiation_party_a.pk),
            raci_scope=obj.raci_scope, influence="low", interest="low", notes="Stepped back."))
    assert resp["Location"] == _projectinitiation_url("pst_list")
    obj.refresh_from_db()
    assert obj.influence == "low" and obj.interest == "low"
    assert obj.engagement_strategy == "monitor"     # derived, so the grid follows the edit


def test_projectinitiation_kickoff_edit_saves_and_returns_to_the_register(
        client_a, projectinitiation_kickoff_planned):
    obj = projectinitiation_kickoff_planned
    resp = _projectinitiation_post(
        client_a, "pko_edit", obj.pk,
        data=_projectinitiation_kickoff_payload(
            obj.project, agenda_template="agile",
            meeting_date=_projectinitiation_local_minute_string(obj.meeting_date),
            agenda="Sprint zero walkthrough."))
    assert resp["Location"] == _projectinitiation_url("pko_list")
    obj.refresh_from_db()
    assert obj.agenda_template == "agile" and obj.agenda == "Sprint zero walkthrough."
    assert obj.status == "planned"                  # `status` is not a form field


@pytest.mark.parametrize("route,fixture,model,list_route", [
    ("prq_delete", "projectinitiation_request_draft", ProjectRequest, "prq_list"),
    ("prj_delete", "projectinitiation_project_draft", Project, "prj_list"),
    ("pst_delete", "projectinitiation_stakeholder_a", ProjectStakeholder, "pst_list"),
    ("pko_delete", "projectinitiation_kickoff_planned", ProjectKickoff, "pko_list"),
])
def test_projectinitiation_delete_removes_the_row_on_post(
        client_a, request, route, fixture, model, list_route):
    obj = request.getfixturevalue(fixture)
    resp = _projectinitiation_post(client_a, route, obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _projectinitiation_url(list_route)
    assert not model.objects.filter(pk=obj.pk).exists()
    assert _projectinitiation_said(resp, "Deleted successfully.")


@pytest.mark.parametrize("route,fixture,model", [
    ("prq_delete", "projectinitiation_request_draft", ProjectRequest),
    ("prj_delete", "projectinitiation_project_draft", Project),
    ("pst_delete", "projectinitiation_stakeholder_a", ProjectStakeholder),
    ("pko_delete", "projectinitiation_kickoff_planned", ProjectKickoff),
])
def test_projectinitiation_delete_never_happens_on_a_get(
        client_a, request, route, fixture, model):
    """A GET that deletes is a link a crawler, a prefetcher or a browser preview can fire."""
    obj = request.getfixturevalue(fixture)
    resp = _projectinitiation_get(client_a, route, obj.pk)
    assert resp.status_code == 405
    assert model.objects.filter(pk=obj.pk).exists()


def test_projectinitiation_deleting_a_project_cascades_its_stakeholders_and_kickoff(
        client_a, projectinitiation_project_draft, projectinitiation_stakeholder_a,
        projectinitiation_kickoff_planned):
    """Both children are ``on_delete=CASCADE`` - the confirm dialog says so, and this is what
    makes that promise true."""
    _projectinitiation_post(client_a, "prj_delete", projectinitiation_project_draft.pk)
    assert not ProjectStakeholder.objects.filter(
        pk=projectinitiation_stakeholder_a.pk).exists()
    assert not ProjectKickoff.objects.filter(pk=projectinitiation_kickoff_planned.pk).exists()


# ==================================================================================================
# 7. Search, filters and pagination on all four registers
# ==================================================================================================

#: The lifecycle fixtures that between them cover every documented filter value on each register.
_PROJECTINITIATION_REQUEST_FIXTURES = (
    "projectinitiation_request_draft", "projectinitiation_request_submitted",
    "projectinitiation_request_screening", "projectinitiation_request_needs_information",
    "projectinitiation_request_approved", "projectinitiation_request_rejected",
    "projectinitiation_request_deferred")
_PROJECTINITIATION_PROJECT_FIXTURES = (
    "projectinitiation_project_draft", "projectinitiation_project_charter_submitted",
    "projectinitiation_project_charter_approved", "projectinitiation_project_charter_rejected",
    "projectinitiation_project_cancelled", "projectinitiation_project_overdue")
_PROJECTINITIATION_STAKEHOLDER_FIXTURES = (
    "projectinitiation_stakeholder_a", "projectinitiation_stakeholder_monitor",
    "projectinitiation_stakeholder_user_only")
_PROJECTINITIATION_KICKOFF_FIXTURES = (
    "projectinitiation_kickoff_planned", "projectinitiation_kickoff_scheduled",
    "projectinitiation_kickoff_held", "projectinitiation_kickoff_completed",
    "projectinitiation_kickoff_baselined")


def _projectinitiation_load(request, names):
    """Materialise a tuple of fixture names, in order."""
    return [request.getfixturevalue(name) for name in names]


def _projectinitiation_assert_narrows(client, route, model, tenant, params, lookups):
    """The register's answer for ``params`` must equal the ORM's answer for ``lookups`` - and be
    strictly smaller than the unfiltered register, so a control that does nothing fails too."""
    expected = set(model.objects.filter(tenant=tenant, **lookups).values_list("pk", flat=True))
    total = model.objects.filter(tenant=tenant).count()
    assert expected, "the scenario has no row for this filter value - the test proves nothing"
    assert len(expected) < total, "this filter value matches every row - it cannot narrow"
    resp = _projectinitiation_get(client, route, **params)
    assert resp.status_code == 200
    assert set(_projectinitiation_pks(resp)) == expected
    return resp


@pytest.mark.parametrize("param,lookup,value", [
    ("status", "status", "submitted"),
    ("status", "status", "rejected"),
    ("request_type", "request_type", "change_request"),
    ("request_type", "request_type", "idea"),
    ("priority", "priority", "critical"),
    ("priority", "priority", "low"),
    ("risk_rating", "risk_rating", "high"),
    ("feasibility", "feasibility", "not_feasible"),
    ("decision", "decision", "go"),
    ("decision", "decision", "no_go"),
])
def test_projectinitiation_request_register_filters_narrow_to_the_orm_answer(
        client_a, request, tenant_a, param, lookup, value):
    _projectinitiation_load(request, _PROJECTINITIATION_REQUEST_FIXTURES)
    _projectinitiation_assert_narrows(
        client_a, "prq_list", ProjectRequest, tenant_a, {param: value}, {lookup: value})


def test_projectinitiation_request_register_filters_by_org_unit_pk(
        client_a, request, tenant_a, projectinitiation_org_unit_a):
    _projectinitiation_load(request, _PROJECTINITIATION_REQUEST_FIXTURES)
    _projectinitiation_assert_narrows(
        client_a, "prq_list", ProjectRequest, tenant_a,
        {"org_unit": str(projectinitiation_org_unit_a.pk)},
        {"org_unit_id": projectinitiation_org_unit_a.pk})


@pytest.mark.parametrize("term", ["Supplier scorecard", "warehouses", "TELEMATICS"])
def test_projectinitiation_request_register_searches_by_title(
        client_a, request, tenant_a, term):
    """``icontains``, so the last case also pins that the search is case-insensitive."""
    _projectinitiation_load(request, _PROJECTINITIATION_REQUEST_FIXTURES)
    resp = _projectinitiation_get(client_a, "prq_list", q=term)
    assert resp.status_code == 200
    assert resp.context["q"] == term
    found = set(_projectinitiation_pks(resp))
    assert found == set(ProjectRequest.objects.filter(
        tenant=tenant_a, title__icontains=term).values_list("pk", flat=True))
    assert 0 < len(found) < ProjectRequest.objects.filter(tenant=tenant_a).count()


def test_projectinitiation_request_register_searches_the_description_too(
        client_a, request, tenant_a):
    """The factory gives every row the same description, so the needle is planted on one row -
    a term that matches everything would pass a search test that does nothing."""
    _projectinitiation_load(request, _PROJECTINITIATION_REQUEST_FIXTURES)
    needle = _projectinitiation_request(
        tenant_a, title="Needle request",
        description="Four depots share one unsupported Access database.")
    resp = _projectinitiation_get(client_a, "prq_list", q="unsupported Access")
    assert _projectinitiation_pks(resp) == [needle.pk]


def test_projectinitiation_request_register_searches_by_number(
        client_a, projectinitiation_request_draft, projectinitiation_request_submitted):
    resp = _projectinitiation_get(client_a, "prq_list",
                                  q=projectinitiation_request_submitted.number)
    assert _projectinitiation_pks(resp) == [projectinitiation_request_submitted.pk]


@pytest.mark.parametrize("param,lookup,value", [
    ("status", "status", "cancelled"),
    ("status", "status", "chartered"),
    ("charter_status", "charter_status", "submitted"),
    ("charter_status", "charter_status", "rejected"),
    ("charter_status", "charter_status", "approved"),
])
def test_projectinitiation_project_register_filters_narrow_to_the_orm_answer(
        client_a, request, tenant_a, param, lookup, value):
    _projectinitiation_load(request, _PROJECTINITIATION_PROJECT_FIXTURES)
    _projectinitiation_assert_narrows(
        client_a, "prj_list", Project, tenant_a, {param: value}, {lookup: value})


def test_projectinitiation_project_register_filters_by_methodology(
        client_a, request, tenant_a):
    _projectinitiation_load(request, _PROJECTINITIATION_PROJECT_FIXTURES)
    _projectinitiation_project(tenant_a, name="Agile pilot", code="AGP-01", methodology="agile")
    _projectinitiation_assert_narrows(
        client_a, "prj_list", Project, tenant_a, {"methodology": "agile"},
        {"methodology": "agile"})


def test_projectinitiation_project_register_filters_by_org_unit_and_client_pks(
        client_a, request, tenant_a, projectinitiation_org_unit_a, projectinitiation_party_a):
    _projectinitiation_load(request, _PROJECTINITIATION_PROJECT_FIXTURES)
    _projectinitiation_assert_narrows(
        client_a, "prj_list", Project, tenant_a,
        {"org_unit": str(projectinitiation_org_unit_a.pk)},
        {"org_unit_id": projectinitiation_org_unit_a.pk})
    _projectinitiation_assert_narrows(
        client_a, "prj_list", Project, tenant_a,
        {"client": str(projectinitiation_party_a.pk)},
        {"client_id": projectinitiation_party_a.pk})


@pytest.mark.parametrize("term,field", [
    ("Overdue rollout", "name"),
    ("SSN-01", "code"),
])
def test_projectinitiation_project_register_searches_name_and_code(
        client_a, request, tenant_a, term, field):
    _projectinitiation_load(request, _PROJECTINITIATION_PROJECT_FIXTURES)
    resp = _projectinitiation_get(client_a, "prj_list", q=term)
    found = set(_projectinitiation_pks(resp))
    assert found == set(Project.objects.filter(
        tenant=tenant_a, **{f"{field}__icontains": term}).values_list("pk", flat=True))
    assert 0 < len(found) < Project.objects.filter(tenant=tenant_a).count()


@pytest.mark.parametrize("param,lookup,value", [
    ("stakeholder_type", "stakeholder_type", "sponsor"),
    ("stakeholder_type", "stakeholder_type", "team_member"),
    ("raci_role", "raci_role", "a"),
    ("raci_role", "raci_role", "c"),
    ("influence", "influence", "high"),
    ("influence", "influence", "medium"),
    ("interest", "interest", "low"),
])
def test_projectinitiation_stakeholder_register_filters_narrow_to_the_orm_answer(
        client_a, request, tenant_a, param, lookup, value):
    _projectinitiation_load(request, _PROJECTINITIATION_STAKEHOLDER_FIXTURES)
    _projectinitiation_assert_narrows(
        client_a, "pst_list", ProjectStakeholder, tenant_a, {param: value}, {lookup: value})


def test_projectinitiation_stakeholder_register_filters_by_project_pk(
        client_a, request, tenant_a, projectinitiation_project_draft):
    _projectinitiation_load(request, _PROJECTINITIATION_STAKEHOLDER_FIXTURES)
    other = _projectinitiation_project(tenant_a, name="Second project", code="SEC-01")
    _projectinitiation_stakeholder(other, raci_scope="other scope")
    _projectinitiation_assert_narrows(
        client_a, "pst_list", ProjectStakeholder, tenant_a,
        {"project": str(projectinitiation_project_draft.pk)},
        {"project_id": projectinitiation_project_draft.pk})


def test_projectinitiation_stakeholder_register_searches_the_raci_scope(
        client_a, request, tenant_a):
    _projectinitiation_load(request, _PROJECTINITIATION_STAKEHOLDER_FIXTURES)
    resp = _projectinitiation_get(client_a, "pst_list", q="data migration")
    found = set(_projectinitiation_pks(resp))
    assert found == set(ProjectStakeholder.objects.filter(
        tenant=tenant_a, raci_scope__icontains="data migration").values_list("pk", flat=True))
    assert 0 < len(found) < ProjectStakeholder.objects.filter(tenant=tenant_a).count()


def test_projectinitiation_stakeholder_register_searches_the_notes(
        client_a, request, tenant_a, projectinitiation_project_draft):
    """The factory gives every stakeholder the same note, so the needle is planted on one row."""
    _projectinitiation_load(request, _PROJECTINITIATION_STAKEHOLDER_FIXTURES)
    needle = _projectinitiation_stakeholder(
        projectinitiation_project_draft, raci_scope="vendor selection",
        notes="Chairs the vendor selection panel.")
    resp = _projectinitiation_get(client_a, "pst_list", q="vendor selection panel")
    assert _projectinitiation_pks(resp) == [needle.pk]


@pytest.mark.parametrize("value", ["planned", "scheduled", "held", "completed"])
def test_projectinitiation_kickoff_register_filters_by_status(
        client_a, request, tenant_a, value):
    _projectinitiation_load(request, _PROJECTINITIATION_KICKOFF_FIXTURES)
    _projectinitiation_assert_narrows(
        client_a, "pko_list", ProjectKickoff, tenant_a, {"status": value}, {"status": value})


def test_projectinitiation_kickoff_register_filters_by_agenda_template(
        client_a, request, tenant_a):
    _projectinitiation_load(request, _PROJECTINITIATION_KICKOFF_FIXTURES)
    _projectinitiation_kickoff(
        _projectinitiation_project(tenant_a, name="Agile ceremony", code="AGC-01"),
        agenda_template="agile")
    _projectinitiation_assert_narrows(
        client_a, "pko_list", ProjectKickoff, tenant_a, {"agenda_template": "agile"},
        {"agenda_template": "agile"})


def test_projectinitiation_kickoff_register_filters_by_project_pk(
        client_a, request, tenant_a, projectinitiation_kickoff_planned):
    _projectinitiation_load(request, _PROJECTINITIATION_KICKOFF_FIXTURES)
    _projectinitiation_assert_narrows(
        client_a, "pko_list", ProjectKickoff, tenant_a,
        {"project": str(projectinitiation_kickoff_planned.project_id)},
        {"project_id": projectinitiation_kickoff_planned.project_id})


@pytest.mark.parametrize("term,field", [
    ("Depot boardroom", "location_or_link"),
    ("Charter walkthrough", "agenda"),
])
def test_projectinitiation_kickoff_register_searches_location_and_agenda(
        client_a, request, tenant_a, term, field):
    _projectinitiation_load(request, _PROJECTINITIATION_KICKOFF_FIXTURES)
    _projectinitiation_kickoff(
        _projectinitiation_project(tenant_a, name="Quiet ceremony", code="QCM-01"),
        location_or_link="", agenda="")
    resp = _projectinitiation_get(client_a, "pko_list", q=term)
    found = set(_projectinitiation_pks(resp))
    assert found == set(ProjectKickoff.objects.filter(
        tenant=tenant_a, **{f"{field}__icontains": term}).values_list("pk", flat=True))
    assert 0 < len(found) < ProjectKickoff.objects.filter(tenant=tenant_a).count()


# -- pagination (L9) -------------------------------------------------------------------------------

def test_projectinitiation_request_register_paginates_at_the_shared_page_size(
        client_a, tenant_a):
    """``PROJECTINITIATION_PAGE_SIZE + 1`` rows is the smallest data set that proves there IS a
    second page. Reading the size from the conftest rather than hard-coding 15 keeps this honest
    if ``crud_list``'s default ever moves."""
    rows = _projectinitiation_fill_requests(tenant_a, PROJECTINITIATION_PAGE_SIZE + 1)
    first = _projectinitiation_get(client_a, "prq_list")
    assert len(_projectinitiation_pks(first)) == PROJECTINITIATION_PAGE_SIZE
    assert first.context["page_obj"].paginator.num_pages == 2
    assert first.context["page_obj"].paginator.count == len(rows)

    second = _projectinitiation_get(client_a, "prq_list", page="2")
    assert second.status_code == 200
    assert len(_projectinitiation_pks(second)) == 1
    assert second.context["page_obj"].number == 2
    assert set(_projectinitiation_pks(first)) & set(_projectinitiation_pks(second)) == set()


@pytest.mark.parametrize("route", ["prq_list", "prj_list", "pst_list", "pko_list"])
def test_projectinitiation_every_register_clamps_a_page_past_the_end(
        client_a, tenant_a, projectinitiation_project_draft, route):
    """``Paginator.get_page`` clamps rather than raising, so a stale bookmark on page 40 shows the
    LAST page - never an EmptyPage 500 and never a blank table."""
    _projectinitiation_fill_requests(tenant_a, PROJECTINITIATION_PAGE_SIZE + 1)
    _projectinitiation_fill_projects(tenant_a, PROJECTINITIATION_PAGE_SIZE + 1)
    _projectinitiation_fill_stakeholders(projectinitiation_project_draft,
                                         PROJECTINITIATION_PAGE_SIZE + 1)
    _projectinitiation_fill_kickoffs(tenant_a, PROJECTINITIATION_PAGE_SIZE + 1)
    resp = _projectinitiation_get(client_a, route, page="999")
    assert resp.status_code == 200
    page = resp.context["page_obj"]
    assert page.paginator.num_pages >= 2
    assert page.number == page.paginator.num_pages     # clamped to the LAST page, not raised
    assert len(_projectinitiation_pks(resp)) >= 1


@pytest.mark.parametrize("route", ["prq_list", "prj_list", "pst_list", "pko_list"])
@pytest.mark.parametrize("page", ["abc", "0", "-1", "", "NaN", "1e3"])
def test_projectinitiation_every_register_falls_back_to_page_one_on_a_junk_page_param(
        client_a, tenant_a, projectinitiation_project_draft, route, page):
    _projectinitiation_fill_requests(tenant_a, 2)
    _projectinitiation_fill_projects(tenant_a, 2)
    _projectinitiation_fill_stakeholders(projectinitiation_project_draft, 2)
    _projectinitiation_fill_kickoffs(tenant_a, 2)
    resp = _projectinitiation_get(client_a, route, page=page)
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 1
    assert len(_projectinitiation_pks(resp)) >= 2


# ==================================================================================================
# 8. Negative input on the registers (L11) - 200 with the filter SKIPPED, never a 500, never an
#    empty page for a value that could not be a filter in the first place
# ==================================================================================================

_PROJECTINITIATION_REGISTER_MODELS = {
    "prq_list": ProjectRequest, "prj_list": Project,
    "pst_list": ProjectStakeholder, "pko_list": ProjectKickoff,
}

#: Every enum control on every register, with a value that is not one of its CHOICES.
_PROJECTINITIATION_JUNK_ENUMS = (
    ("prq_list", "status"), ("prq_list", "request_type"), ("prq_list", "priority"),
    ("prq_list", "risk_rating"), ("prq_list", "feasibility"), ("prq_list", "decision"),
    ("prj_list", "status"), ("prj_list", "charter_status"), ("prj_list", "methodology"),
    ("pst_list", "stakeholder_type"), ("pst_list", "raci_role"), ("pst_list", "influence"),
    ("pst_list", "interest"),
    ("pko_list", "status"), ("pko_list", "agenda_template"),
)

#: Every int-FK control on every register.
_PROJECTINITIATION_INT_FILTERS = (
    ("prq_list", "org_unit"), ("prj_list", "org_unit"), ("prj_list", "client"),
    ("pst_list", "project"), ("pko_list", "project"),
)


def _projectinitiation_seed_every_register(tenant, project):
    """Three rows in each of the four registers, so "the register did not empty" means something."""
    _projectinitiation_fill_requests(tenant, 3)
    _projectinitiation_fill_projects(tenant, 3)
    _projectinitiation_fill_stakeholders(project, 3)
    _projectinitiation_fill_kickoffs(tenant, 3)


def _projectinitiation_assert_full_register(response, route, tenant):
    """The whole (first page of the) register came back - the junk value was IGNORED."""
    assert response.status_code == 200
    total = _PROJECTINITIATION_REGISTER_MODELS[route].objects.filter(tenant=tenant).count()
    assert len(_projectinitiation_pks(response)) == min(total, PROJECTINITIATION_PAGE_SIZE)


@pytest.mark.parametrize("route,param", _PROJECTINITIATION_JUNK_ENUMS)
@pytest.mark.parametrize("value", ["zzz", "nope", "<script>alert(1)</script>", "2"])
def test_projectinitiation_junk_enum_filter_is_skipped_rather_than_matched(
        client_a, tenant_a, projectinitiation_project_draft, route, param, value):
    """An unrecognised CHOICES value neither raises nor narrows - ``.filter(status="nope")``
    silently matches nothing and EMPTIES the register for a value anyone can type into the
    address bar (a stale bookmark, a renamed choice). ``crud_list``'s enum guard skips it."""
    _projectinitiation_seed_every_register(tenant_a, projectinitiation_project_draft)
    resp = _projectinitiation_get(client_a, route, **{param: value})
    _projectinitiation_assert_full_register(resp, route, tenant_a)


@pytest.mark.parametrize("route,param", _PROJECTINITIATION_INT_FILTERS)
@pytest.mark.parametrize("value", [
    "abc",                       # not decimal at all
    "0",                         # decimal, in range, and still not a pk (AutoField starts at 1)
    "-4",                        # the minus sign fails isdecimal()
    "1.5",
    "NaN",
    "Infinity",
    "\u00b2",                    # U+00B2: isdigit() True, isdecimal() False - int() refuses it
    "999999999999999999999",     # in-decimal but wider than a signed 64-bit column
    "9" * 5000,                  # refused on LENGTH before any arbitrary-precision parse
])
def test_projectinitiation_junk_fk_filter_is_skipped_rather_than_matched(
        client_a, tenant_a, projectinitiation_project_draft, route, param, value):
    _projectinitiation_seed_every_register(tenant_a, projectinitiation_project_draft)
    resp = _projectinitiation_get(client_a, route, **{param: value})
    _projectinitiation_assert_full_register(resp, route, tenant_a)


@pytest.mark.parametrize("route,param", _PROJECTINITIATION_INT_FILTERS)
def test_projectinitiation_a_pk_shaped_fk_filter_that_matches_nothing_returns_nothing(
        client_a, tenant_a, projectinitiation_project_draft, route, param):
    """The deliberate other side of the L11 guard, pinned so nobody "fixes" it into ignoring the
    value: ``999999`` IS a possible primary key, so filtering on it is a real narrowing request
    and an empty register is the correct answer. It is also the same code path that keeps
    ``?project=<another workspace's pk>`` from listing this workspace's rows.
    """
    _projectinitiation_seed_every_register(tenant_a, projectinitiation_project_draft)
    resp = _projectinitiation_get(client_a, route, **{param: "999999"})
    assert resp.status_code == 200
    assert _projectinitiation_pks(resp) == []


@pytest.mark.parametrize("route", ["prq_list", "prj_list", "pst_list", "pko_list"])
def test_projectinitiation_a_whole_query_string_of_junk_still_renders_the_register(
        client_a, tenant_a, projectinitiation_project_draft, route):
    """The realistic shape of a mangled bookmark: several junk params at once."""
    _projectinitiation_seed_every_register(tenant_a, projectinitiation_project_draft)
    resp = _projectinitiation_get(
        client_a, route, status="zzz", page="abc", org_unit="abc", project="abc",
        client="abc", influence="???", agenda_template="none", decision="\u00b2")
    _projectinitiation_assert_full_register(resp, route, tenant_a)


@pytest.mark.parametrize("route", ["prq_list", "prj_list", "pst_list", "pko_list"])
def test_projectinitiation_a_search_term_of_markup_is_escaped_not_executed(
        client_a, tenant_a, projectinitiation_project_draft, route):
    _projectinitiation_seed_every_register(tenant_a, projectinitiation_project_draft)
    resp = _projectinitiation_get(client_a, route, q="<script>alert('x')</script>")
    assert resp.status_code == 200
    body = _projectinitiation_body(resp)
    assert "<script>alert(" not in body
    assert "&lt;script&gt;" in body


@pytest.mark.parametrize("route", ["prq_list", "prj_list", "pst_list", "pko_list"])
def test_projectinitiation_an_empty_filter_value_is_not_a_filter(
        client_a, tenant_a, projectinitiation_project_draft, route):
    """``?status=`` is what a Reset button posts - it must mean "no filter", not
    ``.filter(status="")``."""
    _projectinitiation_seed_every_register(tenant_a, projectinitiation_project_draft)
    resp = _projectinitiation_get(client_a, route, status="", project="", q="   ")
    _projectinitiation_assert_full_register(resp, route, tenant_a)
    assert resp.context["q"] == ""


# ==================================================================================================
# 9. The 15 POST verbs - the happy path, end to end
# ==================================================================================================

def test_projectinitiation_the_whole_initiation_chain_runs_end_to_end(
        client_a, tenant_a, admin_user, projectinitiation_org_unit_a,
        projectinitiation_party_a):
    """Intake -> decision -> project -> charter -> ceremony, driven entirely through the HTTP
    verbs, asserting the stamp and the project-status side effect at every step.

    This is the sub-module's reason to exist: no step here may be reachable except through the
    one before it, and every one of the nine POSTs is the only supported way to move that state.
    """
    demand = _projectinitiation_request(
        tenant_a, title="Chain demand", org_unit=projectinitiation_org_unit_a,
        requester_party=projectinitiation_party_a, assigned_approver=admin_user,
        created_by=admin_user)

    # 1. submit -------------------------------------------------------------------------------
    resp = _projectinitiation_post(client_a, "prq_submit", demand.pk)
    assert resp["Location"] == _projectinitiation_url("prq_detail", demand.pk)
    demand.refresh_from_db()
    assert demand.status == "submitted" and demand.submitted_at is not None
    assert demand.decided_at is None            # submitting is not deciding

    # 2. approve ------------------------------------------------------------------------------
    resp = _projectinitiation_post(client_a, "prq_approve", demand.pk)
    assert _projectinitiation_said(resp, "it can now be converted to a project")
    demand.refresh_from_db()
    assert demand.status == "approved" and demand.decision == "go"
    assert demand.decided_by_id == admin_user.pk and demand.decided_at is not None

    # 3. convert ------------------------------------------------------------------------------
    resp = _projectinitiation_post(client_a, "prq_convert", demand.pk)
    demand.refresh_from_db()
    project = demand.converted_project
    assert project is not None
    assert resp["Location"] == _projectinitiation_url("prj_detail", project.pk)
    assert demand.status == "converted"
    assert project.name == demand.title and project.request_id == demand.pk
    assert project.status == "draft" and project.charter_status == "draft"

    # 4. submit the charter -------------------------------------------------------------------
    resp = _projectinitiation_post(client_a, "prj_submit_charter", project.pk)
    assert resp["Location"] == _projectinitiation_url("prj_detail", project.pk)
    project.refresh_from_db()
    assert project.charter_status == "submitted"
    assert project.status == "draft"            # submitting a charter does not charter a project

    # 5. approve the charter ------------------------------------------------------------------
    resp = _projectinitiation_post(client_a, "prj_approve_charter", project.pk)
    assert _projectinitiation_said(resp, "Charter approved")
    project.refresh_from_db()
    assert project.charter_status == "approved"
    assert project.charter_approved_by_id == admin_user.pk
    assert project.charter_approved_at is not None
    assert project.status == "chartered"         # draft -> chartered, the one status this sets

    # 6. plan the kickoff (through the create view, not the factory) ---------------------------
    meeting = _projectinitiation_minute(days=5)
    resp = _projectinitiation_post(
        client_a, "pko_create",
        data=_projectinitiation_kickoff_payload(
            project, meeting_date=_projectinitiation_local_minute_string(meeting)))
    kickoff = ProjectKickoff.objects.get(project=project)
    assert resp["Location"] == _projectinitiation_url("pko_detail", kickoff.pk)
    assert kickoff.status == "planned"

    # 7. schedule -----------------------------------------------------------------------------
    resp = _projectinitiation_post(client_a, "pko_schedule", kickoff.pk)
    assert _projectinitiation_said(resp, "Kickoff scheduled.")
    kickoff.refresh_from_db()
    project.refresh_from_db()
    assert kickoff.status == "scheduled"
    assert project.status == "chartered"        # booking a meeting does not advance the project

    # 8. mark held ----------------------------------------------------------------------------
    resp = _projectinitiation_post(client_a, "pko_mark_held", kickoff.pk)
    kickoff.refresh_from_db()
    project.refresh_from_db()
    assert kickoff.status == "held"
    assert project.status == "kickoff"           # chartered -> kickoff

    # 9. complete -----------------------------------------------------------------------------
    resp = _projectinitiation_post(client_a, "pko_complete", kickoff.pk)
    assert _projectinitiation_said(resp, "Kickoff completed")
    kickoff.refresh_from_db()
    project.refresh_from_db()
    assert kickoff.status == "completed" and kickoff.completed_at is not None
    assert project.status == "active"            # kickoff -> active, the go-live

    # 10. acknowledge the baseline ------------------------------------------------------------
    resp = _projectinitiation_post(client_a, "pko_mark_baseline_set", kickoff.pk)
    assert _projectinitiation_said(resp, "Baseline acknowledged.")
    kickoff.refresh_from_db()
    assert kickoff.baseline_acknowledged_at is not None
    assert kickoff.baseline_acknowledged_by_id == admin_user.pk

    # The immutable trail carries every step, and `action` never exceeds AuditLog's varchar(10).
    request_actions = {row.action for row in _projectinitiation_audits(demand)}
    assert {"submit", "approve", "convert"} <= request_actions
    kickoff_actions = {row.action for row in _projectinitiation_audits(kickoff)}
    assert {"schedule", "held", "complete", "baseline"} <= kickoff_actions
    assert all(len(action) <= 10 for action in request_actions | kickoff_actions)


# ==================================================================================================
# 10. The gates - every verb refuses every now-forbidden source state, with a message and no write
# ==================================================================================================

_PROJECTINITIATION_ALL_REQUEST_STATUSES = (
    "draft", "submitted", "screening", "assessment", "needs_information", "approved",
    "rejected", "deferred", "converted")


def _projectinitiation_request_in(tenant, status, **overrides):
    """A request parked in ``status``.

    The MODEL has no transition guard - the VIEWS do - which is exactly what lets a gate test put
    a row anywhere in the lifecycle and then assert the verb's refusal. Decided states carry the
    stamps a real decision would have left, so the refusal is tested against a realistic row.
    """
    fields = {"title": f"Request in {status}", "status": status}
    if status in ("approved", "converted"):
        fields.update(decision="go", decided_at=timezone.now() - datetime.timedelta(days=1))
    elif status == "rejected":
        fields.update(decision="no_go", decided_at=timezone.now() - datetime.timedelta(days=1),
                      rejection_reason="Negative ROI.")
    fields.update(overrides)
    return _projectinitiation_request(tenant, **fields)


def _projectinitiation_assert_refused(response, obj, detail_route, before, fragment, level):
    """A refusal is a message + a redirect to the row's own detail page + NO write.

    ``_projectinitiation_unchanged`` covers ``updated_at`` as well, so a guard that returns early
    but has already called ``save()`` fails here rather than passing quietly.
    """
    assert response.status_code == 302
    assert response["Location"] == _projectinitiation_url(detail_route, obj.pk)
    queued = _projectinitiation_messages(response)
    assert any(fragment in message for message in queued), queued
    assert level in _projectinitiation_levels(response)
    _projectinitiation_unchanged(obj, before)


# -- prq_submit ------------------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["draft", "needs_information"])
def test_projectinitiation_request_submit_accepts_a_draft_or_a_send_back(
        client_a, tenant_a, status):
    """Re-submission after a send-back is the NORMAL path, not an error."""
    obj = _projectinitiation_request_in(tenant_a, status)
    resp = _projectinitiation_post(client_a, "prq_submit", obj.pk)
    assert resp["Location"] == _projectinitiation_url("prq_detail", obj.pk)
    assert _projectinitiation_said(resp, "for screening")
    obj.refresh_from_db()
    assert obj.status == "submitted" and obj.submitted_at is not None


@pytest.mark.parametrize("status", [s for s in _PROJECTINITIATION_ALL_REQUEST_STATUSES
                                    if s not in ("draft", "needs_information")])
def test_projectinitiation_request_submit_refuses_every_other_state(client_a, tenant_a, status):
    obj = _projectinitiation_request_in(tenant_a, status)
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prq_submit", obj.pk)
    _projectinitiation_assert_refused(resp, obj, "prq_detail", before, "is already", "info")


def test_projectinitiation_request_submit_logs_the_state_it_actually_came_from(
        client_a, projectinitiation_request_needs_information):
    """A hard-coded ``{"from": "draft"}`` made the immutable trail assert the gate was respected
    in exactly the cases where it was not."""
    obj = projectinitiation_request_needs_information
    _projectinitiation_post(client_a, "prq_submit", obj.pk)
    entry = _projectinitiation_audits(obj, action="submit")[0]
    assert entry.changes["from"] == "needs_information"
    assert entry.changes["to"] == "submitted"
    assert entry.changes["verb"] == "submit"


# -- prq_approve -----------------------------------------------------------------------------------

@pytest.mark.parametrize("status", ["submitted", "screening", "assessment"])
def test_projectinitiation_request_approve_accepts_every_decision_status(
        client_a, tenant_a, admin_user, status):
    """The gate is ``DECISION_STATUSES``, the whole tuple - not a hard-coded ``== "submitted"``."""
    obj = _projectinitiation_request_in(tenant_a, status)
    resp = _projectinitiation_post(client_a, "prq_approve", obj.pk)
    assert _projectinitiation_said(resp, "it can now be converted to a project")
    obj.refresh_from_db()
    assert obj.status == "approved" and obj.decision == "go"
    assert obj.decided_by_id == admin_user.pk and obj.decided_at is not None


@pytest.mark.parametrize("status", [s for s in _PROJECTINITIATION_ALL_REQUEST_STATUSES
                                    if s not in ("submitted", "screening", "assessment")])
def test_projectinitiation_request_approve_refuses_everything_outside_decision_statuses(
        client_a, tenant_a, status):
    """L35, the absent-prerequisite case: a never-submitted draft must not be stampable
    ``decided_at=<now>`` while ``submitted_at`` is still NULL."""
    obj = _projectinitiation_request_in(tenant_a, status)
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prq_approve", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before, "Only a request under review can be approved", "error")


# -- prq_reject ------------------------------------------------------------------------------------

_PROJECTINITIATION_REJECT_REASON = "Negative ROI and three mature vendors already do this."


@pytest.mark.parametrize("status", ["submitted", "screening", "assessment"])
def test_projectinitiation_request_reject_records_the_no_go_and_its_reason(
        client_a, tenant_a, admin_user, status):
    obj = _projectinitiation_request_in(tenant_a, status)
    resp = _projectinitiation_post(client_a, "prq_reject", obj.pk,
                                   data={"reason": _PROJECTINITIATION_REJECT_REASON})
    assert resp["Location"] == _projectinitiation_url("prq_detail", obj.pk)
    obj.refresh_from_db()
    assert obj.status == "rejected" and obj.decision == "no_go"
    assert obj.rejection_reason == _PROJECTINITIATION_REJECT_REASON
    assert obj.decided_by_id == admin_user.pk and obj.decided_at is not None


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_projectinitiation_request_reject_needs_a_stated_reason(
        client_a, projectinitiation_request_submitted, reason):
    """A rejection with no stated reason is the single most common way an intake process loses
    the trust of the people feeding it - and the form check runs BEFORE the status gate."""
    obj = projectinitiation_request_submitted
    before = _projectinitiation_snapshot(obj)
    data = {} if reason is None else {"reason": reason}
    resp = _projectinitiation_post(client_a, "prq_reject", obj.pk, data=data)
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before, "A rejection needs a stated reason.", "error")


def test_projectinitiation_request_reject_checks_the_reason_before_the_status(
        client_a, projectinitiation_request_draft):
    """Order is behaviour: a reason-less POST at a draft answers the reason, not the state."""
    obj = projectinitiation_request_draft
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prq_reject", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before, "A rejection needs a stated reason.", "error")


def test_projectinitiation_request_reject_will_not_re_reject(
        client_a, projectinitiation_request_rejected):
    """No re-stamp: ``decided_by``/``decided_at`` are evidence of who said No-Go and when."""
    obj = projectinitiation_request_rejected
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prq_reject", obj.pk,
                                   data={"reason": "Second thoughts."})
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before, "That request is already rejected.", "info")


def test_projectinitiation_request_reject_sends_a_converted_row_to_the_project(
        client_a, projectinitiation_request_converted):
    obj = projectinitiation_request_converted
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prq_reject", obj.pk,
                                   data={"reason": "Cancelled after all."})
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before, "cannot be rejected", "error")


@pytest.mark.parametrize("status", ["draft", "needs_information", "approved", "deferred"])
def test_projectinitiation_request_reject_refuses_everything_outside_decision_statuses(
        client_a, tenant_a, status):
    """L35 again: a No-Go is a formal DECISION, so it needs something to decide on."""
    obj = _projectinitiation_request_in(tenant_a, status)
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prq_reject", obj.pk,
                                   data={"reason": _PROJECTINITIATION_REJECT_REASON})
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before, "Only a request under review can be rejected", "error")


# -- prq_return_for_information --------------------------------------------------------------------

_PROJECTINITIATION_QUESTION = "Lease break costs for both sites, please."


@pytest.mark.parametrize("status", ["submitted", "screening", "assessment", "deferred"])
def test_projectinitiation_request_return_sends_an_undecided_row_back(
        client_a, tenant_a, status):
    obj = _projectinitiation_request_in(tenant_a, status)
    resp = _projectinitiation_post(client_a, "prq_return_for_information", obj.pk,
                                   data={"reason": _PROJECTINITIATION_QUESTION})
    assert _projectinitiation_said(resp, "back for information")
    obj.refresh_from_db()
    assert obj.status == "needs_information"
    assert obj.information_requested == _PROJECTINITIATION_QUESTION


@pytest.mark.parametrize("status", ["approved", "rejected"])
def test_projectinitiation_request_return_voids_the_decision_it_reverses(
        client_a, tenant_a, admin_user, status):
    """Leaving the stamps on produced a row that rendered "Needs Information" and "No-Go" at
    once, answered ``?decision=no_go`` on the register while sitting with the requester, and -
    from ``approved`` - silently killed a Go, because Convert requires ``status == "approved"``.
    """
    obj = _projectinitiation_request_in(tenant_a, status, decided_by=admin_user)
    resp = _projectinitiation_post(client_a, "prq_return_for_information", obj.pk,
                                   data={"reason": _PROJECTINITIATION_QUESTION})
    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.status == "needs_information"
    assert obj.decision == ""
    assert obj.decided_by_id is None and obj.decided_at is None
    assert obj.rejection_reason == ""
    # The decision it removed goes into the immutable trail FIRST.
    entry = _projectinitiation_audits(obj, action="return")[0]
    assert entry.changes["from"] == status
    assert entry.changes["voided_decision"] in ("go", "no_go")


def test_projectinitiation_request_return_reopens_the_row_for_editing(
        client_a, projectinitiation_request_approved):
    """This is the reopen path: ``prq_edit``'s lock follows ``decided_at``, so clearing the stamp
    is what makes a sent-back request editable again."""
    obj = projectinitiation_request_approved
    assert _projectinitiation_get(client_a, "prq_edit", obj.pk).status_code == 302

    _projectinitiation_post(client_a, "prq_return_for_information", obj.pk,
                            data={"reason": _PROJECTINITIATION_QUESTION})
    assert _projectinitiation_get(client_a, "prq_edit", obj.pk).status_code == 200


@pytest.mark.parametrize("reason", ["", "   ", None])
def test_projectinitiation_request_return_needs_the_question_stated(
        client_a, projectinitiation_request_submitted, reason):
    obj = projectinitiation_request_submitted
    before = _projectinitiation_snapshot(obj)
    data = {} if reason is None else {"reason": reason}
    resp = _projectinitiation_post(client_a, "prq_return_for_information", obj.pk, data=data)
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before, "Say what information is needed.", "error")


def test_projectinitiation_request_return_will_not_send_back_twice(
        client_a, projectinitiation_request_needs_information):
    obj = projectinitiation_request_needs_information
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prq_return_for_information", obj.pk,
                                   data={"reason": "And one more thing."})
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before, "already waiting on information", "info")


@pytest.mark.parametrize("status", ["draft", "converted"])
def test_projectinitiation_request_return_refuses_a_draft_or_a_converted_row(
        client_a, tenant_a, status):
    """A draft was never sent anywhere to be sent back FROM; a converted one is a project now."""
    obj = _projectinitiation_request_in(tenant_a, status)
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prq_return_for_information", obj.pk,
                                   data={"reason": _PROJECTINITIATION_QUESTION})
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before, "cannot be sent back", "error")


# -- prq_convert -----------------------------------------------------------------------------------

def test_projectinitiation_request_convert_mints_the_project_and_redirects_to_it(
        client_a, tenant_a, admin_user, projectinitiation_org_unit_a,
        projectinitiation_party_a):
    """The highest-value verb in the sub-module - and the only one that redirects to a DIFFERENT
    register's detail page, because the user's attention has moved to the project."""
    obj = _projectinitiation_request_in(
        tenant_a, "approved", org_unit=projectinitiation_org_unit_a,
        requester_party=projectinitiation_party_a, assigned_approver=admin_user)
    resp = _projectinitiation_post(client_a, "prq_convert", obj.pk)
    obj.refresh_from_db()
    project = obj.converted_project
    assert project is not None
    assert resp["Location"] == _projectinitiation_url("prj_detail", project.pk)
    assert _projectinitiation_said(resp, f"Created project {project.number} from {obj.number}.")
    assert obj.status == "converted"
    assert project.tenant_id == tenant_a.pk and project.created_by_id == admin_user.pk
    entry = _projectinitiation_audits(obj, action="convert")[0]
    assert entry.changes == {"verb": "convert", "from": obj.number, "to": project.number}


@pytest.mark.parametrize("status", [s for s in _PROJECTINITIATION_ALL_REQUEST_STATUSES
                                    if s != "approved"])
def test_projectinitiation_request_convert_refuses_anything_not_approved(
        client_a, tenant_a, status):
    obj = _projectinitiation_request_in(tenant_a, status)
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prq_convert", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before,
        "Only an approved request can be converted to a project.", "error")
    assert not Project.objects.filter(request=obj).exists()


def test_projectinitiation_request_convert_will_not_mint_a_second_project(
        client_a, projectinitiation_request_converted):
    """Guarded twice - the view checks ``converted_project_id`` and ``convert_to_project()`` does
    a row-level compare-and-swap - because a double-click here would otherwise mint two projects
    for one demand. This drives the VIEW's guard by putting the row back into ``approved`` while
    it still points at its project, which is the only way to reach that branch.
    """
    obj = projectinitiation_request_converted
    ProjectRequest.objects.filter(pk=obj.pk).update(status="approved")
    obj.refresh_from_db()
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prq_convert", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "prq_detail", before, "has already been converted", "info")
    assert Project.objects.filter(request=obj).count() == 1


# -- prj_submit_charter ----------------------------------------------------------------------------

@pytest.mark.parametrize("charter_status", ["draft", "rejected"])
def test_projectinitiation_project_submit_charter_accepts_a_draft_or_rejected_charter(
        client_a, tenant_a, charter_status):
    """``rejected`` is a RESERVED choice no 7.1 verb sets, but it is an accepted SOURCE here so a
    charter an approver sent back can be resubmitted."""
    obj = _projectinitiation_project(tenant_a, name=f"Charter {charter_status}",
                                     code="CHS-01", charter_status=charter_status)
    resp = _projectinitiation_post(client_a, "prj_submit_charter", obj.pk)
    assert resp["Location"] == _projectinitiation_url("prj_detail", obj.pk)
    assert _projectinitiation_said(resp, "submitted for approval")
    obj.refresh_from_db()
    assert obj.charter_status == "submitted"
    assert obj.status == "draft"           # the charter moved; the project did not
    entry = _projectinitiation_audits(obj, action="update")[0]
    assert entry.changes["verb"] == "submit_charter"
    assert entry.changes["from"] == charter_status


@pytest.mark.parametrize("charter_status", ["submitted", "approved"])
def test_projectinitiation_project_submit_charter_refuses_a_charter_already_in_flight(
        client_a, tenant_a, charter_status):
    obj = _projectinitiation_project(tenant_a, name="In flight", code="INF-01",
                                     charter_status=charter_status)
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prj_submit_charter", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "prj_detail", before, "already submitted or approved", "info")


@pytest.mark.parametrize("status", TERMINAL_STATUSES)
def test_projectinitiation_project_submit_charter_refuses_a_terminal_project(
        client_a, tenant_a, status):
    """Gating on ``charter_status`` alone let a cancelled project be walked to a green charter
    while ``status`` stayed cancelled and the success message claimed it was chartered."""
    obj = _projectinitiation_project(tenant_a, name=f"Terminal {status}", code="TRM-01",
                                     status=status, charter_status="draft")
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prj_submit_charter", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "prj_detail", before, "charter cannot be changed", "error")


# -- prj_approve_charter ---------------------------------------------------------------------------

def test_projectinitiation_project_approve_charter_stamps_and_charters_a_draft_project(
        client_a, admin_user, projectinitiation_project_charter_submitted):
    obj = projectinitiation_project_charter_submitted
    resp = _projectinitiation_post(client_a, "prj_approve_charter", obj.pk)
    assert resp["Location"] == _projectinitiation_url("prj_detail", obj.pk)
    obj.refresh_from_db()
    assert obj.charter_status == "approved"
    assert obj.charter_approved_by_id == admin_user.pk
    assert obj.charter_approved_at is not None
    assert obj.status == "chartered"
    entry = _projectinitiation_audits(obj, action="approve")[0]
    assert entry.changes == {"verb": "approve_charter", "from": "submitted", "to": "approved"}


@pytest.mark.parametrize("status", ["kickoff", "active", "on_hold"])
def test_projectinitiation_project_approve_charter_only_walks_a_draft_project_forward(
        client_a, tenant_a, status):
    """``status`` is the KICKOFF verbs' to advance past ``chartered`` - approving a charter on a
    project that is already live must not drag it backwards."""
    obj = _projectinitiation_project(tenant_a, name=f"Live {status}", code="LIV-01",
                                     status=status, charter_status="submitted")
    _projectinitiation_post(client_a, "prj_approve_charter", obj.pk)
    obj.refresh_from_db()
    assert obj.charter_status == "approved"
    assert obj.status == status


def test_projectinitiation_project_approve_charter_will_not_re_stamp(
        client_a, projectinitiation_project_charter_approved):
    """A second click must not overwrite the first approver's name."""
    obj = projectinitiation_project_charter_approved
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prj_approve_charter", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "prj_detail", before, "That charter is already approved.", "info")


@pytest.mark.parametrize("charter_status", ["draft", "rejected"])
def test_projectinitiation_project_approve_charter_refuses_an_unsubmitted_charter(
        client_a, tenant_a, charter_status):
    """L35: the absent prerequisite is refused, not waved through to approval."""
    obj = _projectinitiation_project(tenant_a, name="Unsubmitted", code="UNS-01",
                                     charter_status=charter_status)
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prj_approve_charter", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "prj_detail", before, "Submit the charter before approving it.", "error")


@pytest.mark.parametrize("status", TERMINAL_STATUSES)
def test_projectinitiation_project_approve_charter_refuses_a_terminal_project(
        client_a, tenant_a, status):
    obj = _projectinitiation_project(tenant_a, name=f"Terminal {status}", code="TRA-01",
                                     status=status, charter_status="submitted")
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "prj_approve_charter", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "prj_detail", before, "charter cannot be approved", "error")


# -- prj_delete and the reopen it owes the source request ------------------------------------------

def test_projectinitiation_project_delete_reopens_the_request_it_came_from(
        client_a, projectinitiation_request_converted):
    """``ProjectRequest.converted_project`` is SET_NULL, so a bare delete left the request reading
    "Converted" with no project - a dead state every verb then refuses, making the demand
    permanently unrecoverable. Reopening puts it back in the ready-to-convert queue."""
    source = projectinitiation_request_converted
    project = source.converted_project
    resp = _projectinitiation_post(client_a, "prj_delete", project.pk)
    assert resp["Location"] == _projectinitiation_url("prj_list")
    assert not Project.objects.filter(pk=project.pk).exists()
    source.refresh_from_db()
    assert source.status == "approved"
    assert source.converted_project_id is None
    assert _projectinitiation_said(resp, "was reopened as approved")
    entry = _projectinitiation_audits(source, action="update")[0]
    assert entry.changes["verb"] == "reopen_on_project_delete"


def test_projectinitiation_a_reopened_request_can_be_converted_again(
        client_a, projectinitiation_request_converted):
    """The whole point of the reopen: the demand is recoverable, not stranded."""
    source = projectinitiation_request_converted
    _projectinitiation_post(client_a, "prj_delete", source.converted_project.pk)
    resp = _projectinitiation_post(client_a, "prq_convert", source.pk)
    source.refresh_from_db()
    assert source.status == "converted"
    assert source.converted_project is not None
    assert resp["Location"] == _projectinitiation_url("prj_detail",
                                                      source.converted_project_id)


def test_projectinitiation_project_delete_says_nothing_about_a_request_it_never_had(
        client_a, projectinitiation_project_draft):
    resp = _projectinitiation_post(client_a, "prj_delete", projectinitiation_project_draft.pk)
    assert not _projectinitiation_said(resp, "was reopened as approved")
    assert _projectinitiation_said(resp, "Deleted successfully.")


def test_projectinitiation_project_delete_leaves_a_request_that_is_not_converted_alone(
        client_a, tenant_a, projectinitiation_request_approved):
    """The reopen is keyed on ``request.status == "converted"``, so a project hand-linked to a
    request in some other state must not have its request rewritten to ``approved``."""
    source = projectinitiation_request_approved
    ProjectRequest.objects.filter(pk=source.pk).update(status="deferred")
    project = _projectinitiation_project(tenant_a, name="Hand linked", code="HLK-01",
                                         request=source)
    _projectinitiation_post(client_a, "prj_delete", project.pk)
    source.refresh_from_db()
    assert source.status == "deferred"


# -- pko_schedule ----------------------------------------------------------------------------------

def test_projectinitiation_kickoff_schedule_books_a_planned_dated_ceremony(
        client_a, projectinitiation_kickoff_planned):
    obj = projectinitiation_kickoff_planned
    project_before = _projectinitiation_snapshot(obj.project)
    resp = _projectinitiation_post(client_a, "pko_schedule", obj.pk)
    assert resp["Location"] == _projectinitiation_url("pko_detail", obj.pk)
    assert _projectinitiation_said(resp, "Kickoff scheduled.")
    obj.refresh_from_db()
    assert obj.status == "scheduled"
    # Login-only ON PURPOSE: booking a meeting is not advancing the project, and it does not.
    _projectinitiation_unchanged(obj.project, project_before)


def test_projectinitiation_kickoff_schedule_needs_a_meeting_date(
        client_a, projectinitiation_kickoff_undated):
    """L35: without the date this books a ceremony nobody can attend - and ``pko_mark_held``
    then advances the PROJECT off the back of it."""
    obj = projectinitiation_kickoff_undated
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "pko_schedule", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "pko_detail", before,
        "Set a meeting date before scheduling the kickoff.", "error")


@pytest.mark.parametrize("fixture", ["projectinitiation_kickoff_scheduled",
                                     "projectinitiation_kickoff_held",
                                     "projectinitiation_kickoff_completed"])
def test_projectinitiation_kickoff_schedule_refuses_a_ceremony_past_that_point(
        client_a, request, fixture):
    obj = request.getfixturevalue(fixture)
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "pko_schedule", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "pko_detail", before, "already scheduled or past that point", "info")


# -- pko_mark_held ---------------------------------------------------------------------------------

def test_projectinitiation_kickoff_mark_held_advances_the_project_to_kickoff(
        client_a, projectinitiation_kickoff_scheduled):
    obj = projectinitiation_kickoff_scheduled
    resp = _projectinitiation_post(client_a, "pko_mark_held", obj.pk)
    assert _projectinitiation_said(resp, "Kickoff marked as held.")
    obj.refresh_from_db()
    project = Project.objects.get(pk=obj.project_id)
    assert obj.status == "held"
    assert project.status == "kickoff"      # chartered -> kickoff
    assert _projectinitiation_audits(obj, action="held")


def test_projectinitiation_kickoff_mark_held_refuses_a_planned_ceremony(
        client_a, projectinitiation_kickoff_planned):
    """The regression guard: ``planned`` is deliberately NOT an allowed source, because accepting
    it would skip ``pko_schedule`` and with it the "set a meeting date first" requirement - a
    ceremony marked held with ``meeting_date`` NULL that also advances the PROJECT."""
    obj = projectinitiation_kickoff_planned
    before = _projectinitiation_snapshot(obj)
    project_before = _projectinitiation_snapshot(obj.project)
    resp = _projectinitiation_post(client_a, "pko_mark_held", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "pko_detail", before, "Schedule the kickoff before marking it held.", "error")
    _projectinitiation_unchanged(obj.project, project_before)


@pytest.mark.parametrize("fixture", ["projectinitiation_kickoff_held",
                                     "projectinitiation_kickoff_completed"])
def test_projectinitiation_kickoff_mark_held_refuses_a_ceremony_already_held(
        client_a, request, fixture):
    obj = request.getfixturevalue(fixture)
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "pko_mark_held", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "pko_detail", before, "already been held", "info")


def test_projectinitiation_kickoff_mark_held_does_not_drag_a_live_project_backwards(
        client_a, tenant_a, admin_user):
    """Only ``draft``/``chartered`` walk forward - an ``on_hold`` project keeps its status."""
    project = _projectinitiation_project(tenant_a, name="Paused programme", code="PAU-01",
                                         status="on_hold", charter_status="approved",
                                         created_by=admin_user)
    obj = _projectinitiation_kickoff(project, status="scheduled")
    _projectinitiation_post(client_a, "pko_mark_held", obj.pk)
    project.refresh_from_db()
    assert project.status == "on_hold"


# -- pko_complete (fix C2 - the two-gate verb) -----------------------------------------------------

def test_projectinitiation_kickoff_complete_takes_the_project_live(
        client_a, projectinitiation_kickoff_ready_to_complete):
    obj = projectinitiation_kickoff_ready_to_complete
    resp = _projectinitiation_post(client_a, "pko_complete", obj.pk)
    assert _projectinitiation_said(resp, "Kickoff completed")
    obj.refresh_from_db()
    project = Project.objects.get(pk=obj.project_id)
    assert obj.status == "completed" and obj.completed_at is not None
    assert project.status == "active"


def test_projectinitiation_kickoff_complete_refuses_an_unapproved_charter(
        client_a, projectinitiation_kickoff_held):
    """**Fix C2, and the sharpest L35 case in 7.1.** The kickoff prerequisite is met and the
    CHARTER one is not. Without this gate an ordinary member could go create-project ->
    create-kickoff -> Complete and land an ``active`` project on a draft charter, routing straight
    around the ``@tenant_admin_required`` on ``prj_approve_charter``.
    """
    obj = projectinitiation_kickoff_held
    assert obj.status == "held" and obj.project.charter_status != "approved"
    before = _projectinitiation_snapshot(obj)
    project_before = _projectinitiation_snapshot(obj.project)
    resp = _projectinitiation_post(client_a, "pko_complete", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "pko_detail", before,
        "Approve the charter before completing the kickoff", "error")
    # The project must not have gone live either - the refusal has to be total.
    _projectinitiation_unchanged(obj.project, project_before)
    assert Project.objects.get(pk=obj.project_id).status != "active"


def test_projectinitiation_kickoff_complete_succeeds_once_the_charter_is_approved(
        client_a, projectinitiation_kickoff_held):
    """The other half of C2: the gate is a prerequisite, not a permanent block. Approving the
    charter through its own admin-gated verb unblocks the same POST that just bounced."""
    obj = projectinitiation_kickoff_held
    project = obj.project
    assert _projectinitiation_post(client_a, "pko_complete", obj.pk).status_code == 302
    obj.refresh_from_db()
    assert obj.status == "held"

    _projectinitiation_post(client_a, "prj_submit_charter", project.pk)
    _projectinitiation_post(client_a, "prj_approve_charter", project.pk)
    _projectinitiation_post(client_a, "pko_complete", obj.pk)
    obj.refresh_from_db()
    project.refresh_from_db()
    assert obj.status == "completed"
    assert project.status == "active"


@pytest.mark.parametrize("fixture", ["projectinitiation_kickoff_planned",
                                     "projectinitiation_kickoff_scheduled"])
def test_projectinitiation_kickoff_complete_refuses_a_ceremony_never_held(
        client_a, request, fixture):
    obj = request.getfixturevalue(fixture)
    before = _projectinitiation_snapshot(obj)
    project_before = _projectinitiation_snapshot(obj.project)
    resp = _projectinitiation_post(client_a, "pko_complete", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "pko_detail", before, "Hold the kickoff before completing it.", "error")
    _projectinitiation_unchanged(obj.project, project_before)


def test_projectinitiation_kickoff_complete_refuses_a_ceremony_already_completed(
        client_a, projectinitiation_kickoff_completed):
    obj = projectinitiation_kickoff_completed
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "pko_complete", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "pko_detail", before, "already completed", "info")


# -- pko_mark_baseline_set -------------------------------------------------------------------------

@pytest.mark.parametrize("fixture", ["projectinitiation_kickoff_held",
                                     "projectinitiation_kickoff_completed"])
def test_projectinitiation_kickoff_baseline_stamps_who_acknowledged_and_when(
        client_a, request, admin_user, fixture):
    obj = request.getfixturevalue(fixture)
    resp = _projectinitiation_post(client_a, "pko_mark_baseline_set", obj.pk)
    assert resp["Location"] == _projectinitiation_url("pko_detail", obj.pk)
    assert _projectinitiation_said(resp, "Baseline acknowledged.")
    obj.refresh_from_db()
    assert obj.baseline_acknowledged_at is not None
    assert obj.baseline_acknowledged_by_id == admin_user.pk
    assert obj.status in ("held", "completed")     # the stamp does not move the ceremony on


def test_projectinitiation_kickoff_baseline_will_not_re_stamp(
        client_a, projectinitiation_kickoff_baselined):
    """The acknowledgement is evidence of who accepted the baseline and when, so a second click
    must not overwrite the first."""
    obj = projectinitiation_kickoff_baselined
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "pko_mark_baseline_set", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "pko_detail", before, "was already acknowledged", "info")


@pytest.mark.parametrize("fixture", ["projectinitiation_kickoff_planned",
                                     "projectinitiation_kickoff_scheduled"])
def test_projectinitiation_kickoff_baseline_refuses_a_ceremony_that_has_not_happened(
        client_a, request, fixture):
    """``scheduled`` is refused as well as ``planned``, or the guard contradicts its own message:
    a merely scheduled ceremony has not happened, and this stamps who accepted the baseline AT
    it."""
    obj = request.getfixturevalue(fixture)
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_post(client_a, "pko_mark_baseline_set", obj.pk)
    _projectinitiation_assert_refused(
        resp, obj, "pko_detail", before,
        "Hold the kickoff before acknowledging the baseline.", "error")


# ==================================================================================================
# 11. Replay - every verb posted twice, and the second one must change nothing
# ==================================================================================================

#: ``(verb, a fixture in the verb's ACCEPTED state, needs a reason, the SECOND response's target)``
_PROJECTINITIATION_REPLAY_VERBS = (
    ("prq_submit", "projectinitiation_request_draft", False, "prq_detail"),
    ("prq_approve", "projectinitiation_request_submitted", False, "prq_detail"),
    ("prq_reject", "projectinitiation_request_submitted", True, "prq_detail"),
    ("prq_return_for_information", "projectinitiation_request_submitted", True, "prq_detail"),
    ("prq_convert", "projectinitiation_request_approved", False, "prq_detail"),
    ("prj_submit_charter", "projectinitiation_project_draft", False, "prj_detail"),
    ("prj_approve_charter", "projectinitiation_project_charter_submitted", False, "prj_detail"),
    ("pko_schedule", "projectinitiation_kickoff_planned", False, "pko_detail"),
    ("pko_mark_held", "projectinitiation_kickoff_scheduled", False, "pko_detail"),
    ("pko_complete", "projectinitiation_kickoff_ready_to_complete", False, "pko_detail"),
    ("pko_mark_baseline_set", "projectinitiation_kickoff_held", False, "pko_detail"),
)


@pytest.mark.parametrize("verb,fixture,needs_reason,detail_route",
                         _PROJECTINITIATION_REPLAY_VERBS)
def test_projectinitiation_replaying_a_verb_is_refused_with_zero_field_deltas(
        client_a, request, verb, fixture, needs_reason, detail_route):
    """The double-submit shape: a slow response, a second click, two identical POSTs.

    The second must be refused CLEANLY - a message, a redirect, and not one column different,
    ``updated_at`` included. Anything else means the guard returns early but has already written.
    """
    obj = request.getfixturevalue(fixture)
    data = {"reason": "Stated for the record."} if needs_reason else {}

    first = _projectinitiation_post(client_a, verb, obj.pk, data=data)
    assert first.status_code == 302
    settled = _projectinitiation_snapshot(obj)

    second = _projectinitiation_post(client_a, verb, obj.pk, data=data)
    assert second.status_code == 302
    assert second["Location"] == _projectinitiation_url(detail_route, obj.pk)
    assert _projectinitiation_messages(second), "a refusal must say why"
    assert _projectinitiation_deltas(settled, _projectinitiation_snapshot(obj)) == {}


def test_projectinitiation_double_clicking_convert_mints_exactly_one_project(
        client_a, projectinitiation_request_approved):
    obj = projectinitiation_request_approved
    _projectinitiation_post(client_a, "prq_convert", obj.pk)
    _projectinitiation_post(client_a, "prq_convert", obj.pk)
    assert Project.objects.filter(request=obj).count() == 1


@pytest.mark.parametrize("verb,fixture", [
    ("prq_delete", "projectinitiation_request_draft"),
    ("prj_delete", "projectinitiation_project_draft"),
    ("pst_delete", "projectinitiation_stakeholder_a"),
    ("pko_delete", "projectinitiation_kickoff_planned"),
])
def test_projectinitiation_replaying_a_delete_is_a_clean_404(
        client_a, request, verb, fixture):
    """The same claim for a row that is gone: ``crud_delete``'s ``get_object_or_404`` answers 404
    rather than 500ing on a missing pk."""
    obj = request.getfixturevalue(fixture)
    assert _projectinitiation_post(client_a, verb, obj.pk).status_code == 302
    assert _projectinitiation_post(client_a, verb, obj.pk).status_code == 404


# ==================================================================================================
# 12. Method discipline - all 15 verbs are POST-only
# ==================================================================================================

_PROJECTINITIATION_VERB_FIXTURES = {
    "prq_submit": "projectinitiation_request_draft",
    "prq_approve": "projectinitiation_request_submitted",
    "prq_reject": "projectinitiation_request_submitted",
    "prq_return_for_information": "projectinitiation_request_submitted",
    "prq_convert": "projectinitiation_request_approved",
    "prq_delete": "projectinitiation_request_draft",
    "prj_submit_charter": "projectinitiation_project_draft",
    "prj_approve_charter": "projectinitiation_project_charter_submitted",
    "prj_delete": "projectinitiation_project_draft",
    "pst_delete": "projectinitiation_stakeholder_a",
    "pko_schedule": "projectinitiation_kickoff_planned",
    "pko_mark_held": "projectinitiation_kickoff_scheduled",
    "pko_complete": "projectinitiation_kickoff_ready_to_complete",
    "pko_mark_baseline_set": "projectinitiation_kickoff_held",
    "pko_delete": "projectinitiation_kickoff_planned",
}


def test_projectinitiation_every_post_verb_is_covered_by_the_method_matrix():
    assert set(_PROJECTINITIATION_VERB_FIXTURES) == set(_PROJECTINITIATION_POST_VERBS)
    assert len(_PROJECTINITIATION_POST_VERBS) == 15


@pytest.mark.parametrize("verb", _PROJECTINITIATION_POST_VERBS)
def test_projectinitiation_every_verb_refuses_a_get(client_a, request, verb):
    """A tenant ADMIN clears every decorator stacked above ``@require_POST``, so 405 here is the
    method gate answering and not a role gate masking it. A verb reachable by GET is a verb a
    crawler, a prefetcher or a browser preview can fire."""
    obj = request.getfixturevalue(_PROJECTINITIATION_VERB_FIXTURES[verb])
    before = _projectinitiation_snapshot(obj)
    resp = _projectinitiation_get(client_a, verb, obj.pk)
    assert resp.status_code == 405
    _projectinitiation_unchanged(obj, before)


# ==================================================================================================
# 13. The `attendee_total` annotation (fix I16), the ordering it nearly cost, and the budgets
# ==================================================================================================

def test_projectinitiation_kickoff_register_annotates_attendee_total_not_attendee_count(
        client_a, projectinitiation_kickoff_with_attendees):
    """``attendee_count`` is a PROPERTY - a data descriptor - so annotating over the name raises
    "AttributeError: can't set attribute". The register annotates ``attendee_total`` instead, and
    the two must agree: three stakeholders on the project, exactly two attending.
    """
    resp = _projectinitiation_get(client_a, "pko_list")
    row = next(row for row in resp.context["object_list"]
               if row.pk == projectinitiation_kickoff_with_attendees.pk)
    assert row.attendee_total == 2
    assert row.attendee_count == 2          # the property still works and still agrees
    assert isinstance(type(row).attendee_count, property)
    assert "attendee_total" in row.__dict__  # it really is an annotation on the instance


def test_projectinitiation_kickoff_register_counts_zero_attendees_as_zero_not_null(
        client_a, projectinitiation_kickoff_planned):
    """A filtered ``Count`` over a LEFT JOIN must read 0, not None - the template prints it."""
    resp = _projectinitiation_get(client_a, "pko_list")
    row = next(row for row in resp.context["object_list"]
               if row.pk == projectinitiation_kickoff_planned.pk)
    assert row.attendee_total == 0
    assert ">0</td>" in _projectinitiation_body(resp)


def test_projectinitiation_project_detail_annotates_attendee_total_on_its_kickoff_block(
        client_a, projectinitiation_kickoff_with_attendees):
    """The same annotation, for the same reason: the charter page's Attending column would
    otherwise fire one COUNT per kickoff row."""
    project = projectinitiation_kickoff_with_attendees.project
    resp = _projectinitiation_get(client_a, "prj_detail", project.pk)
    row = list(resp.context["kickoffs"])[0]
    assert row.attendee_total == 2 == row.attendee_count


def test_projectinitiation_kickoff_register_stays_newest_first_under_the_aggregate(
        client_a, tenant_a, member_user):
    """**The one that breaks silently.** An aggregate over a multi-valued relation makes Django
    drop ``Meta.ordering`` entirely - no ORDER BY is emitted at all - so without the explicit
    ``.order_by("-created_at", "-id")`` the register flips out of newest-first while every status
    and content assertion still passes.
    """
    kickoffs = _projectinitiation_fill_kickoffs(tenant_a, 5)
    # Give the aggregate something to chew on, so this is not testing the trivial LEFT JOIN.
    _projectinitiation_stakeholder(kickoffs[0].project, raci_scope="a", attending_kickoff=True)
    _projectinitiation_stakeholder(kickoffs[3].project, user=member_user, raci_scope="b",
                                   attending_kickoff=True)
    resp = _projectinitiation_get(client_a, "pko_list")
    assert _projectinitiation_pks(resp) == [row.pk for row in reversed(kickoffs)]


@pytest.mark.parametrize("route", ["prq_list", "prj_list", "pst_list", "pko_list"])
def test_projectinitiation_every_register_orders_newest_first(
        client_a, tenant_a, projectinitiation_project_draft, route):
    """``Meta.ordering = ["-created_at", "-id"]`` on all four - and ``pst_list`` deliberately
    overrides it with the influence ranking, so it is excluded from the equality below."""
    rows = {
        "prq_list": lambda: _projectinitiation_fill_requests(tenant_a, 4),
        "prj_list": lambda: _projectinitiation_fill_projects(tenant_a, 4),
        "pst_list": lambda: _projectinitiation_fill_stakeholders(
            projectinitiation_project_draft, 4),
        "pko_list": lambda: _projectinitiation_fill_kickoffs(tenant_a, 4),
    }[route]()
    resp = _projectinitiation_get(client_a, route)
    mine = {row.pk for row in rows}
    # A subsequence, not the whole page: the fixtures this test pulls in add rows of their own to
    # some of these registers, and their relative order is what is under test.
    seen = [pk for pk in _projectinitiation_pks(resp) if pk in mine]
    if route == "pst_list":
        # Equal influence, so the tie-break is the annotation's secondary key: ``id`` ascending.
        assert seen == [row.pk for row in rows]
    else:
        assert seen == [row.pk for row in reversed(rows)]


def _projectinitiation_measure(client, route, **params):
    """The number of queries one GET of ``route`` costs, measured rather than guessed.

    Pinning a MEASURED baseline instead of a magic constant is what makes the flatness claim a
    claim about the row count and not about the current session/auth plumbing.
    """
    with CaptureQueriesContext(connection) as ctx:
        response = _projectinitiation_get(client, route, **params)
    assert response.status_code == 200
    return len(ctx.captured_queries), response


def test_projectinitiation_kickoff_register_cost_is_flat_in_the_row_count(
        client_a, tenant_a, member_user, django_assert_max_num_queries):
    """The N+1 the annotation exists to kill: ``attendee_count`` is one COUNT per row (25 queries
    on a full page before fix I16), and ``__str__``/the Project column is another FK hop per row.

    Measured at 2 rows, then asserted UNCHANGED at a full 15-row page.
    """
    kickoffs = _projectinitiation_fill_kickoffs(tenant_a, 2)
    _projectinitiation_stakeholder(kickoffs[0].project, raci_scope="a", attending_kickoff=True)
    _projectinitiation_get(client_a, "pko_list")          # warm the session / auth caches
    baseline, resp = _projectinitiation_measure(client_a, "pko_list")
    assert len(_projectinitiation_pks(resp)) == 2

    # Exactly one full page, so the attendee-bearing rows are all still on it.
    more = _projectinitiation_fill_kickoffs(tenant_a, PROJECTINITIATION_PAGE_SIZE - 2)
    for kickoff in more[:4]:
        _projectinitiation_stakeholder(kickoff.project, user=member_user,
                                       raci_scope="attending", attending_kickoff=True)
    with django_assert_max_num_queries(baseline):
        resp = _projectinitiation_get(client_a, "pko_list")
    assert len(_projectinitiation_pks(resp)) == PROJECTINITIATION_PAGE_SIZE
    assert sum(row.attendee_total for row in resp.context["object_list"]) == 5


@pytest.mark.parametrize("route,fill", [
    ("prq_list", "requests"), ("prj_list", "projects"), ("pst_list", "stakeholders"),
])
def test_projectinitiation_register_cost_is_flat_in_the_row_count(
        client_a, tenant_a, django_assert_max_num_queries, route, fill):
    """``prq_list`` has NO ``select_related`` - deliberate, the register renders no joined column
    - so this is the test that would catch a template edit adding one. ``prj_list`` and
    ``pst_list`` do join, and this is what proves the joins absorb the per-row hops.

    The stakeholder host project is built here rather than pulled from a fixture: a fixture row
    would land in ``prj_list`` too and make its row count off by one.
    """
    host = (_projectinitiation_project(tenant_a, name="Stakeholder host", code="SKH-99")
            if fill == "stakeholders" else None)
    filler = {
        "requests": lambda count: _projectinitiation_fill_requests(tenant_a, count),
        "projects": lambda count: _projectinitiation_fill_projects(tenant_a, count),
        "stakeholders": lambda count: _projectinitiation_fill_stakeholders(host, count),
    }[fill]
    filler(2)
    _projectinitiation_get(client_a, route)               # warm the session / auth caches
    baseline, resp = _projectinitiation_measure(client_a, route)
    assert len(_projectinitiation_pks(resp)) == 2

    filler(PROJECTINITIATION_PAGE_SIZE - 1)
    with django_assert_max_num_queries(baseline):
        resp = _projectinitiation_get(client_a, route)
    assert len(_projectinitiation_pks(resp)) == PROJECTINITIATION_PAGE_SIZE


def test_projectinitiation_project_detail_cost_is_flat_in_its_stakeholder_count(
        client_a, projectinitiation_project_draft, projectinitiation_kickoff_planned,
        django_assert_max_num_queries):
    """Every stakeholder row prints ``party.name`` or ``user.username`` - three FK hops that the
    ``select_related("party", "user")`` absorbs, and the kickoff block's Attending column is the
    annotation rather than a COUNT per row."""
    project = projectinitiation_project_draft
    _projectinitiation_fill_stakeholders(project, 2)
    _projectinitiation_get(client_a, "prj_detail", project.pk)   # warm the caches
    with CaptureQueriesContext(connection) as ctx:
        _projectinitiation_get(client_a, "prj_detail", project.pk)
    baseline = len(ctx.captured_queries)

    _projectinitiation_fill_stakeholders(project, 20)
    with django_assert_max_num_queries(baseline):
        resp = _projectinitiation_get(client_a, "prj_detail", project.pk)
    assert len(list(resp.context["stakeholders"])) == 22


def test_projectinitiation_kickoff_detail_cost_is_flat_in_its_attendee_count(
        client_a, projectinitiation_kickoff_planned, django_assert_max_num_queries):
    """``attending`` is the very queryset the page iterates, and the template reads its length off
    the cache rather than firing ``obj.attendee_count`` for the same rows a second time."""
    project = projectinitiation_kickoff_planned.project
    _projectinitiation_fill_stakeholders(project, 2, attending_kickoff=True)
    _projectinitiation_get(client_a, "pko_detail", projectinitiation_kickoff_planned.pk)
    with CaptureQueriesContext(connection) as ctx:
        _projectinitiation_get(client_a, "pko_detail", projectinitiation_kickoff_planned.pk)
    baseline = len(ctx.captured_queries)

    _projectinitiation_fill_stakeholders(project, 20, attending_kickoff=True)
    with django_assert_max_num_queries(baseline):
        resp = _projectinitiation_get(client_a, "pko_detail",
                                      projectinitiation_kickoff_planned.pk)
    assert len(list(resp.context["attending"])) == 22


# ==================================================================================================
# 14. Messages and redirects - every verb answers, and none of them renders a page
# ==================================================================================================

@pytest.mark.parametrize("verb,fixture,needs_reason,detail_route",
                         _PROJECTINITIATION_REPLAY_VERBS)
def test_projectinitiation_every_accepted_verb_reports_success_and_redirects(
        client_a, request, verb, fixture, needs_reason, detail_route):
    """POST-redirect-GET on all eleven state verbs: a verb that RENDERS leaves the POST in the
    browser's history and re-fires on refresh."""
    obj = request.getfixturevalue(fixture)
    data = {"reason": "Stated for the record."} if needs_reason else {}
    resp = _projectinitiation_post(client_a, verb, obj.pk, data=data)
    assert resp.status_code == 302
    assert "success" in _projectinitiation_levels(resp)
    assert resp["Location"].startswith("/projects/")


@pytest.mark.parametrize("verb,fixture,list_route", [
    ("prq_delete", "projectinitiation_request_draft", "prq_list"),
    ("prj_delete", "projectinitiation_project_draft", "prj_list"),
    ("pst_delete", "projectinitiation_stakeholder_a", "pst_list"),
    ("pko_delete", "projectinitiation_kickoff_planned", "pko_list"),
])
def test_projectinitiation_every_delete_reports_success_and_returns_to_its_register(
        client_a, request, verb, fixture, list_route):
    """A delete goes back to the REGISTER, not to a detail page for a row that no longer exists."""
    obj = request.getfixturevalue(fixture)
    resp = _projectinitiation_post(client_a, verb, obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _projectinitiation_url(list_route)
    assert "success" in _projectinitiation_levels(resp)


@pytest.mark.parametrize("verb,fixture,needs_reason,detail_route",
                         _PROJECTINITIATION_REPLAY_VERBS)
def test_projectinitiation_a_verbs_success_message_survives_the_redirect(
        client_a, request, verb, fixture, needs_reason, detail_route):
    """Followed to the end, the message renders on the landing page - the user is told what
    happened rather than being dropped on a page that silently looks the same."""
    obj = request.getfixturevalue(fixture)
    data = {"reason": "Stated for the record."} if needs_reason else {}
    resp = _projectinitiation_post(client_a, verb, obj.pk, data=data, follow=True)
    assert resp.status_code == 200
    assert len(resp.redirect_chain) == 1
    assert [str(message) for message in resp.context["messages"]]


def test_projectinitiation_a_refused_verb_message_survives_the_redirect(
        client_a, projectinitiation_kickoff_held):
    """The C2 refusal, followed all the way: the user lands back on the kickoff and is told to
    approve the charter first - not left wondering why nothing happened."""
    resp = _projectinitiation_post(client_a, "pko_complete",
                                   projectinitiation_kickoff_held.pk, follow=True)
    assert resp.status_code == 200
    assert any("Approve the charter before completing the kickoff" in str(message)
               for message in resp.context["messages"])


# ==================================================================================================
# 15. `is_overdue` on screen - a DERIVED flag, so a template typo shows nothing at 200
# ==================================================================================================

def test_projectinitiation_project_detail_flags_an_overdue_project(
        client_a, projectinitiation_project_overdue):
    """``end_date`` five days past and ``status="active"``."""
    resp = _projectinitiation_get(client_a, "prj_detail",
                                  projectinitiation_project_overdue.pk)
    assert resp.context["obj"].is_overdue is True
    assert "Overdue" in _projectinitiation_body(resp)


def test_projectinitiation_project_detail_does_not_flag_a_project_due_today(
        client_a, tenant_a):
    """The boundary, on the SAME basis the property uses: ``is_overdue`` is ``end_date <
    localdate()``, so a project due TODAY is not overdue. Deriving today from
    ``timezone.localdate()`` rather than ``datetime.date.today()`` is what keeps this from
    flaking for the hours either side of local midnight (L16).
    """
    today = _projectinitiation_today()
    obj = _projectinitiation_project(tenant_a, name="Due today", code="DUE-01",
                                     status="active", end_date=today)
    resp = _projectinitiation_get(client_a, "prj_detail", obj.pk)
    assert resp.context["obj"].is_overdue is False
    assert "Overdue" not in _projectinitiation_body(resp)


@pytest.mark.parametrize("status", TERMINAL_STATUSES)
def test_projectinitiation_project_detail_does_not_flag_a_finished_project(
        client_a, tenant_a, status):
    """A completed or cancelled project cannot be late - the work stopped."""
    today = _projectinitiation_today()
    obj = _projectinitiation_project(
        tenant_a, name=f"Finished {status}", code="FIN-01", status=status,
        end_date=today - datetime.timedelta(days=30))
    resp = _projectinitiation_get(client_a, "prj_detail", obj.pk)
    assert resp.context["obj"].is_overdue is False
    assert "Overdue" not in _projectinitiation_body(resp)


def test_projectinitiation_kickoff_complete_does_not_drag_a_paused_project_live(
        client_a, tenant_a, admin_user):
    """Only ``draft``/``chartered``/``kickoff`` walk forward to ``active``. A project deliberately
    put ``on_hold`` after its ceremony keeps that status when the kickoff is closed out.

    NOTE, and reported rather than asserted: the success message on this path still reads
    "... is now active", which is not what happened. The STATUS behaviour below is correct and is
    what this test pins; the message wording is a product defect (see the lane report) of exactly
    the class the review pass fixed for the charter verbs, and asserting the wrong wording here
    would cement it.
    """
    project = _projectinitiation_project(
        tenant_a, name="Paused after kickoff", code="PAK-01", status="on_hold",
        charter_status="approved", charter_approved_by=admin_user,
        charter_approved_at=timezone.now() - datetime.timedelta(days=3), created_by=admin_user)
    kickoff = _projectinitiation_kickoff(project, status="held")
    resp = _projectinitiation_post(client_a, "pko_complete", kickoff.pk)
    assert resp.status_code == 302
    kickoff.refresh_from_db()
    project.refresh_from_db()
    assert kickoff.status == "completed" and kickoff.completed_at is not None
    assert project.status == "on_hold"
