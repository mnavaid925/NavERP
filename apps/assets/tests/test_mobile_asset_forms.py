"""
Unit and tenant-isolation tests for Sub-module 11.13 Mobile Asset Management forms.

Covers:
1. Security Invariants (Mass Assignment):
   - Excludes 'tenant', 'number', and internal timestamps from Meta.fields across all 4 forms.
2. MobileAssetInspectionForm:
   - Valid data creation and edit
   - Minimal valid submission with only required fields
   - Missing required fields validation
   - Foreign key queryset scoping (asset, fixed_asset, inspector)
   - Cross-tenant reject_foreign validation (asset, fixed_asset, inspector)
3. FieldWorkOrderForm:
   - Valid data creation and edit
   - Minimal valid submission with only required fields
   - Missing required fields validation
   - Foreign key queryset scoping (asset, fixed_asset, assigned_technician, maintenance_request)
   - Cross-tenant reject_foreign validation (asset, fixed_asset, assigned_technician, maintenance_request)
4. AssetScanLogForm:
   - Valid data creation with asset and GPS coordinates
   - Valid unmatched/unassigned submission (optional asset=None)
   - Missing required fields validation
   - Foreign key queryset scoping (asset, scanned_by)
   - Cross-tenant reject_foreign validation (asset, scanned_by)
5. AssetGeofenceEventForm:
   - Valid data creation and edit
   - Minimal valid submission without acknowledged_by
   - Missing required fields validation
   - Foreign key queryset scoping (asset, acknowledged_by)
   - Cross-tenant reject_foreign validation (asset, acknowledged_by)
6. Tenant binding and initialization invariants.
"""
from decimal import Decimal
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounting.models import FixedAsset
from apps.assets.forms import (
    AssetGeofenceEventForm,
    AssetScanLogForm,
    FieldWorkOrderForm,
    MobileAssetInspectionForm,
)
from apps.assets.models import (
    AssetGeofenceEvent,
    AssetMaintenanceRequest,
    AssetScanLog,
    FieldWorkOrder,
    MobileAssetInspection,
)
from apps.scm.models import Asset

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Payload Builders (prefixed with _mobile_asset_*)
# ==============================================================================

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
# 1. Security Invariants: Mass Assignment Exclusions
# ==============================================================================

def test_mobile_asset_form_mass_assignment_inspection(tenant_a):
    """Ensure tenant, number, and internal timestamps are strictly excluded from MobileAssetInspectionForm."""
    form = MobileAssetInspectionForm(tenant=tenant_a)
    forbidden_fields = {"tenant", "number", "synced_at", "created_at", "updated_at"}
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"{field_name} must NOT be exposed in form.fields"


def test_mobile_asset_form_mass_assignment_work_order(tenant_a):
    """Ensure tenant, number, and internal timestamps are strictly excluded from FieldWorkOrderForm."""
    form = FieldWorkOrderForm(tenant=tenant_a)
    forbidden_fields = {"tenant", "number", "completed_at", "signed_at", "synced_at", "created_at", "updated_at"}
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"{field_name} must NOT be exposed in form.fields"


def test_mobile_asset_form_mass_assignment_scan_log(tenant_a):
    """Ensure tenant, number, and internal timestamps are strictly excluded from AssetScanLogForm."""
    form = AssetScanLogForm(tenant=tenant_a)
    forbidden_fields = {"tenant", "number", "scanned_at", "created_at", "updated_at"}
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"{field_name} must NOT be exposed in form.fields"


def test_mobile_asset_form_mass_assignment_geofence_event(tenant_a):
    """Ensure tenant, number, and internal timestamps are strictly excluded from AssetGeofenceEventForm."""
    form = AssetGeofenceEventForm(tenant=tenant_a)
    forbidden_fields = {"tenant", "number", "detected_at", "acknowledged_at", "created_at", "updated_at"}
    for field_name in forbidden_fields:
        assert field_name not in form.fields, f"{field_name} must NOT be exposed in form.fields"


