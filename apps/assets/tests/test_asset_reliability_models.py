"""Unit and invariant tests for Module 11.7 Asset Reliability & Condition Monitoring models."""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.assets.models import (
    AssetConditionAssessment,
    AssetTelemetryReading,
    AssetFailureMode,
    AssetCalibrationRecord,
)


# ==============================================================================
# 1. AssetConditionAssessment Model Tests
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_models_condition_assessment_str_and_numbering(condition_assessment_a):
    assert condition_assessment_a.number.startswith("ACAS-")
    assert "ACAS-" in str(condition_assessment_a)
    assert condition_assessment_a.title in str(condition_assessment_a)
    assert condition_assessment_a.status == "draft"


@pytest.mark.django_db
def test_asset_reliability_models_condition_assessment_defaults(tenant_a):
    assessment = AssetConditionAssessment.objects.create(
        tenant=tenant_a,
        title="Centrifugal Pump Baseline Inspection",
        findings="Impeller vanes intact; normal wear on mechanical packing.",
    )
    assert assessment.number.startswith("ACAS-")
    assert assessment.assessment_type == "visual_inspection"
    assert assessment.condition_grade == "grade_2_good"
    assert assessment.health_score == 85
    assert assessment.operating_status == "normal_operation"
    assert assessment.status == "completed"
    assert assessment.followup_required is False
    assert assessment.checklist_summary == ""
    assert assessment.recommendations == ""


@pytest.mark.django_db
def test_asset_reliability_models_condition_assessment_css_properties(condition_assessment_a):
    # Status CSS
    condition_assessment_a.status = "draft"
    assert condition_assessment_a.status_css == "badge-slate"
    condition_assessment_a.status = "completed"
    assert condition_assessment_a.status_css == "badge-info"
    condition_assessment_a.status = "reviewed"
    assert condition_assessment_a.status_css == "badge-green"
    condition_assessment_a.status = "archived"
    assert condition_assessment_a.status_css == "badge-muted"

    # Condition Grade CSS
    condition_assessment_a.condition_grade = "grade_1_excellent"
    assert condition_assessment_a.condition_grade_css == "badge-green"
    condition_assessment_a.condition_grade = "grade_2_good"
    assert condition_assessment_a.condition_grade_css == "badge-info"
    condition_assessment_a.condition_grade = "grade_3_fair"
    assert condition_assessment_a.condition_grade_css == "badge-amber"
    condition_assessment_a.condition_grade = "grade_4_poor"
    assert condition_assessment_a.condition_grade_css == "badge-red"
    condition_assessment_a.condition_grade = "grade_5_critical"
    assert condition_assessment_a.condition_grade_css == "badge-red"

    # Operating Status CSS
    condition_assessment_a.operating_status = "normal_operation"
    assert condition_assessment_a.operating_status_css == "badge-green"
    condition_assessment_a.operating_status = "operational_with_defects"
    assert condition_assessment_a.operating_status_css == "badge-amber"
    condition_assessment_a.operating_status = "reduced_capacity"
    assert condition_assessment_a.operating_status_css == "badge-amber"
    condition_assessment_a.operating_status = "quarantined_unsafe"
    assert condition_assessment_a.operating_status_css == "badge-red"
    condition_assessment_a.operating_status = "decommission_recommended"
    assert condition_assessment_a.operating_status_css == "badge-red"

    # Assessment Type CSS
    condition_assessment_a.assessment_type = "visual_inspection"
    assert condition_assessment_a.assessment_type_css == "badge-slate"
    condition_assessment_a.assessment_type = "ndt_ultrasonic"
    assert condition_assessment_a.assessment_type_css == "badge-info"
    condition_assessment_a.assessment_type = "ndt_thermography"
    assert condition_assessment_a.assessment_type_css == "badge-amber"
    condition_assessment_a.assessment_type = "ndt_dye_penetrant"
    assert condition_assessment_a.assessment_type_css == "badge-amber"


@pytest.mark.django_db
def test_asset_reliability_models_condition_assessment_health_score_validation(tenant_a):
    assessment_invalid_high = AssetConditionAssessment(
        tenant=tenant_a,
        title="Test Validation High",
        findings="Testing out of bounds health score",
        health_score=105,
    )
    with pytest.raises(ValidationError):
        assessment_invalid_high.full_clean()

    assessment_valid = AssetConditionAssessment(
        tenant=tenant_a,
        title="Test Validation Valid",
        findings="Testing valid health score",
        health_score=100,
    )
    assessment_valid.full_clean()  # should not raise


