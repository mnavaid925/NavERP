"""Multi-tenancy, authentication, and cross-tenant IDOR isolation tests for eCommerce 9.4.

Covers:
- Anonymous user access prevention (302 redirect to login)
- Cross-tenant IDOR defense (404 on all foreign tenant records)
- Queryset isolation across tenant boundaries on list views
- Mutation action guards

Naming conventions enforced:
- Test functions: test_cartcheckout_*
- Module-level helpers: _cartcheckout_*
"""
import pytest
from django.urls import reverse

from apps.ecommerce.models import (
    Cart,
    CheckoutSession,
    ShippingMethodConfig,
    PaymentMethodConfig,
)
from apps.ecommerce.tests.conftest import (
    _cartcheckout_cart,
    _cartcheckout_shipping_method,
    _cartcheckout_payment_method,
    _cartcheckout_checkout_session,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Anonymous Access Prevention Tests
# ==============================================================================

@pytest.mark.parametrize(
    "url_name,args",
    [
        ("cart_list", []),
        ("cart_create", []),
        ("checkoutsession_list", []),
        ("checkoutsession_create", []),
        ("shippingmethodconfig_list", []),
        ("shippingmethodconfig_create", []),
        ("paymentmethodconfig_list", []),
        ("paymentmethodconfig_create", []),
    ],
)
def test_cartcheckout_anonymous_redirects_to_login(client, url_name, args):
    url = reverse(f"ecommerce:{url_name}", args=args)
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url or "/login/" in response.url


# ==============================================================================
# Cross-Tenant IDOR Tests (Client A attacking Tenant B records -> 404)
# ==============================================================================

def test_cartcheckout_cart_cross_tenant_idor(client_a, ecom_cart_b):
    # Detail
    url_detail = reverse("ecommerce:cart_detail", kwargs={"pk": ecom_cart_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit
    url_edit = reverse("ecommerce:cart_edit", kwargs={"pk": ecom_cart_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"email": "hacked@example.com"}).status_code == 404

    # Recover
    url_recover = reverse("ecommerce:cart_recover", kwargs={"pk": ecom_cart_b.pk})
    assert client_a.post(url_recover).status_code == 404

    # Delete
    url_delete = reverse("ecommerce:cart_delete", kwargs={"pk": ecom_cart_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_cartcheckout_checkout_session_cross_tenant_idor(client_a, ecom_checkout_session_b):
    # Detail
    url_detail = reverse("ecommerce:checkoutsession_detail", kwargs={"pk": ecom_checkout_session_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit
    url_edit = reverse("ecommerce:checkoutsession_edit", kwargs={"pk": ecom_checkout_session_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"email": "hacked@example.com"}).status_code == 404

    # Advance
    url_advance = reverse("ecommerce:checkoutsession_advance", kwargs={"pk": ecom_checkout_session_b.pk})
    assert client_a.post(url_advance).status_code == 404

    # Delete
    url_delete = reverse("ecommerce:checkoutsession_delete", kwargs={"pk": ecom_checkout_session_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_cartcheckout_shipping_method_cross_tenant_idor(client_a, ecom_shipping_method_b):
    # Detail
    url_detail = reverse("ecommerce:shippingmethodconfig_detail", kwargs={"pk": ecom_shipping_method_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit
    url_edit = reverse("ecommerce:shippingmethodconfig_edit", kwargs={"pk": ecom_shipping_method_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked Ground"}).status_code == 404

    # Toggle
    url_toggle = reverse("ecommerce:shippingmethodconfig_toggle", kwargs={"pk": ecom_shipping_method_b.pk})
    assert client_a.post(url_toggle).status_code == 404

    # Delete
    url_delete = reverse("ecommerce:shippingmethodconfig_delete", kwargs={"pk": ecom_shipping_method_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_cartcheckout_payment_method_cross_tenant_idor(client_a, ecom_payment_method_b):
    # Detail
    url_detail = reverse("ecommerce:paymentmethodconfig_detail", kwargs={"pk": ecom_payment_method_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit
    url_edit = reverse("ecommerce:paymentmethodconfig_edit", kwargs={"pk": ecom_payment_method_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked Payment"}).status_code == 404

    # Toggle
    url_toggle = reverse("ecommerce:paymentmethodconfig_toggle", kwargs={"pk": ecom_payment_method_b.pk})
    assert client_a.post(url_toggle).status_code == 404

    # Delete
    url_delete = reverse("ecommerce:paymentmethodconfig_delete", kwargs={"pk": ecom_payment_method_b.pk})
    assert client_a.post(url_delete).status_code == 404


# ==============================================================================
# Queryset Isolation on List Views Tests
# ==============================================================================

def test_cartcheckout_list_views_tenant_isolation(
    client_a,
    tenant_a,
    tenant_b,
    ecom_cart_a,
    ecom_cart_b,
    ecom_checkout_session_a,
    ecom_checkout_session_b,
    ecom_shipping_method_a,
    ecom_shipping_method_b,
    ecom_payment_method_a,
    ecom_payment_method_b,
):
    # 1. Cart list
    resp_cart = client_a.get(reverse("ecommerce:cart_list"))
    assert resp_cart.status_code == 200
    cart_pks = [c.pk for c in resp_cart.context["carts"]]
    assert ecom_cart_a.pk in cart_pks
    assert ecom_cart_b.pk not in cart_pks

    # 2. Checkout Session list
    resp_session = client_a.get(reverse("ecommerce:checkoutsession_list"))
    assert resp_session.status_code == 200
    session_pks = [s.pk for s in resp_session.context["sessions"]]
    assert ecom_checkout_session_a.pk in session_pks
    assert ecom_checkout_session_b.pk not in session_pks

    # 3. Shipping Method list
    resp_ship = client_a.get(reverse("ecommerce:shippingmethodconfig_list"))
    assert resp_ship.status_code == 200
    ship_pks = [m.pk for m in resp_ship.context["methods"]]
    assert ecom_shipping_method_a.pk in ship_pks
    assert ecom_shipping_method_b.pk not in ship_pks

    # 4. Payment Method list
    resp_pay = client_a.get(reverse("ecommerce:paymentmethodconfig_list"))
    assert resp_pay.status_code == 200
    pay_pks = [p.pk for p in resp_pay.context["methods"]]
    assert ecom_payment_method_a.pk in pay_pks
    assert ecom_payment_method_b.pk not in pay_pks
