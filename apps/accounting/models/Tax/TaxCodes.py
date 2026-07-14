"""Accounting 2.11 Tax — TaxCodes models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


# ============================================================================ 2.11 Tax
class TaxCode(TenantOwned):
    """A tax rate master (sales/VAT/GST/use) pointing at its payable GL account."""

    TAX_TYPE_CHOICES = [("sales", "Sales Tax"), ("vat", "VAT"), ("gst", "GST"), ("use", "Use Tax")]

    name = models.CharField(max_length=120)
    jurisdiction = models.CharField(max_length=120, blank=True)
    tax_type = models.CharField(max_length=8, choices=TAX_TYPE_CHOICES, default="sales")
    rate_pct = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    payable_account = models.ForeignKey("accounting.GLAccount", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="tax_codes")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.rate_pct}%)"
