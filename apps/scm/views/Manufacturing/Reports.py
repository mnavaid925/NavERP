"""SCM 4.8 Manufacturing — the two computed pages: MRP and the production schedule.

Neither owns a model. MRP nets demand against supply and emits SUGGESTIONS; a human converts each
one into a work order (make) or a purchase requisition (buy). Nothing here writes a document by
itself — the same compute-then-convert contract 4.3's reorder alerts and 4.7's safety-stock
calculator hold to, and for the same reason: a silent auto-PO is a business decision the planner
never made.
"""
from datetime import timedelta

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _item_qs, _location_qs
from apps.scm.models import (BillOfMaterials, Item, ReorderRule, SalesOrderLine, StockMove,
                             WorkCenter, WorkOrder)
from apps.scm.models._base import q2, q4

ZERO = Decimal("0")

#: Planning horizon for the MRP netting pass.
_MRP_HORIZON_DAYS = 90


@login_required
def mrp_report(request):
    """Explode open demand, net it against stock and open supply, suggest make or buy.

    Four passes, each ONE query — never a lookup per item:

    1. **Demand** — open sales-order lines inside the horizon, plus released work orders' remaining
       component requirements.
    2. **Explosion** — every demanded item with an active BOM is exploded to its raw components, so
       the requirement lands on what actually has to be bought or made.
    3. **Supply** — on-hand from the StockMove ledger.
    4. **Netting** — requirement − on-hand, with the make/buy split decided by
       ``manufactured_item_ids`` (one query for the whole tenant, not an EXISTS per row).

    Open purchase orders are deliberately NOT counted as incoming supply: ``PurchaseOrderLine`` has
    no ``item`` FK (4.1 uses free-text lines with a SKU hint), so matching them to an item here
    would be a guess. The page says so rather than quietly overstating supply.
    """
    tenant = request.tenant
    horizon_days = _MRP_HORIZON_DAYS
    try:
        horizon_days = max(1, min(int(request.GET.get("horizon") or _MRP_HORIZON_DAYS), 365))
    except (TypeError, ValueError):
        horizon_days = _MRP_HORIZON_DAYS
    until = timezone.localdate() + timedelta(days=horizon_days)

    location_id = request.GET.get("location") or ""
    requirements = {}   # item_id -> Decimal
    sources = {}        # item_id -> set of source labels

    def _add(item_id, quantity, source):
        if quantity <= ZERO:
            return
        requirements[item_id] = requirements.get(item_id, ZERO) + quantity
        sources.setdefault(item_id, set()).add(source)

    # --- 1. independent demand: open sales-order lines in the horizon ------------------------------
    demand_lines = (SalesOrderLine.objects
                    .filter(sales_order__tenant=tenant,
                            sales_order__order_date__lte=until)
                    .exclude(sales_order__status__in=("draft", "cancelled", "closed"))
                    .select_related("item"))
    for line in demand_lines:
        if line.item_id:
            _add(line.item_id, line.quantity_ordered or ZERO, "Sales orders")

    # --- 2. dependent demand: outstanding components on live runs ----------------------------------
    live_components = (WorkOrder.objects
                       .filter(tenant=tenant, status__in=WorkOrder.OPEN_STATUSES)
                       .values_list("pk", flat=True))
    if live_components:
        from apps.scm.models import WorkOrderComponent
        for component in (WorkOrderComponent.objects
                          .filter(work_order_id__in=list(live_components))
                          .select_related("item")):
            _add(component.item_id, component.quantity_outstanding, "Work orders")

    # --- 3. explode anything that is made, so the requirement lands on the raw materials -----------
    manufactured = BillOfMaterials.manufactured_item_ids(tenant)
    # Resolve every demanded item in ONE query before the explosion loop. Calling
    # Item.objects.get(pk=...) inside the loop would be a query per demanded item — the exact N+1
    # manufactured_item_ids() exists to avoid one line above.
    demanded_items = {item.pk: item for item in
                      Item.objects.filter(tenant=tenant, pk__in=set(requirements))}
    exploded_requirements = {}
    for item_id, quantity in requirements.items():
        # The parent still needs making or buying — keep it either way.
        exploded_requirements[item_id] = exploded_requirements.get(item_id, ZERO) + quantity
        if item_id not in manufactured:
            continue
        bom = BillOfMaterials.active_for(tenant, demanded_items.get(item_id))
        if bom is None:
            continue
        for row in bom.explode(quantity):
            child_id = row["item"].pk
            exploded_requirements[child_id] = exploded_requirements.get(child_id, ZERO) + row["quantity"]
            sources.setdefault(child_id, set()).add(f"BOM {bom.number}")

    # --- 4. supply + netting ----------------------------------------------------------------------
    item_ids = set(exploded_requirements)
    on_hand_qs = StockMove.objects.filter(tenant=tenant, item_id__in=item_ids)
    if location_id.isdigit():
        on_hand_qs = on_hand_qs.filter(location_id=int(location_id))
    on_hand = {row["item_id"]: (row["q"] or ZERO)
               for row in on_hand_qs.values("item_id").annotate(q=Sum("quantity"))}
    items = {item.pk: item for item in Item.objects.filter(tenant=tenant, pk__in=item_ids)
             .select_related("uom", "category")}
    safety = {rule.item_id: (rule.safety_stock or ZERO)
              for rule in ReorderRule.objects.filter(tenant=tenant, item_id__in=item_ids,
                                                     is_active=True)}

    rows = []
    for item_id, required in exploded_requirements.items():
        item = items.get(item_id)
        if item is None:
            continue
        available = on_hand.get(item_id, ZERO)
        buffer_qty = safety.get(item_id, ZERO)
        shortfall = q4(required + buffer_qty - available)
        if shortfall <= ZERO:
            continue
        rows.append({
            "item": item,
            "required": q4(required),
            "safety_stock": q4(buffer_qty),
            "on_hand": q4(available),
            "shortfall": shortfall,
            "action": "make" if item_id in manufactured else "buy",
            "sources": ", ".join(sorted(sources.get(item_id, ()))),
        })
    rows.sort(key=lambda row: row["shortfall"], reverse=True)

    page_obj = paginate(request, rows, per_page=30)
    return render(request, "scm/manufacturing/mrp_report.html", {
        "rows": page_obj.object_list,
        "page_obj": page_obj,
        "horizon_days": horizon_days,
        "until": until,
        "locations": _location_qs(tenant),
        "make_count": sum(1 for row in rows if row["action"] == "make"),
        "buy_count": sum(1 for row in rows if row["action"] == "buy"),
        "total_rows": len(rows),
    })


