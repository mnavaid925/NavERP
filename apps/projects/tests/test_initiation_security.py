"""Projects 7.1 Project Initiation & Charter - SECURITY tests.

The fourth and last 7.1 lane. ``test_initiation_models.py`` owns the invariants,
``test_initiation_forms.py`` the field lists and validation, ``test_initiation_views.py`` the
functional HTTP layer (happy paths, filters, state gates, replay, query budgets) - every request
in that lane is made by a tenant ADMIN of the row's OWN workspace, so the only thing that can
refuse a verb there is its own state gate. This file owns the three questions those three never
ask: **who may reach it, whose workspace is it, and what does the answer disclose.**

What it locks down, finding by finding:

* **The login wall.** All 32 routes, GET and POST, redirect an anonymous caller to ``/login/``
  before any database work - and, more to the point, before any write. The 15 verbs are re-posted
  against REAL tenant-A rows so the redirect is proved to happen ahead of the mutation, not just
  ahead of the render.
* **The role gate, asserted as a MATRIX (I5 / I13 / I19).** Exactly eight verbs are
  ``@tenant_admin_required``; the other seven are login-only. A member POSTs all fifteen and the
  403 set must be exactly those eight. That split is deliberate house style, so it is pinned
  rather than assumed: a peer session that gates or ungates a verb fails HERE, as a visible
  decision, instead of silently in production. The eight refusals leave ZERO field deltas, and an
  admin control proves each 403 is about the ROLE and not about the row's state.
* **Cross-tenant IDOR - the highest-value class.** Every detail/edit GET and every delete/verb
  POST on a tenant-B pk answers **404** (never 403, which would confirm the row exists, and never
  500), with B's row byte-for-byte unchanged. A's registers never list B's rows, A's search never
  reaches B's text, and a foreign pk in an FK filter returns an empty register rather than the
  whole one.
  **403 vs 404 depends on the ACTOR** (``apps/core/decorators.py:16``): the role check runs
  *before* ``get_object_or_404``, so on an admin-gated verb a tenant-A member gets 403 and a
  tenant-A admin gets 404. Every IDOR-404 assertion below therefore uses ``client_a`` (an admin),
  and the member-403 assertions never claim a 404. Both halves are asserted explicitly.
* **Cross-tenant FK smuggling at the ROUTE (C2-adjacent, I1).** The forms lane pins this at the
  form layer; this lane posts a valid own-tenant create/edit form carrying another workspace's
  ``project`` / ``party`` / ``user`` / ``org_unit`` / ``client`` / ``charter_document`` /
  ``requester_party`` / ``assigned_approver`` / ``source_opportunity`` pk. Every one is rejected
  as a FIELD ERROR and nothing lands. Each is paired with a **same-tenant control that must
  succeed**, so a test that passes because the payload was malformed cannot hide here.
  Note ``_reject_foreign``'s "belongs to another workspace" wording is unreachable this way -
  ``TenantModelForm`` narrows the queryset first and Django's own "Select a valid choice" wins -
  so these assert that the FIELD HAS AN ERROR, never the sentence.
* **Mass assignment at the route (L20 / L22, I3).** ``tenant`` ``number`` ``status`` ``decision``
  ``decided_by`` ``decided_at`` ``submitted_at`` ``converted_project`` ``created_by``
  ``charter_status`` ``charter_approved_by`` ``charter_approved_at`` ``completed_at``
  ``baseline_acknowledged_by`` ``baseline_acknowledged_at`` ``id``/``pk``, and the three evidence
  fields the fix pass added to ``ProjectRequestForm.Meta.exclude`` (``rejection_reason``,
  ``information_requested``, ``decision_notes``) are POSTed directly at create AND at edit on all
  four models, and every one is ignored.
* **The post-decision / post-approval edit locks (I2 / I3).** You cannot forge the signature, but
  you could change what it signs. A member cannot rewrite an approved charter or an approved
  business case through the ungated edit route, and ``charter_approved_by``/``_at`` survive the
  attempt intact.
* **The ``tenant=None`` user (I1).** The guard now sits on the FIRST line of all four create
  views. The regression it prevents is a disclosure, not a crash: ``TenantModelForm`` only scopes
  its FK dropdowns when ``tenant is not None``, so the un-hoisted guard rendered every workspace's
  party, org-unit and document names and every user's email address. This lane asserts the
  redirect, that the form never rendered, that none of those strings reach the body - and, as the
  control that keeps the claim honest, that a ``tenant=None`` form really is unscoped, which is
  exactly why the view must never build one.
* **CSRF (L44).** Every verb, every create and every edit is refused 403 without a token, with
  nothing written; the same client still reads every register (so the 403 is a token failure, not
  a login failure) and the same POST succeeds once it carries the token.
* **Audit integrity (I12).** The verbs write an ``AuditLog`` row whose ``changes["from"]`` is the
  row's REAL prior status. The old hard-coded literal made the immutable trail assert the gate was
  respected in precisely the cases where it was skipped, which is why this is a security
  assertion and not a cosmetic one. Every action string is also checked against
  ``core.AuditLog.action``'s ``varchar(10)``.
* **Numeric hardening (M20).** Negative, ``NaN``, ``Infinity``, garbage and over-``max_digits``
  money reach a friendly field error at the route - 200 with the form redisplayed, never a 500 -
  and no row is created or changed.

**Two known gaps are encoded as STRICT XFAIL tripwires**, not asserted as correct behaviour - see
``test_projectinitiation_an_approved_charter_survives_a_member_delete`` and
``test_projectinitiation_a_completed_kickoff_is_closed_to_editing``. Both are reported to the
parent session as findings. Each marker is a tripwire, not an excuse: fix the view and the test
goes green-as-unexpected-pass, which fails the suite until the marker is deleted in the same
change.

Conventions: every test ``test_projectinitiation_*`` and every module-level helper
``_projectinitiation_*`` / ``_PROJECTINITIATION_*``, so 7.2 appending into this package cannot
shadow either. Dates derive from ``timezone.now()`` / ``timezone.localdate()`` (L16), never
``datetime.date.today()``. Nothing here touches the network. The file is pure ASCII on purpose:
several 7.1 messages carry U+2014 and curly quotes, so every message assertion matches an ASCII
SUBSTRING and a copy edit cannot turn into a red suite.
"""
import datetime

import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog
from apps.projects.forms import (
    ProjectForm,
    ProjectKickoffForm,
    ProjectRequestForm,
    ProjectStakeholderForm,
)
from apps.projects.models import Project, ProjectKickoff, ProjectRequest, ProjectStakeholder
from apps.projects.tests.conftest import (
    _projectinitiation_kickoff,
    _projectinitiation_project,
    _projectinitiation_request,
    _projectinitiation_stakeholder,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Route tables and module-level helpers - every name ``_projectinitiation_*`` / ``_PROJECTINITIATION_*``
# so a sibling lane appending nearby cannot rebind one and so a failure names its own lane.
# ==================================================================================================

#: The nine routes that take no pk.
_PROJECTINITIATION_PK_LESS_ROUTES = (
    "overview",
    "prq_list", "prq_create",
    "prj_list", "prj_create",
    "pst_list", "pst_create",
    "pko_list", "pko_create",
)

#: The twenty-three routes that take one pk. 9 + 23 = the 32 routes the sub-module owns.
_PROJECTINITIATION_PK_ROUTES = (
    "prq_detail", "prq_edit", "prq_delete", "prq_submit", "prq_approve", "prq_reject",
    "prq_return_for_information", "prq_convert",
    "prj_detail", "prj_edit", "prj_delete", "prj_submit_charter", "prj_approve_charter",
    "pst_detail", "pst_edit", "pst_delete",
    "pko_detail", "pko_edit", "pko_delete", "pko_schedule", "pko_mark_held", "pko_complete",
    "pko_mark_baseline_set",
)

_PROJECTINITIATION_ALL_ROUTES = _PROJECTINITIATION_PK_LESS_ROUTES + _PROJECTINITIATION_PK_ROUTES

#: THE ROLE MATRIX. Eight verbs answer a non-admin member with 403; they are the ones that record
#: a governance DECISION (approve / reject / return / convert / approve-charter) or move the
#: PROJECT's own lifecycle and stamp a signature (mark-held / complete / baseline). I5 added the
#: return verb, I13 added the three kickoff ceremony verbs.
_PROJECTINITIATION_ADMIN_VERBS = (
    "prq_approve", "prq_reject", "prq_return_for_information", "prq_convert",
    "prj_approve_charter",
    "pko_mark_held", "pko_complete", "pko_mark_baseline_set",
)

#: ...and the seven that are login-only. The four deletes match house style (287 of 393 delete
#: views app-wide are login-only); ``prq_submit`` and ``prj_submit_charter`` ASK for a decision
#: rather than making one; ``pko_schedule`` books a meeting without advancing the project.
#: ``test_projectinitiation_the_admin_gate_is_exactly_these_eight`` is what makes both tuples a
#: contract instead of a description.
_PROJECTINITIATION_OPEN_VERBS = (
    "prq_submit", "prq_delete",
    "prj_submit_charter", "prj_delete",
    "pst_delete",
    "pko_schedule", "pko_delete",
)

_PROJECTINITIATION_POST_VERBS = _PROJECTINITIATION_ADMIN_VERBS + _PROJECTINITIATION_OPEN_VERBS

#: The fixture each verb is exercised against - one row per verb, in a state the verb ACCEPTS, so
#: a "not 403" is never vacuous (a refusal on state would be a 302, not a 403) and so the admin
#: control below actually mutates something.
_PROJECTINITIATION_VERB_TARGETS = {
    "prq_submit": "projectinitiation_request_draft",
    "prq_approve": "projectinitiation_request_submitted",
    "prq_reject": "projectinitiation_request_submitted",
    "prq_return_for_information": "projectinitiation_request_submitted",
    "prq_convert": "projectinitiation_request_approved",
    "prq_delete": "projectinitiation_request_draft",
    "prj_submit_charter": "projectinitiation_project_draft",
    "prj_approve_charter": "projectinitiation_project_charter_submitted",
    # NOT ``project_draft``: ``stakeholder_a`` and ``kickoff_planned`` hang off it, and the
    # matrix test below fires all fifteen verbs against this table in one go - a CASCADE here
    # would delete ``pst_delete``'s and ``pko_delete``'s targets before their own turn came.
    "prj_delete": "projectinitiation_project_charter_rejected",
    "pst_delete": "projectinitiation_stakeholder_a",
    "pko_schedule": "projectinitiation_kickoff_planned",
    "pko_mark_held": "projectinitiation_kickoff_scheduled",
    "pko_complete": "projectinitiation_kickoff_ready_to_complete",
    "pko_mark_baseline_set": "projectinitiation_kickoff_held",
    "pko_delete": "projectinitiation_kickoff_planned",
}

#: Tenant B's row for each verb, keyed by the entity prefix the url name carries.
_PROJECTINITIATION_FOREIGN_FIXTURES = {
    "prq": "projectinitiation_request_b",
    "prj": "projectinitiation_project_b",
    "pst": "projectinitiation_stakeholder_b",
    "pko": "projectinitiation_kickoff_b",
}

#: Cross-tenant GET probes: every rendering route that takes a pk, on all four models.
_PROJECTINITIATION_FOREIGN_GET_ROUTES = (
    ("prq_detail", "projectinitiation_request_b"),
    ("prq_edit", "projectinitiation_request_b"),
    ("prj_detail", "projectinitiation_project_b"),
    ("prj_edit", "projectinitiation_project_b"),
    ("pst_detail", "projectinitiation_stakeholder_b"),
    ("pst_edit", "projectinitiation_stakeholder_b"),
    ("pko_detail", "projectinitiation_kickoff_b"),
    ("pko_edit", "projectinitiation_kickoff_b"),
)

#: The four registers with the tenant-B fixture that must never appear on them.
_PROJECTINITIATION_REGISTER_LEAK_PROBES = (
    ("prq_list", "projectinitiation_request_b"),
    ("prj_list", "projectinitiation_project_b"),
    ("pst_list", "projectinitiation_stakeholder_b"),
    ("pko_list", "projectinitiation_kickoff_b"),
)

#: The four create routes and the four edit routes, with the fixture an edit acts on. Both create
#: guards (tenant-less) and both smuggling lanes walk these.
_PROJECTINITIATION_CREATE_ROUTES = ("prq_create", "prj_create", "pst_create", "pko_create")

_PROJECTINITIATION_EDIT_TARGETS = {
    "prq_edit": "projectinitiation_request_draft",
    "prj_edit": "projectinitiation_project_draft",
    "pst_edit": "projectinitiation_stakeholder_a",
    "pko_edit": "projectinitiation_kickoff_planned",
}


def _projectinitiation_url(name, *args):
    return reverse(f"projects:{name}", args=args)


def _projectinitiation_login_url():
    return reverse("accounts:login")


def _projectinitiation_route_args(name, pk=1):
    """``()`` for the nine pk-less routes, ``(pk,)`` for the other twenty-three."""
    return () if name in _PROJECTINITIATION_PK_LESS_ROUTES else (pk,)


def _projectinitiation_messages(response):
    """Every message queued on the request that produced ``response``, as plain strings.

    Read off the REQUEST rather than the rendered page: the verbs redirect, so nothing has
    rendered - and therefore consumed - the storage yet.
    """
    return [str(message) for message in get_messages(response.wsgi_request)]


def _projectinitiation_said(response, fragment):
    """True when any queued message contains ``fragment``. ASCII substrings only."""
    return any(fragment in message for message in _projectinitiation_messages(response))


def _projectinitiation_body(response):
    return response.content.decode()


def _projectinitiation_pks(response, key="object_list"):
    return [row.pk for row in response.context[key]]


def _projectinitiation_snapshot(obj):
    """Every stored column of one row, read back from the database.

    A refused POST has to leave the row byte-for-byte as it was, and a status-only comparison
    would miss a stamped ``decided_by``, a moved ``updated_at`` or a re-minted ``number``.
    Comparing the whole row is what makes "nothing changed" mean nothing at all. Returns ``None``
    once the row is gone, which is itself a loud failure signal in an "unchanged" assertion.
    """
    return type(obj)._default_manager.filter(pk=obj.pk).values().first()


def _projectinitiation_deltas(before, after):
    if before is None or after is None:
        return {"__row__": (before, after)}
    return {name: (before[name], after[name])
            for name in before if before[name] != after[name]}


def _projectinitiation_unchanged(obj, before, label=""):
    deltas = _projectinitiation_deltas(before, _projectinitiation_snapshot(obj))
    assert deltas == {}, f"a refused request wrote to the row {label}: {deltas}"


def _projectinitiation_target(request, verb):
    """The tenant-A row a verb acts on, resolved lazily so a test builds only what it needs."""
    return request.getfixturevalue(_PROJECTINITIATION_VERB_TARGETS[verb])


def _projectinitiation_foreign_target(request, verb):
    """The tenant-B row the same verb is aimed at for the IDOR probes."""
    return request.getfixturevalue(_PROJECTINITIATION_FOREIGN_FIXTURES[verb.split("_")[0]])


def _projectinitiation_verb_payload(verb):
    """The POST body a verb needs to get PAST its own form and reach its state gate.

    Only the two decision verbs take one: ``ProjectRequestDecisionForm.reason`` is required, and
    without it ``prq_reject`` / ``prq_return_for_information`` answer "needs a stated reason"
    before the gate - which would make a "the member was refused" assertion pass for the wrong
    reason.
    """
    if verb in ("prq_reject", "prq_return_for_information"):
        return {"reason": "Stated so the refusal under test is the ROLE gate, not the form."}
    return {}


def _projectinitiation_audits(obj, action=None):
    """The audit rows written against ``obj``, newest first."""
    qs = AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)), object_id=obj.pk)
    if action is not None:
        qs = qs.filter(action=action)
    return list(qs.order_by("-id"))


