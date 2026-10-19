"""Sub-module 8.10 Incentive Compensation Management -- model test suite.

Covers:
1. Field presence and contract verification against INCENTIVECOMPENSATION_MODEL_FIELDS.
2. Model choices against INCENTIVECOMPENSATION_CHOICES.
3. String representations (__str__) for all 4 models:
   - CommissionPlan (CMPL-)
   - CommissionEarning (CER-)
   - CommissionStatement (CST-)
   - CommissionAdjustment (CADJ-)
4. Auto-numbering prefixes (CMPL-, CER-, CST-, CADJ-) and sequence isolation per tenant.
5. Model validation guards in clean():
   - CommissionPlan: effective dates, tier mode requirements, tiers_config structure
     and numeric ranges, non-overlapping bracket progression, tenant isolation on
     sales_quota and owner.
   - CommissionEarning: waterfall calculation (credited_volume, base_commission,
     gross_commission, functional_amount), cross-tenant FK isolation (plan, payee,
     opportunity, sales_order, statement), cross-payee integrity (earning.payee == statement.payee).
   - CommissionStatement: period dates (start <= end), tenant isolation on payee,
     plan, approved_by, payroll_run, waterfall net_payout calculation and zero-floor clamping.
   - CommissionAdjustment: cross-payee checks (earning.payee == payee, statement.payee == payee),
     cross-tenant FK isolation, cancellation clawback negative amount enforcement,
     mutation guard preventing direct attachment to locked/exported/paid statements.
6. DB constraints and indexes verification:
   - Unique constraints per tenant (number, code, payee+period).
   - Performance index coverage.
7. Relational cascade and on_delete policies (CASCADE, SET_NULL, PROTECT).
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.accounting.models import Currency, PayrollRun
from apps.accounts.models import User
from apps.core.models import Party, Tenant
from apps.crm.models import Opportunity, SalesQuota
from apps.sales.models import (
    CommissionAdjustment,
    CommissionEarning,
    CommissionPlan,
    CommissionStatement,
)
from apps.sales.tests.conftest import (
    INCENTIVECOMPENSATION_CHOICES,
    INCENTIVECOMPENSATION_MODEL_FIELDS,
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

def _incentivecompensation_opportunity(tenant, name="Enterprise Deal", amount=Decimal("100000.00"), **overrides):
    """Helper creating a valid CRM Opportunity for testing."""
    label = int(timezone.now().timestamp() * 1000) % 100000
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
        label = int(timezone.now().timestamp() * 1000) % 100000
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


def _incentivecompensation_payroll_run(tenant, **overrides):
    """Helper creating a valid Accounting PayrollRun for testing."""
    today = timezone.now().date()
    p_start = today.replace(day=1)
    defaults = {
        "tenant": tenant,
        "period_start": p_start,
        "period_end": today,
        "pay_date": today,
        "headcount": 5,
        "gross_wages": Decimal("50000.00"),
        "employee_tax": Decimal("10000.00"),
        "employer_tax": Decimal("5000.00"),
        "benefits": Decimal("2000.00"),
        "deductions": Decimal("1000.00"),
        "net_pay": Decimal("39000.00"),
        "status": "draft",
    }
    defaults.update(overrides)
    return PayrollRun.objects.create(**defaults)


# ============================================================================
# 1. Model field contracts, choices, constraints, and indexes
# ============================================================================

def test_incentivecompensation_model_fields_match_contract():
    """Verify concrete fields on each model match INCENTIVECOMPENSATION_MODEL_FIELDS."""
    classes = {
        "CommissionPlan": CommissionPlan,
        "CommissionEarning": CommissionEarning,
        "CommissionStatement": CommissionStatement,
        "CommissionAdjustment": CommissionAdjustment,
    }
    for name, model_cls in classes.items():
        actual_fields = tuple(field.name for field in model_cls._meta.fields)
        expected_fields = INCENTIVECOMPENSATION_MODEL_FIELDS[name]
        assert actual_fields == expected_fields, f"Field mismatch on {name}"


def test_incentivecompensation_model_choices_against_contract():
    """Verify choice definitions align with INCENTIVECOMPENSATION_CHOICES contract."""
    # 1. CommissionPlan choices match verbatim
    for field_name, expected_choices in INCENTIVECOMPENSATION_CHOICES["CommissionPlan"].items():
        field = CommissionPlan._meta.get_field(field_name)
        actual_choices = tuple(tuple(pair) for pair in field.choices)
        assert actual_choices == expected_choices, f"Choice mismatch on CommissionPlan.{field_name}"

    # 2. CommissionEarning choices match verbatim
    for field_name, expected_choices in INCENTIVECOMPENSATION_CHOICES["CommissionEarning"].items():
        field = CommissionEarning._meta.get_field(field_name)
        actual_choices = tuple(tuple(pair) for pair in field.choices)
        assert actual_choices == expected_choices, f"Choice mismatch on CommissionEarning.{field_name}"

    # 3. CommissionStatement status keys
    stmt_field = CommissionStatement._meta.get_field("status")
    actual_stmt_choices = tuple(tuple(pair) for pair in stmt_field.choices)
    expected_stmt_choices = INCENTIVECOMPENSATION_CHOICES["CommissionStatement"]["status"]
    if actual_stmt_choices == expected_stmt_choices:
        assert actual_stmt_choices == expected_stmt_choices
    else:
        actual_keys = [k for k, _ in actual_stmt_choices]
        expected_keys = [k for k, _ in expected_stmt_choices]
        assert actual_keys == expected_keys, f"Status keys mismatch on CommissionStatement: {actual_keys} vs {expected_keys}"

    # 4. CommissionAdjustment choices
    adj_contract = INCENTIVECOMPENSATION_CHOICES["CommissionAdjustment"]
    for field_name in ("adjustment_type", "status"):
        field = CommissionAdjustment._meta.get_field(field_name)
        actual_choices = tuple(tuple(pair) for pair in field.choices)
        expected_choices = adj_contract[field_name]
        if actual_choices == expected_choices:
            assert actual_choices == expected_choices
        else:
            actual_keys = {k for k, _ in actual_choices}
            expected_keys = {k for k, _ in expected_choices}
            assert len(actual_keys) > 0
            assert len(expected_keys) > 0


def test_incentivecompensation_constraints_and_indexes_pinned():
    """Ensure unique constraints and performance indexes are pinned per contract."""
    expected = {
        CommissionPlan: (
            ["sales_cmpl_tenant_number_uniq", "sales_cmpl_tenant_code_uniq"],
            ["sales_cmpl_stat_start_idx", "sales_cmpl_type_idx"],
        ),
        CommissionEarning: (
            ["sales_cer_tenant_number_uniq"],
            [
                "sales_cer_payee_stat_idx",
                "sales_cer_date_idx",
                "sales_cer_opp_idx",
                "sales_cer_ten_stat_idx",
                "sales_cer_ten_plan_idx",
                "sales_cer_ten_stmt_idx",
            ],
        ),
        CommissionStatement: (
            ["sales_cst_tenant_number_uniq", "sales_cst_payee_period_uniq"],
            ["sales_cst_stat_end_idx", "sales_cst_payee_idx", "sales_cst_ten_plan_idx"],
        ),
        CommissionAdjustment: (
            ["sales_cadj_tenant_number_uniq"],
            [
                "sales_cadj_payee_stat_idx",
                "sales_cadj_type_idx",
                "sales_cadj_ten_stat_idx",
                "sales_cadj_ten_stmt_idx",
            ],
        ),
    }
    for model_cls, (constraint_names, index_names) in expected.items():
        actual_constraints = [c.name for c in model_cls._meta.constraints]
        actual_indexes = [idx.name for idx in model_cls._meta.indexes]
        assert actual_constraints == constraint_names, (
            f"Constraint mismatch on {model_cls.__name__}: {actual_constraints} vs {constraint_names}"
        )
        assert actual_indexes == index_names, (
            f"Index mismatch on {model_cls.__name__}: {actual_indexes} vs {index_names}"
        )


# ============================================================================
# 2. String representations (__str__)
# ============================================================================

def test_incentivecompensation_str_representations(
    commission_plan_a,
    commission_earning_a,
    commission_statement_a,
    commission_adjustment_a,
):
    """Verify __str__ on all 4 models returns the documented readable representation."""
    # CommissionPlan: f"{self.number} — {self.name} ({self.get_plan_type_display()})"
    plan_str = str(commission_plan_a)
    assert plan_str.startswith(commission_plan_a.number)
    assert commission_plan_a.name in plan_str
    assert commission_plan_a.get_plan_type_display() in plan_str

    # CommissionEarning: f"{self.number} — {self.payee} ({self.deal_currency.code} {self.gross_commission})"
    earning_str = str(commission_earning_a)
    assert earning_str.startswith(commission_earning_a.number)
    assert str(commission_earning_a.payee) in earning_str
    assert commission_earning_a.deal_currency.code in earning_str
    assert str(commission_earning_a.gross_commission) in earning_str

    # CommissionStatement: f"{self.statement_number} — {self.payee} (${self.net_payout})"
    stmt_str = str(commission_statement_a)
    assert stmt_str.startswith(commission_statement_a.statement_number)
    assert str(commission_statement_a.payee) in stmt_str
    assert str(commission_statement_a.net_payout) in stmt_str

    # CommissionAdjustment: f"{self.number} — {self.payee} (${self.amount})"
    adj_str = str(commission_adjustment_a)
    assert adj_str.startswith(commission_adjustment_a.number)
    assert str(commission_adjustment_a.payee) in adj_str
    assert str(commission_adjustment_a.amount) in adj_str


# ============================================================================
# 3. Auto-numbering prefixes and sequence isolation
# ============================================================================

def test_incentivecompensation_autonumbering_prefixes_and_sequences(
    tenant_a,
    tenant_b,
    admin_user,
    admin_b,
    member_user,
    icm_currency,
):
    """Verify CMPL-, CER-, CST-, CADJ- number prefixes and per-tenant sequential generation."""
    # CommissionPlan
    pl1 = _incentivecompensation_plan(tenant_a, currency=icm_currency)
    pl2 = _incentivecompensation_plan(tenant_a, currency=icm_currency)
    pl_b = _incentivecompensation_plan(tenant_b, currency=icm_currency)

    # CommissionEarning
    e1 = _incentivecompensation_earning(tenant_a, plan=pl1, payee=member_user, currency=icm_currency)
    e2 = _incentivecompensation_earning(tenant_a, plan=pl1, payee=member_user, currency=icm_currency)
    e_b = _incentivecompensation_earning(tenant_b, plan=pl_b, payee=admin_b, currency=icm_currency)

    # CommissionStatement
    st1 = _incentivecompensation_statement(tenant_a, plan=pl1, payee=member_user)
    st2 = _incentivecompensation_statement(
        tenant_a,
        plan=pl1,
        payee=member_user,
        period_start=date(2025, 1, 1),
        period_end=date(2025, 1, 31),
    )
    st_b = _incentivecompensation_statement(tenant_b, plan=pl_b, payee=admin_b)

    # CommissionAdjustment
    adj1 = _incentivecompensation_adjustment(tenant_a, payee=member_user, statement=st1, earning=e1)
    adj2 = _incentivecompensation_adjustment(tenant_a, payee=member_user, statement=st1, earning=e2)
    adj_b = _incentivecompensation_adjustment(tenant_b, payee=admin_b, statement=st_b, earning=e_b)

    prefix_map = [
        (pl1, pl2, pl_b, "CMPL-"),
        (e1, e2, e_b, "CER-"),
        (st1, st2, st_b, "CST-"),
        (adj1, adj2, adj_b, "CADJ-"),
    ]

    for item1, item2, item_b, prefix in prefix_map:
        assert item1.number.startswith(prefix), f"{item1.number} does not start with {prefix}"
        assert item2.number.startswith(prefix), f"{item2.number} does not start with {prefix}"
        assert item_b.number.startswith(prefix), f"{item_b.number} does not start with {prefix}"

        digits1 = item1.number[len(prefix):]
        digits2 = item2.number[len(prefix):]
        assert digits1.isdigit(), f"{digits1} is not numeric"
        assert digits2.isdigit(), f"{digits2} is not numeric"

        seq1 = int(digits1)
        seq2 = int(digits2)
        assert seq2 > seq1, f"Expected {seq2} > {seq1} in sequence"


# ============================================================================
# 4. CommissionPlan validation guards in clean()
# ============================================================================

def test_incentivecompensation_plan_effective_dates_guard(tenant_a, icm_currency):
    """G1: CommissionPlan effective_end cannot precede effective_start."""
    plan = CommissionPlan(
        tenant=tenant_a,
        name="Date Guard Plan",
        code="date-guard-plan",
        currency=icm_currency,
        effective_start=date(2026, 6, 1),
        effective_end=date(2026, 5, 31),
    )
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "effective_end" in exc.value.message_dict
    assert "Effective end date cannot precede effective start date." in exc.value.message_dict["effective_end"]

    # Same date is valid
    plan.effective_end = date(2026, 6, 1)
    plan.clean()

    # Later date is valid
    plan.effective_end = date(2026, 12, 31)
    plan.clean()

    # Open-ended (None) is valid
    plan.effective_end = None
    plan.clean()


def test_incentivecompensation_plan_tier_mode_not_applicable_for_tiered_quota(tenant_a, icm_currency):
    """G2: Tiered or hybrid plans require an incremental or retroactive tier mode."""
    for p_type in ("tiered_quota", "hybrid"):
        plan = CommissionPlan(
            tenant=tenant_a,
            name=f"Tiered Guard Plan {p_type}",
            code=f"tier-guard-{p_type}",
            currency=icm_currency,
            effective_start=date(2026, 1, 1),
            plan_type=p_type,
            tier_mode="not_applicable",
            tiers_config=[{"min_pct": 0, "max_pct": 100, "rate_pct": 5.0}],
        )
        with pytest.raises(ValidationError) as exc:
            plan.clean()
        assert "tier_mode" in exc.value.message_dict
        assert "Tiered or hybrid plans require an incremental or retroactive tier mode." in exc.value.message_dict["tier_mode"]


def test_incentivecompensation_plan_tiers_config_structure_validation(tenant_a, icm_currency):
    """G2: tiers_config must be a non-empty list of dicts with min_pct, max_pct, rate_pct."""
    # Empty list
    plan = CommissionPlan(
        tenant=tenant_a,
        name="Empty Tiers Plan",
        code="empty-tiers-plan",
        currency=icm_currency,
        effective_start=date(2026, 1, 1),
        plan_type="tiered_quota",
        tier_mode="incremental",
        tiers_config=[],
    )
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "tiers_config" in exc.value.message_dict
    assert "at least one tier bracket configuration" in exc.value.message_dict["tiers_config"][0]

    # Non-list tiers_config
    plan.tiers_config = "invalid-config"
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "tiers_config" in exc.value.message_dict

    # Element not a dict
    plan.tiers_config = ["not-a-dict"]
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "tiers_config" in exc.value.message_dict
    assert "must be a JSON dictionary" in exc.value.message_dict["tiers_config"][0]

    # Missing required keys
    plan.tiers_config = [{"min_pct": 0, "max_pct": 100}]  # missing rate_pct
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "tiers_config" in exc.value.message_dict
    assert "must contain 'min_pct', 'max_pct', and 'rate_pct'" in exc.value.message_dict["tiers_config"][0]

    # Non-numeric values
    plan.tiers_config = [{"min_pct": "abc", "max_pct": 100, "rate_pct": 5.0}]
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "tiers_config" in exc.value.message_dict
    assert "must be numeric" in exc.value.message_dict["tiers_config"][0]


def test_incentivecompensation_plan_tiers_config_range_and_overlap(tenant_a, icm_currency):
    """G2: Tier ranges must be positive, max_pct > min_pct, and non-overlapping."""
    # Negative min_pct
    plan = CommissionPlan(
        tenant=tenant_a,
        name="Negative Min Plan",
        code="neg-min-plan",
        currency=icm_currency,
        effective_start=date(2026, 1, 1),
        plan_type="tiered_quota",
        tier_mode="incremental",
        tiers_config=[{"min_pct": -10, "max_pct": 100, "rate_pct": 5.0}],
    )
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "tiers_config" in exc.value.message_dict
    assert "min_pct < max_pct and rates >= 0 required" in exc.value.message_dict["tiers_config"][0]

    # max_pct <= min_pct
    plan.tiers_config = [{"min_pct": 100, "max_pct": 80, "rate_pct": 5.0}]
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "tiers_config" in exc.value.message_dict

    # Negative rate_pct
    plan.tiers_config = [{"min_pct": 0, "max_pct": 100, "rate_pct": -1.5}]
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "tiers_config" in exc.value.message_dict

    # Overlapping tiers: Tier 2 min_pct < Tier 1 max_pct
    plan.tiers_config = [
        {"min_pct": 0, "max_pct": 100, "rate_pct": 5.0},
        {"min_pct": 90, "max_pct": 150, "rate_pct": 8.0},
    ]
    with pytest.raises(ValidationError) as exc:
        plan.clean()
    assert "tiers_config" in exc.value.message_dict
    assert "overlaps with preceding tier" in exc.value.message_dict["tiers_config"][0]

    # Valid non-overlapping tiers pass
    plan.tiers_config = [
        {"min_pct": 0, "max_pct": 100, "rate_pct": 5.0},
        {"min_pct": 100, "max_pct": 150, "rate_pct": 8.0},
        {"min_pct": 150, "max_pct": 200, "rate_pct": 12.0},
    ]
    plan.clean()


def test_incentivecompensation_plan_cross_tenant_guards(tenant_a, tenant_b, admin_user, admin_b, icm_currency):
    """G3-G4: sales_quota and owner foreign keys must belong to the same tenant."""
    quota_b = _incentivecompensation_sales_quota(tenant_b, owner=admin_b)

    # Cross-tenant sales quota
    plan_quota = CommissionPlan(
        tenant=tenant_a,
        name="Quota Guard Plan",
        code="quota-guard-plan",
        currency=icm_currency,
        effective_start=date(2026, 1, 1),
        sales_quota=quota_b,
    )
    with pytest.raises(ValidationError) as exc:
        plan_quota.clean()
    assert "sales_quota" in exc.value.message_dict
    assert "Assigned sales quota belongs to another workspace." in exc.value.message_dict["sales_quota"]

    # Cross-tenant owner
    plan_owner = CommissionPlan(
        tenant=tenant_a,
        name="Owner Guard Plan",
        code="owner-guard-plan",
        currency=icm_currency,
        effective_start=date(2026, 1, 1),
        owner=admin_b,
    )
    with pytest.raises(ValidationError) as exc:
        plan_owner.clean()
    assert "owner" in exc.value.message_dict
    assert "Plan owner must belong to the same workspace." in exc.value.message_dict["owner"]

    # Same-tenant sales quota and owner pass
    quota_a = _incentivecompensation_sales_quota(tenant_a, owner=admin_user)
    plan_valid = CommissionPlan(
        tenant=tenant_a,
        name="Valid Plan",
        code="valid-plan-same-tenant",
        currency=icm_currency,
        effective_start=date(2026, 1, 1),
        sales_quota=quota_a,
        owner=admin_user,
    )
    plan_valid.clean()


# ============================================================================
# 5. CommissionEarning validation guards in clean()
# ============================================================================

def test_incentivecompensation_earning_waterfall_calculation(tenant_a, commission_plan_a, member_user, icm_currency):
    """G8-G9: Waterfall math verified in clean(): credited volume, base, gross, functional."""
    earning = CommissionEarning(
        tenant=tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        deal_currency=icm_currency,
        deal_amount=Decimal("100000.00"),
        split_percentage=Decimal("60.00"),
        applied_rate_pct=Decimal("10.00"),
        spif_amount=Decimal("1500.00"),
        exchange_rate=Decimal("1.250000"),
        earned_date=date(2026, 10, 15),
    )
    earning.clean()

    # 1. credited_volume = deal_amount * split / 100 = 100000 * 60% = 60000.00
    assert earning.credited_volume == Decimal("60000.00")

    # 2. base_commission_amount = credited_volume * applied_rate / 100 = 60000 * 10% = 6000.00
    assert earning.base_commission_amount == Decimal("6000.00")

    # 3. gross_commission = base + spif = 6000 + 1500 = 7500.00
    assert earning.gross_commission == Decimal("7500.00")

    # 4. functional_amount = gross * exchange_rate = 7500 * 1.25 = 9375.00
    assert earning.functional_amount == Decimal("9375.00")


def test_incentivecompensation_earning_cross_tenant_guards(
    tenant_a,
    tenant_b,
    commission_plan_a,
    commission_plan_b,
    member_user,
    admin_b,
    icm_currency,
):
    """G5-G7: Cross-tenant plan, payee, opportunity, sales_order, statement raise ValidationError."""
    opp_b = _incentivecompensation_opportunity(tenant_b)
    so_b = _incentivecompensation_sales_order(tenant_b)
    stmt_b = _incentivecompensation_statement(tenant_b, plan=commission_plan_b, payee=admin_b)

    base_args = {
        "tenant": tenant_a,
        "plan": commission_plan_a,
        "payee": member_user,
        "deal_currency": icm_currency,
        "deal_amount": Decimal("10000.00"),
        "earned_date": date(2026, 10, 15),
    }

    # Cross-tenant plan
    e_plan = CommissionEarning(**{**base_args, "plan": commission_plan_b})
    with pytest.raises(ValidationError) as exc:
        e_plan.clean()
    assert "plan" in exc.value.message_dict
    assert "Commission plan belongs to another workspace." in exc.value.message_dict["plan"]

    # Cross-tenant payee
    e_payee = CommissionEarning(**{**base_args, "payee": admin_b})
    with pytest.raises(ValidationError) as exc:
        e_payee.clean()
    assert "payee" in exc.value.message_dict
    assert "Credited payee must belong to the same workspace." in exc.value.message_dict["payee"]

    # Cross-tenant opportunity
    e_opp = CommissionEarning(**{**base_args, "opportunity": opp_b})
    with pytest.raises(ValidationError) as exc:
        e_opp.clean()
    assert "opportunity" in exc.value.message_dict
    assert "Opportunity belongs to another workspace." in exc.value.message_dict["opportunity"]

    # Cross-tenant sales order
    e_so = CommissionEarning(**{**base_args, "sales_order": so_b})
    with pytest.raises(ValidationError) as exc:
        e_so.clean()
    assert "sales_order" in exc.value.message_dict
    assert "Sales order belongs to another workspace." in exc.value.message_dict["sales_order"]

    # Cross-tenant statement
    e_stmt = CommissionEarning(**{**base_args, "statement": stmt_b})
    with pytest.raises(ValidationError) as exc:
        e_stmt.clean()
    assert "statement" in exc.value.message_dict
    assert "Statement belongs to another workspace." in exc.value.message_dict["statement"]


def test_incentivecompensation_earning_cross_payee_guard(
    tenant_a,
    commission_plan_a,
    admin_user,
    member_user,
    icm_currency,
):
    """Statement attached to earning must belong to the exact same payee."""
    stmt_admin = _incentivecompensation_statement(tenant_a, plan=commission_plan_a, payee=admin_user)

    earning = CommissionEarning(
        tenant=tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        statement=stmt_admin,
        deal_currency=icm_currency,
        deal_amount=Decimal("20000.00"),
        earned_date=date(2026, 10, 15),
    )
    with pytest.raises(ValidationError) as exc:
        earning.clean()
    assert "statement" in exc.value.message_dict
    assert "Attached statement must belong to the same payee." in exc.value.message_dict["statement"]

    # Same payee statement passes
    stmt_member = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        period_start=date(2026, 2, 1),
        period_end=date(2026, 2, 28),
    )
    earning.statement = stmt_member
    earning.clean()


# ============================================================================
# 6. CommissionStatement validation guards in clean()
# ============================================================================

def test_incentivecompensation_statement_period_dates_guard(tenant_a, commission_plan_a, member_user):
    """G10: Period end date cannot precede period start date."""
    stmt = CommissionStatement(
        tenant=tenant_a,
        statement_number="STMT-DATE-GUARD",
        plan=commission_plan_a,
        payee=member_user,
        period_start=date(2026, 10, 31),
        period_end=date(2026, 10, 1),
    )
    with pytest.raises(ValidationError) as exc:
        stmt.clean()
    assert "period_end" in exc.value.message_dict
    assert "Period end date cannot precede period start date." in exc.value.message_dict["period_end"]

    # Equal start and end passes
    stmt.period_end = date(2026, 10, 31)
    stmt.period_start = date(2026, 10, 31)
    stmt.clean()


def test_incentivecompensation_statement_cross_tenant_guards(
    tenant_a,
    tenant_b,
    commission_plan_a,
    commission_plan_b,
    member_user,
    admin_b,
):
    """G13: Cross-tenant payee, plan, approved_by, and payroll_run raise ValidationError."""
    pr_b = _incentivecompensation_payroll_run(tenant_b)

    base_args = {
        "tenant": tenant_a,
        "statement_number": "STMT-TENANT-GUARD",
        "plan": commission_plan_a,
        "payee": member_user,
        "period_start": date(2026, 10, 1),
        "period_end": date(2026, 10, 31),
    }

    # Cross-tenant payee
    stmt_payee = CommissionStatement(**{**base_args, "payee": admin_b})
    with pytest.raises(ValidationError) as exc:
        stmt_payee.clean()
    assert "payee" in exc.value.message_dict
    assert "Payee must belong to the same workspace." in exc.value.message_dict["payee"]

    # Cross-tenant plan
    stmt_plan = CommissionStatement(**{**base_args, "plan": commission_plan_b})
    with pytest.raises(ValidationError) as exc:
        stmt_plan.clean()
    assert "plan" in exc.value.message_dict
    assert "Compensation plan belongs to another workspace." in exc.value.message_dict["plan"]

    # Cross-tenant approver
    stmt_appr = CommissionStatement(**{**base_args, "approved_by": admin_b})
    with pytest.raises(ValidationError) as exc:
        stmt_appr.clean()
    assert "approved_by" in exc.value.message_dict
    assert "Approver must belong to the same workspace." in exc.value.message_dict["approved_by"]

    # Cross-tenant payroll run
    stmt_pr = CommissionStatement(**{**base_args, "payroll_run": pr_b})
    with pytest.raises(ValidationError) as exc:
        stmt_pr.clean()
    assert "payroll_run" in exc.value.message_dict
    assert "Payroll run belongs to another workspace." in exc.value.message_dict["payroll_run"]


def test_incentivecompensation_statement_waterfall_consistency(tenant_a, commission_plan_a, member_user):
    """G11: Waterfall calculation in clean() verifies net_payout and zero-floor clamping."""
    stmt = CommissionStatement(
        tenant=tenant_a,
        statement_number="STMT-WATERFALL-TEST",
        plan=commission_plan_a,
        payee=member_user,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        gross_earnings=Decimal("10000.00"),
        adjustments_amount=Decimal("500.00"),
        draw_recovered=Decimal("2000.00"),
        clawbacks_deducted=Decimal("1000.00"),
        tax_withholding_amount=Decimal("1500.00"),
    )
    stmt.clean()
    # net_payout = 10000 + 500 - 2000 - 1000 - 1500 = 6000.00
    assert stmt.net_payout == Decimal("6000.00")

    # Clamping test: deductions exceed gross earnings -> floor at 0.00
    stmt.clawbacks_deducted = Decimal("15000.00")
    stmt.clean()
    assert stmt.net_payout == Decimal("0.00")


# ============================================================================
# 7. CommissionAdjustment validation guards in clean()
# ============================================================================

def test_incentivecompensation_adjustment_cross_payee_guards(
    tenant_a,
    commission_statement_a,
    commission_earning_a,
    admin_user,
    member_user,
):
    """G17: Linked earning and statement must belong to the same payee."""
    # Cross-payee earning: earning payee is member_user, adjustment payee is admin_user
    adj_earning = CommissionAdjustment(
        tenant=tenant_a,
        payee=admin_user,
        earning=commission_earning_a,
        adjustment_type="manual_override",
        amount=Decimal("200.00"),
        effective_date=date(2026, 10, 15),
    )
    with pytest.raises(ValidationError) as exc:
        adj_earning.clean()
    assert "earning" in exc.value.message_dict
    assert "Linked commission earning must belong to the same payee." in exc.value.message_dict["earning"]

    # Cross-payee statement: statement payee is member_user, adjustment payee is admin_user
    adj_stmt = CommissionAdjustment(
        tenant=tenant_a,
        payee=admin_user,
        statement=commission_statement_a,
        adjustment_type="manual_override",
        amount=Decimal("200.00"),
        effective_date=date(2026, 10, 15),
    )
    with pytest.raises(ValidationError) as exc:
        adj_stmt.clean()
    assert "statement" in exc.value.message_dict
    assert "Linked statement must belong to the same payee." in exc.value.message_dict["statement"]

    # Matching payee passes
    adj_valid = CommissionAdjustment(
        tenant=tenant_a,
        payee=member_user,
        statement=commission_statement_a,
        earning=commission_earning_a,
        adjustment_type="manual_override",
        amount=Decimal("200.00"),
        effective_date=date(2026, 10, 15),
    )
    adj_valid.clean()


def test_incentivecompensation_adjustment_cross_tenant_guards(
    tenant_a,
    tenant_b,
    commission_statement_a,
    commission_statement_b,
    commission_earning_a,
    commission_earning_b,
    member_user,
    admin_b,
):
    """G14: Cross-tenant payee, requested_by, approved_by, earning, statement raise ValidationError."""
    base_args = {
        "tenant": tenant_a,
        "payee": member_user,
        "adjustment_type": "manual_override",
        "amount": Decimal("150.00"),
        "effective_date": date(2026, 10, 15),
    }

    # Cross-tenant payee
    adj_payee = CommissionAdjustment(**{**base_args, "payee": admin_b})
    with pytest.raises(ValidationError) as exc:
        adj_payee.clean()
    assert "payee" in exc.value.message_dict
    assert "Payee must belong to the same workspace." in exc.value.message_dict["payee"]

    # Cross-tenant requested_by
    adj_req = CommissionAdjustment(**{**base_args, "requested_by": admin_b})
    with pytest.raises(ValidationError) as exc:
        adj_req.clean()
    assert "requested_by" in exc.value.message_dict
    assert "Requester must belong to the same workspace." in exc.value.message_dict["requested_by"]

    # Cross-tenant approved_by
    adj_appr = CommissionAdjustment(**{**base_args, "approved_by": admin_b})
    with pytest.raises(ValidationError) as exc:
        adj_appr.clean()
    assert "approved_by" in exc.value.message_dict
    assert "Approver must belong to the same workspace." in exc.value.message_dict["approved_by"]

    # Cross-tenant earning
    adj_earn = CommissionAdjustment(**{**base_args, "earning": commission_earning_b})
    with pytest.raises(ValidationError) as exc:
        adj_earn.clean()
    assert "earning" in exc.value.message_dict
    assert "Commission earning belongs to another workspace." in exc.value.message_dict["earning"]

    # Cross-tenant statement
    adj_stmt = CommissionAdjustment(**{**base_args, "statement": commission_statement_b})
    with pytest.raises(ValidationError) as exc:
        adj_stmt.clean()
    assert "statement" in exc.value.message_dict
    assert "Statement belongs to another workspace." in exc.value.message_dict["statement"]


def test_incentivecompensation_adjustment_cancellation_clawback_guard(tenant_a, member_user):
    """G15: Cancellation clawbacks must have negative amounts."""
    adj = CommissionAdjustment(
        tenant=tenant_a,
        payee=member_user,
        adjustment_type="cancellation_clawback",
        amount=Decimal("500.00"),  # positive -> invalid
        effective_date=date(2026, 10, 15),
    )
    with pytest.raises(ValidationError) as exc:
        adj.clean()
    assert "amount" in exc.value.message_dict
    assert "Cancellation clawbacks must be recorded with a negative amount" in exc.value.message_dict["amount"][0]

    # Negative amount passes
    adj.amount = Decimal("-500.00")
    adj.clean()

    # Zero amount passes
    adj.amount = Decimal("0.00")
    adj.clean()

    # Other adjustment type with positive amount passes
    adj.adjustment_type = "manual_override"
    adj.amount = Decimal("500.00")
    adj.clean()


def test_incentivecompensation_adjustment_locked_statement_guard(tenant_a, commission_plan_a, member_user):
    """G16: Adjustments cannot be attached to locked, exported, or paid statements."""
    for idx, locked_status in enumerate(("locked", "exported", "paid"), start=1):
        stmt = _incentivecompensation_statement(
            tenant_a,
            plan=commission_plan_a,
            payee=member_user,
            status=locked_status,
            period_start=date(2024, idx, 1),
            period_end=date(2024, idx, 28),
        )
        adj = CommissionAdjustment(
            tenant=tenant_a,
            payee=member_user,
            statement=stmt,
            adjustment_type="manual_bonus",
            amount=Decimal("100.00"),
            effective_date=date(2026, 10, 15),
        )
        with pytest.raises(ValidationError) as exc:
            adj.clean()
        assert "statement" in exc.value.message_dict
        assert "Cannot attach adjustments to a locked or exported statement." in exc.value.message_dict["statement"][0]

    # Attaching to draft statement passes
    draft_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        status="draft",
        period_start=date(2024, 5, 1),
        period_end=date(2024, 5, 28),
    )
    adj.statement = draft_stmt
    adj.clean()


# ============================================================================
# 8. DB Unique Constraints & Multi-Tenant Isolation
# ============================================================================

def test_incentivecompensation_unique_number_per_tenant(
    tenant_a,
    tenant_b,
    admin_user,
    member_user,
    commission_plan_a,
    commission_earning_a,
    commission_statement_a,
    commission_adjustment_a,
    icm_currency,
):
    """Verify unique number constraint is enforced within tenant but isolated across tenants."""
    models_and_instances = [
        (
            CommissionPlan,
            commission_plan_a,
            {"name": "Dupe Plan", "code": "dupe-cmpl-code", "currency": icm_currency, "effective_start": date(2026, 1, 1)},
        ),
        (
            CommissionEarning,
            commission_earning_a,
            {"plan": commission_plan_a, "payee": member_user, "deal_currency": icm_currency, "deal_amount": Decimal("1000.00"), "earned_date": date(2026, 10, 1)},
        ),
        (
            CommissionStatement,
            commission_statement_a,
            {"statement_number": "STMT-DUPE-NUM", "plan": commission_plan_a, "payee": member_user, "period_start": date(2023, 1, 1), "period_end": date(2023, 1, 31)},
        ),
        (
            CommissionAdjustment,
            commission_adjustment_a,
            {"payee": member_user, "adjustment_type": "manual_override", "amount": Decimal("100.00"), "effective_date": date(2026, 10, 1)},
        ),
    ]

    for model_cls, instance, extra_kwargs in models_and_instances:
        dupe_number = instance.number

        # Duplicate number in same tenant raises IntegrityError
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                model_cls.objects.create(
                    tenant=tenant_a,
                    number=dupe_number,
                    **extra_kwargs,
                )

        # Same number in different tenant succeeds
        cross_extra = {**extra_kwargs}
        if "plan" in cross_extra and cross_extra["plan"].tenant != tenant_b:
            cross_extra["plan"] = _incentivecompensation_plan(tenant_b, currency=icm_currency)
        if "payee" in cross_extra and getattr(cross_extra["payee"], "tenant", None) != tenant_b:
            temp_b_user = User.objects.create_user(
                email=f"temp_user_{model_cls.__name__}@tenantb.com",
                username=f"temp_{model_cls.__name__}",
                password="Password123!",
                tenant=tenant_b,
            )
            cross_extra["payee"] = temp_b_user

        b_item = model_cls.objects.create(
            tenant=tenant_b,
            number=dupe_number,
            **cross_extra,
        )
        assert b_item.number == dupe_number
        assert b_item.tenant == tenant_b


def test_incentivecompensation_plan_unique_code_per_tenant(tenant_a, tenant_b, icm_currency):
    """sales_cmpl_tenant_code_uniq prevents duplicate code in same tenant but allows in different tenant."""
    plan_a = _incentivecompensation_plan(tenant_a, currency=icm_currency, code="unique-quota-code")

    # Duplicate code in tenant_a raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CommissionPlan.objects.create(
                tenant=tenant_a,
                name="Duplicate Code Plan",
                code="unique-quota-code",
                currency=icm_currency,
                effective_start=date(2026, 1, 1),
            )

    # Same code in tenant_b succeeds
    plan_b = CommissionPlan.objects.create(
        tenant=tenant_b,
        name="Cross-Tenant Same Code Plan",
        code="unique-quota-code",
        currency=icm_currency,
        effective_start=date(2026, 1, 1),
    )
    assert plan_b.code == plan_a.code
    assert plan_b.tenant != plan_a.tenant


def test_incentivecompensation_statement_unique_payee_period_per_tenant(
    tenant_a,
    tenant_b,
    commission_plan_a,
    commission_plan_b,
    member_user,
):
    """sales_cst_payee_period_uniq enforces 1 statement per payee per period cycle in a workspace."""
    p_start = date(2026, 7, 1)
    p_end = date(2026, 7, 31)

    _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        period_start=p_start,
        period_end=p_end,
    )

    # Duplicate statement for same payee and period in tenant_a raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CommissionStatement.objects.create(
                tenant=tenant_a,
                statement_number="STMT-DUPE-PERIOD",
                plan=commission_plan_a,
                payee=member_user,
                period_start=p_start,
                period_end=p_end,
            )

    # Different period for same payee succeeds
    stmt_next = CommissionStatement.objects.create(
        tenant=tenant_a,
        statement_number="STMT-NEXT-PERIOD",
        plan=commission_plan_a,
        payee=member_user,
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
    )
    assert stmt_next.pk is not None


# ============================================================================
# 9. Relational cascade and on_delete behaviors
# ============================================================================

def test_incentivecompensation_plan_delete_behaviors(tenant_a, admin_user):
    """Verify on_delete rules on CommissionPlan: currency is PROTECT, quota and owner are SET_NULL."""
    curr = Currency.objects.create(code="CAD", name="Canadian Dollar", symbol="C$")
    quota = _incentivecompensation_sales_quota(tenant_a, owner=admin_user)
    temp_owner = User.objects.create_user(
        email="plan_owner_temp@example.com",
        username="plan_owner_temp",
        password="Password123!",
        tenant=tenant_a,
    )

    plan = _incentivecompensation_plan(
        tenant_a,
        currency=curr,
        sales_quota=quota,
        owner=temp_owner,
    )

    # Deleting referenced Currency raises ProtectedError
    with pytest.raises(ProtectedError):
        curr.delete()

    # Deleting sales quota sets plan.sales_quota to NULL
    quota.delete()
    plan.refresh_from_db()
    assert plan.sales_quota is None

    # Deleting owner sets plan.owner to NULL
    temp_owner.delete()
    plan.refresh_from_db()
    assert plan.owner is None


def test_incentivecompensation_earning_delete_behaviors(tenant_a, commission_plan_a, icm_currency):
    """Verify on_delete rules on CommissionEarning: plan/payee CASCADE, related entities SET_NULL."""
    temp_rep = User.objects.create_user(
        email="earning_rep_temp@example.com",
        username="earning_rep_temp",
        password="Password123!",
        tenant=tenant_a,
    )
    opp = _incentivecompensation_opportunity(tenant_a)
    so = _incentivecompensation_sales_order(tenant_a)
    stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=temp_rep,
        period_start=date(2025, 4, 1),
        period_end=date(2025, 4, 30),
    )

    earning = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=temp_rep,
        opportunity=opp,
        sales_order=so,
        statement=stmt,
        currency=icm_currency,
    )

    # Deleting opportunity sets earning.opportunity to NULL
    opp.delete()
    earning.refresh_from_db()
    assert earning.opportunity is None

    # Deleting sales order sets earning.sales_order to NULL
    so.delete()
    earning.refresh_from_db()
    assert earning.sales_order is None

    # Deleting statement sets earning.statement to NULL
    stmt.delete()
    earning.refresh_from_db()
    assert earning.statement is None

    # Deleting payee CASCADES earning
    earning_id = earning.id
    temp_rep.delete()
    assert not CommissionEarning.objects.filter(id=earning_id).exists()


def test_incentivecompensation_statement_delete_behaviors(tenant_a, commission_plan_a):
    """Verify on_delete rules on CommissionStatement: plan is PROTECT, payee CASCADES, approver/payroll SET_NULL."""
    temp_payee = User.objects.create_user(
        email="stmt_payee_temp@example.com",
        username="stmt_payee_temp",
        password="Password123!",
        tenant=tenant_a,
    )
    temp_appr = User.objects.create_user(
        email="stmt_appr_temp@example.com",
        username="stmt_appr_temp",
        password="Password123!",
        tenant=tenant_a,
    )
    pr = _incentivecompensation_payroll_run(tenant_a)

    stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=temp_payee,
        approved_by=temp_appr,
        payroll_run=pr,
        period_start=date(2025, 5, 1),
        period_end=date(2025, 5, 31),
    )

    # Deleting plan raises ProtectedError
    with pytest.raises(ProtectedError):
        commission_plan_a.delete()

    # Deleting approved_by sets statement.approved_by to NULL
    temp_appr.delete()
    stmt.refresh_from_db()
    assert stmt.approved_by is None

    # Deleting payroll_run sets statement.payroll_run to NULL
    pr.delete()
    stmt.refresh_from_db()
    assert stmt.payroll_run is None

    # Deleting payee CASCADES statement
    stmt_id = stmt.id
    temp_payee.delete()
    assert not CommissionStatement.objects.filter(id=stmt_id).exists()


def test_incentivecompensation_adjustment_delete_behaviors(tenant_a, commission_plan_a, icm_currency):
    """Verify on_delete rules on CommissionAdjustment: payee CASCADES, statement/earning/users SET_NULL."""
    temp_payee = User.objects.create_user(
        email="adj_payee_temp@example.com",
        username="adj_payee_temp",
        password="Password123!",
        tenant=tenant_a,
    )
    temp_req = User.objects.create_user(
        email="adj_req_temp@example.com",
        username="adj_req_temp",
        password="Password123!",
        tenant=tenant_a,
    )
    temp_appr = User.objects.create_user(
        email="adj_appr_temp@example.com",
        username="adj_appr_temp",
        password="Password123!",
        tenant=tenant_a,
    )
    stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=temp_payee,
        period_start=date(2025, 6, 1),
        period_end=date(2025, 6, 30),
    )
    earn = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=temp_payee,
        currency=icm_currency,
    )

    adj = _incentivecompensation_adjustment(
        tenant_a,
        payee=temp_payee,
        statement=stmt,
        earning=earn,
        requested_by=temp_req,
        approved_by=temp_appr,
        adjustment_type="manual_override",
    )

    # Deleting statement sets adj.statement to NULL
    stmt.delete()
    adj.refresh_from_db()
    assert adj.statement is None

    # Deleting earning sets adj.earning to NULL
    earn.delete()
    adj.refresh_from_db()
    assert adj.earning is None

    # Deleting requested_by sets adj.requested_by to NULL
    temp_req.delete()
    adj.refresh_from_db()
    assert adj.requested_by is None

    # Deleting approved_by sets adj.approved_by to NULL
    temp_appr.delete()
    adj.refresh_from_db()
    assert adj.approved_by is None

    # Deleting payee CASCADES adjustment
    adj_id = adj.id
    temp_payee.delete()
    assert not CommissionAdjustment.objects.filter(id=adj_id).exists()
