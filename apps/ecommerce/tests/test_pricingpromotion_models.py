"""Unit and invariant tests for eCommerce 9.3 Pricing & Promotion Engine models.

Covers:
- DynamicPriceRule
- CouponPromotion
- FlashSale
- CompetitorPriceMonitor

Naming conventions enforced:
- Test functions: test_pricingpromotion_*
- Module-level helpers: _pricingpromotion_*
"""
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ecommerce.models import (
    DynamicPriceRule,
    CouponPromotion,
    FlashSale,
    CompetitorPriceMonitor,
)
from apps.ecommerce.tests.conftest import (
    _pricingpromotion_rule,
    _pricingpromotion_coupon,
    _pricingpromotion_flash_sale,
    _pricingpromotion_monitor,
    PRICINGPROMOTION_MODEL_FIELDS,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_pricingpromotion_*)
# ==============================================================================

def _pricingpromotion_force_number(model_cls, tenant, number, **kwargs):
    """Instantiate and save an object with an explicitly forced number."""
    instance = model_cls(tenant=tenant, **kwargs)
    instance.number = number
    instance.save()
    return instance


# ==============================================================================
# DynamicPriceRule Model Tests
# ==============================================================================

def test_pricingpromotion_rule_model_fields_contract(tenant_a):
    """Verify DynamicPriceRule has all fields pinned in the pre-build contract."""
    rule = _pricingpromotion_rule(tenant_a, name="Contract Check")
    expected_fields = PRICINGPROMOTION_MODEL_FIELDS["DynamicPriceRule"]
    for field_name in expected_fields:
        assert hasattr(rule, field_name), f"DynamicPriceRule missing field {field_name}"


def test_pricingpromotion_rule_defaults_and_fields(tenant_a):
    """Test DynamicPriceRule defaults, choices, and relations."""
    rule = DynamicPriceRule.objects.create(
        tenant=tenant_a,
        name="Summer Clearance",
        adjustment_value=Decimal("15.0000"),
    )
    assert rule.rule_type == "percentage_discount"
    assert rule.scope == "storewide"
    assert rule.customer_segment == "all"
    assert rule.loyalty_tier == "none"
    assert rule.min_quantity == 1
    assert rule.currency_code == "USD"
    assert rule.priority == 10
    assert rule.is_active is True
    assert rule.category is None
    assert rule.product is None
    assert rule.variant is None
    assert rule.created_at is not None
    assert rule.updated_at is not None


def test_pricingpromotion_rule_str_representation(tenant_a):
    """Test DynamicPriceRule __str__ includes number and name."""
    rule = _pricingpromotion_rule(tenant_a, name="VIP 20% Discount")
    assert str(rule) == f"{rule.number} — VIP 20% Discount"


def test_pricingpromotion_rule_autonumber_generation(tenant_a, tenant_b):
    """Test DynamicPriceRule generates EDPR- prefix and distinct sequences per tenant."""
    r1 = _pricingpromotion_rule(tenant_a, name="Rule A1")
    r2 = _pricingpromotion_rule(tenant_a, name="Rule A2")
    r_b = _pricingpromotion_rule(tenant_b, name="Rule B1")

    assert r1.number.startswith("EDPR-")
    assert r2.number.startswith("EDPR-")
    assert r_b.number.startswith("EDPR-")

    seq1 = int(r1.number.split("-")[-1])
    seq2 = int(r2.number.split("-")[-1])
    assert seq2 == seq1 + 1


def test_pricingpromotion_rule_unique_constraint(tenant_a):
    """Test DynamicPriceRule unique constraint on (tenant, number)."""
    r1 = _pricingpromotion_rule(tenant_a, name="Rule 1")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _pricingpromotion_force_number(
                DynamicPriceRule,
                tenant=tenant_a,
                number=r1.number,
                name="Duplicate Number Rule",
            )


def test_pricingpromotion_rule_is_currently_valid_property(tenant_a):
    """Test DynamicPriceRule validity based on active flag and valid_from/to time window."""
    now = timezone.now()

    # Active and valid
    rule_valid = _pricingpromotion_rule(
        tenant_a,
        is_active=True,
        valid_from=now - timezone.timedelta(days=1),
        valid_to=now + timezone.timedelta(days=1),
    )
    assert rule_valid.is_currently_valid is True

    # Inactive
    rule_inactive = _pricingpromotion_rule(tenant_a, is_active=False)
    assert rule_inactive.is_currently_valid is False

    # Not yet active (future)
    rule_future = _pricingpromotion_rule(
        tenant_a,
        valid_from=now + timezone.timedelta(days=2),
    )
    assert rule_future.is_currently_valid is False

    # Expired
    rule_expired = _pricingpromotion_rule(
        tenant_a,
        valid_from=now - timezone.timedelta(days=5),
        valid_to=now - timezone.timedelta(days=1),
    )
    assert rule_expired.is_currently_valid is False


