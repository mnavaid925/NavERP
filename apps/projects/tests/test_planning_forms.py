"""Projects 7.2 Project Planning & Scheduling - FORM tests.

The four planning forms are 7.2's entire write boundary: every byte that reaches a
``ProjectTask``, ``TaskDependency``, ``ProjectMilestone`` or ``ScheduleBaseline`` through the UI
passes through one of them. This lane owns the claims no other lane can see.

**1. What is NOT a field.** Each ``Meta.fields`` list is a security control, not a tidiness
preference. ``MilestoneForm`` omits ``status`` AND ``actual_date`` (fix **I2**): status moves only
through the tenant-admin-gated ``mst_achieve``, and ``actual_date`` is stamped by ``save()`` -
leaving either on the form would let any member achieve a milestone through the ungated edit view.
``BaselineForm`` omits ``is_active`` and the four freeze-time snapshot columns - they are written
by ``freeze_snapshot()`` and the activate/promote verbs only - and LOCKS ``baseline_type`` on edit
(fix **I1**): a row's type moves only through the audited ``bsl_promote`` verb, so an edit POST
that flips it is a ``baseline_type`` error while CREATE accepts both types freely. ``number`` /
``tenant`` / ``created_by`` are on nobody's list.

**2. Tenant scoping of every tenant-stamped FK, on both layers.** ``TenantModelForm`` narrows a
``ModelChoiceField`` whose target model carries a ``tenant`` column, so a crafted cross-tenant
POST answers with Django's ``"Select a valid choice."``; widening the queryset first (the shape a
POST that never went near the widget actually takes) is how the ``_reject_foreign`` backstop
behind it is reached. Per the 7.2 contract, every cross-tenant case asserts that the field HAS an
error - never the message wording.

The one FK that must stay UNGUARDED is ``owner`` on ``TaskForm``: it is a User FK and users can be
tenant-less (the superuser), so a tenant comparison would reject legitimate picks - the 7.1
precedent for ``project_manager`` / ``executive_sponsor``. The absence is proved behaviourally,
the way 7.1 proves ``currency`` is never handed to ``_reject_foreign``.

**3. The task-form guards.** On EDIT only, walking the candidate parent's ancestor chain must
never reach ``self`` - nesting a task beneath its own descendant would make the WBS tree
unrenderable - and the model's cross-project parent guard (C1) and inverted-window guard surface
keyed on ``parent`` / ``planned_end`` through the form.

Required fields: the build contract's "``project`` + ``name`` only" for ``TaskForm`` is loose.
As everywhere in this app, a field carrying a model default WITHOUT ``blank=True`` is mechanically
required on its ModelForm (7.1 pins the same trap as ten required fields on
``ProjectRequestForm``). The as-built required sets are pinned below.

Determinism (L16): ``USE_TZ`` is True and ``TIME_ZONE`` is UTC; every date basis is
``timezone.localdate()`` through ``_planning_today()``, never ``datetime.date.today()``. No
network, no filesystem. Tests use the FACTORIES, never the seeder, and never ``bulk_create``
(numbering lives in ``save()``).

Naming (mandatory): every test is ``test_planning_*`` and every module-level helper
``_planning_*`` / ``_PLANNING_*``, so neither lane of this package can shadow the other. 7.1's
FACTORY functions are imported where they fit (its fixtures never are).

Scope: forms only. Models, views, urls and permissions belong to the other three lanes.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import NON_FIELD_ERRORS

from apps.projects.forms import (
    BaselineForm,
    MilestoneForm,
    TaskDependencyForm,
    TaskForm,
)
from apps.projects.models import (
    ProjectMilestone,
    ProjectTask,
    ScheduleBaseline,
    TaskDependency,
)
from apps.projects.tests.conftest import (
    _planning_task,
    _planning_today,
    _projectinitiation_project,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Module-level helpers - all _planning_* / _PLANNING_* for the same reason the tests are: Python
# binds the LAST module-level definition, so an unprefixed helper here would silently rebind a
# sibling lane's (L47). Record factories come from conftest, which OWNS them.
# ==================================================================================================

#: ``TaskForm.Meta.fields``, verbatim and in order - the exact 13. ``tenant``, ``number`` and
#: ``created_by`` are the system's; a POST that could name them would forge provenance.
_PLANNING_TASK_FIELDS = [
    "project", "parent", "node_type", "name", "description", "owner", "status",
    "planned_start", "planned_end", "effort_hours", "estimation_method", "confidence",
    "sequence",
]

#: ``TaskDependencyForm.Meta.fields``, verbatim and in order - the exact 5.
_PLANNING_DEPENDENCY_FIELDS = ["predecessor", "successor", "link_type", "lag_days", "note"]

#: ``MilestoneForm.Meta.fields``, verbatim and in order - the exact 8. ``status`` and
#: ``actual_date`` are verb/stamp territory (I2) and must never appear.
_PLANNING_MILESTONE_FIELDS = [
    "project", "anchor_task", "name", "description", "target_date", "is_phase_gate",
    "entry_criteria", "exit_criteria",
]

#: ``BaselineForm.Meta.fields``, verbatim and in order - the exact 5. ``is_active`` and the four
#: snapshot columns are freeze-time evidence the verbs write.
_PLANNING_BASELINE_FIELDS = ["project", "name", "baseline_type", "strategy_note", "note"]

#: The AS-BUILT required set of ``TaskForm``. Beyond ``project`` + ``name``, every field carrying
#: a model default without ``blank=True`` (``node_type``, ``status``, ``estimation_method``,
#: ``confidence``, ``sequence``) is mechanically required - the 7.1 trap, pinned the same way.
_PLANNING_TASK_REQUIRED = {
    "project", "name", "node_type", "status", "estimation_method", "confidence", "sequence",
}


def _planning_task_payload(project, **overrides):
    """A valid ``TaskForm`` POST for ``project`` - every required field plus the dated window.

    Everything else on the form is optional, so a negative test can add one bad value to this and
    know the only reason the form failed is the value it changed.
    """
    payload = {
        "project": str(project.pk),
        "parent": "",
        "node_type": "work_package",
        "name": "Draft the lift plan",
        "description": "",
        "owner": "",
        "status": "planned",
        "planned_start": str(_planning_today()),
        "planned_end": str(_planning_today() + datetime.timedelta(days=4)),
        "effort_hours": "40.00",
        "estimation_method": "bottom_up",
        "confidence": "medium",
        "sequence": "0",
    }
    payload.update(overrides)
    return payload


def _planning_dependency_payload(predecessor, successor, **overrides):
    """A valid ``TaskDependencyForm`` POST predecessor -> successor (FS, zero lag)."""
    payload = {
        "predecessor": str(predecessor.pk),
        "successor": str(successor.pk),
        "link_type": "finish_to_start",
        "lag_days": "0",
        "note": "",
    }
    payload.update(overrides)
    return payload


def _planning_milestone_payload(project, **overrides):
    """A valid ``MilestoneForm`` POST for ``project`` - the three required fields plus blanks."""
    payload = {
        "project": str(project.pk),
        "anchor_task": "",
        "name": "Gate: foundations signed off",
        "description": "",
        "target_date": str(_planning_today() + datetime.timedelta(days=30)),
        "is_phase_gate": "",
        "entry_criteria": "",
        "exit_criteria": "",
    }
    payload.update(overrides)
    return payload


def _planning_baseline_payload(project, **overrides):
    """A valid ``BaselineForm`` POST for ``project`` - what_if unless overridden."""
    payload = {
        "project": str(project.pk),
        "name": "Compression scenario A",
        "baseline_type": "what_if",
        "strategy_note": "",
        "note": "",
    }
    payload.update(overrides)
    return payload


def _planning_widen(form, *names):
    """Drop the tenant narrowing off named ``ModelChoiceField``s, in place.

    A narrowed ``<select>`` refuses a foreign pk as "Select a valid choice", which is a real
    control - but it proves the WIDGET was scoped, not that the boundary holds. Widening first is
    how a crafted POST that never went near the widget is simulated, so what answers is the second
    layer: ``_reject_foreign`` in each form's ``clean()``.
    """
    for name in names:
        field = form.fields[name]
        field.queryset = field.queryset.model._default_manager.all()
    return form


# ==================================================================================================
# 1. TaskForm - the field list IS the security boundary, and the valid path saves
# ==================================================================================================

def test_planning_task_form_valid_path_and_field_list(tenant_a, planning_project_a):
    """``Meta.fields`` is the exact 13-list (so ``tenant`` / ``number`` / ``created_by`` are
    offered to nobody); the as-built required set is pinned; a valid POST saves with every cleaned
    value stuck and the system's own stamps minted.

    The build contract's "``project`` + ``name`` only" required claim is loose: as everywhere in
    this app, a field with a model default and no ``blank=True`` is required on the ModelForm
    (7.1 pins the identical trap as ten required fields on ``ProjectRequestForm``), so the
    as-built set of SEVEN is what is pinned.
    """
    form = TaskForm(tenant=tenant_a)
    assert TaskForm.Meta.fields == _PLANNING_TASK_FIELDS
    assert list(form.fields) == _PLANNING_TASK_FIELDS
    assert len(form.fields) == 13
    for absent in ("tenant", "number", "created_by"):
        assert absent not in form.fields, absent

    required = {name for name, field in form.fields.items() if field.required}
    assert required == _PLANNING_TASK_REQUIRED
    empty = TaskForm({}, tenant=tenant_a)
    assert not empty.is_valid()
    assert set(empty.errors) == _PLANNING_TASK_REQUIRED

    form = TaskForm(_planning_task_payload(planning_project_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("TSK-")
    assert obj.project_id == planning_project_a.pk
    assert obj.parent_id is None
    assert obj.owner_id is None
    assert obj.name == "Draft the lift plan"
    assert obj.node_type == "work_package"
    assert obj.status == "planned"
    assert obj.planned_start == _planning_today()
    assert obj.planned_end == _planning_today() + datetime.timedelta(days=4)
    assert obj.effort_hours == Decimal("40.00")
    assert obj.estimation_method == "bottom_up"
    assert obj.confidence == "medium"
    assert obj.sequence == 0


# ==================================================================================================
# 2. TaskForm.owner - the ONE FK deliberately left out of _reject_foreign (7.1 precedent)
# ==================================================================================================

def test_planning_task_form_owner_is_deliberately_not_rejected(
        tenant_a, planning_project_a, planning_tenantless_user):
    """``owner`` is a User FK and users can be tenant-less (the superuser), so ``TaskForm`` must
    never tenant-compare it - the same treatment 7.1 gives ``project_manager`` /
    ``executive_sponsor``.

    Part 1: a tenant-None user offered as owner, the queryset widened first (the shape a crafted
    POST that never went near the widget takes) - the form VALIDATES and the row saves with that
    owner. ``clean()`` re-checks ``["project", "parent"]`` and must leave ``owner`` alone.

    Part 2 (the 7.1 currency-test mirror): on a ``tenant=None`` form ``_reject_foreign`` rejects
    EVERY tenant-stamped row it is handed - so in one and the same POST the tenant-stamped
    ``project`` is refused and the tenant-less ``owner`` accepted, which can only happen if
    ``owner`` was never passed to it. A regression that added the name would make every
    tenant-less user unassignable in every workspace.
    """
    payload = _planning_task_payload(planning_project_a, owner=str(planning_tenantless_user.pk))
    form = TaskForm(payload, tenant=tenant_a)
    _planning_widen(form, "owner")
    assert "owner" not in form.errors
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.owner_id == planning_tenantless_user.pk

    form = TaskForm(payload, tenant=None)
    assert not form.is_valid()
    assert "project" in form.errors
    assert "owner" not in form.errors
    assert form.cleaned_data["owner"] == planning_tenantless_user


# ==================================================================================================
# 3. TaskForm - the cross-tenant FK boundary, on both layers
# ==================================================================================================

def test_planning_task_form_rejects_cross_tenant_project(
        tenant_a, planning_project_a, planning_project_b):
    """A crafted POST carrying tenant B's project pk. Layer 1: the narrowed dropdown refuses it
    outright. Layer 2: with the queryset widened (the shape a POST that never went near the widget
    takes), ``_reject_foreign`` - which lists ``project`` - refuses it too. Either way the error
    keys on ``project`` and nothing saves; never the wording."""
    before = ProjectTask.objects.count()
    payload = _planning_task_payload(planning_project_b)

    form = TaskForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert ProjectTask.objects.count() == before

    form = TaskForm(payload, tenant=tenant_a)
    _planning_widen(form, "project", "parent")
    assert not form.is_valid()
    assert "project" in form.errors
    assert ProjectTask.objects.count() == before


# ==================================================================================================
# 4. TaskForm - the C1 cross-project parent guard, at the form layer
# ==================================================================================================

def test_planning_task_form_rejects_parent_from_another_project(tenant_a, planning_project_a):
    """C1 at the form layer: a SAME-TENANT parent from a sibling project passes the tenant
    narrowing, so the error that answers is the MODEL clean's cross-project guard, surfaced keyed
    on ``parent``. A parent that cannot be narrowed away must not slip through either."""
    sibling = _projectinitiation_project(tenant_a, name="Sibling build host", code="SBH-01")
    cousin = _planning_task(tenant_a, sibling)
    before = ProjectTask.objects.count()

    form = TaskForm(_planning_task_payload(planning_project_a, parent=str(cousin.pk)),
                    tenant=tenant_a)
    assert not form.is_valid()
    assert "parent" in form.errors
    assert ("The parent task must belong to the same project as the task."
            in " ".join(form.errors["parent"]))
    assert ProjectTask.objects.count() == before


def test_planning_task_form_rejects_parent_from_another_tenant(
        tenant_a, planning_project_a, planning_task_b):
    """A tenant B parent pk. Layer 1: queryset scoping fires first. Layer 2: widened,
    ``_reject_foreign`` - which lists ``parent`` alongside ``project`` - refuses it too. Either
    way the error keys on ``parent``; never the wording; nothing saves."""
    before = ProjectTask.objects.count()
    payload = _planning_task_payload(planning_project_a, parent=str(planning_task_b.pk))

    form = TaskForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "parent" in form.errors
    assert ProjectTask.objects.count() == before

    form = TaskForm(payload, tenant=tenant_a)
    _planning_widen(form, "parent")
    assert not form.is_valid()
    assert "parent" in form.errors
    assert ProjectTask.objects.count() == before


# ==================================================================================================
# 5. TaskForm - the descendant cycle guard (edit-only), and the inverted planned window
# ==================================================================================================

def test_planning_task_form_rejects_a_descendant_as_parent(tenant_a, planning_task_a):
    """The cycle guard (edit only): pointing a task at its own CHILD would make the WBS tree
    unrenderable - walking UP from the candidate parent reaches ``self`` in one hop here. A
    same-project NON-descendant parent on the same edit form still saves, so the guard is the
    ancestry and not the edit."""
    child = _planning_task(tenant_a, planning_task_a.project, parent=planning_task_a)
    other_root = _planning_task(tenant_a, planning_task_a.project)

    form = TaskForm(
        _planning_task_payload(planning_task_a.project, parent=str(child.pk)),
        instance=planning_task_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "parent" in form.errors
    assert "A task cannot be nested beneath its own descendant." in form.errors["parent"]

    form = TaskForm(
        _planning_task_payload(planning_task_a.project, parent=str(other_root.pk)),
        instance=planning_task_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().parent_id == other_root.pk


def test_planning_task_form_rejects_planned_end_before_start(tenant_a, planning_project_a):
    """The model's inverted-window guard surfaces at the form layer keyed ``planned_end``; an
    equal-date window is legal and reads as a one-day task."""
    today = _planning_today()
    bad = TaskForm(
        _planning_task_payload(planning_project_a,
                               planned_start=str(today + datetime.timedelta(days=10)),
                               planned_end=str(today + datetime.timedelta(days=5))),
        tenant=tenant_a)
    assert not bad.is_valid()
    assert "planned_end" in bad.errors

    same = TaskForm(
        _planning_task_payload(planning_project_a, planned_start=str(today),
                               planned_end=str(today)),
        tenant=tenant_a)
    assert same.is_valid(), same.errors
    assert same.save().duration_days == 1


# ==================================================================================================
# 6. TaskDependencyForm - the edge writer
# ==================================================================================================

def test_planning_dependency_form_valid_path_and_defaults(tenant_a, planning_project_a):
    """Exact 5-field list; a valid POST saves the edge with the FS / zero-lag defaults stuck and
    ``note`` optional. ``link_type`` / ``lag_days`` carry model defaults WITHOUT ``blank=True``,
    so the form refuses a POST that omits them - the defaults are pinned on the model and proved
    through the save."""
    form = TaskDependencyForm(tenant=tenant_a)
    assert TaskDependencyForm.Meta.fields == _PLANNING_DEPENDENCY_FIELDS
    assert list(form.fields) == _PLANNING_DEPENDENCY_FIELDS
    assert TaskDependency._meta.get_field("link_type").default == "finish_to_start"
    assert TaskDependency._meta.get_field("lag_days").default == 0

    required = {name for name, field in form.fields.items() if field.required}
    assert required == {"predecessor", "successor", "link_type", "lag_days"}
    empty = TaskDependencyForm({}, tenant=tenant_a)
    assert not empty.is_valid()
    assert set(empty.errors) == required

    pred = _planning_task(tenant_a, planning_project_a)
    succ = _planning_task(tenant_a, planning_project_a)
    form = TaskDependencyForm(_planning_dependency_payload(pred, succ), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.number.startswith("DEP-")
    assert obj.tenant_id == tenant_a.pk
    assert obj.predecessor_id == pred.pk
    assert obj.successor_id == succ.pk
    assert obj.link_type == "finish_to_start"
    assert obj.lag_days == 0
    assert obj.note == ""


def test_planning_dependency_form_rejects_cross_tenant_endpoints(
        tenant_a, planning_project_a, planning_task_b):
    """A foreign endpoint on EITHER side, on both layers: the narrowed dropdown refuses it, and
    widened the ``_reject_foreign`` re-check - which lists BOTH endpoints - refuses it too. The
    error keys on the endpoint's own field; never the wording; nothing saves."""
    mine = _planning_task(tenant_a, planning_project_a)
    before = TaskDependency.objects.count()
    foreign_first = _planning_dependency_payload(planning_task_b, mine)
    foreign_second = _planning_dependency_payload(mine, planning_task_b)

    form = TaskDependencyForm(foreign_first, tenant=tenant_a)
    assert not form.is_valid()
    assert "predecessor" in form.errors
    form = TaskDependencyForm(foreign_second, tenant=tenant_a)
    assert not form.is_valid()
    assert "successor" in form.errors
    assert TaskDependency.objects.count() == before

    form = TaskDependencyForm(foreign_first, tenant=tenant_a)
    _planning_widen(form, "predecessor", "successor")
    assert not form.is_valid()
    assert "predecessor" in form.errors
    form = TaskDependencyForm(foreign_second, tenant=tenant_a)
    _planning_widen(form, "predecessor", "successor")
    assert not form.is_valid()
    assert "successor" in form.errors
    assert TaskDependency.objects.count() == before


