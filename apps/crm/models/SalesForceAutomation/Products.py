"""CRM 1.2 Sales Force Automation — Products models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class Product(TenantNumbered):
    """A sales-catalog product/service (1.2 Quoting). CRM-owned for now — migrate to the
    shared ``core.Item`` master once Inventory (Module 5) ships. Distinct from the 1.12
    ``ProductStock`` (which tracks on-hand inventory, not a sellable catalog + list price)."""

    NUMBER_PREFIX = "PRD"

    TYPE_CHOICES = [
        ("good", "Good"),
        ("service", "Service"),
        ("subscription", "Subscription"),
    ]

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=64, blank=True)
    product_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default="good")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_pct = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                  validators=[MinValueValidator(0), MaxValueValidator(100)])
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "product_type"], name="crm_prd_tnt_type_idx"),
            models.Index(fields=["tenant", "is_active"], name="crm_prd_tnt_active_idx"),
        ]

    @property
    def margin_pct(self):
        """Gross margin %, or None when no price is set. Decimal-safe on a fresh instance."""
        price = Decimal(self.unit_price or 0)
        if not price:
            return None
        return (price - Decimal(self.cost or 0)) / price * 100

    def __str__(self):
        return f"{self.number} · {self.name}"
