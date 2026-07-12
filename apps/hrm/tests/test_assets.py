"""Tests for HRM 3.33 Asset Management sub-module: the central ``Asset`` register
(``ASSET-#####``) + ``AssetMaintenance`` (``ASSETMNT-#####``) + the nullable
``AssetAllocation.asset`` FK that links the pre-existing 3.3 issuance rows to a register row.

Mirrors ``test_analytics_dashboard.py`` / ``test_payroll_reports.py`` — same fixture style
(local ``pytest.fixture``s in this module reusing the shared root/HRM conftest), aggregate/
formula correctness against hand-verified numbers, IDOR, access-control, empty-tenant, and
query-count-ceiling structure.

Covers:
  - ``Asset`` computed depreciation properties (``months_in_service``,
    ``accumulated_depreciation`` straight-line + declining-balance, ``current_book_value``,
    ``is_under_warranty``) — hand-verified against a FROZEN "today" (``timezone.localdate()``
    is monkeypatched since it isn't otherwise injectable).
  - The two save()-time sync points that are the heart of 3.33:
    ``AssetAllocation._sync_linked_asset()`` (issued/returned/damaged/lost -> Asset status +
    current_holder; a no-op for every pre-3.33 ``asset=None`` row) and
    ``AssetMaintenance._sync_asset_status()`` (a "repair" record moves an asset in/out of
    "in_repair"; every other maintenance type never touches Asset.status) — proven to fire from
    a plain model-level ``.save()``, not just the dedicated views.
  - Full CRUD + lifecycle views for both models (list/create/detail/edit/delete + assign/
    return/retire/dispose for Asset; create/complete/delete for AssetMaintenance), including the
    guard rails (delete blocked while assigned/in_repair, retire/dispose status gates, the
    friendly no-500 handling of a garbage/cross-tenant employee pk on assign).
  - ``AssetForm``/``AssetMaintenanceForm``/``AssetAllocationForm`` ``.clean()`` validation.
  - Access control (anonymous redirect, non-admin tenant member 200 — @login_required only),
    multi-tenant IDOR (404 + list isolation + ignored cross-tenant filter pks), CSRF enforcement,
    an empty-tenant smoke test, and N+1 query-count ceilings on both list views.
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ============================================================
# Shared fixtures
# ============================================================

@pytest.fixture
def frozen_today(monkeypatch):
    """Pins ``timezone.localdate()`` (used internally by Asset's depreciation/warranty
    properties, not otherwise injectable) to a fixed date so ``months_in_service`` and friends
    are hand-verifiable regardless of the real wall-clock date the suite runs on."""
    from django.utils import timezone as dj_timezone
    fixed = datetime.date(2026, 7, 13)
    monkeypatch.setattr(dj_timezone, "localdate", lambda: fixed)
    return fixed


@pytest.fixture
def asset_in_stock_a(db, tenant_a):
    """A bare in-stock Asset for tenant_a — no purchase/depreciation fields set."""
    from apps.hrm.models import Asset
    return Asset.objects.create(
        tenant=tenant_a, name="ThinkPad X1", category="laptop", status="in_stock", condition="good",
    )


@pytest.fixture
def asset_b(db, tenant_b):
    """An in-stock Asset belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import Asset
    return Asset.objects.create(
        tenant=tenant_b, name="Globex Laptop", category="laptop", status="in_stock", condition="good",
    )


@pytest.fixture
def assigned_asset_a(db, tenant_a, employee_a):
    """An Asset assigned to employee_a via a REAL issued AssetAllocation (exercises
    ``_sync_linked_asset`` rather than hand-setting status/current_holder)."""
    from apps.hrm.models import Asset, AssetAllocation
    asset = Asset.objects.create(tenant=tenant_a, name="Dell Latitude", category="laptop", status="in_stock")
    AssetAllocation.objects.create(
        tenant=tenant_a, employee=employee_a, asset=asset, asset_name=asset.name,
        asset_category=asset.category, status="issued", issued_at=timezone.now(),
    )
    asset.refresh_from_db()
    return asset


@pytest.fixture
def active_repair_a(db, tenant_a, assigned_asset_a):
    """A scheduled 'repair' AssetMaintenance on assigned_asset_a — CREATING it flips the asset
    to in_repair (still holding employee_a as current_holder) via ``_sync_asset_status()``."""
    from apps.hrm.models import AssetMaintenance
    record = AssetMaintenance.objects.create(
        tenant=tenant_a, asset=assigned_asset_a, maintenance_type="repair", status="scheduled",
        scheduled_date=datetime.date(2026, 7, 1),
    )
    assigned_asset_a.refresh_from_db()
    return record


@pytest.fixture
def retired_asset_a(db, tenant_a):
    """A retired Asset for tenant_a (dispose-action pre-req)."""
    from apps.hrm.models import Asset
    return Asset.objects.create(tenant=tenant_a, name="Old Printer", category="other", status="retired")


@pytest.fixture
def maintenance_a(db, tenant_a, asset_in_stock_a):
    """A scheduled PREVENTIVE maintenance record on asset_in_stock_a (never touches Asset.status)."""
    from apps.hrm.models import AssetMaintenance
    return AssetMaintenance.objects.create(
        tenant=tenant_a, asset=asset_in_stock_a, maintenance_type="preventive", status="scheduled",
        scheduled_date=datetime.date(2026, 7, 1),
    )


