"""Inventory 5.7 Stock Movement & Transfers — TransferRoute form."""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign
from apps.inventory.models import TransferRoute


class TransferRouteForm(TenantUniqueMixin, TenantModelForm):
    """One routing catalog entry. Every FK is tenant-scoped by the base; the crafted-POST
    re-check below is the authorization boundary, not the narrowed dropdowns."""

    class Meta:
        model = TransferRoute
        fields = ["name", "code", "mode", "origin_location", "destination_location",
                  "default_transit_days", "is_active", "notes"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["origin_location", "destination_location"])
        origin, destination = cleaned.get("origin_location"), cleaned.get("destination_location")
        if (self.tenant is not None and origin is not None and destination is not None
                and origin.pk == destination.pk):
            self.add_error("destination_location",
                           "A route's start and end must be different locations.")
        return cleaned
