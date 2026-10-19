"""Sales 8.13 — `ContentEngagement` (`CNG-`), the content performance record.

A content engagement is one *interaction* with a piece of enablement content: a view, a
download, a share, a comment, a session attendance, a full read. It carries the two numbers the
NavERP bullet asks for:

* **engagement scoring** -- a 0-100 behavioural score derived from what the person actually did
  (the same signal webinar platforms use to rank attendees Hot / Warm / Nurture), and
* **content-to-revenue mapping** -- the revenue credited to that interaction, so a piece of
  collateral can be judged on what it produced rather than on how often it was opened.

The content item itself is NOT declared here. `sales.EnablementContent` (`ECN-`, Sales 8.9) owns
the collateral master -- title, type, file, audience -- and this table only measures
interactions with it.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

ENGAGEMENT_TYPE_CHOICES = [
    ("view", "Content View"),
    ("download", "Content Download"),
    ("share", "Share / Forward"),
    ("comment", "Comment / Feedback"),
    ("attend", "Event / Session Attendance"),
    ("complete", "Full Consumption"),
]

ENGAGEMENT_CHANNEL_CHOICES = [
    ("email", "Email"),
    ("web", "Website"),
    ("search", "Search"),
    ("social", "Social Media"),
    ("sales", "Sales Rep Shared"),
    ("event", "Event"),
    ("partner", "Partner"),
    ("other", "Other"),
]


class ContentEngagement(TenantNumbered):
    """One engagement with a piece of sales enablement content (8.13)."""

    NUMBER_PREFIX = "CNG"

    content = models.ForeignKey(
        "sales.EnablementContent",
        on_delete=models.CASCADE,
        related_name="sales_content_engagements",
    )
    account = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_content_engagements",
    )
    lead = models.ForeignKey(
        "crm.Lead",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_content_engagements",
    )
    campaign = models.ForeignKey(
        "crm.Campaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_content_engagements",
    )
    engagement_type = models.CharField(
        max_length=20,
        choices=ENGAGEMENT_TYPE_CHOICES,
        default="view",
        db_index=True,
    )
    engagement_channel = models.CharField(
        max_length=20,
        choices=ENGAGEMENT_CHANNEL_CHOICES,
        default="web",
    )
    engagement_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Behavioural score 0-100 for this interaction.",
    )
    revenue_attributed = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Revenue credited to this content interaction (content-to-revenue mapping).",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_content_engagements",
    )
    engaged_at = models.DateTimeField(default=timezone.now, db_index=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-engaged_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_cng_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "content", "-engaged_at"],
                name="sales_cng_tnt_content_idx",
            ),
            models.Index(
                fields=["tenant", "account"],
                name="sales_cng_tnt_account_idx",
            ),
            models.Index(
                fields=["tenant", "engagement_type"],
                name="sales_cng_tnt_type_idx",
            ),
        ]

    def __str__(self):
        title = self.content.title if self.content_id else "Content"
        return f"{self.number} · {title} · {self.get_engagement_type_display()}"

    @property
    def is_high_intent(self):
        """Whether this interaction shows buying intent worth a sales follow-up."""
        return self.engagement_score >= 70

    @property
    def is_download(self):
        return self.engagement_type == "download"

    def clean(self):
        super().clean()
        tenant_id = self.tenant_id
        if tenant_id:
            for field_name, label in (
                ("content", "Content"),
                ("account", "Account"),
                ("lead", "Lead"),
                ("campaign", "Campaign"),
                ("currency", "Currency"),
            ):
                related = getattr(self, field_name, None)
                if related is None:
                    continue
                if getattr(related, "tenant_id", None) != tenant_id:
                    raise ValidationError(
                        {field_name: f"{label} must belong to the same workspace."}
                    )
