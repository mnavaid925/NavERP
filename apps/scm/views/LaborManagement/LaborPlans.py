"""SCM 4.14 Labor Management — ``LaborPlan`` views: the CRUD, the ladder, and the generator.

**One table, one child, one generator.** A labour plan is SAP EWM's *planned workload document*: a
persisted artefact with a lifecycle, not a screen that re-answers last week's staffing question with
this week's data. ``status`` is ``editable=False`` and absent from ``LaborPlanForm.Meta.fields``, so
the only way it moves is through the three verbs below — a crafted ``status=approved`` in a POST
body cannot land, because there is no path from form data to the column at all.

**The ladder, stated once** (the module constants are what BOTH the guard inside each verb and the
``can_*`` flag handed to the detail template read, so a button and the route behind it can never
disagree — the 4.10 "two of three shapes" finding)::

    draft --generate--> planned --approve--> approved
      \\                    \\                    |
       \\-------------------- archive ------------/  --> archived

``generate`` is the ONLY route into ``planned``: the grid is the plan, so "the generator has run" and
"this plan has lines" are the same fact and do not need two flags. ``approve`` accepts ``planned``
only and refuses a plan with no lines — approving an empty plan approves nothing, and it would put
the green badge on the one plan on the list that has never been costed. ``archive`` accepts anything
still live, which is what retires a plan without deleting the roster somebody staffed to.

**4.14 writes NO ``StockMove`` and NO ``JournalEntry``** (the standing L29 rule). The generator READS
4.3's append-only ledger, 4.4's pick lines, 4.1's receipt lines or 4.7's forecast periods to derive
volume, and it writes exactly one table: ``LaborPlanLine``. Nothing in this file creates a movement
of stock or an accounting document, and nothing here imports ``apps.hrm`` — the payroll hand-off is
the CSV on ``labor_payroll_export`` and lives nowhere near a foreign key.

**Query hygiene.** The list annotates the grid rollup in ONE grouped aggregate
(:func:`_with_grid_totals`) rather than letting the template touch :meth:`LaborPlan.totals`, which is
an aggregate PER ROW. The detail page paginates the grid — a plan may legitimately hold
``MAX_PLAN_LINES`` (2000) rows and fetching them all to render fifteen is the payload, not the page.
:func:`laborplan_generate` is bounded at **one COUNT, at most eight resolver calls, one volume
aggregate, one DELETE and one ``bulk_create``**, whatever the size of the grid.

--------------------------------------------------------------------------------------------------
Context-var contract (pinned, L7 — the templates are written by a separate agent, so EVERY key each
page consumes is listed here, not merely the list variable):
--------------------------------------------------------------------------------------------------
* ``scm/labor/laborplan/list.html`` — ``object_list`` + ``page_obj`` + ``q`` (from ``crud_list``),
  where every row additionally carries four annotations: ``line_count`` (int), ``required_shifts``
  and ``planned_shifts`` (Decimals — **person-shifts, not headcount**; see
  :meth:`LaborPlan.totals`) and ``shift_gap`` (planned − required, signed). Filter context:
  ``status_choices`` / ``bucket_choices`` / ``volume_source_choices`` / ``method_choices`` (lists of
  ``(value, label)`` pairs) and ``locations`` (a ``Location`` queryset — compare with
  ``l.pk|stringformat:"d"``, NEVER ``|slugify``). Header chips: ``stats``, a dict with keys
  ``draft`` / ``planned`` / ``approved`` / ``archived`` counted over the WHOLE workspace. Filter
  params: ``q`` / ``status`` / ``bucket`` / ``volume_source`` / ``method`` (strings — compare with
  ``request.GET.<param>`` directly), ``location`` (pk) and ``date_from`` / ``date_to`` on
  ``period_start``.
* ``scm/labor/laborplan/form.html`` — ``form``, ``is_edit`` and ``obj`` (``None`` on create).
* ``scm/labor/laborplan/detail.html`` — ``obj``; ``lines`` (the CURRENT PAGE of the grid, each row
  carrying its ``standard``) with ``page_obj`` for ``partials/pagination.html``; ``totals`` (the dict
  :meth:`LaborPlan.totals` returns — ``lines`` / ``required_minutes`` / ``required_shifts`` /
  ``planned_shifts`` / ``shift_gap`` / ``coverage_pct``, the last **``None`` when nothing is
  required**, which must render as an em dash and never as 0%); ``bucket_rows`` (a list of dicts
  ``{"period_start", "required", "planned", "gap", "is_short", "is_over"}``, one per bucket across
  the WHOLE plan — this is the only place a headcount sum means anything, because it is one bucket
  and therefore one day's roster); ``periods`` (int, the plan's span in buckets),
  ``scoped_activity_count`` and ``projected_lines`` (what a Generate press WOULD build),
  ``max_horizon_periods`` / ``max_plan_lines`` (the two bounds, so the UI can state them BEFORE the
  button is pressed); ``history_start`` / ``history_end`` (the derived-volume window, both ``None``
  when the plan has no start date); ``can_edit`` / ``can_delete`` / ``can_generate`` /
  ``can_approve`` / ``can_archive``; and ``generate_blocked_reason`` (``""`` when Generate is
  available — say WHY it is not rather than silently hiding the button, the 4.13
  ``parts_location_missing`` rule).
* ``scm/labor/laborplanline/form.html`` — ``form``, ``is_edit`` (always ``True`` — lines are created
  by the generator and by nothing else), ``obj`` (the line) and ``plan`` (the PARENT: the line form
  has no ``plan`` field, so the breadcrumb and the cancel link can only get it from here).

Badge colours come from the models: ``obj.status_css`` and ``line.activity_css``.
``badge-success`` / ``badge-warning`` / ``badge-danger`` DO NOT EXIST in theme.css (L33).

``laborplan_delete``, ``_generate`` and ``_approve`` are ``@tenant_admin_required``, so wrap those
three buttons in ``{% if request.user.is_superuser or request.user.is_tenant_admin %}`` — showing a
member a button they will 403 on is the 4.11 finding.
"""
from datetime import datetime, time, timedelta

from django.db.models.functions import Abs, Coalesce, TruncDay

from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _date_window, _location_qs, _need_tenant

from apps.scm.forms import LaborPlanForm, LaborPlanLineForm
from apps.scm.models import (
    ACTIVITY_CHOICES,
    DIRECT_ACTIVITIES,
    DemandForecastPeriod,
    GoodsReceiptLine,
    LaborPlan,
    LaborPlanLine,
    LaborStandard,
    Location,
    PLAN_BUCKET_CHOICES,
    PLAN_METHOD_CHOICES,
    PLAN_STATUS_CHOICES,
    PickTaskLine,
    StockMove,
    VOLUME_SOURCE_CHOICES,
    # THE resolver. Most-specific-wins, effective-dated, `None` when nothing matches — and it is
    # imported rather than re-implemented for the reason its own docstring gives: a second copy of
    # the precedence ladder is a second answer to "which standard applies", and the two would
    # disagree the first time a site-specific standard was added.
    select_standard,
)
from apps.scm.models._base import q4

ZERO = Decimal("0")

#: ``activity`` -> label, for the "no standard resolved for X" warning. A Django template cannot look
#: a choice label up from a raw token (``get_FOO_display`` only exists on a model INSTANCE) and
#: neither can a message built from a bare string, so the map is resolved once here — the
#: ``_PROBLEM_LABELS`` precedent in the 4.13 asset view.
_ACTIVITY_LABELS = dict(ACTIVITY_CHOICES)

# =================================================================================== the ladder
#: ``generate`` is the only route into ``planned``, so it is available on both open statuses: a
#: regenerate is the normal case (the volumes moved, the standards were re-timed) and forcing a plan
#: backwards to ``draft`` first would be a status change nobody meant to make.
GENERATABLE_STATUSES = LaborPlan.EDITABLE_STATUSES          # ("draft", "planned")
#: ``planned`` ONLY. A draft has no grid — the generator is what builds it — so approving one would
#: approve an empty document, and the list would carry a green badge on the single plan that has
#: never been costed. The refusal message says "generate it first" rather than merely refusing.
APPROVABLE_STATUSES = ("planned",)
#: Anything still live. Archiving is how a plan is retired WITHOUT losing the roster a site staffed
#: to, which is the whole reason `delete` refuses an approved plan.
ARCHIVABLE_STATUSES = ("draft", "planned", "approved")

