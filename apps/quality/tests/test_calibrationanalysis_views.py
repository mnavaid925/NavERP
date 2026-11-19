"""View unit tests for Sub-module 12.10: Calibration & Measurement System Analysis (MSA).

Covers all 25 views across the 5 entities/endpoints:
1. CalibrationGage (list, create, detail, edit, delete, export_csv)
2. CalibrationRecord (list, create, detail, edit, delete, export_csv)
3. OutOfToleranceInvestigation (list, create, detail, edit, delete, export_csv)
4. MeasurementSystemAnalysis (list, create, detail, edit, delete, export_csv)
5. CalibrationVendors directory (calibration_vendor_directory)
6. Cross-tenant isolation & IDOR prevention across all 5 models/views.

Conventions:
- All test functions prefixed: test_calibrationanalysis_views_*
- All module helpers prefixed: _calibrationanalysis_*
- Uses client logged in as admin_user with tenant=tenant_a.
"""
import csv
import io
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, OrgUnit, Party, PartyRole
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.CalibrationAnalysis.CalibrationRecords import CalibrationRecord
from apps.quality.models.CalibrationAnalysis.MeasurementSystemAnalyses import MeasurementSystemAnalysis
from apps.quality.models.CalibrationAnalysis.OutOfToleranceInvestigations import OutOfToleranceInvestigation

User = get_user_model()
pytestmark = pytest.mark.django_db


# =============================================================================
# Helper Utilities (Prefix: _calibrationanalysis_*)
# =============================================================================

def _calibrationanalysis_pk(val):
    """Return pk if val is a model instance, or val itself if scalar / None."""
    if hasattr(val, "pk"):
        return val.pk
    return val


def _calibrationanalysis_date(days_offset=0):
    """Return an ISO formatted date string relative to today."""
    return (timezone.now().date() + timedelta(days=days_offset)).isoformat()


def _calibrationanalysis_gage_data(**extra):
    """Build valid baseline POST dictionary for CalibrationGageForm."""
    uid = uuid.uuid4().hex[:6]
    data = {
        "gage_id": f"GAG-VW-{uid}",
        "name": f"Precision Bore Micrometer {uid}",
        "gage_type": "caliper_micrometer",
        "criticality": "critical",
        "status": "active_in_service",
        "manufacturer": "Starrett",
        "model_number": "STR-441",
        "serial_number": f"SN-BOR-{uid}",
        "measurement_range": "25 - 50 mm",
        "resolution": "0.001 mm",
        "accuracy_spec": "+/- 0.002 mm",
        "max_permissible_error": "0.0020",
        "engineering_unit": "mm",
        "is_reference_standard": False,
        "nist_traceability_number": f"NIST-VIEW-{uid}",
        "reference_standard_parent": "",
        "asset_link": "",
        "work_center": "",
        "department": "",
        "custodian": "",
        "storage_location": "Metrology Lab Shelf 4",
        "calibration_interval_days": 180,
        "last_calibration_date": _calibrationanalysis_date(-20),
        "next_calibration_due": _calibrationanalysis_date(160),
        "sop_document": "",
        "notes": "Precision bore gage used in CNC turning.",
    }
    data.update(extra)
    return data


def _calibrationanalysis_record_data(gage, **extra):
    """Build valid baseline POST dictionary for CalibrationRecordForm."""
    uid = uuid.uuid4().hex[:6]
    data = {
        "gage": _calibrationanalysis_pk(gage),
        "calibration_date": _calibrationanalysis_date(0),
        "calibration_type": "internal_metrology",
        "status": "completed",
        "service_vendor": "",
        "certificate_number": f"CERT-VW-{uid}",
        "as_found_condition": "in_tolerance",
        "as_left_condition": "in_tolerance",
        "overall_result": "pass",
        "ambient_temperature_c": "20.10",
        "ambient_relative_humidity": "45.00",
        "expanded_uncertainty": "0.0015",
        "test_uncertainty_ratio": "4.50",
        "max_observed_error": "0.0008",
        "guardband_applied": True,
        "standards_used": [],
        "standard_traceability_notes": "Traceable to NIST standards.",
        "technician_name": "Senior Metrologist",
        "calibrated_by_user": "",
        "approved_by": "",
        "notes": "Routine scheduled calibration.",
    }
    data.update(extra)
    return data


def _calibrationanalysis_oot_data(record, gage, **extra):
    """Build valid baseline POST dictionary for OutOfToleranceInvestigationForm."""
    uid = uuid.uuid4().hex[:6]
    data = {
        "calibration_record": _calibrationanalysis_pk(record),
        "gage": _calibrationanalysis_pk(gage),
        "discovery_date": _calibrationanalysis_date(0),
        "status": "open",
        "risk_level": "major",
        "title": f"OOT Investigation on Gage {uid}",
        "as_found_error_description": "Exceeded maximum permissible error by 0.015mm.",
        "suspect_window_start": _calibrationanalysis_date(-60),
        "suspect_window_end": _calibrationanalysis_date(0),
        "suspect_work_center": "",
        "suspect_production_orders": "PO-1001, PO-1002",
        "suspect_lots_count": 5,
        "products_affected": "High Precision Valve Spool",
        "consumer_risk_rating": 3,
        "producer_risk_rating": 3,
        "containment_actions_taken": "Instrument pulled from shop floor.",
        "product_disposition": "quarantine_scrap",
        "customer_notification_required": False,
        "product_recall_required": False,
        "linked_ncr": "",
        "linked_capa": "",
        "investigator": "",
        "quality_approver": "",
        "closure_date": "",
        "conclusion_summary": "Root cause anvil wear.",
    }
    data.update(extra)
    return data


def _calibrationanalysis_msa_data(gage, **extra):
    """Build valid baseline POST dictionary for MeasurementSystemAnalysisForm."""
    uid = uuid.uuid4().hex[:6]
    data = {
        "study_title": f"Bore Micrometer MSA Study {uid}",
        "gage": _calibrationanalysis_pk(gage),
        "study_type": "gage_rr_crossed",
        "analysis_method": "anova",
        "status": "draft",
        "characteristic_name": "Inner Valve Bore Diameter",
        "study_date": _calibrationanalysis_date(0),
        "number_of_operators": 3,
        "number_of_parts": 10,
        "number_of_trials": 3,
        "specification_tolerance": "0.0500",
        "reference_master_value": "25.0000",
        "repeatability_ev": "0.0012",
        "reproducibility_av": "0.0009",
        "gage_rr_grr": "0.0015",
        "part_variation_pv": "0.0120",
        "total_variation_tv": "0.0121",
        "percent_gage_rr_study_variation": "12.40",
        "percent_tolerance_pt_ratio": "18.00",
        "number_of_distinct_categories_ndc": "11.00",
        "bias_value": "0.0001",
        "bias_percentage": "0.10",
        "linearity_slope": "0.0005",
        "linearity_r_squared": "0.9900",
        "study_result": "acceptable",
        "study_protocol_doc": "",
        "study_lead": "",
        "approved_by": "",
        "conclusion": "Measurement system deemed acceptable.",
        "notes": "ANOVA crossed GRR study.",
    }
    data.update(extra)
    return data


