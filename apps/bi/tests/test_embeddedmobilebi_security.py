"""Security and multi-tenant isolation unit tests for Sub-module 10.17 Embedded & Mobile BI.

Verifies:
1. Multi-tenant Isolation & IDOR Protection:
   - Comprehensive cross-tenant tests across all 4 entities: detail, edit, delete, preview, player, heartbeat, and revoke endpoints with Tenant B's PK accessed by Tenant A client -> assert 404.
   - List queryset isolation (no cross-tenant leakage between tenants).
   - Form-level cross-tenant foreign key injection rejection (dashboard, report, semantic_model, embedded_config, target_user, pinned IDs).
2. Authentication & Role-Based Access Control:
   - Unauthenticated requests to staff endpoints redirect to login (302).
   - Non-admin tenant member denied on create, edit, delete, revoke (403 via @tenant_admin_required) while GET list/detail succeeds (200).
   - POST-only enforcement on delete, revoke, and heartbeat (GET returns 405).
3. Stored XSS Prevention:
   - custom_css validation & rendering: <script>, </style>, javascript:, expression( rejected in form and stripped in preview template.
   - Kiosk player playlist JSON escaping: slide titles with </script><script> safely contained in json_script.
4. Secret & Token Cryptographic Integrity:
   - API token secrets: plaintext never stored in DB (only SHA-256 hash); verified with verify_token.
   - Plaintext key exposed once via session pop, never in messages or forms.
   - Secret fields (token_hash, token_prefix) excluded from ModelForm.
   - Kiosk passcode verification constant-time check.
5. Audit Trail Verification:
   - AuditLog entries created on all mutations with valid user, object, action, and tenant.
"""
import hashlib
import json
import secrets
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.bi.forms.EmbeddedMobileBi.EmbedApiTokens import EmbedApiTokenForm
from apps.bi.forms.EmbeddedMobileBi.EmbeddedAnalyticsConfigs import EmbeddedAnalyticsConfigForm
from apps.bi.forms.EmbeddedMobileBi.KioskWallboardDisplays import KioskWallboardDisplayForm
from apps.bi.forms.EmbeddedMobileBi.MobileBiConfigurations import MobileBiConfigurationForm
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.EmbeddedMobileBi.EmbedApiTokens import EmbedApiToken
from apps.bi.models.EmbeddedMobileBi.EmbeddedAnalyticsConfigs import EmbeddedAnalyticsConfig
from apps.bi.models.EmbeddedMobileBi.KioskWallboardDisplays import KioskWallboardDisplay
from apps.bi.models.EmbeddedMobileBi.MobileBiConfigurations import MobileBiConfiguration
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.SemanticLayer.SemanticModels import SemanticModel
from apps.core.models import AuditLog

User = get_user_model()


# ==============================================================================
# Module Helpers (strictly prefixed with _embeddedmobilebi_security_)
# ==============================================================================


def _embeddedmobilebi_security_create_embed_config(tenant, user=None, **kwargs):
    """Helper to create a tenant-scoped EmbeddedAnalyticsConfig."""
    defaults = {
        "tenant": tenant,
        "name": f"Security Embed Config {timezone.now().timestamp()}",
        "slug": f"sec-embed-{timezone.now().timestamp()}",
        "target_type": "dashboard",
        "embedding_mode": "iframe",
        "auth_mode": "signed_jwt",
        "theme_mode": "light",
        "primary_color": "#1e40af",
        "accent_color": "#3b82f6",
        "status": "active",
        "created_by": user,
    }
    defaults.update(kwargs)
    return EmbeddedAnalyticsConfig.objects.create(**defaults)


def _embeddedmobilebi_security_create_kiosk_display(tenant, user=None, **kwargs):
    """Helper to create a tenant-scoped KioskWallboardDisplay."""
    defaults = {
        "tenant": tenant,
        "name": f"Security Kiosk Display {timezone.now().timestamp()}",
        "kiosk_slug": f"sec-kiosk-{timezone.now().timestamp()}",
        "theme": "dark_oled",
        "transition_effect": "fade",
        "display_schedule": "continuous_24_7",
        "default_slide_duration_seconds": 30,
        "auto_refresh_data_interval_seconds": 300,
        "status": "active",
        "is_public_kiosk": False,
        "playlist_items": [{"type": "dashboard", "title": "Overview", "duration_seconds": 30}],
        "created_by": user,
    }
    defaults.update(kwargs)
    return KioskWallboardDisplay.objects.create(**defaults)


def _embeddedmobilebi_security_create_mobile_config(tenant, user=None, **kwargs):
    """Helper to create a tenant-scoped MobileBiConfiguration."""
    defaults = {
        "tenant": tenant,
        "name": f"Security Mobile Config {timezone.now().timestamp()}",
        "touch_layout_preset": "comfortable",
        "push_digest_frequency": "weekly",
        "offline_caching_enabled": True,
        "cache_max_age_hours": 12,
        "max_cache_storage_mb": 100,
        "inactivity_lock_minutes": 15,
        "status": "active",
        "created_by": user,
    }
    defaults.update(kwargs)
    return MobileBiConfiguration.objects.create(**defaults)


