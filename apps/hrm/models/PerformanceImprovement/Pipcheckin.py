"""HRM 3.21 Performance Improvement — Pipcheckin models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class PIPCheckIn(TenantNumbered):
    """A scheduled review-checkpoint on a PIP (3.21) — mirrors the ``ReviewRating``→``PerformanceReview``
    / ``MeetingActionItem``→``OneOnOneMeeting`` child pattern. Inherits the parent PIP's confidentiality
    (no independent gate — the view checks ``_can_view_pip(request, checkin.pip)``)."""

    NUMBER_PREFIX = "PCI"

    RATING_CHOICES = [
        ("on_track", "On Track"),
        ("at_risk", "At Risk"),
        ("off_track", "Off Track"),
    ]

    pip = models.ForeignKey("hrm.PerformanceImprovementPlan", on_delete=models.CASCADE, related_name="checkins")
    checkin_date = models.DateField()
    completed_at = models.DateTimeField(null=True, blank=True, editable=False)
    progress_notes = models.TextField(blank=True)
    progress_rating = models.CharField(max_length=10, choices=RATING_CHOICES, default="on_track")

    class Meta:
        ordering = ["pip", "checkin_date"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "pip"], name="hrm_pci_tenant_pip_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.pip.number} ({self.checkin_date})" if self.pip_id else self.number
