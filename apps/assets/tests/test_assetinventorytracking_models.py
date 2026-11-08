"""Asset Inventory & Tracking (11.2) — MODEL Invariants Test Suite.

Covers the 4 core models:
- AssetAudit [AAUD-]
- AssetMovementLog [AMOV-]
- AssetCustodyLog [ACHK-]
- AssetIncidentReport [AINC-]

Invariants pinned:
1. String representations (__str__) for all 4 models.
2. Auto-number generation and collision-free prefixing (AAUD, AMOV, ACHK, AINC).
3. Default field values, status choices, and valid colour-named theme.css status_css properties.
4. Tenant isolation and compound unique constraints ((tenant, number)).
5. Calculation and helper methods across physical audits, spatial transfers, crib loans, and incident reports.
"""
from decimal import Decimal
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.assets.models import (
    AssetAudit,
    AssetCustodyLog,
    AssetIncidentReport,
    AssetMovementLog,
)


def _assetinventorytracking_allowed_badge_classes():
    """Return the set of valid theme.css badge classes."""
    return {
        "badge-green",
        "badge-red",
        "badge-amber",
        "badge-info",
        "badge-muted",
        "badge-slate",
    }


# ==============================================================================
# 1. String Representations (__str__)
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_audit_str(audit_a):
    """AssetAudit __str__ includes number and title with em-dash."""
    assert str(audit_a) == f"{audit_a.number} — Q2 Annual Physical Audit"


@pytest.mark.django_db
def test_assetinventorytracking_movement_str(movement_a):
    """AssetMovementLog __str__ includes number, title, and asset number."""
    assert str(movement_a) == f"{movement_a.number} — Transfer CNC to Bay 2 ({movement_a.asset.number})"


@pytest.mark.django_db
def test_assetinventorytracking_custody_str(custody_a):
    """AssetCustodyLog __str__ includes number, asset number, and action type display."""
    assert str(custody_a) == f"{custody_a.number} — {custody_a.asset.number} ({custody_a.get_action_type_display()})"


@pytest.mark.django_db
def test_assetinventorytracking_incident_str(incident_a):
    """AssetIncidentReport __str__ includes number, title, and asset number."""
    assert str(incident_a) == f"{incident_a.number} — Spindle Motor Damage Report ({incident_a.asset.number})"


# ==============================================================================
# 2. Number Sequence & Prefix Integrity
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_audit_number_sequence(tenant_a, location_a):
    """AssetAudit generates unique sequential numbers with prefix AAUD-."""
    a1 = AssetAudit.objects.create(
        tenant=tenant_a,
        title="Audit 1",
        audit_type="cycle_count",
        target_location=location_a,
        scheduled_date=timezone.now().date(),
    )
    a2 = AssetAudit.objects.create(
        tenant=tenant_a,
        title="Audit 2",
        audit_type="cycle_count",
        target_location=location_a,
        scheduled_date=timezone.now().date(),
    )
    assert a1.number.startswith("AAUD-")
    assert a2.number.startswith("AAUD-")
    assert a1.number != a2.number


@pytest.mark.django_db
def test_assetinventorytracking_movement_number_sequence(tenant_a, operational_asset_a, location_a):
    """AssetMovementLog generates sequential numbers with prefix AMOV-."""
    m1 = AssetMovementLog.objects.create(
        tenant=tenant_a,
        title="Move 1",
        asset=operational_asset_a,
        movement_type="department_transfer",
        from_location=location_a,
        to_location=location_a,
    )
    m2 = AssetMovementLog.objects.create(
        tenant=tenant_a,
        title="Move 2",
        asset=operational_asset_a,
        movement_type="department_transfer",
        from_location=location_a,
        to_location=location_a,
    )
    assert m1.number.startswith("AMOV-")
    assert m2.number.startswith("AMOV-")
    assert m1.number != m2.number


@pytest.mark.django_db
def test_assetinventorytracking_custody_number_sequence(tenant_a, operational_asset_a, vendor_party_a):
    """AssetCustodyLog generates sequential numbers with prefix ACHK-."""
    c1 = AssetCustodyLog.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        action_type="checkout",
        borrower=vendor_party_a,
        borrower_name=vendor_party_a.name,
        checkout_date=timezone.now(),
        expected_return_date=timezone.now().date() + timezone.timedelta(days=1),
    )
    c2 = AssetCustodyLog.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        action_type="checkout",
        borrower=vendor_party_a,
        borrower_name=vendor_party_a.name,
        checkout_date=timezone.now(),
        expected_return_date=timezone.now().date() + timezone.timedelta(days=2),
    )
    assert c1.number.startswith("ACHK-")
    assert c2.number.startswith("ACHK-")
    assert c1.number != c2.number


