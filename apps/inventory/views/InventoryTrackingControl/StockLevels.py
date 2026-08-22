"""Inventory 5.6 Inventory Tracking & Control — Real-Time Stock Levels page.

**Real-Time Stock Levels** bullet: On-Hand, Allocated, Available and On-Order per
item × location. Declares NO table — every column is a live aggregate over data owned
elsewhere (L36): on-hand from SCM 4.3's append-only ``StockMove`` ledger, allocated
from 4.5's ``SalesOrderAllocation`` claims PLUS this sub-module's reservations,
non-sellable from this sub-module's ``StockStatus`` classifications, and on-order
from 4.1's open purchase-order lines.

Every figure is ONE grouped query per source, merged in Python — never a per-row
aggregate inside the loop, which would be an N+1 over the whole warehouse (perf rule).
Rows are plain dicts by the time they reach the paginator (a GROUP BY cannot paginate
through the model manager), so the GET filters run here too, BEFORE pagination.

Scope note: a row exists where stock HAS moved. An item with open orders but an empty
ledger has no level to track yet — replenishment reads 4.7's reorder alerts for that.

The availability formula (identical to the one the reservation form enforces at spot
level — keep the two in step):

    available = on_hand − Σ active claims − Σ non-sellable classifications

It is deliberately NOT clamped at zero: a negative figure means the workspace has
promised more than it can physically ship, which is precisely what this page exists
to surface.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import F, Sum

from apps.core.crud import paginate
from apps.inventory.models import InventoryReservation, StockStatus
from apps.inventory.views._common import *  # noqa: F401,F403
from apps.scm.models import (GoodsReceiptLine, Item, Location, PurchaseOrder,
                             PurchaseOrderLine, SalesOrderAllocation, StockMove)


def _on_order_map(tenant):
    """{sku: outstanding} across every RECEIVABLE purchase order, keyed by ``sku_hint``.

    4.1's PO lines predate the item spine (L28): they carry a free-text ``sku_hint``,
    not an FK, so the match is EXACT-STRING against ``Item.sku`` — a fuzzy or
    case-insensitive guess would attach someone else's open order line to the wrong
    SKU. Outstanding = ordered − accepted receipts (cancelled GRNs excluded), floored
    at zero so an over-receipt cannot read as negative demand.

    Ordered and received are TWO grouped queries merged in Python, deliberately not one:
    annotating the line's ``quantity`` alongside child ``receipt_lines__quantity_received``
    joins each receipt row onto its line, and that fan-out multiplies ``ordered`` by the
    receipt count — an order of 10 received as 4+6 would report 10 outstanding instead of 0.
    """
    ordered_rows = (PurchaseOrderLine.objects
                    .filter(purchase_order__tenant=tenant,
                            purchase_order__status__in=PurchaseOrder.RECEIVABLE_STATUSES)
                    .exclude(sku_hint="")
                    .values("sku_hint")
                    .annotate(ordered=Sum("quantity")))
    # Received is scoped to the SAME receivable POs so both halves of the subtraction
    # cover exactly the same order population.
    received_rows = (GoodsReceiptLine.objects
                     .filter(po_line__purchase_order__tenant=tenant,
                             po_line__purchase_order__status__in=PurchaseOrder.RECEIVABLE_STATUSES)
                     .exclude(goods_receipt__status="cancelled")
                     .values(sku=F("po_line__sku_hint"))
                     .annotate(received=Sum("quantity_received")))
    ordered = {row["sku_hint"]: row["ordered"] or 0 for row in ordered_rows}
    received = {row["sku"]: row["received"] or 0 for row in received_rows}
    return {sku: max(qty - received.get(sku, 0), 0) for sku, qty in ordered.items()}


def _pair_map(queryset, item_key="item_id", location_key="location_id"):
    """{(item_id, location_id): Σ quantity} for one claim/classification source.

    Callers project the pair as aliases (the spine allocation reaches its item through
    the order LINE and its own ``location_id`` field name is taken, so it aliases both).
    """
    return {(row[item_key], row[location_key]): row["s"] or 0 for row in queryset}


@login_required
def stocklevels(request):
    tenant = request.tenant
    # --- the four sources, each ONE grouped query -----------------------------------------
    combos = list(
        StockMove.objects.filter(tenant=tenant)
        .values("item_id", "location_id", "item__sku", "item__name",
                "location__code", "location__name")
        .annotate(on_hand=Sum("quantity"))
        .order_by("item__sku", "location__code"))
    allocations = _pair_map(
        SalesOrderAllocation.objects
        .filter(status__in=SalesOrderAllocation.ACTIVE_STATUSES,
                sales_order_line__sales_order__tenant=tenant)
        # The item sits on the ORDER LINE, and both field names collide with the
        # model's own columns — so both halves of the pair key are aliased.
        .values(iid=F("sales_order_line__item_id"), loc=F("location_id"))
        .annotate(s=Sum("quantity")),
        item_key="iid", location_key="loc")
    reservations = _pair_map(
        InventoryReservation.objects
        .filter(tenant=tenant, status__in=InventoryReservation.ACTIVE_STATUSES)
        .values("item_id", "location_id")
        .annotate(s=Sum("quantity")))
    unsellable = _pair_map(
        StockStatus.objects.filter(tenant=tenant).exclude(status="active")
        .values("item_id", "location_id").annotate(s=Sum("quantity")))
    on_order = _on_order_map(tenant)

    # --- merge -------------------------------------------------------------------------------
    items = {i.pk: i for i in Item.objects.filter(tenant=tenant)}
    locations = {loc.pk: loc for loc in Location.objects.filter(tenant=tenant)}
    rows = []
    for combo in combos:
        key = (combo["item_id"], combo["location_id"])
        on_hand = combo["on_hand"] or 0
        allocated = allocations.get(key, 0) + reservations.get(key, 0)
        held = unsellable.get(key, 0)
        rows.append({
            "item": items.get(combo["item_id"]),
            "location": locations.get(combo["location_id"]),
            "on_hand": on_hand,
            "allocated": allocated,
            "held": held,
            # Same formula as the reservation form's ATP check — see module docstring.
            "available": on_hand - allocated - held,
            "on_order": on_order.get(combo["item__sku"], 0),
        })

    # --- filters (parsed BEFORE pagination) ----------------------------------------------------
    q = request.GET.get("q", "").strip()
    if q:
        ql = q.lower()
        rows = [r for r in rows if r["item"] is not None and (
            ql in r["item"].sku.lower() or ql in r["item"].name.lower())]
    item_filter = request.GET.get("item", "").strip()
    if item_filter.isdecimal():
        rows = [r for r in rows if r["item"] is not None and str(r["item"].pk) == item_filter]
    location_filter = request.GET.get("location", "").strip()
    if location_filter.isdecimal():
        rows = [r for r in rows if r["location"] is not None and str(r["location"].pk) == location_filter]
    shortage_only = request.GET.get("view", "").strip() == "shortage"
    if shortage_only:
        rows = [r for r in rows if r["available"] <= 0]

    # The shared crud helper paginates plain lists too; 25 keeps this page's window.
    page_obj = paginate(request, rows, per_page=25)
    return render(request, "inventory/tracking/stocklevels.html", {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "q": q,
        # The filter dropdowns reuse the maps already loaded for the merge (sorted
        # copies) — re-querying Item/Location here was a second fetch of both tables
        # on every request for identical rows.
        "items": sorted(items.values(), key=lambda obj: obj.sku),
        "locations": sorted(locations.values(), key=lambda loc: loc.code),
        "shortage_only": shortage_only,
    })
