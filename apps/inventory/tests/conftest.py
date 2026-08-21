"""Inventory test fixtures.

Reuses the shared root conftest (tenant_a, tenant_b, admin_user, admin_b, client_a,
client_b, member_user) and adds the 5.1 catalog layer around SCM 4.3's item spine:
``scm.Item`` masters (one per tenant), then one ``ItemAttribute`` / ``ItemPrice`` /
``ProductFile`` row per tenant so list/detail/IDOR tests have both an owned and a
foreign target.
"""
from decimal import Decimal

import pytest


@pytest.fixture
def item_a(db, tenant_a):
    """A stock item master on the SCM spine, tenant_a, with a cost basis."""
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant_a, sku="CAT-1", name="Catalog Widget", standard_cost=Decimal("8.00"),
    )


@pytest.fixture
def item_b(db, tenant_b):
    from apps.scm.models import Item
    return Item.objects.create(
        tenant=tenant_b, sku="CAT-1", name="Globex Catalog Widget", standard_cost=Decimal("5.00"),
    )


@pytest.fixture
def attribute_a(db, tenant_a, item_a):
    from apps.inventory.models import ItemAttribute
    return ItemAttribute.objects.create(
        tenant=tenant_a, item=item_a, name="Color", value="Industrial Blue", sequence=10,
    )


@pytest.fixture
def attribute_b(db, tenant_b, item_b):
    from apps.inventory.models import ItemAttribute
    return ItemAttribute.objects.create(
        tenant=tenant_b, item=item_b, name="Color", value="Safety Yellow", sequence=10,
    )


@pytest.fixture
def price_a(db, tenant_a, item_a):
    """A retail price row for item_a — $12.00 against an $8.00 standard cost."""
    from apps.inventory.models import ItemPrice
    return ItemPrice.objects.create(
        tenant=tenant_a, item=item_a, price_type="retail", unit_price=Decimal("12.00"),
    )


@pytest.fixture
def price_b(db, tenant_b, item_b):
    from apps.inventory.models import ItemPrice
    return ItemPrice.objects.create(
        tenant=tenant_b, item=item_b, price_type="retail", unit_price=Decimal("9.00"),
    )


@pytest.fixture
def product_file_a(db, tenant_a, item_a):
    """A linked photo marked as item_a's cover."""
    from apps.inventory.models import ProductFile
    return ProductFile.objects.create(
        tenant=tenant_a, item=item_a, kind="photo", title="Widget photo",
        url="https://files.example.com/catalog/cat-1/photo.jpg", is_primary=True,
    )


@pytest.fixture
def product_file_b(db, tenant_b, item_b):
    from apps.inventory.models import ProductFile
    return ProductFile.objects.create(
        tenant=tenant_b, item=item_b, kind="manual", title="Globex manual",
        url="https://files.example.com/catalog/globex/manual.pdf",
    )


# ---- 5.2 Vendor / Supplier Management ---------------------------------------------------------

@pytest.fixture
def vendor_party_a(db, tenant_a):
    """A supplier-role core.Party on the spine, tenant_a."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_a, name="Acme Supplies Ltd", kind="organization")
    PartyRole.objects.create(tenant=tenant_a, party=party, role="supplier")
    return party


@pytest.fixture
def vendor_party_b(db, tenant_b):
    """A vendor-role core.Party, tenant_b — the foreign target for IDOR/guard tests."""
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant_b, name="Globex Vendors Inc", kind="organization")
    PartyRole.objects.create(tenant=tenant_b, party=party, role="vendor")
    return party


@pytest.fixture
def communication_a(db, tenant_a, vendor_party_a):
    """An overdue follow-up call logged against vendor_party_a."""
    import datetime

    from apps.inventory.models import VendorCommunication
    return VendorCommunication.objects.create(
        tenant=tenant_a, party=vendor_party_a, channel="call", direction="outbound",
        subject="Quarterly capacity check",
        body="Asked for a revised lead-time commitment.",
        occurred_at=datetime.datetime(2026, 8, 10, 10, 0),
        follow_up_on=datetime.date(2026, 8, 15),  # past → overdue badge/chip
    )


@pytest.fixture
def communication_b(db, tenant_b, vendor_party_b):
    from apps.inventory.models import VendorCommunication
    return VendorCommunication.objects.create(
        tenant=tenant_b, party=vendor_party_b, channel="email", direction="inbound",
        subject="Revised price list",
        body="Their 3% increase lands in January.",
    )
