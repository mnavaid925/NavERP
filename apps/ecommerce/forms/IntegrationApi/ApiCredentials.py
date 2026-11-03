from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin
from apps.ecommerce.models.IntegrationApi.ApiCredentials import ApiCredential


class ApiCredentialForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ApiCredential
        exclude = [
            "tenant",
            "number",
            "client_id",
            "client_secret_hash",
            "secret_prefix",
            "total_requests_count",
            "last_used_at",
            "revoked_at",
            "created_by",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "e.g. Next.js Headless Web Storefront",
                }
            ),
            "tier": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "scopes": forms.TextInput(
                attrs={
                    "class": "form-input font-mono text-xs",
                    "placeholder": "read_catalog,read_orders,write_orders",
                }
            ),
            "allowed_origins": forms.Textarea(
                attrs={
                    "class": "form-textarea font-mono text-xs",
                    "rows": 2,
                    "placeholder": "https://myshop.com, https://app.myshop.com (or * for public storefront)",
                }
            ),
            "allowed_ips": forms.Textarea(
                attrs={
                    "class": "form-textarea font-mono text-xs",
                    "rows": 2,
                    "placeholder": "192.168.1.0/24 (one CIDR per line, or blank for all)",
                }
            ),
            "rate_limit_rpm": forms.NumberInput(
                attrs={"class": "form-input", "placeholder": "120"}
            ),
            "expires_at": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-input"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 2,
                    "placeholder": "Consumer application notes and partner ownership...",
                }
            ),
        }

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if not name:
            raise forms.ValidationError("Credential client name is required.")
        return name

    def clean_rate_limit_rpm(self):
        val = self.cleaned_data.get("rate_limit_rpm")
        if val is not None and val < 1:
            raise forms.ValidationError("Rate limit must be at least 1 request/minute.")
        return val
