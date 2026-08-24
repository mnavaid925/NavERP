"""Inventory 5.19 Third-Party Integrations & API — ChannelListingMap.

**OWNERSHIP (L36/L29):**
The local catalogue spine stays owned by ``scm.Item`` / ``scm.Location`` (4.3); the connection
register is this sub-module's ``IntegrationChannel``. What 5.19 adds here is THE inventory-domain
asset of the sub-module: the join row that teaches a channel WHICH local SKU (optionally narrowed
to one stocking location) answers to WHICH external product/variant id. High-volume plumbing
nobody cites a CLM- number for — hence plain ``TenantOwned``, deliberately NOT TenantNumbered
(WebhookDelivery telemetry side of the line).

Sync bookkeeping is display-only: ``last_pushed_qty`` / ``last_pushed_at`` are derived copies a
future transport stamps; NOTHING in this build writes them and no StockMove ever flows from them.
"""
from django.core.exceptions import ValidationError
from django.db import models

from apps.inventory.models._base import *  # noqa: F401,F403


class ChannelListingMap(TenantOwned):
    """Local SKU <-> external product/variant id <-> stocking location, per channel."""

    #: Every FK a chosen row must share this workspace's tenant with — read by BOTH the form's
    #: ``_reject_foreign`` and this model's own ``clean()`` loop (scm idiom: one table, two readers).
    TENANT_SCOPED_FKS = ("channel", "item", "location")

    channel = models.ForeignKey(
        "inventory.IntegrationChannel",
        on_delete=models.CASCADE,
        related_name="listings",
        help_text="The connection this mapping belongs to (the sub-module's one cascade)",
    )
    item = models.ForeignKey(
        "scm.Item",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="channel_listings",
        help_text="Blank = a channel-wide row (availability rule rather than one SKU)",
    )
    location = models.ForeignKey(
        "scm.Location",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        help_text="Blank = every location backs this listing",
    )
    external_product_id = models.CharField(
        max_length=80,
        blank=True,
        help_text="Shopify product gid / Amazon ASIN / Woo product id",
    )
    external_variant_id = models.CharField(
        max_length=80,
        blank=True,
        help_text="Shopify variant gid / Amazon ASIN-SKU / Woo variation id",
    )
    external_sku = models.CharField(
        max_length=80,
        blank=True,
        help_text="The SKU as the platform knows it, when it differs from ours",
    )
    sync_enabled = models.BooleanField(
        default=True,
        help_text="Paused rows are left out of stock pushes",
    )
    price_override = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Channel-specific selling price, overriding the catalogue price",
    )
    last_pushed_qty = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
        help_text="Derived display copy of the quantity last pushed — NEVER the on-hand source",
    )
    last_pushed_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="When the last push for this listing completed",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["channel__name", "id"]
        unique_together = (("tenant", "channel", "external_variant_id"),)
        indexes = [
            models.Index(fields=["tenant", "item"], name="inv_clm_tnt_item_idx"),
        ]
        # MariaDB allows duplicate NULLs in a unique column, so local-only rows (blank variant id)
        # coexist without constraint drama — research-verified.

    def __str__(self):
        return (
            f"{self.channel.number} — "
            f"{self.external_sku or (self.item.sku if self.item_id else '') or 'channel-wide'}"
        )

    def clean(self):
        """The cross-tenant FK guard.

        Skipped while the instance has no tenant yet: an unsaved row has ``tenant_id`` ``None``
        and ``self.tenant`` would raise ``RelatedObjectDoesNotExist`` on a non-nullable FK rather
        than return ``None``. Keyed off ``<name>_id`` so an UNSET required FK (channel) falls
        through to the field's own "required" error instead of a 500 from dereferencing it here.
        """
        super().clean()
        if self.tenant_id is None:
            return
        for name in self.TENANT_SCOPED_FKS:
            if getattr(self, f"{name}_id", None) is None:
                continue
            # Defaulted getattr: RelatedObjectDoesNotExist subclasses AttributeError, so a pointer
            # whose row went away degrades to None here instead of 500-ing inside validation.
            related = getattr(self, name, None)
            if related is not None and related.tenant_id != self.tenant_id:
                raise ValidationError({name: "That record belongs to another workspace."})
