from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered, TenantOwned


class EcommerceOrder(TenantNumbered):
    """
    Central enterprise sales order placed via eCommerce storefront and digital channels.
    Encapsulates lifecycle state machine, payment state, fraud risk analysis,
    inventory reservation, address snapshots, and financial summary totals.
    """

    NUMBER_PREFIX = "EORD"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_validation", "Pending Validation"),
        ("validated", "Validated & Approved"),
        ("processing", "Processing / In Fulfillment"),
        ("partially_fulfilled", "Partially Fulfilled"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
        ("closed", "Closed"),
    ]

    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending Payment"),
        ("authorized", "Payment Authorized"),
        ("captured", "Payment Captured"),
        ("partially_refunded", "Partially Refunded"),
        ("refunded", "Fully Refunded"),
        ("failed", "Payment Failed"),
    ]

    FULFILLMENT_STATUS_CHOICES = [
        ("unfulfilled", "Unfulfilled"),
        ("partially_fulfilled", "Partially Fulfilled"),
        ("fulfilled", "Fulfilled"),
        ("returned", "Returned"),
    ]

    FRAUD_RISK_CHOICES = [
        ("low", "Low Risk"),
        ("medium", "Medium Risk"),
        ("high", "High Risk"),
        ("flagged", "Fraud Flagged"),
    ]

    AVS_STATUS_CHOICES = [
        ("unverified", "Unverified"),
        ("passed", "Address Verified (Passed)"),
        ("failed", "Verification Failed"),
        ("corrected", "Address Corrected"),
    ]

    RESERVATION_STATUS_CHOICES = [
        ("none", "No Reservation"),
        ("reserved", "Stock Reserved"),
        ("allocated", "Stock Allocated to Node"),
        ("released", "Reservation Released"),
    ]

    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="ecommerce_orders",
        help_text="Customer party registered in core identity spine",
    )
    guest_email = models.EmailField(
        blank=True,
        help_text="Email for notifications and guest checkout accounts",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="ecommerce_orders",
        help_text="ISO-4217 transaction currency",
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="pending_validation",
        help_text="Primary order processing state",
    )
    payment_status = models.CharField(
        max_length=25,
        choices=PAYMENT_STATUS_CHOICES,
        default="pending",
        help_text="Settlement and gateway transaction state",
    )
    fulfillment_status = models.CharField(
        max_length=25,
        choices=FULFILLMENT_STATUS_CHOICES,
        default="unfulfilled",
        help_text="Physical shipping and dispatch state",
    )
    fraud_risk_level = models.CharField(
        max_length=15,
        choices=FRAUD_RISK_CHOICES,
        default="low",
        help_text="Automated risk score evaluation category",
    )
    fraud_score = models.PositiveSmallIntegerField(
        default=10,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Calculated fraud probability score (0 = lowest risk, 100 = critical risk)",
    )
    address_verification_status = models.CharField(
        max_length=20,
        choices=AVS_STATUS_CHOICES,
        default="unverified",
        help_text="Address Verification System (AVS) match status",
    )
    inventory_reservation_status = models.CharField(
        max_length=20,
        choices=RESERVATION_STATUS_CHOICES,
        default="none",
        help_text="Warehouse inventory hold status for ordered items",
    )

    # Financial Summaries
    subtotal_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Sum of order line totals before tax, shipping, and order-level discounts",
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total promotional deduction applied to order",
    )
    shipping_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Freight and courier delivery charges",
    )
    tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculated sales tax / VAT / GST",
    )
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Net grand total payable by customer",
    )

    applied_coupon = models.ForeignKey(
        "ecommerce.CouponPromotion",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
        help_text="Voucher code applied to this order",
    )

    # Shipping Address Snapshot
    shipping_address = models.ForeignKey(
        "core.Address",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shipping_orders",
        help_text="Address record linked from core Party address book",
    )
    shipping_name = models.CharField(max_length=150, help_text="Recipient name")
    shipping_address_line1 = models.CharField(max_length=255, help_text="Street address")
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=30)
    shipping_country = models.CharField(max_length=100)

    # Billing Address Snapshot
    billing_address = models.ForeignKey(
        "core.Address",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="billing_orders",
        help_text="Billing address record linked from core Party address book",
    )
    billing_name = models.CharField(max_length=150, blank=True)
    billing_address_line1 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=30, blank=True)
    billing_country = models.CharField(max_length=100, blank=True)

    # Post-Purchase Modifications & Audit
    cancellation_reason = models.TextField(blank=True, help_text="Reason recorded if order was cancelled")
    cancelled_at = models.DateTimeField(null=True, blank=True)
    customer_notes = models.TextField(blank=True, help_text="Instructions entered by buyer at checkout")
    internal_notes = models.TextField(blank=True, help_text="Staff-only operational remarks")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_ord_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="ecom_ord_tnt_status_idx"),
            models.Index(fields=["tenant", "customer"], name="ecom_ord_tnt_customer_idx"),
            models.Index(fields=["tenant", "created_at"], name="ecom_ord_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} ({self.customer.name})"

    def recalculate_totals(self):
        """Sum line totals and compute grand total."""
        lines_sum = sum((line.line_total for line in self.lines.all()), Decimal("0.00"))
        self.subtotal_amount = lines_sum
        self.total_amount = max(
            Decimal("0.00"),
            (self.subtotal_amount - self.discount_amount + self.shipping_amount + self.tax_amount),
        )
        self.save(update_fields=["subtotal_amount", "total_amount"])

    def can_cancel(self):
        """Order can be cancelled if not already fulfilled or delivered."""
        return self.status not in ("fulfilled", "cancelled", "closed")

    def cancel_order(self, reason="Customer requested cancellation"):
        if not self.can_cancel():
            return False
        self.status = "cancelled"
        self.cancellation_reason = reason
        self.cancelled_at = timezone.now()
        self.inventory_reservation_status = "released"
        self.save(update_fields=["status", "cancellation_reason", "cancelled_at", "inventory_reservation_status"])
        for line in self.lines.all():
            if line.status != "fulfilled":
                line.status = "cancelled"
                line.save(update_fields=["status"])
        return True


class EcommerceOrderLine(TenantOwned):
    """
    Individual item ordered within an eCommerceOrder.
    Snapshots product title, SKU, unit pricing, discounts, and fulfillment progress.
    """

    LINE_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("reserved", "Stock Reserved"),
        ("routing", "Routing to Fulfillment"),
        ("fulfilled", "Fulfilled"),
        ("cancelled", "Cancelled"),
        ("returned", "Returned"),
    ]

    order = models.ForeignKey(
        EcommerceOrder,
        on_delete=models.CASCADE,
        related_name="lines",
        help_text="Parent eCommerce order",
    )
    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.PROTECT,
        related_name="order_lines",
        help_text="Catalog product reference",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="order_lines",
        help_text="Specific variant/SKU option",
    )
    sku = models.CharField(max_length=80, help_text="SKU snapshot at moment of purchase")
    product_name = models.CharField(max_length=200, help_text="Product title snapshot")
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    fulfilled_quantity = models.PositiveIntegerField(default=0)
    returned_quantity = models.PositiveIntegerField(default=0)

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    unit_discount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    line_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    status = models.CharField(
        max_length=20,
        choices=LINE_STATUS_CHOICES,
        default="pending",
    )

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["tenant", "order"], name="ecom_oln_tnt_order_idx"),
        ]

    def __str__(self):
        return f"{self.product_name} x {self.quantity} ({self.order.number})"

    def save(self, *args, **kwargs):
        # Calculate line total: (unit_price - unit_discount) * quantity
        effective_price = max(Decimal("0.00"), self.unit_price - self.unit_discount)
        self.line_total = effective_price * self.quantity
        super().save(*args, **kwargs)
