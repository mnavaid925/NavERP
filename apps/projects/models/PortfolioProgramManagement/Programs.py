"""Projects 7.12 Portfolio & Program Management — Program [PGM-].

Realizes NavERP 7.12 bullet 2 Program Dependency Mapping (delivery container).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models


class Program(TenantNumbered):
    NUMBER_PREFIX = "PGM"

    STATUS_CHOICES = [
        ("proposed", "Proposed"),
        ("planning", "Planning"),
        ("active", "Active"),
        ("on_hold", "On Hold"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    portfolio = models.ForeignKey(
        "projects.Portfolio",
        on_delete=models.CASCADE,
        related_name="programs",
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=30, blank=True)
    description = models.TextField(blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_programs",
    )
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="proposed")
    target_start_date = models.DateField(null=True, blank=True)
    target_end_date = models.DateField(null=True, blank=True)
    objectives = models.TextField(blank=True)
    budget_target = models.DecimalField(max_digits=14, decimal_places=2, default=ZERO)

    class Meta:
        ordering = ["portfolio_id", "-created_at"]
        unique_together = (
            ("tenant", "number"),
            ("tenant", "portfolio", "name"),
        )
        indexes = [
            models.Index(fields=["tenant", "portfolio"], name="pgm_tnt_portfolio_idx"),
            models.Index(fields=["tenant", "status"], name="pgm_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def total_projects(self):
        return self.investments.count()

    @property
    def allocated_budget(self):
        agg = self.investments.aggregate(s=models.Sum("allocated_budget"))["s"]
        return q2(agg or ZERO)
