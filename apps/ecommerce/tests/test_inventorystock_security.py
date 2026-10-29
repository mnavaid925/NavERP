"""Comprehensive multi-tenancy, authorization, and IDOR isolation tests for eCommerce 9.2.

Covers:
- Unauthenticated access prevention (login redirect)
- Cross-tenant IDOR defense (404 on foreign tenant records)
- Queryset isolation on all list views
- Audit log emission on CRUD actions

Naming conventions enforced:
- Test functions: test_inventorystock_*
"""
import pytest
from django.urls import reverse

from apps.core.models import AuditLog
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
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Anonymous Access Tests
# ==============================================================================

@pytest.mark.parametrize(
    "url_name,args",
    [
        ("inventory_operations", []),
        ("fulfillmentcenter_list", []),
        ("fulfillmentcenter_create", []),
        ("inventoryallocation_list", []),
        ("inventoryallocation_create", []),
        ("backorderpolicy_list", []),
        ("backorderpolicy_create", []),
        ("channelinventorysync_list", []),
        ("channelinventorysync_create", []),
    ],
)
def test_inventorystock_anonymous_redirects_to_login(client, url_name, args):
    url = reverse(f"ecommerce:{url_name}", args=args)
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url or "/login/" in response.url


# ==============================================================================
# Cross-Tenant IDOR Tests
# ==============================================================================

def test_inventorystock_fulfillmentcenter_cross_tenant_idor(client_a, ecom_center_b):
    # Detail
    url_detail = reverse("ecommerce:fulfillmentcenter_detail", kwargs={"pk": ecom_center_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit
    url_edit = reverse("ecommerce:fulfillmentcenter_edit", kwargs={"pk": ecom_center_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked"}).status_code == 404

    # Delete
    url_delete = reverse("ecommerce:fulfillmentcenter_delete", kwargs={"pk": ecom_center_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_inventorystock_inventoryallocation_cross_tenant_idor(client_a, ecom_allocation_b):
    # Detail
    url_detail = reverse("ecommerce:inventoryallocation_detail", kwargs={"pk": ecom_allocation_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit
    url_edit = reverse("ecommerce:inventoryallocation_edit", kwargs={"pk": ecom_allocation_b.pk})
    assert client_a.get(url_edit).status_code == 404

    # Adjust
    url_adjust = reverse("ecommerce:inventoryallocation_adjust", kwargs={"pk": ecom_allocation_b.pk})
    assert client_a.get(url_adjust).status_code == 404
    assert client_a.post(url_adjust, {"adjustment_type": "cycle_count", "adjustment_quantity": 10, "reason_notes": "Test"}).status_code == 404

    # Delete
    url_delete = reverse("ecommerce:inventoryallocation_delete", kwargs={"pk": ecom_allocation_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_inventorystock_backorderpolicy_cross_tenant_idor(client_a, ecom_backorder_b):
    # Detail
    url_detail = reverse("ecommerce:backorderpolicy_detail", kwargs={"pk": ecom_backorder_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit
    url_edit = reverse("ecommerce:backorderpolicy_edit", kwargs={"pk": ecom_backorder_b.pk})
    assert client_a.get(url_edit).status_code == 404

    # Delete
    url_delete = reverse("ecommerce:backorderpolicy_delete", kwargs={"pk": ecom_backorder_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_inventorystock_channelinventorysync_cross_tenant_idor(client_a, ecom_sync_b):
    # Detail
    url_detail = reverse("ecommerce:channelinventorysync_detail", kwargs={"pk": ecom_sync_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit
    url_edit = reverse("ecommerce:channelinventorysync_edit", kwargs={"pk": ecom_sync_b.pk})
    assert client_a.get(url_edit).status_code == 404

    # Trigger
    url_trigger = reverse("ecommerce:channelinventorysync_trigger", kwargs={"pk": ecom_sync_b.pk})
    assert client_a.post(url_trigger).status_code == 404

    # Delete
    url_delete = reverse("ecommerce:channelinventorysync_delete", kwargs={"pk": ecom_sync_b.pk})
    assert client_a.post(url_delete).status_code == 404


# ==============================================================================
# List Queryset Scoping Tests
# ==============================================================================

def test_inventorystock_lists_tenant_isolation(
    client_a,
    tenant_a,
    tenant_b,
    ecom_center_a,
    ecom_center_b,
    ecom_allocation_a,
    ecom_allocation_b,
    ecom_backorder_a,
    ecom_backorder_b,
    ecom_sync_a,
    ecom_sync_b,
):
    # Centers list
    resp_centers = client_a.get(reverse("ecommerce:fulfillmentcenter_list"))
    centers_in_view = resp_centers.context["centers"]
    assert ecom_center_a in centers_in_view
    assert ecom_center_b not in centers_in_view

    # Allocations list
    resp_allocs = client_a.get(reverse("ecommerce:inventoryallocation_list"))
    allocs_in_view = resp_allocs.context["allocations"]
    assert ecom_allocation_a in allocs_in_view
    assert ecom_allocation_b not in allocs_in_view

    # Backorders list
    resp_backorders = client_a.get(reverse("ecommerce:backorderpolicy_list"))
    backorders_in_view = resp_backorders.context["policies"]
    assert ecom_backorder_a in backorders_in_view
    assert ecom_backorder_b not in backorders_in_view

    # Syncs list
    resp_syncs = client_a.get(reverse("ecommerce:channelinventorysync_list"))
    syncs_in_view = resp_syncs.context["syncs"]
    assert ecom_sync_a in syncs_in_view
    assert ecom_sync_b not in syncs_in_view


# ==============================================================================
# Audit Log Tests
# ==============================================================================

def test_inventorystock_audit_log_emission_on_delete(client_a, tenant_a, ecom_center_a):
    initial_count = AuditLog.objects.filter(tenant=tenant_a, action="delete").count()
    url = reverse("ecommerce:fulfillmentcenter_delete", kwargs={"pk": ecom_center_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    new_count = AuditLog.objects.filter(tenant=tenant_a, action="delete").count()
    assert new_count == initial_count + 1
    log = AuditLog.objects.filter(tenant=tenant_a, action="delete").latest("at")
    assert log.action == "delete"
    assert ecom_center_a.name in log.target or ecom_center_a.code in str(log.changes)
