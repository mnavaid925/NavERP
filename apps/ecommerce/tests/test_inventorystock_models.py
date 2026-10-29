"""Comprehensive unit and invariant tests for eCommerce 9.2 Inventory & Stock models.

Covers:
- FulfillmentCenter
- InventoryAllocation
- BackorderPolicy
- ChannelInventorySync

Naming conventions enforced:
- Test functions: test_inventorystock_*
- Module-level helpers: _inventorystock_*
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ecommerce.models import (
    FulfillmentCenter,
    InventoryAllocation,
    BackorderPolicy,
    ChannelInventorySync,
    CatalogProduct,
    ProductVariant,
)
from apps.ecommerce.tests.conftest import (
    _inventorystock_center,
    _inventorystock_allocation,
    _inventorystock_backorder,
    _inventorystock_sync,
    _productcatalog_product,
    _productcatalog_variant,
)
from apps.scm.models import Location

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_inventorystock_*)
# ==============================================================================

def _inventorystock_create_scm_location(tenant, name="Primary SCM Location", code="LOC-001"):
    return Location.objects.create(
        tenant=tenant,
        name=name,
        code=code,
    )


# ==============================================================================
# FulfillmentCenter Model Tests
# ==============================================================================

def test_inventorystock_fulfillmentcenter_creation_and_auto_number(tenant_a):
    center = _inventorystock_center(tenant_a, name="Central Warehouse", code="WH-CENTRAL")
    assert center.pk is not None
    assert center.number.startswith("EFC-")
    assert center.priority == 1
    assert center.is_active is True
    assert center.supports_pick_pack_ship is True
    assert center.supports_customer_pickup is False
    assert str(center) == "Central Warehouse (WH-CENTRAL)"


def test_inventorystock_fulfillmentcenter_unique_code_per_tenant(tenant_a, tenant_b):
    _inventorystock_center(tenant_a, name="Hub 1", code="SHARED-CODE")
    # Same code in different tenant is allowed
    center_b = _inventorystock_center(tenant_b, name="Hub 2", code="SHARED-CODE")
    assert center_b.pk is not None

    # Duplicate code in same tenant raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _inventorystock_center(tenant_a, name="Hub 3", code="SHARED-CODE")


def test_inventorystock_fulfillmentcenter_scm_location_fk(tenant_a):
    loc = _inventorystock_create_scm_location(tenant_a, name="Dock 4", code="LOC-D4")
    center = _inventorystock_center(tenant_a, name="Air Freight Hub", code="AIR-01", location=loc)
    assert center.location == loc
    assert center.location.code == "LOC-D4"


# ==============================================================================
# InventoryAllocation Model Tests
# ==============================================================================

def test_inventorystock_inventoryallocation_creation_and_auto_number(tenant_a, ecom_variant_a, ecom_center_a):
    alloc = _inventorystock_allocation(
        tenant_a,
        ecom_variant_a,
        ecom_center_a,
        quantity_on_hand=100,
        quantity_allocated=15,
        safety_stock_buffer=10,
        low_stock_threshold=20,
    )
    assert alloc.pk is not None
    assert alloc.number.startswith("EAL-")
    assert alloc.product == ecom_variant_a.product
    # ATP = max(0, 100 - 15 - 10) = 75
    assert alloc.available_to_promise == 75
    # 75 > low_stock_threshold (20) -> is_low_stock_alert is False
    assert alloc.is_low_stock_alert is False


def test_inventorystock_inventoryallocation_atp_and_low_stock_alert(tenant_a, ecom_variant_a, ecom_center_a):
    alloc = _inventorystock_allocation(
        tenant_a,
        ecom_variant_a,
        ecom_center_a,
        quantity_on_hand=30,
        quantity_allocated=15,
        safety_stock_buffer=10,
        low_stock_threshold=10,
    )
    # ATP = max(0, 30 - 15 - 10) = 5
    assert alloc.available_to_promise == 5
    # 5 <= 10 -> is_low_stock_alert is True
    assert alloc.is_low_stock_alert is True


def test_inventorystock_inventoryallocation_atp_cannot_be_negative(tenant_a, ecom_variant_a, ecom_center_a):
    alloc = _inventorystock_allocation(
        tenant_a,
        ecom_variant_a,
        ecom_center_a,
        quantity_on_hand=10,
        quantity_allocated=20,
        safety_stock_buffer=10,
    )
    # 10 - 20 - 10 = -20 -> clamped to 0
    assert alloc.available_to_promise == 0


def test_inventorystock_inventoryallocation_unique_together(tenant_a, ecom_variant_a, ecom_center_a):
    _inventorystock_allocation(tenant_a, ecom_variant_a, ecom_center_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _inventorystock_allocation(tenant_a, ecom_variant_a, ecom_center_a)


# ==============================================================================
# BackorderPolicy Model Tests
# ==============================================================================

def test_inventorystock_backorderpolicy_creation(tenant_a, ecom_variant_a):
    policy = _inventorystock_backorder(
        tenant_a,
        ecom_variant_a,
        policy_type="pre_order_only",
        storefront_message="Pre-order today. Dispatches in November.",
        max_backorder_quantity=100,
    )
    assert policy.pk is not None
    assert policy.number.startswith("EBK-")
    assert policy.variant == ecom_variant_a
    assert policy.policy_type == "pre_order_only"
    assert policy.max_backorder_quantity == 100
    assert policy.current_backorder_count == 0
    assert policy.is_active is True
    assert "EBK" in str(policy) or ecom_variant_a.sku in str(policy)


def test_inventorystock_backorderpolicy_one_to_one_variant(tenant_a, ecom_variant_a):
    _inventorystock_backorder(tenant_a, ecom_variant_a)
    # Creating a second backorder policy for the same variant raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _inventorystock_backorder(tenant_a, ecom_variant_a)


# ==============================================================================
# ChannelInventorySync Model Tests
# ==============================================================================

def test_inventorystock_channelinventorysync_creation(tenant_a, ecom_variant_a, ecom_center_a):
    sync = _inventorystock_sync(
        tenant_a,
        ecom_variant_a,
        ecom_center_a,
        channel_type="shopify",
        allocation_buffer_pct=Decimal("15.00"),
    )
    assert sync.pk is not None
    assert sync.number.startswith("ESYN-")
    assert sync.variant == ecom_variant_a
    assert sync.fulfillment_center == ecom_center_a
    assert sync.channel_type == "shopify"
    assert sync.sync_mode == "real_time_webhook"
    assert sync.sync_status == "synced"
    assert "Shopify" in str(sync)


def test_inventorystock_channelinventorysync_calculate_broadcast_quantity(tenant_a, ecom_variant_a, ecom_center_a):
    # Setup allocation: on_hand 100, allocated 0, safety 0 -> ATP 100
    _inventorystock_allocation(tenant_a, ecom_variant_a, ecom_center_a, quantity_on_hand=100, quantity_allocated=0, safety_stock_buffer=0)
    
    # Sync with 10% buffer
    sync = _inventorystock_sync(
        tenant_a,
        ecom_variant_a,
        ecom_center_a,
        channel_type="amazon",
        allocation_buffer_pct=Decimal("10.00"),
    )
    # Total ATP for center = 100. 10% buffer = 10 units. Broadcast quantity = 90
    broadcast_qty = sync.calculate_broadcast_quantity()
    assert broadcast_qty == 90


def test_inventorystock_channelinventorysync_unique_constraint(tenant_a, ecom_variant_a, ecom_center_a):
    _inventorystock_sync(tenant_a, ecom_variant_a, ecom_center_a, channel_type="amazon")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _inventorystock_sync(tenant_a, ecom_variant_a, ecom_center_a, channel_type="amazon")
