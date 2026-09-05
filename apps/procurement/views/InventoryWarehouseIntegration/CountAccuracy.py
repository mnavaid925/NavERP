"""Procurement 6.18 Inventory & Warehouse Integration — the Count Accuracy read-out.

**Cycle Count Integration** bullet. One read-only page over counting, which is already fully built
elsewhere: SCM 4.4 owns ``CycleCountTask`` / ``CycleCountTaskLine``, and Module 5.11 owns
``CountProgram`` and ``PhysicalInventory``. This page **counts nothing and reconciles nothing** —
it reads what those did and tells a buyer what it means for the data they order against.

**Nothing here is stored.** No model, no form, no migration, no write of any kind. Every figure is
a live grouped aggregate over data owned elsewhere (L36).

--------------------------------------------------------------------------------------------------
The aggregation trap
--------------------------------------------------------------------------------------------------

``CycleCountTaskLine.variance`` is a **Python property** (``CycleCountTasks.py:108``). It cannot be
put in a ``Sum()``, a ``filter()`` or an ``order_by()`` — the ORM does not see it, and reaching for
it row by row would be an N+1 across every count line in the window. Every variance figure here is
therefore built from the underlying COLUMNS:

* net variance  = ``Sum(counted_quantity) − Sum(expected_quantity)`` (the two sums are annotated
  separately and subtracted in Python, so the arithmetic is visible rather than buried in an
  expression);
* absolute variance = ``Sum(Abs(counted_quantity − expected_quantity))`` — a database expression,
  because an over-count and an under-count of the same size must not cancel each other out the way
  they legitimately do in the NET figure;
* variance line count = a conditional ``Count`` over the same two columns.

**Uncounted lines are excluded from every accuracy figure.** ``counted_quantity`` is nullable and
null means "not counted yet", not "counted zero". Including those lines would let a freshly
scheduled task drag the accuracy percentage down as though the warehouse had lost the stock.

--------------------------------------------------------------------------------------------------
Shape
--------------------------------------------------------------------------------------------------

* Fixed query count: one aggregate for the task strip, one for the line strip, one grouped query
  for the item roll-up, one for the location roll-up, one for the programme schedule, and one
  location fetch shared by the dropdown and the roll-up's paths. Nothing aggregates inside a loop,
  so doubling the count volume does not add a query.
* ``ROW_CAP`` bounds the two roll-ups and ``truncated`` says so — the ranking is worst-first, so a
  capped page still shows the rows that matter, and it does not pretend to be complete.
* Every url is ``reverse()``d in Python, never in the template.
* ``request.tenant is None`` renders an empty read-out, never a 500; junk GET params (including an
  unparseable date) narrow nothing and return 200.

**The limitation this page must not paper over** is :data:`ATTRIBUTION_NOTE`.
"""
from datetime import date as _date, timedelta

from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import Abs, Coalesce
from django.urls import reverse
from django.utils import timezone

from apps.core.crud import as_db_int
from apps.inventory.models import CountProgram
from apps.scm.models import CycleCountTask, CycleCountTaskLine, Item, Location

from apps.procurement.models._base import ZERO
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE = "procurement/inventorywarehouse/count_accuracy.html"

#: Hard ceiling on each roll-up table, surfaced as ``row_cap`` with ``truncated``.
ROW_CAP = 500

#: The ``?window=`` vocabulary, in days. Frozen here because the template compares
#: ``selected_window`` against these exact values. An explicit ``date_from``/``date_to`` pair
#: overrides the window — a named window is a shortcut, not a cage.
WINDOW_CHOICES = [
    ("30", "Last 30 days"),
    ("90", "Last 90 days"),
    ("180", "Last 180 days"),
    ("365", "Last 12 months"),
]
_WINDOW_VALUES = {value for value, _label in WINDOW_CHOICES}
_DEFAULT_WINDOW = "90"

#: Quantity × cost needs a wider field than either operand: 16,4 × 14,4 cannot be held by a 16,4.
_VALUE_FIELD = DecimalField(max_digits=28, decimal_places=4)
_QTY_FIELD = DecimalField(max_digits=20, decimal_places=4)

#: An item counts as a repeat offender at this many DISTINCT tasks with a variance. Two is the
#: threshold on purpose: one bad count is an incident, the same item twice is a process problem —
#: which is the whole point of ranking it.
_REPEAT_OFFENDER_TASKS = 2

#: Location accuracy → theme.css colour-named badges (L33). 98% is the usual cycle-count target;
#: below 95% is the band a warehouse manager is expected to act on.
_ACCURACY_BANDS = ((98, "badge-green"), (95, "badge-amber"))

