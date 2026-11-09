"""Functional view and workflow action tests for Module 11.7: Asset Reliability & Condition Monitoring.

Covers all 28 views across the 4 entities:
1. AssetConditionAssessment (list, detail, create, edit, delete, complete, review, trigger_request)
2. AssetTelemetryReading (list, detail, create, edit, delete, flag_anomaly, trigger_request)
3. AssetFailureMode (list, detail, create, edit, delete, activate, archive)
4. AssetCalibrationRecord (list, detail, create, edit, delete, quarantine)
5. Unauthenticated access redirects across all entities
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    AssetCategory,
    AssetConditionAssessment,
    AssetTelemetryReading,
    AssetFailureMode,
    AssetCalibrationRecord,
    AssetMaintenanceRequest,
)


# ==============================================================================
# Helper Payload Factories (prefixed with _asset_reliability_views_)
# ==============================================================================

def _asset_reliability_views_condition_payload(fixed_asset=None, operational_asset=None, category=None, inspector=None, vendor=None, **overrides):
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


def _asset_reliability_views_telemetry_payload(fixed_asset=None, operational_asset=None, user=None, **overrides):
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


def _asset_reliability_views_failure_mode_payload(fixed_asset=None, operational_asset=None, category=None, schedule=None, user=None, **overrides):
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


def _asset_reliability_views_calibration_payload(fixed_asset=None, operational_asset=None, user=None, vendor=None, doc=None, **overrides):
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
# 1. AssetConditionAssessment Views
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_list_success(client_a, condition_assessment_a):
    """asset_condition_assessment_list returns 200 and validates full context contract."""
    url = reverse("assets:asset_condition_assessment_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Context keys verification
    assert "condition_assessments" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "status_choices" in resp.context
    assert "condition_grade_choices" in resp.context
    assert "assessment_type_choices" in resp.context
    assert "operating_status_choices" in resp.context
    assert "category_list" in resp.context
    assert "total_assessments" in resp.context
    assert "critical_defect_count" in resp.context
    assert "average_health_score" in resp.context
    assert "followup_count" in resp.context

    assert resp.context["total_assessments"] >= 1
    assert condition_assessment_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_list_tenant_isolation(client_a, condition_assessment_a, condition_assessment_b):
    """asset_condition_assessment_list strictly isolates assessments by tenant."""
    url = reverse("assets:asset_condition_assessment_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    pks = [a.pk for a in resp.context["condition_assessments"]]
    assert condition_assessment_a.pk in pks
    assert condition_assessment_b.pk not in pks
    content = resp.content.decode()
    assert "Spindle Ultrasound" in content
    assert "Globex Stacker" not in content


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_list_filters(client_a, tenant_a, fixed_asset_a, operational_asset_a, category_root_a):
    """asset_condition_assessment_list handles q, status, grade, type, operating status, and category filters."""
    item1 = AssetConditionAssessment.objects.create(
        tenant=tenant_a,
        title="Spindle Ultrasound Special Filter Test",
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        asset_category=category_root_a,
        assessment_type="ndt_ultrasonic",
        condition_grade="grade_4_poor",
        operating_status="reduced_capacity",
        status="draft",
        findings="Cavitation pitting found on impeller blades.",
    )
    item2 = AssetConditionAssessment.objects.create(
        tenant=tenant_a,
        title="Laser Shaft Alignment Check",
        assessment_type="visual_inspection",
        condition_grade="grade_1_excellent",
        operating_status="normal_operation",
        status="completed",
        findings="Alignment perfectly within specifications.",
    )
    url = reverse("assets:asset_condition_assessment_list")

    # Filter q
    resp_q = client_a.get(url, {"q": "Cavitation"})
    assert resp_q.status_code == 200
    pks_q = [a.pk for a in resp_q.context["condition_assessments"]]
    assert item1.pk in pks_q
    assert item2.pk not in pks_q

    # Filter status
    resp_stat = client_a.get(url, {"status": "draft"})
    assert resp_stat.status_code == 200
    pks_stat = [a.pk for a in resp_stat.context["condition_assessments"]]
    assert item1.pk in pks_stat
    assert item2.pk not in pks_stat

    # Filter condition_grade
    resp_grade = client_a.get(url, {"condition_grade": "grade_4_poor"})
    assert resp_grade.status_code == 200
    pks_grade = [a.pk for a in resp_grade.context["condition_assessments"]]
    assert item1.pk in pks_grade
    assert item2.pk not in pks_grade

    # Filter assessment_type
    resp_type = client_a.get(url, {"assessment_type": "ndt_ultrasonic"})
    assert resp_type.status_code == 200
    pks_type = [a.pk for a in resp_type.context["condition_assessments"]]
    assert item1.pk in pks_type
    assert item2.pk not in pks_type

    # Filter operating_status
    resp_op = client_a.get(url, {"operating_status": "reduced_capacity"})
    assert resp_op.status_code == 200
    pks_op = [a.pk for a in resp_op.context["condition_assessments"]]
    assert item1.pk in pks_op
    assert item2.pk not in pks_op

    # Filter category
    resp_cat = client_a.get(url, {"category": str(category_root_a.pk)})
    assert resp_cat.status_code == 200
    pks_cat = [a.pk for a in resp_cat.context["condition_assessments"]]
    assert item1.pk in pks_cat
    assert item2.pk not in pks_cat


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_list_junk_params(client_a, condition_assessment_a):
    """asset_condition_assessment_list gracefully handles junk filter parameters without 500."""
    url = reverse("assets:asset_condition_assessment_list")
    resp = client_a.get(url, {
        "category": "not_an_int",
        "status": "non_existent_status",
        "condition_grade": "bogus_grade",
        "page": "invalid_page",
    })
    assert resp.status_code == 200
    assert "condition_assessments" in resp.context


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_list_pagination(client_a, tenant_a):
    """asset_condition_assessment_list paginates cleanly at 15 items per page."""
    for i in range(16):
        AssetConditionAssessment.objects.create(
            tenant=tenant_a,
            title=f"Batch Assessment {i}",
            findings=f"Findings detail for {i}",
        )
    url = reverse("assets:asset_condition_assessment_list")
    resp = client_a.get(url, {"page": "2"})
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 2
    assert resp.context["is_paginated"] is True


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_detail_success(client_a, condition_assessment_a):
    """asset_condition_assessment_detail returns 200 with assessment context."""
    url = reverse("assets:asset_condition_assessment_detail", args=[condition_assessment_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["assessment"] == condition_assessment_a
    assert condition_assessment_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_detail_cross_tenant_404(client_a, condition_assessment_b):
    """asset_condition_assessment_detail prevents cross-tenant access with 404."""
    url = reverse("assets:asset_condition_assessment_detail", args=[condition_assessment_b.pk])
    resp = client_a.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_create_get(client_a):
    """asset_condition_assessment_create GET renders form with is_edit=False."""
    url = reverse("assets:asset_condition_assessment_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["assessment"] is None


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_create_post_success(client_a, tenant_a, fixed_asset_a, admin_user):
    """asset_condition_assessment_create POST valid data creates record and redirects to detail."""
    url = reverse("assets:asset_condition_assessment_create")
    data = _asset_reliability_views_condition_payload(fixed_asset=fixed_asset_a, title="Thermographic Electrical Panel Scan")
    resp = client_a.post(url, data=data)
    assert resp.status_code == 302
    created = AssetConditionAssessment.objects.filter(tenant=tenant_a, title=data["title"]).first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.inspector == admin_user
    assert resp.url == reverse("assets:asset_condition_assessment_detail", args=[created.pk])


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_create_post_invalid(client_a):
    """asset_condition_assessment_create POST invalid data re-renders form with 200."""
    url = reverse("assets:asset_condition_assessment_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_edit_get(client_a, condition_assessment_a):
    """asset_condition_assessment_edit GET renders form with is_edit=True."""
    url = reverse("assets:asset_condition_assessment_edit", args=[condition_assessment_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["assessment"] == condition_assessment_a


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_edit_post_success(client_a, condition_assessment_a):
    """asset_condition_assessment_edit POST valid update redirects to detail."""
    url = reverse("assets:asset_condition_assessment_edit", args=[condition_assessment_a.pk])
    data = _asset_reliability_views_condition_payload(
        title="Updated Ultrasound Analysis Scope",
        health_score="92",
    )
    resp = client_a.post(url, data=data)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_condition_assessment_detail", args=[condition_assessment_a.pk])
    condition_assessment_a.refresh_from_db()
    assert condition_assessment_a.title == "Updated Ultrasound Analysis Scope"
    assert condition_assessment_a.health_score == 92


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_edit_post_invalid(client_a, condition_assessment_a):
    """asset_condition_assessment_edit POST invalid data returns 200 with errors."""
    url = reverse("assets:asset_condition_assessment_edit", args=[condition_assessment_a.pk])
    resp = client_a.post(url, data={"title": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_edit_cross_tenant_404(client_a, condition_assessment_b):
    """asset_condition_assessment_edit prevents cross-tenant access with 404."""
    url = reverse("assets:asset_condition_assessment_edit", args=[condition_assessment_b.pk])
    resp = client_a.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_delete_method_not_allowed(client_a, condition_assessment_a):
    """asset_condition_assessment_delete rejects GET requests with 405."""
    url = reverse("assets:asset_condition_assessment_delete", args=[condition_assessment_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_delete_non_admin_forbidden(member_client, condition_assessment_a):
    """asset_condition_assessment_delete denies non-tenant-admin users with 403."""
    url = reverse("assets:asset_condition_assessment_delete", args=[condition_assessment_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_delete_admin_success(client_a, condition_assessment_a):
    """asset_condition_assessment_delete deletes record and redirects to list."""
    url = reverse("assets:asset_condition_assessment_delete", args=[condition_assessment_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_condition_assessment_list")
    assert not AssetConditionAssessment.objects.filter(pk=condition_assessment_a.pk).exists()


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_complete_action(client_a, tenant_a):
    """asset_condition_assessment_complete transitions draft assessment to completed."""
    assessment = AssetConditionAssessment.objects.create(
        tenant=tenant_a,
        title="Draft Assessment for Completion",
        findings="Findings initial text",
        status="draft",
    )
    url = reverse("assets:asset_condition_assessment_complete", args=[assessment.pk])

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # POST transitions status
    resp = client_a.post(url)
    assert resp.status_code == 302
    assessment.refresh_from_db()
    assert assessment.status == "completed"


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_review_permissions(client_a, member_client, condition_assessment_a):
    """asset_condition_assessment_review requires tenant admin and transitions status to reviewed."""
    condition_assessment_a.status = "completed"
    condition_assessment_a.save()
    url = reverse("assets:asset_condition_assessment_review", args=[condition_assessment_a.pk])

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # Member user gets 403
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403

    # Admin user succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    condition_assessment_a.refresh_from_db()
    assert condition_assessment_a.status == "reviewed"
    assert condition_assessment_a.reviewed_by is not None
    assert condition_assessment_a.reviewed_at is not None


@pytest.mark.django_db
def test_asset_reliability_views_condition_assessment_trigger_request_action(client_a, condition_assessment_a):
    """asset_condition_assessment_trigger_request creates linked AssetMaintenanceRequest and prevents duplicate tickets."""
    url = reverse("assets:asset_condition_assessment_trigger_request", args=[condition_assessment_a.pk])

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # POST creates maintenance ticket
    resp = client_a.post(url)
    assert resp.status_code == 302
    condition_assessment_a.refresh_from_db()
    assert condition_assessment_a.triggered_maintenance_request is not None
    assert condition_assessment_a.followup_required is True
    req = condition_assessment_a.triggered_maintenance_request
    assert resp.url == reverse("assets:asset_maintenance_request_detail", args=[req.pk])

    # Calling again redirects to existing ticket without duplicating
    resp2 = client_a.post(url)
    assert resp2.status_code == 302
    assert resp2.url == reverse("assets:asset_maintenance_request_detail", args=[req.pk])
    assert AssetMaintenanceRequest.objects.filter(triggering_condition_assessments=condition_assessment_a).count() == 1


# ==============================================================================
# 2. AssetTelemetryReading Views
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_list_success(client_a, telemetry_reading_a):
    """asset_telemetry_reading_list returns 200 and validates full context contract."""
    url = reverse("assets:asset_telemetry_reading_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Context keys verification
    assert "telemetry_readings" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "source_choices" in resp.context
    assert "metric_type_choices" in resp.context
    assert "threshold_status_choices" in resp.context
    assert "total_readings" in resp.context
    assert "critical_reading_count" in resp.context
    assert "anomaly_reading_count" in resp.context
    assert "normal_reading_count" in resp.context

    assert resp.context["total_readings"] >= 1
    assert telemetry_reading_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_list_tenant_isolation(client_a, telemetry_reading_a, telemetry_reading_b):
    """asset_telemetry_reading_list strictly isolates telemetry records by tenant."""
    url = reverse("assets:asset_telemetry_reading_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    pks = [r.pk for r in resp.context["telemetry_readings"]]
    assert telemetry_reading_a.pk in pks
    assert telemetry_reading_b.pk not in pks
    content = resp.content.decode()
    assert telemetry_reading_a.sensor_identifier in content
    assert telemetry_reading_b.sensor_identifier not in content


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_list_filters(client_a, tenant_a, fixed_asset_a):
    """asset_telemetry_reading_list handles q, threshold, metric, source, and is_anomaly filters."""
    r1 = AssetTelemetryReading.objects.create(
        tenant=tenant_a,
        sensor_identifier="SENS-CRIT-99",
        fixed_asset=fixed_asset_a,
        source="iot_sensor",
        metric_type="vibration_peak_accel",
        reading_value=Decimal("10.0000"),
        baseline_value=Decimal("5.0000"),
        is_anomaly=False,
        alert_notes="High harmonics detected on main gear mesh.",
    )
    r2 = AssetTelemetryReading.objects.create(
        tenant=tenant_a,
        sensor_identifier="SENS-NORM-01",
        source="manual_gauge",
        metric_type="bearing_temperature",
        reading_value=Decimal("45.2000"),
        baseline_value=Decimal("45.0000"),
        is_anomaly=False,
        alert_notes="Operating temperature within standard envelope.",
    )
    r3 = AssetTelemetryReading.objects.create(
        tenant=tenant_a,
        sensor_identifier="SENS-ANOM-02",
        source="scada_historian",
        metric_type="operating_pressure",
        reading_value=Decimal("80.0000"),
        baseline_value=Decimal("80.0000"),
        is_anomaly=True,
        alert_notes="Statistical pattern anomaly detected.",
    )
    url = reverse("assets:asset_telemetry_reading_list")

    # Filter q
    resp_q = client_a.get(url, {"q": "harmonics"})
    assert resp_q.status_code == 200
    pks_q = [r.pk for r in resp_q.context["telemetry_readings"]]
    assert r1.pk in pks_q
    assert r2.pk not in pks_q

    # Filter threshold_status (r1 deviation is 100% >= 50% -> critical)
    resp_thresh = client_a.get(url, {"threshold_status": "critical"})
    assert resp_thresh.status_code == 200
    pks_th = [r.pk for r in resp_thresh.context["telemetry_readings"]]
    assert r1.pk in pks_th
    assert r2.pk not in pks_th

    # Filter metric_type
    resp_metric = client_a.get(url, {"metric_type": "bearing_temperature"})
    assert resp_metric.status_code == 200
    pks_m = [r.pk for r in resp_metric.context["telemetry_readings"]]
    assert r2.pk in pks_m
    assert r1.pk not in pks_m

    # Filter source
    resp_src = client_a.get(url, {"source": "manual_gauge"})
    assert resp_src.status_code == 200
    pks_src = [r.pk for r in resp_src.context["telemetry_readings"]]
    assert r2.pk in pks_src
    assert r1.pk not in pks_src

    # Filter is_anomaly="1"
    resp_anom1 = client_a.get(url, {"is_anomaly": "1"})
    assert resp_anom1.status_code == 200
    pks_a1 = [r.pk for r in resp_anom1.context["telemetry_readings"]]
    assert r3.pk in pks_a1
    assert r1.pk not in pks_a1

    # Filter is_anomaly="0"
    resp_anom0 = client_a.get(url, {"is_anomaly": "0"})
    assert resp_anom0.status_code == 200
    pks_a0 = [r.pk for r in resp_anom0.context["telemetry_readings"]]
    assert r1.pk in pks_a0
    assert r3.pk not in pks_a0


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_list_junk_params(client_a, telemetry_reading_a):
    """asset_telemetry_reading_list handles junk query parameters gracefully."""
    url = reverse("assets:asset_telemetry_reading_list")
    resp = client_a.get(url, {
        "threshold_status": "invalid_status",
        "metric_type": "invalid_type",
        "is_anomaly": "not_a_boolean",
        "page": "bogus_page",
    })
    assert resp.status_code == 200
    assert "telemetry_readings" in resp.context


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_list_pagination(client_a, tenant_a):
    """asset_telemetry_reading_list paginates cleanly at 15 items per page."""
    for i in range(16):
        AssetTelemetryReading.objects.create(
            tenant=tenant_a,
            sensor_identifier=f"SENS-PAGIN-{i}",
            reading_value=Decimal("5.0000"),
        )
    url = reverse("assets:asset_telemetry_reading_list")
    resp = client_a.get(url, {"page": "2"})
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 2
    assert resp.context["is_paginated"] is True


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_detail_success(client_a, telemetry_reading_a):
    """asset_telemetry_reading_detail returns 200 with reading context."""
    url = reverse("assets:asset_telemetry_reading_detail", args=[telemetry_reading_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["reading"] == telemetry_reading_a
    assert telemetry_reading_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_detail_cross_tenant_404(client_a, telemetry_reading_b):
    """asset_telemetry_reading_detail blocks cross-tenant access with 404."""
    url = reverse("assets:asset_telemetry_reading_detail", args=[telemetry_reading_b.pk])
    resp = client_a.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_create_get(client_a):
    """asset_telemetry_reading_create GET renders form with is_edit=False."""
    url = reverse("assets:asset_telemetry_reading_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["reading"] is None


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_create_post_success(client_a, tenant_a, fixed_asset_a, admin_user):
    """asset_telemetry_reading_create POST valid data creates record and assigns recorded_by."""
    url = reverse("assets:asset_telemetry_reading_create")
    data = _asset_reliability_views_telemetry_payload(
        fixed_asset=fixed_asset_a,
        sensor_identifier="TEST-SENS-CREAT",
        reading_value="7.8000",
    )
    resp = client_a.post(url, data=data)
    assert resp.status_code == 302
    created = AssetTelemetryReading.objects.filter(tenant=tenant_a, sensor_identifier="TEST-SENS-CREAT").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.recorded_by == admin_user
    assert resp.url == reverse("assets:asset_telemetry_reading_detail", args=[created.pk])


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_create_post_invalid(client_a):
    """asset_telemetry_reading_create POST invalid data re-renders form with errors."""
    url = reverse("assets:asset_telemetry_reading_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_edit_get(client_a, telemetry_reading_a):
    """asset_telemetry_reading_edit GET renders form with is_edit=True."""
    url = reverse("assets:asset_telemetry_reading_edit", args=[telemetry_reading_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["reading"] == telemetry_reading_a


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_edit_post_success(client_a, telemetry_reading_a):
    """asset_telemetry_reading_edit POST valid data updates record and redirects to detail."""
    url = reverse("assets:asset_telemetry_reading_edit", args=[telemetry_reading_a.pk])
    data = _asset_reliability_views_telemetry_payload(
        sensor_identifier="SENS-UPDATED-01",
        reading_value="9.1500",
        alert_notes="Updated telemetry observations.",
    )
    resp = client_a.post(url, data=data)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_telemetry_reading_detail", args=[telemetry_reading_a.pk])
    telemetry_reading_a.refresh_from_db()
    assert telemetry_reading_a.sensor_identifier == "SENS-UPDATED-01"
    assert telemetry_reading_a.reading_value == Decimal("9.1500")


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_edit_post_invalid(client_a, telemetry_reading_a):
    """asset_telemetry_reading_edit POST invalid data returns 200."""
    url = reverse("assets:asset_telemetry_reading_edit", args=[telemetry_reading_a.pk])
    resp = client_a.post(url, data={"reading_value": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_edit_cross_tenant_404(client_a, telemetry_reading_b):
    """asset_telemetry_reading_edit denies cross-tenant access with 404."""
    url = reverse("assets:asset_telemetry_reading_edit", args=[telemetry_reading_b.pk])
    resp = client_a.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_delete_method_not_allowed(client_a, telemetry_reading_a):
    """asset_telemetry_reading_delete rejects GET requests with 405."""
    url = reverse("assets:asset_telemetry_reading_delete", args=[telemetry_reading_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_delete_non_admin_forbidden(member_client, telemetry_reading_a):
    """asset_telemetry_reading_delete denies non-tenant-admin users with 403."""
    url = reverse("assets:asset_telemetry_reading_delete", args=[telemetry_reading_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_delete_admin_success(client_a, telemetry_reading_a):
    """asset_telemetry_reading_delete removes record and redirects to list."""
    url = reverse("assets:asset_telemetry_reading_delete", args=[telemetry_reading_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_telemetry_reading_list")
    assert not AssetTelemetryReading.objects.filter(pk=telemetry_reading_a.pk).exists()


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_flag_anomaly_action(client_a, telemetry_reading_a):
    """asset_telemetry_reading_flag_anomaly flags anomaly and sets confidence."""
    url = reverse("assets:asset_telemetry_reading_flag_anomaly", args=[telemetry_reading_a.pk])

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # POST flags anomaly
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_telemetry_reading_detail", args=[telemetry_reading_a.pk])
    telemetry_reading_a.refresh_from_db()
    assert telemetry_reading_a.is_anomaly is True
    assert telemetry_reading_a.threshold_status == "anomaly_detected"
    assert telemetry_reading_a.anomaly_confidence >= Decimal("95.00")


@pytest.mark.django_db
def test_asset_reliability_views_telemetry_reading_trigger_request_action(client_a, telemetry_reading_a):
    """asset_telemetry_reading_trigger_request generates maintenance request and prevents duplication."""
    url = reverse("assets:asset_telemetry_reading_trigger_request", args=[telemetry_reading_a.pk])

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # POST triggers maintenance ticket
    resp = client_a.post(url)
    assert resp.status_code == 302
    telemetry_reading_a.refresh_from_db()
    assert telemetry_reading_a.triggered_maintenance_request is not None
    req = telemetry_reading_a.triggered_maintenance_request
    assert resp.url == reverse("assets:asset_maintenance_request_detail", args=[req.pk])

    # Calling again redirects to existing ticket without duplicating
    resp2 = client_a.post(url)
    assert resp2.status_code == 302
    assert resp2.url == reverse("assets:asset_maintenance_request_detail", args=[req.pk])
    assert AssetMaintenanceRequest.objects.filter(triggering_telemetry_readings=telemetry_reading_a).count() == 1


# ==============================================================================
# 3. AssetFailureMode Views
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_list_success(client_a, failure_mode_a):
    """asset_failure_mode_list returns 200 and validates full context contract."""
    url = reverse("assets:asset_failure_mode_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Context keys verification
    assert "failure_modes" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "risk_level_choices" in resp.context
    assert "rcm_strategy_choices" in resp.context
    assert "status_choices" in resp.context
    assert "category_list" in resp.context
    assert "total_failure_modes" in resp.context
    assert "extreme_risk_count" in resp.context
    assert "high_risk_count" in resp.context
    assert "cbm_strategy_count" in resp.context

    assert resp.context["total_failure_modes"] >= 1
    assert failure_mode_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_list_tenant_isolation(client_a, failure_mode_a, failure_mode_b):
    """asset_failure_mode_list strictly isolates FMEA failure modes by tenant."""
    url = reverse("assets:asset_failure_mode_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    pks = [f.pk for f in resp.context["failure_modes"]]
    assert failure_mode_a.pk in pks
    assert failure_mode_b.pk not in pks
    content = resp.content.decode()
    assert failure_mode_a.failure_mode in content
    assert failure_mode_b.failure_mode not in content


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_list_filters(client_a, tenant_a, fixed_asset_a, category_root_a):
    """asset_failure_mode_list handles q, risk_level, rcm_strategy, status, and category filters."""
    fm1 = AssetFailureMode.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        asset_category=category_root_a,
        component_subsystem="Hydraulic Proportional Valve",
        function_description="Meter pilot pressure smoothly",
        functional_failure="Valve spool sticking",
        failure_mode="Silt lock and particulate binding",
        failure_cause="Contaminated oil",
        failure_effect="Cylinder uncontrolled lurch",
        severity_score=10,
        occurrence_score=8,
        detection_score=8,
        rcm_strategy="condition_based",
        status="active",
    )
    fm2 = AssetFailureMode.objects.create(
        tenant=tenant_a,
        component_subsystem="Control Cabinet Cooling Fan",
        function_description="Ventilate VFD drives",
        functional_failure="Fan motor stoppage",
        failure_mode="Bearing seizure",
        failure_cause="Normal wear",
        failure_effect="Cabinet temperature trip",
        severity_score=3,
        occurrence_score=3,
        detection_score=3,
        rcm_strategy="run_to_failure",
        status="draft",
    )
    url = reverse("assets:asset_failure_mode_list")

    # Filter q
    resp_q = client_a.get(url, {"q": "Proportional"})
    assert resp_q.status_code == 200
    pks_q = [f.pk for f in resp_q.context["failure_modes"]]
    assert fm1.pk in pks_q
    assert fm2.pk not in pks_q

    # Filter risk_level (fm1 RPN 9*7*5=315 -> extreme; fm2 RPN 3*3*3=27 -> low)
    resp_risk = client_a.get(url, {"risk_level": "extreme"})
    assert resp_risk.status_code == 200
    pks_r = [f.pk for f in resp_risk.context["failure_modes"]]
    assert fm1.pk in pks_r
    assert fm2.pk not in pks_r

    # Filter rcm_strategy
    resp_strat = client_a.get(url, {"rcm_strategy": "run_to_failure"})
    assert resp_strat.status_code == 200
    pks_s = [f.pk for f in resp_strat.context["failure_modes"]]
    assert fm2.pk in pks_s
    assert fm1.pk not in pks_s

    # Filter status
    resp_stat = client_a.get(url, {"status": "active"})
    assert resp_stat.status_code == 200
    pks_st = [f.pk for f in resp_stat.context["failure_modes"]]
    assert fm1.pk in pks_st
    assert fm2.pk not in pks_st

    # Filter category
    resp_cat = client_a.get(url, {"category": str(category_root_a.pk)})
    assert resp_cat.status_code == 200
    pks_cat = [f.pk for f in resp_cat.context["failure_modes"]]
    assert fm1.pk in pks_cat
    assert fm2.pk not in pks_cat


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_list_junk_params(client_a, failure_mode_a):
    """asset_failure_mode_list handles junk query parameters gracefully."""
    url = reverse("assets:asset_failure_mode_list")
    resp = client_a.get(url, {
        "category": "not_an_id",
        "risk_level": "invalid_risk",
        "rcm_strategy": "bogus_strategy",
        "page": "junk_page",
    })
    assert resp.status_code == 200
    assert "failure_modes" in resp.context


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_list_pagination(client_a, tenant_a):
    """asset_failure_mode_list paginates cleanly at 15 items per page."""
    for i in range(16):
        AssetFailureMode.objects.create(
            tenant=tenant_a,
            component_subsystem=f"Component {i}",
            function_description="Function description",
            functional_failure="Functional failure",
            failure_mode=f"Mode {i}",
            failure_cause="Cause",
            failure_effect="Effect",
        )
    url = reverse("assets:asset_failure_mode_list")
    resp = client_a.get(url, {"page": "2"})
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 2
    assert resp.context["is_paginated"] is True


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_detail_success(client_a, failure_mode_a):
    """asset_failure_mode_detail returns 200 with failure_mode context."""
    url = reverse("assets:asset_failure_mode_detail", args=[failure_mode_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["failure_mode"] == failure_mode_a
    assert failure_mode_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_detail_cross_tenant_404(client_a, failure_mode_b):
    """asset_failure_mode_detail prevents cross-tenant access with 404."""
    url = reverse("assets:asset_failure_mode_detail", args=[failure_mode_b.pk])
    resp = client_a.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_create_get(client_a):
    """asset_failure_mode_create GET renders form with is_edit=False."""
    url = reverse("assets:asset_failure_mode_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["failure_mode"] is None


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_create_post_success(client_a, tenant_a, fixed_asset_a, admin_user):
    """asset_failure_mode_create POST valid data creates FMEA record and sets assessed_by."""
    url = reverse("assets:asset_failure_mode_create")
    data = _asset_reliability_views_failure_mode_payload(
        fixed_asset=fixed_asset_a,
        failure_mode="Cavitation erosion on impeller blade tips",
    )
    resp = client_a.post(url, data=data)
    assert resp.status_code == 302
    created = AssetFailureMode.objects.filter(tenant=tenant_a, failure_mode=data["failure_mode"]).first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.assessed_by == admin_user
    assert resp.url == reverse("assets:asset_failure_mode_detail", args=[created.pk])


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_create_post_invalid(client_a):
    """asset_failure_mode_create POST invalid data returns 200 with errors."""
    url = reverse("assets:asset_failure_mode_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_edit_get(client_a, failure_mode_a):
    """asset_failure_mode_edit GET renders form with is_edit=True."""
    url = reverse("assets:asset_failure_mode_edit", args=[failure_mode_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["failure_mode"] == failure_mode_a


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_edit_post_success(client_a, failure_mode_a):
    """asset_failure_mode_edit POST valid update redirects to detail."""
    url = reverse("assets:asset_failure_mode_edit", args=[failure_mode_a.pk])
    data = _asset_reliability_views_failure_mode_payload(
        component_subsystem="Updated Ceramic Spindle Assembly",
        severity_score=9,
        occurrence_score=6,
        detection_score=4,
    )
    resp = client_a.post(url, data=data)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_failure_mode_detail", args=[failure_mode_a.pk])
    failure_mode_a.refresh_from_db()
    assert failure_mode_a.component_subsystem == "Updated Ceramic Spindle Assembly"
    assert failure_mode_a.rpn == 216


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_edit_post_invalid(client_a, failure_mode_a):
    """asset_failure_mode_edit POST invalid data returns 200."""
    url = reverse("assets:asset_failure_mode_edit", args=[failure_mode_a.pk])
    resp = client_a.post(url, data={"component_subsystem": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_edit_cross_tenant_404(client_a, failure_mode_b):
    """asset_failure_mode_edit denies cross-tenant access with 404."""
    url = reverse("assets:asset_failure_mode_edit", args=[failure_mode_b.pk])
    resp = client_a.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_delete_method_not_allowed(client_a, failure_mode_a):
    """asset_failure_mode_delete rejects GET requests with 405."""
    url = reverse("assets:asset_failure_mode_delete", args=[failure_mode_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_delete_non_admin_forbidden(member_client, failure_mode_a):
    """asset_failure_mode_delete denies non-tenant-admin users with 403."""
    url = reverse("assets:asset_failure_mode_delete", args=[failure_mode_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_delete_admin_success(client_a, failure_mode_a):
    """asset_failure_mode_delete removes record and redirects to list."""
    url = reverse("assets:asset_failure_mode_delete", args=[failure_mode_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_failure_mode_list")
    assert not AssetFailureMode.objects.filter(pk=failure_mode_a.pk).exists()


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_activate_action(client_a, tenant_a):
    """asset_failure_mode_activate transitions draft record to active."""
    fm = AssetFailureMode.objects.create(
        tenant=tenant_a,
        component_subsystem="Test Subsystem",
        function_description="Function",
        functional_failure="Failure",
        failure_mode="Mode",
        failure_cause="Cause",
        failure_effect="Effect",
        status="draft",
    )
    url = reverse("assets:asset_failure_mode_activate", args=[fm.pk])

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # POST activates
    resp = client_a.post(url)
    assert resp.status_code == 302
    fm.refresh_from_db()
    assert fm.status == "active"


@pytest.mark.django_db
def test_asset_reliability_views_failure_mode_archive_permissions(client_a, member_client, failure_mode_a):
    """asset_failure_mode_archive requires tenant admin and transitions status to archived."""
    url = reverse("assets:asset_failure_mode_archive", args=[failure_mode_a.pk])

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # Non-admin gets 403
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403

    # Admin succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    failure_mode_a.refresh_from_db()
    assert failure_mode_a.status == "archived"


# ==============================================================================
# 4. AssetCalibrationRecord Views
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_list_success(client_a, calibration_record_a):
    """asset_calibration_record_list returns 200 and validates full context contract."""
    url = reverse("assets:asset_calibration_record_list")
    resp = client_a.get(url)
    assert resp.status_code == 200

    # Context keys verification
    assert "calibration_records" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "calibration_result_choices" in resp.context
    assert "status_choices" in resp.context
    assert "tolerance_unit_choices" in resp.context
    assert "vendor_list" in resp.context
    assert "total_calibrations" in resp.context
    assert "passed_count" in resp.context
    assert "failed_count" in resp.context
    assert "overdue_count" in resp.context

    assert resp.context["total_calibrations"] >= 1
    assert calibration_record_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_list_tenant_isolation(client_a, calibration_record_a, calibration_record_b):
    """asset_calibration_record_list strictly isolates calibration logs by tenant."""
    url = reverse("assets:asset_calibration_record_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    pks = [c.pk for c in resp.context["calibration_records"]]
    assert calibration_record_a.pk in pks
    assert calibration_record_b.pk not in pks
    content = resp.content.decode()
    assert calibration_record_a.instrument_tag in content
    assert calibration_record_b.instrument_tag not in content


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_list_filters(client_a, tenant_a, vendor_party_a):
    """asset_calibration_record_list handles q, calibration_result, status, and vendor filters."""
    today = timezone.now().date()
    c1 = AssetCalibrationRecord.objects.create(
        tenant=tenant_a,
        instrument_tag="FLOW-METER-999",
        reference_standard_used="Yokogawa Reference Flow Rig",
        calibration_date=today,
        calibration_frequency_days=180,
        next_due_date=today + timedelta(days=180),
        setpoint_nominal=Decimal("250.0000"),
        as_found_reading=Decimal("265.0000"),
        as_left_reading=Decimal("250.2000"),
        calibration_result="pass_with_adjustment",
        service_vendor=vendor_party_a,
        status="valid",
    )
    c2 = AssetCalibrationRecord.objects.create(
        tenant=tenant_a,
        instrument_tag="TEMP-GAUGE-001",
        reference_standard_used="Hart Dry Well Calibrator",
        calibration_date=today,
        calibration_frequency_days=90,
        next_due_date=today + timedelta(days=90),
        setpoint_nominal=Decimal("100.0000"),
        as_found_reading=Decimal("115.0000"),
        as_left_reading=Decimal("114.5000"),
        calibration_result="fail_out_of_tolerance",
        status="voided",
    )
    url = reverse("assets:asset_calibration_record_list")

    # Filter q
    resp_q = client_a.get(url, {"q": "FLOW-METER"})
    assert resp_q.status_code == 200
    pks_q = [c.pk for c in resp_q.context["calibration_records"]]
    assert c1.pk in pks_q
    assert c2.pk not in pks_q

    # Filter calibration_result
    resp_res = client_a.get(url, {"calibration_result": "fail_out_of_tolerance"})
    assert resp_res.status_code == 200
    pks_r = [c.pk for c in resp_res.context["calibration_records"]]
    assert c2.pk in pks_r
    assert c1.pk not in pks_r

    # Filter status
    resp_stat = client_a.get(url, {"status": "voided"})
    assert resp_stat.status_code == 200
    pks_st = [c.pk for c in resp_stat.context["calibration_records"]]
    assert c2.pk in pks_st
    assert c1.pk not in pks_st

    # Filter vendor
    resp_v = client_a.get(url, {"vendor": str(vendor_party_a.pk)})
    assert resp_v.status_code == 200
    pks_v = [c.pk for c in resp_v.context["calibration_records"]]
    assert c1.pk in pks_v
    assert c2.pk not in pks_v


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_list_junk_params(client_a, calibration_record_a):
    """asset_calibration_record_list handles junk parameters safely."""
    url = reverse("assets:asset_calibration_record_list")
    resp = client_a.get(url, {
        "vendor": "not_an_int",
        "calibration_result": "invalid_result",
        "status": "bogus_status",
        "page": "junk_page",
    })
    assert resp.status_code == 200
    assert "calibration_records" in resp.context


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_list_pagination(client_a, tenant_a):
    """asset_calibration_record_list paginates cleanly at 15 items per page."""
    today = timezone.now().date()
    for i in range(16):
        AssetCalibrationRecord.objects.create(
            tenant=tenant_a,
            instrument_tag=f"INST-PAGIN-{i}",
            reference_standard_used="Fluke 754",
            calibration_date=today,
            next_due_date=today + timedelta(days=365),
            setpoint_nominal=Decimal("50.0000"),
            as_found_reading=Decimal("50.0000"),
            as_left_reading=Decimal("50.0000"),
        )
    url = reverse("assets:asset_calibration_record_list")
    resp = client_a.get(url, {"page": "2"})
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 2
    assert resp.context["is_paginated"] is True


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_detail_success(client_a, calibration_record_a):
    """asset_calibration_record_detail returns 200 with calibration context."""
    url = reverse("assets:asset_calibration_record_detail", args=[calibration_record_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["calibration"] == calibration_record_a
    assert calibration_record_a.number in resp.content.decode()


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_detail_cross_tenant_404(client_a, calibration_record_b):
    """asset_calibration_record_detail prevents cross-tenant access with 404."""
    url = reverse("assets:asset_calibration_record_detail", args=[calibration_record_b.pk])
    resp = client_a.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_create_get(client_a):
    """asset_calibration_record_create GET renders form with is_edit=False."""
    url = reverse("assets:asset_calibration_record_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["is_edit"] is False
    assert resp.context["calibration"] is None


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_create_post_success(client_a, tenant_a, fixed_asset_a, admin_user):
    """asset_calibration_record_create POST valid data creates record and sets calibrated_by."""
    url = reverse("assets:asset_calibration_record_create")
    data = _asset_reliability_views_calibration_payload(
        fixed_asset=fixed_asset_a,
        instrument_tag="TEST-PT-CREAT-01",
    )
    resp = client_a.post(url, data=data)
    assert resp.status_code == 302
    created = AssetCalibrationRecord.objects.filter(tenant=tenant_a, instrument_tag="TEST-PT-CREAT-01").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.calibrated_by == admin_user
    assert resp.url == reverse("assets:asset_calibration_record_detail", args=[created.pk])


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_create_post_invalid(client_a):
    """asset_calibration_record_create POST invalid data returns 200 with errors."""
    url = reverse("assets:asset_calibration_record_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_edit_get(client_a, calibration_record_a):
    """asset_calibration_record_edit GET renders form with is_edit=True."""
    url = reverse("assets:asset_calibration_record_edit", args=[calibration_record_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["is_edit"] is True
    assert resp.context["calibration"] == calibration_record_a


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_edit_post_success(client_a, calibration_record_a):
    """asset_calibration_record_edit POST valid update redirects to detail."""
    url = reverse("assets:asset_calibration_record_edit", args=[calibration_record_a.pk])
    data = _asset_reliability_views_calibration_payload(
        instrument_tag="PT-UPDATED-99",
        as_left_reading="100.0050",
    )
    resp = client_a.post(url, data=data)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_calibration_record_detail", args=[calibration_record_a.pk])
    calibration_record_a.refresh_from_db()
    assert calibration_record_a.instrument_tag == "PT-UPDATED-99"
    assert calibration_record_a.as_left_reading == Decimal("100.0050")


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_edit_post_invalid(client_a, calibration_record_a):
    """asset_calibration_record_edit POST invalid data returns 200."""
    url = reverse("assets:asset_calibration_record_edit", args=[calibration_record_a.pk])
    resp = client_a.post(url, data={"instrument_tag": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_edit_cross_tenant_404(client_a, calibration_record_b):
    """asset_calibration_record_edit denies cross-tenant access with 404."""
    url = reverse("assets:asset_calibration_record_edit", args=[calibration_record_b.pk])
    resp = client_a.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_delete_method_not_allowed(client_a, calibration_record_a):
    """asset_calibration_record_delete rejects GET requests with 405."""
    url = reverse("assets:asset_calibration_record_delete", args=[calibration_record_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_delete_non_admin_forbidden(member_client, calibration_record_a):
    """asset_calibration_record_delete denies non-tenant-admin users with 403."""
    url = reverse("assets:asset_calibration_record_delete", args=[calibration_record_a.pk])
    resp = member_client.post(url)
    assert resp.status_code == 403


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_delete_admin_success(client_a, calibration_record_a):
    """asset_calibration_record_delete removes record and redirects to list."""
    url = reverse("assets:asset_calibration_record_delete", args=[calibration_record_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_calibration_record_list")
    assert not AssetCalibrationRecord.objects.filter(pk=calibration_record_a.pk).exists()


@pytest.mark.django_db
def test_asset_reliability_views_calibration_record_quarantine_permissions(client_a, member_client, calibration_record_a):
    """asset_calibration_record_quarantine requires tenant admin and transitions status to voided/quarantined."""
    url = reverse("assets:asset_calibration_record_quarantine", args=[calibration_record_a.pk])

    # GET rejected with 405
    assert client_a.get(url).status_code == 405

    # Non-admin gets 403
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403

    # Admin succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    calibration_record_a.refresh_from_db()
    assert calibration_record_a.calibration_result == "quarantined"
    assert calibration_record_a.status == "voided"


# ==============================================================================
# 5. Security & Authentication Checks
# ==============================================================================

@pytest.mark.django_db
def test_asset_reliability_views_unauthenticated_redirects(client, condition_assessment_a, telemetry_reading_a, failure_mode_a, calibration_record_a):
    """Unauthenticated users must be redirected to login across all 4 reliability entities."""
    endpoints = [
        reverse("assets:asset_condition_assessment_list"),
        reverse("assets:asset_condition_assessment_create"),
        reverse("assets:asset_condition_assessment_detail", args=[condition_assessment_a.pk]),
        reverse("assets:asset_telemetry_reading_list"),
        reverse("assets:asset_telemetry_reading_create"),
        reverse("assets:asset_telemetry_reading_detail", args=[telemetry_reading_a.pk]),
        reverse("assets:asset_failure_mode_list"),
        reverse("assets:asset_failure_mode_create"),
        reverse("assets:asset_failure_mode_detail", args=[failure_mode_a.pk]),
        reverse("assets:asset_calibration_record_list"),
        reverse("assets:asset_calibration_record_create"),
        reverse("assets:asset_calibration_record_detail", args=[calibration_record_a.pk]),
    ]
    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url or "login" in resp.url
