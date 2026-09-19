"""Projects 7.16 Reporting & Business Intelligence — the compute registry.

One place that turns a stored *question* (``ProjectReport``) or a *tile* (``DashboardWidget``) into rows,
chart payload and KPI cards by reading the modules that own the data: 7.2 schedule, 7.3 resources,
7.4 cost/EVM, 7.5 risk/issue, 7.6 quality, 7.7 scope, 7.11 time, 7.13 agile and 7.15 billing.

**Read-only rule (L29).** Nothing in this module writes except the one documented repair in
:func:`renumber_tiles` (a tile ``position`` tie left behind by ``wdg_move``) — no ``save()``/``create()``/
``delete()`` of any data row, no ``accounting.*`` import, no mutation of a 7.4 or 7.15 row. Balances and EVM
stay derived where they are owned (``CostControlAccount`` ``@property`` reads, 7.15 billing rows); 7.16 only
aggregates them. If a figure must be persisted, that is a ``ProjectReportRun`` row, never a new column.

**Import direction:** analytics imports models; forms and views import analytics; models NEVER import
analytics. That is why the metric↔chart pair is validated in ``DashboardWidgetForm.clean()`` (which calls
``allowed_charts``) and not in ``DashboardWidget.clean()``.

**JSON boundary:** every payload leaves through :func:`json_safe`, because templates hand it straight to
``json_script`` and never call ``json.dumps`` themselves. A ``Decimal`` or ``date`` that escapes this module
surfaces as a template rendering error far from its cause.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.projects.models import (
    CostControlAccount,
    DashboardWidget,
    IssueEscalation,
    KnowledgeEntry,
    Portfolio,
    PortfolioInvestment,
    Project,
    ProjectClientInvoice,
    ProjectDashboard,
    ProjectExpense,
    ProjectIssue,
    ProjectMilestone,
    ProjectReport,
    ProjectReportRun,
    ProjectRisk,
    ProjectTask,
    QualityDefect,
    Requirement,
    ResourceAllocation,
    ResourceTimeEntry,
    ScopeChangeRequest,
    Sprint,
)
from apps.projects.models.ReportingBusinessIntelligence._choices import (
    CHART_CHOICES,
    DIMENSION_CHOICES,
    MEASURE_CHOICES,
    RANGE_CHOICES,
    REPORT_TYPE_CHOICES,
    SUBJECT_CHOICES,
    WIDGET_METRIC_CHOICES,
)

#: Hard ceiling on rows a single register page will build. Anything above is aggregated away and the
#: payload carries a truncation caveat — an unbounded report is a timed-out request, not a feature.
MAX_REGISTER_ROWS = 2000

#: Ceiling on the CSV writer, which streams instead of rendering — procurement's verified value, and
#: the reason a "download everything" link is not the same request as "show everything".
MAX_EXPORT_ROWS = 5000

#: Grid cap. A dashboard past this is a scroll, not an overview.
MAX_TILES_PER_DASHBOARD = 24

#: Projects whose EVM is evaluated per compute. CostControlAccount properties each run their own
#: aggregates, so the cost is O(accounts) *after* scope + top_n narrow the set — never O(rows).
MAX_EVM_PROJECTS = 200

#: The single spelling of the null-group label, so a row and a caveat can never disagree.
UNASSIGNED = "(unassigned)"

_MEASURE_LABELS = dict(MEASURE_CHOICES)
_DIMENSION_LABELS = dict(DIMENSION_CHOICES)

#: The windows a tile or dashboard may offer: every preset, never ``custom`` (A1.2/A1.3 rule 4 — a
#: tile carries no date pair of its own to resolve).
PRESET_RANGES = [(key, label) for key, label in RANGE_CHOICES if key != "custom"]

#: Cross-module links the reporting home page offers. Views ``reverse()`` these; analytics never does,
#: because a bad name would then surface at import time in an unrelated request path (B3.0).
SIBLING_BOARDS = [
    {"label": "Portfolio dashboard", "url_name": "projects:pfm_dashboard", "module": "7.12"},
    {"label": "Utilization dashboard", "url_name": "projects:utilization_dashboard", "module": "7.3"},
    {"label": "Velocity report", "url_name": "projects:velocity_report", "module": "7.13"},
    {"label": "Project P&L", "url_name": "projects:financial_pnl", "module": "7.15"},
    {"label": "Financial variance", "url_name": "projects:financial_variance", "module": "7.15"},
    {"label": "AR aging", "url_name": "projects:ar_aging", "module": "7.15"},
    {"label": "Cash flow forecast", "url_name": "projects:cash_flow_forecast", "module": "7.15"},
    {"label": "Risk analysis", "url_name": "projects:risk_analysis", "module": "7.5"},
    {"label": "Quality value report", "url_name": "projects:qrv_report", "module": "7.6"},
    {"label": "Task board", "url_name": "projects:task_board", "module": "7.2"},
    {"label": "Gantt timeline", "url_name": "projects:gantt_timeline", "module": "7.2"},
    {"label": "Sprint execution", "url_name": "projects:sprint_execution", "module": "7.13"},
]


# =================================================================================================
# json boundary + window maths
# =================================================================================================
def json_safe(value):
    """Coerce one value into something ``json_script`` can serialise. THE single conversion point."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        # 2dp for money-ish numbers, 4dp for ratios/indices so CPI 0.9876 survives the round trip.
        try:
            quantised = value.quantize(Decimal("0.0001"))
        except InvalidOperation:  # a NaN/Infinity or absurd exponent
            return float(value)
        text = f"{quantised:f}"
        return float(text.rstrip("0").rstrip(".")) if "." in text else int(quantised)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)


