"""Unit tests for Sub-module 10.17 Embedded & Mobile BI models.

Models covered:
- EmbeddedAnalyticsConfig (EMB)
- KioskWallboardDisplay (WALL)
- MobileBiConfiguration (MOB)
- EmbedApiToken (EAPI)
"""
from datetime import timedelta
import secrets

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.bi.models import (
    BiDashboard,
    EmbedApiToken,
    EmbeddedAnalyticsConfig,
    KioskWallboardDisplay,
    MobileBiConfiguration,
    ReportDefinition,
    SemanticModel,
)
from apps.core.models import Tenant

User = get_user_model()


# ---------------------------------------------------------------------------
# Module Helpers (strictly prefixed with _embeddedmobilebi_)
# ---------------------------------------------------------------------------


def _embeddedmobilebi_create_report(tenant, name="Test Report Definition"):
    """Helper to create a ReportDefinition with minimal fields."""
    return ReportDefinition.objects.create(
        tenant=tenant,
        name=name,
        slug="test-report-definition",
        category="sales",
        report_type="standard_tabular",
        status="published",
    )


def _embeddedmobilebi_create_embed_config(tenant, name="Test Embed Config", **kwargs):
    """Helper to create an EmbeddedAnalyticsConfig with default values."""
    defaults = {
        "name": name,
        "target_type": "dashboard",
        "embedding_mode": "iframe",
        "auth_mode": "signed_jwt",
        "theme_mode": "light",
        "status": "active",
    }
    defaults.update(kwargs)
    return EmbeddedAnalyticsConfig.objects.create(tenant=tenant, **defaults)


def _embeddedmobilebi_create_wallboard(tenant, name="Test Wallboard", **kwargs):
    """Helper to create a KioskWallboardDisplay with default values."""
    defaults = {
        "name": name,
        "location_description": "Ops Center Display",
        "theme": "dark_navy",
        "display_schedule": "continuous_24_7",
        "status": "active",
    }
    defaults.update(kwargs)
    return KioskWallboardDisplay.objects.create(tenant=tenant, **defaults)


def _embeddedmobilebi_create_mobile_config(tenant, name="Test Mobile Profile", **kwargs):
    """Helper to create a MobileBiConfiguration with default values."""
    defaults = {
        "name": name,
        "touch_layout_preset": "comfortable",
        "push_digest_frequency": "daily_morning",
        "status": "active",
    }
    defaults.update(kwargs)
    return MobileBiConfiguration.objects.create(tenant=tenant, **defaults)


def _embeddedmobilebi_create_token(tenant, name="Test Embed Token", **kwargs):
    """Helper to create an EmbedApiToken with valid hash and default values."""
    raw_token, prefix, token_hash = EmbedApiToken.generate_secret()
    defaults = {
        "name": name,
        "token_prefix": prefix,
        "token_hash": token_hash,
        "status": "active",
    }
    defaults.update(kwargs)
    return EmbedApiToken.objects.create(tenant=tenant, **defaults)


# ===========================================================================
# 1. EmbeddedAnalyticsConfig Model Tests (EMB)
# ===========================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_config_fixture_and_str(embedded_analytics_config_a):
    """Test EmbeddedAnalyticsConfig fixture from conftest, string representation, and prefix."""
    assert embedded_analytics_config_a.pk is not None
    assert embedded_analytics_config_a.number.startswith("EMB-")
    expected_str = f"{embedded_analytics_config_a.number} - {embedded_analytics_config_a.name} ({embedded_analytics_config_a.get_target_type_display()})"
    assert str(embedded_analytics_config_a) == expected_str


@pytest.mark.django_db
def test_embeddedmobilebi_config_autonumbering(tenant_a):
    """Test auto-numbering generates sequential EMB- numbers."""
    cfg1 = _embeddedmobilebi_create_embed_config(tenant=tenant_a, name="Portal Alpha")
    cfg2 = _embeddedmobilebi_create_embed_config(tenant=tenant_a, name="Portal Beta")

    assert cfg1.number.startswith("EMB-")
    assert cfg2.number.startswith("EMB-")
    assert cfg1.number != cfg2.number


