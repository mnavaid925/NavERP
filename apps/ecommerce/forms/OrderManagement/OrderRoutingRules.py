from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.OrderManagement.OrderRoutingRules import OrderRoutingRule


class OrderRoutingRuleForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = OrderRoutingRule
        fields = [
            "name",
            "strategy",
            "priority",
            "destination_country",
            "destination_region",
            "preferred_fulfillment_center",
            "allow_split_shipment",
            "enable_dropship",
            "is_active",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Domestic Priority Routing"}),
            "strategy": forms.Select(attrs={"class": "form-select"}),
            "priority": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "destination_country": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. United States or US"}),
            "destination_region": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. California, West Coast"}),
            "preferred_fulfillment_center": forms.Select(attrs={"class": "form-select"}),
            "allow_split_shipment": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "enable_dropship": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["preferred_fulfillment_center"].queryset = FulfillmentCenter.objects.filter(
                tenant=self.tenant, is_active=True
            )

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["preferred_fulfillment_center"])
        return cleaned