def _projectinitiation_gated_verb_landed(verb, target):
    """True when an admin-gated verb actually did its work - the control that stops the 403
    assertions passing because the row was in a state every actor is refused."""
    target.refresh_from_db()
    return {
        "prq_approve": lambda: target.status == "approved",
        "prq_reject": lambda: target.status == "rejected",
        "prq_return_for_information": lambda: target.status == "needs_information",
        "prq_convert": lambda: target.converted_project_id is not None,
        "prj_approve_charter": lambda: target.charter_status == "approved",
        "pko_mark_held": lambda: target.status == "held",
        "pko_complete": lambda: target.status == "completed",
        "pko_mark_baseline_set": lambda: target.baseline_acknowledged_at is not None,
    }[verb]()


def _projectinitiation_open_verb_landed(verb, target):
    """True when a login-only verb did its work for an ordinary member."""
    if verb in ("prq_delete", "prj_delete", "pst_delete", "pko_delete"):
        return not type(target)._default_manager.filter(pk=target.pk).exists()
    target.refresh_from_db()
    return {
        "prq_submit": lambda: target.status == "submitted",
        "prj_submit_charter": lambda: target.charter_status == "submitted",
        "pko_schedule": lambda: target.status == "scheduled",
    }[verb]()


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


def _projectinitiation_meeting_date_string(days=7):
    """A future meeting date in the ``%Y-%m-%dT%H:%M`` shape the datetime-local widget accepts.

    Derived from ``timezone.now()`` and rendered through ``timezone.localtime`` - the same basis
    the views and ``Project.is_overdue`` use (L16). ``datetime.datetime.now()`` would drift by the
    UTC offset and flake for the hours either side of local midnight.
    """
    return timezone.localtime(
        timezone.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")


def _projectinitiation_kickoff_payload(project, **overrides):
    """The minimum valid ``ProjectKickoffForm`` POST, WITH a meeting date.

    The date is not decoration: ``pko_schedule`` refuses a kickoff that has none ("Set a meeting
    date before scheduling the kickoff"), so a chain test built on a dateless payload would stall
    at ``planned`` and read as a gate that fired when it never ran.
    """
    payload = {"project": str(project.pk), "agenda_template": "standard",
               "meeting_date": _projectinitiation_meeting_date_string()}
    payload.update(overrides)
    return payload


def _projectinitiation_seed_one_local_row(route, tenant):
    """One tenant-A row for ``route``'s register, so a filter test has something to lose.

    A cross-tenant filter assertion that runs against an EMPTY register passes for the wrong
    reason - which is the whole failure mode this helper exists to rule out.
    """
    project = _projectinitiation_project(tenant, name="Local filter project", code="LFP-01")
    if route == "prq_list":
        _projectinitiation_request(tenant, title="Local filter request")
    elif route == "pst_list":
        _projectinitiation_stakeholder(project, raci_scope="local filter scope")
    elif route == "pko_list":
        _projectinitiation_kickoff(project)
    return project


def _projectinitiation_edit_payload(route, target):
    """A VALID edit body for one of the four edit routes, ready to have a smuggled key added."""
    return {
        "prq_edit": lambda: _projectinitiation_request_payload(title="Edited through the route"),
        "prj_edit": lambda: _projectinitiation_project_payload(name="Edited through the route"),
        "pst_edit": lambda: _projectinitiation_stakeholder_payload(
            target.project, party=str(target.party_id), raci_scope="edited scope"),
        "pko_edit": lambda: _projectinitiation_kickoff_payload(
            target.project, agenda="Edited through the route"),
    }[route]()


# ==================================================================================================
# 1. The login wall - anonymous reaches nothing and mutates nothing
# ==================================================================================================

@pytest.mark.parametrize("name", _PROJECTINITIATION_ALL_ROUTES)
def test_projectinitiation_anonymous_get_is_redirected_to_login_on_every_route(client, name):
    """All 32 routes, GET. ``login_required`` fires before any database work, so the pk need not
    exist - what is asserted is that no route in this sub-module is reachable logged out."""
    resp = client.get(_projectinitiation_url(name, *_projectinitiation_route_args(name)))
    assert resp.status_code == 302, name
    assert resp["Location"].startswith(_projectinitiation_login_url()), name


@pytest.mark.parametrize("name", _PROJECTINITIATION_ALL_ROUTES)
def test_projectinitiation_anonymous_post_is_redirected_to_login_on_every_route(client, name):
    """All 32 routes, POST. A verb must not answer 405 (which would prove it exists and is
    POST-only) or 403 ahead of the login wall: the decorators stack
    ``login_required(tenant_admin_required(require_POST(view)))``, so the redirect comes first,
    every time and on every route."""
    resp = client.post(_projectinitiation_url(name, *_projectinitiation_route_args(name)), {})
    assert resp.status_code == 302, name
    assert resp["Location"].startswith(_projectinitiation_login_url()), name


@pytest.mark.parametrize("verb", _PROJECTINITIATION_POST_VERBS)
def test_projectinitiation_anonymous_cannot_mutate_a_real_row(client, request, verb):
    """The same fifteen POSTs against REAL tenant-A rows: redirected, and the row is untouched.

    The route-table test above proves the redirect; this one proves the redirect happens BEFORE
    the write, which is the property that actually matters.
    """
    target = _projectinitiation_target(request, verb)
    before = _projectinitiation_snapshot(target)

    resp = client.post(
        _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))

    assert resp.status_code == 302
    assert resp["Location"].startswith(_projectinitiation_login_url())
    _projectinitiation_unchanged(target, before, verb)


@pytest.mark.parametrize("route,fixture", _PROJECTINITIATION_FOREIGN_GET_ROUTES + (
    ("prq_detail", "projectinitiation_request_draft"),
    ("prj_detail", "projectinitiation_project_draft"),
))
def test_projectinitiation_anonymous_gets_no_content_from_a_real_row(
        client, request, route, fixture):
    """A redirect body is empty: the row's number, title and every other column must not ride out
    on the 302. Asserted rather than assumed, because a view that rendered first and redirected
    afterwards would still be a 302."""
    obj = request.getfixturevalue(fixture)

    resp = client.get(_projectinitiation_url(route, obj.pk))

    assert resp.status_code == 302
    assert resp.content == b""
    assert obj.number.encode() not in resp.content


@pytest.mark.parametrize("route", _PROJECTINITIATION_CREATE_ROUTES)
def test_projectinitiation_anonymous_create_post_saves_nothing(client, route, tenant_a,
                                                               projectinitiation_project_draft):
    """The create routes are where an unauthenticated POST would plant a row rather than read
    one. Nothing is minted, in any workspace."""
    payload = {
        "prq_create": lambda: _projectinitiation_request_payload(title="Anonymous intake"),
        "prj_create": lambda: _projectinitiation_project_payload(name="Anonymous project"),
        "pst_create": lambda: _projectinitiation_stakeholder_payload(
            projectinitiation_project_draft, raci_scope="anonymous scope"),
        "pko_create": lambda: _projectinitiation_kickoff_payload(
            projectinitiation_project_draft, agenda="Anonymous agenda"),
    }[route]()
    before = {model: model.objects.count()
              for model in (ProjectRequest, Project, ProjectStakeholder, ProjectKickoff)}

    resp = client.post(_projectinitiation_url(route), payload)

    assert resp.status_code == 302
    assert resp["Location"].startswith(_projectinitiation_login_url())
    assert {model: model.objects.count() for model in before} == before


