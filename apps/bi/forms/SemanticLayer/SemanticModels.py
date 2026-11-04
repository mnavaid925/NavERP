from django import forms
from django.contrib.auth import get_user_model

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataWarehouse.DataMarts import DataMart
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class SemanticModelForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = SemanticModel
        fields = [
            "name",
            "code",
            "model_type",
            "warehouse_table",
            "data_mart",
            "primary_key_column",
            "natural_key_columns",
            "grain_description",
            "is_conformed_dimension",
            "scd_type",
            "is_virtual_view",
            "sql_definition",
            "access_tier",
            "certification_status",
            "owner",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Sales Performance Analytics"}),
            "code": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. sales_performance"}),
            "model_type": forms.Select(attrs={"class": "form-select"}),
            "warehouse_table": forms.Select(attrs={"class": "form-select"}),
            "data_mart": forms.Select(attrs={"class": "form-select"}),
            "primary_key_column": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "id"}),
            "natural_key_columns": forms.TextInput(attrs={"class": "form-input font-mono text-sm", "placeholder": "e.g. invoice_number, line_no"}),
            "grain_description": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. One row per posted invoice line item"}),
            "is_conformed_dimension": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "scd_type": forms.Select(attrs={"class": "form-select"}),
            "is_virtual_view": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "sql_definition": forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 5, "placeholder": "SELECT ... FROM ..."}),
            "access_tier": forms.Select(attrs={"class": "form-select"}),
            "certification_status": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["warehouse_table"].queryset = WarehouseTable.objects.filter(tenant=self.tenant)
            self.fields["data_mart"].queryset = DataMart.objects.filter(tenant=self.tenant)
            self.fields["owner"].queryset = get_user_model().objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["warehouse_table", "data_mart"])
        return cleaned_data


class SemanticModelCertificationForm(forms.Form):
    certification_status = forms.ChoiceField(
        choices=SemanticModel.CERTIFICATION_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    certification_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-textarea", "rows": 3, "placeholder": "Reason or sign-off notes for status transition..."}
        ),
    )
