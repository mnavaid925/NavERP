"""Inventory 5.17 Reporting & Analytics — view behaviour.

The four live report pages (valuation / turnover / aging / ABC) are computed at
request time from the ledger: each renders its title, surfaces a seeded SKU once
moves exist, and its filters narrow the table (not the pickers, not the totals).
Window input is clamped, never trusted. The snapshot CRUD side freezes the SAME
engine's output into an immutable IRS- row — generate redirects to the detail
page carrying the minted number, delete is admin-gated, and both detail and
delete 404 across the tenant fence.
"""
from decimal import Decimal

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.inventory.models import InventoryReportSnapshot

pytestmark = pytest.mark.django_db


def _post_move(tenant, item, location, *, quantity="4", unit_cost="1",
               move_type="receipt", days_ago=0):
    """One append-only StockMove leg, mirroring conftest._post_move's fields."""
    from apps.scm.models import StockMove
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location,
        quantity=Decimal(quantity), unit_cost=Decimal(unit_cost),
        move_type=move_type, reference="", reason="",
        moved_at=timezone.now() - datetime.timedelta(days=days_ago))


def _stocked_item(tenant, sku):
    """A stocked weighted-avg item master; average_cost stays at its default."""
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant, sku=sku, name=f"Report {sku}", standard_cost=Decimal("8.00"))


# ---- live report pages ------------------------------------------------------------------------


def test_report_pages_render_titles_and_seeded_sku(client_a, tenant_a, item_a,
                                                    location_a):
    """Each of the four pages is 200 under its title, and CAT-1 surfaces on every
    one once a receipt leg exists (all four compute from the same ledger)."""
    _post_move(tenant_a, item_a, location_a, quantity="10")

    expected = {
        "report_valuation": "Inventory Valuation Report",
        "report_turnover": "Stock Turnover Ratio",
        "report_aging": "Aging Analysis",
        "report_abc": "ABC Analysis",
    }
    for name, title in expected.items():
        response = client_a.get(reverse(f"inventory:{name}"))
        assert response.status_code == 200
        assert title in response.content.decode()
        assert "CAT-1" in response.content.decode()


def test_valuation_search_nomatch_shows_empty_state(client_a, item_a, location_a):
    _post_move(item_a.tenant, item_a, location_a, quantity="6")
    html = client_a.get(reverse("inventory:report_valuation"),
                        {"q": "NOMATCH"}).content.decode()
    # The empty STATE must render and the TABLE must carry no stock row. The
    # filter dropdown legitimately still lists CAT-1 (pickers stay full-set —
    # review M2), so absence is asserted on the row link, not the page.
    assert "Nothing to value" in html
    assert "/scm/items/%d/" % item_a.pk not in html


def test_turnover_velocity_dead_filter_excludes_the_traded_item(client_a, item_a,
                                                                 location_a):
    """:velocity=dead keeps only no-demand items — the received-and-reissued SKU
    reads fast (its window had customer demand) and must drop out."""
    fast = _stocked_item(item_a.tenant, "TURN-FAST")
    _post_move(item_a.tenant, item_a, location_a, quantity="10")          # dead
    _post_move(item_a.tenant, fast, location_a, quantity="10")
    _post_move(item_a.tenant, fast, location_a, quantity="-4", move_type="issue")

    html = client_a.get(reverse("inventory:report_turnover"),
                        {"velocity": "dead"}).content.decode()
    assert "CAT-1" in html and "TURN-FAST" not in html


def test_aging_health_dead_filter_shows_only_dead_rows(client_a, item_a, location_a):
    """Receipt-only stock never drew → dead; a recently issued spot stays healthy
    and must vanish under ?health=dead."""
    healthy = _stocked_item(item_a.tenant, "AGE-LIVE")
    _post_move(item_a.tenant, item_a, location_a, quantity="8")            # dead
    _post_move(item_a.tenant, healthy, location_a, quantity="8")
    _post_move(item_a.tenant, healthy, location_a, quantity="-2",
               move_type="issue")                                          # fresh draw

    rows = client_a.get(reverse("inventory:report_aging"),
                        {"health": "dead"}).context["object_list"]
    assert [row["item"].sku for row in rows] == ["CAT-1"]


def test_abc_class_filter_keeps_only_a_rows(client_a, item_a, location_a):
    """Two trading SKUs ranked by issued cost: the top one holds exactly 80% of the
    cumulative share → class A; the tail lands in C and filters out."""
    tail = _stocked_item(item_a.tenant, "PARETO-TAIL")
    _post_move(item_a.tenant, item_a, location_a, quantity="100")
    _post_move(item_a.tenant, item_a, location_a, quantity="-80", move_type="issue")
    _post_move(item_a.tenant, tail, location_a, quantity="30")
    _post_move(item_a.tenant, tail, location_a, quantity="-20", move_type="issue")

    rows = client_a.get(reverse("inventory:report_abc"),
                        {"class": "a"}).context["object_list"]
    assert [row["item"].sku for row in rows] == ["CAT-1"]
    assert all(row["abc_class"] == "A" for row in rows)


