"""Inventory 5.19 Third-Party Integrations & API — ChannelListingMap form.

The three FKs are narrowed to the tenant's own rows (channel by name, item by SKU, location by
code) and re-checked in ``clean()`` — the narrowed ``<select>`` is UX, not an authorization
boundary. ``last_pushed_qty`` / ``last_pushed_at`` are structurally excluded (editable=False):
nothing a human types may claim a sync happened.
"""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import _reject_foreign
from apps.inventory.models.ThirdPartyIntegrations.ChannelListingMaps import ChannelListingMap
from apps.inventory.models.ThirdPartyIntegrations.IntegrationChannels import IntegrationChannel
from apps.scm.models import Item, Location


class ChannelListingMapForm(TenantUniqueMixin, TenantModelForm):
    """Map one local SKU (optionally at one location) to a channel's external ids."""

    class Meta:
        model = ChannelListingMap
        fields = [
            "channel",
            "item",
            "location",
            "external_product_id",
            "external_variant_id",
            "external_sku",
            "price_override",
            "sync_enabled",
            "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["channel"].queryset = IntegrationChannel.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["item"].queryset = Item.objects.filter(tenant=self.tenant).order_by("sku")
            self.fields["location"].queryset = Location.objects.filter(
                tenant=self.tenant
            ).order_by("code")

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["channel", "item", "location"])
        return cleaned