def test_pricingpromotion_rule_calculate_price_percentage(tenant_a):
    """Test calculate_price with percentage_discount."""
    rule = _pricingpromotion_rule(
        tenant_a,
        rule_type="percentage_discount",
        adjustment_value=Decimal("20.0000"),
    )
    # 20% off 100 is 80
    new_price = rule.calculate_price(Decimal("100.0000"))
    assert new_price == Decimal("80.0000")


def test_pricingpromotion_rule_calculate_price_fixed_discount(tenant_a):
    """Test calculate_price with fixed_discount and zero floor."""
    rule = _pricingpromotion_rule(
        tenant_a,
        rule_type="fixed_discount",
        adjustment_value=Decimal("25.0000"),
    )
    # 25 off 100 is 75
    assert rule.calculate_price(Decimal("100.0000")) == Decimal("75.0000")

    # 25 off 20 caps at 0 (non-negative)
    assert rule.calculate_price(Decimal("20.0000")) == Decimal("0.0000")


def test_pricingpromotion_rule_calculate_price_fixed_override(tenant_a):
    """Test calculate_price with fixed_price_override."""
    rule = _pricingpromotion_rule(
        tenant_a,
        rule_type="fixed_price_override",
        adjustment_value=Decimal("49.9900"),
    )
    assert rule.calculate_price(Decimal("120.0000")) == Decimal("49.9900")


def test_pricingpromotion_rule_calculate_price_inactive(tenant_a):
    """Test calculate_price returns original price when rule is invalid."""
    rule = _pricingpromotion_rule(
        tenant_a,
        is_active=False,
        rule_type="percentage_discount",
        adjustment_value=Decimal("50.0000"),
    )
    assert rule.calculate_price(Decimal("100.0000")) == Decimal("100.0000")


# ==============================================================================
# CouponPromotion Model Tests
# ==============================================================================

def test_pricingpromotion_coupon_model_fields_contract(tenant_a):
    """Verify CouponPromotion has all fields pinned in the pre-build contract."""
    coupon = _pricingpromotion_coupon(tenant_a, code="TESTCODE")
    expected_fields = PRICINGPROMOTION_MODEL_FIELDS["CouponPromotion"]
    for field_name in expected_fields:
        assert hasattr(coupon, field_name), f"CouponPromotion missing field {field_name}"


def test_pricingpromotion_coupon_defaults_and_fields(tenant_a):
    """Test CouponPromotion defaults, choices, and relations."""
    coupon = CouponPromotion.objects.create(
        tenant=tenant_a,
        code="SAVE10",
        name="Save 10 Percent",
        discount_value=Decimal("10.0000"),
    )
    assert coupon.discount_type == "percentage"
    assert coupon.min_spend == Decimal("0.0000")
    assert coupon.max_discount_amount is None
    assert coupon.usage_limit_total is None
    assert coupon.usage_limit_per_customer == 1
    assert coupon.used_count == 0
    assert coupon.is_stackable is False
    assert coupon.loyalty_tier_required == "none"
    assert coupon.customer is None
    assert coupon.is_active is True
    assert coupon.created_at is not None
    assert coupon.updated_at is not None


def test_pricingpromotion_coupon_code_uppercase_normalization(tenant_a):
    """Test CouponPromotion code is automatically converted to uppercase and stripped on save."""
    coupon = CouponPromotion.objects.create(
        tenant=tenant_a,
        code="  lower-code-123  ",
        name="Lowercase Test",
    )
    assert coupon.code == "LOWER-CODE-123"


def test_pricingpromotion_coupon_str_representation(tenant_a):
    """Test CouponPromotion __str__ includes code and name."""
    coupon = _pricingpromotion_coupon(tenant_a, code="WELCOME", name="Welcome Voucher")
    assert str(coupon) == "WELCOME — Welcome Voucher"


