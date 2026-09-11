"""Projects 7.5 — ProjectIssue [ISS-]: one logged issue, action item or decision on one project.

Bullet **4 Issue Logging & Escalation** owns this row. A ``ProjectRisk`` records something that
*might* happen; an issue is something that already *has* — a blocker, a decision that had to be
taken, an action item someone owes. ``rsk_realize`` mints one of these automatically when a risk
materializes, which is the one place the risk register and the issue log meet, so the two cannot
drift about which risk became real.

**Everything derived is a Python property, never a column.** ``is_open``, ``is_overdue`` and
``age_days`` are pure functions of the status and two dates (the 7.1 ROI / 7.4 EVM ruling): a
stored age is stale the moment the clock moves, and a stored ``is_overdue`` is stale the moment the
due date is edited. ``age_days`` reads ``timezone.localdate()`` — the same clock the rest of 7.5
uses (L16).

**The lifecycle is verb-driven.** ``status``, ``root_cause``, ``resolution_note``, ``resolved_by``,
``resolved_at``, ``escalation_level``, ``escalated_to``, ``escalated_at`` and ``created_by`` are all
OFF the model form: ``iss_escalate``, ``iss_resolve`` and ``iss_close`` are the only writers of
those stamps, so the evidence trail keeps its timestamps. ``is_locked`` (``resolved``/``closed``)
is what makes edit/delete refuse a finished row.

**Boundaries (L36):** ``project``, ``wbs_node`` and ``risk`` are all FK'd **by string** into
7.1/7.2/7.5 — none is re-declared here. ``lessons_learned`` is a FIELD on the row, not a store: the
knowledge repository is 7.10's (Ruling 3), and the monitoring page reads it back as a lens.
"""
from apps.projects.models._base import *  # noqa: F401,F403
from apps.projects.models._base import models, settings


class ProjectIssue(TenantNumbered):
    NUMBER_PREFIX = "ISS"

    #: What kind of entry this is. An ``action_item`` is a task someone owes; a ``decision`` is a
    #: choice that was made and must be recorded; a plain ``issue`` is a live problem.
    ISSUE_TYPE_CHOICES = [
        ("issue", "Issue"),
        ("action_item", "Action Item"),
        ("decision", "Decision"),
        ("other", "Other"),
    ]
    #: Four bands, no numeric score — the issue log is triaged by impact, not by P × I.
    SEVERITY_CHOICES = [
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("blocked", "Blocked"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]

    project = models.ForeignKey(
        "projects.Project", on_delete=models.CASCADE, related_name="issues")
    wbs_node = models.ForeignKey(
        "projects.ProjectTask", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="issues")
    #: The register row this issue grew out of, when it came from a realized risk.
    risk = models.ForeignKey(
        "projects.ProjectRisk", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="issues")
    title = models.CharField(max_length=255)
    description = models.TextField()
    issue_type = models.CharField(max_length=12, choices=ISSUE_TYPE_CHOICES, default="issue")
    severity = models.CharField(max_length=8, choices=SEVERITY_CHOICES, default="medium")
    #: Verb-driven (escalate / resolve / close) — OFF the form, so the evidence trail keeps its
    #: stamps.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="owned_issues")
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="raised_issues")
    identified_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(
        null=True, blank=True, help_text="When this issue needs to be resolved by.")
    #: 0 means never escalated; each ``iss_escalate`` bumps it one level (max 4). Stored because
    #: the queue lens (``?escalated=1``) is a real column lookup, not a derived figure.
    escalation_level = models.PositiveSmallIntegerField(default=0)
    escalated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="escalated_issues")
    escalated_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: The resolution capture — written by ``iss_resolve``, never by a generic edit.
    root_cause = models.TextField(blank=True)
    resolution_note = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="resolved_issues")
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    #: The closed-row takeaway. A field, NOT a store — the knowledge repository is 7.10's.
    lessons_learned = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        editable=False, related_name="iss_created")

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "project"], name="iss_tnt_project_idx"),
            models.Index(fields=["tenant", "status"], name="iss_tnt_status_idx"),
            models.Index(fields=["tenant", "severity"], name="iss_tnt_severity_idx"),
            models.Index(fields=["tenant", "escalation_level"], name="iss_tnt_esc_idx"),
            models.Index(fields=["tenant", "-created_at"], name="iss_tnt_created_idx"),
            # The ``?issue_type=`` filter and the pinned ``?overdue=1`` due-date lens — the RRA
            # register already carries the due_date twin (``rra_tnt_due_idx``).
            models.Index(fields=["tenant", "issue_type"], name="iss_tnt_type_idx"),
            models.Index(fields=["tenant", "due_date"], name="iss_tnt_due_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    # -- derived figures (never stored) ---------------------------------------------------------

    @property
    def is_open(self):
        """The three live statuses — everything but the resolved/closed/cancelled terminals."""
        return self.status in ("open", "in_progress", "blocked")

    @property
    def is_overdue(self):
        """Due date passed while the issue is still live. Uses ``timezone.localdate()`` (L16)."""
        if not self.due_date:
            return False
        return self.due_date < timezone.localdate() and self.is_open

    @property
    def age_days(self):
        """Days since the issue was raised (0 when ``identified_date`` is unset)."""
        if not self.identified_date:
            return 0
        return (timezone.localdate() - self.identified_date).days

    @property
    def is_locked(self):
        """Resolved and closed rows are frozen evidence — edit/delete refuse them."""
        return self.status in ("resolved", "closed")

    def clean(self):
        super().clean()
        if self.wbs_node_id and self.project_id \
                and self.wbs_node.project_id != self.project_id:
            raise ValidationError(
                {"wbs_node": "The WBS node must belong to the same project as the issue."})
        if self.risk_id and self.project_id \
                and self.risk.project_id != self.project_id:
            raise ValidationError(
                {"risk": "The risk must belong to the same project as the issue."})
