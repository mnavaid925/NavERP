"""Inventory 5.10 Returns Management — DispositionRoutingRuleForm."""
from django import forms

from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import _reject_foreign
from apps.inventory.models import DispositionRoutingRule
from apps.scm.models import Item, ItemCategory, Location


class DispositionRoutingRuleForm(TenantUniqueMixin, TenantModelForm):
    """Form for configuring automated disposition routing rules."""

    class Meta:
        model = DispositionRoutingRule
        fields = [
            "name",
            "item",
            "category",
            "condition_grade",
            "suggested_disposition",
            "destination_location",
            "priority",
            "is_active",
            "requires_supervisor_approval",
            "notes",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Grade A Electronics Restock"}),
            "notes": forms.TextInput(attrs={"placeholder": "Internal operator notes"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant).order_by("sku")
            self.fields["category"].queryset = ItemCategory.objects.filter(tenant=self.tenant).order_by("name")
            self.fields["destination_location"].queryset = Location.objects.filter(
                tenant=self.tenant, is_active=True
            ).order_by("code")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(
            self,
            cleaned,
            ["item", "category", "destination_location"],
        )
        return cleaned
