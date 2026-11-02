"""Security, IDOR, authorization, method safety, mass assignment, negative input,
manifest scoping, and audit log forensics tests for eCommerce 9.16 Mobile Commerce.

Covers:
1. Multi-Tenant IDOR Isolation:
   - Cross-tenant detail access: Tenant A requesting Tenant B's MobileAppConfig,
     MobileDeviceRegistration, MobilePushCampaign, MobileLocationRule -> 404.
   - Cross-tenant edit access: Tenant A requesting Tenant B's edit URLs (GET and POST) -> 404.
   - Cross-tenant delete access: Tenant A POSTing to Tenant B's delete URLs -> 404, does not delete Tenant B record.
   - Cross-tenant action endpoints: Tenant A POSTing to Tenant B's ping, test_send, or simulate -> 404.
   - Cross-tenant foreign key tampering in form payloads rejected.
2. Authentication & Authorization:
   - Unauthenticated access: all 24 internal URLs redirect to login.
   - Non-admin authorization: non-admin member receives 403 on privileged write views (@tenant_admin_required).
   - Non-admin read access: non-admin member can read hub, lists, and details (200 OK).
3. Method Enforcement:
   - Delete, ping, test_send, and simulate endpoints return 405 on GET.
4. Mass Assignment Hardening:
   - Submitting `tenant`, `number`, `status`, `push_token` in POST payloads does not override view-owned attributes.
5. Negative Input & Injection Hardening:
   - Non-finite coordinates (`NaN`, `Infinity`, `inf`), out-of-range floats, and malformed strings safely handled
     without unhandled 500 crashes.
   - Malicious CSS / script injection strings in hex color inputs fail form validation safely.
   - XSS script tags in text fields are HTML-escaped when rendered in templates.
6. Public Manifest Scoping:
   - `pwa_manifest_json` exposes only non-sensitive manifest data and respects tenant isolation and `enable_pwa`.
   - Payment secrets (e.g. apple_pay_merchant_id, google_pay_gateway_id) are never leaked in manifest JSON.
7. Audit Log Forensics:
   - Verify `AuditLog` records exist for CREATE, UPDATE, DELETE, and SEND actions.
   - Verify AuditLog records are strictly isolated by tenant.

Conventions enforced:
- pytestmark = pytest.mark.django_db
- Test functions: test_mobilecommerce_*
- Module-level helpers: _mobilecommerce_*
- Fixtures and model helpers from apps.ecommerce.tests.conftest
"""
from decimal import Decimal
import json
import uuid

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.models import AuditLog, Party
from apps.ecommerce.forms.MobileCommerce.MobileAppConfigs import MobileAppConfigForm
from apps.ecommerce.forms.MobileCommerce.MobileDeviceRegistrations import MobileDeviceRegistrationForm
from apps.ecommerce.forms.MobileCommerce.MobileLocationRules import MobileLocationRuleForm
from apps.ecommerce.forms.MobileCommerce.MobilePushCampaigns import MobilePushCampaignForm
from apps.ecommerce.models import (
    MobileAppConfig,
    MobileDeviceRegistration,
    MobilePushCampaign,
    MobileLocationRule,
)
from apps.ecommerce.tests.conftest import (
    _mobilecommerce_app_config,
    _mobilecommerce_device_registration,
    _mobilecommerce_push_campaign,
    _mobilecommerce_location_rule,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Module-Level Helpers (_mobilecommerce_*)
# ==============================================================================

def _mobilecommerce_valid_appconfig_post_data(**overrides):
    """Generate a valid POST data dictionary for MobileAppConfig creation/edit."""
    data = {
        "app_name": "Secure Mobile Storefront",
        "short_name": "SecStore",
        "description": "Progressive Web App security test storefront.",
        "theme_color": "#2563EB",
        "background_color": "#FFFFFF",
        "display_mode": "standalone",
        "orientation": "portrait",
        "start_url": "/ecommerce/",
        "scope": "/ecommerce/",
        "icon_192_url": "/static/ecommerce/img/icon-192.png",
        "icon_512_url": "/static/ecommerce/img/icon-512.png",
        "offline_cache_strategy": "stale_while_revalidate",
        "offline_fallback_html": "<h1>Offline</h1><p>Please check your internet connection.</p>",
        "enable_pwa": True,
        "enable_biometric_login": True,
        "min_ios_version": "16.0",
        "min_android_version": "12.0",
        "apple_pay_merchant_id": "merchant.com.example.secure",
        "google_pay_gateway_id": "gateway-acme-sec",
        "enable_apple_pay": True,
        "enable_google_pay": True,
        "enable_in_app_wallet": True,
        "enable_express_checkout": True,
        "is_active": True,
    }
    data.update(overrides)
    return data


def _mobilecommerce_valid_device_post_data(customer_profile=None, party=None, **overrides):
    """Generate a valid POST data dictionary for MobileDeviceRegistration creation/edit."""
    data = {
        "customer_profile": customer_profile.pk if customer_profile else "",
        "party": party.pk if party else "",
        "device_uuid": str(uuid.uuid4()),
        "device_platform": "ios",
        "device_model": "iPhone 16 Pro",
        "os_version": "iOS 18.2",
        "app_version": "3.1.0",
        "push_provider": "apns",
        "push_enabled": True,
        "biometric_enrolled": True,
        "location_permission": "while_in_use",
        "last_latitude": "37.774929",
        "last_longitude": "-122.419416",
        "is_active": True,
    }
    data.update(overrides)
    return data


def _mobilecommerce_valid_pushcampaign_post_data(product=None, category=None, coupon=None, **overrides):
    """Generate a valid POST data dictionary for MobilePushCampaign creation/edit."""
    data = {
        "campaign_name": "Security Push Blast",
        "campaign_type": "promotional",
        "target_platform": "all",
        "notification_title": "Exclusive Flash Sale Today!",
        "notification_body": "Use code SECURE20 for 20% off all catalog items.",
        "image_url": "https://cdn.example.com/promos/sec.jpg",
        "badge_increment": 1,
        "sound_name": "default",
        "deep_link_type": "home",
        "deep_link_url": "navstore://home",
        "target_product": product.pk if product else "",
        "target_category": category.pk if category else "",
        "target_coupon": coupon.pk if coupon else "",
        "scheduled_for": timezone.now().strftime("%Y-%m-%dT%H:%M"),
    }
    data.update(overrides)
    return data


def _mobilecommerce_valid_locationrule_post_data(center=None, promotion=None, **overrides):
    """Generate a valid POST data dictionary for MobileLocationRule creation/edit."""
    data = {
        "name": "Downtown Secure Geofence",
        "rule_type": "geofence_entry",
        "fulfillment_center": center.pk if center else "",
        "store_name": "Secure Flagship Store",
        "latitude": "40.712776",
        "longitude": "-74.005974",
        "radius_meters": 300,
        "trigger_action": "apply_coupon",
        "linked_promotion": promotion.pk if promotion else "",
        "push_message": "Welcome to our store! Check in for express pickup.",
        "enable_bopis_checkin": True,
        "enable_instore_mode": True,
        "dwell_time_seconds": 60,
        "is_active": True,
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. Multi-Tenant IDOR Isolation Tests
# ==============================================================================

def test_mobilecommerce_idor_appconfig_detail_blocked(auth_client_a, ecom_mobile_config_b):
    """Tenant A client requesting Tenant B MobileAppConfig detail returns 404."""
    url = reverse("ecommerce:mobileappconfig_detail", args=[ecom_mobile_config_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_mobilecommerce_idor_appconfig_edit_blocked(auth_client_a, ecom_mobile_config_b):
    """Tenant A client requesting Tenant B MobileAppConfig edit returns 404 on GET and POST."""
    url = reverse("ecommerce:mobileappconfig_edit", args=[ecom_mobile_config_b.pk])
    assert auth_client_a.get(url).status_code == 404

    payload = _mobilecommerce_valid_appconfig_post_data(
        short_name="TamperedConfig",
        app_name="Tampered App Name",
    )
    assert auth_client_a.post(url, payload).status_code == 404

    ecom_mobile_config_b.refresh_from_db()
    assert ecom_mobile_config_b.short_name != "TamperedConfig"


def test_mobilecommerce_idor_appconfig_delete_blocked(auth_client_a, ecom_mobile_config_b):
    """Tenant A client POSTing to Tenant B MobileAppConfig delete returns 404 and does not delete."""
    url = reverse("ecommerce:mobileappconfig_delete", args=[ecom_mobile_config_b.pk])
    resp = auth_client_a.post(url)
    assert resp.status_code == 404
    assert MobileAppConfig.objects.filter(pk=ecom_mobile_config_b.pk).exists() is True


def test_mobilecommerce_idor_device_detail_blocked(auth_client_a, ecom_mobile_device_b):
    """Tenant A client requesting Tenant B MobileDeviceRegistration detail returns 404."""
    url = reverse("ecommerce:mobiledeviceregistration_detail", args=[ecom_mobile_device_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_mobilecommerce_idor_device_edit_blocked(auth_client_a, ecom_mobile_device_b):
    """Tenant A client requesting Tenant B MobileDeviceRegistration edit returns 404 on GET and POST."""
    url = reverse("ecommerce:mobiledeviceregistration_edit", args=[ecom_mobile_device_b.pk])
    assert auth_client_a.get(url).status_code == 404

    payload = _mobilecommerce_valid_device_post_data(device_model="Tampered Model X")
    assert auth_client_a.post(url, payload).status_code == 404

    ecom_mobile_device_b.refresh_from_db()
    assert ecom_mobile_device_b.device_model != "Tampered Model X"


def test_mobilecommerce_idor_device_delete_blocked(auth_client_a, ecom_mobile_device_b):
    """Tenant A client POSTing to Tenant B MobileDeviceRegistration delete returns 404 and does not delete."""
    url = reverse("ecommerce:mobiledeviceregistration_delete", args=[ecom_mobile_device_b.pk])
    resp = auth_client_a.post(url)
    assert resp.status_code == 404
    assert MobileDeviceRegistration.objects.filter(pk=ecom_mobile_device_b.pk).exists() is True


def test_mobilecommerce_idor_device_ping_blocked(auth_client_a, ecom_mobile_device_b):
    """Tenant A client POSTing to Tenant B MobileDeviceRegistration telemetry ping returns 404."""
    url = reverse("ecommerce:mobiledeviceregistration_ping", args=[ecom_mobile_device_b.pk])
    resp = auth_client_a.post(url, {"lat": "37.7749", "lng": "-122.4194"})
    assert resp.status_code == 404


def test_mobilecommerce_idor_pushcampaign_detail_blocked(auth_client_a, ecom_mobile_push_b):
    """Tenant A client requesting Tenant B MobilePushCampaign detail returns 404."""
    url = reverse("ecommerce:mobilepushcampaign_detail", args=[ecom_mobile_push_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_mobilecommerce_idor_pushcampaign_edit_blocked(auth_client_a, ecom_mobile_push_b):
    """Tenant A client requesting Tenant B MobilePushCampaign edit returns 404 on GET and POST."""
    url = reverse("ecommerce:mobilepushcampaign_edit", args=[ecom_mobile_push_b.pk])
    assert auth_client_a.get(url).status_code == 404

    payload = _mobilecommerce_valid_pushcampaign_post_data(campaign_name="Hacked Campaign")
    assert auth_client_a.post(url, payload).status_code == 404

    ecom_mobile_push_b.refresh_from_db()
    assert ecom_mobile_push_b.campaign_name != "Hacked Campaign"


def test_mobilecommerce_idor_pushcampaign_delete_blocked(auth_client_a, ecom_mobile_push_b):
    """Tenant A client POSTing to Tenant B MobilePushCampaign delete returns 404 and does not delete."""
    url = reverse("ecommerce:mobilepushcampaign_delete", args=[ecom_mobile_push_b.pk])
    resp = auth_client_a.post(url)
    assert resp.status_code == 404
    assert MobilePushCampaign.objects.filter(pk=ecom_mobile_push_b.pk).exists() is True


def test_mobilecommerce_idor_pushcampaign_test_send_blocked(auth_client_a, ecom_mobile_push_b):
    """Tenant A client POSTing to Tenant B MobilePushCampaign test_send returns 404 and does not dispatch."""
    url = reverse("ecommerce:mobilepushcampaign_test_send", args=[ecom_mobile_push_b.pk])
    resp = auth_client_a.post(url)
    assert resp.status_code == 404

    ecom_mobile_push_b.refresh_from_db()
    assert ecom_mobile_push_b.sent_count == 0
    assert ecom_mobile_push_b.status == "draft"


def test_mobilecommerce_idor_locationrule_detail_blocked(auth_client_a, ecom_mobile_location_b):
    """Tenant A client requesting Tenant B MobileLocationRule detail returns 404."""
    url = reverse("ecommerce:mobilelocationrule_detail", args=[ecom_mobile_location_b.pk])
    resp = auth_client_a.get(url)
    assert resp.status_code == 404


def test_mobilecommerce_idor_locationrule_edit_blocked(auth_client_a, ecom_mobile_location_b):
    """Tenant A client requesting Tenant B MobileLocationRule edit returns 404 on GET and POST."""
    url = reverse("ecommerce:mobilelocationrule_edit", args=[ecom_mobile_location_b.pk])
    assert auth_client_a.get(url).status_code == 404

    payload = _mobilecommerce_valid_locationrule_post_data(name="Tampered Geofence")
    assert auth_client_a.post(url, payload).status_code == 404

    ecom_mobile_location_b.refresh_from_db()
    assert ecom_mobile_location_b.name != "Tampered Geofence"


def test_mobilecommerce_idor_locationrule_delete_blocked(auth_client_a, ecom_mobile_location_b):
    """Tenant A client POSTing to Tenant B MobileLocationRule delete returns 404 and does not delete."""
    url = reverse("ecommerce:mobilelocationrule_delete", args=[ecom_mobile_location_b.pk])
    resp = auth_client_a.post(url)
    assert resp.status_code == 404
    assert MobileLocationRule.objects.filter(pk=ecom_mobile_location_b.pk).exists() is True


def test_mobilecommerce_idor_locationrule_simulate_blocked(auth_client_a, ecom_mobile_location_b):
    """Tenant A client POSTing to Tenant B MobileLocationRule simulate returns 404."""
    url = reverse("ecommerce:mobilelocationrule_simulate", args=[ecom_mobile_location_b.pk])
    resp = auth_client_a.post(url, {"test_lat": "40.712776", "test_lng": "-74.005974"})
    assert resp.status_code == 404


def test_mobilecommerce_cross_tenant_fk_tampering_rejected(
    tenant_a,
    tenant_b,
    ecom_profile_b,
    ecom_product_b,
    ecom_category_b,
    ecom_coupon_b,
    ecom_center_b,
):
    """Forms strictly reject cross-tenant foreign key injections via reject_foreign."""
    # 1. Device form rejecting foreign customer_profile
    data_dev = _mobilecommerce_valid_device_post_data(customer_profile=ecom_profile_b)
    form_dev = MobileDeviceRegistrationForm(data=data_dev, tenant=tenant_a)
    assert not form_dev.is_valid()
    assert "customer_profile" in form_dev.errors

    # 2. Push campaign form rejecting foreign product, category, coupon
    data_push_prod = _mobilecommerce_valid_pushcampaign_post_data(product=ecom_product_b)
    form_push_prod = MobilePushCampaignForm(data=data_push_prod, tenant=tenant_a)
    assert not form_push_prod.is_valid()
    assert "target_product" in form_push_prod.errors

    data_push_cat = _mobilecommerce_valid_pushcampaign_post_data(category=ecom_category_b)
    form_push_cat = MobilePushCampaignForm(data=data_push_cat, tenant=tenant_a)
    assert not form_push_cat.is_valid()
    assert "target_category" in form_push_cat.errors

    data_push_coup = _mobilecommerce_valid_pushcampaign_post_data(coupon=ecom_coupon_b)
    form_push_coup = MobilePushCampaignForm(data=data_push_coup, tenant=tenant_a)
    assert not form_push_coup.is_valid()
    assert "target_coupon" in form_push_coup.errors

    # 3. Location rule form rejecting foreign fulfillment_center, linked_promotion
    data_loc_fc = _mobilecommerce_valid_locationrule_post_data(center=ecom_center_b)
    form_loc_fc = MobileLocationRuleForm(data=data_loc_fc, tenant=tenant_a)
    assert not form_loc_fc.is_valid()
    assert "fulfillment_center" in form_loc_fc.errors

    data_loc_promo = _mobilecommerce_valid_locationrule_post_data(promotion=ecom_coupon_b)
    form_loc_promo = MobileLocationRuleForm(data=data_loc_promo, tenant=tenant_a)
    assert not form_loc_promo.is_valid()
    assert "linked_promotion" in form_loc_promo.errors


# ==============================================================================
# 2. Authentication & Authorization Tests
# ==============================================================================

def test_mobilecommerce_unauthenticated_access_redirects_to_login(
    client,
    ecom_mobile_config_a,
    ecom_mobile_device_a,
    ecom_mobile_push_a,
    ecom_mobile_location_a,
):
    """Assert unauthenticated anonymous requests to all 24 internal URLs redirect to login."""
    urls = [
        # Hub
        reverse("ecommerce:mobile_hub"),
        # Configs
        reverse("ecommerce:mobileappconfig_list"),
        reverse("ecommerce:mobileappconfig_create"),
        reverse("ecommerce:mobileappconfig_detail", args=[ecom_mobile_config_a.pk]),
        reverse("ecommerce:mobileappconfig_edit", args=[ecom_mobile_config_a.pk]),
        reverse("ecommerce:mobileappconfig_delete", args=[ecom_mobile_config_a.pk]),
        # Devices
        reverse("ecommerce:mobiledeviceregistration_list"),
        reverse("ecommerce:mobiledeviceregistration_create"),
        reverse("ecommerce:mobiledeviceregistration_detail", args=[ecom_mobile_device_a.pk]),
        reverse("ecommerce:mobiledeviceregistration_edit", args=[ecom_mobile_device_a.pk]),
        reverse("ecommerce:mobiledeviceregistration_delete", args=[ecom_mobile_device_a.pk]),
        reverse("ecommerce:mobiledeviceregistration_ping", args=[ecom_mobile_device_a.pk]),
        # Push Campaigns
        reverse("ecommerce:mobilepushcampaign_list"),
        reverse("ecommerce:mobilepushcampaign_create"),
        reverse("ecommerce:mobilepushcampaign_detail", args=[ecom_mobile_push_a.pk]),
        reverse("ecommerce:mobilepushcampaign_edit", args=[ecom_mobile_push_a.pk]),
        reverse("ecommerce:mobilepushcampaign_delete", args=[ecom_mobile_push_a.pk]),
        reverse("ecommerce:mobilepushcampaign_test_send", args=[ecom_mobile_push_a.pk]),
        # Location Rules
        reverse("ecommerce:mobilelocationrule_list"),
        reverse("ecommerce:mobilelocationrule_create"),
        reverse("ecommerce:mobilelocationrule_detail", args=[ecom_mobile_location_a.pk]),
        reverse("ecommerce:mobilelocationrule_edit", args=[ecom_mobile_location_a.pk]),
        reverse("ecommerce:mobilelocationrule_delete", args=[ecom_mobile_location_a.pk]),
        reverse("ecommerce:mobilelocationrule_simulate", args=[ecom_mobile_location_a.pk]),
    ]

    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for {url}, got {resp.status_code}"
        assert "/login/" in resp.url or "accounts" in resp.url


def test_mobilecommerce_non_admin_forbidden_on_privileged_write_views(
    member_client,
    ecom_mobile_config_a,
    ecom_mobile_device_a,
    ecom_mobile_push_a,
    ecom_mobile_location_a,
):
    """Non-admin member client receives 403 Forbidden on all views decorated with @tenant_admin_required."""
    privileged_write_endpoints = [
        # AppConfig
        ("GET", reverse("ecommerce:mobileappconfig_create"), None),
        ("POST", reverse("ecommerce:mobileappconfig_create"), _mobilecommerce_valid_appconfig_post_data()),
        ("GET", reverse("ecommerce:mobileappconfig_edit", args=[ecom_mobile_config_a.pk]), None),
        ("POST", reverse("ecommerce:mobileappconfig_edit", args=[ecom_mobile_config_a.pk]), _mobilecommerce_valid_appconfig_post_data()),
        ("POST", reverse("ecommerce:mobileappconfig_delete", args=[ecom_mobile_config_a.pk]), None),
        # DeviceRegistration
        ("GET", reverse("ecommerce:mobiledeviceregistration_create"), None),
        ("POST", reverse("ecommerce:mobiledeviceregistration_create"), _mobilecommerce_valid_device_post_data()),
        ("GET", reverse("ecommerce:mobiledeviceregistration_edit", args=[ecom_mobile_device_a.pk]), None),
        ("POST", reverse("ecommerce:mobiledeviceregistration_edit", args=[ecom_mobile_device_a.pk]), _mobilecommerce_valid_device_post_data()),
        ("POST", reverse("ecommerce:mobiledeviceregistration_delete", args=[ecom_mobile_device_a.pk]), None),
        ("POST", reverse("ecommerce:mobiledeviceregistration_ping", args=[ecom_mobile_device_a.pk]), {"lat": "37.77", "lng": "-122.41"}),
        # PushCampaign
        ("GET", reverse("ecommerce:mobilepushcampaign_create"), None),
        ("POST", reverse("ecommerce:mobilepushcampaign_create"), _mobilecommerce_valid_pushcampaign_post_data()),
        ("GET", reverse("ecommerce:mobilepushcampaign_edit", args=[ecom_mobile_push_a.pk]), None),
        ("POST", reverse("ecommerce:mobilepushcampaign_edit", args=[ecom_mobile_push_a.pk]), _mobilecommerce_valid_pushcampaign_post_data()),
        ("POST", reverse("ecommerce:mobilepushcampaign_delete", args=[ecom_mobile_push_a.pk]), None),
        ("POST", reverse("ecommerce:mobilepushcampaign_test_send", args=[ecom_mobile_push_a.pk]), None),
        # LocationRule
        ("GET", reverse("ecommerce:mobilelocationrule_create"), None),
        ("POST", reverse("ecommerce:mobilelocationrule_create"), _mobilecommerce_valid_locationrule_post_data()),
        ("GET", reverse("ecommerce:mobilelocationrule_edit", args=[ecom_mobile_location_a.pk]), None),
        ("POST", reverse("ecommerce:mobilelocationrule_edit", args=[ecom_mobile_location_a.pk]), _mobilecommerce_valid_locationrule_post_data()),
        ("POST", reverse("ecommerce:mobilelocationrule_delete", args=[ecom_mobile_location_a.pk]), None),
        ("POST", reverse("ecommerce:mobilelocationrule_simulate", args=[ecom_mobile_location_a.pk]), {"test_lat": "40.71", "test_lng": "-74.00"}),
    ]

    for method, url, data in privileged_write_endpoints:
        if method == "GET":
            resp = member_client.get(url)
        else:
            resp = member_client.post(url, data or {})
        assert resp.status_code == 403, f"Expected 403 Forbidden for {method} {url}, got {resp.status_code}"


def test_mobilecommerce_non_admin_allowed_read_views(
    member_client,
    ecom_mobile_config_a,
    ecom_mobile_device_a,
    ecom_mobile_push_a,
    ecom_mobile_location_a,
):
    """Non-admin member client can access read views (hub, lists, details) with 200 OK."""
    read_urls = [
        reverse("ecommerce:mobile_hub"),
        reverse("ecommerce:mobileappconfig_list"),
        reverse("ecommerce:mobileappconfig_detail", args=[ecom_mobile_config_a.pk]),
        reverse("ecommerce:mobiledeviceregistration_list"),
        reverse("ecommerce:mobiledeviceregistration_detail", args=[ecom_mobile_device_a.pk]),
        reverse("ecommerce:mobilepushcampaign_list"),
        reverse("ecommerce:mobilepushcampaign_detail", args=[ecom_mobile_push_a.pk]),
        reverse("ecommerce:mobilelocationrule_list"),
        reverse("ecommerce:mobilelocationrule_detail", args=[ecom_mobile_location_a.pk]),
    ]
    for url in read_urls:
        resp = member_client.get(url)
        assert resp.status_code == 200, f"Expected 200 OK for {url}, got {resp.status_code}"


# ==============================================================================
# 3. Method Enforcement Tests (@require_POST)
# ==============================================================================

def test_mobilecommerce_method_enforcement_get_on_post_only_endpoints(
    auth_client_a,
    ecom_mobile_config_a,
    ecom_mobile_device_a,
    ecom_mobile_push_a,
    ecom_mobile_location_a,
):
    """Assert GET requests to POST-only actions and delete views return 405 Method Not Allowed."""
    post_only_urls = [
        reverse("ecommerce:mobileappconfig_delete", args=[ecom_mobile_config_a.pk]),
        reverse("ecommerce:mobiledeviceregistration_delete", args=[ecom_mobile_device_a.pk]),
        reverse("ecommerce:mobiledeviceregistration_ping", args=[ecom_mobile_device_a.pk]),
        reverse("ecommerce:mobilepushcampaign_delete", args=[ecom_mobile_push_a.pk]),
        reverse("ecommerce:mobilepushcampaign_test_send", args=[ecom_mobile_push_a.pk]),
        reverse("ecommerce:mobilelocationrule_delete", args=[ecom_mobile_location_a.pk]),
        reverse("ecommerce:mobilelocationrule_simulate", args=[ecom_mobile_location_a.pk]),
    ]
    for url in post_only_urls:
        resp = auth_client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET {url}, got {resp.status_code}"


# ==============================================================================
# 4. Mass Assignment Hardening Tests
# ==============================================================================

def test_mobilecommerce_mass_assignment_appconfig(auth_client_a, tenant_a, tenant_b):
    """Submitting foreign tenant or system number in payload cannot reassign tenant or override number."""
    payload = _mobilecommerce_valid_appconfig_post_data(
        short_name="MassAssignConfig",
        tenant=tenant_b.pk,
        number="MALICIOUS-MAC-999",
    )
    url = reverse("ecommerce:mobileappconfig_create")
    resp = auth_client_a.post(url, payload)
    assert resp.status_code == 302

    created_config = MobileAppConfig.objects.get(short_name="MassAssignConfig")
    assert created_config.tenant == tenant_a
    assert created_config.number.startswith("EMAC-")
    assert created_config.number != "MALICIOUS-MAC-999"


def test_mobilecommerce_mass_assignment_device_registration(auth_client_a, tenant_a, tenant_b):
    """Submitting foreign tenant, system number, or push_token cannot overwrite view-owned fields."""
    dev_uuid = str(uuid.uuid4())
    payload = _mobilecommerce_valid_device_post_data(
        device_uuid=dev_uuid,
        tenant=tenant_b.pk,
        number="MALICIOUS-DEV-999",
        push_token="injected_malicious_token",
    )
    url = reverse("ecommerce:mobiledeviceregistration_create")
    resp = auth_client_a.post(url, payload)
    assert resp.status_code == 302

    created_dev = MobileDeviceRegistration.objects.get(device_uuid=dev_uuid)
    assert created_dev.tenant == tenant_a
    assert created_dev.number.startswith("EMDR-")
    assert created_dev.number != "MALICIOUS-DEV-999"
    # push_token is excluded from the form and should remain the model default ("")
    assert created_dev.push_token == ""


def test_mobilecommerce_mass_assignment_push_campaign(auth_client_a, tenant_a, tenant_b):
    """Submitting status, metric counters, or tenant cannot override campaign workflow defaults."""
    payload = _mobilecommerce_valid_pushcampaign_post_data(
        campaign_name="MassAssignPushCampaign",
        tenant=tenant_b.pk,
        number="MALICIOUS-MPC-999",
        status="sent",
        sent_count=99999,
        delivered_count=88888,
        opened_count=77777,
        converted_count=66666,
        converted_revenue="123456.78",
    )
    url = reverse("ecommerce:mobilepushcampaign_create")
    resp = auth_client_a.post(url, payload)
    assert resp.status_code == 302

    created_camp = MobilePushCampaign.objects.get(campaign_name="MassAssignPushCampaign")
    assert created_camp.tenant == tenant_a
    assert created_camp.number.startswith("EMPC-")
    assert created_camp.number != "MALICIOUS-MPC-999"
    # System & metrics attributes must remain at initial default values
    assert created_camp.status == "draft"
    assert created_camp.sent_count == 0
    assert created_camp.delivered_count == 0
    assert created_camp.opened_count == 0
    assert created_camp.converted_count == 0
    assert created_camp.converted_revenue == Decimal("0.00")


def test_mobilecommerce_mass_assignment_location_rule(auth_client_a, tenant_a, tenant_b):
    """Submitting foreign tenant or system number in payload cannot reassign tenant or override number."""
    payload = _mobilecommerce_valid_locationrule_post_data(
        name="MassAssignLocationRule",
        tenant=tenant_b.pk,
        number="MALICIOUS-MLR-999",
    )
    url = reverse("ecommerce:mobilelocationrule_create")
    resp = auth_client_a.post(url, payload)
    assert resp.status_code == 302

    created_rule = MobileLocationRule.objects.get(name="MassAssignLocationRule")
    assert created_rule.tenant == tenant_a
    assert created_rule.number.startswith("EMLR-")
    assert created_rule.number != "MALICIOUS-MLR-999"


# ==============================================================================
# 5. Negative Input & Injection Hardening Tests
# ==============================================================================

def test_mobilecommerce_ping_negative_and_non_finite_coordinates(auth_client_a, ecom_mobile_device_a):
    """Telemetry ping endpoint handles non-finite (NaN, inf) and out-of-range floats gracefully without 500 crash."""
    url = reverse("ecommerce:mobiledeviceregistration_ping", args=[ecom_mobile_device_a.pk])
    initial_lat = ecom_mobile_device_a.last_latitude
    initial_lng = ecom_mobile_device_a.last_longitude

    negative_payloads = [
        {"lat": "NaN", "lng": "Infinity"},
        {"lat": "-inf", "lng": "inf"},
        {"lat": "999.0", "lng": "-999.0"},
        {"lat": "-91.0", "lng": "180.0"},
        {"lat": "45.0", "lng": "181.0"},
        {"lat": "invalid_number", "lng": "corrupted"},
        {"lat": "1e9999", "lng": "-1e9999"},
    ]

    for payload in negative_payloads:
        resp = auth_client_a.post(url, payload)
        assert resp.status_code == 302, f"Failed for payload {payload}: returned {resp.status_code}"
        ecom_mobile_device_a.refresh_from_db()
        # Device coordinates should not be updated to invalid/out-of-range numbers
        assert ecom_mobile_device_a.last_latitude == initial_lat
        assert ecom_mobile_device_a.last_longitude == initial_lng

    # Valid coordinates update properly
    valid_resp = auth_client_a.post(url, {"lat": "37.774929", "lng": "-122.419416"})
    assert valid_resp.status_code == 302
    ecom_mobile_device_a.refresh_from_db()
    assert str(ecom_mobile_device_a.last_latitude) == "37.774929"
    assert str(ecom_mobile_device_a.last_longitude) == "-122.419416"


def test_mobilecommerce_location_simulate_negative_and_non_finite_coordinates(auth_client_a, ecom_mobile_location_a):
    """Geofence simulation handles non-finite (NaN, inf) and out-of-range floats gracefully without 500 crash."""
    url = reverse("ecommerce:mobilelocationrule_simulate", args=[ecom_mobile_location_a.pk])

    negative_payloads = [
        {"test_lat": "NaN", "test_lng": "Infinity"},
        {"test_lat": "-inf", "test_lng": "inf"},
        {"test_lat": "180.0", "test_lng": "-300.0"},
        {"test_lat": "not_a_number", "test_lng": "invalid_coords"},
        {"test_lat": "", "test_lng": ""},
    ]

    for payload in negative_payloads:
        resp = auth_client_a.post(url, payload)
        assert resp.status_code == 302, f"Simulation crashed on payload {payload} with status {resp.status_code}"

    # Valid simulation executes and redirects cleanly
    valid_resp = auth_client_a.post(url, {"test_lat": "40.712776", "test_lng": "-74.005974"})
    assert valid_resp.status_code == 302


def test_mobilecommerce_color_css_injection_hardening(auth_client_a):
    """Form validation rejects CSS and script injection strings in hex color inputs."""
    url = reverse("ecommerce:mobileappconfig_create")

    malicious_colors = [
        "red; behavior:url(xss.htc);",
        "<script>alert('xss')</script>",
        "javascript:alert(1)",
        "expression(alert(1))",
        "#GGGGGG",
        "#12345",
        "#1234567",
        "rgb(255,0,0)",
        '"><script>alert(1)</script>',
    ]

    for idx, bad_color in enumerate(malicious_colors):
        payload = _mobilecommerce_valid_appconfig_post_data(
            short_name=f"ColorSec{idx}",
            theme_color=bad_color,
        )
        resp = auth_client_a.post(url, payload)
        assert resp.status_code == 200, f"Expected 200 with form errors for color '{bad_color}'"
        assert "theme_color" in resp.context["form"].errors


def test_mobilecommerce_xss_auto_escaping_in_templates(
    auth_client_a,
    tenant_a,
    ecom_center_a,
):
    """Ensure HTML and script injection in entity names are safely escaped in rendered HTML templates."""
    xss_payload = "<script>alert('nav_sec_xss')</script>"

    # 1. Config with script tags in app_name
    config = _mobilecommerce_app_config(
        tenant_a,
        short_name="XSSConfig",
        app_name=f"PWA Store {xss_payload}",
    )
    resp_config = auth_client_a.get(reverse("ecommerce:mobileappconfig_detail", args=[config.pk]))
    assert resp_config.status_code == 200
    html_config = resp_config.content.decode("utf-8")
    assert "<script>alert('nav_sec_xss')</script>" not in html_config
    assert "&lt;script&gt;alert(&#x27;nav_sec_xss&#x27;)&lt;/script&gt;" in html_config or "&lt;script&gt;" in html_config

    # 2. Push campaign with script tags in notification title
    push = _mobilecommerce_push_campaign(
        tenant_a,
        campaign_name="XSSPushCampaign",
        notification_title=f"Urgent Flash {xss_payload}",
    )
    resp_push = auth_client_a.get(reverse("ecommerce:mobilepushcampaign_detail", args=[push.pk]))
    assert resp_push.status_code == 200
    html_push = resp_push.content.decode("utf-8")
    assert "<script>alert('nav_sec_xss')</script>" not in html_push
    assert "&lt;script&gt;" in html_push

    # 3. Location rule with script tags in store_name
    loc = _mobilecommerce_location_rule(
        tenant_a,
        fulfillment_center=ecom_center_a,
        name="XSSLocationRule",
        store_name=f"Flagship {xss_payload}",
    )
    resp_loc = auth_client_a.get(reverse("ecommerce:mobilelocationrule_detail", args=[loc.pk]))
    assert resp_loc.status_code == 200
    html_loc = resp_loc.content.decode("utf-8")
    assert "<script>alert('nav_sec_xss')</script>" not in html_loc
    assert "&lt;script&gt;" in html_loc


# ==============================================================================
# 6. Public Manifest Scoping Tests
# ==============================================================================

def test_mobilecommerce_manifest_public_anonymous_access(client):
    """Web App Manifest endpoint is publicly accessible without login and returns application/manifest+json."""
    url = reverse("ecommerce:pwa_manifest_json")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/manifest+json"

    data = json.loads(resp.content)
    assert "name" in data
    assert "short_name" in data
    assert "icons" in data


def test_mobilecommerce_manifest_tenant_scoping(
    auth_client_a,
    auth_client_b,
    ecom_mobile_config_a,
    ecom_mobile_config_b,
):
    """PWA Manifest endpoint is strictly tenant-scoped to the active request tenant."""
    url = reverse("ecommerce:pwa_manifest_json")

    # Tenant A request
    resp_a = auth_client_a.get(url)
    assert resp_a.status_code == 200
    data_a = json.loads(resp_a.content)
    assert data_a["short_name"] == ecom_mobile_config_a.short_name
    assert data_a["name"] == ecom_mobile_config_a.app_name

    # Tenant B request
    resp_b = auth_client_b.get(url)
    assert resp_b.status_code == 200
    data_b = json.loads(resp_b.content)
    assert data_b["short_name"] == ecom_mobile_config_b.short_name
    assert data_b["name"] == ecom_mobile_config_b.app_name

    # Cross-tenant separation check
    assert data_a["short_name"] != data_b["short_name"]


def test_mobilecommerce_manifest_respects_enable_pwa_flag(auth_client_a, ecom_mobile_config_a):
    """When enable_pwa or is_active is False, manifest falls back to default storefront metadata."""
    url = reverse("ecommerce:pwa_manifest_json")

    # 1. When enable_pwa is False
    ecom_mobile_config_a.enable_pwa = False
    ecom_mobile_config_a.save()

    resp_disabled = auth_client_a.get(url)
    assert resp_disabled.status_code == 200
    data_disabled = json.loads(resp_disabled.content)
    assert data_disabled["name"] == "NavERP Mobile Store"
    assert data_disabled["short_name"] == "NavERP Store"

    # 2. When is_active is False
    ecom_mobile_config_a.enable_pwa = True
    ecom_mobile_config_a.is_active = False
    ecom_mobile_config_a.save()

    resp_inactive = auth_client_a.get(url)
    assert resp_inactive.status_code == 200
    data_inactive = json.loads(resp_inactive.content)
    assert data_inactive["name"] == "NavERP Mobile Store"
    assert data_inactive["short_name"] == "NavERP Store"


def test_mobilecommerce_manifest_no_payment_secrets_leaked(auth_client_a, tenant_a):
    """Public PWA manifest JSON never leaks internal payment gateway secrets or sensitive keys."""
    # Create an active PWA config with sensitive merchant IDs
    config = _mobilecommerce_app_config(
        tenant_a,
        short_name="SecSecretPWA",
        enable_pwa=True,
        is_active=True,
        apple_pay_merchant_id="merchant.secret.vault.8888",
        google_pay_gateway_id="gateway-secret-token-9999",
        offline_fallback_html="<!-- internal debug diagnostics -->",
    )
    url = reverse("ecommerce:pwa_manifest_json")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200

    content_str = resp.content.decode("utf-8")
    assert "merchant.secret.vault.8888" not in content_str
    assert "gateway-secret-token-9999" not in content_str
    assert "offline_fallback_html" not in content_str
    assert "internal debug diagnostics" not in content_str

    manifest_dict = json.loads(content_str)
    # Manifest schema should contain only standard PWA keys
    allowed_keys = {
        "name", "short_name", "description", "start_url",
        "scope", "display", "orientation", "theme_color",
        "background_color", "icons",
    }
    assert set(manifest_dict.keys()).issubset(allowed_keys)


# ==============================================================================
# 7. Audit Log Forensics Tests
# ==============================================================================

def test_mobilecommerce_audit_log_appconfig_lifecycle(auth_client_a, tenant_a, admin_user):
    """AuditLog records CREATE, UPDATE, and DELETE operations for MobileAppConfig."""
    # 1. CREATE
    create_url = reverse("ecommerce:mobileappconfig_create")
    post_data = _mobilecommerce_valid_appconfig_post_data(short_name="AuditAppConfig")
    resp_create = auth_client_a.post(create_url, post_data)
    assert resp_create.status_code == 302

    config = MobileAppConfig.objects.get(short_name="AuditAppConfig")
    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="CREATE",
        object_id=config.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("name") == "AuditAppConfig"

    # 2. UPDATE
    edit_url = reverse("ecommerce:mobileappconfig_edit", args=[config.pk])
    post_data["short_name"] = "AuditAppConfigUpdated"
    resp_edit = auth_client_a.post(edit_url, post_data)
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="UPDATE",
        object_id=config.pk,
    ).first()
    assert log_update is not None
    assert log_update.changes.get("name") == "AuditAppConfigUpdated"

    # 3. DELETE
    config_num = config.number
    delete_url = reverse("ecommerce:mobileappconfig_delete", args=[config.pk])
    resp_delete = auth_client_a.post(delete_url)
    assert resp_delete.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="DELETE",
        changes__number=config_num,
    ).first()
    assert log_delete is not None


def test_mobilecommerce_audit_log_device_lifecycle(auth_client_a, tenant_a, admin_user):
    """AuditLog records CREATE, UPDATE, and DELETE operations for MobileDeviceRegistration."""
    # 1. CREATE
    dev_uuid = str(uuid.uuid4())
    create_url = reverse("ecommerce:mobiledeviceregistration_create")
    post_data = _mobilecommerce_valid_device_post_data(device_uuid=dev_uuid)
    resp_create = auth_client_a.post(create_url, post_data)
    assert resp_create.status_code == 302

    device = MobileDeviceRegistration.objects.get(device_uuid=dev_uuid)
    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="CREATE",
        object_id=device.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("uuid") == dev_uuid

    # 2. UPDATE
    edit_url = reverse("ecommerce:mobiledeviceregistration_edit", args=[device.pk])
    post_data["device_model"] = "iPhone 16 Pro Max Audit"
    resp_edit = auth_client_a.post(edit_url, post_data)
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="UPDATE",
        object_id=device.pk,
    ).first()
    assert log_update is not None

    # 3. DELETE
    dev_num = device.number
    delete_url = reverse("ecommerce:mobiledeviceregistration_delete", args=[device.pk])
    resp_delete = auth_client_a.post(delete_url)
    assert resp_delete.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="DELETE",
        changes__number=dev_num,
    ).first()
    assert log_delete is not None


def test_mobilecommerce_audit_log_pushcampaign_lifecycle_and_send(
    auth_client_a,
    tenant_a,
    admin_user,
    ecom_mobile_device_a,
):
    """AuditLog records CREATE, UPDATE, SEND, and DELETE operations for MobilePushCampaign."""
    # 1. CREATE
    create_url = reverse("ecommerce:mobilepushcampaign_create")
    post_data = _mobilecommerce_valid_pushcampaign_post_data(campaign_name="AuditPushCampaign")
    resp_create = auth_client_a.post(create_url, post_data)
    assert resp_create.status_code == 302

    campaign = MobilePushCampaign.objects.get(campaign_name="AuditPushCampaign")
    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="CREATE",
        object_id=campaign.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("name") == "AuditPushCampaign"

    # 2. UPDATE
    edit_url = reverse("ecommerce:mobilepushcampaign_edit", args=[campaign.pk])
    post_data["campaign_name"] = "AuditPushCampaignUpdated"
    resp_edit = auth_client_a.post(edit_url, post_data)
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="UPDATE",
        object_id=campaign.pk,
    ).first()
    assert log_update is not None

    # 3. SEND Action
    send_url = reverse("ecommerce:mobilepushcampaign_test_send", args=[campaign.pk])
    resp_send = auth_client_a.post(send_url)
    assert resp_send.status_code == 302

    log_send = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="SEND",
        object_id=campaign.pk,
    ).first()
    assert log_send is not None
    assert "dispatched_count" in log_send.changes

    # 4. DELETE
    camp_num = campaign.number
    delete_url = reverse("ecommerce:mobilepushcampaign_delete", args=[campaign.pk])
    resp_delete = auth_client_a.post(delete_url)
    assert resp_delete.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="DELETE",
        changes__number=camp_num,
    ).first()
    assert log_delete is not None


def test_mobilecommerce_audit_log_locationrule_lifecycle(auth_client_a, tenant_a, admin_user):
    """AuditLog records CREATE, UPDATE, and DELETE operations for MobileLocationRule."""
    # 1. CREATE
    create_url = reverse("ecommerce:mobilelocationrule_create")
    post_data = _mobilecommerce_valid_locationrule_post_data(name="AuditLocationRule")
    resp_create = auth_client_a.post(create_url, post_data)
    assert resp_create.status_code == 302

    rule = MobileLocationRule.objects.get(name="AuditLocationRule")
    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="CREATE",
        object_id=rule.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("name") == "AuditLocationRule"

    # 2. UPDATE
    edit_url = reverse("ecommerce:mobilelocationrule_edit", args=[rule.pk])
    post_data["name"] = "AuditLocationRuleUpdated"
    resp_edit = auth_client_a.post(edit_url, post_data)
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="UPDATE",
        object_id=rule.pk,
    ).first()
    assert log_update is not None

    # 3. DELETE
    rule_num = rule.number
    delete_url = reverse("ecommerce:mobilelocationrule_delete", args=[rule.pk])
    resp_delete = auth_client_a.post(delete_url)
    assert resp_delete.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="DELETE",
        changes__number=rule_num,
    ).first()
    assert log_delete is not None


