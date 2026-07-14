"""CRM 1.3 Marketing Automation — EmailCampaigns models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class EmailCampaign(TenantNumbered):
    """An email send/blast (1.3 Email Marketing) tied to a Campaign + EmailTemplate.

    A/B testing folds into ``variant_template`` (+ ``is_ab_test``); drip folds into
    ``send_type='drip'`` + ``scheduled_at`` — no separate DripStep/ABVariant tables. All the
    engagement counters are SYSTEM-managed (set by ``emailcampaign_send`` / the seeder) and
    excluded from the form so a user can't fabricate metrics.
    """

    NUMBER_PREFIX = "BLAST"

    SEND_TYPE_CHOICES = [
        ("one_time", "One-time Blast"),
        ("drip", "Drip / Automated"),
        ("ab_test", "A/B Test"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("paused", "Paused"),
        ("cancelled", "Cancelled"),
    ]
    SENT_STATUSES = ("sending", "sent")

    name = models.CharField(max_length=255)
    campaign = models.ForeignKey("Campaign", on_delete=models.CASCADE, related_name="email_campaigns")
    template = models.ForeignKey("EmailTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="email_campaigns")
    variant_template = models.ForeignKey("EmailTemplate", on_delete=models.SET_NULL, null=True, blank=True, related_name="+")  # A/B variant B
    is_ab_test = models.BooleanField(default=False)
    send_type = models.CharField(max_length=10, choices=SEND_TYPE_CHOICES, default="one_time")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)  # system-set on send
    # Engagement counters — system-managed (excluded from the form).
    recipients_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    opened_count = models.PositiveIntegerField(default=0)
    clicked_count = models.PositiveIntegerField(default=0)
    bounced_count = models.PositiveIntegerField(default=0)
    unsubscribed_count = models.PositiveIntegerField(default=0)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_email_campaigns")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_blast_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_blast_tnt_created_idx"),
        ]

    @property
    def delivered_count(self):
        return max(0, (self.sent_count or 0) - (self.bounced_count or 0))

    @property
    def open_rate(self):
        """Unique opens ÷ delivered, as a %. None when nothing was delivered.

        Casts to Decimal so the property is correct on a freshly-created (un-round-tripped)
        instance, mirroring ``Campaign.roi``."""
        delivered = self.delivered_count
        if not delivered:
            return None
        return Decimal(self.opened_count or 0) / Decimal(delivered) * 100

    @property
    def click_rate(self):
        delivered = self.delivered_count
        if not delivered:
            return None
        return Decimal(self.clicked_count or 0) / Decimal(delivered) * 100

    @property
    def bounce_rate(self):
        sent = self.sent_count or 0
        if not sent:
            return None
        return Decimal(self.bounced_count or 0) / Decimal(sent) * 100

    def __str__(self):
        return f"{self.number} · {self.name}"
