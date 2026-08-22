"""Inventory 5.5 Warehousing & Bin Management — BinCapacity form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign
from apps.inventory.models import BinCapacity


class BinCapacityForm(TenantUniqueMixin, TenantModelForm):
    """One bin's capacity envelope. At least one limit must be given — a profile with no
    limits at all is not a declaration, it is an empty row."""

    class Meta:
        model = BinCapacity
        fields = ["location", "max_weight_kg", "max_volume_m3", "max_quantity", "notes"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["location"])
        limits = [cleaned.get("max_weight_kg"), cleaned.get("max_volume_m3"),
                  cleaned.get("max_quantity")]
        if not any(v is not None for v in limits):
            raise ValidationError(
                "Set at least one limit — weight, volume or quantity (blank means unlimited, "
                "so a profile with all three blank declares nothing).")
        return cleaned
