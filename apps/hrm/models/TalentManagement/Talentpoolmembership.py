"""HRM 3.38 Talent Management & Succession — Talentpoolmembership models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.TalentManagement._helpers import _NINE_BOX_LABELS, _rating_band
from apps.hrm.models.TalentManagement._helpers import _NINE_BOX_LABELS, _rating_band


class TalentPoolMembership(TenantOwned):
    """One employee's place in a talent pool, carrying their 9-box coordinates + retention posture.

    The ratings come from the linked 3.19 ``PerformanceReview`` (``effective_rating`` = the performance axis,
    ``potential_rating`` = the potential axis); the two Decimal columns here are optional OVERRIDES a talent
    reviewer can set when calibrating. ``nine_box_quadrant`` is COMPUTED from whichever applies — never stored."""

    STATUS_CHOICES = [
        ("active", "Active"),
        ("exited", "Exited"),
        ("promoted", "Promoted"),
    ]
    FLIGHT_RISK_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    pool = models.ForeignKey("hrm.TalentPool", on_delete=models.CASCADE, related_name="memberships")
    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE,
                                 related_name="talent_memberships")
    joined_on = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    review = models.ForeignKey("hrm.PerformanceReview", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="talent_memberships",
                               help_text="Source review for the 9-box ratings (optional).")
    performance_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("5"))],
        help_text="Overrides the linked review's effective rating (1-5).")
    potential_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("1")), MaxValueValidator(Decimal("5"))],
        help_text="Overrides the linked review's potential rating (1-5).")
    flight_risk = models.CharField(max_length=10, choices=FLIGHT_RISK_CHOICES, default="low")
    retention_action_plan = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "pool", "employee")
        indexes = [
            models.Index(fields=["tenant", "pool"], name="hrm_tpm_tnt_pool_idx"),
            models.Index(fields=["tenant", "employee"], name="hrm_tpm_tnt_emp_idx"),
            models.Index(fields=["tenant", "flight_risk"], name="hrm_tpm_tnt_risk_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_tpm_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.employee} in {self.pool}" if self.employee_id and self.pool_id else "Talent membership"

    # ---- 9-box (computed, NEVER stored) ----
    @property
    def effective_performance(self):
        """The override if set, else the linked review's effective_rating, else None."""
        if self.performance_rating is not None:
            return self.performance_rating
        return self.review.effective_rating if self.review_id else None

    @property
    def effective_potential(self):
        if self.potential_rating is not None:
            return self.potential_rating
        return self.review.potential_rating if self.review_id else None

    @property
    def performance_band(self):
        return _rating_band(self.effective_performance)

    @property
    def potential_band(self):
        return _rating_band(self.effective_potential)

    @property
    def nine_box_quadrant(self):
        """The standard 9-box label (Star / Core Player / Underperformer / …), or None when either axis
        has no rating yet."""
        perf, pot = self.performance_band, self.potential_band
        if perf is None or pot is None:
            return None
        return _NINE_BOX_LABELS.get((perf, pot))
