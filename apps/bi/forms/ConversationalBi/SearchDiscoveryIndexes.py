import json

from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.ConversationalBi.SearchDiscoveryIndexes import SearchDiscoveryIndex
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.SemanticLayer.BusinessGlossaryTerms import BusinessGlossaryTerm
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class SearchDiscoveryIndexForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SearchDiscoveryIndex
        fields = [
            "asset_name",
            "asset_type",
            "target_url",
            "description",
            "category",
            "synonyms",
            "search_keywords",
            "semantic_model",
            "dashboard",
            "report",
            "kpi",
            "warehouse_table",
            "glossary_term",
            "relevance_weight",
            "is_featured",
            "is_verified",
        ]
        widgets = {
            "asset_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Executive Revenue Dashboard"}),
            "asset_type": forms.Select(attrs={"class": "form-select"}),
            "target_url": forms.TextInput(attrs={"class": "form-input", "placeholder": "/bi/dashboards/1/"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Overview of this analytical asset..."}),
            "category": forms.TextInput(attrs={"class": "form-input", "placeholder": "Finance"}),
            "synonyms": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": '["sales", "revenue", "top line"] or comma-separated'}),
            "search_keywords": forms.TextInput(attrs={"class": "form-input", "placeholder": "q4, margin, arr, enterprise"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "dashboard": forms.Select(attrs={"class": "form-select"}),
            "report": forms.Select(attrs={"class": "form-select"}),
            "kpi": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "glossary_term": forms.Select(attrs={"class": "form-select"}),
            "relevance_weight": forms.NumberInput(attrs={"class": "form-input", "step": "0.10"}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_verified": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)
            self.fields["dashboard"].queryset = BiDashboard.objects.filter(tenant=self.tenant)
            self.fields["report"].queryset = ReportDefinition.objects.filter(tenant=self.tenant)
            self.fields["kpi"].queryset = KpiDefinition.objects.filter(tenant=self.tenant)
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant)
            self.fields["glossary_term"].queryset = BusinessGlossaryTerm.objects.filter(tenant=self.tenant)
        self.fields["semantic_model"].required = False
        self.fields["dashboard"].required = False
        self.fields["report"].required = False
        self.fields["kpi"].required = False
        self.fields["warehouse_table"].required = False
        self.fields["glossary_term"].required = False

    def clean_target_url(self):
        url = self.cleaned_data.get("target_url", "").strip()
        if url:
            if url.startswith("//"):
                raise ValidationError("Protocol-relative URLs are not allowed.")
            if not (url.startswith("/") or url.startswith("http://") or url.startswith("https://")):
                raise ValidationError("Target URL must start with a leading slash '/' or valid HTTP(S) scheme.")
        return url

    def clean_synonyms(self):
        val = self.cleaned_data.get("synonyms")
        if not val:
            return []
        if isinstance(val, list):
            return [str(item).strip() for item in val if str(item).strip()]
        if isinstance(val, str):
            val_str = val.strip()
            if not val_str:
                return []
            if val_str.startswith("["):
                try:
                    parsed = json.loads(val_str)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except (json.JSONDecodeError, ValueError):
                    pass
            # Comma-separated fallback
            return [tok.strip() for tok in val_str.split(",") if tok.strip()]
        return []

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["semantic_model", "dashboard", "report", "kpi", "warehouse_table", "glossary_term"],
        )
        return cleaned_data
