"""View unit tests for Sub-module 12.9: Final Quality Control / Outgoing Quality Control (FQC / OQC).

Covers all 28 views, routes, query filters, search, pagination, context contracts,
form submissions (valid & invalid), status progressions, custom business actions,
CSV exports, deletion guards, and multi-tenant isolation:
1. FinalInspectionLots (list, detail, create, edit, delete, toggle_hold, export)
2. CertificatesOfConformance (list, detail, create, edit, delete, sign, export)
3. PackagingLabelVerifications (list, detail, create, edit, delete, export)
4. QualityReleaseAuthorizations (list, detail, create, edit, delete, toggle_hold, export)
5. OqcHoldBoard (oqc_hold_board)
6. Cross-tenant isolation & unauthenticated redirection
"""
import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Party
from apps.quality.models import (
    CertificateOfConformance,
    FinalInspectionLot,
    PackagingLabelVerification,
    QualityReleaseAuthorization,
)

User = get_user_model()
pytestmark = pytest.mark.django_db


# =============================================================================
# Helper Utilities (Prefix: _finalquality_*)
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


# =============================================================================
# 1. FinalInspectionLots Views
# =============================================================================

def test_finalquality_view_lot_list_get_and_context(client, admin_user, final_lot_a):
    """Verify FinalInspectionLots list GET returns 200 with required context keys and lot content."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "inspection_lots",
        "page_obj",
        "paginator",
        "q",
        "stage",
        "status",
        "decision",
        "on_hold",
        "stage_choices",
        "status_choices",
        "decision_choices",
        "total_count",
        "accepted_count",
        "hold_count",
        "rejected_count",
        "STAGE_CSS",
        "STATUS_CSS",
        "DECISION_CSS",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from final inspection lot list context"

    assert final_lot_a in resp.context["inspection_lots"]
    assert final_lot_a.number in resp.content.decode()
    assert final_lot_a.title in resp.content.decode()


def test_finalquality_view_lot_list_search_and_filters(client, admin_user, tenant_a, final_lot_a, customer_party_a):
    """Verify list filters by query, stage, status, decision, and on_hold flags."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_list")

    # Match search by title
    resp = client.get(url, {"q": "Precision Actuators"})
    assert resp.status_code == 200
    assert final_lot_a in resp.context["inspection_lots"]

    # Match search by item_code
    resp = client.get(url, {"q": "ACT-990"})
    assert resp.status_code == 200
    assert final_lot_a in resp.context["inspection_lots"]

    # Match filter by stage
    resp = client.get(url, {"stage": "post_packaging_oqc"})
    assert resp.status_code == 200
    assert final_lot_a in resp.context["inspection_lots"]

    # Match filter by status
    resp = client.get(url, {"status": "completed"})
    assert resp.status_code == 200
    assert final_lot_a in resp.context["inspection_lots"]

    # Match filter by decision
    resp = client.get(url, {"decision": "accepted"})
    assert resp.status_code == 200
    assert final_lot_a in resp.context["inspection_lots"]

    # Match filter by on_hold == "0"
    resp = client.get(url, {"on_hold": "0"})
    assert resp.status_code == 200
    assert final_lot_a in resp.context["inspection_lots"]

    # Non-matching on_hold == "1"
    resp = client.get(url, {"on_hold": "1"})
    assert resp.status_code == 200
    assert final_lot_a not in resp.context["inspection_lots"]

    # Non-matching search query
    resp_nomatch = client.get(url, {"q": "NON_EXISTENT_QUERY_XYZ"})
    assert resp_nomatch.status_code == 200
    assert final_lot_a not in resp_nomatch.context["inspection_lots"]


