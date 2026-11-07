import json

from django import forms
from django.core.exceptions import ValidationError

from apps.bi.forms._common import TenantUniqueMixin, reject_foreign
from apps.bi.models.EmbeddedMobileBi.EmbedApiTokens import EmbedApiToken
from apps.bi.models.EmbeddedMobileBi.EmbeddedAnalyticsConfigs import EmbeddedAnalyticsConfig
from apps.core.forms import TenantModelForm


class EmbedApiTokenForm(TenantUniqueMixin, TenantModelForm):
    scopes_raw = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input font-mono text-xs"}),
        label="Granted Permission Scopes (comma-separated or JSON list)",
        help_text="e.g. read:dashboard, read:report, embed:view, query:data",
        initial="read:dashboard, embed:view, query:data",
    )
    injected_rls_context_raw = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-textarea font-mono text-xs"}),
        label="Injected Row-Level Security Context (JSON)",
        help_text='JSON dictionary of attribute constraints, e.g. {"department": "Finance", "region": "North America"}',
    )

    class Meta:
        model = EmbedApiToken
        fields = [
            "name",
            "status",
            "embedded_config",
            "allowed_ip_ranges",
            "rate_limit_rpm",
            "expires_at",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "embedded_config": forms.Select(attrs={"class": "form-select"}),
            "allowed_ip_ranges": forms.TextInput(attrs={"class": "form-input font-mono"}),
            "rate_limit_rpm": forms.NumberInput(attrs={"class": "form-input", "min": 10}),
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["embedded_config"].queryset = EmbeddedAnalyticsConfig.objects.filter(
                tenant=self.tenant
            ).order_by("name")

        if self.instance and self.instance.pk:
            if self.instance.scopes:
                if isinstance(self.instance.scopes, list):
                    self.fields["scopes_raw"].initial = ", ".join(self.instance.scopes)
                else:
                    self.fields["scopes_raw"].initial = str(self.instance.scopes)

            if self.instance.injected_rls_context:
                self.fields["injected_rls_context_raw"].initial = json.dumps(
                    self.instance.injected_rls_context, indent=2
                )
            else:
                self.fields["injected_rls_context_raw"].initial = "{}"
        else:
            self.fields["injected_rls_context_raw"].initial = "{}"

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["embedded_config"])

        raw_scopes = cleaned_data.get("scopes_raw", "").strip()
        if raw_scopes:
            if raw_scopes.startswith("["):
                try:
                    parsed_scopes = json.loads(raw_scopes)
                    self.instance.scopes = parsed_scopes if isinstance(parsed_scopes, list) else [str(parsed_scopes)]
                except json.JSONDecodeError:
                    self.instance.scopes = [s.strip() for s in raw_scopes.split(",") if s.strip()]
            else:
                self.instance.scopes = [s.strip() for s in raw_scopes.split(",") if s.strip()]
        else:
            self.instance.scopes = ["read:dashboard", "embed:view"]

        raw_rls = cleaned_data.get("injected_rls_context_raw", "").strip()
        if raw_rls:
            try:
                parsed_rls = json.loads(raw_rls)
                if not isinstance(parsed_rls, dict):
                    self.add_error("injected_rls_context_raw", "RLS context must be a JSON dictionary.")
                else:
                    self.instance.injected_rls_context = parsed_rls
            except json.JSONDecodeError as exc:
                self.add_error("injected_rls_context_raw", f"Invalid JSON syntax in RLS context: {exc}")
        else:
            self.instance.injected_rls_context = {}

        return cleaned_data
