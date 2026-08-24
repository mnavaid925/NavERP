"""Inventory 5.15 Quality Control (QC) & Inspection — QcChecklist forms."""
from django import forms
from django.forms import inlineformset_factory

from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign, _vendor_parties
from apps.inventory.models import QcChecklist, QcChecklistItem


class QcChecklistForm(TenantUniqueMixin, TenantModelForm):
    """One pre-acceptance checklist.

    The TenantUniqueMixin stamps ``instance.tenant`` before validation so the model's
    foreign-item ``clean()`` checks pass on CREATE. The vendor dropdown is scoped to the
    workspace's supplier/vendor-role parties (the 5.2 rule — both role spellings accepted);
    the crafted-POST re-check covers every tenant-scoped FK.
    """

    class Meta:
        model = QcChecklist
        fields = ["name", "item", "vendor", "description", "is_active"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        if "vendor" in self.fields:
            self.fields["vendor"].queryset = _vendor_parties(tenant)
            self.fields["vendor"].required = False

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "vendor"])
        return cleaned


class QcChecklistItemForm(TenantUniqueMixin, TenantModelForm):
    """One checkpoint row inside the checklist's inline editor."""

    class Meta:
        model = QcChecklistItem
        fields = ["label", "kind", "expected_result", "is_mandatory", "sequence"]
        widgets = {
            "label": forms.TextInput(attrs={"placeholder": "e.g. Carton seal intact"}),
            "expected_result": forms.TextInput(attrs={"placeholder": "e.g. Seal unbroken"}),
        }


QcChecklistItemFormSet = inlineformset_factory(
    QcChecklist,
    QcChecklistItem,
    form=QcChecklistItemForm,
    extra=3,
    can_delete=True,
)