@pytest.mark.django_db
def test_embeddedmobilebi_config_default_values(tenant_a):
    """Test default values for EmbeddedAnalyticsConfig fields."""
    config = EmbeddedAnalyticsConfig.objects.create(
        tenant=tenant_a,
        name="Default Test Config",
    )

    assert config.target_type == "dashboard"
    assert config.embedding_mode == "iframe"
    assert config.auth_mode == "signed_jwt"
    assert config.status == "active"
    assert config.allowed_origins == "*"
    assert config.theme_mode == "light"
    assert config.primary_color == "#1e40af"
    assert config.accent_color == "#3b82f6"
    assert config.custom_css == ""
    assert config.enable_rls_filter is True
    assert config.default_rls_attributes == {}
    assert config.view_count == 0
    assert config.last_accessed_at is None
    assert config.slug == "default-test-config"


@pytest.mark.django_db
def test_embeddedmobilebi_config_unique_slug_generation_per_tenant(tenant_a, tenant_b):
    """Test unique slug generation and collision resolution scoped per tenant."""
    cfg1 = _embeddedmobilebi_create_embed_config(tenant=tenant_a, name="Executive Dashboard")
    assert cfg1.slug == "executive-dashboard"

    cfg2 = _embeddedmobilebi_create_embed_config(tenant=tenant_a, name="Executive Dashboard")
    assert cfg2.slug == "executive-dashboard-1"

    cfg3 = _embeddedmobilebi_create_embed_config(tenant=tenant_a, name="Executive Dashboard")
    assert cfg3.slug == "executive-dashboard-2"

    # Cross-tenant: tenant_b can reuse "executive-dashboard" base slug
    cfg_b = _embeddedmobilebi_create_embed_config(tenant=tenant_b, name="Executive Dashboard")
    assert cfg_b.slug == "executive-dashboard"

    # Re-saving existing record preserves its slug without incrementing
    cfg1.description = "Updated description"
    cfg1.save()
    assert cfg1.slug == "executive-dashboard"

    # Empty / special characters fallback
    cfg_special = _embeddedmobilebi_create_embed_config(tenant=tenant_a, name="$$$###")
    assert cfg_special.slug.startswith("embed-config")


@pytest.mark.django_db
def test_embeddedmobilebi_config_target_type_choices_and_relationships(
    tenant_a, bi_dashboard_a, semantic_model_a
):
    """Test target type choices and foreign key relationships for dashboard, report, and semantic model."""
    report_def = _embeddedmobilebi_create_report(tenant_a)

    # Dashboard target
    cfg_dash = _embeddedmobilebi_create_embed_config(
        tenant=tenant_a,
        name="Dashboard Embed",
        target_type="dashboard",
        dashboard=bi_dashboard_a,
    )
    assert cfg_dash.dashboard == bi_dashboard_a
    assert bi_dashboard_a.embedded_configs.filter(pk=cfg_dash.pk).exists()

    # Report target
    cfg_rep = _embeddedmobilebi_create_embed_config(
        tenant=tenant_a,
        name="Report Embed",
        target_type="report",
        report=report_def,
    )
    assert cfg_rep.report == report_def
    assert report_def.embedded_configs.filter(pk=cfg_rep.pk).exists()

    # Semantic model target
    cfg_sem = _embeddedmobilebi_create_embed_config(
        tenant=tenant_a,
        name="Semantic Model Embed",
        target_type="semantic_model",
        semantic_model=semantic_model_a,
    )
    assert cfg_sem.semantic_model == semantic_model_a
    assert semantic_model_a.embedded_configs.filter(pk=cfg_sem.pk).exists()

    # Verify model choices contract
    assert [c[0] for c in EmbeddedAnalyticsConfig.TARGET_TYPE_CHOICES] == [
        "dashboard",
        "report",
        "semantic_model",
    ]
    assert [c[0] for c in EmbeddedAnalyticsConfig.EMBEDDING_MODE_CHOICES] == [
        "iframe",
        "web_component",
        "headless_api",
    ]
    assert [c[0] for c in EmbeddedAnalyticsConfig.AUTH_MODE_CHOICES] == [
        "public_token",
        "signed_jwt",
        "sso_passthrough",
    ]
    assert [c[0] for c in EmbeddedAnalyticsConfig.THEME_MODE_CHOICES] == [
        "light",
        "dark",
        "auto",
        "custom",
    ]
    assert [c[0] for c in EmbeddedAnalyticsConfig.STATUS_CHOICES] == [
        "active",
        "paused",
        "revoked",
    ]


