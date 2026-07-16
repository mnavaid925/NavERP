"""HRM 3.40 Workforce Planning — Workforceplan models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


# ---------------------------------------------------------------------------
# 3.40 Workforce Planning — the demand/supply/gap planning layer. A WorkforcePlan
# is a planning cycle for an org unit; its lines hold the per-department current vs
# planned headcount (gap + budget impact are COMPUTED); scenarios are signed what-if
# deltas on top of a plan; EmployeeSkill is the skills inventory that powers Supply
# Analysis. Derived gap-analysis + analytics views need no tables of their own.
#
# CONFIDENTIAL: headcount plans include RESTRUCTURING and REDUCTION lines — every
# plan/line/scenario view is @tenant_admin_required. EmployeeSkill is the exception:
# it is own-vs-admin self-service (an employee curates their own skills).
#
# NOTE (seeder): WorkforcePlanLine.org_unit / .designation are SET_NULL, and nothing
# here PROTECTs a master the seeder flushes — so no _seed_tenant teardown entry is
# needed (unlike 3.38's SuccessionPlan.critical_role, which is PROTECT).
# ---------------------------------------------------------------------------
class WorkforcePlan(TenantNumbered):
    """A workforce planning cycle (``WFP-#####``) for an org unit (or the whole company). The four
    totals are COMPUTED from its lines and are ANNOTATION-AWARE — the list view annotates them so
    rendering N plans doesn't fire 4N aggregate queries."""

    NUMBER_PREFIX = "WFP"

    PLAN_TYPE_CHOICES = [
        ("annual", "Annual"),
        ("project", "Project"),
        ("restructuring", "Restructuring"),
        ("custom", "Custom"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("approved", "Approved"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=150)
    org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_workforce_plans",
                                 help_text="Blank = the whole organization.")
    plan_type = models.CharField(max_length=15, choices=PLAN_TYPE_CHOICES, default="annual")
    period_start = models.DateField()
    period_end = models.DateField()
    growth_assumption_percent = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True,
        help_text="Business-growth assumption driving the demand forecast, e.g. 12.50 = +12.5%.")
    owner = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="workforce_plans_owned")
    currency = models.ForeignKey("accounting.Currency", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_workforce_plans")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"), ("tenant", "name"))
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_wfp_tnt_status_idx"),
            models.Index(fields=["tenant", "plan_type"], name="hrm_wfp_tnt_type_idx"),
            models.Index(fields=["tenant", "-created_at"], name="hrm_wfp_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}" if self.number else self.name

    # ---- Totals: COMPUTED from the lines, annotation-aware (see workforceplan_list) ----
    @property
    def total_current_headcount(self):
        annotated = getattr(self, "_total_current", None)
        if annotated is not None:
            return annotated
        return self.lines.aggregate(v=Sum("current_headcount"))["v"] or 0

    @property
    def total_planned_headcount(self):
        annotated = getattr(self, "_total_planned", None)
        if annotated is not None:
            return annotated
        return self.lines.aggregate(v=Sum("planned_headcount"))["v"] or 0

    @property
    def total_gap(self):
        """Net headcount change across the plan (negative = a net reduction)."""
        return self.total_planned_headcount - self.total_current_headcount

    @property
    def total_budget_impact(self):
        """Sum of each line's budget impact. Computed in Python off the (few) lines rather than in SQL,
        because a line only contributes when BOTH its gap and its avg_annual_cost are set."""
        total = Decimal("0")
        for line in self.lines.all():
            impact = line.budget_impact
            if impact is not None:
                total += impact
        return total
