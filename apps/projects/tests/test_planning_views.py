"""Projects 7.2 Project Planning & Scheduling - VIEW tests.

The HTTP layer of the sub-module: 24 routes, the five registers + the WBS tree they render, every
context key the test contract pins, search/filter/junk/pagination behaviour, the CRUD round-trips
through real POSTs, and the verbs' state machines (achieve / activate / promote / frozen refusals).
Model invariants belong to ``test_planning_models.py`` and form validation to
``test_planning_forms.py``; role gating (403), cross-tenant IDOR (404), CSRF and anonymous access
belong to ``test_planning_security.py``. Every request here is made by a TENANT ADMIN
(root conftest's ``client_a`` - there is deliberately no ``planning_client``), so the only thing
that can refuse a verb in this lane is its own state gate.

What this lane exists to catch:

* **A blank region that returns 200.** A mismatched context key renders nothing and reports
  success, so every register/tree test asserts CONTENT - the row's own ``TSK-/DEP-/MST-/BSL-``
  number in the body - and then asserts each pinned key by name (``object_list`` / ``page_obj`` /
  ``q`` + the ``*_choices`` / ``projects`` extras) and the template hygiene markers (``{#`` and
  ``{% comment`` must never leak into rendered list/tree pages).
* **A filter that silently empties a register.** Every documented control is compared against the
  ORM's own answer for the same narrowing, and the junk values (``?status=nope``, ``?project=abc``,
  ``?project=0``, an over-range pk) must return the FULL register at 200 - never a 500, never an
  empty page (L9/L11).
* **A tree that renders undecorated rows.** ``tsk_tree`` hangs the DECORATED child instances on
  ``node.kids``; rendering through ``node.children.all`` would show rows without ``wbs_code``,
  rollups or the critical badge - so the tests walk the context's own instances and the body.
* **A verb that writes when it should refuse.** Achieve/activate/promote are exercised on both
  sides: the happy path, then every now-forbidden source state, each of which must answer with a
  message, a redirect, and leave the row as it was.

Determinism (L16): every date basis is ``timezone.localdate()`` (via the conftest's
``_planning_today``). ``datetime.date.today()`` never appears. Nothing here touches the network or
the demo seeder - every test builds exactly the rows it asserts on from the conftest factories.

Naming (mandatory): every test is ``test_planning_*`` and every module-level helper
``_planning_*`` / ``_PLANNING_*``, so neither lane of this package can shadow the other.

This file is pure ASCII on purpose. Several 7.2 messages carry U+2014, so every message assertion
below matches an ASCII SUBSTRING - a copy edit must not turn into a red suite.
"""
import datetime
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from apps.projects.models import ProjectMilestone, ProjectTask, ScheduleBaseline, TaskDependency
from apps.projects.tests.conftest import (
    PLANNING_PAGE_SIZE,
    _planning_baseline,
    _planning_dependency,
    _planning_fill_tasks,
    _planning_milestone,
    _planning_task,
    _planning_today,
    _planning_wbs_tree,
    _projectinitiation_project,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Module-level helpers - every one ``_planning_*`` for the same reason the tests are (Python binds
# the LAST module-level definition, so an unprefixed helper here would silently rebind a sibling
# lane's). Record factories come from the conftest, which OWNS them.
# ==================================================================================================

#: The four registers, with the model each one lists and the template it must render.
_PLANNING_REGISTERS = (
    ("tsk_list", ProjectTask, "projects/planning/task/list.html"),
    ("dep_list", TaskDependency, "projects/planning/taskdependency/list.html"),
    ("mst_list", ProjectMilestone, "projects/planning/milestone/list.html"),
    ("bsl_list", ScheduleBaseline, "projects/planning/schedulebaseline/list.html"),
)


def _planning_url(name, *args):
    return reverse(f"projects:{name}", args=args)


def _planning_get(client, name, /, *args, **params):
    return client.get(_planning_url(name, *args), params)


def _planning_post(client, name, /, *args, data=None, follow=False):
    """POST one 7.2 route. CSRF is off on the ordinary test client - the enforced-CSRF pair
    belongs to the security lane."""
    return client.post(_planning_url(name, *args), data or {}, follow=follow)


def _planning_messages(response):
    """Every message queued on the request that produced ``response``, as plain strings.

    Read off the REQUEST rather than the rendered page: the verbs all redirect, so nothing has
    rendered - and therefore consumed - the storage yet.
    """
    return [str(message) for message in get_messages(response.wsgi_request)]


def _planning_said(response, fragment):
    """True when any queued message contains ``fragment`` (ASCII substrings only - several 7.2
    messages carry U+2014, and matching a whole sentence would turn a copy edit into a red suite)."""
    return any(fragment in message for message in _planning_messages(response))


def _planning_body(response):
    return response.content.decode()


def _planning_templates(response):
    """Every template name that rendered, including ``base.html`` and the widget partials."""
    return [template.name for template in response.templates if template.name]


def _planning_pks(response, key="object_list"):
    """The primary keys the page actually rendered, in order."""
    return [row.pk for row in response.context[key]]


def _planning_snapshot(obj):
    """Every concrete column of ``obj``, read FRESH from the database. ``updated_at`` is
    ``auto_now``, so it is in here deliberately: a refusal that still reaches ``save()`` moves it,
    and a snapshot comparison is the only thing that catches a "refusal" which writes nothing
    visible but writes."""
    fresh = type(obj)._default_manager.get(pk=obj.pk)
    return {field.attname: getattr(fresh, field.attname)
            for field in fresh._meta.concrete_fields}


def _planning_unchanged(obj, before):
    """Assert ``obj``'s row is byte-for-byte what ``before`` recorded."""
    after = _planning_snapshot(obj)
    deltas = {name: (before[name], after[name]) for name in before if before[name] != after[name]}
    assert deltas == {}, f"a refused verb wrote to the row: {deltas}"


def _planning_assert_narrows(client, route, model, tenant, params, lookups):
    """The register's answer for ``params`` must equal the ORM's answer for ``lookups`` - and be
    strictly smaller than the unfiltered register, so a control that does nothing fails too."""
    expected = set(model.objects.filter(tenant=tenant, **lookups).values_list("pk", flat=True))
    total = model.objects.filter(tenant=tenant).count()
    assert expected, "the scenario has no row for this filter value - the test proves nothing"
    assert len(expected) < total, "this filter value matches every row - it cannot narrow"
    resp = _planning_get(client, route, **params)
    assert resp.status_code == 200
    assert set(_planning_pks(resp)) == expected
    return resp


def _planning_task_payload(project, **overrides):
    """A valid ``TaskForm`` POST - only ``project`` and ``name`` are required; the rest is the
    shape the form itself would submit."""
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
        "lag_days": "2",
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


def _planning_task_filter_scenario(tenant, project, other_project):
    """A workspace with a known answer for every task-register filter.

    Four work packages on ``project`` (the default bottom_up/planned shape, a ``done`` one, a
    ``deliverable``, a ``parametric`` one) plus one task on ``other_project`` - each needle
    distinct so a filter that matches everything fails the "cannot narrow" guard.
    """
    plain = _planning_task(tenant, project, name="Scaffold the depot roof",
                           description="A needle in the description.")
    done = _planning_task(tenant, project, name="Paint the done shutters", status="done")
    deliverable = _planning_task(tenant, project, name="Envelope deliverable",
                                 node_type="deliverable", planned_start=None, planned_end=None,
                                 effort_hours=None)
    parametric = _planning_task(tenant, project, name="Parametric pour estimate",
                                estimation_method="parametric")
    elsewhere = _planning_task(tenant, other_project, name="A task in the other project")
    return plain, done, deliverable, parametric, elsewhere


# ==================================================================================================
# 1. The four registers - context keys, content, search and filters
# ==================================================================================================

def test_planning_task_register_renders_context_keys_and_content(
        client_a, tenant_a, planning_project_a, planning_task_a):
    resp = _planning_get(client_a, "tsk_list")
    assert resp.status_code == 200
    assert "projects/planning/task/list.html" in _planning_templates(resp)
    for key in ("object_list", "page_obj", "q", "status_choices", "node_type_choices",
                "estimation_method_choices", "projects"):
        assert key in resp.context, f"tsk_list dropped its pinned key: {key}"
    assert resp.context["status_choices"] == ProjectTask.STATUS_CHOICES
    assert resp.context["node_type_choices"] == ProjectTask.NODE_TYPE_CHOICES
    assert resp.context["estimation_method_choices"] == ProjectTask.ESTIMATION_CHOICES
    assert resp.context["page_obj"].paginator.per_page == PLANNING_PAGE_SIZE
    assert planning_project_a in list(resp.context["projects"])
    body = _planning_body(resp)
    # CONTENT, not just status: a mis-named key renders an empty <div> at 200.
    assert planning_task_a.number in body
    assert planning_task_a.name in body
    assert "{#" not in body and "{% comment" not in body


def test_planning_task_register_search_and_filters(
        client_a, tenant_a, planning_project_a, planning_project_b):
    """``?q=`` hits name/number/description; every enum + the project filter narrow to the ORM's
    own answer; a no-match search empties the register LEGITIMATELY (200, not an error)."""
    other_project = _projectinitiation_project(
        tenant_a, name="Filter scenario second host", code="FSH-01", status="active",
        charter_status="approved")
    plain, done, deliverable, parametric, elsewhere = _planning_task_filter_scenario(
        tenant_a, planning_project_a, other_project)

    # Search: name, number, and the description needle (icontains).
    resp = _planning_get(client_a, "tsk_list", q="depot roof")
    assert resp.status_code == 200
    assert _planning_pks(resp) == [plain.pk]
    assert resp.context["q"] == "depot roof"
    assert _planning_pks(_planning_get(client_a, "tsk_list", q=done.number)) == [done.pk]
    assert _planning_pks(_planning_get(client_a, "tsk_list", q="needle in the description")) \
        == [plain.pk]
    resp = _planning_get(client_a, "tsk_list", q="zzz-no-such-task-zzz")
    assert resp.status_code == 200
    assert list(resp.context["object_list"]) == []

    # Filters narrow to the ORM answer.
    _planning_assert_narrows(client_a, "tsk_list", ProjectTask, tenant_a,
                             {"status": "done"}, {"status": "done"})
    _planning_assert_narrows(client_a, "tsk_list", ProjectTask, tenant_a,
                             {"node_type": "deliverable"}, {"node_type": "deliverable"})
    _planning_assert_narrows(client_a, "tsk_list", ProjectTask, tenant_a,
                             {"estimation_method": "parametric"},
                             {"estimation_method": "parametric"})
    _planning_assert_narrows(client_a, "tsk_list", ProjectTask, tenant_a,
                             {"project": str(planning_project_a.pk)},
                             {"project_id": planning_project_a.pk})
    # The other host's task is the only row that project filter can leave.
    _planning_assert_narrows(client_a, "tsk_list", ProjectTask, tenant_a,
                             {"project": str(other_project.pk)}, {"project_id": other_project.pk})
    assert elsewhere.pk in _planning_pks(_planning_get(
        client_a, "tsk_list", project=str(other_project.pk)))
    # tenant B's project pk is a VALID int - it filters (to nothing), it does not skip.
    resp = _planning_get(client_a, "tsk_list", project=str(planning_project_b.pk))
    assert resp.status_code == 200
    assert list(resp.context["object_list"]) == []


def test_planning_task_register_skips_junk_params(
        client_a, tenant_a, planning_project_a, planning_project_b):
    """Junk enum values and junk pks are SKIPPED, not matched: every row stays listed at 200
    (L11) - a stale bookmark must never silently empty a register."""
    other_project = _projectinitiation_project(
        tenant_a, name="Junk scenario second host", code="JSH-01", status="active",
        charter_status="approved")
    _planning_task_filter_scenario(tenant_a, planning_project_a, other_project)
    expected = set(ProjectTask.objects.filter(tenant=tenant_a).values_list("pk", flat=True))
    assert len(expected) == 5

    for params in (
        {"status": "nope", "node_type": "abc", "estimation_method": "zzz", "project": "abc"},
        {"status": "nope", "node_type": "abc", "estimation_method": "zzz", "project": "0"},
        {"status": "nope", "node_type": "abc", "estimation_method": "zzz",
         "project": "999999999999999999999"},
    ):
        resp = client_a.get(_planning_url("tsk_list"), params)
        assert resp.status_code == 200
        assert set(_planning_pks(resp)) == expected, f"junk params {params} emptied the register"


def test_planning_dependency_register_renders_context_keys_and_filters(
        client_a, tenant_a, planning_project_a, planning_dependency_a):
    dep = planning_dependency_a
    other_pred = _planning_task(tenant_a, planning_project_a, name="Sequence predecessor")
    other_succ = _planning_task(tenant_a, planning_project_a, name="Sequence successor")
    ss_dep = _planning_dependency(tenant_a, other_pred, other_succ, link_type="start_to_start")

    resp = _planning_get(client_a, "dep_list")
    assert resp.status_code == 200
    assert "projects/planning/taskdependency/list.html" in _planning_templates(resp)
    for key in ("object_list", "page_obj", "q", "link_type_choices", "projects"):
        assert key in resp.context, f"dep_list dropped its pinned key: {key}"
    assert resp.context["link_type_choices"] == TaskDependency.LINK_TYPE_CHOICES
    assert resp.context["page_obj"].paginator.per_page == PLANNING_PAGE_SIZE
    body = _planning_body(resp)
    assert dep.number in body
    assert dep.predecessor.name in body and dep.successor.name in body
    assert "{#" not in body and "{% comment" not in body

    # Search by predecessor name.
    resp = _planning_get(client_a, "dep_list", q=dep.predecessor.name)
    assert resp.status_code == 200
    assert _planning_pks(resp) == [dep.pk]
    # The link_type filter narrows; junk is skipped, not matched.
    _planning_assert_narrows(client_a, "dep_list", TaskDependency, tenant_a,
                             {"link_type": "start_to_start"}, {"link_type": "start_to_start"})
    resp = _planning_get(client_a, "dep_list", link_type="zzz")
    assert resp.status_code == 200
    assert set(_planning_pks(resp)) == {dep.pk, ss_dep.pk}


def test_planning_milestone_register_renders_context_keys_and_filters(
        client_a, tenant_a, planning_project_a, planning_project_b):
    """Milestones come back target_date-ordered (the deliberate Meta.ordering exception) and the
    status / project / is_phase_gate controls narrow; junk enums are skipped."""
    today = _planning_today()
    early = _planning_milestone(tenant_a, planning_project_a, name="Kickoff gate",
                                target_date=today + datetime.timedelta(days=10),
                                is_phase_gate=True)
    late = _planning_milestone(tenant_a, planning_project_a, name="Design freeze",
                               target_date=today + datetime.timedelta(days=20))
    achieved = _planning_milestone(tenant_a, planning_project_a, name="Permit granted",
                                   target_date=today + datetime.timedelta(days=30),
                                   status="achieved")
    other_project = _projectinitiation_project(
        tenant_a, name="Milestone scenario second host", code="MSH-01", status="active",
        charter_status="approved")
    stray = _planning_milestone(tenant_a, other_project, name="Stray milestone",
                                target_date=today + datetime.timedelta(days=5))

    resp = _planning_get(client_a, "mst_list")
    assert resp.status_code == 200
    assert "projects/planning/milestone/list.html" in _planning_templates(resp)
    for key in ("object_list", "page_obj", "q", "status_choices", "projects"):
        assert key in resp.context, f"mst_list dropped its pinned key: {key}"
    assert resp.context["status_choices"] == ProjectMilestone.STATUS_CHOICES
    body = _planning_body(resp)
    for row in (early, late, achieved):
        assert row.number in body
    # Meta.ordering ["target_date", "id"] survives crud_list (rows were created 20/10/30/5).
    assert _planning_pks(resp) == [stray.pk, early.pk, late.pk, achieved.pk]
    assert "{#" not in body and "{% comment" not in body

    _planning_assert_narrows(client_a, "mst_list", ProjectMilestone, tenant_a,
                             {"status": "achieved"}, {"status": "achieved"})
    _planning_assert_narrows(client_a, "mst_list", ProjectMilestone, tenant_a,
                             {"project": str(planning_project_a.pk)},
                             {"project_id": planning_project_a.pk})
    _planning_assert_narrows(client_a, "mst_list", ProjectMilestone, tenant_a,
                             {"is_phase_gate": "True"}, {"is_phase_gate": True})
    _planning_assert_narrows(client_a, "mst_list", ProjectMilestone, tenant_a,
                             {"is_phase_gate": "False"}, {"is_phase_gate": False})
    # Junk enum skipped - and junk boolean likewise (ValidationError inside .filter()).
    resp = _planning_get(client_a, "mst_list", status="zzz")
    assert resp.status_code == 200
    assert set(_planning_pks(resp)) == {early.pk, late.pk, achieved.pk, stray.pk}
    resp = _planning_get(client_a, "mst_list", is_phase_gate="abc", project="0")
    assert resp.status_code == 200
    assert set(_planning_pks(resp)) == {early.pk, late.pk, achieved.pk, stray.pk}


def test_planning_baseline_register_renders_context_keys_and_filters(
        client_a, tenant_a, planning_project_a, planning_project_b,
        planning_baseline_whatif_a, planning_baseline_frozen_a):
    other_project = _projectinitiation_project(
        tenant_a, name="Baseline scenario second host", code="BSH-01", status="active",
        charter_status="approved")
    stray = _planning_baseline(tenant_a, other_project, name="Other host scenario")

    resp = _planning_get(client_a, "bsl_list")
    assert resp.status_code == 200
    assert "projects/planning/schedulebaseline/list.html" in _planning_templates(resp)
    for key in ("object_list", "page_obj", "q", "baseline_type_choices", "projects"):
        assert key in resp.context, f"bsl_list dropped its pinned key: {key}"
    assert resp.context["baseline_type_choices"] == ScheduleBaseline.BASELINE_TYPE_CHOICES
    body = _planning_body(resp)
    assert planning_baseline_whatif_a.number in body
    assert planning_baseline_frozen_a.name in body
    assert "{#" not in body and "{% comment" not in body

    _planning_assert_narrows(client_a, "bsl_list", ScheduleBaseline, tenant_a,
                             {"baseline_type": "what_if"}, {"baseline_type": "what_if"})
    _planning_assert_narrows(client_a, "bsl_list", ScheduleBaseline, tenant_a,
                             {"project": str(planning_project_a.pk)},
                             {"project_id": planning_project_a.pk})
    assert stray.pk not in _planning_pks(_planning_get(
        client_a, "bsl_list", project=str(planning_project_a.pk)))
    resp = _planning_get(client_a, "bsl_list", baseline_type="zzz")
    assert resp.status_code == 200
    assert set(_planning_pks(resp)) == {planning_baseline_whatif_a.pk,
                                        planning_baseline_frozen_a.pk, stray.pk}


# ==================================================================================================
# 2. The WBS tree - decoration, the critical chain, the project picker
# ==================================================================================================

def test_planning_wbs_tree_renders_codes_rollups_and_structure(
        client_a, planning_project_a, planning_wbs_tree_a):
    """The tree view decorates IN PYTHON: position-derived WBS codes, post-order deliverable
    rollups, and the decorated instances hung on ``kids`` (the template include walks those)."""
    tree = planning_wbs_tree_a
    today = _planning_today()
    resp = _planning_get(client_a, "tsk_tree", project=str(planning_project_a.pk))
    assert resp.status_code == 200
    assert "projects/planning/task/tree.html" in _planning_templates(resp)
    assert resp.context["project"].pk == planning_project_a.pk
    assert resp.context["tree_max_depth"] == 5
    assert isinstance(resp.context["critical_ids"], set)

    roots = list(resp.context["roots"])
    assert [node.pk for node in roots] == [tree["d1"].pk, tree["d2"].pk]
    d1, d2 = roots
    assert d1.wbs_code == "1"
    assert [kid.wbs_code for kid in d1.kids] == ["1.1", "1.2"]
    assert [kid.pk for kid in d1.kids] == [tree["wp11"].pk, tree["wp12"].pk]
    assert d2.wbs_code == "2"
    assert [kid.wbs_code for kid in d2.kids] == ["2.1", "2.2"]
    # The kids are DECORATED instances - each carries its own wbs_code and rollup attrs.
    assert all(kid.wbs_code == "2.1" for kid in d2.kids if kid.pk == tree["wp21"].pk)
    assert d2.kids[0].rollup_count == 1 and d2.kids[0].rollup_effort_hours == Decimal("8.00")

    # Post-order subtree rollup on the deliverables (the children own the real windows/effort).
    assert d1.rollup_start == today
    assert d1.rollup_end == today + datetime.timedelta(days=4)
    assert d1.rollup_effort_hours == Decimal("40.00")
    assert d1.rollup_count == 2
    assert d2.rollup_start == today
    assert d2.rollup_end == today + datetime.timedelta(days=2)
    assert d2.rollup_effort_hours == Decimal("16.00")
    assert d2.rollup_count == 2

    body = _planning_body(resp)
    for code in ("1", "1.1", "1.2", "2.1", "2.2"):
        assert f'<span class="badge badge-slate">{code}</span>' in body
    assert "2 packages" in body                 # the deliverable rollup count, pluralized
    assert "40.00h" in body                     # d1's rollup effort
    assert '<select name="project"' in body     # the project picker is present
    assert "{#" not in body and "{% comment" not in body


def test_planning_wbs_tree_marks_the_critical_chain(
        client_a, tenant_a, planning_project_a, planning_wbs_tree_a):
    """One FS chain wp11 -> wp12 (3 + 2 days) beats the isolated wp21/wp22 pair: exactly the two
    chain pks come back critical, and the badge renders ONLY on the chain nodes."""
    tree = planning_wbs_tree_a
    _planning_dependency(tenant_a, tree["wp11"], tree["wp12"])

    resp = _planning_get(client_a, "tsk_tree", project=str(planning_project_a.pk))
    assert resp.status_code == 200
    assert resp.context["critical_ids"] == {tree["wp11"].pk, tree["wp12"].pk}

    roots = {node.pk: node for node in resp.context["roots"]}
    d1_kids = {kid.pk: kid for kid in roots[tree["d1"].pk].kids}
    d2_kids = {kid.pk: kid for kid in roots[tree["d2"].pk].kids}
    assert d1_kids[tree["wp11"].pk].is_critical is True
    assert d1_kids[tree["wp12"].pk].is_critical is True
    assert d2_kids[tree["wp21"].pk].is_critical is False
    assert d2_kids[tree["wp22"].pk].is_critical is False

    body = _planning_body(resp)
    assert body.count('<span class="badge badge-red">Critical</span>') == 2


def test_planning_wbs_tree_project_picker_honored_and_junk_ignored(
        client_a, tenant_a, planning_project_a, planning_project_b,
        planning_tenantless_client):
    """``?project=<own pk>`` is honored; a foreign pk, junk or an absent param fall back to the
    tenant's FIRST project by name (never another workspace's); a tenant-less user gets
    ``project=None`` with empty roots - 200, never a 500."""
    earlier = _projectinitiation_project(
        tenant_a, name="Aaa earlier site works", code="AES-01", status="active",
        charter_status="approved")          # sorts before "Planning host Alpha" by name

    resp = _planning_get(client_a, "tsk_tree", project=str(planning_project_a.pk))
    assert resp.context["project"].pk == planning_project_a.pk

    resp = _planning_get(client_a, "tsk_tree", project=str(planning_project_b.pk))
    assert resp.status_code == 200
    assert resp.context["project"].pk == earlier.pk      # tenant A's first by name, never B's

    resp = _planning_get(client_a, "tsk_tree", project="abc")
    assert resp.status_code == 200
    assert resp.context["project"].pk == earlier.pk
    resp = _planning_get(client_a, "tsk_tree")
    assert resp.context["project"].pk == earlier.pk

    resp = _planning_get(planning_tenantless_client, "tsk_tree")
    assert resp.status_code == 200
    assert resp.context["project"] is None
    assert list(resp.context["roots"]) == []
    assert list(resp.context["projects"]) == []


# ==================================================================================================
# 3. CRUD round-trips - the rows actually land, edit, and leave
# ==================================================================================================

def test_planning_task_crud_round_trip(client_a, tenant_a, planning_project_a):
    # GET create renders an unbound form with `is_edit` False and NO `obj`.
    resp = _planning_get(client_a, "tsk_create")
    assert resp.status_code == 200
    assert resp.context["is_edit"] is False
    assert "obj" not in resp.context
    assert not resp.context["form"].is_bound

    payload = _planning_task_payload(planning_project_a, name="Framing package")
    resp = _planning_post(client_a, "tsk_create", data=payload)
    assert resp.status_code == 302
    obj = ProjectTask.objects.get(name="Framing package")
    assert resp["Location"] == _planning_url("tsk_detail", obj.pk)
    assert obj.number.startswith("TSK-") and obj.tenant_id == tenant_a.pk

    resp = _planning_get(client_a, "tsk_detail", obj.pk)
    assert resp.status_code == 200
    body = _planning_body(resp)
    assert obj.number in body and "Framing package" in body

    resp = _planning_get(client_a, "tsk_edit", obj.pk)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["obj"].pk == obj.pk

    resp = _planning_post(client_a, "tsk_edit", obj.pk,
                          data=_planning_task_payload(planning_project_a,
                                                      name="Framing package, rescoped"))
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("tsk_list")
    obj.refresh_from_db()
    assert obj.name == "Framing package, rescoped"

    resp = _planning_post(client_a, "tsk_delete", obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("tsk_list")
    assert _planning_get(client_a, "tsk_detail", obj.pk).status_code == 404


def test_planning_dependency_crud_round_trip(client_a, tenant_a, planning_project_a):
    pred = _planning_task(tenant_a, planning_project_a, name="Round trip predecessor")
    succ = _planning_task(tenant_a, planning_project_a, name="Round trip successor")

    resp = _planning_post(
        client_a, "dep_create",
        data=_planning_dependency_payload(pred, succ, link_type="start_to_start", lag_days="2"))
    assert resp.status_code == 302
    obj = TaskDependency.objects.get(predecessor=pred, successor=succ)
    assert resp["Location"] == _planning_url("dep_detail", obj.pk)
    assert obj.number.startswith("DEP-") and obj.tenant_id == tenant_a.pk
    assert obj.link_type == "start_to_start" and obj.lag_days == 2

    resp = _planning_get(client_a, "dep_detail", obj.pk)
    assert resp.status_code == 200
    body = _planning_body(resp)
    assert obj.number in body and pred.name in body and succ.name in body

    resp = _planning_get(client_a, "dep_edit", obj.pk)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["obj"].pk == obj.pk

    resp = _planning_post(
        client_a, "dep_edit", obj.pk,
        data=_planning_dependency_payload(pred, succ, link_type="finish_to_start",
                                          lag_days="-1", note="Re-sequenced with a one-day lead."))
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("dep_list")
    obj.refresh_from_db()
    assert obj.link_type == "finish_to_start" and obj.lag_days == -1
    assert obj.note == "Re-sequenced with a one-day lead."

    resp = _planning_post(client_a, "dep_delete", obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("dep_list")
    assert _planning_get(client_a, "dep_detail", obj.pk).status_code == 404


def test_planning_milestone_crud_round_trip(client_a, tenant_a, planning_project_a):
    resp = _planning_post(client_a, "mst_create",
                          data=_planning_milestone_payload(planning_project_a))
    assert resp.status_code == 302
    obj = ProjectMilestone.objects.get(name="Permit gate")
    assert resp["Location"] == _planning_url("mst_detail", obj.pk)
    assert obj.number.startswith("MST-") and obj.tenant_id == tenant_a.pk
    # `status` is NOT a form field: a fresh milestone is always born planned, stamp-less.
    assert obj.status == "planned" and obj.actual_date is None
    assert obj.is_phase_gate is True

    resp = _planning_get(client_a, "mst_detail", obj.pk)
    assert resp.status_code == 200
    body = _planning_body(resp)
    assert obj.number in body and "Permit gate" in body

    resp = _planning_get(client_a, "mst_edit", obj.pk)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["obj"].pk == obj.pk

    resp = _planning_post(client_a, "mst_edit", obj.pk,
                          data=_planning_milestone_payload(planning_project_a,
                                                           name="Permit gate, moved"))
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("mst_list")
    obj.refresh_from_db()
    assert obj.name == "Permit gate, moved"
    assert obj.status == "planned"          # the edit can never smuggle a status change

    resp = _planning_post(client_a, "mst_delete", obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("mst_list")
    assert _planning_get(client_a, "mst_detail", obj.pk).status_code == 404


def test_planning_baseline_crud_round_trip_what_if(client_a, tenant_a, planning_project_a):
    resp = _planning_post(client_a, "bsl_create",
                          data=_planning_baseline_payload(planning_project_a))
    assert resp.status_code == 302
    obj = ScheduleBaseline.objects.get(name="Two-week compression")
    assert resp["Location"] == _planning_url("bsl_detail", obj.pk)
    assert obj.number.startswith("BSL-") and obj.tenant_id == tenant_a.pk
    # A what-if is born neither frozen nor active, with NO snapshot (that is promote's job).
    assert obj.baseline_type == "what_if"
    assert obj.is_active is False
    assert obj.frozen_on is None and obj.planned_finish is None
    assert obj.task_count is None and obj.total_effort_hours is None

    resp = _planning_get(client_a, "bsl_detail", obj.pk)
    assert resp.status_code == 200
    body = _planning_body(resp)
    assert obj.number in body and "Two-week compression" in body

    resp = _planning_get(client_a, "bsl_edit", obj.pk)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["obj"].pk == obj.pk

    resp = _planning_post(client_a, "bsl_edit", obj.pk,
                          data=_planning_baseline_payload(planning_project_a,
                                                          name="Two-week compression, revised"))
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("bsl_list")
    obj.refresh_from_db()
    assert obj.name == "Two-week compression, revised"
    assert obj.baseline_type == "what_if"   # same-type edit passes the type lock

    resp = _planning_post(client_a, "bsl_delete", obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("bsl_list")
    assert _planning_get(client_a, "bsl_detail", obj.pk).status_code == 404


def test_planning_baseline_create_as_baseline_snapshots_and_takes_over(
        client_a, tenant_a, planning_project_a, planning_baseline_active_a):
    """Born frozen: creating a ``baseline``-typed row snapshots the live plan and flips OFF the
    previous active baseline - exactly one active per project, enforced by the verb."""
    _planning_fill_tasks(tenant_a, planning_project_a, 2)
    today = _planning_today()

    resp = _planning_post(client_a, "bsl_create",
                          data=_planning_baseline_payload(planning_project_a,
                                                          name="Freeze the plan",
                                                          baseline_type="baseline"))
    assert resp.status_code == 302
    obj = ScheduleBaseline.objects.get(name="Freeze the plan")
    assert resp["Location"] == _planning_url("bsl_detail", obj.pk)
    assert obj.number.startswith("BSL-")
    assert obj.frozen_on == today
    assert obj.task_count == 2
    assert obj.planned_finish == today + datetime.timedelta(days=4)
    assert obj.total_effort_hours == Decimal("80.00")
    assert obj.is_active is True

    planning_baseline_active_a.refresh_from_db()
    assert planning_baseline_active_a.is_active is False
    actives = ScheduleBaseline.objects.filter(
        tenant=tenant_a, project=planning_project_a, is_active=True)
    assert [row.pk for row in actives] == [obj.pk]


def test_planning_task_detail_lists_children_and_links(
        client_a, tenant_a, planning_project_a):
    parent = _planning_task(tenant_a, planning_project_a, name="Envelope deliverable",
                            node_type="deliverable", planned_start=None, planned_end=None,
                            effort_hours=None)
    child = _planning_task(tenant_a, planning_project_a, parent=parent, name="Cladding package")
    upstream = _planning_task(tenant_a, planning_project_a, name="Upstream package")
    downstream = _planning_task(tenant_a, planning_project_a, name="Downstream package")
    dep_in = _planning_dependency(tenant_a, upstream, parent)
    dep_out = _planning_dependency(tenant_a, parent, downstream)

    resp = _planning_get(client_a, "tsk_detail", parent.pk)
    assert resp.status_code == 200
    assert "projects/planning/task/detail.html" in _planning_templates(resp)
    assert resp.context["obj"].pk == parent.pk
    assert [row.pk for row in resp.context["child_tasks"]] == [child.pk]
    assert [row.pk for row in resp.context["predecessor_links"]] == [dep_in.pk]
    assert [row.pk for row in resp.context["successor_links"]] == [dep_out.pk]
    body = _planning_body(resp)
    assert child.name in body and dep_in.number in body and dep_out.number in body


# ==================================================================================================
# 4. The verbs - achieve, activate, promote, and the frozen refusals
# ==================================================================================================

def test_planning_milestone_achieve_stamps_once_and_refuses_replays(
        client_a, planning_milestone_a):
    obj = planning_milestone_a
    resp = _planning_post(client_a, "mst_achieve", obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("mst_detail", obj.pk)
    assert _planning_said(resp, f"Milestone {obj.number} achieved.")
    obj.refresh_from_db()
    assert obj.status == "achieved"
    assert obj.actual_date == _planning_today()

    # A replay must be refused with the ORIGINAL stamp intact - the first achievement is the
    # evidence, so a second click may not re-stamp it with today's date.
    past = _planning_today() - datetime.timedelta(days=3)
    ProjectMilestone.objects.filter(pk=obj.pk).update(actual_date=past)
    resp = _planning_post(client_a, "mst_achieve", obj.pk)
    assert resp.status_code == 302
    assert _planning_said(resp, "already achieved")
    obj.refresh_from_db()
    assert obj.status == "achieved"
    assert obj.actual_date == past


def test_planning_milestone_achieve_refuses_cancelled(client_a, tenant_a, planning_project_a):
    obj = _planning_milestone(tenant_a, planning_project_a, name="Cancelled gate",
                              status="cancelled")
    resp = _planning_post(client_a, "mst_achieve", obj.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("mst_detail", obj.pk)
    assert _planning_said(resp, "cannot be achieved")
    obj.refresh_from_db()
    assert obj.status == "cancelled"
    assert obj.actual_date is None


def test_planning_baseline_activate_flips_exactly_one(
        client_a, planning_baseline_active_a, planning_baseline_frozen_a,
        planning_baseline_whatif_a):
    frozen = planning_baseline_frozen_a        # baseline-typed, currently inactive
    active = planning_baseline_active_a

    resp = _planning_post(client_a, "bsl_activate", frozen.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("bsl_detail", frozen.pk)
    assert _planning_said(resp, "is now the active baseline")
    frozen.refresh_from_db()
    active.refresh_from_db()
    assert frozen.is_active is True and active.is_active is False

    # Repeating the verb is an info no-op - nothing flips back.
    resp = _planning_post(client_a, "bsl_activate", frozen.pk)
    assert resp.status_code == 302
    assert _planning_said(resp, "already the active one")
    frozen.refresh_from_db()
    active.refresh_from_db()
    assert frozen.is_active is True and active.is_active is False

    # A what-if cannot be activated - promote is the only road in (L35).
    resp = _planning_post(client_a, "bsl_activate", planning_baseline_whatif_a.pk)
    assert resp.status_code == 302
    assert _planning_said(resp, "Only a frozen baseline can be activated")
    planning_baseline_whatif_a.refresh_from_db()
    assert planning_baseline_whatif_a.baseline_type == "what_if"
    assert planning_baseline_whatif_a.is_active is False
    frozen.refresh_from_db()
    assert frozen.is_active is True


def test_planning_baseline_promote_freezes_and_takes_over(
        client_a, tenant_a, planning_project_a, planning_baseline_whatif_a,
        planning_baseline_active_a):
    _planning_fill_tasks(tenant_a, planning_project_a, 2)
    today = _planning_today()
    whatif = planning_baseline_whatif_a

    resp = _planning_post(client_a, "bsl_promote", whatif.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("bsl_detail", whatif.pk)
    assert _planning_said(resp, "promoted to the active baseline")
    whatif.refresh_from_db()
    assert whatif.baseline_type == "baseline"
    assert whatif.frozen_on == today
    assert whatif.task_count == 2
    assert whatif.planned_finish == today + datetime.timedelta(days=4)
    assert whatif.total_effort_hours == Decimal("80.00")
    assert whatif.is_active is True
    planning_baseline_active_a.refresh_from_db()
    assert planning_baseline_active_a.is_active is False

    # Promoting a row that is already a frozen baseline is an info no-op.
    resp = _planning_post(client_a, "bsl_promote", whatif.pk)
    assert resp.status_code == 302
    assert _planning_said(resp, "already a frozen baseline")
    whatif.refresh_from_db()
    assert whatif.baseline_type == "baseline" and whatif.is_active is True


def test_planning_frozen_baseline_refuses_edit_and_delete(
        client_a, planning_baseline_active_a, planning_baseline_whatif_a):
    """A frozen row refuses edit (GET and POST) and delete with a message - and the what-if
    control proves the gate is the row's state, not the route."""
    frozen = planning_baseline_active_a
    before = _planning_snapshot(frozen)

    resp = _planning_get(client_a, "bsl_edit", frozen.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("bsl_detail", frozen.pk)
    assert _planning_said(resp, "frozen baseline cannot be changed")
    _planning_unchanged(frozen, before)

    resp = _planning_post(client_a, "bsl_edit", frozen.pk,
                          data=_planning_baseline_payload(frozen.project,
                                                          name="Rewritten after the freeze"))
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("bsl_detail", frozen.pk)
    assert _planning_said(resp, "frozen baseline cannot be changed")
    _planning_unchanged(frozen, before)

    resp = _planning_post(client_a, "bsl_delete", frozen.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("bsl_detail", frozen.pk)
    assert _planning_said(resp, "frozen baseline cannot be changed")
    assert ScheduleBaseline.objects.filter(pk=frozen.pk).exists()
    _planning_unchanged(frozen, before)

    # The what-if control: edit renders the form, delete really deletes.
    resp = _planning_get(client_a, "bsl_edit", planning_baseline_whatif_a.pk)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    resp = _planning_post(client_a, "bsl_delete", planning_baseline_whatif_a.pk)
    assert resp.status_code == 302
    assert resp["Location"] == _planning_url("bsl_list")
    assert not ScheduleBaseline.objects.filter(pk=planning_baseline_whatif_a.pk).exists()


# ==================================================================================================
# 5. Pagination - a full page plus one
# ==================================================================================================

def test_planning_registers_paginate_to_a_second_page(client_a, tenant_a, planning_project_a):
    """PAGE_SIZE + 1 tasks: page 1 is full, page 2 holds the one leftover, junk and past-the-end
    page numbers fall to page 1 / the last page instead of erroring (L9)."""
    tasks = _planning_fill_tasks(tenant_a, planning_project_a, PLANNING_PAGE_SIZE + 1)

    resp = _planning_get(client_a, "tsk_list")
    assert resp.status_code == 200
    page_obj = resp.context["page_obj"]
    assert page_obj.paginator.per_page == PLANNING_PAGE_SIZE
    assert page_obj.number == 1
    assert len(list(resp.context["object_list"])) == PLANNING_PAGE_SIZE
    assert tasks[-1].pk not in _planning_pks(resp)

    resp = _planning_get(client_a, "tsk_list", page="2")
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 2
    assert _planning_pks(resp) == [tasks[-1].pk]

    resp = _planning_get(client_a, "tsk_list", page="abc")
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 1
    assert len(list(resp.context["object_list"])) == PLANNING_PAGE_SIZE

    resp = _planning_get(client_a, "tsk_list", page="99")
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == resp.context["page_obj"].paginator.num_pages
    assert _planning_pks(resp) == [tasks[-1].pk]