@pytest.mark.django_db
def test_embeddedmobilebi_config_tenant_isolation(
    embedded_analytics_config_a, embedded_analytics_config_b, tenant_a, tenant_b
):
    """Test tenant isolation of EmbeddedAnalyticsConfig querysets and constraints."""
    qs_a = EmbeddedAnalyticsConfig.objects.filter(tenant=tenant_a)
    qs_b = EmbeddedAnalyticsConfig.objects.filter(tenant=tenant_b)

    assert embedded_analytics_config_a in qs_a
    assert embedded_analytics_config_a not in qs_b
    assert embedded_analytics_config_b in qs_b
    assert embedded_analytics_config_b not in qs_a

    # Number uniqueness per tenant: duplicate number in tenant_a raises IntegrityError
    with pytest.raises(IntegrityError):
        EmbeddedAnalyticsConfig.objects.create(
            tenant=tenant_a,
            number=embedded_analytics_config_a.number,
            name="Colliding Number",
        )


@pytest.mark.django_db
def test_embeddedmobilebi_config_fk_set_null_on_delete(tenant_a, bi_dashboard_a):
    """Test that deleting the referenced dashboard sets FK to NULL instead of cascading."""
    config = _embeddedmobilebi_create_embed_config(
        tenant=tenant_a,
        name="Dashboard To Delete Embed",
        target_type="dashboard",
        dashboard=bi_dashboard_a,
    )
    assert config.dashboard_id == bi_dashboard_a.pk

    bi_dashboard_a.delete()
    config.refresh_from_db()
    assert config.dashboard is None


# ===========================================================================
# 2. KioskWallboardDisplay Model Tests (WALL)
# ===========================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_wallboard_fixture_and_str(kiosk_wallboard_display_a):
    """Test KioskWallboardDisplay fixture, string representation with and without location."""
    assert kiosk_wallboard_display_a.pk is not None
    assert kiosk_wallboard_display_a.number.startswith("WALL-")
    expected_str = f"{kiosk_wallboard_display_a.number} - {kiosk_wallboard_display_a.name} ({kiosk_wallboard_display_a.location_description or 'Unassigned'})"
    assert str(kiosk_wallboard_display_a) == expected_str

    kiosk_wallboard_display_a.location_description = ""
    assert str(kiosk_wallboard_display_a) == f"{kiosk_wallboard_display_a.number} - {kiosk_wallboard_display_a.name} (Unassigned)"


@pytest.mark.django_db
def test_embeddedmobilebi_wallboard_default_values(tenant_a):
    """Test default values for KioskWallboardDisplay fields."""
    display = KioskWallboardDisplay.objects.create(
        tenant=tenant_a,
        name="Operations Center Screen",
    )

    assert display.location_description == ""
    assert display.access_passcode == ""
    assert display.is_public_kiosk is False
    assert display.status == "active"
    assert display.playlist_items == []
    assert display.default_slide_duration_seconds == 30
    assert display.transition_effect == "fade"
    assert display.theme == "dark_navy"
    assert display.display_schedule == "continuous_24_7"
    assert display.operating_hours_json == {}
    assert display.auto_refresh_data_interval_seconds == 60
    assert display.last_heartbeat_at is None
    assert display.device_ip_address is None
    assert display.device_user_agent == ""
    assert display.kiosk_slug == "operations-center-screen"


