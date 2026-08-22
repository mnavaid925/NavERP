"""Inventory 5.4 Receiving & Putaway — PutawayRule form.

A configuration line, not a document: no numbering, no workflow, no custom ``__init__``.
``TenantUniqueMixin`` stamps ``instance.tenant`` during CREATE validation so the model's
cross-tenant ``clean()`` cannot falsely reject before the CRUD helper assigns the real
tenant (SEC-1 two-jobs rule), and ``_reject_foreign`` re-checks every chosen FK where it
renders as a field error — a narrowed ``<select>`` is UX, not an authorization boundary.
There is deliberately NO queryset narrowing beyond that: all three SCM targets carry their
own ``tenant``, so ``TenantModelForm`` already scopes them (5.2 narrowed party for ROLE
reasons only; nothing analogous exists here).
"""
from apps.inventory.forms._common import *  # noqa: F401,F403
from apps.inventory.forms._common import TenantUniqueMixin, _reject_foreign
from apps.inventory.models import PutawayRule


class PutawayRuleForm(TenantUniqueMixin, TenantModelForm):
    """One standing putaway instruction. Overlapping rules are legal by design — the
    resolver's tier order decides which fires — so there is no uniqueness rule to police
    here beyond tenant ownership."""

    class Meta:
        model = PutawayRule
        fields = ["item", "category", "source_location", "destination", "priority",
                  "is_active", "notes"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned,
                        ["item", "category", "source_location", "destination"])
        return cleaned
