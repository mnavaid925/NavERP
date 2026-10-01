"""8.7 Territory & Quota Management -- forms lane.

Tests cover:
- Exclusion of frozen evidence fields (L22): assigned_by, last_run_at, status, approval stamps.
- Tenant isolation: foreign key dropdown querysets scoped to request.tenant.
- Tenant=None safety: empty querysets (I1).
- Valid submission and validation errors on forms.
- Rejection of cross-tenant foreign keys.

Names: every test is `test_territoryquotamanagement_*` and every helper `_territoryquotamanagement_*`.
"""
from decimal import Decimal
import json

import pytest
from django.utils import timezone

from apps.sales.forms.TerritoryQuotaManagement.AccountTerritoryAssignments import (
    AccountTerritoryAssignmentForm,
)
from apps.sales.forms.TerritoryQuotaManagement.QuotaPlans import (
    QuotaPlanForm,
)
from apps.sales.forms.TerritoryQuotaManagement.TerritoryMembers import (
    TerritoryMemberForm,
)
from apps.sales.forms.TerritoryQuotaManagement.TerritoryRules import (
    TerritoryRuleForm,
)
from apps.sales.tests.conftest import (
    _territoryquotamanagement_account,
    _territoryquotamanagement_crm_quota,
    _territoryquotamanagement_crm_territory,
    _territoryquotamanagement_rule,
    _salesforecasting_period,
)

pytestmark = pytest.mark.django_db

_FROZEN_EVIDENCE_EXCLUDED = {
    TerritoryRuleForm: {"last_run_at", "last_run_matched_count", "tenant", "number"},
    AccountTerritoryAssignmentForm: {"assigned_by", "tenant", "number"},
    TerritoryMemberForm: {"tenant", "number"},
    QuotaPlanForm: {
        "status", "submitted_by", "approved_by", "submitted_at", "approved_at",
        "calculated_at", "tenant", "number",
    },
}


def test_territoryquotamanagement_forms_exclude_frozen_evidence():
    """Frozen evidence fields must never appear on user-facing forms (L22)."""
    for form_cls, excluded_fields in _FROZEN_EVIDENCE_EXCLUDED.items():
        form_fields = set(form_cls.Meta.fields if hasattr(form_cls, "Meta") and hasattr(form_cls.Meta, "fields") else [])
        for fld in excluded_fields:
            assert fld not in form_fields, f"Field {fld!r} must be excluded from {form_cls.__name__}"


def test_territoryquotamanagement_forms_tenant_isolation_on_none():
    """When tenant=None, foreign key fields must default to empty querysets (I1)."""
    rule_form = TerritoryRuleForm(tenant=None)
    assert rule_form.fields["target_territory"].queryset.count() == 0

    assign_form = AccountTerritoryAssignmentForm(tenant=None)
    assert assign_form.fields["account"].queryset.count() == 0
    assert assign_form.fields["territory"].queryset.count() == 0
    assert assign_form.fields["owner"].queryset.count() == 0

    member_form = TerritoryMemberForm(tenant=None)
    assert member_form.fields["territory"].queryset.count() == 0
    assert member_form.fields["user"].queryset.count() == 0

    plan_form = QuotaPlanForm(tenant=None)
    assert plan_form.fields["quota_ref"].queryset.count() == 0
    assert plan_form.fields["forecast_period"].queryset.count() == 0
    assert plan_form.fields["territory"].queryset.count() == 0
    assert plan_form.fields["owner"].queryset.count() == 0


