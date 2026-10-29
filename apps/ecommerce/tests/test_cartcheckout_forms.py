"""Form validation and tenant isolation tests for eCommerce 9.4 Shopping Cart & Checkout.

Covers:
- CartForm
- CartItemForm
- CheckoutSessionForm
- ShippingMethodConfigForm
- PaymentMethodConfigForm

Naming conventions enforced:
- Test functions: test_cartcheckout_*
- Module-level helpers: _cartcheckout_*
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.accounting.models import TaxCode
from apps.core.models import Party, PartyRole
from apps.ecommerce.forms.CartCheckout.Carts import CartForm, CartItemForm
from apps.ecommerce.forms.CartCheckout.CheckoutSessions import CheckoutSessionForm
from apps.ecommerce.forms.CartCheckout.ShippingMethods import ShippingMethodConfigForm
from apps.ecommerce.forms.CartCheckout.PaymentMethods import PaymentMethodConfigForm
from apps.ecommerce.models import (
    Cart,
    CartItem,
    CheckoutSession,
    ShippingMethodConfig,
    PaymentMethodConfig,
)
from apps.ecommerce.tests.conftest import (
    _cartcheckout_cart,
    _cartcheckout_shipping_method,
    _cartcheckout_payment_method,
    _cartcheckout_checkout_session,
    _productcatalog_product,
    _productcatalog_variant,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_cartcheckout_*)
# ==============================================================================

def _cartcheckout_create_party_customer(tenant, name="Customer Tester"):
    party = Party.objects.create(tenant=tenant, name=name, kind="person")
    PartyRole.objects.create(party=party, role="customer")
    return party


def _cartcheckout_create_tax_code(tenant, code="SALESTAX"):
    return TaxCode.objects.create(
        tenant=tenant,
        code=code,
        name=f"Tax {code}",
        rate=Decimal("0.0825"),
    )


# ==============================================================================
# CartForm & CartItemForm Tests
# ==============================================================================

def test_cartcheckout_cart_form_valid(tenant_a):
    cust_a = _cartcheckout_create_party_customer(tenant_a, name="Alice Buyer")
    data = {
        "customer": cust_a.pk,
        "session_key": "sess_form_valid_123",
        "email": "alice@example.com",
        "status": "active",
        "currency": "USD",
        "coupon_code": "WELCOME10",
        "notes": "Gift wrap requested",
    }
    form = CartForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    cart = form.save(commit=False)
    cart.tenant = tenant_a
    cart.save()
    assert cart.pk is not None
    assert cart.customer == cust_a
    assert cart.coupon_code == "WELCOME10"


def test_cartcheckout_cart_form_rejects_foreign_customer(tenant_a, tenant_b):
    cust_b = _cartcheckout_create_party_customer(tenant_b, name="Foreign Buyer")
    data = {
        "customer": cust_b.pk,
        "email": "foreign@example.com",
        "status": "active",
        "currency": "USD",
    }
    form = CartForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer" in form.errors


def test_cartcheckout_cart_item_form_valid_and_tenant_scoped(tenant_a, tenant_b):
    cart_a = _cartcheckout_cart(tenant_a)
    prod_a = _productcatalog_product(tenant_a, name="Canvas Backpack")
    var_a = _productcatalog_variant(tenant_a, prod_a, name="Olive Green", price=Decimal("45.00"))

    data = {
        "product": prod_a.pk,
        "variant": var_a.pk,
        "quantity": 2,
        "unit_price": Decimal("45.00"),
        "total_price": Decimal("90.00"),
    }
    form = CartItemForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    item = form.save(commit=False)
    item.cart = cart_a
    item.save()
    assert item.pk is not None
    assert item.quantity == 2

    # Reject foreign product from tenant_b
    prod_b = _productcatalog_product(tenant_b, name="Foreign Product")
    bad_data = data.copy()
    bad_data["product"] = prod_b.pk
    bad_form = CartItemForm(data=bad_data, tenant=tenant_a)
    assert not bad_form.is_valid()
    assert "product" in bad_form.errors


# ==============================================================================
# CheckoutSessionForm Tests
# ==============================================================================

def test_cartcheckout_checkout_session_form_valid(tenant_a, ecom_cart_a):
    cust_a = _cartcheckout_create_party_customer(tenant_a, name="Bob Builder")
    ship_a = _cartcheckout_shipping_method(tenant_a, name="Ground Express", code="EXP-01")
    pay_a = _cartcheckout_payment_method(tenant_a, name="Credit Card Stripe")
    tax_a = _cartcheckout_create_tax_code(tenant_a, code="STATE-TX")

    data = {
        "cart": ecom_cart_a.pk,
        "customer": cust_a.pk,
        "email": "bob@example.com",
        "phone": "+1-555-0199",
        "flow_type": "one_page",
        "current_step": "contact",
        "status": "in_progress",
        "shipping_name": "Bob Builder",
        "shipping_address_line1": "456 Market St",
        "shipping_city": "Austin",
        "shipping_state": "TX",
        "shipping_postal_code": "78701",
        "shipping_country": "US",
        "billing_same_as_shipping": True,
        "shipping_method": ship_a.pk,
        "payment_method": pay_a.pk,
        "tax_code": tax_a.pk,
        "tax_jurisdiction": "Travis County",
        "tax_rate": Decimal("0.0825"),
        "subtotal_amount": Decimal("100.00"),
        "discount_amount": Decimal("0.00"),
        "shipping_amount": Decimal("10.00"),
        "tax_amount": Decimal("8.25"),
        "total_amount": Decimal("118.25"),
        "payment_status": "pending",
        "expires_at": "2026-11-01T12:00",
    }
    form = CheckoutSessionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    session = form.save(commit=False)
    session.tenant = tenant_a
    session.save()
    assert session.pk is not None
    assert session.email == "bob@example.com"
    assert session.shipping_method == ship_a


def test_cartcheckout_checkout_session_form_rejects_foreign_relations(tenant_a, tenant_b, ecom_cart_a, ecom_cart_b):
    # Foreign shipping and payment methods
    ship_b = _cartcheckout_shipping_method(tenant_b, name="Foreign Ground", code="F-GND")
    pay_b = _cartcheckout_payment_method(tenant_b, name="Foreign Stripe")

    data = {
        "cart": ecom_cart_b.pk,  # Foreign cart!
        "email": "alien@example.com",
        "flow_type": "one_page",
        "current_step": "contact",
        "status": "in_progress",
        "shipping_method": ship_b.pk,
        "payment_method": pay_b.pk,
        "shipping_country": "US",
        "billing_country": "US",
        "expires_at": "2026-11-01T12:00",
    }
    form = CheckoutSessionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "cart" in form.errors
    assert "shipping_method" in form.errors
    assert "payment_method" in form.errors


# ==============================================================================
# ShippingMethodConfigForm Tests
# ==============================================================================

def test_cartcheckout_shipping_method_form_valid_and_normalization(tenant_a):
    data = {
        "name": "Standard Priority Courier",
        "code": "  courier_pri  ",  # tests code stripping & uppercase
        "carrier": "fedex",
        "calculation_type": "flat_rate",
        "base_rate": Decimal("14.50"),
        "cost_per_kg": Decimal("1.25"),
        "free_shipping_threshold": Decimal("100.00"),
        "estimated_days_min": 2,
        "estimated_days_max": 4,
        "destination_countries": " us, ca ,  mx ",  # tests list normalization
        "is_active": True,
        "sort_order": 5,
        "description": "Fast nationwide FedEx 2-4 day service",
    }
    form = ShippingMethodConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    shipping = form.save(commit=False)
    shipping.tenant = tenant_a
    shipping.save()
    assert shipping.pk is not None
    assert shipping.code == "COURIER_PRI"
    assert shipping.destination_countries == "US,CA,MX"


def test_cartcheckout_shipping_method_form_default_destination_countries(tenant_a):
    data = {
        "name": "Worldwide DHL",
        "code": "DHL_WW",
        "carrier": "dhl",
        "calculation_type": "weight_tiered",
        "base_rate": Decimal("25.00"),
        "cost_per_kg": Decimal("5.00"),
        "estimated_days_min": 3,
        "estimated_days_max": 7,
        "destination_countries": "",  # Empty should default to ALL
        "is_active": True,
        "sort_order": 1,
    }
    form = ShippingMethodConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    shipping = form.save(commit=False)
    shipping.tenant = tenant_a
    shipping.save()
    assert shipping.destination_countries == "ALL"


# ==============================================================================
# PaymentMethodConfigForm Tests
# ==============================================================================

def test_cartcheckout_payment_method_form_valid_and_normalization(tenant_a):
    data = {
        "name": "PayPal Checkout Express",
        "provider": "paypal",
        "method_category": "wallet",
        "environment": "sandbox",
        "is_active": True,
        "display_order": 2,
        "fee_type": "percentage",
        "fee_amount": Decimal("2.90"),
        "min_order_amount": Decimal("1.00"),
        "max_order_amount": Decimal("2000.00"),
        "supported_currencies": " usd, eur,  gbp ",  # tests currency normalization
        "instructions": "Log in with your PayPal account at step 4.",
        "supports_refunds": True,
    }
    form = PaymentMethodConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    payment = form.save(commit=False)
    payment.tenant = tenant_a
    payment.save()
    assert payment.pk is not None
    assert payment.supported_currencies == "USD,EUR,GBP"
    assert payment.fee_amount == Decimal("2.90")


def test_cartcheckout_payment_method_form_default_supported_currencies(tenant_a):
    data = {
        "name": "Cash on Delivery",
        "provider": "cod",
        "method_category": "cash_on_delivery",
        "environment": "production",
        "is_active": True,
        "display_order": 10,
        "fee_type": "fixed",
        "fee_amount": Decimal("5.00"),
        "supported_currencies": "",  # Empty should default to USD
        "supports_refunds": False,
    }
    form = PaymentMethodConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    payment = form.save(commit=False)
    payment.tenant = tenant_a
    payment.save()
    assert payment.supported_currencies == "USD"
