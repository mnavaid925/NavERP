"""Accounting 2.4 Accounts Receivable — CustomerProfiles models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class CustomerProfile(TenantOwned):
    """Thin AR extension on a ``core.Party`` (the customer) with credit controls."""

    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="customer_profile")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="customer_profiles")
    credit_limit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    ar_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="customer_ar_accounts")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="customer_profiles")
    credit_on_hold = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["party__name"]

    def __str__(self):
        return f"Customer: {self.party_id and self.party.name}"