def _embeddedmobilebi_security_create_api_token(tenant, config=None, user=None, **kwargs):
    """Helper to create a tenant-scoped EmbedApiToken with valid hash."""
    raw_secret, prefix, token_hash = EmbedApiToken.generate_secret()
    defaults = {
        "tenant": tenant,
        "name": f"Security API Token {timezone.now().timestamp()}",
        "embedded_config": config,
        "token_prefix": prefix,
        "token_hash": token_hash,
        "scopes": ["read:dashboard", "embed:render"],
        "rate_limit_rpm": 120,
        "status": "active",
        "created_by": user,
    }
    defaults.update(kwargs)
    token = EmbedApiToken.objects.create(**defaults)
    token._raw_secret_for_test = raw_secret
    return token


def _embeddedmobilebi_security_create_report(tenant, user=None, name="Security Test Report", slug="sec-test-report"):
    """Helper to create a tenant-scoped ReportDefinition with valid schema."""
    return ReportDefinition.objects.create(
        tenant=tenant,
        created_by=user,
        name=name,
        slug=slug,
        category="sales",
        report_type="standard_tabular",
        status="published",
    )


# ==============================================================================
# 1. Multi-Tenant Isolation & IDOR Protection
# ==============================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_security_embedded_config_cross_tenant_idor(
    client_a, embedded_analytics_config_b
):
    """Assert Tenant A client receives 404 for all Tenant B EmbeddedAnalyticsConfig endpoints."""
    pk = embedded_analytics_config_b.pk
    detail_url = reverse("bi:embedded_analytics_config_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:embedded_analytics_config_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:embedded_analytics_config_delete", kwargs={"pk": pk})
    preview_url = reverse("bi:embedded_analytics_config_preview", kwargs={"pk": pk})

    # Detail, edit GET, preview GET return 404
    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404
    assert client_a.get(preview_url).status_code == 404

    # Edit POST and Delete POST return 404
    assert client_a.post(edit_url, data={"name": "Hacked Embed Config"}).status_code == 404
    assert client_a.post(delete_url).status_code == 404

    # Verify object was not deleted or altered
    embedded_analytics_config_b.refresh_from_db()
    assert embedded_analytics_config_b.name != "Hacked Embed Config"


@pytest.mark.django_db
def test_embeddedmobilebi_security_kiosk_display_cross_tenant_idor(
    client_a, kiosk_wallboard_display_b
):
    """Assert Tenant A client receives 404 for all Tenant B KioskWallboardDisplay endpoints."""
    pk = kiosk_wallboard_display_b.pk
    detail_url = reverse("bi:kiosk_wallboard_display_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:kiosk_wallboard_display_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:kiosk_wallboard_display_delete", kwargs={"pk": pk})
    player_url = reverse("bi:kiosk_wallboard_display_player", kwargs={"pk": pk})
    heartbeat_url = reverse("bi:kiosk_wallboard_display_heartbeat", kwargs={"pk": pk})

    # Detail, edit GET return 404
    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404

    # Private kiosk display player accessed by Tenant A client returns 404
    assert client_a.get(player_url).status_code == 404

    # Mutating endpoints return 404
    assert client_a.post(edit_url, data={"name": "Hacked Wallboard"}).status_code == 404
    assert client_a.post(delete_url).status_code == 404

    # Heartbeat for foreign private display returns 404 JSON
    hb_resp = client_a.post(heartbeat_url)
    assert hb_resp.status_code == 404
    assert hb_resp.json().get("status") == "error"

    # Verify object was not deleted or altered
    kiosk_wallboard_display_b.refresh_from_db()
    assert kiosk_wallboard_display_b.name != "Hacked Wallboard"


@pytest.mark.django_db
def test_embeddedmobilebi_security_mobile_config_cross_tenant_idor(
    client_a, mobile_bi_config_b
):
    """Assert Tenant A client receives 404 for all Tenant B MobileBiConfiguration endpoints."""
    pk = mobile_bi_config_b.pk
    detail_url = reverse("bi:mobile_bi_config_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:mobile_bi_config_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:mobile_bi_config_delete", kwargs={"pk": pk})

    # Detail, edit GET return 404
    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404

    # Edit POST and Delete POST return 404
    assert client_a.post(edit_url, data={"name": "Hacked Mobile Profile"}).status_code == 404
    assert client_a.post(delete_url).status_code == 404

    # Verify object was not deleted or altered
    mobile_bi_config_b.refresh_from_db()
    assert mobile_bi_config_b.name != "Hacked Mobile Profile"


@pytest.mark.django_db
def test_embeddedmobilebi_security_embed_api_token_cross_tenant_idor(
    client_a, embed_api_token_b
):
    """Assert Tenant A client receives 404 for all Tenant B EmbedApiToken endpoints."""
    pk = embed_api_token_b.pk
    detail_url = reverse("bi:embed_api_token_detail", kwargs={"pk": pk})
    edit_url = reverse("bi:embed_api_token_edit", kwargs={"pk": pk})
    delete_url = reverse("bi:embed_api_token_delete", kwargs={"pk": pk})
    revoke_url = reverse("bi:embed_api_token_revoke", kwargs={"pk": pk})

    # Detail, edit GET return 404
    assert client_a.get(detail_url).status_code == 404
    assert client_a.get(edit_url).status_code == 404

    # Edit POST, Delete POST, Revoke POST return 404
    assert client_a.post(edit_url, data={"name": "Hacked Token"}).status_code == 404
    assert client_a.post(delete_url).status_code == 404
    assert client_a.post(revoke_url).status_code == 404

    # Verify object was not deleted or revoked
    embed_api_token_b.refresh_from_db()
    assert embed_api_token_b.status == "active"
    assert embed_api_token_b.name != "Hacked Token"


