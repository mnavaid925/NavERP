"""CRM 1.5 Activity & Communication Management — CalendarEvents models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class CalendarEvent(TenantNumbered):
    """A scheduled event / meeting (1.5 Calendar Integration). Carries a ``public_token`` for the
    login-free invite/RSVP + ``.ics`` pages (mirrors ``Case.public_token``). External
    Google/Outlook/iCal sync is represented by ``sync_source`` + the ICS export — OAuth push/pull
    is deferred."""

    NUMBER_PREFIX = "EVT"

    TYPE_CHOICES = [
        ("meeting", "Meeting"),
        ("call", "Call"),
        ("demo", "Demo"),
        ("deadline", "Deadline"),
        ("reminder", "Reminder"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]
    SYNC_SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("google", "Google Calendar"),
        ("outlook", "Outlook"),
        ("ical", "iCal"),
    ]

    title = models.CharField(max_length=255)
    event_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="meeting")
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    all_day = models.BooleanField(default=False)
    location = models.CharField(max_length=255, blank=True)
    video_url = models.URLField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    sync_source = models.CharField(max_length=10, choices=SYNC_SOURCE_CHOICES, default="manual")
    reminder_minutes = models.PositiveSmallIntegerField(default=15, null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_calendar_events")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_calendar_events")
    related_opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="calendar_events")
    related_case = models.ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="calendar_events")
    description = models.TextField(blank=True)
    # Unguessable bearer token for the public invite/RSVP/ICS endpoints (no login). System-set;
    # editable=False keeps it off every form/admin (mirrors Case/LandingPage/KnowledgeArticle tokens).
    public_token = models.CharField(max_length=64, unique=True, editable=False, blank=True)

    class Meta:
        ordering = ["-start"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_calevent_tenant_status_idx"),
            models.Index(fields=["tenant", "start"], name="crm_calevent_tenant_start_idx"),
        ]

    @property
    def is_past(self):
        return bool(self.start and self.start < timezone.now())

    @property
    def duration_display(self):
        """``H:MM`` span when both ends are set, else ``""``."""
        if self.start and self.end and self.end > self.start:
            minutes = int((self.end - self.start).total_seconds() // 60)
            return "%d:%02d" % divmod(minutes, 60)
        return ""

    def save(self, *args, **kwargs):
        if not self.public_token:
            self.public_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number} · {self.title}"


class EventAttendee(models.Model):
    """An invitee on a ``CalendarEvent`` (1.5). Plain child row (mirrors ``CaseComment``) — no
    auto-number. ``responded_at`` is system-set when the RSVP leaves ``no_response``. ``email`` is
    NULLed when blank so multiple party-only attendees don't collide on ``unique_together``."""

    RSVP_CHOICES = [
        ("no_response", "No Response"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("tentative", "Tentative"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    event = models.ForeignKey("crm.CalendarEvent", on_delete=models.CASCADE, related_name="attendees")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="event_attendees")
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)  # NULL (not "") when blank — see save()
    rsvp_status = models.CharField(max_length=20, choices=RSVP_CHOICES, default="no_response")
    is_organizer = models.BooleanField(default=False)
    responded_at = models.DateTimeField(null=True, blank=True)  # system-set on RSVP
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_organizer", "name"]
        # One row per (event, email); blank email stored as NULL so several party-only attendees
        # (no email) are allowed — MySQL/MariaDB exempt NULLs from a UNIQUE index.
        unique_together = ("event", "email")

    def save(self, *args, **kwargs):
        if not self.email:
            self.email = None
        if self.rsvp_status != "no_response" and self.responded_at is None:
            self.responded_at = timezone.now()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_rsvp_status_display()})"