def test_pricingpromotion_coupon_autonumber_generation(tenant_a, tenant_b):
    """Test CouponPromotion generates ECPN- prefix and tenant sequence."""
    c1 = _pricingpromotion_coupon(tenant_a, code="C1")
    c2 = _pricingpromotion_coupon(tenant_a, code="C2")
    c_b = _pricingpromotion_coupon(tenant_b, code="CB")

    assert c1.number.startswith("ECPN-")
    assert c2.number.startswith("ECPN-")
    assert c_b.number.startswith("ECPN-")

    seq1 = int(c1.number.split("-")[-1])
    seq2 = int(c2.number.split("-")[-1])
    assert seq2 == seq1 + 1


def test_pricingpromotion_coupon_unique_code_per_tenant(tenant_a, tenant_b):
    """Test coupon code uniqueness within the same tenant, allowed across tenants."""
    _pricingpromotion_coupon(tenant_a, code="BLACKFRIDAY")

    # Duplicate code in same tenant raises IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _pricingpromotion_coupon(tenant_a, code="blackfriday")

    # Same code in tenant_b is allowed
    coupon_b = _pricingpromotion_coupon(tenant_b, code="BLACKFRIDAY")
    assert coupon_b.id is not None


def test_pricingpromotion_coupon_is_currently_valid_property(tenant_a):
    """Test CouponPromotion validity property based on time, active flag, and usage limit."""
    now = timezone.now()

    # Valid
    c = _pricingpromotion_coupon(tenant_a, code="V1", is_active=True, usage_limit_total=10, used_count=5)
    assert c.is_currently_valid is True
    assert c.remaining_redemptions == 5

    # Exhausted usage limit
    c_exhausted = _pricingpromotion_coupon(tenant_a, code="V2", usage_limit_total=10, used_count=10)
    assert c_exhausted.is_currently_valid is False
    assert c_exhausted.remaining_redemptions == 0

    # Inactive
    c_inactive = _pricingpromotion_coupon(tenant_a, code="V3", is_active=False)
    assert c_inactive.is_currently_valid is False


def test_pricingpromotion_coupon_calculate_discount_percentage_and_cap(tenant_a):
    """Test calculate_discount with percentage and optional max_discount_amount cap."""
    # 20% discount with max cap of $25
    coupon = _pricingpromotion_coupon(
        tenant_a,
        code="PCT20",
        discount_type="percentage",
        discount_value=Decimal("20.0000"),
        min_spend=Decimal("50.0000"),
        max_discount_amount=Decimal("25.0000"),
    )

    # Below min spend -> 0 discount
    assert coupon.calculate_discount(Decimal("40.0000")) == Decimal("0.0000")

    # Subtotal 100 -> 20% is 20 (under 25 cap)
    assert coupon.calculate_discount(Decimal("100.0000")) == Decimal("20.0000")

    # Subtotal 200 -> 20% is 40, capped at 25
    assert coupon.calculate_discount(Decimal("200.0000")) == Decimal("25.0000")


def test_pricingpromotion_coupon_calculate_discount_fixed_cart(tenant_a):
    """Test calculate_discount with fixed_cart amount bounded by cart subtotal."""
    coupon = _pricingpromotion_coupon(
        tenant_a,
        code="FIXED15",
        discount_type="fixed_cart",
        discount_value=Decimal("15.0000"),
        min_spend=Decimal("20.0000"),
    )
    assert coupon.calculate_discount(Decimal("50.0000")) == Decimal("15.0000")
    # Subtotal below min spend
    assert coupon.calculate_discount(Decimal("10.0000")) == Decimal("0.0000")


# ==============================================================================
# FlashSale Model Tests
# ==============================================================================

def test_pricingpromotion_flash_sale_model_fields_contract(tenant_a, ecom_variant_a):
    """Verify FlashSale has all fields pinned in the pre-build contract."""
    sale = _pricingpromotion_flash_sale(tenant_a, variant=ecom_variant_a)
    expected_fields = PRICINGPROMOTION_MODEL_FIELDS["FlashSale"]
    for field_name in expected_fields:
        assert hasattr(sale, field_name), f"FlashSale missing field {field_name}"


def test_pricingpromotion_flash_sale_defaults_and_fields(tenant_a):
    """Test FlashSale default values, choices, and relations."""
    now = timezone.now()
    sale = FlashSale.objects.create(
        tenant=tenant_a,
        title="Spring Clearance Sale",
        start_time=now,
        end_time=now + timezone.timedelta(hours=6),
    )
    assert sale.status == "draft"
    assert sale.discount_percentage == Decimal("20.00")
    assert sale.flash_price is None
    assert sale.inventory_cap == 100
    assert sale.units_sold == 0
    assert sale.max_units_per_order == 2
    assert sale.badge_label == "FLASH DEAL"
    assert sale.banner_bg_color == "#ef4444"
    assert sale.created_at is not None
    assert sale.updated_at is not None


