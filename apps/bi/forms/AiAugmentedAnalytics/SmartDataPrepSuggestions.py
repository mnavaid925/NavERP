from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.AiAugmentedAnalytics.SmartDataPrepSuggestions import SmartDataPrepSuggestion
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.core.forms import TenantModelForm


class SmartDataPrepSuggestionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SmartDataPrepSuggestion
        fields = [
            "target_table",
            "target_column",
            "suggestion_type",
            "related_table",
            "related_column",
            "confidence_score",
            "rationale",
            "status",
            "review_notes",
        ]
        widgets = {
            "target_table": forms.Select(attrs={"class": "form-select"}),
            "target_column": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. customer_id, order_date"}),
            "suggestion_type": forms.Select(attrs={"class": "form-select"}),
            "related_table": forms.Select(attrs={"class": "form-select"}),
            "related_column": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. id, party_number"}),
            "confidence_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "rationale": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Explanation of suggested join or transform..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "review_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Data engineer review notes..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["target_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant)
            self.fields["related_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant)
        self.fields["related_table"].required = False

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["target_table", "related_table"])
        return cleaned_data
