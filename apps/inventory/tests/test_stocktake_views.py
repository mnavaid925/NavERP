"""Inventory 5.11 Stocktaking & Cycle Counting — view + security behaviour.

Pages render for the whole route surface, the run verb mints/reuses a marked spine
sheet and stamps last_run_date, reconcile refusal keeps the freeze, variance report
derives rows from counted sheets only, deletes are POST-only and drafts-only, and
every foreign-workspace route 404s.
"""
from decimal import Decimal

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import CountProgram, PhysicalInventory
from apps.scm.models import CycleCountTask

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


def _program(tenant, **kw):
    wh, zone = _tree(tenant)
    return CountProgram.objects.create(
        tenant=tenant, name="Weekly A", location=zone, frequency="weekly",
        weekday=0, count_method="zone", **kw)


def _event(tenant, status="draft", **kw):
    wh, _ = _tree(tenant)
    ev = PhysicalInventory(tenant=tenant, warehouse=wh,
                           scheduled_date=timezone.localdate(), **kw)
    ev.save()
    if status != "draft":
        marker = ev.task_marker()
        CycleCountTask.objects.create(tenant=tenant, location=wh,
                                      scheduled_date=timezone.localdate(),
                                      count_method="full", notes=marker)
        PhysicalInventory.objects.filter(pk=ev.pk).update(status=status)
        ev.refresh_from_db()
    return ev


def test_program_pages_render(client_a, tenant_a):
    prog = _program(tenant_a)
    assert client_a.get(reverse("inventory:countprogram_list")).status_code == 200
    assert client_a.get(reverse("inventory:countprogram_detail",
                                args=[prog.pk])).status_code == 200
    assert client_a.get(reverse("inventory:countprogram_create")).status_code == 200


def test_run_verb_mints_and_stamps(client_a, tenant_a):
    prog = _program(tenant_a)
    r = client_a.post(reverse("inventory:countprogram_run", args=[prog.pk]))
    assert r.status_code == 302 and "/scm/cycle-counts/" in r.url
    fresh = CountProgram.objects.get(pk=prog.pk)
    assert fresh.last_run_date == timezone.localdate()
    assert CycleCountTask.objects.filter(
        notes__startswith=f"Via count program {fresh.number}").exists()


def test_physical_pages_render_with_coverage(client_a, tenant_a):
    ev = _event(tenant_a, status="counting")
    response = client_a.get(reverse("inventory:physicalinventory_detail",
                                    args=[ev.pk]))
    body = response.content.decode()
    assert "/1 reconciled" in body or "0/1 reconciled" in body
    assert "CC-" in body
    assert client_a.get(reverse("inventory:physicalinventory_list")).status_code == 200


def test_reconcile_refusal_keeps_freeze(client_a, tenant_a):
    ev = _event(tenant_a, status="counting")
    client_a.post(reverse("inventory:physicalinventory_reconcile", args=[ev.pk]))
    assert PhysicalInventory.objects.get(pk=ev.pk).status == "counting"


def test_variance_report_rows_from_counted_sheets(client_a, tenant_a):
    wh, zone = _tree(tenant_a)
    from apps.scm.models import CycleCountTaskLine, Item
    item = Item.objects.create(tenant=tenant_a, sku="STK-1", name="Counted thing")
    task = CycleCountTask.objects.create(
        tenant=tenant_a, location=zone, scheduled_date=timezone.localdate(),
        count_method="full", status="counted")
    CycleCountTaskLine.objects.create(cycle_count=task, item=item)
    response = client_a.get(reverse("inventory:variance_report"))
    assert response.status_code == 200
    body = response.content.decode()
    assert task.number in body and "clean" in body


def test_delete_is_post_only_and_drafts_only(client_a, tenant_a):
    ev = _event(tenant_a)
    url = reverse("inventory:physicalinventory_delete", args=[ev.pk])
    assert client_a.get(url).status_code in (403, 405)
    live = _event(tenant_a, status="counting")
    assert client_a.post(reverse("inventory:physicalinventory_delete",
                                 args=[live.pk])).status_code == 302
    assert PhysicalInventory.objects.filter(pk=live.pk).exists()   # guarded


def test_foreign_routes_404(client_a, tenant_b):
    prog_b = _program(tenant_b)
    ev_b = _event(tenant_b, status="counting")
    assert client_a.get(reverse("inventory:countprogram_edit",
                                args=[prog_b.pk])).status_code == 404
    assert client_a.post(reverse("inventory:physicalinventory_start",
                                 args=[ev_b.pk])).status_code == 404
    assert client_a.post(reverse("inventory:physicalinventory_cancel",
                                 args=[ev_b.pk])).status_code == 404


def test_login_required(client, tenant_a):
    prog = _program(tenant_a)
    response = client.get(reverse("inventory:countprogram_list"))
    assert response.status_code in (302, 403)