# ============================================================== volume: which flow drives which work
#
# Every DIRECT activity is driven by one of three warehouse flows, and the mapping is declared ONCE
# here because the generator branches on it for every line it writes. It is built from the two
# frozensets rather than hand-typed per activity so the partition stays total by construction: an
# activity in neither set falls through to `throughput`, which is a defensible number rather than a
# KeyError or a silent zero.
#
#: Work whose volume is what came IN — ``move_type="receipt"`` on the ledger.
INBOUND_ACTIVITIES = frozenset({"receive", "putaway"})
#: Work whose volume is what went OUT — ``move_type="issue"``. ``replenish`` is here because a pick
#: face is refilled in proportion to what is picked out of it, and ``vas`` because value-added
#: service (kitting, labelling, gift-wrap) is performed on outbound orders.
OUTBOUND_ACTIVITIES = frozenset({"pick", "pack", "load", "replenish", "vas"})
#: The third flow, and the reason it exists: ``cycle_count`` is driven by neither direction alone.
#: Counting workload tracks how much the site MOVES — inventory accuracy decays with every touch,
#: inbound and outbound alike — so it reads both sides added together.
_THROUGHPUT = "throughput"
_FLOWS = ("inbound", "outbound", _THROUGHPUT)

#: The ONLY two move types that are dock work. Every other type in ``StockMove.MOVE_TYPES`` is
#: excluded deliberately, and each for its own reason — this is a whitelist rather than an
#: ``exclude()`` precisely so a type added later is absent until somebody decides it belongs:
#:
#: * ``consumption`` / ``production`` — a work order's raw-material draw and its finished-goods
#:   report. Manufacturing, not receiving or shipping; nobody unloaded a trailer for either.
#: * ``maintenance`` — an MRO spare pulled for a repair. Same argument, and 4.13 gave it its own
#:   type rather than reusing ``issue`` for exactly this class of miscounting.
#: * ``transfer`` — posted as a **−/+ PAIR** across two locations, so counting it would book two
#:   movements for one physical touch and double the volume of every site that puts stock away.
#: * ``adjustment`` — a write-off, a damage, a count correction or a revaluation. A quantity
#:   changing on paper is not a quantity anybody carried.
#:
#: This is the same line 4.7's ``demand_series`` draws when it reads ``move_type="issue"`` alone as
#: customer demand, and the ``StockMove.MOVE_TYPES`` comments argue it at the source.
_WAREHOUSE_MOVE_TYPES = ("receipt", "issue")

#: ``same_period_last_year`` looks back **364 days, not 365**. 364 is 52 whole weeks, so the
#: comparison bucket lands on the same weekday — which matters on both grains: a Monday is not a
#: Saturday's workload on a daily plan, and a weekly bucket offset by one day straddles two weeks.
_ONE_YEAR_DAYS = 364

#: How deep the location scope walks. ``scm.Location`` is a self-referencing tree (site > warehouse >
#: zone > bin), and a plan is written at warehouse or zone level while the LEDGER is written at bin
#: level — so filtering ``location_id=plan.location_id`` exactly would generate a grid of zeroes for
#: a perfectly ordinary plan and read as "this site has no work". The walk is one query per level and
#: is capped here rather than run to exhaustion, because a `parent` cycle (nothing in 4.3 refuses
#: one) would otherwise be an infinite loop inside a POST.
MAX_LOCATION_DEPTH = 6

#: Defensive ceiling on the history walk. ``history_days`` is capped at 730 by its own field
#: validator, so this can only bite on a row written by a migration or a fixture that went around
#: it — and the point is that such a row degrades to a shorter average rather than to a loop nobody
#: bounded (L40: the guard has to be cheaper than the thing it guards).
MAX_HISTORY_BUCKETS = 730

#: Grid rows shown per page on the detail. A plan may hold ``MAX_PLAN_LINES`` (2000) rows and this is
#: a Paginator slice, so the DATABASE applies it: it bounds what is FETCHED, not merely what is
#: rendered (L40 §1 — a guard that first builds the whole thing is the payload, not a guard).
GRID_PAGE_SIZE = 50

#: ``standard_minutes_snapshot`` is ``DecimalField(12, 4)`` — eight integer digits — while
#: :func:`q4` clamps to the app's (14, 4) shape at TEN. So ``q4`` alone is NOT a safe clamp for this
#: column: ``LaborStandard.minutes_for()`` returns a q4 figure, a large forecast volume against a
#: fat per-unit standard genuinely reaches it, and an over-range decimal raises ``DataError`` inside
#: ``bulk_create`` — which fails the WHOLE generated grid rather than the one absurd row. Same
#: reasoning, same shape, as ``LaborPlans.MAX_REQUIRED_MINUTES`` / ``MAX_PLAN_HEADCOUNT`` on the
#: model; those two are applied by ``required_minutes_for()`` / ``headcount_for()`` and this is the
#: one column no model method owns.
MAX_SNAPSHOT_MINUTES = Decimal("99999999.9999")

#: One output shape for the grid rollup on the list, so Django never has to guess how to combine two
#: SUMs of ``DecimalField(8, 2)`` columns with the subtraction between them.
_SHIFTS = models.DecimalField(max_digits=14, decimal_places=2)


# =================================================================================== small helpers
def _detail(pk):
    """The one redirect target every verb in this module answers with."""
    return redirect("scm:laborplan_detail", pk=pk)


def _moment(day, *, end_of_day=False):
    """A date boundary as a tz-AWARE datetime, for a lookup against a ``DateTimeField``.

    ``moved_at`` and ``pick_task__picked_at`` are datetimes; handing them a bare ``date`` under
    ``USE_TZ`` works but Django reads it as UTC and warns, so under any project timezone other than
    UTC the whole volume window silently shifts by the offset — and a shifted window is the kind of
    wrong that reconciles to nothing and looks like nothing. The pair is used HALF-OPEN
    (``>= start``, ``< end_of_day``) rather than as ``__date__range``, because the ``__date`` lookup
    wraps the column in ``CAST(CONVERT_TZ(...))`` and makes ``scm_move_tnt_movedat_idx`` unusable on
    the module's fastest-growing table (4.7's ``_history._moment`` says the same, for the same
    query).
    """
    stamp = datetime.combine(day, time.min) + (timedelta(days=1) if end_of_day else timedelta())
    return timezone.make_aware(stamp) if timezone.is_naive(stamp) else stamp


def _flow_for(activity):
    """Which warehouse flow drives ``activity`` — see :data:`INBOUND_ACTIVITIES`."""
    if activity in INBOUND_ACTIVITIES:
        return "inbound"
    if activity in OUTBOUND_ACTIVITIES:
        return "outbound"
    return _THROUGHPUT


def _location_scope_ids(tenant, location):
    """``{pk}`` of the plan's location and every location beneath it, or ``None`` for the network.

    ``None`` means "do not filter at all" and is returned for a network-wide plan — deliberately
    distinct from an empty set, which would filter on ``IN ()`` and match nothing. Those two answers
    are opposite and conflating them is how a network plan quietly generates a grid of zeroes.

    The walk is breadth-first with a visited set, which does two things: it bounds the query count at
    :data:`MAX_LOCATION_DEPTH` regardless of how the tree is shaped, and it terminates on a
    ``parent`` cycle. 4.3 does not refuse such a cycle anywhere, so "it cannot happen" is a claim
    about data rather than about code, and this is inside a POST.
    """
    if location is None or tenant is None:
        return None
    ids = {location.pk}
    frontier = [location.pk]
    for _ in range(MAX_LOCATION_DEPTH):
        children = list(Location.objects
                        .filter(tenant=tenant, parent_id__in=frontier)
                        .exclude(pk__in=ids)
                        .values_list("pk", flat=True))
        if not children:
            break
        ids.update(children)
        frontier = children
    return ids


