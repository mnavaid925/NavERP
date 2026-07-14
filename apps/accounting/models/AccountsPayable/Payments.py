"""Accounting 2.3 Accounts Payable — Payments models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# =================================================== 2.3+2.4 shared Payment + cash application
class Payment(TenantNumbered):
    """A unified inbound (customer receipt) / outbound (vendor payment) money movement [PAY-]."""

    NUMBER_PREFIX = "PAY"

    DIRECTION_CHOICES = [("in", "Inbound — Customer Receipt"), ("out", "Outbound — Vendor Payment")]
    METHOD_CHOICES = [
        ("bank_transfer", "Bank Transfer"),
        ("check", "Check"),
        ("cash", "Cash"),
        ("card", "Card"),
        ("ach", "ACH"),
        ("wire", "Wire Transfer"),
    ]
    STATUS_CHOICES = [("draft", "Draft"), ("confirmed", "Confirmed"), ("void", "Void")]

    direction = models.CharField(max_length=3, choices=DIRECTION_CHOICES)
    party = models.ForeignKey("core.Party", on_delete=models.PROTECT, related_name="accounting_payments")
    bank_account = models.ForeignKey("accounting.BankAccount", on_delete=models.PROTECT, related_name="payments")
    payment_method = models.CharField(max_length=16, choices=METHOD_CHOICES, default="bank_transfer")
    payment_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="payments")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    journal_entry = models.ForeignKey("accounting.JournalEntry", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="payments", editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [models.Index(fields=["tenant", "status"], name="acc_pay_tenant_status_idx")]

    @property
    def is_locked(self):
        return self.status in ("confirmed", "void")

    def allocated_total(self):
        return self.allocations.aggregate(s=Sum("allocated_amount"))["s"] or ZERO

    def unallocated(self):
        return (self.amount or ZERO) - self.allocated_total()

    def __str__(self):
        return self.number or f"PAY #{self.pk}"
