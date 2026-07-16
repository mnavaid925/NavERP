"""HRM 3.27 Communication Hub — WorkforcePlanLines forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    WorkforcePlanLine,
)


class WorkforcePlanLineForm(TenantModelForm):
    # plan is set by the view (inline child).
    class Meta:
        model = WorkforcePlanLine
        fields = ["org_unit", "designation", "current_headcount", "planned_headcount", "hiring_type",
                  "avg_annual_cost", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "org_unit" in self.fields:
                self.fields["org_unit"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            if "designation" in self.fields:
                self.fields["designation"].queryset = (
                    Designation.objects.filter(tenant=self.tenant).order_by("name"))

    def clean(self):
        cleaned = super().clean()
        cost = cleaned.get("avg_annual_cost")
        if cost is not None and cost < 0:
            self.add_error("avg_annual_cost", "Must be zero or greater.")
        return cleaned
