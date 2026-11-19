"""Unit and validation tests for Module 12.9 Final Quality Control / Outgoing Quality Control (FQC / OQC) forms.

Covers:
- FinalInspectionLotForm
- CertificateOfConformanceForm
- PackagingLabelVerificationForm
- QualityReleaseAuthorizationForm

Naming conventions:
- Every test function: test_finalquality_form_*
- Every module-level helper: _finalquality_*
"""
from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import Party
from apps.quality.forms import (
    CertificateOfConformanceForm,
    FinalInspectionLotForm,
    PackagingLabelVerificationForm,
    QualityReleaseAuthorizationForm,
)
from apps.quality.models import (
    CertificateOfConformance,
    ControlledDocument,
    FinalInspectionLot,
    NonConformanceReport,
    PackagingLabelVerification,
    ProcessDeviation,
    QualityReleaseAuthorization,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# =============================================================================
# Module Helpers (Prefix: _finalquality_*)
# =============================================================================

def _finalquality_pk(val):
    """Return pk if val is a model instance, or val itself if scalar / None."""
    if hasattr(val, "pk"):
        return val.pk
    return val


def _finalquality_date(days_offset=0):
    """Return an ISO formatted date string relative to today."""
    return (timezone.now().date() + timedelta(days=days_offset)).isoformat()


def _finalquality_create_sales_order(tenant, customer, order_date=None):
    """Create a minimal SalesOrder for testing dropdowns and foreign key links."""
    from apps.scm.models import SalesOrder
    return SalesOrder.objects.create(
        tenant=tenant,
        customer=customer,
        order_date=order_date or timezone.now().date(),
    )


def _finalquality_create_shipment(tenant, carrier=None):
    """Create a minimal Shipment for testing dropdowns and foreign key links."""
    from apps.scm.models import Shipment
    return Shipment.objects.create(
        tenant=tenant,
        carrier=carrier,
        direction="outbound",
        origin_text="Origin Facility",
        destination_text="Destination Facility",
    )


def _finalquality_create_work_order(tenant):
    """Create a minimal WorkOrder for testing dropdowns and foreign key links."""
    from apps.scm.models import Item, WorkOrder
    item = Item.objects.create(
        tenant=tenant,
        sku=f"SKU-{uuid.uuid4().hex[:6].upper()}",
        name="Test Component Item",
    )
    return WorkOrder.objects.create(
        tenant=tenant,
        item=item,
        quantity_planned=Decimal("25.000"),
    )


def _finalquality_lot_base_data(customer=None, inspector=None, decision_by=None, **extra):
    """Build valid baseline POST dictionary for FinalInspectionLotForm."""
    data = {
        "title": "Final Inspection - Actuator Assembly",
        "inspection_stage": "post_packaging_oqc",
        "sampling_standard": "ansi_asq_z1_4_normal",
        "aql_critical": "0.00",
        "aql_major": "1.00",
        "aql_minor": "4.00",
        "status": "in_progress",
        "usage_decision": "pending",
        "decision_rationale": "",
        "item_code": "ACT-990",
        "item_name": "Precision Flight Actuator",
        "lot_number": "LOT-2026-FQC-01",
        "batch_number": "BATCH-990-A",
        "serial_number_range": "SN-100 through SN-120",
        "lot_quantity": 100,
        "sample_size_inspected": 20,
        "critical_defects_count": 0,
        "major_defects_count": 0,
        "minor_defects_count": 0,
        "units_passed": 20,
        "units_rejected": 0,
        "visual_inspection_passed": True,
        "dimensional_inspection_passed": True,
        "functional_test_passed": True,
        "packaging_inspection_passed": True,
        "is_on_hold": False,
        "hold_reason": "",
        "customer": _finalquality_pk(customer) if customer else "",
        "sales_order_number": "SO-4401",
        "sales_order": "",
        "work_order_number": "WO-8801",
        "work_order": "",
        "inspection_plan": "",
        "non_conformance": "",
        "process_deviation": "",
        "inspector": _finalquality_pk(inspector) if inspector else "",
        "decision_by": _finalquality_pk(decision_by) if decision_by else "",
        "inspection_date": _finalquality_date(0),
        "decision_date": "",
        "inspection_notes": "Sample meets all engineering drawing requirements.",
    }
    data.update(extra)
    return data


def _finalquality_coc_base_data(customer, lot=None, **extra):
    """Build valid baseline POST dictionary for CertificateOfConformanceForm."""
    data = {
        "title": "Certificate of Conformance - Actuators",
        "certificate_type": "aerospace_as9100_as9102",
        "customer": _finalquality_pk(customer),
        "customer_po_number": "PO-99120",
        "sales_order_number": "SO-4401",
        "sales_order": "",
        "shipment_number": "SHP-7701",
        "shipment": "",
        "item_code": "ACT-990",
        "item_name": "Precision Flight Actuator",
        "revision": "Rev D",
        "lot_number": "LOT-2026-FQC-01",
        "batch_number": "BATCH-990-A",
        "serial_numbers_text": "SN-100 through SN-150",
        "certified_quantity": 50,
        "inspection_lot": _finalquality_pk(lot) if lot else "",
        "applicable_specifications": "AS9100D, MIL-STD-130N",
        "test_results_summary": "Zero hydraulic pressure leaks, tensile strength 850 MPa.",
        "conformance_statement": "We certify that the materials and articles supplied conform in all respects.",
        "signatory_title": "Quality Director",
        "notes": "CoC ready for authorized digital signature.",
    }
    data.update(extra)
    return data


def _finalquality_packaging_base_data(lot=None, verifier=None, **extra):
    """Build valid baseline POST dictionary for PackagingLabelVerificationForm."""
    data = {
        "title": "Packaging & Label Verification - Flight Actuators",
        "status": "verified",
        "disposition": "pass_released",
        "item_code": "ACT-990",
        "item_name": "Precision Flight Actuator",
        "lot_number": "LOT-2026-FQC-01",
        "carton_count_inspected": 10,
        "label_part_number": "LBL-ACT-990",
        "label_artwork_revision": "Rev 2",
        "artwork_master": "",
        "barcode_symbology": "datamatrix_gs1_2d",
        "scanned_barcode_data": "(01)0085009901(10)LOT-2026-FQC-01",
        "iso_iec_print_grade": "grade_a_4_0",
        "label_content_accurate": True,
        "regulatory_symbols_present": True,
        "serialization_verified": True,
        "carton_integrity_intact": True,
        "tamper_evident_seal_intact": True,
        "cushioning_dunnage_adequate": True,
        "pallet_stacking_compliant": True,
        "inspection_lot": _finalquality_pk(lot) if lot else "",
        "shipment": "",
        "verifier": _finalquality_pk(verifier) if verifier else "",
        "verified_date": _finalquality_date(0),
        "discrepancy_details": "",
        "notes": "Packaging inspection completed without discrepancies.",
    }
    data.update(extra)
    return data


def _finalquality_release_base_data(customer, lot=None, coc=None, packaging=None, officer=None, **extra):
    """Build valid baseline POST dictionary for QualityReleaseAuthorizationForm."""
    data = {
        "title": "Quality Release Authorization - Actuator Shipment",
        "status": "draft",
        "release_disposition": "pending_review",
        "customer": _finalquality_pk(customer),
        "destination_country": "United States",
        "destination_facility": "Aero Hub Bay 1",
        "shipment_number": "SHP-7701",
        "shipment": "",
        "sales_order_number": "SO-4401",
        "sales_order": "",
        "lot_number": "LOT-2026-FQC-01",
        "quantity_authorized": 100,
        "inspection_lot": _finalquality_pk(lot) if lot else "",
        "certificate_of_conformance": _finalquality_pk(coc) if coc else "",
        "packaging_verification": _finalquality_pk(packaging) if packaging else "",
        "is_on_hold": False,
        "hold_reason": "",
        "final_inspection_passed": True,
        "no_open_ncrs_or_capas": True,
        "packaging_label_approved": True,
        "coc_issued_and_signed": True,
        "export_compliance_verified": True,
        "certificate_of_origin_attached": False,
        "shipping_container_security_seal": "SEAL-99412",
        "carrier_name": "FedEx Freight",
        "tracking_reference": "TRK-99412-A",
        "releasing_officer": _finalquality_pk(officer) if officer else "",
        "release_date": _finalquality_date(0),
        "concession_rationale": "",
        "notes": "Quality release package under evaluation.",
    }
    data.update(extra)
    return data


# =============================================================================
# 1. FinalInspectionLotForm Tests
# =============================================================================

def test_finalquality_form_lot_init_without_tenant():
    """Verify FinalInspectionLotForm initializes cleanly when tenant is None."""
    form = FinalInspectionLotForm()
    assert form.tenant is None
    assert "title" in form.fields
    assert "usage_decision" in form.fields


def test_finalquality_form_lot_system_field_exclusions(tenant_a, customer_party_a):
    """Verify tenant, number, created_at, updated_at are strictly excluded from form fields."""
    form = FinalInspectionLotForm(tenant=tenant_a)
    for excluded in ["tenant", "number", "created_at", "updated_at"]:
        assert excluded not in form.fields

    # Attempting to inject system fields via POST payload must not bypass generator
    payload = _finalquality_lot_base_data(
        customer=customer_party_a,
        tenant=tenant_a.pk,
        number="QFQC-INJECT-9999",
        created_at=_finalquality_date(-10),
    )
    bound_form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=True)
    assert instance.number != "QFQC-INJECT-9999"
    assert instance.number.startswith("QFQC-")


