"""Sales 8.14 — PartnerProfile model."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

PARTNER_TYPE_CHOICES = [
    ("reseller", "Reseller / VAR"),
    ("system_integrator", "System Integrator (SI)"),
    ("distributor", "Distributor"),
    ("isv_technology", "ISV / Technology Partner"),
    ("referral", "Referral / Affiliate"),
    ("consulting", "Consulting & Advisory"),
]

ONBOARDING_STATUS_CHOICES = [
    ("applied", "Application Submitted"),
    ("under_review", "Under Review"),
    ("agreement_pending", "Agreement Pending"),
    ("onboarding", "Onboarding & Training"),
    ("active", "Active Certified Partner"),
    ("suspended", "Suspended"),
    ("terminated", "Terminated"),
]

PARTNER_TIER_CHOICES = [
    ("registered", "Registered Partner"),
    ("bronze", "Bronze"),
    ("silver", "Silver"),
    ("gold", "Gold"),
    ("platinum", "Platinum"),
]


class PartnerProfile(TenantNumbered):
    NUMBER_PREFIX = "PTR"

    partner = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_partner_profiles",
        help_text="Partner organization entity (core.Party with role partner)",
    )
    partner_type = models.CharField(
        max_length=30,
        choices=PARTNER_TYPE_CHOICES,
        default="reseller",
    )
    onboarding_status = models.CharField(
        max_length=20,
        choices=ONBOARDING_STATUS_CHOICES,
        default="applied",
    )
    tier = models.CharField(
        max_length=20,
        choices=PARTNER_TIER_CHOICES,
        default="registered",
    )
    tier_effective_date = models.DateField(null=True, blank=True)
    tier_review_date = models.DateField(null=True, blank=True)
    application_date = models.DateField(default=timezone.localdate)
    agreement_signed_at = models.DateTimeField(null=True, blank=True)
    agreement_document = models.ForeignKey(
        "core.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_partner_agreements",
    )
    channel_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_managed_partners",
    )
    authorized_territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_territory_partners",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.PROTECT,
        related_name="sales_partner_currencies",
    )
    annual_revenue_target = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    actual_revenue_ytd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    required_certifications_count = models.PositiveSmallIntegerField(default=1)
    active_certifications_count = models.PositiveSmallIntegerField(default=0)
    base_discount_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("10.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    deal_reg_margin_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    portal_access_enabled = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-actual_revenue_ytd", "partner__name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "partner"], name="sales_ptr_ten_part_uniq"),
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_ptr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "onboarding_status"], name="sales_ptr_onboard_idx"),
            models.Index(fields=["tenant", "tier"], name="sales_ptr_tier_idx"),
            models.Index(fields=["tenant", "partner_type"], name="sales_ptr_type_idx"),
            models.Index(fields=["tenant", "channel_manager"], name="sales_ptr_cam_idx"),
        ]

    def __str__(self):
        partner_name = getattr(self.partner, "name", "Partner")
        return f"{self.number} — {partner_name} ({self.get_tier_display()})"

    def clean(self):
        super().clean()
        if self.partner_id and hasattr(self, "tenant_id"):
            if self.partner.tenant_id != self.tenant_id:
                raise ValidationError({"partner": "The selected partner organization belongs to another workspace."})

        if self.authorized_territory_id and hasattr(self, "tenant_id"):
            if self.authorized_territory.tenant_id != self.tenant_id:
                raise ValidationError({"authorized_territory": "The selected territory belongs to another workspace."})

        if self.agreement_document_id and hasattr(self, "tenant_id"):
            if self.agreement_document.tenant_id != self.tenant_id:
                raise ValidationError({"agreement_document": "The selected document belongs to another workspace."})

        if self.channel_manager_id and hasattr(self, "tenant_id"):
            if getattr(self.channel_manager, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"channel_manager": "The selected channel manager belongs to another workspace."})

        if self.onboarding_status == "active" and self.agreement_signed_at is None:
            raise ValidationError({"agreement_signed_at": "Active certified partners must have a signed agreement timestamp."})

    @property
    def tier_badge_class(self):
        mapping = {
            "platinum": "badge-purple",
            "gold": "badge-amber",
            "silver": "badge-slate",
            "bronze": "badge-info",
            "registered": "badge-muted",
        }
        # Remember: project badges are only badge-green, badge-amber, badge-red, badge-info, badge-muted, badge-slate
        mapping = {
            "platinum": "badge-green",
            "gold": "badge-amber",
            "silver": "badge-slate",
            "bronze": "badge-info",
            "registered": "badge-muted",
        }
        return mapping.get(self.tier, "badge-muted")

    @property
    def status_badge_class(self):
        mapping = {
            "active": "badge-green",
            "onboarding": "badge-info",
            "agreement_pending": "badge-amber",
            "under_review": "badge-slate",
            "applied": "badge-muted",
            "suspended": "badge-amber",
            "terminated": "badge-red",
        }
        return mapping.get(self.onboarding_status, "badge-slate")

    @property
    def revenue_attainment_pct(self):
        if self.annual_revenue_target and self.annual_revenue_target > 0:
            return round((self.actual_revenue_ytd / self.annual_revenue_target) * Decimal("100"), 1)
        return Decimal("0.0")

    @property
    def certification_compliance_pct(self):
        if self.required_certifications_count and self.required_certifications_count > 0:
            return min(round((self.active_certifications_count / self.required_certifications_count) * 100), 100)
        return 100