def test_pricingpromotion_flash_sale_str_representation(tenant_a, ecom_variant_a):
    """Test FlashSale __str__ includes number and title."""
    sale = _pricingpromotion_flash_sale(tenant_a, title="Cyber Monday Blitz", variant=ecom_variant_a)
    assert str(sale) == f"{sale.number} — Cyber Monday Blitz"


def test_pricingpromotion_flash_sale_autonumber_generation(tenant_a, tenant_b, ecom_variant_a, ecom_variant_b):
    """Test FlashSale generates EFLS- prefix and sequential numbering."""
    s1 = _pricingpromotion_flash_sale(tenant_a, title="Sale A1", variant=ecom_variant_a)
    s2 = _pricingpromotion_flash_sale(tenant_a, title="Sale A2", variant=ecom_variant_a)
    s_b = _pricingpromotion_flash_sale(tenant_b, title="Sale B1", variant=ecom_variant_b)

    assert s1.number.startswith("EFLS-")
    assert s2.number.startswith("EFLS-")
    assert s_b.number.startswith("EFLS-")

    seq1 = int(s1.number.split("-")[-1])
    seq2 = int(s2.number.split("-")[-1])
    assert seq2 == seq1 + 1


def test_pricingpromotion_flash_sale_is_live_property(tenant_a, ecom_variant_a):
    """Test FlashSale is_live property based on status, time window, and inventory cap."""
    now = timezone.now()

    # Active and inside window
    sale_live = _pricingpromotion_flash_sale(
        tenant_a,
        variant=ecom_variant_a,
        status="active",
        inventory_cap=10,
        units_sold=2,
        start_time=now - timezone.timedelta(hours=1),
        end_time=now + timezone.timedelta(hours=1),
    )
    assert sale_live.is_live is True
    assert sale_live.remaining_units == 8
    assert sale_live.sold_percentage == 20

    # Draft status not live
    sale_draft = _pricingpromotion_flash_sale(
        tenant_a,
        variant=ecom_variant_a,
        status="draft",
        start_time=now - timezone.timedelta(hours=1),
        end_time=now + timezone.timedelta(hours=1),
    )
    assert sale_draft.is_live is False

    # Sold out not live
    sale_sold_out = _pricingpromotion_flash_sale(
        tenant_a,
        variant=ecom_variant_a,
        status="active",
        inventory_cap=10,
        units_sold=10,
        start_time=now - timezone.timedelta(hours=1),
        end_time=now + timezone.timedelta(hours=1),
    )
    assert sale_sold_out.is_live is False
    assert sale_sold_out.remaining_units == 0
    assert sale_sold_out.sold_percentage == 100


def test_pricingpromotion_flash_sale_calculate_effective_price(tenant_a, ecom_variant_a):
    """Test calculate_effective_price with percentage discount and price override."""
    # Percentage calculation
    sale_pct = _pricingpromotion_flash_sale(
        tenant_a,
        variant=ecom_variant_a,
        discount_percentage=Decimal("30.00"),
        flash_price=None,
    )
    # 30% off 200 is 140
    assert sale_pct.calculate_effective_price(Decimal("200.0000")) == Decimal("140.0000")

    # Flash price override takes precedence
    sale_override = _pricingpromotion_flash_sale(
        tenant_a,
        variant=ecom_variant_a,
        discount_percentage=Decimal("30.00"),
        flash_price=Decimal("99.9900"),
    )
    assert sale_override.calculate_effective_price(Decimal("200.0000")) == Decimal("99.9900")


# ==============================================================================
# CompetitorPriceMonitor Model Tests
# ==============================================================================

def test_pricingpromotion_monitor_model_fields_contract(tenant_a, ecom_variant_a):
    """Verify CompetitorPriceMonitor has all fields pinned in the pre-build contract."""
    monitor = _pricingpromotion_monitor(tenant_a, variant=ecom_variant_a)
    expected_fields = PRICINGPROMOTION_MODEL_FIELDS["CompetitorPriceMonitor"]
    for field_name in expected_fields:
        assert hasattr(monitor, field_name), f"CompetitorPriceMonitor missing field {field_name}"


