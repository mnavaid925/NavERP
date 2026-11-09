"""Asset Depreciation & Financial Management (11.4) — FORMS Invariants Test Suite.

Covers the 4 model forms:
- AssetDepreciationScheduleForm
- AssetRevaluationForm
- AssetTransferForm
- CapitalizationPolicyForm

Invariants pinned:
1. Valid data submissions producing valid forms, correct model instances, and proper tenant linkage.
2. System & workflow field exclusion (tenant, auto-generated number, workflow status,
   internal/derived ledger fields like journal_entry, posted_at, approved_at, completed_at,
   and running calculation totals) preventing mass-assignment vulnerability.
3. Strict tenant isolation on choice querysets (fixed_asset, operational_asset, fiscal_period,
   expense_account, accumulated_account, cost_center, appraiser, locations, departments,
   custodians, transferred_by, category, CIP accounts).
4. Cross-tenant foreign key rejection via field-level queryset exclusion and reject_foreign clean() validation.
5. Negative/invalid edge case handling (invalid choices, missing required fields, non-existent foreign keys).
6. Commit handling (commit=True saves with auto-numbered prefix; commit=False attaches tenant instance).
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounting.models import FiscalPeriod, FixedAsset, GLAccount
from apps.assets.forms import (
    AssetDepreciationScheduleForm,
    AssetRevaluationForm,
    AssetTransferForm,
    CapitalizationPolicyForm,
)
from apps.assets.models import (
    AssetCategory,
    AssetDepreciationSchedule,
    AssetRevaluation,
    AssetTransfer,
    CapitalizationPolicy,
)
from apps.core.models import OrgUnit, Party
from apps.scm.models import Asset, Location

User = get_user_model()


# ==============================================================================
# Helper Functions & Payloads
# ==============================================================================


def _assetdepreciation_fiscal_period(tenant, name="FY2026-P01", **kwargs):
    """Create a test fiscal period belonging to the given tenant."""
    now = timezone.now().date()
    return FiscalPeriod.objects.create(
        tenant=tenant,
        name=name,
        period_type="month",
        start_date=now.replace(day=1),
        end_date=now.replace(day=28),
        status="open",
        **kwargs,
    )


def _assetdepreciation_schedule_payload(
    fixed_asset,
    operational_asset=None,
    fiscal_period=None,
    expense_account=None,
    accumulated_account=None,
    cost_center=None,
    **kwargs,
):
    """Generate valid base form payload for AssetDepreciationScheduleForm."""
    payload = {
        "fixed_asset": fixed_asset.pk if hasattr(fixed_asset, "pk") else fixed_asset,
        "operational_asset": (operational_asset.pk if hasattr(operational_asset, "pk") else operational_asset) or "",
        "fiscal_period": (fiscal_period.pk if hasattr(fiscal_period, "pk") else fiscal_period) or "",
        "fiscal_year": 2026,
        "period_number": 2,
        "period_frequency": "monthly",
        "schedule_date": str(timezone.now().date()),
        "depreciation_method": "straight_line",
        "starting_book_value": "118200.00",
        "depreciation_amount": "1800.00",
        "total_units_expected": "",
        "units_produced_period": "",
        "expense_account": (expense_account.pk if hasattr(expense_account, "pk") else expense_account) or "",
        "accumulated_account": (accumulated_account.pk if hasattr(accumulated_account, "pk") else accumulated_account) or "",
        "cost_center": (cost_center.pk if hasattr(cost_center, "pk") else cost_center) or "",
        "notes": "Regular monthly straight-line depreciation schedule run.",
    }
    payload.update(kwargs)
    return payload


def _assetdepreciation_revaluation_payload(
    fixed_asset,
    operational_asset=None,
    appraiser=None,
    impairment_loss_account=None,
    revaluation_surplus_account=None,
    **kwargs,
):
    """Generate valid base form payload for AssetRevaluationForm."""
    payload = {
        "title": "Mid-Year CNC Impairment Review",
        "fixed_asset": fixed_asset.pk if hasattr(fixed_asset, "pk") else fixed_asset,
        "operational_asset": (operational_asset.pk if hasattr(operational_asset, "pk") else operational_asset) or "",
        "event_type": "impairment",
        "valuation_method": "independent_appraisal",
        "valuation_date": str(timezone.now().date()),
        "appraiser": (appraiser.pk if hasattr(appraiser, "pk") else appraiser) or "",
        "appraiser_name_fallback": "Global Valuation Associates",
        "new_fair_market_value": "95000.00",
        "new_salvage_value": "10000.00",
        "remaining_useful_life_months": 48,
        "impairment_loss_account": (impairment_loss_account.pk if hasattr(impairment_loss_account, "pk") else impairment_loss_account) or "",
        "revaluation_surplus_account": (revaluation_surplus_account.pk if hasattr(revaluation_surplus_account, "pk") else revaluation_surplus_account) or "",
        "reason_and_methodology": "Appraisal assessment reflecting technological changes under IAS 36.",
    }
    payload.update(kwargs)
    return payload


def _assetdepreciation_transfer_payload(
    fixed_asset,
    operational_asset=None,
    source_department=None,
    source_location=None,
    source_custodian=None,
    source_expense_account=None,
    destination_department=None,
    destination_location=None,
    destination_custodian=None,
    destination_expense_account=None,
    transferred_by=None,
    **kwargs,
):
    """Generate valid base form payload for AssetTransferForm."""
    payload = {
        "title": "Transfer CNC Mill to Plant 2 Assembly",
        "fixed_asset": fixed_asset.pk if hasattr(fixed_asset, "pk") else fixed_asset,
        "operational_asset": (operational_asset.pk if hasattr(operational_asset, "pk") else operational_asset) or "",
        "transfer_type": "inter_facility",
        "transfer_date": str(timezone.now().date()),
        "source_department": (source_department.pk if hasattr(source_department, "pk") else source_department) or "",
        "source_location": (source_location.pk if hasattr(source_location, "pk") else source_location) or "",
        "source_custodian": (source_custodian.pk if hasattr(source_custodian, "pk") else source_custodian) or "",
        "source_expense_account": (source_expense_account.pk if hasattr(source_expense_account, "pk") else source_expense_account) or "",
        "destination_department": (destination_department.pk if hasattr(destination_department, "pk") else destination_department) or "",
        "destination_location": (destination_location.pk if hasattr(destination_location, "pk") else destination_location) or "",
        "destination_custodian": (destination_custodian.pk if hasattr(destination_custodian, "pk") else destination_custodian) or "",
        "destination_expense_account": (destination_expense_account.pk if hasattr(destination_expense_account, "pk") else destination_expense_account) or "",
        "transportation_cost": "650.00",
        "transferred_by": (transferred_by.pk if hasattr(transferred_by, "pk") else transferred_by) or "",
        "reason": "Facility reorganization and capacity rebalancing.",
    }
    payload.update(kwargs)
    return payload


def _assetdepreciation_policy_payload(
    name="Corporate Machinery CapEx Policy",
    category=None,
    default_cip_account=None,
    default_expense_account=None,
    **kwargs,
):
    """Generate valid base form payload for CapitalizationPolicyForm."""
    payload = {
        "name": name,
        "policy_scope": "global_default",
        "category": (category.pk if hasattr(category, "pk") else category) or "",
        "minimum_cost_threshold": "3000.00",
        "minimum_useful_life_months": 12,
        "default_classification": "capitalize",
        "de_minimis_safe_harbor": True,
        "applicable_gaap_standard": "US GAAP / IFRS IAS 16",
        "default_cip_account": (default_cip_account.pk if hasattr(default_cip_account, "pk") else default_cip_account) or "",
        "default_expense_account": (default_expense_account.pk if hasattr(default_expense_account, "pk") else default_expense_account) or "",
        "effective_from": "2026-01-01",
        "effective_to": "",
        "is_active": True,
        "policy_notes": "General threshold for fixed asset capitalization across all facilities.",
    }
    payload.update(kwargs)
    return payload


# ==============================================================================
# 1. AssetDepreciationScheduleForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_create_valid(
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    expense_account_a,
    accum_account_a,
    org_unit_a,
):
    """AssetDepreciationScheduleForm successfully creates and persists a valid schedule."""
    fp_a = _assetdepreciation_fiscal_period(tenant_a, name="FY2026-P02")
    data = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        fiscal_period=fp_a,
        expense_account=expense_account_a,
        accumulated_account=accum_account_a,
        cost_center=org_unit_a,
        period_number=2,
        starting_book_value="118200.00",
        depreciation_amount="1800.00",
    )
    form = AssetDepreciationScheduleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    schedule = form.save()
    assert schedule.pk is not None
    assert schedule.tenant == tenant_a
    assert schedule.number.startswith("ADEP-")
    assert schedule.fixed_asset == fixed_asset_a
    assert schedule.operational_asset == operational_asset_a
    assert schedule.fiscal_period == fp_a
    assert schedule.fiscal_year == 2026
    assert schedule.period_number == 2
    assert schedule.depreciation_method == "straight_line"
    assert schedule.starting_book_value == Decimal("118200.00")
    assert schedule.depreciation_amount == Decimal("1800.00")
    assert schedule.expense_account == expense_account_a
    assert schedule.accumulated_account == accum_account_a
    assert schedule.cost_center == org_unit_a
    assert schedule.status == "draft"


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_update_valid(
    tenant_a,
    fixed_asset_a,
    expense_account_a,
    accum_account_a,
):
    """AssetDepreciationScheduleForm successfully updates an existing schedule instance."""
    schedule = AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        fiscal_year=2026,
        period_number=1,
        period_frequency="monthly",
        depreciation_method="straight_line",
        starting_book_value=Decimal("120000.00"),
        depreciation_amount=Decimal("1800.00"),
        expense_account=expense_account_a,
        accumulated_account=accum_account_a,
        notes="Initial draft schedule notes.",
        status="draft",
    )
    data = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        expense_account=expense_account_a,
        accumulated_account=accum_account_a,
        period_number=3,
        depreciation_amount="2000.00",
        notes="Updated notes after mid-month adjustment.",
    )
    form = AssetDepreciationScheduleForm(data=data, instance=schedule, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == schedule.pk
    assert updated.period_number == 3
    assert updated.depreciation_amount == Decimal("2000.00")
    assert updated.notes == "Updated notes after mid-month adjustment."


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_excludes_system_fields():
    """AssetDepreciationScheduleForm excludes tenant, auto-number, status, and ledger internals."""
    form = AssetDepreciationScheduleForm()
    expected_exclusions = [
        "tenant",
        "number",
        "accumulated_depreciation_after",
        "ending_book_value",
        "journal_entry",
        "status",
        "posted_at",
        "posted_by",
        "created_at",
        "updated_at",
    ]
    for field_name in expected_exclusions:
        assert field_name not in form.fields, f"{field_name} must be excluded from form.fields"
    assert AssetDepreciationScheduleForm.Meta.exclude == expected_exclusions


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_mass_assignment_protection(
    tenant_a,
    fixed_asset_a,
):
    """Malicious payload attempting to force status='posted' and inject journal_entry is sanitized."""
    data = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        status="posted",
        number="ADEP-9999-HACK",
        accumulated_depreciation_after="999999.00",
        ending_book_value="0.00",
        posted_at="2020-01-01T00:00:00Z",
    )
    form = AssetDepreciationScheduleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    saved = form.save()
    assert saved.status == "draft"  # Model default preserved
    assert saved.number != "ADEP-9999-HACK"
    assert saved.number.startswith("ADEP-")
    assert saved.posted_at is None
    assert saved.accumulated_depreciation_after == Decimal("0.00")


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_tenant_queryset_scoping(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    expense_account_a,
    expense_account_b,
    accum_account_a,
    accum_account_b,
    org_unit_a,
    org_unit_b,
):
    """Dropdown querysets for fixed_asset, operational_asset, accounts, and cost_center are strictly tenant-scoped."""
    fp_a = _assetdepreciation_fiscal_period(tenant_a, name="FY2026-P01-A")
    fp_b = _assetdepreciation_fiscal_period(tenant_b, name="FY2026-P01-B")

    form_a = AssetDepreciationScheduleForm(tenant=tenant_a)

    # Fixed Assets
    assert fixed_asset_a in form_a.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form_a.fields["fixed_asset"].queryset

    # Operational Assets
    assert operational_asset_a in form_a.fields["operational_asset"].queryset
    assert operational_asset_b not in form_a.fields["operational_asset"].queryset

    # Fiscal Periods
    assert fp_a in form_a.fields["fiscal_period"].queryset
    assert fp_b not in form_a.fields["fiscal_period"].queryset

    # GL Accounts
    assert expense_account_a in form_a.fields["expense_account"].queryset
    assert expense_account_b not in form_a.fields["expense_account"].queryset
    assert accum_account_a in form_a.fields["accumulated_account"].queryset
    assert accum_account_b not in form_a.fields["accumulated_account"].queryset

    # Cost Centers (OrgUnit)
    assert org_unit_a in form_a.fields["cost_center"].queryset
    assert org_unit_b not in form_a.fields["cost_center"].queryset


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_rejects_cross_tenant_fixed_asset(
    tenant_a,
    tenant_b,
    fixed_asset_b,
):
    """Submitting another tenant's fixed_asset fails form validation."""
    data = _assetdepreciation_schedule_payload(fixed_asset=fixed_asset_b)
    form = AssetDepreciationScheduleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_rejects_cross_tenant_operational_asset(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    operational_asset_b,
):
    """Submitting another tenant's operational_asset fails form validation."""
    data = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_b,
    )
    form = AssetDepreciationScheduleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operational_asset" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_rejects_cross_tenant_accounts(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    expense_account_b,
    accum_account_b,
):
    """Submitting another tenant's GL expense or accumulated account fails form validation."""
    data_exp = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        expense_account=expense_account_b,
    )
    form_exp = AssetDepreciationScheduleForm(data=data_exp, tenant=tenant_a)
    assert not form_exp.is_valid()
    assert "expense_account" in form_exp.errors

    data_accum = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        accumulated_account=accum_account_b,
    )
    form_accum = AssetDepreciationScheduleForm(data=data_accum, tenant=tenant_a)
    assert not form_accum.is_valid()
    assert "accumulated_account" in form_accum.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_rejects_cross_tenant_cost_center(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    org_unit_b,
):
    """Submitting another tenant's cost center fails form validation."""
    data = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        cost_center=org_unit_b,
    )
    form = AssetDepreciationScheduleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "cost_center" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_reject_foreign_clean_direct(
    tenant_a,
    fixed_asset_a,
    fixed_asset_b,
):
    """Directly test reject_foreign invocation in clean() when cross-tenant objects are present."""
    form = AssetDepreciationScheduleForm(tenant=tenant_a)
    form.cleaned_data = {
        "fixed_asset": fixed_asset_b,
        "operational_asset": None,
        "fiscal_period": None,
        "expense_account": None,
        "accumulated_account": None,
        "cost_center": None,
    }
    cleaned = form.clean()
    assert "fixed_asset" in form.errors
    assert "That record belongs to another workspace." in form.errors["fixed_asset"]


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_uop_method_fields(
    tenant_a,
    fixed_asset_a,
):
    """AssetDepreciationScheduleForm accepts valid parameters for Units-of-Production method."""
    data = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        depreciation_method="units_of_production",
        total_units_expected="100000.00",
        units_produced_period="2500.00",
    )
    form = AssetDepreciationScheduleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    saved = form.save()
    assert saved.depreciation_method == "units_of_production"
    assert saved.total_units_expected == Decimal("100000.00")
    assert saved.units_produced_period == Decimal("2500.00")


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_validation_missing_required(tenant_a):
    """Missing required fixed_asset causes form validation to fail."""
    data = _assetdepreciation_schedule_payload(fixed_asset="")
    form = AssetDepreciationScheduleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_validation_invalid_method(
    tenant_a,
    fixed_asset_a,
):
    """Submitting an invalid depreciation_method choice causes validation error."""
    data = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        depreciation_method="crypto_amortization",
    )
    form = AssetDepreciationScheduleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "depreciation_method" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_validation_invalid_period_frequency(
    tenant_a,
    fixed_asset_a,
):
    """Submitting an invalid period_frequency choice causes validation error."""
    data = _assetdepreciation_schedule_payload(
        fixed_asset=fixed_asset_a,
        period_frequency="bi_weekly",
    )
    form = AssetDepreciationScheduleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "period_frequency" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_schedule_save_commit_false(
    tenant_a,
    fixed_asset_a,
):
    """Saving with commit=False attaches tenant to instance and delays DB commit."""
    data = _assetdepreciation_schedule_payload(fixed_asset=fixed_asset_a)
    form = AssetDepreciationScheduleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    assert instance.pk is None
    assert instance.tenant == tenant_a
    assert instance.fixed_asset == fixed_asset_a
    instance.save()
    assert instance.pk is not None