def test_finalquality_form_lot_tenant_scoping_users_active_only(tenant_a, tenant_b, admin_user, admin_b):
    """Verify inspector and decision_by dropdowns only contain active users in the same tenant."""
    inactive_user_a = User.objects.create_user(
        username="inactive_qa_a",
        email="inactive_qa_a@example.com",
        tenant=tenant_a,
        is_active=False,
    )

    form = FinalInspectionLotForm(tenant=tenant_a)
    inspector_qs = form.fields["inspector"].queryset
    decision_qs = form.fields["decision_by"].queryset

    assert admin_user in inspector_qs
    assert admin_user in decision_qs
    assert inactive_user_a not in inspector_qs
    assert inactive_user_a not in decision_qs
    assert admin_b not in inspector_qs
    assert admin_b not in decision_qs


def test_finalquality_form_lot_tenant_scoping_customer(tenant_a, tenant_b, customer_party_a, customer_party_b):
    """Verify customer dropdown includes tenant_a parties and excludes tenant_b parties."""
    form = FinalInspectionLotForm(tenant=tenant_a)
    customer_qs = form.fields["customer"].queryset

    assert customer_party_a in customer_qs
    assert customer_party_b not in customer_qs


def test_finalquality_form_lot_tenant_scoping_quality_and_scm_foreign_keys(
    tenant_a, tenant_b, doc_a, quality_doc_b, ncr_a, ncr_b, process_deviation_a, process_deviation_b, customer_party_a, customer_party_b
):
    """Verify inspection_plan, ncr, process_deviation, sales_order, and work_order are tenant scoped."""
    so_a = _finalquality_create_sales_order(tenant_a, customer_party_a)
    so_b = _finalquality_create_sales_order(tenant_b, customer_party_b)
    wo_a = _finalquality_create_work_order(tenant_a)
    wo_b = _finalquality_create_work_order(tenant_b)

    form = FinalInspectionLotForm(tenant=tenant_a)

    # Controlled documents
    assert doc_a in form.fields["inspection_plan"].queryset
    assert quality_doc_b not in form.fields["inspection_plan"].queryset

    # NonConformanceReports
    assert ncr_a in form.fields["non_conformance"].queryset
    assert ncr_b not in form.fields["non_conformance"].queryset

    # ProcessDeviations
    assert process_deviation_a in form.fields["process_deviation"].queryset
    assert process_deviation_b not in form.fields["process_deviation"].queryset

    # SCM SalesOrder and WorkOrder
    assert so_a in form.fields["sales_order"].queryset
    assert so_b not in form.fields["sales_order"].queryset
    assert wo_a in form.fields["work_order"].queryset
    assert wo_b not in form.fields["work_order"].queryset


