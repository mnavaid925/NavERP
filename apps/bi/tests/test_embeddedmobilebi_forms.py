"""Unit tests for Sub-module 10.17 Embedded & Mobile BI forms.

Forms covered:
- EmbeddedAnalyticsConfigForm (EmbeddedAnalyticsConfig)
- KioskWallboardDisplayForm (KioskWallboardDisplay)
- MobileBiConfigurationForm (MobileBiConfiguration)
- EmbedApiTokenForm (EmbedApiToken)
"""
import json
import pytest
from django import forms

from apps.bi.forms import (
    EmbedApiTokenForm,
    EmbeddedAnalyticsConfigForm,
    KioskWallboardDisplayForm,
    MobileBiConfigurationForm,
)
from apps.bi.models import (
    BiDashboard,
    EmbedApiToken,
    EmbeddedAnalyticsConfig,
    KioskWallboardDisplay,
    MobileBiConfiguration,
    ReportDefinition,
    SemanticModel,
)


# ---------------------------------------------------------------------------
# Module Helpers (strictly prefixed with _embeddedmobilebi_)
# ---------------------------------------------------------------------------


def _embeddedmobilebi_create_report(tenant, name="Test Report", slug="test-report"):
    """Helper to create a ReportDefinition with valid minimal fields."""
    return ReportDefinition.objects.create(
        tenant=tenant,
        name=name,
        slug=slug,
        category="sales",
        report_type="standard_tabular",
        status="published",
    )


def _embeddedmobilebi_forms_valid_config_data(
    target_type="dashboard",
    dashboard=None,
    report=None,
    semantic_model=None,
    **kwargs,
):
    """Helper returning a valid data payload for EmbeddedAnalyticsConfigForm."""
    data = {
        "name": "Partner Portal Embed",
        "slug": "partner-portal-embed",
        "description": "Executive dashboard embedded into external vendor portal",
        "target_type": target_type,
        "embedding_mode": "iframe",
        "auth_mode": "signed_jwt",
        "status": "active",
        "allowed_origins": "https://portal.acme.com, https://app.acme.com",
        "theme_mode": "light",
        "primary_color": "#1e40af",
        "accent_color": "#3b82f6",
        "custom_css": ".portal-card { border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }",
        "enable_rls_filter": True,
        "default_rls_attributes_raw": '{"region": "North America", "tier": "Enterprise"}',
    }
    if dashboard:
        data["dashboard"] = dashboard.pk
    if report:
        data["report"] = report.pk
    if semantic_model:
        data["semantic_model"] = semantic_model.pk
    data.update(kwargs)
    return data


def _embeddedmobilebi_forms_valid_wallboard_data(**kwargs):
    """Helper returning a valid data payload for KioskWallboardDisplayForm."""
    data = {
        "name": "HQ Operations Command Wallboard",
        "location_description": "Ops Center Floor 3, Wall Display A",
        "kiosk_slug": "hq-operations-wallboard",
        "access_passcode": "WALLPASS123",
        "is_public_kiosk": True,
        "status": "active",
        "default_slide_duration_seconds": 30,
        "transition_effect": "fade",
        "theme": "dark_oled",
        "display_schedule": "continuous_24_7",
        "auto_refresh_data_interval_seconds": 300,
        "playlist_items_raw": json.dumps(
            [
                {"type": "dashboard", "id": 1, "title": "Revenue Real-Time", "duration_seconds": 30},
                {"type": "dashboard", "id": 2, "title": "Support Queue Status", "duration_seconds": 45},
            ]
        ),
        "operating_hours_raw": json.dumps(
            {"start": "06:00", "end": "22:00", "days": [1, 2, 3, 4, 5]}
        ),
    }
    data.update(kwargs)
    return data


def _embeddedmobilebi_forms_valid_mobile_data(target_user, **kwargs):
    """Helper returning a valid data payload for MobileBiConfigurationForm."""
    data = {
        "name": "Field Sales Exec Mobile Profile",
        "target_user": target_user.pk,
        "is_default_profile": False,
        "status": "active",
        "offline_caching_enabled": True,
        "cache_max_age_hours": 24,
        "max_cache_storage_mb": 500,
        "sync_on_wifi_only": True,
        "touch_layout_preset": "comfortable",
        "enable_push_insights": True,
        "push_digest_frequency": "daily_morning",
        "require_biometric_lock": True,
        "inactivity_lock_minutes": 15,
        "pinned_dashboard_ids_raw": "[]",
        "pinned_report_ids_raw": "[]",
    }
    data.update(kwargs)
    return data


def _embeddedmobilebi_forms_valid_token_data(embedded_config, **kwargs):
    """Helper returning a valid data payload for EmbedApiTokenForm."""
    data = {
        "name": "Production Portal SDK Token",
        "status": "active",
        "embedded_config": embedded_config.pk,
        "allowed_ip_ranges": "192.168.1.0/24, 10.0.0.0/8",
        "rate_limit_rpm": 120,
        "scopes_raw": "read:dashboard, embed:view, query:data",
        "injected_rls_context_raw": json.dumps(
            {"department": "Sales", "territory": "EMEA"}
        ),
    }
    data.update(kwargs)
    return data


