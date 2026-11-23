from django import forms

from apps.core.forms import TenantModelForm
from apps.documents.forms._common import TenantUniqueMixin
from apps.documents.models.SearchDiscovery.DocumentSearchQueryLogs import DocumentSearchQueryLog


class DocumentSearchQueryLogForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DocumentSearchQueryLog
        fields = [
            "query_text",
            "search_source",
            "results_count",
            "is_zero_result",
            "execution_time_ms",
        ]
        widgets = {
            "query_text": forms.TextInput(attrs={"class": "form-input", "readonly": "readonly"}),
            "search_source": forms.Select(attrs={"class": "form-select"}),
            "results_count": forms.NumberInput(attrs={"class": "form-input", "readonly": "readonly"}),
            "is_zero_result": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "execution_time_ms": forms.NumberInput(attrs={"class": "form-input", "readonly": "readonly"}),
        }
