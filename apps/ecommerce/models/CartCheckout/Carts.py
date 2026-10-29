import secrets
from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class Cart(TenantNumbered):
    """Shopping Cart supporting both persistent authenticated and guest sessions."""

    STATUS_ACTIVE = "active"
    STATUS_LOCKED = "locked"
    STATUS_ABANDONED = "abandoned"
    STATUS_CONVERTED = "converted"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_LOCKED, "Locked (In Checkout)"),
        (STATUS_ABANDONED, "Abandoned"),
        (STATUS_CONVERTED, "Converted to Order"),
        (STATUS_EXPIRED, "Expired"),
    ]

    NUMBER_PREFIX = "ECRT"

    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecommerce_carts",
        help_text="Registered customer account, if authenticated.",
    )
    session_key = models.CharField(
        max_length=64,
        blank=True,
        db_index=True,
        help_text="Browser/client session key for guest visitors.",
    )
    email = models.EmailField(
        blank=True,
        help_text="Contact email captured for guest checkout and abandonment recovery.",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True,
    )
    currency = models.CharField(max_length=3, default="USD")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    shipping_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    coupon_code = models.CharField(max_length=50, blank=True)
    last_activity_at = models.DateTimeField(default=timezone.now)
    abandoned_at = models.DateTimeField(null=True, blank=True)
    recovery_token = models.CharField(max_length=64, blank=True, null=True, unique=True)
    recovery_sent_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-last_activity_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_cart_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="ecom_cart_tnt_stat_idx"),
            models.Index(fields=["tenant", "session_key"], name="ecom_cart_tnt_sess_idx"),
            models.Index(fields=["tenant", "customer"], name="ecom_cart_tnt_cust_idx"),
        ]

    def __str__(self):
        owner = self.email or (str(self.customer) if self.customer else f"Guest ({self.session_key[:8]}...)")
        return f"{self.number} — {owner} ({self.get_status_display()})"

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())

    def recalculate_totals(self, commit=True):
        """Compute line item totals and overall grand total."""
        items = list(self.items.all())
        raw_subtotal = Decimal("0.00")
        for item in items:
            raw_subtotal += (item.unit_price * item.quantity).quantize(Decimal("0.01"))
        self.subtotal = raw_subtotal

        # Grand total computation with discounts, taxes, and shipping
        calculated = self.subtotal - self.discount_total + self.tax_total + self.shipping_total
        self.grand_total = max(Decimal("0.00"), calculated.quantize(Decimal("0.01")))
        if commit:
            self.save(update_fields=["subtotal", "grand_total", "updated_at"])

    def generate_recovery_token(self):
        """Generate a cryptographically safe token for 1-click cart recovery."""
        if not self.recovery_token:
            self.recovery_token = secrets.token_urlsafe(32)
        return self.recovery_token

    def mark_abandoned(self):
        """Flag the cart as abandoned and record timestamp."""
        if self.status == self.STATUS_ACTIVE:
            self.status = self.STATUS_ABANDONED
            self.abandoned_at = timezone.now()
            self.generate_recovery_token()
            self.save(update_fields=["status", "abandoned_at", "recovery_token", "updated_at"])


class CartItem(models.Model):
    """Line item in a shopping cart."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    custom_attributes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["cart", "product"], name="ecom_citem_cart_prd_idx"),
        ]

    def __str__(self):
        product_title = str(self.variant) if self.variant else str(self.product)
        return f"{self.quantity}x {product_title} @ {self.unit_price}"

    def save(self, *args, **kwargs):
        if self.variant and not self.unit_price:
            self.unit_price = self.variant.price
        self.total_price = (self.unit_price * self.quantity).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)
