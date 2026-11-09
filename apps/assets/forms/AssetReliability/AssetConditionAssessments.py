from django import forms

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetCategory
from apps.assets.models.AssetReliability.AssetConditionAssessments import AssetConditionAssessment
from apps.core.models import Party
from apps.scm.models import Asset as OperationalAsset


class AssetConditionAssessmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetConditionAssessment
        fields = [
            "title",
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "inspector",
            "external_inspector",
            "assessment_date",
            "assessment_type",
            "condition_grade",
            "health_score",
            "operating_status",
            "checklist_summary",
            "findings",
            "recommendations",
            "followup_required",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Annual Ultrasonic Thickness Inspection on CNC Lathe"}),
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "asset_category": forms.Select(attrs={"class": "form-select"}),
            "inspector": forms.Select(attrs={"class": "form-select"}),
            "external_inspector": forms.Select(attrs={"class": "form-select"}),
            "assessment_date": forms.DateInput(attrs={"type": "date", "class": "form-input"}),
            "assessment_type": forms.Select(attrs={"class": "form-select"}),
            "condition_grade": forms.Select(attrs={"class": "form-select"}),
            "health_score": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 100}),
            "operating_status": forms.Select(attrs={"class": "form-select"}),
            "checklist_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Inspected bearing housings, check valve seals, structural frame welds..."}),
            "findings": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Detailed physical findings, wear patterns, ultrasonic metal thickness measurements..."}),
            "recommendations": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Recommended corrective maintenance, lube changes, or load restrictions..."}),
            "followup_required": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant)
            self.fields["asset_category"].queryset = AssetCategory.objects.filter(tenant=self.tenant)
            self.fields["external_inspector"].queryset = Party.objects.filter(
                tenant=self.tenant,
                roles__role="vendor",
            ).distinct()

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["fixed_asset", "operational_asset", "asset_category", "external_inspector"])
        return cleaned_data