def test_planning_dependency_form_rejects_self_link(tenant_a, planning_project_a):
    """The model clean's self-link rule surfaces as a NON-FIELD error - there is no single field
    to blame for an edge that starts and ends on the same node."""
    task = _planning_task(tenant_a, planning_project_a)
    form = TaskDependencyForm(_planning_dependency_payload(task, task), tenant=tenant_a)
    assert not form.is_valid()
    assert NON_FIELD_ERRORS in form.errors
    assert "A task cannot depend on itself." in form.non_field_errors()
    assert TaskDependency.objects.count() == 0


# ==================================================================================================
# 7. MilestoneForm - I2: status and actual_date are NOT fields
# ==================================================================================================

def test_planning_milestone_form_excludes_status_and_actual_date(tenant_a, planning_project_a):
    """I2: the exact 8-field list, and ``status`` / ``actual_date`` (like ``number`` /
    ``tenant``) are NOT fields - status moves only through the tenant-admin-gated
    ``mst_achieve``, so leaving it on the form would let any member achieve a milestone through
    the ungated edit view. A POST smuggling both names still saves a ``planned`` row with no
    stamp and a freshly minted number."""
    form = MilestoneForm(tenant=tenant_a)
    assert MilestoneForm.Meta.fields == _PLANNING_MILESTONE_FIELDS
    assert list(form.fields) == _PLANNING_MILESTONE_FIELDS
    assert len(form.fields) == 8
    for absent in ("status", "actual_date", "number", "tenant"):
        assert absent not in MilestoneForm.Meta.fields, absent
        assert absent not in form.fields, absent

    required = {name for name, field in form.fields.items() if field.required}
    assert required == {"project", "name", "target_date"}
    empty = MilestoneForm({}, tenant=tenant_a)
    assert not empty.is_valid()
    assert set(empty.errors) == required

    form = MilestoneForm(
        _planning_milestone_payload(planning_project_a, status="achieved",
                                    actual_date="2020-01-01"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("MST-")
    assert obj.status == "planned"
    assert obj.actual_date is None


def test_planning_milestone_form_rejects_cross_tenant_project_and_anchor(
        tenant_a, planning_project_a, planning_project_b, planning_task_b):
    """A foreign ``project`` (narrowed AND widened - ``_reject_foreign`` lists it) and an
    ``anchor_task`` that cannot legally anchor: one from ANOTHER TENANT (both layers) and one
    from a sibling SAME-TENANT project (the model clean's guard, keyed on the field)."""
    before = ProjectMilestone.objects.count()
    foreign_project = _planning_milestone_payload(planning_project_b)

    form = MilestoneForm(foreign_project, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors

    form = MilestoneForm(foreign_project, tenant=tenant_a)
    _planning_widen(form, "project", "anchor_task")
    assert not form.is_valid()
    assert "project" in form.errors

    form = MilestoneForm(
        _planning_milestone_payload(planning_project_a, anchor_task=str(planning_task_b.pk)),
        tenant=tenant_a)
    _planning_widen(form, "anchor_task")
    assert not form.is_valid()
    assert "anchor_task" in form.errors

    sibling = _projectinitiation_project(tenant_a, name="Anchor sibling host", code="ASH-01")
    cousin = _planning_task(tenant_a, sibling)
    form = MilestoneForm(
        _planning_milestone_payload(planning_project_a, anchor_task=str(cousin.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "anchor_task" in form.errors
    assert ("The anchor task must belong to the same project as the milestone."
            in " ".join(form.errors["anchor_task"]))
    assert ProjectMilestone.objects.count() == before


# ==================================================================================================
# 8. BaselineForm - the exclusions, the edit-only type lock (I1) and the cross-tenant project
# ==================================================================================================

def test_planning_baseline_form_fields_and_exclusions(tenant_a, planning_project_a):
    """Exact 5-field list; ``is_active`` and the four freeze-time snapshot columns (like
    ``number`` / ``tenant``) are absent - they are written by ``freeze_snapshot()`` and the
    activate/promote verbs, never by a form - and BOTH types are valid on create. A saved row
    holds the system's values: inactive, unsnapshotted, minted."""
    form = BaselineForm(tenant=tenant_a)
    assert BaselineForm.Meta.fields == _PLANNING_BASELINE_FIELDS
    assert list(form.fields) == _PLANNING_BASELINE_FIELDS
    assert len(form.fields) == 5
    for absent in ("is_active", "frozen_on", "planned_finish", "task_count",
                   "total_effort_hours", "number", "tenant"):
        assert absent not in form.fields, absent

    required = {name for name, field in form.fields.items() if field.required}
    assert required == {"project", "name", "baseline_type"}
    empty = BaselineForm({}, tenant=tenant_a)
    assert not empty.is_valid()
    assert set(empty.errors) == required

    for baseline_type in ("baseline", "what_if"):
        form = BaselineForm(
            _planning_baseline_payload(planning_project_a, baseline_type=baseline_type),
            tenant=tenant_a)
        assert form.is_valid(), (baseline_type, form.errors)
        obj = form.save()
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("BSL-")
        assert obj.baseline_type == baseline_type
        assert obj.is_active is False
        assert obj.frozen_on is None
        assert obj.planned_finish is None
        assert obj.task_count is None
        assert obj.total_effort_hours is None


def test_planning_baseline_form_type_lock_on_edit_only(
        tenant_a, planning_project_a, planning_baseline_whatif_a, planning_baseline_frozen_a):
    """I1, edit-only: an edit POST that flips ``baseline_type`` is a field error on the row
    itself (either direction - the type is fixed, not directional), the row is untouched, a
    SAME-TYPE edit round-trips, and on CREATE both types are still free."""
    form = BaselineForm(
        _planning_baseline_payload(planning_baseline_whatif_a.project,
                                   baseline_type="baseline", name="Renamed scenario"),
        instance=planning_baseline_whatif_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "baseline_type" in form.errors
    assert "A row's type is fixed" in " ".join(form.errors["baseline_type"])
    planning_baseline_whatif_a.refresh_from_db()
    assert planning_baseline_whatif_a.baseline_type == "what_if"

    form = BaselineForm(
        _planning_baseline_payload(planning_baseline_frozen_a.project,
                                   baseline_type="what_if"),
        instance=planning_baseline_frozen_a, tenant=tenant_a)
    assert not form.is_valid()
    assert "baseline_type" in form.errors

    form = BaselineForm(
        _planning_baseline_payload(planning_baseline_whatif_a.project,
                                   baseline_type="what_if", name="Renamed scenario"),
        instance=planning_baseline_whatif_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.pk == planning_baseline_whatif_a.pk
    assert obj.baseline_type == "what_if"
    assert obj.name == "Renamed scenario"

    for baseline_type in ("baseline", "what_if"):
        assert BaselineForm(
            _planning_baseline_payload(planning_project_a, baseline_type=baseline_type),
            tenant=tenant_a).is_valid(), baseline_type


def test_planning_baseline_form_rejects_cross_tenant_project(
        tenant_a, planning_project_a, planning_project_b):
    """A crafted POST carrying tenant B's project pk, on both layers - the narrowed dropdown and
    then the widened ``_reject_foreign`` re-check. Error on ``project``, nothing saved; never the
    wording."""
    before = ScheduleBaseline.objects.count()
    payload = _planning_baseline_payload(planning_project_b)

    form = BaselineForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert ScheduleBaseline.objects.count() == before

    form = BaselineForm(payload, tenant=tenant_a)
    _planning_widen(form, "project")
    assert not form.is_valid()
    assert "project" in form.errors
    assert ScheduleBaseline.objects.count() == before
