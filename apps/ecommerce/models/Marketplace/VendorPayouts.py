from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.ecommerce.models._base import TenantNumbered


class VendorPayout(TenantNumbered):
    NUMBER_PREFIX = "EVPO"

    PAYOUT_STATUS_CHOICES = [
        ("draft", "Draft Batch"),
        ("pending_approval", "Pending Finance Approval"),
        ("processing", "Processing with Bank / Gateway"),
        ("completed", "Completed & Disbursed"),
        ("failed", "Disbursement Failed"),
        ("cancelled", "Cancelled"),
    ]

    PAYOUT_METHOD_CHOICES = [
        ("stripe_connect", "Stripe Connect Transfer"),
        ("bank_transfer", "Bank Wire / ACH"),
        ("paypal", "PayPal Payout"),
        ("manual_check", "Manual Check / Voucher"),
    ]

    vendor = models.ForeignKey(
        "ecommerce.MarketplaceVendor",
        on_delete=models.PROTECT,
        related_name="payouts",
        help_text="Marketplace vendor receiving this disbursement settlement",
    )
    period_start = models.DateField(
        help_text="Start date of earning period covered",
    )
    period_end = models.DateField(
        help_text="End date of earning period covered",
    )
    gross_sales_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gross sales volume from fulfilled vendor sub-orders",
    )
    commission_deducted = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total marketplace platform commission retained",
    )
    fees_deducted = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Payment processing, gateway, or listing fees deducted",
    )
    refunds_deducted = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Customer returns and refund clawbacks deducted",
    )
    tax_withholding_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Statutory withholding tax deducted",
    )
    net_payout_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Final disbursed amount transferred to vendor",
    )
    payout_method = models.CharField(
        max_length=25,
        choices=PAYOUT_METHOD_CHOICES,
        default="bank_transfer",
        help_text="Transfer method used for disbursement",
    )
    payout_status = models.CharField(
        max_length=25,
        choices=PAYOUT_STATUS_CHOICES,
        default="draft",
        db_index=True,
        help_text="Settlement lifecycle status",
    )
    reference_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="Gateway transfer ID (e.g. tr_1N7...) or bank confirmation number",
    )
    tax_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Tax year for 1099-K reporting, e.g. 2026",
    )
    is_1099_reported = models.BooleanField(
        default=False,
        help_text="Flag indicating annual 1099 form has been generated and filed",
    )
    notes = models.TextField(
        blank=True,
        help_text="Disbursement notes, audit remarks, or gateway error codes",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_payouts",
        help_text="Finance administrator who approved payout batch",
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when funds transfer was executed",
    )

    class Meta:
        ordering = ["-period_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_evpo_tenant_num_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "vendor", "payout_status"],
                name="idx_evpo_ten_ven_stat",
            ),
            models.Index(
                fields=["tenant", "period_end"],
                name="idx_evpo_ten_period",
            ),
        ]

    def clean(self):
        super().clean()
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValidationError({"period_end": "Period end date cannot precede period start date."})

        # Tenant boundary check
        if self.vendor_id and hasattr(self, "tenant_id") and self.vendor.tenant_id != self.tenant_id:
            raise ValidationError({"vendor": "Vendor belongs to another workspace."})

    def calculate_net(self):
        net = (
            (self.gross_sales_amount or Decimal("0.00"))
            - (self.commission_deducted or Decimal("0.00"))
            - (self.fees_deducted or Decimal("0.00"))
            - (self.refunds_deducted or Decimal("0.00"))
            - (self.tax_withholding_amount or Decimal("0.00"))
        )
        self.net_payout_amount = Decimal(round(max(Decimal("0.00"), net), 2))

    def save(self, *args, **kwargs):
        self.calculate_net()
        if not self.tax_year and self.period_end:
            self.tax_year = self.period_end.year
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} ({self.vendor.store_name} • ${self.net_payout_amount})"
