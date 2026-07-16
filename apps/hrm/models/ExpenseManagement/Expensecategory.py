"""HRM 3.34 Expense Management — Expensecategory models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.34 Expense Management — ExpenseCategory / ExpenseClaim / ExpenseClaimLine
#
# Employee T&E claims (distinct from crm.Expense [sales/deal] and from payroll's
# reimbursement_amount/PayComponent(reimbursement), which is a deferred payout integration).
# A claim header has line items (each with a receipt) and a 2-stage manager->finance approval
# machine. Policy compliance is a COMPUTED soft-flag per line (never stored). No GL posting.
# ---------------------------------------------------------------------------
class ExpenseCategory(TenantOwned):
    """3.34 expense taxonomy (Travel/Food/Accommodation/...) + the per-category policy limits that
    ExpenseClaimLine.policy_violation checks against. gl_account_hint is a coding HINT only — no GL
    posting happens from this module."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    per_claim_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Max amount for a single expense line in this category. Blank = no limit.")
    monthly_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Max total per employee per month. Not enforced automatically this pass.")
    requires_receipt_above = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="A line above this amount must have a receipt attached. Blank = never required.")
    gl_account_hint = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="hrm_expense_category_hints")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        indexes = [models.Index(fields=["tenant", "is_active"], name="hrm_expcat_tnt_active_idx")]

    def __str__(self):
        return f"{self.name} ({self.code})" if self.code else self.name
