"""Security, multi-tenant isolation, IDOR, CSRF, mass-assignment, and XSS tests for Sub-module 11.13: Mobile Asset Management.

Covers all 4 entities across all 20 endpoints:
- MobileAssetInspection
- FieldWorkOrder
- AssetScanLog
- AssetGeofenceEvent

Security aspects verified:
1. Authentication Gates (@login_required):
   - Unauthenticated GET & POST requests to all 20 endpoints redirect to login (HTTP 302).
2. Superuser Tenant Isolation (tenant=None):
   - Superuser with tenant=None sees zero tenant records and zero KPI metrics on all 4 list endpoints.
   - Superuser receives HTTP 404 on detail, edit (GET/POST), and delete (POST) for both Tenant A and Tenant B records.
3. Cross-Tenant IDOR & List Isolation:
   - Tenant A GET/POST to Tenant B detail, edit, and delete endpoints returns HTTP 404; Tenant B records remain intact.
   - Symmetric Tenant B GET/POST to Tenant A detail, edit, and delete endpoints returns HTTP 404; Tenant A records remain intact.
   - List views and KPI aggregates strictly isolate Tenant A vs Tenant B records.
4. Cross-Tenant Foreign Key Injection Defense (via POST create & edit):
   - Tenant A POSTing Tenant B's asset, fixed_asset, user (inspector, assigned_technician,
     scanned_by, acknowledged_by), or maintenance_request fails form validation and never persists cross-tenant links.
5. Mass Assignment & System Field Tamper Prevention:
   - Forms exclude tenant, number, and system timestamps from Meta.fields.
   - POSTing forged 'tenant', 'number', 'created_at', 'updated_at', or system timestamps
     ('synced_at', 'actual_arrival', 'completed_at', 'signed_at', 'scanned_at', 'detected_at', 'acknowledged_at')
     is ignored or overwritten by server logic on both create and edit.
6. HTTP Method & CSRF Enforcement:
   - All 4 delete endpoints reject GET requests with HTTP 405 Method Not Allowed.
   - Client(enforce_csrf_checks=True) rejects POST requests without CSRF token with HTTP 403 across all 12 mutating routes.
7. Stored XSS Escaping & Input Fuzzing:
   - HTML/script payloads stored via create POST in text inputs are rendered HTML-escaped in both detail and list views.
   - Malicious XSS/SQLi/NaN/extreme-length query params do not cause HTTP 500 or unescaped reflection.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.assets.forms import (
    AssetGeofenceEventForm,
    AssetScanLogForm,
    FieldWorkOrderForm,
    MobileAssetInspectionForm,
)
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
# Module Helpers (strictly prefixed with _mobile_asset_*)
# ==============================================================================


def _mobile_asset_sec_inspection_payload(asset, inspector, fixed_asset=None, **overrides):
    """Build a valid form payload for MobileAssetInspection create/edit POST requests."""
    now_dt = timezone.now().strftime("%Y-%m-%dT%H:%M")
    today = timezone.now().date().isoformat()
    data = {
        "title": "Security Verified Walkaround Inspection",
        "inspection_type": "pre_trip",
        "asset": str(asset.pk),
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "inspector": str(inspector.pk),
        "inspection_date": now_dt,
        "scheduled_date": today,
        "overall_result": "pass",
        "condition_rating": "4",
        "meter_reading": "1500.00",
        "checklist_summary": "Hydraulics, brakes, and safety guards verified.",
        "photo_url": "https://cdn.example.com/inspections/sec-photo.jpg",
        "photo_caption": "Main frame nameplate check",
        "voice_notes_transcription": "All inspection parameters nominal.",
        "corrective_action_required": False,
        "findings_summary": "No defects found.",
        "gps_latitude": "37.774900",
        "gps_longitude": "-122.419400",
        "location_accuracy_m": "4.0",
        "client_sync_id": "sec-sync-uuid-001",
        "is_offline_captured": False,
        "status": "submitted",
    }
    data.update(overrides)
    return data


def _mobile_asset_sec_work_order_payload(
    asset, technician, fixed_asset=None, maintenance_request=None, **overrides
):
    """Build a valid form payload for FieldWorkOrder create/edit POST requests."""
    now = timezone.now()
    data = {
        "title": "Security Verified Field Calibration",
        "work_order_type": "scheduled_pm",
        "priority": "high",
        "status": "dispatched",
        "asset": str(asset.pk),
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "assigned_technician": str(technician.pk),
        "maintenance_request": str(maintenance_request.pk) if maintenance_request else "",
        "scheduled_start": now.strftime("%Y-%m-%dT%H:%M"),
        "scheduled_end": (now + timezone.timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M"),
        "labor_wrench_minutes": "90",
        "safety_lockout_confirmed": True,
        "parts_requisition_notes": "Calibration kit and seal pack.",
        "estimated_parts_cost": "180.00",
        "work_performed_notes": "Standard field calibration performed.",
        "signature_name": "",
        "signature_designation": "",
        "dispatch_latitude": "37.774900",
        "dispatch_longitude": "-122.419400",
        "completion_latitude": "37.775000",
        "completion_longitude": "-122.419500",
        "client_sync_id": "sec-fwo-uuid-001",
        "is_offline_captured": False,
    }
    data.update(overrides)
    return data


def _mobile_asset_sec_scan_log_payload(scanned_by, asset=None, **overrides):
    """Build a valid form payload for AssetScanLog create/edit POST requests."""
    data = {
        "scanned_by": str(scanned_by.pk),
        "scan_context": "field_audit",
        "scan_method": "camera_qr",
        "raw_payload": "ACME-SEC-QR-001",
        "asset": str(asset.pk) if asset else "",
        "match_status": "matched",
        "gps_latitude": "37.774900",
        "gps_longitude": "-122.419400",
        "gps_accuracy_m": "3.2",
        "device_info": "Zebra TC57 Field Scanner",
        "notes": "Verified barcode integrity.",
        "client_sync_id": "sec-scan-uuid-001",
        "is_offline_captured": False,
    }
    data.update(overrides)
    return data


def _mobile_asset_sec_geofence_event_payload(asset, acknowledged_by=None, **overrides):
    """Build a valid form payload for AssetGeofenceEvent create/edit POST requests."""
    data = {
        "asset": str(asset.pk),
        "fence_name": "Acme North Security Yard",
        "center_latitude": "37.774000",
        "center_longitude": "-122.419000",
        "radius_meters": "150",
        "recorded_latitude": "37.774900",
        "recorded_longitude": "-122.419400",
        "recorded_accuracy_m": "5.0",
        "distance_from_center_m": "120.0",
        "event_type": "perimeter_exit",
        "severity": "high",
        "status": "open_alert",
        "acknowledged_by": str(acknowledged_by.pk) if acknowledged_by else "",
        "resolution_notes": "Investigating boundary crossing.",
    }
    data.update(overrides)
    return data


def _mobile_asset_sec_all_20_urls(inspection, work_order, scan_log, geofence_event):
    """Return all 20 Mobile Asset Management endpoint URLs across the 4 entities."""
    return [
        # MobileAssetInspection (5)
        reverse("assets:mobile_asset_inspection_list"),
        reverse("assets:mobile_asset_inspection_create"),
        reverse("assets:mobile_asset_inspection_detail", kwargs={"pk": inspection.pk}),
        reverse("assets:mobile_asset_inspection_edit", kwargs={"pk": inspection.pk}),
        reverse("assets:mobile_asset_inspection_delete", kwargs={"pk": inspection.pk}),
        # FieldWorkOrder (5)
        reverse("assets:field_work_order_list"),
        reverse("assets:field_work_order_create"),
        reverse("assets:field_work_order_detail", kwargs={"pk": work_order.pk}),
        reverse("assets:field_work_order_edit", kwargs={"pk": work_order.pk}),
        reverse("assets:field_work_order_delete", kwargs={"pk": work_order.pk}),
        # AssetScanLog (5)
        reverse("assets:asset_scan_log_list"),
        reverse("assets:asset_scan_log_create"),
        reverse("assets:asset_scan_log_detail", kwargs={"pk": scan_log.pk}),
        reverse("assets:asset_scan_log_edit", kwargs={"pk": scan_log.pk}),
        reverse("assets:asset_scan_log_delete", kwargs={"pk": scan_log.pk}),
        # AssetGeofenceEvent (5)
        reverse("assets:asset_geofence_event_list"),
        reverse("assets:asset_geofence_event_create"),
        reverse("assets:asset_geofence_event_detail", kwargs={"pk": geofence_event.pk}),
        reverse("assets:asset_geofence_event_edit", kwargs={"pk": geofence_event.pk}),
        reverse("assets:asset_geofence_event_delete", kwargs={"pk": geofence_event.pk}),
    ]


def _mobile_asset_sec_create_superuser():
    """Create a superuser with tenant=None (platform admin with no tenant workspace)."""
    su = User.objects.create_superuser(
        email="superuser.mobile@naverp.test",
        username="su_mobile_sec",
        password="SuperUserPass123!",
    )
    assert su.is_superuser is True
    assert su.tenant is None
    return su


# ==============================================================================
# 1. Authentication Gates (Unauthenticated GET & POST -> 302 Login Redirect)
# ==============================================================================


def test_mobile_asset_security_unauthenticated_get_all_20_endpoints_redirect(
    client, mobile_inspection_a, field_work_order_a, asset_scan_log_a, asset_geofence_event_a
):
    """Unauthenticated GET requests to all 20 Mobile Asset endpoints redirect (302) to login."""
    urls = _mobile_asset_sec_all_20_urls(
        mobile_inspection_a, field_work_order_a, asset_scan_log_a, asset_geofence_event_a
    )
    assert len(urls) == 20

    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 login redirect for GET {url}, got {resp.status_code}"
        assert "/accounts/login/" in resp.url or "login" in resp.url


def test_mobile_asset_security_unauthenticated_post_all_20_endpoints_redirect(
    client, mobile_inspection_a, field_work_order_a, asset_scan_log_a, asset_geofence_event_a
):
    """Unauthenticated POST requests to all 20 Mobile Asset endpoints redirect (302) without mutating DB."""
    urls = _mobile_asset_sec_all_20_urls(
        mobile_inspection_a, field_work_order_a, asset_scan_log_a, asset_geofence_event_a
    )
    assert len(urls) == 20

    initial_counts = (
        MobileAssetInspection.objects.count(),
        FieldWorkOrder.objects.count(),
        AssetScanLog.objects.count(),
        AssetGeofenceEvent.objects.count(),
    )

    for url in urls:
        resp = client.post(url, data={"title": "Unauthenticated Mutation"})
        assert resp.status_code == 302, f"Expected 302 login redirect for POST {url}, got {resp.status_code}"
        assert "/accounts/login/" in resp.url or "login" in resp.url

    assert (
        MobileAssetInspection.objects.count(),
        FieldWorkOrder.objects.count(),
        AssetScanLog.objects.count(),
        AssetGeofenceEvent.objects.count(),
    ) == initial_counts


# ==============================================================================
# 2. Superuser (tenant=None) Isolation Tests
# ==============================================================================


def test_mobile_asset_security_superuser_sees_zero_tenant_records_on_lists(
    mobile_inspection_a,
    mobile_inspection_b,
    field_work_order_a,
    field_work_order_b,
    asset_scan_log_a,
    asset_scan_log_b,
    asset_geofence_event_a,
    asset_geofence_event_b,
):
    """Superuser with tenant=None sees zero tenant records and zero KPI totals across all 4 list views."""
    su = _mobile_asset_sec_create_superuser()
    su_client = Client()
    su_client.force_login(su)

    list_specs = [
        (
            "assets:mobile_asset_inspection_list",
            "inspections",
            "total_inspections",
            [mobile_inspection_a, mobile_inspection_b],
        ),
        (
            "assets:field_work_order_list",
            "work_orders",
            "total_work_orders",
            [field_work_order_a, field_work_order_b],
        ),
        (
            "assets:asset_scan_log_list",
            "scans",
            "total_scans",
            [asset_scan_log_a, asset_scan_log_b],
        ),
        (
            "assets:asset_geofence_event_list",
            "events",
            "total_events",
            [asset_geofence_event_a, asset_geofence_event_b],
        ),
    ]

    for url_name, ctx_list_key, ctx_total_key, forbidden_records in list_specs:
        resp = su_client.get(reverse(url_name))
        assert resp.status_code == 200
        assert len(resp.context[ctx_list_key]) == 0
        assert resp.context[ctx_total_key] == 0
        body = resp.content.decode("utf-8")
        for rec in forbidden_records:
            assert rec not in resp.context[ctx_list_key]
            assert rec.number not in body


def test_mobile_asset_security_superuser_receives_404_on_detail_edit_delete(
    mobile_inspection_a,
    mobile_inspection_b,
    field_work_order_a,
    field_work_order_b,
    asset_scan_log_a,
    asset_scan_log_b,
    asset_geofence_event_a,
    asset_geofence_event_b,
):
    """Superuser with tenant=None receives HTTP 404 on detail, edit (GET/POST), and delete (POST) for all tenant records."""
    su = _mobile_asset_sec_create_superuser()
    su_client = Client()
    su_client.force_login(su)

    targets = [
        ("mobile_asset_inspection", mobile_inspection_a),
        ("mobile_asset_inspection", mobile_inspection_b),
        ("field_work_order", field_work_order_a),
        ("field_work_order", field_work_order_b),
        ("asset_scan_log", asset_scan_log_a),
        ("asset_scan_log", asset_scan_log_b),
        ("asset_geofence_event", asset_geofence_event_a),
        ("asset_geofence_event", asset_geofence_event_b),
    ]

    for prefix, obj in targets:
        detail_url = reverse(f"assets:{prefix}_detail", kwargs={"pk": obj.pk})
        edit_url = reverse(f"assets:{prefix}_edit", kwargs={"pk": obj.pk})
        delete_url = reverse(f"assets:{prefix}_delete", kwargs={"pk": obj.pk})

        assert su_client.get(detail_url).status_code == 404
        assert su_client.get(edit_url).status_code == 404
        assert su_client.post(edit_url, data={"title": "SU Tamper"}).status_code == 404
        assert su_client.post(delete_url).status_code == 404

    assert MobileAssetInspection.objects.filter(pk__in=[mobile_inspection_a.pk, mobile_inspection_b.pk]).count() == 2
    assert FieldWorkOrder.objects.filter(pk__in=[field_work_order_a.pk, field_work_order_b.pk]).count() == 2
    assert AssetScanLog.objects.filter(pk__in=[asset_scan_log_a.pk, asset_scan_log_b.pk]).count() == 2
    assert AssetGeofenceEvent.objects.filter(pk__in=[asset_geofence_event_a.pk, asset_geofence_event_b.pk]).count() == 2


# ==============================================================================
# 3. Cross-Tenant IDOR & List Isolation Tests
# ==============================================================================


def test_mobile_asset_security_idor_tenant_a_to_tenant_b_returns_404_and_preserves_records(
    client_a,
    tenant_b,
    operational_asset_b,
    admin_b,
    mobile_inspection_b,
    field_work_order_b,
    asset_scan_log_b,
    asset_geofence_event_b,
):
    """Tenant A GET/POST to Tenant B detail, edit, and delete endpoints returns 404; Tenant B records stay intact."""
    orig_ins_title = mobile_inspection_b.title
    orig_fwo_title = field_work_order_b.title
    orig_scan_payload = asset_scan_log_b.raw_payload
    orig_geo_fence = asset_geofence_event_b.fence_name

    # MobileAssetInspection
    ins_detail = reverse("assets:mobile_asset_inspection_detail", kwargs={"pk": mobile_inspection_b.pk})
    ins_edit = reverse("assets:mobile_asset_inspection_edit", kwargs={"pk": mobile_inspection_b.pk})
    ins_delete = reverse("assets:mobile_asset_inspection_delete", kwargs={"pk": mobile_inspection_b.pk})
    assert client_a.get(ins_detail).status_code == 404
    assert client_a.get(ins_edit).status_code == 404
    assert (
        client_a.post(
            ins_edit,
            data=_mobile_asset_sec_inspection_payload(operational_asset_b, admin_b, title="IDOR Hijack"),
        ).status_code
        == 404
    )
    assert client_a.post(ins_delete).status_code == 404

    # FieldWorkOrder
    fwo_detail = reverse("assets:field_work_order_detail", kwargs={"pk": field_work_order_b.pk})
    fwo_edit = reverse("assets:field_work_order_edit", kwargs={"pk": field_work_order_b.pk})
    fwo_delete = reverse("assets:field_work_order_delete", kwargs={"pk": field_work_order_b.pk})
    assert client_a.get(fwo_detail).status_code == 404
    assert client_a.get(fwo_edit).status_code == 404
    assert (
        client_a.post(
            fwo_edit,
            data=_mobile_asset_sec_work_order_payload(operational_asset_b, admin_b, title="IDOR Hijack"),
        ).status_code
        == 404
    )
    assert client_a.post(fwo_delete).status_code == 404

    # AssetScanLog
    scan_detail = reverse("assets:asset_scan_log_detail", kwargs={"pk": asset_scan_log_b.pk})
    scan_edit = reverse("assets:asset_scan_log_edit", kwargs={"pk": asset_scan_log_b.pk})
    scan_delete = reverse("assets:asset_scan_log_delete", kwargs={"pk": asset_scan_log_b.pk})
    assert client_a.get(scan_detail).status_code == 404
    assert client_a.get(scan_edit).status_code == 404
    assert (
        client_a.post(
            scan_edit,
            data=_mobile_asset_sec_scan_log_payload(admin_b, operational_asset_b, raw_payload="HIJACK"),
        ).status_code
        == 404
    )
    assert client_a.post(scan_delete).status_code == 404

    # AssetGeofenceEvent
    geo_detail = reverse("assets:asset_geofence_event_detail", kwargs={"pk": asset_geofence_event_b.pk})
    geo_edit = reverse("assets:asset_geofence_event_edit", kwargs={"pk": asset_geofence_event_b.pk})
    geo_delete = reverse("assets:asset_geofence_event_delete", kwargs={"pk": asset_geofence_event_b.pk})
    assert client_a.get(geo_detail).status_code == 404
    assert client_a.get(geo_edit).status_code == 404
    assert (
        client_a.post(
            geo_edit,
            data=_mobile_asset_sec_geofence_event_payload(operational_asset_b, fence_name="IDOR Hijack"),
        ).status_code
        == 404
    )
    assert client_a.post(geo_delete).status_code == 404

    # Verify all Tenant B records remain intact and unchanged
    mobile_inspection_b.refresh_from_db()
    field_work_order_b.refresh_from_db()
    asset_scan_log_b.refresh_from_db()
    asset_geofence_event_b.refresh_from_db()

    assert mobile_inspection_b.tenant == tenant_b and mobile_inspection_b.title == orig_ins_title
    assert field_work_order_b.tenant == tenant_b and field_work_order_b.title == orig_fwo_title
    assert asset_scan_log_b.tenant == tenant_b and asset_scan_log_b.raw_payload == orig_scan_payload
    assert asset_geofence_event_b.tenant == tenant_b and asset_geofence_event_b.fence_name == orig_geo_fence


def test_mobile_asset_security_idor_tenant_b_to_tenant_a_returns_404_and_preserves_records(
    client_b,
    tenant_a,
    operational_asset_a,
    admin_user,
    mobile_inspection_a,
    field_work_order_a,
    asset_scan_log_a,
    asset_geofence_event_a,
):
    """Symmetric IDOR: Tenant B GET/POST to Tenant A detail, edit, and delete endpoints returns 404."""
    orig_ins_title = mobile_inspection_a.title
    orig_fwo_title = field_work_order_a.title
    orig_scan_payload = asset_scan_log_a.raw_payload
    orig_geo_fence = asset_geofence_event_a.fence_name

    targets = [
        (
            "mobile_asset_inspection",
            mobile_inspection_a.pk,
            _mobile_asset_sec_inspection_payload(operational_asset_a, admin_user, title="IDOR B->A"),
        ),
        (
            "field_work_order",
            field_work_order_a.pk,
            _mobile_asset_sec_work_order_payload(operational_asset_a, admin_user, title="IDOR B->A"),
        ),
        (
            "asset_scan_log",
            asset_scan_log_a.pk,
            _mobile_asset_sec_scan_log_payload(admin_user, operational_asset_a, raw_payload="IDOR-B-A"),
        ),
        (
            "asset_geofence_event",
            asset_geofence_event_a.pk,
            _mobile_asset_sec_geofence_event_payload(operational_asset_a, fence_name="IDOR B->A"),
        ),
    ]

    for prefix, pk, payload in targets:
        assert client_b.get(reverse(f"assets:{prefix}_detail", kwargs={"pk": pk})).status_code == 404
        assert client_b.get(reverse(f"assets:{prefix}_edit", kwargs={"pk": pk})).status_code == 404
        assert client_b.post(reverse(f"assets:{prefix}_edit", kwargs={"pk": pk}), data=payload).status_code == 404
        assert client_b.post(reverse(f"assets:{prefix}_delete", kwargs={"pk": pk})).status_code == 404

    mobile_inspection_a.refresh_from_db()
    field_work_order_a.refresh_from_db()
    asset_scan_log_a.refresh_from_db()
    asset_geofence_event_a.refresh_from_db()

    assert mobile_inspection_a.tenant == tenant_a and mobile_inspection_a.title == orig_ins_title
    assert field_work_order_a.tenant == tenant_a and field_work_order_a.title == orig_fwo_title
    assert asset_scan_log_a.tenant == tenant_a and asset_scan_log_a.raw_payload == orig_scan_payload
    assert asset_geofence_event_a.tenant == tenant_a and asset_geofence_event_a.fence_name == orig_geo_fence


def test_mobile_asset_security_list_views_and_kpis_tenant_isolated(
    client_a,
    client_b,
    mobile_inspection_a,
    mobile_inspection_b,
    field_work_order_a,
    field_work_order_b,
    asset_scan_log_a,
    asset_scan_log_b,
    asset_geofence_event_a,
    asset_geofence_event_b,
):
    """List views and KPI cards strictly show only the authenticated user's tenant records."""
    # Inspections
    resp_ins_a = client_a.get(reverse("assets:mobile_asset_inspection_list"))
    assert resp_ins_a.status_code == 200
    assert mobile_inspection_a in resp_ins_a.context["inspections"]
    assert mobile_inspection_b not in resp_ins_a.context["inspections"]
    assert resp_ins_a.context["total_inspections"] == 1
    assert mobile_inspection_b.title not in resp_ins_a.content.decode("utf-8")

    resp_ins_b = client_b.get(reverse("assets:mobile_asset_inspection_list"))
    assert resp_ins_b.status_code == 200
    assert mobile_inspection_b in resp_ins_b.context["inspections"]
    assert mobile_inspection_a not in resp_ins_b.context["inspections"]
    assert resp_ins_b.context["total_inspections"] == 1
    assert mobile_inspection_a.title not in resp_ins_b.content.decode("utf-8")

    # Field Work Orders
    resp_fwo_a = client_a.get(reverse("assets:field_work_order_list"))
    assert resp_fwo_a.status_code == 200
    assert field_work_order_a in resp_fwo_a.context["work_orders"]
    assert field_work_order_b not in resp_fwo_a.context["work_orders"]
    assert resp_fwo_a.context["total_work_orders"] == 1
    assert field_work_order_b.title not in resp_fwo_a.content.decode("utf-8")

    resp_fwo_b = client_b.get(reverse("assets:field_work_order_list"))
    assert resp_fwo_b.status_code == 200
    assert field_work_order_b in resp_fwo_b.context["work_orders"]
    assert field_work_order_a not in resp_fwo_b.context["work_orders"]
    assert resp_fwo_b.context["total_work_orders"] == 1
    assert field_work_order_a.title not in resp_fwo_b.content.decode("utf-8")

    # Asset Scan Logs
    resp_scan_a = client_a.get(reverse("assets:asset_scan_log_list"))
    assert resp_scan_a.status_code == 200
    assert asset_scan_log_a in resp_scan_a.context["scans"]
    assert asset_scan_log_b not in resp_scan_a.context["scans"]
    assert resp_scan_a.context["total_scans"] == 1
    assert asset_scan_log_b.raw_payload not in resp_scan_a.content.decode("utf-8")

    resp_scan_b = client_b.get(reverse("assets:asset_scan_log_list"))
    assert resp_scan_b.status_code == 200
    assert asset_scan_log_b in resp_scan_b.context["scans"]
    assert asset_scan_log_a not in resp_scan_b.context["scans"]
    assert resp_scan_b.context["total_scans"] == 1
    assert asset_scan_log_a.raw_payload not in resp_scan_b.content.decode("utf-8")

    # Asset Geofence Events
    resp_geo_a = client_a.get(reverse("assets:asset_geofence_event_list"))
    assert resp_geo_a.status_code == 200
    assert asset_geofence_event_a in resp_geo_a.context["events"]
    assert asset_geofence_event_b not in resp_geo_a.context["events"]
    assert resp_geo_a.context["total_events"] == 1
    assert asset_geofence_event_b.fence_name not in resp_geo_a.content.decode("utf-8")

    resp_geo_b = client_b.get(reverse("assets:asset_geofence_event_list"))
    assert resp_geo_b.status_code == 200
    assert asset_geofence_event_b in resp_geo_b.context["events"]
    assert asset_geofence_event_a not in resp_geo_b.context["events"]
    assert resp_geo_b.context["total_events"] == 1
    assert asset_geofence_event_a.fence_name not in resp_geo_b.content.decode("utf-8")


