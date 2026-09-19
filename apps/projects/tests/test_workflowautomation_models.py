"""Projects 7.17 Workflow & Automation — Model tests.

Covers:
  1. ProjectWorkflowRule [PWF-] & WorkflowExecutionLog
  2. ProjectApprovalGate [PAR-]
  3. RecurringTaskSchedule [RTS-]
  4. ProjectWebhookEndpoint [PWH-] & ProjectWebhookDelivery

Test coverage includes:
  - Model defaults, choices, auto-number prefixes (PWF-, PAR-, RTS-, PWH-).
  - Badges and properties (is_active_badge, status_badge, is_terminal, frequency_badge, health_badge).
  - RecurringTaskSchedule.generate_task (ProjectTask attributes: effort_hours, assignee, planned_start, planned_end, status="planned").
  - RecurringTaskSchedule.advance_next_run_date for various frequencies.
  - ProjectWebhookEndpoint.generate_secret and verify_signature.
  - __str__ representations.
  - Meta constraints (unique_together = ("tenant", "number")).
"""
from datetime import timedelta
from decimal import Decimal
import hmac
import hashlib
import json
import pytest

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
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

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Module Helpers (_workflowautomation_*)
# ==================================================================================================

def _workflowautomation_make_sample_payload():
    return json.dumps({"event": "task.created", "task_id": 42}).encode("utf-8")


def _workflowautomation_assert_prefix(obj, prefix):
    assert obj.number.startswith(f"{prefix}-"), f"Expected number prefix {prefix}-, got {obj.number}"


# ==================================================================================================
# 1. Auto-numbering and Prefixes
# ==================================================================================================

def test_workflowautomation_model_autonumber_prefixes(
    tenant_a,
    workflowautomation_project_a,
    admin_user,
):
    """Verify that newly minted models have expected auto-number prefixes:
    ProjectWorkflowRule: PWF-
    ProjectApprovalGate: PAR-
    RecurringTaskSchedule: RTS-
    ProjectWebhookEndpoint: PWH-
    """
    rule = _workflowautomation_rule(tenant_a, project=workflowautomation_project_a)
    _workflowautomation_assert_prefix(rule, "PWF")

    gate = _workflowautomation_gate(
        tenant_a,
        project=workflowautomation_project_a,
        requested_by=admin_user,
        approver=admin_user,
    )
    _workflowautomation_assert_prefix(gate, "PAR")

    schedule = _workflowautomation_schedule(
        tenant_a,
        project=workflowautomation_project_a,
        default_assignee=admin_user,
    )
    _workflowautomation_assert_prefix(schedule, "RTS")

    webhook = _workflowautomation_webhook(tenant_a, project=workflowautomation_project_a)
    _workflowautomation_assert_prefix(webhook, "PWH")


def test_workflowautomation_model_autonumber_sequential_per_tenant(
    tenant_a,
    tenant_b,
    workflowautomation_project_a,
    workflowautomation_project_b,
):
    """Verify numbering increments sequentially per tenant and sequences are isolated across tenants."""
    rule_a1 = _workflowautomation_rule(tenant_a, project=workflowautomation_project_a, name="Rule A1")
    rule_a2 = _workflowautomation_rule(tenant_a, project=workflowautomation_project_a, name="Rule A2")
    rule_b1 = _workflowautomation_rule(tenant_b, project=workflowautomation_project_b, name="Rule B1")

    # Sequence numbers within tenant A increment
    num_a1 = int(rule_a1.number.split("-")[1])
    num_a2 = int(rule_a2.number.split("-")[1])
    assert num_a2 == num_a1 + 1

    # Tenant B starts its own independent sequence
    num_b1 = int(rule_b1.number.split("-")[1])
    assert num_b1 >= 1


def test_workflowautomation_model_number_does_not_change_on_resave(
    workflowautomation_rule_a,
    workflowautomation_gate_a,
    workflowautomation_schedule_a,
    workflowautomation_webhook_a,
):
    """Saving an existing model must never alter its minted number."""
    initial_rule_num = workflowautomation_rule_a.number
    workflowautomation_rule_a.name = "Renamed Rule"
    workflowautomation_rule_a.save()
    assert workflowautomation_rule_a.number == initial_rule_num

    initial_gate_num = workflowautomation_gate_a.number
    workflowautomation_gate_a.title = "Updated Gate Title"
    workflowautomation_gate_a.save()
    assert workflowautomation_gate_a.number == initial_gate_num

    initial_sched_num = workflowautomation_schedule_a.number
    workflowautomation_schedule_a.title_template = "Updated Schedule Template"
    workflowautomation_schedule_a.save()
    assert workflowautomation_schedule_a.number == initial_sched_num

    initial_hook_num = workflowautomation_webhook_a.number
    workflowautomation_webhook_a.name = "Updated Webhook Name"
    workflowautomation_webhook_a.save()
    assert workflowautomation_webhook_a.number == initial_hook_num


