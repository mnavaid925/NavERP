from django import forms

from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerPrivacyRequests import CustomerPrivacyRequest


class CustomerPrivacyRequestForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CustomerPrivacyRequest
        fields = [
            "customer",
            "request_type",
            "status",
            "requested_by_email",
            "verification_method",
            "statutory_deadline",
            "resolution_notes",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": "form-select"}),
            "request_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "requested_by_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "requester@example.com"}),
            "verification_method": forms.TextInput(attrs={"class": "form-input", "placeholder": "account_login, email_otp, id_document"}),
            "statutory_deadline": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "resolution_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        if self.tenant is not None:
            reject_foreign(self, cleaned, ["customer"])
        return cleaned
