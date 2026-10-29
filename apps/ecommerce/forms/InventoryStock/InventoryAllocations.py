from django import forms

from apps.ecommerce.forms._common import TenantModelForm, TenantUniqueMixin, reject_foreign
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.InventoryStock.InventoryAllocations import InventoryAllocation
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant


class InventoryAllocationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = InventoryAllocation
        fields = [
            "product",
            "variant",
            "fulfillment_center",
            "zone_bin",
            "quantity_on_hand",
            "quantity_allocated",
            "safety_stock_buffer",
            "low_stock_threshold",
            "restock_lead_time_days",
            "last_counted_at",
            "notes",
        ]
        widgets = {
            "product": forms.Select(attrs={"class": "form-select"}),
            "variant": forms.Select(attrs={"class": "form-select"}),
            "fulfillment_center": forms.Select(attrs={"class": "form-select"}),
            "zone_bin": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Aisle 3, Bin B-12"}),
            "quantity_on_hand": forms.NumberInput(attrs={"class": "form-input"}),
            "quantity_allocated": forms.NumberInput(attrs={"class": "form-input"}),
            "safety_stock_buffer": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "low_stock_threshold": forms.NumberInput(attrs={"class": "form-input", "min": 0}),
            "restock_lead_time_days": forms.NumberInput(attrs={"class": "form-input", "min": 1}),
            "last_counted_at": forms.DateTimeInput(attrs={"class": "form-input", "type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if hasattr(self, "tenant") and self.tenant is not None:
            self.fields["product"].queryset = CatalogProduct.objects.filter(tenant=self.tenant)
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=self.tenant)
            self.fields["fulfillment_center"].queryset = FulfillmentCenter.objects.filter(tenant=self.tenant)

    def clean(self):
        cleaned = super().clean()
        reject_foreign(self, cleaned, ["product", "variant", "fulfillment_center"])

        variant = cleaned.get("variant")
        product = cleaned.get("product")
        if variant and product and variant.product_id != product.pk:
            self.add_error("variant", "The selected variant does not belong to the selected catalog product.")

        return cleaned


class StockAdjustmentActionForm(forms.Form):
    ADJUSTMENT_TYPE_CHOICES = [
        ("cycle_count", "Cycle Count Audit Reconciliation"),
        ("damage_write_off", "Damage / Spoilage / Shrinkage Write-Off"),
        ("receipt_reconcile", "Inbound Shipment Reconciliation"),
        ("manual_correction", "Manual Operational Correction"),
    ]

    adjustment_type = forms.ChoiceField(
        choices=ADJUSTMENT_TYPE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    adjustment_quantity = forms.IntegerField(
        help_text="Units to add (positive number) or remove (negative number)",
        widget=forms.NumberInput(attrs={"class": "form-input", "placeholder": "e.g. +10 or -5"}),
    )
    reason_notes = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Reason for stock adjustment..."}),
        required=True,
    )
