"""Projects 7.8 — Task & Work Management security tests.

IDOR 404s, the both-actor method guards (the module's C2 lesson), role gates, CSRF, anonymity,
mass assignment, crafted FKs and XSS. Every assertion here is about what an attacker gets, not
about what the happy path does.

Naming: every test ``test_taskwork_*``, every helper ``_taskwork_*``.
"""
import pytest
from django.urls import reverse

from apps.projects.models import ProjectTask, TaskBlock, TaskChecklistItem


#: The POST-only verbs and the fixture whose pk they take.
_POST_ONLY_VERBS = [
    ("tcl_delete", "taskwork_checklist_mixed_item_a"),
    ("tcl_check", "taskwork_checklist_mixed_item_a"),
    ("tsk_start", "taskwork_task_planned_a"),
    ("tsk_complete", "taskwork_task_planned_a"),
    ("tsk_block", "taskwork_task_planned_a"),
    ("tsk_unblock", "taskwork_task_planned_a"),
]

#: The routes that read a pk and must 404 for another tenant's row.
_FOREIGN_PK_ROUTES = [
    ("tbk_detail", "taskwork_block_active_b"),
    ("tcl_detail", "taskwork_item_b"),
    ("tcl_edit", "taskwork_item_b"),
    ("tsk_execute", "planning_task_b"),
]


# ==================================================================================================
# The both-actor method guard — the module's C2 lesson
# ==================================================================================================

@pytest.mark.parametrize("name,fixture", _POST_ONLY_VERBS)
def test_taskwork_a_member_get_on_a_post_only_verb_is_405_not_403(
        db, taskwork_member_client, request, name, fixture):
    """The decorator order is ``login_required(require_POST(tenant_admin_required(view)))``, so
    the METHOD check runs before any role check. 405 is house policy for every POST-only verb;
    a 403 here would mean the role check fired first (the C2 regression)."""
    url = reverse("projects:%s" % name, args=[request.getfixturevalue(fixture).pk])
    assert taskwork_member_client.get(url).status_code == 405


@pytest.mark.parametrize("name,fixture", _POST_ONLY_VERBS)
def test_taskwork_an_admin_get_on_a_post_only_verb_is_also_405(
        db, taskwork_admin_client, request, name, fixture):
    """The other half: the method guard must not depend on the actor."""
    url = reverse("projects:%s" % name, args=[request.getfixturevalue(fixture).pk])
    assert taskwork_admin_client.get(url).status_code == 405


def test_taskwork_bulk_update_get_is_405_for_both_actors(
        db, taskwork_member_client, taskwork_admin_client):
    url = reverse("projects:tsk_bulk_update")
    assert taskwork_member_client.get(url).status_code == 405
    assert taskwork_admin_client.get(url).status_code == 405


# ==================================================================================================
# IDOR — another tenant's pk is a 404, never a 200 and never a write
# ==================================================================================================

@pytest.mark.parametrize("name,fixture", _FOREIGN_PK_ROUTES)
def test_taskwork_a_foreign_pk_on_a_detail_route_is_404(
        db, taskwork_admin_client, request, name, fixture):
    url = reverse("projects:%s" % name, args=[request.getfixturevalue(fixture).pk])
    assert taskwork_admin_client.get(url).status_code == 404


def test_taskwork_a_foreign_pk_cannot_be_deleted(db, taskwork_admin_client, taskwork_item_b):
    taskwork_admin_client.post(reverse("projects:tcl_delete", args=[taskwork_item_b.pk]))
    assert TaskChecklistItem.objects.filter(pk=taskwork_item_b.pk).exists()


def test_taskwork_a_foreign_pk_cannot_be_toggled(db, taskwork_admin_client, taskwork_item_b):
    before = taskwork_item_b.is_done
    taskwork_admin_client.post(reverse("projects:tcl_check", args=[taskwork_item_b.pk]))
    taskwork_item_b.refresh_from_db()
    assert taskwork_item_b.is_done == before


def test_taskwork_a_foreign_task_cannot_be_started(db, taskwork_admin_client, planning_task_b):
    before = planning_task_b.status
    taskwork_admin_client.post(reverse("projects:tsk_start", args=[planning_task_b.pk]))
    planning_task_b.refresh_from_db()
    assert planning_task_b.status == before


def test_taskwork_a_foreign_task_cannot_be_blocked(db, taskwork_admin_client, planning_task_b):
    taskwork_admin_client.post(reverse("projects:tsk_block", args=[planning_task_b.pk]),
                               {"reason": "Cross-tenant attempt.", "unblock_criteria": "Nope."})
    assert not planning_task_b.blocks.exists()


# ==================================================================================================
# The bulk verb — crafted ids
# ==================================================================================================

def test_taskwork_bulk_update_cannot_write_another_tenants_task(
        db, taskwork_admin_client, planning_project_a, planning_task_b):
    mine = _taskwork_task(planning_project_a)
    before = planning_task_b.priority
    taskwork_admin_client.post(reverse("projects:tsk_bulk_update"),
                               {"task_ids": [mine.pk, planning_task_b.pk], "priority": "critical"})
    planning_task_b.refresh_from_db()
    assert planning_task_b.priority == before


def test_taskwork_bulk_update_refuses_a_foreign_tenant_assignee(
        db, taskwork_admin_client, planning_project_a, admin_b):
    """C2: the assignee lookup is tenant-scoped (+ the tenant-less superuser), so a foreign
    user pk cannot be written into this workspace."""
    task = _taskwork_task(planning_project_a)
    taskwork_admin_client.post(reverse("projects:tsk_bulk_update"),
                               {"task_ids": [task.pk], "assignee": admin_b.pk})
    task.refresh_from_db()
    assert task.assignee_id != admin_b.pk


