"""
Unit and integration test suite for Sub-module 11.13: Mobile Asset Management Views.

Covers all 4 entities across all standard CRUD and workflow operations:
1. MobileAssetInspection:
   - mobile_asset_inspection_list (GET 200, context variables, search ?q=, filters, junk params, pagination)
   - mobile_asset_inspection_detail (GET 200, context object, renders MINS identifier, cross-tenant IDOR 404)
   - mobile_asset_inspection_create (GET 200 form, POST valid -> 302 + AuditLog + tenant assignment, POST invalid 200)
   - mobile_asset_inspection_edit (GET 200 form, POST valid -> 302 + AuditLog + offline sync, cross-tenant 404)
   - mobile_asset_inspection_delete (POST 302 + AuditLog, GET 405 require_POST, cross-tenant 404)

2. FieldWorkOrder:
   - field_work_order_list (GET 200, context variables, search ?q=, status/priority/type filters, junk params, pagination)
   - field_work_order_detail (GET 200, context object, renders FWO identifier & work notes, cross-tenant IDOR 404)
   - field_work_order_create (GET 200 form, POST valid -> 302 + AuditLog + auto-arrival/completed/signed timestamps)
   - field_work_order_edit (GET 200 form, POST valid -> 302 + auto-populates signed_at on signature, cross-tenant 404)
   - field_work_order_delete (POST 302 + AuditLog, GET 405 require_POST, cross-tenant 404)

3. AssetScanLog:
   - asset_scan_log_list (GET 200, context variables, search ?q=, match/method/context filters, junk params, pagination)
   - asset_scan_log_detail (GET 200, context object, renders SCAN identifier & raw payload, cross-tenant IDOR 404)
   - asset_scan_log_create (GET 200 form, POST valid -> 302 + AuditLog + defaults scanned_by, POST invalid 200)
   - asset_scan_log_edit (GET 200 form, POST valid -> 302 + AuditLog, cross-tenant 404)
   - asset_scan_log_delete (POST 302 + AuditLog, GET 405 require_POST, cross-tenant 404)

4. AssetGeofenceEvent:
   - asset_geofence_event_list (GET 200, context variables, search ?q=, status/type/severity filters, junk params, pagination)
   - asset_geofence_event_detail (GET 200, context object, renders GEO identifier & fence name, cross-tenant IDOR 404)
   - asset_geofence_event_create (GET 200 form, POST valid -> 302 + AuditLog + tenant assignment, POST invalid 200)
   - asset_geofence_event_edit (GET 200 form, POST valid -> 302 + auto-populates acknowledged_by/at on resolve)
   - asset_geofence_event_delete (POST 302 + AuditLog, GET 405 require_POST, cross-tenant 404)

5. Security:
   - Unauthenticated access redirects to login for all endpoints.
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.assets.models import (
    AssetGeofenceEvent,
    AssetScanLog,
    FieldWorkOrder,
    MobileAssetInspection,
)
from apps.core.models import AuditLog

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (strictly prefixed with _mobile_asset_*)
# ==============================================================================

def _mobile_asset_create_inspection(tenant, asset, inspector, title="Test Inspection", **kwargs):
    """Instantiate a MobileAssetInspection record with sensible defaults."""
    data = {
        "tenant": tenant,
        "asset": asset,
        "inspector": inspector,
        "title": title,
        "inspection_type": "routine_pm",
        "overall_result": "pass",
        "condition_rating": 5,
        "status": "submitted",
    }
    data.update(kwargs)
    return MobileAssetInspection.objects.create(**data)


def _mobile_asset_create_work_order(tenant, asset, technician, title="Test Work Order", **kwargs):
    """Instantiate a FieldWorkOrder record with sensible defaults."""
    data = {
        "tenant": tenant,
        "asset": asset,
        "assigned_technician": technician,
        "title": title,
        "work_order_type": "scheduled_pm",
        "priority": "medium",
        "status": "dispatched",
    }
    data.update(kwargs)
    return FieldWorkOrder.objects.create(**data)


def _mobile_asset_create_scan_log(tenant, asset, user, payload="BARCODE-12345", **kwargs):
    """Instantiate an AssetScanLog record with sensible defaults."""
    data = {
        "tenant": tenant,
        "asset": asset,
        "scanned_by": user,
        "raw_payload": payload,
        "scan_context": "field_audit",
        "scan_method": "camera_qr",
        "match_status": "matched",
    }
    data.update(kwargs)
    return AssetScanLog.objects.create(**data)


def _mobile_asset_create_geofence_event(tenant, asset, fence_name="Perimeter Fence", **kwargs):
    """Instantiate an AssetGeofenceEvent record with sensible defaults."""
    data = {
        "tenant": tenant,
        "asset": asset,
        "fence_name": fence_name,
        "center_latitude": Decimal("37.774900"),
        "center_longitude": Decimal("-122.419400"),
        "radius_meters": 100,
        "recorded_latitude": Decimal("37.775000"),
        "recorded_longitude": Decimal("-122.419500"),
        "distance_from_center_m": 25.0,
        "event_type": "inside_perimeter",
        "severity": "info",
        "status": "open_alert",
    }
    data.update(kwargs)
    return AssetGeofenceEvent.objects.create(**data)


def _mobile_asset_inspection_payload(asset, inspector, fixed_asset=None, **overrides):
    """Build a complete valid payload for MobileAssetInspectionForm."""
    now_dt = timezone.now().strftime("%Y-%m-%dT%H:%M")
    today = timezone.now().date().isoformat()
    data = {
        "title": "Daily Pre-Shift Walkaround & Tire Check",
        "inspection_type": "pre_trip",
        "asset": str(asset.pk),
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "inspector": str(inspector.pk),
        "inspection_date": now_dt,
        "scheduled_date": today,
        "overall_result": "pass",
        "condition_rating": "4",
        "meter_reading": "1250.50",
        "checklist_summary": "Tires 80%, Fluids OK, Hydraulic lines clean.",
        "photo_url": "https://cdn.example.com/inspections/photo1.jpg",
        "photo_caption": "Front-right hydraulic ram seal verification",
        "voice_notes_transcription": "Walkaround completed. No leaks observed.",
        "corrective_action_required": False,
        "findings_summary": "All systems operating within acceptable parameters.",
        "gps_latitude": "37.774929",
        "gps_longitude": "-122.419416",
        "location_accuracy_m": "3.5",
        "client_sync_id": "c1a2b3c4-d5e6-7890-abcd-ef1234567890",
        "is_offline_captured": False,
        "status": "submitted",
    }
    data.update(overrides)
    return data


def _mobile_asset_work_order_payload(asset, technician, fixed_asset=None, maintenance_request=None, **overrides):
    """Build a complete valid payload for FieldWorkOrderForm."""
    now = timezone.now()
    start_dt = now.strftime("%Y-%m-%dT%H:%M")
    end_dt = (now + timezone.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")
    data = {
        "title": "Field Hydraulic Hose Replacement",
        "work_order_type": "emergency_repair",
        "priority": "high",
        "status": "dispatched",
        "asset": str(asset.pk),
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "assigned_technician": str(technician.pk),
        "maintenance_request": str(maintenance_request.pk) if maintenance_request else "",
        "scheduled_start": start_dt,
        "scheduled_end": end_dt,
        "labor_wrench_minutes": "180",
        "safety_lockout_confirmed": True,
        "parts_requisition_notes": "High-pressure hydraulic hose 1/2 in x 24 in, 2x O-rings",
        "estimated_parts_cost": "245.50",
        "work_performed_notes": "Replaced ruptured line and bled hydraulic system.",
        "signature_name": "Marcus Vance",
        "signature_designation": "Site Operations Supervisor",
        "dispatch_latitude": "37.774900",
        "dispatch_longitude": "-122.419400",
        "completion_latitude": "37.775100",
        "completion_longitude": "-122.419600",
        "client_sync_id": "f8a9b0c1-d2e3-4567-8901-abcdef123456",
        "is_offline_captured": False,
    }
    data.update(overrides)
    return data


def _mobile_asset_scan_log_payload(scanned_by, asset=None, **overrides):
    """Build a complete valid payload for AssetScanLogForm."""
    data = {
        "scanned_by": str(scanned_by.pk),
        "scan_context": "field_audit",
        "scan_method": "camera_qr",
        "raw_payload": "ACME-ASSET-QR-009876",
        "asset": str(asset.pk) if asset else "",
        "match_status": "matched",
        "gps_latitude": "37.774929",
        "gps_longitude": "-122.419416",
        "gps_accuracy_m": "4.2",
        "device_info": "Zebra TC57 Android 11",
        "notes": "Verified yard gate barcode label intact.",
        "client_sync_id": "a1b2c3d4-e5f6-7890-abcd-ef0123456789",
        "is_offline_captured": False,
    }
    data.update(overrides)
    return data


def _mobile_asset_geofence_event_payload(asset, acknowledged_by=None, **overrides):
    """Build a complete valid payload for AssetGeofenceEventForm."""
    data = {
        "asset": str(asset.pk),
        "fence_name": "Main Construction Yard Perimeter",
        "center_latitude": "37.774000",
        "center_longitude": "-122.419000",
        "radius_meters": "250",
        "recorded_latitude": "37.776500",
        "recorded_longitude": "-122.421500",
        "recorded_accuracy_m": "5.0",
        "distance_from_center_m": "320.5",
        "event_type": "perimeter_exit",
        "severity": "high",
        "status": "open_alert",
        "acknowledged_by": str(acknowledged_by.pk) if acknowledged_by else "",
        "resolution_notes": "Asset flagged moving outside authorized boundary.",
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. MobileAssetInspection View Tests
# ==============================================================================

def test_mobile_asset_view_inspection_list_get_200_and_context(client_a, mobile_inspection_a):
    """GET list returns 200 with all contract context keys and metric counts."""
    url = reverse("assets:mobile_asset_inspection_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "inspections" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "status_choices" in resp.context
    assert "result_choices" in resp.context
    assert "type_choices" in resp.context
    assert "total_inspections" in resp.context
    assert "passed_count" in resp.context
    assert "failed_count" in resp.context
    assert "offline_captured_count" in resp.context
    assert mobile_inspection_a in resp.context["inspections"]
    assert resp.context["total_inspections"] >= 1


def test_mobile_asset_view_inspection_list_search_filter(client_a, tenant_a, operational_asset_a, admin_user):
    """Search query ?q= correctly filters inspections by title, number, asset, or inspector."""
    url = reverse("assets:mobile_asset_inspection_list")
    ins_1 = _mobile_asset_create_inspection(
        tenant_a, operational_asset_a, admin_user, title="Hydraulic Pressure Testing Checklist"
    )
    ins_2 = _mobile_asset_create_inspection(
        tenant_a, operational_asset_a, admin_user, title="Electrical Cabin Interlock Review"
    )

    # Search matching ins_1
    resp_1 = client_a.get(f"{url}?q=Hydraulic")
    assert resp_1.status_code == 200
    assert ins_1 in resp_1.context["inspections"]
    assert ins_2 not in resp_1.context["inspections"]

    # Search matching ins_2
    resp_2 = client_a.get(f"{url}?q=Electrical")
    assert resp_2.status_code == 200
    assert ins_2 in resp_2.context["inspections"]
    assert ins_1 not in resp_2.context["inspections"]

    # Search by number
    resp_num = client_a.get(f"{url}?q={ins_1.number}")
    assert resp_num.status_code == 200
    assert ins_1 in resp_num.context["inspections"]

    # Search non-matching query returns 200 with empty list
    resp_none = client_a.get(f"{url}?q=COMPLETELY_NONEXISTENT_QUERY_XYZ")
    assert resp_none.status_code == 200
    assert len(resp_none.context["inspections"]) == 0


def test_mobile_asset_view_inspection_list_dropdown_filters(client_a, tenant_a, operational_asset_a, admin_user):
    """Dropdown filters for status, overall_result, and inspection_type restrict results correctly."""
    url = reverse("assets:mobile_asset_inspection_list")
    ins_pass = _mobile_asset_create_inspection(
        tenant_a,
        operational_asset_a,
        admin_user,
        title="Pass Routine Inspection",
        status="approved",
        overall_result="pass",
        inspection_type="routine_pm",
    )
    ins_fail = _mobile_asset_create_inspection(
        tenant_a,
        operational_asset_a,
        admin_user,
        title="Fail Safety Walkaround",
        status="draft",
        overall_result="critical_hazard",
        inspection_type="safety_audit",
    )

    # Filter by status
    resp_status = client_a.get(f"{url}?status=approved")
    assert resp_status.status_code == 200
    assert ins_pass in resp_status.context["inspections"]
    assert ins_fail not in resp_status.context["inspections"]

    # Filter by overall_result
    resp_result = client_a.get(f"{url}?overall_result=critical_hazard")
    assert resp_result.status_code == 200
    assert ins_fail in resp_result.context["inspections"]
    assert ins_pass not in resp_result.context["inspections"]

    # Filter by inspection_type
    resp_type = client_a.get(f"{url}?inspection_type=safety_audit")
    assert resp_type.status_code == 200
    assert ins_fail in resp_type.context["inspections"]
    assert ins_pass not in resp_type.context["inspections"]


def test_mobile_asset_view_inspection_list_junk_params_graceful(client_a, mobile_inspection_a):
    """Junk filter and pagination query params do not 500 and are handled gracefully."""
    url = reverse("assets:mobile_asset_inspection_list")
    resp_junk = client_a.get(f"{url}?status=invalid_status_xyz&overall_result=nonsense&page=not_an_int")
    assert resp_junk.status_code == 200
    assert resp_junk.context["page_obj"].number == 1

    resp_out_of_range = client_a.get(f"{url}?page=99999")
    assert resp_out_of_range.status_code == 200
    assert resp_out_of_range.context["page_obj"].number == resp_out_of_range.context["paginator"].num_pages


def test_mobile_asset_view_inspection_list_pagination(client_a, tenant_a, operational_asset_a, admin_user):
    """Pagination divides recordsets into pages of 15 items."""
    url = reverse("assets:mobile_asset_inspection_list")
    created = [
        _mobile_asset_create_inspection(
            tenant_a, operational_asset_a, admin_user, title=f"Bulk Inspection {i:02d}"
        )
        for i in range(16)
    ]
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["inspections"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(f"{url}?page=2")
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["inspections"]) >= 1
    assert resp_p2.context["page_obj"].has_previous()


def test_mobile_asset_view_inspection_detail_get_200_and_renders_identifier(client_a, mobile_inspection_a):
    """Detail view returns 200, populates inspection context, and renders MINS identifier."""
    url = reverse("assets:mobile_asset_inspection_detail", kwargs={"pk": mobile_inspection_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["inspection"] == mobile_inspection_a
    content = resp.content.decode("utf-8")
    assert mobile_inspection_a.number in content
    assert escape(mobile_inspection_a.title) in content


def test_mobile_asset_view_inspection_detail_cross_tenant_404(client_a, mobile_inspection_b):
    """Cross-tenant access to mobile inspection detail returns HTTP 404."""
    url = reverse("assets:mobile_asset_inspection_detail", kwargs={"pk": mobile_inspection_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_mobile_asset_view_inspection_create_get(client_a):
    """GET create renders form with initial inspector defaulted to request.user."""
    url = reverse("assets:mobile_asset_inspection_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["title"] == "New Mobile Inspection"


def test_mobile_asset_view_inspection_create_post_valid(client_a, tenant_a, operational_asset_a, admin_user):
    """POST valid inspection creates object, sets tenant, records audit log, and redirects to detail."""
    url = reverse("assets:mobile_asset_inspection_create")
    payload = _mobile_asset_inspection_payload(
        operational_asset_a, admin_user, title="Brake & Hydraulic System Walkaround", is_offline_captured=True
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = MobileAssetInspection.objects.get(title="Brake & Hydraulic System Walkaround", tenant=tenant_a)
    assert created.tenant == tenant_a
    assert created.inspector == admin_user
    assert created.is_offline_captured is True
    assert created.synced_at is not None
    assert resp.url == reverse("assets:mobile_asset_inspection_detail", kwargs={"pk": created.pk})

    # Verify audit log recorded
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=created.pk,
    ).exists()


def test_mobile_asset_view_inspection_create_post_invalid(client_a):
    """POST invalid payload returns 200 with form errors and does not create an object."""
    url = reverse("assets:mobile_asset_inspection_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_mobile_asset_view_inspection_edit_get(client_a, mobile_inspection_a):
    """GET edit renders form populated with inspection instance."""
    url = reverse("assets:mobile_asset_inspection_edit", kwargs={"pk": mobile_inspection_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["inspection"] == mobile_inspection_a
    assert "form" in resp.context


def test_mobile_asset_view_inspection_edit_post_valid(client_a, tenant_a, operational_asset_a, admin_user):
    """POST valid edit updates fields, populates synced_at if offline captured, records audit log, and redirects."""
    inspection = _mobile_asset_create_inspection(
        tenant_a, operational_asset_a, admin_user, title="Initial Inspection Title", condition_rating=3
    )
    url = reverse("assets:mobile_asset_inspection_edit", kwargs={"pk": inspection.pk})
    payload = _mobile_asset_inspection_payload(
        operational_asset_a,
        admin_user,
        title="Updated Inspection Title Post-Service",
        condition_rating="5",
        is_offline_captured=True,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:mobile_asset_inspection_detail", kwargs={"pk": inspection.pk})

    inspection.refresh_from_db()
    assert inspection.title == "Updated Inspection Title Post-Service"
    assert inspection.condition_rating == 5
    assert inspection.synced_at is not None

    # Verify audit log updated
    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=inspection.pk,
    ).exists()


def test_mobile_asset_view_inspection_edit_cross_tenant_404(client_a, mobile_inspection_b, operational_asset_b, admin_b):
    """Cross-tenant GET and POST to edit mobile inspection returns HTTP 404."""
    url = reverse("assets:mobile_asset_inspection_edit", kwargs={"pk": mobile_inspection_b.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 404

    payload = _mobile_asset_inspection_payload(operational_asset_b, admin_b)
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 404


def test_mobile_asset_view_inspection_delete_post(client_a, tenant_a, operational_asset_a, admin_user):
    """POST to delete removes inspection, writes audit log, and redirects to list."""
    inspection = _mobile_asset_create_inspection(
        tenant_a, operational_asset_a, admin_user, title="Temporary Inspection To Delete"
    )
    ins_pk = inspection.pk
    url = reverse("assets:mobile_asset_inspection_delete", kwargs={"pk": ins_pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:mobile_asset_inspection_list")
    assert not MobileAssetInspection.objects.filter(pk=ins_pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=ins_pk,
    ).exists()


def test_mobile_asset_view_inspection_delete_get_405(client_a, mobile_inspection_a):
    """GET to delete returns 405 Method Not Allowed due to require_POST."""
    url = reverse("assets:mobile_asset_inspection_delete", kwargs={"pk": mobile_inspection_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_mobile_asset_view_inspection_delete_cross_tenant_404(client_a, mobile_inspection_b):
    """Cross-tenant POST to delete foreign inspection returns HTTP 404."""
    url = reverse("assets:mobile_asset_inspection_delete", kwargs={"pk": mobile_inspection_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert MobileAssetInspection.objects.filter(pk=mobile_inspection_b.pk).exists()


# ==============================================================================
# 2. FieldWorkOrder View Tests
# ==============================================================================

def test_mobile_asset_view_work_order_list_get_200_and_context(client_a, field_work_order_a):
    """GET list returns 200 with all contract context keys and metric counts."""
    url = reverse("assets:field_work_order_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "work_orders" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "status_choices" in resp.context
    assert "priority_choices" in resp.context
    assert "type_choices" in resp.context
    assert "total_work_orders" in resp.context
    assert "active_count" in resp.context
    assert "completed_count" in resp.context
    assert "urgent_count" in resp.context
    assert "total_wrench_hours" in resp.context
    assert field_work_order_a in resp.context["work_orders"]


def test_mobile_asset_view_work_order_list_search_filter(client_a, tenant_a, operational_asset_a, admin_user):
    """Search query ?q= correctly filters work orders by title, number, asset, or technician."""
    url = reverse("assets:field_work_order_list")
    wo_1 = _mobile_asset_create_work_order(
        tenant_a, operational_asset_a, admin_user, title="Emergency Transmission Overhaul"
    )
    wo_2 = _mobile_asset_create_work_order(
        tenant_a, operational_asset_a, admin_user, title="Quarterly Radiator Flush"
    )

    resp_1 = client_a.get(f"{url}?q=Transmission")
    assert resp_1.status_code == 200
    assert wo_1 in resp_1.context["work_orders"]
    assert wo_2 not in resp_1.context["work_orders"]

    resp_num = client_a.get(f"{url}?q={wo_1.number}")
    assert resp_num.status_code == 200
    assert wo_1 in resp_num.context["work_orders"]

    resp_none = client_a.get(f"{url}?q=NONEXISTENT_FWO_QUERY_XYZ")
    assert resp_none.status_code == 200
    assert len(resp_none.context["work_orders"]) == 0


def test_mobile_asset_view_work_order_list_dropdown_filters(client_a, tenant_a, operational_asset_a, admin_user):
    """Dropdown filters for status, priority, and work_order_type restrict work order results correctly."""
    url = reverse("assets:field_work_order_list")
    wo_urgent = _mobile_asset_create_work_order(
        tenant_a,
        operational_asset_a,
        admin_user,
        title="Urgent Breakdown Repair",
        status="en_route",
        priority="urgent",
        work_order_type="breakdown_repair",
    )
    wo_low = _mobile_asset_create_work_order(
        tenant_a,
        operational_asset_a,
        admin_user,
        title="Low Priority Greasing",
        status="completed",
        priority="low",
        work_order_type="preventive_maintenance",
    )

    # Filter by status
    resp_status = client_a.get(f"{url}?status=en_route")
    assert resp_status.status_code == 200
    assert wo_urgent in resp_status.context["work_orders"]
    assert wo_low not in resp_status.context["work_orders"]

    # Filter by priority
    resp_pri = client_a.get(f"{url}?priority=urgent")
    assert resp_pri.status_code == 200
    assert wo_urgent in resp_pri.context["work_orders"]
    assert wo_low not in resp_pri.context["work_orders"]

    # Filter by work_order_type
    resp_type = client_a.get(f"{url}?work_order_type=preventive_maintenance")
    assert resp_type.status_code == 200
    assert wo_low in resp_type.context["work_orders"]
    assert wo_urgent not in resp_type.context["work_orders"]


def test_mobile_asset_view_work_order_list_junk_params_graceful(client_a, field_work_order_a):
    """Junk filter and pagination query params do not 500 on work order list."""
    url = reverse("assets:field_work_order_list")
    resp = client_a.get(f"{url}?status=invalid_xyz&priority=nonsense&page=foo")
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 1


def test_mobile_asset_view_work_order_list_pagination(client_a, tenant_a, operational_asset_a, admin_user):
    """Pagination splits work orders into pages of 15."""
    url = reverse("assets:field_work_order_list")
    created = [
        _mobile_asset_create_work_order(
            tenant_a, operational_asset_a, admin_user, title=f"Batch WO {i:02d}"
        )
        for i in range(16)
    ]
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["work_orders"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(f"{url}?page=2")
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["work_orders"]) >= 1
    assert resp_p2.context["page_obj"].has_previous()


def test_mobile_asset_view_work_order_detail_get_200_and_renders_identifier(client_a, field_work_order_a):
    """Detail view returns 200, context work_order, and renders FWO number and work performed notes."""
    url = reverse("assets:field_work_order_detail", kwargs={"pk": field_work_order_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["work_order"] == field_work_order_a
    content = resp.content.decode("utf-8")
    assert field_work_order_a.number in content
    assert escape(field_work_order_a.title) in content
    if field_work_order_a.work_performed_notes:
        assert escape(field_work_order_a.work_performed_notes) in content


def test_mobile_asset_view_work_order_detail_cross_tenant_404(client_a, field_work_order_b):
    """Cross-tenant access to field work order detail returns HTTP 404."""
    url = reverse("assets:field_work_order_detail", kwargs={"pk": field_work_order_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_mobile_asset_view_work_order_create_get(client_a):
    """GET create renders form with initial technician defaulted to request.user."""
    url = reverse("assets:field_work_order_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["title"] == "New Field Work Order"


def test_mobile_asset_view_work_order_create_post_valid_and_auto_timestamps(
    client_a, tenant_a, operational_asset_a, admin_user
):
    """POST valid work order creates object, sets tenant, auto-populates timestamps, and records audit log."""
    url = reverse("assets:field_work_order_create")
    payload = _mobile_asset_work_order_payload(
        operational_asset_a,
        admin_user,
        title="Field Generator Alternator Replacement",
        status="completed",
        signature_name="Robert Vance",
        is_offline_captured=True,
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = FieldWorkOrder.objects.get(title="Field Generator Alternator Replacement", tenant=tenant_a)
    assert created.tenant == tenant_a
    assert created.assigned_technician == admin_user
    assert created.actual_arrival is not None
    assert created.completed_at is not None
    assert created.signed_at is not None
    assert created.synced_at is not None
    assert resp.url == reverse("assets:field_work_order_detail", kwargs={"pk": created.pk})

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=created.pk,
    ).exists()


def test_mobile_asset_view_work_order_create_post_invalid(client_a):
    """POST invalid work order returns 200 with form errors."""
    url = reverse("assets:field_work_order_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_mobile_asset_view_work_order_edit_get(client_a, field_work_order_a):
    """GET edit renders form with work_order instance."""
    url = reverse("assets:field_work_order_edit", kwargs={"pk": field_work_order_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["work_order"] == field_work_order_a
    assert "form" in resp.context


def test_mobile_asset_view_work_order_edit_post_valid_and_auto_timestamps(
    client_a, tenant_a, operational_asset_a, admin_user
):
    """POST edit updates fields and auto-populates signed_at, actual_arrival, and audit log."""
    wo = _mobile_asset_create_work_order(
        tenant_a,
        operational_asset_a,
        admin_user,
        title="Initial Dispatched WO",
        status="dispatched",
        actual_arrival=None,
        signed_at=None,
    )
    url = reverse("assets:field_work_order_edit", kwargs={"pk": wo.pk})
    payload = _mobile_asset_work_order_payload(
        operational_asset_a,
        admin_user,
        title="Updated On-Site WO",
        status="on_site",
        signature_name="Lead Inspector Gomez",
        labor_wrench_minutes="120",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:field_work_order_detail", kwargs={"pk": wo.pk})

    wo.refresh_from_db()
    assert wo.title == "Updated On-Site WO"
    assert wo.status == "on_site"
    assert wo.labor_wrench_minutes == 120
    assert wo.actual_arrival is not None
    assert wo.signed_at is not None

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=wo.pk,
    ).exists()


def test_mobile_asset_view_work_order_edit_cross_tenant_404(client_a, field_work_order_b, operational_asset_b, admin_b):
    """Cross-tenant GET and POST edit on foreign field work order returns HTTP 404."""
    url = reverse("assets:field_work_order_edit", kwargs={"pk": field_work_order_b.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 404

    payload = _mobile_asset_work_order_payload(operational_asset_b, admin_b)
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 404


def test_mobile_asset_view_work_order_delete_post(client_a, tenant_a, operational_asset_a, admin_user):
    """POST delete removes work order, writes audit log, and redirects to list."""
    wo = _mobile_asset_create_work_order(tenant_a, operational_asset_a, admin_user, title="WO To Delete")
    wo_pk = wo.pk
    url = reverse("assets:field_work_order_delete", kwargs={"pk": wo_pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:field_work_order_list")
    assert not FieldWorkOrder.objects.filter(pk=wo_pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=wo_pk,
    ).exists()


def test_mobile_asset_view_work_order_delete_get_405(client_a, field_work_order_a):
    """GET to delete returns 405 Method Not Allowed."""
    url = reverse("assets:field_work_order_delete", kwargs={"pk": field_work_order_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_mobile_asset_view_work_order_delete_cross_tenant_404(client_a, field_work_order_b):
    """Cross-tenant POST delete on foreign work order returns HTTP 404."""
    url = reverse("assets:field_work_order_delete", kwargs={"pk": field_work_order_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert FieldWorkOrder.objects.filter(pk=field_work_order_b.pk).exists()


# ==============================================================================
# 3. AssetScanLog View Tests
# ==============================================================================

def test_mobile_asset_view_scan_log_list_get_200_and_context(client_a, asset_scan_log_a):
    """GET list returns 200 with all contract context keys and metric counts."""
    url = reverse("assets:asset_scan_log_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "scans" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "match_choices" in resp.context
    assert "method_choices" in resp.context
    assert "context_choices" in resp.context
    assert "total_scans" in resp.context
    assert "matched_count" in resp.context
    assert "not_found_count" in resp.context
    assert "rfid_count" in resp.context
    assert asset_scan_log_a in resp.context["scans"]


def test_mobile_asset_view_scan_log_list_search_filter(client_a, tenant_a, operational_asset_a, admin_user):
    """Search query ?q= correctly filters scan logs by raw_payload, device_info, or number."""
    url = reverse("assets:asset_scan_log_list")
    scan_1 = _mobile_asset_create_scan_log(
        tenant_a, operational_asset_a, admin_user, payload="QR-WAREHOUSE-NORTH-9901", device_info="Zebra TC57"
    )
    scan_2 = _mobile_asset_create_scan_log(
        tenant_a, operational_asset_a, admin_user, payload="BARCODE-SOUTH-YARD-4422", device_info="Honeywell CT40"
    )

    resp_1 = client_a.get(f"{url}?q=NORTH-9901")
    assert resp_1.status_code == 200
    assert scan_1 in resp_1.context["scans"]
    assert scan_2 not in resp_1.context["scans"]

    resp_dev = client_a.get(f"{url}?q=Honeywell")
    assert resp_dev.status_code == 200
    assert scan_2 in resp_dev.context["scans"]
    assert scan_1 not in resp_dev.context["scans"]

    resp_none = client_a.get(f"{url}?q=UNMATCHED_SCAN_QUERY_XYZ")
    assert resp_none.status_code == 200
    assert len(resp_none.context["scans"]) == 0


def test_mobile_asset_view_scan_log_list_dropdown_filters(client_a, tenant_a, operational_asset_a, admin_user):
    """Dropdown filters for match_status, scan_method, and scan_context restrict scans correctly."""
    url = reverse("assets:asset_scan_log_list")
    scan_matched = _mobile_asset_create_scan_log(
        tenant_a,
        operational_asset_a,
        admin_user,
        payload="MATCH-PAYLOAD-01",
        match_status="matched",
        scan_method="camera_qr",
        scan_context="field_audit",
    )
    scan_rfid = _mobile_asset_create_scan_log(
        tenant_a,
        operational_asset_a,
        admin_user,
        payload="RFID-EPC-TAG-99",
        match_status="not_found",
        scan_method="bluetooth_rfid",
        scan_context="gate_checkin",
    )

    # Filter by match_status
    resp_match = client_a.get(f"{url}?match_status=matched")
    assert resp_match.status_code == 200
    assert scan_matched in resp_match.context["scans"]
    assert scan_rfid not in resp_match.context["scans"]

    # Filter by scan_method
    resp_meth = client_a.get(f"{url}?scan_method=bluetooth_rfid")
    assert resp_meth.status_code == 200
    assert scan_rfid in resp_meth.context["scans"]
    assert scan_matched not in resp_meth.context["scans"]

    # Filter by scan_context
    resp_ctx = client_a.get(f"{url}?scan_context=gate_checkin")
    assert resp_ctx.status_code == 200
    assert scan_rfid in resp_ctx.context["scans"]
    assert scan_matched not in resp_ctx.context["scans"]


def test_mobile_asset_view_scan_log_list_junk_params_graceful(client_a, asset_scan_log_a):
    """Junk filter and pagination query params do not 500 on scan log list."""
    url = reverse("assets:asset_scan_log_list")
    resp = client_a.get(f"{url}?match_status=bogus&page=invalid")
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 1


def test_mobile_asset_view_scan_log_list_pagination(client_a, tenant_a, operational_asset_a, admin_user):
    """Pagination splits scan logs into pages of 15."""
    url = reverse("assets:asset_scan_log_list")
    created = [
        _mobile_asset_create_scan_log(
            tenant_a, operational_asset_a, admin_user, payload=f"BATCH-PAYLOAD-{i:03d}"
        )
        for i in range(16)
    ]
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["scans"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(f"{url}?page=2")
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["scans"]) >= 1
    assert resp_p2.context["page_obj"].has_previous()


def test_mobile_asset_view_scan_log_detail_get_200_and_renders_identifier(client_a, asset_scan_log_a):
    """Detail view returns 200, context scan, and renders SCAN number and raw payload."""
    url = reverse("assets:asset_scan_log_detail", kwargs={"pk": asset_scan_log_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["scan"] == asset_scan_log_a
    content = resp.content.decode("utf-8")
    assert asset_scan_log_a.number in content
    assert asset_scan_log_a.raw_payload in content


def test_mobile_asset_view_scan_log_detail_cross_tenant_404(client_a, asset_scan_log_b):
    """Cross-tenant access to asset scan log detail returns HTTP 404."""
    url = reverse("assets:asset_scan_log_detail", kwargs={"pk": asset_scan_log_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_mobile_asset_view_scan_log_create_get(client_a):
    """GET create renders form with initial scanned_by defaulted to request.user."""
    url = reverse("assets:asset_scan_log_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["title"] == "Record Mobile Scan"


def test_mobile_asset_view_scan_log_create_post_valid(client_a, tenant_a, operational_asset_a, admin_user):
    """POST valid scan log creates object, sets tenant, records audit log, and redirects to detail."""
    url = reverse("assets:asset_scan_log_create")
    payload = _mobile_asset_scan_log_payload(
        admin_user, asset=operational_asset_a, raw_payload="ACME-INVENTORY-SCAN-90210"
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetScanLog.objects.get(raw_payload="ACME-INVENTORY-SCAN-90210", tenant=tenant_a)
    assert created.tenant == tenant_a
    assert created.scanned_by == admin_user
    assert resp.url == reverse("assets:asset_scan_log_detail", kwargs={"pk": created.pk})

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=created.pk,
    ).exists()


def test_mobile_asset_view_scan_log_create_post_invalid(client_a):
    """POST invalid scan log returns 200 with form errors."""
    url = reverse("assets:asset_scan_log_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_mobile_asset_view_scan_log_edit_get(client_a, asset_scan_log_a):
    """GET edit renders form with scan instance."""
    url = reverse("assets:asset_scan_log_edit", kwargs={"pk": asset_scan_log_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["scan"] == asset_scan_log_a
    assert "form" in resp.context


def test_mobile_asset_view_scan_log_edit_post_valid(client_a, tenant_a, operational_asset_a, admin_user):
    """POST edit updates scan log fields, records audit log, and redirects to detail."""
    scan = _mobile_asset_create_scan_log(
        tenant_a, operational_asset_a, admin_user, payload="INITIAL-PAYLOAD-111", notes="Initial scan note"
    )
    url = reverse("assets:asset_scan_log_edit", kwargs={"pk": scan.pk})
    payload = _mobile_asset_scan_log_payload(
        admin_user,
        asset=operational_asset_a,
        raw_payload="UPDATED-PAYLOAD-222",
        notes="Updated audit verification note",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_scan_log_detail", kwargs={"pk": scan.pk})

    scan.refresh_from_db()
    assert scan.raw_payload == "UPDATED-PAYLOAD-222"
    assert scan.notes == "Updated audit verification note"

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=scan.pk,
    ).exists()


def test_mobile_asset_view_scan_log_edit_cross_tenant_404(client_a, asset_scan_log_b, admin_b):
    """Cross-tenant GET and POST edit on foreign scan log returns HTTP 404."""
    url = reverse("assets:asset_scan_log_edit", kwargs={"pk": asset_scan_log_b.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 404

    payload = _mobile_asset_scan_log_payload(admin_b)
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 404


def test_mobile_asset_view_scan_log_delete_post(client_a, tenant_a, operational_asset_a, admin_user):
    """POST delete removes scan log, writes audit log, and redirects to list."""
    scan = _mobile_asset_create_scan_log(tenant_a, operational_asset_a, admin_user, payload="DELETE-ME-SCAN")
    scan_pk = scan.pk
    url = reverse("assets:asset_scan_log_delete", kwargs={"pk": scan_pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_scan_log_list")
    assert not AssetScanLog.objects.filter(pk=scan_pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=scan_pk,
    ).exists()


def test_mobile_asset_view_scan_log_delete_get_405(client_a, asset_scan_log_a):
    """GET to delete returns 405 Method Not Allowed."""
    url = reverse("assets:asset_scan_log_delete", kwargs={"pk": asset_scan_log_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_mobile_asset_view_scan_log_delete_cross_tenant_404(client_a, asset_scan_log_b):
    """Cross-tenant POST delete on foreign scan log returns HTTP 404."""
    url = reverse("assets:asset_scan_log_delete", kwargs={"pk": asset_scan_log_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert AssetScanLog.objects.filter(pk=asset_scan_log_b.pk).exists()


# ==============================================================================
# 4. AssetGeofenceEvent View Tests
# ==============================================================================

def test_mobile_asset_view_geofence_event_list_get_200_and_context(client_a, asset_geofence_event_a):
    """GET list returns 200 with all contract context keys and metric counts."""
    url = reverse("assets:asset_geofence_event_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "events" in resp.context
    assert "page_obj" in resp.context
    assert "paginator" in resp.context
    assert "is_paginated" in resp.context
    assert "event_type_choices" in resp.context
    assert "severity_choices" in resp.context
    assert "status_choices" in resp.context
    assert "total_events" in resp.context
    assert "open_alerts_count" in resp.context
    assert "critical_breaches_count" in resp.context
    assert "resolved_count" in resp.context
    assert asset_geofence_event_a in resp.context["events"]


def test_mobile_asset_view_geofence_event_list_search_filter(client_a, tenant_a, operational_asset_a):
    """Search query ?q= correctly filters geofence alerts by fence_name, number, or notes."""
    url = reverse("assets:asset_geofence_event_list")
    ev_1 = _mobile_asset_create_geofence_event(
        tenant_a, operational_asset_a, fence_name="Quarry Zone Alpha Perimeter", resolution_notes="Dispatched security"
    )
    ev_2 = _mobile_asset_create_geofence_event(
        tenant_a, operational_asset_a, fence_name="Highway Corridor Geo-corral", resolution_notes="Authorized transit"
    )

    resp_1 = client_a.get(f"{url}?q=Quarry")
    assert resp_1.status_code == 200
    assert ev_1 in resp_1.context["events"]
    assert ev_2 not in resp_1.context["events"]

    resp_num = client_a.get(f"{url}?q={ev_1.number}")
    assert resp_num.status_code == 200
    assert ev_1 in resp_num.context["events"]

    resp_none = client_a.get(f"{url}?q=NONEXISTENT_GEOFENCE_QUERY_XYZ")
    assert resp_none.status_code == 200
    assert len(resp_none.context["events"]) == 0


def test_mobile_asset_view_geofence_event_list_dropdown_filters(client_a, tenant_a, operational_asset_a):
    """Dropdown filters for status, event_type, and severity restrict geofence events correctly."""
    url = reverse("assets:asset_geofence_event_list")
    ev_crit = _mobile_asset_create_geofence_event(
        tenant_a,
        operational_asset_a,
        fence_name="Critical Fence",
        status="open_alert",
        event_type="perimeter_exit",
        severity="critical",
    )
    ev_res = _mobile_asset_create_geofence_event(
        tenant_a,
        operational_asset_a,
        fence_name="Resolved Fence",
        status="resolved",
        event_type="inside_perimeter",
        severity="info",
    )

    # Filter by status
    resp_status = client_a.get(f"{url}?status=open_alert")
    assert resp_status.status_code == 200
    assert ev_crit in resp_status.context["events"]
    assert ev_res not in resp_status.context["events"]

    # Filter by event_type
    resp_type = client_a.get(f"{url}?event_type=perimeter_exit")
    assert resp_type.status_code == 200
    assert ev_crit in resp_type.context["events"]
    assert ev_res not in resp_type.context["events"]

    # Filter by severity
    resp_sev = client_a.get(f"{url}?severity=info")
    assert resp_sev.status_code == 200
    assert ev_res in resp_sev.context["events"]
    assert ev_crit not in resp_sev.context["events"]


def test_mobile_asset_view_geofence_event_list_junk_params_graceful(client_a, asset_geofence_event_a):
    """Junk filter and pagination query params do not 500 on geofence event list."""
    url = reverse("assets:asset_geofence_event_list")
    resp = client_a.get(f"{url}?status=bogus&page=invalid")
    assert resp.status_code == 200
    assert resp.context["page_obj"].number == 1


def test_mobile_asset_view_geofence_event_list_pagination(client_a, tenant_a, operational_asset_a):
    """Pagination splits geofence events into pages of 15."""
    url = reverse("assets:asset_geofence_event_list")
    created = [
        _mobile_asset_create_geofence_event(
            tenant_a, operational_asset_a, fence_name=f"Perimeter Fence {i:02d}"
        )
        for i in range(16)
    ]
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["events"]) == 15
    assert resp_p1.context["page_obj"].has_next()

    resp_p2 = client_a.get(f"{url}?page=2")
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["events"]) >= 1
    assert resp_p2.context["page_obj"].has_previous()


def test_mobile_asset_view_geofence_event_detail_get_200_and_renders_identifier(client_a, asset_geofence_event_a):
    """Detail view returns 200, context event, and renders GEO number and fence name."""
    url = reverse("assets:asset_geofence_event_detail", kwargs={"pk": asset_geofence_event_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["event"] == asset_geofence_event_a
    content = resp.content.decode("utf-8")
    assert asset_geofence_event_a.number in content
    assert asset_geofence_event_a.fence_name in content


def test_mobile_asset_view_geofence_event_detail_cross_tenant_404(client_a, asset_geofence_event_b):
    """Cross-tenant access to geofence event detail returns HTTP 404."""
    url = reverse("assets:asset_geofence_event_detail", kwargs={"pk": asset_geofence_event_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_mobile_asset_view_geofence_event_create_get(client_a):
    """GET create renders form."""
    url = reverse("assets:asset_geofence_event_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["title"] == "Log Geofence Event"


def test_mobile_asset_view_geofence_event_create_post_valid(client_a, tenant_a, operational_asset_a):
    """POST valid geofence event creates object, sets tenant, records audit log, and redirects to detail."""
    url = reverse("assets:asset_geofence_event_create")
    payload = _mobile_asset_geofence_event_payload(operational_asset_a, fence_name="Remote Depot Geofence")
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = AssetGeofenceEvent.objects.get(fence_name="Remote Depot Geofence", tenant=tenant_a)
    assert created.tenant == tenant_a
    assert resp.url == reverse("assets:asset_geofence_event_detail", kwargs={"pk": created.pk})

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=created.pk,
    ).exists()


def test_mobile_asset_view_geofence_event_create_post_invalid(client_a):
    """POST invalid geofence event returns 200 with form errors."""
    url = reverse("assets:asset_geofence_event_create")
    resp = client_a.post(url, data={})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


def test_mobile_asset_view_geofence_event_edit_get(client_a, asset_geofence_event_a):
    """GET edit renders form with event instance."""
    url = reverse("assets:asset_geofence_event_edit", kwargs={"pk": asset_geofence_event_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["event"] == asset_geofence_event_a
    assert "form" in resp.context


def test_mobile_asset_view_geofence_event_edit_post_valid_and_auto_ack(
    client_a, tenant_a, operational_asset_a, admin_user
):
    """POST edit with status=resolved auto-populates acknowledged_by and acknowledged_at, and writes audit log."""
    event = _mobile_asset_create_geofence_event(
        tenant_a,
        operational_asset_a,
        fence_name="Unresolved Fence",
        status="open_alert",
        acknowledged_by=None,
        acknowledged_at=None,
    )
    url = reverse("assets:asset_geofence_event_edit", kwargs={"pk": event.pk})
    payload = _mobile_asset_geofence_event_payload(
        operational_asset_a,
        fence_name="Resolved Fence Perimeter",
        status="resolved",
        resolution_notes="Authorized movement outside boundary confirmed.",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_geofence_event_detail", kwargs={"pk": event.pk})

    event.refresh_from_db()
    assert event.fence_name == "Resolved Fence Perimeter"
    assert event.status == "resolved"
    assert event.acknowledged_by == admin_user
    assert event.acknowledged_at is not None

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=event.pk,
    ).exists()


def test_mobile_asset_view_geofence_event_edit_cross_tenant_404(client_a, asset_geofence_event_b, operational_asset_b):
    """Cross-tenant GET and POST edit on foreign geofence alert returns HTTP 404."""
    url = reverse("assets:asset_geofence_event_edit", kwargs={"pk": asset_geofence_event_b.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 404

    payload = _mobile_asset_geofence_event_payload(operational_asset_b)
    resp_post = client_a.post(url, data=payload)
    assert resp_post.status_code == 404


def test_mobile_asset_view_geofence_event_delete_post(client_a, tenant_a, operational_asset_a):
    """POST delete removes geofence alert, writes audit log, and redirects to list."""
    event = _mobile_asset_create_geofence_event(tenant_a, operational_asset_a, fence_name="Delete Fence Alert")
    ev_pk = event.pk
    url = reverse("assets:asset_geofence_event_delete", kwargs={"pk": ev_pk})

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("assets:asset_geofence_event_list")
    assert not AssetGeofenceEvent.objects.filter(pk=ev_pk).exists()

    assert AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=ev_pk,
    ).exists()


def test_mobile_asset_view_geofence_event_delete_get_405(client_a, asset_geofence_event_a):
    """GET to delete returns 405 Method Not Allowed."""
    url = reverse("assets:asset_geofence_event_delete", kwargs={"pk": asset_geofence_event_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


def test_mobile_asset_view_geofence_event_delete_cross_tenant_404(client_a, asset_geofence_event_b):
    """Cross-tenant POST delete on foreign geofence alert returns HTTP 404."""
    url = reverse("assets:asset_geofence_event_delete", kwargs={"pk": asset_geofence_event_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert AssetGeofenceEvent.objects.filter(pk=asset_geofence_event_b.pk).exists()


# ==============================================================================
# 5. Security & Authentication Tests
# ==============================================================================

def test_mobile_asset_view_unauthenticated_redirects_to_login(
    client, mobile_inspection_a, field_work_order_a, asset_scan_log_a, asset_geofence_event_a
):
    """Unauthenticated access to any Mobile Asset Management view redirects to login."""
    urls = [
        reverse("assets:mobile_asset_inspection_list"),
        reverse("assets:mobile_asset_inspection_create"),
        reverse("assets:mobile_asset_inspection_detail", kwargs={"pk": mobile_inspection_a.pk}),
        reverse("assets:mobile_asset_inspection_edit", kwargs={"pk": mobile_inspection_a.pk}),
        reverse("assets:mobile_asset_inspection_delete", kwargs={"pk": mobile_inspection_a.pk}),
        reverse("assets:field_work_order_list"),
        reverse("assets:field_work_order_create"),
        reverse("assets:field_work_order_detail", kwargs={"pk": field_work_order_a.pk}),
        reverse("assets:field_work_order_edit", kwargs={"pk": field_work_order_a.pk}),
        reverse("assets:field_work_order_delete", kwargs={"pk": field_work_order_a.pk}),
        reverse("assets:asset_scan_log_list"),
        reverse("assets:asset_scan_log_create"),
        reverse("assets:asset_scan_log_detail", kwargs={"pk": asset_scan_log_a.pk}),
        reverse("assets:asset_scan_log_edit", kwargs={"pk": asset_scan_log_a.pk}),
        reverse("assets:asset_scan_log_delete", kwargs={"pk": asset_scan_log_a.pk}),
        reverse("assets:asset_geofence_event_list"),
        reverse("assets:asset_geofence_event_create"),
        reverse("assets:asset_geofence_event_detail", kwargs={"pk": asset_geofence_event_a.pk}),
        reverse("assets:asset_geofence_event_edit", kwargs={"pk": asset_geofence_event_a.pk}),
        reverse("assets:asset_geofence_event_delete", kwargs={"pk": asset_geofence_event_a.pk}),
    ]

    for target_url in urls:
        resp = client.get(target_url)
        assert resp.status_code == 302, f"Expected 302 redirect for {target_url}, got {resp.status_code}"
        assert "/accounts/login/" in resp.url or "login" in resp.url
