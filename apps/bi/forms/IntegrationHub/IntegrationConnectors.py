import json

from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin
from apps.bi.models.IntegrationHub.IntegrationConnectors import IntegrationConnector
from apps.core.forms import TenantModelForm


class IntegrationConnectorForm(TenantUniqueMixin, TenantModelForm):
    connection_config_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "class": "form-textarea font-mono text-xs",
                "placeholder": '{\n  "bootstrap_servers": "kafka.internal:9092",\n  "topic": "erp.finance.events",\n  "batch_size": 500\n}',
            }
        ),
        label="Connection Configuration (JSON)",
        help_text="Host connection parameters, topics, endpoints, and timeouts in valid JSON",
    )

    auth_credentials_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "class": "form-textarea font-mono text-xs",
                "placeholder": '{\n  "api_key": "sec_live_...",\n  "secret_header": "X-API-Key"\n}',
            }
        ),
        label="Authentication Credentials (JSON)",
        help_text="API keys, bearer tokens, or client credentials stored securely",
    )

    class Meta:
        model = IntegrationConnector
        fields = [
            "name",
            "slug",
            "description",
            "connector_type",
            "target_system",
            "sync_direction",
            "auth_type",
            "message_format",
            "sync_interval",
            "status",
            "is_enabled",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Finance GL Reverse ETL"}
            ),
            "slug": forms.TextInput(
                attrs={"class": "form-input font-mono", "placeholder": "finance-gl-reverse-etl"}
            ),
            "description": forms.Textarea(
                attrs={"class": "form-textarea", "rows": 3, "placeholder": "Operational objectives and payload description..."}
            ),
            "connector_type": forms.Select(attrs={"class": "form-select"}),
            "target_system": forms.Select(attrs={"class": "form-select"}),
            "sync_direction": forms.Select(attrs={"class": "form-select"}),
            "auth_type": forms.Select(attrs={"class": "form-select"}),
            "message_format": forms.Select(attrs={"class": "form-select"}),
            "sync_interval": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "is_enabled": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.connection_config:
                self.fields["connection_config_raw"].initial = json.dumps(
                    self.instance.connection_config, indent=2
                )
            # Do NOT populate auth_credentials_raw on edit to prevent exposing cleartext secrets (Rule L20)

    def clean_connection_config_raw(self):
        data = (self.cleaned_data.get("connection_config_raw") or "").strip()
        if not data:
            return {}
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValidationError("Connection configuration must be a JSON object (dictionary).")
            return parsed
        except json.JSONDecodeError as err:
            raise ValidationError(f"Invalid JSON syntax in connection configuration: {err}")

    def clean_auth_credentials_raw(self):
        data = (self.cleaned_data.get("auth_credentials_raw") or "").strip()
        if not data:
            return None
        try:
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ValidationError("Authentication credentials must be a JSON object (dictionary).")
            return parsed
        except json.JSONDecodeError as err:
            raise ValidationError(f"Invalid JSON syntax in credentials: {err}")

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.connection_config = self.cleaned_data.get("connection_config_raw") or {}
        new_creds = self.cleaned_data.get("auth_credentials_raw")
        if new_creds is not None:
            instance.auth_credentials = new_creds
        elif not instance.pk:
            instance.auth_credentials = {}
        if commit:
            instance.save()
        return instance
