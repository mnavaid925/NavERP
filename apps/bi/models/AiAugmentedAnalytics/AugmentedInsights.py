from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.bi.models._base import TenantNumbered


class AugmentedInsight(TenantNumbered):
    NUMBER_PREFIX = "BAIN"

    INSIGHT_TYPE_CHOICES = [
        ("key_driver", "Key Driver Analysis"),
        ("anomaly", "Statistical Anomaly"),
        ("trend_shift", "Trend Direction Shift"),
        ("outlier", "Distribution Outlier"),
        ("period_comparison", "Period Variance Spike"),
    ]

    IMPACT_DIRECTION_CHOICES = [
        ("favorable", "Favorable Impact"),
        ("unfavorable", "Unfavorable Impact"),
        ("neutral", "Neutral / Informational"),
    ]

    SEVERITY_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]

    STATUS_CHOICES = [
        ("new", "New Insight"),
        ("bookmarked", "Bookmarked"),
        ("dismissed", "Dismissed"),
        ("actioned", "Action Taken"),
    ]

    title = models.CharField(max_length=200)
    insight_type = models.CharField(max_length=24, choices=INSIGHT_TYPE_CHOICES, default="key_driver")
    metric_name = models.CharField(max_length=120, help_text="Analyzed metric, e.g. Gross Margin %, Total Revenue, Delivery Lead Time")
    baseline_value = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal("0.0000"))
    observed_value = models.DecimalField(max_digits=16, decimal_places=4, default=Decimal("0.0000"))
    variance_percentage = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0.00"))
    impact_direction = models.CharField(max_length=16, choices=IMPACT_DIRECTION_CHOICES, default="neutral")
    severity = models.CharField(max_length=16, choices=SEVERITY_CHOICES, default="medium")
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("90.00"), help_text="Statistical confidence percentage")
    narrative_summary = models.TextField(help_text="Plain-text natural language explanation of the insight")
    dimension_name = models.CharField(max_length=100, blank=True, help_text="Primary dimension sliced, e.g. Region, Product Family, Customer Tier")
    dimension_value = models.CharField(max_length=120, blank=True, help_text="Value of primary dimension, e.g. EMEA, High Tech, Tier 1")
    driver_decomposition = models.JSONField(default=list, blank=True, help_text="Top contributing positive and negative drivers")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="new")
    action_notes = models.TextField(blank=True, help_text="Management commentary or logged follow-up steps")

    semantic_model = models.ForeignKey(
        "bi.SemanticModel",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="augmented_insights",
    )
    kpi_definition = models.ForeignKey(
        "bi.KpiDefinition",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="augmented_insights",
    )
    warehouse_table = models.ForeignKey(
        "bi.WarehouseTable",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="augmented_insights",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_augmented_insights",
    )

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bain_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "insight_type"], name="idx_bain_ten_type"),
            models.Index(fields=["tenant", "status"], name="idx_bain_ten_status"),
            models.Index(fields=["tenant", "severity"], name="idx_bain_ten_sev"),
            models.Index(fields=["tenant", "impact_direction"], name="idx_bain_ten_dir"),
            models.Index(fields=["tenant", "created_at"], name="idx_bain_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    def get_absolute_url(self):
        return reverse("bi:augmented_insight_detail", kwargs={"pk": self.pk})

    @property
    def badge_color(self):
        if self.severity == "critical":
            return "badge-red"
        if self.severity == "high":
            return "badge-amber"
        if self.severity == "medium":
            return "badge-info"
        return "badge-slate"

    @property
    def impact_badge_color(self):
        if self.impact_direction == "favorable":
            return "badge-green"
        if self.impact_direction == "unfavorable":
            return "badge-red"
        return "badge-slate"