@pytest.mark.django_db
def test_embeddedmobilebi_wallboard_unique_slug_generation_per_tenant(tenant_a, tenant_b):
    """Test unique kiosk_slug generation and collision resolution scoped per tenant."""
    w1 = _embeddedmobilebi_create_wallboard(tenant=tenant_a, name="Warehouse Wallboard")
    assert w1.kiosk_slug == "warehouse-wallboard"

    w2 = _embeddedmobilebi_create_wallboard(tenant=tenant_a, name="Warehouse Wallboard")
    assert w2.kiosk_slug == "warehouse-wallboard-1"

    w3 = _embeddedmobilebi_create_wallboard(tenant=tenant_a, name="Warehouse Wallboard")
    assert w3.kiosk_slug == "warehouse-wallboard-2"

    # Cross-tenant: tenant_b can reuse "warehouse-wallboard"
    w_b = _embeddedmobilebi_create_wallboard(tenant=tenant_b, name="Warehouse Wallboard")
    assert w_b.kiosk_slug == "warehouse-wallboard"

    # Re-saving preserves existing kiosk_slug
    w1.location_description = "Updated Aisle 4"
    w1.save()
    assert w1.kiosk_slug == "warehouse-wallboard"

    # Fallback for unslugifiable characters
    w_fallback = _embeddedmobilebi_create_wallboard(tenant=tenant_a, name="!!!")
    assert w_fallback.kiosk_slug.startswith("kiosk-display")


@pytest.mark.django_db
def test_embeddedmobilebi_wallboard_choices_and_indexes(tenant_a):
    """Test choices and composite indexes on KioskWallboardDisplay."""
    assert [c[0] for c in KioskWallboardDisplay.TRANSITION_EFFECT_CHOICES] == [
        "fade",
        "slide_horizontal",
        "zoom",
        "none",
    ]
    assert [c[0] for c in KioskWallboardDisplay.WALLBOARD_THEME_CHOICES] == [
        "dark_oled",
        "dark_navy",
        "light_high_contrast",
    ]
    assert [c[0] for c in KioskWallboardDisplay.DISPLAY_SCHEDULE_CHOICES] == [
        "continuous_24_7",
        "business_hours",
        "shift_work",
    ]
    assert [c[0] for c in KioskWallboardDisplay.STATUS_CHOICES] == [
        "active",
        "standby",
        "offline",
    ]

    index_names = {idx.name for idx in KioskWallboardDisplay._meta.indexes}
    assert "idx_wall_ten_stat" in index_names
    assert "idx_wall_ten_theme" in index_names
    assert "idx_wall_ten_schedule" in index_names
    assert "idx_wall_ten_heartbeat" in index_names
    assert "idx_wall_ten_created" in index_names


@pytest.mark.django_db
def test_embeddedmobilebi_wallboard_heartbeat_recording(tenant_a):
    """Test record_heartbeat method updates last_heartbeat_at, IP, and user-agent atomically."""
    display = _embeddedmobilebi_create_wallboard(tenant=tenant_a, name="Heartbeat Test Display")
    assert display.last_heartbeat_at is None

    test_ip = "192.168.10.45"
    test_ua = "NavERP-Kiosk-Client/1.0 (RaspberryPi; Linux armv7l)"
    display.record_heartbeat(ip_address=test_ip, user_agent=test_ua)

    display.refresh_from_db()
    assert display.last_heartbeat_at is not None
    assert (timezone.now() - display.last_heartbeat_at) < timedelta(seconds=5)
    assert display.device_ip_address == test_ip
    assert display.device_user_agent == test_ua

    # Truncate overly long user agent (max 250 characters)
    long_ua = "A" * 300
    display.record_heartbeat(ip_address=test_ip, user_agent=long_ua)
    display.refresh_from_db()
    assert len(display.device_user_agent) == 250


