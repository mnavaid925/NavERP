from django import forms
from django.contrib.auth import get_user_model
from django.db import models

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile


class CustomerAccountProfileForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerAccountProfile
        fields = [
            "customer",
            "user",
            "tier",
            "status",
            "auth_mode",
            "phone_number",
            "phone_verified",
            "preferred_currency",
            "preferred_language",
            "email_marketing_opt_in",
            "sms_marketing_opt_in",
            "notification_frequency",
            "internal_notes",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
            "user": forms.Select(attrs={"class": "form-select"}),
            "tier": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "auth_mode": forms.Select(attrs={"class": "form-select"}),
            "phone_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "+1 555-0199"}),
            "phone_verified": forms.CheckboxInput(attrs={"class": "form-checkbox rounded text-primary"}),
            "preferred_currency": forms.Select(attrs={"class": "form-select"}),
            "preferred_language": forms.TextInput(attrs={"class": "form-input", "placeholder": "en"}),
            "email_marketing_opt_in": forms.CheckboxInput(attrs={"class": "form-checkbox rounded text-primary"}),
            "sms_marketing_opt_in": forms.CheckboxInput(attrs={"class": "form-checkbox rounded text-primary"}),
            "notification_frequency": forms.Select(attrs={"class": "form-select"}),
            "internal_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["user"].queryset = get_user_model().objects.filter(tenant=self.tenant)
            self.fields["preferred_currency"].queryset = Currency.objects.filter(is_active=True)

    def clean(self):
        cleaned = super().clean()
        if self.tenant is not None:
            reject_foreign(self, cleaned, ["customer", "user"])
        return cleaned
