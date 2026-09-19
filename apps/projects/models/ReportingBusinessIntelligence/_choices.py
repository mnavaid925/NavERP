"""Projects 7.16 Reporting & Business Intelligence — the frozen report/dashboard vocabulary.

One shared choices module for the whole sub-module: the builder, the tiles, the canned reports and the
templates all read the SAME list, so a report axis can never exist in one place and not another.
No models here. ``apps/projects/analytics.py`` mirrors these keys in its registries; models NEVER import
analytics (one-way edge), which is what keeps the metric↔chart rule out of ``DashboardWidget.clean()``.

The axes are FROZEN and code-defined: there is no formula parser, no user-authored expression and no
``MetricDefinition`` table. Adding an axis is a code change reviewed alongside the compute function that
implements it, so a builder dropdown can never invent one. Formula/calculated columns are parked to 7.19.
"""

# -- the window ---------------------------------------------------------------------------------
# `custom` is required by the builder's explicit date_from/date_to pair: without it the two date
# columns are unreachable (procurement.DATE_RANGE_CHOICES carries it for the same reason).
# ProjectDashboard / DashboardWidget REFUSE `custom` in clean() — they carry no date pair to resolve.
RANGE_CHOICES = [
    ("last_7", "Last 7 days"),
    ("last_30", "Last 30 days"),
    ("last_90", "Last 90 days"),
    ("quarter", "This quarter"),
    ("year", "This year"),
    ("all", "All time"),
    ("custom", "Custom range"),
]

# -- how a result renders -----------------------------------------------------------------------
# CANVAS kinds (Chart.js 4.4.1, already global in templates/base.html): bar, line, pie, doughnut.
# HTML kinds (NO canvas — a KPI card, gauge, table and heat band are markup): kpi, gauge, table, heat.
# analytics.allowed_charts(metric) is the authority on which pair; CHART_CHOICES only bounds the column.
CHART_CHOICES = [
    ("kpi", "KPI Card"),
    ("gauge", "Gauge"),
    ("bar", "Bar Chart"),
    ("line", "Line Chart"),
    ("pie", "Pie Chart"),
    ("doughnut", "Doughnut Chart"),
    ("table", "Table"),
    ("heat", "Heat Bands"),
]

# -- dashboard chrome ---------------------------------------------------------------------------
LAYOUT_CHOICES = [
    ("one", "Single column"),
    ("two", "Two columns"),
    ("three", "Three columns"),
]

SIZE_CHOICES = [
    ("small", "Small (quarter width)"),
    ("medium", "Medium (half width)"),
    ("large", "Large (three-quarter width)"),
    ("full", "Full width"),
]

# The real NavERP personas a tenant template is authored for.
AUDIENCE_CHOICES = [
    ("pm", "Project Manager"),
    ("resource_manager", "Resource Manager"),
    ("finance", "Finance / PMO Costing"),
    ("quality", "Quality Manager"),
    ("agile_team", "Agile Team"),
    ("executive", "Executive / Steering Committee"),
    ("portfolio", "Portfolio Manager"),
]

# -- the canned report kinds (16) ---------------------------------------------------------------
# One entry per analytics.STANDARD_REPORTS key; "custom" is the builder's own kind.
# rbi_home's "standard reports" answer is these 16 kinds x 4 scope axes, NOT 16 pages.
REPORT_TYPE_CHOICES = [
    ("status_report", "Project Status Report"),
    ("milestone_summary", "Milestone Summary"),
    ("schedule_variance", "Schedule Variance"),
    ("risk_register", "Risk Register"),
    ("issue_log", "Issue Log"),
    ("quality_defect_summary", "Quality & Defect Summary"),
    ("scope_change_summary", "Scope Change Summary"),
    ("cost_variance", "Cost Variance"),
    ("earned_value", "Earned Value (EVM)"),
    ("resource_utilization", "Resource Utilization"),
    ("time_entry", "Time Entry Detail"),
    ("billing_summary", "Billing Summary"),
    ("agile_throughput", "Agile Throughput / Velocity"),
    ("portfolio_health", "Portfolio Health"),
    ("steering_pack", "Executive & Steering Pack"),
    ("custom", "Custom (built with the report builder)"),
]

# -- what a report counts rows OF (16 registers) -------------------------------------------------
SUBJECT_CHOICES = [
    ("project", "Projects"),
    ("task", "Tasks & work items"),
    ("milestone", "Milestones"),
    ("requirement", "Requirements"),
    ("change_order", "Scope changes"),
    ("sprint", "Sprints"),
    ("time_entry", "Time entries"),
    ("resource_allocation", "Resource allocations"),
    ("cost", "Cost lines (7.4 cost control)"),
    ("invoice", "Project invoices (7.15)"),
    ("payment", "Payments received (7.15)"),
    ("risk", "Risks"),
    ("issue", "Issues"),
    ("quality_review", "Quality reviews"),
    ("defect", "Quality defects"),
    ("document", "Documents & lessons"),
]

