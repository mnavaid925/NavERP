"""Accounting 2.13 Budgeting & Planning — BudgetLines models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class BudgetLine(TenantOwned):
    """One budgeted amount for an account (optionally a cost-centre) within a Budget."""

    budget = models.ForeignKey("accounting.Budget", on_delete=models.CASCADE, related_name="lines")
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.PROTECT, related_name="budget_lines")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="budget_lines")
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["gl_account__code"]

    def __str__(self):
        return f"{self.gl_account_id and self.gl_account.code}: {self.amount}"
