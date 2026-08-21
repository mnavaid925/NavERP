"""Inventory 5.1 Product & Catalog Management — ItemPrice form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _active_currencies, _reject_foreign
from apps.inventory.models import ItemPrice


class ItemPriceForm(TenantUniqueMixin, TenantModelForm):
    """One sell-side price row. Excludes nothing user-entered; there is no stored derived column."""

    class Meta:
        model = ItemPrice
        fields = ["item", "price_type", "unit_price", "currency", "min_quantity",
                  "valid_from", "valid_until", "is_active", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_currencies(self)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item"])
        return cleaned
