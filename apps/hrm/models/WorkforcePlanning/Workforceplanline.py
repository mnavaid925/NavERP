"""HRM 3.40 Workforce Planning — Workforceplanline models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class WorkforcePlanLine(TenantOwned):
    """One department (optionally narrowed to a designation) inside a WorkforcePlan: its current vs planned
    headcount. ``headcount_gap`` and ``budget_impact`` are COMPUTED, never stored."""

    HIRING_TYPE_CHOICES = [
        ("new_growth", "New Growth"),
        ("replacement", "Replacement"),
        ("attrition_backfill", "Attrition Backfill"),
        ("reduction", "Reduction"),
    ]

    plan = models.ForeignKey("hrm.WorkforcePlan", on_delete=models.CASCADE, related_name="lines")
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_workforce_plan_lines")
    designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name="workforce_plan_lines",
                                    help_text="Blank = a whole-department aggregate.")
    current_headcount = models.PositiveSmallIntegerField(default=0)
    planned_headcount = models.PositiveSmallIntegerField(default=0)
    hiring_type = models.CharField(max_length=20, choices=HIRING_TYPE_CHOICES, default="new_growth")
    avg_annual_cost = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True,
                                          help_text="Fully-loaded average annual cost per head.")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["tenant", "plan"], name="hrm_wfpl_tnt_plan_idx"),
            models.Index(fields=["tenant", "org_unit"], name="hrm_wfpl_tnt_org_idx"),
        ]

    def __str__(self):
        unit = self.org_unit.name if self.org_unit_id else "All"
        return f"{unit}: {self.current_headcount} -> {self.planned_headcount}"

    @property
    def headcount_gap(self):
        """planned − current. Positive = hiring need; negative = a reduction."""
        return self.planned_headcount - self.current_headcount

    @property
    def budget_impact(self):
        """gap × avg_annual_cost — None when no cost is set (so it can't be silently treated as zero)."""
        if self.avg_annual_cost is None:
            return None
        return self.headcount_gap * self.avg_annual_cost
