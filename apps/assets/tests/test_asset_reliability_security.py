"""Security, multi-tenant isolation, authorization, IDOR defense, and audit test suite
for Sub-module 11.7: Asset Reliability & Condition Monitoring.

Covers all 28 views across the 4 entities:
1. Multi-Tenant Isolation & IDOR Defense (assert 404 across detail, edit, delete, custom actions, and reverse IDOR)
2. List Isolation (assert zero cross-tenant contamination in list views)
3. Role-Based Access Control (RBAC) & Privileged Gates (@tenant_admin_required vs standard member)
4. Cross-Tenant Foreign Key Injection Prevention (reject_foreign across all foreign keys)
5. Authentication Enforcement (assert 302 login redirect across all 28 endpoints)
6. Mass Assignment & State Tampering Resistance (tenant, number, status overrides are ignored)
7. Audit Log Generation (assert immutable AuditLog rows on CRUD and workflow transitions)
8. HTTP Method Guards (require_POST on state-mutating actions)
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    AssetCategory,
    AssetConditionAssessment,
    AssetTelemetryReading,
    AssetFailureMode,
    AssetCalibrationRecord,
    AssetMaintenanceRequest,
    AssetMaintenanceSchedule,
)
from apps.core.models import AuditLog

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Payload Factories (prefixed with _asset_reliability_security_)
# ==============================================================================

def _asset_reliability_security_condition_payload(fixed_asset=None, operational_asset=None, category=None, inspector=None, vendor=None, **overrides):
    today = timezone.now().date()
    payload = {
        "title": "Comprehensive Ultrasonic Integrity Analysis",
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
        "findings": "Minor surface wear detected. Shell thickness within allowable tolerance limits.",
        "recommendations": "Continue normal operation; re-measure during next scheduled annual turnaround.",
        "followup_required": False,
    }
    payload.update(overrides)
    return payload


def _asset_reliability_security_telemetry_payload(fixed_asset=None, operational_asset=None, user=None, **overrides):
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


def _asset_reliability_security_failure_mode_payload(fixed_asset=None, operational_asset=None, category=None, schedule=None, user=None, **overrides):
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


def _asset_reliability_security_calibration_payload(fixed_asset=None, operational_asset=None, user=None, vendor=None, doc=None, **overrides):
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
        "notes": "Ambient conditions: 22C, 45% RH. Zero and span verified per standard SOP.",
    }
    payload.update(overrides)
    return payload


# ==============================================================================
# 1. Multi-Tenant Isolation & IDOR Defense (assert 404)
# ==============================================================================

def test_asset_reliability_security_idor_condition_assessment_detail_returns_404(client_a, condition_assessment_b):
    """Tenant A client requesting Tenant B condition assessment detail returns 404."""
    url = reverse("assets:asset_condition_assessment_detail", args=[condition_assessment_b.pk])
    assert client_a.get(url).status_code == 404


def test_asset_reliability_security_idor_condition_assessment_edit_returns_404(client_a, condition_assessment_b):
    """Tenant A client requesting Tenant B condition assessment edit returns 404 on GET and POST."""
    url = reverse("assets:asset_condition_assessment_edit", args=[condition_assessment_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"title": "Hacked Assessment Title"}).status_code == 404


def test_asset_reliability_security_idor_condition_assessment_delete_returns_404(client_a, condition_assessment_b):
    """Tenant A admin client attempting to delete Tenant B condition assessment returns 404."""
    url = reverse("assets:asset_condition_assessment_delete", args=[condition_assessment_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetConditionAssessment.objects.filter(pk=condition_assessment_b.pk).exists()


def test_asset_reliability_security_idor_condition_assessment_actions_return_404(client_a, condition_assessment_b):
    """Tenant A client calling workflow actions on Tenant B assessment returns 404."""
    actions = [
        "assets:asset_condition_assessment_complete",
        "assets:asset_condition_assessment_review",
        "assets:asset_condition_assessment_trigger_request",
    ]
    for action_name in actions:
        url = reverse(action_name, args=[condition_assessment_b.pk])
        resp = client_a.post(url)
        assert resp.status_code == 404, f"Action {action_name} failed to return 404 for cross-tenant IDOR"


def test_asset_reliability_security_idor_telemetry_reading_detail_returns_404(client_a, telemetry_reading_b):
    """Tenant A client requesting Tenant B telemetry reading detail returns 404."""
    url = reverse("assets:asset_telemetry_reading_detail", args=[telemetry_reading_b.pk])
    assert client_a.get(url).status_code == 404


def test_asset_reliability_security_idor_telemetry_reading_edit_returns_404(client_a, telemetry_reading_b):
    """Tenant A client requesting Tenant B telemetry reading edit returns 404 on GET and POST."""
    url = reverse("assets:asset_telemetry_reading_edit", args=[telemetry_reading_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"sensor_identifier": "HACKED-SENSOR"}).status_code == 404


def test_asset_reliability_security_idor_telemetry_reading_delete_returns_404(client_a, telemetry_reading_b):
    """Tenant A admin client attempting to delete Tenant B telemetry reading returns 404."""
    url = reverse("assets:asset_telemetry_reading_delete", args=[telemetry_reading_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetTelemetryReading.objects.filter(pk=telemetry_reading_b.pk).exists()


def test_asset_reliability_security_idor_telemetry_reading_actions_return_404(client_a, telemetry_reading_b):
    """Tenant A client calling actions on Tenant B telemetry reading returns 404."""
    actions = [
        "assets:asset_telemetry_reading_flag_anomaly",
        "assets:asset_telemetry_reading_trigger_request",
    ]
    for action_name in actions:
        url = reverse(action_name, args=[telemetry_reading_b.pk])
        resp = client_a.post(url)
        assert resp.status_code == 404, f"Action {action_name} failed to return 404 for cross-tenant IDOR"


def test_asset_reliability_security_idor_failure_mode_detail_returns_404(client_a, failure_mode_b):
    """Tenant A client requesting Tenant B failure mode detail returns 404."""
    url = reverse("assets:asset_failure_mode_detail", args=[failure_mode_b.pk])
    assert client_a.get(url).status_code == 404


def test_asset_reliability_security_idor_failure_mode_edit_returns_404(client_a, failure_mode_b):
    """Tenant A client requesting Tenant B failure mode edit returns 404 on GET and POST."""
    url = reverse("assets:asset_failure_mode_edit", args=[failure_mode_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"component_subsystem": "Hacked Component"}).status_code == 404


def test_asset_reliability_security_idor_failure_mode_delete_returns_404(client_a, failure_mode_b):
    """Tenant A admin client attempting to delete Tenant B failure mode returns 404."""
    url = reverse("assets:asset_failure_mode_delete", args=[failure_mode_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetFailureMode.objects.filter(pk=failure_mode_b.pk).exists()


def test_asset_reliability_security_idor_failure_mode_actions_return_404(client_a, failure_mode_b):
    """Tenant A client calling actions on Tenant B failure mode returns 404."""
    actions = [
        "assets:asset_failure_mode_activate",
        "assets:asset_failure_mode_archive",
    ]
    for action_name in actions:
        url = reverse(action_name, args=[failure_mode_b.pk])
        resp = client_a.post(url)
        assert resp.status_code == 404, f"Action {action_name} failed to return 404 for cross-tenant IDOR"


def test_asset_reliability_security_idor_calibration_record_detail_returns_404(client_a, calibration_record_b):
    """Tenant A client requesting Tenant B calibration record detail returns 404."""
    url = reverse("assets:asset_calibration_record_detail", args=[calibration_record_b.pk])
    assert client_a.get(url).status_code == 404


def test_asset_reliability_security_idor_calibration_record_edit_returns_404(client_a, calibration_record_b):
    """Tenant A client requesting Tenant B calibration record edit returns 404 on GET and POST."""
    url = reverse("assets:asset_calibration_record_edit", args=[calibration_record_b.pk])
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"instrument_tag": "HACKED-TAG"}).status_code == 404


def test_asset_reliability_security_idor_calibration_record_delete_returns_404(client_a, calibration_record_b):
    """Tenant A admin client attempting to delete Tenant B calibration record returns 404."""
    url = reverse("assets:asset_calibration_record_delete", args=[calibration_record_b.pk])
    response = client_a.post(url)
    assert response.status_code == 404
    assert AssetCalibrationRecord.objects.filter(pk=calibration_record_b.pk).exists()


def test_asset_reliability_security_idor_calibration_record_quarantine_returns_404(client_a, calibration_record_b):
    """Tenant A client calling quarantine on Tenant B calibration record returns 404."""
    url = reverse("assets:asset_calibration_record_quarantine", args=[calibration_record_b.pk])
    resp = client_a.post(url)
    assert resp.status_code == 404


def test_asset_reliability_security_reverse_idor(client_b, condition_assessment_a, telemetry_reading_a, failure_mode_a, calibration_record_a):
    """Tenant B user accessing Tenant A records returns 404 across detail, edit, delete, and actions."""
    # Condition Assessment
    assert client_b.get(reverse("assets:asset_condition_assessment_detail", args=[condition_assessment_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_condition_assessment_edit", args=[condition_assessment_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_condition_assessment_delete", args=[condition_assessment_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_condition_assessment_complete", args=[condition_assessment_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_condition_assessment_review", args=[condition_assessment_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_condition_assessment_trigger_request", args=[condition_assessment_a.pk])).status_code == 404

    # Telemetry Reading
    assert client_b.get(reverse("assets:asset_telemetry_reading_detail", args=[telemetry_reading_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_telemetry_reading_edit", args=[telemetry_reading_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_telemetry_reading_delete", args=[telemetry_reading_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_telemetry_reading_flag_anomaly", args=[telemetry_reading_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_telemetry_reading_trigger_request", args=[telemetry_reading_a.pk])).status_code == 404

    # Failure Mode
    assert client_b.get(reverse("assets:asset_failure_mode_detail", args=[failure_mode_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_failure_mode_edit", args=[failure_mode_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_failure_mode_delete", args=[failure_mode_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_failure_mode_activate", args=[failure_mode_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_failure_mode_archive", args=[failure_mode_a.pk])).status_code == 404

    # Calibration Record
    assert client_b.get(reverse("assets:asset_calibration_record_detail", args=[calibration_record_a.pk])).status_code == 404
    assert client_b.get(reverse("assets:asset_calibration_record_edit", args=[calibration_record_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_calibration_record_delete", args=[calibration_record_a.pk])).status_code == 404
    assert client_b.post(reverse("assets:asset_calibration_record_quarantine", args=[calibration_record_a.pk])).status_code == 404


def test_asset_reliability_security_list_isolation(client_a, client_b, condition_assessment_a, condition_assessment_b,
                                                  telemetry_reading_a, telemetry_reading_b, failure_mode_a,
                                                  failure_mode_b, calibration_record_a, calibration_record_b):
    """List views strictly isolate data between Tenant A and Tenant B."""
    # 1. Condition Assessments
    resp_a = client_a.get(reverse("assets:asset_condition_assessment_list"))
    assert resp_a.status_code == 200
    items_a = list(resp_a.context["condition_assessments"])
    assert condition_assessment_a in items_a
    assert condition_assessment_b not in items_a
    assert condition_assessment_b.title not in resp_a.content.decode()

    resp_b = client_b.get(reverse("assets:asset_condition_assessment_list"))
    assert resp_b.status_code == 200
    items_b = list(resp_b.context["condition_assessments"])
    assert condition_assessment_b in items_b
    assert condition_assessment_a not in items_b

    # 2. Telemetry Readings
    resp_tel_a = client_a.get(reverse("assets:asset_telemetry_reading_list"))
    assert resp_tel_a.status_code == 200
    tel_items_a = list(resp_tel_a.context["telemetry_readings"])
    assert telemetry_reading_a in tel_items_a
    assert telemetry_reading_b not in tel_items_a

    resp_tel_b = client_b.get(reverse("assets:asset_telemetry_reading_list"))
    assert resp_tel_b.status_code == 200
    tel_items_b = list(resp_tel_b.context["telemetry_readings"])
    assert telemetry_reading_b in tel_items_b
    assert telemetry_reading_a not in tel_items_b

    # 3. Failure Modes
    resp_fm_a = client_a.get(reverse("assets:asset_failure_mode_list"))
    assert resp_fm_a.status_code == 200
    fm_items_a = list(resp_fm_a.context["failure_modes"])
    assert failure_mode_a in fm_items_a
    assert failure_mode_b not in fm_items_a

    resp_fm_b = client_b.get(reverse("assets:asset_failure_mode_list"))
    assert resp_fm_b.status_code == 200
    fm_items_b = list(resp_fm_b.context["failure_modes"])
    assert failure_mode_b in fm_items_b
    assert failure_mode_a not in fm_items_b

    # 4. Calibration Records
    resp_cal_a = client_a.get(reverse("assets:asset_calibration_record_list"))
    assert resp_cal_a.status_code == 200
    cal_items_a = list(resp_cal_a.context["calibration_records"])
    assert calibration_record_a in cal_items_a
    assert calibration_record_b not in cal_items_a

    resp_cal_b = client_b.get(reverse("assets:asset_calibration_record_list"))
    assert resp_cal_b.status_code == 200
    cal_items_b = list(resp_cal_b.context["calibration_records"])
    assert calibration_record_b in cal_items_b
    assert calibration_record_a not in cal_items_b


# ==============================================================================
# 2. Role-Based Access Control (RBAC) & Privileged Gates
# ==============================================================================

def test_asset_reliability_security_rbac_condition_assessment_delete_admin_only(member_client, client_a, condition_assessment_a):
    """condition_assessment_delete requires tenant admin role; member receives 403."""
    url = reverse("assets:asset_condition_assessment_delete", args=[condition_assessment_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    assert AssetConditionAssessment.objects.filter(pk=condition_assessment_a.pk).exists()

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not AssetConditionAssessment.objects.filter(pk=condition_assessment_a.pk).exists()


def test_asset_reliability_security_rbac_condition_assessment_review_admin_only(member_client, client_a, condition_assessment_a):
    """condition_assessment_review requires tenant admin role; member receives 403."""
    url = reverse("assets:asset_condition_assessment_review", args=[condition_assessment_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    condition_assessment_a.refresh_from_db()
    assert condition_assessment_a.status == "draft"

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    condition_assessment_a.refresh_from_db()
    assert condition_assessment_a.status == "reviewed"


def test_asset_reliability_security_rbac_telemetry_reading_delete_admin_only(member_client, client_a, telemetry_reading_a):
    """telemetry_reading_delete requires tenant admin role; member receives 403."""
    url = reverse("assets:asset_telemetry_reading_delete", args=[telemetry_reading_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    assert AssetTelemetryReading.objects.filter(pk=telemetry_reading_a.pk).exists()

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not AssetTelemetryReading.objects.filter(pk=telemetry_reading_a.pk).exists()


def test_asset_reliability_security_rbac_failure_mode_delete_admin_only(member_client, client_a, failure_mode_a):
    """failure_mode_delete requires tenant admin role; member receives 403."""
    url = reverse("assets:asset_failure_mode_delete", args=[failure_mode_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    assert AssetFailureMode.objects.filter(pk=failure_mode_a.pk).exists()

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not AssetFailureMode.objects.filter(pk=failure_mode_a.pk).exists()


def test_asset_reliability_security_rbac_failure_mode_archive_admin_only(member_client, client_a, failure_mode_a):
    """failure_mode_archive requires tenant admin role; member receives 403."""
    url = reverse("assets:asset_failure_mode_archive", args=[failure_mode_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    failure_mode_a.refresh_from_db()
    assert failure_mode_a.status == "draft"

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    failure_mode_a.refresh_from_db()
    assert failure_mode_a.status == "archived"


def test_asset_reliability_security_rbac_calibration_record_delete_admin_only(member_client, client_a, calibration_record_a):
    """calibration_record_delete requires tenant admin role; member receives 403."""
    url = reverse("assets:asset_calibration_record_delete", args=[calibration_record_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    assert AssetCalibrationRecord.objects.filter(pk=calibration_record_a.pk).exists()

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    assert not AssetCalibrationRecord.objects.filter(pk=calibration_record_a.pk).exists()


def test_asset_reliability_security_rbac_calibration_record_quarantine_admin_only(member_client, client_a, calibration_record_a):
    """calibration_record_quarantine requires tenant admin role; member receives 403."""
    url = reverse("assets:asset_calibration_record_quarantine", args=[calibration_record_a.pk])
    # Member attempt blocked
    resp_member = member_client.post(url)
    assert resp_member.status_code == 403
    calibration_record_a.refresh_from_db()
    assert calibration_record_a.calibration_result != "quarantined"

    # Admin attempt succeeds
    resp_admin = client_a.post(url)
    assert resp_admin.status_code == 302
    calibration_record_a.refresh_from_db()
    assert calibration_record_a.calibration_result == "quarantined"
    assert calibration_record_a.status == "voided"


def test_asset_reliability_security_rbac_member_permitted_actions(member_client, condition_assessment_a, telemetry_reading_a, failure_mode_a):
    """Non-admin members are permitted to execute standard operational actions."""
    # 1. Condition assessment complete
    url_complete = reverse("assets:asset_condition_assessment_complete", args=[condition_assessment_a.pk])
    resp1 = member_client.post(url_complete)
    assert resp1.status_code == 302
    condition_assessment_a.refresh_from_db()
    assert condition_assessment_a.status == "completed"

    # 2. Condition assessment trigger request
    url_trig_cas = reverse("assets:asset_condition_assessment_trigger_request", args=[condition_assessment_a.pk])
    resp2 = member_client.post(url_trig_cas)
    assert resp2.status_code == 302
    condition_assessment_a.refresh_from_db()
    assert condition_assessment_a.triggered_maintenance_request is not None

    # 3. Telemetry flag anomaly
    url_flag = reverse("assets:asset_telemetry_reading_flag_anomaly", args=[telemetry_reading_a.pk])
    resp3 = member_client.post(url_flag)
    assert resp3.status_code == 302
    telemetry_reading_a.refresh_from_db()
    assert telemetry_reading_a.is_anomaly is True

    # 4. Telemetry trigger request
    url_trig_tel = reverse("assets:asset_telemetry_reading_trigger_request", args=[telemetry_reading_a.pk])
    resp4 = member_client.post(url_trig_tel)
    assert resp4.status_code == 302
    telemetry_reading_a.refresh_from_db()
    assert telemetry_reading_a.triggered_maintenance_request is not None

    # 5. Failure mode activate
    url_act = reverse("assets:asset_failure_mode_activate", args=[failure_mode_a.pk])
    resp5 = member_client.post(url_act)
    assert resp5.status_code == 302
    failure_mode_a.refresh_from_db()
    assert failure_mode_a.status == "active"


# ==============================================================================
# 3. Cross-Tenant Foreign Key Injection Prevention
# ==============================================================================

def test_asset_reliability_security_fk_injection_condition_assessment_fixed_asset_rejected(client_a, fixed_asset_b):
    """Attempting to bind Tenant B's FixedAsset in Tenant A condition assessment fails validation."""
    url = reverse("assets:asset_condition_assessment_create")
    payload = _asset_reliability_security_condition_payload(fixed_asset=fixed_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_condition_assessment_operational_asset_rejected(client_a, operational_asset_b):
    """Attempting to bind Tenant B's OperationalAsset in Tenant A condition assessment fails validation."""
    url = reverse("assets:asset_condition_assessment_create")
    payload = _asset_reliability_security_condition_payload(operational_asset=operational_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "operational_asset" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_condition_assessment_category_rejected(client_a, category_root_b):
    """Attempting to bind Tenant B's AssetCategory in Tenant A condition assessment fails validation."""
    url = reverse("assets:asset_condition_assessment_create")
    payload = _asset_reliability_security_condition_payload(category=category_root_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "asset_category" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_condition_assessment_inspector_rejected(client_a, admin_b):
    """Attempting to bind Tenant B's User as inspector in Tenant A condition assessment fails validation."""
    url = reverse("assets:asset_condition_assessment_create")
    payload = _asset_reliability_security_condition_payload(inspector=admin_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "inspector" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_condition_assessment_vendor_rejected(client_a, vendor_party_b):
    """Attempting to bind Tenant B's Vendor in Tenant A condition assessment fails validation."""
    url = reverse("assets:asset_condition_assessment_create")
    payload = _asset_reliability_security_condition_payload(vendor=vendor_party_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "external_inspector" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_telemetry_reading_fixed_asset_rejected(client_a, fixed_asset_b):
    """Attempting to bind Tenant B's FixedAsset in Tenant A telemetry reading fails validation."""
    url = reverse("assets:asset_telemetry_reading_create")
    payload = _asset_reliability_security_telemetry_payload(fixed_asset=fixed_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_telemetry_reading_operational_asset_rejected(client_a, operational_asset_b):
    """Attempting to bind Tenant B's OperationalAsset in Tenant A telemetry reading fails validation."""
    url = reverse("assets:asset_telemetry_reading_create")
    payload = _asset_reliability_security_telemetry_payload(operational_asset=operational_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "operational_asset" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_telemetry_reading_recorded_by_rejected(client_a, admin_b):
    """Attempting to bind Tenant B's User in Tenant A telemetry reading fails validation."""
    url = reverse("assets:asset_telemetry_reading_create")
    payload = _asset_reliability_security_telemetry_payload(user=admin_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "recorded_by" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_failure_mode_fixed_asset_rejected(client_a, fixed_asset_b):
    """Attempting to bind Tenant B's FixedAsset in Tenant A failure mode fails validation."""
    url = reverse("assets:asset_failure_mode_create")
    payload = _asset_reliability_security_failure_mode_payload(fixed_asset=fixed_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_failure_mode_operational_asset_rejected(client_a, operational_asset_b):
    """Attempting to bind Tenant B's OperationalAsset in Tenant A failure mode fails validation."""
    url = reverse("assets:asset_failure_mode_create")
    payload = _asset_reliability_security_failure_mode_payload(operational_asset=operational_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "operational_asset" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_failure_mode_category_rejected(client_a, category_root_b):
    """Attempting to bind Tenant B's AssetCategory in Tenant A failure mode fails validation."""
    url = reverse("assets:asset_failure_mode_create")
    payload = _asset_reliability_security_failure_mode_payload(category=category_root_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "asset_category" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_failure_mode_schedule_rejected(client_a, maintenance_schedule_b):
    """Attempting to bind Tenant B's MaintenanceSchedule in Tenant A failure mode fails validation."""
    url = reverse("assets:asset_failure_mode_create")
    payload = _asset_reliability_security_failure_mode_payload(schedule=maintenance_schedule_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "linked_maintenance_schedule" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_failure_mode_assessed_by_rejected(client_a, admin_b):
    """Attempting to bind Tenant B's User in Tenant A failure mode fails validation."""
    url = reverse("assets:asset_failure_mode_create")
    payload = _asset_reliability_security_failure_mode_payload(user=admin_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "assessed_by" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_calibration_record_fixed_asset_rejected(client_a, fixed_asset_b):
    """Attempting to bind Tenant B's FixedAsset in Tenant A calibration record fails validation."""
    url = reverse("assets:asset_calibration_record_create")
    payload = _asset_reliability_security_calibration_payload(fixed_asset=fixed_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "fixed_asset" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_calibration_record_operational_asset_rejected(client_a, operational_asset_b):
    """Attempting to bind Tenant B's OperationalAsset in Tenant A calibration record fails validation."""
    url = reverse("assets:asset_calibration_record_create")
    payload = _asset_reliability_security_calibration_payload(operational_asset=operational_asset_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "operational_asset" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_calibration_record_calibrated_by_rejected(client_a, admin_b):
    """Attempting to bind Tenant B's User in Tenant A calibration record fails validation."""
    url = reverse("assets:asset_calibration_record_create")
    payload = _asset_reliability_security_calibration_payload(user=admin_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "calibrated_by" in response.context["form"].errors


def test_asset_reliability_security_fk_injection_calibration_record_vendor_rejected(client_a, vendor_party_b):
    """Attempting to bind Tenant B's Vendor in Tenant A calibration record fails validation."""
    url = reverse("assets:asset_calibration_record_create")
    payload = _asset_reliability_security_calibration_payload(vendor=vendor_party_b)
    response = client_a.post(url, data=payload)
    assert response.status_code == 200
    assert "service_vendor" in response.context["form"].errors


# ==============================================================================
# 4. Authentication Enforcement (Unauthenticated 302 Redirect to Login)
# ==============================================================================

def test_asset_reliability_security_unauthenticated_redirect_to_login(
    client, condition_assessment_a, telemetry_reading_a, failure_mode_a, calibration_record_a
):
    """Unauthenticated client is redirected to login for all 28 reliability endpoints."""
    endpoints = [
        # Condition Assessment (8 routes)
        reverse("assets:asset_condition_assessment_list"),
        reverse("assets:asset_condition_assessment_create"),
        reverse("assets:asset_condition_assessment_detail", args=[condition_assessment_a.pk]),
        reverse("assets:asset_condition_assessment_edit", args=[condition_assessment_a.pk]),
        reverse("assets:asset_condition_assessment_delete", args=[condition_assessment_a.pk]),
        reverse("assets:asset_condition_assessment_complete", args=[condition_assessment_a.pk]),
        reverse("assets:asset_condition_assessment_review", args=[condition_assessment_a.pk]),
        reverse("assets:asset_condition_assessment_trigger_request", args=[condition_assessment_a.pk]),

        # Telemetry Reading (7 routes)
        reverse("assets:asset_telemetry_reading_list"),
        reverse("assets:asset_telemetry_reading_create"),
        reverse("assets:asset_telemetry_reading_detail", args=[telemetry_reading_a.pk]),
        reverse("assets:asset_telemetry_reading_edit", args=[telemetry_reading_a.pk]),
        reverse("assets:asset_telemetry_reading_delete", args=[telemetry_reading_a.pk]),
        reverse("assets:asset_telemetry_reading_flag_anomaly", args=[telemetry_reading_a.pk]),
        reverse("assets:asset_telemetry_reading_trigger_request", args=[telemetry_reading_a.pk]),

        # Failure Mode (7 routes)
        reverse("assets:asset_failure_mode_list"),
        reverse("assets:asset_failure_mode_create"),
        reverse("assets:asset_failure_mode_detail", args=[failure_mode_a.pk]),
        reverse("assets:asset_failure_mode_edit", args=[failure_mode_a.pk]),
        reverse("assets:asset_failure_mode_delete", args=[failure_mode_a.pk]),
        reverse("assets:asset_failure_mode_activate", args=[failure_mode_a.pk]),
        reverse("assets:asset_failure_mode_archive", args=[failure_mode_a.pk]),

        # Calibration Record (6 routes)
        reverse("assets:asset_calibration_record_list"),
        reverse("assets:asset_calibration_record_create"),
        reverse("assets:asset_calibration_record_detail", args=[calibration_record_a.pk]),
        reverse("assets:asset_calibration_record_edit", args=[calibration_record_a.pk]),
        reverse("assets:asset_calibration_record_delete", args=[calibration_record_a.pk]),
        reverse("assets:asset_calibration_record_quarantine", args=[calibration_record_a.pk]),
    ]
    assert len(endpoints) == 28, f"Expected exactly 28 endpoints tested, found {len(endpoints)}"

    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 login redirect for GET {url}, got {resp.status_code}"
        assert "/accounts/login/" in resp.url or "login" in resp.url

        # POST attempt as unauthenticated
        resp_post = client.post(url, data={})
        assert resp_post.status_code == 302, f"Expected 302 login redirect for POST {url}, got {resp_post.status_code}"


# ==============================================================================
# 5. Mass Assignment & State Tampering Resistance
# ==============================================================================

def test_asset_reliability_security_mass_assignment_condition_assessment_create(client_a, tenant_a, tenant_b, fixed_asset_a):
    """Injected tenant, number, and status are strictly ignored on condition assessment create."""
    url = reverse("assets:asset_condition_assessment_create")
    malicious_payload = _asset_reliability_security_condition_payload(
        fixed_asset=fixed_asset_a,
        title="Tamper Assessment Create",
        # Malicious injected fields
        tenant=tenant_b.pk,
        number="ACAS-HACKED-9999",
        status="reviewed",
    )
    resp = client_a.post(url, data=malicious_payload)
    assert resp.status_code == 302

    created = AssetConditionAssessment.objects.filter(tenant=tenant_a, title="Tamper Assessment Create").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.number != "ACAS-HACKED-9999"
    assert created.number.startswith("ACAS-")
    assert created.status == "completed"  # Injected 'reviewed' status ignored; model default is 'completed'
    assert created.status != "reviewed"


def test_asset_reliability_security_mass_assignment_condition_assessment_edit(client_a, tenant_a, tenant_b, condition_assessment_a):
    """Injected tenant, number, and status are strictly ignored on condition assessment edit."""
    url = reverse("assets:asset_condition_assessment_edit", args=[condition_assessment_a.pk])
    original_number = condition_assessment_a.number

    malicious_payload = _asset_reliability_security_condition_payload(
        fixed_asset=condition_assessment_a.fixed_asset,
        title="Legitimate Assessment Update",
        # Injected overrides
        tenant=tenant_b.pk,
        number="ACAS-FORGED-0001",
        status="reviewed",
    )
    resp = client_a.post(url, data=malicious_payload)
    assert resp.status_code == 302

    condition_assessment_a.refresh_from_db()
    assert condition_assessment_a.title == "Legitimate Assessment Update"
    assert condition_assessment_a.tenant == tenant_a
    assert condition_assessment_a.number == original_number
    assert condition_assessment_a.status == "draft"


def test_asset_reliability_security_mass_assignment_telemetry_reading_create(client_a, tenant_a, tenant_b, fixed_asset_a):
    """Injected tenant and number are ignored on telemetry reading create."""
    url = reverse("assets:asset_telemetry_reading_create")
    malicious_payload = _asset_reliability_security_telemetry_payload(
        fixed_asset=fixed_asset_a,
        sensor_identifier="SENS-TAMPER-01",
        tenant=tenant_b.pk,
        number="ATEL-HACKED-9999",
    )
    resp = client_a.post(url, data=malicious_payload)
    assert resp.status_code == 302

    created = AssetTelemetryReading.objects.filter(tenant=tenant_a, sensor_identifier="SENS-TAMPER-01").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.number != "ATEL-HACKED-9999"
    assert created.number.startswith("ATEL-")


def test_asset_reliability_security_mass_assignment_telemetry_reading_edit(client_a, tenant_a, tenant_b, telemetry_reading_a):
    """Injected tenant and number are ignored on telemetry reading edit."""
    url = reverse("assets:asset_telemetry_reading_edit", args=[telemetry_reading_a.pk])
    original_number = telemetry_reading_a.number

    malicious_payload = _asset_reliability_security_telemetry_payload(
        fixed_asset=telemetry_reading_a.fixed_asset,
        sensor_identifier="SENS-VALID-UPDATE",
        tenant=tenant_b.pk,
        number="ATEL-OVERWRITE-777",
    )
    resp = client_a.post(url, data=malicious_payload)
    assert resp.status_code == 302

    telemetry_reading_a.refresh_from_db()
    assert telemetry_reading_a.sensor_identifier == "SENS-VALID-UPDATE"
    assert telemetry_reading_a.tenant == tenant_a
    assert telemetry_reading_a.number == original_number


def test_asset_reliability_security_mass_assignment_failure_mode_create(client_a, tenant_a, tenant_b, fixed_asset_a):
    """Injected tenant, number, status, and rpn are ignored on failure mode create."""
    url = reverse("assets:asset_failure_mode_create")
    malicious_payload = _asset_reliability_security_failure_mode_payload(
        fixed_asset=fixed_asset_a,
        component_subsystem="Tamper Bearing Component",
        severity_score=5,
        occurrence_score=4,
        detection_score=3,
        # Injected overrides
        tenant=tenant_b.pk,
        number="AFMA-HACKED-001",
        status="archived",
        rpn=999,
        risk_level="extreme",
    )
    resp = client_a.post(url, data=malicious_payload)
    assert resp.status_code == 302

    created = AssetFailureMode.objects.filter(tenant=tenant_a, component_subsystem="Tamper Bearing Component").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.number != "AFMA-HACKED-001"
    assert created.number.startswith("AFMA-")
    assert created.status == "active"  # Injected status ignored; default is active
    assert created.status != "archived"
    assert created.rpn == 60  # Correctly calculated 5 * 4 * 3 = 60, not 999
    assert created.risk_level == "low"  # Calculated from RPN 60, not 'extreme'


def test_asset_reliability_security_mass_assignment_failure_mode_edit(client_a, tenant_a, tenant_b, failure_mode_a):
    """Injected tenant, number, and status are ignored on failure mode edit."""
    url = reverse("assets:asset_failure_mode_edit", args=[failure_mode_a.pk])
    original_number = failure_mode_a.number

    malicious_payload = _asset_reliability_security_failure_mode_payload(
        fixed_asset=failure_mode_a.fixed_asset,
        component_subsystem="Verified Updated Subsystem",
        severity_score=4,
        occurrence_score=3,
        detection_score=2,
        # Injected overrides
        tenant=tenant_b.pk,
        number="AFMD-OVERWRITE-888",
        status="archived",
    )
    resp = client_a.post(url, data=malicious_payload)
    assert resp.status_code == 302

    failure_mode_a.refresh_from_db()
    assert failure_mode_a.component_subsystem == "Verified Updated Subsystem"
    assert failure_mode_a.tenant == tenant_a
    assert failure_mode_a.number == original_number
    assert failure_mode_a.status == "draft"  # Injected 'archived' ignored


def test_asset_reliability_security_mass_assignment_calibration_record_create(client_a, tenant_a, tenant_b, fixed_asset_a):
    """Injected tenant, number, and status are ignored on calibration record create."""
    url = reverse("assets:asset_calibration_record_create")
    malicious_payload = _asset_reliability_security_calibration_payload(
        fixed_asset=fixed_asset_a,
        instrument_tag="PT-TAMPER-01",
        # Injected overrides
        tenant=tenant_b.pk,
        number="ACAL-HACKED-9999",
        status="voided",
    )
    resp = client_a.post(url, data=malicious_payload)
    assert resp.status_code == 302

    created = AssetCalibrationRecord.objects.filter(tenant=tenant_a, instrument_tag="PT-TAMPER-01").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.number != "ACAL-HACKED-9999"
    assert created.number.startswith("ACAL-")
    assert created.status == "valid"  # Injected 'voided' ignored; default is valid


def test_asset_reliability_security_mass_assignment_calibration_record_edit(client_a, tenant_a, tenant_b, calibration_record_a):
    """Injected tenant, number, and status are ignored on calibration record edit."""
    url = reverse("assets:asset_calibration_record_edit", args=[calibration_record_a.pk])
    original_number = calibration_record_a.number

    malicious_payload = _asset_reliability_security_calibration_payload(
        fixed_asset=calibration_record_a.fixed_asset,
        instrument_tag="PT-VERIFIED-UPDATE",
        # Injected overrides
        tenant=tenant_b.pk,
        number="ACAL-OVERWRITE-555",
        status="voided",
    )
    resp = client_a.post(url, data=malicious_payload)
    assert resp.status_code == 302

    calibration_record_a.refresh_from_db()
    assert calibration_record_a.instrument_tag == "PT-VERIFIED-UPDATE"
    assert calibration_record_a.tenant == tenant_a
    assert calibration_record_a.number == original_number
    assert calibration_record_a.status == "valid"  # Injected 'voided' ignored


# ==============================================================================
# 6. Audit Log Generation
# ==============================================================================

def test_asset_reliability_security_audit_log_condition_assessment_lifecycle(client_a, tenant_a, admin_user, fixed_asset_a):
    """AuditLog rows are generated for condition assessment create, update, and delete."""
    # 1. Create
    url_create = reverse("assets:asset_condition_assessment_create")
    payload = _asset_reliability_security_condition_payload(fixed_asset=fixed_asset_a, title="Audit Lifecycle Test")
    resp_create = client_a.post(url_create, data=payload)
    assert resp_create.status_code == 302

    assessment = AssetConditionAssessment.objects.get(tenant=tenant_a, title="Audit Lifecycle Test")
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=assessment.pk,
    ).exists()

    # 2. Update
    url_edit = reverse("assets:asset_condition_assessment_edit", args=[assessment.pk])
    payload["title"] = "Audit Lifecycle Updated"
    resp_edit = client_a.post(url_edit, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=assessment.pk,
    ).exists()

    # 3. Delete
    url_delete = reverse("assets:asset_condition_assessment_delete", args=[assessment.pk])
    resp_del = client_a.post(url_delete)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=assessment.pk,
    ).exists()


def test_asset_reliability_security_audit_log_condition_assessment_actions(client_a, tenant_a, admin_user, condition_assessment_a):
    """AuditLog rows are generated for condition assessment workflow actions (complete, review, trigger_request)."""
    # 1. Complete action
    url_complete = reverse("assets:asset_condition_assessment_complete", args=[condition_assessment_a.pk])
    resp_comp = client_a.post(url_complete)
    assert resp_comp.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=condition_assessment_a.pk,
    ).exists()

    # 2. Review action
    url_review = reverse("assets:asset_condition_assessment_review", args=[condition_assessment_a.pk])
    resp_rev = client_a.post(url_review)
    assert resp_rev.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=condition_assessment_a.pk,
    ).count() >= 2

    # 3. Trigger Maintenance Request action
    url_trigger = reverse("assets:asset_condition_assessment_trigger_request", args=[condition_assessment_a.pk])
    resp_trig = client_a.post(url_trigger)
    assert resp_trig.status_code == 302

    condition_assessment_a.refresh_from_db()
    req = condition_assessment_a.triggered_maintenance_request
    assert req is not None
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=req.pk,
    ).exists()


def test_asset_reliability_security_audit_log_telemetry_reading_lifecycle(client_a, tenant_a, admin_user, fixed_asset_a):
    """AuditLog rows are generated for telemetry reading create, update, and delete."""
    # 1. Create
    url_create = reverse("assets:asset_telemetry_reading_create")
    payload = _asset_reliability_security_telemetry_payload(fixed_asset=fixed_asset_a, sensor_identifier="SENS-AUD-01")
    resp_create = client_a.post(url_create, data=payload)
    assert resp_create.status_code == 302

    reading = AssetTelemetryReading.objects.get(tenant=tenant_a, sensor_identifier="SENS-AUD-01")
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=reading.pk,
    ).exists()

    # 2. Update
    url_edit = reverse("assets:asset_telemetry_reading_edit", args=[reading.pk])
    payload["alert_notes"] = "Updated audit alert notes."
    resp_edit = client_a.post(url_edit, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=reading.pk,
    ).exists()

    # 3. Delete
    url_delete = reverse("assets:asset_telemetry_reading_delete", args=[reading.pk])
    resp_del = client_a.post(url_delete)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=reading.pk,
    ).exists()


def test_asset_reliability_security_audit_log_telemetry_reading_actions(client_a, tenant_a, admin_user, telemetry_reading_a):
    """AuditLog rows are generated for telemetry anomaly flagging and request triggering."""
    # 1. Flag anomaly
    url_flag = reverse("assets:asset_telemetry_reading_flag_anomaly", args=[telemetry_reading_a.pk])
    resp_flag = client_a.post(url_flag)
    assert resp_flag.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=telemetry_reading_a.pk,
    ).exists()

    # 2. Trigger maintenance request
    url_trig = reverse("assets:asset_telemetry_reading_trigger_request", args=[telemetry_reading_a.pk])
    resp_trig = client_a.post(url_trig)
    assert resp_trig.status_code == 302

    telemetry_reading_a.refresh_from_db()
    req = telemetry_reading_a.triggered_maintenance_request
    assert req is not None
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=req.pk,
    ).exists()


def test_asset_reliability_security_audit_log_failure_mode_lifecycle(client_a, tenant_a, admin_user, fixed_asset_a):
    """AuditLog rows are generated for failure mode create, update, and delete."""
    # 1. Create
    url_create = reverse("assets:asset_failure_mode_create")
    payload = _asset_reliability_security_failure_mode_payload(fixed_asset=fixed_asset_a, component_subsystem="Audited Subsystem")
    resp_create = client_a.post(url_create, data=payload)
    assert resp_create.status_code == 302

    fm = AssetFailureMode.objects.get(tenant=tenant_a, component_subsystem="Audited Subsystem")
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=fm.pk,
    ).exists()

    # 2. Update
    url_edit = reverse("assets:asset_failure_mode_edit", args=[fm.pk])
    payload["mitigation_task"] = "Updated mitigation schedule and task."
    resp_edit = client_a.post(url_edit, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=fm.pk,
    ).exists()

    # 3. Delete
    url_delete = reverse("assets:asset_failure_mode_delete", args=[fm.pk])
    resp_del = client_a.post(url_delete)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=fm.pk,
    ).exists()


def test_asset_reliability_security_audit_log_failure_mode_actions(client_a, tenant_a, admin_user, failure_mode_a):
    """AuditLog rows are generated for failure mode activate and archive actions."""
    # 1. Activate
    url_act = reverse("assets:asset_failure_mode_activate", args=[failure_mode_a.pk])
    resp_act = client_a.post(url_act)
    assert resp_act.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=failure_mode_a.pk,
    ).exists()

    # 2. Archive
    url_arch = reverse("assets:asset_failure_mode_archive", args=[failure_mode_a.pk])
    resp_arch = client_a.post(url_arch)
    assert resp_arch.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=failure_mode_a.pk,
    ).count() >= 2


def test_asset_reliability_security_audit_log_calibration_record_lifecycle(client_a, tenant_a, admin_user, fixed_asset_a):
    """AuditLog rows are generated for calibration record create, update, and delete."""
    # 1. Create
    url_create = reverse("assets:asset_calibration_record_create")
    payload = _asset_reliability_security_calibration_payload(fixed_asset=fixed_asset_a, instrument_tag="CAL-AUDIT-01")
    resp_create = client_a.post(url_create, data=payload)
    assert resp_create.status_code == 302

    cal = AssetCalibrationRecord.objects.get(tenant=tenant_a, instrument_tag="CAL-AUDIT-01")
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=cal.pk,
    ).exists()

    # 2. Update
    url_edit = reverse("assets:asset_calibration_record_edit", args=[cal.pk])
    payload["notes"] = "Updated metrology environmental records."
    resp_edit = client_a.post(url_edit, data=payload)
    assert resp_edit.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=cal.pk,
    ).exists()

    # 3. Delete
    url_delete = reverse("assets:asset_calibration_record_delete", args=[cal.pk])
    resp_del = client_a.post(url_delete)
    assert resp_del.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=cal.pk,
    ).exists()


