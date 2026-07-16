"""HRM 3.32 Analytics Dashboard — Widget models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.AnalyticsDashboard.ANALYTICS_RANGE_CHOICESs import ANALYTICS_RANGE_CHOICES
from apps.hrm.models.AnalyticsDashboard.ANALYTICS_RANGE_CHOICESs import ANALYTICS_RANGE_CHOICES


WIDGET_CHART_CHOICES = [
    ("kpi", "KPI Card"), ("gauge", "Gauge"), ("bar", "Bar Chart"), ("line", "Line Chart"),
    ("pie", "Pie Chart"), ("doughnut", "Doughnut Chart"), ("table", "Table"),
]


WIDGET_SIZE_CHOICES = [
    ("small", "Small (quarter width)"), ("medium", "Medium (half width)"),
    ("large", "Large (three-quarter width)"), ("full", "Full width"),
]


WIDGET_METRIC_CHOICES = [
    # --- scalar (KPI card / gauge) ---
    ("kpi_headcount", "KPI - Active Headcount (#)"),
    ("kpi_attrition_rate", "KPI - Attrition Rate (%, annualized)"),
    ("kpi_avg_tenure", "KPI - Avg Tenure (yrs)"),
    ("kpi_gross_payroll", "KPI - Payroll Cost ($)"),
    ("kpi_absenteeism_rate", "KPI - Absenteeism Rate (%)"),
    ("kpi_open_reqs", "KPI - Open Requisitions (#)"),
    ("kpi_pending_leave", "KPI - Pending Leave Requests (#)"),
    ("kpi_gender_diversity", "KPI - Gender Diversity (% female)"),
    ("kpi_avg_attrition_risk", "KPI - Avg Attrition Risk Score (0-100)"),
    # --- series (bar / line / pie / doughnut) ---
    ("headcount_trend", "Chart - Headcount Trend (12mo)"),
    ("attrition_by_department", "Chart - Attrition by Department (#)"),
    ("gender_split", "Chart - Gender Split (#)"),
    ("leave_by_type", "Chart - Leave Days by Type"),
    ("hiring_funnel", "Chart - Hiring Funnel (applications by stage)"),
    ("payroll_cost_by_department", "Chart - Payroll Cost by Department ($)"),
    # --- table ---
    ("top_attrition_risk_employees", "Table - Top Attrition-Risk Employees"),
]


class HRDashboardWidget(models.Model):
    """One tile on an ``HRDashboard`` (3.32). ``metric`` selects a read-only aggregation (see
    ``apps/hrm/analytics.WIDGET_METRICS``); ``chart_type`` chooses how to render it (the form's
    ``clean()`` enforces a chart the metric supports). A child row — it carries its own tenant FK +
    timestamps and no human-readable number. ``target_value`` is an optional goal used by gauge/KPI
    widgets (progress-to-target)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    dashboard = models.ForeignKey("HRDashboard", on_delete=models.CASCADE, related_name="widgets")
    title = models.CharField(max_length=120)
    metric = models.CharField(max_length=40, choices=WIDGET_METRIC_CHOICES, default="kpi_headcount")
    chart_type = models.CharField(max_length=10, choices=WIDGET_CHART_CHOICES, default="kpi")
    date_range = models.CharField(max_length=10, choices=ANALYTICS_RANGE_CHOICES, default="last_90")
    size = models.CharField(max_length=10, choices=WIDGET_SIZE_CHOICES, default="medium")
    target_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)  # optional goal for gauge/KPI
    position = models.PositiveIntegerField(default=0)  # manual ordering on the dashboard
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        indexes = [
            models.Index(fields=["tenant", "dashboard"], name="hrm_hrwidget_tnt_dash_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_chart_type_display()})"