def _history_buckets(plan):
    """``[(start, end)]`` of the derived-history window, in BUCKET-SIZED chunks, newest first.

    Chunked to the plan's own bucket length rather than to days, because that is what makes the
    method mean anything: a weekly plan's moving average has to be the mean of weekly totals, and a
    mean of daily totals would understate every bucket by a factor of seven.

    Walked BACKWARDS from the day before the plan opens, so the newest bucket is always whole and
    aligned to the plan's grain. The oldest chunk is DROPPED when the window does not cover it fully
    — a four-day remainder counted as a week is a low outlier that drags the average down, and a
    number that quietly under-staffs a site is worse than one fewer sample.

    The walk is capped at :data:`MAX_HISTORY_BUCKETS`; ``history_days`` is already capped at 730 by
    its field validator, so the cap only bites on a row written around that validator.
    """
    start, end = plan.history_window()
    if start is None or end is None or end < start:
        return []
    step = 1 if plan.bucket == "day" else 7
    out, cursor_end = [], end
    while cursor_end >= start and len(out) < MAX_HISTORY_BUCKETS:
        cursor_start = cursor_end - timedelta(days=step - 1)
        if cursor_start < start:
            break                       # a PARTIAL oldest bucket — dropped, see the docstring
        out.append((cursor_start, cursor_end))
        cursor_end = cursor_start - timedelta(days=1)
    return out


def _daily_series(plan, tenant, window_start, window_end):
    """``{flow: {day: Decimal}}`` of derived volume over ``[window_start, window_end]`` inclusive.

    **Derived at generate time from the live transactions, never from a stored history table** —
    4.7's rule, and the reason a regenerate always reflects what actually happened rather than a
    stale copy of it. Keyed by DAY rather than by bucket because a weekly plan keeps its own
    ``period_start`` weekday (``LaborPlan.period_starts`` deliberately does not snap to Monday), so a
    ``TruncWeek`` here would mis-align every bucket against the volume read for it. Days are folded
    into the plan's own buckets afterwards by :func:`_sum_days`.

    One query per source, whatever the window. The ``stock_moves`` leg groups by ``move_type`` as
    well as by day, so both directions come back from a single aggregate.

    ``pick_tasks`` and ``goods_receipts`` produce ONE series that answers for all three flows, and
    that is the honest reading of the choice rather than a shortcut: picking "pick task history" as
    the volume source says *drive this whole site off order-picking volume*, which is a legitimate
    thing for a pick-dominated operation to plan on, and inventing a second series it did not ask
    for would be the view deciding something the planner already decided.
    """
    empty = {flow: {} for flow in _FLOWS}
    if tenant is None or window_start is None or window_end is None or window_end < window_start:
        return empty
    scope = _location_scope_ids(tenant, plan.location)

    if plan.volume_source == "stock_moves":
        rows = StockMove.objects.filter(
            tenant=tenant, move_type__in=_WAREHOUSE_MOVE_TYPES,
            moved_at__gte=_moment(window_start),
            moved_at__lt=_moment(window_end, end_of_day=True))
        if scope is not None:
            rows = rows.filter(location_id__in=scope)
        # Filters BEFORE .values()/.annotate(): a .filter() after the grouping becomes a HAVING
        # clause on the aggregate, which is not what "only this site" means.
        #
        # Abs() because the ledger is SIGNED — an issue is stored negative. Summing raw quantities
        # would net a busy day's receipts against its issues and report a site that moved ten
        # thousand cartons as having moved none.
        #
        # .order_by() clears StockMove.Meta.ordering, which would otherwise drag `-moved_at` into
        # the GROUP BY and split every day into one row per timestamp.
        rows = (rows.annotate(day=TruncDay("moved_at", output_field=models.DateField()))
                .values("move_type", "day")
                .annotate(total=Sum(Abs("quantity")))
                .order_by())
        inbound, outbound = {}, {}
        for row in rows:
            target = inbound if row["move_type"] == "receipt" else outbound
            target[row["day"]] = (row["total"] or ZERO)
        return {"inbound": inbound, "outbound": outbound,
                _THROUGHPUT: _merge_days(inbound, outbound)}

    if plan.volume_source == "pick_tasks":
        # `picked_at` is stamped when the task is actually picked, so an open or cancelled task
        # contributes nothing — which is right: the plan is sized on work that HAPPENED. Reached
        # through `pick_task__tenant` because PickTaskLine carries no tenant column of its own.
        rows = PickTaskLine.objects.filter(
            pick_task__tenant=tenant,
            pick_task__picked_at__gte=_moment(window_start),
            pick_task__picked_at__lt=_moment(window_end, end_of_day=True))
        if scope is not None:
            rows = rows.filter(from_location_id__in=scope)
        rows = (rows.annotate(day=TruncDay("pick_task__picked_at",
                                           output_field=models.DateField()))
                .values("day").annotate(total=Sum("quantity_picked")).order_by())
        series = {row["day"]: (row["total"] or ZERO) for row in rows}
        return {flow: series for flow in _FLOWS}

    if plan.volume_source == "goods_receipts":
        # `receipt_date` is a DateField, so no _moment() normalisation is owed here — and `range` is
        # inclusive at both ends, which is what a receipt window means to the person who typed it.
        # `status="received"` because a draft GRN is a document somebody is still filling in and a
        # cancelled one is a delivery that never landed; neither is labour anybody performed.
        rows = GoodsReceiptLine.objects.filter(
            goods_receipt__tenant=tenant, goods_receipt__status="received",
            goods_receipt__receipt_date__range=(window_start, window_end))
        if scope is not None:
            rows = rows.filter(goods_receipt__location_id__in=scope)
        rows = (rows.values("goods_receipt__receipt_date")
                .annotate(total=Sum("quantity_received")).order_by())
        series = {row["goods_receipt__receipt_date"]: (row["total"] or ZERO) for row in rows}
        return {flow: series for flow in _FLOWS}

    # `manual` and `demand_forecast` derive nothing from history: the first is the planner typing
    # `planned_headcount` on a brand-new site with no history at all, and the second reads 4.7's
    # forward periods instead (see _forecast_volumes).
    return empty


def _merge_days(left, right):
    """``{day: left + right}`` over the union of both keys — the ``throughput`` flow."""
    out = dict(left)
    for day, value in right.items():
        out[day] = (out.get(day) or ZERO) + value
    return out


def _sum_days(series, start, end):
    """Total of ``series`` over ``[start, end]`` inclusive, walking the RANGE and not the dict.

    Walking the range keeps the cost proportional to the bucket (1 or 7 iterations) instead of to
    the size of the window, and a day the source never wrote is a genuine zero rather than a missing
    key — an absent day is a day nothing moved.
    """
    total, cursor = ZERO, start
    while cursor <= end:
        total += series.get(cursor) or ZERO
        cursor += timedelta(days=1)
    return total


