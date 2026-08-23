"""Inventory 5.13 Inventory Forecasting & Planning — forms."""
from django import forms

from apps.inventory.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.inventory.models import StockLevelPlan


class StockLevelPlanForm(TenantUniqueMixin, TenantModelForm):
    """One SKU's seasonal stock target. The mixin validates (tenant, number) and
    stamps instance.tenant for clean()'s foreign-FK checks on create."""

    class Meta:
        model = StockLevelPlan
        fields = ["item", "location", "seasonal_profile", "base_target_qty",
                  "min_qty", "max_qty", "effective_from", "effective_until", "notes"]
        widgets = {
            "effective_from": forms.DateInput(attrs={"type": "date"}),
            "effective_until": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "location", "seasonal_profile"])
        item = cleaned.get("item")
        profile = cleaned.get("seasonal_profile")
        if item and profile and profile.item_id and profile.item_id != item.pk:
            self.add_error("seasonal_profile",
                           "That profile belongs to a different item.")
        return cleaned
