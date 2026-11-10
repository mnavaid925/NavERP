"""Form validation and tenant isolation test suite for Sub-module 11.8: Warranty & Insurance Management.

Covers all 4 ModelForms:
- AssetWarrantyForm (AssetWarranty)
- AssetWarrantyClaimForm (AssetWarrantyClaim)
- AssetInsurancePolicyForm (AssetInsurancePolicy)
- AssetInsuranceClaimForm (AssetInsuranceClaim)

Invariants pinned:
1. Exclusions & mass-assignment protection: verify tenant, auto-generated number,
   and view-owned workflow fields are excluded from Meta.fields and cannot be injected.
2. Tenant FK dropdown filtering: verify foreign key dropdown querysets only list tenant_a
   records and exclude tenant_b records.
3. Defense-in-depth reject_foreign(): verify injecting a tenant_b foreign key into any
   foreign key field triggers a ValidationError in clean().
4. Currency handling: verify currency queryset is global and active-only.
5. Date interval validations:
   - AssetWarrantyForm: end_date < start_date raises ValidationError.
   - AssetInsurancePolicyForm: expiration_date < effective_date raises ValidationError.
6. Deductible business logic validations:
   - AssetWarrantyClaimForm: deductible_applied > claimed_amount raises ValidationError.
   - AssetInsuranceClaimForm: deductible_applied > claimed_loss_amount raises ValidationError.
7. Save flow: saving valid form with commit=False, setting tenant and auto-numbering,
   persists to database cleanly.
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounting.models import Currency, FixedAsset
from apps.assets.forms import (
    AssetInsuranceClaimForm,
    AssetInsurancePolicyForm,
    AssetWarrantyClaimForm,
    AssetWarrantyForm,
)
from apps.assets.models import (
    AssetCategory,
    AssetIncidentReport,
    AssetInsuranceClaim,
    AssetInsurancePolicy,
    AssetMaintenanceRequest,
    AssetServiceContract,
    AssetWarranty,
    AssetWarrantyClaim,
)
from apps.core.models import Document, Party, PartyRole
from apps.scm.models import Asset as OperationalAsset

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helpers (strictly prefixed with _assetwarrantyinsurance_)
# ==============================================================================

def _assetwarrantyinsurance_ensure_vendor_role(party):
    """Ensure party has an active vendor role to satisfy vendor-filtered FK dropdowns."""
    PartyRole.objects.get_or_create(
        tenant=party.tenant,
        party=party,
        role="vendor",
        defaults={"status": "active"},
    )
    return party


def _assetwarrantyinsurance_valid_warranty_data(currency, warrantor_party, **overrides):
    """Build a valid payload for AssetWarrantyForm."""
    today = timezone.now().date()
    data = {
        "title": "Industrial Compressor OEM Factory Warranty",
        "warranty_certificate_number": "CERT-2026-COMP-01",
        "warrantor_party": str(warrantor_party.pk),
        "currency": str(currency.pk),
        "warranty_type": "oem_standard",
        "coverage_scope": "comprehensive",
        "start_date": today.strftime("%Y-%m-%d"),
        "end_date": (today + timezone.timedelta(days=365)).strftime("%Y-%m-%d"),
        "meter_type": "hours",
        "meter_limit": "5000",
        "parts_coverage_percent": "100",
        "labor_coverage_percent": "100",
        "travel_dispatch_covered": True,
        "deductible_amount": "250.00",
        "contract_purchase_price": "1500.00",
        "terms_and_conditions": "Full replacement and repair coverage against manufacturing defects.",
    }
    data.update(overrides)
    return data


def _assetwarrantyinsurance_valid_warranty_claim_data(currency, warranty, **overrides):
    """Build a valid payload for AssetWarrantyClaimForm."""
    today = timezone.now().date()
    data = {
        "title": "High-Pressure Impeller Bearing Failure Claim",
        "warranty": str(warranty.pk),
        "incident_date": today.strftime("%Y-%m-%d"),
        "operating_meter_at_failure": "1420",
        "defect_description": "Excessive bearing play and high heat vibration trip.",
        "warrantor_claim_reference": "OEM-RMA-84912",
        "currency": str(currency.pk),
        "claimed_amount": "3200.00",
        "deductible_applied": "250.00",
        "resolution_type": "on_site_repair",
        "part_return_status": "return_required_pending",
        "rma_tracking_number": "1Z9999999999999999",
        "settlement_notes": "Shipped to OEM regional repair depot.",
    }
    data.update(overrides)
    return data


def _assetwarrantyinsurance_valid_insurance_policy_data(currency, underwriter_party, **overrides):
    """Build a valid payload for AssetInsurancePolicyForm."""
    today = timezone.now().date()
    data = {
        "policy_number": "POL-2026-IND-MACH-01",
        "title": "Machinery Breakdown & Boiler Explosion Policy",
        "policy_type": "machinery_breakdown",
        "valuation_basis": "replacement_cost_value",
        "underwriter_party": str(underwriter_party.pk),
        "currency": str(currency.pk),
        "effective_date": today.strftime("%Y-%m-%d"),
        "expiration_date": (today + timezone.timedelta(days=365)).strftime("%Y-%m-%d"),
        "total_insured_value": "350000.00",
        "deductible_retention": "5000.00",
        "coinsurance_percentage": "100",
        "annual_premium": "12500.00",
        "premium_frequency": "annual",
        "coverage_terms": "Sudden and accidental electrical and mechanical breakdown schedule.",
    }
    data.update(overrides)
    return data


def _assetwarrantyinsurance_valid_insurance_claim_data(currency, policy, **overrides):
    """Build a valid payload for AssetInsuranceClaimForm."""
    today = timezone.now().date()
    data = {
        "title": "Main Transformer Stator Flashover Claim",
        "policy": str(policy.pk),
        "incident_date": today.strftime("%Y-%m-%d"),
        "peril_type": "electrical_arcing_surge",
        "incident_description": "Severe voltage transient punctured winding insulation causing arcing.",
        "incident_location": "Building A - Switchgear Vault",
        "carrier_claim_number": "CLM-TRV-2026-00491",
        "adjuster_name": "Sarah Jenkins (Crawford & Co)",
        "currency": str(currency.pk),
        "claimed_loss_amount": "28000.00",
        "deductible_applied": "5000.00",
        "salvage_recovery_amount": "1200.00",
        "settlement_method": "direct_indemnity_check",
        "settlement_notes": "Forensic electrical engineer inspection concluded utility surge.",
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. AssetWarrantyForm Tests
# ==============================================================================

def test_assetwarrantyinsurance_warranty_form_valid_minimal(tenant_a, currency_usd, vendor_party_a):
    """Form validates successfully with minimal required fields."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    today = timezone.now().date()
    data = {
        "title": "Basic Electric Motor OEM Warranty",
        "warrantor_party": str(vendor_party_a.pk),
        "currency": str(currency_usd.pk),
        "warranty_type": "oem_standard",
        "coverage_scope": "comprehensive",
        "start_date": today.strftime("%Y-%m-%d"),
        "end_date": (today + timezone.timedelta(days=365)).strftime("%Y-%m-%d"),
        "meter_type": "hours",
        "parts_coverage_percent": "100",
        "labor_coverage_percent": "100",
        "deductible_amount": "0.00",
        "contract_purchase_price": "0.00",
    }
    form = AssetWarrantyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_warranty_form_valid_full(
    tenant_a,
    currency_usd,
    vendor_party_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    service_contract_a,
):
    """Form validates successfully with all fields populated."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    doc_a = Document.objects.create(tenant=tenant_a, name="Warranty Certificate", file="contracts/cert.pdf")
    data = _assetwarrantyinsurance_valid_warranty_data(
        currency_usd,
        vendor_party_a,
        fixed_asset=str(fixed_asset_a.pk),
        operational_asset=str(operational_asset_a.pk),
        asset_category=str(category_root_a.pk),
        service_contract=str(service_contract_a.pk),
        contract_document=str(doc_a.pk),
    )
    form = AssetWarrantyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_warranty_form_required_fields(tenant_a):
    """Form fails validation when required fields are missing."""
    form = AssetWarrantyForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "start_date" in form.errors
    assert "end_date" in form.errors


def test_assetwarrantyinsurance_warranty_form_exclusions_and_mass_assignment(
    tenant_a,
    currency_usd,
    vendor_party_a,
    admin_user,
):
    """Verify system, lifecycle, and view-owned workflow fields are excluded from Meta.fields."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    form = AssetWarrantyForm(tenant=tenant_a)
    excluded = ["tenant", "number", "status", "registered_by", "created_at", "updated_at"]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from AssetWarrantyForm"

    # Attempt injecting malicious status and number
    data = _assetwarrantyinsurance_valid_warranty_data(currency_usd, vendor_party_a)
    data.update({
        "status": "voided",
        "number": "AWAR-MALICIOUS-9999",
    })
    form_post = AssetWarrantyForm(data=data, tenant=tenant_a)
    assert form_post.is_valid(), form_post.errors
    warranty = form_post.save(commit=False)
    warranty.registered_by = admin_user
    warranty.save()

    assert warranty.status == "active"
    assert warranty.number != "AWAR-MALICIOUS-9999"
    assert warranty.number.startswith("AWAR-")


