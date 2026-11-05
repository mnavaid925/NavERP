from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class BiDashboardWidget(TenantNumbered):
    NUMBER_PREFIX = "BDWG"

    WIDGET_TYPE_CHOICES = [
        ("kpi_card", "Headline KPI Metric Card"),
        ("line", "Line Trend Chart"),
        ("area", "Area / Stacked Area Chart"),
        ("bar", "Horizontal Bar Chart"),
        ("column", "Vertical Column Chart"),
        ("pie", "Pie Chart"),
        ("donut", "Donut Composition Chart"),
        ("gauge", "Gauge / Target Progress"),
        ("heatmap", "Matrix Heatmap"),
        ("funnel", "Conversion Funnel"),
        ("treemap", "Hierarchical Treemap"),
        ("table_pivot", "Data / Pivot Table"),
        ("streaming_counter", "Live Streaming Counter / Ticker"),
    ]

    AGGREGATION_CHOICES = [
        ("sum", "Sum"),
        ("avg", "Average"),
        ("count", "Count"),
        ("count_distinct", "Distinct Count"),
        ("min", "Minimum"),
        ("max", "Maximum"),
        ("last", "Latest Non-Null Value"),
    ]

    dashboard = models.ForeignKey(
        "bi.BiDashboard",
        on_delete=models.CASCADE,
        related_name="widgets",
    )
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=255, blank=True)
    widget_type = models.CharField(max_length=40, choices=WIDGET_TYPE_CHOICES, default="kpi_card")
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dashboard_widgets",
        help_text="Governed analytical dataset source (10.4)",
    )
    calculated_measure = models.ForeignKey(
        "bi.CalculatedMeasure",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dashboard_widgets",
        help_text="Governed metric measure for KPI value and aggregations (10.4)",
    )
    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dashboard_widgets",
        help_text="Direct physical analytical warehouse table (10.3)",
    )
    drill_hierarchy = models.ForeignKey(
        "bi.DrillHierarchy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dashboard_widgets",
        help_text="Pre-configured drill path (10.4)",
    )
    aggregation_type = models.CharField(
        max_length=30,
        choices=AGGREGATION_CHOICES,
        default="sum",
    )
    pos_x = models.PositiveSmallIntegerField(
        default=0,
        help_text="Horizontal column coordinate on 12-col grid (0 to 11)",
    )
    pos_y = models.PositiveSmallIntegerField(
        default=0,
        help_text="Vertical row coordinate on grid (0 to 100)",
    )
    width_cols = models.PositiveSmallIntegerField(
        default=4,
        help_text="Width in columns on 12-col grid (1 to 12)",
    )
    height_rows = models.PositiveSmallIntegerField(
        default=4,
        help_text="Height in grid row units (1 to 12)",
    )
    refresh_interval_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Widget-specific auto-refresh interval in seconds (0 = inherit from dashboard)",
    )
    drilldown_target_url = models.CharField(
        max_length=255,
        blank=True,
        help_text="Destination URL or report route triggered upon clicking widget marks",
    )
    chart_config_json = models.JSONField(
        default=dict,
        help_text="Visual options: colors, axis labels, legend position, tooltip formatting, sparkline history points",
    )
    filter_overrides_json = models.JSONField(
        default=dict,
        help_text="Fixed filter overrides applied exclusively to this widget",
    )
    sort_order = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "bi_dashboard_widget"
        ordering = ["pos_y", "pos_x", "sort_order"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bdwg_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "dashboard"], name="idx_bdwg_ten_dsh"),
            models.Index(fields=["tenant", "widget_type"], name="idx_bdwg_ten_wtype"),
            models.Index(fields=["tenant", "semantic_model"], name="idx_bdwg_ten_smdl"),
            models.Index(fields=["tenant", "calculated_measure"], name="idx_bdwg_ten_cmsr"),
            models.Index(fields=["tenant", "sort_order"], name="idx_bdwg_ten_sort"),
            models.Index(fields=["tenant", "is_active"], name="idx_bdwg_ten_act"),
        ]

    def __str__(self):
        return f"{self.title} ({self.number}) [{self.get_widget_type_display()}]"

    def get_absolute_url(self):
        return reverse("bi:bi_dashboard_widget_detail", kwargs={"pk": self.pk})

    @property
    def badge_widget_type(self):
        mapping = {
            "kpi_card": "badge-green",
            "line": "badge-info",
            "area": "badge-info",
            "bar": "badge-slate",
            "column": "badge-slate",
            "pie": "badge-amber",
            "donut": "badge-amber",
            "gauge": "badge-green",
            "heatmap": "badge-amber",
            "funnel": "badge-info",
            "treemap": "badge-muted",
            "table_pivot": "badge-slate",
            "streaming_counter": "badge-green",
        }
        return mapping.get(self.widget_type, "badge-info")
