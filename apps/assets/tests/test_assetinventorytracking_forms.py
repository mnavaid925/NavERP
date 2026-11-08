"""Asset Inventory & Tracking (11.2) — FORMS Invariants Test Suite.

Covers the 4 model forms:
- AssetAuditForm
- AssetMovementLogForm
- AssetCustodyLogForm
- AssetIncidentReportForm

Invariants pinned:
1. Field presence & required validation.
2. System & workflow field exclusion (tenant, number, status, timestamps, privileged actions).
3. Tenant-scoped dropdown querysets.
4. Cross-tenant FK rejection via reject_foreign / validation.
"""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.assets.forms import (
    AssetAuditForm,
    AssetCustodyLogForm,
    AssetIncidentReportForm,
    AssetMovementLogForm,
)


# ==============================================================================
# 1. AssetAuditForm
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_audit_form_valid(tenant_a, location_a, org_unit_a, admin_user):
    """AssetAuditForm validates clean data scoped to tenant."""
    form_data = {
        "title": "Quarterly Floor Check",
        "audit_type": "cycle_count",
        "target_location": location_a.pk,
        "target_org_unit": org_unit_a.pk,
        "lead_auditor": admin_user.pk,
        "scheduled_date": str(timezone.now().date()),
        "is_blind_count": True,
        "expected_asset_count": 20,
        "scanned_asset_count": 0,
        "matched_asset_count": 0,
        "missing_asset_count": 0,
        "discrepancy_count": 0,
    }
    form = AssetAuditForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetinventorytracking_audit_form_excludes_system_fields():
    """AssetAuditForm strictly excludes tenant, number, status, and reconciliation_action."""
    form = AssetAuditForm()
    excluded = ["tenant", "number", "status", "reconciliation_action", "reconciled_by", "reconciled_at"]
    for field_name in excluded:
        assert field_name not in form.fields


@pytest.mark.django_db
def test_assetinventorytracking_audit_form_rejects_cross_tenant_location(tenant_a, location_b, admin_user):
    """AssetAuditForm rejects location belonging to another tenant."""
    form_data = {
        "title": "Cross Tenant Audit Attempt",
        "audit_type": "wall_to_wall",
        "target_location": location_b.pk,
        "lead_auditor": admin_user.pk,
        "scheduled_date": str(timezone.now().date()),
        "expected_asset_count": 10,
        "scanned_asset_count": 0,
        "matched_asset_count": 0,
        "missing_asset_count": 0,
        "discrepancy_count": 0,
    }
    form = AssetAuditForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_location" in form.errors


# ==============================================================================
# 2. AssetMovementLogForm
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_movement_form_valid(tenant_a, operational_asset_a, location_a, location_a2, vendor_party_a):
    """AssetMovementLogForm validates clean relocation request."""
    form_data = {
        "title": "Move CNC to Assembly",
        "asset": operational_asset_a.pk,
        "movement_type": "inter_facility_transfer",
        "from_location": location_a.pk,
        "to_location": location_a2.pk,
        "from_custodian": vendor_party_a.pk,
        "carrier_name": "Rapid Dispatch",
        "reason": "Assembly line setup",
    }
    form = AssetMovementLogForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetinventorytracking_movement_form_excludes_receipt_and_system_fields():
    """AssetMovementLogForm excludes tenant, number, status, condition_on_receipt, dispatch/receipt stamps."""
    form = AssetMovementLogForm()
    excluded = [
        "tenant",
        "number",
        "status",
        "condition_on_receipt",
        "dispatch_date",
        "dispatched_by",
        "received_date",
        "received_by",
    ]
    for field_name in excluded:
        assert field_name not in form.fields


@pytest.mark.django_db
def test_assetinventorytracking_movement_form_rejects_cross_tenant_asset(tenant_a, operational_asset_b, location_a):
    """AssetMovementLogForm rejects foreign tenant asset."""
    form_data = {
        "title": "Illegal Cross-Tenant Move",
        "asset": operational_asset_b.pk,
        "movement_type": "department_transfer",
        "from_location": location_a.pk,
        "to_location": location_a.pk,
    }
    form = AssetMovementLogForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors


# ==============================================================================
# 3. AssetCustodyLogForm
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_custody_form_valid(tenant_a, operational_asset_a, vendor_party_a, admin_user):
    """AssetCustodyLogForm validates equipment checkout."""
    form_data = {
        "asset": operational_asset_a.pk,
        "action_type": "checkout",
        "borrower": vendor_party_a.pk,
        "borrower_name": "Field Technician Alpha",
        "crib_attendant": admin_user.pk,
        "purpose": "Emergency repair on site",
        "checkout_date": str(timezone.now()),
        "expected_return_date": str(timezone.now().date() + timezone.timedelta(days=3)),
        "checkout_condition": "excellent",
        "borrower_signature_acknowledged": True,
    }
    form = AssetCustodyLogForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetinventorytracking_custody_form_excludes_return_and_system_fields():
    """AssetCustodyLogForm excludes tenant, number, status, actual_return_date, return_condition."""
    form = AssetCustodyLogForm()
    excluded = ["tenant", "number", "status", "actual_return_date", "return_condition"]
    for field_name in excluded:
        assert field_name not in form.fields


@pytest.mark.django_db
def test_assetinventorytracking_custody_form_rejects_cross_tenant_borrower(tenant_a, operational_asset_a, vendor_party_b):
    """AssetCustodyLogForm rejects borrower belonging to another tenant."""
    form_data = {
        "asset": operational_asset_a.pk,
        "action_type": "checkout",
        "borrower": vendor_party_b.pk,
        "expected_return_date": str(timezone.now().date() + timezone.timedelta(days=3)),
    }
    form = AssetCustodyLogForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "borrower" in form.errors


# ==============================================================================
# 4. AssetIncidentReportForm
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_incident_form_valid(tenant_a, operational_asset_a, location_a, admin_user):
    """AssetIncidentReportForm validates incident intake without workflow fields."""
    form_data = {
        "title": "Spindle Vibration Alarm Incident",
        "asset": operational_asset_a.pk,
        "incident_type": "damaged_beyond_repair",
        "severity": "critical",
        "incident_date": str(timezone.now().date()),
        "last_known_location": location_a.pk,
        "location_details": "Cell 4",
        "investigator": admin_user.pk,
        "estimated_loss_value": "4500.00",
        "insurance_claimed_amount": "0.00",
        "insurance_settled_amount": "0.00",
        "incident_description": "Excessive bearing runout caused severe chatter and cutter failure.",
    }
    form = AssetIncidentReportForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_assetinventorytracking_incident_form_excludes_privileged_write_off_fields():
    """AssetIncidentReportForm strictly excludes tenant, number, status, resolution_action, write_off_*."""
    form = AssetIncidentReportForm()
    excluded = [
        "tenant",
        "number",
        "status",
        "reported_by",
        "resolution_action",
        "write_off_authorized_by",
        "write_off_date",
        "write_off_notes",
    ]
    for field_name in excluded:
        assert field_name not in form.fields


@pytest.mark.django_db
def test_assetinventorytracking_incident_form_rejects_cross_tenant_asset(tenant_a, operational_asset_b):
    """AssetIncidentReportForm rejects asset belonging to foreign tenant."""
    form_data = {
        "title": "Cross Tenant Loss Report",
        "asset": operational_asset_b.pk,
        "incident_type": "lost",
        "severity": "high",
        "incident_date": str(timezone.now().date()),
        "incident_description": "Attempt to report asset of another tenant",
    }
    form = AssetIncidentReportForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "asset" in form.errors
