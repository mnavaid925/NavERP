from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class FlashSale(TenantNumbered):
    """
    Time-delimited high-velocity flash sales and lightning deals.
    Provides live countdown metadata, inventory reservation quotas, and purchase limits.
    """

    NUMBER_PREFIX = "EFLS"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("ended", "Ended"),
    ]

    title = models.CharField(
        max_length=255,
        help_text="Flash sale event headline (e.g. Midnight Lightning Deal - 40% Off Audio)",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Operational lifecycle state",
    )
    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flash_sales",
        help_text="Featured catalog product",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flash_sales",
        help_text="Featured product SKU variant",
    )
    category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flash_sales",
        help_text="Featured store category",
    )
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("20.00"),
        validators=[MinValueValidator(Decimal("0.00")), MaxValueValidator(Decimal("100.00"))],
        help_text="Percentage off standard selling price (0-100%)",
    )
    flash_price = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Explicit price override during flash event (takes precedence over discount percentage)",
    )
    inventory_cap = models.PositiveIntegerField(
        default=100,
        help_text="Total promotional units reserved for this flash sale",
    )
    units_sold = models.PositiveIntegerField(
        default=0,
        help_text="Quantity claimed by shoppers during flash event",
    )
    max_units_per_order = models.PositiveIntegerField(
        default=2,
        help_text="Anti-scalping purchase cap per checkout order",
    )
    start_time = models.DateTimeField(
        default=timezone.now,
        help_text="Event commencement timestamp",
    )
    end_time = models.DateTimeField(
        help_text="Event expiration timestamp",
    )
    badge_label = models.CharField(
        max_length=50,
        default="FLASH DEAL",
        help_text="Promotional callout badge text shown on product cards",
    )
    banner_bg_color = models.CharField(
        max_length=20,
        default="#ef4444",
        help_text="Hex color code for storefront countdown header (e.g. #ef4444)",
    )
    terms_and_conditions = models.TextField(
        blank=True,
        help_text="Special checkout conditions or return policy caveats",
    )

    class Meta:
        ordering = ["-start_time", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_fls_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status", "start_time", "end_time"], name="ecom_fls_tnt_stat_time_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_live(self):
        if self.status != "active":
            return False
        now = timezone.now()
        if now < self.start_time or now > self.end_time:
            return False
        if self.units_sold >= self.inventory_cap:
            return False
        return True

    @property
    def remaining_units(self):
        return max(0, self.inventory_cap - self.units_sold)

    @property
    def sold_percentage(self):
        if self.inventory_cap <= 0:
            return 0
        return min(100, int((self.units_sold / self.inventory_cap) * 100))

    def calculate_effective_price(self, original_price):
        """
        Calculates promotional price during flash sale.
        """
        base = Decimal(original_price or 0)
        if self.flash_price is not None:
            return Decimal(self.flash_price)
        pct = Decimal(self.discount_percentage or 0)
        discount = (base * pct) / Decimal("100")
        return max(Decimal("0.0000"), base - discount)
