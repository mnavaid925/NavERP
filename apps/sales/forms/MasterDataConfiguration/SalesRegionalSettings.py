"""Form for SalesRegionalSetting model."""
import json
from django import forms
from django.core.exceptions import ValidationError

from apps.core.forms import TenantModelForm
from apps.sales.models.MasterDataConfiguration.SalesRegionalSettings import SalesRegionalSetting


class SalesRegionalSettingForm(TenantModelForm):
    """Form to create and update sales regional profiles and localization settings."""

    supported_currencies_raw = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-input uppercase",
                "placeholder": "e.g. USD, EUR, GBP, CAD, CHF, AUD",
            }
        ),
        label="Supported Currencies",
        help_text="Comma-separated ISO 4217 currency codes.",
    )

    class Meta:
        model = SalesRegionalSetting
        fields = [
            "name",
            "region_code",
            "primary_currency",
            "date_format",
            "number_format",
            "tax_display_mode",
            "default_quote_terms",
            "statutory_disclaimer",
            "compliance_framework",
            "cooling_off_days",
            "is_default",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. EMEA Commercial Profile"}),
            "region_code": forms.Select(attrs={"class": "form-select"}),
            "primary_currency": forms.TextInput(attrs={"class": "form-input uppercase", "maxlength": "3", "placeholder": "USD"}),
            "date_format": forms.Select(attrs={"class": "form-select"}),
            "number_format": forms.Select(attrs={"class": "form-select"}),
            "tax_display_mode": forms.Select(attrs={"class": "form-select"}),
            "default_quote_terms": forms.Textarea(attrs={"class": "form-textarea", "rows": 4, "placeholder": "Standard commercial proposal and contract terms..."}),
            "statutory_disclaimer": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Mandatory legal cooling-off and privacy statutory notice..."}),
            "compliance_framework": forms.Select(attrs={"class": "form-select"}),
            "cooling_off_days": forms.NumberInput(attrs={"class": "form-input", "min": "0"}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.supported_currencies:
            if isinstance(self.instance.supported_currencies, list):
                self.fields["supported_currencies_raw"].initial = ", ".join(self.instance.supported_currencies)

    def clean_primary_currency(self):
        curr = self.cleaned_data.get("primary_currency", "").strip().upper()
        if not curr:
            return "USD"
        return curr

    def clean_supported_currencies_raw(self):
        raw = self.cleaned_data.get("supported_currencies_raw", "").strip()
        if not raw:
            return []
        cleaned = raw.replace(";", ",").replace("\n", ",")
        items = [c.strip().upper() for c in cleaned.split(",") if c.strip()]
        return items

    def clean(self):
        cleaned_data = super().clean()
        currencies = cleaned_data.get("supported_currencies_raw")
        if currencies is not None:
            self.instance.supported_currencies = currencies
        return cleaned_data
