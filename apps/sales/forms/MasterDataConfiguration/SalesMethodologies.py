"""Form for SalesMethodology model."""
import json
from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.sales.models.MasterDataConfiguration.SalesMethodologies import SalesMethodology
from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline, PipelineStage


class SalesMethodologyForm(TenantModelForm):
    """Form to create and update sales methodologies and stage gate criteria."""

    qualification_criteria_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-textarea font-mono text-sm",
                "rows": 4,
                "placeholder": '[{"key": "metrics", "label": "Quantified Economic Impact", "weight": 20, "is_required": true}]',
            }
        ),
        label="Qualification Criteria (JSON)",
        help_text="JSON list of qualification criteria objects with key, label, weight, and is_required.",
    )

    class Meta:
        model = SalesMethodology
        fields = [
            "name",
            "framework",
            "pipeline",
            "gating_stage",
            "min_passing_score",
            "is_mandatory_gate",
            "coaching_guidelines",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Enterprise MEDDPICC Stage Gate"}),
            "framework": forms.Select(attrs={"class": "form-select"}),
            "pipeline": forms.Select(attrs={"class": "form-select"}),
            "gating_stage": forms.Select(attrs={"class": "form-select"}),
            "min_passing_score": forms.NumberInput(attrs={"class": "form-input", "min": "0", "max": "100"}),
            "is_mandatory_gate": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "coaching_guidelines": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Questions to ask, deal risks to look for, coaching guidelines..."}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant and not getattr(self.instance, "tenant_id", None):
            self.instance.tenant = self.tenant
        if self.tenant:
            self.fields["pipeline"].queryset = Pipeline.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["gating_stage"].queryset = PipelineStage.objects.filter(tenant=self.tenant, is_active=True)

        if self.instance and self.instance.pk and self.instance.qualification_criteria:
            self.fields["qualification_criteria_raw"].initial = json.dumps(self.instance.qualification_criteria, indent=2)

    def clean_qualification_criteria_raw(self):
        raw = self.cleaned_data.get("qualification_criteria_raw", "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise ValidationError("Criteria must be a JSON array of objects.")
            return parsed
        except json.JSONDecodeError as exc:
            raise ValidationError(f"Invalid JSON format: {exc}")

    def clean(self):
        cleaned_data = super().clean()
        criteria = cleaned_data.get("qualification_criteria_raw")
        if criteria is not None:
            self.instance.qualification_criteria = criteria
        return cleaned_data