# ==================================================================================================
# 2. The role gate - eight admin-only verbs, seven login-only, asserted as a matrix
# ==================================================================================================

def test_projectinitiation_the_admin_gate_is_exactly_these_eight(member_client, request):
    """THE matrix. A tenant-A member POSTs all fifteen verbs at rows their gates ACCEPT; the set
    that answers 403 must be exactly the eight ``@tenant_admin_required`` ones.

    Pinned as a set rather than one test per verb because the failure that matters is a verb
    JOINING or LEAVING the gate. 7.1 deliberately gates the five decision verbs and the three
    ceremony verbs that move ``Project.status`` or stamp a signature, and deliberately leaves the
    four deletes, both "ask for a decision" verbs and ``pko_schedule`` open. A future change to
    either list should be a decision somebody made on purpose, and this is where it becomes one.
    """
    refused = set()
    for verb in _PROJECTINITIATION_POST_VERBS:
        target = _projectinitiation_target(request, verb)
        resp = member_client.post(
            _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))
        assert resp.status_code in (302, 403), f"{verb} answered {resp.status_code}"
        if resp.status_code == 403:
            refused.add(verb)

    assert refused == set(_PROJECTINITIATION_ADMIN_VERBS)


@pytest.mark.parametrize("verb", _PROJECTINITIATION_ADMIN_VERBS)
def test_projectinitiation_a_member_post_on_a_gated_verb_is_403_and_changes_nothing(
        member_client, request, verb):
    """403 is only half the claim: the row must be byte-for-byte what it was, which is what rules
    out a view that mutated and then raised."""
    target = _projectinitiation_target(request, verb)
    before = _projectinitiation_snapshot(target)

    resp = member_client.post(
        _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))

    assert resp.status_code == 403
    _projectinitiation_unchanged(target, before, verb)


@pytest.mark.parametrize("verb", _PROJECTINITIATION_ADMIN_VERBS)
def test_projectinitiation_an_admin_post_on_the_same_verb_and_row_succeeds(
        client_a, request, verb):
    """The control that keeps the eight 403s meaningful: same verb, same row state, admin actor -
    and the work lands. Without this, every 403 above would also pass on a row whose state gate
    refuses everybody."""
    target = _projectinitiation_target(request, verb)

    resp = client_a.post(
        _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))

    assert resp.status_code == 302
    assert _projectinitiation_gated_verb_landed(verb, target), verb


@pytest.mark.parametrize("verb", _PROJECTINITIATION_ADMIN_VERBS)
def test_projectinitiation_a_member_get_on_a_gated_verb_is_403_not_405(
        member_client, request, verb):
    """The decorator order is ``login_required(tenant_admin_required(require_POST(view)))``, so
    for a member the ROLE check is reached before the method check. A 405 here would mean the
    member cleared the gate and was stopped only by the HTTP method - a very different (and much
    weaker) claim."""
    target = _projectinitiation_target(request, verb)
    before = _projectinitiation_snapshot(target)

    resp = member_client.get(_projectinitiation_url(verb, target.pk))

    assert resp.status_code == 403
    _projectinitiation_unchanged(target, before, verb)


@pytest.mark.parametrize("verb", _PROJECTINITIATION_OPEN_VERBS)
def test_projectinitiation_a_member_get_on_an_open_verb_is_405_and_writes_nothing(
        member_client, request, verb):
    """For the seven login-only verbs the method check is the outermost thing left, so a GET is
    405 - and, more to the point, a link, a prefetch or a crawler cannot mutate anything."""
    target = _projectinitiation_target(request, verb)
    before = _projectinitiation_snapshot(target)

    resp = member_client.get(_projectinitiation_url(verb, target.pk))

    assert resp.status_code == 405
    _projectinitiation_unchanged(target, before, verb)


@pytest.mark.parametrize("verb", _PROJECTINITIATION_OPEN_VERBS)
def test_projectinitiation_an_ordinary_member_may_work_the_open_verbs(
        member_client, request, verb):
    """The other half of the split, asserted as-built: an ordinary member submits a request,
    submits a charter, schedules a kickoff and deletes any of the four rows. This is house style,
    not an oversight, so it is pinned - a future decision to gate one of these will change this
    test and be visible in the diff rather than silently tightening production."""
    target = _projectinitiation_target(request, verb)

    resp = member_client.post(
        _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))

    assert resp.status_code == 302
    assert _projectinitiation_open_verb_landed(verb, target), verb


def test_projectinitiation_a_member_deleting_a_project_reopens_its_source_request(
        member_client, projectinitiation_request_converted):
    """``prj_delete`` is login-only, so an ordinary member can delete a converted project - and
    the I10 reopen then walks the tenant admin's APPROVED request back to ``approved`` with its
    ``converted_project`` cleared.

    Asserted deliberately, because it is the sharpest consequence of the login-only choice: a
    member cannot approve a request, but they can reverse the effect of an approval that was
    already acted on. The reopen itself is the correct behaviour (the alternative - I10's dead
    ``converted`` state with no project - is strictly worse); the exposure is who may trigger it.
    """
    source = projectinitiation_request_converted
    project = source.converted_project
    assert project is not None and source.status == "converted"

    resp = member_client.post(_projectinitiation_url("prj_delete", project.pk), {})

    assert resp.status_code == 302
    assert not Project.objects.filter(pk=project.pk).exists()
    source.refresh_from_db()
    assert source.status == "approved"
    assert source.converted_project_id is None


def test_projectinitiation_a_member_cannot_reach_approved_through_the_kickoff_chain(
        member_client, projectinitiation_project_draft):
    """C2's regression, restated as the AUTHORIZATION claim it really is.

    Before the fix a member could go create-project -> create-kickoff -> Complete and land an
    ``active`` project carrying ``charter_status='draft'`` and ``charter_approved_by=None`` -
    routing straight around the ``@tenant_admin_required`` on ``prj_approve_charter``. Every step
    of that chain is walked here as the member; the chain must die at the first gated verb, and
    the project must still be a draft with an unsigned charter.
    """
    project = projectinitiation_project_draft
    kickoff_resp = member_client.post(
        _projectinitiation_url("pko_create"),
        _projectinitiation_kickoff_payload(project, agenda="Member-run ceremony"))
    assert kickoff_resp.status_code == 302
    kickoff = ProjectKickoff.objects.get(project=project)

    assert member_client.post(
        _projectinitiation_url("pko_schedule", kickoff.pk), {}).status_code == 302
    assert member_client.post(
        _projectinitiation_url("pko_mark_held", kickoff.pk), {}).status_code == 403
    assert member_client.post(
        _projectinitiation_url("pko_complete", kickoff.pk), {}).status_code == 403
    assert member_client.post(
        _projectinitiation_url("pko_mark_baseline_set", kickoff.pk), {}).status_code == 403

    kickoff.refresh_from_db()
    project.refresh_from_db()
    assert kickoff.status == "scheduled"
    assert kickoff.completed_at is None
    assert kickoff.baseline_acknowledged_at is None
    assert project.status == "draft"
    assert project.charter_status == "draft"
    assert project.charter_approved_by_id is None


def test_projectinitiation_a_member_cannot_reverse_a_tenant_admins_decision(
        client_a, member_client, projectinitiation_request_submitted):
    """I5, end to end. The admin records a Go; the member's send-back - the one verb that VOIDS a
    decision - is refused, and the decision stamps survive intact."""
    obj = projectinitiation_request_submitted
    assert client_a.post(_projectinitiation_url("prq_approve", obj.pk), {}).status_code == 302
    obj.refresh_from_db()
    approver, decided_at = obj.decided_by_id, obj.decided_at
    before = _projectinitiation_snapshot(obj)

    resp = member_client.post(
        _projectinitiation_url("prq_return_for_information", obj.pk),
        {"reason": "Reopening someone else's approval."})

    assert resp.status_code == 403
    _projectinitiation_unchanged(obj, before)
    obj.refresh_from_db()
    assert obj.status == "approved"
    assert obj.decision == "go"
    assert obj.decided_by_id == approver
    assert obj.decided_at == decided_at


# ==================================================================================================
# 3. Cross-tenant IDOR - 404 on every pk route, both directions, all four models
# ==================================================================================================

@pytest.mark.parametrize("route,fixture", _PROJECTINITIATION_FOREIGN_GET_ROUTES)
def test_projectinitiation_cross_tenant_get_is_404(client_a, request, route, fixture):
    """Tenant A's ADMIN on tenant B's pk. 404, never 403 (which would confirm the row exists) and
    never 500. The admin actor is deliberate: on a gated route the role check runs first, so a
    member would be refused before the lookup and the 404 would never be reached."""
    obj = request.getfixturevalue(fixture)

    resp = client_a.get(_projectinitiation_url(route, obj.pk))

    assert resp.status_code == 404, route


@pytest.mark.parametrize("route,fixture", _PROJECTINITIATION_FOREIGN_GET_ROUTES)
def test_projectinitiation_cross_tenant_get_discloses_nothing(client_a, request, route, fixture):
    """A 404 page must not carry the row it refused to serve."""
    obj = request.getfixturevalue(fixture)

    resp = client_a.get(_projectinitiation_url(route, obj.pk))
    body = _projectinitiation_body(resp)

    assert obj.number not in body
    assert str(obj) not in body


@pytest.mark.parametrize("verb", _PROJECTINITIATION_POST_VERBS)
def test_projectinitiation_cross_tenant_post_is_404_and_changes_nothing(
        client_a, request, verb):
    """All fifteen verbs, aimed by tenant A's admin at tenant B's row: 404, and B's row is
    byte-for-byte what it was. This is the class the whole lane exists for - every one of the four
    deletes is in here, so a scoping slip would DESTROY another workspace's row rather than
    merely read it."""
    target = _projectinitiation_foreign_target(request, verb)
    before = _projectinitiation_snapshot(target)

    resp = client_a.post(
        _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))

    assert resp.status_code == 404, verb
    _projectinitiation_unchanged(target, before, verb)


@pytest.mark.parametrize("verb", _PROJECTINITIATION_ADMIN_VERBS)
def test_projectinitiation_a_member_on_a_foreign_pk_is_403_not_404(
        member_client, request, verb):
    """The other side of the actor split, pinned so a future reader does not "fix" the 404 test
    into a member one and quietly weaken it: ``apps/core/decorators.py:16`` raises
    ``PermissionDenied`` BEFORE ``get_object_or_404`` runs, so a tenant-A member aimed at a
    tenant-B row is refused on ROLE and never reaches the scope check. Either refusal is correct
    - what must not happen is a 200, or a write."""
    target = _projectinitiation_foreign_target(request, verb)
    before = _projectinitiation_snapshot(target)

    resp = member_client.post(
        _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))

    assert resp.status_code == 403, verb
    _projectinitiation_unchanged(target, before, verb)


@pytest.mark.parametrize("verb", _PROJECTINITIATION_OPEN_VERBS)
def test_projectinitiation_a_member_on_a_foreign_pk_of_an_open_verb_is_404(
        member_client, request, verb):
    """...and on the seven login-only verbs there is no role gate to fire first, so the same
    member falls through to the tenant scope check and gets the 404. Nothing is deleted."""
    target = _projectinitiation_foreign_target(request, verb)
    before = _projectinitiation_snapshot(target)

    resp = member_client.post(
        _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))

    assert resp.status_code == 404, verb
    _projectinitiation_unchanged(target, before, verb)


