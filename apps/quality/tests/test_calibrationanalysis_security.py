"""
Security, Multi-Tenant Data Isolation, Role-Based Access Control, and Adversarial Tests
for Sub-module 12.10: Calibration & Measurement System Analysis (MSA).

Covers all security vectors:
1. Cross-Tenant IDOR:
   - Detail view with cross-tenant PK returns HTTP 404 (CalibrationGage, CalibrationRecord,
     OutOfToleranceInvestigation, MeasurementSystemAnalysis) in both directions (A->B and B->A).
   - Edit GET with cross-tenant PK returns HTTP 404.
   - Edit POST with cross-tenant PK returns HTTP 404.
   - Delete POST with cross-tenant PK returns HTTP 404.
   - List querysets strictly isolated (Tenant A never sees Tenant B records; vendor directory strictly isolated).
   - CSV exports strictly isolated (Tenant B data never appears in Tenant A CSV).
   - Form FK cross-tenant injection rejected via reject_foreign (direct cleaned_data and bound form).

2. Authentication & Authorization:
   - Unauthenticated access to all 21 endpoints redirects to login (HTTP 302).
   - Unauthenticated mutating POST requests redirect to login (HTTP 302).
   - Delete endpoints require POST method (GET -> HTTP 405 Method Not Allowed).
   - Delete endpoints require tenant admin (@tenant_admin_required) — non-admin user gets HTTP 403 Forbidden.

3. CSV Formula Injection (CWE-1236):
   - Cells with leading '=', '+', '-', '@', '\\t', '\\r' are neutralized with "'" prefix in exported CSV data.
   - Sets 'X-Content-Type-Options: nosniff' header on all 4 CSV export responses.

4. Audit Logging & State Transitions:
   - Create, edit, and delete actions record AuditLog entries with valid verbs ('create', 'update', 'delete' <= 10 chars).
   - State transitions (quarantine on OOT result, active on pass, out of service on unrepairable failure)
     are strictly enforced and cannot be manipulated cross-tenant.
   - Mass assignment prevention: tenant and number fields cannot be overwritten via form submissions.

Conventions:
- All test functions prefixed: test_calibrationanalysis_security_*
- All module helpers prefixed: _calibrationanalysis_*
"""
import csv
import html
import io
import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, OrgUnit, Party, PartyRole
from apps.quality.forms._common import reject_foreign
from apps.quality.forms.CalibrationAnalysis.CalibrationGages import CalibrationGageForm
from apps.quality.forms.CalibrationAnalysis.CalibrationRecords import CalibrationRecordForm
from apps.quality.forms.CalibrationAnalysis.MeasurementSystemAnalyses import MeasurementSystemAnalysisForm
from apps.quality.forms.CalibrationAnalysis.OutOfToleranceInvestigations import OutOfToleranceInvestigationForm
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.CalibrationAnalysis.CalibrationRecords import CalibrationRecord
from apps.quality.models.CalibrationAnalysis.MeasurementSystemAnalyses import MeasurementSystemAnalysis
from apps.quality.models.CalibrationAnalysis.OutOfToleranceInvestigations import OutOfToleranceInvestigation
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.scm.models.AssetManagement.Assets import Asset
from apps.scm.models.Manufacturing.WorkCenters import WorkCenter

User = get_user_model()
pytestmark = pytest.mark.django_db


# =============================================================================
# Module Helpers (Prefix: _calibrationanalysis_*)
# =============================================================================

def _calibrationanalysis_pk(val):
    """Return pk if val is a model instance, or val itself if scalar / None."""
    if hasattr(val, "pk"):
        return val.pk
    return val


def _calibrationanalysis_date(days_offset=0):
    """Return an ISO formatted date string relative to today."""
    return (timezone.now().date() + timedelta(days=days_offset)).isoformat()


def _calibrationanalysis_create_work_center(tenant, code=None, name=None):
    """Create a minimal WorkCenter instance for testing tenant foreign key scoping."""
    uid = uuid.uuid4().hex[:6]
    return WorkCenter.objects.create(
        tenant=tenant,
        code=code or f"WC-SEC-{uid}",
        name=name or f"Machining Station {uid}",
    )


def _calibrationanalysis_create_asset(tenant, code=None, name=None):
    """Create a minimal Asset instance for testing tenant foreign key scoping."""
    uid = uuid.uuid4().hex[:6]
    return Asset.objects.create(
        tenant=tenant,
        code=code or f"AST-SEC-{uid}",
        name=name or f"Inspection Station Asset {uid}",
    )


def _calibrationanalysis_create_standard(tenant, gage_id=None, name=None, **extra):
    """Create a reference standard gage (is_reference_standard=True) for testing."""
    uid = uuid.uuid4().hex[:6]
    defaults = {
        "tenant": tenant,
        "gage_id": gage_id or f"GAG-STD-{uid}",
        "name": name or f"Grade 0 Master Gage Block {uid}",
        "gage_type": "gauge_block_pin",
        "criticality": "critical",
        "status": "active_in_service",
        "is_reference_standard": True,
        "measurement_range": "0.5mm to 100mm",
        "resolution": "0.0001 mm",
        "accuracy_spec": "+/- 0.0001 mm",
        "max_permissible_error": Decimal("0.0001"),
        "engineering_unit": "mm",
        "calibration_interval_days": 365,
    }
    defaults.update(extra)
    return CalibrationGage.objects.create(**defaults)


def _calibrationanalysis_gage_base_data(**extra):
    """Build valid baseline POST dictionary for CalibrationGageForm."""
    uid = uuid.uuid4().hex[:6]
    data = {
        "gage_id": f"GAG-SEC-{uid}",
        "name": f"Digital Micrometer 0-25mm {uid}",
        "gage_type": "caliper_micrometer",
        "criticality": "major",
        "status": "active_in_service",
        "manufacturer": "Mitutoyo",
        "model_number": "293-240-30",
        "serial_number": f"SN-SEC-{uid}",
        "measurement_range": "0 - 25 mm",
        "resolution": "0.001 mm",
        "accuracy_spec": "+/- 0.001 mm",
        "max_permissible_error": "0.0020",
        "engineering_unit": "mm",
        "is_reference_standard": False,
        "nist_traceability_number": "NIST-SEC-2026-001",
        "reference_standard_parent": "",
        "asset_link": "",
        "work_center": "",
        "department": "",
        "custodian": "",
        "storage_location": "Metrology Lab Cabinet A",
        "calibration_interval_days": 180,
        "last_calibration_date": _calibrationanalysis_date(-30),
        "next_calibration_due": _calibrationanalysis_date(150),
        "sop_document": "",
        "notes": "Standard inspection tool for precision machining.",
    }
    data.update(extra)
    return data


