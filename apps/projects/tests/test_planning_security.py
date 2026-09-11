"""Projects 7.2 Project Planning & Scheduling - SECURITY tests.

The fourth 7.2 lane. ``test_planning_models.py`` owns the invariants, ``test_planning_forms.py``
the field lists and validation, ``test_planning_views.py`` the functional HTTP layer (happy paths,
filters, state gates, pagination) - every request in that lane is made by ``client_a``, a tenant
ADMIN of the row's OWN workspace, so the only thing that can refuse a verb there is its own state
gate. This file owns the three questions those three never ask: **who may reach it, whose
workspace is it, and what does the answer disclose.**

What it locks down, finding by finding:

* **Cross-tenant IDOR - the highest-value class.** Every detail/edit GET and every delete/verb
  POST aimed by ``client_a`` (tenant A's ADMIN) at a tenant-B pk answers **404** (never 403, which
  would confirm the row exists, and never 500), with B's row byte-for-byte unchanged. The admin
  actor is deliberate (``apps/core/decorators.py``): the ``@tenant_admin_required`` role check
  runs *before* ``get_object_or_404``, so on the three gated verbs a member would be refused on
  ROLE and the scope check would never be reached - every IDOR-404 assertion here therefore uses
  an admin, and the member-403 assertions never claim a 404.
* **The role gate on the three governance verbs.** ``mst_achieve`` / ``bsl_activate`` /
  ``bsl_promote`` are the 7.2 verbs that move governance state, and all three are
  ``login_required(tenant_admin_required(require_POST(view)))``. A member POSTs each at OWN-tenant
  rows whose state gates would ACCEPT: the answer is 403 with ZERO field deltas, and an admin
  replay on the same row proves the 403 was about the ROLE, not the row.
* **The verbs are POST-only.** A GET on any of the seven POST-only routes (4 deletes + 3 verbs)
  is 405 - a link, a prefetch or a crawler cannot mutate anything.
* **The I4 template guard.** Rendering the admin buttons to a member would just serve a hard 403,
  so the detail templates wrap them in
  ``{% if request.user.is_superuser or request.user.is_tenant_admin %}``. A member's milestone
  page carries no "Mark Achieved" and their baseline pages neither "Promote to Baseline" nor
  "Activate"; the admin's pages do - while the Edit links stay for everyone.
* **Cross-tenant FK smuggling at the ROUTE (C2-adjacent, I1).** A valid own-tenant create POST
  carrying another workspace's ``project`` / ``parent`` / ``successor`` / ``anchor_task`` pk is
  rejected as a FIELD ERROR and nothing lands anywhere. Each smuggle is paired with a
  **same-tenant control POST that DOES create**, so a payload that was simply malformed cannot
  read as a security win. The assertion is that the FIELD HAS AN ERROR - never the wording, since
  ``TenantModelForm`` narrows the queryset first and Django's own "Select a valid choice" message
  pre-empts ``_reject_foreign``'s sentence on every reachable path.
* **The two edit locks at the route (I1 / I2).** ``bsl_edit`` and ``mst_edit`` are login-only, so
  a member reaches them. ``BaselineForm`` locks ``baseline_type`` on edit (type moves only
  through the gated ``bsl_promote``, which snapshots and audits it) and ``MilestoneForm`` does
  not offer ``status`` at all (it moves only through the gated ``mst_achieve``) - a smuggled
  ``status=achieved`` is ignored and the row's status and stamp survive.
* **The tenant=None user and the login wall.** The superuser shape sees every register EMPTY (no
  workspace's rows, empty project dropdowns) and is turned away from every create view on the
  FIRST line; an anonymous caller is redirected to login on every register, and the verb POSTs
  answer the redirect BEFORE any mutation.
* **Template hygiene.** Rendered pages must carry neither ``{#`` nor ``{% comment`` (a leaked
  comment is a disclosure of intent, and one that renders is a syntax bug), and the ``confirm()``
  dialogs interpolate NUMBERS only - never a free-text project name, which is what
  ``obj.project.name`` in a rendered body would mean.
* **The tenant-scoping contract (7.1 lane style).** All four planning models take ``tenant`` from
  the shared ``TenantNumbered`` base with ``related_name="+"`` - the views always filter by
  ``request.tenant``, so no reverse accessor may exist on ``core.Tenant``.

Conventions: every test is ``test_planning_*`` and every module-level helper ``_planning_*`` /
``_PLANNING_*``, so no sibling lane appending into this package can shadow either. Dates derive
from ``timezone.localdate()`` via ``_planning_today()`` (L16), never ``datetime.date.today()``.
Nothing here touches the seeder (``seed_projects``) or ``bulk_create``; rows come from the
``conftest`` factories, which construct + ``.save()`` so ``TenantNumbered`` mints the number.
The file is pure ASCII on purpose: several refusal messages carry U+2014 and curly quotes, so any
message assertion matches an ASCII SUBSTRING and a copy edit cannot turn into a red suite.
"""
import datetime
import re