# ==============================================================================
# 4. Cross-Tenant Foreign Key Injection Defense (via POST Create & Edit)
# ==============================================================================


def test_mobile_asset_security_cross_tenant_fk_injection_inspection(
    client_a,
    tenant_a,
    admin_user,
    admin_b,
    operational_asset_a,
    operational_asset_b,
    fixed_asset_a,
    fixed_asset_b,
    mobile_inspection_a,
):
    """Tenant A POSTing Tenant B asset, fixed_asset, or inspector fails validation on create and edit."""
    create_url = reverse("assets:mobile_asset_inspection_create")
    edit_url = reverse("assets:mobile_asset_inspection_edit", kwargs={"pk": mobile_inspection_a.pk})

    injection_cases = [
        (
            "asset",
            _mobile_asset_sec_inspection_payload(
                operational_asset_b, admin_user, fixed_asset=fixed_asset_a, title="Injected B Asset"
            ),
        ),
        (
            "fixed_asset",
            _mobile_asset_sec_inspection_payload(
                operational_asset_a, admin_user, fixed_asset=fixed_asset_b, title="Injected B FixedAsset"
            ),
        ),
        (
            "inspector",
            _mobile_asset_sec_inspection_payload(
                operational_asset_a, admin_b, fixed_asset=fixed_asset_a, title="Injected B Inspector"
            ),
        ),
    ]

    for field_name, payload in injection_cases:
        resp_create = client_a.post(create_url, data=payload)
        assert resp_create.status_code == 200
        assert not resp_create.context["form"].is_valid()
        assert field_name in resp_create.context["form"].errors
        assert not MobileAssetInspection.objects.filter(title=payload["title"]).exists()

        resp_edit = client_a.post(edit_url, data=payload)
        assert resp_edit.status_code == 200
        assert not resp_edit.context["form"].is_valid()
        assert field_name in resp_edit.context["form"].errors

    mobile_inspection_a.refresh_from_db()
    assert mobile_inspection_a.asset == operational_asset_a
    assert mobile_inspection_a.fixed_asset == fixed_asset_a
    assert mobile_inspection_a.inspector == admin_user
    assert mobile_inspection_a.tenant == tenant_a


