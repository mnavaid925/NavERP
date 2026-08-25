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
        # The from==to refusal lives ONLY in the model's clean() — a keyed field error
        # there renders once; duplicating it here would show the message twice.
        _reject_foreign(self, cleaned, ["item", "from_uom", "to_uom"])
        return cleaned
