"""Inventory 5.17 — the shared compute engine behind the four reports.

Every figure the valuation / turnover / aging / ABC pages render comes out of this
module, and the snapshot generator runs the SAME functions — a frozen IRS- row can
never disagree with what the live page said at that instant (the scm 4.11
"one number, computed once" rule, applied at inventory-report granularity).

**One ledger fetch per request.** The constructor of :class:`Ledger` reads the
tenant's ``scm.StockMove`` rows ONCE in chronological order and indexes them by
item and by item×location; every report then works over those plain lists in
Python. No report may issue a per-row aggregate inside its loop — that would be
an N+1 across the whole warehouse (repo perf rule).

**Ownership (L36/L29):** everything computed here is DERIVED from SCM 4.3's
append-only ledger. Nothing in this sub-module writes a StockMove, an Item or a
JournalEntry. Where SCM already publishes a sibling figure — the per-item
valuation page (``scm:valuation_report``) and the single-number KPI tiles
(``inv_turnover`` …) — this engine deliberately computes the DRILL-DOWN variants
(per item×location, filtered windows) rather than rival totals under the same
name; grand totals here are page furniture, not the accounting record.

**Costing rules (mirroring SCM's own valuation walk, localized because peer apps
don't import each other's internals):**

* weighted_avg items value on-hand × the cached ``average_cost``;
* fifo/lifo items walk their inbound cost layers chronologically (fifo consumes
  oldest first, lifo newest first) and value what survives;
* TRANSFER legs are excluded from the *costing* layer walks exactly as SCM's
  valuation excludes them — a transfer is priced at the item's average on both
  legs, and letting it consume real layers would drift a FIFO item toward WAC.

The AGING report is deliberately different there: it is a PHYSICAL view — every
inbound leg (transfers included) is a fresh arrival at that spot, and every
outbound leg consumes the oldest stock first — so its buckets always sum to the
spot's true on-hand. The two pages answer different questions and say so.
"""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from apps.scm.models import Item, StockMove

ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")

#: Customer demand — the same convention scm 4.7's demand series uses.
DEMAND_TYPES = ("issue",)
#: Any draw that physically consumes stock (demand OR internal use).
ANY_DRAW_TYPES = ("issue", "consumption", "maintenance")
#: Inbound legs excluded from the COSTING walks only (see module docstring).
TRANSFER_TYPE = "transfer"

AGING_BUCKETS = [
    ("0-30", "0–30 d", 0, 30),
    ("31-60", "31–60 d", 31, 60),
    ("61-90", "61–90 d", 61, 90),
    ("91-180", "91–180 d", 91, 180),
    ("180plus", "180+ d", 181, None),
]
BUCKET_LABELS = [key for key, _label, _lo, _hi in AGING_BUCKETS]

DEFAULT_WINDOW_DAYS = 90
MAX_WINDOW_DAYS = 3650

#: Window presets offered in the turnover/ABC filter dropdowns (days, label).
WINDOW_CHOICES = [("30", "Last 30 days"), ("60", "Last 60 days"), ("90", "Last 90 days"),
                  ("180", "Last 180 days"), ("365", "Last 365 days")]


def q2(value):
    return (value if value is not None else ZERO).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def f2(value):
    """JSON-safe float for snapshot summaries (None passes through)."""
    return None if value is None else float(q2(value))


def clamp_window(raw, default=DEFAULT_WINDOW_DAYS):
    """Parse a ?days= query value into a sane positive int, else the default.

    The length guard is not cosmetic: a 4301-digit ``isdecimal()`` string passes
    the check and then blows Python's int→str conversion limit inside ``int()``.
    """
    raw = (raw or "").strip()
    if not raw.isdecimal() or len(raw) > 4:
        return default
    return max(1, min(int(raw), MAX_WINDOW_DAYS))