@pytest.mark.parametrize("route,fixture", (
    ("prq_edit", "projectinitiation_request_b"),
    ("prj_edit", "projectinitiation_project_b"),
    ("pst_edit", "projectinitiation_stakeholder_b"),
    ("pko_edit", "projectinitiation_kickoff_b"),
))
def test_projectinitiation_cross_tenant_edit_post_cannot_rewrite_the_row(
        client_a, request, route, fixture):
    """A hand-crafted edit POST that never rendered a form. 404 before ``crud_edit`` binds
    anything, and B's row is unchanged."""
    obj = request.getfixturevalue(fixture)
    before = _projectinitiation_snapshot(obj)

    resp = client_a.post(_projectinitiation_url(route, obj.pk),
                         _projectinitiation_edit_payload(route, obj))

    assert resp.status_code == 404
    _projectinitiation_unchanged(obj, before, route)


@pytest.mark.parametrize("route,fixture", _PROJECTINITIATION_REGISTER_LEAK_PROBES)
def test_projectinitiation_a_register_never_contains_another_workspaces_row(
        client_a, request, route, fixture):
    foreign = request.getfixturevalue(fixture)

    resp = client_a.get(_projectinitiation_url(route))

    assert resp.status_code == 200
    assert foreign.pk not in _projectinitiation_pks(resp)
    assert foreign.number not in _projectinitiation_body(resp)


@pytest.mark.parametrize("route,fixture,term", (
    ("prq_list", "projectinitiation_request_b", "Globex only request"),
    ("prj_list", "projectinitiation_project_b", "Globex only project"),
))
def test_projectinitiation_a_search_never_reaches_another_workspaces_text(
        client_a, request, route, fixture, term):
    """``?q=`` runs before pagination and after the tenant filter. If the order were ever
    inverted, search would become an oracle for another workspace's titles."""
    foreign = request.getfixturevalue(fixture)

    resp = client_a.get(_projectinitiation_url(route), {"q": term})

    assert resp.status_code == 200
    assert _projectinitiation_pks(resp) == []
    assert foreign.number not in _projectinitiation_body(resp)


@pytest.mark.parametrize("route,param,fixture", (
    ("prq_list", "org_unit", "projectinitiation_org_unit_b"),
    ("prj_list", "org_unit", "projectinitiation_org_unit_b"),
    ("prj_list", "client", "projectinitiation_party_b"),
    ("pst_list", "project", "projectinitiation_project_b"),
    ("pko_list", "project", "projectinitiation_project_b"),
))
def test_projectinitiation_a_foreign_pk_in_an_fk_filter_returns_nothing_not_everything(
        client_a, request, route, param, fixture, tenant_a):
    """A real, in-range, valid pk that belongs to ANOTHER workspace is a narrowing request the
    register must honour - and honouring it yields nothing, because the tenant filter is applied
    first.

    It must not be treated as junk and SKIPPED, because a skipped filter returns the whole
    register and turns the parameter into an existence oracle ("did the row count change?"), and
    it must not 500. The unfiltered read first is what stops this passing on an empty register.
    """
    foreign = request.getfixturevalue(fixture)
    _projectinitiation_seed_one_local_row(route, tenant_a)

    unfiltered = client_a.get(_projectinitiation_url(route))
    resp = client_a.get(_projectinitiation_url(route), {param: str(foreign.pk)})

    assert _projectinitiation_pks(unfiltered) != [], "the register was empty before the filter"
    assert resp.status_code == 200
    assert _projectinitiation_pks(resp) == []


def test_projectinitiation_tenant_b_cannot_see_tenant_a_either(
        client_b, projectinitiation_request_draft, projectinitiation_project_draft,
        projectinitiation_stakeholder_a, projectinitiation_kickoff_planned):
    """Isolation is symmetric or it is not isolation. The whole probe set again, from B's side."""
    for route, obj in (("prq_detail", projectinitiation_request_draft),
                       ("prj_detail", projectinitiation_project_draft),
                       ("pst_detail", projectinitiation_stakeholder_a),
                       ("pko_detail", projectinitiation_kickoff_planned)):
        assert client_b.get(_projectinitiation_url(route, obj.pk)).status_code == 404, route
    for route in ("prq_list", "prj_list", "pst_list", "pko_list"):
        resp = client_b.get(_projectinitiation_url(route))
        assert resp.status_code == 200
        assert _projectinitiation_pks(resp) == [], route


# ==================================================================================================
# 4. Cross-tenant FK smuggling at the ROUTE - every scoped FK, each with a same-tenant control
# ==================================================================================================
#
# The forms lane proves the FIELD rejects a foreign pk. These prove the same thing where an
# attacker actually stands: a valid own-tenant create/edit POST with one foreign FK in it. The
# assertion is that the FIELD HAS AN ERROR and nothing landed - never the wording, because
# ``TenantModelForm`` narrows the queryset first and Django's own "Select a valid choice" message
# pre-empts ``_reject_foreign``'s "belongs to another workspace" on every reachable path.

@pytest.mark.parametrize("field,fixture", (
    ("org_unit", "projectinitiation_org_unit_b"),
    ("requester_party", "projectinitiation_party_b"),
    ("source_opportunity", "projectinitiation_opportunity_b"),
    ("requested_by", "projectinitiation_member_b"),
    ("assigned_reviewer", "projectinitiation_member_b"),
    ("assigned_approver", "projectinitiation_member_b"),
))
def test_projectinitiation_request_create_rejects_a_foreign_fk(
        client_a, request, field, fixture):
    foreign = request.getfixturevalue(fixture)
    payload = _projectinitiation_request_payload(
        title="Smuggled intake", **{field: str(foreign.pk)})

    resp = client_a.post(_projectinitiation_url("prq_create"), payload)

    assert resp.status_code == 200
    assert field in resp.context["form"].errors
    assert not ProjectRequest.objects.filter(title="Smuggled intake").exists()


@pytest.mark.parametrize("field,fixture", (
    ("org_unit", "projectinitiation_org_unit_a"),
    ("requester_party", "projectinitiation_party_a"),
    ("source_opportunity", "projectinitiation_opportunity_a"),
    ("requested_by", "member_user"),
    ("assigned_reviewer", "member_user"),
    ("assigned_approver", "member_user"),
))
def test_projectinitiation_request_create_accepts_the_same_field_from_its_own_workspace(
        client_a, request, tenant_a, field, fixture):
    """The control that makes the six rejections above non-vacuous: the identical POST with the
    SAME field pointing at tenant A's own row must succeed. Without this pair a payload that was
    simply malformed would read as a security win."""
    local = request.getfixturevalue(fixture)
    payload = _projectinitiation_request_payload(
        title="Local intake", **{field: str(local.pk)})

    resp = client_a.post(_projectinitiation_url("prq_create"), payload)

    assert resp.status_code == 302
    obj = ProjectRequest.objects.get(title="Local intake")
    assert obj.tenant_id == tenant_a.pk
    assert getattr(obj, f"{field}_id") == local.pk


@pytest.mark.parametrize("field,fixture", (
    ("org_unit", "projectinitiation_org_unit_b"),
    ("client", "projectinitiation_party_b"),
    ("charter_document", "projectinitiation_document_b"),
    ("executive_sponsor", "projectinitiation_member_b"),
    ("project_manager", "projectinitiation_member_b"),
))
def test_projectinitiation_project_create_rejects_a_foreign_fk(
        client_a, request, field, fixture):
    foreign = request.getfixturevalue(fixture)
    payload = _projectinitiation_project_payload(
        name="Smuggled project", **{field: str(foreign.pk)})

    resp = client_a.post(_projectinitiation_url("prj_create"), payload)

    assert resp.status_code == 200
    assert field in resp.context["form"].errors
    assert not Project.objects.filter(name="Smuggled project").exists()


@pytest.mark.parametrize("field,fixture", (
    ("org_unit", "projectinitiation_org_unit_a"),
    ("client", "projectinitiation_party_a"),
    ("charter_document", "projectinitiation_document_a"),
    ("executive_sponsor", "member_user"),
    ("project_manager", "member_user"),
))
def test_projectinitiation_project_create_accepts_the_same_field_from_its_own_workspace(
        client_a, request, tenant_a, field, fixture):
    local = request.getfixturevalue(fixture)
    payload = _projectinitiation_project_payload(name="Local project", **{field: str(local.pk)})

    resp = client_a.post(_projectinitiation_url("prj_create"), payload)

    assert resp.status_code == 302
    obj = Project.objects.get(name="Local project")
    assert obj.tenant_id == tenant_a.pk
    assert getattr(obj, f"{field}_id") == local.pk


@pytest.mark.parametrize("field,fixture", (
    ("project", "projectinitiation_project_b"),
    ("party", "projectinitiation_party_b"),
    ("user", "projectinitiation_member_b"),
))
def test_projectinitiation_stakeholder_create_rejects_a_foreign_fk(
        client_a, request, projectinitiation_project_draft, projectinitiation_party_a,
        field, fixture):
    """``project`` is the sharp one: a stakeholder hung off another workspace's project would put
    tenant A's row on tenant B's charter. The explicit ``ModelChoiceField`` fails closed at
    ``Project.objects.none()`` and ``__init__`` narrows it to this workspace."""
    foreign = request.getfixturevalue(fixture)
    payload = _projectinitiation_stakeholder_payload(
        projectinitiation_project_draft, raci_scope="smuggled scope",
        party=str(projectinitiation_party_a.pk))
    payload[field] = str(foreign.pk)

    resp = client_a.post(_projectinitiation_url("pst_create"), payload)

    assert resp.status_code == 200
    assert field in resp.context["form"].errors
    assert not ProjectStakeholder.objects.filter(raci_scope="smuggled scope").exists()


def test_projectinitiation_stakeholder_create_accepts_its_own_workspaces_fks(
        client_a, tenant_a, projectinitiation_project_draft, projectinitiation_party_a,
        member_user):
    """The control for all three rejections above."""
    payload = _projectinitiation_stakeholder_payload(
        projectinitiation_project_draft, raci_scope="local scope",
        party=str(projectinitiation_party_a.pk), user=str(member_user.pk))

    resp = client_a.post(_projectinitiation_url("pst_create"), payload)

    assert resp.status_code == 302
    obj = ProjectStakeholder.objects.get(raci_scope="local scope")
    assert obj.tenant_id == tenant_a.pk
    assert obj.project_id == projectinitiation_project_draft.pk
    assert obj.party_id == projectinitiation_party_a.pk
    assert obj.user_id == member_user.pk


def test_projectinitiation_kickoff_create_rejects_a_foreign_project(
        client_a, projectinitiation_project_b):
    payload = _projectinitiation_kickoff_payload(
        projectinitiation_project_b, agenda="Smuggled ceremony")

    resp = client_a.post(_projectinitiation_url("pko_create"), payload)

    assert resp.status_code == 200
    assert "project" in resp.context["form"].errors
    assert not ProjectKickoff.objects.filter(agenda="Smuggled ceremony").exists()


def test_projectinitiation_kickoff_create_accepts_its_own_workspaces_project(
        client_a, tenant_a, projectinitiation_project_draft):
    payload = _projectinitiation_kickoff_payload(
        projectinitiation_project_draft, agenda="Local ceremony")

    resp = client_a.post(_projectinitiation_url("pko_create"), payload)

    assert resp.status_code == 302
    obj = ProjectKickoff.objects.get(agenda="Local ceremony")
    assert obj.tenant_id == tenant_a.pk
    assert obj.project_id == projectinitiation_project_draft.pk


