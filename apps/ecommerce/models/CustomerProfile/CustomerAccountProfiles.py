import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.ecommerce.models._base import TenantNumbered


class CustomerAccountProfile(TenantNumbered):
    NUMBER_PREFIX = "ECAP"

    TIER_CHOICES = [
        ("bronze", "Bronze"),
        ("silver", "Silver"),
        ("gold", "Gold"),
        ("platinum", "Platinum"),
        ("vip", "VIP"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("pending_verification", "Pending Verification"),
        ("suspended", "Suspended"),
        ("locked", "Locked"),
        ("anonymized", "Anonymized / GDPR Erased"),
    ]
    AUTH_MODE_CHOICES = [
        ("password", "Email / Password"),
        ("passwordless_email", "Passwordless Email Magic Link"),
        ("phone_otp", "Phone SMS OTP"),
        ("sso_oauth", "Single Sign-On (SSO / OAuth)"),
    ]
    FREQUENCY_CHOICES = [
        ("all", "All Communications"),
        ("weekly_digest", "Weekly Digest"),
        ("promotions_only", "Promotions & Offers Only"),
    ]

    customer = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        related_name="ecommerce_profiles",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ecommerce_customer_profiles",
    )
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default="bronze")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default="active")
    auth_mode = models.CharField(max_length=25, choices=AUTH_MODE_CHOICES, default="password")

    phone_number = models.CharField(max_length=32, blank=True)
    phone_verified = models.BooleanField(default=False)

    preferred_currency = models.ForeignKey(
        "accounting.Currency",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ecommerce_customer_profiles",
    )
    preferred_language = models.CharField(max_length=10, default="en")

    email_marketing_opt_in = models.BooleanField(default=False)
    sms_marketing_opt_in = models.BooleanField(default=False)
    notification_frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        default="all",
    )
    marketing_consent_at = models.DateTimeField(null=True, blank=True)
    unsubscribe_token = models.CharField(max_length=64, blank=True, default="")

    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    order_count = models.PositiveIntegerField(default=0)
    last_order_at = models.DateTimeField(null=True, blank=True)

    internal_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "tier"], name="idx_ecap_ten_tier"),
            models.Index(fields=["tenant", "status"], name="idx_ecap_ten_stat"),
            models.Index(fields=["tenant", "customer"], name="idx_ecap_ten_cust"),
        ]

    def __str__(self):
        return f"{self.number} - {self.customer}"

    def save(self, *args, **kwargs):
        if not self.unsubscribe_token:
            self.unsubscribe_token = secrets.token_urlsafe(32)[:64]
        if (self.email_marketing_opt_in or self.sms_marketing_opt_in) and not self.marketing_consent_at:
            self.marketing_consent_at = timezone.now()
        super().save(*args, **kwargs)
