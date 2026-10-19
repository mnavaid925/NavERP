"""Sales 8.13 — `AttributionTouchpoint` (`ATB-`), the marketing touch ledger.

A touch is ONE interaction between a prospect and a marketing activity: an ad impression, an
email open, a content download, a webinar attendance. It is the raw data row -- it records what
happened, on which channel, at what cost.

It deliberately carries NO credit. Credit is a function of the attribution model AND the whole
journey, so it lives on `CampaignAttribution` (one row per touch per model). Keeping the two apart
is what lets a team evaluate first-touch and last-touch side by side instead of re-typing the
journey for every model.

OWNERSHIP (L36/L37): no campaign, lead, opportunity, account or currency table is declared here.
The campaign master is `crm.Campaign` (CAM-), the journey identity is `crm.Lead` (LEAD-), the
conversion endpoint is `crm.Opportunity` (OPP-), the account is `core.Party`, and the money
denomination is `accounting.Currency`.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered

TOUCH_CHANNEL_CHOICES = [
    ("email", "Email"),
    ("paid_search", "Paid Search"),
    ("organic_search", "Organic Search"),
    ("social", "Social Media"),
    ("display", "Display / Banner"),
    ("webinar", "Webinar"),
    ("event", "Event"),
    ("referral", "Referral / Partner"),
    ("direct_mail", "Direct Mail"),
    ("website", "Website / Organic Visit"),
    ("other", "Other"),
]

TOUCH_TYPE_CHOICES = [
    ("impression", "Ad Impression"),
    ("click", "Click / Visit"),
    ("email_open", "Email Open"),
    ("email_click", "Email Click"),
    ("content_download", "Content Download"),
    ("event_registration", "Event Registration"),
    ("event_attendance", "Event Attendance"),
    ("meeting", "Sales Meeting"),
    ("trial_start", "Trial Start"),
    ("demo_request", "Demo Request"),
]

TOUCH_POSITION_CHOICES = [
    ("first", "First Touch"),
    ("middle", "Middle Touch"),
    ("last", "Last Touch"),
]


class AttributionTouchpoint(TenantNumbered):
    """A single marketing interaction on the path to a conversion (8.13)."""

    NUMBER_PREFIX = "ATB"

    campaign = models.ForeignKey(
        "crm.Campaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_attribution_touchpoints",
        help_text="Source campaign. Optional -- an organic or direct touch has no campaign.",
    )
    lead = models.ForeignKey(
        "crm.Lead",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_attribution_touchpoints",
    )
    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_attribution_touchpoints",
    )
    channel = models.CharField(
        max_length=30,
        choices=TOUCH_CHANNEL_CHOICES,
        default="email",
        db_index=True,
    )
    touch_type = models.CharField(
        max_length=30,
        choices=TOUCH_TYPE_CHOICES,
        default="click",
        db_index=True,
    )
    touch_date = models.DateField(db_index=True)
    touch_position = models.CharField(
        max_length=12,
        choices=TOUCH_POSITION_CHOICES,
        default="middle",
        db_index=True,
        help_text="Journey position. First-touch and last-touch credit are derived from this.",
    )
    cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Cost of this interaction (media spend, allocated event cost).",
    )
    engagement_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Pipeline or revenue value present at the moment of this touch.",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_attribution_touchpoints",
    )
    source_reference = models.CharField(
        max_length=255,
        blank=True,
        help_text="UTM string or external interaction id.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-touch_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_atb_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "touch_date"],
                name="sales_atb_tnt_date_idx",
            ),
            models.Index(
                fields=["tenant", "campaign", "touch_date"],
                name="sales_atb_tnt_camp_idx",
            ),
            models.Index(
                fields=["tenant", "lead"],
                name="sales_atb_tnt_lead_idx",
            ),
            models.Index(
                fields=["tenant", "opportunity"],
                name="sales_atb_tnt_opp_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} · {self.get_channel_display()} · {self.touch_date}"

    @property
    def is_first_touch(self):
        return self.touch_position == "first"

    @property
    def is_last_touch(self):
        return self.touch_position == "last"

    @property
    def attributed_revenue(self):
        """Revenue credited to this touch across every attribution model."""
        return sum(
            (a.attributed_revenue or Decimal("0.00")) for a in self.attributions.all()
        )

    def clean(self):
        super().clean()
        tenant_id = self.tenant_id
        if tenant_id:
            # `currency` is deliberately absent: `accounting.Currency` is a GLOBAL master with no
            # tenant FK, so `getattr(currency, "tenant_id", None)` is None and every currency would
            # be rejected as cross-tenant (L29 -- Currency is never tenant-checked).
            for field_name, label in (
                ("campaign", "Campaign"),
                ("lead", "Lead"),
                ("opportunity", "Opportunity"),
            ):
                related = getattr(self, field_name, None)
                if related is None:
                    continue
                if getattr(related, "tenant_id", None) != tenant_id:
                    raise ValidationError(
                        {field_name: f"{label} must belong to the same workspace."}
                    )
