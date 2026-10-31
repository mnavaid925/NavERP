from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.CustomerProfile.CustomerAccountProfiles import CustomerAccountProfile
from apps.ecommerce.models.MarketingCampaign.AffiliatePartners import AffiliatePartner
from apps.ecommerce.models.MarketingCampaign.AffiliateReferralConversions import AffiliateReferralConversion
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder


class AffiliateReferralConversionForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = AffiliateReferralConversion
        fields = [
            "affiliate",
            "order",
            "referred_customer",
            "attribution_type",
            "order_amount",
            "commission_rate_applied",
            "notes",
        ]
        widgets = {
            "affiliate": forms.Select(attrs={"class": "form-select"}),
            "order": forms.Select(attrs={"class": "form-select"}),
            "referred_customer": forms.Select(attrs={"class": "form-select"}),
            "attribution_type": forms.Select(attrs={"class": "form-select"}),
            "order_amount": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "placeholder": "150.00"}
            ),
            "commission_rate_applied": forms.NumberInput(
                attrs={"class": "form-input", "step": "0.01", "placeholder": "10.00"}
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-textarea",
                    "rows": 3,
                    "placeholder": "Attribution notes or clawback details...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["affiliate"].queryset = AffiliatePartner.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["order"].queryset = (
                EcommerceOrder.objects.filter(tenant=self.tenant)
                .select_related("customer")
                .order_by("-created_at")
            )
            self.fields["referred_customer"].queryset = (
                CustomerAccountProfile.objects.filter(tenant=self.tenant)
                .select_related("customer")
                .order_by("customer__name")
            )

    def clean(self):
        cleaned_data = super().clean()
        reject_foreign(self, cleaned_data, ["affiliate", "order", "referred_customer"])

        order_amount = cleaned_data.get("order_amount")
        if order_amount is not None and order_amount < 0:
            self.add_error("order_amount", "Order amount must be greater than or equal to 0.00.")

        commission_rate = cleaned_data.get("commission_rate_applied")
        if commission_rate is not None and commission_rate < 0:
            self.add_error("commission_rate_applied", "Commission rate must be greater than or equal to 0.00.")

        return cleaned_data