@pytest.fixture
def maintenance_b(db, tenant_b, asset_b):
    """A maintenance record belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import AssetMaintenance
    return AssetMaintenance.objects.create(
        tenant=tenant_b, asset=asset_b, maintenance_type="preventive", status="scheduled",
        scheduled_date=datetime.date(2026, 7, 1),
    )


@pytest.fixture
def many_assets_a(db, tenant_a, dept_a, employee_a):
    """12 Assets for tenant_a (location + current_holder set on some) — the N+1 query-count
    fixture for asset_list."""
    from apps.hrm.models import Asset
    assets = []
    for i in range(12):
        assets.append(Asset.objects.create(
            tenant=tenant_a, name=f"Bulk Asset {i}", category="laptop", status="in_stock",
            location=dept_a, condition="good",
        ))
    return assets


@pytest.fixture
def many_maintenance_a(db, tenant_a, many_assets_a):
    """12 maintenance records (one per many_assets_a row) — the N+1 query-count fixture for
    assetmaintenance_list."""
    from apps.hrm.models import AssetMaintenance
    records = []
    for asset in many_assets_a:
        records.append(AssetMaintenance.objects.create(
            tenant=tenant_a, asset=asset, maintenance_type="preventive", status="scheduled",
            scheduled_date=datetime.date(2026, 7, 1), vendor="Acme Repairs",
        ))
    return records


def _asset_payload(**overrides):
    """A minimal-but-complete valid AssetForm POST payload (all required fields filled)."""
    data = {
        "asset_tag": "", "name": "Test Asset", "category": "laptop", "manufacturer": "",
        "model_number": "", "serial_number": "", "status": "in_stock", "condition": "good",
        "purchase_date": "", "purchase_cost": "", "currency": "", "warranty_expiry": "",
        "location": "", "depreciation_method": "none", "useful_life_months": "",
        "salvage_value": "", "notes": "",
    }
    data.update(overrides)
    return data


def _maintenance_payload(asset_pk, **overrides):
    """A minimal-but-complete valid AssetMaintenanceForm POST payload."""
    data = {
        "asset": asset_pk, "maintenance_type": "preventive", "status": "scheduled",
        "scheduled_date": "2026-07-01", "completed_date": "", "vendor": "", "cost": "",
        "contract_start": "", "contract_end": "", "notes": "",
    }
    data.update(overrides)
    return data


def _allocation_payload(employee_pk, **overrides):
    """A minimal-but-complete valid AssetAllocationForm POST payload."""
    data = {
        "program": "", "employee": employee_pk, "asset": "", "asset_name": "Loaner Laptop",
        "asset_category": "other", "serial_number": "", "asset_tag": "", "status": "pending",
        "return_due_date": "", "notes": "",
    }
    data.update(overrides)
    return data


# ============================================================
# 1. Depreciation / warranty properties (hand-verified math)
# ============================================================

class TestMonthsInService:
    def test_no_purchase_date_is_zero(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(tenant=tenant_a, name="No Date", category="other")
        assert obj.months_in_service == 0

    def test_future_purchase_date_is_zero(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="Future", category="other",
            purchase_date=frozen_today + datetime.timedelta(days=10),
        )
        assert obj.months_in_service == 0

    def test_purchase_date_is_today_is_zero(self, frozen_today, tenant_a):
        """`today <= purchase_date` -> 0 (boundary: purchased today counts as 0 months)."""
        from apps.hrm.models import Asset
        obj = Asset.objects.create(tenant=tenant_a, name="Today", category="other", purchase_date=frozen_today)
        assert obj.months_in_service == 0

    def test_exact_five_months_ago_same_day(self, frozen_today, tenant_a):
        """2026-02-13 -> 2026-07-13 is exactly 5 whole months (same day-of-month)."""
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="Five Months", category="other", purchase_date=datetime.date(2026, 2, 13),
        )
        assert obj.months_in_service == 5

    def test_partial_month_rounds_down(self, frozen_today, tenant_a):
        """2026-04-20 -> 2026-07-13: 3 calendar-months apart by number, but the 3rd month only
        completes on 2026-07-20 (after "today" 2026-07-13) -> exactly 2 WHOLE months elapsed."""
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="Partial Month", category="other", purchase_date=datetime.date(2026, 4, 20),
        )
        assert obj.months_in_service == 2

    def test_never_negative(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="Yesterday", category="other",
            purchase_date=frozen_today - datetime.timedelta(days=1),
        )
        assert obj.months_in_service >= 0


class TestAccumulatedDepreciation:
    def test_straight_line_hand_verified(self, frozen_today, tenant_a):
        """cost=1200, salvage=200, useful_life=10mo, purchased 5 months ago:
        (1200-200) * 5 / 10 = 500.00."""
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="Straight Line", category="other",
            purchase_date=datetime.date(2026, 2, 13), purchase_cost=Decimal("1200"),
            salvage_value=Decimal("200"), depreciation_method="straight_line", useful_life_months=10,
        )
        assert obj.months_in_service == 5
        assert obj.accumulated_depreciation == Decimal("500.00")

    def test_straight_line_book_value(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="Straight Line BV", category="other",
            purchase_date=datetime.date(2026, 2, 13), purchase_cost=Decimal("1200"),
            salvage_value=Decimal("200"), depreciation_method="straight_line", useful_life_months=10,
        )
        assert obj.current_book_value == Decimal("700.00")

    def test_declining_balance_hand_verified(self, frozen_today, tenant_a):
        """cost=1200, salvage=100, useful_life=10mo, purchased 5 months ago. Formula: monthly
        rate=0.20/12; book = cost*(1-rate)**months, floored at salvage;
        accumulated = cost - book. Independently computed (decimal, 28-digit precision) =
        96.72 accumulated / 1103.28 book value."""
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="Declining Balance", category="other",
            purchase_date=datetime.date(2026, 2, 13), purchase_cost=Decimal("1200"),
            salvage_value=Decimal("100"), depreciation_method="declining_balance", useful_life_months=10,
        )
        assert obj.accumulated_depreciation == Decimal("96.72")
        assert obj.current_book_value == Decimal("1103.28")

    def test_method_none_guard(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="No Depreciation", category="other",
            purchase_date=datetime.date(2026, 2, 13), purchase_cost=Decimal("1200"),
            salvage_value=Decimal("200"), depreciation_method="none", useful_life_months=10,
        )
        assert obj.accumulated_depreciation == Decimal("0")

    def test_useful_life_none_guard(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="No Useful Life", category="other",
            purchase_date=datetime.date(2026, 2, 13), purchase_cost=Decimal("1200"),
            depreciation_method="straight_line", useful_life_months=None,
        )
        assert obj.accumulated_depreciation == Decimal("0")

    def test_useful_life_zero_guard(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="Zero Useful Life", category="other",
            purchase_date=datetime.date(2026, 2, 13), purchase_cost=Decimal("1200"),
            depreciation_method="straight_line", useful_life_months=0,
        )
        assert obj.accumulated_depreciation == Decimal("0")

    def test_no_purchase_cost_guard(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="No Cost", category="other",
            purchase_date=datetime.date(2026, 2, 13),
            depreciation_method="straight_line", useful_life_months=10,
        )
        assert obj.accumulated_depreciation == Decimal("0")
        assert obj.current_book_value == Decimal("0")

    def test_fully_depreciated_floors_at_salvage(self, frozen_today, tenant_a):
        """cost=1200, salvage=200, useful_life=10mo, purchased 24 months ago (well past useful
        life) -> current_book_value is EXACTLY salvage, never below it."""
        from apps.hrm.models import Asset
        obj = Asset.objects.create(
            tenant=tenant_a, name="Fully Depreciated", category="other",
            purchase_date=datetime.date(2024, 7, 13), purchase_cost=Decimal("1200"),
            salvage_value=Decimal("200"), depreciation_method="straight_line", useful_life_months=10,
        )
        assert obj.months_in_service > 10
        assert obj.current_book_value == Decimal("200.00")
        assert obj.accumulated_depreciation == Decimal("1000.00")


class TestIsUnderWarranty:
    def test_expiry_today_is_true(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(tenant=tenant_a, name="Warranty Today", category="other",
                                   warranty_expiry=frozen_today)
        assert obj.is_under_warranty is True

    def test_expiry_in_future_is_true(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(tenant=tenant_a, name="Warranty Future", category="other",
                                   warranty_expiry=frozen_today + datetime.timedelta(days=1))
        assert obj.is_under_warranty is True

    def test_expiry_in_past_is_false(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(tenant=tenant_a, name="Warranty Past", category="other",
                                   warranty_expiry=frozen_today - datetime.timedelta(days=1))
        assert obj.is_under_warranty is False

    def test_no_expiry_is_false(self, frozen_today, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(tenant=tenant_a, name="No Warranty", category="other")
        assert obj.is_under_warranty is False


# ============================================================
# 2. AssetAllocation.save() sync (_sync_linked_asset)
# ============================================================

class TestAssetAllocationSyncLinkedAsset:
    def test_issued_flips_asset_to_assigned(self, tenant_a, asset_in_stock_a, employee_a):
        from apps.hrm.models import AssetAllocation
        AssetAllocation.objects.create(
            tenant=tenant_a, employee=employee_a, asset=asset_in_stock_a, asset_name=asset_in_stock_a.name,
            asset_category=asset_in_stock_a.category, status="issued",
        )
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "assigned"
        assert asset_in_stock_a.current_holder_id == employee_a.pk

    def test_returned_flips_asset_to_in_stock_no_holder(self, tenant_a, assigned_asset_a, employee_a):
        from apps.hrm.models import AssetAllocation
        allocation = assigned_asset_a.allocations.get(status="issued")
        allocation.status = "returned"
        allocation.save()
        assigned_asset_a.refresh_from_db()
        assert assigned_asset_a.status == "in_stock"
        assert assigned_asset_a.current_holder_id is None

    def test_damaged_flips_asset_to_in_repair_no_holder(self, tenant_a, assigned_asset_a):
        from apps.hrm.models import AssetAllocation
        allocation = assigned_asset_a.allocations.get(status="issued")
        allocation.status = "damaged"
        allocation.save()
        assigned_asset_a.refresh_from_db()
        assert assigned_asset_a.status == "in_repair"
        assert assigned_asset_a.current_holder_id is None

    def test_lost_flips_asset_to_retired_no_holder(self, tenant_a, assigned_asset_a):
        from apps.hrm.models import AssetAllocation
        allocation = assigned_asset_a.allocations.get(status="issued")
        allocation.status = "lost"
        allocation.save()
        assigned_asset_a.refresh_from_db()
        assert assigned_asset_a.status == "retired"
        assert assigned_asset_a.current_holder_id is None

    def test_pending_status_is_noop(self, tenant_a, asset_in_stock_a, employee_a):
        """"pending" isn't in the sync mapping -> the linked Asset is left untouched."""
        from apps.hrm.models import AssetAllocation
        AssetAllocation.objects.create(
            tenant=tenant_a, employee=employee_a, asset=asset_in_stock_a, asset_name=asset_in_stock_a.name,
            asset_category=asset_in_stock_a.category, status="pending",
        )
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"
        assert asset_in_stock_a.current_holder_id is None

    def test_asset_none_never_touches_any_asset(self, tenant_a, employee_a, asset_in_stock_a):
        """CRITICAL regression guard: an allocation with asset=None (every pre-3.33 row) must
        NEVER touch any Asset row — no error, and the unrelated in-stock asset is untouched."""
        from apps.hrm.models import AssetAllocation
        before_status = asset_in_stock_a.status
        before_updated_at = asset_in_stock_a.updated_at
        allocation = AssetAllocation.objects.create(
            tenant=tenant_a, employee=employee_a, asset=None, asset_name="Legacy Laptop",
            asset_category="laptop", status="issued",
        )
        assert allocation.asset_id is None
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == before_status
        assert asset_in_stock_a.updated_at == before_updated_at

    def test_asset_none_survives_every_status_transition(self, tenant_a, employee_a):
        """A pre-3.33 allocation (asset=None) can cycle through every status without ever
        raising — no linked Asset to sync onto."""
        from apps.hrm.models import AssetAllocation
        allocation = AssetAllocation.objects.create(
            tenant=tenant_a, employee=employee_a, asset=None, asset_name="Legacy Phone",
            asset_category="phone", status="pending",
        )
        for status in ["issued", "returned", "damaged", "lost", "pending"]:
            allocation.status = status
            allocation.save()  # must not raise
        assert allocation.asset_id is None

    def test_idempotent_no_duplicate_write_when_unchanged(self, tenant_a, assigned_asset_a):
        """Saving an allocation whose status/asset are unchanged doesn't error or desync."""
        allocation = assigned_asset_a.allocations.get(status="issued")
        allocation.notes = "touched"
        allocation.save()
        assigned_asset_a.refresh_from_db()
        assert assigned_asset_a.status == "assigned"
        assert assigned_asset_a.current_holder_id == allocation.employee_id


