from datetime import timedelta
from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class CheckoutSession(TenantNumbered):
    """Checkout session orchestrating the customer conversion funnel."""

    FLOW_ONE_PAGE = "one_page"
    FLOW_MULTI_STEP = "multi_step"

    FLOW_TYPE_CHOICES = [
        (FLOW_ONE_PAGE, "One-Page Checkout"),
        (FLOW_MULTI_STEP, "Multi-Step Checkout"),
    ]

    STEP_CONTACT = "contact"
    STEP_SHIPPING_ADDR = "shipping_address"
    STEP_SHIPPING_METHOD = "shipping_method"
    STEP_PAYMENT = "payment"
    STEP_REVIEW = "review"
    STEP_COMPLETED = "completed"

    STEP_CHOICES = [
        (STEP_CONTACT, "Contact Details"),
        (STEP_SHIPPING_ADDR, "Shipping Address"),
        (STEP_SHIPPING_METHOD, "Shipping Method"),
        (STEP_PAYMENT, "Payment"),
        (STEP_REVIEW, "Review & Place Order"),
        (STEP_COMPLETED, "Completed"),
    ]

    STATUS_IN_PROGRESS = "in_progress"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_EXPIRED = "expired"
    STATUS_ABANDONED = "abandoned"

    STATUS_CHOICES = [
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_PROCESSING, "Processing Payment"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_ABANDONED, "Abandoned"),
    ]

    PAYMENT_PENDING = "pending"
    PAYMENT_AUTHORIZED = "authorized"
    PAYMENT_PAID = "paid"
    PAYMENT_FAILED = "failed"

    PAYMENT_STATUS_CHOICES = [
        (PAYMENT_PENDING, "Pending"),
        (PAYMENT_AUTHORIZED, "Authorized"),
        (PAYMENT_PAID, "Paid"),
        (PAYMENT_FAILED, "Failed"),
    ]

    NUMBER_PREFIX = "ECKS"

    cart = models.ForeignKey(
        "ecommerce.Cart",
        on_delete=models.CASCADE,
        related_name="checkout_sessions",
    )
    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecommerce_checkout_sessions",
    )
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    flow_type = models.CharField(max_length=20, choices=FLOW_TYPE_CHOICES, default=FLOW_ONE_PAGE)
    current_step = models.CharField(max_length=20, choices=STEP_CHOICES, default=STEP_CONTACT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_IN_PROGRESS, db_index=True)

    # Shipping Address Information
    shipping_name = models.CharField(max_length=150, blank=True)
    shipping_address_line1 = models.CharField(max_length=255, blank=True)
    shipping_address_line2 = models.CharField(max_length=255, blank=True)
    shipping_city = models.CharField(max_length=100, blank=True)
    shipping_state = models.CharField(max_length=100, blank=True)
    shipping_postal_code = models.CharField(max_length=30, blank=True)
    shipping_country = models.CharField(max_length=2, default="US")

    # Billing Address Information
    billing_same_as_shipping = models.BooleanField(default=True)
    billing_name = models.CharField(max_length=150, blank=True)
    billing_address_line1 = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_postal_code = models.CharField(max_length=30, blank=True)
    billing_country = models.CharField(max_length=2, default="US")

    # Method Selections
    shipping_method = models.ForeignKey(
        "ecommerce.ShippingMethodConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkout_sessions",
    )
    payment_method = models.ForeignKey(
        "ecommerce.PaymentMethodConfig",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkout_sessions",
    )

    # Tax & Compliance
    tax_code = models.ForeignKey(
        "accounting.TaxCode",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ecommerce_checkouts",
    )
    tax_jurisdiction = models.CharField(max_length=100, blank=True)
    tax_rate = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal("0.0000"))
    is_tax_exempt = models.BooleanField(default=False)
    tax_exemption_number = models.CharField(max_length=50, blank=True)
    tax_breakdown = models.JSONField(default=dict, blank=True)

    # Financial Totals Snapshot
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    shipping_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))

    # Payment Status & Lifecycle
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    payment_transaction_id = models.CharField(max_length=100, blank=True)
    order_reference = models.CharField(max_length=50, blank=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="ecom_cks_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="ecom_cks_tnt_stat_idx"),
            models.Index(fields=["tenant", "cart"], name="ecom_cks_tnt_cart_idx"),
            models.Index(fields=["tenant", "customer"], name="ecom_cks_tnt_cust_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.email} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        if self.billing_same_as_shipping and not self.billing_name:
            self.billing_name = self.shipping_name
            self.billing_address_line1 = self.shipping_address_line1
            self.billing_city = self.shipping_city
            self.billing_state = self.shipping_state
            self.billing_postal_code = self.shipping_postal_code
            self.billing_country = self.shipping_country
        super().save(*args, **kwargs)

    def advance_step(self):
        """Move forward to next step in the conversion funnel."""
        step_progression = [
            self.STEP_CONTACT,
            self.STEP_SHIPPING_ADDR,
            self.STEP_SHIPPING_METHOD,
            self.STEP_PAYMENT,
            self.STEP_REVIEW,
            self.STEP_COMPLETED,
        ]
        try:
            current_idx = step_progression.index(self.current_step)
            if current_idx < len(step_progression) - 1:
                self.current_step = step_progression[current_idx + 1]
                if self.current_step == self.STEP_COMPLETED:
                    self.status = self.STATUS_COMPLETED
                    self.completed_at = timezone.now()
                self.save(update_fields=["current_step", "status", "completed_at", "updated_at"])
        except ValueError:
            pass