@pytest.mark.django_db
def test_asset_reliability_models_condition_assessment_unique_number(tenant_a, condition_assessment_a):
    with pytest.raises(IntegrityError):
        AssetConditionAssessment.objects.create(
            tenant=tenant_a,
            number=condition_assessment_a.number,
            title="Duplicate Number Collision",
            findings="Should trigger unique constraint violation.",
        )


# ==============================================================================
# 2. AssetTelemetryReading Model Tests
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_models_telemetry_reading_str_and_numbering(telemetry_reading_a):
    assert telemetry_reading_a.number.startswith("ATEL-")
    assert "ATEL-" in str(telemetry_reading_a)
    assert "Vibration Velocity RMS" in str(telemetry_reading_a)
    assert "4.2000 mm_per_s" in str(telemetry_reading_a)


@pytest.mark.django_db
def test_asset_reliability_models_telemetry_reading_defaults(tenant_a):
    reading = AssetTelemetryReading.objects.create(
        tenant=tenant_a,
        reading_value=Decimal("5.0000"),
    )
    assert reading.number.startswith("ATEL-")
    assert reading.source == "iot_sensor"
    assert reading.metric_type == "vibration_velocity_rms"
    assert reading.metric_unit == "mm_per_s"
    assert reading.threshold_status == "normal"
    assert reading.is_anomaly is False
    assert reading.deviation_percentage is None


@pytest.mark.django_db
def test_asset_reliability_models_telemetry_reading_deviation_normal(tenant_a):
    reading = AssetTelemetryReading(
        tenant=tenant_a,
        reading_value=Decimal("11.0000"),
        baseline_value=Decimal("10.0000"),
    )
    reading.save()
    reading.refresh_from_db()
    # (11 - 10) / 10 * 100 = 10.00%
    assert reading.deviation_percentage == Decimal("10.00")
    assert reading.threshold_status == "normal"
    assert reading.threshold_status_css == "badge-green"


@pytest.mark.django_db
def test_asset_reliability_models_telemetry_reading_deviation_warning(tenant_a):
    reading_pos = AssetTelemetryReading(
        tenant=tenant_a,
        reading_value=Decimal("13.0000"),
        baseline_value=Decimal("10.0000"),
    )
    reading_pos.save()
    reading_pos.refresh_from_db()
    # (13 - 10) / 10 * 100 = +30.00% (warning: >= 20% and < 50%)
    assert reading_pos.deviation_percentage == Decimal("30.00")
    assert reading_pos.threshold_status == "warning"
    assert reading_pos.threshold_status_css == "badge-amber"

    reading_neg = AssetTelemetryReading(
        tenant=tenant_a,
        reading_value=Decimal("7.5000"),
        baseline_value=Decimal("10.0000"),
    )
    reading_neg.save()
    reading_neg.refresh_from_db()
    # (7.5 - 10) / 10 * 100 = -25.00%
    assert reading_neg.deviation_percentage == Decimal("-25.00")
    assert reading_neg.threshold_status == "warning"


@pytest.mark.django_db
def test_asset_reliability_models_telemetry_reading_deviation_critical(tenant_a):
    reading = AssetTelemetryReading(
        tenant=tenant_a,
        reading_value=Decimal("16.0000"),
        baseline_value=Decimal("10.0000"),
    )
    reading.save()
    reading.refresh_from_db()
    # (16 - 10) / 10 * 100 = +60.00% (critical: >= 50%)
    assert reading.deviation_percentage == Decimal("60.00")
    assert reading.threshold_status == "critical"
    assert reading.threshold_status_css == "badge-red"


@pytest.mark.django_db
def test_asset_reliability_models_telemetry_reading_deviation_anomaly(tenant_a):
    reading = AssetTelemetryReading(
        tenant=tenant_a,
        reading_value=Decimal("10.5000"),
        baseline_value=Decimal("10.0000"),
        is_anomaly=True,
        anomaly_confidence=Decimal("94.50"),
    )
    reading.save()
    reading.refresh_from_db()
    assert reading.threshold_status == "anomaly_detected"
    assert reading.threshold_status_css == "badge-red"


