from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered


class AffiliatePartner(TenantNumbered):
    NUMBER_PREFIX = "EAFF"

    PARTNER_TYPE_CHOICES = [
        ("affiliate", "Affiliate Marketer"),
        ("influencer", "Social Influencer"),
        ("brand_ambassador", "Brand Ambassador"),
        ("customer_advocate", "Customer Referral Advocate"),
    ]

    COMMISSION_TYPE_CHOICES = [
        ("percentage_net_sales", "Percentage of Net Sales"),
        ("flat_per_order", "Flat Dollar per Order"),
        ("tiered", "Tiered Sales Volume"),
    ]

    STATUS_CHOICES = [
        ("pending_approval", "Pending Approval"),
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("inactive", "Inactive"),
    ]

    name = models.CharField(
        max_length=120,
        help_text="Partner display name or company name",
    )
    party = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="affiliate_profiles",
        help_text="Unified Core Spine Party entity",
    )
    customer_profile = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="affiliate_partnerships",
        help_text="Optional shopper account profile for customer advocates",
    )
    partner_type = models.CharField(
        max_length=25,
        choices=PARTNER_TYPE_CHOICES,
        default="affiliate",
        help_text="Partner classification",
    )
    referral_code = models.CharField(
        max_length=50,
        help_text="Unique discount / promo tracking code, e.g. 'SUMMER25', 'ALICE10'",
    )
    referral_link_slug = models.CharField(
        max_length=60,
        help_text="Unique tracking URL slug, e.g. 'alice-smith'",
    )
    commission_type = models.CharField(
        max_length=25,
        choices=COMMISSION_TYPE_CHOICES,
        default="percentage_net_sales",
        help_text="Attribution commission remuneration model",
    )
    commission_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Commission rate percentage (e.g. 10.00%) or flat dollar amount ($10.00)",
    )
    cookie_duration_days = models.PositiveIntegerField(
        default=30,
        help_text="Referral attribution cookie window in days",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending_approval",
        help_text="Partnership approval and operational status",
    )
    payout_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("50.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Minimum earnings required before payout batch generation",
    )
    payment_email = models.EmailField(
        blank=True,
        help_text="Payout PayPal / remittance email address",
    )
    total_orders_referred = models.PositiveIntegerField(
        default=0,
        help_text="Cumulative number of completed orders referred",
    )
    total_revenue_generated = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total store revenue generated through this partner",
    )
    total_commission_earned = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total commissions earned historically",
    )
    total_commission_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total commissions disbursed",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_eaff_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "referral_code"],
                name="ecommerce_eaff_code_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "referral_link_slug"],
                name="ecommerce_eaff_slug_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status", "partner_type"],
                name="idx_eaff_ten_stat_type",
            ),
        ]

    def __str__(self):
        return f"{self.name} [{self.referral_code}]"

    def clean(self):
        super().clean()
        if not self.referral_link_slug and self.name:
            self.referral_link_slug = slugify(self.name)[:60]
        if self.referral_code:
            self.referral_code = self.referral_code.upper().strip()

    @property
    def unpaid_commission(self):
        return max(self.total_commission_earned - self.total_commission_paid, Decimal("0.00"))

    @property
    def is_eligible_for_payout(self):
        return self.unpaid_commission >= self.payout_threshold
