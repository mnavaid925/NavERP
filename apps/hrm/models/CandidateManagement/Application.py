"""HRM 3.6 Candidate Management — Application models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.CandidateManagement.Candidate import CANDIDATE_SOURCE_CHOICES
from apps.hrm.models.CandidateManagement.REJECTION_REASON_CHOICESs import REJECTION_REASON_CHOICES
from apps.hrm.models.CandidateManagement.Candidate import CANDIDATE_SOURCE_CHOICES
from apps.hrm.models.CandidateManagement.REJECTION_REASON_CHOICESs import REJECTION_REASON_CHOICES


APPLICATION_STAGE_CHOICES = [
    ("applied", "Applied"),
    ("screening", "Screening"),
    ("phone_screen", "Phone Screen"),
    ("assessment", "Assessment / Test"),
    ("interview", "Interview"),
    ("offer", "Offer"),
    ("hired", "Hired"),
    ("rejected", "Rejected"),
    ("withdrawn", "Withdrawn"),
    ("on_hold", "On Hold"),
]


# Terminal stages an application can't be "advanced" out of without an explicit restore.
APPLICATION_TERMINAL_STAGES = ("hired", "rejected", "withdrawn")


class JobApplication(TenantNumbered):
    """A candidate's application to a requisition (3.6) — the recruiting pipeline record. ``stage`` is
    the workflow-owned state machine (set only by the stage-move POST actions, never the form);
    rating/notes are recruiter annotations. Unique per (candidate, requisition) so one person can't
    double-apply to the same opening."""

    NUMBER_PREFIX = "APP"

    candidate = models.ForeignKey("hrm.CandidateProfile", on_delete=models.CASCADE, related_name="applications")
    requisition = models.ForeignKey("hrm.JobRequisition", on_delete=models.CASCADE, related_name="applications")
    stage = models.CharField(max_length=20, choices=APPLICATION_STAGE_CHOICES, default="applied",
                             editable=False)
    source = models.CharField(max_length=20, choices=CANDIDATE_SOURCE_CHOICES, default="careers_page")
    referred_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="referrals")
    cover_letter_text = models.TextField(blank=True)
    cover_letter_file = models.FileField(upload_to="hrm/candidates/covers/%Y/%m/", null=True, blank=True)
    screening_answers = models.JSONField(default=dict, blank=True,
        help_text="Per-requisition screening questions and answers, stored as a {question: answer} map.")
    rating = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Recruiter rating, 1–5.")
    rejection_reason = models.CharField(max_length=30, choices=REJECTION_REASON_CHOICES, blank=True)
    rejection_notes = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    applied_at = models.DateTimeField(auto_now_add=True)
    stage_changed_at = models.DateTimeField(null=True, blank=True, editable=False)
    hired_on = models.DateField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-applied_at"]
        unique_together = ("tenant", "number")
        constraints = [
            models.UniqueConstraint(fields=["candidate", "requisition"], name="hrm_app_cand_req_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "stage"], name="hrm_app_tenant_stage_idx"),
            models.Index(fields=["tenant", "source"], name="hrm_app_tenant_source_idx"),
            models.Index(fields=["tenant", "requisition"], name="hrm_app_tenant_req_idx"),
            models.Index(fields=["tenant", "candidate"], name="hrm_app_tenant_cand_idx"),
            # Supports the default ``-applied_at`` ordering of the application list under the tenant filter.
            models.Index(fields=["tenant", "applied_at"], name="hrm_app_tenant_applied_idx"),
        ]

    def clean(self):
        super().clean()
        if self.rating is not None and not (1 <= self.rating <= 5):
            raise ValidationError({"rating": "Rating must be between 1 and 5."})

    def __str__(self):
        return f"{self.number} · {self.candidate.name} → {self.requisition.title}"