def test_mobile_asset_security_cross_tenant_fk_injection_work_order(
    client_a,
    tenant_a,
    admin_user,
    admin_b,
    operational_asset_a,
    operational_asset_b,
    fixed_asset_a,
    fixed_asset_b,
    maintenance_request_b,
    field_work_order_a,
):
    """Tenant A POSTing Tenant B asset, fixed_asset, assigned_technician, or maintenance_request fails validation."""
    create_url = reverse("assets:field_work_order_create")
    edit_url = reverse("assets:field_work_order_edit", kwargs={"pk": field_work_order_a.pk})

    injection_cases = [
        (
            "asset",
            _mobile_asset_sec_work_order_payload(
                operational_asset_b, admin_user, fixed_asset=fixed_asset_a, title="Injected FWO B Asset"
            ),
        ),
        (
            "fixed_asset",
            _mobile_asset_sec_work_order_payload(
                operational_asset_a, admin_user, fixed_asset=fixed_asset_b, title="Injected FWO B FixedAsset"
            ),
        ),
        (
            "assigned_technician",
            _mobile_asset_sec_work_order_payload(
                operational_asset_a, admin_b, fixed_asset=fixed_asset_a, title="Injected FWO B Tech"
            ),
        ),
        (
            "maintenance_request",
            _mobile_asset_sec_work_order_payload(
                operational_asset_a,
                admin_user,
                fixed_asset=fixed_asset_a,
                maintenance_request=maintenance_request_b,
                title="Injected FWO B MaintReq",
            ),
        ),
    ]

    for field_name, payload in injection_cases:
        resp_create = client_a.post(create_url, data=payload)
        assert resp_create.status_code == 200
        assert not resp_create.context["form"].is_valid()
        assert field_name in resp_create.context["form"].errors
        assert not FieldWorkOrder.objects.filter(title=payload["title"]).exists()

        resp_edit = client_a.post(edit_url, data=payload)
        assert resp_edit.status_code == 200
        assert not resp_edit.context["form"].is_valid()
        assert field_name in resp_edit.context["form"].errors

    field_work_order_a.refresh_from_db()
    assert field_work_order_a.asset == operational_asset_a
    assert field_work_order_a.fixed_asset == fixed_asset_a
    assert field_work_order_a.assigned_technician == admin_user
    assert field_work_order_a.tenant == tenant_a