# ==================================================================================================
# 2. Meta Constraints & Multi-Tenant Isolation
# ==================================================================================================

def test_workflowautomation_model_unique_together_tenant_number(
    tenant_a,
    workflowautomation_project_a,
    workflowautomation_rule_a,
    workflowautomation_gate_a,
    workflowautomation_schedule_a,
    workflowautomation_webhook_a,
):
    """Verify unique_together = [('tenant', 'number')] enforces uniqueness within the same tenant."""
    # ProjectWorkflowRule collision
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_rule = ProjectWorkflowRule(
                tenant=tenant_a,
                project=workflowautomation_project_a,
                name="Duplicate Rule",
            )
            dup_rule.number = workflowautomation_rule_a.number
            dup_rule.save()

    # ProjectApprovalGate collision
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_gate = ProjectApprovalGate(
                tenant=tenant_a,
                project=workflowautomation_project_a,
                title="Duplicate Gate",
                target_model="milestone",
                target_id=1,
                requested_by=workflowautomation_gate_a.requested_by,
                approver=workflowautomation_gate_a.approver,
            )
            dup_gate.number = workflowautomation_gate_a.number
            dup_gate.save()

    # RecurringTaskSchedule collision
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_sched = RecurringTaskSchedule(
                tenant=tenant_a,
                project=workflowautomation_project_a,
                title_template="Duplicate Schedule",
                start_date=_workflowautomation_today(),
                next_run_date=_workflowautomation_today(),
            )
            dup_sched.number = workflowautomation_schedule_a.number
            dup_sched.save()

    # ProjectWebhookEndpoint collision
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            dup_wh = ProjectWebhookEndpoint(
                tenant=tenant_a,
                project=workflowautomation_project_a,
                name="Duplicate Webhook",
                target_url="https://example.com/duplicate",
            )
            dup_wh.number = workflowautomation_webhook_a.number
            dup_wh.save()


def test_workflowautomation_model_same_number_allowed_across_different_tenants(
    tenant_a,
    tenant_b,
    workflowautomation_project_a,
    workflowautomation_project_b,
):
    """Different tenants may have the same number without collision."""
    rule_a = _workflowautomation_rule(tenant_a, project=workflowautomation_project_a)
    rule_b = ProjectWorkflowRule(
        tenant=tenant_b,
        project=workflowautomation_project_b,
        name="Rule with same number in tenant B",
    )
    rule_b.number = rule_a.number
    rule_b.save()

    assert rule_a.tenant != rule_b.tenant
    assert rule_a.number == rule_b.number


