from django import forms

from apps.ecommerce.forms._common import TenantModelForm, reject_foreign
from apps.ecommerce.models.AnalyticsBi.AttributionTouchpoints import AttributionTouchpoint
from apps.ecommerce.models.CartCheckout.Carts import Cart
from apps.ecommerce.models.MarketingCampaign.AffiliatePartners import AffiliatePartner
from apps.ecommerce.models.MarketingCampaign.MarketingCampaigns import MarketingCampaign
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder


class AttributionTouchpointForm(TenantModelForm):
    class Meta:
        model = AttributionTouchpoint
        fields = [
            "order",
            "cart",
            "channel_type",
            "attribution_model",
            "campaign",
            "affiliate",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "touchpoint_timestamp",
            "attribution_weight",
            "attributed_revenue",
            "estimated_cac",
            "landing_page_url",
            "referrer_url",
        ]
        widgets = {
            "order": forms.Select(attrs={"class": "form-select"}),
            "cart": forms.Select(attrs={"class": "form-select"}),
            "channel_type": forms.Select(attrs={"class": "form-select"}),
            "attribution_model": forms.Select(attrs={"class": "form-select"}),
            "campaign": forms.Select(attrs={"class": "form-select"}),
            "affiliate": forms.Select(attrs={"class": "form-select"}),
            "utm_source": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. google, facebook, newsletter"}),
            "utm_medium": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. cpc, email, referral"}),
            "utm_campaign": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. summer_sale_2026"}),
            "touchpoint_timestamp": forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-input"}),
            "attribution_weight": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001", "min": 0, "max": 1}),
            "attributed_revenue": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "estimated_cac": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "landing_page_url": forms.TextInput(attrs={"class": "form-input", "placeholder": "https://..."}),
            "referrer_url": forms.TextInput(attrs={"class": "form-input", "placeholder": "https://..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["order"].queryset = EcommerceOrder.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["cart"].queryset = Cart.objects.filter(
                tenant=self.tenant
            ).order_by("-created_at")
            self.fields["campaign"].queryset = MarketingCampaign.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["affiliate"].queryset = AffiliatePartner.objects.filter(
                tenant=self.tenant
            ).order_by("name")

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["order", "cart", "campaign", "affiliate"])
        return cleaned