# ==============================================================================
# 2. AssetRevaluationForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_create_valid(
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    vendor_party_a,
    expense_account_a,
    surplus_account_a,
):
    """AssetRevaluationForm creates and persists a valid asset revaluation record."""
    data = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        appraiser=vendor_party_a,
        impairment_loss_account=expense_account_a,
        revaluation_surplus_account=surplus_account_a,
        event_type="revaluation_up",
        valuation_method="independent_appraisal",
        new_fair_market_value="135000.00",
        new_salvage_value="15000.00",
        remaining_useful_life_months=72,
    )
    form = AssetRevaluationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    rev = form.save()
    assert rev.pk is not None
    assert rev.tenant == tenant_a
    assert rev.number.startswith("AREV-")
    assert rev.title == "Mid-Year CNC Impairment Review"
    assert rev.fixed_asset == fixed_asset_a
    assert rev.operational_asset == operational_asset_a
    assert rev.event_type == "revaluation_up"
    assert rev.valuation_method == "independent_appraisal"
    assert rev.appraiser == vendor_party_a
    assert rev.new_fair_market_value == Decimal("135000.00")
    assert rev.new_salvage_value == Decimal("15000.00")
    assert rev.remaining_useful_life_months == 72
    assert rev.impairment_loss_account == expense_account_a
    assert rev.revaluation_surplus_account == surplus_account_a
    assert rev.status == "draft"


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_update_valid(
    tenant_a,
    fixed_asset_a,
    vendor_party_a,
):
    """AssetRevaluationForm successfully updates an existing revaluation instance."""
    rev = AssetRevaluation.objects.create(
        tenant=tenant_a,
        title="Initial Valuation Draft",
        fixed_asset=fixed_asset_a,
        event_type="impairment",
        valuation_method="cost_approach",
        new_fair_market_value=Decimal("80000.00"),
        status="draft",
    )
    data = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        appraiser=vendor_party_a,
        title="Updated Certified Valuation",
        new_fair_market_value="88000.00",
        remaining_useful_life_months=36,
    )
    form = AssetRevaluationForm(data=data, instance=rev, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == rev.pk
    assert updated.title == "Updated Certified Valuation"
    assert updated.new_fair_market_value == Decimal("88000.00")
    assert updated.remaining_useful_life_months == 36


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_excludes_system_fields():
    """AssetRevaluationForm strictly excludes tenant, auto-number, historical balances, and approval internals."""
    form = AssetRevaluationForm()
    expected_exclusions = [
        "tenant",
        "number",
        "historical_cost",
        "accumulated_depreciation_before",
        "carrying_value_before",
        "revaluation_adjustment",
        "journal_entry",
        "status",
        "approved_by",
        "approved_at",
        "created_at",
        "updated_at",
    ]
    for field_name in expected_exclusions:
        assert field_name not in form.fields, f"{field_name} must be excluded from form.fields"
    assert AssetRevaluationForm.Meta.exclude == expected_exclusions


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_mass_assignment_protection(
    tenant_a,
    fixed_asset_a,
):
    """Malicious payload attempting to force status='approved' and inject carrying balances is sanitized."""
    data = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        status="approved",
        number="AREV-HACK-01",
        historical_cost="500000.00",
        carrying_value_before="450000.00",
        revaluation_adjustment="150000.00",
        approved_at="2026-01-01T00:00:00Z",
    )
    form = AssetRevaluationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    saved = form.save()
    assert saved.status == "draft"
    assert saved.number != "AREV-HACK-01"
    assert saved.number.startswith("AREV-")
    assert saved.approved_at is None
    assert saved.historical_cost == Decimal("0.00")
    assert saved.revaluation_adjustment == Decimal("0.00")


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_tenant_queryset_scoping(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    vendor_party_a,
    vendor_party_b,
    expense_account_a,
    expense_account_b,
    surplus_account_a,
):
    """Dropdown querysets for fixed_asset, operational_asset, appraiser, and GL accounts are tenant-scoped."""
    form_a = AssetRevaluationForm(tenant=tenant_a)

    # Fixed Assets
    assert fixed_asset_a in form_a.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form_a.fields["fixed_asset"].queryset

    # Operational Assets
    assert operational_asset_a in form_a.fields["operational_asset"].queryset
    assert operational_asset_b not in form_a.fields["operational_asset"].queryset

    # Appraiser (Party)
    assert vendor_party_a in form_a.fields["appraiser"].queryset
    assert vendor_party_b not in form_a.fields["appraiser"].queryset

    # GL Accounts
    assert expense_account_a in form_a.fields["impairment_loss_account"].queryset
    assert expense_account_b not in form_a.fields["impairment_loss_account"].queryset
    assert surplus_account_a in form_a.fields["revaluation_surplus_account"].queryset


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_rejects_cross_tenant_fixed_asset(
    tenant_a,
    tenant_b,
    fixed_asset_b,
):
    """Submitting another tenant's fixed_asset fails validation on revaluation form."""
    data = _assetdepreciation_revaluation_payload(fixed_asset=fixed_asset_b)
    form = AssetRevaluationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_rejects_cross_tenant_operational_asset(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    operational_asset_b,
):
    """Submitting another tenant's operational_asset fails validation."""
    data = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_b,
    )
    form = AssetRevaluationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operational_asset" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_rejects_cross_tenant_appraiser(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    vendor_party_b,
):
    """Submitting another tenant's party as appraiser fails validation."""
    data = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        appraiser=vendor_party_b,
    )
    form = AssetRevaluationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "appraiser" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_rejects_cross_tenant_accounts(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    expense_account_b,
):
    """Submitting another tenant's GL impairment loss account fails validation."""
    data = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        impairment_loss_account=expense_account_b,
    )
    form = AssetRevaluationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "impairment_loss_account" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_reject_foreign_clean_direct(
    tenant_a,
    fixed_asset_a,
    fixed_asset_b,
):
    """Directly verify reject_foreign hook on AssetRevaluationForm.clean()."""
    form = AssetRevaluationForm(tenant=tenant_a)
    form.cleaned_data = {
        "fixed_asset": fixed_asset_b,
        "operational_asset": None,
        "appraiser": None,
        "impairment_loss_account": None,
        "revaluation_surplus_account": None,
    }
    form.clean()
    assert "fixed_asset" in form.errors
    assert "That record belongs to another workspace." in form.errors["fixed_asset"]


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_validation_missing_required(tenant_a):
    """Missing required title or fixed_asset fails revaluation form validation."""
    data = _assetdepreciation_revaluation_payload(fixed_asset="", title="")
    form = AssetRevaluationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_validation_invalid_event_type(
    tenant_a,
    fixed_asset_a,
):
    """Invalid event_type choice fails validation."""
    data = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        event_type="speculative_bubble",
    )
    form = AssetRevaluationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "event_type" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_validation_invalid_valuation_method(
    tenant_a,
    fixed_asset_a,
):
    """Invalid valuation_method choice fails validation."""
    data = _assetdepreciation_revaluation_payload(
        fixed_asset=fixed_asset_a,
        valuation_method="astrological_reading",
    )
    form = AssetRevaluationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "valuation_method" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_revaluation_save_commit_false(
    tenant_a,
    fixed_asset_a,
):
    """Saving revaluation form with commit=False sets tenant on instance."""
    data = _assetdepreciation_revaluation_payload(fixed_asset=fixed_asset_a)
    form = AssetRevaluationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    assert instance.pk is None
    assert instance.tenant == tenant_a
    instance.save()
    assert instance.pk is not None


