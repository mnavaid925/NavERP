from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.forms import TenantModelForm
from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor

User = get_user_model()


class MarketplaceVendorForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MarketplaceVendor
        exclude = [
            "tenant",
            "number",
            "rating_average",
            "rating_count",
            "kyc_verified_at",
            "suspended_at",
            "suspended_by",
            "created_at",
            "updated_at",
        ]
        widgets = {
            "party": forms.Select(attrs={"class": "form-select"}),
            "owner_user": forms.Select(attrs={"class": "form-select"}),
            "store_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Apex Electronics, Bloom Artisans"}),
            "slug": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. apex-electronics"}),
            "headline": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Premium Handcrafted Goods & Gear"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "logo_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://..."}),
            "banner_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://..."}),
            "support_email": forms.EmailInput(attrs={"class": "form-input", "placeholder": "support@vendor.com"}),
            "support_phone": forms.TextInput(attrs={"class": "form-input", "placeholder": "+1 555-0199"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "kyc_status": forms.Select(attrs={"class": "form-select"}),
            "kyc_document_type": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Certificate of Formation"}),
            "kyc_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "commission_type": forms.Select(attrs={"class": "form-select"}),
            "commission_rate": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "fixed_fee_per_order": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "payout_method": forms.Select(attrs={"class": "form-select"}),
            "payout_account_identifier": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. acct_1N7... or IBAN"}),
            "min_payout_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "tax_id": forms.TextInput(attrs={"class": "form-input", "placeholder": "EIN / VAT ID"}),
            "tax_form_status": forms.Select(attrs={"class": "form-select"}),
            "shipping_lead_time_days": forms.NumberInput(attrs={"class": "form-input"}),
            "return_policy": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
            "is_featured": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "suspension_reason": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["party"].queryset = Party.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["owner_user"].queryset = User.objects.filter(is_active=True).order_by("username")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["party"])
        return cleaned_data


class VendorKycVerificationForm(forms.Form):
    kyc_status = forms.ChoiceField(
        choices=MarketplaceVendor.KYC_STATUS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    kyc_document_type = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-input", "placeholder": "Document verified, e.g. Business Tax ID certificate"}),
    )
    kyc_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Compliance review remarks..."}),
    )


class VendorSuspensionForm(forms.Form):
    suspension_reason = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Reason for suspension (SLA breach, prohibited items, customer disputes)..."}),
    )
