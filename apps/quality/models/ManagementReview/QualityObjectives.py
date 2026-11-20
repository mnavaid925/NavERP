from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class QualityObjective(TenantNumbered):
    NUMBER_PREFIX = "QOBJ"

    CATEGORY_CHOICES = [
        ("product_quality", "Product Quality & Safety"),
        ("process_performance", "Process Performance & Operational Yield"),
        ("compliance_regulatory", "Regulatory Compliance & Audit Performance"),
        ("customer_satisfaction", "Customer Satisfaction & Complaint Reduction"),
        ("supplier_quality", "Supplier Quality & Incoming Acceptance"),
        ("safety_environmental", "Safety & Environmental Compliance"),
        ("continuous_improvement", "Continuous Improvement & Cost of Quality"),
    ]

    CADENCE_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("semi_annual", "Semi-Annual"),
        ("annual", "Annual"),
    ]

    DIRECTION_CHOICES = [
        ("higher_better", "Higher is Better (>= Target)"),
        ("lower_better", "Lower is Better (<= Target)"),
        ("exact", "Exact Target (= Target)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("on_track", "On Track"),
        ("at_risk", "At Risk"),
        ("behind", "Behind Target"),
        ("achieved", "Achieved"),
        ("abandoned", "Abandoned"),
    ]

    RAG_STATUS_CHOICES = [
        ("green", "Green — On Track"),
        ("amber", "Amber — At Risk"),
        ("red", "Red — Critical Variance"),
        ("neutral", "Neutral — Not Measured"),
    ]

    CATEGORY_CSS = {
        "product_quality": "badge-info",
        "process_performance": "badge-info",
        "compliance_regulatory": "badge-slate",
        "customer_satisfaction": "badge-green",
        "supplier_quality": "badge-amber",
        "safety_environmental": "badge-slate",
        "continuous_improvement": "badge-green",
    }

    STATUS_CSS = {
        "draft": "badge-muted",
        "active": "badge-info",
        "on_track": "badge-green",
        "at_risk": "badge-amber",
        "behind": "badge-red",
        "achieved": "badge-green",
        "abandoned": "badge-slate",
    }

    RAG_CSS = {
        "green": "badge-green",
        "amber": "badge-amber",
        "red": "badge-red",
        "neutral": "badge-muted",
    }

    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default="product_quality", db_index=True)
    period_year = models.PositiveIntegerField(default=2026, db_index=True)
    cadence = models.CharField(max_length=20, choices=CADENCE_CHOICES, default="quarterly")
    metric_unit = models.CharField(max_length=50, default="%")

    baseline_value = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    target_value = models.DecimalField(max_digits=12, decimal_places=3)
    current_value = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    target_direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default="higher_better")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    rag_status = models.CharField(max_length=16, choices=RAG_STATUS_CHOICES, default="neutral", db_index=True)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="quality_objectives",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quality_objectives",
    )

    target_date = models.DateField(null=True, blank=True)
    last_evaluated_date = models.DateField(null=True, blank=True)
    action_plan_summary = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_year", "-created_at"]
        verbose_name = "Quality Objective"
        verbose_name_plural = "Quality Objectives"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="qobj_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qobj_ten_status"),
            models.Index(fields=["tenant", "category"], name="idx_qobj_ten_cat"),
            models.Index(fields=["tenant", "period_year"], name="idx_qobj_ten_year"),
            models.Index(fields=["tenant", "rag_status"], name="idx_qobj_ten_rag"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qobj_ten_created"),
            models.Index(fields=["tenant", "-period_year", "-created_at"], name="idx_qobj_ten_yr_crd"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.period_year})"

    @property
    def variance(self):
        if self.current_value is None or self.target_value is None:
            return None
        return self.current_value - self.target_value

    @property
    def is_achieved(self):
        if self.current_value is None or self.target_value is None:
            return False
        if self.target_direction == "higher_better":
            return self.current_value >= self.target_value
        elif self.target_direction == "lower_better":
            return self.current_value <= self.target_value
        else:
            return self.current_value == self.target_value

    @property
    def progress_percent(self):
        if self.current_value is None or self.target_value is None:
            return 0
        if self.is_achieved:
            return 100
        if self.target_direction == "lower_better":
            if self.baseline_value is not None and self.baseline_value > self.target_value:
                span = self.baseline_value - self.target_value
                progress = self.baseline_value - self.current_value
                pct = int((progress / span) * 100)
                return max(0, min(100, pct))
            if self.current_value > 0 and self.target_value > 0:
                pct = int((self.target_value / self.current_value) * 100)
                return max(0, min(100, pct))
            return 0
        elif self.target_direction == "higher_better":
            if self.baseline_value is not None and self.target_value > self.baseline_value:
                span = self.target_value - self.baseline_value
                progress = self.current_value - self.baseline_value
                pct = int((progress / span) * 100)
                return max(0, min(100, pct))
            if self.target_value != 0:
                pct = int((self.current_value / self.target_value) * 100)
                return max(0, min(100, pct))
            return 0
        else:
            if self.target_value != 0:
                diff = abs(self.current_value - self.target_value)
                pct = int(max(0, 100 - (diff / abs(self.target_value) * 100)))
                return max(0, min(100, pct))
            return 100 if self.is_achieved else 0

    @property
    def category_badge_class(self):
        return self.CATEGORY_CSS.get(self.category, "badge-info")

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-muted")

    @property
    def rag_badge_class(self):
        return self.RAG_CSS.get(self.rag_status, "badge-muted")

    def evaluate_performance(self):
        """Update RAG status and operational status based on current_value vs target_value."""
        if self.current_value is None:
            self.rag_status = "neutral"
            return

        self.last_evaluated_date = timezone.now().date()
        if self.is_achieved:
            self.rag_status = "green"
            self.status = "achieved"
        else:
            if self.target_direction == "higher_better":
                ratio = self.current_value / self.target_value if self.target_value != 0 else Decimal("0")
                if ratio >= Decimal("0.90"):
                    self.rag_status = "amber"
                    self.status = "at_risk"
                else:
                    self.rag_status = "red"
                    self.status = "behind"
            elif self.target_direction == "lower_better":
                ratio = self.target_value / self.current_value if self.current_value != 0 else Decimal("0")
                if ratio >= Decimal("0.90"):
                    self.rag_status = "amber"
                    self.status = "at_risk"
                else:
                    self.rag_status = "red"
                    self.status = "behind"
            else:
                self.rag_status = "red"
                self.status = "behind"
