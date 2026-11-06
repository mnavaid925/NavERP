import json
from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.OlapAnalysis.OlapCubes import OlapCube
from apps.bi.models.SemanticLayer.DrillHierarchies import DrillHierarchy
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class OlapCubeForm(TenantUniqueMixin, TenantModelForm):
    dimensions_config_raw = forms.CharField(
        label="Dimensions Configuration (JSON)",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="List of dimensions with attribute names, types, and hierarchy levels",
    )
    measures_config_raw = forms.CharField(
        label="Measures Configuration (JSON)",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="List of measures with formulas, aggregations, and display formats",
    )
    aggregations_config_raw = forms.CharField(
        label="Pre-Aggregated Cuboids (JSON)",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea font-mono text-xs"}),
        required=False,
        help_text="List of dimension combinations for pre-calculated summary rollups",
    )

    class Meta:
        model = OlapCube
        fields = [
            "name",
            "slug",
            "description",
            "storage_mode",
            "semantic_model",
            "warehouse_table",
            "default_hierarchy",
            "time_intelligence_enabled",
            "cache_ttl_minutes",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Revenue & Margin Cube"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "auto-generated-if-blank"}),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
            "storage_mode": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "default_hierarchy": forms.Select(attrs={"class": "form-select"}),
            "cache_ttl_minutes": forms.NumberInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        if "data" in kwargs and kwargs["data"]:
            data = kwargs["data"].copy()
            if "dimensions_config" in data and "dimensions_config_raw" not in data:
                data["dimensions_config_raw"] = json.dumps(data["dimensions_config"]) if isinstance(data["dimensions_config"], list) else str(data["dimensions_config"])
            if "measures_config" in data and "measures_config_raw" not in data:
                data["measures_config_raw"] = json.dumps(data["measures_config"]) if isinstance(data["measures_config"], list) else str(data["measures_config"])
            if "aggregations_config" in data and "aggregations_config_raw" not in data:
                data["aggregations_config_raw"] = json.dumps(data["aggregations_config"]) if isinstance(data["aggregations_config"], list) else str(data["aggregations_config"])
            kwargs["data"] = data
        elif len(args) > 0 and args[0]:
            data = args[0].copy()
            if "dimensions_config" in data and "dimensions_config_raw" not in data:
                data["dimensions_config_raw"] = json.dumps(data["dimensions_config"]) if isinstance(data["dimensions_config"], list) else str(data["dimensions_config"])
            if "measures_config" in data and "measures_config_raw" not in data:
                data["measures_config_raw"] = json.dumps(data["measures_config"]) if isinstance(data["measures_config"], list) else str(data["measures_config"])
            if "aggregations_config" in data and "aggregations_config_raw" not in data:
                data["aggregations_config_raw"] = json.dumps(data["aggregations_config"]) if isinstance(data["aggregations_config"], list) else str(data["aggregations_config"])
            args = (data,) + args[1:]

        super().__init__(*args, **kwargs)
        if "slug" in self.fields:
            self.fields["slug"].required = False
        if "cache_ttl_minutes" in self.fields:
            self.fields["cache_ttl_minutes"].required = False
        if self.tenant is not None:
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant)
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant)
            self.fields["default_hierarchy"].queryset = DrillHierarchy.objects.filter(tenant=self.tenant)

        if self.instance and self.instance.pk:
            if self.instance.dimensions_config:
                self.fields["dimensions_config_raw"].initial = json.dumps(self.instance.dimensions_config, indent=2)
            if self.instance.measures_config:
                self.fields["measures_config_raw"].initial = json.dumps(self.instance.measures_config, indent=2)
            if self.instance.aggregations_config:
                self.fields["aggregations_config_raw"].initial = json.dumps(self.instance.aggregations_config, indent=2)
        else:
            self.fields["dimensions_config_raw"].initial = json.dumps([
                {"name": "FiscalPeriod", "type": "time", "levels": ["Year", "Quarter", "Month"]},
                {"name": "OrgUnit", "type": "organization", "levels": ["Company", "Division", "Department"]},
                {"name": "GLAccount", "type": "financial", "levels": ["Class", "Group", "Account"]},
            ], indent=2)
            self.fields["measures_config_raw"].initial = json.dumps([
                {"name": "NetRevenue", "aggregation": "sum", "format": "$#,##0.00"},
                {"name": "TotalExpenses", "aggregation": "sum", "format": "$#,##0.00"},
                {"name": "OperatingMargin", "formula": "[NetRevenue] - [TotalExpenses]", "format": "$#,##0.00"},
            ], indent=2)
            self.fields["aggregations_config_raw"].initial = json.dumps([
                ["FiscalPeriod", "OrgUnit"],
                ["FiscalPeriod", "GLAccount"],
            ], indent=2)

    def clean_dimensions_config_raw(self):
        val = self.cleaned_data.get("dimensions_config_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Dimensions config must be a JSON array of dimensions.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean_measures_config_raw(self):
        val = self.cleaned_data.get("measures_config_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Measures config must be a JSON array of measures.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean_aggregations_config_raw(self):
        val = self.cleaned_data.get("aggregations_config_raw", "").strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Aggregations config must be a JSON array of dimension sets.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["semantic_model", "warehouse_table", "default_hierarchy"])
        if cleaned.get("name") and not cleaned.get("slug"):
            from django.utils.text import slugify
            base_slug = slugify(cleaned["name"]) or "cube"
            slug = base_slug[:120]
            cleaned["slug"] = slug
            self.instance.slug = slug
        if cleaned.get("cache_ttl_minutes") in (None, ""):
            cleaned["cache_ttl_minutes"] = 60
            self.instance.cache_ttl_minutes = 60
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "dimensions_config_raw" in self.cleaned_data:
            instance.dimensions_config = self.cleaned_data["dimensions_config_raw"]
        if "measures_config_raw" in self.cleaned_data:
            instance.measures_config = self.cleaned_data["measures_config_raw"]
        if "aggregations_config_raw" in self.cleaned_data:
            instance.aggregations_config = self.cleaned_data["aggregations_config_raw"]
        if commit:
            instance.save()
        return instance
