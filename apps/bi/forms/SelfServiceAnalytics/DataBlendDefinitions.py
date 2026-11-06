import json
from django import forms
from django.utils.text import slugify

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SelfServiceAnalytics.DataBlendDefinitions import DataBlendDefinition
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class DataBlendDefinitionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DataBlendDefinition
        fields = [
            "name",
            "slug",
            "description",
            "primary_source_type",
            "primary_semantic_model",
            "primary_warehouse_table",
            "secondary_source_type",
            "secondary_semantic_model",
            "secondary_warehouse_table",
            "join_type",
            "join_keys_mapping_json",
            "cardinality",
            "collision_resolution",
            "status",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Sales Opportunities & Procurement Orders Blend"}),
            "slug": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. sales-procurement-blend"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 2, "placeholder": "Analytical objective of this multi-source mashup..."}),
            "primary_source_type": forms.Select(attrs={"class": "form-select"}),
            "primary_semantic_model": forms.Select(attrs={"class": "form-select"}),
            "primary_warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "secondary_source_type": forms.Select(attrs={"class": "form-select"}),
            "secondary_semantic_model": forms.Select(attrs={"class": "form-select"}),
            "secondary_warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "join_type": forms.Select(attrs={"class": "form-select"}),
            "join_keys_mapping_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 3, "placeholder": '[{"primary_field": "customer_id", "secondary_field": "account_id"}]'}),
            "cardinality": forms.Select(attrs={"class": "form-select"}),
            "collision_resolution": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. prefix_secondary"}),
            "status": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "slug" in self.fields:
            self.fields["slug"].required = False
        if "join_keys_mapping_json" in self.fields:
            self.fields["join_keys_mapping_json"].required = False

        if self.tenant is not None:
            active_smdl = SemanticModel.objects.filter(tenant=self.tenant, is_active=True)
            active_wtbl = WarehouseTable.objects.filter(tenant=self.tenant, is_active=True)
            if "primary_semantic_model" in self.fields:
                self.fields["primary_semantic_model"].queryset = active_smdl
            if "secondary_semantic_model" in self.fields:
                self.fields["secondary_semantic_model"].queryset = active_smdl
            if "primary_warehouse_table" in self.fields:
                self.fields["primary_warehouse_table"].queryset = active_wtbl
            if "secondary_warehouse_table" in self.fields:
                self.fields["secondary_warehouse_table"].queryset = active_wtbl

    def clean_join_keys_mapping_json(self):
        val = self.cleaned_data.get("join_keys_mapping_json")
        if isinstance(val, str):
            try:
                return json.loads(val) if val.strip() else []
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(f"Invalid JSON in join keys mapping: {exc}")
        return val or []

    def clean(self):
        cleaned = super().clean()
        reject_foreign(
            self,
            cleaned,
            ["primary_semantic_model", "secondary_semantic_model", "primary_warehouse_table", "secondary_warehouse_table"],
        )
        name = cleaned.get("name")
        slug = cleaned.get("slug")
        if not slug and name:
            cleaned["slug"] = slugify(name)[:100] or "blend"
        return cleaned
