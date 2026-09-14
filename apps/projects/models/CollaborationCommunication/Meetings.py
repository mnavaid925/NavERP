"""Projects 7.9 — Meeting [MTG-] and its two children: the agenda and the action items.

Realizes bullet **3's meeting management**: the agenda builder (``MeetingAgendaItem``), minutes
capture (``Meeting.minutes`` + its stamps) and action-item tracking (``MeetingActionItem``).
The file holds the primary model plus its two children — the ``Invoices.py`` = ``Invoice`` +
``InvoiceLine`` rule. Neither child has an independent register: both are read and edited on the
meeting detail page, which is why they live here rather than in files of their own.

**The status machine.** ``scheduled → in_progress → completed``, with ``cancelled`` reachable from
either live state. ``mtg_start`` / ``mtg_complete`` / ``mtg_cancel`` are the writers, each
stamping its own actual-time field.

**``recurrence`` DECLARES the pattern; nothing schedules it.** A real recurrence engine creates
the next occurrence, which needs the scheduler that 7.17 Workflow & Automation owns. This column
records "this is the weekly steering meeting" so the register can group and report on it; the
next row is still created by hand.

**Minutes are verb-written.** ``minutes`` / ``minutes_by`` / ``minutes_at`` are OFF the model form
and written by ``mtg_minutes`` alone. Capturing minutes does NOT move the status — writing up a
meeting is not completing it (``mtg_complete`` is).

**``actual_start`` / ``actual_end`` are verb-written** by ``mtg_start`` / ``mtg_complete``, never
on a form.

**No money column.** Nothing on a meeting is priced; cost lives on 7.4's registers (L29).
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class Meeting(TenantNumbered):
    NUMBER_PREFIX = "MTG"

    KIND_CHOICES = [
        ("standup", "Standup"),
        ("review", "Review"),
        ("steering", "Steering Committee"),
        ("workshop", "Workshop"),
        ("other", "Other"),
    ]
    MODE_CHOICES = [
        ("in_person", "In person"),
        ("virtual", "Virtual"),
        ("hybrid", "Hybrid"),
    ]
    #: DECLARED, not scheduled — see the module docstring. The engine is 7.17's.
    RECURRENCE_CHOICES = [
        ("none", "One-off"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("biweekly", "Bi-weekly"),
        ("monthly", "Monthly"),
    ]
    STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="meetings")
    title = models.CharField(max_length=200)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default="standup")
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default="virtual")
    recurrence = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default="none")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="scheduled")

    #: VERB-WRITTEN by ``mtg_minutes`` ONLY — never on a form, and never a status change.
    minutes = models.TextField(blank=True)
    minutes_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    minutes_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: VERB-WRITTEN by ``mtg_start`` / ``mtg_complete`` ONLY.
    actual_start = models.DateTimeField(null=True, blank=True, editable=False)
    actual_end = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["-scheduled_start", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="mtg_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="mtg_tnt_status_idx"),
            models.Index(fields=["tenant", "scheduled_start"], name="mtg_tnt_start_idx"),
            # The activity feed's meeting source, which orders by `-created_at` (the register
            # itself sorts by `-scheduled_start`, served by mtg_tnt_start_idx).
            models.Index(fields=["tenant", "-created_at"], name="mtg_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_upcoming(self):
        """Scheduled and still in the future — the register's "what is next" lens (L16 clock)."""
        return self.status == "scheduled" and self.scheduled_start >= timezone.now()

    @property
    def is_past(self):
        """Its slot has passed — true regardless of status, so a never-closed meeting shows up."""
        return self.scheduled_start < timezone.now()


class MeetingAgendaItem(TenantNumbered):
    """One line of a meeting's agenda (bullet 3's *agenda builders*).

    ``is_covered`` / ``covered_by`` / ``covered_at`` are **VERB-WRITTEN by ``agi_cover`` ONLY** —
    a toggle, so an un-cover goes through the SAME verb + audit and the stamps keep their
    timestamps. ``title`` / ``sequence`` / ``presenter`` / ``duration_minutes`` stay editable on a
    covered item: an agenda line is a working row, not frozen evidence — only the STAMPS are
    verb-only.
    """

    NUMBER_PREFIX = "AGI"

    meeting = models.ForeignKey(
        "projects.Meeting", on_delete=models.CASCADE, related_name="agenda_items")
    title = models.CharField(max_length=255)
    presenter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="presented_agenda_items")
    duration_minutes = models.PositiveSmallIntegerField(default=0)
    #: Order within the meeting's agenda. Defaults to 0 — with the ``id`` tiebreak in
    #: Meta.ordering a never-sequenced agenda still reads in append order.
    sequence = models.PositiveSmallIntegerField(default=0)
    #: VERB-WRITTEN by ``agi_cover`` ONLY.
    is_covered = models.BooleanField(default=False)
    covered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    covered_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["meeting_id", "sequence", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "meeting"], name="agi_tnt_meeting_idx"),
            models.Index(fields=["tenant", "is_covered"], name="agi_tnt_covered_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"


class MeetingActionItem(TenantNumbered):
    """One action agreed in a meeting (bullet 3's *action item tracking*).

    ⚠️ **``hrm.MeetingActionItem`` ALREADY EXISTS** — ``apps/hrm/models/ContinuousFeedback/
    Meetingactionitem.py``, HRM 3.20's action item on a **1-on-1 meeting** (``NUMBER_PREFIX =
    "MAI"``). Different app, different domain (an HR 1-on-1 vs a project meeting), and there is no
    Python or database conflict: Django resolves each class inside its own app. **Do NOT "fix"
    this by renaming or merging either one** — the same ruling 7.1 recorded for the three ``PRJ-``
    models (``apps/projects/models/ProjectInitiation/Projects.py:6-17``). It is also why this
    model's prefix is ``MAIT``, not ``MAI``.

    ``is_done`` / ``done_by`` / ``done_at`` are **VERB-WRITTEN by ``mai_toggle`` ONLY** — one
    writer per direction, ``previous`` captured before mutating.

    ``task`` is an **optional** link to a real ``projects.ProjectTask``: a minute can point at the
    work it produced, which is what makes this register join to the plan. 7.9 never CREATES a task
    — the WBS is 7.2's and the execution layer is 7.8's.
    """

    NUMBER_PREFIX = "MAIT"

    meeting = models.ForeignKey(
        "projects.Meeting", on_delete=models.CASCADE, related_name="action_items")
    description = models.TextField()
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="meeting_action_items")
    due_date = models.DateField(null=True, blank=True)
    #: Optional pointer at the task this action produced. SET_NULL — deleting the task must not
    #: delete the minute that asked for it.
    task = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="meeting_action_items")
    #: VERB-WRITTEN by ``mai_toggle`` ONLY.
    is_done = models.BooleanField(default=False)
    done_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")
    done_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="+")

    class Meta:
        ordering = ["meeting_id", "id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "meeting"], name="mait_tnt_meeting_idx"),
            models.Index(fields=["tenant", "is_done"], name="mait_tnt_done_idx"),
            models.Index(fields=["tenant", "assignee"], name="mait_tnt_assignee_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.description[:60]}"

    @property
    def is_overdue(self):
        """Past its due date and still open (L16 clock; safe on an unset ``due_date``)."""
        if not self.due_date or self.is_done:
            return False
        return self.due_date < timezone.localdate()