def test_assetwarrantyinsurance_warranty_form_fk_dropdown_filtering_tenant_isolation(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    vendor_party_a,
    vendor_party_b,
    category_root_a,
    category_root_b,
    service_contract_a,
    service_contract_b,
):
    """Form dropdown querysets must only contain tenant_a records, never tenant_b."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_b)
    doc_a = Document.objects.create(tenant=tenant_a, name="Doc A", file="a.pdf")
    doc_b = Document.objects.create(tenant=tenant_b, name="Doc B", file="b.pdf")

    form = AssetWarrantyForm(tenant=tenant_a)

    assert fixed_asset_a in form.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form.fields["fixed_asset"].queryset

    assert operational_asset_a in form.fields["operational_asset"].queryset
    assert operational_asset_b not in form.fields["operational_asset"].queryset

    assert category_root_a in form.fields["asset_category"].queryset
    assert category_root_b not in form.fields["asset_category"].queryset

    assert vendor_party_a in form.fields["warrantor_party"].queryset
    assert vendor_party_b not in form.fields["warrantor_party"].queryset

    assert service_contract_a in form.fields["service_contract"].queryset
    assert service_contract_b not in form.fields["service_contract"].queryset

    assert doc_a in form.fields["contract_document"].queryset
    assert doc_b not in form.fields["contract_document"].queryset


def test_assetwarrantyinsurance_warranty_form_reject_foreign_fixed_asset(
    tenant_a,
    currency_usd,
    vendor_party_a,
    fixed_asset_b,
):
    """Cross-tenant fixed asset is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    data = _assetwarrantyinsurance_valid_warranty_data(
        currency_usd,
        vendor_party_a,
        fixed_asset=str(fixed_asset_b.pk),
    )
    # 1. Scoped queryset blocks it
    form = AssetWarrantyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetWarrantyForm(data=data, tenant=tenant_a)
    form_wide.fields["fixed_asset"].queryset = FixedAsset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["fixed_asset"]


