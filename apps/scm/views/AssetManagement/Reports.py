"""SCM 4.13 Asset Management — three COMPUTED report pages. No new table, no new column.

Everything here is derived from rows that already exist, the ``valuation_report`` /
``reorder_alerts`` / ``carbon_footprint_report`` precedent:

* :func:`pm_forecast` — the preventive-maintenance board, over ``MaintenancePlan`` and its due
  arithmetic, with the open-jobs queue folded in so dispatch does not need a sixth destination.
* :func:`sparepart_list` — the MRO storeroom, over ``Item(is_spare_part=True)`` and **4.3's
  append-only ``StockMove`` ledger**. There is no second parts catalogue and no stored on-hand.
* :func:`asset_depreciation_report` — repair-vs-replace, over figures **READ** from the linked
  ``accounting.FixedAsset``.

TWO STANDING RULES THIS MODULE IS BUILT AROUND.

**1. Coverage, not a confident zero** (the 4.11 ``projected_stockout_count`` lesson, restated by
4.12's carbon report). An asset with no capitalised record CANNOT be given a repair-vs-replace
ratio, and one whose book value is nil cannot be divided by. Those rows are COUNTED and reported as
excluded rather than folded in as zero — a green 0 % that actually means "we had no data" is worse
than a blank, because a blank makes somebody go and look. Both reports render 200 on an EMPTY tenant
with an honest zero-coverage line and ``None`` totals; neither may 500 on a first run.

**2. SCM reads these figures, it does not own them** (L29). Acquisition cost, salvage value, useful
life, method and accumulated depreciation all belong to ``apps.accounting``, and the depreciation
JOURNAL is posted there. 4.13 stores none of them, recomputes none of them and posts no
``JournalEntry``. Two writers of one accumulated figure is precisely how the two numbers on the two
pages come to disagree.

QUERY HYGIENE. Nothing below calls a per-row method that queries. ``Item.on_hand()``,
``Asset.maintenance_cost_to_date()`` and ``MaintenancePlan.latest_reading()`` are all correct and
all fire their own queries, so each is replaced here by ONE grouped aggregate (or, for the plan's
meter, by a scalar subquery whose result is used to PRIME the model's own cache, so the method still
answers and simply never queries). ``Exists()``, not ``Count()``, wherever a template only asks
"are there any?".
"""
import datetime

from django.db.models.functions import Coalesce

from apps.scm.views._common import *  # noqa: F401,F403

# The quantizers live in the MODELS toolkit — views/_common.py deliberately does not re-export them.
# Same import shape the 4.12 carbon report uses (ContractCompliance/Reports.py:53). q2/q4 CLAMP as
# well as quantize, so one poisoned labour rate degrades its own row instead of raising inside a
# report that is rendering a hundred of them.
from apps.scm.models._base import ZERO, q2, q4
from apps.scm.models import (
    Asset,
    CRITICALITY_CHOICES,
    Item,
    ItemCategory,
    Location,
    MaintenancePlan,
    MaintenanceWorkOrder,
    MaintenanceWorkOrderPart,
    MeterReading,
    PRIORITY_CHOICES,
    ReorderRule,
    StockMove,
)
from apps.scm import analytics

#: Wide output fields for the multiplied sums below. A ``quantity × unit_cost`` over a whole
#: workspace routinely exceeds the 14-digit shape of either operand, and Django uses the FIRST
#: operand's field to size the expression unless it is told otherwise — which is a ``DataError`` on
#: a report, from data that is individually perfectly valid.
_MONEY = models.DecimalField(max_digits=24, decimal_places=4)
_QTY = models.DecimalField(max_digits=20, decimal_places=4)


# =============================================================================================
# 4.13 report 1 — the PM forecast board
# =============================================================================================
#: The default horizon. Four weeks is the window a planner actually schedules against; the page
#: exposes it as ``?days=`` with a set of presets rather than a free-text box nobody can guess.
DEFAULT_FORECAST_DAYS = 30
MIN_FORECAST_DAYS = 1
#: One year. The ceiling is not decoration: the horizon is fed to ``timedelta(days=…)`` and then to
#: a date comparison, and an unbounded value out of the query string is an ``OverflowError`` — a
#: 500, from a URL anybody can type (the 4.10 finding).
MAX_FORECAST_DAYS = 365
#: Presets the template renders as the horizon dropdown. Passed from the view because a filter
#: control with no context is the recurring bug the house rule exists to stop.
FORECAST_DAY_OPTIONS = [7, 14, 30, 60, 90, 180, 365]

#: How many open jobs the dispatch board renders. The cap is a queryset SLICE so the DATABASE
#: applies it (L40 §1: a guard that first builds the whole thing is the payload, not a guard). The
#: per-status counts beside it are a separate grouped query over the WHOLE queue, so the page can
#: say it is showing a window without pretending the window is the total.
MAX_BOARD_ROWS = 100


def _horizon(request):
    """``(days, raw, invalid)`` — ``?days=N`` clamped to 1..365, junk falling back to the default.

    Three different bad inputs, one posture: ``?days=abc``, ``?days=-5`` and ``?days=²`` are all
    refused by ``as_db_int`` (``isdecimal()`` is precisely ``int()``'s accepted set, and a minus
    sign is not in it), ``?days=99999999999999999999`` is refused as over-range, and an in-range but
    absurd ``?days=100000`` is clamped. Nothing raises. ``invalid`` is returned so the page can say
    "showing the default window" instead of silently ignoring what somebody asked for.
    """
    raw = (request.GET.get("days") or "").strip()
    if not raw:
        return DEFAULT_FORECAST_DAYS, "", False
    number = as_db_int(raw)
    if number is None:
        return DEFAULT_FORECAST_DAYS, raw, True
    clamped = min(max(number, MIN_FORECAST_DAYS), MAX_FORECAST_DAYS)
    return clamped, raw, clamped != number


