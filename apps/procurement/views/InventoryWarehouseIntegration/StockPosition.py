"""Procurement 6.18 Inventory & Warehouse Integration — the Stock Position board.

**Stock Level Visibility** bullet. One read-only page answering the buyer's question, which is not
quite the warehouse's: *for this item at this location, what do I physically have, what is already
spoken for, what is on its way, when does it land, and from whom?*

**Nothing here is stored.** There is no model, no form, no migration and no write of any kind —
every column is a live grouped aggregate over data owned elsewhere (L36). A row appears and
disappears purely as the underlying ledger, orders and rules move.

What makes this different from ``inventory:stocklevels``, which shows the same four warehouse
columns: the **expected date, vendor and PO number of the earliest inbound order**, the
**open-requisition** column, **days of cover**, and the **reorder point** the replenishment run
actually triggers on — i.e. the supply side. Stock levels answer "what is in the building";
this page answers "and is anything coming".

Discipline a reviewer will otherwise go looking for:

* **The availability formula is reused VERBATIM**, not re-derived:
  ``available = on_hand − (SO allocations + reservations) − non-sellable``
  (``apps/inventory/views/InventoryTrackingControl/StockLevels.py:124``). There is exactly one
  definition of available in this codebase and this page does not add a second. It is deliberately
  NOT clamped at zero — a negative figure means the workspace has promised more than it holds,
  which is precisely what the page exists to surface.
* **Below-point is the RUN's trigger, not a fresh opinion.**
  ``supply = on_hand + on_order + open_requisitions``; below point when ``supply <= reorder_point``
  (``ReplenishmentRun.generate``, ``Runs.py:403-409``, which in turn follows
  ``ReorderRule.is_below_point``). A board that disagreed with the run it links to about whether an
  item is short would be worse than one that is merely opinionated.
* **Every figure is ONE grouped query per source, merged in Python.** The query count is FLAT: it
  does not move when the row count doubles, because there is no aggregate inside the loop. The
  ``_on_order_map`` shape is **two** queries rather than one for the fan-out reason its own
  docstring gives, and it is imported from this sub-module's model module rather than copied a
  third time.
* **Peer apps are not reached into.** ``apps.scm.views._helpers`` and ``apps.inventory.views.*``
  are NOT imported — only their MODELS, which are the public surface. The maps this page needs
  already live in ``apps.procurement.models.InventoryWarehouseIntegration.Runs``.
* **Rows are plain dicts**, because a GROUP BY cannot paginate through the model manager. So the
  GET filters run HERE, before pagination, and **every url is ``reverse()``d in Python** — a
  ``{% url %}`` tag cannot express "only when this row has an inbound order", and a null pk in one
  is a ``NoReverseMatch`` 500 rather than a blank cell.
* ``request.tenant is None`` renders an EMPTY board, never a 500. Junk GET params narrow nothing
  and return 200 (``as_db_int`` refuses non-decimal, over-range and oversized pks alike).
* ``ROW_CAP`` bounds the render and the page SAYS it did, via ``truncated`` — a capped board that
  implied its stats covered the whole workspace would be a lie told quietly.

**The honest limitation is printed on the page, not buried here** — see :data:`SKU_MATCH_NOTE`.
"""
from django.db.models import F, Q, Sum
from django.urls import reverse

from apps.core.crud import as_db_int, paginate
from apps.core.models import Party
from apps.inventory.models import InventoryReservation, StockStatus
from apps.scm.models import (Item, Location, PurchaseOrder, PurchaseOrderLine,
                             ReorderRule, SalesOrderAllocation, StockMove)

from apps.procurement.models._base import ZERO
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it, and a package-level re-export would be a star-import cycle at URLconf import time.
from apps.procurement.models.InventoryWarehouseIntegration.Policies import ReplenishmentPolicy
from apps.procurement.models.InventoryWarehouseIntegration.Runs import (_on_order_map,
                                                                        _open_requisition_map,
                                                                        _pair_map)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE = "procurement/inventorywarehouse/stock_position.html"

#: Hard ceiling on rendered rows, reported to the template as ``row_cap`` alongside ``truncated``
#: so the board states its limit instead of implying the stats cover the whole workspace.
ROW_CAP = 500

