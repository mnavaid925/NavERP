"""Unit and validation tests for Module 12.10 Calibration & Measurement System Analysis (MSA) forms.

Covers all 4 forms:
- CalibrationGageForm
- CalibrationRecordForm
- OutOfToleranceInvestigationForm
- MeasurementSystemAnalysisForm

Naming conventions:
- Every test function: test_calibrationanalysis_forms_*
- Every module-level helper: _calibrationanalysis_*
"""
from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.models import OrgUnit, Party
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


def _calibrationanalysis_create_work_center(tenant, code=None, name=None):
    """Create a minimal WorkCenter instance for testing tenant foreign key scoping."""
    uid = uuid.uuid4().hex[:6]
    return WorkCenter.objects.create(
        tenant=tenant,
        code=code or f"WC-{uid}",
        name=name or f"Machining Cell {uid}",
    )


def _calibrationanalysis_create_asset(tenant, code=None, name=None):
    """Create a minimal Asset instance for testing tenant foreign key scoping."""
    uid = uuid.uuid4().hex[:6]
    return Asset.objects.create(
        tenant=tenant,
        code=code or f"AST-{uid}",
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
        "gage_id": f"GAG-TST-{uid}",
        "name": f"Digital Micrometer 0-25mm {uid}",
        "gage_type": "caliper_micrometer",
        "criticality": "major",
        "status": "active_in_service",
        "manufacturer": "Mitutoyo",
        "model_number": "293-240-30",
        "serial_number": f"SN-{uid}",
        "measurement_range": "0 - 25 mm",
        "resolution": "0.001 mm",
        "accuracy_spec": "+/- 0.001 mm",
        "max_permissible_error": "0.0020",
        "engineering_unit": "mm",
        "is_reference_standard": False,
        "nist_traceability_number": "NIST-TEST-2026-001",
        "reference_standard_parent": "",
        "asset_link": "",
        "work_center": "",
        "department": "",
        "custodian": "",
        "storage_location": "Tool Crib Shelf B-12",
        "calibration_interval_days": 180,
        "last_calibration_date": _calibrationanalysis_date(-30),
        "next_calibration_due": _calibrationanalysis_date(150),
        "sop_document": "",
        "notes": "Standard inspection tool for turning operations.",
    }
    data.update(extra)
    return data


def _calibrationanalysis_record_base_data(gage, **extra):
    """Build valid baseline POST dictionary for CalibrationRecordForm."""
    data = {
        "gage": _calibrationanalysis_pk(gage),
        "calibration_date": _calibrationanalysis_date(-2),
        "calibration_type": "internal_metrology",
        "status": "completed",
        "service_vendor": "",
        "certificate_number": "CERT-2026-TEST-01",
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
        "standard_traceability_notes": "Calibrated against Grade 0 gauge block set.",
        "technician_name": "Senior Metrologist",
        "calibrated_by_user": "",
        "approved_by": "",
        "notes": "Routine scheduled calibration completed.",
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
        "bias_percentage": "0.20",
        "linearity_slope": "0.0010",
        "linearity_r_squared": "0.9850",
        "study_result": "acceptable",
        "study_protocol_doc": "",
        "study_lead": "",
        "approved_by": "",
        "conclusion": "Measurement system is capable for process monitoring.",
        "notes": "Conducted per AIAG MSA Reference Manual 4th Edition.",
    }
    data.update(extra)
    return data


# =============================================================================
# 1. CalibrationGageForm Tests
# =============================================================================

def test_calibrationanalysis_forms_gage_init_unbound_no_tenant():
    """Verify CalibrationGageForm initializes cleanly without a tenant provided."""
    form = CalibrationGageForm()
    assert form.tenant is None
    assert "gage_id" in form.fields
    assert "name" in form.fields
    assert "calibration_interval_days" in form.fields


def test_calibrationanalysis_forms_gage_system_field_exclusions(tenant_a):
    """Verify system fields (tenant, number, last_calibration_result, created_at, updated_at) are excluded."""
    form = CalibrationGageForm(tenant=tenant_a)
    excluded_fields = ["tenant", "number", "last_calibration_result", "created_at", "updated_at"]
    for field_name in excluded_fields:
        assert field_name not in form.fields, f"{field_name} must be excluded from CalibrationGageForm"

    # Attempting to post system fields must be ignored and not bypass auto-numbering
    payload = _calibrationanalysis_gage_base_data(
        tenant=tenant_a.pk,
        number="QGAG-INJECTED-9999",
        last_calibration_result="fail_out_of_tolerance",
        created_at=_calibrationanalysis_date(-10),
    )
    bound_form = CalibrationGageForm(data=payload, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=True)
    assert instance.tenant == tenant_a
    assert instance.number != "QGAG-INJECTED-9999"
    assert instance.number.startswith("QGAG-")
    assert instance.last_calibration_result == ""


def test_calibrationanalysis_forms_gage_tenant_scoping_dropdowns(
    tenant_a,
    tenant_b,
    cal_standard_a,
    cal_standard_b,
    quality_department,
    quality_department_b,
    admin_user,
    admin_b,
    doc_a,
    doc_b,
):
    """Verify all foreign key querysets are scoped to tenant and reference standard rules."""
    regular_gage_a = CalibrationGage.objects.create(
        tenant=tenant_a,
        gage_id="GAG-NON-REF-01",
        name="Working Shop Caliper",
        is_reference_standard=False,
    )
    wc_a = _calibrationanalysis_create_work_center(tenant_a)
    wc_b = _calibrationanalysis_create_work_center(tenant_b)
    ast_a = _calibrationanalysis_create_asset(tenant_a)
    ast_b = _calibrationanalysis_create_asset(tenant_b)

    form = CalibrationGageForm(tenant=tenant_a)

    # reference_standard_parent: must only include tenant_a reference standards
    parent_qs = form.fields["reference_standard_parent"].queryset
    assert cal_standard_a in parent_qs
    assert cal_standard_b not in parent_qs
    assert regular_gage_a not in parent_qs, "Non-reference standards must not be in parent queryset"

    # department: scoped to tenant_a
    dept_qs = form.fields["department"].queryset
    assert quality_department in dept_qs
    assert quality_department_b not in dept_qs

    # custodian: scoped to tenant_a users
    custodian_qs = form.fields["custodian"].queryset
    assert admin_user in custodian_qs
    assert admin_b not in custodian_qs

    # sop_document: scoped to tenant_a controlled documents
    sop_qs = form.fields["sop_document"].queryset
    assert doc_a in sop_qs
    assert doc_b not in sop_qs

    # work_center and asset_link: scoped to tenant_a
    wc_qs = form.fields["work_center"].queryset
    assert wc_a in wc_qs
    assert wc_b not in wc_qs

    ast_qs = form.fields["asset_link"].queryset
    assert ast_a in ast_qs
    assert ast_b not in ast_qs


