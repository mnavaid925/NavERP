"""Accounting 2.5 Cash Management — BankAccounts models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ============================================================ 2.5 Cash (defined
# before Payment because Payment FKs a BankAccount).
class BankAccount(TenantOwned):
    """A tenant bank account; the anchor for cash positioning and reconciliation."""

    name = models.CharField(max_length=255)
    account_number_last4 = models.CharField(max_length=4, blank=True, help_text="Last 4 digits only — never store the full number")
    bank_name = models.CharField(max_length=255, blank=True)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="bank_accounts")
    gl_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="bank_accounts", help_text="The GL cash account this bank maps to")
    opening_balance = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    opening_balance_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def current_balance(self):
        agg = self.transactions.aggregate(
            credit=Sum("amount", filter=Q(direction="credit")),
            debit=Sum("amount", filter=Q(direction="debit")),
        )
        return (self.opening_balance or ZERO) + (agg["credit"] or ZERO) - (agg["debit"] or ZERO)

    def __str__(self):
        return self.name
