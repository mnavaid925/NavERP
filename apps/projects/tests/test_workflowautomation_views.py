"""Projects 7.17 Workflow & Automation — VIEW tests.

Covers all 40 routes across the 5 sub-module sections:
  1. Operational Boards (AutomationBoards.py):
     - projects:automation_overview
     - projects:approval_inbox
     - projects:recurrence_calendar
     - projects:webhook_diagnostics
  2. Workflow Rules (WorkflowRules.py):
     - projects:pwf_list, projects:pwf_create, projects:pwf_detail, projects:pwf_edit
     - projects:pwf_delete, projects:pwf_toggle_active, projects:pwf_test_run, projects:pwf_execute_now
  3. Approval Gates (ApprovalGates.py):
     - projects:par_list, projects:par_create, projects:par_detail, projects:par_edit
     - projects:par_delete, projects:par_approve, projects:par_reject, projects:par_escalate
     - projects:par_delegate, projects:par_cancel
  4. Recurring Tasks (RecurringTasks.py):
     - projects:rts_list, projects:rts_create, projects:rts_detail, projects:rts_edit
     - projects:rts_delete, projects:rts_toggle_active, projects:rts_generate_task, projects:rts_skip_next
  5. Webhooks (Webhooks.py):
     - projects:pwh_list, projects:pwh_create, projects:pwh_detail, projects:pwh_edit
     - projects:pwh_delete, projects:pwh_toggle_active, projects:pwh_test_ping, projects:pwh_rotate_secret
     - projects:pwh_delivery_list, projects:pwh_delivery_detail

Test coverage includes:
  - GET 200 OK + expected context keys for all list, board, detail, create, edit views.
  - POST create/edit/delete/action redirect (302) and state modification verification.
  - In par_approve / par_reject / par_delegate / par_escalate, verify approver check and requester self-approval rejection.
  - In par_delete, verify terminal gates cannot be deleted.
  - In pwh_create and pwh_rotate_secret, verify one-time secret revelation in session/detail context (revealed_secret).
  - In rts_generate_task, verify a ProjectTask is created with correct fields.
  - Negative input hardening (junk GET params return 200, page 2, page 999, search filtering, status filtering).
  - Multi-tenant isolation for every route (Tenant A accessing Tenant B pk -> 404, A's list never contains B's rows).
  - Auth & permissions (@login_required, @require_POST).
"""
import datetime
from decimal import Decimal
import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.projects.models import (
    ProjectApprovalGate,
    ProjectTask,
    ProjectWebhookDelivery,
    ProjectWebhookEndpoint,
    ProjectWorkflowRule,
    RecurringTaskSchedule,
    WorkflowExecutionLog,
)
from apps.projects.tests.conftest import (
    _workflowautomation_delivery,
    _workflowautomation_execution_log,
    _workflowautomation_gate,
    _workflowautomation_rule,
    _workflowautomation_schedule,
    _workflowautomation_today,
    _workflowautomation_webhook,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==================================================================================================
# Module-level Helpers (_workflowautomation_*)
# ==================================================================================================

def _workflowautomation_url(name, *args):
    return reverse(f"projects:{name}", args=args)


def _workflowautomation_get(client, name, /, *args, **params):
    return client.get(_workflowautomation_url(name, *args), params)


def _workflowautomation_post(client, name, /, *args, data=None, follow=False):
    return client.post(_workflowautomation_url(name, *args), data or {}, follow=follow)


def _workflowautomation_messages(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


def _workflowautomation_task(tenant, project, name="Test Task", **overrides):
    today = _workflowautomation_today()
    data = dict(
        tenant=tenant,
        project=project,
        name=name,
        node_type="work_package",
        planned_start=today,
        planned_end=today + datetime.timedelta(days=7),
    )
    data.update(overrides)
    return ProjectTask.objects.create(**data)


# ==================================================================================================
# 1. Operational Boards (AutomationBoards.py)
# ==================================================================================================

def test_workflowautomation_view_overview_get(
    client_a,
    tenant_a,
    workflowautomation_rule_a,
    workflowautomation_gate_a,
    workflowautomation_schedule_a,
    workflowautomation_webhook_a,
    workflowautomation_delivery_a,
):
    """GET automation_overview returns 200 with expected context keys and computed stats."""
    res = _workflowautomation_get(client_a, "automation_overview")
    assert res.status_code == 200
    assert "stats" in res.context
    assert "pending_gates" in res.context
    assert "recent_logs" in res.context
    assert "upcoming_recurring" in res.context

    stats = res.context["stats"]
    assert stats["rules_count"] >= 1
    assert stats["active_rules"] >= 1
    assert stats["pending_gates"] >= 1
    assert stats["active_schedules"] >= 1
    assert stats["active_webhooks"] >= 1


def test_workflowautomation_view_overview_isolation(
    client_a,
    tenant_a,
    tenant_b,
    workflowautomation_rule_b,
    workflowautomation_gate_b,
    workflowautomation_schedule_b,
    workflowautomation_webhook_b,
):
    """Tenant A's automation_overview does not count or display Tenant B's objects."""
    res = _workflowautomation_get(client_a, "automation_overview")
    assert res.status_code == 200
    stats = res.context["stats"]
    assert stats["rules_count"] == 0
    assert stats["pending_gates"] == 0
    assert stats["active_schedules"] == 0
    assert stats["active_webhooks"] == 0


def test_workflowautomation_view_overview_unauthenticated():
    """Unauthenticated access to automation_overview redirects to login."""
    anon = Client()
    res = _workflowautomation_get(anon, "automation_overview")
    assert res.status_code == 302
    assert "/login/" in res.url


def test_workflowautomation_view_approval_inbox_get(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_gate_a,
    workflowautomation_project_a,
):
    """GET approval_inbox returns 200 with my_gates and delegated_gates in context."""
    # Gate where admin_user is delegate_approver
    _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
        delegate_approver=admin_user,
        title="Delegated Gate A",
    )
    res = _workflowautomation_get(client_a, "approval_inbox")
    assert res.status_code == 200
    assert "gates" in res.context
    assert "delegated_gates" in res.context
    assert "stats" in res.context

    stats = res.context["stats"]
    assert stats["my_pending"] >= 1
    assert stats["delegated_pending"] >= 1


def test_workflowautomation_view_approval_inbox_isolation(
    client_a,
    workflowautomation_gate_b,
):
    """Tenant B gates never appear in Tenant A approver inbox."""
    res = _workflowautomation_get(client_a, "approval_inbox")
    assert res.status_code == 200
    gate_ids = [g.pk for g in res.context["gates"]]
    assert workflowautomation_gate_b.pk not in gate_ids


def test_workflowautomation_view_approval_inbox_unauthenticated():
    """Unauthenticated access to approval_inbox redirects to login."""
    anon = Client()
    res = _workflowautomation_get(anon, "approval_inbox")
    assert res.status_code == 302


def test_workflowautomation_view_recurrence_calendar_get(
    client_a,
    workflowautomation_schedule_a,
):
    """GET recurrence_calendar returns 200 with upcoming schedules and stats."""
    res = _workflowautomation_get(client_a, "recurrence_calendar")
    assert res.status_code == 200
    assert "upcoming_schedules" in res.context
    assert "stats" in res.context
    stats = res.context["stats"]
    assert stats["total_recurring"] >= 1
    assert stats["runs_this_month"] >= 1


def test_workflowautomation_view_recurrence_calendar_isolation(
    client_a,
    workflowautomation_schedule_b,
):
    """Tenant B recurring schedules do not appear in Tenant A calendar."""
    res = _workflowautomation_get(client_a, "recurrence_calendar")
    assert res.status_code == 200
    schedule_ids = [s.pk for s in res.context["upcoming_schedules"]]
    assert workflowautomation_schedule_b.pk not in schedule_ids


def test_workflowautomation_view_recurrence_calendar_unauthenticated():
    """Unauthenticated access to recurrence_calendar redirects to login."""
    anon = Client()
    res = _workflowautomation_get(anon, "recurrence_calendar")
    assert res.status_code == 302


def test_workflowautomation_view_webhook_diagnostics_get(
    client_a,
    workflowautomation_webhook_a,
    workflowautomation_delivery_a,
):
    """GET webhook_diagnostics returns 200 with endpoints, recent_failures, and stats."""
    res = _workflowautomation_get(client_a, "webhook_diagnostics")
    assert res.status_code == 200
    assert "endpoints" in res.context
    assert "recent_failures" in res.context
    assert "stats" in res.context
    stats = res.context["stats"]
    assert stats["total_endpoints"] >= 1
    assert stats["active_endpoints"] >= 1
    assert stats["success_rate_pct"] == 100.0


def test_workflowautomation_view_webhook_diagnostics_isolation(
    client_a,
    workflowautomation_webhook_b,
):
    """Tenant B endpoints do not appear in Tenant A webhook diagnostics."""
    res = _workflowautomation_get(client_a, "webhook_diagnostics")
    assert res.status_code == 200
    ep_ids = [ep.pk for ep in res.context["endpoints"]]
    assert workflowautomation_webhook_b.pk not in ep_ids


def test_workflowautomation_view_webhook_diagnostics_unauthenticated():
    """Unauthenticated access to webhook_diagnostics redirects to login."""
    anon = Client()
    res = _workflowautomation_get(anon, "webhook_diagnostics")
    assert res.status_code == 302


# ==================================================================================================
# 2. Workflow Rules (WorkflowRules.py)
# ==================================================================================================

def test_workflowautomation_view_pwf_list_get_and_context(
    client_a,
    workflowautomation_rule_a,
):
    """GET pwf_list returns 200 with all pinned context keys."""
    res = _workflowautomation_get(client_a, "pwf_list")
    assert res.status_code == 200
    for key in (
        "rules",
        "page_obj",
        "trigger_entity_choices",
        "trigger_event_choices",
        "projects",
        "stats",
        "q",
        "trigger_entity",
        "is_active",
        "project_id",
    ):
        assert key in res.context
    assert res.context["stats"]["total"] >= 1


def test_workflowautomation_view_pwf_list_search_and_filters(
    client_a,
    tenant_a,
    workflowautomation_project_a,
):
    """Test searching and filtering rules by q, trigger_entity, is_active, and project."""
    rule1 = _workflowautomation_rule(
        tenant_a,
        project=workflowautomation_project_a,
        name="Alpha Rule SearchTarget",
        trigger_entity="task",
        is_active=True,
    )
    rule2 = _workflowautomation_rule(
        tenant_a,
        project=workflowautomation_project_a,
        name="Beta Rule",
        trigger_entity="milestone",
        is_active=False,
    )

    # Search by q
    res_q = _workflowautomation_get(client_a, "pwf_list", q="SearchTarget")
    assert res_q.status_code == 200
    names = [r.name for r in res_q.context["rules"]]
    assert "Alpha Rule SearchTarget" in names
    assert "Beta Rule" not in names

    # Filter by trigger_entity
    res_entity = _workflowautomation_get(client_a, "pwf_list", trigger_entity="milestone")
    assert res_entity.status_code == 200
    names = [r.name for r in res_entity.context["rules"]]
    assert "Beta Rule" in names
    assert "Alpha Rule SearchTarget" not in names

    # Filter by is_active=true
    res_act = _workflowautomation_get(client_a, "pwf_list", is_active="true")
    assert res_act.status_code == 200
    assert all(r.is_active for r in res_act.context["rules"])

    # Filter by is_active=false
    res_inact = _workflowautomation_get(client_a, "pwf_list", is_active="false")
    assert res_inact.status_code == 200
    assert all(not r.is_active for r in res_inact.context["rules"])

    # Filter by project
    res_proj = _workflowautomation_get(client_a, "pwf_list", project=str(workflowautomation_project_a.pk))
    assert res_proj.status_code == 200
    assert len(res_proj.context["rules"]) >= 2


def test_workflowautomation_view_pwf_list_negative_input_and_pagination(
    client_a,
    tenant_a,
    workflowautomation_project_a,
):
    """Junk GET params (?project=abc, ?is_active=junk, ?page=999) return 200 without 500 error."""
    # Negative input hardening
    res_junk = _workflowautomation_get(
        client_a, "pwf_list", project="abc", is_active="unknown", page="999", junk="123"
    )
    assert res_junk.status_code == 200

    # Create 26 rules to test pagination (per_page=25)
    for i in range(26):
        _workflowautomation_rule(
            tenant_a,
            project=workflowautomation_project_a,
            name=f"Paging Rule {i}",
        )
    res_p1 = _workflowautomation_get(client_a, "pwf_list", page="1")
    assert res_p1.status_code == 200
    assert len(res_p1.context["rules"]) == 25

    res_p2 = _workflowautomation_get(client_a, "pwf_list", page="2")
    assert res_p2.status_code == 200
    assert len(res_p2.context["rules"]) >= 1


def test_workflowautomation_view_pwf_list_isolation(
    client_a,
    workflowautomation_rule_b,
):
    """Tenant A's rule list never contains Tenant B's rules."""
    res = _workflowautomation_get(client_a, "pwf_list")
    assert res.status_code == 200
    rule_ids = [r.pk for r in res.context["rules"]]
    assert workflowautomation_rule_b.pk not in rule_ids


def test_workflowautomation_view_pwf_create_get(
    client_a,
    workflowautomation_project_a,
):
    """GET pwf_create returns 200 with form, rule=None, is_edit=False."""
    res = _workflowautomation_get(client_a, "pwf_create", project=str(workflowautomation_project_a.pk))
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["rule"] is None
    assert res.context["is_edit"] is False


def test_workflowautomation_view_pwf_create_post_valid(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """POST valid data creates ProjectWorkflowRule and redirects to pwf_detail."""
    data = {
        "name": "Auto Escalation Rule",
        "description": "Escalates after 24h",
        "project": workflowautomation_project_a.pk,
        "is_active": "on",
        "trigger_entity": "task",
        "trigger_event": "status_changed",
        "conditions": json.dumps([{"field": "status", "operator": "equals", "value": "blocked"}]),
        "actions": json.dumps([{"type": "notify", "parameters": {"channel": "email"}}]),
    }
    res = _workflowautomation_post(client_a, "pwf_create", data=data)
    assert res.status_code == 302
    created = ProjectWorkflowRule.objects.filter(tenant=tenant_a, name="Auto Escalation Rule").first()
    assert created is not None
    assert created.owner == admin_user
    assert res.url == _workflowautomation_url("pwf_detail", created.pk)


def test_workflowautomation_view_pwf_create_post_invalid(client_a):
    """POST invalid data returns 200 and re-renders form with errors."""
    res = _workflowautomation_post(client_a, "pwf_create", data={"name": ""})
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["form"].errors


def test_workflowautomation_view_pwf_detail_get(
    client_a,
    workflowautomation_rule_a,
    admin_user,
):
    """GET pwf_detail returns 200 with rule, execution_logs, test_form."""
    workflowautomation_rule_a.owner = admin_user
    workflowautomation_rule_a.save(update_fields=["owner"])
    res = _workflowautomation_get(client_a, "pwf_detail", workflowautomation_rule_a.pk)
    assert res.status_code == 200
    assert res.context["rule"] == workflowautomation_rule_a
    assert "execution_logs" in res.context
    assert "test_form" in res.context


def test_workflowautomation_view_pwf_detail_isolation(
    client_a,
    workflowautomation_rule_b,
):
    """Tenant A accessing Tenant B's rule detail returns 404."""
    res = _workflowautomation_get(client_a, "pwf_detail", workflowautomation_rule_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_pwf_edit_get(
    client_a,
    workflowautomation_rule_a,
):
    """GET pwf_edit returns 200 with is_edit=True."""
    res = _workflowautomation_get(client_a, "pwf_edit", workflowautomation_rule_a.pk)
    assert res.status_code == 200
    assert res.context["rule"] == workflowautomation_rule_a
    assert res.context["is_edit"] is True


def test_workflowautomation_view_pwf_edit_post_valid(
    client_a,
    workflowautomation_rule_a,
    workflowautomation_project_a,
):
    """POST valid update to rule redirects to pwf_detail and persists changes."""
    data = {
        "name": "Updated Rule Name",
        "description": "Updated Description",
        "project": workflowautomation_project_a.pk,
        "is_active": "on",
        "trigger_entity": "task",
        "trigger_event": "status_changed",
        "conditions": json.dumps([]),
        "actions": json.dumps([]),
    }
    res = _workflowautomation_post(client_a, "pwf_edit", workflowautomation_rule_a.pk, data=data)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("pwf_detail", workflowautomation_rule_a.pk)
    workflowautomation_rule_a.refresh_from_db()
    assert workflowautomation_rule_a.name == "Updated Rule Name"


def test_workflowautomation_view_pwf_edit_isolation(
    client_a,
    workflowautomation_rule_b,
):
    """Tenant A editing Tenant B's rule returns 404."""
    res = _workflowautomation_get(client_a, "pwf_edit", workflowautomation_rule_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_pwf_delete_post(
    client_a,
    tenant_a,
    workflowautomation_project_a,
):
    """POST pwf_delete deletes the rule and redirects to pwf_list."""
    rule = _workflowautomation_rule(tenant_a, project=workflowautomation_project_a, name="To Delete")
    res = _workflowautomation_post(client_a, "pwf_delete", rule.pk)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("pwf_list")
    assert not ProjectWorkflowRule.objects.filter(pk=rule.pk).exists()


def test_workflowautomation_view_pwf_delete_get_not_allowed(
    client_a,
    workflowautomation_rule_a,
):
    """GET pwf_delete is rejected with 405 Method Not Allowed (@require_POST)."""
    res = _workflowautomation_get(client_a, "pwf_delete", workflowautomation_rule_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_pwf_delete_isolation(
    client_a,
    workflowautomation_rule_b,
):
    """Tenant A deleting Tenant B's rule returns 404."""
    res = _workflowautomation_post(client_a, "pwf_delete", workflowautomation_rule_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_pwf_toggle_active_post(
    client_a,
    workflowautomation_rule_a,
):
    """POST pwf_toggle_active flips is_active state and redirects to pwf_detail."""
    initial = workflowautomation_rule_a.is_active
    res = _workflowautomation_post(client_a, "pwf_toggle_active", workflowautomation_rule_a.pk)
    assert res.status_code == 302
    workflowautomation_rule_a.refresh_from_db()
    assert workflowautomation_rule_a.is_active != initial

    # Toggle back
    res2 = _workflowautomation_post(client_a, "pwf_toggle_active", workflowautomation_rule_a.pk)
    assert res2.status_code == 302
    workflowautomation_rule_a.refresh_from_db()
    assert workflowautomation_rule_a.is_active == initial


def test_workflowautomation_view_pwf_toggle_active_get_not_allowed(
    client_a,
    workflowautomation_rule_a,
):
    """GET pwf_toggle_active returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "pwf_toggle_active", workflowautomation_rule_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_pwf_toggle_active_isolation(
    client_a,
    workflowautomation_rule_b,
):
    """Tenant A toggling Tenant B's rule returns 404."""
    res = _workflowautomation_post(client_a, "pwf_toggle_active", workflowautomation_rule_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_pwf_test_run_success(
    client_a,
    tenant_a,
    workflowautomation_rule_a,
    workflowautomation_project_a,
):
    """POST pwf_test_run creates simulated WorkflowExecutionLog without mutating target."""
    task = _workflowautomation_task(tenant_a, workflowautomation_project_a, name="Task for Test Run")
    res = _workflowautomation_post(
        client_a, "pwf_test_run", workflowautomation_rule_a.pk, data={"target_id": task.pk}
    )
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("pwf_detail", workflowautomation_rule_a.pk)

    log = WorkflowExecutionLog.objects.filter(rule=workflowautomation_rule_a, target_id=task.pk).first()
    assert log is not None
    assert log.status == "simulated"


def test_workflowautomation_view_pwf_test_run_target_not_found(
    client_a,
    workflowautomation_rule_a,
):
    """POST pwf_test_run with non-existent target shows error message and redirects."""
    res = _workflowautomation_post(
        client_a, "pwf_test_run", workflowautomation_rule_a.pk, data={"target_id": 999999}
    )
    assert res.status_code == 302
    messages = _workflowautomation_messages(res)
    assert any("not found" in m.lower() for m in messages)


def test_workflowautomation_view_pwf_test_run_get_not_allowed(
    client_a,
    workflowautomation_rule_a,
):
    """GET pwf_test_run returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "pwf_test_run", workflowautomation_rule_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_pwf_test_run_isolation(
    client_a,
    workflowautomation_rule_b,
):
    """Tenant A posting test_run on Tenant B rule returns 404."""
    res = _workflowautomation_post(client_a, "pwf_test_run", workflowautomation_rule_b.pk, data={"target_id": 1})
    assert res.status_code == 404


def test_workflowautomation_view_pwf_execute_now_success(
    client_a,
    tenant_a,
    workflowautomation_rule_a,
    workflowautomation_project_a,
):
    """POST pwf_execute_now executes rule, increments execution_count, and logs success."""
    task = _workflowautomation_task(tenant_a, workflowautomation_project_a, name="Task for Execution")
    initial_count = workflowautomation_rule_a.execution_count

    res = _workflowautomation_post(
        client_a, "pwf_execute_now", workflowautomation_rule_a.pk, data={"target_id": task.pk}
    )
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("pwf_detail", workflowautomation_rule_a.pk)

    workflowautomation_rule_a.refresh_from_db()
    assert workflowautomation_rule_a.execution_count == initial_count + 1
    assert workflowautomation_rule_a.last_fired_at is not None

    log = WorkflowExecutionLog.objects.filter(rule=workflowautomation_rule_a, status="success").first()
    assert log is not None


def test_workflowautomation_view_pwf_execute_now_target_not_found(
    client_a,
    workflowautomation_rule_a,
):
    """POST pwf_execute_now with invalid target shows error and does not increment count."""
    initial_count = workflowautomation_rule_a.execution_count
    res = _workflowautomation_post(
        client_a, "pwf_execute_now", workflowautomation_rule_a.pk, data={"target_id": 999999}
    )
    assert res.status_code == 302
    workflowautomation_rule_a.refresh_from_db()
    assert workflowautomation_rule_a.execution_count == initial_count


def test_workflowautomation_view_pwf_execute_now_get_not_allowed(
    client_a,
    workflowautomation_rule_a,
):
    """GET pwf_execute_now returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "pwf_execute_now", workflowautomation_rule_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_pwf_execute_now_isolation(
    client_a,
    workflowautomation_rule_b,
):
    """Tenant A running execute_now on Tenant B rule returns 404."""
    res = _workflowautomation_post(
        client_a, "pwf_execute_now", workflowautomation_rule_b.pk, data={"target_id": 1}
    )
    assert res.status_code == 404


# ==================================================================================================
# 3. Approval Gates (ApprovalGates.py)
# ==================================================================================================

def test_workflowautomation_view_par_list_get_and_context(
    client_a,
    workflowautomation_gate_a,
):
    """GET par_list returns 200 with all pinned context keys."""
    res = _workflowautomation_get(client_a, "par_list")
    assert res.status_code == 200
    for key in (
        "gates",
        "page_obj",
        "gate_type_choices",
        "status_choices",
        "projects",
        "stats",
        "q",
        "gate_type",
        "status",
        "project_id",
    ):
        assert key in res.context
    assert res.context["stats"]["total"] >= 1


def test_workflowautomation_view_par_list_search_and_filters(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """Filter par_list by q, gate_type, status, and project."""
    gate1 = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
        title="Gate Alpha UniqueSearch",
        gate_type="phase_gate",
        status="pending",
    )
    gate2 = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
        title="Gate Beta",
        gate_type="budget_override",
        status="approved",
    )

    # Search by q
    res_q = _workflowautomation_get(client_a, "par_list", q="UniqueSearch")
    assert res_q.status_code == 200
    titles = [g.title for g in res_q.context["gates"]]
    assert "Gate Alpha UniqueSearch" in titles
    assert "Gate Beta" not in titles

    # Filter by gate_type
    res_type = _workflowautomation_get(client_a, "par_list", gate_type="budget_override")
    assert res_type.status_code == 200
    titles = [g.title for g in res_type.context["gates"]]
    assert "Gate Beta" in titles

    # Filter by status
    res_stat = _workflowautomation_get(client_a, "par_list", status="approved")
    assert res_stat.status_code == 200
    assert all(g.status == "approved" for g in res_stat.context["gates"])

    # Filter by project
    res_proj = _workflowautomation_get(client_a, "par_list", project=str(workflowautomation_project_a.pk))
    assert res_proj.status_code == 200
    assert len(res_proj.context["gates"]) >= 2


def test_workflowautomation_view_par_list_negative_input_and_pagination(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """Junk GET params return 200 without 500 error, and page 2 pagination works."""
    res_junk = _workflowautomation_get(
        client_a, "par_list", project="xyz", status="junk", page="999", junk="123"
    )
    assert res_junk.status_code == 200

    # Create 26 gates to test pagination (per_page=25)
    for i in range(26):
        _workflowautomation_gate(
            tenant_a,
            workflowautomation_project_a,
            requested_by=admin_user,
            approver=admin_user,
            title=f"Paged Gate {i}",
        )
    res_p1 = _workflowautomation_get(client_a, "par_list", page="1")
    assert res_p1.status_code == 200
    assert len(res_p1.context["gates"]) == 25

    res_p2 = _workflowautomation_get(client_a, "par_list", page="2")
    assert res_p2.status_code == 200
    assert len(res_p2.context["gates"]) >= 1


def test_workflowautomation_view_par_list_isolation(
    client_a,
    workflowautomation_gate_b,
):
    """Tenant A's gate list never contains Tenant B's gates."""
    res = _workflowautomation_get(client_a, "par_list")
    assert res.status_code == 200
    gate_ids = [g.pk for g in res.context["gates"]]
    assert workflowautomation_gate_b.pk not in gate_ids


def test_workflowautomation_view_par_create_get(
    client_a,
    workflowautomation_project_a,
):
    """GET par_create returns 200 with form, gate=None, is_edit=False."""
    res = _workflowautomation_get(client_a, "par_create", project=str(workflowautomation_project_a.pk))
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["gate"] is None
    assert res.context["is_edit"] is False


def test_workflowautomation_view_par_create_post_valid(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """POST valid gate data creates ProjectApprovalGate with requested_by=user."""
    data = {
        "project": workflowautomation_project_a.pk,
        "gate_type": "phase_gate",
        "title": "Phase 2 Signoff",
        "description": "Signoff needed for Phase 2",
        "target_model": "milestone",
        "target_id": 42,
        "target_label": "Milestone M2",
        "approver": admin_user.pk,
        "timeout_hours": 72,
    }
    res = _workflowautomation_post(client_a, "par_create", data=data)
    assert res.status_code == 302
    gate = ProjectApprovalGate.objects.filter(tenant=tenant_a, title="Phase 2 Signoff").first()
    assert gate is not None
    assert gate.requested_by == admin_user
    assert res.url == _workflowautomation_url("par_detail", gate.pk)


def test_workflowautomation_view_par_create_post_invalid(client_a):
    """POST invalid gate data returns 200 and re-renders form."""
    res = _workflowautomation_post(client_a, "par_create", data={"title": ""})
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["form"].errors


def test_workflowautomation_view_par_detail_get(
    client_a,
    workflowautomation_gate_a,
):
    """GET par_detail returns 200 with gate, decision_form, delegate_form."""
    res = _workflowautomation_get(client_a, "par_detail", workflowautomation_gate_a.pk)
    assert res.status_code == 200
    assert res.context["gate"] == workflowautomation_gate_a
    assert "decision_form" in res.context
    assert "delegate_form" in res.context


def test_workflowautomation_view_par_detail_isolation(
    client_a,
    workflowautomation_gate_b,
):
    """Tenant A accessing Tenant B gate returns 404."""
    res = _workflowautomation_get(client_a, "par_detail", workflowautomation_gate_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_par_edit_get(
    client_a,
    workflowautomation_gate_a,
):
    """GET par_edit on pending gate returns 200 with is_edit=True."""
    res = _workflowautomation_get(client_a, "par_edit", workflowautomation_gate_a.pk)
    assert res.status_code == 200
    assert res.context["gate"] == workflowautomation_gate_a
    assert res.context["is_edit"] is True


def test_workflowautomation_view_par_edit_terminal_gate_blocked(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """GET or POST par_edit on a terminal gate redirects to par_detail with warning."""
    terminal_gate = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
        status="approved",
    )
    res = _workflowautomation_get(client_a, "par_edit", terminal_gate.pk)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("par_detail", terminal_gate.pk)
    messages = _workflowautomation_messages(res)
    assert any("terminal" in m.lower() for m in messages)


def test_workflowautomation_view_par_edit_post_valid(
    client_a,
    workflowautomation_gate_a,
    admin_user,
    workflowautomation_project_a,
):
    """POST valid update to gate redirects to par_detail and updates title."""
    data = {
        "project": workflowautomation_project_a.pk,
        "gate_type": "phase_gate",
        "title": "Updated Gate Title",
        "target_model": "milestone",
        "target_id": 1,
        "approver": admin_user.pk,
        "timeout_hours": 48,
    }
    res = _workflowautomation_post(client_a, "par_edit", workflowautomation_gate_a.pk, data=data)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("par_detail", workflowautomation_gate_a.pk)
    workflowautomation_gate_a.refresh_from_db()
    assert workflowautomation_gate_a.title == "Updated Gate Title"


def test_workflowautomation_view_par_edit_isolation(
    client_a,
    workflowautomation_gate_b,
):
    """Tenant A editing Tenant B gate returns 404."""
    res = _workflowautomation_get(client_a, "par_edit", workflowautomation_gate_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_par_delete_pending_or_cancelled(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """POST par_delete successfully deletes pending or cancelled gates."""
    gate1 = _workflowautomation_gate(
        tenant_a, workflowautomation_project_a, requested_by=admin_user, approver=admin_user, status="pending"
    )
    res1 = _workflowautomation_post(client_a, "par_delete", gate1.pk)
    assert res1.status_code == 302
    assert not ProjectApprovalGate.objects.filter(pk=gate1.pk).exists()

    gate2 = _workflowautomation_gate(
        tenant_a, workflowautomation_project_a, requested_by=admin_user, approver=admin_user, status="cancelled"
    )
    res2 = _workflowautomation_post(client_a, "par_delete", gate2.pk)
    assert res2.status_code == 302
    assert not ProjectApprovalGate.objects.filter(pk=gate2.pk).exists()


def test_workflowautomation_view_par_delete_terminal_gate_rejected(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """POST par_delete on terminal gate (approved/rejected) is rejected with error message."""
    gate_approved = _workflowautomation_gate(
        tenant_a, workflowautomation_project_a, requested_by=admin_user, approver=admin_user, status="approved"
    )
    res = _workflowautomation_post(client_a, "par_delete", gate_approved.pk)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("par_detail", gate_approved.pk)
    assert ProjectApprovalGate.objects.filter(pk=gate_approved.pk).exists()
    messages = _workflowautomation_messages(res)
    assert any("cannot delete" in m.lower() for m in messages)


def test_workflowautomation_view_par_delete_get_not_allowed(
    client_a,
    workflowautomation_gate_a,
):
    """GET par_delete returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "par_delete", workflowautomation_gate_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_par_delete_isolation(
    client_a,
    workflowautomation_gate_b,
):
    """Tenant A deleting Tenant B gate returns 404."""
    res = _workflowautomation_post(client_a, "par_delete", workflowautomation_gate_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_par_approve_success(
    client_a,
    workflowautomation_gate_a,
):
    """Approver approves pending gate; status transitions to 'approved' and decided_at is set."""
    res = _workflowautomation_post(
        client_a, "par_approve", workflowautomation_gate_a.pk, data={"decision_notes": "Looks good"}
    )
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("par_detail", workflowautomation_gate_a.pk)

    workflowautomation_gate_a.refresh_from_db()
    assert workflowautomation_gate_a.status == "approved"
    assert workflowautomation_gate_a.decided_at is not None
    assert workflowautomation_gate_a.decision_notes == "Looks good"


def test_workflowautomation_view_par_approve_self_approval_rejected(
    tenant_a,
    member_user,
    workflowautomation_project_a,
):
    """Non-admin requester cannot self-approve their own approval gate."""
    # Create non-admin client
    member_c = Client()
    member_c.force_login(member_user)

    # Gate where member_user is BOTH requester and approver
    gate = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=member_user,
        approver=member_user,
        status="pending",
    )
    res = _workflowautomation_post(member_c, "par_approve", gate.pk)
    assert res.status_code == 302
    gate.refresh_from_db()
    assert gate.status == "pending"  # Self-approval refused!
    messages = _workflowautomation_messages(res)
    assert any("requesters cannot approve their own" in m.lower() for m in messages)


def test_workflowautomation_view_par_approve_unauthorized_user_rejected(
    tenant_a,
    admin_user,
    member_user,
    workflowautomation_project_a,
):
    """User who is neither approver, delegate, nor admin cannot approve gate."""
    member_c = Client()
    member_c.force_login(member_user)

    gate = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
        status="pending",
    )
    res = _workflowautomation_post(member_c, "par_approve", gate.pk)
    assert res.status_code == 302
    gate.refresh_from_db()
    assert gate.status == "pending"
    messages = _workflowautomation_messages(res)
    assert any("not authorized" in m.lower() for m in messages)


def test_workflowautomation_view_par_approve_terminal_gate_rejected(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """Terminal gate cannot be approved again."""
    gate = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
        status="approved",
    )
    res = _workflowautomation_post(client_a, "par_approve", gate.pk)
    assert res.status_code == 302
    messages = _workflowautomation_messages(res)
    assert any("already in state" in m.lower() for m in messages)


def test_workflowautomation_view_par_approve_get_not_allowed(
    client_a,
    workflowautomation_gate_a,
):
    """GET par_approve returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "par_approve", workflowautomation_gate_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_par_approve_isolation(
    client_a,
    workflowautomation_gate_b,
):
    """Tenant A approving Tenant B gate returns 404."""
    res = _workflowautomation_post(client_a, "par_approve", workflowautomation_gate_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_par_reject_success(
    client_a,
    workflowautomation_gate_a,
):
    """Approver rejects gate; status transitions to 'rejected'."""
    res = _workflowautomation_post(
        client_a, "par_reject", workflowautomation_gate_a.pk, data={"decision_notes": "Needs revision"}
    )
    assert res.status_code == 302
    workflowautomation_gate_a.refresh_from_db()
    assert workflowautomation_gate_a.status == "rejected"
    assert workflowautomation_gate_a.decided_at is not None
    assert workflowautomation_gate_a.decision_notes == "Needs revision"


def test_workflowautomation_view_par_reject_unauthorized_user_rejected(
    tenant_a,
    admin_user,
    member_user,
    workflowautomation_project_a,
):
    """Unauthorized user cannot reject gate."""
    member_c = Client()
    member_c.force_login(member_user)

    gate = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
        status="pending",
    )
    res = _workflowautomation_post(member_c, "par_reject", gate.pk)
    assert res.status_code == 302
    gate.refresh_from_db()
    assert gate.status == "pending"


def test_workflowautomation_view_par_reject_get_not_allowed(
    client_a,
    workflowautomation_gate_a,
):
    """GET par_reject returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "par_reject", workflowautomation_gate_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_par_reject_isolation(
    client_a,
    workflowautomation_gate_b,
):
    """Tenant A rejecting Tenant B gate returns 404."""
    res = _workflowautomation_post(client_a, "par_reject", workflowautomation_gate_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_par_escalate_success(
    client_a,
    workflowautomation_gate_a,
):
    """Escalating pending gate sets status='escalated' and sets escalated_at."""
    res = _workflowautomation_post(client_a, "par_escalate", workflowautomation_gate_a.pk)
    assert res.status_code == 302
    workflowautomation_gate_a.refresh_from_db()
    assert workflowautomation_gate_a.status == "escalated"
    assert workflowautomation_gate_a.escalated_at is not None


def test_workflowautomation_view_par_escalate_unauthorized_user_rejected(
    tenant_a,
    admin_user,
    member_user,
    workflowautomation_project_a,
):
    """Unauthorized user cannot escalate gate."""
    member_c = Client()
    member_c.force_login(member_user)

    gate = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
        status="pending",
    )
    res = _workflowautomation_post(member_c, "par_escalate", gate.pk)
    assert res.status_code == 302
    gate.refresh_from_db()
    assert gate.status == "pending"


def test_workflowautomation_view_par_escalate_get_not_allowed(
    client_a,
    workflowautomation_gate_a,
):
    """GET par_escalate returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "par_escalate", workflowautomation_gate_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_par_escalate_isolation(
    client_a,
    workflowautomation_gate_b,
):
    """Tenant A escalating Tenant B gate returns 404."""
    res = _workflowautomation_post(client_a, "par_escalate", workflowautomation_gate_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_par_delegate_success(
    client_a,
    tenant_a,
    workflowautomation_gate_a,
    member_user,
):
    """Delegating approval gate to another user in same tenant succeeds."""
    res = _workflowautomation_post(
        client_a,
        "par_delegate",
        workflowautomation_gate_a.pk,
        data={"delegate_approver": member_user.pk, "notes": "On annual leave"},
    )
    assert res.status_code == 302
    workflowautomation_gate_a.refresh_from_db()
    assert workflowautomation_gate_a.delegate_approver == member_user


def test_workflowautomation_view_par_delegate_cross_tenant_rejected(
    client_a,
    workflowautomation_gate_a,
    admin_b,
):
    """Delegating approval gate to user from another tenant is rejected."""
    res = _workflowautomation_post(
        client_a,
        "par_delegate",
        workflowautomation_gate_a.pk,
        data={"delegate_approver": admin_b.pk},
    )
    assert res.status_code == 302
    workflowautomation_gate_a.refresh_from_db()
    assert workflowautomation_gate_a.delegate_approver != admin_b
    messages = _workflowautomation_messages(res)
    assert any("valid user" in m.lower() or "tenant" in m.lower() for m in messages)


def test_workflowautomation_view_par_delegate_get_not_allowed(
    client_a,
    workflowautomation_gate_a,
):
    """GET par_delegate returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "par_delegate", workflowautomation_gate_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_par_delegate_isolation(
    client_a,
    workflowautomation_gate_b,
    member_user,
):
    """Tenant A delegating Tenant B gate returns 404."""
    res = _workflowautomation_post(
        client_a,
        "par_delegate",
        workflowautomation_gate_b.pk,
        data={"delegate_approver": member_user.pk},
    )
    assert res.status_code == 404


def test_workflowautomation_view_par_cancel_success(
    client_a,
    workflowautomation_gate_a,
):
    """POST par_cancel sets status to 'cancelled'."""
    res = _workflowautomation_post(client_a, "par_cancel", workflowautomation_gate_a.pk)
    assert res.status_code == 302
    workflowautomation_gate_a.refresh_from_db()
    assert workflowautomation_gate_a.status == "cancelled"


def test_workflowautomation_view_par_cancel_get_not_allowed(
    client_a,
    workflowautomation_gate_a,
):
    """GET par_cancel returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "par_cancel", workflowautomation_gate_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_par_cancel_isolation(
    client_a,
    workflowautomation_gate_b,
):
    """Tenant A cancelling Tenant B gate returns 404."""
    res = _workflowautomation_post(client_a, "par_cancel", workflowautomation_gate_b.pk)
    assert res.status_code == 404


# ==================================================================================================
# 4. Recurring Tasks (RecurringTasks.py)
# ==================================================================================================

def test_workflowautomation_view_rts_list_get_and_context(
    client_a,
    workflowautomation_schedule_a,
):
    """GET rts_list returns 200 with all pinned context keys."""
    res = _workflowautomation_get(client_a, "rts_list")
    assert res.status_code == 200
    for key in (
        "schedules",
        "page_obj",
        "frequency_choices",
        "priority_choices",
        "projects",
        "stats",
        "q",
        "frequency",
        "is_active",
        "project_id",
    ):
        assert key in res.context
    assert res.context["stats"]["total"] >= 1


def test_workflowautomation_view_rts_list_search_and_filters(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """Filter rts_list by q, frequency, is_active, and project."""
    sch1 = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        default_assignee=admin_user,
        title_template="Weekly Sprint Sync UniqueTarget",
        frequency="weekly",
        is_active=True,
    )
    sch2 = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        default_assignee=admin_user,
        title_template="Monthly Backlog Review",
        frequency="monthly",
        is_active=False,
    )

    # Search by q
    res_q = _workflowautomation_get(client_a, "rts_list", q="UniqueTarget")
    assert res_q.status_code == 200
    titles = [s.title_template for s in res_q.context["schedules"]]
    assert "Weekly Sprint Sync UniqueTarget" in titles
    assert "Monthly Backlog Review" not in titles

    # Filter by frequency
    res_freq = _workflowautomation_get(client_a, "rts_list", frequency="monthly")
    assert res_freq.status_code == 200
    titles = [s.title_template for s in res_freq.context["schedules"]]
    assert "Monthly Backlog Review" in titles

    # Filter by is_active=true
    res_act = _workflowautomation_get(client_a, "rts_list", is_active="true")
    assert res_act.status_code == 200
    assert all(s.is_active for s in res_act.context["schedules"])

    # Filter by project
    res_proj = _workflowautomation_get(client_a, "rts_list", project=str(workflowautomation_project_a.pk))
    assert res_proj.status_code == 200
    assert len(res_proj.context["schedules"]) >= 2


def test_workflowautomation_view_rts_list_negative_input_and_pagination(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """Junk GET params return 200 without 500 error, and page 2 pagination works."""
    res_junk = _workflowautomation_get(
        client_a, "rts_list", project="xyz", frequency="junk", page="999", junk="123"
    )
    assert res_junk.status_code == 200

    # Create 26 schedules to test pagination (per_page=25)
    for i in range(26):
        _workflowautomation_schedule(
            tenant_a,
            workflowautomation_project_a,
            default_assignee=admin_user,
            title_template=f"Paging Schedule {i}",
        )
    res_p1 = _workflowautomation_get(client_a, "rts_list", page="1")
    assert res_p1.status_code == 200
    assert len(res_p1.context["schedules"]) == 25

    res_p2 = _workflowautomation_get(client_a, "rts_list", page="2")
    assert res_p2.status_code == 200
    assert len(res_p2.context["schedules"]) >= 1


def test_workflowautomation_view_rts_list_isolation(
    client_a,
    workflowautomation_schedule_b,
):
    """Tenant A's schedule list never contains Tenant B's schedules."""
    res = _workflowautomation_get(client_a, "rts_list")
    assert res.status_code == 200
    schedule_ids = [s.pk for s in res.context["schedules"]]
    assert workflowautomation_schedule_b.pk not in schedule_ids


def test_workflowautomation_view_rts_create_get(
    client_a,
    workflowautomation_project_a,
):
    """GET rts_create returns 200 with form, schedule=None, is_edit=False."""
    res = _workflowautomation_get(client_a, "rts_create", project=str(workflowautomation_project_a.pk))
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["schedule"] is None
    assert res.context["is_edit"] is False


def test_workflowautomation_view_rts_create_post_valid(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """POST valid data creates RecurringTaskSchedule and redirects to rts_detail."""
    today = _workflowautomation_today()
    data = {
        "project": workflowautomation_project_a.pk,
        "title_template": "Weekly Standup {{date}}",
        "description_template": "Standup notes",
        "is_active": "on",
        "frequency": "weekly",
        "interval_count": 1,
        "priority": "medium",
        "effort_hours": "1.50",
        "assignee_strategy": "fixed_user",
        "default_assignee": admin_user.pk,
        "start_date": today.isoformat(),
        "next_run_date": today.isoformat(),
    }
    res = _workflowautomation_post(client_a, "rts_create", data=data)
    assert res.status_code == 302
    sch = RecurringTaskSchedule.objects.filter(tenant=tenant_a, title_template="Weekly Standup {{date}}").first()
    assert sch is not None
    assert res.url == _workflowautomation_url("rts_detail", sch.pk)


def test_workflowautomation_view_rts_create_post_invalid(client_a):
    """POST invalid data returns 200 and re-renders form."""
    res = _workflowautomation_post(client_a, "rts_create", data={"title_template": ""})
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["form"].errors


def test_workflowautomation_view_rts_detail_get(
    client_a,
    workflowautomation_schedule_a,
):
    """GET rts_detail returns 200 with schedule and recent_tasks."""
    res = _workflowautomation_get(client_a, "rts_detail", workflowautomation_schedule_a.pk)
    assert res.status_code == 200
    assert res.context["schedule"] == workflowautomation_schedule_a
    assert "recent_tasks" in res.context


def test_workflowautomation_view_rts_detail_isolation(
    client_a,
    workflowautomation_schedule_b,
):
    """Tenant A accessing Tenant B schedule returns 404."""
    res = _workflowautomation_get(client_a, "rts_detail", workflowautomation_schedule_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_rts_edit_get(
    client_a,
    workflowautomation_schedule_a,
):
    """GET rts_edit returns 200 with is_edit=True."""
    res = _workflowautomation_get(client_a, "rts_edit", workflowautomation_schedule_a.pk)
    assert res.status_code == 200
    assert res.context["schedule"] == workflowautomation_schedule_a
    assert res.context["is_edit"] is True


def test_workflowautomation_view_rts_edit_post_valid(
    client_a,
    workflowautomation_schedule_a,
    workflowautomation_project_a,
    admin_user,
):
    """POST valid update to schedule redirects to rts_detail."""
    today = _workflowautomation_today()
    data = {
        "project": workflowautomation_project_a.pk,
        "title_template": "Updated Recurring Title",
        "description_template": "Updated Description",
        "is_active": "on",
        "frequency": "biweekly",
        "interval_count": 1,
        "priority": "high",
        "effort_hours": "3.00",
        "assignee_strategy": "fixed_user",
        "default_assignee": admin_user.pk,
        "start_date": today.isoformat(),
        "next_run_date": today.isoformat(),
    }
    res = _workflowautomation_post(client_a, "rts_edit", workflowautomation_schedule_a.pk, data=data)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("rts_detail", workflowautomation_schedule_a.pk)
    workflowautomation_schedule_a.refresh_from_db()
    assert workflowautomation_schedule_a.title_template == "Updated Recurring Title"
    assert workflowautomation_schedule_a.frequency == "biweekly"


def test_workflowautomation_view_rts_edit_isolation(
    client_a,
    workflowautomation_schedule_b,
):
    """Tenant A editing Tenant B schedule returns 404."""
    res = _workflowautomation_get(client_a, "rts_edit", workflowautomation_schedule_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_rts_delete_post(
    client_a,
    tenant_a,
    workflowautomation_project_a,
    admin_user,
):
    """POST rts_delete deletes the schedule and redirects to rts_list."""
    sch = _workflowautomation_schedule(
        tenant_a, workflowautomation_project_a, default_assignee=admin_user, title_template="To Delete"
    )
    res = _workflowautomation_post(client_a, "rts_delete", sch.pk)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("rts_list")
    assert not RecurringTaskSchedule.objects.filter(pk=sch.pk).exists()


def test_workflowautomation_view_rts_delete_get_not_allowed(
    client_a,
    workflowautomation_schedule_a,
):
    """GET rts_delete returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "rts_delete", workflowautomation_schedule_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_rts_delete_isolation(
    client_a,
    workflowautomation_schedule_b,
):
    """Tenant A deleting Tenant B schedule returns 404."""
    res = _workflowautomation_post(client_a, "rts_delete", workflowautomation_schedule_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_rts_toggle_active_post(
    client_a,
    workflowautomation_schedule_a,
):
    """POST rts_toggle_active flips is_active state and redirects to rts_detail."""
    initial = workflowautomation_schedule_a.is_active
    res = _workflowautomation_post(client_a, "rts_toggle_active", workflowautomation_schedule_a.pk)
    assert res.status_code == 302
    workflowautomation_schedule_a.refresh_from_db()
    assert workflowautomation_schedule_a.is_active != initial


def test_workflowautomation_view_rts_toggle_active_get_not_allowed(
    client_a,
    workflowautomation_schedule_a,
):
    """GET rts_toggle_active returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "rts_toggle_active", workflowautomation_schedule_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_rts_toggle_active_isolation(
    client_a,
    workflowautomation_schedule_b,
):
    """Tenant A toggling Tenant B schedule returns 404."""
    res = _workflowautomation_post(client_a, "rts_toggle_active", workflowautomation_schedule_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_rts_generate_task_post(
    client_a,
    workflowautomation_schedule_a,
    admin_user,
):
    """POST rts_generate_task creates a ProjectTask with correct fields and advances next_run_date."""
    initial_count = workflowautomation_schedule_a.tasks_created_count
    old_run_date = workflowautomation_schedule_a.next_run_date

    res = _workflowautomation_post(client_a, "rts_generate_task", workflowautomation_schedule_a.pk)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("rts_detail", workflowautomation_schedule_a.pk)

    workflowautomation_schedule_a.refresh_from_db()
    assert workflowautomation_schedule_a.tasks_created_count == initial_count + 1
    assert workflowautomation_schedule_a.next_run_date > old_run_date

    task = ProjectTask.objects.filter(
        tenant=workflowautomation_schedule_a.tenant,
        project=workflowautomation_schedule_a.project,
        effort_hours=workflowautomation_schedule_a.effort_hours,
    ).latest("created_at")
    assert task.status == "planned"
    assert task.assignee == admin_user
    assert workflowautomation_schedule_a.number in task.description


def test_workflowautomation_view_rts_generate_task_get_not_allowed(
    client_a,
    workflowautomation_schedule_a,
):
    """GET rts_generate_task returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "rts_generate_task", workflowautomation_schedule_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_rts_generate_task_isolation(
    client_a,
    workflowautomation_schedule_b,
):
    """Tenant A generating task on Tenant B schedule returns 404."""
    res = _workflowautomation_post(client_a, "rts_generate_task", workflowautomation_schedule_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_rts_skip_next_post(
    client_a,
    workflowautomation_schedule_a,
):
    """POST rts_skip_next advances next_run_date without generating a task."""
    initial_task_count = ProjectTask.objects.filter(project=workflowautomation_schedule_a.project).count()
    old_run_date = workflowautomation_schedule_a.next_run_date

    res = _workflowautomation_post(client_a, "rts_skip_next", workflowautomation_schedule_a.pk)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("rts_detail", workflowautomation_schedule_a.pk)

    workflowautomation_schedule_a.refresh_from_db()
    assert workflowautomation_schedule_a.next_run_date > old_run_date
    new_task_count = ProjectTask.objects.filter(project=workflowautomation_schedule_a.project).count()
    assert new_task_count == initial_task_count


def test_workflowautomation_view_rts_skip_next_get_not_allowed(
    client_a,
    workflowautomation_schedule_a,
):
    """GET rts_skip_next returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "rts_skip_next", workflowautomation_schedule_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_rts_skip_next_isolation(
    client_a,
    workflowautomation_schedule_b,
):
    """Tenant A skipping run on Tenant B schedule returns 404."""
    res = _workflowautomation_post(client_a, "rts_skip_next", workflowautomation_schedule_b.pk)
    assert res.status_code == 404


# ==================================================================================================
# 5. Webhooks (Webhooks.py)
# ==================================================================================================

def test_workflowautomation_view_pwh_list_get_and_context(
    client_a,
    workflowautomation_webhook_a,
):
    """GET pwh_list returns 200 with all pinned context keys."""
    res = _workflowautomation_get(client_a, "pwh_list")
    assert res.status_code == 200
    for key in (
        "webhooks",
        "page_obj",
        "projects",
        "stats",
        "q",
        "is_active",
        "project_id",
    ):
        assert key in res.context
    assert res.context["stats"]["total"] >= 1


def test_workflowautomation_view_pwh_list_search_and_filters(
    client_a,
    tenant_a,
    workflowautomation_project_a,
):
    """Filter pwh_list by q, is_active, and project."""
    ep1 = _workflowautomation_webhook(
        tenant_a,
        project=workflowautomation_project_a,
        name="Target Webhook UniqueSearch",
        is_active=True,
    )
    ep2 = _workflowautomation_webhook(
        tenant_a,
        project=workflowautomation_project_a,
        name="Inactive Webhook",
        is_active=False,
    )

    # Search by q
    res_q = _workflowautomation_get(client_a, "pwh_list", q="UniqueSearch")
    assert res_q.status_code == 200
    names = [ep.name for ep in res_q.context["webhooks"]]
    assert "Target Webhook UniqueSearch" in names
    assert "Inactive Webhook" not in names

    # Filter by is_active=true
    res_act = _workflowautomation_get(client_a, "pwh_list", is_active="true")
    assert res_act.status_code == 200
    assert all(ep.is_active for ep in res_act.context["webhooks"])

    # Filter by is_active=false
    res_inact = _workflowautomation_get(client_a, "pwh_list", is_active="false")
    assert res_inact.status_code == 200
    assert all(not ep.is_active for ep in res_inact.context["webhooks"])

    # Filter by project
    res_proj = _workflowautomation_get(client_a, "pwh_list", project=str(workflowautomation_project_a.pk))
    assert res_proj.status_code == 200
    assert len(res_proj.context["webhooks"]) >= 2


def test_workflowautomation_view_pwh_list_negative_input_and_pagination(
    client_a,
    tenant_a,
    workflowautomation_project_a,
):
    """Junk GET params return 200 without 500 error, and page 2 pagination works."""
    res_junk = _workflowautomation_get(
        client_a, "pwh_list", project="xyz", is_active="junk", page="999", junk="123"
    )
    assert res_junk.status_code == 200

    # Create 26 webhooks to test pagination (per_page=25)
    for i in range(26):
        _workflowautomation_webhook(
            tenant_a,
            project=workflowautomation_project_a,
            name=f"Paging Webhook {i}",
        )
    res_p1 = _workflowautomation_get(client_a, "pwh_list", page="1")
    assert res_p1.status_code == 200
    assert len(res_p1.context["webhooks"]) == 25

    res_p2 = _workflowautomation_get(client_a, "pwh_list", page="2")
    assert res_p2.status_code == 200
    assert len(res_p2.context["webhooks"]) >= 1


def test_workflowautomation_view_pwh_list_isolation(
    client_a,
    workflowautomation_webhook_b,
):
    """Tenant A's webhook list never contains Tenant B's webhooks."""
    res = _workflowautomation_get(client_a, "pwh_list")
    assert res.status_code == 200
    ep_ids = [ep.pk for ep in res.context["webhooks"]]
    assert workflowautomation_webhook_b.pk not in ep_ids


def test_workflowautomation_view_pwh_create_get(
    client_a,
    workflowautomation_project_a,
):
    """GET pwh_create returns 200 with form, webhook=None, is_edit=False."""
    res = _workflowautomation_get(client_a, "pwh_create", project=str(workflowautomation_project_a.pk))
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["webhook"] is None
    assert res.context["is_edit"] is False


def test_workflowautomation_view_pwh_create_post_and_secret_revelation(
    client_a,
    tenant_a,
    workflowautomation_project_a,
):
    """POST valid data creates webhook endpoint, stores secret in session, and reveals it once on detail."""
    data = {
        "project": workflowautomation_project_a.pk,
        "name": "Jira Webhook Receiver",
        "target_url": "https://jira.example.com/webhooks/incoming",
        "is_active": "on",
        "event_types": json.dumps(["task.created", "gate.approved"]),
    }
    res = _workflowautomation_post(client_a, "pwh_create", data=data)
    assert res.status_code == 302
    created = ProjectWebhookEndpoint.objects.filter(tenant=tenant_a, name="Jira Webhook Receiver").first()
    assert created is not None
    assert res.url == _workflowautomation_url("pwh_detail", created.pk)

    # First visit to detail: secret revealed
    detail_res1 = client_a.get(res.url)
    assert detail_res1.status_code == 200
    assert detail_res1.context["revealed_secret"] is not None
    assert len(detail_res1.context["revealed_secret"]) > 0

    # Second visit to detail: one-time revelation popped (None)
    detail_res2 = client_a.get(res.url)
    assert detail_res2.status_code == 200
    assert detail_res2.context["revealed_secret"] is None


def test_workflowautomation_view_pwh_create_post_invalid(client_a):
    """POST invalid data returns 200 and re-renders form."""
    res = _workflowautomation_post(client_a, "pwh_create", data={"name": ""})
    assert res.status_code == 200
    assert "form" in res.context
    assert res.context["form"].errors


def test_workflowautomation_view_pwh_detail_get(
    client_a,
    workflowautomation_webhook_a,
):
    """GET pwh_detail returns 200 with webhook, deliveries, test_form, revealed_secret."""
    res = _workflowautomation_get(client_a, "pwh_detail", workflowautomation_webhook_a.pk)
    assert res.status_code == 200
    assert res.context["webhook"] == workflowautomation_webhook_a
    assert "deliveries" in res.context
    assert "test_form" in res.context
    assert res.context["revealed_secret"] is None


def test_workflowautomation_view_pwh_detail_isolation(
    client_a,
    workflowautomation_webhook_b,
):
    """Tenant A accessing Tenant B webhook returns 404."""
    res = _workflowautomation_get(client_a, "pwh_detail", workflowautomation_webhook_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_pwh_edit_get(
    client_a,
    workflowautomation_webhook_a,
):
    """GET pwh_edit returns 200 with is_edit=True."""
    res = _workflowautomation_get(client_a, "pwh_edit", workflowautomation_webhook_a.pk)
    assert res.status_code == 200
    assert res.context["webhook"] == workflowautomation_webhook_a
    assert res.context["is_edit"] is True


def test_workflowautomation_view_pwh_edit_post_valid(
    client_a,
    workflowautomation_webhook_a,
    workflowautomation_project_a,
):
    """POST valid update to webhook redirects to pwh_detail."""
    data = {
        "project": workflowautomation_project_a.pk,
        "name": "Updated Webhook Name",
        "target_url": "https://hooks.slack.com/services/updated",
        "is_active": "on",
        "event_types": json.dumps(["task.completed"]),
    }
    res = _workflowautomation_post(client_a, "pwh_edit", workflowautomation_webhook_a.pk, data=data)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("pwh_detail", workflowautomation_webhook_a.pk)
    workflowautomation_webhook_a.refresh_from_db()
    assert workflowautomation_webhook_a.name == "Updated Webhook Name"


def test_workflowautomation_view_pwh_edit_isolation(
    client_a,
    workflowautomation_webhook_b,
):
    """Tenant A editing Tenant B webhook returns 404."""
    res = _workflowautomation_get(client_a, "pwh_edit", workflowautomation_webhook_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_pwh_delete_post(
    client_a,
    tenant_a,
    workflowautomation_project_a,
):
    """POST pwh_delete deletes webhook and redirects to pwh_list."""
    wh = _workflowautomation_webhook(tenant_a, project=workflowautomation_project_a, name="To Delete")
    res = _workflowautomation_post(client_a, "pwh_delete", wh.pk)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("pwh_list")
    assert not ProjectWebhookEndpoint.objects.filter(pk=wh.pk).exists()


def test_workflowautomation_view_pwh_delete_get_not_allowed(
    client_a,
    workflowautomation_webhook_a,
):
    """GET pwh_delete returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "pwh_delete", workflowautomation_webhook_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_pwh_delete_isolation(
    client_a,
    workflowautomation_webhook_b,
):
    """Tenant A deleting Tenant B webhook returns 404."""
    res = _workflowautomation_post(client_a, "pwh_delete", workflowautomation_webhook_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_pwh_toggle_active_post(
    client_a,
    workflowautomation_webhook_a,
):
    """POST pwh_toggle_active flips is_active state and redirects to pwh_detail."""
    initial = workflowautomation_webhook_a.is_active
    res = _workflowautomation_post(client_a, "pwh_toggle_active", workflowautomation_webhook_a.pk)
    assert res.status_code == 302
    workflowautomation_webhook_a.refresh_from_db()
    assert workflowautomation_webhook_a.is_active != initial


def test_workflowautomation_view_pwh_toggle_active_get_not_allowed(
    client_a,
    workflowautomation_webhook_a,
):
    """GET pwh_toggle_active returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "pwh_toggle_active", workflowautomation_webhook_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_pwh_toggle_active_isolation(
    client_a,
    workflowautomation_webhook_b,
):
    """Tenant A toggling Tenant B webhook returns 404."""
    res = _workflowautomation_post(client_a, "pwh_toggle_active", workflowautomation_webhook_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_pwh_test_ping_post(
    client_a,
    workflowautomation_webhook_a,
):
    """POST pwh_test_ping dispatches simulated delivery and updates last_status_code."""
    res = _workflowautomation_post(
        client_a,
        "pwh_test_ping",
        workflowautomation_webhook_a.pk,
        data={"event_type": "test.ping", "custom_payload": '{"ping": "pong"}'},
    )
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("pwh_detail", workflowautomation_webhook_a.pk)

    workflowautomation_webhook_a.refresh_from_db()
    assert workflowautomation_webhook_a.last_status_code == 200
    assert workflowautomation_webhook_a.last_fired_at is not None

    delivery = ProjectWebhookDelivery.objects.filter(
        webhook=workflowautomation_webhook_a, event="test.ping"
    ).first()
    assert delivery is not None
    assert delivery.status == "simulated"
    assert delivery.status_code == 200


def test_workflowautomation_view_pwh_test_ping_get_not_allowed(
    client_a,
    workflowautomation_webhook_a,
):
    """GET pwh_test_ping returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "pwh_test_ping", workflowautomation_webhook_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_pwh_test_ping_isolation(
    client_a,
    workflowautomation_webhook_b,
):
    """Tenant A sending test ping to Tenant B webhook returns 404."""
    res = _workflowautomation_post(client_a, "pwh_test_ping", workflowautomation_webhook_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_pwh_rotate_secret_post_and_revelation(
    client_a,
    workflowautomation_webhook_a,
):
    """POST pwh_rotate_secret changes secret and reveals new secret once in detail."""
    old_secret = workflowautomation_webhook_a.secret
    res = _workflowautomation_post(client_a, "pwh_rotate_secret", workflowautomation_webhook_a.pk)
    assert res.status_code == 302
    assert res.url == _workflowautomation_url("pwh_detail", workflowautomation_webhook_a.pk)

    workflowautomation_webhook_a.refresh_from_db()
    assert workflowautomation_webhook_a.secret != old_secret

    # First visit: secret revealed
    detail_res1 = client_a.get(res.url)
    assert detail_res1.status_code == 200
    assert detail_res1.context["revealed_secret"] is not None

    # Second visit: one-time revelation consumed
    detail_res2 = client_a.get(res.url)
    assert detail_res2.status_code == 200
    assert detail_res2.context["revealed_secret"] is None


def test_workflowautomation_view_pwh_rotate_secret_get_not_allowed(
    client_a,
    workflowautomation_webhook_a,
):
    """GET pwh_rotate_secret returns 405 (@require_POST)."""
    res = _workflowautomation_get(client_a, "pwh_rotate_secret", workflowautomation_webhook_a.pk)
    assert res.status_code == 405


def test_workflowautomation_view_pwh_rotate_secret_isolation(
    client_a,
    workflowautomation_webhook_b,
):
    """Tenant A rotating Tenant B webhook returns 404."""
    res = _workflowautomation_post(client_a, "pwh_rotate_secret", workflowautomation_webhook_b.pk)
    assert res.status_code == 404


def test_workflowautomation_view_pwh_delivery_list_get_and_context(
    client_a,
    workflowautomation_delivery_a,
):
    """GET pwh_delivery_list returns 200 with deliveries, page_obj, status_choices, webhook_id."""
    res = _workflowautomation_get(client_a, "pwh_delivery_list")
    assert res.status_code == 200
    for key in ("deliveries", "page_obj", "status_choices", "webhook_id"):
        assert key in res.context
    assert len(res.context["deliveries"]) >= 1


def test_workflowautomation_view_pwh_delivery_list_filters_and_negative_input(
    client_a,
    tenant_a,
    workflowautomation_webhook_a,
):
    """Filter pwh_delivery_list by webhook and status, and harden against junk params."""
    d1 = _workflowautomation_delivery(
        tenant_a, workflowautomation_webhook_a, status="success"
    )
    d2 = _workflowautomation_delivery(
        tenant_a, workflowautomation_webhook_a, status="failed", status_code=500
    )

    # Filter by webhook
    res_wh = _workflowautomation_get(client_a, "pwh_delivery_list", webhook=str(workflowautomation_webhook_a.pk))
    assert res_wh.status_code == 200
    assert len(res_wh.context["deliveries"]) >= 2

    # Filter by status
    res_stat = _workflowautomation_get(client_a, "pwh_delivery_list", status="failed")
    assert res_stat.status_code == 200
    assert all(d.status == "failed" for d in res_stat.context["deliveries"])

    # Negative input hardening
    res_junk = _workflowautomation_get(
        client_a, "pwh_delivery_list", webhook="not_an_int", status="junk", page="999", junk="123"
    )
    assert res_junk.status_code == 200

    # Create 31 deliveries to test pagination (per_page=30)
    for _ in range(31):
        _workflowautomation_delivery(tenant_a, workflowautomation_webhook_a)
    res_p1 = _workflowautomation_get(client_a, "pwh_delivery_list", page="1")
    assert res_p1.status_code == 200
    assert len(res_p1.context["deliveries"]) == 30

    res_p2 = _workflowautomation_get(client_a, "pwh_delivery_list", page="2")
    assert res_p2.status_code == 200
    assert len(res_p2.context["deliveries"]) >= 1


def test_workflowautomation_view_pwh_delivery_list_isolation(
    client_a,
    tenant_b,
    workflowautomation_webhook_b,
):
    """Tenant A's delivery list never contains Tenant B's deliveries."""
    deliv_b = _workflowautomation_delivery(tenant_b, workflowautomation_webhook_b)
    res = _workflowautomation_get(client_a, "pwh_delivery_list")
    assert res.status_code == 200
    deliv_ids = [d.pk for d in res.context["deliveries"]]
    assert deliv_b.pk not in deliv_ids


def test_workflowautomation_view_pwh_delivery_detail_get(
    client_a,
    workflowautomation_delivery_a,
):
    """GET pwh_delivery_detail returns 200 with delivery object in context."""
    res = _workflowautomation_get(client_a, "pwh_delivery_detail", workflowautomation_delivery_a.pk)
    assert res.status_code == 200
    assert res.context["delivery"] == workflowautomation_delivery_a


def test_workflowautomation_view_pwh_delivery_detail_isolation(
    client_a,
    tenant_b,
    workflowautomation_webhook_b,
):
    """Tenant A accessing Tenant B's webhook delivery detail returns 404."""
    deliv_b = _workflowautomation_delivery(tenant_b, workflowautomation_webhook_b)
    res = _workflowautomation_get(client_a, "pwh_delivery_detail", deliv_b.pk)
    assert res.status_code == 404
