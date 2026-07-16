"""HRM 3.2 Organizational Structure — Costcenter models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class CostCenterProfile(TenantOwned):
    """HRM companion to ``core.OrgUnit(kind="cost_center")`` (3.2). Adds the budget owner, annual
    budget and code core cannot hold. The CC node + its parent roll-up hierarchy live on OrgUnit;
    budget-vs-actuals reporting (against payroll spend) waits on the Accounting module."""

    org_unit = models.OneToOneField("core.OrgUnit", on_delete=models.CASCADE, related_name="cost_center_profile")
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    owner = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="owned_cost_centers")
    budget_annual = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budget_year = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["org_unit__name"]
        unique_together = ("tenant", "org_unit")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_cc_tenant_active_idx"),
            models.Index(fields=["tenant", "owner"], name="hrm_cc_tenant_owner_idx"),
        ]

    def clean(self):
        super().clean()
        # Defense-in-depth (see DepartmentProfile.clean): the form queryset is the primary guard;
        # the tenant branch fires only on direct model.save() once tenant is set.
        if self.org_unit_id:
            if self.org_unit.kind != "cost_center":
                raise ValidationError({"org_unit": "Linked unit must be a Cost Center."})
            if self.tenant_id and self.org_unit.tenant_id != self.tenant_id:
                raise ValidationError({"org_unit": "Cost Center belongs to another tenant."})

    def __str__(self):
        return f"{self.org_unit.name} ({self.code})" if self.code else self.org_unit.name
