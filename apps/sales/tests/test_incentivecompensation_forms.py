"""Sub-module 8.10 Incentive Compensation Management -- form test suite.

Covers:
1. System/workflow field exclusion contracts (regression test for C5):
   - CommissionStatementForm.Meta.fields strictly excludes "status", "tenant", "number",
     and auto-aggregated settlement fields.
   - CommissionAdjustmentForm.Meta.fields strictly excludes "status", "tenant", "number",
     and audit/approval tracking fields.
   - CommissionEarningForm.Meta.fields strictly excludes "status", "tenant", "number",
     and waterfall-calculated amount fields.
   - CommissionPlanForm.Meta.fields strictly excludes "tenant", "number", and internal
     JSON schema fields (handled via tiers_json / spif_json).
2. Tenant isolation and scoping of dropdown querysets:
   - All foreign key dropdown querysets are strictly scoped to the bound tenant.
   - Initializing forms with tenant=None defaults FK querysets to .none() (tenant safety).
3. Valid form instantiation, validation, and saves across all 4 forms:
   - CommissionPlanForm: valid flat revenue plan, valid tiered quota plan with JSON brackets,
     and editing existing plans.
   - CommissionEarningForm: valid earning creation with automated waterfall calculations
     and editing existing earnings.
   - CommissionStatementForm: valid settlement statement creation and editing existing statements.
   - CommissionAdjustmentForm: valid manual override adjustment, valid cancellation clawback,
     and editing existing adjustments.
4. Cross-tenant foreign key rejection across all 4 forms:
   - Both default choice validation and widened queryset _reject_foreign checks reject
     Tenant B records (payee, plan, sales_quota, opportunity, sales_order, clawback_parent,
     statement, earning) when submitted to Tenant A forms.
5. CommissionPlanForm error handling on tier brackets (regression test for C6):
   - Submitting tiered or hybrid plans without brackets (empty list or blank) triggers
     clean form validation errors on 'tiers_json' without raising ValueError.
   - Submitting malformed JSON or non-list data triggers ValidationError on 'tiers_json'.
   - Submitting invalid tier configurations (missing keys, non-numeric values, inverted ranges,
     or overlapping brackets) triggers ValidationError remapped to 'tiers_json' without ValueError.
   - Submitting malformed or non-list SPIF JSON triggers ValidationError on 'spif_json'.
6. Date range validations:
   - CommissionStatementForm rejects period_start > period_end.
   - CommissionPlanForm rejects effective_start > effective_end.
7. Business logic guards:
   - CommissionAdjustmentForm rejects positive amounts for cancellation clawbacks.
   - CommissionAdjustmentForm rejects attachment to locked/exported/paid statements.
   - CommissionAdjustmentForm rejects cross-payee mismatches between adjustment payee
     and linked earning or statement.
"""
from datetime import date, timedelta
from decimal import Decimal
import json
import uuid

import pytest
from django.utils import timezone

from apps.accounting.models import Currency
from apps.accounts.models import User
from apps.core.models import Party
from apps.crm.models import Opportunity, SalesQuota
from apps.sales.forms.IncentiveCompensation import (
    CommissionAdjustmentForm,
    CommissionEarningForm,
    CommissionPlanForm,
    CommissionStatementForm,
)
from apps.sales.models import (
    CommissionAdjustment,
    CommissionEarning,
    CommissionPlan,
    CommissionStatement,
)
from apps.sales.tests.conftest import (
    _incentivecompensation_adjustment,
    _incentivecompensation_currency,
    _incentivecompensation_earning,
    _incentivecompensation_plan,
    _incentivecompensation_statement,
)
from apps.scm.models import SalesOrder

pytestmark = pytest.mark.django_db


# ============================================================================
# Helpers (_incentivecompensation_*)
# ============================================================================

def _incentivecompensation_widen(form, field_name, queryset):
    """Widens a form field queryset to allow cross-tenant test values past choice validation."""
    form.fields[field_name].queryset = queryset


def _incentivecompensation_sales_quota(tenant, owner=None, target_amount=Decimal("250000.00"), **overrides):
    """Helper creating a valid CRM SalesQuota for testing."""
    defaults = {
        "tenant": tenant,
        "owner": owner,
        "period_type": "quarterly",
        "period_year": timezone.now().year,
        "period_number": 4,
        "target_amount": target_amount,
    }
    defaults.update(overrides)
    return SalesQuota.objects.create(**defaults)


def _incentivecompensation_opportunity(tenant, name="Enterprise Deal", amount=Decimal("100000.00"), **overrides):
    """Helper creating a valid CRM Opportunity for testing."""
    label = f"{int(timezone.now().timestamp() * 1000) % 100000}-{uuid.uuid4().hex[:4]}"
    defaults = {
        "tenant": tenant,
        "name": f"{name} {label}",
        "stage": "prospecting",
        "forecast_category": "pipeline",
        "amount": amount,
        "probability": 50,
    }
    defaults.update(overrides)
    return Opportunity.objects.create(**defaults)


