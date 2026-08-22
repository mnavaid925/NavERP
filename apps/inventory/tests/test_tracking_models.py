"""Inventory 5.6 Inventory Tracking & Control — model invariants.

The tracking layer's whole contract lives at the model boundary: a classification claim
(``StockStatus``) that draws its ceiling from the append-only ``scm.StockMove`` ledger via
``spot_moves()``/``spot_on_hand()``, an ATP lock (``InventoryReservation``) with a per-tenant
RSV- sequence and PROTECTed FKs, cross-workspace guards in ``clean()`` on BOTH models, and
the reservation lifecycle state machine whose ``_advance()`` refuses every transition the
ACTIONABLE set doesn't allow — including same-state re-fires of release/consume/cancel.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.utils import timezone

from apps.inventory.models import InventoryReservation, StockStatus

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers


def _tracking_seed(tenant, item, location, quantity, *, lot=None, move_type="receipt"):
    """Post ONE move into the append-only ledger — signed quantity is the physical truth."""
    from apps.scm.models import StockMove

    return StockMove.objects.create(
        tenant=tenant, item=item, location=location, lot_serial=lot,
        quantity=Decimal(quantity), unit_cost=Decimal("0"),
        move_type=move_type, moved_at=timezone.now())


def _tracking_lot(tenant, item, number="LOT-TRK-1"):
    from apps.scm.models import LotSerial

    return LotSerial.objects.create(tenant=tenant, item=item, number=number)


def _tracking_audit_rows(obj):
    from django.contrib.contenttypes.models import ContentType

    from apps.core.models import AuditLog
    return AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)), object_id=obj.pk)


@pytest.fixture
def trk_bin_a(db, tenant_a):
    """A stock spot on the SCM spine, tenant_a."""
    from apps.scm.models import Location

    return Location.objects.create(tenant=tenant_a, code="TRK-BIN-A", name="Tracking bin A")


@pytest.fixture
def trk_bin_b(db, tenant_b):
    """Same role in ANOTHER workspace — the foreign FK target for guard tests."""
    from apps.scm.models import Location

    return Location.objects.create(tenant=tenant_b, code="TRK-BIN-B", name="Globex tracking bin")


# ------------------------------------------------------------------ StockStatus


def test_tracking_stock_status_str_shape(tenant_a, item_a, trk_bin_a):
    row = StockStatus.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a,
        status="damaged", quantity=Decimal("3"))
    text = str(row)
    assert text.startswith("CAT-1 @ TRK-BIN-A · ")
    assert "Damaged" in text
    assert "×3" in text


def test_tracking_stock_status_choices_and_sellability(tenant_a, item_a, trk_bin_a):
    assert [value for value, _label in StockStatus.STATUS_CHOICES] == [
        "active", "damaged", "expired", "on_hold"]
    for status, expected in [("active", True), ("damaged", False),
                             ("expired", False), ("on_hold", False)]:
        row = StockStatus(
            tenant=tenant_a, item=item_a, location=trk_bin_a,
            status=status, quantity=Decimal("1"))
        assert row.is_sellable is expected, status


def test_tracking_stock_status_css_covers_every_status():
    mapping = {"active": "badge-green", "damaged": "badge-red",
               "expired": "badge-amber", "on_hold": "badge-info"}
    for status, _label in StockStatus.STATUS_CHOICES:
        row = StockStatus(status=status)
        assert row.status_css == mapping[status], status


def test_tracking_spot_moves_whole_location_pool_without_lot(tenant_a, item_a, trk_bin_a):
    _tracking_seed(tenant_a, item_a, trk_bin_a, "10")
    _tracking_seed(tenant_a, item_a, trk_bin_a, "-4", move_type="issue")
    claim = StockStatus.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a,
        status="damaged", quantity=Decimal("2"))
    # No lot named -> the whole (item, location) pool is in scope, moves of any type.
    assert claim.spot_moves().count() == 2


def test_tracking_spot_moves_narrows_by_lot_when_set(tenant_a, item_a, trk_bin_a):
    _tracking_seed(tenant_a, item_a, trk_bin_a, "10")  # unlotted receipt stays OUT of scope
    lot = _tracking_lot(tenant_a, item_a)
    _tracking_seed(tenant_a, item_a, trk_bin_a, "6", lot=lot)
    claim = StockStatus.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, lot_serial=lot,
        status="on_hold", quantity=Decimal("2"))
    moves = claim.spot_moves()
    assert moves.count() == 1
    assert all(move.lot_serial_id == lot.pk for move in moves)


def test_tracking_spot_on_hand_sums_signed_moves(tenant_a, item_a, trk_bin_a):
    claim = StockStatus.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a,
        status="damaged", quantity=Decimal("2"))
    _tracking_seed(tenant_a, item_a, trk_bin_a, "10")
    assert claim.spot_on_hand() == Decimal("10")
    _tracking_seed(tenant_a, item_a, trk_bin_a, "-4", move_type="issue")
    assert claim.spot_on_hand() == Decimal("6")


def test_tracking_stock_status_clean_rejects_foreign_item(tenant_a, item_b, trk_bin_a):
    claim = StockStatus(tenant=tenant_a, item=item_b, location=trk_bin_a, quantity=Decimal("1"))
    with pytest.raises(ValidationError) as err:
        claim.clean()
    assert "item" in err.value.message_dict


def test_tracking_stock_status_clean_rejects_foreign_location(tenant_a, item_a, trk_bin_b):
    claim = StockStatus(tenant=tenant_a, item=item_a, location=trk_bin_b, quantity=Decimal("1"))
    with pytest.raises(ValidationError) as err:
        claim.clean()
    assert "location" in err.value.message_dict


def test_tracking_stock_status_clean_rejects_foreign_lot(tenant_a, item_a, trk_bin_a, item_b):
    foreign_lot = _tracking_lot(item_b.tenant, item_b)
    claim = StockStatus(
        tenant=tenant_a, item=item_a, location=trk_bin_a, lot_serial=foreign_lot,
        quantity=Decimal("1"))
    with pytest.raises(ValidationError) as err:
        claim.clean()
    assert "lot_serial" in err.value.message_dict


def test_tracking_stock_status_clean_rejects_lot_of_other_item(tenant_a, item_a, trk_bin_a):
    from apps.scm.models import Item

    sibling = Item.objects.create(tenant=tenant_a, sku="CAT-9", name="Other stock item")
    wrong_lot = _tracking_lot(tenant_a, sibling)
    claim = StockStatus(
        tenant=tenant_a, item=item_a, location=trk_bin_a, lot_serial=wrong_lot,
        quantity=Decimal("1"))
    with pytest.raises(ValidationError) as err:
        claim.clean()
    assert "lot_serial" in err.value.message_dict


# ------------------------------------------------------------------ InventoryReservation


def test_tracking_reservation_numbers_sequential_and_per_tenant(
        tenant_a, tenant_b, item_a, item_b, trk_bin_a, trk_bin_b):
    first = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    second = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    assert first.number == "RSV-00001"
    assert second.number == "RSV-00002"
    # A second workspace's sequence starts at one — numbers never share across tenants.
    other = InventoryReservation.objects.create(
        tenant=tenant_b, item=item_b, location=trk_bin_b, quantity=Decimal("1"))
    assert other.number == "RSV-00001"


def test_tracking_reservation_number_unique_per_tenant(tenant_a, item_a, trk_bin_a):
    InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"),
        number="RSV-04200")
    with pytest.raises(IntegrityError):
        InventoryReservation.objects.create(
            tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"),
            number="RSV-04200")


def test_tracking_reservation_active_and_editable_flags(tenant_a, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    assert row.is_active is True   # reserved
    assert row.is_editable is True
    row.status = "released"
    assert row.is_active is True   # still holding availability back until goods move
    assert row.is_editable is False
    row.status = "consumed"
    assert row.is_active is False
    row.status = "cancelled"
    assert row.is_active is False


def test_tracking_reservation_css_mapping():
    mapping = {"reserved": "badge-info", "released": "badge-amber",
               "consumed": "badge-green", "cancelled": "badge-slate"}
    for status, _label in InventoryReservation.STATUS_CHOICES:
        row = InventoryReservation(status=status)
        assert row.status_css == mapping[status], status


def test_tracking_reservation_protect_item_and_location_deletes(
        tenant_a, admin_user, item_a, trk_bin_a):
    InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"),
        reserved_by=admin_user)
    with pytest.raises(ProtectedError):
        item_a.delete()
    with pytest.raises(ProtectedError):
        trk_bin_a.delete()


def test_tracking_reservation_reserved_by_survives_user_deletion(
        tenant_a, admin_user, member_user, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"),
        reserved_by=admin_user)
    admin_user.delete()
    row.refresh_from_db()
    assert row.reserved_by is None  # SET_NULL — the lock outlives whoever raised it


def test_tracking_reservation_clean_rejects_foreign_item(tenant_a, item_b, trk_bin_a):
    row = InventoryReservation(
        tenant=tenant_a, item=item_b, location=trk_bin_a, quantity=Decimal("1"))
    with pytest.raises(ValidationError) as err:
        row.clean()
    assert "item" in err.value.message_dict


def test_tracking_reservation_clean_rejects_foreign_location(tenant_a, item_a, trk_bin_b):
    row = InventoryReservation(
        tenant=tenant_a, item=item_a, location=trk_bin_b, quantity=Decimal("1"))
    with pytest.raises(ValidationError) as err:
        row.clean()
    assert "location" in err.value.message_dict


def test_tracking_reservation_clean_rejects_foreign_lot(tenant_a, item_a, trk_bin_a, item_b):
    foreign_lot = _tracking_lot(item_b.tenant, item_b)
    row = InventoryReservation(
        tenant=tenant_a, item=item_a, location=trk_bin_a, lot_serial=foreign_lot,
        quantity=Decimal("1"))
    with pytest.raises(ValidationError) as err:
        row.clean()
    assert "lot_serial" in err.value.message_dict


def test_tracking_reservation_clean_rejects_lot_of_other_item(tenant_a, item_a, trk_bin_a):
    from apps.scm.models import Item

    sibling = Item.objects.create(tenant=tenant_a, sku="CAT-8", name="Sibling stock item")
    wrong_lot = _tracking_lot(tenant_a, sibling)
    row = InventoryReservation(
        tenant=tenant_a, item=item_a, location=trk_bin_a, lot_serial=wrong_lot,
        quantity=Decimal("1"))
    with pytest.raises(ValidationError) as err:
        row.clean()
    assert "lot_serial" in err.value.message_dict


# ------------------------------------------------------------------ lifecycle state machine


def test_tracking_lifecycle_release_then_consume_stamps_resolved_at(
        tenant_a, admin_user, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    released = row.release(admin_user)
    assert released.status == "released"
    assert released.resolved_at is None  # handed to the floor, still counting as allocated
    consumed = row.consume(admin_user)
    assert consumed.status == "consumed"
    assert consumed.resolved_at is not None  # the goods left — the claim closed


def test_tracking_lifecycle_cancel_from_reserved(
        tenant_a, admin_user, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    cancelled = row.cancel(admin_user)
    assert cancelled.status == "cancelled"
    assert cancelled.resolved_at is not None


def test_tracking_lifecycle_consume_directly_from_reserved(
        tenant_a, admin_user, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    consumed = row.consume(admin_user)
    assert consumed.status == "consumed"
    assert consumed.resolved_at is not None


def test_tracking_lifecycle_release_twice_refused(
        tenant_a, admin_user, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    row.release(admin_user)
    with pytest.raises(ValidationError):
        row.release(admin_user)
    row.refresh_from_db()
    assert row.status == "released"


def test_tracking_lifecycle_consume_twice_refused(
        tenant_a, admin_user, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    row.consume(admin_user)
    with pytest.raises(ValidationError):
        row.consume(admin_user)
    row.refresh_from_db()
    assert row.status == "consumed"


def test_tracking_lifecycle_consume_after_cancel_refused(
        tenant_a, admin_user, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    row.cancel(admin_user)
    with pytest.raises(ValidationError):
        row.consume(admin_user)
    row.refresh_from_db()
    assert row.status == "cancelled"


def test_tracking_lifecycle_release_after_consume_refused(
        tenant_a, admin_user, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    row.consume(admin_user)
    with pytest.raises(ValidationError):
        row.release(admin_user)
    row.refresh_from_db()
    assert row.status == "consumed"


def test_tracking_lifecycle_cancel_twice_refused(
        tenant_a, admin_user, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    row.cancel(admin_user)
    with pytest.raises(ValidationError):
        row.cancel(admin_user)
    row.refresh_from_db()
    assert row.status == "cancelled"


def test_tracking_lifecycle_actions_write_audit_log(
        tenant_a, admin_user, item_a, trk_bin_a):
    row = InventoryReservation.objects.create(
        tenant=tenant_a, item=item_a, location=trk_bin_a, quantity=Decimal("1"))
    before = _tracking_audit_rows(row).count()

    actions = [row.release(admin_user), row.consume(admin_user)]
    rows = _tracking_audit_rows(row)
    assert rows.count() == before + len(actions)
    assert list(rows.order_by("id").values_list("action", flat=True)) == ["released", "consumed"]
