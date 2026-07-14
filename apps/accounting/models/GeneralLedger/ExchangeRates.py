"""Accounting 2.2 General Ledger — ExchangeRates models (split from models.py/models_advanced.py)."""
from apps.accounting.models._base import *  # noqa: F401,F403


class ExchangeRate(TenantOwned):
    """Daily spot rate for a currency (functional currency assumed = tenant base)."""

    SOURCE_CHOICES = [("manual", "Manual"), ("feed", "Feed")]

    currency = models.ForeignKey("accounting.Currency", on_delete=models.CASCADE, related_name="exchange_rates")
    rate_date = models.DateField()
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default="manual")

    class Meta:
        ordering = ["-rate_date", "currency__code"]
        unique_together = ("tenant", "currency", "rate_date")
        indexes = [models.Index(fields=["tenant", "rate_date"], name="acc_fx_tenant_date_idx")]

    def __str__(self):
        return f"{self.currency_id and self.currency.code} @ {self.rate} ({self.rate_date})"
