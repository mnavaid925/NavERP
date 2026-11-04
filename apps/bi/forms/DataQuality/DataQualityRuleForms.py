import json
from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataQuality.DataQualityRules import DataQualityRule
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class DataQualityRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DataQualityRule
        fields = [
            "name",
            "code",
            "rule_category",
            "dimension",
            "target_type",
            "warehouse_table",
            "semantic_model",
            "target_column",
            "rule_type",
            "parameters_json",
            "severity",
            "failure_tolerance_pct",
            "steward",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Sales Amount Positive Check"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. sales_amount_positive"}),
            "rule_category": forms.Select(attrs={"class": "form-select"}),
            "dimension": forms.Select(attrs={"class": "form-select"}),
            "target_type": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "target_column": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. total_amount"}),
            "rule_type": forms.Select(attrs={"class": "form-select"}),
            "parameters_json": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4, "placeholder": '{"min_value": 0, "max_value": 1000000}'}),
            "severity": forms.Select(attrs={"class": "form-select"}),
            "failure_tolerance_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "0.00"}),
            "steward": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Business context and rule intent"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant).order_by("name")
            user_qs = get_user_model().objects.filter(tenant=self.tenant)
            steward_filter = Q(is_active=True)
            if self.instance and self.instance.pk and self.instance.steward_id:
                steward_filter |= Q(pk=self.instance.steward_id)
            self.fields["steward"].queryset = user_qs.filter(steward_filter).order_by("first_name", "username")

    def clean_parameters_json(self):
        val = self.cleaned_data.get("parameters_json")
        if isinstance(val, str):
            val_str = val.strip()
            if not val_str:
                return {}
            try:
                return json.loads(val_str)
            except json.JSONDecodeError as exc:
                raise forms.ValidationError(f"Invalid JSON configuration: {exc}")
        return val or {}

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["warehouse_table", "semantic_model", "steward"])
        target_type = cleaned.get("target_type")
        warehouse_table = cleaned.get("warehouse_table")
        semantic_model = cleaned.get("semantic_model")
        if target_type == "warehouse_table" and not warehouse_table:
            self.add_error("warehouse_table", "A warehouse table must be selected when target type is Warehouse Table.")
        elif target_type == "semantic_model" and not semantic_model:
            self.add_error("semantic_model", "A semantic model must be selected when target type is Semantic Model.")
        return cleaned
