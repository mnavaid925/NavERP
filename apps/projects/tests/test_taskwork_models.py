"""Projects 7.8 — Task & Work Management model tests.

The 7.8 layer adds NO new task table: it extends ``ProjectTask`` in place (the six execution
fields + the two verb-written stamps) and adds two registers, ``TaskChecklistItem`` [TCL-] and
``TaskBlock`` [TBK-]. These tests pin the model surface those two registers and the extension
present to the views.

Naming: every test ``test_taskwork_*``, every helper ``_taskwork_*``.
"""
import datetime
from decimal import Decimal

import pytest

from apps.projects.models import ProjectTask, TaskBlock, TaskChecklistItem


# ==================================================================================================
# Numbering and __str__
# ==================================================================================================

def test_taskwork_checklist_item_mints_a_tcl_number(db, planning_project_a, taskwork_task_planned_a):
    item = _taskwork_item(planning_project_a.tenant, taskwork_task_planned_a)
    assert item.number.startswith("TCL-")


def test_taskwork_block_mints_a_tbk_number(db, planning_project_a, taskwork_task_planned_a):
    block = _taskwork_a_block(planning_project_a.tenant, taskwork_task_planned_a)
    assert block.number.startswith("TBK-")


def test_taskwork_numbers_are_per_tenant_not_global(db, tenant_a, tenant_b,
                                                    planning_project_a, planning_project_b):
    """Each tenant's first TCL is 00001 — the number sequence is tenant-scoped."""
    a = _taskwork_item(tenant_a, _taskwork_task(planning_project_a))
    b = _taskwork_item(tenant_b, _taskwork_task(planning_project_b))
    assert a.number == b.number


# ==================================================================================================
# TaskBlock.is_active — the derived open/closed state
# ==================================================================================================

def test_taskwork_block_is_active_when_unblocked_at_is_null(db, taskwork_block_active_a):
    assert taskwork_block_active_a.is_active is True


def test_taskwork_block_is_not_active_once_the_trail_is_written(db, taskwork_block_closed_a):
    assert taskwork_block_closed_a.is_active is False


def test_taskwork_block_closed_carries_its_full_evidence(db, taskwork_block_closed_a):
    """A closed block keeps who/when/why — the row is evidence, not a flag."""
    assert taskwork_block_closed_a.unblocked_by_id is not None
    assert taskwork_block_closed_a.unblocked_at is not None
    assert taskwork_block_closed_a.resolution_note


# ==================================================================================================
# The derived blocking state on ProjectTask (Ruling 3 — never a stored column)
# ==================================================================================================

def test_taskwork_manual_block_makes_the_task_blocked(db, taskwork_task_blocked_a):
    assert taskwork_task_blocked_a.is_manually_blocked is True
    assert taskwork_task_blocked_a.is_blocked is True


def test_taskwork_closed_block_leaves_the_task_unblocked(db, planning_project_a):
    task = _taskwork_task(planning_project_a, status="in_progress")
    _taskwork_a_block(planning_project_a.tenant, task,
                      unblocked_at=datetime.datetime.now(datetime.timezone.utc))
    assert task.is_manually_blocked is False


def test_taskwork_unfinished_fs_predecessor_blocks_the_successor(db, taskwork_task_dep_blocked_a):
    assert taskwork_task_dep_blocked_a.is_dependency_blocked is True
    assert taskwork_task_dep_blocked_a.is_blocked is True


def test_taskwork_no_links_and_no_block_is_not_blocked(db, taskwork_task_planned_a):
    assert taskwork_task_planned_a.is_dependency_blocked is False
    assert taskwork_task_planned_a.is_manually_blocked is False
    assert taskwork_task_planned_a.is_blocked is False


def test_taskwork_done_predecessor_does_not_block(db, planning_project_a):
    """An FS link stops blocking once the predecessor is done — the rule is about LIVE work."""
    tenant = planning_project_a.tenant
    upstream = _taskwork_task(planning_project_a, status="done", sequence=1)
    downstream = _taskwork_task(planning_project_a, status="planned", sequence=2)
    _taskwork_link(tenant, upstream, downstream)
    assert downstream.is_dependency_blocked is False


def test_taskwork_cancelled_predecessor_does_not_block(db, planning_project_a):
    tenant = planning_project_a.tenant
    upstream = _taskwork_task(planning_project_a, status="cancelled", sequence=1)
    downstream = _taskwork_task(planning_project_a, status="planned", sequence=2)
    _taskwork_link(tenant, upstream, downstream)
    assert downstream.is_dependency_blocked is False


# ==================================================================================================
# checklist_progress — the model's own figure (the view computes its own off the prefetch)
# ==================================================================================================

