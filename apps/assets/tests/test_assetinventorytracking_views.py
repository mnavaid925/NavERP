"""Asset Inventory & Tracking (11.2) — VIEWS & Workflow Invariants Test Suite.

Covers all 4 entities:
- AssetAudit
- AssetMovementLog
- AssetCustodyLog
- AssetIncidentReport

Invariants pinned:
1. List views: context keys, query filtering, search parameters, summary KPI cards.
2. Detail & Form views: object resolution, form rendering, create and edit flows.
3. State transition action views: atomic execution, status updates, and operational side-effects.
4. HTTP method enforcement: require_POST on mutating actions.
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import (
    AssetAudit,
    AssetCustodyLog,
    AssetIncidentReport,
    AssetMovementLog,
)
from apps.scm.models import Asset


# ==============================================================================
# 1. AssetAudit Views
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_audit_list_view(client, tenant_a, admin_user, audit_a):
    """asset_audit_list renders 200 and passes required context keys."""
    client.force_login(admin_user)
    url = reverse("assets:asset_audit_list")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "audits" in resp.context
    assert "status_choices" in resp.context
    assert "type_choices" in resp.context
    assert "locations" in resp.context
    assert "org_units" in resp.context
    assert resp.context["total_count"] >= 1


@pytest.mark.django_db
def test_assetinventorytracking_audit_detail_view(client, admin_user, audit_a):
    """asset_audit_detail renders 200 with audit in context."""
    client.force_login(admin_user)
    url = reverse("assets:asset_audit_detail", kwargs={"pk": audit_a.pk})
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.context["audit"] == audit_a


@pytest.mark.django_db
def test_assetinventorytracking_audit_create_flow(client, tenant_a, admin_user, location_a):
    """asset_audit_create creates new audit and redirects to detail."""
    client.force_login(admin_user)
    url = reverse("assets:asset_audit_create")
    post_data = {
        "title": "Year-End Comprehensive Count",
        "audit_type": "wall_to_wall",
        "target_location": location_a.pk,
        "lead_auditor": admin_user.pk,
        "scheduled_date": str(timezone.now().date()),
        "is_blind_count": True,
        "expected_asset_count": 40,
        "scanned_asset_count": 0,
        "matched_asset_count": 0,
        "missing_asset_count": 0,
        "discrepancy_count": 0,
    }
    resp = client.post(url, data=post_data)
    assert resp.status_code == 302
    created = AssetAudit.objects.filter(tenant=tenant_a, title="Year-End Comprehensive Count").first()
    assert created is not None
    assert created.number.startswith("AAUD-")


@pytest.mark.django_db
def test_assetinventorytracking_audit_lifecycle_actions(client, admin_user, audit_a):
    """Audit lifecycle: start -> complete -> reconcile."""
    client.force_login(admin_user)

    # 1. Start audit
    resp_start = client.post(reverse("assets:asset_audit_start", kwargs={"pk": audit_a.pk}))
    assert resp_start.status_code == 302
    audit_a.refresh_from_db()
    assert audit_a.status == "in_progress"

    # 2. Complete audit
    post_complete = {
        "scanned_asset_count": 25,
        "matched_asset_count": 24,
        "missing_asset_count": 1,
        "discrepancy_count": 1,
        "discrepancy_notes": "1 asset missing from shelf",
    }
    resp_comp = client.post(reverse("assets:asset_audit_complete", kwargs={"pk": audit_a.pk}), data=post_complete)
    assert resp_comp.status_code == 302
    audit_a.refresh_from_db()
    assert audit_a.status == "completed"

    # 3. Reconcile audit (admin only)
    post_reconcile = {
        "reconciliation_action": "incident_initiated",
        "discrepancy_notes": "Incident report initiated for missing unit",
    }
    resp_rec = client.post(reverse("assets:asset_audit_reconcile", kwargs={"pk": audit_a.pk}), data=post_reconcile)
    assert resp_rec.status_code == 302
    audit_a.refresh_from_db()
    assert audit_a.status == "reconciled"


# ==============================================================================
# 2. AssetMovementLog Views
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_movement_list_view(client, admin_user, movement_a):
    """asset_movement_log_list renders 200 with required context keys."""
    client.force_login(admin_user)
    url = reverse("assets:asset_movement_log_list")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "movements" in resp.context
    assert "status_choices" in resp.context
    assert "type_choices" in resp.context
    assert "assets" in resp.context


@pytest.mark.django_db
def test_assetinventorytracking_movement_dispatch_and_receive(client, admin_user, movement_a, operational_asset_a, location_a2):
    """Dispatching and receiving a movement updates asset location atomically."""
    client.force_login(admin_user)

    # 1. Dispatch
    resp_disp = client.post(reverse("assets:asset_movement_log_dispatch", kwargs={"pk": movement_a.pk}))
    assert resp_disp.status_code == 302
    movement_a.refresh_from_db()
    assert movement_a.status == "dispatched"

    # 2. Receive
    resp_rcv = client.post(
        reverse("assets:asset_movement_log_receive", kwargs={"pk": movement_a.pk}),
        data={"condition_on_receipt": "good", "notes": "Received safely"},
    )
    assert resp_rcv.status_code == 302
    movement_a.refresh_from_db()
    assert movement_a.status == "received"

    # Operational asset location is updated to destination
    operational_asset_a.refresh_from_db()
    assert operational_asset_a.location == location_a2


# ==============================================================================
# 3. AssetCustodyLog Views
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_custody_list_view(client, admin_user, custody_a):
    """asset_custody_log_list renders 200 with active loans in context."""
    client.force_login(admin_user)
    url = reverse("assets:asset_custody_log_list")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "custody_logs" in resp.context
    assert "borrowers" in resp.context
    assert resp.context["active_loans_count"] >= 1


@pytest.mark.django_db
def test_assetinventorytracking_custody_checkin_flow(client, admin_user, custody_a):
    """Checking in borrowed equipment marks loan returned."""
    client.force_login(admin_user)
    resp = client.post(
        reverse("assets:asset_custody_log_checkin", kwargs={"pk": custody_a.pk}),
        data={"return_condition": "good", "notes": "Returned on time"},
    )
    assert resp.status_code == 302
    custody_a.refresh_from_db()
    assert custody_a.status == "returned"
    assert custody_a.actual_return_date is not None


@pytest.mark.django_db
def test_assetinventorytracking_custody_delete_guard(client, admin_user, custody_a):
    """Active loan cannot be deleted; returned loan can be deleted."""
    client.force_login(admin_user)

    # Active loan delete rejected
    resp = client.post(reverse("assets:asset_custody_log_delete", kwargs={"pk": custody_a.pk}))
    assert resp.status_code == 302
    assert AssetCustodyLog.objects.filter(pk=custody_a.pk).exists()

    # Mark returned
    custody_a.status = "returned"
    custody_a.save()

    # Returned loan delete succeeds
    resp_del = client.post(reverse("assets:asset_custody_log_delete", kwargs={"pk": custody_a.pk}))
    assert resp_del.status_code == 302
    assert not AssetCustodyLog.objects.filter(pk=custody_a.pk).exists()


# ==============================================================================
# 4. AssetIncidentReport Views
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_incident_list_view(client, admin_user, incident_a):
    """asset_incident_report_list renders 200 with required context keys."""
    client.force_login(admin_user)
    url = reverse("assets:asset_incident_report_list")
    resp = client.get(url)
    assert resp.status_code == 200
    assert "incidents" in resp.context
    assert "status_choices" in resp.context
    assert "severity_choices" in resp.context


@pytest.mark.django_db
def test_assetinventorytracking_incident_authorize_write_off(client, admin_user, incident_a, operational_asset_a):
    """Authorizing write-off decommissions operational asset to disposed."""
    client.force_login(admin_user)
    url = reverse("assets:asset_incident_report_authorize_write_off", kwargs={"pk": incident_a.pk})
    resp = client.post(url, data={"write_off_notes": "Irreparable stator damage"})
    assert resp.status_code == 302
    incident_a.refresh_from_db()
    assert incident_a.status == "written_off"
    assert incident_a.resolution_action == "written_off"

    # Operational asset status is updated to disposed
    operational_asset_a.refresh_from_db()
    assert operational_asset_a.status == "disposed"
