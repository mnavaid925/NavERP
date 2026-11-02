"""Unit and contract tests for eCommerce 9.16 Mobile Commerce forms.

Covers:
- MobileAppConfigForm:
    * System fields excluded (tenant, number, created_at, updated_at).
    * Valid payload creation and persistence.
    * Hex color validation on theme_color and background_color (rejects non-hex values, auto-prepends #).
    * Composite uniqueness via TenantUniqueMixin on (tenant, short_name).
- MobileDeviceRegistrationForm:
    * System/secret fields excluded (tenant, number, push_token, last_active_at, created_at, updated_at, badge_count).
    * Foreign key queryset scoping (customer_profile and party dropdowns strictly tenant-filtered).
    * Cross-tenant foreign key rejection via reject_foreign.
    * Composite uniqueness on device_uuid via TenantUniqueMixin.
- MobilePushCampaignForm:
    * System/workflow fields excluded (tenant, number, status, created_by, sent_at, metrics counters, etc.).
    * Foreign key queryset scoping (target_product active only, target_category active, target_coupon active).
    * Cross-tenant foreign key rejection.
    * Valid creation payload and persistence.
- MobileLocationRuleForm:
    * System fields excluded (tenant, number, created_at, updated_at).
    * Foreign key queryset scoping (fulfillment_center active, linked_promotion active).
    * Cross-tenant foreign key rejection.
    * Valid coordinate inputs and boundary validation.

Conventions enforced:
- Test functions: test_mobilecommerce_*
- Module-level helpers: _mobilecommerce_*
"""
from decimal import Decimal
import uuid

import pytest
from django.utils import timezone

