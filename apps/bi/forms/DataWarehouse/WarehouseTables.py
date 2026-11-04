import json

from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataWarehouse.DataMarts import DataMart
from apps.bi.models.DataWarehouse.LakehouseZones import LakehouseZone
from apps.bi.models.DataWarehouse.WarehouseStoragePolicies import WarehouseStoragePolicy
from apps.bi.models.DataWarehouse.WarehouseTables import WarehouseTable
from apps.core.forms import TenantModelForm


class WarehouseTableForm(TenantUniqueMixin, TenantModelForm):
    schema_definition_raw = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-textarea font-mono text-xs",
                "rows": 8,
                "placeholder": '[{"name": "entry_sk", "type": "BIGINT", "nullable": false},\n {"name": "account_sk", "type": "INTEGER", "nullable": false},\n {"name": "amount", "type": "NUMERIC(18,2)", "nullable": false}]',
            }
        ),
        required=False,
        label="Schema Column Definitions (JSON Array)",
        help_text="Define column names, SQL types, and nullability constraints in JSON array format.",
    )

    class Meta:
        model = WarehouseTable
        fields = [
            "name",
            "table_name",
            "table_type",
            "schema_type",
            "grain",
            "lakehouse_zone",
            "data_mart",
            "storage_policy",
            "primary_key_column",
            "natural_key_column",
            "is_conformed_dimension",
            "description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Fact General Ledger Journal Entries"}),
            "table_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. fact_gl_journal_entries"}),
            "table_type": forms.Select(attrs={"class": "form-select"}),
            "schema_type": forms.Select(attrs={"class": "form-select"}),
            "grain": forms.Select(attrs={"class": "form-select"}),
            "lakehouse_zone": forms.Select(attrs={"class": "form-select"}),
            "data_mart": forms.Select(attrs={"class": "form-select"}),
            "storage_policy": forms.Select(attrs={"class": "form-select"}),
            "primary_key_column": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. entry_sk, id"}),
            "natural_key_column": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. journal_number, code"}),
            "is_conformed_dimension": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Data grain, business definitions, upstream pipelines..."}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["lakehouse_zone"].queryset = LakehouseZone.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("zone_type", "name")
            self.fields["data_mart"].queryset = DataMart.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")
            self.fields["storage_policy"].queryset = WarehouseStoragePolicy.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("name")

        if self.instance and self.instance.pk and self.instance.schema_definition:
            self.fields["schema_definition_raw"].initial = json.dumps(
                self.instance.schema_definition, indent=2
            )

    def clean_table_name(self):
        name = self.cleaned_data.get("table_name", "").strip().lower()
        if name:
            existing = WarehouseTable.objects.filter(tenant=self.tenant, table_name=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise forms.ValidationError("A warehouse table with this physical table name already exists in your workspace.")
        return name

    def clean_schema_definition_raw(self):
        raw = self.cleaned_data.get("schema_definition_raw", "").strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, list):
                raise forms.ValidationError("Schema definition must be a JSON array of column objects.")
            for item in parsed:
                if not isinstance(item, dict) or "name" not in item:
                    raise forms.ValidationError("Each item in the schema definition must be a dictionary containing at least a 'name' key.")
            return parsed
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON format: {exc.msg}")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["lakehouse_zone", "data_mart", "storage_policy"])
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "schema_definition_raw" in self.cleaned_data:
            instance.schema_definition = self.cleaned_data["schema_definition_raw"]
        if commit:
            instance.save()
        return instance