class Ledger:
    """One chronological fetch of the tenant's moves, indexed for all four reports.

    Stocked items only: every report in this sub-module values physical stock,
    so service/expensed item legs are excluded at the DB, not per row later.
    """

    def __init__(self, tenant, location=None):
        qs = (StockMove.objects.filter(tenant=tenant, item__item_type="stock")
              .order_by("moved_at", "id"))
        if location is not None:
            qs = qs.filter(location=location)
        self.moves = list(qs.only("item_id", "location_id", "quantity", "unit_cost",
                                  "move_type", "moved_at"))
        self.by_item = {}
        self.by_spot = {}
        for move in self.moves:
            self.by_item.setdefault(move.item_id, []).append(move)
            self.by_spot.setdefault((move.item_id, move.location_id), []).append(move)

    def items(self, tenant):
        """Stocked item masters for this tenant, keyed for O(1) row assembly."""
        return {obj.pk: obj for obj in Item.objects.filter(tenant=tenant, item_type="stock")}

    def locations(self, tenant):
        from apps.scm.models import Location
        return {obj.pk: obj for obj in Location.objects.filter(tenant=tenant)}


# --------------------------------------------------------------------------- costing
def _on_hand(moves):
    return sum((m.quantity for m in moves), ZERO)


def _value_walk(item, moves):
    """(on_hand, value) for one spot under the item's costing method.

    Same algorithm as SCM's per-item valuation walk (transfers excluded from the
    costing pass, landed costs ignored — this page has no uplift map by design),
    applied at item×location granularity.
    """
    on_hand = _on_hand(moves)
    if on_hand <= ZERO:
        return on_hand, ZERO
    if item.costing_method == "weighted_avg":
        return on_hand, q2(on_hand * (item.average_cost or ZERO))
    layers = [[m.quantity, m.unit_cost or ZERO] for m in moves
              if m.quantity > ZERO and m.move_type != TRANSFER_TYPE]
    outbound = sum((-m.quantity for m in moves
                    if m.quantity < ZERO and m.move_type != TRANSFER_TYPE), ZERO)
    order = layers if item.costing_method == "fifo" else list(reversed(layers))
    remaining = outbound
    for layer in order:
        if remaining <= ZERO:
            break
        take = min(layer[0], remaining)
        layer[0] -= take
        remaining -= take
    return on_hand, q2(sum((qty * cost for qty, cost in layers), ZERO))


def _value_at(item, moves, cutoff):
    """_value_walk over only the moves posted before ``cutoff`` (turnover's start book value)."""
    return _value_walk(item, [m for m in moves if m.moved_at < cutoff])


# ------------------------------------------------------------------------- valuation
def valuation_rows(tenant, ledger=None, location=None):
    """Per item×location on-hand + value under each item's costing method.

    Returns ``(rows, totals)`` — rows sorted by value desc (the Pareto order a
    warehouse walk actually follows); totals carries the grand value and counts.
    """
    ledger = ledger or Ledger(tenant, location=location)
    items = ledger.items(tenant)
    locations = ledger.locations(tenant)
    rows = []
    total_value = ZERO
    for (item_id, location_id), moves in ledger.by_spot.items():
        item = items.get(item_id)
        if item is None:
            continue
        on_hand, value = _value_walk(item, moves)
        if on_hand == ZERO and value == ZERO:
            continue
        total_value += value
        rows.append({
            "item": item,
            "location": locations.get(location_id),
            "on_hand": q2(on_hand),
            "unit_value": q2(value / on_hand) if on_hand > ZERO else ZERO,
            "value": value,
            "method": item.get_costing_method_display(),
        })
    rows.sort(key=lambda r: r["value"], reverse=True)
    return rows, {"total_value": total_value, "spots": len(rows)}


