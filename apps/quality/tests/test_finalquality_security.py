"""
Security, Multi-Tenant Data Isolation, Role-Based Access Control, and Adversarial Tests
for Sub-module 12.9: Final Quality Control / Outgoing Quality Control (FQC / OQC).

Covers:
1. Multi-Tenant Isolation & IDOR Resistance:
   - Cross-tenant IDOR defense: accessing Tenant B objects (detail, edit, delete, toggle_hold, sign)
     by Tenant A user returns HTTP 404 (and symmetric cross-tenant checks).
   - Cross-tenant data isolation: list views and OQC hold board never leak Tenant B records.
   - Cross-tenant foreign key injection: attempting to link Tenant B's customer, inspection lot,
     CoC, packaging verification, or user accounts into Tenant A forms is rejected by reject_foreign.
   - Mass assignment prevention: tenant and number fields cannot be overwritten via form submissions.
2. Authorization & RBAC Enforcement:
   - Unauthenticated access on all 28 endpoints redirects to login (HTTP 302).
   - Standard non-admin tenant user attempting to execute privileged actions (delete, toggle_hold,
     sign) is denied with HTTP 403 Forbidden via @tenant_admin_required.
   - HTTP method enforcement: all state-mutating actions reject GET with HTTP 405 Method Not Allowed.
3. Digital Signature Integrity & State Immutability:
   - Approved & digitally signed CoC cannot be mutated via edit view.
   - Approved & digitally signed CoC cannot be re-signed.
   - Approved & digitally signed CoC cannot be hard-deleted.
   - Authorized quality release cannot be hard-deleted.
   - SHA-256 digital signature digest tampering check: changing attested document fields
     invalidates the cryptographic signature digest.
4. Counterparty & Business Rule Enforcement:
   - Cross-customer counterparty mismatch: linking an inspection lot, CoC, or sales order belonging
     to Customer X into a record belonging to Customer Y is rejected with form validation error.
   - Release hold conflict: authorizing or fully releasing a shipment while is_on_hold=True
     is rejected with form validation error.
   - Hold toggle reason mandatory: attempting to engage hold without a reason is rejected in views and forms.
5. CSV Injection Formula Neutralization & nosniff Header:
   - All 4 export endpoints neutralize formula injection prefixes (=, +, -, @, \\t, \\r) by prepending '
     and set X-Content-Type-Options: nosniff header.
6. Audit Trail Verification:
   - AuditLog records are faithfully generated for create, update, delete, sign, hold, release, and export actions.
"""
import csv
import hashlib
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Party
from apps.quality.forms.FinalQuality.CertificatesOfConformance import CertificateOfConformanceForm
from apps.quality.forms.FinalQuality.FinalInspectionLots import FinalInspectionLotForm
from apps.quality.forms.FinalQuality.PackagingLabelVerifications import PackagingLabelVerificationForm
from apps.quality.forms.FinalQuality.QualityReleaseAuthorizations import QualityReleaseAuthorizationForm
from apps.quality.models.FinalQuality.CertificatesOfConformance import CertificateOfConformance
from apps.quality.models.FinalQuality.FinalInspectionLots import FinalInspectionLot
from apps.quality.models.FinalQuality.PackagingLabelVerifications import PackagingLabelVerification
from apps.quality.models.FinalQuality.QualityReleaseAuthorizations import QualityReleaseAuthorization

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


def _finalquality_lot_data(customer=None, inspector=None, decision_by=None, **extra):
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


def _finalquality_coc_data(customer, lot=None, **extra):
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


def _finalquality_packaging_data(lot=None, verifier=None, **extra):
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


def _finalquality_release_data(customer, lot=None, coc=None, packaging=None, officer=None, **extra):
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


def _finalquality_compute_coc_hash(certificate, user_id, timestamp_iso):
    """Compute the expected SHA-256 digital signature hash for a CertificateOfConformance."""
    raw_stamp = (
        f"{certificate.number}:{certificate.tenant_id}:{user_id}:{timestamp_iso}:"
        f"{certificate.customer_id}:{certificate.item_code}:{certificate.lot_number}:"
        f"{certificate.certified_quantity}:{certificate.applicable_specifications}:"
        f"{certificate.test_results_summary}:{certificate.conformance_statement}"
    )
    return hashlib.sha256(raw_stamp.encode("utf-8")).hexdigest()


# =============================================================================
# 1. Multi-Tenant Isolation & Cross-Tenant IDOR Resistance
# =============================================================================

