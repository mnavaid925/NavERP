from django import forms

from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.models.AssetProcurement.AssetAcquisitionReceipts import AssetAcquisitionReceipt
from apps.assets.models.AssetProcurement.AssetRequisitions import AssetRequisition
from apps.core.models import Party
from apps.scm.models import Location, PurchaseOrder


class AssetAcquisitionReceiptForm(TenantUniqueMixin, forms.ModelForm):
    class Meta:
        model = AssetAcquisitionReceipt
        exclude = [
            "tenant",
            "number",
            "status",
            "created_at",
            "updated_at",
            "inspected_by",
            "inspected_at",
        ]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-input", "placeholder": "e.g. Receipt of Haas VF-4SS CNC Machine"}),
            "requisition": forms.Select(attrs={"class": "form-select"}),
            "purchase_order": forms.Select(attrs={"class": "form-select"}),
            "vendor": forms.Select(attrs={"class": "form-select"}),
            "manufacturer": forms.TextInput(attrs={"class": "form-input", "placeholder": "Haas Automation"}),
            "model_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "VF-4SS"}),
            "serial_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "SN-HAAS-2026-9921"}),
            "quantity_received": forms.NumberInput(attrs={"class": "form-input", "min": "1"}),
            "received_date": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "carrier_name": forms.TextInput(attrs={"class": "form-input", "placeholder": "DHL Freight / Expeditors"}),
            "tracking_number": forms.TextInput(attrs={"class": "form-input", "placeholder": "TRK-99201928"}),
            "bill_of_lading": forms.TextInput(attrs={"class": "form-input", "placeholder": "BOL-2026-0811"}),
            "receiving_location": forms.Select(attrs={"class": "form-select"}),
            "condition_on_arrival": forms.Select(attrs={"class": "form-select"}),
            "inspection_notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3, "placeholder": "Visual inspection findings, package integrity, damages..."}),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        if self.tenant:
            self.fields["requisition"].queryset = AssetRequisition.objects.filter(tenant=self.tenant)
            self.fields["purchase_order"].queryset = PurchaseOrder.objects.filter(tenant=self.tenant)
            self.fields["vendor"].queryset = Party.objects.filter(
                tenant=self.tenant, roles__role__in=["vendor", "supplier"]
            ).distinct()
            self.fields["receiving_location"].queryset = Location.objects.filter(tenant=self.tenant, is_active=True)

    def clean_quantity_received(self):
        qty = self.cleaned_data.get("quantity_received")
        if qty is not None and qty < 1:
            raise forms.ValidationError("Quantity received must be at least 1.")
        return qty

    def clean(self):
        cleaned_data = super().clean()
        if self.tenant:
            reject_foreign(
                self,
                cleaned_data,
                ["requisition", "purchase_order", "vendor", "receiving_location"],
            )
        return cleaned_data