@pytest.mark.django_db
def test_asset_reliability_models_telemetry_reading_zero_baseline(tenant_a):
    reading = AssetTelemetryReading(
        tenant=tenant_a,
        reading_value=Decimal("10.0000"),
        baseline_value=Decimal("0.0000"),
    )
    reading.save()
    reading.refresh_from_db()
    assert reading.deviation_percentage is None
    assert reading.threshold_status == "normal"


@pytest.mark.django_db
def test_asset_reliability_models_telemetry_reading_css_properties(telemetry_reading_a):
    telemetry_reading_a.source = "iot_sensor"
    assert telemetry_reading_a.source_css == "badge-info"
    telemetry_reading_a.source = "scada_historian"
    assert telemetry_reading_a.source_css == "badge-slate"
    telemetry_reading_a.source = "manual_gauge"
    assert telemetry_reading_a.source_css == "badge-muted"

    telemetry_reading_a.metric_type = "bearing_temperature"
    assert telemetry_reading_a.metric_type_css == "badge-red"
    telemetry_reading_a.metric_type = "vibration_velocity_rms"
    assert telemetry_reading_a.metric_type_css == "badge-amber"
    telemetry_reading_a.metric_type = "operating_pressure"
    assert telemetry_reading_a.metric_type_css == "badge-info"


@pytest.mark.django_db
def test_asset_reliability_models_telemetry_reading_anomaly_confidence_validation(tenant_a):
    reading = AssetTelemetryReading(
        tenant=tenant_a,
        reading_value=Decimal("12.0000"),
        is_anomaly=True,
        anomaly_confidence=Decimal("110.00"),
    )
    with pytest.raises(ValidationError):
        reading.full_clean()


@pytest.mark.django_db
def test_asset_reliability_models_telemetry_reading_unique_number(tenant_a, telemetry_reading_a):
    with pytest.raises(IntegrityError):
        AssetTelemetryReading.objects.create(
            tenant=tenant_a,
            number=telemetry_reading_a.number,
            reading_value=Decimal("2.0000"),
        )


# ==============================================================================
# 3. AssetFailureMode Model Tests
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_models_failure_mode_str_and_numbering(failure_mode_a):
    assert failure_mode_a.number.startswith("AFMA-")
    assert "AFMA-" in str(failure_mode_a)
    assert failure_mode_a.component_subsystem in str(failure_mode_a)
    assert failure_mode_a.failure_mode in str(failure_mode_a)
    assert f"RPN {failure_mode_a.rpn}" in str(failure_mode_a)


@pytest.mark.django_db
def test_asset_reliability_models_failure_mode_defaults(tenant_a):
    fm = AssetFailureMode.objects.create(
        tenant=tenant_a,
        component_subsystem="Hydraulic Return Line",
        function_description="Route return fluid at < 5 bar back to tank",
        functional_failure="Ruptured return hose causing fluid loss",
        failure_mode="Elastomeric Fatigue & Pressure Pulsation",
        failure_cause="Cyclic fatigue under continuous pulsating load",
        failure_effect="Loss of pressure and hydraulic oil spill hazard",
    )
    assert fm.number.startswith("AFMA-")
    assert fm.severity_score == 5
    assert fm.occurrence_score == 5
    assert fm.detection_score == 5
    # Default RPN = 5 * 5 * 5 = 125
    assert fm.rpn == 125
    assert fm.risk_level == "medium"
    assert fm.rcm_strategy == "condition_based"
    assert fm.status == "active"


@pytest.mark.django_db
def test_asset_reliability_models_failure_mode_rpn_calculation_low_risk(tenant_a):
    fm = AssetFailureMode(
        tenant=tenant_a,
        component_subsystem="Coolant Mist Collector Filter",
        function_description="Filter airborne oil droplets",
        functional_failure="Filter element saturation",
        failure_mode="Particulate Blinding",
        failure_cause="Normal particulate capture over extended service life",
        failure_effect="Minor decrease in suction airflow",
        severity_score=2,
        occurrence_score=3,
        detection_score=4,
    )
    fm.save()
    fm.refresh_from_db()
    # RPN = 2 * 3 * 4 = 24 (< 100 => low)
    assert fm.rpn == 24
    assert fm.risk_level == "low"
    assert fm.risk_level_css == "badge-green"