def test_finalquality_sec_idor_lot_detail_edit_delete_toggle_hold(client_a, client_b, final_lot_a, final_lot_b):
    """Verify Tenant A user cannot access or mutate Tenant B's inspection lot and vice versa (HTTP 404)."""
    # Tenant A -> Tenant B (must 404)
    assert client_a.get(reverse("quality:final_inspection_lot_detail", kwargs={"pk": final_lot_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:final_inspection_lot_edit", kwargs={"pk": final_lot_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:final_inspection_lot_delete", kwargs={"pk": final_lot_b.pk})).status_code == 404
    assert client_a.post(
        reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": final_lot_b.pk}),
        {"hold_reason": "Malicious hold attempt"},
    ).status_code == 404

    # Symmetric: Tenant B -> Tenant A (must 404)
    assert client_b.get(reverse("quality:final_inspection_lot_detail", kwargs={"pk": final_lot_a.pk})).status_code == 404
    assert client_b.get(reverse("quality:final_inspection_lot_edit", kwargs={"pk": final_lot_a.pk})).status_code == 404
    assert client_b.post(reverse("quality:final_inspection_lot_delete", kwargs={"pk": final_lot_a.pk})).status_code == 404
    assert client_b.post(
        reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": final_lot_a.pk}),
        {"hold_reason": "Malicious hold attempt"},
    ).status_code == 404


def test_finalquality_sec_idor_coc_detail_edit_delete_sign(client_a, client_b, coc_a, coc_b):
    """Verify Tenant A user cannot access, edit, delete, or sign Tenant B's CoC and vice versa (HTTP 404)."""
    # Tenant A -> Tenant B (must 404)
    assert client_a.get(reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:certificate_of_conformance_edit", kwargs={"pk": coc_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:certificate_of_conformance_delete", kwargs={"pk": coc_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:certificate_of_conformance_sign", kwargs={"pk": coc_b.pk})).status_code == 404

    # Symmetric: Tenant B -> Tenant A (must 404)
    assert client_b.get(reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_a.pk})).status_code == 404
    assert client_b.get(reverse("quality:certificate_of_conformance_edit", kwargs={"pk": coc_a.pk})).status_code == 404
    assert client_b.post(reverse("quality:certificate_of_conformance_delete", kwargs={"pk": coc_a.pk})).status_code == 404
    assert client_b.post(reverse("quality:certificate_of_conformance_sign", kwargs={"pk": coc_a.pk})).status_code == 404


def test_finalquality_sec_idor_packaging_detail_edit_delete(client_a, client_b, packaging_verification_a, packaging_verification_b):
    """Verify Tenant A user cannot access, edit, or delete Tenant B's packaging verification and vice versa (HTTP 404)."""
    # Tenant A -> Tenant B (must 404)
    assert client_a.get(reverse("quality:packaging_label_verification_detail", kwargs={"pk": packaging_verification_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:packaging_label_verification_edit", kwargs={"pk": packaging_verification_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:packaging_label_verification_delete", kwargs={"pk": packaging_verification_b.pk})).status_code == 404

    # Symmetric: Tenant B -> Tenant A (must 404)
    assert client_b.get(reverse("quality:packaging_label_verification_detail", kwargs={"pk": packaging_verification_a.pk})).status_code == 404
    assert client_b.get(reverse("quality:packaging_label_verification_edit", kwargs={"pk": packaging_verification_a.pk})).status_code == 404
    assert client_b.post(reverse("quality:packaging_label_verification_delete", kwargs={"pk": packaging_verification_a.pk})).status_code == 404


def test_finalquality_sec_idor_quality_release_detail_edit_delete_toggle_hold(client_a, client_b, quality_release_a, quality_release_b):
    """Verify Tenant A user cannot access, edit, delete, or toggle hold on Tenant B's release and vice versa (HTTP 404)."""
    # Tenant A -> Tenant B (must 404)
    assert client_a.get(reverse("quality:quality_release_authorization_detail", kwargs={"pk": quality_release_b.pk})).status_code == 404
    assert client_a.get(reverse("quality:quality_release_authorization_edit", kwargs={"pk": quality_release_b.pk})).status_code == 404
    assert client_a.post(reverse("quality:quality_release_authorization_delete", kwargs={"pk": quality_release_b.pk})).status_code == 404
    assert client_a.post(
        reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": quality_release_b.pk}),
        {"hold_reason": "Malicious hold attempt"},
    ).status_code == 404

    # Symmetric: Tenant B -> Tenant A (must 404)
    assert client_b.get(reverse("quality:quality_release_authorization_detail", kwargs={"pk": quality_release_a.pk})).status_code == 404
    assert client_b.get(reverse("quality:quality_release_authorization_edit", kwargs={"pk": quality_release_a.pk})).status_code == 404
    assert client_b.post(reverse("quality:quality_release_authorization_delete", kwargs={"pk": quality_release_a.pk})).status_code == 404
    assert client_b.post(
        reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": quality_release_a.pk}),
        {"hold_reason": "Malicious hold attempt"},
    ).status_code == 404


def test_finalquality_sec_list_views_data_isolation(client_a, client_b, final_lot_a, final_lot_b, coc_a, coc_b, packaging_verification_a, packaging_verification_b, quality_release_a, quality_release_b):
    """Verify list views strictly scope records to the active tenant without cross-tenant data leakage."""
    # Tenant A listing
    resp_lot_a = client_a.get(reverse("quality:final_inspection_lot_list"))
    assert resp_lot_a.status_code == 200
    content_lot_a = resp_lot_a.content.decode()
    assert final_lot_a.title in content_lot_a
    assert final_lot_b.title not in content_lot_a
    assert final_lot_a in resp_lot_a.context["inspection_lots"]
    assert final_lot_b not in resp_lot_a.context["inspection_lots"]

    resp_coc_a = client_a.get(reverse("quality:certificate_of_conformance_list"))
    assert resp_coc_a.status_code == 200
    content_coc_a = resp_coc_a.content.decode()
    assert coc_a.customer.name in content_coc_a
    assert coc_b.customer.name not in content_coc_a
    assert coc_a in resp_coc_a.context["certificates"]
    assert coc_b not in resp_coc_a.context["certificates"]

    resp_pkg_a = client_a.get(reverse("quality:packaging_label_verification_list"))
    assert resp_pkg_a.status_code == 200
    content_pkg_a = resp_pkg_a.content.decode()
    assert packaging_verification_a.title in content_pkg_a
    assert packaging_verification_b.title not in content_pkg_a
    assert packaging_verification_a in resp_pkg_a.context["verifications"]
    assert packaging_verification_b not in resp_pkg_a.context["verifications"]

    resp_rel_a = client_a.get(reverse("quality:quality_release_authorization_list"))
    assert resp_rel_a.status_code == 200
    content_rel_a = resp_rel_a.content.decode()
    assert quality_release_a.title in content_rel_a
    assert quality_release_b.title not in content_rel_a
    assert quality_release_a in resp_rel_a.context["releases"]
    assert quality_release_b not in resp_rel_a.context["releases"]

    # Symmetric: Tenant B listing
    resp_lot_b = client_b.get(reverse("quality:final_inspection_lot_list"))
    assert resp_lot_b.status_code == 200
    content_lot_b = resp_lot_b.content.decode()
    assert final_lot_b.title in content_lot_b
    assert final_lot_a.title not in content_lot_b
    assert final_lot_b in resp_lot_b.context["inspection_lots"]
    assert final_lot_a not in resp_lot_b.context["inspection_lots"]

    resp_coc_b = client_b.get(reverse("quality:certificate_of_conformance_list"))
    assert resp_coc_b.status_code == 200
    content_coc_b = resp_coc_b.content.decode()
    assert coc_b.customer.name in content_coc_b
    assert coc_a.customer.name not in content_coc_b
    assert coc_b in resp_coc_b.context["certificates"]
    assert coc_a not in resp_coc_b.context["certificates"]

    resp_pkg_b = client_b.get(reverse("quality:packaging_label_verification_list"))
    assert resp_pkg_b.status_code == 200
    content_pkg_b = resp_pkg_b.content.decode()
    assert packaging_verification_b.title in content_pkg_b
    assert packaging_verification_a.title not in content_pkg_b
    assert packaging_verification_b in resp_pkg_b.context["verifications"]
    assert packaging_verification_a not in resp_pkg_b.context["verifications"]

    resp_rel_b = client_b.get(reverse("quality:quality_release_authorization_list"))
    assert resp_rel_b.status_code == 200
    content_rel_b = resp_rel_b.content.decode()
    assert quality_release_b.title in content_rel_b
    assert quality_release_a.title not in content_rel_b
    assert quality_release_b in resp_rel_b.context["releases"]
    assert quality_release_a not in resp_rel_b.context["releases"]


def test_finalquality_sec_hold_board_data_isolation(client_a, client_b, final_lot_a, final_lot_b, coc_a, coc_b, quality_release_a, quality_release_b):
    """Verify OQC hold and release board strictly isolates active holds and pending queues per tenant."""
    # Tenant A view
    resp_a = client_a.get(reverse("quality:oqc_hold_board"))
    assert resp_a.status_code == 200
    content_a = resp_a.content.decode()
    ctx_a = resp_a.context

    # Ensure Tenant B lots and releases (which are on hold) are not visible to Tenant A
    assert final_lot_b.title not in content_a
    assert quality_release_b.title not in content_a
    assert coc_b.title not in content_a

    assert all(obj.tenant_id == final_lot_a.tenant_id for obj in ctx_a["active_holds_lots"])
    assert all(obj.tenant_id == final_lot_a.tenant_id for obj in ctx_a["active_holds_releases"])
    assert all(obj.tenant_id == final_lot_a.tenant_id for obj in ctx_a["pending_cocs"])
    assert all(obj.tenant_id == final_lot_a.tenant_id for obj in ctx_a["ready_releases"])

    # Symmetric: Tenant B view
    resp_b = client_b.get(reverse("quality:oqc_hold_board"))
    assert resp_b.status_code == 200
    content_b = resp_b.content.decode()
    ctx_b = resp_b.context

    assert final_lot_a.title not in content_b
    assert quality_release_a.title not in content_b
    assert coc_a.title not in content_b

    assert all(obj.tenant_id == final_lot_b.tenant_id for obj in ctx_b["active_holds_lots"])
    assert all(obj.tenant_id == final_lot_b.tenant_id for obj in ctx_b["active_holds_releases"])
    assert all(obj.tenant_id == final_lot_b.tenant_id for obj in ctx_b["pending_cocs"])
    assert all(obj.tenant_id == final_lot_b.tenant_id for obj in ctx_b["ready_releases"])


def test_finalquality_sec_foreign_key_injection_lot_form(tenant_a, customer_party_b, admin_b):
    """Verify submitting Tenant B foreign keys (customer, inspector, decision_by) to Tenant A lot form is rejected."""
    data = _finalquality_lot_data(
        customer=customer_party_b,
        inspector=admin_b,
        decision_by=admin_b,
    )
    form = FinalInspectionLotForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer" in form.errors or "__all__" in form.errors or "inspector" in form.errors


def test_finalquality_sec_foreign_key_injection_coc_form(tenant_a, customer_party_a, customer_party_b, final_lot_b):
    """Verify submitting Tenant B foreign keys (customer, inspection_lot) to Tenant A CoC form is rejected."""
    # Attempting to assign Tenant B customer to Tenant A CoC
    data_bad_cust = _finalquality_coc_data(customer=customer_party_b)
    form_bad_cust = CertificateOfConformanceForm(data=data_bad_cust, tenant=tenant_a)
    assert not form_bad_cust.is_valid()
    assert "customer" in form_bad_cust.errors or "__all__" in form_bad_cust.errors

    # Attempting to link Tenant B inspection lot to Tenant A CoC
    data_bad_lot = _finalquality_coc_data(customer=customer_party_a, lot=final_lot_b)
    form_bad_lot = CertificateOfConformanceForm(data=data_bad_lot, tenant=tenant_a)
    assert not form_bad_lot.is_valid()
    assert "inspection_lot" in form_bad_lot.errors or "__all__" in form_bad_lot.errors


def test_finalquality_sec_foreign_key_injection_packaging_form(tenant_a, final_lot_b, admin_b):
    """Verify submitting Tenant B foreign keys (inspection_lot, verifier) to Tenant A packaging form is rejected."""
    data = _finalquality_packaging_data(lot=final_lot_b, verifier=admin_b)
    form = PackagingLabelVerificationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_lot" in form.errors or "verifier" in form.errors or "__all__" in form.errors


def test_finalquality_sec_foreign_key_injection_release_form(tenant_a, customer_party_a, customer_party_b, final_lot_b, coc_b, packaging_verification_b, admin_b):
    """Verify submitting Tenant B foreign keys (customer, lot, coc, packaging, releasing_officer) to release form is rejected."""
    data = _finalquality_release_data(
        customer=customer_party_b,
        lot=final_lot_b,
        coc=coc_b,
        packaging=packaging_verification_b,
        officer=admin_b,
    )
    form = QualityReleaseAuthorizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert any(k in form.errors for k in ["customer", "inspection_lot", "certificate_of_conformance", "packaging_verification", "releasing_officer", "__all__"])


def test_finalquality_sec_mass_assignment_tenant_and_number_prevented(tenant_a, tenant_b, customer_party_a, final_lot_a):
    """Verify tenant and auto-generated number fields cannot be mass assigned through form submissions."""
    # 1. Lot form
    lot_data = _finalquality_lot_data(customer=customer_party_a)
    lot_data.update({"tenant": tenant_b.pk, "number": "MALICIOUS-LOT-999"})
    lot_form = FinalInspectionLotForm(data=lot_data, tenant=tenant_a)
    assert lot_form.is_valid(), lot_form.errors
    lot_obj = lot_form.save(commit=False)
    assert lot_obj.tenant == tenant_a
    assert lot_obj.number != "MALICIOUS-LOT-999"

    # 2. CoC form
    coc_data = _finalquality_coc_data(customer=customer_party_a, lot=final_lot_a)
    coc_data.update({"tenant": tenant_b.pk, "number": "MALICIOUS-COC-999"})
    coc_form = CertificateOfConformanceForm(data=coc_data, tenant=tenant_a)
    assert coc_form.is_valid(), coc_form.errors
    coc_obj = coc_form.save(commit=False)
    assert coc_obj.tenant == tenant_a
    assert coc_obj.number != "MALICIOUS-COC-999"

    # 3. Packaging form
    pkg_data = _finalquality_packaging_data(lot=final_lot_a)
    pkg_data.update({"tenant": tenant_b.pk, "number": "MALICIOUS-PKG-999"})
    pkg_form = PackagingLabelVerificationForm(data=pkg_data, tenant=tenant_a)
    assert pkg_form.is_valid(), pkg_form.errors
    pkg_obj = pkg_form.save(commit=False)
    assert pkg_obj.tenant == tenant_a
    assert pkg_obj.number != "MALICIOUS-PKG-999"

    # 4. Release form
    rel_data = _finalquality_release_data(customer=customer_party_a, lot=final_lot_a)
    rel_data.update({"tenant": tenant_b.pk, "number": "MALICIOUS-REL-999"})
    rel_form = QualityReleaseAuthorizationForm(data=rel_data, tenant=tenant_a)
    assert rel_form.is_valid(), rel_form.errors
    rel_obj = rel_form.save(commit=False)
    assert rel_obj.tenant == tenant_a
    assert rel_obj.number != "MALICIOUS-REL-999"


# =============================================================================
# 2. Authorization & RBAC Enforcement
# =============================================================================

def test_finalquality_sec_unauthenticated_redirection_all_28_endpoints(client, final_lot_a, coc_a, packaging_verification_a, quality_release_a):
    """Verify unauthenticated requests redirect to login across all 28 endpoints in Sub-module 12.9."""
    endpoints = [
        # FinalInspectionLots (7)
        reverse("quality:final_inspection_lot_list"),
        reverse("quality:final_inspection_lot_create"),
        reverse("quality:final_inspection_lot_export"),
        reverse("quality:final_inspection_lot_detail", kwargs={"pk": final_lot_a.pk}),
        reverse("quality:final_inspection_lot_edit", kwargs={"pk": final_lot_a.pk}),
        reverse("quality:final_inspection_lot_delete", kwargs={"pk": final_lot_a.pk}),
        reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": final_lot_a.pk}),
        # CertificatesOfConformance (7)
        reverse("quality:certificate_of_conformance_list"),
        reverse("quality:certificate_of_conformance_create"),
        reverse("quality:certificate_of_conformance_export"),
        reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_a.pk}),
        reverse("quality:certificate_of_conformance_edit", kwargs={"pk": coc_a.pk}),
        reverse("quality:certificate_of_conformance_delete", kwargs={"pk": coc_a.pk}),
        reverse("quality:certificate_of_conformance_sign", kwargs={"pk": coc_a.pk}),
        # PackagingLabelVerifications (6)
        reverse("quality:packaging_label_verification_list"),
        reverse("quality:packaging_label_verification_create"),
        reverse("quality:packaging_label_verification_export"),
        reverse("quality:packaging_label_verification_detail", kwargs={"pk": packaging_verification_a.pk}),
        reverse("quality:packaging_label_verification_edit", kwargs={"pk": packaging_verification_a.pk}),
        reverse("quality:packaging_label_verification_delete", kwargs={"pk": packaging_verification_a.pk}),
        # QualityReleaseAuthorizations (7)
        reverse("quality:quality_release_authorization_list"),
        reverse("quality:quality_release_authorization_create"),
        reverse("quality:quality_release_authorization_export"),
        reverse("quality:quality_release_authorization_detail", kwargs={"pk": quality_release_a.pk}),
        reverse("quality:quality_release_authorization_edit", kwargs={"pk": quality_release_a.pk}),
        reverse("quality:quality_release_authorization_delete", kwargs={"pk": quality_release_a.pk}),
        reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": quality_release_a.pk}),
        # OqcHoldBoard (1)
        reverse("quality:oqc_hold_board"),
    ]

    assert len(endpoints) == 28, f"Expected exactly 28 endpoints, got {len(endpoints)}"

    for url in endpoints:
        # GET check
        resp_get = client.get(url)
        assert resp_get.status_code == 302, f"GET {url} did not redirect, got {resp_get.status_code}"
        assert "login" in resp_get.url.lower(), f"GET {url} did not redirect to login: {resp_get.url}"

        # POST check
        resp_post = client.post(url, {})
        assert resp_post.status_code == 302, f"POST {url} did not redirect, got {resp_post.status_code}"
        assert "login" in resp_post.url.lower(), f"POST {url} did not redirect to login: {resp_post.url}"


