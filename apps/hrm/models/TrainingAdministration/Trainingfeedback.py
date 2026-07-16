"""HRM 3.24 Training Administration — Trainingfeedback models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class TrainingFeedback(TenantOwned):
    """A post-training (Kirkpatrick Level-1 "reaction") evaluation for one attendance record (3.24
    Training Feedback). One per attendance (unique_together). ``is_anonymous`` masks the attendee on
    read for non-admins (clones the 3.20 ``Feedback.is_anonymous`` pattern)."""

    attendance = models.ForeignKey("hrm.TrainingAttendance", on_delete=models.CASCADE, related_name="feedback")
    overall_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    content_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    trainer_rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    would_recommend = models.BooleanField(default=True)
    comments = models.TextField(blank=True)
    is_anonymous = models.BooleanField(default=False, help_text="Hide the attendee's identity on read (non-admins).")

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "attendance")

    @property
    def giver_anonymized(self):
        """Mirrors ``Feedback.giver_anonymized`` — the read-render mask flag (one place to change)."""
        return self.is_anonymous

    def __str__(self):
        return f"Feedback · {self.attendance}" if self.attendance_id else "Feedback"
