"""HRM 3.2 Organizational Structure — Costcenter forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    CostCenterProfile,
    EmployeeProfile,
)


class CostCenterProfileForm(TenantModelForm):
    class Meta:
        model = CostCenterProfile
        fields = ["org_unit", "code", "description", "owner", "budget_annual", "budget_year",
                  "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["org_unit"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="cost_center")
                .filter(Q(cost_center_profile__isnull=True) | Q(pk=self.instance.org_unit_id))
                .order_by("name"))
            self.fields["owner"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant)
                .select_related("party").order_by("party__name"))