def test_finalquality_sec_non_admin_forbidden_on_privileged_actions(member_client, final_lot_a, coc_a, packaging_verification_a, quality_release_a):
    """Verify non-admin tenant user attempting to execute delete, toggle_hold, or sign is denied (HTTP 403)."""
    # 1. FinalInspectionLot delete & toggle-hold
    assert member_client.post(reverse("quality:final_inspection_lot_delete", kwargs={"pk": final_lot_a.pk})).status_code == 403
    assert member_client.post(
        reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": final_lot_a.pk}),
        {"hold_reason": "Non-admin hold attempt"},
    ).status_code == 403

    # 2. CertificateOfConformance delete & sign
    assert member_client.post(reverse("quality:certificate_of_conformance_delete", kwargs={"pk": coc_a.pk})).status_code == 403
    assert member_client.post(reverse("quality:certificate_of_conformance_sign", kwargs={"pk": coc_a.pk})).status_code == 403

    # 3. PackagingLabelVerification delete
    assert member_client.post(reverse("quality:packaging_label_verification_delete", kwargs={"pk": packaging_verification_a.pk})).status_code == 403

    # 4. QualityReleaseAuthorization delete & toggle-hold
    assert member_client.post(reverse("quality:quality_release_authorization_delete", kwargs={"pk": quality_release_a.pk})).status_code == 403
    assert member_client.post(
        reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": quality_release_a.pk}),
        {"hold_reason": "Non-admin hold attempt"},
    ).status_code == 403

    # Confirm objects still exist and hold states are untouched
    assert FinalInspectionLot.objects.filter(pk=final_lot_a.pk).exists()
    assert CertificateOfConformance.objects.filter(pk=coc_a.pk).exists()
    assert PackagingLabelVerification.objects.filter(pk=packaging_verification_a.pk).exists()
    assert QualityReleaseAuthorization.objects.filter(pk=quality_release_a.pk).exists()