# ------------------------------------------------------------------------- turnover
def turnover_rows(tenant, days, ledger=None, location=None):
    """Per-item turnover over a trailing window.

    turns = COGS ÷ average inventory value, where COGS is the cost of the
    customer-issue legs inside the window and the average is the mean of the
    window-start and now book values under the item's own costing method.
    days_on_hand answers "how long would today's stock last at this rate".
    """
    ledger = ledger or Ledger(tenant, location=location)
    items = ledger.items(tenant)
    now = timezone.now()
    start = now - timedelta(days=days)
    days_dec = Decimal(days)
    rows = []
    total_cogs = ZERO
    for item_id, moves in ledger.by_item.items():
        item = items.get(item_id)
        if item is None:
            continue
        cogs = q2(sum(((-m.quantity) * (m.unit_cost or ZERO) for m in moves
                       if m.move_type in DEMAND_TYPES and start <= m.moved_at <= now), ZERO))
        sold_units = sum((-m.quantity for m in moves
                          if m.move_type in DEMAND_TYPES and start <= m.moved_at <= now), ZERO)
        end_on_hand, end_value = _value_walk(item, moves)
        _start_hand, start_value = _value_at(item, moves, start)
        # Average of the window endpoints; when both endpoints are stockless but
        # demand provably existed inside the window (received-and-sold-through),
        # fall back to whichever book value exists so a trading SKU never reads
        # "dead" — the same fallback SCM's inv_turnover KPI applies.
        avg_value = (start_value + end_value) * _HALF
        if avg_value <= ZERO:
            avg_value = end_value or start_value
        turns = (cogs / avg_value) if avg_value > ZERO else None
        doh = (days_dec / turns) if turns is not None and turns > ZERO else None
        total_cogs += cogs
        rows.append({
            "item": item,
            "sold_units": q2(sold_units),
            "cogs": cogs,
            "start_value": q2(start_value),
            "end_value": end_value,
            "avg_value": q2(avg_value),
            "end_on_hand": q2(end_on_hand),
            # ≥2 turns per window reads fast; below half a turn reads slow; no
            # customer demand at all reads dead-in-window regardless of stock.
            "velocity": _velocity(cogs, turns),
            "turns": q2(turns) if turns is not None else None,
            "days_on_hand": int(doh.quantize(Decimal("1"), rounding=ROUND_HALF_UP)) if doh is not None else None,
        })
    rows.sort(key=lambda r: r["cogs"], reverse=True)
    return rows, {"total_cogs": total_cogs, "window_days": days, "items": len(rows)}


def _velocity(cogs, turns):
    """Velocity verdict for one item-window.

    No demand at all reads dead. Demand WITH a measurable average stock reads
    off the turns bands. Demand with NO measurable stock at either endpoint
    (received-and-sold-through inside the window) is the FASTEST possible
    mover, not a dead one — it never got a chance to rest.
    """
    if cogs <= ZERO:
        return "dead"
    if turns is None:
        return "fast"
    if turns >= 2:
        return "fast"
    if turns >= _HALF:
        return "medium"
    return "slow"


_HALF = Decimal("0.5")
VELOCITY_CSS = {"fast": "badge-green", "medium": "badge-info",
                "slow": "badge-amber", "dead": "badge-red"}
VELOCITY_CHOICES = [("fast", "Fast"), ("medium", "Medium"), ("slow", "Slow"), ("dead", "Dead")]


