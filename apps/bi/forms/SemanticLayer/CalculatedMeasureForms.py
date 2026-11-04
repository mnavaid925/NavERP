from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.SemanticLayer.BusinessGlossaryTerms import BusinessGlossaryTerm
from apps.bi.models.SemanticLayer.CalculatedMeasures import CalculatedMeasure
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class CalculatedMeasureForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CalculatedMeasure
        fields = [
            "semantic_model",
            "glossary_term",
            "name",
            "code",
            "aggregation_type",
            "source_column",
            "formula_expression",
            "filter_expression",
            "time_intelligence",
            "format_string",
            "display_units",
            "target_value",
            "warning_threshold",
            "critical_threshold",
            "description",
            "is_active",
        ]
        widgets = {
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "glossary_term": forms.Select(attrs={"class": "form-select"}),
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Gross Profit Margin %"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. gross_profit_margin_pct"}),
            "aggregation_type": forms.Select(attrs={"class": "form-select"}),
            "source_column": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. amount, revenue"}),
            "formula_expression": forms.TextInput(attrs={"class": "form-input font-mono text-xs", "placeholder": "e.g. ([revenue] - [cost]) / [revenue] * 100"}),
            "filter_expression": forms.TextInput(attrs={"class": "form-input font-mono text-xs", "placeholder": "e.g. status = 'posted'"}),
            "time_intelligence": forms.Select(attrs={"class": "form-select"}),
            "format_string": forms.Select(attrs={"class": "form-select"}),
            "display_units": forms.Select(attrs={"class": "form-select"}),
            "target_value": forms.NumberInput(attrs={"class": "form-input font-mono text-sm", "step": "0.0001"}),
            "warning_threshold": forms.NumberInput(attrs={"class": "form-input font-mono text-sm", "step": "0.0001"}),
            "critical_threshold": forms.NumberInput(attrs={"class": "form-input font-mono text-sm", "step": "0.0001"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)
            self.fields["glossary_term"].queryset = BusinessGlossaryTerm.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["semantic_model", "glossary_term"])

        agg_type = cleaned_data.get("aggregation_type")
        source_col = cleaned_data.get("source_column")
        formula = cleaned_data.get("formula_expression")

        if agg_type == "formula" and not formula:
            self.add_error("formula_expression", "A calculation formula is required when aggregation type is set to Formula.")
        elif agg_type != "formula" and not source_col and not formula:
            self.add_error("source_column", "Specify either a source column or formula expression.")

        return cleaned_data