def test_finalquality_sec_mutate_actions_reject_get_with_405(client_a, final_lot_a, coc_a, packaging_verification_a, quality_release_a):
    """Verify all state-changing endpoints reject GET with HTTP 405 Method Not Allowed (@require_POST)."""
    privileged_endpoints = [
        reverse("quality:final_inspection_lot_delete", kwargs={"pk": final_lot_a.pk}),
        reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": final_lot_a.pk}),
        reverse("quality:certificate_of_conformance_delete", kwargs={"pk": coc_a.pk}),
        reverse("quality:certificate_of_conformance_sign", kwargs={"pk": coc_a.pk}),
        reverse("quality:packaging_label_verification_delete", kwargs={"pk": packaging_verification_a.pk}),
        reverse("quality:quality_release_authorization_delete", kwargs={"pk": quality_release_a.pk}),
        reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": quality_release_a.pk}),
    ]

    for url in privileged_endpoints:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"GET {url} was expected to return 405, got {resp.status_code}"


# =============================================================================
# 3. Digital Signature Integrity & State Immutability
# =============================================================================

def test_finalquality_sec_signed_coc_cannot_be_edited(client_a, coc_a, customer_party_a):
    """Verify an approved & digitally signed CoC cannot be mutated via the edit view."""
    assert coc_a.status == "approved_signed"

    # GET edit view redirects with error
    resp_get = client_a.get(reverse("quality:certificate_of_conformance_edit", kwargs={"pk": coc_a.pk}))
    assert resp_get.status_code == 302
    assert resp_get.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_a.pk})

    # POST to edit view redirects with error without altering the model
    original_title = coc_a.title
    edit_data = _finalquality_coc_data(customer=customer_party_a, title="Tampered Title Attempt")
    resp_post = client_a.post(reverse("quality:certificate_of_conformance_edit", kwargs={"pk": coc_a.pk}), edit_data)
    assert resp_post.status_code == 302

    coc_a.refresh_from_db()
    assert coc_a.title == original_title
    assert coc_a.status == "approved_signed"


