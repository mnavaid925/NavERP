from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.AiAugmentedAnalytics.AugmentedInsights import AugmentedInsight
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class AugmentedInsightForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AugmentedInsight
        fields = [
            "title",
            "insight_type",
            "metric_name",
            "baseline_value",
            "observed_value",
            "variance_percentage",
            "impact_direction",
            "severity",
            "confidence_score",
            "narrative_summary",
            "dimension_name",
            "dimension_value",
            "status",
            "action_notes",
            "semantic_model",
            "kpi_definition",
            "warehouse_table",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Q4 EMEA Gross Margin Compression"}),
            "insight_type": forms.Select(attrs={"class": "form-select"}),
            "metric_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Gross Margin %"}),
            "baseline_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "observed_value": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001"}),
            "variance_percentage": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "impact_direction": forms.Select(attrs={"class": "form-select"}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "confidence_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "narrative_summary": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Executive narrative explaining the insight..."}),
            "dimension_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Region"}),
            "dimension_value": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. EMEA"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "action_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Action items or notes..."}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "kpi_definition": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)
            self.fields["kpi_definition"].queryset = KpiDefinition.objects.filter(tenant=self.tenant)
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant)
        self.fields["semantic_model"].required = False
        self.fields["kpi_definition"].required = False
        self.fields["warehouse_table"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["semantic_model", "kpi_definition", "warehouse_table"])
        return cleaned_data