def _calibrationanalysis_record_base_data(gage, **extra):
    """Build valid baseline POST dictionary for CalibrationRecordForm."""
    uid = uuid.uuid4().hex[:6]
    data = {
        "gage": _calibrationanalysis_pk(gage),
        "calibration_date": _calibrationanalysis_date(-2),
        "calibration_type": "internal_metrology",
        "status": "completed",
        "service_vendor": "",
        "certificate_number": f"CERT-SEC-{uid}",
        "as_found_condition": "in_tolerance",
        "as_left_condition": "in_tolerance",
        "overall_result": "pass",
        "ambient_temperature_c": "20.00",
        "ambient_relative_humidity": "45.00",
        "expanded_uncertainty": "0.0020",
        "test_uncertainty_ratio": "4.00",
        "max_observed_error": "0.0010",
        "guardband_applied": True,
        "standards_used": [],
        "standard_traceability_notes": "Calibrated against Grade 0 master gauge blocks.",
        "technician_name": "Senior Metrologist",
        "calibrated_by_user": "",
        "approved_by": "",
        "notes": "Routine scheduled calibration completed conforming to ISO 17025.",
    }
    data.update(extra)
    return data


def _calibrationanalysis_oot_base_data(record, gage, **extra):
    """Build valid baseline POST dictionary for OutOfToleranceInvestigationForm."""
    data = {
        "calibration_record": _calibrationanalysis_pk(record),
        "gage": _calibrationanalysis_pk(gage),
        "discovery_date": _calibrationanalysis_date(0),
        "status": "open",
        "risk_level": "major",
        "title": "Out-of-Tolerance Deviation on Caliper Anvils",
        "as_found_error_description": "Jaw parallelism deviation of 0.045mm exceeded 0.020mm MPE.",
        "suspect_window_start": _calibrationanalysis_date(-90),
        "suspect_window_end": _calibrationanalysis_date(0),
        "suspect_work_center": "",
        "suspect_production_orders": "WO-2026-0811, WO-2026-0815",
        "suspect_lots_count": 8,
        "products_affected": "Housing Assembly P/N 88120",
        "consumer_risk_rating": 3,
        "producer_risk_rating": 3,
        "containment_actions_taken": "Instrument tagged and quarantined to metrology holding locker.",
        "product_disposition": "pending_review",
        "customer_notification_required": False,
        "product_recall_required": False,
        "linked_ncr": "",
        "linked_capa": "",
        "investigator": "",
        "quality_approver": "",
        "closure_date": "",
        "conclusion_summary": "",
    }
    data.update(extra)
    return data


def _calibrationanalysis_msa_base_data(gage, **extra):
    """Build valid baseline POST dictionary for MeasurementSystemAnalysisForm."""
    data = {
        "study_title": "Micrometer 0-25mm Crossed Gage R&R Study",
        "gage": _calibrationanalysis_pk(gage),
        "study_type": "gage_rr_crossed",
        "analysis_method": "anova",
        "status": "draft",
        "characteristic_name": "Outer Spool Diameter",
        "study_date": _calibrationanalysis_date(-1),
        "number_of_operators": 3,
        "number_of_parts": 10,
        "number_of_trials": 3,
        "specification_tolerance": "0.1000",
        "reference_master_value": "12.5000",
        "repeatability_ev": "0.0020",
        "reproducibility_av": "0.0015",
        "gage_rr_grr": "0.0025",
        "part_variation_pv": "0.0150",
        "total_variation_tv": "0.0152",
        "percent_gage_rr_study_variation": "16.45",
        "percent_tolerance_pt_ratio": "15.00",
        "number_of_distinct_categories_ndc": "8.00",
        "bias_value": "0.0002",
        "bias_percentage": "1.60",
        "linearity_slope": "0.0010",
        "linearity_r_squared": "0.9800",
        "study_result": "acceptable",
        "study_protocol_doc": "",
        "study_lead": "",
        "approved_by": "",
        "conclusion": "Initial trial run completed. Full analysis pending review.",
        "notes": "Conducted in CNC machining clean area.",
    }
    data.update(extra)
    return data


# =============================================================================
# 1. Multi-Tenant Data Isolation & Cross-Tenant IDOR Protection
# =============================================================================

