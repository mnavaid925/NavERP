"""HRM 3.40 Workforce Planning — Workforcescenario models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class WorkforceScenario(TenantNumbered):
    """A named what-if variant on a WorkforcePlan (``WFS-#####``) — e.g. a hiring freeze or a
    restructuring. The deltas are SIGNED (a reduction scenario carries a negative headcount_delta)."""

    NUMBER_PREFIX = "WFS"

    SCENARIO_TYPE_CHOICES = [
        ("growth", "Growth"),
        ("freeze", "Hiring Freeze"),
        ("restructuring", "Restructuring"),
        ("attrition", "Attrition"),
        ("cost_reduction", "Cost Reduction"),
        ("custom", "Custom"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    plan = models.ForeignKey("hrm.WorkforcePlan", on_delete=models.CASCADE, related_name="scenarios")
    name = models.CharField(max_length=150)
    scenario_type = models.CharField(max_length=20, choices=SCENARIO_TYPE_CHOICES, default="custom")
    affected_org_unit = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="hrm_workforce_scenarios")
    description = models.TextField(blank=True)
    headcount_delta = models.SmallIntegerField(default=0, help_text="Signed: negative = a reduction.")
    cost_delta = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"),
                                     help_text="Signed: negative = a saving.")
    is_baseline = models.BooleanField(default=False)
    is_selected = models.BooleanField(default=False)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("tenant", "number"), ("tenant", "plan", "name"))
        indexes = [
            models.Index(fields=["tenant", "plan"], name="hrm_wfs_tnt_plan_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_wfs_tnt_status_idx"),
            models.Index(fields=["tenant", "scenario_type"], name="hrm_wfs_tnt_type_idx"),
            models.Index(fields=["tenant", "-created_at"], name="hrm_wfs_tnt_created_idx"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}" if self.number else self.name

    @property
    def resulting_headcount(self):
        """The plan's planned headcount with this scenario's delta applied."""
        return self.plan.total_planned_headcount + self.headcount_delta
