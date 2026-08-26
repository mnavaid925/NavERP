"""Procurement 6.9 Catalog Management — CatalogPriceTier form.

One price break on a catalogue item. ``status`` is never a form field — tiers enter as
Proposed and move only through the guarded lifecycle actions; ``submitted_by`` is stamped
by the view on create.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import CatalogPriceTier


class CatalogPriceTierForm(TenantUniqueMixin, TenantModelForm):
    """Create/edit one volume break. The mixin goes FIRST so ``instance.tenant`` is stamped
    before the model's overlap check reads it; date-window / discount-cap / active-overlap
    rules live on the model's ``clean()`` and run through full_clean."""

    class Meta:
        model = CatalogPriceTier
        fields = ["catalog_item", "min_quantity", "unit_price", "discount_pct",
                  "valid_from", "valid_until", "contract"]

    def clean(self):
        cleaned = super().clean()
        # Crafted-POST re-check: both FKs are tenant-scoped selects in the UI; here they are
        # re-verified so another workspace's row can never ride in.
        _reject_foreign(self, cleaned, ["catalog_item", "contract"])
        return cleaned