def test_mobile_asset_security_cross_tenant_fk_injection_scan_log(
    client_a,
    tenant_a,
    admin_user,
    admin_b,
    operational_asset_a,
    operational_asset_b,
    asset_scan_log_a,
):
    """Tenant A POSTing Tenant B asset or scanned_by fails validation on create and edit."""
    create_url = reverse("assets:asset_scan_log_create")
    edit_url = reverse("assets:asset_scan_log_edit", kwargs={"pk": asset_scan_log_a.pk})

    injection_cases = [
        (
            "asset",
            _mobile_asset_sec_scan_log_payload(
                admin_user, asset=operational_asset_b, raw_payload="INJECT-SCAN-ASSET-B"
            ),
        ),
        (
            "scanned_by",
            _mobile_asset_sec_scan_log_payload(
                admin_b, asset=operational_asset_a, raw_payload="INJECT-SCAN-USER-B"
            ),
        ),
    ]

    for field_name, payload in injection_cases:
        resp_create = client_a.post(create_url, data=payload)
        assert resp_create.status_code == 200
        assert not resp_create.context["form"].is_valid()
        assert field_name in resp_create.context["form"].errors
        assert not AssetScanLog.objects.filter(raw_payload=payload["raw_payload"]).exists()

        resp_edit = client_a.post(edit_url, data=payload)
        assert resp_edit.status_code == 200
        assert not resp_edit.context["form"].is_valid()
        assert field_name in resp_edit.context["form"].errors

    asset_scan_log_a.refresh_from_db()
    assert asset_scan_log_a.asset == operational_asset_a
    assert asset_scan_log_a.scanned_by == admin_user
    assert asset_scan_log_a.tenant == tenant_a