# ==============================================================================
# 2. MobileAssetInspectionForm Tests
# ==============================================================================

def test_mobile_asset_form_inspection_valid_create(tenant_a, operational_asset_a, fixed_asset_a, admin_user):
    """Test full valid submission and clean save() of MobileAssetInspectionForm."""
    payload = _mobile_asset_inspection_payload(
        asset=operational_asset_a,
        inspector=admin_user,
        fixed_asset=fixed_asset_a,
    )
    form = MobileAssetInspectionForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("MINS-")
    assert instance.title == "Daily Pre-Shift Walkaround & Tire Check"
    assert instance.asset == operational_asset_a
    assert instance.fixed_asset == fixed_asset_a
    assert instance.inspector == admin_user
    assert instance.condition_rating == 4
    assert instance.overall_result == "pass"
    assert instance.status == "submitted"
    assert instance.meter_reading == Decimal("1250.50")
    assert instance.gps_latitude == Decimal("37.774929")
    assert instance.gps_longitude == Decimal("-122.419416")


def test_mobile_asset_form_inspection_valid_minimal(tenant_a, operational_asset_a, admin_user):
    """Test minimal valid MobileAssetInspectionForm without optional fields."""
    now_dt = timezone.now().strftime("%Y-%m-%dT%H:%M")
    payload = {
        "title": "Minimal Quick Inspection",
        "inspection_type": "routine_pm",
        "asset": str(operational_asset_a.pk),
        "inspector": str(admin_user.pk),
        "inspection_date": now_dt,
        "overall_result": "pass",
        "condition_rating": "5",
        "status": "draft",
    }
    form = MobileAssetInspectionForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.fixed_asset is None
    assert instance.meter_reading is None
    assert instance.checklist_summary == ""


def test_mobile_asset_form_inspection_valid_edit(tenant_a, operational_asset_a, fixed_asset_a, admin_user):
    """Test editing an existing MobileAssetInspection instance via form."""
    inspection = MobileAssetInspection.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        fixed_asset=fixed_asset_a,
        inspector=admin_user,
        title="Initial Walkaround",
        inspection_type="routine_pm",
        overall_result="pass",
        condition_rating=4,
        status="draft",
    )

    payload = _mobile_asset_inspection_payload(
        asset=operational_asset_a,
        inspector=admin_user,
        fixed_asset=fixed_asset_a,
        title="Updated Supervisory Walkaround",
        status="under_review",
        overall_result="conditional_pass",
        condition_rating="3",
        findings_summary="Hydraulic line weep observed at manifold 2.",
    )
    form = MobileAssetInspectionForm(data=payload, instance=inspection, tenant=tenant_a)
    assert form.is_valid(), form.errors

    saved = form.save()
    assert saved.pk == inspection.pk
    assert saved.title == "Updated Supervisory Walkaround"
    assert saved.status == "under_review"
    assert saved.overall_result == "conditional_pass"
    assert saved.condition_rating == 3
    assert "Hydraulic line weep" in saved.findings_summary


def test_mobile_asset_form_inspection_required_fields(tenant_a):
    """Test validation errors when mandatory fields are omitted."""
    form = MobileAssetInspectionForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "asset" in form.errors
    assert "inspector" in form.errors
    assert "inspection_date" in form.errors


