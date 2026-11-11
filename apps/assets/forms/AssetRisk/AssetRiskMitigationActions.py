from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetRisk.AssetRiskMitigationActions import AssetRiskMitigationAction
from apps.assets.models.AssetRisk.AssetRiskRegisters import AssetRiskRegister
from apps.core.models import Party

User = get_user_model()


class AssetRiskMitigationActionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetRiskMitigationAction
        fields = [
            "title",
            "risk",
            "action_type",
            "description",
            "assigned_to",
            "alternative_supplier",
            "target_completion_date",
            "estimated_cost",
            "actual_cost",
            "priority",
            "status",
            "verification_notes",
            "effectiveness_rating",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Install Automatic Transfer Switch for Emergency Generator"}
            ),
            "risk": forms.Select(attrs={"class": "form-select"}),
            "action_type": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Action scope, technical deliverables, and verification criteria..."}
            ),
            "assigned_to": forms.Select(attrs={"class": "form-select"}),
            "alternative_supplier": forms.Select(attrs={"class": "form-select"}),
            "target_completion_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
            "estimated_cost": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "placeholder": "0.00"}
            ),
            "actual_cost": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "placeholder": "0.00"}
            ),
            "priority": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "verification_notes": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Post-implementation engineering observations and evidence..."}
            ),
            "effectiveness_rating": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["risk"].queryset = AssetRiskRegister.objects.filter(tenant=self.tenant)
            self.fields["assigned_to"].queryset = User.objects.filter(tenant=self.tenant)
            self.fields["alternative_supplier"].queryset = Party.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["risk", "assigned_to", "alternative_supplier"])
        return cleaned