def _incentivecompensation_sales_order(tenant, customer=None, total=Decimal("50000.00"), **overrides):
    """Helper creating a valid SCM SalesOrder for testing."""
    if customer is None:
        label = f"{int(timezone.now().timestamp() * 1000) % 100000}-{uuid.uuid4().hex[:4]}"
        customer = Party.objects.create(
            tenant=tenant,
            name=f"Customer {label}",
            kind="organization",
        )
    defaults = {
        "tenant": tenant,
        "customer": customer,
        "source_channel": "direct",
        "status": "draft",
        "credit_hold": False,
        "fraud_flag": False,
        "subtotal": total,
        "tax_total": Decimal("0.00"),
        "total": total,
    }
    defaults.update(overrides)
    return SalesOrder.objects.create(**defaults)


def _incentivecompensation_plan_payload(currency, **overrides):
    """Returns a valid default payload dictionary for CommissionPlanForm."""
    uid = uuid.uuid4().hex[:8]
    payload = {
        "name": f"Enterprise Quota Plan {uid}",
        "code": f"cmpl-plan-{uid}",
        "description": "Standard AE baseline compensation plan.",
        "plan_type": "flat_revenue",
        "tier_mode": "not_applicable",
        "status": "active",
        "payout_frequency": "monthly",
        "effective_start": timezone.now().date().isoformat(),
        "effective_end": (timezone.now().date() + timedelta(days=365)).isoformat(),
        "currency": str(currency.pk),
        "target_region": "Americas",
        "base_rate_pct": "8.50",
        "draw_amount": "0.00",
        "is_draw_recoverable": True,
        "clawback_window_days": 90,
        "tax_withholding_pct": "20.00",
        "sales_quota": "",
        "owner": "",
        "tiers_json": "",
        "spif_json": "",
    }
    payload.update(overrides)
    return payload


def _incentivecompensation_earning_payload(plan, payee, currency, **overrides):
    """Returns a valid default payload dictionary for CommissionEarningForm."""
    payload = {
        "plan": str(plan.pk),
        "payee": str(payee.pk),
        "opportunity": "",
        "sales_order": "",
        "credit_type": "direct",
        "split_percentage": "100.00",
        "deal_amount": "50000.00",
        "attainment_pct_at_close": "100.00",
        "applied_rate_pct": "8.50",
        "spif_amount": "0.00",
        "deal_currency": str(currency.pk),
        "exchange_rate": "1.000000",
        "earned_date": timezone.now().date().isoformat(),
        "clawback_parent": "",
    }
    payload.update(overrides)
    return payload


def _incentivecompensation_statement_payload(plan, payee, **overrides):
    """Returns a valid default payload dictionary for CommissionStatementForm."""
    uid = uuid.uuid4().hex[:6]
    today = timezone.now().date()
    p_start = today.replace(day=1)
    payload = {
        "statement_number": f"STMT-{p_start.strftime('%Y%m')}-{payee.pk}-{uid}",
        "payee": str(payee.pk),
        "plan": str(plan.pk),
        "period_start": p_start.isoformat(),
        "period_end": today.isoformat(),
        "draw_advance_paid": "0.00",
        "notes": "Monthly settlement cycle statement.",
    }
    payload.update(overrides)
    return payload


def _incentivecompensation_adjustment_payload(payee, **overrides):
    """Returns a valid default payload dictionary for CommissionAdjustmentForm."""
    payload = {
        "statement": "",
        "earning": "",
        "payee": str(payee.pk),
        "adjustment_type": "manual_override",
        "amount": "250.00",
        "reason": "Discretionary manager performance bonus.",
        "effective_date": timezone.now().date().isoformat(),
    }
    payload.update(overrides)
    return payload


# ============================================================================
# 1. System/Workflow Field Exclusion Tests (Regression Test for C5)
# ============================================================================

def test_incentivecompensation_meta_fields_system_fields_excluded():
    """Verify system/workflow fields are excluded from Meta.fields across all 4 forms.

    C5 regression test: 'status' MUST NOT be authorable by reps or managers via
    CommissionStatementForm, CommissionAdjustmentForm, or CommissionEarningForm.
    Auto-numbering 'number' and multi-tenant scoping 'tenant' must be strictly excluded.
    """
    # 1. CommissionStatementForm
    stmt_fields = set(CommissionStatementForm.Meta.fields)
    assert "status" not in stmt_fields, "status must be excluded from CommissionStatementForm (C5)"
    assert "tenant" not in stmt_fields, "tenant must be excluded from CommissionStatementForm"
    assert "number" not in stmt_fields, "number must be excluded from CommissionStatementForm"
    # Automated calculation & approval fields should also be excluded
    assert "net_payout" not in stmt_fields
    assert "gross_earnings" not in stmt_fields
    assert "approved_by" not in stmt_fields
    assert "payroll_run" not in stmt_fields

    # 2. CommissionAdjustmentForm
    adj_fields = set(CommissionAdjustmentForm.Meta.fields)
    assert "status" not in adj_fields, "status must be excluded from CommissionAdjustmentForm (C5)"
    assert "tenant" not in adj_fields, "tenant must be excluded from CommissionAdjustmentForm"
    assert "number" not in adj_fields, "number must be excluded from CommissionAdjustmentForm"
    assert "requested_by" not in adj_fields
    assert "approved_by" not in adj_fields

    # 3. CommissionEarningForm
    earning_fields = set(CommissionEarningForm.Meta.fields)
    assert "status" not in earning_fields, "status must be excluded from CommissionEarningForm (C5)"
    assert "tenant" not in earning_fields, "tenant must be excluded from CommissionEarningForm"
    assert "number" not in earning_fields, "number must be excluded from CommissionEarningForm"
    assert "credited_volume" not in earning_fields
    assert "base_commission_amount" not in earning_fields
    assert "gross_commission" not in earning_fields
    assert "functional_amount" not in earning_fields
    assert "statement" not in earning_fields

    # 4. CommissionPlanForm
    plan_fields = set(CommissionPlanForm.Meta.fields)
    assert "tenant" not in plan_fields, "tenant must be excluded from CommissionPlanForm"
    assert "number" not in plan_fields, "number must be excluded from CommissionPlanForm"
    assert "tiers_config" not in plan_fields, "tiers_config is managed via tiers_json"
    assert "spif_config" not in plan_fields, "spif_config is managed via spif_json"