def test_workflowautomation_model_multi_tenant_isolation(
    tenant_a,
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
    """Tenant A queries must never contain Tenant B rows, and vice-versa."""
    # Rules
    assert workflowautomation_rule_a in ProjectWorkflowRule.objects.filter(tenant=tenant_a)
    assert workflowautomation_rule_b not in ProjectWorkflowRule.objects.filter(tenant=tenant_a)
    assert workflowautomation_rule_b in ProjectWorkflowRule.objects.filter(tenant=tenant_b)

    # Gates
    assert workflowautomation_gate_a in ProjectApprovalGate.objects.filter(tenant=tenant_a)
    assert workflowautomation_gate_b not in ProjectApprovalGate.objects.filter(tenant=tenant_a)

    # Schedules
    assert workflowautomation_schedule_a in RecurringTaskSchedule.objects.filter(tenant=tenant_a)
    assert workflowautomation_schedule_b not in RecurringTaskSchedule.objects.filter(tenant=tenant_a)

    # Webhooks
    assert workflowautomation_webhook_a in ProjectWebhookEndpoint.objects.filter(tenant=tenant_a)
    assert workflowautomation_webhook_b not in ProjectWebhookEndpoint.objects.filter(tenant=tenant_a)

    # Deliveries
    assert workflowautomation_delivery_a in ProjectWebhookDelivery.objects.filter(tenant=tenant_a)
    assert workflowautomation_delivery_a not in ProjectWebhookDelivery.objects.filter(tenant=tenant_b)


# ==================================================================================================
# 3. Model Defaults and Choices
# ==================================================================================================

def test_workflowautomation_model_rule_defaults_and_choices(tenant_a, workflowautomation_project_a):
    """Verify ProjectWorkflowRule field defaults, entity choices, and event choices."""
    rule = ProjectWorkflowRule.objects.create(
        tenant=tenant_a,
        project=workflowautomation_project_a,
        name="Default Check Rule",
    )
    assert rule.is_active is True
    assert rule.trigger_entity == "task"
    assert rule.trigger_event == "status_changed"
    assert rule.trigger_field == ""
    assert rule.trigger_value == ""
    assert rule.conditions == []
    assert rule.actions == []
    assert rule.execution_count == 0
    assert rule.last_fired_at is None

    expected_entities = {
        "project", "task", "milestone", "risk",
        "issue", "budget", "scope_change", "inspection",
    }
    actual_entities = {c[0] for c in ProjectWorkflowRule.TRIGGER_ENTITY_CHOICES}
    assert expected_entities == actual_entities

    expected_events = {
        "created", "updated", "status_changed",
        "due_date_approaching", "threshold_breached", "blocked",
    }
    actual_events = {c[0] for c in ProjectWorkflowRule.TRIGGER_EVENT_CHOICES}
    assert expected_events == actual_events


def test_workflowautomation_model_execution_log_defaults_and_choices(tenant_a, workflowautomation_rule_a):
    """Verify WorkflowExecutionLog field defaults and choices."""
    log = WorkflowExecutionLog.objects.create(
        tenant=tenant_a,
        rule=workflowautomation_rule_a,
    )
    assert log.status == "success"
    assert log.record_label == ""
    assert log.target_model == ""
    assert log.target_id is None
    assert log.error_msg == ""
    assert log.duration_ms == 0
    assert log.evaluated_conditions == {}
    assert log.executed_actions == []
    assert log.fired_at is not None

    expected_statuses = {"success", "failed", "condition_failed", "simulated"}
    actual_statuses = {c[0] for c in WorkflowExecutionLog.STATUS_CHOICES}
    assert expected_statuses == actual_statuses


def test_workflowautomation_model_approval_gate_defaults_and_choices(
    tenant_a,
    workflowautomation_project_a,
    admin_user,
):
    """Verify ProjectApprovalGate field defaults, gate type choices, and status choices."""
    gate = ProjectApprovalGate.objects.create(
        tenant=tenant_a,
        project=workflowautomation_project_a,
        title="Gate Defaults Test",
        target_model="Project",
        target_id=workflowautomation_project_a.pk,
        requested_by=admin_user,
        approver=admin_user,
    )
    assert gate.gate_type == "phase_gate"
    assert gate.status == "pending"
    assert gate.timeout_hours == 48
    assert gate.threshold_amount is None
    assert gate.auto_approve_threshold is None
    assert gate.decision_notes == ""
    assert gate.decided_at is None
    assert gate.escalated_at is None

    expected_types = {
        "phase_gate", "scope_change", "budget_override",
        "deliverable_acceptance", "charter_signoff",
    }
    actual_types = {c[0] for c in ProjectApprovalGate.GATE_TYPE_CHOICES}
    assert expected_types == actual_types

    expected_statuses = {"pending", "approved", "rejected", "escalated", "auto_approved", "cancelled"}
    actual_statuses = {c[0] for c in ProjectApprovalGate.STATUS_CHOICES}
    assert expected_statuses == actual_statuses


def test_workflowautomation_model_recurring_task_defaults_and_choices(
    tenant_a,
    workflowautomation_project_a,
):
    """Verify RecurringTaskSchedule field defaults and choices."""
    today = _workflowautomation_today()
    schedule = RecurringTaskSchedule.objects.create(
        tenant=tenant_a,
        project=workflowautomation_project_a,
        title_template="Default Task Template",
        start_date=today,
        next_run_date=today,
    )
    assert schedule.is_active is True
    assert schedule.frequency == "weekly"
    assert schedule.interval_count == 1
    assert schedule.days_of_week == ""
    assert schedule.day_of_month is None
    assert schedule.priority == "medium"
    assert schedule.effort_hours == Decimal("0.00")
    assert schedule.assignee_strategy == "fixed_user"
    assert schedule.default_assignee is None
    assert schedule.end_date is None
    assert schedule.last_run_date is None
    assert schedule.tasks_created_count == 0

    expected_freqs = {"daily", "weekly", "biweekly", "monthly", "quarterly", "sprint_cadence"}
    actual_freqs = {c[0] for c in RecurringTaskSchedule.FREQUENCY_CHOICES}
    assert expected_freqs == actual_freqs

    expected_priorities = {"urgent", "high", "medium", "low"}
    actual_priorities = {c[0] for c in RecurringTaskSchedule.PRIORITY_CHOICES}
    assert expected_priorities == actual_priorities

    expected_strategies = {"fixed_user", "project_manager", "unassigned"}
    actual_strategies = {c[0] for c in RecurringTaskSchedule.ASSIGNEE_STRATEGY_CHOICES}
    assert expected_strategies == actual_strategies


def test_workflowautomation_model_webhook_endpoint_defaults(tenant_a, workflowautomation_project_a):
    """Verify ProjectWebhookEndpoint field defaults."""
    webhook = ProjectWebhookEndpoint.objects.create(
        tenant=tenant_a,
        project=workflowautomation_project_a,
        name="Default Hook",
        target_url="https://example.com/hook",
    )
    assert webhook.is_active is True
    assert webhook.secret == ""
    assert webhook.event_types == []
    assert webhook.custom_headers == {}
    assert webhook.last_status_code is None
    assert webhook.last_fired_at is None
    assert webhook.failure_count == 0


def test_workflowautomation_model_webhook_delivery_defaults_and_choices(
    tenant_a,
    workflowautomation_webhook_a,
):
    """Verify ProjectWebhookDelivery field defaults and choices."""
    delivery = ProjectWebhookDelivery.objects.create(
        tenant=tenant_a,
        webhook=workflowautomation_webhook_a,
        event="test.event",
    )
    assert delivery.status == "success"
    assert delivery.payload == {}
    assert delivery.signature == ""
    assert delivery.status_code is None
    assert delivery.response_body == ""
    assert delivery.duration_ms == 0
    assert delivery.attempted_at is not None

    expected_statuses = {"success", "failed", "simulated"}
    actual_statuses = {c[0] for c in ProjectWebhookDelivery.STATUS_CHOICES}
    assert expected_statuses == actual_statuses


# ==================================================================================================
# 4. Badges and Properties
# ==================================================================================================

def test_workflowautomation_model_rule_is_active_badge(workflowautomation_rule_a):
    """Test is_active_badge on ProjectWorkflowRule."""
    workflowautomation_rule_a.is_active = True
    assert workflowautomation_rule_a.is_active_badge == "badge-green"

    workflowautomation_rule_a.is_active = False
    assert workflowautomation_rule_a.is_active_badge == "badge-slate"


def test_workflowautomation_model_execution_log_status_badge(tenant_a, workflowautomation_rule_a):
    """Test status_badge on WorkflowExecutionLog for all status values."""
    expected_mapping = {
        "success": "badge-green",
        "failed": "badge-red",
        "condition_failed": "badge-amber",
        "simulated": "badge-info",
        "unknown_custom": "badge-slate",
    }
    for status_val, expected_badge in expected_mapping.items():
        log = WorkflowExecutionLog(
            tenant=tenant_a,
            rule=workflowautomation_rule_a,
            status=status_val,
        )
        assert log.status_badge == expected_badge


def test_workflowautomation_model_approval_gate_status_badge(
    tenant_a,
    workflowautomation_project_a,
    admin_user,
):
    """Test status_badge on ProjectApprovalGate for all status values."""
    expected_mapping = {
        "pending": "badge-amber",
        "approved": "badge-green",
        "auto_approved": "badge-green",
        "rejected": "badge-red",
        "escalated": "badge-red",
        "cancelled": "badge-slate",
        "other": "badge-slate",
    }
    for status_val, expected_badge in expected_mapping.items():
        gate = ProjectApprovalGate(
            tenant=tenant_a,
            project=workflowautomation_project_a,
            requested_by=admin_user,
            approver=admin_user,
            status=status_val,
        )
        assert gate.status_badge == expected_badge


def test_workflowautomation_model_approval_gate_is_terminal(
    tenant_a,
    workflowautomation_project_a,
    admin_user,
):
    """Test is_terminal on ProjectApprovalGate:
    True for approved, auto_approved, rejected, cancelled.
    False for pending, escalated.
    """
    terminal_statuses = ["approved", "auto_approved", "rejected", "cancelled"]
    non_terminal_statuses = ["pending", "escalated"]

    for st in terminal_statuses:
        gate = ProjectApprovalGate(
            tenant=tenant_a,
            project=workflowautomation_project_a,
            requested_by=admin_user,
            approver=admin_user,
            status=st,
        )
        assert gate.is_terminal is True, f"Status {st} should be terminal"

    for st in non_terminal_statuses:
        gate = ProjectApprovalGate(
            tenant=tenant_a,
            project=workflowautomation_project_a,
            requested_by=admin_user,
            approver=admin_user,
            status=st,
        )
        assert gate.is_terminal is False, f"Status {st} should not be terminal"


def test_workflowautomation_model_recurring_schedule_badges(
    tenant_a,
    workflowautomation_project_a,
):
    """Test is_active_badge and frequency_badge on RecurringTaskSchedule."""
    sched = RecurringTaskSchedule(
        tenant=tenant_a,
        project=workflowautomation_project_a,
        is_active=True,
        frequency="weekly",
        start_date=_workflowautomation_today(),
        next_run_date=_workflowautomation_today(),
    )
    assert sched.is_active_badge == "badge-green"
    sched.is_active = False
    assert sched.is_active_badge == "badge-slate"

    freq_badges = {
        "daily": "badge-blue",
        "weekly": "badge-purple",
        "biweekly": "badge-indigo",
        "monthly": "badge-amber",
        "quarterly": "badge-emerald",
        "sprint_cadence": "badge-cyan",
        "custom_other": "badge-slate",
    }
    for freq, expected_badge in freq_badges.items():
        sched.frequency = freq
        assert sched.frequency_badge == expected_badge, f"Frequency {freq} expected badge {expected_badge}"


def test_workflowautomation_model_webhook_endpoint_badges(
    tenant_a,
    workflowautomation_project_a,
):
    """Test is_active_badge and health_badge on ProjectWebhookEndpoint."""
    wh = ProjectWebhookEndpoint(
        tenant=tenant_a,
        project=workflowautomation_project_a,
        is_active=True,
    )
    assert wh.is_active_badge == "badge-green"
    wh.is_active = False
    assert wh.is_active_badge == "badge-slate"

    # Health badge based on last_status_code
    wh.last_status_code = None
    assert wh.health_badge == "badge-slate"

    wh.last_status_code = 200
    assert wh.health_badge == "badge-green"

    wh.last_status_code = 204
    assert wh.health_badge == "badge-green"

    wh.last_status_code = 301
    assert wh.health_badge == "badge-info"

    wh.last_status_code = 302
    assert wh.health_badge == "badge-info"

    wh.last_status_code = 400
    assert wh.health_badge == "badge-red"

    wh.last_status_code = 500
    assert wh.health_badge == "badge-red"


def test_workflowautomation_model_webhook_delivery_status_badge(
    tenant_a,
    workflowautomation_webhook_a,
):
    """Test status_badge on ProjectWebhookDelivery."""
    expected_mapping = {
        "success": "badge-green",
        "failed": "badge-red",
        "simulated": "badge-info",
        "other": "badge-slate",
    }
    for status_val, expected_badge in expected_mapping.items():
        delivery = ProjectWebhookDelivery(
            tenant=tenant_a,
            webhook=workflowautomation_webhook_a,
            event="test",
            status=status_val,
        )
        assert delivery.status_badge == expected_badge


# ==================================================================================================
# 5. String Representations (__str__)
# ==================================================================================================

def test_workflowautomation_model_rule_str(workflowautomation_rule_a):
    """ProjectWorkflowRule __str__ format: '{number} — {name}'."""
    expected = f"{workflowautomation_rule_a.number} \u2014 {workflowautomation_rule_a.name}"
    assert str(workflowautomation_rule_a) == expected


def test_workflowautomation_model_execution_log_str(tenant_a, workflowautomation_rule_a):
    """WorkflowExecutionLog __str__ format: 'Log for {rule_label} ({status}) at {fired_at}'."""
    log = _workflowautomation_execution_log(tenant_a, workflowautomation_rule_a, status="success")
    expected = f"Log for {workflowautomation_rule_a.number} (success) at {log.fired_at}"
    assert str(log) == expected

    # When rule is not in fields_cache, falls back to Rule #{rule_id}
    log_uncached = WorkflowExecutionLog.objects.only("id", "rule_id", "status", "fired_at").get(pk=log.pk)
    expected_uncached = f"Log for Rule #{workflowautomation_rule_a.pk} (success) at {log_uncached.fired_at}"
    assert str(log_uncached) == expected_uncached


def test_workflowautomation_model_approval_gate_str(workflowautomation_gate_a):
    """ProjectApprovalGate __str__ format: '{number} — {title} ({status_display})'."""
    expected = f"{workflowautomation_gate_a.number} \u2014 {workflowautomation_gate_a.title} ({workflowautomation_gate_a.get_status_display()})"
    assert str(workflowautomation_gate_a) == expected


def test_workflowautomation_model_recurring_schedule_str(workflowautomation_schedule_a):
    """RecurringTaskSchedule __str__ format: '{number} — {title_template} ({frequency_display})'."""
    expected = f"{workflowautomation_schedule_a.number} \u2014 {workflowautomation_schedule_a.title_template} ({workflowautomation_schedule_a.get_frequency_display()})"
    assert str(workflowautomation_schedule_a) == expected


def test_workflowautomation_model_webhook_endpoint_str(workflowautomation_webhook_a):
    """ProjectWebhookEndpoint __str__ format: '{number} — {name} ({target_url})'."""
    expected = f"{workflowautomation_webhook_a.number} \u2014 {workflowautomation_webhook_a.name} ({workflowautomation_webhook_a.target_url})"
    assert str(workflowautomation_webhook_a) == expected


def test_workflowautomation_model_webhook_delivery_str(tenant_a, workflowautomation_webhook_a):
    """ProjectWebhookDelivery __str__ format: 'Delivery for {webhook_label} ({status}) at {attempted_at}'."""
    delivery = _workflowautomation_delivery(tenant_a, workflowautomation_webhook_a, status="success")
    expected = f"Delivery for {workflowautomation_webhook_a.number} (success) at {delivery.attempted_at}"
    assert str(delivery) == expected

    # When webhook is not cached
    delivery_uncached = ProjectWebhookDelivery.objects.only("id", "webhook_id", "status", "attempted_at").get(pk=delivery.pk)
    expected_uncached = f"Delivery for Webhook #{workflowautomation_webhook_a.pk} (success) at {delivery_uncached.attempted_at}"
    assert str(delivery_uncached) == expected_uncached


# ==================================================================================================
# 6. RecurringTaskSchedule — advance_next_run_date & clean
# ==================================================================================================

def test_workflowautomation_model_schedule_advance_daily(tenant_a, workflowautomation_project_a):
    """advance_next_run_date for daily cadence advances by 1 * interval_count days."""
    today = _workflowautomation_today()
    schedule = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        frequency="daily",
        interval_count=1,
        next_run_date=today,
    )
    schedule.advance_next_run_date()
    assert schedule.next_run_date == today + timedelta(days=1)

    # With interval = 3
    schedule.interval_count = 3
    schedule.advance_next_run_date()
    assert schedule.next_run_date == today + timedelta(days=1 + 3)


