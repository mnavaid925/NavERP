"""SCM 4.3 Inventory Management — computed reports (no CRUD models).

Everything here is derived from the append-only StockMove ledger: the inventory dashboard, the
FIFO/LIFO/WAC valuation report, reorder alerts, the stock ledger, and on-hand by location.
"""
from decimal import Decimal

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.models import Item, Location, ReorderRule, StockMove

ZERO = Decimal("0")


# ============================================================================ valuation
def _item_valuation(item, moves):
    """Return (on_hand, value) for one item under its costing_method, from its ``moves`` (chronological).

    - weighted_avg: on_hand × cached average_cost.
    - fifo/lifo: walk the inbound cost layers, consume by total outbound, value the remaining layers
      (fifo consumes oldest first → oldest layers gone; lifo consumes newest first).
    """
    on_hand = sum((m.quantity for m in moves), ZERO)
    if on_hand <= ZERO:
        return on_hand, ZERO
    if item.costing_method == "weighted_avg":
        return on_hand, (on_hand * (item.average_cost or ZERO)).quantize(Decimal("0.01"))

    # Transfers are EXCLUDED from the layer walk. A transfer is an internal relocation posted as a
    # −/+ pair at the item's average cost: it nets to zero for item-level quantity, but if included
    # it would consume a real FIFO layer on the way out and create a fake average-cost layer on the
    # way in — drifting a FIFO/LIFO item toward weighted-average with every transfer (code review).
    # on_hand above still counts them, so the quantity stays correct; only the costing ignores them.
    costed = [m for m in moves if m.move_type != "transfer"]
    layers = [[m.quantity, m.unit_cost or ZERO] for m in costed if m.quantity > ZERO]  # (qty, cost)
    outbound = sum((-m.quantity for m in costed if m.quantity < ZERO), ZERO)
    order = layers if item.costing_method == "fifo" else list(reversed(layers))
    remaining = outbound
    for layer in order:  # consume the outbound quantity from the front (fifo) / back (lifo)
        if remaining <= ZERO:
            break
        take = min(layer[0], remaining)
        layer[0] -= take
        remaining -= take
    value = sum((qty * cost for qty, cost in layers), ZERO)
    return on_hand, value.quantize(Decimal("0.01"))


@login_required
def valuation_report(request):
    """Per-item on-hand and stock value under each item's costing method."""
    items = (Item.objects.filter(tenant=request.tenant, item_type="stock")
             .prefetch_related(models.Prefetch(
                 "stock_moves",
                 queryset=StockMove.objects.order_by("moved_at", "id"))))
    rows, grand_total = [], ZERO
    for item in items:
        on_hand, value = _item_valuation(item, list(item.stock_moves.all()))
        if on_hand or value:
            rows.append({"item": item, "on_hand": on_hand, "value": value,
                         "method": item.get_costing_method_display()})
            grand_total += value
    rows.sort(key=lambda r: r["value"], reverse=True)
    return render(request, "scm/inventory/valuation_report.html", {
        "rows": rows,
        "grand_total": grand_total.quantize(Decimal("0.01")),
    })


# ============================================================================ reorder alerts
@login_required
def reorder_alerts(request):
    """Items at/below their reorder point — with a one-click pre-fill into 4.1 requisition_create."""
    rules = list(ReorderRule.objects.filter(tenant=request.tenant, is_active=True)
                 .select_related("item", "location"))
    # One grouped query for every rule's on-hand, then reuse it for BOTH the threshold test and the
    # suggested quantity — previously each rule cost two separate aggregates (perf review).
    qty_map = ReorderRule.on_hand_map(request.tenant, rules)
    alerts = []
    for rule in rules:
        on_hand = qty_map.get((rule.item_id, rule.location_id), ZERO)
        if on_hand <= rule.reorder_point:
            alerts.append({
                "rule": rule, "on_hand": on_hand,
                "suggested": rule.suggested_quantity(on_hand=on_hand),
                "shortfall": rule.reorder_point - on_hand,
            })
    alerts.sort(key=lambda a: a["shortfall"], reverse=True)
    return render(request, "scm/inventory/reorder_alerts.html", {"alerts": alerts})


# ============================================================================ stock ledger
@login_required
def stock_ledger(request):
    """The raw StockMove ledger, filterable by item and location — the audit trail of every movement."""
    qs = (StockMove.objects.filter(tenant=request.tenant)
          .select_related("item", "location", "lot_serial"))
    return crud_list(
        request, qs, "scm/inventory/stock_ledger.html",
        search_fields=["reference", "item__sku", "item__name", "location__code"],
        filters=[("item", "item_id", True), ("location", "location_id", True),
                 ("move_type", "move_type", False)],
        extra_context={
            "items": Item.objects.filter(tenant=request.tenant),
            "locations": Location.objects.filter(tenant=request.tenant),
            "type_choices": StockMove.MOVE_TYPES,
        },
        # 30 rather than the app-wide 15: this is an append-only audit trail people scan, and it is
        # the highest-volume table in the module.
        per_page=30,
    )


# ============================================================================ on-hand by location
@login_required
def on_hand_by_location(request):
    """A location × item on-hand grid, derived from the ledger in one grouped query."""
    rows = (StockMove.objects.filter(tenant=request.tenant)
            .values("location__code", "location__name", "item__sku", "item__name")
            .annotate(qty=Sum("quantity"),
                      value=Sum(F("quantity") * F("unit_cost"),
                                output_field=models.DecimalField(max_digits=20, decimal_places=4)))
            .order_by("location__code", "item__sku"))
    grouped = {}
    for row in rows:
        if not row["qty"]:
            continue
        loc = row["location__code"] or "—"
        grouped.setdefault(loc, {"name": row["location__name"], "items": []})
        grouped[loc]["items"].append(row)
    return render(request, "scm/inventory/on_hand_by_location.html", {"grouped": grouped})