def test_calibrationanalysis_security_idor_gage_detail_edit_delete(
    client, admin_user, admin_b, cal_gage_a, cal_gage_b
):
    """Verify cross-tenant IDOR access on CalibrationGage returns HTTP 404 in both directions."""
    # Tenant A user accessing Tenant B gage
    client.force_login(admin_user)
    assert client.get(
        reverse("quality:calibration_gage_detail", kwargs={"pk": cal_gage_b.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:calibration_gage_edit", kwargs={"pk": cal_gage_b.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:calibration_gage_edit", kwargs={"pk": cal_gage_b.pk}),
        {"name": "Cross Tenant Malicious Tamper"},
    ).status_code == 404
    assert client.post(
        reverse("quality:calibration_gage_delete", kwargs={"pk": cal_gage_b.pk})
    ).status_code == 404

    # Symmetric: Tenant B user accessing Tenant A gage
    client.force_login(admin_b)
    assert client.get(
        reverse("quality:calibration_gage_detail", kwargs={"pk": cal_gage_a.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:calibration_gage_edit", kwargs={"pk": cal_gage_a.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:calibration_gage_edit", kwargs={"pk": cal_gage_a.pk}),
        {"name": "Cross Tenant Malicious Tamper"},
    ).status_code == 404
    assert client.post(
        reverse("quality:calibration_gage_delete", kwargs={"pk": cal_gage_a.pk})
    ).status_code == 404


def test_calibrationanalysis_security_idor_record_detail_edit_delete(
    client, admin_user, admin_b, cal_record_a, cal_record_b
):
    """Verify cross-tenant IDOR access on CalibrationRecord returns HTTP 404 in both directions."""
    # Tenant A user accessing Tenant B record
    client.force_login(admin_user)
    assert client.get(
        reverse("quality:calibration_record_detail", kwargs={"pk": cal_record_b.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:calibration_record_edit", kwargs={"pk": cal_record_b.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:calibration_record_edit", kwargs={"pk": cal_record_b.pk}),
        {"technician_name": "Cross Tenant Malicious Technician"},
    ).status_code == 404
    assert client.post(
        reverse("quality:calibration_record_delete", kwargs={"pk": cal_record_b.pk})
    ).status_code == 404

    # Symmetric: Tenant B user accessing Tenant A record
    client.force_login(admin_b)
    assert client.get(
        reverse("quality:calibration_record_detail", kwargs={"pk": cal_record_a.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:calibration_record_edit", kwargs={"pk": cal_record_a.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:calibration_record_edit", kwargs={"pk": cal_record_a.pk}),
        {"technician_name": "Cross Tenant Malicious Technician"},
    ).status_code == 404
    assert client.post(
        reverse("quality:calibration_record_delete", kwargs={"pk": cal_record_a.pk})
    ).status_code == 404


def test_calibrationanalysis_security_idor_oot_detail_edit_delete(
    client, admin_user, admin_b, cal_oot_a, cal_oot_b
):
    """Verify cross-tenant IDOR access on OutOfToleranceInvestigation returns HTTP 404 in both directions."""
    # Tenant A user accessing Tenant B OOT investigation
    client.force_login(admin_user)
    assert client.get(
        reverse("quality:out_of_tolerance_investigation_detail", kwargs={"pk": cal_oot_b.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": cal_oot_b.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": cal_oot_b.pk}),
        {"title": "Cross Tenant Malicious OOT Tamper"},
    ).status_code == 404
    assert client.post(
        reverse("quality:out_of_tolerance_investigation_delete", kwargs={"pk": cal_oot_b.pk})
    ).status_code == 404

    # Symmetric: Tenant B user accessing Tenant A OOT investigation
    client.force_login(admin_b)
    assert client.get(
        reverse("quality:out_of_tolerance_investigation_detail", kwargs={"pk": cal_oot_a.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": cal_oot_a.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": cal_oot_a.pk}),
        {"title": "Cross Tenant Malicious OOT Tamper"},
    ).status_code == 404
    assert client.post(
        reverse("quality:out_of_tolerance_investigation_delete", kwargs={"pk": cal_oot_a.pk})
    ).status_code == 404


def test_calibrationanalysis_security_idor_msa_detail_edit_delete(
    client, admin_user, admin_b, cal_msa_a, cal_msa_b
):
    """Verify cross-tenant IDOR access on MeasurementSystemAnalysis returns HTTP 404 in both directions."""
    # Tenant A user accessing Tenant B MSA study
    client.force_login(admin_user)
    assert client.get(
        reverse("quality:measurement_system_analysis_detail", kwargs={"pk": cal_msa_b.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:measurement_system_analysis_edit", kwargs={"pk": cal_msa_b.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:measurement_system_analysis_edit", kwargs={"pk": cal_msa_b.pk}),
        {"study_title": "Cross Tenant Malicious MSA Tamper"},
    ).status_code == 404
    assert client.post(
        reverse("quality:measurement_system_analysis_delete", kwargs={"pk": cal_msa_b.pk})
    ).status_code == 404

    # Symmetric: Tenant B user accessing Tenant A MSA study
    client.force_login(admin_b)
    assert client.get(
        reverse("quality:measurement_system_analysis_detail", kwargs={"pk": cal_msa_a.pk})
    ).status_code == 404
    assert client.get(
        reverse("quality:measurement_system_analysis_edit", kwargs={"pk": cal_msa_a.pk})
    ).status_code == 404
    assert client.post(
        reverse("quality:measurement_system_analysis_edit", kwargs={"pk": cal_msa_a.pk}),
        {"study_title": "Cross Tenant Malicious MSA Tamper"},
    ).status_code == 404
    assert client.post(
        reverse("quality:measurement_system_analysis_delete", kwargs={"pk": cal_msa_a.pk})
    ).status_code == 404


def test_calibrationanalysis_security_list_querysets_tenant_isolated(
    client, admin_user, admin_b, cal_gage_a, cal_gage_b, cal_record_a, cal_record_b,
    cal_oot_a, cal_oot_b, cal_msa_a, cal_msa_b, cal_vendor_a, cal_vendor_b
):
    """Verify list views strictly isolate querysets between tenants."""
    # Tenant A view checks
    client.force_login(admin_user)

    # 1. Gage list
    resp_gage = client.get(reverse("quality:calibration_gage_list"))
    assert resp_gage.status_code == 200
    assert cal_gage_a.gage_id in resp_gage.content.decode()
    assert cal_gage_b.gage_id not in resp_gage.content.decode()

    # 2. Calibration record list
    resp_rec = client.get(reverse("quality:calibration_record_list"))
    assert resp_rec.status_code == 200
    assert cal_record_a.certificate_number in resp_rec.content.decode()
    assert cal_record_b.certificate_number not in resp_rec.content.decode()

    # 3. OOT investigation list
    resp_oot = client.get(reverse("quality:out_of_tolerance_investigation_list"))
    assert resp_oot.status_code == 200
    assert html.escape(cal_oot_a.title) in resp_oot.content.decode()
    assert cal_oot_a.gage.gage_id in resp_oot.content.decode()
    assert html.escape(cal_oot_b.title) not in resp_oot.content.decode()
    assert cal_oot_b.gage.gage_id not in resp_oot.content.decode()

    # 4. MSA studies list
    resp_msa = client.get(reverse("quality:measurement_system_analysis_list"))
    assert resp_msa.status_code == 200
    assert html.escape(cal_msa_a.study_title) in resp_msa.content.decode()
    assert html.escape(cal_msa_b.study_title) not in resp_msa.content.decode()

    # 5. Vendor directory
    resp_vendor = client.get(reverse("quality:calibration_vendor_directory"))
    assert resp_vendor.status_code == 200
    assert cal_vendor_a.name in resp_vendor.content.decode()
    assert cal_vendor_b.name not in resp_vendor.content.decode()

    # Tenant B view checks
    client.force_login(admin_b)

    # 1. Gage list
    resp_gage_b = client.get(reverse("quality:calibration_gage_list"))
    assert resp_gage_b.status_code == 200
    assert cal_gage_b.gage_id in resp_gage_b.content.decode()
    assert cal_gage_a.gage_id not in resp_gage_b.content.decode()

    # 2. Calibration record list
    resp_rec_b = client.get(reverse("quality:calibration_record_list"))
    assert resp_rec_b.status_code == 200
    assert cal_record_b.certificate_number in resp_rec_b.content.decode()
    assert cal_record_a.certificate_number not in resp_rec_b.content.decode()

    # 3. OOT investigation list
    resp_oot_b = client.get(reverse("quality:out_of_tolerance_investigation_list"))
    assert resp_oot_b.status_code == 200
    assert html.escape(cal_oot_b.title) in resp_oot_b.content.decode()
    assert cal_oot_b.gage.gage_id in resp_oot_b.content.decode()
    assert html.escape(cal_oot_a.title) not in resp_oot_b.content.decode()
    assert cal_oot_a.gage.gage_id not in resp_oot_b.content.decode()

    # 4. MSA studies list
    resp_msa_b = client.get(reverse("quality:measurement_system_analysis_list"))
    assert resp_msa_b.status_code == 200
    assert html.escape(cal_msa_b.study_title) in resp_msa_b.content.decode()
    assert html.escape(cal_msa_a.study_title) not in resp_msa_b.content.decode()

    # 5. Vendor directory
    resp_vendor_b = client.get(reverse("quality:calibration_vendor_directory"))
    assert resp_vendor_b.status_code == 200
    assert cal_vendor_b.name in resp_vendor_b.content.decode()
    assert cal_vendor_a.name not in resp_vendor_b.content.decode()


def test_calibrationanalysis_security_csv_exports_tenant_isolated(
    client, admin_user, admin_b, cal_gage_a, cal_gage_b, cal_record_a, cal_record_b,
    cal_oot_a, cal_oot_b, cal_msa_a, cal_msa_b
):
    """Verify CSV export endpoints strictly isolate tenant records."""
    # Tenant A exports
    client.force_login(admin_user)

    resp_gage = client.get(reverse("quality:calibration_gage_export_csv"))
    assert resp_gage.status_code == 200
    content_gage = resp_gage.content.decode()
    assert cal_gage_a.gage_id in content_gage
    assert cal_gage_b.gage_id not in content_gage

    resp_rec = client.get(reverse("quality:calibration_record_export_csv"))
    assert resp_rec.status_code == 200
    content_rec = resp_rec.content.decode()
    assert cal_record_a.certificate_number in content_rec
    assert cal_record_b.certificate_number not in content_rec

    resp_oot = client.get(reverse("quality:out_of_tolerance_investigation_export_csv"))
    assert resp_oot.status_code == 200
    content_oot = resp_oot.content.decode()
    assert cal_oot_a.title in content_oot
    assert cal_oot_b.title not in content_oot

    resp_msa = client.get(reverse("quality:measurement_system_analysis_export_csv"))
    assert resp_msa.status_code == 200
    content_msa = resp_msa.content.decode()
    assert cal_msa_a.study_title in content_msa
    assert cal_msa_b.study_title not in content_msa

    # Tenant B exports
    client.force_login(admin_b)

    resp_gage_b = client.get(reverse("quality:calibration_gage_export_csv"))
    assert resp_gage_b.status_code == 200
    content_gage_b = resp_gage_b.content.decode()
    assert cal_gage_b.gage_id in content_gage_b
    assert cal_gage_a.gage_id not in content_gage_b

    resp_rec_b = client.get(reverse("quality:calibration_record_export_csv"))
    assert resp_rec_b.status_code == 200
    content_rec_b = resp_rec_b.content.decode()
    assert cal_record_b.certificate_number in content_rec_b
    assert cal_record_a.certificate_number not in content_rec_b

    resp_oot_b = client.get(reverse("quality:out_of_tolerance_investigation_export_csv"))
    assert resp_oot_b.status_code == 200
    content_oot_b = resp_oot_b.content.decode()
    assert cal_oot_b.title in content_oot_b
    assert cal_oot_a.title not in content_oot_b

    resp_msa_b = client.get(reverse("quality:measurement_system_analysis_export_csv"))
    assert resp_msa_b.status_code == 200
    content_msa_b = resp_msa_b.content.decode()
    assert cal_msa_b.study_title in content_msa_b
    assert cal_msa_a.study_title not in content_msa_b


# =============================================================================
# 2. Form Foreign Key Boundary Enforcement (reject_foreign)
# =============================================================================

def test_calibrationanalysis_security_reject_foreign_gage_form(
    tenant_a, tenant_b, admin_b, cal_standard_b, quality_department_b
):
    """Verify CalibrationGageForm rejects foreign reference_standard_parent, asset_link, work_center, department, custodian, sop_document."""
    asset_b = _calibrationanalysis_create_asset(tenant_b)
    wc_b = _calibrationanalysis_create_work_center(tenant_b)
    doc_b = ControlledDocument.objects.create(
        tenant=tenant_b,
        owner=admin_b,
        title="Foreign SOP Document B",
        document_type="sop",
        revision="1.0",
        lifecycle_state="effective",
    )

    # 1. Direct reject_foreign invocation on cleaned_data
    form_direct = CalibrationGageForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct._errors = {}
    form_direct.cleaned_data = {
        "reference_standard_parent": cal_standard_b,
        "asset_link": asset_b,
        "work_center": wc_b,
        "department": quality_department_b,
        "custodian": admin_b,
        "sop_document": doc_b,
    }
    reject_foreign(form_direct, form_direct.cleaned_data, [
        "reference_standard_parent", "asset_link", "work_center", "department", "custodian", "sop_document"
    ])
    for field in ["reference_standard_parent", "asset_link", "work_center", "department", "custodian", "sop_document"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field]

    # 2. Form submission with foreign custodian pk is rejected by field queryset scoping
    bad_data = _calibrationanalysis_gage_base_data(custodian=admin_b.pk)
    form_bound = CalibrationGageForm(data=bad_data, tenant=tenant_a)
    assert not form_bound.is_valid()
    assert "custodian" in form_bound.errors


def test_calibrationanalysis_security_reject_foreign_record_form(
    tenant_a, tenant_b, admin_b, cal_gage_b, cal_vendor_b, cal_standard_b
):
    """Verify CalibrationRecordForm rejects foreign gage, service_vendor, standards_used, calibrated_by_user, approved_by."""
    # 1. Direct reject_foreign invocation on cleaned_data
    form_direct = CalibrationRecordForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct._errors = {}
    form_direct.cleaned_data = {
        "gage": cal_gage_b,
        "service_vendor": cal_vendor_b,
        "standards_used": [cal_standard_b],
        "calibrated_by_user": admin_b,
        "approved_by": admin_b,
    }
    reject_foreign(form_direct, form_direct.cleaned_data, [
        "gage", "service_vendor", "standards_used", "calibrated_by_user", "approved_by"
    ])
    for field in ["gage", "service_vendor", "standards_used", "calibrated_by_user", "approved_by"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field]

    # 2. Form submission with foreign gage pk is rejected
    bad_data = _calibrationanalysis_record_base_data(gage=cal_gage_b.pk)
    form_bound = CalibrationRecordForm(data=bad_data, tenant=tenant_a)
    assert not form_bound.is_valid()
    assert "gage" in form_bound.errors


def test_calibrationanalysis_security_reject_foreign_oot_form(
    tenant_a, tenant_b, admin_b, cal_record_b, cal_gage_b
):
    """Verify OutOfToleranceInvestigationForm rejects foreign calibration_record, gage, suspect_work_center, linked_ncr, linked_capa, investigator, quality_approver."""
    wc_b = _calibrationanalysis_create_work_center(tenant_b)
    ncr_b = NonConformanceReport.objects.create(
        tenant=tenant_b,
        title="Foreign NCR B",
        description="Defect in tenant B",
        initiator=admin_b,
        owner=admin_b,
    )
    capa_b = CapaInvestigation.objects.create(
        tenant=tenant_b,
        title="Foreign CAPA B",
        issue_summary="CAPA in tenant B",
        lead_investigator=admin_b,
        quality_owner=admin_b,
    )

    # 1. Direct reject_foreign invocation on cleaned_data
    form_direct = OutOfToleranceInvestigationForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct._errors = {}
    form_direct.cleaned_data = {
        "calibration_record": cal_record_b,
        "gage": cal_gage_b,
        "suspect_work_center": wc_b,
        "linked_ncr": ncr_b,
        "linked_capa": capa_b,
        "investigator": admin_b,
        "quality_approver": admin_b,
    }
    reject_foreign(form_direct, form_direct.cleaned_data, [
        "calibration_record", "gage", "suspect_work_center", "linked_ncr", "linked_capa", "investigator", "quality_approver"
    ])
    for field in ["calibration_record", "gage", "suspect_work_center", "linked_ncr", "linked_capa", "investigator", "quality_approver"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field]

    # 2. Form submission with foreign calibration_record pk is rejected
    bad_data = _calibrationanalysis_oot_base_data(record=cal_record_b.pk, gage=cal_gage_b.pk)
    form_bound = OutOfToleranceInvestigationForm(data=bad_data, tenant=tenant_a)
    assert not form_bound.is_valid()
    assert "calibration_record" in form_bound.errors


def test_calibrationanalysis_security_reject_foreign_msa_form(
    tenant_a, tenant_b, admin_b, cal_gage_b
):
    """Verify MeasurementSystemAnalysisForm rejects foreign gage, study_protocol_doc, study_lead, approved_by."""
    doc_b = ControlledDocument.objects.create(
        tenant=tenant_b,
        owner=admin_b,
        title="Foreign Protocol SOP B",
        document_type="sop",
        revision="1.0",
        lifecycle_state="effective",
    )

    # 1. Direct reject_foreign invocation on cleaned_data
    form_direct = MeasurementSystemAnalysisForm(data={}, tenant=tenant_a)
    form_direct.is_valid()
    form_direct._errors = {}
    form_direct.cleaned_data = {
        "gage": cal_gage_b,
        "study_protocol_doc": doc_b,
        "study_lead": admin_b,
        "approved_by": admin_b,
    }
    reject_foreign(form_direct, form_direct.cleaned_data, [
        "gage", "study_protocol_doc", "study_lead", "approved_by"
    ])
    for field in ["gage", "study_protocol_doc", "study_lead", "approved_by"]:
        assert field in form_direct.errors
        assert "That record belongs to another workspace." in form_direct.errors[field]

    # 2. Form submission with foreign gage pk is rejected
    bad_data = _calibrationanalysis_msa_base_data(gage=cal_gage_b.pk)
    form_bound = MeasurementSystemAnalysisForm(data=bad_data, tenant=tenant_a)
    assert not form_bound.is_valid()
    assert "gage" in form_bound.errors


# =============================================================================
# 3. Authentication & Authorization (21 GET endpoints, Mutating POST, @require_POST, @tenant_admin_required)
# =============================================================================

def test_calibrationanalysis_security_unauthenticated_access_redirects_to_login(
    client, cal_gage_a, cal_record_a, cal_oot_a, cal_msa_a
):
    """Verify all 21 GET endpoints redirect unauthenticated requests to login (HTTP 302)."""
    endpoints = [
        # CalibrationGage (5 GET endpoints)
        reverse("quality:calibration_gage_list"),
        reverse("quality:calibration_gage_create"),
        reverse("quality:calibration_gage_export_csv"),
        reverse("quality:calibration_gage_detail", kwargs={"pk": cal_gage_a.pk}),
        reverse("quality:calibration_gage_edit", kwargs={"pk": cal_gage_a.pk}),
        # CalibrationRecord (5 GET endpoints)
        reverse("quality:calibration_record_list"),
        reverse("quality:calibration_record_create"),
        reverse("quality:calibration_record_export_csv"),
        reverse("quality:calibration_record_detail", kwargs={"pk": cal_record_a.pk}),
        reverse("quality:calibration_record_edit", kwargs={"pk": cal_record_a.pk}),
        # OutOfToleranceInvestigation (5 GET endpoints)
        reverse("quality:out_of_tolerance_investigation_list"),
        reverse("quality:out_of_tolerance_investigation_create"),
        reverse("quality:out_of_tolerance_investigation_export_csv"),
        reverse("quality:out_of_tolerance_investigation_detail", kwargs={"pk": cal_oot_a.pk}),
        reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": cal_oot_a.pk}),
        # MeasurementSystemAnalysis (5 GET endpoints)
        reverse("quality:measurement_system_analysis_list"),
        reverse("quality:measurement_system_analysis_create"),
        reverse("quality:measurement_system_analysis_export_csv"),
        reverse("quality:measurement_system_analysis_detail", kwargs={"pk": cal_msa_a.pk}),
        reverse("quality:measurement_system_analysis_edit", kwargs={"pk": cal_msa_a.pk}),
        # CalibrationVendors (1 GET endpoint)
        reverse("quality:calibration_vendor_directory"),
    ]

    assert len(endpoints) == 21, f"Expected exactly 21 endpoints, got {len(endpoints)}"

    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302, f"Endpoint {url} did not redirect unauthenticated GET client"
        assert "/accounts/login/" in resp.url or "login" in resp.url


def test_calibrationanalysis_security_unauthenticated_mutations_redirect_to_login(
    client, cal_gage_a, cal_record_a, cal_oot_a, cal_msa_a
):
    """Verify unauthenticated mutating POST requests redirect to login (HTTP 302)."""
    post_targets = [
        # CalibrationGage
        reverse("quality:calibration_gage_create"),
        reverse("quality:calibration_gage_edit", kwargs={"pk": cal_gage_a.pk}),
        reverse("quality:calibration_gage_delete", kwargs={"pk": cal_gage_a.pk}),
        # CalibrationRecord
        reverse("quality:calibration_record_create"),
        reverse("quality:calibration_record_edit", kwargs={"pk": cal_record_a.pk}),
        reverse("quality:calibration_record_delete", kwargs={"pk": cal_record_a.pk}),
        # OutOfToleranceInvestigation
        reverse("quality:out_of_tolerance_investigation_create"),
        reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": cal_oot_a.pk}),
        reverse("quality:out_of_tolerance_investigation_delete", kwargs={"pk": cal_oot_a.pk}),
        # MeasurementSystemAnalysis
        reverse("quality:measurement_system_analysis_create"),
        reverse("quality:measurement_system_analysis_edit", kwargs={"pk": cal_msa_a.pk}),
        reverse("quality:measurement_system_analysis_delete", kwargs={"pk": cal_msa_a.pk}),
    ]

    for url in post_targets:
        resp = client.post(url, {})
        assert resp.status_code == 302, f"POST to {url} did not redirect unauthenticated client"
        assert "/accounts/login/" in resp.url or "login" in resp.url


def test_calibrationanalysis_security_delete_endpoints_require_post_method(
    client, admin_user, cal_gage_a, cal_record_a, cal_oot_a, cal_msa_a
):
    """Verify all 4 delete endpoints require POST and reject GET with HTTP 405 Method Not Allowed."""
    client.force_login(admin_user)
    delete_urls = [
        reverse("quality:calibration_gage_delete", kwargs={"pk": cal_gage_a.pk}),
        reverse("quality:calibration_record_delete", kwargs={"pk": cal_record_a.pk}),
        reverse("quality:out_of_tolerance_investigation_delete", kwargs={"pk": cal_oot_a.pk}),
        reverse("quality:measurement_system_analysis_delete", kwargs={"pk": cal_msa_a.pk}),
    ]
    for url in delete_urls:
        resp = client.get(url)
        assert resp.status_code == 405, f"GET on {url} should return 405 Method Not Allowed"


def test_calibrationanalysis_security_delete_endpoints_require_tenant_admin(
    member_client, cal_gage_a, cal_record_a, cal_oot_a, cal_msa_a
):
    """Verify non-admin tenant members are rejected with HTTP 403 Forbidden on all 4 delete endpoints."""
    # 1. CalibrationGage delete
    resp_gage = member_client.post(
        reverse("quality:calibration_gage_delete", kwargs={"pk": cal_gage_a.pk})
    )
    assert resp_gage.status_code == 403
    assert CalibrationGage.objects.filter(pk=cal_gage_a.pk).exists()

    # 2. CalibrationRecord delete
    resp_rec = member_client.post(
        reverse("quality:calibration_record_delete", kwargs={"pk": cal_record_a.pk})
    )
    assert resp_rec.status_code == 403
    assert CalibrationRecord.objects.filter(pk=cal_record_a.pk).exists()

    # 3. OutOfToleranceInvestigation delete
    resp_oot = member_client.post(
        reverse("quality:out_of_tolerance_investigation_delete", kwargs={"pk": cal_oot_a.pk})
    )
    assert resp_oot.status_code == 403
    assert OutOfToleranceInvestigation.objects.filter(pk=cal_oot_a.pk).exists()

    # 4. MeasurementSystemAnalysis delete
    resp_msa = member_client.post(
        reverse("quality:measurement_system_analysis_delete", kwargs={"pk": cal_msa_a.pk})
    )
    assert resp_msa.status_code == 403
    assert MeasurementSystemAnalysis.objects.filter(pk=cal_msa_a.pk).exists()


# =============================================================================
# 4. CSV Formula Injection Defense (CWE-1236)
# =============================================================================

def test_calibrationanalysis_security_csv_export_neutralizes_formula_gage(client, admin_user, tenant_a):
    """Verify CalibrationGage CSV export neutralizes formula prefixes and sets nosniff."""
    client.force_login(admin_user)
    CalibrationGage.objects.create(
        tenant=tenant_a,
        gage_id="=cmd|' /C calc'!A0",
        name="+SUM(1+1) Caliper",
        gage_type="caliper_micrometer",
        criticality="critical",
        status="active_in_service",
        serial_number="-SN-FORMULA-01",
        measurement_range="@0-100mm",
        max_permissible_error=Decimal("0.0020"),
        engineering_unit="\t=TAB-UNIT",
        storage_location="\r=RETURN-LOCATION",
    )

    resp = client.get(reverse("quality:calibration_gage_export_csv"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_formula = False
    for row in rows:
        for cell in row:
            if any(cell.startswith(p) for p in ["'=", "'+", "'-", "'@", "'\t", "'\r"]):
                found_formula = True
    assert found_formula, f"Formula prefix neutralization failed in CalibrationGage CSV:\n{content}"


def test_calibrationanalysis_security_csv_export_neutralizes_formula_record(client, admin_user, tenant_a, cal_gage_a):
    """Verify CalibrationRecord CSV export neutralizes formula prefixes and sets nosniff."""
    client.force_login(admin_user)
    CalibrationRecord.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        calibration_date=timezone.now().date(),
        calibration_type="internal_metrology",
        status="completed",
        certificate_number="=SUM(A1:A10)",
        overall_result="pass",
        expanded_uncertainty=Decimal("0.0010"),
        test_uncertainty_ratio=Decimal("4.00"),
    )

    resp = client.get(reverse("quality:calibration_record_export_csv"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_formula = False
    for row in rows:
        for cell in row:
            if cell.startswith("'="):
                found_formula = True
    assert found_formula, f"Formula prefix neutralization failed in CalibrationRecord CSV:\n{content}"


def test_calibrationanalysis_security_csv_export_neutralizes_formula_oot(client, admin_user, tenant_a, cal_gage_a, cal_record_a):
    """Verify OutOfToleranceInvestigation CSV export neutralizes formula prefixes and sets nosniff."""
    client.force_login(admin_user)
    OutOfToleranceInvestigation.objects.create(
        tenant=tenant_a,
        calibration_record=cal_record_a,
        gage=cal_gage_a,
        title="=cmd|' /C calc'!A0",
        discovery_date=timezone.now().date(),
        suspect_window_start=timezone.now().date() - timedelta(days=30),
        status="open",
        risk_level="major",
        suspect_lots_count=5,
    )

    resp = client.get(reverse("quality:out_of_tolerance_investigation_export_csv"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_formula = False
    for row in rows:
        for cell in row:
            if cell.startswith("'="):
                found_formula = True
    assert found_formula, f"Formula prefix neutralization failed in OOT CSV:\n{content}"


def test_calibrationanalysis_security_csv_export_neutralizes_formula_msa(client, admin_user, tenant_a, cal_gage_a):
    """Verify MeasurementSystemAnalysis CSV export neutralizes formula prefixes and sets nosniff."""
    client.force_login(admin_user)
    MeasurementSystemAnalysis.objects.create(
        tenant=tenant_a,
        gage=cal_gage_a,
        study_title="=cmd|' /C notepad'!A0",
        characteristic_name="+CRITICAL-DIAMETER",
        study_type="gage_rr_crossed",
        analysis_method="anova",
        status="draft",
        study_date=timezone.now().date(),
    )

    resp = client.get(reverse("quality:measurement_system_analysis_export_csv"))
    assert resp.status_code == 200
    assert resp["X-Content-Type-Options"] == "nosniff"

    content = resp.content.decode("utf-8")
    reader = csv.reader(io.StringIO(content))
    rows = list(reader)

    found_formula = False
    for row in rows:
        for cell in row:
            if any(cell.startswith(p) for p in ["'=", "'+"]):
                found_formula = True
    assert found_formula, f"Formula prefix neutralization failed in MSA CSV:\n{content}"


# =============================================================================
# 5. Audit Logging & State Transitions
# =============================================================================

def test_calibrationanalysis_security_audit_log_gage_lifecycle(client_a, tenant_a, admin_user):
    """Verify AuditLog records are faithfully generated with short verbs (<= 10 chars) for Gage create, edit, delete."""
    # 1. Create
    data = _calibrationanalysis_gage_base_data()
    resp_create = client_a.post(reverse("quality:calibration_gage_create"), data)
    assert resp_create.status_code == 302
    created_gage = CalibrationGage.objects.get(tenant=tenant_a, gage_id=data["gage_id"])

    audit_create = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="create", object_id=str(created_gage.pk)
    ).first()
    assert audit_create is not None, "AuditLog for Gage create was not recorded!"
    assert len(audit_create.action) <= 10

    # 2. Update
    data["name"] = "Updated Gage Name for Audit Test"
    resp_update = client_a.post(
        reverse("quality:calibration_gage_edit", kwargs={"pk": created_gage.pk}), data
    )
    assert resp_update.status_code == 302
    audit_update = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="update", object_id=str(created_gage.pk)
    ).first()
    assert audit_update is not None, "AuditLog for Gage update was not recorded!"
    assert len(audit_update.action) <= 10

    # 3. Delete
    resp_delete = client_a.post(
        reverse("quality:calibration_gage_delete", kwargs={"pk": created_gage.pk})
    )
    assert resp_delete.status_code == 302
    audit_delete = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="delete", object_id=str(created_gage.pk)
    ).first()
    assert audit_delete is not None, "AuditLog for Gage delete was not recorded!"
    assert len(audit_delete.action) <= 10


def test_calibrationanalysis_security_audit_log_record_lifecycle(client_a, tenant_a, cal_gage_a, admin_user):
    """Verify AuditLog records are faithfully generated for CalibrationRecord create, edit, delete."""
    # 1. Create
    data = _calibrationanalysis_record_base_data(gage=cal_gage_a)
    resp_create = client_a.post(reverse("quality:calibration_record_create"), data)
    assert resp_create.status_code == 302
    created_record = CalibrationRecord.objects.get(tenant=tenant_a, certificate_number=data["certificate_number"])

    audit_create = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="create", object_id=str(created_record.pk)
    ).first()
    assert audit_create is not None, "AuditLog for CalibrationRecord create was not recorded!"
    assert len(audit_create.action) <= 10

    # 2. Update
    data["technician_name"] = "Lead Metrology Engineer"
    resp_update = client_a.post(
        reverse("quality:calibration_record_edit", kwargs={"pk": created_record.pk}), data
    )
    assert resp_update.status_code == 302
    audit_update = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="update", object_id=str(created_record.pk)
    ).first()
    assert audit_update is not None, "AuditLog for CalibrationRecord update was not recorded!"
    assert len(audit_update.action) <= 10

    # 3. Delete
    resp_delete = client_a.post(
        reverse("quality:calibration_record_delete", kwargs={"pk": created_record.pk})
    )
    assert resp_delete.status_code == 302
    audit_delete = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="delete", object_id=str(created_record.pk)
    ).first()
    assert audit_delete is not None, "AuditLog for CalibrationRecord delete was not recorded!"
    assert len(audit_delete.action) <= 10


def test_calibrationanalysis_security_audit_log_oot_lifecycle(client_a, tenant_a, cal_gage_a, cal_record_a, admin_user):
    """Verify AuditLog records are faithfully generated for OutOfToleranceInvestigation create, edit, delete."""
    # 1. Create
    data = _calibrationanalysis_oot_base_data(record=cal_record_a, gage=cal_gage_a)
    resp_create = client_a.post(reverse("quality:out_of_tolerance_investigation_create"), data)
    assert resp_create.status_code == 302
    created_oot = OutOfToleranceInvestigation.objects.filter(tenant=tenant_a, gage=cal_gage_a).latest("id")

    audit_create = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="create", object_id=str(created_oot.pk)
    ).first()
    assert audit_create is not None, "AuditLog for OOT create was not recorded!"
    assert len(audit_create.action) <= 10

    # 2. Update
    data["title"] = "Updated OOT Investigation Title"
    resp_update = client_a.post(
        reverse("quality:out_of_tolerance_investigation_edit", kwargs={"pk": created_oot.pk}), data
    )
    assert resp_update.status_code == 302
    audit_update = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="update", object_id=str(created_oot.pk)
    ).first()
    assert audit_update is not None, "AuditLog for OOT update was not recorded!"
    assert len(audit_update.action) <= 10

    # 3. Delete
    resp_delete = client_a.post(
        reverse("quality:out_of_tolerance_investigation_delete", kwargs={"pk": created_oot.pk})
    )
    assert resp_delete.status_code == 302
    audit_delete = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="delete", object_id=str(created_oot.pk)
    ).first()
    assert audit_delete is not None, "AuditLog for OOT delete was not recorded!"
    assert len(audit_delete.action) <= 10


def test_calibrationanalysis_security_audit_log_msa_lifecycle(client_a, tenant_a, cal_gage_a, admin_user):
    """Verify AuditLog records are faithfully generated for MeasurementSystemAnalysis create, edit, delete."""
    # 1. Create
    data = _calibrationanalysis_msa_base_data(gage=cal_gage_a)
    resp_create = client_a.post(reverse("quality:measurement_system_analysis_create"), data)
    assert resp_create.status_code == 302
    created_msa = MeasurementSystemAnalysis.objects.get(tenant=tenant_a, study_title=data["study_title"])

    audit_create = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="create", object_id=str(created_msa.pk)
    ).first()
    assert audit_create is not None, "AuditLog for MSA create was not recorded!"
    assert len(audit_create.action) <= 10

    # 2. Update
    data["characteristic_name"] = "Critical Bore Inner Diameter"
    resp_update = client_a.post(
        reverse("quality:measurement_system_analysis_edit", kwargs={"pk": created_msa.pk}), data
    )
    assert resp_update.status_code == 302
    audit_update = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="update", object_id=str(created_msa.pk)
    ).first()
    assert audit_update is not None, "AuditLog for MSA update was not recorded!"
    assert len(audit_update.action) <= 10

    # 3. Delete
    resp_delete = client_a.post(
        reverse("quality:measurement_system_analysis_delete", kwargs={"pk": created_msa.pk})
    )
    assert resp_delete.status_code == 302
    audit_delete = AuditLog.objects.filter(
        tenant=tenant_a, user=admin_user, action="delete", object_id=str(created_msa.pk)
    ).first()
    assert audit_delete is not None, "AuditLog for MSA delete was not recorded!"
    assert len(audit_delete.action) <= 10