def test_finalquality_view_lot_list_junk_parameters_and_pagination(client, admin_user, tenant_a, customer_party_a):
    """Verify list handles junk params safely and paginates beyond PAGE_SIZE."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_list")

    # Junk params
    resp_junk = client.get(url, {
        "stage": "bogus_stage",
        "status": "bogus_status",
        "decision": "bogus_decision",
        "on_hold": "not_a_boolean",
        "page": "invalid_page_number",
    })
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1

    # Bulk create to test pagination
    lots_to_create = [
        FinalInspectionLot(
            tenant=tenant_a,
            title=f"Paged Final Inspection Lot {i}",
            item_code="ACT-990",
            lot_quantity=10,
            sample_size_inspected=2,
            customer=customer_party_a,
        )
        for i in range(16)
    ]
    FinalInspectionLot.objects.bulk_create(lots_to_create)

    resp_p2 = client.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2
    assert resp_p2.context["paginator"].num_pages >= 2


def test_finalquality_view_lot_detail_get_and_context(client, admin_user, final_lot_a):
    """Verify lot detail GET returns 200 with required context keys and lot details."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_detail", kwargs={"pk": final_lot_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["lot"] == final_lot_a
    assert "STAGE_CSS" in resp.context
    assert "STATUS_CSS" in resp.context
    assert "DECISION_CSS" in resp.context
    assert final_lot_a.number in resp.content.decode()
    assert final_lot_a.title in resp.content.decode()


def test_finalquality_view_lot_create_get(client, admin_user):
    """Verify lot create GET renders form with is_edit=False and expected title."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["lot"] is None
    assert resp.context["title"] == "New Final Inspection Lot"


def test_finalquality_view_lot_create_post_valid(client, admin_user, tenant_a, customer_party_a):
    """Verify valid POST creates FinalInspectionLot, writes audit log, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_create")
    post_data = _finalquality_lot_data(
        customer=customer_party_a,
        title="Created Flight Actuator Inspection Lot",
        item_code="ACT-CREATED-01",
        lot_quantity=200,
        sample_size_inspected=25,
        units_passed=25,
        units_rejected=0,
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_lot = FinalInspectionLot.objects.get(title="Created Flight Actuator Inspection Lot", tenant=tenant_a)
    assert resp.url == reverse("quality:final_inspection_lot_detail", kwargs={"pk": created_lot.pk})
    assert created_lot.item_code == "ACT-CREATED-01"
    assert created_lot.customer == customer_party_a
    assert created_lot.tenant == tenant_a

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        target__contains=created_lot.number,
    ).exists()


def test_finalquality_view_lot_create_post_invalid(client, admin_user):
    """Verify invalid POST returns 200 with form validation errors."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_create")
    # Sample size > lot quantity violates validation
    post_data = _finalquality_lot_data(
        title="",
        lot_quantity=10,
        sample_size_inspected=50,
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_finalquality_view_lot_edit_get(client, admin_user, final_lot_a):
    """Verify lot edit GET returns 200 with populated form."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_edit", kwargs={"pk": final_lot_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["lot"] == final_lot_a


def test_finalquality_view_lot_edit_post_valid(client, admin_user, tenant_a, final_lot_a, customer_party_a):
    """Verify valid POST updates the lot and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_edit", kwargs={"pk": final_lot_a.pk})
    post_data = _finalquality_lot_data(
        customer=customer_party_a,
        title="Updated Flight Actuator Inspection Lot",
        inspection_notes="Updated notes from second review.",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:final_inspection_lot_detail", kwargs={"pk": final_lot_a.pk})

    final_lot_a.refresh_from_db()
    assert final_lot_a.title == "Updated Flight Actuator Inspection Lot"
    assert final_lot_a.inspection_notes == "Updated notes from second review."

    # Verify audit log
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        target__contains=final_lot_a.number,
    ).exists()


def test_finalquality_view_lot_edit_post_invalid(client, admin_user, final_lot_a):
    """Verify invalid POST on edit renders 200 with errors."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_edit", kwargs={"pk": final_lot_a.pk})
    resp = client.post(url, {"title": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "title" in resp.context["form"].errors


def test_finalquality_view_lot_delete_methods_and_permissions(client, admin_user, member_user, tenant_a, customer_party_a):
    """Verify delete requires POST, tenant admin permission, and successfully deletes record."""
    lot_to_delete = FinalInspectionLot.objects.create(
        tenant=tenant_a,
        title="Lot Pending Deletion",
        item_code="ACT-DEL-01",
        customer=customer_party_a,
    )
    url = reverse("quality:final_inspection_lot_delete", kwargs={"pk": lot_to_delete.pk})

    # GET is rejected with 405 Method Not Allowed
    client.force_login(admin_user)
    resp_get = client.get(url)
    assert resp_get.status_code == 405

    # Non-admin user POST returns 403 Forbidden
    client.force_login(member_user)
    resp_forbidden = client.post(url)
    assert resp_forbidden.status_code == 403

    # Tenant admin POST deletes and redirects
    client.force_login(admin_user)
    resp_delete = client.post(url)
    assert resp_delete.status_code == 302
    assert resp_delete.url == reverse("quality:final_inspection_lot_list")
    assert not FinalInspectionLot.objects.filter(pk=lot_to_delete.pk).exists()

    # Audit log created
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", target__contains=lot_to_delete.number).exists()


def test_finalquality_view_lot_toggle_hold_methods_permissions_and_validation(client, admin_user, member_user, tenant_a, final_lot_a):
    """Verify toggle_hold requires POST, tenant admin, non-empty hold reason, and toggles hold correctly."""
    url = reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": final_lot_a.pk})

    # GET is rejected with 405
    client.force_login(admin_user)
    assert client.get(url).status_code == 405

    # Non-admin user POST returns 403
    client.force_login(member_user)
    assert client.post(url, {"hold_reason": "Suspect lot"}).status_code == 403

    # Tenant admin attempts to activate hold without a reason -> rejected with error
    client.force_login(admin_user)
    final_lot_a.is_on_hold = False
    final_lot_a.save()

    resp_no_reason = client.post(url, {"hold_reason": ""})
    assert resp_no_reason.status_code == 302
    final_lot_a.refresh_from_db()
    assert final_lot_a.is_on_hold is False

    # Tenant admin activates hold with reason
    resp_hold = client.post(url, {"hold_reason": "Calibration error on dial micrometer"})
    assert resp_hold.status_code == 302
    final_lot_a.refresh_from_db()
    assert final_lot_a.is_on_hold is True
    assert final_lot_a.hold_reason == "Calibration error on dial micrometer"

    # Audit log for hold
    assert AuditLog.objects.filter(tenant=tenant_a, action="hold", target__contains=final_lot_a.number).exists()

    # Releasing from hold (hold_reason not mandatory when releasing)
    resp_release = client.post(url)
    assert resp_release.status_code == 302
    final_lot_a.refresh_from_db()
    assert final_lot_a.is_on_hold is False

    # Audit log for release
    assert AuditLog.objects.filter(tenant=tenant_a, action="release", target__contains=final_lot_a.number).exists()


def test_finalquality_view_lot_export_csv(client, admin_user, final_lot_a):
    """Verify export returns CSV with attachment header, nosniff, and data rows."""
    client.force_login(admin_user)
    url = reverse("quality:final_inspection_lot_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "final_inspection_lots.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "Lot Number" in headers
    assert "Title" in headers
    assert "Stage" in headers
    rows = list(reader)
    assert any(final_lot_a.number in row[0] for row in rows)


# =============================================================================
# 2. CertificatesOfConformance Views
# =============================================================================

def test_finalquality_view_coc_list_get_and_context(client, admin_user, coc_a):
    """Verify CertificateOfConformance list GET returns 200 with required context keys."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_conformance_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "certificates",
        "page_obj",
        "paginator",
        "q",
        "type",
        "status",
        "customer_id",
        "type_choices",
        "status_choices",
        "customers",
        "total_count",
        "signed_count",
        "review_count",
        "TYPE_CSS",
        "STATUS_CSS",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from CoC list context"

    assert coc_a in resp.context["certificates"]
    assert coc_a.number in resp.content.decode()


def test_finalquality_view_coc_list_search_and_filters(client, admin_user, coc_a, customer_party_a):
    """Verify CoC list filters by query, type, status, and customer."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_conformance_list")

    # Match query
    resp = client.get(url, {"q": "Precision Actuators"})
    assert resp.status_code == 200
    assert coc_a in resp.context["certificates"]

    # Match type
    resp = client.get(url, {"type": "aerospace_as9100_as9102"})
    assert resp.status_code == 200
    assert coc_a in resp.context["certificates"]

    # Match status
    resp = client.get(url, {"status": "approved_signed"})
    assert resp.status_code == 200
    assert coc_a in resp.context["certificates"]

    # Match customer
    resp = client.get(url, {"customer": str(customer_party_a.pk)})
    assert resp.status_code == 200
    assert coc_a in resp.context["certificates"]

    # Mismatch
    resp = client.get(url, {"status": "draft"})
    assert resp.status_code == 200
    assert coc_a not in resp.context["certificates"]


def test_finalquality_view_coc_list_junk_parameters(client, admin_user, coc_a):
    """Verify CoC list handles junk parameters cleanly."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_conformance_list")
    resp = client.get(url, {
        "type": "invalid_type",
        "status": "invalid_status",
        "customer": "not_an_int",
        "page": "invalid_page",
    })
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 1


def test_finalquality_view_coc_detail_get_and_context(client, admin_user, coc_a):
    """Verify CoC detail GET returns 200 with required context keys and certificate content."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["certificate"] == coc_a
    assert "TYPE_CSS" in resp.context
    assert "STATUS_CSS" in resp.context
    assert coc_a.number in resp.content.decode()


def test_finalquality_view_coc_create_get(client, admin_user):
    """Verify CoC create GET renders form with is_edit=False."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_conformance_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["certificate"] is None
    assert resp.context["title"] == "New Certificate of Conformance"


def test_finalquality_view_coc_create_post_valid(client, admin_user, tenant_a, customer_party_a, final_lot_a):
    """Verify valid POST creates CertificateOfConformance and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_conformance_create")
    post_data = _finalquality_coc_data(
        customer=customer_party_a,
        lot=final_lot_a,
        title="Created CoC Flight Actuators",
        certified_quantity=100,
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_coc = CertificateOfConformance.objects.get(title="Created CoC Flight Actuators", tenant=tenant_a)
    assert resp.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": created_coc.pk})
    assert created_coc.customer == customer_party_a
    assert created_coc.inspection_lot == final_lot_a

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", target__contains=created_coc.number).exists()


def test_finalquality_view_coc_create_post_invalid(client, admin_user):
    """Verify invalid POST returns 200 with form validation errors."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_conformance_create")
    resp = client.post(url, {"title": "", "certified_quantity": 0})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_finalquality_view_coc_edit_get_and_post_valid(client, admin_user, tenant_a, customer_party_a):
    """Verify edit GET and valid POST on a draft CoC."""
    draft_coc = CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="Draft CoC for Edit",
        customer=customer_party_a,
        status="draft",
        certified_quantity=20,
    )
    url = reverse("quality:certificate_of_conformance_edit", kwargs={"pk": draft_coc.pk})

    client.force_login(admin_user)
    # GET
    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["certificate"] == draft_coc

    # POST valid update
    post_data = _finalquality_coc_data(
        customer=customer_party_a,
        title="Updated CoC After Review",
        certified_quantity=30,
    )
    resp_post = client.post(url, post_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": draft_coc.pk})

    draft_coc.refresh_from_db()
    assert draft_coc.title == "Updated CoC After Review"
    assert draft_coc.certified_quantity == 30

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", target__contains=draft_coc.number).exists()


def test_finalquality_view_coc_edit_immutability_guard(client, admin_user, tenant_a, coc_a, customer_party_a):
    """Verify editing a signed or revoked CoC is blocked and redirects with an error message."""
    client.force_login(admin_user)
    # coc_a is status="approved_signed"
    url = reverse("quality:certificate_of_conformance_edit", kwargs={"pk": coc_a.pk})

    # GET redirects to detail
    resp_get = client.get(url)
    assert resp_get.status_code == 302
    assert resp_get.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_a.pk})

    # POST also redirects to detail without modifying record
    resp_post = client.post(url, {"title": "Attempted Hack of Signed CoC"})
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_a.pk})

    coc_a.refresh_from_db()
    assert coc_a.title != "Attempted Hack of Signed CoC"

    # Test revoked state
    revoked_coc = CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="Revoked CoC",
        customer=customer_party_a,
        status="revoked",
        certified_quantity=10,
    )
    url_revoked = reverse("quality:certificate_of_conformance_edit", kwargs={"pk": revoked_coc.pk})
    resp_revoked = client.get(url_revoked)
    assert resp_revoked.status_code == 302
    assert resp_revoked.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": revoked_coc.pk})


def test_finalquality_view_coc_delete_methods_permissions_and_guard(client, admin_user, member_user, tenant_a, coc_a, customer_party_a):
    """Verify CoC delete methods, permissions, and guard preventing deletion of signed CoCs."""
    # Attempting to delete a signed CoC (coc_a)
    url_signed = reverse("quality:certificate_of_conformance_delete", kwargs={"pk": coc_a.pk})

    # GET is rejected with 405
    client.force_login(admin_user)
    assert client.get(url_signed).status_code == 405

    # Non-admin user POST returns 403
    client.force_login(member_user)
    assert client.post(url_signed).status_code == 403

    # Admin user attempts to delete signed CoC -> guarded! Redirects with error, record preserved
    client.force_login(admin_user)
    resp_guard = client.post(url_signed)
    assert resp_guard.status_code == 302
    assert resp_guard.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_a.pk})
    assert CertificateOfConformance.objects.filter(pk=coc_a.pk).exists()

    # Deleting a draft CoC succeeds
    draft_coc = CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="Draft CoC to Delete",
        customer=customer_party_a,
        status="draft",
        certified_quantity=10,
    )
    url_draft = reverse("quality:certificate_of_conformance_delete", kwargs={"pk": draft_coc.pk})
    resp_delete = client.post(url_draft)
    assert resp_delete.status_code == 302
    assert resp_delete.url == reverse("quality:certificate_of_conformance_list")
    assert not CertificateOfConformance.objects.filter(pk=draft_coc.pk).exists()

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", target__contains=draft_coc.number).exists()


def test_finalquality_view_coc_sign_methods_permissions_and_workflow(client, admin_user, member_user, tenant_a, customer_party_a, coc_a):
    """Verify signing CoC requires POST, tenant admin, blocks already signed/revoked, and calculates hash."""
    draft_coc = CertificateOfConformance.objects.create(
        tenant=tenant_a,
        title="CoC Ready to Sign",
        customer=customer_party_a,
        status="under_review",
        item_code="ACT-990",
        lot_number="LOT-2026-FQC-01",
        certified_quantity=50,
        applicable_specifications="AS9100D",
        test_results_summary="Tensile test passed",
        conformance_statement="Conforms fully",
    )
    url_draft = reverse("quality:certificate_of_conformance_sign", kwargs={"pk": draft_coc.pk})

    # GET is rejected with 405
    client.force_login(admin_user)
    assert client.get(url_draft).status_code == 405

    # Non-admin user POST returns 403
    client.force_login(member_user)
    assert client.post(url_draft).status_code == 403

    # Tenant admin signs the certificate
    client.force_login(admin_user)
    resp_sign = client.post(url_draft)
    assert resp_sign.status_code == 302
    assert resp_sign.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": draft_coc.pk})

    draft_coc.refresh_from_db()
    assert draft_coc.status == "approved_signed"
    assert draft_coc.authorized_signatory == admin_user
    assert draft_coc.signed_date == timezone.now().date()
    assert len(draft_coc.digital_signature_hash) == 64  # SHA-256 hexdigest

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="sign", target__contains=draft_coc.number).exists()

    # Attempting to re-sign an already signed certificate -> redirects with error
    resp_re_sign = client.post(url_draft)
    assert resp_re_sign.status_code == 302
    assert resp_re_sign.url == reverse("quality:certificate_of_conformance_detail", kwargs={"pk": draft_coc.pk})


def test_finalquality_view_coc_export_csv_and_c1_regression(client, admin_user, tenant_a, coc_a):
    """Verify export returns CSV and regression test for unpersisted CoC audit log (C1)."""
    client.force_login(admin_user)
    url = reverse("quality:certificate_of_conformance_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "certificates_of_conformance.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "Certificate Number" in headers
    assert "Title" in headers
    assert "Customer" in headers
    rows = list(reader)
    assert any(coc_a.number in row[0] for row in rows)

    # C1 regression check: audit log created with None instance without crashing
    export_logs = AuditLog.objects.filter(tenant=tenant_a, action="export")
    assert export_logs.exists()
    latest_log = export_logs.latest("id")
    assert latest_log.changes.get("model") == "CertificateOfConformance"


# =============================================================================
# 3. PackagingLabelVerifications Views
# =============================================================================

def test_finalquality_view_packaging_list_get_and_context(client, admin_user, packaging_verification_a):
    """Verify PackagingLabelVerification list GET returns 200 with required context keys."""
    client.force_login(admin_user)
    url = reverse("quality:packaging_label_verification_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "verifications",
        "page_obj",
        "paginator",
        "q",
        "status",
        "disposition",
        "grade",
        "status_choices",
        "disposition_choices",
        "grade_choices",
        "total_count",
        "verified_count",
        "failed_count",
        "BARCODE_CSS",
        "GRADE_CSS",
        "STATUS_CSS",
        "DISPOSITION_CSS",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from packaging list context"

    assert packaging_verification_a in resp.context["verifications"]
    assert packaging_verification_a.number in resp.content.decode()


def test_finalquality_view_packaging_list_search_and_filters(client, admin_user, packaging_verification_a):
    """Verify packaging list filters by query, status, disposition, and grade."""
    client.force_login(admin_user)
    url = reverse("quality:packaging_label_verification_list")

    # Match search
    resp = client.get(url, {"q": "Packaging Audit"})
    assert resp.status_code == 200
    assert packaging_verification_a in resp.context["verifications"]

    # Match status
    resp = client.get(url, {"status": "verified"})
    assert resp.status_code == 200
    assert packaging_verification_a in resp.context["verifications"]

    # Match disposition
    resp = client.get(url, {"disposition": "pass_released"})
    assert resp.status_code == 200
    assert packaging_verification_a in resp.context["verifications"]

    # Match grade
    resp = client.get(url, {"grade": "grade_a_4_0"})
    assert resp.status_code == 200
    assert packaging_verification_a in resp.context["verifications"]

    # Mismatch
    resp = client.get(url, {"disposition": "relabel_required"})
    assert resp.status_code == 200
    assert packaging_verification_a not in resp.context["verifications"]

    # Junk params
    resp_junk = client.get(url, {"status": "bogus", "disposition": "bogus", "grade": "bogus", "page": "invalid"})
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_finalquality_view_packaging_detail_get_and_context(client, admin_user, packaging_verification_a):
    """Verify packaging detail GET returns 200 with required context keys and verification details."""
    client.force_login(admin_user)
    url = reverse("quality:packaging_label_verification_detail", kwargs={"pk": packaging_verification_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["verification"] == packaging_verification_a
    assert "BARCODE_CSS" in resp.context
    assert "GRADE_CSS" in resp.context
    assert "STATUS_CSS" in resp.context
    assert "DISPOSITION_CSS" in resp.context
    assert packaging_verification_a.number in resp.content.decode()


def test_finalquality_view_packaging_create_get(client, admin_user):
    """Verify packaging create GET renders form with is_edit=False."""
    client.force_login(admin_user)
    url = reverse("quality:packaging_label_verification_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["verification"] is None
    assert resp.context["title"] == "New Packaging & Label Verification"


def test_finalquality_view_packaging_create_post_valid(client, admin_user, tenant_a, final_lot_a):
    """Verify valid POST creates PackagingLabelVerification and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:packaging_label_verification_create")
    post_data = _finalquality_packaging_data(
        lot=final_lot_a,
        verifier=admin_user,
        title="Created Packaging Verification Flight Unit",
        item_code="ACT-990",
        carton_count_inspected=12,
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_pkg = PackagingLabelVerification.objects.get(title="Created Packaging Verification Flight Unit", tenant=tenant_a)
    assert resp.url == reverse("quality:packaging_label_verification_detail", kwargs={"pk": created_pkg.pk})
    assert created_pkg.carton_count_inspected == 12
    assert created_pkg.verifier == admin_user

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", target__contains=created_pkg.number).exists()


def test_finalquality_view_packaging_create_post_invalid(client, admin_user):
    """Verify invalid POST returns 200 with form validation errors."""
    client.force_login(admin_user)
    url = reverse("quality:packaging_label_verification_create")
    # Missing discrepancy_details when disposition is relabel_required
    post_data = _finalquality_packaging_data(
        title="Invalid Verification",
        disposition="relabel_required",
        discrepancy_details="",
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "discrepancy_details" in resp.context["form"].errors


def test_finalquality_view_packaging_edit_get_and_post(client, admin_user, tenant_a, packaging_verification_a):
    """Verify packaging edit GET and valid POST."""
    client.force_login(admin_user)
    url = reverse("quality:packaging_label_verification_edit", kwargs={"pk": packaging_verification_a.pk})

    # GET
    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["verification"] == packaging_verification_a

    # POST valid update
    post_data = _finalquality_packaging_data(
        title="Updated Packaging Audit - Actuators",
        notes="Updated packaging observation notes.",
    )
    resp_post = client.post(url, post_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:packaging_label_verification_detail", kwargs={"pk": packaging_verification_a.pk})

    packaging_verification_a.refresh_from_db()
    assert packaging_verification_a.title == "Updated Packaging Audit - Actuators"
    assert packaging_verification_a.notes == "Updated packaging observation notes."

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", target__contains=packaging_verification_a.number).exists()


def test_finalquality_view_packaging_delete_methods_and_permissions(client, admin_user, member_user, tenant_a):
    """Verify packaging delete methods, permissions, and deletion execution."""
    pkg_to_delete = PackagingLabelVerification.objects.create(
        tenant=tenant_a,
        title="Packaging Audit To Delete",
        item_code="DEL-PKG-01",
    )
    url = reverse("quality:packaging_label_verification_delete", kwargs={"pk": pkg_to_delete.pk})

    # GET rejected with 405
    client.force_login(admin_user)
    assert client.get(url).status_code == 405

    # Non-admin user POST returns 403
    client.force_login(member_user)
    assert client.post(url).status_code == 403

    # Admin user POST deletes
    client.force_login(admin_user)
    resp_delete = client.post(url)
    assert resp_delete.status_code == 302
    assert resp_delete.url == reverse("quality:packaging_label_verification_list")
    assert not PackagingLabelVerification.objects.filter(pk=pkg_to_delete.pk).exists()

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", target__contains=pkg_to_delete.number).exists()


def test_finalquality_view_packaging_export_csv(client, admin_user, packaging_verification_a):
    """Verify packaging export returns CSV with attachment header, nosniff, and data rows."""
    client.force_login(admin_user)
    url = reverse("quality:packaging_label_verification_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "packaging_label_verifications.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "Verification Number" in headers
    assert "Title" in headers
    assert "Disposition" in headers
    rows = list(reader)
    assert any(packaging_verification_a.number in row[0] for row in rows)


# =============================================================================
# 4. QualityReleaseAuthorizations Views
# =============================================================================

def test_finalquality_view_release_list_get_and_context(client, admin_user, quality_release_a):
    """Verify QualityReleaseAuthorization list GET returns 200 with required context keys."""
    client.force_login(admin_user)
    url = reverse("quality:quality_release_authorization_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "releases",
        "page_obj",
        "paginator",
        "q",
        "status",
        "disposition",
        "on_hold",
        "customer_id",
        "status_choices",
        "disposition_choices",
        "customers",
        "total_count",
        "authorized_count",
        "hold_count",
        "STATUS_CSS",
        "DISPOSITION_CSS",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from quality release list context"

    assert quality_release_a in resp.context["releases"]
    assert quality_release_a.number in resp.content.decode()


def test_finalquality_view_release_list_search_and_filters(client, admin_user, quality_release_a, customer_party_a):
    """Verify release list filters by query, status, disposition, on_hold, and customer."""
    client.force_login(admin_user)
    url = reverse("quality:quality_release_authorization_list")

    # Match search
    resp = client.get(url, {"q": "Outgoing Release"})
    assert resp.status_code == 200
    assert quality_release_a in resp.context["releases"]

    # Match status
    resp = client.get(url, {"status": "authorized"})
    assert resp.status_code == 200
    assert quality_release_a in resp.context["releases"]

    # Match disposition
    resp = client.get(url, {"disposition": "released_full"})
    assert resp.status_code == 200
    assert quality_release_a in resp.context["releases"]

    # Match on_hold == "0"
    resp = client.get(url, {"on_hold": "0"})
    assert resp.status_code == 200
    assert quality_release_a in resp.context["releases"]

    # Mismatch on_hold == "1"
    resp = client.get(url, {"on_hold": "1"})
    assert resp.status_code == 200
    assert quality_release_a not in resp.context["releases"]

    # Match customer
    resp = client.get(url, {"customer": str(customer_party_a.pk)})
    assert resp.status_code == 200
    assert quality_release_a in resp.context["releases"]

    # Junk params
    resp_junk = client.get(url, {"status": "bogus", "disposition": "bogus", "on_hold": "junk", "customer": "abc", "page": "xyz"})
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_finalquality_view_release_detail_get_and_context(client, admin_user, quality_release_a):
    """Verify release detail GET returns 200 with required context keys and release details."""
    client.force_login(admin_user)
    url = reverse("quality:quality_release_authorization_detail", kwargs={"pk": quality_release_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["release"] == quality_release_a
    assert "STATUS_CSS" in resp.context
    assert "DISPOSITION_CSS" in resp.context
    assert quality_release_a.number in resp.content.decode()


def test_finalquality_view_release_create_get(client, admin_user):
    """Verify release create GET renders form with is_edit=False."""
    client.force_login(admin_user)
    url = reverse("quality:quality_release_authorization_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["release"] is None
    assert resp.context["title"] == "New Quality Release Authorization"


def test_finalquality_view_release_create_post_valid(client, admin_user, tenant_a, customer_party_a, final_lot_a, coc_a, packaging_verification_a):
    """Verify valid POST creates QualityReleaseAuthorization and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:quality_release_authorization_create")
    post_data = _finalquality_release_data(
        customer=customer_party_a,
        lot=final_lot_a,
        coc=coc_a,
        packaging=packaging_verification_a,
        officer=admin_user,
        title="Created Quality Release Package",
        quantity_authorized=150,
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_rel = QualityReleaseAuthorization.objects.get(title="Created Quality Release Package", tenant=tenant_a)
    assert resp.url == reverse("quality:quality_release_authorization_detail", kwargs={"pk": created_rel.pk})
    assert created_rel.customer == customer_party_a
    assert created_rel.inspection_lot == final_lot_a
    assert created_rel.certificate_of_conformance == coc_a
    assert created_rel.packaging_verification == packaging_verification_a

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", target__contains=created_rel.number).exists()


def test_finalquality_view_release_create_post_invalid(client, admin_user, customer_party_a):
    """Verify invalid POST returns 200 with form validation errors."""
    client.force_login(admin_user)
    url = reverse("quality:quality_release_authorization_create")
    # Hold without hold_reason, or conditional_release without concession_rationale
    post_data = _finalquality_release_data(
        customer=customer_party_a,
        title="Invalid Release",
        is_on_hold=True,
        hold_reason="",
    )
    resp = client.post(url, post_data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "hold_reason" in resp.context["form"].errors


def test_finalquality_view_release_edit_get_and_post(client, admin_user, tenant_a, quality_release_a, customer_party_a):
    """Verify release edit GET and valid POST."""
    client.force_login(admin_user)
    url = reverse("quality:quality_release_authorization_edit", kwargs={"pk": quality_release_a.pk})

    # GET
    resp_get = client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["release"] == quality_release_a

    # POST valid update
    post_data = _finalquality_release_data(
        customer=customer_party_a,
        title="Updated Outgoing Quality Release",
        notes="Updated shipping dispatch clearance notes.",
    )
    resp_post = client.post(url, post_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("quality:quality_release_authorization_detail", kwargs={"pk": quality_release_a.pk})

    quality_release_a.refresh_from_db()
    assert quality_release_a.title == "Updated Outgoing Quality Release"
    assert quality_release_a.notes == "Updated shipping dispatch clearance notes."

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", target__contains=quality_release_a.number).exists()


def test_finalquality_view_release_delete_methods_permissions_and_guard(client, admin_user, member_user, tenant_a, customer_party_a, quality_release_a):
    """Verify release deletion methods, permissions, and guard protecting authorized releases."""
    url_auth = reverse("quality:quality_release_authorization_delete", kwargs={"pk": quality_release_a.pk})

    # GET rejected with 405
    client.force_login(admin_user)
    assert client.get(url_auth).status_code == 405

    # Non-admin user POST returns 403
    client.force_login(member_user)
    assert client.post(url_auth).status_code == 403

    # Admin user attempts to delete authorized release (quality_release_a) -> guarded!
    client.force_login(admin_user)
    resp_guard = client.post(url_auth)
    assert resp_guard.status_code == 302
    assert resp_guard.url == reverse("quality:quality_release_authorization_detail", kwargs={"pk": quality_release_a.pk})
    assert QualityReleaseAuthorization.objects.filter(pk=quality_release_a.pk).exists()

    # Deleting a draft release succeeds
    draft_release = QualityReleaseAuthorization.objects.create(
        tenant=tenant_a,
        title="Draft Release To Delete",
        customer=customer_party_a,
        status="draft",
        quantity_authorized=10,
    )
    url_draft = reverse("quality:quality_release_authorization_delete", kwargs={"pk": draft_release.pk})
    resp_delete = client.post(url_draft)
    assert resp_delete.status_code == 302
    assert resp_delete.url == reverse("quality:quality_release_authorization_list")
    assert not QualityReleaseAuthorization.objects.filter(pk=draft_release.pk).exists()

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", target__contains=draft_release.number).exists()


def test_finalquality_view_release_toggle_hold_methods_permissions_and_workflow(client, admin_user, member_user, tenant_a, customer_party_a):
    """Verify release toggle_hold requires POST, tenant admin, non-empty reason, and updates status."""
    rel = QualityReleaseAuthorization.objects.create(
        tenant=tenant_a,
        title="Release for Hold Toggle",
        customer=customer_party_a,
        status="draft",
        is_on_hold=False,
        quantity_authorized=50,
    )
    url = reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": rel.pk})

    # GET rejected with 405
    client.force_login(admin_user)
    assert client.get(url).status_code == 405

    # Non-admin user POST returns 403
    client.force_login(member_user)
    assert client.post(url, {"hold_reason": "Hold"}).status_code == 403

    # Admin user attempts to engage hold without reason -> error redirect
    client.force_login(admin_user)
    resp_no_reason = client.post(url, {"hold_reason": ""})
    assert resp_no_reason.status_code == 302
    rel.refresh_from_db()
    assert rel.is_on_hold is False

    # Admin engages hold with reason
    resp_hold = client.post(url, {"hold_reason": "Carrier customs clearance documents missing"})
    assert resp_hold.status_code == 302
    rel.refresh_from_db()
    assert rel.is_on_hold is True
    assert rel.status == "active_hold"
    assert rel.hold_reason == "Carrier customs clearance documents missing"

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="hold", target__contains=rel.number).exists()

    # Admin releases from hold
    resp_release = client.post(url)
    assert resp_release.status_code == 302
    rel.refresh_from_db()
    assert rel.is_on_hold is False
    assert rel.status == "draft"

    # Audit log check
    assert AuditLog.objects.filter(tenant=tenant_a, action="release", target__contains=rel.number).exists()


def test_finalquality_view_release_export_csv(client, admin_user, quality_release_a):
    """Verify release export returns CSV with attachment header, nosniff, and data rows."""
    client.force_login(admin_user)
    url = reverse("quality:quality_release_authorization_export")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    assert "quality_releases.csv" in resp["Content-Disposition"]
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    headers = next(reader)
    assert "Release Number" in headers
    assert "Title" in headers
    assert "Status" in headers
    rows = list(reader)
    assert any(quality_release_a.number in row[0] for row in rows)


# =============================================================================
# 5. OqcHoldBoard View
# =============================================================================

def test_finalquality_view_oqc_hold_board_get_and_context(client, admin_user, final_lot_a, quality_release_a, coc_a):
    """Verify OQC Hold & Release Board GET returns 200 with all required context keys."""
    client.force_login(admin_user)
    url = reverse("quality:oqc_hold_board")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "active_holds_lots",
        "active_holds_releases",
        "pending_cocs",
        "ready_releases",
        "hold_lot_count",
        "hold_release_count",
        "pending_lot_count",
        "pending_coc_count",
        "ready_release_count",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from OQC Hold Board context"

    assert resp.context["hold_lot_count"] == len(resp.context["active_holds_lots"])
    assert resp.context["hold_release_count"] == len(resp.context["active_holds_releases"])


def test_finalquality_view_oqc_hold_board_unsliced_counts_and_large_datasets(client, admin_user, tenant_a, customer_party_a):
    """Verify dashboard metrics compute accurate totals on unsliced querysets even when >10 records exist."""
    client.force_login(admin_user)
    url = reverse("quality:oqc_hold_board")

    # Create 12 pending CoCs (status='draft')
    for i in range(12):
        CertificateOfConformance.objects.create(
            tenant=tenant_a,
            title=f"Pending CoC {i}",
            customer=customer_party_a,
            status="draft",
            certified_quantity=10,
        )

    # Create 12 ready releases
    for i in range(12):
        QualityReleaseAuthorization.objects.create(
            tenant=tenant_a,
            title=f"Ready Release {i}",
            customer=customer_party_a,
            status="authorized",
            release_disposition="released_full",
            is_on_hold=False,
            final_inspection_passed=True,
            no_open_ncrs_or_capas=True,
            packaging_label_approved=True,
            coc_issued_and_signed=True,
            quantity_authorized=25,
        )

    resp = client.get(url)
    assert resp.status_code == 200

    # Total counts are accurate on unsliced querysets
    assert resp.context["pending_coc_count"] >= 12
    assert resp.context["ready_release_count"] >= 12

    # Context items are capped to 10 for dashboard display
    assert len(resp.context["pending_cocs"]) == 10
    assert len(resp.context["ready_releases"]) == 10


# =============================================================================
# 6. Multi-Tenant Isolation & Unauthenticated Protection
# =============================================================================

def test_finalquality_view_unauthenticated_redirects_all_endpoints(client, final_lot_a, coc_a, packaging_verification_a, quality_release_a):
    """Verify unauthenticated requests across all 28 views redirect to login."""
    endpoints = [
        ("get", reverse("quality:final_inspection_lot_list")),
        ("get", reverse("quality:final_inspection_lot_create")),
        ("get", reverse("quality:final_inspection_lot_detail", kwargs={"pk": final_lot_a.pk})),
        ("get", reverse("quality:final_inspection_lot_edit", kwargs={"pk": final_lot_a.pk})),
        ("post", reverse("quality:final_inspection_lot_delete", kwargs={"pk": final_lot_a.pk})),
        ("post", reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": final_lot_a.pk})),
        ("get", reverse("quality:final_inspection_lot_export")),
        ("get", reverse("quality:certificate_of_conformance_list")),
        ("get", reverse("quality:certificate_of_conformance_create")),
        ("get", reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_a.pk})),
        ("get", reverse("quality:certificate_of_conformance_edit", kwargs={"pk": coc_a.pk})),
        ("post", reverse("quality:certificate_of_conformance_delete", kwargs={"pk": coc_a.pk})),
        ("post", reverse("quality:certificate_of_conformance_sign", kwargs={"pk": coc_a.pk})),
        ("get", reverse("quality:certificate_of_conformance_export")),
        ("get", reverse("quality:packaging_label_verification_list")),
        ("get", reverse("quality:packaging_label_verification_create")),
        ("get", reverse("quality:packaging_label_verification_detail", kwargs={"pk": packaging_verification_a.pk})),
        ("get", reverse("quality:packaging_label_verification_edit", kwargs={"pk": packaging_verification_a.pk})),
        ("post", reverse("quality:packaging_label_verification_delete", kwargs={"pk": packaging_verification_a.pk})),
        ("get", reverse("quality:packaging_label_verification_export")),
        ("get", reverse("quality:quality_release_authorization_list")),
        ("get", reverse("quality:quality_release_authorization_create")),
        ("get", reverse("quality:quality_release_authorization_detail", kwargs={"pk": quality_release_a.pk})),
        ("get", reverse("quality:quality_release_authorization_edit", kwargs={"pk": quality_release_a.pk})),
        ("post", reverse("quality:quality_release_authorization_delete", kwargs={"pk": quality_release_a.pk})),
        ("post", reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": quality_release_a.pk})),
        ("get", reverse("quality:quality_release_authorization_export")),
        ("get", reverse("quality:oqc_hold_board")),
    ]

    for method, url in endpoints:
        resp = getattr(client, method)(url)
        assert resp.status_code == 302, f"Endpoint {url} did not redirect unauthenticated user"
        assert "/login/" in resp.url


def test_finalquality_view_cross_tenant_isolation(
    client,
    admin_user,
    final_lot_b,
    coc_b,
    packaging_verification_b,
    quality_release_b,
):
    """Verify tenant A admin is strictly forbidden / 404 from accessing tenant B resources."""
    client.force_login(admin_user)

    # Detail access -> 404
    assert client.get(reverse("quality:final_inspection_lot_detail", kwargs={"pk": final_lot_b.pk})).status_code == 404
    assert client.get(reverse("quality:certificate_of_conformance_detail", kwargs={"pk": coc_b.pk})).status_code == 404
    assert client.get(reverse("quality:packaging_label_verification_detail", kwargs={"pk": packaging_verification_b.pk})).status_code == 404
    assert client.get(reverse("quality:quality_release_authorization_detail", kwargs={"pk": quality_release_b.pk})).status_code == 404

    # Edit access -> 404
    assert client.get(reverse("quality:final_inspection_lot_edit", kwargs={"pk": final_lot_b.pk})).status_code == 404
    assert client.get(reverse("quality:certificate_of_conformance_edit", kwargs={"pk": coc_b.pk})).status_code == 404
    assert client.get(reverse("quality:packaging_label_verification_edit", kwargs={"pk": packaging_verification_b.pk})).status_code == 404
    assert client.get(reverse("quality:quality_release_authorization_edit", kwargs={"pk": quality_release_b.pk})).status_code == 404

    # Action endpoints -> 404
    assert client.post(reverse("quality:final_inspection_lot_delete", kwargs={"pk": final_lot_b.pk})).status_code == 404
    assert client.post(reverse("quality:final_inspection_lot_toggle_hold", kwargs={"pk": final_lot_b.pk})).status_code == 404
    assert client.post(reverse("quality:certificate_of_conformance_delete", kwargs={"pk": coc_b.pk})).status_code == 404
    assert client.post(reverse("quality:certificate_of_conformance_sign", kwargs={"pk": coc_b.pk})).status_code == 404
    assert client.post(reverse("quality:packaging_label_verification_delete", kwargs={"pk": packaging_verification_b.pk})).status_code == 404
    assert client.post(reverse("quality:quality_release_authorization_delete", kwargs={"pk": quality_release_b.pk})).status_code == 404
    assert client.post(reverse("quality:quality_release_authorization_toggle_hold", kwargs={"pk": quality_release_b.pk})).status_code == 404

    # List views must not leak tenant B records
    resp_lot_list = client.get(reverse("quality:final_inspection_lot_list"))
    assert final_lot_b not in resp_lot_list.context["inspection_lots"]

    resp_coc_list = client.get(reverse("quality:certificate_of_conformance_list"))
    assert coc_b not in resp_coc_list.context["certificates"]

    resp_pkg_list = client.get(reverse("quality:packaging_label_verification_list"))
    assert packaging_verification_b not in resp_pkg_list.context["verifications"]

    resp_rel_list = client.get(reverse("quality:quality_release_authorization_list"))
    assert quality_release_b not in resp_rel_list.context["releases"]