@pytest.mark.django_db
def test_asset_reliability_models_failure_mode_rpn_calculation_medium_risk(tenant_a):
    # Boundary test: RPN = 100
    fm_boundary = AssetFailureMode(
        tenant=tenant_a,
        component_subsystem="Pneumatic Chuck Clamp",
        function_description="Clamp workpiece with 25 kN force",
        functional_failure="Reduced clamping force",
        failure_mode="Piston seal wear",
        failure_cause="Abrasive particulate ingress",
        failure_effect="Potential workpiece slippage during cutting",
        severity_score=5,
        occurrence_score=4,
        detection_score=5,
    )
    fm_boundary.save()
    fm_boundary.refresh_from_db()
    assert fm_boundary.rpn == 100
    assert fm_boundary.risk_level == "medium"
    assert fm_boundary.risk_level_css == "badge-info"

    # Upper boundary: RPN = 250
    fm_upper = AssetFailureMode(
        tenant=tenant_a,
        component_subsystem="Way Lubing System",
        function_description="Deliver 2 ml/hr slideway lubricant",
        functional_failure="Blocked metering orifice",
        failure_mode="Wax accumulation",
        failure_cause="Incompatible lubricant mixing",
        failure_effect="Slideway stick-slip wear",
        severity_score=10,
        occurrence_score=5,
        detection_score=5,
    )
    fm_upper.save()
    fm_upper.refresh_from_db()
    assert fm_upper.rpn == 250
    assert fm_upper.risk_level == "medium"


@pytest.mark.django_db
def test_asset_reliability_models_failure_mode_rpn_calculation_high_risk(tenant_a):
    # Boundary test: RPN = 251 or 300
    fm = AssetFailureMode(
        tenant=tenant_a,
        component_subsystem="Ballscrew Drive",
        function_description="Convert rotary to linear motion with < 2um backlash",
        functional_failure="Loss of positioning repeatability",
        failure_mode="Recirculating ball bearing fatigue pitting",
        failure_cause="Contamination from abrasive dust",
        failure_effect="Part dimensional out-of-tolerance scrap",
        severity_score=6,
        occurrence_score=5,
        detection_score=10,
    )
    fm.save()
    fm.refresh_from_db()
    # RPN = 6 * 5 * 10 = 300 (251-500 => high)
    assert fm.rpn == 300
    assert fm.risk_level == "high"
    assert fm.risk_level_css == "badge-amber"


@pytest.mark.django_db
def test_asset_reliability_models_failure_mode_rpn_calculation_extreme_risk(tenant_a):
    fm = AssetFailureMode(
        tenant=tenant_a,
        component_subsystem="Main Electrical Transformer",
        function_description="Step down 11kV grid to 415V plant power",
        functional_failure="Total plant power loss with arc flash",
        failure_mode="Dielectric Breakdown of Core Windings",
        failure_cause="Moisture intrusion and thermal aging of cellulose insulation",
        failure_effect="Catastrophic plant blackout, fire, and extreme personnel risk",
        severity_score=10,
        occurrence_score=8,
        detection_score=7,
    )
    fm.save()
    fm.refresh_from_db()
    # RPN = 10 * 8 * 7 = 560 (> 500 => extreme)
    assert fm.rpn == 560
    assert fm.risk_level == "extreme"
    assert fm.risk_level_css == "badge-red"


@pytest.mark.django_db
def test_asset_reliability_models_failure_mode_rpn_method_alias(failure_mode_a):
    failure_mode_a.severity_score = 8
    failure_mode_a.occurrence_score = 4
    failure_mode_a.detection_score = 3
    failure_mode_a.calculate_rpn_and_risk_level()
    assert failure_mode_a.rpn == 96
    assert failure_mode_a.risk_level == "low"


@pytest.mark.django_db
def test_asset_reliability_models_failure_mode_css_properties(failure_mode_a):
    failure_mode_a.status = "active"
    assert failure_mode_a.status_css == "badge-green"
    failure_mode_a.status = "draft"
    assert failure_mode_a.status_css == "badge-slate"
    failure_mode_a.status = "superseded"
    assert failure_mode_a.status_css == "badge-amber"
    failure_mode_a.status = "archived"
    assert failure_mode_a.status_css == "badge-muted"

    failure_mode_a.rcm_strategy = "condition_based"
    assert failure_mode_a.rcm_strategy_css == "badge-info"
    failure_mode_a.rcm_strategy = "time_based_pm"
    assert failure_mode_a.rcm_strategy_css == "badge-slate"
    failure_mode_a.rcm_strategy = "failure_finding"
    assert failure_mode_a.rcm_strategy_css == "badge-amber"
    failure_mode_a.rcm_strategy = "redesign_required"
    assert failure_mode_a.rcm_strategy_css == "badge-red"


