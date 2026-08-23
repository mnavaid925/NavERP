"""Inventory 5.14 Barcode & RFID Integration — RfidTag form."""
from django import forms

from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import _reject_foreign
from apps.inventory.models.BarcodeRfidIntegration.RfidTags import RfidTag
from apps.scm.models import Item, Location, LotSerial


class RfidTagForm(TenantUniqueMixin, TenantModelForm):
    """Form for registering/maintaining an RFID tag [TAG-]; status is verb-driven, not a field."""

    class Meta:
        model = RfidTag
        fields = [
            "epc",
            "kind",
            "item",
            "location",
            "lot_serial",
            "target_ref",
            "pallet_ref",
            "notes",
        ]
        widgets = {
            "epc": forms.TextInput(attrs={"placeholder": "e.g. E280-689E-0000-0001", "style": "text-transform: uppercase"}),
            "target_ref": forms.TextInput(attrs={"placeholder": "Free-text target reference"}),
            "pallet_ref": forms.TextInput(attrs={"placeholder": "Pallet / handling-unit reference"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant).order_by("sku")
            self.fields["location"].queryset = Location.objects.filter(tenant=self.tenant).order_by("code")
            self.fields["lot_serial"].queryset = LotSerial.objects.filter(tenant=self.tenant).order_by("number")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "location", "lot_serial"])
        return cleaned
