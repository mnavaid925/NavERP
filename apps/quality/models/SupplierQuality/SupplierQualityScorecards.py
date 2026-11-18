from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class SupplierQualityScorecard(TenantNumbered):
    NUMBER_PREFIX = "QSSC"

    CADENCE_CHOICES = [
        ("monthly", "Monthly Evaluation"),
        ("quarterly", "Quarterly Evaluation"),
        ("semi_annual", "Semi-Annual Evaluation"),
        ("annual", "Annual Evaluation"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("under_review", "Under Review"),
        ("published", "Published / Final"),
        ("disputed", "Vendor Disputed"),
    ]

    GRADE_CHOICES = [
        ("grade_a", "Grade A (Preferred / Excellent >= 90)"),
        ("grade_b", "Grade B (Approved / Good 80-89.9)"),
        ("grade_c", "Grade C (Conditional / At Risk 70-79.9)"),
        ("grade_d", "Grade D (Unsatisfactory < 70)"),
    ]

    CADENCE_CSS = {
        "monthly": "badge-info",
        "quarterly": "badge-slate",
        "semi_annual": "badge-amber",
        "annual": "badge-slate",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "under_review": "badge-amber",
        "published": "badge-green",
        "disputed": "badge-red",
    }

    GRADE_CSS = {
        "grade_a": "badge-green",
        "grade_b": "badge-info",
        "grade_c": "badge-amber",
        "grade_d": "badge-red",
    }

    supplier = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="quality_scorecards",
        help_text="Evaluated vendor / supplier party",
    )
    cadence = models.CharField(
        max_length=20,
        choices=CADENCE_CHOICES,
        default="quarterly",
        db_index=True,
    )
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )

    # 5 Weighted Dimensions
    lot_acceptance_rate_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Weight 30% (Lots accepted without rejection)",
    )
    defect_ppm_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Weight 25% (Parts per million defect rate score)",
    )
    scar_responsiveness_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Weight 20% (On-time containment and closure of SCARs)",
    )
    audit_compliance_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Weight 15% (QMS audit adherence and findings clearance)",
    )
    documentation_coa_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Weight 10% (CoA accuracy and delivery documentation)",
    )

    overall_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Computed weighted composite score 0-100",
    )
    grade = models.CharField(
        max_length=15,
        choices=GRADE_CHOICES,
        blank=True,
        default="",
        db_index=True,
    )

    total_lots_received = models.PositiveIntegerField(default=0)
    lots_rejected = models.PositiveIntegerField(default=0)
    total_scars_issued = models.PositiveIntegerField(default=0)

    evaluated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evaluated_scorecards",
    )
    is_manual_override = models.BooleanField(default=False)
    override_justification = models.TextField(blank=True)
    evaluation_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-created_at"]
        verbose_name = "Supplier Quality Scorecard"
        verbose_name_plural = "Supplier Quality Scorecards"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="quality_qssc_ten_num_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qssc_ten_status"),
            models.Index(fields=["tenant", "supplier"], name="idx_qssc_ten_supp"),
            models.Index(fields=["tenant", "grade"], name="idx_qssc_ten_grade"),
            models.Index(fields=["tenant", "cadence"], name="idx_qssc_ten_cadence"),
            models.Index(fields=["tenant", "period_start", "period_end"], name="idx_qssc_ten_period"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qssc_ten_created"),
            models.Index(fields=["tenant", "-period_end", "-created_at"], name="idx_qssc_ten_pend_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.supplier.name} ({self.get_cadence_display()} {self.period_end})"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def cadence_css(self):
        return self.CADENCE_CSS.get(self.cadence, "badge-slate")

    @property
    def grade_css(self):
        return self.GRADE_CSS.get(self.grade, "badge-slate")

    @property
    def is_expired(self):
        if self.period_end:
            return self.period_end < timezone.now().date()
        return False

    @property
    def is_action_required(self):
        return self.grade in ("grade_c", "grade_d") or (
            self.overall_score is not None and self.overall_score < Decimal("80.00")
        )

    def calculate_composite_score(self):
        lot_score = self.lot_acceptance_rate_score or Decimal("0.00")
        ppm_score = self.defect_ppm_score or Decimal("0.00")
        scar_score = self.scar_responsiveness_score or Decimal("0.00")
        audit_score = self.audit_compliance_score or Decimal("0.00")
        doc_score = self.documentation_coa_score or Decimal("0.00")

        composite = (
            lot_score * Decimal("0.30")
            + ppm_score * Decimal("0.25")
            + scar_score * Decimal("0.20")
            + audit_score * Decimal("0.15")
            + doc_score * Decimal("0.10")
        )
        return round(composite, 2)

    def determine_grade(self, score):
        if score is None:
            return ""
        if score >= Decimal("90.00"):
            return "grade_a"
        if score >= Decimal("80.00"):
            return "grade_b"
        if score >= Decimal("70.00"):
            return "grade_c"
        return "grade_d"

    def save(self, *args, **kwargs):
        if not self.is_manual_override:
            calculated = self.calculate_composite_score()
            self.overall_score = calculated
            self.grade = self.determine_grade(calculated)
        else:
            if self.overall_score is None:
                self.overall_score = self.calculate_composite_score()
            if not self.grade and self.overall_score is not None:
                self.grade = self.determine_grade(self.overall_score)
        super().save(*args, **kwargs)
