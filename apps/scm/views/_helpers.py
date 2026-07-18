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

    For an inbound move the item's cached weighted-average cost is rolled forward FIRST — against the
    pre-move on-hand — then the move is written, so the average reflects the layer just added without
    the new quantity skewing its own weighting.

    ``unit_cost is not None`` (not a truthiness test): a genuinely FREE receipt (found stock, a
    zero-cost sample) must still dilute the average downward. Treating 0 as "no cost given" would
    silently overstate the item's value (code review).
    """
    from apps.scm.models import StockMove
    quantity = quantity or ZERO
    if quantity > ZERO and unit_cost is not None:
        item.apply_receipt(quantity, unit_cost)
    return StockMove.objects.create(
        tenant=tenant, item=item, location=location, lot_serial=lot_serial,
        quantity=quantity, unit_cost=unit_cost or ZERO, move_type=move_type,
        reference=reference or "", reason=reason or "",
        moved_at=moved_at or timezone.now(),
    )


def _insufficient_stock(item, location, quantity, lot_serial=None):
    """Return the shortfall message when ``location`` can't cover an outbound ``quantity``, else ''.

    Scoped to (item, location) AND — when the line names one — the specific lot/serial. Checking a
    lot's tenant-wide total instead would let a transfer draw a lot out of a location that never held
    it: the tenant-wide figure stays balanced while the source location goes negative and the lot's
    real holding location is never debited (security review). On-hand is the live StockMove aggregate,
    so this also reflects moves already posted by earlier lines in the same transaction.
    """
    qs = item.stock_moves.filter(location=location)
    if lot_serial is not None:
        qs = qs.filter(lot_serial=lot_serial)
    available = qs.aggregate(q=Sum("quantity"))["q"] or ZERO
    if quantity > available:
        where = f"{lot_serial.number} at {location.code}" if lot_serial is not None else location.code
        return f"{item.sku}: only {available} available at {where}, cannot move {quantity}."
    return ""


def _shared_items(lines):
    """One `Item` instance per item_id, shared across every line of a document.

    `select_related("item")` hands back a SEPARATE Item object per line row, so two lines for the
    same item would each read their own stale `average_cost` — the second line's weighted-average
    roll would then overwrite the first's with a figure computed from pre-first-line state, silently
    corrupting the cached cost (code review). Sharing one instance keeps the roll cumulative.
    """
    shared = {}
    for line in lines:
        shared.setdefault(line.item_id, line.item)
    return shared


def _post_transfer(transfer, user, moved_at=None):
    """Post a completed transfer as a −/+ StockMove pair per line (source out, destination in).

    Guards each line against the source's current on-hand, accounting for earlier lines in the same
    transfer. Cost carries at the item's average cost so a transfer is value-neutral at item level.
    Assumes an enclosing transaction.atomic().
    """
    moved_at = moved_at or timezone.now()
    lines = list(transfer.lines.select_related("item", "lot_serial"))
    items = _shared_items(lines)
    for line in lines:
        item = items[line.item_id]
        shortfall = _insufficient_stock(item, transfer.from_location, line.quantity, line.lot_serial)
        if shortfall:
            raise ValidationError(shortfall)
        cost = item.average_cost or ZERO
        _post_stock_move(transfer.tenant, item=item, location=transfer.from_location,
                         quantity=-line.quantity, move_type="transfer", unit_cost=cost,
                         lot_serial=line.lot_serial, reference=transfer.number,
                         reason="Transfer out", moved_at=moved_at)
        _post_stock_move(transfer.tenant, item=item, location=transfer.to_location,
                         quantity=line.quantity, move_type="transfer", unit_cost=cost,
                         lot_serial=line.lot_serial, reference=transfer.number,
                         reason="Transfer in", moved_at=moved_at)


# ---------------------------------------------------------------------------------------------
# 4.1 GoodsReceiptNote -> StockMove (wired in 4.4).
#
# When 4.1 shipped, there was no stock ledger, so booking a receipt only flipped a status and left a
# TODO. 4.3 then shipped StockMove but nothing went back to close the loop — so a receipt said goods
# arrived while on-hand never moved, leaving procure-to-pay and inventory disconnected. 4.4 needs
# received stock to exist before putaway can direct it anywhere, so the wire-up lands here.
#
# Item resolution is BEST-EFFORT by design: 4.1's PO/GRN lines are free text (`sku_hint`) because
# they predate the item master, so a line whose hint matches no Item cannot post a move. Rather than
# fail the whole receipt (breaking existing 4.1 behaviour) or skip silently (hiding the gap), the
# helpers report what they couldn't match so the caller can surface it.
# ---------------------------------------------------------------------------------------------
def _resolve_grn_item(tenant, po_line):
    """Best-effort map a free-text 4.1 purchase-order line onto a 4.3 Item via its ``sku_hint``."""
    from apps.scm.models import Item
    sku = (getattr(po_line, "sku_hint", "") or "").strip()
    if not sku:
        return None
    return Item.objects.filter(tenant=tenant, sku__iexact=sku).first()


def _receiving_location(grn):
    """Where a receipt's goods land: the GRN's own staging location, else the tenant's first
    warehouse. Returns None when the tenant has no location at all (nothing can be posted)."""
    from apps.scm.models import Location
    if grn.location_id:
        return grn.location
    return (Location.objects.filter(tenant=grn.tenant, location_type="warehouse", is_active=True)
            .order_by("code").first()
            or Location.objects.filter(tenant=grn.tenant, is_active=True).order_by("code").first())


def _post_grn_receipt(grn, user, moved_at=None):
    """Post one inbound StockMove per received line. Assumes an enclosing transaction.atomic().

    Returns ``(posted, unmatched)`` — how many moves were written and the descriptions of any lines
    whose free-text SKU matched no Item, so the caller can tell the user rather than fail silently.
    """
    location = _receiving_location(grn)
    if location is None:
        return 0, ["no stock location exists for this workspace"]
    moved_at = moved_at or timezone.now()
    posted, unmatched = 0, []
    for line in grn.lines.select_related("po_line"):
        qty = line.quantity_received or ZERO
        if qty <= ZERO or not line.po_line_id:
            continue
        item = _resolve_grn_item(grn.tenant, line.po_line)
        if item is None:
            unmatched.append(line.po_line.item_description or line.po_line.sku_hint or "a line")
            continue
        # The PO line's agreed price IS the inbound cost layer (the field is `unit_price` on the
        # order line; StockMove calls the same figure `unit_cost`).
        _post_stock_move(grn.tenant, item=item, location=location, quantity=qty,
                         move_type="receipt", unit_cost=line.po_line.unit_price or ZERO,
                         reference=grn.number, reason="Goods receipt", moved_at=moved_at)
        posted += 1
    return posted, unmatched


def _reverse_grn_receipt(grn, user, moved_at=None):
    """Compensate a cancelled receipt by posting the mirror-image negative moves.

    The ledger is append-only, so a cancellation NEVER deletes the original moves — it posts
    offsetting ones, exactly like a journal reversal. Reverses only what the receipt actually
    posted (matched by its reference), so a partially-matched receipt unwinds symmetrically.
    """
    from apps.scm.models import StockMove
    moved_at = moved_at or timezone.now()
    reversed_count = 0
    originals = StockMove.objects.filter(tenant=grn.tenant, reference=grn.number,
                                         move_type="receipt").select_related("item", "location")
    for move in originals:
        if move.quantity <= ZERO:
            continue  # already a reversal — don't reverse the reversal
        _post_stock_move(grn.tenant, item=move.item, location=move.location,
                         quantity=-move.quantity, move_type="receipt",
                         unit_cost=move.unit_cost, lot_serial=move.lot_serial,
                         reference=grn.number, reason="Goods receipt cancelled",
                         moved_at=moved_at)
        reversed_count += 1
    return reversed_count


def _post_adjustment(adjustment, user, moved_at=None):
    """Post an adjustment as one StockMove per line (signed quantity_delta). Atomic assumed.

    A negative delta that would drive on-hand below zero is refused — you cannot write off stock you
    do not have.
    """
    moved_at = moved_at or timezone.now()
    lines = list(adjustment.lines.select_related("item", "lot_serial"))
    items = _shared_items(lines)  # see _shared_items — two lines for one item must roll cumulatively
    for line in lines:
        item = items[line.item_id]
        if line.quantity_delta < ZERO:
            shortfall = _insufficient_stock(item, adjustment.location, -line.quantity_delta,
                                            line.lot_serial)
            if shortfall:
                raise ValidationError(shortfall)
        _post_stock_move(adjustment.tenant, item=item, location=adjustment.location,
                         quantity=line.quantity_delta, move_type="adjustment",
                         unit_cost=line.unit_cost if line.unit_cost else (item.average_cost or ZERO),
                         lot_serial=line.lot_serial, reference=adjustment.number,
                         reason=adjustment.get_reason_display(), moved_at=moved_at)