def test_projectinitiation_an_edit_cannot_move_a_row_onto_another_workspaces_project(
        client_a, projectinitiation_stakeholder_a, projectinitiation_kickoff_planned,
        projectinitiation_project_b):
    """The same smuggle on the EDIT route, where the row already exists and only the pointer would
    move - a quieter and more useful attack than creating one."""
    stakeholder = projectinitiation_stakeholder_a
    kickoff = projectinitiation_kickoff_planned
    stakeholder_before = _projectinitiation_snapshot(stakeholder)
    kickoff_before = _projectinitiation_snapshot(kickoff)

    pst_resp = client_a.post(
        _projectinitiation_url("pst_edit", stakeholder.pk),
        _projectinitiation_stakeholder_payload(
            projectinitiation_project_b, party=str(stakeholder.party_id),
            raci_scope=stakeholder.raci_scope))
    pko_resp = client_a.post(
        _projectinitiation_url("pko_edit", kickoff.pk),
        _projectinitiation_kickoff_payload(projectinitiation_project_b))

    assert pst_resp.status_code == 200
    assert "project" in pst_resp.context["form"].errors
    assert pko_resp.status_code == 200
    assert "project" in pko_resp.context["form"].errors
    _projectinitiation_unchanged(stakeholder, stakeholder_before, "pst_edit")
    _projectinitiation_unchanged(kickoff, kickoff_before, "pko_edit")


def test_projectinitiation_an_edit_cannot_repoint_a_request_at_a_foreign_org_unit(
        client_a, projectinitiation_request_draft, projectinitiation_org_unit_b):
    obj = projectinitiation_request_draft
    before = _projectinitiation_snapshot(obj)

    resp = client_a.post(
        _projectinitiation_url("prq_edit", obj.pk),
        _projectinitiation_request_payload(org_unit=str(projectinitiation_org_unit_b.pk)))

    assert resp.status_code == 200
    assert "org_unit" in resp.context["form"].errors
    _projectinitiation_unchanged(obj, before, "prq_edit")


def test_projectinitiation_an_edit_cannot_attach_a_foreign_charter_document(
        client_a, projectinitiation_project_draft, projectinitiation_document_b):
    """The charter document is the artefact the whole sub-module is named after; attaching another
    workspace's file to this workspace's charter would be a read of their storage path."""
    obj = projectinitiation_project_draft
    before = _projectinitiation_snapshot(obj)

    resp = client_a.post(
        _projectinitiation_url("prj_edit", obj.pk),
        _projectinitiation_project_payload(
            charter_document=str(projectinitiation_document_b.pk)))

    assert resp.status_code == 200
    assert "charter_document" in resp.context["form"].errors
    _projectinitiation_unchanged(obj, before, "prj_edit")


# ==================================================================================================
# 5. Mass assignment at the HTTP layer - create AND edit, all four models
# ==================================================================================================
#
# The forms lane pins this at the form layer (a smuggled column is not in ``Meta.fields``, so it is
# never bound). These assert the same claim at the ROUTE, which is the only place it is actually
# defended in production.

def test_projectinitiation_request_create_ignores_every_smuggled_system_column(
        client_a, tenant_a, tenant_b, admin_b, projectinitiation_project_b):
    """Nineteen smuggled keys in one POST, including the three DECISION EVIDENCE fields the fix
    pass added to ``Meta.exclude`` (I3): ``rejection_reason`` and ``information_requested`` are
    written only by ``@tenant_admin_required`` verbs, so a field a gated verb writes must not be
    POST-settable through the ungated create/edit form."""
    resp = client_a.post(_projectinitiation_url("prq_create"), _projectinitiation_request_payload(
        title="Smuggled intake",
        tenant=str(tenant_b.pk),
        number="PRQ-99999",
        status="approved",
        decision="go",
        decided_by=str(admin_b.pk),
        decided_at="2020-01-01T00:00",
        submitted_at="2020-01-01T00:00",
        converted_project=str(projectinitiation_project_b.pk),
        created_by=str(admin_b.pk),
        rejection_reason="smuggled rationale",
        information_requested="smuggled question",
        decision_notes="smuggled note",
        id="4242",
        pk="4242",
    ))

    assert resp.status_code == 302
    obj = ProjectRequest.objects.get(title="Smuggled intake")
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("PRQ-") and obj.number != "PRQ-99999"
    assert obj.status == "draft"
    assert obj.decision == ""
    assert obj.decided_by_id is None
    assert obj.decided_at is None
    assert obj.submitted_at is None
    assert obj.converted_project_id is None
    assert obj.created_by_id != admin_b.pk
    assert obj.rejection_reason == ""
    assert obj.information_requested == ""
    assert obj.decision_notes == ""
    assert obj.pk != 4242


def test_projectinitiation_request_edit_ignores_every_smuggled_system_column(
        client_a, tenant_a, tenant_b, admin_b, projectinitiation_request_draft,
        projectinitiation_project_b):
    """The same nineteen keys on the EDIT route. This is the one that matters most: a member who
    could set ``status='approved'`` here would not need ``prq_approve`` at all, and one who could
    blank ``rejection_reason`` could erase an admin's stated rationale while leaving the No-Go."""
    obj = projectinitiation_request_draft
    original_number, original_pk = obj.number, obj.pk

    resp = client_a.post(_projectinitiation_url("prq_edit", obj.pk),
                         _projectinitiation_request_payload(
                             title="Edited through the route",
                             tenant=str(tenant_b.pk),
                             number="PRQ-99999",
                             status="approved",
                             decision="go",
                             decided_by=str(admin_b.pk),
                             decided_at="2020-01-01T00:00",
                             submitted_at="2020-01-01T00:00",
                             converted_project=str(projectinitiation_project_b.pk),
                             created_by=str(admin_b.pk),
                             rejection_reason="smuggled rationale",
                             information_requested="smuggled question",
                             decision_notes="smuggled note",
                             id="999",
                             pk="999"))

    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.title == "Edited through the route"        # the one field the form DOES own
    assert obj.pk == original_pk
    assert obj.tenant_id == tenant_a.pk
    assert obj.number == original_number
    assert obj.status == "draft"
    assert obj.decision == ""
    assert obj.decided_by_id is None
    assert obj.decided_at is None
    assert obj.submitted_at is None
    assert obj.converted_project_id is None
    assert obj.created_by_id != admin_b.pk
    assert obj.rejection_reason == ""
    assert obj.information_requested == ""
    assert obj.decision_notes == ""


def test_projectinitiation_project_create_ignores_every_smuggled_system_column(
        client_a, tenant_a, tenant_b, admin_b, projectinitiation_request_draft):
    """``charter_status`` + its two stamps are the signature; ``request`` is the provenance the
    convert verb owns. A POST that could set all four would mint a project that claims an approval
    nobody made, on a demand nobody raised."""
    resp = client_a.post(_projectinitiation_url("prj_create"), _projectinitiation_project_payload(
        name="Smuggled project",
        tenant=str(tenant_b.pk),
        number="PRJ-99999",
        status="active",
        charter_status="approved",
        charter_approved_by=str(admin_b.pk),
        charter_approved_at="2020-01-01T00:00",
        created_by=str(admin_b.pk),
        request=str(projectinitiation_request_draft.pk),
        id="888",
    ))

    assert resp.status_code == 302
    obj = Project.objects.get(name="Smuggled project")
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("PRJ-") and obj.number != "PRJ-99999"
    assert obj.status == "draft"
    assert obj.charter_status == "draft"
    assert obj.charter_approved_by_id is None
    assert obj.charter_approved_at is None
    assert obj.created_by_id != admin_b.pk
    assert obj.request_id is None
    assert obj.pk != 888


def test_projectinitiation_project_edit_ignores_every_smuggled_system_column(
        client_a, tenant_a, tenant_b, admin_b, projectinitiation_project_draft,
        projectinitiation_request_draft):
    obj = projectinitiation_project_draft
    original_number, original_pk = obj.number, obj.pk

    resp = client_a.post(_projectinitiation_url("prj_edit", obj.pk),
                         _projectinitiation_project_payload(
                             name="Edited through the route",
                             tenant=str(tenant_b.pk),
                             number="PRJ-99999",
                             status="active",
                             charter_status="approved",
                             charter_approved_by=str(admin_b.pk),
                             charter_approved_at="2020-01-01T00:00",
                             created_by=str(admin_b.pk),
                             request=str(projectinitiation_request_draft.pk),
                             id="888"))

    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.name == "Edited through the route"
    assert obj.pk == original_pk
    assert obj.tenant_id == tenant_a.pk
    assert obj.number == original_number
    assert obj.status == "draft"
    assert obj.charter_status == "draft"
    assert obj.charter_approved_by_id is None
    assert obj.charter_approved_at is None
    assert obj.created_by_id != admin_b.pk
    assert obj.request_id is None


def test_projectinitiation_kickoff_create_ignores_every_smuggled_system_column(
        client_a, tenant_a, tenant_b, admin_b, projectinitiation_project_draft):
    """``status='completed'`` + ``completed_at`` + the baseline stamps in one POST is the whole
    ceremony forged in a single request - and ``pko_complete`` is one of the three verbs I13
    gated at tenant admin, so the form must not offer a way round it."""
    resp = client_a.post(_projectinitiation_url("pko_create"), _projectinitiation_kickoff_payload(
        projectinitiation_project_draft,
        agenda="Smuggled ceremony",
        tenant=str(tenant_b.pk),
        number="PKO-99999",
        status="completed",
        completed_at="2020-01-01T00:00",
        baseline_acknowledged_by=str(admin_b.pk),
        baseline_acknowledged_at="2020-01-01T00:00",
        created_by=str(admin_b.pk),
        id="777",
    ))

    assert resp.status_code == 302
    obj = ProjectKickoff.objects.get(agenda="Smuggled ceremony")
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("PKO-") and obj.number != "PKO-99999"
    assert obj.status == "planned"
    assert obj.completed_at is None
    assert obj.baseline_acknowledged_by_id is None
    assert obj.baseline_acknowledged_at is None
    assert obj.created_by_id != admin_b.pk
    assert obj.pk != 777
    projectinitiation_project_draft.refresh_from_db()
    assert projectinitiation_project_draft.status == "draft"


def test_projectinitiation_kickoff_edit_ignores_every_smuggled_system_column(
        client_a, tenant_a, tenant_b, admin_b, projectinitiation_kickoff_planned):
    obj = projectinitiation_kickoff_planned
    original_number, original_pk = obj.number, obj.pk

    resp = client_a.post(_projectinitiation_url("pko_edit", obj.pk),
                         _projectinitiation_kickoff_payload(
                             obj.project,
                             agenda="Edited through the route",
                             tenant=str(tenant_b.pk),
                             number="PKO-99999",
                             status="completed",
                             completed_at="2020-01-01T00:00",
                             baseline_acknowledged_by=str(admin_b.pk),
                             baseline_acknowledged_at="2020-01-01T00:00",
                             created_by=str(admin_b.pk),
                             id="777"))

    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.agenda == "Edited through the route"
    assert obj.pk == original_pk
    assert obj.tenant_id == tenant_a.pk
    assert obj.number == original_number
    assert obj.status == "planned"
    assert obj.completed_at is None
    assert obj.baseline_acknowledged_by_id is None
    assert obj.baseline_acknowledged_at is None


