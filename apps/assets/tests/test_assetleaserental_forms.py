"""Unit and validation tests for Module 11.10 Lease & Rental Management forms."""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.assets.forms.AssetLeaseRental.AssetLeaseContracts import AssetLeaseContractForm
from apps.assets.forms.AssetLeaseRental.AssetLeaseSchedules import AssetLeaseScheduleForm
from apps.assets.forms.AssetLeaseRental.AssetLeaseModifications import AssetLeaseModificationForm
from apps.assets.forms.AssetLeaseRental.AssetLeaseBuyAnalyses import AssetLeaseBuyAnalysisForm
from apps.assets.models.AssetLeaseRental.AssetLeaseModifications import AssetLeaseModification


# ===========================================================================
# 1. AssetLeaseContractForm Tests
# ===========================================================================

@pytest.mark.django_db
def test_assetleaserental_contract_form_valid(tenant_a, vendor_party_a, operational_asset_a, category_root_a, fixed_asset_a):
    today = timezone.now().date()
    data = {
        "title": "CNC Center Operational Lease",
        "master_lease_agreement_ref": "MLA-2026-FORM-001",
        "lessor": str(vendor_party_a.pk),
        "asset": str(operational_asset_a.pk),
        "category": str(category_root_a.pk),
        "fixed_asset": str(fixed_asset_a.pk),
        "inception_date": today.strftime("%Y-%m-%d"),
        "commencement_date": today.strftime("%Y-%m-%d"),
        "expiration_date": (today + timezone.timedelta(days=730)).strftime("%Y-%m-%d"),
        "first_payment_date": today.strftime("%Y-%m-%d"),
        "lease_term_months": 24,
        "economic_life_months": 60,
        "payment_amount": "2500.00",
        "payment_frequency": "monthly",
        "payment_timing": "arrears",
        "discount_rate_pct": "6.0000",
        "fair_market_value": "75000.00",
        "initial_direct_costs": "500.00",
        "lease_incentives": "0.00",
        "residual_value_guarantee": "0.00",
        "purchase_option_price": "0.00",
        "transfer_of_ownership": False,
        "has_purchase_option": False,
        "is_specialized_asset": False,
        "classification": "operating",
        "status": "draft",
    }
    form = AssetLeaseContractForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetleaserental_contract_form_date_validation(tenant_a, vendor_party_a):
    today = timezone.now().date()
    data = {
        "title": "Invalid Date Lease",
        "lessor": str(vendor_party_a.pk),
        "commencement_date": today.strftime("%Y-%m-%d"),
        "expiration_date": (today - timezone.timedelta(days=10)).strftime("%Y-%m-%d"),
        "lease_term_months": 12,
        "payment_amount": "1000.00",
        "payment_frequency": "monthly",
        "payment_timing": "arrears",
        "discount_rate_pct": "5.0000",
        "fair_market_value": "10000.00",
    }
    form = AssetLeaseContractForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "expiration_date" in form.errors
    assert "cannot precede commencement date" in str(form.errors["expiration_date"])


@pytest.mark.django_db
def test_assetleaserental_contract_form_term_bounds(tenant_a, vendor_party_a):
    data = {
        "title": "Invalid Term Lease",
        "lessor": str(vendor_party_a.pk),
        "lease_term_months": 0,
        "payment_amount": "1000.00",
        "payment_frequency": "monthly",
        "payment_timing": "arrears",
        "discount_rate_pct": "5.0000",
    }
    form = AssetLeaseContractForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lease_term_months" in form.errors

    data["lease_term_months"] = 601
    form2 = AssetLeaseContractForm(data=data, tenant=tenant_a)
    assert not form2.is_valid()
    assert "lease_term_months" in form2.errors