# ---------------------------------------------------------------------------- aging
def aging_rows(tenant, ledger=None, location=None):
    """Per item×location FIFO age buckets over the PHYSICAL layers.

    Buckets always sum to the spot's true on-hand (transfers included as
    arrivals — see module docstring). ``last_draw_at`` drives the slow/dead
    flags: stock with no outbound leg of any kind for 90+ days is dead weight.
    """
    ledger = ledger or Ledger(tenant, location=location)
    items = ledger.items(tenant)
    locations = ledger.locations(tenant)
    now = timezone.now()
    rows = []
    total_value = ZERO
    dead_value = ZERO
    for (item_id, location_id), moves in ledger.by_spot.items():
        item = items.get(item_id)
        if item is None:
            continue
        on_hand = _on_hand(moves)
        if on_hand <= ZERO:
            continue
        # Physical layer walk: inbound legs arrive (oldest-first consumption),
        # EVERY outbound leg consumes — including transfers out, which are just
        # this stock leaving for another shelf.
        layers = []
        remaining_out = ZERO
        for move in moves:  # chronological
            if move.quantity > ZERO:
                layers.append([move.quantity, move.unit_cost or ZERO, move.moved_at])
            else:
                remaining_out += -move.quantity
        for layer in layers:
            if remaining_out <= ZERO:
                break
            take = min(layer[0], remaining_out)
            layer[0] -= take
            remaining_out -= take
        buckets = {key: {"qty": ZERO, "value": ZERO} for key in BUCKET_LABELS}
        spot_value = ZERO
        oldest_days = 0
        for qty, cost, moved_at in layers:
            if qty <= ZERO:
                continue
            age_days = max((now - moved_at).days, 0)
            oldest_days = max(oldest_days, age_days)
            value = q2(qty * cost)
            spot_value += value
            for key, _label, lo, hi in AGING_BUCKETS:
                if age_days >= lo and (hi is None or age_days <= hi):
                    buckets[key]["qty"] += q2(qty)
                    buckets[key]["value"] += value
                    break
        draws = [m for m in moves if m.move_type in ANY_DRAW_TYPES and m.quantity < ZERO]
        last_draw = max((m.moved_at for m in draws), default=None)
        days_since_draw = ((now - last_draw).days if last_draw else None)
        health = "healthy"
        if days_since_draw is None or days_since_draw >= 91:
            health = "dead"
        elif days_since_draw >= 61:
            health = "slow"
        total_value += spot_value
        if health == "dead":
            dead_value += spot_value
        rows.append({
            "item": item,
            "location": locations.get(location_id),
            "on_hand": q2(on_hand),
            # Pre-aligned bucket cells (template-safe: no variable key lookups).
            "bucket_rows": [{"key": key, "label": label,
                             "qty": q2(buckets[key]["qty"])} for key, label, _lo, _hi in AGING_BUCKETS],
            "buckets": buckets,
            "total_value": spot_value,
            "oldest_days": oldest_days,
            "last_draw_at": last_draw,
            "days_since_draw": days_since_draw,
            "health": health,
        })
    rows.sort(key=lambda r: (-r["buckets"]["180plus"]["value"], -r["total_value"]))
    return rows, {"total_value": total_value, "dead_value": dead_value,
                  "spots": len(rows)}


HEALTH_CSS = {"healthy": "badge-green", "slow": "badge-amber", "dead": "badge-red"}
HEALTH_CHOICES = [("healthy", "Healthy"), ("slow", "Slow moving"), ("dead", "Dead stock")]


# ------------------------------------------------------------------------------ ABC
def abc_rows(tenant, days, ledger=None, location=None):
    """Consumption-value Pareto over the stocked item master.

    Items rank by the cost of their customer-issue legs in the window; the
    cumulative share assigns A (top 80% of value), B (next 15%), C (tail).
    Zero-demand items are class C with a dead velocity flag — they carry
    on-hand value but no usage, which is exactly what the class must surface.
    """
    rows, meta = turnover_rows(tenant, days, ledger=ledger, location=location)
    ranked = [r for r in rows if r["cogs"] > ZERO]
    unranked = [r for r in rows if r["cogs"] <= ZERO]
    grand = sum((r["cogs"] for r in ranked), ZERO)
    cumulative = ZERO
    counts = {"A": 0, "B": 0, "C": 0}
    for row in ranked:
        cumulative += row["cogs"]
        share = (cumulative / grand * 100) if grand > ZERO else Decimal("100")
        row["cum_share"] = q2(share)
        row["abc_class"] = "A" if share <= 80 else ("B" if share <= 95 else "C")
        counts[row["abc_class"]] += 1
    for row in unranked:
        row["cum_share"] = None
        row["abc_class"] = "C"
        counts["C"] += 1
    ordered = ranked + unranked
    meta.update({"a_items": counts["A"], "b_items": counts["B"], "c_items": counts["C"],
                 "a_share_pct": (q2(sum((r['cogs'] for r in ordered if r['abc_class'] == 'A'), ZERO)
                                    / grand * 100) if grand > ZERO else ZERO)})
    return ordered, meta


