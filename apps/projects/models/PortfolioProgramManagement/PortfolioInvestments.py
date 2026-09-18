"""Projects 7.12 Portfolio & Program Management — PortfolioInvestment [PIN-].

Realizes NavERP 7.12 bullet 3 Strategic Alignment & Scoring (OKR linkage, multi-criteria scoring)
and bullet 5 Portfolio Reporting & Governance (investment decisions).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class PortfolioInvestment(TenantNumbered):
    NUMBER_PREFIX = "PIN"

    STATUS_CHOICES = [
        ("proposed", "Proposed"),
        ("under_review", "Under Review"),
        ("funded", "Funded"),
        ("deferred", "Deferred"),
        ("rejected", "Rejected"),
    ]

    portfolio = models.ForeignKey(
        "projects.Portfolio",
        on_delete=models.CASCADE,
        related_name="investments",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="portfolio_investments",
    )
    program = models.ForeignKey(
        "projects.Program",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investments",
    )
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="proposed")

    # The 4 Scoring Criteria (0 - 100 scale)
    strategic_fit = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Alignment to strategic goals and OKRs (0-100).",
    )
    financial_return = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Expected ROI, NPV or cost reduction (0-100).",
    )
    delivery_risk = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Risk score: 100 = minimal risk / easiest execution, 0 = highest risk.",
    )
    capacity_fit = models.PositiveSmallIntegerField(
        default=50,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Resource availability and skills suitability (0-100).",
    )

    # Weights for criteria (Default 25 each, sum = 100)
    weight_strategic = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    weight_financial = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    weight_risk = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    weight_capacity = models.PositiveSmallIntegerField(
        default=25,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    allocated_budget = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    decision_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["portfolio_id", "-created_at"]
        unique_together = (
            ("tenant", "number"),
            ("tenant", "portfolio", "project"),
        )
        indexes = [
            models.Index(fields=["tenant", "portfolio"], name="pin_tnt_portfolio_idx"),
            models.Index(fields=["tenant", "status"], name="pin_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.project.name} ({self.portfolio.name})"

    @property
    def weighted_score(self):
        total_w = (
            self.weight_strategic
            + self.weight_financial
            + self.weight_risk
            + self.weight_capacity
        ) or 100
        score = (
            Decimal(self.strategic_fit * self.weight_strategic)
            + Decimal(self.financial_return * self.weight_financial)
            + Decimal(self.delivery_risk * self.weight_risk)
            + Decimal(self.capacity_fit * self.weight_capacity)
        ) / Decimal(total_w)
        return score.quantize(Decimal("0.1"))

    def clean(self):
        super().clean()
        if self.tenant_id:
            if self.project_id and self.project.tenant_id != self.tenant_id:
                raise ValidationError("Project belongs to a different workspace.")
            if self.portfolio_id and self.portfolio.tenant_id != self.tenant_id:
                raise ValidationError("Portfolio belongs to a different workspace.")
            if self.program_id:
                if self.program.tenant_id != self.tenant_id:
                    raise ValidationError("Program belongs to a different workspace.")
                if self.portfolio_id and self.program.portfolio_id != self.portfolio_id:
                    raise ValidationError("Selected program does not belong to the selected portfolio.")
