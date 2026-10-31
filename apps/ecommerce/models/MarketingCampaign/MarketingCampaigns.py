from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from apps.ecommerce.models._base import TenantNumbered


class MarketingCampaign(TenantNumbered):
    NUMBER_PREFIX = "EMCP"

    CAMPAIGN_TYPE_CHOICES = [
        ("newsletter_broadcast", "Newsletter Broadcast"),
        ("drip_sequence", "Automated Drip Sequence"),
        ("order_alert", "Transactional Order Alert"),
        ("back_in_stock", "Back in Stock Alert"),
        ("abandoned_cart", "Abandoned Cart Recovery"),
        ("geofenced_blast", "Geofenced Location Blast"),
        ("promotional_flash", "Promotional Flash Sale"),
    ]

    CHANNEL_CHOICES = [
        ("email", "Email"),
        ("sms", "SMS"),
        ("push", "Web / Mobile Push"),
        ("omnichannel", "Omnichannel (Email + SMS + Push)"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending / In Progress"),
        ("sent", "Sent / Completed"),
        ("paused", "Paused"),
        ("cancelled", "Cancelled"),
    ]

    name = models.CharField(
        max_length=150,
        help_text="Administrative campaign name, e.g. 'Black Friday VIP Early Access'",
    )
    code = models.CharField(
        max_length=60,
        help_text="Machine identifier slug",
    )
    campaign_type = models.CharField(
        max_length=30,
        choices=CAMPAIGN_TYPE_CHOICES,
        default="newsletter_broadcast",
        help_text="Primary campaign archetype",
    )
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default="email",
        help_text="Outbound marketing communication channel",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
        help_text="Lifecycle dispatch status",
    )
    target_segment = models.ForeignKey(
        "ecommerce.AudienceSegment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marketing_campaigns",
        help_text="Target audience cohort from Personalization engine",
    )
    target_product = models.ForeignKey(
        "ecommerce.CatalogProduct",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marketing_campaigns",
        help_text="Target product for alerts or promo blasts",
    )
    subject = models.CharField(
        max_length=200,
        blank=True,
        help_text="Email subject line / SMS headline / Push title",
    )
    preview_text = models.CharField(
        max_length=255,
        blank=True,
        help_text="Email preheader preview text / short summary",
    )
    content_body = models.TextField(
        help_text="Newsletter HTML markup / SMS copy / Push body",
    )
    sender_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Brand or sender display name",
    )
    sender_address = models.CharField(
        max_length=120,
        blank=True,
        help_text="From email address or SMS sender ID",
    )
    scheduled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled broadcast dispatch time",
    )
    sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when campaign dispatch completed",
    )
    send_throttle_window_hours = models.PositiveIntegerField(
        default=16,
        help_text="Smart Sending cooldown window in hours to prevent recipient fatigue",
    )
    geofence_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Target geographic latitude for geofenced push alerts",
    )
    geofence_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Target geographic longitude for geofenced push alerts",
    )
    geofence_radius_km = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Target radius in km around geofence coordinate",
    )
    recipient_count = models.PositiveIntegerField(
        default=0,
        help_text="Total targeted recipient profiles",
    )
    delivered_count = models.PositiveIntegerField(
        default=0,
        help_text="Confirmed delivered messages",
    )
    opened_count = models.PositiveIntegerField(
        default=0,
        help_text="Unique opens recorded",
    )
    clicked_count = models.PositiveIntegerField(
        default=0,
        help_text="Unique link clicks recorded",
    )
    bounced_count = models.PositiveIntegerField(
        default=0,
        help_text="Failed or bounced dispatches",
    )
    unsubscribed_count = models.PositiveIntegerField(
        default=0,
        help_text="Unsubscribe opt-outs recorded",
    )
    complaint_count = models.PositiveIntegerField(
        default=0,
        help_text="Spam complaints reported",
    )
    revenue_attributed = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total store revenue directly attributed to this campaign",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="ecommerce_emcp_tenant_num_uniq",
            ),
            models.UniqueConstraint(
                fields=["tenant", "code"],
                name="ecommerce_emcp_code_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status", "campaign_type"],
                name="idx_emcp_ten_stat_type",
            ),
            models.Index(
                fields=["tenant", "scheduled_at"],
                name="idx_emcp_ten_sched_at",
            ),
            models.Index(
                fields=["tenant", "target_segment"],
                name="idx_emcp_ten_segment",
            ),
            models.Index(
                fields=["tenant", "target_product"],
                name="idx_emcp_ten_product",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.number or 'draft'})"

    def clean(self):
        super().clean()
        if not self.code and self.name:
            self.code = slugify(self.name)[:60]
        if self.channel == "sms" and len(self.content_body or "") > 1600:
            raise ValidationError({"content_body": "SMS content cannot exceed 1600 characters."})

    @property
    def open_rate(self):
        if not self.delivered_count:
            return Decimal("0.0")
        return round(Decimal(self.opened_count) / Decimal(self.delivered_count) * Decimal("100.0"), 1)

    @property
    def click_rate(self):
        if not self.delivered_count:
            return Decimal("0.0")
        return round(Decimal(self.clicked_count) / Decimal(self.delivered_count) * Decimal("100.0"), 1)
