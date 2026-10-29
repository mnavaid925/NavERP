"""Comprehensive view, route, filter, and CRUD tests for eCommerce 9.2 Inventory & Stock.

Covers:
- Operations Console (inventory_operations)
- FulfillmentCenter views
- InventoryAllocation views & stock adjustment workflow
- BackorderPolicy views
- ChannelInventorySync views & broadcast trigger workflow

Naming conventions enforced:
- Test functions: test_inventorystock_*
"""
from decimal import Decimal
import pytest
from django.urls import reverse

from apps.ecommerce.models import (
    FulfillmentCenter,
    InventoryAllocation,
    BackorderPolicy,
    ChannelInventorySync,
)
from apps.ecommerce.tests.conftest import (
    _inventorystock_center,
    _inventorystock_allocation,
    _inventorystock_backorder,
    _inventorystock_sync,
    _productcatalog_product,
    _productcatalog_variant,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Operations Console Tests
# ==============================================================================

def test_inventorystock_operations_view(client_a, tenant_a, ecom_variant_a, ecom_center_a):
    _inventorystock_allocation(tenant_a, ecom_variant_a, ecom_center_a, quantity_on_hand=50, quantity_allocated=10, safety_stock_buffer=5)
    _inventorystock_backorder(tenant_a, ecom_variant_a)
    _inventorystock_sync(tenant_a, ecom_variant_a, ecom_center_a)

    url = reverse("ecommerce:inventory_operations")
    response = client_a.get(url)
    assert response.status_code == 200
    assert "kpis" in response.context
    assert "centers" in response.context
    assert "low_stock_allocations" in response.context
    assert "recent_syncs" in response.context
    assert "recent_backorders" in response.context
    kpis = response.context["kpis"]
    assert kpis["total_on_hand"] >= 50
    assert kpis["total_allocated"] >= 10
    assert kpis["total_atp"] >= 35


# ==============================================================================
# FulfillmentCenter View Tests
# ==============================================================================

def test_inventorystock_fulfillmentcenter_list(client_a, tenant_a, ecom_center_a):
    c2 = _inventorystock_center(tenant_a, name="Retail Store", code="RET-01", center_type="retail_store", is_active=False)
    url = reverse("ecommerce:fulfillmentcenter_list")
    
    # 1. Base list
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "centers" in resp.context
    assert len(resp.context["centers"]) == 2

    # 2. Search query filter
    resp_q = client_a.get(url, {"q": "Retail"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["centers"]) == 1

    # 3. Center type filter
    resp_type = client_a.get(url, {"center_type": "retail_store"})
    assert resp_type.status_code == 200
    assert len(resp_type.context["centers"]) == 1

    # 4. Status filter
    resp_active = client_a.get(url, {"is_active": "1"})
    assert resp_active.status_code == 200
    assert len(resp_active.context["centers"]) == 1


def test_inventorystock_fulfillmentcenter_create(client_a, tenant_a):
    url = reverse("ecommerce:fulfillmentcenter_create")
    resp = client_a.get(url)
    assert resp.status_code == 200

    payload = {
        "name": "East Coast Distribution",
        "code": "ECD-01",
        "center_type": "internal_warehouse",
        "priority": 2,
        "is_active": True,
        "supports_pick_pack_ship": True,
        "supports_customer_pickup": True,
        "daily_cutoff_time": "17:00",
        "city": "Boston",
        "state": "MA",
        "postal_code": "02108",
        "country": "USA",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    center = FulfillmentCenter.objects.get(code="ECD-01", tenant=tenant_a)
    assert center.priority == 2


def test_inventorystock_fulfillmentcenter_detail(client_a, tenant_a, ecom_center_a, ecom_variant_a):
    _inventorystock_allocation(tenant_a, ecom_variant_a, ecom_center_a)
    url = reverse("ecommerce:fulfillmentcenter_detail", kwargs={"pk": ecom_center_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "center" in resp.context
    assert "allocations" in resp.context
    assert "sync_channels" in resp.context


def test_inventorystock_fulfillmentcenter_edit(client_a, tenant_a, ecom_center_a):
    url = reverse("ecommerce:fulfillmentcenter_edit", kwargs={"pk": ecom_center_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    payload = {
        "name": "Updated Center Name",
        "code": ecom_center_a.code,
        "center_type": ecom_center_a.center_type,
        "priority": 5,
        "is_active": True,
        "city": ecom_center_a.city,
        "country": ecom_center_a.country,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    ecom_center_a.refresh_from_db()
    assert ecom_center_a.name == "Updated Center Name"
    assert ecom_center_a.priority == 5


def test_inventorystock_fulfillmentcenter_delete(client_a, tenant_a, ecom_center_a):
    url = reverse("ecommerce:fulfillmentcenter_delete", kwargs={"pk": ecom_center_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not FulfillmentCenter.objects.filter(pk=ecom_center_a.pk).exists()


# ==============================================================================
# InventoryAllocation View Tests
# ==============================================================================

def test_inventorystock_inventoryallocation_list(client_a, tenant_a, ecom_variant_a, ecom_center_a):
    _inventorystock_allocation(tenant_a, ecom_variant_a, ecom_center_a, quantity_on_hand=100, low_stock_threshold=10)
    url = reverse("ecommerce:inventoryallocation_list")

    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "allocations" in resp.context
    assert len(resp.context["allocations"]) == 1

    # Filter by center
    resp_c = client_a.get(url, {"center": str(ecom_center_a.pk)})
    assert resp_c.status_code == 200
    assert len(resp_c.context["allocations"]) == 1

    # Filter by low_stock (none low)
    resp_low = client_a.get(url, {"low_stock": "1"})
    assert resp_low.status_code == 200
    assert len(resp_low.context["allocations"]) == 0


def test_inventorystock_inventoryallocation_create_with_variant_prefill(client_a, tenant_a, ecom_variant_a, ecom_center_a):
    url = reverse("ecommerce:inventoryallocation_create")
    # GET with ?variant=ID (I5 prefill verification)
    resp = client_a.get(url, {"variant": str(ecom_variant_a.pk)})
    assert resp.status_code == 200
    form = resp.context["form"]
    assert form.initial.get("variant") == ecom_variant_a.pk
    assert form.initial.get("product") == ecom_variant_a.product_id

    # POST create
    payload = {
        "product": ecom_variant_a.product.pk,
        "variant": ecom_variant_a.pk,
        "fulfillment_center": ecom_center_a.pk,
        "zone_bin": "Rack-7",
        "quantity_on_hand": 120,
        "quantity_allocated": 10,
        "safety_stock_buffer": 10,
        "low_stock_threshold": 15,
        "restock_lead_time_days": 14,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    alloc = InventoryAllocation.objects.get(variant=ecom_variant_a, fulfillment_center=ecom_center_a, tenant=tenant_a)
    assert alloc.quantity_on_hand == 120


def test_inventorystock_inventoryallocation_adjust_workflow(client_a, tenant_a, ecom_allocation_a):
    url = reverse("ecommerce:inventoryallocation_adjust", kwargs={"pk": ecom_allocation_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "allocation" in resp.context

    # 1. Valid positive adjustment
    before_qty = ecom_allocation_a.quantity_on_hand
    payload_pos = {
        "adjustment_type": "cycle_count",
        "adjustment_quantity": 25,
        "reason_notes": "Cycle count audit reconciliation",
    }
    resp_pos = client_a.post(url, payload_pos)
    assert resp_pos.status_code == 302
    ecom_allocation_a.refresh_from_db()
    assert ecom_allocation_a.quantity_on_hand == before_qty + 25

    # 2. Invalid negative adjustment causing negative physical on-hand (I4 guard)
    payload_neg = {
        "adjustment_type": "damage_write_off",
        "adjustment_quantity": -(ecom_allocation_a.quantity_on_hand + 50),
        "reason_notes": "Exceeds physical count error test",
    }
    resp_neg = client_a.post(url, payload_neg)
    assert resp_neg.status_code == 200  # Re-renders form with error
    assert "adjustment_quantity" in resp_neg.context["form"].errors


def test_inventorystock_inventoryallocation_delete(client_a, tenant_a, ecom_allocation_a):
    url = reverse("ecommerce:inventoryallocation_delete", kwargs={"pk": ecom_allocation_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not InventoryAllocation.objects.filter(pk=ecom_allocation_a.pk).exists()


# ==============================================================================
# BackorderPolicy View Tests
# ==============================================================================

def test_inventorystock_backorderpolicy_list(client_a, tenant_a, ecom_backorder_a):
    url = reverse("ecommerce:backorderpolicy_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "policies" in resp.context
    assert len(resp.context["policies"]) == 1


def test_inventorystock_backorderpolicy_create(client_a, tenant_a, ecom_product_a):
    v2 = _productcatalog_variant(tenant_a, ecom_product_a, sku="VAR-NEW-02")
    url = reverse("ecommerce:backorderpolicy_create")
    resp = client_a.get(url)
    assert resp.status_code == 200

    payload = {
        "variant": v2.pk,
        "policy_type": "pre_order_only",
        "storefront_message": "Pre-order now. Launch date Dec 1.",
        "expected_availability_date": "2026-12-01",
        "max_backorder_quantity": 200,
        "auto_notify_waitlist": True,
        "is_active": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    policy = BackorderPolicy.objects.get(variant=v2, tenant=tenant_a)
    assert policy.max_backorder_quantity == 200


def test_inventorystock_backorderpolicy_detail(client_a, tenant_a, ecom_backorder_a):
    url = reverse("ecommerce:backorderpolicy_detail", kwargs={"pk": ecom_backorder_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "policy" in resp.context
    assert "variant" in resp.context


def test_inventorystock_backorderpolicy_edit(client_a, tenant_a, ecom_backorder_a):
    url = reverse("ecommerce:backorderpolicy_edit", kwargs={"pk": ecom_backorder_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    payload = {
        "variant": ecom_backorder_a.variant.pk,
        "policy_type": "deny_when_empty",
        "storefront_message": "Sold Out",
        "max_backorder_quantity": 0,
        "is_active": False,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    ecom_backorder_a.refresh_from_db()
    assert ecom_backorder_a.policy_type == "deny_when_empty"
    assert ecom_backorder_a.is_active is False


def test_inventorystock_backorderpolicy_delete(client_a, tenant_a, ecom_backorder_a):
    url = reverse("ecommerce:backorderpolicy_delete", kwargs={"pk": ecom_backorder_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not BackorderPolicy.objects.filter(pk=ecom_backorder_a.pk).exists()


# ==============================================================================
# ChannelInventorySync View Tests
# ==============================================================================

def test_inventorystock_channelinventorysync_list(client_a, tenant_a, ecom_sync_a):
    url = reverse("ecommerce:channelinventorysync_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "syncs" in resp.context
    assert len(resp.context["syncs"]) == 1


def test_inventorystock_channelinventorysync_create(client_a, tenant_a, ecom_product_a, ecom_center_a):
    v2 = _productcatalog_variant(tenant_a, ecom_product_a, sku="VAR-SYNC-02")
    url = reverse("ecommerce:channelinventorysync_create")
    resp = client_a.get(url)
    assert resp.status_code == 200

    payload = {
        "variant": v2.pk,
        "channel_type": "walmart_marketplace",
        "channel_name": "Walmart US Feed",
        "fulfillment_center": ecom_center_a.pk,
        "sync_mode": "scheduled_batch",
        "allocation_buffer_pct": "8.00",
        "sync_status": "pending",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    sync = ChannelInventorySync.objects.get(variant=v2, channel_name="Walmart US Feed", tenant=tenant_a)
    assert sync.channel_type == "walmart_marketplace"


def test_inventorystock_channelinventorysync_detail_preloads_allocations(client_a, tenant_a, ecom_sync_a):
    url = reverse("ecommerce:channelinventorysync_detail", kwargs={"pk": ecom_sync_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sync" in resp.context
    assert "allocations" in resp.context  # I3 verification


def test_inventorystock_channelinventorysync_trigger_and_redirect_safety(client_a, tenant_a, ecom_sync_a):
    url = reverse("ecommerce:channelinventorysync_trigger", kwargs={"pk": ecom_sync_a.pk})

    # 1. Trigger with safe local next URL
    resp_safe = client_a.post(url, {"next": "/ecommerce/inventory/sync/"})
    assert resp_safe.status_code == 302
    assert resp_safe.url == "/ecommerce/inventory/sync/"

    # 2. Trigger with malicious open redirect attempt (I1 hardening)
    resp_malicious = client_a.post(url, {"next": "https://evil.example.com/steal"})
    assert resp_malicious.status_code == 302
    # Must fallback to detail view, NOT evil.example.com
    assert "evil.example.com" not in resp_malicious.url
    assert reverse("ecommerce:channelinventorysync_detail", kwargs={"pk": ecom_sync_a.pk}) in resp_malicious.url


def test_inventorystock_channelinventorysync_delete(client_a, tenant_a, ecom_sync_a):
    url = reverse("ecommerce:channelinventorysync_delete", kwargs={"pk": ecom_sync_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not ChannelInventorySync.objects.filter(pk=ecom_sync_a.pk).exists()
