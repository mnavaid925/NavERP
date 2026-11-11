"""
Unit tests for Sub-module 11.13: Mobile Asset Management Models.
Covers MobileAssetInspection, FieldWorkOrder, AssetScanLog, AssetGeofenceEvent.
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets.models import (
    MobileAssetInspection,
    FieldWorkOrder,
    AssetScanLog,
    AssetGeofenceEvent,
)

VALID_BADGE_CLASSES = {
    "badge-slate",
    "badge-info",
    "badge-amber",
    "badge-green",
    "badge-red",
    "badge-muted",
}


def _mobile_asset_create_inspection(tenant, asset, inspector, title="Test Inspection", **kwargs):
    """Module-level helper to instantiate MobileAssetInspection with defaults."""
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
    """Module-level helper to instantiate FieldWorkOrder with defaults."""
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
    """Module-level helper to instantiate AssetScanLog with defaults."""
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
    """Module-level helper to instantiate AssetGeofenceEvent with defaults."""
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


@pytest.mark.django_db
class TestMobileAssetModels:
    """Model test suite for Sub-module 11.13 Mobile Asset Management."""

    # -------------------------------------------------------------------------
    # MobileAssetInspection Tests
    # -------------------------------------------------------------------------

    def test_mobile_asset_model_inspection_number_and_str(self, mobile_inspection_a):
        """Verifies MobileAssetInspection auto-numbering with MINS prefix and __str__."""
        assert mobile_inspection_a.pk is not None
        assert mobile_inspection_a.number.startswith("MINS")
        expected_str = f"{mobile_inspection_a.number} - {mobile_inspection_a.title} ({mobile_inspection_a.get_overall_result_display()})"
        assert str(mobile_inspection_a) == expected_str

    def test_mobile_asset_model_inspection_defaults_and_choices(self, tenant_a, operational_asset_a, admin_user):
        """Verifies default values and choices on MobileAssetInspection."""
        inspection = MobileAssetInspection.objects.create(
            tenant=tenant_a,
            asset=operational_asset_a,
            inspector=admin_user,
            title="Default Walkaround Audit",
        )
        assert inspection.inspection_type == "routine_pm"
        assert inspection.overall_result == "pass"
        assert inspection.condition_rating == 5
        assert inspection.status == "submitted"
        assert inspection.corrective_action_required is False
        assert inspection.is_offline_captured is False
        assert inspection.checklist_summary == ""
        assert inspection.findings_summary == ""

        # Test valid choice options
        valid_results = [c[0] for c in MobileAssetInspection.OVERALL_RESULT_CHOICES]
        assert "pass" in valid_results
        assert "conditional_pass" in valid_results
        assert "fail" in valid_results
        assert "critical_hazard" in valid_results

        valid_types = [c[0] for c in MobileAssetInspection.INSPECTION_TYPE_CHOICES]
        assert "safety_audit" in valid_types
        assert "pre_trip" in valid_types
        assert "condition_assessment" in valid_types
        assert "routine_pm" in valid_types
        assert "breakdown_triage" in valid_types

    def test_mobile_asset_model_inspection_badge_classes(self, mobile_inspection_a):
        """Verifies status, result, and type badge CSS property resolution."""
        # Status badges
        for status_val, expected_css in MobileAssetInspection.STATUS_CSS.items():
            mobile_inspection_a.status = status_val
            assert mobile_inspection_a.status_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        mobile_inspection_a.status = "unknown_status"
        assert mobile_inspection_a.status_badge_class == "badge-slate"

        # Overall result badges
        for res_val, expected_css in MobileAssetInspection.OVERALL_RESULT_CSS.items():
            mobile_inspection_a.overall_result = res_val
            assert mobile_inspection_a.result_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        mobile_inspection_a.overall_result = "unknown_result"
        assert mobile_inspection_a.result_badge_class == "badge-slate"

        # Inspection type badges
        for type_val, expected_css in MobileAssetInspection.INSPECTION_TYPE_CSS.items():
            mobile_inspection_a.inspection_type = type_val
            assert mobile_inspection_a.type_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        mobile_inspection_a.inspection_type = "unknown_type"
        assert mobile_inspection_a.type_badge_class == "badge-slate"

    def test_mobile_asset_model_inspection_ordering(self, tenant_a, operational_asset_a, admin_user):
        """Verifies default ordering [-inspection_date, -id]."""
        now = timezone.now()
        insp1 = _mobile_asset_create_inspection(
            tenant_a, operational_asset_a, admin_user,
            title="Earlier Inspection",
            inspection_date=now - timezone.timedelta(days=2),
        )
        insp2 = _mobile_asset_create_inspection(
            tenant_a, operational_asset_a, admin_user,
            title="Later Inspection",
            inspection_date=now,
        )
        inspections = list(MobileAssetInspection.objects.filter(tenant=tenant_a))
        # Newest inspection_date must come first
        assert inspections[0].pk == insp2.pk
        assert inspections[1].pk == insp1.pk

    # -------------------------------------------------------------------------
    # FieldWorkOrder Tests
    # -------------------------------------------------------------------------

    def test_mobile_asset_model_field_work_order_number_and_str(self, field_work_order_a):
        """Verifies FieldWorkOrder auto-numbering with MFWO prefix and __str__."""
        assert field_work_order_a.pk is not None
        assert field_work_order_a.number.startswith("MFWO")
        expected_str = f"{field_work_order_a.number} - {field_work_order_a.title} ({field_work_order_a.get_status_display()})"
        assert str(field_work_order_a) == expected_str

    def test_mobile_asset_model_field_work_order_defaults_and_choices(self, tenant_a, operational_asset_a, admin_user):
        """Verifies default values and choices on FieldWorkOrder."""
        fwo = FieldWorkOrder.objects.create(
            tenant=tenant_a,
            asset=operational_asset_a,
            assigned_technician=admin_user,
            title="Field Inspection Job",
        )
        assert fwo.work_order_type == "scheduled_pm"
        assert fwo.priority == "medium"
        assert fwo.status == "dispatched"
        assert fwo.labor_wrench_minutes == 0
        assert fwo.safety_lockout_confirmed is False
        assert fwo.estimated_parts_cost == Decimal("0.00")
        assert fwo.is_offline_captured is False

        valid_types = [c[0] for c in FieldWorkOrder.WORK_ORDER_TYPE_CHOICES]
        assert "emergency_repair" in valid_types
        assert "scheduled_pm" in valid_types
        assert "inspection_followup" in valid_types
        assert "calibration" in valid_types
        assert "installation" in valid_types

        valid_priorities = [c[0] for c in FieldWorkOrder.PRIORITY_CHOICES]
        assert "low" in valid_priorities
        assert "medium" in valid_priorities
        assert "high" in valid_priorities
        assert "urgent" in valid_priorities

        valid_statuses = [c[0] for c in FieldWorkOrder.STATUS_CHOICES]
        assert "dispatched" in valid_statuses
        assert "en_route" in valid_statuses
        assert "on_site" in valid_statuses
        assert "in_progress" in valid_statuses
        assert "paused" in valid_statuses
        assert "completed" in valid_statuses
        assert "cancelled" in valid_statuses

    def test_mobile_asset_model_field_work_order_badge_classes(self, field_work_order_a):
        """Verifies status, priority, and type badge CSS property resolution."""
        # Status badges
        for status_val, expected_css in FieldWorkOrder.STATUS_CSS.items():
            field_work_order_a.status = status_val
            assert field_work_order_a.status_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        field_work_order_a.status = "unknown_status"
        assert field_work_order_a.status_badge_class == "badge-slate"

        # Priority badges
        for prio_val, expected_css in FieldWorkOrder.PRIORITY_CSS.items():
            field_work_order_a.priority = prio_val
            assert field_work_order_a.priority_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        field_work_order_a.priority = "unknown_priority"
        assert field_work_order_a.priority_badge_class == "badge-slate"

        # Work order type badges
        for type_val, expected_css in FieldWorkOrder.WORK_ORDER_TYPE_CSS.items():
            field_work_order_a.work_order_type = type_val
            assert field_work_order_a.type_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        field_work_order_a.work_order_type = "unknown_type"
        assert field_work_order_a.type_badge_class == "badge-slate"

    def test_mobile_asset_model_field_work_order_ordering(self, tenant_a, operational_asset_a, admin_user):
        """Verifies default ordering [-scheduled_start, -id]."""
        now = timezone.now()
        fwo1 = _mobile_asset_create_work_order(
            tenant_a, operational_asset_a, admin_user,
            title="Earlier Dispatch",
            scheduled_start=now - timezone.timedelta(hours=5),
        )
        fwo2 = _mobile_asset_create_work_order(
            tenant_a, operational_asset_a, admin_user,
            title="Later Dispatch",
            scheduled_start=now + timezone.timedelta(hours=2),
        )
        orders = list(FieldWorkOrder.objects.filter(tenant=tenant_a))
        # Newest scheduled_start first
        assert orders[0].pk == fwo2.pk
        assert orders[1].pk == fwo1.pk

    # -------------------------------------------------------------------------
    # AssetScanLog Tests
    # -------------------------------------------------------------------------

    def test_mobile_asset_model_scan_log_number_and_str(self, asset_scan_log_a):
        """Verifies AssetScanLog auto-numbering with ASCN prefix and __str__."""
        assert asset_scan_log_a.pk is not None
        assert asset_scan_log_a.number.startswith("ASCN")
        expected_str = f"{asset_scan_log_a.number} - {asset_scan_log_a.raw_payload} ({asset_scan_log_a.get_match_status_display()})"
        assert str(asset_scan_log_a) == expected_str

    def test_mobile_asset_model_scan_log_defaults_and_choices(self, tenant_a, operational_asset_a, admin_user):
        """Verifies default values and choices on AssetScanLog."""
        scan = AssetScanLog.objects.create(
            tenant=tenant_a,
            asset=operational_asset_a,
            scanned_by=admin_user,
            raw_payload="TAG-RFID-990011",
        )
        assert scan.scan_context == "field_audit"
        assert scan.scan_method == "camera_qr"
        assert scan.match_status == "matched"
        assert scan.is_offline_captured is False

        valid_contexts = [c[0] for c in AssetScanLog.SCAN_CONTEXT_CHOICES]
        assert "field_audit" in valid_contexts
        assert "checkout_verification" in valid_contexts
        assert "work_order_init" in valid_contexts
        assert "receiving" in valid_contexts
        assert "location_reconciliation" in valid_contexts

        valid_methods = [c[0] for c in AssetScanLog.SCAN_METHOD_CHOICES]
        assert "camera_barcode" in valid_methods
        assert "camera_qr" in valid_methods
        assert "bluetooth_rfid" in valid_methods
        assert "handheld_laser" in valid_methods
        assert "manual_entry" in valid_methods

        valid_matches = [c[0] for c in AssetScanLog.MATCH_STATUS_CHOICES]
        assert "matched" in valid_matches
        assert "not_found" in valid_matches
        assert "mismatched" in valid_matches
        assert "unassigned" in valid_matches

    def test_mobile_asset_model_scan_log_badge_classes(self, asset_scan_log_a):
        """Verifies match_status, scan_method, and scan_context badge CSS resolution."""
        # Match status badges
        for status_val, expected_css in AssetScanLog.MATCH_STATUS_CSS.items():
            asset_scan_log_a.match_status = status_val
            assert asset_scan_log_a.match_status_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_scan_log_a.match_status = "unknown_status"
        assert asset_scan_log_a.match_status_badge_class == "badge-slate"

        # Scan method badges
        for method_val, expected_css in AssetScanLog.SCAN_METHOD_CSS.items():
            asset_scan_log_a.scan_method = method_val
            assert asset_scan_log_a.scan_method_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_scan_log_a.scan_method = "unknown_method"
        assert asset_scan_log_a.scan_method_badge_class == "badge-slate"

        # Scan context badges
        for context_val, expected_css in AssetScanLog.SCAN_CONTEXT_CSS.items():
            asset_scan_log_a.scan_context = context_val
            assert asset_scan_log_a.scan_context_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_scan_log_a.scan_context = "unknown_context"
        assert asset_scan_log_a.scan_context_badge_class == "badge-slate"

    def test_mobile_asset_model_scan_log_ordering(self, tenant_a, operational_asset_a, admin_user):
        """Verifies default ordering [-scanned_at, -id]."""
        now = timezone.now()
        s1 = _mobile_asset_create_scan_log(
            tenant_a, operational_asset_a, admin_user,
            payload="PAYLOAD-001",
            scanned_at=now - timezone.timedelta(minutes=30),
        )
        s2 = _mobile_asset_create_scan_log(
            tenant_a, operational_asset_a, admin_user,
            payload="PAYLOAD-002",
            scanned_at=now,
        )
        scans = list(AssetScanLog.objects.filter(tenant=tenant_a))
        assert scans[0].pk == s2.pk
        assert scans[1].pk == s1.pk

    # -------------------------------------------------------------------------
    # AssetGeofenceEvent Tests
    # -------------------------------------------------------------------------

    def test_mobile_asset_model_geofence_event_number_and_str(self, asset_geofence_event_a):
        """Verifies AssetGeofenceEvent auto-numbering with AGEO prefix and __str__."""
        assert asset_geofence_event_a.pk is not None
        assert asset_geofence_event_a.number.startswith("AGEO")
        expected_str = f"{asset_geofence_event_a.number} - {asset_geofence_event_a.fence_name} ({asset_geofence_event_a.get_event_type_display()})"
        assert str(asset_geofence_event_a) == expected_str

    def test_mobile_asset_model_geofence_event_defaults_and_choices(self, tenant_a, operational_asset_a):
        """Verifies default values and choices on AssetGeofenceEvent."""
        geo = AssetGeofenceEvent.objects.create(
            tenant=tenant_a,
            asset=operational_asset_a,
            fence_name="Test Depot Perimeter",
            center_latitude=Decimal("37.774900"),
            center_longitude=Decimal("-122.419400"),
            recorded_latitude=Decimal("37.775000"),
            recorded_longitude=Decimal("-122.419500"),
        )
        assert geo.radius_meters == 100
        assert geo.distance_from_center_m == 0.0
        assert geo.event_type == "inside_perimeter"
        assert geo.severity == "info"
        assert geo.status == "open_alert"

        valid_events = [c[0] for c in AssetGeofenceEvent.EVENT_TYPE_CHOICES]
        assert "inside_perimeter" in valid_events
        assert "boundary_warning" in valid_events
        assert "perimeter_exit" in valid_events
        assert "perimeter_entry" in valid_events
        assert "unauthorized_movement" in valid_events

        valid_severities = [c[0] for c in AssetGeofenceEvent.SEVERITY_CHOICES]
        assert "info" in valid_severities
        assert "low" in valid_severities
        assert "medium" in valid_severities
        assert "high" in valid_severities
        assert "critical" in valid_severities

        valid_statuses = [c[0] for c in AssetGeofenceEvent.STATUS_CHOICES]
        assert "open_alert" in valid_statuses
        assert "under_investigation" in valid_statuses
        assert "resolved" in valid_statuses
        assert "false_alarm" in valid_statuses

    def test_mobile_asset_model_geofence_event_badge_classes(self, asset_geofence_event_a):
        """Verifies event_type, severity, and status badge CSS resolution."""
        # Event type badges
        for type_val, expected_css in AssetGeofenceEvent.EVENT_TYPE_CSS.items():
            asset_geofence_event_a.event_type = type_val
            assert asset_geofence_event_a.event_type_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_geofence_event_a.event_type = "unknown_type"
        assert asset_geofence_event_a.event_type_badge_class == "badge-slate"

        # Severity badges
        for sev_val, expected_css in AssetGeofenceEvent.SEVERITY_CSS.items():
            asset_geofence_event_a.severity = sev_val
            assert asset_geofence_event_a.severity_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_geofence_event_a.severity = "unknown_severity"
        assert asset_geofence_event_a.severity_badge_class == "badge-slate"

        # Status badges
        for status_val, expected_css in AssetGeofenceEvent.STATUS_CSS.items():
            asset_geofence_event_a.status = status_val
            assert asset_geofence_event_a.status_badge_class == expected_css
            assert expected_css in VALID_BADGE_CLASSES
        asset_geofence_event_a.status = "unknown_status"
        assert asset_geofence_event_a.status_badge_class == "badge-slate"

    def test_mobile_asset_model_geofence_event_ordering(self, tenant_a, operational_asset_a):
        """Verifies default ordering [-detected_at, -id]."""
        now = timezone.now()
        g1 = _mobile_asset_create_geofence_event(
            tenant_a, operational_asset_a,
            fence_name="Earlier Perimeter Alert",
            detected_at=now - timezone.timedelta(hours=2),
        )
        g2 = _mobile_asset_create_geofence_event(
            tenant_a, operational_asset_a,
            fence_name="Later Perimeter Alert",
            detected_at=now,
        )
        events = list(AssetGeofenceEvent.objects.filter(tenant=tenant_a))
        assert events[0].pk == g2.pk
        assert events[1].pk == g1.pk

    # -------------------------------------------------------------------------
    # Tenant Isolation & Integrity Tests
    # -------------------------------------------------------------------------

    def test_mobile_asset_model_tenant_isolation(
        self,
        tenant_a,
        tenant_b,
        operational_asset_a,
        operational_asset_b,
        admin_user,
        admin_b,
    ):
        """Ensures complete tenant isolation across all four models."""
        # Tenant A records
        insp_a = _mobile_asset_create_inspection(tenant_a, operational_asset_a, admin_user, "A Insp")
        fwo_a = _mobile_asset_create_work_order(tenant_a, operational_asset_a, admin_user, "A Work")
        scan_a = _mobile_asset_create_scan_log(tenant_a, operational_asset_a, admin_user, "A SCAN")
        geo_a = _mobile_asset_create_geofence_event(tenant_a, operational_asset_a, "A Yard")

        # Tenant B records
        insp_b = _mobile_asset_create_inspection(tenant_b, operational_asset_b, admin_b, "B Insp")
        fwo_b = _mobile_asset_create_work_order(tenant_b, operational_asset_b, admin_b, "B Work")
        scan_b = _mobile_asset_create_scan_log(tenant_b, operational_asset_b, admin_b, "B SCAN")
        geo_b = _mobile_asset_create_geofence_event(tenant_b, operational_asset_b, "B Yard")

        # Query Tenant A
        assert insp_a in MobileAssetInspection.objects.filter(tenant=tenant_a)
        assert insp_b not in MobileAssetInspection.objects.filter(tenant=tenant_a)

        assert fwo_a in FieldWorkOrder.objects.filter(tenant=tenant_a)
        assert fwo_b not in FieldWorkOrder.objects.filter(tenant=tenant_a)

        assert scan_a in AssetScanLog.objects.filter(tenant=tenant_a)
        assert scan_b not in AssetScanLog.objects.filter(tenant=tenant_a)

        assert geo_a in AssetGeofenceEvent.objects.filter(tenant=tenant_a)
        assert geo_b not in AssetGeofenceEvent.objects.filter(tenant=tenant_a)

    def test_mobile_asset_model_unique_constraints(self, tenant_a, operational_asset_a, admin_user):
        """Ensures (tenant, number) uniqueness constraint triggers IntegrityError on collision."""
        insp1 = _mobile_asset_create_inspection(tenant_a, operational_asset_a, admin_user, "Insp 1")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                MobileAssetInspection.objects.create(
                    tenant=tenant_a,
                    asset=operational_asset_a,
                    inspector=admin_user,
                    title="Insp Dupe Number",
                    number=insp1.number,
                )

        fwo1 = _mobile_asset_create_work_order(tenant_a, operational_asset_a, admin_user, "FWO 1")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                FieldWorkOrder.objects.create(
                    tenant=tenant_a,
                    asset=operational_asset_a,
                    assigned_technician=admin_user,
                    title="FWO Dupe Number",
                    number=fwo1.number,
                )

        scan1 = _mobile_asset_create_scan_log(tenant_a, operational_asset_a, admin_user, "SCAN 1")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssetScanLog.objects.create(
                    tenant=tenant_a,
                    asset=operational_asset_a,
                    scanned_by=admin_user,
                    raw_payload="SCAN 1",
                    number=scan1.number,
                )

        geo1 = _mobile_asset_create_geofence_event(tenant_a, operational_asset_a, "GEO 1")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssetGeofenceEvent.objects.create(
                    tenant=tenant_a,
                    asset=operational_asset_a,
                    fence_name="GEO Dupe",
                    center_latitude=Decimal("37.774900"),
                    center_longitude=Decimal("-122.419400"),
                    recorded_latitude=Decimal("37.775000"),
                    recorded_longitude=Decimal("-122.419500"),
                    number=geo1.number,
                )

    def test_mobile_asset_model_all_badge_css_validity(self):
        """Verifies all defined badge CSS classes in model dictionaries exist in VALID_BADGE_CLASSES."""
        css_dictionaries = [
            MobileAssetInspection.STATUS_CSS,
            MobileAssetInspection.OVERALL_RESULT_CSS,
            MobileAssetInspection.INSPECTION_TYPE_CSS,
            FieldWorkOrder.STATUS_CSS,
            FieldWorkOrder.PRIORITY_CSS,
            FieldWorkOrder.WORK_ORDER_TYPE_CSS,
            AssetScanLog.MATCH_STATUS_CSS,
            AssetScanLog.SCAN_METHOD_CSS,
            AssetScanLog.SCAN_CONTEXT_CSS,
            AssetGeofenceEvent.EVENT_TYPE_CSS,
            AssetGeofenceEvent.SEVERITY_CSS,
            AssetGeofenceEvent.STATUS_CSS,
        ]
        for css_dict in css_dictionaries:
            for key, badge_cls in css_dict.items():
                assert badge_cls in VALID_BADGE_CLASSES, f"Invalid badge class '{badge_cls}' for key '{key}'"