def test_workflowautomation_model_schedule_advance_weekly(tenant_a, workflowautomation_project_a):
    """advance_next_run_date for weekly cadence advances by 7 * interval_count days."""
    today = _workflowautomation_today()
    schedule = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        frequency="weekly",
        interval_count=1,
        next_run_date=today,
    )
    schedule.advance_next_run_date()
    assert schedule.next_run_date == today + timedelta(days=7)

    schedule.interval_count = 2
    schedule.advance_next_run_date()
    assert schedule.next_run_date == today + timedelta(days=7 + 14)


def test_workflowautomation_model_schedule_advance_biweekly(tenant_a, workflowautomation_project_a):
    """advance_next_run_date for biweekly cadence advances by 14 * interval_count days."""
    today = _workflowautomation_today()
    schedule = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        frequency="biweekly",
        interval_count=1,
        next_run_date=today,
    )
    schedule.advance_next_run_date()
    assert schedule.next_run_date == today + timedelta(days=14)


def test_workflowautomation_model_schedule_advance_monthly(tenant_a, workflowautomation_project_a):
    """advance_next_run_date for monthly cadence advances by 30 * interval_count days."""
    today = _workflowautomation_today()
    schedule = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        frequency="monthly",
        interval_count=1,
        next_run_date=today,
    )
    schedule.advance_next_run_date()
    assert schedule.next_run_date == today + timedelta(days=30)


