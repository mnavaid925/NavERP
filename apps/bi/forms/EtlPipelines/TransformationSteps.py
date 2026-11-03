import json

from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.EtlPipelines.EtlPipelines import EtlPipeline
from apps.bi.models.EtlPipelines.TransformationSteps import TransformationStep
from apps.core.models.Integration import MappingTemplate


class TransformationStepForm(TenantUniqueMixin, forms.ModelForm):
    upstream_step_ids_raw = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
        required=False,
        label="Upstream Prerequisites (JSON Array)",
        help_text='JSON array of prerequisite step numbers/IDs feeding input into this node, e.g. ["BTRN-00001"]',
    )
    step_config_raw = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4}),
        required=False,
        label="Step Configuration (JSON)",
        help_text='Detailed transform settings, e.g. {"join_type": "left", "join_keys": ["customer_id"], "group_by": ["period_id"], "metrics": ["sum(amount)"]}',
    )

    class Meta:
        model = TransformationStep
        fields = [
            "pipeline",
            "name",
            "step_type",
            "sequence",
            "mapping_template",
            "status",
            "is_blocking",
            "description",
        ]
        widgets = {
            "pipeline": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Join Customer Dimension & Calculate Margin"}),
            "step_type": forms.Select(attrs={"class": "form-select"}),
            "sequence": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "mapping_template": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_blocking": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Describe step transformation logic"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["pipeline"].queryset = EtlPipeline.objects.filter(tenant=self.tenant)
            self.fields["mapping_template"].queryset = MappingTemplate.objects.filter(tenant=self.tenant)
        if self.instance and self.instance.pk:
            if self.instance.upstream_step_ids:
                self.fields["upstream_step_ids_raw"].initial = json.dumps(self.instance.upstream_step_ids, indent=2)
            if self.instance.step_config:
                self.fields["step_config_raw"].initial = json.dumps(self.instance.step_config, indent=2)

    def clean_upstream_step_ids_raw(self):
        raw = self.cleaned_data.get("upstream_step_ids_raw", "").strip()
        if not raw:
            return []
        try:
            val = json.loads(raw)
            if not isinstance(val, list):
                raise forms.ValidationError("Must be a valid JSON array of step identifiers.")
            return val
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean_step_config_raw(self):
        raw = self.cleaned_data.get("step_config_raw", "").strip()
        if not raw:
            return {}
        try:
            val = json.loads(raw)
            if not isinstance(val, dict):
                raise forms.ValidationError("Must be a valid JSON object.")
            return val
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["pipeline", "mapping_template"])
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "upstream_step_ids_raw" in self.cleaned_data:
            instance.upstream_step_ids = self.cleaned_data["upstream_step_ids_raw"]
        if "step_config_raw" in self.cleaned_data:
            instance.step_config = self.cleaned_data["step_config_raw"]
        if commit:
            instance.save()
        return instance