def test_projectinitiation_stakeholder_create_ignores_every_smuggled_system_column(
        client_a, tenant_a, tenant_b, admin_b, projectinitiation_project_draft,
        projectinitiation_party_a):
    resp = client_a.post(_projectinitiation_url("pst_create"),
                         _projectinitiation_stakeholder_payload(
                             projectinitiation_project_draft,
                             party=str(projectinitiation_party_a.pk),
                             raci_scope="smuggled scope",
                             tenant=str(tenant_b.pk),
                             number="PST-99999",
                             created_by=str(admin_b.pk),
                             id="666"))

    assert resp.status_code == 302
    obj = ProjectStakeholder.objects.get(raci_scope="smuggled scope")
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("PST-") and obj.number != "PST-99999"
    assert obj.created_by_id != admin_b.pk
    assert obj.pk != 666


def test_projectinitiation_stakeholder_edit_ignores_every_smuggled_system_column(
        client_a, tenant_a, tenant_b, admin_b, projectinitiation_stakeholder_a):
    obj = projectinitiation_stakeholder_a
    original_number, original_pk = obj.number, obj.pk

    resp = client_a.post(_projectinitiation_url("pst_edit", obj.pk),
                         _projectinitiation_stakeholder_payload(
                             obj.project,
                             party=str(obj.party_id),
                             raci_scope="edited scope",
                             tenant=str(tenant_b.pk),
                             number="PST-99999",
                             created_by=str(admin_b.pk),
                             id="666"))

    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.raci_scope == "edited scope"
    assert obj.pk == original_pk
    assert obj.tenant_id == tenant_a.pk
    assert obj.number == original_number


def test_projectinitiation_a_create_post_cannot_plant_a_row_in_another_workspace(
        client_a, tenant_a, tenant_b):
    """The headline of the whole section, isolated: ``tenant`` is stamped from ``request.tenant``
    in the view, not read from the POST, so tenant B's register gains nothing."""
    before = ProjectRequest.objects.filter(tenant=tenant_b).count()

    client_a.post(_projectinitiation_url("prq_create"),
                  _projectinitiation_request_payload(title="Planted", tenant=str(tenant_b.pk)))

    assert ProjectRequest.objects.filter(tenant=tenant_b).count() == before
    assert ProjectRequest.objects.get(title="Planted").tenant_id == tenant_a.pk


# ==================================================================================================
# 6. The post-decision / post-approval edit locks (I2 / I3)
# ==================================================================================================
#
# "You cannot forge the signature, but you could change what it signs." Both edit routes are
# login-only, so the lock - not the role gate - is the only thing standing between an ordinary
# member and the text a tenant admin approved.

def test_projectinitiation_a_member_cannot_rewrite_an_approved_charter(
        member_client, projectinitiation_project_charter_approved):
    """I2. The refusal must happen BEFORE ``crud_edit`` binds the form, and the two stamps that
    attest to the approved text have to survive it unchanged."""
    obj = projectinitiation_project_charter_approved
    before = _projectinitiation_snapshot(obj)
    approver, approved_at = obj.charter_approved_by_id, obj.charter_approved_at

    resp = member_client.post(
        _projectinitiation_url("prj_edit", obj.pk),
        _projectinitiation_project_payload(
            name="Rewritten under the signature", methodology="agile",
            objectives="Different objectives from the ones that were approved.",
            in_scope="A larger scope than the approved charter carried."))

    assert resp.status_code == 302
    assert resp["Location"] == _projectinitiation_url("prj_detail", obj.pk)
    assert _projectinitiation_said(resp, "An approved charter cannot be edited")
    _projectinitiation_unchanged(obj, before)
    obj.refresh_from_db()
    assert obj.charter_approved_by_id == approver
    assert obj.charter_approved_at == approved_at


def test_projectinitiation_a_member_cannot_open_the_edit_form_of_an_approved_charter(
        member_client, projectinitiation_project_charter_approved):
    """A GET must be refused too: rendering the form would hand the member a pre-filled page that
    looks editable and a token to POST it with."""
    resp = member_client.get(
        _projectinitiation_url("prj_edit", projectinitiation_project_charter_approved.pk))

    assert resp.status_code == 302
    assert "form" not in (resp.context or {})


def test_projectinitiation_a_member_cannot_rewrite_an_approved_business_case(
        member_client, projectinitiation_request_approved):
    """I3, the money half: leaving ``estimated_cost`` / ``estimated_benefit`` / ``risk_rating``
    writable after ``decided_at`` is stamped means the ROI on the page is not the ROI that was
    approved - and ``roi_pct`` is DERIVED, so rewriting the inputs silently rewrites the output."""
    obj = projectinitiation_request_approved
    before = _projectinitiation_snapshot(obj)
    decider, decided_at = obj.decided_by_id, obj.decided_at

    resp = member_client.post(
        _projectinitiation_url("prq_edit", obj.pk),
        _projectinitiation_request_payload(
            title="Rewritten after approval", estimated_cost="1.00",
            estimated_benefit="9999999.00", risk_rating="low", strategic_alignment="5"))

    assert resp.status_code == 302
    assert resp["Location"] == _projectinitiation_url("prq_detail", obj.pk)
    assert _projectinitiation_said(resp, "cannot be edited")
    _projectinitiation_unchanged(obj, before)
    obj.refresh_from_db()
    assert obj.decided_by_id == decider
    assert obj.decided_at == decided_at


def test_projectinitiation_a_member_cannot_rewrite_a_converted_business_case(
        member_client, projectinitiation_request_converted):
    """``converted`` is locked separately from the decision stamp: the business case is now a
    project's charter, so editing it would change the provenance of a live project."""
    obj = projectinitiation_request_converted
    before = _projectinitiation_snapshot(obj)

    resp = member_client.post(
        _projectinitiation_url("prq_edit", obj.pk),
        _projectinitiation_request_payload(title="Rewritten after conversion"))

    assert resp.status_code == 302
    _projectinitiation_unchanged(obj, before)


def test_projectinitiation_a_rejected_request_keeps_the_admins_stated_reason(
        member_client, projectinitiation_request_rejected):
    """Both halves of I3 in one place: the edit is locked by the decision stamp, AND
    ``rejection_reason`` is not a form field, so neither route lets a member erase or rewrite the
    rationale the admin recorded."""
    obj = projectinitiation_request_rejected
    original_reason = obj.rejection_reason
    assert original_reason

    resp = member_client.post(
        _projectinitiation_url("prq_edit", obj.pk),
        _projectinitiation_request_payload(title="Reason laundering",
                                           rejection_reason="",
                                           decision_notes="looks fine to me"))

    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.rejection_reason == original_reason
    assert obj.decision == "no_go"
    assert obj.decision_notes == ""


def test_projectinitiation_the_reopen_path_is_the_only_way_back_into_an_edit(
        client_a, member_client, projectinitiation_request_approved):
    """The lock follows the EVIDENCE stamp, not a status list. That is what makes
    ``prq_return_for_information`` - itself tenant-admin gated - the single supported way to
    reopen a decided request: the member cannot edit before it, and can after."""
    obj = projectinitiation_request_approved
    assert member_client.get(
        _projectinitiation_url("prq_edit", obj.pk)).status_code == 302

    assert client_a.post(_projectinitiation_url("prq_return_for_information", obj.pk),
                         {"reason": "Send me the lease break costs."}).status_code == 302

    obj.refresh_from_db()
    assert obj.decided_at is None
    assert member_client.get(_projectinitiation_url("prq_edit", obj.pk)).status_code == 200


# ==================================================================================================
# 7. The tenant=None user (I1) - a disclosure bug, not a crash
# ==================================================================================================

@pytest.mark.parametrize("route", _PROJECTINITIATION_CREATE_ROUTES)
def test_projectinitiation_a_tenantless_user_is_turned_away_from_every_create_view(
        projectinitiation_tenantless_client, route):
    """The guard is on the FIRST line of all four create views, ahead of the form construction.
    ``User.tenant`` is ``SET_NULL``, so this is any member of a deleted workspace, not only the
    superuser."""
    resp = projectinitiation_tenantless_client.get(_projectinitiation_url(route))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("dashboard:home")
    assert _projectinitiation_said(resp, "Select a tenant workspace before creating records.")


@pytest.mark.parametrize("route", _PROJECTINITIATION_CREATE_ROUTES)
def test_projectinitiation_a_tenantless_create_never_renders_an_unscoped_dropdown(
        projectinitiation_tenantless_client, route, tenant_a, tenant_b,
        projectinitiation_party_a, projectinitiation_party_b, projectinitiation_org_unit_a,
        projectinitiation_org_unit_b, projectinitiation_document_a,
        projectinitiation_document_b, projectinitiation_project_draft,
        projectinitiation_project_b, admin_user, admin_b, projectinitiation_member_b):
    """THE regression I1 actually was. The bug was not the 500 it never caused - it was that
    ``TenantModelForm`` only scopes an FK queryset when ``tenant is not None``, so a form built
    for a tenant-less user listed EVERY workspace's party, org-unit, document and project names
    and EVERY user's email address in its ``<select>`` options.

    Following the redirect to its destination and scanning the whole delivered body is what makes
    this a disclosure test rather than a status-code test.
    """
    resp = projectinitiation_tenantless_client.get(
        _projectinitiation_url(route), follow=True)
    body = _projectinitiation_body(resp)

    assert resp.redirect_chain == [(reverse("dashboard:home"), 302)]
    assert "form" not in (resp.context or {})
    for leaked in (projectinitiation_party_a.name, projectinitiation_party_b.name,
                   projectinitiation_org_unit_a.name, projectinitiation_org_unit_b.name,
                   projectinitiation_document_a.name, projectinitiation_document_b.name,
                   projectinitiation_project_draft.name, projectinitiation_project_b.name,
                   admin_user.email, admin_b.email, projectinitiation_member_b.email):
        assert leaked not in body, leaked
    for field in ('name="org_unit"', 'name="client"', 'name="party"', 'name="project"',
                  'name="charter_document"', 'name="requester_party"'):
        assert field not in body, field


@pytest.mark.parametrize("form_class", [ProjectRequestForm, ProjectForm,
                                        ProjectStakeholderForm])
def test_projectinitiation_a_tenantless_form_is_exactly_what_the_guard_prevents(
        form_class, tenant_a, tenant_b, projectinitiation_party_b,
        projectinitiation_org_unit_b, projectinitiation_document_b,
        projectinitiation_member_b):
    """The control that keeps the test above honest: built with ``tenant=None`` these forms
    really ARE unscoped, so the view's first-line guard is the only thing between a tenant-less
    session and another workspace's names.

    This is not a claim about what the form should do - the fixer pass tried hardening
    ``apps/core/forms/_common.py`` to fail closed and REVERTED it, because ten tests in
    ``apps/inventory`` and ``apps/procurement`` encode the current contract (see the Phase 5
    notes). It is the measurement that makes I1's guard load-bearing, and it fails loudly if
    that shared decision is ever revisited without this lane being revisited too.
    """
    form = form_class(tenant=None)
    foreign_rows = [projectinitiation_party_b, projectinitiation_org_unit_b,
                    projectinitiation_document_b, projectinitiation_member_b]
    leaked = sorted(
        name for name, field in form.fields.items()
        if getattr(field, "queryset", None) is not None
        and any(row in field.queryset for row in foreign_rows))

    assert leaked, (
        f"{form_class.__name__}(tenant=None) no longer offers another workspace's rows - if the "
        "shared TenantModelForm was hardened to fail closed, delete this control and say so in "
        "the same change")


