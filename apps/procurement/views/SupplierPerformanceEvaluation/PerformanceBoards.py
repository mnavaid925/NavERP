"""Procurement 6.16 Supplier Performance & Evaluation — the three COMPUTED boards.

**Benchmarking & Trending** is the one NavERP.md bullet of 6.16 that describes a *view over
measurements that already exist*, not a new document. Every figure these three pages render was
frozen onto a ``SupplierKpiScore`` row by ``supplierevaluation_generate`` — which is exactly why
the bullet ships as boards and declares **no model, no form and no migration**. There is no
``models/SupplierPerformanceEvaluation/PerformanceBoards.py``; this lane adds no table at all.
(The ``GoodsReceiptInspection/ReceiptBoards.py`` and ``BudgetCostManagement/VarianceReport.py``
precedents — read-only pages over rows somebody else owns.)

**The arithmetic is not here.** Ranking, percentiles, the quadrant rule, the period-by-period
series and the perception delta all live in :mod:`apps.procurement.performance`, alongside the
resolvers that produced the underlying scores. These views parse the query string, hand the
parsed values to one helper, and render what comes back. A figure computed in a view would be a
second answer to a question the scorecard has already answered — and the two would drift the
first time a weight changed.

**What these pages are NOT — and this one matters more than the code.** Everything on the
benchmark board is a ranking of *this tenant's own suppliers against each other*, computed by
averaging and sorting the tenant's own frozen score rows. It is not an industry benchmark,
nothing here is predictive, and no model was trained on anything.
:data:`~apps.procurement.performance.BENCHMARK_NOTE` says so in one sentence and the board prints
it above the table, unconditionally — including on the empty board, where a reader is most likely
to assume the missing numbers are somewhere else. ``SupplierKpi.industry_benchmark_value`` is a
figure somebody typed in by hand; the trend board is the only page here that surfaces it and it
is labelled hand-entered where it appears.

**Query discipline — these are the only aggregate pages in 6.16, so they are the obvious N+1
sites.** Each board is a fixed, small number of queries that does NOT grow with the number of
suppliers, periods or KPIs on the page:

* ``supplier_benchmark_board`` — the period picker, the category picker, and
  ``benchmark_rows()``'s three (scorecards with ``Count`` annotated, the profiles for the whole
  cohort in one ``party_id__in``, the risk assessments for the whole cohort in one more). The
  ranking and the percentiles are ONE Python pass over rows already in memory. Twenty suppliers
  and two hundred cost the same five queries.
* ``supplier_trend_board`` — the two pickers, the supplier lookup and ``trend_series()``'s two
  (the scorecards, then every line across all of them in one ``scorecard_id__in``); a sixth only
  when ``?kpi=`` is set and the KPI has to be resolved. Never one query per period: three periods
  and ten cost the same.
* ``supplier_perception_gap`` — the supplier picker, the selection lookup, the window picker, and
  ``perception_gap_rows()``'s single pass over the window's submitted responses, bucketed in
  Python by KPI and side. One grouped read, not two loops.

Every ``__str__`` and template FK hop is ``select_related``-ed inside the helper that fetches the
row, so nothing here dereferences a deferred relation while rendering.

**Tenant scoping.** Every queryset is ``filter(tenant=request.tenant)``; there is no ``.all()``
in this file. All three views open with the tenant-``None`` guard — the superuser carries
``tenant=None`` by design, and a board that renders blank without saying why sends the reader
looking for a bug in the data.

**Import discipline.** ``SupplierKpi`` comes from its ENTITY module, never from
``apps.procurement.models``: this sub-package is not added to the package ``__init__``
re-export blocks until the Integrate phase, and a package-level import would be a star-import
cycle at URLconf import time (the ``CostForecasts.py`` precedent). ``apps.procurement.performance``
is a flat module at the app root and imports cleanly. Sibling-app models (``scm``, ``core``) are
imported INSIDE the function that needs them.
"""
import datetime

from apps.core.crud import as_db_int
from apps.procurement import performance
from apps.procurement.models.SupplierPerformanceEvaluation.SupplierKpis import (
    TIER_CHOICES, SupplierKpi)
from apps.procurement.views._common import *  # noqa: F401,F403

TEMPLATE_BENCHMARK = "procurement/performance/benchmark_board.html"
TEMPLATE_TREND = "procurement/performance/trend_board.html"
TEMPLATE_GAP = "procurement/performance/perception_gap.html"

#: The four performance/risk segments ``performance.quadrant_for()`` returns, with their labels.
#: A LEGEND, not a filter — the board's query string carries ``period``/``tier``/``category``
#: only (§3.5), because a quadrant is derived from two axes the reader can already see and a
#: fourth filter would just hide rows from the cohort statistics printed above them.
QUADRANT_CHOICES = (
    ("strategic", "Strategic"),
    ("hidden", "Hidden high performer"),
    ("development", "Development"),
    ("underperforming", "Underperforming"),
)

