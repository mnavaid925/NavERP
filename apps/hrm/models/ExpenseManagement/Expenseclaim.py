"""HRM 3.34 Expense Management — Expenseclaim models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class ExpenseClaim(TenantNumbered):
    """3.34 employee T&E claim header. Lean 2-stage status machine (draft -> submitted ->
    manager_approved -> approved -> reimbursed; rejected/cancelled off the open stages).
    total_amount/line_count/has_violations are properties recomputed from .lines — callers MUST
    prefetch_related("lines__category") to avoid N+1."""

    NUMBER_PREFIX = "ECL"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("manager_approved", "Manager Approved"),
        ("approved", "Approved (Finance)"),
        ("reimbursed", "Reimbursed"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
    ]
    OPEN_STATUSES = ("draft", "submitted")  # cancel-eligible; edit/delete are stricter (draft only)
    PAYMENT_METHOD_CHOICES = [
        ("bank_transfer", "Bank Transfer"),
        ("cash", "Cash"),
        ("payroll", "Payroll"),
        ("other", "Other"),
    ]

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="expense_claims")
    title = models.CharField(max_length=255)
    purpose = models.TextField(blank=True, help_text="Why this expense was incurred (trip name, project, etc).")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_expense_claims")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    manager_approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                         blank=True, related_name="hrm_expenseclaim_manager_approvals")
    manager_approved_at = models.DateTimeField(null=True, blank=True)
    finance_approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                         blank=True, related_name="hrm_expenseclaim_finance_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)  # finance-stage decision timestamp
    rejection_reason = models.TextField(blank=True)  # also holds an optional cancel note
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)
    payment_reference = models.CharField(max_length=100, blank=True)
    reimbursed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_expclaim_tnt_emp_st_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_expclaim_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}" if self.number else self.title

    @property
    def total_amount(self):
        # Reuse the prefetch cache when a list/detail view already fetched the lines (sum in Python,
        # 0 extra queries); fall back to one efficient SQL aggregate for a standalone claim.
        if "lines" in getattr(self, "_prefetched_objects_cache", {}):
            return sum((line.amount for line in self.lines.all()), Decimal("0"))
        return self.lines.aggregate(total=Sum("amount"))["total"] or Decimal("0")

    @property
    def line_count(self):
        # If a future prefetched-list template renders this per row, make it cache-aware like total_amount.
        return self.lines.count()

    @property
    def has_violations(self):
        return any(line.policy_violation for line in self.lines.all())
