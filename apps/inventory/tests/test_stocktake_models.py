"""Inventory 5.11 Stocktaking & Cycle Counting — model invariants.

Two documents sit on top of SCM 4.4's ``CycleCountTask`` spine without re-declaring any of
it: ``CountProgram`` [CTP-] owns the recurring CALENDAR (is_due/generate_tasks stamping a
``Via count program`` provenance marker into spine notes) and ``PhysicalInventory`` [PHY-]
owns the warehouse-wide FREEZE (start spawns one blind full-count sheet per bin/zone,
reconcile refuses while any spawned sheet is still open). Statuses move ONLY through the
verbs on the inventory side; the spine's own statuses are ordinary data.
"""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.utils import timezone

from apps.inventory.models import CountProgram, PhysicalInventory

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _stocktake_monday():
    """A known Monday (2026-08-24) for deterministic cadence math."""
    return datetime.date(2026, 8, 24)


def _stocktake_tuesday():
    return _stocktake_monday() + datetime.timedelta(days=1)


def _stocktake_program(tenant, location=None, *, name="Probe cadence", **fields):
    return CountProgram.objects.create(
        tenant=tenant, name=name, location=location,
        frequency=fields.pop("frequency", "weekly"),
        weekday=fields.pop("weekday", 0),
        **fields)


def _stocktake_sheet(tenant, location, *, status="scheduled", scheduled_date=None,
                     count_method="full", notes=""):
    """A spine CycleCountTask as 5.11 sees it — statuses are plain data on 4.4."""
    from apps.scm.models import CycleCountTask

    return CycleCountTask.objects.create(
        tenant=tenant, location=location,
        scheduled_date=scheduled_date or timezone.localdate(),
        count_method=count_method, status=status, notes=notes)


def _stocktake_audit_rows(obj):
    from django.contrib.contenttypes.models import ContentType

    from apps.core.models import AuditLog
    return AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)), object_id=obj.pk)


# ------------------------------------------------------------------ CountProgram — identity


def test_stocktake_count_program_numbers_sequential_and_per_tenant(
        tenant_a, tenant_b, stocktake_zone_a, stocktake_bin_b):
    first = _stocktake_program(tenant_a, stocktake_zone_a)
    second = _stocktake_program(tenant_a, stocktake_zone_a, name="Second cadence")
    assert first.number == "CTP-00001"
    assert second.number == "CTP-00002"
    # A second workspace's sequence starts at one — numbers never share across tenants.
    other = _stocktake_program(tenant_b, stocktake_bin_b, name="Globex cadence")
    assert other.number == "CTP-00001"


def test_stocktake_count_program_name_unique_per_tenant(
        tenant_a, stocktake_zone_a):
    _stocktake_program(tenant_a, stocktake_zone_a, name="Weekly sweep")
    with pytest.raises(IntegrityError):
        _stocktake_program(tenant_a, stocktake_zone_a, name="Weekly sweep")


def test_stocktake_count_program_str_and_ordering(tenant_a, stocktake_zone_a):
    zeta = _stocktake_program(tenant_a, stocktake_zone_a, name="Zeta sweep")
    alpha = _stocktake_program(tenant_a, stocktake_zone_a, name="Alpha sweep")
    assert str(zeta) == f"{zeta.number} · Zeta sweep"
    assert list(CountProgram.objects.filter(tenant=tenant_a)) == [alpha, zeta]  # Meta.ordering name


def test_stocktake_count_program_cadence_label(tenant_a, stocktake_zone_a):
    daily = _stocktake_program(tenant_a, None, frequency="daily",
                               weekday=None, name="Daily patrol")
    weekly = _stocktake_program(tenant_a, stocktake_zone_a, frequency="weekly",
                                weekday=0, name="Monday sweep")
    monthly = _stocktake_program(tenant_a, None, frequency="monthly", weekday=None,
                                 day_of_month=15, name="Mid-month sweep")
    assert daily.cadence_label == "Every day"
    assert weekly.cadence_label == "Every Monday"
    assert monthly.cadence_label == "On day 15 monthly"


# ------------------------------------------------------------------ CountProgram — cadence


def test_stocktake_count_program_is_due_truth_table(tenant_a, stocktake_zone_a):
    monday, tuesday = _stocktake_monday(), _stocktake_tuesday()
    daily = _stocktake_program(tenant_a, stocktake_zone_a, frequency="daily",
                               weekday=None, name="Every day")
    weekly_monday = _stocktake_program(tenant_a, stocktake_zone_a, frequency="weekly",
                                       weekday=0, name="Mondays")
    inactive = _stocktake_program(tenant_a, stocktake_zone_a, frequency="weekly",
                                  weekday=0, is_active=False, name="Retired")
    assert daily.is_due(monday) and daily.is_due(tuesday)          # daily: always due
    assert weekly_monday.is_due(monday)
    assert not weekly_monday.is_due(tuesday)                        # weekly: only its weekday
    assert not inactive.is_due(monday)                              # inactive: never
    # A weekly program missing its weekday answers False rather than crashing.
    broken = CountProgram(frequency="weekly", weekday=None, is_active=True)
    assert not broken.is_due(monday)
    # Already run today -> not due again.
    daily.last_run_date = tuesday
    assert not daily.is_due(tuesday)
    assert daily.is_due(monday)


