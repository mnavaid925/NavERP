"""Sales 8.12 — Forms for `StageVelocityAnalysis`."""
from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.sales.forms._common import TenantUniqueMixin, _reject_foreign
from apps.sales.models.SalesAnalytics.StageVelocityAnalyses import StageVelocityAnalysis


class StageVelocityAnalysisForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = StageVelocityAnalysis
        fields = [
            "pipeline",
            "pipeline_stage",
            "period_start",
            "period_end",
            "opportunity_count",
            "median_days_in_stage",
            "p90_days_in_stage",
            "max_days_in_stage",
            "sales_cycle_days",
            "velocity_value",
            "is_bottleneck",
            "bottleneck_rank",
            "recommendation",
            "benchmark_days",
            "benchmark_source",
            "benchmark_as_of",
            "segment",
            "status",
            "notes",
        ]
        widgets = {
            "pipeline": forms.Select(attrs={"class": "form-select"}),
            "pipeline_stage": forms.Select(attrs={"class": "form-select"}),
            "period_start": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "period_end": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "opportunity_count": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "median_days_in_stage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "p90_days_in_stage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "max_days_in_stage": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "sales_cycle_days": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "velocity_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "is_bottleneck": forms.CheckboxInput(attrs={"class": "form-check"}),
            "bottleneck_rank": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "recommendation": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "benchmark_days": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "benchmark_source": forms.TextInput(attrs={"class": "form-input"}),
            "benchmark_as_of": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "segment": forms.TextInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def clean_pipeline_stage(self, value):
        """The stage must belong to the chosen pipeline.

        The FK is a plain stage reference, so a stage from another pipeline is
        otherwise a legal pick that would silently report the wrong stage.
        """
        if value is None:
            return value
        pipeline = self.cleaned_data.get("pipeline")
        if pipeline is not None and value.pipeline_id != pipeline.pk:
            raise ValidationError("Choose a stage from the selected pipeline.")
        return value

    def clean(self):
        cleaned_data = super().clean()
        _reject_foreign(self, cleaned_data, ["pipeline", "pipeline_stage"])
        return cleaned_data
