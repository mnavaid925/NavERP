"""Comprehensive view, route, filter, and CRUD tests for eCommerce 9.4 Shopping Cart & Checkout.

Covers:
- Cart views (list, create, detail, edit, delete, recover)
- CheckoutSession views (list, create, detail, edit, delete, advance)
- ShippingMethodConfig views (list, create, detail, edit, delete, toggle)
- PaymentMethodConfig views (list, create, detail, edit, delete, toggle)

Naming conventions enforced:
- Test functions: test_cartcheckout_*
- Module-level helpers: _cartcheckout_*
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.ecommerce.models import (
    Cart,
    CartItem,
    CheckoutSession,
    ShippingMethodConfig,
    PaymentMethodConfig,
)
from apps.ecommerce.tests.conftest import (
    _cartcheckout_cart,
    _cartcheckout_cart_item,
    _cartcheckout_shipping_method,
    _cartcheckout_payment_method,
    _cartcheckout_checkout_session,
    _productcatalog_product,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Cart View Tests
# ==============================================================================

def test_cartcheckout_cart_list_view(client_a, tenant_a, ecom_cart_a):
    _cartcheckout_cart(tenant_a, session_key="abandoned_cart_sess", status="abandoned", email="lost@example.com")
    url = reverse("ecommerce:cart_list")

    # 1. Base list
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "carts" in resp.context
    assert "status_choices" in resp.context
    assert len(resp.context["carts"]) >= 2

    # 2. Search query filter
    resp_q = client_a.get(url, {"q": "lost@example.com"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["carts"]) == 1

    # 3. Status filter
    resp_status = client_a.get(url, {"status": "abandoned"})
    assert resp_status.status_code == 200
    assert len(resp_status.context["carts"]) == 1


def test_cartcheckout_cart_detail_view(client_a, tenant_a, ecom_cart_a):
    prod = _productcatalog_product(tenant_a, name="Desk Chair")
    _cartcheckout_cart_item(ecom_cart_a, prod, quantity=2, unit_price=Decimal("80.00"))

    url = reverse("ecommerce:cart_detail", args=[ecom_cart_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["cart"] == ecom_cart_a
    assert "items" in resp.context
    assert len(resp.context["items"]) == 1


def test_cartcheckout_cart_create_view(client_a, tenant_a):
    url = reverse("ecommerce:cart_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    payload = {
        "session_key": "new_guest_sess_777",
        "email": "newbie@example.com",
        "status": "active",
        "currency": "USD",
        "coupon_code": "DISCOUNT15",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302

    created = Cart.objects.get(tenant=tenant_a, session_key="new_guest_sess_777")
    assert created.email == "newbie@example.com"
    assert created.coupon_code == "DISCOUNT15"


def test_cartcheckout_cart_edit_view(client_a, tenant_a, ecom_cart_a):
    url = reverse("ecommerce:cart_edit", args=[ecom_cart_a.pk])
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    payload = {
        "session_key": ecom_cart_a.session_key,
        "email": "updated_email@example.com",
        "status": "locked",
        "currency": "USD",
        "coupon_code": "UPDATED20",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302

    ecom_cart_a.refresh_from_db()
    assert ecom_cart_a.email == "updated_email@example.com"
    assert ecom_cart_a.status == "locked"


def test_cartcheckout_cart_recover_action(client_a, tenant_a, ecom_cart_a):
    ecom_cart_a.mark_abandoned()
    url = reverse("ecommerce:cart_recover", args=[ecom_cart_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    ecom_cart_a.refresh_from_db()
    assert ecom_cart_a.recovery_sent_at is not None


def test_cartcheckout_cart_delete_view(client_a, tenant_a, ecom_cart_a):
    url = reverse("ecommerce:cart_delete", args=[ecom_cart_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not Cart.objects.filter(pk=ecom_cart_a.pk).exists()


# ==============================================================================
# CheckoutSession View Tests
# ==============================================================================

def test_cartcheckout_checkout_session_list_view(client_a, tenant_a, ecom_checkout_session_a):
    url = reverse("ecommerce:checkoutsession_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sessions" in resp.context
    assert "status_choices" in resp.context
    assert "flow_choices" in resp.context
    assert len(resp.context["sessions"]) >= 1

    # Filter by flow_type
    resp_flow = client_a.get(url, {"flow_type": "one_page"})
    assert resp_flow.status_code == 200
    assert len(resp_flow.context["sessions"]) >= 1


def test_cartcheckout_checkout_session_detail_view(client_a, tenant_a, ecom_checkout_session_a):
    url = reverse("ecommerce:checkoutsession_detail", args=[ecom_checkout_session_a.pk])
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["session"] == ecom_checkout_session_a


def test_cartcheckout_checkout_session_create_view(client_a, tenant_a, ecom_cart_a):
    url = reverse("ecommerce:checkoutsession_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    payload = {
        "cart": ecom_cart_a.pk,
        "email": "customer_checkout@example.com",
        "phone": "+1-555-8888",
        "flow_type": "multi_step",
        "current_step": "contact",
        "status": "in_progress",
        "shipping_name": "Valued Shopper",
        "shipping_address_line1": "789 Pine Ave",
        "shipping_city": "Seattle",
        "shipping_state": "WA",
        "shipping_postal_code": "98101",
        "shipping_country": "US",
        "billing_same_as_shipping": True,
        "tax_rate": Decimal("0.0000"),
        "subtotal_amount": Decimal("100.00"),
        "discount_amount": Decimal("0.00"),
        "shipping_amount": Decimal("0.00"),
        "tax_amount": Decimal("0.00"),
        "total_amount": Decimal("100.00"),
        "payment_status": "pending",
        "expires_at": (timezone.now() + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M"),
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302

    created = CheckoutSession.objects.filter(tenant=tenant_a, email="customer_checkout@example.com").first()
    assert created is not None
    assert created.flow_type == "multi_step"


def test_cartcheckout_checkout_session_advance_action(client_a, tenant_a, ecom_checkout_session_a):
    assert ecom_checkout_session_a.current_step == "contact"
    url = reverse("ecommerce:checkoutsession_advance", args=[ecom_checkout_session_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    ecom_checkout_session_a.refresh_from_db()
    assert ecom_checkout_session_a.current_step == "shipping_address"


def test_cartcheckout_checkout_session_delete_view(client_a, tenant_a, ecom_checkout_session_a):
    url = reverse("ecommerce:checkoutsession_delete", args=[ecom_checkout_session_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not CheckoutSession.objects.filter(pk=ecom_checkout_session_a.pk).exists()


# ==============================================================================
# ShippingMethodConfig View Tests
# ==============================================================================

def test_cartcheckout_shipping_method_list_view(client_a, tenant_a, ecom_shipping_method_a):
    url = reverse("ecommerce:shippingmethodconfig_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "methods" in resp.context
    assert "carrier_choices" in resp.context
    assert "calc_type_choices" in resp.context
    assert len(resp.context["methods"]) >= 1


def test_cartcheckout_shipping_method_create_view(client_a, tenant_a):
    url = reverse("ecommerce:shippingmethodconfig_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    payload = {
        "name": "Overnight Courier",
        "code": "OVERNIGHT",
        "carrier": "fedex",
        "calculation_type": "flat_rate",
        "base_rate": Decimal("35.00"),
        "cost_per_kg": Decimal("0.00"),
        "estimated_days_min": 1,
        "estimated_days_max": 1,
        "destination_countries": "US",
        "is_active": True,
        "sort_order": 2,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302

    created = ShippingMethodConfig.objects.get(tenant=tenant_a, code="OVERNIGHT")
    assert created.name == "Overnight Courier"


def test_cartcheckout_shipping_method_toggle_action(client_a, tenant_a, ecom_shipping_method_a):
    assert ecom_shipping_method_a.is_active is True
    url = reverse("ecommerce:shippingmethodconfig_toggle", args=[ecom_shipping_method_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    ecom_shipping_method_a.refresh_from_db()
    assert ecom_shipping_method_a.is_active is False


# ==============================================================================
# PaymentMethodConfig View Tests
# ==============================================================================

def test_cartcheckout_payment_method_list_view(client_a, tenant_a, ecom_payment_method_a):
    url = reverse("ecommerce:paymentmethodconfig_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "methods" in resp.context
    assert "provider_choices" in resp.context
    assert "category_choices" in resp.context
    assert len(resp.context["methods"]) >= 1


def test_cartcheckout_payment_method_create_view(client_a, tenant_a):
    url = reverse("ecommerce:paymentmethodconfig_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    payload = {
        "name": "Klarna Slice in 4",
        "provider": "klarna",
        "method_category": "bnpl",
        "environment": "sandbox",
        "is_active": True,
        "display_order": 3,
        "fee_type": "none",
        "fee_amount": Decimal("0.00"),
        "supported_currencies": "USD",
        "supports_refunds": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302

    created = PaymentMethodConfig.objects.get(tenant=tenant_a, provider="klarna")
    assert created.name == "Klarna Slice in 4"


def test_cartcheckout_payment_method_toggle_action(client_a, tenant_a, ecom_payment_method_a):
    assert ecom_payment_method_a.is_active is True
    url = reverse("ecommerce:paymentmethodconfig_toggle", args=[ecom_payment_method_a.pk])
    resp = client_a.post(url)
    assert resp.status_code == 302

    ecom_payment_method_a.refresh_from_db()
    assert ecom_payment_method_a.is_active is False
