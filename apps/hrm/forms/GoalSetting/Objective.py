"""HRM 3.18 Goal Setting — Objective forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    GoalPeriod,
    Objective,
)


class ObjectiveForm(TenantModelForm):
    # number is auto-assigned; progress_pct/health_status are derived, never form-typed.
    class Meta:
        model = Objective
        fields = ["title", "description", "owner", "goal_period", "parent_objective", "department",
                  "scope", "target_type", "weight", "status", "start_date", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            if "owner" in self.fields:
                self.fields["owner"].queryset = (
                    EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "goal_period" in self.fields:
                self.fields["goal_period"].queryset = (
                    GoalPeriod.objects.filter(tenant=self.tenant).order_by("-start_date"))
            if "department" in self.fields:
                self.fields["department"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            if "parent_objective" in self.fields:
                # Exclude self so an objective can't be picked as its own parent (model clean() also guards).
                qs = Objective.objects.filter(tenant=self.tenant).select_related("goal_period").order_by("title")
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                self.fields["parent_objective"].queryset = qs
