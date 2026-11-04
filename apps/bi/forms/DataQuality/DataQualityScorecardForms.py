from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataQuality.DataQualityScorecards import DataQualityScorecard
from apps.bi.models.DataWarehouse.DataMarts import DataMart
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm
from apps.core.models.OrgUnit import OrgUnit


class DataQualityScorecardForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = DataQualityScorecard
        fields = [
            "name",
            "code",
            "scope_type",
            "warehouse_table",
            "semantic_model",
            "data_mart",
            "org_unit",
            "target_quality_score",
            "evaluation_period",
            "steward",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Sales Data Quality Scorecard"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. sales_data_quality"}),
            "scope_type": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "data_mart": forms.Select(attrs={"class": "form-select"}),
            "org_unit": forms.Select(attrs={"class": "form-select"}),
            "target_quality_score": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "placeholder": "95.00"}),
            "evaluation_period": forms.Select(attrs={"class": "form-select"}),
            "steward": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Executive context, SLA criteria, and scope description"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["data_mart"].queryset = DataMart.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["org_unit"].queryset = OrgUnit.objects.filter(tenant=self.tenant).order_by("name")
            user_qs = get_user_model().objects.filter(tenant=self.tenant)
            steward_filter = Q(is_active=True)
            if self.instance and self.instance.pk and self.instance.steward_id:
                steward_filter |= Q(pk=self.instance.steward_id)
            self.fields["steward"].queryset = user_qs.filter(steward_filter).order_by("first_name", "username")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["warehouse_table", "semantic_model", "data_mart", "org_unit", "steward"])
        scope_type = cleaned.get("scope_type")
        if scope_type == "warehouse_table" and not cleaned.get("warehouse_table"):
            self.add_error("warehouse_table", "A warehouse table is required when scope is Warehouse Table.")
        elif scope_type == "semantic_model" and not cleaned.get("semantic_model"):
            self.add_error("semantic_model", "A semantic model is required when scope is Semantic Model.")
        elif scope_type == "data_mart" and not cleaned.get("data_mart"):
            self.add_error("data_mart", "A data mart is required when scope is Data Mart Domain.")
        return cleaned