def test_stocktake_count_program_is_due_monthly_with_short_month_rollup(tenant_a):
    mid = CountProgram(tenant_id=tenant_a.id, frequency="monthly", day_of_month=15,
                       is_active=True)
    assert mid.is_due(datetime.date(2026, 7, 15))
    assert not mid.is_due(datetime.date(2026, 7, 14))
    assert not mid.is_due(datetime.date(2026, 7, 16))
    # Day 28 fires even in short months (min(today.day, 28)).
    edge = CountProgram(tenant_id=tenant_a.id, frequency="monthly",
                        day_of_month=28, is_active=True)
    assert edge.is_due(datetime.date(2026, 2, 28))


# ------------------------------------------------------------------ CountProgram — clean()


def test_stocktake_clean_rejects_foreign_location(tenant_a, stocktake_bin_b):
    program = _stocktake_program(tenant_a, stocktake_bin_b)
    with pytest.raises(ValidationError) as err:
        program.clean()
    assert "location" in err.value.message_dict


def test_stocktake_clean_rejects_weekly_without_weekday(tenant_a, stocktake_zone_a):
    program = _stocktake_program(tenant_a, stocktake_zone_a, weekday=None)
    with pytest.raises(ValidationError) as err:
        program.clean()
    assert "weekday" in err.value.message_dict


def test_stocktake_clean_rejects_monthly_without_day_of_month(tenant_a, stocktake_zone_a):
    program = _stocktake_program(tenant_a, stocktake_zone_a,
                                 frequency="monthly", weekday=None, day_of_month=None)
    with pytest.raises(ValidationError) as err:
        program.clean()
    assert "day_of_month" in err.value.message_dict


# ------------------------------------------------------------------ CountProgram — generate_tasks


def test_stocktake_generate_tasks_mints_blind_sheet_with_provenance(
        tenant_a, admin_user, stocktake_program_a):
    stocktake_program_a.count_method = "full"
    stocktake_program_a.save()
    today = _stocktake_monday()
    task, created = stocktake_program_a.generate_tasks(admin_user, today=today)
    assert created is True
    assert task.tenant_id == tenant_a.id
    assert task.location_id == stocktake_program_a.location_id
    assert task.scheduled_date == today
    assert task.count_method == "full"
    # Provenance stamp lives in spine notes; nothing else links module 5 to 4.4.
    assert task.notes.startswith(f"Via count program {stocktake_program_a.number}")
    assert stocktake_program_a.name in task.notes
    stocktake_program_a.refresh_from_db()
    assert stocktake_program_a.last_run_date == today


def test_stocktake_generate_tasks_same_day_reuse_returns_existing(
        tenant_a, admin_user, stocktake_program_a):
    today = _stocktake_monday()
    first, created_first = stocktake_program_a.generate_tasks(admin_user, today=today)
    second, created_second = stocktake_program_a.generate_tasks(admin_user, today=today)
    assert created_first is True
    assert created_second is False
    assert second.pk == first.pk
    from apps.scm.models import CycleCountTask
    assert CycleCountTask.objects.filter(tenant=tenant_a).count() == 1


def test_stocktake_generate_tasks_reuse_ignores_cancelled_sheets(
        tenant_a, admin_user, stocktake_program_a):
    today = _stocktake_monday()
    stale, _created = stocktake_program_a.generate_tasks(admin_user, today=today)
    stale.status = "cancelled"  # spine statuses are plain data on 4.4
    stale.save(update_fields=["status"])
    fresh, created = stocktake_program_a.generate_tasks(admin_user, today=today)
    assert created is True
    assert fresh.pk != stale.pk


def test_stocktake_generate_tasks_refuses_none_scope(tenant_a, admin_user):
    orphan = _stocktake_program(tenant_a, None, name="No scope yet")
    with pytest.raises(ValidationError) as err:
        orphan.generate_tasks(admin_user)
    assert "no counting scope" in str(err.value)


# ------------------------------------------------------------------ PhysicalInventory — identity


