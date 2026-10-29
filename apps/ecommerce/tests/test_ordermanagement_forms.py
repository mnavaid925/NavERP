"""Comprehensive form validation and tenant isolation tests for eCommerce 9.5 OMS.

Covers:
- EcommerceOrderForm & EcommerceOrderLineForm
- OrderRoutingRuleForm
- OrderFulfillmentForm
- ReturnMerchandiseAuthorizationForm

Naming conventions enforced:
- Test functions: test_ordermanagement_*
"""
from decimal import Decimal
import pytest

from apps.core.models import Party
from apps.ecommerce.forms.OrderManagement.EcommerceOrders import (
    EcommerceOrderForm,
    EcommerceOrderLineForm,
)
from apps.ecommerce.forms.OrderManagement.OrderRoutingRules import OrderRoutingRuleForm
from apps.ecommerce.forms.OrderManagement.OrderFulfillments import OrderFulfillmentForm
from apps.ecommerce.forms.OrderManagement.ReturnMerchandiseAuthorizations import (
    ReturnMerchandiseAuthorizationForm,
)
from apps.ecommerce.models import (
    EcommerceOrder,
    EcommerceOrderLine,
    OrderRoutingRule,
    OrderFulfillment,
    ReturnMerchandiseAuthorization,
)
from apps.ecommerce.tests.conftest import (
    ORDERMANAGEMENT_FORM_FIELDS,
    _ordermanagement_customer,
    _ordermanagement_currency,
    _ordermanagement_order,
    _ordermanagement_routing_rule,
    _ordermanagement_fulfillment,
    _ordermanagement_rma,
    _inventorystock_center,
    _pricingpromotion_coupon,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Form Contract Fields Test
# ==============================================================================

def test_ordermanagement_form_fields_contract():
    """Verify all 9.5 forms contain exact contract-pinned fields."""
    forms_dict = {
        "EcommerceOrderForm": EcommerceOrderForm,
        "EcommerceOrderLineForm": EcommerceOrderLineForm,
        "OrderRoutingRuleForm": OrderRoutingRuleForm,
        "OrderFulfillmentForm": OrderFulfillmentForm,
        "ReturnMerchandiseAuthorizationForm": ReturnMerchandiseAuthorizationForm,
    }
    for form_name, form_cls in forms_dict.items():
        expected_fields = set(ORDERMANAGEMENT_FORM_FIELDS[form_name])
        actual_fields = set(form_cls.base_fields.keys())
        assert expected_fields == actual_fields, f"Form {form_name} fields mismatch: diff={expected_fields ^ actual_fields}"


# ==============================================================================
# EcommerceOrderForm & EcommerceOrderLineForm Tests
# ==============================================================================

def test_ordermanagement_order_form_valid(tenant_a, ecom_customer_a, ecom_currency_usd):
    data = {
        "customer": ecom_customer_a.pk,
        "guest_email": "customer@example.com",
        "currency": ecom_currency_usd.pk,
        "status": "pending_validation",
        "payment_status": "pending",
        "fulfillment_status": "unfulfilled",
        "fraud_risk_level": "low",
        "fraud_score": 10,
        "address_verification_status": "passed",
        "inventory_reservation_status": "reserved",
        "discount_amount": "0.00",
        "shipping_amount": "15.00",
        "tax_amount": "8.50",
        "shipping_name": "John Doe",
        "shipping_address_line1": "100 Broadway",
        "shipping_city": "New York",
        "shipping_state": "NY",
        "shipping_postal_code": "10001",
        "shipping_country": "USA",
        "customer_notes": "Please leave at porch",
    }
    form = EcommerceOrderForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    order = form.save(commit=False)
    order.tenant = tenant_a
    order.save()
    assert order.pk is not None
    assert order.number.startswith("EORD-")


def test_ordermanagement_order_form_rejects_foreign_customer(tenant_a, tenant_b, ecom_customer_b, ecom_currency_usd):
    data = {
        "customer": ecom_customer_b.pk,  # from tenant_b
        "currency": ecom_currency_usd.pk,
        "shipping_name": "Foreign Customer",
        "shipping_address_line1": "123 Somewhere",
        "shipping_city": "Dallas",
        "shipping_postal_code": "75001",
        "shipping_country": "USA",
    }
    form = EcommerceOrderForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer" in form.errors or "Invalid choice" in str(form.errors)


def test_ordermanagement_order_form_rejects_foreign_coupon(tenant_a, tenant_b, ecom_customer_a, ecom_currency_usd):
    foreign_coupon = _pricingpromotion_coupon(tenant_b, code="FOREIGN20")
    data = {
        "customer": ecom_customer_a.pk,
        "currency": ecom_currency_usd.pk,
        "applied_coupon": foreign_coupon.pk,
        "shipping_name": "John Doe",
        "shipping_address_line1": "100 Broadway",
        "shipping_city": "New York",
        "shipping_postal_code": "10001",
        "shipping_country": "USA",
    }
    form = EcommerceOrderForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "applied_coupon" in form.errors or "Invalid choice" in str(form.errors)


def test_ordermanagement_order_line_form_valid(tenant_a, ecom_order_a, ecom_product_a, ecom_variant_a):
    data = {
        "product": ecom_product_a.pk,
        "variant": ecom_variant_a.pk,
        "sku": ecom_variant_a.sku,
        "product_name": ecom_product_a.name,
        "quantity": 2,
        "unit_price": "299.99",
        "unit_discount": "20.00",
        "status": "pending",
    }
    form = EcommerceOrderLineForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    line = form.save(commit=False)
    line.tenant = tenant_a
    line.order = ecom_order_a
    line.save()
    assert line.pk is not None
    # line_total = (2 * 299.99) - (2 * 20.00) = 559.98
    assert line.line_total == Decimal("559.98")


def test_ordermanagement_order_line_form_rejects_foreign_product(tenant_a, tenant_b, ecom_order_a, ecom_product_b):
    data = {
        "product": ecom_product_b.pk,  # from tenant_b
        "sku": "FOREIGN-SKU",
        "product_name": "Foreign Server",
        "quantity": 1,
        "unit_price": "100.00",
        "status": "pending",
    }
    form = EcommerceOrderLineForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "product" in form.errors or "Invalid choice" in str(form.errors)


# ==============================================================================
# OrderRoutingRuleForm Tests
# ==============================================================================

def test_ordermanagement_routing_rule_form_valid(tenant_a, ecom_center_a):
    data = {
        "name": "Regional West Routing",
        "strategy": "fewest_splits",
        "priority": 2,
        "destination_country": "USA",
        "destination_region": "West Coast",
        "preferred_fulfillment_center": ecom_center_a.pk,
        "allow_split_shipment": True,
        "enable_dropship": False,
        "is_active": True,
        "description": "Prefers closest hub with fewest splits",
    }
    form = OrderRoutingRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    rule = form.save(commit=False)
    rule.tenant = tenant_a
    rule.save()
    assert rule.pk is not None
    assert rule.strategy == "fewest_splits"


def test_ordermanagement_routing_rule_form_rejects_foreign_center(tenant_a, tenant_b, ecom_center_b):
    data = {
        "name": "Invalid Route",
        "strategy": "closest_location",
        "preferred_fulfillment_center": ecom_center_b.pk,  # from tenant_b
    }
    form = OrderRoutingRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "preferred_fulfillment_center" in form.errors or "Invalid choice" in str(form.errors)


# ==============================================================================
# OrderFulfillmentForm Tests
# ==============================================================================

def test_ordermanagement_fulfillment_form_valid(tenant_a, ecom_order_a, ecom_center_a):
    data = {
        "order": ecom_order_a.pk,
        "fulfillment_center": ecom_center_a.pk,
        "carrier_name": "DHL Express",
        "tracking_number": "DHL-9876543210",
        "tracking_url": "https://dhl.com/track/9876543210",
        "status": "allocated",
        "shipping_cost": "22.50",
        "notification_sent": False,
    }
    form = OrderFulfillmentForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    ful = form.save(commit=False)
    ful.tenant = tenant_a
    ful.save()
    assert ful.pk is not None
    assert ful.carrier_name == "DHL Express"


def test_ordermanagement_fulfillment_form_rejects_foreign_order(tenant_a, tenant_b, ecom_order_b, ecom_center_a):
    data = {
        "order": ecom_order_b.pk,  # from tenant_b
        "fulfillment_center": ecom_center_a.pk,
        "carrier_name": "FedEx",
    }
    form = OrderFulfillmentForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "order" in form.errors or "Invalid choice" in str(form.errors)


# ==============================================================================
# ReturnMerchandiseAuthorizationForm Tests
# ==============================================================================

def test_ordermanagement_rma_form_valid(tenant_a, ecom_order_a, ecom_customer_a, ecom_center_a):
    data = {
        "order": ecom_order_a.pk,
        "customer": ecom_customer_a.pk,
        "return_type": "refund",
        "status": "requested",
        "reason": "damaged_defective",
        "restocking_fee": "10.00",
        "refund_amount": "90.00",
        "refund_status": "pending",
        "restocking_status": "pending",
        "restocking_center": ecom_center_a.pk,
        "customer_notes": "Item arrived with broken seal.",
    }
    form = ReturnMerchandiseAuthorizationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    rma = form.save(commit=False)
    rma.tenant = tenant_a
    rma.save()
    assert rma.pk is not None
    assert rma.reason == "damaged_defective"


def test_ordermanagement_rma_form_rejects_restocking_fee_exceeding_refund(tenant_a, ecom_order_a, ecom_customer_a):
    """Verify Finding I2: restocking fee cannot exceed refund amount."""
    data = {
        "order": ecom_order_a.pk,
        "customer": ecom_customer_a.pk,
        "return_type": "refund",
        "status": "requested",
        "reason": "changed_mind",
        "restocking_fee": "100.00",
        "refund_amount": "50.00",  # fee > refund
        "refund_status": "pending",
        "restocking_status": "pending",
    }
    form = ReturnMerchandiseAuthorizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "restocking_fee" in form.errors
    assert "Restocking fee cannot exceed the total refund amount" in form.errors["restocking_fee"][0]


def test_ordermanagement_rma_form_rejects_foreign_customer(tenant_a, tenant_b, ecom_order_a, ecom_customer_b):
    data = {
        "order": ecom_order_a.pk,
        "customer": ecom_customer_b.pk,  # from tenant_b
        "return_type": "refund",
        "status": "requested",
        "reason": "wrong_item_sent",
    }
    form = ReturnMerchandiseAuthorizationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer" in form.errors or "Invalid choice" in str(form.errors)
