"""Projects 7.16 Reporting & Business Intelligence — DashboardWidget (a tile).

An unnumbered child of ``ProjectDashboard``: a metric key pointing into ``analytics.WIDGET_METRICS``, a
chart kind, a window, a grid size and a manual position. ``metric`` and ``chart_type`` are valid only as a
PAIR — the legal set comes from ``analytics.allowed_charts(metric)``.

Models never import analytics (one-way edge), so that pair rule is enforced in ``DashboardWidgetForm.clean()``
and not here; ``choices=WIDGET_METRIC_CHOICES`` still refuses an unknown key at form/DB level.

Tenancy is denormalised on purpose: ``tenant`` MUST equal ``dashboard.tenant``. ``clean()`` enforces it,
``wdg_create`` sets it from the parent, and it is what lets a tile be ``get_object_or_404``'d by
``pk, tenant=request.tenant`` without a join.
"""
from django.core.exceptions import ValidationError
from django.db import models

from apps.projects.models.ReportingBusinessIntelligence._choices import (
    CANVAS_CHARTS,
    CHART_CHOICES,
    RANGE_CHOICES,
    SIZE_CHOICES,
    WIDGET_METRIC_CHOICES,
)

#: size key → Tailwind col-span class the grid template applies
_SIZE_CSS = {
    "small": "lg:col-span-3",
    "medium": "lg:col-span-6",
    "large": "lg:col-span-9",
    "full": "lg:col-span-12",
}


class DashboardWidget(models.Model):
    WIDGET_METRIC_CHOICES = WIDGET_METRIC_CHOICES
    CHART_CHOICES = CHART_CHOICES
    RANGE_CHOICES = RANGE_CHOICES
    SIZE_CHOICES = SIZE_CHOICES

    tenant = models.ForeignKey(
        "core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True
    )
    dashboard = models.ForeignKey(
        "projects.ProjectDashboard", on_delete=models.CASCADE, related_name="widgets"
    )
    title = models.CharField(max_length=120)
    metric = models.CharField(
        max_length=40, choices=WIDGET_METRIC_CHOICES, default="kpi_active_projects"
    )
    chart_type = models.CharField(max_length=10, choices=CHART_CHOICES, default="kpi")
    date_range = models.CharField(max_length=10, choices=RANGE_CHOICES, default="last_30")
    size = models.CharField(max_length=10, choices=SIZE_CHOICES, default="medium")
    position = models.PositiveIntegerField(default=0)
    target_value = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    portfolio = models.ForeignKey(
        "projects.Portfolio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]
        indexes = [
            models.Index(fields=["tenant", "dashboard"], name="wdg_tnt_dash_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_chart_type_display()})"

    # -- computed, never stored -----------------------------------------------------------------
    @property
    def is_canvas(self):
        return self.chart_type in CANVAS_CHARTS

    @property
    def canvas_id(self):
        """The exact DOM id the template renders and the Chart.js bootstrap looks up."""
        return f"wchart{self.pk}"

    @property
    def size_css(self):
        return _SIZE_CSS.get(self.size, "lg:col-span-6")

    @property
    def metric_label(self):
        return self.get_metric_display()

    @property
    def chart_label(self):
        return self.get_chart_type_display()

    # `drill_url_name` is deliberately NOT a property — it lives in
    # analytics.WIDGET_METRICS[metric]["drill_url_name"] and arrives via compute_widget().

    # -- validation ---------------------------------------------------------------------------------
    def clean(self):
        errors = {}

        if self.date_range == "custom":
            errors["date_range"] = (
                "A tile has no date pair — pick one of the presets or all time."
            )

        if self.tenant_id:
            if (
                self.dashboard_id
                and self.dashboard.tenant_id != self.tenant_id
            ):
                errors["dashboard"] = "This dashboard belongs to another workspace."
            for field in ("project", "portfolio"):
                related = getattr(self, field, None)
                if related is not None and related.tenant_id != self.tenant_id:
                    errors[field] = "That scope belongs to another workspace."

        if errors:
            raise ValidationError(errors)