def _date_window(date_range, date_from=None, date_to=None, as_of=None):
    """Turn a preset (or an explicit pair) into concrete ``(start, end, as_of)`` dates.

    ``all`` returns ``(None, None, as_of)`` — an unbounded window is a real answer, not a missing one.
    """
    today = as_of or timezone.localdate()

    if date_from and date_to:
        return date_from, date_to, today

    if date_range == "all":
        return None, None, today
    if date_range == "last_7":
        return today - timezone.timedelta(days=6), today, today
    if date_range == "last_30":
        return today - timezone.timedelta(days=29), today, today
    if date_range == "last_90":
        return today - timezone.timedelta(days=89), today, today
    if date_range == "quarter":
        quarter_start = date(today.year, ((today.month - 1) // 3) * 3 + 1, 1)
        return quarter_start, today, today
    if date_range == "year":
        return date(today.year, 1, 1), today, today
    return today - timezone.timedelta(days=89), today, today


def resolve_window(spec, *, as_of=None):
    """The ONE window resolver → ``{"start", "end", "as_of", "label"}``.

    Accepts a ``ProjectReport`` (including the unsaved instance a builder form produced), a bare range
    key, or ``None``. An explicit ``date_from``/``date_to`` pair always beats the preset, which is what
    keeps a ``custom`` report's window stable from run to run.
    """
    if spec is None or isinstance(spec, str):
        date_range, date_from, date_to = spec or "last_90", None, None
    else:
        date_range = getattr(spec, "date_range", None) or "last_90"
        date_from = getattr(spec, "date_from", None)
        date_to = getattr(spec, "date_to", None)

    start, end, as_of = _date_window(date_range, date_from, date_to, as_of)
    if date_range == "custom" or (date_from and date_to):
        label = f"{start.isoformat()} → {end.isoformat()}"
    else:
        label = dict(RANGE_CHOICES).get(date_range, date_range)
    return {"start": start, "end": end, "as_of": as_of, "label": label}


def _money(value):
    return "" if value is None else f"{Decimal(value):,.2f}"


def _num(value):
    return "" if value is None else f"{Decimal(value):,.2f}".rstrip("0").rstrip(".")


def _hours(value):
    return "" if value is None else f"{Decimal(value):,.1f} h"


def _pct_text(value):
    return "—" if value is None else f"{Decimal(value):,.1f}%"


def _within(field, start, end):
    """``{field}__range`` only when BOTH bounds exist — one open bound must not collapse the filter."""
    if start and end:
        return {f"{field}__range": (start, end)}
    if start:
        return {f"{field}__gte": start}
    if end:
        return {f"{field}__lte": end}
    return {}


# =================================================================================================
# ACL — the ONE definition of visibility (a private row for another user is a 404, never a 403)
# =================================================================================================
def visible_reports(request):
    if request.tenant is None:
        return ProjectReport.objects.none()
    return ProjectReport.objects.filter(
        Q(tenant=request.tenant) & (Q(is_shared=True) | Q(owner=request.user))
    ).distinct()


def visible_dashboards(request):
    if request.tenant is None:
        return ProjectDashboard.objects.none()
    # owner=None rows are tenant-provided audience templates, so they are visible to everyone.
    return ProjectDashboard.objects.filter(
        Q(tenant=request.tenant)
        & (Q(is_shared=True) | Q(owner=request.user) | Q(owner__isnull=True))
    ).distinct()


def visible_runs(request):
    """A run has no ``is_shared`` of its own — it inherits its parent question's privacy."""
    if request.tenant is None:
        return ProjectReportRun.objects.none()
    user = request.user
    return ProjectReportRun.objects.filter(
        Q(tenant=request.tenant)
        & (
            Q(report__is_shared=True)
            | Q(report__owner=user)
            | Q(generated_by=user)
            | Q(issued_by=user)
        )
    ).distinct()


def home_dashboard(request):
    """The board to land on: the caller's own ``is_default``, else a tenant template, else newest visible.

    Read-only — "my home" never writes ``is_default`` on the user's behalf (A1.2 rule 1 owns that flag).
    ``audience`` is deliberately NOT matched here: ``accounts.Role`` only carries the seeded Admin/Member
    names (verified ``apps/accounts/management/commands/seed_accounts.py:56-62``), so there is no
    role → audience mapping to read, and guessing from a group name would silently pick the wrong board.
    """
    if request.tenant is None:
        return None
    boards = visible_dashboards(request)
    mine = boards.filter(owner=request.user, is_default=True).first()
    if mine:
        return mine
    templates = boards.filter(owner__isnull=True, is_shared=True)
    return (
        templates.filter(is_default=True).first()
        or templates.order_by("-updated_at", "-id").first()
        or boards.order_by("-updated_at", "-id").first()
    )


# =================================================================================================
# EVM access — one batched read of 7.4's derived properties
# =================================================================================================
def _evm_map(tenant, project_ids, as_of=None):
    """``{project_id: {bac, pv, ev, ac, cv, sv, cpi, spi, eac, health}}`` in ONE queryset.

    The values are 7.4's ``@property`` reads, so each account costs its own aggregate queries; that is
    why callers pass an ALREADY-scoped, top_n-narrowed id list (bounded by MAX_EVM_PROJECTS) rather than
    every project in the tenant. Reading them here keeps the EVM maths in exactly one place — 7.4.
    """
    if not project_ids:
        return {}
    out = {}
    accounts = CostControlAccount.objects.filter(
        tenant=tenant, project_id__in=list(project_ids)[:MAX_EVM_PROJECTS]
    ).select_related("project")
    for account in accounts:
        out[account.project_id] = {
            "bac": account.bac,
            "pv": account.pv,
            "ev": account.ev,
            "ac": account.ac,
            "cv": account.cv,
            "sv": account.sv,
            "cpi": account.cpi,
            "spi": account.spi,
            "eac": account.eac,
            "health": (account.health or {}).get("state") or "",
        }
    return out


# =================================================================================================
# Frozen axes: measures (what a row counts) and dimensions (how rows group)
# =================================================================================================
def _pct(numerator, denominator):
    """Percentage guarded against a zero denominator — ``None`` means "no answer", ``0`` is a real one."""
    numerator = Decimal(numerator or 0)
    denominator = Decimal(denominator or 0)
    if denominator == 0:
        return None
    return (numerator / denominator * Decimal(100)).quantize(Decimal("0.01"))


def _margin_pct(revenue, cost):
    """Margin as a share of what was billed — the ONE spelling, so a report row and a steering-pack band
    can never disagree about the same two numbers."""
    return _pct(Decimal(revenue or 0) - Decimal(cost or 0), revenue)


# Each measure carries the display ``kind`` the cell formatter and the KPI strip read. The facts it needs
# are hard-coded in ``_aggregate``'s one pass — adding a measure there must name it here too, and a test
# pins this dict's keys to ``MEASURE_CHOICES``.
def _measure(kind):
    # ``unit`` is deliberately the same token as ``kind``: it is the vocabulary _format_unit() reads, and
    # the one the tile registry uses, so a figure cannot format differently in a table and on a tile.
    return {"label": "", "kind": kind, "unit": kind}


MEASURES = {
    "planned_value": _measure("money"),
    "earned_value": _measure("money"),
    "actual_cost": _measure("money"),
    "budget_at_completion": _measure("money"),
    "eac": _measure("money"),
    "cv": _measure("money"),
    "cv_pct": _measure("pct"),
    "sv": _measure("money"),
    "sv_pct": _measure("pct"),
    "cpi": _measure("index"),
    "spi": _measure("index"),
    "margin_pct": _measure("pct"),
    "hours": _measure("hours"),
    "billable_pct": _measure("pct"),
    "utilization_pct": _measure("pct"),
    "task_count": _measure("num"),
    "open_count": _measure("num"),
    "completed_count": _measure("num"),
    "on_time_pct": _measure("pct"),
    "slip_days": _measure("days"),
    "exposure_value": _measure("money"),
    "aging_days": _measure("days"),
    "unbilled_amount": _measure("money"),
    "invoiced_amount": _measure("money"),
}
for _key, _entry in MEASURES.items():
    _entry["label"] = _MEASURE_LABELS.get(_key, _key)
del _key, _entry

DIMENSIONS = {key: label for key, label in DIMENSION_CHOICES}
SUBJECTS = {key: label for key, label in SUBJECT_CHOICES}


def _format_unit(unit, value):
    """One figure's display text, shaped by its unit — tables, KPI strips and tiles all read this."""
    if value is None:
        return "—"
    formatter = {
        "money": _money, "pct": _pct_text, "hours": _hours, "index": _num,
        "count": _num, "num": _num,
    }.get(unit)
    if formatter:
        return formatter(value)
    if unit == "days":
        return f"{_num(value)} d"
    return _num(value)


def _format_measure(measure, value):
    return _format_unit((MEASURES.get(measure) or {}).get("unit", "num"), value)

#: metric key -> the chart kinds it can legitimately render as. ``table``-only metrics never get a
#: canvas; a canvas for a scalar is an empty square that still returns HTTP 200 (L8).
_WIDGET_SHAPE = {
    "scalar": ["kpi", "gauge"],
    "series": ["bar", "line", "pie", "doughnut", "heat"],
    "table": ["table"],
}

_METRIC_LABELS = dict(WIDGET_METRIC_CHOICES)


def _metric(kind, unit, drill_url_name):
    """One row of the tile registry. The entry's ``label`` is filled from ``WIDGET_METRIC_CHOICES`` just
    below, so a renamed dropdown entry can never disagree with the tile header it renders."""
    return {
        "label": "",
        "kind": kind,
        "charts": list(_WIDGET_SHAPE[kind]),
        "unit": unit,
        "drill_url_name": drill_url_name,
    }


WIDGET_METRICS = {
    "kpi_active_projects": _metric("scalar", "count", "projects:prj_list"),
    "kpi_overdue_tasks": _metric("scalar", "count", "projects:tsk_list"),
    "kpi_open_risks": _metric("scalar", "count", "projects:rsk_list"),
    "kpi_open_issues": _metric("scalar", "count", "projects:iss_list"),
    "kpi_open_defects": _metric("scalar", "count", "projects:qdf_list"),
    "kpi_cpi": _metric("scalar", "index", "projects:cca_list"),
    "kpi_spi": _metric("scalar", "index", "projects:cca_list"),
    "kpi_utilization_pct": _metric("scalar", "pct", "projects:rte_list"),
    "kpi_billable_pct": _metric("scalar", "pct", "projects:rte_list"),
    "kpi_unbilled_amount": _metric("scalar", "money", "projects:pci_list"),
    "kpi_schedule_slip_days": _metric("scalar", "days", "projects:mst_list"),
    "projects_by_status": _metric("series", "count", "projects:prj_list"),
    "tasks_by_status": _metric("series", "count", "projects:tsk_list"),
    "risks_by_category": _metric("series", "count", "projects:rsk_list"),
    "issues_by_severity": _metric("series", "count", "projects:iss_list"),
    "defects_by_severity": _metric("series", "count", "projects:qdf_list"),
    "hours_by_activity_code": _metric("series", "hours", "projects:rte_list"),
    "cost_variance_by_project": _metric("series", "money", "projects:cca_list"),
    "ev_curve_by_month": _metric("series", "money", "projects:cca_list"),
    "utilization_by_resource": _metric("series", "pct", "projects:rte_list"),
    "milestones_on_time_by_month": _metric("series", "count", "projects:mst_list"),
    # 7.12 owns portfolio health, so the heat tile drills to its board, not to a register list.
    "health_heat_bands": _metric("series", "count", "projects:pfm_dashboard"),
    "top_cost_variance_projects": _metric("table", "money", "projects:cca_list"),
    "top_risk_exposure_projects": _metric("table", "money", "projects:rsk_list"),
    "overdue_milestones": _metric("table", "count", "projects:mst_list"),
}
for _key, _entry in WIDGET_METRICS.items():
    _entry["label"] = _METRIC_LABELS.get(_key, _key)
del _key, _entry


def allowed_charts(metric):
    """The metric↔chart authority. Forms validate with it; models must not import this module."""
    entry = WIDGET_METRICS.get(metric)
    return list(entry["charts"]) if entry else []


def chart_rules():
    """``{metric_key: [chart_key, …]}`` — handed to the widget form page as ``chart_rules`` and to the
    JS that prunes the chart dropdown, so the pair is enforced in the UI and the form by one table."""
    return {key: list(entry["charts"]) for key, entry in WIDGET_METRICS.items()}


# =================================================================================================
# Row facts — every register is flattened into the same primitive dict, so ONE pivot engine serves all
# =================================================================================================
def _fact(row, *, project=None, project_id=None, status="", kind="", date_value=None, due_value=None,
          actual_value=None, planned_value=None, hours=None, billable=None,
          exposure=None, amount=None, severity="", category="", resource="", role="",
          activity="", wbs_phase="", client="", org_unit="", portfolio="", priority="",
          month_value=None, task_count=None, is_open=None, is_done=None):
    """Normalise a source row into the facts the measures/dimensions read.

    Deliberately plain values: no model instances reach the payload (L29 + the JSON boundary).
    """
    return {
        "project": project,
        "project_id": project_id,
        "status": status or "",
        "kind": kind or "",
        "date": date_value,
        "due": due_value,
        "actual": actual_value,
        "planned": planned_value,
        "hours": Decimal(hours or 0),
        "billable": Decimal(billable or 0),
        "exposure": Decimal(exposure or 0),
        "amount": Decimal(amount or 0),
        "severity": severity or "",
        "category": category or "",
        "resource": resource or "",
        "role": role or "",
        "activity": activity or "",
        "wbs_phase": wbs_phase or "",
        "client": client or "",
        "org_unit": org_unit or "",
        "portfolio": portfolio or "",
        "priority": priority or "",
        "month": month_value or (date_value.replace(day=1) if isinstance(date_value, date) else None),
        "task_count": task_count if task_count is not None else 0,
        "is_open": bool(is_open),
        "is_done": bool(is_done),
    }


def _month_of(value):
    return value.replace(day=1) if isinstance(value, date) else None


def _slip_days(actual, planned):
    if isinstance(actual, date) and isinstance(planned, date):
        return (actual - planned).days
    return None


# =================================================================================================
# Register loaders — each flattens its source rows into the shared fact dict
# =================================================================================================
def _scoped(qs, tenant, start, end, scope, date_field=None):
    """The two filters every register shares: the tenant, and (when it declares one) the window."""
    qs = qs.filter(tenant=tenant)
    if date_field and (start or end):
        qs = qs.filter(**_within(date_field, start, end))
    project_ids = scope.get("project_ids")
    if project_ids is not None:
        qs = qs.filter(project_id__in=project_ids)
    return qs


def _scope_project_ids(tenant, scope):
    """Resolve the four scope FKs into one project-id set.

    Done as an explicit set rather than a ``project__portfolio_investments__…`` join so a portfolio
    investment cannot silently multiply a register's rows.
    """
    if not (scope.get("project_id") or scope.get("portfolio_id")
            or scope.get("client_id") or scope.get("org_unit_id")):
        return None

    projects = Project.objects.filter(tenant=tenant)
    if scope.get("project_id"):
        projects = projects.filter(pk=scope["project_id"])
    if scope.get("client_id"):
        projects = projects.filter(client_id=scope["client_id"])
    if scope.get("org_unit_id"):
        projects = projects.filter(org_unit_id=scope["org_unit_id"])
    if scope.get("portfolio_id"):
        invested = PortfolioInvestment.objects.filter(
            tenant=tenant, portfolio_id=scope["portfolio_id"]
        ).values_list("project_id", flat=True)
        projects = projects.filter(pk__in=list(invested))
    return set(projects.values_list("id", flat=True))


def _portfolio_names(tenant):
    """``{project_id: portfolio_name}`` — Project carries no portfolio FK; 7.12's investment rows do."""
    out = {}
    for investment in PortfolioInvestment.objects.filter(tenant=tenant).select_related("portfolio"):
        out.setdefault(investment.project_id, str(investment.portfolio))
    return out


def _program_names(tenant):
    """``{project_id: program_name}`` for the middle tier of the exec pack's rollup.

    ``PortfolioInvestment.program`` is nullable, so a project invested in directly is simply absent here
    and the rollup renders it under its portfolio — which is the truth, not a missing value.
    """
    out = {}
    for investment in PortfolioInvestment.objects.filter(
        tenant=tenant, program__isnull=False
    ).select_related("program"):
        out.setdefault(investment.project_id, str(investment.program))
    return out


def _name(value):
    return str(value) if value is not None else UNASSIGNED


def _load_facts(subject, tenant, start, end, as_of, scope):
    """Return ``(facts, caveats)`` for one register.

    An unbuildable register returns ``([], [caveat])`` instead of guessing a field name — a wrong lookup
    here is a 500 on a report page, and an honest empty register with a caveat is the better answer.
    """
    caveats = []
    facts = []
    portfolios = _portfolio_names(tenant)

    if subject == "project":
        rows = _scoped(Project.objects.select_related("client", "org_unit"), tenant, None, None, scope)
        rows = rows.filter(pk__in=scope["project_ids"]) if scope.get("project_ids") is not None else rows
        for project in rows:
            facts.append(_fact(
                project, project=project.name, project_id=project.pk,
                portfolio=portfolios.get(project.pk, UNASSIGNED),
                client=_name(project.client), org_unit=_name(project.org_unit),
                status=project.status, date_value=project.start_date,
                is_open=project.status in ("chartered", "kickoff", "active", "on_hold"),
                is_done=project.status == "completed",
            ))
    elif subject == "task":
        rows = _scoped(
            ProjectTask.objects.select_related("project", "assignee"),
            tenant, start, end, scope, "planned_end",
        )
        for task in rows:
            facts.append(_fact(
                task, project=task.project.name if task.project else UNASSIGNED,
                project_id=task.project_id,
                portfolio=portfolios.get(task.project_id, UNASSIGNED),
                status=task.status, kind=task.node_type, priority=task.priority,
                date_value=task.planned_end, due_value=task.planned_end,
                actual_value=task.actual_end, planned_value=task.planned_start,
                resource=_name(task.assignee), hours=task.effort_hours, task_count=1,
                is_open=task.status not in ("done", "cancelled"), is_done=task.status == "done",
            ))
    elif subject == "milestone":
        rows = _scoped(
            ProjectMilestone.objects.select_related("project"),
            tenant, start, end, scope, "target_date",
        )
        for milestone in rows:
            facts.append(_fact(
                milestone, project=milestone.project.name if milestone.project else UNASSIGNED,
                project_id=milestone.project_id,
                portfolio=portfolios.get(milestone.project_id, UNASSIGNED),
                status=milestone.status, date_value=milestone.target_date,
                due_value=milestone.target_date, actual_value=milestone.actual_date,
                wbs_phase="Phase gate" if milestone.is_phase_gate else "Milestone",
                task_count=1, is_open=milestone.status in ("planned", "in_review"),
                is_done=milestone.status == "achieved",
            ))
    elif subject == "risk":
        rows = _scoped(
            ProjectRisk.objects.select_related("project", "owner"),
            tenant, start, end, scope, "identified_date",
        )
        for risk in rows:
            facts.append(_fact(
                risk, project=risk.project.name if risk.project else UNASSIGNED,
                project_id=risk.project_id,
                portfolio=portfolios.get(risk.project_id, UNASSIGNED),
                status=risk.status, category=risk.get_category_display(),
                # Both figures are 7.5's own derivations: `probability` is a 1–5 ordinal, so re-spelling
                # its conversion here would understate exposure ~10x, and `impact` is likewise not a
                # 1–25 score. Reading the model keeps this register and 7.5's page telling one story.
                severity=risk.get_severity_band_display(),
                resource=_name(risk.owner), date_value=risk.identified_date,
                due_value=risk.review_date, exposure=risk.exposure, task_count=1,
                is_open=risk.status != "closed", is_done=risk.status == "closed",
            ))
    elif subject == "issue":
        rows = _scoped(
            ProjectIssue.objects.select_related("project", "owner"),
            tenant, start, end, scope, "identified_date",
        )
        for issue in rows:
            facts.append(_fact(
                issue, project=issue.project.name if issue.project else UNASSIGNED,
                project_id=issue.project_id,
                portfolio=portfolios.get(issue.project_id, UNASSIGNED),
                status=issue.status, severity=issue.get_severity_display(),
                kind=issue.get_issue_type_display(), resource=_name(issue.owner),
                date_value=issue.identified_date, due_value=issue.due_date, task_count=1,
                is_open=issue.status != "closed", is_done=issue.status == "closed",
            ))
    elif subject == "defect":
        rows = _scoped(
            QualityDefect.objects.select_related("project"),
            tenant, start, end, scope, "identified_date",
        )
        for defect in rows:
            facts.append(_fact(
                defect, project=defect.project.name if defect.project else UNASSIGNED,
                project_id=defect.project_id,
                portfolio=portfolios.get(defect.project_id, UNASSIGNED),
                status=defect.status, severity=defect.get_severity_display(),
                category=defect.get_defect_category_display(), kind=defect.get_disposition_display(),
                date_value=defect.identified_date, due_value=defect.due_date, task_count=1,
                is_open=defect.status not in ("closed", "resolved"), is_done=defect.status == "closed",
            ))
    elif subject == "change_order":
        rows = _scoped(
            ScopeChangeRequest.objects.select_related("project"),
            tenant, start, end, scope, "created_at",
        )
        for change in rows:
            facts.append(_fact(
                change, project=change.project.name if change.project else UNASSIGNED,
                project_id=change.project_id,
                portfolio=portfolios.get(change.project_id, UNASSIGNED),
                status=change.status, priority=change.get_priority_display(),
                amount=change.cost_impact, exposure=change.cost_impact,
                date_value=change.created_at.date(), task_count=1,
                is_open=change.status not in ("implemented", "rejected", "cancelled"),
                is_done=change.status in ("approved", "implemented"),
            ))
    elif subject == "requirement":
        rows = _scoped(
            Requirement.objects.select_related("project"), tenant, None, None, scope
        )
        for requirement in rows:
            facts.append(_fact(
                requirement,
                project=requirement.project.name if requirement.project else UNASSIGNED,
                project_id=requirement.project_id, status=requirement.status,
                priority=requirement.get_priority_display(),
                kind=requirement.get_requirement_type_display(),
                date_value=requirement.created_at.date(), task_count=1,
                is_open=requirement.status not in ("verified", "closed"),
                is_done=requirement.status == "verified",
            ))
    elif subject == "sprint":
        rows = _scoped(
            Sprint.objects.select_related("project"), tenant, start, end, scope, "start_date"
        )
        for sprint in rows:
            facts.append(_fact(
                sprint, project=sprint.project.name if sprint.project else UNASSIGNED,
                project_id=sprint.project_id, status=sprint.status,
                date_value=sprint.start_date, actual_value=sprint.end_date,
                planned_value=sprint.start_date, amount=sprint.committed_points,
                task_count=sprint.committed_points,
                is_open=sprint.status not in ("completed", "cancelled"),
                is_done=sprint.status == "completed",
            ))
    elif subject == "time_entry":
        rows = _scoped(
            ResourceTimeEntry.objects.select_related("project", "resource"),
            tenant, start, end, scope, "entry_date",
        )
        for entry in rows:
            facts.append(_fact(
                entry, project=entry.project.name if entry.project else UNASSIGNED,
                project_id=entry.project_id,
                portfolio=portfolios.get(entry.project_id, UNASSIGNED),
                status=entry.status, resource=_name(entry.resource),
                activity=entry.activity_code or UNASSIGNED,
                date_value=entry.entry_date, hours=entry.hours,
                billable=entry.hours if entry.is_billable else Decimal("0"),
                task_count=1, is_open=entry.status == "draft", is_done=entry.status == "approved",
            ))
    elif subject == "resource_allocation":
        rows = _scoped(
            ResourceAllocation.objects.select_related("project", "resource"),
            tenant, start, end, scope, "start_date",
        )
        for allocation in rows:
            facts.append(_fact(
                allocation,
                project=allocation.project.name if allocation.project else UNASSIGNED,
                project_id=allocation.project_id,
                portfolio=portfolios.get(allocation.project_id, UNASSIGNED),
                status=allocation.booking_status, resource=_name(allocation.resource),
                role=allocation.role_name or UNASSIGNED, date_value=allocation.start_date,
                hours=allocation.total_hours, task_count=1,
                is_open=allocation.booking_status not in ("released", "cancelled"),
            ))
    elif subject == "cost":
        rows = _scoped(
            ProjectExpense.objects.select_related("project"), tenant, start, end, scope, "entry_date"
        )
        for expense in rows:
            facts.append(_fact(
                expense, project=expense.project.name if expense.project else UNASSIGNED,
                project_id=expense.project_id,
                portfolio=portfolios.get(expense.project_id, UNASSIGNED),
                status=expense.status, kind=expense.get_entry_type_display(),
                client=_name(expense.vendor), date_value=expense.entry_date,
                amount=expense.amount, task_count=1,
                is_open=expense.status == "draft", is_done=expense.status == "posted",
            ))
    elif subject == "invoice":
        rows = _scoped(
            ProjectClientInvoice.objects.select_related("project"),
            tenant, start, end, scope, "billing_date",
        )
        for invoice in rows:
            facts.append(_fact(
                invoice, project=invoice.project.name if invoice.project else UNASSIGNED,
                project_id=invoice.project_id,
                portfolio=portfolios.get(invoice.project_id, UNASSIGNED),
                status=invoice.status, kind=invoice.get_billing_type_display(),
                date_value=invoice.billing_date, due_value=invoice.due_date,
                amount=invoice.total_amount, task_count=1,
                is_open=invoice.status not in ("paid", "cancelled"), is_done=invoice.status == "paid",
            ))
    elif subject == "quality_review":
        from apps.projects.models import QualityReview

        rows = _scoped(
            QualityReview.objects.select_related("project"),
            tenant, start, end, scope, "review_date",
        )
        for review in rows:
            facts.append(_fact(
                review, project=review.project.name if review.project else UNASSIGNED,
                project_id=review.project_id, status=review.status,
                kind=review.get_review_type_display(), date_value=review.review_date,
                task_count=1, is_open=review.status not in ("closed", "completed"),
                is_done=review.status in ("closed", "completed"),
            ))
    elif subject == "document":
        from apps.projects.models import ProjectDocument

        rows = _scoped(ProjectDocument.objects.select_related("project"), tenant, None, None, scope)
        for document in rows:
            facts.append(_fact(
                document, project=document.project.name if document.project else UNASSIGNED,
                project_id=document.project_id, status=document.status,
                kind=document.get_document_type_display(),
                date_value=document.created_at.date(), task_count=1,
                is_open=document.status in ("draft", "in_review"), is_done=document.status == "approved",
            ))
    elif subject == "payment":
        caveats.append(
            "Cash is owned by the accounting ledger (L29). Use Billing Summary for the invoice-level "
            "view of what has been billed, collected and aged."
        )
        return [], caveats
    else:
        caveats.append(f"Unknown register '{subject}' — no data returned.")

    return facts, caveats


# =================================================================================================
# The pivot engine — one implementation serves every question
# =================================================================================================
def _group_value(fact, dimension):
    return {
        "project": lambda: fact["project"] or UNASSIGNED,
        "portfolio": lambda: fact["portfolio"] or UNASSIGNED,
        "client": lambda: fact["client"] or UNASSIGNED,
        "org_unit": lambda: fact["org_unit"] or UNASSIGNED,
        "resource": lambda: fact["resource"] or UNASSIGNED,
        "role": lambda: fact["role"] or UNASSIGNED,
        "activity_code": lambda: fact["activity"] or UNASSIGNED,
        "wbs_phase": lambda: fact["wbs_phase"] or UNASSIGNED,
        "milestone_status": lambda: fact["status"] or UNASSIGNED,
        "task_type": lambda: fact["kind"] or UNASSIGNED,
        "priority": lambda: fact["priority"] or fact["severity"] or UNASSIGNED,
        "status": lambda: fact["status"] or UNASSIGNED,
        "risk_category": lambda: fact["category"] or UNASSIGNED,
        "severity": lambda: fact["severity"] or UNASSIGNED,
        "defect_severity": lambda: fact["severity"] or UNASSIGNED,
        "month": lambda: fact["month"].strftime("%Y-%m") if fact["month"] else UNASSIGNED,
        "quarter": lambda: (
            f"{fact['month'].year}-Q{(fact['month'].month - 1) // 3 + 1}" if fact["month"]
            else UNASSIGNED
        ),
    }.get(dimension, lambda: "All rows")()


def _aggregate(facts, evm_map):
    """Reduce one group's facts to every measure's value — one pass, so the requested subset is sliced
    out afterwards rather than driving the arithmetic.

    EVM ratios are derived from SUMMED components (``CPI = ΣEV / ΣAC``) and never averaged across
    projects — averaging a ratio is the classic roll-up error this engine exists to prevent.
    """
    project_ids = {fact["project_id"] for fact in facts if fact.get("project_id")}
    evm = {key: Decimal("0") for key in ("bac", "pv", "ev", "ac")}
    for project_id in project_ids:
        account = evm_map.get(project_id) or {}
        for key in evm:
            evm[key] += Decimal(account.get(key) or 0)

    hours = sum((fact["hours"] for fact in facts), Decimal("0"))
    billable = sum((fact["billable"] for fact in facts), Decimal("0"))
    amount = sum((fact["amount"] for fact in facts), Decimal("0"))
    exposure = sum((fact["exposure"] for fact in facts), Decimal("0"))

    slipped = [
        days for fact in facts
        if (days := _slip_days(fact["actual"], fact["planned"])) is not None
    ]
    delivered = [fact for fact in facts if fact["due"] and fact["actual"]]
    on_time = sum(
        1 for fact in delivered
        if (_slip_days(fact["actual"], fact["due"]) or 0) <= 0
    )
    newest = max((fact["date"] for fact in facts if fact["date"]), default=None)
    ageing = [
        (newest - fact["date"]).days for fact in facts
        if fact["is_open"] and fact["date"] and newest and fact["date"] <= newest
    ]

    return {
        "planned_value": evm["pv"],
        "earned_value": evm["ev"],
        "actual_cost": evm["ac"],
        "budget_at_completion": evm["bac"],
        "eac": ((evm["bac"] / evm["ac"] * evm["ev"]) if evm["ac"] else None),
        "cv": (evm["ev"] - evm["ac"]) if (evm["ev"] or evm["ac"]) else None,
        "cv_pct": _pct(evm["ev"] - evm["ac"], evm["pv"]),
        "sv": (evm["ev"] - evm["pv"]) if (evm["ev"] or evm["pv"]) else None,
        "sv_pct": _pct(evm["ev"] - evm["pv"], evm["bac"]),
        "cpi": (evm["ev"] / evm["ac"]).quantize(Decimal("0.0001")) if evm["ac"] else None,
        "spi": (evm["ev"] / evm["pv"]).quantize(Decimal("0.0001")) if evm["pv"] else None,
        "margin_pct": _margin_pct(amount, evm["ac"]),
        "hours": hours,
        "billable_pct": _pct(billable, hours),
        # Capacity lives on allocations, not on the rows this register counts; a report that needs it
        # groups by resource/project and reads the two values side by side rather than a fake ratio.
        "utilization_pct": None,
        "task_count": len(facts),
        "open_count": sum(1 for fact in facts if fact["is_open"]),
        "completed_count": sum(1 for fact in facts if fact["is_done"]),
        "on_time_pct": _pct(on_time, len(delivered)),
        "slip_days": (
            (Decimal(sum(slipped)) / Decimal(len(slipped))).quantize(Decimal("0.1")) if slipped else None
        ),
        "exposure_value": exposure,
        "aging_days": (
            (Decimal(sum(ageing)) / Decimal(len(ageing))).quantize(Decimal("0.1")) if ageing else None
        ),
        "invoiced_amount": amount,
        # Unbilled = work earned but not yet invoiced. Only meaningful where both sides exist.
        "unbilled_amount": (
            max(evm["ev"] - amount, Decimal("0")) if (evm["ev"] or amount) else None
        ),
    }


def _sort_rows(rows, sort_key, top_n):
    def weight(row):
        value = row.get(sort_key)
        if isinstance(value, (int, float, Decimal)):
            return value
        return None

    rows.sort(key=lambda row: (weight(row) is None, -(weight(row) or 0), str(row.get("label"))))
    return rows[:top_n] if top_n else rows


def compute_report(report, *, as_of=None):
    """Compute one stored question into the payload a run will freeze — the nine JSON-safe keys of B3.4.

    ``report`` may be a saved ``ProjectReport`` or the unsaved instance a builder form just produced;
    both expose the same attributes, which is what lets the preview and a real run share one engine.
    **Nothing is written here** — freezing a result into ``ProjectReportRun`` is the view's job, inside
    its own transaction, so this stays safely callable from a page render.
    """
    return _compute(_spec_of(report), getattr(report, "tenant_id", None), as_of=as_of)


def _spec_of(report):
    """A ``ProjectReport`` instance (saved or not) → the plain dict the engine consumes.

    Attribute reads, never a query: the scope is carried as FK ids precisely so an unsaved instance with
    no primary key still produces a spec.
    """
    return {
        "report_type": report.report_type,
        "subject": report.subject,
        "measures": list(report.measures or []),
        "dimension_1": report.dimension_1,
        "dimension_2": report.dimension_2,
        "date_range": report.date_range,
        "date_from": report.date_from,
        "date_to": report.date_to,
        "as_of": report.as_of,
        "chart_type": report.chart_type,
        "top_n": report.top_n,
        "sort_by": report.sort_by,
        "project_id": report.project_id,
        "portfolio_id": report.portfolio_id,
        "client_id": report.client_id,
        "org_unit_id": report.org_unit_id,
    }


def _compute(spec, tenant, as_of=None):
    """The engine behind :func:`compute_report` and :func:`standard_report` — spec in, payload out."""
    if tenant is None:
        return json_safe(_empty_payload(
            "No workspace is bound to this request — module data is only visible to a tenant account.",
            spec,
        ))

    subject, measures, dimensions = _axes(spec)
    as_of = as_of or spec.get("as_of")
    start, end, resolved_as_of = _date_window(
        spec.get("date_range") or "last_90", spec.get("date_from"), spec.get("date_to"), as_of
    )
    scope = {
        "project_id": spec.get("project_id"),
        "portfolio_id": spec.get("portfolio_id"),
        "client_id": spec.get("client_id"),
        "org_unit_id": spec.get("org_unit_id"),
    }
    scope["project_ids"] = _scope_project_ids(tenant, scope)

    facts, caveats = _load_facts(subject, tenant, start, end, resolved_as_of, scope)
    if not facts:
        payload = _empty_payload(
            "No rows matched this question in the selected window.", spec, caveats=caveats
        )
        payload["window"] = {"from": start, "to": end, "as_of": resolved_as_of}
        return json_safe(payload)

    project_ids = {fact["project_id"] for fact in facts if fact.get("project_id")}
    evm_map = _evm_map(tenant, project_ids, resolved_as_of)

    needs_evm = {
        "planned_value", "earned_value", "actual_cost", "budget_at_completion", "eac",
        "cv", "cv_pct", "sv", "sv_pct", "cpi", "spi", "margin_pct", "unbilled_amount",
    }
    if project_ids and not evm_map and needs_evm & set(measures):
        caveats.append(
            "No 7.4 cost control account exists for these projects, so the EVM measures have no value."
        )

    grouped = {}
    for fact in facts:
        key = tuple(_group_value(fact, dim) for dim in dimensions)
        grouped.setdefault(key, []).append(fact)

    rows = []
    for key, members in grouped.items():
        values = _aggregate(members, evm_map)
        row = {"label": key[0], "sublabel": key[1] if len(key) > 1 else "", "count": len(members)}
        row.update({measure: values.get(measure) for measure in measures})
        rows.append(row)

    group_count = len(rows)
    top_n = min(MAX_REGISTER_ROWS, spec.get("top_n") or 100)
    sort_by = spec.get("sort_by") or measures[0]
    rows = _sort_rows(rows, sort_by, top_n)

    # The honest truncation claim compares the GROUPS against what is actually rendered — ``top_n``
    # cuts well before MAX_REGISTER_ROWS, and a flag that only watched the cap would tell a reader
    # nothing was dropped while 50 of 150 groups sat off the page.
    truncated = group_count > len(rows)
    if truncated:
        caveats.append(
            f"This question groups into {group_count} rows; the {len(rows)} with the strongest "
            f"{_MEASURE_LABELS.get(sort_by, sort_by)} are shown. Narrow the window or the scope."
        )
    if "utilization_pct" in measures:
        caveats.append(
            "Utilization needs allocated capacity; pick the Resource Utilization report or a resource "
            "dashboard tile for the booked-vs-allocated ratio."
        )

    dimensions_shown = 2 if len(dimensions) > 1 else 1
    columns = [_DIMENSION_LABELS.get(dim, dim) for dim in dimensions[:dimensions_shown]]
    columns.append("Rows")
    columns += [_MEASURE_LABELS.get(measure, measure) for measure in measures]

    table_rows = [
        [row["label"], *([row["sublabel"]] if dimensions_shown > 1 else []), row["count"],
         *[_format_measure(measure, row.get(measure)) for measure in measures]]
        for row in rows
    ]

    first_measure = sort_by if sort_by in measures else measures[0]
    payload = {
        "columns": columns,
        "rows": table_rows,
        "chart_type": spec.get("chart_type") or "table",
        "chart_labels": [row["label"] for row in rows],
        "chart_data": [row.get(first_measure) for row in rows],
        "chart_dataset_label": _MEASURE_LABELS.get(first_measure, first_measure),
        "caveats": caveats,
        "truncated": truncated,
        "group_count": group_count,
        "rating": _rating_of(rows, first_measure),
        "summary": _summary_cards(rows, measures, facts),
        "window": {"from": start, "to": end, "as_of": resolved_as_of},
        "subject": subject,
        "measures": measures,
        "dimensions": dimensions,
        "sort_by": first_measure,
    }
    return json_safe(payload)


def _axes(spec):
    """Normalise the question's axes once — shared by the engine and its empty answer, so the two
    payloads can never disagree about which measures they describe."""
    spec = spec or {}
    subject = spec.get("subject") or "project"
    measures = [m for m in (spec.get("measures") or []) if m][:3] or ["task_count"]
    dimensions = [d for d in (spec.get("dimension_1"), spec.get("dimension_2"))
                  if d and d != "none"] or ["project"]
    return subject, measures, dimensions


def _empty_payload(message, spec, caveats=None):
    subject, measures, dimensions = _axes(spec)
    return {
        "columns": [_DIMENSION_LABELS.get(dimensions[0], dimensions[0]), "Rows"]
        + [_MEASURE_LABELS.get(m, m) for m in measures],
        "rows": [], "chart_labels": [], "chart_data": [], "chart_dataset_label": "",
        "chart_type": (spec or {}).get("chart_type") or "table",
        "caveats": list(caveats or []) + [message],
        "truncated": False, "group_count": 0, "rating": "", "summary": {},
        "subject": subject, "measures": measures, "dimensions": dimensions,
        "sort_by": measures[0], "window": None,
    }


def summary_pairs(summary):
    """``{label: display}`` → the ``[{label, value}]`` list the KPI strip iterates.

    ``ProjectReportRun.summary_cards`` (A1.5) carries the identical three lines, because a model must not
    import this module — the duplication is the price of the one-way edge, and a test pins both outputs.
    """
    return [{"label": label, "value": value} for label, value in (summary or {}).items()]


def _rating_of(rows, measure):
    """A RAG letter for a computed result — the string a frozen run stores so history can be counted.

    Absence of data is never red: an empty register is not a distressed project.
    """
    values = [
        row.get(measure) for row in rows
        if isinstance(row.get(measure), (int, float, Decimal))
    ]
    if not values:
        return ""
    worst = min(values)
    if measure in ("cpi", "spi"):
        return "red" if worst < Decimal("0.9") else ("amber" if worst < Decimal("1.0") else "green")
    if measure.endswith("_pct"):
        return "red" if worst < Decimal("50") else ("amber" if worst < Decimal("80") else "green")
    if measure in ("cv", "sv"):
        return "red" if worst < 0 else "green"
    if measure == "slip_days":
        return "red" if worst > Decimal("10") else ("amber" if worst > 0 else "green")
    return ""


def _summary_cards(rows, measures, facts):
    """The KPI strip as ``{label: display}`` — the frozen shape a run stores (A1.5/D7).

    ``Rows`` counts the whole register; additive measures total the displayed slice and ratios average
    it, because a sum of percentages is not a thing anyone means.
    """
    cards = {"Rows": _num(len(facts))}
    for measure in measures:
        values = [
            row.get(measure) for row in rows
            if isinstance(row.get(measure), (int, float, Decimal))
        ]
        if not values:
            continue
        total = sum(values, Decimal("0"))
        shown = total if measure in (
            "hours", "task_count", "open_count", "completed_count",
            "invoiced_amount", "unbilled_amount", "exposure_value",
            "planned_value", "earned_value", "actual_cost", "budget_at_completion",
            "cv", "sv",
        ) else total / Decimal(len(values))
        cards[_MEASURE_LABELS.get(measure, measure)] = _format_measure(measure, shown)
    return cards


#: The 15 canned answers. Each is AXES over the one engine — there is deliberately no per-kind
#: ``computer`` callable, because a second arithmetic for each report is how two reports end up
#: disagreeing about the same number. ``custom`` is absent by contract: it is the builder's own kind.
STANDARD_REPORTS = {
    "status_report": {"subject": "project", "measures": ["completed_count", "open_count"],
                      "dimension_1": "project", "chart_type": "table"},
    "milestone_summary": {"subject": "milestone", "measures": ["on_time_pct", "completed_count"],
                          "dimension_1": "milestone_status", "chart_type": "bar"},
    "schedule_variance": {"subject": "task", "measures": ["slip_days", "on_time_pct"],
                          "dimension_1": "project", "chart_type": "bar"},
    "risk_register": {"subject": "risk", "measures": ["exposure_value", "open_count"],
                      "dimension_1": "risk_category", "chart_type": "table"},
    "issue_log": {"subject": "issue", "measures": ["open_count", "aging_days"],
                  "dimension_1": "severity", "chart_type": "bar"},
    "quality_defect_summary": {"subject": "defect", "measures": ["open_count", "task_count"],
                               "dimension_1": "defect_severity", "chart_type": "doughnut"},
    "scope_change_summary": {"subject": "change_order", "measures": ["task_count", "exposure_value"],
                             "dimension_1": "status", "chart_type": "table"},
    "cost_variance": {"subject": "cost", "measures": ["cv", "cv_pct"],
                      "dimension_1": "project", "chart_type": "bar"},
    "earned_value": {"subject": "cost", "measures": ["planned_value", "earned_value", "actual_cost"],
                     "dimension_1": "project", "chart_type": "line"},
    "resource_utilization": {"subject": "resource_allocation",
                             "measures": ["hours", "billable_pct"], "dimension_1": "resource",
                             "chart_type": "bar"},
    "time_entry": {"subject": "time_entry", "measures": ["hours", "billable_pct"],
                   "dimension_1": "activity_code", "chart_type": "bar"},
    "billing_summary": {"subject": "invoice", "measures": ["invoiced_amount", "unbilled_amount"],
                        "dimension_1": "status", "chart_type": "table"},
    "agile_throughput": {"subject": "sprint", "measures": ["completed_count", "task_count"],
                         "dimension_1": "month", "chart_type": "line"},
    "portfolio_health": {"subject": "project", "measures": ["open_count", "on_time_pct"],
                         "dimension_1": "portfolio", "chart_type": "heat"},
    "steering_pack": {"subject": "project", "measures": ["cpi", "spi", "on_time_pct"],
                      "dimension_1": "project", "chart_type": "table"},
}
for _key, _entry in STANDARD_REPORTS.items():
    _entry["label"] = dict(REPORT_TYPE_CHOICES).get(_key, _key)
del _key, _entry

#: What a caller may narrow a canned report by. Axes are NOT in this list on purpose — the registry owns
#: them, so a query string cannot make a shared report ask a different question (L11's cousin).
REPORT_PARAM_KEYS = (
    "project_id", "portfolio_id", "client_id", "org_unit_id", "as_of", "top_n", "date_range",
)


def standard_report(kind, tenant, params=None):
    """Render one canned kind. ``params`` is filtered to :data:`REPORT_PARAM_KEYS` before it is merged,
    so the axes always come from the registry — the same reason ``report_type`` is not a query param."""
    entry = STANDARD_REPORTS.get(kind)
    spec = dict(entry or STANDARD_REPORTS["status_report"])
    spec.pop("label", None)
    spec["report_type"] = kind if entry else "status_report"
    for key in REPORT_PARAM_KEYS:
        value = (params or {}).get(key)
        if value is not None:
            spec[key] = value
    payload = _compute(spec, tenant, as_of=spec.get("as_of"))
    if entry is None:
        payload["caveats"] = [
            f"No standard report is registered as '{kind}', so the status report is shown instead."
        ] + payload["caveats"]
    payload["kind"] = spec["report_type"]
    payload["kind_label"] = dict(REPORT_TYPE_CHOICES).get(kind, kind)
    return payload


#: The three RAG letters and the words that ride beside them. A colour-only cell is invisible to a screen
#: reader and to roughly 8% of readers with a red/green deficiency, so a heat band always renders both.
_RAG_BANDS = [("green", "On track"), ("amber", "Watch"), ("red", "Off track")]
_RAG_KEYS = {key for key, _label in _RAG_BANDS}

#: Letter → colour-named badge class (L33). ``ProjectReportRun`` carries its own identical three lines
#: because a model must not import this module — the same price as ``summary_pairs``/``summary_cards``.
_RAG_CSS = {key: f"badge-{key}" for key, _label in _RAG_BANDS}

_CHART_LABELS = dict(CHART_CHOICES)

#: 7.4's ``CostControlAccount.health`` state words → the RAG letter a pack prints. The one place the two
#: vocabularies are bridged, so the heat tile and the steering bands can never disagree.
_HEALTH_RAG = {
    "under": "green", "ok": "green", "green": "green",
    "watch": "amber", "amber": "amber",
    "over": "red", "red": "red",
}

#: A gauge needs a ceiling to be a gauge. A percentage tops out at 100 and a CPI/SPI dial is meaningful
#: against 2.0; a money or count scalar has no natural ceiling, so it gets none and renders as a KPI card.
_GAUGE_MAX = {"pct": Decimal("100"), "index": Decimal("2")}

#: What a tile falls back to when its stored chart kind cannot carry its metric.
_TILE_FALLBACK_CHART = {"scalar": "kpi", "series": "bar", "table": "table"}

#: Series whose values add up to something a reader would call a total (a percentage does not).
_TOTAL_UNITS = ("count", "hours", "money")


# =================================================================================================
# Widgets — one bounded aggregate each, so a dashboard is a handful of queries
# =================================================================================================
WIDGET_COMPUTE = {}


def _widget(func):
    """Register a tile's compute under its own name: ``_tile_<metric>`` -> metric ``<metric>``.

    The name is the key, so a registry row and its compute cannot drift apart; the parity assert
    below is what turns a missing or misspelled one into an import error instead of a dead tile.
    """
    WIDGET_COMPUTE[func.__name__.removeprefix("_tile_")] = func
    return func


def _tile_qs(model, tenant, project_ids=None):
    """The one bounded read a tile may issue: tenant first, then the tile's own scope (A1.3).

    ``project_ids`` is ``None`` for an unscoped tile and a concrete id list otherwise — passing the
    resolved set rather than the FK keeps a portfolio-scoped tile honest without a second join.
    """
    qs = model.objects.filter(tenant=tenant)
    return qs if project_ids is None else qs.filter(project_id__in=project_ids)


def _windowed(qs, field, start, end):
    """Date-window an already tenant-and-scope-bounded queryset."""
    return qs.filter(**_within(field, start, end))


def _label_series(qs, field, label_map):
    """Group a choice field into ``{label: count}``, bucketing nulls visibly instead of losing them."""
    out = {}
    for row in qs.values(field).annotate(value=Count("id")):
        label = label_map.get(row[field]) or row[field] or UNASSIGNED
        out[str(label)] = row["value"]
    return out


@_widget
def _tile_kpi_active_projects(tenant, start, end, project_ids):
    return _tile_qs(Project, tenant, project_ids).filter(
        status="active").count()


@_widget
def _tile_kpi_overdue_tasks(tenant, start, end, project_ids):
    return _tile_qs(ProjectTask, tenant, project_ids).filter(
        planned_end__lt=timezone.localdate()
    ).exclude(status__in=("done", "cancelled")).count()


@_widget
def _tile_kpi_open_risks(tenant, start, end, project_ids):
    return _tile_qs(ProjectRisk, tenant, project_ids).exclude(status="closed").count()


@_widget
def _tile_kpi_open_issues(tenant, start, end, project_ids):
    return _tile_qs(ProjectIssue, tenant, project_ids).exclude(status="closed").count()


@_widget
def _tile_kpi_open_defects(tenant, start, end, project_ids):
    return _tile_qs(QualityDefect, tenant, project_ids).exclude(
        status__in=("closed", "resolved")
    ).count()


@_widget
def _tile_kpi_cpi(tenant, start, end, project_ids):
    totals = _totals(tenant, project_ids)
    return (totals["ev"] / totals["ac"]).quantize(Decimal("0.0001")) if totals["ac"] else None


@_widget
def _tile_kpi_spi(tenant, start, end, project_ids):
    totals = _totals(tenant, project_ids)
    return (totals["ev"] / totals["pv"]).quantize(Decimal("0.0001")) if totals["pv"] else None


@_widget
def _tile_kpi_utilization_pct(tenant, start, end, project_ids):
    booked_qs = _windowed(_tile_qs(ResourceTimeEntry, tenant, project_ids), "entry_date", start, end)
    booked = booked_qs.aggregate(value=Sum("hours"))["value"] or Decimal("0")
    allocated_qs = _windowed(
        _tile_qs(ResourceAllocation, tenant, project_ids), "start_date", start, end)
    allocated = allocated_qs.aggregate(value=Sum("total_hours"))["value"] or Decimal("0")
    return _pct(booked, allocated)


@_widget
def _tile_kpi_billable_pct(tenant, start, end, project_ids):
    rows = _windowed(_tile_qs(ResourceTimeEntry, tenant, project_ids), "entry_date", start, end)
    total = rows.aggregate(value=Sum("hours"))["value"] or Decimal("0")
    billable = rows.filter(is_billable=True).aggregate(value=Sum("hours"))["value"] or Decimal("0")
    return _pct(billable, total)


@_widget
def _tile_kpi_unbilled_amount(tenant, start, end, project_ids):
    totals = _totals(tenant, project_ids)
    return max(totals["ev"] - totals["invoiced"], Decimal("0"))


@_widget
def _tile_kpi_schedule_slip_days(tenant, start, end, project_ids):
    slipped = [
        days for milestone in _tile_qs(ProjectMilestone, tenant, project_ids).exclude(
            actual_date=None
        ).only("target_date", "actual_date")
        if (days := _slip_days(milestone.actual_date, milestone.target_date)) is not None and days > 0
    ]
    if not slipped:
        return None
    return (Decimal(sum(slipped)) / Decimal(len(slipped))).quantize(Decimal("0.1"))


@_widget
def _tile_projects_by_status(tenant, start, end, project_ids):
    return _label_series(
        _tile_qs(Project, tenant, project_ids), "status", dict(Project.STATUS_CHOICES)
    )


@_widget
def _tile_tasks_by_status(tenant, start, end, project_ids):
    return _label_series(
        _windowed(_tile_qs(ProjectTask, tenant, project_ids), "planned_end", start, end),
        "status", dict(ProjectTask.STATUS_CHOICES),
    )


@_widget
def _tile_risks_by_category(tenant, start, end, project_ids):
    return _label_series(
        _tile_qs(ProjectRisk, tenant, project_ids), "category", dict(ProjectRisk.CATEGORY_CHOICES)
    )


@_widget
def _tile_issues_by_severity(tenant, start, end, project_ids):
    return _label_series(
        _tile_qs(ProjectIssue, tenant, project_ids), "severity", dict(ProjectIssue.SEVERITY_CHOICES)
    )


@_widget
def _tile_defects_by_severity(tenant, start, end, project_ids):
    return _label_series(
        _tile_qs(QualityDefect, tenant, project_ids), "severity",
        dict(QualityDefect.SEVERITY_CHOICES),
    )


@_widget
def _tile_hours_by_activity_code(tenant, start, end, project_ids):
    out = {}
    for row in _windowed(_tile_qs(ResourceTimeEntry, tenant, project_ids), "entry_date", start, end).values(
        "activity_code"
    ).annotate(value=Sum("hours")):
        out[row["activity_code"] or UNASSIGNED] = row["value"] or Decimal("0")
    return out


@_widget
def _tile_cost_variance_by_project(tenant, start, end, project_ids):
    return {
        row["label"]: row["value"]
        for row in _project_measure_rows(tenant, project_ids, lambda account: account["cv"])
    }


@_widget
def _tile_ev_curve_by_month(tenant, start, end, project_ids):
    """Posted 7.4 expense value per month. The EVM properties are as-of-today by design, so a monthly
    curve built from them would be one full re-evaluation per month; posted cost is the honest series."""
    rows = _tile_qs(ProjectExpense, tenant, project_ids).filter(
        status="posted"
    ).annotate(month=TruncMonth("entry_date")).values("month").annotate(
        value=Sum("amount")
    ).order_by("month")
    return {
        (row["month"].strftime("%Y-%m") if row["month"] else UNASSIGNED): (row["value"] or Decimal("0"))
        for row in rows
    }


@_widget
def _tile_utilization_by_resource(tenant, start, end, project_ids):
    booked, capacity = {}, {}
    for entry in _windowed(
    _tile_qs(ResourceTimeEntry, tenant, project_ids).select_related("resource"), "entry_date", start, end
    ):
        key = _name(entry.resource)
        booked[key] = booked.get(key, Decimal("0")) + (entry.hours or Decimal("0"))
    for allocation in _windowed(
    _tile_qs(ResourceAllocation, tenant, project_ids).select_related("resource"), "start_date", start, end
    ):
        key = _name(allocation.resource)
        capacity[key] = capacity.get(key, Decimal("0")) + (allocation.total_hours or Decimal("0"))
    return {
        name: _pct(booked.get(name, Decimal("0")), capacity.get(name, Decimal("0")))
        for name in sorted(set(booked) | set(capacity))
    }


@_widget
def _tile_milestones_on_time_by_month(tenant, start, end, project_ids):
    out = {}
    milestones = _windowed(
        _tile_qs(ProjectMilestone, tenant, project_ids).exclude(actual_date=None),
        "actual_date", start, end,
    )
    for milestone in milestones:
        month = _month_of(milestone.actual_date)
        if not month:
            continue
        key = month.strftime("%Y-%m")
        late = (_slip_days(milestone.actual_date, milestone.target_date) or 0) > 0
        bucket = out.setdefault(key, {"on_time": 0, "late": 0})
        bucket["late" if late else "on_time"] += 1
    return {key: bucket["on_time"] for key, bucket in sorted(out.items())}


@_widget
def _tile_health_heat_bands(tenant, start, end, project_ids):
    bands = {key: 0 for key, _label in _RAG_BANDS}
    for account in _evm_map(tenant, _tenant_project_ids(tenant, project_ids)).values():
        rating = _HEALTH_RAG.get(account.get("health") or "")
        if rating:
            bands[rating] += 1
    return bands


@_widget
def _tile_top_cost_variance_projects(tenant, start, end, project_ids):
    rows = _project_measure_rows(tenant, project_ids, lambda account: account["cv"])
    return {
        "columns": ["Project", "Cost variance"],
        "rows": [[row["label"], _format_unit("money", row["value"])] for row in rows[:10]],
        "total": len(rows),
    }


@_widget
def _tile_top_risk_exposure_projects(tenant, start, end, project_ids):
    rows = _risk_exposure_grouped(tenant, project_ids)
    return {
        "columns": ["Project", "Open risk exposure"],
        "rows": [[row["label"], _format_unit("money", row["value"])] for row in rows[:10]],
        "total": len(rows),
    }


@_widget
def _tile_overdue_milestones(tenant, start, end, project_ids):
    cutoff = end or timezone.localdate()
    milestones = _tile_qs(ProjectMilestone, tenant, project_ids).filter(
        target_date__lt=cutoff, status__in=("planned", "in_review")
    ).select_related("project").order_by("target_date")
    total = milestones.count()
    return {
        "columns": ["Milestone", "Planned", "Days late"],
        "rows": [
            [
                f"{milestone.name} · {milestone.project.name if milestone.project else UNASSIGNED}",
                milestone.target_date.isoformat(),
                _format_unit("days", (cutoff - milestone.target_date).days),
            ]
            for milestone in milestones[:10]
        ],
        "total": total,
    }


# Every registry row must have a compute and every compute a registry row. Loud at import, not
# as a permanently blank tile.
assert set(WIDGET_COMPUTE) == set(WIDGET_METRICS), (
    "tile registry drift: "
    f"missing {sorted(set(WIDGET_METRICS) - set(WIDGET_COMPUTE))}, "
    f"unknown {sorted(set(WIDGET_COMPUTE) - set(WIDGET_METRICS))}"
)


def _tenant_project_ids(tenant, project_ids=None):
    return list(
        _tile_qs(Project, tenant, project_ids).values_list("id", flat=True)[:MAX_EVM_PROJECTS]
    )


def _project_measure_rows(tenant, project_ids, pick):
    """One EVM read per project, labelled — the shared body of the cost-variance tile and table."""
    evm_map = _evm_map(tenant, _tenant_project_ids(tenant, project_ids))
    names = dict(_tile_qs(Project, tenant, project_ids).values_list("id", "name"))
    rows = [
        {"label": names.get(project_id, UNASSIGNED), "value": pick(account)}
        for project_id, account in evm_map.items()
    ]
    rows = [row for row in rows if row["value"] is not None]
    rows.sort(key=lambda row: row["value"])
    return rows


def _totals(tenant, project_ids=None):
    """ΣEV/ΣAC/ΣPV/ΣBAC plus what 7.15 has invoiced, in one pass over the scoped cost accounts."""
    evm_map = _evm_map(tenant, _tenant_project_ids(tenant, project_ids))
    invoiced = _tile_qs(ProjectClientInvoice, tenant, project_ids).exclude(
        status__in=("draft", "cancelled")
    ).aggregate(value=Sum("total_amount"))["value"] or Decimal("0")
    totals = {"ev": Decimal("0"), "ac": Decimal("0"), "pv": Decimal("0"),
              "bac": Decimal("0"), "invoiced": invoiced}
    for account in evm_map.values():
        for key in ("ev", "ac", "pv", "bac"):
            totals[key] += Decimal(account.get(key) or 0)
    return totals


def compute_widget(widget, *, date_range=None):
    """Evaluate one tile into the payload its template branch expects.

    ``date_range`` overrides ``widget.date_range`` WITHOUT mutating the row — that is how ``pdb_detail``'s
    ``?range=`` reaches every tile while the dashboard keeps the window its author saved (B2.4). The tile's
    own ``project``/``portfolio`` scope is resolved here and threaded into the compute call: a scoped tile
    that quietly answered with tenant-wide numbers would be worse than an empty one, because it would look
    right.

    A failing metric degrades to a caveat rather than raising — one broken tile must not 500 a dashboard.
    """
    entry = WIDGET_METRICS.get(widget.metric) or {}
    kind = entry.get("kind", "table")
    unit = entry.get("unit", "count")
    range_key = date_range or widget.date_range
    if range_key == "custom":  # a tile carries no date pair of its own to resolve
        range_key = "last_90"
    window = resolve_window(range_key)
    project_ids = _scope_project_ids(widget.tenant_id, {
        "project_id": widget.project_id,
        "portfolio_id": widget.portfolio_id,
    })
    caveats = []
    payload = {
        "kind": kind,
        "metric": widget.metric,
        "unit": unit,
        "chart_type": widget.chart_type,
        "drill_url_name": entry.get("drill_url_name") or "",
        "range_label": window["label"],
        "caveats": caveats,
    }

    def blank(error):
        """A tile that cannot answer is a scalar dash — one shape for every failure, so no template
        branch renders empty and no canvas config is built for a payload with no data."""
        return json_safe({
            **payload, "kind": "scalar", "chart_type": _TILE_FALLBACK_CHART["scalar"],
            "value": None, "display": "—", "max": None, "pct": None, "error": error,
        })

    func = WIDGET_COMPUTE.get(widget.metric)
    if func is None:
        caveats.append(f"Metric '{widget.metric}' has no compute implementation.")
        return blank("unknown metric")

    if widget.chart_type not in entry.get("charts", []):
        fallback = _TILE_FALLBACK_CHART[kind]
        caveats.append(
            f"'{widget.get_metric_display()}' cannot render as a "
            f"{_CHART_LABELS.get(widget.chart_type, widget.chart_type).lower()}; showing it as a "
            f"{_CHART_LABELS.get(fallback, fallback).lower()} instead."
        )
        payload["chart_type"] = fallback

    try:
        result = func(widget.tenant_id, window["start"], window["end"], project_ids)
        if kind == "scalar":
            payload.update(_scalar_tile(result, unit))
        elif kind == "series":
            payload.update(_series_tile(result, unit))
            _apply_heat_bands(payload, result, caveats)
        else:
            payload.update(_table_tile(result))
    except Exception as exc:  # noqa: BLE001 — a dashboard tile must never take the page down
        caveats.append(f"This tile could not be computed ({type(exc).__name__}).")
        return blank(type(exc).__name__)
    return json_safe(payload)


def _scalar_tile(value, unit):
    """The KPI card / gauge shape: the number, its display text, and the gauge geometry.

    ``max`` is the unit's natural ceiling and ``pct`` is where the value sits against it — ``None`` for a
    money or count scalar, which has no ceiling and therefore renders as a card, never as a dial.
    """
    ceiling = _GAUGE_MAX.get(unit)
    pct = None
    if value is not None and ceiling:
        ratio = Decimal(value) / ceiling * Decimal(100)
        pct = int(min(max(ratio, Decimal("0")), Decimal("100")))
    return {"value": value, "display": _format_unit(unit, value), "max": ceiling, "pct": pct}


def _series_tile(result, unit):
    """``{label: value}`` → the parallel arrays the canvas and its HTML fallback both read."""
    items = sorted((result or {}).items(), key=lambda pair: str(pair[0]))
    values = [value for _label, value in items]
    total = None
    if values and unit in _TOTAL_UNITS:
        total = sum((Decimal(value or 0) for value in values), Decimal("0"))
    return {
        "labels": [str(label) for label, _value in items],
        "data": values,
        "total": total,
    }


def _table_tile(result):
    """A table tile's own ``columns``/``rows`` — each table names its own columns, because one shared
    column list is how the exposure table and the days-late table ended up labelling each other's
    numbers. ``total`` is what the scope holds and ``rows`` is what fits, so ``truncated`` can be honest."""
    result = result or {}
    rows = result.get("rows") or []
    total = result.get("total")
    total = len(rows) if total is None else total
    return {
        "columns": result.get("columns") or [],
        "rows": rows,
        "total": total,
        "truncated": len(rows) < total,
    }


def _apply_heat_bands(payload, result, caveats):
    """A heat band is a RAG strip, not a generic series — so it only renders when the values ARE RAG.

    Anything else falls back to bars with a caveat rather than printing three confident zeroes for a
    series that was never green/amber/red (L8's blank-region trap, caught at the payload instead).
    """
    if payload["chart_type"] != "heat":
        return
    if result and set(result) <= _RAG_KEYS:
        payload["bands"] = [
            {"label": label, "count": int((result or {}).get(key) or 0), "css": _RAG_CSS[key]}
            for key, label in _RAG_BANDS
        ]
        return
    caveats.append(
        "Heat bands need a green/amber/red series, so this tile is shown as a bar chart instead.")
    payload["chart_type"] = _TILE_FALLBACK_CHART["series"]


# =================================================================================================
# Frozen-run readers — the only code that reads a stored run payload back, and it reads one key
# =================================================================================================
def _issued_ratings(tenant, *, as_of=None):
    """``[(report_id, project_id, rating)]`` for every issued run, newest first — ONE query.

    Every streak and every month bucket in this module is computed from a list like this, so a pack
    rendering sixty projects costs one read rather than sixty (B3.5's no-per-row-loop rule).
    """
    runs = ProjectReportRun.objects.filter(tenant=tenant, status="issued")
    if as_of is not None:
        runs = runs.filter(as_of__lte=as_of)
    return [
        (report_id, project_id, (payload or {}).get("rating") or "")
        for report_id, project_id, payload in runs.order_by("-generated_at", "-id").values_list(
            "report_id", "report__project_id", "data")[:MAX_REGISTER_ROWS]
    ]


def _rating_series(rows):
    """``{project_id: [rating, …]}`` newest-first, from the newest report bound to each project.

    Restricted to one report per project on purpose: two different questions can both be ``red`` for
    entirely unrelated reasons, and walking across that boundary would call it one long red streak.
    """
    by_report = {}
    chosen = {}
    for report_id, project_id, rating in rows:
        by_report.setdefault(report_id, []).append(rating)
        chosen.setdefault(project_id, report_id)
    return {
        project_id: by_report[report_id] for project_id, report_id in chosen.items()
    }


def _streak_result(rating, weeks):
    """The one place a streak becomes a sentence, so the pack and a run detail can't word it differently.

    ``weeks`` counts issued runs, not calendar weeks — a run's cadence is whatever its author froze it at,
    and "6 weeks" would be a claim the stored series cannot support.
    """
    if not rating:
        return {"rating": "", "weeks": 0, "label": "no rating on record"}
    if not weeks:
        return {"rating": rating, "weeks": 0, "label": f"{rating} · no prior run at this rating"}
    return {
        "rating": rating, "weeks": weeks,
        "label": f"{rating} · {weeks} {'run' if weeks == 1 else 'runs'} in a row",
    }


def _streak(rating, ratings):
    """Consecutive newest runs already carrying ``rating`` — 0 when the streak is new at this letter."""
    weeks = 0
    for stored in ratings or []:
        if stored != rating:
            break
        weeks += 1
    return _streak_result(rating, weeks)


def rag_streak(tenant, project=None, as_of=None):
    """The "how long has this been amber" claim, read from the frozen series and never recomputed.

    Returns ``{"rating", "weeks", "label"}``; with no issued run in scope it is
    ``{"rating": "", "weeks": 0, "label": "no rating on record"}``, which is what the template's
    ``{% if %}`` covers. ``project`` narrows to runs of reports bound to that project; without one the
    tenant's newest issued run answers.
    """
    rows = _issued_ratings(tenant, as_of=as_of)
    if not rows:
        return _streak_result("", 0)
    series = _rating_series(rows)
    key = rows[0][1] if project is None else getattr(project, "pk", project)
    ratings = series.get(key)
    if not ratings:
        return _streak_result("", 0)
    return _streak(ratings[0], ratings)


def rag_history(tenant, *, months=6, as_of=None):
    """``[{"label", "green", "amber", "red"}]`` — issued-run ratings per month, oldest first.

    A streak answers "how long has it been amber"; only the buckets answer "when did it turn", which is
    the one table the steering pack prints that no live query can produce. Empty months are kept, so a
    gap reads as a gap instead of disappearing.
    """
    months = max(1, min(int(months or 6), 24))
    today = as_of or timezone.localdate()
    first_year, m = today.year, today.month - (months - 1)
    while m <= 0:
        m += 12
        first_year -= 1
    keys = []
    year, month = first_year, m
    for _step in range(months):
        keys.append((f"{year:04d}-{month:02d}", date(year, month, 1).strftime("%b %y")))
        month += 1
        if month == 13:
            month, year = 1, year + 1

    buckets = {key: {"green": 0, "amber": 0, "red": 0} for key, _label in keys}
    since = datetime(first_year, m, 1, tzinfo=timezone.get_current_timezone())
    runs = ProjectReportRun.objects.filter(
        tenant=tenant, status="issued", generated_at__gte=since
    ).annotate(bucket=TruncMonth("generated_at")).values_list("bucket", "data")
    for bucket_month, payload in runs:
        key = bucket_month.strftime("%Y-%m") if bucket_month else ""
        if key not in buckets:
            continue
        rating = (payload or {}).get("rating") or ""
        if rating in _RAG_KEYS:
            buckets[key][rating] += 1
    return [{"label": label, **buckets[key]} for key, label in keys]


def narrative_seed(tenant, report, result):
    """A factual starter sentence for a new run's ``narrative`` — the author is expected to edit it.

    Nothing here is generated prose and nothing is markdown: every clause names something this scope
    actually holds — the leading row of the frozen answer, the open escalation count, the newest
    published lesson learned, the top caveat. It is a starting point, not an autopilot.
    """
    result = result or {}
    rows = result.get("rows") or []
    sentences = []
    if not rows:
        sentences.append("No rows matched the selected window, so nothing in this pack asks for a decision.")
    else:
        lead = rows[0]
        lead_label = lead[0] if isinstance(lead, (list, tuple)) and lead else str(lead)
        columns = result.get("columns") or []
        dataset = result.get("chart_dataset_label") or ""
        index = columns.index(dataset) if dataset in columns else None
        value = lead[index] if index is not None and index < len(lead) else ""
        subject = dict(SUBJECT_CHOICES).get(result.get("subject") or "", "group")
        clause = f"{lead_label} leads the {subject} on {dataset}"
        sentences.append(f"{clause} ({value})." if value != "" else f"{clause}.")

    rating = (result.get("rating") or "").upper()
    if rating in ("RED", "AMBER"):
        sentences.append(
            f"The result is rated {rating.title()}, so this pack should name the decision being asked for.")

    project_ids = _scope_project_ids(tenant, {
        "project_id": getattr(report, "project_id", None),
        "portfolio_id": getattr(report, "portfolio_id", None),
        "client_id": getattr(report, "client_id", None),
        "org_unit_id": getattr(report, "org_unit_id", None),
    })
    escalations = IssueEscalation.objects.filter(tenant=tenant, resolved_at=None)
    if project_ids is not None:
        escalations = escalations.filter(issue__project_id__in=project_ids)
    open_count = escalations.count()
    if open_count:
        sentences.append(
            f"{open_count} open issue "
            f"{'escalation' if open_count == 1 else 'escalations'} "
            f"{'awaits' if open_count == 1 else 'await'} a response.")

    lessons = KnowledgeEntry.objects.filter(tenant=tenant, status="published", kind="lesson_learned")
    if project_ids is not None:
        lessons = lessons.filter(source_project_id__in=project_ids)
    lesson = lessons.order_by("-created_at", "-id").first()
    if lesson:
        sentences.append(
            f"The newest published lesson learned on this scope reads: {lesson.summary or lesson.title}.")

    caveats = result.get("caveats") or []
    if caveats:
        sentences.append(f"Note: {caveats[0]}")
    return " ".join(sentences)


def exec_pack(tenant, *, portfolio=None, project=None, as_of=None):
    """The steering-committee read: portfolio RAG, the money, the top threats — composed from the
    functions above, adding no new query grammar and writing nothing.

    Bands carry ``drill_url_name`` + ``drill_pk`` instead of a resolved URL because analytics must not
    call ``reverse()`` (B3.0); the view turns them into the ``drill_url`` B2.1 pins.
    """
    if tenant is None:
        return json_safe({
            "columns": [], "rows": [], "summary": {}, "bands": [], "rollup": [],
            "rag_history": [], "money": {}, "caveats": [
                "No workspace is bound to this request — module data is only visible to a tenant account."],
        })

    portfolio_id = getattr(portfolio, "pk", portfolio)
    project_id = getattr(project, "pk", project)
    window = resolve_window("last_90", as_of=as_of)
    params = {"as_of": window["as_of"], "top_n": MAX_EVM_PROJECTS}
    if portfolio_id:
        params["portfolio_id"] = portfolio_id
    if project_id:
        params["project_id"] = project_id
    pack = standard_report("steering_pack", tenant, params)

    project_ids = _scope_project_ids(tenant, {
        "project_id": project_id, "portfolio_id": portfolio_id})
    evm_map = _evm_map(tenant, _tenant_project_ids(tenant, project_ids), window["as_of"])
    totals = _totals(tenant, project_ids)
    series = _rating_series(_issued_ratings(tenant, as_of=window["as_of"]))
    portfolios = _portfolio_names(tenant)
    programs = _program_names(tenant)
    hours_by_project = {
        row["project_id"]: row["value"] or Decimal("0")
        for row in _tile_qs(ResourceTimeEntry, tenant, project_ids)
        .values("project_id").annotate(value=Sum("hours"))
    }
    invoiced_by_project = {
        row["project_id"]: row["value"] or Decimal("0")
        for row in _tile_qs(ProjectClientInvoice, tenant, project_ids)
        .exclude(status__in=("draft", "cancelled"))
        .values("project_id").annotate(value=Sum("total_amount"))
    }

    bands = []
    for row in _tile_qs(Project, tenant, project_ids).order_by("name")[:MAX_EVM_PROJECTS]:
        account = evm_map.get(row.pk) or {}
        invoiced = invoiced_by_project.get(row.pk)
        rating = _HEALTH_RAG.get(account.get("health") or "") or ""
        streak = _streak(rating, series.get(row.pk))
        bands.append({
            "project": row,
            "portfolio": portfolios.get(row.pk, UNASSIGNED),
            "program": programs.get(row.pk, ""),
            "rating": streak["rating"],
            "rag_css": _RAG_CSS.get(streak["rating"], "badge-muted"),
            "streak_weeks": streak["weeks"],
            "streak_label": streak["label"],
            "cpi": account.get("cpi"),
            "spi": account.get("spi"),
            "cv": _format_unit("money", account.get("cv")),
            "sv": _format_unit("money", account.get("sv")),
            "hours": hours_by_project.get(row.pk, Decimal("0")),
            "margin_pct": _format_unit("pct", _margin_pct(invoiced, account.get("ac"))),
            "drill_url_name": "projects:prj_detail",
            "drill_pk": row.pk,
        })

    overdue = (WIDGET_COMPUTE["overdue_milestones"](
        tenant, window["start"], window["end"], project_ids) or {}).get("rows") or []

    return json_safe({
        "scope_label": _pack_scope_label(tenant, portfolio_id, project_id),
        "window": {"from": window["start"], "to": window["end"], "as_of": window["as_of"]},
        "as_of": window["as_of"],
        "columns": pack.get("columns") or [],
        "rows": pack.get("rows") or [],
        "summary": pack.get("summary") or {},
        "chart_type": pack.get("chart_type") or "table",
        "chart_labels": pack.get("chart_labels") or [],
        "chart_data": pack.get("chart_data") or [],
        "chart_dataset_label": pack.get("chart_dataset_label") or "",
        "rating": pack.get("rating") or "",
        "truncated": pack.get("truncated") or False,
        "group_count": pack.get("group_count") or 0,
        "money": {
            "Budget at completion": _format_unit("money", totals["bac"]),
            "Earned value": _format_unit("money", totals["ev"]),
            "Actual cost": _format_unit("money", totals["ac"]),
            "Invoiced": _format_unit("money", totals["invoiced"]),
            "Unbilled": _format_unit("money", max(totals["ev"] - totals["invoiced"], Decimal("0"))),
            "CPI": _format_unit("index", (totals["ev"] / totals["ac"]).quantize(Decimal("0.0001"))
                                if totals["ac"] else None),
            "SPI": _format_unit("index", (totals["ev"] / totals["pv"]).quantize(Decimal("0.0001"))
                                if totals["pv"] else None),
        },
        "bands": bands,
        "rollup": _rollup_rows(bands),
        "rag_history": rag_history(tenant, as_of=window["as_of"]),
        "top_risks": [
            {"label": row["label"], "value": _format_unit("money", row["value"])}
            for row in _risk_exposure_grouped(tenant, project_ids)[:5]
        ],
        "overdue_milestones": overdue[:5],
        "caveats": (pack.get("caveats") or []) + [
            "EVM measures come from 7.4 cost control accounts and are only as current as their postings.",
        ],
    })


def _pack_scope_label(tenant, portfolio_id, project_id):
    """What the pack says it covers, in the words a reader would use for it."""
    if project_id:
        project = Project.objects.filter(tenant=tenant, pk=project_id).first()
        return project.name if project else UNASSIGNED
    if portfolio_id:
        portfolio = Portfolio.objects.filter(tenant=tenant, pk=portfolio_id).first()
        return str(portfolio) if portfolio else UNASSIGNED
    return "All projects"


def _rollup_rows(bands):
    """Portfolio → program → project, flattened into the ordered rows one table prints.

    Each row carries its ``level`` so the template indents instead of doing index gymnastics, and the
    portfolio and program rows count their own projects — the nesting a steering committee reads.
    """
    nested = {}
    for band in bands:
        nested.setdefault(band["portfolio"], {}).setdefault(
            band["program"] or UNASSIGNED, []).append(band)
    rows = []
    for portfolio_name in sorted(nested):
        programs = nested[portfolio_name]
        members = [band for group in programs.values() for band in group]
        rows.append({"level": "portfolio", "label": portfolio_name, "projects": len(members)})
        for program_name in sorted(programs):
            group = programs[program_name]
            rows.append({"level": "program", "label": program_name, "projects": len(group)})
            for band in sorted(group, key=lambda item: item["project"].name):
                rows.append({
                    "level": "project", "label": band["project"].name, "projects": 1,
                    "rating": band["rating"], "rag_css": band["rag_css"], "cv": band["cv"],
                })
    return rows


def renumber_tiles(dashboard):
    """Rewrite tile positions to 1..n in the order they already sit.

    The ONE write in this module and the only documented position-repair path: ``wdg_move`` calls it when
    two tiles tie, which happens only once a row has left the grid out from under the move. 1-based
    because ``wdg_create`` stamps ``max + 1``.
    """
    tiles = list(dashboard.widgets.filter(tenant_id=dashboard.tenant_id).order_by("position", "id"))
    changed = []
    for index, widget in enumerate(tiles, start=1):
        if widget.position != index:
            widget.position = index
            changed.append(widget)
    if changed:
        DashboardWidget.objects.bulk_update(changed, ["position"])


def _risk_exposure_grouped(tenant, project_ids=None):
    """Open risk exposure per project, worst first — the shared body of the exposure tile and the pack.

    Sums 7.5's own ``exposure`` property instead of re-deriving it here, so the tile, the pack and the
    risk register cannot tell three stories about the same risk.
    """
    risks = _tile_qs(ProjectRisk, tenant, project_ids).exclude(
        status="closed").select_related("project")
    grouped = {}
    for risk in risks:
        key = risk.project.name if risk.project else UNASSIGNED
        grouped[key] = grouped.get(key, Decimal("0")) + Decimal(risk.exposure or 0)
    return sorted(
        ({"label": label, "value": value} for label, value in grouped.items()),
        key=lambda row: row["value"], reverse=True,
    )
