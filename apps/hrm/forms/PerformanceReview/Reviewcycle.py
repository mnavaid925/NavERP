"""HRM 3.19 Performance Review — Reviewcycle forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    GoalPeriod,
    ReviewCycle,
)


# ------------------------------------------------------------------------- 3.19 Performance Review
class ReviewCycleForm(TenantModelForm):
    # `status` is workflow-owned (the phase machine — changed only via reviewcycle_advance_phase,
    # never a directly-editable field). This mirrors the 3.18 GoalPeriodForm fix: exposing status
    # on the form would let a non-admin POST a phase change and bypass the @tenant_admin_required gate.
    class Meta:
        model = ReviewCycle
        fields = ["name", "cycle_type", "self_review_start", "self_review_end",
                  "manager_review_start", "manager_review_end", "calibration_date",
                  "results_release_date", "goal_period", "description"]
        widgets = {
            "self_review_start": forms.DateInput(attrs={"type": "date"}),
            "self_review_end": forms.DateInput(attrs={"type": "date"}),
            "manager_review_start": forms.DateInput(attrs={"type": "date"}),
            "manager_review_end": forms.DateInput(attrs={"type": "date"}),
            "calibration_date": forms.DateInput(attrs={"type": "date"}),
            "results_release_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None and "goal_period" in self.fields:
            self.fields["goal_period"].queryset = (
                GoalPeriod.objects.filter(tenant=self.tenant).order_by("-start_date"))
