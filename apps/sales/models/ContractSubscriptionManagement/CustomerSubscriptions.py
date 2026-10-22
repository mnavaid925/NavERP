"""Sales 8.15 — CustomerSubscription model."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

SUBSCRIPTION_STATUS_CHOICES = [
    ("trialing", "Trialing"),
    ("active", "Active"),
    ("paused", "Paused / Suspended"),
    ("past_due", "Past Due / Grace Period"),
    ("cancelled", "Cancelled"),
    ("expired", "Expired"),
]

PRICING_MODEL_CHOICES = [
    ("per_seat", "Per Seat / User License"),
    ("flat_fee", "Flat Recurring Fee"),
    ("usage_metered", "Usage Metered (In Arrears)"),
    ("hybrid", "Hybrid (Base Fee + Overage)"),
]

BILLING_CADENCE_CHOICES = [
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("semi_annual", "Semi-Annual"),
    ("annual", "Annual"),
]


class CustomerSubscription(TenantNumbered):
    NUMBER_PREFIX = "CSB"

    contract = models.ForeignKey(
        "sales.CustomerContract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions",
    )
    account = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="customer_subscriptions",
    )
    subscription_name = models.CharField(max_length=255)
    plan_code = models.CharField(max_length=60)
    status = models.CharField(
        max_length=30,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default="active",
    )
    pricing_model = models.CharField(
        max_length=30,
        choices=PRICING_MODEL_CHOICES,
        default="per_seat",
    )
    billing_cadence = models.CharField(
        max_length=20,
        choices=BILLING_CADENCE_CHOICES,
        default="monthly",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    mrr = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    start_date = models.DateField(default=timezone.localdate)
    current_term_start = models.DateField(default=timezone.localdate)
    current_term_end = models.DateField()
    trial_ends_at = models.DateField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    resumed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(blank=True)
    auto_renew = models.BooleanField(default=True)
    renewal_notice_days = models.PositiveIntegerField(default=30)
    renewal_quote = models.ForeignKey(
        "sales.CPQQuote",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renewal_subscriptions",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_customer_subscriptions",
    )

    class Meta:
        ordering = ["-current_term_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_csb_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_csb_ten_status_idx"),
            models.Index(fields=["tenant", "account"], name="sales_csb_ten_acc_idx"),
            models.Index(fields=["tenant", "current_term_end"], name="sales_csb_ten_end_idx"),
            models.Index(fields=["tenant", "contract"], name="sales_csb_ten_contract_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.subscription_name} ({self.account.name})"

    def calculate_mrr(self):
        amount = Decimal(self.quantity) * self.unit_price
        if self.billing_cadence == "monthly":
            return amount.quantize(Decimal("0.01"))
        elif self.billing_cadence == "quarterly":
            return (amount / Decimal("3.00")).quantize(Decimal("0.01"))
        elif self.billing_cadence == "semi_annual":
            return (amount / Decimal("6.00")).quantize(Decimal("0.01"))
        elif self.billing_cadence == "annual":
            return (amount / Decimal("12.00")).quantize(Decimal("0.01"))
        return amount.quantize(Decimal("0.01"))

    def clean(self):
        super().clean()
        if self.current_term_end and self.current_term_start and self.current_term_end < self.current_term_start:
            raise ValidationError({"current_term_end": "Term end date cannot precede term start date."})

        if self.status == "cancelled" and not self.cancellation_reason.strip():
            raise ValidationError({"cancellation_reason": "Cancellation reason is required when cancelling a subscription."})

        if self.account_id and self.tenant_id and self.account.tenant_id != self.tenant_id:
            raise ValidationError({"account": "Account must belong to this workspace."})

        if self.contract_id and self.tenant_id and self.contract.tenant_id != self.tenant_id:
            raise ValidationError({"contract": "Contract must belong to this workspace."})

        if self.owner_id and self.tenant_id and getattr(self.owner, "tenant_id", None) != self.tenant_id:
            raise ValidationError({"owner": "Owner must belong to this workspace."})

        if self.renewal_quote_id and self.tenant_id and self.renewal_quote.tenant_id != self.tenant_id:
            raise ValidationError({"renewal_quote": "Renewal quote must belong to this workspace."})

        self.mrr = self.calculate_mrr()
