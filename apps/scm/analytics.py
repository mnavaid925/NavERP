"""SCM 4.11 Supply Chain Analytics — the compute layer.

**One number, computed once.** Every figure the five analytics pages render — the tile, its CSV
export, the ``KpiSnapshot`` frozen from it and the ``SupplyChainAlert`` raised off it — comes out of
:func:`compute_metric` in this module. That is the whole reason the file exists: a tile that says
"4.2 turns" and an alert that fires at 3.9 would both be defensible if each owned its own SQL, and
neither would be trustworthy. So the SQL lives here, once, and the four consumers differ only in what
they do with the answer.

Result contract (mirroring ``apps/crm/analytics.py``)::

    resolver(tenant, start, end, scope, params) -> {
        "value":     Decimal or None,   # None = not computable, and the breakdown says why
        "display":   str,               # the value rendered per its METRIC_META unit
        "breakdown": {...},             # the component arithmetic, JSON-serializable
        "rows":      [...],             # supporting rows (capped), JSON-serializable
    }

``params`` carries the metric's own knobs (``.days`` / ``.pct``) and defaults to the module-wide
fallbacks, so the four-argument form in the plan is still a legal call; :func:`compute_metric` always
passes the fifth explicitly. **Everything inside ``breakdown`` and ``rows`` must be a float, int, str,
bool or None — never a Decimal, date or model instance** — because ``KpiSnapshot.breakdown`` is a
``JSONField`` that stores it verbatim and re-renders it months later without recomputing. The
top-level ``value`` stays a ``Decimal``: that is what :func:`band_for` compares and what
``KpiSnapshot.value`` (a ``DecimalField`` written through ``q4()``) stores.

**Import direction is ONE-WAY: analytics -> models -> _choices.** This module imports
``apps.scm.models``; nothing under ``apps/scm/models/`` may import this module at module scope. The
metric vocabulary therefore lives in ``models/SupplyChainAnalytics/_choices.py`` (pure data, no
queries) so ``KpiTarget.metric`` can take its ``choices`` from the same catalog the resolvers below
are keyed by, without the edge running both ways. That is the split ``apps/crm`` already proved
(``models/AnalyticsReporting/_choices.py`` vs ``apps/crm/analytics.py``).

**The metric set is CLOSED — the Module 10 boundary.** There is no formula language here, no semantic
layer, no OLAP cube engine and no machine learning. A ``KpiTarget`` picks one key out of
:data:`~apps.scm.models.SupplyChainAnalytics._choices.METRIC_META` and a *reviewed* resolver in this
file computes it. Authoring your own calculation over a semantic layer is 10.11; the generic BI/widget
canvas is 10.8/10.10; genuine ML/AutoML is 10.13. 4.11 must not grow towards any of them — a metric
key is a promise that somebody read the SQL, and that promise is what lets ``KpiTarget.clean()``
validate a target against the metric's own metadata instead of against whatever was typed.

**4.11 is READ-ONLY over 4.1-4.10.** Nothing in this module writes a ``StockMove`` or a
``JournalEntry``, ever. Where an earlier sub-module already derives a figure — ``ReorderRule.abc_class``
(4.7), ``Carrier.on_time_delivery_pct`` (4.6), ``SupplierScorecard.overall_score`` (4.2) — 4.11 READS
and TRENDS it and never computes a rival number under the same name.

**Money and currency.** ``PurchaseOrder`` / ``SalesOrder`` / ``FreightInvoice`` each carry a nullable
``accounting.Currency`` and this repo has NO FX-rate table. Money metrics therefore sum in whatever
currency the documents were raised in and return a ``mixed_currency`` flag (plus the currency codes)
in ``breakdown`` when the window spans more than one. A rate is never invented, and the money
formatter deliberately prints no currency symbol for the same reason.

**Cost.** The RESOLVERS run on page load. Every one is a small fixed number of grouped
``aggregate()``/``annotate()`` queries — never one query per row — and every row list it returns is
capped, with a ``truncated`` flag in the breakdown when a cap bit. The two WRITERS at the bottom
(:func:`capture_snapshots` and :func:`detect_alerts`) are batch actions that evaluate many metrics in
one pass; they belong behind an admin-gated POST or a management command, never on a GET.
"""
from datetime import date, timedelta
from decimal import Decimal, DivisionByZero, InvalidOperation

from django.db import transaction
from django.db.models import (Avg, Case, Count, DecimalField, Exists, ExpressionWrapper, F, Max,
                              Min, OuterRef, Q, Sum, Value, When)
from django.utils import timezone

from apps.scm.models import (CapaAction, Carrier, CarrierRateCard, DemandForecastPeriod,
                             DemandSignal, FreightInvoice, GoodsReceiptLine, GoodsReceiptNote,
                             Item, KpiSnapshot, KpiTarget, Load, NonConformance, PickTaskLine,
                             ProductionTimeLog, PurchaseOrder, PurchaseOrderLine, ReorderRule,
                             ReturnDisposition, RFQQuote, SalesOrderAllocation, SalesOrderLine,
                             Shipment, StockMove,
                             SupplierContract, SupplierRiskAssessment, SupplierScorecard,
                             SupplyChainAlert, TrackingEvent, WarrantyClaimCost, YardVisit, q2, q4)
# 4.7 already owns the calendar-bucket arithmetic (and the tz-aware DateTimeField boundary helper,
# whose comment explains why a bare `date` silently shifts a window under a non-UTC project
# timezone). Imported rather than re-derived: two implementations of "how many months is this" are
# two chances to disagree, and `period_count` in particular is the L40 fix — it counts buckets
# ARITHMETICALLY so a caller can reject an absurd span without first building it.
from apps.scm.models.DemandPlanning._history import (bucket_start, next_bucket,
                                                     period_count as _bucket_count, period_label,
                                                     _moment)
from apps.scm.models.SupplyChainAnalytics._choices import (METRIC_META, OPEN_ALERT_STATUSES,
                                                           PERIOD_GRAIN_CHOICES)

ZERO = Decimal("0")
HUNDRED = Decimal("100")
DAYS_PER_YEAR = Decimal("365")
MINUTES_PER_HOUR = Decimal("60")
SECONDS_PER_HOUR = Decimal("3600")

#: Products of two Decimal columns need an explicit output_field; wide enough that a quantity x cost
#: over a large ledger cannot overflow the expression before it is quantized for display.
_DEC = DecimalField(max_digits=24, decimal_places=6)


# =================================================================================================
# Module-level defaults for the metric knobs
#
# A page has to work BEFORE anybody has created a KpiTarget — the analytics pages are browsable from
# the sidebar on a fresh tenant. So every metric that is defined in terms of an N or a % carries a
# documented default here, and `KpiTarget.parameter_days` / `parameter_pct` override it when a target
# is passed. These are conventional planning values, not derived from anything: they exist so the
# first render says something true rather than nothing.
# =================================================================================================

#: No issue/consumption movement for this many days and the stock is "dead".
DEAD_STOCK_DAYS = 90
#: A remaining FIFO cost layer older than this counts as "aging".
AGING_DAYS = 90
#: Annual inventory carrying rate, as a percentage of stock value (storage + capital + shrink).
CARRYING_PCT = Decimal("25")
#: A short-window demand rate this far above the long-window mean is a "spike".
SPIKE_PCT = Decimal("50")
#: A lot expiring inside this many days is at risk.
EXPIRY_DAYS = 90
#: A shipment with no tracking event for this many days has gone quiet.
STALE_TRACKING_DAYS = 3
#: A supplier contract ending inside this many days is a continuity risk.
CONTRACT_EXPIRY_DAYS = 60

#: Which default belongs to which metric. Keys not listed here take no parameter.
METRIC_PARAM_DEFAULTS = {
    "inv_dead_stock_value": {"days": DEAD_STOCK_DAYS},
    "inv_aging_over_days_value": {"days": AGING_DAYS},
    "inv_expiry_risk_value": {"days": EXPIRY_DAYS},
    "inv_carrying_cost": {"pct": CARRYING_PCT},
    "supplier_disruption_score": {"days": CONTRACT_EXPIRY_DAYS},
    "demand_spike_count": {"pct": SPIKE_PCT},
    "shipments_at_risk_count": {"days": STALE_TRACKING_DAYS},
}


# =================================================================================================
# Caps
#
# Every one of these bounds a query at the DATABASE (a slice becomes a LIMIT), never by measuring
# something already built in memory — L40: `len(build_the_whole_thing())` is the payload, not the
# guard. Where a cap can bite, the resolver reports `truncated: true` in its breakdown rather than
# quietly returning a smaller, wrong number.
# =================================================================================================

#: Items pulled into a grouped on-hand position.
MAX_ITEM_ROWS = 5000
#: Groups pulled from a grouped-by-key aggregate (sku_hint, vendor, GL account, ...).
MAX_GROUP_ROWS = 2000
#: Rows scanned for an in-Python average/median (cycle times, lead times).
MAX_SAMPLE_ROWS = 5000
#: Ledger rows pulled into the FIFO aging walk — the only resolver that needs individual moves.
MAX_LEDGER_ROWS = 50000
#: Items the FIFO aging walk covers, highest stock value first.
MAX_AGING_ITEMS = 500
#: Supporting rows any resolver returns in ``rows``.
MAX_DETAIL_ROWS = 25
#: Buckets :func:`period_windows` will generate for one trend line.
MAX_TREND_PERIODS = 60

#: Targets one :func:`capture_snapshots` run will evaluate. Checked with ``.count()`` BEFORE any
#: target is fetched, so the guard is O(1) in the thing it guards (L40).
MAX_SNAPSHOT_TARGETS = 200
#: Alerts one :func:`detect_alerts` run may raise per ``alert_type``. Applied as a LIMIT on the
#: ordered query, so the biggest exception of each kind survives and the tail is dropped — an alert
#: queue that raises 4000 rows is an alert queue nobody opens twice.
MAX_ALERTS_PER_TYPE = 25

#: Fewest suppliers a "bottom decile" can be measured over. Below this the decile is degenerate — on
#: a tenant with one supplier the bottom 10% IS that supplier, and the metric would report "100% of
#: spend is tail spend" about a sole strategic relationship. Tail spend means the long tail of small
#: suppliers; with no tail there is no figure, and saying so is better than a confident 100%.
MIN_TAIL_SUPPLIERS = 10

#: Outbound move types that are COGS. ``transfer`` is EXCLUDED because it is an internal relocation
#: posted as a signed pair and counting it double-counts — the same exclusion
#: ``apps/scm/views/InventoryManagement/Reports.py`` makes in the FIFO/LIFO layer walk. ``issue`` is
#: customer demand and ``consumption`` is a work-order draw: 4.8 split them deliberately so 4.7's
#: forecasts would not read raw-material draws as demand, and both are genuine cost out of stock.
COGS_MOVE_TYPES = ("issue", "consumption")

#: PO statuses that represent committed money. Draft and pending-approval are not spend yet, and a
#: cancelled order never was.
SPEND_PO_STATUSES = ("approved", "sent", "acknowledged", "partially_received", "received", "closed")

#: Contract statuses that count as cover for on/off-contract spend. ``renewed`` is excluded: the
#: successor contract is its own row and is the one that should be covering the order.
COVERING_CONTRACT_STATUSES = ("active", "expiring")

#: Freight bills that have actually been through 4.6's audit. ``not_matched`` was never audited, and
#: ``duplicate`` is the audit SAYING this is a second copy of a bill already counted — including it
#: would double the freight leg of every cost figure below.
AUDITED_FREIGHT_MATCH_STATUSES = ("matched", "price_variance", "disputed")

#: Sales-order statuses that are NOT demand and NOT revenue. Same exclusion 4.7's ``demand_series``
#: makes: a draft is not an order and a cancellation never was.
NON_REVENUE_SO_STATUSES = ("draft", "cancelled")

#: Shipments still on the road — the population "at risk" can be drawn from.
IN_FLIGHT_SHIPMENT_STATUSES = ("booked", "in_transit", "exception")

#: 4.10's restock marker. ``_post_stock_move`` stamps ``reference=<the RMA's number>`` on the
#: positive ``receipt`` it writes when a returned unit goes back into stock
#: (``views/ReturnsManagement/ReturnDispositions.py``), and ``ReturnAuthorization.NUMBER_PREFIX`` is
#: ``RMA``. No other writer in the app puts an ``RMA-`` reference on a ``receipt``: transfers stamp
#: ``TRF-``, adjustments ``ADJ-``, receipts ``GRN-``, work orders ``WO-``, quality write-offs
#: ``NCR-``. That is what makes a return restock RELIABLY IDENTIFIABLE, and therefore what lets
#: :func:`_r_demand_spike_count` ship the NETTED demand series instead of a gross-series caveat.
RETURN_REFERENCE_PREFIX = "RMA-"
#: 4.9's scrap marker, and 4.10's return write-off marker — the two named sources of an ``adjustment``.
NCR_REFERENCE_PREFIX = "NCR-"

#: The short trailing window a demand spike is measured over, against the whole window's daily rate.
SPIKE_SHORT_DAYS = 7

# -- The two rates 4.1-4.10 does not record ------------------------------------------------------
# A pick line costs something to walk, touch and pack, and no row anywhere in this app carries that
# number: 4.4's PickTask has no cost column and there is no labour-rate master outside 4.8's work
# centres (which are production, not distribution). These are therefore CONVENTIONS, exactly like
# CARRYING_PCT above — stated, echoed into every breakdown that uses them, and separately visible in
# the cost stack so a reader can subtract them back out and substitute their own figure. They are
# NOT derived from anything and the page must not imply they are.
HANDLING_COST_PER_PICK_LINE = Decimal("1.50")
HANDLING_COST_PER_PICK_UNIT = Decimal("0.25")

#: Printed by every margin metric. L29: ``apps.accounting`` owns the ledger; SCM posts no
#: ``JournalEntry`` and this is not the statutory P&L.
OPERATIONAL_ESTIMATE_NOTE = (
    "OPERATIONAL ESTIMATE over SCM rows — NOT the statutory P&L. SCM posts no JournalEntry; "
    "apps.accounting owns the ledger, and its Balance Sheet / P&L are the reportable figures. This "
    "number exists to steer operations (which item, which customer, which lane), not to be filed.")

#: **"In full" is DEFINED HERE AND NOWHERE ELSE IN THE REPO.** Returned verbatim in
#: :func:`_r_otif_pct`'s breakdown so the page prints the definition beside the number.
IN_FULL_DEFINITION = (
    "In full = no line of the shipment's sales order is short. A line is short when the sum of its "
    "SalesOrderAllocation quantities (excluding cancelled) is below quantity_ordered, or when none "
    "of what it reserved has actually left stock. SalesOrderLine has NO quantity_shipped column, so "
    "the allocation rows are the only per-line quantity 4.5 records, and a released allocation or "
    "an 'issue' StockMove for the item is the only evidence the goods physically moved.")

_GRAINS = tuple(value for value, _ in PERIOD_GRAIN_CHOICES)

# -- Window bounds, and why they are not decoration ----------------------------------------------
# Date arithmetic OVERFLOWS at the edges of `datetime.date`, and every overflow here is an uncaught
# 500 on a value a caller can choose:
#   * `next_bucket(9999-12-31, "day")` adds a day and leaves the calendar (period_windows);
#   * `next_bucket(9999-12-01, "month")` and the quarter form both roll into year 10000;
#   * `_moment(9999-12-31, end_of_day=True)` adds a day to build the half-open upper bound, so
#     EVERY resolver that windows a DateTimeField inherits the same crash.
# 9998-12-31 is the highest end date all four grains and the moment helper survive, and 1900-01-01
# is the floor 4.7 already uses (DemandForecast.MIN_HORIZON_YEAR) for the same class of problem.
# `compute_metric` clamps to these ONCE, at the single entry point, so no resolver has to remember.
MIN_PERIOD_DATE = date(1900, 1, 1)
MAX_PERIOD_DATE = date(9998, 12, 31)


def clamp_date(value):
    """Bring a date inside the range this module's arithmetic can survive — see above."""
    if value is None:
        return None
    return min(max(value, MIN_PERIOD_DATE), MAX_PERIOD_DATE)


# =================================================================================================
# 1. Windows
# =================================================================================================