def test_assetwarrantyinsurance_warranty_form_reject_foreign_operational_asset(
    tenant_a,
    currency_usd,
    vendor_party_a,
    operational_asset_b,
):
    """Cross-tenant operational asset is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    data = _assetwarrantyinsurance_valid_warranty_data(
        currency_usd,
        vendor_party_a,
        operational_asset=str(operational_asset_b.pk),
    )
    form_wide = AssetWarrantyForm(data=data, tenant=tenant_a)
    form_wide.fields["operational_asset"].queryset = OperationalAsset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["operational_asset"]


def test_assetwarrantyinsurance_warranty_form_reject_foreign_warrantor_party(
    tenant_a,
    currency_usd,
    vendor_party_b,
):
    """Cross-tenant warrantor party is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_b)
    data = _assetwarrantyinsurance_valid_warranty_data(
        currency_usd,
        vendor_party_b,
    )
    form_wide = AssetWarrantyForm(data=data, tenant=tenant_a)
    form_wide.fields["warrantor_party"].queryset = Party.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["warrantor_party"]


def test_assetwarrantyinsurance_warranty_form_reject_foreign_asset_category(
    tenant_a,
    currency_usd,
    vendor_party_a,
    category_root_b,
):
    """Cross-tenant asset category is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    data = _assetwarrantyinsurance_valid_warranty_data(
        currency_usd,
        vendor_party_a,
        asset_category=str(category_root_b.pk),
    )
    form_wide = AssetWarrantyForm(data=data, tenant=tenant_a)
    form_wide.fields["asset_category"].queryset = AssetCategory.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["asset_category"]


def test_assetwarrantyinsurance_warranty_form_reject_foreign_service_contract(
    tenant_a,
    currency_usd,
    vendor_party_a,
    service_contract_b,
):
    """Cross-tenant service contract is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    data = _assetwarrantyinsurance_valid_warranty_data(
        currency_usd,
        vendor_party_a,
        service_contract=str(service_contract_b.pk),
    )
    form_wide = AssetWarrantyForm(data=data, tenant=tenant_a)
    form_wide.fields["service_contract"].queryset = AssetServiceContract.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["service_contract"]


def test_assetwarrantyinsurance_warranty_form_reject_foreign_contract_document(
    tenant_a,
    tenant_b,
    currency_usd,
    vendor_party_a,
):
    """Cross-tenant document is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    doc_b = Document.objects.create(tenant=tenant_b, name="Doc B", file="b.pdf")
    data = _assetwarrantyinsurance_valid_warranty_data(
        currency_usd,
        vendor_party_a,
        contract_document=str(doc_b.pk),
    )
    form_wide = AssetWarrantyForm(data=data, tenant=tenant_a)
    form_wide.fields["contract_document"].queryset = Document.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["contract_document"]


def test_assetwarrantyinsurance_warranty_form_currency_global_active(tenant_a, currency_usd):
    """Currency queryset is global and active-only."""
    inactive_curr = Currency.objects.create(code="INACT1", name="Inactive Currency", symbol="I", is_active=False)
    form = AssetWarrantyForm(tenant=tenant_a)
    assert currency_usd in form.fields["currency"].queryset
    assert inactive_curr not in form.fields["currency"].queryset


def test_assetwarrantyinsurance_warranty_form_date_validation_end_before_start(
    tenant_a,
    currency_usd,
    vendor_party_a,
):
    """end_date < start_date raises a ValidationError on end_date."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    today = timezone.now().date()
    data = _assetwarrantyinsurance_valid_warranty_data(
        currency_usd,
        vendor_party_a,
        start_date=today.strftime("%Y-%m-%d"),
        end_date=(today - timezone.timedelta(days=1)).strftime("%Y-%m-%d"),
    )
    form = AssetWarrantyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "end_date" in form.errors
    assert "Warranty expiration date cannot precede inception date." in form.errors["end_date"]