@pytest.mark.django_db
def test_embeddedmobilebi_security_list_querysets_tenant_isolated(
    client_a,
    embedded_analytics_config_a,
    embedded_analytics_config_b,
    kiosk_wallboard_display_a,
    kiosk_wallboard_display_b,
    mobile_bi_config_a,
    mobile_bi_config_b,
    embed_api_token_a,
    embed_api_token_b,
):
    """Assert Tenant A list views only render Tenant A entities and strictly exclude Tenant B."""
    # 1. Embedded Analytics Config list
    resp1 = client_a.get(reverse("bi:embedded_analytics_config_list"))
    assert resp1.status_code == 200
    configs = list(resp1.context["configs"])
    assert embedded_analytics_config_a in configs
    assert embedded_analytics_config_b not in configs

    # 2. Kiosk Wallboard Display list
    resp2 = client_a.get(reverse("bi:kiosk_wallboard_display_list"))
    assert resp2.status_code == 200
    displays = list(resp2.context["displays"])
    assert kiosk_wallboard_display_a in displays
    assert kiosk_wallboard_display_b not in displays

    # 3. Mobile BI Config list
    resp3 = client_a.get(reverse("bi:mobile_bi_config_list"))
    assert resp3.status_code == 200
    m_configs = list(resp3.context["configs"])
    assert mobile_bi_config_a in m_configs
    assert mobile_bi_config_b not in m_configs

    # 4. Embed API Token list
    resp4 = client_a.get(reverse("bi:embed_api_token_list"))
    assert resp4.status_code == 200
    tokens = list(resp4.context["tokens"])
    assert embed_api_token_a in tokens
    assert embed_api_token_b not in tokens


@pytest.mark.django_db
def test_embeddedmobilebi_security_form_fk_injection_rejection_embedded_config(
    tenant_a,
    tenant_b,
    admin_user,
    admin_user_b,
    bi_dashboard_a,
    bi_dashboard_b,
    semantic_model_a,
    semantic_model_b,
):
    """Assert EmbeddedAnalyticsConfigForm rejects cross-tenant foreign key injection."""
    report_a = _embeddedmobilebi_security_create_report(tenant=tenant_a, user=admin_user, slug="rep-a")
    report_b = _embeddedmobilebi_security_create_report(tenant=tenant_b, user=admin_user_b, slug="rep-b")

    # Verify queryset filtering in form __init__
    form = EmbeddedAnalyticsConfigForm(tenant=tenant_a)
    assert bi_dashboard_a in form.fields["dashboard"].queryset
    assert bi_dashboard_b not in form.fields["dashboard"].queryset
    assert report_a in form.fields["report"].queryset
    assert report_b not in form.fields["report"].queryset
    assert semantic_model_a in form.fields["semantic_model"].queryset
    assert semantic_model_b not in form.fields["semantic_model"].queryset

    # Attempt cross-tenant Dashboard injection
    post_data_dash = {
        "name": "Malicious Dashboard Embed",
        "slug": "malicious-dash-embed",
        "target_type": "dashboard",
        "dashboard": bi_dashboard_b.pk,
        "embedding_mode": "iframe",
        "auth_mode": "sso_passthrough",
        "theme_mode": "light",
        "primary_color": "#1e40af",
        "accent_color": "#3b82f6",
        "status": "active",
    }
    form_dash = EmbeddedAnalyticsConfigForm(data=post_data_dash, tenant=tenant_a)
    assert not form_dash.is_valid()
    assert "dashboard" in form_dash.errors or "__all__" in form_dash.errors

    # Attempt cross-tenant Report injection
    post_data_rep = {
        "name": "Malicious Report Embed",
        "slug": "malicious-rep-embed",
        "target_type": "report",
        "report": report_b.pk,
        "embedding_mode": "iframe",
        "auth_mode": "sso_passthrough",
        "theme_mode": "light",
        "primary_color": "#1e40af",
        "accent_color": "#3b82f6",
        "status": "active",
    }
    form_rep = EmbeddedAnalyticsConfigForm(data=post_data_rep, tenant=tenant_a)
    assert not form_rep.is_valid()
    assert "report" in form_rep.errors or "__all__" in form_rep.errors

    # Attempt cross-tenant SemanticModel injection
    post_data_model = {
        "name": "Malicious Model Embed",
        "slug": "malicious-model-embed",
        "target_type": "semantic_model",
        "semantic_model": semantic_model_b.pk,
        "embedding_mode": "web_component",
        "auth_mode": "signed_jwt",
        "theme_mode": "light",
        "primary_color": "#1e40af",
        "accent_color": "#3b82f6",
        "status": "active",
    }
    form_model = EmbeddedAnalyticsConfigForm(data=post_data_model, tenant=tenant_a)
    assert not form_model.is_valid()
    assert "semantic_model" in form_model.errors or "__all__" in form_model.errors


@pytest.mark.django_db
def test_embeddedmobilebi_security_form_fk_injection_rejection_api_token(
    tenant_a, embedded_analytics_config_a, embedded_analytics_config_b
):
    """Assert EmbedApiTokenForm rejects cross-tenant embedded_config injection."""
    form = EmbedApiTokenForm(tenant=tenant_a)
    assert embedded_analytics_config_a in form.fields["embedded_config"].queryset
    assert embedded_analytics_config_b not in form.fields["embedded_config"].queryset

    post_data = {
        "name": "Injected Config Token",
        "status": "active",
        "embedded_config": embedded_analytics_config_b.pk,
        "scopes_raw": "read:dashboard, embed:view",
        "rate_limit_rpm": 60,
    }
    bound_form = EmbedApiTokenForm(data=post_data, tenant=tenant_a)
    assert not bound_form.is_valid()
    assert "embedded_config" in bound_form.errors or "__all__" in bound_form.errors


