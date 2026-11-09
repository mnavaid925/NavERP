from django import forms

from apps.accounting.models import FixedAsset
from apps.assets.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.assets.models import AssetCategory, AssetMaintenanceSchedule
from apps.assets.models.AssetReliability.AssetFailureModes import AssetFailureMode
from apps.scm.models import Asset as OperationalAsset


class AssetFailureModeForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AssetFailureMode
        fields = [
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "component_subsystem",
            "function_description",
            "functional_failure",
            "failure_mode",
            "failure_cause",
            "failure_effect",
            "severity_score",
            "occurrence_score",
            "detection_score",
            "rcm_strategy",
            "strategy_rationale",
            "mitigation_task",
            "linked_maintenance_schedule",
            "assessed_by",
            "status",
        ]
        widgets = {
            "fixed_asset": forms.Select(attrs={"class": "form-select"}),
            "operational_asset": forms.Select(attrs={"class": "form-select"}),
            "asset_category": forms.Select(attrs={"class": "form-select"}),
            "component_subsystem": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Centrifugal Pump Impeller / Drive Shaft"}),
            "function_description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Primary engineering function..."}),
            "functional_failure": forms.TextInput(attrs={"class": "form-input", "placeholder": "Inability to sustain rated discharge flow/pressure"}),
            "failure_mode": forms.TextInput(attrs={"class": "form-input", "placeholder": "Cavitation erosion / Blade tip breakage"}),
            "failure_cause": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Low NPSH available, vortexing, fluid vaporisation..."}),
            "failure_effect": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Flow loss, violent vibration, line starvation..."}),
            "severity_score": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 10}),
            "occurrence_score": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 10}),
            "detection_score": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 10}),
            "rcm_strategy": forms.Select(attrs={"class": "form-select"}),
            "strategy_rationale": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Justification for selected proactive maintenance policy..."}),
            "mitigation_task": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Proactive task: Monthly ultrasonic cavitation detection..."}),
            "linked_maintenance_schedule": forms.Select(attrs={"class": "form-select"}),
            "assessed_by": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["fixed_asset"].queryset = FixedAsset.objects.filter(tenant=self.tenant)
            self.fields["operational_asset"].queryset = OperationalAsset.objects.filter(tenant=self.tenant)
            self.fields["asset_category"].queryset = AssetCategory.objects.filter(tenant=self.tenant)
            self.fields["linked_maintenance_schedule"].queryset = AssetMaintenanceSchedule.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["fixed_asset", "operational_asset", "asset_category", "linked_maintenance_schedule"],
        )
        return cleaned_data