def test_pricingpromotion_monitor_defaults_and_fields(tenant_a, ecom_variant_a):
    """Test CompetitorPriceMonitor defaults, choices, and relations."""
    monitor = CompetitorPriceMonitor.objects.create(
        tenant=tenant_a,
        competitor_name="RetailKing",
        variant=ecom_variant_a,
        competitor_url="https://retailking.com/item/1",
        competitor_price=Decimal("950.0000"),
    )
    assert monitor.competitor_currency == "USD"
    assert monitor.is_in_stock is True
    assert monitor.last_scraped_at is None
    assert monitor.match_strategy == "manual"
    assert monitor.beat_by_value == Decimal("0.0000")
    assert monitor.min_margin_pct == Decimal("10.00")
    assert monitor.floor_price is None
    assert monitor.status == "active"
    assert monitor.created_at is not None
    assert monitor.updated_at is not None


def test_pricingpromotion_monitor_str_representation(tenant_a, ecom_variant_a):
    """Test CompetitorPriceMonitor __str__ includes competitor name, SKU, and price."""
    monitor = _pricingpromotion_monitor(
        tenant_a,
        variant=ecom_variant_a,
        competitor_name="Amazon US",
        competitor_price=Decimal("849.9900"),
    )
    assert str(monitor) == f"Amazon US · {ecom_variant_a.sku} ($849.9900)"


def test_pricingpromotion_monitor_autonumber_generation(tenant_a, tenant_b, ecom_variant_a, ecom_variant_b):
    """Test CompetitorPriceMonitor generates ECPM- prefix and tenant sequence."""
    m1 = _pricingpromotion_monitor(tenant_a, variant=ecom_variant_a)
    m2 = _pricingpromotion_monitor(tenant_a, variant=ecom_variant_a, competitor_name="Comp2")
    m_b = _pricingpromotion_monitor(tenant_b, variant=ecom_variant_b)

    assert m1.number.startswith("ECPM-")
    assert m2.number.startswith("ECPM-")
    assert m_b.number.startswith("ECPM-")

    seq1 = int(m1.number.split("-")[-1])
    seq2 = int(m2.number.split("-")[-1])
    assert seq2 == seq1 + 1


def test_pricingpromotion_monitor_margin_floor_and_suggested_price(tenant_a, ecom_variant_a):
    """
    Test margin_floor_price and suggested_price repricing logic.
    ecom_variant_a has cost_price = 600.00.
    With min_margin_pct = 10.00, cost floor = 600 * 1.10 = 660.00.
    """
    monitor = _pricingpromotion_monitor(
        tenant_a,
        variant=ecom_variant_a,
        competitor_price=Decimal("800.0000"),
        match_strategy="beat_by_fixed",
        beat_by_value=Decimal("50.0000"),
        min_margin_pct=Decimal("10.00"),
    )

    # Expected floor: 600 * 1.10 = 660.00
    assert monitor.margin_floor_price == Decimal("660.0000")

    # Suggested price: 800 - 50 = 750 (well above 660 floor)
    assert monitor.suggested_price == Decimal("750.0000")
    assert monitor.is_margin_risk is False

    # Now competitor drops to 650 (below 660 floor)
    monitor.competitor_price = Decimal("650.0000")
    assert monitor.is_margin_risk is True
    # Suggested price will be clamped to floor (660.00)
    assert monitor.suggested_price == Decimal("660.0000")


def test_pricingpromotion_monitor_suggested_price_beat_by_percent(tenant_a, ecom_variant_a):
    """Test suggested_price with beat_by_percent strategy."""
    # Competitor 1000, beat by 5% = 950
    monitor = _pricingpromotion_monitor(
        tenant_a,
        variant=ecom_variant_a,
        competitor_price=Decimal("1000.0000"),
        match_strategy="beat_by_percent",
        beat_by_value=Decimal("5.0000"),
        min_margin_pct=Decimal("10.00"),
    )
    assert monitor.suggested_price == Decimal("950.0000")


def test_pricingpromotion_monitor_out_of_stock_or_manual_strategy(tenant_a, ecom_variant_a):
    """Test suggested_price returns None when manual review or competitor out of stock."""
    # Manual review
    monitor_manual = _pricingpromotion_monitor(
        tenant_a,
        variant=ecom_variant_a,
        match_strategy="manual",
    )
    assert monitor_manual.suggested_price is None

    # Out of stock
    monitor_oos = _pricingpromotion_monitor(
        tenant_a,
        variant=ecom_variant_a,
        match_strategy="match_exact",
        is_in_stock=False,
    )
    assert monitor_oos.suggested_price is None