# ==============================================================================
# 3. AssetTransferForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_create_valid(
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    org_unit_a,
    location_a,
    location_a2,
    vendor_party_a,
    expense_account_a,
    admin_user,
):
    """AssetTransferForm creates and persists a valid transfer relocation order."""
    data = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        source_department=org_unit_a,
        source_location=location_a,
        source_custodian=vendor_party_a,
        source_expense_account=expense_account_a,
        destination_department=org_unit_a,
        destination_location=location_a2,
        destination_custodian=vendor_party_a,
        destination_expense_account=expense_account_a,
        transferred_by=admin_user,
        transfer_type="inter_facility",
        transportation_cost="850.00",
    )
    form = AssetTransferForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    transfer = form.save()
    assert transfer.pk is not None
    assert transfer.tenant == tenant_a
    assert transfer.number.startswith("AXFR-")
    assert transfer.title == "Transfer CNC Mill to Plant 2 Assembly"
    assert transfer.fixed_asset == fixed_asset_a
    assert transfer.operational_asset == operational_asset_a
    assert transfer.transfer_type == "inter_facility"
    assert transfer.source_department == org_unit_a
    assert transfer.source_location == location_a
    assert transfer.destination_location == location_a2
    assert transfer.transportation_cost == Decimal("850.00")
    assert transfer.transferred_by == admin_user
    assert transfer.status == "draft"


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_update_valid(
    tenant_a,
    fixed_asset_a,
    location_a,
    location_a2,
):
    """AssetTransferForm successfully updates an existing transfer order."""
    transfer = AssetTransfer.objects.create(
        tenant=tenant_a,
        title="Initial Draft Relocation",
        fixed_asset=fixed_asset_a,
        transfer_type="inter_facility",
        source_location=location_a,
        destination_location=location_a2,
        transportation_cost=Decimal("400.00"),
        status="draft",
    )
    data = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        source_location=location_a,
        destination_location=location_a2,
        title="Updated Rigging & Moving Logistics",
        transportation_cost="750.00",
        reason="Heavy rigging equipment contracted for weekend relocation.",
    )
    form = AssetTransferForm(data=data, instance=transfer, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == transfer.pk
    assert updated.title == "Updated Rigging & Moving Logistics"
    assert updated.transportation_cost == Decimal("750.00")
    assert updated.reason == "Heavy rigging equipment contracted for weekend relocation."


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_excludes_system_fields():
    """AssetTransferForm strictly excludes tenant, auto-number, carrying balances, and completion internals."""
    form = AssetTransferForm()
    expected_exclusions = [
        "tenant",
        "number",
        "carrying_value_at_transfer",
        "journal_entry",
        "status",
        "received_by",
        "completed_at",
        "created_at",
        "updated_at",
    ]
    for field_name in expected_exclusions:
        assert field_name not in form.fields, f"{field_name} must be excluded from form.fields"
    assert AssetTransferForm.Meta.exclude == expected_exclusions


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_mass_assignment_protection(
    tenant_a,
    fixed_asset_a,
):
    """Malicious payload attempting to force status='completed' and inject carrying balances is sanitized."""
    data = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        status="completed",
        number="AXFR-HACK-01",
        carrying_value_at_transfer="120000.00",
        completed_at="2026-01-01T00:00:00Z",
    )
    form = AssetTransferForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    saved = form.save()
    assert saved.status == "draft"
    assert saved.number != "AXFR-HACK-01"
    assert saved.number.startswith("AXFR-")
    assert saved.completed_at is None
    assert saved.carrying_value_at_transfer == Decimal("0.00")


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_tenant_queryset_scoping(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    org_unit_a,
    org_unit_b,
    location_a,
    location_b,
    vendor_party_a,
    vendor_party_b,
    expense_account_a,
    expense_account_b,
    admin_user,
    admin_b,
):
    """All foreign key dropdowns in AssetTransferForm are strictly scoped to the active tenant."""
    # Create inactive user for tenant_a to verify active filter
    inactive_user = User.objects.create_user(
        email="inactive_a@example.com",
        username="inactive_a",
        password="TestPassword123!",
        tenant=tenant_a,
        is_active=False,
    )

    form_a = AssetTransferForm(tenant=tenant_a)

    # Fixed & Operational Assets
    assert fixed_asset_a in form_a.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form_a.fields["fixed_asset"].queryset
    assert operational_asset_a in form_a.fields["operational_asset"].queryset
    assert operational_asset_b not in form_a.fields["operational_asset"].queryset

    # Departments (OrgUnit)
    assert org_unit_a in form_a.fields["source_department"].queryset
    assert org_unit_b not in form_a.fields["source_department"].queryset
    assert org_unit_a in form_a.fields["destination_department"].queryset
    assert org_unit_b not in form_a.fields["destination_department"].queryset

    # Locations
    assert location_a in form_a.fields["source_location"].queryset
    assert location_b not in form_a.fields["source_location"].queryset
    assert location_a in form_a.fields["destination_location"].queryset
    assert location_b not in form_a.fields["destination_location"].queryset

    # Custodians (Party)
    assert vendor_party_a in form_a.fields["source_custodian"].queryset
    assert vendor_party_b not in form_a.fields["source_custodian"].queryset
    assert vendor_party_a in form_a.fields["destination_custodian"].queryset
    assert vendor_party_b not in form_a.fields["destination_custodian"].queryset

    # GL Accounts
    assert expense_account_a in form_a.fields["source_expense_account"].queryset
    assert expense_account_b not in form_a.fields["source_expense_account"].queryset
    assert expense_account_a in form_a.fields["destination_expense_account"].queryset
    assert expense_account_b not in form_a.fields["destination_expense_account"].queryset

    # Users (transferred_by: tenant_a and is_active=True)
    assert admin_user in form_a.fields["transferred_by"].queryset
    assert admin_b not in form_a.fields["transferred_by"].queryset
    assert inactive_user not in form_a.fields["transferred_by"].queryset


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_rejects_cross_tenant_fixed_asset(
    tenant_a,
    tenant_b,
    fixed_asset_b,
):
    """Submitting another tenant's fixed_asset fails validation on transfer form."""
    data = _assetdepreciation_transfer_payload(fixed_asset=fixed_asset_b)
    form = AssetTransferForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_rejects_cross_tenant_locations(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    location_b,
):
    """Submitting another tenant's source or destination location fails validation."""
    data_src = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        source_location=location_b,
    )
    form_src = AssetTransferForm(data=data_src, tenant=tenant_a)
    assert not form_src.is_valid()
    assert "source_location" in form_src.errors

    data_dst = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        destination_location=location_b,
    )
    form_dst = AssetTransferForm(data=data_dst, tenant=tenant_a)
    assert not form_dst.is_valid()
    assert "destination_location" in form_dst.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_rejects_cross_tenant_departments(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    org_unit_b,
):
    """Submitting another tenant's department fails validation."""
    data = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        source_department=org_unit_b,
    )
    form = AssetTransferForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "source_department" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_rejects_cross_tenant_custodians(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    vendor_party_b,
):
    """Submitting another tenant's party as custodian fails validation."""
    data = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        destination_custodian=vendor_party_b,
    )
    form = AssetTransferForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "destination_custodian" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_rejects_cross_tenant_transferred_by(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    admin_b,
):
    """Submitting another tenant's user as transferred_by fails validation."""
    data = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        transferred_by=admin_b,
    )
    form = AssetTransferForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "transferred_by" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_reject_foreign_clean_direct(
    tenant_a,
    fixed_asset_a,
    fixed_asset_b,
):
    """Directly verify reject_foreign hook on AssetTransferForm.clean()."""
    form = AssetTransferForm(tenant=tenant_a)
    form.cleaned_data = {
        "fixed_asset": fixed_asset_b,
        "operational_asset": None,
        "source_department": None,
        "source_location": None,
        "source_custodian": None,
        "source_expense_account": None,
        "destination_department": None,
        "destination_location": None,
        "destination_custodian": None,
        "destination_expense_account": None,
        "transferred_by": None,
    }
    form.clean()
    assert "fixed_asset" in form.errors
    assert "That record belongs to another workspace." in form.errors["fixed_asset"]


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_validation_missing_required(tenant_a):
    """Missing required title or fixed_asset fails transfer form validation."""
    data = _assetdepreciation_transfer_payload(fixed_asset="", title="")
    form = AssetTransferForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_validation_invalid_transfer_type(
    tenant_a,
    fixed_asset_a,
):
    """Invalid transfer_type choice fails validation."""
    data = _assetdepreciation_transfer_payload(
        fixed_asset=fixed_asset_a,
        transfer_type="teleportation_line",
    )
    form = AssetTransferForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "transfer_type" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_transfer_save_commit_false(
    tenant_a,
    fixed_asset_a,
):
    """Saving transfer form with commit=False sets tenant on instance."""
    data = _assetdepreciation_transfer_payload(fixed_asset=fixed_asset_a)
    form = AssetTransferForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    assert instance.pk is None
    assert instance.tenant == tenant_a
    instance.save()
    assert instance.pk is not None


