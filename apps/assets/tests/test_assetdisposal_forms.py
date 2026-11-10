"""Form unit tests for Sub-module 11.9: Asset Disposal & Retirement."""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.assets.forms.AssetDisposal import (
    AssetDisposalRequestForm,
    AssetResaleListingForm,
    AssetTradeInForm,
    AssetScrapSalvageForm,
    AssetDisposalAppraisalForm,
    AssetDisposalRejectForm,
    AssetResaleBidForm,
    AssetResaleAcceptForm,
    AssetScrapAbatementForm,
    AssetScrapCertificateForm,
)
from apps.assets.models import (
    AssetDisposalRequest,
    AssetResaleListing,
    AssetTradeIn,
    AssetScrapSalvage,
)


# ==============================================================================
# 1. AssetDisposalRequestForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_request_form_valid(tenant_a, fixed_asset_a, operational_asset_a, category_root_a, admin_user):
    data = {
        "title": "Machine Line Decommissioning",
        "fixed_asset": fixed_asset_a.pk,
        "operational_asset": operational_asset_a.pk,
        "category": category_root_a.pk,
        "disposal_method": "resale",
        "retirement_reason": "technological_obsolescence",
        "justification_notes": "Upgrading production line to high-speed CNC cell.",
        "acquisition_cost": "50000.00",
        "accumulated_depreciation": "30000.00",
        "net_book_value": "20000.00",
        "estimated_residual_value": "22000.00",
        "estimated_removal_cost": "1500.00",
    }
    form = AssetDisposalRequestForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.requested_by = admin_user
    instance.save()
    assert instance.pk is not None
    assert instance.title == "Machine Line Decommissioning"
    assert instance.net_book_value == Decimal("20000.00")


@pytest.mark.django_db
def test_assetdisposal_request_form_auto_derives_financials_from_asset(tenant_a, fixed_asset_a, category_root_a):
    fixed_asset_a.acquisition_cost = Decimal("85000.00")
    fixed_asset_a.accumulated_depreciation = Decimal("40000.00")
    fixed_asset_a.save()

    data = {
        "title": "Automated Financial Derivation Request",
        "fixed_asset": fixed_asset_a.pk,
        "category": category_root_a.pk,
        "disposal_method": "scrap_salvage",
        "retirement_reason": "end_of_life",
        "justification_notes": "Asset reached end of economic life.",
    }
    form = AssetDisposalRequestForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    cleaned = form.cleaned_data
    assert cleaned["acquisition_cost"] == Decimal("85000.00")
    assert cleaned["accumulated_depreciation"] == Decimal("40000.00")
    assert cleaned["net_book_value"] == Decimal("45000.00")


@pytest.mark.django_db
def test_assetdisposal_request_form_rejects_cross_tenant_fixed_asset(tenant_a, fixed_asset_b, category_root_a):
    data = {
        "title": "Cross Tenant Fixed Asset Test",
        "fixed_asset": fixed_asset_b.pk,
        "category": category_root_a.pk,
        "disposal_method": "resale",
        "retirement_reason": "end_of_life",
        "justification_notes": "Attempting cross-tenant injection.",
    }
    form = AssetDisposalRequestForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_assetdisposal_request_form_excludes_system_and_approver_fields(tenant_a):
    form = AssetDisposalRequestForm(tenant=tenant_a)
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "status" not in form.fields
    assert "approved_by" not in form.fields
    assert "completed_at" not in form.fields
    assert "realized_gain_loss" not in form.fields


# ==============================================================================
# 2. AssetResaleListingForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_resale_listing_form_valid(tenant_a, disposal_request_a, fixed_asset_a, vendor_party_a, admin_user):
    today = timezone.now().date()
    data = {
        "disposal_request": disposal_request_a.pk,
        "fixed_asset": fixed_asset_a.pk,
        "listing_channel": "online_marketplace",
        "listing_reference": "LOT-RESALE-001",
        "listing_date": today.isoformat(),
        "reserve_price": "25000.00",
        "asking_price": "30000.00",
        "broker_auctioneer": vendor_party_a.pk,
        "buyer": vendor_party_a.pk,
        "buyer_contact_name": "John Doe Machinery",
        "buyer_contact_email": "johndoe@example.com",
        "buyer_contact_phone": "+1-555-123-4567",
        "terms_and_conditions": "As-is, where-is.",
    }
    form = AssetResaleListingForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.managed_by = admin_user
    instance.save()
    assert instance.pk is not None
    assert instance.listing_reference == "LOT-RESALE-001"
    assert instance.reserve_price == Decimal("25000.00")