def test_territoryquotamanagement_territory_rule_form_valid(tqm_tenant_a, tqm_territory):
    """Valid data on TerritoryRuleForm successfully saves a rule."""
    form_data = {
        "name": "Midwest Auto Rule",
        "segment_type": "geographic",
        "match_mode": "all",
        "alignment_type": "primary",
        "assignment_scope": "exact",
        "target_territory": tqm_territory.pk,
        "priority": 100,
        "is_active": True,
        "conditions": json.dumps([{"field": "state", "operator": "eq", "value": "IL"}]),
        "effective_from": timezone.localdate(),
    }
    form = TerritoryRuleForm(form_data, tenant=tqm_tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    rule = form.save(commit=False)
    rule.tenant = tqm_tenant_a
    rule.save()
    assert rule.pk is not None


def test_territoryquotamanagement_territory_rule_form_named_account_disable(tqm_tenant_a, tqm_territory):
    """Conditions are disabled on named_account rules in TerritoryRuleForm."""
    form = TerritoryRuleForm(tenant=tqm_tenant_a, initial={"segment_type": "named_account"})
    # Bound form with named_account ignores/clears conditions
    bound = TerritoryRuleForm(
        {
            "name": "Named Account Rule",
            "segment_type": "named_account",
            "target_territory": tqm_territory.pk,
            "match_mode": "all",
            "alignment_type": "primary",
            "assignment_scope": "exact",
            "priority": 100,
            "effective_from": timezone.localdate(),
            "conditions": '[{"field": "state", "operator": "eq", "value": "IL"}]',
        },
        tenant=tqm_tenant_a,
    )
    # Model clean rejects named_account with conditions
    assert not bound.is_valid()
    assert "conditions" in bound.errors or "__all__" in bound.errors


def test_territoryquotamanagement_assignment_form_valid(tqm_tenant_a, tqm_account_a, tqm_territory, tqm_admin_a):
    """AccountTerritoryAssignmentForm saves valid assignment."""
    data = {
        "account": tqm_account_a.pk,
        "territory": tqm_territory.pk,
        "alignment_type": "primary",
        "assignment_source": "manual",
        "owner": tqm_admin_a.pk,
        "effective_from": timezone.localdate(),
    }
    form = AccountTerritoryAssignmentForm(data, tenant=tqm_tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    assignment = form.save(commit=False)
    assignment.tenant = tqm_tenant_a
    assignment.save()
    assert assignment.pk is not None


def test_territoryquotamanagement_assignment_form_cross_tenant_rejected(
    tqm_tenant_a, tqm_tenant_b, tqm_account_a, tqm_territory
):
    """Attempting to assign a territory from Tenant B in Tenant A's form fails validation."""
    terr_b = _territoryquotamanagement_crm_territory(tqm_tenant_b, name="Foreign Territory")
    data = {
        "account": tqm_account_a.pk,
        "territory": terr_b.pk,
        "alignment_type": "primary",
        "assignment_source": "manual",
        "effective_from": timezone.localdate(),
    }
    form = AccountTerritoryAssignmentForm(data, tenant=tqm_tenant_a)
    assert not form.is_valid()
    assert "territory" in form.errors


def test_territoryquotamanagement_member_form_valid(tqm_tenant_a, tqm_territory, tqm_admin_a):
    """TerritoryMemberForm successfully creates an AE direct member."""
    data = {
        "territory": tqm_territory.pk,
        "user": tqm_admin_a.pk,
        "member_role": "ae",
        "assignment_type": "direct",
        "is_primary": True,
        "coverage_split_pct": "100.00",
        "effective_from": timezone.localdate(),
    }
    form = TerritoryMemberForm(data, tenant=tqm_tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    member = form.save(commit=False)
    member.tenant = tqm_tenant_a
    member.save()
    assert member.pk is not None


def test_territoryquotamanagement_quota_plan_form_valid(
    tqm_tenant_a, tqm_territory, tqm_quota, tqm_admin_a
):
    """QuotaPlanForm validates top-down derivation proposal."""
    period = _salesforecasting_period(tqm_tenant_a)
    data = {
        "quota_ref": tqm_quota.pk,
        "forecast_period": period.pk,
        "territory": tqm_territory.pk,
        "owner": tqm_admin_a.pk,
        "method": "top_down",
        "allocation_basis": "historical_revenue",
        "baseline_source": "previous_year",
        "growth_target_pct": "10.00",
        "attrition_relief_pct": "2.00",
        "target_type": "revenue",
        "phasing": "equal",
    }
    form = QuotaPlanForm(data, tenant=tqm_tenant_a)
    assert form.is_valid(), f"Errors: {form.errors}"
    plan = form.save(commit=False)
    plan.tenant = tqm_tenant_a
    plan.save()
    assert plan.pk is not None
