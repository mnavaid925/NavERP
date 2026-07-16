"""HRM 3.34 Expense Management — Expenseclaimline models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class ExpenseClaimLine(TenantOwned):
    """One expense line on a claim. policy_violation/violation_reason are COMPUTED (never stored) —
    always current, no stale-flag risk. Editable only while the parent claim is status='draft'
    (enforced in the views)."""

    claim = models.ForeignKey("hrm.ExpenseClaim", on_delete=models.CASCADE, related_name="lines")
    category = models.ForeignKey("hrm.ExpenseCategory", on_delete=models.PROTECT, related_name="claim_lines")
    expense_date = models.DateField()
    merchant = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    # WARNING: extension allowlist + size cap enforced in ExpenseClaimLineForm.clean_receipt (shared
    # _validate_upload). Keep MEDIA_ROOT outside the web root and serve with Content-Disposition:
    # attachment + X-Content-Type-Options: nosniff in production (mirrors InvestmentProof).
    receipt = models.FileField(upload_to="hrm/expense_receipts/%Y/%m/", null=True, blank=True)

    class Meta:
        ordering = ["expense_date", "id"]
        indexes = [models.Index(fields=["tenant", "claim"], name="hrm_expline_tnt_claim_idx")]

    def __str__(self):
        cat = self.category.name if self.category_id else "Uncategorized"
        return f"{self.claim.number if self.claim_id else '?'} - {cat} - {self.amount}"

    def _policy_check(self):
        """(violation, reason) — both comparisons None-guarded. Checks per_claim_limit (amount) +
        requires_receipt_above (receipt presence). monthly_limit is NOT checked here (deferred)."""
        if not self.category_id or self.amount is None:
            return False, ""
        cat = self.category
        reasons = []
        if cat.per_claim_limit is not None and self.amount > cat.per_claim_limit:
            reasons.append(f"Exceeds per-claim limit of {cat.per_claim_limit}")
        if (cat.requires_receipt_above is not None and self.amount > cat.requires_receipt_above
                and not self.receipt):
            reasons.append(f"Receipt required above {cat.requires_receipt_above}")
        return bool(reasons), "; ".join(reasons)

    @property
    def policy_violation(self):
        return self._policy_check()[0]

    @property
    def violation_reason(self):
        return self._policy_check()[1]
