"""Cross-cutting private helpers for the scm views package.

Helpers used by MORE THAN ONE sub-module/entity live here; anything used by a single entity stays in
that entity's own view module (mirrors apps/accounting/views/_helpers.py).
"""
from apps.scm.views._common import *  # noqa: F401,F403

# Defined once in the forms toolkit and re-exported here rather than duplicated: the buy-from-party
# rule (accept BOTH the `supplier` and `vendor` PartyRole spellings) is a single decision, and two
# copies would drift the day one of them is changed. Views legitimately depend on forms.
from apps.scm.forms._common import _supplier_parties  # noqa: F401


def _need_tenant(request):
    """True (and flashes) when the user has no tenant workspace.

    The superuser has ``tenant=None`` by design and every scm view filters by tenant, so creating a
    record as that user would silently produce an orphan row. Callers redirect on True.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return True
    return False


# ---------------------------------------------------------------------------------------------
# 4.3 Inventory — the StockMove posting service.
#
# Every stock movement in the module goes through here so on-hand stays a pure aggregate of an
# append-only ledger. Used by StockTransfer.complete and StockAdjustment.post today, and the
# documented future hook for 4.1's GoodsReceiptNote.mark_received. Callers MUST already be inside a
# transaction.atomic() block (the actions are) — these helpers create rows but do not open their own
# transaction, so a partial multi-line post rolls back with its parent.
# ---------------------------------------------------------------------------------------------
ZERO = Decimal("0")


def _post_stock_move(tenant, *, item, location, quantity, move_type, unit_cost=ZERO,
                     lot_serial=None, reference="", reason="", moved_at=None):
    """Append one StockMove with a SIGNED quantity (+ into / − out of the location).

    For an inbound move (positive quantity of a receipt/adjustment) the item's cached weighted-average
    cost is rolled forward FIRST — against the pre-move on-hand — then the move is written, so the
    average reflects the layer just added without the new quantity skewing its own weighting.
    """
    from apps.scm.models import StockMove
    quantity = quantity or ZERO
    if quantity > ZERO and unit_cost:
        item.apply_receipt(quantity, unit_cost)
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location, lot_serial=lot_serial,
        quantity=quantity, unit_cost=unit_cost or ZERO, move_type=move_type,
        reference=reference or "", reason=reason or "",
        moved_at=moved_at or timezone.now(),
    )


def _insufficient_stock(item, location, quantity, lot_serial=None):
    """Return the shortfall message when ``location`` can't cover an outbound ``quantity``, else ''.

    On-hand is the live StockMove aggregate, so this reflects any moves already posted in the same
    transaction (a multi-line transfer that over-draws the same item across lines is caught).
    """
    available = item.on_hand(location=location)
    if lot_serial is not None:
        available = lot_serial.on_hand()
    if quantity > available:
        where = lot_serial.number if lot_serial is not None else location.code
        return f"{item.sku}: only {available} available at {where}, cannot move {quantity}."
    return ""


def _post_transfer(transfer, user, moved_at=None):
    """Post a completed transfer as a −/+ StockMove pair per line (source out, destination in).

    Guards each line against the source's current on-hand, accounting for earlier lines in the same
    transfer. Cost carries at the item's average cost so a transfer is value-neutral. Assumes an
    enclosing transaction.atomic().
    """
    moved_at = moved_at or timezone.now()
    for line in transfer.lines.select_related("item", "lot_serial"):
        shortfall = _insufficient_stock(line.item, transfer.from_location, line.quantity, line.lot_serial)
        if shortfall:
            raise ValidationError(shortfall)
        cost = line.item.average_cost or ZERO
        _post_stock_move(transfer.tenant, item=line.item, location=transfer.from_location,
                         quantity=-line.quantity, move_type="transfer", unit_cost=cost,
                         lot_serial=line.lot_serial, reference=transfer.number,
                         reason="Transfer out", moved_at=moved_at)
        _post_stock_move(transfer.tenant, item=line.item, location=transfer.to_location,
                         quantity=line.quantity, move_type="transfer", unit_cost=cost,
                         lot_serial=line.lot_serial, reference=transfer.number,
                         reason="Transfer in", moved_at=moved_at)


def _post_adjustment(adjustment, user, moved_at=None):
    """Post an adjustment as one StockMove per line (signed quantity_delta). Atomic assumed.

    A negative delta that would drive on-hand below zero is refused — you cannot write off stock you
    do not have.
    """
    moved_at = moved_at or timezone.now()
    for line in adjustment.lines.select_related("item", "lot_serial"):
        if line.quantity_delta < ZERO:
            shortfall = _insufficient_stock(line.item, adjustment.location, -line.quantity_delta,
                                            line.lot_serial)
            if shortfall:
                raise ValidationError(shortfall)
        _post_stock_move(adjustment.tenant, item=line.item, location=adjustment.location,
                         quantity=line.quantity_delta, move_type="adjustment",
                         unit_cost=line.unit_cost or (line.item.average_cost or ZERO),
                         lot_serial=line.lot_serial, reference=adjustment.number,
                         reason=adjustment.get_reason_display(), moved_at=moved_at)
