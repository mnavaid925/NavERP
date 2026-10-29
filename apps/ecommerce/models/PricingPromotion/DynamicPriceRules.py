from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class DynamicPriceRule(TenantNumbered):
    """
    Dynamic pricing rule engine for eCommerce catalog.
    Evaluates volume breaks, customer segments, loyalty tiers, time windows, and geo-pricing.
    """

    NUMBER_PREFIX = "EDPR"

    RULE_TYPE_CHOICES = [
        ("percentage_discount", "Percentage Discount"),
        ("fixed_discount", "Fixed Discount Amount"),
        ("fixed_price_override", "Fixed Price Override"),
    ]

    SCOPE_CHOICES = [
        ("storewide", "Storewide (All Products)"),
        ("category", "Store Category"),
        ("product", "Specific Product"),
        ("variant", "Specific SKU Variant"),
    ]

    CUSTOMER_SEGMENT_CHOICES = [
        ("all", "All Customers"),
        ("retail", "Retail / Standard"),
        ("wholesale", "Wholesale / B2B"),
        ("vip", "VIP / Key Accounts"),
    ]

    LOYALTY_TIER_CHOICES = [
        ("none", "No Loyalty Requirement"),
        ("bronze", "Bronze Tier"),
        ("silver", "Silver Tier"),
        ("gold", "Gold Tier"),
        ("platinum", "Platinum Tier"),
    ]

    name = models.CharField(max_length=255, help_text="Descriptive title of the pricing rule")
    rule_type = models.CharField(
        max_length=30,
        choices=RULE_TYPE_CHOICES,
        default="percentage_discount",
        help_text="Calculation mode applied when rule matches",
    )
    adjustment_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Discount percentage (e.g. 15.0000 for 15%) or fixed currency amount",
    )
    scope = models.CharField(
        max_length=20,
        choices=SCOPE_CHOICES,
        default="storewide",
        help_text="Catalog application scope",
    )
    category = models.ForeignKey(
        "ecommerce.StoreCategory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dynamic_price_rules",
        help_text="Target category when scope is 'category'",
    )
    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dynamic_price_rules",
        help_text="Target product when scope is 'product'",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dynamic_price_rules",
        help_text="Target SKU variant when scope is 'variant'",
    )
    customer_segment = models.CharField(
        max_length=20,
        choices=CUSTOMER_SEGMENT_CHOICES,
        default="all",
        help_text="Customer group qualification",
    )
    loyalty_tier = models.CharField(
        max_length=20,
        choices=LOYALTY_TIER_CHOICES,
        default="none",
        help_text="Minimum loyalty reward tier unlock",
    )
    min_quantity = models.PositiveIntegerField(
        default=1,
        help_text="Minimum purchase quantity threshold (volume break tier)",
    )
    country_code = models.CharField(
        max_length=2,
        blank=True,
        help_text="ISO 3166-1 alpha-2 country code for geo-pricing (leave blank for global)",
    )
    currency_code = models.CharField(
        max_length=3,
        default="USD",
        help_text="Currency ISO code",
    )
    valid_from = models.DateTimeField(
        default=timezone.now,
        help_text="Rule activation date and time",
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Rule expiration date and time (leave blank for indefinite)",
    )
    priority = models.PositiveIntegerField(
        default=10,
        help_text="Evaluation priority: higher priority rules take precedence",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Master enable/disable switch",
    )
    description = models.TextField(blank=True, help_text="Internal notes and campaign justification")

    class Meta:
        ordering = ["-priority", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_dpr_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "priority"], name="ecom_dpr_tnt_act_prio_idx"),
            models.Index(fields=["tenant", "scope"], name="ecom_dpr_tnt_scope_idx"),
            models.Index(fields=["tenant", "customer_segment"], name="ecom_dpr_tnt_seg_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    @property
    def is_currently_valid(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        return True

    def calculate_price(self, base_price):
        """
        Calculates adjusted price based on this rule.
        Ensures resulting price is non-negative Decimal.
        """
        base = Decimal(base_price or 0)
        if not self.is_currently_valid:
            return base

        val = Decimal(self.adjustment_value or 0)
        if self.rule_type == "percentage_discount":
            discount = (base * val) / Decimal("100")
            return max(Decimal("0.0000"), base - discount)
        elif self.rule_type == "fixed_discount":
            return max(Decimal("0.0000"), base - val)
        elif self.rule_type == "fixed_price_override":
            return max(Decimal("0.0000"), val)
        return base
