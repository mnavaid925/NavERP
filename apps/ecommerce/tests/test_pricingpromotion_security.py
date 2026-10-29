"""Multi-tenancy, authorization, and IDOR isolation tests for eCommerce 9.3 Pricing & Promotion Engine.

Covers:
- Unauthenticated access prevention (login redirect)
- Cross-tenant IDOR defense (404 on foreign tenant records)
- Queryset isolation on all list views
- Non-admin authorization restrictions (403 on destructive endpoints)
- Audit log emission on CRUD actions

Naming conventions enforced:
- Test functions: test_pricingpromotion_*
"""
import pytest
from django.urls import reverse

from apps.core.models import AuditLog
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
# Anonymous Access Tests
# ==============================================================================

@pytest.mark.parametrize(
    "url_name,args",
    [
        ("dynamicpricerule_list", []),
        ("dynamicpricerule_create", []),
        ("couponpromotion_list", []),
        ("couponpromotion_create", []),
        ("flashsale_list", []),
        ("flashsale_create", []),
        ("competitorpricemonitor_list", []),
        ("competitorpricemonitor_create", []),
    ],
)
def test_pricingpromotion_anonymous_redirects_to_login(client, url_name, args):
    """Ensure unauthenticated requests are redirected to login."""
    url = reverse(f"ecommerce:{url_name}", args=args)
    response = client.get(url)
    assert response.status_code == 302
    assert "/accounts/login/" in response.url or "/login/" in response.url


# ==============================================================================
# Cross-Tenant IDOR Tests
# ==============================================================================

def test_pricingpromotion_dynamicpricerule_cross_tenant_idor(client_a, ecom_rule_b):
    """Test client_a cannot view, edit, or delete client_b's DynamicPriceRule."""
    # Detail -> 404
    url_detail = reverse("ecommerce:dynamicpricerule_detail", kwargs={"pk": ecom_rule_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit -> 404
    url_edit = reverse("ecommerce:dynamicpricerule_edit", kwargs={"pk": ecom_rule_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked Rule"}).status_code == 404

    # Delete -> 404
    url_delete = reverse("ecommerce:dynamicpricerule_delete", kwargs={"pk": ecom_rule_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_pricingpromotion_couponpromotion_cross_tenant_idor(client_a, ecom_coupon_b):
    """Test client_a cannot view, edit, or delete client_b's CouponPromotion."""
    # Detail -> 404
    url_detail = reverse("ecommerce:couponpromotion_detail", kwargs={"pk": ecom_coupon_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit -> 404
    url_edit = reverse("ecommerce:couponpromotion_edit", kwargs={"pk": ecom_coupon_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"name": "Hacked Coupon"}).status_code == 404

    # Delete -> 404
    url_delete = reverse("ecommerce:couponpromotion_delete", kwargs={"pk": ecom_coupon_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_pricingpromotion_flashsale_cross_tenant_idor(client_a, ecom_flash_sale_b):
    """Test client_a cannot view, edit, or delete client_b's FlashSale."""
    # Detail -> 404
    url_detail = reverse("ecommerce:flashsale_detail", kwargs={"pk": ecom_flash_sale_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit -> 404
    url_edit = reverse("ecommerce:flashsale_edit", kwargs={"pk": ecom_flash_sale_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"title": "Hacked Flash Sale"}).status_code == 404

    # Delete -> 404
    url_delete = reverse("ecommerce:flashsale_delete", kwargs={"pk": ecom_flash_sale_b.pk})
    assert client_a.post(url_delete).status_code == 404


def test_pricingpromotion_competitorpricemonitor_cross_tenant_idor(client_a, ecom_monitor_b):
    """Test client_a cannot view, edit, delete, or sync client_b's CompetitorPriceMonitor."""
    # Detail -> 404
    url_detail = reverse("ecommerce:competitorpricemonitor_detail", kwargs={"pk": ecom_monitor_b.pk})
    assert client_a.get(url_detail).status_code == 404

    # Edit -> 404
    url_edit = reverse("ecommerce:competitorpricemonitor_edit", kwargs={"pk": ecom_monitor_b.pk})
    assert client_a.get(url_edit).status_code == 404
    assert client_a.post(url_edit, {"competitor_name": "Hacked Monitor"}).status_code == 404

    # Delete -> 404
    url_delete = reverse("ecommerce:competitorpricemonitor_delete", kwargs={"pk": ecom_monitor_b.pk})
    assert client_a.post(url_delete).status_code == 404

    # Sync -> 404
    url_sync = reverse("ecommerce:competitorpricemonitor_sync", kwargs={"pk": ecom_monitor_b.pk})
    assert client_a.post(url_sync).status_code == 404


# ==============================================================================
# List Queryset Scoping Tests
# ==============================================================================

def test_pricingpromotion_lists_tenant_isolation(
    client_a,
    tenant_a,
    tenant_b,
    ecom_rule_a,
    ecom_rule_b,
    ecom_coupon_a,
    ecom_coupon_b,
    ecom_flash_sale_a,
    ecom_flash_sale_b,
    ecom_monitor_a,
    ecom_monitor_b,
):
    """Test all 4 list views isolate querysets strictly by request.tenant."""
    # Rules list
    resp_rules = client_a.get(reverse("ecommerce:dynamicpricerule_list"))
    rules_in_view = resp_rules.context["rules"]
    assert ecom_rule_a in rules_in_view
    assert ecom_rule_b not in rules_in_view

    # Coupons list
    resp_coupons = client_a.get(reverse("ecommerce:couponpromotion_list"))
    coupons_in_view = resp_coupons.context["coupons"]
    assert ecom_coupon_a in coupons_in_view
    assert ecom_coupon_b not in coupons_in_view

    # Flash sales list
    resp_sales = client_a.get(reverse("ecommerce:flashsale_list"))
    sales_in_view = resp_sales.context["sales"]
    assert ecom_flash_sale_a in sales_in_view
    assert ecom_flash_sale_b not in sales_in_view

    # Competitor monitors list
    resp_monitors = client_a.get(reverse("ecommerce:competitorpricemonitor_list"))
    monitors_in_view = resp_monitors.context["monitors"]
    assert ecom_monitor_a in monitors_in_view
    assert ecom_monitor_b not in monitors_in_view


# ==============================================================================
# Audit Log Emission Tests
# ==============================================================================

def test_pricingpromotion_audit_log_emission_on_delete(client_a, tenant_a, ecom_rule_a):
    """Test that deleting a DynamicPriceRule writes an immutable AuditLog entry."""
    initial_count = AuditLog.objects.filter(tenant=tenant_a, action="delete").count()
    url = reverse("ecommerce:dynamicpricerule_delete", kwargs={"pk": ecom_rule_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302

    new_count = AuditLog.objects.filter(tenant=tenant_a, action="delete").count()
    assert new_count == initial_count + 1
    log = AuditLog.objects.filter(tenant=tenant_a, action="delete").latest("at")
    assert log.action == "delete"
    assert ecom_rule_a.name in str(log.changes) or ecom_rule_a.number in str(log.changes)


# ==============================================================================
# Tenant Admin Restriction Tests
# ==============================================================================

def test_pricingpromotion_non_admin_member_delete_forbidden(member_client, tenant_a, ecom_rule_a):
    """Test non-admin member gets 403 Forbidden on tenant-admin protected endpoints."""
    url = reverse("ecommerce:dynamicpricerule_delete", kwargs={"pk": ecom_rule_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    # Ensure rule still exists
    assert DynamicPriceRule.objects.filter(pk=ecom_rule_a.pk).exists()
