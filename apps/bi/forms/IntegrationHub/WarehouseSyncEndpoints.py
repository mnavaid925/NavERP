import json

from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataWarehouse.DataMarts import DataMart
from apps.bi.models.IntegrationHub.WarehouseSyncEndpoints import WarehouseSyncEndpoint
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.forms import TenantModelForm


class WarehouseSyncEndpointForm(TenantUniqueMixin, TenantModelForm):
    connection_config_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "form-textarea font-mono text-xs",
                "placeholder": '{\n  "account_identifier": "xy12345.us-east-1",\n  "warehouse_name": "COMPUTE_WH",\n  "role": "DATA_ANALYST"\n}',
            }
        ),
        label="Cloud Warehouse Configuration (JSON)",
        help_text="Warehouse endpoint parameters, account IDs, and roles in valid JSON",
    )

    class Meta:
        model = WarehouseSyncEndpoint
        fields = [
            "name",
            "slug",
            "target_warehouse",
            "sync_mode",
            "semantic_model",
            "data_mart",
            "destination_database",
            "destination_schema",
            "destination_table",
            "auth_method",
            "sync_schedule",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Snowflake Customer Metrics Mart"}
            ),
            "slug": forms.TextInput(
                attrs={"class": "form-input font-mono", "placeholder": "snowflake-customer-mart"}
            ),
            "target_warehouse": forms.Select(attrs={"class": "form-select"}),
            "sync_mode": forms.Select(attrs={"class": "form-select"}),
            "semantic_model": forms.Select(attrs={"class": "form-select"}),
            "data_mart": forms.Select(attrs={"class": "form-select"}),
            "destination_database": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "ANALYTICS_PROD"}
            ),
            "destination_schema": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "NAVERP_EXPORTS"}
            ),
            "destination_table": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "DIM_CUSTOMERS"}
            ),
            "auth_method": forms.Select(attrs={"class": "form-select"}),
            "sync_schedule": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["semantic_model"].queryset = SemanticModel.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["data_mart"].queryset = DataMart.objects.filter(
                tenant=self.tenant
            ).order_by("name")
        else:
            self.fields["semantic_model"].queryset = SemanticModel.objects.none()
            self.fields["data_mart"].queryset = DataMart.objects.none()

        if self.instance and self.instance.pk and self.instance.connection_config:
            self.fields["connection_config_raw"].initial = json.dumps(
                self.instance.connection_config, indent=2
            )

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["semantic_model", "data_mart"])
        return cleaned_data

    def clean_connection_config_raw(self):
        data = self.cleaned_data.get("connection_config_raw", "").strip()
        if not data:
            return {}
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValidationError("Connection configuration must be a JSON object (dictionary).")
            return parsed
        except json.JSONDecodeError as err:
            raise ValidationError(f"Invalid JSON syntax in connection configuration: {err}")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.connection_config = self.cleaned_data.get("connection_config_raw") or {}
        if commit:
            instance.save()
        return instance