#: The limitation this page states out loud instead of implying a capability it lacks. Verbatim on
#: the page.
ATTRIBUTION_NOTE = (
    "This page reports WHAT the variance was, never WHY. Root-cause attribution — receiving error, "
    "putaway error, picking error, supplier shortage, damage, data entry, shrinkage — is not "
    "recorded anywhere in NavERP today: a count line stores an expected quantity and a counted "
    "quantity and nothing else, so any cause shown here would be invented. That matters most for "
    "the obvious next step: a count variance is NOT evidence against a supplier, and feeding these "
    "figures into a supplier scorecard belongs to 6.16 Supplier Performance, which owns the "
    "scorecard and the evidence rules for it. Read the rankings below as 'where to go look', not "
    "as 'who is at fault'."
)

#: A counted line whose count disagrees with the book figure. Defined ONCE and reused by every
#: aggregate on the page, so the item table, the location table and the summary strip can never
#: draw the variance line differently.
_COUNTED = Q(counted_quantity__isnull=False)
_HAS_VARIANCE = _COUNTED & ~Q(counted_quantity=F("expected_quantity"))

#: The two sums the contract pins, plus the absolute and value figures that a net sum cannot give.
_ROLLUP_ANNOTATIONS = {
    "count_lines": Count("pk", filter=_COUNTED),
    "variance_lines": Count("pk", filter=_HAS_VARIANCE),
    # Sum(counted) and Sum(expected) are annotated SEPARATELY and subtracted in Python: the
    # contract pins that arithmetic, and `.variance` — being a Python property — is unavailable to
    # the ORM either way.
    "counted_sum": Coalesce(Sum("counted_quantity", filter=_COUNTED), Value(ZERO),
                            output_field=_QTY_FIELD),
    "expected_sum": Coalesce(Sum("expected_quantity", filter=_COUNTED), Value(ZERO),
                             output_field=_QTY_FIELD),
    # Absolute, NOT net: a +5 and a −5 are two errors, not zero errors.
    "abs_sum": Coalesce(
        Sum(Abs(F("counted_quantity") - F("expected_quantity")), filter=_COUNTED,
            output_field=_QTY_FIELD),
        Value(ZERO), output_field=_QTY_FIELD),
    "value_sum": Coalesce(
        Sum(Abs(F("counted_quantity") - F("expected_quantity")) * F("item__average_cost"),
            filter=_COUNTED, output_field=_VALUE_FIELD),
        Value(ZERO), output_field=_VALUE_FIELD),
}


def _accuracy_pct(count_lines, variance_lines):
    """Share of counted lines that agreed with the book, as a percentage.

    No counted lines means "not measured": ``None``, so the template prints a dash rather than a
    perfect 100% earned by counting nothing.
    """
    if not count_lines:
        return None
    return (count_lines - variance_lines) * 100 / count_lines


def _accuracy_css(accuracy_pct):
    """Badge for an accuracy percentage. Unmeasured is muted, never green."""
    if accuracy_pct is None:
        return "badge-muted"
    for threshold, css in _ACCURACY_BANDS:
        if accuracy_pct >= threshold:
            return css
    return "badge-red"


