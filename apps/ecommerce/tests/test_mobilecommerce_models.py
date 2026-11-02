"""Unit and contract tests for eCommerce 9.16 Mobile Commerce models.

Covers:
- MobileAppConfig: prefix EMAC-, contract fields, W3C PWA manifest generation,
  hex color validation, unique constraints on (tenant, short_name) and (tenant, number).
- MobileDeviceRegistration: prefix EMDR-, contract fields, record_activity telemetry,
  badge reset, composite indexes, unique constraints on (tenant, device_uuid) and (tenant, number).
- MobilePushCampaign: prefix EMPC-, contract fields, dispatch simulation,
  open rate and CTR metrics properties, unique constraint on (tenant, number).
- MobileLocationRule: prefix EMLR-, contract fields, Haversine distance computation,
  domain error prevention on clamped coords, is_device_inside geofencing,
  unique constraint on (tenant, number).
- Multi-tenant isolation: Tenant A records strictly isolated from Tenant B.

Conventions enforced:
- Test functions: test_mobilecommerce_*
- Module-level helpers: _mobilecommerce_*
"""
from decimal import Decimal
import json

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ecommerce.models import (
    MobileAppConfig,
    MobileDeviceRegistration,
    MobilePushCampaign,
    MobileLocationRule,
)
from apps.ecommerce.tests.conftest import (
    MOBILECOMMERCE_MODEL_FIELDS,
    _mobilecommerce_app_config,
    _mobilecommerce_device_registration,
    _mobilecommerce_push_campaign,
    _mobilecommerce_location_rule,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Module-Level Helpers (_mobilecommerce_*)
# ==============================================================================

def _mobilecommerce_create_app_config(tenant, **kwargs):
    """Helper to create a MobileAppConfig instance."""
    return _mobilecommerce_app_config(tenant, **kwargs)


def _mobilecommerce_create_device(tenant, **kwargs):
    """Helper to create a MobileDeviceRegistration instance."""
    return _mobilecommerce_device_registration(tenant, **kwargs)


def _mobilecommerce_create_push_campaign(tenant, **kwargs):
    """Helper to create a MobilePushCampaign instance."""
    return _mobilecommerce_push_campaign(tenant, **kwargs)


def _mobilecommerce_create_location_rule(tenant, **kwargs):
    """Helper to create a MobileLocationRule instance."""
    return _mobilecommerce_location_rule(tenant, **kwargs)


# ==============================================================================
# MobileAppConfig Tests
# ==============================================================================

def test_mobilecommerce_appconfig_contract_fields(ecom_mobile_config_a):
    """Verify MobileAppConfig defines all fields specified in MOBILECOMMERCE_MODEL_FIELDS."""
    expected_fields = MOBILECOMMERCE_MODEL_FIELDS["MobileAppConfig"]
    actual_fields = [
        f.name for f in MobileAppConfig._meta.get_fields()
        if not f.is_relation or f.many_to_one or f.one_to_one
    ]
    for field in expected_fields:
        assert field in actual_fields, f"MobileAppConfig is missing contract field: '{field}'"


def test_mobilecommerce_appconfig_auto_number(ecom_mobile_config_a):
    """Verify MobileAppConfig generates auto-number with prefix EMAC-."""
    assert ecom_mobile_config_a.number.startswith("EMAC-")
    assert len(ecom_mobile_config_a.number) > 5


def test_mobilecommerce_appconfig_str(ecom_mobile_config_a):
    """Verify MobileAppConfig string representation format."""
    expected = f"{ecom_mobile_config_a.short_name} ({ecom_mobile_config_a.number})"
    assert str(ecom_mobile_config_a) == expected


def test_mobilecommerce_appconfig_manifest_dict(ecom_mobile_config_a):
    """Verify generate_manifest_dict outputs a valid W3C PWA manifest dictionary."""
    manifest = ecom_mobile_config_a.generate_manifest_dict()
    assert isinstance(manifest, dict)
    assert manifest["name"] == ecom_mobile_config_a.app_name
    assert manifest["short_name"] == ecom_mobile_config_a.short_name
    assert manifest["description"] == ecom_mobile_config_a.description
    assert manifest["start_url"] == ecom_mobile_config_a.start_url
    assert manifest["scope"] == ecom_mobile_config_a.scope
    assert manifest["display"] == ecom_mobile_config_a.display_mode
    assert manifest["orientation"] == ecom_mobile_config_a.orientation
    assert manifest["theme_color"] == ecom_mobile_config_a.theme_color
    assert manifest["background_color"] == ecom_mobile_config_a.background_color

    # Verify icons list structure
    icons = manifest["icons"]
    assert isinstance(icons, list)
    assert len(icons) == 2
    sizes = [icon["sizes"] for icon in icons]
    assert "192x192" in sizes
    assert "512x512" in sizes
    for icon in icons:
        assert icon["type"] == "image/png"
        assert icon["purpose"] == "any maskable"


def test_mobilecommerce_appconfig_manifest_json(ecom_mobile_config_a):
    """Verify generate_manifest_json returns valid, parseable JSON matching the manifest dict."""
    manifest_json = ecom_mobile_config_a.generate_manifest_json()
    assert isinstance(manifest_json, str)
    parsed = json.loads(manifest_json)
    assert parsed == ecom_mobile_config_a.generate_manifest_dict()


def test_mobilecommerce_appconfig_hex_color_validation(tenant_a):
    """Verify hex color validator accepts valid 6-char hex and rejects invalid formats."""
    # Valid hex colors should pass full_clean
    valid_config = _mobilecommerce_create_app_config(
        tenant_a,
        short_name="ValidHex",
        theme_color="#2563EB",
        background_color="#FFFFFF",
    )
    valid_config.full_clean()

    # Invalid theme_color formats
    invalid_theme_cases = ["#FFF", "2563EB", "#2563EB1", "blue", "#GGGGGG", ""]
    for invalid_val in invalid_theme_cases:
        bad_config = MobileAppConfig(
            tenant=tenant_a,
            short_name=f"BadTheme_{invalid_val[:4]}",
            theme_color=invalid_val,
            background_color="#FFFFFF",
        )
        with pytest.raises(ValidationError):
            bad_config.full_clean()

    # Invalid background_color formats
    invalid_bg_cases = ["#123", "red", "#ZZZZZZ", "transparent"]
    for invalid_val in invalid_bg_cases:
        bad_config = MobileAppConfig(
            tenant=tenant_a,
            short_name=f"BadBg_{invalid_val[:4]}",
            theme_color="#2563EB",
            background_color=invalid_val,
        )
        with pytest.raises(ValidationError):
            bad_config.full_clean()


def test_mobilecommerce_appconfig_unique_short_name(tenant_a, tenant_b):
    """Verify unique constraint on (tenant, short_name): blocked intra-tenant, allowed inter-tenant."""
    _mobilecommerce_create_app_config(tenant_a, short_name="UniqueLauncher")

    # Allowed for a different tenant
    config_b = _mobilecommerce_create_app_config(tenant_b, short_name="UniqueLauncher")
    assert config_b.short_name == "UniqueLauncher"

    # Blocked for the same tenant
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _mobilecommerce_create_app_config(tenant_a, short_name="UniqueLauncher")


def test_mobilecommerce_appconfig_unique_number(tenant_a, tenant_b):
    """Verify unique constraint on (tenant, number)."""
    cfg_a = _mobilecommerce_create_app_config(tenant_a, short_name="CfgA1", number="EMAC-77777")

    # Allowed across tenants
    cfg_b = _mobilecommerce_create_app_config(tenant_b, short_name="CfgB1", number="EMAC-77777")
    assert cfg_a.number == cfg_b.number

    # Blocked within same tenant
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _mobilecommerce_create_app_config(tenant_a, short_name="CfgA2", number="EMAC-77777")


# ==============================================================================
# MobileDeviceRegistration Tests
# ==============================================================================

def test_mobilecommerce_deviceregistration_contract_fields(ecom_mobile_device_a):
    """Verify MobileDeviceRegistration defines all fields specified in contract."""
    expected_fields = MOBILECOMMERCE_MODEL_FIELDS["MobileDeviceRegistration"]
    actual_fields = [
        f.name for f in MobileDeviceRegistration._meta.get_fields()
        if not f.is_relation or f.many_to_one or f.one_to_one
    ]
    for field in expected_fields:
        assert field in actual_fields, f"MobileDeviceRegistration missing contract field: '{field}'"


def test_mobilecommerce_deviceregistration_auto_number(ecom_mobile_device_a):
    """Verify MobileDeviceRegistration auto-generates number with EMDR- prefix."""
    assert ecom_mobile_device_a.number.startswith("EMDR-")
    assert len(ecom_mobile_device_a.number) > 5


def test_mobilecommerce_deviceregistration_str(tenant_a):
    """Verify string representation with and without device model."""
    dev_with_model = _mobilecommerce_create_device(
        tenant_a,
        device_uuid="uuid-model-test-01",
        device_platform="ios",
        device_model="iPhone 15 Pro",
    )
    assert str(dev_with_model) == f"{dev_with_model.number} (Apple iOS - iPhone 15 Pro)"

    dev_no_model = _mobilecommerce_create_device(
        tenant_a,
        device_uuid="uuid-no-model-test-02",
        device_platform="android",
        device_model="",
    )
    assert str(dev_no_model) == f"{dev_no_model.number} (Google Android)"


def test_mobilecommerce_deviceregistration_record_activity(ecom_mobile_device_a):
    """Verify record_activity updates last_active_at and GPS coordinates."""
    old_active_at = ecom_mobile_device_a.last_active_at
    new_lat = Decimal("40.712800")
    new_lng = Decimal("-74.006000")

    ecom_mobile_device_a.record_activity(lat=new_lat, lng=new_lng)
    ecom_mobile_device_a.refresh_from_db()

    assert ecom_mobile_device_a.last_latitude == new_lat
    assert ecom_mobile_device_a.last_longitude == new_lng
    assert ecom_mobile_device_a.last_active_at >= old_active_at

    # Telemetry ping without coords keeps existing coordinates intact
    ecom_mobile_device_a.record_activity()
    ecom_mobile_device_a.refresh_from_db()
    assert ecom_mobile_device_a.last_latitude == new_lat
    assert ecom_mobile_device_a.last_longitude == new_lng


def test_mobilecommerce_deviceregistration_reset_badge_count(ecom_mobile_device_a):
    """Verify reset_badge_count resets unread badge counter to zero."""
    ecom_mobile_device_a.badge_count = 5
    ecom_mobile_device_a.save(update_fields=["badge_count"])

    ecom_mobile_device_a.reset_badge_count()
    ecom_mobile_device_a.refresh_from_db()
    assert ecom_mobile_device_a.badge_count == 0


def test_mobilecommerce_deviceregistration_composite_indexes():
    """Verify composite indexes exist on MobileDeviceRegistration for telemetry and broadcast."""
    indexes = {idx.name: idx.fields for idx in MobileDeviceRegistration._meta.indexes}

    assert "idx_emdr_ten_last_act" in indexes
    assert indexes["idx_emdr_ten_last_act"] == ["tenant", "-last_active_at"]

    assert "idx_emdr_ten_push_act" in indexes
    assert indexes["idx_emdr_ten_push_act"] == ["tenant", "is_active", "push_enabled"]


def test_mobilecommerce_deviceregistration_unique_device_uuid(tenant_a, tenant_b):
    """Verify unique constraint on (tenant, device_uuid)."""
    uuid_str = "device-hardware-uuid-11223344"
    _mobilecommerce_create_device(tenant_a, device_uuid=uuid_str)

    # Allowed across tenants
    dev_b = _mobilecommerce_create_device(tenant_b, device_uuid=uuid_str)
    assert dev_b.device_uuid == uuid_str

    # Blocked within same tenant
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _mobilecommerce_create_device(tenant_a, device_uuid=uuid_str)


def test_mobilecommerce_deviceregistration_unique_number(tenant_a, tenant_b):
    """Verify unique constraint on (tenant, number)."""
    dev_a = _mobilecommerce_create_device(tenant_a, device_uuid="uuid-num-a", number="EMDR-99901")
    dev_b = _mobilecommerce_create_device(tenant_b, device_uuid="uuid-num-b", number="EMDR-99901")
    assert dev_a.number == dev_b.number

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _mobilecommerce_create_device(tenant_a, device_uuid="uuid-num-c", number="EMDR-99901")


# ==============================================================================
# MobilePushCampaign Tests
# ==============================================================================

def test_mobilecommerce_pushcampaign_contract_fields(ecom_mobile_push_a):
    """Verify MobilePushCampaign defines all contract fields."""
    expected_fields = MOBILECOMMERCE_MODEL_FIELDS["MobilePushCampaign"]
    actual_fields = [
        f.name for f in MobilePushCampaign._meta.get_fields()
        if not f.is_relation or f.many_to_one or f.one_to_one
    ]
    for field in expected_fields:
        assert field in actual_fields, f"MobilePushCampaign missing contract field: '{field}'"


def test_mobilecommerce_pushcampaign_auto_number(ecom_mobile_push_a):
    """Verify MobilePushCampaign auto-generates number with EMPC- prefix."""
    assert ecom_mobile_push_a.number.startswith("EMPC-")
    assert len(ecom_mobile_push_a.number) > 5


def test_mobilecommerce_pushcampaign_str(ecom_mobile_push_a):
    """Verify string representation of MobilePushCampaign."""
    expected = f"{ecom_mobile_push_a.campaign_name} ({ecom_mobile_push_a.number})"
    assert str(ecom_mobile_push_a) == expected


def test_mobilecommerce_pushcampaign_dispatch_simulation(tenant_a):
    """Verify dispatch_simulation updates status, timestamp, counts, and attributed revenue."""
    campaign = _mobilecommerce_create_push_campaign(tenant_a, status="draft")
    assert campaign.status == "draft"
    assert campaign.sent_at is None

    campaign.dispatch_simulation(device_count=50)
    campaign.refresh_from_db()

    assert campaign.status == "sent"
    assert campaign.sent_at is not None
    assert campaign.sent_count == 50
    assert campaign.delivered_count == 49
    assert campaign.opened_count == 20  # int(50 * 0.4)
    assert campaign.converted_count == 5  # int(50 * 0.1)
    assert campaign.converted_revenue == Decimal("225.00")  # 5 * 45


def test_mobilecommerce_pushcampaign_metrics_properties(tenant_a):
    """Verify open_rate_pct and click_through_rate_pct calculations and zero guards."""
    campaign = _mobilecommerce_create_push_campaign(
        tenant_a,
        delivered_count=0,
        opened_count=0,
        converted_count=0,
    )
    # Zero guard checks
    assert campaign.open_rate_pct == 0.0
    assert campaign.calculate_open_rate_pct() == 0.0
    assert campaign.click_through_rate_pct == 0.0
    assert campaign.calculate_ctr_pct() == 0.0
    assert campaign.ctr_pct == 0.0

    # Populated metrics
    campaign.delivered_count = 200
    campaign.opened_count = 50
    campaign.converted_count = 10

    # 50 / 200 * 100 = 25.0%
    assert campaign.open_rate_pct == 25.0
    assert campaign.calculate_open_rate_pct() == 25.0

    # 10 / 50 * 100 = 20.0%
    assert campaign.click_through_rate_pct == 20.0
    assert campaign.calculate_ctr_pct() == 20.0
    assert campaign.ctr_pct == 20.0


def test_mobilecommerce_pushcampaign_unique_number(tenant_a, tenant_b):
    """Verify unique constraint on (tenant, number)."""
    camp_a = _mobilecommerce_create_push_campaign(tenant_a, campaign_name="CampA1", number="EMPC-66601")
    camp_b = _mobilecommerce_create_push_campaign(tenant_b, campaign_name="CampB1", number="EMPC-66601")
    assert camp_a.number == camp_b.number

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _mobilecommerce_create_push_campaign(tenant_a, campaign_name="CampA2", number="EMPC-66601")


# ==============================================================================
# MobileLocationRule Tests
# ==============================================================================

def test_mobilecommerce_locationrule_contract_fields(ecom_mobile_location_a):
    """Verify MobileLocationRule defines all contract fields."""
    expected_fields = MOBILECOMMERCE_MODEL_FIELDS["MobileLocationRule"]
    actual_fields = [
        f.name for f in MobileLocationRule._meta.get_fields()
        if not f.is_relation or f.many_to_one or f.one_to_one
    ]
    for field in expected_fields:
        assert field in actual_fields, f"MobileLocationRule missing contract field: '{field}'"


def test_mobilecommerce_locationrule_auto_number(ecom_mobile_location_a):
    """Verify MobileLocationRule auto-generates number with EMLR- prefix."""
    assert ecom_mobile_location_a.number.startswith("EMLR-")
    assert len(ecom_mobile_location_a.number) > 5


def test_mobilecommerce_locationrule_str(ecom_mobile_location_a):
    """Verify string representation of MobileLocationRule."""
    expected = f"{ecom_mobile_location_a.name} - {ecom_mobile_location_a.store_name} ({ecom_mobile_location_a.number})"
    assert str(ecom_mobile_location_a) == expected


def test_mobilecommerce_locationrule_distance_to_accurate(tenant_a):
    """Verify distance_to computes accurate Haversine distance in meters and handles zero distance."""
    rule = _mobilecommerce_create_location_rule(
        tenant_a,
        latitude=Decimal("37.774900"),
        longitude=Decimal("-122.419400"),
    )
    # Distance to exact same location should be 0.0
    zero_dist = rule.distance_to(Decimal("37.774900"), Decimal("-122.419400"))
    assert zero_dist == 0.0

    # Known distance: San Francisco (37.7749, -122.4194) to Oakland City Center (37.8044, -122.2712)
    # Expected distance is ~13.4 km - 14.0 km (13,000m - 14,000m)
    dist = rule.distance_to(37.8044, -122.2712)
    assert 13000 <= dist <= 14000


def test_mobilecommerce_locationrule_distance_to_edge_cases(tenant_a):
    """Verify distance_to gracefully handles None, invalid coords, and clamped antipodal coords without math domain errors."""
    rule = _mobilecommerce_create_location_rule(
        tenant_a,
        latitude=Decimal("0.000000"),
        longitude=Decimal("0.000000"),
    )
    # None coordinates return infinity
    assert rule.distance_to(None, None) == float("inf")
    assert rule.distance_to(37.77, None) == float("inf")
    assert rule.distance_to(None, -122.41) == float("inf")

    # Non-numeric/malformed values return infinity
    assert rule.distance_to("invalid", "coords") == float("inf")
    assert rule.distance_to(float("nan"), 0.0) == float("inf")
    assert rule.distance_to(0.0, float("inf")) == float("inf")

    # Antipodal points (180 degrees apart) where 'a' could exceed 1.0 due to float precision
    # Must not raise ValueError: math domain error
    antipodal_dist = rule.distance_to(Decimal("0.000000"), Decimal("180.000000"))
    assert isinstance(antipodal_dist, float)
    assert antipodal_dist > 19000000  # ~20,015 km (half Earth circumference)


def test_mobilecommerce_locationrule_is_device_inside(tenant_a):
    """Verify is_device_inside and is_within_geofence evaluate true within radius and false outside."""
    rule = _mobilecommerce_create_location_rule(
        tenant_a,
        latitude=Decimal("37.774900"),
        longitude=Decimal("-122.419400"),
        radius_meters=500,
    )
    # Point ~50 meters away (inside 500m radius)
    inside_lat = 37.775300
    inside_lng = -122.419400
    assert rule.is_device_inside(inside_lat, inside_lng) is True
    assert rule.is_within_geofence(inside_lat, inside_lng) is True

    # Point ~2000 meters away (outside 500m radius)
    outside_lat = 37.790000
    outside_lng = -122.419400
    assert rule.is_device_inside(outside_lat, outside_lng) is False
    assert rule.is_within_geofence(outside_lat, outside_lng) is False


def test_mobilecommerce_locationrule_unique_number(tenant_a, tenant_b):
    """Verify unique constraint on (tenant, number)."""
    rule_a = _mobilecommerce_create_location_rule(tenant_a, name="RuleA1", number="EMLR-55501")
    rule_b = _mobilecommerce_create_location_rule(tenant_b, name="RuleB1", number="EMLR-55501")
    assert rule_a.number == rule_b.number

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _mobilecommerce_create_location_rule(tenant_a, name="RuleA2", number="EMLR-55501")


# ==============================================================================
# Multi-Tenant Isolation Tests
# ==============================================================================

def test_mobilecommerce_multi_tenant_isolation(
    tenant_a,
    tenant_b,
    ecom_mobile_config_a,
    ecom_mobile_config_b,
    ecom_mobile_device_a,
    ecom_mobile_device_b,
    ecom_mobile_push_a,
    ecom_mobile_push_b,
    ecom_mobile_location_a,
    ecom_mobile_location_b,
):
    """Verify strict tenant isolation across all Mobile Commerce models."""
    # App Config isolation
    configs_a = list(MobileAppConfig.objects.filter(tenant=tenant_a))
    assert ecom_mobile_config_a in configs_a
    assert ecom_mobile_config_b not in configs_a

    # Device Registration isolation
    devices_a = list(MobileDeviceRegistration.objects.filter(tenant=tenant_a))
    assert ecom_mobile_device_a in devices_a
    assert ecom_mobile_device_b not in devices_a

    # Push Campaign isolation
    campaigns_a = list(MobilePushCampaign.objects.filter(tenant=tenant_a))
    assert ecom_mobile_push_a in campaigns_a
    assert ecom_mobile_push_b not in campaigns_a

    # Location Rule isolation
    locations_a = list(MobileLocationRule.objects.filter(tenant=tenant_a))
    assert ecom_mobile_location_a in locations_a
    assert ecom_mobile_location_b not in locations_a
