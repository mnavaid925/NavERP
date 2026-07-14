"""Accounting 2.5 Cash Management — BankTransactions models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# =============================================================== 2.5 Bank txns + reconciliation
class BankTransaction(TenantOwned):
    """An imported / fed / manual bank-statement line awaiting reconciliation."""

    DIRECTION_CHOICES = [("credit", "Credit — Money In"), ("debit", "Debit — Money Out")]
    SOURCE_CHOICES = [("manual", "Manual Entry"), ("csv_import", "CSV Import"), ("bank_feed", "Bank Feed")]
    STATUS_CHOICES = [
        ("unmatched", "Unmatched"),
        ("matched", "Matched"),
        ("reconciled", "Reconciled"),
        ("excluded", "Excluded"),
    ]

    bank_account = models.ForeignKey("accounting.BankAccount", on_delete=models.CASCADE, related_name="transactions")
    transaction_date = models.DateField()
    description = models.CharField(max_length=512)
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    direction = models.CharField(max_length=6, choices=DIRECTION_CHOICES)
    source = models.CharField(max_length=12, choices=SOURCE_CHOICES, default="manual")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="unmatched", editable=False)
    external_ref = models.CharField(max_length=255, blank=True, help_text="Bank's own transaction id (dedupe key)")

    class Meta:
        ordering = ["-transaction_date", "-id"]
        indexes = [models.Index(fields=["tenant", "transaction_date"], name="acc_bt_tenant_date_idx")]

    def __str__(self):
        return f"{self.transaction_date} · {self.description[:40]}"