# ==============================================================================
# 4. CapitalizationPolicyForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_create_valid(
    tenant_a,
    category_root_a,
    cip_account_a,
    expense_account_a,
):
    """CapitalizationPolicyForm creates and persists a valid capitalization policy rule."""
    data = _assetdepreciation_policy_payload(
        name="IRS De Minimis Safe Harbor Rule ($2,500)",
        category=category_root_a,
        default_cip_account=cip_account_a,
        default_expense_account=expense_account_a,
        policy_scope="tax_book_safe_harbor",
        minimum_cost_threshold="2500.00",
        minimum_useful_life_months=12,
        default_classification="expense_immediately",
        de_minimis_safe_harbor=True,
    )
    form = CapitalizationPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    policy = form.save()
    assert policy.pk is not None
    assert policy.tenant == tenant_a
    assert policy.number.startswith("ACTH-")
    assert policy.name == "IRS De Minimis Safe Harbor Rule ($2,500)"
    assert policy.policy_scope == "tax_book_safe_harbor"
    assert policy.category == category_root_a
    assert policy.minimum_cost_threshold == Decimal("2500.00")
    assert policy.minimum_useful_life_months == 12
    assert policy.default_classification == "expense_immediately"
    assert policy.de_minimis_safe_harbor is True
    assert policy.default_cip_account == cip_account_a
    assert policy.default_expense_account == expense_account_a
    assert policy.is_active is True


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_update_valid(
    tenant_a,
    category_root_a,
):
    """CapitalizationPolicyForm successfully updates an existing policy instance."""
    policy = CapitalizationPolicy.objects.create(
        tenant=tenant_a,
        name="Initial Policy Memo",
        policy_scope="global_default",
        minimum_cost_threshold=Decimal("1000.00"),
        minimum_useful_life_months=12,
        is_active=True,
    )
    data = _assetdepreciation_policy_payload(
        name="Updated Policy Memo ($5,000 CapEx Threshold)",
        category=category_root_a,
        policy_scope="category_override",
        minimum_cost_threshold="5000.00",
        minimum_useful_life_months=24,
    )
    form = CapitalizationPolicyForm(data=data, instance=policy, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == policy.pk
    assert updated.name == "Updated Policy Memo ($5,000 CapEx Threshold)"
    assert updated.policy_scope == "category_override"
    assert updated.minimum_cost_threshold == Decimal("5000.00")
    assert updated.minimum_useful_life_months == 24


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_excludes_system_fields():
    """CapitalizationPolicyForm strictly excludes tenant, auto-number, created_at, and updated_at."""
    form = CapitalizationPolicyForm()
    expected_exclusions = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
    ]
    for field_name in expected_exclusions:
        assert field_name not in form.fields, f"{field_name} must be excluded from form.fields"
    assert CapitalizationPolicyForm.Meta.exclude == expected_exclusions


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_mass_assignment_protection(
    tenant_a,
):
    """Malicious payload attempting to force custom number or tenant injection is sanitized."""
    data = _assetdepreciation_policy_payload(
        name="Hacked Policy Number",
        number="ACTH-CUSTOM-OVERRIDE",
    )
    form = CapitalizationPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    saved = form.save()
    assert saved.number != "ACTH-CUSTOM-OVERRIDE"
    assert saved.number.startswith("ACTH-")


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_tenant_queryset_scoping(
    tenant_a,
    tenant_b,
    category_root_a,
    category_root_b,
    cip_account_a,
    expense_account_a,
    expense_account_b,
):
    """Category and GLAccount dropdowns in CapitalizationPolicyForm are scoped to tenant and active status."""
    # Create inactive category for tenant_a to verify active filter
    inactive_cat = AssetCategory.objects.create(
        tenant=tenant_a,
        code="INACT-CAT-01",
        name="Inactive IT Asset Category",
        is_active=False,
    )

    form_a = CapitalizationPolicyForm(tenant=tenant_a)

    # Asset Categories (must be tenant_a and is_active=True)
    assert category_root_a in form_a.fields["category"].queryset
    assert category_root_b not in form_a.fields["category"].queryset
    assert inactive_cat not in form_a.fields["category"].queryset

    # GL Accounts
    assert cip_account_a in form_a.fields["default_cip_account"].queryset
    assert expense_account_b not in form_a.fields["default_cip_account"].queryset
    assert expense_account_a in form_a.fields["default_expense_account"].queryset
    assert expense_account_b not in form_a.fields["default_expense_account"].queryset


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_rejects_cross_tenant_category(
    tenant_a,
    tenant_b,
    category_root_b,
):
    """Submitting another tenant's category fails validation on policy form."""
    data = _assetdepreciation_policy_payload(category=category_root_b)
    form = CapitalizationPolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "category" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_rejects_cross_tenant_accounts(
    tenant_a,
    tenant_b,
    expense_account_b,
):
    """Submitting another tenant's GL account fails validation on policy form."""
    data_cip = _assetdepreciation_policy_payload(default_cip_account=expense_account_b)
    form_cip = CapitalizationPolicyForm(data=data_cip, tenant=tenant_a)
    assert not form_cip.is_valid()
    assert "default_cip_account" in form_cip.errors

    data_exp = _assetdepreciation_policy_payload(default_expense_account=expense_account_b)
    form_exp = CapitalizationPolicyForm(data=data_exp, tenant=tenant_a)
    assert not form_exp.is_valid()
    assert "default_expense_account" in form_exp.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_reject_foreign_clean_direct(
    tenant_a,
    category_root_b,
):
    """Directly verify reject_foreign hook on CapitalizationPolicyForm.clean()."""
    form = CapitalizationPolicyForm(tenant=tenant_a)
    form.cleaned_data = {
        "category": category_root_b,
        "default_cip_account": None,
        "default_expense_account": None,
    }
    form.clean()
    assert "category" in form.errors
    assert "That record belongs to another workspace." in form.errors["category"]


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_validation_missing_name(tenant_a):
    """Missing required name fails policy form validation."""
    data = _assetdepreciation_policy_payload(name="")
    form = CapitalizationPolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_validation_invalid_scope(tenant_a):
    """Invalid policy_scope choice fails validation."""
    data = _assetdepreciation_policy_payload(policy_scope="unregulated_threshold")
    form = CapitalizationPolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "policy_scope" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_validation_invalid_classification(tenant_a):
    """Invalid default_classification choice fails validation."""
    data = _assetdepreciation_policy_payload(default_classification="off_balance_sheet")
    form = CapitalizationPolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "default_classification" in form.errors


@pytest.mark.django_db
def test_assetdepreciation_forms_policy_save_commit_false(tenant_a):
    """Saving policy form with commit=False sets tenant on instance."""
    data = _assetdepreciation_policy_payload(name="Deferred Commit Policy")
    form = CapitalizationPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    assert instance.pk is None
    assert instance.tenant == tenant_a
    instance.save()
    assert instance.pk is not None
