"""Inventory 5.12 Multi-Location Management — the LocationNetwork form.

One verb-less config row, so the whole form is identity + placement: code/name/tier,
the two placement FKs and the free-text notes. ``number`` stays off the form (auto
via TenantNumbered save()).

``TenantUniqueMixin`` does double duty here: it makes ("tenant","code") and
("tenant","warehouse") actually validate at the form boundary, AND it stamps
``instance.tenant`` before ``is_valid()`` so the model ``clean()`` cross-tenant
guards see a tenant on CREATE (the CRUD helper only assigns the real one after).
``_reject_foreign`` re-checks both chosen FKs where they render as field errors —
including ``parent``, a SELF-FK: it simply compares ``chosen.tenant_id`` against the
form-stamped tenant, which holds for any tenant-carrying model, this one included.

There is deliberately NO queryset narrowing beyond what ``TenantModelForm`` already
does (house rule): both targets carry their own ``tenant`` column, so the base class
scopes every ModelChoiceField automatically (apps/core/forms/_common.py) — no custom
__init__ needed.
"""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign
from apps.inventory.models.MultiLocationManagement import LocationNetwork


class LocationNetworkForm(TenantUniqueMixin, TenantModelForm):
    """Create/edit one org-tier node. Placement (parent/warehouse) is validated by
    the model's cycle + warehouse-type guards on full_clean; nothing else to gate —
    a config row has no status machine."""

    class Meta:
        model = LocationNetwork
        fields = ["code", "name", "node_type", "parent", "warehouse",
                  "is_active", "notes"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["parent", "warehouse"])
        return cleaned