def _forecast_volumes(plan, tenant, buckets):
    """``{bucket_start: Decimal}`` from the linked 4.7 forecast's own periods.

    **4.14 CONSUMES the forecast; it does not re-derive seasonality.** The statistical machinery, the
    seasonality profiles and the consensus adjustments already exist in 4.7 and are somebody else's
    job to be right about, so this reads ``final_quantity`` — the bottom of that waterfall — and does
    no smoothing of its own. The plan's ``method`` and ``history_days`` are therefore **not consulted
    on this source**, because a forecast is already the forward projection those two exist to
    produce; the generate verb says so in a message rather than leaving a planner to wonder why
    changing the method changed nothing.

    The forecast's buckets are its own (day / week / month / quarter) and rarely line up with the
    plan's, so each forecast period is spread EVENLY across the days it covers and the plan bucket
    takes its overlapping share. A 3,000-unit month becomes 100 units a day, which a daily plan reads
    as 100 and a weekly one as 700. Even spreading is a stated assumption rather than a hidden one:
    intra-period shape is what a seasonality profile is for, and 4.7 owns that.

    Both sides are sorted by start, so the inner loop breaks the moment a period opens after this
    bucket closes — the product of two capped horizons is bounded but need not be paid in full.
    """
    forecast = plan.demand_forecast
    if forecast is None or tenant is None or not buckets:
        return {}
    # Defence in depth, and consistency with the sibling read on the 4.13 asset page. There is no
    # HTTP write path that could attach a foreign forecast — `demand_forecast` is in
    # `LaborPlan.TENANT_SCOPED_FKS`, so both the model's clean() and the form's reject a crafted pk
    # — but this page derives a ROSTER from another workspace's numbers, and a row that predates
    # that guard (a fixture, a data migration, a future importer, a direct DB edit) must generate
    # nothing rather than quietly staff a site off somebody else's demand.
    if forecast.tenant_id != tenant.pk:
        return {}

    periods = list(DemandForecastPeriod.objects
                   .filter(forecast_id=forecast.pk, forecast__tenant=tenant)
                   .order_by("period_start")
                   .values_list("period_start", "period_end", "final_quantity"))
    out = {}
    for bucket_start, bucket_end in buckets:
        total = ZERO
        for period_start, period_end, quantity in periods:
            if period_start > bucket_end:
                break                       # sorted — nothing later can overlap this bucket either
            if period_end is None or period_end < period_start or period_end < bucket_start:
                continue
            span = (period_end - period_start).days + 1
            if span <= 0:
                continue
            overlap = (min(bucket_end, period_end) - max(bucket_start, period_start)).days + 1
            if overlap <= 0:
                continue
            total += Decimal(quantity or ZERO) * Decimal(overlap) / Decimal(span)
        out[bucket_start] = total
    return out


def _direct_standards_qs(plan, tenant):
    """The active, in-scope, effective standards a Generate would price this plan from.

    Mirrors :func:`select_standard`'s own filter **token for token**, which is what makes the count
    below an honest prediction rather than a different question asked with similar words:
    ``status="active"``, effective on the plan's opening day, and scoped to this site or to the
    network. The category rungs of the resolver's ladder are unreachable here on purpose — a plan
    has no item category, so a category-scoped standard is never selected for one, and including
    those rows in the scope would count activities the grid will not contain.
    """
    if tenant is None or plan.period_start is None:
        return LaborStandard.objects.none()
    qs = (LaborStandard.objects
          .filter(tenant=tenant, status="active", activity__in=DIRECT_ACTIVITIES,
                  effective_from__lte=plan.period_start)
          .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=plan.period_start)))
    if plan.location_id:
        qs = qs.filter(Q(location_id=plan.location_id) | Q(location__isnull=True))
    else:
        qs = qs.filter(location__isnull=True)
    return qs


def _scoped_activity_count(plan, tenant):
    """How many DISTINCT direct activities a Generate would emit lines for — **one COUNT(\\*)**.

    DISTINCT ON ACTIVITY, not a count of standards, and the difference is the guard working
    correctly rather than approximately. ``LaborPlanLine`` is
    ``unique_together ("plan", "period_start", "activity")``, so the grid is one row per
    (bucket × ACTIVITY) no matter how many standards resolve to each — counting standards would both
    over-refuse a library with several scopes per activity and misdescribe the grid to the planner in
    the refusal message.

    Cheap on purpose: a ceiling check has to cost less than the thing it protects against or it is
    the same problem with an extra step (L40). This is one aggregate against the standards library
    and it runs BEFORE a single row is built.

    ``.order_by()`` is load-bearing and not tidying. ``LaborStandard.Meta.ordering`` is
    ``["activity", "-effective_from", "-id"]``, and Django adds every ordering column to the SELECT
    list of a ``values()`` query — so ``DISTINCT`` would be taken over
    ``(activity, effective_from, id)`` instead of over ``activity``, which is distinct on the
    primary key, i.e. not distinct at all. The count would then be the number of STANDARDS, the
    ceiling guard would refuse plans that fit, and the detail page would quote a projected line count
    the generator never intended to build.
    """
    return _direct_standards_qs(plan, tenant).order_by().values("activity").distinct().count()


def _with_grid_totals(qs):
    """Annotate ``line_count`` / ``required_shifts`` / ``planned_shifts`` / ``shift_gap`` in ONE pass.

    :meth:`LaborPlan.totals` is an aggregate over the child table, which is correct on the detail
    page (once) and is a query PER ROW on a list. One grouped aggregate does the whole page instead.

    Exactly ONE reverse join is added, so nothing here fans the rows out and both SUMs stay honest;
    every filter this page applies afterwards walks a FORWARD FK (``location``), which cannot
    multiply a row.

    The Meta ordering is RESTATED, and it is not redundant: ``QuerySet.ordered`` returns False the
    moment a query has a GROUP BY even though the compiler still emits the Meta ORDER BY, so without
    this ``paginate()`` raises ``UnorderedObjectListWarning`` on every page load of a list that is in
    fact perfectly ordered (the 4.8 finding ``views/_common.py:20-23`` records). The SQL is
    identical; only the property stops lying.

    Coalesce is load-bearing rather than tidy: a plan with no lines annotates ``None``, which would
    blank the column on exactly the plans that most need "0" printed against them — the ones nobody
    has generated yet.
    """
    return qs.annotate(
        line_count=Count("lines"),
        required_shifts=Coalesce(Sum("lines__required_headcount"),
                                 models.Value(ZERO, output_field=_SHIFTS), output_field=_SHIFTS),
        planned_shifts=Coalesce(Sum("lines__planned_headcount"),
                                models.Value(ZERO, output_field=_SHIFTS), output_field=_SHIFTS),
    ).annotate(
        shift_gap=models.ExpressionWrapper(F("planned_shifts") - F("required_shifts"),
                                           output_field=_SHIFTS),
    ).order_by("-period_start", "-id")


def _transition(request, pk, *, from_statuses, to_status, action, verb, stamps=None, audit=None,
                message=None, precheck=None):
    """Guard, stamp, audit, redirect — the shape both plain status verbs in this file share.

    ``action`` and ``verb`` are two different things and both are needed. ``action`` is the SLUG the
    audit row is keyed on (``approve`` / ``archive``), so the trail stays filterable; ``verb`` is the
    past participle the two human sentences read with.

    The row is taken ``FOR UPDATE`` and its status re-read INSIDE ``transaction.atomic()``: two
    concurrent POSTs (a double-click, a retry, a replay) would otherwise both see ``planned`` and
    each stamp ``approved_at``, and the second stamp is the one that survives. The object is resolved
    BEFORE the status guard so a cross-tenant pk answers 404 rather than a 302 that leaks "there is a
    row there, you just cannot move it" (the 4.12 finding).

    ``precheck`` is evaluated INSIDE the lock and never by the caller before it. A guard that reads a
    CHILD table (here: does this plan have any lines?) is a plain snapshot read — run before the lock
    it answers about the state the request started in, and the write then waits for the lock and
    lands the moment the competing transaction commits. That is the 4.13 finding, priced in advance.

    ``save(update_fields=…)`` is narrow on purpose: a full ``save()`` would write back every
    in-memory column, including any a concurrent edit had just changed.
    """
    with transaction.atomic():
        obj = get_object_or_404(LaborPlan.objects.select_for_update(), pk=pk, tenant=request.tenant)
        if obj.status not in from_statuses:
            messages.error(request, f"{obj.number} cannot be {verb} — it is "
                                    f"{obj.get_status_display().lower()}.")
            return _detail(pk)
        if precheck is not None:
            refusal = precheck(obj)
            if refusal:
                messages.error(request, refusal)
                return _detail(pk)

        fields = ["status", "updated_at"]
        obj.status = to_status
        for field, value in (stamps or {}).items():
            setattr(obj, field, value)
            fields.append(field)
        obj.save(update_fields=list(dict.fromkeys(fields)))

    write_audit_log(request.user, obj, "update",
                    {"action": action, "status": to_status, **(audit or {})})
    messages.success(request, message or f"{obj.number} {verb}.")
    return _detail(pk)