# =============================================================================
# 1. CalibrationGage Views
# =============================================================================

def test_calibrationanalysis_views_gage_list_get_and_context(client, admin_user, cal_gage_a):
    """Verify CalibrationGage list GET returns 200 with all pinned context keys."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "gages",
        "gage_list",
        "page_obj",
        "search_query",
        "status_filter",
        "type_filter",
        "criticality_filter",
        "status_choices",
        "type_choices",
        "criticality_choices",
        "total_gages",
        "past_due_count",
        "in_service_count",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from calibration gage list context"

    assert cal_gage_a in resp.context["gages"]
    assert cal_gage_a in resp.context["gage_list"]
    assert cal_gage_a.gage_id in resp.content.decode()


def test_calibrationanalysis_views_gage_list_search_and_filters(client, admin_user, cal_gage_a):
    """Verify gage list filter fuzzing for query, status, gage_type, and criticality."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_list")

    # Match by gage_id
    resp = client.get(url, {"q": cal_gage_a.gage_id})
    assert resp.status_code == 200
    assert cal_gage_a in resp.context["gages"]

    # Match by name
    resp = client.get(url, {"q": "Outside Micrometer"})
    assert resp.status_code == 200
    assert cal_gage_a in resp.context["gages"]

    # Match by manufacturer
    resp = client.get(url, {"q": "Mitutoyo"})
    assert resp.status_code == 200
    assert cal_gage_a in resp.context["gages"]

    # Match by status
    resp = client.get(url, {"status": "active_in_service"})
    assert resp.status_code == 200
    assert cal_gage_a in resp.context["gages"]

    # Match by gage_type
    resp = client.get(url, {"gage_type": "caliper_micrometer"})
    assert resp.status_code == 200
    assert cal_gage_a in resp.context["gages"]

    # Match by criticality
    resp = client.get(url, {"criticality": "critical"})
    assert resp.status_code == 200
    assert cal_gage_a in resp.context["gages"]

    # Negative search
    resp_nomatch = client.get(url, {"q": "NON_EXISTENT_TAG_99999"})
    assert resp_nomatch.status_code == 200
    assert cal_gage_a not in resp_nomatch.context["gages"]


def test_calibrationanalysis_views_gage_list_pagination_and_junk_params(client, admin_user, tenant_a):
    """Verify gage list handles pagination beyond PAGE_SIZE (15) and invalid junk params."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_list")

    # Bulk create gages to exceed page size
    for idx in range(18):
        CalibrationGage.objects.create(
            tenant=tenant_a,
            gage_id=f"GAG-BULK-{idx:03d}",
            name=f"Bulk Test Gage {idx}",
            gage_type="pressure_temperature",
            criticality="minor",
            status="active_in_service",
            measurement_range="0-100 bar",
            max_permissible_error=Decimal("0.5"),
            engineering_unit="bar",
            calibration_interval_days=90,
        )

    # Page 1
    resp_p1 = client.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert resp_p1.context["page_obj"].number == 1
    assert resp_p1.context["page_obj"].has_next()

    # Page 2
    resp_p2 = client.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2

    # Junk params
    resp_junk = client.get(url, {
        "page": "invalid_page_abc",
        "status": "not_a_valid_status_xxx",
        "gage_type": "corrupted_type",
        "criticality": "unknown_crit",
    })
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_calibrationanalysis_views_gage_list_unauthenticated_redirect(client):
    """Verify unauthenticated access redirects to login."""
    url = reverse("quality:calibration_gage_list")
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url or "login" in resp.url


def test_calibrationanalysis_views_gage_create_get(client, admin_user):
    """Verify gage create GET returns 200 with form and is_edit=False."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_create")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["gage"] is None
    assert resp.context["obj"] is None