@pytest.mark.django_db
def test_assetleaserental_contract_form_discount_rate_bounds(tenant_a, vendor_party_a):
    data = {
        "title": "Invalid Discount Rate Lease",
        "lessor": str(vendor_party_a.pk),
        "lease_term_months": 12,
        "payment_amount": "1000.00",
        "payment_frequency": "monthly",
        "payment_timing": "arrears",
        "discount_rate_pct": "-2.5000",
    }
    form = AssetLeaseContractForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "discount_rate_pct" in form.errors

    data["discount_rate_pct"] = "105.0000"
    form2 = AssetLeaseContractForm(data=data, tenant=tenant_a)
    assert not form2.is_valid()
    assert "discount_rate_pct" in form2.errors


@pytest.mark.django_db
def test_assetleaserental_contract_form_negative_amount(tenant_a, vendor_party_a):
    data = {
        "title": "Negative Payment Lease",
        "lessor": str(vendor_party_a.pk),
        "lease_term_months": 12,
        "payment_amount": "-1500.00",
        "payment_frequency": "monthly",
        "payment_timing": "arrears",
        "discount_rate_pct": "5.0000",
    }
    form = AssetLeaseContractForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "payment_amount" in form.errors


@pytest.mark.django_db
def test_assetleaserental_contract_form_reject_foreign_party(tenant_a, vendor_party_b):
    data = {
        "title": "Foreign Lessor Lease",
        "lessor": str(vendor_party_b.pk),
        "lease_term_months": 12,
        "payment_amount": "1000.00",
        "payment_frequency": "monthly",
        "payment_timing": "arrears",
        "discount_rate_pct": "5.0000",
    }
    form = AssetLeaseContractForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lessor" in form.errors


@pytest.mark.django_db
def test_assetleaserental_contract_form_queryset_scoping(tenant_a, vendor_party_a, vendor_party_b, operational_asset_a, operational_asset_b):
    form = AssetLeaseContractForm(tenant=tenant_a)
    lessor_pks = set(form.fields["lessor"].queryset.values_list("pk", flat=True))
    assert vendor_party_a.pk in lessor_pks
    assert vendor_party_b.pk not in lessor_pks

    asset_pks = set(form.fields["asset"].queryset.values_list("pk", flat=True))
    assert operational_asset_a.pk in asset_pks
    assert operational_asset_b.pk not in asset_pks


# ===========================================================================
# 2. AssetLeaseScheduleForm Tests
# ===========================================================================

@pytest.mark.django_db
def test_assetleaserental_schedule_form_valid(tenant_a, lease_contract_a):
    today = timezone.now().date()
    data = {
        "lease_contract": str(lease_contract_a.pk),
        "period_number": 99,
        "due_date": today.strftime("%Y-%m-%d"),
        "payment_amount": "4500.00",
        "beginning_liability": "100000.00",
        "interest_expense": "500.00",
        "principal_reduction": "4000.00",
        "ending_liability": "96000.00",
        "rou_depreciation": "3500.00",
        "ending_rou_asset_value": "90000.00",
        "status": "scheduled",
        "notes": "Custom schedule line form test",
    }
    form = AssetLeaseScheduleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetleaserental_schedule_form_duplicate_period(tenant_a, lease_contract_a, lease_schedule_a):
    data = {
        "lease_contract": str(lease_contract_a.pk),
        "period_number": lease_schedule_a.period_number,
        "due_date": timezone.now().date().strftime("%Y-%m-%d"),
        "payment_amount": "4500.00",
        "status": "scheduled",
    }
    form = AssetLeaseScheduleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "period_number" in form.errors
    assert "already exists for contract" in str(form.errors["period_number"])


@pytest.mark.django_db
def test_assetleaserental_schedule_form_reject_foreign_contract(tenant_a, lease_contract_b):
    data = {
        "lease_contract": str(lease_contract_b.pk),
        "period_number": 1,
        "due_date": timezone.now().date().strftime("%Y-%m-%d"),
        "payment_amount": "2000.00",
        "status": "scheduled",
    }
    form = AssetLeaseScheduleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lease_contract" in form.errors


