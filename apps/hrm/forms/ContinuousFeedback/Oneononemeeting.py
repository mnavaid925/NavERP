"""HRM 3.20 Continuous Feedback — Oneononemeeting forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    Objective,
    OneOnOneMeeting,
)


class OneOnOneMeetingForm(TenantModelForm):
    # `status` is workflow-owned (changed only via the complete/cancel actions) — exposing it would
    # let a non-admin POST a phase change and bypass the gate (the GoalPeriodForm/ReviewCycleForm fix).
    # `number`/`completed_at` are auto/workflow. `manager_private_notes` STAYS on the form: the writer
    # (the manager) must be able to type it — only the READ side is confidential, gated in the detail view.
    class Meta:
        model = OneOnOneMeeting
        fields = ["manager", "employee", "scheduled_at", "agenda", "shared_notes",
                  "manager_private_notes", "related_objective"]
        widgets = {
            "agenda": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "shared_notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "manager_private_notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            emps = (EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "manager" in self.fields:
                self.fields["manager"].queryset = emps
            if "employee" in self.fields:
                self.fields["employee"].queryset = emps
            if "related_objective" in self.fields:
                self.fields["related_objective"].queryset = (
                    Objective.objects.filter(tenant=self.tenant)
                    .select_related("goal_period").order_by("title"))