from apps.core.models.Party import Party
from apps.ecommerce.forms.MobileCommerce.MobileAppConfigs import MobileAppConfigForm
from apps.ecommerce.forms.MobileCommerce.MobileDeviceRegistrations import MobileDeviceRegistrationForm
from apps.ecommerce.forms.MobileCommerce.MobilePushCampaigns import MobilePushCampaignForm
from apps.ecommerce.forms.MobileCommerce.MobileLocationRules import MobileLocationRuleForm
from apps.ecommerce.models import (
    CatalogProduct,
    StoreCategory,
    CouponPromotion,
    FulfillmentCenter,
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
    _productcatalog_product,
    _productcatalog_category,
    _pricingpromotion_coupon,
    _inventorystock_center,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Module-Level Helpers (_mobilecommerce_*)
# ==============================================================================

def _mobilecommerce_create_party(tenant, name="Mobile Shopper"):
    """Helper to create a tenant-scoped Party record."""
    return Party.objects.create(tenant=tenant, name=name, kind="person")


def _mobilecommerce_valid_appconfig_payload(**overrides):
    """Generate a valid dictionary payload for MobileAppConfigForm."""
    payload = {
        "app_name": "NavERP Storefront Mobile",
        "short_name": "NavStorefront",
        "description": "Progressive Web App and hybrid mobile application experience.",
        "theme_color": "#2563EB",
        "background_color": "#FFFFFF",
        "display_mode": "standalone",
        "orientation": "portrait",
        "start_url": "/ecommerce/",
        "scope": "/ecommerce/",
        "icon_192_url": "/static/ecommerce/img/icon-192.png",
        "icon_512_url": "/static/ecommerce/img/icon-512.png",
        "offline_cache_strategy": "stale_while_revalidate",
        "offline_fallback_html": "<h1>Offline</h1><p>Check connection.</p>",
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
    payload.update(overrides)
    return payload


def _mobilecommerce_valid_device_payload(customer_profile=None, party=None, **overrides):
    """Generate a valid dictionary payload for MobileDeviceRegistrationForm."""
    payload = {
        "customer_profile": customer_profile.pk if customer_profile else "",
        "party": party.pk if party else "",
        "device_uuid": str(uuid.uuid4()),
        "device_platform": "ios",
        "device_model": "iPhone 15 Pro Max",
        "os_version": "iOS 18.1",
        "app_version": "2.4.0",
        "push_provider": "apns",
        "push_enabled": True,
        "biometric_enrolled": True,
        "location_permission": "while_in_use",
        "last_latitude": "37.774929",
        "last_longitude": "-122.419416",
        "is_active": True,
    }
    payload.update(overrides)
    return payload


def _mobilecommerce_valid_pushcampaign_payload(product=None, category=None, coupon=None, **overrides):
    """Generate a valid dictionary payload for MobilePushCampaignForm."""
    payload = {
        "campaign_name": "Summer Flash Sale Push",
        "campaign_type": "promotional",
        "target_platform": "all",
        "notification_title": "Exclusive Flash Sale Today!",
        "notification_body": "Use code SUMMER20 for 20% off all catalog items.",
        "image_url": "https://cdn.example.com/promos/hero.jpg",
        "badge_increment": 1,
        "sound_name": "default",
        "deep_link_type": "product",
        "deep_link_url": "navstore://products/123",
        "target_product": product.pk if product else "",
        "target_category": category.pk if category else "",
        "target_coupon": coupon.pk if coupon else "",
        "scheduled_for": timezone.now().strftime("%Y-%m-%dT%H:%M"),
    }
    payload.update(overrides)
    return payload


def _mobilecommerce_valid_locationrule_payload(center=None, promotion=None, **overrides):
    """Generate a valid dictionary payload for MobileLocationRuleForm."""
    payload = {
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
    payload.update(overrides)
    return payload


# ==============================================================================
# 1. MobileAppConfigForm Tests
# ==============================================================================

def test_mobilecommerce_appconfig_form_excluded_fields():
    """Verify system fields (tenant, number, created_at, updated_at) are excluded from MobileAppConfigForm."""
    form = MobileAppConfigForm()
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "created_at" not in form.fields
    assert "updated_at" not in form.fields


def test_mobilecommerce_appconfig_form_valid_creation(tenant_a):
    """Verify MobileAppConfigForm creates a valid record when populated with correct data."""
    data = _mobilecommerce_valid_appconfig_payload(short_name="AcmePWA")
    form = MobileAppConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.short_name == "AcmePWA"
    assert instance.app_name == "NavERP Storefront Mobile"
    assert instance.theme_color == "#2563EB"
    assert instance.background_color == "#FFFFFF"
    assert instance.enable_pwa is True
    assert instance.enable_apple_pay is True


def test_mobilecommerce_appconfig_form_hex_color_auto_prefix(tenant_a):
    """Verify clean_theme_color and clean_background_color prepend '#' if omitted and format is 6-hex."""
    data = _mobilecommerce_valid_appconfig_payload(
        short_name="HexTestStore",
        theme_color="10B981",       # omitted '#'
        background_color="F3F4F6",  # omitted '#'
    )
    form = MobileAppConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["theme_color"] == "#10B981"
    assert form.cleaned_data["background_color"] == "#F3F4F6"


@pytest.mark.parametrize("invalid_color", [
    "not-a-color",
    "#123",       # only 3 chars
    "#12345",     # 5 chars
    "#GGGGGG",    # non-hex chars
    "#1234567",   # 7 hex chars
    "red",
])
def test_mobilecommerce_appconfig_form_hex_color_validation_rejects_invalid(tenant_a, invalid_color):
    """Verify non-hex colors in theme_color and background_color are rejected with clear error messages."""
    data = _mobilecommerce_valid_appconfig_payload(
        short_name="BadColorStore",
        theme_color=invalid_color,
        background_color="#FFFFFF",
    )
    form = MobileAppConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "theme_color" in form.errors
    if len(invalid_color) <= 7:
        assert "hex" in str(form.errors["theme_color"]).lower()

    data_bg = _mobilecommerce_valid_appconfig_payload(
        short_name="BadBgColorStore",
        theme_color="#2563EB",
        background_color=invalid_color,
    )
    form_bg = MobileAppConfigForm(data=data_bg, tenant=tenant_a)
    assert not form_bg.is_valid()
    assert "background_color" in form_bg.errors
    if len(invalid_color) <= 7:
        assert "hex" in str(form_bg.errors["background_color"]).lower()


def test_mobilecommerce_appconfig_form_tenant_unique_short_name(tenant_a, tenant_b):
    """Verify composite uniqueness on (tenant, short_name) via TenantUniqueMixin."""
    # Existing config in Tenant A
    _mobilecommerce_app_config(tenant_a, short_name="AlphaStore")

    # Duplicate short_name in Tenant A should fail form validation
    data_a = _mobilecommerce_valid_appconfig_payload(short_name="AlphaStore")
    form_a = MobileAppConfigForm(data=data_a, tenant=tenant_a)
    assert not form_a.is_valid()
    assert "short_name" in form_a.errors or "__all__" in form_a.errors

    # Same short_name in Tenant B must succeed (cross-tenant multi-tenancy isolation)
    data_b = _mobilecommerce_valid_appconfig_payload(short_name="AlphaStore")
    form_b = MobileAppConfigForm(data=data_b, tenant=tenant_b)
    assert form_b.is_valid(), form_b.errors


def test_mobilecommerce_appconfig_form_update_existing_instance(tenant_a):
    """Verify editing an existing MobileAppConfig preserves valid state without self-uniqueness collision."""
    existing = _mobilecommerce_app_config(tenant_a, short_name="SelfEditStore", app_name="Old Name")

    data = _mobilecommerce_valid_appconfig_payload(
        short_name="SelfEditStore",
        app_name="Updated App Name",
    )
    form = MobileAppConfigForm(data=data, instance=existing, tenant=tenant_a)
    assert form.is_valid(), form.errors

    updated = form.save()
    assert updated.pk == existing.pk
    assert updated.app_name == "Updated App Name"
    assert updated.short_name == "SelfEditStore"


# ==============================================================================
# 2. MobileDeviceRegistrationForm Tests
# ==============================================================================

def test_mobilecommerce_deviceregistration_form_excluded_fields():
    """Verify system/secret fields are excluded from MobileDeviceRegistrationForm."""
    form = MobileDeviceRegistrationForm()
    excluded = ["tenant", "number", "push_token", "created_at", "updated_at", "last_active_at", "badge_count"]
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} should be excluded from MobileDeviceRegistrationForm"


def test_mobilecommerce_deviceregistration_form_valid_creation(tenant_a, ecom_profile_a):
    """Verify MobileDeviceRegistrationForm validates and saves with valid customer and party."""
    party = _mobilecommerce_create_party(tenant_a, name="Jane Doe")
    test_uuid = str(uuid.uuid4())
    data = _mobilecommerce_valid_device_payload(
        customer_profile=ecom_profile_a,
        party=party,
        device_uuid=test_uuid,
        device_platform="android",
        push_provider="fcm",
    )
    form = MobileDeviceRegistrationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.device_uuid == test_uuid
    assert instance.device_platform == "android"
    assert instance.push_provider == "fcm"
    assert instance.customer_profile == ecom_profile_a
    assert instance.party == party


def test_mobilecommerce_deviceregistration_form_anonymous_device_valid(tenant_a):
    """Verify MobileDeviceRegistrationForm allows registering an unauthenticated guest mobile device."""
    test_uuid = str(uuid.uuid4())
    data = _mobilecommerce_valid_device_payload(
        customer_profile=None,
        party=None,
        device_uuid=test_uuid,
    )
    form = MobileDeviceRegistrationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.customer_profile is None
    assert instance.party is None


def test_mobilecommerce_deviceregistration_form_fk_queryset_scoping(tenant_a, tenant_b, ecom_profile_a, ecom_profile_b):
    """Verify customer_profile and party dropdown querysets contain only tenant-scoped records."""
    party_a = _mobilecommerce_create_party(tenant_a, name="Tenant A User")
    party_b = _mobilecommerce_create_party(tenant_b, name="Tenant B User")

    form_a = MobileDeviceRegistrationForm(tenant=tenant_a)
    cust_qs = list(form_a.fields["customer_profile"].queryset)
    party_qs = list(form_a.fields["party"].queryset)

    assert ecom_profile_a in cust_qs
    assert ecom_profile_b not in cust_qs

    assert party_a in party_qs
    assert party_b not in party_qs


def test_mobilecommerce_deviceregistration_form_rejects_cross_tenant_fk(tenant_a, tenant_b, ecom_profile_b):
    """Verify passing foreign tenant customer_profile or party fails form validation."""
    party_b = _mobilecommerce_create_party(tenant_b, name="Foreign Party")

    # Cross-tenant customer_profile
    data_bad_cust = _mobilecommerce_valid_device_payload(customer_profile=ecom_profile_b)
    form_cust = MobileDeviceRegistrationForm(data=data_bad_cust, tenant=tenant_a)
    assert not form_cust.is_valid()
    assert "customer_profile" in form_cust.errors

    # Cross-tenant party
    data_bad_party = _mobilecommerce_valid_device_payload(party=party_b)
    form_party = MobileDeviceRegistrationForm(data=data_bad_party, tenant=tenant_a)
    assert not form_party.is_valid()
    assert "party" in form_party.errors


def test_mobilecommerce_deviceregistration_form_tenant_unique_device_uuid(tenant_a, tenant_b):
    """Verify composite uniqueness on (tenant, device_uuid) via TenantUniqueMixin."""
    shared_uuid = str(uuid.uuid4())
    _mobilecommerce_device_registration(tenant_a, device_uuid=shared_uuid)

    # Submitting duplicate device_uuid in Tenant A fails
    data_a = _mobilecommerce_valid_device_payload(device_uuid=shared_uuid)
    form_a = MobileDeviceRegistrationForm(data=data_a, tenant=tenant_a)
    assert not form_a.is_valid()
    assert "device_uuid" in form_a.errors or "__all__" in form_a.errors

    # Submitting identical device_uuid in Tenant B passes
    data_b = _mobilecommerce_valid_device_payload(device_uuid=shared_uuid)
    form_b = MobileDeviceRegistrationForm(data=data_b, tenant=tenant_b)
    assert form_b.is_valid(), form_b.errors


def test_mobilecommerce_deviceregistration_form_update_self(tenant_a):
    """Verify updating an existing device registration succeeds without false duplicate error."""
    device = _mobilecommerce_device_registration(tenant_a, device_uuid="11111111-2222-3333-4444-555555555555")

    data = _mobilecommerce_valid_device_payload(
        device_uuid="11111111-2222-3333-4444-555555555555",
        device_model="iPhone 16 Pro Updated",
    )
    form = MobileDeviceRegistrationForm(data=data, instance=device, tenant=tenant_a)
    assert form.is_valid(), form.errors

    saved = form.save()
    assert saved.pk == device.pk
    assert saved.device_model == "iPhone 16 Pro Updated"


# ==============================================================================
# 3. MobilePushCampaignForm Tests
# ==============================================================================

def test_mobilecommerce_pushcampaign_form_excluded_fields():
    """Verify system/workflow fields are excluded from MobilePushCampaignForm."""
    form = MobilePushCampaignForm()
    excluded = [
        "tenant", "number", "status", "created_at", "updated_at",
        "sent_at", "sent_count", "delivered_count", "opened_count",
        "converted_count", "converted_revenue", "created_by",
    ]
    for field_name in excluded:
        assert field_name not in form.fields, f"{field_name} should be excluded from MobilePushCampaignForm"


def test_mobilecommerce_pushcampaign_form_valid_creation(tenant_a, user_a, ecom_product_a, ecom_category_a, ecom_coupon_a):
    """Verify MobilePushCampaignForm creates a valid push campaign with optional target FKs."""
    data = _mobilecommerce_valid_pushcampaign_payload(
        product=ecom_product_a,
        category=ecom_category_a,
        coupon=ecom_coupon_a,
        campaign_name="Black Friday Teaser",
    )
    form = MobilePushCampaignForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.created_by = user_a
    instance.save()

    assert instance.pk is not None
    assert instance.campaign_name == "Black Friday Teaser"
    assert instance.target_product == ecom_product_a
    assert instance.target_category == ecom_category_a
    assert instance.target_coupon == ecom_coupon_a
    assert instance.status == "draft"  # default status maintained on model


def test_mobilecommerce_pushcampaign_form_blank_optional_targets(tenant_a):
    """Verify MobilePushCampaignForm validates when deep link targets are omitted."""
    data = _mobilecommerce_valid_pushcampaign_payload(
        product=None,
        category=None,
        coupon=None,
        campaign_name="General Broadcast Alert",
    )
    form = MobilePushCampaignForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.target_product is None
    assert instance.target_category is None
    assert instance.target_coupon is None


def test_mobilecommerce_pushcampaign_form_fk_queryset_scoping(
    tenant_a, tenant_b, ecom_product_a, ecom_product_b,
    ecom_category_a, ecom_category_b, ecom_coupon_a, ecom_coupon_b
):
    """Verify FK dropdowns only include active records belonging to the current tenant."""
    # Inactive product in Tenant A should be filtered out (queryset: status='active')
    inactive_product_a = _productcatalog_product(
        tenant_a,
        name="Archived Laptop",
        slug="archived-laptop-a",
        status="archived",
    )
    # Inactive category in Tenant A should be filtered out (queryset: is_active=True)
    inactive_cat_a = _productcatalog_category(
        tenant_a,
        name="Retired Category",
        slug="retired-cat-a",
        is_active=False,
    )
    # Inactive coupon in Tenant A should be filtered out (queryset: is_active=True)
    inactive_coupon_a = _pricingpromotion_coupon(
        tenant_a,
        code="EXPIRED10",
        name="Expired Discount",
        is_active=False,
    )

    form = MobilePushCampaignForm(tenant=tenant_a)

    prod_qs = list(form.fields["target_product"].queryset)
    cat_qs = list(form.fields["target_category"].queryset)
    coupon_qs = list(form.fields["target_coupon"].queryset)

    # Product scoping
    assert ecom_product_a in prod_qs
    assert ecom_product_b not in prod_qs
    assert inactive_product_a not in prod_qs

    # Category scoping
    assert ecom_category_a in cat_qs
    assert ecom_category_b not in cat_qs
    assert inactive_cat_a not in cat_qs

    # Coupon scoping
    assert ecom_coupon_a in coupon_qs
    assert ecom_coupon_b not in coupon_qs
    assert inactive_coupon_a not in coupon_qs


def test_mobilecommerce_pushcampaign_form_rejects_cross_tenant_fks(
    tenant_a, tenant_b, ecom_product_b, ecom_category_b, ecom_coupon_b
):
    """Verify passing foreign tenant product, category, or coupon fails validation."""
    # Foreign product
    data_prod = _mobilecommerce_valid_pushcampaign_payload(product=ecom_product_b)
    form_prod = MobilePushCampaignForm(data=data_prod, tenant=tenant_a)
    assert not form_prod.is_valid()
    assert "target_product" in form_prod.errors

    # Foreign category
    data_cat = _mobilecommerce_valid_pushcampaign_payload(category=ecom_category_b)
    form_cat = MobilePushCampaignForm(data=data_cat, tenant=tenant_a)
    assert not form_cat.is_valid()
    assert "target_category" in form_cat.errors

    # Foreign coupon
    data_coupon = _mobilecommerce_valid_pushcampaign_payload(coupon=ecom_coupon_b)
    form_coupon = MobilePushCampaignForm(data=data_coupon, tenant=tenant_a)
    assert not form_coupon.is_valid()
    assert "target_coupon" in form_coupon.errors


# ==============================================================================
# 4. MobileLocationRuleForm Tests
# ==============================================================================

def test_mobilecommerce_locationrule_form_excluded_fields():
    """Verify system fields (tenant, number, created_at, updated_at) are excluded from MobileLocationRuleForm."""
    form = MobileLocationRuleForm()
    assert "tenant" not in form.fields
    assert "number" not in form.fields
    assert "created_at" not in form.fields
    assert "updated_at" not in form.fields


def test_mobilecommerce_locationrule_form_valid_creation(tenant_a, ecom_center_a, ecom_coupon_a):
    """Verify MobileLocationRuleForm validates and saves with physical store center and promotion."""
    data = _mobilecommerce_valid_locationrule_payload(
        center=ecom_center_a,
        promotion=ecom_coupon_a,
        name="Midtown Express Pickup",
        latitude="40.758896",
        longitude="-73.985130",
        radius_meters=250,
    )
    form = MobileLocationRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()

    assert instance.pk is not None
    assert instance.name == "Midtown Express Pickup"
    assert instance.fulfillment_center == ecom_center_a
    assert instance.linked_promotion == ecom_coupon_a
    assert instance.latitude == Decimal("40.758896")
    assert instance.longitude == Decimal("-73.985130")
    assert instance.radius_meters == 250
    assert instance.enable_bopis_checkin is True


def test_mobilecommerce_locationrule_form_standalone_geofence(tenant_a):
    """Verify MobileLocationRuleForm validates without linked fulfillment center or promotion."""
    data = _mobilecommerce_valid_locationrule_payload(
        center=None,
        promotion=None,
        name="Pop-up Event Geofence",
    )
    form = MobileLocationRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), form.errors

    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.pk is not None
    assert instance.fulfillment_center is None
    assert instance.linked_promotion is None


def test_mobilecommerce_locationrule_form_fk_queryset_scoping(
    tenant_a, tenant_b, ecom_center_a, ecom_center_b, ecom_coupon_a, ecom_coupon_b
):
    """Verify fulfillment_center and linked_promotion querysets are tenant-scoped and filter active records."""
    inactive_center_a = _inventorystock_center(
        tenant_a,
        name="Inactive Depot",
        code="DEPOT-INACT",
        is_active=False,
    )
    inactive_coupon_a = _pricingpromotion_coupon(
        tenant_a,
        code="OLDDISC",
        name="Old Coupon",
        is_active=False,
    )

    form = MobileLocationRuleForm(tenant=tenant_a)

    center_qs = list(form.fields["fulfillment_center"].queryset)
    promo_qs = list(form.fields["linked_promotion"].queryset)

    # Fulfillment Center scoping
    assert ecom_center_a in center_qs
    assert ecom_center_b not in center_qs
    assert inactive_center_a not in center_qs

    # Promotion scoping
    assert ecom_coupon_a in promo_qs
    assert ecom_coupon_b not in promo_qs
    assert inactive_coupon_a not in promo_qs


def test_mobilecommerce_locationrule_form_rejects_cross_tenant_fks(
    tenant_a, tenant_b, ecom_center_b, ecom_coupon_b
):
    """Verify passing foreign tenant fulfillment center or promotion fails form validation."""
    # Foreign fulfillment center
    data_center = _mobilecommerce_valid_locationrule_payload(center=ecom_center_b)
    form_center = MobileLocationRuleForm(data=data_center, tenant=tenant_a)
    assert not form_center.is_valid()
    assert "fulfillment_center" in form_center.errors

    # Foreign linked promotion
    data_promo = _mobilecommerce_valid_locationrule_payload(promotion=ecom_coupon_b)
    form_promo = MobileLocationRuleForm(data=data_promo, tenant=tenant_a)
    assert not form_promo.is_valid()
    assert "linked_promotion" in form_promo.errors


def test_mobilecommerce_locationrule_form_valid_coordinate_boundaries(tenant_a):
    """Verify valid boundary coordinates (e.g. poles and international date line extremes) validate properly."""
    # North pole boundary
    data_north = _mobilecommerce_valid_locationrule_payload(
        name="North Pole Rule",
        latitude="90.000000",
        longitude="0.000000",
    )
    form_north = MobileLocationRuleForm(data=data_north, tenant=tenant_a)
    assert form_north.is_valid(), form_north.errors

    # South pole boundary
    data_south = _mobilecommerce_valid_locationrule_payload(
        name="South Pole Rule",
        latitude="-90.000000",
        longitude="0.000000",
    )
    form_south = MobileLocationRuleForm(data=data_south, tenant=tenant_a)
    assert form_south.is_valid(), form_south.errors

    # Antimeridian boundary
    data_date_line = _mobilecommerce_valid_locationrule_payload(
        name="Antimeridian Rule",
        latitude="0.000000",
        longitude="-180.000000",
    )
    form_date_line = MobileLocationRuleForm(data=data_date_line, tenant=tenant_a)
    assert form_date_line.is_valid(), form_date_line.errors


def test_mobilecommerce_locationrule_form_invalid_coordinates_rejected(tenant_a):
    """Verify non-numeric coordinates or values exceeding DecimalField max_digits fail validation."""
    # Non-numeric latitude
    data_nan = _mobilecommerce_valid_locationrule_payload(latitude="not-a-number")
    form_nan = MobileLocationRuleForm(data=data_nan, tenant=tenant_a)
    assert not form_nan.is_valid()
    assert "latitude" in form_nan.errors

    # Latitude exceeding max_digits (max_digits=9, decimal_places=6 allows up to 3 digits before decimal)
    data_overflow = _mobilecommerce_valid_locationrule_payload(latitude="10000.123456")
    form_overflow = MobileLocationRuleForm(data=data_overflow, tenant=tenant_a)
    assert not form_overflow.is_valid()
    assert "latitude" in form_overflow.errors
