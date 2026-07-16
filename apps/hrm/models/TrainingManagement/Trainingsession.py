"""HRM 3.22 Training Management — Trainingsession models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class TrainingSession(TenantNumbered):
    """A scheduled occurrence of a ``TrainingCourse`` (3.22 Training Calendar / Classroom / Virtual /
    External) — one date/time window with its own venue OR meeting link OR external vendor, an
    instructor, a capacity, and (for external sessions) cost tracking. ``delivery_mode`` unifies the
    three delivery bullets; ``clean()`` enforces the mode-specific required fields plus an
    instructor/venue double-booking overlap guard (an Absorb LMS differentiator)."""

    NUMBER_PREFIX = "TRS"

    DELIVERY_MODE_CHOICES = [
        ("classroom", "Classroom"),
        ("virtual", "Virtual"),
        ("external", "External"),
    ]
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("confirmed", "Confirmed"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("postponed", "Postponed"),
    ]
    MEETING_PLATFORM_CHOICES = [
        ("zoom", "Zoom"),
        ("teams", "Microsoft Teams"),
        ("webex", "Webex"),
        ("google_meet", "Google Meet"),
        ("gotomeeting", "GoToMeeting"),
        ("other", "Other"),
    ]
    # Statuses that free an instructor/venue slot — a cancelled/postponed session never conflicts.
    _INACTIVE_STATUSES = ("cancelled", "postponed")
    JOIN_WINDOW = timedelta(minutes=15)   # a "Join" button goes live this long before start.

    course = models.ForeignKey("hrm.TrainingCourse", on_delete=models.PROTECT, related_name="sessions",
                               help_text="The catalog course this session delivers.")
    delivery_mode = models.CharField(max_length=10, choices=DELIVERY_MODE_CHOICES, default="classroom")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="scheduled")
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    timezone = models.CharField(max_length=50, default="UTC",
                                help_text="IANA/display timezone the times are quoted in.")
    capacity = models.PositiveIntegerField(default=20)
    waitlist_enabled = models.BooleanField(default=False,
                                           help_text="Allow a waitlist once full (the queue itself is 3.24 Nomination).")
    # Classroom
    venue_name = models.CharField(max_length=255, blank=True)
    venue_address = models.TextField(blank=True)
    # Virtual
    meeting_platform = models.CharField(max_length=15, choices=MEETING_PLATFORM_CHOICES, blank=True)
    meeting_link = models.URLField(blank=True)
    meeting_id = models.CharField(max_length=100, blank=True)
    # Instructor (internal employee OR a named external trainer)
    instructor_employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name="training_sessions_instructed")
    external_instructor_name = models.CharField(max_length=255, blank=True)
    # External vendor — a core.Party (vendor role); no new vendor table.
    external_vendor = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="training_sessions_as_vendor")
    # Cost tracking (external sessions) — currency is the GLOBAL accounting master (no tenant FK).
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="training_sessions")
    invoice_reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_datetime", "number"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_trs_tenant_status_idx"),
            models.Index(fields=["tenant", "course"], name="hrm_trs_tenant_course_idx"),
            models.Index(fields=["tenant", "delivery_mode"], name="hrm_trs_tenant_mode_idx"),
            models.Index(fields=["tenant", "start_datetime"], name="hrm_trs_tenant_start_idx"),
            models.Index(fields=["tenant", "instructor_employee"], name="hrm_trs_tenant_instr_idx"),
        ]

    def clean(self):
        if self.start_datetime and self.end_datetime and self.end_datetime <= self.start_datetime:
            raise ValidationError({"end_datetime": "The end time must be after the start time."})
        if self.delivery_mode == "classroom" and not self.venue_name.strip():
            raise ValidationError({"venue_name": "A classroom session needs a venue."})
        if self.delivery_mode == "virtual" and not self.meeting_link.strip():
            raise ValidationError({"meeting_link": "A virtual session needs a meeting link."})
        if self.delivery_mode == "external" and not (self.external_vendor_id or self.external_instructor_name.strip()):
            raise ValidationError(
                {"external_vendor": "An external session needs a vendor or a named external instructor."})
        # Double-booking guard — only when we have a real time window and an active status.
        if self.start_datetime and self.end_datetime and self.status not in self._INACTIVE_STATUSES:
            overlapping = TrainingSession.objects.filter(
                tenant_id=self.tenant_id,
                start_datetime__lt=self.end_datetime,
                end_datetime__gt=self.start_datetime,
            ).exclude(pk=self.pk).exclude(status__in=self._INACTIVE_STATUSES)
            if self.instructor_employee_id and overlapping.filter(
                    instructor_employee_id=self.instructor_employee_id).exists():
                raise ValidationError(
                    {"instructor_employee": "This instructor is already booked for an overlapping session."})
            if self.delivery_mode == "classroom" and self.venue_name.strip() and overlapping.filter(
                    delivery_mode="classroom", venue_name__iexact=self.venue_name.strip()).exists():
                raise ValidationError({"venue_name": "This venue is already booked for an overlapping session."})

    @property
    def can_join(self):
        """Derived (never stored) — the virtual "Join" button is live from 15 min before start until
        the end time, and only when there's a link. Mirrors TalentLMS's calendar Join affordance."""
        if not self.meeting_link or not (self.start_datetime and self.end_datetime):
            return False
        now = timezone.now()
        return (self.start_datetime - self.JOIN_WINDOW) <= now <= self.end_datetime

    @property
    def is_upcoming(self):
        """Derived — a live, not-yet-started session (the calendar's default lens)."""
        return self.status not in ("completed", "cancelled") and bool(
            self.start_datetime and self.start_datetime > timezone.now())

    @property
    def approved_nomination_count(self):
        """Derived (3.24 cross-touch) — how many nominations are approved for this session."""
        return self.nominations.filter(status="approved").count()

    @property
    def is_full(self):
        """Derived (3.24 cross-touch) — approved nominations have reached the seat capacity."""
        return self.approved_nomination_count >= self.capacity

    def __str__(self):
        if self.course_id:
            return f"{self.number} · {self.course.title} ({self.start_datetime:%Y-%m-%d %H:%M})"
        return self.number
