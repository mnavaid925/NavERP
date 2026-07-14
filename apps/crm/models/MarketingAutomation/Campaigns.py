"""CRM 1.3 Marketing Automation — Campaigns models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class Campaign(TenantNumbered):
    """A marketing campaign (1.3) with planned/actual budget + ROI."""

    NUMBER_PREFIX = "CAM"

    TYPE_CHOICES = [
        ("email", "Email"),
        ("webinar", "Webinar"),
        ("event", "Event"),
        ("digital_ad", "Digital Ad"),
        ("direct_mail", "Direct Mail"),
        ("social", "Social Media"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("planned", "Planned"),
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    OBJECTIVE_CHOICES = [
        ("awareness", "Brand Awareness"),
        ("lead_gen", "Lead Generation"),
        ("nurture", "Nurture / Engagement"),
        ("conversion", "Conversion / Sales"),
        ("event", "Event Promotion"),
        ("retention", "Retention / Loyalty"),
    ]

    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="email")
    objective = models.CharField(max_length=20, choices=OBJECTIVE_CHOICES, default="lead_gen")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="planned")
    # Self-FK lets campaigns roll up under a parent program (e.g. "Q3 Demand Gen").
    parent_campaign = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_campaigns")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget_planned = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    budget_actual = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    expected_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actual_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    target_size = models.PositiveIntegerField(default=0)
    # UTM tagging so downstream web/landing traffic can be attributed to the campaign.
    utm_source = models.CharField(max_length=120, blank=True)
    utm_medium = models.CharField(max_length=120, blank=True)
    utm_campaign = models.CharField(max_length=120, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_campaigns")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_campaign_tnt_status_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_campaign_tnt_created_idx"),
        ]

    @property
    def roi(self):
        """Return on investment %, or None when no actual spend is recorded.

        Casts to Decimal so the property is correct on a freshly-created (un-round-tripped)
        instance, where DecimalField values are still plain strings.
        """
        budget = Decimal(self.budget_actual or 0)
        if not budget:
            return None
        return (Decimal(self.actual_revenue or 0) - budget) / budget * 100

    def __str__(self):
        return f"{self.number} · {self.name}"


class CampaignMember(models.Model):
    """A target-list member of a Campaign (1.3) with per-recipient response tracking.

    Not ``TenantNumbered`` — it's a membership row (target-list segmentation), so it
    carries its own tenant FK + timestamps and no human-readable number. Targets either a
    reused ``core.Party`` (account/contact) or a ``crm.Lead``; ``member_name``/``member_email``
    keep a display snapshot so imported list rows survive a null/changed source record.
    """

    STATUS_CHOICES = [
        ("targeted", "Targeted"),
        ("sent", "Sent"),
        ("opened", "Opened"),
        ("clicked", "Clicked"),
        ("responded", "Responded"),
        ("converted", "Converted"),
        ("bounced", "Bounced"),
        ("unsubscribed", "Unsubscribed"),
    ]
    RESPONDED_STATUSES = ("responded", "converted")

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    campaign = models.ForeignKey("Campaign", on_delete=models.CASCADE, related_name="members")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_campaign_members")
    lead = models.ForeignKey("Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_campaign_members")
    member_name = models.CharField(max_length=255)
    member_email = models.EmailField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="targeted")
    responded_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_cmem_tnt_status_idx"),
            models.Index(fields=["tenant", "campaign"], name="crm_cmem_tnt_camp_idx"),
            models.Index(fields=["tenant", "created_at"], name="crm_cmem_tnt_created_idx"),
        ]

    @property
    def has_responded(self):
        return self.status in self.RESPONDED_STATUSES

    def save(self, *args, **kwargs):
        # System-set responded_at: stamp the first time the member responds/converts.
        if self.status in self.RESPONDED_STATUSES and self.responded_at is None:
            self.responded_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.member_name} · {self.get_status_display()}"