def test_assetwarrantyinsurance_warranty_form_date_validation_same_day_valid(
    tenant_a,
    currency_usd,
    vendor_party_a,
):
    """end_date == start_date is a valid 1-day warranty coverage."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    today = timezone.now().date()
    data = _assetwarrantyinsurance_valid_warranty_data(
        currency_usd,
        vendor_party_a,
        start_date=today.strftime("%Y-%m-%d"),
        end_date=today.strftime("%Y-%m-%d"),
    )
    form = AssetWarrantyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_warranty_form_save_flow(tenant_a, currency_usd, vendor_party_a, admin_user):
    """Save flow sets tenant, registered_by, and generates sequential number correctly."""
    _assetwarrantyinsurance_ensure_vendor_role(vendor_party_a)
    data = _assetwarrantyinsurance_valid_warranty_data(currency_usd, vendor_party_a)
    form = AssetWarrantyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    warranty = form.save(commit=False)
    assert warranty.tenant == tenant_a
    warranty.registered_by = admin_user
    warranty.save()

    assert warranty.pk is not None
    assert warranty.number.startswith("AWAR-")
    assert warranty.registered_by == admin_user
    assert warranty.title == "Industrial Compressor OEM Factory Warranty"


# ==============================================================================
# 2. AssetWarrantyClaimForm Tests
# ==============================================================================

def test_assetwarrantyinsurance_warranty_claim_form_valid_minimal(tenant_a, currency_usd, warranty_a):
    """Form validates successfully with minimal required fields."""
    today = timezone.now().date()
    data = {
        "title": "Minor Component Fracture Claim",
        "warranty": str(warranty_a.pk),
        "incident_date": today.strftime("%Y-%m-%d"),
        "defect_description": "Crack on casing detected during routine servicing.",
        "currency": str(currency_usd.pk),
        "claimed_amount": "1200.00",
        "deductible_applied": "0.00",
        "resolution_type": "pending_evaluation",
        "part_return_status": "not_required",
    }
    form = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_warranty_claim_form_valid_full(
    tenant_a,
    currency_usd,
    warranty_a,
    fixed_asset_a,
    operational_asset_a,
    maintenance_request_a,
):
    """Form validates successfully with full field set."""
    doc_a = Document.objects.create(tenant=tenant_a, name="Claim Diagnostic Report", file="claims/diag.pdf")
    data = _assetwarrantyinsurance_valid_warranty_claim_data(
        currency_usd,
        warranty_a,
        fixed_asset=str(fixed_asset_a.pk),
        operational_asset=str(operational_asset_a.pk),
        maintenance_request=str(maintenance_request_a.pk),
        supporting_document=str(doc_a.pk),
    )
    form = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_warranty_claim_form_required_fields(tenant_a):
    """Form fails validation when required fields are missing."""
    form = AssetWarrantyClaimForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "warranty" in form.errors
    assert "incident_date" in form.errors
    assert "defect_description" in form.errors
    assert "claimed_amount" in form.errors


def test_assetwarrantyinsurance_warranty_claim_form_exclusions_and_mass_assignment(
    tenant_a,
    currency_usd,
    warranty_a,
    admin_user,
):
    """Verify system and workflow fields are excluded from AssetWarrantyClaimForm."""
    form = AssetWarrantyClaimForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "claim_status",
        "filed_by",
        "approved_by",
        "approved_amount",
        "rejected_amount",
        "net_recovery_amount",
        "settlement_date",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from AssetWarrantyClaimForm"

    # Attempt injecting status, approved_amount, and number
    data = _assetwarrantyinsurance_valid_warranty_claim_data(currency_usd, warranty_a)
    data.update({
        "claim_status": "approved",
        "approved_amount": "50000.00",
        "number": "AWCL-HACK-01",
    })
    form_post = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    assert form_post.is_valid(), form_post.errors
    claim = form_post.save(commit=False)
    claim.filed_by = admin_user
    claim.save()

    assert claim.claim_status == "draft"
    assert claim.approved_amount == Decimal("0.00")
    assert claim.number != "AWCL-HACK-01"
    assert claim.number.startswith("AWCL-")


def test_assetwarrantyinsurance_warranty_claim_form_fk_dropdown_filtering_tenant_isolation(
    tenant_a,
    tenant_b,
    warranty_a,
    warranty_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    maintenance_request_a,
    maintenance_request_b,
):
    """Form dropdown querysets must only contain tenant_a records, never tenant_b."""
    doc_a = Document.objects.create(tenant=tenant_a, name="Doc A", file="a.pdf")
    doc_b = Document.objects.create(tenant=tenant_b, name="Doc B", file="b.pdf")

    form = AssetWarrantyClaimForm(tenant=tenant_a)

    assert warranty_a in form.fields["warranty"].queryset
    assert warranty_b not in form.fields["warranty"].queryset

    assert fixed_asset_a in form.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form.fields["fixed_asset"].queryset

    assert operational_asset_a in form.fields["operational_asset"].queryset
    assert operational_asset_b not in form.fields["operational_asset"].queryset

    assert maintenance_request_a in form.fields["maintenance_request"].queryset
    assert maintenance_request_b not in form.fields["maintenance_request"].queryset

    assert doc_a in form.fields["supporting_document"].queryset
    assert doc_b not in form.fields["supporting_document"].queryset


def test_assetwarrantyinsurance_warranty_claim_form_reject_foreign_warranty(
    tenant_a,
    currency_usd,
    warranty_b,
):
    """Cross-tenant warranty is rejected by reject_foreign()."""
    data = _assetwarrantyinsurance_valid_warranty_claim_data(
        currency_usd,
        warranty_b,
    )
    # Scoped queryset rejects choice
    form = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "warranty" in form.errors

    # Widened queryset triggers reject_foreign
    form_wide = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["warranty"].queryset = AssetWarranty.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["warranty"]


def test_assetwarrantyinsurance_warranty_claim_form_reject_foreign_fixed_asset(
    tenant_a,
    currency_usd,
    warranty_a,
    fixed_asset_b,
):
    """Cross-tenant fixed asset is rejected by reject_foreign()."""
    data = _assetwarrantyinsurance_valid_warranty_claim_data(
        currency_usd,
        warranty_a,
        fixed_asset=str(fixed_asset_b.pk),
    )
    form_wide = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["fixed_asset"].queryset = FixedAsset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["fixed_asset"]


def test_assetwarrantyinsurance_warranty_claim_form_reject_foreign_operational_asset(
    tenant_a,
    currency_usd,
    warranty_a,
    operational_asset_b,
):
    """Cross-tenant operational asset is rejected by reject_foreign()."""
    data = _assetwarrantyinsurance_valid_warranty_claim_data(
        currency_usd,
        warranty_a,
        operational_asset=str(operational_asset_b.pk),
    )
    form_wide = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["operational_asset"].queryset = OperationalAsset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["operational_asset"]


def test_assetwarrantyinsurance_warranty_claim_form_reject_foreign_maintenance_request(
    tenant_a,
    currency_usd,
    warranty_a,
    maintenance_request_b,
):
    """Cross-tenant maintenance request is rejected by reject_foreign()."""
    data = _assetwarrantyinsurance_valid_warranty_claim_data(
        currency_usd,
        warranty_a,
        maintenance_request=str(maintenance_request_b.pk),
    )
    form_wide = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["maintenance_request"].queryset = AssetMaintenanceRequest.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["maintenance_request"]


def test_assetwarrantyinsurance_warranty_claim_form_reject_foreign_supporting_document(
    tenant_a,
    tenant_b,
    currency_usd,
    warranty_a,
):
    """Cross-tenant supporting document is rejected by reject_foreign()."""
    doc_b = Document.objects.create(tenant=tenant_b, name="Doc B", file="b.pdf")
    data = _assetwarrantyinsurance_valid_warranty_claim_data(
        currency_usd,
        warranty_a,
        supporting_document=str(doc_b.pk),
    )
    form_wide = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["supporting_document"].queryset = Document.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["supporting_document"]


def test_assetwarrantyinsurance_warranty_claim_form_currency_global_active(tenant_a, currency_usd):
    """Currency queryset is global and active-only."""
    inactive_curr = Currency.objects.create(code="INACT2", name="Inactive 2", symbol="I", is_active=False)
    form = AssetWarrantyClaimForm(tenant=tenant_a)
    assert currency_usd in form.fields["currency"].queryset
    assert inactive_curr not in form.fields["currency"].queryset


def test_assetwarrantyinsurance_warranty_claim_form_deductible_exceeds_claimed(
    tenant_a,
    currency_usd,
    warranty_a,
):
    """Deductible applied cannot exceed total claimed amount."""
    data = _assetwarrantyinsurance_valid_warranty_claim_data(
        currency_usd,
        warranty_a,
        claimed_amount="500.00",
        deductible_applied="800.00",
    )
    form = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "deductible_applied" in form.errors
    assert "Deductible applied cannot exceed total claimed amount." in form.errors["deductible_applied"]


def test_assetwarrantyinsurance_warranty_claim_form_deductible_equal_to_claimed_valid(
    tenant_a,
    currency_usd,
    warranty_a,
):
    """Deductible equal to claimed amount is valid (net payout is 0)."""
    data = _assetwarrantyinsurance_valid_warranty_claim_data(
        currency_usd,
        warranty_a,
        claimed_amount="500.00",
        deductible_applied="500.00",
    )
    form = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_warranty_claim_form_save_flow(
    tenant_a,
    currency_usd,
    warranty_a,
    admin_user,
):
    """Save flow sets tenant, filed_by, and generates sequential claim number."""
    data = _assetwarrantyinsurance_valid_warranty_claim_data(currency_usd, warranty_a)
    form = AssetWarrantyClaimForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    claim = form.save(commit=False)
    assert claim.tenant == tenant_a
    claim.filed_by = admin_user
    claim.save()

    assert claim.pk is not None
    assert claim.number.startswith("AWCL-")
    assert claim.filed_by == admin_user
    assert claim.warranty == warranty_a
    assert claim.title == "High-Pressure Impeller Bearing Failure Claim"


# ==============================================================================
# 3. AssetInsurancePolicyForm Tests
# ==============================================================================

def test_assetwarrantyinsurance_insurance_policy_form_valid_minimal(
    tenant_a,
    currency_usd,
    underwriter_party_a,
):
    """Form validates successfully with minimal required fields."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    today = timezone.now().date()
    data = {
        "policy_number": "POL-2026-MIN-001",
        "title": "Minimal Machinery Property Policy",
        "policy_type": "machinery_breakdown",
        "valuation_basis": "replacement_cost_value",
        "underwriter_party": str(underwriter_party_a.pk),
        "currency": str(currency_usd.pk),
        "effective_date": today.strftime("%Y-%m-%d"),
        "expiration_date": (today + timezone.timedelta(days=365)).strftime("%Y-%m-%d"),
        "total_insured_value": "100000.00",
        "deductible_retention": "5000.00",
        "coinsurance_percentage": "100",
        "annual_premium": "4000.00",
        "premium_frequency": "annual",
    }
    form = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_insurance_policy_form_valid_full(
    tenant_a,
    currency_usd,
    underwriter_party_a,
    broker_party_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    admin_user,
):
    """Form validates successfully with full field set."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    _assetwarrantyinsurance_ensure_vendor_role(broker_party_a)
    doc_a = Document.objects.create(tenant=tenant_a, name="Full Policy Binder", file="insurance/binder.pdf")
    data = _assetwarrantyinsurance_valid_insurance_policy_data(
        currency_usd,
        underwriter_party_a,
        broker_party=str(broker_party_a.pk),
        fixed_asset=str(fixed_asset_a.pk),
        operational_asset=str(operational_asset_a.pk),
        asset_category=str(category_root_a.pk),
        policy_document=str(doc_a.pk),
        risk_manager=str(admin_user.pk),
    )
    form = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_insurance_policy_form_required_fields(tenant_a):
    """Form fails validation when required fields are missing."""
    form = AssetInsurancePolicyForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "policy_number" in form.errors
    assert "title" in form.errors
    assert "effective_date" in form.errors
    assert "expiration_date" in form.errors


def test_assetwarrantyinsurance_insurance_policy_form_exclusions_and_mass_assignment(
    tenant_a,
    currency_usd,
    underwriter_party_a,
    admin_user,
):
    """Verify system, lifecycle, and view-owned workflow fields are excluded from Meta.fields."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    form = AssetInsurancePolicyForm(tenant=tenant_a)
    excluded = ["tenant", "number", "status", "created_at", "updated_at"]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from AssetInsurancePolicyForm"

    # Attempt injecting malicious status and number
    data = _assetwarrantyinsurance_valid_insurance_policy_data(currency_usd, underwriter_party_a)
    data.update({
        "status": "voided",
        "number": "AINS-MALICIOUS-9999",
    })
    form_post = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    assert form_post.is_valid(), form_post.errors
    policy = form_post.save(commit=False)
    policy.risk_manager = admin_user
    policy.save()

    assert policy.status == "active"
    assert policy.number != "AINS-MALICIOUS-9999"
    assert policy.number.startswith("AINS-")


