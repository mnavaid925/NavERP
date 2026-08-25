"""Inventory 5.20 Units of Measure (UOM) — forms."""
from apps.inventory.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign

from apps.inventory.models import UomConversion


class UomConversionForm(TenantUniqueMixin, TenantModelForm):
    """One conversion rule. The mixin validates the tenant-including unique_together
    and stamps instance.tenant for clean()'s foreign-FK checks on create."""

    class Meta:
        model = UomConversion
        fields = ["item", "from_uom", "to_uom", "factor", "is_active", "notes"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "from_uom", "to_uom"])
        if (cleaned.get("from_uom") and cleaned.get("to_uom")
                and cleaned["from_uom"] == cleaned["to_uom"]):
            self.add_error("to_uom", "A conversion needs two different units.")
        return cleaned