def test_taskwork_checklist_progress_is_none_with_no_items(db, taskwork_checklist_empty_a):
    assert taskwork_checklist_empty_a.checklist_progress is None


def test_taskwork_checklist_progress_is_75_when_three_of_four_are_done(db, taskwork_checklist_mixed_a):
    assert taskwork_checklist_mixed_a.checklist_progress == 75


def test_taskwork_checklist_progress_is_zero_when_none_are_done(db, planning_project_a):
    task = _taskwork_task(planning_project_a)
    _taskwork_items(planning_project_a.tenant, task, 3, done=0)
    assert task.checklist_progress == 0


def test_taskwork_checklist_progress_is_100_when_all_are_done(db, planning_project_a):
    task = _taskwork_task(planning_project_a)
    _taskwork_items(planning_project_a.tenant, task, 2, done=2)
    assert task.checklist_progress == 100


# ==================================================================================================
# The in-place execution extension's vocabulary
# ==================================================================================================

def test_taskwork_priority_choices_are_the_four_values(db):
    assert [v for v, _ in ProjectTask.PRIORITY_CHOICES] == ["low", "medium", "high", "critical"]


def test_taskwork_moscow_choices_are_the_four_values(db):
    assert [v for v, _ in ProjectTask.MOSCOW_CHOICES] == [
        "must_have", "should_have", "could_have", "wont_have"]


def test_taskwork_moscow_is_nullable_for_the_unclassified_bucket(db, planning_project_a):
    """The board's "Unclassified" bucket and the priority page's unclassified group both read
    ``moscow IS NULL`` — so the field MUST be nullable (M5 seeds exactly this state)."""
    task = _taskwork_task(planning_project_a, moscow=None)
    task.refresh_from_db()
    assert task.moscow is None


def test_taskwork_status_choices_are_the_four_values(db):
    assert [v for v, _ in ProjectTask.STATUS_CHOICES] == [
        "planned", "in_progress", "done", "cancelled"]


@pytest.mark.parametrize("status", ["done", "cancelled"])
def test_taskwork_terminal_statuses_are_done_and_cancelled(db, planning_project_a, status):
    """The view's ``_TERMINAL_STATUSES`` gate (M8) must agree with the model's vocabulary."""
    from apps.projects.views.TaskWorkManagement.ProjectTasks import _TERMINAL_STATUSES
    assert status in _TERMINAL_STATUSES


# ==================================================================================================
# Eisenhower quadrants
# ==================================================================================================

@pytest.mark.parametrize("urgent,important,expected", [
    (True, True, "do_first"),
    (False, True, "schedule"),
    (True, False, "delegate"),
    (False, False, "eliminate"),
])
def test_taskwork_eisenhower_quadrant_is_derived_from_the_two_flags(
        db, planning_project_a, urgent, important, expected):
    task = _taskwork_task(planning_project_a, is_urgent=urgent, is_important=important)
    assert task.eisenhower_quadrant == expected


# ==================================================================================================
# Indexes — the named ones the migration created
# ==================================================================================================

def test_taskwork_checklist_indexes_are_named():
    names = {i.name for i in TaskChecklistItem._meta.indexes}
    assert {"tcl_tnt_task_idx", "tcl_tnt_done_idx"} <= names


def test_taskwork_block_indexes_are_named():
    names = {i.name for i in TaskBlock._meta.indexes}
    assert {"tbk_tnt_task_idx", "tbk_tnt_unblocked_idx"} <= names


def test_taskwork_task_extension_indexes_are_named():
    names = {i.name for i in ProjectTask._meta.indexes}
    assert {"tsk_tnt_assignee_idx", "tsk_tnt_priority_idx"} <= names


# ==================================================================================================
# Helpers
# ==================================================================================================

def _taskwork_task(project, **overrides):
    from apps.projects.tests.conftest import _planning_task
    return _planning_task(project.tenant, project, **overrides)


def _taskwork_item(tenant, task, **overrides):
    from apps.projects.tests.conftest import _taskwork_checklist_item
    return _taskwork_checklist_item(tenant, task, **overrides)


def _taskwork_items(tenant, task, count, done=0):
    from apps.projects.tests.conftest import _taskwork_fill_checklist
    return _taskwork_fill_checklist(tenant, task, count, done=done)


def _taskwork_a_block(tenant, task, **overrides):
    from apps.projects.tests.conftest import _taskwork_block
    return _taskwork_block(tenant, task, **overrides)


def _taskwork_link(tenant, predecessor, successor):
    from apps.projects.tests.conftest import _planning_dependency
    return _planning_dependency(tenant, predecessor, successor)
