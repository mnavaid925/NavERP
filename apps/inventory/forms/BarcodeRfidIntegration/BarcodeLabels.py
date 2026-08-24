"""Inventory 5.14 Barcode & RFID Integration — BarcodeLabelForm."""
from django import forms

from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import _reject_foreign
from apps.inventory.models import BarcodeLabel
from apps.scm.models import Item, Location, LotSerial


class BarcodeLabelForm(TenantUniqueMixin, TenantModelForm):
    """Form for issuing/maintaining warehouse barcode labels.

    ``status`` and the ``printed_*`` stamp are deliberately OFF the form — they move only
    through the verb methods (``print()`` / ``void()``), never through a crafted POST.
    """

    class Meta:
        model = BarcodeLabel
        fields = [
            "label_kind",
            "target_type",
            "item",
            "location",
            "lot_serial",
            "target_ref",
            "pallet_ref",
            "symbology",
            "payload",
            "copies",
            "notes",
        ]
        widgets = {
            "target_ref": forms.TextInput(attrs={"placeholder": "Raw code for free-form targets"}),
            "pallet_ref": forms.TextInput(attrs={"placeholder": "License plate / pallet reference"}),
            "payload": forms.TextInput(attrs={"placeholder": "Leave blank to derive from the target"}),
            "notes": forms.TextInput(attrs={"placeholder": "Internal operator notes"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Blank payload is the FEATURE — model.save() derives it from the target
        # (sku / bin code / lot number / free-form ref), so the form must not demand it.
        self.fields["payload"].required = False
        self.fields["payload"].help_text = "Leave blank to derive from the selected target."
        if self.tenant is not None:
            self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant).order_by("sku")
            self.fields["location"].queryset = Location.objects.filter(tenant=self.tenant).order_by("code")
            self.fields["lot_serial"].queryset = LotSerial.objects.filter(tenant=self.tenant).order_by("number")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(
            self,
            cleaned,
            ["item", "location", "lot_serial"],
        )

        # Target/FK consistency: when target_type names exactly one FK field, that field is
        # REQUIRED — otherwise save() derives an empty payload (item.sku of None → "") and a
        # label prints with nothing encoded. Free-form needs at least one raw reference.
        target_type = cleaned.get("target_type")
        required_fk = {"item": "item", "location": "location", "lot": "lot_serial"}.get(target_type)
        if required_fk is not None:
            if not cleaned.get(required_fk):
                self.add_error(
                    required_fk,
                    "Select the record this label points at for the chosen target type.",
                )
        elif target_type == "free":
            if not (cleaned.get("target_ref") or "").strip() and not (cleaned.get("pallet_ref") or "").strip():
                self.add_error("target_ref", "Provide a free-form reference code for this label.")

        return cleaned
