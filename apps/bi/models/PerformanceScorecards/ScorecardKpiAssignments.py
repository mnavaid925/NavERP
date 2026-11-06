from decimal import Decimal

from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.bi.models._base import TenantNumbered


class ScorecardKpiAssignment(TenantNumbered):
    NUMBER_PREFIX = "BSCI"

    PERSPECTIVE_CHOICES = [
        ("financial", "Financial"),
        ("customer", "Customer"),
        ("internal_process", "Internal Business Process"),
        ("learning_growth", "Learning & Growth"),
    ]

    RAG_STATUS_CHOICES = [
        ("green", "Green (On Track)"),
        ("amber", "Amber (Needs Attention)"),
        ("red", "Red (Critical / Off Track)"),
        ("gray", "Gray (Not Evaluated)"),
    ]

    TREND_CHOICES = [
        ("improving", "Improving (↗)"),
        ("steady", "Steady / Neutral (→)"),
        ("deteriorating", "Deteriorating (↘)"),
    ]

    scorecard = models.ForeignKey(
        "bi.PerformanceScorecard",
        on_delete=models.CASCADE,
        related_name="kpi_assignments",
    )
    kpi = models.ForeignKey(
        "bi.KpiDefinition",
        on_delete=models.CASCADE,
        related_name="scorecard_assignments",
    )
    objective = models.ForeignKey(
        "bi.StrategicObjective",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scorecard_kpis",
    )
    perspective = models.CharField(max_length=30, choices=PERSPECTIVE_CHOICES, default="internal_process")
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        help_text="Weight percentage within perspective or scorecard",
    )
    target_value = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    actual_value = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))

    # Plan vs. Actual Variance
    variance = models.DecimalField(max_digits=14, decimal_places=4, default=Decimal("0.0000"))
    variance_percentage = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))

    # Status Indicators & Trend
    rag_status = models.CharField(max_length=10, choices=RAG_STATUS_CHOICES, default="gray")
    trend_direction = models.CharField(max_length=20, choices=TREND_CHOICES, default="steady")
    normalized_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Normalized achievement score 0.00-100.00%",
    )

    # Benchmark Overlay
    benchmark_overlay_value = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    benchmark_gap = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)

    manager_notes = models.TextField(blank=True, help_text="Qualitative commentary and corrective actions")
    sort_order = models.PositiveIntegerField(default=10)
    evaluated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["scorecard", "perspective", "sort_order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bsci_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "scorecard", "kpi"], name="bi_bsci_ten_sc_kpi_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "scorecard"], name="idx_bsci_ten_sc"),
            models.Index(fields=["tenant", "kpi"], name="idx_bsci_ten_kpi"),
            models.Index(fields=["tenant", "rag_status"], name="idx_bsci_ten_rag"),
            models.Index(fields=["tenant", "perspective"], name="idx_bsci_ten_persp"),
            models.Index(fields=["tenant", "trend_direction"], name="idx_bsci_ten_trend"),
        ]

    def __str__(self):
        return f"{self.number} - {self.scorecard.name} / {self.kpi.name}"

    def get_absolute_url(self):
        return reverse("bi:scorecard_kpi_assignment_detail", kwargs={"pk": self.pk})

    def calculate_performance_metrics(self):
        """Calculate variance, RAG status, normalized achievement score, and benchmark gap."""
        self.variance = self.actual_value - self.target_value
        if self.target_value and self.target_value != Decimal("0.0000"):
            self.variance_percentage = round(
                ((self.actual_value - self.target_value) / abs(self.target_value)) * Decimal("100.00"),
                2,
            )
        else:
            self.variance_percentage = Decimal("0.00")

        # Determine RAG status using direction
        kpi_direction = self.kpi.target_direction if self.kpi_id else "maximize"
        warn = self.kpi.warning_threshold if self.kpi_id else None
        crit = self.kpi.critical_threshold if self.kpi_id else None

        if kpi_direction == "maximize":
            if self.actual_value >= self.target_value:
                self.rag_status = "green"
                # Cap at 100% or calculate achievement ratio
                achieve = Decimal("100.00") if self.target_value <= 0 else min(Decimal("100.00"), (self.actual_value / self.target_value) * Decimal("100.00"))
                self.normalized_score = round(max(Decimal("0.00"), achieve), 2)
            elif warn is not None and self.actual_value >= warn:
                self.rag_status = "amber"
                self.normalized_score = Decimal("75.00")
            elif crit is not None and self.actual_value < crit:
                self.rag_status = "red"
                self.normalized_score = Decimal("40.00")
            else:
                self.rag_status = "amber" if warn is not None else "red"
                self.normalized_score = Decimal("60.00") if self.rag_status == "amber" else Decimal("30.00")
        elif kpi_direction == "minimize":
            if self.actual_value <= self.target_value:
                self.rag_status = "green"
                self.normalized_score = Decimal("100.00")
            elif warn is not None and self.actual_value <= warn:
                self.rag_status = "amber"
                self.normalized_score = Decimal("75.00")
            elif crit is not None and self.actual_value > crit:
                self.rag_status = "red"
                self.normalized_score = Decimal("40.00")
            else:
                self.rag_status = "amber" if warn is not None else "red"
                self.normalized_score = Decimal("60.00") if self.rag_status == "amber" else Decimal("30.00")
        else:  # in_range
            lower = warn if warn is not None else self.target_value * Decimal("0.9")
            upper = crit if crit is not None else self.target_value * Decimal("1.1")
            if lower <= self.actual_value <= upper:
                self.rag_status = "green"
                self.normalized_score = Decimal("100.00")
            else:
                self.rag_status = "amber"
                self.normalized_score = Decimal("60.00")

        # Trend direction against previous KPI measurement
        if self.kpi_id and self.kpi.previous_value is not None:
            prev = self.kpi.previous_value
            if self.actual_value > prev:
                self.trend_direction = "improving" if kpi_direction == "maximize" else "deteriorating"
            elif self.actual_value < prev:
                self.trend_direction = "deteriorating" if kpi_direction == "maximize" else "improving"
            else:
                self.trend_direction = "steady"
        else:
            self.trend_direction = "steady"

        # Benchmark gap
        if self.benchmark_overlay_value is not None:
            self.benchmark_gap = self.actual_value - self.benchmark_overlay_value
        elif self.kpi_id and self.kpi.industry_benchmark_value is not None:
            self.benchmark_overlay_value = self.kpi.industry_benchmark_value
            self.benchmark_gap = self.actual_value - self.benchmark_overlay_value
        else:
            self.benchmark_gap = None

        self.evaluated_at = timezone.now()

    def save(self, *args, **kwargs):
        # Default perspective from KPI if not set
        if not self.perspective and self.kpi_id:
            self.perspective = self.kpi.perspective
        # Default target value from KPI if not set
        if not self.target_value and self.kpi_id and self.kpi.target_value:
            self.target_value = self.kpi.target_value
        # Default benchmark overlay from KPI if not set
        if not self.benchmark_overlay_value and self.kpi_id and self.kpi.industry_benchmark_value:
            self.benchmark_overlay_value = self.kpi.industry_benchmark_value

        self.calculate_performance_metrics()
        super().save(*args, **kwargs)
