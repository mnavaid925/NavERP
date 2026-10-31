from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class CustomerSubscription(TenantNumbered):
    NUMBER_PREFIX = "ESUB"

    STATUS_CHOICES = [
        ("trialing", "Trialing"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("past_due", "Past Due (In Dunning)"),
        ("pending_cancellation", "Pending Cancellation"),
        ("cancelled", "Cancelled"),
        ("expired", "Expired"),
    ]

    customer_profile = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        on_delete=models.CASCADE,
        related_name="subscriptions",
        help_text="Shopper account owning this recurring subscription",
    )
    plan = models.ForeignKey(
        "ecommerce.SubscriptionPlan",
        on_delete=models.PROTECT,
        related_name="subscriptions",
        help_text="Subscription plan governing cadence and discount terms",
    )
    product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.PROTECT,
        related_name="subscriptions",
        help_text="Canonical catalog product delivered recurringly",
    )
    variant = models.ForeignKey(
        "ecommerce.ProductVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
        help_text="Specific variant / SKU option (flavor, size, shade)",
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="active",
        help_text="Current subscriber lifecycle state",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        help_text="Quantity of item per shipment cycle",
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gross unit price before recurring discount",
    )
    recurring_discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Recurring discount percentage applied per cycle",
    )
    started_at = models.DateTimeField(
        default=timezone.now,
        help_text="Initial subscription creation timestamp",
    )
    next_billing_date = models.DateField(
        help_text="Scheduled date for upcoming automated cycle charge",
    )
    next_delivery_date = models.DateField(
        null=True,
        blank=True,
        help_text="Estimated date of upcoming shipment delivery",
    )
    paused_until = models.DateField(
        null=True,
        blank=True,
        help_text="If paused, date on which subscription automatically resumes",
    )
    completed_cycles_count = models.PositiveIntegerField(
        default=0,
        help_text="Total lifetime billing cycles successfully charged",
    )
    consecutive_successful_cycles = models.PositiveIntegerField(
        default=0,
        help_text="Consecutive successful charges without failure or pause",
    )
    failed_payment_count = models.PositiveIntegerField(
        default=0,
        help_text="Consecutive payment decline count for dunning",
    )
    shipping_address_line = models.CharField(
        max_length=255,
        blank=True,
        help_text="Delivery address snapshot or instruction",
    )
    payment_method_ref = models.CharField(
        max_length=100,
        blank=True,
        help_text="Opaque gateway payment method or card token reference",
    )
    cancellation_reason = models.CharField(
        max_length=255,
        blank=True,
        help_text="Documented reason if cancelled or pending cancellation",
    )
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when subscription was cancelled",
    )

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_esub_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status", "next_billing_date"],
                name="idx_esub_ten_stat_nbill",
            ),
            models.Index(
                fields=["tenant", "customer_profile", "status"],
                name="idx_esub_ten_cust_stat",
            ),
        ]

    @property
    def recurring_total(self):
        gross = self.unit_price * self.quantity
        if self.recurring_discount_pct > Decimal("0.00"):
            discount = (gross * self.recurring_discount_pct) / Decimal("100.00")
            return max(Decimal("0.00"), gross - discount)
        return gross

    def clean(self):
        super().clean()
        if self.unit_price < Decimal("0.00"):
            raise ValidationError({"unit_price": "Unit price cannot be negative."})
        if self.quantity < 1:
            raise ValidationError({"quantity": "Quantity must be at least 1."})
        if self.recurring_discount_pct < Decimal("0.00") or self.recurring_discount_pct > Decimal("100.00"):
            raise ValidationError({"recurring_discount_pct": "Discount percentage must be between 0 and 100."})

        # Tenant cross-reference validation
        if self.customer_profile_id and self.customer_profile and self.customer_profile.tenant_id != self.tenant_id:
            raise ValidationError({"customer_profile": "Customer profile belongs to another workspace."})
        if self.plan_id and self.plan and self.plan.tenant_id != self.tenant_id:
            raise ValidationError({"plan": "Subscription plan belongs to another workspace."})
        if self.product_id and self.product and self.product.tenant_id != self.tenant_id:
            raise ValidationError({"product": "Catalog product belongs to another workspace."})
        if self.variant_id and self.variant and self.variant.tenant_id != self.tenant_id:
            raise ValidationError({"variant": "Product variant belongs to another workspace."})

    def __str__(self):
        return f"{self.customer_profile} - {self.product.name} ({self.number}) [{self.get_status_display()}]"
