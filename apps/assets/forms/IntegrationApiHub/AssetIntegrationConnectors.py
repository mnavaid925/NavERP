from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.accounting.models import Currency
from apps.assets.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    reject_foreign,
)
from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import (
    AssetIntegrationConnector,
    validate_connector_endpoint_url,
)
from apps.core.models import OrgUnit, Party

User = get_user_model()


class AssetIntegrationConnectorForm(TenantUniqueMixin, TenantModelForm):
    """Create and edit form for Asset Integration Connectors with SSRF and tenant guards."""

    class Meta:
        model = AssetIntegrationConnector
        fields = [
            "name",
            "connector_category",
            "provider",
            "protocol",
            "sync_direction",
            "environment",
            "endpoint_url",
            "auth_method",
            "rate_limit_rpm",
            "timeout_seconds",
            "retry_policy_max",
            "polling_interval_minutes",
            "status",
            "vendor_partner",
            "default_org_unit",
            "default_currency",
            "owner",
            "webhook_verify_tls",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. SAP S/4HANA Production Asset Ledger",
                }
            ),
            "connector_category": forms.Select(attrs={"class": "form-select"}),
            "provider": forms.Select(attrs={"class": "form-select"}),
            "protocol": forms.Select(attrs={"class": "form-select"}),
            "sync_direction": forms.Select(attrs={"class": "form-select"}),
            "environment": forms.Select(attrs={"class": "form-select"}),
            "endpoint_url": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "https://api-erp.example.com/odata/v4 or opc.tcp://scada.example.com:4840",
                }
            ),
            "auth_method": forms.Select(attrs={"class": "form-select"}),
            "rate_limit_rpm": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "timeout_seconds": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "retry_policy_max": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "polling_interval_minutes": forms.NumberInput(
                attrs={"class": "form-input", "min": 1}
            ),
            "status": forms.Select(attrs={"class": "form-select"}),
            "vendor_partner": forms.Select(attrs={"class": "form-select"}),
            "default_org_unit": forms.Select(attrs={"class": "form-select"}),
            "default_currency": forms.Select(attrs={"class": "form-select"}),
            "owner": forms.Select(attrs={"class": "form-select"}),
            "webhook_verify_tls": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Authentication notes, IP allowlists, failover instructions...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["vendor_partner"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["default_org_unit"].queryset = OrgUnit.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["owner"].queryset = User.objects.filter(
                tenant=self.tenant
            ).order_by("username")
        else:
            self.fields["vendor_partner"].queryset = Party.objects.none()
            self.fields["default_org_unit"].queryset = OrgUnit.objects.none()
            self.fields["owner"].queryset = User.objects.none()

        if self.instance and self.instance.default_currency_id:
            self.fields["default_currency"].queryset = Currency.objects.filter(
                Q(is_active=True) | Q(pk=self.instance.default_currency_id)
            ).order_by("code")
        else:
            self.fields["default_currency"].queryset = Currency.objects.filter(
                is_active=True
            ).order_by("code")

        for optional_field in (
            "vendor_partner",
            "default_org_unit",
            "default_currency",
            "owner",
            "notes",
        ):
            self.fields[optional_field].required = False

    def clean_endpoint_url(self):
        return validate_connector_endpoint_url(self.cleaned_data.get("endpoint_url"))

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(
            self,
            cleaned_data,
            ["vendor_partner", "default_org_unit", "owner"],
        )
        if (cleaned_data.get("rate_limit_rpm") or 0) < 1:
            self.add_error(
                "rate_limit_rpm", "Rate limit must be at least 1 request per minute."
            )
        if (cleaned_data.get("timeout_seconds") or 0) < 1:
            self.add_error("timeout_seconds", "Timeout must be at least 1 second.")
        if (cleaned_data.get("polling_interval_minutes") or 0) < 1:
            self.add_error(
                "polling_interval_minutes",
                "Polling interval must be at least 1 minute.",
            )
        return cleaned_data