def test_assetwarrantyinsurance_insurance_policy_form_fk_dropdown_filtering_tenant_isolation(
    tenant_a,
    tenant_b,
    underwriter_party_a,
    underwriter_party_b,
    broker_party_a,
    broker_party_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    category_root_a,
    category_root_b,
    admin_user,
    admin_b,
):
    """Form dropdown querysets must only contain tenant_a records, never tenant_b."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_b)
    _assetwarrantyinsurance_ensure_vendor_role(broker_party_a)
    _assetwarrantyinsurance_ensure_vendor_role(broker_party_b)
    doc_a = Document.objects.create(tenant=tenant_a, name="Doc A", file="a.pdf")
    doc_b = Document.objects.create(tenant=tenant_b, name="Doc B", file="b.pdf")

    form = AssetInsurancePolicyForm(tenant=tenant_a)

    assert underwriter_party_a in form.fields["underwriter_party"].queryset
    assert underwriter_party_b not in form.fields["underwriter_party"].queryset

    assert broker_party_a in form.fields["broker_party"].queryset
    assert broker_party_b not in form.fields["broker_party"].queryset

    assert fixed_asset_a in form.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form.fields["fixed_asset"].queryset

    assert operational_asset_a in form.fields["operational_asset"].queryset
    assert operational_asset_b not in form.fields["operational_asset"].queryset

    assert category_root_a in form.fields["asset_category"].queryset
    assert category_root_b not in form.fields["asset_category"].queryset

    assert doc_a in form.fields["policy_document"].queryset
    assert doc_b not in form.fields["policy_document"].queryset

    assert admin_user in form.fields["risk_manager"].queryset
    assert admin_b not in form.fields["risk_manager"].queryset


def test_assetwarrantyinsurance_insurance_policy_form_reject_foreign_underwriter(
    tenant_a,
    currency_usd,
    underwriter_party_b,
):
    """Cross-tenant underwriter party is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_b)
    data = _assetwarrantyinsurance_valid_insurance_policy_data(
        currency_usd,
        underwriter_party_b,
    )
    form_wide = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    form_wide.fields["underwriter_party"].queryset = Party.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["underwriter_party"]