def test_calibrationanalysis_forms_gage_self_parenting_prevention_queryset(tenant_a, cal_standard_a):
    """Verify an existing gage is excluded from its own reference_standard_parent queryset on edit."""
    other_standard = _calibrationanalysis_create_standard(tenant_a, gage_id="GAG-REF-OTHER")
    form = CalibrationGageForm(instance=cal_standard_a, tenant=tenant_a)
    parent_qs = form.fields["reference_standard_parent"].queryset

    assert cal_standard_a not in parent_qs, "Gage instance must be excluded from its own parent queryset"
    assert other_standard in parent_qs


def test_calibrationanalysis_forms_gage_self_parenting_prevention_clean(tenant_a, cal_standard_a):
    """Verify clean() prevents setting reference_standard_parent to the same instance."""
    # Direct clean() method validation
    form_direct = CalibrationGageForm(instance=cal_standard_a, tenant=tenant_a)
    form_direct.cleaned_data = {"reference_standard_parent": cal_standard_a}
    form_direct.clean()
    assert "reference_standard_parent" in form_direct.errors
    assert "A gage cannot be its own reference standard parent." in form_direct.errors["reference_standard_parent"]

    # Bound form rejects selection because instance is excluded from queryset
    payload = _calibrationanalysis_gage_base_data(
        gage_id=cal_standard_a.gage_id,
        name=cal_standard_a.name,
        reference_standard_parent=cal_standard_a.pk,
    )
    form_bound = CalibrationGageForm(data=payload, instance=cal_standard_a, tenant=tenant_a)
    assert not form_bound.is_valid()
    assert "reference_standard_parent" in form_bound.errors
    assert any("not one of the available choices" in e for e in form_bound.errors["reference_standard_parent"])


def test_calibrationanalysis_forms_gage_clean_interval_validation_zero_and_negative(tenant_a):
    """Verify calibration_interval_days must be strictly greater than zero."""
    # Zero interval triggers clean() validation
    data_zero = _calibrationanalysis_gage_base_data(calibration_interval_days=0)
    form_zero = CalibrationGageForm(data=data_zero, tenant=tenant_a)
    assert not form_zero.is_valid()
    assert "calibration_interval_days" in form_zero.errors
    assert "Interval must be greater than zero." in form_zero.errors["calibration_interval_days"]

    # Negative interval caught by PositiveIntegerField min_value=0
    data_neg = _calibrationanalysis_gage_base_data(calibration_interval_days=-30)
    form_neg = CalibrationGageForm(data=data_neg, tenant=tenant_a)
    assert not form_neg.is_valid()
    assert "calibration_interval_days" in form_neg.errors
    assert any("greater than or equal to 0" in e for e in form_neg.errors["calibration_interval_days"])

    # Direct clean() check for negative value
    form_direct = CalibrationGageForm(tenant=tenant_a)
    form_direct.cleaned_data = {"calibration_interval_days": -10}
    form_direct.clean()
    assert "calibration_interval_days" in form_direct.errors
    assert "Interval must be greater than zero." in form_direct.errors["calibration_interval_days"]

    # Positive interval passes
    data_pos = _calibrationanalysis_gage_base_data(calibration_interval_days=365)
    form_pos = CalibrationGageForm(data=data_pos, tenant=tenant_a)
    assert form_pos.is_valid(), form_pos.errors


