"""HRM 3.27 Communication Hub — Survey models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class Survey(TenantNumbered):
    """3.27 admin-authored engagement survey. `questions` is a JSON list of
    {"text", "type": rating|text|single_choice, "options": [...]} — a rating question with a 0-10 scale
    covers the eNPS pattern with no extra schema. Lifecycle draft -> open -> closed; employees respond
    once (SurveyResponse). `is_anonymous` suppresses respondent identity in results (display-layer only —
    the response still stores employee for the respond-once guard)."""

    NUMBER_PREFIX = "SUR"

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("open", "Open"),
        ("closed", "Closed"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    questions = models.JSONField(default=list,
                                 help_text='List of {"text": str, "type": "rating"|"text"|"single_choice", "options": [...]}.')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    is_anonymous = models.BooleanField(default=False)
    opens_at = models.DateField(null=True, blank=True)
    closes_at = models.DateField(null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                               editable=False, related_name="hrm_survey_authored")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_survey_tenant_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.title}" if self.number else self.title


class SurveyResponse(TenantOwned):
    """One employee's answers to a Survey. `answers` is a {question_index: answer} JSON map mirroring
    Survey.questions. `unique_together (survey, employee)` enforces respond-once. Created only via
    views.survey_respond, read only via views.survey_results aggregation — no standalone CRUD (exempt
    from the CRUD-list rule, like PayslipLine / LearningPathItem)."""

    survey = models.ForeignKey("hrm.Survey", on_delete=models.CASCADE, related_name="responses")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="survey_responses")
    answers = models.JSONField(default=dict)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
        unique_together = ("survey", "employee")
        indexes = [
            models.Index(fields=["tenant", "survey"], name="hrm_survresp_tenant_surv_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_survresp_tenant_emp_idx"),
        ]

    def __str__(self):
        return f"{self.survey} · {self.employee}"
