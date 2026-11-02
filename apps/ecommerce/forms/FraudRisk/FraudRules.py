from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.FraudRisk.FraudRules import FraudRule


class FraudRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = FraudRule
        exclude = ["tenant", "number", "created_at", "updated_at"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Card Velocity Exceeded (3+ per hr)"}),
            "rule_code": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. R-VEL-01"}),
            "rule_scope": forms.Select(attrs={"class": "form-select"}),
            "rule_type": forms.Select(attrs={"class": "form-select"}),
            "condition_operator": forms.Select(attrs={"class": "form-select"}),
            "threshold_value": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 5, 2500.00, US,CA"}),
            "risk_score_impact": forms.NumberInput(attrs={"class": "form-input", "placeholder": "25"}),
            "action_to_take": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.NumberInput(attrs={"class": "form-input", "placeholder": "10"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Explain threat vector, false positive guidance..."}),
        }

    def clean_threshold_value(self):
        val = self.cleaned_data.get("threshold_value", "").strip()
        if not val:
            raise forms.ValidationError("Threshold value cannot be empty.")
        return val

    def clean_priority(self):
        val = self.cleaned_data.get("priority")
        if val is not None and val < 1:
            raise forms.ValidationError("Priority must be 1 or higher.")
        return val