def test_finalquality_form_lot_chained_select_related_on_sales_order(tenant_a):
    """Verify chained select_related on sales_order dropdown to optimize query execution."""
    form = FinalInspectionLotForm(tenant=tenant_a)
    assert "customer" in form.fields["sales_order"].queryset.query.select_related


def test_finalquality_form_lot_valid_payload_save_commit_false_and_true(tenant_a, admin_user, customer_party_a):
    """Verify valid form submission succeeds with commit=False and commit=True."""
    payload = _finalquality_lot_base_data(
        customer=customer_party_a,
        inspector=admin_user,
        decision_by=admin_user,
        lot_quantity=150,
        sample_size_inspected=30,
        units_passed=30,
        units_rejected=0,
    )
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    # commit=False
    unsaved = form.save(commit=False)
    assert unsaved.pk is None
    assert unsaved.tenant == tenant_a
    assert unsaved.lot_quantity == 150
    assert unsaved.customer == customer_party_a

    # commit=True
    saved = form.save(commit=True)
    assert saved.pk is not None
    assert saved.number.startswith("QFQC-")
    assert FinalInspectionLot.objects.filter(pk=saved.pk).exists()


def test_finalquality_form_lot_required_fields(tenant_a):
    """Verify required field validation fails when title is omitted."""
    payload = _finalquality_lot_base_data(title="")
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors


def test_finalquality_form_lot_validation_sample_size_exceeds_lot_quantity(tenant_a, customer_party_a):
    """Verify clean validation catches sample_size_inspected > lot_quantity."""
    payload = _finalquality_lot_base_data(
        customer=customer_party_a,
        lot_quantity=50,
        sample_size_inspected=80,
        units_passed=50,
    )
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "sample_size_inspected" in form.errors
    assert "Sample size cannot exceed total lot quantity." in form.errors["sample_size_inspected"]


def test_finalquality_form_lot_validation_units_exceed_sample_size(tenant_a, customer_party_a):
    """Verify clean validation catches units_passed + units_rejected > sample_size_inspected."""
    payload = _finalquality_lot_base_data(
        customer=customer_party_a,
        lot_quantity=100,
        sample_size_inspected=20,
        units_passed=18,
        units_rejected=5,  # 18 + 5 = 23 > 20
    )
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "units_passed" in form.errors
    assert "Total units passed and rejected cannot exceed sample size inspected." in form.errors["units_passed"]


def test_finalquality_form_lot_validation_hold_reason_required(tenant_a, customer_party_a):
    """Verify hold_reason is required when is_on_hold is True."""
    payload = _finalquality_lot_base_data(
        customer=customer_party_a,
        is_on_hold=True,
        hold_reason="",
    )
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "hold_reason" in form.errors
    assert "A hold reason is required when a lot is placed on hold." in form.errors["hold_reason"]

    # Passing hold reason clears the error
    payload["hold_reason"] = "Quarantine pending rework"
    valid_form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors


@pytest.mark.parametrize("usage_decision", [
    "quarantined_hold",
    "rejected_mrb",
    "accepted_with_concession",
])
def test_finalquality_form_lot_validation_usage_decision_rationale_required(tenant_a, customer_party_a, usage_decision):
    """Verify decision_rationale is mandatory when lot is quarantined, rejected, or accepted with concession."""
    payload = _finalquality_lot_base_data(
        customer=customer_party_a,
        usage_decision=usage_decision,
        decision_rationale="",
    )
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "decision_rationale" in form.errors
    assert "Decision rationale is mandatory when accepting with concession, holding, or rejecting." in form.errors["decision_rationale"]

    # When decision rationale is provided, form validates cleanly
    payload["decision_rationale"] = f"Formal MRB rationale for {usage_decision} disposition."
    valid_form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors


def test_finalquality_form_lot_reject_foreign_cross_tenant_entities(
    tenant_a, tenant_b, admin_b, customer_party_b, quality_doc_b, ncr_b, process_deviation_b
):
    """Verify reject_foreign rejects foreign customer, inspector, decision_by, and quality documents."""
    so_b = _finalquality_create_sales_order(tenant_b, customer_party_b)
    wo_b = _finalquality_create_work_order(tenant_b)

    # 1. Foreign customer
    payload = _finalquality_lot_base_data(customer=customer_party_b)
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer" in form.errors

    # 2. Foreign inspector
    payload = _finalquality_lot_base_data(inspector=admin_b)
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspector" in form.errors

    # 3. Foreign decision_by
    payload = _finalquality_lot_base_data(decision_by=admin_b)
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "decision_by" in form.errors

    # 4. Foreign inspection_plan
    payload = _finalquality_lot_base_data(inspection_plan=quality_doc_b)
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_plan" in form.errors

    # 5. Foreign non_conformance
    payload = _finalquality_lot_base_data(non_conformance=ncr_b)
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "non_conformance" in form.errors

    # 6. Foreign process_deviation
    payload = _finalquality_lot_base_data(process_deviation=process_deviation_b)
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "process_deviation" in form.errors

    # 7. Foreign sales_order
    payload = _finalquality_lot_base_data(sales_order=so_b)
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "sales_order" in form.errors

    # 8. Foreign work_order
    payload = _finalquality_lot_base_data(work_order=wo_b)
    form = FinalInspectionLotForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "work_order" in form.errors


# =============================================================================
# 2. CertificateOfConformanceForm Tests
# =============================================================================

def test_finalquality_form_coc_init_without_tenant():
    """Verify CertificateOfConformanceForm initializes cleanly when tenant is None."""
    form = CertificateOfConformanceForm()
    assert form.tenant is None
    assert "title" in form.fields
    assert "certificate_type" in form.fields


def test_finalquality_form_coc_system_and_workflow_field_exclusions(tenant_a, customer_party_a, final_lot_a):
    """Verify system, hash, and workflow-managed fields are excluded from CertificateOfConformanceForm."""
    form = CertificateOfConformanceForm(tenant=tenant_a)
    excluded_fields = [
        "tenant", "number", "created_at", "updated_at",
        "digital_signature_hash", "qr_verification_code",
        "status", "authorized_signatory", "signed_date",
    ]
    for field in excluded_fields:
        assert field not in form.fields, f"{field} should be excluded from CertificateOfConformanceForm"

    # Attempting to inject excluded fields in POST must be disregarded
    payload = _finalquality_coc_base_data(
        customer=customer_party_a,
        lot=final_lot_a,
        number="QCOC-INJECT-999",
        digital_signature_hash="fake-hash-inject",
        status="approved_signed",
        signed_date=_finalquality_date(-5),
    )
    bound_form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=True)
    assert instance.number != "QCOC-INJECT-999"
    assert instance.number.startswith("QCOC-")
    assert instance.digital_signature_hash == ""
    assert instance.status == "draft"  # Default status, not approved_signed


def test_finalquality_form_coc_tenant_scoping_foreign_keys(
    tenant_a, tenant_b, customer_party_a, customer_party_b, final_lot_a, final_lot_b
):
    """Verify customer, sales_order, shipment, and inspection_lot are strictly scoped to the tenant."""
    so_a = _finalquality_create_sales_order(tenant_a, customer_party_a)
    so_b = _finalquality_create_sales_order(tenant_b, customer_party_b)
    sh_a = _finalquality_create_shipment(tenant_a)
    sh_b = _finalquality_create_shipment(tenant_b)

    form = CertificateOfConformanceForm(tenant=tenant_a)

    assert customer_party_a in form.fields["customer"].queryset
    assert customer_party_b not in form.fields["customer"].queryset

    assert so_a in form.fields["sales_order"].queryset
    assert so_b not in form.fields["sales_order"].queryset

    assert sh_a in form.fields["shipment"].queryset
    assert sh_b not in form.fields["shipment"].queryset

    assert final_lot_a in form.fields["inspection_lot"].queryset
    assert final_lot_b not in form.fields["inspection_lot"].queryset