@pytest.mark.parametrize("form_class", [ProjectStakeholderForm, ProjectKickoffForm])
def test_projectinitiation_the_project_dropdown_fails_closed_without_a_tenant(
        form_class, projectinitiation_project_draft, projectinitiation_project_b):
    """M6: both ``project`` fields declare ``queryset=Project.objects.none()`` at class level and
    narrow it in ``__init__``, so the fallback for a path that forgets to scope is an EMPTY
    dropdown rather than every workspace's projects. The one FK a tenant-less form must not leak
    is the one that would hang this workspace's row on another's charter."""
    assert list(form_class(tenant=None).fields["project"].queryset) == []


def test_projectinitiation_a_tenantless_create_post_saves_nothing(
        projectinitiation_tenantless_client, projectinitiation_project_draft):
    """The guard has to hold on POST too, or the redirect is only cosmetic."""
    before = {model: model.objects.count()
              for model in (ProjectRequest, Project, ProjectStakeholder, ProjectKickoff)}

    for route, payload in (
            ("prq_create", _projectinitiation_request_payload(title="Tenantless intake")),
            ("prj_create", _projectinitiation_project_payload(name="Tenantless project")),
            ("pst_create", _projectinitiation_stakeholder_payload(
                projectinitiation_project_draft, raci_scope="tenantless scope")),
            ("pko_create", _projectinitiation_kickoff_payload(
                projectinitiation_project_draft, agenda="Tenantless agenda"))):
        resp = projectinitiation_tenantless_client.post(
            _projectinitiation_url(route), payload)
        assert resp.status_code == 302, route
        assert resp["Location"] == reverse("dashboard:home"), route

    assert {model: model.objects.count() for model in before} == before


@pytest.mark.parametrize("route", ("prq_list", "prj_list", "pst_list", "pko_list"))
def test_projectinitiation_a_tenantless_register_is_empty_not_universal(
        projectinitiation_tenantless_client, route, projectinitiation_request_draft,
        projectinitiation_project_draft, projectinitiation_stakeholder_a,
        projectinitiation_kickoff_planned, projectinitiation_request_b,
        projectinitiation_project_b, projectinitiation_stakeholder_b,
        projectinitiation_kickoff_b):
    """``filter(tenant=None)`` compiles to ``tenant_id IS NULL`` and matches nothing, which is the
    designed answer (CLAUDE.md's multi-tenancy rule 1). The failure this guards against is a view
    that special-cased ``tenant is None`` into "show everything"."""
    resp = projectinitiation_tenantless_client.get(_projectinitiation_url(route))

    assert resp.status_code == 200
    assert _projectinitiation_pks(resp) == []


def test_projectinitiation_a_tenantless_user_cannot_reach_any_workspaces_row(
        projectinitiation_tenantless_client, projectinitiation_request_draft,
        projectinitiation_project_b):
    """Detail routes scope on ``tenant=request.tenant`` too, so a tenant-less session is 404 on
    every row in every workspace - not just on the ones it happens not to own."""
    for route, obj in (("prq_detail", projectinitiation_request_draft),
                       ("prj_detail", projectinitiation_project_b)):
        assert projectinitiation_tenantless_client.get(
            _projectinitiation_url(route, obj.pk)).status_code == 404, route


# ==================================================================================================
# 8. CSRF (L44)
# ==================================================================================================

@pytest.mark.parametrize("verb", _PROJECTINITIATION_POST_VERBS)
def test_projectinitiation_a_verb_without_a_csrf_token_is_refused(
        projectinitiation_csrf_client, request, verb):
    """Every one of the fifteen, with a valid admin session and no token: 403, row untouched.

    Note this is a genuinely different refusal from the role gate - the actor here is a tenant
    ADMIN who would otherwise be allowed - so the eight gated verbs are covered twice on purpose,
    once for who and once for how.
    """
    target = _projectinitiation_target(request, verb)
    before = _projectinitiation_snapshot(target)

    resp = projectinitiation_csrf_client.post(
        _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))

    assert resp.status_code == 403, verb
    _projectinitiation_unchanged(target, before, verb)


@pytest.mark.parametrize("route", _PROJECTINITIATION_CREATE_ROUTES)
def test_projectinitiation_a_create_without_a_csrf_token_saves_nothing(
        projectinitiation_csrf_client, route, projectinitiation_project_draft):
    payload = {
        "prq_create": lambda: _projectinitiation_request_payload(title="No token here"),
        "prj_create": lambda: _projectinitiation_project_payload(name="No token here"),
        "pst_create": lambda: _projectinitiation_stakeholder_payload(
            projectinitiation_project_draft, raci_scope="no token scope"),
        "pko_create": lambda: _projectinitiation_kickoff_payload(
            projectinitiation_project_draft, agenda="No token agenda"),
    }[route]()
    before = {model: model.objects.count()
              for model in (ProjectRequest, Project, ProjectStakeholder, ProjectKickoff)}

    resp = projectinitiation_csrf_client.post(_projectinitiation_url(route), payload)

    assert resp.status_code == 403
    assert {model: model.objects.count() for model in before} == before


@pytest.mark.parametrize("route", sorted(_PROJECTINITIATION_EDIT_TARGETS))
def test_projectinitiation_an_edit_without_a_csrf_token_changes_nothing(
        projectinitiation_csrf_client, request, route):
    target = request.getfixturevalue(_PROJECTINITIATION_EDIT_TARGETS[route])
    before = _projectinitiation_snapshot(target)

    resp = projectinitiation_csrf_client.post(
        _projectinitiation_url(route, target.pk),
        _projectinitiation_edit_payload(route, target))

    assert resp.status_code == 403
    _projectinitiation_unchanged(target, before, route)


@pytest.mark.parametrize("route", ("overview", "prq_list", "prj_list", "pst_list", "pko_list"))
def test_projectinitiation_the_same_csrf_enforcing_client_still_reads_every_register(
        projectinitiation_csrf_client, route):
    """The L44 pair. CSRF enforcement must not be mistaken for a broken session: the same client
    that was refused every POST reads every page fine, which is what makes the 403s above a TOKEN
    failure and not a login failure."""
    assert projectinitiation_csrf_client.get(
        _projectinitiation_url(route)).status_code == 200


def test_projectinitiation_a_csrf_enforcing_post_that_carries_the_token_succeeds(
        projectinitiation_csrf_client, projectinitiation_request_draft):
    """...and the completing half: with the token taken off the rendered page, the same POST
    works. Without this, a view that answered 403 for some unrelated reason would look secure."""
    obj = projectinitiation_request_draft
    page = projectinitiation_csrf_client.get(_projectinitiation_url("prq_detail", obj.pk))
    token = str(page.context["csrf_token"])

    resp = projectinitiation_csrf_client.post(
        _projectinitiation_url("prq_submit", obj.pk), {"csrfmiddlewaretoken": token})

    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.status == "submitted"


def test_projectinitiation_every_detail_page_ships_a_csrf_token_for_its_action_forms(
        client_a, projectinitiation_request_submitted, projectinitiation_project_draft,
        projectinitiation_kickoff_planned):
    """The detail pages are where the verb buttons live. A POST form rendered WITHOUT
    ``{% csrf_token %}`` would be a 403 for every legitimate user - the failure mode that tempts
    somebody to exempt the view instead of fixing the template."""
    for route, obj in (("prq_detail", projectinitiation_request_submitted),
                       ("prj_detail", projectinitiation_project_draft),
                       ("pko_detail", projectinitiation_kickoff_planned)):
        body = _projectinitiation_body(client_a.get(_projectinitiation_url(route, obj.pk)))
        assert 'name="csrfmiddlewaretoken"' in body, route


# ==================================================================================================
# 9. Audit integrity (I12) - the trail records what actually happened
# ==================================================================================================
#
# The old code hard-coded ``{"from": "draft"}`` on every verb. That is a security defect, not a
# cosmetic one: it made the immutable trail assert the gate was respected in EXACTLY the cases
# where it was skipped (a needs_information -> submitted hop logged as coming from draft, and C2's
# ungated complete logged as a clean transition).

@pytest.mark.parametrize("verb,fixture,expected_from,expected_to", (
    ("prq_submit", "projectinitiation_request_needs_information",
     "needs_information", "submitted"),
    ("prq_approve", "projectinitiation_request_screening", "screening", "approved"),
    ("prq_reject", "projectinitiation_request_submitted", "submitted", "rejected"),
    ("prq_return_for_information", "projectinitiation_request_screening",
     "screening", "needs_information"),
    ("prj_submit_charter", "projectinitiation_project_charter_rejected",
     "rejected", "submitted"),
    ("prj_approve_charter", "projectinitiation_project_charter_submitted",
     "submitted", "approved"),
    ("pko_schedule", "projectinitiation_kickoff_planned", "planned", "scheduled"),
    ("pko_mark_held", "projectinitiation_kickoff_scheduled", "scheduled", "held"),
    ("pko_complete", "projectinitiation_kickoff_ready_to_complete", "held", "completed"),
    ("pko_mark_baseline_set", "projectinitiation_kickoff_held", "held", "acknowledged"),
))
def test_projectinitiation_a_verb_logs_the_state_it_really_came_from(
        client_a, request, verb, fixture, expected_from, expected_to):
    """Every source state here is deliberately NOT the model default, so a hard-coded literal
    cannot pass: ``screening`` not ``submitted``, ``needs_information`` not ``draft``, a
    ``rejected`` charter not a fresh one."""
    target = request.getfixturevalue(fixture)

    resp = client_a.post(
        _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))

    assert resp.status_code == 302
    entry = _projectinitiation_audits(target)[0]
    assert entry.changes["from"] == expected_from, verb
    assert entry.changes["to"] == expected_to, verb


def test_projectinitiation_a_send_back_records_the_decision_it_voided(
        client_a, projectinitiation_request_approved):
    """I4 + I12 together: the send-back VOIDS a recorded Go, and what it voided is written into
    the immutable trail BEFORE the columns are cleared. Without that, the reversal of an approval
    would leave no evidence anywhere that an approval had ever existed."""
    obj = projectinitiation_request_approved

    client_a.post(_projectinitiation_url("prq_return_for_information", obj.pk),
                  {"reason": "Send me the lease break costs."})

    entry = _projectinitiation_audits(obj)[0]
    assert entry.action == "return"
    assert entry.changes["from"] == "approved"
    assert entry.changes["voided_decision"] == "go"
    obj.refresh_from_db()
    assert obj.decision == ""
    assert obj.decided_by_id is None
    assert obj.decided_at is None


def test_projectinitiation_a_conversion_records_both_numbers(
        client_a, projectinitiation_request_approved):
    """``prq_convert``'s trail is the only link back to the demand once the project is live."""
    obj = projectinitiation_request_approved

    client_a.post(_projectinitiation_url("prq_convert", obj.pk), {})

    obj.refresh_from_db()
    entry = _projectinitiation_audits(obj, action="convert")[0]
    assert entry.changes["from"] == obj.number
    assert entry.changes["to"] == obj.converted_project.number


def test_projectinitiation_a_project_delete_records_the_request_it_reopened(
        member_client, projectinitiation_request_converted):
    """The reopen is a WRITE to a row the deleter never named, so it gets its own audit entry -
    otherwise a request would silently walk from ``converted`` back to ``approved`` with nothing
    saying who did it or why."""
    source = projectinitiation_request_converted

    member_client.post(
        _projectinitiation_url("prj_delete", source.converted_project.pk), {})

    entry = _projectinitiation_audits(source, action="update")[0]
    assert entry.changes["verb"] == "reopen_on_project_delete"
    assert entry.changes["from"] == "converted"
    assert entry.changes["to"] == "approved"