def test_stocktake_physical_inventory_numbers_sequential_and_per_tenant(
        tenant_a, tenant_b, stocktake_warehouse_a, stocktake_warehouse_b):
    first = PhysicalInventory.objects.create(
        tenant=tenant_a, warehouse=stocktake_warehouse_a,
        scheduled_date=_stocktake_monday())
    second = PhysicalInventory.objects.create(
        tenant=tenant_a, warehouse=stocktake_warehouse_a,
        scheduled_date=_stocktake_monday())
    assert first.number == "PHY-00001"
    assert second.number == "PHY-00002"
    other = PhysicalInventory.objects.create(
        tenant=tenant_b, warehouse=stocktake_warehouse_b,
        scheduled_date=_stocktake_monday())
    assert other.number == "PHY-00001"


def test_stocktake_physical_inventory_str_and_ordering(
        tenant_a, stocktake_warehouse_a):
    older = PhysicalInventory.objects.create(
        tenant=tenant_a, warehouse=stocktake_warehouse_a,
        scheduled_date=datetime.date(2026, 8, 1))
    newer = PhysicalInventory.objects.create(
        tenant=tenant_a, warehouse=stocktake_warehouse_a,
        scheduled_date=datetime.date(2026, 8, 20))
    assert str(older) == f"{older.number} · SWH-A"
    rows = list(PhysicalInventory.objects.filter(tenant=tenant_a))
    assert rows[0].pk == newer.pk  # -scheduled_date: the upcoming freeze leads


def test_stocktake_physical_inventory_task_marker_format(stocktake_event_a):
    assert stocktake_event_a.task_marker() == (
        f"Physical inventory {stocktake_event_a.number} #{stocktake_event_a.pk}")


def test_stocktake_physical_inventory_is_editable_only_in_draft(
        tenant_a, admin_user, stocktake_warehouse_a):
    event = PhysicalInventory.objects.create(
        tenant=tenant_a, warehouse=stocktake_warehouse_a,
        scheduled_date=_stocktake_monday())
    assert event.is_editable is True
    assert event.status == "draft"
    event = event.start(admin_user)  # verbs return the re-read row
    assert event.is_editable is False
    event = event.cancel(admin_user)
    assert event.is_editable is False


# ------------------------------------------------------------------ PhysicalInventory — start()


def test_stocktake_start_freezes_and_spawns_one_full_sheet_per_bin_zone(
        admin_user, stocktake_zone_a, stocktake_bin_a,
        stocktake_event_counting_a):
    event = stocktake_event_counting_a
    event.refresh_from_db()
    assert event.status == "counting"
    assert event.is_frozen is True
    assert event.started_at is not None
    sheets = list(event.spawned_tasks())
    assert len(sheets) == 2  # SZ-A + SA-01: every spawnable location under SWH-A
    assert {sheet.location.code for sheet in sheets} == {"SZ-A", "SA-01"}
    today = timezone.localdate()
    for sheet in sheets:
        assert sheet.status == "scheduled"
        assert sheet.count_method == "full"
        assert sheet.scheduled_date == today
        assert sheet.notes == event.task_marker()
        assert sheet.number.startswith("CC-")


def test_stocktake_start_refuses_when_not_draft(
        admin_user, stocktake_event_counting_a):
    with pytest.raises(ValidationError):  # already counting
        stocktake_event_counting_a.start(admin_user)
    stocktake_event_counting_a.refresh_from_db()
    assert stocktake_event_counting_a.status == "counting"
    stocktake_event_counting_a.cancel(admin_user)
    with pytest.raises(ValidationError):  # cancelled too
        stocktake_event_counting_a.start(admin_user)


def test_stocktake_start_skips_locations_already_covered_by_own_marker(
        tenant_a, admin_user, stocktake_event_a, stocktake_zone_a, stocktake_bin_a):
    _stocktake_sheet(tenant_a, stocktake_zone_a,
                     notes=stocktake_event_a.task_marker())
    event = stocktake_event_a.start(admin_user)
    sheets = event.spawned_tasks()
    assert sheets.count() == 2  # the pre-existing SZ-A sheet adopted, only SA-01 minted
    assert set(sheets.values_list("location__code", flat=True)) == {"SZ-A", "SA-01"}
    assert sheets.filter(location=stocktake_zone_a).count() == 1


# ------------------------------------------------------------------ PhysicalInventory — reconcile()


def test_stocktake_reconcile_refuses_while_any_sheet_open_and_names_it(
        tenant_a, admin_user, stocktake_zone_a, stocktake_bin_a,
        stocktake_event_counting_a):
    event = stocktake_event_counting_a
    sheets = list(event.spawned_tasks().order_by("number"))
    sheets[0].status = "counted"  # one done, one still open
    sheets[0].save(update_fields=["status"])
    with pytest.raises(ValidationError) as err:
        event.reconcile(admin_user)
    assert "still open" in str(err.value)
    assert sheets[1].number in str(err.value)  # the message names the blocking sheet
    event.refresh_from_db()
    assert event.status == "counting"
    assert event.is_frozen is True


