from django import forms
from django.utils.text import slugify

from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.MarketingCampaign.AffiliatePartners import AffiliatePartner


class AffiliatePartnerForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AffiliatePartner
        fields = [
            "name",
            "party",
            "customer_profile",
            "partner_type",
            "referral_code",
            "referral_link_slug",
            "commission_type",
            "commission_rate",
            "cookie_duration_days",
            "payout_threshold",
            "payment_email",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-input", "placeholder": "e.g. Alice Smith / StyleBlog Inc"}
            ),
            "party": forms.Select(attrs={"class": "form-select"}),
            "customer_profile": forms.Select(attrs={"class": "form-select"}),
            "partner_type": forms.Select(attrs={"class": "form-select"}),
            "referral_code": forms.TextInput(
                attrs={"class": "form-input uppercase font-mono", "placeholder": "e.g. ALICE15"}
            ),
            "referral_link_slug": forms.TextInput(
                attrs={"class": "form-input lowercase font-mono", "placeholder": "e.g. alice-smith"}
            ),
            "commission_type": forms.Select(attrs={"class": "form-select"}),
            "commission_rate": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "placeholder": "10.00"}
            ),
            "cookie_duration_days": forms.NumberInput(
                attrs={"class": "form-input", "min": 1, "max": 365, "placeholder": "30"}
            ),
            "payout_threshold": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "placeholder": "50.00"}
            ),
            "payment_email": forms.EmailInput(
                attrs={"class": "form-input", "placeholder": "payouts@partner.com"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["party"].queryset = Party.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["customer_profile"].queryset = CustomerAccountProfile.objects.filter(
                tenant=self.tenant
            ).order_by("user__username")

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["party", "customer_profile"])

        name = cleaned_data.get("name")
        slug = cleaned_data.get("referral_link_slug")
        if not slug and name:
            cleaned_data["referral_link_slug"] = slugify(name)[:60]

        code = cleaned_data.get("referral_code")
        if code:
            cleaned_data["referral_code"] = code.upper().strip()

        return cleaned_data
