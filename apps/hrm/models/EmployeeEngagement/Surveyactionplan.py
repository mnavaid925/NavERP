"""HRM 3.41 Employee Engagement & Wellbeing — Surveyactionplan models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.41 Employee Engagement & Wellbeing — an EXTENSION pass that reuses 3.27's
# Survey/SurveyResponse (pulse/eNPS delivery) and Announcement (values/mission
# content) rather than rebuilding them. It adds only the real gaps:
#   * SurveyActionPlan — turns a closed survey's findings into a tracked initiative
#     (the Culture Amp / Qualtrics "close the loop" differentiator).
#   * WellbeingProgram — ONE catalog table, program_type-discriminated, covering
#     Wellbeing Programs / Employee Assistance / Culture & Values / Social Connect.
#   * WellbeingParticipation — the RSVP/attendance/points child of a program.
#   * FlexibleWorkArrangement — a Work-Life-Balance request, a structural clone of
#     3.35 TravelRequest (reuses _hr_request_* verbatim).
#
# CONFIDENTIALITY: EAP/counseling data is highly sensitive. WellbeingProgram forces
# is_confidential=True for program_type="eap_counseling" in save() (not a form
# default — a tampered POST can't turn it off), and a confidential program's roster
# is AGGREGATE-ONLY for every viewer including admins (see wellbeingprogram_detail).
# ---------------------------------------------------------------------------
class SurveyActionPlan(TenantNumbered):
    """A tracked follow-up initiative born from a (typically closed) 3.27 Survey — the "close the loop"
    step that turns low-scoring drivers into an owned, dated action. ``completed_at`` is auto-managed in
    ``save()``; ``is_overdue`` is pure arithmetic (safe to render unannotated)."""

    NUMBER_PREFIX = "ACTP"

    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    _CLOSED_STATUSES = ("completed", "cancelled")

    survey = models.ForeignKey("hrm.Survey", on_delete=models.CASCADE, related_name="action_plans",
                               help_text="The survey this plan responds to (typically a closed one).")
    title = models.CharField(max_length=255)
    focus_area = models.CharField(max_length=255,
                                  help_text="The low-scoring driver/theme this plan addresses.")
    owner = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT,
                              related_name="owned_action_plans",
                              help_text="The accountable owner — may be a manager, not necessarily an admin.")
    department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                   limit_choices_to={"kind": "department"},
                                   related_name="survey_action_plans")
    description = models.TextField()
    related_objective = models.ForeignKey("hrm.Objective", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="survey_action_plans")
    target_date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="open")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-target_date", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_actp_tenant_status_idx"),
            models.Index(fields=["tenant", "survey"], name="hrm_actp_tenant_survey_idx"),
            models.Index(fields=["tenant", "owner"], name="hrm_actp_tenant_owner_idx"),
            models.Index(fields=["tenant", "department"], name="hrm_actp_tenant_dept_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}" if self.number else self.title

    def save(self, *args, **kwargs):
        # Auto-manage completed_at symmetrically: stamp it when the plan first closes, clear it if the
        # plan is later reopened. No separate "close" action needed.
        if self.status in self._CLOSED_STATUSES:
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        return super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        return self.status in ("open", "in_progress") and self.target_date < timezone.localdate()
