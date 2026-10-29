"""Comprehensive form validation and tenant isolation tests for eCommerce 9.2.

Covers:
- FulfillmentCenterForm
- InventoryAllocationForm
- StockAdjustmentActionForm
- BackorderPolicyForm
- ChannelInventorySyncForm

Naming conventions enforced:
- Test functions: test_inventorystock_*
"""
from decimal import Decimal
import pytest

from apps.ecommerce.forms.InventoryStock.FulfillmentCenters import FulfillmentCenterForm
from apps.ecommerce.forms.InventoryStock.InventoryAllocations import (
    InventoryAllocationForm,
    StockAdjustmentActionForm,
)
from apps.ecommerce.forms.InventoryStock.BackorderPolicies import BackorderPolicyForm
from apps.ecommerce.forms.InventoryStock.ChannelInventorySyncs import ChannelInventorySyncForm
from apps.ecommerce.models import (
    FulfillmentCenter,
    InventoryAllocation,
    BackorderPolicy,
    ChannelInventorySync,
)
from apps.ecommerce.tests.conftest import (
    _inventorystock_center,
    _inventorystock_allocation,
    _productcatalog_product,
    _productcatalog_variant,
)
from apps.scm.models import Location

pytestmark = pytest.mark.django_db


# ==============================================================================
# FulfillmentCenterForm Tests
# ==============================================================================

def test_inventorystock_fulfillmentcenter_form_valid(tenant_a):
    data = {
        "name": "North Pacific Hub",
        "code": "NPH-01",
        "center_type": "internal_warehouse",
        "priority": 1,
        "is_active": True,
        "supports_pick_pack_ship": True,
        "supports_customer_pickup": False,
        "daily_cutoff_time": "16:00",
        "address_line1": "100 Industrial Parkway",
        "city": "Seattle",
        "state": "WA",
        "postal_code": "98101",
        "country": "US",
        "contact_email": "ops@example.com",
    }
    form = FulfillmentCenterForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.code == "NPH-01"


def test_inventorystock_fulfillmentcenter_form_rejects_foreign_location(tenant_a, tenant_b):
    foreign_loc = Location.objects.create(tenant=tenant_b, name="Foreign Dock", code="FD-01")
    data = {
        "name": "Acme Hub",
        "code": "AC-01",
        "center_type": "internal_warehouse",
        "priority": 1,
        "location": foreign_loc.pk,
    }
    form = FulfillmentCenterForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "location" in form.errors or "Invalid choice" in str(form.errors)


# ==============================================================================
# InventoryAllocationForm Tests
# ==============================================================================

def test_inventorystock_inventoryallocation_form_valid(tenant_a, ecom_variant_a, ecom_center_a):
    data = {
        "product": ecom_variant_a.product.pk,
        "variant": ecom_variant_a.pk,
        "fulfillment_center": ecom_center_a.pk,
        "zone_bin": "Bin A-10",
        "quantity_on_hand": 50,
        "quantity_allocated": 5,
        "safety_stock_buffer": 5,
        "low_stock_threshold": 10,
        "restock_lead_time_days": 5,
    }
    form = InventoryAllocationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    alloc = form.save(commit=False)
    alloc.tenant = tenant_a
    alloc.save()
    assert alloc.pk is not None
    assert alloc.quantity_on_hand == 50


def test_inventorystock_inventoryallocation_form_mismatched_product_variant(tenant_a, ecom_variant_a, ecom_center_a):
    other_product = _productcatalog_product(tenant_a, name="Different Catalog Product", slug="diff-prod")
    data = {
        "product": other_product.pk,  # Product does not match variant's parent product!
        "variant": ecom_variant_a.pk,
        "fulfillment_center": ecom_center_a.pk,
        "quantity_on_hand": 50,
        "quantity_allocated": 0,
        "safety_stock_buffer": 0,
        "low_stock_threshold": 5,
        "restock_lead_time_days": 3,
    }
    form = InventoryAllocationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "variant" in form.errors


