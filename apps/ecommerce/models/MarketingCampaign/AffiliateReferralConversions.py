from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class AffiliateReferralConversion(TenantNumbered):
    NUMBER_PREFIX = "EARC"

    ATTRIBUTION_TYPE_CHOICES = [
        ("referral_link", "Referral Tracking Link"),
        ("coupon_code", "Affiliate Coupon Code"),
        ("manual_credit", "Manual Administrative Credit"),
    ]

    STATUS_CHOICES = [
        ("pending_review", "Pending Review"),
        ("approved", "Approved for Payout"),
        ("paid", "Paid / Remitted"),
        ("voided_refund", "Voided / Refund Clawback"),
    ]

    affiliate = models.ForeignKey(
        "ecommerce.AffiliatePartner",
        on_delete=models.CASCADE,
        related_name="conversions",
        help_text="Credited affiliate partner",
    )
    order = models.ForeignKey(
        "ecommerce.EcommerceOrder",
        on_delete=models.CASCADE,
        related_name="affiliate_conversions",
        help_text="Referred store order from Order Management System",
    )
    referred_customer = models.ForeignKey(
        "ecommerce.CustomerAccountProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="affiliate_conversions",
        help_text="Referred shopper profile",
    )
    attribution_type = models.CharField(
        max_length=25,
        choices=ATTRIBUTION_TYPE_CHOICES,
        default="referral_link",
        help_text="Attribution mechanism",
    )
    order_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Eligible net merchandise order amount",
    )
    commission_rate_applied = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Historical commission rate locked at conversion time",
    )
    commission_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Calculated partner commission amount",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending_review",
        help_text="Remittance approval status",
    )
    payout_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="Remittance reference or accounting payment batch voucher ID",
    )
    paid_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of commission disbursement",
    )
    notes = models.TextField(
        blank=True,
        help_text="Audit notes, reason for void/rejection, or clawback details",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_earc_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "affiliate", "order"],
                name="ecommerce_earc_aff_order_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status", "created_at"],
                name="idx_earc_ten_stat_created",
            ),
        ]

    def __str__(self):
        return f"Conversion {self.number or 'draft'} ({self.affiliate.name} - Order {self.order.number})"

    def clean(self):
        super().clean()
        if self.affiliate and not self.commission_rate_applied:
            self.commission_rate_applied = self.affiliate.commission_rate
        if self.order_amount is not None and self.commission_rate_applied is not None:
            if self.affiliate and self.affiliate.commission_type == "flat_per_order":
                self.commission_amount = self.commission_rate_applied
            else:
                self.commission_amount = round(
                    Decimal(self.order_amount) * (Decimal(self.commission_rate_applied) / Decimal("100.0")),
                    2,
                )