# ======================================================================================= the list
@login_required
def laborplan_list(request):
    """Search + five filters + a period window over the workspace's labour plans.

    EVERY filter is applied BEFORE ``crud_list`` paginates. One applied afterwards would page over
    the unfiltered set and quietly show the wrong rows on page 2.

    ``location`` goes through ``crud_list``'s ``is_int=True`` leg, which applies the L11 guard:
    ``?location=abc``, ``?location=²`` (``isdigit()`` says yes, ``int()`` says no) and
    ``?location=99999999999999999999`` (converts fine, then overflows inside the driver) all SKIP the
    filter rather than raise on a URL anybody can type into the address bar. The date window goes
    through the SHARED ``_date_window`` helper — ``period_start`` is a plain ``DateField``, so no
    boundary normalisation is owed and junk input skips the filter for the same reason.

    The grid rollup comes from :func:`_with_grid_totals`, never from ``LaborPlan.totals`` — see there.
    """
    qs = (LaborPlan.objects.filter(tenant=request.tenant)
          .select_related("location", "demand_forecast", "approved_by"))
    qs = _date_window(qs, request.GET, "period_start")
    qs = _with_grid_totals(qs)

    # ONE aggregate for all four chips, over the WHOLE workspace rather than the filtered page: "3
    # plans awaiting approval" is a fact somebody has to act on, and recomputing it per filter would
    # make the number change as you browse.
    stats = LaborPlan.objects.filter(tenant=request.tenant).aggregate(
        draft=Count("id", filter=Q(status="draft")),
        planned=Count("id", filter=Q(status="planned")),
        approved=Count("id", filter=Q(status="approved")),
        archived=Count("id", filter=Q(status="archived")),
    )

    return crud_list(
        request, qs, "scm/labor/laborplan/list.html",
        search_fields=["number", "name", "notes"],
        filters=[("status", "status", False), ("bucket", "bucket", False),
                 ("volume_source", "volume_source", False), ("method", "method", False),
                 ("location", "location_id", True)],
        extra_context={
            # The vocabularies come from `_choices` via the models package's star re-export and NOT
            # from `_meta.get_field(...).choices`: they are the same lists the form renders from, and
            # naming them directly keeps "the filter offers what the column accepts" a fact rather
            # than a coincidence.
            "status_choices": PLAN_STATUS_CHOICES,
            "bucket_choices": PLAN_BUCKET_CHOICES,
            "volume_source_choices": VOLUME_SOURCE_CHOICES,
            "method_choices": PLAN_METHOD_CHOICES,
            # Not narrowed by is_active: a plan written for a site later deactivated is still a row
            # somebody filters for, and hiding the option would make it unfindable.
            "locations": _location_qs(request.tenant),
            "stats": stats,
        },
    )


# ======================================================================================= the CRUD
@login_required
def laborplan_create(request):
    return _laborplan_form(request, instance=None)


@login_required
def laborplan_edit(request, pk):
    """Editable while the plan is ``draft`` or ``planned`` only.

    An approved plan is the roster the site is staffing to and an archived one is history. Editing
    either in place would restate the question after the answer had been agreed — the horizon, the
    volume source and the productivity assumption are precisely what the approval was of — while
    leaving a grid on the page that was derived from the OLD values and now reconciles to nothing.
    Archive it and build the successor instead.
    """
    obj = get_object_or_404(LaborPlan, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and can no "
                                "longer be edited — its grid was derived from the settings as they "
                                "stand. Archive it and build the successor instead.")
        return _detail(pk)
    return _laborplan_form(request, instance=obj)


def _laborplan_form(request, instance):
    """Create and edit share one form path, landing on the DETAIL page rather than the list.

    Hand-rolled instead of ``crud_create`` / ``crud_edit`` for one reason, and it is the 4.7
    ``_demandforecast_form`` reason: those helpers take a static ``success_url`` name and cannot
    redirect to a pk, so a newly created plan would land back on the list — one click away from the
    Generate button that is the entire next step. Hand-rolled means this path owes its own
    ``write_audit_log``, written with ``_changed(form)`` rather than a second copy of the redaction
    list.
    """
    if instance is None and _need_tenant(request):
        return redirect("scm:laborplan_list")
    is_edit = instance is not None
    if request.method == "POST":
        form = LaborPlanForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            # Re-stated rather than trusted to the form's own stamp: the form sets it so that
            # `LaborPlan.clean()`'s cross-tenant guard is live on the create path, and this is what
            # makes it true at save time even if that constructor changes.
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "update" if is_edit else "create", _changed(form))
            messages.success(request, f"{obj.number} saved."
                             + ("" if is_edit else " Press Generate to build the bucket × activity "
                                                   "grid from the standards library."))
            return _detail(obj.pk)
        # No messages.error here: the bound form is re-rendered below with its own field errors, and
        # a banner repeating them is noise that pushes the actual fields off the screen.
    else:
        form = LaborPlanForm(instance=instance, tenant=request.tenant)
    return render(request, "scm/labor/laborplan/form.html",
                  {"form": form, "is_edit": is_edit, "obj": instance})