def _newest_reading_case(tenant):
    """The pk of the asset's latest reading, as a scalar expression to annotate onto a plan row.

    Paired with the priming loop in :func:`pm_forecast`, this is how a board of plans answers the
    meter and condition axes without a query per row.

    ``MaintenancePlan.due_status()`` consults the meter and condition axes, both of which read
    ``latest_reading()``. That method is correct and it queries — so evaluating a board of plans
    would fire one ``MeterReading`` SELECT per plan, which is the N+1 the module's query-hygiene
    rule forbids outright.

    The fix is not to re-derive "what does this meter say now" here (two implementations of that
    question drift the first time either learns about a second meter — the model says so in as many
    words). It is to resolve the row ids with a scalar subquery on the plan queryset and then set
    ``_latest_reading_cache``, the attribute ``latest_reading()`` already checks. The MODEL still
    answers the question; it simply never has to ask the database.

    The ``Case`` mirrors ``Asset.latest_reading()`` exactly, including the rule that matters most: an
    asset with a NAMED primary meter does **not** fall back to readings logged under another name
    (an odometer value handed to a plan whose interval is in running hours would schedule a service
    roughly never, silently). Only an asset with no primary meter named takes the newest row of any
    meter.

    The cache is set on EVERY plan, including to ``None``. Leaving it unset on the plans with no
    reading would put the per-row query straight back for exactly the rows most likely to have one.

    **``tenant`` narrows nothing and is stated anyway.** The plans are already this workspace's and
    an asset's readings are its own tenant's, so the predicate cannot change a single row. What it
    does is make ``scm_mtr_tnt_asset_idx`` — ``(tenant, asset, read_at)`` — REACHABLE: ``tenant_id``
    is its leading column, so a subquery filtering on ``asset_id`` alone falls back to the plain FK
    index and then filesorts, per plan on the board. Passed as a LITERAL rather than
    ``OuterRef("tenant_id")`` for the reason :func:`_spare_part_qs` gives: the scoping is identical
    and a correlated tenant reference is one more outer column MySQL must resolve inside a
    dependent subquery.
    """
    named = (MeterReading.objects
             .filter(tenant=tenant, asset_id=OuterRef("asset_id"),
                     meter_name=OuterRef("asset__meter_name"))
             .order_by("-read_at", "-id"))
    any_meter = (MeterReading.objects
                 .filter(tenant=tenant, asset_id=OuterRef("asset_id"))
                 .order_by("-read_at", "-id"))
    return models.Case(
        models.When(asset__meter_name="",
                    then=models.Subquery(any_meter.values("pk")[:1])),
        default=models.Subquery(named.values("pk")[:1]),
        output_field=models.IntegerField(),
    )


def _due_reason(plan, status, days_left, gap, latest):
    """``(reason_kind, sentence)`` — WHY this plan is on the board, with its arithmetic shown.

    The decomposition is exact rather than a guess. ``MaintenancePlan.due_status()`` can only answer
    ``overdue`` for one of three reasons — the meter axis passed its target, the condition axis
    crossed its threshold, or the date passed — so testing them in that order and falling through is
    a complete cover of the method's own logic, with no second copy of the comparison living here.
    """
    unit = plan.asset.meter_unit or ""
    unit_suffix = f" {unit}" if unit else ""

    if gap is not None and gap <= ZERO:
        latest_value = latest.reading if latest is not None else None
        return "meter", (
            f"Meter is {q4(abs(gap))}{unit_suffix} past the {plan.next_due_reading}{unit_suffix} "
            f"target" + (f" — reading now {latest_value}{unit_suffix}." if latest_value is not None
                         else "."))

    if days_left is not None and days_left < 0:
        return "date", (f"Was due {plan.next_due_on:%b %d, %Y} — {abs(days_left)} day(s) overdue.")

    if status == "overdue":
        # The only remaining way due_status() says overdue: the condition axis fired.
        operator = plan.get_condition_operator_display() or "past"
        latest_value = latest.reading if latest is not None else "—"
        return "condition", (
            f"Latest reading {latest_value}{unit_suffix} is {operator.lower()} the "
            f"{plan.condition_threshold}{unit_suffix} threshold.")

    if days_left == 0:
        return "date", f"Due today ({plan.next_due_on:%b %d, %Y})."

    if days_left is not None:
        return "date", (f"Due {plan.next_due_on:%b %d, %Y} — in {days_left} day(s)"
                        + (f", raisable from {plan.lead_time_days} day(s) out."
                           if plan.lead_time_days else "."))

    return "date", "No date scheduled."


