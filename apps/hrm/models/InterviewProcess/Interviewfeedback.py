"""HRM 3.7 Interview Process — Interviewfeedback models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.InterviewProcess.RECOMMENDATION_CHOICESs import RECOMMENDATION_CHOICES
from apps.hrm.models.InterviewProcess.RECOMMENDATION_CHOICESs import RECOMMENDATION_CHOICES


class InterviewFeedback(TenantNumbered):
    """A structured interview scorecard (3.7) — one per panelist per interview. ``overall_recommendation``
    is the 5-level hire signal; ``is_submitted`` flips via the submit action (enabling anti-anchoring
    blinding — strict queryset-level blinding is deferred). Per-competency ratings live in child
    ``FeedbackCriterion`` rows; averages are annotated/aggregated in the views (no query-in-property)."""

    NUMBER_PREFIX = "IFB"

    interview = models.ForeignKey("hrm.Interview", on_delete=models.CASCADE, related_name="feedback_entries")
    panelist = models.ForeignKey("hrm.InterviewPanelist", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="+")
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="interview_feedback")
    overall_recommendation = models.CharField(max_length=20, choices=RECOMMENDATION_CHOICES, default="maybe")
    summary = models.TextField(blank=True, help_text="Overall impression / key takeaways.")
    is_submitted = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        # ("interview", "panelist") enforces one scorecard per panelist per interview (the docstring
        # contract). On MariaDB/SQLite a UNIQUE index treats NULLs as distinct, so multiple
        # panelist=NULL (unassigned) cards on one interview are still allowed — exactly what we want,
        # and portable (a conditional UniqueConstraint would silently no-op on MariaDB: no partial idx).
        unique_together = [("tenant", "number"), ("interview", "panelist")]
        indexes = [
            models.Index(fields=["tenant", "interview"], name="hrm_ifb_tenant_intv_idx"),
            models.Index(fields=["tenant", "overall_recommendation"], name="hrm_ifb_tenant_reco_idx"),
            models.Index(fields=["tenant", "is_submitted"], name="hrm_ifb_tenant_sub_idx"),
        ]

    def __str__(self):
        reco = self.get_overall_recommendation_display()
        return f"{self.number} · {reco}" if self.number else reco
