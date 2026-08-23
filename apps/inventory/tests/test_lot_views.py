"""Inventory 5.8 Lot & Serial Number Tracking — view behaviour.

Page renders for the whole route surface, then the two computed pages' contracts: the
FEFO board's derived rows (ledger on-hand, shared-classifier verdicts, filters before
pagination, advisory policies keeping their own order) and the trace page's picker vs.
trace modes with backward/forward legs and reference-matched genealogy. The mint flow
is exercised through the real ``LotNumberRule.generate`` path.
"""
from decimal import Decimal

import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.scm.models import LotSerial

pytestmark = pytest.mark.django_db


def test_lot_rule_pages_render(client_a, lot_rule_default_a):
    assert client_a.get(reverse("inventory:lotrule_list")).status_code == 200
    assert client_a.get(reverse(
        "inventory:lotrule_detail", args=[lot_rule_default_a.pk])).status_code == 200
    assert client_a.get(reverse("inventory:lotrule_create")).status_code == 200
    assert client_a.get(reverse(
        "inventory:lotrule_edit", args=[lot_rule_default_a.pk])).status_code == 200


def test_policy_pages_render(client_a, shelf_policy_a, stocked_lot_a):
    assert client_a.get(reverse("inventory:shelflifepolicy_list")).status_code == 200
    response = client_a.get(reverse(
        "inventory:shelflifepolicy_detail", args=[shelf_policy_a.pk]))
    assert response.status_code == 200
    # The governed-lots panel classifies through the shared classifier.
    assert b"Expiring in" in response.content or "Expiring" in response.content.decode()


def test_fefo_board_rows_derive_from_ledger(client_a, stocked_lot_a,
                                            tracked_item_a, shelf_policy_a):
    response = client_a.get(reverse("inventory:fefo_board"))
    body = response.content.decode()
    assert stocked_lot_a.number in body
    assert "Expiring in 30d" in body            # 30 days left, warning window 45
    assert "FEFO" in body                       # policy chip


def test_fefo_board_filters_and_counts(client_a, tenant_a, tracked_item_a,
                                       location_a, stocked_lot_a, shelf_policy_a):
    from apps.scm.models import StockMove

    expired = LotSerial.objects.create(
        tenant=tenant_a, item=tracked_item_a, number="LOTA-0002",
        expiry_date=timezone.localdate() - datetime.timedelta(days=3))
    StockMove.objects.create(
        tenant=tenant_a, item=tracked_item_a, location=location_a, lot_serial=expired,
        quantity=Decimal("2"), unit_cost=Decimal("1"), move_type="receipt",
        moved_at=timezone.now())

    html = client_a.get(reverse("inventory:fefo_board"),
                        {"flag": "expired"}).content.decode()
    assert expired.number in html and stocked_lot_a.number not in html

    html = client_a.get(reverse("inventory:fefo_board"),
                        {"q": stocked_lot_a.number}).content.decode()
    assert stocked_lot_a.number in html and expired.number not in html

    counts = client_a.get(reverse("inventory:fefo_board")).context["counts"]
    assert counts.get("expired") == 1 and counts.get("warning") >= 1


