"""Inventory 5.5 Warehousing & Bin Management — model invariants.

``BinCapacity`` is a pure profile over SCM 4.3's location spine: its on-hand and its
utilisation are always DERIVED from the append-only ``StockMove`` ledger, never stored,
and utilisation answers ``None`` when no limit was declared rather than a flattering 0%.
``CrossDockOrder`` is the bypass-storage document whose ``receive`` / ``ship`` / ``cancel``
actions post REAL legs into that same ledger — those actions are tested through their
public entry points so the status guards, the shortfall guard, the compensating -receipt
reversal and the audit trail are all exercised as committed behaviour, not bypassed.
"""
import re
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import DecimalField, Value
from django.utils import timezone

from apps.core.models import AuditLog
from apps.inventory.models import BinCapacity, CrossDockOrder
from apps.scm.models import Item, Location, LotSerial, StockMove

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ module helpers


def _warehousing_item(tenant, sku):
    """A stock item on the SCM spine with a non-zero cost basis."""
    return Item.objects.create(
        tenant=tenant, sku=sku, name=f"Warehouse {sku}",
        item_type="stock", standard_cost=Decimal("8.00"),
    )


def _warehousing_location(tenant, code, location_type="bin"):
    """A location on the SCM spine (bin by default; pass 'staging' for docks)."""
    return Location.objects.create(
        tenant=tenant, code=code, name=f"Area {code}", location_type=location_type,
    )


def _warehousing_lot(tenant, item, number):
    """A lot/batch row for a tracked item."""
    return LotSerial.objects.create(tenant=tenant, item=item, kind="lot", number=number)


def _warehousing_bin(location, **limits):
    """A BinCapacity envelope; the tenant always follows the location's spine row."""
    return BinCapacity.objects.create(tenant_id=location.tenant_id, location=location, **limits)


def _warehousing_move(tenant, item, location, quantity, move_type="receipt",
                      reference="", lot_serial=None, unit_cost="0"):
    """Append one signed StockMove leg directly to the 4.3 ledger."""
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location, lot_serial=lot_serial,
        quantity=Decimal(quantity), unit_cost=Decimal(unit_cost),
        move_type=move_type, reference=reference, reason="test helper",
        moved_at=timezone.now(),
    )


def _warehousing_xd(tenant, item, dock, quantity="10", unit_cost="2.50", lot_serial=None):
    """A draft CrossDockOrder scheduled for today; save() mints its XD- number."""
    return CrossDockOrder.objects.create(
        tenant=tenant, item=item, dock_location=dock, lot_serial=lot_serial,
        quantity=Decimal(quantity), unit_cost=Decimal(unit_cost),
        scheduled_date=timezone.localdate(),
    )


# ------------------------------------------------------------------ BinCapacity