# -- what a report measures (24, frozen) ---------------------------------------------------------
# The 15 ratio/variance/aging keys are the calculated columns other products sell a formula editor for;
# here they are read-only keys backed by analytics, so the EVM maths stays in ONE place. Costs/EVM come
# from CostControlAccount's @property reads, billing from 7.15 rows — 7.16 stores NONE of them.
MEASURE_CHOICES = [
    ("planned_value", "Planned value (PV)"),
    ("earned_value", "Earned value (EV)"),
    ("actual_cost", "Actual cost (AC)"),
    ("budget_at_completion", "Budget at completion (BAC)"),
    ("eac", "Estimate at completion (EAC)"),
    ("cv", "Cost variance (CV)"),
    ("cv_pct", "Cost variance %"),
    ("sv", "Schedule variance (SV)"),
    ("sv_pct", "Schedule variance %"),
    ("cpi", "Cost performance index (CPI)"),
    ("spi", "Schedule performance index (SPI)"),
    ("margin_pct", "Margin % (invoiced vs actual cost)"),
    ("hours", "Hours booked"),
    ("billable_pct", "Billable %"),
    ("utilization_pct", "Utilization %"),
    ("task_count", "Tasks"),
    ("open_count", "Open items"),
    ("completed_count", "Completed items"),
    ("on_time_pct", "On-time %"),
    ("slip_days", "Schedule slip (days)"),
    ("exposure_value", "Risk exposure value"),
    ("aging_days", "Aging (days)"),
    ("unbilled_amount", "Unbilled amount"),
    ("invoiced_amount", "Invoiced amount"),
]

# -- how a report groups rows (18, incl. none) ---------------------------------------------------
# `defect_severity` is split out of `severity` because the quality register's scale
# (critical/major/minor/trivial) is not the risk/issue scale. `none` is a real option, not a blank.
DIMENSION_CHOICES = [
    ("project", "Project"),
    ("portfolio", "Portfolio"),
    ("client", "Client"),
    ("org_unit", "Department / cost centre"),
    ("resource", "Resource"),
    ("role", "Role"),
    ("activity_code", "Activity code"),
    ("wbs_phase", "WBS phase"),
    ("milestone_status", "Milestone status"),
    ("task_type", "Task type"),
    ("priority", "Priority"),
    ("status", "Status"),
    ("risk_category", "Risk category"),
    ("severity", "Severity"),
    ("defect_severity", "Defect severity"),
    ("month", "Month"),
    ("quarter", "Quarter"),
    ("none", "- none -"),
]

# -- run workflow -------------------------------------------------------------------------------
# Module name carries the RUN_ prefix so this shared vocabulary can never be mistaken for a
# project/task status list; the model still exposes it as ProjectReportRun.STATUS_CHOICES.
RUN_STATUS_CHOICES = [
    ("draft", "Draft (frozen, not yet issued)"),
    ("issued", "Issued"),
    ("archived", "Archived"),
]

# -- tile metrics (25) ---------------------------------------------------------------------------
# Every key MUST exist in analytics.WIDGET_METRICS with the same spelling — the tile is a pointer
# into that registry, and a typo'd key is a blank tile that still returns 200 (L8).
WIDGET_METRIC_CHOICES = [
    # scalar → kpi / gauge
    ("kpi_active_projects", "KPI · Active projects (#)"),
    ("kpi_overdue_tasks", "KPI · Overdue tasks (#)"),
    ("kpi_open_risks", "KPI · Open risks (#)"),
    ("kpi_open_issues", "KPI · Open issues (#)"),
    ("kpi_open_defects", "KPI · Open defects (#)"),
    ("kpi_cpi", "KPI · CPI"),
    ("kpi_spi", "KPI · SPI"),
    ("kpi_utilization_pct", "KPI · Utilization %"),
    ("kpi_billable_pct", "KPI · Billable %"),
    ("kpi_unbilled_amount", "KPI · Unbilled amount"),
    ("kpi_schedule_slip_days", "KPI · Schedule slip (days)"),
    # series → bar / line / pie / doughnut / heat
    ("projects_by_status", "Chart · Projects by status"),
    ("tasks_by_status", "Chart · Tasks by status"),
    ("risks_by_category", "Chart · Risks by category"),
    ("issues_by_severity", "Chart · Issues by severity"),
    ("defects_by_severity", "Chart · Defects by severity"),
    ("hours_by_activity_code", "Chart · Hours by activity code"),
    ("cost_variance_by_project", "Chart · Cost variance by project"),
    ("ev_curve_by_month", "Chart · EV curve by month"),
    ("utilization_by_resource", "Chart · Utilization by resource"),
    ("milestones_on_time_by_month", "Chart · Milestones on time by month"),
    ("health_heat_bands", "Chart · Portfolio health heat bands"),
    # table → table only
    ("top_cost_variance_projects", "Table · Worst cost variance"),
    ("top_risk_exposure_projects", "Table · Highest risk exposure"),
    ("overdue_milestones", "Table · Overdue milestones"),
]


#: chart kinds rendered by Chart.js on a <canvas>
CANVAS_CHARTS = ("bar", "line", "pie", "doughnut")
#: chart kinds rendered as plain HTML (never a canvas — a blank canvas still returns 200, L8)
HTML_CHARTS = ("kpi", "gauge", "table", "heat")
