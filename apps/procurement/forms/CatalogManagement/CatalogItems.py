"""Procurement 6.9 Catalog Management — CatalogItem form.

One header form; price breaks are managed on the detail page as ``CatalogPriceTier`` rows
(lane B), so this form carries only the catalogue entry itself.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models.CatalogManagement.CatalogItems import CatalogItem


class CatalogItemForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = CatalogItem
        # EXCLUDED and why: ``number`` is assigned once by TenantNumbered.save(); status moves
        # only through the guarded submit/approve/reject/block actions; the submitted/approved/
        # created stamps and rejection_reason are written server-side by those verbs.
        fields = ["source_type", "item", "supplier", "contract", "name", "supplier_part_no",
                  "description", "manufacturer", "uom", "currency", "base_price",
                  "category_text", "is_preferred", "is_active"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["item", "supplier", "contract", "uom"])
        # Mirrors the model rules as FIELD errors (the model's clean() raises non-field ones):
        if cleaned.get("source_type") == "internal" and not cleaned.get("item"):
            self.add_error("item", "An internal catalog entry must point at a stock item.")
        if cleaned.get("source_type") == "supplier_product" \
                and not (cleaned.get("name") or "").strip():
            self.add_error("name", "A supplier product needs a catalogue name.")
        return cleaned
