from django import forms

from apps.core.models.Party import Party
from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder
from apps.ecommerce.models.OrderManagement.ReturnMerchandiseAuthorizations import ReturnMerchandiseAuthorization


class ReturnMerchandiseAuthorizationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ReturnMerchandiseAuthorization
        fields = [
            "order",
            "customer",
            "return_type",
            "status",
            "reason",
            "return_shipping_label_url",
            "return_tracking_number",
            "restocking_fee",
            "refund_amount",
            "refund_status",
            "restocking_status",
            "restocking_center",
            "customer_notes",
            "inspection_notes",
        ]
        widgets = {
            "order": forms.Select(attrs={"class": "form-select"}),
            "customer": forms.Select(attrs={"class": "form-select"}),
            "return_type": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "reason": forms.Select(attrs={"class": "form-select"}),
            "return_shipping_label_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://..."}),
            "return_tracking_number": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. RMA-TRACK-12345"}),
            "restocking_fee": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "refund_amount": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "refund_status": forms.Select(attrs={"class": "form-select"}),
            "restocking_status": forms.Select(attrs={"class": "form-select"}),
            "restocking_center": forms.Select(attrs={"class": "form-select"}),
            "customer_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
            "inspection_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["order"].queryset = EcommerceOrder.objects.filter(tenant=self.tenant)
            self.fields["customer"].queryset = Party.objects.filter(tenant=self.tenant)
            self.fields["restocking_center"].queryset = FulfillmentCenter.objects.filter(
                tenant=self.tenant, is_active=True
            )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["order", "customer", "restocking_center"])
        return cleaned
