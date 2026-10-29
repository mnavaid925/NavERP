from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder
from apps.ecommerce.models.OrderManagement.OrderFulfillments import OrderFulfillment


class OrderFulfillmentForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = OrderFulfillment
        fields = [
            "order",
            "fulfillment_center",
            "carrier_name",
            "tracking_number",
            "tracking_url",
            "status",
            "shipping_cost",
            "estimated_delivery_date",
            "shipping_label_url",
            "notification_sent",
            "notes",
        ]
        widgets = {
            "order": forms.Select(attrs={"class": "form-select"}),
            "fulfillment_center": forms.Select(attrs={"class": "form-select"}),
            "carrier_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. FedEx, UPS, DHL, USPS"}),
            "tracking_number": forms.TextInput(attrs={"class": "form-input font-mono", "placeholder": "e.g. 1Z9999999999999999"}),
            "tracking_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://..."}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "shipping_cost": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0"}),
            "estimated_delivery_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "shipping_label_url": forms.URLInput(attrs={"class": "form-input", "placeholder": "https://..."}),
            "notification_sent": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["order"].queryset = EcommerceOrder.objects.filter(tenant=self.tenant)
            self.fields["fulfillment_center"].queryset = FulfillmentCenter.objects.filter(
                tenant=self.tenant, is_active=True
            )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["order", "fulfillment_center"])
        return cleaned
