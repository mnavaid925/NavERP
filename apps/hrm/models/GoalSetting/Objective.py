"""HRM 3.18 Goal Setting — Objective models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.GoalSetting._helpers import _HEALTH_LABELS, _clamp_pct, _pace_health
from apps.hrm.models.GoalSetting._helpers import _HEALTH_LABELS, _clamp_pct, _pace_health


class Objective(TenantNumbered):
    """The "O" in OKR (3.18.1/3.18.2/3.18.3/3.18.4). Owned by an ``EmployeeProfile``,
    scoped to a ``GoalPeriod``, optionally aligned up a cascade via ``parent_objective``
    and tagged to a ``core.OrgUnit`` department. ``progress_pct``/``health_status`` are
    derived from its KeyResults, never stored."""

    NUMBER_PREFIX = "OBJ"

    SCOPE_CHOICES = [
        ("company", "Company"),
        ("department", "Department"),
        ("team", "Team"),
        ("individual", "Individual"),
    ]
    TARGET_TYPE_CHOICES = [
        ("aspirational", "Aspirational"),
        ("committed", "Committed"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("at_risk", "At Risk"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.PROTECT, related_name="objectives",
                              help_text="The goal owner (an EmployeeProfile — never a raw Party/User).")
    goal_period = models.ForeignKey("hrm.GoalPeriod", on_delete=models.PROTECT, related_name="objectives")
    parent_objective = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name="child_objectives",
                                         help_text="Aligns (rolls up into) a parent objective — the cascade link.")
    department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="objectives",
                                   help_text="Department/team scope (a core.OrgUnit); blank for individual goals.")
    scope = models.CharField(max_length=15, choices=SCOPE_CHOICES, default="individual")
    target_type = models.CharField(max_length=15, choices=TARGET_TYPE_CHOICES, default="committed",
                                   help_text="Aspirational (50–70% is a win) vs. committed (100% expected).")
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=100,
                                 validators=[MinValueValidator(0), MaxValueValidator(100)],
                                 help_text="Relative weight among SIBLING objectives under the same parent "
                                           "(for a parent's weighted-children view). NOT used to compute this "
                                           "objective's own progress_pct — that is strictly a KR-weighted rollup.")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    start_date = models.DateField(null=True, blank=True,
                                  help_text="Defaults to the period's start; stored so an objective can start later.")
    due_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-goal_period__start_date", "title"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_obj_tenant_status_idx"),
            models.Index(fields=["tenant", "goal_period"], name="hrm_obj_tenant_period_idx"),
            models.Index(fields=["tenant", "owner"], name="hrm_obj_tenant_owner_idx"),
            models.Index(fields=["tenant", "parent_objective"], name="hrm_obj_tenant_parent_idx"),
            models.Index(fields=["tenant", "department"], name="hrm_obj_tenant_department_idx"),
        ]

    def clean(self):
        # No self-parenting, and no cycle in the alignment chain (cheap bounded walk).
        if self.parent_objective_id and self.pk and self.parent_objective_id == self.pk:
            raise ValidationError({"parent_objective": "An objective cannot align to itself."})
        node, depth = self.parent_objective, 0
        while node is not None and depth < 20:
            if self.pk and node.pk == self.pk:
                raise ValidationError({"parent_objective": "This alignment would create a cycle."})
            node, depth = node.parent_objective, depth + 1

    def _krs(self):
        """Materialize child KeyResults once per instance (prefetched by list/detail views)
        so ``progress_pct``/``health_status``/``key_result_count`` don't re-query."""
        if not hasattr(self, "_krs_cache"):
            self._krs_cache = list(self.key_results.all())
        return self._krs_cache

    @property
    def progress_pct(self):
        """Weighted average of child ``KeyResult.progress_pct`` by ``KeyResult.weight``
        (3.18.3 weighted rollup). Falls back to a simple mean if all weights are 0;
        ``0`` when there are no key results."""
        krs = self._krs()
        if not krs:
            return ZERO
        total_weight = sum((kr.weight for kr in krs), ZERO)
        if total_weight > 0:
            acc = sum((kr.progress_pct * kr.weight for kr in krs), ZERO)
            return _clamp_pct(acc / total_weight)
        acc = sum((kr.progress_pct for kr in krs), ZERO)
        return _clamp_pct(acc / Decimal(len(krs)))

    @property
    def health_status(self):
        start = self.start_date or (self.goal_period.start_date if self.goal_period_id else None)
        end = self.due_date or (self.goal_period.end_date if self.goal_period_id else None)
        return _pace_health(self.progress_pct, start, end, completed=(self.status == "completed"))

    @property
    def health_status_display(self):
        return _HEALTH_LABELS.get(self.health_status, self.health_status)

    @property
    def key_result_count(self):
        return len(self._krs())

    def __str__(self):
        return f"{self.number} · {self.title}"