def _as_date(raw):
    """A ``YYYY-MM-DD`` GET value as a date, or ``None``. Junk narrows nothing and never raises."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return _date.fromisoformat(raw)
    except ValueError:
        return None


@login_required
def count_accuracy(request):
    """Counting accuracy over a window, ranked by item and by location. Derived on read."""
    tenant = request.tenant
    today = timezone.localdate()

    selected_window = (request.GET.get("window") or "").strip()
    if selected_window not in _WINDOW_VALUES:
        selected_window = _DEFAULT_WINDOW
    location_id = as_db_int(request.GET.get("location"))
    date_from = _as_date(request.GET.get("date_from"))
    date_to = _as_date(request.GET.get("date_to"))
    # An explicit date wins on the side it is given; the named window supplies whichever side was
    # left blank, so the window is a shortcut rather than a cage AND the pair is always closed.
    #
    # **Half-filled is the ordinary case, not a hand-edited URL.** The filter bar renders two
    # INDEPENDENT ``<input type="date">`` boxes, so clearing one and pressing Apply submits
    # ``date_to=`` — and ``scheduled_date__lte=None`` is ``ValueError: Cannot use None as a query
    # value``, i.e. a 500 off the filter bar. Resolving the missing half rather than dropping the
    # bound also keeps the prose beneath the form ("Counts scheduled between X and Y") true: it
    # prints both dates unconditionally and would otherwise print a blank.
    #
    # The window is a LENGTH, so it is applied in whichever direction is missing: given a start,
    # the window ends it; given an end, the window starts it; given neither, it is the N days
    # ending today. That is also what makes the dropdown live — with a start date typed in, a
    # window that only ever resolved to "today" would change nothing.
    window = timedelta(days=int(selected_window))
    if date_to is None:
        date_to = (date_from + window) if date_from is not None else today
    if date_from is None:
        date_from = date_to - window

    stats = {
        "tasks_total": 0, "tasks_scheduled": 0, "tasks_counted": 0,
        "tasks_reconciled": 0, "tasks_cancelled": 0,
        "lines_counted": 0, "lines_with_variance": 0, "variance_rate_pct": None,
        "net_variance_qty": ZERO, "abs_variance_qty": ZERO, "variance_value": ZERO,
        "accuracy_pct": None,
    }
    locations = Location.objects.none()
    selected_location = None
    item_rows, location_rows, program_rows = [], [], []
    truncated = False

    if tenant is not None:
        # ONE query, shared by the filter dropdown and the location roll-up's paths. The bounded
        # `select_related` chain lets `Location.path()` — the ONE definition of a readable location
        # path — run without a query per ancestry hop on a warehouse › zone › bin hierarchy.
        location_map = {obj.pk: obj for obj in
                        Location.objects.filter(tenant=tenant)
                        .select_related("parent__parent__parent")
                        .order_by("code")}
        locations = list(location_map.values())
        if location_id is not None:
            selected_location = location_map.get(location_id)

        task_filter = Q(tenant=tenant, scheduled_date__gte=date_from, scheduled_date__lte=date_to)
        if selected_location is not None:
            task_filter &= Q(location_id=selected_location.pk)

        # --- ONE aggregate for the whole task strip -----------------------------------------
        task_stats = CycleCountTask.objects.filter(task_filter).aggregate(
            total=Count("pk"),
            scheduled=Count("pk", filter=Q(status__in=("scheduled", "in_progress"))),
            counted=Count("pk", filter=Q(status="counted")),
            reconciled=Count("pk", filter=Q(status="reconciled")),
            cancelled=Count("pk", filter=Q(status="cancelled")))
        stats.update(
            tasks_total=task_stats["total"] or 0,
            tasks_scheduled=task_stats["scheduled"] or 0,
            tasks_counted=task_stats["counted"] or 0,
            tasks_reconciled=task_stats["reconciled"] or 0,
            tasks_cancelled=task_stats["cancelled"] or 0)

        # Lines of the tasks in the window. Cancelled tasks are excluded: a count that was called
        # off measured nothing, and letting it score would punish the warehouse for a scheduling
        # decision.
        lines = CycleCountTaskLine.objects.filter(
            Q(cycle_count__tenant=tenant,
              cycle_count__scheduled_date__gte=date_from,
              cycle_count__scheduled_date__lte=date_to)
            & ~Q(cycle_count__status="cancelled")
            & (Q(cycle_count__location_id=selected_location.pk)
               if selected_location is not None else Q()))

        # --- ONE aggregate for the whole line strip ------------------------------------------
        line_stats = lines.aggregate(**_ROLLUP_ANNOTATIONS)
        counted_lines = line_stats["count_lines"] or 0
        variance_lines = line_stats["variance_lines"] or 0
        stats.update(
            lines_counted=counted_lines,
            lines_with_variance=variance_lines,
            variance_rate_pct=(variance_lines * 100 / counted_lines) if counted_lines else None,
            # The pinned arithmetic: Sum(counted) − Sum(expected).
            net_variance_qty=(line_stats["counted_sum"] or ZERO) - (line_stats["expected_sum"]
                                                                    or ZERO),
            abs_variance_qty=line_stats["abs_sum"] or ZERO,
            variance_value=line_stats["value_sum"] or ZERO,
            accuracy_pct=_accuracy_pct(counted_lines, variance_lines))

        # --- ONE grouped query: the item roll-up ---------------------------------------------
        # Worst first — most absolute variance — because a capped table must keep the rows a buyer
        # would have scrolled to find.
        item_batch = list(lines
                          .values("item_id")
                          .annotate(variance_tasks=Count("cycle_count_id", distinct=True,
                                                         filter=_HAS_VARIANCE),
                                    **_ROLLUP_ANNOTATIONS)
                          .filter(count_lines__gt=0)
                          # An annotated queryset is NOT ordered by Meta.ordering — Django does not
                          # apply it to a GROUP BY — so the ordering is explicit, and `id` breaks
                          # ties so the page cannot repeat or drop a row between requests.
                          .order_by("-abs_sum", "item_id")[:ROW_CAP + 1])
        truncated = truncated or len(item_batch) > ROW_CAP
        item_batch = item_batch[:ROW_CAP]
        item_map = {obj.pk: obj for obj in
                    Item.objects.filter(tenant=tenant,
                                        pk__in=[row["item_id"] for row in item_batch])
                    .select_related("uom")}
        for row in item_batch:
            item_rows.append({
                "item": item_map.get(row["item_id"]),
                "count_lines": row["count_lines"],
                "variance_lines": row["variance_lines"],
                "net_variance": (row["counted_sum"] or ZERO) - (row["expected_sum"] or ZERO),
                "abs_variance": row["abs_sum"] or ZERO,
                "variance_value": row["value_sum"] or ZERO,
                "accuracy_pct": _accuracy_pct(row["count_lines"], row["variance_lines"]),
                "repeat_offender": (row["variance_tasks"] or 0) >= _REPEAT_OFFENDER_TASKS,
            })

        # --- ONE grouped query: the location roll-up ------------------------------------------
        # Worst first here is LEAST accurate, which a database cannot order by directly (accuracy
        # is a ratio of two aggregates), so the query orders deterministically by variance count
        # and the ranking is applied in Python over the capped batch.
        loc_batch = list(lines
                         .values(loc_id=F("cycle_count__location_id"))
                         .annotate(**_ROLLUP_ANNOTATIONS)
                         .filter(count_lines__gt=0)
                         .order_by("-variance_lines", "loc_id")[:ROW_CAP + 1])
        truncated = truncated or len(loc_batch) > ROW_CAP
        for row in loc_batch[:ROW_CAP]:
            location = location_map.get(row["loc_id"])
            accuracy = _accuracy_pct(row["count_lines"], row["variance_lines"])
            location_rows.append({
                "location": location,
                "path": location.path() if location is not None else "",
                "count_lines": row["count_lines"],
                "variance_lines": row["variance_lines"],
                "net_variance": (row["counted_sum"] or ZERO) - (row["expected_sum"] or ZERO),
                "accuracy_pct": accuracy,
                "accuracy_css": _accuracy_css(accuracy),
            })
        location_rows.sort(key=lambda r: (r["accuracy_pct"] if r["accuracy_pct"] is not None
                                          else 101, -r["variance_lines"]))

        # --- ONE query: the counting SCHEDULE that produced all of the above -------------------
        # `is_due` and `cadence_label` are both pure Python on already-loaded columns, so calling
        # them per row costs nothing.
        programs = (CountProgram.objects.filter(tenant=tenant)
                    .select_related("location")
                    .order_by("-is_active", "name", "id"))
        if selected_location is not None:
            programs = programs.filter(Q(location_id=selected_location.pk)
                                       | Q(location__isnull=True))
        for program in programs[:ROW_CAP]:
            program_rows.append({
                "program": program,
                "cadence_label": program.cadence_label,
                "last_run_date": program.last_run_date,
                "is_due": program.is_due(today),
                "location": program.location,
                "abc_class": program.abc_class,
                "url": reverse("inventory:countprogram_detail", args=[program.pk]),
            })

    return render(request, TEMPLATE, {
        "stats": stats,
        "item_rows": item_rows,
        "location_rows": location_rows,
        "program_rows": program_rows,
        "locations": locations,
        "window_choices": WINDOW_CHOICES,
        "selected_window": selected_window,
        "selected_location": selected_location,
        "date_from": date_from,
        "date_to": date_to,
        "row_cap": ROW_CAP,
        "truncated": truncated,
        "attribution_note": ATTRIBUTION_NOTE,
        # Out to the pages that OWN counting — this one reports, it does not count, reconcile or
        # schedule.
        "links": [
            {"label": "Cycle count tasks", "url": reverse("scm:cyclecounttask_list"),
             "icon": "clipboard-list"},
            {"label": "Count programmes", "url": reverse("inventory:countprogram_list"),
             "icon": "calendar-clock"},
            {"label": "Physical inventory", "url": reverse("inventory:physicalinventory_list"),
             "icon": "boxes"},
            {"label": "Stock adjustments", "url": reverse("scm:stockadjustment_list"),
             "icon": "scale"},
        ],
    })