# ===========================================================================
# 1. EmbeddedAnalyticsConfigForm Tests (EMB)
# ===========================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_system_fields_excluded():
    """Verify system fields (tenant, number, view_count, last_accessed_at, created_by, timestamps) are excluded."""
    form = EmbeddedAnalyticsConfigForm()
    excluded = [
        "tenant",
        "number",
        "view_count",
        "last_accessed_at",
        "created_by",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in EmbeddedAnalyticsConfigForm"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_tenant_scoping(
    tenant_a,
    tenant_b,
    bi_dashboard_a,
    bi_dashboard_b,
    semantic_model_a,
    semantic_model_b,
):
    """Verify ForeignKeys (dashboard, report, semantic_model) querysets only display tenant A records."""
    report_a = _embeddedmobilebi_create_report(tenant_a, name="Acme Scope Report", slug="acme-scope-rep")
    report_b = _embeddedmobilebi_create_report(tenant_b, name="Globex Scope Report", slug="globex-scope-rep")

    form = EmbeddedAnalyticsConfigForm(tenant=tenant_a)

    dash_qs = form.fields["dashboard"].queryset
    assert bi_dashboard_a in dash_qs
    assert bi_dashboard_b not in dash_qs

    rep_qs = form.fields["report"].queryset
    assert report_a in rep_qs
    assert report_b not in rep_qs

    sm_qs = form.fields["semantic_model"].queryset
    assert semantic_model_a in sm_qs
    assert semantic_model_b not in sm_qs


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_unscoped_initialization():
    """Verify form initializes safely without tenant without raising exceptions."""
    form = EmbeddedAnalyticsConfigForm(tenant=None)
    assert form.fields["dashboard"].required is False
    assert form.fields["report"].required is False
    assert form.fields["semantic_model"].required is False
    assert form.fields["default_rls_attributes_raw"].initial == "{}"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_initial_data_loading(
    tenant_a, embedded_analytics_config_a
):
    """Verify initial data for default_rls_attributes_raw is formatted from instance attributes."""
    embedded_analytics_config_a.default_rls_attributes = {"tier": "Enterprise", "geo": "US"}
    embedded_analytics_config_a.save()

    form = EmbeddedAnalyticsConfigForm(tenant=tenant_a, instance=embedded_analytics_config_a)
    initial_raw = form.fields["default_rls_attributes_raw"].initial
    parsed = json.loads(initial_raw)
    assert parsed == {"tier": "Enterprise", "geo": "US"}

    # When instance has empty attributes, defaults to "{}"
    embedded_analytics_config_a.default_rls_attributes = {}
    embedded_analytics_config_a.save()
    form_empty = EmbeddedAnalyticsConfigForm(tenant=tenant_a, instance=embedded_analytics_config_a)
    assert form_empty.fields["default_rls_attributes_raw"].initial == "{}"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_valid_dashboard_target_save(
    tenant_a, bi_dashboard_a
):
    """Verify valid form save with target_type='dashboard' persists correctly."""
    data = _embeddedmobilebi_forms_valid_config_data(
        target_type="dashboard",
        dashboard=bi_dashboard_a,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed: {form.errors}"
    config = form.save()

    assert config.tenant == tenant_a
    assert config.target_type == "dashboard"
    assert config.dashboard == bi_dashboard_a
    assert config.name == "Partner Portal Embed"
    assert config.default_rls_attributes == {"region": "North America", "tier": "Enterprise"}
    assert config.primary_color == "#1e40af"
    assert config.accent_color == "#3b82f6"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_valid_report_target_save(
    tenant_a
):
    """Verify valid form save with target_type='report' persists correctly."""
    report_a = _embeddedmobilebi_create_report(tenant_a, name="Acme Valid Report", slug="acme-valid-rep")
    data = _embeddedmobilebi_forms_valid_config_data(
        target_type="report",
        report=report_a,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed: {form.errors}"
    config = form.save()

    assert config.tenant == tenant_a
    assert config.target_type == "report"
    assert config.report == report_a


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_valid_semantic_model_target_save(
    tenant_a, semantic_model_a
):
    """Verify valid form save with target_type='semantic_model' persists correctly."""
    data = _embeddedmobilebi_forms_valid_config_data(
        target_type="semantic_model",
        semantic_model=semantic_model_a,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form validation failed: {form.errors}"
    config = form.save()

    assert config.tenant == tenant_a
    assert config.target_type == "semantic_model"
    assert config.semantic_model == semantic_model_a


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_target_type_missing_dashboard_error(tenant_a):
    """Verify target_type='dashboard' requires selecting a dashboard."""
    data = _embeddedmobilebi_forms_valid_config_data(
        target_type="dashboard",
        dashboard=None,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dashboard" in form.errors
    assert "Please select a Dashboard for Dashboard target type." in form.errors["dashboard"]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_target_type_missing_report_error(tenant_a):
    """Verify target_type='report' requires selecting an operational report."""
    data = _embeddedmobilebi_forms_valid_config_data(
        target_type="report",
        report=None,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "report" in form.errors
    assert "Please select an Operational Report for Report target type." in form.errors["report"]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_target_type_missing_semantic_model_error(tenant_a):
    """Verify target_type='semantic_model' requires selecting a semantic model."""
    data = _embeddedmobilebi_forms_valid_config_data(
        target_type="semantic_model",
        semantic_model=None,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors
    assert "Please select a Semantic Model for Semantic Model target type." in form.errors["semantic_model"]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_rejects_foreign_dashboard(
    tenant_a, bi_dashboard_b
):
    """Verify cross-tenant dashboard FK is rejected via reject_foreign."""
    data = _embeddedmobilebi_forms_valid_config_data(
        target_type="dashboard",
        dashboard=bi_dashboard_b,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dashboard" in form.errors
    assert any("another workspace" in str(e).lower() or "valid choice" in str(e).lower() for e in form.errors["dashboard"])


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_rejects_foreign_report(
    tenant_a, tenant_b
):
    """Verify cross-tenant report FK is rejected via reject_foreign."""
    foreign_report = _embeddedmobilebi_create_report(tenant_b, name="Globex Foreign Rep", slug="globex-foreign-rep")
    data = _embeddedmobilebi_forms_valid_config_data(
        target_type="report",
        report=foreign_report,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "report" in form.errors
    assert any("another workspace" in str(e).lower() or "valid choice" in str(e).lower() for e in form.errors["report"])


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_rejects_foreign_semantic_model(
    tenant_a, semantic_model_b
):
    """Verify cross-tenant semantic model FK is rejected via reject_foreign."""
    data = _embeddedmobilebi_forms_valid_config_data(
        target_type="semantic_model",
        semantic_model=semantic_model_b,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "semantic_model" in form.errors
    assert any("another workspace" in str(e).lower() or "valid choice" in str(e).lower() for e in form.errors["semantic_model"])


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_clean_custom_css_valid(
    tenant_a, bi_dashboard_a
):
    """Verify clean_custom_css accepts standard safe CSS definitions."""
    safe_css = """
    .chart-container { background-color: #f8fafc; border: 1px solid #e2e8f0; }
    h2.title { font-size: 1.25rem; font-weight: 600; color: #1e293b; }
    """
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        custom_css=safe_css,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Valid CSS unexpectedly failed: {form.errors}"
    assert form.cleaned_data["custom_css"] == safe_css.strip()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "malicious_css",
    [
        "<script>alert('XSS')</script>",
        "<SCRIPT src='evil.js'></SCRIPT>",
        "</script><script>alert(1)</script>",
        "body { color: red; } </script>",
    ],
)
def test_embeddedmobilebi_forms_config_clean_custom_css_rejects_script_tags(
    tenant_a, bi_dashboard_a, malicious_css
):
    """Verify clean_custom_css strictly rejects script tags (C3 security fix)."""
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        custom_css=malicious_css,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "custom_css" in form.errors
    assert "HTML or script tags and executable expressions are not allowed" in form.errors["custom_css"][0]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "malicious_css",
    [
        "<style>body { background: black; }</style>",
        "</style><img src=x onerror=alert(1)>",
        "<STYLE>.hack { display: none; }</STYLE>",
        "</STYLE><script>steal()</script>",
    ],
)
def test_embeddedmobilebi_forms_config_clean_custom_css_rejects_style_tags(
    tenant_a, bi_dashboard_a, malicious_css
):
    """Verify clean_custom_css strictly rejects opening and closing style tags (C3 security fix)."""
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        custom_css=malicious_css,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "custom_css" in form.errors
    assert "HTML or script tags and executable expressions are not allowed" in form.errors["custom_css"][0]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "malicious_css",
    [
        "background-image: url(javascript:alert(1));",
        "background-image: url(JAVASCRIPT:alert(1));",
        "width: expression(alert('exploited'));",
        "height: EXPRESSION(document.cookie);",
    ],
)
def test_embeddedmobilebi_forms_config_clean_custom_css_rejects_javascript_and_expressions(
    tenant_a, bi_dashboard_a, malicious_css
):
    """Verify clean_custom_css rejects javascript: URI schemes and CSS expressions."""
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        custom_css=malicious_css,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "custom_css" in form.errors
    assert "HTML or script tags and executable expressions are not allowed" in form.errors["custom_css"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("valid_hex", ["#1e40af", "#3b82f6", "#000000", "#FFFFFF", "#123456", "#abcdef"])
def test_embeddedmobilebi_forms_config_clean_primary_color_valid(
    tenant_a, bi_dashboard_a, valid_hex
):
    """Verify clean_primary_color accepts valid 6-char hex color codes (M7 fix)."""
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        primary_color=valid_hex,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Valid hex {valid_hex} failed: {form.errors}"
    assert form.cleaned_data["primary_color"] == valid_hex


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_hex", ["red", "#fff", "#1234567", "123456", "#12345g", "#", "#12", "rgb(0,0,0)"])
def test_embeddedmobilebi_forms_config_clean_primary_color_invalid_formats(
    tenant_a, bi_dashboard_a, invalid_hex
):
    """Verify clean_primary_color rejects invalid hex color strings (M7 fix)."""
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        primary_color=invalid_hex,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "primary_color" in form.errors
    assert "Primary color must be a valid 6-character hex code" in form.errors["primary_color"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("valid_hex", ["#10b981", "#ef4444", "#ffffff", "#0f172a"])
def test_embeddedmobilebi_forms_config_clean_accent_color_valid(
    tenant_a, bi_dashboard_a, valid_hex
):
    """Verify clean_accent_color accepts valid 6-char hex color codes (M7 fix)."""
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        accent_color=valid_hex,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Valid accent hex {valid_hex} failed: {form.errors}"
    assert form.cleaned_data["accent_color"] == valid_hex


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_hex", ["blue", "#123", "#12345678", "transparent", "#zzzzzz"])
def test_embeddedmobilebi_forms_config_clean_accent_color_invalid_formats(
    tenant_a, bi_dashboard_a, invalid_hex
):
    """Verify clean_accent_color rejects invalid hex color strings (M7 fix)."""
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        accent_color=invalid_hex,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "accent_color" in form.errors
    assert "Accent color must be a valid 6-character hex code" in form.errors["accent_color"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_default_rls_attributes_valid_json(
    tenant_a, bi_dashboard_a
):
    """Verify valid JSON dictionary in default_rls_attributes_raw is parsed into instance."""
    rls_json = '{"org_id": 105, "role": "manager", "regions": ["North", "South"]}'
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        default_rls_attributes_raw=rls_json,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    config = form.save()
    assert config.default_rls_attributes == {
        "org_id": 105,
        "role": "manager",
        "regions": ["North", "South"],
    }


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_default_rls_attributes_invalid_syntax(
    tenant_a, bi_dashboard_a
):
    """Verify invalid JSON syntax triggers a validation error on default_rls_attributes_raw."""
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        default_rls_attributes_raw='{"region": "North America", unclosed',
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "default_rls_attributes_raw" in form.errors
    assert "Invalid JSON syntax" in form.errors["default_rls_attributes_raw"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("non_dict_json", ['["array", "not", "dict"]', '"string_value"', "12345", "true"])
def test_embeddedmobilebi_forms_config_default_rls_attributes_non_dict_rejected(
    tenant_a, bi_dashboard_a, non_dict_json
):
    """Verify non-dictionary JSON inputs are rejected with descriptive error."""
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        default_rls_attributes_raw=non_dict_json,
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "default_rls_attributes_raw" in form.errors
    assert "RLS attributes must be a JSON object (dictionary)." in form.errors["default_rls_attributes_raw"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_config_default_rls_attributes_empty(
    tenant_a, bi_dashboard_a
):
    """Verify empty default_rls_attributes_raw defaults to an empty dictionary."""
    data = _embeddedmobilebi_forms_valid_config_data(
        dashboard=bi_dashboard_a,
        default_rls_attributes_raw="",
    )
    form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    config = form.save()
    assert config.default_rls_attributes == {}


# ===========================================================================
# 2. KioskWallboardDisplayForm Tests (WALL)
# ===========================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_system_fields_excluded():
    """Verify system fields (tenant, number, last_heartbeat_at, device telemetry, created_by, timestamps) are excluded."""
    form = KioskWallboardDisplayForm()
    excluded = [
        "tenant",
        "number",
        "slug",
        "last_heartbeat_at",
        "device_ip_address",
        "device_user_agent",
        "created_by",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in KioskWallboardDisplayForm"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_unscoped_initialization():
    """Verify form initializes safely with tenant=None."""
    form = KioskWallboardDisplayForm(tenant=None)
    assert form.fields["playlist_items_raw"].initial == "[]"
    assert form.fields["operating_hours_raw"].initial == "{}"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_initial_data_loading(
    tenant_a, kiosk_wallboard_display_a
):
    """Verify initial data for playlist_items_raw and operating_hours_raw loads from instance."""
    kiosk_wallboard_display_a.playlist_items = [
        {"type": "dashboard", "id": 10, "title": "Plant Yield", "duration_seconds": 60}
    ]
    kiosk_wallboard_display_a.operating_hours_json = {"start": "07:00", "end": "19:00"}
    kiosk_wallboard_display_a.save()

    form = KioskWallboardDisplayForm(tenant=tenant_a, instance=kiosk_wallboard_display_a)
    assert json.loads(form.fields["playlist_items_raw"].initial) == [
        {"type": "dashboard", "id": 10, "title": "Plant Yield", "duration_seconds": 60}
    ]
    assert json.loads(form.fields["operating_hours_raw"].initial) == {
        "start": "07:00",
        "end": "19:00",
    }

    # When instance has empty fields
    kiosk_wallboard_display_a.playlist_items = []
    kiosk_wallboard_display_a.operating_hours_json = {}
    kiosk_wallboard_display_a.save()
    form_empty = KioskWallboardDisplayForm(tenant=tenant_a, instance=kiosk_wallboard_display_a)
    assert form_empty.fields["playlist_items_raw"].initial == "[]"
    assert form_empty.fields["operating_hours_raw"].initial == "{}"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_valid_save(tenant_a):
    """Verify valid form save correctly populates model fields and parsed JSON structures."""
    data = _embeddedmobilebi_forms_valid_wallboard_data()
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    display = form.save()

    assert display.tenant == tenant_a
    assert display.name == "HQ Operations Command Wallboard"
    assert display.kiosk_slug == "hq-operations-wallboard"
    assert display.access_passcode == "WALLPASS123"
    assert display.is_public_kiosk is True
    assert display.theme == "dark_oled"
    assert display.default_slide_duration_seconds == 30
    assert len(display.playlist_items) == 2
    assert display.playlist_items[0]["title"] == "Revenue Real-Time"
    assert display.operating_hours_json["start"] == "06:00"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_playlist_items_valid_json(tenant_a):
    """Verify valid JSON list parses into instance.playlist_items."""
    items = [{"type": "dashboard", "id": 5, "duration_seconds": 20}]
    data = _embeddedmobilebi_forms_valid_wallboard_data(
        playlist_items_raw=json.dumps(items)
    )
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    display = form.save()
    assert display.playlist_items == items


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_playlist_items_invalid_json_syntax(tenant_a):
    """Verify malformed JSON syntax in playlist_items_raw triggers form error."""
    data = _embeddedmobilebi_forms_valid_wallboard_data(
        playlist_items_raw="[{'unquoted': key}]"
    )
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "playlist_items_raw" in form.errors
    assert "Invalid JSON syntax in playlist" in form.errors["playlist_items_raw"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("non_list_json", ['{"type": "dashboard"}', '"just_string"', "99", "false"])
def test_embeddedmobilebi_forms_wallboard_playlist_items_non_list_rejected(
    tenant_a, non_list_json
):
    """Verify non-list JSON in playlist_items_raw is rejected with a validation error."""
    data = _embeddedmobilebi_forms_valid_wallboard_data(
        playlist_items_raw=non_list_json
    )
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "playlist_items_raw" in form.errors
    assert "Playlist items must be a JSON array of slide objects." in form.errors["playlist_items_raw"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_playlist_items_empty(tenant_a):
    """Verify empty playlist_items_raw defaults to an empty list."""
    data = _embeddedmobilebi_forms_valid_wallboard_data(
        playlist_items_raw=""
    )
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    display = form.save()
    assert display.playlist_items == []


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_operating_hours_valid_json(tenant_a):
    """Verify valid JSON dictionary parses into instance.operating_hours_json."""
    hours = {"timezone": "UTC", "open": "08:00", "close": "18:00"}
    data = _embeddedmobilebi_forms_valid_wallboard_data(
        operating_hours_raw=json.dumps(hours)
    )
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    display = form.save()
    assert display.operating_hours_json == hours


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_operating_hours_invalid_json_syntax(tenant_a):
    """Verify invalid JSON syntax in operating_hours_raw triggers a validation error."""
    data = _embeddedmobilebi_forms_valid_wallboard_data(
        operating_hours_raw='{"start": "08:00", unclosed'
    )
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operating_hours_raw" in form.errors
    assert "Invalid JSON syntax in operating hours" in form.errors["operating_hours_raw"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("non_dict_json", ['["08:00", "18:00"]', '"always_open"', "100", "true"])
def test_embeddedmobilebi_forms_wallboard_operating_hours_non_dict_rejected(
    tenant_a, non_dict_json
):
    """Verify non-dictionary JSON in operating_hours_raw is rejected."""
    data = _embeddedmobilebi_forms_valid_wallboard_data(
        operating_hours_raw=non_dict_json
    )
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "operating_hours_raw" in form.errors
    assert "Operating hours must be a JSON object." in form.errors["operating_hours_raw"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_operating_hours_empty(tenant_a):
    """Verify empty operating_hours_raw defaults to an empty dict."""
    data = _embeddedmobilebi_forms_valid_wallboard_data(
        operating_hours_raw=""
    )
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    display = form.save()
    assert display.operating_hours_json == {}


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_slide_duration_negative_rejected(tenant_a):
    """Verify negative slide duration fails validation on PositiveIntegerField."""
    data = _embeddedmobilebi_forms_valid_wallboard_data(
        default_slide_duration_seconds=-5
    )
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "default_slide_duration_seconds" in form.errors


@pytest.mark.django_db
def test_embeddedmobilebi_forms_wallboard_auto_refresh_negative_rejected(tenant_a):
    """Verify negative refresh interval fails validation on PositiveIntegerField."""
    data = _embeddedmobilebi_forms_valid_wallboard_data(
        auto_refresh_data_interval_seconds=-60
    )
    form = KioskWallboardDisplayForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "auto_refresh_data_interval_seconds" in form.errors


# ===========================================================================
# 3. MobileBiConfigurationForm Tests (MOB)
# ===========================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_system_fields_excluded():
    """Verify system fields (tenant, number, slug, last_synced_at, created_by, timestamps) are excluded."""
    form = MobileBiConfigurationForm()
    excluded = [
        "tenant",
        "number",
        "slug",
        "last_synced_at",
        "created_by",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in MobileBiConfigurationForm"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_target_user_scoping(
    tenant_a, tenant_b, admin_user, admin_user_b
):
    """Verify target_user dropdown queryset only contains users from tenant A."""
    form = MobileBiConfigurationForm(tenant=tenant_a)
    user_qs = form.fields["target_user"].queryset
    assert admin_user in user_qs
    assert admin_user_b not in user_qs


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_unscoped_initialization():
    """Verify form initializes safely without tenant without raising exceptions."""
    form = MobileBiConfigurationForm(tenant=None)
    assert form.fields["target_user"].required is False
    assert form.fields["pinned_dashboard_ids_raw"].initial == "[]"
    assert form.fields["pinned_report_ids_raw"].initial == "[]"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_initial_data_loading(
    tenant_a, mobile_bi_config_a, bi_dashboard_a
):
    """Verify initial data for pinned dashboard and report raw fields load from instance."""
    mobile_bi_config_a.pinned_dashboard_ids = [bi_dashboard_a.pk]
    mobile_bi_config_a.pinned_report_ids = [42]
    mobile_bi_config_a.save()

    form = MobileBiConfigurationForm(tenant=tenant_a, instance=mobile_bi_config_a)
    assert json.loads(form.fields["pinned_dashboard_ids_raw"].initial) == [bi_dashboard_a.pk]
    assert json.loads(form.fields["pinned_report_ids_raw"].initial) == [42]

    # When instance has empty lists
    mobile_bi_config_a.pinned_dashboard_ids = []
    mobile_bi_config_a.pinned_report_ids = []
    mobile_bi_config_a.save()
    form_empty = MobileBiConfigurationForm(tenant=tenant_a, instance=mobile_bi_config_a)
    assert form_empty.fields["pinned_dashboard_ids_raw"].initial == "[]"
    assert form_empty.fields["pinned_report_ids_raw"].initial == "[]"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_valid_save(
    tenant_a, admin_user, bi_dashboard_a
):
    """Verify valid mobile profile form saves correctly with pinned dashboard and report IDs."""
    report_a = _embeddedmobilebi_create_report(tenant_a, name="Acme Mobile Rep", slug="acme-mob-rep")
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_dashboard_ids_raw=f"[{bi_dashboard_a.pk}]",
        pinned_report_ids_raw=f"[{report_a.pk}]",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    config = form.save()

    assert config.tenant == tenant_a
    assert config.name == "Field Sales Exec Mobile Profile"
    assert config.target_user == admin_user
    assert config.pinned_dashboard_ids == [bi_dashboard_a.pk]
    assert config.pinned_report_ids == [report_a.pk]
    assert config.offline_caching_enabled is True
    assert config.cache_max_age_hours == 24
    assert config.touch_layout_preset == "comfortable"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_rejects_foreign_target_user(
    tenant_a, admin_user_b
):
    """Verify target_user belonging to another tenant is rejected by reject_foreign."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user_b,
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "target_user" in form.errors
    assert any("another workspace" in str(e).lower() or "valid choice" in str(e).lower() for e in form.errors["target_user"])


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_pinned_dashboards_valid(
    tenant_a, admin_user, bi_dashboard_a
):
    """Verify valid tenant dashboard IDs in pinned_dashboard_ids_raw pass validation (M9 fix)."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_dashboard_ids_raw=f"[{bi_dashboard_a.pk}]",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    config = form.save()
    assert config.pinned_dashboard_ids == [bi_dashboard_a.pk]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_pinned_dashboards_rejects_foreign_tenant_dashboards(
    tenant_a, admin_user, bi_dashboard_b
):
    """Verify pinned dashboard IDs from another workspace are strictly rejected in clean() (M9 fix)."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_dashboard_ids_raw=f"[{bi_dashboard_b.pk}]",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pinned_dashboard_ids_raw" in form.errors
    assert "The following dashboard IDs do not exist in your tenant" in form.errors["pinned_dashboard_ids_raw"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_pinned_dashboards_rejects_nonexistent_ids(
    tenant_a, admin_user
):
    """Verify non-existent dashboard IDs are rejected in clean() (M9 fix)."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_dashboard_ids_raw="[999999]",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pinned_dashboard_ids_raw" in form.errors
    assert "The following dashboard IDs do not exist in your tenant" in form.errors["pinned_dashboard_ids_raw"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("non_list_input", ['{"id": 1}', '"dashboard_1"', "42", "true"])
def test_embeddedmobilebi_forms_mobile_pinned_dashboards_rejects_non_list(
    tenant_a, admin_user, non_list_input
):
    """Verify non-array JSON inputs are rejected with descriptive error."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_dashboard_ids_raw=non_list_input,
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pinned_dashboard_ids_raw" in form.errors
    assert "Must be a JSON array of numeric integer IDs." in form.errors["pinned_dashboard_ids_raw"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_elements", ['["dash_1", "dash_2"]', '[1, "two", 3]', "[1.5, 2.7]"])
def test_embeddedmobilebi_forms_mobile_pinned_dashboards_rejects_non_integer_elements(
    tenant_a, admin_user, invalid_elements
):
    """Verify arrays containing non-integer elements are rejected."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_dashboard_ids_raw=invalid_elements,
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pinned_dashboard_ids_raw" in form.errors
    assert "Must be a JSON array of numeric integer IDs." in form.errors["pinned_dashboard_ids_raw"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_pinned_dashboards_invalid_syntax(
    tenant_a, admin_user
):
    """Verify invalid JSON syntax triggers syntax error."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_dashboard_ids_raw="[1, 2,",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pinned_dashboard_ids_raw" in form.errors
    assert "Invalid JSON syntax" in form.errors["pinned_dashboard_ids_raw"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_pinned_dashboards_empty(
    tenant_a, admin_user
):
    """Verify empty pinned_dashboard_ids_raw defaults to an empty list."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_dashboard_ids_raw="",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    config = form.save()
    assert config.pinned_dashboard_ids == []


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_pinned_reports_valid(
    tenant_a, admin_user
):
    """Verify valid tenant report IDs in pinned_report_ids_raw pass validation (M9 fix)."""
    report_a = _embeddedmobilebi_create_report(tenant_a, name="Acme Pinned Report", slug="acme-pinned-rep")
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_report_ids_raw=f"[{report_a.pk}]",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    config = form.save()
    assert config.pinned_report_ids == [report_a.pk]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_pinned_reports_rejects_foreign_tenant_reports(
    tenant_a, tenant_b, admin_user
):
    """Verify pinned report IDs from another workspace are strictly rejected in clean() (M9 fix)."""
    report_b = _embeddedmobilebi_create_report(tenant_b, name="Globex Pinned Report", slug="globex-pinned-rep")
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_report_ids_raw=f"[{report_b.pk}]",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pinned_report_ids_raw" in form.errors
    assert "The following report IDs do not exist in your tenant" in form.errors["pinned_report_ids_raw"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_pinned_reports_rejects_nonexistent_ids(
    tenant_a, admin_user
):
    """Verify non-existent report IDs are rejected in clean() (M9 fix)."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_report_ids_raw="[888888]",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pinned_report_ids_raw" in form.errors
    assert "The following report IDs do not exist in your tenant" in form.errors["pinned_report_ids_raw"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("non_list_input", ['{"report": 1}', '"report_1"', "99", "false"])
def test_embeddedmobilebi_forms_mobile_pinned_reports_rejects_non_list(
    tenant_a, admin_user, non_list_input
):
    """Verify non-array JSON inputs are rejected for pinned reports."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_report_ids_raw=non_list_input,
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pinned_report_ids_raw" in form.errors
    assert "Must be a JSON array of numeric integer IDs." in form.errors["pinned_report_ids_raw"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("invalid_elements", ['["rep_a"]', '[10, "bad"]', "[2.2]"])
def test_embeddedmobilebi_forms_mobile_pinned_reports_rejects_non_integer_elements(
    tenant_a, admin_user, invalid_elements
):
    """Verify report arrays containing non-integer elements are rejected."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_report_ids_raw=invalid_elements,
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pinned_report_ids_raw" in form.errors
    assert "Must be a JSON array of numeric integer IDs." in form.errors["pinned_report_ids_raw"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_pinned_reports_invalid_syntax(
    tenant_a, admin_user
):
    """Verify invalid JSON syntax triggers syntax error on pinned reports."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_report_ids_raw="[1, 2, {unclosed",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "pinned_report_ids_raw" in form.errors
    assert "Invalid JSON syntax" in form.errors["pinned_report_ids_raw"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_mobile_pinned_reports_empty(
    tenant_a, admin_user
):
    """Verify empty pinned_report_ids_raw defaults to an empty list."""
    data = _embeddedmobilebi_forms_valid_mobile_data(
        target_user=admin_user,
        pinned_report_ids_raw="",
    )
    form = MobileBiConfigurationForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    config = form.save()
    assert config.pinned_report_ids == []


# ===========================================================================
# 4. EmbedApiTokenForm Tests (EAPI)
# ===========================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_system_and_secret_fields_excluded():
    """Verify system and secret fields (tenant, number, token_hash, token_prefix, last_used_at, created_by) are excluded (L20)."""
    form = EmbedApiTokenForm()
    excluded = [
        "tenant",
        "number",
        "token_prefix",
        "token_hash",
        "total_requests_count",
        "last_used_at",
        "created_by",
        "created_at",
        "updated_at",
    ]
    for field in excluded:
        assert field not in form.fields, f"Security violation: {field} exposed in EmbedApiTokenForm"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_tenant_scoping(
    tenant_a, tenant_b, embedded_analytics_config_a, embedded_analytics_config_b
):
    """Verify embedded_config dropdown only displays configs from tenant A."""
    form = EmbedApiTokenForm(tenant=tenant_a)
    config_qs = form.fields["embedded_config"].queryset
    assert embedded_analytics_config_a in config_qs
    assert embedded_analytics_config_b not in config_qs


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_unscoped_initialization():
    """Verify form initializes safely with tenant=None."""
    form = EmbedApiTokenForm(tenant=None)
    assert form.fields["embedded_config"].required is False
    assert form.fields["scopes_raw"].initial == "read:dashboard, embed:view, query:data"
    assert form.fields["injected_rls_context_raw"].initial == "{}"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_initial_data_loading(
    tenant_a, embed_api_token_a
):
    """Verify initial data for scopes_raw and injected_rls_context_raw loads from instance."""
    embed_api_token_a.scopes = ["read:dashboard", "read:kpi", "export:pdf"]
    embed_api_token_a.injected_rls_context = {"cost_center": "CC-901"}
    embed_api_token_a.save()

    form = EmbedApiTokenForm(tenant=tenant_a, instance=embed_api_token_a)
    assert form.fields["scopes_raw"].initial == "read:dashboard, read:kpi, export:pdf"
    assert json.loads(form.fields["injected_rls_context_raw"].initial) == {"cost_center": "CC-901"}

    # When instance has empty RLS context
    embed_api_token_a.injected_rls_context = {}
    embed_api_token_a.save()
    form_empty = EmbedApiTokenForm(tenant=tenant_a, instance=embed_api_token_a)
    assert form_empty.fields["injected_rls_context_raw"].initial == "{}"


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_valid_save(
    tenant_a, embedded_analytics_config_a
):
    """Verify valid form save correctly populates model fields and parsed scopes/RLS context."""
    data = _embeddedmobilebi_forms_valid_token_data(
        embedded_config=embedded_analytics_config_a,
    )
    form = EmbedApiTokenForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    token = form.save()

    assert token.tenant == tenant_a
    assert token.name == "Production Portal SDK Token"
    assert token.embedded_config == embedded_analytics_config_a
    assert token.allowed_ip_ranges == "192.168.1.0/24, 10.0.0.0/8"
    assert token.rate_limit_rpm == 120
    assert token.scopes == ["read:dashboard", "embed:view", "query:data"]
    assert token.injected_rls_context == {"department": "Sales", "territory": "EMEA"}


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_rejects_foreign_embedded_config(
    tenant_a, embedded_analytics_config_b
):
    """Verify cross-tenant embedded_config is rejected via reject_foreign."""
    data = _embeddedmobilebi_forms_valid_token_data(
        embedded_config=embedded_analytics_config_b,
    )
    form = EmbedApiTokenForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "embedded_config" in form.errors
    assert any("another workspace" in str(e).lower() or "valid choice" in str(e).lower() for e in form.errors["embedded_config"])


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_scopes_comma_separated_parsing(
    tenant_a, embedded_analytics_config_a
):
    """Verify comma-separated string in scopes_raw is parsed into a list of scope strings."""
    data = _embeddedmobilebi_forms_valid_token_data(
        embedded_config=embedded_analytics_config_a,
        scopes_raw="read:dashboard, read:report, embed:render, export:csv",
    )
    form = EmbedApiTokenForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    token = form.save()
    assert token.scopes == ["read:dashboard", "read:report", "embed:render", "export:csv"]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_scopes_json_array_parsing(
    tenant_a, embedded_analytics_config_a
):
    """Verify JSON array string in scopes_raw is parsed into a list of scope strings."""
    data = _embeddedmobilebi_forms_valid_token_data(
        embedded_config=embedded_analytics_config_a,
        scopes_raw='["read:dashboard", "embed:view", "query:ad_hoc"]',
    )
    form = EmbedApiTokenForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    token = form.save()
    assert token.scopes == ["read:dashboard", "embed:view", "query:ad_hoc"]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_scopes_empty_default(
    tenant_a, embedded_analytics_config_a
):
    """Verify empty scopes_raw falls back to safe default scopes."""
    data = _embeddedmobilebi_forms_valid_token_data(
        embedded_config=embedded_analytics_config_a,
        scopes_raw="",
    )
    form = EmbedApiTokenForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    token = form.save()
    assert token.scopes == ["read:dashboard", "embed:view"]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_injected_rls_valid_json(
    tenant_a, embedded_analytics_config_a
):
    """Verify valid JSON dictionary parses into instance.injected_rls_context."""
    rls_data = {"branch_code": "NYC-01", "classification": "restricted"}
    data = _embeddedmobilebi_forms_valid_token_data(
        embedded_config=embedded_analytics_config_a,
        injected_rls_context_raw=json.dumps(rls_data),
    )
    form = EmbedApiTokenForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    token = form.save()
    assert token.injected_rls_context == rls_data


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_injected_rls_invalid_syntax(
    tenant_a, embedded_analytics_config_a
):
    """Verify invalid JSON syntax triggers a validation error on injected_rls_context_raw."""
    data = _embeddedmobilebi_forms_valid_token_data(
        embedded_config=embedded_analytics_config_a,
        injected_rls_context_raw='{"branch": "NYC", broken',
    )
    form = EmbedApiTokenForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "injected_rls_context_raw" in form.errors
    assert "Invalid JSON syntax in RLS context" in form.errors["injected_rls_context_raw"][0]


@pytest.mark.django_db
@pytest.mark.parametrize("non_dict_json", ['["finance", "marketing"]', '"single_string"', "500", "false"])
def test_embeddedmobilebi_forms_token_injected_rls_non_dict_rejected(
    tenant_a, embedded_analytics_config_a, non_dict_json
):
    """Verify non-dictionary JSON is rejected for injected_rls_context_raw."""
    data = _embeddedmobilebi_forms_valid_token_data(
        embedded_config=embedded_analytics_config_a,
        injected_rls_context_raw=non_dict_json,
    )
    form = EmbedApiTokenForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "injected_rls_context_raw" in form.errors
    assert "RLS context must be a JSON dictionary." in form.errors["injected_rls_context_raw"][0]


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_injected_rls_empty(
    tenant_a, embedded_analytics_config_a
):
    """Verify empty injected_rls_context_raw defaults to an empty dictionary."""
    data = _embeddedmobilebi_forms_valid_token_data(
        embedded_config=embedded_analytics_config_a,
        injected_rls_context_raw="",
    )
    form = EmbedApiTokenForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    token = form.save()
    assert token.injected_rls_context == {}


@pytest.mark.django_db
def test_embeddedmobilebi_forms_token_rate_limit_rpm_negative_rejected(
    tenant_a, embedded_analytics_config_a
):
    """Verify negative rate_limit_rpm fails validation on PositiveIntegerField."""
    data = _embeddedmobilebi_forms_valid_token_data(
        embedded_config=embedded_analytics_config_a,
        rate_limit_rpm=-10,
    )
    form = EmbedApiTokenForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "rate_limit_rpm" in form.errors
