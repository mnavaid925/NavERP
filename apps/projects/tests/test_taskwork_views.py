"""Projects 7.8 — Task & Work Management view tests.

All 17 routes, the four computed pages, every verb's happy path AND its refusal, the bulk bar,
and pagination. The computed pages derive everything on read — nothing is snapshotted — so the
assertions read the RENDERED page and the view context.

Naming: every test ``test_taskwork_*``, every helper ``_taskwork_*``.
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.projects.models import ProjectTask, TaskBlock, TaskChecklistItem


#: Every 7.8 route and the fixture whose pk it takes (None = no pk).
_TASKWORK_ROUTES = [
    ("task_board", None), ("gantt_timeline", None), ("task_priority", None),
    ("tbk_list", None), ("tbk_detail", "taskwork_block_active_a"),
    ("tcl_list", None), ("tcl_create", None), ("tcl_detail", "taskwork_checklist_mixed_item_a"),
    ("tcl_edit", "taskwork_checklist_mixed_item_a"), ("tcl_delete", "taskwork_checklist_mixed_item_a"),
    ("tcl_check", "taskwork_checklist_mixed_item_a"),
    ("tsk_execute", "taskwork_task_planned_a"), ("tsk_start", "taskwork_task_planned_a"),
    ("tsk_complete", "taskwork_task_planned_a"), ("tsk_block", "taskwork_task_planned_a"),
    ("tsk_unblock", "taskwork_task_planned_a"), ("tsk_bulk_update", None),
]

# ==================================================================================================
# Every route resolves and renders for an admin
# ==================================================================================================

@pytest.mark.parametrize("name,fixture", _TASKWORK_ROUTES)
def test_taskwork_every_route_renders_for_an_admin(
        db, taskwork_admin_client, request, name, fixture):
    kwargs = {}
    if fixture is not None:
        kwargs["pk"] = request.getfixturevalue(fixture).pk
    resp = taskwork_admin_client.get(reverse("projects:%s" % name, kwargs=kwargs))
    assert resp.status_code in (200, 405), name


# ==================================================================================================
# The four computed pages
# ==================================================================================================

def test_taskwork_board_renders_columns_and_the_unclassified_bucket(
        db, taskwork_admin_client, planning_project_a, taskwork_task_planned_a):
    body = taskwork_admin_client.get(reverse("projects:task_board")).content.decode()
    assert "Unclassified" in body


def test_taskwork_board_groups_a_task_under_its_status_column(
        db, taskwork_admin_client, taskwork_task_planned_a):
    resp = taskwork_admin_client.get(reverse("projects:task_board"))
    assert resp.status_code == 200
    assert taskwork_task_planned_a in [t for col in resp.context["columns"] for t in col["tasks"]]


def test_taskwork_priority_page_buckets_live_work_only(
        db, taskwork_admin_client, taskwork_task_done_a, taskwork_task_planned_a):
    """I6: done/cancelled drop out of the MoSCoW groups and the Eisenhower quadrants."""
    resp = taskwork_admin_client.get(reverse("projects:task_priority"))
    assert resp.status_code == 200
    shown = {t.pk for group in resp.context["moscow_groups"] for t in group["tasks"]}
    shown |= {t.pk for quad in resp.context["quadrants"] for t in quad["tasks"]}
    assert taskwork_task_planned_a.pk in shown
    assert taskwork_task_done_a.pk not in shown


def test_taskwork_gantt_renders_bars(db, taskwork_admin_client, planning_project_a,
                                     taskwork_task_planned_a):
    resp = taskwork_admin_client.get(
        reverse("projects:gantt_timeline") + "?project=%s" % planning_project_a.pk)
    assert resp.status_code == 200
    assert resp.context["bars"]


def test_taskwork_gantt_tooltip_never_renders_none(db, taskwork_admin_client,
                                                   planning_project_a, taskwork_task_planned_a):
    """I8: the tooltip reads the bar's resolved window, so an undated deliverable no longer
    renders the string ``None``."""
    body = taskwork_admin_client.get(
        reverse("projects:gantt_timeline") + "?project=%s" % planning_project_a.pk).content.decode()
    assert 'title="None' not in body
    assert "None% complete" not in body


def test_taskwork_gantt_today_line_renders_when_today_is_in_the_window(
        db, taskwork_admin_client, planning_project_a, taskwork_task_planned_a):
    """M6: the marker is drawn only when today falls inside the resolved window."""
    body = taskwork_admin_client.get(
        reverse("projects:gantt_timeline") + "?project=%s" % planning_project_a.pk).content.decode()
    assert 'class="tw-today"' in body


def test_taskwork_gantt_today_line_absent_for_a_past_window(
        db, taskwork_admin_client, planning_project_a, taskwork_task_planned_a):
    body = taskwork_admin_client.get(
        reverse("projects:gantt_timeline")
        + "?project=%s&start=2020-01-01&end=2020-02-01" % planning_project_a.pk).content.decode()
    assert 'class="tw-today"' not in body


def test_taskwork_gantt_with_no_project_is_the_empty_state_not_a_500(db, taskwork_admin_client):
    """The regression net for the M6 fix: ``window_start`` only exists once a project resolved."""
    resp = taskwork_admin_client.get(reverse("projects:gantt_timeline"))
    assert resp.status_code == 200


def test_taskwork_gantt_with_a_junk_project_is_the_empty_state(db, taskwork_admin_client):
    resp = taskwork_admin_client.get(reverse("projects:gantt_timeline") + "?project=999999")
    assert resp.status_code == 200


# ==================================================================================================
# tsk_detail — the view-computed context the panels consume (I7)
# ==================================================================================================

def test_taskwork_detail_passes_the_view_computed_checklist_progress(
        db, taskwork_admin_client, taskwork_checklist_mixed_a):
    resp = taskwork_admin_client.get(
        reverse("projects:tsk_detail", args=[taskwork_checklist_mixed_a.pk]))
    assert resp.status_code == 200
    assert resp.context["checklist_progress"] == 75


def test_taskwork_detail_passes_none_for_an_empty_checklist(
        db, taskwork_admin_client, taskwork_checklist_empty_a):
    resp = taskwork_admin_client.get(
        reverse("projects:tsk_detail", args=[taskwork_checklist_empty_a.pk]))
    assert resp.context["checklist_progress"] is None


def test_taskwork_detail_panel_reads_the_context_not_the_property(
        db, taskwork_admin_client, taskwork_checklist_mixed_a):
    """The rendered panel shows the view's figure — the template must not call
    ``obj.checklist_progress`` (whose two COUNTs bypass the prefetch)."""
    body = taskwork_admin_client.get(
        reverse("projects:tsk_detail", args=[taskwork_checklist_mixed_a.pk])).content.decode()
    assert "75% of the checklist is done." in body


def test_taskwork_detail_attaches_active_blocks_for_the_panel(
        db, taskwork_admin_client, taskwork_task_blocked_a):
    resp = taskwork_admin_client.get(
        reverse("projects:tsk_detail", args=[taskwork_task_blocked_a.pk]))
    assert resp.context["obj"].active_blocks


def test_taskwork_detail_renders_the_blocks_panel_forms(
        db, taskwork_admin_client, taskwork_task_blocked_a):
    body = taskwork_admin_client.get(
        reverse("projects:tsk_detail", args=[taskwork_task_blocked_a.pk])).content.decode()
    assert "Blocking verdict" in body


# ==================================================================================================
# The lifecycle verbs — happy path and refusal
# ==================================================================================================

def test_taskwork_start_moves_planned_to_in_progress_and_stamps(
        db, taskwork_admin_client, taskwork_task_planned_a):
    taskwork_admin_client.post(reverse("projects:tsk_start", args=[taskwork_task_planned_a.pk]))
    taskwork_task_planned_a.refresh_from_db()
    assert taskwork_task_planned_a.status == "in_progress"
    assert taskwork_task_planned_a.actual_start is not None


def test_taskwork_start_refuses_a_non_planned_task(db, taskwork_admin_client,
                                                   taskwork_task_done_a):
    taskwork_admin_client.post(reverse("projects:tsk_start", args=[taskwork_task_done_a.pk]))
    taskwork_task_done_a.refresh_from_db()
    assert taskwork_task_done_a.status == "done"


def test_taskwork_complete_moves_in_progress_to_done_and_attests_100(
        db, taskwork_admin_client, taskwork_task_in_progress_a):
    taskwork_admin_client.post(
        reverse("projects:tsk_complete", args=[taskwork_task_in_progress_a.pk]))
    taskwork_task_in_progress_a.refresh_from_db()
    assert taskwork_task_in_progress_a.status == "done"
    assert taskwork_task_in_progress_a.percent_complete == Decimal("100.00")
    assert taskwork_task_in_progress_a.actual_end is not None


def test_taskwork_complete_refuses_a_blocked_task(db, taskwork_admin_client,
                                                  taskwork_task_blocked_a):
    taskwork_admin_client.post(
        reverse("projects:tsk_complete", args=[taskwork_task_blocked_a.pk]))
    taskwork_task_blocked_a.refresh_from_db()
    assert taskwork_task_blocked_a.status == "in_progress"


def test_taskwork_block_mints_an_evidence_row(db, taskwork_admin_client,
                                              taskwork_task_in_progress_a):
    taskwork_admin_client.post(
        reverse("projects:tsk_block", args=[taskwork_task_in_progress_a.pk]),
        {"reason": "Waiting on the vendor.", "unblock_criteria": "Vendor replies."})
    assert taskwork_task_in_progress_a.blocks.count() == 1
    assert taskwork_task_in_progress_a.blocks.first().is_active is True


def test_taskwork_block_refuses_a_second_open_block(db, taskwork_admin_client,
                                                    taskwork_task_blocked_a):
    before = taskwork_task_blocked_a.blocks.count()
    taskwork_admin_client.post(
        reverse("projects:tsk_block", args=[taskwork_task_blocked_a.pk]),
        {"reason": "Another one.", "unblock_criteria": "Something."})
    assert taskwork_task_blocked_a.blocks.count() == before


def test_taskwork_block_refuses_terminal_work(db, taskwork_admin_client,
                                              taskwork_task_cancelled_a):
    """M8: a cancelled task has nothing left to hold."""
    taskwork_admin_client.post(
        reverse("projects:tsk_block", args=[taskwork_task_cancelled_a.pk]),
        {"reason": "Attempt.", "unblock_criteria": "Attempt."})
    assert not taskwork_task_cancelled_a.blocks.exists()


def test_taskwork_unblock_writes_the_trail_once(db, taskwork_admin_client,
                                                taskwork_task_blocked_a):
    block = taskwork_task_blocked_a.blocks.first()
    taskwork_admin_client.post(
        reverse("projects:tsk_unblock", args=[taskwork_task_blocked_a.pk]),
        {"resolution_note": "Credentials arrived."})
    block.refresh_from_db()
    assert block.unblocked_at is not None
    assert block.resolution_note == "Credentials arrived."


def test_taskwork_unblock_refuses_when_no_block_stands(db, taskwork_admin_client,
                                                       taskwork_task_planned_a):
    taskwork_admin_client.post(
        reverse("projects:tsk_unblock", args=[taskwork_task_planned_a.pk]),
        {"resolution_note": "Nothing to clear."})
    assert not taskwork_task_planned_a.blocks.exists()


def test_taskwork_execute_saves_the_execution_fields(db, taskwork_admin_client,
                                                     taskwork_task_in_progress_a):
    taskwork_admin_client.post(
        reverse("projects:tsk_execute", args=[taskwork_task_in_progress_a.pk]),
        {"assignee": "", "priority": "critical", "moscow": "must_have",
         "percent_complete": "80"})
    taskwork_task_in_progress_a.refresh_from_db()
    assert taskwork_task_in_progress_a.priority == "critical"
    assert taskwork_task_in_progress_a.percent_complete == Decimal("80")


def test_taskwork_execute_cannot_lower_a_done_rows_percent(db, taskwork_admin_client,
                                                           taskwork_task_done_a):
    """M9 end-to-end through the view."""
    taskwork_admin_client.post(
        reverse("projects:tsk_execute", args=[taskwork_task_done_a.pk]),
        {"assignee": "", "priority": "high", "moscow": "", "percent_complete": "10"})
    taskwork_task_done_a.refresh_from_db()
    assert taskwork_task_done_a.percent_complete == Decimal("100.00")


# ==================================================================================================
# The checklist toggle
# ==================================================================================================

def test_taskwork_checklist_check_ticks_an_item(db, taskwork_admin_client, planning_project_a):
    task = _taskwork_task(planning_project_a)
    item = _taskwork_item(planning_project_a.tenant, task)
    taskwork_admin_client.post(reverse("projects:tcl_check", args=[item.pk]))
    item.refresh_from_db()
    assert item.is_done is True
    assert item.done_at is not None


def test_taskwork_checklist_check_untick_clears_the_stamps(db, taskwork_admin_client,
                                                           planning_project_a):
    task = _taskwork_task(planning_project_a)
    item = _taskwork_item(planning_project_a.tenant, task, is_done=True,
                          done_at=datetime.datetime.now(datetime.timezone.utc))
    taskwork_admin_client.post(reverse("projects:tcl_check", args=[item.pk]))
    item.refresh_from_db()
    assert item.is_done is False
    assert item.done_at is None


# ==================================================================================================
# The bulk update (I9 / M10)
# ==================================================================================================

def test_taskwork_bulk_update_applies_to_the_selected_rows(db, taskwork_admin_client,
                                                           planning_project_a):
    a = _taskwork_task(planning_project_a)
    b = _taskwork_task(planning_project_a)
    taskwork_admin_client.post(reverse("projects:tsk_bulk_update"),
                               {"task_ids": [a.pk, b.pk], "priority": "high"})
    a.refresh_from_db(); b.refresh_from_db()
    assert a.priority == "high" and b.priority == "high"


def test_taskwork_bulk_update_skips_a_forged_id(db, taskwork_admin_client, planning_project_a):
    a = _taskwork_task(planning_project_a)
    taskwork_admin_client.post(reverse("projects:tsk_bulk_update"),
                               {"task_ids": [a.pk, 999999], "priority": "high"})
    a.refresh_from_db()
    assert a.priority == "high"


def test_taskwork_bulk_update_caps_the_batch_and_says_so(db, taskwork_admin_client):
    """I9: the batch is capped at 500 and the user is told the remainder was not considered."""
    resp = taskwork_admin_client.post(
        reverse("projects:tsk_bulk_update"),
        {"task_ids": list(range(1, 601)), "priority": "low"}, follow=True)
    body = resp.content.decode()
    assert "Only the first 500" in body


def test_taskwork_bulk_update_refuses_a_blocked_rows_terminal_transition(
        db, taskwork_admin_client, taskwork_task_blocked_a):
    """M10: an open block must not outlive the work it was holding."""
    before = taskwork_task_blocked_a.status
    resp = taskwork_admin_client.post(
        reverse("projects:tsk_bulk_update"),
        {"task_ids": [taskwork_task_blocked_a.pk], "status": "cancelled"}, follow=True)
    taskwork_task_blocked_a.refresh_from_db()
    assert taskwork_task_blocked_a.status == before
    assert "still open" in resp.content.decode()


def test_taskwork_bulk_update_refuses_an_unknown_status(db, taskwork_admin_client,
                                                        planning_project_a):
    a = _taskwork_task(planning_project_a)
    taskwork_admin_client.post(reverse("projects:tsk_bulk_update"),
                               {"task_ids": [a.pk], "status": "not_a_status"})
    a.refresh_from_db()
    assert a.status == "planned"


# ==================================================================================================
# Pagination — the checklist register runs past one page
# ==================================================================================================

def test_taskwork_checklist_register_paginates(db, taskwork_admin_client, planning_project_a):
    task = _taskwork_task(planning_project_a)
    _taskwork_items(planning_project_a.tenant, task, 20)
    resp = taskwork_admin_client.get(reverse("projects:tcl_list"))
    assert resp.status_code == 200
    assert resp.context["page_obj"].paginator.num_pages > 1


def test_taskwork_checklist_register_page_two_renders(db, taskwork_admin_client,
                                                      planning_project_a):
    task = _taskwork_task(planning_project_a)
    _taskwork_items(planning_project_a.tenant, task, 20)
    resp = taskwork_admin_client.get(reverse("projects:tcl_list") + "?page=2")
    assert resp.status_code == 200


# ==================================================================================================
# The register lenses
# ==================================================================================================

def test_taskwork_checklist_register_filters_by_task(db, taskwork_admin_client,
                                                     planning_project_a):
    a = _taskwork_task(planning_project_a)
    b = _taskwork_task(planning_project_a)
    _taskwork_item(planning_project_a.tenant, a, label="On A")
    _taskwork_item(planning_project_a.tenant, b, label="On B")
    resp = taskwork_admin_client.get(reverse("projects:tcl_list") + "?task=%s" % a.pk)
    body = resp.content.decode()
    assert "On A" in body and "On B" not in body


def test_taskwork_block_register_renders(db, taskwork_admin_client, taskwork_block_active_a):
    resp = taskwork_admin_client.get(reverse("projects:tbk_list"))
    assert resp.status_code == 200
    assert taskwork_block_active_a in resp.context["page_obj"]


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