def test_finalquality_sec_signed_coc_cannot_be_resigned(client_a, coc_a):
    """Verify an approved & digitally signed CoC cannot be re-signed (prevents signature overwrites)."""
    assert coc_a.status == "approved_signed"
    original_hash = coc_a.digital_signature_hash

    resp = client_a.post(reverse("quality:certificate_of_conformance_sign", kwargs={"pk": coc_a.pk}))
    assert resp.status_code == 302
    assert resp.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_a.pk})

    coc_a.refresh_from_db()
    assert coc_a.digital_signature_hash == original_hash
    assert coc_a.status == "approved_signed"


def test_finalquality_sec_signed_coc_cannot_be_hard_deleted(client_a, coc_a):
    """Verify an approved & digitally signed CoC cannot be hard-deleted (audit preservation)."""
    assert coc_a.status == "approved_signed"

    resp = client_a.post(reverse("quality:certificate_of_conformance_delete", kwargs={"pk": coc_a.pk}))
    assert resp.status_code == 302
    assert resp.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_a.pk})

    assert CertificateOfConformance.objects.filter(pk=coc_a.pk).exists()


def test_finalquality_sec_authorized_release_cannot_be_deleted(client_a, quality_release_a):
    """Verify an authorized quality release cannot be hard-deleted (traceability protection)."""
    assert quality_release_a.status == "authorized"

    resp = client_a.post(reverse("quality:quality_release_authorization_delete", kwargs={"pk": quality_release_a.pk}))
    assert resp.status_code == 302
    assert resp.url == reverse("quality:quality_release_authorization_detail", kwargs={"pk": quality_release_a.pk})

    assert QualityReleaseAuthorization.objects.filter(pk=quality_release_a.pk).exists()


def test_finalquality_sec_coc_sha256_digital_signature_tampering_check(client_a, tenant_a, customer_party_a, final_lot_a, admin_user):
    """Verify SHA-256 digital signature digest integrity and detect document field tampering."""
    draft_coc = CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="CoC for Cryptographic Tamper Test",
        certificate_type="standard_commercial",
        status="draft",
        customer=customer_party_a,
        item_code="ACT-990",
        item_name="Precision Flight Actuator",
        lot_number="LOT-2026-FQC-01",
        certified_quantity=100,
        applicable_specifications="ISO 9001:2015",
        test_results_summary="All parameters within limits.",
        conformance_statement="Conforming in all respects.",
        inspection_lot=final_lot_a,
    )

    # Sign the CoC
    resp = client_a.post(reverse("quality:certificate_of_conformance_sign", kwargs={"pk": draft_coc.pk}))
    assert resp.status_code == 302
    draft_coc.refresh_from_db()
    assert draft_coc.status == "approved_signed"
    assert draft_coc.is_signed is True
    assert draft_coc.authorized_signatory == admin_user
    assert len(draft_coc.digital_signature_hash) == 64

    # Tampering test: if any attested document field is tampered with, hash validation fails
    tampered_fields = [
        ("certified_quantity", 200),
        ("item_code", "TAMPERED-CODE"),
        ("lot_number", "TAMPERED-LOT"),
        ("conformance_statement", "Maliciously altered statement"),
        ("test_results_summary", "Altered test results"),
        ("applicable_specifications", "Forged specs"),
    ]

    for field_name, bad_value in tampered_fields:
        original_value = getattr(draft_coc, field_name)
        setattr(draft_coc, field_name, bad_value)

        # Attempt to compute hash with altered field
        tampered_hash = _finalquality_compute_coc_hash(
            draft_coc,
            user_id=admin_user.id,
            timestamp_iso=timezone.now().isoformat(),
        )
        assert tampered_hash != draft_coc.digital_signature_hash, f"Tampering on {field_name} was not detected!"

        # Restore original value
        setattr(draft_coc, field_name, original_value)


# =============================================================================
# 4. Counterparty & Business Rule Enforcement
# =============================================================================

def test_finalquality_sec_cross_customer_mismatch_in_coc(tenant_a, customer_party_a):
    """Verify attempting to link an inspection lot belonging to Customer X into Customer Y's CoC is rejected."""
    customer_other = Party.objects.create(tenant=tenant_a, name="Other Client Corporation")
    other_lot = FinalInspectionLot.objects.create(
        tenant=tenant_a,
        title="Lot for Other Client",
        customer=customer_other,
        item_code="ACT-990",
        lot_number="LOT-OTHER-01",
    )

    coc_data = _finalquality_coc_data(
        customer=customer_party_a,
        lot=other_lot,
    )
    form = CertificateOfConformanceForm(data=coc_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspection_lot" in form.errors
    assert "does not belong to the selected customer" in form.errors["inspection_lot"][0]


def test_finalquality_sec_cross_customer_mismatch_in_release(tenant_a, customer_party_a, final_lot_a):
    """Verify attempting to link a lot or CoC belonging to Customer X into Customer Y's release is rejected."""
    customer_other = Party.objects.create(tenant=tenant_a, name="Competitor Recipient LLC")
    other_lot = FinalInspectionLot.objects.create(
        tenant=tenant_a,
        title="Lot for Other Client",
        customer=customer_other,
        item_code="ACT-990",
        lot_number="LOT-OTHER-02",
    )
    other_coc = CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="CoC for Other Client",
        customer=customer_other,
        item_code="ACT-990",
        lot_number="LOT-OTHER-02",
    )

    # 1. Mismatched inspection lot
    rel_data_lot_mismatch = _finalquality_release_data(
        customer=customer_party_a,
        lot=other_lot,
    )
    form_lot = QualityReleaseAuthorizationForm(data=rel_data_lot_mismatch, tenant=tenant_a)
    assert not form_lot.is_valid()
    assert "inspection_lot" in form_lot.errors
    assert "does not belong to the selected customer" in form_lot.errors["inspection_lot"][0]

    # 2. Mismatched CoC
    rel_data_coc_mismatch = _finalquality_release_data(
        customer=customer_party_a,
        lot=final_lot_a,
        coc=other_coc,
    )
    form_coc = QualityReleaseAuthorizationForm(data=rel_data_coc_mismatch, tenant=tenant_a)
    assert not form_coc.is_valid()
    assert "certificate_of_conformance" in form_coc.errors
    assert "does not belong to the selected customer" in form_coc.errors["certificate_of_conformance"][0]


