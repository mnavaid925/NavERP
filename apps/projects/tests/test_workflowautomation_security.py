"""Projects 7.17 Workflow & Automation — SECURITY and TENANT ISOLATION tests.

Covers:
1. Multi-Tenant Isolation (IDOR) — Mandatory:
   - Detail GET by Tenant A on Tenant B's PK -> 404.
   - Edit GET/POST by Tenant A on Tenant B's PK -> 404.
   - Delete POST by Tenant A on Tenant B's PK -> 404.
   - Action POSTs (pwf_toggle_active, pwf_test_run, pwf_execute_now, par_approve,
     par_reject, par_escalate, par_delegate, par_cancel, rts_toggle_active,
     rts_generate_task, rts_skip_next, pwh_toggle_active, pwh_test_ping,
     pwh_rotate_secret) by Tenant A on Tenant B's PK -> 404.
   - List views and boards (pwf_list, par_list, rts_list, pwh_list, pwh_delivery_list,
     automation_overview, approval_inbox, recurrence_calendar, webhook_diagnostics):
     Tenant A never sees Tenant B's rows.
   - Cross-tenant delegation: par_delegate rejects delegating to a user from Tenant B.
   - Foreign FK rejection: submitting Tenant B's project PK in create/edit form is rejected.
2. Authentication & Authorization:
   - Unauthenticated requests to all endpoints redirect to login (302).
   - Approval gate governance:
     - Non-approver / non-admin user cannot approve or reject a gate (error message, no status change).
     - Requester self-approval is blocked unless tenant admin.
     - Terminal gates cannot be deleted (par_delete) or edited (par_edit).
3. CSRF & HTTP Methods:
   - All mutative endpoints enforce @require_POST (GET -> 405).
   - All POST endpoints enforce CSRF checks (Client(enforce_csrf_checks=True) -> 403).
4. Secret Handling:
   - Webhook HMAC secret is never stored in plaintext on the model or flashed via messages.
   - Secret is revealed strictly once via session pop-once in pwh_detail.
5. Negative-Input Hardening:
   - Junk GET query parameters return 200, never 500.
"""
import json
import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.projects.models import (
    ProjectApprovalGate,
    ProjectWebhookDelivery,
    ProjectWebhookEndpoint,
    ProjectWorkflowRule,
    RecurringTaskSchedule,
)
from apps.projects.tests.conftest import (
    _workflowautomation_delivery,
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
    """Resolve a projects URL with the projects namespace."""
    return reverse(f"projects:{name}", args=args)


def _workflowautomation_messages(response):
    """Extract message strings from response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


# ==================================================================================================
# 1. Multi-Tenant Isolation (IDOR) — Mandatory
# ==================================================================================================

def test_workflowautomation_security_idor_detail_get_404(
    client_a,
    tenant_b,
    workflowautomation_rule_b,
    workflowautomation_gate_b,
    workflowautomation_schedule_b,
    workflowautomation_webhook_b,
):
    """Tenant A attempting GET detail on Tenant B objects returns 404."""
    delivery_b = _workflowautomation_delivery(tenant_b, workflowautomation_webhook_b)

    detail_routes = [
        _workflowautomation_url("pwf_detail", workflowautomation_rule_b.pk),
        _workflowautomation_url("par_detail", workflowautomation_gate_b.pk),
        _workflowautomation_url("rts_detail", workflowautomation_schedule_b.pk),
        _workflowautomation_url("pwh_detail", workflowautomation_webhook_b.pk),
        _workflowautomation_url("pwh_delivery_detail", delivery_b.pk),
    ]

    for url in detail_routes:
        res = client_a.get(url)
        assert res.status_code == 404, f"IDOR detail GET {url} should return 404, got {res.status_code}"


def test_workflowautomation_security_idor_edit_get_and_post_404(
    client_a,
    workflowautomation_rule_b,
    workflowautomation_gate_b,
    workflowautomation_schedule_b,
    workflowautomation_webhook_b,
):
    """Tenant A attempting GET or POST edit on Tenant B objects returns 404."""
    edit_routes = [
        _workflowautomation_url("pwf_edit", workflowautomation_rule_b.pk),
        _workflowautomation_url("par_edit", workflowautomation_gate_b.pk),
        _workflowautomation_url("rts_edit", workflowautomation_schedule_b.pk),
        _workflowautomation_url("pwh_edit", workflowautomation_webhook_b.pk),
    ]

    for url in edit_routes:
        res_get = client_a.get(url)
        assert res_get.status_code == 404, f"IDOR edit GET {url} should return 404, got {res_get.status_code}"

        res_post = client_a.post(url, {"name": "Hacked Name", "title": "Hacked Title"})
        assert res_post.status_code == 404, f"IDOR edit POST {url} should return 404, got {res_post.status_code}"


def test_workflowautomation_security_idor_delete_post_404(
    client_a,
    workflowautomation_rule_b,
    workflowautomation_gate_b,
    workflowautomation_schedule_b,
    workflowautomation_webhook_b,
):
    """Tenant A attempting POST delete on Tenant B objects returns 404."""
    delete_routes = [
        _workflowautomation_url("pwf_delete", workflowautomation_rule_b.pk),
        _workflowautomation_url("par_delete", workflowautomation_gate_b.pk),
        _workflowautomation_url("rts_delete", workflowautomation_schedule_b.pk),
        _workflowautomation_url("pwh_delete", workflowautomation_webhook_b.pk),
    ]

    for url in delete_routes:
        res = client_a.post(url, {})
        assert res.status_code == 404, f"IDOR delete POST {url} should return 404, got {res.status_code}"

    # Verify objects still exist
    assert ProjectWorkflowRule.objects.filter(pk=workflowautomation_rule_b.pk).exists()
    assert ProjectApprovalGate.objects.filter(pk=workflowautomation_gate_b.pk).exists()
    assert RecurringTaskSchedule.objects.filter(pk=workflowautomation_schedule_b.pk).exists()
    assert ProjectWebhookEndpoint.objects.filter(pk=workflowautomation_webhook_b.pk).exists()


def test_workflowautomation_security_idor_action_posts_404(
    client_a,
    workflowautomation_rule_b,
    workflowautomation_gate_b,
    workflowautomation_schedule_b,
    workflowautomation_webhook_b,
):
    """Tenant A attempting mutative action POSTs on Tenant B objects returns 404."""
    action_routes = [
        # Workflow rules
        _workflowautomation_url("pwf_toggle_active", workflowautomation_rule_b.pk),
        _workflowautomation_url("pwf_test_run", workflowautomation_rule_b.pk),
        _workflowautomation_url("pwf_execute_now", workflowautomation_rule_b.pk),
        # Approval gates
        _workflowautomation_url("par_approve", workflowautomation_gate_b.pk),
        _workflowautomation_url("par_reject", workflowautomation_gate_b.pk),
        _workflowautomation_url("par_escalate", workflowautomation_gate_b.pk),
        _workflowautomation_url("par_delegate", workflowautomation_gate_b.pk),
        _workflowautomation_url("par_cancel", workflowautomation_gate_b.pk),
        # Recurring tasks
        _workflowautomation_url("rts_toggle_active", workflowautomation_schedule_b.pk),
        _workflowautomation_url("rts_generate_task", workflowautomation_schedule_b.pk),
        _workflowautomation_url("rts_skip_next", workflowautomation_schedule_b.pk),
        # Webhooks
        _workflowautomation_url("pwh_toggle_active", workflowautomation_webhook_b.pk),
        _workflowautomation_url("pwh_test_ping", workflowautomation_webhook_b.pk),
        _workflowautomation_url("pwh_rotate_secret", workflowautomation_webhook_b.pk),
    ]

    for url in action_routes:
        res = client_a.post(url, {})
        assert res.status_code == 404, f"IDOR action POST {url} should return 404, got {res.status_code}"


def test_workflowautomation_security_list_and_board_views_isolation(
    client_a,
    tenant_b,
    workflowautomation_rule_a,
    workflowautomation_rule_b,
    workflowautomation_gate_a,
    workflowautomation_gate_b,
    workflowautomation_schedule_a,
    workflowautomation_schedule_b,
    workflowautomation_webhook_a,
    workflowautomation_webhook_b,
    workflowautomation_delivery_a,
):
    """Tenant A list views and operational boards never show Tenant B rows."""
    delivery_b = _workflowautomation_delivery(tenant_b, workflowautomation_webhook_b)

    # 1. pwf_list
    res_pwf = client_a.get(_workflowautomation_url("pwf_list"))
    assert res_pwf.status_code == 200
    pwf_ids = [r.pk for r in res_pwf.context["rules"]]
    assert workflowautomation_rule_a.pk in pwf_ids
    assert workflowautomation_rule_b.pk not in pwf_ids
    assert workflowautomation_rule_b.name.encode() not in res_pwf.content

    # 2. par_list
    res_par = client_a.get(_workflowautomation_url("par_list"))
    assert res_par.status_code == 200
    par_ids = [g.pk for g in res_par.context["gates"]]
    assert workflowautomation_gate_a.pk in par_ids
    assert workflowautomation_gate_b.pk not in par_ids
    assert workflowautomation_gate_b.title.encode() not in res_par.content

    # 3. rts_list
    res_rts = client_a.get(_workflowautomation_url("rts_list"))
    assert res_rts.status_code == 200
    rts_ids = [s.pk for s in res_rts.context["schedules"]]
    assert workflowautomation_schedule_a.pk in rts_ids
    assert workflowautomation_schedule_b.pk not in rts_ids
    assert workflowautomation_schedule_b.title_template.encode() not in res_rts.content

    # 4. pwh_list
    res_pwh = client_a.get(_workflowautomation_url("pwh_list"))
    assert res_pwh.status_code == 200
    pwh_ids = [w.pk for w in res_pwh.context["webhooks"]]
    assert workflowautomation_webhook_a.pk in pwh_ids
    assert workflowautomation_webhook_b.pk not in pwh_ids
    assert workflowautomation_webhook_b.name.encode() not in res_pwh.content

    # 5. pwh_delivery_list
    res_del = client_a.get(_workflowautomation_url("pwh_delivery_list"))
    assert res_del.status_code == 200
    del_ids = [d.pk for d in res_del.context["deliveries"]]
    assert workflowautomation_delivery_a.pk in del_ids
    assert delivery_b.pk not in del_ids

    # 6. automation_overview
    res_ov = client_a.get(_workflowautomation_url("automation_overview"))
    assert res_ov.status_code == 200
    pending_gate_ids = [g.pk for g in res_ov.context["pending_gates"]]
    assert workflowautomation_gate_b.pk not in pending_gate_ids
    upcoming_ids = [s.pk for s in res_ov.context["upcoming_recurring"]]
    assert workflowautomation_schedule_b.pk not in upcoming_ids
    assert workflowautomation_rule_b.name.encode() not in res_ov.content
    assert workflowautomation_gate_b.title.encode() not in res_ov.content

    # 7. approval_inbox
    res_ib = client_a.get(_workflowautomation_url("approval_inbox"))
    assert res_ib.status_code == 200
    inbox_ids = [g.pk for g in res_ib.context["gates"]]
    assert workflowautomation_gate_b.pk not in inbox_ids
    assert workflowautomation_gate_b.title.encode() not in res_ib.content

    # 8. recurrence_calendar
    res_cal = client_a.get(_workflowautomation_url("recurrence_calendar"))
    assert res_cal.status_code == 200
    cal_ids = [s.pk for s in res_cal.context["upcoming_schedules"]]
    assert workflowautomation_schedule_b.pk not in cal_ids
    assert workflowautomation_schedule_b.title_template.encode() not in res_cal.content

    # 9. webhook_diagnostics
    res_diag = client_a.get(_workflowautomation_url("webhook_diagnostics"))
    assert res_diag.status_code == 200
    diag_ep_ids = [ep.pk for ep in res_diag.context["endpoints"]]
    assert workflowautomation_webhook_a.pk in diag_ep_ids
    assert workflowautomation_webhook_b.pk not in diag_ep_ids
    assert workflowautomation_webhook_b.name.encode() not in res_diag.content


def test_workflowautomation_security_cross_tenant_delegation_rejected(
    client_a,
    admin_b,
    workflowautomation_gate_a,
):
    """par_delegate rejects delegating to a user from Tenant B."""
    url = _workflowautomation_url("par_delegate", workflowautomation_gate_a.pk)
    res = client_a.post(url, {"delegate_approver": str(admin_b.pk), "notes": "Delegating across tenants"})
    assert res.status_code == 302

    workflowautomation_gate_a.refresh_from_db()
    assert workflowautomation_gate_a.delegate_approver is None
    assert workflowautomation_gate_a.delegate_approver != admin_b

    msgs = _workflowautomation_messages(res)
    assert any("valid user" in m.lower() or "tenant" in m.lower() for m in msgs)


def test_workflowautomation_security_foreign_fk_rejection(
    client_a,
    workflowautomation_project_a,
    workflowautomation_project_b,
    workflowautomation_rule_a,
    workflowautomation_rule_b,
    workflowautomation_gate_a,
    workflowautomation_schedule_a,
    workflowautomation_webhook_a,
):
    """Submitting Tenant B's project PK in create/edit forms is rejected by _reject_foreign."""
    today = _workflowautomation_today()

    # 1. ProjectWorkflowRuleForm: create with foreign project
    res_pwf_create = client_a.post(
        _workflowautomation_url("pwf_create"),
        {
            "name": "Cross-Tenant Rule Attempt",
            "project": str(workflowautomation_project_b.pk),
            "trigger_entity": "task",
            "trigger_event": "status_changed",
            "conditions": "[]",
            "actions": "[]",
        },
    )
    assert res_pwf_create.status_code == 200
    assert "project" in res_pwf_create.context["form"].errors
    assert not ProjectWorkflowRule.objects.filter(name="Cross-Tenant Rule Attempt").exists()

    # 2. ProjectWorkflowRuleForm: edit with foreign project
    res_pwf_edit = client_a.post(
        _workflowautomation_url("pwf_edit", workflowautomation_rule_a.pk),
        {
            "name": workflowautomation_rule_a.name,
            "project": str(workflowautomation_project_b.pk),
            "trigger_entity": workflowautomation_rule_a.trigger_entity,
            "trigger_event": workflowautomation_rule_a.trigger_event,
            "conditions": "[]",
            "actions": "[]",
        },
    )
    assert res_pwf_edit.status_code == 200
    assert "project" in res_pwf_edit.context["form"].errors
    workflowautomation_rule_a.refresh_from_db()
    assert workflowautomation_rule_a.project_id != workflowautomation_project_b.pk

    # 3. ProjectApprovalGateForm: create with foreign project
    res_par_create = client_a.post(
        _workflowautomation_url("par_create"),
        {
            "title": "Cross-Tenant Gate Attempt",
            "gate_type": "phase_gate",
            "project": str(workflowautomation_project_b.pk),
            "target_model": "milestone",
            "target_id": "1",
            "target_label": "Target Milestone",
        },
    )
    assert res_par_create.status_code == 200
    assert "project" in res_par_create.context["form"].errors
    assert not ProjectApprovalGate.objects.filter(title="Cross-Tenant Gate Attempt").exists()

    # 4. ProjectApprovalGateForm: create with foreign rule
    res_par_create_rule = client_a.post(
        _workflowautomation_url("par_create"),
        {
            "title": "Cross-Tenant Rule Gate Attempt",
            "gate_type": "phase_gate",
            "project": str(workflowautomation_project_a.pk),
            "rule": str(workflowautomation_rule_b.pk),
            "target_model": "milestone",
            "target_id": "1",
            "target_label": "Target Milestone",
        },
    )
    assert res_par_create_rule.status_code == 200
    assert "rule" in res_par_create_rule.context["form"].errors
    assert not ProjectApprovalGate.objects.filter(title="Cross-Tenant Rule Gate Attempt").exists()

    # 5. ProjectApprovalGateForm: edit with foreign project
    res_par_edit = client_a.post(
        _workflowautomation_url("par_edit", workflowautomation_gate_a.pk),
        {
            "title": workflowautomation_gate_a.title,
            "gate_type": workflowautomation_gate_a.gate_type,
            "project": str(workflowautomation_project_b.pk),
            "target_model": workflowautomation_gate_a.target_model,
            "target_id": workflowautomation_gate_a.target_id,
            "target_label": workflowautomation_gate_a.target_label,
        },
    )
    assert res_par_edit.status_code == 200
    assert "project" in res_par_edit.context["form"].errors
    workflowautomation_gate_a.refresh_from_db()
    assert workflowautomation_gate_a.project_id != workflowautomation_project_b.pk

    # 6. RecurringTaskScheduleForm: create with foreign project
    res_rts_create = client_a.post(
        _workflowautomation_url("rts_create"),
        {
            "title_template": "Cross-Tenant Schedule Attempt",
            "frequency": "weekly",
            "project": str(workflowautomation_project_b.pk),
            "start_date": str(today),
            "priority": "medium",
            "assignee_strategy": "project_lead",
        },
    )
    assert res_rts_create.status_code == 200
    assert "project" in res_rts_create.context["form"].errors
    assert not RecurringTaskSchedule.objects.filter(title_template="Cross-Tenant Schedule Attempt").exists()

    # 7. RecurringTaskScheduleForm: edit with foreign project
    res_rts_edit = client_a.post(
        _workflowautomation_url("rts_edit", workflowautomation_schedule_a.pk),
        {
            "title_template": workflowautomation_schedule_a.title_template,
            "frequency": workflowautomation_schedule_a.frequency,
            "project": str(workflowautomation_project_b.pk),
            "start_date": str(workflowautomation_schedule_a.start_date),
            "priority": workflowautomation_schedule_a.priority,
            "assignee_strategy": workflowautomation_schedule_a.assignee_strategy,
        },
    )
    assert res_rts_edit.status_code == 200
    assert "project" in res_rts_edit.context["form"].errors
    workflowautomation_schedule_a.refresh_from_db()
    assert workflowautomation_schedule_a.project_id != workflowautomation_project_b.pk

    # 8. ProjectWebhookEndpointForm: create with foreign project
    res_pwh_create = client_a.post(
        _workflowautomation_url("pwh_create"),
        {
            "name": "Cross-Tenant Webhook Attempt",
            "target_url": "https://example.com/cross-tenant",
            "project": str(workflowautomation_project_b.pk),
            "event_types": '["task.created"]',
        },
    )
    assert res_pwh_create.status_code == 200
    assert "project" in res_pwh_create.context["form"].errors
    assert not ProjectWebhookEndpoint.objects.filter(name="Cross-Tenant Webhook Attempt").exists()

    # 9. ProjectWebhookEndpointForm: edit with foreign project
    res_pwh_edit = client_a.post(
        _workflowautomation_url("pwh_edit", workflowautomation_webhook_a.pk),
        {
            "name": workflowautomation_webhook_a.name,
            "target_url": workflowautomation_webhook_a.target_url,
            "project": str(workflowautomation_project_b.pk),
            "event_types": '["task.created"]',
        },
    )
    assert res_pwh_edit.status_code == 200
    assert "project" in res_pwh_edit.context["form"].errors
    workflowautomation_webhook_a.refresh_from_db()
    assert workflowautomation_webhook_a.project_id != workflowautomation_project_b.pk


# ==================================================================================================
# 2. Authentication & Authorization
# ==================================================================================================

def test_workflowautomation_security_unauthenticated_redirects_to_login(
    projectinitiation_anon_client,
    workflowautomation_rule_a,
    workflowautomation_gate_a,
    workflowautomation_schedule_a,
    workflowautomation_webhook_a,
    workflowautomation_delivery_a,
):
    """Unauthenticated requests to all 40 endpoints redirect to login (302)."""
    endpoints = [
        # Boards (4)
        _workflowautomation_url("automation_overview"),
        _workflowautomation_url("approval_inbox"),
        _workflowautomation_url("recurrence_calendar"),
        _workflowautomation_url("webhook_diagnostics"),
        # Workflow Rules (8)
        _workflowautomation_url("pwf_list"),
        _workflowautomation_url("pwf_create"),
        _workflowautomation_url("pwf_detail", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_edit", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_delete", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_toggle_active", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_test_run", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_execute_now", workflowautomation_rule_a.pk),
        # Approval Gates (10)
        _workflowautomation_url("par_list"),
        _workflowautomation_url("par_create"),
        _workflowautomation_url("par_detail", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_edit", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_delete", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_approve", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_reject", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_escalate", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_delegate", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_cancel", workflowautomation_gate_a.pk),
        # Recurring Tasks (8)
        _workflowautomation_url("rts_list"),
        _workflowautomation_url("rts_create"),
        _workflowautomation_url("rts_detail", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_edit", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_delete", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_toggle_active", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_generate_task", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_skip_next", workflowautomation_schedule_a.pk),
        # Webhooks & Deliveries (10)
        _workflowautomation_url("pwh_list"),
        _workflowautomation_url("pwh_create"),
        _workflowautomation_url("pwh_detail", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_edit", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_delete", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_toggle_active", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_test_ping", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_rotate_secret", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_delivery_list"),
        _workflowautomation_url("pwh_delivery_detail", workflowautomation_delivery_a.pk),
    ]

    for url in endpoints:
        res = projectinitiation_anon_client.get(url)
        assert res.status_code == 302, f"Expected 302 for unauthenticated on {url}, got {res.status_code}"
        assert "/login/" in res.url, f"Expected '/login/' in redirect url for {url}, got {res.url}"


def test_workflowautomation_security_approval_gate_non_approver_blocked(
    member_client,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """Non-approver / non-admin user cannot approve, reject, escalate, or delegate a gate."""
    # Gate where approver is admin_user, not member_user
    gate = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
        delegate_approver=None,
        status="pending",
    )

    # 1. par_approve blocked
    res_appr = member_client.post(_workflowautomation_url("par_approve", gate.pk), {})
    assert res_appr.status_code == 302
    gate.refresh_from_db()
    assert gate.status == "pending"
    msgs = _workflowautomation_messages(res_appr)
    assert any("not authorized to approve" in m.lower() for m in msgs)

    # 2. par_reject blocked
    res_rej = member_client.post(_workflowautomation_url("par_reject", gate.pk), {})
    assert res_rej.status_code == 302
    gate.refresh_from_db()
    assert gate.status == "pending"
    msgs = _workflowautomation_messages(res_rej)
    assert any("not authorized to reject" in m.lower() for m in msgs)

    # 3. par_escalate blocked
    res_esc = member_client.post(_workflowautomation_url("par_escalate", gate.pk), {})
    assert res_esc.status_code == 302
    gate.refresh_from_db()
    assert gate.status == "pending"
    msgs = _workflowautomation_messages(res_esc)
    assert any("not authorized to escalate" in m.lower() for m in msgs)

    # 4. par_delegate blocked
    res_del = member_client.post(
        _workflowautomation_url("par_delegate", gate.pk),
        {"delegate_approver": str(admin_user.pk)},
    )
    assert res_del.status_code == 302
    gate.refresh_from_db()
    assert gate.delegate_approver is None
    msgs = _workflowautomation_messages(res_del)
    assert any("not authorized to delegate" in m.lower() for m in msgs)


def test_workflowautomation_security_approval_gate_requester_self_approval_blocked(
    member_client,
    client_a,
    tenant_a,
    admin_user,
    member_user,
    workflowautomation_project_a,
):
    """Requester self-approval is blocked unless tenant admin."""
    # 1. Regular member attempts self-approval -> blocked
    gate_member = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=member_user,
        approver=member_user,
        status="pending",
    )
    res_mem = member_client.post(_workflowautomation_url("par_approve", gate_member.pk), {})
    assert res_mem.status_code == 302
    gate_member.refresh_from_db()
    assert gate_member.status == "pending"
    msgs = _workflowautomation_messages(res_mem)
    assert any("requesters cannot approve their own" in m.lower() for m in msgs)

    # 2. Tenant admin CAN self-approve
    gate_admin = _workflowautomation_gate(
        tenant_a,
        workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
        status="pending",
    )
    res_adm = client_a.post(_workflowautomation_url("par_approve", gate_admin.pk), {})
    assert res_adm.status_code == 302
    gate_admin.refresh_from_db()
    assert gate_admin.status == "approved"
    msgs_adm = _workflowautomation_messages(res_adm)
    assert any("has been approved" in m.lower() for m in msgs_adm)


def test_workflowautomation_security_terminal_gates_cannot_be_deleted_or_edited(
    client_a,
    tenant_a,
    admin_user,
    workflowautomation_project_a,
):
    """Terminal gates (approved/rejected/auto_approved) cannot be deleted (par_delete) or edited (par_edit)."""
    terminal_statuses = ["approved", "rejected", "auto_approved"]

    for stat in terminal_statuses:
        gate = _workflowautomation_gate(
            tenant_a,
            workflowautomation_project_a,
            requested_by=admin_user,
            approver=admin_user,
            status=stat,
            title=f"Terminal Gate {stat.capitalize()}",
        )

        # Attempt delete -> 302 redirect with error, gate NOT deleted
        res_del = client_a.post(_workflowautomation_url("par_delete", gate.pk), {})
        assert res_del.status_code == 302
        assert ProjectApprovalGate.objects.filter(pk=gate.pk).exists()
        msgs_del = _workflowautomation_messages(res_del)
        assert any("cannot delete gate" in m.lower() for m in msgs_del)

        # Attempt edit GET -> 302 redirect with warning
        res_edit_get = client_a.get(_workflowautomation_url("par_edit", gate.pk))
        assert res_edit_get.status_code == 302
        msgs_edit_get = _workflowautomation_messages(res_edit_get)
        assert any("cannot edit gate" in m.lower() and "terminal status" in m.lower() for m in msgs_edit_get)

        # Attempt edit POST -> 302 redirect, title unchanged
        res_edit_post = client_a.post(
            _workflowautomation_url("par_edit", gate.pk),
            {"title": "Modified Title Terminal Attempt"},
        )
        assert res_edit_post.status_code == 302
        gate.refresh_from_db()
        assert gate.title == f"Terminal Gate {stat.capitalize()}"


# ==================================================================================================
# 3. CSRF & HTTP Methods
# ==================================================================================================

def test_workflowautomation_security_mutative_endpoints_require_post_405(
    client_a,
    workflowautomation_rule_a,
    workflowautomation_gate_a,
    workflowautomation_schedule_a,
    workflowautomation_webhook_a,
):
    """All 18 mutative action and delete endpoints reject GET with 405 Method Not Allowed."""
    mutative_routes = [
        # Workflow rules
        _workflowautomation_url("pwf_delete", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_toggle_active", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_test_run", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_execute_now", workflowautomation_rule_a.pk),
        # Approval gates
        _workflowautomation_url("par_delete", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_approve", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_reject", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_escalate", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_delegate", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_cancel", workflowautomation_gate_a.pk),
        # Recurring tasks
        _workflowautomation_url("rts_delete", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_toggle_active", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_generate_task", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_skip_next", workflowautomation_schedule_a.pk),
        # Webhooks
        _workflowautomation_url("pwh_delete", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_toggle_active", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_test_ping", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_rotate_secret", workflowautomation_webhook_a.pk),
    ]

    for url in mutative_routes:
        res = client_a.get(url)
        assert res.status_code == 405, f"Expected 405 on GET {url}, got {res.status_code}"


def test_workflowautomation_security_post_endpoints_enforce_csrf_403(
    projectinitiation_csrf_client,
    workflowautomation_rule_a,
    workflowautomation_gate_a,
    workflowautomation_schedule_a,
    workflowautomation_webhook_a,
):
    """All mutative and create/edit POST endpoints return 403 Forbidden without CSRF token."""
    post_routes = [
        # Rules
        _workflowautomation_url("pwf_create"),
        _workflowautomation_url("pwf_edit", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_delete", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_toggle_active", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_test_run", workflowautomation_rule_a.pk),
        _workflowautomation_url("pwf_execute_now", workflowautomation_rule_a.pk),
        # Gates
        _workflowautomation_url("par_create"),
        _workflowautomation_url("par_edit", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_delete", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_approve", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_reject", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_escalate", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_delegate", workflowautomation_gate_a.pk),
        _workflowautomation_url("par_cancel", workflowautomation_gate_a.pk),
        # Recurring tasks
        _workflowautomation_url("rts_create"),
        _workflowautomation_url("rts_edit", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_delete", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_toggle_active", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_generate_task", workflowautomation_schedule_a.pk),
        _workflowautomation_url("rts_skip_next", workflowautomation_schedule_a.pk),
        # Webhooks
        _workflowautomation_url("pwh_create"),
        _workflowautomation_url("pwh_edit", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_delete", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_toggle_active", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_test_ping", workflowautomation_webhook_a.pk),
        _workflowautomation_url("pwh_rotate_secret", workflowautomation_webhook_a.pk),
    ]

    for url in post_routes:
        res = projectinitiation_csrf_client.post(url, {})
        assert res.status_code == 403, f"Expected 403 CSRF rejection on {url}, got {res.status_code}"


# ==================================================================================================
# 4. Secret Handling
# ==================================================================================================

def test_workflowautomation_security_webhook_secret_not_plaintext_or_flashed(
    client_a,
    workflowautomation_project_a,
    workflowautomation_webhook_a,
):
    """Webhook HMAC secret is never stored in plaintext on the model or flashed via messages."""
    # 1. Verify model storage is encrypted
    raw_secret = workflowautomation_webhook_a.generate_secret()
    workflowautomation_webhook_a.save()
    assert workflowautomation_webhook_a.secret != raw_secret
    assert raw_secret not in workflowautomation_webhook_a.secret
    assert workflowautomation_webhook_a.get_secret() == raw_secret

    # 2. Verify pwh_create messages do not flash raw secret
    res_create = client_a.post(
        _workflowautomation_url("pwh_create"),
        {
            "name": "Secret Flash Test Webhook",
            "target_url": "https://example.com/test",
            "project": str(workflowautomation_project_a.pk),
            "event_types": '["task.created"]',
        },
    )
    assert res_create.status_code == 302
    msgs_create = _workflowautomation_messages(res_create)
    created_webhook = ProjectWebhookEndpoint.objects.get(name="Secret Flash Test Webhook")
    revealed_secret = created_webhook.get_secret()
    for msg in msgs_create:
        assert revealed_secret not in msg, "Raw webhook secret was leaked in flash message on creation!"

    # 3. Verify pwh_rotate_secret messages do not flash new secret
    res_rot = client_a.post(_workflowautomation_url("pwh_rotate_secret", created_webhook.pk), {})
    assert res_rot.status_code == 302
    created_webhook.refresh_from_db()
    new_secret = created_webhook.get_secret()
    assert new_secret != revealed_secret
    msgs_rot = _workflowautomation_messages(res_rot)
    for msg in msgs_rot:
        assert new_secret not in msg, "Rotated webhook secret was leaked in flash message on rotation!"


def test_workflowautomation_security_webhook_secret_revealed_once_via_session(
    client_a,
    workflowautomation_project_a,
    workflowautomation_webhook_a,
):
    """Secret is revealed strictly once via session pop-once in pwh_detail."""
    # 1. Create webhook: session receives raw secret
    res_create = client_a.post(
        _workflowautomation_url("pwh_create"),
        {
            "name": "Session Reveal Webhook",
            "target_url": "https://example.com/session-reveal",
            "project": str(workflowautomation_project_a.pk),
            "event_types": '["task.created"]',
        },
    )
    assert res_create.status_code == 302
    created_webhook = ProjectWebhookEndpoint.objects.get(name="Session Reveal Webhook")
    raw_secret = created_webhook.get_secret()

    # First GET pwh_detail: secret revealed in context
    res_detail_1 = client_a.get(_workflowautomation_url("pwh_detail", created_webhook.pk))
    assert res_detail_1.status_code == 200
    assert res_detail_1.context["revealed_secret"] == raw_secret
    assert raw_secret.encode() in res_detail_1.content

    # Second GET pwh_detail: secret is popped from session, context is None
    res_detail_2 = client_a.get(_workflowautomation_url("pwh_detail", created_webhook.pk))
    assert res_detail_2.status_code == 200
    assert res_detail_2.context["revealed_secret"] is None
    assert raw_secret.encode() not in res_detail_2.content

    # 2. Rotate secret: session receives new raw secret
    res_rot = client_a.post(_workflowautomation_url("pwh_rotate_secret", created_webhook.pk), {})
    assert res_rot.status_code == 302
    created_webhook.refresh_from_db()
    new_raw_secret = created_webhook.get_secret()
    assert new_raw_secret != raw_secret

    # First GET after rotate: revealed once
    res_detail_3 = client_a.get(_workflowautomation_url("pwh_detail", created_webhook.pk))
    assert res_detail_3.status_code == 200
    assert res_detail_3.context["revealed_secret"] == new_raw_secret
    assert new_raw_secret.encode() in res_detail_3.content

    # Second GET after rotate: None
    res_detail_4 = client_a.get(_workflowautomation_url("pwh_detail", created_webhook.pk))
    assert res_detail_4.status_code == 200
    assert res_detail_4.context["revealed_secret"] is None
    assert new_raw_secret.encode() not in res_detail_4.content


# ==================================================================================================
# 5. Negative-Input Hardening
# ==================================================================================================

def test_workflowautomation_security_negative_input_hardening(
    client_a,
    workflowautomation_rule_a,
    workflowautomation_gate_a,
    workflowautomation_schedule_a,
    workflowautomation_webhook_a,
):
    """Junk GET params, invalid filter types, and non-existent IDs return 200 or 404, never 500."""
    # Junk GET query params on lists and boards
    queries = [
        (_workflowautomation_url("pwf_list"), {"project": "junk", "is_active": "bad", "page": "999", "trigger_entity": "invalid"}),
        (_workflowautomation_url("par_list"), {"project": "junk", "gate_type": "bad", "status": "junk", "page": "999"}),
        (_workflowautomation_url("rts_list"), {"project": "junk", "frequency": "bad", "is_active": "junk", "page": "999"}),
        (_workflowautomation_url("pwh_list"), {"project": "junk", "is_active": "junk", "page": "999"}),
        (_workflowautomation_url("pwh_delivery_list"), {"webhook": "junk", "status": "bad", "page": "999"}),
        (_workflowautomation_url("automation_overview"), {"junk_param": "xyz"}),
        (_workflowautomation_url("approval_inbox"), {"junk_param": "xyz"}),
        (_workflowautomation_url("recurrence_calendar"), {"junk_param": "xyz"}),
        (_workflowautomation_url("webhook_diagnostics"), {"junk_param": "xyz"}),
    ]

    for url, params in queries:
        res = client_a.get(url, params)
        assert res.status_code == 200, f"Junk GET {url} failed with status {res.status_code}"

    # Non-existent PKs return 404
    non_existent_pk = 999999
    non_existent_routes = [
        _workflowautomation_url("pwf_detail", non_existent_pk),
        _workflowautomation_url("pwf_edit", non_existent_pk),
        _workflowautomation_url("par_detail", non_existent_pk),
        _workflowautomation_url("par_edit", non_existent_pk),
        _workflowautomation_url("rts_detail", non_existent_pk),
        _workflowautomation_url("rts_edit", non_existent_pk),
        _workflowautomation_url("pwh_detail", non_existent_pk),
        _workflowautomation_url("pwh_edit", non_existent_pk),
        _workflowautomation_url("pwh_delivery_detail", non_existent_pk),
    ]

    for url in non_existent_routes:
        res = client_a.get(url)
        assert res.status_code == 404, f"Expected 404 for non-existent PK on {url}, got {res.status_code}"