class TestWarehousingBinCapacityModel:
    def test_warehousing_bin_str_lists_every_declared_limit(self, tenant_a):
        bin_row = _warehousing_bin(
            _warehousing_location(tenant_a, "BIN-S1"),
            max_weight_kg=Decimal("500.00"), max_volume_m3=Decimal("2.500"),
            max_quantity=Decimal("250"))
        text = str(bin_row)
        assert text.startswith("BIN-S1 ·")
        assert "kg" in text and "m³" in text and "units" in text

    def test_warehousing_bin_str_without_any_limits(self, tenant_a):
        bin_row = _warehousing_bin(_warehousing_location(tenant_a, "BIN-S2"))
        assert str(bin_row) == "BIN-S2 · no limits set"

    def test_warehousing_bin_one_envelope_per_tenant_location(self, tenant_a):
        """(tenant, location) is a hard constraint — two envelopes would fork the truth."""
        loc = _warehousing_location(tenant_a, "BIN-U1")
        _warehousing_bin(loc, max_quantity=Decimal("10"))
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                _warehousing_bin(loc, max_quantity=Decimal("99"))

    def test_warehousing_bin_clean_rejects_foreign_tenant_location(self, tenant_a, tenant_b):
        foreign = _warehousing_location(tenant_b, "BIN-F9")
        bin_row = BinCapacity(tenant=tenant_a, location=foreign)
        with pytest.raises(ValidationError) as err:
            bin_row.full_clean()
        assert "location" in err.value.message_dict

    def test_warehousing_bin_on_hand_equals_stockmove_sum(self, tenant_a):
        """On-hand is never stored: it is exactly the signed sum of this bin's moves."""
        item = _warehousing_item(tenant_a, "BIN-OH")
        loc = _warehousing_location(tenant_a, "BIN-OH")
        other = _warehousing_location(tenant_a, "BIN-ELSEWHERE")
        bin_row = _warehousing_bin(loc)
        _warehousing_move(tenant_a, item, loc, "40")
        _warehousing_move(tenant_a, item, loc, "-15", move_type="issue")
        # a movement at ANOTHER bin of the same tenant must not leak into this one
        _warehousing_move(tenant_a, item, other, "999")
        assert bin_row.on_hand == Decimal("25")

    def test_warehousing_bin_utilisation_none_when_limit_missing_or_zero(self, tenant_a):
        unlimited = _warehousing_bin(_warehousing_location(tenant_a, "BIN-NOLIM"))
        zero_limit = _warehousing_bin(_warehousing_location(tenant_a, "BIN-ZEROLIM"),
                                      max_quantity=Decimal("0"))
        assert unlimited.utilisation_pct is None
        assert zero_limit.utilisation_pct is None
        assert zero_limit.quantity_utilisation is None

    def test_warehousing_bin_utilisation_correct_and_over_limit_preserved(self, tenant_a):
        """A full bin reads 100%; an OVER-full bin keeps its true >100 figure — no clamp."""
        item = _warehousing_item(tenant_a, "BIN-UT")
        ok_bin = _warehousing_bin(_warehousing_location(tenant_a, "BIN-OK"),
                                  max_quantity=Decimal("200"))
        _warehousing_move(tenant_a, item, ok_bin.location, "30")
        _warehousing_move(tenant_a, item, ok_bin.location, "-5", move_type="issue")
        assert ok_bin.utilisation_pct == Decimal("12.5")
        over_bin = _warehousing_bin(_warehousing_location(tenant_a, "BIN-OVER"),
                                    max_quantity=Decimal("100"))
        _warehousing_move(tenant_a, item, over_bin.location, "150")
        assert over_bin.utilisation_pct == Decimal("150.0")

    def test_warehousing_bin_utilisation_prefers_annotated_on_hand_qty(self, tenant_a):
        """The list view's Subquery wins: an annotated on_hand_qty must be used as-is."""
        item = _warehousing_item(tenant_a, "BIN-AQ")
        loc = _warehousing_location(tenant_a, "BIN-AQ")
        bin_row = _warehousing_bin(loc, max_quantity=Decimal("100"))
        _warehousing_move(tenant_a, item, loc, "25")
        live = BinCapacity.objects.get(pk=bin_row.pk)
        assert live.utilisation_pct == Decimal("25.0")  # fallback re-aggregates
        inflated = (
            BinCapacity.objects.filter(pk=bin_row.pk)
            .annotate(on_hand_qty=Value(Decimal("123456"), output_field=DecimalField(
                max_digits=16, decimal_places=4)))
            .get()
        )
        assert inflated.utilisation_pct == Decimal("123456.0")


# ------------------------------------------------------------------ CrossDockOrder