# ============================================================================
# 2. Dropdown Queryset Scoping Tests
# ============================================================================

def test_incentivecompensation_form_querysets_tenant_scoped(
    tenant_a,
    tenant_b,
    admin_user,
    member_user,
    admin_b,
    commission_plan_a,
    commission_plan_b,
    commission_earning_a,
    commission_earning_b,
    commission_statement_a,
    commission_statement_b,
    icm_currency,
):
    """Foreign key querysets in all 4 forms must be strictly scoped to request.tenant."""
    quota_a = _incentivecompensation_sales_quota(tenant_a, owner=admin_user)
    quota_b = _incentivecompensation_sales_quota(tenant_b, owner=admin_b)
    opp_a = _incentivecompensation_opportunity(tenant_a)
    opp_b = _incentivecompensation_opportunity(tenant_b)
    so_a = _incentivecompensation_sales_order(tenant_a)
    so_b = _incentivecompensation_sales_order(tenant_b)

    # CommissionPlanForm
    plan_form = CommissionPlanForm(tenant=tenant_a)
    quota_qs = plan_form.fields["sales_quota"].queryset
    owner_qs = plan_form.fields["owner"].queryset
    assert quota_a in quota_qs
    assert quota_b not in quota_qs
    assert admin_user in owner_qs
    assert admin_b not in owner_qs

    # CommissionEarningForm
    earning_form = CommissionEarningForm(tenant=tenant_a)
    assert commission_plan_a in earning_form.fields["plan"].queryset
    assert commission_plan_b not in earning_form.fields["plan"].queryset
    assert member_user in earning_form.fields["payee"].queryset
    assert admin_b not in earning_form.fields["payee"].queryset
    assert opp_a in earning_form.fields["opportunity"].queryset
    assert opp_b not in earning_form.fields["opportunity"].queryset
    assert so_a in earning_form.fields["sales_order"].queryset
    assert so_b not in earning_form.fields["sales_order"].queryset
    assert commission_earning_a in earning_form.fields["clawback_parent"].queryset
    assert commission_earning_b not in earning_form.fields["clawback_parent"].queryset

    # CommissionStatementForm
    stmt_form = CommissionStatementForm(tenant=tenant_a)
    assert member_user in stmt_form.fields["payee"].queryset
    assert admin_b not in stmt_form.fields["payee"].queryset
    assert commission_plan_a in stmt_form.fields["plan"].queryset
    assert commission_plan_b not in stmt_form.fields["plan"].queryset

    # CommissionAdjustmentForm
    adj_form = CommissionAdjustmentForm(tenant=tenant_a)
    assert commission_statement_a in adj_form.fields["statement"].queryset
    assert commission_statement_b not in adj_form.fields["statement"].queryset
    assert commission_earning_a in adj_form.fields["earning"].queryset
    assert commission_earning_b not in adj_form.fields["earning"].queryset
    assert member_user in adj_form.fields["payee"].queryset
    assert admin_b not in adj_form.fields["payee"].queryset

    # None tenant safety: all FK querysets default to empty
    plan_form_none = CommissionPlanForm(tenant=None)
    assert plan_form_none.fields["sales_quota"].queryset.count() == 0
    assert plan_form_none.fields["owner"].queryset.count() == 0

    earning_form_none = CommissionEarningForm(tenant=None)
    assert earning_form_none.fields["plan"].queryset.count() == 0
    assert earning_form_none.fields["payee"].queryset.count() == 0
    assert earning_form_none.fields["opportunity"].queryset.count() == 0
    assert earning_form_none.fields["sales_order"].queryset.count() == 0
    assert earning_form_none.fields["clawback_parent"].queryset.count() == 0

    stmt_form_none = CommissionStatementForm(tenant=None)
    assert stmt_form_none.fields["payee"].queryset.count() == 0
    assert stmt_form_none.fields["plan"].queryset.count() == 0

    adj_form_none = CommissionAdjustmentForm(tenant=None)
    assert adj_form_none.fields["statement"].queryset.count() == 0
    assert adj_form_none.fields["earning"].queryset.count() == 0
    assert adj_form_none.fields["payee"].queryset.count() == 0