def test_workflowautomation_model_schedule_advance_quarterly(tenant_a, workflowautomation_project_a):
    """advance_next_run_date for quarterly cadence advances by 90 * interval_count days."""
    today = _workflowautomation_today()
    schedule = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        frequency="quarterly",
        interval_count=1,
        next_run_date=today,
    )
    schedule.advance_next_run_date()
    assert schedule.next_run_date == today + timedelta(days=90)


def test_workflowautomation_model_schedule_advance_sprint_cadence(tenant_a, workflowautomation_project_a):
    """advance_next_run_date for sprint_cadence advances by 14 * interval_count days."""
    today = _workflowautomation_today()
    schedule = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        frequency="sprint_cadence",
        interval_count=1,
        next_run_date=today,
    )
    schedule.advance_next_run_date()
    assert schedule.next_run_date == today + timedelta(days=14)


def test_workflowautomation_model_schedule_advance_deactivates_past_end_date(
    tenant_a,
    workflowautomation_project_a,
):
    """advance_next_run_date sets is_active=False when next_run_date surpasses end_date."""
    today = _workflowautomation_today()
    schedule = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        frequency="weekly",
        interval_count=1,
        next_run_date=today,
        end_date=today + timedelta(days=5),  # Advancing by 7 will exceed end_date
        is_active=True,
    )
    schedule.advance_next_run_date()
    assert schedule.next_run_date == today + timedelta(days=7)
    assert schedule.is_active is False


