"""Asset Procurement & Acquisition (11.1) — FORMS Validation Invariants Test Suite.

Covers the 4 ModelForms:
- AssetRequisitionForm (AssetRequisition)
- AssetAcquisitionReceiptForm (AssetAcquisitionReceipt)
- AssetCapitalizationForm (AssetCapitalization)
- AssetTagForm (AssetTag)

Invariants pinned:
1. Form initialization with and without tenant (tenant-scoping vs unbound).
2. Successful validation with valid data (minimal and full payloads).
3. Required fields enforcement.
4. Mass assignment protection: verify system/workflow fields (tenant, number, status,
   is_verified, scanner_device_id, rejection_reason, total_cost_basis, audit stamps)
   are not exposed in form fields or cannot be overwritten.
5. Cross-tenant foreign key rejection: verifies both field queryset scoping and
   defense-in-depth reject_foreign handler.
6. Clean validation methods:
   - AssetRequisitionForm: estimated_cost >= 0
   - AssetAcquisitionReceiptForm: quantity_received >= 1
   - AssetCapitalizationForm: costs >= 0, useful_life_months >= 1, salvage_value <= total_cost_basis
   - AssetTagForm: clean_tag_code trims whitespace, rejects blank, enforces per-tenant uniqueness.
7. Queryset tenant isolation: ensure foreign key field dropdowns only list tenant-owned records.
"""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.accounting.models import GLAccount
from apps.assets.forms import (
    AssetAcquisitionReceiptForm,
    AssetCapitalizationForm,
    AssetRequisitionForm,
    AssetTagForm,
)
from apps.assets.models import (
    AssetAcquisitionReceipt,
    AssetCapitalization,
    AssetRequisition,
    AssetTag,
)
from apps.core.models import OrgUnit, Party
from apps.scm.models import Asset, Location, PurchaseOrder


# ==============================================================================
# Helper Functions (strictly prefixed with _assetprocurement_)
# ==============================================================================


def _assetprocurement_valid_requisition_data(currency, **overrides):
    """Build a valid payload for AssetRequisitionForm."""
    data = {
        "title": "5-Axis CNC Machining Center",
        "description": "High-precision vertical machining center with tool changer.",
        "business_justification": "Required for aerospace component prototyping backlog.",
        "asset_category": "machinery",
        "priority": "high",
        "estimated_cost": Decimal("135000.00"),
        "currency": currency.pk,
        "budget_code": "CAPEX-2026-ENG-01",
        "proposed_manufacturer": "Haas Automation",
        "proposed_model": "VF-4SS",
        "required_delivery_date": "2026-12-15",
    }
    data.update(overrides)
    return data


def _assetprocurement_valid_receipt_data(**overrides):
    """Build a valid payload for AssetAcquisitionReceiptForm."""
    data = {
        "title": "Dock Delivery of Haas VF-4SS Machining Center",
        "manufacturer": "Haas Automation",
        "model_number": "VF-4SS",
        "serial_number": "SN-VF4SS-2026-9021",
        "quantity_received": 1,
        "received_date": timezone.now().date(),
        "carrier_name": "Freight Logistics Inc.",
        "tracking_number": "TRK-9876543210",
        "bill_of_lading": "BOL-2026-HAAS-01",
        "condition_on_arrival": "excellent",
        "inspection_notes": "Crate intact, no visible shipping damage, shockwatch green.",
    }
    data.update(overrides)
    return data


def _assetprocurement_valid_capitalization_data(**overrides):
    """Build a valid payload for AssetCapitalizationForm."""
    data = {
        "title": "Capitalization — Haas VF-4SS 5-Axis Mill",
        "asset_name": "Haas VF-4SS CNC Milling Center #1",
        "purchase_cost": Decimal("125000.00"),
        "freight_cost": Decimal("3500.00"),
        "installation_cost": Decimal("2500.00"),
        "customs_duties_cost": Decimal("1500.00"),
        "other_initial_costs": Decimal("500.00"),
        "is_cip_conversion": False,
        "depreciation_method": "straight_line",
        "useful_life_months": 84,
        "salvage_value": Decimal("10000.00"),
        "in_service_date": timezone.now().date(),
    }
    data.update(overrides)
    return data


