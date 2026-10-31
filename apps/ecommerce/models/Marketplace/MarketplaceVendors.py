from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg, Count
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered


class MarketplaceVendor(TenantNumbered):
    NUMBER_PREFIX = "EMKV"

    STATUS_CHOICES = [
        ("draft", "Draft Application"),
        ("submitted", "Application Submitted"),
        ("under_review", "Compliance Review"),
        ("approved", "Approved"),
        ("active", "Active Seller"),
        ("suspended", "Suspended (Policy/SLA Breach)"),
        ("terminated", "Terminated"),
    ]

    KYC_STATUS_CHOICES = [
        ("unsubmitted", "Unsubmitted"),
        ("pending", "Under Verification"),
        ("verified", "Identity Verified"),
        ("rejected", "Verification Rejected"),
    ]

    COMMISSION_TYPE_CHOICES = [
        ("percentage", "Percentage Only"),
        ("fixed", "Flat Fee Only"),
        ("combined", "Percentage + Flat Fee"),
    ]

    PAYOUT_METHOD_CHOICES = [
        ("stripe_connect", "Stripe Connect"),
        ("bank_transfer", "Direct Bank Transfer / ACH"),
        ("paypal", "PayPal Payouts"),
        ("manual_check", "Manual Check / Wire"),
    ]

    TAX_FORM_CHOICES = [
        ("not_required", "Not Required"),
        ("w9_pending", "W-9 Pending"),
        ("w9_received", "W-9 Received"),
        ("w8ben_received", "W-8BEN Received"),
        ("1099_eligible", "1099-K Eligible"),
    ]

    party = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="marketplace_vendors",
        help_text="Unified legal party (person or organization)",
    )
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_marketplace_vendors",
        help_text="Primary login user managing this vendor",
    )
    store_name = models.CharField(
        max_length=150,
        help_text="Public vendor store name",
    )
    slug = models.SlugField(
        max_length=160,
        help_text="URL slug for public storefront, e.g. acme-crafts",
    )
    headline = models.CharField(
        max_length=255,
        blank=True,
        help_text="Short tagline or slogan",
    )
    description = models.TextField(
        blank=True,
        help_text="Storefront about text and company profile",
    )
    logo_url = models.URLField(
        blank=True,
        help_text="Store logo graphic URL",
    )
    banner_url = models.URLField(
        blank=True,
        help_text="Storefront hero banner image URL",
    )
    support_email = models.EmailField(
        blank=True,
        help_text="Customer support email address",
    )
    support_phone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Customer support phone number",
    )
    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
        help_text="Current seller lifecycle status",
    )
    kyc_status = models.CharField(
        max_length=25,
        choices=KYC_STATUS_CHOICES,
        default="unsubmitted",
        db_index=True,
        help_text="Identity & legal compliance status",
    )
    kyc_document_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Document submitted (e.g. Business License, Certificate of Formation, Passport)",
    )
    kyc_notes = models.TextField(
        blank=True,
        help_text="Compliance officer notes regarding KYC verification",
    )
    kyc_verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of KYC identity verification approval",
    )
    commission_type = models.CharField(
        max_length=20,
        choices=COMMISSION_TYPE_CHOICES,
        default="percentage",
        help_text="Commission fee structure applied to this vendor",
    )
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
        help_text="Percentage fee deducted from gross sales (e.g. 15.00%)",
    )
    fixed_fee_per_order = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Flat fee deducted per sub-order (e.g. $1.50)",
    )
    payout_method = models.CharField(
        max_length=25,
        choices=PAYOUT_METHOD_CHOICES,
        default="bank_transfer",
        help_text="Disbursement gateway or channel",
    )
    payout_account_identifier = models.CharField(
        max_length=120,
        blank=True,
        help_text="Connected account ID, IBAN, or recipient address",
    )
    min_payout_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("50.00"),
        help_text="Minimum accumulated balance required for payout release",
    )
    tax_id = models.CharField(
        max_length=64,
        blank=True,
        help_text="EIN, SSN, or VAT tax registration number",
    )
    tax_form_status = models.CharField(
        max_length=25,
        choices=TAX_FORM_CHOICES,
        default="not_required",
        help_text="W-9 / W-8BEN form status for 1099 compliance",
    )
    shipping_lead_time_days = models.PositiveIntegerField(
        default=2,
        help_text="Standard promised dispatch SLA in business days",
    )
    return_policy = models.TextField(
        blank=True,
        help_text="Vendor-specific return policy terms",
    )
    rating_average = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Aggregate customer satisfaction score (0.00 to 5.00)",
    )
    rating_count = models.PositiveIntegerField(
        default=0,
        help_text="Total number of customer ratings received",
    )
    is_featured = models.BooleanField(
        default=False,
        help_text="Highlight in marketplace seller directory and homepage",
    )
    suspension_reason = models.TextField(
        blank=True,
        help_text="Formal reason if vendor account is suspended",
    )
    suspended_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when vendor was suspended",
    )
    suspended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="suspended_vendors",
        help_text="Administrator who initiated suspension",
    )

    class Meta:
        ordering = ["store_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_emkv_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "slug"],
                name="ecommerce_emkv_tenant_slug_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status"],
                name="idx_emkv_ten_status",
            ),
            models.Index(
                fields=["tenant", "kyc_status"],
                name="idx_emkv_ten_kyc",
            ),
        ]

    def clean(self):
        super().clean()
        if self.store_name and not self.slug:
            self.slug = slugify(self.store_name)
        elif self.slug:
            self.slug = slugify(self.slug)

        if self.commission_rate is not None and (self.commission_rate < Decimal("0.00") or self.commission_rate > Decimal("100.00")):
            raise ValidationError({"commission_rate": "Commission rate must be between 0.00% and 100.00%."})
        if self.fixed_fee_per_order is not None and self.fixed_fee_per_order < Decimal("0.00"):
            raise ValidationError({"fixed_fee_per_order": "Fixed fee per order cannot be negative."})
        if self.min_payout_amount is not None and self.min_payout_amount < Decimal("0.00"):
            raise ValidationError({"min_payout_amount": "Minimum payout amount cannot be negative."})

        # Tenant boundary check for Party
        if self.party_id and hasattr(self, "tenant_id") and self.party.tenant_id != self.tenant_id:
            raise ValidationError({"party": "Party belongs to another workspace."})

    def update_rating(self):
        """Recomputes aggregate seller rating from fulfilled sub-orders."""
        agg = self.sub_orders.filter(customer_rating__isnull=False).aggregate(
            total=Count("customer_rating"),
            avg=Avg("customer_rating"),
        )
        total = agg["total"] or 0
        avg = agg["avg"]
        self.rating_count = total
        self.rating_average = Decimal(round(avg, 2)) if avg is not None else Decimal("0.00")
        self.save(update_fields=["rating_average", "rating_count"])

    def __str__(self):
        return f"{self.store_name} ({self.number})"
