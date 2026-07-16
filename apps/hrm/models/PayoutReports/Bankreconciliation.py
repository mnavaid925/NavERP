"""HRM 3.17 Payout & Reports — Bankreconciliation models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class BankReconciliation(TenantNumbered):
    """Reconciles a ``PayoutBatch``'s payments against an imported bank statement (3.17) — ``BRC-#####``.
    ``recompute()`` matches by ``PayoutPayment.transaction_reference``/``status`` (no separate
    ``BankStatementLine`` table); matched/unmatched aggregates are derived."""

    NUMBER_PREFIX = "BRC"

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("reconciled", "Reconciled"),
        ("discrepancy", "Discrepancy"),
    ]

    batch = models.ForeignKey("hrm.PayoutBatch", on_delete=models.PROTECT, related_name="reconciliations")
    statement_date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    matched_count = models.PositiveIntegerField(default=0, editable=False)
    matched_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    unmatched_count = models.PositiveIntegerField(default=0, editable=False)
    unmatched_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    statement_reference = models.CharField(max_length=100, blank=True)
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_bank_reconciliations", editable=False)
    reconciled_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-statement_date"]
        indexes = [
            models.Index(fields=["tenant", "batch"], name="hrm_brc_tenant_batch_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_brc_tenant_status_idx"),
        ]

    def recompute(self):
        """Match the batch's current payments against the (implicit) bank statement by UTR + status:
        a payment with a transaction_reference AND status=paid is matched; everything else (failed/
        returned, or a processing/pending row with no UTR) is unmatched. Sets aggregates + status."""
        cur = self.batch._current_payments()
        matched = cur.filter(status="paid").exclude(transaction_reference="")
        unmatched = cur.exclude(pk__in=matched.values("pk"))
        m = matched.aggregate(c=Count("id"), a=Sum("net_amount"))
        u = unmatched.aggregate(c=Count("id"), a=Sum("net_amount"))
        self.matched_count = m["c"] or 0
        self.matched_amount = m["a"] or ZERO
        self.unmatched_count = u["c"] or 0
        self.unmatched_amount = u["a"] or ZERO
        self.status = "reconciled" if self.unmatched_count == 0 else "discrepancy"
        self.reconciled_at = timezone.now()
        self.save(update_fields=["matched_count", "matched_amount", "unmatched_count",
                                 "unmatched_amount", "status", "reconciled_at", "updated_at"])

    def __str__(self):
        return f"{self.number} · {self.batch.number} · {self.get_status_display()}"
