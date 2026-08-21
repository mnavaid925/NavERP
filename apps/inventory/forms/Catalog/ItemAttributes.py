"""Inventory 5.1 Product & Catalog Management — ItemAttribute form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign
from apps.inventory.models import ItemAttribute


class ItemAttributeForm(TenantUniqueMixin, TenantModelForm):
    """One spec-sheet row. The (tenant, item, name) uniqueness is what stops a product carrying
    "Color" twice; TenantUniqueMixin is what makes that constraint a rendered field error instead
    of an IntegrityError on save."""

    class Meta:
        model = ItemAttribute
        fields = ["item", "name", "value", "unit", "sequence"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item"])
        return cleaned
