"""Inventory 5.11 Stocktaking & Cycle Counting — model invariants.

CountProgram cadence/due logic and spine-sheet minting with provenance markers;
PhysicalInventory's verb-driven lifecycle under FOR UPDATE, the reconcile guard
that refuses to lift a freeze while spawned sheets are open, and cross-tenant
clean() rejections.
"""
from decimal import Decimal

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.inventory.models import CountProgram, PhysicalInventory

pytestmark = pytest.mark.django_db


def _tree(tenant):
    from apps.scm.models import Location
    wh, _ = Location.objects.get_or_create(
        tenant=tenant, code="STK-WH", defaults={"name": "Stocktake WH",
                                                "location_type": "warehouse"})
    zone, _ = Location.objects.get_or_create(
        tenant=tenant, code="STK-ZA", defaults={"name": "Zone A",
                                                "location_type": "zone", "parent": wh})
    return wh, zone


def _program(tenant, location=None, **kw):
    from apps.scm.models import Location
    if location is None:
        wh, zone = _tree(tenant)
        location = zone
    return CountProgram.objects.create(
        tenant=tenant, name="Weekly A", location=location, frequency="weekly",
        weekday=0, count_method="zone", **kw)


def _event(tenant, user=None, **kw):
    wh, zone = _tree(tenant)
    from apps.scm.models import Location
    Location.objects.get_or_create(
        tenant=tenant, code="STK-B1",
        defaults={"name": "Bin B1", "location_type": "bin", "parent": zone})
    ev = PhysicalInventory(tenant=tenant, warehouse=wh,
                           scheduled_date=timezone.localdate(),
                           requested_by=user, **kw)
    ev.save()
    return ev


# ---------------------------------------------------------------- CountProgram

def test_program_prefix_and_cadence_label(db, tenant_a):
    prog = _program(tenant_a)
    assert prog.number.startswith("CTP-")
    assert prog.cadence_label == "Every Monday"


def test_program_is_due_respects_frequency_and_lastrun(tenant_a):
    monday = timezone.localdate() - datetime.timedelta(
        days=timezone.localdate().weekday())
    prog = _program(tenant_a)
    assert prog.is_due(monday) is True
    prog.last_run_date = monday
    assert prog.is_due(monday) is False
    prog.is_active = False
    assert prog.is_due(monday) is False


def test_program_weekly_requires_weekday(tenant_a):
    wh, _ = _tree(tenant_a)
    prog = CountProgram(tenant=tenant_a, name="Broken", location=wh,
                        frequency="weekly")
    with pytest.raises(ValidationError):
        prog.full_clean()


def test_program_generate_mints_marked_sheet_once(tenant_a, admin_user):
    prog = _program(tenant_a)
    today = timezone.localdate()
    task, created = prog.generate_tasks(admin_user, today)
    assert created is True and task.number.startswith("CC-")
    assert task.notes.startswith(f"Via count program {prog.number}")
    again, created2 = prog.generate_tasks(admin_user, today)
    assert created2 is False and again.pk == task.pk   # same-day reuse
    assert CountProgram.objects.get(pk=prog.pk).last_run_date == today


def test_program_generate_requires_scope(db, tenant_a, admin_user):
    from apps.scm.models import Location
    wh, _ = _tree(tenant_a)
    prog = CountProgram.objects.create(
        tenant=tenant_a, name="No scope", frequency="daily")
    with pytest.raises(ValidationError):
        prog.generate_tasks(admin_user)


def test_program_foreign_location_rejected(tenant_a, tenant_b):
    from apps.scm.models import Location
    foreign = Location.objects.create(tenant=tenant_b, code="STK-FRN",
                                      name="Foreign", location_type="zone")
    prog = CountProgram(tenant=tenant_a, name="X", location=foreign, frequency="daily")
    with pytest.raises(ValidationError):
        prog.full_clean()


# ---------------------------------------------------------------- PhysicalInventory

def test_event_start_freezes_and_spawns_one_sheet_per_bin(tenant_a, admin_user):
    ev = _event(tenant_a)
    ev.start(admin_user)
    fresh = PhysicalInventory.objects.get(pk=ev.pk)
    assert fresh.status == "counting" and fresh.is_frozen is True
    sheets = list(fresh.spawned_tasks())
    assert len(sheets) >= 2                      # STK-ZA + any other child sections
    assert all(s.count_method == "full" for s in sheets)


def test_event_start_twice_refused(tenant_a, admin_user):
    from django.core.exceptions import ValidationError as VE
    ev = _event(tenant_a)
    ev.start(admin_user)
    with pytest.raises(VE):
        ev.start(admin_user)


def test_event_reconcile_refused_while_sheets_open_then_ok(tenant_a, admin_user):
    from apps.scm.models import CycleCountTask
    ev = _event(tenant_a)
    ev.start(admin_user)
    with pytest.raises(ValidationError):
        ev.reconcile(admin_user)                 # freeze cannot hide uncounted bins
    CycleCountTask.objects.filter(
        notes__startswith=ev.task_marker(ev.number)).update(status="reconciled")
    ev.reconcile(admin_user)
    fresh = PhysicalInventory.objects.get(pk=ev.pk)
    assert fresh.status == "reconciled" and fresh.is_frozen is False


def test_event_cancel_lifts_freeze_from_counting(tenant_a, admin_user):
    ev = _event(tenant_a)
    ev.start(admin_user)
    ev.cancel(admin_user)
    fresh = PhysicalInventory.objects.get(pk=ev.pk)
    assert fresh.status == "cancelled" and fresh.is_frozen is False


def test_event_coverage_none_without_sheets(db, tenant_a):
    ev = _event(tenant_a)
    assert ev.coverage is None


def test_event_foreign_warehouse_rejected(tenant_a, tenant_b):
    from apps.scm.models import Location
    foreign = Location.objects.create(tenant=tenant_b, code="STK-FWH",
                                      name="Foreign WH", location_type="warehouse")
    ev = PhysicalInventory(tenant=tenant_a, warehouse=foreign,
                           scheduled_date=timezone.localdate())
    with pytest.raises(ValidationError):
        ev.full_clean()