def test_turnover_window_clamped_not_trusted(client_a, item_a, location_a):
    _post_move(item_a.tenant, item_a, location_a, quantity="3")

    clamped = client_a.get(reverse("inventory:report_turnover"), {"days": "99999"})
    assert clamped.status_code == 200
    assert clamped.context["days"] == 3650              # MAX_WINDOW_DAYS ceiling

    junk = client_a.get(reverse("inventory:report_turnover"), {"days": "junk"})
    assert junk.status_code == 200
    assert junk.context["days"] == 90                   # DEFAULT_WINDOW_DAYS fallback


# ---- snapshots [IRS-] -------------------------------------------------------------------------


def test_snapshot_list_empty_state_then_shows_number(client_a, tenant_a):
    empty = client_a.get(reverse("inventory:snapshot_list"))
    assert empty.status_code == 200
    assert "No snapshots yet" in empty.content.decode()

    snap = InventoryReportSnapshot.objects.create(tenant=tenant_a,
                                                  report_type="valuation")
    listed = client_a.get(reverse("inventory:snapshot_list"))
    assert listed.status_code == 200
    assert snap.number in listed.content.decode()


def test_snapshot_generate_post_freezes_aging_and_redirects_to_detail(
        client_a, admin_user, item_a, location_a):
    _post_move(item_a.tenant, item_a, location_a, quantity="5")

    response = client_a.post(reverse("inventory:snapshot_generate"), data={
        "report_type": "aging", "title": "V", "location": "",
        "window_days": "", "notes": ""})
    assert response.status_code == 302 and "/snapshots/" in response.url

    snap = InventoryReportSnapshot.objects.get(tenant=admin_user.tenant,
                                               report_type="aging")
    assert response.url.endswith(f"/snapshots/{snap.pk}/")
    assert snap.generated_by == admin_user
    assert isinstance(snap.summary, dict) and snap.summary
    assert "total_value" in snap.summary and "dead_spots" in snap.summary

    followed = client_a.get(response.url, follow=True)
    assert followed.status_code == 200
    assert snap.number in followed.content.decode()


def test_snapshot_generate_get_preselects_type_from_querystring(client_a):
    response = client_a.get(reverse("inventory:snapshot_generate"), {"type": "abc"})
    assert response.status_code == 200
    assert response.context["form"].initial["report_type"] == "abc"


def test_snapshot_detail_shows_number_and_freeze_details(client_a, tenant_a):
    snap = InventoryReportSnapshot.objects.create(tenant=tenant_a,
                                                  report_type="turnover")
    html = client_a.get(reverse("inventory:snapshot_detail",
                                args=[snap.pk])).content.decode()
    assert snap.number in html and "Freeze Details" in html


def test_admin_delete_redirects_and_removes_row(client_a, tenant_a):
    snap = InventoryReportSnapshot.objects.create(tenant=tenant_a,
                                                  report_type="valuation")
    response = client_a.post(reverse("inventory:snapshot_delete", args=[snap.pk]))
    assert response.status_code == 302
    assert response.url == reverse("inventory:snapshot_list")
    assert not InventoryReportSnapshot.objects.filter(pk=snap.pk).exists()


def test_member_cannot_delete_but_can_open_generate(member_client, member_user,
                                                    tenant_a):
    """Delete rewrites audit evidence — tenant-admin only (PermissionDenied → 403
    under the test runner); reading the generate form is ordinary staff business."""
    snap = InventoryReportSnapshot.objects.create(tenant=tenant_a,
                                                  report_type="valuation")
    denied = member_client.post(reverse("inventory:snapshot_delete",
                                        args=[snap.pk]))
    assert denied.status_code == 403
    snap.refresh_from_db()                          # raises if deleted

    assert member_client.get(reverse(
        "inventory:snapshot_generate")).status_code == 200


def test_snapshot_detail_and_delete_cross_tenant_404(client_b, tenant_a):
    snap = InventoryReportSnapshot.objects.create(tenant=tenant_a,
                                                  report_type="aging")
    assert client_b.get(reverse(
        "inventory:snapshot_detail", args=[snap.pk])).status_code == 404
    assert client_b.post(reverse(
        "inventory:snapshot_delete", args=[snap.pk])).status_code == 404
    snap.refresh_from_db()                          # foreign delete wrote nothing
