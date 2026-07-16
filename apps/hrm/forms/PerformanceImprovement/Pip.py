"""HRM 3.21 Performance Improvement — Pip forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    PerformanceImprovementPlan,
)


class PIPCloseForm(TenantModelForm):
    # The narrow close-with-outcome form (the ONLY write path to outcome/outcome_date/outcome_notes — the
    # general edit form never exposes them). The close VIEW sets status="closed" on the instance before
    # validation so the model's outcome-iff-closed clean() passes. tenant= kept for signature parity.
    class Meta:
        model = PerformanceImprovementPlan
        fields = ["outcome", "outcome_date", "outcome_notes"]
        widgets = {
            "outcome_date": forms.DateInput(attrs={"type": "date"}),
            "outcome_notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def clean_outcome(self):
        outcome = self.cleaned_data.get("outcome")
        if not outcome:
            raise forms.ValidationError("Select an outcome to close the plan.")
        return outcome