@pytest.mark.django_db
def test_assetleaserental_schedule_form_queryset_scoping(tenant_a, lease_contract_a, lease_contract_b):
    form = AssetLeaseScheduleForm(tenant=tenant_a)
    contract_pks = set(form.fields["lease_contract"].queryset.values_list("pk", flat=True))
    assert lease_contract_a.pk in contract_pks
    assert lease_contract_b.pk not in contract_pks


# ===========================================================================
# 3. AssetLeaseModificationForm Tests
# ===========================================================================

@pytest.mark.django_db
def test_assetleaserental_modification_form_valid(tenant_a, lease_contract_a, admin_user):
    today = timezone.now().date()
    data = {
        "lease_contract": str(lease_contract_a.pk),
        "modification_type": "term_extension",
        "request_date": today.strftime("%Y-%m-%d"),
        "effective_date": today.strftime("%Y-%m-%d"),
        "prior_lease_liability": "80000.00",
        "revised_lease_liability": "95000.00",
        "prior_rou_asset_value": "75000.00",
        "revised_rou_asset_value": "90000.00",
        "gain_loss_on_modification": "0.00",
        "impairment_loss_recognized": "0.00",
        "revised_term_months": 48,
        "revised_payment_amount": "4200.00",
        "revised_discount_rate_pct": "6.0000",
        "requested_by": str(admin_user.pk),
        "status": "draft",
        "justification": "Extended operational requirements for plant expansion.",
    }
    form = AssetLeaseModificationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetleaserental_modification_form_discount_rate_bounds(tenant_a, lease_contract_a, admin_user):
    today = timezone.now().date()
    data = {
        "lease_contract": str(lease_contract_a.pk),
        "modification_type": "rate_change",
        "request_date": today.strftime("%Y-%m-%d"),
        "effective_date": today.strftime("%Y-%m-%d"),
        "revised_discount_rate_pct": "120.0000",
        "requested_by": str(admin_user.pk),
        "status": "draft",
        "justification": "Rate recalculation",
    }
    form = AssetLeaseModificationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "revised_discount_rate_pct" in form.errors


@pytest.mark.django_db
def test_assetleaserental_modification_form_term_bounds(tenant_a, lease_contract_a, admin_user):
    today = timezone.now().date()
    data = {
        "lease_contract": str(lease_contract_a.pk),
        "modification_type": "term_extension",
        "request_date": today.strftime("%Y-%m-%d"),
        "effective_date": today.strftime("%Y-%m-%d"),
        "revised_term_months": 0,
        "requested_by": str(admin_user.pk),
        "status": "draft",
        "justification": "Term change",
    }
    form = AssetLeaseModificationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "revised_term_months" in form.errors


@pytest.mark.django_db
def test_assetleaserental_modification_form_negative_amounts(tenant_a, lease_contract_a, admin_user):
    today = timezone.now().date()
    data = {
        "lease_contract": str(lease_contract_a.pk),
        "modification_type": "payment_reduction",
        "request_date": today.strftime("%Y-%m-%d"),
        "effective_date": today.strftime("%Y-%m-%d"),
        "revised_payment_amount": "-500.00",
        "requested_by": str(admin_user.pk),
        "status": "draft",
        "justification": "Negative payment invalid",
    }
    form = AssetLeaseModificationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "revised_payment_amount" in form.errors


@pytest.mark.django_db
def test_assetleaserental_modification_form_reject_foreign_contract(tenant_a, lease_contract_b, admin_user):
    today = timezone.now().date()
    data = {
        "lease_contract": str(lease_contract_b.pk),
        "modification_type": "term_extension",
        "request_date": today.strftime("%Y-%m-%d"),
        "effective_date": today.strftime("%Y-%m-%d"),
        "requested_by": str(admin_user.pk),
        "status": "draft",
        "justification": "Cross tenant modification injection",
    }
    form = AssetLeaseModificationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "lease_contract" in form.errors