@login_required
def pm_forecast(request):
    """Preventive work owed inside ``?days=N``, bucketed, plus the open-jobs board.

    THE BUCKETS. ``overdue`` and ``due today`` come straight from ``MaintenancePlan.due_status()``,
    so they mean exactly what every other page in the module means by them. ``due soon`` is
    **this page's horizon**, not the plan's own ``lead_time_days``: the planner asked "what is owed
    in the next N days", and answering with each plan's private call horizon instead would silently
    hide a job due in three weeks because its lead time happens to be seven days. Each row still
    carries ``within_lead_time`` — the plan's own "may be raised now" answer — so the Generate button
    can be rendered honestly.

    WHY A PLAN WITH A FUTURE DATE CAN READ OVERDUE. On a ``combined`` plan, due is whichever axis
    arrives first. The work was owed at 500 hours and the machine is at 540, so the meter outranks a
    date that has not arrived. That is the model's contract, not a bug, and ``due_reason`` says so on
    the row.

    QUERIES. One for the plans (with the open-job ``Exists`` and the latest-reading id folded into
    the same statement), one to fetch those readings, one for the job counts, one for the board
    slice. Nothing scales with the number of rows.

    NOT PAGINATED, deliberately. The buckets and the header counts have to describe the same set the
    table shows, and a paginated board whose chips counted something else would be a page that
    contradicts itself (the ``reorder_alerts`` / ``valuation_report`` posture). The scan is bounded
    by ``is_active`` plus the horizon, and by there being one plan per obligation per machine.
    """
    days, days_raw, days_invalid = _horizon(request)
    today = timezone.localdate()
    horizon = today + datetime.timedelta(days=days)

    # A plan blocks a duplicate generate while it already has a live job. EXISTS, not COUNT: the
    # template asks "is there one?", and a COUNT would GROUP BY the whole work-order table per plan
    # (and unset QuerySet.ordered into the bargain).
    has_open_job = Exists(MaintenanceWorkOrder.objects.filter(
        plan_id=OuterRef("pk"), status__in=MaintenanceWorkOrder.OPEN_STATUSES))

    # The usage-driven triggers cannot be pre-filtered by date: a meter or condition plan comes due
    # because the MACHINE moved, which no WHERE clause on next_due_on can see. They are pulled in
    # full and evaluated in Python; the calendar-only plans are bounded by the horizon in SQL so the
    # scan does not grow with the length of the schedule.
    usage_triggers = ("meter", "combined", "condition")
    plans = list(MaintenancePlan.objects
                 .filter(tenant=request.tenant, is_active=True)
                 .filter(Q(next_due_on__isnull=False, next_due_on__lte=horizon)
                         | Q(trigger_type__in=usage_triggers))
                 .select_related("asset", "assigned_to", "parts_location")
                 .annotate(has_open_job=has_open_job,
                           newest_reading_pk=_newest_reading_case(request.tenant))
                 .order_by(F("next_due_on").asc(nulls_last=True), "-id"))

    reading_ids = {p.newest_reading_pk for p in plans if p.newest_reading_pk}
    readings = (MeterReading.objects
                .filter(tenant=request.tenant, pk__in=reading_ids)
                .select_related("recorded_by")
                .in_bulk()) if reading_ids else {}

    overdue, due_today, due_soon = [], [], []
    for plan in plans:
        # THE PRIME. Set unconditionally (None included) so latest_reading() can never fall through
        # to a query — see _newest_reading_case.
        plan._latest_reading_cache = readings.get(plan.newest_reading_pk)

        status = plan.due_status(today)
        days_left = plan.days_until_due(today)
        gap = plan.meter_gap()
        latest = plan._latest_reading_cache
        reason_kind, reason = _due_reason(plan, status, days_left, gap, latest)

        row = {
            "plan": plan,
            "asset": plan.asset,
            "due_status": status,
            # One lookup from the model's own dicts, so the badge and the bucket cannot disagree.
            "due_status_label": MaintenancePlan.DUE_STATUS_LABELS.get(status, "Not scheduled"),
            "due_status_css": MaintenancePlan.DUE_STATUS_CSS.get(status, "badge-muted"),
            "days_until_due": days_left,
            "meter_gap": gap,
            "latest_reading": latest,
            "due_reason": reason,
            "reason_kind": reason_kind,
            "usage_due": reason_kind in ("meter", "condition"),
            # The plan's OWN call horizon — whether a job may legitimately be raised right now.
            "within_lead_time": status in ("overdue", "due_today", "due_soon"),
            "has_open_job": plan.has_open_job,
        }

        if status == "overdue":
            overdue.append(row)
        elif status == "due_today":
            due_today.append(row)
        elif days_left is not None and 0 < days_left <= days:
            due_soon.append(row)
        # else: a plan beyond the horizon, or a usage-driven plan that has not fired and carries no
        # date inside the window. Neither is owed in the period the planner asked about.

    # Usage-driven first (the machine has already passed the target, so it is owed regardless of the
    # calendar), then most days overdue.
    overdue.sort(key=lambda r: (0 if r["usage_due"] else 1,
                                r["days_until_due"] if r["days_until_due"] is not None else 0))
    due_soon.sort(key=lambda r: r["days_until_due"])

    # ------------------------------------------------------------------ the open-jobs board
    # OPEN_STATUSES, the model's own declared "still live" set, rather than a fourth hand-written
    # tuple — it spans requested -> approved -> scheduled -> in_progress AND on_hold, so a job parked
    # on hold cannot quietly vanish from the one board dispatch reads.
    jobs = (MaintenanceWorkOrder.objects
            .filter(tenant=request.tenant, status__in=MaintenanceWorkOrder.OPEN_STATUSES)
            .select_related("asset", "assigned_to", "plan"))

    status_labels = dict(MaintenanceWorkOrder.STATUS_CHOICES)
    ladder = {value: index for index, value in enumerate(MaintenanceWorkOrder.OPEN_STATUSES)}
    # ONE grouped query for every chip, over the WHOLE queue rather than the rendered window.
    # `.order_by()` is load-bearing: Meta.ordering is ["-reported_at", "-id"], and an inherited
    # ORDER BY column would be dragged into the GROUP BY and split the counts per timestamp.
    open_by_status = [
        {"status": row["status"],
         "label": status_labels.get(row["status"], row["status"]),
         "css": MaintenanceWorkOrder.STATUS_CSS.get(row["status"], "badge-muted"),
         "count": row["n"]}
        for row in jobs.order_by().values("status").annotate(n=Count("id"))
    ]
    open_by_status.sort(key=lambda r: ladder.get(r["status"], len(ladder)))
    open_job_count = sum(row["count"] for row in open_by_status)

    # Urgent first. PRIORITY_CHOICES is already declared in urgency order (urgent, high, medium,
    # low), so the rank IS its index — ordering on the raw column would sort alphabetically and put
    # "high" above "urgent", which on a dispatch board is the answer being wrong.
    priority_rank = models.Case(
        *[models.When(priority=value, then=models.Value(index))
          for index, (value, _label) in enumerate(PRIORITY_CHOICES)],
        default=models.Value(len(PRIORITY_CHOICES)), output_field=models.IntegerField())
    open_jobs = list(jobs.annotate(priority_rank=priority_rank)
                     .order_by("priority_rank",
                               F("scheduled_start").asc(nulls_last=True),
                               "-reported_at")[:MAX_BOARD_ROWS + 1])
    open_jobs_truncated = len(open_jobs) > MAX_BOARD_ROWS
    del open_jobs[MAX_BOARD_ROWS:]

    return render(request, "scm/assets/pm_forecast.html", {
        "days": days,
        "days_raw": days_raw,
        "days_invalid": days_invalid,
        "day_options": FORECAST_DAY_OPTIONS,
        "min_days": MIN_FORECAST_DAYS,
        "max_days": MAX_FORECAST_DAYS,
        "today": today,
        "horizon": horizon,
        "overdue": overdue,
        "due_today": due_today,
        "due_soon": due_soon,
        "open_jobs": open_jobs,
        "open_jobs_truncated": open_jobs_truncated,
        "board_cap": MAX_BOARD_ROWS,
        "open_by_status": open_by_status,
        "open_job_count": open_job_count,
        "stats": {
            "overdue": len(overdue),
            "due_today": len(due_today),
            "due_soon": len(due_soon),
            "total_due": len(overdue) + len(due_today) + len(due_soon),
            "plans_considered": len(plans),
            "open_jobs": open_job_count,
        },
    })


