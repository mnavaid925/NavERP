"""Accounting 2.13 Budgeting & Planning — Budgets models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# =============================================================== 2.13 Budgeting & Planning
class Budget(TenantNumbered):
    """A budget version for a fiscal period. Lines are entered as standalone ``BudgetLine`` rows;
    the budget-variance report compares them to posted actuals."""

    NUMBER_PREFIX = "BUD"
    VERSION_CHOICES = [("original", "Original"), ("revised", "Revised"), ("forecast", "Forecast")]
    STATUS_CHOICES = [("draft", "Draft"), ("approved", "Approved"), ("archived", "Archived")]

    name = models.CharField(max_length=255)
    fiscal_period = models.ForeignKey("accounting.FiscalPeriod", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="budgets")
    version = models.CharField(max_length=10, choices=VERSION_CHOICES, default="original")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-id"]
        unique_together = ("tenant", "number")

    def total(self):
        from django.db.models import Sum
        return self.lines.aggregate(s=Sum("amount"))["s"] or ZERO

    def __str__(self):
        return f"{self.number} · {self.name}"