@pytest.mark.django_db
def test_embeddedmobilebi_security_form_fk_injection_rejection_mobile_config(
    tenant_a, tenant_b, admin_user, admin_user_b, bi_dashboard_a, bi_dashboard_b
):
    """Assert MobileBiConfigurationForm rejects foreign target_user and cross-tenant pinned IDs."""
    report_b = _embeddedmobilebi_security_create_report(tenant=tenant_b, user=admin_user_b, slug="rep-mob-b")

    form = MobileBiConfigurationForm(tenant=tenant_a)
    assert admin_user in form.fields["target_user"].queryset
    assert admin_user_b not in form.fields["target_user"].queryset

    # 1. Foreign target_user injection
    post_data_user = {
        "name": "Foreign Target Profile",
        "target_user": admin_user_b.pk,
        "touch_layout_preset": "comfortable",
        "push_digest_frequency": "weekly",
        "status": "active",
    }
    form_user = MobileBiConfigurationForm(data=post_data_user, tenant=tenant_a)
    assert not form_user.is_valid()
    assert "target_user" in form_user.errors or "__all__" in form_user.errors

    # 2. Cross-tenant pinned dashboard ID injection
    post_data_dash = {
        "name": "Cross-Tenant Pinned Dashboards",
        "target_user": admin_user.pk,
        "touch_layout_preset": "comfortable",
        "push_digest_frequency": "weekly",
        "status": "active",
        "pinned_dashboard_ids_raw": json.dumps([bi_dashboard_a.pk, bi_dashboard_b.pk]),
    }
    form_dash = MobileBiConfigurationForm(data=post_data_dash, tenant=tenant_a)
    assert not form_dash.is_valid()
    assert "pinned_dashboard_ids_raw" in form_dash.errors

    # 3. Cross-tenant pinned report ID injection
    post_data_rep = {
        "name": "Cross-Tenant Pinned Reports",
        "target_user": admin_user.pk,
        "touch_layout_preset": "comfortable",
        "push_digest_frequency": "weekly",
        "status": "active",
        "pinned_report_ids_raw": json.dumps([report_b.pk]),
    }
    form_rep = MobileBiConfigurationForm(data=post_data_rep, tenant=tenant_a)
    assert not form_rep.is_valid()
    assert "pinned_report_ids_raw" in form_rep.errors


# ==============================================================================
# 2. Authentication & Role-Based Access Control
# ==============================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_security_unauthenticated_staff_endpoints_redirect_login(
    anon_client,
    embedded_analytics_config_a,
    kiosk_wallboard_display_a,
    mobile_bi_config_a,
    embed_api_token_a,
):
    """Assert unauthenticated requests to staff routes are redirected to login (302)."""
    cfg_pk = embedded_analytics_config_a.pk
    wall_pk = kiosk_wallboard_display_a.pk
    mob_pk = mobile_bi_config_a.pk
    tok_pk = embed_api_token_a.pk

    protected_urls = [
        # EmbeddedAnalyticsConfig
        reverse("bi:embedded_analytics_config_list"),
        reverse("bi:embedded_analytics_config_create"),
        reverse("bi:embedded_analytics_config_detail", kwargs={"pk": cfg_pk}),
        reverse("bi:embedded_analytics_config_edit", kwargs={"pk": cfg_pk}),
        reverse("bi:embedded_analytics_config_delete", kwargs={"pk": cfg_pk}),
        reverse("bi:embedded_analytics_config_preview", kwargs={"pk": cfg_pk}),
        # KioskWallboardDisplay staff routes
        reverse("bi:kiosk_wallboard_display_list"),
        reverse("bi:kiosk_wallboard_display_create"),
        reverse("bi:kiosk_wallboard_display_detail", kwargs={"pk": wall_pk}),
        reverse("bi:kiosk_wallboard_display_edit", kwargs={"pk": wall_pk}),
        reverse("bi:kiosk_wallboard_display_delete", kwargs={"pk": wall_pk}),
        # MobileBiConfiguration
        reverse("bi:mobile_bi_config_list"),
        reverse("bi:mobile_bi_config_create"),
        reverse("bi:mobile_bi_config_detail", kwargs={"pk": mob_pk}),
        reverse("bi:mobile_bi_config_edit", kwargs={"pk": mob_pk}),
        reverse("bi:mobile_bi_config_delete", kwargs={"pk": mob_pk}),
        # EmbedApiToken
        reverse("bi:embed_api_token_list"),
        reverse("bi:embed_api_token_create"),
        reverse("bi:embed_api_token_detail", kwargs={"pk": tok_pk}),
        reverse("bi:embed_api_token_edit", kwargs={"pk": tok_pk}),
        reverse("bi:embed_api_token_delete", kwargs={"pk": tok_pk}),
        reverse("bi:embed_api_token_revoke", kwargs={"pk": tok_pk}),
    ]

    for url in protected_urls:
        resp = anon_client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for {url}, got {resp.status_code}"
        assert "/login/" in resp.url, f"Expected login redirect for {url}, got {resp.url}"


