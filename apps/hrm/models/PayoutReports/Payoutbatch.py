"""HRM 3.17 Payout & Reports — Payoutbatch models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.17 Payout & Reports — the salary DISBURSEMENT + distribution + reconciliation
# layer on top of 3.14 (PayrollCycle/Payslip). A PayoutBatch is generated from a
# LOCKED PayrollCycle's payslips; PayoutPayment tracks per-employee money-movement
# status (paid/failed/returned) against a snapshot of net_pay + the employee's
# MASKED bank details; PayslipDistribution tracks send/view/download of the payslip;
# BankReconciliation matches a batch's payments to the bank statement by UTR. This is
# bookkeeping ABOUT payments, not a ledger entry — money still posts only through
# accounting.PayrollRun/JournalEntry (L29); 3.17 posts NOTHING new to the GL. The
# actual bank-file writer + payslip-PDF rendering + live bank API are deferred.
# ---------------------------------------------------------------------------
class PayoutBatch(TenantNumbered):
    """A salary-disbursement run header (3.17) — ``POB-#####`` — generated from one **locked**
    ``PayrollCycle``'s payslips. Derived ``total_amount``/``paid_*``/``failed_count`` come from its
    ``PayoutPayment``s (over the non-superseded, i.e. non-retried, rows). One batch per cycle."""

    NUMBER_PREFIX = "POB"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("approved", "Approved"),
        ("disbursed", "Disbursed"),
        ("partially_disbursed", "Partially Disbursed"),
        ("reconciled", "Reconciled"),
    ]
    BANK_FILE_FORMAT_CHOICES = [
        ("neft", "NEFT"),
        ("nach", "NACH"),
        ("ach", "ACH"),
        ("manual", "Manual"),
        ("other", "Other"),
    ]

    cycle = models.ForeignKey("hrm.PayrollCycle", on_delete=models.PROTECT, related_name="payout_batches")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    bank_file_format = models.CharField(max_length=15, choices=BANK_FILE_FORMAT_CHOICES, default="neft")
    source_bank_name = models.CharField(max_length=255, blank=True,
        help_text="The disbursing (company) bank surfaced before initiating payment.")
    source_account_last4 = models.CharField(max_length=8, blank=True,
        validators=[RegexValidator(r"^(••••)?\d{0,4}$",
            "Enter only a masked last-4 (e.g. ••••4321), never the full account number.")],
        help_text="Masked disbursing account — never the full number.")
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_payout_batch_generations", editable=False)
    generated_at = models.DateTimeField(null=True, blank=True, editable=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="hrm_payout_batch_approvals", editable=False)
    approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    disbursed_at = models.DateTimeField(null=True, blank=True, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-cycle__pay_date"]
        unique_together = ("tenant", "cycle")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_pob_tenant_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.cycle_id and not self.cycle.is_locked:
            raise ValidationError({"cycle": "A payout batch can only be created from a locked payroll cycle."})

    @property
    def is_editable(self):
        return self.status == "draft"

    def _current_payments(self):
        """The non-superseded payment rows (a retried failed row is excluded — its retry is the current
        one) — the correct set for totals so a retried employee is never double-counted."""
        return self.payments.filter(retries__isnull=True)

    def _totals(self):
        """One aggregate pass over the current payments, cached per instance (mirrors PayrollCycle._totals)."""
        if not hasattr(self, "_totals_cache"):
            cur = self._current_payments()
            self._totals_cache = cur.aggregate(
                head=Count("id"), total=Sum("net_amount"),
                paid_c=Count("id", filter=Q(status="paid")),
                paid_a=Sum("net_amount", filter=Q(status="paid")),
                failed_c=Count("id", filter=Q(status__in=["failed", "returned"])),
                hold_c=Count("id", filter=Q(status="on_hold")))
        return self._totals_cache

    @property
    def headcount(self):
        return self._totals()["head"] or 0

    @property
    def total_amount(self):
        return self._totals()["total"] or ZERO

    @property
    def paid_count(self):
        return self._totals()["paid_c"] or 0

    @property
    def paid_amount(self):
        return self._totals()["paid_a"] or ZERO

    @property
    def failed_count(self):
        return self._totals()["failed_c"] or 0

    @property
    def on_hold_count(self):
        return self._totals()["hold_c"] or 0

    def __str__(self):
        return f"{self.number} · {self.cycle.number} · {self.get_status_display()}"
