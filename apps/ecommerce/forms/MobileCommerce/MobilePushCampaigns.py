from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.MobileCommerce.MobilePushCampaigns import MobilePushCampaign
from apps.ecommerce.models.PricingPromotion.CouponPromotions import CouponPromotion
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory


class MobilePushCampaignForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MobilePushCampaign
        exclude = [
            "tenant",
            "number",
            "created_at",
            "updated_at",
            "sent_at",
            "sent_count",
            "delivered_count",
            "opened_count",
            "converted_count",
            "converted_revenue",
            "created_by",
        ]
        widgets = {
            "campaign_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Summer Flash Sale Launch"}),
            "campaign_type": forms.Select(attrs={"class": "form-select"}),
            "target_platform": forms.Select(attrs={"class": "form-select"}),
            "notification_title": forms.TextInput(attrs={"class": "form-input", "placeholder": "Headline (max 100 chars)"}),
            "notification_body": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Message body copy..."}),
            "image_url": forms.TextInput(attrs={"class": "form-input", "placeholder": "https://cdn.example.com/promos/hero.jpg"}),
            "badge_increment": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 99}),
            "sound_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "default"}),
            "deep_link_type": forms.Select(attrs={"class": "form-select"}),
            "deep_link_url": forms.TextInput(attrs={"class": "form-input", "placeholder": "myapp://sale/summer-2026"}),
            "target_product": forms.Select(attrs={"class": "form-select"}),
            "target_category": forms.Select(attrs={"class": "form-select"}),
            "target_coupon": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "scheduled_for": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["target_product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant, status="active")
            self.fields["target_category"].queryset = StoreCategory.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["target_coupon"].queryset = CouponPromotion.objects.filter(tenant=self.tenant, is_active=True)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["target_product", "target_category", "target_coupon"])
        return cleaned
