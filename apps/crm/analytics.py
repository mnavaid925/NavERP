"""CRM 1.6 Analytics & Reporting — the compute layer.

Every figure surfaced by a dashboard widget or a standard report is a **read-only
aggregation** over the existing CRM models (Opportunity / Case / Lead / Campaign /
CrmTask / CommunicationLog). Nothing is stored: dashboards compute live on each render
(real-time data), and a report is only frozen when the user explicitly takes a
``ReportSnapshot``. Centralizing the queries here keeps the views thin and makes the
metrics unit-testable in isolation.

Import direction: this module imports ``models`` — ``models.py`` never imports this one
(it owns only the field choice lists). That one-way edge avoids a circular import.

Widget result contract (``compute_widget``):
  * scalar -> {kind, value(float), display(str), max(float), pct(int 0-100)}
  * series -> {kind, labels[str], data[number]}
  * table  -> {kind, columns[str], rows[list]}

Report result contract (``compute_report`` — every value JSON-serializable so a
``ReportSnapshot`` can store it verbatim and re-render without recomputing):
  {summary:[{label,value}], columns[str], rows[list], chart_type, chart_label,
   chart_labels[str], chart_data[number]}
"""
from datetime import timedelta

from django.db.models import Avg, Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth, TruncWeek
from django.utils import timezone

from .models import Campaign, Case, CommunicationLog, CrmTask, Lead, Opportunity

# ---------------------------------------------------------------------------
# Formatting helpers (return display strings; keep raw numbers separate)
# ---------------------------------------------------------------------------

def _money(v):
    return "${:,.0f}".format(float(v or 0))


def _num(v):
    return "{:,}".format(int(v or 0))


def _pct(v):
    return "{:.0f}%".format(float(v or 0))


def _hours(v):
    return "{:.1f}".format(v) if v is not None else "—"


def _avg(values):
    vals = [v for v in values if v is not None]
    return (sum(vals) / len(vals)) if vals else None


# ---------------------------------------------------------------------------
# Date-window selector (filters ``created_at`` unless a field is given)
# ---------------------------------------------------------------------------

def range_bounds(key):
    """Translate an ``ANALYTICS_RANGE_CHOICES`` key into ``(start, end)`` datetimes.

    ``end`` is always ``None`` (meaning "up to now"); ``start`` is ``None`` for "all time"."""
    now = timezone.now()
    if key == "last_7":
        return now - timedelta(days=7), None
    if key == "last_30":
        return now - timedelta(days=30), None
    if key == "last_90":
        return now - timedelta(days=90), None
    if key == "quarter":
        q_start_month = 3 * ((now.month - 1) // 3) + 1
        return now.replace(month=q_start_month, day=1, hour=0, minute=0, second=0, microsecond=0), None
    if key == "year":
        return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0), None
    return None, None  # "all"


def _in_range(qs, start, end, field="created_at"):
    if start is not None:
        qs = qs.filter(**{f"{field}__gte": start})
    if end is not None:
        qs = qs.filter(**{f"{field}__lt": end})
    return qs


def _trunc_and_fmt(group_by):
    """Return ``(trunc_function, label_formatter)`` for a period grouping."""
    if group_by == "week":
        return TruncWeek, (lambda d: d.strftime("%d %b"))
    return TruncMonth, (lambda d: d.strftime("%b %Y"))


def _bucket(qs, field, trunc):
    """``{truncated_date: count}`` for a queryset bucketed by ``trunc(field)``."""
    rows = qs.annotate(p=trunc(field)).values("p").annotate(c=Count("id")).order_by("p")
    return {row["p"]: row["c"] for row in rows if row["p"]}


# ===========================================================================
# Widget metric resolvers — each takes (tenant, start, end), returns a partial
# result dict (kind/max/pct are added by compute_widget).
# ===========================================================================

# --- scalar (KPI card / gauge) ---------------------------------------------

def _r_open_pipeline(tenant, start, end):
    qs = _in_range(Opportunity.objects.filter(tenant=tenant, stage__in=Opportunity.OPEN_STAGES), start, end)
    v = qs.aggregate(s=Sum("amount"))["s"] or 0
    return {"value": float(v), "display": _money(v)}


def _r_weighted_forecast(tenant, start, end):
    qs = _in_range(Opportunity.objects.filter(tenant=tenant, stage__in=Opportunity.OPEN_STAGES), start, end)
    agg = qs.aggregate(w=Sum(F("amount") * F("probability"),
                             output_field=DecimalField(max_digits=18, decimal_places=2)))
    v = (agg["w"] or 0) / 100
    return {"value": float(v), "display": _money(v)}


