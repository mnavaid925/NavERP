"""HRM 3.19 Performance Review — Performancereview forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    PerformanceReview,
    ReviewCycle,
    ReviewTemplate,
)


class PerformanceReviewForm(TenantModelForm):
    # number + all workflow/calibration fields (status/manager_rating/calibrated_rating/
    # potential_rating/calibration_notes/*_at/acknowledged_by) are set only by the dedicated
    # submit/share/acknowledge/calibrate actions — never on this create/edit form.
    class Meta:
        model = PerformanceReview
        fields = ["cycle", "template", "subject", "reviewer", "review_type",
                  "strengths", "improvements", "private_notes", "is_anonymous"]
        widgets = {
            "strengths": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "improvements": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "private_notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            emps = (EmployeeProfile.objects.filter(tenant=self.tenant)
                    .select_related("party").order_by("party__name"))
            if "cycle" in self.fields:
                self.fields["cycle"].queryset = (
                    ReviewCycle.objects.filter(tenant=self.tenant).order_by("-self_review_start"))
            if "template" in self.fields:
                self.fields["template"].queryset = (
                    ReviewTemplate.objects.filter(tenant=self.tenant, is_active=True).order_by("review_type", "name"))
            if "subject" in self.fields:
                self.fields["subject"].queryset = emps
            if "reviewer" in self.fields:
                self.fields["reviewer"].queryset = emps