import pytest
from django.urls import reverse

from apps.projects.models import (
    ProjectMilestone,
    ProjectTask,
    ScheduleBaseline,
    TaskDependency,
)
from apps.projects.tests.conftest import (
    _planning_task,
    _planning_today,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Route tables and module-level helpers - every name ``_planning_*`` / ``_PLANNING_*`` so a sibling
# lane appending nearby cannot rebind one and so a failure names its own lane.
# ==================================================================================================

#: The four registers. The tree is NOT a register (it renders one project's WBS), but it is a
#: rendering route and walks with the hygiene test below.
_PLANNING_REGISTERS = ("tsk_list", "dep_list", "mst_list", "bsl_list")

#: Cross-tenant GET probes: every detail and edit route on all four models, against tenant B's row.
_PLANNING_FOREIGN_GET_PROBES = (
    ("tsk_detail", "planning_task_b"),
    ("tsk_edit", "planning_task_b"),
    ("dep_detail", "planning_dependency_b"),
    ("dep_edit", "planning_dependency_b"),
    ("mst_detail", "planning_milestone_b"),
    ("mst_edit", "planning_milestone_b"),
    ("bsl_detail", "planning_baseline_b"),
    ("bsl_edit", "planning_baseline_b"),
)

#: ...and the four delete POSTs - the writes that would DESTROY another workspace's row.
_PLANNING_FOREIGN_DELETE_PROBES = (
    ("tsk_delete", "planning_task_b"),
    ("dep_delete", "planning_dependency_b"),
    ("mst_delete", "planning_milestone_b"),
    ("bsl_delete", "planning_baseline_b"),
)

#: The three governance verbs, aimed cross-tenant.
_PLANNING_FOREIGN_VERB_PROBES = (
    ("mst_achieve", "planning_milestone_b"),
    ("bsl_activate", "planning_baseline_b"),
    ("bsl_promote", "planning_baseline_b"),
)

#: All seven POST-only routes (4 deletes + 3 verbs), each against a tenant-A row whose OWN state
#: gate would ACCEPT the verb - so a 405 below is the method check, never a state refusal.
_PLANNING_POST_ONLY_PROBES = (
    ("tsk_delete", "planning_task_a"),
    ("dep_delete", "planning_dependency_a"),
    ("mst_delete", "planning_milestone_a"),
    ("bsl_delete", "planning_baseline_whatif_a"),
    ("mst_achieve", "planning_milestone_a"),
    ("bsl_activate", "planning_baseline_frozen_a"),
    ("bsl_promote", "planning_baseline_whatif_a"),
)

#: The anonymous-actor probe: every POST-only route against a REAL tenant-A row, to prove the
#: login redirect happens ahead of the write and not just ahead of the render.
_PLANNING_ANON_VERB_PROBES = _PLANNING_POST_ONLY_PROBES

#: The pk-less rendering routes (four registers + the WBS tree) the hygiene test walks.
_PLANNING_RENDER_ROUTES = _PLANNING_REGISTERS + ("tsk_tree",)

#: The four detail pages that carry verb buttons and/or delete confirms.
_PLANNING_DETAIL_PROBES = (
    ("tsk_detail", "planning_task_a"),
    ("dep_detail", "planning_dependency_a"),
    ("mst_detail", "planning_milestone_a"),
    ("bsl_detail", "planning_baseline_whatif_a"),
)


def _planning_url(name, *args):
    return reverse(f"projects:{name}", args=args)


def _planning_login_url():
    return reverse("accounts:login")


def _planning_body(response):
    return response.content.decode()


def _planning_pks(response, key="object_list"):
    return [row.pk for row in response.context[key]]


def _planning_snapshot(obj):
    """Every stored column of one row, read back from the database.

    A refused POST has to leave the row byte-for-byte as it was, and a status-only comparison
    would miss a stamped ``actual_date``, a flipped ``is_active`` or a re-minted ``number``.
    Returns ``None`` once the row is gone, which is itself a loud failure signal in an
    "unchanged" assertion.
    """
    return type(obj)._default_manager.filter(pk=obj.pk).values().first()


def _planning_deltas(before, after):
    if before is None or after is None:
        return {"__row__": (before, after)}
    return {name: (before[name], after[name])
            for name in before if before[name] != after[name]}


def _planning_unchanged(obj, before, label=""):
    deltas = _planning_deltas(before, _planning_snapshot(obj))
    assert deltas == {}, f"a refused request wrote to the row {label}: {deltas}"


def _planning_confirm_literals(body):
    """Every ``confirm('...')`` literal on a rendered page, in document order.

    The planning templates quote their confirm strings with single quotes and interpolate only
    ``{{ obj.number }}`` (digits and a prefix), so a simple non-apostrophe capture is exact for
    as-built markup - and would also catch a future free-text interpolation the moment it
    rendered, which is the point.
    """
    return re.findall(r"confirm\('([^']*)'\)", body)


def _planning_task_payload(project, **overrides):
    """A valid ``TaskForm`` POST - only ``project`` and ``name`` are required."""
    today = _planning_today()
    payload = {
        "project": str(project.pk),
        "name": "Framing package",
        "node_type": "work_package",
        "status": "planned",
        "planned_start": today.isoformat(),
        "planned_end": (today + datetime.timedelta(days=4)).isoformat(),
        "effort_hours": "40.00",
        "estimation_method": "bottom_up",
        "confidence": "medium",
        "sequence": "1",
    }
    payload.update(overrides)
    return payload


def _planning_dependency_payload(predecessor, successor, **overrides):
    payload = {
        "predecessor": str(predecessor.pk),
        "successor": str(successor.pk),
        "link_type": "finish_to_start",
        "lag_days": "0",
        "note": "Roof must be on before the paint crew starts.",
    }
    payload.update(overrides)
    return payload


def _planning_milestone_payload(project, **overrides):
    payload = {
        "project": str(project.pk),
        "name": "Permit gate",
        "description": "The building permit is in hand.",
        "target_date": (_planning_today() + datetime.timedelta(days=30)).isoformat(),
        "is_phase_gate": "on",
        "entry_criteria": "Drawings signed.",
        "exit_criteria": "Permit issued.",
    }
    payload.update(overrides)
    return payload


def _planning_baseline_payload(project, **overrides):
    payload = {
        "project": str(project.pk),
        "name": "Two-week compression",
        "baseline_type": "what_if",
        "strategy_note": "Crash the framing crew.",
        "note": "Costed against the current plan.",
    }
    payload.update(overrides)
    return payload


# ==================================================================================================
# 1. Cross-tenant IDOR - 404 on every pk route, with the row untouched
# ==================================================================================================

@pytest.mark.parametrize("route,fixture", _PLANNING_FOREIGN_GET_PROBES)
def test_planning_cross_tenant_detail_and_edit_are_404(client_a, request, route, fixture):
    """Tenant A's ADMIN GETs tenant B's detail and edit pages. 404 each - never 403 (which would
    confirm the row exists) and never 500. The admin actor is deliberate: on the gated verbs the
    role check runs before the lookup, so only an admin actually reaches the tenant scope check
    that a broken scoping would defeat."""
    obj = request.getfixturevalue(fixture)

    resp = client_a.get(_planning_url(route, obj.pk))

    assert resp.status_code == 404, route
    assert obj.number not in _planning_body(resp), route


@pytest.mark.parametrize("route,fixture", _PLANNING_FOREIGN_DELETE_PROBES)
def test_planning_cross_tenant_delete_post_is_404_and_row_intact(client_a, request, route,
                                                                 fixture):
    """The deletes are the sharpest IDOR: a scoping slip would not merely READ another workspace's
    row but DESTROY it. 404, the row still exists, and it is byte-for-byte what it was."""
    obj = request.getfixturevalue(fixture)
    before = _planning_snapshot(obj)

    resp = client_a.post(_planning_url(route, obj.pk), {})

    assert resp.status_code == 404, route
    assert type(obj)._default_manager.filter(pk=obj.pk).exists(), route
    _planning_unchanged(obj, before, route)


@pytest.mark.parametrize("verb,fixture", _PLANNING_FOREIGN_VERB_PROBES)
def test_planning_cross_tenant_verbs_are_404(client_a, request, verb, fixture):
    """``mst_achieve`` / ``bsl_activate`` / ``bsl_promote`` aimed by tenant A's admin at tenant B's
    pks: 404, and B's rows are untouched. ``planning_baseline_b`` is a what_if, i.e. a row BOTH
    baseline verbs would act on if the scope check ever let them through."""
    target = request.getfixturevalue(fixture)
    before = _planning_snapshot(target)

    resp = client_a.post(_planning_url(verb, target.pk), {})

    assert resp.status_code == 404, verb
    _planning_unchanged(target, before, verb)


# ==================================================================================================
# 2. Method and role gates on the POST-only routes
# ==================================================================================================

@pytest.mark.parametrize("route,fixture", _PLANNING_POST_ONLY_PROBES)
def test_planning_verbs_are_post_only(client_a, request, route, fixture):
    """All seven POST-only routes answer a GET with 405. The actor is the admin, so the login and
    role gates pass and the 405 is genuinely the method check - and each target row is in a state
    its verb would ACCEPT, so the assertion cannot be passing via a state refusal that happens to
    precede the lookup."""
    target = request.getfixturevalue(fixture)

    resp = client_a.get(_planning_url(route, target.pk))

    assert resp.status_code == 405, route


@pytest.mark.parametrize("verb,fixture", (
    ("mst_achieve", "planning_milestone_a"),
    ("bsl_activate", "planning_baseline_frozen_a"),
    ("bsl_promote", "planning_baseline_whatif_a"),
))
def test_planning_admin_gated_verbs_403_for_member_and_succeed_for_admin(
        client_a, member_client, request, verb, fixture):
    """THE role gate. ``mst_achieve`` / ``bsl_activate`` / ``bsl_promote`` are the 7.2 verbs that
    move governance state, and each is POSTed here by a tenant-A MEMBER at an OWN-tenant row whose
    state gate would ACCEPT it: 403 (PermissionDenied), ZERO field deltas. The admin replay on the
    same row then does the work - without that control, every 403 above would also pass on a row
    whose state gate refuses everybody (the 403 was the ROLE, not the row)."""
    target = request.getfixturevalue(fixture)
    before = _planning_snapshot(target)

    refused = member_client.post(_planning_url(verb, target.pk), {})
    assert refused.status_code == 403, verb
    _planning_unchanged(target, before, verb)

    allowed = client_a.post(_planning_url(verb, target.pk), {})
    assert allowed.status_code == 302, verb
    target.refresh_from_db()
    landed = {
        "mst_achieve": lambda: (target.status == "achieved"
                                and target.actual_date == _planning_today()),
        "bsl_activate": lambda: target.is_active is True,
        "bsl_promote": lambda: (target.baseline_type == "baseline"
                                and target.is_active is True
                                and target.frozen_on == _planning_today()),
    }[verb]()
    assert landed, verb


# ==================================================================================================
# 3. The I4 template guard - the admin buttons never render for a member
# ==================================================================================================

def test_planning_member_detail_pages_hide_the_admin_verbs(
        client_a, member_client, planning_milestone_a, planning_baseline_whatif_a,
        planning_baseline_frozen_a):
    """I4. Rendering a button the view will 403 is a UX lie that invites the POST; the detail
    templates therefore wrap the verb forms in
    ``{% if request.user.is_superuser or request.user.is_tenant_admin %}``. Pinned as exact page
    strings per the contract: the member's planned-milestone page has no "Mark Achieved" while the
    admin's does; the member's what-if page has no "Promote to Baseline" and their inactive-frozen
    page no "Activate", while the admin's pages show both. Edit links stay for everyone."""
    member_mst = member_client.get(_planning_url("mst_detail", planning_milestone_a.pk))
    assert member_mst.status_code == 200
    assert "Mark Achieved" not in _planning_body(member_mst)

    admin_mst = client_a.get(_planning_url("mst_detail", planning_milestone_a.pk))
    assert admin_mst.status_code == 200
    assert "Mark Achieved" in _planning_body(admin_mst)

    member_whatif = member_client.get(_planning_url("bsl_detail", planning_baseline_whatif_a.pk))
    assert member_whatif.status_code == 200
    assert "Promote to Baseline" not in _planning_body(member_whatif)

    admin_whatif = client_a.get(_planning_url("bsl_detail", planning_baseline_whatif_a.pk))
    assert admin_whatif.status_code == 200
    assert "Promote to Baseline" in _planning_body(admin_whatif)

    member_frozen = member_client.get(_planning_url("bsl_detail", planning_baseline_frozen_a.pk))
    assert member_frozen.status_code == 200
    assert "Activate" not in _planning_body(member_frozen)

    admin_frozen = client_a.get(_planning_url("bsl_detail", planning_baseline_frozen_a.pk))
    assert admin_frozen.status_code == 200
    assert "Activate" in _planning_body(admin_frozen)


# ==================================================================================================
# 4. Cross-tenant FK smuggling at the ROUTE - each with a same-tenant control
# ==================================================================================================
#
# The forms lane proves the FIELD rejects a foreign pk. This proves the same thing where an
# attacker actually stands: a valid create POST with a foreign FK in it, paired with a same-tenant
# control that DOES create - so a malformed payload cannot fake a pass.

def test_planning_crafted_cross_tenant_post_creates_nothing(
        client_a, tenant_a, planning_project_a, planning_project_b, planning_task_a,
        planning_task_b):
    """``client_a`` POSTs each create form carrying tenant-B FKs (task: ``project`` AND ``parent``;
    dependency: ``successor``; milestone: ``project`` AND ``anchor_task``; baseline:
    ``project``). Each answers 200 with the field in error and NO row is created anywhere; each
    paired same-tenant control POST then creates, proving the payloads were well formed and the
    refusals are the tenant scoping."""
    local_sibling = _planning_task(tenant_a, planning_project_a, name="Local control sibling")
    before = {model: model.objects.count()
              for model in (ProjectTask, TaskDependency, ProjectMilestone, ScheduleBaseline)}

    resp = client_a.post(_planning_url("tsk_create"), _planning_task_payload(
        planning_project_b, parent=str(planning_task_b.pk), name="Smuggled task"))
    assert resp.status_code == 200
    assert "project" in resp.context["form"].errors
    assert "parent" in resp.context["form"].errors
    assert ProjectTask.objects.count() == before[ProjectTask]

    resp = client_a.post(_planning_url("dep_create"), _planning_dependency_payload(
        planning_task_a, planning_task_b))
    assert resp.status_code == 200
    assert "successor" in resp.context["form"].errors
    assert TaskDependency.objects.count() == before[TaskDependency]

    resp = client_a.post(_planning_url("mst_create"), _planning_milestone_payload(
        planning_project_b, anchor_task=str(planning_task_b.pk), name="Smuggled milestone"))
    assert resp.status_code == 200
    assert "project" in resp.context["form"].errors
    assert "anchor_task" in resp.context["form"].errors
    assert ProjectMilestone.objects.count() == before[ProjectMilestone]

    resp = client_a.post(_planning_url("bsl_create"), _planning_baseline_payload(
        planning_project_b, name="Smuggled baseline"))
    assert resp.status_code == 200
    assert "project" in resp.context["form"].errors
    assert ScheduleBaseline.objects.count() == before[ScheduleBaseline]

    # The controls: the identical POSTs against tenant A's own rows DO create.
    resp = client_a.post(_planning_url("tsk_create"), _planning_task_payload(
        planning_project_a, name="Local control task"))
    assert resp.status_code == 302
    assert ProjectTask.objects.get(name="Local control task").tenant_id == tenant_a.pk

    resp = client_a.post(_planning_url("dep_create"), _planning_dependency_payload(
        planning_task_a, local_sibling))
    assert resp.status_code == 302
    assert TaskDependency.objects.filter(
        predecessor=planning_task_a, successor=local_sibling).exists()

    resp = client_a.post(_planning_url("mst_create"), _planning_milestone_payload(
        planning_project_a, name="Local control milestone"))
    assert resp.status_code == 302
    assert ProjectMilestone.objects.get(name="Local control milestone").tenant_id == tenant_a.pk

    resp = client_a.post(_planning_url("bsl_create"), _planning_baseline_payload(
        planning_project_a, name="Local control baseline"))
    assert resp.status_code == 302
    created = ScheduleBaseline.objects.get(name="Local control baseline")
    assert created.tenant_id == tenant_a.pk and created.baseline_type == "what_if"

    after = {model: model.objects.count()
             for model in (ProjectTask, TaskDependency, ProjectMilestone, ScheduleBaseline)}
    assert {model: after[model] - before[model]
            for model in before} == {ProjectTask: 1, TaskDependency: 1, ProjectMilestone: 1,
                                     ScheduleBaseline: 1}


# ==================================================================================================
# 5. The edit locks at the route (I1 / I2) - login-only routes a member can reach
# ==================================================================================================

def test_planning_member_cannot_flip_baseline_type_through_edit(
        member_client, planning_baseline_whatif_a):
    """I1 at the route. ``bsl_edit`` is login-only, so a member reaches it - and a hand-crafted
    POST flipping ``baseline_type`` to ``baseline`` would mint an evidence-less frozen row, which
    is why the form locks the type on edit (only the gated ``bsl_promote`` may move it, with its
    snapshot and audit row). The POST answers 200 with the field in error, the row is unchanged -
    still a what-if, no snapshot columns filled, still inactive - and the row is STILL editable
    (the lock is on the type, not the route)."""
    row = planning_baseline_whatif_a
    before = _planning_snapshot(row)

    resp = member_client.post(_planning_url("bsl_edit", row.pk), _planning_baseline_payload(
        row.project, name="Renamed by member", baseline_type="baseline"))

    assert resp.status_code == 200
    assert "baseline_type" in resp.context["form"].errors
    _planning_unchanged(row, before, "bsl_edit")
    row.refresh_from_db()
    assert row.baseline_type == "what_if"
    assert row.frozen_on is None and row.planned_finish is None
    assert row.task_count is None and row.total_effort_hours is None
    assert row.is_active is False

    assert member_client.get(_planning_url("bsl_edit", row.pk)).status_code == 200


def test_planning_member_cannot_move_milestone_status_through_edit(
        member_client, planning_milestone_a):
    """I2 at the route. ``mst_edit`` is login-only and the edit itself is member-legal, so a member
    POSTs VALID data with a smuggled ``status=achieved`` - and the edit LANDS (the name changes,
    proving the pass is not a silent refusal) while ``status`` stays ``planned`` and
    ``actual_date`` stays empty: status is not a form field, it moves only through the gated
    ``mst_achieve``."""
    obj = planning_milestone_a

    resp = member_client.post(_planning_url("mst_edit", obj.pk), _planning_milestone_payload(
        obj.project, name="Renamed by member", status="achieved"))

    assert resp.status_code == 302
    obj.refresh_from_db()
    assert obj.name == "Renamed by member"
    assert obj.status == "planned"
    assert obj.actual_date is None


# ==================================================================================================
# 6. The tenant=None user and the login wall
# ==================================================================================================

def test_planning_tenantless_user_sees_empty_registers_and_anonymous_is_redirected_to_login(
        request, planning_tenantless_client, planning_anon_client, planning_task_a,
        planning_task_b, planning_dependency_a, planning_dependency_b, planning_milestone_a,
        planning_milestone_b, planning_baseline_whatif_a, planning_baseline_b,
        planning_baseline_frozen_a):
    """The two actors that own no rows.

    The superuser shape (``tenant=None`` - also any member of a deleted workspace) gets 200 on
    every register with an EMPTY ``object_list`` and an empty project dropdown: ``filter(tenant
    is None)`` matches nothing, and the failure this guards against is a view that special-cased
    the missing tenant into "show everything". No row number from either workspace rides out on
    the empty state. The four create views turn them away on their FIRST line - 302 to
    ``dashboard:home``, nothing written. An anonymous caller is redirected to login on every
    register, and the seven POST-only routes answer the redirect BEFORE the mutation: each is
    re-posted against a REAL tenant-A row and the row survives byte-for-byte.
    """
    every_row = (planning_task_a, planning_task_b, planning_dependency_a, planning_dependency_b,
                 planning_milestone_a, planning_milestone_b, planning_baseline_whatif_a,
                 planning_baseline_b, planning_baseline_frozen_a)

    for route in _PLANNING_REGISTERS:
        resp = planning_tenantless_client.get(_planning_url(route))
        assert resp.status_code == 200, route
        assert _planning_pks(resp) == [], route
        assert list(resp.context["projects"]) == [], route
        body = _planning_body(resp)
        for row in every_row:
            assert row.number not in body, (route, row.number)

    before = {model: model.objects.count()
              for model in (ProjectTask, TaskDependency, ProjectMilestone, ScheduleBaseline)}
    for route in ("tsk_create", "dep_create", "mst_create", "bsl_create"):
        resp = planning_tenantless_client.post(_planning_url(route), {})
        assert resp.status_code == 302, route
        assert resp["Location"] == reverse("dashboard:home"), route
    assert {model: model.objects.count()
            for model in (ProjectTask, TaskDependency, ProjectMilestone,
                          ScheduleBaseline)} == before

    for route in _PLANNING_REGISTERS:
        resp = planning_anon_client.get(_planning_url(route))
        assert resp.status_code == 302, route
        assert resp["Location"].startswith(_planning_login_url()), route

    for verb, fixture in _PLANNING_ANON_VERB_PROBES:
        row = request.getfixturevalue(fixture)
        before_row = _planning_snapshot(row)
        resp = planning_anon_client.post(_planning_url(verb, row.pk), {})
        assert resp.status_code == 302, verb
        assert resp["Location"].startswith(_planning_login_url()), verb
        _planning_unchanged(row, before_row, verb)


# ==================================================================================================
# 7. Template hygiene - comments never render, confirms interpolate numbers only
# ==================================================================================================

def test_planning_no_template_comment_markers_leak(request, client_a, member_client,
                                                   planning_project_a, planning_project_b,
                                                   planning_task_a, planning_dependency_a,
                                                   planning_milestone_a,
                                                   planning_baseline_whatif_a):
    """As admin AND member: the four registers, the WBS tree and the three verb-carrying detail
    pages render 200 with NEITHER ``{#`` NOR ``{% comment`` in the body - a template comment that
    reaches the wire is either a disclosure of intent or a broken tag.

    The same renders pin the confirm() rule: every ``confirm('...')`` on the list pages
    interpolates NUMBERS only (each literal carries a digit - the ``{{ obj.number }}`` - and
    neither workspace's project NAME ever appears in one, which is what a free-text interpolation
    like ``obj.project.name`` would put there). The exact leak the rule exists for is asserted on
    the rendered baseline detail HTML: the raw expression never rides out on any page, admin or
    member.
    """
    for client in (client_a, member_client):
        for route in _PLANNING_RENDER_ROUTES:
            resp = client.get(_planning_url(route))
            assert resp.status_code == 200, route
            body = _planning_body(resp)
            assert "{#" not in body, route
            assert "{% comment" not in body, route
        for route, fixture in _PLANNING_DETAIL_PROBES:
            row = request.getfixturevalue(fixture)
            resp = client.get(_planning_url(route, row.pk))
            assert resp.status_code == 200, route
            body = _planning_body(resp)
            assert "{#" not in body, route
            assert "{% comment" not in body, route
            assert "obj.project.name" not in body, route

        for route in _PLANNING_REGISTERS:
            body = _planning_body(client.get(_planning_url(route)))
            literals = _planning_confirm_literals(body)
            assert literals, f"{route}: no confirm() rendered - the assertion would be vacuous"
            for literal in literals:
                assert any(character.isdigit() for character in literal), (route, literal)
                assert planning_project_a.name not in literal, (route, literal)
                assert planning_project_b.name not in literal, (route, literal)


# ==================================================================================================
# 8. The tenant-scoping contract (7.1 lane style) - scoped FK, no reverse accessor
# ==================================================================================================

@pytest.mark.parametrize("model,accessor", (
    (ProjectTask, "projecttask_set"),
    (TaskDependency, "taskdependency_set"),
    (ProjectMilestone, "projectmilestone_set"),
    (ScheduleBaseline, "schedulebaseline_set"),
))
def test_planning_tenant_fk_has_no_reverse_accessor(model, accessor, tenant_a):
    """Every planning model takes ``tenant`` from the shared ``TenantNumbered`` base: a NON-null
    CASCADE FK to ``core.Tenant`` with ``related_name="+"`` - the views always filter by
    ``request.tenant``, so no reverse accessor is created and the abstract base never clashes
    across its many subclasses. If a model ever grows a reverse tenant accessor (or the base drops
    the ``+``), this fails as a visible decision rather than silently changing what a tenant
    object exposes."""
    field = model._meta.get_field("tenant")
    assert field.related_model._meta.label == "core.Tenant", model.__name__
    assert field.null is False, model.__name__
    assert field.remote_field.on_delete.__name__ == "CASCADE", model.__name__
    assert field.remote_field.related_name == "+", model.__name__
    assert not hasattr(tenant_a, accessor), accessor