class TestWarehousingCrossDockOrderModel:
    def test_warehousing_xd_number_auto_assigned_per_tenant(self, tenant_a, tenant_b):
        first = _warehousing_xd(tenant_a, _warehousing_item(tenant_a, "XD-NUM"),
                                _warehousing_location(tenant_a, "DOCK-N1", "staging"))
        second = _warehousing_xd(tenant_a, first.item, first.dock_location)
        assert re.fullmatch(r"XD-\d{5}", first.number)
        assert second.number == "XD-00002"
        # a second workspace's sequence starts at one — numbers never share across tenants
        theirs = _warehousing_xd(tenant_b, _warehousing_item(tenant_b, "XD-NUM"),
                                 _warehousing_location(tenant_b, "DOCK-N2", "staging"))
        assert theirs.number == "XD-00001"

    def test_warehousing_xd_is_editable_only_while_draft(self, tenant_a, admin_user):
        order = _warehousing_xd(tenant_a, _warehousing_item(tenant_a, "XD-ED"),
                                _warehousing_location(tenant_a, "DOCK-E1", "staging"))
        assert order.is_editable is True
        got = order.receive(admin_user)
        assert got.is_editable is False
        shipped = got.ship(admin_user)
        assert shipped.is_editable is False

    def test_warehousing_xd_status_css_covers_all_statuses_with_fallback(self):
        expected = {"draft": "badge-slate", "received": "badge-info",
                    "shipped": "badge-green", "cancelled": "badge-red"}
        order = CrossDockOrder()
        for status, _label in CrossDockOrder.STATUS_CHOICES:
            order.status = status
            assert order.status_css == expected[status]
        order.status = "teleported"
        assert order.status_css == "badge-muted"

    def test_warehousing_xd_str_shows_number_and_sku(self, tenant_a):
        item = _warehousing_item(tenant_a, "XD-STR")
        order = _warehousing_xd(tenant_a, item,
                                _warehousing_location(tenant_a, "DOCK-S1", "staging"),
                                quantity="7")
        text = str(order)
        assert order.number in text and item.sku in text

    def test_warehousing_xd_clean_rejects_foreign_tenant_dock(self, tenant_a, tenant_b):
        order = _warehousing_xd(tenant_a, _warehousing_item(tenant_a, "XD-FD"),
                                _warehousing_location(tenant_a, "DOCK-FD", "staging"))
        order.dock_location = _warehousing_location(tenant_b, "DOCK-FX", "staging")
        with pytest.raises(ValidationError) as err:
            order.full_clean()
        assert "dock_location" in err.value.message_dict

    def test_warehousing_xd_clean_rejects_foreign_tenant_lot(self, tenant_a, tenant_b):
        order = _warehousing_xd(tenant_a, _warehousing_item(tenant_a, "XD-FL"),
                                _warehousing_location(tenant_a, "DOCK-FL", "staging"))
        foreign_lot = _warehousing_lot(tenant_b, _warehousing_item(tenant_b, "XD-FLB"), "LOT-X")
        order.lot_serial = foreign_lot
        with pytest.raises(ValidationError) as err:
            order.full_clean()
        assert "lot_serial" in err.value.message_dict

    def test_warehousing_xd_clean_rejects_lot_of_another_item(self, tenant_a):
        order = _warehousing_xd(tenant_a, _warehousing_item(tenant_a, "XD-LI"),
                                _warehousing_location(tenant_a, "DOCK-LI", "staging"))
        other_lot = _warehousing_lot(tenant_a, _warehousing_item(tenant_a, "XD-LIB"), "LOT-Y")
        order.lot_serial = other_lot
        with pytest.raises(ValidationError) as err:
            order.full_clean()
        assert "lot_serial" in err.value.message_dict

    def test_warehousing_xd_clean_accepts_valid_combination(self, tenant_a):
        item = _warehousing_item(tenant_a, "XD-OK")
        order = _warehousing_xd(tenant_a, item,
                               _warehousing_location(tenant_a, "DOCK-OK", "staging"))
        order.lot_serial = _warehousing_lot(tenant_a, item, "LOT-OK")
        order.full_clean()  # must not raise


