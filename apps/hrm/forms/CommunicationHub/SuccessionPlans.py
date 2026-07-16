"""HRM 3.27 Communication Hub — SuccessionPlans forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    EmployeeProfile,
    SuccessionPlan,
)


class SuccessionPlanForm(TenantModelForm):
    class Meta:
        model = SuccessionPlan
        fields = ["critical_role", "department", "incumbent", "vacancy_risk", "status", "review_date", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "critical_role" in self.fields:
                self.fields["critical_role"].queryset = (
                    Designation.objects.filter(tenant=self.tenant).order_by("name"))
            if "incumbent" in self.fields:
                self.fields["incumbent"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
                    .order_by("party__name"))
            if "department" in self.fields:
                self.fields["department"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