def _r_win_rate(tenant, start, end):
    # Date window filters on created_at, so this is the win rate of opportunities *created*
    # in the window (not closed in it) — a deliberate cohort semantics.
    agg = _in_range(Opportunity.objects.filter(tenant=tenant), start, end).aggregate(
        won=Count("id", filter=Q(stage="closed_won")),
        closed=Count("id", filter=Q(stage__in=["closed_won", "closed_lost"])))
    rate = (agg["won"] / agg["closed"] * 100) if agg["closed"] else 0
    return {"value": float(rate), "display": _pct(rate)}


def _r_revenue_won(tenant, start, end):
    qs = _in_range(Opportunity.objects.filter(tenant=tenant, stage="closed_won"), start, end)
    v = qs.aggregate(s=Sum("amount"))["s"] or 0
    return {"value": float(v), "display": _money(v)}


def _r_new_leads(tenant, start, end):
    c = _in_range(Lead.objects.filter(tenant=tenant), start, end).count()
    return {"value": float(c), "display": _num(c)}


def _r_open_cases(tenant, start, end):
    c = _in_range(Case.objects.filter(tenant=tenant, status__in=Case.OPEN_STATUSES), start, end).count()
    return {"value": float(c), "display": _num(c)}


def _r_avg_csat(tenant, start, end):
    qs = _in_range(Case.objects.filter(tenant=tenant, satisfaction_rating__isnull=False), start, end)
    v = qs.aggregate(a=Avg("satisfaction_rating"))["a"]  # None when no rated cases in range
    return {"value": float(v) if v is not None else 0,
            "display": ("{:.1f}".format(v) if v is not None else "—")}


def _r_open_tasks(tenant, start, end):
    c = _in_range(CrmTask.objects.filter(tenant=tenant, status__in=CrmTask.OPEN_STATUSES), start, end).count()
    return {"value": float(c), "display": _num(c)}


# --- series (bar / line / pie / doughnut) ----------------------------------

def _count_by_choice(qs, field, choices, start, end):
    qs = _in_range(qs, start, end)
    counts = {row[field]: row["c"] for row in qs.values(field).annotate(c=Count("id"))}
    return {"labels": [label for _, label in choices],
            "data": [counts.get(val, 0) for val, _ in choices]}


def _r_pipeline_by_stage(tenant, start, end):
    qs = _in_range(Opportunity.objects.filter(tenant=tenant, stage__in=Opportunity.OPEN_STAGES), start, end)
    counts = {row["stage"]: row["c"] for row in qs.values("stage").annotate(c=Count("id"))}
    open_stages = [(v, l) for v, l in Opportunity.STAGE_CHOICES if v in Opportunity.OPEN_STAGES]
    return {"labels": [l for _, l in open_stages], "data": [counts.get(v, 0) for v, _ in open_stages]}


def _r_pipeline_value_by_stage(tenant, start, end):
    qs = _in_range(Opportunity.objects.filter(tenant=tenant, stage__in=Opportunity.OPEN_STAGES), start, end)
    sums = {row["stage"]: row["s"] for row in qs.values("stage").annotate(s=Sum("amount"))}
    open_stages = [(v, l) for v, l in Opportunity.STAGE_CHOICES if v in Opportunity.OPEN_STAGES]
    return {"labels": [l for _, l in open_stages], "data": [float(sums.get(v) or 0) for v, _ in open_stages]}


def _r_win_loss(tenant, start, end):
    agg = _in_range(Opportunity.objects.filter(tenant=tenant), start, end).aggregate(
        won=Count("id", filter=Q(stage="closed_won")),
        lost=Count("id", filter=Q(stage="closed_lost")))
    return {"labels": ["Won", "Lost"], "data": [agg["won"] or 0, agg["lost"] or 0]}


def _r_revenue_won_by_month(tenant, start, end):
    qs = _in_range(Opportunity.objects.filter(tenant=tenant, stage="closed_won"), start, end)
    rows = (qs.annotate(p=TruncMonth(Coalesce("stage_changed_at", "created_at")))
              .values("p").annotate(s=Sum("amount")).order_by("p"))
    labels, data = [], []
    for r in rows:
        if not r["p"]:
            continue
        labels.append(r["p"].strftime("%b %Y"))
        data.append(float(r["s"] or 0))
    return {"labels": labels, "data": data}


def _r_leads_by_rating(tenant, start, end):
    return _count_by_choice(Lead.objects.filter(tenant=tenant), "rating", Lead.RATING_CHOICES, start, end)


