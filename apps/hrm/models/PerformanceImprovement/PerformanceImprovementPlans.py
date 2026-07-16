"""HRM 3.21 Performance Improvement — PerformanceImprovementPlans models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.21 Performance Improvement — the corrective-action / disciplinary layer and
# the FOURTH & FINAL Performance-Management sub-module (3.18 Goal Setting →
# 3.19 Performance Review → 3.20 Continuous Feedback → 3.21). Structured
# Performance Improvement Plans (with an HR-approval workflow), progressive
# disciplinary warning letters, and manager-only coaching logs — the most
# sensitive HRM records, so CONFIDENTIALITY is the design crux. Reuses the
# spine + already-built HRM models (NavERP-ERD.md): every person is an
# ``EmployeeProfile``; a PIP optionally cites the 3.19 ``PerformanceReview``
# that triggered it. Adds ONLY these 4 tables — no new core-spine entity,
# posts no GL. Confidentiality CLONES 3.19/3.20 field-for-field:
# ``_can_view_pip``/``_visible_pips_q`` mirror ``_can_view_review`` (subject/
# manager/admin, no team/public tier); ``CoachingNote`` clones the
# ``OneOnOneMeeting.manager_private_notes`` read-gate at the WHOLE-model level
# (coach/admin only — the coached employee is NEVER a viewer: the strictest
# gate in the cluster).
# ---------------------------------------------------------------------------
class PerformanceImprovementPlan(TenantNumbered):
    """A corrective-action plan (3.21) — subject + owning manager, an HR-approval workflow, structured
    issue/standards/goals/support/measurement sections, a 30/60/90-day window (extendable), and a
    close-with-outcome step. CONFIDENTIAL — visible only to the subject, the manager, or a tenant admin
    (clones the 3.19 ``PerformanceReview`` confidentiality). Optionally cites the ``PerformanceReview``
    that triggered it."""

    NUMBER_PREFIX = "PIP"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending_hr_approval", "Pending HR Approval"),
        ("active", "Active"),
        ("closed", "Closed"),
    ]
    OUTCOME_CHOICES = [
        ("successful", "Successful"),
        ("extended", "Extended"),
        ("failed", "Failed"),
        ("terminated", "Terminated"),
    ]

    subject = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="pips_as_subject",
                                help_text="The employee on the plan.")
    manager = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="pips_as_manager",
                                help_text="Who owns/drives the plan (stored explicitly — may differ from the reporting line if escalated).")
    triggering_review = models.ForeignKey("hrm.PerformanceReview", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="triggered_pips",
                                          help_text="Optional 3.19 review that prompted this plan.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft",
                              help_text="Workflow — HR approves a draft before it goes active; changed only via the workflow actions.")
    outcome = models.CharField(max_length=15, choices=OUTCOME_CHOICES, blank=True,
                               help_text="Set only when the plan is closed (via the close action), never on the form.")
    outcome_date = models.DateField(null=True, blank=True)
    outcome_notes = models.TextField(blank=True)
    performance_issue = models.TextField(help_text="The specific performance gap (corrective, not vague criticism).")
    expected_standards = models.TextField()
    improvement_goals = models.TextField(help_text="The SMART expectations the employee must meet.")
    support_provided = models.TextField(blank=True, help_text="Training/coaching/resources the org commits to.")
    measurement_criteria = models.TextField(help_text="How success is judged.")
    start_date = models.DateField()
    end_date = models.DateField()
    extended_end_date = models.DateField(null=True, blank=True, help_text="Set by the extend action.")
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    acknowledged_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="pips_acknowledged", editable=False)
    hr_approved_at = models.DateTimeField(null=True, blank=True, editable=False)
    hr_approved_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name="pips_hr_approved", editable=False)

    class Meta:
        ordering = ["-start_date", "number"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_pip_tenant_status_idx"),
            models.Index(fields=["tenant", "subject"], name="hrm_pip_tenant_subject_idx"),
            models.Index(fields=["tenant", "manager"], name="hrm_pip_tenant_manager_idx"),
        ]

    def clean(self):
        if self.subject_id and self.manager_id and self.subject_id == self.manager_id:
            raise ValidationError({"manager": "The manager can't be the plan's subject."})
        if self.status == "closed" and not self.outcome:
            raise ValidationError({"outcome": "A closed plan must record an outcome."})
        if self.outcome and self.status != "closed":
            raise ValidationError({"outcome": "An outcome can only be set on a closed plan."})
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "End date must be after the start date."})
        if self.extended_end_date and self.end_date and self.extended_end_date <= self.end_date:
            raise ValidationError({"extended_end_date": "The extended end date must be after the original end date."})

    @property
    def effective_end_date(self):
        """The date the plan actually runs to — the extension if set, else the original end."""
        return self.extended_end_date or self.end_date

    @property
    def checkin_count(self):
        return self.checkins.count()

    def __str__(self):
        return f"{self.number} · {self.subject.party.name}" if self.subject_id else self.number
