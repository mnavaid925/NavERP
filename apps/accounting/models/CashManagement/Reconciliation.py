"""Accounting 2.5 Cash Management — Reconciliation models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class ReconciliationMatch(TenantOwned):
    """A confirmed pairing of a :class:`BankTransaction` with a Payment or JournalLine."""

    bank_transaction = models.ForeignKey("accounting.BankTransaction", on_delete=models.CASCADE, related_name="matches")
    payment = models.ForeignKey("accounting.Payment", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="reconciliation_matches")
    journal_line = models.ForeignKey("accounting.JournalLine", on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="reconciliation_matches")
    matched_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="accounting_reconciliation_matches", editable=False)
    matched_at = models.DateTimeField(auto_now_add=True)
    is_confirmed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-matched_at"]

    def __str__(self):
        return f"Match #{self.pk} · {self.bank_transaction_id}"