def _r_leads_by_status(tenant, start, end):
    return _count_by_choice(Lead.objects.filter(tenant=tenant), "status", Lead.STATUS_CHOICES, start, end)


def _r_leads_by_source(tenant, start, end):
    return _count_by_choice(Lead.objects.filter(tenant=tenant), "source", Lead.SOURCE_CHOICES, start, end)


def _r_cases_by_status(tenant, start, end):
    return _count_by_choice(Case.objects.filter(tenant=tenant), "status", Case.STATUS_CHOICES, start, end)


def _r_cases_by_priority(tenant, start, end):
    return _count_by_choice(Case.objects.filter(tenant=tenant), "priority", Case.PRIORITY_CHOICES, start, end)


def _r_tasks_by_type(tenant, start, end):
    return _count_by_choice(CrmTask.objects.filter(tenant=tenant), "type", CrmTask.TYPE_CHOICES, start, end)


# --- table -----------------------------------------------------------------

def _r_top_performers(tenant, start, end):
    qs = _in_range(Opportunity.objects.filter(tenant=tenant, stage="closed_won"), start, end)
    rows = (qs.values("owner", "owner__first_name", "owner__last_name", "owner__username")
              .annotate(deals=Count("id"), rev=Sum("amount")).order_by("-rev")[:10])
    out = []
    for r in rows:
        name = ("{} {}".format(r["owner__first_name"] or "", r["owner__last_name"] or "").strip()
                or r["owner__username"] or "Unassigned")
        rev = float(r["rev"] or 0)
        deals = r["deals"] or 0
        out.append([name, deals, _money(rev), _money(rev / deals if deals else 0)])
    return {"columns": ["Sales Rep", "Deals Won", "Revenue Won", "Avg Deal Size"], "rows": out}


def _r_campaign_roi(tenant, start, end):
    # .values() avoids instantiating Campaign objects just to read three columns.
    qs = (_in_range(Campaign.objects.filter(tenant=tenant), start, end)
          .values("name", "budget_actual", "actual_revenue").order_by("-actual_revenue")[:10])
    out = []
    for c in qs:
        budget = float(c["budget_actual"] or 0)
        rev = float(c["actual_revenue"] or 0)
        roi = ((rev - budget) / budget * 100) if budget else None
        out.append([c["name"], _money(budget), _money(rev), (_pct(roi) if roi is not None else "—")])
    return {"columns": ["Campaign", "Spend", "Revenue", "ROI %"], "rows": out}


# Chart kinds each metric kind can be drawn as.
SCALAR_CHARTS = ["kpi", "gauge"]
SERIES_CHARTS = ["bar", "line", "pie", "doughnut"]
TABLE_CHARTS = ["table"]

# The single source of truth for widget compute behaviour, keyed to match
# ``models.WIDGET_METRIC_CHOICES``. ``intrinsic_max`` lets a percentage / rating
# scalar render a meaningful gauge without a user-set target.
WIDGET_METRICS = {
    "kpi_open_pipeline": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_open_pipeline},
    "kpi_weighted_forecast": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_weighted_forecast},
    "kpi_win_rate": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_win_rate, "intrinsic_max": 100},
    "kpi_revenue_won": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_revenue_won},
    "kpi_new_leads": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_new_leads},
    "kpi_open_cases": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_open_cases},
    "kpi_avg_csat": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_avg_csat, "intrinsic_max": 5},
    "kpi_open_tasks": {"kind": "scalar", "charts": SCALAR_CHARTS, "resolver": _r_open_tasks},
    "pipeline_by_stage": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_pipeline_by_stage},
    "pipeline_value_by_stage": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_pipeline_value_by_stage},
    "win_loss": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_win_loss},
    "revenue_won_by_month": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_revenue_won_by_month},
    "leads_by_rating": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_leads_by_rating},
    "leads_by_status": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_leads_by_status},
    "leads_by_source": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_leads_by_source},
    "cases_by_status": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_cases_by_status},
    "cases_by_priority": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_cases_by_priority},
    "tasks_by_type": {"kind": "series", "charts": SERIES_CHARTS, "resolver": _r_tasks_by_type},
    "top_performers": {"kind": "table", "charts": TABLE_CHARTS, "resolver": _r_top_performers},
    "campaign_roi": {"kind": "table", "charts": TABLE_CHARTS, "resolver": _r_campaign_roi},
}


def allowed_charts(metric):
    """Chart types valid for a metric (used by the widget form's clean())."""
    meta = WIDGET_METRICS.get(metric)
    return meta["charts"] if meta else []


