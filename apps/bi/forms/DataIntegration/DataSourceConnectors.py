import json

from django import forms

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.DataIntegration.DataSourceConnectors import DataSourceConnector
from apps.core.models.Integration import ApiCredential


class DataSourceConnectorForm(TenantUniqueMixin, forms.ModelForm):
    connection_config_raw = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea font-mono text-xs", "rows": 4}),
        required=False,
        label="Connection Configuration (JSON)",
        help_text="Host, port, database name, bucket, credentials, or custom query options in valid JSON format.",
    )

    class Meta:
        model = DataSourceConnector
        fields = [
            "name",
            "connector_type",
            "status",
            "credential",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Production PostgreSQL ERP Replica"}),
            "connector_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "credential": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Documentation or operational notes for this data source"}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["credential"].queryset = ApiCredential.objects.filter(tenant=self.tenant)
        if self.instance and self.instance.pk and self.instance.connection_config:
            self.fields["connection_config_raw"].initial = json.dumps(self.instance.connection_config, indent=2)

    def clean_connection_config_raw(self):
        raw = self.cleaned_data.get("connection_config_raw", "").strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise forms.ValidationError("Connection configuration must be a valid JSON object/dictionary.")
            return parsed
        except json.JSONDecodeError as err:
            raise forms.ValidationError(f"Invalid JSON syntax: {err}")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["credential"])
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if "connection_config_raw" in self.cleaned_data:
            instance.connection_config = self.cleaned_data["connection_config_raw"]
        if self.tenant and not instance.tenant_id:
            instance.tenant = self.tenant
        if commit:
            instance.save()
            self.save_m2m()
        return instance