#: One page of the board. 25 rather than the crud default of 15 — a buyer scans a position board,
#: they do not read it a screenful at a time.
_PER_PAGE = 25

#: The ``?view=`` vocabulary. Frozen here because the template compares ``selected_view`` against
#: these exact values, and every one of them is a real, actionable slice:
#:
#: * ``below_point`` — the run's own trigger: on-hand PLUS everything inbound still fails to reach
#:   the reorder point.
#: * ``shortage``    — ``available <= 0``: more is promised than is holdable, right now.
#: * ``no_cover``    — below point AND nothing whatsoever on the way (no open PO, no open
#:   requisition). A strict subset of ``below_point``, and the only slice that is a to-do list:
#:   these are the rows where somebody has to raise a requisition today.
#:
#: ``no_cover`` deliberately does NOT mean "days_of_cover is blank". A blank cover figure means
#: the item has no measured demand rate, which is not a problem — flagging it would bury the rows
#: that are.
VIEW_CHOICES = [
    ("below_point", "Below reorder point"),
    ("shortage", "In shortage (available ≤ 0)"),
    ("no_cover", "Below point with nothing on the way"),
]
_VIEW_VALUES = {value for value, _label in VIEW_CHOICES}

#: The limitation this page must state out loud rather than paper over. Verbatim on the page.
SKU_MATCH_NOTE = (
    "On-order and open-requisition figures join to an item by EXACT-STRING SKU match: the spine's "
    "purchase-order and requisition lines carry free-text item descriptions and a sku_hint, not an "
    "item foreign key, so there is no other join available. A line whose sku_hint is blank, "
    "misspelled or cased differently is NOT counted here, and it is not guessed at either — a "
    "fuzzy match would attach somebody else's inbound order to the wrong item, which is worse than "
    "a figure that is visibly incomplete. These columns are therefore a floor, not a total. The "
    "real fix is a spine migration giving those lines an item FK; it is not a 6.18 change."
)


def _supplier_parties(tenant):
    """Parties this tenant can buy from — the supplier-OR-vendor role rule shared across 6.x."""
    if tenant is None:
        return Party.objects.none()
    return (Party.objects
            .filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct()
            .order_by("name"))


def _inbound_po_map(tenant):
    """``{sku: {date, vendor, number, po_id}}`` for the EARLIEST inbound order per SKU. ONE query.

    "Earliest" is by ``expected_date`` ascending, and a NULL expected date sorts LAST: an order
    with no promised date is real supply but it cannot be the answer to "when does it land" while
    a dated one exists. Rows are folded with ``setdefault``, so the first row per SKU in that order
    wins — no per-SKU subquery, no aggregate inside a loop.

    Scoped to ``RECEIVABLE_STATUSES``, the same population :func:`_on_order_map` sums, so the
    quantity column and the date column can never describe different sets of orders.

    **A receivable status is not the same as an outstanding quantity**, though, and the caller
    closes that gap: a purchase order can still be ``approved`` after every line on it has been
    received, and showing it as "expected" would promise a delivery that already happened. The
    merge therefore attaches this block only where ``on_order`` is greater than zero, so the
    Expected column and the On-order column always describe the same stock.

    Same exact-string ``sku_hint`` join as every other supply figure on this page — see
    :data:`SKU_MATCH_NOTE`.
    """
    if tenant is None:
        return {}
    rows = (PurchaseOrderLine.objects
            .filter(purchase_order__tenant=tenant,
                    purchase_order__status__in=PurchaseOrder.RECEIVABLE_STATUSES)
            .exclude(sku_hint="")
            .values("sku_hint",
                    po_id=F("purchase_order_id"),
                    po_number=F("purchase_order__number"),
                    po_date=F("purchase_order__expected_date"),
                    po_vendor=F("purchase_order__vendor__name"))
            .order_by(F("purchase_order__expected_date").asc(nulls_last=True),
                      "purchase_order__number"))
    earliest = {}
    for row in rows:
        earliest.setdefault(row["sku_hint"], {
            "date": row["po_date"],
            "vendor": row["po_vendor"] or "",
            "number": row["po_number"],
            "po_id": row["po_id"],
        })
    return earliest