def test_finalquality_form_coc_chained_select_related_on_sales_order(tenant_a):
    """Verify chained select_related on sales_order dropdown in CertificateOfConformanceForm."""
    form = CertificateOfConformanceForm(tenant=tenant_a)
    assert "customer" in form.fields["sales_order"].queryset.query.select_related


def test_finalquality_form_coc_valid_payload_save_commit_false_and_true(tenant_a, customer_party_a, final_lot_a):
    """Verify valid CertificateOfConformanceForm saves correctly with commit=False and commit=True."""
    payload = _finalquality_coc_base_data(
        customer=customer_party_a,
        lot=final_lot_a,
        certified_quantity=75,
    )
    form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    # commit=False
    unsaved = form.save(commit=False)
    assert unsaved.pk is None
    assert unsaved.tenant == tenant_a
    assert unsaved.certified_quantity == 75

    # commit=True
    saved = form.save(commit=True)
    assert saved.pk is not None
    assert saved.number.startswith("QCOC-")
    assert CertificateOfConformance.objects.filter(pk=saved.pk).exists()


def test_finalquality_form_coc_required_fields(tenant_a, customer_party_a):
    """Verify required fields fail validation when empty in CertificateOfConformanceForm."""
    payload = _finalquality_coc_base_data(customer=customer_party_a, title="")
    form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors


@pytest.mark.parametrize("invalid_qty", [0, -1, -50])
def test_finalquality_form_coc_certified_quantity_positive_validation(tenant_a, customer_party_a, invalid_qty):
    """Verify certified_quantity must be at least 1 unit."""
    payload = _finalquality_coc_base_data(
        customer=customer_party_a,
        certified_quantity=invalid_qty,
    )
    form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "certified_quantity" in form.errors
    assert "Certified quantity must be at least 1 unit." in form.errors["certified_quantity"]


def test_finalquality_form_coc_counterparty_integrity_sales_order(tenant_a, customer_party_a):
    """Verify linking a sales_order belonging to a different customer raises a validation error."""
    other_customer_a = Party.objects.create(tenant=tenant_a, name="Other Client In Tenant A")
    so_other = _finalquality_create_sales_order(tenant_a, other_customer_a)

    payload = _finalquality_coc_base_data(
        customer=customer_party_a,
        sales_order=so_other,
    )
    form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "sales_order" in form.errors
    assert "Linked sales order does not belong to the selected customer." in form.errors["sales_order"]

    # When sales order matches customer, form is valid
    so_matching = _finalquality_create_sales_order(tenant_a, customer_party_a)
    payload["sales_order"] = so_matching.pk
    valid_form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors


def test_finalquality_form_coc_counterparty_integrity_inspection_lot(tenant_a, customer_party_a):
    """Verify linking an inspection_lot belonging to a different customer raises a validation error."""
    other_customer_a = Party.objects.create(tenant=tenant_a, name="Other Client In Tenant A")
    lot_other = FinalInspectionLot.objects.create(
        tenant=tenant_a,
        title="Lot for Other Customer",
        customer=other_customer_a,
    )

    payload = _finalquality_coc_base_data(
        customer=customer_party_a,
        inspection_lot=lot_other,
    )
    form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_lot" in form.errors
    assert "Linked inspection lot does not belong to the selected customer." in form.errors["inspection_lot"]

    # When lot matches customer, form is valid
    lot_matching = FinalInspectionLot.objects.create(
        tenant=tenant_a,
        title="Lot for Matching Customer",
        customer=customer_party_a,
    )
    payload["inspection_lot"] = lot_matching.pk
    valid_form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors


def test_finalquality_form_coc_reject_foreign_cross_tenant(
    tenant_a, tenant_b, customer_party_a, customer_party_b, final_lot_b
):
    """Verify reject_foreign rejects foreign customer, sales_order, shipment, and inspection_lot."""
    so_b = _finalquality_create_sales_order(tenant_b, customer_party_b)
    sh_b = _finalquality_create_shipment(tenant_b)

    # 1. Foreign customer
    payload = _finalquality_coc_base_data(customer=customer_party_b)
    form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer" in form.errors

    # 2. Foreign sales order
    payload = _finalquality_coc_base_data(customer=customer_party_a, sales_order=so_b)
    form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "sales_order" in form.errors

    # 3. Foreign shipment
    payload = _finalquality_coc_base_data(customer=customer_party_a, shipment=sh_b)
    form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "shipment" in form.errors

    # 4. Foreign inspection lot
    payload = _finalquality_coc_base_data(customer=customer_party_a, inspection_lot=final_lot_b)
    form = CertificateOfConformanceForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_lot" in form.errors


# =============================================================================
# 3. PackagingLabelVerificationForm Tests
# =============================================================================

def test_finalquality_form_packaging_init_without_tenant():
    """Verify PackagingLabelVerificationForm initializes cleanly when tenant is None."""
    form = PackagingLabelVerificationForm()
    assert form.tenant is None
    assert "title" in form.fields
    assert "disposition" in form.fields


