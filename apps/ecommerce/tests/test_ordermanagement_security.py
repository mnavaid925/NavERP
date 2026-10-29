"""Comprehensive multi-tenancy, authorization, and IDOR isolation tests for eCommerce 9.5 OMS.

Covers:
- Unauthenticated access prevention (login redirect)
- Cross-tenant IDOR defense (404 on foreign tenant records for detail/edit/actions/delete)
- Queryset isolation on all list views
- Tenant admin restrictions on destructive endpoints (403 Forbidden for members)
- Immutable AuditLog emission on CRUD deletions

Naming conventions enforced:
- Test functions: test_ordermanagement_*
- Module-level helpers: _ordermanagement_*
"""
import pytest
from django.urls import reverse

from apps.core.models import AuditLog
from apps.ecommerce.models import (
    EcommerceOrder,
    OrderRoutingRule,
    OrderFulfillment,
    ReturnMerchandiseAuthorization,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Anonymous Access Tests
# ==============================================================================

@pytest.mark.parametrize(
    "url_name,args",
    [
        ("ecommerceorder_list", []),
        ("ecommerceorder_create", []),
        ("orderroutingrule_list", []),
        ("orderroutingrule_create", []),
        ("orderfulfillment_list", []),
        ("orderfulfillment_create", []),
        ("returnmerchandiseauthorization_list", []),
        ("returnmerchandiseauthorization_create", []),
    ],
)
def test_ordermanagement_anonymous_redirects_to_login(client, url_name, args):
    url = reverse(f"ecommerce:{url_name}", args=args)
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url or "/login/" in response.url


# ==============================================================================
# Cross-Tenant IDOR Tests
# ==============================================================================

def test_ordermanagement_order_cross_tenant_idor(client_a, ecom_order_b):
    """Test client_a cannot view, edit, cancel, or delete client_b's order."""
    # Detail -> 404
    url_detail = reverse("ecommerce:ecommerceorder_detail", kwargs={"pk": ecom_order_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit -> 404
    url_edit = reverse("ecommerce:ecommerceorder_edit", kwargs={"pk": ecom_order_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"shipping_name": "Hacked Recipient"}).status_code == 404

    # Cancel -> 404
    url_cancel = reverse("ecommerce:ecommerceorder_cancel", kwargs={"pk": ecom_order_b.pk})
    assert client_a.post(url_cancel, {"cancellation_reason": "Hacked Cancel"}).status_code == 404

    # Delete -> 404
    url_delete = reverse("ecommerce:ecommerceorder_delete", kwargs={"pk": ecom_order_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_ordermanagement_routing_rule_cross_tenant_idor(client_a, ecom_routing_rule_b):
    """Test client_a cannot view, edit, or delete client_b's routing rule."""
    # Detail -> 404
    url_detail = reverse("ecommerce:orderroutingrule_detail", kwargs={"pk": ecom_routing_rule_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit -> 404
    url_edit = reverse("ecommerce:orderroutingrule_edit", kwargs={"pk": ecom_routing_rule_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked Route"}).status_code == 404

    # Delete -> 404
    url_delete = reverse("ecommerce:orderroutingrule_delete", kwargs={"pk": ecom_routing_rule_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_ordermanagement_fulfillment_cross_tenant_idor(client_a, ecom_fulfillment_b):
    """Test client_a cannot view, edit, ship, or delete client_b's fulfillment package."""
    # Detail -> 404
    url_detail = reverse("ecommerce:orderfulfillment_detail", kwargs={"pk": ecom_fulfillment_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit -> 404
    url_edit = reverse("ecommerce:orderfulfillment_edit", kwargs={"pk": ecom_fulfillment_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"carrier_name": "Hacked Carrier"}).status_code == 404

    # Ship -> 404
    url_ship = reverse("ecommerce:orderfulfillment_ship", kwargs={"pk": ecom_fulfillment_b.pk})
    assert client_a.post(url_ship).status_code == 404

    # Delete -> 404
    url_delete = reverse("ecommerce:orderfulfillment_delete", kwargs={"pk": ecom_fulfillment_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_ordermanagement_rma_cross_tenant_idor(client_a, ecom_rma_b):
    """Test client_a cannot view, edit, complete, or delete client_b's RMA."""
    # Detail -> 404
    url_detail = reverse("ecommerce:returnmerchandiseauthorization_detail", kwargs={"pk": ecom_rma_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit -> 404
    url_edit = reverse("ecommerce:returnmerchandiseauthorization_edit", kwargs={"pk": ecom_rma_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"refund_amount": "9999.00"}).status_code == 404

    # Complete -> 404
    url_complete = reverse("ecommerce:returnmerchandiseauthorization_complete", kwargs={"pk": ecom_rma_b.pk})
    assert client_a.post(url_complete).status_code == 404

    # Delete -> 404
    url_delete = reverse("ecommerce:returnmerchandiseauthorization_delete", kwargs={"pk": ecom_rma_b.pk})
    assert client_a.post(url_delete).status_code == 404


# ==============================================================================
# List Queryset Isolation Tests
# ==============================================================================

def test_ordermanagement_lists_tenant_isolation(
    client_a,
    tenant_a,
    tenant_b,
    ecom_order_a,
    ecom_order_b,
    ecom_routing_rule_a,
    ecom_routing_rule_b,
    ecom_fulfillment_a,
    ecom_fulfillment_b,
    ecom_rma_a,
    ecom_rma_b,
):
    """Test all 4 list views isolate querysets strictly by request.tenant."""
    # Orders list
    resp_orders = client_a.get(reverse("ecommerce:ecommerceorder_list"))
    orders_in_view = resp_orders.context["orders"]
    assert any(o.pk == ecom_order_a.pk for o in orders_in_view)
    assert not any(o.pk == ecom_order_b.pk for o in orders_in_view)

    # Routing rules list
    resp_rules = client_a.get(reverse("ecommerce:orderroutingrule_list"))
    rules_in_view = resp_rules.context["rules"]
    assert any(r.pk == ecom_routing_rule_a.pk for r in rules_in_view)
    assert not any(r.pk == ecom_routing_rule_b.pk for r in rules_in_view)

    # Fulfillments list
    resp_ful = client_a.get(reverse("ecommerce:orderfulfillment_list"))
    ful_in_view = resp_ful.context["fulfillments"]
    assert any(f.pk == ecom_fulfillment_a.pk for f in ful_in_view)
    assert not any(f.pk == ecom_fulfillment_b.pk for f in ful_in_view)

    # RMAs list
    resp_rmas = client_a.get(reverse("ecommerce:returnmerchandiseauthorization_list"))
    rmas_in_view = resp_rmas.context["returns"]
    assert any(r.pk == ecom_rma_a.pk for r in rmas_in_view)
    assert not any(r.pk == ecom_rma_b.pk for r in rmas_in_view)


# ==============================================================================
# Tenant Admin Restriction Tests
# ==============================================================================

def test_ordermanagement_non_admin_member_delete_forbidden(
    member_client,
    tenant_a,
    ecom_order_a,
    ecom_routing_rule_a,
    ecom_fulfillment_a,
    ecom_rma_a,
):
    """Test non-admin member gets 403 Forbidden on tenant-admin protected delete endpoints."""
    # Order delete
    url_order_del = reverse("ecommerce:ecommerceorder_delete", kwargs={"pk": ecom_order_a.pk})
    assert member_client.post(url_order_del).status_code == 403
    assert EcommerceOrder.objects.filter(pk=ecom_order_a.pk).exists()

    # Routing rule delete
    url_rule_del = reverse("ecommerce:orderroutingrule_delete", kwargs={"pk": ecom_routing_rule_a.pk})
    assert member_client.post(url_rule_del).status_code == 403
    assert OrderRoutingRule.objects.filter(pk=ecom_routing_rule_a.pk).exists()

    # Fulfillment delete
    url_ful_del = reverse("ecommerce:orderfulfillment_delete", kwargs={"pk": ecom_fulfillment_a.pk})
    assert member_client.post(url_ful_del).status_code == 403
    assert OrderFulfillment.objects.filter(pk=ecom_fulfillment_a.pk).exists()

    # RMA delete
    url_rma_del = reverse("ecommerce:returnmerchandiseauthorization_delete", kwargs={"pk": ecom_rma_a.pk})
    assert member_client.post(url_rma_del).status_code == 403
    assert ReturnMerchandiseAuthorization.objects.filter(pk=ecom_rma_a.pk).exists()


# ==============================================================================
# Audit Log Emission Tests
# ==============================================================================

def test_ordermanagement_audit_log_emission_on_delete(client_a, tenant_a, ecom_order_a):
    """Test that deleting an EcommerceOrder writes an immutable AuditLog entry."""
    initial_count = AuditLog.objects.filter(tenant=tenant_a, action="delete").count()
    url = reverse("ecommerce:ecommerceorder_delete", kwargs={"pk": ecom_order_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    new_count = AuditLog.objects.filter(tenant=tenant_a, action="delete").count()
    assert new_count == initial_count + 1
    log = AuditLog.objects.filter(tenant=tenant_a, action="delete").latest("at")
    assert log.action == "delete"
    assert ecom_order_a.number in str(log.changes)
