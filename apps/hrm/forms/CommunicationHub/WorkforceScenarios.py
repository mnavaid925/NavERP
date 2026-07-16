"""HRM 3.27 Communication Hub — WorkforceScenarios forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    WorkforcePlan,
    WorkforceScenario,
)


class WorkforceScenarioForm(TenantModelForm):
    # `plan` is an editable dropdown. When created from a plan's "New Scenario" link the view seeds
    # initial={"plan": ...} from ?plan=<id>, but the user can always change it here.
    class Meta:
        model = WorkforceScenario
        fields = ["plan", "name", "scenario_type", "affected_org_unit", "description",
                  "headcount_delta", "cost_delta", "is_baseline", "is_selected", "status", "notes"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}),
                   "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "plan" in self.fields:
                self.fields["plan"].queryset = (
                    WorkforcePlan.objects.filter(tenant=self.tenant).order_by("-created_at"))
            if "affected_org_unit" in self.fields:
                self.fields["affected_org_unit"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))

    def clean(self):
        cleaned = super().clean()
        # unique_together(tenant, plan, name) — guarded here (tenant is form-excluded).
        plan, name = cleaned.get("plan"), cleaned.get("name")
        if plan and name and self.tenant is not None:
            dupe = WorkforceScenario.objects.filter(tenant=self.tenant, plan=plan, name=name)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("name", "This plan already has a scenario with that name.")
        return cleaned