def test_finalquality_form_packaging_system_field_exclusions(tenant_a, final_lot_a):
    """Verify tenant, number, created_at, updated_at are excluded from PackagingLabelVerificationForm."""
    form = PackagingLabelVerificationForm(tenant=tenant_a)
    for field in ["tenant", "number", "created_at", "updated_at"]:
        assert field not in form.fields

    payload = _finalquality_packaging_base_data(
        lot=final_lot_a,
        number="QPKG-INJECT-1234",
    )
    bound_form = PackagingLabelVerificationForm(data=payload, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=True)
    assert instance.number != "QPKG-INJECT-1234"
    assert instance.number.startswith("QPKG-")


def test_finalquality_form_packaging_tenant_scoping_foreign_keys(
    tenant_a, tenant_b, admin_user, admin_b, doc_a, quality_doc_b, final_lot_a, final_lot_b
):
    """Verify artwork_master, inspection_lot, shipment, and verifier are scoped to tenant."""
    sh_a = _finalquality_create_shipment(tenant_a)
    sh_b = _finalquality_create_shipment(tenant_b)

    inactive_user_a = User.objects.create_user(
        username="inactive_pkg_user",
        email="inactive_pkg_user@example.com",
        tenant=tenant_a,
        is_active=False,
    )

    form = PackagingLabelVerificationForm(tenant=tenant_a)

    assert doc_a in form.fields["artwork_master"].queryset
    assert quality_doc_b not in form.fields["artwork_master"].queryset

    assert final_lot_a in form.fields["inspection_lot"].queryset
    assert final_lot_b not in form.fields["inspection_lot"].queryset

    assert sh_a in form.fields["shipment"].queryset
    assert sh_b not in form.fields["shipment"].queryset

    assert admin_user in form.fields["verifier"].queryset
    assert inactive_user_a not in form.fields["verifier"].queryset
    assert admin_b not in form.fields["verifier"].queryset


def test_finalquality_form_packaging_valid_payload_save_commit_false_and_true(tenant_a, admin_user, final_lot_a):
    """Verify valid PackagingLabelVerificationForm submission with commit=False and commit=True."""
    payload = _finalquality_packaging_base_data(
        lot=final_lot_a,
        verifier=admin_user,
        carton_count_inspected=15,
    )
    form = PackagingLabelVerificationForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    # commit=False
    unsaved = form.save(commit=False)
    assert unsaved.pk is None
    assert unsaved.tenant == tenant_a
    assert unsaved.carton_count_inspected == 15

    # commit=True
    saved = form.save(commit=True)
    assert saved.pk is not None
    assert saved.number.startswith("QPKG-")
    assert PackagingLabelVerification.objects.filter(pk=saved.pk).exists()


def test_finalquality_form_packaging_required_fields(tenant_a):
    """Verify required field validation fails when title is empty in PackagingLabelVerificationForm."""
    payload = _finalquality_packaging_base_data(title="")
    form = PackagingLabelVerificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors


@pytest.mark.parametrize("disposition", [
    "relabel_required",
    "repack_required",
    "reject_quarantine",
])
def test_finalquality_form_packaging_disposition_discrepancy_details_required(tenant_a, final_lot_a, disposition):
    """Verify discrepancy_details is mandatory when relabeling, repacking, or quarantining."""
    payload = _finalquality_packaging_base_data(
        lot=final_lot_a,
        disposition=disposition,
        discrepancy_details="",
    )
    form = PackagingLabelVerificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "discrepancy_details" in form.errors
    assert "Discrepancy details are required when relabeling, repacking, or quarantining." in form.errors["discrepancy_details"]

    # When details are provided, validation succeeds
    payload["discrepancy_details"] = "Barcode grade D below threshold; relabeling required."
    valid_form = PackagingLabelVerificationForm(data=payload, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors


def test_finalquality_form_packaging_reject_foreign_cross_tenant(
    tenant_a, tenant_b, admin_b, quality_doc_b, final_lot_b
):
    """Verify reject_foreign rejects foreign artwork_master, inspection_lot, shipment, and verifier."""
    sh_b = _finalquality_create_shipment(tenant_b)

    # 1. Foreign artwork master
    payload = _finalquality_packaging_base_data(artwork_master=quality_doc_b)
    form = PackagingLabelVerificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "artwork_master" in form.errors

    # 2. Foreign inspection lot
    payload = _finalquality_packaging_base_data(inspection_lot=final_lot_b)
    form = PackagingLabelVerificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_lot" in form.errors

    # 3. Foreign shipment
    payload = _finalquality_packaging_base_data(shipment=sh_b)
    form = PackagingLabelVerificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "shipment" in form.errors

    # 4. Foreign verifier
    payload = _finalquality_packaging_base_data(verifier=admin_b)
    form = PackagingLabelVerificationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "verifier" in form.errors


# =============================================================================
# 4. QualityReleaseAuthorizationForm Tests
# =============================================================================

def test_finalquality_form_release_init_without_tenant():
    """Verify QualityReleaseAuthorizationForm initializes cleanly when tenant is None."""
    form = QualityReleaseAuthorizationForm()
    assert form.tenant is None
    assert "title" in form.fields
    assert "release_disposition" in form.fields


def test_finalquality_form_release_system_field_exclusions(tenant_a, customer_party_a):
    """Verify tenant, number, created_at, updated_at are excluded from QualityReleaseAuthorizationForm."""
    form = QualityReleaseAuthorizationForm(tenant=tenant_a)
    for field in ["tenant", "number", "created_at", "updated_at"]:
        assert field not in form.fields

    payload = _finalquality_release_base_data(
        customer=customer_party_a,
        number="QREL-INJECT-9999",
    )
    bound_form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=True)
    assert instance.number != "QREL-INJECT-9999"
    assert instance.number.startswith("QREL-")