# ============================================================
# 3. AssetMaintenance.save() sync (_sync_asset_status)
# ============================================================

class TestAssetMaintenanceSyncAssetStatus:
    def test_repair_scheduled_flips_in_stock_asset_to_in_repair(self, tenant_a, asset_in_stock_a):
        from apps.hrm.models import AssetMaintenance
        AssetMaintenance.objects.create(
            tenant=tenant_a, asset=asset_in_stock_a, maintenance_type="repair", status="scheduled",
            scheduled_date=datetime.date(2026, 7, 1),
        )
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_repair"

    def test_repair_in_progress_flips_assigned_asset_to_in_repair(self, tenant_a, assigned_asset_a):
        from apps.hrm.models import AssetMaintenance
        AssetMaintenance.objects.create(
            tenant=tenant_a, asset=assigned_asset_a, maintenance_type="repair", status="in_progress",
            scheduled_date=datetime.date(2026, 7, 1),
        )
        assigned_asset_a.refresh_from_db()
        assert assigned_asset_a.status == "in_repair"
        # holder is untouched by the maintenance sync
        assert assigned_asset_a.current_holder_id is not None

    def test_repair_completed_returns_assigned_holder_asset_to_assigned(self, tenant_a, active_repair_a):
        active_repair_a.status = "completed"
        active_repair_a.completed_date = datetime.date(2026, 7, 5)
        active_repair_a.save()
        active_repair_a.asset.refresh_from_db()
        assert active_repair_a.asset.status == "assigned"

    def test_repair_completed_returns_holderless_asset_to_in_stock(self, tenant_a, asset_in_stock_a):
        from apps.hrm.models import AssetMaintenance
        record = AssetMaintenance.objects.create(
            tenant=tenant_a, asset=asset_in_stock_a, maintenance_type="repair", status="scheduled",
            scheduled_date=datetime.date(2026, 7, 1),
        )
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_repair"
        record.status = "completed"
        record.save()
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"

    def test_repair_cancelled_returns_asset_to_service(self, tenant_a, asset_in_stock_a):
        from apps.hrm.models import AssetMaintenance
        record = AssetMaintenance.objects.create(
            tenant=tenant_a, asset=asset_in_stock_a, maintenance_type="repair", status="scheduled",
            scheduled_date=datetime.date(2026, 7, 1),
        )
        record.status = "cancelled"
        record.save()
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"

    @pytest.mark.parametrize("mtype", ["preventive", "amc", "warranty_claim", "inspection"])
    def test_non_repair_types_never_change_asset_status(self, tenant_a, asset_in_stock_a, mtype):
        from apps.hrm.models import AssetMaintenance
        AssetMaintenance.objects.create(
            tenant=tenant_a, asset=asset_in_stock_a, maintenance_type=mtype, status="scheduled",
            scheduled_date=datetime.date(2026, 7, 1),
        )
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"

    def test_fires_from_plain_model_save_not_just_views(self, tenant_a, asset_in_stock_a):
        """No view/client involved at all — a bare ORM .save() must trigger the sync."""
        from apps.hrm.models import AssetMaintenance
        record = AssetMaintenance(
            tenant=tenant_a, asset=asset_in_stock_a, maintenance_type="repair", status="scheduled",
            scheduled_date=datetime.date(2026, 7, 1),
        )
        record.save()
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_repair"


