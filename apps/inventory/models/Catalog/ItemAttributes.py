"""Inventory 5.1 Product & Catalog Management — ItemAttribute.

**Product Attributes** bullet: size, colour, weight, dimensions and free-form custom fields as
name/value rows hanging off the catalog spine. The spine itself is 4.3's ``scm.Item`` (L36 — this
app extends it, never re-declares it), so an attribute is a CHILD table keyed by string FK, not a
parallel master.

Why child rows rather than columns on ``Item``: "size" exists for apparel, "voltage" for
electronics and neither belongs on a shared master that 4.8's BOM explosion, 4.3's valuation and
4.7's forecasting all read. Columns would also cap the vocabulary at whatever shipped; a row per
attribute is unbounded and tenant-owned.

``sequence`` orders the rows the way a spec sheet reads them (dimensions before weight before
colour) rather than alphabetically.
"""
from apps.inventory.models._base import *  # noqa: F401,F403


class ItemAttribute(TenantOwned):
    """One typed name/value attribute on a product [of the 5.1 catalog layer]."""

    item = models.ForeignKey(
        "scm.Item", on_delete=models.CASCADE, related_name="catalog_attributes",
        help_text="The product this attribute describes")
    name = models.CharField(max_length=60, help_text='e.g. "Color", "Size", "Voltage"')
    value = models.CharField(max_length=255)
    unit = models.CharField(max_length=20, blank=True,
                            help_text='Optional unit shown after the value, e.g. "mm", "kg", "V"')
    sequence = models.PositiveIntegerField(default=0, help_text="Spec-sheet display order")

    class Meta:
        ordering = ["item_id", "sequence", "name"]
        unique_together = ("tenant", "item", "name")
        indexes = [models.Index(fields=["tenant", "item"], name="inv_ita_tnt_item_idx")]

    def clean(self):
        if self.item_id and self.item.tenant_id != self.tenant_id:
            raise ValidationError({"item": "That item belongs to another workspace."})

    @property
    def display_value(self):
        """The value with its unit, ready for a spec sheet line — "42 mm", not two cells."""
        return f"{self.value} {self.unit}".strip()

    def __str__(self):
        sku = self.item.sku if self.item_id else "?"
        return f"{sku} · {self.name}"