def range_bounds(key, today=None):
    """Translate a ``DATE_RANGE_CHOICES`` key into an inclusive ``(start, end)`` pair of ``date``s.

    Both ends are inclusive and counted in calendar days, so ``last_7`` is a seven-day window ending
    today (not eight). ``end`` is always a real date. ``start`` is ``None`` for ``all`` — meaning
    "no lower bound", which every helper here honours by simply not adding the filter.

    A caller that must persist the window (``KpiSnapshot.period_start`` is a non-null ``DateField``)
    has to substitute a concrete date for that ``None`` itself; this function will not invent one,
    because "the beginning of time" is a different date for every tenant.
    """
    today = today or timezone.localdate()
    if key == "last_7":
        return today - timedelta(days=6), today
    if key == "last_30":
        return today - timedelta(days=29), today
    if key == "last_90":
        return today - timedelta(days=89), today
    if key == "quarter":
        return today.replace(month=((today.month - 1) // 3) * 3 + 1, day=1), today
    if key == "year":
        return today.replace(month=1, day=1), today
    return None, today  # "all"


def period_count(grain, start, end):
    """How many ``grain`` buckets ``start``..``end`` spans — ARITHMETICALLY, never by walking.

    Delegates to 4.7's ``models/DemandPlanning/_history.period_count``, which is the same function
    with its arguments in the other order (``(start, end, bucket)``). The order is flipped here to
    match ``period_windows(grain, count, end)`` and the rest of 4.11, and the delegation is the point:
    counting buckets by building the list first is exactly the DoS L40 was written about, and there
    must be one implementation of the arithmetic, not two.
    """
    grain = _grain(grain)
    return _bucket_count(start, end, grain)


def period_windows(grain, count, end=None):
    """The last ``count`` ``grain`` buckets ending with the one containing ``end``, oldest first.

    Returns ``[(period_start, period_end)]`` with ``period_end`` the LAST day inside the bucket (the
    4.7 convention: 1-31 Jan, not 1 Jan - 1 Feb), which is exactly the pair a trend point stores in
    ``KpiSnapshot.period_start``/``period_end``.

    ``count`` is clamped to :data:`MAX_TREND_PERIODS` BEFORE anything is built — the clamp is O(1) in
    the thing it bounds, which is the whole point (L40).

    ``end`` is clamped to :data:`MAX_PERIOD_DATE` for a second, separate reason: bounding the COUNT
    does not bound the DATE, and the very first bucket built at ``9999-12-31`` raises
    ``OverflowError`` inside ``next_bucket`` before the count clamp has anything to do.
    """
    grain = _grain(grain)
    end = clamp_date(end or timezone.localdate())
    try:
        count = int(count or 1)
    except (TypeError, ValueError):
        count = 1
    count = max(1, min(count, MAX_TREND_PERIODS))
    windows, cursor = [], bucket_start(end, grain)
    for _ in range(count):
        windows.append((cursor, next_bucket(cursor, grain) - timedelta(days=1)))
        # One day before this bucket's first day always lands inside the previous bucket, whatever
        # the grain and whatever the month length — so normalising that date IS the previous bucket.
        cursor = bucket_start(cursor - timedelta(days=1), grain)
    windows.reverse()
    return windows


def period_windows_labelled(grain, count, end=None):
    """:func:`period_windows` with 4.7's short human label per bucket — the chart's x-axis."""
    grain = _grain(grain)
    return [(start, stop, period_label(start, grain)) for start, stop in period_windows(grain, count, end)]


def window_days(start, end):
    """Inclusive length of a window in days, or ``None`` when it has no lower bound."""
    if start is None or end is None or end < start:
        return None
    return (end - start).days + 1


def _grain(grain):
    return grain if grain in _GRAINS else "month"


def _in_dates(qs, field, start, end):
    """Narrow a queryset on a ``DateField``. A ``None`` bound is simply not applied."""
    if start is not None:
        qs = qs.filter(**{f"{field}__gte": start})
    if end is not None:
        qs = qs.filter(**{f"{field}__lte": end})
    return qs


def _in_moments(qs, field, start, end):
    """Narrow a queryset on a ``DateTimeField`` using a HALF-OPEN tz-aware range.

    Not ``__date__range``: that lookup wraps the column in ``CAST(CONVERT_TZ(...))`` and makes
    ``scm_move_tnt_movedat_idx`` unusable on the module's fastest-growing table (4.7 hit this and
    documented it). ``_moment`` is 4.7's boundary helper — a bare ``date`` on a ``DateTimeField``
    lookup is read as naive UTC and silently shifts the whole window under any other project
    timezone.
    """
    if start is not None:
        qs = qs.filter(**{f"{field}__gte": _moment(start)})
    if end is not None:
        qs = qs.filter(**{f"{field}__lt": _moment(end, end_of_day=True)})
    return qs


# =================================================================================================
# 2. Display formatters
#
# The raw number and its display string are kept strictly separate: `value` is what gets banded,
# stored and compared, `display` is what a tile prints. `_display_for` dispatches on the metric's
# METRIC_META unit so a metric can never be rendered as the wrong kind of quantity.
# =================================================================================================

#: What every formatter prints for "there is no number here". Distinct from "0", which is a fact.
NO_VALUE = "—"


def _money(value):
    """Grouped 2dp with NO currency symbol — deliberately.

    There is no FX table in this repo, so a money figure may legitimately be a sum across currencies
    (the resolver flags that as ``mixed_currency``). Printing "$" over a mixed sum would be a lie
    that looks like a fact.
    """
    return NO_VALUE if value is None else "{:,.2f}".format(float(value))


def _num(value):
    return NO_VALUE if value is None else "{:,.2f}".format(float(value))


def _count(value):
    return NO_VALUE if value is None else "{:,}".format(int(value))


def _pct(value):
    return NO_VALUE if value is None else "{:.1f}%".format(float(value))


def _days(value):
    return NO_VALUE if value is None else "{:.1f} d".format(float(value))


def _hours(value):
    return NO_VALUE if value is None else "{:.1f} h".format(float(value))


def _turns(value):
    # Plain ASCII 'x', not the multiplication sign: these strings reach a cp1252 Windows console
    # through the management commands, where a stray non-cp1252 codepoint is a UnicodeEncodeError.
    return NO_VALUE if value is None else "{:.2f}x".format(float(value))


def _score(value):
    return NO_VALUE if value is None else "{:.1f}".format(float(value))


#: unit (from METRIC_UNIT_CHOICES) -> formatter.
FORMATTERS = {
    "money": _money,
    "num": _num,
    "count": _count,
    "pct": _pct,
    "days": _days,
    "hours": _hours,
    "turns": _turns,
    "score": _score,
}


def _display_for(metric, value):
    """Render ``value`` the way ``metric``'s registry unit says to."""
    unit = (METRIC_META.get(metric) or {}).get("unit", "num")
    return FORMATTERS.get(unit, _num)(value)


def _f(value, places=2):
    """A JSON-safe float (or None) — every number inside ``breakdown``/``rows`` goes through here."""
    if value is None:
        return None
    try:
        return round(float(value), places)
    except (TypeError, ValueError, InvalidOperation):
        return None


def _iso(value):
    """A JSON-safe date/datetime string (or None)."""
    return value.isoformat() if value is not None else None


def _result(metric, value, breakdown=None, rows=None, display=None):
    """The result contract, built in one place so `display` can never disagree with `value`."""
    return {
        "value": value,
        "display": display if display is not None else _display_for(metric, value),
        "breakdown": breakdown if breakdown is not None else {},
        "rows": rows if rows is not None else [],
    }


def _unavailable(metric, reason, **extra):
    """A computed "no number, and here is why" — not an error, and not a zero.

    Zero is a fact ("no dead stock"); this is the absence of one ("no stock to measure"). Rendering
    them the same way is how a page ends up reporting good news it never computed.
    """
    breakdown = {"unavailable": reason}
    breakdown.update(extra)
    return _result(metric, None, breakdown=breakdown)


def _safe_div(numerator, denominator):
    """``numerator / denominator`` as a Decimal, or ``None`` when the denominator is empty."""
    if numerator is None or denominator in (None, ZERO):
        return None
    try:
        return Decimal(numerator) / Decimal(denominator)
    except (DivisionByZero, InvalidOperation, TypeError):
        return None


def _median(values):
    """Median of a list of Decimals (mean of the middle two when even). ``None`` when empty."""
    ordered = sorted(v for v in values if v is not None)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return Decimal(ordered[middle])
    return (Decimal(ordered[middle - 1]) + Decimal(ordered[middle])) / 2


class _Rows(dict):
    """A dict that remembers whether the query behind it hit its row cap.

    A plain dict would force every helper to return a tuple and every caller to unpack it; the flag
    matters too much to make it that easy to drop, because a truncated position silently understates
    every figure derived from it.
    """

    truncated = False


# =================================================================================================
# 3. Banding
# =================================================================================================

def band_for(target, value):
    """``ok`` / ``warning`` / ``critical`` / ``unknown`` for ``value`` against ``target``'s bands.

    **Both ``KpiSnapshot.status_band`` and the alert detector call THIS**, which is what makes it
    impossible for a tile to read green while its own alert fires.

    ``direction`` decides which way "crossing" runs: ``lower_is_better`` bands run
    ``target <= warning <= critical`` and a value at or above a threshold has crossed it;
    ``higher_is_better`` runs the other way and a value at or below a threshold has crossed it. A
    value that has crossed nothing is ``ok`` — including a value between the target and the warning
    band, which is off the goal but not yet a warning.

    ``target_value`` alone does NOT band anything: the bands are the two thresholds. That is not an
    oversight, it is the same rule ``KpiTarget.clean()`` enforces when it refuses ``is_alerting`` on
    a target with neither threshold set (a tick-box that can never fire). If ``target_value`` banded
    on its own, the tile and the detector would disagree about a row the model says cannot alert.
    """
    if target is None or value is None:
        return "unknown"
    warning = getattr(target, "warning_threshold", None)
    critical = getattr(target, "critical_threshold", None)
    if warning is None and critical is None:
        return "unknown"
    try:
        value = Decimal(value)
    except (TypeError, ValueError, InvalidOperation):
        return "unknown"
    lower_is_better = getattr(target, "direction", "") == "lower_is_better"

    def crossed(threshold):
        if threshold is None:
            return False
        return value >= threshold if lower_is_better else value <= threshold

    if crossed(critical):
        return "critical"
    if crossed(warning):
        return "warning"
    return "ok"


# =================================================================================================
# 4. Scope + parameters
# =================================================================================================

class MetricScope:
    """What a metric narrows to: one of ``SCOPE_CHOICES`` plus the object it points at.

    Built from ``KpiTarget.resolved_scope()`` — which returns exactly ``(scope, subject or None)`` —
    or from ``None`` for the whole network. The narrowing methods take the FIELD PATH from the
    queryset's own root (a vendor is ``vendor`` on ``PurchaseOrder`` but
    ``purchase_order__vendor`` on ``GoodsReceiptNote``), so one scope serves every family.

    A scope from the wrong family RAISES rather than narrowing nothing. Silently ignoring it would
    compute the network-wide figure and label it with a supplier's name — the "same tenant is not the
    same subject" failure (L40) in its most expensive form, because it looks exactly like a real
    answer. :func:`compute_metric` rejects the combination first (a metric declares its legal scopes
    in ``METRIC_META``), so reaching this raise means a caller bypassed the entry point.
    """

    __slots__ = ("value", "subject")

    #: Scope values whose subject narrows an item/location axis.
    ITEM_FAMILY = ("all", "category", "location")
    VENDOR_FAMILY = ("all", "vendor")
    CARRIER_FAMILY = ("all", "carrier", "location")

    def __init__(self, value="all", subject=None):
        self.value = value or "all"
        self.subject = subject

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<MetricScope {self.value}:{self.subject!r}>"

    @property
    def is_network(self):
        return self.value == "all"

    @property
    def subject_pk(self):
        """The subject's primary key, for a queryset narrowed against ITS OWN table.

        Django coerces a model instance on a FOREIGN-KEY lookup (``filter(carrier=obj)``) but not on
        a bare ``pk=``/``id=`` one, which raises ``TypeError: int() argument must be ... not
        'Carrier'``. A primary key is accepted by both forms, so the carrier narrowing passes this
        and works whether the queryset is ``Shipment`` (an FK away) or ``Carrier`` itself.
        """
        return getattr(self.subject, "pk", self.subject)

    @property
    def label(self):
        if self.is_network:
            return "Whole network"
        return f"{self.value.title()}: {self.subject}"

    def _reject(self, family):
        raise ValueError(
            f"A '{self.value}' scope cannot narrow a {family} figure — compute_metric() checks a "
            f"metric's legal scopes in METRIC_META before it gets here.")

    def narrow_item_rows(self, qs, item_path="item", location_path="location"):
        """Narrow anything keyed by (item, location): ``StockMove``, ``ReorderRule``, pick lines.

        Category is matched DIRECTLY, not down the ``ItemCategory.parent`` tree — the same one-level
        match every category filter in 4.3 uses. A metric scoped to a parent category therefore
        measures items filed directly under it, which is what the operator picked, and is stated in
        the breakdown rather than guessed at.
        """
        if self.is_network:
            return qs
        if self.value == "category":
            return qs.filter(**{f"{item_path}__category": self.subject})
        if self.value == "location":
            return qs.filter(**{location_path: self.subject})
        return self._reject("stock")

    def narrow_vendor(self, qs, vendor_path="vendor"):
        if self.is_network:
            return qs
        if self.value == "vendor":
            return qs.filter(**{vendor_path: self.subject})
        return self._reject("supplier")

    def narrow_carrier(self, qs, carrier_path="carrier", location_path="location",
                       carrier_name_path=None):
        """Narrow anything keyed by carrier and/or location.

        A path passed as ``None`` means "this queryset has no such column", and a scope that needs
        it is REJECTED rather than silently ignored — a ``Shipment`` has no location and a
        ``FreightInvoice`` has neither, so widening instead of refusing would compute the whole
        network's figure and label it with somebody's warehouse.

        ``carrier_name_path`` exists for the one table that predates 4.6 and stores the haulier as
        free text: ``YardVisit.carrier_name`` (its own ``help_text`` says "free text until 4.6
        TMS"). Under a carrier scope it is matched case-insensitively against the carrier's party
        name. That is best-effort in exactly the way ``sku_hint`` is — a differently-spelled haulier
        is not counted — so :func:`_r_dwell_hours_avg` reports the matched row count and prints the
        caveat rather than letting a silent zero read as "no dwell".
        """
        if self.is_network:
            return qs
        if self.value == "carrier":
            if carrier_name_path:
                name = (getattr(self.subject, "name", "") or "").strip()
                return qs.filter(**{f"{carrier_name_path}__iexact": name}) if name else qs.none()
            if carrier_path:
                # The PK, not the instance — see subject_pk. The carrier scorecard narrows the
                # Carrier table itself, where `pk=<Carrier>` is a TypeError.
                return qs.filter(**{carrier_path: self.subject_pk})
        elif self.value == "location" and location_path:
            return qs.filter(**{location_path: self.subject})
        return self._reject("carrier")


#: The whole-network scope — the default for every page that has no target behind it.
NETWORK = MetricScope("all", None)


class MetricParams:
    """The metric's own knobs: ``days`` (the N in its definition) and ``pct``.

    Resolved from a ``KpiTarget`` when one exists and from :data:`METRIC_PARAM_DEFAULTS` when it does
    not, so an analytics page renders a true number on a tenant that has never created a target.
    """

    __slots__ = ("days", "pct")

    def __init__(self, days=None, pct=None):
        self.days = days
        self.pct = pct

    def __repr__(self):  # pragma: no cover - debugging aid
        return f"<MetricParams days={self.days} pct={self.pct}>"

    @classmethod
    def for_metric(cls, metric, target=None):
        defaults = METRIC_PARAM_DEFAULTS.get(metric, {})
        days = getattr(target, "parameter_days", None) if target is not None else None
        pct = getattr(target, "parameter_pct", None) if target is not None else None
        return cls(days=days if days else defaults.get("days"),
                   pct=pct if pct is not None else defaults.get("pct"))


#: What a bare four-argument resolver call gets. compute_metric always passes the metric's own.
DEFAULT_PARAMS = MetricParams(days=DEAD_STOCK_DAYS, pct=CARRYING_PCT)


def _coerce_scope(scope, target=None):
    """Accept a ``MetricScope``, a ``(value, subject)`` pair, a ``KpiTarget``, or ``None``."""
    if isinstance(scope, MetricScope):
        return scope
    if scope is None and target is not None and hasattr(target, "resolved_scope"):
        return MetricScope(*target.resolved_scope())
    if scope is None:
        return NETWORK
    if hasattr(scope, "resolved_scope"):
        return MetricScope(*scope.resolved_scope())
    if isinstance(scope, (tuple, list)) and len(scope) == 2:
        return MetricScope(scope[0], scope[1])
    if isinstance(scope, str):
        return MetricScope(scope, None)
    raise ValueError(f"Cannot read {scope!r} as a metric scope.")


# =================================================================================================
# 5. Supplier signal statistics — shared with 4.2's scorecard
# =================================================================================================

def supplier_delivery_stats(tenant, party, start, end):
    """On-time delivery for one supplier (or the whole network when ``party`` is None).

    Returns ``{"receipts", "datable", "on_time", "late", "pct"}`` where ``pct`` is a ``Decimal`` or
    ``None``. A receipt only counts if its purchase order carried an ``expected_date`` — with nothing
    promised there is nothing to be late against, and scoring an undated receipt as "on time" is how
    an OTD number quietly becomes 100%.

    **Twin: ``SupplierScorecard.recompute_from_signals`` (4.2).** That method derives its delivery
    score from exactly this arithmetic — received-status ``GoodsReceiptNote`` rows in the period
    whose ``receipt_date`` is on or before ``PurchaseOrder.expected_date``, over the receipts that
    have an expected date at all. This function is deliberately shipped STANDALONE rather than by
    refactoring 4.2 to call it: 4.2 is shipped and tested, and rewriting a green, load-bearing method
    during an unrelated build is the over-correction L38 is about. **A parity test is owed** —
    ``supplier_delivery_stats(t, p, s, e)["pct"]`` must equal the ``delivery_score`` a scorecard for
    the same party and window computes. If the two ever diverge, THIS is the copy to change, because
    4.2's is the one with users.
    """
    rows = _delivery_rows(tenant, party, start, end)
    datable = sum(row["datable"] for row in rows)
    on_time = sum(row["on_time"] for row in rows)
    pct = _safe_div(Decimal(on_time) * HUNDRED, Decimal(datable)) if datable else None
    return {
        "receipts": datable,
        "datable": datable,
        "on_time": on_time,
        "late": datable - on_time,
        "pct": pct,
    }


def supplier_quality_stats(tenant, party, start, end):
    """Reject rate for one supplier (or the whole network when ``party`` is None).

    Returns ``{"received", "rejected", "presented", "reject_pct", "quality_pct"}``. The denominator
    is received PLUS rejected — what the supplier actually presented — not just what was accepted;
    dividing by the accepted quantity alone would make a supplier look better the more it got wrong.

    **Twin: ``SupplierScorecard.recompute_from_signals`` (4.2)**, whose quality score is
    ``100 - rejected * 100 / (received + rejected)`` over the same receipts. Shipped standalone for
    the reason given in :func:`supplier_delivery_stats`; **a parity test is owed** asserting
    ``quality_pct`` equals a scorecard's ``quality_score`` for the same party and window.
    """
    rows = _quality_rows(tenant, party, start, end)
    received = sum((row["received"] for row in rows), ZERO)
    rejected = sum((row["rejected"] for row in rows), ZERO)
    presented = received + rejected
    reject_pct = _safe_div(rejected * HUNDRED, presented) if presented > ZERO else None
    return {
        "received": received,
        "rejected": rejected,
        "presented": presented,
        "reject_pct": reject_pct,
        "quality_pct": (HUNDRED - reject_pct) if reject_pct is not None else None,
    }


def _delivery_rows(tenant, party, start, end):
    """Per-supplier on-time counts in ONE grouped query — the leaderboard behind both OTD callers."""
    qs = GoodsReceiptNote.objects.filter(tenant=tenant, status="received")
    # An order with no promised date cannot be late — see the note in supplier_delivery_stats.
    qs = qs.exclude(purchase_order__expected_date__isnull=True)
    qs = _in_dates(qs, "receipt_date", start, end)
    if party is not None:
        qs = qs.filter(purchase_order__vendor=party)
    rows = (qs.values("purchase_order__vendor_id", "purchase_order__vendor__name")
            .annotate(datable=Count("id"),
                      on_time=Count("id", filter=Q(receipt_date__lte=F("purchase_order__expected_date"))))
            .order_by("-datable"))
    return [{"vendor_id": row["purchase_order__vendor_id"],
             "vendor": row["purchase_order__vendor__name"],
             "datable": row["datable"] or 0,
             "on_time": row["on_time"] or 0}
            for row in rows[:MAX_GROUP_ROWS]]


def _quality_rows(tenant, party, start, end):
    """Per-supplier received/rejected quantities in ONE grouped query.

    Rooted on ``GoodsReceiptLine``, which has no tenant column of its own (it is a child row) — the
    tenant comes through ``goods_receipt__tenant``, exactly as 4.2 reaches it.
    """
    qs = GoodsReceiptLine.objects.filter(goods_receipt__tenant=tenant,
                                         goods_receipt__status="received")
    qs = _in_dates(qs, "goods_receipt__receipt_date", start, end)
    if party is not None:
        qs = qs.filter(goods_receipt__purchase_order__vendor=party)
    rows = (qs.values("goods_receipt__purchase_order__vendor_id",
                      "goods_receipt__purchase_order__vendor__name")
            .annotate(received=Sum("quantity_received"), rejected=Sum("quantity_rejected")))
    return [{"vendor_id": row["goods_receipt__purchase_order__vendor_id"],
             "vendor": row["goods_receipt__purchase_order__vendor__name"],
             "received": row["received"] or ZERO,
             "rejected": row["rejected"] or ZERO}
            for row in rows[:MAX_GROUP_ROWS]]


# =================================================================================================
# 6. Shared inventory machinery
# =================================================================================================

def _stock_position(tenant, scope, as_of, positive_only=True):
    """``{item_id: {sku, name, qty, cost, value}}`` — derived on-hand and its value, in ONE query.

    On-hand is the ``StockMove`` aggregate (the only source of truth for quantity — there is no
    stored quantity anywhere in 4.3). Value is quantity x the item's cached weighted-average cost,
    i.e. ``Item.total_value()``'s documented quick figure. The authoritative FIFO/LIFO/WAC number is
    4.3's valuation report, which walks every cost layer per item; that is far too expensive for a
    page that renders several metrics at once, so every money figure derived from this helper says
    ``valuation: "on-hand x cached average cost"`` in its breakdown.
    """
    qs = _in_moments(scope.narrow_item_rows(StockMove.objects.filter(tenant=tenant)),
                     "moved_at", None, as_of)
    rows = (qs.values("item_id", "item__sku", "item__name", "item__average_cost")
            .annotate(qty=Sum("quantity")))
    fetched = list(rows[:MAX_ITEM_ROWS + 1])
    position = _Rows()
    position.truncated = len(fetched) > MAX_ITEM_ROWS
    for row in fetched[:MAX_ITEM_ROWS]:
        qty = row["qty"] or ZERO
        if positive_only and qty <= ZERO:
            continue
        cost = row["item__average_cost"] or ZERO
        position[row["item_id"]] = {
            "sku": row["item__sku"], "name": row["item__name"],
            "qty": qty, "cost": cost, "value": qty * cost,
        }
    return position


def _position_value(position):
    return sum((row["value"] for row in position.values()), ZERO)


def _effective_window(tenant, scope, start, end):
    """``(start, days, note)`` — the window's real length, resolving an open-ended "all time".

    An all-time window has no lower bound, so any rate expressed "per year" needs a span. Rather than
    invent one, this asks the ledger for its own first movement — ONE aggregate, and only when the
    window is genuinely open-ended.
    """
    days = window_days(start, end)
    if days is not None:
        return start, days, ""
    first = (scope.narrow_item_rows(StockMove.objects.filter(tenant=tenant))
             .aggregate(first=Min("moved_at"))["first"])
    if first is None:
        return start, None, "No stock movements to measure a window against."
    first_date = timezone.localtime(first).date() if timezone.is_aware(first) else first.date()
    return first_date, window_days(first_date, end), (
        f"All-time window measured from the first stock movement ({first_date.isoformat()}).")


def _turnover_figures(tenant, scope, start, end):
    """Everything both turnover and days-on-hand need, in three grouped queries.

    Cost of goods issued over the window (``issue`` + ``consumption``, ``transfer`` excluded), the
    opening and closing stock value, and the per-item cost rows behind the total. Turnover and DOH
    are the same division read two ways, so they share this rather than each running its own ledger
    pass and reporting figures that do not reconcile.
    """
    moves = StockMove.objects.filter(tenant=tenant, move_type__in=COGS_MOVE_TYPES)
    moves = _in_moments(scope.narrow_item_rows(moves), "moved_at", start, end)
    cost_rows = (moves.values("item_id", "item__sku", "item__name")
                 .annotate(cost=Sum(F("quantity") * F("unit_cost"), output_field=_DEC),
                           qty=Sum("quantity"))
                 .order_by("cost"))  # most negative first == most cost issued
    fetched = list(cost_rows[:MAX_ITEM_ROWS])
    # Outbound quantities are signed negative in the append-only ledger, so the cost of what left is
    # the negation of the sum. Same convention 4.7's demand_series negates.
    cost_issued = sum((-(row["cost"] or ZERO) for row in fetched), ZERO)

    effective_start, span, note = _effective_window(tenant, scope, start, end)
    opening = (_stock_position(tenant, scope, effective_start - timedelta(days=1))
               if effective_start is not None else _Rows())
    closing = _stock_position(tenant, scope, end)
    opening_value, closing_value = _position_value(opening), _position_value(closing)
    if effective_start is None or not opening:
        average_value, basis = closing_value, "closing stock value (no opening position)"
    else:
        average_value = (opening_value + closing_value) / 2
        basis = "mean of opening and closing stock value"
    return {
        "cost_issued": cost_issued,
        "opening_value": opening_value,
        "closing_value": closing_value,
        "average_value": average_value,
        "basis": basis,
        "span_days": span,
        "window_note": note,
        "item_rows": fetched,
        "truncated": closing.truncated or opening.truncated,
    }


# =================================================================================================
# 7. INVENTORY resolvers
#
# Group -> the `inventory_analytics` page. Everything here is derived from the append-only StockMove
# ledger plus the item/lot/reorder masters; nothing is stored and nothing is posted.
# =================================================================================================

def _r_inv_turnover(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Cost of stock issued over the window / average stock value, ANNUALISED.

    A target ("we run six turns") is always an annual figure, so the window rate is scaled to a year
    and the raw window rate is reported alongside it. ``transfer`` moves are excluded because an
    internal relocation is a signed pair that would count itself out and back in again.
    """
    figures = _turnover_figures(tenant, scope, start, end)
    window_turns = _safe_div(figures["cost_issued"], figures["average_value"])
    if window_turns is None:
        return _unavailable("inv_turnover",
                            "No stock value to turn over in this window.",
                            cost_issued=_f(figures["cost_issued"]),
                            average_inventory_value=_f(figures["average_value"]))
    span = figures["span_days"]
    annualised = window_turns * DAYS_PER_YEAR / Decimal(span) if span else window_turns
    rows = [{"sku": row["item__sku"], "name": row["item__name"],
             "cost_issued": _f(-(row["cost"] or ZERO)), "quantity_issued": _f(-(row["qty"] or ZERO), 4)}
            for row in figures["item_rows"][:MAX_DETAIL_ROWS]]
    return _result("inv_turnover", annualised, breakdown={
        "cost_issued": _f(figures["cost_issued"]),
        "opening_value": _f(figures["opening_value"]),
        "closing_value": _f(figures["closing_value"]),
        "average_inventory_value": _f(figures["average_value"]),
        "average_basis": figures["basis"],
        "window_turns": _f(window_turns, 4),
        "window_days": span,
        "annualised": True,
        "move_types": list(COGS_MOVE_TYPES),
        "excludes": "transfer",
        "note": ("Counts issues (customer demand) AND consumption (work-order draws); transfers are "
                 "excluded because an internal relocation is posted as a signed pair and would be "
                 "counted twice."),
        "valuation": "on-hand x cached average cost",
        "truncated": figures["truncated"],
        "window_note": figures["window_note"],
    }, rows=rows)


def _r_inv_days_on_hand(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """365 / annualised turns — how long the stock on hand would last at the window's issue rate."""
    figures = _turnover_figures(tenant, scope, start, end)
    window_turns = _safe_div(figures["cost_issued"], figures["average_value"])
    span = figures["span_days"]
    if window_turns is None or window_turns <= ZERO or not span:
        return _unavailable("inv_days_on_hand",
                            "Nothing was issued from this stock in the window, so it has no "
                            "measurable days of cover.",
                            cost_issued=_f(figures["cost_issued"]),
                            average_inventory_value=_f(figures["average_value"]))
    annualised = window_turns * DAYS_PER_YEAR / Decimal(span)
    days = DAYS_PER_YEAR / annualised
    return _result("inv_days_on_hand", days, breakdown={
        "annualised_turns": _f(annualised, 4),
        "cost_issued": _f(figures["cost_issued"]),
        "average_inventory_value": _f(figures["average_value"]),
        "average_basis": figures["basis"],
        "window_days": span,
        "move_types": list(COGS_MOVE_TYPES),
        "excludes": "transfer",
        "valuation": "on-hand x cached average cost",
        "truncated": figures["truncated"],
    })


def _r_inv_dead_stock_value(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Value of stock still on hand that has not been issued or consumed for N days.

    Two grouped queries: the on-hand position as at the window end, and the set of items that DID
    move outbound inside the N-day tail. Everything holding stock and absent from that set is dead.
    """
    days = params.days or DEAD_STOCK_DAYS
    cutoff = end - timedelta(days=days)
    position = _stock_position(tenant, scope, end)
    if not position:
        return _unavailable("inv_dead_stock_value", "Nothing is on hand in this scope.",
                            parameter_days=days)
    moved = StockMove.objects.filter(tenant=tenant, move_type__in=COGS_MOVE_TYPES,
                                     item_id__in=list(position.keys()))
    moved = _in_moments(scope.narrow_item_rows(moved), "moved_at", cutoff, end)
    live_ids = set(moved.values_list("item_id", flat=True).distinct()[:MAX_ITEM_ROWS])

    dead = [(item_id, row) for item_id, row in position.items() if item_id not in live_ids]
    dead.sort(key=lambda pair: pair[1]["value"], reverse=True)
    total = sum((row["value"] for _, row in dead), ZERO)
    on_hand_total = _position_value(position)
    rows = [{"sku": row["sku"], "name": row["name"], "quantity": _f(row["qty"], 4),
             "unit_cost": _f(row["cost"], 4), "value": _f(row["value"])}
            for _, row in dead[:MAX_DETAIL_ROWS]]
    return _result("inv_dead_stock_value", total, breakdown={
        "parameter_days": days,
        "cutoff": _iso(cutoff),
        "dead_items": len(dead),
        "items_on_hand": len(position),
        "stock_value": _f(on_hand_total),
        "dead_share_pct": _f(_safe_div(total * HUNDRED, on_hand_total)),
        "move_types": list(COGS_MOVE_TYPES),
        "valuation": "on-hand x cached average cost",
        "truncated": position.truncated,
        "note": (f"Dead = on hand at {end.isoformat()} with no issue or consumption movement since "
                 f"{cutoff.isoformat()}."),
    }, rows=rows)


def _r_inv_aging_over_days_value(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Value of the remaining FIFO cost layers older than N days, plus the standard age buckets.

    This is the one resolver that needs individual ledger rows: an age bucket is a property of the
    cost LAYER that is still on hand, which only a FIFO walk can identify. It is bounded twice — to
    the highest-value :data:`MAX_AGING_ITEMS` items and to :data:`MAX_LEDGER_ROWS` moves — and both
    caps are LIMITs on the query, not measurements of a list already built (L40).

    Transfers are excluded from the walk for the same reason 4.3's valuation report excludes them:
    an internal relocation would consume a real layer on the way out and create a fake
    average-cost layer on the way in, drifting a FIFO item towards weighted average.
    """
    days = params.days or AGING_DAYS
    position = _stock_position(tenant, scope, end)
    if not position:
        return _unavailable("inv_aging_over_days_value", "Nothing is on hand in this scope.",
                            parameter_days=days)
    ranked = sorted(position.items(), key=lambda pair: pair[1]["value"], reverse=True)
    item_ids = [item_id for item_id, _ in ranked[:MAX_AGING_ITEMS]]

    moves = StockMove.objects.filter(tenant=tenant, item_id__in=item_ids).exclude(move_type="transfer")
    moves = _in_moments(scope.narrow_item_rows(moves), "moved_at", None, end)
    fetched = list(moves.order_by("item_id", "moved_at", "id")
                   .values_list("item_id", "quantity", "unit_cost", "moved_at")[:MAX_LEDGER_ROWS + 1])
    truncated = len(fetched) > MAX_LEDGER_ROWS or len(ranked) > MAX_AGING_ITEMS
    if len(fetched) > MAX_LEDGER_ROWS:
        # Read the partial item off the PROBE row (index MAX_LEDGER_ROWS) before slicing it away —
        # not off the last kept row. Rows are ordered by item_id, so when the probe belongs to a new
        # item the last kept item was fetched COMPLETELY and dropping it threw away a correct walk;
        # the item actually cut in half is always the probe's. When the probe's item has no rows
        # inside the slice the filter simply matches nothing, which is the right no-op.
        partial = fetched[MAX_LEDGER_ROWS][0]
        fetched = [row for row in fetched[:MAX_LEDGER_ROWS] if row[0] != partial]

    ledger = {}
    for item_id, quantity, unit_cost, moved_at in fetched:
        ledger.setdefault(item_id, []).append((quantity or ZERO, unit_cost or ZERO, moved_at))

    buckets = [("0-30", 0, 30), ("31-60", 31, 60), ("61-90", 61, 90),
               ("91-180", 91, 180), ("181+", 181, None)]
    bucket_totals = {name: ZERO for name, _, _ in buckets}
    over_total, item_over = ZERO, {}
    for item_id, entries in ledger.items():
        layers = [[qty, cost, moved_at] for qty, cost, moved_at in entries if qty > ZERO]
        outbound = sum((-qty for qty, _, _ in entries if qty < ZERO), ZERO)
        for layer in layers:  # FIFO: the oldest layers are consumed first
            if outbound <= ZERO:
                break
            take = min(layer[0], outbound)
            layer[0] -= take
            outbound -= take
        for remaining, cost, moved_at in layers:
            if remaining <= ZERO:
                continue
            moved_date = (timezone.localtime(moved_at).date()
                          if timezone.is_aware(moved_at) else moved_at.date())
            age = (end - moved_date).days
            value = remaining * cost
            for name, low, high in buckets:
                if age >= low and (high is None or age <= high):
                    bucket_totals[name] += value
                    break
            if age > days:
                over_total += value
                item_over[item_id] = item_over.get(item_id, ZERO) + value

    ranked_over = sorted(item_over.items(), key=lambda pair: pair[1], reverse=True)
    rows = [{"sku": position[item_id]["sku"], "name": position[item_id]["name"],
             "value_over_days": _f(value)}
            for item_id, value in ranked_over[:MAX_DETAIL_ROWS] if item_id in position]
    return _result("inv_aging_over_days_value", over_total, breakdown={
        "parameter_days": days,
        "as_of": _iso(end),
        "buckets": {name: _f(total) for name, total in bucket_totals.items()},
        "aging_items": len(item_over),
        "items_walked": len(ledger),
        "moves_walked": len(fetched),
        "excludes": "transfer",
        "valuation": "remaining FIFO cost layers",
        "truncated": truncated or position.truncated,
        "note": ("Age is measured on the remaining FIFO cost layer, not on the item. Transfers are "
                 "excluded from the walk (4.3's valuation report makes the same exclusion), so a "
                 "relocated layer keeps its original age."),
    }, rows=rows)


def _r_inv_expiry_risk_value(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Value of on-hand stock in lots expiring within N days — and what has already expired.

    ONE grouped query over the ledger joined to ``LotSerial``: on-hand per lot, valued at the item's
    average cost. Already-expired stock still sitting on hand is reported separately in the breakdown
    rather than folded into the headline, because the two demand different actions.
    """
    days = params.days or EXPIRY_DAYS
    horizon = end + timedelta(days=days)
    qs = StockMove.objects.filter(tenant=tenant, lot_serial__isnull=False,
                                  lot_serial__expiry_date__isnull=False,
                                  lot_serial__expiry_date__lte=horizon)
    qs = _in_moments(scope.narrow_item_rows(qs), "moved_at", None, end)
    rows = (qs.values("lot_serial_id", "lot_serial__number", "lot_serial__expiry_date",
                      "lot_serial__status", "item__sku", "item__name", "item__average_cost")
            .annotate(qty=Sum("quantity")))
    fetched = list(rows[:MAX_ITEM_ROWS + 1])
    truncated = len(fetched) > MAX_ITEM_ROWS

    expiring, expired, detail = ZERO, ZERO, []
    for row in fetched[:MAX_ITEM_ROWS]:
        qty = row["qty"] or ZERO
        if qty <= ZERO:
            continue
        value = qty * (row["item__average_cost"] or ZERO)
        expiry = row["lot_serial__expiry_date"]
        already = expiry < end
        if already:
            expired += value
        else:
            expiring += value
        detail.append({"lot": row["lot_serial__number"], "sku": row["item__sku"],
                       "name": row["item__name"], "expiry_date": _iso(expiry),
                       "days_left": (expiry - end).days, "status": row["lot_serial__status"],
                       "quantity": _f(qty, 4), "value": _f(value), "expired": already})
    if not detail:
        # No lot is expiring. That is a genuine zero when there IS stock — including a tenant whose
        # items are all tracking='none', where nothing CAN expire — but on a scope holding no stock
        # at all a green "0.00" reads as "we are clean" when the truth is "we have no data". The
        # existence check costs one query and only ever runs on this empty path, so the normal
        # render stays a single query. Every sibling inventory metric draws the same line.
        if not _in_moments(scope.narrow_item_rows(StockMove.objects.filter(tenant=tenant)),
                           "moved_at", None, end).exists():
            return _unavailable("inv_expiry_risk_value", "Nothing is on hand in this scope.",
                                parameter_days=days)
    detail.sort(key=lambda row: (row["days_left"], -(row["value"] or 0)))
    return _result("inv_expiry_risk_value", expiring, breakdown={
        "parameter_days": days,
        "horizon": _iso(horizon),
        "expiring_value": _f(expiring),
        "already_expired_value": _f(expired),
        "lots": len(detail),
        "valuation": "on-hand x cached average cost",
        "truncated": truncated,
        "note": ("Headline counts lots expiring between the window end and the horizon. Stock in "
                 "lots that have ALREADY expired is reported separately — it is a write-off "
                 "decision, not a sell-through one."),
    }, rows=detail[:MAX_DETAIL_ROWS])


def _r_inv_excess_vs_policy_value(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Value of stock held above the replenishment policy's order-up-to level.

    The ceiling is ``reorder_point + reorder_quantity`` — the classic min/max order-up-to level,
    which is the most stock the policy ever intends to hold — falling back to ``safety_stock`` when a
    rule carries neither. Stated explicitly in the breakdown because "excess" is meaningless without
    saying excess of WHAT.

    Two queries: the rules, and ``ReorderRule.on_hand_map`` for every rule's on-hand in ONE grouped
    aggregate. Never ``Item.on_hand()`` in a loop.
    """
    rules = list(scope.narrow_item_rows(
        ReorderRule.objects.filter(tenant=tenant, is_active=True)
    ).select_related("item", "location")[:MAX_ITEM_ROWS + 1])
    truncated = len(rules) > MAX_ITEM_ROWS
    rules = rules[:MAX_ITEM_ROWS]
    if not rules:
        return _unavailable("inv_excess_vs_policy_value",
                            "No active reorder rules in this scope, so there is no policy to be "
                            "in excess of.")
    on_hand = ReorderRule.on_hand_map(tenant, rules)
    total, detail = ZERO, []
    for rule in rules:
        qty = on_hand.get((rule.item_id, rule.location_id), ZERO)
        ceiling = (rule.reorder_point or ZERO) + (rule.reorder_quantity or ZERO)
        if ceiling <= ZERO:
            ceiling = rule.safety_stock or ZERO
        excess = qty - ceiling
        if excess <= ZERO:
            continue
        value = excess * (rule.item.average_cost or ZERO)
        total += value
        detail.append({"sku": rule.item.sku, "name": rule.item.name,
                       "location": rule.location.code, "on_hand": _f(qty, 4),
                       "policy_ceiling": _f(ceiling, 4), "excess_quantity": _f(excess, 4),
                       "value": _f(value)})
    detail.sort(key=lambda row: -(row["value"] or 0))
    return _result("inv_excess_vs_policy_value", total, breakdown={
        "rules_checked": len(rules),
        "rules_in_excess": len(detail),
        "policy": "reorder_point + reorder_quantity (order-up-to level), or safety_stock when unset",
        "valuation": "excess quantity x cached average cost",
        "truncated": truncated,
    }, rows=detail[:MAX_DETAIL_ROWS])


def _r_inv_carrying_cost(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Stock value x the annual carrying rate, pro-rated to the window.

    The rate is a policy number (storage, capital, insurance, shrinkage), not something derivable
    from any row in 4.1-4.10 — it comes from ``KpiTarget.parameter_pct`` and falls back to
    :data:`CARRYING_PCT`.
    """
    pct = params.pct if params.pct is not None else CARRYING_PCT
    position = _stock_position(tenant, scope, end)
    stock_value = _position_value(position)
    _, span, note = _effective_window(tenant, scope, start, end)
    if stock_value <= ZERO:
        return _unavailable("inv_carrying_cost", "Nothing is on hand in this scope.",
                            parameter_pct=_f(pct))
    annual = stock_value * Decimal(pct) / HUNDRED
    if span:
        cost = annual * Decimal(span) / DAYS_PER_YEAR
        prorated = True
    else:
        cost, prorated = annual, False
    return _result("inv_carrying_cost", cost, breakdown={
        "parameter_pct": _f(pct),
        "stock_value": _f(stock_value),
        "annual_carrying_cost": _f(annual),
        "window_days": span,
        "prorated": prorated,
        "items_on_hand": len(position),
        "valuation": "on-hand x cached average cost",
        "truncated": position.truncated,
        "window_note": note,
    })


def _r_inv_stockout_count(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """How many active reorder rules are at or below their reorder point, right now.

    A count and its trend only — the live, actionable list stays 4.3's ``scm:reorder_alerts``, which
    also offers the one-click hand-off into a requisition. Two views of the same rows would drift.

    This is a POSITION, not a window: a reorder point is about stock as it stands. ``end`` bounds the
    on-hand aggregate so a historic snapshot is still truthful.
    """
    rules = list(scope.narrow_item_rows(
        ReorderRule.objects.filter(tenant=tenant, is_active=True)
    ).select_related("item", "location")[:MAX_ITEM_ROWS + 1])
    truncated = len(rules) > MAX_ITEM_ROWS
    rules = rules[:MAX_ITEM_ROWS]
    if not rules:
        return _unavailable("inv_stockout_count", "No active reorder rules in this scope.")
    on_hand = ReorderRule.on_hand_map(tenant, rules)
    below = []
    for rule in rules:
        qty = on_hand.get((rule.item_id, rule.location_id), ZERO)
        if qty <= (rule.reorder_point or ZERO):
            below.append({"sku": rule.item.sku, "name": rule.item.name,
                          "location": rule.location.code, "on_hand": _f(qty, 4),
                          "reorder_point": _f(rule.reorder_point, 4),
                          "shortfall": _f((rule.reorder_point or ZERO) - qty, 4),
                          "suggested": _f(rule.suggested_quantity(on_hand=qty), 4)})
    below.sort(key=lambda row: -(row["shortfall"] or 0))
    return _result("inv_stockout_count", Decimal(len(below)), breakdown={
        "rules_checked": len(rules),
        "rules_below_point": len(below),
        "coverage_pct": _f(_safe_div(Decimal(len(rules) - len(below)) * HUNDRED, Decimal(len(rules)))),
        "truncated": truncated,
        "note": "The live list is 4.3's Reorder Alerts page; 4.11 shows the count and its trend.",
    }, rows=below[:MAX_DETAIL_ROWS])


def _r_inv_abc_a_share_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Share of stock value held in items 4.7 classified A.

    Reads the STORED ``ReorderRule.abc_class`` (and reports ``xyz_class`` alongside it). 4.7 derives
    that Pareto rank from sales revenue in one grouped pass; deriving a second, differently-shaped
    ranking here would give the tenant two contradictory "A lists".

    An item with rules at several locations can be classed differently at each; the strongest class
    wins for the item, and the breakdown says so.
    """
    position = _stock_position(tenant, scope, end)
    if not position:
        return _unavailable("inv_abc_a_share_pct", "Nothing is on hand in this scope.")
    rows = (scope.narrow_item_rows(ReorderRule.objects.filter(tenant=tenant, is_active=True))
            .exclude(abc_class="")
            .values_list("item_id", "abc_class", "xyz_class")[:MAX_ITEM_ROWS])
    order = {"A": 3, "B": 2, "C": 1}
    best, xyz = {}, {}
    for item_id, abc, xyz_class in rows:
        if order.get(abc, 0) > order.get(best.get(item_id, ""), 0):
            best[item_id] = abc
        if xyz_class:
            xyz.setdefault(item_id, xyz_class)

    totals = {"A": ZERO, "B": ZERO, "C": ZERO, "": ZERO}
    for item_id, row in position.items():
        totals[best.get(item_id, "")] += row["value"]
    stock_value = sum(totals.values(), ZERO)
    share = _safe_div(totals["A"] * HUNDRED, stock_value)
    if share is None:
        return _unavailable("inv_abc_a_share_pct", "Stock in this scope has no value to apportion.")
    ranked = sorted(((item_id, row) for item_id, row in position.items() if best.get(item_id) == "A"),
                    key=lambda pair: pair[1]["value"], reverse=True)
    detail = [{"sku": row["sku"], "name": row["name"], "abc_class": "A",
               "xyz_class": xyz.get(item_id, ""), "quantity": _f(row["qty"], 4),
               "value": _f(row["value"])}
              for item_id, row in ranked[:MAX_DETAIL_ROWS]]
    return _result("inv_abc_a_share_pct", share, breakdown={
        "stock_value": _f(stock_value),
        "class_value": {name or "unclassified": _f(value) for name, value in totals.items()},
        "classified_items": len(best),
        "items_on_hand": len(position),
        "source": "ReorderRule.abc_class (derived by 4.7 from sales revenue) — read, not recomputed",
        "multi_location": "An item classed differently per location takes its strongest class.",
        "truncated": position.truncated,
    }, rows=detail)


# =================================================================================================
# 8. PROCUREMENT resolvers
#
# Group -> the `spend_analytics` page. Over PurchaseOrder(+Line), PurchaseRequisition, RFQQuote,
# GoodsReceiptNote(+Line), SupplierContract and SupplierScorecard.
#
# CAVEAT THAT APPLIES TO THE WHOLE GROUP, and must be printed on the page rather than buried here:
# 4.1's PurchaseOrderLine carries free-text `item_description` / `sku_hint` and has NO Item FK. So
# there is no real item taxonomy behind procurement spend: the category axis is GL-account based,
# and any per-SKU figure is a best-effort match on the free-text `sku_hint`. Every resolver that
# leans on either says so in its own breakdown.
# =================================================================================================

#: Repeated verbatim into the breakdown of every sku_hint-based figure.
SKU_HINT_CAVEAT = ("PO lines carry free-text sku_hint and no Item FK, so SKU grouping is a "
                   "best-effort text match — lines with a blank or mistyped hint are not grouped.")
GL_AXIS_CAVEAT = ("Spend category is the line's GL account, not an item taxonomy: 4.1 PO lines have "
                  "no Item FK.")


def _spend_orders(tenant, scope, start, end):
    """The committed purchase orders inside the window — the base queryset of the whole group."""
    qs = scope.narrow_vendor(PurchaseOrder.objects.filter(tenant=tenant,
                                                          status__in=SPEND_PO_STATUSES))
    return _in_dates(qs, "order_date", start, end)


def _currency_split(qs, path="currency__code"):
    """``(rows, mixed)`` — spend per currency code and whether the window spans more than one.

    There is NO FX-rate table in this repo. Totals are therefore sums of face values in whatever
    currency each document was raised in, and this is how a page learns it must say so. Inventing a
    rate would be worse than the caveat.
    """
    rows = list(qs.values(path).annotate(total=Sum("total"), orders=Count("id"))[:MAX_GROUP_ROWS])
    codes = [row[path] or "(none)" for row in rows]
    return rows, len(codes) > 1


def _r_spend_total(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Total committed purchase-order value in the window, plus the spend cube's three axes.

    Four grouped queries: by currency (which also yields the total and the order count), by supplier,
    by GL account and by receiving business unit.
    """
    orders = _spend_orders(tenant, scope, start, end)
    currency_rows, mixed = _currency_split(orders)
    total = sum((row["total"] or ZERO for row in currency_rows), ZERO)
    order_count = sum(row["orders"] or 0 for row in currency_rows)
    if not order_count:
        return _unavailable("spend_total", "No committed purchase orders in this window.",
                            statuses=list(SPEND_PO_STATUSES))

    by_vendor = list(orders.values("vendor_id", "vendor__name")
                     .annotate(total=Sum("total"), orders=Count("id"))
                     .order_by("-total")[:MAX_DETAIL_ROWS])
    by_account = list(PurchaseOrderLine.objects.filter(purchase_order__in=orders)
                      .values("gl_account__code", "gl_account__name")
                      .annotate(total=Sum("line_total"))
                      .order_by("-total")[:MAX_DETAIL_ROWS])
    by_unit = list(orders.values("ship_to__name").annotate(total=Sum("total"))
                   .order_by("-total")[:MAX_DETAIL_ROWS])
    return _result("spend_total", total, breakdown={
        "orders": order_count,
        "suppliers": len(by_vendor),
        "average_order_value": _f(_safe_div(total, Decimal(order_count))),
        "mixed_currency": mixed,
        "by_currency": {(row["currency__code"] or "(none)"): _f(row["total"]) for row in currency_rows},
        "by_account": {(row["gl_account__code"] or "(unposted)"): _f(row["total"]) for row in by_account},
        "by_business_unit": {(row["ship_to__name"] or "(unassigned)"): _f(row["total"]) for row in by_unit},
        "statuses": list(SPEND_PO_STATUSES),
        "category_axis": GL_AXIS_CAVEAT,
        "currency_note": ("No FX table exists in this build — totals are face values summed across "
                          "currencies. Read the per-currency split when mixed_currency is true."),
    }, rows=[{"vendor": row["vendor__name"], "orders": row["orders"], "total": _f(row["total"]),
              "share_pct": _f(_safe_div((row["total"] or ZERO) * HUNDRED, total))}
             for row in by_vendor])


def _r_spend_off_contract_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Share of spend placed with no active supplier contract covering the order date.

    ONE query: each order is annotated with an ``EXISTS`` against its vendor's contracts, and the
    result is grouped on that flag. The alternative — pulling every order into Python and matching
    date windows there — is the same answer at N times the cost.

    **Caveat, and it belongs on the page:** cover is VENDOR-level. 4.2 has no contract-to-item
    linkage, so an order to a contracted supplier counts as on-contract even if the specific line was
    never in the agreement. The unrequisitioned share is reported alongside as the maverick-buying
    proxy 4.1 can actually evidence.
    """
    orders = _spend_orders(tenant, scope, start, end)
    covering = SupplierContract.objects.filter(
        tenant=tenant, party_id=OuterRef("vendor_id"), status__in=COVERING_CONTRACT_STATUSES,
    ).filter(
        Q(start_date__isnull=True) | Q(start_date__lte=OuterRef("order_date")),
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=OuterRef("order_date")),
    )
    # The aliases must NOT be called `total`: within one .annotate() Django resolves later
    # arguments against the aliases already declared in it, so `unrequisitioned=Sum("total", ...)`
    # would try to sum the alias and raise "Cannot compute Sum('total'): 'total' is an aggregate".
    rows = list(orders.annotate(on_contract=Exists(covering))
                .values("on_contract")
                .annotate(spend=Sum("total"), orders=Count("id"),
                          unrequisitioned=Sum("total", filter=Q(requisition__isnull=True))))
    covered = sum((row["spend"] or ZERO for row in rows if row["on_contract"]), ZERO)
    uncovered = sum((row["spend"] or ZERO for row in rows if not row["on_contract"]), ZERO)
    total = covered + uncovered
    if total <= ZERO:
        return _unavailable("spend_off_contract_pct", "No committed purchase orders in this window.")
    unreq = sum((row["unrequisitioned"] or ZERO for row in rows), ZERO)
    pct = _safe_div(uncovered * HUNDRED, total)
    return _result("spend_off_contract_pct", pct, breakdown={
        "total_spend": _f(total),
        "on_contract_spend": _f(covered),
        "off_contract_spend": _f(uncovered),
        "off_contract_orders": sum(row["orders"] or 0 for row in rows if not row["on_contract"]),
        "orders": sum(row["orders"] or 0 for row in rows),
        "unrequisitioned_spend": _f(unreq),
        "unrequisitioned_pct": _f(_safe_div(unreq * HUNDRED, total)),
        "covering_statuses": list(COVERING_CONTRACT_STATUSES),
        "caveat": ("Contract cover is vendor-level and date-based: 4.2 has no contract-to-item "
                   "linkage, so a line outside an agreement still counts as on-contract."),
    })


def _r_spend_top_supplier_share_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Share of spend concentrated in the top five suppliers, with the sole-source count beside it.

    Four queries: the grand total, the supplier league table, and two grouped COUNTs (evaluated as
    ``HAVING`` in the database, so the SKU groups never travel).
    """
    orders = _spend_orders(tenant, scope, start, end)
    total = orders.aggregate(total=Sum("total"))["total"] or ZERO
    if total <= ZERO:
        return _unavailable("spend_top_supplier_share_pct", "No committed purchase orders in this window.")
    league = list(orders.values("vendor_id", "vendor__name")
                  .annotate(total=Sum("total"), orders=Count("id"))
                  .order_by("-total")[:MAX_DETAIL_ROWS])
    top5 = sum((row["total"] or ZERO for row in league[:5]), ZERO)

    sku_groups = (PurchaseOrderLine.objects.filter(purchase_order__in=orders)
                  .exclude(sku_hint="")
                  .values("sku_hint")
                  .annotate(vendors=Count("purchase_order__vendor_id", distinct=True)))
    sku_total = sku_groups.count()
    sole_source = sku_groups.filter(vendors=1).count()
    return _result("spend_top_supplier_share_pct", _safe_div(top5 * HUNDRED, total), breakdown={
        "total_spend": _f(total),
        "top5_spend": _f(top5),
        "suppliers_ranked": len(league),
        "sku_hints": sku_total,
        "sole_source_skus": sole_source,
        "sole_source_pct": _f(_safe_div(Decimal(sole_source) * HUNDRED, Decimal(sku_total)))
        if sku_total else None,
        "sku_caveat": SKU_HINT_CAVEAT,
        "note": ("Suppliers ranked is capped at the detail-row limit, so it is 'the biggest N', not "
                 "the supplier count."),
    }, rows=[{"vendor": row["vendor__name"], "orders": row["orders"], "total": _f(row["total"]),
              "share_pct": _f(_safe_div((row["total"] or ZERO) * HUNDRED, total))}
             for row in league])


def _r_spend_tail_share_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Share of spend sitting in the smallest decile of suppliers — the tail-spend figure.

    Suppliers are ranked by value; the bottom 10% BY SUPPLIER COUNT is the tail. Defining the tail by
    count rather than by value is what makes the number actionable: it says "this many relationships
    are costing you this little", which is a consolidation decision.

    Refuses to compute below :data:`MIN_TAIL_SUPPLIERS` — see that constant for why a decile of one
    supplier is a misleading 100% rather than a small number.
    """
    orders = _spend_orders(tenant, scope, start, end)
    league = list(orders.values("vendor_id", "vendor__name")
                  .annotate(total=Sum("total"), orders=Count("id"))
                  .order_by("-total")[:MAX_GROUP_ROWS + 1])
    truncated = len(league) > MAX_GROUP_ROWS
    league = league[:MAX_GROUP_ROWS]
    if not league:
        return _unavailable("spend_tail_share_pct", "No committed purchase orders in this window.")
    total = sum((row["total"] or ZERO for row in league), ZERO)
    if total <= ZERO:
        return _unavailable("spend_tail_share_pct", "Committed orders in this window total nothing.")
    if len(league) < MIN_TAIL_SUPPLIERS:
        return _unavailable(
            "spend_tail_share_pct",
            f"Only {len(league)} supplier(s) were bought from in this window — a bottom decile "
            f"needs at least {MIN_TAIL_SUPPLIERS} to mean anything.",
            suppliers=len(league), total_spend=_f(total))
    tail_size = max(1, len(league) // 10)
    tail = league[-tail_size:]
    tail_value = sum((row["total"] or ZERO for row in tail), ZERO)
    tail_orders = sum(row["orders"] or 0 for row in tail)
    return _result("spend_tail_share_pct", _safe_div(tail_value * HUNDRED, total), breakdown={
        "total_spend": _f(total),
        "tail_spend": _f(tail_value),
        "suppliers": len(league),
        "tail_suppliers": tail_size,
        "tail_orders": tail_orders,
        "tail_definition": "the bottom 10% of suppliers by spend (at least one)",
        "average_tail_order_value": _f(_safe_div(tail_value, Decimal(tail_orders))),
        "truncated": truncated,
    }, rows=[{"vendor": row["vendor__name"], "orders": row["orders"], "total": _f(row["total"])}
             for row in reversed(tail[-MAX_DETAIL_ROWS:])])


def _r_savings_negotiated(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Awarded quote value vs the MEDIAN competing quote on the same RFQ.

    The one savings figure in this repo with evidence behind it: both numbers are real rows a
    supplier actually sent. Median rather than mean because a single absurd quote should not mint
    savings, and the awarded quote is excluded from its own comparison set — "competing" means the
    others. An RFQ with no competing quote is skipped entirely rather than scored as zero savings,
    and the skipped count is reported so the figure cannot be read as covering every award.
    """
    orders = _spend_orders(tenant, scope, start, end).filter(quote__isnull=False)
    awarded = list(orders.values_list("id", "number", "quote_id", "quote__rfq_id", "quote__total",
                                      "vendor__name", "currency__code")[:MAX_SAMPLE_ROWS + 1])
    truncated = len(awarded) > MAX_SAMPLE_ROWS
    awarded = awarded[:MAX_SAMPLE_ROWS]
    if not awarded:
        return _unavailable("savings_negotiated",
                            "No purchase orders in this window were awarded from an RFQ quote, so "
                            "there is nothing to compare an award against.")
    rfq_ids = {row[3] for row in awarded if row[3]}
    quotes = {}
    for rfq_id, quote_id, quote_total in RFQQuote.objects.filter(
            tenant=tenant, rfq_id__in=rfq_ids).values_list("rfq_id", "id", "total")[:MAX_GROUP_ROWS]:
        quotes.setdefault(rfq_id, []).append((quote_id, quote_total or ZERO))

    total, detail, skipped = ZERO, [], 0
    currencies = {row[6] or "(none)" for row in awarded}
    for _, number, quote_id, rfq_id, quote_total, vendor, currency in awarded:
        competing = [value for other_id, value in quotes.get(rfq_id, [])
                     if other_id != quote_id and value > ZERO]
        median = _median(competing)
        if median is None or quote_total is None:
            skipped += 1
            continue
        saving = median - quote_total
        total += saving
        detail.append({"order": number, "vendor": vendor, "currency": currency,
                       "awarded_value": _f(quote_total), "median_competing": _f(median),
                       "competing_quotes": len(competing), "saving": _f(saving)})
    detail.sort(key=lambda row: -(row["saving"] or 0))
    if not detail:
        return _unavailable("savings_negotiated",
                            "Every awarded order in this window was the only quote on its RFQ — "
                            "there is no competing price to measure a saving against.",
                            awards=len(awarded), skipped=skipped)
    return _result("savings_negotiated", total, breakdown={
        "awards_compared": len(detail),
        "awards_skipped_no_competition": skipped,
        "awards": len(awarded),
        "rfqs": len(rfq_ids),
        "basis": "awarded quote value vs the median of the OTHER quotes on the same RFQ",
        "mixed_currency": len(currencies) > 1,
        "currencies": sorted(currencies),
        "truncated": truncated,
    }, rows=detail[:MAX_DETAIL_ROWS])


def _r_savings_price_variance_opportunity(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """What buying every unit at the best price already paid for the same SKU would have saved.

    ONE grouped query does the whole thing: per ``sku_hint``, the spend, the quantity and the lowest
    unit price seen. The opportunity is ``spend - best_price x quantity``, which is algebraically the
    per-line ``qty x (paid - best)`` summed, without fetching a single line.

    This is an OPPORTUNITY, not a realised saving, and the page must say so: the cheapest price may
    have come with a lead time or a minimum order the other buys could not have taken.
    """
    orders = _spend_orders(tenant, scope, start, end)
    lines = PurchaseOrderLine.objects.filter(purchase_order__in=orders).exclude(sku_hint="")
    rows = list(lines.values("sku_hint")
                .annotate(spend=Sum(F("quantity") * F("unit_price"), output_field=_DEC),
                          quantity=Sum("quantity"),
                          best=Min("unit_price"),
                          vendors=Count("purchase_order__vendor_id", distinct=True),
                          lines=Count("id"))
                .order_by("-spend")[:MAX_GROUP_ROWS + 1])
    truncated = len(rows) > MAX_GROUP_ROWS
    rows = rows[:MAX_GROUP_ROWS]
    if not rows:
        return _unavailable("savings_price_variance_opportunity",
                            "No purchase-order lines in this window carry a SKU hint to group on.",
                            caveat=SKU_HINT_CAVEAT)
    currencies = set(orders.values_list("currency__code", flat=True).distinct()[:MAX_GROUP_ROWS])

    total, detail, multi_vendor = ZERO, [], 0
    for row in rows:
        spend = row["spend"] or ZERO
        quantity = row["quantity"] or ZERO
        best = row["best"] or ZERO
        opportunity = spend - best * quantity
        if opportunity <= ZERO:
            continue
        if (row["vendors"] or 0) > 1:
            multi_vendor += 1
        total += opportunity
        detail.append({"sku_hint": row["sku_hint"], "lines": row["lines"],
                       "vendors": row["vendors"], "quantity": _f(quantity, 4),
                       "spend": _f(spend), "best_unit_price": _f(best, 4),
                       "opportunity": _f(opportunity)})
    detail.sort(key=lambda row: -(row["opportunity"] or 0))
    return _result("savings_price_variance_opportunity", total, breakdown={
        "skus_grouped": len(rows),
        "skus_with_variance": len(detail),
        "skus_multi_vendor": multi_vendor,
        "basis": "sum over sku_hint of (spend - lowest unit price x quantity)",
        "mixed_currency": len({code or "(none)" for code in currencies}) > 1,
        "sku_caveat": SKU_HINT_CAVEAT,
        "note": ("An opportunity, not a realised saving: the lowest price may have carried a lead "
                 "time or minimum order the other buys could not have taken."),
        "truncated": truncated,
    }, rows=detail[:MAX_DETAIL_ROWS])


def _r_supplier_otd_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Share of goods receipts booked on or before the purchase order's expected date.

    Uses :func:`supplier_delivery_stats`' arithmetic — the same as 4.2's scorecard — and renders the
    all-suppliers leaderboard from the one grouped query behind it.
    """
    party = scope.subject if scope.value == "vendor" else None
    rows = _delivery_rows(tenant, party, start, end)
    datable = sum(row["datable"] for row in rows)
    if not datable:
        return _unavailable("supplier_otd_pct",
                            "No goods receipts in this window came from an order with a promised "
                            "date, so nothing can be measured as on time.")
    on_time = sum(row["on_time"] for row in rows)
    league = sorted(rows, key=lambda row: (-(row["datable"]), row["vendor"] or ""))
    detail = [{"vendor": row["vendor"], "receipts": row["datable"], "on_time": row["on_time"],
               "late": row["datable"] - row["on_time"],
               "otd_pct": _f(_safe_div(Decimal(row["on_time"]) * HUNDRED, Decimal(row["datable"])))}
              for row in league[:MAX_DETAIL_ROWS]]
    return _result("supplier_otd_pct", _safe_div(Decimal(on_time) * HUNDRED, Decimal(datable)),
                   breakdown={
                       "receipts_measured": datable,
                       "on_time": on_time,
                       "late": datable - on_time,
                       "suppliers": len(rows),
                       "basis": "GoodsReceiptNote.receipt_date <= PurchaseOrder.expected_date",
                       "excluded": ("Receipts against an order with no expected date — with nothing "
                                    "promised there is nothing to be late against."),
                       "twin": "SupplierScorecard.recompute_from_signals (4.2) delivery score",
                   }, rows=detail)


def _r_supplier_reject_rate_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Rejected quantity as a share of everything the supplier presented (received + rejected)."""
    party = scope.subject if scope.value == "vendor" else None
    rows = _quality_rows(tenant, party, start, end)
    received = sum((row["received"] for row in rows), ZERO)
    rejected = sum((row["rejected"] for row in rows), ZERO)
    presented = received + rejected
    if presented <= ZERO:
        return _unavailable("supplier_reject_rate_pct",
                            "No goods receipt lines in this window, so there is no quantity to "
                            "measure rejections against.")
    league = sorted(rows, key=lambda row: -(row["rejected"]))
    detail = [{"vendor": row["vendor"], "received": _f(row["received"], 4),
               "rejected": _f(row["rejected"], 4),
               "reject_pct": _f(_safe_div(row["rejected"] * HUNDRED,
                                          row["received"] + row["rejected"]))}
              for row in league[:MAX_DETAIL_ROWS]]
    return _result("supplier_reject_rate_pct", _safe_div(rejected * HUNDRED, presented), breakdown={
        "received": _f(received, 4),
        "rejected": _f(rejected, 4),
        "presented": _f(presented, 4),
        "suppliers": len(rows),
        "basis": "quantity_rejected / (quantity_received + quantity_rejected)",
        "twin": "SupplierScorecard.recompute_from_signals (4.2) quality score",
    }, rows=detail)


def _r_supplier_score_avg(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Mean ``overall_score`` of PUBLISHED 4.2 scorecards whose period ends in the window.

    Trends the STORED 4.2 rows and never derives a rival supplier score: the scorecard already blends
    delivery, quality, price and responsiveness under reviewed weights, and a second blend under the
    same name would be indefensible. Draft cards are excluded — an unpublished card is a work in
    progress, not a rating.
    """
    qs = scope.narrow_vendor(SupplierScorecard.objects.filter(tenant=tenant, status="published"),
                             vendor_path="party")
    qs = _in_dates(qs, "period_end", start, end).exclude(overall_score__isnull=True)
    summary = qs.aggregate(mean=Avg("overall_score"), cards=Count("id"),
                           best=Max("overall_score"), worst=Min("overall_score"))
    if not summary["cards"]:
        return _unavailable("supplier_score_avg",
                            "No published supplier scorecards close in this window. Scorecards are "
                            "published from 4.2 Supplier Relationship Management.")
    league = list(qs.values("party_id", "party__name")
                  .annotate(mean=Avg("overall_score"), cards=Count("id"))
                  .order_by("-mean")[:MAX_DETAIL_ROWS])
    mean = summary["mean"]
    return _result("supplier_score_avg", Decimal(mean) if mean is not None else None, breakdown={
        "scorecards": summary["cards"],
        "best": _f(summary["best"]),
        "worst": _f(summary["worst"]),
        "suppliers": len(league),
        "source": "SupplierScorecard.overall_score (4.2), published cards only — read, not recomputed",
        "weights": "delivery 35 / quality 35 / price 15 / responsiveness 15, set by 4.2",
    }, rows=[{"vendor": row["party__name"], "scorecards": row["cards"], "score": _f(row["mean"])}
             for row in league])


def _r_procure_cycle_days(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Days from raising a requisition to the purchase order that came out of it.

    ONE capped values_list, averaged in Python — the two dates live on different tables in different
    column types (``PurchaseRequisition.created_at`` is a timestamp, ``PurchaseOrder.order_date`` a
    date), and subtracting those in SQL portably is not worth a second query. Approval-to-order is
    reported alongside because the two halves fail for different reasons: a long raise-to-approve is
    a governance problem, a long approve-to-order is a buyer-capacity one.
    """
    orders = _spend_orders(tenant, scope, start, end).filter(requisition__isnull=False)
    rows = list(orders.values_list("order_date", "requisition__created_at",
                                   "requisition__approved_at")[:MAX_SAMPLE_ROWS + 1])
    truncated = len(rows) > MAX_SAMPLE_ROWS
    rows = rows[:MAX_SAMPLE_ROWS]
    raised, approved = [], []
    for order_date, created_at, approved_at in rows:
        if not order_date:
            continue
        if created_at:
            raised.append(Decimal((order_date - _as_date(created_at)).days))
        if approved_at:
            approved.append(Decimal((order_date - _as_date(approved_at)).days))
    if not raised:
        return _unavailable("procure_cycle_days",
                            "No purchase orders in this window came from a requisition, so there is "
                            "no cycle to measure.")
    mean = sum(raised, ZERO) / Decimal(len(raised))
    backdated = sum(1 for value in raised if value < ZERO)
    return _result("procure_cycle_days", mean, breakdown={
        "orders_measured": len(raised),
        "median_days": _f(_median(raised)),
        "fastest_days": _f(min(raised)),
        "slowest_days": _f(max(raised)),
        "approval_to_order_days": _f(sum(approved, ZERO) / Decimal(len(approved))) if approved else None,
        "backdated_orders": backdated,
        "basis": "PurchaseOrder.order_date - PurchaseRequisition.created_at (raise to order)",
        "note": ("Only orders that actually carry a requisition are measured — a direct buy has no "
                 "cycle, and counting it as zero days would flatter the average."),
        # order_date is hand-entered while created_at is a system stamp, so a back-dated order
        # legitimately produces a NEGATIVE cycle. Counted and reported rather than clamped to zero:
        # clamping would quietly shorten the average and hide the data-entry problem causing it.
        "backdated_note": ("Orders dated before the requisition that raised them: the cycle is "
                           "negative for those and they are counted, not clipped."),
        "truncated": truncated,
    })


def _r_procure_lead_days(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Days from placing a purchase order to the first goods receipt against it.

    Measured on RECEIVED receipts inside the window. The slip against the promised date is reported
    beside it — a supplier can be reliably slow (long but predictable lead time) or reliably late
    (short promise it never keeps), and those are different conversations.
    """
    qs = GoodsReceiptNote.objects.filter(tenant=tenant, status="received")
    qs = scope.narrow_vendor(qs, vendor_path="purchase_order__vendor")
    qs = _in_dates(qs, "receipt_date", start, end)
    rows = list(qs.values_list("receipt_date", "purchase_order__order_date",
                               "purchase_order__expected_date")[:MAX_SAMPLE_ROWS + 1])
    truncated = len(rows) > MAX_SAMPLE_ROWS
    rows = rows[:MAX_SAMPLE_ROWS]
    lead, slip = [], []
    for receipt_date, order_date, expected_date in rows:
        if order_date and receipt_date:
            lead.append(Decimal((receipt_date - order_date).days))
        if expected_date and receipt_date:
            slip.append(Decimal((receipt_date - expected_date).days))
    if not lead:
        return _unavailable("procure_lead_days",
                            "No goods receipts in this window came from an order with an order "
                            "date, so no lead time can be measured.")
    mean = sum(lead, ZERO) / Decimal(len(lead))
    return _result("procure_lead_days", mean, breakdown={
        "receipts_measured": len(lead),
        "median_days": _f(_median(lead)),
        "fastest_days": _f(min(lead)),
        "slowest_days": _f(max(lead)),
        "average_slip_days": _f(sum(slip, ZERO) / Decimal(len(slip))) if slip else None,
        "receipts_with_promise": len(slip),
        "backdated_receipts": sum(1 for value in lead if value < ZERO),
        "basis": "GoodsReceiptNote.receipt_date - PurchaseOrder.order_date",
        "note": ("Slip is receipt_date - expected_date: positive means late against the promise, "
                 "which is a different failure from a simply long lead time."),
        "truncated": truncated,
    })


def _as_date(value):
    """A ``date`` from either a date or an aware/naive datetime — window arithmetic needs one type."""
    if hasattr(value, "date"):
        return timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    return value


# =================================================================================================
# 9. Shared logistics machinery
# =================================================================================================

def _hours_between(earlier, later):
    """Whole-hours-and-fraction between two datetimes as a Decimal, or ``None``.

    Done in Python rather than in SQL deliberately: MariaDB's ``TIMESTAMPDIFF`` and SQLite's
    ``julianday`` are not the same expression, and 4.6's own ``YardVisit.dwell_minutes`` already
    subtracts in Python. One arithmetic, both backends.
    """
    if earlier is None or later is None:
        return None
    return Decimal((later - earlier).total_seconds()) / SECONDS_PER_HOUR


def _delivered_rows(tenant, scope, start, end, require_promise=True):
    """``(rows, truncated)`` — delivered shipments in the window, in ONE query.

    Shared by :func:`_r_otd_pct`, :func:`_r_otif_pct` and :func:`_r_carrier_otd_trend` so the three
    cannot each fetch a slightly different population and disagree about the same fleet.

    ``require_promise`` keeps the OTD rule 4.6 already uses: a shipment with no
    ``planned_delivery_date`` cannot be late (``Carrier.recompute_scorecard`` excludes it for the
    same reason ``supplier_delivery_stats`` excludes an undated receipt), so it is out of the OTD
    denominator. Transit time does not need a promise, so that caller passes ``False``.

    The on-time comparison is folded in PYTHON, not written as ``actual_delivery_at__date__lte``.
    Two reasons and both matter: it is the identical arithmetic ``Carrier.recompute_scorecard``
    performs, so 4.11's live figure and 4.6's stored one can only differ by their WINDOW; and a
    ``__date`` lookup on MySQL/MariaDB compiles to ``CONVERT_TZ`` whenever the project timezone is
    not UTC, which returns NULL — and therefore a confident 0% — on a server with no timezone tables
    loaded.
    """
    qs = Shipment.objects.filter(tenant=tenant, status="delivered",
                                 actual_delivery_at__isnull=False)
    if require_promise:
        qs = qs.filter(planned_delivery_date__isnull=False)
    qs = scope.narrow_carrier(qs, location_path=None)
    qs = _in_moments(qs, "actual_delivery_at", start, end)
    fetched = list(qs.values_list("id", "number", "carrier_id", "carrier__party__name",
                                  "planned_delivery_date", "actual_delivery_at",
                                  "actual_pickup_at", "origin_text", "destination_text", "mode",
                                  "sales_order_id", "sales_order__number",
                                  "sales_order__customer__name")[:MAX_SAMPLE_ROWS + 1])
    truncated = len(fetched) > MAX_SAMPLE_ROWS
    rows = []
    for (pk, number, carrier_id, carrier, planned, actual, picked, origin, destination, mode,
         order_id, order_number, customer) in fetched[:MAX_SAMPLE_ROWS]:
        delivered_on = _as_date(actual)
        rows.append({
            "id": pk, "shipment": number, "carrier_id": carrier_id,
            "carrier": carrier or "(unassigned)", "mode": mode,
            "planned": planned, "delivered_on": delivered_on,
            "on_time": bool(planned and delivered_on <= planned),
            "days_late": (delivered_on - planned).days if planned else None,
            "transit_hours": _hours_between(picked, actual),
            "lane": f"{origin or '?'} -> {destination or '?'}",
            "sales_order_id": order_id, "sales_order": order_number or "",
            "customer": customer or "",
        })
    return rows, truncated


def _fold_otd(rows, key):
    """``{key: {"delivered", "on_time"}}`` over already-fetched shipment rows — no extra query."""
    folded = {}
    for row in rows:
        bucket = folded.setdefault(row[key], {"delivered": 0, "on_time": 0})
        bucket["delivered"] += 1
        bucket["on_time"] += 1 if row["on_time"] else 0
    return folded


def _in_full_orders(tenant, order_ids, start, end):
    """``(in_full_ids, short_rows, lines_checked)`` for the orders behind a set of shipments.

    **This is the ONLY implementation of "in full" in the repo** — see :data:`IN_FULL_DEFINITION`,
    which :func:`_r_otif_pct` returns verbatim so the page prints it beside the number.

    TWO queries. The first groups every line of those orders with two conditional sums over its
    allocations (all non-cancelled claims, and the released subset). The second asks which of the
    items involved have any ``issue`` movement in the window at all. A line then passes when it is
    fully claimed AND something it claimed actually moved — a reservation on its own is a promise of
    stock, not a dispatch of it, and counting it as shipped is how an OTIF number quietly becomes an
    OTD number.
    """
    if not order_ids:
        return set(), [], 0
    line_rows = list(
        SalesOrderLine.objects
        .filter(sales_order__tenant=tenant, sales_order_id__in=order_ids)
        .values("id", "sales_order_id", "sales_order__number", "item_id", "item__sku",
                "description", "quantity_ordered")
        .annotate(allocated=Sum("allocations__quantity",
                                filter=~Q(allocations__status="cancelled")),
                  released=Sum("allocations__quantity",
                               filter=Q(allocations__status="released")))[:MAX_GROUP_ROWS])
    item_ids = {row["item_id"] for row in line_rows if row["item_id"]}
    issued = set()
    if item_ids:
        moves = StockMove.objects.filter(tenant=tenant, move_type="issue", item_id__in=item_ids)
        issued = set(_in_moments(moves, "moved_at", start, end)
                     .values_list("item_id", flat=True).distinct()[:MAX_ITEM_ROWS])

    complete, short = {}, []
    for row in line_rows:
        ordered = row["quantity_ordered"] or ZERO
        allocated = row["allocated"] or ZERO
        dispatched = (row["released"] or ZERO) > ZERO or row["item_id"] in issued
        ok = allocated >= ordered and dispatched
        order_id = row["sales_order_id"]
        complete[order_id] = complete.get(order_id, True) and ok
        if not ok:
            short.append({"sales_order": row["sales_order__number"],
                          "sku": row["item__sku"] or (row["description"] or "(unmapped)"),
                          "ordered": _f(ordered, 4), "allocated": _f(allocated, 4),
                          "short_by": _f(max(ordered - allocated, ZERO), 4),
                          "dispatched": dispatched})
    return {order_id for order_id, ok in complete.items() if ok}, short, len(line_rows)


def _audited_freight(tenant, scope, start, end):
    """Freight bills 4.6 has actually audited, narrowed and windowed on ``invoice_date``.

    ``duplicate`` is excluded because the audit found it to be a second copy of a bill already
    counted, and ``rejected`` because it will not be paid — counting either inflates every cost per
    unit derived from this queryset.
    """
    qs = FreightInvoice.objects.filter(tenant=tenant,
                                       match_status__in=AUDITED_FREIGHT_MATCH_STATUSES)
    qs = qs.exclude(approval_status="rejected")
    qs = scope.narrow_carrier(qs, location_path=None)
    return _in_dates(qs, "invoice_date", start, end)


def _currency_codes(qs, path="currency__code"):
    """``(sorted codes, mixed)`` for any money queryset. No FX table exists — see the docstring."""
    codes = sorted({code or "(none)" for code in
                    qs.values_list(path, flat=True).distinct()[:MAX_GROUP_ROWS]})
    return codes, len(codes) > 1


# =================================================================================================
# 10. LOGISTICS resolvers
#
# Group -> the `logistics_kpis` page. Over Shipment / TrackingEvent / Load / LoadStop / Carrier /
# CarrierRateCard / FreightInvoice(+Line) / YardVisit.
# =================================================================================================

def _r_otd_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Share of delivered shipments that arrived on or before the date they were promised for.

    Windowed on the ACTUAL delivery, because that is when the outcome happened — a shipment planned
    for March and delivered in April belongs to April's score. Shipments with no promised date are
    excluded: with nothing promised there is nothing to be late against, which is the same rule
    ``Carrier.recompute_scorecard`` (4.6) and :func:`supplier_delivery_stats` (4.2) both apply.
    """
    rows, truncated = _delivered_rows(tenant, scope, start, end)
    if not rows:
        return _unavailable("otd_pct",
                            "No shipment was delivered in this window against a promised delivery "
                            "date, so nothing can be measured as on time.")
    delivered = len(rows)
    on_time = sum(1 for row in rows if row["on_time"])
    late = [row for row in rows if not row["on_time"]]
    late.sort(key=lambda row: -(row["days_late"] or 0))
    by_carrier = _fold_otd(rows, "carrier")
    by_lane = _fold_otd(rows, "lane")
    slips = [Decimal(row["days_late"]) for row in late if row["days_late"] is not None]
    return _result("otd_pct", _safe_div(Decimal(on_time) * HUNDRED, Decimal(delivered)), breakdown={
        "delivered": delivered,
        "on_time": on_time,
        "late": delivered - on_time,
        "average_days_late": _f(sum(slips, ZERO) / Decimal(len(slips))) if slips else None,
        "worst_days_late": _f(max(slips)) if slips else None,
        "carriers": len(by_carrier),
        "lanes": len(by_lane),
        "by_carrier": {name: _f(_safe_div(Decimal(counts["on_time"]) * HUNDRED,
                                          Decimal(counts["delivered"])))
                       for name, counts in sorted(by_carrier.items())[:MAX_DETAIL_ROWS]},
        "by_lane": {name: _f(_safe_div(Decimal(counts["on_time"]) * HUNDRED,
                                       Decimal(counts["delivered"])))
                    for name, counts in sorted(by_lane.items())[:MAX_DETAIL_ROWS]},
        "basis": "Shipment.actual_delivery_at (date) <= Shipment.planned_delivery_date",
        "excluded": ("Delivered shipments with no planned delivery date — nothing was promised, so "
                     "nothing can be late. Same exclusion 4.6's carrier scorecard makes."),
        "truncated": truncated,
    }, rows=[{"shipment": row["shipment"], "carrier": row["carrier"], "lane": row["lane"],
              "promised": _iso(row["planned"]), "delivered_on": _iso(row["delivered_on"]),
              "days_late": row["days_late"], "customer": row["customer"]}
             for row in late[:MAX_DETAIL_ROWS]])


def _r_otif_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """On time AND in full — the share of deliveries that were both.

    "In full" is defined ONCE, in :func:`_in_full_orders`, and :data:`IN_FULL_DEFINITION` is
    returned in the breakdown so the page prints the definition rather than leaving a reader to
    guess what "full" means here.

    Only shipments that carry a sales order can be scored: without one there are no ordered
    quantities to be short of. Shipments with no order are counted and reported separately instead
    of being scored as complete, which would flatter the figure exactly where the data is thinnest.
    """
    rows, truncated = _delivered_rows(tenant, scope, start, end)
    scorable = [row for row in rows if row["sales_order_id"]]
    if not scorable:
        return _unavailable("otif_pct",
                            "No shipment delivered in this window is linked to a sales order, so "
                            "there are no ordered quantities to measure 'in full' against.",
                            delivered=len(rows),
                            shipments_without_order=len(rows),
                            definition=IN_FULL_DEFINITION)
    order_ids = {row["sales_order_id"] for row in scorable}
    in_full, short_lines, lines_checked = _in_full_orders(tenant, order_ids, start, end)

    otif, on_time_only, in_full_only, failures = 0, 0, 0, []
    for row in scorable:
        full = row["sales_order_id"] in in_full
        if row["on_time"] and full:
            otif += 1
            continue
        on_time_only += 1 if row["on_time"] else 0
        in_full_only += 1 if full else 0
        failures.append({"shipment": row["shipment"], "sales_order": row["sales_order"],
                         "customer": row["customer"], "carrier": row["carrier"],
                         "on_time": row["on_time"], "in_full": full,
                         "days_late": row["days_late"],
                         "failed": ("late and short" if not row["on_time"] and not full
                                    else ("late" if not row["on_time"] else "short"))})
    return _result("otif_pct", _safe_div(Decimal(otif) * HUNDRED, Decimal(len(scorable))),
                   breakdown={
                       "definition": IN_FULL_DEFINITION,
                       "shipments_scored": len(scorable),
                       "on_time_and_in_full": otif,
                       "late_but_in_full": in_full_only,
                       "on_time_but_short": on_time_only,
                       "shipments_without_order": len(rows) - len(scorable),
                       "order_lines_checked": lines_checked,
                       "short_lines": len(short_lines),
                       "orders": len(order_ids),
                       "orders_in_full": len(in_full),
                       "otd_component_pct": _f(_safe_div(
                           Decimal(sum(1 for row in scorable if row["on_time"])) * HUNDRED,
                           Decimal(len(scorable)))),
                       "in_full_component_pct": _f(_safe_div(
                           Decimal(sum(1 for row in scorable if row["sales_order_id"] in in_full))
                           * HUNDRED, Decimal(len(scorable)))),
                       "caveat": ("A shipment with no sales order behind it cannot be scored for "
                                  "'in full' and is left OUT of the denominator rather than "
                                  "assumed complete."),
                       "truncated": truncated,
                   }, rows=failures[:MAX_DETAIL_ROWS])


def _r_freight_cost_per_unit(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Audited freight billed, over every basis the shipment and load rows can supply.

    THREE queries: one aggregate over the audited bills (which carries the cost and, through the
    single-valued ``shipment``/``load`` joins, every denominator with it), one for the currency
    split, one for the per-carrier league.

    The headline picks the first basis that is actually populated — weight, then volume, then
    packages, then shipment count — and names it in ``basis``, because "freight cost per unit" is
    meaningless without saying which unit. Every other basis is reported alongside, so a page can
    render the one its operators think in.
    """
    invoices = _audited_freight(tenant, scope, start, end)
    totals = invoices.aggregate(
        billed=Sum("billed_amount"), bills=Count("id"),
        weight=Sum("shipment__weight_kg"), volume=Sum("shipment__volume_cbm"),
        packages=Sum("shipment__package_count"),
        shipments=Count("shipment", distinct=True),
        # Counted directly, not as bills - shipments: `shipments` is DISTINCT, so two bills against
        # the same shipment made that subtraction claim a bill had no shipment when it did — and the
        # note below tells the reader to trust this number before trusting the per-kilogram figure.
        bills_no_shipment=Count("id", filter=Q(shipment__isnull=True)),
        distance=Sum("load__distance_km"), loads=Count("load", distinct=True))
    if not totals["bills"]:
        return _unavailable("freight_cost_per_unit",
                            "No audited carrier invoice falls in this window. A bill is counted "
                            "once 4.6's freight audit has run on it.",
                            audited_statuses=list(AUDITED_FREIGHT_MATCH_STATUSES))
    billed = totals["billed"] or ZERO
    bases = [
        ("kg", "per kilogram", totals["weight"] or ZERO),
        ("cbm", "per cubic metre", totals["volume"] or ZERO),
        ("package", "per package", Decimal(totals["packages"] or 0)),
        ("shipment", "per shipment", Decimal(totals["shipments"] or 0)),
        ("km", "per kilometre", totals["distance"] or ZERO),
    ]
    rates = {key: _f(_safe_div(billed, quantity), 4) for key, _, quantity in bases}
    headline = next(((key, label, quantity) for key, label, quantity in bases if quantity > ZERO),
                    None)
    if headline is None:
        return _unavailable("freight_cost_per_unit",
                            "The audited bills in this window carry no weight, volume, package "
                            "count, shipment or distance to divide the cost by.",
                            billed=_f(billed), bills=totals["bills"])
    codes, mixed = _currency_codes(invoices)
    league = list(invoices.values("carrier_id", "carrier__party__name")
                  .annotate(billed=Sum("billed_amount"), bills=Count("id"),
                            weight=Sum("shipment__weight_kg"),
                            shipments=Count("shipment", distinct=True))
                  .order_by("-billed")[:MAX_DETAIL_ROWS])
    return _result("freight_cost_per_unit", _safe_div(billed, headline[2]), breakdown={
        "basis": headline[1],
        "basis_key": headline[0],
        "basis_quantity": _f(headline[2], 4),
        "billed": _f(billed),
        "bills": totals["bills"],
        "shipments": totals["shipments"],
        "loads": totals["loads"],
        "bills_without_shipment": totals["bills_no_shipment"],
        "rates": rates,
        "mixed_currency": mixed,
        "currencies": codes,
        "audited_statuses": list(AUDITED_FREIGHT_MATCH_STATUSES),
        "excluded": ("Bills the audit marked 'duplicate' (a second copy of a cost already counted) "
                     "and bills rejected at approval (they will not be paid)."),
        "note": ("Denominators come from the shipment/load each bill points at, so a bill raised "
                 "against a whole load rather than a shipment contributes cost with no weight — "
                 "read bills_without_shipment before trusting the per-kilogram figure."),
    }, rows=[{"carrier": row["carrier__party__name"], "bills": row["bills"],
              "shipments": row["shipments"], "billed": _f(row["billed"]),
              "weight_kg": _f(row["weight"], 2),
              "per_kg": _f(_safe_div(row["billed"] or ZERO, row["weight"] or ZERO), 4),
              "per_shipment": _f(_safe_div(row["billed"] or ZERO,
                                           Decimal(row["shipments"] or 0)))}
             for row in league])


def _r_equipment_utilization_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """How full the equipment went out — loaded weight over the equipment's rated capacity.

    ONE grouped query: per load, the summed weight and volume of the shipments consolidated onto it
    beside the load's own rated capacity. 4.6 already renders this for a SINGLE load
    (``Load.weight_utilization_pct``); 4.11's job is the fleet-level roll-up and the split by
    equipment type, which is where a systematic problem shows.

    Loads with no rated capacity are counted and reported but cannot be scored — a percentage of an
    unknown capacity is not a smaller number, it is not a number. Cancelled loads are excluded.
    """
    loads = Load.objects.filter(tenant=tenant).exclude(status="cancelled")
    loads = scope.narrow_carrier(loads, location_path=None)
    loads = _in_moments(loads, "planned_departure", start, end)
    fetched = list(loads.values("id", "number", "equipment_type", "carrier__party__name",
                                "equipment_capacity_weight_kg", "equipment_capacity_volume_cbm")
                   # `shipment_count`, not `shipments`: an alias must never shadow the relation the
                   # aggregates in the same .annotate() are traversing.
                   .annotate(weight=Sum("shipments__weight_kg"),
                             volume=Sum("shipments__volume_cbm"),
                             shipment_count=Count("shipments__id"))[:MAX_GROUP_ROWS + 1])
    truncated = len(fetched) > MAX_GROUP_ROWS
    fetched = fetched[:MAX_GROUP_ROWS]
    if not fetched:
        return _unavailable("equipment_utilization_pct",
                            "No load departed in this window. Loads with no planned departure date "
                            "cannot be placed in a window and are not counted.")

    weight_used, weight_cap, volume_used, volume_cap = ZERO, ZERO, ZERO, ZERO
    uncapacitated, by_equipment, detail = 0, {}, []
    for row in fetched:
        capacity_w = row["equipment_capacity_weight_kg"] or ZERO
        capacity_v = row["equipment_capacity_volume_cbm"] or ZERO
        used_w = row["weight"] or ZERO
        used_v = row["volume"] or ZERO
        if capacity_w <= ZERO and capacity_v <= ZERO:
            uncapacitated += 1
            continue
        weight_used += used_w
        weight_cap += capacity_w
        volume_used += used_v
        volume_cap += capacity_v
        bucket = by_equipment.setdefault(row["equipment_type"],
                                         {"loads": 0, "used": ZERO, "capacity": ZERO})
        bucket["loads"] += 1
        bucket["used"] += used_w
        bucket["capacity"] += capacity_w
        detail.append({"load": row["number"], "carrier": row["carrier__party__name"] or "",
                       "equipment": row["equipment_type"], "shipments": row["shipment_count"],
                       "weight_kg": _f(used_w), "capacity_kg": _f(capacity_w),
                       "weight_utilization_pct": _f(_safe_div(used_w * HUNDRED, capacity_w)),
                       "volume_utilization_pct": _f(_safe_div(used_v * HUNDRED, capacity_v))})
    weight_pct = _safe_div(weight_used * HUNDRED, weight_cap)
    if weight_pct is None:
        return _unavailable("equipment_utilization_pct",
                            "None of the loads in this window record an equipment capacity to "
                            "measure the loaded weight against.",
                            loads=len(fetched), loads_without_capacity=uncapacitated)
    detail.sort(key=lambda row: (row["weight_utilization_pct"] or 0))
    return _result("equipment_utilization_pct", weight_pct, breakdown={
        "loads_scored": len(detail),
        "loads_without_capacity": uncapacitated,
        "weight_loaded_kg": _f(weight_used),
        "weight_capacity_kg": _f(weight_cap),
        "volume_utilization_pct": _f(_safe_div(volume_used * HUNDRED, volume_cap)),
        "volume_loaded_cbm": _f(volume_used, 3),
        "volume_capacity_cbm": _f(volume_cap, 3),
        "by_equipment_type": {name: _f(_safe_div(bucket["used"] * HUNDRED, bucket["capacity"]))
                              for name, bucket in sorted(by_equipment.items())},
        "loads_by_equipment_type": {name: bucket["loads"]
                                    for name, bucket in sorted(by_equipment.items())},
        "basis": "sum of consolidated Shipment.weight_kg / sum of Load.equipment_capacity_weight_kg",
        "note": ("Weight is the headline; the volume twin is beside it because a cube-out and a "
                 "weight-out are different problems with different fixes. Loads with no planned "
                 "departure cannot be windowed and are absent entirely."),
        "truncated": truncated,
    }, rows=detail[:MAX_DETAIL_ROWS])


def _r_freight_variance_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Billed-versus-contracted freight, as a share of what was contracted.

    Reads 4.6's own audit output — ``variance_amount`` and ``match_status`` are written by
    ``FreightInvoice.run_audit`` — rather than re-deriving the comparison. The recovered/disputed
    split IS the match status: ``disputed`` is variance somebody is chasing, ``price_variance`` is
    variance that has been accepted, and ``matched`` is a bill that agreed with its rate card.
    """
    invoices = _audited_freight(tenant, scope, start, end)
    totals = invoices.aggregate(variance=Sum("variance_amount"), contract=Sum("contract_amount"),
                                billed=Sum("billed_amount"), bills=Count("id"))
    if not totals["bills"]:
        return _unavailable("freight_variance_pct",
                            "No audited carrier invoice falls in this window.",
                            audited_statuses=list(AUDITED_FREIGHT_MATCH_STATUSES))
    contract = totals["contract"] or ZERO
    variance = totals["variance"] or ZERO
    pct = _safe_div(variance * HUNDRED, contract)
    if pct is None:
        return _unavailable("freight_variance_pct",
                            "The audited bills in this window carry no contracted amount to "
                            "measure a variance against — their rate cards did not resolve.",
                            billed=_f(totals["billed"]), variance=_f(variance),
                            bills=totals["bills"])
    by_status = list(invoices.values("match_status")
                     .annotate(variance=Sum("variance_amount"), bills=Count("id"),
                               billed=Sum("billed_amount")))
    league = list(invoices.values("carrier_id", "carrier__party__name")
                  .annotate(variance=Sum("variance_amount"), contract=Sum("contract_amount"),
                            billed=Sum("billed_amount"), bills=Count("id"))
                  .order_by("-variance")[:MAX_DETAIL_ROWS])
    status_variance = {row["match_status"]: row["variance"] or ZERO for row in by_status}
    codes, mixed = _currency_codes(invoices)
    return _result("freight_variance_pct", pct, breakdown={
        "bills": totals["bills"],
        "billed": _f(totals["billed"]),
        "contracted": _f(contract),
        "variance": _f(variance),
        "disputed_variance": _f(status_variance.get("disputed", ZERO)),
        "accepted_variance": _f(status_variance.get("price_variance", ZERO)),
        "clean_bills": next((row["bills"] for row in by_status
                             if row["match_status"] == "matched"), 0),
        "by_match_status": {row["match_status"]: _f(row["variance"]) for row in by_status},
        "bills_by_match_status": {row["match_status"]: row["bills"] for row in by_status},
        "mixed_currency": mixed,
        "currencies": codes,
        "source": "FreightInvoice.variance_amount / .match_status, written by 4.6's freight audit",
        "note": ("Positive means the carrier billed above the rate card. Disputed variance is money "
                 "being chased; accepted variance has already been agreed and is a rate-card "
                 "problem, not a billing one."),
    }, rows=[{"carrier": row["carrier__party__name"], "bills": row["bills"],
              "billed": _f(row["billed"]), "contracted": _f(row["contract"]),
              "variance": _f(row["variance"]),
              "variance_pct": _f(_safe_div((row["variance"] or ZERO) * HUNDRED,
                                           row["contract"] or ZERO))}
             for row in league])


def _r_carrier_otd_trend(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Trends 4.6's STORED ``Carrier.on_time_delivery_pct`` — it does not restate it.

    ``Carrier.recompute_scorecard`` already derives that percentage from the carrier's delivered
    shipments and stores it. Deriving a second on-time figure here under a second name would give
    the tenant two carrier league tables that disagree, so this reads the column and BUILDS THE ROW
    AROUND IT: the project44 canonical carrier scorecard — on-time, average transit against the rate
    card's promise, cost per kilogram, billing variance and exception count.

    **The stored figure is the carrier's WHOLE delivered history, not this window.** 4.6 recomputes
    it over every delivered shipment with a planned date, unwindowed. That is stated here and is the
    honest reason it can differ from :func:`_r_otd_pct`, which measures the same idea inside the
    window. The supporting columns beside it ARE windowed.
    """
    carriers = Carrier.objects.filter(tenant=tenant)
    carriers = scope.narrow_carrier(carriers, carrier_path="pk", location_path=None)
    fetched = list(carriers.exclude(status="inactive")
                   .values("id", "number", "party__name", "on_time_delivery_pct", "primary_mode",
                           "service_level", "status")[:MAX_GROUP_ROWS + 1])
    truncated = len(fetched) > MAX_GROUP_ROWS
    fetched = fetched[:MAX_GROUP_ROWS]
    scored = [row for row in fetched if row["on_time_delivery_pct"] is not None]
    if not scored:
        return _unavailable("carrier_otd_trend",
                            "No active carrier carries a stored on-time score yet. 4.6 derives it "
                            "from delivered shipments — recompute a carrier's scorecard first.",
                            carriers=len(fetched))
    ids = [row["id"] for row in fetched]

    promises = {row["carrier_id"]: row["transit"] for row in
                CarrierRateCard.objects.filter(carrier__tenant=tenant, carrier_id__in=ids,
                                               is_active=True, transit_days__isnull=False)
                .values("carrier_id").annotate(transit=Avg("transit_days"))[:MAX_GROUP_ROWS]}
    exceptions = {row["carrier_id"]: row["n"] for row in
                  _in_moments(Shipment.objects.filter(tenant=tenant, carrier_id__in=ids,
                                                      status="exception"),
                              "created_at", start, end)
                  .values("carrier_id").annotate(n=Count("id"))[:MAX_GROUP_ROWS]}
    freight = {row["carrier_id"]: row for row in
               _audited_freight(tenant, NETWORK, start, end).filter(carrier_id__in=ids)
               .values("carrier_id").annotate(billed=Sum("billed_amount"),
                                              contract=Sum("contract_amount"),
                                              variance=Sum("variance_amount"),
                                              weight=Sum("shipment__weight_kg"))[:MAX_GROUP_ROWS]}
    delivered_rows, delivered_truncated = _delivered_rows(tenant, scope, start, end,
                                                          require_promise=False)
    transit = {}
    for row in delivered_rows:
        if row["transit_hours"] is None:
            continue
        bucket = transit.setdefault(row["carrier_id"], [ZERO, 0])
        bucket[0] += row["transit_hours"]
        bucket[1] += 1

    detail = []
    for row in fetched:
        bills = freight.get(row["id"]) or {}
        hours, samples = transit.get(row["id"], (ZERO, 0))
        detail.append({
            "carrier": row["party__name"], "number": row["number"], "mode": row["primary_mode"],
            "service_level": row["service_level"],
            "otd_pct": _f(row["on_time_delivery_pct"]),
            "avg_transit_days": _f(hours / Decimal(samples) / Decimal("24")) if samples else None,
            "rate_card_transit_days": _f(promises.get(row["id"])),
            "cost_per_kg": _f(_safe_div(bills.get("billed") or ZERO, bills.get("weight") or ZERO), 4),
            "variance_pct": _f(_safe_div((bills.get("variance") or ZERO) * HUNDRED,
                                         bills.get("contract") or ZERO)),
            "exceptions": exceptions.get(row["id"], 0),
            "deliveries_sampled": samples,
        })
    detail.sort(key=lambda row: (row["otd_pct"] is None, row["otd_pct"] or 0))
    scores = [Decimal(row["on_time_delivery_pct"]) for row in scored]
    return _result("carrier_otd_trend", sum(scores, ZERO) / Decimal(len(scores)), breakdown={
        "carriers": len(fetched),
        "carriers_scored": len(scored),
        "best_pct": _f(max(scores)),
        "worst_pct": _f(min(scores)),
        "exceptions": sum(exceptions.values()),
        "source": ("Carrier.on_time_delivery_pct, derived and stored by 4.6's "
                   "Carrier.recompute_scorecard — read, not recomputed"),
        "headline_basis": "unweighted mean of the stored per-carrier percentages",
        "window_caveat": ("The stored on-time percentage covers each carrier's WHOLE delivered "
                          "history, not this window — 4.6 recomputes it unwindowed. The transit, "
                          "cost, variance and exception columns beside it ARE windowed, so read "
                          "them as 'how this carrier is behaving now' against a lifetime score."),
        "truncated": truncated or delivered_truncated,
    }, rows=detail[:MAX_DETAIL_ROWS])


def _r_dwell_hours_avg(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """How long a vehicle sits on site — gate in to gate out — plus the tracking-silence twin.

    The headline is yard dwell, measured on ``YardVisit`` visits that have both arrived and departed
    inside the window; the gate-to-dock and dock-to-departure halves are reported beside it because
    they fail for different reasons (a queue at the gate is a scheduling problem, a long time on the
    dock is a labour one).

    The tracking-gap figure in the breakdown is the second half of the same question for goods that
    never touch our yard: for each shipment, the mean interval between its ``TrackingEvent`` rows,
    computed as span over intervals in ONE grouped query rather than by walking every event.
    """
    visits = YardVisit.objects.filter(tenant=tenant, arrived_at__isnull=False,
                                      departed_at__isnull=False)
    visits = scope.narrow_carrier(visits, carrier_path=None, location_path="dock_door",
                                  carrier_name_path="carrier_name")
    visits = _in_moments(visits, "arrived_at", start, end)
    fetched = list(visits.values_list("number", "carrier_name", "direction", "dock_door__code",
                                      "arrived_at", "docked_at",
                                      "departed_at")[:MAX_SAMPLE_ROWS + 1])
    truncated = len(fetched) > MAX_SAMPLE_ROWS

    # The tracking half has no location column (a Shipment is not at a Location), so a location
    # scope legitimately cannot narrow it. Excluded and SAID so rather than silently left network-
    # wide under a warehouse's name.
    tracking_scoped = scope.value != "location"
    gaps, gap_shipments = [], 0
    if tracking_scoped:
        events = TrackingEvent.objects.filter(shipment__tenant=tenant)
        if scope.value == "carrier":
            events = events.filter(shipment__carrier=scope.subject)
        events = _in_moments(events, "event_at", start, end)
        for row in (events.values("shipment_id")
                    .annotate(first=Min("event_at"), last=Max("event_at"),
                              n=Count("id"))[:MAX_GROUP_ROWS]):
            if (row["n"] or 0) < 2:
                continue
            span = _hours_between(row["first"], row["last"])
            if span is None:
                continue
            gap_shipments += 1
            gaps.append(span / Decimal(row["n"] - 1))

    dwell, gate_to_dock, dock_to_out, detail = [], [], [], []
    for number, carrier_name, direction, dock, arrived, docked, departed in fetched[:MAX_SAMPLE_ROWS]:
        on_site = _hours_between(arrived, departed)
        if on_site is None:
            continue
        dwell.append(on_site)
        waiting = _hours_between(arrived, docked)
        working = _hours_between(docked, departed)
        if waiting is not None:
            gate_to_dock.append(waiting)
        if working is not None:
            dock_to_out.append(working)
        detail.append({"visit": number, "carrier": carrier_name, "direction": direction,
                       "dock": dock or "", "arrived": _iso(arrived), "departed": _iso(departed),
                       "dwell_hours": _f(on_site), "gate_to_dock_hours": _f(waiting),
                       "dock_to_departure_hours": _f(working)})

    tracking_gap = (sum(gaps, ZERO) / Decimal(len(gaps))) if gaps else None
    if not dwell:
        return _unavailable(
            "dwell_hours_avg",
            "No vehicle completed a yard visit in this window (a visit needs both an arrival and a "
            "departure to have a dwell).",
            yard_visits=0,
            tracking_gap_hours_avg=_f(tracking_gap),
            tracking_shipments=gap_shipments,
            tracking_scoped=tracking_scoped)
    detail.sort(key=lambda row: -(row["dwell_hours"] or 0))
    return _result("dwell_hours_avg", sum(dwell, ZERO) / Decimal(len(dwell)), breakdown={
        "yard_visits": len(dwell),
        "median_dwell_hours": _f(_median(dwell)),
        "longest_dwell_hours": _f(max(dwell)),
        "shortest_dwell_hours": _f(min(dwell)),
        "gate_to_dock_hours_avg": _f(sum(gate_to_dock, ZERO) / Decimal(len(gate_to_dock)))
        if gate_to_dock else None,
        "dock_to_departure_hours_avg": _f(sum(dock_to_out, ZERO) / Decimal(len(dock_to_out)))
        if dock_to_out else None,
        "tracking_gap_hours_avg": _f(tracking_gap),
        "tracking_shipments": gap_shipments,
        "tracking_scoped": tracking_scoped,
        "basis": "YardVisit.departed_at - YardVisit.arrived_at, windowed on the arrival",
        "carrier_axis": ("YardVisit predates 4.6 and stores the haulier as free text "
                         "(carrier_name), so a carrier scope matches it BY NAME, case-insensitively "
                         "— a differently-spelled haulier is not counted. The shipment tracking "
                         "half narrows on the real Carrier FK."),
        "location_note": ("A location scope narrows the yard half by dock door. The tracking-gap "
                          "figure is omitted under a location scope: a Shipment has no location, so "
                          "there is nothing to narrow it by and reporting the network figure under "
                          "a warehouse's name would be worse than omitting it."),
        "truncated": truncated,
    }, rows=detail[:MAX_DETAIL_ROWS])


# =================================================================================================
# 11. Shared margin machinery
#
# EVERY resolver in the margin group carries OPERATIONAL_ESTIMATE_NOTE in its breakdown, and the
# page renders it (L29). SCM posts no JournalEntry: apps.accounting owns the ledger, its Balance
# Sheet / P&L are the reportable figures, and nothing here is a substitute for them. What these do
# offer that the ledger cannot is the OPERATIONAL cut — by item, by customer, by lane, by channel —
# because the ledger books a sale, not the pick line and the freight bill behind it.
# =================================================================================================

#: The revenue formula, written once. Same shape as ``SalesOrderLine.line_subtotal`` (quantity x
#: price, less the line discount) — tax is deliberately out, because a margin measured on a
#: tax-inclusive number moves when a tax rate does.
_REVENUE_EXPR = ExpressionWrapper(
    F("quantity_ordered") * F("unit_price")
    * (Value(HUNDRED, output_field=_DEC) - F("discount_pct")) / Value(HUNDRED, output_field=_DEC),
    output_field=_DEC)


def _issued_unit_costs(tenant, scope, start, end):
    """``{item_id: the unit cost at which stock actually left}`` for the window. ONE query.

    Derived from the ``issue`` ledger — total cost issued over total quantity issued, per item —
    which is the real cost of what shipped rather than what the item's cached average happens to be
    today. Items with no issue movement fall back to ``Item.average_cost`` at the call site.
    """
    moves = StockMove.objects.filter(tenant=tenant, move_type="issue")
    moves = _in_moments(scope.narrow_item_rows(moves), "moved_at", start, end)
    out = {}
    for row in (moves.values("item_id")
                .annotate(cost=Sum(F("quantity") * F("unit_cost"), output_field=_DEC),
                          qty=Sum("quantity"))[:MAX_ITEM_ROWS]):
        # Outbound quantities are signed negative in the append-only ledger; negating both leaves
        # the ratio positive and unchanged.
        quantity = -(row["qty"] or ZERO)
        if quantity > ZERO:
            out[row["item_id"]] = -(row["cost"] or ZERO) / quantity
    return out


def _margin_base(tenant, scope, start, end):
    """Revenue and COGS for the window, cut every way the margin group needs. TWO queries.

    The sales lines are grouped ONCE at (item x customer x channel) grain and folded in Python into
    the four cuts, rather than running a separate aggregate per cut — four queries that each round
    their own COGS is how a page ends up with four totals that do not add up.

    COGS is the item's ledger-derived issue cost for the window where there is one, and its cached
    ``average_cost`` where there is not. Which of the two was used is counted and reported.
    """
    lines = (SalesOrderLine.objects.filter(sales_order__tenant=tenant)
             .exclude(sales_order__status__in=NON_REVENUE_SO_STATUSES))
    lines = scope.narrow_item_rows(lines, item_path="item")
    lines = _in_dates(lines, "sales_order__order_date", start, end)
    fetched = list(lines.values("item_id", "item__sku", "item__name", "item__category__name",
                                "item__average_cost", "sales_order__customer_id",
                                "sales_order__customer__name", "sales_order__source_channel",
                                "sales_order__currency__code")
                   .annotate(revenue=Sum(_REVENUE_EXPR), quantity=Sum("quantity_ordered"),
                             lines=Count("id"))[:MAX_GROUP_ROWS + 1])
    truncated = len(fetched) > MAX_GROUP_ROWS
    fetched = fetched[:MAX_GROUP_ROWS]
    issued = _issued_unit_costs(tenant, scope, start, end) if fetched else {}

    base = {"revenue": ZERO, "cogs": ZERO, "quantity": ZERO, "lines": 0, "groups": len(fetched),
            "by_item": {}, "by_category": {}, "by_customer": {}, "by_channel": {},
            "from_ledger": 0, "from_average": 0, "unmapped_lines": 0,
            "currencies": set(), "truncated": truncated}
    for row in fetched:
        revenue = row["revenue"] or ZERO
        quantity = row["quantity"] or ZERO
        item_id = row["item_id"]
        if item_id is None:
            # A quote-converted line that was never mapped to an Item has revenue and no cost basis
            # at all. Counted, reported, and left OUT of the COGS side rather than costed at zero —
            # which would show it as pure margin.
            base["unmapped_lines"] += row["lines"]
            unit_cost = None
        elif item_id in issued:
            unit_cost = issued[item_id]
            base["from_ledger"] += 1
        else:
            unit_cost = row["item__average_cost"] or ZERO
            base["from_average"] += 1
        cogs = quantity * unit_cost if unit_cost is not None else ZERO
        base["revenue"] += revenue
        base["cogs"] += cogs
        base["quantity"] += quantity
        base["lines"] += row["lines"]
        if row["sales_order__currency__code"]:
            base["currencies"].add(row["sales_order__currency__code"])

        for cut, key, label in (
                ("by_item", item_id, row["item__sku"] or "(unmapped)"),
                ("by_category", row["item__category__name"] or "(uncategorised)", None),
                ("by_customer", row["sales_order__customer_id"],
                 row["sales_order__customer__name"] or "(unknown)"),
                ("by_channel", row["sales_order__source_channel"] or "(unset)", None)):
            bucket = base[cut].setdefault(key, {"label": label if label is not None else key,
                                                "revenue": ZERO, "cogs": ZERO, "quantity": ZERO})
            bucket["revenue"] += revenue
            bucket["cogs"] += cogs
            bucket["quantity"] += quantity
            if cut == "by_item":
                bucket["name"] = row["item__name"] or ""
    base["gross_profit"] = base["revenue"] - base["cogs"]
    base["margin_pct"] = _safe_div(base["gross_profit"] * HUNDRED, base["revenue"])
    base["mixed_currency"] = len(base["currencies"]) > 1
    return base


def _cut_rows(cut, limit=MAX_DETAIL_ROWS):
    """A margin cut as JSON-safe rows, richest first."""
    rows = []
    for bucket in sorted(cut.values(), key=lambda entry: -entry["revenue"]):
        profit = bucket["revenue"] - bucket["cogs"]
        rows.append({"label": bucket["label"], "name": bucket.get("name", ""),
                     "quantity": _f(bucket["quantity"], 4), "revenue": _f(bucket["revenue"]),
                     "cogs": _f(bucket["cogs"]), "gross_profit": _f(profit),
                     "margin_pct": _f(_safe_div(profit * HUNDRED, bucket["revenue"]))})
    return rows[:limit]


def _cut_totals(cut, limit=MAX_DETAIL_ROWS):
    """A margin cut as a ``{label: margin %}`` map for the breakdown."""
    return {bucket["label"]: _f(_safe_div((bucket["revenue"] - bucket["cogs"]) * HUNDRED,
                                          bucket["revenue"]))
            for bucket in sorted(cut.values(), key=lambda entry: -entry["revenue"])[:limit]}


def _handling_proxy(tenant, start, end):
    """The warehouse handling leg — ONE aggregate over 4.4's picked lines.

    **The two rates are CONVENTIONS, not derived** (see :data:`HANDLING_COST_PER_PICK_LINE`): 4.4
    records no cost on a pick and there is no distribution labour rate anywhere in 4.1-4.10. Both
    rates go into the returned dict so every caller echoes them into its breakdown and a reader can
    redo the arithmetic with their own number instead of taking this one on trust.
    """
    picked = PickTaskLine.objects.filter(pick_task__tenant=tenant)
    picked = _in_moments(picked, "pick_task__picked_at", start, end)
    totals = picked.aggregate(lines=Count("id"), units=Sum("quantity_picked"),
                              tasks=Count("pick_task", distinct=True))
    lines = Decimal(totals["lines"] or 0)
    units = totals["units"] or ZERO
    return {
        "lines": totals["lines"] or 0,
        "tasks": totals["tasks"] or 0,
        "units": units,
        "cost": lines * HANDLING_COST_PER_PICK_LINE + units * HANDLING_COST_PER_PICK_UNIT,
        "rate_per_line": HANDLING_COST_PER_PICK_LINE,
        "rate_per_unit": HANDLING_COST_PER_PICK_UNIT,
        "basis": ("pick lines x a per-line rate plus picked units x a per-unit rate. BOTH RATES ARE "
                  "PLANNING CONVENTIONS with no source row in 4.1-4.10 — 4.4 records no cost on a "
                  "pick. They are shown so this leg can be recomputed with your own figures."),
    }


def _quality_cost(tenant, start, end):
    """4.9's cost of quality plus 4.10's warranty spend — ONE aggregate each."""
    ncr = _in_dates(NonConformance.objects.filter(tenant=tenant), "detected_on", start, end)
    ncr_totals = ncr.aggregate(cost=Sum("cost_of_quality"), count=Count("id"))
    warranty = _in_dates(WarrantyClaimCost.objects.filter(claim__tenant=tenant),
                         "claim__submitted_on", start, end)
    warranty_totals = warranty.aggregate(claimed=Sum("amount_claimed"),
                                         approved=Sum("amount_approved"), lines=Count("id"))
    return {
        "nonconformance_cost": ncr_totals["cost"] or ZERO,
        "nonconformances": ncr_totals["count"] or 0,
        "warranty_cost": warranty_totals["claimed"] or ZERO,
        "warranty_recoverable": warranty_totals["approved"] or ZERO,
        "warranty_cost_lines": warranty_totals["lines"] or 0,
        "note": ("Warranty cost is what handling the failure cost US (parts, labour, freight, "
                 "service, admin). What the supplier accepted is reported separately as a RECOVERY "
                 "against it, not netted off — the two settle on different dates."),
    }


def _returns_cost(tenant, start, end):
    """4.10's returns write-down, per customer. ONE capped fetch, folded in Python.

    A restocked unit loses the difference between what it cost going out (``ReturnLine.unit_cost``)
    and what it is worth coming back (``ReturnDisposition.restock_unit_cost``) — the graded cost.
    A written-off unit loses its whole cost less whatever was recovered for it. Both are clamped at
    zero: a unit that came back worth MORE than it went out at is a data-entry problem, not a
    negative cost to hand back to the margin.
    """
    dispositions = _in_dates(ReturnDisposition.objects.filter(return_line__return_authorization__tenant=tenant),
                             "received_on", start, end)
    fetched = list(dispositions.exclude(disposition="received_pending")
                   .values_list("return_line__return_authorization__customer_id",
                                "return_line__return_authorization__customer__name",
                                "disposition", "quantity", "return_line__unit_cost",
                                "restock_unit_cost", "recovery_value")[:MAX_SAMPLE_ROWS + 1])
    truncated = len(fetched) > MAX_SAMPLE_ROWS
    total, by_customer, restocked, written_off = ZERO, {}, 0, 0
    for (customer_id, customer, disposition, quantity, unit_cost, restock_cost,
         recovery) in fetched[:MAX_SAMPLE_ROWS]:
        quantity = quantity or ZERO
        original = quantity * (unit_cost or ZERO)
        if disposition == "restock":
            loss = original - quantity * (restock_cost or ZERO)
            restocked += 1
        else:
            loss = original - (recovery or ZERO)
            written_off += 1
        loss = max(loss, ZERO)
        total += loss
        bucket = by_customer.setdefault(customer_id, {"label": customer or "(unknown)",
                                                      "cost": ZERO, "units": ZERO})
        bucket["cost"] += loss
        bucket["units"] += quantity
    return {"cost": total, "by_customer": by_customer, "dispositions": len(fetched[:MAX_SAMPLE_ROWS]),
            "restocked": restocked, "written_off": written_off, "truncated": truncated,
            "basis": ("restocked: quantity x (original unit cost - graded restock cost); written "
                      "off: quantity x original unit cost, less any recovery value. Both floored "
                      "at zero.")}


# =================================================================================================
# 12. MARGIN resolvers
#
# Group -> the `margin_analytics` page.
# =================================================================================================

def _r_gross_margin_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Revenue less the cost of the goods behind it, as a percentage of revenue.

    Revenue is the ordered value net of line discount and BEFORE tax. Cost is what the ledger says
    the goods cost to issue in this window, falling back to the item's cached average cost.
    """
    base = _margin_base(tenant, scope, start, end)
    if base["revenue"] <= ZERO:
        return _unavailable("gross_margin_pct",
                            "No sales-order value in this window to measure a margin on. Draft and "
                            "cancelled orders are excluded — a draft is not revenue and a "
                            "cancellation never was.",
                            note=OPERATIONAL_ESTIMATE_NOTE)
    return _result("gross_margin_pct", base["margin_pct"], breakdown={
        "revenue": _f(base["revenue"]),
        "cogs": _f(base["cogs"]),
        "gross_profit": _f(base["gross_profit"]),
        "quantity": _f(base["quantity"], 4),
        "order_lines": base["lines"],
        "items": len(base["by_item"]),
        "customers": len(base["by_customer"]),
        "by_category": _cut_totals(base["by_category"]),
        "by_channel": _cut_totals(base["by_channel"]),
        "by_customer": _cut_totals(base["by_customer"]),
        "cogs_from_issue_ledger": base["from_ledger"],
        "cogs_from_average_cost": base["from_average"],
        "unmapped_lines": base["unmapped_lines"],
        "mixed_currency": base["mixed_currency"],
        "currencies": sorted(base["currencies"]),
        "revenue_basis": "quantity_ordered x unit_price x (1 - discount_pct/100), before tax",
        "cogs_basis": ("the item's issue-weighted unit cost from the StockMove ledger for this "
                       "window, falling back to Item.average_cost where the item did not move"),
        "note": OPERATIONAL_ESTIMATE_NOTE,
        "unmapped_note": ("Order lines with no Item behind them (converted from a CRM quote and "
                          "never mapped) contribute revenue and no cost. They are counted here "
                          "rather than costed at zero, which would render as pure margin."),
        "truncated": base["truncated"],
    }, rows=_cut_rows(base["by_item"]))


def _r_margin_after_cost_to_serve_pct(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Gross margin less what it actually cost to serve the order — the differentiator.

    Four legs come off the gross margin, each measured on real rows and each reported separately so
    a reader can see which one is eating the business:

    * **freight** — audited ``FreightInvoice.billed_amount`` reached through the shipment's sales
      order, so it lands on the customer that caused it;
    * **returns** — 4.10's write-down (see :func:`_returns_cost`), also per customer;
    * **cost of quality** — 4.9's ``NonConformance.cost_of_quality`` plus 4.10's warranty spend;
    * **warehouse handling** — 4.4's picked lines and units at the two stated planning rates.

    Freight and returns are CAUSED by a customer and are charged to that customer. Quality and
    handling are not attributable to one — an NCR is about an item and a pick line is about a
    warehouse — so the customer ranking allocates them pro rata on revenue share and says so. The
    headline is unaffected by that choice: it is total profit over total revenue either way.
    """
    base = _margin_base(tenant, scope, start, end)
    if base["revenue"] <= ZERO:
        return _unavailable("margin_after_cost_to_serve_pct",
                            "No sales-order value in this window to serve, so there is no "
                            "cost-to-serve margin to measure.",
                            note=OPERATIONAL_ESTIMATE_NOTE)
    freight_rows = list(_audited_freight(tenant, NETWORK, start, end)
                        .filter(shipment__sales_order__isnull=False)
                        .values("shipment__sales_order__customer_id",
                                "shipment__sales_order__customer__name")
                        .annotate(billed=Sum("billed_amount"), bills=Count("id"))[:MAX_GROUP_ROWS])
    freight_total = sum((row["billed"] or ZERO for row in freight_rows), ZERO)
    freight_by_customer = {row["shipment__sales_order__customer_id"]: row["billed"] or ZERO
                           for row in freight_rows}
    returns = _returns_cost(tenant, start, end)
    quality = _quality_cost(tenant, start, end)
    handling = _handling_proxy(tenant, start, end)

    quality_total = quality["nonconformance_cost"] + quality["warranty_cost"]
    unallocated = quality_total + handling["cost"]
    cost_to_serve = freight_total + returns["cost"] + unallocated
    net_profit = base["gross_profit"] - cost_to_serve

    ranking = []
    for customer_id, bucket in base["by_customer"].items():
        revenue = bucket["revenue"]
        share = _safe_div(revenue, base["revenue"]) or ZERO
        freight = freight_by_customer.get(customer_id, ZERO)
        returned = (returns["by_customer"].get(customer_id) or {}).get("cost", ZERO)
        allocated = unallocated * share
        profit = revenue - bucket["cogs"] - freight - returned - allocated
        ranking.append({"customer": bucket["label"], "revenue": _f(revenue),
                        "cogs": _f(bucket["cogs"]),
                        "gross_profit": _f(revenue - bucket["cogs"]),
                        "freight": _f(freight), "returns": _f(returned),
                        "allocated_overhead": _f(allocated), "net_profit": _f(profit),
                        "net_margin_pct": _f(_safe_div(profit * HUNDRED, revenue)),
                        "revenue_share_pct": _f(share * HUNDRED)})
    ranking.sort(key=lambda row: (row["net_profit"] is None, row["net_profit"] or 0))
    return _result("margin_after_cost_to_serve_pct",
                   _safe_div(net_profit * HUNDRED, base["revenue"]), breakdown={
                       "revenue": _f(base["revenue"]),
                       "cogs": _f(base["cogs"]),
                       "gross_profit": _f(base["gross_profit"]),
                       "gross_margin_pct": _f(base["margin_pct"]),
                       "cost_to_serve": _f(cost_to_serve),
                       "cost_to_serve_pct_of_revenue": _f(
                           _safe_div(cost_to_serve * HUNDRED, base["revenue"])),
                       "net_profit": _f(net_profit),
                       "freight_cost": _f(freight_total),
                       "freight_bills": sum(row["bills"] or 0 for row in freight_rows),
                       "returns_cost": _f(returns["cost"]),
                       "returns_dispositions": returns["dispositions"],
                       "returns_basis": returns["basis"],
                       "quality_cost": _f(quality_total),
                       "nonconformance_cost": _f(quality["nonconformance_cost"]),
                       "nonconformances": quality["nonconformances"],
                       "warranty_cost": _f(quality["warranty_cost"]),
                       "warranty_recoverable": _f(quality["warranty_recoverable"]),
                       "warranty_note": quality["note"],
                       "handling_cost": _f(handling["cost"]),
                       "handling_pick_lines": handling["lines"],
                       "handling_pick_units": _f(handling["units"], 4),
                       "handling_rate_per_line": _f(handling["rate_per_line"]),
                       "handling_rate_per_unit": _f(handling["rate_per_unit"]),
                       "handling_basis": handling["basis"],
                       "customers_ranked": len(ranking),
                       "allocation": ("Freight and returns are charged to the customer that caused "
                                      "them. Quality and handling are not attributable to one "
                                      "customer, so the ranking spreads them on revenue share; the "
                                      "headline is total profit over total revenue and does not "
                                      "depend on that choice."),
                       "mixed_currency": base["mixed_currency"],
                       "currencies": sorted(base["currencies"]),
                       "note": OPERATIONAL_ESTIMATE_NOTE,
                       "truncated": base["truncated"] or returns["truncated"],
                   }, rows=ranking[:MAX_DETAIL_ROWS])


def _r_supply_cost_stack(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """The whole supply chain's cost, leg by leg — a waterfall, not a single figure.

    ``kind="table"``: the ROWS are the result and the value is their total. Seven legs, each from
    the sub-module that owns it, and each one able to say which table it came from.

    **Production is CONVERSION cost only** — labour and machine time from 4.8's
    ``ProductionTimeLog`` at the work centre's rates. The materials a work order consumed are
    already in the purchase leg, and adding the consumption ledger here would count the same money
    twice. ``downtime`` logs are excluded for the reason 4.8 excludes them: idle time is a loss
    metric, not a cost the good units absorb.
    """
    orders = _spend_orders(tenant, scope, start, end)
    purchase = orders.aggregate(total=Sum("total"), orders=Count("id"))
    freight = _audited_freight(tenant, scope, start, end).aggregate(
        inbound=Sum("billed_amount", filter=Q(shipment__direction="inbound")),
        outbound=Sum("billed_amount", filter=Q(shipment__direction="outbound")),
        unattributed=Sum("billed_amount", filter=Q(shipment__isnull=True)),
        billed=Sum("billed_amount"), bills=Count("id"))
    handling = _handling_proxy(tenant, start, end)
    quality = _quality_cost(tenant, start, end)
    returns = _returns_cost(tenant, start, end)

    logs = ProductionTimeLog.objects.filter(tenant=tenant).exclude(entry_type="downtime")
    logs = _in_moments(logs, "started_at", start, end)
    # Minute-cost is summed in SQL and divided by 60 ONCE in Python: dividing inside the aggregate
    # would need a Decimal Value in the expression on every backend, and this way the rounding
    # happens once instead of per row.
    production = logs.aggregate(
        labor=Sum(Case(When(entry_type__in=("setup", "labor"),
                            then=F("duration_minutes") * F("work_center__labor_cost_per_hour")),
                       output_field=_DEC)),
        machine=Sum(Case(When(entry_type="machine",
                              then=F("duration_minutes") * F("work_center__machine_cost_per_hour")),
                         output_field=_DEC)),
        minutes=Sum("duration_minutes"), logs=Count("id"), orders=Count("work_order", distinct=True))
    labor_cost = (production["labor"] or ZERO) / MINUTES_PER_HOUR
    machine_cost = (production["machine"] or ZERO) / MINUTES_PER_HOUR

    legs = [
        ("purchase", "Purchase cost", purchase["total"] or ZERO,
         "PurchaseOrder.total on committed orders (4.1)"),
        ("inbound_freight", "Inbound freight", freight["inbound"] or ZERO,
         "audited FreightInvoice.billed_amount on inbound shipments (4.6)"),
        ("warehousing", "Warehousing & handling", handling["cost"],
         "picked lines and units at the two stated planning rates (4.4)"),
        ("production", "Production conversion", labor_cost + machine_cost,
         "ProductionTimeLog labour and machine hours at work-centre rates (4.8)"),
        ("outbound_freight", "Outbound freight", freight["outbound"] or ZERO,
         "audited FreightInvoice.billed_amount on outbound shipments (4.6)"),
        ("quality", "Cost of quality", quality["nonconformance_cost"] + quality["warranty_cost"],
         "NonConformance.cost_of_quality (4.9) plus warranty claim costs (4.10)"),
        ("returns", "Returns & write-downs", returns["cost"],
         "ReturnDisposition write-down against the original unit cost (4.10)"),
    ]
    total = sum((amount for _, _, amount, _ in legs), ZERO)
    if total <= ZERO:
        return _unavailable("supply_cost_stack",
                            "No purchasing, freight, picking, production, quality or returns "
                            "activity in this window to build a cost stack from.",
                            note=OPERATIONAL_ESTIMATE_NOTE)
    rows = [{"leg": label, "key": key, "amount": _f(amount),
             "share_pct": _f(_safe_div(amount * HUNDRED, total)), "source": source}
            for key, label, amount, source in legs]
    codes, mixed = _currency_codes(orders)
    return _result("supply_cost_stack", total, breakdown={
        "total": _f(total),
        "legs": {key: _f(amount) for key, _, amount, _ in legs},
        "purchase_orders": purchase["orders"] or 0,
        "freight_bills": freight["bills"] or 0,
        "freight_unattributed": _f(freight["unattributed"]),
        "pick_lines": handling["lines"],
        "handling_rate_per_line": _f(handling["rate_per_line"]),
        "handling_rate_per_unit": _f(handling["rate_per_unit"]),
        "handling_basis": handling["basis"],
        "production_labor": _f(labor_cost),
        "production_machine": _f(machine_cost),
        "production_hours": _f(Decimal(production["minutes"] or 0) / MINUTES_PER_HOUR),
        "work_orders": production["orders"] or 0,
        "nonconformances": quality["nonconformances"],
        "returns_dispositions": returns["dispositions"],
        "mixed_currency": mixed,
        "currencies": codes,
        "double_count_guard": ("Production is CONVERSION cost only (labour and machine time). The "
                               "materials a work order consumed are already inside the purchase "
                               "leg, so the consumption ledger is deliberately not added here."),
        "note": OPERATIONAL_ESTIMATE_NOTE,
        "truncated": returns["truncated"],
    }, rows=rows)


def _r_ppv_value(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """What was paid above (or below) the item's standard cost — purchase price variance.

    TWO queries: the purchase lines grouped by their free-text ``sku_hint``, and the items whose
    ``sku`` those hints resolve to. Items with no standard cost are excluded — there is no standard
    to vary from, and treating a blank as zero would report the entire spend as adverse variance.

    **The join is the caveat** (see :data:`SKU_HINT_CAVEAT`): 4.1's purchase-order lines carry free
    text and no ``Item`` FK, so a mistyped or blank hint simply does not match and its spend is
    invisible to this figure. The unmatched spend is reported so the coverage is legible.
    """
    orders = PurchaseOrder.objects.filter(tenant=tenant, status__in=SPEND_PO_STATUSES)
    if scope.value == "vendor":
        orders = orders.filter(vendor=scope.subject)
    orders = _in_dates(orders, "order_date", start, end)
    lines = PurchaseOrderLine.objects.filter(purchase_order__in=orders).exclude(sku_hint="")
    # The quantity alias is `qty`, NOT `quantity`: within one .annotate() Django resolves later
    # arguments against the aliases already declared in it, so `quantity=Sum("quantity")` beside
    # `spend=Sum(F("quantity") * ...)` makes the F() point at the aggregate and raises
    # "Cannot compute Sum(...): ... is an aggregate". Same trap _r_spend_off_contract_pct documents.
    fetched = list(lines.values("sku_hint")
                   .annotate(spend=Sum(F("quantity") * F("unit_price"), output_field=_DEC),
                             qty=Sum("quantity"),
                             line_count=Count("id"),
                             orders=Count("purchase_order", distinct=True))
                   .order_by("-spend")[:MAX_GROUP_ROWS + 1])
    truncated = len(fetched) > MAX_GROUP_ROWS
    fetched = fetched[:MAX_GROUP_ROWS]
    if not fetched:
        return _unavailable("ppv_value",
                            "No committed purchase-order line in this window carries a SKU hint to "
                            "match against the item catalog.",
                            sku_caveat=SKU_HINT_CAVEAT, note=OPERATIONAL_ESTIMATE_NOTE)
    items = Item.objects.filter(tenant=tenant, sku__in=[row["sku_hint"] for row in fetched])
    if scope.value == "category":
        items = items.filter(category=scope.subject)
    catalog = {row["sku"]: row for row in
               items.values("sku", "name", "standard_cost",
                            "category__name")[:MAX_GROUP_ROWS]}

    total, detail, unmatched_spend, no_standard = ZERO, [], ZERO, 0
    for row in fetched:
        item = catalog.get(row["sku_hint"])
        spend = row["spend"] or ZERO
        if item is None:
            unmatched_spend += spend
            continue
        standard = item["standard_cost"] or ZERO
        if standard <= ZERO:
            no_standard += 1
            continue
        quantity = row["qty"] or ZERO
        variance = spend - standard * quantity
        total += variance
        detail.append({"sku": row["sku_hint"], "name": item["name"],
                       "category": item["category__name"] or "(uncategorised)",
                       "quantity": _f(quantity, 4), "spend": _f(spend),
                       "standard_cost": _f(standard, 4),
                       "average_paid": _f(_safe_div(spend, quantity), 4),
                       "variance": _f(variance),
                       "variance_pct": _f(_safe_div(variance * HUNDRED, standard * quantity)),
                       "orders": row["orders"]})
    if not detail:
        return _unavailable("ppv_value",
                            "No purchase-order line in this window matched an item that carries a "
                            "standard cost, so there is no standard to measure a variance against.",
                            sku_hints=len(fetched), items_without_standard=no_standard,
                            unmatched_spend=_f(unmatched_spend), sku_caveat=SKU_HINT_CAVEAT,
                            note=OPERATIONAL_ESTIMATE_NOTE)
    detail.sort(key=lambda row: -(row["variance"] or 0))
    codes, mixed = _currency_codes(orders)
    return _result("ppv_value", total, breakdown={
        "skus_matched": len(detail),
        "sku_hints": len(fetched),
        "items_without_standard_cost": no_standard,
        "unmatched_spend": _f(unmatched_spend),
        "adverse_variance": _f(sum((Decimal(str(row["variance"])) for row in detail
                                    if (row["variance"] or 0) > 0), ZERO)),
        "favourable_variance": _f(sum((Decimal(str(row["variance"])) for row in detail
                                       if (row["variance"] or 0) < 0), ZERO)),
        "basis": "sum over matched SKUs of (spend - Item.standard_cost x quantity)",
        "sku_caveat": SKU_HINT_CAVEAT,
        "mixed_currency": mixed,
        "currencies": codes,
        "note": OPERATIONAL_ESTIMATE_NOTE,
        "sign": "Positive is adverse — more was paid than the standard says the item should cost.",
        "truncated": truncated,
    }, rows=detail[:MAX_DETAIL_ROWS])


def _r_scrap_value(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Stock written off the ledger, valued, and split by what wrote it off.

    Every write-off in this app is a NEGATIVE ``adjustment`` move, and every writer stamps the
    source document's number on it: ``NCR-`` for a 4.9 quality disposition, ``RMA-`` for a 4.10
    return write-off, ``ADJ-`` for a stock adjustment or cycle count. That reference convention is
    what makes the split possible without a second column, and the 4.9 rows are joined back to
    ``NonConformance`` so the quality share is broken out by its real disposition.
    """
    moves = StockMove.objects.filter(tenant=tenant, move_type="adjustment", quantity__lt=ZERO)
    moves = _in_moments(scope.narrow_item_rows(moves), "moved_at", start, end)
    # `qty`, not `quantity` — see the note in _r_ppv_value: an alias that shadows a real column
    # makes every later F() in the same .annotate() point at the aggregate instead of the column.
    fetched = list(moves.values("reference", "item_id", "item__sku", "item__name")
                   .annotate(cost=Sum(F("quantity") * F("unit_cost"), output_field=_DEC),
                             qty=Sum("quantity"),
                             move_count=Count("id"))[:MAX_GROUP_ROWS + 1])
    truncated = len(fetched) > MAX_GROUP_ROWS
    fetched = fetched[:MAX_GROUP_ROWS]
    if not fetched:
        return _unavailable("scrap_value",
                            "No stock was written off in this window. Write-offs are negative "
                            "'adjustment' moves on the append-only ledger.",
                            note=OPERATIONAL_ESTIMATE_NOTE)
    ncr_numbers = {row["reference"] for row in fetched
                   if (row["reference"] or "").startswith(NCR_REFERENCE_PREFIX)}
    ncr_dispositions = {}
    if ncr_numbers:
        ncr_dispositions = {row["number"]: (row["disposition"], row["severity"]) for row in
                            NonConformance.objects.filter(tenant=tenant, number__in=ncr_numbers)
                            .values("number", "disposition", "severity")[:MAX_GROUP_ROWS]}

    total, by_source, by_disposition, by_item, detail = ZERO, {}, {}, {}, []
    for row in fetched:
        # Outbound quantities are negative in the ledger; negate both so the loss reads positive.
        value = -(row["cost"] or ZERO)
        quantity = -(row["qty"] or ZERO)
        reference = row["reference"] or ""
        total += value
        if reference.startswith(NCR_REFERENCE_PREFIX):
            source = "quality (4.9 NCR)"
            disposition = (ncr_dispositions.get(reference) or ("unmatched", ""))[0]
            by_disposition[disposition] = by_disposition.get(disposition, ZERO) + value
        elif reference.startswith(RETURN_REFERENCE_PREFIX):
            source = "returns (4.10 write-off)"
        elif reference:
            source = "stock adjustment (4.3)"
        else:
            source = "unreferenced"
        by_source[source] = by_source.get(source, ZERO) + value
        bucket = by_item.setdefault(row["item_id"], {"sku": row["item__sku"],
                                                     "name": row["item__name"],
                                                     "value": ZERO, "quantity": ZERO})
        bucket["value"] += value
        bucket["quantity"] += quantity
        detail.append({"reference": reference, "sku": row["item__sku"], "name": row["item__name"],
                       "source": source, "quantity": _f(quantity, 4), "value": _f(value),
                       "moves": row["move_count"]})
    detail.sort(key=lambda row: -(row["value"] or 0))
    return _result("scrap_value", total, breakdown={
        "write_offs": len(fetched),
        "items": len(by_item),
        "by_source": {name: _f(value) for name, value in sorted(by_source.items())},
        "by_ncr_disposition": {name: _f(value) for name, value in sorted(by_disposition.items())},
        "top_items": {bucket["sku"]: _f(bucket["value"]) for bucket in
                      sorted(by_item.values(), key=lambda entry: -entry["value"])[:MAX_DETAIL_ROWS]},
        "basis": "negative 'adjustment' StockMove quantity x its unit_cost",
        "source_split": ("Each write-off carries its source document's number: NCR- is a 4.9 "
                         "quality disposition, RMA- a 4.10 return write-off, ADJ- a stock "
                         "adjustment or cycle count. An 'unmatched' NCR disposition means the "
                         "reference no longer resolves to a nonconformance row."),
        "excludes": ("Consumption and production moves — a work order drawing components is not "
                     "scrap, and 4.8 gives it its own move types precisely so this can tell them "
                     "apart."),
        "note": OPERATIONAL_ESTIMATE_NOTE,
        "truncated": truncated,
    }, rows=detail[:MAX_DETAIL_ROWS])


# =================================================================================================
# 13. RISK resolvers
#
# Group -> the `disruption_risk` page.
#
# HONEST FRAMING, AND IT IS NOT NEGOTIABLE. Every score below is a DETERMINISTIC weighted composite
# over rows that already exist, and every one renders its own component arithmetic — the points, the
# evidence behind them and a sentence saying what the component means. There is no model, no
# training set, no inference and no "AI" anywhere in this file or on the page it feeds. Run it twice
# on the same data and it returns the same number, and anyone can check it by hand. Genuine
# ML/AutoML is Module 10's 10.13. Whatever the module bullet calls this, the page says what it
# actually does, which is arithmetic somebody reviewed.
# =================================================================================================

#: :func:`_r_supplier_disruption_score`'s weights. Same shape and same re-weighting rule as
#: ``SupplierScorecard.recompute_overall`` (4.2): a component with no signal DROPS OUT and the rest
#: are re-weighted over whatever is present, so a supplier with no risk assessment on file is scored
#: on what IS known rather than penalised for the gap or flattered by a phantom zero.
DISRUPTION_WEIGHTS = {
    "late_delivery": 25,
    "quality_rejects": 12,
    "nonconformances": 8,
    "open_capa": 8,
    "contract_cover": 12,
    "concentration": 10,
    "acknowledgement": 5,
    "stored_risk_index": 20,
}

#: Severity -> points, for the nonconformance component. Stated, not derived.
NCR_SEVERITY_POINTS = {"critical": Decimal("4"), "major": Decimal("2"),
                       "minor": Decimal("1"), "observation": Decimal("0.5")}

#: CAPA statuses that are still work in progress.
OPEN_CAPA_STATUSES = ("open", "investigating", "in_progress", "pending_verification")

#: Purchase-order statuses by which an acknowledgement should have arrived. An approved-but-unsent
#: order has not been asked yet, so counting it as unacknowledged would blame the supplier for our
#: own backlog.
ACK_EXPECTED_PO_STATUSES = ("sent", "acknowledged", "partially_received", "received", "closed")

#: Risk assessments that represent a real view. A draft is somebody's half-finished opinion.
PUBLISHED_RISK_STATUSES = ("submitted", "reviewed")


def _clamp_score(value):
    """Bound a component to 0-100 — every component is a percentage of "as bad as this gets"."""
    if value is None:
        return None
    return min(max(Decimal(value), ZERO), HUNDRED)


def _latest_risk_indices(tenant, party=None):
    """``{party_id: (risk_index, risk_level, assessment_date, number)}`` — the LATEST per supplier.

    ONE ordered, capped query folded in Python. A per-party ``MAX(assessment_date)`` subquery would
    be one query per supplier, and 4.2 does not store a "current" flag.
    """
    qs = SupplierRiskAssessment.objects.filter(tenant=tenant,
                                               status__in=PUBLISHED_RISK_STATUSES)
    if party is not None:
        qs = qs.filter(party=party)
    latest = {}
    for row in (qs.order_by("-assessment_date", "-id")
                .values("party_id", "party__name", "risk_index", "risk_level", "assessment_date",
                        "number")[:MAX_GROUP_ROWS]):
        latest.setdefault(row["party_id"], row)
    return latest


def _contract_cover(tenant, vendor_ids, as_of, horizon_days):
    """``(covered, expiring, detail)`` for a set of suppliers — TWO queries, never one per vendor."""
    if not vendor_ids:
        return set(), set(), {}
    horizon = as_of + timedelta(days=horizon_days)
    rows = list(SupplierContract.objects
                .filter(tenant=tenant, party_id__in=vendor_ids,
                        status__in=COVERING_CONTRACT_STATUSES)
                .filter(Q(start_date__isnull=True) | Q(start_date__lte=as_of))
                .filter(Q(end_date__isnull=True) | Q(end_date__gte=as_of))
                .values("party_id", "party__name", "number", "title",
                        "end_date")[:MAX_GROUP_ROWS])
    covered, expiring, detail = set(), set(), {}
    for row in rows:
        covered.add(row["party_id"])
        soonest = detail.get(row["party_id"])
        end_date = row["end_date"]
        if end_date is not None and end_date <= horizon:
            expiring.add(row["party_id"])
        if soonest is None or (end_date is not None
                               and (soonest["end_date"] is None or end_date < soonest["end_date"])):
            detail[row["party_id"]] = row
    # A supplier with one contract expiring next week and another running for three years is
    # covered, not expiring — the later contract is the cover.
    expiring = {party_id for party_id in expiring
                if (detail.get(party_id) or {}).get("end_date") is not None
                and detail[party_id]["end_date"] <= horizon}
    return covered, expiring, detail


def _sole_source_share(tenant, party, start, end):
    """``(sole_sourced, supplied, pct)`` — how much of what this supplier sells only it sells.

    ONE grouped query over the whole tenant's committed purchase lines: per ``sku_hint``, how many
    distinct vendors supplied it and whether this one is among them. Best-effort on the free-text
    hint (see :data:`SKU_HINT_CAVEAT`).
    """
    orders = _in_dates(PurchaseOrder.objects.filter(tenant=tenant, status__in=SPEND_PO_STATUSES),
                       "order_date", start, end)
    rows = list(PurchaseOrderLine.objects.filter(purchase_order__in=orders).exclude(sku_hint="")
                .values("sku_hint")
                .annotate(vendors=Count("purchase_order__vendor", distinct=True),
                          mine=Count("id", filter=Q(purchase_order__vendor=party)))[:MAX_GROUP_ROWS])
    supplied = [row for row in rows if (row["mine"] or 0) > 0]
    sole = [row for row in supplied if (row["vendors"] or 0) == 1]
    return len(sole), len(supplied), _safe_div(Decimal(len(sole)) * HUNDRED,
                                               Decimal(len(supplied))) if supplied else None


def _r_supplier_disruption_score(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """A 0-100 disruption composite for one supplier, or for the supply base as a whole.

    Eight components, each scored 0 (no concern) to 100 (as bad as this component gets), blended on
    :data:`DISRUPTION_WEIGHTS` and **re-weighted over whichever components have a signal** — the
    exact rule ``SupplierScorecard.recompute_overall`` already uses, so a supplier with no risk
    assessment on file is scored on what is known rather than given a phantom zero.

    ``breakdown["components"]`` carries, for every component, its points, its weight, the share of
    the final score it contributed, the raw evidence it was computed from and one line saying what
    it means. That is the whole point: this number is a claim about a supplier's reliability, and a
    claim nobody can check is not worth making.

    **4.2's ``SupplierRiskAssessment.risk_index`` is ONE weighted input here — it is not rebuilt.**
    4.2 owns the risk register; a second one under a second name would give the tenant two
    contradictory answers about the same supplier.
    """
    party = scope.subject if scope.value == "vendor" else None
    horizon_days = params.days or CONTRACT_EXPIRY_DAYS
    as_of = end or timezone.localdate()
    components = {}

    def add(key, points, evidence, explanation):
        points = _clamp_score(points)
        if points is None:
            components[key] = {"points": None, "weight": DISRUPTION_WEIGHTS[key],
                               "evidence": evidence, "explanation": explanation,
                               "scored": False}
        else:
            components[key] = {"points": _f(points), "weight": DISRUPTION_WEIGHTS[key],
                               "evidence": evidence, "explanation": explanation, "scored": True,
                               "_raw": points}

    # 1. Late delivery — the shared 4.2 arithmetic, not a rival one.
    delivery = supplier_delivery_stats(tenant, party, start, end)
    add("late_delivery",
        (HUNDRED - delivery["pct"]) if delivery["pct"] is not None else None,
        {"receipts": delivery["datable"], "on_time": delivery["on_time"], "late": delivery["late"],
         "otd_pct": _f(delivery["pct"])},
        "The share of dated receipts that arrived late. 100 points = nothing arrived on time.")

    # 2. Quality rejects — likewise shared with the 4.2 scorecard.
    quality = supplier_quality_stats(tenant, party, start, end)
    add("quality_rejects",
        (quality["reject_pct"] * 5) if quality["reject_pct"] is not None else None,
        {"received": _f(quality["received"], 4), "rejected": _f(quality["rejected"], 4),
         "reject_pct": _f(quality["reject_pct"]), "scale": "reject % x 5, so 20% rejected = 100"},
        "Quantity rejected as a share of everything presented, on a stated linear scale.")

    # Is there a supplier relationship here AT ALL? The two absolute-count components below
    # (nonconformances, open CAPAs) are the only ones whose natural value on an empty tenant is a
    # confident ZERO — "no quality failures, no corrective actions, nothing to worry about" —
    # computed from no rows whatsoever. That is the reassuring-zero failure `_r_inv_expiry_risk_value`
    # already had to fix: a green 0 that means "we have no data", rendered identically to a green 0
    # that means "we checked and it is clean". So both are scored ONLY when something establishes
    # that the subject really is a supplier we trade with. Both figures are already in hand — this
    # costs no query.
    has_relationship = bool(delivery["datable"]) or quality["presented"] > ZERO

    # 3. Nonconformances — 4.9 rows weighted by their own severity.
    ncr_qs = _in_dates(NonConformance.objects.filter(tenant=tenant, supplier__isnull=False),
                       "detected_on", start, end)
    if party is not None:
        ncr_qs = ncr_qs.filter(supplier=party)
    ncr_rows = list(ncr_qs.values("supplier_id", "supplier__name", "severity")
                    .annotate(n=Count("id"))[:MAX_GROUP_ROWS])
    ncr_by_severity, ncr_by_party = {}, {}
    for row in ncr_rows:
        ncr_by_severity[row["severity"]] = ncr_by_severity.get(row["severity"], 0) + row["n"]
        bucket = ncr_by_party.setdefault(row["supplier_id"], {"name": row["supplier__name"],
                                                              "count": 0, "weighted": ZERO})
        bucket["count"] += row["n"]
        bucket["weighted"] += NCR_SEVERITY_POINTS.get(row["severity"], ZERO) * row["n"]
    weighted_ncr = sum((bucket["weighted"] for bucket in ncr_by_party.values()), ZERO)
    add("nonconformances",
        weighted_ncr * 10 if ncr_rows else (ZERO if has_relationship else None),
        {"nonconformances": sum(ncr_by_severity.values()), "by_severity": ncr_by_severity,
         "severity_weighted": _f(weighted_ncr),
         "scale": "severity-weighted count x 10 (critical 4, major 2, minor 1, observation 0.5)"},
        "Quality failures raised against this supplier, weighted by how serious each one was.")

    # 4. Open corrective actions — work this supplier still owes.
    capa_qs = CapaAction.objects.filter(tenant=tenant, supplier__isnull=False,
                                        status__in=OPEN_CAPA_STATUSES)
    if party is not None:
        capa_qs = capa_qs.filter(supplier=party)
    capa_rows = list(capa_qs.values("supplier_id", "supplier__name")
                     .annotate(n=Count("id"), overdue=Count("id", filter=Q(due_date__lt=as_of)))
                     [:MAX_GROUP_ROWS])
    open_capa = sum(row["n"] or 0 for row in capa_rows)
    overdue_capa = sum(row["overdue"] or 0 for row in capa_rows)
    add("open_capa",
        Decimal(open_capa) * 20 if capa_rows else (ZERO if has_relationship else None),
        {"open": open_capa, "overdue": overdue_capa,
         "statuses": list(OPEN_CAPA_STATUSES), "scale": "20 points per open CAPA, capped at 100"},
        "Corrective actions still open against this supplier — unfinished business is exposure.")

    # 5. Contract cover.
    if party is not None:
        vendor_ids = {party.pk}
    else:
        vendor_ids = set(_in_dates(PurchaseOrder.objects.filter(tenant=tenant,
                                                                status__in=SPEND_PO_STATUSES),
                                   "order_date", start, end)
                         .values_list("vendor_id", flat=True).distinct()[:MAX_GROUP_ROWS])
    covered, expiring, contract_detail = _contract_cover(tenant, vendor_ids, as_of, horizon_days)
    if not vendor_ids:
        cover_points, cover_evidence = None, {"suppliers": 0}
    elif party is not None:
        contract = contract_detail.get(party.pk)
        cover_points = (HUNDRED if party.pk not in covered
                        else (Decimal("60") if party.pk in expiring else ZERO))
        cover_evidence = {"covered": party.pk in covered, "expiring": party.pk in expiring,
                          "contract": (contract or {}).get("number", ""),
                          "ends": _iso((contract or {}).get("end_date")),
                          "horizon_days": horizon_days}
    else:
        uncovered = len(vendor_ids - covered)
        cover_points = _safe_div(Decimal(uncovered) * HUNDRED, Decimal(len(vendor_ids)))
        cover_evidence = {"suppliers": len(vendor_ids), "covered": len(covered),
                          "uncovered": uncovered, "expiring": len(expiring),
                          "horizon_days": horizon_days}
    add("contract_cover", cover_points, cover_evidence,
        "No live contract scores 100; one ending inside the horizon scores 60; covered scores 0.")

    # 6. Concentration — how exposed we are if this supplier stops.
    if party is not None:
        sole, supplied, sole_pct = _sole_source_share(tenant, party, start, end)
        add("concentration", sole_pct,
            {"sku_hints_supplied": supplied, "sole_sourced": sole,
             "sole_source_pct": _f(sole_pct), "caveat": SKU_HINT_CAVEAT},
            "The share of what this supplier sells us that nobody else currently does.")
    else:
        top = compute_metric(tenant, "spend_top_supplier_share_pct", start, end, scope=NETWORK)
        add("concentration", top.get("value"),
            {"top5_share_pct": _f(top.get("value")),
             "suppliers_ranked": (top.get("breakdown") or {}).get("suppliers_ranked")},
            "How much of total spend sits with the five biggest suppliers.")

    # 7. Acknowledgement discipline.
    ack_qs = _in_dates(PurchaseOrder.objects.filter(tenant=tenant,
                                                    status__in=ACK_EXPECTED_PO_STATUSES),
                       "order_date", start, end)
    if party is not None:
        ack_qs = ack_qs.filter(vendor=party)
    ack = ack_qs.aggregate(sent=Count("id"),
                           acknowledged=Count("id", filter=Q(acknowledged_at__isnull=False)))
    sent = ack["sent"] or 0
    acknowledged = ack["acknowledged"] or 0
    add("acknowledgement",
        _safe_div(Decimal(sent - acknowledged) * HUNDRED, Decimal(sent)) if sent else None,
        {"orders_sent": sent, "acknowledged": acknowledged, "unacknowledged": sent - acknowledged},
        "Orders dispatched to this supplier that were never acknowledged back.")

    # 8. 4.2's STORED risk register — read, never rebuilt.
    indices = _latest_risk_indices(tenant, party)
    if party is not None:
        assessment = indices.get(party.pk)
        index = assessment["risk_index"] if assessment else None
        evidence = {"assessment": (assessment or {}).get("number", ""),
                    "risk_index": _f(index), "risk_level": (assessment or {}).get("risk_level", ""),
                    "assessed_on": _iso((assessment or {}).get("assessment_date"))}
    else:
        values = [row["risk_index"] for row in indices.values() if row["risk_index"] is not None]
        index = (sum(values, ZERO) / Decimal(len(values))) if values else None
        evidence = {"suppliers_assessed": len(values), "mean_risk_index": _f(index)}
    add("stored_risk_index",
        ((Decimal(index) - Decimal("1")) * HUNDRED / Decimal("4")) if index else None,
        evidence,
        "4.2's own financial/geopolitical/compliance/operational review, rescaled from 1-5 to 0-100.")

    scored = {key: entry for key, entry in components.items() if entry["scored"]}
    if not scored:
        return _unavailable("supplier_disruption_score",
                            "There is no delivery, quality, contract, acknowledgement or risk-"
                            "assessment signal for this supplier in the window, so nothing can be "
                            "scored. A supplier with no history is an unknown, not a safe bet.",
                            components={key: entry["explanation"]
                                        for key, entry in components.items()},
                            parameter_days=horizon_days)
    total_weight = sum(entry["weight"] for entry in scored.values())
    composite = sum((entry["_raw"] * entry["weight"] for entry in scored.values()),
                    ZERO) / Decimal(total_weight)
    for key, entry in components.items():
        raw = entry.pop("_raw", None)
        entry["contribution"] = (_f(raw * entry["weight"] / Decimal(total_weight))
                                 if raw is not None else None)

    if party is not None:
        rows = [{"component": key, "points": entry["points"], "weight": entry["weight"],
                 "contribution": entry["contribution"], "scored": entry["scored"],
                 "explanation": entry["explanation"]}
                for key, entry in components.items()]
    else:
        # The network figure's supporting rows are the per-supplier league built from the grouped
        # queries already run above — no extra query, and no per-supplier composite (that would be
        # one full pass per supplier, which is the N+1 this whole file is written to avoid).
        league = {}
        for row in _delivery_rows(tenant, None, start, end):
            league.setdefault(row["vendor_id"], {"vendor": row["vendor"]}).update(
                {"receipts": row["datable"], "on_time": row["on_time"],
                 "otd_pct": _f(_safe_div(Decimal(row["on_time"]) * HUNDRED,
                                         Decimal(row["datable"])) if row["datable"] else None)})
        for row in _quality_rows(tenant, None, start, end):
            entry = league.setdefault(row["vendor_id"], {"vendor": row["vendor"]})
            presented = row["received"] + row["rejected"]
            entry["reject_pct"] = _f(_safe_div(row["rejected"] * HUNDRED, presented)
                                     if presented > ZERO else None)
        for party_id, entry in ncr_by_party.items():
            league.setdefault(party_id, {"vendor": entry["name"]})["nonconformances"] = entry["count"]
        for row in capa_rows:
            league.setdefault(row["supplier_id"],
                              {"vendor": row["supplier__name"]})["open_capa"] = row["n"]
        for party_id, row in indices.items():
            league.setdefault(party_id, {"vendor": row["party__name"]}).update(
                {"risk_index": _f(row["risk_index"]), "risk_level": row["risk_level"]})
        for party_id, entry in league.items():
            entry["contract_cover"] = ("covered" if party_id in covered else "none")
            if party_id in expiring:
                entry["contract_cover"] = "expiring"
        rows = sorted(league.values(), key=lambda entry: (entry.get("otd_pct") is None,
                                                          entry.get("otd_pct") or 0))
    return _result("supplier_disruption_score", composite, breakdown={
        "subject": scope.label,
        "components": components,
        "components_scored": len(scored),
        "components_total": len(components),
        "weights": dict(DISRUPTION_WEIGHTS),
        "weight_applied": total_weight,
        "parameter_days": horizon_days,
        "method": ("Deterministic weighted composite over rows that already exist. Each component "
                   "is scored 0-100, multiplied by its weight, and the total is divided by the "
                   "weight of the components that HAD a signal — the same re-weighting "
                   "SupplierScorecard.recompute_overall uses. No model, no training data, no "
                   "inference: run it twice on the same rows and it returns the same number."),
        "reuse": ("Delivery and quality come from the same functions 4.2's scorecard uses, and the "
                  "risk index is 4.2's STORED assessment read as one weighted input. 4.11 does not "
                  "keep a second supplier-risk register."),
        "direction": "Higher is worse — this is exposure, not performance.",
    }, rows=rows[:MAX_DETAIL_ROWS])


def _r_demand_spike_count(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Items whose recent demand rate has jumped clear of the window's own rate.

    Two grouped queries over the ledger: the whole window, and its final
    :data:`SPIKE_SHORT_DAYS` days. An item spikes when its short-window DAILY rate exceeds the whole
    window's daily rate by more than ``parameter_pct``.

    **The netting question, decided.** A 4.10 restock is posted by ``_post_stock_move`` as a POSITIVE
    ``receipt`` carrying ``reference=<the RMA number>``, and ``ReturnAuthorization`` numbers begin
    ``RMA-``; no other writer in this app puts an ``RMA-`` reference on a ``receipt`` (transfers
    stamp ``TRF-``, adjustments ``ADJ-``, goods receipts ``GRN-``, work orders ``WO-``, quality
    write-offs ``NCR-``). A restock is therefore RELIABLY IDENTIFIABLE, so this ships the **NETTED**
    series: demand is issues less returns-to-stock in the same bucket, and both halves are reported.

    Netting is a floor on the correction, not a full one, and the breakdown says so: a return
    scrapped instead of restocked, and a credit-only return where nothing comes back, leave no
    ``receipt`` row to net. Those still inflate the series — but by less than doing nothing would.
    """
    pct = params.pct if params.pct is not None else SPIKE_PCT
    span = window_days(start, end)
    if not span or span <= SPIKE_SHORT_DAYS:
        return _unavailable("demand_spike_count",
                            f"A spike is the last {SPIKE_SHORT_DAYS} days measured against a longer "
                            f"baseline, so the window has to be longer than that. Widen the date "
                            f"range.",
                            parameter_pct=_f(pct), window_days=span,
                            short_window_days=SPIKE_SHORT_DAYS)
    short_start = end - timedelta(days=SPIKE_SHORT_DAYS - 1)
    baseline = _demand_rows(tenant, scope, start, end)
    recent = _demand_rows(tenant, scope, short_start, end)
    if not baseline:
        return _unavailable("demand_spike_count",
                            "Nothing was issued from stock in this window, so there is no demand "
                            "series to find a spike in.",
                            parameter_pct=_f(pct))

    threshold = Decimal("1") + Decimal(pct) / HUNDRED
    spikes, new_demand, gross_total, returned_total = [], 0, ZERO, ZERO
    for item_id, row in baseline.items():
        gross_total += row["gross"]
        returned_total += row["returned"]
        recent_row = recent.get(item_id)
        if recent_row is None or recent_row["net"] <= ZERO:
            continue
        base_rate = row["net"] / Decimal(span)
        recent_rate = recent_row["net"] / Decimal(SPIKE_SHORT_DAYS)
        if base_rate <= ZERO:
            # Demand out of nothing is a NEW item, not a spike in an existing pattern. Counted and
            # reported separately: a ratio against a zero baseline is infinite, not informative.
            new_demand += 1
            continue
        ratio = recent_rate / base_rate
        if ratio <= threshold:
            continue
        spikes.append({"sku": row["sku"], "name": row["name"],
                       "baseline_daily": _f(base_rate, 4), "recent_daily": _f(recent_rate, 4),
                       "increase_pct": _f((ratio - Decimal("1")) * HUNDRED),
                       "recent_units": _f(recent_row["net"], 4),
                       "window_units": _f(row["net"], 4),
                       "returned_units": _f(recent_row["returned"], 4)})
    spikes.sort(key=lambda row: -(row["increase_pct"] or 0))

    signals = DemandSignal.objects.filter(tenant=tenant, signal_type="order_surge")
    signals = _in_moments(signals, "observed_at", start, end)
    surge_signals = signals.exclude(status__in=("dismissed", "expired")).count()
    forecast_periods = _in_dates(
        DemandForecastPeriod.objects.filter(forecast__tenant=tenant,
                                            forecast__status__in=("statistical", "in_review",
                                                                  "approved")),
        "period_end", start, end)
    forecast_totals = forecast_periods.aggregate(
        periods=Count("id"),
        uplifts=Count("id", filter=Q(final_quantity__gt=F("historical_quantity") * threshold)))
    return _result("demand_spike_count", Decimal(len(spikes)), breakdown={
        "parameter_pct": _f(pct),
        "window_days": span,
        "short_window_days": SPIKE_SHORT_DAYS,
        "short_window_start": _iso(short_start),
        "items_with_demand": len(baseline),
        "items_spiking": len(spikes),
        "items_new_demand": new_demand,
        "gross_issued_units": _f(gross_total, 4),
        "returned_to_stock_units": _f(returned_total, 4),
        "netting": "netted",
        "netting_basis": ("Demand = 'issue' moves LESS the 'receipt' moves whose reference is an "
                          "RMA number — a 4.10 restock. That reference is written by "
                          "_post_stock_move and no other writer stamps RMA- on a receipt, so the "
                          "restock is identifiable and is netted out."),
        "netting_limit": ("Netting is a floor on the correction, not a complete one: a return that "
                          "was scrapped rather than restocked, and a credit-only return where "
                          "nothing physically comes back, leave no receipt row to net. Those still "
                          "inflate the series."),
        "surge_signals": surge_signals,
        "forecast_periods": forecast_totals["periods"] or 0,
        "forecast_uplift_periods": forecast_totals["uplifts"] or 0,
        "corroboration": ("surge_signals counts 4.7's own DemandSignal rows of type 'order surge' "
                          "that are still live; forecast_uplift_periods counts plan-of-record "
                          "buckets already forecasting above the same threshold against their own "
                          "year-ago actual. Neither feeds the headline — both are there to say "
                          "whether the ledger and the plan agree."),
        "method": ("A plain rate comparison, stated on screen: the last N days' daily rate against "
                   "the whole window's daily rate. No model and no learned threshold."),
    }, rows=spikes[:MAX_DETAIL_ROWS])


def _demand_rows(tenant, scope, start, end):
    """``{item_id: {sku, name, gross, returned, net}}`` — netted demand for a window, in ONE query.

    Both halves come out of the same grouped aggregate with conditional sums, so the gross series
    and the netted one can never be measured over different populations.
    """
    moves = StockMove.objects.filter(tenant=tenant).filter(
        Q(move_type="issue")
        | Q(move_type="receipt", reference__startswith=RETURN_REFERENCE_PREFIX))
    moves = _in_moments(scope.narrow_item_rows(moves), "moved_at", start, end)
    out = {}
    for row in (moves.values("item_id", "item__sku", "item__name")
                .annotate(issued=Sum("quantity", filter=Q(move_type="issue")),
                          returned=Sum("quantity", filter=Q(move_type="receipt")))[:MAX_ITEM_ROWS]):
        # Issues are signed negative in the append-only ledger; restocks are signed positive.
        gross = -(row["issued"] or ZERO)
        returned = row["returned"] or ZERO
        if gross <= ZERO and returned <= ZERO:
            continue
        out[row["item_id"]] = {"sku": row["item__sku"], "name": row["item__name"],
                               "gross": gross, "returned": returned,
                               "net": max(gross - returned, ZERO)}
    return out


def _r_projected_stockout_count(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Replenishment rules whose projected position runs out before the next delivery can land.

    Projected available = on hand, less what is already reserved against open sales orders, plus
    what is still outstanding on receivable purchase orders. Divided by the rule's own
    ``avg_daily_demand`` that gives days of cover, and a rule stocks out when its cover is shorter
    than its ``lead_time_days``.

    FOUR queries, none of them per rule: the rules, ``ReorderRule.on_hand_map`` for every on-hand
    figure in one aggregate, the open allocations grouped by (item, location), and the outstanding
    inbound. Inbound is matched by the free-text ``sku_hint`` and lands at ITEM level because a
    purchase-order line names neither an item nor a location (:data:`SKU_HINT_CAVEAT`) — which
    makes the inbound leg optimistic for a multi-site tenant, and that is stated rather than hidden.
    """
    rules = list(scope.narrow_item_rows(
        ReorderRule.objects.filter(tenant=tenant, is_active=True)
    ).select_related("item", "location")[:MAX_ITEM_ROWS + 1])
    truncated = len(rules) > MAX_ITEM_ROWS
    rules = rules[:MAX_ITEM_ROWS]
    if not rules:
        return _unavailable("projected_stockout_count",
                            "No active reorder rule in this scope, so there is no policy to "
                            "project a stockout against.")
    on_hand = ReorderRule.on_hand_map(tenant, rules)
    item_ids = {rule.item_id for rule in rules}

    reserved = {}
    for row in (SalesOrderAllocation.objects
                .filter(tenant=tenant, status__in=("reserved", "released"),
                        sales_order_line__item_id__in=item_ids)
                .exclude(sales_order_line__sales_order__status__in=("cancelled", "closed"))
                .values("sales_order_line__item_id", "location_id")
                .annotate(qty=Sum("quantity"))[:MAX_ITEM_ROWS]):
        reserved[(row["sales_order_line__item_id"], row["location_id"])] = row["qty"] or ZERO

    skus = {rule.item.sku for rule in rules if rule.item_id}
    ordered = {row["sku_hint"]: row["qty"] or ZERO for row in
               PurchaseOrderLine.objects
               .filter(purchase_order__tenant=tenant,
                       purchase_order__status__in=PurchaseOrder.RECEIVABLE_STATUSES,
                       sku_hint__in=skus)
               .values("sku_hint").annotate(qty=Sum("quantity"))[:MAX_GROUP_ROWS]}
    received = {row["po_line__sku_hint"]: row["qty"] or ZERO for row in
                GoodsReceiptLine.objects
                .filter(goods_receipt__tenant=tenant,
                        po_line__purchase_order__status__in=PurchaseOrder.RECEIVABLE_STATUSES,
                        po_line__sku_hint__in=skus)
                .exclude(goods_receipt__status="cancelled")
                .values("po_line__sku_hint").annotate(qty=Sum("quantity_received"))[:MAX_GROUP_ROWS]}
    inbound = {sku: max(quantity - received.get(sku, ZERO), ZERO)
               for sku, quantity in ordered.items()}

    at_risk, no_demand, detail = 0, 0, []
    for rule in rules:
        daily = rule.avg_daily_demand or ZERO
        if daily <= ZERO:
            # No demand rate means no runway to measure. 4.7 writes avg_daily_demand when the rule
            # is calculated; an uncalculated rule is silent here rather than reported as safe.
            no_demand += 1
            continue
        stock = on_hand.get((rule.item_id, rule.location_id), ZERO)
        claimed = reserved.get((rule.item_id, rule.location_id), ZERO)
        incoming = inbound.get(rule.item.sku, ZERO) if rule.item_id else ZERO
        available = stock - claimed + incoming
        cover_days = available / daily
        lead = Decimal(rule.lead_time_days or 0)
        if cover_days >= lead:
            continue
        at_risk += 1
        detail.append({"sku": rule.item.sku, "name": rule.item.name,
                       "location": rule.location.code, "on_hand": _f(stock, 4),
                       "reserved": _f(claimed, 4), "inbound": _f(incoming, 4),
                       "available": _f(available, 4), "avg_daily_demand": _f(daily, 4),
                       "days_of_cover": _f(cover_days), "lead_time_days": int(lead),
                       "shortfall_days": _f(lead - cover_days),
                       "stockout_on": _iso(end + timedelta(days=int(max(cover_days, ZERO))))})
    detail.sort(key=lambda row: -(row["shortfall_days"] or 0))
    # Every rule skipped for a missing demand rate means NOTHING was measurable — report that rather
    # than a confident green "0 projected stockouts". avg_daily_demand is editable=False and written
    # only by 4.7's calculate, so a tenant that has never run it would otherwise see a reassuring
    # zero computed from zero measurable rules. Same posture the dead-stock and turnover resolvers
    # already take when their denominator is empty.
    if rules and no_demand == len(rules):
        return _unavailable(
            "projected_stockout_count",
            "No reorder rule has a demand rate yet — run 4.7's safety-stock recalculation and this "
            "becomes measurable.",
            rules_checked=len(rules), rules_without_demand_rate=no_demand)
    return _result("projected_stockout_count", Decimal(at_risk), breakdown={
        "rules_checked": len(rules),
        "rules_at_risk": at_risk,
        "rules_without_demand_rate": no_demand,
        "as_of": _iso(end),
        "formula": ("(on hand - reserved + outstanding inbound) / avg_daily_demand, compared with "
                    "the rule's lead_time_days"),
        "reserved_basis": ("open SalesOrderAllocation rows in reserved or released status, on "
                           "orders that are neither cancelled nor closed"),
        "inbound_basis": ("purchase-order quantity still outstanding on receivable orders, matched "
                          "by sku_hint"),
        "inbound_caveat": (SKU_HINT_CAVEAT + " Inbound also lands at ITEM level because a purchase "
                           "line names no location, so a multi-site tenant's cover is optimistic "
                           "at any single site."),
        "demand_source": "ReorderRule.avg_daily_demand, derived and stored by 4.7 — read, not recomputed",
        "position_note": ("This is a POSITION, not a window aggregate: it reads stock and orders as "
                          "they stand. 'end' bounds nothing here except the projected stockout date."),
        "truncated": truncated,
    }, rows=detail[:MAX_DETAIL_ROWS])


def _r_shipments_at_risk_count(tenant, start, end, scope, params=DEFAULT_PARAMS):
    """Shipments in flight that are going to be late, have gone quiet, or are already in exception.

    Three rules, ONE query (the last tracking event is a grouped ``MAX`` on the same fetch):

    * the carrier's own ETA is already past the date we promised;
    * no tracking event for more than ``parameter_days`` — silence is not good news;
    * the shipment is sitting in ``exception``, which 4.6 sets from a tracking event that said so.

    A POSITION, not a window aggregate — a shipment is at risk now or it is not — so ``end`` is the
    as-of date the silence is measured against and ``start`` is deliberately unused.
    """
    days = params.days or STALE_TRACKING_DAYS
    as_of = _moment(end or timezone.localdate(), end_of_day=True)
    qs = Shipment.objects.filter(tenant=tenant, status__in=IN_FLIGHT_SHIPMENT_STATUSES)
    qs = scope.narrow_carrier(qs, location_path=None)
    fetched = list(qs.annotate(last_event=Max("events__event_at"))
                   .values_list("id", "number", "carrier_id", "carrier__party__name", "status",
                                "planned_delivery_date", "eta", "carrier_tracking_number",
                                "destination_text", "last_event")[:MAX_SAMPLE_ROWS + 1])
    truncated = len(fetched) > MAX_SAMPLE_ROWS
    fetched = fetched[:MAX_SAMPLE_ROWS]
    if not fetched:
        return _unavailable("shipments_at_risk_count",
                            "No shipment is in flight right now — nothing is booked, in transit or "
                            "in exception.",
                            parameter_days=days, statuses=list(IN_FLIGHT_SHIPMENT_STATUSES))

    late_eta, stale, exceptions, detail = 0, 0, 0, []
    for (pk, number, carrier_id, carrier, status, planned, eta, tracking, destination,
         last_event) in fetched:
        reasons = []
        if eta is not None and planned is not None and _as_date(eta) > planned:
            reasons.append("ETA past the promised date")
            late_eta += 1
        silent_hours = _hours_between(last_event, as_of)
        silent_days = (silent_hours / Decimal("24")) if silent_hours is not None else None
        if last_event is None or (silent_days is not None and silent_days > days):
            reasons.append("no tracking event" if last_event is None
                           else f"no tracking event for {int(silent_days)} day(s)")
            stale += 1
        if status == "exception":
            reasons.append("carrier reported an exception")
            exceptions += 1
        if not reasons:
            continue
        detail.append({"shipment": number, "carrier": carrier or "(unassigned)", "status": status,
                       "destination": destination or "", "tracking": tracking or "",
                       "promised": _iso(planned), "eta": _iso(eta),
                       "last_event": _iso(last_event),
                       "days_silent": _f(silent_days) if silent_days is not None else None,
                       "days_late": (_as_date(eta) - planned).days
                       if (eta is not None and planned is not None) else None,
                       "reasons": reasons})
    detail.sort(key=lambda row: (-(len(row["reasons"])), -(row["days_late"] or 0)))
    return _result("shipments_at_risk_count", Decimal(len(detail)), breakdown={
        "parameter_days": days,
        "as_of": _iso(end),
        "in_flight": len(fetched),
        "at_risk": len(detail),
        "eta_past_promise": late_eta,
        "tracking_stale": stale,
        "in_exception": exceptions,
        "statuses": list(IN_FLIGHT_SHIPMENT_STATUSES),
        "rules": ("A shipment counts once, however many of the three rules it trips; the reasons "
                  "are listed per row and the three counts above overlap deliberately."),
        "position_note": ("This is a POSITION, not a window aggregate: a shipment is at risk now or "
                          "it is not. 'end' is the date the tracking silence is measured against."),
        "truncated": truncated,
    }, rows=detail[:MAX_DETAIL_ROWS])


# =================================================================================================
# 14. The registry
# =================================================================================================

#: metric key -> resolver. The catalog (METRIC_META) and this table are deliberately separate files:
#: the catalog is data the model layer reads, this is code the model layer must never import.
_RESOLVERS = {
    # --- inventory (9) ---
    "inv_turnover": _r_inv_turnover,
    "inv_days_on_hand": _r_inv_days_on_hand,
    "inv_dead_stock_value": _r_inv_dead_stock_value,
    "inv_aging_over_days_value": _r_inv_aging_over_days_value,
    "inv_expiry_risk_value": _r_inv_expiry_risk_value,
    "inv_excess_vs_policy_value": _r_inv_excess_vs_policy_value,
    "inv_carrying_cost": _r_inv_carrying_cost,
    "inv_stockout_count": _r_inv_stockout_count,
    "inv_abc_a_share_pct": _r_inv_abc_a_share_pct,
    # --- procurement (11) ---
    "spend_total": _r_spend_total,
    "spend_off_contract_pct": _r_spend_off_contract_pct,
    "spend_top_supplier_share_pct": _r_spend_top_supplier_share_pct,
    "spend_tail_share_pct": _r_spend_tail_share_pct,
    "savings_negotiated": _r_savings_negotiated,
    "savings_price_variance_opportunity": _r_savings_price_variance_opportunity,
    "supplier_otd_pct": _r_supplier_otd_pct,
    "supplier_reject_rate_pct": _r_supplier_reject_rate_pct,
    "supplier_score_avg": _r_supplier_score_avg,
    "procure_cycle_days": _r_procure_cycle_days,
    "procure_lead_days": _r_procure_lead_days,
    # --- logistics (7) ---
    "otd_pct": _r_otd_pct,
    "otif_pct": _r_otif_pct,
    "freight_cost_per_unit": _r_freight_cost_per_unit,
    "equipment_utilization_pct": _r_equipment_utilization_pct,
    "freight_variance_pct": _r_freight_variance_pct,
    "carrier_otd_trend": _r_carrier_otd_trend,
    "dwell_hours_avg": _r_dwell_hours_avg,
    # --- margin (5) ---
    "gross_margin_pct": _r_gross_margin_pct,
    "margin_after_cost_to_serve_pct": _r_margin_after_cost_to_serve_pct,
    "supply_cost_stack": _r_supply_cost_stack,
    "ppv_value": _r_ppv_value,
    "scrap_value": _r_scrap_value,
    # --- risk (4) ---
    "supplier_disruption_score": _r_supplier_disruption_score,
    "demand_spike_count": _r_demand_spike_count,
    "projected_stockout_count": _r_projected_stockout_count,
    "shipments_at_risk_count": _r_shipments_at_risk_count,
}

#: The catalog with a resolver attached — the single source of truth every consumer reads. Built FROM
#: ``METRIC_META`` so a metric's label, unit, direction, legal scopes and required parameters are the
#: same objects the model layer validates against; only ``resolver`` is added here.
SCM_METRICS = {
    key: dict(meta, key=key, resolver=_RESOLVERS[key])
    for key, meta in METRIC_META.items() if key in _RESOLVERS
}

# -------------------------------------------------------------------------------------------------
# COMPLETENESS CHECK — LIVE. All 36 catalogued metrics now have a resolver, so the catalog and the
# compute layer cannot diverge again: adding a METRIC_META entry without a resolver is an
# ImportError at startup rather than a KeyError on somebody's dashboard three weeks later.
#
# Deliberately a raise and not an `assert`: `assert` is stripped under `python -O`, and a silently
# missing resolver is exactly the drift this exists to make impossible.
# -------------------------------------------------------------------------------------------------
_MISSING_RESOLVERS = sorted(key for key in METRIC_META if key not in _RESOLVERS)
if _MISSING_RESOLVERS:  # pragma: no cover - a startup guard, not a runtime branch
    raise ImportError(
        "apps/scm/analytics.py has no resolver for these METRIC_META keys: "
        + ", ".join(_MISSING_RESOLVERS))

#: The reverse of the check above: a resolver keyed by something the catalog does not list would
#: never be reachable through compute_metric(), because that entry point validates against
#: METRIC_META first. Caught at import for the same reason.
_ORPHAN_RESOLVERS = sorted(key for key in _RESOLVERS if key not in METRIC_META)
if _ORPHAN_RESOLVERS:  # pragma: no cover - a startup guard, not a runtime branch
    raise ImportError(
        "apps/scm/analytics.py defines resolvers no metric catalog entry can reach: "
        + ", ".join(_ORPHAN_RESOLVERS))


# =================================================================================================
# 15. The single entry point
# =================================================================================================

def compute_metric(tenant, metric, start, end, scope=None, target=None):
    """Compute one metric. **Every 4.11 number comes through here.**

    ``scope`` accepts a :class:`MetricScope`, a ``(scope, subject)`` pair (what
    ``KpiTarget.resolved_scope()`` returns), a ``KpiTarget`` itself, a bare scope string, or ``None``
    for the whole network. When ``scope`` is omitted and ``target`` is given, the target's own
    resolved scope is used.

    ``target`` supplies the metric's knobs (``parameter_days`` / ``parameter_pct``) and its bands;
    without one the module defaults apply, so a page renders a true figure on a tenant that has never
    created a target.

    Returns the resolver's contract dict enriched with the metric's identity, the window, the
    resolved scope label and the band. An unknown key raises ``ValueError`` — the registry is closed,
    and a typo must fail loudly rather than render an empty tile.

    Three things it refuses to compute, each returning a value of ``None`` with the reason in
    ``breakdown["unavailable"]`` rather than a misleading number:

    1. **A scope whose subject was deleted.** The scope FKs are ``SET_NULL``, so removing a category
       leaves ``scope="category"`` pointing at nothing. Treating that as "no filter" would silently
       report the network-wide figure under a name that promises one category —
       ``KpiTarget.resolved_scope()``'s docstring says callers must not do that, and this is the
       caller.
    2. **A scope the metric cannot mean anything at** (a carrier scope on dead stock). ``clean()``
       already rejects it on the way in; this catches a target that predates a narrowed catalog.
    3. **A window that runs backwards.**

    It also CLAMPS the window to :data:`MIN_PERIOD_DATE`/:data:`MAX_PERIOD_DATE` before any resolver
    sees it. Doing that here rather than in each resolver is the point: an end date of
    ``9999-12-31`` overflows ``_moment``'s half-open upper bound, so without this every
    DateTimeField-windowed metric in the file is a 500 waiting for somebody to type a big year into
    a date filter.
    """
    meta = METRIC_META.get(metric)
    if meta is None:
        raise ValueError(
            f"'{metric}' is not a supply-chain metric — the 4.11 registry is closed. "
            f"Authoring a new calculation is Module 10's 10.11.")
    entry = SCM_METRICS.get(metric)
    if entry is None:
        raise ValueError(
            f"'{metric}' is in the metric catalog but this build ships no resolver for it.")

    scope = _coerce_scope(scope, target)
    params = MetricParams.for_metric(metric, target)
    start, end = clamp_date(start), clamp_date(end)

    if start is not None and end is not None and end < start:
        result = _unavailable(metric, "The window ends before it starts.")
    elif scope.value not in meta["scopes"]:
        result = _unavailable(
            metric, f"'{meta['label']}' cannot be narrowed to a {scope.value} — it is only "
                    f"computable at: {', '.join(meta['scopes'])}.")
    elif scope.value != "all" and scope.subject is None:
        result = _unavailable(
            metric, "This target narrows to a record that has since been deleted. The figure is "
                    "deliberately not widened to the whole network — that would be a different "
                    "number under the same name.")
    else:
        result = entry["resolver"](tenant, start, end, scope, params)

    result.setdefault("rows", [])
    result.setdefault("breakdown", {})
    result.update({
        "metric": metric,
        "label": meta["label"],
        "group": meta["group"],
        "unit": meta["unit"],
        "kind": meta["kind"],
        "direction": (getattr(target, "direction", "") or meta["direction"]),
        "scope": scope.value,
        "scope_label": scope.label,
        "period_start": _iso(start),
        "period_end": _iso(end),
        "parameter_days": params.days,
        "parameter_pct": _f(params.pct),
        "band": band_for(target, result.get("value")),
    })
    return result


def metrics_for_group(group):
    """``[(key, meta)]`` for one report page, in catalog order — what the five views iterate."""
    return [(key, meta) for key, meta in SCM_METRICS.items() if meta["group"] == group]


# =================================================================================================
# 16. The two writers
#
# Everything above this line READS. These two are the only functions in 4.11 that write a row, and
# they write only 4.11's own tables: a KpiSnapshot and a SupplyChainAlert. **Neither posts a
# StockMove and neither posts a JournalEntry** — 4.11 is read-only over 4.1-4.10, and
# apps.accounting owns the ledger (L29).
#
# Both take the number from :func:`compute_metric` rather than running SQL of their own. That is the
# whole design: the tile a planner reads, the CSV they export, the snapshot the trend line is drawn
# from and the alert that wakes somebody up are four renderings of ONE computation, so they cannot
# disagree about what the number is.
# =================================================================================================

#: The scope FKs a target may point at, for one ``select_related`` instead of four lazy loads per
#: target inside the capture loop.
_SCOPE_SELECT = ("scope_category", "scope_location", "scope_carrier", "scope_vendor")

#: How :func:`_impact_of` finds the money behind a breach when the metric itself is not a money
#: metric. Ordered from most specific to most general, and every key is one a resolver above
#: actually emits — an impact figure invented from a metric that has no money behind it would rank
#: the alert queue by a number nobody could act on.
# `variance` BEFORE `billed`: on a freight-variance breach the money at risk is the overage, not the
# whole freight bill. Ranking by `billed` put a large invoice with a trivial variance above a small
# one with a huge variance — the opposite of what a queue ordered by value at risk is for.
#: Every key here is one a resolver above ACTUALLY emits — checked, not assumed. `dead_share_value`
#: and `excess_value` were listed and emitted by nothing, which reads as coverage while providing
#: none: a metric whose impact key is imaginary silently ranks at zero forever.
IMPACT_KEYS = ("impact_value", "off_contract_spend", "stock_value", "variance", "billed",
               "cost_to_serve", "total_spend", "revenue", "total")

#: The window rule-based exceptions are detected over. Position-style rules (dead stock, expiry,
#: projected stockouts, shipments in flight) read as-of today whatever this says; the rules that ARE
#: window aggregates (off-contract spend, price variance, freight variance, demand spikes) use it.
DETECTION_RANGE = "last_90"


def _snapshot_payload(result):
    """The JSON blob a snapshot freezes: the component arithmetic plus enough identity to render it.

    ``KpiSnapshot.breakdown`` stores this verbatim and re-renders it months later WITHOUT
    recomputing, so it has to carry the display string and the scope label too — by then the
    supplier may have been renamed and the metric's parameters retuned, and a frozen point that
    silently adopts today's labels is the drift the table exists to prevent.

    The top-level ``value`` is deliberately NOT copied in: it is a ``Decimal`` (not JSON) and it
    already has a typed column of its own.
    """
    payload = dict(result.get("breakdown") or {})
    payload["rows"] = list(result.get("rows") or [])[:MAX_DETAIL_ROWS]
    for key in ("display", "label", "unit", "kind", "scope", "scope_label", "direction",
                "period_start", "period_end", "parameter_days", "parameter_pct"):
        payload[key] = result.get(key)
    return payload


def _dimension_of(target):
    """``(dimension_key, dimension_label)`` for a target — TYPED, so it resolves back years later.

    ``category:12`` rather than ``12``: the key is what the unique constraint de-duplicates on and
    what an alert's dedupe matching compares, and a bare integer says neither what kind of thing it
    points at nor which tenant it belongs to (L40 §3). The roll-up row is ``""``, never NULL — see
    ``KpiSnapshot``'s module docstring for why a nullable key would duplicate on every re-run.
    """
    scope_value, subject = target.resolved_scope()
    if subject is None:
        return "", ""
    return f"{scope_value}:{subject.pk}"[:64], (target.scope_label or "")[:160]


def capture_snapshots(tenant, targets=None, period_end=None, user=None):
    """Freeze one period's value for each active target. **Idempotent — a re-run updates.**

    The period is the target's OWN ``period_grain`` bucket containing ``period_end`` (so a monthly
    target snapshots January as 1-31 January), not its ``date_range``: ``date_range`` is the rolling
    window the LIVE tile reads, and rolling windows overlap, which would make a trend line of them
    meaningless. One target, one grain bucket, one point.

    ``update_or_create`` on ``(tenant, kpi_target, period_start, dimension_key)`` — the model's own
    unique key — so pressing Capture twice updates the period rather than stacking a second row, and
    ``computed_at`` is re-stamped so "this figure is three minutes old" stays true.

    Three things it refuses to write, each counted in ``skipped`` rather than guessed at:

    * a metric that came back with **no value** (``KpiSnapshot.value`` is non-null, and a
      not-computable figure stored as ``0`` would render as good news);
    * a target whose **metric is no longer in the catalog** (``compute_metric`` raises, and inventing
      a number for a metric nobody can compute is worse than a gap in the trend);
    * a target belonging to **another tenant**, when a caller passes its own list.

    **There is no per-dimension fan-out, and that is a decision.** A snapshot's ``dimension_key`` is
    the TARGET's own scope (:func:`_dimension_of`), so one target writes one row per period. The
    resolvers' ``rows`` are supporting evidence — SKUs, vendor names, lane strings — with no stable
    typed identity behind them, and minting a ``dimension_key`` out of a display label would produce
    frozen history that cannot be resolved back to a record later, which is the untyped-pointer
    failure L40 §3 is about. The component arithmetic is frozen in ``breakdown`` instead, where it
    keeps its evidence without pretending to be a dimension.
    """
    period_end = period_end or timezone.localdate()
    summary = {"targets": 0, "created": 0, "updated": 0, "skipped": 0, "available": 0,
               "capped": False, "period_end": _iso(period_end), "details": []}
    if tenant is None:
        summary["details"].append({"skipped": "No tenant — a snapshot is always tenant-scoped."})
        return summary

    tenant_pk = getattr(tenant, "pk", tenant)
    if targets is None:
        queryset = KpiTarget.objects.filter(tenant=tenant, is_active=True)
        # THE GUARD, and it is O(1) in the thing it guards: a COUNT decides whether the fan-out is
        # acceptable BEFORE a single target row — let alone a single resolver — is materialized.
        # `len(list(queryset))` would be the payload, not the guard (L40 §1).
        summary["available"] = queryset.count()
        summary["capped"] = summary["available"] > MAX_SNAPSHOT_TARGETS
        targets = list(queryset.select_related(*_SCOPE_SELECT)[:MAX_SNAPSHOT_TARGETS])
    else:
        # A caller-supplied list still has to belong to this tenant: two records joined by an action
        # must agree on more than being passed to the same function (L40 §3).
        targets = [target for target in targets if target.tenant_id == tenant_pk]
        summary["available"] = len(targets)
        summary["capped"] = len(targets) > MAX_SNAPSHOT_TARGETS
        targets = targets[:MAX_SNAPSHOT_TARGETS]

    with transaction.atomic():
        stamped = []
        for target in targets:
            summary["targets"] += 1
            start, stop = period_windows(target.period_grain, 1, end=period_end)[0]
            try:
                result = compute_metric(tenant, target.metric, start, stop,
                                        scope=target, target=target)
            except ValueError as exc:
                summary["skipped"] += 1
                summary["details"].append({"target": target.number, "name": target.name,
                                           "skipped": str(exc)})
                continue
            value = result.get("value")
            if value is None:
                summary["skipped"] += 1
                summary["details"].append({
                    "target": target.number, "name": target.name,
                    "skipped": (result.get("breakdown") or {}).get(
                        "unavailable", "The metric returned no value for this period.")})
                continue
            dimension_key, dimension_label = _dimension_of(target)
            _, created = KpiSnapshot.objects.update_or_create(
                tenant=target.tenant, kpi_target=target, period_start=start,
                dimension_key=dimension_key,
                defaults={
                    # The TARGET's own metric, never a caller-supplied one — a snapshot must not be
                    # able to wear a label its target does not measure (L40 §3b).
                    "metric": target.metric,
                    "period_end": stop,
                    "dimension_label": dimension_label,
                    # q4() clamps as well as quantizes: an over-range Decimal is a DataError, and
                    # this is the writer the model's comment says must pass through it.
                    "value": q4(value),
                    "target_value_at_time": target.target_value,
                    "status_band": result.get("band") or "unknown",
                    "breakdown": _snapshot_payload(result),
                    "computed_at": timezone.now(),
                    "computed_by": user if getattr(user, "pk", None) else None,
                })
            summary["created" if created else "updated"] += 1
            summary["details"].append({"target": target.number, "name": target.name,
                                       "metric": target.metric, "period_start": _iso(start),
                                       "period_end": _iso(stop), "value": result.get("display"),
                                       "band": result.get("band"), "created": created})
            target.last_evaluated_at = timezone.now()
            stamped.append(target)
        if stamped:
            KpiTarget.objects.bulk_update(stamped, ["last_evaluated_at"])
    return summary


def _impact_of(result, meta):
    """The money a breach is worth, for ranking the queue and for the alert-fatigue floor.

    A money metric IS its own impact. Everything else looks for a figure the resolver already put in
    its breakdown (:data:`IMPACT_KEYS`) — the off-contract spend behind an off-contract percentage,
    the freight overage behind a variance percentage.

    **Returns ``None``, not ``ZERO``, when the metric has no money behind it at all**, and the two
    mean different things. Most of the catalog — ``otd_pct``, ``otif_pct``, ``inv_turnover``,
    ``supplier_otd_pct``, ``supplier_disruption_score``, ``projected_stockout_count`` and others —
    emits no ``IMPACT_KEYS`` figure, so collapsing "unmeasurable" into "zero" made
    ``impact < min_impact_value`` true forever: any operator who set a floor on one of those targets
    silently stopped receiving its alerts. That is the same never-fires conjunction
    ``KpiTarget.clean()`` rejects for a missing threshold, arrived at from the other direction.
    Callers rank with ``impact or ZERO`` and apply the floor only when the figure is real, so an
    unmeasurable impact fails OPEN (the alert fires) rather than closed.
    """
    value = result.get("value")
    if meta.get("unit") == "money" and value is not None:
        return abs(Decimal(value))
    breakdown = result.get("breakdown") or {}
    for key in IMPACT_KEYS:
        candidate = breakdown.get(key)
        # `isinstance(True, int)` is True, so booleans are excluded explicitly — `mixed_currency`
        # and `truncated` are not amounts.
        if isinstance(candidate, bool) or not isinstance(candidate, (int, float)):
            continue
        if candidate:
            return abs(Decimal(str(candidate)))
    return None


def _candidate(alert_type, dedupe_key, title, *, severity="warning", metric="", target=None,
               observed=None, threshold=None, impact=ZERO, dimension_key="", dimension_label="",
               detail=None, **subjects):
    """One alert the detector wants to exist, as plain data — nothing is written until the end.

    Building every candidate first is what lets the whole open set be resolved in ONE query by
    ``dedupe_key``; resolving per candidate would be a SELECT per exception, which is exactly the
    N+1 the ``(tenant, dedupe_key)`` index exists to avoid.

    ``**subjects`` are the six typed FKs, passed as **primary keys** (``item=14``, ``party=3``) and
    written straight to the ``_id`` attribute. Every one comes out of a tenant-filtered query above,
    which is what makes them safe to set without re-fetching the row — and passing the id rather
    than a throwaway model instance keeps this loop free of objects nobody reads.
    """
    return {
        "alert_type": alert_type,
        "dedupe_key": (dedupe_key or "")[:120],
        "title": (title or "")[:200],
        "severity": severity,
        "metric": metric,
        "kpi_target": target,
        "observed_value": q4(observed) if observed is not None else None,
        "threshold_value": q4(threshold) if threshold is not None else None,
        "impact_value": q2(impact or ZERO),
        "dimension_key": (dimension_key or "")[:64],
        "dimension_label": (dimension_label or "")[:160],
        "detail": detail or {},
        "subjects": {name: value for name, value in subjects.items() if value is not None},
    }


def _lookup_ids(model_qs, field, values, limit=MAX_ALERTS_PER_TYPE * 2):
    """``{business key: pk}`` in ONE query, for turning a resolver's display rows into typed FKs.

    The resolvers return SKUs, shipment numbers and location codes because that is what a page
    prints. An alert needs the real row, so the keys are resolved back here rather than stored as
    text: a bare label carries neither a tenant nor a type, and an alert pointing at "WIDGET-1" is
    an alert nobody can click through (L40 §3).
    """
    values = [value for value in values if value]
    if not values:
        return {}
    return {row[field]: row["id"] for row in
            model_qs.filter(**{f"{field}__in": values}).values(field, "id")[:limit]}


def detect_alerts(tenant, user=None):
    """Raise, re-fire and rank the exception queue. **The ONLY writer of ``SupplyChainAlert``.**

    Two halves, and both go through :func:`compute_metric` so an alert can never quote a number the
    page it links to disagrees with:

    1. **KPI breaches.** Every active, alerting target is computed and banded with :func:`band_for`
       — the same function ``KpiSnapshot.status_band`` uses, which is what makes it impossible for a
       tile to read green while its own alert fires. A target's ``min_impact_value`` is the
       alert-fatigue floor: a breach worth less than it raises nothing, and the count is returned so
       the caller can say so out loud rather than leaving an operator wondering.
    2. **Rule-based exceptions** that legitimately have no target behind them — dead stock, expiring
       lots, projected stockouts, demand spikes, shipments at risk and gone quiet, risky suppliers,
       expiring contracts, off-contract spend, price variance and freight variance. Each is capped
       at :data:`MAX_ALERTS_PER_TYPE` on an ORDERED query, so the biggest exception of each kind
       survives and the tail is dropped: a queue that raises four thousand rows is a queue nobody
       opens twice.

    **De-duplication is this function, not a constraint** (see ``SupplyChainAlert``'s module
    docstring: a unique_together would permanently block the next genuine breach, and MariaDB has no
    partial indexes so a conditional constraint would silently protect nothing). Inside one
    ``transaction.atomic()`` the whole open set is fetched by ``dedupe_key`` in ONE query, and a
    repeat breach **updates** the row that is already open — moving ``last_seen_at`` so it reads
    "still breaching" — instead of creating a second one. A resolved alert is deliberately NOT
    matched, so a problem that comes back raises a fresh row.

    **Cost: this is a BATCH action, not a page load.** It computes every alerting target plus ten
    rule-based passes, so it runs on the order of a hundred queries on a seeded tenant and grows
    with the number of alerting targets. That is why the plan puts it behind a
    ``@tenant_admin_required`` POST and a management command rather than on a dashboard — do not
    call it from a GET.
    """
    summary = {"created": 0, "updated": 0, "skipped": 0, "targets": 0, "breaches": 0,
               "below_impact": 0, "exceptions": 0, "by_type": {}}
    if tenant is None:
        return summary
    start, end = range_bounds(DETECTION_RANGE)
    candidates = []

    # ---- 1. KPI breaches -----------------------------------------------------------------------
    targets = list(KpiTarget.objects
                   .filter(tenant=tenant, is_active=True, is_alerting=True)
                   .select_related(*_SCOPE_SELECT)[:MAX_SNAPSHOT_TARGETS])
    for target in targets:
        summary["targets"] += 1
        window_start, window_end = range_bounds(target.date_range)
        try:
            result = compute_metric(tenant, target.metric, window_start, window_end,
                                    scope=target, target=target)
        except ValueError:
            summary["skipped"] += 1
            continue
        band = result.get("band")
        if band not in ("warning", "critical"):
            continue
        meta = METRIC_META.get(target.metric) or {}
        impact = _impact_of(result, meta)
        floor = target.min_impact_value or ZERO
        # `impact is not None` matters: a metric with no money behind it (most of the catalog) is
        # UNMEASURABLE, not worth zero, and suppressing it against a floor would mute the target
        # permanently. An unmeasurable impact fails OPEN — see _impact_of.
        if floor > ZERO and impact is not None and impact < floor:
            # The alert-fatigue floor the operator set. Counted and RETURNED rather than silently
            # dropped, so the POST action can say "3 breaches were below their impact floor" — a
            # suppression nobody can see is how a floor becomes a blindfold.
            summary["below_impact"] += 1
            continue
        summary["breaches"] += 1
        dimension_key, dimension_label = _dimension_of(target)
        # band=="critical" means the critical threshold was crossed, so it is not None; likewise for
        # warning. band_for() cannot return either without the matching threshold being set.
        threshold = (target.critical_threshold if band == "critical" else target.warning_threshold)
        # A category-scoped target's subject is an ItemCategory, and the alert has no category FK —
        # the three that DO line up are set, and the scope is carried in dimension_key regardless.
        _, subject = target.resolved_scope()
        subject_pk = getattr(subject, "pk", None)
        candidates.append(_candidate(
            "kpi_breach",
            f"kpi_breach:{dimension_key or 'network'}:{target.pk}",
            f"{target.name} is {result.get('display')} ({band})",
            severity="critical" if band == "critical" else target.severity,
            metric=target.metric, target=target,
            # `impact or ZERO`: SupplyChainAlert.impact_value is a non-null column and the queue is
            # ordered by it, so an unmeasurable impact sorts to the bottom rather than erroring.
            observed=result.get("value"), threshold=threshold, impact=impact or ZERO,
            dimension_key=dimension_key,
            dimension_label=dimension_label or target.scope_label,
            detail={"band": band, "display": result.get("display"),
                    "target_value": _f(target.target_value),
                    "warning_threshold": _f(target.warning_threshold),
                    "critical_threshold": _f(target.critical_threshold),
                    "direction": result.get("direction"),
                    "period_start": result.get("period_start"),
                    "period_end": result.get("period_end"),
                    "breakdown": _snapshot_payload(result)},
            location=subject_pk if target.scope == "location" else None,
            carrier=subject_pk if target.scope == "carrier" else None,
            party=subject_pk if target.scope == "vendor" else None))

    # ---- 2. Rule-based exceptions ---------------------------------------------------------------
    exceptions = (_detect_dead_stock(tenant, start, end)
                  + _detect_expiry_risk(tenant, start, end)
                  + _detect_stockout_risk(tenant, start, end)
                  + _detect_demand_spikes(tenant, start, end)
                  + _detect_shipment_risk(tenant, start, end)
                  + _detect_supplier_risk(tenant, start, end)
                  + _detect_contract_expiry(tenant, start, end)
                  + _detect_off_contract_spend(tenant, start, end)
                  + _detect_price_variance(tenant, start, end)
                  + _detect_freight_variance(tenant, start, end))
    summary["exceptions"] = len(exceptions)
    candidates.extend(exceptions)

    # ---- 3. One query for the open set, then update-or-create ------------------------------------
    with transaction.atomic():
        keys = [candidate["dedupe_key"] for candidate in candidates if candidate["dedupe_key"]]
        open_rows = {}
        if keys:
            # select_for_update(), not a bare read. transaction.atomic() bounds the write but grants
            # no mutual exclusion, and de-dupe here is deliberately NOT backed by a unique constraint
            # (MariaDB has no partial indexes, so a conditional one is silently dropped). Without the
            # lock, two concurrent runs — two admins pressing Run detection, or one double-submit —
            # both read an empty open set and both create, producing exactly the duplicate this
            # whole block exists to prevent. SupplyChainAlerts.py:464 already takes this lock for a
            # strictly weaker reason.
            for alert in (SupplyChainAlert.objects
                          .select_for_update()
                          .filter(tenant=tenant, status__in=OPEN_ALERT_STATUSES,
                                  dedupe_key__in=keys)):
                open_rows.setdefault(alert.dedupe_key, alert)
        now = timezone.now()
        for candidate in candidates:
            bucket = summary["by_type"].setdefault(candidate["alert_type"],
                                                   {"created": 0, "updated": 0})
            existing = open_rows.get(candidate["dedupe_key"])
            if existing is not None:
                existing.observed_value = candidate["observed_value"]
                existing.threshold_value = candidate["threshold_value"]
                existing.impact_value = candidate["impact_value"]
                existing.severity = candidate["severity"]
                existing.title = candidate["title"]
                existing.dimension_label = candidate["dimension_label"]
                existing.detail = candidate["detail"]
                existing.last_seen_at = now
                existing.save(update_fields=["observed_value", "threshold_value", "impact_value",
                                             "severity", "title", "dimension_label", "detail",
                                             "last_seen_at", "updated_at"])
                summary["updated"] += 1
                bucket["updated"] += 1
                continue
            alert = SupplyChainAlert(
                tenant=tenant, alert_type=candidate["alert_type"], metric=candidate["metric"],
                kpi_target=candidate["kpi_target"], title=candidate["title"],
                severity=candidate["severity"], observed_value=candidate["observed_value"],
                threshold_value=candidate["threshold_value"],
                impact_value=candidate["impact_value"], dimension_key=candidate["dimension_key"],
                dimension_label=candidate["dimension_label"], detail=candidate["detail"],
                dedupe_key=candidate["dedupe_key"], raised_at=now, last_seen_at=now)
            for name, value in candidate["subjects"].items():
                setattr(alert, f"{name}_id", value)
            # save(), not bulk_create: TenantNumbered.save() is what mints ALR-00001, and a queue of
            # alerts with blank numbers is a queue nobody can quote in an email.
            alert.save()
            open_rows[candidate["dedupe_key"]] = alert
            summary["created"] += 1
            bucket["created"] += 1
    return summary


# -------------------------------------------------------------------------------------------------
# The rule-based detectors.
#
# Each returns a list of candidates and each is bounded at MAX_ALERTS_PER_TYPE on an ORDERED source,
# so what survives the cap is the biggest exception of its kind rather than an arbitrary slice.
# Where a metric already exists for the exception, the detector calls compute_metric and reads its
# rows — so the alert and the tile are literally the same computation, which is the reason this
# whole module exists.
# -------------------------------------------------------------------------------------------------

def _rows_of(tenant, metric, start, end):
    """``(rows, result)`` from a catalogued metric, or ``([], None)`` when it is not computable.

    No ``target`` is passed: a rule-based exception has none by definition, so the metric's knobs
    come from :data:`METRIC_PARAM_DEFAULTS` — the same documented defaults the page renders with
    when no target exists.
    """
    try:
        result = compute_metric(tenant, metric, start, end, scope=NETWORK)
    except ValueError:
        return [], None
    if result.get("value") is None:
        return [], result
    return list(result.get("rows") or []), result


def _detect_dead_stock(tenant, start, end):
    """Stock on hand that has not moved for the module's default dead-stock window."""
    rows, result = _rows_of(tenant, "inv_dead_stock_value", None, end)
    if not rows:
        return []
    rows = sorted(rows, key=lambda row: -(row.get("value") or 0))[:MAX_ALERTS_PER_TYPE]
    items = _lookup_ids(Item.objects.filter(tenant=tenant), "sku",
                        [row.get("sku") for row in rows])
    days = (result.get("breakdown") or {}).get("parameter_days", DEAD_STOCK_DAYS)
    out = []
    for row in rows:
        item_id = items.get(row.get("sku"))
        out.append(_candidate(
            "dead_stock", f"dead_stock:item:{item_id or row.get('sku')}",
            f"{row.get('sku')} has not moved for {days} days ({row.get('value')} held)",
            severity="warning", metric="inv_dead_stock_value",
            observed=row.get("value"), impact=row.get("value") or ZERO,
            dimension_key=f"item:{item_id}" if item_id else "",
            dimension_label=f"{row.get('sku')} · {row.get('name') or ''}".strip(" ·"),
            detail=dict(row, parameter_days=days),
            item=item_id))
    return out


def _detect_expiry_risk(tenant, start, end):
    """Lots inside the expiry horizon, worst first — already-expired stock ranks as critical."""
    rows, result = _rows_of(tenant, "inv_expiry_risk_value", None, end)
    if not rows:
        return []
    rows = sorted(rows, key=lambda row: (row.get("days_left") if row.get("days_left") is not None
                                         else 9999))[:MAX_ALERTS_PER_TYPE]
    items = _lookup_ids(Item.objects.filter(tenant=tenant), "sku",
                        [row.get("sku") for row in rows])
    days = (result.get("breakdown") or {}).get("parameter_days", EXPIRY_DAYS)
    out = []
    for row in rows:
        item_id = items.get(row.get("sku"))
        expired = bool(row.get("expired"))
        out.append(_candidate(
            "expiry_risk", f"expiry_risk:lot:{row.get('lot')}",
            (f"Lot {row.get('lot')} ({row.get('sku')}) "
             + ("has already expired" if expired
                else f"expires in {row.get('days_left')} day(s)")),
            severity="critical" if expired else "warning", metric="inv_expiry_risk_value",
            observed=row.get("value"), threshold=days, impact=row.get("value") or ZERO,
            dimension_key=f"lot:{row.get('lot')}",
            dimension_label=f"Lot {row.get('lot')} · {row.get('sku')}",
            detail=dict(row, parameter_days=days),
            item=item_id))
    return out


def _detect_stockout_risk(tenant, start, end):
    """Replenishment rules projected to run dry before their own lead time is up."""
    rows, _ = _rows_of(tenant, "projected_stockout_count", None, end)
    if not rows:
        return []
    rows = sorted(rows, key=lambda row: -(row.get("shortfall_days") or 0))[:MAX_ALERTS_PER_TYPE]
    items = _lookup_ids(Item.objects.filter(tenant=tenant), "sku",
                        [row.get("sku") for row in rows])
    return [_candidate(
        "stockout_risk",
        f"stockout_risk:item:{items.get(row.get('sku')) or row.get('sku')}:{row.get('location')}",
        (f"{row.get('sku')} at {row.get('location')} has {row.get('days_of_cover')} days of cover "
         f"against a {row.get('lead_time_days')}-day lead time"),
        severity="critical" if (row.get("available") or 0) <= 0 else "warning",
        metric="projected_stockout_count",
        observed=row.get("days_of_cover"), threshold=row.get("lead_time_days"),
        dimension_key=f"item:{items.get(row.get('sku'))}:{row.get('location')}",
        dimension_label=f"{row.get('sku')} @ {row.get('location')}",
        detail=row,
        item=items.get(row.get("sku")))
        for row in rows]


def _detect_demand_spikes(tenant, start, end):
    """Items whose recent demand rate has jumped clear of their own baseline."""
    rows, result = _rows_of(tenant, "demand_spike_count", start, end)
    if not rows:
        return []
    rows = sorted(rows, key=lambda row: -(row.get("increase_pct") or 0))[:MAX_ALERTS_PER_TYPE]
    items = _lookup_ids(Item.objects.filter(tenant=tenant), "sku",
                        [row.get("sku") for row in rows])
    pct = (result.get("breakdown") or {}).get("parameter_pct", _f(SPIKE_PCT))
    return [_candidate(
        "demand_spike", f"demand_spike:item:{items.get(row.get('sku')) or row.get('sku')}",
        f"{row.get('sku')} demand is up {row.get('increase_pct')}% on its own baseline",
        severity="warning", metric="demand_spike_count",
        observed=row.get("increase_pct"), threshold=pct,
        dimension_key=f"item:{items.get(row.get('sku'))}",
        dimension_label=f"{row.get('sku')} · {row.get('name') or ''}".strip(" ·"),
        detail=row,
        item=items.get(row.get("sku")))
        for row in rows]


def _detect_shipment_risk(tenant, start, end):
    """Shipments in flight that are late, in exception, or have gone quiet.

    Two types out of one query, because they are two different conversations: a shipment that is
    going to MISS ITS DATE is a chase with the carrier, and a shipment that has merely gone quiet is
    a chase for VISIBILITY. So a row is filed under ``stale_tracking`` only when silence is the ONLY
    thing wrong with it; the moment it is also late or in exception it becomes ``shipment_at_risk``,
    because the delivery problem is the one somebody has to act on and it must not be buried under a
    tracking-integration complaint. One row, one alert, filed by its worst symptom.
    """
    rows, result = _rows_of(tenant, "shipments_at_risk_count", None, end)
    if not rows:
        return []
    numbers = _lookup_ids(Shipment.objects.filter(tenant=tenant), "number",
                          [row.get("shipment") for row in rows])
    days = (result.get("breakdown") or {}).get("parameter_days", STALE_TRACKING_DAYS)
    stale, at_risk = [], []
    for row in rows:
        reasons = row.get("reasons") or []
        silent_only = bool(reasons) and all("tracking" in reason for reason in reasons)
        (stale if silent_only else at_risk).append(row)
    out = []
    for alert_type, group, headline in (
            ("stale_tracking", stale[:MAX_ALERTS_PER_TYPE],
             "has sent no tracking update"),
            ("shipment_at_risk", at_risk[:MAX_ALERTS_PER_TYPE],
             "is at risk of missing its promised date")):
        for row in group:
            shipment_id = numbers.get(row.get("shipment"))
            out.append(_candidate(
                alert_type, f"{alert_type}:shipment:{shipment_id or row.get('shipment')}",
                f"{row.get('shipment')} ({row.get('carrier')}) {headline}",
                severity="critical" if (row.get("days_late") or 0) > 0 else "warning",
                metric="shipments_at_risk_count",
                observed=row.get("days_silent") if alert_type == "stale_tracking"
                else row.get("days_late"),
                threshold=days if alert_type == "stale_tracking" else None,
                dimension_key=f"shipment:{shipment_id}" if shipment_id else "",
                dimension_label=f"{row.get('shipment')} -> {row.get('destination') or ''}".strip(),
                detail=dict(row, parameter_days=days),
                shipment=shipment_id))
    return out


def _detect_supplier_risk(tenant, start, end):
    """Suppliers 4.2's OWN risk register already rates high or critical.

    Reads ``SupplierRiskAssessment`` directly rather than the composite: 4.2 owns the register, a
    high rating there is already a reviewed human judgement, and raising a queue item off it is
    surfacing 4.2's conclusion rather than second-guessing it with a rival score.
    """
    latest = _latest_risk_indices(tenant)
    ranked = sorted((row for row in latest.values() if row["risk_level"] in ("high", "critical")),
                    key=lambda row: -(row["risk_index"] or ZERO))[:MAX_ALERTS_PER_TYPE]
    return [_candidate(
        "supplier_risk", f"supplier_risk:vendor:{row['party_id']}",
        f"{row['party__name']} is rated {row['risk_level']} risk ({row['number']})",
        severity="critical" if row["risk_level"] == "critical" else "warning",
        metric="supplier_disruption_score",
        observed=row["risk_index"], threshold=Decimal("3"),
        dimension_key=f"vendor:{row['party_id']}", dimension_label=row["party__name"] or "",
        detail={"assessment": row["number"], "risk_index": _f(row["risk_index"]),
                "risk_level": row["risk_level"],
                "assessed_on": _iso(row["assessment_date"]),
                "source": "SupplierRiskAssessment (4.2) — read, not recomputed"},
        party=row["party_id"])
        for row in ranked]


def _detect_contract_expiry(tenant, start, end):
    """Supplier contracts running out inside the module's continuity horizon."""
    today = end or timezone.localdate()
    horizon = today + timedelta(days=CONTRACT_EXPIRY_DAYS)
    rows = list(SupplierContract.objects
                .filter(tenant=tenant, status__in=COVERING_CONTRACT_STATUSES,
                        end_date__isnull=False, end_date__gte=today, end_date__lte=horizon)
                .values("id", "number", "title", "party_id", "party__name", "end_date",
                        "contract_value", "auto_renew", "renewal_notice_days")
                .order_by("end_date")[:MAX_ALERTS_PER_TYPE])
    return [_candidate(
        "contract_expiry", f"contract_expiry:contract:{row['id']}",
        (f"{row['number']} with {row['party__name']} ends "
         f"{row['end_date'].isoformat()} ({(row['end_date'] - today).days} days)"),
        severity="critical" if (row["end_date"] - today).days <= 14 and not row["auto_renew"]
        else "warning",
        observed=(row["end_date"] - today).days, threshold=CONTRACT_EXPIRY_DAYS,
        impact=row["contract_value"] or ZERO,
        dimension_key=f"contract:{row['id']}",
        dimension_label=f"{row['number']} · {row['party__name'] or ''}".strip(" ·"),
        detail={"contract": row["number"], "title": row["title"],
                "supplier": row["party__name"], "ends": _iso(row["end_date"]),
                "days_to_expiry": (row["end_date"] - today).days,
                "contract_value": _f(row["contract_value"]),
                "auto_renew": row["auto_renew"],
                "renewal_notice_days": row["renewal_notice_days"]},
        party=row["party_id"])
        for row in rows]


def _detect_off_contract_spend(tenant, start, end):
    """Suppliers bought from in the window with no live contract covering the order.

    TWO queries — the spend league and the covering contracts — never one per vendor. The caveat the
    metric carries applies here too: cover is vendor-level, because 4.2 has no contract-to-item
    linkage to check a line against.
    """
    orders = _in_dates(PurchaseOrder.objects.filter(tenant=tenant, status__in=SPEND_PO_STATUSES),
                       "order_date", start, end)
    league = list(orders.values("vendor_id", "vendor__name")
                  .annotate(spend=Sum("total"), orders=Count("id"))
                  .order_by("-spend")[:MAX_GROUP_ROWS])
    if not league:
        return []
    covered, _, _ = _contract_cover(tenant, [row["vendor_id"] for row in league],
                                    end or timezone.localdate(), CONTRACT_EXPIRY_DAYS)
    uncovered = [row for row in league if row["vendor_id"] not in covered][:MAX_ALERTS_PER_TYPE]
    return [_candidate(
        "off_contract_spend", f"off_contract_spend:vendor:{row['vendor_id']}",
        (f"{row['vendor__name']}: {_money(row['spend'])} across {row['orders']} order(s) with no "
         f"live contract"),
        severity="warning", metric="spend_off_contract_pct",
        observed=row["spend"], impact=row["spend"] or ZERO,
        dimension_key=f"vendor:{row['vendor_id']}", dimension_label=row["vendor__name"] or "",
        detail={"supplier": row["vendor__name"], "spend": _f(row["spend"]),
                "orders": row["orders"], "window_start": _iso(start), "window_end": _iso(end),
                "caveat": ("Cover is vendor-level and date-based: 4.2 has no contract-to-item "
                           "linkage, so this says the supplier has no live agreement at all.")},
        party=row["vendor_id"])
        for row in uncovered]


def _detect_price_variance(tenant, start, end):
    """SKUs bought at materially different prices in the same window."""
    rows, _ = _rows_of(tenant, "savings_price_variance_opportunity", start, end)
    if not rows:
        return []
    rows = sorted(rows, key=lambda row: -(row.get("opportunity") or 0))[:MAX_ALERTS_PER_TYPE]
    items = _lookup_ids(Item.objects.filter(tenant=tenant), "sku",
                        [row.get("sku_hint") for row in rows])
    return [_candidate(
        "price_variance", f"price_variance:sku:{row.get('sku_hint')}",
        (f"{row.get('sku_hint')} bought at more than one price — {_money(row.get('opportunity'))} "
         f"between the best price and what was paid"),
        severity="warning", metric="savings_price_variance_opportunity",
        observed=row.get("opportunity"), impact=row.get("opportunity") or ZERO,
        dimension_key=f"sku:{row.get('sku_hint')}", dimension_label=row.get("sku_hint") or "",
        detail=dict(row, caveat=SKU_HINT_CAVEAT),
        item=items.get(row.get("sku_hint")))
        for row in rows]


def _detect_freight_variance(tenant, start, end):
    """Carrier bills 4.6's audit found to be over the rate card, biggest first."""
    rows = list(_audited_freight(tenant, NETWORK, start, end)
                .filter(match_status__in=("price_variance", "disputed"),
                        variance_amount__gt=ZERO)
                .values("id", "number", "carrier_id", "carrier__party__name", "shipment_id",
                        "billed_amount", "contract_amount", "variance_amount", "variance_pct",
                        "match_status", "invoice_date")
                .order_by("-variance_amount")[:MAX_ALERTS_PER_TYPE])
    return [_candidate(
        "freight_variance", f"freight_variance:invoice:{row['id']}",
        (f"{row['number']} from {row['carrier__party__name']} is "
         f"{_money(row['variance_amount'])} over the rate card"),
        severity="critical" if row["match_status"] == "disputed" else "warning",
        metric="freight_variance_pct",
        observed=row["variance_amount"], threshold=row["contract_amount"],
        impact=row["variance_amount"] or ZERO,
        dimension_key=f"carrier:{row['carrier_id']}",
        dimension_label=f"{row['number']} · {row['carrier__party__name'] or ''}".strip(" ·"),
        detail={"invoice": row["number"], "carrier": row["carrier__party__name"],
                "billed": _f(row["billed_amount"]), "contracted": _f(row["contract_amount"]),
                "variance": _f(row["variance_amount"]), "variance_pct": _f(row["variance_pct"]),
                "match_status": row["match_status"], "invoice_date": _iso(row["invoice_date"])},
        carrier=row["carrier_id"], shipment=row["shipment_id"])
        for row in rows]
