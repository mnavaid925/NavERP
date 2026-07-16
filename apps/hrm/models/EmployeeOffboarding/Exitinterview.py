"""HRM 3.4 Employee Offboarding — Exitinterview models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.EmployeeOffboarding.Separationcase import SeparationCase
from apps.hrm.models.EmployeeOffboarding._helpers import _RATING_VALIDATORS
from apps.hrm.models.EmployeeOffboarding.Separationcase import SeparationCase
from apps.hrm.models.EmployeeOffboarding._helpers import _RATING_VALIDATORS


class ExitInterview(TenantNumbered):
    """A structured exit interview tied to a ``SeparationCase`` (3.4). One per case (form-guarded —
    not a DB constraint, so a skipped/no-show one can be superseded). Eight 1–5 Likert ratings + a
    coded ``primary_reason`` feed attrition insight. ``status``/``conducted_at`` are workflow-owned
    (set by the complete/skip actions, never on the form)."""

    NUMBER_PREFIX = "EI"

    MODE_CHOICES = [
        ("in_person", "In Person"),
        ("video", "Video Call"),
        ("phone", "Phone"),
        ("form", "Self-Service Form"),
    ]
    EI_STATUS_CHOICES = [
        ("scheduled", "Scheduled"),
        ("completed", "Completed"),
        ("skipped", "Skipped"),
        ("no_show", "No Show"),
    ]
    # (field, label) pairs — drives the form fieldset and the detail rating display.
    RATING_FIELDS = [
        ("rating_job_satisfaction", "Job Satisfaction"),
        ("rating_management", "Management"),
        ("rating_compensation", "Compensation"),
        ("rating_work_environment", "Work Environment"),
        ("rating_growth_opportunities", "Growth Opportunities"),
        ("rating_work_life_balance", "Work-Life Balance"),
        ("rating_culture", "Culture"),
        ("rating_overall", "Overall"),
    ]

    case = models.ForeignKey("hrm.SeparationCase", on_delete=models.CASCADE, related_name="exit_interviews")
    interviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="hrm_exit_interviews_conducted")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    conducted_at = models.DateTimeField(null=True, blank=True, editable=False)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="in_person")
    status = models.CharField(max_length=20, choices=EI_STATUS_CHOICES, default="scheduled", editable=False)
    rating_job_satisfaction = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_management = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_compensation = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_work_environment = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_growth_opportunities = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_work_life_balance = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_culture = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    rating_overall = models.SmallIntegerField(null=True, blank=True, validators=_RATING_VALIDATORS)
    primary_reason = models.CharField(max_length=30, choices=SeparationCase.EXIT_REASON_CHOICES, blank=True)
    would_recommend = models.BooleanField(null=True, blank=True)
    would_rejoin = models.BooleanField(null=True, blank=True)
    what_went_well = models.TextField(blank=True)
    what_to_improve = models.TextField(blank=True)
    additional_comments = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "case"], name="hrm_ei_tenant_case_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_ei_tenant_status_idx"),
            models.Index(fields=["tenant", "mode"], name="hrm_ei_tenant_mode_idx"),
        ]

    @property
    def average_rating(self):
        """Mean of the answered Likert ratings (1 decimal), or None if none answered."""
        vals = [getattr(self, f) for f, _ in self.RATING_FIELDS if getattr(self, f) is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    def __str__(self):
        name = self.case.employee.name if self.case_id and self.case.employee_id else "—"
        return f"{self.number} · Exit Interview for {name}"
