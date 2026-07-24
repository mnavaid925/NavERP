"""SCM 4.7 Demand Planning — the derived demand-history series.

**There is deliberately NO demand-history table.** History is ALWAYS aggregated on demand from the
transactions that already exist — 4.5's ``SalesOrderLine`` (what customers asked for) or 4.3's
append-only ``StockMove`` ledger (what actually shipped) — exactly the derived-never-stored rule that
governs ``Item.on_hand()`` and ``SalesOrderLine.quantity_allocated()``. Re-keying sales history into a
fourth table would guarantee it drifts from the orders it was copied from.

All three consumers share this one function: forecast generation, seasonality derivation, and the
safety-stock calculator.

Model imports are made INSIDE the functions (the ``ReorderRule.on_hand_map()`` precedent) — this
module is reached from ``InventoryManagement/ReorderRules.py``, which ``models/__init__.py`` loads
BEFORE ``DemandPlanning``, so a module-level import would be a cycle.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import DateField, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncQuarter, TruncWeek

ZERO = Decimal("0")

#: Periods per year for each bucket — the season length the statistical engines default to.
PERIODS_PER_YEAR = {"day": 365, "week": 52, "month": 12, "quarter": 4}

_TRUNC = {"day": TruncDay, "week": TruncWeek, "month": TruncMonth, "quarter": TruncQuarter}


# ----------------------------------------------------------------------------- calendar buckets
def bucket_start(value, bucket):
    """Normalise a date to the first day of its bucket (Monday for weeks)."""
    if bucket == "week":
        return value - timedelta(days=value.weekday())
    if bucket == "month":
        return date(value.year, value.month, 1)
    if bucket == "quarter":
        return date(value.year, ((value.month - 1) // 3) * 3 + 1, 1)
    return value


def next_bucket(value, bucket):
    """First day of the bucket AFTER the one ``value`` starts."""
    if bucket == "week":
        return value + timedelta(days=7)
    if bucket == "month":
        return date(value.year + (value.month // 12), (value.month % 12) + 1, 1)
    if bucket == "quarter":
        month = ((value.month - 1) // 3) * 3 + 4
        return date(value.year + (month > 12), month - 12 if month > 12 else month, 1)
    return value + timedelta(days=1)


def period_label(value, bucket):
    """Short human label for a bucket start — the column header planners read."""
    if bucket == "month":
        return value.strftime("%b %Y")
    if bucket == "quarter":
        return f"Q{(value.month - 1) // 3 + 1} {value.year}"
    if bucket == "week":
        return f"W{value.isocalendar()[1]} {value.year}"
    return value.strftime("%d %b %Y")


def period_range(start, end, bucket):
    """Every ``(period_start, period_end)`` pair covering ``start``..``end`` inclusive.

    ``period_end`` is the LAST day inside the bucket, not the next bucket's first day, so a period's
    stored dates read the way a planner writes them (1–31 Jan, not 1 Jan – 1 Feb).
    """
    if not start or not end or end < start:
        return []
    out, cursor = [], bucket_start(start, bucket)
    while cursor <= end:
        following = next_bucket(cursor, bucket)
        out.append((cursor, following - timedelta(days=1)))
        cursor = following
    return out


def periods_per_year(bucket):
    return PERIODS_PER_YEAR.get(bucket, 12)


# ----------------------------------------------------------------------------- the history series
def demand_series(tenant, *, item, location=None, customer=None, source="sales_orders",
                  start, end, bucket="month", exclude_outliers=False, sigma=3):
    """Historical demand for one item as an ordered, DENSE ``[(period_start, quantity)]``.

    Dense means every bucket between ``start`` and ``end`` appears, zero-filled where nothing sold —
    a sparse series would silently shift every later period and wreck any seasonal fit.

    ``source``:
      * ``sales_orders`` — what customers ORDERED: ``SalesOrderLine.quantity_ordered`` bucketed by
        ``sales_order__order_date``, excluding draft and cancelled orders (a draft is not demand and a
        cancellation never was). This is true demand, including what could not be filled.
      * ``stock_issues`` — what actually SHIPPED: ``StockMove`` rows of type ``issue``, whose
        quantities are signed negative in the ledger and are therefore negated here. This is
        constrained demand — it cannot see a lost sale.
      * ``manual`` — no derivation at all; the planner types the numbers into the period grid.
    """
    from apps.scm.models import SalesOrderLine, StockMove

    if tenant is None or item is None or not start or not end or end < start:
        return []
    bucket = bucket if bucket in _TRUNC else "month"
    buckets = period_range(start, end, bucket)
    totals = {period_start: ZERO for period_start, _ in buckets}
    if source == "manual" or not totals:
        return [(period_start, ZERO) for period_start, _ in buckets]

    trunc = _TRUNC[bucket]
    if source == "stock_issues":
        moves = StockMove.objects.filter(tenant=tenant, item=item, move_type="issue",
                                         moved_at__date__range=(start, end))
        if location is not None:
            moves = moves.filter(location=location)
        # Filters BEFORE .values()/.annotate() — a .filter() after the grouping becomes a HAVING
        # clause on the aggregate, which is not what "only this location" means.
        rows = (moves.annotate(period=trunc("moved_at", output_field=DateField()))
                .values("period").annotate(total=Sum("quantity")).order_by("period"))
        for row in rows:
            if row["period"] in totals:
                # Issues are signed negative in the append-only ledger — negate to read as demand.
                totals[row["period"]] = -(row["total"] or ZERO)
    else:
        rows = (SalesOrderLine.objects
                .filter(sales_order__tenant=tenant, item=item,
                        sales_order__order_date__range=(start, end))
                .exclude(sales_order__status__in=("draft", "cancelled")))
        if customer is not None:
            rows = rows.filter(sales_order__customer=customer)
        rows = (rows.annotate(period=trunc("sales_order__order_date", output_field=DateField()))
                .values("period").annotate(total=Sum("quantity_ordered")).order_by("period"))
        for row in rows:
            if row["period"] in totals:
                totals[row["period"]] = row["total"] or ZERO

    series = [(period_start, totals[period_start]) for period_start, _ in buckets]
    if exclude_outliers:
        from apps.scm.models.DemandPlanning._forecasting import clip_outliers
        clipped = clip_outliers([qty for _, qty in series], Decimal(str(sigma or 3)))
        series = [(period_start, qty) for (period_start, _), qty in zip(series, clipped)]
    return series


def demand_series_map(tenant, items, *, start, end, bucket="month", source="sales_orders"):
    """``{item_id: [(period_start, quantity)]}`` for MANY items in ONE grouped query.

    The batch form of ``demand_series``, for pages that size or score every item at once (the
    safety-stock recalculation, the forecast-accuracy league table). Calling ``demand_series`` per row
    there would fire one aggregate per item — the exact N+1 that ``ReorderRule.on_hand_map()`` exists
    to avoid.

    Deliberately item-level: there is no ``location``/``customer`` narrowing here. For the default
    ``sales_orders`` source that changes nothing (an order line has no location), and for
    ``stock_issues`` the caller gets the item's whole network movement — which is the right figure for
    a network-wide policy pass and is documented rather than silently different.
    """
    from apps.scm.models import SalesOrderLine, StockMove

    item_ids = {getattr(item, "pk", item) for item in (items or [])}
    if tenant is None or not item_ids or not start or not end or end < start:
        return {}
    bucket = bucket if bucket in _TRUNC else "month"
    buckets = [period_start for period_start, _ in period_range(start, end, bucket)]
    empty = {period_start: ZERO for period_start in buckets}
    out = {item_id: dict(empty) for item_id in item_ids}
    trunc = _TRUNC[bucket]

    if source == "manual":
        pass
    elif source == "stock_issues":
        rows = (StockMove.objects
                .filter(tenant=tenant, item_id__in=item_ids, move_type="issue",
                        moved_at__date__range=(start, end))
                .annotate(period=trunc("moved_at", output_field=DateField()))
                .values("item_id", "period").annotate(total=Sum("quantity")))
        for row in rows:
            if row["period"] in out.get(row["item_id"], {}):
                out[row["item_id"]][row["period"]] = -(row["total"] or ZERO)
    else:
        rows = (SalesOrderLine.objects
                .filter(sales_order__tenant=tenant, item_id__in=item_ids,
                        sales_order__order_date__range=(start, end))
                .exclude(sales_order__status__in=("draft", "cancelled"))
                .annotate(period=trunc("sales_order__order_date", output_field=DateField()))
                .values("item_id", "period").annotate(total=Sum("quantity_ordered")))
        for row in rows:
            if row["period"] in out.get(row["item_id"], {}):
                out[row["item_id"]][row["period"]] = row["total"] or ZERO

    return {item_id: [(period_start, totals[period_start]) for period_start in buckets]
            for item_id, totals in out.items()}
