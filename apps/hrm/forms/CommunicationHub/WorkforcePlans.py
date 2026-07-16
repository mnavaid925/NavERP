"""HRM 3.27 Communication Hub — WorkforcePlans forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    WorkforcePlan,
)
from apps.hrm.forms.CommunicationHub._helpers import _scope_currency


class WorkforcePlanForm(TenantModelForm):
    class Meta:
        model = WorkforcePlan
        fields = ["name", "org_unit", "plan_type", "period_start", "period_end",
                  "growth_assumption_percent", "owner", "currency", "status", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _scope_currency(self)
        if self.tenant is not None:
            if "org_unit" in self.fields:
                self.fields["org_unit"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            if "owner" in self.fields:
                self.fields["owner"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant).select_related("party")
                    .order_by("party__name"))

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("period_start"), cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "Period end cannot be before the period start.")
        # unique_together(tenant, name) — Django skips validate_unique (tenant is form-excluded).
        name = cleaned.get("name")
        if name and self.tenant is not None:
            dupe = WorkforcePlan.objects.filter(tenant=self.tenant, name=name)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("name", "A workforce plan with this name already exists.")
        return cleaned
