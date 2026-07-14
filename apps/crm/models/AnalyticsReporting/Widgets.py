"""CRM 1.6 Analytics & Reporting — Widgets models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403
from apps.crm.models.AnalyticsReporting._choices import ANALYTICS_RANGE_CHOICES, WIDGET_CHART_CHOICES, WIDGET_METRIC_CHOICES, WIDGET_SIZE_CHOICES


class DashboardWidget(models.Model):
    """One tile on an ``AnalyticsDashboard`` (1.6). ``metric`` selects a read-only aggregation
    (see ``analytics.WIDGET_METRICS``); ``chart_type`` chooses how to render it (the form's
    ``clean()`` enforces a chart that the metric supports). Not ``TenantNumbered`` — it is a
    child row, so it carries its own tenant FK + timestamps and no human-readable number.
    ``target_value`` is an optional goal used by gauge/KPI widgets (progress-to-target)."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    dashboard = models.ForeignKey("AnalyticsDashboard", on_delete=models.CASCADE, related_name="widgets")
    title = models.CharField(max_length=120)
    metric = models.CharField(max_length=40, choices=WIDGET_METRIC_CHOICES, default="kpi_open_pipeline")
    chart_type = models.CharField(max_length=10, choices=WIDGET_CHART_CHOICES, default="kpi")
    date_range = models.CharField(max_length=10, choices=ANALYTICS_RANGE_CHOICES, default="last_30")
    size = models.CharField(max_length=10, choices=WIDGET_SIZE_CHOICES, default="medium")
    target_value = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)  # optional goal for gauge/KPI
    position = models.PositiveIntegerField(default=0)  # manual ordering on the dashboard
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        indexes = [
            models.Index(fields=["tenant", "dashboard"], name="crm_widget_tnt_dash_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_chart_type_display()})"