@pytest.mark.django_db
def test_embeddedmobilebi_wallboard_passcode_and_tenant_isolation(
    kiosk_wallboard_display_a, kiosk_wallboard_display_b, tenant_a, tenant_b
):
    """Test passcode matching via secrets.compare_digest and tenant isolation."""
    assert secrets.compare_digest(kiosk_wallboard_display_a.access_passcode, "WALL1234") is True
    assert secrets.compare_digest(kiosk_wallboard_display_a.access_passcode, "WRONGPASS") is False

    qs_a = KioskWallboardDisplay.objects.filter(tenant=tenant_a)
    qs_b = KioskWallboardDisplay.objects.filter(tenant=tenant_b)

    assert kiosk_wallboard_display_a in qs_a
    assert kiosk_wallboard_display_a not in qs_b
    assert kiosk_wallboard_display_b in qs_b
    assert kiosk_wallboard_display_b not in qs_a


# ===========================================================================
# 3. MobileBiConfiguration Model Tests (MOB)
# ===========================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_mobile_fixture_and_str(mobile_bi_config_a, admin_user, tenant_a):
    """Test MobileBiConfiguration fixture, string representation variants per I6, and prefix."""
    assert mobile_bi_config_a.pk is not None
    assert mobile_bi_config_a.number.startswith("MOB-")

    # Variant 1: target_user is loaded/cached in _state.fields_cache
    expected_str = f"{mobile_bi_config_a.number} - {mobile_bi_config_a.name} ({admin_user.username})"
    assert str(mobile_bi_config_a) == expected_str

    # Variant 2: target_user_id exists but relation is not in fields_cache (avoids N+1 query per I6)
    cfg_uncached = MobileBiConfiguration.objects.only("id", "number", "name", "target_user_id").get(
        pk=mobile_bi_config_a.pk
    )
    assert "target_user" not in cfg_uncached._state.fields_cache
    assert str(cfg_uncached) == f"{cfg_uncached.number} - {cfg_uncached.name} (User #{admin_user.id})"

    # Variant 3: No target_user, is_default_profile=True
    cfg_default = _embeddedmobilebi_create_mobile_config(
        tenant=tenant_a,
        name="Global Tenant Profile",
        target_user=None,
        is_default_profile=True,
    )
    assert str(cfg_default) == f"{cfg_default.number} - {cfg_default.name} (Tenant Default)"

    # Variant 4: No target_user, is_default_profile=False
    cfg_standard = _embeddedmobilebi_create_mobile_config(
        tenant=tenant_a,
        name="Generic Profile",
        target_user=None,
        is_default_profile=False,
    )
    assert str(cfg_standard) == f"{cfg_standard.number} - {cfg_standard.name}"


@pytest.mark.django_db
def test_embeddedmobilebi_mobile_default_values(tenant_a):
    """Test default values for MobileBiConfiguration fields."""
    config = MobileBiConfiguration.objects.create(
        tenant=tenant_a,
        name="Standard Field Mobile",
    )

    assert config.target_user is None
    assert config.is_default_profile is False
    assert config.status == "active"
    assert config.offline_caching_enabled is True
    assert config.cache_max_age_hours == 24
    assert config.max_cache_storage_mb == 100
    assert config.sync_on_wifi_only is False
    assert config.pinned_dashboard_ids == []
    assert config.pinned_report_ids == []
    assert config.touch_layout_preset == "comfortable"
    assert config.enable_push_insights is True
    assert config.push_digest_frequency == "daily_morning"
    assert config.require_biometric_lock is False
    assert config.inactivity_lock_minutes == 5
    assert config.last_synced_at is None


