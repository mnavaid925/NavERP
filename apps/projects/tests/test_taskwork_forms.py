"""Projects 7.8 — Task & Work Management form tests.

Four forms: ``TaskExecutionForm`` (the ONLY execution-field write surface — I2's ruling),
``TaskChecklistItemForm`` (the checklist ModelForm), and the two plain ``forms.Form`` verb
bodies ``TaskBlockForm`` / ``TaskUnblockForm``. ``TaskBlock`` itself has no ModelForm by ruling:
the row is minted by ``tsk_block`` and closed by ``tsk_unblock``.

Naming: every test ``test_taskwork_*``, every helper ``_taskwork_*``.
"""
from decimal import Decimal

import pytest

from apps.projects.forms import (
    TaskBlockForm,
    TaskChecklistItemForm,
    TaskExecutionForm,
    TaskUnblockForm,
)


# ==================================================================================================
# TaskExecutionForm — the exact field set (the guard that keeps plan fields unreachable)
# ==================================================================================================

def test_taskwork_execution_form_field_set_is_exactly_the_six(db):
    """I2's ruling: the six execution fields, nothing else. Adding a plan field here would make
    the whole planning surface editable from the execution page."""
    assert list(TaskExecutionForm.Meta.fields) == [
        "assignee", "priority", "moscow", "is_urgent", "is_important", "percent_complete"]


def test_taskwork_execution_form_excludes_the_verb_written_stamps(db):
    """``actual_start`` / ``actual_end`` are stamped by the verbs and are on NO form."""
    fields = set(TaskExecutionForm.Meta.fields)
    assert "actual_start" not in fields
    assert "actual_end" not in fields
    assert "status" not in fields


def test_taskwork_execution_form_excludes_the_plan_fields(db):
    """The plan fields stay on 7.2's ``TaskForm`` — the execution form must not reach them."""
    fields = set(TaskExecutionForm.Meta.fields)
    for plan_field in ("name", "project", "parent", "node_type", "planned_start", "planned_end",
                       "effort_hours", "estimation_method", "confidence", "sequence"):
        assert plan_field not in fields


# ==================================================================================================
# M9 — the two guards that protect attested history
# ==================================================================================================

def test_taskwork_execution_form_freezes_a_done_rows_percent_complete(db, taskwork_task_done_a):
    """``tsk_complete`` wrote 100 as evidence; a form must not be able to quietly lower it."""
    form = TaskExecutionForm(
        data={"assignee": "", "priority": "high", "moscow": "", "percent_complete": "10"},
        instance=taskwork_task_done_a, tenant=taskwork_task_done_a.tenant)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["percent_complete"] == Decimal("100.00")


def test_taskwork_execution_form_still_allows_the_other_fields_on_a_done_row(
        db, taskwork_task_done_a):
    """The freeze is surgical: only the completion stamp is held, the other five stay writable."""
    form = TaskExecutionForm(
        data={"assignee": "", "priority": "critical", "moscow": "must_have",
              "percent_complete": "10"},
        instance=taskwork_task_done_a, tenant=taskwork_task_done_a.tenant)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["priority"] == "critical"
    assert form.cleaned_data["moscow"] == "must_have"


def test_taskwork_execution_form_refuses_a_cancelled_row(db, taskwork_task_cancelled_a):
    """The work is not happening — execution fields cannot be written on cancelled rows."""
    form = TaskExecutionForm(
        data={"assignee": "", "priority": "high", "moscow": "", "percent_complete": "50"},
        instance=taskwork_task_cancelled_a, tenant=taskwork_task_cancelled_a.tenant)
    assert not form.is_valid()
    assert "cancelled" in str(form.errors).lower()


def test_taskwork_execution_form_accepts_a_live_row_unchanged(db, taskwork_task_in_progress_a):
    """The control: an in-progress row takes a percent write normally."""
    form = TaskExecutionForm(
        data={"assignee": "", "priority": "high", "moscow": "should_have",
              "percent_complete": "80"},
        instance=taskwork_task_in_progress_a, tenant=taskwork_task_in_progress_a.tenant)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["percent_complete"] == Decimal("80")


# ==================================================================================================
# TaskChecklistItemForm — the checklist ModelForm
# ==================================================================================================

def test_taskwork_checklist_form_field_set(db):
    assert list(TaskChecklistItemForm.Meta.fields) == ["task", "label", "sequence"]


def test_taskwork_checklist_form_excludes_the_tick_stamps(db):
    """``is_done`` / ``done_by`` / ``done_at`` are written by the tcl_check toggle only."""
    fields = set(TaskChecklistItemForm.Meta.fields)
    assert "is_done" not in fields
    assert "done_by" not in fields
    assert "done_at" not in fields


def test_taskwork_checklist_form_requires_a_label(db, planning_project_a, taskwork_task_planned_a):
    form = TaskChecklistItemForm(
        data={"task": taskwork_task_planned_a.pk, "label": "", "sequence": "1"},
        tenant=planning_project_a.tenant)
    assert not form.is_valid()
    assert "label" in form.errors


def test_taskwork_checklist_form_rejects_a_foreign_tenant_task(
        db, planning_project_b, taskwork_task_planned_a):
    """The tenant-scoped queryset narrows ``task`` first, so a foreign pk is a FIELD error
    ("Select a valid choice"), never a silent cross-tenant write."""
    form = TaskChecklistItemForm(
        data={"task": taskwork_task_planned_a.pk, "label": "Cross-tenant attempt",
              "sequence": "1"},
        tenant=planning_project_b.tenant)
    assert not form.is_valid()
    assert "task" in form.errors


# ==================================================================================================
# The two plain verb bodies
# ==================================================================================================

def test_taskwork_block_form_requires_both_texts(db):
    """A block with no stated reason or no exit criteria is not evidence."""
    assert not TaskBlockForm(data={"reason": "", "unblock_criteria": ""}).is_valid()
    assert TaskBlockForm(data={"reason": "Why", "unblock_criteria": "What clears it"}).is_valid()


def test_taskwork_block_form_has_exactly_the_two_fields(db):
    assert list(TaskBlockForm().fields) == ["reason", "unblock_criteria"]


def test_taskwork_unblock_form_requires_a_resolution_note(db):
    assert not TaskUnblockForm(data={"resolution_note": ""}).is_valid()
    assert TaskUnblockForm(data={"resolution_note": "Credentials arrived."}).is_valid()


def test_taskwork_unblock_form_has_exactly_the_one_field(db):
    assert list(TaskUnblockForm().fields) == ["resolution_note"]


def test_taskwork_block_forms_cannot_touch_the_evidence_stamps(db):
    """Neither verb body exposes a stamp — ``tsk_block`` / ``tsk_unblock`` own those."""
    for form_cls in (TaskBlockForm, TaskUnblockForm):
        fields = set(form_cls().fields)
        for stamp in ("blocked_by", "blocked_at", "unblocked_by", "unblocked_at", "task"):
            assert stamp not in fields