@login_required
def laborplan_detail(request, pk):
    """The plan header, the paginated bucket × activity grid, and the per-bucket roster rollup.

    **The grid is PAGINATED, not sliced.** A plan may legitimately hold ``MAX_PLAN_LINES`` rows and
    the reviewer has to be able to reach all of them, so this is a real Paginator (bound to
    ``page_obj`` so ``partials/pagination.html`` works unchanged) rather than the truncated panel
    other detail pages use for a "what does it say lately" strip.

    ``totals`` and ``bucket_rows`` are computed over the WHOLE plan and not over the page — a header
    figure that changed as you paged would be worse than no header figure. Both are single grouped
    aggregates; ``bucket_rows`` is bounded by ``MAX_HORIZON_PERIODS`` by construction, because one
    row per bucket is exactly what the plan's own span cap bounds.

    **``bucket_rows`` is the only place a headcount SUM means anything**, and the distinction is the
    reason it exists. Headcount does not add across buckets — two people on Monday and two on Tuesday
    is two people, not four — which is why :meth:`LaborPlan.totals` denominates its plan-wide figures
    in person-SHIFTS. Within ONE bucket the sum across activities *is* a headcount: it is how many
    bodies the site needs that day.

    ``projected_lines`` is what a Generate press WOULD build, computed from the same
    :func:`_scoped_activity_count` the verb's ceiling guard reads, so the number the UI states before
    the button is pressed and the number the refusal quotes afterwards are ONE statement of the rule.
    """
    obj = get_object_or_404(
        LaborPlan.objects.select_related("location", "demand_forecast", "demand_forecast__item",
                                         "approved_by"),
        pk=pk, tenant=request.tenant)

    # `plan__tenant` rather than the related manager alone. The manager is already constrained by
    # `plan`, which implies the tenant — the explicit predicate is the house idiom because the
    # scoping rule for this table has to read the same way in every place it appears, including the
    # places where it is the only thing standing between a pk and another workspace's grid.
    grid = (LaborPlanLine.objects
            .filter(plan_id=obj.pk, plan__tenant=request.tenant)
            .select_related("standard")
            .order_by("period_start", "activity"))
    page_obj = paginate(request, grid, GRID_PAGE_SIZE)

    # ONE grouped query for the whole per-bucket rollup. The gap is computed in Python rather than
    # annotated because these are already aggregates and the arithmetic is three subtractions over a
    # list capped at MAX_HORIZON_PERIODS — a second ExpressionWrapper layer would buy nothing.
    #
    # `.order_by()` BEFORE `.values()` is load-bearing, not tidying. Django folds whatever ordering a
    # queryset carries into the GROUP BY, and `grid` is ordered by (period_start, activity) — so
    # without the clear, this would group by activity as well and return one row per activity per
    # bucket, i.e. exactly the ungrouped grid it is supposed to roll up. Same trap the 4.13
    # `_OPEN_JOB_COUNT` note records.
    bucket_rows = []
    for row in (grid.order_by()
                .values("period_start")
                .annotate(required=Sum("required_headcount"), planned=Sum("planned_headcount"))
                .order_by("period_start")):
        required = row["required"] or ZERO
        planned = row["planned"] or ZERO
        gap = planned - required
        bucket_rows.append({
            "period_start": row["period_start"],
            "required": required,
            "planned": planned,
            "gap": gap,
            "is_short": gap < ZERO,
            "is_over": gap > ZERO,
        })

    periods = obj.period_count()
    activity_count = _scoped_activity_count(obj, request.tenant)
    history_start, history_end = obj.history_window()
    totals = obj.totals()

    # Say WHY Generate is unavailable rather than hiding the button and letting somebody guess — the
    # 4.13 `parts_location_missing` rule. Each branch is the exact refusal laborplan_generate would
    # answer with, so the page and the route cannot disagree about whether the press would work.
    blocked = ""
    if obj.status not in GENERATABLE_STATUSES:
        blocked = (f"{obj.number} is {obj.get_status_display().lower()} — the grid is the roster "
                   "that was approved and is no longer regenerated.")
    elif periods <= 0:
        blocked = "The plan has no period to generate over — set a start and an end date."
    elif periods > LaborPlan.MAX_HORIZON_PERIODS:
        blocked = (f"That period is {periods} {obj.get_bucket_display().lower()} buckets and the "
                   f"maximum is {LaborPlan.MAX_HORIZON_PERIODS}.")
    elif activity_count == 0:
        blocked = ("No active labour standard covers this scope for any direct activity on "
                   f"{obj.period_start:%d %b %Y} — a plan is priced from the standards library, so "
                   "there is nothing to price it with yet.")
    elif periods * activity_count > LaborPlan.MAX_PLAN_LINES:
        blocked = (f"That would build {periods * activity_count} lines and the maximum is "
                   f"{LaborPlan.MAX_PLAN_LINES}.")

    return render(request, "scm/labor/laborplan/detail.html", {
        "obj": obj,
        "lines": page_obj.object_list,
        "page_obj": page_obj,
        # coverage_pct inside is None — never 0 — when nothing is required. A plan whose grid has not
        # been generated is UNANSWERED, and a confident 0% would read as catastrophically
        # understaffed on the emptiest page in the module (the 4.11 lesson).
        "totals": totals,
        "bucket_rows": bucket_rows,
        "periods": periods,
        "scoped_activity_count": activity_count,
        "projected_lines": periods * activity_count,
        "max_horizon_periods": LaborPlan.MAX_HORIZON_PERIODS,
        "max_plan_lines": LaborPlan.MAX_PLAN_LINES,
        # Both None when the plan has no start date yet — print an em dash, not today's date.
        "history_start": history_start,
        "history_end": history_end,
        "can_edit": obj.is_editable,
        # Exactly the condition laborplan_delete enforces — offering a one-click failure is worse
        # than not offering the button (the 4.12 rule).
        "can_delete": obj.is_editable,
        "can_generate": not blocked,
        "generate_blocked_reason": blocked,
        # Mirrors the verb's own precheck: a plan with no lines is not approvable.
        "can_approve": obj.status in APPROVABLE_STATUSES and (totals["lines"] or 0) > 0,
        "can_archive": obj.status in ARCHIVABLE_STATUSES,
    })


@tenant_admin_required
@require_POST
def laborplan_delete(request, pk):
    """Delete a plan — refused once it is approved or archived.

    An approved plan is the roster a site staffed to and an archived one is the record of a staffing
    decision somebody made; losing either must not be one click away, and ``archive`` exists
    precisely so that retiring a plan never means destroying it.

    Hand-rolled rather than delegated to ``crud_delete``, and the reason is the whole point of this
    view: ``crud_delete`` re-fetches the row by pk WITHOUT a lock and re-checks no guard it was never
    told about, so the status refusal below would be advisory — read from an unlocked snapshot it
    answers about the state this request started in, and the DELETE then waits on the lock and
    executes anyway, against a plan approved in the gap (the 4.13 finding).

    ``LaborPlanLine.plan`` is ``CASCADE``, so the entire generated grid goes with the header. That is
    said out loud, with the count, and only after the delete actually succeeded.
    """
    with transaction.atomic():
        obj = get_object_or_404(LaborPlan.objects.select_for_update(), pk=pk, tenant=request.tenant)
        if not obj.is_editable:
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} and cannot "
                                    "be deleted — an approved plan is the roster a site staffed to. "
                                    "Archive it instead; an archived plan stays readable.")
            return _detail(pk)
        # Counted BEFORE the delete, while the rows still exist to be counted.
        lines = obj.lines.count()
        number = obj.number
        # Inside the transaction so the audit row rolls back with a failed delete rather than
        # recording a deletion that did not happen.
        write_audit_log(request.user, obj, "delete", {"lines": lines})
        obj.delete()

    messages.success(request, f"{number} deleted"
                              + (f", and {lines} generated plan line(s) with it." if lines else "."))
    return redirect("scm:laborplan_list")