def test_calibrationanalysis_forms_gage_reject_foreign_tenants_direct(
    tenant_a, tenant_b, cal_standard_b, quality_department_b, admin_b, doc_b
):
    """Directly verify reject_foreign raises workspace error for foreign relations."""
    wc_b = _calibrationanalysis_create_work_center(tenant_b)
    ast_b = _calibrationanalysis_create_asset(tenant_b)

    form = CalibrationGageForm(tenant=tenant_a)
    form.cleaned_data = {
        "reference_standard_parent": cal_standard_b,
        "asset_link": ast_b,
        "work_center": wc_b,
        "department": quality_department_b,
        "custodian": admin_b,
        "sop_document": doc_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["reference_standard_parent", "asset_link", "work_center", "department", "custodian", "sop_document"],
    )
    for field_name in ["reference_standard_parent", "asset_link", "work_center", "department", "custodian", "sop_document"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


def test_calibrationanalysis_forms_gage_reject_foreign_tenants_bound(tenant_a, tenant_b, cal_standard_b):
    """Verify bound form rejects foreign tenant PKs submitted in POST payload."""
    payload = _calibrationanalysis_gage_base_data(reference_standard_parent=cal_standard_b.pk)
    form = CalibrationGageForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "reference_standard_parent" in form.errors


def test_calibrationanalysis_forms_gage_valid_submission_create_and_update(
    tenant_a, cal_standard_a, admin_user, quality_department, doc_a
):
    """Verify valid form submission succeeds with commit=False and commit=True, and updates instance."""
    wc_a = _calibrationanalysis_create_work_center(tenant_a)
    ast_a = _calibrationanalysis_create_asset(tenant_a)

    payload = _calibrationanalysis_gage_base_data(
        gage_id="GAG-NEW-001",
        name="High-Precision Bore Gage",
        reference_standard_parent=cal_standard_a.pk,
        asset_link=ast_a.pk,
        work_center=wc_a.pk,
        department=quality_department.pk,
        custodian=admin_user.pk,
        sop_document=doc_a.pk,
        calibration_interval_days=90,
    )
    form = CalibrationGageForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    # commit=False test
    obj = form.save(commit=False)
    assert obj.tenant == tenant_a
    assert obj.gage_id == "GAG-NEW-001"
    assert obj.reference_standard_parent == cal_standard_a
    obj.save()

    # Verify database persistence
    saved = CalibrationGage.objects.get(pk=obj.pk)
    assert saved.number.startswith("QGAG-")
    assert saved.work_center == wc_a
    assert saved.sop_document == doc_a

    # Update existing instance
    update_payload = _calibrationanalysis_gage_base_data(
        gage_id="GAG-NEW-001",
        name="Updated Bore Gage 50-100mm",
        calibration_interval_days=180,
    )
    edit_form = CalibrationGageForm(data=update_payload, instance=saved, tenant=tenant_a)
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save(commit=True)
    assert updated.pk == saved.pk
    assert updated.name == "Updated Bore Gage 50-100mm"
    assert updated.calibration_interval_days == 180


def test_calibrationanalysis_forms_gage_field_validations_max_length(tenant_a):
    """Verify max length validations on CharField attributes."""
    payload_long_id = _calibrationanalysis_gage_base_data(gage_id="G" * 65)
    form_long_id = CalibrationGageForm(data=payload_long_id, tenant=tenant_a)
    assert not form_long_id.is_valid()
    assert "gage_id" in form_long_id.errors

    payload_long_name = _calibrationanalysis_gage_base_data(name="N" * 151)
    form_long_name = CalibrationGageForm(data=payload_long_name, tenant=tenant_a)
    assert not form_long_name.is_valid()
    assert "name" in form_long_name.errors

    payload_long_loc = _calibrationanalysis_gage_base_data(storage_location="L" * 121)
    form_long_loc = CalibrationGageForm(data=payload_long_loc, tenant=tenant_a)
    assert not form_long_loc.is_valid()
    assert "storage_location" in form_long_loc.errors


def test_calibrationanalysis_forms_gage_decimal_precision(tenant_a):
    """Verify max_permissible_error handles 4-decimal precision properly."""
    payload = _calibrationanalysis_gage_base_data(max_permissible_error="0.0025")
    form = CalibrationGageForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    assert instance.max_permissible_error == Decimal("0.0025")

    # Non-decimal invalid input
    payload_invalid = _calibrationanalysis_gage_base_data(max_permissible_error="not-a-number")
    form_invalid = CalibrationGageForm(data=payload_invalid, tenant=tenant_a)
    assert not form_invalid.is_valid()
    assert "max_permissible_error" in form_invalid.errors


def test_calibrationanalysis_forms_gage_choices_validation(tenant_a):
    """Verify choices on gage_type, criticality, and status."""
    payload_invalid = _calibrationanalysis_gage_base_data(
        gage_type="laser_scanner_unsupported",
        criticality="urgent_non_choice",
        status="demolished_unknown",
    )
    form = CalibrationGageForm(data=payload_invalid, tenant=tenant_a)
    assert not form.is_valid()
    assert "gage_type" in form.errors
    assert "criticality" in form.errors
    assert "status" in form.errors


def test_calibrationanalysis_forms_gage_tenant_unique_constraint(tenant_a, cal_gage_a):
    """Verify TenantUniqueMixin enforces unique gage_id per workspace."""
    payload = _calibrationanalysis_gage_base_data(
        gage_id=cal_gage_a.gage_id,
        name="Duplicate Gage in Tenant A",
    )
    form = CalibrationGageForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "__all__" in form.errors
    assert any("already exists" in str(err) for err in form.errors["__all__"])


# =============================================================================
# 2. CalibrationRecordForm Tests
# =============================================================================

def test_calibrationanalysis_forms_record_init_unbound_no_tenant():
    """Verify CalibrationRecordForm initializes cleanly when tenant is None."""
    form = CalibrationRecordForm()
    assert form.tenant is None
    assert "gage" in form.fields
    assert "calibration_date" in form.fields
    assert "standards_used" in form.fields


def test_calibrationanalysis_forms_record_system_field_exclusions(tenant_a, cal_gage_a):
    """Verify tenant, number, approved_at, test_points_data, created_at, updated_at are excluded."""
    form = CalibrationRecordForm(tenant=tenant_a)
    forbidden_fields = ["tenant", "number", "approved_at", "test_points_data", "created_at", "updated_at"]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"{field_name} must be excluded from CalibrationRecordForm"

    # Injected system parameters must not take effect
    payload = _calibrationanalysis_record_base_data(
        gage=cal_gage_a,
        tenant=tenant_a.pk,
        number="QCAL-HACKED-9999",
        approved_at=timezone.now().isoformat(),
        test_points_data=[{"nominal": 10.0, "error": 0.001}],
    )
    bound_form = CalibrationRecordForm(data=payload, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=True)
    assert instance.tenant == tenant_a
    assert instance.number != "QCAL-HACKED-9999"
    assert instance.number.startswith("QCAL-")
    assert instance.approved_at is None
    assert instance.test_points_data == []


def test_calibrationanalysis_forms_record_future_date_validation(tenant_a, cal_gage_a):
    """Verify calibration_date cannot be in the future."""
    # Future date triggers validation error
    future_date = _calibrationanalysis_date(1)
    payload_future = _calibrationanalysis_record_base_data(gage=cal_gage_a, calibration_date=future_date)
    form_future = CalibrationRecordForm(data=payload_future, tenant=tenant_a)
    assert not form_future.is_valid()
    assert "calibration_date" in form_future.errors
    assert "Calibration date cannot be in the future." in form_future.errors["calibration_date"]

    # Today's date is valid
    today_date = _calibrationanalysis_date(0)
    payload_today = _calibrationanalysis_record_base_data(gage=cal_gage_a, calibration_date=today_date)
    form_today = CalibrationRecordForm(data=payload_today, tenant=tenant_a)
    assert form_today.is_valid(), form_today.errors

    # Past date is valid
    past_date = _calibrationanalysis_date(-15)
    payload_past = _calibrationanalysis_record_base_data(gage=cal_gage_a, calibration_date=past_date)
    form_past = CalibrationRecordForm(data=payload_past, tenant=tenant_a)
    assert form_past.is_valid(), form_past.errors


def test_calibrationanalysis_forms_record_self_calibration_prevention(tenant_a, cal_standard_a):
    """Verify an instrument cannot be used as its own calibration reference standard."""
    payload = _calibrationanalysis_record_base_data(
        gage=cal_standard_a,
        standards_used=[cal_standard_a.pk],
    )
    form = CalibrationRecordForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "standards_used" in form.errors
    assert "A gage cannot be used as its own calibration reference standard." in form.errors["standards_used"]


def test_calibrationanalysis_forms_record_standards_used_queryset_scoping(
    tenant_a, tenant_b, cal_standard_a, cal_standard_b, cal_gage_a
):
    """Verify standards_used is strictly limited to tenant standards where is_reference_standard=True."""
    other_standard_a = _calibrationanalysis_create_standard(tenant_a, gage_id="GAG-REF-OTHER-02")
    form = CalibrationRecordForm(tenant=tenant_a)
    standards_qs = form.fields["standards_used"].queryset

    assert cal_standard_a in standards_qs
    assert other_standard_a in standards_qs
    assert cal_standard_b not in standards_qs, "Cross-tenant reference standards must be excluded"
    assert cal_gage_a not in standards_qs, "Non-reference standards must not appear in standards_used"


def test_calibrationanalysis_forms_record_tenant_scoping_other_fks(
    tenant_a, tenant_b, cal_gage_a, cal_gage_b, cal_vendor_a, cal_vendor_b, admin_user, admin_b
):
    """Verify gage, service_vendor, calibrated_by_user, and approved_by are scoped to tenant."""
    form = CalibrationRecordForm(tenant=tenant_a)

    # gage
    gage_qs = form.fields["gage"].queryset
    assert cal_gage_a in gage_qs
    assert cal_gage_b not in gage_qs

    # service_vendor
    vendor_qs = form.fields["service_vendor"].queryset
    assert cal_vendor_a in vendor_qs
    assert cal_vendor_b not in vendor_qs

    # users
    cal_by_qs = form.fields["calibrated_by_user"].queryset
    appr_by_qs = form.fields["approved_by"].queryset
    assert admin_user in cal_by_qs
    assert admin_b not in cal_by_qs
    assert admin_user in appr_by_qs
    assert admin_b not in appr_by_qs


def test_calibrationanalysis_forms_record_reject_foreign_tenants_direct(
    tenant_a, tenant_b, cal_gage_b, cal_vendor_b, cal_standard_b, admin_b
):
    """Directly verify reject_foreign raises workspace error on CalibrationRecord foreign relations."""
    form = CalibrationRecordForm(tenant=tenant_a)
    form.cleaned_data = {
        "gage": cal_gage_b,
        "service_vendor": cal_vendor_b,
        "standards_used": [cal_standard_b],
        "calibrated_by_user": admin_b,
        "approved_by": admin_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["gage", "service_vendor", "standards_used", "calibrated_by_user", "approved_by"],
    )
    for field_name in ["gage", "service_vendor", "standards_used", "calibrated_by_user", "approved_by"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


def test_calibrationanalysis_forms_record_reject_foreign_tenants_bound(tenant_a, tenant_b, cal_gage_b):
    """Verify bound CalibrationRecordForm rejects foreign gage PK submitted in POST payload."""
    payload = _calibrationanalysis_record_base_data(gage=cal_gage_b.pk)
    form = CalibrationRecordForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "gage" in form.errors


def test_calibrationanalysis_forms_record_valid_submission_create_and_m2m(
    tenant_a, cal_gage_a, cal_standard_a, cal_vendor_a, admin_user
):
    """Verify valid form submission saves record and properly handles ManyToMany standards_used."""
    payload = _calibrationanalysis_record_base_data(
        gage=cal_gage_a,
        service_vendor=cal_vendor_a.pk,
        standards_used=[cal_standard_a.pk],
        calibrated_by_user=admin_user.pk,
        approved_by=admin_user.pk,
        expanded_uncertainty="0.0015",
        test_uncertainty_ratio="4.50",
    )
    form = CalibrationRecordForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    record = form.save(commit=False)
    assert record.tenant == tenant_a
    assert record.gage == cal_gage_a
    assert record.service_vendor == cal_vendor_a
    record.save()
    form.save_m2m()

    saved = CalibrationRecord.objects.get(pk=record.pk)
    assert saved.number.startswith("QCAL-")
    assert cal_standard_a in saved.standards_used.all()
    assert saved.expanded_uncertainty == Decimal("0.0015")
    assert saved.test_uncertainty_ratio == Decimal("4.50")


def test_calibrationanalysis_forms_record_choice_fields_and_decimals(tenant_a, cal_gage_a):
    """Verify choices on calibration_type, conditions, overall_result, and numeric decimals."""
    payload_invalid = _calibrationanalysis_record_base_data(
        gage=cal_gage_a,
        calibration_type="unknown_cal_method",
        as_found_condition="broken_unrecognized",
        overall_result="maybe_passed",
    )
    form = CalibrationRecordForm(data=payload_invalid, tenant=tenant_a)
    assert not form.is_valid()
    assert "calibration_type" in form.errors
    assert "as_found_condition" in form.errors
    assert "overall_result" in form.errors

    # Valid decimal precision
    payload_valid = _calibrationanalysis_record_base_data(
        gage=cal_gage_a,
        ambient_temperature_c="21.50",
        ambient_relative_humidity="48.20",
        expanded_uncertainty="0.0003",
        test_uncertainty_ratio="5.25",
        max_observed_error="0.0008",
    )
    form_valid = CalibrationRecordForm(data=payload_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_calibrationanalysis_forms_record_optional_fields_blank(tenant_a, cal_gage_a):
    """Verify CalibrationRecordForm succeeds when all optional fields are blank."""
    payload_minimal = {
        "gage": cal_gage_a.pk,
        "calibration_date": _calibrationanalysis_date(-1),
        "calibration_type": "internal_metrology",
        "status": "completed",
        "service_vendor": "",
        "certificate_number": "",
        "as_found_condition": "in_tolerance",
        "as_left_condition": "in_tolerance",
        "overall_result": "pass",
        "ambient_temperature_c": "20.00",
        "ambient_relative_humidity": "45.00",
        "expanded_uncertainty": "0.0020",
        "test_uncertainty_ratio": "4.00",
        "max_observed_error": "0.0050",
        "guardband_applied": True,
        "standards_used": [],
        "standard_traceability_notes": "",
        "technician_name": "",
        "calibrated_by_user": "",
        "approved_by": "",
        "notes": "",
    }
    form = CalibrationRecordForm(data=payload_minimal, tenant=tenant_a)
    assert form.is_valid(), form.errors


# =============================================================================
# 3. OutOfToleranceInvestigationForm Tests
# =============================================================================

def test_calibrationanalysis_forms_oot_init_unbound_no_tenant():
    """Verify OutOfToleranceInvestigationForm initializes cleanly without a tenant."""
    form = OutOfToleranceInvestigationForm()
    assert form.tenant is None
    assert "calibration_record" in form.fields
    assert "gage" in form.fields
    assert "suspect_window_start" in form.fields


def test_calibrationanalysis_forms_oot_system_field_exclusions(tenant_a, cal_gage_a, cal_record_oot_a):
    """Verify tenant, number, created_at, updated_at are excluded from form fields."""
    form = OutOfToleranceInvestigationForm(tenant=tenant_a)
    forbidden = ["tenant", "number", "created_at", "updated_at"]
    for field_name in forbidden:
        assert field_name not in form.fields, f"{field_name} must be excluded from OutOfToleranceInvestigationForm"

    # Injected system fields in payload are ignored
    payload = _calibrationanalysis_oot_base_data(
        record=cal_record_oot_a,
        gage=cal_gage_a,
        tenant=tenant_a.pk,
        number="QOOT-HACKED-9999",
        created_at=_calibrationanalysis_date(-5),
    )
    bound_form = OutOfToleranceInvestigationForm(data=payload, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=True)
    assert instance.tenant == tenant_a
    assert instance.number != "QOOT-HACKED-9999"
    assert instance.number.startswith("QOOT-")


def test_calibrationanalysis_forms_oot_cross_record_integrity(tenant_a, cal_gage_a, cal_record_oot_a):
    """Verify clean() enforces calibration_record.gage_id == gage.pk."""
    # Create another gage in tenant_a
    gage_two = CalibrationGage.objects.create(
        tenant=tenant_a,
        gage_id="GAG-DIG-MISMATCH",
        name="Mismatched Secondary Gage",
    )
    # cal_record_oot_a is linked to cal_gage_a; setting gage=gage_two must fail cross-integrity check
    payload_mismatch = _calibrationanalysis_oot_base_data(
        record=cal_record_oot_a,
        gage=gage_two,
    )
    form_mismatch = OutOfToleranceInvestigationForm(data=payload_mismatch, tenant=tenant_a)
    assert not form_mismatch.is_valid()
    assert "calibration_record" in form_mismatch.errors
    assert "Calibration record does not belong to the selected gage." in form_mismatch.errors["calibration_record"]

    # Matching gage and calibration_record succeeds
    payload_match = _calibrationanalysis_oot_base_data(
        record=cal_record_oot_a,
        gage=cal_gage_a,
    )
    form_match = OutOfToleranceInvestigationForm(data=payload_match, tenant=tenant_a)
    assert form_match.is_valid(), form_match.errors


def test_calibrationanalysis_forms_oot_date_validation_suspect_window(tenant_a, cal_gage_a, cal_record_oot_a):
    """Verify suspect_window_start cannot be after suspect_window_end date."""
    # Start after End triggers validation error
    payload_invalid = _calibrationanalysis_oot_base_data(
        record=cal_record_oot_a,
        gage=cal_gage_a,
        suspect_window_start=_calibrationanalysis_date(5),
        suspect_window_end=_calibrationanalysis_date(0),
    )
    form_invalid = OutOfToleranceInvestigationForm(data=payload_invalid, tenant=tenant_a)
    assert not form_invalid.is_valid()
    assert "suspect_window_start" in form_invalid.errors
    assert "Suspect window start cannot be after end date." in form_invalid.errors["suspect_window_start"]

    # Start equal to End is valid (same day discovery)
    payload_same_day = _calibrationanalysis_oot_base_data(
        record=cal_record_oot_a,
        gage=cal_gage_a,
        suspect_window_start=_calibrationanalysis_date(-1),
        suspect_window_end=_calibrationanalysis_date(-1),
    )
    form_same_day = OutOfToleranceInvestigationForm(data=payload_same_day, tenant=tenant_a)
    assert form_same_day.is_valid(), form_same_day.errors

    # Start before End is valid
    payload_valid = _calibrationanalysis_oot_base_data(
        record=cal_record_oot_a,
        gage=cal_gage_a,
        suspect_window_start=_calibrationanalysis_date(-30),
        suspect_window_end=_calibrationanalysis_date(0),
    )
    form_valid = OutOfToleranceInvestigationForm(data=payload_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_calibrationanalysis_forms_oot_tenant_scoping_dropdowns(
    tenant_a,
    tenant_b,
    cal_gage_a,
    cal_gage_b,
    cal_record_oot_a,
    cal_record_b,
    ncr_a,
    ncr_b,
    capa_investigation_a,
    capa_investigation_b,
    admin_user,
    admin_b,
):
    """Verify all FK querysets are scoped to tenant in OutOfToleranceInvestigationForm."""
    wc_a = _calibrationanalysis_create_work_center(tenant_a)
    wc_b = _calibrationanalysis_create_work_center(tenant_b)

    form = OutOfToleranceInvestigationForm(tenant=tenant_a)

    assert cal_record_oot_a in form.fields["calibration_record"].queryset
    assert cal_record_b not in form.fields["calibration_record"].queryset

    assert cal_gage_a in form.fields["gage"].queryset
    assert cal_gage_b not in form.fields["gage"].queryset

    assert wc_a in form.fields["suspect_work_center"].queryset
    assert wc_b not in form.fields["suspect_work_center"].queryset

    assert ncr_a in form.fields["linked_ncr"].queryset
    assert ncr_b not in form.fields["linked_ncr"].queryset

    assert capa_investigation_a in form.fields["linked_capa"].queryset
    assert capa_investigation_b not in form.fields["linked_capa"].queryset

    assert admin_user in form.fields["investigator"].queryset
    assert admin_b not in form.fields["investigator"].queryset

    assert admin_user in form.fields["quality_approver"].queryset
    assert admin_b not in form.fields["quality_approver"].queryset


def test_calibrationanalysis_forms_oot_select_related_on_calibration_record(tenant_a):
    """Verify calibration_record queryset performs select_related('gage') for performance."""
    form = OutOfToleranceInvestigationForm(tenant=tenant_a)
    assert "gage" in form.fields["calibration_record"].queryset.query.select_related


def test_calibrationanalysis_forms_oot_reject_foreign_tenants_direct(
    tenant_a, tenant_b, cal_gage_b, cal_record_b, ncr_b, capa_investigation_b, admin_b
):
    """Directly verify reject_foreign raises workspace error on all OutOfToleranceInvestigation FKs."""
    wc_b = _calibrationanalysis_create_work_center(tenant_b)

    form = OutOfToleranceInvestigationForm(tenant=tenant_a)
    form.cleaned_data = {
        "calibration_record": cal_record_b,
        "gage": cal_gage_b,
        "suspect_work_center": wc_b,
        "linked_ncr": ncr_b,
        "linked_capa": capa_investigation_b,
        "investigator": admin_b,
        "quality_approver": admin_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["calibration_record", "gage", "suspect_work_center", "linked_ncr", "linked_capa", "investigator", "quality_approver"],
    )
    for field_name in ["calibration_record", "gage", "suspect_work_center", "linked_ncr", "linked_capa", "investigator", "quality_approver"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


def test_calibrationanalysis_forms_oot_reject_foreign_tenants_bound(tenant_a, tenant_b, cal_record_b):
    """Verify bound OutOfToleranceInvestigationForm rejects foreign calibration_record PK."""
    payload = _calibrationanalysis_oot_base_data(record=cal_record_b.pk, gage=cal_record_b.gage_id)
    form = OutOfToleranceInvestigationForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "calibration_record" in form.errors


def test_calibrationanalysis_forms_oot_valid_submission_create_and_update(
    tenant_a, cal_gage_a, cal_record_oot_a, ncr_a, capa_investigation_a, admin_user
):
    """Verify valid submission with commit=False and commit=True, and updating an existing instance."""
    wc_a = _calibrationanalysis_create_work_center(tenant_a)

    payload = _calibrationanalysis_oot_base_data(
        record=cal_record_oot_a,
        gage=cal_gage_a,
        suspect_work_center=wc_a.pk,
        linked_ncr=ncr_a.pk,
        linked_capa=capa_investigation_a.pk,
        investigator=admin_user.pk,
        quality_approver=admin_user.pk,
        suspect_lots_count=12,
        consumer_risk_rating=4,
        producer_risk_rating=2,
        product_disposition="re_inspect_inventory",
        customer_notification_required=True,
    )
    form = OutOfToleranceInvestigationForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    assert instance.tenant == tenant_a
    assert instance.gage == cal_gage_a
    assert instance.calibration_record == cal_record_oot_a
    instance.save()

    saved = OutOfToleranceInvestigation.objects.get(pk=instance.pk)
    assert saved.number.startswith("QOOT-")
    assert saved.suspect_work_center == wc_a
    assert saved.linked_ncr == ncr_a
    assert saved.customer_notification_required is True

    # Update existing instance
    update_payload = _calibrationanalysis_oot_base_data(
        record=cal_record_oot_a,
        gage=cal_gage_a,
        status="closed",
        closure_date=_calibrationanalysis_date(0),
        conclusion_summary="100% of suspect inventory re-inspected. Zero defective assemblies found.",
    )
    edit_form = OutOfToleranceInvestigationForm(data=update_payload, instance=saved, tenant=tenant_a)
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save(commit=True)
    assert updated.status == "closed"
    assert updated.closure_date == timezone.now().date()
    assert "100% of suspect inventory" in updated.conclusion_summary


def test_calibrationanalysis_forms_oot_field_validations_risk_ratings_and_choices(
    tenant_a, cal_gage_a, cal_record_oot_a
):
    """Verify choices on status, risk_level, product_disposition, and ratings bounds."""
    payload_invalid = _calibrationanalysis_oot_base_data(
        record=cal_record_oot_a,
        gage=cal_gage_a,
        status="non_existent_status",
        risk_level="extreme_danger_unknown",
        product_disposition="throw_into_river",
    )
    form = OutOfToleranceInvestigationForm(data=payload_invalid, tenant=tenant_a)
    assert not form.is_valid()
    assert "status" in form.errors
    assert "risk_level" in form.errors
    assert "product_disposition" in form.errors

    # Title max length
    payload_title = _calibrationanalysis_oot_base_data(
        record=cal_record_oot_a,
        gage=cal_gage_a,
        title="T" * 181,
    )
    form_title = OutOfToleranceInvestigationForm(data=payload_title, tenant=tenant_a)
    assert not form_title.is_valid()
    assert "title" in form_title.errors


# =============================================================================
# 4. MeasurementSystemAnalysisForm Tests
# =============================================================================

def test_calibrationanalysis_forms_msa_init_unbound_no_tenant():
    """Verify MeasurementSystemAnalysisForm initializes cleanly when tenant is None."""
    form = MeasurementSystemAnalysisForm()
    assert form.tenant is None
    assert "study_title" in form.fields
    assert "gage" in form.fields
    assert "number_of_operators" in form.fields


def test_calibrationanalysis_forms_msa_system_field_exclusions(tenant_a, cal_gage_a):
    """Verify tenant, number, raw_study_data, approved_at, created_at, updated_at are excluded."""
    form = MeasurementSystemAnalysisForm(tenant=tenant_a)
    forbidden = ["tenant", "number", "raw_study_data", "approved_at", "created_at", "updated_at"]
    for field_name in forbidden:
        assert field_name not in form.fields, f"{field_name} must be excluded from MeasurementSystemAnalysisForm"

    # Injected system parameters must be ignored
    payload = _calibrationanalysis_msa_base_data(
        gage=cal_gage_a,
        tenant=tenant_a.pk,
        number="QMSA-HACKED-9999",
        raw_study_data={"operators": 5},
        approved_at=timezone.now().isoformat(),
    )
    bound_form = MeasurementSystemAnalysisForm(data=payload, tenant=tenant_a)
    assert bound_form.is_valid(), bound_form.errors
    instance = bound_form.save(commit=True)
    assert instance.tenant == tenant_a
    assert instance.number != "QMSA-HACKED-9999"
    assert instance.number.startswith("QMSA-")
    assert instance.raw_study_data == {}
    assert instance.approved_at is None


def test_calibrationanalysis_forms_msa_positive_integers_validation_operators(tenant_a, cal_gage_a):
    """Verify number_of_operators must be at least 1."""
    # 0 operators triggers clean() validation
    payload_zero = _calibrationanalysis_msa_base_data(gage=cal_gage_a, number_of_operators=0)
    form_zero = MeasurementSystemAnalysisForm(data=payload_zero, tenant=tenant_a)
    assert not form_zero.is_valid()
    assert "number_of_operators" in form_zero.errors
    assert "Operators must be at least 1." in form_zero.errors["number_of_operators"]

    # Negative operators caught by PositiveIntegerField min_value=0
    payload_neg = _calibrationanalysis_msa_base_data(gage=cal_gage_a, number_of_operators=-2)
    form_neg = MeasurementSystemAnalysisForm(data=payload_neg, tenant=tenant_a)
    assert not form_neg.is_valid()
    assert "number_of_operators" in form_neg.errors
    assert any("greater than or equal to 0" in e for e in form_neg.errors["number_of_operators"])

    # Direct clean() check for negative value
    form_direct = MeasurementSystemAnalysisForm(tenant=tenant_a)
    form_direct.cleaned_data = {"number_of_operators": -1}
    form_direct.clean()
    assert "number_of_operators" in form_direct.errors
    assert "Operators must be at least 1." in form_direct.errors["number_of_operators"]

    # 1 or more passes
    payload_valid = _calibrationanalysis_msa_base_data(gage=cal_gage_a, number_of_operators=1)
    form_valid = MeasurementSystemAnalysisForm(data=payload_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_calibrationanalysis_forms_msa_positive_integers_validation_parts(tenant_a, cal_gage_a):
    """Verify number_of_parts must be at least 1."""
    # 0 parts triggers clean() validation
    payload_zero = _calibrationanalysis_msa_base_data(gage=cal_gage_a, number_of_parts=0)
    form_zero = MeasurementSystemAnalysisForm(data=payload_zero, tenant=tenant_a)
    assert not form_zero.is_valid()
    assert "number_of_parts" in form_zero.errors
    assert "Parts must be at least 1." in form_zero.errors["number_of_parts"]

    # Negative parts caught by PositiveIntegerField min_value=0
    payload_neg = _calibrationanalysis_msa_base_data(gage=cal_gage_a, number_of_parts=-5)
    form_neg = MeasurementSystemAnalysisForm(data=payload_neg, tenant=tenant_a)
    assert not form_neg.is_valid()
    assert "number_of_parts" in form_neg.errors
    assert any("greater than or equal to 0" in e for e in form_neg.errors["number_of_parts"])

    # Direct clean() check for negative value
    form_direct = MeasurementSystemAnalysisForm(tenant=tenant_a)
    form_direct.cleaned_data = {"number_of_parts": -5}
    form_direct.clean()
    assert "number_of_parts" in form_direct.errors
    assert "Parts must be at least 1." in form_direct.errors["number_of_parts"]

    # 10 parts passes
    payload_valid = _calibrationanalysis_msa_base_data(gage=cal_gage_a, number_of_parts=10)
    form_valid = MeasurementSystemAnalysisForm(data=payload_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_calibrationanalysis_forms_msa_positive_integers_validation_trials(tenant_a, cal_gage_a):
    """Verify number_of_trials must be at least 1."""
    # 0 trials triggers clean() validation
    payload_zero = _calibrationanalysis_msa_base_data(gage=cal_gage_a, number_of_trials=0)
    form_zero = MeasurementSystemAnalysisForm(data=payload_zero, tenant=tenant_a)
    assert not form_zero.is_valid()
    assert "number_of_trials" in form_zero.errors
    assert "Trials must be at least 1." in form_zero.errors["number_of_trials"]

    # Negative trials caught by PositiveIntegerField min_value=0
    payload_neg = _calibrationanalysis_msa_base_data(gage=cal_gage_a, number_of_trials=-1)
    form_neg = MeasurementSystemAnalysisForm(data=payload_neg, tenant=tenant_a)
    assert not form_neg.is_valid()
    assert "number_of_trials" in form_neg.errors
    assert any("greater than or equal to 0" in e for e in form_neg.errors["number_of_trials"])

    # Direct clean() check for negative value
    form_direct = MeasurementSystemAnalysisForm(tenant=tenant_a)
    form_direct.cleaned_data = {"number_of_trials": -1}
    form_direct.clean()
    assert "number_of_trials" in form_direct.errors
    assert "Trials must be at least 1." in form_direct.errors["number_of_trials"]

    # 3 trials passes
    payload_valid = _calibrationanalysis_msa_base_data(gage=cal_gage_a, number_of_trials=3)
    form_valid = MeasurementSystemAnalysisForm(data=payload_valid, tenant=tenant_a)
    assert form_valid.is_valid(), form_valid.errors


def test_calibrationanalysis_forms_msa_specification_tolerance_positive_validation(tenant_a, cal_gage_a):
    """Verify specification_tolerance must be strictly positive (> 0)."""
    # 0 tolerance triggers error
    payload_zero = _calibrationanalysis_msa_base_data(gage=cal_gage_a, specification_tolerance="0.0000")
    form_zero = MeasurementSystemAnalysisForm(data=payload_zero, tenant=tenant_a)
    assert not form_zero.is_valid()
    assert "specification_tolerance" in form_zero.errors
    assert "Specification tolerance must be positive." in form_zero.errors["specification_tolerance"]

    # Negative tolerance triggers error
    payload_neg = _calibrationanalysis_msa_base_data(gage=cal_gage_a, specification_tolerance="-0.0500")
    form_neg = MeasurementSystemAnalysisForm(data=payload_neg, tenant=tenant_a)
    assert not form_neg.is_valid()
    assert "specification_tolerance" in form_neg.errors
    assert "Specification tolerance must be positive." in form_neg.errors["specification_tolerance"]

    # Positive tolerance passes
    payload_pos = _calibrationanalysis_msa_base_data(gage=cal_gage_a, specification_tolerance="0.0500")
    form_pos = MeasurementSystemAnalysisForm(data=payload_pos, tenant=tenant_a)
    assert form_pos.is_valid(), form_pos.errors


def test_calibrationanalysis_forms_msa_tenant_scoping_dropdowns(
    tenant_a, tenant_b, cal_gage_a, cal_gage_b, doc_a, doc_b, admin_user, admin_b
):
    """Verify gage, study_protocol_doc, study_lead, and approved_by are scoped to tenant."""
    form = MeasurementSystemAnalysisForm(tenant=tenant_a)

    assert cal_gage_a in form.fields["gage"].queryset
    assert cal_gage_b not in form.fields["gage"].queryset

    assert doc_a in form.fields["study_protocol_doc"].queryset
    assert doc_b not in form.fields["study_protocol_doc"].queryset

    assert admin_user in form.fields["study_lead"].queryset
    assert admin_b not in form.fields["study_lead"].queryset

    assert admin_user in form.fields["approved_by"].queryset
    assert admin_b not in form.fields["approved_by"].queryset


def test_calibrationanalysis_forms_msa_reject_foreign_tenants_direct(
    tenant_a, tenant_b, cal_gage_b, doc_b, admin_b
):
    """Directly verify reject_foreign raises workspace error on MeasurementSystemAnalysis FKs."""
    form = MeasurementSystemAnalysisForm(tenant=tenant_a)
    form.cleaned_data = {
        "gage": cal_gage_b,
        "study_protocol_doc": doc_b,
        "study_lead": admin_b,
        "approved_by": admin_b,
    }
    reject_foreign(
        form,
        form.cleaned_data,
        ["gage", "study_protocol_doc", "study_lead", "approved_by"],
    )
    for field_name in ["gage", "study_protocol_doc", "study_lead", "approved_by"]:
        assert field_name in form.errors
        assert "That record belongs to another workspace." in str(form.errors[field_name])


def test_calibrationanalysis_forms_msa_reject_foreign_tenants_bound(tenant_a, tenant_b, cal_gage_b):
    """Verify bound MeasurementSystemAnalysisForm rejects foreign gage PK."""
    payload = _calibrationanalysis_msa_base_data(gage=cal_gage_b.pk)
    form = MeasurementSystemAnalysisForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "gage" in form.errors


def test_calibrationanalysis_forms_msa_valid_submission_create_and_update(
    tenant_a, cal_gage_a, doc_a, admin_user
):
    """Verify valid MSA form submission saves successfully and updates existing instance."""
    payload = _calibrationanalysis_msa_base_data(
        gage=cal_gage_a,
        study_protocol_doc=doc_a.pk,
        study_lead=admin_user.pk,
        approved_by=admin_user.pk,
        repeatability_ev="0.0018",
        reproducibility_av="0.0012",
        gage_rr_grr="0.0022",
        part_variation_pv="0.0152",
        total_variation_tv="0.0154",
        percent_gage_rr_study_variation="14.28",
        percent_tolerance_pt_ratio="22.00",
        number_of_distinct_categories_ndc="9.00",
        study_result="acceptable",
    )
    form = MeasurementSystemAnalysisForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    assert instance.tenant == tenant_a
    assert instance.gage == cal_gage_a
    assert instance.study_protocol_doc == doc_a
    instance.save()

    saved = MeasurementSystemAnalysis.objects.get(pk=instance.pk)
    assert saved.number.startswith("QMSA-")
    assert saved.gage_rr_grr == Decimal("0.0022")
    assert saved.study_lead == admin_user
    assert saved.study_result == "acceptable"

    # Update existing instance
    update_payload = _calibrationanalysis_msa_base_data(
        gage=cal_gage_a,
        status="approved",
        conclusion="Approved for ISO 9001:2015 production quality release.",
    )
    edit_form = MeasurementSystemAnalysisForm(data=update_payload, instance=saved, tenant=tenant_a)
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save(commit=True)
    assert updated.status == "approved"
    assert "Approved for ISO 9001:2015" in updated.conclusion


def test_calibrationanalysis_forms_msa_study_choices_and_decimals(tenant_a, cal_gage_a):
    """Verify choices on study_type, analysis_method, status, study_result, and decimal metrics."""
    payload_invalid = _calibrationanalysis_msa_base_data(
        gage=cal_gage_a,
        study_type="invalid_study_type",
        analysis_method="quantum_estimation",
        status="waiting_on_godot",
        study_result="miraculous",
    )
    form = MeasurementSystemAnalysisForm(data=payload_invalid, tenant=tenant_a)
    assert not form.is_valid()
    assert "study_type" in form.errors
    assert "analysis_method" in form.errors
    assert "status" in form.errors
    assert "study_result" in form.errors

    # Verify decimal handling on metrics
    payload_decimals = _calibrationanalysis_msa_base_data(
        gage=cal_gage_a,
        bias_value="0.0004",
        bias_percentage="0.40",
        linearity_slope="0.0012",
        linearity_r_squared="0.9912",
    )
    form_decimals = MeasurementSystemAnalysisForm(data=payload_decimals, tenant=tenant_a)
    assert form_decimals.is_valid(), form_decimals.errors
    instance = form_decimals.save(commit=False)
    assert instance.bias_value == Decimal("0.0004")
    assert instance.bias_percentage == Decimal("0.40")
    assert instance.linearity_slope == Decimal("0.0012")
    assert instance.linearity_r_squared == Decimal("0.9912")