def _assetprocurement_valid_tag_data(**overrides):
    """Build a valid payload for AssetTagForm."""
    data = {
        "tag_code": "ATAG-TEST-00001",
        "tag_format": "qr_code",
        "physical_placement": "Chassis sideplate next to main power interlock",
        "notes": "Weatherproof synthetic polyester label with permanent acrylic adhesive.",
    }
    data.update(overrides)
    return data


def _assetprocurement_create_tenant_b_gl_account(tenant_b, code="1500-B", name="Machinery B"):
    """Helper to create a tenant-B GLAccount for cross-tenant tests."""
    return GLAccount.objects.create(
        tenant=tenant_b,
        code=code,
        name=name,
        account_type="asset",
        normal_balance="debit",
        is_active=True,
    )


# ==============================================================================
# 1. AssetRequisitionForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_requisition_form_init_without_tenant():
    """Form initializes cleanly when tenant is not passed."""
    form = AssetRequisitionForm()
    assert form.tenant is None
    assert "title" in form.fields
    assert "currency" in form.fields


@pytest.mark.django_db
def test_assetprocurement_requisition_form_init_with_tenant_scoping(
    tenant_a,
    tenant_b,
    vendor_party_a,
    vendor_party_b,
    org_unit_a,
    location_a,
    location_b,
    po_a,
    po_b,
):
    """Form querysets are properly filtered to the active tenant."""
    org_unit_b = OrgUnit.objects.create(tenant=tenant_b, name="Dept B", kind="department")

    form = AssetRequisitionForm(tenant=tenant_a)

    assert vendor_party_a in form.fields["proposed_vendor"].queryset
    assert vendor_party_b not in form.fields["proposed_vendor"].queryset

    assert org_unit_a in form.fields["target_org_unit"].queryset
    assert org_unit_b not in form.fields["target_org_unit"].queryset

    assert location_a in form.fields["target_location"].queryset
    assert location_b not in form.fields["target_location"].queryset

    assert po_a in form.fields["purchase_order"].queryset
    assert po_b not in form.fields["purchase_order"].queryset


@pytest.mark.django_db
def test_assetprocurement_requisition_form_valid_minimal(tenant_a, currency_usd):
    """Form validates with only required fields."""
    data = {
        "title": "Hydraulic Workshop Press",
        "business_justification": "Required for bending sheet metal fixtures in cell 3.",
        "asset_category": "machinery",
        "priority": "medium",
        "estimated_cost": Decimal("25000.00"),
    }
    form = AssetRequisitionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetprocurement_requisition_form_valid_full(
    tenant_a, currency_usd, vendor_party_a, org_unit_a, location_a, po_a
):
    """Form validates with all valid fields supplied."""
    data = _assetprocurement_valid_requisition_data(
        currency_usd,
        proposed_vendor=vendor_party_a.pk,
        target_org_unit=org_unit_a.pk,
        target_location=location_a.pk,
        purchase_order=po_a.pk,
    )
    form = AssetRequisitionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    req = form.save()
    assert req.pk is not None
    assert req.tenant == tenant_a
    assert req.title == "5-Axis CNC Machining Center"
    assert req.proposed_vendor == vendor_party_a
    assert req.target_org_unit == org_unit_a
    assert req.target_location == location_a
    assert req.purchase_order == po_a


@pytest.mark.django_db
def test_assetprocurement_requisition_form_required_fields(tenant_a):
    """Form fails validation when required fields are missing."""
    form = AssetRequisitionForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "business_justification" in form.errors


@pytest.mark.django_db
def test_assetprocurement_requisition_form_mass_assignment_protection(tenant_a, currency_usd, admin_user):
    """Verify system, lifecycle, and workflow fields are not editable via the form."""
    form = AssetRequisitionForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "status",
        "rejection_reason",
        "created_at",
        "updated_at",
        "submitted_by",
        "submitted_at",
        "approved_by",
        "approved_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from AssetRequisitionForm"

    # Attempt injecting excluded values into POST data
    data = _assetprocurement_valid_requisition_data(currency_usd)
    data.update({
        "status": "approved",
        "number": "AREQ-HACK-0001",
        "rejection_reason": "Injected malicious text",
    })
    form = AssetRequisitionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    req = form.save()

    assert req.status == "draft"
    assert req.rejection_reason == ""
    assert req.number != "AREQ-HACK-0001"
    assert req.number.startswith("AREQ-")


