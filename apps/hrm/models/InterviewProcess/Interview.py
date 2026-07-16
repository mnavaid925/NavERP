"""HRM 3.7 Interview Process — Interview models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.InterviewProcess.PANELIST_ROLE_CHOICESs import PANELIST_ROLE_CHOICES
from apps.hrm.models.InterviewProcess.RSVP_STATUS_CHOICESs import RSVP_STATUS_CHOICES
from apps.hrm.models.InterviewProcess.VIDEO_PROVIDER_CHOICESs import VIDEO_PROVIDER_CHOICES
from apps.hrm.models.InterviewProcess.PANELIST_ROLE_CHOICESs import PANELIST_ROLE_CHOICES
from apps.hrm.models.InterviewProcess.RSVP_STATUS_CHOICESs import RSVP_STATUS_CHOICES
from apps.hrm.models.InterviewProcess.VIDEO_PROVIDER_CHOICESs import VIDEO_PROVIDER_CHOICES


# ---------------------------------------------------------------------------
# 3.7 Interview Process — scheduling, panel assignment, and structured feedback/
# scorecards. Interviews hang off the 3.6 ``JobApplication`` spine (candidate +
# requisition are reached through it). Invites/reminders REUSE the 3.6
# ``CandidateEmailTemplate`` + ``CandidateCommunication`` log via the
# ``_send_candidate_email`` view helper — no new email model. Live calendar /
# Zoom-Teams-Meet auto-link / SMS dispatch + AI scoring are DEFERRED (the meeting
# link is a plain field; reminders are a manual, audited action).
# ---------------------------------------------------------------------------
INTERVIEW_MODE_CHOICES = [
    ("in_person", "In Person"),
    ("phone", "Phone"),
    ("video", "Video Call"),
    ("one_way_video", "One-way Video"),
]


INTERVIEW_STATUS_CHOICES = [
    ("scheduled", "Scheduled"),
    ("confirmed", "Confirmed"),
    ("in_progress", "In Progress"),
    ("completed", "Completed"),
    ("cancelled", "Cancelled"),
    ("no_show", "No Show"),
    ("rescheduled", "Rescheduled"),
]


# Closed statuses an interview can't be transitioned out of without an explicit reschedule
# (mirrors APPLICATION_TERMINAL_STAGES). A no-show/cancelled round is re-run by rescheduling.
INTERVIEW_TERMINAL_STATUSES = ("completed", "cancelled", "no_show")


class Interview(TenantNumbered):
    """A scheduled interview round on a ``JobApplication`` (3.7). ``status`` is the workflow-owned state
    machine — set only by the status-action POSTs (confirm/start/complete/cancel/no_show/reschedule),
    never the form (``editable=False``), mirroring ``JobApplication.stage``. Candidate + requisition are
    reached through ``application``. ``meeting_url``/``video_provider`` hold the video link (live
    Zoom/Teams/Meet generation deferred); ``reminder_sent_at``/``feedback_reminder_sent_at`` are stamped
    by the manual send-reminder actions (automated Celery dispatch deferred)."""

    NUMBER_PREFIX = "INTV"

    application = models.ForeignKey("hrm.JobApplication", on_delete=models.CASCADE, related_name="interviews")
    title = models.CharField(max_length=255, help_text='e.g. "Technical Round 2" or "HR Screen".')
    round_number = models.PositiveSmallIntegerField(default=1)
    mode = models.CharField(max_length=20, choices=INTERVIEW_MODE_CHOICES, default="video")
    status = models.CharField(max_length=20, choices=INTERVIEW_STATUS_CHOICES, default="scheduled",
                              editable=False)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveSmallIntegerField(default=60)
    location = models.CharField(max_length=255, blank=True,
                                help_text="Physical room / address for in-person rounds.")
    video_provider = models.CharField(max_length=20, choices=VIDEO_PROVIDER_CHOICES, blank=True)
    meeting_url = models.URLField(blank=True,
        help_text="Video meeting link (paste from Zoom/Teams/Meet — auto-generation is deferred).")
    interviewer_instructions = models.TextField(blank=True,
        help_text="Briefing shown to the panel (focus areas, must-asks).")
    notes = models.TextField(blank=True)
    scheduled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="scheduled_interviews")
    reminder_sent_at = models.DateTimeField(null=True, blank=True, editable=False)
    feedback_reminder_sent_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-scheduled_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_intv_tenant_status_idx"),
            models.Index(fields=["tenant", "mode"], name="hrm_intv_tenant_mode_idx"),
            models.Index(fields=["tenant", "application"], name="hrm_intv_tenant_app_idx"),
            # Supports the default ``-scheduled_at`` ordering of the interview list under the tenant filter.
            models.Index(fields=["tenant", "scheduled_at"], name="hrm_intv_tenant_sched_idx"),
        ]

    @property
    def candidate(self):
        """The interviewee, via the application. Views that list interviews must
        ``select_related("application__candidate")`` to keep this O(1)."""
        return self.application.candidate

    @property
    def requisition(self):
        """The open position, via the application (select_related in list views)."""
        return self.application.requisition

    @property
    def is_closed(self):
        return self.status in INTERVIEW_TERMINAL_STATUSES

    def __str__(self):
        return f"{self.number} · {self.title}" if self.number else self.title


class InterviewPanelist(TenantOwned):
    """An interviewer assigned to an ``Interview`` (3.7). Managed inline on the interview detail hub
    (add/remove/rsvp POST actions) like ``CandidateSkill`` / ``RequisitionApproval`` — no standalone
    pages. ``role`` labels the panel seat; ``rsvp_status`` tracks the interviewer's acceptance;
    ``notified_at`` is stamped when an invite is sent. Unique per (interview, interviewer)."""

    interview = models.ForeignKey("hrm.Interview", on_delete=models.CASCADE, related_name="panelists")
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                    related_name="interview_panels")
    role = models.CharField(max_length=20, choices=PANELIST_ROLE_CHOICES, default="interviewer")
    rsvp_status = models.CharField(max_length=20, choices=RSVP_STATUS_CHOICES, default="pending")
    briefing_notes = models.TextField(blank=True)
    notified_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["role", "pk"]
        unique_together = ("interview", "interviewer")
        indexes = [
            models.Index(fields=["tenant", "interview"], name="hrm_ipan_tenant_intv_idx"),
        ]

    def __str__(self):
        who = self.interviewer.get_full_name() or self.interviewer.username
        return f"{who} ({self.get_role_display()})"
