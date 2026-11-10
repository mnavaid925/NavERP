from django import forms

from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetCategory
from apps.assets.models.AssetCompliance.AssetComplianceFrameworks import AssetComplianceFramework
from apps.core.models import Party


class AssetComplianceFrameworkForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetComplianceFramework
        fields = [
            "name",
            "code",
            "framework_type",
            "regulatory_agency",
            "applicable_category",
            "effective_date",
            "revision",
            "mandatory_audit_cycle_months",
            "readiness_score",
            "description",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. OSHA 1910.119 Process Safety Management"}),
            "code": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. OSHA-1910-PSM"}),
            "framework_type": forms.Select(attrs={"class": "form-select"}),
            "regulatory_agency": forms.Select(attrs={"class": "form-select"}),
            "applicable_category": forms.Select(attrs={"class": "form-select"}),
            "effective_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "revision": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. 2024 Edition"}),
            "mandatory_audit_cycle_months": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "readiness_score": forms.NumberInput(attrs={"class": "form-input", "min": "0", "max": "100"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Scope, legal citations, enforcement guidelines, and audit checkpoints..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["regulatory_agency"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["applicable_category"].queryset = AssetCategory.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["regulatory_agency", "applicable_category"])
        return cleaned
