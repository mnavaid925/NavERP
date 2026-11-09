"""Unit and validation tests for Module 11.7 Asset Reliability & Condition Monitoring forms."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.assets.forms import (
    AssetConditionAssessmentForm,
    AssetTelemetryReadingForm,
    AssetFailureModeForm,
    AssetCalibrationRecordForm,
)
from apps.assets.forms._common import reject_foreign
from apps.assets.models import (
    AssetConditionAssessment,
    AssetTelemetryReading,
    AssetFailureMode,
    AssetCalibrationRecord,
)
from apps.core.models import Document


# ---------------------------------------------------------------------------
# Test Helpers & Payload Factories
# ---------------------------------------------------------------------------

def _asset_reliability_forms_condition_payload(fixed_asset=None, operational_asset=None, category=None, inspector=None, vendor=None, **overrides):
    today = timezone.now().date()
    payload = {
        "title": "Ultrasonic Testing on Main Spindle Housing",
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "operational_asset": str(operational_asset.pk) if operational_asset else "",
        "asset_category": str(category.pk) if category else "",
        "inspector": str(inspector.pk) if inspector else "",
        "external_inspector": str(vendor.pk) if vendor else "",
        "assessment_date": today.strftime("%Y-%m-%d"),
        "assessment_type": "ndt_ultrasonic",
        "condition_grade": "grade_2_good",
        "health_score": "85",
        "operating_status": "normal_operation",
        "checklist_summary": "1. Visual shell check\n2. Ultrasonic thickness measurement\n3. Vibration sweep",
        "findings": "Minor surface wear detected. Shell thickness within allowable tolerance limits (14.8mm vs 15.0mm nominal).",
        "recommendations": "Continue normal operation; re-measure during next scheduled annual turnaround.",
        "followup_required": False,
    }
    payload.update(overrides)
    return payload


def _asset_reliability_forms_telemetry_payload(fixed_asset=None, operational_asset=None, user=None, **overrides):
    now = timezone.now()
    payload = {
        "sensor_identifier": "VIB-CNC-01-RADIAL",
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "operational_asset": str(operational_asset.pk) if operational_asset else "",
        "recorded_by": str(user.pk) if user else "",
        "recorded_at": now.strftime("%Y-%m-%dT%H:%M"),
        "source": "iot_sensor",
        "metric_type": "vibration_velocity_rms",
        "metric_unit": "mm_per_s",
        "reading_value": "4.2500",
        "baseline_value": "3.5000",
        "is_anomaly": False,
        "anomaly_confidence": "15.00",
        "alert_notes": "Telemetry sampled during normal steady-state machining run.",
    }
    payload.update(overrides)
    return payload


def _asset_reliability_forms_failure_mode_payload(fixed_asset=None, operational_asset=None, category=None, schedule=None, user=None, **overrides):
    payload = {
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "operational_asset": str(operational_asset.pk) if operational_asset else "",
        "asset_category": str(category.pk) if category else "",
        "component_subsystem": "Main Spindle Bearings",
        "function_description": "Support high-speed rotational drive shaft with minimal radial runout under cutting load.",
        "functional_failure": "Excessive bearing friction and vibration resulting in spindle lockup.",
        "failure_mode": "Ceramic ball fatigue spalling and micro-brinelling",
        "failure_cause": "Contamination ingress into bearing cartridge or inadequate grease lubrication.",
        "failure_effect": "Loss of workpiece concentricity, thermal expansion, complete machine shutdown.",
        "severity_score": 7,
        "occurrence_score": 4,
        "detection_score": 3,
        "rcm_strategy": "condition_based",
        "strategy_rationale": "High-frequency vibration accelerometer provides early warning before mechanical damage.",
        "mitigation_task": "Monthly FFT vibration analysis and bi-weekly bearing housing acoustic monitoring.",
        "linked_maintenance_schedule": str(schedule.pk) if schedule else "",
        "assessed_by": str(user.pk) if user else "",
    }
    payload.update(overrides)
    return payload


def _asset_reliability_forms_calibration_payload(fixed_asset=None, operational_asset=None, user=None, vendor=None, doc=None, **overrides):
    today = timezone.now().date()
    payload = {
        "instrument_tag": "PT-DISCHARGE-101",
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "operational_asset": str(operational_asset.pk) if operational_asset else "",
        "calibrated_by": str(user.pk) if user else "",
        "service_vendor": str(vendor.pk) if vendor else "",
        "calibration_date": today.strftime("%Y-%m-%d"),
        "calibration_frequency_days": 365,
        "next_due_date": (today + timedelta(days=365)).strftime("%Y-%m-%d"),
        "reference_standard_used": "Fluke 754 Documenting Process Calibrator (Traceable NIST #98124)",
        "traceability_certificate_no": "NIST-2026-PT-0914",
        "setpoint_nominal": "100.0000",
        "allowable_tolerance": "0.5000",
        "tolerance_unit": "psi",
        "as_found_reading": "99.8500",
        "as_left_reading": "100.0200",
        "calibration_result": "pass",
        "certificate_number": "CAL-CERT-2026-441",
        "certificate_expiry": (today + timedelta(days=365)).strftime("%Y-%m-%d"),
        "certificate_document": str(doc.pk) if doc else "",
        "notes": "Ambient conditions: 22°C, 45% RH. Zero and span verified per standard SOP.",
    }
    payload.update(overrides)
    return payload


# ==============================================================================
# 1. AssetConditionAssessmentForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_initialization(tenant_a):
    """AssetConditionAssessmentForm initializes cleanly with tenant and binds instance."""
    form = AssetConditionAssessmentForm(tenant=tenant_a)
    assert form.tenant == tenant_a
    assert form.instance.tenant == tenant_a
    assert form.fields["title"].widget.attrs.get("class") == "form-input"
    assert form.fields["fixed_asset"].widget.attrs.get("class") == "form-select"
    assert form.fields["findings"].widget.attrs.get("class") == "form-textarea"


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_field_exclusions(tenant_a):
    """System fields (tenant, number, status, reviewed_by, reviewed_at, triggered_maintenance_request) must NOT be present."""
    form = AssetConditionAssessmentForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "status",
        "reviewed_by",
        "reviewed_at",
        "triggered_maintenance_request",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Security violation: {field_name} must NOT be editable in form"


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_queryset_scoping(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    category_root_a,
    category_root_b,
    admin_user,
    admin_b,
    vendor_party_a,
    vendor_party_b,
):
    """ForeignKey querysets in AssetConditionAssessmentForm must only include the active tenant's records."""
    form = AssetConditionAssessmentForm(tenant=tenant_a)

    # FixedAsset scoping
    assert fixed_asset_a in form.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form.fields["fixed_asset"].queryset

    # Operational Asset scoping
    assert operational_asset_a in form.fields["operational_asset"].queryset
    assert operational_asset_b not in form.fields["operational_asset"].queryset

    # AssetCategory scoping
    assert category_root_a in form.fields["asset_category"].queryset
    assert category_root_b not in form.fields["asset_category"].queryset

    # Inspector (User) scoping
    assert admin_user in form.fields["inspector"].queryset
    assert admin_b not in form.fields["inspector"].queryset

    # External Inspector (Vendor Party) scoping
    assert vendor_party_a in form.fields["external_inspector"].queryset
    assert vendor_party_b not in form.fields["external_inspector"].queryset


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_valid_submit_and_save(
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    admin_user,
    vendor_party_a,
):
    """Submitting valid assessment data passes validation and saves model instance with auto-generated number."""
    data = _asset_reliability_forms_condition_payload(
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        category=category_root_a,
        inspector=admin_user,
        vendor=vendor_party_a,
        health_score="92",
        condition_grade="grade_1_excellent",
        operating_status="normal_operation",
        followup_required=True,
    )
    form = AssetConditionAssessmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("ACAS-")
    assert instance.title == "Ultrasonic Testing on Main Spindle Housing"
    assert instance.health_score == 92
    assert instance.condition_grade == "grade_1_excellent"
    assert instance.operating_status == "normal_operation"
    assert instance.followup_required is True
    assert instance.fixed_asset == fixed_asset_a
    assert instance.operational_asset == operational_asset_a
    assert instance.asset_category == category_root_a
    assert instance.inspector == admin_user
    assert instance.external_inspector == vendor_party_a


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_minimal_valid(tenant_a):
    """AssetConditionAssessmentForm validates successfully with minimal required fields (without optional FKs/notes)."""
    data = {
        "title": "Minimal Visual Survey",
        "assessment_date": timezone.now().date().strftime("%Y-%m-%d"),
        "assessment_type": "visual_inspection",
        "condition_grade": "grade_2_good",
        "health_score": 85,
        "operating_status": "normal_operation",
        "findings": "External casing free of structural cracks or fluid leaks.",
    }
    form = AssetConditionAssessmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("ACAS-")
    assert instance.health_score == 85
    assert instance.condition_grade == "grade_2_good"
    assert instance.fixed_asset is None
    assert instance.operational_asset is None
    assert instance.inspector is None
    assert instance.external_inspector is None
    assert instance.checklist_summary == ""
    assert instance.recommendations == ""


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_rejects_foreign_fixed_asset(tenant_a, fixed_asset_b):
    """Form rejects fixed_asset foreign key from another tenant."""
    data = _asset_reliability_forms_condition_payload(fixed_asset=fixed_asset_b)
    form = AssetConditionAssessmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_rejects_foreign_operational_asset(tenant_a, operational_asset_b):
    """Form rejects operational_asset foreign key from another tenant."""
    data = _asset_reliability_forms_condition_payload(operational_asset=operational_asset_b)
    form = AssetConditionAssessmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operational_asset" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_rejects_foreign_asset_category(tenant_a, category_root_b):
    """Form rejects asset_category foreign key from another tenant."""
    data = _asset_reliability_forms_condition_payload(category=category_root_b)
    form = AssetConditionAssessmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset_category" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_rejects_foreign_inspector(tenant_a, admin_b):
    """Form rejects inspector foreign key from another tenant."""
    data = _asset_reliability_forms_condition_payload(inspector=admin_b)
    form = AssetConditionAssessmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspector" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_rejects_foreign_external_inspector(tenant_a, vendor_party_b):
    """Form rejects external_inspector vendor foreign key from another tenant."""
    data = _asset_reliability_forms_condition_payload(vendor=vendor_party_b)
    form = AssetConditionAssessmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "external_inspector" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_clean_reject_foreign_direct(
    tenant_a,
    fixed_asset_b,
    operational_asset_b,
    category_root_b,
    admin_b,
    vendor_party_b,
):
    """Defense-in-depth: reject_foreign() helper explicitly tags workspace boundary violations."""
    form = AssetConditionAssessmentForm(tenant=tenant_a)
    cleaned_data = {
        "fixed_asset": fixed_asset_b,
        "operational_asset": operational_asset_b,
        "asset_category": category_root_b,
        "inspector": admin_b,
        "external_inspector": vendor_party_b,
    }
    form.cleaned_data = cleaned_data
    reject_foreign(form, cleaned_data, ["fixed_asset", "operational_asset", "asset_category", "inspector", "external_inspector"])
    for fld in ["fixed_asset", "operational_asset", "asset_category", "inspector", "external_inspector"]:
        assert fld in form.errors
        assert "That record belongs to another workspace." in form.errors[fld]


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_missing_required_fields(tenant_a):
    """Form requires title and findings fields."""
    form = AssetConditionAssessmentForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "findings" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_health_score_boundaries(tenant_a):
    """AssetConditionAssessmentForm rejects out-of-bounds health scores (<0 or >100) or non-numeric input."""
    # Negative score
    form_neg = AssetConditionAssessmentForm(
        data=_asset_reliability_forms_condition_payload(health_score="-5"),
        tenant=tenant_a,
    )
    assert not form_neg.is_valid()
    assert "health_score" in form_neg.errors

    # Over 100 score
    form_high = AssetConditionAssessmentForm(
        data=_asset_reliability_forms_condition_payload(health_score="105"),
        tenant=tenant_a,
    )
    assert not form_high.is_valid()
    assert "health_score" in form_high.errors

    # Non-numeric string
    form_str = AssetConditionAssessmentForm(
        data=_asset_reliability_forms_condition_payload(health_score="excellent"),
        tenant=tenant_a,
    )
    assert not form_str.is_valid()
    assert "health_score" in form_str.errors


