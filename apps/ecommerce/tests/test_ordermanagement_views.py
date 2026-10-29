"""Comprehensive view, route, filter, and CRUD tests for eCommerce 9.5 OMS.

Covers:
- EcommerceOrder views & cancellation workflow
- OrderRoutingRule views
- OrderFulfillment views & carrier dispatch ship workflow
- ReturnMerchandiseAuthorization views & settlement workflow

Naming conventions enforced:
- Test functions: test_ordermanagement_*
- Module-level helpers: _ordermanagement_*
"""
from decimal import Decimal
import pytest
from django.urls import reverse

from apps.ecommerce.models import (
    EcommerceOrder,
    EcommerceOrderLine,
    OrderRoutingRule,
    OrderFulfillment,
    ReturnMerchandiseAuthorization,
)
from apps.ecommerce.tests.conftest import (
    ORDERMANAGEMENT_URLS,
    _ordermanagement_order,
    _ordermanagement_line,
    _ordermanagement_routing_rule,
    _ordermanagement_fulfillment,
    _ordermanagement_rma,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# URL Routing Contract Test
# ==============================================================================

def test_ordermanagement_urls_contract():
    """Verify all 22 contract-pinned 9.5 routes resolve successfully via reverse()."""
    dummy_pk = 1
    for url_name in ORDERMANAGEMENT_URLS:
        kwargs = {"pk": dummy_pk} if "<int:pk>" in ORDERMANAGEMENT_URLS[url_name] else {}
        resolved_url = reverse(f"ecommerce:{url_name}", kwargs=kwargs)
        assert resolved_url is not None
        assert resolved_url.startswith("/ecommerce/")


# ==============================================================================
# EcommerceOrder Views
# ==============================================================================

def test_ordermanagement_order_list_and_filters(client_a, tenant_a, ecom_customer_a, ecom_currency_usd):
    o1 = _ordermanagement_order(tenant_a, customer=ecom_customer_a, currency=ecom_currency_usd, status="pending_validation")
    o2 = _ordermanagement_order(tenant_a, customer=ecom_customer_a, currency=ecom_currency_usd, status="fulfilled", fulfillment_status="fulfilled")

    url = reverse("ecommerce:ecommerceorder_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "orders" in resp.context
    assert "status_choices" in resp.context
    assert "payment_status_choices" in resp.context
    assert "fulfillment_status_choices" in resp.context
    assert "fraud_risk_choices" in resp.context
    assert len(resp.context["orders"]) >= 2

    # Status filter
    resp_status = client_a.get(url, {"status": "fulfilled"})
    assert resp_status.status_code == 200
    assert any(o.pk == o2.pk for o in resp_status.context["orders"])
    assert not any(o.pk == o1.pk for o in resp_status.context["orders"])

    # Search filter by number
    resp_q = client_a.get(url, {"q": o1.number})
    assert resp_q.status_code == 200
    assert any(o.pk == o1.pk for o in resp_q.context["orders"])


def test_ordermanagement_order_detail(client_a, tenant_a, ecom_order_a, ecom_product_a, ecom_variant_a, ecom_center_a):
    _ordermanagement_line(tenant_a, ecom_order_a, product=ecom_product_a, variant=ecom_variant_a)
    _ordermanagement_fulfillment(tenant_a, ecom_order_a, fulfillment_center=ecom_center_a)
    _ordermanagement_rma(tenant_a, ecom_order_a)

    url = reverse("ecommerce:ecommerceorder_detail", kwargs={"pk": ecom_order_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["order"] == ecom_order_a
    assert len(resp.context["lines"]) == 1
    assert len(resp.context["fulfillments"]) == 1
    assert len(resp.context["returns"]) == 1


def test_ordermanagement_order_create_and_edit(client_a, tenant_a, ecom_customer_a, ecom_currency_usd):
    create_url = reverse("ecommerce:ecommerceorder_create")
    resp_get = client_a.get(create_url)
    assert resp_get.status_code == 200

    payload = {
        "customer": ecom_customer_a.pk,
        "currency": ecom_currency_usd.pk,
        "status": "pending_validation",
        "payment_status": "pending",
        "fulfillment_status": "unfulfilled",
        "fraud_risk_level": "low",
        "fraud_score": 10,
        "address_verification_status": "passed",
        "inventory_reservation_status": "none",
        "discount_amount": "0.00",
        "shipping_amount": "12.00",
        "tax_amount": "5.00",
        "shipping_name": "Bob Builder",
        "shipping_address_line1": "789 Fixer Ave",
        "shipping_city": "Denver",
        "shipping_postal_code": "80201",
        "shipping_country": "USA",
    }
    resp_post = client_a.post(create_url, payload)
    assert resp_post.status_code == 302
    created_order = EcommerceOrder.objects.filter(tenant=tenant_a, shipping_name="Bob Builder").first()
    assert created_order is not None

    edit_url = reverse("ecommerce:ecommerceorder_edit", kwargs={"pk": created_order.pk})
    resp_edit_get = client_a.get(edit_url)
    assert resp_edit_get.status_code == 200

    payload["shipping_city"] = "Boulder"
    resp_edit_post = client_a.post(edit_url, payload)
    assert resp_edit_post.status_code == 302
    created_order.refresh_from_db()
    assert created_order.shipping_city == "Boulder"


def test_ordermanagement_order_cancel_action(client_a, tenant_a, ecom_order_a):
    url = reverse("ecommerce:ecommerceorder_cancel", kwargs={"pk": ecom_order_a.pk})
    resp = client_a.post(url, {"cancellation_reason": "Buyer bought wrong item"})
    assert resp.status_code == 302
    ecom_order_a.refresh_from_db()
    assert ecom_order_a.status == "cancelled"
    assert ecom_order_a.cancellation_reason == "Buyer bought wrong item"


def test_ordermanagement_order_delete(client_a, tenant_a, ecom_customer_a, ecom_currency_usd):
    order = _ordermanagement_order(tenant_a, customer=ecom_customer_a, currency=ecom_currency_usd)
    url = reverse("ecommerce:ecommerceorder_delete", kwargs={"pk": order.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not EcommerceOrder.objects.filter(pk=order.pk).exists()


# ==============================================================================
# OrderRoutingRule Views
# ==============================================================================

def test_ordermanagement_routing_rule_list_and_filters(client_a, tenant_a, ecom_center_a):
    r1 = _ordermanagement_routing_rule(tenant_a, name="Domestic Rule", strategy="closest_location", priority=1)
    r2 = _ordermanagement_routing_rule(tenant_a, name="Dropship Rule", strategy="drop_ship_preferred", priority=5)

    url = reverse("ecommerce:orderroutingrule_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "rules" in resp.context
    assert "strategy_choices" in resp.context

    resp_filter = client_a.get(url, {"strategy": "drop_ship_preferred"})
    assert resp_filter.status_code == 200
    assert any(r.pk == r2.pk for r in resp_filter.context["rules"])
    assert not any(r.pk == r1.pk for r in resp_filter.context["rules"])


def test_ordermanagement_routing_rule_crud(client_a, tenant_a, ecom_center_a):
    create_url = reverse("ecommerce:orderroutingrule_create")
    payload = {
        "name": "Midwest Express Routing",
        "strategy": "fewest_splits",
        "priority": 3,
        "destination_country": "USA",
        "destination_region": "Midwest",
        "preferred_fulfillment_center": ecom_center_a.pk,
        "allow_split_shipment": True,
        "enable_dropship": False,
        "is_active": True,
    }
    resp = client_a.post(create_url, payload)
    assert resp.status_code == 302
    rule = OrderRoutingRule.objects.filter(tenant=tenant_a, name="Midwest Express Routing").first()
    assert rule is not None

    detail_url = reverse("ecommerce:orderroutingrule_detail", kwargs={"pk": rule.pk})
    assert client_a.get(detail_url).status_code == 200

    edit_url = reverse("ecommerce:orderroutingrule_edit", kwargs={"pk": rule.pk})
    payload["priority"] = 1
    assert client_a.post(edit_url, payload).status_code == 302
    rule.refresh_from_db()
    assert rule.priority == 1

    delete_url = reverse("ecommerce:orderroutingrule_delete", kwargs={"pk": rule.pk})
    assert client_a.post(delete_url).status_code == 302
    assert not OrderRoutingRule.objects.filter(pk=rule.pk).exists()


# ==============================================================================
# OrderFulfillment Views
# ==============================================================================

def test_ordermanagement_fulfillment_list_and_filters(client_a, tenant_a, ecom_order_a, ecom_center_a):
    f1 = _ordermanagement_fulfillment(tenant_a, ecom_order_a, fulfillment_center=ecom_center_a, status="allocated")
    f2 = _ordermanagement_fulfillment(tenant_a, ecom_order_a, fulfillment_center=ecom_center_a, status="delivered")

    url = reverse("ecommerce:orderfulfillment_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "fulfillments" in resp.context
    assert "status_choices" in resp.context

    resp_filter = client_a.get(url, {"status": "delivered"})
    assert resp_filter.status_code == 200
    assert any(f.pk == f2.pk for f in resp_filter.context["fulfillments"])
    assert not any(f.pk == f1.pk for f in resp_filter.context["fulfillments"])


def test_ordermanagement_fulfillment_crud_and_ship_action(client_a, tenant_a, ecom_order_a, ecom_center_a):
    create_url = reverse("ecommerce:orderfulfillment_create")
    payload = {
        "order": ecom_order_a.pk,
        "fulfillment_center": ecom_center_a.pk,
        "carrier_name": "FedEx Ground",
        "tracking_number": "TRACK-11223344",
        "status": "allocated",
        "shipping_cost": "18.50",
    }
    resp = client_a.post(create_url, payload)
    assert resp.status_code == 302
    ful = OrderFulfillment.objects.filter(tenant=tenant_a, tracking_number="TRACK-11223344").first()
    assert ful is not None

    detail_url = reverse("ecommerce:orderfulfillment_detail", kwargs={"pk": ful.pk})
    assert client_a.get(detail_url).status_code == 200

    ship_url = reverse("ecommerce:orderfulfillment_ship", kwargs={"pk": ful.pk})
    resp_ship = client_a.post(ship_url)
    assert resp_ship.status_code == 302
    ful.refresh_from_db()
    assert ful.status == "shipped"
    assert ful.shipped_at is not None

    delete_url = reverse("ecommerce:orderfulfillment_delete", kwargs={"pk": ful.pk})
    assert client_a.post(delete_url).status_code == 302
    assert not OrderFulfillment.objects.filter(pk=ful.pk).exists()


# ==============================================================================
# ReturnMerchandiseAuthorization Views
# ==============================================================================

def test_ordermanagement_rma_list_and_filters(client_a, tenant_a, ecom_order_a, ecom_customer_a):
    r1 = _ordermanagement_rma(tenant_a, ecom_order_a, customer=ecom_customer_a, return_type="refund", status="requested")
    r2 = _ordermanagement_rma(tenant_a, ecom_order_a, customer=ecom_customer_a, return_type="store_credit", status="completed")

    url = reverse("ecommerce:returnmerchandiseauthorization_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "returns" in resp.context
    assert "status_choices" in resp.context
    assert "return_type_choices" in resp.context
    assert "reason_choices" in resp.context

    resp_type = client_a.get(url, {"return_type": "store_credit"})
    assert resp_type.status_code == 200
    assert any(r.pk == r2.pk for r in resp_type.context["returns"])
    assert not any(r.pk == r1.pk for r in resp_type.context["returns"])


def test_ordermanagement_rma_crud_and_complete_settlement(client_a, tenant_a, ecom_order_a, ecom_customer_a, ecom_center_a):
    create_url = reverse("ecommerce:returnmerchandiseauthorization_create")
    payload = {
        "order": ecom_order_a.pk,
        "customer": ecom_customer_a.pk,
        "return_type": "refund",
        "status": "requested",
        "reason": "changed_mind",
        "restocking_fee": "5.00",
        "refund_amount": "45.00",
        "refund_status": "pending",
        "restocking_status": "pending",
        "restocking_center": ecom_center_a.pk,
    }
    resp = client_a.post(create_url, payload)
    assert resp.status_code == 302
    rma = ReturnMerchandiseAuthorization.objects.filter(tenant=tenant_a, order=ecom_order_a).first()
    assert rma is not None

    detail_url = reverse("ecommerce:returnmerchandiseauthorization_detail", kwargs={"pk": rma.pk})
    assert client_a.get(detail_url).status_code == 200

    complete_url = reverse("ecommerce:returnmerchandiseauthorization_complete", kwargs={"pk": rma.pk})
    resp_comp = client_a.post(complete_url)
    assert resp_comp.status_code == 302
    rma.refresh_from_db()
    assert rma.status == "completed"
    assert rma.completed_at is not None
    assert rma.refund_status == "processed"

    delete_url = reverse("ecommerce:returnmerchandiseauthorization_delete", kwargs={"pk": rma.pk})
    assert client_a.post(delete_url).status_code == 302
    assert not ReturnMerchandiseAuthorization.objects.filter(pk=rma.pk).exists()
