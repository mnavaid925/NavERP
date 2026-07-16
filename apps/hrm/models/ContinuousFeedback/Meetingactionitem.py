"""HRM 3.20 Continuous Feedback — Meetingactionitem models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class MeetingActionItem(TenantNumbered):
    """An action item captured in a 1:1 (3.20) — mirrors the ``KeyResult``→``Objective`` /
    ``ReviewRating``→``PerformanceReview`` child-row pattern."""

    NUMBER_PREFIX = "MAI"

    STATUS_CHOICES = [
        ("open", "Open"),
        ("done", "Done"),
    ]

    meeting = models.ForeignKey("hrm.OneOnOneMeeting", on_delete=models.CASCADE, related_name="action_items")
    description = models.TextField()
    owner = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="meeting_action_items")
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="open")
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["meeting", "due_date", "description"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "meeting"], name="hrm_mai_tenant_meeting_idx"),
            models.Index(fields=["tenant", "owner"], name="hrm_mai_tenant_owner_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_mai_tenant_status_idx"),
        ]

    @property
    def is_overdue(self):
        """Open + past its due date (derived, mirrors the pattern used across HRM child rows)."""
        return bool(self.status == "open" and self.due_date and self.due_date < timezone.now().date())

    def __str__(self):
        return f"{self.number} · {self.description[:40]}"
