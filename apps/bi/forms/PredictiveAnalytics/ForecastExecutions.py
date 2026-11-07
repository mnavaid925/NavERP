from django import forms

from apps.bi.forms._common import reject_foreign
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.PredictiveAnalytics.ForecastExecutions import ForecastExecution
from apps.bi.models.PredictiveAnalytics.PredictiveModels import PredictiveModel
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class ForecastExecutionForm(TenantModelForm):
    class Meta:
        model = ForecastExecution
        fields = [
            "name",
            "model",
            "semantic_model",
            "kpi_definition",
            "cadence",
            "horizon_periods",
            "confidence_level",
            "historical_window_periods",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FY2027 Revenue Projection"}),
            "model": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "kpi_definition": forms.Select(attrs={"class": "form-select"}),
            "cadence": forms.Select(attrs={"class": "form-select"}),
            "horizon_periods": forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 60}),
            "confidence_level": forms.Select(attrs={"class": "form-select"}),
            "historical_window_periods": forms.NumberInput(attrs={"class": "form-input", "min": 6, "max": 120}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-textarea", "placeholder": "Simulation assumptions and methodology notes"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["model"].queryset = PredictiveModel.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)
            self.fields["kpi_definition"].queryset = KpiDefinition.objects.filter(tenant=self.tenant, is_active=True)

    def clean_model(self):
        return reject_foreign(self.tenant, self.cleaned_data.get("model"))

    def clean_semantic_model(self):
        return reject_foreign(self.tenant, self.cleaned_data.get("semantic_model"))

    def clean_kpi_definition(self):
        return reject_foreign(self.tenant, self.cleaned_data.get("kpi_definition"))