# ============================================================================
# 3. CommissionPlanForm Tests
# ============================================================================

def test_incentivecompensation_plan_form_valid_flat_save(tenant_a, icm_currency, admin_user):
    """Submitting valid flat revenue plan saves cleanly with CMPL auto-numbering."""
    quota = _incentivecompensation_sales_quota(tenant_a, owner=admin_user)
    payload = _incentivecompensation_plan_payload(
        currency=icm_currency,
        plan_type="flat_revenue",
        tier_mode="not_applicable",
        base_rate_pct="7.50",
        sales_quota=str(quota.pk),
        owner=str(admin_user.pk),
    )
    form = CommissionPlanForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    plan = form.save()

    assert plan.pk is not None
    assert plan.tenant == tenant_a
    assert plan.number.startswith("CMPL-")
    assert plan.plan_type == "flat_revenue"
    assert plan.tier_mode == "not_applicable"
    assert plan.base_rate_pct == Decimal("7.50")
    assert plan.tiers_config == []
    assert plan.spif_config == []
    assert plan.sales_quota == quota
    assert plan.owner == admin_user


def test_incentivecompensation_plan_form_valid_tiered_save(tenant_a, icm_currency, admin_user):
    """Submitting valid tiered quota plan with JSON brackets saves parsed configuration."""
    tiers = [
        {"min_pct": 0, "max_pct": 100, "rate_pct": 5.0},
        {"min_pct": 100, "max_pct": 150, "rate_pct": 10.0},
        {"min_pct": 150, "max_pct": 200, "rate_pct": 15.0},
    ]
    spifs = [
        {"name": "Q4 New Logo Booster", "bonus_amount": 750.0, "criteria": "new_logo"}
    ]
    payload = _incentivecompensation_plan_payload(
        currency=icm_currency,
        plan_type="tiered_quota",
        tier_mode="incremental",
        base_rate_pct="5.00",
        tiers_json=json.dumps(tiers),
        spif_json=json.dumps(spifs),
    )
    form = CommissionPlanForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    plan = form.save()

    assert plan.pk is not None
    assert plan.plan_type == "tiered_quota"
    assert plan.tier_mode == "incremental"
    assert len(plan.tiers_config) == 3
    assert plan.tiers_config[0]["rate_pct"] == 5.0
    assert len(plan.spif_config) == 1
    assert plan.spif_config[0]["bonus_amount"] == 750.0


def test_incentivecompensation_plan_form_edit_existing(tenant_a, commission_plan_a):
    """Editing existing CommissionPlan preserves and updates JSON configurations."""
    commission_plan_a.tiers_config = [{"min_pct": 0, "max_pct": 100, "rate_pct": 8.0}]
    commission_plan_a.plan_type = "tiered_quota"
    commission_plan_a.tier_mode = "incremental"
    commission_plan_a.save()

    # Initial population test
    form_unbound = CommissionPlanForm(instance=commission_plan_a, tenant=tenant_a)
    assert "8.0" in form_unbound.fields["tiers_json"].initial

    # Bound edit
    updated_tiers = [
        {"min_pct": 0, "max_pct": 100, "rate_pct": 8.0},
        {"min_pct": 100, "max_pct": 125, "rate_pct": 12.0},
    ]
    clean_code = f"plan-edit-{uuid.uuid4().hex[:8]}"
    commission_plan_a.code = clean_code
    commission_plan_a.save()

    payload = _incentivecompensation_plan_payload(
        currency=commission_plan_a.currency,
        name="Updated Tiered AE Plan",
        code=clean_code,
        plan_type="tiered_quota",
        tier_mode="incremental",
        tiers_json=json.dumps(updated_tiers),
    )
    form_bound = CommissionPlanForm(payload, instance=commission_plan_a, tenant=tenant_a)
    assert form_bound.is_valid(), f"Form errors: {form_bound.errors}"
    saved_plan = form_bound.save()

    assert saved_plan.pk == commission_plan_a.pk
    assert saved_plan.name == "Updated Tiered AE Plan"
    assert len(saved_plan.tiers_config) == 2


def test_incentivecompensation_plan_form_date_range_validation(tenant_a, icm_currency):
    """CommissionPlanForm rejects effective_end preceding effective_start."""
    today = timezone.now().date()
    payload = _incentivecompensation_plan_payload(
        currency=icm_currency,
        effective_start=today.isoformat(),
        effective_end=(today - timedelta(days=10)).isoformat(),
    )
    form = CommissionPlanForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "effective_end" in form.errors
    assert "Effective end date cannot precede effective start date." in form.errors["effective_end"]


def test_incentivecompensation_plan_form_tiers_json_invalid_syntax(tenant_a, icm_currency):
    """CommissionPlanForm clean_tiers_json rejects invalid JSON syntax without ValueError."""
    payload = _incentivecompensation_plan_payload(
        currency=icm_currency,
        plan_type="tiered_quota",
        tier_mode="incremental",
        tiers_json='[{"min_pct": 0, "max_pct": 100, invalid_syntax',
    )
    form = CommissionPlanForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "tiers_json" in form.errors
    assert any("Invalid JSON format" in err for err in form.errors["tiers_json"])


