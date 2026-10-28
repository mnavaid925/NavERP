"""Sales 8.18 — SalesIntegrationConnector forms."""
from django import forms

from apps.core.forms import TenantModelForm
from apps.sales.models.IntegrationApiHub.Connectors import SalesIntegrationConnector


class SalesIntegrationConnectorForm(TenantModelForm):
    credential_input = forms.CharField(
        label="API Key / Secret Token",
        required=False,
        widget=forms.PasswordInput(
            render_value=False,
            attrs={"class": "form-input", "placeholder": "Enter secret to set or change"},
        ),
        help_text="Stored with Fernet encryption at rest. Leave blank to preserve existing credentials.",
    )

    class Meta:
        model = SalesIntegrationConnector
        fields = [
            "name",
            "category",
            "provider",
            "environment",
            "base_url",
            "auth_method",
            "remote_scope_ref",
            "health_status",
            "is_active",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Corporate SAP S/4HANA"}),
            "category": forms.Select(attrs={"class": "form-select"}),
            "provider": forms.Select(attrs={"class": "form-select"}),
            "environment": forms.Select(attrs={"class": "form-select"}),
            "base_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://api.sap.example.com/v1"}),
            "auth_method": forms.Select(attrs={"class": "form-select"}),
            "remote_scope_ref": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. client_100 or workspace_prod"}),
            "health_status": forms.Select(attrs={"class": "form-select"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw_secret = self.cleaned_data.get("credential_input")
        if raw_secret:
            instance.set_credential(raw_secret)
        if commit:
            instance.save()
        return instance