@pytest.mark.django_db
def test_asset_reliability_forms_condition_assessment_invalid_choices(tenant_a):
    """Form rejects invalid choice values for assessment_type, condition_grade, operating_status."""
    form = AssetConditionAssessmentForm(
        data=_asset_reliability_forms_condition_payload(
            assessment_type="magic_wand_scan",
            condition_grade="grade_99",
            operating_status="blown_up",
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "assessment_type" in form.errors
    assert "condition_grade" in form.errors
    assert "operating_status" in form.errors


# ==============================================================================
# 2. AssetTelemetryReadingForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_initialization(tenant_a):
    """AssetTelemetryReadingForm initializes cleanly with tenant."""
    form = AssetTelemetryReadingForm(tenant=tenant_a)
    assert form.tenant == tenant_a
    assert form.instance.tenant == tenant_a
    assert form.fields["sensor_identifier"].widget.attrs.get("class") == "form-input"
    assert form.fields["reading_value"].widget.attrs.get("class") == "form-input"
    assert form.fields["is_anomaly"].widget.attrs.get("class") == "form-checkbox"


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_field_exclusions(tenant_a):
    """System and derived telemetry fields (tenant, number, deviation_percentage, threshold_status) must NOT be in form."""
    form = AssetTelemetryReadingForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "deviation_percentage",
        "threshold_status",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Security violation: {field_name} must NOT be editable in form"


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_queryset_scoping(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    admin_user,
    admin_b,
):
    """ForeignKeys on AssetTelemetryReadingForm must be scoped to the active tenant."""
    form = AssetTelemetryReadingForm(tenant=tenant_a)

    # FixedAsset scoping
    assert fixed_asset_a in form.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form.fields["fixed_asset"].queryset

    # Operational Asset scoping
    assert operational_asset_a in form.fields["operational_asset"].queryset
    assert operational_asset_b not in form.fields["operational_asset"].queryset

    # User scoping
    assert admin_user in form.fields["recorded_by"].queryset
    assert admin_b not in form.fields["recorded_by"].queryset


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_valid_submit_and_save(
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    admin_user,
):
    """Valid telemetry submission passes validation and computes deviation upon save."""
    data = _asset_reliability_forms_telemetry_payload(
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        user=admin_user,
        reading_value="5.2500",
        baseline_value="3.5000",
        is_anomaly=True,
        anomaly_confidence="88.50",
    )
    form = AssetTelemetryReadingForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("ATEL-")
    assert instance.sensor_identifier == "VIB-CNC-01-RADIAL"
    assert instance.reading_value == Decimal("5.2500")
    assert instance.baseline_value == Decimal("3.5000")
    assert instance.is_anomaly is True
    assert instance.anomaly_confidence == Decimal("88.50")
    # Derived fields calculated in model save
    assert instance.deviation_percentage == Decimal("50.00")
    assert instance.threshold_status == "anomaly_detected"


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_minimal_valid(tenant_a):
    """Form validates with only required reading fields (without optional FKs/notes/baseline)."""
    now = timezone.now()
    data = {
        "recorded_at": now.strftime("%Y-%m-%dT%H:%M"),
        "source": "iot_sensor",
        "metric_type": "vibration_velocity_rms",
        "metric_unit": "mm_per_s",
        "reading_value": "18.5000",
    }
    form = AssetTelemetryReadingForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("ATEL-")
    assert instance.reading_value == Decimal("18.5000")
    assert instance.source == "iot_sensor"
    assert instance.metric_type == "vibration_velocity_rms"
    assert instance.metric_unit == "mm_per_s"
    assert instance.fixed_asset is None
    assert instance.operational_asset is None
    assert instance.recorded_by is None


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_rejects_foreign_fixed_asset(tenant_a, fixed_asset_b):
    """Form rejects fixed_asset belonging to another tenant."""
    data = _asset_reliability_forms_telemetry_payload(fixed_asset=fixed_asset_b)
    form = AssetTelemetryReadingForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_rejects_foreign_operational_asset(tenant_a, operational_asset_b):
    """Form rejects operational_asset belonging to another tenant."""
    data = _asset_reliability_forms_telemetry_payload(operational_asset=operational_asset_b)
    form = AssetTelemetryReadingForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operational_asset" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_rejects_foreign_recorded_by(tenant_a, admin_b):
    """Form rejects recorded_by user belonging to another tenant."""
    data = _asset_reliability_forms_telemetry_payload(user=admin_b)
    form = AssetTelemetryReadingForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "recorded_by" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_clean_reject_foreign_direct(tenant_a, fixed_asset_b, operational_asset_b, admin_b):
    """Direct reject_foreign validation tags foreign items on AssetTelemetryReadingForm."""
    form = AssetTelemetryReadingForm(tenant=tenant_a)
    cleaned_data = {
        "fixed_asset": fixed_asset_b,
        "operational_asset": operational_asset_b,
        "recorded_by": admin_b,
    }
    form.cleaned_data = cleaned_data
    reject_foreign(form, cleaned_data, ["fixed_asset", "operational_asset", "recorded_by"])
    for fld in ["fixed_asset", "operational_asset", "recorded_by"]:
        assert fld in form.errors
        assert "That record belongs to another workspace." in form.errors[fld]


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_missing_reading_value(tenant_a):
    """Form requires reading_value."""
    form = AssetTelemetryReadingForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "reading_value" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_invalid_numerics(tenant_a):
    """Form rejects non-numeric inputs in numeric fields."""
    form = AssetTelemetryReadingForm(
        data=_asset_reliability_forms_telemetry_payload(
            reading_value="not_a_number",
            baseline_value="invalid_baseline",
            anomaly_confidence="super_confident",
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "reading_value" in form.errors
    assert "baseline_value" in form.errors
    assert "anomaly_confidence" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_anomaly_confidence_bounds(tenant_a):
    """Form rejects anomaly confidence < 0 or > 100."""
    form_neg = AssetTelemetryReadingForm(
        data=_asset_reliability_forms_telemetry_payload(anomaly_confidence="-1.50"),
        tenant=tenant_a,
    )
    assert not form_neg.is_valid()
    assert "anomaly_confidence" in form_neg.errors

    form_high = AssetTelemetryReadingForm(
        data=_asset_reliability_forms_telemetry_payload(anomaly_confidence="105.00"),
        tenant=tenant_a,
    )
    assert not form_high.is_valid()
    assert "anomaly_confidence" in form_high.errors


@pytest.mark.django_db
def test_asset_reliability_forms_telemetry_reading_invalid_choices(tenant_a):
    """Form rejects invalid choices for source, metric_type, metric_unit."""
    form = AssetTelemetryReadingForm(
        data=_asset_reliability_forms_telemetry_payload(
            source="alien_radio",
            metric_type="quantum_flux",
            metric_unit="lightyears",
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "source" in form.errors
    assert "metric_type" in form.errors
    assert "metric_unit" in form.errors


# ==============================================================================
# 3. AssetFailureModeForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_initialization(tenant_a):
    """AssetFailureModeForm initializes cleanly with tenant."""
    form = AssetFailureModeForm(tenant=tenant_a)
    assert form.tenant == tenant_a
    assert form.instance.tenant == tenant_a
    assert form.fields["component_subsystem"].widget.attrs.get("class") == "form-input"
    assert form.fields["functional_failure"].widget.attrs.get("class") == "form-input"
    assert form.fields["severity_score"].widget.attrs.get("class") == "form-input"


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_field_exclusions(tenant_a):
    """System fields (tenant, number, rpn, risk_level) AND status must NOT be present in AssetFailureModeForm."""
    form = AssetFailureModeForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "rpn",
        "risk_level",
        "status",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Security violation: {field_name} must NOT be editable in form"


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_queryset_scoping(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    category_root_a,
    category_root_b,
    maintenance_schedule_a,
    maintenance_schedule_b,
    admin_user,
    admin_b,
):
    """ForeignKeys on AssetFailureModeForm must be scoped to the active tenant."""
    form = AssetFailureModeForm(tenant=tenant_a)

    # FixedAsset scoping
    assert fixed_asset_a in form.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form.fields["fixed_asset"].queryset

    # Operational Asset scoping
    assert operational_asset_a in form.fields["operational_asset"].queryset
    assert operational_asset_b not in form.fields["operational_asset"].queryset

    # AssetCategory scoping
    assert category_root_a in form.fields["asset_category"].queryset
    assert category_root_b not in form.fields["asset_category"].queryset

    # Maintenance Schedule scoping
    assert maintenance_schedule_a in form.fields["linked_maintenance_schedule"].queryset
    assert maintenance_schedule_b not in form.fields["linked_maintenance_schedule"].queryset

    # User scoping
    assert admin_user in form.fields["assessed_by"].queryset
    assert admin_b not in form.fields["assessed_by"].queryset


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_valid_submit_and_save(
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    maintenance_schedule_a,
    admin_user,
):
    """Submitting valid failure mode form data saves instance and calculates RPN and risk_level."""
    data = _asset_reliability_forms_failure_mode_payload(
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        category=category_root_a,
        schedule=maintenance_schedule_a,
        user=admin_user,
        severity_score=8,
        occurrence_score=5,
        detection_score=6,
        rcm_strategy="condition_based",
    )
    form = AssetFailureModeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("AFMA-")
    assert instance.component_subsystem == "Main Spindle Bearings"
    assert instance.severity_score == 8
    assert instance.occurrence_score == 5
    assert instance.detection_score == 6
    # 8 * 5 * 6 = 240 -> Medium Risk (100 - 250)
    assert instance.rpn == 240
    assert instance.risk_level == "medium"
    assert instance.status == "active"  # Default in model


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_minimal_valid(tenant_a):
    """AssetFailureModeForm validates with only required narrative fields and score/strategy fields (without optional FKs/notes)."""
    data = {
        "component_subsystem": "Cooling Fan Cowl",
        "function_description": "Direct ambient airflow over compressor fins",
        "functional_failure": "Airflow reduced or obstructed",
        "failure_mode": "Debris accumulation on intake screen",
        "failure_cause": "Dust buildup from ambient foundry air",
        "failure_effect": "Elevated compressor oil operating temperature",
        "severity_score": 4,
        "occurrence_score": 5,
        "detection_score": 2,
        "rcm_strategy": "condition_based",
    }
    form = AssetFailureModeForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("AFMA-")
    # 4 * 5 * 2 = 40 -> Low Risk (< 100)
    assert instance.rpn == 40
    assert instance.risk_level == "low"
    assert instance.fixed_asset is None
    assert instance.operational_asset is None
    assert instance.asset_category is None
    assert instance.linked_maintenance_schedule is None
    assert instance.assessed_by is None


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_rejects_foreign_fixed_asset(tenant_a, fixed_asset_b):
    """Form rejects fixed_asset from another tenant."""
    data = _asset_reliability_forms_failure_mode_payload(fixed_asset=fixed_asset_b)
    form = AssetFailureModeForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_rejects_foreign_operational_asset(tenant_a, operational_asset_b):
    """Form rejects operational_asset from another tenant."""
    data = _asset_reliability_forms_failure_mode_payload(operational_asset=operational_asset_b)
    form = AssetFailureModeForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operational_asset" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_rejects_foreign_asset_category(tenant_a, category_root_b):
    """Form rejects asset_category from another tenant."""
    data = _asset_reliability_forms_failure_mode_payload(category=category_root_b)
    form = AssetFailureModeForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset_category" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_rejects_foreign_maintenance_schedule(tenant_a, maintenance_schedule_b):
    """Form rejects linked_maintenance_schedule from another tenant."""
    data = _asset_reliability_forms_failure_mode_payload(schedule=maintenance_schedule_b)
    form = AssetFailureModeForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "linked_maintenance_schedule" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_rejects_foreign_assessed_by(tenant_a, admin_b):
    """Form rejects assessed_by user from another tenant."""
    data = _asset_reliability_forms_failure_mode_payload(user=admin_b)
    form = AssetFailureModeForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "assessed_by" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_clean_reject_foreign_direct(
    tenant_a,
    fixed_asset_b,
    operational_asset_b,
    category_root_b,
    maintenance_schedule_b,
    admin_b,
):
    """Direct reject_foreign validation tags foreign items on AssetFailureModeForm."""
    form = AssetFailureModeForm(tenant=tenant_a)
    cleaned_data = {
        "fixed_asset": fixed_asset_b,
        "operational_asset": operational_asset_b,
        "asset_category": category_root_b,
        "linked_maintenance_schedule": maintenance_schedule_b,
        "assessed_by": admin_b,
    }
    form.cleaned_data = cleaned_data
    reject_foreign(form, cleaned_data, ["fixed_asset", "operational_asset", "asset_category", "linked_maintenance_schedule", "assessed_by"])
    for fld in ["fixed_asset", "operational_asset", "asset_category", "linked_maintenance_schedule", "assessed_by"]:
        assert fld in form.errors
        assert "That record belongs to another workspace." in form.errors[fld]


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_missing_required_fields(tenant_a):
    """Form requires component_subsystem, function_description, functional_failure, failure_mode, failure_cause, failure_effect."""
    form = AssetFailureModeForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    required = [
        "component_subsystem",
        "function_description",
        "functional_failure",
        "failure_mode",
        "failure_cause",
        "failure_effect",
    ]
    for fld in required:
        assert fld in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_score_boundaries(tenant_a):
    """Form rejects severity, occurrence, and detection scores out of 1-10 range."""
    # Severity < 1
    form_s0 = AssetFailureModeForm(
        data=_asset_reliability_forms_failure_mode_payload(severity_score=0),
        tenant=tenant_a,
    )
    assert not form_s0.is_valid()
    assert "severity_score" in form_s0.errors

    # Severity > 10
    form_s11 = AssetFailureModeForm(
        data=_asset_reliability_forms_failure_mode_payload(severity_score=11),
        tenant=tenant_a,
    )
    assert not form_s11.is_valid()
    assert "severity_score" in form_s11.errors

    # Occurrence < 1
    form_o0 = AssetFailureModeForm(
        data=_asset_reliability_forms_failure_mode_payload(occurrence_score=0),
        tenant=tenant_a,
    )
    assert not form_o0.is_valid()
    assert "occurrence_score" in form_o0.errors

    # Occurrence > 10
    form_o15 = AssetFailureModeForm(
        data=_asset_reliability_forms_failure_mode_payload(occurrence_score=15),
        tenant=tenant_a,
    )
    assert not form_o15.is_valid()
    assert "occurrence_score" in form_o15.errors

    # Detection < 1
    form_d0 = AssetFailureModeForm(
        data=_asset_reliability_forms_failure_mode_payload(detection_score=0),
        tenant=tenant_a,
    )
    assert not form_d0.is_valid()
    assert "detection_score" in form_d0.errors

    # Detection > 10
    form_d20 = AssetFailureModeForm(
        data=_asset_reliability_forms_failure_mode_payload(detection_score=20),
        tenant=tenant_a,
    )
    assert not form_d20.is_valid()
    assert "detection_score" in form_d20.errors


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_invalid_score_types(tenant_a):
    """Form rejects non-numeric input for scores."""
    form = AssetFailureModeForm(
        data=_asset_reliability_forms_failure_mode_payload(
            severity_score="critical",
            occurrence_score="often",
            detection_score="hard",
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "severity_score" in form.errors
    assert "occurrence_score" in form.errors
    assert "detection_score" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_failure_mode_invalid_rcm_strategy(tenant_a):
    """Form rejects invalid rcm_strategy choice."""
    form = AssetFailureModeForm(
        data=_asset_reliability_forms_failure_mode_payload(rcm_strategy="do_nothing_at_all"),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "rcm_strategy" in form.errors


# ==============================================================================
# 4. AssetCalibrationRecordForm Tests
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_initialization(tenant_a):
    """AssetCalibrationRecordForm initializes cleanly with tenant."""
    form = AssetCalibrationRecordForm(tenant=tenant_a)
    assert form.tenant == tenant_a
    assert form.instance.tenant == tenant_a
    assert form.fields["instrument_tag"].widget.attrs.get("class") == "form-input"
    assert form.fields["calibration_result"].widget.attrs.get("class") == "form-select"
    assert form.fields["setpoint_nominal"].widget.attrs.get("class") == "form-input"


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_field_exclusions(tenant_a):
    """System and derived calibration fields (tenant, number, as_found_error, as_left_error, status) must NOT be in form."""
    form = AssetCalibrationRecordForm(tenant=tenant_a)
    forbidden_fields = [
        "tenant",
        "number",
        "as_found_error",
        "as_left_error",
        "status",
    ]
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"Security violation: {field_name} must NOT be editable in form"


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_queryset_scoping(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    admin_user,
    admin_b,
    vendor_party_a,
    vendor_party_b,
):
    """ForeignKeys on AssetCalibrationRecordForm must be scoped to the active tenant."""
    doc_a = Document.objects.create(tenant=tenant_a, name="Cert A", file="documents/cert_a.pdf")
    doc_b = Document.objects.create(tenant=tenant_b, name="Cert B", file="documents/cert_b.pdf")

    form = AssetCalibrationRecordForm(tenant=tenant_a)

    # FixedAsset scoping
    assert fixed_asset_a in form.fields["fixed_asset"].queryset
    assert fixed_asset_b not in form.fields["fixed_asset"].queryset

    # Operational Asset scoping
    assert operational_asset_a in form.fields["operational_asset"].queryset
    assert operational_asset_b not in form.fields["operational_asset"].queryset

    # User scoping
    assert admin_user in form.fields["calibrated_by"].queryset
    assert admin_b not in form.fields["calibrated_by"].queryset

    # Vendor scoping
    assert vendor_party_a in form.fields["service_vendor"].queryset
    assert vendor_party_b not in form.fields["service_vendor"].queryset

    # Certificate document scoping
    assert doc_a in form.fields["certificate_document"].queryset
    assert doc_b not in form.fields["certificate_document"].queryset


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_valid_submit_and_save(
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    admin_user,
    vendor_party_a,
):
    """Submitting valid calibration form data saves instance and calculates errors and status."""
    doc_a = Document.objects.create(tenant=tenant_a, name="Fluke Metrology Cert", file="documents/cal_cert.pdf")
    today = timezone.now().date()
    data = _asset_reliability_forms_calibration_payload(
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        user=admin_user,
        vendor=vendor_party_a,
        doc=doc_a,
        setpoint_nominal="100.0000",
        as_found_reading="99.7000",
        as_left_reading="100.0500",
        allowable_tolerance="0.5000",
        calibration_result="pass",
    )
    form = AssetCalibrationRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("ACAL-")
    assert instance.instrument_tag == "PT-DISCHARGE-101"
    assert instance.setpoint_nominal == Decimal("100.0000")
    assert instance.as_found_reading == Decimal("99.7000")
    assert instance.as_left_reading == Decimal("100.0500")
    assert instance.allowable_tolerance == Decimal("0.5000")
    # Derived error calculations
    assert instance.as_found_error == Decimal("-0.3000")
    assert instance.as_left_error == Decimal("0.0500")
    assert instance.status == "valid"
    assert instance.certificate_document == doc_a


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_minimal_valid(tenant_a):
    """AssetCalibrationRecordForm validates with only required metrological fields (without optional FKs/notes/certificate)."""
    today = timezone.now().date()
    data = {
        "instrument_tag": "FLOW-MTR-01",
        "calibration_date": today.strftime("%Y-%m-%d"),
        "calibration_frequency_days": 365,
        "next_due_date": (today + timedelta(days=180)).strftime("%Y-%m-%d"),
        "reference_standard_used": "Micro Motion Coriolis Master Meter #MM-881",
        "setpoint_nominal": "50.0000",
        "allowable_tolerance": "0.5000",
        "tolerance_unit": "percent_span",
        "as_found_reading": "49.9500",
        "as_left_reading": "50.0000",
        "calibration_result": "pass",
    }
    form = AssetCalibrationRecordForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.number.startswith("ACAL-")
    assert instance.tolerance_unit == "percent_span"
    assert instance.calibration_frequency_days == 365
    assert instance.as_found_error == Decimal("-0.0500")
    assert instance.as_left_error == Decimal("0.0000")
    assert instance.status == "valid"
    assert instance.fixed_asset is None
    assert instance.operational_asset is None
    assert instance.calibrated_by is None
    assert instance.service_vendor is None
    assert instance.certificate_document is None


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_rejects_foreign_fixed_asset(tenant_a, fixed_asset_b):
    """Form rejects fixed_asset belonging to another tenant."""
    data = _asset_reliability_forms_calibration_payload(fixed_asset=fixed_asset_b)
    form = AssetCalibrationRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_rejects_foreign_operational_asset(tenant_a, operational_asset_b):
    """Form rejects operational_asset belonging to another tenant."""
    data = _asset_reliability_forms_calibration_payload(operational_asset=operational_asset_b)
    form = AssetCalibrationRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operational_asset" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_rejects_foreign_calibrated_by(tenant_a, admin_b):
    """Form rejects calibrated_by user belonging to another tenant."""
    data = _asset_reliability_forms_calibration_payload(user=admin_b)
    form = AssetCalibrationRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "calibrated_by" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_rejects_foreign_service_vendor(tenant_a, vendor_party_b):
    """Form rejects service_vendor belonging to another tenant."""
    data = _asset_reliability_forms_calibration_payload(vendor=vendor_party_b)
    form = AssetCalibrationRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "service_vendor" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_rejects_foreign_certificate_document(tenant_a, tenant_b):
    """Form rejects certificate_document belonging to another tenant."""
    doc_b = Document.objects.create(tenant=tenant_b, name="Globex Cert", file="documents/globex_cal.pdf")
    data = _asset_reliability_forms_calibration_payload(doc=doc_b)
    form = AssetCalibrationRecordForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "certificate_document" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_clean_reject_foreign_direct(
    tenant_a,
    tenant_b,
    fixed_asset_b,
    operational_asset_b,
    admin_b,
    vendor_party_b,
):
    """Direct reject_foreign validation tags foreign items on AssetCalibrationRecordForm."""
    doc_b = Document.objects.create(tenant=tenant_b, name="Foreign Cert", file="documents/f.pdf")
    form = AssetCalibrationRecordForm(tenant=tenant_a)
    cleaned_data = {
        "fixed_asset": fixed_asset_b,
        "operational_asset": operational_asset_b,
        "calibrated_by": admin_b,
        "service_vendor": vendor_party_b,
        "certificate_document": doc_b,
    }
    form.cleaned_data = cleaned_data
    reject_foreign(form, cleaned_data, ["fixed_asset", "operational_asset", "calibrated_by", "service_vendor", "certificate_document"])
    for fld in ["fixed_asset", "operational_asset", "calibrated_by", "service_vendor", "certificate_document"]:
        assert fld in form.errors
        assert "That record belongs to another workspace." in form.errors[fld]


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_missing_required_fields(tenant_a):
    """Form requires instrument_tag, reference_standard_used, setpoint_nominal, as_found_reading, as_left_reading, next_due_date."""
    form = AssetCalibrationRecordForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    required = [
        "instrument_tag",
        "reference_standard_used",
        "setpoint_nominal",
        "as_found_reading",
        "as_left_reading",
        "next_due_date",
    ]
    for fld in required:
        assert fld in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_invalid_numerics(tenant_a):
    """Form rejects non-numeric strings in numeric fields."""
    form = AssetCalibrationRecordForm(
        data=_asset_reliability_forms_calibration_payload(
            setpoint_nominal="hundred",
            allowable_tolerance="half",
            as_found_reading="approx_99",
            as_left_reading="exact_100",
            calibration_frequency_days="annual",
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "setpoint_nominal" in form.errors
    assert "allowable_tolerance" in form.errors
    assert "as_found_reading" in form.errors
    assert "as_left_reading" in form.errors
    assert "calibration_frequency_days" in form.errors


@pytest.mark.django_db
def test_asset_reliability_forms_calibration_record_invalid_choices(tenant_a):
    """Form rejects invalid choices for tolerance_unit and calibration_result."""
    form = AssetCalibrationRecordForm(
        data=_asset_reliability_forms_calibration_payload(
            tolerance_unit="lightyears",
            calibration_result="maybe_passed",
        ),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "tolerance_unit" in form.errors
    assert "calibration_result" in form.errors
