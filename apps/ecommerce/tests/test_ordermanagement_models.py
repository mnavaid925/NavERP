"""Comprehensive unit and invariant tests for eCommerce 9.5 Order Management System (OMS) models.

Covers:
- EcommerceOrder & EcommerceOrderLine
- OrderRoutingRule
- OrderFulfillment
- ReturnMerchandiseAuthorization

Naming conventions enforced:
- Test functions: test_ordermanagement_*
- Module-level helpers: _ordermanagement_*
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ecommerce.models import (
    EcommerceOrder,
    EcommerceOrderLine,
    OrderRoutingRule,
    OrderFulfillment,
    ReturnMerchandiseAuthorization,
)
from apps.ecommerce.tests.conftest import (
    ORDERMANAGEMENT_MODEL_FIELDS,
    ORDERMANAGEMENT_CHOICES,
    _ordermanagement_customer,
    _ordermanagement_currency,
    _ordermanagement_order,
    _ordermanagement_line,
    _ordermanagement_routing_rule,
    _ordermanagement_fulfillment,
    _ordermanagement_rma,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Model Contract Fields & Choices Tests
# ==============================================================================

def test_ordermanagement_model_fields_contract():
    """Verify all 9.5 models contain exact contract-pinned fields."""
    models_dict = {
        "EcommerceOrder": EcommerceOrder,
        "EcommerceOrderLine": EcommerceOrderLine,
        "OrderRoutingRule": OrderRoutingRule,
        "OrderFulfillment": OrderFulfillment,
        "ReturnMerchandiseAuthorization": ReturnMerchandiseAuthorization,
    }
    for model_name, model_cls in models_dict.items():
        expected_fields = set(ORDERMANAGEMENT_MODEL_FIELDS[model_name])
        actual_fields = {f.name for f in model_cls._meta.get_fields() if hasattr(f, "name")}
        for field in expected_fields:
            assert field in actual_fields, f"Model {model_name} missing contract field {field}"


def test_ordermanagement_model_choices_contract():
    """Verify all 9.5 choices match contract-pinned options."""
    for model_name, choice_dict in ORDERMANAGEMENT_CHOICES.items():
        model_cls = globals()[model_name]
        for field_name, expected_choices in choice_dict.items():
            field = model_cls._meta.get_field(field_name)
            actual_keys = [k for k, _ in field.choices]
            expected_keys = [k for k, _ in expected_choices]
            assert actual_keys == expected_keys, f"{model_name}.{field_name} choices mismatch"


# ==============================================================================
# EcommerceOrder & EcommerceOrderLine Tests
# ==============================================================================

def test_ordermanagement_order_creation_and_auto_number(tenant_a, ecom_customer_a, ecom_currency_usd):
    order = _ordermanagement_order(tenant_a, customer=ecom_customer_a, currency=ecom_currency_usd)
    assert order.pk is not None
    assert order.number.startswith("EORD-")
    assert order.status == "pending_validation"
    assert order.payment_status == "pending"
    assert order.fulfillment_status == "unfulfilled"
    assert order.subtotal_amount == Decimal("100.00")
    assert str(order) == f"{order.number} ({ecom_customer_a.name})"


def test_ordermanagement_order_lines_and_recalculate_totals(tenant_a, ecom_order_a, ecom_product_a, ecom_variant_a):
    line1 = _ordermanagement_line(
        tenant_a,
        ecom_order_a,
        product=ecom_product_a,
        variant=ecom_variant_a,
        quantity=2,
        unit_price=Decimal("150.00"),
        unit_discount=Decimal("10.00"),
    )
    # line_total = (2 * 150.00) - (2 * 10.00) = 280.00
    assert line1.line_total == Decimal("280.00")

    line2 = _ordermanagement_line(
        tenant_a,
        ecom_order_a,
        product=ecom_product_a,
        variant=ecom_variant_a,
        quantity=1,
        unit_price=Decimal("50.00"),
        unit_discount=Decimal("0.00"),
    )
    assert line2.line_total == Decimal("50.00")

    ecom_order_a.discount_amount = Decimal("20.00")
    ecom_order_a.shipping_amount = Decimal("15.00")
    ecom_order_a.tax_amount = Decimal("25.00")
    ecom_order_a.save()

    ecom_order_a.recalculate_totals()
    assert ecom_order_a.subtotal_amount == Decimal("330.00")
    # Total = 330.00 - 20.00 (discount) + 15.00 (shipping) + 25.00 (tax) = 350.00
    assert ecom_order_a.total_amount == Decimal("350.00")


def test_ordermanagement_order_can_cancel_and_cancel_order(tenant_a, ecom_order_a, ecom_product_a, ecom_variant_a):
    line = _ordermanagement_line(tenant_a, ecom_order_a, product=ecom_product_a, variant=ecom_variant_a, status="pending")
    assert ecom_order_a.can_cancel() is True

    cancelled = ecom_order_a.cancel_order(reason="Customer requested cancellation")
    assert cancelled is True
    assert ecom_order_a.status == "cancelled"
    assert ecom_order_a.cancellation_reason == "Customer requested cancellation"
    assert ecom_order_a.cancelled_at is not None

    line.refresh_from_db()
    assert line.status == "cancelled"

    # Cannot cancel an already cancelled order
    assert ecom_order_a.can_cancel() is False
    assert ecom_order_a.cancel_order(reason="Try again") is False


def test_ordermanagement_order_unique_number_per_tenant(tenant_a, tenant_b, ecom_customer_a, ecom_customer_b, ecom_currency_usd):
    order_a = _ordermanagement_order(tenant_a, customer=ecom_customer_a, currency=ecom_currency_usd)
    # Different tenant can share number
    order_b = EcommerceOrder.objects.create(
        tenant=tenant_b,
        number=order_a.number,
        customer=ecom_customer_b,
        currency=ecom_currency_usd,
        shipping_name="Jane Doe",
        shipping_address_line1="456 Elm St",
        shipping_city="Dallas",
        shipping_postal_code="75001",
        shipping_country="USA",
    )
    assert order_b.pk is not None

    # Same tenant duplicate number raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EcommerceOrder.objects.create(
                tenant=tenant_a,
                number=order_a.number,
                customer=ecom_customer_a,
                currency=ecom_currency_usd,
                shipping_name="John Dup",
                shipping_address_line1="123 Dup St",
                shipping_city="Austin",
                shipping_postal_code="78701",
                shipping_country="USA",
            )


# ==============================================================================
# OrderRoutingRule Tests
# ==============================================================================

def test_ordermanagement_routing_rule_creation_and_auto_number(tenant_a, ecom_center_a):
    rule = _ordermanagement_routing_rule(
        tenant_a,
        name="Express Priority Route",
        strategy="closest_location",
        priority=5,
        preferred_fulfillment_center=ecom_center_a,
    )
    assert rule.pk is not None
    assert rule.number.startswith("EORT-")
    assert rule.strategy == "closest_location"
    assert rule.priority == 5
    assert rule.preferred_fulfillment_center == ecom_center_a
    assert str(rule) == "Express Priority Route (Priority 5)"


# ==============================================================================
# OrderFulfillment Tests
# ==============================================================================

def test_ordermanagement_fulfillment_creation_and_auto_number(tenant_a, ecom_order_a, ecom_center_a):
    ful = _ordermanagement_fulfillment(tenant_a, ecom_order_a, fulfillment_center=ecom_center_a)
    assert ful.pk is not None
    assert ful.number.startswith("EFUL-")
    assert ful.status == "allocated"
    assert ful.order == ecom_order_a
    assert ful.fulfillment_center == ecom_center_a
    assert str(ful) == f"{ful.number} (FedEx Ground: 1234567890)"


def test_ordermanagement_fulfillment_mark_shipped_and_delivered(tenant_a, ecom_order_a, ecom_center_a):
    ful = _ordermanagement_fulfillment(tenant_a, ecom_order_a, fulfillment_center=ecom_center_a)
    assert ful.shipped_at is None

    ful.carrier_name = "UPS Express"
    ful.tracking_number = "1Z9999999999999999"
    ful.save()

    ful.mark_shipped()
    ful.refresh_from_db()
    assert ful.status == "shipped"
    assert ful.carrier_name == "UPS Express"
    assert ful.tracking_number == "1Z9999999999999999"
    assert ful.shipped_at is not None

    ecom_order_a.refresh_from_db()
    assert ecom_order_a.fulfillment_status == "partially_fulfilled"

    ful.mark_delivered()
    ful.refresh_from_db()
    assert ful.status == "delivered"
    assert ful.actual_delivery_date is not None


# ==============================================================================
# ReturnMerchandiseAuthorization Tests
# ==============================================================================

def test_ordermanagement_rma_creation_and_auto_number(tenant_a, ecom_order_a, ecom_customer_a, ecom_center_a):
    rma = _ordermanagement_rma(
        tenant_a,
        ecom_order_a,
        customer=ecom_customer_a,
        restocking_center=ecom_center_a,
    )
    assert rma.pk is not None
    assert rma.number.startswith("ERMA-")
    assert rma.return_type == "refund"
    assert rma.status == "requested"
    assert rma.restocking_center == ecom_center_a
    assert str(rma) == f"{rma.number} ({rma.get_return_type_display()} - {ecom_order_a.number})"


def test_ordermanagement_rma_authorize_and_complete_settlement(tenant_a, ecom_order_a, ecom_customer_a):
    rma = _ordermanagement_rma(tenant_a, ecom_order_a, customer=ecom_customer_a)
    assert rma.authorized_at is None
    assert rma.completed_at is None

    rma.authorize()
    rma.refresh_from_db()
    assert rma.status == "authorized"
    assert rma.authorized_at is not None

    rma.complete_settlement()
    rma.refresh_from_db()
    assert rma.status == "completed"
    assert rma.refund_status == "processed"
    assert rma.completed_at is not None