@pytest.mark.django_db
def test_embeddedmobilebi_security_non_admin_member_denied_on_mutations_403(
    member_client,
    embedded_analytics_config_a,
    kiosk_wallboard_display_a,
    mobile_bi_config_a,
    embed_api_token_a,
):
    """Assert non-admin tenant member receives HTTP 403 on create, edit, delete, and revoke."""
    cfg_pk = embedded_analytics_config_a.pk
    wall_pk = kiosk_wallboard_display_a.pk
    mob_pk = mobile_bi_config_a.pk
    tok_pk = embed_api_token_a.pk

    mutation_checks = [
        # Create GET & POST
        ("GET", reverse("bi:embedded_analytics_config_create"), None),
        ("POST", reverse("bi:embedded_analytics_config_create"), {"name": "Test"}),
        ("GET", reverse("bi:kiosk_wallboard_display_create"), None),
        ("POST", reverse("bi:kiosk_wallboard_display_create"), {"name": "Test"}),
        ("GET", reverse("bi:mobile_bi_config_create"), None),
        ("POST", reverse("bi:mobile_bi_config_create"), {"name": "Test"}),
        ("GET", reverse("bi:embed_api_token_create"), None),
        ("POST", reverse("bi:embed_api_token_create"), {"name": "Test"}),
        # Edit GET & POST
        ("GET", reverse("bi:embedded_analytics_config_edit", kwargs={"pk": cfg_pk}), None),
        ("POST", reverse("bi:embedded_analytics_config_edit", kwargs={"pk": cfg_pk}), {"name": "Update"}),
        ("GET", reverse("bi:kiosk_wallboard_display_edit", kwargs={"pk": wall_pk}), None),
        ("POST", reverse("bi:kiosk_wallboard_display_edit", kwargs={"pk": wall_pk}), {"name": "Update"}),
        ("GET", reverse("bi:mobile_bi_config_edit", kwargs={"pk": mob_pk}), None),
        ("POST", reverse("bi:mobile_bi_config_edit", kwargs={"pk": mob_pk}), {"name": "Update"}),
        ("GET", reverse("bi:embed_api_token_edit", kwargs={"pk": tok_pk}), None),
        ("POST", reverse("bi:embed_api_token_edit", kwargs={"pk": tok_pk}), {"name": "Update"}),
        # Delete POST
        ("POST", reverse("bi:embedded_analytics_config_delete", kwargs={"pk": cfg_pk}), None),
        ("POST", reverse("bi:kiosk_wallboard_display_delete", kwargs={"pk": wall_pk}), None),
        ("POST", reverse("bi:mobile_bi_config_delete", kwargs={"pk": mob_pk}), None),
        ("POST", reverse("bi:embed_api_token_delete", kwargs={"pk": tok_pk}), None),
        # Revoke POST
        ("POST", reverse("bi:embed_api_token_revoke", kwargs={"pk": tok_pk}), None),
    ]

    for method, url, data in mutation_checks:
        if method == "GET":
            resp = member_client.get(url)
        else:
            resp = member_client.post(url, data=data or {})
        assert resp.status_code == 403, (
            f"Expected 403 Forbidden for non-admin member on {method} {url}, got {resp.status_code}"
        )


@pytest.mark.django_db
def test_embeddedmobilebi_security_non_admin_member_allowed_read_views_200(
    member_client,
    embedded_analytics_config_a,
    kiosk_wallboard_display_a,
    mobile_bi_config_a,
    embed_api_token_a,
):
    """Assert standard non-admin tenant member can view list and detail pages (200 OK)."""
    cfg_pk = embedded_analytics_config_a.pk
    wall_pk = kiosk_wallboard_display_a.pk
    mob_pk = mobile_bi_config_a.pk
    tok_pk = embed_api_token_a.pk

    read_urls = [
        reverse("bi:embedded_analytics_config_list"),
        reverse("bi:embedded_analytics_config_detail", kwargs={"pk": cfg_pk}),
        reverse("bi:embedded_analytics_config_preview", kwargs={"pk": cfg_pk}),
        reverse("bi:kiosk_wallboard_display_list"),
        reverse("bi:kiosk_wallboard_display_detail", kwargs={"pk": wall_pk}),
        reverse("bi:mobile_bi_config_list"),
        reverse("bi:mobile_bi_config_detail", kwargs={"pk": mob_pk}),
        reverse("bi:embed_api_token_list"),
        reverse("bi:embed_api_token_detail", kwargs={"pk": tok_pk}),
    ]

    for url in read_urls:
        resp = member_client.get(url)
        assert resp.status_code == 200, (
            f"Expected 200 OK for non-admin member reading {url}, got {resp.status_code}"
        )


@pytest.mark.django_db
def test_embeddedmobilebi_security_post_only_enforcement_405(
    client_a,
    embedded_analytics_config_a,
    kiosk_wallboard_display_a,
    mobile_bi_config_a,
    embed_api_token_a,
):
    """Assert GET requests to mutating POST-only endpoints return HTTP 405 Method Not Allowed."""
    cfg_pk = embedded_analytics_config_a.pk
    wall_pk = kiosk_wallboard_display_a.pk
    mob_pk = mobile_bi_config_a.pk
    tok_pk = embed_api_token_a.pk

    post_only_urls = [
        reverse("bi:embedded_analytics_config_delete", kwargs={"pk": cfg_pk}),
        reverse("bi:kiosk_wallboard_display_delete", kwargs={"pk": wall_pk}),
        reverse("bi:kiosk_wallboard_display_heartbeat", kwargs={"pk": wall_pk}),
        reverse("bi:mobile_bi_config_delete", kwargs={"pk": mob_pk}),
        reverse("bi:embed_api_token_delete", kwargs={"pk": tok_pk}),
        reverse("bi:embed_api_token_revoke", kwargs={"pk": tok_pk}),
    ]

    for url in post_only_urls:
        resp = client_a.get(url)
        assert resp.status_code == 405, (
            f"Expected 405 Method Not Allowed on GET {url}, got {resp.status_code}"
        )


