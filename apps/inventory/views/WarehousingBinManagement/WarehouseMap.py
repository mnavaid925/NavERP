"""Inventory 5.5 Warehousing & Bin Management — the Warehouse Map (computed page).

**Warehouse Mapping** bullet: a blueprint of each warehouse's layout with how full every
bin actually is. This page DECLARES NO TABLE of its own — a map is a QUERY over the
location spine SCM 4.3 owns plus the capacity profiles and the append-only ledger
(scm 4.15's precedent: when a NavERP bullet is answerable from existing tables, the
honest build is the page, not another copy of the rows).

Everything on it is derived in three queries:

* all tenant locations in one fetch (the tree is walked in Python — a location tree is
  dozens of rows, not thousands);
* ONE group-by over ``StockMove`` giving every location's on-hand quantity AND value,
  so rendering never aggregates per row;
* the ``BinCapacity`` profiles keyed by location.

A malformed self-parent cycle in the location tree cannot hang the page: the walk
carries a seen-set exactly like ``Location.path()`` does, and a residual pass sweeps
any island the two walks missed into the orphans table — the map promises nothing
silently dropped, cycles included.
"""
from decimal import Decimal

from django.db.models import DecimalField, F, Sum

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.models import BinCapacity

#: Guards the Python-side tree walk. A legitimate warehouse hierarchy nests
#: warehouse → zone → aisle → rack → bin = 4 hops; anything deeper than this is bad
#: hand-data, not a real layout, and is shown truncated rather than hung.
_MAX_DEPTH = 8

ZERO = Decimal("0")


@login_required
def warehousemap(request):
    from apps.scm.models import Location, StockMove

    tenant = request.tenant
    locations = list(Location.objects.filter(tenant=tenant)
                     .select_related("parent").order_by("code"))

    # ONE group-by for both figures every row shows. The ledger is the fastest-growing
    # table in the system; per-row aggregates here would make the map O(bins × moves).
    totals = {}
    if locations:
        moves = StockMove.objects.filter(
            tenant=tenant, location_id__in=[loc.pk for loc in locations])
        for row in moves.values("location_id").annotate(
                qty=Sum("quantity"),
                value=Sum(F("quantity") * F("unit_cost"),
                          output_field=DecimalField(max_digits=20, decimal_places=4))):
            totals[row["location_id"]] = row

    capacities = {bc.location_id: bc for bc in BinCapacity.objects.filter(tenant=tenant)
                  .select_related("location")}

    children = {}
    for loc in locations:
        children.setdefault(loc.parent_id, []).append(loc)

    def _row(loc, depth):
        total = totals.get(loc.pk) or {}
        profile = capacities.get(loc.pk)
        on_hand = total.get("qty") or ZERO
        return {
            "loc": loc,
            "depth": depth,
            # Pre-computed: Django templates can't multiply, so the row carries its own
            # indent in px (14px per level reads clearly without swallowing wide codes).
            "indent": depth * 14,
            "on_hand": on_hand,
            "value": (total.get("value") or ZERO).quantize(Decimal("0.01")),
            "profile": profile,
            # Raw ratio quantized to one decimal, computed HERE where both operands are
            # real Decimals — widthratio yields a string, which silently failed every
            # `>= 100` comparison. The template clamps the bar at full width but keeps
            # the true figure, so an over-limit bin stays honestly red.
            "pct": ((on_hand / profile.max_quantity) * Decimal("100")).quantize(
                       Decimal("0.1")) if profile and profile.max_quantity else None,
        }

    def _walk(parent_pk, depth, seen):
        """Flatten one subtree into indented rows, cycle-guarded.

        Warehouse-typed children are skipped: a warehouse under a warehouse heads its
        OWN section below, so emitting it as an indented child row here would render
        the same location twice.
        """
        rows = []
        if depth > _MAX_DEPTH:
            return rows
        for loc in children.get(parent_pk, []):
            if loc.pk in seen or loc.location_type == "warehouse":
                continue
            rows.append(_row(loc, depth))
            rows.extend(_walk(loc.pk, depth + 1, seen | {loc.pk}))
        return rows

    emitted = set()

    sections = []
    for wh in [loc for loc in locations if loc.location_type == "warehouse"]:
        rows = _walk(wh.pk, 0, {wh.pk})
        emitted.add(wh.pk)
        emitted.update(row["loc"].pk for row in rows)
        sections.append({"warehouse": wh, "rows": rows})

    # Roots outside any warehouse (a stray top-level zone, an unattached transit lane)
    # still appear — silently dropping them from the map would hide bad structure data.
    # Built from the orphan LIST itself, not by walking parentless roots: a warehouse
    # may legitimately have no parent, and _walk(None, …) would re-walk it here.
    orphan_rows, seen = [], set()
    for loc in [loc for loc in locations
                if loc.parent_id is None and loc.location_type != "warehouse"]:
        if loc.pk in seen:
            continue
        orphan_rows.append(_row(loc, 0))
        seen.add(loc.pk)
        for row in _walk(loc.pk, 1, seen):
            orphan_rows.append(row)
            seen.add(row["loc"].pk)
    emitted |= seen

    # Residual pass: whatever neither walk reached — a cycle island among non-warehouse
    # locations has no root and no warehouse head to hang off — lands in the orphans
    # table rather than vanishing.
    for loc in locations:
        if loc.pk not in emitted and loc.location_type != "warehouse":
            orphan_rows.append(_row(loc, 0))
            emitted.add(loc.pk)

    type_counts = {"warehouse": 0, "zone": 0, "bin": 0, "staging": 0, "transit": 0}
    for loc in locations:
        type_counts[loc.location_type] = type_counts.get(loc.location_type, 0) + 1

    # Over-capacity bins, from data already in hand — no second pass over the ledger.
    over_count = sum(
        1 for bc in capacities.values()
        if bc.max_quantity and (totals.get(bc.location_id) or {}).get("qty", ZERO) >= bc.max_quantity)

    return render(request, "inventory/warehouse/map.html", {
        "sections": sections,
        "orphan_rows": orphan_rows,
        "stats": {
            **type_counts,
            "profiled": len(capacities),
            "over": over_count,
        },
    })
