from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class AdHocQuery(TenantNumbered):
    NUMBER_PREFIX = "BAHQ"

    SOURCE_TYPE_CHOICES = [
        ("semantic_model", "Governed Semantic Model"),
        ("warehouse_table", "Warehouse Fact/Dimension Table"),
        ("blend", "Blended Dataset Mashup"),
    ]

    VISUALIZATION_TYPE_CHOICES = [
        ("table", "Data Table Grid"),
        ("bar_chart", "Bar / Column Chart"),
        ("line_chart", "Line Trend Chart"),
        ("area_chart", "Area Chart"),
        ("pie_chart", "Donut / Pie Chart"),
        ("kpi_card", "Single Metric KPI Card"),
        ("pivot_table", "Multi-Dimensional Pivot Matrix"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Exploration"),
        ("active", "Active / Ready"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPE_CHOICES, default="semantic_model")
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ad_hoc_queries",
    )
    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ad_hoc_queries",
    )
    data_blend = models.ForeignKey(
        "bi.DataBlendDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ad_hoc_queries",
    )
    fields_config_json = models.JSONField(
        default=list,
        help_text="List of selected dimensions and measures with aggregations",
    )
    filter_criteria_json = models.JSONField(
        default=list,
        help_text="Multi-condition filter rules: field, operator, value",
    )
    sort_config_json = models.JSONField(
        default=list,
        help_text="Sorting criteria: field, direction",
    )
    visualization_type = models.CharField(max_length=30, choices=VISUALIZATION_TYPE_CHOICES, default="table")
    chart_config_json = models.JSONField(
        default=dict,
        help_text="Chart styling, colors, axes labels, legends",
    )
    row_limit = models.PositiveIntegerField(default=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    last_executed_at = models.DateTimeField(null=True, blank=True)
    execution_duration_ms = models.PositiveIntegerField(default=0)
    row_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_ad_hoc_queries",
    )

    class Meta:
        db_table = "bi_ad_hoc_query"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bahq_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bahq_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "source_type"], name="idx_bahq_ten_src"),
            models.Index(fields=["tenant", "visualization_type"], name="idx_bahq_ten_viz"),
            models.Index(fields=["tenant", "status"], name="idx_bahq_ten_stat"),
            models.Index(fields=["tenant", "created_by"], name="idx_bahq_ten_user"),
            models.Index(fields=["tenant", "created_at"], name="idx_bahq_ten_created"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            base = slugify(self.name)[:100] or "query"
            self.slug = base
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("bi:ad_hoc_query_detail", kwargs={"pk": self.pk})

    @property
    def badge_status(self):
        mapping = {
            "draft": "badge-amber",
            "active": "badge-green",
            "archived": "badge-muted",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def badge_source(self):
        mapping = {
            "semantic_model": "badge-info",
            "warehouse_table": "badge-amber",
            "blend": "badge-green",
        }
        return mapping.get(self.source_type, "badge-slate")

    @property
    def badge_viz(self):
        mapping = {
            "table": "badge-slate",
            "bar_chart": "badge-info",
            "line_chart": "badge-green",
            "area_chart": "badge-info",
            "pie_chart": "badge-amber",
            "kpi_card": "badge-green",
            "pivot_table": "badge-slate",
        }
        return mapping.get(self.visualization_type, "badge-slate")
