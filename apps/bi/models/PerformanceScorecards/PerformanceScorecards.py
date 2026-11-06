from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered


class PerformanceScorecard(TenantNumbered):
    NUMBER_PREFIX = "BSCR"

    SCORECARD_TYPE_CHOICES = [
        ("balanced_scorecard", "Balanced Scorecard (4 Perspectives)"),
        ("executive", "Executive Leadership Scorecard"),
        ("departmental", "Departmental Operating Scorecard"),
        ("operational", "Operational Excellence Scorecard"),
        ("strategic_initiative", "Strategic Initiative Scorecard"),
    ]

    PERIOD_CHOICES = [
        ("monthly", "Monthly"),
        ("quarterly", "Quarterly"),
        ("semi_annual", "Semi-Annual"),
        ("annual", "Annual"),
        ("rolling_12_months", "Rolling 12 Months"),
    ]

    RAG_STATUS_CHOICES = [
        ("green", "Green (On Track)"),
        ("amber", "Amber (Needs Attention)"),
        ("red", "Red (Critical / Off Track)"),
        ("gray", "Gray (Not Evaluated)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Setup"),
        ("active", "Active Scorecard"),
        ("in_review", "In Review / Audit"),
        ("closed", "Closed Period"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    scorecard_type = models.CharField(max_length=30, choices=SCORECARD_TYPE_CHOICES, default="balanced_scorecard")
    review_period = models.CharField(max_length=20, choices=PERIOD_CHOICES, default="quarterly")
    fiscal_year = models.PositiveIntegerField(default=2026)

    # 4 Kaplan & Norton Perspectives Target Weights (%)
    financial_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("25.00"))
    customer_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("25.00"))
    internal_process_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("25.00"))
    learning_growth_weight = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("25.00"))

    # Calculated Roll-up Score & Overall RAG Health
    overall_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Weighted roll-up score from 0.00 to 100.00%",
    )
    overall_rag_status = models.CharField(max_length=10, choices=RAG_STATUS_CHOICES, default="gray")

    # Publishing & Governance
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    is_default = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="owned_scorecards",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="performance_scorecards",
    )
    last_recalculated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fiscal_year", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_bscr_tenant_slug_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_bscr_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "scorecard_type"], name="idx_bscr_ten_type"),
            models.Index(fields=["tenant", "status"], name="idx_bscr_ten_stat"),
            models.Index(fields=["tenant", "owner"], name="idx_bscr_ten_owner"),
            models.Index(fields=["tenant", "fiscal_year"], name="idx_bscr_ten_fyr"),
            models.Index(fields=["tenant", "overall_rag_status"], name="idx_bscr_ten_rag"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name} ({self.fiscal_year})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)[:120]
        if self.is_default and self.tenant_id:
            PerformanceScorecard.objects.filter(tenant=self.tenant, is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("bi:performance_scorecard_detail", kwargs={"pk": self.pk})

    def recalculate_performance(self):
        """Aggregate KPI scores across 4 perspectives and calculate overall weighted index."""
        assignments = list(self.kpi_assignments.select_related("kpi").all())
        if not assignments:
            self.overall_score = Decimal("0.00")
            self.overall_rag_status = "gray"
            self.last_recalculated_at = timezone.now()
            self.save(update_fields=["overall_score", "overall_rag_status", "last_recalculated_at", "updated_at"])
            return

        perspectives = {
            "financial": {"weight": self.financial_weight, "items": []},
            "customer": {"weight": self.customer_weight, "items": []},
            "internal_process": {"weight": self.internal_process_weight, "items": []},
            "learning_growth": {"weight": self.learning_growth_weight, "items": []},
        }

        for a in assignments:
            persp = a.perspective
            if persp in perspectives:
                perspectives[persp]["items"].append(a)

        total_score = Decimal("0.00")
        total_weight_evaluated = Decimal("0.00")

        for persp, data in perspectives.items():
            items = data["items"]
            persp_weight = data["weight"]
            if not items or persp_weight <= Decimal("0.00"):
                continue

            persp_item_weights = sum(item.weight for item in items)
            if persp_item_weights > Decimal("0.00"):
                persp_score = sum(
                    (item.normalized_score * item.weight) / persp_item_weights
                    for item in items
                )
            else:
                persp_score = sum(item.normalized_score for item in items) / Decimal(str(len(items)))

            total_score += (persp_score * persp_weight)
            total_weight_evaluated += persp_weight

        if total_weight_evaluated > Decimal("0.00"):
            self.overall_score = round(total_score / total_weight_evaluated, 2)
        else:
            self.overall_score = Decimal("0.00")

        if self.overall_score >= Decimal("85.00"):
            self.overall_rag_status = "green"
        elif self.overall_score >= Decimal("70.00"):
            self.overall_rag_status = "amber"
        elif self.overall_score > Decimal("0.00"):
            self.overall_rag_status = "red"
        else:
            self.overall_rag_status = "gray"

        self.last_recalculated_at = timezone.now()
        self.save(update_fields=["overall_score", "overall_rag_status", "last_recalculated_at", "updated_at"])

    def get_perspective_summary(self, assignments=None):
        """Return counts and average scores per BSC perspective."""
        if assignments is None:
            assignments = list(self.kpi_assignments.all())
        summary = {
            "financial": {"name": "Financial", "count": 0, "on_track": 0, "avg_score": Decimal("0.00")},
            "customer": {"name": "Customer", "count": 0, "on_track": 0, "avg_score": Decimal("0.00")},
            "internal_process": {"name": "Internal Process", "count": 0, "on_track": 0, "avg_score": Decimal("0.00")},
            "learning_growth": {"name": "Learning & Growth", "count": 0, "on_track": 0, "avg_score": Decimal("0.00")},
        }

        for a in assignments:
            p = a.perspective
            if p in summary:
                summary[p]["count"] += 1
                if a.rag_status == "green":
                    summary[p]["on_track"] += 1
                summary[p]["avg_score"] += a.normalized_score

        for p, data in summary.items():
            if data["count"] > 0:
                data["avg_score"] = round(data["avg_score"] / Decimal(str(data["count"])), 2)

        return summary
