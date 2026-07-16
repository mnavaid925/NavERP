"""HRM 3.18 Goal Setting — Goalperiod models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403
from apps.hrm.models.GoalSetting._helpers import _clamp_pct
from apps.hrm.models.GoalSetting._helpers import _clamp_pct


class GoalPeriod(TenantOwned):
    """A named quarterly/half-yearly/annual OKR cycle every ``Objective`` is scoped to
    (3.18.4 Goal Timeline). Small per-tenant catalog identified by ``name`` — not
    auto-numbered, same pattern as ``hrm.JobGrade``. "Current" is simply
    ``status="active"`` (no second is_current source of truth)."""

    PERIOD_TYPE_CHOICES = [
        ("quarterly", "Quarterly"),
        ("half_yearly", "Half-Yearly"),
        ("annual", "Annual"),
        ("custom", "Custom"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("closed", "Closed"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=100, help_text='e.g. "Q3 2026".')
    period_type = models.CharField(max_length=15, choices=PERIOD_TYPE_CHOICES, default="quarterly")
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date"]
        unique_together = ("tenant", "name")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_gp_tenant_status_idx"),
        ]

    def clean(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError({"end_date": "End date must be after the start date."})

    @property
    def objective_count(self):
        # A view's list uses an annotated ``num_objectives`` (O(1)); this property is for
        # the detail page where the objectives are already loaded/prefetched.
        return self.objectives.count()

    @property
    def avg_progress_pct(self):
        """Simple mean of the period's objectives' (already-derived) progress. ``progress_pct``
        is not a DB column, so this is computed in Python — the detail view prefetches
        ``objectives__key_results`` to keep it a bounded number of queries."""
        objs = list(self.objectives.all())
        if not objs:
            return ZERO
        total = sum((o.progress_pct for o in objs), ZERO)
        return _clamp_pct(total / Decimal(len(objs)))

    def __str__(self):
        return f"{self.name} ({self.get_period_type_display()})"