def test_incentivecompensation_plan_form_tiers_json_not_a_list(tenant_a, icm_currency):
    """CommissionPlanForm clean_tiers_json rejects non-array JSON objects."""
    payload = _incentivecompensation_plan_payload(
        currency=icm_currency,
        plan_type="tiered_quota",
        tier_mode="incremental",
        tiers_json='{"min_pct": 0, "max_pct": 100, "rate_pct": 8.0}',
    )
    form = CommissionPlanForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "tiers_json" in form.errors
    assert "Tiers configuration must be a JSON array of objects." in form.errors["tiers_json"]


def test_incentivecompensation_plan_form_spif_json_invalid_syntax_and_type(tenant_a, icm_currency):
    """CommissionPlanForm clean_spif_json rejects malformed or non-array SPIF configuration."""
    # Syntax error
    payload_bad_syntax = _incentivecompensation_plan_payload(
        currency=icm_currency,
        spif_json='{"name": "Booster", broken',
    )
    form_syntax = CommissionPlanForm(payload_bad_syntax, tenant=tenant_a)
    assert not form_syntax.is_valid()
    assert "spif_json" in form_syntax.errors
    assert any("Invalid JSON format" in err for err in form_syntax.errors["spif_json"])

    # Non-list error
    payload_dict = _incentivecompensation_plan_payload(
        currency=icm_currency,
        spif_json='{"name": "Booster", "bonus_amount": 500}',
    )
    form_dict = CommissionPlanForm(payload_dict, tenant=tenant_a)
    assert not form_dict.is_valid()
    assert "spif_json" in form_dict.errors
    assert "SPIF configuration must be a JSON array of objects." in form_dict.errors["spif_json"]