@pytest.mark.django_db
def test_embeddedmobilebi_mobile_single_default_profile_enforcement(tenant_a, tenant_b):
    """Test single-default profile enforcement per tenant in save() per M6."""
    p1 = _embeddedmobilebi_create_mobile_config(
        tenant=tenant_a,
        name="Profile Alpha",
        is_default_profile=True,
    )
    assert p1.is_default_profile is True

    # Creating a second default profile in tenant_a automatically resets p1
    p2 = _embeddedmobilebi_create_mobile_config(
        tenant=tenant_a,
        name="Profile Beta",
        is_default_profile=True,
    )
    p1.refresh_from_db()
    assert p1.is_default_profile is False
    assert p2.is_default_profile is True

    # Cross-tenant: tenant_b can have its own default profile without resetting tenant_a's p2
    p_b = _embeddedmobilebi_create_mobile_config(
        tenant=tenant_b,
        name="Globex Mobile Default",
        is_default_profile=True,
    )
    p2.refresh_from_db()
    assert p2.is_default_profile is True
    assert p_b.is_default_profile is True

    # Re-saving p2 does not unset itself
    p2.name = "Profile Beta Renamed"
    p2.save()
    p2.refresh_from_db()
    assert p2.is_default_profile is True


@pytest.mark.django_db
def test_embeddedmobilebi_mobile_pinned_ids_lists(tenant_a, bi_dashboard_a):
    """Test storing and retrieving pinned dashboard and report ID lists."""
    report_def = _embeddedmobilebi_create_report(tenant_a)
    cfg = _embeddedmobilebi_create_mobile_config(
        tenant=tenant_a,
        name="Executive Pinned Suite",
        pinned_dashboard_ids=[bi_dashboard_a.id, 999],
        pinned_report_ids=[report_def.id],
    )
    cfg.refresh_from_db()
    assert cfg.pinned_dashboard_ids == [bi_dashboard_a.id, 999]
    assert cfg.pinned_report_ids == [report_def.id]


@pytest.mark.django_db
def test_embeddedmobilebi_mobile_choices_and_tenant_isolation(
    mobile_bi_config_a, mobile_bi_config_b, tenant_a, tenant_b
):
    """Test choices, index definitions, and tenant isolation for MobileBiConfiguration."""
    assert [c[0] for c in MobileBiConfiguration.TOUCH_PRESET_CHOICES] == [
        "compact",
        "comfortable",
        "large_cards",
    ]
    assert [c[0] for c in MobileBiConfiguration.DIGEST_FREQUENCY_CHOICES] == [
        "realtime",
        "hourly",
        "daily_morning",
        "weekly",
        "disabled",
    ]
    assert [c[0] for c in MobileBiConfiguration.STATUS_CHOICES] == [
        "active",
        "inactive",
    ]

    index_names = {idx.name for idx in MobileBiConfiguration._meta.indexes}
    assert "idx_mob_ten_stat" in index_names
    assert "idx_mob_ten_usr" in index_names
    assert "idx_mob_ten_default" in index_names
    assert "idx_mob_ten_layout" in index_names
    assert "idx_mob_ten_digest" in index_names
    assert "idx_mob_ten_created" in index_names

    qs_a = MobileBiConfiguration.objects.filter(tenant=tenant_a)
    qs_b = MobileBiConfiguration.objects.filter(tenant=tenant_b)

    assert mobile_bi_config_a in qs_a
    assert mobile_bi_config_a not in qs_b
    assert mobile_bi_config_b in qs_b
    assert mobile_bi_config_b not in qs_a


# ===========================================================================
# 4. EmbedApiToken Model Tests (EAPI)
# ===========================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_token_fixture_and_str(embed_api_token_a):
    """Test EmbedApiToken fixture, string representation, and prefix."""
    assert embed_api_token_a.pk is not None
    assert embed_api_token_a.number.startswith("EAPI-")
    expected_str = f"{embed_api_token_a.number} - {embed_api_token_a.name} ({embed_api_token_a.token_prefix}...)"
    assert str(embed_api_token_a) == expected_str


@pytest.mark.django_db
def test_embeddedmobilebi_token_default_values(tenant_a):
    """Test default values for EmbedApiToken fields."""
    token = EmbedApiToken.objects.create(
        tenant=tenant_a,
        name="Default Token Test",
        token_hash="fakehash" * 8,
    )

    assert token.token_prefix == "eapi_live_"
    assert token.status == "active"
    assert token.scopes == []
    assert token.embedded_config is None
    assert token.injected_rls_context == {}
    assert token.allowed_ip_ranges == ""
    assert token.rate_limit_rpm == 120
    assert token.expires_at is None
    assert token.total_requests_count == 0
    assert token.last_used_at is None