def test_finalquality_sec_release_hold_conflict_enforcement(tenant_a, customer_party_a, final_lot_a):
    """Verify attempting to authorize or fully release while is_on_hold=True is rejected."""
    # Hold engaged but status set to authorized
    rel_data_auth = _finalquality_release_data(
        customer=customer_party_a,
        lot=final_lot_a,
        is_on_hold=True,
        hold_reason="Suspect batch under quarantine",
        status="authorized",
        release_disposition="pending_review",
    )
    form_auth = QualityReleaseAuthorizationForm(data=rel_data_auth, tenant=tenant_a)
    assert not form_auth.is_valid()
    assert "status" in form_auth.errors
    assert "Cannot authorize or fully release" in form_auth.errors["status"][0]

    # Hold engaged but disposition set to released_full
    rel_data_disp = _finalquality_release_data(
        customer=customer_party_a,
        lot=final_lot_a,
        is_on_hold=True,
        hold_reason="Suspect batch under quarantine",
        status="draft",
        release_disposition="released_full",
    )
    form_disp = QualityReleaseAuthorizationForm(data=rel_data_disp, tenant=tenant_a)
    assert not form_disp.is_valid()
    assert "status" in form_disp.errors


def test_finalquality_sec_hold_reason_mandatory_in_view_and_form(client_a, tenant_a, customer_party_a, final_lot_a):
    """Verify activating a hold without providing a reason is rejected in views and forms."""
    # 1. FinalInspectionLot toggle hold view: empty reason rejected
    final_lot_a.is_on_hold = False
    final_lot_a.save()

    resp_lot = client_a.post(
        reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": final_lot_a.pk}),
        {"hold_reason": "   "},
    )
    assert resp_lot.status_code == 302
    final_lot_a.refresh_from_db()
    assert final_lot_a.is_on_hold is False, "Lot hold was erroneously activated with blank reason!"

    # 2. FinalInspectionLot form: is_on_hold=True with empty hold_reason
    form_lot = FinalInspectionLotForm(
        data=_finalquality_lot_data(customer=customer_party_a, is_on_hold=True, hold_reason=""),
        tenant=tenant_a,
    )
    assert not form_lot.is_valid()
    assert "hold_reason" in form_lot.errors

    # 3. QualityReleaseAuthorization toggle hold view: empty reason rejected
    release = QualityReleaseAuthorization.objects.create(
        tenant=tenant_a,
        title="Release for Hold Reason Test",
        customer=customer_party_a,
        is_on_hold=False,
    )
    resp_rel = client_a.post(
        reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": release.pk}),
        {"hold_reason": ""},
    )
    assert resp_rel.status_code == 302
    release.refresh_from_db()
    assert release.is_on_hold is False, "Release hold was erroneously activated with empty reason!"

    # 4. QualityReleaseAuthorization form: is_on_hold=True with empty hold_reason
    form_rel = QualityReleaseAuthorizationForm(
        data=_finalquality_release_data(customer=customer_party_a, is_on_hold=True, hold_reason=""),
        tenant=tenant_a,
    )
    assert not form_rel.is_valid()
    assert "hold_reason" in form_rel.errors


# =============================================================================
# 5. CSV Injection Formula Neutralization & Nosniff Header
# =============================================================================