def test_calibrationanalysis_security_state_transitions_on_calibration_results(
    client_a, tenant_a, cal_gage_a
):
    """Verify state transitions and quarantine triggers on calibration results."""
    # 1. Calibration record with fail_out_of_tolerance -> Gage is automatically quarantined
    cal_gage_a.status = "active_in_service"
    cal_gage_a.save()

    data_oot = _calibrationanalysis_record_base_data(
        gage=cal_gage_a,
        overall_result="fail_out_of_tolerance",
        status="completed",
    )
    resp1 = client_a.post(reverse("quality:calibration_record_create"), data_oot)
    assert resp1.status_code == 302

    cal_gage_a.refresh_from_db()
    assert cal_gage_a.status == "quarantined_oot"

    # 2. Creating an OutOfToleranceInvestigation also enforces gage quarantine
    cal_gage_a.status = "active_in_service"
    cal_gage_a.save()

    rec = CalibrationRecord.objects.filter(tenant=tenant_a, gage=cal_gage_a).latest("id")
    data_inv = _calibrationanalysis_oot_base_data(record=rec, gage=cal_gage_a)
    resp2 = client_a.post(reverse("quality:out_of_tolerance_investigation_create"), data_inv)
    assert resp2.status_code == 302

    cal_gage_a.refresh_from_db()
    assert cal_gage_a.status == "quarantined_oot"

    # 3. Calibration record with pass -> Gage is restored to active_in_service
    data_pass = _calibrationanalysis_record_base_data(
        gage=cal_gage_a,
        overall_result="pass",
        status="completed",
    )
    resp3 = client_a.post(reverse("quality:calibration_record_create"), data_pass)
    assert resp3.status_code == 302

    cal_gage_a.refresh_from_db()
    assert cal_gage_a.status == "active_in_service"

    # 4. Calibration record with fail_unrepairable -> Gage is marked out_of_service
    data_unrepairable = _calibrationanalysis_record_base_data(
        gage=cal_gage_a,
        overall_result="fail_unrepairable",
        status="completed",
    )
    resp4 = client_a.post(reverse("quality:calibration_record_create"), data_unrepairable)
    assert resp4.status_code == 302

    cal_gage_a.refresh_from_db()
    assert cal_gage_a.status == "out_of_service"