# ==============================================================================
# 3. Stored XSS Prevention
# ==============================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_security_custom_css_xss_injection_rejected_in_form(tenant_a, bi_dashboard_a):
    """Assert EmbeddedAnalyticsConfigForm rejects dangerous script/style tags in custom_css."""
    base_data = {
        "name": "CSS Security Test",
        "slug": "css-sec-test",
        "target_type": "dashboard",
        "dashboard": bi_dashboard_a.pk,
        "embedding_mode": "iframe",
        "auth_mode": "sso_passthrough",
        "theme_mode": "light",
        "primary_color": "#1e40af",
        "accent_color": "#3b82f6",
        "status": "active",
    }

    malicious_payloads = [
        "<script>alert('xss')</script>",
        "</style><script>alert('breakout')</script>",
        "<style>body { background: red; }</style>",
        "body { background-image: url('javascript:alert(1)'); }",
        "div { width: expression(alert(1)); }",
        "/* comment */ <SCRIPT SRC='http://evil.com/xss.js'></SCRIPT>",
    ]

    for payload in malicious_payloads:
        data = base_data.copy()
        data["custom_css"] = payload
        form = EmbeddedAnalyticsConfigForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Form unexpectedly accepted dangerous custom_css payload: {payload}"
        assert "custom_css" in form.errors

    # Verify benign custom CSS is cleanly accepted
    safe_data = base_data.copy()
    safe_data["custom_css"] = ".custom-dashboard-card { border-radius: 8px; border: 1px solid #e2e8f0; }"
    safe_form = EmbeddedAnalyticsConfigForm(data=safe_data, tenant=tenant_a)
    assert safe_form.is_valid(), f"Safe CSS failed form validation: {safe_form.errors}"


