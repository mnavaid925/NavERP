"""HRM 3.19 Performance Review — Reviewcycle models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class ReviewCycle(TenantOwned):
    """A named annual/half-yearly/quarterly appraisal cycle + a phase machine (3.19.1).
    Small per-tenant catalog identified by ``name`` (not auto-numbered, same pattern as
    ``GoalPeriod``/``JobGrade``). Optionally aligned to a 3.18 ``GoalPeriod`` so a review's
    goal section reuses the OKR cycle window."""

    CYCLE_TYPE_CHOICES = [
        ("annual", "Annual"),
        ("half_yearly", "Half-Yearly"),
        ("quarterly", "Quarterly"),
        ("custom", "Custom"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("self_assessment", "Self-Assessment"),
        ("manager_review", "Manager Review"),
        ("calibration", "Calibration"),
        ("released", "Results Released"),
        ("closed", "Closed"),
    ]
    # Phase order for reviewcycle_advance_phase (no magic-string math duplicated in the view).
    PHASE_ORDER = ("draft", "self_assessment", "manager_review", "calibration", "released", "closed")

    name = models.CharField(max_length=100, help_text='e.g. "H1 2026 Performance Review".')
    cycle_type = models.CharField(max_length=15, choices=CYCLE_TYPE_CHOICES, default="annual")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft",
                              help_text="Phase machine — gates which review actions are open. Advanced via the workflow action.")
    self_review_start = models.DateField(null=True, blank=True)
    self_review_end = models.DateField(null=True, blank=True)
    manager_review_start = models.DateField(null=True, blank=True)
    manager_review_end = models.DateField(null=True, blank=True)
    calibration_date = models.DateField(null=True, blank=True)
    results_release_date = models.DateField(null=True, blank=True)
    goal_period = models.ForeignKey("hrm.GoalPeriod", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="review_cycles",
                                    help_text="Aligns the review to a 3.18 OKR cycle (the goal-review section reads its Objectives).")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-self_review_start", "name"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_rc_tenant_status_idx"),
        ]

    def clean(self):
        if self.self_review_start and self.self_review_end and self.self_review_end <= self.self_review_start:
            raise ValidationError({"self_review_end": "Self-review end must be after its start."})
        if self.manager_review_start and self.manager_review_end and self.manager_review_end <= self.manager_review_start:
            raise ValidationError({"manager_review_end": "Manager-review end must be after its start."})
        if (self.manager_review_start and self.self_review_end
                and self.manager_review_start < self.self_review_end):
            raise ValidationError(
                {"manager_review_start": "Manager review shouldn't start before self-assessment closes."})

    @property
    def review_count(self):
        return self.reviews.count()

    def __str__(self):
        return f"{self.name} ({self.get_cycle_type_display()})"