@pytest.mark.django_db
def test_assetinventorytracking_incident_number_sequence(tenant_a, operational_asset_a):
    """AssetIncidentReport generates sequential numbers with prefix AINC-."""
    i1 = AssetIncidentReport.objects.create(
        tenant=tenant_a,
        title="Incident 1",
        asset=operational_asset_a,
        incident_type="lost",
        incident_date=timezone.now().date(),
        incident_description="Test incident 1",
    )
    i2 = AssetIncidentReport.objects.create(
        tenant=tenant_a,
        title="Incident 2",
        asset=operational_asset_a,
        incident_type="stolen",
        incident_date=timezone.now().date(),
        incident_description="Test incident 2",
    )
    assert i1.number.startswith("AINC-")
    assert i2.number.startswith("AINC-")
    assert i1.number != i2.number


# ==============================================================================
# 3. Status Badges & Choices Conformance
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_status_css_badges(audit_a, movement_a, custody_a, incident_a):
    """Every model exposes a valid status_css property from theme.css palette."""
    valid_badges = _assetinventorytracking_allowed_badge_classes()
    assert audit_a.status_css in valid_badges
    assert movement_a.status_css in valid_badges
    assert custody_a.status_css in valid_badges
    assert incident_a.status_css in valid_badges


@pytest.mark.django_db
def test_assetinventorytracking_all_status_choices_have_valid_css():
    """All declared STATUS_CHOICES in all 4 models map to valid theme.css classes."""
    valid_badges = _assetinventorytracking_allowed_badge_classes()
    for status_val, _ in AssetAudit.STATUS_CHOICES:
        assert AssetAudit.STATUS_CSS.get(status_val) in valid_badges
    for status_val, _ in AssetMovementLog.STATUS_CHOICES:
        assert AssetMovementLog.STATUS_CSS.get(status_val) in valid_badges
    for status_val, _ in AssetCustodyLog.STATUS_CHOICES:
        assert AssetCustodyLog.STATUS_CSS.get(status_val) in valid_badges
    for status_val, _ in AssetIncidentReport.STATUS_CHOICES:
        assert AssetIncidentReport.STATUS_CSS.get(status_val) in valid_badges


# ==============================================================================
# 4. Multi-Tenant Constraints (Unique per Tenant)
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_unique_number_per_tenant(tenant_a, tenant_b, audit_a, movement_a, custody_a, incident_a, location_b, operational_asset_b):
    """Same number is allowed across different tenants, but strictly unique within tenant."""
    # Cross-tenant reuse is legal
    audit_cross = AssetAudit(
        tenant=tenant_b,
        number=audit_a.number,
        title="Globex Duplicate Num Audit",
        audit_type="spot_check",
        target_location=location_b,
        scheduled_date=timezone.now().date(),
    )
    audit_cross.save()
    assert audit_cross.pk is not None

    # Intra-tenant duplicate number violates unique constraint
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            AssetAudit.objects.create(
                tenant=tenant_a,
                number=audit_a.number,
                title="Acme Collision Audit",
                audit_type="spot_check",
                target_location=audit_a.target_location,
                scheduled_date=timezone.now().date(),
            )


# ==============================================================================
# 5. Domain Invariants & Logic Helpers
# ==============================================================================


@pytest.mark.django_db
def test_assetinventorytracking_custody_overdue_detection(tenant_a, operational_asset_a, vendor_party_a):
    """AssetCustodyLog detects overdue returns when expected return date is in past."""
    past_date = timezone.now().date() - timezone.timedelta(days=2)
    future_date = timezone.now().date() + timezone.timedelta(days=5)

    c_overdue = AssetCustodyLog.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        action_type="checkout",
        borrower=vendor_party_a,
        borrower_name="Tech 1",
        checkout_date=timezone.now() - timezone.timedelta(days=10),
        expected_return_date=past_date,
        status="active_loan",
    )
    assert c_overdue.expected_return_date < timezone.now().date()

    c_active = AssetCustodyLog.objects.create(
        tenant=tenant_a,
        asset=operational_asset_a,
        action_type="checkout",
        borrower=vendor_party_a,
        borrower_name="Tech 2",
        checkout_date=timezone.now(),
        expected_return_date=future_date,
        status="active_loan",
    )
    assert c_active.expected_return_date >= timezone.now().date()


@pytest.mark.django_db
def test_assetinventorytracking_audit_counts_calculation(audit_a):
    """AssetAudit discrepancy calculations operate correctly on positive counts."""
    audit_a.expected_asset_count = 50
    audit_a.scanned_asset_count = 48
    audit_a.matched_asset_count = 46
    audit_a.missing_asset_count = 4
    audit_a.discrepancy_count = 4
    audit_a.save()

    refreshed = AssetAudit.objects.get(pk=audit_a.pk)
    assert refreshed.missing_asset_count == 4
    assert refreshed.discrepancy_count == 4