@pytest.mark.django_db
def test_embeddedmobilebi_security_custom_css_striptags_rendering_in_preview(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Assert preview template filters custom_css through striptags, neutralizing residual HTML."""
    # Create configuration with raw payload stored directly in DB (simulating legacy/imported data)
    config = _embeddedmobilebi_security_create_embed_config(
        tenant=tenant_a,
        user=admin_user,
        dashboard=bi_dashboard_a,
        custom_css="body { font-size: 14px; } <script>alert('pwned')</script> /* clean */",
    )

    url = reverse("bi:embedded_analytics_config_preview", kwargs={"pk": config.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    html = resp.content.decode("utf-8")
    assert "<script>alert('pwned')</script>" not in html
    # Verify that <script> tags were completely removed by striptags
    assert "<script" not in html[html.find("<style>"):html.find("</style>")]


@pytest.mark.django_db
def test_embeddedmobilebi_security_kiosk_player_playlist_json_escaping(
    client_a, tenant_a, admin_user
):
    """Assert Kiosk player safely escapes script closing tags in playlist items via json_script."""
    xss_title = '</script><script>alert("wallboard-xss")</script>'
    display = _embeddedmobilebi_security_create_kiosk_display(
        tenant=tenant_a,
        user=admin_user,
        playlist_items=[
            {
                "type": "dashboard",
                "title": xss_title,
                "duration_seconds": 25,
            }
        ],
    )

    url = reverse("bi:kiosk_wallboard_display_player", kwargs={"pk": display.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200

    html = resp.content.decode("utf-8")
    # Verify literal raw tag is NOT closing the script block
    assert '</script><script>alert("wallboard-xss")</script>' not in html
    # json_script encodes '<' as '\u003C' and '>' as '\u003E'
    assert r"\u003C/script\u003E\u003Cscript\u003E" in html


# ==============================================================================
# 4. Secret & Token Cryptographic Integrity
# ==============================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_security_api_token_hash_storage_and_verification(
    tenant_a, admin_user, embedded_analytics_config_a
):
    """Assert API token secrets are SHA-256 hashed, plaintext is never stored in DB, and verification works."""
    raw_token, prefix, token_hash = EmbedApiToken.generate_secret()

    # Verify cryptographic properties
    assert raw_token.startswith("eapi_live_")
    assert prefix == raw_token[:14]
    assert len(token_hash) == 64
    assert hashlib.sha256(raw_token.encode("utf-8")).hexdigest() == token_hash

    # Save to database
    token = EmbedApiToken.objects.create(
        tenant=tenant_a,
        name="Security Integrity Token",
        embedded_config=embedded_analytics_config_a,
        token_prefix=prefix,
        token_hash=token_hash,
        scopes=["read:dashboard"],
        created_by=admin_user,
    )

    # Verification checks
    assert token.verify_token(raw_token) is True
    assert token.verify_token("eapi_live_tamperedkey1234567890abcdef") is False
    assert token.verify_token("") is False
    assert token.verify_token(raw_token + "trailing") is False

    # DB direct inspection: ensure raw_token is not stored anywhere
    raw_db_row = EmbedApiToken.objects.filter(pk=token.pk).values().first()
    for col_name, col_value in raw_db_row.items():
        assert raw_token != str(col_value), f"Plaintext secret token leaked into DB column {col_name}!"


@pytest.mark.django_db
def test_embeddedmobilebi_security_token_secret_session_pop_single_exposure(
    client_a, tenant_a, embedded_analytics_config_a
):
    """Assert token plaintext is exposed strictly once via session pop and never persisted."""
    create_url = reverse("bi:embed_api_token_create")
    post_data = {
        "name": "One-Time Secret Token",
        "embedded_config": embedded_analytics_config_a.pk,
        "status": "active",
        "scopes_raw": "read:dashboard, embed:view",
        "rate_limit_rpm": 100,
    }

    # Generate token via creation view
    resp_create = client_a.post(create_url, data=post_data)
    assert resp_create.status_code == 302
    created_token = EmbedApiToken.objects.filter(name="One-Time Secret Token").first()
    assert created_token is not None

    detail_url = reverse("bi:embed_api_token_detail", kwargs={"pk": created_token.pk})

    # First GET view: session secret popped and shown in one-time banner
    resp_first = client_a.get(detail_url)
    assert resp_first.status_code == 200
    assert resp_first.context["new_key"] is not None
    secret_key = resp_first.context["new_key"]
    assert secret_key.startswith("eapi_live_")
    assert secret_key in resp_first.content.decode("utf-8")

    # Second GET view: session is now empty, secret is completely gone, masked prefix is shown
    resp_second = client_a.get(detail_url)
    assert resp_second.status_code == 200
    assert resp_second.context["new_key"] is None
    assert secret_key not in resp_second.content.decode("utf-8")
    assert f"{created_token.token_prefix}••••••••••••••••••••" in resp_second.content.decode("utf-8")


@pytest.mark.django_db
def test_embeddedmobilebi_security_token_hash_excluded_from_model_form(tenant_a):
    """Assert sensitive cryptographic fields (token_hash, token_prefix) are excluded from form fields."""
    form = EmbedApiTokenForm(tenant=tenant_a)
    assert "token_hash" not in form.fields
    assert "token_prefix" not in form.fields

    # Attempt to mass-assign forged token_hash via POST
    forged_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    forged_data = {
        "name": "Tampered Hash Test",
        "status": "active",
        "scopes_raw": "read:dashboard",
        "rate_limit_rpm": 60,
        "token_hash": forged_hash,
        "token_prefix": "eapi_live_hack",
    }
    bound_form = EmbedApiTokenForm(data=forged_data, tenant=tenant_a)
    assert bound_form.is_valid()
    inst = bound_form.save(commit=False)
    # The form does not set token_hash or token_prefix
    assert inst.token_hash != forged_hash
    assert inst.token_prefix != "eapi_live_hack"


@pytest.mark.django_db
def test_embeddedmobilebi_security_kiosk_passcode_constant_time_verification(
    anon_client, tenant_a, admin_user
):
    """Assert kiosk passcode is verified via constant-time compare_digest for player and heartbeat."""
    correct_pin = "WALL987654"
    kiosk = _embeddedmobilebi_security_create_kiosk_display(
        tenant=tenant_a,
        user=admin_user,
        is_public_kiosk=True,
        access_passcode=correct_pin,
    )

    player_url = reverse("bi:kiosk_wallboard_display_player", kwargs={"pk": kiosk.pk})
    heartbeat_url = reverse("bi:kiosk_wallboard_display_heartbeat", kwargs={"pk": kiosk.pk})

    # 1. Player access tests
    # No passcode -> 404
    assert anon_client.get(player_url).status_code == 404
    # Wrong passcode -> 404
    assert anon_client.get(f"{player_url}?passcode=WRONGPIN").status_code == 404
    # Correct passcode -> 200
    assert anon_client.get(f"{player_url}?passcode={correct_pin}").status_code == 200

    # 2. Heartbeat access tests
    # No passcode -> 404
    hb_none = anon_client.post(heartbeat_url)
    assert hb_none.status_code == 404
    # Wrong passcode -> 404
    hb_wrong = anon_client.post(f"{heartbeat_url}?passcode=INVALID")
    assert hb_wrong.status_code == 404
    # Correct passcode via query parameter -> 200
    hb_param = anon_client.post(f"{heartbeat_url}?passcode={correct_pin}")
    assert hb_param.status_code == 200
    assert hb_param.json().get("status") == "ok"
    # Correct passcode via X-Kiosk-Passcode header -> 200
    hb_header = anon_client.post(heartbeat_url, HTTP_X_KIOSK_PASSCODE=correct_pin)
    assert hb_header.status_code == 200
    assert hb_header.json().get("status") == "ok"


# ==============================================================================
# 5. Audit Trail Verification
# ==============================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_security_audit_log_embedded_config_mutations(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Assert AuditLog records create, update, and delete actions for EmbeddedAnalyticsConfig."""
    # 1. Create action
    create_url = reverse("bi:embedded_analytics_config_create")
    post_data = {
        "name": "Audit Tracked Embed",
        "slug": "audit-tracked-embed",
        "target_type": "dashboard",
        "dashboard": bi_dashboard_a.pk,
        "embedding_mode": "iframe",
        "auth_mode": "sso_passthrough",
        "theme_mode": "light",
        "primary_color": "#1e40af",
        "accent_color": "#3b82f6",
        "status": "active",
    }
    resp = client_a.post(create_url, data=post_data)
    assert resp.status_code == 302
    cfg = EmbeddedAnalyticsConfig.objects.filter(slug="audit-tracked-embed").first()
    assert cfg is not None

    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(cfg.pk),
    ).first()
    assert log_create is not None

    # 2. Update action
    edit_url = reverse("bi:embedded_analytics_config_edit", kwargs={"pk": cfg.pk})
    post_data["name"] = "Audit Tracked Embed Renamed"
    resp_edit = client_a.post(edit_url, data=post_data)
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(cfg.pk),
    ).first()
    assert log_update is not None

    # 3. Delete action
    delete_url = reverse("bi:embedded_analytics_config_delete", kwargs={"pk": cfg.pk})
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=str(cfg.pk),
    ).first()
    assert log_delete is not None


