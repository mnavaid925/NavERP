"""HRM 3.36 Helpdesk — Helpdeskticket models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.JobRequisition.PRIORITY_CHOICESs import PRIORITY_CHOICES
from apps.hrm.models.JobRequisition.PRIORITY_CHOICESs import PRIORITY_CHOICES


class HelpdeskTicket(TenantNumbered):
    """An employee helpdesk ticket (``TKT-#####``). Agent-worked lifecycle (new -> open -> in_progress
    -> waiting -> resolved -> closed, + cancelled) driven by bespoke action views — NOT the
    single-approver ``_hr_request_*`` machine (a ticket is worked, not authorized). The requester FK is
    named ``employee`` so the ticket reuses ``_ss_scope`` / ``_can_manage_own_child`` verbatim. SLA due
    timestamps are stamped once in ``save()`` from the policy's per-priority targets (mirrors
    ``crm.Case.save``); breach / at-risk / age are COMPUTED, never stored. Post-resolution CSAT
    (``satisfaction_*``) is captured inline via the feedback action — no separate survey model."""

    NUMBER_PREFIX = "TKT"

    PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent")]
    STATUS_CHOICES = [
        ("new", "New"),
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("waiting", "Waiting on Requester"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
        ("cancelled", "Cancelled"),
    ]
    # Statuses in which the ticket is still being worked (requester may edit/cancel; SLA clock live).
    OPEN_STATUSES = ("new", "open", "in_progress", "waiting")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE,
                                 related_name="helpdesk_tickets")  # the requester
    subject = models.CharField(max_length=255)
    description = models.TextField()
    category = models.ForeignKey("hrm.HelpdeskCategory", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="tickets")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="new")
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_helpdesk_assigned")
    sla_policy = models.ForeignKey("hrm.HelpdeskSLAPolicy", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="tickets")
    first_response_due = models.DateTimeField(null=True, blank=True)
    resolution_due = models.DateTimeField(null=True, blank=True)
    first_responded_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    # Inline CSAT — set by the requester through the feedback action after resolution (never on the agent form).
    satisfaction_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    satisfaction_comment = models.TextField(blank=True)
    satisfaction_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_tkt_tnt_status_idx"),
            models.Index(fields=["tenant", "employee", "status"], name="hrm_tkt_emp_status_idx"),
            models.Index(fields=["tenant", "assignee"], name="hrm_tkt_tnt_assignee_idx"),
            models.Index(fields=["tenant", "category"], name="hrm_tkt_tnt_cat_idx"),
            # Backs the default ``-created_at`` ordering on the unfiltered list landing page, the exposed
            # ?priority= filter, and the SLA-policy usage/delete-guard counts (mirrors crm.Case indexes).
            models.Index(fields=["tenant", "-created_at"], name="hrm_tkt_tnt_created_idx"),
            models.Index(fields=["tenant", "priority"], name="hrm_tkt_tnt_priority_idx"),
            models.Index(fields=["tenant", "sla_policy"], name="hrm_tkt_tnt_slapolicy_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.subject}" if self.number else self.subject

    def save(self, *args, **kwargs):
        # Stamp the SLA due timestamps once, from the policy's per-priority targets, anchored at
        # creation time (each computed independently while still blank — mirrors crm.Case.save()).
        if self.sla_policy_id and (self.first_response_due is None or self.resolution_due is None):
            anchor = self.created_at or timezone.now()
            resp_h, res_h = self.sla_policy.targets_for(self.priority)
            if resp_h and self.first_response_due is None:
                self.first_response_due = anchor + timedelta(hours=resp_h)
            if res_h and self.resolution_due is None:
                self.resolution_due = anchor + timedelta(hours=res_h)
        return super().save(*args, **kwargs)

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def first_response_breached(self):
        """Open, past the first-response deadline, and no agent has responded yet."""
        return bool(self.first_response_due and self.first_responded_at is None
                    and self.is_open and self.first_response_due < timezone.now())

    @property
    def resolution_breached(self):
        """Open and past the resolution deadline."""
        return bool(self.resolution_due and self.is_open and self.resolution_due < timezone.now())

    @property
    def is_breached(self):
        return self.first_response_breached or self.resolution_breached

    @property
    def sla_state(self):
        """``ok`` / ``at_risk`` / ``breached`` / ``closed`` for the list SLA badge. ``at_risk`` = still
        open, not breached, and within the last 25% of the resolution window."""
        if not self.is_open:
            return "closed"
        if self.is_breached:
            return "breached"
        if self.resolution_due:
            now = timezone.now()
            anchor = self.created_at or now
            total = (self.resolution_due - anchor).total_seconds()
            remaining = (self.resolution_due - now).total_seconds()
            if total > 0 and remaining <= 0.25 * total:
                return "at_risk"
        return "ok"

    @property
    def age_days(self):
        """Whole days from creation to close/resolve/now."""
        end = self.closed_at or self.resolved_at or timezone.now()
        return max(0, (end - (self.created_at or end)).days)
