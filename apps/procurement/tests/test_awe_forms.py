"""Procurement 6.3 Approval Workflow Engine — form tests."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.procurement.forms import (
    ApprovalDecisionForm,
    ApprovalDelegationForm,
    ApprovalRoutingRuleForm,
    EscalationPolicyForm,
)

pytestmark = pytest.mark.django_db


def _payload(**over):
    data = {"commodity": "", "min_total": "", "max_total": "",
            "required_tiers": "2", "escalation_hours": "", "is_active": "on",
            "notes": ""}
    data.update(over)
    return data


def test_rule_form_valid_and_normalises_keyword(tenant_a, org_unit_a):
    form = ApprovalRoutingRuleForm(
        _payload(org_unit=org_unit_a.pk, commodity="  SAFETY  "), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.tenant = tenant_a
    obj.save()
    assert obj.commodity == "safety"


def test_rule_form_refuses_inverted_band(tenant_a):
    form = ApprovalRoutingRuleForm(
        _payload(min_total="500", max_total="100"), tenant=tenant_a)
    assert not form.is_valid() and "max_total" in form.errors


def test_rule_form_rejects_foreign_org(tenant_a, org_unit_b):
    form = ApprovalRoutingRuleForm(
        _payload(org_unit=org_unit_b.pk), tenant=tenant_a)
    assert not form.is_valid()


def test_delegation_form_rules(tenant_a, admin_user, member_user, org_unit_b):
    base = {"delegator": admin_user.pk, "delegate": member_user.pk,
            "valid_from": timezone.localdate(),
            "valid_until": timezone.localdate() + timedelta(days=7),
            "reason": "leave"}
    form = ApprovalDelegationForm(base, tenant=tenant_a)
    assert form.is_valid(), form.errors

    form = ApprovalDelegationForm({**base, "delegate": admin_user.pk}, tenant=tenant_a)
    assert not form.is_valid()

    form = ApprovalDelegationForm({**base, "scope_org_unit": org_unit_b.pk},
                                  tenant=tenant_a)
    assert not form.is_valid()

    form = ApprovalDelegationForm({
        **base, "valid_until": timezone.localdate() - timedelta(days=1)},
        tenant=tenant_a)
    assert not form.is_valid()


def test_decision_form_comment_optional():
    assert ApprovalDecisionForm({"comment": ""}).is_valid()
    # Bound-but-empty is the honest "no data at all" probe — an UNBOUND form's
    # is_valid() is always False by Django contract.
    assert ApprovalDecisionForm({}).is_valid()
    long = ApprovalDecisionForm({"comment": "x" * 2001})
    assert not long.is_valid()


def test_policy_form(tenant_a, member_user, admin_b):
    form = EscalationPolicyForm(
        {"idle_hours": "12", "escalate_to": member_user.pk, "is_active": "on"},
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    # Zero hours = "escalate immediately", legal since review BUG-1 (the engine
    # honours `is not None`) — the same semantics routing rules carry.
    form = EscalationPolicyForm(
        {"idle_hours": "0", "escalate_to": "", "is_active": ""}, tenant=tenant_a)
    assert form.is_valid(), form.errors
    # A backup approver from another workspace is refused.
    form = EscalationPolicyForm(
        {"idle_hours": "12", "escalate_to": admin_b.pk, "is_active": "on"},
        tenant=tenant_a)
    assert not form.is_valid() and "escalate_to" in form.errors
