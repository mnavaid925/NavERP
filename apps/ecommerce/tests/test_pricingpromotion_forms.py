"""Form validation and tenant isolation tests for eCommerce 9.3 Pricing & Promotion Engine.

Covers:
- DynamicPriceRuleForm
- CouponPromotionForm
- FlashSaleForm
- CompetitorPriceMonitorForm

Naming conventions enforced:
- Test functions: test_pricingpromotion_*
"""
from decimal import Decimal
import pytest
from django.utils import timezone

from apps.core.models.Party import Party
from apps.ecommerce.forms.PricingPromotion.DynamicPriceRules import DynamicPriceRuleForm
from apps.ecommerce.forms.PricingPromotion.CouponPromotions import CouponPromotionForm
from apps.ecommerce.forms.PricingPromotion.FlashSales import FlashSaleForm
from apps.ecommerce.forms.PricingPromotion.CompetitorPriceMonitors import CompetitorPriceMonitorForm
from apps.ecommerce.tests.conftest import (
    PRICINGPROMOTION_FORM_FIELDS,
    _productcatalog_category,
    _productcatalog_product,
    _productcatalog_variant,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Form Fields Contract Check
# ==============================================================================

def test_pricingpromotion_form_fields_contract():
    """Verify that form Meta.fields match the pre-build contract."""
    assert tuple(DynamicPriceRuleForm.Meta.fields) == PRICINGPROMOTION_FORM_FIELDS["DynamicPriceRuleForm"]
    assert tuple(CouponPromotionForm.Meta.fields) == PRICINGPROMOTION_FORM_FIELDS["CouponPromotionForm"]
    assert tuple(FlashSaleForm.Meta.fields) == PRICINGPROMOTION_FORM_FIELDS["FlashSaleForm"]
    assert tuple(CompetitorPriceMonitorForm.Meta.fields) == PRICINGPROMOTION_FORM_FIELDS["CompetitorPriceMonitorForm"]


# ==============================================================================
# DynamicPriceRuleForm Tests
# ==============================================================================

def test_pricingpromotion_dynamicpricerule_form_valid_storewide(tenant_a):
    """Test valid storewide DynamicPriceRuleForm submission."""
    now = timezone.now()
    data = {
        "name": "Sitewide Holiday 15%",
        "rule_type": "percentage_discount",
        "adjustment_value": "15.0000",
        "scope": "storewide",
        "customer_segment": "all",
        "loyalty_tier": "none",
        "min_quantity": 1,
        "currency_code": "USD",
        "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
        "priority": 10,
        "is_active": True,
    }
    form = DynamicPriceRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.name == "Sitewide Holiday 15%"


def test_pricingpromotion_dynamicpricerule_form_scope_category_requires_category(tenant_a):
    """Test that scope='category' without selecting category fails validation."""
    data = {
        "name": "Category Rule Missing Target",
        "rule_type": "percentage_discount",
        "adjustment_value": "10.0000",
        "scope": "category",
        "category": "",
    }
    form = DynamicPriceRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "category" in form.errors


def test_pricingpromotion_dynamicpricerule_form_scope_variant_autopopulates_product(tenant_a, ecom_variant_a):
    """Test that scope='variant' auto-populates product from variant."""
    now = timezone.now()
    data = {
        "name": "Variant Specific Rule",
        "rule_type": "fixed_price_override",
        "adjustment_value": "799.0000",
        "scope": "variant",
        "variant": ecom_variant_a.pk,
        "customer_segment": "all",
        "loyalty_tier": "none",
        "min_quantity": 1,
        "currency_code": "USD",
        "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
        "priority": 10,
        "is_active": True,
    }
    form = DynamicPriceRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data.get("product") == ecom_variant_a.product


def test_pricingpromotion_dynamicpricerule_form_invalid_negative_and_excess_percent(tenant_a):
    """Test negative adjustment and percentage > 100% rejection."""
    # Negative value
    form_neg = DynamicPriceRuleForm(
        data={"name": "Neg", "rule_type": "percentage_discount", "adjustment_value": "-5.00", "scope": "storewide"},
        tenant=tenant_a,
    )
    assert not form_neg.is_valid()
    assert "adjustment_value" in form_neg.errors

    # Percentage > 100
    form_over = DynamicPriceRuleForm(
        data={"name": "Over", "rule_type": "percentage_discount", "adjustment_value": "120.00", "scope": "storewide"},
        tenant=tenant_a,
    )
    assert not form_over.is_valid()
    assert "adjustment_value" in form_over.errors


def test_pricingpromotion_dynamicpricerule_form_expiration_before_activation(tenant_a):
    """Test that valid_to before valid_from triggers validation error."""
    now = timezone.now()
    data = {
        "name": "Backwards Dates",
        "rule_type": "percentage_discount",
        "adjustment_value": "10.00",
        "scope": "storewide",
        "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
        "valid_to": (now - timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
    }
    form = DynamicPriceRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "valid_to" in form.errors


def test_pricingpromotion_dynamicpricerule_form_rejects_foreign_fk(tenant_a, tenant_b, ecom_category_b):
    """Test cross-tenant FK injection rejection."""
    data = {
        "name": "Cross Tenant Category Inject",
        "rule_type": "percentage_discount",
        "adjustment_value": "10.00",
        "scope": "category",
        "category": ecom_category_b.pk,
    }
    form = DynamicPriceRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "category" in form.errors


# ==============================================================================
# CouponPromotionForm Tests
# ==============================================================================

def test_pricingpromotion_coupon_form_valid(tenant_a):
    """Test valid CouponPromotionForm submission with uppercase code normalization."""
    now = timezone.now()
    data = {
        "code": "spring25",
        "name": "Spring Sale 25% Off",
        "discount_type": "percentage",
        "discount_value": "25.0000",
        "min_spend": "50.0000",
        "max_discount_amount": "50.0000",
        "usage_limit_total": 500,
        "usage_limit_per_customer": 2,
        "is_stackable": False,
        "loyalty_tier_required": "none",
        "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
        "is_active": True,
    }
    form = CouponPromotionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.code == "SPRING25"


def test_pricingpromotion_coupon_form_negative_and_excess_validation(tenant_a):
    """Test CouponPromotionForm rejects negative values and percentage > 100%."""
    # Negative discount
    form_neg = CouponPromotionForm(
        data={"code": "BAD", "name": "Bad", "discount_type": "percentage", "discount_value": "-10.00"},
        tenant=tenant_a,
    )
    assert not form_neg.is_valid()
    assert "discount_value" in form_neg.errors

    # Percentage > 100
    form_over = CouponPromotionForm(
        data={"code": "BAD2", "name": "Bad 2", "discount_type": "percentage", "discount_value": "110.00"},
        tenant=tenant_a,
    )
    assert not form_over.is_valid()
    assert "discount_value" in form_over.errors


def test_pricingpromotion_coupon_form_rejects_foreign_customer(tenant_a, tenant_b):
    """Test CouponPromotionForm rejects a customer Party belonging to another tenant."""
    foreign_party = Party.objects.create(tenant=tenant_b, name="Foreign Customer")
    data = {
        "code": "FOR-CUST",
        "name": "Targeted Campaign",
        "discount_type": "fixed_cart",
        "discount_value": "10.00",
        "customer": foreign_party.pk,
    }
    form = CouponPromotionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "customer" in form.errors


# ==============================================================================
# FlashSaleForm Tests
# ==============================================================================

def test_pricingpromotion_flashsale_form_valid(tenant_a, ecom_variant_a):
    """Test valid FlashSaleForm creation with all timing and inventory settings."""
    now = timezone.now()
    data = {
        "title": "Midnight Audio Blast",
        "status": "scheduled",
        "product": ecom_variant_a.product.pk,
        "variant": ecom_variant_a.pk,
        "discount_percentage": "35.00",
        "inventory_cap": 50,
        "max_units_per_order": 2,
        "start_time": (now + timezone.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        "end_time": (now + timezone.timedelta(hours=8)).strftime("%Y-%m-%dT%H:%M"),
        "badge_label": "FLASH DEAL",
        "banner_bg_color": "#ef4444",
    }
    form = FlashSaleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.title == "Midnight Audio Blast"


def test_pricingpromotion_flashsale_form_end_time_before_start_time(tenant_a):
    """Test FlashSaleForm rejects end_time earlier than start_time."""
    now = timezone.now()
    data = {
        "title": "Invalid Window",
        "status": "draft",
        "discount_percentage": "20.00",
        "inventory_cap": 10,
        "start_time": (now + timezone.timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M"),
        "end_time": (now + timezone.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
    }
    form = FlashSaleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "end_time" in form.errors


def test_pricingpromotion_flashsale_form_inventory_cap_min_1_and_order_cap(tenant_a):
    """Test FlashSaleForm rejects inventory_cap < 1 (M1 review fix) and max_units > inventory_cap."""
    now = timezone.now()
    # inventory_cap = 0
    form_zero = FlashSaleForm(
        data={
            "title": "Zero Cap",
            "status": "draft",
            "inventory_cap": 0,
            "start_time": now.strftime("%Y-%m-%dT%H:%M"),
            "end_time": (now + timezone.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        },
        tenant=tenant_a,
    )
    assert not form_zero.is_valid()
    assert "inventory_cap" in form_zero.errors

    # max_units_per_order > inventory_cap
    form_cap_exceeded = FlashSaleForm(
        data={
            "title": "Scalper Paradise",
            "status": "draft",
            "inventory_cap": 5,
            "max_units_per_order": 10,
            "start_time": now.strftime("%Y-%m-%dT%H:%M"),
            "end_time": (now + timezone.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        },
        tenant=tenant_a,
    )
    assert not form_cap_exceeded.is_valid()
    assert "max_units_per_order" in form_cap_exceeded.errors


def test_pricingpromotion_flashsale_form_rejects_foreign_variant(tenant_a, tenant_b, ecom_variant_b):
    """Test FlashSaleForm rejects variant belonging to another tenant."""
    now = timezone.now()
    data = {
        "title": "Foreign Variant Sale",
        "status": "draft",
        "variant": ecom_variant_b.pk,
        "inventory_cap": 10,
        "start_time": now.strftime("%Y-%m-%dT%H:%M"),
        "end_time": (now + timezone.timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
    }
    form = FlashSaleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "variant" in form.errors


# ==============================================================================
# CompetitorPriceMonitorForm Tests
# ==============================================================================

def test_pricingpromotion_monitor_form_valid(tenant_a, ecom_variant_a):
    """Test valid CompetitorPriceMonitorForm submission and uppercase currency normalization."""
    data = {
        "competitor_name": "Amazon US",
        "variant": ecom_variant_a.pk,
        "competitor_url": "https://www.amazon.com/dp/B000TEST",
        "competitor_price": "799.9900",
        "competitor_currency": "usd",
        "is_in_stock": True,
        "match_strategy": "beat_by_fixed",
        "beat_by_value": "15.0000",
        "min_margin_pct": "12.00",
        "status": "active",
    }
    form = CompetitorPriceMonitorForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    # Currency normalized to uppercase USD (from I1 fix)
    assert instance.competitor_currency == "USD"
    # Product auto-populated from variant
    assert instance.product == ecom_variant_a.product


def test_pricingpromotion_monitor_form_negative_price_and_margin(tenant_a, ecom_variant_a):
    """Test CompetitorPriceMonitorForm rejects negative competitor price and margin pct."""
    # Negative competitor price
    form_neg_price = CompetitorPriceMonitorForm(
        data={
            "competitor_name": "Comp",
            "variant": ecom_variant_a.pk,
            "competitor_url": "https://example.com",
            "competitor_price": "-10.00",
        },
        tenant=tenant_a,
    )
    assert not form_neg_price.is_valid()
    assert "competitor_price" in form_neg_price.errors

    # Negative margin pct
    form_neg_margin = CompetitorPriceMonitorForm(
        data={
            "competitor_name": "Comp",
            "variant": ecom_variant_a.pk,
            "competitor_url": "https://example.com",
            "competitor_price": "100.00",
            "min_margin_pct": "-5.00",
        },
        tenant=tenant_a,
    )
    assert not form_neg_margin.is_valid()
    assert "min_margin_pct" in form_neg_margin.errors


def test_pricingpromotion_monitor_form_invalid_currency_code(tenant_a, ecom_variant_a):
    """Test CompetitorPriceMonitorForm rejects currency codes not 3 chars (I1 review fix)."""
    form = CompetitorPriceMonitorForm(
        data={
            "competitor_name": "Comp",
            "variant": ecom_variant_a.pk,
            "competitor_url": "https://example.com",
            "competitor_price": "100.00",
            "competitor_currency": "US",
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "competitor_currency" in form.errors


def test_pricingpromotion_monitor_form_rejects_foreign_variant(tenant_a, tenant_b, ecom_variant_b):
    """Test CompetitorPriceMonitorForm rejects variant from foreign tenant."""
    data = {
        "competitor_name": "Cross Tenant Comp",
        "variant": ecom_variant_b.pk,
        "competitor_url": "https://example.com",
        "competitor_price": "500.00",
    }
    form = CompetitorPriceMonitorForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "variant" in form.errors
