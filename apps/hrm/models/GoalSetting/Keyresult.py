"""HRM 3.18 Goal Setting — Keyresult models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.GoalSetting._helpers import _HEALTH_LABELS, _clamp_pct, _pace_health
from apps.hrm.models.GoalSetting._helpers import _HEALTH_LABELS, _clamp_pct, _pace_health


class KeyResult(TenantNumbered):
    """The measurable "KR" under an ``Objective`` (3.18.1/3.18.3/3.18.5). ``metric_type``
    folds the Viva Goals/Perdoo/Profit.co KR-type distinction into one CharField.
    ``progress_pct``/``health_status`` are derived, never stored."""

    NUMBER_PREFIX = "KR"

    METRIC_TYPE_CHOICES = [
        ("numeric", "Numeric"),
        ("percentage", "Percentage"),
        ("currency", "Currency"),
        ("boolean", "Boolean"),
        ("milestone", "Milestone"),
    ]
    STATUS_CHOICES = [
        ("not_started", "Not Started"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    _METRIC_TYPES = ("numeric", "percentage", "currency")

    objective = models.ForeignKey("hrm.Objective", on_delete=models.CASCADE, related_name="key_results")
    title = models.CharField(max_length=255)
    metric_type = models.CharField(max_length=15, choices=METRIC_TYPE_CHOICES, default="numeric")
    start_value = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True,
                                      help_text="Baseline value (nullable for boolean/milestone KRs).")
    target_value = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    current_value = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True,
                                        help_text="Advanced by GoalCheckIn.save(); also directly editable on the KR form.")
    is_milestone_event = models.BooleanField(default=False,
                                             help_text="For milestone-type KRs: progress is driven by discrete "
                                                       "check-in milestone events rather than a continuous value.")
    unit = models.CharField(max_length=30, blank=True, help_text='Free text, e.g. "%", "$", "signups".')
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                 validators=[MinValueValidator(0), MaxValueValidator(100)],
                                 help_text="Weight among sibling KeyResults under the same Objective "
                                           "(equal-split by default, overridable).")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="not_started")

    class Meta:
        ordering = ["objective", "-weight", "title"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "objective"], name="hrm_kr_tenant_objective_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_kr_tenant_status_idx"),
        ]

    def clean(self):
        if self.metric_type in self._METRIC_TYPES and self.target_value is None:
            raise ValidationError({"target_value": "A numeric/percentage/currency key result needs a target value."})
        if self.weight is not None and self.weight < 0:
            raise ValidationError({"weight": "Weight cannot be negative."})

    @property
    def progress_pct(self):
        """Derived completion %. Numeric-family KRs interpolate start→current→target;
        boolean is 0/100; milestone falls back to completion status (step-weighted
        milestone sub-tracking is deferred)."""
        mt = self.metric_type
        if mt in self._METRIC_TYPES:
            if self.target_value is None:
                return ZERO
            start = self.start_value if self.start_value is not None else ZERO
            current = self.current_value if self.current_value is not None else start
            denom = self.target_value - start
            if denom == 0:
                return Decimal("100") if current >= self.target_value else ZERO
            return _clamp_pct((current - start) / denom * Decimal("100"))
        if mt == "boolean":
            if self.status == "completed":
                return Decimal("100")
            return Decimal("100") if (self.current_value or ZERO) else ZERO
        # milestone: completion-driven fallback (no milestone_target_count field this pass).
        return Decimal("100") if self.status == "completed" else ZERO

    @property
    def health_status(self):
        # Uses the parent objective's period window; views set kr.objective / select_related
        # objective__goal_period so this stays query-free at render time.
        period = self.objective.goal_period if self.objective_id else None
        start = period.start_date if period else None
        end = period.end_date if period else None
        return _pace_health(self.progress_pct, start, end, completed=(self.status == "completed"))

    @property
    def health_status_display(self):
        return _HEALTH_LABELS.get(self.health_status, self.health_status)

    def __str__(self):
        return f"{self.number} · {self.title} ({self.get_metric_type_display()})"
