"""CRM 1.2 Sales Force Automation — PriceBooks models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class PriceBook(TenantNumbered):
    """A regional/tier price list (1.2 Quoting). ``price_adjustment_pct`` shifts a product's
    base price by ±% for this book (e.g. EU Tier-2 = -10%) — a per-product override table
    (PriceBookEntry) is a documented future enhancement, not built here."""

    NUMBER_PREFIX = "PB"

    name = models.CharField(max_length=255)
    currency_code = models.CharField(max_length=3, default="USD")
    region = models.CharField(max_length=120, blank=True)
    tier = models.CharField(max_length=120, blank=True)
    price_adjustment_pct = models.DecimalField(  # ± off base; floor at -100% so it can't make a negative price
        max_digits=6, decimal_places=2, default=0, validators=[MinValueValidator(-100)])
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_default", "name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="crm_pb_tnt_active_idx"),
            models.Index(fields=["tenant", "is_default"], name="crm_pb_tnt_default_idx"),
        ]

    def adjusted_price(self, base):
        """Apply this book's ± adjustment to a product base price (Decimal-safe)."""
        base = Decimal(base or 0)
        return base * (Decimal(100) + Decimal(self.price_adjustment_pct or 0)) / 100

    def __str__(self):
        return f"{self.number} · {self.name}"