def test_mobile_asset_security_cross_tenant_fk_injection_geofence_event(
    client_a,
    tenant_a,
    admin_b,
    operational_asset_a,
    operational_asset_b,
    asset_geofence_event_a,
):
    """Tenant A POSTing Tenant B asset or acknowledged_by fails validation on create and edit."""
    create_url = reverse("assets:asset_geofence_event_create")
    edit_url = reverse("assets:asset_geofence_event_edit", kwargs={"pk": asset_geofence_event_a.pk})

    injection_cases = [
        (
            "asset",
            _mobile_asset_sec_geofence_event_payload(
                operational_asset_b, fence_name="Injected GEO B Asset"
            ),
        ),
        (
            "acknowledged_by",
            _mobile_asset_sec_geofence_event_payload(
                operational_asset_a, acknowledged_by=admin_b, fence_name="Injected GEO B AckUser"
            ),
        ),
    ]

    for field_name, payload in injection_cases:
        resp_create = client_a.post(create_url, data=payload)
        assert resp_create.status_code == 200
        assert not resp_create.context["form"].is_valid()
        assert field_name in resp_create.context["form"].errors
        assert not AssetGeofenceEvent.objects.filter(fence_name=payload["fence_name"]).exists()

        resp_edit = client_a.post(edit_url, data=payload)
        assert resp_edit.status_code == 200
        assert not resp_edit.context["form"].is_valid()
        assert field_name in resp_edit.context["form"].errors

    asset_geofence_event_a.refresh_from_db()
    assert asset_geofence_event_a.asset == operational_asset_a
    assert asset_geofence_event_a.acknowledged_by is None
    assert asset_geofence_event_a.tenant == tenant_a


# ==============================================================================
# 5. Mass Assignment & System Timestamp Tamper Prevention
# ==============================================================================


def test_mobile_asset_security_mass_assignment_forms_exclude_system_fields(tenant_a):
    """All 4 ModelForms exclude tenant, number, and server-managed timestamps from Meta.fields."""
    forbidden_by_form = [
        (
            MobileAssetInspectionForm(tenant=tenant_a),
            {"tenant", "number", "synced_at", "created_at", "updated_at"},
        ),
        (
            FieldWorkOrderForm(tenant=tenant_a),
            {"tenant", "number", "actual_arrival", "completed_at", "signed_at", "synced_at", "created_at", "updated_at"},
        ),
        (
            AssetScanLogForm(tenant=tenant_a),
            {"tenant", "number", "scanned_at", "created_at", "updated_at"},
        ),
        (
            AssetGeofenceEventForm(tenant=tenant_a),
            {"tenant", "number", "detected_at", "acknowledged_at", "created_at", "updated_at"},
        ),
    ]
    for form, forbidden_fields in forbidden_by_form:
        for field_name in forbidden_fields:
            assert field_name not in form.fields, f"{field_name} leaked in {type(form).__name__}"


def test_mobile_asset_security_mass_assignment_post_inspection(
    client_a, tenant_a, tenant_b, operational_asset_a, admin_user, mobile_inspection_a
):
    """POSTing forged tenant, number, and synced_at is ignored on MobileAssetInspection create and edit."""
    forged_dt = "2001-01-01T00:00:00Z"

    # 1. Create POST with forged fields (online capture -> synced_at must stay None)
    payload_create = _mobile_asset_sec_inspection_payload(
        operational_asset_a,
        admin_user,
        title="MassAssign Inspection Create",
        is_offline_captured=False,
        tenant=str(tenant_b.pk),
        number="MINS-99999",
        synced_at=forged_dt,
        created_at=forged_dt,
        updated_at=forged_dt,
    )
    resp_create = client_a.post(reverse("assets:mobile_asset_inspection_create"), data=payload_create)
    assert resp_create.status_code == 302
    created = MobileAssetInspection.objects.get(title="MassAssign Inspection Create")
    assert created.tenant == tenant_a
    assert created.number != "MINS-99999"
    assert created.number.startswith("MINS-")
    assert created.synced_at is None
    assert created.created_at.year >= 2025

    # 2. Edit POST with forged fields (offline capture -> server sets synced_at to now, not 2001)
    orig_number = mobile_inspection_a.number
    payload_edit = _mobile_asset_sec_inspection_payload(
        operational_asset_a,
        admin_user,
        title="MassAssign Inspection Edit",
        is_offline_captured=True,
        tenant=str(tenant_b.pk),
        number="MINS-88888",
        synced_at=forged_dt,
    )
    resp_edit = client_a.post(
        reverse("assets:mobile_asset_inspection_edit", kwargs={"pk": mobile_inspection_a.pk}),
        data=payload_edit,
    )
    assert resp_edit.status_code == 302
    mobile_inspection_a.refresh_from_db()
    assert mobile_inspection_a.tenant == tenant_a
    assert mobile_inspection_a.number == orig_number
    assert mobile_inspection_a.synced_at is not None
    assert mobile_inspection_a.synced_at.year >= 2025