def test_asset_reliability_security_audit_log_calibration_record_quarantine(client_a, tenant_a, admin_user, calibration_record_a):
    """AuditLog rows are generated for calibration quarantine action."""
    url_quarantine = reverse("assets:asset_calibration_record_quarantine", args=[calibration_record_a.pk])
    resp = client_a.post(url_quarantine)
    assert resp.status_code == 302

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=calibration_record_a.pk,
    ).exists()


# ==============================================================================
# 7. HTTP Method Guards (require_POST on actions & deletes)
# ==============================================================================

def test_asset_reliability_security_http_method_guards_require_post(
    client_a, condition_assessment_a, telemetry_reading_a, failure_mode_a, calibration_record_a
):
    """All state-mutating actions and deletes strictly require HTTP POST and return 405 on GET."""
    post_only_urls = [
        # Condition Assessment
        reverse("assets:asset_condition_assessment_delete", args=[condition_assessment_a.pk]),
        reverse("assets:asset_condition_assessment_complete", args=[condition_assessment_a.pk]),
        reverse("assets:asset_condition_assessment_review", args=[condition_assessment_a.pk]),
        reverse("assets:asset_condition_assessment_trigger_request", args=[condition_assessment_a.pk]),

        # Telemetry Reading
        reverse("assets:asset_telemetry_reading_delete", args=[telemetry_reading_a.pk]),
        reverse("assets:asset_telemetry_reading_flag_anomaly", args=[telemetry_reading_a.pk]),
        reverse("assets:asset_telemetry_reading_trigger_request", args=[telemetry_reading_a.pk]),

        # Failure Mode
        reverse("assets:asset_failure_mode_delete", args=[failure_mode_a.pk]),
        reverse("assets:asset_failure_mode_activate", args=[failure_mode_a.pk]),
        reverse("assets:asset_failure_mode_archive", args=[failure_mode_a.pk]),

        # Calibration Record
        reverse("assets:asset_calibration_record_delete", args=[calibration_record_a.pk]),
        reverse("assets:asset_calibration_record_quarantine", args=[calibration_record_a.pk]),
    ]

    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET on {url}, got {resp.status_code}"
