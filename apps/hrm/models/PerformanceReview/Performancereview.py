"""HRM 3.19 Performance Review — Performancereview models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.PerformanceReview.REVIEW_TYPE_CHOICESs import REVIEW_TYPE_CHOICES
from apps.hrm.models.PerformanceReview.REVIEW_TYPE_CHOICESs import REVIEW_TYPE_CHOICES


class PerformanceReview(TenantNumbered):
    """The per-instance review row — one per (cycle, subject, reviewer) (3.19.2/3.19.3/3.19.4/3.19.5).
    Self/manager/peer/upward all become rows of this one table. ``overall_rating`` is a derived
    weighted mean of the review's ratings; ``manager_rating``/``calibrated_rating`` are stored
    (pre/post-calibration audit trail)."""

    NUMBER_PREFIX = "RVW"

    REVIEW_TYPE_CHOICES = REVIEW_TYPE_CHOICES
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("shared", "Shared"),
        ("acknowledged", "Acknowledged"),
    ]

    cycle = models.ForeignKey("hrm.ReviewCycle", on_delete=models.PROTECT, related_name="reviews")
    template = models.ForeignKey("hrm.ReviewTemplate", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="reviews")
    subject = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="reviews_received",
                                help_text="The employee being reviewed.")
    reviewer = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="reviews_authored",
                                 help_text="Who fills this instance (== subject for a self review).")
    review_type = models.CharField(max_length=15, choices=REVIEW_TYPE_CHOICES, default="self",
                                   help_text="Denormalized from the template at creation for query convenience.")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    # overall_rating is DERIVED (see the property) — never a stored column.
    manager_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                                         help_text="As-submitted pre-calibration snapshot (manager reviews).")
    calibrated_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                                            help_text="Post-calibration override; downstream comp/promotion reads this.")
    potential_rating = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True,
                                           help_text="9-box potential axis (visualization deferred).")
    strengths = models.TextField(blank=True)
    improvements = models.TextField(blank=True)
    private_notes = models.TextField(blank=True,
                                     help_text="Manager-only — NEVER rendered on the subject-facing view.")
    calibration_notes = models.TextField(blank=True, help_text="Calibration adjustment rationale.")
    is_anonymous = models.BooleanField(default=False,
                                       help_text="Masks the reviewer on the subject-facing view (peer/upward).")
    submitted_at = models.DateTimeField(null=True, blank=True, editable=False)
    shared_at = models.DateTimeField(null=True, blank=True, editable=False)
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    acknowledged_by = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name="reviews_acknowledged", editable=False)

    class Meta:
        ordering = ["-cycle__self_review_start", "subject__party__name"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "cycle"], name="hrm_rvw_tenant_cycle_idx"),
            models.Index(fields=["tenant", "subject"], name="hrm_rvw_tenant_subject_idx"),
            models.Index(fields=["tenant", "reviewer"], name="hrm_rvw_tenant_reviewer_idx"),
            models.Index(fields=["tenant", "review_type"], name="hrm_rvw_tenant_type_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_rvw_tenant_status_idx"),
        ]

    def clean(self):
        if self.review_type == "self" and self.subject_id and self.reviewer_id != self.subject_id:
            raise ValidationError({"reviewer": "A self review must have the subject as the reviewer."})
        if self.review_type != "self" and self.subject_id and self.reviewer_id == self.subject_id:
            raise ValidationError({"reviewer": "A non-self review can't have the subject reviewing themselves."})
        if self.manager_rating is not None and self.review_type != "manager":
            raise ValidationError({"manager_rating": "Manager rating only applies to a manager review."})

    def _ratings(self):
        """Materialize the review's rating lines once per instance (prefetched by detail views)
        so overall_rating/rating_count don't re-query (mirrors Objective._krs())."""
        if not hasattr(self, "_ratings_cache"):
            self._ratings_cache = list(self.ratings.all())
        return self._ratings_cache

    @property
    def overall_rating(self):
        """Weighted mean of the review's ``ReviewRating`` values by weight (simple mean if all
        weights are 0). Returns ``None`` — not 0 — when there are no ratings yet, since a rating
        of 0 is a valid low score and an unrated review should read "Not yet rated"."""
        rows = self._ratings()
        if not rows:
            return None
        total_weight = sum((r.weight for r in rows), ZERO)
        if total_weight > 0:
            acc = sum((r.rating_value * r.weight for r in rows), ZERO)
            return (acc / total_weight).quantize(Decimal("0.01"))
        acc = sum((r.rating_value for r in rows), ZERO)
        return (acc / Decimal(len(rows))).quantize(Decimal("0.01"))

    @property
    def rating_count(self):
        return len(self._ratings())

    @property
    def effective_rating(self):
        """The single value downstream consumers (comp/promotion) read — calibrated overrides the
        derived overall, per Workday's documented pattern."""
        return self.calibrated_rating if self.calibrated_rating is not None else self.overall_rating

    @property
    def goal_period(self):
        """Convenience passthrough to the cycle's aligned OKR period (for the goal-review section)."""
        return self.cycle.goal_period if self.cycle_id else None

    @property
    def reviewer_anonymized(self):
        """True when the reviewer name should be hidden in summary/list views (anonymous peer/upward
        feedback). The detail view additionally un-hides it for the reviewer/admin via ``show_reviewer``."""
        return self.is_anonymous and self.review_type in ("peer", "upward")

    def __str__(self):
        return f"{self.number} · {self.subject.party.name} ({self.get_review_type_display()})"
