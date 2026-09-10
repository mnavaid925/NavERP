"""Projects 7.2 Project Planning & Scheduling — MODEL tests.

The model lane owns the claims the four planning tables would be worthless without — the numbering,
the cross-project guards, the milestone stamp and the baseline freeze:

* **``TenantNumbered``** mints ``TSK-/DEP-/MST-/BSL-00001`` once, per tenant, per MODEL. Two
  workspaces both read ``TSK-00001`` and neither collides; a second ``save()`` never re-numbers.
* **The cross-project guards are the data model.** A task's ``parent`` must live in the same
  project (C1); a dependency's endpoints must live in ONE project (and a task cannot depend on
  itself); a milestone's ``anchor_task`` must live in the same project. ``save()`` never calls
  ``clean()``, so every refusal below goes through ``full_clean()`` — the shape the forms see.
* **``ProjectMilestone.actual_date`` is a system stamp**: ``save()`` writes it the first time the
  status becomes ``achieved``, keeps the ORIGINAL stamp on every re-save while still achieved,
  CLEARS it when the status leaves ``achieved`` (reopen) and re-stamps on re-achievement.
* **``ScheduleBaseline.freeze_snapshot()``** copies the project's live plan into the editable=False
  snapshot columns in ONE aggregate — undated tasks count toward ``task_count`` but contribute
  nothing to ``planned_finish`` (``Max`` skips NULLs), and the effort sum is routed through
  ``q2``'s clamp.
* **The derived values are DERIVED, never columns.** ``duration_days`` and the ``1.2.3`` WBS codes
  are computed on read; no such column may ever exist.

Determinism (L16): ``USE_TZ`` is True, so every date basis here is ``timezone.localdate()`` via
``_planning_today()`` — the same basis ``ProjectMilestone.is_late`` and the achievement stamp use.
``datetime.date.today()`` never appears, or the is_late/stamp assertions flake for the hours either
side of local midnight.

Naming (mandatory): every test is ``test_planning_*`` and every module-level helper
``_planning_*`` / ``_PLANNING_*``, so neither lane of this package can shadow the other.

Scope: models only. Forms, views, urls and permissions belong to the other three lanes.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import NON_FIELD_ERRORS, FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction

from apps.projects.models import (
    MAX_Q2,
    ProjectMilestone,
    ProjectTask,
    ScheduleBaseline,
    TaskDependency,
    q2,
)
from apps.projects.tests.conftest import (
    _planning_baseline,
    _planning_dependency,
    _planning_milestone,
    _planning_task,
    _planning_today,
    _projectinitiation_project,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Local helpers - _planning_* for the same reason the tests are (Python binds the LAST module-level
# definition, so an unprefixed helper here would silently rebind a sibling lane's). Everything that
# builds a planning row comes from the shared conftest factories; these only host and read.
# ==================================================================================================

_PLANNING_MODELS = (
    (ProjectTask, "TSK"),
    (TaskDependency, "DEP"),
    (ProjectMilestone, "MST"),
    (ScheduleBaseline, "BSL"),
)


def _planning_host(tenant, tag):
    """An ACTIVE, charter-approved host project for 7.2 rows — via the 7.1 FACTORY (never the 7.1
    fixtures: the planning lane must not depend on 7.1's fixture rows)."""
    return _projectinitiation_project(
        tenant, name=f"Planning model host {tag}", code=f"PMH-{tag}", status="active",
        charter_status="approved")


def _planning_index_names(model):
    return {index.name for index in model._meta.indexes}


def _planning_non_editable(model):
    """The columns no ModelForm can offer - the model-layer half of the L20/L22 contract."""
    return {f.name for f in model._meta.fields if not f.editable}


def _planning_values(choices):
    """The value strings of a CHOICES list, in declaration order."""
    return [value for value, _label in choices]


# ==================================================================================================
# TenantNumbered - the per-tenant, per-model sequences
# ==================================================================================================

def test_planning_numbering_is_per_tenant_per_model(tenant_a, tenant_b):
    """One row of each model per workspace: tenant A reads TSK-/DEP-/MST-/BSL-00001 and tenant B
    independently reads the SAME four numbers — a number is unique per (model, tenant), never
    globally. And a second ``save()`` never re-numbers what the first one minted."""
    project_a = _planning_host(tenant_a, "NA")
    project_b = _planning_host(tenant_b, "NB")

    a_task = _planning_task(tenant_a, project_a)
    a_dep = _planning_dependency(tenant_a, _planning_task(tenant_a, project_a),
                                 _planning_task(tenant_a, project_a))
    a_milestone = _planning_milestone(tenant_a, project_a)
    a_baseline = _planning_baseline(tenant_a, project_a)

    b_task = _planning_task(tenant_b, project_b)
    b_dep = _planning_dependency(tenant_b, _planning_task(tenant_b, project_b),
                                 _planning_task(tenant_b, project_b))
    b_milestone = _planning_milestone(tenant_b, project_b)
    b_baseline = _planning_baseline(tenant_b, project_b)

    assert [a_task.number, a_dep.number, a_milestone.number, a_baseline.number] == [
        "TSK-00001", "DEP-00001", "MST-00001", "BSL-00001"]
    assert [b_task.number, b_dep.number, b_milestone.number, b_baseline.number] == [
        "TSK-00001", "DEP-00001", "MST-00001", "BSL-00001"]
    assert a_task.tenant_id != b_task.tenant_id

    minted = a_task.number
    a_task.name = "Renamed after the fact"
    a_task.save()
    a_task.refresh_from_db()
    assert a_task.number == minted == "TSK-00001"


# ==================================================================================================
# Vocabulary - the CHOICES constants and the field defaults the forms and registers render
# ==================================================================================================

def test_planning_choice_machine_values_are_pinned():
    """Exact (value, label) tuples of all seven CHOICES constants, plus the field defaults the
    registers and the tree assume. Machine values are API — a rename here is a migration."""
    assert list(ProjectTask.NODE_TYPE_CHOICES) == [
        ("deliverable", "Deliverable"), ("work_package", "Work Package")]
    assert list(ProjectTask.STATUS_CHOICES) == [
        ("planned", "Planned"), ("in_progress", "In Progress"), ("done", "Done"),
        ("cancelled", "Cancelled")]
    assert list(ProjectTask.ESTIMATION_CHOICES) == [
        ("bottom_up", "Bottom-Up"), ("top_down", "Top-Down"), ("analogous", "Analogous"),
        ("parametric", "Parametric")]
    assert list(ProjectTask.CONFIDENCE_CHOICES) == [
        ("high", "High"), ("medium", "Medium"), ("low", "Low")]
    assert list(TaskDependency.LINK_TYPE_CHOICES) == [
        ("finish_to_start", "Finish-to-Start"), ("start_to_start", "Start-to-Start"),
        ("finish_to_finish", "Finish-to-Finish"), ("start_to_finish", "Start-to-Finish")]
    assert list(ProjectMilestone.STATUS_CHOICES) == [
        ("planned", "Planned"), ("in_review", "In Review"), ("achieved", "Achieved"),
        ("missed", "Missed"), ("cancelled", "Cancelled")]
    assert list(ScheduleBaseline.BASELINE_TYPE_CHOICES) == [
        ("baseline", "Frozen Baseline"), ("what_if", "What-If Scenario")]

    # Defaults — read off the fields so a default that only exists in the factory is caught.
    assert ProjectTask._meta.get_field("node_type").default == "work_package"
    assert ProjectTask._meta.get_field("status").default == "planned"
    assert ProjectTask._meta.get_field("estimation_method").default == "bottom_up"
    assert ProjectTask._meta.get_field("confidence").default == "medium"
    assert ProjectTask._meta.get_field("sequence").default == 0
    assert TaskDependency._meta.get_field("link_type").default == "finish_to_start"
    assert TaskDependency._meta.get_field("lag_days").default == 0
    assert ScheduleBaseline._meta.get_field("baseline_type").default == "baseline"
    assert ScheduleBaseline._meta.get_field("is_active").default is False


# ==================================================================================================
# ProjectTask - the derived values, and the two clean() guards save() does not run
# ==================================================================================================

def test_planning_task_duration_days_is_inclusive_or_none(tenant_a):
    """Both dates → ``(end - start).days + 1`` (the calendar reads INCLUSIVE — same-day work is
    still one day); either missing → ``None``. ``duration_days`` — and the ``1.2.3`` WBS code —
    are computed on read and must never become columns."""
    project = _planning_host(tenant_a, "DUR")
    today = _planning_today()

    both = _planning_task(tenant_a, project, planned_start=today,
                          planned_end=today + datetime.timedelta(days=4))
    assert both.duration_days == 5
    same_day = _planning_task(tenant_a, project, planned_start=today, planned_end=today)
    assert same_day.duration_days == 1

    assert _planning_task(tenant_a, project, planned_start=today,
                          planned_end=None).duration_days is None
    assert _planning_task(tenant_a, project, planned_start=None,
                          planned_end=today).duration_days is None
    assert _planning_task(tenant_a, project, planned_start=None,
                          planned_end=None).duration_days is None

    with pytest.raises(FieldDoesNotExist):
        ProjectTask._meta.get_field("duration_days")
    assert isinstance(ProjectTask.duration_days, property)
    with pytest.raises(FieldDoesNotExist):
        ProjectTask._meta.get_field("wbs_code")


def test_planning_task_clean_rejects_planned_end_before_start(tenant_a):
    """An inverted planning window is refused, keyed on ``planned_end`` — the field a user fixes.
    Equal dates are the zero-float same-day case and must pass."""
    project = _planning_host(tenant_a, "WIN")
    today = _planning_today()

    inverted = _planning_task(tenant_a, project, planned_start=today,
                              planned_end=today - datetime.timedelta(days=1))
    with pytest.raises(ValidationError) as excinfo:
        inverted.full_clean()
    assert "planned_end" in excinfo.value.error_dict

    equal = _planning_task(tenant_a, project, planned_start=today, planned_end=today)
    assert equal.full_clean() is None


def test_planning_task_clean_rejects_parent_from_another_project(tenant_a):
    """C1 — the WBS is per-project: a parent from a sibling project in the SAME tenant is still
    refused, keyed on ``parent``. The same-project control proves the guard is the project, not
    the existence of a parent."""
    project = _planning_host(tenant_a, "C1A")
    sibling = _planning_host(tenant_a, "C1B")

    child = _planning_task(tenant_a, project)
    child.parent = _planning_task(tenant_a, sibling)
    with pytest.raises(ValidationError) as excinfo:
        child.full_clean()
    assert "parent" in excinfo.value.error_dict

    child.parent = _planning_task(tenant_a, project)
    assert child.full_clean() is None


# ==================================================================================================
# TaskDependency - the same-project rule, the self-link rule, and the pair constraint
# ==================================================================================================

def test_planning_dependency_clean_rejects_self_link(tenant_a):
    """``predecessor == successor`` → a NON-field error: no single field is the culprit, so the
    form surface it lands on is ``__all__``."""
    project = _planning_host(tenant_a, "SELF")
    task = _planning_task(tenant_a, project)

    shell = TaskDependency(tenant=tenant_a, predecessor=task, successor=task)
    with pytest.raises(ValidationError) as excinfo:
        shell.full_clean()
    assert NON_FIELD_ERRORS in excinfo.value.error_dict
    assert "A task cannot depend on itself." in str(excinfo.value.messages)


def test_planning_dependency_clean_rejects_mismatched_endpoints(tenant_a, tenant_b):
    """Both endpoints must live in ONE project — a cross-project pair inside one tenant and a
    cross-tenant pair raise the SAME message (the rule is about the project, and a cross-tenant
    pair is trivially a cross-project one)."""
    project_a = _planning_host(tenant_a, "DEPA")
    other_project_a = _planning_host(tenant_a, "DEPA2")
    project_b = _planning_host(tenant_b, "DEPB")

    left = _planning_task(tenant_a, project_a)
    cross_project = TaskDependency(tenant=tenant_a, predecessor=left,
                                   successor=_planning_task(tenant_a, other_project_a))
    with pytest.raises(ValidationError) as excinfo:
        cross_project.full_clean()
    assert "Both endpoints of a dependency must belong to the same project." \
        in str(excinfo.value.messages)

    cross_tenant = TaskDependency(tenant=tenant_a, predecessor=left,
                                  successor=_planning_task(tenant_b, project_b))
    with pytest.raises(ValidationError) as excinfo:
        cross_tenant.full_clean()
    assert "Both endpoints of a dependency must belong to the same project." \
        in str(excinfo.value.messages)

    same_project = TaskDependency(tenant=tenant_a, predecessor=left,
                                  successor=_planning_task(tenant_a, project_a))
    assert same_project.full_clean() is None


def test_planning_dependency_pair_is_unique_per_tenant(tenant_a):
    """``(tenant, predecessor, successor)`` — one edge per direction: the duplicate is refused by
    the database, while a different pair AND the reversed pair (which is semantically a different
    sequencing statement) both save."""
    project = _planning_host(tenant_a, "UNQ")
    left = _planning_task(tenant_a, project)
    right = _planning_task(tenant_a, project)

    _planning_dependency(tenant_a, left, right)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _planning_dependency(tenant_a, left, right)

    third = _planning_task(tenant_a, project)
    assert _planning_dependency(tenant_a, left, third).pk
    assert _planning_dependency(tenant_a, right, left).pk


# ==================================================================================================
# ProjectMilestone - the actual_date stamp, is_late, and the anchor guard
# ==================================================================================================

def test_planning_milestone_actual_date_stamps_exactly_once(tenant_a):
    """``save()`` stamps ``actual_date`` the first time the status becomes ``achieved``, keeps the
    ORIGINAL stamp on every re-save while still achieved, CLEARS it when the status leaves
    ``achieved`` (reopen) and re-stamps fresh on re-achievement. You cannot backdate an achievement
    by hand any more than you can un-hold a kickoff."""
    project = _planning_host(tenant_a, "STAMP")
    milestone = _planning_milestone(tenant_a, project, status="planned")
    assert milestone.actual_date is None

    milestone.status = "achieved"
    milestone.save()
    milestone.refresh_from_db()
    assert milestone.actual_date == _planning_today()

    # A re-save while still achieved must NOT overwrite: force the stamp into the past (the shape
    # a date that really was days ago takes), reload the row so the in-memory copy agrees with the
    # database, and prove the second save leaves the stamp alone.
    original = _planning_today() - datetime.timedelta(days=3)
    ProjectMilestone.objects.filter(pk=milestone.pk).update(actual_date=original)
    milestone.refresh_from_db()
    milestone.status = "achieved"
    milestone.save()
    milestone.refresh_from_db()
    assert milestone.actual_date == original

    milestone.status = "planned"
    milestone.save()
    milestone.refresh_from_db()
    assert milestone.actual_date is None

    milestone.status = "achieved"
    milestone.save()
    milestone.refresh_from_db()
    assert milestone.actual_date == _planning_today()


def test_planning_milestone_is_late_follows_status_and_date(tenant_a):
    """Late = the target has passed AND the milestone is still live: ``planned``/``in_review`` are
    late, ``achieved``/``missed``/``cancelled`` never are — even with the same past date. The basis
    is ``timezone.localdate()`` (L16), the same one ``save()`` stamps with."""
    project = _planning_host(tenant_a, "LATE")
    past = _planning_today() - datetime.timedelta(days=1)
    future = _planning_today() + datetime.timedelta(days=7)

    assert _planning_milestone(tenant_a, project, target_date=past,
                               status="planned").is_late is True
    assert _planning_milestone(tenant_a, project, target_date=past,
                               status="in_review").is_late is True
    for status in ("achieved", "missed", "cancelled"):
        row = _planning_milestone(tenant_a, project, target_date=past, status=status)
        assert row.is_late is False, status
    assert _planning_milestone(tenant_a, project, target_date=future,
                               status="planned").is_late is False

    with pytest.raises(FieldDoesNotExist):
        ProjectMilestone._meta.get_field("is_late")
    assert isinstance(ProjectMilestone.is_late, property)


def test_planning_milestone_clean_rejects_anchor_task_from_another_project(tenant_a):
    """A milestone may anchor to a WBS node — but only one of its OWN project, keyed on
    ``anchor_task``. The same-project control passes."""
    project = _planning_host(tenant_a, "ANC")
    sibling = _planning_host(tenant_a, "ANC2")

    milestone = _planning_milestone(tenant_a, project)
    milestone.anchor_task = _planning_task(tenant_a, sibling)
    with pytest.raises(ValidationError) as excinfo:
        milestone.full_clean()
    assert "anchor_task" in excinfo.value.error_dict

    milestone.anchor_task = _planning_task(tenant_a, project)
    assert milestone.full_clean() is None


# ==================================================================================================
# ScheduleBaseline - is_frozen, the freeze snapshot, and the shared q2 clamp beneath it
# ==================================================================================================

def test_planning_baseline_is_frozen_and_freeze_snapshot_aggregates_the_plan(tenant_a):
    """``is_frozen`` follows the TYPE (a what_if row is never frozen, whatever its columns say).
    ``freeze_snapshot()`` copies the live plan into the snapshot columns in ONE aggregate: undated
    tasks count toward ``task_count`` but contribute nothing to ``planned_finish``; an all-undated
    plan snapshots a NULL finish and a 0.00 effort; a ZERO-task project is the same shape with a
    count of 0. ``frozen_on`` records the day of the freeze."""
    project = _planning_host(tenant_a, "BSL")
    what_if = _planning_baseline(tenant_a, project)
    assert what_if.is_frozen is False
    frozen = _planning_baseline(tenant_a, project, baseline_type="baseline")
    assert frozen.is_frozen is True

    today = _planning_today()
    _planning_task(tenant_a, project, planned_start=today,
                   planned_end=today + datetime.timedelta(days=10),
                   effort_hours=Decimal("24.00"))
    _planning_task(tenant_a, project, planned_start=today,
                   planned_end=today + datetime.timedelta(days=4),
                   effort_hours=Decimal("16.50"))
    _planning_task(tenant_a, project, planned_start=None, planned_end=None, effort_hours=None)

    frozen.freeze_snapshot()
    assert frozen.task_count == 3
    assert frozen.planned_finish == today + datetime.timedelta(days=10)
    assert frozen.total_effort_hours == Decimal("40.50")
    assert frozen.frozen_on == _planning_today()

    # All-undated plan: tasks count, but Max over NULLs is NULL and the effort sum routes through
    # q2(None) → 0.00.
    undated_project = _planning_host(tenant_a, "BSL2")
    _planning_task(tenant_a, undated_project, planned_start=None, planned_end=None,
                   effort_hours=None)
    undated = _planning_baseline(tenant_a, undated_project, baseline_type="baseline")
    undated.freeze_snapshot()
    assert undated.task_count == 1
    assert undated.planned_finish is None
    assert undated.total_effort_hours == Decimal("0.00")

    # Zero-task edge: the aggregate runs on an empty plan and lands the zero shape, not an error.
    empty_project = _planning_host(tenant_a, "BSL3")
    empty = _planning_baseline(tenant_a, empty_project, baseline_type="baseline")
    empty.freeze_snapshot()
    assert empty.task_count == 0
    assert empty.planned_finish is None
    assert empty.total_effort_hours == Decimal("0.00")


def test_planning_q2_clamps_to_the_column_ceiling():
    """``q2`` quantizes to 2dp, reads a missing value as 0.00 and CLAMPS to ±MAX_Q2 — the clamp
    ``freeze_snapshot``'s effort sum relies on, pinned at the unit level rather than by building
    ten thousand tasks."""
    assert q2(None) == Decimal("0.00")
    assert q2(Decimal("1")) == Decimal("1.00")
    assert q2(Decimal("112.4999")) == Decimal("112.50")
    assert q2(MAX_Q2) == MAX_Q2
    assert q2(Decimal("99999999999999")) == MAX_Q2
    assert q2(Decimal("-99999999999999")) == -MAX_Q2


# ==================================================================================================
# Meta - the index names, the orderings and the unique_together the schema was built on
# ==================================================================================================

def test_planning_index_names_are_the_as_built_set():
    """Migration 0003's index names are load-bearing: they appear in EXPLAIN plans, in DBA
    conversations and in any future migration that alters them. Re-adding or renaming one is a
    schema decision, so pin the exact set per model — dep carries the successor-side index ONLY
    (the ``(tenant, predecessor, successor)`` unique already covers the predecessor prefix)."""
    assert _planning_index_names(ProjectTask) == {
        "tsk_tnt_project_idx", "tsk_tnt_status_idx", "tsk_tnt_prj_parent_idx",
        "tsk_tnt_ntype_idx"}
    assert _planning_index_names(TaskDependency) == {"dep_tnt_succ_idx"}
    assert _planning_index_names(ProjectMilestone) == {
        "mst_tnt_project_idx", "mst_tnt_status_idx"}
    assert _planning_index_names(ScheduleBaseline) == {"bsl_tnt_project_idx"}


def test_planning_ordering_and_unique_together_are_pinned(tenant_a):
    """Meta.ordering is what every register shows by default. Tasks read WBS-natural
    (project, then sibling sequence, then id); dependencies and baselines read newest-first;
    milestones are the deliberate exception — DATE order, because a milestone register is a
    timeline, proven behaviorally below."""
    assert ProjectTask._meta.ordering == ["project_id", "sequence", "id"]
    assert TaskDependency._meta.ordering == ["-created_at", "-id"]
    assert ProjectMilestone._meta.ordering == ["target_date", "id"]
    assert ScheduleBaseline._meta.ordering == ["-created_at", "-id"]

    assert ProjectTask._meta.unique_together == (("tenant", "number"),)
    assert TaskDependency._meta.unique_together == (
        ("tenant", "number"), ("tenant", "predecessor", "successor"))
    assert ProjectMilestone._meta.unique_together == (("tenant", "number"),)
    assert ScheduleBaseline._meta.unique_together == (("tenant", "number"),)

    project = _planning_host(tenant_a, "ORD")
    today = _planning_today()
    late = _planning_milestone(tenant_a, project, name="Late milestone",
                               target_date=today + datetime.timedelta(days=20))
    early = _planning_milestone(tenant_a, project, name="Early milestone",
                                target_date=today + datetime.timedelta(days=5))
    assert list(ProjectMilestone.objects.filter(project=project)) == [early, late]


# ==================================================================================================
# The editable=False stamp set - the model-layer half of the "no form path" contract
# ==================================================================================================

def test_planning_non_editable_stamps_carry_no_form_path():
    """The stamps a verb or ``save()`` owns — the numbers, the achievement stamp, the freeze-time
    snapshot columns — are ``editable=False`` at the MODEL layer, so no ModelForm can offer them
    however careless its ``Meta.fields``. Everything a user IS meant to edit stays editable."""
    assert _planning_non_editable(ProjectTask) == {
        "number", "created_by", "created_at", "updated_at"}
    assert _planning_non_editable(TaskDependency) == {
        "number", "created_at", "updated_at"}
    assert _planning_non_editable(ProjectMilestone) == {
        "number", "actual_date", "created_at", "updated_at"}
    assert _planning_non_editable(ScheduleBaseline) == {
        "number", "frozen_on", "planned_finish", "task_count", "total_effort_hours",
        "created_at", "updated_at"}
