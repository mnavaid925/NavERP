"""Unit and invariant tests for eCommerce 9.4 Shopping Cart & Checkout models.

Covers:
- Cart
- CartItem
- CheckoutSession
- ShippingMethodConfig
- PaymentMethodConfig

Naming conventions enforced:
- Test functions: test_cartcheckout_*
- Module-level helpers: _cartcheckout_*
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.db import IntegrityError, transaction
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
    _productcatalog_variant,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Cart & CartItem Model Tests
# ==============================================================================

def test_cartcheckout_cart_creation_and_auto_number(tenant_a):
    cart = _cartcheckout_cart(tenant_a, session_key="sess_cart_01")
    assert cart.pk is not None
    assert cart.number.startswith("ECRT-")
    assert cart.status == "active"
    assert cart.currency == "USD"
    assert cart.subtotal == Decimal("100.00")
    assert "sess_cart_01" in str(cart) or cart.number in str(cart)


def test_cartcheckout_cart_unique_number_per_tenant(tenant_a, tenant_b):
    cart_a = _cartcheckout_cart(tenant_a, session_key="cart_tnt_a")
    cart_b = _cartcheckout_cart(tenant_b, session_key="cart_tnt_b")
    assert cart_a.pk is not None
    assert cart_b.pk is not None

    # Duplicate number in same tenant raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Cart.objects.create(
                tenant=tenant_a,
                number=cart_a.number,
                session_key="cart_dup",
            )


def test_cartcheckout_cart_recalculate_totals_and_item_count(tenant_a):
    cart = _cartcheckout_cart(
        tenant_a,
        subtotal=Decimal("0.00"),
        discount_total=Decimal("10.00"),
        shipping_total=Decimal("5.00"),
        tax_total=Decimal("2.50"),
        grand_total=Decimal("0.00"),
    )
    product = _productcatalog_product(tenant_a, name="Test Product")
    variant = _productcatalog_variant(tenant_a, product, name="Variant X", price=Decimal("25.00"))

    item1 = _cartcheckout_cart_item(cart, product, variant=variant, quantity=2, unit_price=Decimal("25.00"))
    item2 = _cartcheckout_cart_item(cart, product, variant=None, quantity=1, unit_price=Decimal("15.00"))

    assert cart.item_count == 3
    cart.recalculate_totals()
    cart.refresh_from_db()

    # Subtotal: (25 * 2) + (15 * 1) = 65.00
    assert cart.subtotal == Decimal("65.00")
    # Grand Total: 65.00 - 10.00 (discount) + 5.00 (shipping) + 2.50 (tax) = 62.50
    assert cart.grand_total == Decimal("62.50")


def test_cartcheckout_cart_recovery_and_abandonment(tenant_a):
    cart = _cartcheckout_cart(tenant_a, status="active")
    assert cart.abandoned_at is None
    assert not cart.recovery_token

    cart.mark_abandoned()
    cart.refresh_from_db()

    assert cart.status == "abandoned"
    assert cart.abandoned_at is not None
    assert cart.recovery_token is not None
    assert len(cart.recovery_token) > 20


def test_cartcheckout_cart_item_creation_and_auto_total_price(tenant_a):
    cart = _cartcheckout_cart(tenant_a)
    product = _productcatalog_product(tenant_a, name="Desk Lamp")
    variant = _productcatalog_variant(tenant_a, product, name="Lamp Black", price=Decimal("40.00"))

    # When unit_price is 0 or None, variant.price is picked up
    item = CartItem.objects.create(
        cart=cart,
        product=product,
        variant=variant,
        quantity=3,
        unit_price=Decimal("0.00"),
    )
    assert item.unit_price == Decimal("40.00")
    assert item.total_price == Decimal("120.00")
    assert "Lamp Black" in str(item) or "Desk Lamp" in str(item)


# ==============================================================================
# CheckoutSession Model Tests
# ==============================================================================

def test_cartcheckout_checkout_session_creation_and_auto_number(tenant_a, ecom_cart_a):
    session = _cartcheckout_checkout_session(
        tenant_a,
        ecom_cart_a,
        email="buyer@example.com",
        shipping_name="John Doe",
        shipping_address_line1="100 Main St",
        shipping_city="Boston",
        shipping_state="MA",
        shipping_postal_code="02101",
        shipping_country="US",
    )
    assert session.pk is not None
    assert session.number.startswith("ECKS-")
    assert session.expires_at is not None
    assert session.billing_name == "John Doe"
    assert session.billing_address_line1 == "100 Main St"
    assert session.billing_city == "Boston"
    assert "buyer@example.com" in str(session)


def test_cartcheckout_checkout_session_unique_number_per_tenant(tenant_a, tenant_b, ecom_cart_a, ecom_cart_b):
    sess_a = _cartcheckout_checkout_session(tenant_a, ecom_cart_a)
    sess_b = _cartcheckout_checkout_session(tenant_b, ecom_cart_b)
    assert sess_a.pk is not None
    assert sess_b.pk is not None

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CheckoutSession.objects.create(
                tenant=tenant_a,
                number=sess_a.number,
                cart=ecom_cart_a,
                email="dup@example.com",
                expires_at=timezone.now() + timedelta(hours=24),
            )


def test_cartcheckout_checkout_session_step_advance(tenant_a, ecom_cart_a):
    session = _cartcheckout_checkout_session(
        tenant_a,
        ecom_cart_a,
        current_step="contact",
        status="in_progress",
    )
    assert session.current_step == "contact"

    # Step progression: contact -> shipping_address -> shipping_method -> payment -> review -> completed
    session.advance_step()
    assert session.current_step == "shipping_address"

    session.advance_step()
    assert session.current_step == "shipping_method"

    session.advance_step()
    assert session.current_step == "payment"

    session.advance_step()
    assert session.current_step == "review"

    session.advance_step()
    assert session.current_step == "completed"
    assert session.status == "completed"
    assert session.completed_at is not None


# ==============================================================================
# ShippingMethodConfig Model Tests
# ==============================================================================

def test_cartcheckout_shipping_method_creation_and_auto_number(tenant_a):
    shipping = _cartcheckout_shipping_method(tenant_a, name="Express Delivery", code="express_air")
    assert shipping.pk is not None
    assert shipping.number.startswith("ESHP-")
    assert shipping.code == "EXPRESS_AIR"  # Uppercase normalization
    assert "Express Delivery" in str(shipping)


def test_cartcheckout_shipping_method_unique_code_per_tenant(tenant_a, tenant_b):
    _cartcheckout_shipping_method(tenant_a, name="Standard 1", code="STD")
    # Allowed across tenants
    ship_b = _cartcheckout_shipping_method(tenant_b, name="Standard 2", code="STD")
    assert ship_b.pk is not None

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _cartcheckout_shipping_method(tenant_a, name="Standard 3", code="STD")


def test_cartcheckout_shipping_method_calculate_rate(tenant_a):
    # 1. Flat Rate
    flat = _cartcheckout_shipping_method(
        tenant_a,
        code="FLAT",
        calculation_type="flat_rate",
        base_rate=Decimal("15.00"),
    )
    assert flat.calculate_rate(Decimal("100.00"), total_weight_kg=5) == Decimal("15.00")

    # 2. Local Pickup (always 0.00)
    pickup = _cartcheckout_shipping_method(
        tenant_a,
        code="PICKUP",
        calculation_type="local_pickup",
        base_rate=Decimal("20.00"),
    )
    assert pickup.calculate_rate(Decimal("50.00")) == Decimal("0.00")

    # 3. Free Threshold
    threshold_method = _cartcheckout_shipping_method(
        tenant_a,
        code="FREE_OVER_50",
        calculation_type="free_threshold",
        base_rate=Decimal("12.00"),
        free_shipping_threshold=Decimal("50.00"),
    )
    assert threshold_method.calculate_rate(Decimal("49.99")) == Decimal("12.00")
    assert threshold_method.calculate_rate(Decimal("50.00")) == Decimal("0.00")
    assert threshold_method.calculate_rate(Decimal("120.00")) == Decimal("0.00")

    # 4. Weight Tiered
    tiered = _cartcheckout_shipping_method(
        tenant_a,
        code="WEIGHT",
        calculation_type="weight_tiered",
        base_rate=Decimal("10.00"),
        cost_per_kg=Decimal("2.50"),
    )
    # base 10 + (4kg * 2.50) = 20.00
    assert tiered.calculate_rate(Decimal("100.00"), total_weight_kg=4) == Decimal("20.00")


# ==============================================================================
# PaymentMethodConfig Model Tests
# ==============================================================================

def test_cartcheckout_payment_method_creation_and_auto_number(tenant_a):
    payment = _cartcheckout_payment_method(tenant_a, name="PayPal Gateway", provider="paypal")
    assert payment.pk is not None
    assert payment.number.startswith("EPMC-")
    assert payment.supports_refunds is True
    assert "PayPal Gateway" in str(payment)


def test_cartcheckout_payment_method_surcharge_calculation(tenant_a):
    # None fee
    p_none = _cartcheckout_payment_method(tenant_a, name="Card", fee_type="none", fee_amount=Decimal("0.00"))
    assert p_none.calculate_surcharge(Decimal("200.00")) == Decimal("0.00")

    # Fixed fee
    p_fixed = _cartcheckout_payment_method(tenant_a, name="COD", fee_type="fixed", fee_amount=Decimal("5.50"))
    assert p_fixed.calculate_surcharge(Decimal("200.00")) == Decimal("5.50")

    # Percentage fee: 3.5% of 200 = 7.00
    p_pct = _cartcheckout_payment_method(tenant_a, name="Klarna", fee_type="percentage", fee_amount=Decimal("3.50"))
    assert p_pct.calculate_surcharge(Decimal("200.00")) == Decimal("7.00")


def test_cartcheckout_payment_method_eligibility(tenant_a):
    method = _cartcheckout_payment_method(
        tenant_a,
        name="Wire Transfer",
        min_order_amount=Decimal("100.00"),
        max_order_amount=Decimal("5000.00"),
    )
    assert method.is_eligible_for_amount(Decimal("99.99")) is False
    assert method.is_eligible_for_amount(Decimal("100.00")) is True
    assert method.is_eligible_for_amount(Decimal("2500.00")) is True
    assert method.is_eligible_for_amount(Decimal("5000.00")) is True
    assert method.is_eligible_for_amount(Decimal("5000.01")) is False