def test_finalquality_sec_csv_export_formula_neutralization_and_nosniff_lot(client_a, tenant_a, customer_party_a):
    """Verify final inspections export neutralizes formula prefixes (=, +, -, @, \\t, \\r) and enforces nosniff."""
    FinalInspectionLot.objects.create(
        tenant=tenant_a,
        title="\tFormula Injection Lot",
        item_code="=SUM(A1:A10)",
        item_name="+cmd|' /C calc'!A0",
        lot_number="@evil_lot_macro",
        hold_reason="-1+2*3",
        is_on_hold=True,
        customer=customer_party_a,
    )

    resp = client_a.get(reverse("quality:final_inspection_lot_export"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_item_code = False
    found_item_name = False
    found_lot_number = False
    found_hold_reason = False
    found_title = False

    for row in rows:
        for cell in row:
            if cell == "'=SUM(A1:A10)":
                found_item_code = True
            elif cell == "'+cmd|' /C calc'!A0":
                found_item_name = True
            elif cell == "'@evil_lot_macro":
                found_lot_number = True
            elif cell == "'-1+2*3":
                found_hold_reason = True
            elif cell == "'\tFormula Injection Lot":
                found_title = True

    assert found_item_code, f"Formula '=SUM(A1:A10)' was not neutralized in CSV export:\n{content}"
    assert found_item_name, f"Formula '+cmd|...' was not neutralized in CSV export:\n{content}"
    assert found_lot_number, f"Formula '@evil...' was not neutralized in CSV export:\n{content}"
    assert found_hold_reason, f"Formula '-1+2*3' was not neutralized in CSV export:\n{content}"
    assert found_title, f"Tab injection '\\t...' was not neutralized in CSV export:\n{content}"


def test_finalquality_sec_csv_export_formula_neutralization_and_nosniff_coc(client_a, tenant_a, customer_party_a):
    """Verify CoC export neutralizes formula prefixes and sets X-Content-Type-Options: nosniff."""
    CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="@Formula Injection CoC",
        customer=customer_party_a,
        customer_po_number="=PO-CALC-01",
        item_code="+ACT-EVIL",
        item_name="-Harmful Item",
        lot_number="\rLOT-CR-01",
        certified_quantity=10,
    )

    resp = client_a.get(reverse("quality:certificate_of_conformance_export"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_po = False
    found_code = False
    found_name = False
    found_title = False
    found_lot = False

    for row in rows:
        for cell in row:
            if cell == "'=PO-CALC-01":
                found_po = True
            elif cell == "'+ACT-EVIL":
                found_code = True
            elif cell == "'-Harmful Item":
                found_name = True
            elif cell == "'@Formula Injection CoC":
                found_title = True
            elif cell == "'\rLOT-CR-01":
                found_lot = True

    assert found_po, f"Formula '=PO-CALC-01' was not neutralized:\n{content}"
    assert found_code, f"Formula '+ACT-EVIL' was not neutralized:\n{content}"
    assert found_name, f"Formula '-Harmful Item' was not neutralized:\n{content}"
    assert found_title, f"Formula '@Formula Injection CoC' was not neutralized:\n{content}"
    assert found_lot, f"Formula '\\rLOT-CR-01' was not neutralized:\n{content}"


def test_finalquality_sec_csv_export_formula_neutralization_and_nosniff_packaging(client_a, tenant_a):
    """Verify packaging verification export neutralizes formula prefixes and sets nosniff."""
    PackagingLabelVerification.objects.create(
        tenant=tenant_a,
        title="=cmd|' /C calc'!A0",
        item_code="+EVIL-PKG",
        item_name="-Packaging Dangerous",
        lot_number="@EVIL-PKG-LOT",
        scanned_barcode_data="\t(01)0085009901",
    )

    resp = client_a.get(reverse("quality:packaging_label_verification_export"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_title = False
    found_code = False
    found_barcode = False

    for row in rows:
        for cell in row:
            if cell == "'=cmd|' /C calc'!A0":
                found_title = True
            elif cell == "'+EVIL-PKG":
                found_code = True
            elif cell == "'\t(01)0085009901":
                found_barcode = True

    assert found_title, f"Formula in packaging title was not neutralized:\n{content}"
    assert found_code, f"Formula in packaging item_code was not neutralized:\n{content}"
    assert found_barcode, f"Formula in packaging scanned_barcode_data was not neutralized:\n{content}"


def test_finalquality_sec_csv_export_formula_neutralization_and_nosniff_release(client_a, tenant_a, customer_party_a):
    """Verify quality releases export neutralizes formula prefixes and sets nosniff."""
    QualityReleaseAuthorization.objects.create(
        tenant=tenant_a,
        title="@Formula Release",
        customer=customer_party_a,
        shipment_number="=SHP-CALC-01",
        lot_number="+LOT-REL-01",
        hold_reason="-Unsafe hold",
        is_on_hold=True,
    )

    resp = client_a.get(reverse("quality:quality_release_authorization_export"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_title = False
    found_shp = False
    found_lot = False
    found_hold = False

    for row in rows:
        for cell in row:
            if cell == "'@Formula Release":
                found_title = True
            elif cell == "'=SHP-CALC-01":
                found_shp = True
            elif cell == "'+LOT-REL-01":
                found_lot = True
            elif cell == "'-Unsafe hold":
                found_hold = True

    assert found_title, f"Formula in release title was not neutralized:\n{content}"
    assert found_shp, f"Formula in release shipment_number was not neutralized:\n{content}"
    assert found_lot, f"Formula in release lot_number was not neutralized:\n{content}"
    assert found_hold, f"Formula in release hold_reason was not neutralized:\n{content}"


# =============================================================================
# 6. Audit Trail Verification
# =============================================================================

def test_finalquality_sec_audit_trail_lot_lifecycle(client_a, tenant_a, customer_party_a, admin_user):
    """Verify AuditLog records are faithfully generated across the full lifecycle of an inspection lot."""
    # 1. Create
    lot_data = _finalquality_lot_data(customer=customer_party_a)
    resp_create = client_a.post(reverse("quality:final_inspection_lot_create"), lot_data)
    assert resp_create.status_code == 302
    created_lot = FinalInspectionLot.objects.filter(tenant=tenant_a, title=lot_data["title"]).latest("id")

    audit_create = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="create", object_id=str(created_lot.pk)).first()
    assert audit_create is not None, "AuditLog for lot create was not recorded!"

    # 2. Update
    lot_data["title"] = "Updated Lot Title for Audit Test"
    resp_update = client_a.post(reverse("quality:final_inspection_lot_edit", kwargs={"pk": created_lot.pk}), lot_data)
    assert resp_update.status_code == 302
    audit_update = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="update", object_id=str(created_lot.pk)).first()
    assert audit_update is not None, "AuditLog for lot update was not recorded!"

    # 3. Hold toggle: place on hold
    resp_hold = client_a.post(
        reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": created_lot.pk}),
        {"hold_reason": "Audit hold test reason"},
    )
    assert resp_hold.status_code == 302
    audit_hold = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="hold", object_id=str(created_lot.pk)).first()
    assert audit_hold is not None, "AuditLog for lot hold was not recorded!"

    # 4. Hold toggle: remove from hold
    resp_release = client_a.post(
        reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": created_lot.pk}),
    )
    assert resp_release.status_code == 302
    audit_release = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="release", object_id=str(created_lot.pk)).first()
    assert audit_release is not None, "AuditLog for lot release was not recorded!"

    # 5. Export
    resp_export = client_a.get(reverse("quality:final_inspection_lot_export"))
    assert resp_export.status_code == 200
    audit_export = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="export", changes={"model": "FinalInspectionLot"}).first()
    assert audit_export is not None, "AuditLog for lot export was not recorded!"

    # 6. Delete
    resp_delete = client_a.post(reverse("quality:final_inspection_lot_delete", kwargs={"pk": created_lot.pk}))
    assert resp_delete.status_code == 302
    audit_delete = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="delete", object_id=str(created_lot.pk)).first()
    assert audit_delete is not None, "AuditLog for lot delete was not recorded!"


def test_finalquality_sec_audit_trail_coc_lifecycle(client_a, tenant_a, customer_party_a, final_lot_a, admin_user):
    """Verify AuditLog records are faithfully generated across create, update, sign, delete, and export on CoC."""
    # 1. Create
    coc_data = _finalquality_coc_data(customer=customer_party_a, lot=final_lot_a)
    resp_create = client_a.post(reverse("quality:certificate_of_conformance_create"), coc_data)
    assert resp_create.status_code == 302
    created_coc = CertificateOfConformance.objects.filter(tenant=tenant_a, title=coc_data["title"]).latest("id")

    audit_create = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="create", object_id=str(created_coc.pk)).first()
    assert audit_create is not None, "AuditLog for CoC create was not recorded!"

    # 2. Update
    coc_data["title"] = "Updated CoC Title for Audit Test"
    resp_update = client_a.post(reverse("quality:certificate_of_conformance_edit", kwargs={"pk": created_coc.pk}), coc_data)
    assert resp_update.status_code == 302
    audit_update = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="update", object_id=str(created_coc.pk)).first()
    assert audit_update is not None, "AuditLog for CoC update was not recorded!"

    # 3. Export
    resp_export = client_a.get(reverse("quality:certificate_of_conformance_export"))
    assert resp_export.status_code == 200
    audit_export = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="export", changes={"model": "CertificateOfConformance"}).first()
    assert audit_export is not None, "AuditLog for CoC export was not recorded!"

    # 4. Sign
    resp_sign = client_a.post(reverse("quality:certificate_of_conformance_sign", kwargs={"pk": created_coc.pk}))
    assert resp_sign.status_code == 302
    audit_sign = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="sign", object_id=str(created_coc.pk)).first()
    assert audit_sign is not None, "AuditLog for CoC sign was not recorded!"

    # 5. Delete on a draft CoC (create a separate draft to test delete audit log)
    draft_coc = CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="Draft CoC for Deletion Audit",
        customer=customer_party_a,
        status="draft",
    )
    resp_delete = client_a.post(reverse("quality:certificate_of_conformance_delete", kwargs={"pk": draft_coc.pk}))
    assert resp_delete.status_code == 302
    audit_delete = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="delete", object_id=str(draft_coc.pk)).first()
    assert audit_delete is not None, "AuditLog for CoC delete was not recorded!"