# ==================================================================================================
# Anonymity
# ==================================================================================================

@pytest.mark.parametrize("name", ["task_board", "gantt_timeline", "task_priority", "tbk_list",
                                  "tcl_list"])
def test_taskwork_an_anonymous_get_redirects_to_login(db, taskwork_anon_client, name):
    resp = taskwork_anon_client.get(reverse("projects:%s" % name))
    assert resp.status_code == 302
    assert "/login" in resp["Location"] or "accounts" in resp["Location"]


@pytest.mark.parametrize("name,args", [
    ("tsk_start", [1]), ("tsk_block", [1]), ("tcl_check", [1]), ("tsk_bulk_update", [])])
def test_taskwork_an_anonymous_post_is_refused(db, taskwork_anon_client, name, args):
    resp = taskwork_anon_client.post(reverse("projects:%s" % name, args=args))
    assert resp.status_code in (302, 403, 405)


# ==================================================================================================
# CSRF
# ==================================================================================================

def test_taskwork_a_csrf_less_bulk_post_is_refused(db, taskwork_csrf_client, admin_user,
                                                   planning_project_a):
    taskwork_csrf_client.force_login(admin_user)
    resp = taskwork_csrf_client.post(reverse("projects:tsk_bulk_update"),
                                     {"task_ids": [1], "priority": "high"})
    assert resp.status_code == 403


def test_taskwork_a_csrf_less_block_post_is_refused(db, taskwork_csrf_client, admin_user,
                                                    taskwork_task_planned_a):
    taskwork_csrf_client.force_login(admin_user)
    resp = taskwork_csrf_client.post(reverse("projects:tsk_block", args=[taskwork_task_planned_a.pk]),
                                     {"reason": "x", "unblock_criteria": "y"})
    assert resp.status_code == 403


# ==================================================================================================
# Mass assignment — the verb-written stamps are unreachable from any form
# ==================================================================================================

def test_taskwork_execute_cannot_write_the_verb_stamps(db, taskwork_admin_client,
                                                       taskwork_task_in_progress_a):
    """``actual_start``/``actual_end`` are verb-written; a crafted POST must not move them."""
    before_start = taskwork_task_in_progress_a.actual_start
    before_end = taskwork_task_in_progress_a.actual_end
    taskwork_admin_client.post(
        reverse("projects:tsk_execute", args=[taskwork_task_in_progress_a.pk]),
        {"assignee": "", "priority": "high", "moscow": "", "percent_complete": "50",
         "actual_start": "2020-01-01", "actual_end": "2020-01-02", "status": "done"})
    taskwork_task_in_progress_a.refresh_from_db()
    assert taskwork_task_in_progress_a.actual_start == before_start
    assert taskwork_task_in_progress_a.actual_end == before_end
    assert taskwork_task_in_progress_a.status == "in_progress"


def test_taskwork_checklist_create_cannot_set_the_tick_stamps(db, taskwork_admin_client,
                                                              planning_project_a,
                                                              taskwork_task_planned_a, admin_user):
    taskwork_admin_client.post(
        reverse("projects:tcl_create"),
        {"task": taskwork_task_planned_a.pk, "label": "Crafted", "sequence": "1",
         "is_done": "on", "done_by": admin_user.pk})
    item = TaskChecklistItem.objects.filter(label="Crafted").first()
    assert item is not None
    assert item.is_done is False
    assert item.done_by_id is None


def test_taskwork_bulk_update_ignores_an_unknown_field(db, taskwork_admin_client,
                                                       planning_project_a):
    task = _taskwork_task(planning_project_a)
    taskwork_admin_client.post(reverse("projects:tsk_bulk_update"),
                               {"task_ids": [task.pk], "priority": "high", "percent_complete": "99"})
    task.refresh_from_db()
    assert task.priority == "high"
    assert task.percent_complete != 99


# ==================================================================================================
# XSS — a crafted label is escaped, never executed
# ==================================================================================================

def test_taskwork_a_script_label_is_escaped_in_the_register(db, taskwork_admin_client,
                                                            planning_project_a):
    task = _taskwork_task(planning_project_a)
    _taskwork_item(planning_project_a.tenant, task,
                   label="<script>alert('xss')</script>")
    body = taskwork_admin_client.get(reverse("projects:tcl_list")).content.decode()
    assert "<script>alert('xss')</script>" not in body
    assert "&lt;script&gt;" in body


def test_taskwork_a_script_reason_is_escaped_on_the_detail_page(db, taskwork_admin_client,
                                                                planning_project_a, admin_user):
    task = _taskwork_task(planning_project_a)
    _taskwork_a_block(planning_project_a.tenant, task, blocked_by=admin_user,
                      reason="<script>alert('xss')</script>")
    body = taskwork_admin_client.get(reverse("projects:tsk_detail", args=[task.pk])).content.decode()
    assert "<script>alert('xss')</script>" not in body


# ==================================================================================================
# Helpers
# ==================================================================================================

def _taskwork_task(project, **overrides):
    from apps.projects.tests.conftest import _planning_task
    return _planning_task(project.tenant, project, **overrides)


def _taskwork_item(tenant, task, **overrides):
    from apps.projects.tests.conftest import _taskwork_checklist_item
    return _taskwork_checklist_item(tenant, task, **overrides)


def _taskwork_a_block(tenant, task, **overrides):
    from apps.projects.tests.conftest import _taskwork_block
    return _taskwork_block(tenant, task, **overrides)
