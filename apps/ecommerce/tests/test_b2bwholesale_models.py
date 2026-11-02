"""Tests for eCommerce 9.17 B2B & Wholesale Commerce Models."""
from decimal import Decimal
import pytest
from django.utils import timezone
from datetime import timedelta

from apps.ecommerce.models import (
    B2bCompanyAccount,
    B2bCompanyUser,
    B2bQuoteRequest,
    B2bQuickOrderTemplate,
)
from apps.ecommerce.tests.conftest import (
    B2BWHOLESALE_MODEL_FIELDS,
    B2BWHOLESALE_CHOICES,
    _b2bwholesale_company_account,
    _b2bwholesale_company_user,
    _b2bwholesale_quote_request,
    _b2bwholesale_quick_order_template,
)


@pytest.mark.django_db
def test_b2bwholesale_model_fields_contract():
    """Verify all 4 models contain expected fields from the contract."""
    for model_cls, model_name in [
        (B2bCompanyAccount, "B2bCompanyAccount"),
        (B2bCompanyUser, "B2bCompanyUser"),
        (B2bQuoteRequest, "B2bQuoteRequest"),
        (B2bQuickOrderTemplate, "B2bQuickOrderTemplate"),
    ]:
        field_names = {f.name for f in model_cls._meta.get_fields()}
        expected_fields = B2BWHOLESALE_MODEL_FIELDS[model_name]
        for field in expected_fields:
            assert field in field_names, f"Model {model_name} missing contract field: {field}"


@pytest.mark.django_db
def test_b2bwholesale_model_choices_contract():
    """Verify choices on models match contract constants."""
    for field, expected_choices in B2BWHOLESALE_CHOICES["B2bCompanyAccount"].items():
        assert tuple(getattr(B2bCompanyAccount, f"{field.upper()}_CHOICES")) == expected_choices

    for field, expected_choices in B2BWHOLESALE_CHOICES["B2bCompanyUser"].items():
        assert tuple(getattr(B2bCompanyUser, f"{field.upper()}_CHOICES")) == expected_choices

    assert tuple(B2bQuoteRequest.STATUS_CHOICES) == B2BWHOLESALE_CHOICES["B2bQuoteRequest"]["status"]
    assert tuple(B2bQuickOrderTemplate.SCOPE_CHOICES) == B2BWHOLESALE_CHOICES["B2bQuickOrderTemplate"]["scope"]
    assert tuple(B2bQuickOrderTemplate.CADENCE_CHOICES) == B2BWHOLESALE_CHOICES["B2bQuickOrderTemplate"]["cadence"]


@pytest.mark.django_db
def test_b2bwholesale_model_numbering_and_str(tenant_a, user_a):
    """Test TenantNumbered sequencing and str representation for all 4 models."""
    co = _b2bwholesale_company_account(tenant_a, primary_contact=user_a, company_name="Apex Global Ltd")
    assert co.number.startswith("EBCA-")
    assert "Apex Global Ltd" in str(co)

    cu = _b2bwholesale_company_user(tenant_a, co, user_a)
    assert cu.number.startswith("EBCU-")
    assert user_a.username in str(cu)

    qr = _b2bwholesale_quote_request(tenant_a, co, requested_by=user_a)
    assert qr.number.startswith("EBQR-")
    assert qr.number in str(qr)

    tmpl = _b2bwholesale_quick_order_template(tenant_a, co, created_by=user_a, name="Daily Stock Kit")
    assert tmpl.number.startswith("EBQT-")
    assert "Daily Stock Kit" in str(tmpl)


@pytest.mark.django_db
def test_b2bwholesale_company_account_credit_methods(tenant_a, user_a):
    """Test credit availability and wholesale discount calculations."""
    co = _b2bwholesale_company_account(
        tenant_a,
        primary_contact=user_a,
        credit_limit=Decimal("10000.00"),
        available_credit=Decimal("10000.00"),
        wholesale_discount_percent=Decimal("15.00"),
        status="active",
        credit_status="good_standing",
    )
    assert co.has_available_credit(Decimal("5000.00")) is True
    assert co.has_available_credit(Decimal("10000.00")) is True
    assert co.has_available_credit(Decimal("10000.01")) is False

    # Discount calculation
    base_price = Decimal("200.00")
    discounted = co.calculate_discounted_price(base_price)
    assert discounted == Decimal("170.00")