#: Printed on the perception-gap board. ONE constant, so the page and its help text cannot
#: describe the scale two different ways.
GAP_NOTE = (
    "Ratings are converted to a 0-100 scale (1 = 0 … 5 = 100) and weighted by each "
    "respondent's importance. Only submitted responses count.")

#: How many distinct ``SupplierProfile.category`` values the benchmark filter offers. Bounded
#: like every other picker in this app — the column is free text, so a large tenant could
#: otherwise put thousands of options into one page.
_CATEGORY_CAP = 200


def _as_date(raw):
    """A ``YYYY-MM-DD`` GET value as a ``date``, or ``None``.

    Junk in the query string is SKIPPED, never raised on (L11) — ``?period=lol`` and
    ``?period=2026-02-31`` are both things anybody can type into the address bar, and both must
    fall back to the default period rather than 500. A local copy of the helper 6.15's variance
    report carries, matching the convention that peer sub-modules mirror this rather than import
    each other's private names.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.date.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _supplier_parties(tenant):
    """Supplier/vendor-role parties for the ``?supplier=`` pickers.

    A LOCAL copy, matching every other procurement sub-module (``ReceiptBoards._supplier_parties``).
    ``.distinct()`` is load-bearing: a party carrying BOTH roles would otherwise appear twice in
    the picker and, worse, twice in any queryset joined through it.
    """
    from apps.core.models import Party

    if tenant is None:
        return Party.objects.none()
    return (Party.objects.filter(tenant=tenant, roles__role__in=("supplier", "vendor"))
            .distinct().order_by("name"))


def _active_kpis(tenant):
    """The active KPI catalogue — the trend board's optional per-KPI filter."""
    if tenant is None:
        return SupplierKpi.objects.none()
    return (SupplierKpi.objects.filter(tenant=tenant, is_active=True)
            .order_by("display_order", "code"))


def _profile_categories(tenant):
    """Distinct non-blank ``scm.SupplierProfile.category`` values in this tenant, sorted.

    ``.order_by()`` (empty) is LOAD-BEARING: it clears the model's ``Meta.ordering`` before the
    ``DISTINCT``, which would otherwise be applied over the ordering column as well and hand back
    duplicate categories (the ``_grouped_sum`` reasoning from 6.15's variance report).
    """
    from apps.scm.models import SupplierProfile

    if tenant is None:
        return []
    return sorted(SupplierProfile.objects.filter(tenant=tenant).exclude(category="")
                  .order_by().values_list("category", flat=True).distinct()[:_CATEGORY_CAP])


def _feedback_windows(tenant, party=None):
    """The selectable perception windows: ``[{"period_start", "period_end", "label"}, ...]``.

    Read from the FEEDBACK rows rather than from the scorecards, because this board compares two
    sides of a survey: a window in which nobody answered is a dead option, and offering it would
    render an empty board that looks like a bug. Narrowed to the selected supplier when there is
    one, so the picker only ever offers windows that have something to show for them.

    ONE query, capped at ``PERIOD_CAP`` pairs. Windows are keyed by ``period_end`` alone (that is
    all the query string carries), so where several windows share an end date the EARLIEST start
    wins — a superset window, which cannot silently drop a submitted response from the period the
    reader picked. The ordering ``("-period_end", "period_start")`` is what makes "earliest
    start" the first row seen.
    """
    from apps.procurement.models.SupplierPerformanceEvaluation.SupplierFeedback import (
        SupplierFeedback)

    if tenant is None:
        return []
    rows = SupplierFeedback.objects.filter(tenant=tenant, status="submitted")
    if party is not None:
        rows = rows.filter(supplier=party)
    pairs = (rows.order_by("-period_end", "period_start")
             .values_list("period_start", "period_end").distinct()[:performance.PERIOD_CAP])

    windows, seen = [], set()
    for period_start, period_end in pairs:
        if period_end in seen:
            continue
        seen.add(period_end)
        windows.append({"period_start": period_start, "period_end": period_end,
                        "label": f"{period_start} to {period_end}"})
    return windows


def _empty_cohort():
    """The ``cohort`` shape ``benchmark_rows()`` returns for an empty period.

    Built here too, so the no-tenant and no-period branches hand the template the SAME keys the
    populated branch does. A missing key renders as the empty string in a Django template, which
    is how a broken statistic ships looking like a blank one (L8).
    """
    return {"count": 0, "scored": 0, "average": None, "best": None, "worst": None}


