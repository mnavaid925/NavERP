from django import forms
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.SelfServiceAnalytics.AdHocCalculatedFields import AdHocCalculatedField
from apps.bi.models.SelfServiceAnalytics.AdHocQueries import AdHocQuery
from apps.core.forms import TenantModelForm


class AdHocCalculatedFieldForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AdHocCalculatedField
        fields = [
            "query",
            "field_name",
            "display_label",
            "formula_expression",
            "return_type",
            "aggregation_mode",
        ]
        widgets = {
            "query": forms.Select(attrs={"class": "form-select"}),
            "field_name": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. net_profit_margin"}),
            "display_label": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Net Profit Margin (%)"}),
            "formula_expression": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. ([revenue] - [cogs]) / [revenue] * 100"}),
            "return_type": forms.Select(attrs={"class": "form-select"}),
            "aggregation_mode": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "field_name" in self.fields:
            self.fields["field_name"].required = False

        if self.tenant is not None and "query" in self.fields:
            self.fields["query"].queryset = AdHocQuery.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["query"])

        display_label = cleaned.get("display_label")
        field_name = cleaned.get("field_name")
        if not field_name and display_label:
            cleaned["field_name"] = slugify(display_label).replace("-", "_")[:50] or "calc_field"

        formula = cleaned.get("formula_expression", "").strip()
        if formula:
            # Basic balance check for bracket pairs
            open_sq = formula.count("[")
            close_sq = formula.count("]")
            open_paren = formula.count("(")
            close_paren = formula.count(")")
            if open_sq != close_sq:
                self.add_error("formula_expression", "Unbalanced brackets in formula expression.")
            if open_paren != close_paren:
                self.add_error("formula_expression", "Unbalanced parentheses in formula expression.")

        return cleaned