def test_assetwarrantyinsurance_insurance_policy_form_reject_foreign_broker(
    tenant_a,
    currency_usd,
    underwriter_party_a,
    broker_party_b,
):
    """Cross-tenant broker party is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    _assetwarrantyinsurance_ensure_vendor_role(broker_party_b)
    data = _assetwarrantyinsurance_valid_insurance_policy_data(
        currency_usd,
        underwriter_party_a,
        broker_party=str(broker_party_b.pk),
    )
    form_wide = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    form_wide.fields["broker_party"].queryset = Party.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["broker_party"]


def test_assetwarrantyinsurance_insurance_policy_form_reject_foreign_fixed_asset(
    tenant_a,
    currency_usd,
    underwriter_party_a,
    fixed_asset_b,
):
    """Cross-tenant fixed asset is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    data = _assetwarrantyinsurance_valid_insurance_policy_data(
        currency_usd,
        underwriter_party_a,
        fixed_asset=str(fixed_asset_b.pk),
    )
    form_wide = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    form_wide.fields["fixed_asset"].queryset = FixedAsset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["fixed_asset"]


def test_assetwarrantyinsurance_insurance_policy_form_reject_foreign_operational_asset(
    tenant_a,
    currency_usd,
    underwriter_party_a,
    operational_asset_b,
):
    """Cross-tenant operational asset is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    data = _assetwarrantyinsurance_valid_insurance_policy_data(
        currency_usd,
        underwriter_party_a,
        operational_asset=str(operational_asset_b.pk),
    )
    form_wide = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    form_wide.fields["operational_asset"].queryset = OperationalAsset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["operational_asset"]


def test_assetwarrantyinsurance_insurance_policy_form_reject_foreign_asset_category(
    tenant_a,
    currency_usd,
    underwriter_party_a,
    category_root_b,
):
    """Cross-tenant asset category is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    data = _assetwarrantyinsurance_valid_insurance_policy_data(
        currency_usd,
        underwriter_party_a,
        asset_category=str(category_root_b.pk),
    )
    form_wide = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    form_wide.fields["asset_category"].queryset = AssetCategory.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["asset_category"]