def test_workflowautomation_model_schedule_clean_validation(tenant_a, workflowautomation_project_a):
    """clean() raises ValidationError when end_date is prior to start_date."""
    today = _workflowautomation_today()
    schedule = RecurringTaskSchedule(
        tenant=tenant_a,
        project=workflowautomation_project_a,
        title_template="Invalid Date Range",
        start_date=today,
        end_date=today - timedelta(days=1),
        next_run_date=today,
    )
    with pytest.raises(ValidationError) as exc_info:
        schedule.clean()
    assert "end_date" in exc_info.value.message_dict


# ==================================================================================================
# 7. RecurringTaskSchedule — generate_task
# ==================================================================================================

def test_workflowautomation_model_schedule_generate_task_attributes(
    tenant_a,
    workflowautomation_project_a,
    admin_user,
):
    """generate_task creates a ProjectTask with expected attributes:
    effort_hours, assignee, planned_start, planned_end, status='planned'.
    """
    today = _workflowautomation_today()
    schedule = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        default_assignee=admin_user,
        effort_hours=Decimal("7.50"),
        assignee_strategy="fixed_user",
        next_run_date=today,
        frequency="weekly",
    )

    task = schedule.generate_task()

    assert isinstance(task, ProjectTask)
    assert task.tenant == tenant_a
    assert task.project == workflowautomation_project_a
    assert task.effort_hours == Decimal("7.50")
    assert task.assignee == admin_user
    assert task.planned_start == today
    assert task.planned_end == today + timedelta(days=5)
    assert task.status == "planned"