def test_mobile_asset_form_inspection_fk_queryset_scoping(
    tenant_a,
    operational_asset_a,
    operational_asset_b,
    fixed_asset_a,
    fixed_asset_b,
    admin_user,
    admin_b,
):
    """Test that MobileAssetInspectionForm scopes FK querysets exclusively to tenant_a records."""
    form = MobileAssetInspectionForm(tenant=tenant_a)

    asset_pks = set(form.fields["asset"].queryset.values_list("pk", flat=True))
    assert operational_asset_a.pk in asset_pks
    assert operational_asset_b.pk not in asset_pks

    fixed_asset_pks = set(form.fields["fixed_asset"].queryset.values_list("pk", flat=True))
    assert fixed_asset_a.pk in fixed_asset_pks
    assert fixed_asset_b.pk not in fixed_asset_pks

    inspector_pks = set(form.fields["inspector"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in inspector_pks
    assert admin_b.pk not in inspector_pks


def test_mobile_asset_form_inspection_reject_foreign_asset(tenant_a, operational_asset_b, fixed_asset_a, admin_user):
    """Test cross-tenant asset rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_inspection_payload(
        asset=operational_asset_b,
        inspector=admin_user,
        fixed_asset=fixed_asset_a,
    )
    # 1. Scoped queryset blocks it
    form = MobileAssetInspectionForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = MobileAssetInspectionForm(data=payload, tenant=tenant_a)
    form_wide.fields["asset"].queryset = Asset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["asset"]


def test_mobile_asset_form_inspection_reject_foreign_fixed_asset(tenant_a, operational_asset_a, fixed_asset_b, admin_user):
    """Test cross-tenant fixed_asset rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_inspection_payload(
        asset=operational_asset_a,
        inspector=admin_user,
        fixed_asset=fixed_asset_b,
    )
    # 1. Scoped queryset blocks it
    form = MobileAssetInspectionForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = MobileAssetInspectionForm(data=payload, tenant=tenant_a)
    form_wide.fields["fixed_asset"].queryset = FixedAsset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["fixed_asset"]


def test_mobile_asset_form_inspection_reject_foreign_inspector(tenant_a, operational_asset_a, admin_b):
    """Test cross-tenant inspector user rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_inspection_payload(
        asset=operational_asset_a,
        inspector=admin_b,
    )
    # 1. Scoped queryset blocks it
    form = MobileAssetInspectionForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "inspector" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = MobileAssetInspectionForm(data=payload, tenant=tenant_a)
    form_wide.fields["inspector"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["inspector"]


# ==============================================================================
# 3. FieldWorkOrderForm Tests
# ==============================================================================

def test_mobile_asset_form_work_order_valid_create(
    tenant_a,
    operational_asset_a,
    fixed_asset_a,
    admin_user,
    maintenance_request_a,
):
    """Test full valid submission and clean save() of FieldWorkOrderForm."""
    payload = _mobile_asset_work_order_payload(
        asset=operational_asset_a,
        technician=admin_user,
        fixed_asset=fixed_asset_a,
        maintenance_request=maintenance_request_a,
    )
    form = FieldWorkOrderForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("MFWO-")
    assert instance.title == "Field Hydraulic Hose Replacement"
    assert instance.asset == operational_asset_a
    assert instance.fixed_asset == fixed_asset_a
    assert instance.assigned_technician == admin_user
    assert instance.maintenance_request == maintenance_request_a
    assert instance.priority == "high"
    assert instance.status == "dispatched"
    assert instance.labor_wrench_minutes == 180
    assert instance.safety_lockout_confirmed is True
    assert instance.estimated_parts_cost == Decimal("245.50")
    assert instance.dispatch_latitude == Decimal("37.774900")
    assert instance.dispatch_longitude == Decimal("-122.419400")


def test_mobile_asset_form_work_order_valid_minimal(tenant_a, operational_asset_a, admin_user):
    """Test minimal valid FieldWorkOrderForm without optional fields."""
    now_dt = timezone.now().strftime("%Y-%m-%dT%H:%M")
    payload = {
        "title": "Minimal Field Repair",
        "work_order_type": "scheduled_pm",
        "priority": "medium",
        "status": "dispatched",
        "asset": str(operational_asset_a.pk),
        "assigned_technician": str(admin_user.pk),
        "scheduled_start": now_dt,
        "labor_wrench_minutes": "0",
        "estimated_parts_cost": "0.00",
        "safety_lockout_confirmed": False,
        "is_offline_captured": False,
    }
    form = FieldWorkOrderForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.status == "dispatched"
    assert instance.fixed_asset is None
    assert instance.maintenance_request is None
    assert instance.parts_requisition_notes == ""
    assert instance.work_performed_notes == ""


def test_mobile_asset_form_work_order_valid_edit(tenant_a, operational_asset_a, admin_user):
    """Test editing an existing FieldWorkOrder instance via form."""
    work_order = FieldWorkOrder.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        assigned_technician=admin_user,
        title="Initial Dispatch Order",
        work_order_type="scheduled_pm",
        priority="low",
        status="dispatched",
        scheduled_start=timezone.now(),
    )

    payload = _mobile_asset_work_order_payload(
        asset=operational_asset_a,
        technician=admin_user,
        title="Updated Emergency Order",
        work_order_type="emergency_repair",
        priority="urgent",
        status="on_site",
        labor_wrench_minutes="95",
        work_performed_notes="Diagnosed electrical relay fault; replacing component.",
    )
    form = FieldWorkOrderForm(data=payload, instance=work_order, tenant=tenant_a)
    assert form.is_valid(), form.errors

    saved = form.save()
    assert saved.pk == work_order.pk
    assert saved.title == "Updated Emergency Order"
    assert saved.priority == "urgent"
    assert saved.status == "on_site"
    assert saved.labor_wrench_minutes == 95
    assert "electrical relay fault" in saved.work_performed_notes


def test_mobile_asset_form_work_order_required_fields(tenant_a):
    """Test validation errors when mandatory fields are omitted."""
    form = FieldWorkOrderForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "title" in form.errors
    assert "asset" in form.errors
    assert "assigned_technician" in form.errors
    assert "scheduled_start" in form.errors


def test_mobile_asset_form_work_order_fk_queryset_scoping(
    tenant_a,
    operational_asset_a,
    operational_asset_b,
    fixed_asset_a,
    fixed_asset_b,
    admin_user,
    admin_b,
    maintenance_request_a,
    maintenance_request_b,
):
    """Test that FieldWorkOrderForm scopes FK querysets exclusively to tenant_a records."""
    form = FieldWorkOrderForm(tenant=tenant_a)

    asset_pks = set(form.fields["asset"].queryset.values_list("pk", flat=True))
    assert operational_asset_a.pk in asset_pks
    assert operational_asset_b.pk not in asset_pks

    fixed_asset_pks = set(form.fields["fixed_asset"].queryset.values_list("pk", flat=True))
    assert fixed_asset_a.pk in fixed_asset_pks
    assert fixed_asset_b.pk not in fixed_asset_pks

    tech_pks = set(form.fields["assigned_technician"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in tech_pks
    assert admin_b.pk not in tech_pks

    req_pks = set(form.fields["maintenance_request"].queryset.values_list("pk", flat=True))
    assert maintenance_request_a.pk in req_pks
    assert maintenance_request_b.pk not in req_pks


def test_mobile_asset_form_work_order_reject_foreign_asset(tenant_a, operational_asset_b, admin_user):
    """Test cross-tenant asset rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_work_order_payload(
        asset=operational_asset_b,
        technician=admin_user,
    )
    # 1. Scoped queryset blocks it
    form = FieldWorkOrderForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = FieldWorkOrderForm(data=payload, tenant=tenant_a)
    form_wide.fields["asset"].queryset = Asset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["asset"]


def test_mobile_asset_form_work_order_reject_foreign_fixed_asset(tenant_a, operational_asset_a, fixed_asset_b, admin_user):
    """Test cross-tenant fixed_asset rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_work_order_payload(
        asset=operational_asset_a,
        technician=admin_user,
        fixed_asset=fixed_asset_b,
    )
    # 1. Scoped queryset blocks it
    form = FieldWorkOrderForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "fixed_asset" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = FieldWorkOrderForm(data=payload, tenant=tenant_a)
    form_wide.fields["fixed_asset"].queryset = FixedAsset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["fixed_asset"]


def test_mobile_asset_form_work_order_reject_foreign_technician(tenant_a, operational_asset_a, admin_b):
    """Test cross-tenant technician user rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_work_order_payload(
        asset=operational_asset_a,
        technician=admin_b,
    )
    # 1. Scoped queryset blocks it
    form = FieldWorkOrderForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "assigned_technician" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = FieldWorkOrderForm(data=payload, tenant=tenant_a)
    form_wide.fields["assigned_technician"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["assigned_technician"]


def test_mobile_asset_form_work_order_reject_foreign_maintenance_request(
    tenant_a,
    operational_asset_a,
    admin_user,
    maintenance_request_b,
):
    """Test cross-tenant maintenance_request rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_work_order_payload(
        asset=operational_asset_a,
        technician=admin_user,
        maintenance_request=maintenance_request_b,
    )
    # 1. Scoped queryset blocks it
    form = FieldWorkOrderForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "maintenance_request" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = FieldWorkOrderForm(data=payload, tenant=tenant_a)
    form_wide.fields["maintenance_request"].queryset = AssetMaintenanceRequest.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["maintenance_request"]


# ==============================================================================
# 4. AssetScanLogForm Tests
# ==============================================================================

def test_mobile_asset_form_scan_log_valid_create(tenant_a, operational_asset_a, admin_user):
    """Test full valid submission and clean save() of AssetScanLogForm with matched asset."""
    payload = _mobile_asset_scan_log_payload(
        scanned_by=admin_user,
        asset=operational_asset_a,
    )
    form = AssetScanLogForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("ASCN-")
    assert instance.scanned_by == admin_user
    assert instance.asset == operational_asset_a
    assert instance.scan_context == "field_audit"
    assert instance.scan_method == "camera_qr"
    assert instance.raw_payload == "ACME-ASSET-QR-009876"
    assert instance.match_status == "matched"
    assert instance.gps_latitude == Decimal("37.774929")
    assert instance.gps_longitude == Decimal("-122.419416")


def test_mobile_asset_form_scan_log_valid_unmatched_minimal(tenant_a, admin_user):
    """Test valid submission for unmatched tag where asset foreign key is optional/omitted."""
    payload = _mobile_asset_scan_log_payload(
        scanned_by=admin_user,
        asset=None,
        raw_payload="UNKNOWN-BARCODE-9999",
        match_status="not_found",
        notes="Barcode not recognized in active registry.",
    )
    form = AssetScanLogForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.asset is None
    assert instance.match_status == "not_found"
    assert instance.raw_payload == "UNKNOWN-BARCODE-9999"


def test_mobile_asset_form_scan_log_valid_edit(tenant_a, admin_user, operational_asset_a):
    """Test editing an existing AssetScanLog record via form."""
    scan = AssetScanLog.objects.create(
        tenant=tenant_a,
        scanned_by=admin_user,
        raw_payload="ACME-RAW-1122",
        scan_context="receiving",
        scan_method="handheld_laser",
        match_status="unassigned",
    )

    payload = _mobile_asset_scan_log_payload(
        scanned_by=admin_user,
        asset=operational_asset_a,
        raw_payload="ACME-RAW-1122",
        match_status="matched",
        notes="Resolved unassigned tag and bound to operational asset.",
    )
    form = AssetScanLogForm(data=payload, instance=scan, tenant=tenant_a)
    assert form.is_valid(), form.errors

    saved = form.save()
    assert saved.pk == scan.pk
    assert saved.asset == operational_asset_a
    assert saved.match_status == "matched"
    assert "Resolved unassigned tag" in saved.notes


def test_mobile_asset_form_scan_log_required_fields(tenant_a):
    """Test validation errors when mandatory scan log fields are omitted."""
    form = AssetScanLogForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "scanned_by" in form.errors
    assert "raw_payload" in form.errors


def test_mobile_asset_form_scan_log_fk_queryset_scoping(
    tenant_a,
    operational_asset_a,
    operational_asset_b,
    admin_user,
    admin_b,
):
    """Test that AssetScanLogForm scopes FK querysets exclusively to tenant_a records."""
    form = AssetScanLogForm(tenant=tenant_a)

    asset_pks = set(form.fields["asset"].queryset.values_list("pk", flat=True))
    assert operational_asset_a.pk in asset_pks
    assert operational_asset_b.pk not in asset_pks

    scanned_by_pks = set(form.fields["scanned_by"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in scanned_by_pks
    assert admin_b.pk not in scanned_by_pks


def test_mobile_asset_form_scan_log_reject_foreign_asset(tenant_a, operational_asset_b, admin_user):
    """Test cross-tenant asset rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_scan_log_payload(
        scanned_by=admin_user,
        asset=operational_asset_b,
    )
    # 1. Scoped queryset blocks it
    form = AssetScanLogForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetScanLogForm(data=payload, tenant=tenant_a)
    form_wide.fields["asset"].queryset = Asset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["asset"]


def test_mobile_asset_form_scan_log_reject_foreign_scanned_by(tenant_a, admin_b):
    """Test cross-tenant scanned_by user rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_scan_log_payload(
        scanned_by=admin_b,
    )
    # 1. Scoped queryset blocks it
    form = AssetScanLogForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "scanned_by" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetScanLogForm(data=payload, tenant=tenant_a)
    form_wide.fields["scanned_by"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["scanned_by"]


# ==============================================================================
# 5. AssetGeofenceEventForm Tests
# ==============================================================================

def test_mobile_asset_form_geofence_event_valid_create(tenant_a, operational_asset_a, admin_user):
    """Test full valid submission and clean save() of AssetGeofenceEventForm."""
    payload = _mobile_asset_geofence_event_payload(
        asset=operational_asset_a,
        acknowledged_by=admin_user,
    )
    form = AssetGeofenceEventForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.number.startswith("AGEO-")
    assert instance.asset == operational_asset_a
    assert instance.fence_name == "Main Construction Yard Perimeter"
    assert instance.center_latitude == Decimal("37.774000")
    assert instance.center_longitude == Decimal("-122.419000")
    assert instance.radius_meters == 250
    assert instance.recorded_latitude == Decimal("37.776500")
    assert instance.recorded_longitude == Decimal("-122.421500")
    assert instance.distance_from_center_m == 320.5
    assert instance.event_type == "perimeter_exit"
    assert instance.severity == "high"
    assert instance.status == "open_alert"
    assert instance.acknowledged_by == admin_user


def test_mobile_asset_form_geofence_event_valid_minimal(tenant_a, operational_asset_a):
    """Test minimal valid AssetGeofenceEventForm without optional acknowledged_by."""
    payload = _mobile_asset_geofence_event_payload(
        asset=operational_asset_a,
        acknowledged_by=None,
        resolution_notes="",
    )
    form = AssetGeofenceEventForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save()
    assert instance.pk is not None
    assert instance.tenant == tenant_a
    assert instance.acknowledged_by is None
    assert instance.resolution_notes == ""


def test_mobile_asset_form_geofence_event_valid_edit(tenant_a, operational_asset_a, admin_user):
    """Test editing an existing AssetGeofenceEvent instance (resolution workflow) via form."""
    event = AssetGeofenceEvent.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        fence_name="Northern Perimeter Yard",
        center_latitude=Decimal("37.774000"),
        center_longitude=Decimal("-122.419000"),
        radius_meters=150,
        recorded_latitude=Decimal("37.776000"),
        recorded_longitude=Decimal("-122.421000"),
        distance_from_center_m=210.0,
        event_type="perimeter_exit",
        severity="high",
        status="open_alert",
    )

    payload = _mobile_asset_geofence_event_payload(
        asset=operational_asset_a,
        acknowledged_by=admin_user,
        fence_name="Northern Perimeter Yard",
        status="resolved",
        resolution_notes="Authorized equipment repositioning verified with site superintendent.",
    )
    form = AssetGeofenceEventForm(data=payload, instance=event, tenant=tenant_a)
    assert form.is_valid(), form.errors

    saved = form.save()
    assert saved.pk == event.pk
    assert saved.status == "resolved"
    assert saved.acknowledged_by == admin_user
    assert "Authorized equipment repositioning" in saved.resolution_notes


def test_mobile_asset_form_geofence_event_required_fields(tenant_a):
    """Test validation errors when mandatory geofence fields are omitted."""
    form = AssetGeofenceEventForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors
    assert "fence_name" in form.errors
    assert "center_latitude" in form.errors
    assert "center_longitude" in form.errors
    assert "radius_meters" in form.errors
    assert "recorded_latitude" in form.errors
    assert "recorded_longitude" in form.errors


def test_mobile_asset_form_geofence_event_fk_queryset_scoping(
    tenant_a,
    operational_asset_a,
    operational_asset_b,
    admin_user,
    admin_b,
):
    """Test that AssetGeofenceEventForm scopes FK querysets exclusively to tenant_a records."""
    form = AssetGeofenceEventForm(tenant=tenant_a)

    asset_pks = set(form.fields["asset"].queryset.values_list("pk", flat=True))
    assert operational_asset_a.pk in asset_pks
    assert operational_asset_b.pk not in asset_pks

    ack_pks = set(form.fields["acknowledged_by"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in ack_pks
    assert admin_b.pk not in ack_pks


def test_mobile_asset_form_geofence_event_reject_foreign_asset(tenant_a, operational_asset_b):
    """Test cross-tenant asset rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_geofence_event_payload(
        asset=operational_asset_b,
    )
    # 1. Scoped queryset blocks it
    form = AssetGeofenceEventForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetGeofenceEventForm(data=payload, tenant=tenant_a)
    form_wide.fields["asset"].queryset = Asset.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["asset"]


def test_mobile_asset_form_geofence_event_reject_foreign_acknowledged_by(tenant_a, operational_asset_a, admin_b):
    """Test cross-tenant acknowledged_by user rejection (choice validation + widened reject_foreign defense)."""
    payload = _mobile_asset_geofence_event_payload(
        asset=operational_asset_a,
        acknowledged_by=admin_b,
    )
    # 1. Scoped queryset blocks it
    form = AssetGeofenceEventForm(data=payload, tenant=tenant_a)
    assert not form.is_valid()
    assert "acknowledged_by" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = AssetGeofenceEventForm(data=payload, tenant=tenant_a)
    form_wide.fields["acknowledged_by"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["acknowledged_by"]


# ==============================================================================
# 6. Tenant Binding and Initialization Invariants
# ==============================================================================

def test_mobile_asset_form_instance_tenant_binding(tenant_a, operational_asset_a, admin_user):
    """Verify that TenantUniqueMixin binds form instance tenant on init."""
    form = MobileAssetInspectionForm(tenant=tenant_a)
    assert form.instance.tenant == tenant_a

    form_fwo = FieldWorkOrderForm(tenant=tenant_a)
    assert form_fwo.instance.tenant == tenant_a

    form_ascn = AssetScanLogForm(tenant=tenant_a)
    assert form_ascn.instance.tenant == tenant_a

    form_ageo = AssetGeofenceEventForm(tenant=tenant_a)
    assert form_ageo.instance.tenant == tenant_a


def test_mobile_asset_form_unbound_initialization_no_tenant():
    """Verify that forms initialize cleanly without tenant kwarg (e.g. schema inspection)."""
    form_mins = MobileAssetInspectionForm()
    assert "title" in form_mins.fields

    form_fwo = FieldWorkOrderForm()
    assert "title" in form_fwo.fields

    form_ascn = AssetScanLogForm()
    assert "raw_payload" in form_ascn.fields

    form_ageo = AssetGeofenceEventForm()
    assert "fence_name" in form_ageo.fields
