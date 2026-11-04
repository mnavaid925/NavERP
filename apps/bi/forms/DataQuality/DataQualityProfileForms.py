from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataQuality.DataQualityProfiles import DataQualityProfile
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class DataQualityProfileForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DataQualityProfile
        fields = [
            "name",
            "target_type",
            "warehouse_table",
            "semantic_model",
            "notes",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Sales Fact Data Profiling"}),
            "target_type": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Optional profiling scope or objectives"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant).order_by("name")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["warehouse_table", "semantic_model"])
        target_type = cleaned.get("target_type")
        warehouse_table = cleaned.get("warehouse_table")
        semantic_model = cleaned.get("semantic_model")
        if target_type == "warehouse_table" and not warehouse_table:
            self.add_error("warehouse_table", "A warehouse table must be selected when target type is Warehouse Table.")
        elif target_type == "semantic_model" and not semantic_model:
            self.add_error("semantic_model", "A semantic model must be selected when target type is Semantic Model.")
        return cleaned