# =============================================================================================
# 4.13 report 2 — the MRO storeroom
# =============================================================================================
#: Printed on the page. The single most important thing a reader of this screen has to understand is
#: that they are looking at 4.3, filtered — not at a parallel parts master they now have to keep in
#: step with the stock ledger.
LEDGER_NOTE = (
    "This is 4.3's inventory, filtered — not a second parts catalogue. A spare part is an "
    "scm.Item flagged 'is spare part', its on-hand is the live SUM of the append-only StockMove "
    "ledger (there is no stored quantity anywhere to drift from it), and its min/max come from the "
    "same ReorderRule the buyer already maintains. Issuing a part to a maintenance job posts a "
    "negative StockMove of type 'maintenance' into that very ledger, which is what the consumption "
    "column below counts."
)

STOCK_STATE_CHOICES = [
    ("below", "At or below reorder point"),
    ("zero", "Out of stock"),
    ("in_stock", "In stock"),
]
ACTIVE_CHOICES = [("active", "Active"), ("inactive", "Inactive")]

#: Default consumption window — the last twelve months, the carbon report's default.
DEFAULT_WINDOW_DAYS = 365


def _day(raw):
    """A ``YYYY-MM-DD`` GET value as a date, or ``None`` if it is anything else.

    ``None`` rather than a raise: the window comes out of the query string, so a hand-typed or
    truncated value must drop the filter, never 500 (L11's rule applied to a date instead of an int).
    Bounded to ``analytics.MIN_PERIOD_DATE``/``MAX_PERIOD_DATE`` for the same reason 4.12's parser is
    — a date within a year of ``date.min`` makes the default-window subtraction below raise
    ``OverflowError``, which is a 500 from a value anybody can type into the address bar.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        value = datetime.date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None
    if not (analytics.MIN_PERIOD_DATE <= value <= analytics.MAX_PERIOD_DATE):
        return None
    return value


def _window(request):
    """Resolve the consumption window, defaulting to the last twelve months.

    Reports whether a value was typed and REJECTED, so the page can say "showing the default window"
    instead of silently ignoring what somebody asked for. A reversed window is a typo rather than an
    empty result, so it is swapped and flagged.
    """
    raw_from = (request.GET.get("date_from") or "").strip()
    raw_to = (request.GET.get("date_to") or "").strip()
    date_from, date_to = _day(raw_from), _day(raw_to)
    invalid = bool(raw_from and date_from is None) or bool(raw_to and date_to is None)
    if date_to is None:
        date_to = timezone.localdate()
    if date_from is None:
        date_from = date_to - datetime.timedelta(days=DEFAULT_WINDOW_DAYS)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
        invalid = True
    return date_from, date_to, raw_from, raw_to, invalid


def _aware_range(date_from, date_to):
    """The window as an inclusive AWARE datetime pair for ``StockMove.moved_at``.

    An explicit range rather than ``moved_at__date__gte``: ``__date`` compiles to ``CONVERT_TZ`` on
    MariaDB and returns NULL when the timezone tables are not loaded, which on XAMPP they are not
    (the 4.12 carbon-report finding). ``time.max`` on the upper bound so a draw made at 16:00 on the
    closing day is inside the window a user asked for — a bare date would resolve to midnight and
    drop the whole final day.
    """
    return (timezone.make_aware(datetime.datetime.combine(date_from, datetime.time.min)),
            timezone.make_aware(datetime.datetime.combine(date_to, datetime.time.max)))


def _spare_part_qs(tenant):
    """This workspace's MRO items, annotated with the two figures the page filters and chips on.

    ``derived_on_hand`` is the item's on-hand **from ONE grouped aggregate over the ledger**
    (``GROUP BY item_id``, inside a scalar subquery) — the whole reason this page is shaped the way
    it is. Calling ``Item.on_hand()`` per row is the N+1 the plan forbids by name, and it would be a
    fresh aggregate for every printed reference because a Django template re-evaluates the call each
    time it appears.

    **Why a correlated subquery rather than the more obvious
    ``annotate(Sum("stock_moves__quantity"))``.** The join form makes the whole item query an
    aggregate query, so Django moves every filter that touches the annotation into a ``HAVING``
    clause — and on MySQL/MariaDB, Django's functional-dependency optimisation groups by the primary
    key ALONE, which means ``HAVING`` cannot resolve a plain column such as ``scm_item.reorder_point``
    unless it happens to be in the (unstable) select list. It works for the page's row query and then
    raises ``OperationalError (1054) Unknown column 'scm_item.reorder_point' in 'having clause'`` the
    moment the same filter is counted for a header chip. Verified against ``nav_erp``, not theorised.
    The subquery form keeps every filter in ``WHERE``, so filtering, ordering, pagination and
    ``.count()`` all behave — and it is still a single SQL statement, with no query per Python row.

    The annotation is NOT called ``on_hand``: that would shadow ``Item.on_hand()`` on every instance
    the queryset returns (an instance ``__dict__`` entry beats a class attribute), so any later code
    that legitimately calls the method on one of these objects would get a ``Decimal`` back and a
    ``TypeError`` a moment later.

    ``effective_point`` is the strictest configured reorder point — the highest active
    ``ReorderRule`` point for the item, falling back to the item-wide default when the item has no
    rule at all (``Item.reorder_point`` is documented as exactly that default). It is compared
    against NETWORK on-hand, and the page says so: the per-location breakdown and the per-rule chips
    on each row are the finer-grained answer, computed per rule against that rule's own location.

    Both subqueries are scoped with the LITERAL tenant rather than ``OuterRef("tenant_id")``: the
    scoping is identical, and a correlated tenant reference is one more outer column MySQL has to
    resolve from inside a derived table.
    """
    on_hand = (StockMove.objects
               .filter(tenant=tenant, item_id=OuterRef("pk"))
               .order_by()
               .values("item_id")
               .annotate(quantity=Sum("quantity"))
               .values("quantity")[:1])
    strictest = (ReorderRule.objects
                 .filter(tenant=tenant, item_id=OuterRef("pk"), is_active=True)
                 .order_by()
                 .values("item_id")
                 .annotate(point=models.Max("reorder_point"))
                 .values("point")[:1])
    return (Item.objects
            .filter(tenant=tenant, is_spare_part=True)
            .select_related("category", "uom")
            .annotate(
                derived_on_hand=Coalesce(models.Subquery(on_hand, output_field=_QTY),
                                         models.Value(ZERO), output_field=_QTY),
                rule_point=models.Subquery(
                    strictest, output_field=models.DecimalField(max_digits=14, decimal_places=2)))
            .annotate(
                effective_point=Coalesce(
                    "rule_point", "reorder_point",
                    output_field=models.DecimalField(max_digits=14, decimal_places=2))))


@login_required
def sparepart_list(request):
    """The MRO storeroom: derived on-hand, the ReorderRule min/max, and maintenance consumption.

    FILTERS, all applied BEFORE pagination so page 2 shows the right rows: ``q`` (sku / name /
    description), ``category`` (int, through ``as_db_int`` so ``?category=abc`` skips the filter
    rather than raising), ``stock`` (``below`` / ``zero`` / ``in_stock``, expressed in SQL against
    the annotations so it is a HAVING clause and not a Python pass over an already-paginated page),
    ``is_active``, and the ``date_from`` / ``date_to`` consumption window.

    QUERIES. One for the page of items (on-hand and the strictest reorder point folded in), then
    exactly four more for the whole page: the per-location breakdown, the item's reorder rules,
    those rules' on-hand (``ReorderRule.on_hand_map``, one grouped query for every rule at once) and
    the windowed maintenance draw. None of them scales with the number of rows on the page.

    THE HEADER CHIPS ARE WORKSPACE-WIDE, not page-wide — "6 below reorder point" is a fact somebody
    has to act on, and recomputing it per filter would make the number change as you browse (the
    ``tradelicense_list`` posture). All three counts come from ONE ``aggregate()``: they were three
    ``.count()`` calls, and two of them carried the correlated on-hand ledger subquery in their
    WHERE, so the strip cost three scans of the item table to print three numbers.
    """
    date_from, date_to, raw_from, raw_to, window_invalid = _window(request)
    start_dt, end_dt = _aware_range(date_from, date_to)

    qs = _spare_part_qs(request.tenant)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(sku__icontains=q) | Q(name__icontains=q) | Q(description__icontains=q))

    # L11: never hand a non-pk to an int FK filter. as_db_int refuses non-decimal, Unicode
    # superscripts AND over-range values — all three would otherwise raise out of .filter().
    category_pk = as_db_int(request.GET.get("category"))
    if category_pk is not None:
        qs = qs.filter(category_id=category_pk)

    stock = (request.GET.get("stock") or "").strip()
    if stock == "below":
        # `effective_point > 0` is not decoration: without it every unstocked part with no policy
        # configured (0 on hand, 0 point) reads as "below reorder point", which would drown the one
        # signal this page exists to give.
        qs = qs.filter(effective_point__gt=ZERO, derived_on_hand__lte=F("effective_point"))
    elif stock == "zero":
        qs = qs.filter(derived_on_hand__lte=ZERO)
    elif stock == "in_stock":
        qs = qs.filter(derived_on_hand__gt=ZERO)

    active = (request.GET.get("is_active") or "").strip()
    if active == "active":
        qs = qs.filter(is_active=True)
    elif active == "inactive":
        qs = qs.filter(is_active=False)

    page_obj = paginate(request, qs.order_by("sku"))
    items = list(page_obj.object_list)
    item_ids = [item.pk for item in items]

    # --- per-location on-hand, ONE grouped query for the whole page ----------------------------
    by_location = {}
    if item_ids:
        for row in (StockMove.objects
                    .filter(tenant=request.tenant, item_id__in=item_ids)
                    .values("item_id", "location_id", "location__code", "location__name")
                    .annotate(qty=Sum("quantity"))
                    .order_by("item_id", "location__code")):
            qty = row["qty"] or ZERO
            if qty == ZERO:
                # A location whose moves net to nothing is not a place this part is held. Printing
                # it as a 0 row would make an empty bin look like a stocking location.
                continue
            by_location.setdefault(row["item_id"], []).append({
                "location_id": row["location_id"],
                "code": row["location__code"],
                "name": row["location__name"],
                "qty": qty,
            })

    # --- the reorder policy, ONE query for the rules + ONE for all their on-hands ---------------
    rules_by_item, all_rules = {}, []
    if item_ids:
        all_rules = list(ReorderRule.objects
                         .filter(tenant=request.tenant, item_id__in=item_ids, is_active=True)
                         .select_related("location"))
        for rule in all_rules:
            rules_by_item.setdefault(rule.item_id, []).append(rule)
    # The model's own batch helper: {(item_id, location_id): qty} for every rule at once. Each of
    # current_on_hand / is_below_point / suggested_quantity would otherwise fire its own aggregate,
    # so a page of rules costs 2-3 queries PER RULE without it (the 4.3 perf finding).
    rule_on_hand = ReorderRule.on_hand_map(request.tenant, all_rules)

    # --- maintenance consumption in the window, ONE grouped query ------------------------------
    consumed = {}
    if item_ids:
        for row in (StockMove.objects
                    .filter(tenant=request.tenant, item_id__in=item_ids, move_type="maintenance",
                            moved_at__gte=start_dt, moved_at__lte=end_dt)
                    .order_by()
                    .values("item_id")
                    .annotate(qty=Sum("quantity"),
                              value=Sum(F("quantity") * F("unit_cost"), output_field=_MONEY),
                              moves=Count("id"))):
            consumed[row["item_id"]] = {
                # The ledger stores an outbound draw as a NEGATIVE quantity. Consumption is what
                # LEFT, so the sign is flipped exactly once — here, not in the template.
                "quantity": -(row["qty"] or ZERO),
                "value": q2(-(row["value"] or ZERO)),
                "moves": row["moves"],
            }

    rows = []
    for item in items:
        on_hand = item.derived_on_hand or ZERO
        point = item.effective_point or ZERO

        rule_rows = []
        for rule in rules_by_item.get(item.pk, []):
            qty = rule_on_hand.get((rule.item_id, rule.location_id), ZERO)
            rule_rows.append({
                "rule": rule,
                "location": rule.location,
                "on_hand": qty,
                # min = the reorder point; max = the level the suggested quantity brings stock back
                # up to (point + safety stock), which is what "min/max" means to a storeroom.
                "min": rule.reorder_point or ZERO,
                "max": (rule.reorder_point or ZERO) + (rule.safety_stock or ZERO),
                "is_below": rule.is_below_point(on_hand=qty),
                "suggested": rule.suggested_quantity(on_hand=qty),
            })

        is_below = point > ZERO and on_hand <= point
        rows.append({
            "item": item,
            "on_hand": on_hand,
            # The quick valuation figure, item.average_cost × on-hand. The authoritative FIFO/LIFO
            # layer walk is the 4.3 valuation report's job and is not duplicated here.
            "value": q2(on_hand * (item.average_cost or ZERO)),
            "reorder_point": point,
            "has_rule": item.rule_point is not None,
            "max_level": max((r["max"] for r in rule_rows), default=None),
            "is_below": is_below,
            "shortfall": q4(point - on_hand) if is_below else None,
            "locations": by_location.get(item.pk, []),
            "rules": rule_rows,
            # None means NO maintenance draw was recorded in this window — and unlike the
            # depreciation report's None, that IS a true zero, because the ledger is complete for
            # this question. It is passed as None purely so the template can print an em dash rather
            # than a column of 0.0000s.
            "consumed": consumed.get(item.pk),
        })

    # --- workspace-wide chips -------------------------------------------------------------------
    # ONE aggregate for the three counts, not three `.count()` calls — and two of those three
    # carried the correlated on-hand ledger subquery in their WHERE, so this is three scans of the
    # item table (each re-running that subquery per item) collapsed into one. The same shape
    # `asset_list` and `maintenanceplan_list` already use for their header strips.
    counts = _spare_part_qs(request.tenant).aggregate(
        total=Count("id"),
        # `effective_point > 0` is not decoration — see the `stock=below` filter above for why an
        # unstocked part with no policy configured must not read as "below reorder point".
        below=Count("id", filter=Q(effective_point__gt=ZERO,
                                   derived_on_hand__lte=F("effective_point"))),
        zero=Count("id", filter=Q(derived_on_hand__lte=ZERO)),
    )
    # One aggregate over the LEDGER rather than over the annotated item queryset: Django refuses to
    # aggregate an aggregate ("Cannot compute Sum(<aggregate>)"), and Σ(quantity × the item's cached
    # average) over every move is arithmetically the same figure as Σ(on-hand × average) per item.
    stock_value = (StockMove.objects
                   .filter(tenant=request.tenant, item__is_spare_part=True)
                   .aggregate(v=Sum(F("quantity") * F("item__average_cost"),
                                    output_field=_MONEY))["v"])
    window_agg = (StockMove.objects
                  .filter(tenant=request.tenant, item__is_spare_part=True,
                          move_type="maintenance", moved_at__gte=start_dt, moved_at__lte=end_dt)
                  .aggregate(v=Sum(F("quantity") * F("unit_cost"), output_field=_MONEY),
                             n=Count("id")))

    return render(request, "scm/assets/spare_parts.html", {
        "rows": rows,
        "page_obj": page_obj,
        "q": q,
        # Every dropdown's data, from the view — a filter <select> with no context is the recurring
        # bug the house rule exists to stop.
        "categories": ItemCategory.objects.filter(tenant=request.tenant, is_active=True),
        "stock": stock,
        "stock_choices": STOCK_STATE_CHOICES,
        "is_active": active,
        "active_choices": ACTIVE_CHOICES,
        "date_from": date_from,
        "date_to": date_to,
        "date_from_raw": raw_from,
        "date_to_raw": raw_to,
        "window_invalid": window_invalid,
        "stats": {
            "total": counts["total"] or 0,
            "below_count": counts["below"] or 0,
            "zero_count": counts["zero"] or 0,
            "stock_value": q2(stock_value or ZERO),
            "consumed_value": q2(-(window_agg["v"] or ZERO)),
            "consumed_moves": window_agg["n"],
        },
        "ledger_note": LEDGER_NOTE,
    })


# =============================================================================================
# 4.13 report 3 — repair vs replace
# =============================================================================================
#: Printed on the page, and the reason this report reads rather than computes.
ACCOUNTING_NOTE = (
    "Acquisition cost, accumulated depreciation and book value are READ from the linked "
    "accounting.FixedAsset. SCM stores none of them, recomputes none of them and posts no journal "
    "entry — the statutory depreciation figures and their GL postings belong to the accounting "
    "module, and two writers of one accumulated figure is exactly how the two numbers on the two "
    "pages come to disagree. Maintenance spend is the SCM side: issued parts at the cost they were "
    "drawn at, plus labour, plus contractor charges, over every job that was not cancelled."
)

#: Where the repair-vs-replace ratio changes colour. A RULE OF THUMB and labelled as one on the
#: page, not a policy engine: cumulative repairs past half the remaining book value is the
#: conventional point to start planning a replacement, and past the whole book value is the point at
#: which the machine has cost more to keep than it is still worth. Declared here so the chip is
#: decided in one place and the template invents no thresholds of its own.
RATIO_WATCH_PCT = Decimal("50")
RATIO_REPLACE_PCT = Decimal("100")

LINK_CHOICES = [("linked", "Linked to a fixed asset"), ("unlinked", "No capitalised record")]


def _ratio_chip(ratio_pct):
    """``(label, css)`` for one repair-vs-replace ratio. ``None`` is its own muted state.

    "Not comparable" is never green: not knowing what a machine is still worth is not the same as
    knowing it is worth keeping (the ``Asset.warranty_chip`` posture). theme.css has
    badge-green / red / amber / info / muted / slate only — badge-success and friends render
    completely unstyled (L33).
    """
    if ratio_pct is None:
        return ("Not comparable", "badge-muted")
    if ratio_pct >= RATIO_REPLACE_PCT:
        return ("Repairs exceed book value", "badge-red")
    if ratio_pct >= RATIO_WATCH_PCT:
        return ("Watch — review replacement", "badge-amber")
    return ("Economic to repair", "badge-green")


@login_required
def asset_depreciation_report(request):
    """Book value from accounting, maintenance spend from SCM, and the ratio between them.

    THE DIVISION IS SHOWN. Each row carries ``maintenance_spend`` and ``book_value`` alongside
    ``ratio_pct`` so the page can print ``12,400 ÷ 48,000 = 25.8 %`` rather than a number the reader
    has to trust. Nothing here is called a model or a prediction, because it is arithmetic.

    THREE WAYS A ROW CAN HAVE NO RATIO, all reported rather than zeroed:

    * **no ``fixed_asset`` link** — there is no capitalised record to compare against. Counted into
      ``unlinked_count`` and excluded from every money total and from the ratio.
    * **a cross-workspace link** — defence in depth. ``Asset.clean()`` refuses one, but this page
      READS money out of another app's table, so a row that predates that guard (a fixture, a direct
      database edit) is treated as UNLINKED here rather than quietly printing another tenant's book
      value. Counted separately so the anomaly is visible instead of merely handled.
    * **a nil book value** — fully depreciated or written down. ``spend ÷ 0`` has no answer, so the
      ratio is ``None`` and **never infinity**, and the asset is counted into ``zero_book_count``.
      Reporting it as an enormous percentage would make a healthy, fully-written-down machine the
      loudest row on a page about replacement decisions.

    QUERIES. One for the assets, then TWO grouped aggregates for the spend — and two is not
    optional. Parts live at a different grain from the job header, so asking for both in one
    ``aggregate()`` joins the child rows in, FANS THE JOB ROWS OUT and multiplies every
    ``labour_cost`` and ``external_cost`` by that job's part count: a three-part repair charged three
    times its labour, silently, forever. ``Asset.maintenance_cost_to_date()`` documents the same trap
    and is deliberately not called per row here — it is correct and it costs two queries EACH.

    NOT PAGINATED, deliberately: the coverage line and the money totals have to describe exactly the
    rows the table shows, and a report whose footer counted a different set from its body is a page
    that contradicts itself. The scan is bounded by the physical plant (the ``valuation_report`` /
    ``reorder_alerts`` posture).
    """
    qs = (Asset.objects
          .filter(tenant=request.tenant)
          .select_related("fixed_asset", "location", "work_center", "org_unit")
          .order_by("code"))

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q) | Q(category__icontains=q)
                       | Q(serial_number__icontains=q) | Q(fixed_asset__number__icontains=q)
                       | Q(fixed_asset__name__icontains=q))

    # All CharField choices — a junk value simply matches nothing rather than raising, so no L11
    # int guard is owed on these three.
    status = (request.GET.get("status") or "").strip()
    if status:
        qs = qs.filter(status=status)
    asset_type = (request.GET.get("asset_type") or "").strip()
    if asset_type:
        qs = qs.filter(asset_type=asset_type)
    criticality = (request.GET.get("criticality") or "").strip()
    if criticality:
        qs = qs.filter(criticality=criticality)

    linked = (request.GET.get("linked") or "").strip()
    if linked == "linked":
        qs = qs.filter(fixed_asset__isnull=False)
    elif linked == "unlinked":
        qs = qs.filter(fixed_asset__isnull=True)

    location_pk = as_db_int(request.GET.get("location"))
    if location_pk is not None:
        qs = qs.filter(location_id=location_pk)

    assets = list(qs)
    asset_ids = [asset.pk for asset in assets]

    # --- maintenance spend: TWO grains, TWO queries — see the docstring -------------------------
    header, parts = {}, {}
    if asset_ids:
        for row in (MaintenanceWorkOrder.objects
                    .filter(tenant=request.tenant, asset_id__in=asset_ids)
                    # A cancelled job may still carry a labour figure typed before it was called
                    # off; counting it would charge the asset for work nobody did.
                    .exclude(status="cancelled")
                    .order_by()
                    .values("asset_id")
                    .annotate(labour=Sum(F("labour_hours") * F("labour_rate"), output_field=_MONEY),
                              external=Sum("external_cost"),
                              jobs=Count("id"),
                              downtime=Sum("downtime_minutes"))):
            header[row["asset_id"]] = row
        for row in (MaintenanceWorkOrderPart.objects
                    # Scoped through work_order__tenant and NEVER on the child alone — the line
                    # carries no tenant column of its own (the ComplianceCheck precedent).
                    .filter(work_order__tenant=request.tenant,
                            work_order__asset_id__in=asset_ids, is_issued=True)
                    .exclude(work_order__status="cancelled")
                    .order_by()
                    .values("work_order__asset_id")
                    .annotate(value=Sum(F("quantity") * F("unit_cost"), output_field=_MONEY))):
            parts[row["work_order__asset_id"]] = row["value"] or ZERO

    rows = []
    linked_count = unlinked_count = foreign_link_count = zero_book_count = ratio_count = 0
    total_acquisition = total_accumulated = total_book = ZERO
    total_spend = linked_spend = unlinked_spend = ZERO

    for asset in assets:
        head = header.get(asset.pk) or {}
        spend = q2((head.get("labour") or ZERO) + (head.get("external") or ZERO)
                   + (parts.get(asset.pk) or ZERO))
        total_spend += spend

        fixed_asset = asset.fixed_asset
        foreign = fixed_asset is not None and fixed_asset.tenant_id != asset.tenant_id
        if foreign:
            fixed_asset = None
            foreign_link_count += 1

        row = {
            "asset": asset,
            "fixed_asset": fixed_asset,
            "foreign_link": foreign,
            "job_count": head.get("jobs") or 0,
            "downtime_minutes": head.get("downtime") or 0,
            "maintenance_spend": spend,
            "parts_spend": q2(parts.get(asset.pk) or ZERO),
            "labour_spend": q2(head.get("labour") or ZERO),
            "external_spend": q2(head.get("external") or ZERO),
        }

        if fixed_asset is None:
            unlinked_count += 1
            unlinked_spend += spend
            row.update({
                "acquisition_cost": None,
                "accumulated_depreciation": None,
                "book_value": None,
                "ratio_pct": None,
                "excluded_reason": (
                    "This asset is linked to a fixed asset in another workspace and is excluded."
                    if foreign else
                    "No capitalised record is linked, so there is no book value to compare the "
                    "repair spend against. Link the asset to its accounting.FixedAsset to include "
                    "it in the ratio."),
            })
        else:
            linked_count += 1
            linked_spend += spend
            acquisition = fixed_asset.acquisition_cost or ZERO
            accumulated = fixed_asset.accumulated_depreciation or ZERO
            # READ from the accounting row, never recomputed here (L29).
            book = fixed_asset.book_value()
            total_acquisition += acquisition
            total_accumulated += accumulated
            total_book += book

            if book > ZERO:
                ratio = q2(spend * Decimal("100") / book)
                ratio_count += 1
                reason = ""
            else:
                # None, NEVER infinity and never a huge percentage — see the docstring.
                ratio = None
                zero_book_count += 1
                reason = ("Book value is nil (fully depreciated or written down), so spend ÷ book "
                          "value has no answer. Excluded from the ratio.")
            row.update({
                "acquisition_cost": acquisition,
                "accumulated_depreciation": accumulated,
                "book_value": book,
                "ratio_pct": ratio,
                "excluded_reason": reason,
            })

        label, css = _ratio_chip(row["ratio_pct"])
        row["ratio_label"] = label
        row["ratio_css"] = css
        rows.append(row)

    # Worst first — this page is read to find the machines that have cost more than they are worth.
    # Rows with no ratio sort to the bottom rather than being dropped: they are the coverage gap and
    # somebody has to see them.
    rows.sort(key=lambda r: (r["ratio_pct"] is None, -(r["ratio_pct"] or ZERO), r["asset"].code))

    considered = len(rows)
    return render(request, "scm/assets/asset_depreciation.html", {
        "rows": rows,
        "q": q,
        "status": status,
        "asset_type": asset_type,
        "criticality": criticality,
        "linked": linked,
        "location": (request.GET.get("location") or "").strip(),
        "status_choices": Asset.STATUS_CHOICES,
        "type_choices": Asset.ASSET_TYPE_CHOICES,
        # From the shared vocabulary in models/AssetManagement/_choices.py, not re-typed here —
        # a filter dropdown built from a second copy of a choices list is one that drifts.
        "criticality_choices": CRITICALITY_CHOICES,
        "link_choices": LINK_CHOICES,
        "locations": Location.objects.filter(tenant=request.tenant),
        "stats": {
            "considered_count": considered,
            "linked_count": linked_count,
            "unlinked_count": unlinked_count,
            "foreign_link_count": foreign_link_count,
            "zero_book_count": zero_book_count,
            "ratio_count": ratio_count,
            # None, never 0 %, when there is nothing to measure — a zero coverage figure on an empty
            # tenant reads as "0 % of our assets are capitalised", which is a different claim.
            "coverage_pct": (q2(Decimal(linked_count) * Decimal("100") / Decimal(considered))
                             if considered else None),
            # None rather than 0.00 when NOTHING is linked: a money total of zero would read as
            # "these machines cost nothing", when the truth is that nobody told us what they cost.
            "total_acquisition": q2(total_acquisition) if linked_count else None,
            "total_accumulated": q2(total_accumulated) if linked_count else None,
            "total_book": q2(total_book) if linked_count else None,
            # Spend is knowable WITHOUT the accounting link, so it is a real zero and is reported as
            # one — the asymmetry with the three totals above is the point of the page.
            "total_spend": q2(total_spend),
            "linked_spend": q2(linked_spend),
            "unlinked_spend": q2(unlinked_spend),
            "overall_ratio_pct": (q2(linked_spend * Decimal("100") / total_book)
                                  if total_book > ZERO else None),
        },
        "watch_pct": RATIO_WATCH_PCT,
        "replace_pct": RATIO_REPLACE_PCT,
        "accounting_note": ACCOUNTING_NOTE,
    })