def test_workflowautomation_model_schedule_generate_task_assignee_strategies(
    tenant_a,
    workflowautomation_project_a,
    admin_user,
):
    """generate_task determines assignee based on assignee_strategy:
    fixed_user -> default_assignee
    project_manager -> project.project_manager
    unassigned -> None
    """
    today = _workflowautomation_today()

    # fixed_user
    sched_fixed = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        assignee_strategy="fixed_user",
        default_assignee=admin_user,
        next_run_date=today,
    )
    task_fixed = sched_fixed.generate_task()
    assert task_fixed.assignee == admin_user

    # project_manager
    workflowautomation_project_a.project_manager = admin_user
    workflowautomation_project_a.save()
    sched_pm = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        assignee_strategy="project_manager",
        next_run_date=today,
    )
    task_pm = sched_pm.generate_task()
    assert task_pm.assignee == admin_user

    # unassigned
    sched_unassigned = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        assignee_strategy="unassigned",
        next_run_date=today,
    )
    task_unassigned = sched_unassigned.generate_task()
    assert task_unassigned.assignee is None


def test_workflowautomation_model_schedule_generate_task_priority_mapping(
    tenant_a,
    workflowautomation_project_a,
):
    """generate_task maps priority choices to ProjectTask priority:
    urgent -> critical
    high -> high
    medium -> medium
    low -> low
    """
    today = _workflowautomation_today()
    priority_tests = [
        ("urgent", "critical"),
        ("high", "high"),
        ("medium", "medium"),
        ("low", "low"),
    ]
    for rts_prio, expected_task_prio in priority_tests:
        schedule = _workflowautomation_schedule(
            tenant_a,
            workflowautomation_project_a,
            priority=rts_prio,
            next_run_date=today,
        )
        task = schedule.generate_task()
        assert task.priority == expected_task_prio, f"Expected {expected_task_prio} for {rts_prio}"