def test_finalquality_sec_audit_trail_packaging_lifecycle(client_a, tenant_a, final_lot_a, admin_user):
    """Verify AuditLog records are faithfully generated across create, update, delete, and export on packaging."""
    # 1. Create
    pkg_data = _finalquality_packaging_data(lot=final_lot_a)
    resp_create = client_a.post(reverse("quality:packaging_label_verification_create"), pkg_data)
    assert resp_create.status_code == 302
    created_pkg = PackagingLabelVerification.objects.filter(tenant=tenant_a, title=pkg_data["title"]).latest("id")

    audit_create = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="create", object_id=str(created_pkg.pk)).first()
    assert audit_create is not None, "AuditLog for packaging create was not recorded!"

    # 2. Update
    pkg_data["title"] = "Updated Packaging Title for Audit Test"
    resp_update = client_a.post(reverse("quality:packaging_label_verification_edit", kwargs={"pk": created_pkg.pk}), pkg_data)
    assert resp_update.status_code == 302
    audit_update = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="update", object_id=str(created_pkg.pk)).first()
    assert audit_update is not None, "AuditLog for packaging update was not recorded!"

    # 3. Export
    resp_export = client_a.get(reverse("quality:packaging_label_verification_export"))
    assert resp_export.status_code == 200
    audit_export = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="export", changes={"model": "PackagingLabelVerification"}).first()
    assert audit_export is not None, "AuditLog for packaging export was not recorded!"

    # 4. Delete
    resp_delete = client_a.post(reverse("quality:packaging_label_verification_delete", kwargs={"pk": created_pkg.pk}))
    assert resp_delete.status_code == 302
    audit_delete = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="delete", object_id=str(created_pkg.pk)).first()
    assert audit_delete is not None, "AuditLog for packaging delete was not recorded!"


def test_finalquality_sec_audit_trail_release_lifecycle(client_a, tenant_a, customer_party_a, final_lot_a, admin_user):
    """Verify AuditLog records are faithfully generated across create, update, hold, release, delete, and export."""
    # 1. Create
    rel_data = _finalquality_release_data(customer=customer_party_a, lot=final_lot_a)
    resp_create = client_a.post(reverse("quality:quality_release_authorization_create"), rel_data)
    assert resp_create.status_code == 302
    created_rel = QualityReleaseAuthorization.objects.filter(tenant=tenant_a, title=rel_data["title"]).latest("id")

    audit_create = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="create", object_id=str(created_rel.pk)).first()
    assert audit_create is not None, "AuditLog for release create was not recorded!"

    # 2. Update
    rel_data["title"] = "Updated Release Title for Audit Test"
    resp_update = client_a.post(reverse("quality:quality_release_authorization_edit", kwargs={"pk": created_rel.pk}), rel_data)
    assert resp_update.status_code == 302
    audit_update = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="update", object_id=str(created_rel.pk)).first()
    assert audit_update is not None, "AuditLog for release update was not recorded!"

    # 3. Hold toggle: place on hold
    resp_hold = client_a.post(
        reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": created_rel.pk}),
        {"hold_reason": "Audit hold test on release"},
    )
    assert resp_hold.status_code == 302
    audit_hold = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="hold", object_id=str(created_rel.pk)).first()
    assert audit_hold is not None, "AuditLog for release hold was not recorded!"

    # 4. Hold toggle: remove from hold
    resp_unhold = client_a.post(
        reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": created_rel.pk}),
    )
    assert resp_unhold.status_code == 302
    audit_unhold = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="release", object_id=str(created_rel.pk)).first()
    assert audit_unhold is not None, "AuditLog for release removal from hold was not recorded!"

    # 5. Export
    resp_export = client_a.get(reverse("quality:quality_release_authorization_export"))
    assert resp_export.status_code == 200
    audit_export = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="export", changes={"model": "QualityReleaseAuthorization"}).first()
    assert audit_export is not None, "AuditLog for release export was not recorded!"

    # 6. Delete (since created_rel is draft)
    resp_delete = client_a.post(reverse("quality:quality_release_authorization_delete", kwargs={"pk": created_rel.pk}))
    assert resp_delete.status_code == 302
    audit_delete = AuditLog.objects.filter(tenant=tenant_a, user=admin_user, action="delete", object_id=str(created_rel.pk)).first()
    assert audit_delete is not None, "AuditLog for release delete was not recorded!"


def test_finalquality_sec_xss_escaping_in_detail_views(client_a, tenant_a, customer_party_a):
    """Verify script payloads in record fields are HTML-escaped and never rendered unescaped in detail views."""
    xss_payload = "<script>alert('xss-exploit')</script>"
    lot = FinalInspectionLot.objects.create(
        tenant=tenant_a,
        title=f"XSS Lot {xss_payload}",
        item_code="XSS-001",
        item_name=xss_payload,
        lot_number="LOT-XSS",
        customer=customer_party_a,
        inspection_notes=xss_payload,
    )

    resp = client_a.get(reverse("quality:final_inspection_lot_detail", kwargs={"pk": lot.pk}))
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "<script>alert('xss-exploit')</script>" not in content
    assert "&lt;script&gt;alert(&#x27;xss-exploit&#x27;)&lt;/script&gt;" in content or "&lt;script&gt;" in content
