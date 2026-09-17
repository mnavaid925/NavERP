"""Projects 7.12 Portfolio & Program Management — Portfolio [PRT-].

Realizes NavERP 7.12 bullet 1 Portfolio Dashboard & Heat Maps (investment envelope)
and bullet 5 Portfolio Reporting & Governance.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class Portfolio(TenantNumbered):
    NUMBER_PREFIX = "PRT"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("on_hold", "On Hold"),
        ("closed", "Closed"),
        ("archived", "Archived"),
    ]

    STRATEGIC_THEME_CHOICES = [
        ("growth", "Growth & Market Expansion"),
        ("efficiency", "Operational Efficiency"),
        ("transformation", "Digital Transformation"),
        ("compliance", "Regulatory & Compliance"),
        ("innovation", "Innovation & R&D"),
        ("customer_experience", "Customer Experience"),
    ]

    name = models.CharField(max_length=255)
    code = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_portfolios",
    )
    strategic_theme = models.CharField(
        max_length=30, choices=STRATEGIC_THEME_CHOICES, default="transformation"
    )
    budget_envelope = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"),)
        indexes = [
            models.Index(fields=["tenant", "status"], name="prt_tnt_status_idx"),
            models.Index(fields=["tenant", "strategic_theme"], name="prt_tnt_theme_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def total_programs(self):
        return self.programs.count()

    @property
    def total_investments(self):
        return self.investments.count()

    @property
    def allocated_budget(self):
        agg = self.investments.aggregate(s=models.Sum("allocated_budget"))["s"]
        return q2(agg or ZERO)

    @property
    def budget_variance(self):
        return q2(self.budget_envelope - self.allocated_budget)
