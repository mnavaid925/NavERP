from django import forms
from apps.core.forms import TenantModelForm
from apps.ecommerce.forms._common import TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.MobileCommerce.MobileLocationRules import MobileLocationRule
from apps.ecommerce.models.PricingPromotion.CouponPromotions import CouponPromotion


class MobileLocationRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = MobileLocationRule
        exclude = ["tenant", "number", "created_at", "updated_at"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Downtown Flagship Welcome Geofence"}),
            "rule_type": forms.Select(attrs={"class": "form-select"}),
            "fulfillment_center": forms.Select(attrs={"class": "form-select"}),
            "store_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Acme Downtown Flagship"}),
            "latitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "40.712776"}),
            "longitude": forms.NumberInput(attrs={"class": "form-input", "step": "0.000001", "placeholder": "-74.005974"}),
            "radius_meters": forms.NumberInput(attrs={"class": "form-input", "min": 50, "max": 50000, "placeholder": "500"}),
            "trigger_action": forms.Select(attrs={"class": "form-select"}),
            "linked_promotion": forms.Select(attrs={"class": "form-select"}),
            "push_message": forms.TextInput(attrs={"class": "form-input", "placeholder": "Welcome! Use code STORE20 today."}),
            "dwell_time_seconds": forms.NumberInput(attrs={"class": "form-input", "min": 0, "max": 3600}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant:
            self.fields["fulfillment_center"].queryset = FulfillmentCenter.objects.filter(tenant=self.tenant, is_active=True)
            self.fields["linked_promotion"].queryset = CouponPromotion.objects.filter(tenant=self.tenant, is_active=True)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["fulfillment_center", "linked_promotion"])
        return cleaned