def test_assetwarrantyinsurance_insurance_policy_form_reject_foreign_policy_document(
    tenant_a,
    tenant_b,
    currency_usd,
    underwriter_party_a,
):
    """Cross-tenant policy document is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    doc_b = Document.objects.create(tenant=tenant_b, name="Doc B", file="b.pdf")
    data = _assetwarrantyinsurance_valid_insurance_policy_data(
        currency_usd,
        underwriter_party_a,
        policy_document=str(doc_b.pk),
    )
    form_wide = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    form_wide.fields["policy_document"].queryset = Document.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["policy_document"]


def test_assetwarrantyinsurance_insurance_policy_form_reject_foreign_risk_manager(
    tenant_a,
    currency_usd,
    underwriter_party_a,
    admin_b,
):
    """Cross-tenant risk manager user is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    data = _assetwarrantyinsurance_valid_insurance_policy_data(
        currency_usd,
        underwriter_party_a,
        risk_manager=str(admin_b.pk),
    )
    form_wide = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    form_wide.fields["risk_manager"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["risk_manager"]


def test_assetwarrantyinsurance_insurance_policy_form_currency_global_active(tenant_a, currency_usd):
    """Currency queryset is global and active-only."""
    inactive_curr = Currency.objects.create(code="INACT3", name="Inactive 3", symbol="I", is_active=False)
    form = AssetInsurancePolicyForm(tenant=tenant_a)
    assert currency_usd in form.fields["currency"].queryset
    assert inactive_curr not in form.fields["currency"].queryset


def test_assetwarrantyinsurance_insurance_policy_form_date_validation_expiration_before_effective(
    tenant_a,
    currency_usd,
    underwriter_party_a,
):
    """expiration_date < effective_date raises a ValidationError on expiration_date."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    today = timezone.now().date()
    data = _assetwarrantyinsurance_valid_insurance_policy_data(
        currency_usd,
        underwriter_party_a,
        effective_date=today.strftime("%Y-%m-%d"),
        expiration_date=(today - timezone.timedelta(days=1)).strftime("%Y-%m-%d"),
    )
    form = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "expiration_date" in form.errors
    assert "Policy expiration date cannot precede effective inception date." in form.errors["expiration_date"]


def test_assetwarrantyinsurance_insurance_policy_form_date_validation_same_day_valid(
    tenant_a,
    currency_usd,
    underwriter_party_a,
):
    """expiration_date == effective_date is valid (single-day binder policy)."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    today = timezone.now().date()
    data = _assetwarrantyinsurance_valid_insurance_policy_data(
        currency_usd,
        underwriter_party_a,
        effective_date=today.strftime("%Y-%m-%d"),
        expiration_date=today.strftime("%Y-%m-%d"),
    )
    form = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_insurance_policy_form_save_flow(
    tenant_a,
    currency_usd,
    underwriter_party_a,
    admin_user,
):
    """Save flow sets tenant, risk_manager, and generates sequential policy tracking number."""
    _assetwarrantyinsurance_ensure_vendor_role(underwriter_party_a)
    data = _assetwarrantyinsurance_valid_insurance_policy_data(currency_usd, underwriter_party_a)
    form = AssetInsurancePolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    policy = form.save(commit=False)
    assert policy.tenant == tenant_a
    policy.risk_manager = admin_user
    policy.save()

    assert policy.pk is not None
    assert policy.number.startswith("AINS-")
    assert policy.risk_manager == admin_user
    assert policy.policy_number == "POL-2026-IND-MACH-01"


# ==============================================================================
# 4. AssetInsuranceClaimForm Tests
# ==============================================================================

def test_assetwarrantyinsurance_insurance_claim_form_valid_minimal(
    tenant_a,
    currency_usd,
    insurance_policy_a,
):
    """Form validates successfully with minimal required fields."""
    today = timezone.now().date()
    data = {
        "title": "Minor Electrical Coil Burnout Claim",
        "policy": str(insurance_policy_a.pk),
        "incident_date": today.strftime("%Y-%m-%d"),
        "peril_type": "electrical_arcing_surge",
        "incident_description": "Short circuit surge burned exciter field coils.",
        "incident_location": "Building A - Substation",
        "currency": str(currency_usd.pk),
        "claimed_loss_amount": "8500.00",
        "deductible_applied": "0.00",
        "salvage_recovery_amount": "0.00",
        "settlement_method": "direct_indemnity_check",
    }
    form = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_insurance_claim_form_valid_full(
    tenant_a,
    currency_usd,
    insurance_policy_a,
    fixed_asset_a,
    operational_asset_a,
    incident_a,
    adjuster_party_a,
):
    """Form validates successfully with full field set."""
    _assetwarrantyinsurance_ensure_vendor_role(adjuster_party_a)
    doc_a = Document.objects.create(tenant=tenant_a, name="Adjuster Proof of Loss", file="claims/proof.pdf")
    data = _assetwarrantyinsurance_valid_insurance_claim_data(
        currency_usd,
        insurance_policy_a,
        fixed_asset=str(fixed_asset_a.pk),
        operational_asset=str(operational_asset_a.pk),
        incident_report=str(incident_a.pk),
        adjuster_party=str(adjuster_party_a.pk),
        proof_of_loss_document=str(doc_a.pk),
    )
    form = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_insurance_claim_form_required_fields(tenant_a):
    """Form fails validation when required fields are missing."""
    form = AssetInsuranceClaimForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "policy" in form.errors
    assert "incident_date" in form.errors
    assert "peril_type" in form.errors
    assert "incident_description" in form.errors
    assert "claimed_loss_amount" in form.errors


def test_assetwarrantyinsurance_insurance_claim_form_exclusions_and_mass_assignment(
    tenant_a,
    currency_usd,
    insurance_policy_a,
    admin_user,
):
    """Verify system, lifecycle, and view-owned workflow fields are excluded from Meta.fields."""
    form = AssetInsuranceClaimForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "claim_status",
        "settlement_payout_amount",
        "claims_officer",
        "settlement_date",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} must be excluded from AssetInsuranceClaimForm"

    # Attempt injecting status, payout, and number
    data = _assetwarrantyinsurance_valid_insurance_claim_data(currency_usd, insurance_policy_a)
    data.update({
        "claim_status": "closed",
        "settlement_payout_amount": "999999.00",
        "number": "AICL-MALICIOUS-9999",
    })
    form_post = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    assert form_post.is_valid(), form_post.errors
    claim = form_post.save(commit=False)
    claim.claims_officer = admin_user
    claim.save()

    assert claim.claim_status == "incident_reported"
    assert claim.settlement_payout_amount == Decimal("0.00")
    assert claim.number != "AICL-MALICIOUS-9999"
    assert claim.number.startswith("AICL-")


def test_assetwarrantyinsurance_insurance_claim_form_fk_dropdown_filtering_tenant_isolation(
    tenant_a,
    tenant_b,
    insurance_policy_a,
    insurance_policy_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    incident_a,
    incident_b,
    adjuster_party_a,
    adjuster_party_b,
):
    """Form dropdown querysets must only contain tenant_a records, never tenant_b."""
    _assetwarrantyinsurance_ensure_vendor_role(adjuster_party_a)
    _assetwarrantyinsurance_ensure_vendor_role(adjuster_party_b)
    doc_a = Document.objects.create(tenant=tenant_a, name="Doc A", file="a.pdf")
    doc_b = Document.objects.create(tenant=tenant_b, name="Doc B", file="b.pdf")

    form = AssetInsuranceClaimForm(tenant=tenant_a)

    assert insurance_policy_a in form.fields["policy"].queryset
    assert insurance_policy_b not in form.fields["policy"].queryset

    assert fixed_asset_a in form.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form.fields["fixed_asset"].queryset

    assert operational_asset_a in form.fields["operational_asset"].queryset
    assert operational_asset_b not in form.fields["operational_asset"].queryset

    assert incident_a in form.fields["incident_report"].queryset
    assert incident_b not in form.fields["incident_report"].queryset

    assert adjuster_party_a in form.fields["adjuster_party"].queryset
    assert adjuster_party_b not in form.fields["adjuster_party"].queryset

    assert doc_a in form.fields["proof_of_loss_document"].queryset
    assert doc_b not in form.fields["proof_of_loss_document"].queryset


