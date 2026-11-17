from django import forms
from django.contrib.auth import get_user_model

from apps.quality.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.quality.models.CapaManagement.CapaEffectivenessReviews import CapaEffectivenessReview
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation

User = get_user_model()


class CapaEffectivenessReviewForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CapaEffectivenessReview
        fields = [
            "capa",
            "review_criteria",
            "verification_method",
            "planned_review_date",
            "evaluator",
            "metrics_evaluated",
            "recurrence_observed",
            "recurrence_details",
            "outcome",
            "status",
            "review_notes",
        ]
        widgets = {
            "capa": forms.Select(attrs={"class": "form-select"}),
            "review_criteria": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Acceptance criteria (e.g., zero defect recurrence in 90-day window, Cpk >= 1.33 across 3 lots)..."}),
            "verification_method": forms.Select(attrs={"class": "form-select"}),
            "planned_review_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "evaluator": forms.Select(attrs={"class": "form-select"}),
            "metrics_evaluated": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Observed test results, scrap count, statistical capability metrics, or complaint data..."}),
            "recurrence_observed": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "recurrence_details": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "If defect recurred, describe circumstances, lots, and new incident references..."}),
            "outcome": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "review_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Evaluation summary, conclusions, and follow-up recommendations..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["capa"].queryset = CapaInvestigation.objects.filter(tenant=self.tenant)
            self.fields["evaluator"].queryset = User.objects.filter(tenant=self.tenant, is_active=True).order_by("username")
        else:
            self.fields["capa"].queryset = CapaInvestigation.objects.none()
            self.fields["evaluator"].queryset = User.objects.none()

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["capa", "evaluator"])
        recurrence = cleaned.get("recurrence_observed")
        outcome = cleaned.get("outcome")
        if recurrence and outcome == "effective":
            self.add_error("outcome", "Cannot mark review as 'Effective' when recurrence has been observed.")
        return cleaned