@login_required
def production_schedule(request):
    """Infinite-capacity load board — planned hours per work centre against effective capacity.

    Infinite-capacity on purpose: it shows WHERE the plan exceeds capacity and by how much, without
    pretending to resolve it. A finite-capacity scheduler that levels and re-sequences across
    centres is a genuine solver and a later pass — showing a fabricated feasible plan would be worse
    than showing an honest overload.
    """
    tenant = request.tenant
    try:
        days = max(1, min(int(request.GET.get("days") or 14), 90))
    except (TypeError, ValueError):
        days = 14
    start = timezone.now()
    end = start + timedelta(days=days)

    centres = list(WorkCenter.objects.filter(tenant=tenant, is_active=True)
                   .select_related("location"))
    orders = (WorkOrder.objects
              .filter(tenant=tenant, status__in=("planned", "released", "in_progress"))
              .select_related("item", "work_center")
              .order_by("planned_start", "-id"))

    rows = []
    for centre in centres:
        scheduled = centre.scheduled_hours(start, end)
        capacity = centre.effective_capacity_hours(days)
        rows.append({
            "centre": centre,
            "scheduled_hours": scheduled,
            "capacity_hours": capacity,
            "load_pct": q2(scheduled / capacity * Decimal("100")) if capacity > ZERO else ZERO,
            "is_overloaded": capacity > ZERO and scheduled > capacity,
        })

    unscheduled = [order for order in orders if order.planned_start is None]
    return render(request, "scm/manufacturing/production_schedule.html", {
        "rows": rows,
        "orders": orders[:60],
        "unscheduled": unscheduled[:20],
        "unscheduled_count": len(unscheduled),
        "days": days,
        "start": start,
        "end": end,
        "overloaded_count": sum(1 for row in rows if row["is_overloaded"]),
    })