def _reorder_rule_map(tenant):
    """``{(item_id, location_id): (reorder_point, avg_daily_demand)}``. ONE query, values only.

    Only the two numbers this board renders are projected — pulling whole ``ReorderRule``
    instances would drag 20 unused columns per row through the merge for no gain.
    """
    if tenant is None:
        return {}
    rows = (ReorderRule.objects
            .filter(tenant=tenant, is_active=True)
            .values("item_id", "location_id", "reorder_point", "avg_daily_demand"))
    return {(row["item_id"], row["location_id"]):
            (row["reorder_point"] or ZERO, row["avg_daily_demand"] or ZERO)
            for row in rows}


def _days_of_cover(available, avg_daily_demand):
    """Days the AVAILABLE figure lasts at the measured demand rate, or ``None``.

    ``None`` means "unmeasurable" (no demand rate on the rule), NOT "zero days" — the template
    prints a dash for it rather than an alarming 0. Negative availability is reported as 0 days
    rather than a negative duration, which would read as time travel.
    """
    if not avg_daily_demand or avg_daily_demand <= ZERO:
        return None
    if available <= ZERO:
        return ZERO
    return available / avg_daily_demand


@login_required
def stock_position(request):
    """Item × location position with the supply side attached. Derived on read, stored nowhere."""
    tenant = request.tenant
    q = (request.GET.get("q") or "").strip()
    item_id = as_db_int(request.GET.get("item"))
    location_id = as_db_int(request.GET.get("location"))
    vendor_id = as_db_int(request.GET.get("vendor"))
    selected_view = (request.GET.get("view") or "").strip()
    if selected_view not in _VIEW_VALUES:
        selected_view = ""

    items = Item.objects.none()
    locations = Location.objects.none()
    vendors = Party.objects.none()
    rows, truncated = [], False

    if tenant is not None:
        # --- the sources, each ONE grouped query (the on-order map is two, on purpose) ----------
        # Narrow the ledger IN THE DATABASE wherever the filter names a real column: item,
        # location and the text search are all real columns on the join, so pushing them down
        # reads fewer rows rather than reading them all and discarding in Python. The `view`
        # filter is derived and cannot be pushed — it runs after the merge.
        moves = StockMove.objects.filter(tenant=tenant)
        if q:
            moves = moves.filter(Q(item__sku__icontains=q) | Q(item__name__icontains=q))
        if item_id is not None:
            moves = moves.filter(item_id=item_id)
        if location_id is not None:
            moves = moves.filter(location_id=location_id)
        combos = list(moves
                      .values("item_id", "location_id", "item__sku")
                      .annotate(on_hand=Sum("quantity"))
                      .order_by("item__sku", "location__code", "item_id", "location_id"))

        allocations = _pair_map(
            SalesOrderAllocation.objects
            .filter(status__in=SalesOrderAllocation.ACTIVE_STATUSES,
                    sales_order_line__sales_order__tenant=tenant)
            # The item sits on the ORDER LINE and both field names collide with the model's own
            # columns, so both halves of the pair key are aliased (StockLevels.py:93-97).
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
        on_order = _on_order_map(tenant)               # TWO queries — see its docstring
        open_requisitions = _open_requisition_map(tenant)
        inbound = _inbound_po_map(tenant)
        rules = _reorder_rule_map(tenant)

        item_map = {obj.pk: obj for obj in
                    Item.objects.filter(tenant=tenant).select_related("uom")}
        location_map = {obj.pk: obj for obj in Location.objects.filter(tenant=tenant)}
        # ONE query for every policy that could govern any row on this board.
        policies = ReplenishmentPolicy.resolve_map(
            tenant, [(combo["item_id"], combo["location_id"]) for combo in combos])

        items = sorted(item_map.values(), key=lambda obj: obj.sku)
        locations = sorted(location_map.values(), key=lambda obj: obj.code)
        vendors = _supplier_parties(tenant)

        # `raise_requisition_url` is the same target on every row, so it is reversed ONCE here
        # rather than 500 times inside the loop.
        requisition_url = reverse("scm:requisition_create")

        # --- merge (pure Python; not one query lives inside this loop) --------------------------
        for combo in combos:
            key = (combo["item_id"], combo["location_id"])
            sku = combo["item__sku"] or ""
            on_hand = combo["on_hand"] or ZERO
            allocated = allocations.get(key, ZERO) + reservations.get(key, ZERO)
            held = unsellable.get(key, ZERO)
            # THE one availability formula (StockLevels.py:124). Not clamped — see the docstring.
            available = on_hand - allocated - held

            ordered = on_order.get(sku, ZERO)
            requested = open_requisitions.get(sku, ZERO)
            reorder_point, avg_daily_demand = rules.get(key, (None, ZERO))
            # The RUN's trigger, verbatim (Runs.py:403-409): on-hand plus everything inbound,
            # against the point. A board that disagreed with the run it links to would be worse
            # than one that is merely opinionated.
            below_point = (reorder_point is not None
                           and (on_hand + ordered + requested) <= reorder_point)

            # The Expected block describes the OUTSTANDING quantity, so it is attached only when
            # there is one. A purchase order can sit in a receivable status long after every line
            # on it was received; naming it here would promise a delivery that already arrived.
            supply = inbound.get(sku) if ordered > ZERO else None
            policy = policies.get(key)
            rows.append({
                "item": item_map.get(combo["item_id"]),
                "location": location_map.get(combo["location_id"]),
                "on_hand": on_hand,
                "allocated": allocated,
                "held": held,
                "available": available,
                "on_order": ordered,
                "expected_date": supply["date"] if supply else None,
                "expected_vendor": supply["vendor"] if supply else "",
                "expected_po_number": supply["number"] if supply else "",
                "expected_po_url": (reverse("scm:purchaseorder_detail", args=[supply["po_id"]])
                                    if supply else ""),
                "open_requisition_qty": requested,
                "reorder_point": reorder_point,
                "avg_daily_demand": avg_daily_demand,
                "days_of_cover": _days_of_cover(available, avg_daily_demand),
                "below_point": below_point,
                "policy_vendor": policy.preferred_vendor if policy is not None
                and policy.preferred_vendor_id else None,
                "raise_requisition_url": requisition_url,
            })

        # The supplier filter is a PREFERRED-VENDOR filter: it is the only vendor a position row
        # owns of its own (the inbound PO's vendor belongs to that order, not to the row). Applied
        # after the merge because the policy that carries it is resolved after the merge.
        if vendor_id is not None:
            rows = [row for row in rows
                    if row["policy_vendor"] is not None and row["policy_vendor"].pk == vendor_id]

    # --- stats are computed over the FILTERED-but-unsliced population -----------------------------
    # (i.e. after q/item/location/vendor, before the `view` slice) so the three view tabs can show
    # how many rows each of them would hold. That is what makes them navigable rather than blind.
    stats = {
        "rows": len(rows),
        "below_point": sum(1 for row in rows if row["below_point"]),
        "shortage": sum(1 for row in rows if row["available"] <= ZERO),
        "no_cover": sum(1 for row in rows if row["below_point"]
                        and not row["on_order"] and not row["open_requisition_qty"]),
    }

    if selected_view == "below_point":
        rows = [row for row in rows if row["below_point"]]
    elif selected_view == "shortage":
        rows = [row for row in rows if row["available"] <= ZERO]
    elif selected_view == "no_cover":
        rows = [row for row in rows if row["below_point"]
                and not row["on_order"] and not row["open_requisition_qty"]]

    if len(rows) > ROW_CAP:
        rows = rows[:ROW_CAP]
        truncated = True

    page_obj = paginate(request, rows, per_page=_PER_PAGE)
    return render(request, TEMPLATE, {
        "page_obj": page_obj,
        "object_list": page_obj.object_list,
        "q": q,
        "items": items,
        "locations": locations,
        "vendors": vendors,
        "view_choices": VIEW_CHOICES,
        "selected_view": selected_view,
        "stats": stats,
        "row_cap": ROW_CAP,
        "truncated": truncated,
        "sku_match_note": SKU_MATCH_NOTE,
    })