@login_required
def supplier_benchmark_board(request):
    """Every supplier in one period, ranked against each other. Reads; writes nothing.

    Five queries, whatever the size of the supply base — see the module docstring. The composite
    each row is ranked on is the weighted mean of the scorecard's own KPI lines, exactly as the
    trend board computes it, so the two boards can never disagree about what a supplier scored.
    SCM's ``overall_score`` rides along beside it under ``overall``, never instead of it.

    Both narrowing params are validated before they reach the compute layer: ``tier`` against
    ``TIER_CHOICES`` and ``category`` against the tenant's own distinct profile categories — the
    same list the picker is built from, so a value the dropdown cannot offer cannot silently
    empty the board either.
    """
    tenant = request.tenant
    periods = performance.period_choices(tenant) if tenant is not None else []

    # The parsed value wins even when it is not in the picker — a hand-typed period with no
    # scorecards renders an honestly empty cohort rather than silently showing a different one.
    selected_period = _as_date(request.GET.get("period"))
    if selected_period is None:
        selected_period = periods[0] if periods else None

    tier = (request.GET.get("tier") or "").strip()
    if tier not in dict(TIER_CHOICES):
        tier = ""
    # Same guard as ``tier`` one line up, and it was missing here: ``?category=zzz`` reached the
    # compute layer and silently emptied the whole board, while ``?tier=zzz`` on the same filter
    # bar reset itself and rendered the full cohort. ``category`` is free text on
    # ``scm.SupplierProfile`` rather than a CHOICES enum, so the legal set is the tenant's own
    # distinct values — computed once here and reused as ``category_choices`` below, so the
    # filter and the dropdown that offers it cannot drift apart.
    categories = _profile_categories(tenant)
    category = (request.GET.get("category") or "").strip()[:120]
    if category not in categories:
        category = ""

    rows, cohort, truncated = [], _empty_cohort(), False
    if tenant is not None and selected_period is not None:
        rows, cohort, truncated = performance.benchmark_rows(
            tenant, selected_period, tier=tier or None, category=category or None)

    return render(request, TEMPLATE_BENCHMARK, {
        "rows": rows,
        "periods": periods,
        "selected_period": selected_period,
        "cohort": cohort,
        "tier_choices": TIER_CHOICES,
        "category_choices": categories,
        "selected_tier": tier,
        "selected_category": category,
        "quadrant_choices": QUADRANT_CHOICES,
        "row_cap": performance.ROW_CAP,
        "truncated": truncated,
        "benchmark_note": performance.BENCHMARK_NOTE,
    })


@login_required
def supplier_trend_board(request):
    """One supplier across every period on record — the composite, and each KPI underneath it.

    Five queries (six with ``?kpi=``) regardless of how many periods the supplier has:
    ``trend_series()`` reads the scorecards once and every line across all of them once, never
    one query per period. Measured flat from three periods to ten.
    """
    tenant = request.tenant
    suppliers = _supplier_parties(tenant)
    kpis = _active_kpis(tenant)

    supplier_id = as_db_int(request.GET.get("supplier"))
    selected_supplier = (suppliers.filter(pk=supplier_id).first()
                         if supplier_id is not None else None)
    kpi_id = as_db_int(request.GET.get("kpi"))
    selected_kpi = kpis.filter(pk=kpi_id).first() if kpi_id is not None else None

    series, kpi_series, truncated = [], [], False
    if tenant is not None and selected_supplier is not None:
        series, kpi_series, truncated = performance.trend_series(
            tenant, selected_supplier, kpi=selected_kpi)

    return render(request, TEMPLATE_TREND, {
        "suppliers": suppliers,
        "selected_supplier": selected_supplier,
        # Free — the periods are the series' own x-axis, already in memory and already ordered
        # oldest to newest. A second query for them could disagree with the points drawn.
        "periods": [point["period_end"] for point in series],
        "series": series,
        "kpi_series": kpi_series,
        "kpis": kpis,
        "selected_kpi": selected_kpi,
        "row_cap": performance.PERIOD_CAP,
        "truncated": truncated,
        "benchmark_note": performance.BENCHMARK_NOTE,
    })


@login_required
def supplier_perception_gap(request):
    """What we think of a supplier against what the supplier thinks of itself, per KPI.

    Four queries. ``delta = self_avg - internal_avg``, so a POSITIVE delta is the supplier rating
    itself higher than we rate it — the conversation worth having, and the reason this board
    exists at all rather than a second average on the scorecard.
    """
    tenant = request.tenant
    suppliers = _supplier_parties(tenant)

    supplier_id = as_db_int(request.GET.get("supplier"))
    selected_supplier = (suppliers.filter(pk=supplier_id).first()
                         if supplier_id is not None else None)

    periods = _feedback_windows(tenant, selected_supplier)
    wanted = _as_date(request.GET.get("period"))
    selected_period = next((window for window in periods if window["period_end"] == wanted), None)
    if selected_period is None and periods:
        selected_period = periods[0]

    gap_rows, truncated = [], False
    if tenant is not None and selected_supplier is not None and selected_period is not None:
        gap_rows, truncated = performance.perception_gap_rows(
            tenant, selected_supplier, selected_period["period_start"],
            selected_period["period_end"])

    return render(request, TEMPLATE_GAP, {
        "suppliers": suppliers,
        "selected_supplier": selected_supplier,
        "periods": periods,
        "selected_period": selected_period,
        "gap_rows": gap_rows,
        "row_cap": performance.ROW_CAP,
        "truncated": truncated,
        "gap_note": GAP_NOTE,
    })
