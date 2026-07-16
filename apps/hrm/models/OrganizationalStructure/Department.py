"""HRM 3.2 Organizational Structure — Department models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class DepartmentProfile(TenantOwned):
    """HRM companion to ``core.OrgUnit(kind="department")`` (3.2). Adds the HR fields core cannot
    hold — department head, cost-center mapping, mnemonic code — without duplicating the OrgUnit
    node (name/parent/hierarchy stay on OrgUnit). The ``head`` drives future approval chains."""

    org_unit = models.OneToOneField("core.OrgUnit", on_delete=models.CASCADE, related_name="department_profile")
    code = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    head = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.SET_NULL, null=True, blank=True, related_name="headed_departments")
    cost_center = models.ForeignKey(
        "core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="department_cost_mappings", limit_choices_to={"kind": "cost_center"})
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["org_unit__name"]
        unique_together = ("tenant", "org_unit")
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="hrm_dp_tenant_active_idx"),
            models.Index(fields=["tenant", "head"], name="hrm_dp_tenant_head_idx"),
            models.Index(fields=["tenant", "cost_center"], name="hrm_dp_tenant_cc_idx"),
        ]

    def clean(self):
        super().clean()
        # NOTE: the PRIMARY cross-tenant defense is the form's FK queryset scoping (org_unit/
        # cost_center are limited to the active tenant in DepartmentProfileForm). These model-level
        # tenant checks are defense-in-depth for direct ``model.save()`` (admin/shell): the view sets
        # ``tenant`` only AFTER ``form.is_valid()``, so ``tenant_id`` is None during form validation
        # and the tenant branch is skipped then (the queryset guard already covers that path).
        if self.org_unit_id:
            if self.org_unit.kind != "department":
                raise ValidationError({"org_unit": "Linked unit must be a Department."})
            if self.tenant_id and self.org_unit.tenant_id != self.tenant_id:
                raise ValidationError({"org_unit": "Department belongs to another tenant."})
        if self.cost_center_id:
            if self.cost_center.kind != "cost_center":
                raise ValidationError({"cost_center": "Linked unit must be a Cost Center."})
            if self.tenant_id and self.cost_center.tenant_id != self.tenant_id:
                raise ValidationError({"cost_center": "Cost Center belongs to another tenant."})

    def __str__(self):
        return f"{self.org_unit.name} ({self.code})" if self.code else self.org_unit.name
