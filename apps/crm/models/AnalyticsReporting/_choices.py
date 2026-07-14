"""CRM 1.6 Analytics & Reporting — _choices models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# Shared date-window selector for both widgets and reports (filters ``created_at``).
ANALYTICS_RANGE_CHOICES = [
    ("last_7", "Last 7 days"),
    ("last_30", "Last 30 days"),
    ("last_90", "Last 90 days"),
    ("quarter", "This quarter"),
    ("year", "This year"),
    ("all", "All time"),
]


DASHBOARD_LAYOUT_CHOICES = [
    ("one", "Single column"),
    ("two", "Two columns"),
    ("three", "Three columns"),
]


WIDGET_CHART_CHOICES = [
    ("kpi", "KPI Card"),
    ("gauge", "Gauge"),
    ("bar", "Bar Chart"),
    ("line", "Line Chart"),
    ("pie", "Pie Chart"),
    ("doughnut", "Doughnut Chart"),
    ("table", "Table"),
]


WIDGET_SIZE_CHOICES = [
    ("small", "Small (quarter width)"),
    ("medium", "Medium (half width)"),
    ("large", "Large (three-quarter width)"),
    ("full", "Full width"),
]


# (key, label) for every widget metric. The matching compute behaviour + the chart
# kinds each one allows are declared in ``analytics.WIDGET_METRICS`` under the same keys.
WIDGET_METRIC_CHOICES = [
    # --- scalar (KPI card / gauge) -------------------------------------------------
    ("kpi_open_pipeline", "KPI · Open Pipeline ($)"),
    ("kpi_weighted_forecast", "KPI · Weighted Forecast ($)"),
    ("kpi_win_rate", "KPI · Win Rate (%)"),
    ("kpi_revenue_won", "KPI · Revenue Won ($)"),
    ("kpi_new_leads", "KPI · New Leads (#)"),
    ("kpi_open_cases", "KPI · Open Cases (#)"),
    ("kpi_avg_csat", "KPI · Avg CSAT (1-5)"),
    ("kpi_open_tasks", "KPI · Open Tasks (#)"),
    # --- series (bar / line / pie / doughnut) -------------------------------------
    ("pipeline_by_stage", "Chart · Pipeline by Stage (#)"),
    ("pipeline_value_by_stage", "Chart · Pipeline Value by Stage ($)"),
    ("win_loss", "Chart · Won vs Lost (#)"),
    ("revenue_won_by_month", "Chart · Revenue Won by Month ($)"),
    ("leads_by_rating", "Chart · Leads by Rating"),
    ("leads_by_status", "Chart · Leads by Status"),
    ("leads_by_source", "Chart · Leads by Source"),
    ("cases_by_status", "Chart · Cases by Status"),
    ("cases_by_priority", "Chart · Cases by Priority"),
    ("tasks_by_type", "Chart · Tasks by Type"),
    # --- table --------------------------------------------------------------------
    ("top_performers", "Table · Top Performers"),
    ("campaign_roi", "Table · Campaign ROI"),
]


REPORT_TYPE_CHOICES = [
    ("sales_activity", "Sales Activity"),
    ("sales_performance", "Sales Performance (Top Performers)"),
    ("funnel", "Funnel Analysis (Drop-off)"),
    ("service", "Service (Resolution Time & CSAT)"),
]


REPORT_GROUP_CHOICES = [
    ("month", "By Month"),
    ("week", "By Week"),
    ("owner", "By Owner"),
    ("priority", "By Priority"),
    ("stage", "By Stage"),
]