def test_mobile_asset_security_mass_assignment_post_work_order(
    client_a, tenant_a, tenant_b, operational_asset_a, admin_user, field_work_order_a
):
    """POSTing forged tenant, number, completed_at, signed_at, synced_at, and actual_arrival is ignored."""
    forged_dt = "2001-01-01T00:00:00Z"

    # 1. Create POST in non-completed dispatched state -> forged timestamps remain None
    payload_create = _mobile_asset_sec_work_order_payload(
        operational_asset_a,
        admin_user,
        title="MassAssign FWO Create",
        status="dispatched",
        signature_name="",
        is_offline_captured=False,
        tenant=str(tenant_b.pk),
        number="MFWO-99999",
        actual_arrival=forged_dt,
        completed_at=forged_dt,
        signed_at=forged_dt,
        synced_at=forged_dt,
    )
    resp_create = client_a.post(reverse("assets:field_work_order_create"), data=payload_create)
    assert resp_create.status_code == 302
    created = FieldWorkOrder.objects.get(title="MassAssign FWO Create")
    assert created.tenant == tenant_a
    assert created.number != "MFWO-99999"
    assert created.number.startswith("MFWO-")
    assert created.actual_arrival is None
    assert created.completed_at is None
    assert created.signed_at is None
    assert created.synced_at is None

    # 2. Edit POST with completed + signature + offline -> server fills current timestamps, not forged 2001
    orig_number = field_work_order_a.number
    payload_edit = _mobile_asset_sec_work_order_payload(
        operational_asset_a,
        admin_user,
        title="MassAssign FWO Edit",
        status="completed",
        signature_name="Plant Supervisor",
        is_offline_captured=True,
        tenant=str(tenant_b.pk),
        number="MFWO-77777",
        actual_arrival=forged_dt,
        completed_at=forged_dt,
        signed_at=forged_dt,
        synced_at=forged_dt,
    )
    resp_edit = client_a.post(
        reverse("assets:field_work_order_edit", kwargs={"pk": field_work_order_a.pk}),
        data=payload_edit,
    )
    assert resp_edit.status_code == 302
    field_work_order_a.refresh_from_db()
    assert field_work_order_a.tenant == tenant_a
    assert field_work_order_a.number == orig_number
    assert field_work_order_a.actual_arrival.year >= 2025
    assert field_work_order_a.completed_at.year >= 2025
    assert field_work_order_a.signed_at.year >= 2025
    assert field_work_order_a.synced_at.year >= 2025


def test_mobile_asset_security_mass_assignment_post_scan_log(
    client_a, tenant_a, tenant_b, operational_asset_a, admin_user, asset_scan_log_a
):
    """POSTing forged tenant, number, and scanned_at is ignored on AssetScanLog create and edit."""
    forged_dt = "2001-01-01T00:00:00Z"

    payload_create = _mobile_asset_sec_scan_log_payload(
        admin_user,
        asset=operational_asset_a,
        raw_payload="MASSASSIGN-SCAN-CREATE",
        tenant=str(tenant_b.pk),
        number="ASCN-99999",
        scanned_at=forged_dt,
    )
    resp_create = client_a.post(reverse("assets:asset_scan_log_create"), data=payload_create)
    assert resp_create.status_code == 302
    created = AssetScanLog.objects.get(raw_payload="MASSASSIGN-SCAN-CREATE")
    assert created.tenant == tenant_a
    assert created.number != "ASCN-99999"
    assert created.number.startswith("ASCN-")
    assert created.scanned_at.year >= 2025

    orig_number = asset_scan_log_a.number
    orig_scanned_at = asset_scan_log_a.scanned_at
    payload_edit = _mobile_asset_sec_scan_log_payload(
        admin_user,
        asset=operational_asset_a,
        raw_payload="MASSASSIGN-SCAN-EDIT",
        tenant=str(tenant_b.pk),
        number="ASCN-77777",
        scanned_at=forged_dt,
    )
    resp_edit = client_a.post(
        reverse("assets:asset_scan_log_edit", kwargs={"pk": asset_scan_log_a.pk}),
        data=payload_edit,
    )
    assert resp_edit.status_code == 302
    asset_scan_log_a.refresh_from_db()
    assert asset_scan_log_a.tenant == tenant_a
    assert asset_scan_log_a.number == orig_number
    assert asset_scan_log_a.scanned_at == orig_scanned_at


def test_mobile_asset_security_mass_assignment_post_geofence_event(
    client_a, tenant_a, tenant_b, operational_asset_a, asset_geofence_event_a
):
    """POSTing forged tenant, number, detected_at, and acknowledged_at is ignored on AssetGeofenceEvent."""
    forged_dt = "2001-01-01T00:00:00Z"

    # 1. Create POST in open_alert status -> acknowledged_at stays None
    payload_create = _mobile_asset_sec_geofence_event_payload(
        operational_asset_a,
        fence_name="MassAssign Geo Create",
        status="open_alert",
        tenant=str(tenant_b.pk),
        number="AGEO-99999",
        detected_at=forged_dt,
        acknowledged_at=forged_dt,
    )
    resp_create = client_a.post(reverse("assets:asset_geofence_event_create"), data=payload_create)
    assert resp_create.status_code == 302
    created = AssetGeofenceEvent.objects.get(fence_name="MassAssign Geo Create")
    assert created.tenant == tenant_a
    assert created.number != "AGEO-99999"
    assert created.number.startswith("AGEO-")
    assert created.detected_at.year >= 2025
    assert created.acknowledged_at is None

    # 2. Edit POST with status=resolved -> server assigns current acknowledged_at, not forged 2001
    orig_number = asset_geofence_event_a.number
    orig_detected_at = asset_geofence_event_a.detected_at
    payload_edit = _mobile_asset_sec_geofence_event_payload(
        operational_asset_a,
        fence_name="MassAssign Geo Edit",
        status="resolved",
        tenant=str(tenant_b.pk),
        number="AGEO-77777",
        detected_at=forged_dt,
        acknowledged_at=forged_dt,
    )
    resp_edit = client_a.post(
        reverse("assets:asset_geofence_event_edit", kwargs={"pk": asset_geofence_event_a.pk}),
        data=payload_edit,
    )
    assert resp_edit.status_code == 302
    asset_geofence_event_a.refresh_from_db()
    assert asset_geofence_event_a.tenant == tenant_a
    assert asset_geofence_event_a.number == orig_number
    assert asset_geofence_event_a.detected_at == orig_detected_at
    assert asset_geofence_event_a.acknowledged_at is not None
    assert asset_geofence_event_a.acknowledged_at.year >= 2025


# ==============================================================================
# 6. HTTP Method (@require_POST) & CSRF Enforcement Gates
# ==============================================================================


