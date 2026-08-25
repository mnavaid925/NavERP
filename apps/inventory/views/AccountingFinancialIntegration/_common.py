"""Shared helpers for the 5.18 Accounting & Financial Integration views.

Used by MORE THAN ONE sync page (AP + AR), so it lives beside them inside this
sub-module rather than being duplicated per entity file.
"""
from apps.core.models import Address
from apps.inventory.models import TaxRule


def _party_country(tenant, party):
    """The counterparty's billing country as recorded on core.Address — '' when none.

    The TaxRule resolver compares case-insensitively, so a free-text country is fine;
    an absent address simply matches only the geography-blind rules.
    """
    if party is None:
        return ""
    addresses = list(Address.objects.filter(tenant=tenant, party=party))
    if not addresses:
        return ""
    billing = next((a for a in addresses if a.kind == "billing"), addresses[0])
    return (billing.country or "").strip()


def _active_tax_rules(tenant):
    """Preload the tenant's active tax rules ONCE per request for the rate lookups."""
    return (TaxRule.objects.filter(tenant=tenant, is_active=True)
            .select_related("item", "category", "tax_code"))
