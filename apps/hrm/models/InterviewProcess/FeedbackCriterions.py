"""HRM 3.7 Interview Process — FeedbackCriterions models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class FeedbackCriterion(TenantOwned):
    """A per-competency rating line on an ``InterviewFeedback`` scorecard (3.7). Managed inline on the
    feedback detail (add/remove POSTs) — no standalone pages. ``rating`` is 1–5 (guarded in
    ``clean()`` and at the form/view layer)."""

    feedback = models.ForeignKey("hrm.InterviewFeedback", on_delete=models.CASCADE, related_name="criteria")
    criterion_name = models.CharField(max_length=150)
    rating = models.PositiveSmallIntegerField(help_text="1 (poor) – 5 (excellent).")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["pk"]
        indexes = [
            models.Index(fields=["tenant", "feedback"], name="hrm_fcrit_tenant_fb_idx"),
        ]

    def clean(self):
        super().clean()
        if self.rating is not None and not (1 <= self.rating <= 5):
            raise ValidationError({"rating": "Rating must be between 1 and 5."})

    def __str__(self):
        return f"{self.criterion_name}: {self.rating}/5"