@pytest.mark.django_db
def test_assetdisposal_resale_listing_form_mismatched_asset_rejected(tenant_a, disposal_request_a, fixed_asset_b):
    today = timezone.now().date()
    data = {
        "disposal_request": disposal_request_a.pk,
        "fixed_asset": fixed_asset_b.pk,
        "listing_channel": "direct_sale",
        "listing_reference": "LOT-ERR-001",
        "listing_date": today.isoformat(),
    }
    form = AssetResaleListingForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_assetdisposal_resale_listing_form_rejects_cross_tenant_buyer(tenant_a, disposal_request_a, fixed_asset_a, vendor_party_b):
    today = timezone.now().date()
    data = {
        "disposal_request": disposal_request_a.pk,
        "fixed_asset": fixed_asset_a.pk,
        "listing_channel": "private_treaty",
        "listing_reference": "LOT-CROSS-001",
        "listing_date": today.isoformat(),
        "buyer": vendor_party_b.pk,
    }
    form = AssetResaleListingForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "buyer" in form.errors


@pytest.mark.django_db
def test_assetdisposal_resale_listing_form_excludes_system_fields(tenant_a):
    form = AssetResaleListingForm(tenant=tenant_a)
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "status" not in form.fields
    assert "payment_status" not in form.fields
    assert "net_sale_proceeds" not in form.fields


# ==============================================================================
# 3. AssetTradeInForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_trade_in_form_valid(tenant_a, disposal_request_a, fixed_asset_a, vendor_party_a, admin_user):
    today = timezone.now().date()
    data = {
        "disposal_request": disposal_request_a.pk,
        "retired_fixed_asset": fixed_asset_a.pk,
        "vendor": vendor_party_a.pk,
        "agreement_number": "AGR-TRD-VALID-01",
        "agreement_date": today.isoformat(),
        "handover_due_date": (today + timezone.timedelta(days=14)).isoformat(),
        "dealer_appraised_value": "15000.00",
        "trade_in_allowance": "12000.00",
        "replacement_asset_cost": "80000.00",
        "notes": "Vendor credit accepted for next-gen machine purchase.",
    }
    form = AssetTradeInForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.managed_by = admin_user
    instance.save()
    assert instance.pk is not None
    assert instance.agreement_number == "AGR-TRD-VALID-01"
    assert instance.trade_in_allowance == Decimal("12000.00")


@pytest.mark.django_db
def test_assetdisposal_trade_in_form_rejects_identical_retired_and_replacement_asset(tenant_a, disposal_request_a, fixed_asset_a, vendor_party_a):
    today = timezone.now().date()
    data = {
        "disposal_request": disposal_request_a.pk,
        "retired_fixed_asset": fixed_asset_a.pk,
        "replacement_fixed_asset": fixed_asset_a.pk,
        "vendor": vendor_party_a.pk,
        "agreement_number": "AGR-TRD-ERR-02",
        "agreement_date": today.isoformat(),
        "trade_in_allowance": "10000.00",
    }
    form = AssetTradeInForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "replacement_fixed_asset" in form.errors or "__all__" in form.errors


@pytest.mark.django_db
def test_assetdisposal_trade_in_form_rejects_cross_tenant_vendor(tenant_a, disposal_request_a, fixed_asset_a, vendor_party_b):
    today = timezone.now().date()
    data = {
        "disposal_request": disposal_request_a.pk,
        "retired_fixed_asset": fixed_asset_a.pk,
        "vendor": vendor_party_b.pk,
        "agreement_number": "AGR-CROSS-03",
        "agreement_date": today.isoformat(),
        "trade_in_allowance": "5000.00",
    }
    form = AssetTradeInForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "vendor" in form.errors


@pytest.mark.django_db
def test_assetdisposal_trade_in_form_excludes_authorized_by(tenant_a):
    form = AssetTradeInForm(tenant=tenant_a)
    assert "authorized_by" not in form.fields
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "status" not in form.fields