def test_calibrationanalysis_views_gage_create_post_valid(client, admin_user, tenant_a):
    """Verify valid gage creation redirects to detail and logs an AuditLog entry."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_create")
    post_data = _calibrationanalysis_gage_data(gage_id="GAG-NEW-0099")

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_gage = CalibrationGage.objects.get(tenant=tenant_a, gage_id="GAG-NEW-0099")
    assert resp.url == reverse("quality:calibration_gage_detail", kwargs={"pk": created_gage.pk})

    # Verify AuditLog created
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created_gage.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user


def test_calibrationanalysis_views_gage_create_post_invalid(client, admin_user, tenant_a):
    """Verify invalid gage submission re-renders 200 with validation errors."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_create")
    post_data = _calibrationanalysis_gage_data(gage_id="")  # Missing required gage_id

    resp = client.post(url, post_data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_calibrationanalysis_views_gage_detail_get_and_context(client, admin_user, cal_gage_a, cal_record_a, cal_oot_a, cal_msa_a):
    """Verify gage detail GET returns 200, dual context keys, and related histories."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_detail", kwargs={"pk": cal_gage_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["gage"] == cal_gage_a
    assert resp.context["obj"] == cal_gage_a

    # Related records dual-bindings
    calibrations = list(resp.context["calibrations"])
    assert cal_record_a in calibrations
    assert cal_record_a in list(resp.context["calibration_history"])

    oot_investigations = list(resp.context["oot_investigations"])
    assert cal_oot_a in oot_investigations
    assert cal_oot_a in list(resp.context["oot_history"])

    msa_studies = list(resp.context["msa_studies"])
    assert cal_msa_a in msa_studies

    assert cal_gage_a.gage_id in resp.content.decode()


def test_calibrationanalysis_views_gage_edit_get(client, admin_user, cal_gage_a):
    """Verify gage edit GET returns 200 with bound form and is_edit=True."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_edit", kwargs={"pk": cal_gage_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["gage"] == cal_gage_a
    assert resp.context["obj"] == cal_gage_a


def test_calibrationanalysis_views_gage_edit_post_valid(client, admin_user, cal_gage_a):
    """Verify valid gage update redirects to detail, updates DB, and logs AuditLog."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_edit", kwargs={"pk": cal_gage_a.pk})
    post_data = _calibrationanalysis_gage_data(
        gage_id=cal_gage_a.gage_id,
        name="Updated Digital Caliper Model 2026",
        notes="Recalibration frequency verified and confirmed.",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:calibration_gage_detail", kwargs={"pk": cal_gage_a.pk})

    cal_gage_a.refresh_from_db()
    assert cal_gage_a.name == "Updated Digital Caliper Model 2026"
    assert cal_gage_a.notes == "Recalibration frequency verified and confirmed."

    audit = AuditLog.objects.filter(
        tenant=cal_gage_a.tenant,
        action="update",
        object_id=str(cal_gage_a.pk),
    ).first()
    assert audit is not None


def test_calibrationanalysis_views_gage_edit_post_invalid(client, admin_user, cal_gage_a):
    """Verify invalid gage update re-renders 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_edit", kwargs={"pk": cal_gage_a.pk})
    post_data = _calibrationanalysis_gage_data(name="")  # Missing required name

    resp = client.post(url, post_data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_calibrationanalysis_views_gage_delete_method_not_allowed(client, admin_user, cal_gage_a):
    """Verify GET on delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_gage_delete", kwargs={"pk": cal_gage_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_calibrationanalysis_views_gage_delete_post_success(client, admin_user, tenant_a):
    """Verify admin POST deletion deletes record, writes AuditLog, and redirects to list."""
    client.force_login(admin_user)
    disposable_gage = CalibrationGage.objects.create(
        tenant=tenant_a,
        gage_id="GAG-TO-DELETE-01",
        name="Disposable Micrometer",
        gage_type="caliper_micrometer",
        criticality="minor",
        status="out_of_service",
        measurement_range="0-25mm",
        max_permissible_error=Decimal("0.01"),
        engineering_unit="mm",
    )
    url = reverse("quality:calibration_gage_delete", kwargs={"pk": disposable_gage.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:calibration_gage_list")

    assert not CalibrationGage.objects.filter(pk=disposable_gage.pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(disposable_gage.pk),
    ).first()
    assert audit is not None


def test_calibrationanalysis_views_gage_delete_non_admin_forbidden(member_client, cal_gage_a):
    """Verify non-admin user cannot delete gage (403 forbidden or redirect)."""
    url = reverse("quality:calibration_gage_delete", kwargs={"pk": cal_gage_a.pk})
    resp = member_client.post(url)
    assert resp.status_code in (403, 302)
    assert CalibrationGage.objects.filter(pk=cal_gage_a.pk).exists()


def test_calibrationanalysis_views_gage_export_csv(client, admin_user, tenant_a, cal_gage_a):
    """Verify gage export CSV returns 200, text/csv, correct headers, and formula sanitization."""
    client.force_login(admin_user)

    # Create gage with dangerous CSV formula characters
    CalibrationGage.objects.create(
        tenant=tenant_a,
        gage_id="=CMD('calc')",
        name="@DangerousFormulaGage",
        gage_type="caliper_micrometer",
        criticality="critical",
        status="active_in_service",
        serial_number="+44102948",
        measurement_range="0-25mm",
        max_permissible_error=Decimal("0.001"),
        engineering_unit="mm",
        storage_location="-RiskShelf",
    )

    url = reverse("quality:calibration_gage_export_csv")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert 'filename="calibration_gages.csv"' in resp["Content-Disposition"]
    assert resp.get("X-Content-Type-Options") == "nosniff"

    content = resp.content.decode("utf-8")
    csv_reader = csv.reader(io.StringIO(content))
    rows = list(csv_reader)

    # Check headers
    expected_headers = [
        "Gage ID", "Name", "Type", "Criticality", "Status",
        "Serial Number", "Range", "MPE", "Unit", "Next Due", "Location"
    ]
    assert rows[0] == expected_headers

    # Check formula sanitization prepends single quote
    formula_row = next(r for r in rows if "@DangerousFormulaGage" in r[1])
    assert formula_row[0].startswith("'=")
    assert formula_row[1].startswith("'@")
    assert formula_row[5].startswith("'+")
    assert formula_row[10].startswith("'-")


# =============================================================================
# 2. CalibrationRecord Views
# =============================================================================

def test_calibrationanalysis_views_record_list_get_and_context(client, admin_user, cal_record_a):
    """Verify CalibrationRecord list GET returns 200 with all pinned context keys."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "calibration_records",
        "page_obj",
        "search_query",
        "result_filter",
        "type_filter",
        "status_filter",
        "result_choices",
        "type_choices",
        "status_choices",
        "total_calibrations",
        "oot_count",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from calibration record list context"

    assert cal_record_a in resp.context["calibration_records"]
    assert cal_record_a.certificate_number in resp.content.decode()


def test_calibrationanalysis_views_record_list_search_by_vendor_and_filters(client, admin_user, cal_record_a, cal_vendor_a):
    """Verify calibration record search by vendor name, certificate, and filters."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_list")

    # Search by service vendor name
    resp_vendor = client.get(url, {"q": cal_vendor_a.name[:10]})
    assert resp_vendor.status_code == 200
    assert cal_record_a in resp_vendor.context["calibration_records"]

    # Search by certificate number
    resp_cert = client.get(url, {"q": cal_record_a.certificate_number})
    assert resp_cert.status_code == 200
    assert cal_record_a in resp_cert.context["calibration_records"]

    # Filter by overall_result
    resp_result = client.get(url, {"overall_result": "pass"})
    assert resp_result.status_code == 200
    assert cal_record_a in resp_result.context["calibration_records"]

    # Filter by calibration_type
    resp_type = client.get(url, {"calibration_type": "external_accredited"})
    assert resp_type.status_code == 200
    assert cal_record_a in resp_type.context["calibration_records"]

    # Filter by status
    resp_status = client.get(url, {"status": "completed"})
    assert resp_status.status_code == 200
    assert cal_record_a in resp_status.context["calibration_records"]

    # Negative search
    resp_none = client.get(url, {"q": "NON_EXISTENT_VENDOR_XYZ"})
    assert resp_none.status_code == 200
    assert cal_record_a not in resp_none.context["calibration_records"]


def test_calibrationanalysis_views_record_list_pagination_and_junk_params(client, admin_user, tenant_a, cal_gage_a):
    """Verify calibration record list handles pagination and junk filter fuzzing."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_list")

    for idx in range(18):
        CalibrationRecord.objects.create(
            tenant=tenant_a,
            gage=cal_gage_a,
            calibration_date=timezone.now().date(),
            calibration_type="internal_metrology",
            status="completed",
            certificate_number=f"BULK-REC-{idx:03d}",
            overall_result="pass",
        )

    resp_p2 = client.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2

    resp_junk = client.get(url, {
        "page": "invalid_page_99",
        "overall_result": "bogus_result",
        "calibration_type": "bogus_type",
        "status": "bogus_status",
    })
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_calibrationanalysis_views_record_list_unauthenticated_redirect(client):
    """Verify unauthenticated access to record list redirects to login."""
    url = reverse("quality:calibration_record_list")
    resp = client.get(url)
    assert resp.status_code == 302


def test_calibrationanalysis_views_record_create_get_with_gage_prefill(client, admin_user, cal_gage_a):
    """Verify GET record create pre-populates gage field when ?gage= is provided."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_create")
    resp = client.get(url, {"gage": str(cal_gage_a.pk)})
    assert resp.status_code == 200
    assert resp.context["form"].initial.get("gage") == str(cal_gage_a.pk)
    assert resp.context["is_edit"] is False


def test_calibrationanalysis_views_record_create_post_valid_and_sync_pass(client, admin_user, tenant_a, cal_gage_a):
    """Verify valid record creation with pass result synchronizes gage status and next due date."""
    client.force_login(admin_user)
    cal_gage_a.status = "quarantined_oot"
    cal_gage_a.calibration_interval_days = 100
    cal_gage_a.save()

    url = reverse("quality:calibration_record_create")
    post_data = _calibrationanalysis_record_data(
        gage=cal_gage_a,
        status="completed",
        overall_result="pass",
        calibration_date=_calibrationanalysis_date(0),
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_rec = CalibrationRecord.objects.get(tenant=tenant_a, certificate_number=post_data["certificate_number"])
    assert resp.url == reverse("quality:calibration_record_detail", kwargs={"pk": created_rec.pk})

    # Verify Gage synchronization
    cal_gage_a.refresh_from_db()
    assert cal_gage_a.status == "active_in_service"
    assert cal_gage_a.last_calibration_date == timezone.now().date()
    assert cal_gage_a.next_calibration_due == timezone.now().date() + timedelta(days=100)

    # Verify AuditLog
    audit = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created_rec.pk)).first()
    assert audit is not None


def test_calibrationanalysis_views_record_create_post_valid_and_sync_oot(client, admin_user, tenant_a, cal_gage_a):
    """Verify record with fail_out_of_tolerance synchronizes gage status to quarantined_oot."""
    client.force_login(admin_user)
    cal_gage_a.status = "active_in_service"
    cal_gage_a.save()

    url = reverse("quality:calibration_record_create")
    post_data = _calibrationanalysis_record_data(
        gage=cal_gage_a,
        status="completed",
        overall_result="fail_out_of_tolerance",
        as_found_condition="out_of_tolerance",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    cal_gage_a.refresh_from_db()
    assert cal_gage_a.status == "quarantined_oot"


def test_calibrationanalysis_views_record_create_post_valid_and_sync_unrepairable(client, admin_user, tenant_a, cal_gage_a):
    """Verify record with fail_unrepairable synchronizes gage status to out_of_service."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_create")
    post_data = _calibrationanalysis_record_data(
        gage=cal_gage_a,
        status="completed",
        overall_result="fail_unrepairable",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    cal_gage_a.refresh_from_db()
    assert cal_gage_a.status == "out_of_service"


def test_calibrationanalysis_views_record_create_post_invalid(client, admin_user):
    """Verify invalid record creation re-renders 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_create")
    resp = client.post(url, {})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_calibrationanalysis_views_record_detail_get_and_context(client, admin_user, cal_record_a, cal_standard_a):
    """Verify record detail GET returns 200 with dual context keys and prefetched standards."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_detail", kwargs={"pk": cal_record_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["record"] == cal_record_a
    assert resp.context["calibration_record"] == cal_record_a
    assert resp.context["obj"] == cal_record_a

    # Standards list verification
    standards = list(resp.context["standards_list"])
    assert cal_standard_a in standards
    assert cal_standard_a in list(resp.context["standards_used"])


def test_calibrationanalysis_views_record_detail_with_oot_investigation(client, admin_user, cal_record_oot_a, cal_oot_a):
    """Verify record detail context provides linked oot_investigation when present."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_detail", kwargs={"pk": cal_record_oot_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["oot_investigation"] == cal_oot_a


def test_calibrationanalysis_views_record_edit_get(client, admin_user, cal_record_a):
    """Verify record edit GET returns 200, bound form, and is_edit=True."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_edit", kwargs={"pk": cal_record_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["record"] == cal_record_a
    assert resp.context["obj"] == cal_record_a


def test_calibrationanalysis_views_record_edit_post_valid(client, admin_user, cal_record_a):
    """Verify valid record edit redirects to detail, updates DB, and writes AuditLog."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_edit", kwargs={"pk": cal_record_a.pk})
    post_data = _calibrationanalysis_record_data(
        gage=cal_record_a.gage,
        certificate_number=cal_record_a.certificate_number,
        technician_name="Updated Metrologist Tech",
        notes="Updated post-calibration verification notes.",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:calibration_record_detail", kwargs={"pk": cal_record_a.pk})

    cal_record_a.refresh_from_db()
    assert cal_record_a.technician_name == "Updated Metrologist Tech"
    assert cal_record_a.notes == "Updated post-calibration verification notes."

    audit = AuditLog.objects.filter(tenant=cal_record_a.tenant, action="update", object_id=str(cal_record_a.pk)).first()
    assert audit is not None


def test_calibrationanalysis_views_record_edit_post_invalid(client, admin_user, cal_record_a):
    """Verify invalid record edit re-renders 200 with errors."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_edit", kwargs={"pk": cal_record_a.pk})
    resp = client.post(url, {"certificate_number": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_calibrationanalysis_views_record_delete_method_not_allowed(client, admin_user, cal_record_a):
    """Verify GET on record delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_record_delete", kwargs={"pk": cal_record_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_calibrationanalysis_views_record_delete_post_success(client, admin_user, tenant_a, cal_gage_a):
    """Verify admin POST deletion deletes record, writes AuditLog, and redirects to list."""
    client.force_login(admin_user)
    disposable_rec = CalibrationRecord.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        calibration_date=timezone.now().date(),
        calibration_type="internal_metrology",
        status="draft",
        certificate_number="CERT-DISPOSE-99",
        overall_result="pass",
    )
    url = reverse("quality:calibration_record_delete", kwargs={"pk": disposable_rec.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:calibration_record_list")

    assert not CalibrationRecord.objects.filter(pk=disposable_rec.pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(disposable_rec.pk)).first()
    assert audit is not None


def test_calibrationanalysis_views_record_delete_non_admin_forbidden(member_client, cal_record_a):
    """Verify non-admin user cannot delete calibration record."""
    url = reverse("quality:calibration_record_delete", kwargs={"pk": cal_record_a.pk})
    resp = member_client.post(url)
    assert resp.status_code in (403, 302)
    assert CalibrationRecord.objects.filter(pk=cal_record_a.pk).exists()


def test_calibrationanalysis_views_record_export_csv(client, admin_user, tenant_a, cal_gage_a, cal_record_a):
    """Verify calibration record CSV export format, headers, and formula sanitization."""
    client.force_login(admin_user)

    # Record with dangerous CSV formula prefix
    CalibrationRecord.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        calibration_date=timezone.now().date(),
        calibration_type="internal_metrology",
        status="completed",
        certificate_number="=SUM(A1:A5)",
        overall_result="pass",
        expanded_uncertainty=Decimal("0.001"),
        test_uncertainty_ratio=Decimal("4.0"),
    )

    url = reverse("quality:calibration_record_export_csv")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert 'filename="calibration_records.csv"' in resp["Content-Disposition"]

    content = resp.content.decode("utf-8")
    rows = list(csv.reader(io.StringIO(content)))

    expected_headers = [
        "Record Number", "Gage Tag", "Gage Name", "Date", "Type",
        "As-Found", "As-Left", "Result", "Uncertainty U", "TUR", "Certificate #"
    ]
    assert rows[0] == expected_headers

    # Formula sanitization verification
    formula_row = next(r for r in rows if "=SUM" in r[10])
    assert formula_row[10].startswith("'=")


# =============================================================================
# 3. OutOfToleranceInvestigation Views
# =============================================================================

def test_calibrationanalysis_views_oot_list_get_and_context(client, admin_user, cal_oot_a):
    """Verify OOT investigation list GET returns 200 with all pinned context keys."""
    client.force_login(admin_user)
    url = reverse("quality:out_of_tolerance_investigation_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "oot_investigations",
        "page_obj",
        "search_query",
        "status_filter",
        "risk_filter",
        "disposition_filter",
        "status_choices",
        "risk_choices",
        "disposition_choices",
        "total_oots",
        "critical_count",
        "open_count",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from OOT list context"

    assert cal_oot_a in resp.context["oot_investigations"]
    assert cal_oot_a.number in resp.content.decode()


def test_calibrationanalysis_views_oot_list_filters_and_search(client, admin_user, cal_oot_a):
    """Verify OOT list search and filters for status, risk_level, and disposition."""
    client.force_login(admin_user)
    url = reverse("quality:out_of_tolerance_investigation_list")

    # Search by title
    resp_title = client.get(url, {"q": "Torque & Measurement"})
    assert resp_title.status_code == 200
    assert cal_oot_a in resp_title.context["oot_investigations"]

    # Filter by status
    resp_status = client.get(url, {"status": "investigating"})
    assert resp_status.status_code == 200
    assert cal_oot_a in resp_status.context["oot_investigations"]

    # Filter by risk_level
    resp_risk = client.get(url, {"risk_level": "critical"})
    assert resp_risk.status_code == 200
    assert cal_oot_a in resp_risk.context["oot_investigations"]

    # Filter by disposition
    cal_oot_a.product_disposition = "quarantine_scrap"
    cal_oot_a.save()
    resp_disp = client.get(url, {"disposition": "quarantine_scrap"})
    assert resp_disp.status_code == 200
    assert cal_oot_a in resp_disp.context["oot_investigations"]

    # Negative search
    resp_none = client.get(url, {"q": "NON_EXISTENT_OOT_XYZ"})
    assert resp_none.status_code == 200
    assert cal_oot_a not in resp_none.context["oot_investigations"]


def test_calibrationanalysis_views_oot_list_pagination_and_junk_params(client, admin_user, tenant_a, cal_gage_a, cal_record_oot_a):
    """Verify OOT list handles pagination beyond 15 items and invalid params."""
    client.force_login(admin_user)
    url = reverse("quality:out_of_tolerance_investigation_list")

    for idx in range(18):
        OutOfToleranceInvestigation.objects.create(
            tenant=tenant_a,
            gage=cal_gage_a,
            calibration_record=cal_record_oot_a,
            title=f"Bulk OOT Investigation {idx:02d}",
            as_found_error_description="Jaw parallelism error",
            suspect_window_start=timezone.now().date() - timedelta(days=30),
            status="open",
            risk_level="major",
        )

    resp_p2 = client.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2

    resp_junk = client.get(url, {
        "page": "junk_page",
        "status": "bogus_status",
        "risk_level": "bogus_risk",
    })
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_calibrationanalysis_views_oot_list_unauthenticated_redirect(client):
    """Verify unauthenticated access to OOT list redirects to login."""
    url = reverse("quality:out_of_tolerance_investigation_list")
    resp = client.get(url)
    assert resp.status_code == 302


def test_calibrationanalysis_views_oot_create_get_with_cal_record_prefill_and_suspect_window(client, admin_user, tenant_a, cal_gage_a, cal_record_oot_a):
    """Verify OOT create GET with ?calibration_record= pre-populates gage, suspect window, and error description."""
    client.force_login(admin_user)

    # Establish an earlier passing calibration record for suspect window calculation
    CalibrationRecord.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        calibration_date=cal_record_oot_a.calibration_date - timedelta(days=90),
        status="completed",
        overall_result="pass",
        certificate_number="CERT-EARLIER-PASS",
    )

    url = reverse("quality:out_of_tolerance_investigation_create")
    resp = client.get(url, {"calibration_record": str(cal_record_oot_a.pk)})
    assert resp.status_code == 200

    form_initial = resp.context["form"].initial
    assert form_initial.get("calibration_record") == str(cal_record_oot_a.pk)
    assert form_initial.get("gage") == cal_gage_a.pk
    assert form_initial.get("suspect_window_start") == cal_record_oot_a.calibration_date - timedelta(days=90)
    assert "As-Found Condition:" in form_initial.get("as_found_error_description", "")


def test_calibrationanalysis_views_oot_create_get_with_gage_prefill(client, admin_user, cal_gage_a):
    """Verify OOT create GET with ?gage= pre-populates gage."""
    client.force_login(admin_user)
    url = reverse("quality:out_of_tolerance_investigation_create")
    resp = client.get(url, {"gage": str(cal_gage_a.pk)})
    assert resp.status_code == 200
    assert resp.context["form"].initial.get("gage") == str(cal_gage_a.pk)


def test_calibrationanalysis_views_oot_create_post_valid_and_gage_quarantined(client, admin_user, tenant_a, cal_gage_a, cal_record_oot_a):
    """Verify valid OOT creation redirects to detail, writes AuditLog, and quarantines the gage."""
    client.force_login(admin_user)
    cal_gage_a.status = "active_in_service"
    cal_gage_a.save()

    url = reverse("quality:out_of_tolerance_investigation_create")
    post_data = _calibrationanalysis_oot_data(
        record=cal_record_oot_a,
        gage=cal_gage_a,
        title="Micrometer Spindle Jam OOT",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_oot = OutOfToleranceInvestigation.objects.get(tenant=tenant_a, title="Micrometer Spindle Jam OOT")
    assert resp.url == reverse("quality:out_of_tolerance_investigation_detail", kwargs={"pk": created_oot.pk})

    # Gage must be quarantined immediately
    cal_gage_a.refresh_from_db()
    assert cal_gage_a.status == "quarantined_oot"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created_oot.pk)).first()
    assert audit is not None


def test_calibrationanalysis_views_oot_create_post_invalid(client, admin_user):
    """Verify invalid OOT post re-renders 200 with errors."""
    client.force_login(admin_user)
    url = reverse("quality:out_of_tolerance_investigation_create")
    resp = client.post(url, {"title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_calibrationanalysis_views_oot_detail_get_and_context(client, admin_user, cal_oot_a):
    """Verify OOT detail GET returns 200 with dual context keys."""
    client.force_login(admin_user)
    url = reverse("quality:out_of_tolerance_investigation_detail", kwargs={"pk": cal_oot_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["investigation"] == cal_oot_a
    assert resp.context["oot_investigation"] == cal_oot_a
    assert resp.context["obj"] == cal_oot_a
    assert cal_oot_a.number in resp.content.decode()


def test_calibrationanalysis_views_oot_edit_get(client, admin_user, cal_oot_a):
    """Verify OOT edit GET returns 200 with bound form and is_edit=True."""
    client.force_login(admin_user)
    url = reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": cal_oot_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["oot_investigation"] == cal_oot_a
    assert resp.context["obj"] == cal_oot_a


def test_calibrationanalysis_views_oot_edit_post_valid(client, admin_user, cal_oot_a):
    """Verify valid OOT edit updates DB, writes AuditLog, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": cal_oot_a.pk})
    post_data = _calibrationanalysis_oot_data(
        record=cal_oot_a.calibration_record,
        gage=cal_oot_a.gage,
        title=cal_oot_a.title,
        containment_actions_taken="Quarantined and inspected 200 finished parts.",
        status="mrb_review",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:out_of_tolerance_investigation_detail", kwargs={"pk": cal_oot_a.pk})

    cal_oot_a.refresh_from_db()
    assert cal_oot_a.containment_actions_taken == "Quarantined and inspected 200 finished parts."
    assert cal_oot_a.status == "mrb_review"

    audit = AuditLog.objects.filter(tenant=cal_oot_a.tenant, action="update", object_id=str(cal_oot_a.pk)).first()
    assert audit is not None


def test_calibrationanalysis_views_oot_edit_post_invalid(client, admin_user, cal_oot_a):
    """Verify invalid OOT edit re-renders 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": cal_oot_a.pk})
    resp = client.post(url, {"title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_calibrationanalysis_views_oot_delete_method_not_allowed(client, admin_user, cal_oot_a):
    """Verify GET on OOT delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:out_of_tolerance_investigation_delete", kwargs={"pk": cal_oot_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_calibrationanalysis_views_oot_delete_post_success(client, admin_user, tenant_a, cal_gage_a, cal_record_oot_a):
    """Verify admin POST deletion removes investigation, writes AuditLog, and redirects."""
    client.force_login(admin_user)
    disposable_oot = OutOfToleranceInvestigation.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        calibration_record=cal_record_oot_a,
        title="OOT to delete",
        as_found_error_description="Jaw error",
        suspect_window_start=timezone.now().date() - timedelta(days=30),
        status="open",
        risk_level="minor",
    )
    url = reverse("quality:out_of_tolerance_investigation_delete", kwargs={"pk": disposable_oot.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:out_of_tolerance_investigation_list")

    assert not OutOfToleranceInvestigation.objects.filter(pk=disposable_oot.pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(disposable_oot.pk)).first()
    assert audit is not None


def test_calibrationanalysis_views_oot_delete_non_admin_forbidden(member_client, cal_oot_a):
    """Verify non-admin user cannot delete OOT investigation."""
    url = reverse("quality:out_of_tolerance_investigation_delete", kwargs={"pk": cal_oot_a.pk})
    resp = member_client.post(url)
    assert resp.status_code in (403, 302)
    assert OutOfToleranceInvestigation.objects.filter(pk=cal_oot_a.pk).exists()


def test_calibrationanalysis_views_oot_export_csv(client, admin_user, tenant_a, cal_gage_a, cal_record_oot_a):
    """Verify OOT CSV export format, headers, and formula sanitization."""
    client.force_login(admin_user)

    OutOfToleranceInvestigation.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        calibration_record=cal_record_oot_a,
        title="+FormulaInjectionOOT",
        as_found_error_description="Formula test",
        suspect_window_start=timezone.now().date() - timedelta(days=30),
        status="open",
        risk_level="critical",
    )

    url = reverse("quality:out_of_tolerance_investigation_export_csv")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert 'filename="oot_investigations.csv"' in resp["Content-Disposition"]

    content = resp.content.decode("utf-8")
    rows = list(csv.reader(io.StringIO(content)))

    expected_headers = [
        "Investigation #", "Title", "Gage Tag", "Discovery Date", "Risk Level",
        "Status", "Disposition", "Suspect Batches", "Recall Required"
    ]
    assert rows[0] == expected_headers

    formula_row = next(r for r in rows if "+FormulaInjectionOOT" in r[1])
    assert formula_row[1].startswith("'+")


# =============================================================================
# 4. MeasurementSystemAnalysis Views
# =============================================================================

def test_calibrationanalysis_views_msa_list_get_and_context(client, admin_user, cal_msa_a):
    """Verify MSA study list GET returns 200 with all pinned context keys."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_list")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "msa_studies",
        "page_obj",
        "search_query",
        "study_type_filter",
        "status_filter",
        "result_filter",
        "study_type_choices",
        "status_choices",
        "result_choices",
        "total_studies",
        "acceptable_count",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from MSA list context"

    assert cal_msa_a in resp.context["msa_studies"]
    assert cal_msa_a.number in resp.content.decode()


def test_calibrationanalysis_views_msa_list_filters_and_search(client, admin_user, cal_msa_a):
    """Verify MSA list search and filters for study_type, status, and study_result."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_list")

    # Search by study_title
    resp_title = client.get(url, {"q": "Machining Cell 1"})
    assert resp_title.status_code == 200
    assert cal_msa_a in resp_title.context["msa_studies"]

    # Search by characteristic_name
    resp_char = client.get(url, {"q": "Outer Spool Diameter"})
    assert resp_char.status_code == 200
    assert cal_msa_a in resp_char.context["msa_studies"]

    # Filter by study_type
    resp_type = client.get(url, {"study_type": "gage_rr_crossed"})
    assert resp_type.status_code == 200
    assert cal_msa_a in resp_type.context["msa_studies"]

    # Filter by status
    resp_status = client.get(url, {"status": "approved"})
    assert resp_status.status_code == 200
    assert cal_msa_a in resp_status.context["msa_studies"]

    # Filter by study_result
    resp_result = client.get(url, {"study_result": "acceptable"})
    assert resp_result.status_code == 200
    assert cal_msa_a in resp_result.context["msa_studies"]

    # Negative search
    resp_none = client.get(url, {"q": "NON_EXISTENT_STUDY_XYZ"})
    assert resp_none.status_code == 200
    assert cal_msa_a not in resp_none.context["msa_studies"]


def test_calibrationanalysis_views_msa_list_pagination_and_junk_params(client, admin_user, tenant_a, cal_gage_a):
    """Verify MSA list handles pagination beyond 15 items and junk query params."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_list")

    for idx in range(18):
        MeasurementSystemAnalysis.objects.create(
            tenant=tenant_a,
            gage=cal_gage_a,
            study_title=f"Bulk MSA Study {idx:02d}",
            study_type="gage_rr_crossed",
            characteristic_name="Shaft OD",
            specification_tolerance=Decimal("0.05"),
            study_result="acceptable",
        )

    resp_p2 = client.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2

    resp_junk = client.get(url, {
        "page": "invalid_page_99",
        "study_type": "corrupted_study_type",
        "study_result": "corrupted_result",
    })
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1


def test_calibrationanalysis_views_msa_list_unauthenticated_redirect(client):
    """Verify unauthenticated access to MSA list redirects to login."""
    url = reverse("quality:measurement_system_analysis_list")
    resp = client.get(url)
    assert resp.status_code == 302


def test_calibrationanalysis_views_msa_create_get_with_gage_prefill(client, admin_user, cal_gage_a):
    """Verify MSA create GET pre-populates gage field when ?gage= is provided."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_create")
    resp = client.get(url, {"gage": str(cal_gage_a.pk)})
    assert resp.status_code == 200
    assert resp.context["form"].initial.get("gage") == str(cal_gage_a.pk)
    assert resp.context["is_edit"] is False


def test_calibrationanalysis_views_msa_create_post_valid(client, admin_user, tenant_a, cal_gage_a):
    """Verify valid MSA study creation redirects to detail and writes AuditLog."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_create")
    post_data = _calibrationanalysis_msa_data(
        gage=cal_gage_a,
        study_title="Line 4 Shaft Diameter Gage R&R Study",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302

    created_msa = MeasurementSystemAnalysis.objects.get(tenant=tenant_a, study_title="Line 4 Shaft Diameter Gage R&R Study")
    assert resp.url == reverse("quality:measurement_system_analysis_detail", kwargs={"pk": created_msa.pk})

    audit = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created_msa.pk)).first()
    assert audit is not None


def test_calibrationanalysis_views_msa_create_post_invalid(client, admin_user):
    """Verify invalid MSA study creation re-renders 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_create")
    resp = client.post(url, {"study_title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_calibrationanalysis_views_msa_detail_get_and_context(client, admin_user, cal_msa_a):
    """Verify MSA detail GET returns 200 with dual context keys."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_detail", kwargs={"pk": cal_msa_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200

    assert resp.context["study"] == cal_msa_a
    assert resp.context["measurement_system_analysis"] == cal_msa_a
    assert resp.context["msa_study"] == cal_msa_a
    assert resp.context["obj"] == cal_msa_a
    assert cal_msa_a.number in resp.content.decode()


def test_calibrationanalysis_views_msa_edit_get(client, admin_user, cal_msa_a):
    """Verify MSA edit GET returns 200 with bound form and is_edit=True."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_edit", kwargs={"pk": cal_msa_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is True
    assert resp.context["msa_study"] == cal_msa_a
    assert resp.context["obj"] == cal_msa_a


def test_calibrationanalysis_views_msa_edit_post_valid(client, admin_user, cal_msa_a):
    """Verify valid MSA edit updates DB, writes AuditLog, and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_edit", kwargs={"pk": cal_msa_a.pk})
    post_data = _calibrationanalysis_msa_data(
        gage=cal_msa_a.gage,
        study_title=cal_msa_a.study_title,
        conclusion="Updated conclusion: Gage R&R within AIAG 10-30% conditional acceptance window.",
        study_result="marginal_conditional",
    )

    resp = client.post(url, post_data)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:measurement_system_analysis_detail", kwargs={"pk": cal_msa_a.pk})

    cal_msa_a.refresh_from_db()
    assert cal_msa_a.conclusion == "Updated conclusion: Gage R&R within AIAG 10-30% conditional acceptance window."
    assert cal_msa_a.study_result == "marginal_conditional"

    audit = AuditLog.objects.filter(tenant=cal_msa_a.tenant, action="update", object_id=str(cal_msa_a.pk)).first()
    assert audit is not None


def test_calibrationanalysis_views_msa_edit_post_invalid(client, admin_user, cal_msa_a):
    """Verify invalid MSA edit re-renders 200 with form errors."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_edit", kwargs={"pk": cal_msa_a.pk})
    resp = client.post(url, {"study_title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_calibrationanalysis_views_msa_delete_method_not_allowed(client, admin_user, cal_msa_a):
    """Verify GET on MSA delete returns 405 Method Not Allowed."""
    client.force_login(admin_user)
    url = reverse("quality:measurement_system_analysis_delete", kwargs={"pk": cal_msa_a.pk})
    resp = client.get(url)
    assert resp.status_code == 405


def test_calibrationanalysis_views_msa_delete_post_success(client, admin_user, tenant_a, cal_gage_a):
    """Verify admin POST deletion removes MSA study, writes AuditLog, and redirects."""
    client.force_login(admin_user)
    disposable_msa = MeasurementSystemAnalysis.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        study_title="Disposable MSA Study",
        study_type="gage_rr_crossed",
        characteristic_name="Shaft OD",
        specification_tolerance=Decimal("0.05"),
    )
    url = reverse("quality:measurement_system_analysis_delete", kwargs={"pk": disposable_msa.pk})
    resp = client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("quality:measurement_system_analysis_list")

    assert not MeasurementSystemAnalysis.objects.filter(pk=disposable_msa.pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(disposable_msa.pk)).first()
    assert audit is not None


def test_calibrationanalysis_views_msa_delete_non_admin_forbidden(member_client, cal_msa_a):
    """Verify non-admin user cannot delete MSA study."""
    url = reverse("quality:measurement_system_analysis_delete", kwargs={"pk": cal_msa_a.pk})
    resp = member_client.post(url)
    assert resp.status_code in (403, 302)
    assert MeasurementSystemAnalysis.objects.filter(pk=cal_msa_a.pk).exists()


def test_calibrationanalysis_views_msa_export_csv(client, admin_user, tenant_a, cal_gage_a):
    """Verify MSA CSV export format, headers, and formula sanitization."""
    client.force_login(admin_user)

    MeasurementSystemAnalysis.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        study_title="-UncheckedFormulaMSA",
        study_type="gage_rr_crossed",
        characteristic_name="Diameter",
        specification_tolerance=Decimal("0.05"),
        study_result="acceptable",
    )

    url = reverse("quality:measurement_system_analysis_export_csv")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert 'filename="msa_studies.csv"' in resp["Content-Disposition"]

    content = resp.content.decode("utf-8")
    rows = list(csv.reader(io.StringIO(content)))

    expected_headers = [
        "Study #", "Title", "Gage Tag", "Type", "Method",
        "Characteristic", "Study Date", "%GRR", "P/T Ratio", "NDC", "Verdict"
    ]
    assert rows[0] == expected_headers

    formula_row = next(r for r in rows if "-UncheckedFormulaMSA" in r[1])
    assert formula_row[1].startswith("'-")


# =============================================================================
# 5. CalibrationVendors Directory View
# =============================================================================

def test_calibrationanalysis_views_vendor_directory_get_and_context(client, admin_user, cal_vendor_a):
    """Verify CalibrationVendors directory GET returns 200 with required context keys."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_vendor_directory")
    resp = client.get(url)
    assert resp.status_code == 200

    context_keys = [
        "vendors",
        "page_obj",
        "search_query",
        "total_vendors",
        "accredited_count",
    ]
    for key in context_keys:
        assert key in resp.context, f"Key '{key}' missing from vendor directory context"

    assert cal_vendor_a in resp.context["vendors"]
    assert cal_vendor_a.name in resp.content.decode()


def test_calibrationanalysis_views_vendor_directory_search_filter(client, admin_user, cal_vendor_a):
    """Verify vendor directory search filter matches by name and tax_id."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_vendor_directory")

    # Search match
    resp_match = client.get(url, {"q": "Precision Standards"})
    assert resp_match.status_code == 200
    assert cal_vendor_a in resp_match.context["vendors"]

    # Negative search
    resp_nomatch = client.get(url, {"q": "NON_EXISTENT_METROLOGY_LAB_XYZ"})
    assert resp_nomatch.status_code == 200
    assert cal_vendor_a not in resp_nomatch.context["vendors"]


def test_calibrationanalysis_views_vendor_directory_pagination(client, admin_user, tenant_a):
    """Verify vendor directory handles pagination beyond PAGE_SIZE (15)."""
    client.force_login(admin_user)
    url = reverse("quality:calibration_vendor_directory")

    for idx in range(18):
        v = Party.objects.create(
            tenant=tenant_a,
            name=f"Bulk Calibration Metrology Lab {idx:02d}",
            kind="organization",
        )
        PartyRole.objects.create(
            tenant=tenant_a,
            party=v,
            role="vendor",
        )

    resp_p2 = client.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert resp_p2.context["page_obj"].number == 2


def test_calibrationanalysis_views_vendor_directory_unauthenticated_redirect(client):
    """Verify unauthenticated access to vendor directory redirects to login."""
    url = reverse("quality:calibration_vendor_directory")
    resp = client.get(url)
    assert resp.status_code == 302


# =============================================================================
# 6. Cross-Tenant Isolation & IDOR Prevention
# =============================================================================

def test_calibrationanalysis_views_cross_tenant_gage_isolation(client, admin_user, cal_gage_b):
    """Verify tenant_a user cannot view, edit, delete, or leak tenant_b CalibrationGage."""
    client.force_login(admin_user)

    # Detail IDOR -> 404
    detail_url = reverse("quality:calibration_gage_detail", kwargs={"pk": cal_gage_b.pk})
    assert client.get(detail_url).status_code == 404

    # Edit IDOR -> 404
    edit_url = reverse("quality:calibration_gage_edit", kwargs={"pk": cal_gage_b.pk})
    assert client.get(edit_url).status_code == 404
    assert client.post(edit_url, _calibrationanalysis_gage_data()).status_code == 404

    # Delete IDOR -> 404
    delete_url = reverse("quality:calibration_gage_delete", kwargs={"pk": cal_gage_b.pk})
    assert client.post(delete_url).status_code == 404
    assert CalibrationGage.objects.filter(pk=cal_gage_b.pk).exists()

    # List isolation
    list_resp = client.get(reverse("quality:calibration_gage_list"))
    assert cal_gage_b not in list_resp.context["gages"]

    # CSV isolation
    csv_resp = client.get(reverse("quality:calibration_gage_export_csv"))
    assert cal_gage_b.gage_id not in csv_resp.content.decode()


def test_calibrationanalysis_views_cross_tenant_record_isolation(client, admin_user, cal_record_b):
    """Verify tenant_a user cannot view, edit, delete, or leak tenant_b CalibrationRecord."""
    client.force_login(admin_user)

    # Detail IDOR -> 404
    detail_url = reverse("quality:calibration_record_detail", kwargs={"pk": cal_record_b.pk})
    assert client.get(detail_url).status_code == 404

    # Edit IDOR -> 404
    edit_url = reverse("quality:calibration_record_edit", kwargs={"pk": cal_record_b.pk})
    assert client.get(edit_url).status_code == 404
    assert client.post(edit_url, _calibrationanalysis_record_data(cal_record_b.gage)).status_code == 404

    # Delete IDOR -> 404
    delete_url = reverse("quality:calibration_record_delete", kwargs={"pk": cal_record_b.pk})
    assert client.post(delete_url).status_code == 404
    assert CalibrationRecord.objects.filter(pk=cal_record_b.pk).exists()

    # List isolation
    list_resp = client.get(reverse("quality:calibration_record_list"))
    assert cal_record_b not in list_resp.context["calibration_records"]

    # CSV isolation
    csv_resp = client.get(reverse("quality:calibration_record_export_csv"))
    assert cal_record_b.certificate_number not in csv_resp.content.decode()


def test_calibrationanalysis_views_cross_tenant_oot_isolation(client, admin_user, cal_oot_b):
    """Verify tenant_a user cannot view, edit, delete, or leak tenant_b OutOfToleranceInvestigation."""
    client.force_login(admin_user)

    # Detail IDOR -> 404
    detail_url = reverse("quality:out_of_tolerance_investigation_detail", kwargs={"pk": cal_oot_b.pk})
    assert client.get(detail_url).status_code == 404

    # Edit IDOR -> 404
    edit_url = reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": cal_oot_b.pk})
    assert client.get(edit_url).status_code == 404
    assert client.post(edit_url, _calibrationanalysis_oot_data(cal_oot_b.calibration_record, cal_oot_b.gage)).status_code == 404

    # Delete IDOR -> 404
    delete_url = reverse("quality:out_of_tolerance_investigation_delete", kwargs={"pk": cal_oot_b.pk})
    assert client.post(delete_url).status_code == 404
    assert OutOfToleranceInvestigation.objects.filter(pk=cal_oot_b.pk).exists()

    # List isolation
    list_resp = client.get(reverse("quality:out_of_tolerance_investigation_list"))
    assert cal_oot_b not in list_resp.context["oot_investigations"]

    # CSV isolation
    csv_resp = client.get(reverse("quality:out_of_tolerance_investigation_export_csv"))
    assert cal_oot_b.title not in csv_resp.content.decode()


def test_calibrationanalysis_views_cross_tenant_msa_isolation(client, admin_user, cal_msa_b):
    """Verify tenant_a user cannot view, edit, delete, or leak tenant_b MeasurementSystemAnalysis."""
    client.force_login(admin_user)

    # Detail IDOR -> 404
    detail_url = reverse("quality:measurement_system_analysis_detail", kwargs={"pk": cal_msa_b.pk})
    assert client.get(detail_url).status_code == 404

    # Edit IDOR -> 404
    edit_url = reverse("quality:measurement_system_analysis_edit", kwargs={"pk": cal_msa_b.pk})
    assert client.get(edit_url).status_code == 404
    assert client.post(edit_url, _calibrationanalysis_msa_data(cal_msa_b.gage)).status_code == 404

    # Delete IDOR -> 404
    delete_url = reverse("quality:measurement_system_analysis_delete", kwargs={"pk": cal_msa_b.pk})
    assert client.post(delete_url).status_code == 404
    assert MeasurementSystemAnalysis.objects.filter(pk=cal_msa_b.pk).exists()

    # List isolation
    list_resp = client.get(reverse("quality:measurement_system_analysis_list"))
    assert cal_msa_b not in list_resp.context["msa_studies"]

    # CSV isolation
    csv_resp = client.get(reverse("quality:measurement_system_analysis_export_csv"))
    assert cal_msa_b.study_title not in csv_resp.content.decode()


def test_calibrationanalysis_views_cross_tenant_vendor_directory_isolation(client, admin_user, cal_vendor_b):
    """Verify tenant_b vendor does not leak into tenant_a CalibrationVendors directory."""
    client.force_login(admin_user)
    resp = client.get(reverse("quality:calibration_vendor_directory"))
    assert resp.status_code == 200
    assert cal_vendor_b not in resp.context["vendors"]
    assert cal_vendor_b.name not in resp.content.decode()