@pytest.mark.django_db
def test_embeddedmobilebi_security_audit_log_kiosk_display_mutations(
    client_a, tenant_a, admin_user
):
    """Assert AuditLog records create, update, and delete actions for KioskWallboardDisplay."""
    # 1. Create action
    create_url = reverse("bi:kiosk_wallboard_display_create")
    post_data = {
        "name": "Audit Wallboard",
        "kiosk_slug": "audit-wallboard",
        "theme": "dark_oled",
        "transition_effect": "fade",
        "display_schedule": "continuous_24_7",
        "default_slide_duration_seconds": 30,
        "auto_refresh_data_interval_seconds": 300,
        "status": "active",
    }
    resp = client_a.post(create_url, data=post_data)
    assert resp.status_code == 302
    disp = KioskWallboardDisplay.objects.filter(name="Audit Wallboard").first()
    assert disp is not None

    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(disp.pk),
    ).first()
    assert log_create is not None

    # 2. Update action
    edit_url = reverse("bi:kiosk_wallboard_display_edit", kwargs={"pk": disp.pk})
    post_data["name"] = "Audit Wallboard Updated"
    resp_edit = client_a.post(edit_url, data=post_data)
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(disp.pk),
    ).first()
    assert log_update is not None

    # 3. Delete action
    delete_url = reverse("bi:kiosk_wallboard_display_delete", kwargs={"pk": disp.pk})
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=str(disp.pk),
    ).first()
    assert log_delete is not None


@pytest.mark.django_db
def test_embeddedmobilebi_security_audit_log_mobile_config_mutations(
    client_a, tenant_a, admin_user
):
    """Assert AuditLog records create, update, and delete actions for MobileBiConfiguration."""
    # 1. Create action
    create_url = reverse("bi:mobile_bi_config_create")
    post_data = {
        "name": "Audit Mobile Profile",
        "target_user": str(admin_user.pk),
        "touch_layout_preset": "comfortable",
        "push_digest_frequency": "weekly",
        "cache_max_age_hours": 12,
        "max_cache_storage_mb": 100,
        "inactivity_lock_minutes": 15,
        "status": "active",
    }
    resp = client_a.post(create_url, data=post_data)
    assert resp.status_code == 302
    mob = MobileBiConfiguration.objects.filter(name="Audit Mobile Profile").first()
    assert mob is not None

    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(mob.pk),
    ).first()
    assert log_create is not None

    # 2. Update action
    edit_url = reverse("bi:mobile_bi_config_edit", kwargs={"pk": mob.pk})
    post_data["name"] = "Audit Mobile Profile Updated"
    resp_edit = client_a.post(edit_url, data=post_data)
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(mob.pk),
    ).first()
    assert log_update is not None

    # 3. Delete action
    delete_url = reverse("bi:mobile_bi_config_delete", kwargs={"pk": mob.pk})
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=str(mob.pk),
    ).first()
    assert log_delete is not None


@pytest.mark.django_db
def test_embeddedmobilebi_security_audit_log_embed_api_token_mutations(
    client_a, tenant_a, admin_user, embedded_analytics_config_a
):
    """Assert AuditLog records create, update, revoke, and delete actions for EmbedApiToken."""
    # 1. Create action
    create_url = reverse("bi:embed_api_token_create")
    post_data = {
        "name": "Audit API Token",
        "embedded_config": embedded_analytics_config_a.pk,
        "status": "active",
        "scopes_raw": "read:dashboard",
        "rate_limit_rpm": 90,
    }
    resp = client_a.post(create_url, data=post_data)
    assert resp.status_code == 302
    tok = EmbedApiToken.objects.filter(name="Audit API Token").first()
    assert tok is not None

    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=str(tok.pk),
    ).first()
    assert log_create is not None

    # 2. Update action
    edit_url = reverse("bi:embed_api_token_edit", kwargs={"pk": tok.pk})
    post_data["name"] = "Audit API Token Updated"
    resp_edit = client_a.post(edit_url, data=post_data)
    assert resp_edit.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=str(tok.pk),
    ).first()
    assert log_update is not None

    # 3. Revoke action
    revoke_url = reverse("bi:embed_api_token_revoke", kwargs={"pk": tok.pk})
    resp_rev = client_a.post(revoke_url)
    assert resp_rev.status_code == 302

    log_revoke = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="revoke",
        object_id=str(tok.pk),
    ).first()
    assert log_revoke is not None

    # 4. Delete action
    delete_url = reverse("bi:embed_api_token_delete", kwargs={"pk": tok.pk})
    resp_del = client_a.post(delete_url)
    assert resp_del.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=str(tok.pk),
    ).first()
    assert log_delete is not None