# ================================================================================== the generator
@tenant_admin_required
@require_POST
def laborplan_generate(request, pk):
    """Build (or rebuild) the bucket × activity grid from the live transactions. **The hard one.**

    Six steps, all inside ONE locked transaction:

    1. **The span, by INTEGER ARITHMETIC on the two dates** — :meth:`LaborPlan.period_count`, never
       ``len(period_starts())``. Building the range in order to discover the range is too big is
       precisely the allocation the check exists to prevent (L40).
    2. **The ceiling, as ONE ``COUNT(*)`` before a single row is built.** ``periods × activities``
       against ``MAX_PLAN_LINES``, with BOTH numbers in the refusal so the planner is told how far
       past the line they are rather than merely that they are past it. A guard that has to build the
       grid before it can measure it is the payload, not a guard.
    3. **Volume derived AT GENERATE TIME from the chosen source**, never from a stored history table
       (4.7's rule) — see :func:`_daily_series` and :func:`_forecast_volumes`. ``consumption``,
       ``production`` and ``maintenance`` moves are deliberately EXCLUDED: they are manufacturing and
       MRO draws, not warehouse in/out work.
    4. **One ``bulk_create`` after deleting this plan's previous generation**, so a regenerate is
       idempotent rather than a ``unique_together`` collision. Each line snapshots the ``standard``
       it was priced from AND that standard's minutes at the time — the glass box: ``forecast_volume
       → standard_minutes_snapshot → required_minutes → required_headcount`` multiplies out on the
       page and still reconciles months after somebody re-times the standard.
    5. **The arithmetic lives on the MODEL**, not here. ``required_minutes_for()`` applies the
       productivity divisor and ``headcount_for()`` divides by the shift, which composes to
       ``minutes / 60 / hours_per_shift / (productivity_pct / 100)`` — the same formula, expressed
       once, so the seeder and any future recompute cannot carry a slightly different version of it.
    6. ``generated_at`` stamped, ``status`` moved to ``planned``, one audit row.

    **``select_standard`` is called once per ACTIVITY, not once per line.** At most eight calls
    (there are eight direct activities) instead of up to 2000, and the standard in force on the
    plan's OPENING day prices the whole plan — frozen in the snapshot. A standard re-timed mid-period
    therefore does not silently restate part of the grid; it is picked up by the next regenerate,
    which is a decision somebody makes rather than one that happens to them.

    An activity in scope for which the resolver answers ``None`` is SKIPPED and named in a warning,
    never written as a zero line. ``None`` says nobody has measured this work; a zero required
    headcount says the work needs nobody, and printing the second when the first is true puts a green
    chip on the activity that is actually unpriced (the ``select_standard`` contract, verbatim).

    The row is locked for the whole of it, so a double-click cannot double-generate: the second POST
    waits, then finds a plan whose previous generation the first one has already replaced, and
    replaces it again with an identical grid rather than doubling it.
    """
    tenant = request.tenant
    with transaction.atomic():
        obj = get_object_or_404(
            LaborPlan.objects.select_for_update().select_related("location", "demand_forecast"),
            pk=pk, tenant=tenant)
        if obj.status not in GENERATABLE_STATUSES:
            messages.error(request, f"{obj.number} is {obj.get_status_display().lower()} — its grid "
                                    "is the roster that was approved and is no longer regenerated. "
                                    "Build a successor plan instead.")
            return _detail(pk)

        # --- 1. the span, arithmetically ----------------------------------------------------------
        periods = obj.period_count()
        if periods <= 0:
            messages.error(request, f"{obj.number} has no period to generate over — set a start and "
                                    "an end date, with the end on or after the start.")
            return _detail(pk)
        # Re-checked here even though `LaborPlan.clean()` owns the bound, because generate is also
        # reachable on rows written by a seeder, a fixture or a data migration that never called it.
        if periods > LaborPlan.MAX_HORIZON_PERIODS:
            messages.error(request, f"{obj.number} spans {periods} "
                                    f"{obj.get_bucket_display().lower()} buckets and the maximum is "
                                    f"{LaborPlan.MAX_HORIZON_PERIODS}. Use a weekly bucket or "
                                    "shorten the period.")
            return _detail(pk)

        # --- 2. the ceiling, one COUNT(*), before anything is allocated ---------------------------
        activity_count = _scoped_activity_count(obj, tenant)
        if activity_count == 0:
            # Refused BEFORE the delete below, deliberately: a regenerate that found no standards
            # must not silently wipe the grid the last one produced.
            messages.error(request, "No active labour standard covers this scope for any direct "
                                    f"activity on {obj.period_start:%d %b %Y}. A plan is priced from "
                                    "the standards library — add and activate a standard for the "
                                    "site (or network-wide) first.")
            return _detail(pk)
        projected = periods * activity_count
        if projected > LaborPlan.MAX_PLAN_LINES:
            messages.error(request, f"{obj.number} would generate {projected} plan lines — "
                                    f"{periods} {obj.get_bucket_display().lower()} bucket(s) × "
                                    f"{activity_count} direct activity(ies) with an active standard "
                                    f"— and the maximum is {LaborPlan.MAX_PLAN_LINES}. Use a weekly "
                                    "bucket, shorten the period, or scope the plan to one site.")
            return _detail(pk)

        # --- 3. the volume, derived now ------------------------------------------------------------
        # `period_starts()` caps its own walk at MAX_HORIZON_PERIODS, which is belt-and-braces behind
        # the check above: this is the call that turns a span into DB rows.
        starts = obj.period_starts()
        buckets = [(start, obj.bucket_end(start)) for start in starts]

        forecast_map, series, history = {}, {}, []
        if obj.volume_source == "demand_forecast":
            forecast_map = _forecast_volumes(obj, tenant, buckets)
        elif obj.volume_source != "manual" and obj.method != "manual":
            if obj.method == "same_period_last_year":
                # A DIFFERENT window from history_window(): this method reads the same calendar
                # position one year back, which lies inside the plan's own dates shifted, not inside
                # the trailing history the other two methods average.
                window_start = obj.period_start - timedelta(days=_ONE_YEAR_DAYS)
                window_end = obj.period_end - timedelta(days=_ONE_YEAR_DAYS)
            else:
                window_start, window_end = obj.history_window()
                history = _history_buckets(obj)
            series = _daily_series(obj, tenant, window_start, window_end)

        # --- 4/5. one line per (bucket × activity), priced through the MODEL ----------------------
        # `.order_by()` before `.distinct()` for the reason `_scoped_activity_count` sets out: the
        # model's Meta ordering would otherwise be added to the SELECT list and the DISTINCT would be
        # taken over (activity, effective_from, id) — one entry per STANDARD, which would ask the
        # resolver the same question several times and build the grid from a count the guard above
        # never agreed to.
        activities = sorted(_direct_standards_qs(obj, tenant)
                            .order_by().values_list("activity", flat=True).distinct())
        standards, unpriced = {}, []
        for activity in activities:
            standard = select_standard(tenant, activity, location=obj.location,
                                       on_date=obj.period_start)
            if standard is None:
                # Reachable when the only rows for this activity are item-category scoped: a plan has
                # no category, so the resolver's category rungs are unreachable from here.
                unpriced.append(activity)
                continue
            standards[activity] = standard

        # Refused BEFORE the delete below, for the same reason the zero-activity check above is: a
        # regenerate that resolved nothing must not silently wipe the grid the last one produced and
        # leave an EMPTY plan sitting in `planned`, which reads as a costed plan needing nobody.
        # Reachable when every in-scope standard for every direct activity is item-category scoped —
        # a plan has no category, so the resolver's category rungs cannot be walked from here.
        if not standards:
            labels = ", ".join(_ACTIVITY_LABELS.get(a, a) for a in unpriced)
            messages.error(request, "Every active standard for this scope is scoped to an item "
                                    f"category ({labels}), and a plan has no item category — so "
                                    "none of them can be selected for it. Add a site-wide or "
                                    "network-wide standard for the activities you want planned.")
            return _detail(pk)

        rows = []
        for bucket_start, bucket_end in buckets:
            for activity, standard in standards.items():
                if obj.volume_source == "demand_forecast":
                    volume = forecast_map.get(bucket_start) or ZERO
                elif series:
                    volume = _bucket_volume(obj, series, _flow_for(activity),
                                            bucket_start, bucket_end, history)
                else:
                    # `manual` on either axis: no derived volume at all, and the planner types
                    # `planned_headcount` on each line. Zero here is the TRUTH about what was
                    # derived, not a failed derivation.
                    volume = ZERO
                volume = q4(volume)
                # THE CLAMP. `minutes_for()` returns a q4 figure clamped to the app's (14, 4) shape,
                # which is two integer digits WIDER than this column — and an over-range decimal
                # raises DataError inside bulk_create, failing the whole grid rather than the one
                # absurd row. See MAX_SNAPSHOT_MINUTES.
                snapshot = min(standard.minutes_for(volume), MAX_SNAPSHOT_MINUTES)
                required_minutes = obj.required_minutes_for(snapshot)
                rows.append(LaborPlanLine(
                    plan=obj,
                    period_start=bucket_start,
                    activity=activity,
                    forecast_volume=volume,
                    standard=standard,
                    standard_minutes_snapshot=snapshot,
                    required_minutes=required_minutes,
                    required_headcount=obj.headcount_for(required_minutes),
                ))

        # --- 4. idempotent regenerate --------------------------------------------------------------
        # DELETE then bulk_create, both inside the lock. The unique_together on
        # (plan, period_start, activity) is enforced in the DATABASE, so an insert-over-the-top would
        # be an IntegrityError rather than an update — and this way a regenerate that narrows the
        # period does not leave orphan buckets outside it, quietly inflating every plan-wide total.
        #
        # `planned_headcount` and `notes` do NOT survive a regenerate, and that is deliberate rather
        # than an omission: a roster typed against last week's required figures is not an answer to
        # this week's question, and silently carrying it forward would leave a planner staring at a
        # coverage percentage nobody computed.
        removed = obj.lines.count()
        obj.lines.all().delete()
        LaborPlanLine.objects.bulk_create(rows, batch_size=500)

        obj.generated_at = timezone.now()
        obj.status = "planned"
        obj.save(update_fields=["generated_at", "status", "updated_at"])

    write_audit_log(request.user, obj, "update", {
        "action": "generate", "status": "planned", "lines": len(rows), "replaced": removed,
        "periods": periods, "activities": sorted(standards), "unpriced": unpriced or None,
        "volume_source": obj.volume_source, "method": obj.method})

    messages.success(request, f"Generated {len(rows)} plan line(s) for {obj.number} — {periods} "
                              f"{obj.get_bucket_display().lower()} bucket(s) × {len(standards)} "
                              f"direct activity(ies), priced from "
                              f"{obj.get_volume_source_display().lower()}."
                              + (f" The previous {removed} line(s) were replaced." if removed
                                 else ""))
    if unpriced:
        labels = ", ".join(_ACTIVITY_LABELS.get(a, a) for a in unpriced)
        messages.warning(request, f"No standard resolved for {labels} at this site, so no line was "
                                  "written for it. An activity nobody has measured has no minutes to "
                                  "plan with — a zero line would have read as work needing nobody.")
    if obj.volume_source == "demand_forecast":
        messages.info(request, f"Volume came from {obj.demand_forecast or 'the linked forecast'}, "
                               "spread evenly across the days each of its periods covers. A forecast "
                               "is already the forward projection, so this plan's method and history "
                               "window were not consulted.")
    elif obj.volume_source == "manual" or obj.method == "manual":
        messages.info(request, "This plan derives no volume, so every line's required headcount is "
                               "zero by construction — type the roster into each line's planned "
                               "headcount.")
    return _detail(pk)


