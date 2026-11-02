"""Comprehensive unit, route, context-contract, filter, and action tests for eCommerce 9.16 Mobile Commerce views.

Covers:
- Mobile Hub Cockpit (`mobile_hub`): KPI aggregates, platform breakdowns, recent feeds, PWA/wallet flags.
- MobileAppConfig CRUD + PWA Web App Manifest endpoint (`pwa_manifest_json`).
- MobileDeviceRegistration CRUD + Telemetry Ping endpoint (`mobiledeviceregistration_ping`).
- MobilePushCampaign CRUD + Dispatch simulation action (`mobilepushcampaign_test_send`) with status guards.
- MobileLocationRule CRUD + Geofence simulation action (`mobilelocationrule_simulate`) with coordinate boundary validation.
- Tenant isolation and IDOR cross-tenant access prevention.

Conventions enforced:
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

from apps.core.models import AuditLog
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
        "app_name": "NavERP Mobile Storefront",
        "short_name": "NavStore",
        "description": "Progressive Web App and mobile customer experience.",
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
        "apple_pay_merchant_id": "merchant.com.example.store",
        "google_pay_gateway_id": "gateway-acme-123",
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
        "campaign_name": "Summer Flash Sale Push",
        "campaign_type": "promotional",
        "target_platform": "all",
        "notification_title": "Exclusive Flash Sale Today!",
        "notification_body": "Use code SUMMER20 for 20% off all catalog items.",
        "image_url": "https://cdn.example.com/promos/summer.jpg",
        "badge_increment": 1,
        "sound_name": "default",
        "deep_link_type": "product",
        "deep_link_url": "navstore://products/123",
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
        "name": "Downtown Flagship Geofence",
        "rule_type": "geofence_entry",
        "fulfillment_center": center.pk if center else "",
        "store_name": "Acme Downtown Flagship",
        "latitude": "40.712776",
        "longitude": "-74.005974",
        "radius_meters": 300,
        "trigger_action": "apply_coupon",
        "linked_promotion": promotion.pk if promotion else "",
        "push_message": "Welcome to our Flagship store! Check in for express pickup.",
        "enable_bopis_checkin": True,
        "enable_instore_mode": True,
        "dwell_time_seconds": 90,
        "is_active": True,
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. Mobile Hub Cockpit Tests
# ==============================================================================

def test_mobilecommerce_hub_view_success(
    auth_client_a,
    tenant_a,
    ecom_mobile_config_a,
    ecom_mobile_device_a,
    ecom_mobile_push_a,
    ecom_mobile_location_a,
):
    """Test mobile commerce cockpit returns 200 with all required context keys and correct metrics."""
    # Create additional devices to verify platform breakdown
    _mobilecommerce_device_registration(
        tenant_a,
        device_uuid=str(uuid.uuid4()),
        device_platform="android",
        push_provider="fcm",
    )
    _mobilecommerce_device_registration(
        tenant_a,
        device_uuid=str(uuid.uuid4()),
        device_platform="pwa_web",
        push_provider="web_push",
    )

    url = reverse("ecommerce:mobile_hub")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200

    required_keys = [
        "app_config",
        "total_devices",
        "ios_devices",
        "android_devices",
        "pwa_devices",
        "active_campaigns",
        "total_push_sent",
        "total_push_opened",
        "total_push_revenue",
        "active_geofences",
        "pwa_enabled",
        "apple_pay_enabled",
        "google_pay_enabled",
        "recent_devices",
        "recent_campaigns",
        "recent_locations",
    ]
    for key in required_keys:
        assert key in resp.context, f"Missing context key '{key}' in mobile_hub"

    assert resp.context["app_config"] == ecom_mobile_config_a
    assert resp.context["total_devices"] >= 3
    assert resp.context["ios_devices"] >= 1
    assert resp.context["android_devices"] >= 1
    assert resp.context["pwa_devices"] >= 1
    assert resp.context["pwa_enabled"] is True
    assert resp.context["apple_pay_enabled"] is True
    assert resp.context["google_pay_enabled"] is True
    assert resp.context["active_geofences"] >= 1


def test_mobilecommerce_hub_view_empty_tenant(auth_client_b, tenant_b):
    """Test mobile commerce cockpit with empty tenant gracefully defaults context values."""
    url = reverse("ecommerce:mobile_hub")
    resp = auth_client_b.get(url)
    assert resp.status_code == 200
    assert resp.context["app_config"] is None
    assert resp.context["total_devices"] == 0
    assert resp.context["ios_devices"] == 0
    assert resp.context["android_devices"] == 0
    assert resp.context["pwa_devices"] == 0
    assert resp.context["active_campaigns"] == 0
    assert resp.context["total_push_sent"] == 0
    assert resp.context["active_geofences"] == 0
    assert resp.context["pwa_enabled"] is False
    assert resp.context["apple_pay_enabled"] is False
    assert resp.context["google_pay_enabled"] is False


def test_mobilecommerce_hub_unauthenticated_redirect(client):
    """Test unauthenticated request to mobile hub redirects to login."""
    url = reverse("ecommerce:mobile_hub")
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/login" in resp.url or "accounts/login" in resp.url


# ==============================================================================
# 2. MobileAppConfig View Tests
# ==============================================================================

def test_mobilecommerce_appconfig_list_view_and_context(auth_client_a, ecom_mobile_config_a):
    """Test MobileAppConfig list view context keys and pagination contract."""
    url = reverse("ecommerce:mobileappconfig_list")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200

    required_keys = [
        "configs",
        "page_obj",
        "paginator",
        "is_paginated",
        "total_count",
        "active_count",
        "pwa_count",
        "q",
        "selected_is_active",
        "selected_enable_pwa",
    ]
    for key in required_keys:
        assert key in resp.context, f"Missing context key '{key}' in mobileappconfig_list"

    assert ecom_mobile_config_a in resp.context["configs"]
    assert resp.context["total_count"] >= 1


def test_mobilecommerce_appconfig_list_search_and_filters(auth_client_a, tenant_a):
    """Test MobileAppConfig list filtering by q search, is_active, and enable_pwa."""
    c1 = _mobilecommerce_app_config(
        tenant_a,
        short_name="SearchTargetApp",
        app_name="Unique Search App Name",
        is_active=True,
        enable_pwa=True,
    )
    c2 = _mobilecommerce_app_config(
        tenant_a,
        short_name="InactiveNativeOnly",
        app_name="Native App Inactive",
        is_active=False,
        enable_pwa=False,
    )

    url = reverse("ecommerce:mobileappconfig_list")

    # Search query
    resp_q = auth_client_a.get(url, {"q": "SearchTargetApp"})
    assert resp_q.status_code == 200
    assert c1 in resp_q.context["configs"]
    assert c2 not in resp_q.context["configs"]

    # Filter is_active=0
    resp_inact = auth_client_a.get(url, {"is_active": "0"})
    assert resp_inact.status_code == 200
    assert c2 in resp_inact.context["configs"]
    assert c1 not in resp_inact.context["configs"]

    # Filter enable_pwa=1
    resp_pwa = auth_client_a.get(url, {"enable_pwa": "1"})
    assert resp_pwa.status_code == 200
    assert c1 in resp_pwa.context["configs"]
    assert c2 not in resp_pwa.context["configs"]


def test_mobilecommerce_appconfig_detail_view(auth_client_a, ecom_mobile_config_a):
    """Test MobileAppConfig detail view returns 200, object, and manifest JSON string."""
    url = reverse("ecommerce:mobileappconfig_detail", kwargs={"pk": ecom_mobile_config_a.pk})
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["config"] == ecom_mobile_config_a
    assert resp.context["object"] == ecom_mobile_config_a
    assert "manifest_json_str" in resp.context
    parsed = json.loads(resp.context["manifest_json_str"])
    assert parsed["short_name"] == ecom_mobile_config_a.short_name


def test_mobilecommerce_appconfig_create_view_get_and_post(auth_client_a, tenant_a):
    """Test MobileAppConfig creation GET and valid POST redirect to detail, setting tenant."""
    url = reverse("ecommerce:mobileappconfig_create")

    # GET form
    resp_get = auth_client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    # POST valid payload
    post_data = _mobilecommerce_valid_appconfig_post_data(short_name="CreatedApp", app_name="Created App Name")
    resp_post = auth_client_a.post(url, data=post_data)
    assert resp_post.status_code == 302

    created = MobileAppConfig.objects.filter(tenant=tenant_a, short_name="CreatedApp").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert resp_post.url == reverse("ecommerce:mobileappconfig_detail", kwargs={"pk": created.pk})

    # Verify audit log recorded
    audit = AuditLog.objects.filter(tenant=tenant_a, action="CREATE", object_id=created.pk).first()
    assert audit is not None


def test_mobilecommerce_appconfig_create_invalid(auth_client_a):
    """Test MobileAppConfig creation with invalid hex color returns 200 with form errors."""
    url = reverse("ecommerce:mobileappconfig_create")
    post_data = _mobilecommerce_valid_appconfig_post_data(theme_color="invalid-color-not-hex")
    resp = auth_client_a.post(url, data=post_data)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert not resp.context["form"].is_valid()
    assert "theme_color" in resp.context["form"].errors


def test_mobilecommerce_appconfig_edit_view(auth_client_a, tenant_a, ecom_mobile_config_a):
    """Test MobileAppConfig edit GET and POST updates record and logs audit entry."""
    url = reverse("ecommerce:mobileappconfig_edit", kwargs={"pk": ecom_mobile_config_a.pk})

    resp_get = auth_client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["config"] == ecom_mobile_config_a

    edit_data = _mobilecommerce_valid_appconfig_post_data(
        short_name=ecom_mobile_config_a.short_name,
        app_name="Updated App Name",
        description="Updated mobile app description",
    )
    resp_post = auth_client_a.post(url, data=edit_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("ecommerce:mobileappconfig_detail", kwargs={"pk": ecom_mobile_config_a.pk})

    ecom_mobile_config_a.refresh_from_db()
    assert ecom_mobile_config_a.app_name == "Updated App Name"
    assert ecom_mobile_config_a.description == "Updated mobile app description"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="UPDATE", object_id=ecom_mobile_config_a.pk).first()
    assert audit is not None


def test_mobilecommerce_appconfig_delete_view(auth_client_a, tenant_a):
    """Test MobileAppConfig delete via POST removes record, writes audit log, redirects to list."""
    config = _mobilecommerce_app_config(tenant_a, short_name="ToDeleteApp", app_name="To Delete App")
    pk = config.pk
    url = reverse("ecommerce:mobileappconfig_delete", kwargs={"pk": pk})

    # GET is rejected with 405 by require_POST
    resp_get = auth_client_a.get(url)
    assert resp_get.status_code == 405

    # POST deletes
    resp_post = auth_client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("ecommerce:mobileappconfig_list")
    assert not MobileAppConfig.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="DELETE", object_id=pk).first()
    assert audit is not None


def test_mobilecommerce_pwa_manifest_json_endpoint(auth_client_a, tenant_a, ecom_mobile_config_a):
    """Test PWA web manifest JSON endpoint returns valid application/manifest+json."""
    url = reverse("ecommerce:pwa_manifest_json")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/manifest+json"

    data = json.loads(resp.content)
    assert data["short_name"] == ecom_mobile_config_a.short_name
    assert data["name"] == ecom_mobile_config_a.app_name
    assert data["theme_color"] == ecom_mobile_config_a.theme_color
    assert "icons" in data


def test_mobilecommerce_pwa_manifest_json_fallback(client):
    """Test PWA web manifest JSON fallback when accessed with no tenant/config."""
    url = reverse("ecommerce:pwa_manifest_json")
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp["Content-Type"] == "application/manifest+json"

    data = json.loads(resp.content)
    assert data["name"] == "NavERP Mobile Store"
    assert data["short_name"] == "NavERP Store"


# ==============================================================================
# 3. MobileDeviceRegistration View Tests
# ==============================================================================

def test_mobilecommerce_device_list_view_and_context(auth_client_a, ecom_mobile_device_a):
    """Test MobileDeviceRegistration list view context keys and choices contract."""
    url = reverse("ecommerce:mobiledeviceregistration_list")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200

    required_keys = [
        "devices",
        "page_obj",
        "paginator",
        "is_paginated",
        "platform_choices",
        "provider_choices",
        "selected_platform",
        "selected_provider",
        "selected_status",
        "total_count",
        "ios_count",
        "android_count",
        "pwa_count",
        "q",
    ]
    for key in required_keys:
        assert key in resp.context, f"Missing context key '{key}' in mobiledeviceregistration_list"

    assert ecom_mobile_device_a in resp.context["devices"]
    assert resp.context["total_count"] >= 1


def test_mobilecommerce_device_list_filters_and_search(auth_client_a, tenant_a):
    """Test MobileDeviceRegistration list filters by platform, provider, is_active, and search q."""
    dev_ios = _mobilecommerce_device_registration(
        tenant_a,
        device_uuid="aaaaaaaa-1111-2222-3333-444444444444",
        device_platform="ios",
        push_provider="apns",
        device_model="UniqueModelAlpha",
        is_active=True,
    )
    dev_android = _mobilecommerce_device_registration(
        tenant_a,
        device_uuid="bbbbbbbb-1111-2222-3333-444444444444",
        device_platform="android",
        push_provider="fcm",
        device_model="UniqueModelBeta",
        is_active=False,
    )

    url = reverse("ecommerce:mobiledeviceregistration_list")

    # Search q
    resp_q = auth_client_a.get(url, {"q": "UniqueModelAlpha"})
    assert resp_q.status_code == 200
    assert dev_ios in resp_q.context["devices"]
    assert dev_android not in resp_q.context["devices"]

    # Filter platform
    resp_plat = auth_client_a.get(url, {"platform": "android"})
    assert resp_plat.status_code == 200
    assert dev_android in resp_plat.context["devices"]
    assert dev_ios not in resp_plat.context["devices"]

    # Filter provider
    resp_prov = auth_client_a.get(url, {"provider": "fcm"})
    assert resp_prov.status_code == 200
    assert dev_android in resp_prov.context["devices"]
    assert dev_ios not in resp_prov.context["devices"]

    # Filter status
    resp_stat = auth_client_a.get(url, {"is_active": "0"})
    assert resp_stat.status_code == 200
    assert dev_android in resp_stat.context["devices"]
    assert dev_ios not in resp_stat.context["devices"]


def test_mobilecommerce_device_detail_view(auth_client_a, ecom_mobile_device_a):
    """Test MobileDeviceRegistration detail view returns 200 and device context."""
    url = reverse("ecommerce:mobiledeviceregistration_detail", kwargs={"pk": ecom_mobile_device_a.pk})
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["device"] == ecom_mobile_device_a
    assert resp.context["object"] == ecom_mobile_device_a


def test_mobilecommerce_device_create_view(auth_client_a, tenant_a):
    """Test MobileDeviceRegistration create GET and valid POST setting tenant and last_active_at."""
    url = reverse("ecommerce:mobiledeviceregistration_create")

    resp_get = auth_client_a.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    target_uuid = str(uuid.uuid4())
    post_data = _mobilecommerce_valid_device_post_data(device_uuid=target_uuid, device_model="Pixel 9 Pro")
    resp_post = auth_client_a.post(url, data=post_data)
    assert resp_post.status_code == 302

    created = MobileDeviceRegistration.objects.filter(tenant=tenant_a, device_uuid=target_uuid).first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.last_active_at is not None
    assert resp_post.url == reverse("ecommerce:mobiledeviceregistration_detail", kwargs={"pk": created.pk})

    audit = AuditLog.objects.filter(tenant=tenant_a, action="CREATE", object_id=created.pk).first()
    assert audit is not None


def test_mobilecommerce_device_edit_view(auth_client_a, tenant_a, ecom_mobile_device_a):
    """Test MobileDeviceRegistration edit GET and POST updates device properties."""
    url = reverse("ecommerce:mobiledeviceregistration_edit", kwargs={"pk": ecom_mobile_device_a.pk})

    resp_get = auth_client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    edit_data = _mobilecommerce_valid_device_post_data(
        device_uuid=ecom_mobile_device_a.device_uuid,
        device_model="iPhone 16 Pro Max Upgraded",
        app_version="4.0.0",
    )
    resp_post = auth_client_a.post(url, data=edit_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("ecommerce:mobiledeviceregistration_detail", kwargs={"pk": ecom_mobile_device_a.pk})

    ecom_mobile_device_a.refresh_from_db()
    assert ecom_mobile_device_a.device_model == "iPhone 16 Pro Max Upgraded"
    assert ecom_mobile_device_a.app_version == "4.0.0"

    audit = AuditLog.objects.filter(tenant=tenant_a, action="UPDATE", object_id=ecom_mobile_device_a.pk).first()
    assert audit is not None


def test_mobilecommerce_device_delete_view(auth_client_a, tenant_a):
    """Test MobileDeviceRegistration delete via POST removes record and writes audit log."""
    dev = _mobilecommerce_device_registration(tenant_a, device_uuid=str(uuid.uuid4()))
    pk = dev.pk
    url = reverse("ecommerce:mobiledeviceregistration_delete", kwargs={"pk": pk})

    resp_post = auth_client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("ecommerce:mobiledeviceregistration_list")
    assert not MobileDeviceRegistration.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="DELETE", object_id=pk).first()
    assert audit is not None


def test_mobilecommerce_device_ping_valid_coordinates(auth_client_a, ecom_mobile_device_a):
    """Test telemetry ping action updates device coordinates and last_active_at timestamp."""
    url = reverse("ecommerce:mobiledeviceregistration_ping", kwargs={"pk": ecom_mobile_device_a.pk})
    old_active = ecom_mobile_device_a.last_active_at

    ping_data = {"lat": "40.712800", "lng": "-74.006000"}
    resp = auth_client_a.post(url, data=ping_data, follow=True)
    assert resp.status_code == 200

    ecom_mobile_device_a.refresh_from_db()
    assert ecom_mobile_device_a.last_latitude == Decimal("40.712800")
    assert ecom_mobile_device_a.last_longitude == Decimal("-74.006000")
    if old_active:
        assert ecom_mobile_device_a.last_active_at >= old_active


def test_mobilecommerce_device_ping_invalid_and_nonfinite_coordinates(auth_client_a, ecom_mobile_device_a):
    """Test telemetry ping action handles non-finite, out-of-range, and non-numeric inputs gracefully without 500."""
    url = reverse("ecommerce:mobiledeviceregistration_ping", kwargs={"pk": ecom_mobile_device_a.pk})

    # Out of range coordinates
    resp1 = auth_client_a.post(url, data={"lat": "150.0", "lng": "250.0"}, follow=True)
    assert resp1.status_code == 200
    messages1 = [m.message for m in resp1.context["messages"]]
    assert any("Coordinates must be within" in m for m in messages1)

    # Non-numeric / NaN input
    resp2 = auth_client_a.post(url, data={"lat": "invalid_val", "lng": "nan"}, follow=True)
    assert resp2.status_code == 200
    messages2 = [m.message for m in resp2.context["messages"]]
    assert any("Invalid numeric coordinates" in m for m in messages2)

    # Empty payload
    resp3 = auth_client_a.post(url, data={}, follow=True)
    assert resp3.status_code == 200


# ==============================================================================
# 4. MobilePushCampaign View Tests
# ==============================================================================

def test_mobilecommerce_pushcampaign_list_view_and_context(auth_client_a, ecom_mobile_push_a):
    """Test MobilePushCampaign list view context keys and aggregation contract."""
    url = reverse("ecommerce:mobilepushcampaign_list")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200

    required_keys = [
        "campaigns",
        "page_obj",
        "paginator",
        "is_paginated",
        "status_choices",
        "type_choices",
        "platform_choices",
        "selected_status",
        "selected_type",
        "selected_platform",
        "total_count",
        "sent_count",
        "draft_count",
        "q",
    ]
    for key in required_keys:
        assert key in resp.context, f"Missing context key '{key}' in mobilepushcampaign_list"

    assert ecom_mobile_push_a in resp.context["campaigns"]
    assert resp.context["total_count"] >= 1


def test_mobilecommerce_pushcampaign_list_filters_and_search(auth_client_a, tenant_a):
    """Test MobilePushCampaign list filtering by status, campaign_type, target_platform, and search q."""
    c_sent = _mobilecommerce_push_campaign(
        tenant_a,
        campaign_name="TargetPushAlpha",
        status="sent",
        campaign_type="cart_abandonment",
        target_platform="ios_only",
        notification_title="Cart Abandonment Headline",
    )
    c_draft = _mobilecommerce_push_campaign(
        tenant_a,
        campaign_name="TargetPushBeta",
        status="draft",
        campaign_type="promotional",
        target_platform="android_only",
        notification_title="Draft Promotional Headline",
    )

    url = reverse("ecommerce:mobilepushcampaign_list")

    # Search q
    resp_q = auth_client_a.get(url, {"q": "TargetPushAlpha"})
    assert resp_q.status_code == 200
    assert c_sent in resp_q.context["campaigns"]
    assert c_draft not in resp_q.context["campaigns"]

    # Filter status
    resp_stat = auth_client_a.get(url, {"status": "sent"})
    assert resp_stat.status_code == 200
    assert c_sent in resp_stat.context["campaigns"]
    assert c_draft not in resp_stat.context["campaigns"]

    # Filter type
    resp_type = auth_client_a.get(url, {"type": "cart_abandonment"})
    assert resp_type.status_code == 200
    assert c_sent in resp_type.context["campaigns"]
    assert c_draft not in resp_type.context["campaigns"]

    # Filter platform
    resp_plat = auth_client_a.get(url, {"platform": "android_only"})
    assert resp_plat.status_code == 200
    assert c_draft in resp_plat.context["campaigns"]
    assert c_sent not in resp_plat.context["campaigns"]


def test_mobilecommerce_pushcampaign_detail_view(auth_client_a, ecom_mobile_push_a):
    """Test MobilePushCampaign detail view returns 200, object, open_rate_pct, and ctr_pct."""
    url = reverse("ecommerce:mobilepushcampaign_detail", kwargs={"pk": ecom_mobile_push_a.pk})
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["campaign"] == ecom_mobile_push_a
    assert resp.context["object"] == ecom_mobile_push_a
    assert "open_rate_pct" in resp.context
    assert "ctr_pct" in resp.context


def test_mobilecommerce_pushcampaign_create_view(auth_client_a, tenant_a, user_a):
    """Test MobilePushCampaign creation GET and POST assigns tenant and created_by."""
    url = reverse("ecommerce:mobilepushcampaign_create")

    resp_get = auth_client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False

    post_data = _mobilecommerce_valid_pushcampaign_post_data(campaign_name="New Created Push Campaign")
    resp_post = auth_client_a.post(url, data=post_data)
    assert resp_post.status_code == 302

    created = MobilePushCampaign.objects.filter(tenant=tenant_a, campaign_name="New Created Push Campaign").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.created_by == user_a
    assert resp_post.url == reverse("ecommerce:mobilepushcampaign_detail", kwargs={"pk": created.pk})

    audit = AuditLog.objects.filter(tenant=tenant_a, action="CREATE", object_id=created.pk).first()
    assert audit is not None


def test_mobilecommerce_pushcampaign_edit_view(auth_client_a, tenant_a, ecom_mobile_push_a):
    """Test MobilePushCampaign edit GET and POST updates campaign copy."""
    url = reverse("ecommerce:mobilepushcampaign_edit", kwargs={"pk": ecom_mobile_push_a.pk})

    resp_get = auth_client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    edit_data = _mobilecommerce_valid_pushcampaign_post_data(
        campaign_name=ecom_mobile_push_a.campaign_name,
        notification_title="Updated Notification Headline",
        notification_body="Updated notification body copy.",
    )
    resp_post = auth_client_a.post(url, data=edit_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("ecommerce:mobilepushcampaign_detail", kwargs={"pk": ecom_mobile_push_a.pk})

    ecom_mobile_push_a.refresh_from_db()
    assert ecom_mobile_push_a.notification_title == "Updated Notification Headline"
    assert ecom_mobile_push_a.notification_body == "Updated notification body copy."

    audit = AuditLog.objects.filter(tenant=tenant_a, action="UPDATE", object_id=ecom_mobile_push_a.pk).first()
    assert audit is not None


def test_mobilecommerce_pushcampaign_delete_view(auth_client_a, tenant_a):
    """Test MobilePushCampaign delete via POST removes record and writes audit log."""
    camp = _mobilecommerce_push_campaign(tenant_a, campaign_name="DeleteMePush")
    pk = camp.pk
    url = reverse("ecommerce:mobilepushcampaign_delete", kwargs={"pk": pk})

    resp_post = auth_client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("ecommerce:mobilepushcampaign_list")
    assert not MobilePushCampaign.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="DELETE", object_id=pk).first()
    assert audit is not None


def test_mobilecommerce_pushcampaign_test_send_success(auth_client_a, tenant_a, ecom_mobile_device_a):
    """Test test_send endpoint dispatches simulation, updates status to sent, and logs audit entry."""
    campaign = _mobilecommerce_push_campaign(tenant_a, status="draft", campaign_name="DispatchablePush")
    url = reverse("ecommerce:mobilepushcampaign_test_send", kwargs={"pk": campaign.pk})

    resp = auth_client_a.post(url, follow=True)
    assert resp.status_code == 200
    assert resp.redirect_chain[-1][0] == reverse("ecommerce:mobilepushcampaign_detail", kwargs={"pk": campaign.pk})

    campaign.refresh_from_db()
    assert campaign.status == "sent"
    assert campaign.sent_at is not None
    assert campaign.sent_count >= 1

    messages = [m.message for m in resp.context["messages"]]
    assert any("dispatched" in m for m in messages)

    audit = AuditLog.objects.filter(tenant=tenant_a, action="SEND", object_id=campaign.pk).first()
    assert audit is not None


def test_mobilecommerce_pushcampaign_test_send_cancelled_guard(auth_client_a, tenant_a):
    """Test test_send status guard blocks dispatch of cancelled campaign with flash message."""
    campaign = _mobilecommerce_push_campaign(tenant_a, status="cancelled", campaign_name="CancelledPush")
    url = reverse("ecommerce:mobilepushcampaign_test_send", kwargs={"pk": campaign.pk})

    resp = auth_client_a.post(url, follow=True)
    assert resp.status_code == 200

    campaign.refresh_from_db()
    assert campaign.status == "cancelled"
    assert campaign.sent_at is None
    assert campaign.sent_count == 0

    messages = [m.message for m in resp.context["messages"]]
    assert any("Cannot dispatch cancelled campaign" in m for m in messages)


# ==============================================================================
# 5. MobileLocationRule View Tests
# ==============================================================================

def test_mobilecommerce_locationrule_list_view_and_context(auth_client_a, ecom_mobile_location_a):
    """Test MobileLocationRule list view context keys and choices contract."""
    url = reverse("ecommerce:mobilelocationrule_list")
    resp = auth_client_a.get(url)
    assert resp.status_code == 200

    required_keys = [
        "location_rules",
        "page_obj",
        "paginator",
        "is_paginated",
        "type_choices",
        "action_choices",
        "selected_type",
        "selected_action",
        "selected_status",
        "total_count",
        "active_count",
        "q",
    ]
    for key in required_keys:
        assert key in resp.context, f"Missing context key '{key}' in mobilelocationrule_list"

    assert ecom_mobile_location_a in resp.context["location_rules"]
    assert resp.context["total_count"] >= 1


def test_mobilecommerce_locationrule_list_filters_and_search(auth_client_a, tenant_a):
    """Test MobileLocationRule list filters by rule_type, trigger_action, is_active, and search q."""
    r1 = _mobilecommerce_location_rule(
        tenant_a,
        name="Uptown Geofence Entry",
        store_name="Uptown Store Target",
        rule_type="geofence_entry",
        trigger_action="apply_coupon",
        is_active=True,
    )
    r2 = _mobilecommerce_location_rule(
        tenant_a,
        name="Airport Beacon Proximity",
        store_name="Airport Kiosk Target",
        rule_type="beacon_proximity",
        trigger_action="bopis_arrival_notify",
        is_active=False,
    )

    url = reverse("ecommerce:mobilelocationrule_list")

    # Search q
    resp_q = auth_client_a.get(url, {"q": "Uptown Store Target"})
    assert resp_q.status_code == 200
    assert r1 in resp_q.context["location_rules"]
    assert r2 not in resp_q.context["location_rules"]

    # Filter rule_type
    resp_type = auth_client_a.get(url, {"rule_type": "beacon_proximity"})
    assert resp_type.status_code == 200
    assert r2 in resp_type.context["location_rules"]
    assert r1 not in resp_type.context["location_rules"]

    # Filter trigger_action
    resp_act = auth_client_a.get(url, {"trigger_action": "apply_coupon"})
    assert resp_act.status_code == 200
    assert r1 in resp_act.context["location_rules"]
    assert r2 not in resp_act.context["location_rules"]

    # Filter status
    resp_stat = auth_client_a.get(url, {"is_active": "0"})
    assert resp_stat.status_code == 200
    assert r2 in resp_stat.context["location_rules"]
    assert r1 not in resp_stat.context["location_rules"]


def test_mobilecommerce_locationrule_detail_view(auth_client_a, ecom_mobile_location_a):
    """Test MobileLocationRule detail view returns 200, location_rule, and object context."""
    url = reverse("ecommerce:mobilelocationrule_detail", kwargs={"pk": ecom_mobile_location_a.pk})
    resp = auth_client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["location_rule"] == ecom_mobile_location_a
    assert resp.context["object"] == ecom_mobile_location_a


def test_mobilecommerce_locationrule_create_view(auth_client_a, tenant_a):
    """Test MobileLocationRule create GET and valid POST setting tenant."""
    url = reverse("ecommerce:mobilelocationrule_create")

    resp_get = auth_client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False

    post_data = _mobilecommerce_valid_locationrule_post_data(name="New Geofence Rule", radius_meters=500)
    resp_post = auth_client_a.post(url, data=post_data)
    assert resp_post.status_code == 302

    created = MobileLocationRule.objects.filter(tenant=tenant_a, name="New Geofence Rule").first()
    assert created is not None
    assert created.tenant == tenant_a
    assert created.radius_meters == 500
    assert resp_post.url == reverse("ecommerce:mobilelocationrule_detail", kwargs={"pk": created.pk})

    audit = AuditLog.objects.filter(tenant=tenant_a, action="CREATE", object_id=created.pk).first()
    assert audit is not None


def test_mobilecommerce_locationrule_edit_view(auth_client_a, tenant_a, ecom_mobile_location_a):
    """Test MobileLocationRule edit GET and POST updates rule properties."""
    url = reverse("ecommerce:mobilelocationrule_edit", kwargs={"pk": ecom_mobile_location_a.pk})

    resp_get = auth_client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True

    edit_data = _mobilecommerce_valid_locationrule_post_data(
        name=ecom_mobile_location_a.name,
        radius_meters=750,
        push_message="Updated geofence push notification.",
    )
    resp_post = auth_client_a.post(url, data=edit_data)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("ecommerce:mobilelocationrule_detail", kwargs={"pk": ecom_mobile_location_a.pk})

    ecom_mobile_location_a.refresh_from_db()
    assert ecom_mobile_location_a.radius_meters == 750
    assert ecom_mobile_location_a.push_message == "Updated geofence push notification."

    audit = AuditLog.objects.filter(tenant=tenant_a, action="UPDATE", object_id=ecom_mobile_location_a.pk).first()
    assert audit is not None


def test_mobilecommerce_locationrule_delete_view(auth_client_a, tenant_a):
    """Test MobileLocationRule delete via POST removes record and writes audit log."""
    rule = _mobilecommerce_location_rule(tenant_a, name="RuleToDelete")
    pk = rule.pk
    url = reverse("ecommerce:mobilelocationrule_delete", kwargs={"pk": pk})

    resp_post = auth_client_a.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("ecommerce:mobilelocationrule_list")
    assert not MobileLocationRule.objects.filter(pk=pk).exists()

    audit = AuditLog.objects.filter(tenant=tenant_a, action="DELETE", object_id=pk).first()
    assert audit is not None


def test_mobilecommerce_locationrule_simulate_inside_geofence(auth_client_a, ecom_mobile_location_a):
    """Test location rule simulate action reports INSIDE geofence when coords match origin."""
    url = reverse("ecommerce:mobilelocationrule_simulate", kwargs={"pk": ecom_mobile_location_a.pk})
    # Coordinates match rule's center exactly
    sim_data = {
        "test_lat": str(ecom_mobile_location_a.latitude),
        "test_lng": str(ecom_mobile_location_a.longitude),
    }
    resp = auth_client_a.post(url, data=sim_data, follow=True)
    assert resp.status_code == 200
    messages = [m.message for m in resp.context["messages"]]
    assert any("INSIDE" in m for m in messages)


def test_mobilecommerce_locationrule_simulate_outside_geofence(auth_client_a, ecom_mobile_location_a):
    """Test location rule simulate action reports OUTSIDE geofence when coords are far away."""
    url = reverse("ecommerce:mobilelocationrule_simulate", kwargs={"pk": ecom_mobile_location_a.pk})
    # Coordinates opposite side of the globe
    sim_data = {
        "test_lat": "-33.8688",
        "test_lng": "151.2093",
    }
    resp = auth_client_a.post(url, data=sim_data, follow=True)
    assert resp.status_code == 200
    messages = [m.message for m in resp.context["messages"]]
    assert any("OUTSIDE" in m for m in messages)


def test_mobilecommerce_locationrule_simulate_empty_and_invalid_coordinates(auth_client_a, ecom_mobile_location_a):
    """Test location rule simulate action handles empty, non-numeric, or non-finite coordinates without 500."""
    url = reverse("ecommerce:mobilelocationrule_simulate", kwargs={"pk": ecom_mobile_location_a.pk})

    # Empty payload
    resp_empty = auth_client_a.post(url, data={"test_lat": "", "test_lng": ""}, follow=True)
    assert resp_empty.status_code == 200
    messages_empty = [m.message for m in resp_empty.context["messages"]]
    assert any("Please enter test latitude and longitude" in m for m in messages_empty)

    # Invalid string input
    resp_invalid = auth_client_a.post(url, data={"test_lat": "bad_lat", "test_lng": "bad_lng"}, follow=True)
    assert resp_invalid.status_code == 200
    messages_invalid = [m.message for m in resp_invalid.context["messages"]]
    assert any("Invalid coordinates provided" in m for m in messages_invalid)

    # Out of range coordinates
    resp_range = auth_client_a.post(url, data={"test_lat": "999.0", "test_lng": "999.0"}, follow=True)
    assert resp_range.status_code == 200
    messages_range = [m.message for m in resp_range.context["messages"]]
    assert any("must be finite and within valid ranges" in m for m in messages_range)


# ==============================================================================
# 6. Cross-Tenant IDOR Protection Tests
# ==============================================================================

def test_mobilecommerce_cross_tenant_isolation_404(
    auth_client_a,
    ecom_mobile_config_b,
    ecom_mobile_device_b,
    ecom_mobile_push_b,
    ecom_mobile_location_b,
):
    """Test Tenant A user cannot view, edit, delete, or perform actions on Tenant B objects (IDOR -> 404)."""
    # 1. Config
    assert auth_client_a.get(reverse("ecommerce:mobileappconfig_detail", kwargs={"pk": ecom_mobile_config_b.pk})).status_code == 404
    assert auth_client_a.get(reverse("ecommerce:mobileappconfig_edit", kwargs={"pk": ecom_mobile_config_b.pk})).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:mobileappconfig_delete", kwargs={"pk": ecom_mobile_config_b.pk})).status_code == 404

    # 2. Device
    assert auth_client_a.get(reverse("ecommerce:mobiledeviceregistration_detail", kwargs={"pk": ecom_mobile_device_b.pk})).status_code == 404
    assert auth_client_a.get(reverse("ecommerce:mobiledeviceregistration_edit", kwargs={"pk": ecom_mobile_device_b.pk})).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:mobiledeviceregistration_delete", kwargs={"pk": ecom_mobile_device_b.pk})).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:mobiledeviceregistration_ping", kwargs={"pk": ecom_mobile_device_b.pk})).status_code == 404

    # 3. Push Campaign
    assert auth_client_a.get(reverse("ecommerce:mobilepushcampaign_detail", kwargs={"pk": ecom_mobile_push_b.pk})).status_code == 404
    assert auth_client_a.get(reverse("ecommerce:mobilepushcampaign_edit", kwargs={"pk": ecom_mobile_push_b.pk})).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:mobilepushcampaign_delete", kwargs={"pk": ecom_mobile_push_b.pk})).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:mobilepushcampaign_test_send", kwargs={"pk": ecom_mobile_push_b.pk})).status_code == 404

    # 4. Location Rule
    assert auth_client_a.get(reverse("ecommerce:mobilelocationrule_detail", kwargs={"pk": ecom_mobile_location_b.pk})).status_code == 404
    assert auth_client_a.get(reverse("ecommerce:mobilelocationrule_edit", kwargs={"pk": ecom_mobile_location_b.pk})).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:mobilelocationrule_delete", kwargs={"pk": ecom_mobile_location_b.pk})).status_code == 404
    assert auth_client_a.post(reverse("ecommerce:mobilelocationrule_simulate", kwargs={"pk": ecom_mobile_location_b.pk})).status_code == 404
