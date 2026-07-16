"""HRM 3.38 Talent Management & Succession — Successioncandidate models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class SuccessionCandidate(TenantOwned):
    """A ranked successor on a SuccessionPlan's bench (an inline child, like TravelBooking under a trip)."""

    READINESS_CHOICES = [
        ("ready_now", "Ready Now"),
        ("ready_1_2y", "Ready in 1-2 Years"),
        ("ready_3_5y", "Ready in 3-5 Years"),
        ("development_needed", "Development Needed"),
    ]

    plan = models.ForeignKey("hrm.SuccessionPlan", on_delete=models.CASCADE, related_name="candidates")
    candidate = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE,
                                  related_name="succession_candidacies")
    readiness = models.CharField(max_length=20, choices=READINESS_CHOICES, default="development_needed")
    rank_order = models.PositiveSmallIntegerField(default=1)
    development_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["rank_order", "id"]
        unique_together = ("tenant", "plan", "candidate")
        indexes = [
            models.Index(fields=["tenant", "plan"], name="hrm_sc_tnt_plan_idx"),
            models.Index(fields=["tenant", "readiness"], name="hrm_sc_tnt_readiness_idx"),
        ]

    def __str__(self):
        return f"{self.candidate} ({self.get_readiness_display()})" if self.candidate_id else "Successor"
