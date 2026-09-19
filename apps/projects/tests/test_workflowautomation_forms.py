"""Projects 7.17 Workflow & Automation — FORM tests.

Covers:
  1. ProjectWorkflowRuleForm & WorkflowRuleTestForm
  2. ProjectApprovalGateForm, ApprovalDecisionForm & ApprovalDelegateForm
  3. RecurringTaskScheduleForm
  4. ProjectWebhookEndpointForm & WebhookTestPingForm

Test coverage:
  - Form exclusions: verify tenant, number, status, requested_by, auto_approve_threshold,
    secret/hash fields, system timestamps, and derived counters are NOT present in form fields.
  - Smuggled values in POST payloads are ignored on save.
  - Required field validation and invalid inputs.
  - ApprovalDelegateForm tenant scoping and inactive user filtering.
  - ProjectWebhookEndpointForm event_types non-empty requirement, JSON parsing, custom_headers parsing.
  - RecurringTaskScheduleForm end_date < start_date clean error, effort hours, frequency choices.
  - Negative input and boundary testing.
  - Edit mode field consistency.
"""
import datetime
from decimal import Decimal
import json

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.projects.forms import (
    ApprovalDecisionForm,
    ApprovalDelegateForm,
    ProjectApprovalGateForm,
    ProjectWebhookEndpointForm,
    ProjectWorkflowRuleForm,
    RecurringTaskScheduleForm,
    WebhookTestPingForm,
    WorkflowRuleTestForm,
)
from apps.projects.models import (
    ProjectApprovalGate,
    ProjectWebhookEndpoint,
    ProjectWorkflowRule,
    RecurringTaskSchedule,
)
from apps.projects.tests.conftest import (
    _workflowautomation_today,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==================================================================================================
# Module Helpers (_workflowautomation_*)
# ==================================================================================================

def _workflowautomation_widen(form, *field_names):
    """Widen the queryset of named ModelChoiceFields to include all objects.
    This simulates a crafted cross-tenant POST where widget narrowing is bypassed.
    """
    for name in field_names:
        field = form.fields[name]
        field.queryset = field.queryset.model._default_manager.all()
    return form


def _workflowautomation_save_form(form, tenant, **extra_attrs):
    """Save a TenantModelForm instance stamping tenant and any extra required model attributes."""
    obj = form.save(commit=False)
    if hasattr(obj, "tenant_id") and not obj.tenant_id:
        obj.tenant = tenant
    for k, v in extra_attrs.items():
        setattr(obj, k, v)
    obj.save()
    return obj


def _workflowautomation_rule_payload(**overrides):
    """Minimum valid payload for ProjectWorkflowRuleForm."""
    payload = {
        "name": "Auto-escalate Critical Bugs",
        "description": "Rule to escalate critical bugs to PM",
        "is_active": True,
        "trigger_entity": "task",
        "trigger_event": "status_changed",
        "trigger_field": "priority",
        "trigger_value": "critical",
        "conditions": json.dumps([{"field": "priority", "operator": "equals", "value": "critical"}]),
        "actions": json.dumps([{"type": "notify_owner", "parameters": {}}]),
    }
    payload.update(overrides)
    return payload


def _workflowautomation_gate_payload(project, approver, **overrides):
    """Minimum valid payload for ProjectApprovalGateForm."""
    payload = {
        "project": str(project.pk),
        "gate_type": "phase_gate",
        "title": "Phase 1 Transition Sign-off",
        "description": "Sign-off required before moving to Phase 2",
        "target_model": "Project",
        "target_id": project.pk,
        "target_label": "Project Phase Gate",
        "approver": str(approver.pk),
        "timeout_hours": 48,
    }
    payload.update(overrides)
    return payload


def _workflowautomation_schedule_payload(project, **overrides):
    """Minimum valid payload for RecurringTaskScheduleForm."""
    today = _workflowautomation_today()
    payload = {
        "project": str(project.pk),
        "title_template": "Weekly Bug Triage — {{week}}",
        "description_template": "Review and assign open bugs for {{project}}",
        "is_active": True,
        "frequency": "weekly",
        "interval_count": 1,
        "priority": "medium",
        "effort_hours": "2.00",
        "assignee_strategy": "unassigned",
        "start_date": today.isoformat(),
        "next_run_date": today.isoformat(),
    }
    payload.update(overrides)
    return payload


def _workflowautomation_webhook_payload(**overrides):
    """Minimum valid payload for ProjectWebhookEndpointForm."""
    payload = {
        "name": "Jira Bi-directional Sync",
        "target_url": "https://hooks.jira.example.com/sync",
        "is_active": True,
        "event_types": json.dumps(["task.created", "task.updated"]),
        "custom_headers": json.dumps({"Authorization": "Bearer secret-token-123"}),
    }
    payload.update(overrides)
    return payload


# ==================================================================================================
# 1. Form Exclusions & Security Boundaries
# ==================================================================================================

def test_workflowautomation_form_rule_exclusions(tenant_a):
    """ProjectWorkflowRuleForm must exclude system columns:
    tenant, number, execution_count, last_fired_at, created_at, updated_at, status.
    """
    form = ProjectWorkflowRuleForm(tenant=tenant_a)
    fields = set(form.fields.keys())

    excluded_expected = {
        "tenant",
        "number",
        "execution_count",
        "last_fired_at",
        "created_at",
        "updated_at",
        "status",
    }
    for field_name in excluded_expected:
        assert field_name not in fields, f"{field_name} must not be present in ProjectWorkflowRuleForm"


def test_workflowautomation_form_approval_gate_exclusions(tenant_a):
    """ProjectApprovalGateForm must exclude system columns & verb-driven fields:
    tenant, number, status, requested_by, auto_approve_threshold, decision_notes,
    decided_at, escalated_at, created_at, updated_at.
    """
    form = ProjectApprovalGateForm(tenant=tenant_a)
    fields = set(form.fields.keys())

    excluded_expected = {
        "tenant",
        "number",
        "status",
        "requested_by",
        "auto_approve_threshold",
        "decision_notes",
        "decided_at",
        "escalated_at",
        "created_at",
        "updated_at",
    }
    for field_name in excluded_expected:
        assert field_name not in fields, f"{field_name} must not be present in ProjectApprovalGateForm"


def test_workflowautomation_form_recurring_schedule_exclusions(tenant_a):
    """RecurringTaskScheduleForm must exclude system columns & counters:
    tenant, number, last_run_date, tasks_created_count, created_at, updated_at, status.
    """
    form = RecurringTaskScheduleForm(tenant=tenant_a)
    fields = set(form.fields.keys())

    excluded_expected = {
        "tenant",
        "number",
        "last_run_date",
        "tasks_created_count",
        "created_at",
        "updated_at",
        "status",
    }
    for field_name in excluded_expected:
        assert field_name not in fields, f"{field_name} must not be present in RecurringTaskScheduleForm"


def test_workflowautomation_form_webhook_endpoint_exclusions(tenant_a):
    """ProjectWebhookEndpointForm must exclude system columns, secrets, and counters:
    tenant, number, secret, signing_secret_hash, last_status_code, last_fired_at,
    failure_count, created_at, updated_at, status.
    """
    form = ProjectWebhookEndpointForm(tenant=tenant_a)
    fields = set(form.fields.keys())

    excluded_expected = {
        "tenant",
        "number",
        "secret",
        "signing_secret_hash",
        "last_status_code",
        "last_fired_at",
        "failure_count",
        "created_at",
        "updated_at",
        "status",
    }
    for field_name in excluded_expected:
        assert field_name not in fields, f"{field_name} must not be present in ProjectWebhookEndpointForm"


def test_workflowautomation_form_smuggled_values_ignored_on_rule_save(
    tenant_a,
    tenant_b,
    workflowautomation_project_a,
):
    """Smuggled system values (tenant, number, execution_count, last_fired_at) in payload
    must be ignored when saving ProjectWorkflowRuleForm.
    """
    payload = _workflowautomation_rule_payload(
        project=str(workflowautomation_project_a.pk),
        tenant=str(tenant_b.pk),
        number="PWF-99999",
        execution_count=999,
        last_fired_at="2020-01-01T00:00:00",
    )
    form = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    rule = _workflowautomation_save_form(form, tenant_a)
    rule.refresh_from_db()

    assert rule.tenant_id == tenant_a.pk
    assert rule.number != "PWF-99999"
    assert rule.number.startswith("PWF-")
    assert rule.execution_count == 0
    assert rule.last_fired_at is None


def test_workflowautomation_form_smuggled_values_ignored_on_approval_gate_save(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    workflowautomation_project_a,
):
    """Smuggled values (tenant, number, status, requested_by, auto_approve_threshold, decided_at)
    in payload must be ignored when saving ProjectApprovalGateForm.
    """
    payload = _workflowautomation_gate_payload(
        project=workflowautomation_project_a,
        approver=admin_user,
        tenant=str(tenant_b.pk),
        number="PAR-99999",
        status="approved",
        requested_by=str(admin_b.pk),
        auto_approve_threshold="99999.00",
        decision_notes="Smuggled decision",
        decided_at="2020-01-01T00:00:00",
    )
    form = ProjectApprovalGateForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    gate = _workflowautomation_save_form(form, tenant_a, requested_by=admin_user)
    gate.refresh_from_db()

    assert gate.tenant_id == tenant_a.pk
    assert gate.number != "PAR-99999"
    assert gate.number.startswith("PAR-")
    assert gate.status == "pending"
    assert gate.auto_approve_threshold is None
    assert gate.decision_notes == ""
    assert gate.decided_at is None


def test_workflowautomation_form_smuggled_values_ignored_on_recurring_schedule_save(
    tenant_a,
    tenant_b,
    workflowautomation_project_a,
):
    """Smuggled values (tenant, number, tasks_created_count, last_run_date) in payload
    must be ignored when saving RecurringTaskScheduleForm.
    """
    payload = _workflowautomation_schedule_payload(
        project=workflowautomation_project_a,
        tenant=str(tenant_b.pk),
        number="RTS-99999",
        tasks_created_count=50,
        last_run_date="2020-01-01",
    )
    form = RecurringTaskScheduleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    schedule = _workflowautomation_save_form(form, tenant_a)
    schedule.refresh_from_db()

    assert schedule.tenant_id == tenant_a.pk
    assert schedule.number != "RTS-99999"
    assert schedule.number.startswith("RTS-")
    assert schedule.tasks_created_count == 0
    assert schedule.last_run_date is None


def test_workflowautomation_form_smuggled_values_ignored_on_webhook_endpoint_save(
    tenant_a,
    tenant_b,
    workflowautomation_project_a,
):
    """Smuggled values (tenant, number, secret, failure_count, last_status_code) in payload
    must be ignored when saving ProjectWebhookEndpointForm.
    """
    payload = _workflowautomation_webhook_payload(
        project=str(workflowautomation_project_a.pk),
        tenant=str(tenant_b.pk),
        number="PWH-99999",
        secret="hacked-secret-key",
        signing_secret_hash="fake-hash",
        failure_count=99,
        last_status_code=500,
    )
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    webhook = _workflowautomation_save_form(form, tenant_a)
    webhook.refresh_from_db()

    assert webhook.tenant_id == tenant_a.pk
    assert webhook.number != "PWH-99999"
    assert webhook.number.startswith("PWH-")
    assert webhook.secret == ""
    assert webhook.failure_count == 0
    assert webhook.last_status_code is None


# ==================================================================================================
# 2. ProjectWorkflowRuleForm & WorkflowRuleTestForm
# ==================================================================================================

def test_workflowautomation_form_rule_valid_create(
    tenant_a,
    workflowautomation_project_a,
    admin_user,
):
    """ProjectWorkflowRuleForm saves successfully with valid input data."""
    payload = _workflowautomation_rule_payload(
        project=str(workflowautomation_project_a.pk),
        owner=str(admin_user.pk),
    )
    form = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    rule = _workflowautomation_save_form(form, tenant_a)
    assert rule.pk is not None
    assert rule.name == "Auto-escalate Critical Bugs"
    assert rule.project == workflowautomation_project_a
    assert rule.owner == admin_user
    assert len(rule.conditions) == 1
    assert len(rule.actions) == 1


def test_workflowautomation_form_rule_required_fields(tenant_a):
    """ProjectWorkflowRuleForm requires name, trigger_entity, trigger_event."""
    form = ProjectWorkflowRuleForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "trigger_entity" in form.errors
    assert "trigger_event" in form.errors


def test_workflowautomation_form_rule_conditions_valid_json_string(tenant_a):
    """clean_conditions parses a valid JSON array string into a Python list."""
    conds = [{"field": "status", "operator": "equals", "value": "in_progress"}]
    payload = _workflowautomation_rule_payload(conditions=json.dumps(conds))
    form = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["conditions"] == conds


def test_workflowautomation_form_rule_conditions_invalid_json(tenant_a):
    """clean_conditions rejects malformed JSON string."""
    payload = _workflowautomation_rule_payload(conditions='[{"field": "status"')
    form = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "conditions" in form.errors

    # Direct invocation of clean_conditions with string
    form_direct = ProjectWorkflowRuleForm(tenant=tenant_a)
    form_direct.cleaned_data = {"conditions": '[{"field": "status"'}
    with pytest.raises(forms.ValidationError, match="Invalid JSON for conditions"):
        form_direct.clean_conditions()


def test_workflowautomation_form_rule_conditions_non_list_json(tenant_a):
    """clean_conditions raises ValidationError when JSON is an object instead of an array."""
    form_direct = ProjectWorkflowRuleForm(tenant=tenant_a)
    form_direct.cleaned_data = {"conditions": '{"field": "status", "value": "done"}'}
    with pytest.raises(forms.ValidationError, match="Conditions must be a JSON array"):
        form_direct.clean_conditions()


def test_workflowautomation_form_rule_conditions_empty_string_defaults_empty_list(tenant_a):
    """clean_conditions defaults empty string to empty list []."""
    payload = _workflowautomation_rule_payload(conditions="")
    form = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["conditions"] == []


def test_workflowautomation_form_rule_actions_valid_json_string(tenant_a):
    """clean_actions parses a valid JSON array string into a Python list."""
    acts = [{"type": "send_notification", "parameters": {"channel": "slack"}}]
    payload = _workflowautomation_rule_payload(actions=json.dumps(acts))
    form = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["actions"] == acts


def test_workflowautomation_form_rule_actions_invalid_json(tenant_a):
    """clean_actions rejects malformed JSON string."""
    payload = _workflowautomation_rule_payload(actions='[{"type": "send"')
    form = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "actions" in form.errors

    # Direct invocation of clean_actions with string
    form_direct = ProjectWorkflowRuleForm(tenant=tenant_a)
    form_direct.cleaned_data = {"actions": '[{"type": "send"'}
    with pytest.raises(forms.ValidationError, match="Invalid JSON for actions"):
        form_direct.clean_actions()


def test_workflowautomation_form_rule_actions_non_list_json(tenant_a):
    """clean_actions raises ValidationError when JSON is a dict or primitive instead of an array."""
    form_direct = ProjectWorkflowRuleForm(tenant=tenant_a)
    form_direct.cleaned_data = {"actions": '{"type": "notify"}'}
    with pytest.raises(forms.ValidationError, match="Actions must be a JSON array"):
        form_direct.clean_actions()


def test_workflowautomation_form_rule_actions_empty_string_defaults_empty_list(tenant_a):
    """clean_actions defaults empty string to empty list []."""
    payload = _workflowautomation_rule_payload(actions="")
    form = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["actions"] == []


def test_workflowautomation_form_rule_foreign_project_rejected(
    tenant_a,
    workflowautomation_project_b,
):
    """ProjectWorkflowRuleForm rejects project belonging to another tenant."""
    # Layer 1: Form widget scoping
    payload = _workflowautomation_rule_payload(project=str(workflowautomation_project_b.pk))
    form = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors

    # Layer 2: clean() _reject_foreign backstop with widened queryset
    form_widened = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    _workflowautomation_widen(form_widened, "project")
    assert not form_widened.is_valid()
    assert "project" in form_widened.errors
    assert "That record belongs to another workspace." in str(form_widened.errors["project"])


def test_workflowautomation_form_rule_optional_project_allowed(tenant_a):
    """ProjectWorkflowRuleForm allows blank project, representing a tenant-wide rule."""
    payload = _workflowautomation_rule_payload(project="")
    form = ProjectWorkflowRuleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    rule = _workflowautomation_save_form(form, tenant_a)
    assert rule.project is None


def test_workflowautomation_form_rule_test_form_valid():
    """WorkflowRuleTestForm is valid with integer target_id."""
    form = WorkflowRuleTestForm(data={"target_id": 42})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["target_id"] == 42


def test_workflowautomation_form_rule_test_form_required_target_id():
    """WorkflowRuleTestForm requires target_id."""
    form = WorkflowRuleTestForm(data={})
    assert not form.is_valid()
    assert "target_id" in form.errors


def test_workflowautomation_form_rule_test_form_invalid_target_id():
    """WorkflowRuleTestForm rejects non-integer target_id."""
    form = WorkflowRuleTestForm(data={"target_id": "abc"})
    assert not form.is_valid()
    assert "target_id" in form.errors


# ==================================================================================================
# 3. ProjectApprovalGateForm, ApprovalDecisionForm & ApprovalDelegateForm
# ==================================================================================================

def test_workflowautomation_form_approval_gate_valid_create(
    tenant_a,
    workflowautomation_project_a,
    workflowautomation_rule_a,
    admin_user,
    member_user,
):
    """ProjectApprovalGateForm creates instance with all valid fields."""
    payload = _workflowautomation_gate_payload(
        project=workflowautomation_project_a,
        approver=admin_user,
        rule=str(workflowautomation_rule_a.pk),
        delegate_approver=str(member_user.pk),
        escalate_to=str(admin_user.pk),
        threshold_amount="15000.00",
    )
    form = ProjectApprovalGateForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    gate = _workflowautomation_save_form(form, tenant_a, requested_by=admin_user)
    assert gate.pk is not None
    assert gate.project == workflowautomation_project_a
    assert gate.rule == workflowautomation_rule_a
    assert gate.approver == admin_user
    assert gate.delegate_approver == member_user
    assert gate.escalate_to == admin_user
    assert gate.threshold_amount == Decimal("15000.00")


def test_workflowautomation_form_approval_gate_required_fields(tenant_a):
    """ProjectApprovalGateForm requires project, title, target_model, target_id, approver."""
    form = ProjectApprovalGateForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert "title" in form.errors
    assert "target_model" in form.errors
    assert "target_id" in form.errors
    assert "approver" in form.errors


def test_workflowautomation_form_approval_gate_foreign_project_rejected(
    tenant_a,
    workflowautomation_project_b,
    admin_user,
):
    """ProjectApprovalGateForm rejects project belonging to another tenant."""
    payload = _workflowautomation_gate_payload(
        project=workflowautomation_project_b,
        approver=admin_user,
    )
    form = ProjectApprovalGateForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors

    form_widened = ProjectApprovalGateForm(payload, tenant=tenant_a)
    _workflowautomation_widen(form_widened, "project")
    assert not form_widened.is_valid()
    assert "project" in form_widened.errors
    assert "That record belongs to another workspace." in str(form_widened.errors["project"])


def test_workflowautomation_form_approval_gate_foreign_rule_rejected(
    tenant_a,
    workflowautomation_project_a,
    workflowautomation_rule_b,
    admin_user,
):
    """ProjectApprovalGateForm rejects rule belonging to another tenant."""
    payload = _workflowautomation_gate_payload(
        project=workflowautomation_project_a,
        approver=admin_user,
        rule=str(workflowautomation_rule_b.pk),
    )
    form = ProjectApprovalGateForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "rule" in form.errors

    form_widened = ProjectApprovalGateForm(payload, tenant=tenant_a)
    _workflowautomation_widen(form_widened, "rule")
    assert not form_widened.is_valid()
    assert "rule" in form_widened.errors
    assert "That record belongs to another workspace." in str(form_widened.errors["rule"])


def test_workflowautomation_form_approval_gate_optional_fields(
    tenant_a,
    workflowautomation_project_a,
    admin_user,
):
    """ProjectApprovalGateForm accepts minimal required fields with optional fields omitted."""
    payload = {
        "project": str(workflowautomation_project_a.pk),
        "gate_type": "phase_gate",
        "title": "Minimal Approval Gate",
        "target_model": "Milestone",
        "target_id": 5,
        "approver": str(admin_user.pk),
        "timeout_hours": 48,
    }
    form = ProjectApprovalGateForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    gate = _workflowautomation_save_form(form, tenant_a, requested_by=admin_user)
    assert gate.rule is None
    assert gate.description == ""
    assert gate.delegate_approver is None
    assert gate.escalate_to is None
    assert gate.threshold_amount is None


def test_workflowautomation_form_approval_decision_form_valid():
    """ApprovalDecisionForm validates approve and reject choices with notes."""
    form_approve = ApprovalDecisionForm(data={"decision": "approve", "decision_notes": "All checks passed."})
    assert form_approve.is_valid(), form_approve.errors
    assert form_approve.cleaned_data["decision"] == "approve"
    assert form_approve.cleaned_data["decision_notes"] == "All checks passed."

    form_reject = ApprovalDecisionForm(data={"decision": "reject", "decision_notes": ""})
    assert form_reject.is_valid(), form_reject.errors
    assert form_reject.cleaned_data["decision"] == "reject"
    assert form_reject.cleaned_data["decision_notes"] == ""


def test_workflowautomation_form_approval_decision_form_invalid():
    """ApprovalDecisionForm rejects missing or unrecognized decision choices."""
    form_empty = ApprovalDecisionForm(data={})
    assert not form_empty.is_valid()
    assert "decision" in form_empty.errors

    form_invalid = ApprovalDecisionForm(data={"decision": "escalate"})
    assert not form_invalid.is_valid()
    assert "decision" in form_invalid.errors


def test_workflowautomation_form_approval_delegate_form_tenant_scoping(
    tenant_a,
    tenant_b,
    admin_user,
    member_user,
    admin_b,
):
    """ApprovalDelegateForm scopes delegate_approver queryset to the given tenant."""
    form = ApprovalDelegateForm(tenant=tenant_a)
    qs = form.fields["delegate_approver"].queryset

    assert admin_user in qs
    assert member_user in qs
    assert admin_b not in qs

    # Valid selection within tenant
    form_valid = ApprovalDelegateForm(data={"delegate_approver": str(member_user.pk)}, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors

    # Foreign tenant user is rejected
    form_invalid = ApprovalDelegateForm(data={"delegate_approver": str(admin_b.pk)}, tenant=tenant_a)
    assert not form_invalid.is_valid()
    assert "delegate_approver" in form_invalid.errors


def test_workflowautomation_form_approval_delegate_form_inactive_user_excluded(
    tenant_a,
):
    """ApprovalDelegateForm excludes inactive users from delegate_approver queryset."""
    inactive_user = User.objects.create_user(
        username="inactive_dev",
        email="inactive@example.com",
        password="TestPass123!",
        tenant=tenant_a,
        is_active=False,
    )
    form = ApprovalDelegateForm(tenant=tenant_a)
    assert inactive_user not in form.fields["delegate_approver"].queryset

    form_submit = ApprovalDelegateForm(data={"delegate_approver": str(inactive_user.pk)}, tenant=tenant_a)
    assert not form_submit.is_valid()
    assert "delegate_approver" in form_submit.errors


def test_workflowautomation_form_approval_delegate_form_tenant_none(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
):
    """When tenant is None, ApprovalDelegateForm includes active users across tenants."""
    form = ApprovalDelegateForm(tenant=None)
    qs = form.fields["delegate_approver"].queryset
    assert admin_user in qs
    assert admin_b in qs


def test_workflowautomation_form_approval_delegate_form_notes_optional(
    tenant_a,
    admin_user,
):
    """ApprovalDelegateForm allows blank notes."""
    form = ApprovalDelegateForm(data={"delegate_approver": str(admin_user.pk), "notes": ""}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["notes"] == ""


# ==================================================================================================
# 4. RecurringTaskScheduleForm
# ==================================================================================================

def test_workflowautomation_form_recurring_schedule_valid_create(
    tenant_a,
    workflowautomation_project_a,
    admin_user,
):
    """RecurringTaskScheduleForm creates instance with valid payload."""
    payload = _workflowautomation_schedule_payload(
        project=workflowautomation_project_a,
        default_assignee=str(admin_user.pk),
        assignee_strategy="fixed_user",
        effort_hours="4.50",
    )
    form = RecurringTaskScheduleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    schedule = _workflowautomation_save_form(form, tenant_a)
    assert schedule.pk is not None
    assert schedule.project == workflowautomation_project_a
    assert schedule.default_assignee == admin_user
    assert schedule.effort_hours == Decimal("4.50")
    assert schedule.frequency == "weekly"


def test_workflowautomation_form_recurring_schedule_required_fields(tenant_a):
    """RecurringTaskScheduleForm requires title_template, frequency, interval_count,
    priority, assignee_strategy, start_date, next_run_date, project.
    """
    form = RecurringTaskScheduleForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert "title_template" in form.errors
    assert "frequency" in form.errors
    assert "interval_count" in form.errors
    assert "priority" in form.errors
    assert "assignee_strategy" in form.errors
    assert "start_date" in form.errors
    assert "next_run_date" in form.errors


def test_workflowautomation_form_recurring_schedule_end_date_before_start_date_error(
    tenant_a,
    workflowautomation_project_a,
):
    """clean() raises ValidationError when end_date is prior to start_date."""
    today = _workflowautomation_today()
    payload = _workflowautomation_schedule_payload(
        project=workflowautomation_project_a,
        start_date=today.isoformat(),
        end_date=(today - datetime.timedelta(days=1)).isoformat(),
    )
    form = RecurringTaskScheduleForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "end_date" in form.errors
    assert "End date cannot be prior to start date." in str(form.errors["end_date"])


def test_workflowautomation_form_recurring_schedule_end_date_equal_or_after_start_date_valid(
    tenant_a,
    workflowautomation_project_a,
):
    """RecurringTaskScheduleForm accepts end_date >= start_date or end_date omitted."""
    today = _workflowautomation_today()

    # Equal start and end date
    payload_equal = _workflowautomation_schedule_payload(
        project=workflowautomation_project_a,
        start_date=today.isoformat(),
        end_date=today.isoformat(),
    )
    form_equal = RecurringTaskScheduleForm(payload_equal, tenant=tenant_a)
    assert form_equal.is_valid(), form_equal.errors

    # End date after start date
    payload_after = _workflowautomation_schedule_payload(
        project=workflowautomation_project_a,
        start_date=today.isoformat(),
        end_date=(today + datetime.timedelta(days=90)).isoformat(),
    )
    form_after = RecurringTaskScheduleForm(payload_after, tenant=tenant_a)
    assert form_after.is_valid(), form_after.errors

    # End date omitted (None)
    payload_none = _workflowautomation_schedule_payload(
        project=workflowautomation_project_a,
        start_date=today.isoformat(),
        end_date="",
    )
    form_none = RecurringTaskScheduleForm(payload_none, tenant=tenant_a)
    assert form_none.is_valid(), form_none.errors
    sched = _workflowautomation_save_form(form_none, tenant_a)
    assert sched.end_date is None


def test_workflowautomation_form_recurring_schedule_positive_effort_hours(
    tenant_a,
    workflowautomation_project_a,
):
    """RecurringTaskScheduleForm accepts positive effort hours."""
    payload = _workflowautomation_schedule_payload(
        project=workflowautomation_project_a,
        effort_hours="37.50",
    )
    form = RecurringTaskScheduleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["effort_hours"] == Decimal("37.50")


def test_workflowautomation_form_recurring_schedule_zero_effort_hours(
    tenant_a,
    workflowautomation_project_a,
):
    """RecurringTaskScheduleForm accepts zero effort hours (0.00)."""
    payload = _workflowautomation_schedule_payload(
        project=workflowautomation_project_a,
        effort_hours="0.00",
    )
    form = RecurringTaskScheduleForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["effort_hours"] == Decimal("0.00")


def test_workflowautomation_form_recurring_schedule_invalid_effort_hours(
    tenant_a,
    workflowautomation_project_a,
):
    """RecurringTaskScheduleForm rejects non-decimal effort hours."""
    payload = _workflowautomation_schedule_payload(
        project=workflowautomation_project_a,
        effort_hours="three_hours",
    )
    form = RecurringTaskScheduleForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "effort_hours" in form.errors


def test_workflowautomation_form_recurring_schedule_valid_frequency_choices(
    tenant_a,
    workflowautomation_project_a,
):
    """RecurringTaskScheduleForm accepts all defined frequency choices."""
    frequencies = ["daily", "weekly", "biweekly", "monthly", "quarterly", "sprint_cadence"]
    for freq in frequencies:
        payload = _workflowautomation_schedule_payload(
            project=workflowautomation_project_a,
            frequency=freq,
        )
        form = RecurringTaskScheduleForm(payload, tenant=tenant_a)
        assert form.is_valid(), f"Frequency {freq} failed validation: {form.errors}"
        assert form.cleaned_data["frequency"] == freq


def test_workflowautomation_form_recurring_schedule_invalid_frequency(
    tenant_a,
    workflowautomation_project_a,
):
    """RecurringTaskScheduleForm rejects invalid frequency value."""
    payload = _workflowautomation_schedule_payload(
        project=workflowautomation_project_a,
        frequency="annual",
    )
    form = RecurringTaskScheduleForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "frequency" in form.errors


def test_workflowautomation_form_recurring_schedule_foreign_project_rejected(
    tenant_a,
    workflowautomation_project_b,
):
    """RecurringTaskScheduleForm rejects project from another tenant."""
    payload = _workflowautomation_schedule_payload(project=workflowautomation_project_b)
    form = RecurringTaskScheduleForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors

    form_widened = RecurringTaskScheduleForm(payload, tenant=tenant_a)
    _workflowautomation_widen(form_widened, "project")
    assert not form_widened.is_valid()
    assert "project" in form_widened.errors
    assert "That record belongs to another workspace." in str(form_widened.errors["project"])


def test_workflowautomation_form_recurring_schedule_boundary_intervals(
    tenant_a,
    workflowautomation_project_a,
):
    """RecurringTaskScheduleForm accepts boundary interval_count values and rejects non-integers."""
    # interval_count = 1 (minimum reasonable)
    payload_1 = _workflowautomation_schedule_payload(project=workflowautomation_project_a, interval_count=1)
    form_1 = RecurringTaskScheduleForm(payload_1, tenant=tenant_a)
    assert form_1.is_valid(), form_1.errors

    # interval_count = 52
    payload_52 = _workflowautomation_schedule_payload(project=workflowautomation_project_a, interval_count=52)
    form_52 = RecurringTaskScheduleForm(payload_52, tenant=tenant_a)
    assert form_52.is_valid(), form_52.errors

    # Non-integer interval_count
    payload_bad = _workflowautomation_schedule_payload(project=workflowautomation_project_a, interval_count="abc")
    form_bad = RecurringTaskScheduleForm(payload_bad, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "interval_count" in form_bad.errors


# ==================================================================================================
# 5. ProjectWebhookEndpointForm & WebhookTestPingForm
# ==================================================================================================

def test_workflowautomation_form_webhook_endpoint_valid_create(
    tenant_a,
    workflowautomation_project_a,
):
    """ProjectWebhookEndpointForm creates webhook with valid payload."""
    payload = _workflowautomation_webhook_payload(
        project=str(workflowautomation_project_a.pk),
    )
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    webhook = _workflowautomation_save_form(form, tenant_a)
    assert webhook.pk is not None
    assert webhook.name == "Jira Bi-directional Sync"
    assert webhook.project == workflowautomation_project_a
    assert webhook.event_types == ["task.created", "task.updated"]
    assert webhook.custom_headers == {"Authorization": "Bearer secret-token-123"}


def test_workflowautomation_form_webhook_endpoint_required_fields(tenant_a):
    """ProjectWebhookEndpointForm requires name, target_url, event_types."""
    form = ProjectWebhookEndpointForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors
    assert "target_url" in form.errors
    assert "event_types" in form.errors


def test_workflowautomation_form_webhook_endpoint_event_types_requires_at_least_one(tenant_a):
    """clean_event_types requires at least one event type selected."""
    # Empty string
    payload_empty = _workflowautomation_webhook_payload(event_types="")
    form_empty = ProjectWebhookEndpointForm(payload_empty, tenant=tenant_a)
    assert not form_empty.is_valid()
    assert "event_types" in form_empty.errors

    # Empty JSON list
    payload_empty_list = _workflowautomation_webhook_payload(event_types="[]")
    form_empty_list = ProjectWebhookEndpointForm(payload_empty_list, tenant=tenant_a)
    assert not form_empty_list.is_valid()
    assert "event_types" in form_empty_list.errors


def test_workflowautomation_form_webhook_endpoint_event_types_invalid_json(tenant_a):
    """clean_event_types rejects malformed JSON."""
    payload = _workflowautomation_webhook_payload(event_types='["task.created",')
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "event_types" in form.errors

    # Direct clean_event_types validation with invalid JSON string
    form_direct = ProjectWebhookEndpointForm(tenant=tenant_a)
    form_direct.cleaned_data = {"event_types": '["task.created",'}
    with pytest.raises(forms.ValidationError, match="Invalid JSON for event types"):
        form_direct.clean_event_types()


def test_workflowautomation_form_webhook_endpoint_event_types_non_list_json(tenant_a):
    """clean_event_types raises ValidationError when JSON is not a list."""
    payload = _workflowautomation_webhook_payload(event_types='{"event": "task.created"}')
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "event_types" in form.errors
    assert "At least one event type must be selected." in str(form.errors["event_types"])

    # Direct clean_event_types validation with non-list string
    form_direct = ProjectWebhookEndpointForm(tenant=tenant_a)
    form_direct.cleaned_data = {"event_types": '{"event": "task.created"}'}
    with pytest.raises(forms.ValidationError, match="Event types must be a JSON array"):
        form_direct.clean_event_types()


def test_workflowautomation_form_webhook_endpoint_event_types_as_list(tenant_a):
    """clean_event_types accepts a Python list directly."""
    payload = _workflowautomation_webhook_payload(event_types=["task.created"])
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["event_types"] == ["task.created"]


def test_workflowautomation_form_webhook_endpoint_custom_headers_valid_json(tenant_a):
    """clean_custom_headers parses a valid JSON object string into a dictionary."""
    headers = {"X-API-Key": "xyz789", "Content-Type": "application/json"}
    payload = _workflowautomation_webhook_payload(custom_headers=json.dumps(headers))
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["custom_headers"] == headers


def test_workflowautomation_form_webhook_endpoint_custom_headers_invalid_json(tenant_a):
    """clean_custom_headers rejects malformed JSON."""
    payload = _workflowautomation_webhook_payload(custom_headers='{"X-Key":')
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "custom_headers" in form.errors

    # Direct clean_custom_headers validation with invalid JSON string
    form_direct = ProjectWebhookEndpointForm(tenant=tenant_a)
    form_direct.cleaned_data = {"custom_headers": '{"X-Key":'}
    with pytest.raises(forms.ValidationError, match="Invalid JSON for custom headers"):
        form_direct.clean_custom_headers()


def test_workflowautomation_form_webhook_endpoint_custom_headers_non_dict_json(tenant_a):
    """clean_custom_headers raises ValidationError when JSON is not a dict."""
    form_direct = ProjectWebhookEndpointForm(tenant=tenant_a)
    form_direct.cleaned_data = {"custom_headers": '["X-Header-1"]'}
    with pytest.raises(forms.ValidationError, match="Custom headers must be a JSON object"):
        form_direct.clean_custom_headers()


def test_workflowautomation_form_webhook_endpoint_custom_headers_empty_string_defaults_empty_dict(tenant_a):
    """clean_custom_headers defaults empty string to empty dict {}."""
    payload = _workflowautomation_webhook_payload(custom_headers="")
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["custom_headers"] == {}


def test_workflowautomation_form_webhook_endpoint_invalid_url(tenant_a):
    """ProjectWebhookEndpointForm rejects invalid target_url values."""
    payload = _workflowautomation_webhook_payload(target_url="not-a-valid-url")
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_url" in form.errors


def test_workflowautomation_form_webhook_endpoint_foreign_project_rejected(
    tenant_a,
    workflowautomation_project_b,
):
    """ProjectWebhookEndpointForm rejects project belonging to another tenant."""
    payload = _workflowautomation_webhook_payload(project=str(workflowautomation_project_b.pk))
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors

    form_widened = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    _workflowautomation_widen(form_widened, "project")
    assert not form_widened.is_valid()
    assert "project" in form_widened.errors
    assert "That record belongs to another workspace." in str(form_widened.errors["project"])


def test_workflowautomation_form_webhook_endpoint_tenant_wide_allowed(tenant_a):
    """ProjectWebhookEndpointForm allows blank project, representing a tenant-wide webhook."""
    payload = _workflowautomation_webhook_payload(project="")
    form = ProjectWebhookEndpointForm(payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    webhook = _workflowautomation_save_form(form, tenant_a)
    assert webhook.project is None


def test_workflowautomation_form_webhook_test_ping_form_valid():
    """WebhookTestPingForm validates successfully with event_type and custom_payload."""
    form = WebhookTestPingForm(data={"event_type": "milestone.reached", "custom_payload": '{"id": 10}'})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["event_type"] == "milestone.reached"
    assert form.cleaned_data["custom_payload"] == '{"id": 10}'


def test_workflowautomation_form_webhook_test_ping_form_missing_event_type():
    """WebhookTestPingForm requires event_type."""
    form = WebhookTestPingForm(data={"event_type": ""})
    assert not form.is_valid()
    assert "event_type" in form.errors


def test_workflowautomation_form_webhook_test_ping_form_optional_custom_payload():
    """WebhookTestPingForm accepts empty custom_payload."""
    form = WebhookTestPingForm(data={"event_type": "test.ping", "custom_payload": ""})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["custom_payload"] == ""


# ==================================================================================================
# 6. Edit Mode Consistency
# ==================================================================================================

def test_workflowautomation_form_edit_mode_offers_same_fields_as_create(
    tenant_a,
    workflowautomation_rule_a,
    workflowautomation_gate_a,
    workflowautomation_schedule_a,
    workflowautomation_webhook_a,
):
    """Edit forms offer the exact same field set as create forms."""
    pairs = [
        (ProjectWorkflowRuleForm, workflowautomation_rule_a),
        (ProjectApprovalGateForm, workflowautomation_gate_a),
        (RecurringTaskScheduleForm, workflowautomation_schedule_a),
        (ProjectWebhookEndpointForm, workflowautomation_webhook_a),
    ]
    for form_class, instance in pairs:
        create_fields = set(form_class(tenant=tenant_a).fields.keys())
        edit_fields = set(form_class(instance=instance, tenant=tenant_a).fields.keys())
        assert create_fields == edit_fields, (
            f"{form_class.__name__} edit fields mismatch: create={create_fields} vs edit={edit_fields}"
        )
