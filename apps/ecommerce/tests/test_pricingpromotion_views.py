"""Comprehensive view, route, filter, and CRUD tests for eCommerce 9.3 Pricing & Promotion Engine.

Covers:
- DynamicPriceRule views (list, detail, create, edit, delete)
- CouponPromotion views (list, detail, create, edit, delete)
- FlashSale views (list, detail, create, edit, delete)
- CompetitorPriceMonitor views (list, detail, create, edit, delete, sync action)

Naming conventions enforced:
- Test functions: test_pricingpromotion_*
"""
from decimal import Decimal
import pytest
from django.urls import reverse
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
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# DynamicPriceRule View Tests
# ==============================================================================

def test_pricingpromotion_dynamicpricerule_list(client_a, tenant_a):
    """Test DynamicPriceRule list view with context keys, filters, and search."""
    r1 = _pricingpromotion_rule(tenant_a, name="Alpha Discount", rule_type="percentage_discount", scope="storewide")
    r2 = _pricingpromotion_rule(tenant_a, name="Beta Discount", rule_type="fixed_discount", scope="storewide", customer_segment="wholesale")

    url = reverse("ecommerce:dynamicpricerule_list")

    # 1. Base list
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "rules" in resp.context
    assert "page_obj" in resp.context
    assert "rule_type_choices" in resp.context
    assert "scope_choices" in resp.context
    assert "segment_choices" in resp.context
    assert len(resp.context["rules"]) == 2
    assert "Alpha Discount" in resp.content.decode()

    # 2. Search query filter
    resp_q = client_a.get(url, {"q": "Alpha"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["rules"]) == 1

    # 3. Rule type filter
    resp_type = client_a.get(url, {"rule_type": "fixed_discount"})
    assert resp_type.status_code == 200
    assert len(resp_type.context["rules"]) == 1

    # 4. Customer segment filter
    resp_seg = client_a.get(url, {"customer_segment": "wholesale"})
    assert resp_seg.status_code == 200
    assert len(resp_seg.context["rules"]) == 1

    # 5. Junk parameter resilience
    resp_junk = client_a.get(url, {"rule_type": "nonexistent_type", "q": ""})
    assert resp_junk.status_code == 200


def test_pricingpromotion_dynamicpricerule_pagination(client_a, tenant_a):
    """Test DynamicPriceRule list pagination with > 25 rules."""
    for i in range(30):
        _pricingpromotion_rule(tenant_a, name=f"Bulk Rule {i}")

    url = reverse("ecommerce:dynamicpricerule_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["rules"]) == 25

    resp_p2 = client_a.get(url, {"page": 2})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["rules"]) == 5


def test_pricingpromotion_dynamicpricerule_detail(client_a, tenant_a, ecom_rule_a):
    """Test DynamicPriceRule detail view returns 200 with object context."""
    url = reverse("ecommerce:dynamicpricerule_detail", kwargs={"pk": ecom_rule_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["rule"] == ecom_rule_a
    assert ecom_rule_a.name in resp.content.decode()


def test_pricingpromotion_dynamicpricerule_create(client_a, tenant_a):
    """Test DynamicPriceRule create GET and POST flows."""
    url = reverse("ecommerce:dynamicpricerule_create")

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context.get("is_edit") is False

    # POST valid
    now = timezone.now()
    payload = {
        "name": "New Sitewide Rule",
        "rule_type": "percentage_discount",
        "adjustment_value": "12.5000",
        "scope": "storewide",
        "customer_segment": "all",
        "loyalty_tier": "none",
        "min_quantity": 1,
        "currency_code": "USD",
        "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
        "priority": 10,
        "is_active": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    created = DynamicPriceRule.objects.filter(tenant=tenant_a, name="New Sitewide Rule").first()
    assert created is not None
    assert created.adjustment_value == Decimal("12.5000")


def test_pricingpromotion_dynamicpricerule_edit(client_a, tenant_a, ecom_rule_a):
    """Test DynamicPriceRule edit GET and POST flows."""
    url = reverse("ecommerce:dynamicpricerule_edit", kwargs={"pk": ecom_rule_a.pk})

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["rule"] == ecom_rule_a
    assert resp_get.context.get("is_edit") is True

    # POST update
    now = timezone.now()
    payload = {
        "name": "Updated Rule Title",
        "rule_type": "fixed_discount",
        "adjustment_value": "30.0000",
        "scope": "storewide",
        "customer_segment": "vip",
        "loyalty_tier": "gold",
        "min_quantity": 2,
        "currency_code": "USD",
        "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
        "priority": 20,
        "is_active": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    ecom_rule_a.refresh_from_db()
    assert ecom_rule_a.name == "Updated Rule Title"
    assert ecom_rule_a.customer_segment == "vip"
    assert ecom_rule_a.priority == 20


def test_pricingpromotion_dynamicpricerule_delete(client_a, tenant_a, ecom_rule_a):
    """Test DynamicPriceRule delete confirmation and removal."""
    url = reverse("ecommerce:dynamicpricerule_delete", kwargs={"pk": ecom_rule_a.pk})

    # GET method not allowed (POST-only action)
    resp_get = client_a.get(url)
    assert resp_get.status_code == 405

    # POST delete
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert not DynamicPriceRule.objects.filter(pk=ecom_rule_a.pk).exists()


# ==============================================================================
# CouponPromotion View Tests
# ==============================================================================

def test_pricingpromotion_couponpromotion_list(client_a, tenant_a):
    """Test CouponPromotion list view, search, and type/status filters."""
    c1 = _pricingpromotion_coupon(tenant_a, code="SPRING10", discount_type="percentage", is_active=True)
    c2 = _pricingpromotion_coupon(tenant_a, code="WINTER20", discount_type="fixed_cart", is_active=False)

    url = reverse("ecommerce:couponpromotion_list")

    # 1. Base list
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "coupons" in resp.context
    assert len(resp.context["coupons"]) == 2

    # 2. Search query filter
    resp_q = client_a.get(url, {"q": "SPRING"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["coupons"]) == 1

    # 3. Discount type filter
    resp_type = client_a.get(url, {"discount_type": "fixed_cart"})
    assert resp_type.status_code == 200
    assert len(resp_type.context["coupons"]) == 1

    # 4. Status filter (active only)
    resp_stat = client_a.get(url, {"is_active": "1"})
    assert resp_stat.status_code == 200
    assert len(resp_stat.context["coupons"]) == 1


def test_pricingpromotion_couponpromotion_detail(client_a, tenant_a, ecom_coupon_a):
    """Test CouponPromotion detail view."""
    url = reverse("ecommerce:couponpromotion_detail", kwargs={"pk": ecom_coupon_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["coupon"] == ecom_coupon_a
    assert ecom_coupon_a.code in resp.content.decode()


def test_pricingpromotion_couponpromotion_create(client_a, tenant_a):
    """Test CouponPromotion create view."""
    url = reverse("ecommerce:couponpromotion_create")

    # GET
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context.get("is_edit") is False

    # POST valid
    now = timezone.now()
    payload = {
        "code": "CYBER50",
        "name": "Cyber Monday 50 Off",
        "discount_type": "fixed_cart",
        "discount_value": "50.0000",
        "min_spend": "150.0000",
        "usage_limit_total": 200,
        "usage_limit_per_customer": 1,
        "loyalty_tier_required": "none",
        "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
        "is_active": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    created = CouponPromotion.objects.filter(tenant=tenant_a, code="CYBER50").first()
    assert created is not None
    assert created.discount_value == Decimal("50.0000")


def test_pricingpromotion_couponpromotion_edit(client_a, tenant_a, ecom_coupon_a):
    """Test CouponPromotion edit view."""
    url = reverse("ecommerce:couponpromotion_edit", kwargs={"pk": ecom_coupon_a.pk})

    now = timezone.now()
    payload = {
        "code": ecom_coupon_a.code,
        "name": "Modified Promo Campaign",
        "discount_type": "percentage",
        "discount_value": "30.0000",
        "min_spend": "75.0000",
        "usage_limit_total": 1000,
        "usage_limit_per_customer": 2,
        "loyalty_tier_required": "bronze",
        "valid_from": now.strftime("%Y-%m-%dT%H:%M"),
        "is_active": True,
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    ecom_coupon_a.refresh_from_db()
    assert ecom_coupon_a.name == "Modified Promo Campaign"
    assert ecom_coupon_a.discount_value == Decimal("30.0000")


def test_pricingpromotion_couponpromotion_delete(client_a, tenant_a, ecom_coupon_a):
    """Test CouponPromotion delete."""
    url = reverse("ecommerce:couponpromotion_delete", kwargs={"pk": ecom_coupon_a.pk})
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert not CouponPromotion.objects.filter(pk=ecom_coupon_a.pk).exists()


# ==============================================================================
# FlashSale View Tests
# ==============================================================================

def test_pricingpromotion_flashsale_list(client_a, tenant_a, ecom_variant_a):
    """Test FlashSale list view, search, and status filter."""
    s1 = _pricingpromotion_flash_sale(tenant_a, title="Noon Lightning", variant=ecom_variant_a, status="active")
    s2 = _pricingpromotion_flash_sale(tenant_a, title="Evening Blitz", variant=ecom_variant_a, status="draft")

    url = reverse("ecommerce:flashsale_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales" in resp.context
    assert len(resp.context["sales"]) == 2

    # Search filter
    resp_q = client_a.get(url, {"q": "Evening"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["sales"]) == 1

    # Status filter
    resp_stat = client_a.get(url, {"status": "active"})
    assert resp_stat.status_code == 200
    assert len(resp_stat.context["sales"]) == 1


def test_pricingpromotion_flashsale_detail(client_a, tenant_a, ecom_flash_sale_a):
    """Test FlashSale detail view."""
    url = reverse("ecommerce:flashsale_detail", kwargs={"pk": ecom_flash_sale_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["sale"] == ecom_flash_sale_a
    assert ecom_flash_sale_a.title in resp.content.decode()


def test_pricingpromotion_flashsale_create(client_a, tenant_a, ecom_variant_a):
    """Test FlashSale create view."""
    url = reverse("ecommerce:flashsale_create")
    now = timezone.now()
    payload = {
        "title": "Weekend Lightning Deal",
        "status": "scheduled",
        "product": ecom_variant_a.product.pk,
        "variant": ecom_variant_a.pk,
        "discount_percentage": "40.00",
        "inventory_cap": 75,
        "max_units_per_order": 3,
        "start_time": (now + timezone.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
        "end_time": (now + timezone.timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M"),
        "badge_label": "FLASH DEAL",
        "banner_bg_color": "#ef4444",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    created = FlashSale.objects.filter(tenant=tenant_a, title="Weekend Lightning Deal").first()
    assert created is not None
    assert created.inventory_cap == 75


def test_pricingpromotion_flashsale_edit(client_a, tenant_a, ecom_flash_sale_a):
    """Test FlashSale edit view."""
    url = reverse("ecommerce:flashsale_edit", kwargs={"pk": ecom_flash_sale_a.pk})
    now = timezone.now()
    payload = {
        "title": "Updated Lightning Title",
        "status": "paused",
        "product": ecom_flash_sale_a.product.pk if ecom_flash_sale_a.product else "",
        "variant": ecom_flash_sale_a.variant.pk if ecom_flash_sale_a.variant else "",
        "discount_percentage": "45.00",
        "inventory_cap": 120,
        "max_units_per_order": 2,
        "start_time": now.strftime("%Y-%m-%dT%H:%M"),
        "end_time": (now + timezone.timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M"),
        "badge_label": "HOT DEAL",
        "banner_bg_color": "#f59e0b",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    ecom_flash_sale_a.refresh_from_db()
    assert ecom_flash_sale_a.title == "Updated Lightning Title"
    assert ecom_flash_sale_a.status == "paused"
    assert ecom_flash_sale_a.inventory_cap == 120


def test_pricingpromotion_flashsale_delete(client_a, tenant_a, ecom_flash_sale_a):
    """Test FlashSale delete view."""
    url = reverse("ecommerce:flashsale_delete", kwargs={"pk": ecom_flash_sale_a.pk})
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert not FlashSale.objects.filter(pk=ecom_flash_sale_a.pk).exists()


# ==============================================================================
# CompetitorPriceMonitor View Tests
# ==============================================================================

def test_pricingpromotion_competitorpricemonitor_list(client_a, tenant_a, ecom_variant_a):
    """Test CompetitorPriceMonitor list view, search, and strategy/status filters."""
    m1 = _pricingpromotion_monitor(tenant_a, variant=ecom_variant_a, competitor_name="Amazon Target", match_strategy="beat_by_fixed", status="active")
    m2 = _pricingpromotion_monitor(tenant_a, variant=ecom_variant_a, competitor_name="Walmart Target", match_strategy="manual", status="paused")

    url = reverse("ecommerce:competitorpricemonitor_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "monitors" in resp.context
    assert len(resp.context["monitors"]) == 2

    # Search filter
    resp_q = client_a.get(url, {"q": "Amazon"})
    assert resp_q.status_code == 200
    assert len(resp_q.context["monitors"]) == 1

    # Strategy filter
    resp_strat = client_a.get(url, {"strategy": "beat_by_fixed"})
    assert resp_strat.status_code == 200
    assert len(resp_strat.context["monitors"]) == 1

    # Status filter
    resp_stat = client_a.get(url, {"status": "paused"})
    assert resp_stat.status_code == 200
    assert len(resp_stat.context["monitors"]) == 1


def test_pricingpromotion_competitorpricemonitor_detail(client_a, tenant_a, ecom_monitor_a):
    """Test CompetitorPriceMonitor detail view."""
    url = reverse("ecommerce:competitorpricemonitor_detail", kwargs={"pk": ecom_monitor_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["monitor"] == ecom_monitor_a
    assert ecom_monitor_a.competitor_name in resp.content.decode()


def test_pricingpromotion_competitorpricemonitor_create(client_a, tenant_a, ecom_variant_a):
    """Test CompetitorPriceMonitor create view."""
    url = reverse("ecommerce:competitorpricemonitor_create")
    payload = {
        "competitor_name": "Best Buy Electronics",
        "variant": ecom_variant_a.pk,
        "competitor_url": "https://www.bestbuy.com/site/6451234.p",
        "competitor_price": "929.9900",
        "competitor_currency": "USD",
        "is_in_stock": True,
        "match_strategy": "match_exact",
        "beat_by_value": "0.0000",
        "min_margin_pct": "15.00",
        "status": "active",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    created = CompetitorPriceMonitor.objects.filter(tenant=tenant_a, competitor_name="Best Buy Electronics").first()
    assert created is not None
    assert created.competitor_price == Decimal("929.9900")


def test_pricingpromotion_competitorpricemonitor_edit(client_a, tenant_a, ecom_monitor_a):
    """Test CompetitorPriceMonitor edit view."""
    url = reverse("ecommerce:competitorpricemonitor_edit", kwargs={"pk": ecom_monitor_a.pk})
    payload = {
        "competitor_name": "MegaStore Prime",
        "variant": ecom_monitor_a.variant.pk,
        "competitor_url": ecom_monitor_a.competitor_url,
        "competitor_price": "859.0000",
        "competitor_currency": "USD",
        "is_in_stock": True,
        "match_strategy": "beat_by_percent",
        "beat_by_value": "3.5000",
        "min_margin_pct": "12.00",
        "status": "active",
    }
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    ecom_monitor_a.refresh_from_db()
    assert ecom_monitor_a.competitor_name == "MegaStore Prime"
    assert ecom_monitor_a.match_strategy == "beat_by_percent"


def test_pricingpromotion_competitorpricemonitor_delete(client_a, tenant_a, ecom_monitor_a):
    """Test CompetitorPriceMonitor delete view."""
    url = reverse("ecommerce:competitorpricemonitor_delete", kwargs={"pk": ecom_monitor_a.pk})
    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    assert not CompetitorPriceMonitor.objects.filter(pk=ecom_monitor_a.pk).exists()


def test_pricingpromotion_competitorpricemonitor_sync_action(client_a, tenant_a, ecom_monitor_a):
    """Test CompetitorPriceMonitor price refresh/sync trigger action."""
    url = reverse("ecommerce:competitorpricemonitor_sync", kwargs={"pk": ecom_monitor_a.pk})
    assert ecom_monitor_a.last_scraped_at is None

    resp_post = client_a.post(url)
    assert resp_post.status_code == 302
    ecom_monitor_a.refresh_from_db()
    assert ecom_monitor_a.last_scraped_at is not None
