"""HRM 3.2 Organizational Structure — Department forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    DepartmentProfile,
    EmployeeProfile,
)


class DepartmentProfileForm(TenantModelForm):
    class Meta:
        model = DepartmentProfile
        fields = ["org_unit", "code", "description", "head", "cost_center", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            # Only department OrgUnits that don't already have a profile (plus this row's own).
            self.fields["org_unit"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="department")
                .filter(Q(department_profile__isnull=True) | Q(pk=self.instance.org_unit_id))
                .order_by("name"))
            self.fields["head"].queryset = (
                EmployeeProfile.objects.filter(tenant=self.tenant)
                .select_related("party").order_by("party__name"))
            self.fields["cost_center"].queryset = (
                OrgUnit.objects.filter(tenant=self.tenant, kind="cost_center").order_by("name"))