def test_mobilecommerce_audit_log_tenant_isolation(auth_client_a, tenant_a, tenant_b, admin_user):
    """Mutating operations performed in Tenant A never generate audit records in Tenant B."""
    initial_b_count = AuditLog.objects.filter(tenant=tenant_b).count()

    # Perform mutations in Tenant A
    post_config = _mobilecommerce_valid_appconfig_post_data(short_name="TenantIsoConfig")
    auth_client_a.post(reverse("ecommerce:mobileappconfig_create"), post_config)

    post_device = _mobilecommerce_valid_device_post_data(device_uuid=str(uuid.uuid4()))
    auth_client_a.post(reverse("ecommerce:mobiledeviceregistration_create"), post_device)

    post_push = _mobilecommerce_valid_pushcampaign_post_data(campaign_name="TenantIsoPush")
    auth_client_a.post(reverse("ecommerce:mobilepushcampaign_create"), post_push)

    post_loc = _mobilecommerce_valid_locationrule_post_data(name="TenantIsoLoc")
    auth_client_a.post(reverse("ecommerce:mobilelocationrule_create"), post_loc)

    final_b_count = AuditLog.objects.filter(tenant=tenant_b).count()
    assert final_b_count == initial_b_count, "AuditLog for Tenant B must not increase during Tenant A actions."