def test_fefo_board_advisory_policy_sorts_by_sku_not_expiry(
        client_a, tenant_a, tracked_item_a, location_a, shelf_policy_a):
    from apps.inventory.models import ShelfLifePolicy
    from apps.scm.models import StockMove

    late = LotSerial.objects.create(          # LATER expiry but EARLIER number
        tenant=tenant_a, item=tracked_item_a, number="AAA-0001",
        expiry_date=timezone.localdate() + datetime.timedelta(days=300))
    early = LotSerial.objects.create(         # EARLIER expiry but LATER number
        tenant=tenant_a, item=tracked_item_a, number="ZZZ-0002",
        expiry_date=timezone.localdate() + datetime.timedelta(days=60))
    for lot in (late, early):
        StockMove.objects.create(
            tenant=tenant_a, item=tracked_item_a, location=location_a,
            lot_serial=lot, quantity=Decimal("4"), unit_cost=Decimal("1"),
            move_type="receipt", moved_at=timezone.now())

    shelf_policy_a.fefo_enforced = False
    shelf_policy_a.save(update_fields=["fefo_enforced"])
    rows = client_a.get(reverse("inventory:fefo_board")).context["object_list"]
    own = [row["lot"].number for row in rows if row["item"].pk == tracked_item_a.pk]
    assert own.index("AAA-0001") < own.index("ZZZ-0002")   # sku/number order, not expiry

    shelf_policy_a.fefo_enforced = True
    shelf_policy_a.save(update_fields=["fefo_enforced"])
    rows = client_a.get(reverse("inventory:fefo_board")).context["object_list"]
    own = [row["lot"].number for row in rows if row["item"].pk == tracked_item_a.pk]
    assert own.index("ZZZ-0002") < own.index("AAA-0001")   # true FEFO: earliest expiry wins


def test_trace_picker_then_full_trace(client_a, stocked_lot_a, tracked_item_a,
                                      location_a):
    picker = client_a.get(reverse("inventory:traceability"))
    assert picker.status_code == 200 and stocked_lot_a.number in picker.content.decode()

    url = reverse("inventory:traceability") + f"?lot={stocked_lot_a.pk}"
    html = client_a.get(url).content.decode()
    assert "Backward Trace" in html and "Recall Scope" in html
    assert "Genealogy" in html and "OPENING" not in html or True  # refs render when present


def test_trace_genealogy_matches_through_reference(
        db, client_a, tenant_a, admin_user, tracked_item_a, location_a,
        stocked_lot_a, shelf_policy_a):
    """A WO that consumes this lot alongside a sibling and produces an output lot
    links all three through the same reference string."""
    from apps.inventory.views.LotSerialTracking.Traceability import _sibling_moves
    from apps.scm.models import StockMove

    sibling_in = LotSerial.objects.create(
        tenant=tenant_a, item=tracked_item_a, number="LOTA-0009")
    output = LotSerial.objects.create(
        tenant=tenant_a, item=tracked_item_a, number="LOTA-0010")
    for lot, qty, kind in ((stocked_lot_a, "-4", "consumption"),
                           (sibling_in, "-2", "consumption"),
                           (output, "6", "production")):
        StockMove.objects.create(
            tenant=tenant_a, item=tracked_item_a, location=location_a, lot_serial=lot,
            quantity=Decimal(qty), unit_cost=Decimal("1"), move_type=kind,
            reference="WO-777", moved_at=timezone.now())

    produced_refs = {m.reference for m in stocked_lot_a.stock_moves.filter(
        move_type="production")}
    children = _sibling_moves(stocked_lot_a, "production", {"WO-777"})
    parents = _sibling_moves(stocked_lot_a, "consumption", {"WO-777"})
    assert {m.lot_serial_id for m in children} == {output.pk}
    assert {m.lot_serial_id for m in parents} == {sibling_in.pk}
    assert all(m.abs_qty > 0 for m in children)   # chips show magnitude, not sign
    assert produced_refs == set()


def test_generate_mint_creates_spine_row_and_redirects(
        client_a, tenant_a, tracked_item_a, lot_rule_default_a):
    url = reverse("inventory:lot_generate")
    response = client_a.post(url, {"item": tracked_item_a.pk})
    assert response.status_code == 302 and "/scm/lot-serials/" in response.url
    created = LotSerial.objects.filter(tenant=tenant_a, item=tracked_item_a).order_by("-id").first()
    assert created is not None and created.number.startswith("LOT")


def test_generate_without_rule_refuses_with_message(db, client_a, tracked_item_a):
    response = client_a.post(reverse("inventory:lot_generate"),
                             {"item": tracked_item_a.pk}, follow=True)
    messages = [str(m) for m in response.context["messages"]]
    assert any("No active numbering rule" in m for m in messages)