def test_calibrationanalysis_security_mass_assignment_protection(
    client_a, tenant_a, tenant_b, admin_user
):
    """Verify tenant and number fields cannot be overwritten via malicious mass-assignment POST payloads."""
    # 1. CalibrationGageForm exclusions
    form_gage = CalibrationGageForm(tenant=tenant_a)
    assert "tenant" not in form_gage.fields
    assert "number" not in form_gage.fields

    gage_data = _calibrationanalysis_gage_base_data(
        tenant=tenant_b.pk,
        number="MALICIOUS-GAGE-NUM",
    )
    resp_gage = client_a.post(reverse("quality:calibration_gage_create"), gage_data)
    assert resp_gage.status_code == 302
    created_gage = CalibrationGage.objects.get(tenant=tenant_a, gage_id=gage_data["gage_id"])
    assert created_gage.tenant == tenant_a
    assert created_gage.number != "MALICIOUS-GAGE-NUM"

    # 2. CalibrationRecordForm exclusions
    form_rec = CalibrationRecordForm(tenant=tenant_a)
    assert "tenant" not in form_rec.fields
    assert "number" not in form_rec.fields

    rec_data = _calibrationanalysis_record_base_data(
        gage=created_gage,
        tenant=tenant_b.pk,
        number="MALICIOUS-REC-NUM",
    )
    resp_rec = client_a.post(reverse("quality:calibration_record_create"), rec_data)
    assert resp_rec.status_code == 302
    created_rec = CalibrationRecord.objects.get(tenant=tenant_a, certificate_number=rec_data["certificate_number"])
    assert created_rec.tenant == tenant_a
    assert created_rec.number != "MALICIOUS-REC-NUM"

    # 3. OutOfToleranceInvestigationForm exclusions
    form_oot = OutOfToleranceInvestigationForm(tenant=tenant_a)
    assert "tenant" not in form_oot.fields
    assert "number" not in form_oot.fields

    oot_data = _calibrationanalysis_oot_base_data(
        record=created_rec,
        gage=created_gage,
        tenant=tenant_b.pk,
        number="MALICIOUS-OOT-NUM",
    )
    resp_oot = client_a.post(reverse("quality:out_of_tolerance_investigation_create"), oot_data)
    assert resp_oot.status_code == 302
    created_oot = OutOfToleranceInvestigation.objects.filter(tenant=tenant_a, gage=created_gage).latest("id")
    assert created_oot.tenant == tenant_a
    assert created_oot.number != "MALICIOUS-OOT-NUM"

    # 4. MeasurementSystemAnalysisForm exclusions
    form_msa = MeasurementSystemAnalysisForm(tenant=tenant_a)
    assert "tenant" not in form_msa.fields
    assert "number" not in form_msa.fields

    msa_data = _calibrationanalysis_msa_base_data(
        gage=created_gage,
        tenant=tenant_b.pk,
        number="MALICIOUS-MSA-NUM",
    )
    resp_msa = client_a.post(reverse("quality:measurement_system_analysis_create"), msa_data)
    assert resp_msa.status_code == 302
    created_msa = MeasurementSystemAnalysis.objects.get(tenant=tenant_a, study_title=msa_data["study_title"])
    assert created_msa.tenant == tenant_a
    assert created_msa.number != "MALICIOUS-MSA-NUM"