# ==============================================================================
# 4. AssetScrapSalvageForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_scrap_salvage_form_valid(tenant_a, disposal_request_a, fixed_asset_a, operational_asset_a, vendor_party_a, admin_user):
    today = timezone.now().date()
    data = {
        "disposal_request": disposal_request_a.pk,
        "fixed_asset": fixed_asset_a.pk,
        "operational_asset": operational_asset_a.pk,
        "recycler_partner": vendor_party_a.pk,
        "supervisor": admin_user.pk,
        "scrap_method": "recycling_recovery",
        "decommissioning_date": today.isoformat(),
        "total_scrap_weight_kg": "950.00",
        "salvage_proceeds": "1800.00",
        "dismantling_cost": "300.00",
        "has_hazardous_materials": True,
        "hazardous_waste_class": "Class 9 - Hydraulic Fluids",
        "epa_manifest_number": "EPA-FORM-001",
        "sanitization_method": "degreased_flushed",
        "cod_number": "COD-FORM-001",
        "notes": "Standard hazmat dismantling flow.",
    }
    form = AssetScrapSalvageForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.supervisor = admin_user
    instance.calculate_net_recovery()
    instance.save()
    assert instance.pk is not None
    assert instance.epa_manifest_number == "EPA-FORM-001"
    assert instance.net_salvage_recovery == Decimal("1500.00")


@pytest.mark.django_db
def test_assetdisposal_scrap_salvage_form_requires_hazmat_details_when_flagged(tenant_a, disposal_request_a, fixed_asset_a):
    data = {
        "disposal_request": disposal_request_a.pk,
        "fixed_asset": fixed_asset_a.pk,
        "scrap_method": "recycling_recovery",
        "has_hazardous_materials": True,
        "hazardous_waste_class": "",
    }
    form = AssetScrapSalvageForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "hazardous_waste_class" in form.errors or form.errors


@pytest.mark.django_db
def test_assetdisposal_scrap_salvage_form_rejects_cross_tenant_recycler(tenant_a, disposal_request_a, fixed_asset_a, vendor_party_b):
    data = {
        "disposal_request": disposal_request_a.pk,
        "fixed_asset": fixed_asset_a.pk,
        "scrap_method": "metal_shredding",
        "recycler_partner": vendor_party_b.pk,
    }
    form = AssetScrapSalvageForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "recycler_partner" in form.errors


# ==============================================================================
# 5. Workflow Action Forms Tests
# ==============================================================================

@pytest.mark.django_db
def test_assetdisposal_appraisal_form_valid(tenant_a, admin_user):
    data = {
        "appraised_by": admin_user.pk,
        "estimated_residual_value": "42000.00",
        "estimated_removal_cost": "3500.00",
        "appraisal_notes": "Fair market value appraised by certified equipment inspector.",
    }
    form = AssetDisposalAppraisalForm(tenant=tenant_a, data=data)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["estimated_residual_value"] == Decimal("42000.00")
    assert form.cleaned_data["estimated_removal_cost"] == Decimal("3500.00")


@pytest.mark.django_db
def test_assetdisposal_reject_form_requires_reason():
    data = {"rejection_reason": ""}
    form = AssetDisposalRejectForm(data=data)
    assert not form.is_valid()
    assert "rejection_reason" in form.errors


@pytest.mark.django_db
def test_assetdisposal_resale_bid_form_valid():
    data = {
        "bid_amount": "39500.00",
        "bidder_name": "Midwest Heavy Tools Ltd",
        "bidder_email": "procurement@midwest.com",
        "bidder_phone": "+1-555-987-6543",
    }
    form = AssetResaleBidForm(data=data)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["bid_amount"] == Decimal("39500.00")


@pytest.mark.django_db
def test_assetdisposal_resale_accept_form_valid(tenant_a):
    data = {
        "final_sale_amount": "40000.00",
        "commission_rate_percent": "7.50",
        "buyer_contact_name": "Apex Precision Ltd",
    }
    form = AssetResaleAcceptForm(tenant=tenant_a, data=data)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["final_sale_amount"] == Decimal("40000.00")
    assert form.cleaned_data["commission_rate_percent"] == Decimal("7.50")


@pytest.mark.django_db
def test_assetdisposal_scrap_abatement_form_valid():
    data = {
        "epa_manifest_number": "EPA-ABATEMENT-2026",
        "abatement_notes": "Certified decontamination completed.",
    }
    form = AssetScrapAbatementForm(data=data)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["epa_manifest_number"] == "EPA-ABATEMENT-2026"


@pytest.mark.django_db
def test_assetdisposal_scrap_certificate_form_valid():
    today = timezone.now().date()
    data = {
        "cod_number": "COD-FINAL-2026",
        "cod_issue_date": today.isoformat(),
        "cod_issuing_agency": "State Environmental Recycling Board",
    }
    form = AssetScrapCertificateForm(data=data)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["cod_number"] == "COD-FINAL-2026"