@pytest.mark.django_db
def test_assetprocurement_requisition_form_negative_cost_rejected(tenant_a, currency_usd):
    """Form rejects negative estimated cost."""
    data = _assetprocurement_valid_requisition_data(currency_usd, estimated_cost=Decimal("-100.00"))
    form = AssetRequisitionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "estimated_cost" in form.errors
    assert "Estimated cost cannot be negative" in form.errors["estimated_cost"][0]


@pytest.mark.django_db
def test_assetprocurement_requisition_form_cross_tenant_vendor_rejected(
    tenant_a, currency_usd, vendor_party_b
):
    """Cross-tenant vendor is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_requisition_data(
        currency_usd, proposed_vendor=vendor_party_b.pk
    )
    # 1. Scoped queryset rejects at choice validation
    form = AssetRequisitionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "proposed_vendor" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetRequisitionForm(data=data, tenant=tenant_a)
    form_wide.fields["proposed_vendor"].queryset = Party.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["proposed_vendor"]


@pytest.mark.django_db
def test_assetprocurement_requisition_form_cross_tenant_org_unit_rejected(
    tenant_a, tenant_b, currency_usd
):
    """Cross-tenant target org unit is rejected by field choices and reject_foreign."""
    org_b = OrgUnit.objects.create(tenant=tenant_b, name="Foreign Org Unit", kind="department")
    data = _assetprocurement_valid_requisition_data(currency_usd, target_org_unit=org_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetRequisitionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_org_unit" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetRequisitionForm(data=data, tenant=tenant_a)
    form_wide.fields["target_org_unit"].queryset = OrgUnit.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["target_org_unit"]


@pytest.mark.django_db
def test_assetprocurement_requisition_form_cross_tenant_location_rejected(
    tenant_a, currency_usd, location_b
):
    """Cross-tenant target location is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_requisition_data(currency_usd, target_location=location_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetRequisitionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_location" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetRequisitionForm(data=data, tenant=tenant_a)
    form_wide.fields["target_location"].queryset = Location.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["target_location"]


@pytest.mark.django_db
def test_assetprocurement_requisition_form_cross_tenant_po_rejected(tenant_a, currency_usd, po_b):
    """Cross-tenant purchase order is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_requisition_data(currency_usd, purchase_order=po_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetRequisitionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "purchase_order" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetRequisitionForm(data=data, tenant=tenant_a)
    form_wide.fields["purchase_order"].queryset = PurchaseOrder.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["purchase_order"]


# ==============================================================================
# 2. AssetAcquisitionReceiptForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_receipt_form_init_without_tenant():
    """Receipt form initializes without tenant argument."""
    form = AssetAcquisitionReceiptForm()
    assert form.tenant is None
    assert "title" in form.fields
    assert "quantity_received" in form.fields


@pytest.mark.django_db
def test_assetprocurement_receipt_form_init_with_tenant_scoping(
    tenant_a, tenant_b, requisition_a, requisition_b, po_a, po_b, vendor_party_a, vendor_party_b, location_a, location_b
):
    """Receipt form querysets are scoped to the active tenant."""
    form = AssetAcquisitionReceiptForm(tenant=tenant_a)

    assert requisition_a in form.fields["requisition"].queryset
    assert requisition_b not in form.fields["requisition"].queryset

    assert po_a in form.fields["purchase_order"].queryset
    assert po_b not in form.fields["purchase_order"].queryset

    assert vendor_party_a in form.fields["vendor"].queryset
    assert vendor_party_b not in form.fields["vendor"].queryset

    assert location_a in form.fields["receiving_location"].queryset
    assert location_b not in form.fields["receiving_location"].queryset


@pytest.mark.django_db
def test_assetprocurement_receipt_form_valid_minimal(tenant_a):
    """Receipt form validates with minimal required data."""
    data = {
        "title": "Minimal Delivery Receipt",
        "quantity_received": 1,
        "received_date": timezone.now().date(),
        "condition_on_arrival": "good",
    }
    form = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetprocurement_receipt_form_valid_full(
    tenant_a, requisition_a, po_a, vendor_party_a, location_a
):
    """Receipt form validates and persists with all fields populated."""
    data = _assetprocurement_valid_receipt_data(
        requisition=requisition_a.pk,
        purchase_order=po_a.pk,
        vendor=vendor_party_a.pk,
        receiving_location=location_a.pk,
    )
    form = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    receipt = form.save()
    assert receipt.pk is not None
    assert receipt.tenant == tenant_a
    assert receipt.requisition == requisition_a
    assert receipt.purchase_order == po_a
    assert receipt.vendor == vendor_party_a
    assert receipt.receiving_location == location_a
    assert receipt.quantity_received == 1


@pytest.mark.django_db
def test_assetprocurement_receipt_form_required_fields(tenant_a):
    """Receipt form fails when required fields are missing."""
    form = AssetAcquisitionReceiptForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "quantity_received" in form.errors


@pytest.mark.django_db
def test_assetprocurement_receipt_form_mass_assignment_protection(tenant_a):
    """System fields like status and inspected_by cannot be set via the receipt form."""
    form = AssetAcquisitionReceiptForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "status",
        "created_at",
        "updated_at",
        "inspected_by",
        "inspected_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from AssetAcquisitionReceiptForm"

    data = _assetprocurement_valid_receipt_data(
        status="accepted",
        number="ARCV-ROGUE-01",
    )
    form = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    receipt = form.save()

    assert receipt.status == "pending_inspection"
    assert receipt.number != "ARCV-ROGUE-01"
    assert receipt.number.startswith("ARCV-")


@pytest.mark.django_db
def test_assetprocurement_receipt_form_zero_quantity_rejected(tenant_a):
    """Receipt quantity must be at least 1."""
    data = _assetprocurement_valid_receipt_data(quantity_received=0)
    form = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "quantity_received" in form.errors
    assert "Quantity received must be at least 1" in form.errors["quantity_received"][0]


@pytest.mark.django_db
def test_assetprocurement_receipt_form_negative_quantity_rejected(tenant_a):
    """Negative quantity is rejected."""
    data = _assetprocurement_valid_receipt_data(quantity_received=-5)
    form = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "quantity_received" in form.errors


@pytest.mark.django_db
def test_assetprocurement_receipt_form_cross_tenant_requisition_rejected(tenant_a, requisition_b):
    """Cross-tenant requisition is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_receipt_data(requisition=requisition_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "requisition" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    form_wide.fields["requisition"].queryset = AssetRequisition.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["requisition"]


@pytest.mark.django_db
def test_assetprocurement_receipt_form_cross_tenant_po_rejected(tenant_a, po_b):
    """Cross-tenant purchase order is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_receipt_data(purchase_order=po_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "purchase_order" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    form_wide.fields["purchase_order"].queryset = PurchaseOrder.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["purchase_order"]


@pytest.mark.django_db
def test_assetprocurement_receipt_form_cross_tenant_vendor_rejected(tenant_a, vendor_party_b):
    """Cross-tenant vendor is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_receipt_data(vendor=vendor_party_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "vendor" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    form_wide.fields["vendor"].queryset = Party.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["vendor"]


@pytest.mark.django_db
def test_assetprocurement_receipt_form_cross_tenant_location_rejected(tenant_a, location_b):
    """Cross-tenant location is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_receipt_data(receiving_location=location_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "receiving_location" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetAcquisitionReceiptForm(data=data, tenant=tenant_a)
    form_wide.fields["receiving_location"].queryset = Location.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["receiving_location"]


# ==============================================================================
# 3. AssetCapitalizationForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_init_without_tenant():
    """Capitalization form initializes cleanly without tenant."""
    form = AssetCapitalizationForm()
    assert form.tenant is None
    assert "title" in form.fields
    assert "asset_name" in form.fields
    assert "purchase_cost" in form.fields


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_init_with_tenant_scoping(
    tenant_a,
    tenant_b,
    receipt_a,
    receipt_b,
    requisition_a,
    requisition_b,
    cip_account_a,
    asset_account_a,
    operational_asset_a,
    operational_asset_b,
):
    """Capitalization form querysets are scoped to active tenant."""
    cip_b = _assetprocurement_create_tenant_b_gl_account(tenant_b, "1599-B", "CIP B")
    asset_b = _assetprocurement_create_tenant_b_gl_account(tenant_b, "1500-B", "Machinery B")

    form = AssetCapitalizationForm(tenant=tenant_a)

    assert receipt_a in form.fields["acquisition_receipt"].queryset
    assert receipt_b not in form.fields["acquisition_receipt"].queryset

    assert requisition_a in form.fields["requisition"].queryset
    assert requisition_b not in form.fields["requisition"].queryset

    assert cip_account_a in form.fields["cip_gl_account"].queryset
    assert cip_b not in form.fields["cip_gl_account"].queryset

    assert asset_account_a in form.fields["asset_gl_account"].queryset
    assert asset_b not in form.fields["asset_gl_account"].queryset

    assert operational_asset_a in form.fields["operational_asset"].queryset
    assert operational_asset_b not in form.fields["operational_asset"].queryset


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_valid_minimal(tenant_a):
    """Capitalization form validates with minimal required data."""
    data = {
        "title": "Minimal Capitalization Record",
        "asset_name": "Standard Hydraulic Bench Press",
        "purchase_cost": Decimal("20000.00"),
        "freight_cost": Decimal("0.00"),
        "installation_cost": Decimal("0.00"),
        "customs_duties_cost": Decimal("0.00"),
        "other_initial_costs": Decimal("0.00"),
        "depreciation_method": "straight_line",
        "useful_life_months": 60,
        "salvage_value": Decimal("1000.00"),
        "in_service_date": timezone.now().date(),
    }
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_valid_full(
    tenant_a, receipt_a, requisition_a, cip_account_a, asset_account_a, operational_asset_a
):
    """Capitalization form validates with all fields and computes total basis on save."""
    data = _assetprocurement_valid_capitalization_data(
        acquisition_receipt=receipt_a.pk,
        requisition=requisition_a.pk,
        cip_gl_account=cip_account_a.pk,
        asset_gl_account=asset_account_a.pk,
        operational_asset=operational_asset_a.pk,
    )
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    cap = form.save()
    assert cap.pk is not None
    assert cap.tenant == tenant_a
    assert cap.acquisition_receipt == receipt_a
    assert cap.requisition == requisition_a
    assert cap.cip_gl_account == cip_account_a
    assert cap.asset_gl_account == asset_account_a
    assert cap.operational_asset == operational_asset_a
    # 125000 + 3500 + 2500 + 1500 + 500 = 133000
    assert cap.total_cost_basis == Decimal("133000.00")


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_required_fields(tenant_a):
    """Capitalization form enforces required fields."""
    form = AssetCapitalizationForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "asset_name" in form.errors


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_mass_assignment_protection(tenant_a):
    """total_cost_basis, status, and capitalized_by are excluded from form fields."""
    form = AssetCapitalizationForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "status",
        "created_at",
        "updated_at",
        "total_cost_basis",
        "capitalized_by",
        "capitalized_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from AssetCapitalizationForm"

    # Attempt to inject total_cost_basis or status via POST data
    data = _assetprocurement_valid_capitalization_data(
        total_cost_basis=Decimal("999999.00"),
        status="capitalized",
        number="ACAP-INJECT-01",
    )
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    cap = form.save()

    assert cap.status == "draft"
    assert cap.number != "ACAP-INJECT-01"
    assert cap.number.startswith("ACAP-")
    # Total basis is strictly computed by the model save(), not the injected form value
    assert cap.total_cost_basis == Decimal("133000.00")


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_negative_costs_rejected(tenant_a):
    """Negative values for any cost field are caught and rejected."""
    cost_fields = [
        "purchase_cost",
        "freight_cost",
        "installation_cost",
        "customs_duties_cost",
        "other_initial_costs",
        "salvage_value",
    ]
    for field in cost_fields:
        data = _assetprocurement_valid_capitalization_data(**{field: Decimal("-10.00")})
        form = AssetCapitalizationForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Expected {field} to fail with negative value"
        assert field in form.errors
        assert "cannot be negative" in form.errors[field][0]


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_zero_useful_life_rejected(tenant_a):
    """Useful life must be at least 1 month."""
    data = _assetprocurement_valid_capitalization_data(useful_life_months=0)
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "useful_life_months" in form.errors
    assert "Useful life must be at least 1 month" in form.errors["useful_life_months"][0]


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_salvage_exceeds_basis_rejected(tenant_a):
    """Salvage value cannot exceed total capitalized cost basis."""
    # Basis: purchase(1000) + freight(0) + install(0) + customs(0) + other(0) = 1000
    # Salvage: 1500 > 1000 -> must fail
    data = _assetprocurement_valid_capitalization_data(
        purchase_cost=Decimal("1000.00"),
        freight_cost=Decimal("0.00"),
        installation_cost=Decimal("0.00"),
        customs_duties_cost=Decimal("0.00"),
        other_initial_costs=Decimal("0.00"),
        salvage_value=Decimal("1500.00"),
    )
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "salvage_value" in form.errors
    assert "Salvage value cannot exceed total capitalized cost basis" in form.errors["salvage_value"][0]


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_salvage_equal_basis_allowed(tenant_a):
    """Salvage value exactly equal to cost basis is allowed (100% scrap recovery)."""
    data = _assetprocurement_valid_capitalization_data(
        purchase_cost=Decimal("10000.00"),
        freight_cost=Decimal("0.00"),
        installation_cost=Decimal("0.00"),
        customs_duties_cost=Decimal("0.00"),
        other_initial_costs=Decimal("0.00"),
        salvage_value=Decimal("10000.00"),
    )
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_cross_tenant_receipt_rejected(tenant_a, receipt_b):
    """Foreign tenant acquisition receipt is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_capitalization_data(acquisition_receipt=receipt_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "acquisition_receipt" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetCapitalizationForm(data=data, tenant=tenant_a)
    form_wide.fields["acquisition_receipt"].queryset = AssetAcquisitionReceipt.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["acquisition_receipt"]


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_cross_tenant_requisition_rejected(tenant_a, requisition_b):
    """Foreign tenant requisition is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_capitalization_data(requisition=requisition_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "requisition" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetCapitalizationForm(data=data, tenant=tenant_a)
    form_wide.fields["requisition"].queryset = AssetRequisition.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["requisition"]


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_cross_tenant_cip_gl_rejected(tenant_a, tenant_b):
    """Foreign tenant CIP GLAccount is rejected by field choices and reject_foreign."""
    cip_b = _assetprocurement_create_tenant_b_gl_account(tenant_b, "1599-B", "Foreign CIP")
    data = _assetprocurement_valid_capitalization_data(cip_gl_account=cip_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "cip_gl_account" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetCapitalizationForm(data=data, tenant=tenant_a)
    form_wide.fields["cip_gl_account"].queryset = GLAccount.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["cip_gl_account"]


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_cross_tenant_asset_gl_rejected(tenant_a, tenant_b):
    """Foreign tenant Asset GLAccount is rejected by field choices and reject_foreign."""
    asset_b = _assetprocurement_create_tenant_b_gl_account(tenant_b, "1500-B", "Foreign Machinery")
    data = _assetprocurement_valid_capitalization_data(asset_gl_account=asset_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset_gl_account" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetCapitalizationForm(data=data, tenant=tenant_a)
    form_wide.fields["asset_gl_account"].queryset = GLAccount.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["asset_gl_account"]


@pytest.mark.django_db
def test_assetprocurement_capitalization_form_cross_tenant_operational_asset_rejected(
    tenant_a, operational_asset_b
):
    """Foreign tenant operational asset is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_capitalization_data(operational_asset=operational_asset_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetCapitalizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operational_asset" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetCapitalizationForm(data=data, tenant=tenant_a)
    form_wide.fields["operational_asset"].queryset = Asset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["operational_asset"]


# ==============================================================================
# 4. AssetTagForm Tests
# ==============================================================================


@pytest.mark.django_db
def test_assetprocurement_tag_form_init_without_tenant():
    """Tag form initializes cleanly without tenant."""
    form = AssetTagForm()
    assert form.tenant is None
    assert "tag_code" in form.fields
    assert "tag_format" in form.fields


@pytest.mark.django_db
def test_assetprocurement_tag_form_init_with_tenant_scoping(
    tenant_a, tenant_b, operational_asset_a, operational_asset_b, capitalization_a, capitalization_b
):
    """Tag form querysets are scoped to active tenant."""
    form = AssetTagForm(tenant=tenant_a)

    assert operational_asset_a in form.fields["operational_asset"].queryset
    assert operational_asset_b not in form.fields["operational_asset"].queryset

    assert capitalization_a in form.fields["capitalization"].queryset
    assert capitalization_b not in form.fields["capitalization"].queryset


@pytest.mark.django_db
def test_assetprocurement_tag_form_valid_minimal(tenant_a):
    """Tag form validates with minimal fields (tag_code, tag_format)."""
    data = {
        "tag_code": "ATAG-MIN-2026-0001",
        "tag_format": "qr_code",
    }
    form = AssetTagForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetprocurement_tag_form_valid_full(tenant_a, operational_asset_a, capitalization_a):
    """Tag form validates and persists with linked operational asset and capitalization."""
    data = _assetprocurement_valid_tag_data(
        tag_code="ATAG-FULL-2026-0001",
        operational_asset=operational_asset_a.pk,
        capitalization=capitalization_a.pk,
    )
    form = AssetTagForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    tag = form.save()
    assert tag.pk is not None
    assert tag.tenant == tenant_a
    assert tag.tag_code == "ATAG-FULL-2026-0001"
    assert tag.operational_asset == operational_asset_a
    assert tag.capitalization == capitalization_a


@pytest.mark.django_db
def test_assetprocurement_tag_form_required_fields(tenant_a):
    """Tag form requires tag_code."""
    form = AssetTagForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "tag_code" in form.errors


@pytest.mark.django_db
def test_assetprocurement_tag_form_mass_assignment_protection(tenant_a):
    """is_verified, scanner_device_id, and workflow fields are not editable via tag form."""
    form = AssetTagForm(tenant=tenant_a)
    excluded = [
        "tenant",
        "number",
        "status",
        "is_verified",
        "scanner_device_id",
        "created_at",
        "updated_at",
        "affixed_by",
        "affixed_at",
        "verified_by",
        "verified_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"{field} should be excluded from AssetTagForm"

    data = _assetprocurement_valid_tag_data(
        tag_code="ATAG-HACK-0001",
        is_verified=True,
        scanner_device_id="ROGUE-SCANNER-XYZ",
        status="verified",
    )
    form = AssetTagForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    tag = form.save()

    assert tag.is_verified is False
    assert tag.scanner_device_id == ""
    assert tag.status == "pending_print"


@pytest.mark.django_db
def test_assetprocurement_tag_form_blank_code_rejected(tenant_a):
    """Blank or whitespace-only tag code is rejected."""
    data = _assetprocurement_valid_tag_data(tag_code="   ")
    form = AssetTagForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "tag_code" in form.errors
    assert any(
        msg in form.errors["tag_code"][0]
        for msg in ["This field is required.", "cannot be blank"]
    )


@pytest.mark.django_db
def test_assetprocurement_tag_form_whitespace_code_trimmed(tenant_a):
    """Leading and trailing whitespace is stripped from tag code."""
    data = _assetprocurement_valid_tag_data(tag_code="  ATAG-TRIM-0001  ")
    form = AssetTagForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["tag_code"] == "ATAG-TRIM-0001"


@pytest.mark.django_db
def test_assetprocurement_tag_form_duplicate_code_same_tenant_rejected(tenant_a, asset_tag_a):
    """Tag code already assigned in the same workspace is rejected."""
    data = _assetprocurement_valid_tag_data(tag_code=asset_tag_a.tag_code)
    form = AssetTagForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "tag_code" in form.errors
    assert "is already assigned" in form.errors["tag_code"][0]


@pytest.mark.django_db
def test_assetprocurement_tag_form_same_code_different_tenant_allowed(tenant_a, asset_tag_b):
    """Tag code matching another tenant's tag is allowed (tenant-isolated uniqueness)."""
    data = _assetprocurement_valid_tag_data(tag_code=asset_tag_b.tag_code)
    form = AssetTagForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetprocurement_tag_form_edit_existing_instance_same_code_valid(tenant_a, asset_tag_a):
    """Editing an existing tag instance retains its own tag code without triggering self-collision."""
    data = _assetprocurement_valid_tag_data(
        tag_code=asset_tag_a.tag_code,
        physical_placement="Relocated to top chassis bracket",
    )
    form = AssetTagForm(data=data, instance=asset_tag_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    updated = form.save()
    assert updated.physical_placement == "Relocated to top chassis bracket"


@pytest.mark.django_db
def test_assetprocurement_tag_form_cross_tenant_operational_asset_rejected(tenant_a, operational_asset_b):
    """Foreign operational asset is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_tag_data(operational_asset=operational_asset_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetTagForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operational_asset" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetTagForm(data=data, tenant=tenant_a)
    form_wide.fields["operational_asset"].queryset = Asset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["operational_asset"]


@pytest.mark.django_db
def test_assetprocurement_tag_form_cross_tenant_capitalization_rejected(tenant_a, capitalization_b):
    """Foreign capitalization is rejected by field choices and reject_foreign."""
    data = _assetprocurement_valid_tag_data(capitalization=capitalization_b.pk)

    # 1. Scoped queryset rejects at choice validation
    form = AssetTagForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "capitalization" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetTagForm(data=data, tenant=tenant_a)
    form_wide.fields["capitalization"].queryset = AssetCapitalization.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["capitalization"]