@pytest.mark.django_db
def test_assetleaserental_modification_form_status_choices_restricted(tenant_a):
    form = AssetLeaseModificationForm(tenant=tenant_a)
    available_statuses = [choice[0] for choice in form.fields["status"].choices]
    assert "draft" in available_statuses
    assert "submitted" in available_statuses
    assert "approved" not in available_statuses
    assert "applied" not in available_statuses


# ===========================================================================
# 4. AssetLeaseBuyAnalysisForm Tests
# ===========================================================================

@pytest.mark.django_db
def test_assetleaserental_buy_analysis_form_valid(tenant_a, category_root_a, admin_user):
    data = {
        "title": "CNC Machining Center Buy vs Lease Analysis",
        "description": "Evaluation for 5-year replacement cycle.",
        "target_asset_name": "Haas VF-4SS CNC Mill",
        "category": str(category_root_a.pk),
        "expected_useful_life_years": "5.0",
        "purchase_price": "120000.00",
        "down_payment_pct": "20.00",
        "loan_interest_rate_pct": "6.50",
        "loan_term_years": "5.0",
        "estimated_salvage_value": "25000.00",
        "annual_maintenance_cost_buy": "4000.00",
        "annual_insurance_tax_buy": "2000.00",
        "lease_term_months": 60,
        "monthly_lease_payment": "2200.00",
        "upfront_lease_fees": "2000.00",
        "end_of_lease_purchase_option": "15000.00",
        "lessor_covers_maintenance": False,
        "annual_maintenance_cost_lease": "2000.00",
        "discount_rate_wacc_pct": "7.50",
        "corporate_tax_rate_pct": "21.00",
        "status": "draft",
        "evaluated_by": str(admin_user.pk),
        "evaluation_notes": "Preliminary financial analysis",
    }
    form = AssetLeaseBuyAnalysisForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetleaserental_buy_analysis_form_pct_bounds(tenant_a, category_root_a):
    data = {
        "title": "Invalid Pct Analysis",
        "target_asset_name": "Test Asset",
        "category": str(category_root_a.pk),
        "expected_useful_life_years": "5.0",
        "purchase_price": "100000.00",
        "down_payment_pct": "150.00",
        "discount_rate_wacc_pct": "8.00",
        "corporate_tax_rate_pct": "25.00",
        "lease_term_months": 36,
        "monthly_lease_payment": "2000.00",
    }
    form = AssetLeaseBuyAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "down_payment_pct" in form.errors


@pytest.mark.django_db
def test_assetleaserental_buy_analysis_form_negative_amounts(tenant_a, category_root_a):
    data = {
        "title": "Negative Price Analysis",
        "target_asset_name": "Test Asset",
        "category": str(category_root_a.pk),
        "expected_useful_life_years": "5.0",
        "purchase_price": "-10000.00",
        "lease_term_months": 36,
        "monthly_lease_payment": "2000.00",
    }
    form = AssetLeaseBuyAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "purchase_price" in form.errors


@pytest.mark.django_db
def test_assetleaserental_buy_analysis_form_reject_foreign_category(tenant_a, category_root_b):
    data = {
        "title": "Cross Tenant Category Analysis",
        "target_asset_name": "Test Asset",
        "category": str(category_root_b.pk),
        "expected_useful_life_years": "5.0",
        "purchase_price": "50000.00",
        "lease_term_months": 36,
        "monthly_lease_payment": "1200.00",
    }
    form = AssetLeaseBuyAnalysisForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "category" in form.errors


@pytest.mark.django_db
def test_assetleaserental_buy_analysis_form_queryset_scoping(tenant_a, category_root_a, category_root_b, admin_user, admin_b):
    form = AssetLeaseBuyAnalysisForm(tenant=tenant_a)
    cat_pks = set(form.fields["category"].queryset.values_list("pk", flat=True))
    assert category_root_a.pk in cat_pks
    assert category_root_b.pk not in cat_pks

    user_pks = set(form.fields["evaluated_by"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in user_pks
    assert admin_b.pk not in user_pks