class TestWarehousingCrossDockLedger:
    def test_warehousing_xd_receive_posts_one_positive_receipt_leg(self, tenant_a, admin_user):
        item = _warehousing_item(tenant_a, "XD-RC")
        dock = _warehousing_location(tenant_a, "DOCK-R1", "staging")
        order = _warehousing_xd(tenant_a, item, dock, quantity="25", unit_cost="2.50")
        got = order.receive(admin_user)
        assert got.status == "received"
        assert got.received_at is not None
        legs = list(got.ledger_moves())
        assert len(legs) == 1
        leg = legs[0]
        assert leg.move_type == "receipt"
        assert leg.reference == got.number
        assert leg.location_id == dock.pk
        assert leg.quantity == Decimal("25")  # inbound only — nothing negative rolled
        item.refresh_from_db()
        assert item.average_cost == Decimal("2.5")  # the cost layer was rolled forward

    def test_warehousing_xd_receive_twice_raises_and_keeps_single_leg(self, tenant_a, admin_user):
        order = _warehousing_xd(tenant_a, _warehousing_item(tenant_a, "XD-R2"),
                                _warehousing_location(tenant_a, "DOCK-R2", "staging"))
        got = order.receive(admin_user)
        with pytest.raises(ValidationError) as err:
            got.receive(admin_user)
        assert "cannot be received" in " ".join(err.value.messages)
        assert got.ledger_moves().count() == 1

    def test_warehousing_xd_ship_before_receive_raises(self, tenant_a, admin_user):
        order = _warehousing_xd(tenant_a, _warehousing_item(tenant_a, "XD-SH"),
                                _warehousing_location(tenant_a, "DOCK-SH", "staging"))
        with pytest.raises(ValidationError) as err:
            order.ship(admin_user)
        assert "receive it first" in " ".join(err.value.messages)
        assert order.status == "draft"
        assert order.ledger_moves().count() == 0

    def test_warehousing_xd_ship_posts_issue_at_average_cost_netting_zero(self, tenant_a, admin_user):
        item = _warehousing_item(tenant_a, "XD-SI")
        dock = _warehousing_location(tenant_a, "DOCK-SI", "staging")
        order = _warehousing_xd(tenant_a, item, dock, quantity="10", unit_cost="2")
        got = order.receive(admin_user)
        item.refresh_from_db()
        average = item.average_cost
        shipped = got.ship(admin_user)
        assert shipped.status == "shipped"
        assert shipped.shipped_at is not None
        legs = {leg.move_type: leg for leg in shipped.ledger_moves()}
        assert set(legs) == {"receipt", "issue"}
        issue = legs["issue"]
        assert issue.quantity == Decimal("-10")
        assert issue.unit_cost == average  # outbound leg carries the WAC cache
        # both legs posted at the dock: the net position is exactly zero afterwards
        assert item.on_hand(dock) == Decimal("0")

    def test_warehousing_xd_cancel_from_draft_flips_status_without_moves(self, tenant_a, admin_user):
        order = _warehousing_xd(tenant_a, _warehousing_item(tenant_a, "XD-C1"),
                                _warehousing_location(tenant_a, "DOCK-C1", "staging"))
        cancelled = order.cancel(admin_user)
        assert cancelled.status == "cancelled"
        assert cancelled.ledger_moves().count() == 0

    def test_warehousing_xd_cancel_from_received_posts_compensating_leg(self, tenant_a, admin_user):
        """From received, cancel appends a guarded -receipt — the ledger nets to ZERO."""
        item = _warehousing_item(tenant_a, "XD-C2")
        dock = _warehousing_location(tenant_a, "DOCK-C2", "staging")
        order = _warehousing_xd(tenant_a, item, dock, quantity="8", unit_cost="3")
        got = order.receive(admin_user)
        cancelled = got.cancel(admin_user)
        assert cancelled.status == "cancelled"
        legs = list(cancelled.ledger_moves())
        assert len(legs) == 2
        assert sum((leg.quantity for leg in legs), Decimal("0")) == Decimal("0")
        reversal = next(leg for leg in legs if leg.quantity < 0)
        assert reversal.move_type == "receipt"  # a compensating receipt, not a delete
        assert reversal.reason == "Cross-dock cancelled"
        assert item.on_hand(dock) == Decimal("0")

    def test_warehousing_xd_cancel_from_shipped_raises(self, tenant_a, admin_user):
        """Once shipped only a compensating document undoes it — cancel() refuses."""
        order = _warehousing_xd(tenant_a, _warehousing_item(tenant_a, "XD-C3"),
                                _warehousing_location(tenant_a, "DOCK-C3", "staging"))
        shipped = order.receive(admin_user).ship(admin_user)
        with pytest.raises(ValidationError) as err:
            shipped.cancel(admin_user)
        assert "cannot be cancelled" in " ".join(err.value.messages)
        shipped.refresh_from_db()
        assert shipped.status == "shipped"
        assert shipped.ledger_moves().count() == 2

    def test_warehousing_xd_cancel_refused_when_stock_already_left_the_dock(self, tenant_a, admin_user):
        """The compensating -receipt is GUARDED: goods already gone can't be reversed."""
        item = _warehousing_item(tenant_a, "XD-C4")
        dock = _warehousing_location(tenant_a, "DOCK-C4", "staging")
        order = _warehousing_xd(tenant_a, item, dock, quantity="10", unit_cost="1")
        got = order.receive(admin_user)
        # four units left the dock before anyone thought to cancel
        _warehousing_move(tenant_a, item, dock, "-4", move_type="issue")
        with pytest.raises(ValidationError) as err:
            got.cancel(admin_user)
        assert "already moved" in " ".join(err.value.messages)
        got.refresh_from_db()
        assert got.status == "received"


class TestWarehousingCrossDockAuditTrail:
    def test_warehousing_xd_audit_rows_written_for_receive_ship_cancel(self, tenant_a, admin_user):
        ct = ContentType.objects.get_for_model(CrossDockOrder)

        flow = _warehousing_xd(tenant_a, _warehousing_item(tenant_a, "XD-AU"),
                               _warehousing_location(tenant_a, "DOCK-A1", "staging"),
                               quantity="5", unit_cost="1")
        got = flow.receive(admin_user)
        row = AuditLog.objects.get(action="receive", content_type=ct, object_id=flow.pk)
        assert row.user == admin_user and row.tenant == tenant_a
        assert row.changes == {"status": "received"}
        got.ship(admin_user)
        ship_log = AuditLog.objects.filter(content_type=ct, object_id=flow.pk).order_by("id")
        assert [entry.action for entry in ship_log] == ["receive", "ship"]

        paper = _warehousing_xd(tenant_a, got.item, got.dock_location).cancel(admin_user)
        paper_log = AuditLog.objects.filter(action="cancel", content_type=ct,
                                            object_id=paper.pk).get()
        assert paper_log.changes == {"status": "cancelled", "reversed_receipt": False}

        reversal_flow = _warehousing_xd(tenant_a, got.item, got.dock_location,
                                        quantity="2", unit_cost="1")
        reversal_received = reversal_flow.receive(admin_user)
        reversal_done = reversal_received.cancel(admin_user)
        reversal_log = AuditLog.objects.filter(action="cancel", content_type=ct,
                                               object_id=reversal_done.pk).get()
        assert reversal_log.changes["reversed_receipt"] is True