ABC_CLASS_CSS = {"A": "badge-green", "B": "badge-info", "C": "badge-muted"}


# ------------------------------------------------------------------------- snapshots
#: Rows kept in a snapshot summary — headlines, not the full table.
SNAPSHOT_TOP_ROWS = 15


def build_summary(report_type, tenant, location=None, window_days=None, ledger=None):
    """Run one report exactly as its live page would and distil scalar-only JSON.

    This is THE freeze path: the snapshot generator (view and seeder alike)
    stores what this returns, so an IRS- row can never disagree with the page
    it froze. Every value must be float/int/str/bool/None — no Decimals, dates
    or model instances (the ``scm.KpiSnapshot`` contract). Callers freezing
    several reports in one pass (the seeder) may thread one ``ledger`` through
    to avoid re-fetching it per call.
    """
    ledger = ledger or Ledger(tenant, location=location)
    if report_type == "valuation":
        rows, totals = valuation_rows(tenant, ledger=ledger)
        return {
            "total_value": f2(totals["total_value"]),
            "spots": totals["spots"],
            "top_rows": [{"sku": r["item"].sku, "name": r["item"].name,
                          "location": r["location"].code if r["location"] else None,
                          "on_hand": f2(r["on_hand"]), "value": f2(r["value"]),
                          "method": r["method"]} for r in rows[:SNAPSHOT_TOP_ROWS]],
        }
    if report_type == "turnover":
        days = window_days or DEFAULT_WINDOW_DAYS
        rows, totals = turnover_rows(tenant, days, ledger=ledger)
        counts = {}
        for row in rows:
            counts[row["velocity"]] = counts.get(row["velocity"], 0) + 1
        return {
            "window_days": days,
            "total_cogs": f2(totals["total_cogs"]),
            "items": totals["items"],
            "velocity_counts": counts,
            "top_rows": [{"sku": r["item"].sku, "cogs": f2(r["cogs"]),
                          "turns": f2(r["turns"]), "velocity": r["velocity"],
                          "days_on_hand": r["days_on_hand"]} for r in rows[:SNAPSHOT_TOP_ROWS]],
        }
    if report_type == "aging":
        rows, totals = aging_rows(tenant, ledger=ledger)
        dead = [r for r in rows if r["health"] == "dead"]
        ranked = sorted(rows, key=lambda x: -x["total_value"])
        return {
            "total_value": f2(totals["total_value"]),
            "dead_value": f2(totals["dead_value"]),
            "spots": totals["spots"],
            "dead_spots": len(dead),
            "top_rows": [{"sku": r["item"].sku,
                          "location": r["location"].code if r["location"] else None,
                          "on_hand": f2(r["on_hand"]),
                          "value": f2(r["total_value"]),
                          "oldest_days": r["oldest_days"], "health": r["health"]}
                         for r in ranked[:SNAPSHOT_TOP_ROWS]],
        }
    if report_type == "abc":
        days = window_days or DEFAULT_WINDOW_DAYS
        rows, stats = abc_rows(tenant, days, ledger=ledger)
        return {
            "window_days": days,
            "a_items": stats["a_items"], "b_items": stats["b_items"], "c_items": stats["c_items"],
            "a_share_pct": f2(stats["a_share_pct"]),
            "top_rows": [{"sku": r["item"].sku, "abc_class": r["abc_class"],
                          "cum_share": f2(r["cum_share"]),
                          "cogs": f2(r["cogs"]), "velocity": r["velocity"]}
                         for r in rows[:SNAPSHOT_TOP_ROWS]],
        }
    raise ValueError(f"Unknown report type: {report_type!r}")
