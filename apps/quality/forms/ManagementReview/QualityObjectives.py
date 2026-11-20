from django import forms
from django.contrib.auth import get_user_model

from apps.core.models import OrgUnit
from apps.quality.forms._common import TenantModelForm, reject_foreign
from apps.quality.models.ManagementReview.QualityObjectives import QualityObjective

User = get_user_model()


class QualityObjectiveForm(TenantModelForm):
    class Meta:
        model = QualityObjective
        fields = [
            "title",
            "description",
            "category",
            "period_year",
            "cadence",
            "metric_unit",
            "baseline_value",
            "target_value",
            "current_value",
            "target_direction",
            "status",
            "owner",
            "org_unit",
            "target_date",
            "action_plan_summary",
            "notes",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. First Pass Inspection Yield >= 98.5%"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Detailed rationale and measurement methodology"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "period_year": forms.NumberInput(attrs={"class": "form-input"}),
            "cadence": forms.Select(attrs={"class": "form-select"}),
            "metric_unit": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. %, PPM, Days"}),
            "baseline_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "target_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "current_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
            "target_direction": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "target_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "action_plan_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Strategic initiatives to reach target"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if self.tenant:
            self.fields["owner"].queryset = User.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("first_name", "last_name", "username")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["owner", "org_unit"])
        return cleaned_data


class QualityObjectiveEvaluateForm(forms.Form):
    current_value = forms.DecimalField(
        max_digits=12,
        decimal_places=3,
        widget=forms.NumberInput(attrs={"class": "form-input", "step": "0.001"}),
        help_text="Updated actual performance metric value",
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Evaluation commentary or variance explanation"}),
    )