def test_workflowautomation_model_schedule_generate_task_template_interpolation(
    tenant_a,
    workflowautomation_project_a,
):
    """generate_task replaces {{date}}, {{week}}, and {{project}} placeholders in title and description."""
    today = _workflowautomation_today()
    iso_date = today.isoformat()
    iso_week = f"W{today.isocalendar()[1]}"
    proj_name = workflowautomation_project_a.name

    schedule = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        title_template="Sprint Sync - {{project}} - {{week}} - {{date}}",
        description_template="Auto generated for {{project}} on {{date}}.",
        next_run_date=today,
    )

    task = schedule.generate_task()

    assert proj_name in task.name
    assert iso_week in task.name
    assert iso_date in task.name
    assert proj_name in task.description
    assert iso_date in task.description
    assert f"[Auto-generated by Recurring Schedule {schedule.number}]" in task.description


def test_workflowautomation_model_schedule_generate_task_increments_and_advances(
    tenant_a,
    workflowautomation_project_a,
):
    """generate_task increments tasks_created_count, sets last_run_date, advances next_run_date, and saves."""
    today = _workflowautomation_today()
    schedule = _workflowautomation_schedule(
        tenant_a,
        workflowautomation_project_a,
        frequency="weekly",
        interval_count=1,
        next_run_date=today,
    )
    initial_count = schedule.tasks_created_count

    schedule.generate_task()
    schedule.refresh_from_db()

    assert schedule.tasks_created_count == initial_count + 1
    assert schedule.last_run_date == today
    assert schedule.next_run_date == today + timedelta(days=7)


# ==================================================================================================
# 8. Webhook Secret Generation and Signature Verification
# ==================================================================================================

def test_workflowautomation_model_webhook_generate_secret(tenant_a, workflowautomation_project_a):
    """generate_secret() creates a 64-char hex secret (32 bytes), encrypts it, and get_secret() returns it."""
    webhook = _workflowautomation_webhook(tenant_a, project=workflowautomation_project_a)
    assert webhook.secret == ""

    raw_secret = webhook.generate_secret()
    assert len(raw_secret) == 64
    assert webhook.secret != ""  # Encrypted ciphertext stored
    assert webhook.secret != raw_secret  # Ciphertext differs from raw plaintext
    assert webhook.get_secret() == raw_secret  # Decrypts back to raw plaintext


def test_workflowautomation_model_webhook_set_and_get_secret(tenant_a, workflowautomation_project_a):
    """set_secret() encrypts the raw secret and get_secret() decrypts it.
    Setting empty string clears the secret.
    """
    webhook = _workflowautomation_webhook(tenant_a, project=workflowautomation_project_a)
    webhook.set_secret("my-super-secret-key-12345")
    assert webhook.secret != "my-super-secret-key-12345"
    assert webhook.get_secret() == "my-super-secret-key-12345"

    # Clearing secret
    webhook.set_secret("")
    assert webhook.secret == ""
    assert webhook.get_secret() == ""


def test_workflowautomation_model_webhook_compute_signature(tenant_a, workflowautomation_project_a):
    """compute_signature() produces HMAC-SHA256 hex digest for given bytes.
    Returns empty string if no secret is set.
    """
    webhook = _workflowautomation_webhook(tenant_a, project=workflowautomation_project_a)
    payload_bytes = _workflowautomation_make_sample_payload()

    # Without secret
    assert webhook.compute_signature(payload_bytes) == ""

    # With secret
    raw_secret = webhook.generate_secret()
    computed = webhook.compute_signature(payload_bytes)
    assert len(computed) == 64

    # Verify matching standard hmac calculation
    expected = hmac.new(raw_secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    assert computed == expected


def test_workflowautomation_model_webhook_verify_signature(tenant_a, workflowautomation_project_a):
    """verify_signature() validates HMAC-SHA256 against expected payload.
    Returns True for valid signature, False for invalid, tampered, or missing secrets.
    """
    webhook = _workflowautomation_webhook(tenant_a, project=workflowautomation_project_a)
    payload_bytes = _workflowautomation_make_sample_payload()
    tampered_bytes = json.dumps({"event": "task.created", "task_id": 999}).encode("utf-8")

    # Without secret, verify_signature is False
    assert webhook.verify_signature(payload_bytes, "any-sig") is False

    # Generate secret
    webhook.generate_secret()
    valid_sig = webhook.compute_signature(payload_bytes)

    # Valid signature
    assert webhook.verify_signature(payload_bytes, valid_sig) is True

    # Tampered payload
    assert webhook.verify_signature(tampered_bytes, valid_sig) is False

    # Invalid signature
    assert webhook.verify_signature(payload_bytes, "bad-signature-string") is False

    # Empty signature
    assert webhook.verify_signature(payload_bytes, "") is False