# ============================================================
# Model basics
# ============================================================

class TestAssetModelBasics:
    def test_str_includes_number_and_name(self, tenant_a, asset_in_stock_a):
        assert asset_in_stock_a.number in str(asset_in_stock_a)
        assert asset_in_stock_a.name in str(asset_in_stock_a)

    def test_number_prefix(self, asset_in_stock_a):
        assert asset_in_stock_a.number.startswith("ASSET-")

    def test_default_status_is_in_stock(self, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(tenant=tenant_a, name="Default Status", category="other")
        assert obj.status == "in_stock"

    def test_default_condition_is_good(self, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(tenant=tenant_a, name="Default Condition", category="other")
        assert obj.condition == "good"

    def test_default_depreciation_method_is_none(self, tenant_a):
        from apps.hrm.models import Asset
        obj = Asset.objects.create(tenant=tenant_a, name="Default Method", category="other")
        assert obj.depreciation_method == "none"

    def test_unique_together_tenant_number(self, tenant_a, asset_in_stock_a):
        from django.db import IntegrityError, transaction
        from apps.hrm.models import Asset
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Asset.objects.create(
                    tenant=tenant_a, name="Duplicate Number", category="other",
                    number=asset_in_stock_a.number,
                )

    def test_ast_prefix_does_not_collide_with_asset_prefix(self, tenant_a, asset_in_stock_a):
        """AssetAllocation.NUMBER_PREFIX="AST" must not collide with Asset.NUMBER_PREFIX="ASSET"
        (next_number matches on f"{prefix}-", and "ASSET-00001" does not start with "AST-")."""
        assert asset_in_stock_a.number.startswith("ASSET-")
        assert not asset_in_stock_a.number.startswith("AST-")


class TestAssetMaintenanceModelBasics:
    def test_str_includes_number_asset_and_type(self, maintenance_a):
        s = str(maintenance_a)
        assert maintenance_a.number in s
        assert maintenance_a.asset.name in s

    def test_number_prefix(self, maintenance_a):
        assert maintenance_a.number.startswith("ASSETMNT-")

    def test_default_status_is_scheduled(self, tenant_a, asset_in_stock_a):
        from apps.hrm.models import AssetMaintenance
        obj = AssetMaintenance.objects.create(
            tenant=tenant_a, asset=asset_in_stock_a, scheduled_date=datetime.date(2026, 7, 1),
        )
        assert obj.status == "scheduled"

    def test_default_type_is_preventive(self, tenant_a, asset_in_stock_a):
        from apps.hrm.models import AssetMaintenance
        obj = AssetMaintenance.objects.create(
            tenant=tenant_a, asset=asset_in_stock_a, scheduled_date=datetime.date(2026, 7, 1),
        )
        assert obj.maintenance_type == "preventive"


# ============================================================
# 6. Forms
# ============================================================

class TestAssetForm:
    def test_valid_payload_passes(self, tenant_a):
        from apps.hrm.forms import AssetForm
        form = AssetForm(data=_asset_payload(), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_salvage_exceeds_cost_rejected(self, tenant_a):
        from apps.hrm.forms import AssetForm
        form = AssetForm(data=_asset_payload(purchase_cost="1000", salvage_value="1500"), tenant=tenant_a)
        assert not form.is_valid()
        assert "salvage_value" in form.errors

    def test_method_without_useful_life_rejected(self, tenant_a):
        from apps.hrm.forms import AssetForm
        form = AssetForm(
            data=_asset_payload(depreciation_method="straight_line", useful_life_months=""),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "useful_life_months" in form.errors

    def test_method_with_useful_life_passes(self, tenant_a):
        from apps.hrm.forms import AssetForm
        form = AssetForm(
            data=_asset_payload(depreciation_method="straight_line", useful_life_months="24"),
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_status_field_not_excluded(self, tenant_a):
        """status IS a form field (HR can hand-correct it) — unlike current_holder."""
        from apps.hrm.forms import AssetForm
        assert "status" in AssetForm.Meta.fields

    def test_current_holder_excluded_system_managed(self):
        """current_holder is system-managed by the allocation sync — never a form field."""
        from apps.hrm.forms import AssetForm
        assert "current_holder" not in AssetForm.Meta.fields

    def test_tenant_and_number_excluded(self):
        from apps.hrm.forms import AssetForm
        assert "tenant" not in AssetForm.Meta.fields
        assert "number" not in AssetForm.Meta.fields

    def test_setting_in_stock_with_open_issued_allocation_rejected(self, tenant_a, assigned_asset_a):
        from apps.hrm.forms import AssetForm
        form = AssetForm(
            data=_asset_payload(name=assigned_asset_a.name, status="in_stock"),
            instance=assigned_asset_a, tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "status" in form.errors

    def test_setting_in_stock_without_open_allocation_passes(self, tenant_a, asset_in_stock_a):
        from apps.hrm.forms import AssetForm
        form = AssetForm(
            data=_asset_payload(name=asset_in_stock_a.name, status="in_stock"),
            instance=asset_in_stock_a, tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_setting_non_in_stock_status_with_open_allocation_passes(self, tenant_a, assigned_asset_a):
        """The guard only blocks the *in_stock* transition — any other status hand-edit is fine."""
        from apps.hrm.forms import AssetForm
        form = AssetForm(
            data=_asset_payload(name=assigned_asset_a.name, status="in_repair"),
            instance=assigned_asset_a, tenant=tenant_a,
        )
        assert form.is_valid(), form.errors


class TestAssetMaintenanceForm:
    def test_valid_payload_passes(self, tenant_a, asset_in_stock_a):
        from apps.hrm.forms import AssetMaintenanceForm
        form = AssetMaintenanceForm(data=_maintenance_payload(asset_in_stock_a.pk), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_completed_before_scheduled_rejected(self, tenant_a, asset_in_stock_a):
        from apps.hrm.forms import AssetMaintenanceForm
        form = AssetMaintenanceForm(
            data=_maintenance_payload(
                asset_in_stock_a.pk, scheduled_date="2026-07-10", completed_date="2026-07-05"),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "completed_date" in form.errors

    def test_completed_on_or_after_scheduled_passes(self, tenant_a, asset_in_stock_a):
        from apps.hrm.forms import AssetMaintenanceForm
        form = AssetMaintenanceForm(
            data=_maintenance_payload(
                asset_in_stock_a.pk, scheduled_date="2026-07-10", completed_date="2026-07-10"),
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_contract_end_equal_start_rejected(self, tenant_a, asset_in_stock_a):
        from apps.hrm.forms import AssetMaintenanceForm
        form = AssetMaintenanceForm(
            data=_maintenance_payload(
                asset_in_stock_a.pk, maintenance_type="amc",
                contract_start="2026-01-01", contract_end="2026-01-01"),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "contract_end" in form.errors

    def test_contract_end_before_start_rejected(self, tenant_a, asset_in_stock_a):
        from apps.hrm.forms import AssetMaintenanceForm
        form = AssetMaintenanceForm(
            data=_maintenance_payload(
                asset_in_stock_a.pk, maintenance_type="amc",
                contract_start="2026-06-01", contract_end="2026-01-01"),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "contract_end" in form.errors

    def test_contract_end_after_start_passes(self, tenant_a, asset_in_stock_a):
        from apps.hrm.forms import AssetMaintenanceForm
        form = AssetMaintenanceForm(
            data=_maintenance_payload(
                asset_in_stock_a.pk, maintenance_type="amc",
                contract_start="2026-01-01", contract_end="2026-12-31"),
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors


class TestAssetAllocationForm:
    def test_valid_payload_passes(self, tenant_a, employee_a):
        from apps.hrm.forms import AssetAllocationForm
        form = AssetAllocationForm(data=_allocation_payload(employee_a.pk), tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_double_issuing_asset_rejected(self, tenant_a, assigned_asset_a, employee_a2):
        """assigned_asset_a already has an active issued allocation — linking it to a SECOND
        issued allocation must be rejected (bypassing the asset_assign in_stock guard)."""
        from apps.hrm.forms import AssetAllocationForm
        form = AssetAllocationForm(
            data=_allocation_payload(
                employee_a2.pk, asset=assigned_asset_a.pk, asset_name=assigned_asset_a.name,
                asset_category=assigned_asset_a.category, status="issued"),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "asset" in form.errors

    def test_issuing_in_stock_asset_passes(self, tenant_a, asset_in_stock_a, employee_a):
        from apps.hrm.forms import AssetAllocationForm
        form = AssetAllocationForm(
            data=_allocation_payload(
                employee_a.pk, asset=asset_in_stock_a.pk, asset_name=asset_in_stock_a.name,
                asset_category=asset_in_stock_a.category, status="issued"),
            tenant=tenant_a,
        )
        assert form.is_valid(), form.errors

    def test_editing_own_issued_allocation_does_not_clash_with_itself(self, tenant_a, assigned_asset_a):
        """Re-saving the SAME issued allocation (excluded via self.instance.pk) must not
        self-clash."""
        from apps.hrm.forms import AssetAllocationForm
        allocation = assigned_asset_a.allocations.get(status="issued")
        form = AssetAllocationForm(
            data=_allocation_payload(
                allocation.employee_id, asset=assigned_asset_a.pk, asset_name=assigned_asset_a.name,
                asset_category=assigned_asset_a.category, status="issued", notes="updated"),
            instance=allocation, tenant=tenant_a,
        )
        assert form.is_valid(), form.errors


# ============================================================
# 4 & CRUD. Asset views
# ============================================================

class TestAssetListView:
    def test_200(self, client_a, asset_in_stock_a):
        resp = client_a.get(reverse("hrm:asset_list"))
        assert resp.status_code == 200
        assert resp.templates[0].name == "hrm/assets/asset/list.html"

    def test_context_keys(self, client_a, asset_in_stock_a):
        resp = client_a.get(reverse("hrm:asset_list"))
        for key in ("object_list", "page_obj", "q", "status_choices", "category_choices",
                    "locations", "holders"):
            assert key in resp.context

    def test_search_by_name(self, client_a, asset_in_stock_a):
        resp = client_a.get(reverse("hrm:asset_list"), {"q": "ThinkPad"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert asset_in_stock_a.pk in pks

    def test_search_no_match(self, client_a, asset_in_stock_a):
        resp = client_a.get(reverse("hrm:asset_list"), {"q": "Nonexistent Zzz"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert asset_in_stock_a.pk not in pks

    def test_filter_by_status(self, client_a, asset_in_stock_a, retired_asset_a):
        resp = client_a.get(reverse("hrm:asset_list"), {"status": "retired"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert retired_asset_a.pk in pks
        assert asset_in_stock_a.pk not in pks

    def test_filter_by_category(self, client_a, asset_in_stock_a):
        resp = client_a.get(reverse("hrm:asset_list"), {"category": "laptop"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert asset_in_stock_a.pk in pks

    def test_filter_by_current_holder(self, client_a, assigned_asset_a, asset_in_stock_a, employee_a):
        resp = client_a.get(reverse("hrm:asset_list"), {"current_holder": str(employee_a.pk)})
        pks = [o.pk for o in resp.context["object_list"]]
        assert assigned_asset_a.pk in pks
        assert asset_in_stock_a.pk not in pks

    def test_bad_page_does_not_500(self, client_a, asset_in_stock_a):
        resp = client_a.get(reverse("hrm:asset_list"), {"page": "999"})
        assert resp.status_code == 200


class TestAssetCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:asset_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_post_creates_with_request_tenant(self, client_a, tenant_a):
        from apps.hrm.models import Asset
        resp = client_a.post(reverse("hrm:asset_create"), _asset_payload(name="Brand New Asset"))
        assert resp.status_code == 302
        obj = Asset.objects.get(tenant=tenant_a, name="Brand New Asset")
        assert obj.tenant_id == tenant_a.pk
        assert obj.number.startswith("ASSET-")

    def test_post_invalid_rerenders_form(self, client_a):
        resp = client_a.post(reverse("hrm:asset_create"), _asset_payload(name=""))
        assert resp.status_code == 200
        assert resp.context["form"].errors


class TestAssetDetailView:
    def test_200_with_context(self, client_a, assigned_asset_a):
        resp = client_a.get(reverse("hrm:asset_detail", args=[assigned_asset_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == assigned_asset_a.pk
        for key in ("allocations", "maintenance_records", "assignable_employees"):
            assert key in resp.context


class TestAssetEditView:
    def test_get_200(self, client_a, asset_in_stock_a):
        resp = client_a.get(reverse("hrm:asset_edit", args=[asset_in_stock_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True
        assert resp.context["obj"].pk == asset_in_stock_a.pk

    def test_post_updates(self, client_a, asset_in_stock_a):
        resp = client_a.post(
            reverse("hrm:asset_edit", args=[asset_in_stock_a.pk]),
            _asset_payload(name="Renamed Asset"),
        )
        assert resp.status_code == 302
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.name == "Renamed Asset"


class TestAssetDeleteView:
    def test_get_not_allowed(self, client_a, asset_in_stock_a):
        resp = client_a.get(reverse("hrm:asset_delete", args=[asset_in_stock_a.pk]))
        assert resp.status_code == 405

    def test_deletes_when_in_stock(self, client_a, asset_in_stock_a):
        from apps.hrm.models import Asset
        pk = asset_in_stock_a.pk
        resp = client_a.post(reverse("hrm:asset_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Asset.objects.filter(pk=pk).exists()

    def test_deletes_when_retired(self, client_a, retired_asset_a):
        from apps.hrm.models import Asset
        pk = retired_asset_a.pk
        resp = client_a.post(reverse("hrm:asset_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Asset.objects.filter(pk=pk).exists()

    def test_blocked_when_assigned(self, client_a, assigned_asset_a):
        from apps.hrm.models import Asset
        pk = assigned_asset_a.pk
        resp = client_a.post(reverse("hrm:asset_delete", args=[pk]))
        assert resp.status_code == 302
        assert Asset.objects.filter(pk=pk).exists()

    def test_blocked_when_in_repair(self, client_a, active_repair_a):
        from apps.hrm.models import Asset
        pk = active_repair_a.asset.pk
        resp = client_a.post(reverse("hrm:asset_delete", args=[pk]))
        assert resp.status_code == 302
        assert Asset.objects.filter(pk=pk).exists()


class TestAssetAssignView:
    def test_assigns_from_in_stock(self, client_a, asset_in_stock_a, employee_a):
        from apps.hrm.models import AssetAllocation
        resp = client_a.post(
            reverse("hrm:asset_assign", args=[asset_in_stock_a.pk]),
            {"employee": str(employee_a.pk), "notes": "New hire kit"},
        )
        assert resp.status_code == 302
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "assigned"
        assert asset_in_stock_a.current_holder_id == employee_a.pk
        assert AssetAllocation.objects.filter(asset=asset_in_stock_a, status="issued",
                                              employee=employee_a).exists()

    def test_rejected_when_not_in_stock(self, client_a, assigned_asset_a, employee_a2):
        resp = client_a.post(
            reverse("hrm:asset_assign", args=[assigned_asset_a.pk]),
            {"employee": str(employee_a2.pk)},
        )
        assert resp.status_code == 302
        assigned_asset_a.refresh_from_db()
        # still assigned to the ORIGINAL holder, not employee_a2
        assert assigned_asset_a.current_holder_id != employee_a2.pk

    def test_rejected_on_garbage_employee_pk_no_500(self, client_a, asset_in_stock_a):
        resp = client_a.post(
            reverse("hrm:asset_assign", args=[asset_in_stock_a.pk]),
            {"employee": "not-a-number"},
        )
        assert resp.status_code == 302
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"

    def test_rejected_on_cross_tenant_employee_pk_no_500(self, client_a, asset_in_stock_a, employee_b):
        resp = client_a.post(
            reverse("hrm:asset_assign", args=[asset_in_stock_a.pk]),
            {"employee": str(employee_b.pk)},
        )
        assert resp.status_code == 302
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"

    def test_rejected_on_missing_employee_no_500(self, client_a, asset_in_stock_a):
        resp = client_a.post(reverse("hrm:asset_assign", args=[asset_in_stock_a.pk]), {})
        assert resp.status_code == 302
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"


class TestAssetReturnView:
    def test_returns_assigned_asset_to_stock(self, client_a, assigned_asset_a):
        resp = client_a.post(reverse("hrm:asset_return", args=[assigned_asset_a.pk]))
        assert resp.status_code == 302
        assigned_asset_a.refresh_from_db()
        assert assigned_asset_a.status == "in_stock"
        assert assigned_asset_a.current_holder_id is None

    def test_marks_allocation_returned(self, client_a, assigned_asset_a):
        allocation = assigned_asset_a.allocations.get(status="issued")
        client_a.post(reverse("hrm:asset_return", args=[assigned_asset_a.pk]))
        allocation.refresh_from_db()
        assert allocation.status == "returned"
        assert allocation.returned_at is not None

    def test_errors_when_no_active_allocation(self, client_a, asset_in_stock_a):
        resp = client_a.post(reverse("hrm:asset_return", args=[asset_in_stock_a.pk]))
        assert resp.status_code == 302
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"


class TestAssetRetireView:
    def test_retires_in_stock_asset(self, client_a, asset_in_stock_a):
        resp = client_a.post(reverse("hrm:asset_retire", args=[asset_in_stock_a.pk]))
        assert resp.status_code == 302
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "retired"
        assert asset_in_stock_a.current_holder_id is None

    def test_retires_in_repair_asset_clears_holder(self, client_a, active_repair_a):
        asset = active_repair_a.asset
        assert asset.current_holder_id is not None
        resp = client_a.post(reverse("hrm:asset_retire", args=[asset.pk]))
        assert resp.status_code == 302
        asset.refresh_from_db()
        assert asset.status == "retired"
        assert asset.current_holder_id is None

    def test_rejected_when_assigned(self, client_a, assigned_asset_a):
        resp = client_a.post(reverse("hrm:asset_retire", args=[assigned_asset_a.pk]))
        assert resp.status_code == 302
        assigned_asset_a.refresh_from_db()
        assert assigned_asset_a.status == "assigned"

    def test_rejected_when_already_retired(self, client_a, retired_asset_a):
        resp = client_a.post(reverse("hrm:asset_retire", args=[retired_asset_a.pk]))
        assert resp.status_code == 302
        retired_asset_a.refresh_from_db()
        assert retired_asset_a.status == "retired"


class TestAssetDisposeView:
    def test_disposes_retired_asset(self, client_a, retired_asset_a):
        resp = client_a.post(reverse("hrm:asset_dispose", args=[retired_asset_a.pk]))
        assert resp.status_code == 302
        retired_asset_a.refresh_from_db()
        assert retired_asset_a.status == "disposed"

    def test_rejected_when_not_retired(self, client_a, asset_in_stock_a):
        resp = client_a.post(reverse("hrm:asset_dispose", args=[asset_in_stock_a.pk]))
        assert resp.status_code == 302
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"


# ============================================================
# 5 & CRUD. AssetMaintenance views
# ============================================================

class TestAssetMaintenanceListView:
    def test_200(self, client_a, maintenance_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_list"))
        assert resp.status_code == 200
        assert resp.templates[0].name == "hrm/assets/assetmaintenance/list.html"

    def test_context_keys(self, client_a, maintenance_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_list"))
        for key in ("object_list", "page_obj", "q", "status_choices", "type_choices", "assets"):
            assert key in resp.context

    def test_search_by_vendor(self, client_a, tenant_a, asset_in_stock_a):
        from apps.hrm.models import AssetMaintenance
        record = AssetMaintenance.objects.create(
            tenant=tenant_a, asset=asset_in_stock_a, maintenance_type="amc", status="scheduled",
            scheduled_date=datetime.date(2026, 7, 1), vendor="Acme Repairs Co",
        )
        resp = client_a.get(reverse("hrm:assetmaintenance_list"), {"q": "Acme Repairs"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert record.pk in pks

    def test_filter_by_status(self, client_a, maintenance_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_list"), {"status": "scheduled"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert maintenance_a.pk in pks

    def test_filter_by_maintenance_type(self, client_a, maintenance_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_list"), {"maintenance_type": "preventive"})
        pks = [o.pk for o in resp.context["object_list"]]
        assert maintenance_a.pk in pks

    def test_filter_by_asset(self, client_a, maintenance_a, asset_in_stock_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_list"), {"asset": str(asset_in_stock_a.pk)})
        pks = [o.pk for o in resp.context["object_list"]]
        assert maintenance_a.pk in pks

    def test_bad_page_does_not_500(self, client_a, maintenance_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_list"), {"page": "999"})
        assert resp.status_code == 200


class TestAssetMaintenanceCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_create"))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is False

    def test_get_honors_asset_query_param_as_initial(self, client_a, asset_in_stock_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_create") + f"?asset={asset_in_stock_a.pk}")
        assert resp.status_code == 200
        assert resp.context["form"].initial.get("asset") == str(asset_in_stock_a.pk)

    def test_post_creates_record(self, client_a, tenant_a, asset_in_stock_a):
        from apps.hrm.models import AssetMaintenance
        resp = client_a.post(
            reverse("hrm:assetmaintenance_create"), _maintenance_payload(asset_in_stock_a.pk),
        )
        assert resp.status_code == 302
        assert AssetMaintenance.objects.filter(tenant=tenant_a, asset=asset_in_stock_a).exists()

    def test_post_with_asset_param_flips_repair_and_redirects_to_asset(self, client_a, asset_in_stock_a):
        url = reverse("hrm:assetmaintenance_create") + f"?asset={asset_in_stock_a.pk}"
        resp = client_a.post(url, _maintenance_payload(
            asset_in_stock_a.pk, maintenance_type="repair", status="scheduled"))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:asset_detail", args=[asset_in_stock_a.pk])
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_repair"

    def test_post_without_asset_param_redirects_to_list(self, client_a, asset_in_stock_a):
        resp = client_a.post(
            reverse("hrm:assetmaintenance_create"), _maintenance_payload(asset_in_stock_a.pk),
        )
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:assetmaintenance_list")

    def test_post_invalid_rerenders_form(self, client_a, asset_in_stock_a):
        resp = client_a.post(
            reverse("hrm:assetmaintenance_create"),
            _maintenance_payload(
                asset_in_stock_a.pk, scheduled_date="2026-07-10", completed_date="2026-01-01"),
        )
        assert resp.status_code == 200
        assert resp.context["form"].errors


class TestAssetMaintenanceDetailView:
    def test_200(self, client_a, maintenance_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_detail", args=[maintenance_a.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == maintenance_a.pk


class TestAssetMaintenanceEditView:
    def test_get_200(self, client_a, maintenance_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_edit", args=[maintenance_a.pk]))
        assert resp.status_code == 200
        assert resp.context["is_edit"] is True

    def test_post_updates(self, client_a, maintenance_a):
        resp = client_a.post(
            reverse("hrm:assetmaintenance_edit", args=[maintenance_a.pk]),
            _maintenance_payload(maintenance_a.asset_id, vendor="Updated Vendor Co"),
        )
        assert resp.status_code == 302
        maintenance_a.refresh_from_db()
        assert maintenance_a.vendor == "Updated Vendor Co"


class TestAssetMaintenanceDeleteView:
    def test_get_not_allowed(self, client_a, maintenance_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_delete", args=[maintenance_a.pk]))
        assert resp.status_code == 405

    def test_deletes_non_repair_record(self, client_a, maintenance_a):
        from apps.hrm.models import AssetMaintenance
        pk = maintenance_a.pk
        resp = client_a.post(reverse("hrm:assetmaintenance_delete", args=[pk]))
        assert resp.status_code == 302
        assert not AssetMaintenance.objects.filter(pk=pk).exists()

    def test_blocks_deleting_active_repair_of_in_repair_asset(self, client_a, active_repair_a):
        from apps.hrm.models import AssetMaintenance
        pk = active_repair_a.pk
        asset = active_repair_a.asset
        resp = client_a.post(reverse("hrm:assetmaintenance_delete", args=[pk]))
        assert resp.status_code == 302
        assert AssetMaintenance.objects.filter(pk=pk).exists()
        asset.refresh_from_db()
        assert asset.status == "in_repair"

    def test_allows_deleting_completed_repair(self, client_a, active_repair_a):
        from apps.hrm.models import AssetMaintenance
        active_repair_a.status = "completed"
        active_repair_a.completed_date = datetime.date(2026, 7, 5)
        active_repair_a.save()
        pk = active_repair_a.pk
        resp = client_a.post(reverse("hrm:assetmaintenance_delete", args=[pk]))
        assert resp.status_code == 302
        assert not AssetMaintenance.objects.filter(pk=pk).exists()


class TestAssetMaintenanceCompleteView:
    def test_completes_scheduled_record(self, client_a, maintenance_a):
        resp = client_a.post(reverse("hrm:assetmaintenance_complete", args=[maintenance_a.pk]))
        assert resp.status_code == 302
        maintenance_a.refresh_from_db()
        assert maintenance_a.status == "completed"
        assert maintenance_a.completed_date is not None

    def test_returns_repaired_asset_with_holder_to_assigned(self, client_a, active_repair_a):
        asset = active_repair_a.asset
        assert asset.status == "in_repair"
        resp = client_a.post(reverse("hrm:assetmaintenance_complete", args=[active_repair_a.pk]))
        assert resp.status_code == 302
        asset.refresh_from_db()
        assert asset.status == "assigned"

    def test_returns_repaired_asset_without_holder_to_in_stock(self, client_a, tenant_a, asset_in_stock_a):
        from apps.hrm.models import AssetMaintenance
        record = AssetMaintenance.objects.create(
            tenant=tenant_a, asset=asset_in_stock_a, maintenance_type="repair", status="scheduled",
            scheduled_date=datetime.date(2026, 7, 1),
        )
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_repair"
        resp = client_a.post(reverse("hrm:assetmaintenance_complete", args=[record.pk]))
        assert resp.status_code == 302
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"

    def test_noop_on_already_completed_record(self, client_a, tenant_a, asset_in_stock_a):
        from apps.hrm.models import AssetMaintenance
        record = AssetMaintenance.objects.create(
            tenant=tenant_a, asset=asset_in_stock_a, maintenance_type="preventive", status="completed",
            scheduled_date=datetime.date(2026, 7, 1), completed_date=datetime.date(2026, 7, 2),
        )
        original_completed = record.completed_date
        resp = client_a.post(reverse("hrm:assetmaintenance_complete", args=[record.pk]))
        assert resp.status_code == 302
        record.refresh_from_db()
        assert record.completed_date == original_completed


# ============================================================
# 7. Access control
# ============================================================

class TestAccessControl:
    @pytest.mark.parametrize("url_name", ["asset_list", "assetmaintenance_list"])
    def test_anonymous_redirects_to_login(self, url_name):
        c = Client()
        resp = c.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_non_admin_member_can_view_asset_list(self, member_client, asset_in_stock_a):
        """login_required only — NOT admin-gated (unlike the Module-0 config views)."""
        resp = member_client.get(reverse("hrm:asset_list"))
        assert resp.status_code == 200

    def test_non_admin_member_can_view_maintenance_list(self, member_client, maintenance_a):
        resp = member_client.get(reverse("hrm:assetmaintenance_list"))
        assert resp.status_code == 200

    def test_non_admin_member_can_create_asset(self, member_client, tenant_a):
        from apps.hrm.models import Asset
        resp = member_client.post(reverse("hrm:asset_create"), _asset_payload(name="Member Created"))
        assert resp.status_code == 302
        assert Asset.objects.filter(tenant=tenant_a, name="Member Created").exists()


class TestCSRFEnforcement:
    def test_asset_delete_enforces_csrf(self, admin_user, asset_in_stock_a):
        from apps.hrm.models import Asset
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:asset_delete", args=[asset_in_stock_a.pk]))
        assert resp.status_code == 403
        assert Asset.objects.filter(pk=asset_in_stock_a.pk).exists()

    def test_asset_assign_enforces_csrf(self, admin_user, asset_in_stock_a, employee_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(
            reverse("hrm:asset_assign", args=[asset_in_stock_a.pk]), {"employee": str(employee_a.pk)},
        )
        assert resp.status_code == 403
        asset_in_stock_a.refresh_from_db()
        assert asset_in_stock_a.status == "in_stock"

    def test_assetmaintenance_delete_enforces_csrf(self, admin_user, maintenance_a):
        from apps.hrm.models import AssetMaintenance
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:assetmaintenance_delete", args=[maintenance_a.pk]))
        assert resp.status_code == 403
        assert AssetMaintenance.objects.filter(pk=maintenance_a.pk).exists()


# ============================================================
# 8. Multi-tenant / IDOR
# ============================================================

class TestAssetIDOR:
    def test_detail_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.get(reverse("hrm:asset_detail", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.get(reverse("hrm:asset_edit", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.post(reverse("hrm:asset_delete", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_assign_cross_tenant_404(self, client_a, asset_b, employee_a):
        resp = client_a.post(
            reverse("hrm:asset_assign", args=[asset_b.pk]), {"employee": str(employee_a.pk)},
        )
        assert resp.status_code == 404

    def test_return_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.post(reverse("hrm:asset_return", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_retire_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.post(reverse("hrm:asset_retire", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_dispose_cross_tenant_404(self, client_a, asset_b):
        resp = client_a.post(reverse("hrm:asset_dispose", args=[asset_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_assets(self, client_a, asset_in_stock_a, asset_b):
        resp = client_a.get(reverse("hrm:asset_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert asset_in_stock_a.pk in pks
        assert asset_b.pk not in pks

    def test_location_filter_cross_tenant_pk_ignored(self, client_a, asset_in_stock_a, dept_b):
        """A cross-tenant location pk never leaks tenant_a rows filtered against it — the
        queryset stays scoped to tenant_a, so it's just an (always-empty) filter, never an error
        or a cross-tenant row."""
        resp = client_a.get(reverse("hrm:asset_list"), {"location": str(dept_b.pk)})
        assert resp.status_code == 200
        pks = [o.pk for o in resp.context["object_list"]]
        assert asset_in_stock_a.pk not in pks

    def test_current_holder_filter_cross_tenant_pk_ignored(self, client_a, asset_in_stock_a, employee_b):
        resp = client_a.get(reverse("hrm:asset_list"), {"current_holder": str(employee_b.pk)})
        assert resp.status_code == 200
        pks = [o.pk for o in resp.context["object_list"]]
        assert asset_in_stock_a.pk not in pks


class TestAssetMaintenanceIDOR:
    def test_detail_cross_tenant_404(self, client_a, maintenance_b):
        resp = client_a.get(reverse("hrm:assetmaintenance_detail", args=[maintenance_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, maintenance_b):
        resp = client_a.get(reverse("hrm:assetmaintenance_edit", args=[maintenance_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, maintenance_b):
        resp = client_a.post(reverse("hrm:assetmaintenance_delete", args=[maintenance_b.pk]))
        assert resp.status_code == 404

    def test_complete_cross_tenant_404(self, client_a, maintenance_b):
        resp = client_a.post(reverse("hrm:assetmaintenance_complete", args=[maintenance_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_records(self, client_a, maintenance_a, maintenance_b):
        resp = client_a.get(reverse("hrm:assetmaintenance_list"))
        pks = [o.pk for o in resp.context["object_list"]]
        assert maintenance_a.pk in pks
        assert maintenance_b.pk not in pks

    def test_asset_filter_cross_tenant_pk_ignored(self, client_a, maintenance_a, asset_b):
        resp = client_a.get(reverse("hrm:assetmaintenance_list"), {"asset": str(asset_b.pk)})
        assert resp.status_code == 200
        pks = [o.pk for o in resp.context["object_list"]]
        assert maintenance_a.pk not in pks


# ============================================================
# 9. Empty tenant
# ============================================================

class TestEmptyTenant:
    def test_asset_list_empty_200(self, client_a):
        resp = client_a.get(reverse("hrm:asset_list"))
        assert resp.status_code == 200
        assert list(resp.context["object_list"]) == []

    def test_assetmaintenance_list_empty_200(self, client_a):
        resp = client_a.get(reverse("hrm:assetmaintenance_list"))
        assert resp.status_code == 200
        assert list(resp.context["object_list"]) == []


# ============================================================
# 10. Query-count ceilings (N+1 guard)
# ============================================================

class TestQueryCount:
    def test_asset_list_query_count_bounded(self, client_a, many_assets_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(12):
            client_a.get(reverse("hrm:asset_list"))

    def test_assetmaintenance_list_query_count_bounded(
            self, client_a, many_maintenance_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(12):
            client_a.get(reverse("hrm:assetmaintenance_list"))
