"""Accounting 2.3 Accounts Payable — VendorProfiles models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class VendorProfile(TenantOwned):
    """Thin AP extension on a ``core.Party`` (the vendor). One per Party per workspace."""

    party = models.OneToOneField("core.Party", on_delete=models.CASCADE, related_name="vendor_profile")
    payment_terms = models.ForeignKey("accounting.PaymentTerm", on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="vendor_profiles")
    default_expense_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                                related_name="vendor_default_expense")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="vendor_profiles")
    is_1099 = models.BooleanField(default=False, verbose_name="1099/W-9 vendor")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["party__name"]

    def __str__(self):
        return f"Vendor: {self.party_id and self.party.name}"