def test_incentivecompensation_plan_form_tiered_missing_brackets_c6_regression(tenant_a, icm_currency):
    """Regression test for C6: missing tier brackets cleanly trigger form error without ValueError.

    When plan_type is 'tiered_quota' or 'hybrid', CommissionPlan.clean() raises ValidationError
    on 'tiers_config'. CommissionPlanForm._post_clean() MUST remap this error to 'tiers_json'
    rather than letting Django crash with:
    'ValueError: CommissionPlanForm has no field named tiers_config'.
    """
    cases = [
        ("tiered_quota", "incremental", ""),
        ("tiered_quota", "incremental", "[]"),
        ("hybrid", "incremental", ""),
        ("hybrid", "retroactive", "[]"),
    ]
    for p_type, t_mode, empty_json in cases:
        payload = _incentivecompensation_plan_payload(
            currency=icm_currency,
            plan_type=p_type,
            tier_mode=t_mode,
            tiers_json=empty_json,
        )
        form = CommissionPlanForm(payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "tiers_json" in form.errors, f"Expected tiers_json in form.errors for {p_type}/{empty_json}"
        assert "Tiered or hybrid plans require at least one tier bracket configuration." in form.errors["tiers_json"]


def test_incentivecompensation_plan_form_tiered_invalid_bracket_structure_c6_regression(tenant_a, icm_currency):
    """Regression test for C6: invalid bracket structures cleanly remap to tiers_json without ValueError."""
    bad_bracket_cases = [
        # Missing required key
        ([{"min_pct": 0, "max_pct": 100}], "must contain 'min_pct', 'max_pct', and 'rate_pct'"),
        # Non-numeric values
        ([{"min_pct": "zero", "max_pct": 100, "rate_pct": 8.0}], "values must be numeric"),
        # Inverted range: max <= min
        ([{"min_pct": 100, "max_pct": 50, "rate_pct": 8.0}], "has invalid range: min_pct < max_pct"),
        # Overlapping progression: tier 2 min < tier 1 max
        ([{"min_pct": 0, "max_pct": 100, "rate_pct": 5.0}, {"min_pct": 80, "max_pct": 150, "rate_pct": 10.0}], "overlaps with preceding tier"),
        # Tier element is not a dict
        (["invalid_tier_string"], "must be a JSON dictionary"),
    ]

    for brackets, err_subtext in bad_bracket_cases:
        payload = _incentivecompensation_plan_payload(
            currency=icm_currency,
            plan_type="tiered_quota",
            tier_mode="incremental",
            tiers_json=json.dumps(brackets),
        )
        form = CommissionPlanForm(payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "tiers_json" in form.errors, f"Expected tiers_json in form.errors for {brackets}"
        assert any(err_subtext in err for err in form.errors["tiers_json"])


def test_incentivecompensation_plan_form_cross_tenant_foreign_key_rejection(
    tenant_a,
    tenant_b,
    admin_b,
    icm_currency,
):
    """CommissionPlanForm rejects Tenant B foreign keys (sales_quota, owner)."""
    quota_b = _incentivecompensation_sales_quota(tenant_b, owner=admin_b)

    fk_cases = [
        ("sales_quota", quota_b, SalesQuota.objects.all()),
        ("owner", admin_b, User.objects.all()),
    ]

    for field_name, foreign_obj, widened_qs in fk_cases:
        payload = _incentivecompensation_plan_payload(
            currency=icm_currency,
            **{field_name: str(foreign_obj.pk)},
        )

        # 1. Default scoped queryset rejects at field choice validation
        form_default = CommissionPlanForm(payload, tenant=tenant_a)
        assert not form_default.is_valid()
        assert field_name in form_default.errors
        assert any("Select a valid choice" in err for err in form_default.errors[field_name])

        # 2. Widened queryset passes choice check, cleanly triggers _reject_foreign in clean()
        form_widened = CommissionPlanForm(payload, tenant=tenant_a)
        _incentivecompensation_widen(form_widened, field_name, widened_qs)
        assert not form_widened.is_valid()
        assert field_name in form_widened.errors
        assert "That record belongs to another workspace." in form_widened.errors[field_name]


# ============================================================================
# 4. CommissionEarningForm Tests
# ============================================================================

def test_incentivecompensation_earning_form_valid_create_save(
    tenant_a,
    commission_plan_a,
    member_user,
    icm_currency,
):
    """Submitting valid earning saves cleanly with CER number and waterfall calculation."""
    opp = _incentivecompensation_opportunity(tenant_a, amount=Decimal("60000.00"))
    so = _incentivecompensation_sales_order(tenant_a, total=Decimal("60000.00"))

    payload = _incentivecompensation_earning_payload(
        plan=commission_plan_a,
        payee=member_user,
        currency=icm_currency,
        opportunity=str(opp.pk),
        sales_order=str(so.pk),
        deal_amount="60000.00",
        split_percentage="100.00",
        applied_rate_pct="10.00",
        spif_amount="500.00",
    )
    form = CommissionEarningForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    earning = form.save()

    assert earning.pk is not None
    assert earning.tenant == tenant_a
    assert earning.number.startswith("CER-")
    assert earning.deal_amount == Decimal("60000.00")
    assert earning.credited_volume == Decimal("60000.00")
    assert earning.base_commission_amount == Decimal("6000.00")
    assert earning.gross_commission == Decimal("6500.00")
    assert earning.functional_amount == Decimal("6500.00")
    assert earning.opportunity == opp
    assert earning.sales_order == so


def test_incentivecompensation_earning_form_edit_existing(
    tenant_a,
    commission_earning_a,
    commission_plan_a,
    member_user,
    icm_currency,
):
    """Editing existing CommissionEarning persists changes and re-computes commission."""
    payload = _incentivecompensation_earning_payload(
        plan=commission_plan_a,
        payee=member_user,
        currency=icm_currency,
        deal_amount="80000.00",
        split_percentage="50.00",
        applied_rate_pct="8.00",
        spif_amount="200.00",
    )
    form = CommissionEarningForm(payload, instance=commission_earning_a, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    saved_earning = form.save()

    assert saved_earning.pk == commission_earning_a.pk
    assert saved_earning.deal_amount == Decimal("80000.00")
    assert saved_earning.split_percentage == Decimal("50.00")
    # Credited volume = 80000 * 50% = 40000
    assert saved_earning.credited_volume == Decimal("40000.00")
    # Base = 40000 * 8% = 3200
    assert saved_earning.base_commission_amount == Decimal("3200.00")
    # Gross = 3200 + 200 = 3400
    assert saved_earning.gross_commission == Decimal("3400.00")


def test_incentivecompensation_earning_form_cross_tenant_foreign_key_rejection(
    tenant_a,
    tenant_b,
    commission_plan_a,
    commission_plan_b,
    commission_earning_b,
    admin_b,
    icm_currency,
):
    """CommissionEarningForm rejects Tenant B foreign keys (plan, payee, opportunity, order, clawback)."""
    opp_b = _incentivecompensation_opportunity(tenant_b)
    so_b = _incentivecompensation_sales_order(tenant_b)

    fk_cases = [
        ("plan", commission_plan_b, CommissionPlan.objects.all()),
        ("payee", admin_b, User.objects.all()),
        ("opportunity", opp_b, Opportunity.objects.all()),
        ("sales_order", so_b, SalesOrder.objects.all()),
        ("clawback_parent", commission_earning_b, CommissionEarning.objects.all()),
    ]

    for field_name, foreign_obj, widened_qs in fk_cases:
        # Build valid base payload and inject the foreign FK
        payload = _incentivecompensation_earning_payload(
            plan=commission_plan_a,
            payee=foreign_obj if field_name == "payee" else admin_b,
            currency=icm_currency,
        )
        payload[field_name] = str(foreign_obj.pk)

        # 1. Default choice validation rejects foreign PK
        form_default = CommissionEarningForm(payload, tenant=tenant_a)
        assert not form_default.is_valid()
        assert field_name in form_default.errors
        assert any("Select a valid choice" in err for err in form_default.errors[field_name])

        # 2. Widened queryset passes choice check, triggers _reject_foreign
        form_widened = CommissionEarningForm(payload, tenant=tenant_a)
        _incentivecompensation_widen(form_widened, field_name, widened_qs)
        assert not form_widened.is_valid()
        assert field_name in form_widened.errors
        assert "That record belongs to another workspace." in form_widened.errors[field_name]


# ============================================================================
# 5. CommissionStatementForm Tests
# ============================================================================

def test_incentivecompensation_statement_form_valid_create_save(
    tenant_a,
    commission_plan_a,
    member_user,
):
    """Submitting valid statement data saves cleanly with CST auto-numbering."""
    payload = _incentivecompensation_statement_payload(
        plan=commission_plan_a,
        payee=member_user,
        draw_advance_paid="1500.00",
        notes="Q4 Initial draft settlement.",
    )
    form = CommissionStatementForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    statement = form.save()

    assert statement.pk is not None
    assert statement.tenant == tenant_a
    assert statement.number.startswith("CST-")
    assert statement.plan == commission_plan_a
    assert statement.payee == member_user
    assert statement.draw_advance_paid == Decimal("1500.00")
    assert statement.notes == "Q4 Initial draft settlement."
    assert statement.status == "draft"


def test_incentivecompensation_statement_form_edit_existing(
    tenant_a,
    commission_statement_a,
    commission_plan_a,
    member_user,
):
    """Editing existing CommissionStatement persists updated fields."""
    payload = _incentivecompensation_statement_payload(
        plan=commission_plan_a,
        payee=member_user,
        statement_number=commission_statement_a.statement_number,
        draw_advance_paid="2000.00",
        notes="Updated notes on draft statement.",
    )
    form = CommissionStatementForm(payload, instance=commission_statement_a, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    saved_stmt = form.save()

    assert saved_stmt.pk == commission_statement_a.pk
    assert saved_stmt.draw_advance_paid == Decimal("2000.00")
    assert saved_stmt.notes == "Updated notes on draft statement."


def test_incentivecompensation_statement_form_date_range_validation(
    tenant_a,
    commission_plan_a,
    member_user,
):
    """CommissionStatementForm rejects period_start > period_end."""
    today = timezone.now().date()
    payload = _incentivecompensation_statement_payload(
        plan=commission_plan_a,
        payee=member_user,
        period_start=today.isoformat(),
        period_end=(today - timedelta(days=15)).isoformat(),
    )
    form = CommissionStatementForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "period_end" in form.errors
    assert "Period end date cannot precede period start date." in form.errors["period_end"]


def test_incentivecompensation_statement_form_cross_tenant_foreign_key_rejection(
    tenant_a,
    tenant_b,
    commission_plan_a,
    commission_plan_b,
    admin_b,
):
    """CommissionStatementForm rejects Tenant B foreign keys (payee, plan)."""
    fk_cases = [
        ("payee", admin_b, User.objects.all()),
        ("plan", commission_plan_b, CommissionPlan.objects.all()),
    ]

    for field_name, foreign_obj, widened_qs in fk_cases:
        payload = _incentivecompensation_statement_payload(
            plan=commission_plan_a,
            payee=admin_b if field_name == "payee" else admin_b,
        )
        payload[field_name] = str(foreign_obj.pk)

        # 1. Default choice validation rejects foreign PK
        form_default = CommissionStatementForm(payload, tenant=tenant_a)
        assert not form_default.is_valid()
        assert field_name in form_default.errors
        assert any("Select a valid choice" in err for err in form_default.errors[field_name])

        # 2. Widened queryset triggers _reject_foreign
        form_widened = CommissionStatementForm(payload, tenant=tenant_a)
        _incentivecompensation_widen(form_widened, field_name, widened_qs)
        assert not form_widened.is_valid()
        assert field_name in form_widened.errors
        assert "That record belongs to another workspace." in form_widened.errors[field_name]


# ============================================================================
# 6. CommissionAdjustmentForm Tests
# ============================================================================

def test_incentivecompensation_adjustment_form_valid_create_save(
    tenant_a,
    member_user,
    commission_statement_a,
    commission_earning_a,
):
    """Submitting valid manual override adjustment saves cleanly with CADJ numbering."""
    payload = _incentivecompensation_adjustment_payload(
        payee=member_user,
        statement=str(commission_statement_a.pk),
        earning=str(commission_earning_a.pk),
        adjustment_type="manual_override",
        amount="350.00",
        reason="Discretionary acceleration bonus for Q3 strategic deal.",
    )
    form = CommissionAdjustmentForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    adj = form.save()

    assert adj.pk is not None
    assert adj.tenant == tenant_a
    assert adj.number.startswith("CADJ-")
    assert adj.payee == member_user
    assert adj.statement == commission_statement_a
    assert adj.earning == commission_earning_a
    assert adj.adjustment_type == "manual_override"
    assert adj.amount == Decimal("350.00")
    assert adj.status == "draft"


def test_incentivecompensation_adjustment_form_valid_clawback_save(
    tenant_a,
    member_user,
    commission_statement_a,
    commission_earning_a,
):
    """Submitting valid cancellation clawback with negative amount saves cleanly."""
    payload = _incentivecompensation_adjustment_payload(
        payee=member_user,
        statement=str(commission_statement_a.pk),
        earning=str(commission_earning_a.pk),
        adjustment_type="cancellation_clawback",
        amount="-500.00",
        reason="Customer contract early cancellation chargeback.",
    )
    form = CommissionAdjustmentForm(payload, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    adj = form.save()

    assert adj.pk is not None
    assert adj.adjustment_type == "cancellation_clawback"
    assert adj.amount == Decimal("-500.00")


def test_incentivecompensation_adjustment_form_edit_existing(
    tenant_a,
    commission_adjustment_a,
    member_user,
):
    """Editing existing CommissionAdjustment persists updated amount and reason."""
    payload = _incentivecompensation_adjustment_payload(
        payee=member_user,
        adjustment_type="draw_true_up",
        amount="175.50",
        reason="Updated reconciliation calculation notes.",
    )
    form = CommissionAdjustmentForm(payload, instance=commission_adjustment_a, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    saved_adj = form.save()

    assert saved_adj.pk == commission_adjustment_a.pk
    assert saved_adj.adjustment_type == "draw_true_up"
    assert saved_adj.amount == Decimal("175.50")
    assert saved_adj.reason == "Updated reconciliation calculation notes."


def test_incentivecompensation_adjustment_form_cancellation_clawback_positive_amount_rejected(
    tenant_a,
    member_user,
):
    """CommissionAdjustmentForm rejects positive amount for cancellation_clawback."""
    payload = _incentivecompensation_adjustment_payload(
        payee=member_user,
        adjustment_type="cancellation_clawback",
        amount="500.00",
        reason="Invalid positive clawback.",
    )
    form = CommissionAdjustmentForm(payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "amount" in form.errors
    assert any("Cancellation clawbacks must be recorded with a negative amount" in err for err in form.errors["amount"])


def test_incentivecompensation_adjustment_form_locked_statement_rejected(
    tenant_a,
    member_user,
    commission_statement_a,
):
    """CommissionAdjustmentForm rejects attachment to locked statements."""
    commission_statement_a.status = "locked"
    commission_statement_a.save()

    payload = _incentivecompensation_adjustment_payload(
        payee=member_user,
        statement=str(commission_statement_a.pk),
        amount="100.00",
    )
    # Widen statement queryset so choice check passes and model clean() fires
    form = CommissionAdjustmentForm(payload, tenant=tenant_a)
    _incentivecompensation_widen(form, "statement", CommissionStatement.objects.filter(tenant=tenant_a))

    assert not form.is_valid()
    assert "statement" in form.errors
    assert any("Cannot attach adjustments to a locked or exported statement" in err for err in form.errors["statement"])


def test_incentivecompensation_adjustment_form_cross_payee_mismatch_rejected(
    tenant_a,
    admin_user,
    member_user,
    commission_plan_a,
):
    """CommissionAdjustmentForm rejects mismatch between adjustment payee and earning/statement payee."""
    earning_admin = _incentivecompensation_earning(tenant_a, plan=commission_plan_a, payee=admin_user)
    stmt_admin = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=admin_user,
        statement_number=f"STMT-ADMIN-{uuid.uuid4().hex[:6]}",
    )

    # 1. Submitting adjustment for member_user with earning belonging to admin_user
    payload_earning = _incentivecompensation_adjustment_payload(
        payee=member_user,
        earning=str(earning_admin.pk),
        amount="100.00",
    )
    form_earning = CommissionAdjustmentForm(payload_earning, tenant=tenant_a)
    assert not form_earning.is_valid()
    assert "earning" in form_earning.errors
    assert any("Linked commission earning must belong to the same payee." in err for err in form_earning.errors["earning"])

    # 2. Submitting adjustment for member_user with statement belonging to admin_user
    payload_stmt = _incentivecompensation_adjustment_payload(
        payee=member_user,
        statement=str(stmt_admin.pk),
        amount="100.00",
    )
    form_stmt = CommissionAdjustmentForm(payload_stmt, tenant=tenant_a)
    assert not form_stmt.is_valid()
    assert "statement" in form_stmt.errors
    assert any("Linked statement must belong to the same payee." in err for err in form_stmt.errors["statement"])


def test_incentivecompensation_adjustment_form_cross_tenant_foreign_key_rejection(
    tenant_a,
    tenant_b,
    commission_statement_b,
    commission_earning_b,
    admin_b,
):
    """CommissionAdjustmentForm rejects Tenant B foreign keys (statement, earning, payee)."""
    fk_cases = [
        ("statement", commission_statement_b, CommissionStatement.objects.all()),
        ("earning", commission_earning_b, CommissionEarning.objects.all()),
        ("payee", admin_b, User.objects.all()),
    ]

    for field_name, foreign_obj, widened_qs in fk_cases:
        payload = _incentivecompensation_adjustment_payload(
            payee=admin_b if field_name == "payee" else admin_b,
        )
        payload[field_name] = str(foreign_obj.pk)

        # 1. Default choice validation rejects foreign PK
        form_default = CommissionAdjustmentForm(payload, tenant=tenant_a)
        assert not form_default.is_valid()
        assert field_name in form_default.errors
        assert any("Select a valid choice" in err for err in form_default.errors[field_name])

        # 2. Widened queryset triggers _reject_foreign
        form_widened = CommissionAdjustmentForm(payload, tenant=tenant_a)
        _incentivecompensation_widen(form_widened, field_name, widened_qs)
        assert not form_widened.is_valid()
        assert field_name in form_widened.errors
        assert "That record belongs to another workspace." in form_widened.errors[field_name]
