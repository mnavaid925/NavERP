"""Accounting 2.2 General Ledger — GLAccounts models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class GLAccount(TenantOwned):
    """A Chart-of-Accounts node. Hierarchical (``parent``), typed, and **never** stores a
    balance — :pymeth:`balance` aggregates posted journal lines on demand (invariant 3)."""

    ACCOUNT_TYPE_CHOICES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("equity", "Equity"),
        ("income", "Income"),
        ("expense", "Expense"),
    ]
    NORMAL_BALANCE_CHOICES = [("debit", "Debit"), ("credit", "Credit")]
    DEBIT_NORMAL_TYPES = ("asset", "expense")

    code = models.CharField(max_length=20)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=12, choices=ACCOUNT_TYPE_CHOICES)
    # Derived from account_type in save() — read-only, never on the ModelForm.
    normal_balance = models.CharField(max_length=6, choices=NORMAL_BALANCE_CHOICES, editable=False, default="debit")
    parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="children")
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = ("tenant", "code")
        indexes = [models.Index(fields=["tenant", "is_active"], name="acc_gl_tenant_active_idx")]

    def save(self, *args, **kwargs):
        self.normal_balance = "debit" if self.account_type in self.DEBIT_NORMAL_TYPES else "credit"
        super().save(*args, **kwargs)

    def balance(self):
        """Signed balance in the account's *normal* direction over **posted** lines only."""
        agg = self.journal_lines.filter(entry__status="posted").aggregate(d=Sum("debit"), c=Sum("credit"))
        debit, credit = agg["d"] or ZERO, agg["c"] or ZERO
        return (debit - credit) if self.normal_balance == "debit" else (credit - debit)

    def __str__(self):
        return f"{self.code} · {self.name}"
