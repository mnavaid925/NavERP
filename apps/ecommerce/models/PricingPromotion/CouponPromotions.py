from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class CouponPromotion(TenantNumbered):
    """
    Discount vouchers, promotional coupon codes, and loyalty reward pricing.
    Supports percentage and fixed cuts, spend thresholds, usage limits, and customer eligibility.
    """

    NUMBER_PREFIX = "ECPN"

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage Off Cart"),
        ("fixed_cart", "Fixed Amount Off Cart"),
        ("fixed_item", "Fixed Amount Off Item"),
        ("free_shipping", "Free Shipping Voucher"),
    ]

    LOYALTY_TIER_CHOICES = [
        ("none", "No Loyalty Requirement"),
        ("bronze", "Bronze Tier"),
        ("silver", "Silver Tier"),
        ("gold", "Gold Tier"),
        ("platinum", "Platinum Tier"),
    ]

    code = models.CharField(
        max_length=50,
        help_text="Alphanumeric coupon code entered by customer at checkout (case-insensitive)",
    )
    name = models.CharField(
        max_length=255,
        help_text="Campaign title (e.g. Summer Kickoff 2026, New Member Welcome)",
    )
    discount_type = models.CharField(
        max_length=30,
        choices=DISCOUNT_TYPE_CHOICES,
        default="percentage",
        help_text="Discount deduction calculation method",
    )
    discount_value = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Percentage off (e.g. 15.0000) or fixed currency deduction amount",
    )
    min_spend = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Minimum cart subtotal required to redeem coupon",
    )
    max_discount_amount = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.0000"))],
        help_text="Maximum dollar discount cap (useful for percentage vouchers)",
    )
    usage_limit_total = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Total global redemptions allowed across all shoppers (leave blank for unlimited)",
    )
    usage_limit_per_customer = models.PositiveIntegerField(
        default=1,
        help_text="Maximum times a single customer account may redeem this code",
    )
    used_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of completed orders that redeemed this coupon",
    )
    is_stackable = models.BooleanField(
        default=False,
        help_text="Can be combined with other coupons or dynamic pricing promotions",
    )
    loyalty_tier_required = models.CharField(
        max_length=20,
        choices=LOYALTY_TIER_CHOICES,
        default="none",
        help_text="Minimum loyalty reward tier needed to unlock this coupon",
    )
    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecommerce_coupons",
        help_text="Specific customer account restriction (leave blank for public campaign)",
    )
    valid_from = models.DateTimeField(
        default=timezone.now,
        help_text="Campaign activation date and time",
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Campaign expiration date and time (leave blank for ongoing)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Master activation toggle",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_cpn_tenant_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "code"], name="ecom_cpn_tenant_code_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active", "code"], name="ecom_cpn_tnt_act_code_idx"),
            models.Index(fields=["tenant", "discount_type"], name="ecom_cpn_tnt_type_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} — {self.name}"

    @property
    def is_currently_valid(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_to and now > self.valid_to:
            return False
        if self.usage_limit_total is not None and self.used_count >= self.usage_limit_total:
            return False
        return True

    @property
    def remaining_redemptions(self):
        if self.usage_limit_total is None:
            return None  # unlimited
        return max(0, self.usage_limit_total - self.used_count)

    def calculate_discount(self, cart_subtotal):
        """
        Calculates promotional deduction on given subtotal.
        Returns Decimal discount amount.
        """
        subtotal = Decimal(cart_subtotal or 0)
        if not self.is_currently_valid:
            return Decimal("0.0000")
        if subtotal < self.min_spend:
            return Decimal("0.0000")

        val = Decimal(self.discount_value or 0)
        discount = Decimal("0.0000")

        if self.discount_type == "percentage":
            discount = (subtotal * val) / Decimal("100")
            if self.max_discount_amount is not None:
                discount = min(discount, Decimal(self.max_discount_amount))
        elif self.discount_type in ("fixed_cart", "fixed_item"):
            discount = min(subtotal, val)
        elif self.discount_type == "free_shipping":
            discount = Decimal("0.0000")  # Handled at shipping calculation stage

        return max(Decimal("0.0000"), discount)
