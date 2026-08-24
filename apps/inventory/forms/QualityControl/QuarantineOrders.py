"""Inventory 5.15 Quality Control (QC) & Inspection — QuarantineOrderForm."""
from django import forms

from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign
from apps.inventory.models import QuarantineOrder


class QuarantineOrderForm(TenantUniqueMixin, TenantModelForm):
    """Draft a segregation order.

    Only draft orders are editable (the views guard the verbs), so the form never sees
    ``status`` or any resolved timestamp. The ledger legs carry the item's average cost
    by construction — there is deliberately no cost field to mistype. The crafted-POST
    re-check covers all four tenant-scoped FK vectors; the model's ``clean()`` adds the
    lot-belongs-to-item rule and the zone-must-differ-from-source rule.
    """

    class Meta:
        model = QuarantineOrder
        fields = ["item", "lot_serial", "source_location", "quarantine_location",
                  "quantity", "reason", "reference", "notes"]
        widgets = {
            "reference": forms.TextInput(attrs={"placeholder": "e.g. GRN-00012 / RMA-00004"}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned,
                        ["item", "lot_serial", "source_location", "quarantine_location"])
        return cleaned
