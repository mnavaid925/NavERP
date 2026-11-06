import json
from django import forms
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.SelfServiceAnalytics.AdHocQueries import AdHocQuery
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SelfServiceAnalytics.DataBlendDefinitions import DataBlendDefinition
from apps.core.forms import TenantModelForm


class AdHocQueryForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AdHocQuery
        fields = [
            "name",
            "slug",
            "description",
            "source_type",
            "semantic_model",
            "warehouse_table",
            "data_blend",
            "visualization_type",
            "row_limit",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Sales Margin by Region 2026"}),
            "slug": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. sales-margin-by-region"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Purpose and hypothesis of this ad-hoc analysis..."}),
            "source_type": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "data_blend": forms.Select(attrs={"class": "form-select"}),
            "visualization_type": forms.Select(attrs={"class": "form-select"}),
            "row_limit": forms.NumberInput(attrs={"class": "form-input", "step": 50, "min": 10, "max": 10000}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "slug" in self.fields:
            self.fields["slug"].required = False

        if self.tenant is not None:
            if "semantic_model" in self.fields:
                self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant, is_active=True)
            if "warehouse_table" in self.fields:
                self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant, is_active=True)
            if "data_blend" in self.fields:
                self.fields["data_blend"].queryset = DataBlendDefinition.objects.filter(tenant=self.tenant, status="active")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["semantic_model", "warehouse_table", "data_blend"])
        name = cleaned.get("name")
        slug = cleaned.get("slug")
        if not slug and name:
            cleaned["slug"] = slugify(name)[:100] or "query"
        return cleaned


class AdHocQueryComposerForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AdHocQuery
        fields = [
            "name",
            "slug",
            "description",
            "source_type",
            "semantic_model",
            "warehouse_table",
            "data_blend",
            "fields_config_json",
            "filter_criteria_json",
            "sort_config_json",
            "visualization_type",
            "chart_config_json",
            "row_limit",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Product Sales vs Returns Exploration"}),
            "slug": forms.TextInput(attrs={"class": "form-input font-mono text-sm"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "source_type": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "data_blend": forms.Select(attrs={"class": "form-select"}),
            "fields_config_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4}),
            "filter_criteria_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
            "sort_config_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 2}),
            "visualization_type": forms.Select(attrs={"class": "form-select"}),
            "chart_config_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3}),
            "row_limit": forms.NumberInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "slug" in self.fields:
            self.fields["slug"].required = False
        for f in ["fields_config_json", "filter_criteria_json", "sort_config_json", "chart_config_json"]:
            if f in self.fields:
                self.fields[f].required = False

        if self.tenant is not None:
            if "semantic_model" in self.fields:
                self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant, is_active=True)
            if "warehouse_table" in self.fields:
                self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant, is_active=True)
            if "data_blend" in self.fields:
                self.fields["data_blend"].queryset = DataBlendDefinition.objects.filter(tenant=self.tenant, status="active")

    def clean_fields_config_json(self):
        val = self.cleaned_data.get("fields_config_json")
        if isinstance(val, str):
            try:
                return json.loads(val) if val.strip() else []
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(f"Invalid JSON in fields config: {exc}")
        return val or []

    def clean_filter_criteria_json(self):
        val = self.cleaned_data.get("filter_criteria_json")
        if isinstance(val, str):
            try:
                return json.loads(val) if val.strip() else []
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(f"Invalid JSON in filter criteria: {exc}")
        return val or []

    def clean_sort_config_json(self):
        val = self.cleaned_data.get("sort_config_json")
        if isinstance(val, str):
            try:
                return json.loads(val) if val.strip() else []
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(f"Invalid JSON in sort config: {exc}")
        return val or []

    def clean_chart_config_json(self):
        val = self.cleaned_data.get("chart_config_json")
        if isinstance(val, str):
            try:
                return json.loads(val) if val.strip() else {}
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(f"Invalid JSON in chart config: {exc}")
        return val or {}

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["semantic_model", "warehouse_table", "data_blend"])
        name = cleaned.get("name")
        slug = cleaned.get("slug")
        if not slug and name:
            cleaned["slug"] = slugify(name)[:100] or "query"
        return cleaned
