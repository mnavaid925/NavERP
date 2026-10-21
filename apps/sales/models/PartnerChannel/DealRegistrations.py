"""Sales 8.14 — DealRegistration model."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

REGISTRATION_STATUS_CHOICES = [
    ("submitted", "Submitted / Pending"),
    ("under_review", "Under Review"),
    ("approved", "Approved & Protected"),
    ("rejected", "Rejected"),
    ("expired", "Protection Expired"),
    ("converted", "Converted to Opportunity"),
    ("conflicted", "Channel Conflicted"),
]

EXCLUSIVITY_CHOICES = [
    ("pending", "Pending Approval"),
    ("exclusive", "Full Exclusivity"),
    ("non_exclusive", "Non-Exclusive"),
    ("expired", "Expired"),
    ("revoked", "Revoked"),
]


class DealRegistration(TenantNumbered):
    NUMBER_PREFIX = "DLR"

    partner = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_partner_deal_registrations",
        help_text="Partner firm submitting the registration",
    )
    customer_account = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_registered_deals",
        help_text="Prospective customer account",
    )
    deal_name = models.CharField(max_length=255)
    estimated_value = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="sales_deal_reg_currencies",
    )
    expected_close_date = models.DateField()
    submission_date = models.DateField(default=timezone.localdate)
    status = models.CharField(
        max_length=20,
        choices=REGISTRATION_STATUS_CHOICES,
        default="submitted",
    )
    rejection_reason = models.CharField(max_length=255, blank=True)
    protection_start_date = models.DateField(null=True, blank=True)
    protection_end_date = models.DateField(null=True, blank=True)
    exclusivity_status = models.CharField(
        max_length=20,
        choices=EXCLUSIVITY_CHOICES,
        default="pending",
    )
    protected_margin_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    extension_count = models.PositiveSmallIntegerField(default=0)
    is_conflicted = models.BooleanField(default=False)
    conflict_summary = models.TextField(blank=True)
    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_registered_deal_sources",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_reviewed_deal_regs",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    partner_rep_name = models.CharField(max_length=150, blank=True)
    partner_rep_email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-submission_date", "-estimated_value"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_dlr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "partner", "status"], name="sales_dlr_part_stat_idx"),
            models.Index(fields=["tenant", "customer_account"], name="sales_dlr_cust_idx"),
            models.Index(fields=["tenant", "protection_end_date"], name="sales_dlr_prot_end_idx"),
            models.Index(fields=["tenant", "status"], name="sales_dlr_stat_idx"),
            models.Index(fields=["tenant", "exclusivity_status"], name="sales_dlr_excl_idx"),
        ]

    def __str__(self):
        partner_name = getattr(self.partner, "name", "Partner")
        return f"{self.number} — {self.deal_name} ({partner_name})"

    def clean(self):
        super().clean()
        if self.partner_id and hasattr(self, "tenant_id"):
            if self.partner.tenant_id != self.tenant_id:
                raise ValidationError({"partner": "The selected partner firm belongs to another workspace."})

        if self.customer_account_id and hasattr(self, "tenant_id"):
            if self.customer_account.tenant_id != self.tenant_id:
                raise ValidationError({"customer_account": "The selected customer account belongs to another workspace."})

        if self.partner_id and self.customer_account_id and self.partner_id == self.customer_account_id:
            raise ValidationError({"customer_account": "The partner organization cannot register itself as the client account."})

        if self.protection_start_date and self.protection_end_date:
            if self.protection_end_date < self.protection_start_date:
                raise ValidationError({"protection_end_date": "Protection end date cannot be earlier than start date."})

        if self.status == "approved":
            if not self.protection_start_date:
                raise ValidationError({"protection_start_date": "Approved registrations must have a protection start date."})
            if not self.protection_end_date:
                raise ValidationError({"protection_end_date": "Approved registrations must have an exclusivity expiration date."})

        if self.opportunity_id and hasattr(self, "tenant_id"):
            if self.opportunity.tenant_id != self.tenant_id:
                raise ValidationError({"opportunity": "The linked opportunity belongs to another workspace."})

    @property
    def status_badge_class(self):
        mapping = {
            "approved": "badge-green",
            "converted": "badge-green",
            "under_review": "badge-info",
            "submitted": "badge-muted",
            "conflicted": "badge-amber",
            "expired": "badge-slate",
            "rejected": "badge-red",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def exclusivity_badge_class(self):
        mapping = {
            "exclusive": "badge-green",
            "non_exclusive": "badge-info",
            "pending": "badge-muted",
            "expired": "badge-slate",
            "revoked": "badge-red",
        }
        return mapping.get(self.exclusivity_status, "badge-slate")

    @property
    def is_protection_active(self):
        if self.status == "approved" and self.protection_end_date:
            return self.protection_end_date >= timezone.localdate()
        return False

    @property
    def days_remaining(self):
        if self.protection_end_date:
            delta = (self.protection_end_date - timezone.localdate()).days
            return max(delta, 0)
        return 0