def test_inventorystock_inventoryallocation_form_rejects_foreign_center(tenant_a, ecom_variant_a, ecom_center_b):
    data = {
        "product": ecom_variant_a.product.pk,
        "variant": ecom_variant_a.pk,
        "fulfillment_center": ecom_center_b.pk,  # Belong to Tenant B!
        "quantity_on_hand": 50,
        "quantity_allocated": 0,
        "safety_stock_buffer": 0,
        "low_stock_threshold": 5,
        "restock_lead_time_days": 3,
    }
    form = InventoryAllocationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "fulfillment_center" in form.errors or "Invalid choice" in str(form.errors)


# ==============================================================================
# StockAdjustmentActionForm Tests
# ==============================================================================

def test_inventorystock_adjustment_action_form_valid():
    data = {
        "adjustment_type": "cycle_count",
        "adjustment_quantity": 25,
        "reason_notes": "Monthly cycle count discovered surplus unrecorded items.",
    }
    form = StockAdjustmentActionForm(data=data)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["adjustment_quantity"] == 25


def test_inventorystock_adjustment_action_form_requires_reason():
    data = {
        "adjustment_type": "damage_write_off",
        "adjustment_quantity": -5,
        "reason_notes": "",
    }
    form = StockAdjustmentActionForm(data=data)
    assert not form.is_valid()
    assert "reason_notes" in form.errors


# ==============================================================================
# BackorderPolicyForm Tests
# ==============================================================================

def test_inventorystock_backorderpolicy_form_valid(tenant_a, ecom_variant_a):
    data = {
        "variant": ecom_variant_a.pk,
        "policy_type": "allow_with_backorder_notice",
        "storefront_message": "Accepting orders. Shipping in 2 weeks.",
        "max_backorder_quantity": 40,
        "auto_notify_waitlist": True,
        "is_active": True,
    }
    form = BackorderPolicyForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    policy = form.save(commit=False)
    policy.tenant = tenant_a
    policy.save()
    assert policy.pk is not None


def test_inventorystock_backorderpolicy_form_rejects_negative_max_quantity(tenant_a, ecom_variant_a):
    data = {
        "variant": ecom_variant_a.pk,
        "policy_type": "pre_order_only",
        "storefront_message": "Pre-order launch.",
        "max_backorder_quantity": -10,  # Negative quantity!
        "is_active": True,
    }
    form = BackorderPolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "max_backorder_quantity" in form.errors


def test_inventorystock_backorderpolicy_form_rejects_foreign_variant(tenant_a, ecom_variant_b):
    data = {
        "variant": ecom_variant_b.pk,  # Tenant B variant!
        "policy_type": "deny_when_empty",
        "max_backorder_quantity": 0,
        "is_active": True,
    }
    form = BackorderPolicyForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "variant" in form.errors or "Invalid choice" in str(form.errors)


# ==============================================================================
# ChannelInventorySyncForm Tests
# ==============================================================================

def test_inventorystock_channelinventorysync_form_valid(tenant_a, ecom_variant_a, ecom_center_a):
    data = {
        "variant": ecom_variant_a.pk,
        "channel_type": "walmart",
        "channel_name": "Walmart Marketplace Feed",
        "fulfillment_center": ecom_center_a.pk,
        "sync_mode": "hourly_batch",
        "allocation_buffer_pct": "12.50",
        "sync_status": "pending",
    }
    form = ChannelInventorySyncForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    sync = form.save(commit=False)
    sync.tenant = tenant_a
    sync.save()
    assert sync.pk is not None
    assert sync.channel_name == "Walmart Marketplace Feed"


def test_inventorystock_channelinventorysync_form_rejects_foreign_variant(tenant_a, ecom_variant_b, ecom_center_a):
    data = {
        "variant": ecom_variant_b.pk,  # Tenant B variant!
        "channel_type": "amazon",
        "channel_name": "US Amazon Feed",
        "fulfillment_center": ecom_center_a.pk,
        "sync_mode": "manual_only",
        "allocation_buffer_pct": "5.00",
        "sync_status": "pending",
    }
    form = ChannelInventorySyncForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "variant" in form.errors or "Invalid choice" in str(form.errors)