def test_finalquality_form_release_tenant_scoping_foreign_keys(
    tenant_a, tenant_b, admin_user, admin_b, customer_party_a, customer_party_b,
    final_lot_a, final_lot_b, coc_a, coc_b, packaging_verification_a, packaging_verification_b
):
    """Verify all dropdown querysets in QualityReleaseAuthorizationForm are tenant scoped."""
    so_a = _finalquality_create_sales_order(tenant_a, customer_party_a)
    so_b = _finalquality_create_sales_order(tenant_b, customer_party_b)
    sh_a = _finalquality_create_shipment(tenant_a)
    sh_b = _finalquality_create_shipment(tenant_b)

    inactive_user_a = User.objects.create_user(
        username="inactive_rel_officer",
        email="inactive_rel_officer@example.com",
        tenant=tenant_a,
        is_active=False,
    )

    form = QualityReleaseAuthorizationForm(tenant=tenant_a)

    assert customer_party_a in form.fields["customer"].queryset
    assert customer_party_b not in form.fields["customer"].queryset

    assert so_a in form.fields["sales_order"].queryset
    assert so_b not in form.fields["sales_order"].queryset

    assert sh_a in form.fields["shipment"].queryset
    assert sh_b not in form.fields["shipment"].queryset

    assert final_lot_a in form.fields["inspection_lot"].queryset
    assert final_lot_b not in form.fields["inspection_lot"].queryset

    assert coc_a in form.fields["certificate_of_conformance"].queryset
    assert coc_b not in form.fields["certificate_of_conformance"].queryset

    assert packaging_verification_a in form.fields["packaging_verification"].queryset
    assert packaging_verification_b not in form.fields["packaging_verification"].queryset

    assert admin_user in form.fields["releasing_officer"].queryset
    assert inactive_user_a not in form.fields["releasing_officer"].queryset
    assert admin_b not in form.fields["releasing_officer"].queryset


def test_finalquality_form_release_chained_select_related(tenant_a):
    """Verify chained select_related on certificate_of_conformance and sales_order dropdowns."""
    form = QualityReleaseAuthorizationForm(tenant=tenant_a)
    assert "customer" in form.fields["sales_order"].queryset.query.select_related
    assert "customer" in form.fields["certificate_of_conformance"].queryset.query.select_related


def test_finalquality_form_release_valid_payload_save_commit_false_and_true(
    tenant_a, customer_party_a, final_lot_a, coc_a, packaging_verification_a, admin_user
):
    """Verify valid QualityReleaseAuthorizationForm saves correctly with commit=False and commit=True."""
    payload = _finalquality_release_base_data(
        customer=customer_party_a,
        lot=final_lot_a,
        coc=coc_a,
        packaging=packaging_verification_a,
        officer=admin_user,
        quantity_authorized=100,
    )
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    # commit=False
    unsaved = form.save(commit=False)
    assert unsaved.pk is None
    assert unsaved.tenant == tenant_a
    assert unsaved.quantity_authorized == 100

    # commit=True
    saved = form.save(commit=True)
    assert saved.pk is not None
    assert saved.number.startswith("QREL-")
    assert QualityReleaseAuthorization.objects.filter(pk=saved.pk).exists()


def test_finalquality_form_release_required_fields(tenant_a, customer_party_a):
    """Verify required field validation fails when title is omitted in QualityReleaseAuthorizationForm."""
    payload = _finalquality_release_base_data(customer=customer_party_a, title="")
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors


def test_finalquality_form_release_hold_reason_mandatory_when_on_hold(tenant_a, customer_party_a):
    """Verify hold_reason is mandatory when is_on_hold is True."""
    payload = _finalquality_release_base_data(
        customer=customer_party_a,
        is_on_hold=True,
        hold_reason="",
    )
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "hold_reason" in form.errors
    assert "A hold reason is mandatory when shipment release is on hold." in form.errors["hold_reason"]


def test_finalquality_form_release_hold_authorization_conflict(tenant_a, customer_party_a):
    """Verify saving status='authorized' or release_disposition='released_full' while on hold fails."""
    # 1. status='authorized' while on hold
    payload = _finalquality_release_base_data(
        customer=customer_party_a,
        is_on_hold=True,
        hold_reason="Customs documentation review pending",
        status="authorized",
        release_disposition="pending_review",
    )
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Cannot authorize or fully release a shipment while an active quality hold is engaged." in form.errors["status"]

    # 2. release_disposition='released_full' while on hold
    payload["status"] = "draft"
    payload["release_disposition"] = "released_full"
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "Cannot authorize or fully release a shipment while an active quality hold is engaged." in form.errors["status"]

    # 3. Valid authorization when not on hold
    payload["is_on_hold"] = False
    payload["hold_reason"] = ""
    payload["status"] = "authorized"
    payload["release_disposition"] = "released_full"
    valid_form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors


def test_finalquality_form_release_conditional_release_concession_rationale(tenant_a, customer_party_a):
    """Verify concession_rationale is mandatory when release_disposition is conditional_release."""
    payload = _finalquality_release_base_data(
        customer=customer_party_a,
        release_disposition="conditional_release",
        concession_rationale="",
    )
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "concession_rationale" in form.errors
    assert "Concession rationale is mandatory for conditional release approvals." in form.errors["concession_rationale"]

    # Passing concession rationale clears error
    payload["concession_rationale"] = "Approved customer deviation CONC-2026-088"
    valid_form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors


def test_finalquality_form_release_counterparty_integrity_sales_order(tenant_a, customer_party_a):
    """Verify linked sales_order must belong to the selected customer."""
    other_customer_a = Party.objects.create(tenant=tenant_a, name="Other Client A")
    so_other = _finalquality_create_sales_order(tenant_a, other_customer_a)

    payload = _finalquality_release_base_data(
        customer=customer_party_a,
        sales_order=so_other,
    )
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "sales_order" in form.errors
    assert "Linked sales order does not belong to the selected customer." in form.errors["sales_order"]

    # Matching customer succeeds
    so_matching = _finalquality_create_sales_order(tenant_a, customer_party_a)
    payload["sales_order"] = so_matching.pk
    valid_form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors


def test_finalquality_form_release_counterparty_integrity_inspection_lot(tenant_a, customer_party_a):
    """Verify linked inspection_lot must belong to the selected customer."""
    other_customer_a = Party.objects.create(tenant=tenant_a, name="Other Client A")
    lot_other = FinalInspectionLot.objects.create(
        tenant=tenant_a,
        title="Other Customer Lot",
        customer=other_customer_a,
    )

    payload = _finalquality_release_base_data(
        customer=customer_party_a,
        inspection_lot=lot_other,
    )
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_lot" in form.errors
    assert "Linked inspection lot does not belong to the selected customer." in form.errors["inspection_lot"]

    # Matching customer succeeds
    lot_matching = FinalInspectionLot.objects.create(
        tenant=tenant_a,
        title="Matching Customer Lot",
        customer=customer_party_a,
    )
    payload["inspection_lot"] = lot_matching.pk
    valid_form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors


def test_finalquality_form_release_counterparty_integrity_certificate_of_conformance(tenant_a, customer_party_a):
    """Verify linked CertificateOfConformance must belong to the selected customer."""
    other_customer_a = Party.objects.create(tenant=tenant_a, name="Other Client A")
    coc_other = CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="Other Customer CoC",
        customer=other_customer_a,
    )

    payload = _finalquality_release_base_data(
        customer=customer_party_a,
        certificate_of_conformance=coc_other,
    )
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "certificate_of_conformance" in form.errors
    assert "Linked Certificate of Conformance does not belong to the selected customer." in form.errors["certificate_of_conformance"]

    # Matching customer succeeds
    coc_matching = CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="Matching Customer CoC",
        customer=customer_party_a,
    )
    payload["certificate_of_conformance"] = coc_matching.pk
    valid_form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert valid_form.is_valid(), valid_form.errors


def test_finalquality_form_release_reject_foreign_cross_tenant(
    tenant_a, tenant_b, admin_b, customer_party_a, customer_party_b,
    final_lot_b, coc_b, packaging_verification_b
):
    """Verify reject_foreign rejects foreign customer, shipment, sales_order, lot, coc, packaging, and officer."""
    so_b = _finalquality_create_sales_order(tenant_b, customer_party_b)
    sh_b = _finalquality_create_shipment(tenant_b)

    # 1. Foreign customer
    payload = _finalquality_release_base_data(customer=customer_party_b)
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer" in form.errors

    # 2. Foreign shipment
    payload = _finalquality_release_base_data(customer=customer_party_a, shipment=sh_b)
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "shipment" in form.errors

    # 3. Foreign sales order
    payload = _finalquality_release_base_data(customer=customer_party_a, sales_order=so_b)
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "sales_order" in form.errors

    # 4. Foreign inspection lot
    payload = _finalquality_release_base_data(customer=customer_party_a, inspection_lot=final_lot_b)
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_lot" in form.errors

    # 5. Foreign CoC
    payload = _finalquality_release_base_data(customer=customer_party_a, certificate_of_conformance=coc_b)
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "certificate_of_conformance" in form.errors

    # 6. Foreign packaging verification
    payload = _finalquality_release_base_data(customer=customer_party_a, packaging_verification=packaging_verification_b)
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "packaging_verification" in form.errors

    # 7. Foreign releasing officer
    payload = _finalquality_release_base_data(customer=customer_party_a, officer=admin_b)
    form = QualityReleaseAuthorizationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "releasing_officer" in form.errors
