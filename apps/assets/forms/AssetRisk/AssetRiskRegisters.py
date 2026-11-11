from django import forms
from django.contrib.auth import get_user_model

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetCategory
from apps.assets.models.AssetRisk.AssetRiskRegisters import AssetRiskRegister
from apps.scm.models import Asset

User = get_user_model()


class AssetRiskRegisterForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetRiskRegister
        fields = [
            "title",
            "asset",
            "category",
            "risk_category",
            "threat_source",
            "failure_mode",
            "description",
            "inherent_likelihood",
            "inherent_impact",
            "residual_likelihood",
            "residual_impact",
            "risk_owner",
            "treatment_strategy",
            "financial_exposure_amount",
            "status",
            "review_frequency",
            "next_review_date",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Main Turbine Bearing Catastrophic Failure Risk"}
            ),
            "asset": forms.Select(attrs={"class": "form-select"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "risk_category": forms.Select(attrs={"class": "form-select"}),
            "threat_source": forms.Select(attrs={"class": "form-select"}),
            "failure_mode": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Excessive vibration leading to fatigue spalling"}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 4, "placeholder": "Risk triggers, failure sequence, and plant impact..."}
            ),
            "inherent_likelihood": forms.NumberInput(
                attrs={"class": "form-input", "min": "1", "max": "5", "placeholder": "1 (Rare) to 5 (Almost Certain)"}
            ),
            "inherent_impact": forms.NumberInput(
                attrs={"class": "form-input", "min": "1", "max": "5", "placeholder": "1 (Insignificant) to 5 (Catastrophic)"}
            ),
            "residual_likelihood": forms.NumberInput(
                attrs={"class": "form-input", "min": "1", "max": "5", "placeholder": "1 to 5"}
            ),
            "residual_impact": forms.NumberInput(
                attrs={"class": "form-input", "min": "1", "max": "5", "placeholder": "1 to 5"}
            ),
            "risk_owner": forms.Select(attrs={"class": "form-select"}),
            "treatment_strategy": forms.Select(attrs={"class": "form-select"}),
            "financial_exposure_amount": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "placeholder": "0.00"}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "review_frequency": forms.Select(attrs={"class": "form-select"}),
            "next_review_date": forms.DateInput(
                attrs={"class": "form-input", "type": "date"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["asset"].queryset = Asset.objects.filter(tenant=self.tenant)
            self.fields["category"].queryset = AssetCategory.objects.filter(tenant=self.tenant)
            self.fields["risk_owner"].queryset = User.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["asset", "category", "risk_owner"])
        return cleaned