def compute_widget(widget):
    """Compute a single widget live. Returns the normalized result dict (see module docstring)."""
    meta = WIDGET_METRICS.get(widget.metric)
    if not meta:
        return {"kind": "scalar", "value": 0, "display": "—", "error": "Unknown metric"}
    start, end = range_bounds(widget.date_range)
    result = meta["resolver"](widget.tenant, start, end)
    result["kind"] = meta["kind"]
    if meta["kind"] == "scalar":
        val = result.get("value") or 0
        target = float(widget.target_value) if widget.target_value is not None else None
        max_v = target or meta.get("intrinsic_max") or (val if val > 0 else 1)
        result["max"] = max_v
        result["pct"] = min(100, round(val / max_v * 100)) if max_v else 0
    return result


# ===========================================================================
# Standard report computers — each takes (report, tenant, start, end).
# ===========================================================================

def _compute_sales_activity(report, tenant, start, end):
    trunc, fmt = _trunc_and_fmt(report.group_by if report.group_by in ("month", "week") else "month")
    opp = _bucket(_in_range(Opportunity.objects.filter(tenant=tenant), start, end), "created_at", trunc)
    task = _bucket(_in_range(CrmTask.objects.filter(tenant=tenant, status="done"), start, end, "completed_at"),
                   "completed_at", trunc)
    comm = _bucket(_in_range(CommunicationLog.objects.filter(tenant=tenant), start, end, "occurred_at"),
                   "occurred_at", trunc)
    keys = sorted(set(opp) | set(task) | set(comm))
    rows = [[fmt(k), opp.get(k, 0), task.get(k, 0), comm.get(k, 0)] for k in keys]
    summary = [
        {"label": "Opportunities Created", "value": _num(sum(opp.values()))},
        {"label": "Tasks Completed", "value": _num(sum(task.values()))},
        {"label": "Communications Logged", "value": _num(sum(comm.values()))},
    ]
    return {"summary": summary,
            "columns": ["Period", "Opportunities Created", "Tasks Completed", "Communications Logged"],
            "rows": rows, "chart_type": "line", "chart_label": "Opportunities Created",
            "chart_labels": [fmt(k) for k in keys], "chart_data": [opp.get(k, 0) for k in keys]}


def _compute_sales_performance(report, tenant, start, end):
    qs = _in_range(Opportunity.objects.filter(tenant=tenant, stage="closed_won"), start, end)
    grouped = (qs.values("owner", "owner__first_name", "owner__last_name", "owner__username")
                 .annotate(deals=Count("id"), rev=Sum("amount")).order_by("-rev"))
    rows, labels, data = [], [], []
    total_deals = total_rev = 0
    for r in grouped:
        name = ("{} {}".format(r["owner__first_name"] or "", r["owner__last_name"] or "").strip()
                or r["owner__username"] or "Unassigned")
        rev = float(r["rev"] or 0)
        deals = r["deals"] or 0
        total_deals += deals
        total_rev += rev
        rows.append([name, deals, _money(rev), _money(rev / deals if deals else 0)])
        labels.append(name)
        data.append(rev)
    summary = [
        {"label": "Sales Reps", "value": _num(len(rows))},
        {"label": "Deals Won", "value": _num(total_deals)},
        {"label": "Revenue Won", "value": _money(total_rev)},
    ]
    return {"summary": summary,
            "columns": ["Sales Rep", "Deals Won", "Revenue Won", "Avg Deal Size"],
            "rows": rows, "chart_type": "bar", "chart_label": "Revenue Won",
            "chart_labels": labels, "chart_data": data}


def _compute_funnel(report, tenant, start, end):
    opps = _in_range(Opportunity.objects.filter(tenant=tenant).exclude(stage="closed_lost"), start, end)
    order = [("prospecting", "Prospecting"), ("qualification", "Qualification"),
             ("proposal", "Proposal"), ("negotiation", "Negotiation"), ("closed_won", "Closed Won")]
    keys = [k for k, _ in order]
    # One grouped query for count+value per current stage, then roll forward: a deal in a
    # later stage has, by definition, already passed through every earlier stage.
    per_stage = {row["stage"]: (row["c"], float(row["s"] or 0))
                 for row in opps.values("stage").annotate(c=Count("id"), s=Sum("amount"))}
    rows, labels, counts = [], [], []
    prev = None
    for i, (val, label) in enumerate(order):
        c = sum(per_stage.get(k, (0, 0))[0] for k in keys[i:])  # currently at-or-past this stage
        s = sum(per_stage.get(k, (0, 0))[1] for k in keys[i:])
        drop = "—" if prev is None else (_pct((prev - c) / prev * 100) if prev else "0%")
        rows.append([label, c, _money(s), drop])
        labels.append(label)
        counts.append(c)
        prev = c
    entered = counts[0] if counts else 0
    won = counts[-1] if counts else 0
    summary = [
        {"label": "Entered Pipeline", "value": _num(entered)},
        {"label": "Won", "value": _num(won)},
        {"label": "Win Conversion", "value": (_pct(won / entered * 100) if entered else "0%")},
    ]
    return {"summary": summary,
            "columns": ["Stage", "Opportunities", "Value ($)", "Drop-off %"],
            "rows": rows, "chart_type": "bar", "chart_label": "Opportunities",
            "chart_labels": labels, "chart_data": counts}