def test_projectinitiation_a_verb_names_the_actor_who_pressed_it(
        client_a, admin_user, projectinitiation_request_submitted):
    """An audit row with no user is not an audit row."""
    obj = projectinitiation_request_submitted

    client_a.post(_projectinitiation_url("prq_approve", obj.pk), {})

    entry = _projectinitiation_audits(obj, action="approve")[0]
    assert entry.user_id == admin_user.pk
    assert entry.tenant_id == obj.tenant_id
    assert obj.number in entry.target


def test_projectinitiation_a_refused_verb_writes_no_audit_row(
        client_a, projectinitiation_request_draft):
    """L35's other edge: a refusal that still logged would put a fabricated transition in the
    immutable trail - the exact failure I12 describes, arriving from the opposite direction."""
    obj = projectinitiation_request_draft
    before = len(_projectinitiation_audits(obj))

    resp = client_a.post(_projectinitiation_url("prq_approve", obj.pk), {})

    assert resp.status_code == 302
    assert _projectinitiation_said(resp, "Only a request under review can be approved")
    assert len(_projectinitiation_audits(obj)) == before


def test_projectinitiation_a_403_writes_no_audit_row(
        member_client, projectinitiation_request_submitted):
    obj = projectinitiation_request_submitted
    before = len(_projectinitiation_audits(obj))

    assert member_client.post(
        _projectinitiation_url("prq_approve", obj.pk), {}).status_code == 403

    assert len(_projectinitiation_audits(obj)) == before


def test_projectinitiation_every_audit_action_fits_the_column(
        client_a, projectinitiation_request_needs_information,
        projectinitiation_request_screening, projectinitiation_request_submitted,
        projectinitiation_request_approved, projectinitiation_project_charter_submitted,
        projectinitiation_project_charter_rejected, projectinitiation_kickoff_planned,
        projectinitiation_kickoff_scheduled, projectinitiation_kickoff_ready_to_complete,
        projectinitiation_kickoff_held, projectinitiation_project_draft,
        projectinitiation_party_a):
    """``core.AuditLog.action`` is ``varchar(10)``. SQLite does not enforce the width, so a
    string that is silently truncated (or, on MySQL in strict mode, a hard write error) would
    never show up in this suite unless it is asserted directly.

    All eleven state verbs are fired once here, plus a create and a delete; ``update`` arrives
    from ``prj_submit_charter``, which logs action ``update`` with ``verb="submit_charter"`` in
    ``changes``. Every action string that lands is measured against the column, and the expected
    twelve are asserted present so a verb that stopped logging altogether cannot pass this by
    writing nothing.
    """
    for verb, target in (
            ("prq_submit", projectinitiation_request_needs_information),
            ("prq_approve", projectinitiation_request_screening),
            ("prq_reject", projectinitiation_request_submitted),
            ("prq_return_for_information", projectinitiation_request_needs_information),
            ("prq_convert", projectinitiation_request_approved),
            ("prj_submit_charter", projectinitiation_project_charter_rejected),
            ("prj_approve_charter", projectinitiation_project_charter_submitted),
            ("pko_schedule", projectinitiation_kickoff_planned),
            ("pko_mark_held", projectinitiation_kickoff_scheduled),
            ("pko_complete", projectinitiation_kickoff_ready_to_complete),
            ("pko_mark_baseline_set", projectinitiation_kickoff_held)):
        client_a.post(
            _projectinitiation_url(verb, target.pk), _projectinitiation_verb_payload(verb))
    client_a.post(_projectinitiation_url("pst_create"),
                  _projectinitiation_stakeholder_payload(
                      projectinitiation_project_draft, raci_scope="audit scope",
                      party=str(projectinitiation_party_a.pk)))
    client_a.post(_projectinitiation_url("pko_delete", projectinitiation_kickoff_planned.pk), {})

    width = AuditLog._meta.get_field("action").max_length
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert actions, "no audit rows were written - the assertion below would be vacuous"
    for action in actions:
        assert len(action) <= width, f"{action!r} does not fit varchar({width})"
    assert {"submit", "approve", "reject", "return", "convert", "schedule", "held", "complete",
            "baseline", "create", "update", "delete"} <= actions


# ==================================================================================================
# 10. Numeric hardening (M20) - a friendly field error, never a 500, never a stored value
# ==================================================================================================

@pytest.mark.parametrize("field", ["estimated_cost", "estimated_benefit"])
@pytest.mark.parametrize("value", ["-5", "-0.01", "NaN", "Infinity", "-Infinity", "abc",
                                   "1e400", "999999999999999.99", "99999999999999999999.99",
                                   "", "  ", "1,000", "0x10"])
def test_projectinitiation_a_bad_money_value_is_a_field_error_not_a_500(
        client_a, field, value):
    """M20 added ``MinValueValidator(0)``; ``max_digits=14`` and ``DecimalField`` cover the rest.
    All of it has to land as a FIELD error on a redisplayed 200 - a 500 on a value anybody can
    type into a form is a denial of service, and a stored negative would reach ``roi_pct`` and
    ``risk_adjusted_benefit``, which are DERIVED and would quietly report a profitable loss."""
    payload = _projectinitiation_request_payload(title="Bad money", **{field: value})

    resp = client_a.post(_projectinitiation_url("prq_create"), payload)

    assert resp.status_code == 200
    assert field in resp.context["form"].errors
    assert not ProjectRequest.objects.filter(title="Bad money").exists()


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "abc", "1e400",
                                   "99999999999999999999.99"])
def test_projectinitiation_a_bad_money_value_cannot_be_edited_into_a_row(
        client_a, projectinitiation_request_draft, value):
    """The same values on the EDIT route, where a stored row is at stake rather than an unsaved
    one."""
    obj = projectinitiation_request_draft
    before = _projectinitiation_snapshot(obj)

    resp = client_a.post(_projectinitiation_url("prq_edit", obj.pk),
                         _projectinitiation_request_payload(estimated_benefit=value))

    assert resp.status_code == 200
    assert "estimated_benefit" in resp.context["form"].errors
    _projectinitiation_unchanged(obj, before)


@pytest.mark.parametrize("value", ["9", "6", "-1", "abc", "NaN", "1e400",
                                   "99999999999999999999"])
def test_projectinitiation_strategic_alignment_stays_inside_its_range(client_a, value):
    """``MaxValueValidator(5)`` on a 0-5 score. Out of range would skew the intake ranking the
    register is sorted and filtered by."""
    resp = client_a.post(_projectinitiation_url("prq_create"),
                         _projectinitiation_request_payload(title="Bad score",
                                                            strategic_alignment=value))

    assert resp.status_code == 200
    assert "strategic_alignment" in resp.context["form"].errors
    assert not ProjectRequest.objects.filter(title="Bad score").exists()


@pytest.mark.parametrize("value", ["NaN", "Infinity", "not-a-date", "0000-00-00T00:00",
                                   "9999999-01-01T00:00", "2026-13-45T99:99"])
def test_projectinitiation_a_bad_meeting_date_is_a_field_error_not_a_500(
        client_a, projectinitiation_project_draft, value):
    """``meeting_date`` is the one datetime a user types. ``pko_schedule`` refuses a kickoff
    without one, so a value that crashed the form - or worse, saved as NULL - would be a way past
    "Set a meeting date before scheduling the kickoff"."""
    payload = _projectinitiation_kickoff_payload(
        projectinitiation_project_draft, agenda="Bad date", meeting_date=value)

    resp = client_a.post(_projectinitiation_url("pko_create"), payload)

    assert resp.status_code == 200
    assert "meeting_date" in resp.context["form"].errors
    assert not ProjectKickoff.objects.filter(agenda="Bad date").exists()


@pytest.mark.parametrize("route,param", (
    ("prq_list", "org_unit"), ("prj_list", "client"), ("pst_list", "project"),
    ("pko_list", "project"), ("prq_list", "page"), ("pko_list", "page"),
))
@pytest.mark.parametrize("value", ["abc", "0", "-1", "NaN", "Infinity",
                                   "999999999999999999999", "\u00b2", "' OR 1=1 --"])
def test_projectinitiation_a_junk_query_parameter_never_500s_for_any_actor(
        member_client, route, param, value):
    """L11 / L9 from the security side, and asserted as the MEMBER rather than the admin: a
    hand-edited URL is the cheapest attack surface there is, and every one of these must return
    the register at 200 rather than a stack trace that names the ORM and the column."""
    resp = member_client.get(_projectinitiation_url(route), {param: value})

    assert resp.status_code == 200


def test_projectinitiation_a_search_term_of_markup_is_escaped_not_executed(client_a):
    """Reflected XSS through ``?q=``: the term is echoed back into the search box, so it must
    arrive escaped."""
    payload = "<script>alert('xss')</script>"

    resp = client_a.get(_projectinitiation_url("prq_list"), {"q": payload})
    body = _projectinitiation_body(resp)

    assert resp.status_code == 200
    assert payload not in body
    assert "&lt;script&gt;" in body


def test_projectinitiation_a_stored_title_of_markup_is_escaped_on_every_page(client_a):
    """Stored XSS: a title posted through the create form must render escaped on the register and
    on the detail page, not execute."""
    payload = "<img src=x onerror=alert(1)>"
    resp = client_a.post(_projectinitiation_url("prq_create"),
                         _projectinitiation_request_payload(title=payload))
    assert resp.status_code == 302
    obj = ProjectRequest.objects.get(title=payload)

    for route, args in (("prq_list", ()), ("prq_detail", (obj.pk,))):
        body = _projectinitiation_body(client_a.get(_projectinitiation_url(route, *args)))
        assert payload not in body, route
        assert "&lt;img" in body, route


# ==================================================================================================
# 11. The two evidence gaps these tests reported - now FIXED, so they are plain regressions
# ==================================================================================================
#
# Both were written first as strict-xfail tripwires stating the behaviour the rest of 7.1's
# evidence model implies. Strict xfail fails the suite the moment the view is fixed, which is what
# forced the markers to be deleted in the change that fixed them (S1, S2). The assertions are
# unchanged - they always described the correct behaviour - and now guard it going forward:
# prj_delete refuses an approved charter (Projects.py), pko_edit refuses an attested kickoff
# (ProjectKickoffs.py, via ProjectKickoff.is_locked).

def test_projectinitiation_an_approved_charter_survives_a_member_delete(
        member_client, projectinitiation_project_charter_approved):
    obj = projectinitiation_project_charter_approved

    member_client.post(_projectinitiation_url("prj_delete", obj.pk), {})

    assert Project.objects.filter(pk=obj.pk).exists(), (
        "a non-admin member deleted a project whose charter a tenant admin had approved")


def test_projectinitiation_a_completed_kickoff_is_closed_to_editing(
        member_client, projectinitiation_kickoff_completed):
    obj = projectinitiation_kickoff_completed
    original_agenda, original_date = obj.agenda, obj.meeting_date

    member_client.post(_projectinitiation_url("pko_edit", obj.pk),
                       _projectinitiation_kickoff_payload(
                           obj.project, agenda="Rewritten after the ceremony",
                           meeting_date="2020-01-01T09:00"))

    obj.refresh_from_db()
    assert obj.agenda == original_agenda and obj.meeting_date == original_date, (
        "a completed kickoff's minutes were rewritten under its completion stamp")