def test_stocktake_reconcile_succeeds_once_every_sheet_reconciled_or_cancelled(
        admin_user, stocktake_zone_a, stocktake_bin_a,
        stocktake_event_counting_a):
    event = stocktake_event_counting_a
    done, dropped = list(event.spawned_tasks().order_by("id"))
    done.status = "reconciled"
    done.save(update_fields=["status"])
    dropped.status = "cancelled"  # cancellation is an acceptable close-out
    dropped.save(update_fields=["status"])
    closed = event.reconcile(admin_user)
    assert closed.status == "reconciled"
    assert closed.is_frozen is False
    assert closed.closed_at is not None


def test_stocktake_reconcile_refuses_from_non_counting_status(
        tenant_a, admin_user, stocktake_event_a):
    with pytest.raises(ValidationError):  # still draft
        stocktake_event_a.reconcile(admin_user)
    stocktake_event_a.refresh_from_db()
    assert stocktake_event_a.status == "draft"


# ------------------------------------------------------------------ PhysicalInventory — cancel()


def test_stocktake_cancel_from_draft(tenant_a, admin_user, stocktake_event_a):
    cancelled = stocktake_event_a.cancel(admin_user)
    assert cancelled.status == "cancelled"
    assert cancelled.is_frozen is False
    assert cancelled.closed_at is not None


def test_stocktake_cancel_from_counting_lifts_freeze(
        admin_user, stocktake_zone_a, stocktake_bin_a,
        stocktake_event_counting_a):
    cancelled = stocktake_event_counting_a.cancel(admin_user)
    assert cancelled.status == "cancelled"
    assert cancelled.is_frozen is False
    assert cancelled.closed_at is not None


def test_stocktake_cancel_refused_from_reconciled(
        tenant_a, admin_user, stocktake_event_counting_a):
    event = stocktake_event_counting_a
    for sheet in event.spawned_tasks():
        sheet.status = "reconciled"
        sheet.save(update_fields=["status"])
    event.reconcile(admin_user)
    with pytest.raises(ValidationError):
        event.cancel(admin_user)
    event.refresh_from_db()
    assert event.status == "reconciled"


# ------------------------------------------------------------------ coverage & spawned_tasks


def test_stocktake_coverage_none_then_tuple_math(
        tenant_a, admin_user, stocktake_zone_a, stocktake_bin_a,
        stocktake_event_a, stocktake_event_counting_a):
    assert stocktake_event_a.coverage is None  # nothing spawned yet
    event = stocktake_event_counting_a
    assert event.coverage == (0, 2)
    sheets = list(event.spawned_tasks())
    sheets[0].status = "reconciled"
    sheets[0].save(update_fields=["status"])
    assert event.coverage == (1, 2)  # cancelled sheets stay in total, not in done
    sheets[1].status = "cancelled"
    sheets[1].save(update_fields=["status"])
    assert event.coverage == (1, 2)


def test_stocktake_spawned_tasks_match_only_own_pk_marker(
        tenant_a, admin_user, stocktake_warehouse_a, stocktake_zone_a,
        stocktake_bin_a, stocktake_event_counting_a):
    # A sibling event over the SAME warehouse shares the whole "Physical inventory PHY-…"
    # prefix shape — only the exact "{number} #{pk}" stamp may match.
    sibling = PhysicalInventory.objects.create(
        tenant=tenant_a, warehouse=stocktake_warehouse_a,
        scheduled_date=_stocktake_monday())
    foreign_sheet = _stocktake_sheet(tenant_a, stocktake_zone_a,
                                     notes=sibling.task_marker())
    mine = set(stocktake_event_counting_a.spawned_tasks())
    theirs = set(sibling.spawned_tasks())
    assert len(mine) == 2
    assert foreign_sheet not in mine
    assert theirs == {foreign_sheet}


def test_stocktake_tenant_scoping_excludes_foreign_rows(
        tenant_a, stocktake_program_a, stocktake_event_a,
        stocktake_program_b, stocktake_event_b):
    assert stocktake_program_b not in CountProgram.objects.filter(tenant=tenant_a)
    assert stocktake_event_b not in PhysicalInventory.objects.filter(tenant=tenant_a)
    assert stocktake_program_a in CountProgram.objects.filter(tenant=tenant_a)
    assert stocktake_event_a in PhysicalInventory.objects.filter(tenant=tenant_a)


# ------------------------------------------------------------------ PROTECT guards


def test_stocktake_protect_location_and_warehouse_deletes(
        tenant_a, stocktake_program_a, stocktake_event_a):
    with pytest.raises(ProtectedError):
        stocktake_program_a.location.delete()
    with pytest.raises(ProtectedError):
        stocktake_event_a.warehouse.delete()