def test_assetwarrantyinsurance_insurance_claim_form_reject_foreign_policy(
    tenant_a,
    currency_usd,
    insurance_policy_b,
):
    """Cross-tenant policy is rejected by reject_foreign()."""
    data = _assetwarrantyinsurance_valid_insurance_claim_data(
        currency_usd,
        insurance_policy_b,
    )
    # 1. Scoped queryset blocks it
    form = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "policy" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["policy"].queryset = AssetInsurancePolicy.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["policy"]


def test_assetwarrantyinsurance_insurance_claim_form_reject_foreign_fixed_asset(
    tenant_a,
    currency_usd,
    insurance_policy_a,
    fixed_asset_b,
):
    """Cross-tenant fixed asset is rejected by reject_foreign()."""
    data = _assetwarrantyinsurance_valid_insurance_claim_data(
        currency_usd,
        insurance_policy_a,
        fixed_asset=str(fixed_asset_b.pk),
    )
    form_wide = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["fixed_asset"].queryset = FixedAsset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["fixed_asset"]


def test_assetwarrantyinsurance_insurance_claim_form_reject_foreign_operational_asset(
    tenant_a,
    currency_usd,
    insurance_policy_a,
    operational_asset_b,
):
    """Cross-tenant operational asset is rejected by reject_foreign()."""
    data = _assetwarrantyinsurance_valid_insurance_claim_data(
        currency_usd,
        insurance_policy_a,
        operational_asset=str(operational_asset_b.pk),
    )
    form_wide = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["operational_asset"].queryset = OperationalAsset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["operational_asset"]


def test_assetwarrantyinsurance_insurance_claim_form_reject_foreign_incident_report(
    tenant_a,
    currency_usd,
    insurance_policy_a,
    incident_b,
):
    """Cross-tenant incident report is rejected by reject_foreign()."""
    data = _assetwarrantyinsurance_valid_insurance_claim_data(
        currency_usd,
        insurance_policy_a,
        incident_report=str(incident_b.pk),
    )
    form_wide = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["incident_report"].queryset = AssetIncidentReport.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["incident_report"]


def test_assetwarrantyinsurance_insurance_claim_form_reject_foreign_adjuster(
    tenant_a,
    currency_usd,
    insurance_policy_a,
    adjuster_party_b,
):
    """Cross-tenant adjuster party is rejected by reject_foreign()."""
    _assetwarrantyinsurance_ensure_vendor_role(adjuster_party_b)
    data = _assetwarrantyinsurance_valid_insurance_claim_data(
        currency_usd,
        insurance_policy_a,
        adjuster_party=str(adjuster_party_b.pk),
    )
    form_wide = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["adjuster_party"].queryset = Party.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["adjuster_party"]


def test_assetwarrantyinsurance_insurance_claim_form_reject_foreign_proof_of_loss_document(
    tenant_a,
    tenant_b,
    currency_usd,
    insurance_policy_a,
):
    """Cross-tenant proof of loss document is rejected by reject_foreign()."""
    doc_b = Document.objects.create(tenant=tenant_b, name="Doc B", file="b.pdf")
    data = _assetwarrantyinsurance_valid_insurance_claim_data(
        currency_usd,
        insurance_policy_a,
        proof_of_loss_document=str(doc_b.pk),
    )
    form_wide = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    form_wide.fields["proof_of_loss_document"].queryset = Document.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["proof_of_loss_document"]


def test_assetwarrantyinsurance_insurance_claim_form_currency_global_active(tenant_a, currency_usd):
    """Currency queryset is global and active-only."""
    inactive_curr = Currency.objects.create(code="INACT4", name="Inactive 4", symbol="I", is_active=False)
    form = AssetInsuranceClaimForm(tenant=tenant_a)
    assert currency_usd in form.fields["currency"].queryset
    assert inactive_curr not in form.fields["currency"].queryset


def test_assetwarrantyinsurance_insurance_claim_form_deductible_exceeds_claimed_loss(
    tenant_a,
    currency_usd,
    insurance_policy_a,
):
    """Policy deductible cannot exceed gross claimed loss amount."""
    data = _assetwarrantyinsurance_valid_insurance_claim_data(
        currency_usd,
        insurance_policy_a,
        claimed_loss_amount="2000.00",
        deductible_applied="5000.00",
    )
    form = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "deductible_applied" in form.errors
    assert "Policy deductible cannot exceed gross claimed loss amount." in form.errors["deductible_applied"]


def test_assetwarrantyinsurance_insurance_claim_form_deductible_equal_to_claimed_loss_valid(
    tenant_a,
    currency_usd,
    insurance_policy_a,
):
    """Policy deductible equal to claimed loss is valid."""
    data = _assetwarrantyinsurance_valid_insurance_claim_data(
        currency_usd,
        insurance_policy_a,
        claimed_loss_amount="5000.00",
        deductible_applied="5000.00",
    )
    form = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_assetwarrantyinsurance_insurance_claim_form_save_flow(
    tenant_a,
    currency_usd,
    insurance_policy_a,
    admin_user,
):
    """Save flow sets tenant, claims_officer, and generates sequential claim number."""
    data = _assetwarrantyinsurance_valid_insurance_claim_data(currency_usd, insurance_policy_a)
    form = AssetInsuranceClaimForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    claim = form.save(commit=False)
    assert claim.tenant == tenant_a
    claim.claims_officer = admin_user
    claim.save()

    assert claim.pk is not None
    assert claim.number.startswith("AICL-")
    assert claim.claims_officer == admin_user
    assert claim.policy == insurance_policy_a
    assert claim.title == "Main Transformer Stator Flashover Claim"
