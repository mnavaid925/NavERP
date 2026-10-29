from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.InventoryStock.ChannelInventorySyncs import ChannelInventorySync
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant


class ChannelInventorySyncForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ChannelInventorySync
        fields = [
            "variant",
            "channel_type",
            "channel_name",
            "fulfillment_center",
            "sync_mode",
            "allocation_buffer_pct",
            "sync_status",
            "error_message",
        ]
        widgets = {
            "variant": forms.Select(attrs={"class": "form-select"}),
            "channel_type": forms.Select(attrs={"class": "form-select"}),
            "channel_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. US Amazon Prime Feed"}),
            "fulfillment_center": forms.Select(attrs={"class": "form-select"}),
            "sync_mode": forms.Select(attrs={"class": "form-select"}),
            "allocation_buffer_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01", "min": "0", "max": "100"}),
            "sync_status": forms.Select(attrs={"class": "form-select"}),
            "error_message": forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant)
            self.fields["fulfillment_center"].queryset = FulfillmentCenter.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["variant", "fulfillment_center"])
        return cleaned