def test_mobile_asset_security_delete_endpoints_return_405_on_get(
    client_a,
    mobile_inspection_a,
    field_work_order_a,
    asset_scan_log_a,
    asset_geofence_event_a,
):
    """All 4 delete endpoints strictly enforce @require_POST and return HTTP 405 on GET."""
    delete_urls = [
        reverse("assets:mobile_asset_inspection_delete", kwargs={"pk": mobile_inspection_a.pk}),
        reverse("assets:field_work_order_delete", kwargs={"pk": field_work_order_a.pk}),
        reverse("assets:asset_scan_log_delete", kwargs={"pk": asset_scan_log_a.pk}),
        reverse("assets:asset_geofence_event_delete", kwargs={"pk": asset_geofence_event_a.pk}),
    ]
    for url in delete_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed on GET {url}, got {resp.status_code}"

    assert MobileAssetInspection.objects.filter(pk=mobile_inspection_a.pk).exists()
    assert FieldWorkOrder.objects.filter(pk=field_work_order_a.pk).exists()
    assert AssetScanLog.objects.filter(pk=asset_scan_log_a.pk).exists()
    assert AssetGeofenceEvent.objects.filter(pk=asset_geofence_event_a.pk).exists()


def test_mobile_asset_security_csrf_enforced_on_all_post_endpoints(
    admin_user,
    operational_asset_a,
    mobile_inspection_a,
    field_work_order_a,
    asset_scan_log_a,
    asset_geofence_event_a,
):
    """Client(enforce_csrf_checks=True) rejects all 12 mutating POST endpoints without CSRF token with HTTP 403."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    post_cases = [
        # MobileAssetInspection
        (
            reverse("assets:mobile_asset_inspection_create"),
            _mobile_asset_sec_inspection_payload(operational_asset_a, admin_user, title="CSRF Blocked Ins"),
        ),
        (
            reverse("assets:mobile_asset_inspection_edit", kwargs={"pk": mobile_inspection_a.pk}),
            _mobile_asset_sec_inspection_payload(operational_asset_a, admin_user, title="CSRF Blocked Ins Edit"),
        ),
        (
            reverse("assets:mobile_asset_inspection_delete", kwargs={"pk": mobile_inspection_a.pk}),
            {},
        ),
        # FieldWorkOrder
        (
            reverse("assets:field_work_order_create"),
            _mobile_asset_sec_work_order_payload(operational_asset_a, admin_user, title="CSRF Blocked FWO"),
        ),
        (
            reverse("assets:field_work_order_edit", kwargs={"pk": field_work_order_a.pk}),
            _mobile_asset_sec_work_order_payload(operational_asset_a, admin_user, title="CSRF Blocked FWO Edit"),
        ),
        (
            reverse("assets:field_work_order_delete", kwargs={"pk": field_work_order_a.pk}),
            {},
        ),
        # AssetScanLog
        (
            reverse("assets:asset_scan_log_create"),
            _mobile_asset_sec_scan_log_payload(admin_user, operational_asset_a, raw_payload="CSRF-BLOCKED-SCAN"),
        ),
        (
            reverse("assets:asset_scan_log_edit", kwargs={"pk": asset_scan_log_a.pk}),
            _mobile_asset_sec_scan_log_payload(admin_user, operational_asset_a, raw_payload="CSRF-BLOCKED-EDIT"),
        ),
        (
            reverse("assets:asset_scan_log_delete", kwargs={"pk": asset_scan_log_a.pk}),
            {},
        ),
        # AssetGeofenceEvent
        (
            reverse("assets:asset_geofence_event_create"),
            _mobile_asset_sec_geofence_event_payload(operational_asset_a, fence_name="CSRF Blocked Geo"),
        ),
        (
            reverse("assets:asset_geofence_event_edit", kwargs={"pk": asset_geofence_event_a.pk}),
            _mobile_asset_sec_geofence_event_payload(operational_asset_a, fence_name="CSRF Blocked Geo Edit"),
        ),
        (
            reverse("assets:asset_geofence_event_delete", kwargs={"pk": asset_geofence_event_a.pk}),
            {},
        ),
    ]

    for url, payload in post_cases:
        resp = csrf_client.post(url, data=payload)
        assert resp.status_code == 403, f"Expected 403 CSRF rejection on POST {url}, got {resp.status_code}"

    # Verify zero mutations occurred
    assert not MobileAssetInspection.objects.filter(title__startswith="CSRF Blocked").exists()
    assert not FieldWorkOrder.objects.filter(title__startswith="CSRF Blocked").exists()
    assert not AssetScanLog.objects.filter(raw_payload__startswith="CSRF-BLOCKED").exists()
    assert not AssetGeofenceEvent.objects.filter(fence_name__startswith="CSRF Blocked").exists()

    mobile_inspection_a.refresh_from_db()
    field_work_order_a.refresh_from_db()
    asset_scan_log_a.refresh_from_db()
    asset_geofence_event_a.refresh_from_db()
    assert mobile_inspection_a.title != "CSRF Blocked Ins Edit"
    assert field_work_order_a.title != "CSRF Blocked FWO Edit"
    assert asset_scan_log_a.raw_payload != "CSRF-BLOCKED-EDIT"
    assert asset_geofence_event_a.fence_name != "CSRF Blocked Geo Edit"


# ==============================================================================
# 7. Stored XSS Escaping & Input Fuzzing Tests
# ==============================================================================


def test_mobile_asset_security_stored_xss_escaped_inspection(
    client_a, tenant_a, operational_asset_a, admin_user
):
    """XSS payloads in MobileAssetInspection text fields are rendered HTML-escaped in detail and list views."""
    xss_title = "<script>alert('xss-ins-title')</script>"
    xss_checklist = "<img src=x onerror=alert('xss-ins-chk')>"
    xss_findings = "<svg onload=alert('xss-ins-fnd')>"
    xss_voice = "<script>alert('xss-ins-vox')</script>"
    xss_caption = "<b onmouseover=alert(1)>caption</b>"

    payload = _mobile_asset_sec_inspection_payload(
        operational_asset_a,
        admin_user,
        title=xss_title,
        checklist_summary=xss_checklist,
        findings_summary=xss_findings,
        voice_notes_transcription=xss_voice,
        photo_url="https://cdn.example.com/inspections/xss-check.jpg",
        photo_caption=xss_caption,
    )
    resp_create = client_a.post(reverse("assets:mobile_asset_inspection_create"), data=payload)
    assert resp_create.status_code == 302

    ins = MobileAssetInspection.objects.get(tenant=tenant_a, title=xss_title)

    # Detail HTML must escape all 5 text payloads
    resp_detail = client_a.get(reverse("assets:mobile_asset_inspection_detail", kwargs={"pk": ins.pk}))
    assert resp_detail.status_code == 200
    detail_html = resp_detail.content.decode("utf-8")
    for raw in [xss_title, xss_checklist, xss_findings, xss_voice, xss_caption]:
        assert raw not in detail_html
        assert escape(raw) in detail_html

    # List HTML must escape title
    resp_list = client_a.get(reverse("assets:mobile_asset_inspection_list"))
    assert resp_list.status_code == 200
    list_html = resp_list.content.decode("utf-8")
    assert xss_title not in list_html
    assert escape(xss_title) in list_html


def test_mobile_asset_security_stored_xss_escaped_work_order(
    client_a, tenant_a, operational_asset_a, admin_user
):
    """XSS payloads in FieldWorkOrder text fields are rendered HTML-escaped in detail and list views."""
    xss_title = "<script>alert('xss-fwo-title')</script>"
    xss_parts = "<img src=x onerror=alert('xss-fwo-parts')>"
    xss_work = "<svg onload=alert('xss-fwo-work')>"
    xss_sig_name = "<script>alert('xss-fwo-sig')</script>"
    xss_sig_desig = "<div onmouseover=alert(1)>Mgr</div>"

    payload = _mobile_asset_sec_work_order_payload(
        operational_asset_a,
        admin_user,
        title=xss_title,
        parts_requisition_notes=xss_parts,
        work_performed_notes=xss_work,
        signature_name=xss_sig_name,
        signature_designation=xss_sig_desig,
    )
    resp_create = client_a.post(reverse("assets:field_work_order_create"), data=payload)
    assert resp_create.status_code == 302

    fwo = FieldWorkOrder.objects.get(tenant=tenant_a, title=xss_title)

    # Detail HTML
    resp_detail = client_a.get(reverse("assets:field_work_order_detail", kwargs={"pk": fwo.pk}))
    assert resp_detail.status_code == 200
    detail_html = resp_detail.content.decode("utf-8")
    for raw in [xss_title, xss_parts, xss_work, xss_sig_name, xss_sig_desig]:
        assert raw not in detail_html
        assert escape(raw) in detail_html

    # List HTML
    resp_list = client_a.get(reverse("assets:field_work_order_list"))
    assert resp_list.status_code == 200
    list_html = resp_list.content.decode("utf-8")
    assert xss_title not in list_html
    assert escape(xss_title) in list_html


def test_mobile_asset_security_stored_xss_escaped_scan_log(
    client_a, tenant_a, operational_asset_a, admin_user
):
    """XSS payloads in AssetScanLog text fields are rendered HTML-escaped in detail and list views."""
    xss_raw_payload = "<script>alert('xss-scan-raw')</script>"
    xss_device_info = "<img src=x onerror=alert('xss-scan-dev')>"
    xss_notes = "<svg onload=alert('xss-scan-notes')>"

    payload = _mobile_asset_sec_scan_log_payload(
        admin_user,
        asset=operational_asset_a,
        raw_payload=xss_raw_payload,
        device_info=xss_device_info,
        notes=xss_notes,
    )
    resp_create = client_a.post(reverse("assets:asset_scan_log_create"), data=payload)
    assert resp_create.status_code == 302

    scan = AssetScanLog.objects.get(tenant=tenant_a, raw_payload=xss_raw_payload)

    # Detail HTML
    resp_detail = client_a.get(reverse("assets:asset_scan_log_detail", kwargs={"pk": scan.pk}))
    assert resp_detail.status_code == 200
    detail_html = resp_detail.content.decode("utf-8")
    for raw in [xss_raw_payload, xss_device_info, xss_notes]:
        assert raw not in detail_html
        assert escape(raw) in detail_html

    # List HTML
    resp_list = client_a.get(reverse("assets:asset_scan_log_list"))
    assert resp_list.status_code == 200
    list_html = resp_list.content.decode("utf-8")
    for raw in [xss_raw_payload, xss_device_info]:
        assert raw not in list_html
        assert escape(raw) in list_html


def test_mobile_asset_security_stored_xss_escaped_geofence_event(
    client_a, tenant_a, operational_asset_a
):
    """XSS payloads in AssetGeofenceEvent text fields are rendered HTML-escaped in detail and list views."""
    xss_fence_name = "<script>alert('xss-geo-fence')</script>"
    xss_resolution = "<img src=x onerror=alert('xss-geo-res')>"

    payload = _mobile_asset_sec_geofence_event_payload(
        operational_asset_a,
        fence_name=xss_fence_name,
        resolution_notes=xss_resolution,
    )
    resp_create = client_a.post(reverse("assets:asset_geofence_event_create"), data=payload)
    assert resp_create.status_code == 302

    event = AssetGeofenceEvent.objects.get(tenant=tenant_a, fence_name=xss_fence_name)

    # Detail HTML
    resp_detail = client_a.get(reverse("assets:asset_geofence_event_detail", kwargs={"pk": event.pk}))
    assert resp_detail.status_code == 200
    detail_html = resp_detail.content.decode("utf-8")
    for raw in [xss_fence_name, xss_resolution]:
        assert raw not in detail_html
        assert escape(raw) in detail_html

    # List HTML
    resp_list = client_a.get(reverse("assets:asset_geofence_event_list"))
    assert resp_list.status_code == 200
    list_html = resp_list.content.decode("utf-8")
    assert xss_fence_name not in list_html
    assert escape(xss_fence_name) in list_html


def test_mobile_asset_security_fuzzing_query_params_and_reflected_xss_safe(
    client_a,
    mobile_inspection_a,
    field_work_order_a,
    asset_scan_log_a,
    asset_geofence_event_a,
):
    """Malicious search/filter/pagination params never trigger 500 or unescaped XSS reflection."""
    xss_query = "<script>alert('reflected-xss')</script>"
    attr_breakout = '" onmouseover="alert(1)"'
    malicious_queries = [
        xss_query,
        attr_breakout,
        "'; DROP TABLE assets_mobileassetinspection; --",
        "' OR '1'='1",
        "A" * 2000,
    ]
    bad_pages = ["abc", "-1", "999999", "NaN", "Infinity", xss_query]

    list_urls = [
        reverse("assets:mobile_asset_inspection_list"),
        reverse("assets:field_work_order_list"),
        reverse("assets:asset_scan_log_list"),
        reverse("assets:asset_geofence_event_list"),
    ]

    for url in list_urls:
        for q_val in malicious_queries:
            resp = client_a.get(url, {"q": q_val, "status": q_val})
            assert resp.status_code == 200
            body = resp.content.decode("utf-8")
            assert xss_query not in body
            assert attr_breakout not in body
        for bad_page in bad_pages:
            resp = client_a.get(url, {"page": bad_page})
            assert resp.status_code == 200
            assert xss_query not in resp.content.decode("utf-8")


def test_mobile_asset_security_audit_logs_not_written_on_idor_or_fk_injection(
    client_a,
    tenant_a,
    tenant_b,
    admin_user,
    operational_asset_b,
    mobile_inspection_b,
    field_work_order_b,
    asset_scan_log_b,
    asset_geofence_event_b,
):
    """Blocked cross-tenant IDOR and FK injection attempts do not emit AuditLog entries."""
    initial_log_count = AuditLog.objects.count()

    # Cross-tenant delete IDOR attempts
    client_a.post(reverse("assets:mobile_asset_inspection_delete", kwargs={"pk": mobile_inspection_b.pk}))
    client_a.post(reverse("assets:field_work_order_delete", kwargs={"pk": field_work_order_b.pk}))
    client_a.post(reverse("assets:asset_scan_log_delete", kwargs={"pk": asset_scan_log_b.pk}))
    client_a.post(reverse("assets:asset_geofence_event_delete", kwargs={"pk": asset_geofence_event_b.pk}))

    # Cross-tenant FK injection attempt
    client_a.post(
        reverse("assets:mobile_asset_inspection_create"),
        data=_mobile_asset_sec_inspection_payload(operational_asset_b, admin_user, title="NoAuditLog"),
    )

    assert AuditLog.objects.count() == initial_log_count