@pytest.mark.django_db
def test_embeddedmobilebi_token_generate_secret_and_verify(tenant_a):
    """Test secret generation, hashing, and constant-time token verification."""
    raw_token, prefix, token_hash = EmbedApiToken.generate_secret()

    assert raw_token.startswith("eapi_live_")
    assert prefix == raw_token[:14]
    assert len(token_hash) == 64  # SHA-256 hex digest

    token = EmbedApiToken.objects.create(
        tenant=tenant_a,
        name="Production Partner SDK",
        token_prefix=prefix,
        token_hash=token_hash,
    )

    # Constant-time verify_token
    assert token.verify_token(raw_token) is True
    assert token.verify_token("eapi_live_invalidtoken1234567890") is False
    assert token.verify_token("") is False


@pytest.mark.django_db
def test_embeddedmobilebi_token_revoke_method(tenant_a):
    """Test token revocation method sets status to 'revoked'."""
    token = _embeddedmobilebi_create_token(tenant=tenant_a, name="Temporary Access Key")
    assert token.status == "active"

    token.revoke()
    token.refresh_from_db()
    assert token.status == "revoked"
    assert token.is_valid is False


@pytest.mark.django_db
def test_embeddedmobilebi_token_is_valid_property(tenant_a):
    """Test is_valid property across active, expired, and revoked states."""
    # Active without expiration -> valid
    token_valid = _embeddedmobilebi_create_token(
        tenant=tenant_a,
        name="Perpetual Key",
        status="active",
        expires_at=None,
    )
    assert token_valid.is_valid is True

    # Active with future expiration -> valid
    future_time = timezone.now() + timedelta(days=30)
    token_future = _embeddedmobilebi_create_token(
        tenant=tenant_a,
        name="Future Expiring Key",
        status="active",
        expires_at=future_time,
    )
    assert token_future.is_valid is True

    # Active with past expiration -> invalid
    past_time = timezone.now() - timedelta(minutes=5)
    token_expired_time = _embeddedmobilebi_create_token(
        tenant=tenant_a,
        name="Past Expired Key",
        status="active",
        expires_at=past_time,
    )
    assert token_expired_time.is_valid is False

    # Status explicitly set to 'expired' -> invalid
    token_status_expired = _embeddedmobilebi_create_token(
        tenant=tenant_a,
        name="Explicitly Expired Key",
        status="expired",
    )
    assert token_status_expired.is_valid is False

    # Status explicitly set to 'revoked' -> invalid
    token_revoked = _embeddedmobilebi_create_token(
        tenant=tenant_a,
        name="Revoked Key",
        status="revoked",
    )
    assert token_revoked.is_valid is False


@pytest.mark.django_db
def test_embeddedmobilebi_token_choices_and_tenant_isolation(
    embed_api_token_a, embed_api_token_b, tenant_a, tenant_b
):
    """Test choices and tenant isolation for EmbedApiToken."""
    assert [c[0] for c in EmbedApiToken.STATUS_CHOICES] == [
        "active",
        "expired",
        "revoked",
    ]

    qs_a = EmbedApiToken.objects.filter(tenant=tenant_a)
    qs_b = EmbedApiToken.objects.filter(tenant=tenant_b)

    assert embed_api_token_a in qs_a
    assert embed_api_token_a not in qs_b
    assert embed_api_token_b in qs_b
    assert embed_api_token_b not in qs_a

    # Uniqueness constraint on [tenant, number]
    with pytest.raises(IntegrityError):
        EmbedApiToken.objects.create(
            tenant=tenant_a,
            number=embed_api_token_a.number,
            name="Colliding Token Number",
            token_hash="fakehash" * 8,
        )