@pytest.mark.django_db
def test_b2bwholesale_company_account_credit_init_on_increase(tenant_a):
    """Test available credit is initialized when limit is raised from 0 (I15)."""
    co = _b2bwholesale_company_account(
        tenant_a,
        company_name="Zero Credit Starter Corp",
        credit_limit=Decimal("0.00"),
        available_credit=Decimal("0.00"),
    )
    assert co.available_credit == Decimal("0.00")

    co.credit_limit = Decimal("25000.00")
    co.save()
    co.refresh_from_db()
    assert co.available_credit == Decimal("25000.00")


@pytest.mark.django_db
def test_b2bwholesale_company_user_can_spend(tenant_a, ecom_b2b_company_a, user_a):
    """Test buyer spending limits against order and monthly budgets."""
    cu = _b2bwholesale_company_user(
        tenant_a,
        ecom_b2b_company_a,
        user_a,
        role="staff_buyer",
        order_spend_limit=Decimal("2000.00"),
        monthly_spend_limit=Decimal("10000.00"),
        monthly_spend_current=Decimal("8500.00"),
    )
    # Order within single limit and within remaining monthly limit
    assert cu.can_spend(Decimal("1000.00")) is True

    # Exceeds per-order limit (2500 > 2000)
    assert cu.can_spend(Decimal("2500.00")) is False

    # Within order limit (1800 < 2000) but exceeds monthly (8500 + 1800 > 10000)
    assert cu.can_spend(Decimal("1800.00")) is False


@pytest.mark.django_db
def test_b2bwholesale_quote_request_recalculate_totals(tenant_a, ecom_b2b_company_a, user_a):
    """Test quote calculation from line items data."""
    qr = _b2bwholesale_quote_request(
        tenant_a,
        ecom_b2b_company_a,
        requested_by=user_a,
        line_items_data=[
            {
                "sku": "SKU-A",
                "name": "Part A",
                "requested_qty": 10,
                "requested_unit_price": 100.0,
                "quoted_unit_price": 90.0,
                "line_total": 900.0,
            },
            {
                "sku": "SKU-B",
                "name": "Part B",
                "requested_qty": 5,
                "requested_unit_price": 200.0,
                "quoted_unit_price": 180.0,
                "line_total": 900.0,
            },
        ],
        shipping_estimate=Decimal("100.00"),
        quoted_discount_percent=Decimal("10.00"),
    )
    qr.recalculate_totals()
    qr.save()
    qr.refresh_from_db()

    # Subtotal is 1800.00, 10% discount = 1620.00 + 100 shipping = 1720.00
    assert qr.original_subtotal == Decimal("1800.00")
    assert qr.quoted_total == Decimal("1720.00")


@pytest.mark.django_db
def test_b2bwholesale_quote_request_preserves_adhoc_subtotal(tenant_a, ecom_b2b_company_a, user_a):
    """Test that ad-hoc quotes without structured line items preserve subtotal (M4)."""
    qr = _b2bwholesale_quote_request(
        tenant_a,
        ecom_b2b_company_a,
        requested_by=user_a,
        line_items_data=[],
        original_subtotal=Decimal("7500.00"),
        shipping_estimate=Decimal("200.00"),
        quoted_discount_percent=Decimal("5.00"),
    )
    qr.recalculate_totals()
    qr.save()
    qr.refresh_from_db()

    assert qr.original_subtotal == Decimal("7500.00")
    assert qr.quoted_total == Decimal("7325.00")  # (7500 * 0.95) + 200


@pytest.mark.django_db
def test_b2bwholesale_quick_order_template_items_count(tenant_a, ecom_b2b_company_a, user_a):
    """Test that total_items_count updates automatically on template save."""
    tmpl = _b2bwholesale_quick_order_template(
        tenant_a,
        ecom_b2b_company_a,
        created_by=user_a,
        items_data=[
            {"sku": "SKU-1", "name": "Item 1", "default_quantity": 5},
            {"sku": "SKU-2", "name": "Item 2", "default_quantity": 10},
            {"sku": "SKU-3", "name": "Item 3", "default_quantity": 20},
        ],
    )
    assert tmpl.total_items_count == 3
