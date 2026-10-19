"""Sales 8.13 — `MarketingEvent` (`EVT-`) and its child `EventRegistration`.

A marketing event is a webinar, conference, workshop or roadshow. It owns the event itself --
when, where, how big, who owns it, what it cost -- and, through the `registrations` child, who
signed up, who actually showed up, and what happened afterwards.

The registration child is what makes the event measurable: it carries the registration status
(the attendance record), the UTM-ish source channel that filled the room, the behavioural
engagement score used to rank who to call first, and the **post-event follow-up state** -- the
automation NavERP asks for, recorded as a lifecycle rather than dispatched by a worker.

`EventRegistration` is NOT numbered. It is an attendance/membership row, not a document, so it
carries its own tenant FK and timestamps and no human-readable number -- the same ruling as
`crm.CampaignMember`.

OWNERSHIP (L36/L37): the campaign, lead, opportunity, account, user and currency masters already
exist (CRM 1.1 / 1.2 / 1.3, core spine, accounts, accounting 2.2). None is declared here.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from apps.sales.models._base import TenantNumbered, TenantOwned

EVENT_TYPE_CHOICES = [
    ("webinar", "Webinar"),
    ("conference", "Conference"),
    ("workshop", "Workshop"),
    ("trade_show", "Trade Show"),
    ("roadshow", "Roadshow"),
    ("roundtable", "Virtual Roundtable"),
    ("user_group", "User Group"),
    ("other", "Other"),
]

EVENT_STATUS_CHOICES = [
    ("planned", "Planned"),
    ("published", "Published / Open for Registration"),
    ("ongoing", "Ongoing"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
]

REGISTRATION_STATUS_CHOICES = [
    ("registered", "Registered"),
    ("confirmed", "Confirmed"),
    ("attended", "Attended"),
    ("no_show", "No-Show"),
    ("cancelled", "Cancelled"),
    ("waitlisted", "Waitlisted"),
]

FOLLOWUP_STATUS_CHOICES = [
    ("pending", "Pending"),
    ("sent", "Follow-Up Sent"),
    ("meeting_booked", "Meeting Booked"),
    ("opportunity_created", "Opportunity Created"),
    ("no_action", "No Action"),
]

REGISTRATION_SOURCE_CHOICES = [
    ("campaign", "Campaign"),
    ("email", "Email Invitation"),
    ("organic", "Organic / Search"),
    ("partner", "Partner"),
    ("referral", "Referral"),
    ("sales_rep", "Sales Rep"),
    ("other", "Other"),
]


class MarketingEvent(TenantNumbered):
    """A marketing event or webinar with registrations and attendance (8.13)."""

    NUMBER_PREFIX = "EVT"

    name = models.CharField(max_length=200)
    event_type = models.CharField(
        max_length=20,
        choices=EVENT_TYPE_CHOICES,
        default="webinar",
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=EVENT_STATUS_CHOICES,
        default="planned",
        db_index=True,
    )
    start_at = models.DateTimeField(db_index=True)
    end_at = models.DateTimeField(null=True, blank=True)
    timezone_name = models.CharField(
        max_length=64,
        default="UTC",
        help_text="IANA zone the event runs in.",
    )
    venue = models.CharField(max_length=255, blank=True)
    virtual_url = models.URLField(max_length=500, blank=True)
    capacity = models.PositiveIntegerField(
        default=0,
        help_text="0 means unlimited capacity.",
    )
    budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
        help_text="Event cost -- the denominator of cost-per-registrant.",
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_marketing_events",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_marketing_events",
    )
    campaign = models.ForeignKey(
        "crm.Campaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_marketing_events",
        help_text="The campaign that promoted the event.",
    )
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_evt_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status"],
                name="sales_evt_tnt_status_idx",
            ),
            models.Index(
                fields=["tenant", "event_type"],
                name="sales_evt_tnt_type_idx",
            ),
            models.Index(
                fields=["tenant", "start_at"],
                name="sales_evt_tnt_start_idx",
            ),
        ]

    def __str__(self):
        return f"{self.number} · {self.name}"

    @property
    def registered_count(self):
        """How many people registered.

        Uses the ``registered_total`` annotation when the queryset provides one, so a list page
        does not issue one COUNT query per row.
        """
        if "registered_total" in self.__dict__:
            return self.__dict__["registered_total"]
        return self.registrations.count()

    @property
    def attended_count(self):
        """How many people actually showed up.

        Prefers the ``attended_total`` annotation, then a prefetched registration cache, and
        only falls back to a query when neither is available.
        """
        if "attended_total" in self.__dict__:
            return self.__dict__["attended_total"]
        cached = getattr(self, "_prefetched_objects_cache", {}).get("registrations")
        if cached is not None:
            return sum(1 for r in cached if r.registration_status == "attended")
        return self.registrations.filter(registration_status="attended").count()

    @property
    def show_up_rate_pct(self):
        """Attendance as a percentage of registrations, or None when nobody registered."""
        registered = self.registered_count
        if not registered:
            return None
        return round(self.attended_count / registered * 100, 1)

    @property
    def revenue_per_registrant(self):
        """Revenue credited to the attendees of this event, per registrant."""
        registered = self.registered_count
        if not registered:
            return None
        cached = getattr(self, "_prefetched_objects_cache", {}).get("registrations")
        if cached is not None:
            total = sum((r.revenue_attributed or Decimal("0.00")) for r in cached)
        else:
            total = (
                self.registrations.aggregate(total=Sum("revenue_attributed"))["total"]
                or Decimal("0.00")
            )
        return total / registered

    def clean(self):
        super().clean()
        tenant_id = self.tenant_id
        if tenant_id:
            # `currency` is deliberately absent: `accounting.Currency` is a GLOBAL master with no
            # tenant FK, so `getattr(currency, "tenant_id", None)` is None and every currency would
            # be rejected as cross-tenant (L29 -- Currency is never tenant-checked).
            for field_name, label in (
                ("owner", "Owner"),
                ("campaign", "Campaign"),
            ):
                related = getattr(self, field_name, None)
                if related is None:
                    continue
                if getattr(related, "tenant_id", None) != tenant_id:
                    raise ValidationError(
                        {field_name: f"{label} must belong to the same workspace."}
                    )
        if self.end_at and self.start_at and self.end_at < self.start_at:
            raise ValidationError(
                {"end_at": "The event cannot end before it starts."}
            )


class EventRegistration(TenantOwned):
    """One registration for a `MarketingEvent`, with attendance and follow-up state (8.13).

    Not ``TenantNumbered`` -- it is an attendance/membership row, so it carries its own tenant FK
    plus timestamps and no human-readable number. ``registrant_name`` / ``registrant_email`` keep
    a display snapshot so the row survives a null or changed source record.
    """

    event = models.ForeignKey(
        "sales.MarketingEvent",
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    lead = models.ForeignKey(
        "crm.Lead",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_event_registrations",
    )
    account = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_event_registrations",
    )
    campaign = models.ForeignKey(
        "crm.Campaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_event_registrations",
        help_text="The campaign that filled the room -- UTM capture on the registrant.",
    )
    registrant_name = models.CharField(max_length=200)
    registrant_email = models.EmailField(blank=True)
    registration_status = models.CharField(
        max_length=20,
        choices=REGISTRATION_STATUS_CHOICES,
        default="registered",
        db_index=True,
    )
    source_channel = models.CharField(
        max_length=30,
        choices=REGISTRATION_SOURCE_CHOICES,
        default="campaign",
    )
    registered_at = models.DateTimeField(default=timezone.now, db_index=True)
    attended_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="Stamped automatically the first time the registration is marked attended.",
    )
    followup_status = models.CharField(
        max_length=20,
        choices=FOLLOWUP_STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    followup_notes = models.TextField(blank=True)
    engagement_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(100)],
        help_text="Behavioural score from attendance, watch time and interactions.",
    )
    revenue_attributed = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_event_registrations",
        help_text="The deal this attendee became.",
    )

    class Meta:
        ordering = ["-registered_at", "-created_at"]
        indexes = [
            models.Index(
                fields=["tenant", "event"],
                name="sales_evr_tnt_event_idx",
            ),
            models.Index(
                fields=["tenant", "registration_status"],
                name="sales_evr_tnt_status_idx",
            ),
            models.Index(
                fields=["tenant", "followup_status"],
                name="sales_evr_tnt_followup_idx",
            ),
        ]

    def __str__(self):
        return f"{self.registrant_name} · {self.get_registration_status_display()}"

    def save(self, *args, **kwargs):
        # Stamp attended_at on the first transition into "attended"; clear it if the row moves
        # off that status.
        if self.registration_status == "attended" and self.attended_at is None:
            self.attended_at = timezone.now()
        elif self.registration_status != "attended":
            self.attended_at = None
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        tenant_id = self.tenant_id
        if tenant_id:
            for field_name, label in (
                ("event", "Event"),
                ("lead", "Lead"),
                ("account", "Account"),
                ("campaign", "Campaign"),
                ("opportunity", "Opportunity"),
            ):
                related = getattr(self, field_name, None)
                if related is None:
                    continue
                if getattr(related, "tenant_id", None) != tenant_id:
                    raise ValidationError(
                        {field_name: f"{label} must belong to the same workspace."}
                    )