def _compute_service(report, tenant, start, end):
    # Durations are averaged in Python on purpose: Avg(ExpressionWrapper(... DurationField))
    # returns a float of microseconds on SQLite but a timedelta on MariaDB, so a single
    # cross-DB expression can't call .total_seconds() safely. The set is bounded by the
    # tenant's cases inside the date window; only the six needed columns are fetched.
    cases = list(_in_range(Case.objects.filter(tenant=tenant), start, end).values(
        "priority", "status", "created_at", "resolved_at", "first_responded_at", "satisfaction_rating"))
    by_period = report.group_by in ("month", "week")
    pr_display = dict(Case.PRIORITY_CHOICES)
    pr_order = [k for k, _ in Case.PRIORITY_CHOICES]

    def group_of(c):
        if by_period:
            d = c["created_at"]
            return d.strftime("%b %Y") if report.group_by == "month" else d.strftime("%d %b")
        return pr_display.get(c["priority"], c["priority"])

    def sort_of(c):
        if by_period:
            return c["created_at"]
        return pr_order.index(c["priority"]) if c["priority"] in pr_order else 99

    groups = {}
    for c in cases:
        g = group_of(c)
        if g not in groups:
            groups[g] = {"items": [], "sort": sort_of(c)}
        groups[g]["items"].append(c)

    rows, labels, data = [], [], []
    for label, grp in sorted(groups.items(), key=lambda kv: kv[1]["sort"]):
        items = grp["items"]
        resolved = [c for c in items if c["resolved_at"]]
        res_h = _avg([(c["resolved_at"] - c["created_at"]).total_seconds() / 3600 for c in resolved])
        fr = [c for c in items if c["first_responded_at"]]
        fr_h = _avg([(c["first_responded_at"] - c["created_at"]).total_seconds() / 3600 for c in fr])
        csat = [c["satisfaction_rating"] for c in items if c["satisfaction_rating"] is not None]
        avg_csat = _avg(csat)
        rows.append([label, len(items), len(resolved), _hours(res_h), _hours(fr_h),
                     ("{:.1f}".format(avg_csat) if avg_csat is not None else "—"), len(csat)])
        labels.append(label)
        data.append(len(items))

    total = len(cases)
    total_resolved = len([c for c in cases if c["resolved_at"]])
    overall_res = _avg([(c["resolved_at"] - c["created_at"]).total_seconds() / 3600
                        for c in cases if c["resolved_at"]])
    overall_csat = _avg([c["satisfaction_rating"] for c in cases if c["satisfaction_rating"] is not None])
    summary = [
        {"label": "Total Cases", "value": _num(total)},
        {"label": "Resolved", "value": (_pct(total_resolved / total * 100) if total else "0%")},
        {"label": "Avg Resolution", "value": ((_hours(overall_res) + " h") if overall_res is not None else "—")},
        {"label": "Avg CSAT", "value": ("{:.1f}".format(overall_csat) if overall_csat is not None else "—")},
    ]
    head = "Period" if by_period else "Priority"
    return {"summary": summary,
            "columns": [head, "Cases", "Resolved", "Avg Resolution (h)", "Avg First Response (h)",
                        "Avg CSAT", "CSAT Responses"],
            "rows": rows, "chart_type": "bar", "chart_label": "Cases",
            "chart_labels": labels, "chart_data": data}


REPORT_COMPUTERS = {
    "sales_activity": _compute_sales_activity,
    "sales_performance": _compute_sales_performance,
    "funnel": _compute_funnel,
    "service": _compute_service,
}


def compute_report(report):
    """Compute a saved report live. Every value in the result is JSON-serializable so a
    ``ReportSnapshot`` can store it verbatim."""
    fn = REPORT_COMPUTERS.get(report.report_type)
    if not fn:
        return {"summary": [], "columns": [], "rows": [], "chart_type": "bar",
                "chart_label": "", "chart_labels": [], "chart_data": []}
    start, end = range_bounds(report.date_range)
    return fn(report, report.tenant, start, end)