def _bucket_volume(plan, series, flow, bucket_start, bucket_end, history):
    """One bucket's expected volume from the derived daily series, under the plan's method.

    * ``naive`` — the MOST RECENT whole history bucket, repeated. The honest choice for a site with
      no seasonality and a short memory: what we did last week is what we will do next week.
    * ``moving_average`` — the mean across every whole history bucket. Buckets are the plan's own
      length (see :func:`_history_buckets`), so a weekly plan averages weekly totals.
    * ``same_period_last_year`` — the actual figure from the same calendar position 52 weeks back,
      read from a window that is the plan's own dates shifted rather than from trailing history.
    * ``manual`` — never reaches here; the caller answers zero.

    Every branch answers ``ZERO`` rather than ``None`` when there is no history to read, and that is
    correct for this figure specifically: an empty ledger for a period genuinely means no volume was
    recorded, which is a measurement and not an unanswered question. The ``None``-not-zero rule
    applies to RATIOS (coverage, performance) whose denominator is missing — see
    ``LaborPlanLine.coverage_pct``.
    """
    days = series.get(flow) or {}
    if not days:
        return ZERO
    if plan.method == "same_period_last_year":
        return _sum_days(days, bucket_start - timedelta(days=_ONE_YEAR_DAYS),
                         bucket_end - timedelta(days=_ONE_YEAR_DAYS))
    if not history:
        return ZERO
    if plan.method == "naive":
        newest_start, newest_end = history[0]
        return _sum_days(days, newest_start, newest_end)
    total = ZERO
    for start, end in history:
        total += _sum_days(days, start, end)
    return total / Decimal(len(history))


# ============================================================== the ladder (no stock effect below)
def _empty_grid_refusal(obj):
    """The one sentence that refuses approving a plan with no lines, or ``""``.

    Passed to :func:`_transition` as a ``precheck`` so it is evaluated INSIDE the row lock. Read by
    the caller beforehand it would be advisory: a concurrent delete-and-regenerate committing in the
    gap would let the approval land on a grid that no longer exists.

    Exists-shaped, not a Count — the question is only "are there any?" (``views/_common.py:20-23``).
    """
    if not obj.lines.exists():
        return (f"{obj.number} has no plan lines yet, so there is nothing to approve. Press Generate "
                "to build the grid from the standards library first — approving an empty plan is "
                "approving nothing.")
    return ""


@tenant_admin_required
@require_POST
def laborplan_approve(request, pk):
    """planned -> approved. Admin-gated: this is the roster the site will be staffed to.

    ``approved_by`` and ``approved_at`` are stamped HERE and are ``editable=False`` and off the form
    (L22), so "who signed this off and when" is a fact about the press of this button rather than two
    values somebody could type. The plan also stops being editable at this point — that is what makes
    the approval mean something.
    """
    return _transition(request, pk, from_statuses=APPROVABLE_STATUSES, to_status="approved",
                       action="approve", verb="approved", precheck=_empty_grid_refusal,
                       stamps={"approved_by": request.user, "approved_at": timezone.now()})


@login_required
@require_POST
def laborplan_archive(request, pk):
    """draft | planned | approved -> archived. Retire a plan WITHOUT destroying it.

    Deliberately ``@login_required`` and not admin-gated, unlike delete: archiving is the safe move
    — every line, every snapshot and the approval stamp survive, and the plan simply stops being one
    of the live ones. That asymmetry is the point of having both verbs. Refusing to archive would
    only push a planner towards asking an administrator to delete instead, which is the outcome the
    whole status vocabulary exists to avoid.
    """
    return _transition(request, pk, from_statuses=ARCHIVABLE_STATUSES, to_status="archived",
                       action="archive", verb="archived")


# ==================================================================================== the plan line
@login_required
def laborplanline_edit(request, pk):
    """Set one bucket's rostered headcount. **Two fields, and the parent decides whether at all.**

    ``LaborPlanLine`` carries **no ``tenant`` column** — it is a pure child of one plan (the
    ``MaintenancePlanTask`` / ``AssetSparePart`` precedent) — so it is resolved through
    ``plan__tenant=request.tenant`` and never on its own pk. A bare pk lookup here would be a
    cross-tenant write, and it is the dangerous kind: nothing about the response would look wrong, so
    no query anybody runs afterwards would ever reveal that it happened. A tenant-less user
    (``request.tenant`` is ``None``) resolves to ``plan__tenant IS NULL`` against a NOT NULL column
    and gets a 404, which is the right answer rather than a lucky one.

    Hand-rolled rather than ``crud_edit`` for a mechanical reason the form's own docstring records:
    that helper resolves its object with ``get_object_or_404(model, pk=pk, tenant=request.tenant)``,
    and a model without a ``tenant`` column raises ``FieldError`` — a 500. Hand-rolled means this
    path owes its own ``write_audit_log``, and it must pass ``tenant=`` explicitly because
    ``write_audit_log`` reads ``obj.tenant`` and this child has none — without it the row would be
    filed under the USER's workspace by fallback, which for a superuser is no workspace at all.

    The route hangs off the LINE's own pk rather than nesting under the plan (the
    ``compliance-checks/`` rationale): a child pk already identifies its parent, and nesting would
    invite a caller to pair a real child with somebody else's parent id.

    Refused once the parent is approved or archived. ``planned_headcount`` IS the roster, so editing
    it on an approved plan changes the very thing the approval was of — which is a new plan, not an
    edit.
    """
    obj = get_object_or_404(
        LaborPlanLine.objects.select_related("plan", "plan__location", "standard"),
        pk=pk, plan__tenant=request.tenant)
    plan = obj.plan
    if not plan.is_editable:
        messages.error(request, f"{plan.number} is {plan.get_status_display().lower()} — its planned "
                                "headcount is the roster that was signed off and can no longer be "
                                "changed here.")
        return _detail(plan.pk)

    if request.method == "POST":
        form = LaborPlanLineForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            line = form.save()
            write_audit_log(request.user, line, "update", {
                "plan": plan.number, "period_start": str(line.period_start),
                "activity": line.activity, **_changed(form)}, tenant=request.tenant)
            messages.success(request, f"{line.get_activity_display()} on "
                                      f"{line.period_start:%d %b %Y} now rosters "
                                      f"{line.planned_headcount} against {line.required_headcount} "
                                      "required.")
            return _detail(plan.pk)
        # Re-rendered below with the form's own field errors — a banner repeating them is noise.
    else:
        form = LaborPlanLineForm(instance=obj, tenant=request.tenant)

    return render(request, "scm/labor/laborplanline/form.html", {
        "form": form,
        # Always True: lines are created by `laborplan_generate`'s bulk_create and by nothing else,
        # so there is no create path through this form (the form's docstring says so too).
        "is_edit": True,
        "obj": obj,
        # The form has no `plan` field, so the breadcrumb, the cancel link and the read-only
        # derived figures beside the two inputs can only get the parent from here.
        "plan": plan,
    })
