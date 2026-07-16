"""HRM 3.17 Payout & Reports — PayoutPayments models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class PayoutPayment(TenantOwned):
    """One employee's disbursement row within a ``PayoutBatch`` (3.17). ``net_amount`` + the bank fields
    are SNAPSHOTTED at generation — the bank fields are the employee's **already-masked** values
    (``masked_bank_account()``/``masked_bank_routing()``), never the raw account number, so they need no
    ``_SENSITIVE_AUDIT_FIELDS`` redaction. A failed payment is re-tried as a NEW row (``retry_of`` → the
    original), preserving the failure history — so there is deliberately **no** ``unique_together`` on
    ``(batch, payslip)`` (that would block a retry); the generate action guarantees one *original* per
    payslip (draft-only delete+recreate), and there is no user-facing create form."""

    PAYMENT_METHOD_CHOICES = [
        ("bank_transfer", "Bank Transfer"),
        ("neft", "NEFT"),
        ("nach", "NACH"),
        ("ach", "ACH"),
        ("cheque", "Cheque"),
        ("cash", "Cash"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("returned", "Returned"),
        ("on_hold", "On Hold"),
    ]

    batch = models.ForeignKey("hrm.PayoutBatch", on_delete=models.CASCADE, related_name="payments")
    payslip = models.ForeignKey("hrm.Payslip", on_delete=models.PROTECT, related_name="payout_payments")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="payout_payments")
    net_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False,
        help_text="Snapshot of Payslip.net_pay at generation time.")
    bank_name_snapshot = models.CharField(max_length=255, blank=True, editable=False)
    bank_account_last4_snapshot = models.CharField(max_length=8, blank=True, editable=False,
        help_text="Masked last-4 of the destination account — never the full number.")
    bank_routing_snapshot = models.CharField(max_length=20, blank=True, editable=False)
    payment_method = models.CharField(max_length=15, choices=PAYMENT_METHOD_CHOICES, default="bank_transfer")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    transaction_reference = models.CharField(max_length=64, blank=True,
        help_text="Bank-assigned UTR / trace number — the reconciliation match key.")
    initiated_at = models.DateTimeField(null=True, blank=True, editable=False)
    paid_on = models.DateTimeField(null=True, blank=True, editable=False)
    failure_reason = models.TextField(blank=True)
    retry_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="retries")

    class Meta:
        ordering = ["batch", "employee__party__name"]
        indexes = [
            models.Index(fields=["tenant", "batch"], name="hrm_pop_tenant_batch_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_pop_tenant_status_idx"),
        ]

    def __str__(self):
        return f"{self.employee} · {self.net_amount} · {self.get_status_display()}"
