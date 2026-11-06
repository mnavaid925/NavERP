from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class OlapCube(TenantNumbered):
    NUMBER_PREFIX = "BOCB"

    STORAGE_MODE_CHOICES = [
        ("rolap", "Relational OLAP (Dynamic Query)"),
        ("summary_rollup", "Pre-Aggregated Summary Rollup"),
        ("hybrid", "Hybrid (Fast Cache + Passthrough)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Definition"),
        ("active", "Active / Ready"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    storage_mode = models.CharField(
        max_length=20,
        choices=STORAGE_MODE_CHOICES,
        default="rolap",
    )
    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="olap_cubes",
    )
    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="olap_cubes",
    )
    default_hierarchy = models.ForeignKey(
        "bi.DrillHierarchy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="olap_cubes",
    )
    dimensions_config = models.JSONField(
        default=list,
        help_text="Dimensional attributes, levels, and keys",
    )
    measures_config = models.JSONField(
        default=list,
        help_text="Measures, formulas, aggregations and format strings",
    )
    aggregations_config = models.JSONField(
        default=list,
        help_text="Pre-calculated cuboid grain specifications",
    )
    time_intelligence_enabled = models.BooleanField(
        default=True,
        help_text="Enables YTD, QTD, YoY, and rolling period calculations",
    )
    cache_ttl_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Cache expiry in minutes for materialized aggregations",
    )
    last_refreshed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_olap_cubes",
    )

    class Meta:
        db_table = "bi_olap_cube"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bocb_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bocb_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "storage_mode"], name="idx_bocb_ten_mode"),
            models.Index(fields=["tenant", "status"], name="idx_bocb_ten_stat"),
            models.Index(fields=["tenant", "created_by"], name="idx_bocb_ten_user"),
        ]

    def __str__(self):
        return f"{self.name} ({self.number})"

    def get_absolute_url(self):
        return reverse("bi:olap_cube_detail", kwargs={"pk": self.pk})

    @property
    def dimension_count(self):
        return len(self.dimensions_config) if isinstance(self.dimensions_config, list) else 0

    @property
    def measure_count(self):
        return len(self.measures_config) if isinstance(self.measures_config, list) else 0

    def refresh_cube(self):
        from django.utils import timezone
        self.last_refreshed_at = timezone.now()
        self.save(update_fields=["last_refreshed_at", "updated_at"])

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "cube"
            self.slug = base_slug[:120]
        super().save(*args, **kwargs)