@pytest.mark.django_db
def test_asset_reliability_models_failure_mode_score_validation(tenant_a):
    fm_out_of_bounds = AssetFailureMode(
        tenant=tenant_a,
        component_subsystem="Test",
        function_description="Test",
        functional_failure="Test",
        failure_mode="Test",
        failure_cause="Test",
        failure_effect="Test",
        severity_score=11,  # max is 10
    )
    with pytest.raises(ValidationError):
        fm_out_of_bounds.full_clean()


@pytest.mark.django_db
def test_asset_reliability_models_failure_mode_unique_number(tenant_a, failure_mode_a):
    with pytest.raises(IntegrityError):
        AssetFailureMode.objects.create(
            tenant=tenant_a,
            number=failure_mode_a.number,
            component_subsystem="Duplicate Subsystem",
            function_description="Test function",
            functional_failure="Test failure",
            failure_mode="Test mode",
            failure_cause="Test cause",
            failure_effect="Test effect",
        )


# ==============================================================================
# 4. AssetCalibrationRecord Model Tests
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_models_calibration_record_str_and_numbering(calibration_record_a):
    assert calibration_record_a.number.startswith("ACAL-")
    assert "ACAL-" in str(calibration_record_a)
    assert calibration_record_a.instrument_tag in str(calibration_record_a)
    assert "Pass (Within Tolerance)" in str(calibration_record_a)


@pytest.mark.django_db
def test_asset_reliability_models_calibration_record_defaults(tenant_a):
    today = timezone.now().date()
    cal = AssetCalibrationRecord.objects.create(
        tenant=tenant_a,
        instrument_tag="PG-FEED-01",
        reference_standard_used="Budenberg Deadweight Tester #1098",
        setpoint_nominal=Decimal("100.0000"),
        as_found_reading=Decimal("100.1500"),
        as_left_reading=Decimal("100.0200"),
        calibration_date=today,
    )
    assert cal.number.startswith("ACAL-")
    assert cal.calibration_frequency_days == 365
    assert cal.next_due_date == today + timedelta(days=365)
    assert cal.allowable_tolerance == Decimal("0.5000")
    assert cal.tolerance_unit == "percent_span"
    assert cal.as_found_error == Decimal("0.1500")
    assert cal.as_left_error == Decimal("0.0200")
    assert cal.calibration_result == "pass"
    assert cal.status == "valid"


@pytest.mark.django_db
def test_asset_reliability_models_calibration_record_out_of_tolerance(tenant_a):
    today = timezone.now().date()
    cal = AssetCalibrationRecord(
        tenant=tenant_a,
        instrument_tag="TT-MOTOR-03",
        reference_standard_used="Fluke 9144 Field Metrology Well",
        calibration_date=today,
        calibration_frequency_days=180,
        setpoint_nominal=Decimal("100.0000"),
        allowable_tolerance=Decimal("0.5000"),
        as_found_reading=Decimal("102.5000"),
        as_left_reading=Decimal("101.2000"),
    )
    cal.save()
    cal.refresh_from_db()
    # as_left_error = 101.2 - 100.0 = 1.2000 > allowable_tolerance (0.5000)
    assert cal.as_left_error == Decimal("1.2000")
    assert cal.calibration_result == "fail_out_of_tolerance"
    assert cal.calibration_result_css == "badge-red"


@pytest.mark.django_db
def test_asset_reliability_models_calibration_record_pass_with_adjustment(tenant_a):
    today = timezone.now().date()
    cal = AssetCalibrationRecord(
        tenant=tenant_a,
        instrument_tag="PT-LINE-05",
        reference_standard_used="Druck DPI 611 Calibrator",
        calibration_date=today,
        setpoint_nominal=Decimal("50.0000"),
        allowable_tolerance=Decimal("0.2000"),
        as_found_reading=Decimal("50.8000"),  # error = 0.8000 > tolerance
        as_left_reading=Decimal("50.0500"),   # error = 0.0500 <= tolerance
    )
    cal.save()
    cal.refresh_from_db()
    assert cal.as_found_error == Decimal("0.8000")
    assert cal.as_left_error == Decimal("0.0500")
    assert cal.calibration_result == "pass_with_adjustment"
    assert cal.calibration_result_css == "badge-info"


