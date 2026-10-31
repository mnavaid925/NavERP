from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered


class SubscriptionPlan(TenantNumbered):
    NUMBER_PREFIX = "ESPL"

    PLAN_TYPE_CHOICES = [
        ("subscribe_save", "Subscribe & Save (Consumable)"),
        ("curated_box", "Curated Assortment Box"),
        ("membership_club", "Membership Club"),
    ]

    FREQUENCY_CHOICES = [
        ("weekly", "Weekly"),
        ("biweekly", "Bi-Weekly (Every 2 Weeks)"),
        ("monthly", "Monthly"),
        ("bimonthly", "Bi-Monthly (Every 2 Months)"),
        ("quarterly", "Quarterly (Every 3 Months)"),
        ("annual", "Annual"),
    ]

    DISCOUNT_TYPE_CHOICES = [
        ("percentage", "Percentage Discount"),
        ("fixed_amount", "Fixed Price Discount"),
        ("none", "No Recurring Discount"),
    ]

    name = models.CharField(
        max_length=150,
        help_text="Plan administrative title e.g. 'Coffee of the Month Club', 'Weekly Protein Refill'",
    )
    code = models.SlugField(
        max_length=60,
        help_text="Unique slug code identifier for checkout or API usage",
    )
    plan_type = models.CharField(
        max_length=30,
        choices=PLAN_TYPE_CHOICES,
        default="subscribe_save",
        help_text="Recurring subscription archetype",
    )
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default="monthly",
        help_text="Recurring billing and delivery cadence",
    )
    interval_count = models.PositiveIntegerField(
        default=1,
        help_text="Cadence multiplier (e.g. interval 2 with frequency weekly = every 2 weeks)",
    )
    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPE_CHOICES,
        default="percentage",
        help_text="Subscriber incentive discount model",
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Discount percentage (e.g. 15.00 for 15%) or fixed discount amount",
    )
    trial_period_days = models.PositiveIntegerField(
        default=0,
        help_text="Free or discounted trial duration in days before full recurring charge",
    )
    min_commitment_cycles = models.PositiveIntegerField(
        default=1,
        help_text="Minimum billing cycles required before subscriber cancellation is permitted",
    )
    allow_pause = models.BooleanField(
        default=True,
        help_text="Allow customer to temporarily pause subscription delivery",
    )
    allow_skip = models.BooleanField(
        default=True,
        help_text="Allow customer to skip an upcoming delivery cycle without cancelling",
    )
    allow_swap = models.BooleanField(
        default=True,
        help_text="Allow customer to swap SKUs or curated selections between cycles",
    )
    max_pause_days = models.PositiveIntegerField(
        default=90,
        help_text="Maximum allowed consecutive pause duration in days",
    )
    target_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription_plans",
        help_text="Optional default product associated with this subscription plan",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Active plans are available for customer enrollment",
    )
    description = models.TextField(
        blank=True,
        help_text="Customer-facing or internal operational description of plan terms",
    )

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_espl_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="ecommerce_espl_code_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "is_active", "plan_type"],
                name="idx_espl_ten_act_type",
            ),
        ]

    def clean(self):
        super().clean()
        if self.code:
            self.code = slugify(self.code)
        elif self.name and not self.code:
            self.code = slugify(self.name)

        if self.discount_value < Decimal("0.00"):
            raise ValidationError({"discount_value": "Discount value cannot be negative."})

        if self.discount_type == "percentage" and self.discount_value > Decimal("100.00"):
            raise ValidationError({"discount_value": "Percentage discount cannot exceed 100%."})

        if self.interval_count < 1:
            raise ValidationError({"interval_count": "Interval count must be at least 1."})

        # Tenant cross-reference validation
        if self.target_product_id and self.target_product and self.target_product.tenant_id != self.tenant_id:
            raise ValidationError({"target_product": "Target product belongs to another workspace."})

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()}) [{self.number}]"