@pytest.mark.django_db
def test_asset_reliability_models_calibration_record_quarantined_preserved(tenant_a):
    today = timezone.now().date()
    cal = AssetCalibrationRecord(
        tenant=tenant_a,
        instrument_tag="FLOW-CORIOLIS-01",
        reference_standard_used="Micro Motion Flow Reference Meter",
        calibration_date=today,
        setpoint_nominal=Decimal("1000.0000"),
        allowable_tolerance=Decimal("1.0000"),
        as_found_reading=Decimal("1050.0000"),
        as_left_reading=Decimal("1050.0000"),
        calibration_result="quarantined",
    )
    cal.save()
    cal.refresh_from_db()
    # Quarantined status should not be overridden by fail_out_of_tolerance
    assert cal.calibration_result == "quarantined"
    assert cal.calibration_result_css == "badge-red"


@pytest.mark.django_db
def test_asset_reliability_models_calibration_record_status_lifecycle_dates(tenant_a):
    today = timezone.now().date()

    # Expired
    cal_expired = AssetCalibrationRecord(
        tenant=tenant_a,
        instrument_tag="INST-EXP-01",
        reference_standard_used="Standard",
        calibration_date=today - timedelta(days=400),
        next_due_date=today - timedelta(days=35),
        setpoint_nominal=Decimal("10.0000"),
        as_found_reading=Decimal("10.0000"),
        as_left_reading=Decimal("10.0000"),
    )
    cal_expired.save()
    cal_expired.refresh_from_db()
    assert cal_expired.status == "expired"
    assert cal_expired.status_css == "badge-red"

    # Expiring Soon (within 30 days)
    cal_soon = AssetCalibrationRecord(
        tenant=tenant_a,
        instrument_tag="INST-SOON-01",
        reference_standard_used="Standard",
        calibration_date=today - timedelta(days=345),
        next_due_date=today + timedelta(days=20),
        setpoint_nominal=Decimal("10.0000"),
        as_found_reading=Decimal("10.0000"),
        as_left_reading=Decimal("10.0000"),
    )
    cal_soon.save()
    cal_soon.refresh_from_db()
    assert cal_soon.status == "expiring_soon"
    assert cal_soon.status_css == "badge-amber"

    # Voided preserved
    cal_voided = AssetCalibrationRecord(
        tenant=tenant_a,
        instrument_tag="INST-VOID-01",
        reference_standard_used="Standard",
        calibration_date=today - timedelta(days=400),
        next_due_date=today - timedelta(days=35),
        setpoint_nominal=Decimal("10.0000"),
        as_found_reading=Decimal("10.0000"),
        as_left_reading=Decimal("10.0000"),
        status="voided",
    )
    cal_voided.save()
    cal_voided.refresh_from_db()
    assert cal_voided.status == "voided"
    assert cal_voided.status_css == "badge-muted"


@pytest.mark.django_db
def test_asset_reliability_models_calibration_record_css_properties(calibration_record_a):
    calibration_record_a.tolerance_unit = "percent_span"
    assert calibration_record_a.tolerance_unit_css == "badge-info"
    calibration_record_a.tolerance_unit = "engineering_units"
    assert calibration_record_a.tolerance_unit_css == "badge-slate"
    calibration_record_a.tolerance_unit = "celsius"
    assert calibration_record_a.tolerance_unit_css == "badge-amber"
    calibration_record_a.tolerance_unit = "psi"
    assert calibration_record_a.tolerance_unit_css == "badge-info"
    calibration_record_a.tolerance_unit = "volts"
    assert calibration_record_a.tolerance_unit_css == "badge-amber"


@pytest.mark.django_db
def test_asset_reliability_models_calibration_record_unique_number(tenant_a, calibration_record_a):
    today = timezone.now().date()
    with pytest.raises(IntegrityError):
        AssetCalibrationRecord.objects.create(
            tenant=tenant_a,
            number=calibration_record_a.number,
            instrument_tag="INST-DUP-01",
            reference_standard_used="Standard",
            calibration_date=today,
            setpoint_nominal=Decimal("10.0000"),
            as_found_reading=Decimal("10.0000"),
            as_left_reading=Decimal("10.0000"),
        )
