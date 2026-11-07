"""View tests for Sub-module 10.17: Embedded & Mobile BI (apps/bi).

Entities covered:
1. EmbeddedAnalyticsConfig:
   - list view (200, search, filters by status, target_type, embedding_mode, stats dict, pagination)
   - create view (GET 200, valid POST 302, audit log verified)
   - detail view (200, snippets present, created_by=None handling verified without 500)
   - edit view (GET 200, valid POST 302, audit log verified)
   - delete view (POST 302, audit log verified; GET 405 Method Not Allowed)
   - preview view (200, atomic view_count increment verified, custom CSS safe)

2. KioskWallboardDisplay:
   - list view (200, search, filters by status, theme, schedule, stats dict, pagination)
   - create view (GET 200, valid POST 302, audit log verified)
   - detail view (200, created_by=None handling verified)
   - edit view (GET 200, valid POST 302, audit log verified)
   - delete view (POST 302, audit log verified; GET 405 Method Not Allowed)
   - player view (200, superuser tenant=None access verified, public kiosk passcode verification, safe playlist rendering)
   - heartbeat endpoint (require_POST enforced, 200 JSON with timestamp, atomic update)

3. MobileBiConfiguration:
   - list view (200, search, filters by status, preset, digest, stats dict, pagination)
   - create view (GET 200, valid POST 302, audit log verified)
   - detail view (200, pinned items rendered, created_by=None handling verified)
   - edit view (GET 200, valid POST 302, audit log verified)
   - delete view (POST 302, audit log verified; GET 405 Method Not Allowed)

4. EmbedApiToken:
   - list view (200, search, filter by status, stats dict, pagination)
   - create view (GET 200, valid POST 302, one-time secret stored in session and hashed in DB)
   - detail view (200, one-time reveal banner if session key present, snippets present, created_by=None safe)
   - edit view (GET 200, valid POST 302, audit log verified)
   - delete view (POST 302, audit log verified; GET 405 Method Not Allowed)
   - revoke view (POST 302, audit log verified, token status set to revoked, GET 405)
"""
import hashlib
import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.core.exceptions import PermissionDenied
from django.test import Client
from django.urls import reverse
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
from apps.core.models import AuditLog

User = get_user_model()


# ==============================================================================
# Module Helpers (strictly prefixed with _embeddedmobilebi_)
# ==============================================================================


def _embeddedmobilebi_create_embed_config(tenant, user=None, **kwargs):
    """Helper to create a tenant-scoped EmbeddedAnalyticsConfig."""
    defaults = {
        "tenant": tenant,
        "name": "Helper Embedded Config",
        "slug": f"helper-embed-{timezone.now().timestamp()}",
        "target_type": "dashboard",
        "embedding_mode": "iframe",
        "auth_mode": "signed_jwt",
        "theme_mode": "light",
        "status": "active",
        "created_by": user,
    }
    defaults.update(kwargs)
    return EmbeddedAnalyticsConfig.objects.create(**defaults)


def _embeddedmobilebi_create_kiosk_display(tenant, user=None, **kwargs):
    """Helper to create a tenant-scoped KioskWallboardDisplay."""
    defaults = {
        "tenant": tenant,
        "name": "Helper Kiosk Display",
        "kiosk_slug": f"helper-kiosk-{timezone.now().timestamp()}",
        "theme": "dark_oled",
        "display_schedule": "continuous_24_7",
        "default_slide_duration_seconds": 30,
        "auto_refresh_data_interval_seconds": 300,
        "status": "active",
        "playlist_items": [{"type": "dashboard", "title": "Overview", "duration_seconds": 30}],
        "created_by": user,
    }
    defaults.update(kwargs)
    return KioskWallboardDisplay.objects.create(**defaults)


def _embeddedmobilebi_create_mobile_config(tenant, user=None, **kwargs):
    """Helper to create a tenant-scoped MobileBiConfiguration."""
    defaults = {
        "tenant": tenant,
        "name": "Helper Mobile Config",
        "touch_layout_preset": "comfortable",
        "push_digest_frequency": "weekly",
        "offline_caching_enabled": True,
        "status": "active",
        "created_by": user,
    }
    defaults.update(kwargs)
    return MobileBiConfiguration.objects.create(**defaults)


def _embeddedmobilebi_create_api_token(tenant, config=None, user=None, **kwargs):
    """Helper to create a tenant-scoped EmbedApiToken."""
    raw_secret, prefix, token_hash = EmbedApiToken.generate_secret()
    defaults = {
        "tenant": tenant,
        "name": "Helper API Token",
        "embedded_config": config,
        "token_prefix": prefix,
        "token_hash": token_hash,
        "scopes": ["read:dashboard", "embed:render"],
        "rate_limit_rpm": 120,
        "status": "active",
        "created_by": user,
    }
    defaults.update(kwargs)
    return EmbedApiToken.objects.create(**defaults)


def _embeddedmobilebi_create_member_user(tenant, username="regular_bi_user"):
    """Helper to create a regular non-admin tenant user."""
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="TestPassword123!",
        tenant=tenant,
        is_tenant_admin=False,
    )


# ==============================================================================
# 1. EmbeddedAnalyticsConfig View Tests
# ==============================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_list_get_and_stats(
    client_a, tenant_a, embedded_analytics_config_a, embedded_analytics_config_b
):
    """Test list view returns 200, context statistics, and scopes to tenant."""
    url = reverse("bi:embedded_analytics_config_list")
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "configs" in resp.context
    assert "embedded_analytics_configs" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["active_count"] >= 1
    assert "iframe_count" in resp.context
    assert "component_count" in resp.context
    assert "status_choices" in resp.context
    assert "target_type_choices" in resp.context
    assert "embedding_mode_choices" in resp.context

    # Verify tenant isolation in list
    item_pks = [c.pk for c in resp.context["configs"]]
    assert embedded_analytics_config_a.pk in item_pks
    assert embedded_analytics_config_b.pk not in item_pks


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_list_search(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test searching list view by name and slug."""
    cfg = _embeddedmobilebi_create_embed_config(
        tenant_a,
        user=admin_user,
        name="UniqueEmbedSearchAlpha",
        slug="unique-search-alpha",
        dashboard=bi_dashboard_a,
    )
    url = reverse("bi:embedded_analytics_config_list")

    # Positive search
    resp = client_a.get(url, {"q": "SearchAlpha"})
    assert resp.status_code == 200
    assert any(c.pk == cfg.pk for c in resp.context["configs"])

    # Negative search
    resp_neg = client_a.get(url, {"q": "NonExistentZetaToken999"})
    assert resp_neg.status_code == 200
    assert not any(c.pk == cfg.pk for c in resp_neg.context["configs"])


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_list_filters(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test filtering configs by status, target_type, and embedding_mode."""
    cfg1 = _embeddedmobilebi_create_embed_config(
        tenant_a,
        user=admin_user,
        name="Paused Web Component",
        status="paused",
        target_type="dashboard",
        embedding_mode="web_component",
        dashboard=bi_dashboard_a,
    )
    url = reverse("bi:embedded_analytics_config_list")

    # Filter by status
    resp_status = client_a.get(url, {"status": "paused"})
    assert resp_status.status_code == 200
    assert all(c.status == "paused" for c in resp_status.context["configs"])

    # Filter by target_type
    resp_target = client_a.get(url, {"target_type": "dashboard"})
    assert resp_target.status_code == 200
    assert all(c.target_type == "dashboard" for c in resp_target.context["configs"])

    # Filter by embedding_mode
    resp_mode = client_a.get(url, {"embedding_mode": "web_component"})
    assert resp_mode.status_code == 200
    assert all(c.embedding_mode == "web_component" for c in resp_mode.context["configs"])


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_list_pagination(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test pagination splits items into pages (page size 20)."""
    bulk = [
        EmbeddedAnalyticsConfig(
            tenant=tenant_a,
            number=f"EMB-PAG-{i:05d}",
            name=f"Paginated Config {i}",
            slug=f"paginated-config-{i}",
            target_type="dashboard",
            dashboard=bi_dashboard_a,
            embedding_mode="iframe",
            auth_mode="signed_jwt",
            theme_mode="light",
            status="active",
            created_by=admin_user,
        )
        for i in range(25)
    ]
    EmbeddedAnalyticsConfig.objects.bulk_create(bulk)

    url = reverse("bi:embedded_analytics_config_list")
    resp_p1 = client_a.get(url, {"page": "1"})
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["configs"]) == 20

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["configs"]) >= 5


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_create_get(client_a):
    """Test create view GET returns 200 and form context."""
    url = reverse("bi:embedded_analytics_config_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert "title" in resp.context


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_create_post_success(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test create view POST valid data redirects 302 and logs audit."""
    url = reverse("bi:embedded_analytics_config_create")
    payload = {
        "name": "Customer Portal Embed Live",
        "slug": "customer-portal-live",
        "description": "Production iframe embed",
        "target_type": "dashboard",
        "dashboard": str(bi_dashboard_a.pk),
        "embedding_mode": "iframe",
        "auth_mode": "signed_jwt",
        "status": "active",
        "allowed_origins": "https://portal.acme.com",
        "theme_mode": "light",
        "primary_color": "#1e40af",
        "accent_color": "#3b82f6",
        "custom_css": ".metric-card { border-radius: 8px; }",
        "enable_rls_filter": "on",
        "default_rls_attributes_raw": json.dumps({"region": "EMEA"}),
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = EmbeddedAnalyticsConfig.objects.get(slug="customer-portal-live")
    assert resp.url == reverse("bi:embedded_analytics_config_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.created_by == admin_user
    assert created.default_rls_attributes == {"region": "EMEA"}

    # Audit log verified
    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None
    assert audit.user == admin_user


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_create_post_invalid(client_a):
    """Test create view POST with invalid data returns 200 with form errors."""
    url = reverse("bi:embedded_analytics_config_create")
    resp = client_a.post(url, data={"name": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_detail_success_and_snippets(
    client_a, embedded_analytics_config_a
):
    """Test detail view returns 200 with expected snippets and embed URL."""
    url = reverse("bi:embedded_analytics_config_detail", kwargs={"pk": embedded_analytics_config_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["config"] == embedded_analytics_config_a
    assert "<iframe" in resp.context["iframe_snippet"]
    assert "<nav-bi-embed" in resp.context["web_component_snippet"]
    assert "curl -X GET" in resp.context["curl_snippet"]
    assert "/preview/" in resp.context["embed_url"]


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_detail_created_by_none(
    client_a, tenant_a, bi_dashboard_a
):
    """Test detail view renders without 500 when created_by is None."""
    cfg = _embeddedmobilebi_create_embed_config(
        tenant_a,
        user=None,
        name="No Creator Embed",
        dashboard=bi_dashboard_a,
    )
    url = reverse("bi:embedded_analytics_config_detail", kwargs={"pk": cfg.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "System" in resp.content.decode()


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_edit_get(client_a, embedded_analytics_config_a):
    """Test edit view GET returns 200 and pre-filled form."""
    url = reverse("bi:embedded_analytics_config_edit", kwargs={"pk": embedded_analytics_config_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["config"] == embedded_analytics_config_a


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_edit_post_success(
    client_a, tenant_a, admin_user, embedded_analytics_config_a, bi_dashboard_a
):
    """Test edit view POST valid data updates record, logs audit, and redirects."""
    url = reverse("bi:embedded_analytics_config_edit", kwargs={"pk": embedded_analytics_config_a.pk})
    payload = {
        "name": "Partner Portal Embed Updated",
        "slug": embedded_analytics_config_a.slug,
        "description": "Updated description",
        "target_type": "dashboard",
        "dashboard": str(bi_dashboard_a.pk),
        "embedding_mode": "iframe",
        "auth_mode": "sso_passthrough",
        "status": "paused",
        "allowed_origins": "https://updated.portal.com",
        "theme_mode": "dark",
        "primary_color": "#0f766e",
        "accent_color": "#14b8a6",
        "custom_css": "",
        "default_rls_attributes_raw": json.dumps({"region": "GLOBAL"}),
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:embedded_analytics_config_detail", kwargs={"pk": embedded_analytics_config_a.pk})

    embedded_analytics_config_a.refresh_from_db()
    assert embedded_analytics_config_a.name == "Partner Portal Embed Updated"
    assert embedded_analytics_config_a.status == "paused"
    assert embedded_analytics_config_a.theme_mode == "dark"

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(embedded_analytics_config_a.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_delete_post_success(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test delete view POST deletes record, logs audit, and redirects to list."""
    cfg = _embeddedmobilebi_create_embed_config(
        tenant_a, user=admin_user, name="To Delete Config", dashboard=bi_dashboard_a
    )
    url = reverse("bi:embedded_analytics_config_delete", kwargs={"pk": cfg.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:embedded_analytics_config_list")
    assert not EmbeddedAnalyticsConfig.objects.filter(pk=cfg.pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(cfg.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_delete_get_not_allowed(
    client_a, embedded_analytics_config_a
):
    """Test delete view GET returns 405 Method Not Allowed due to require_POST."""
    url = reverse("bi:embedded_analytics_config_delete", kwargs={"pk": embedded_analytics_config_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert EmbeddedAnalyticsConfig.objects.filter(pk=embedded_analytics_config_a.pk).exists()


@pytest.mark.django_db
def test_embeddedmobilebi_views_embed_config_preview_atomic_increment_and_css(
    client_a, embedded_analytics_config_a
):
    """Test preview view returns 200, atomically increments view_count, and renders custom CSS."""
    embedded_analytics_config_a.custom_css = ".preview-box { border: 1px solid #ccc; }"
    embedded_analytics_config_a.save()

    initial_count = embedded_analytics_config_a.view_count
    url = reverse("bi:embedded_analytics_config_preview", kwargs={"pk": embedded_analytics_config_a.pk})
    resp = client_a.get(url)

    assert resp.status_code == 200
    assert "config" in resp.context
    assert ".preview-box" in resp.content.decode()

    embedded_analytics_config_a.refresh_from_db()
    assert embedded_analytics_config_a.view_count == initial_count + 1
    assert embedded_analytics_config_a.last_accessed_at is not None


# ==============================================================================
# 2. KioskWallboardDisplay View Tests
# ==============================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_list_get_and_stats(
    client_a, kiosk_wallboard_display_a, kiosk_wallboard_display_b
):
    """Test kiosk display list view returns 200, context stats, and filters by tenant."""
    url = reverse("bi:kiosk_wallboard_display_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "displays" in resp.context
    assert "kiosk_wallboard_displays" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["active_count"] >= 1
    assert "dark_count" in resp.context
    assert "status_choices" in resp.context
    assert "theme_choices" in resp.context
    assert "schedule_choices" in resp.context

    item_pks = [d.pk for d in resp.context["displays"]]
    assert kiosk_wallboard_display_a.pk in item_pks
    assert kiosk_wallboard_display_b.pk not in item_pks


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_list_search(
    client_a, tenant_a, admin_user
):
    """Test searching kiosk displays by name, slug, and location."""
    disp = _embeddedmobilebi_create_kiosk_display(
        tenant_a,
        user=admin_user,
        name="Logistics Dispatch Hub Display",
        kiosk_slug="dispatch-hub-slug",
        location_description="Dock 14 Logistics Pier",
    )
    url = reverse("bi:kiosk_wallboard_display_list")

    # Name search
    resp_name = client_a.get(url, {"q": "Dispatch Hub"})
    assert resp_name.status_code == 200
    assert any(d.pk == disp.pk for d in resp_name.context["displays"])

    # Location search
    resp_loc = client_a.get(url, {"q": "Dock 14"})
    assert resp_loc.status_code == 200
    assert any(d.pk == disp.pk for d in resp_loc.context["displays"])

    # Negative search
    resp_none = client_a.get(url, {"q": "NonExistentDock999"})
    assert resp_none.status_code == 200
    assert not any(d.pk == disp.pk for d in resp_none.context["displays"])


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_list_filters(
    client_a, tenant_a, admin_user
):
    """Test filtering kiosk displays by status, theme, and schedule."""
    disp = _embeddedmobilebi_create_kiosk_display(
        tenant_a,
        user=admin_user,
        name="Executive Briefing Light",
        theme="light_high_contrast",
        display_schedule="business_hours",
        status="paused",
    )
    url = reverse("bi:kiosk_wallboard_display_list")

    # Filter status
    resp_status = client_a.get(url, {"status": "paused"})
    assert resp_status.status_code == 200
    assert all(d.status == "paused" for d in resp_status.context["displays"])

    # Filter theme
    resp_theme = client_a.get(url, {"theme": "light_high_contrast"})
    assert resp_theme.status_code == 200
    assert all(d.theme == "light_high_contrast" for d in resp_theme.context["displays"])

    # Filter schedule
    resp_sched = client_a.get(url, {"schedule": "business_hours"})
    assert resp_sched.status_code == 200
    assert all(d.display_schedule == "business_hours" for d in resp_sched.context["displays"])


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_list_pagination(
    client_a, tenant_a, admin_user
):
    """Test kiosk display pagination splits at 20 items."""
    bulk = [
        KioskWallboardDisplay(
            tenant=tenant_a,
            number=f"WALL-PAG-{i:05d}",
            name=f"Bulk Wallboard {i}",
            kiosk_slug=f"bulk-wall-{i}",
            theme="dark_navy",
            display_schedule="continuous_24_7",
            status="active",
            created_by=admin_user,
        )
        for i in range(25)
    ]
    KioskWallboardDisplay.objects.bulk_create(bulk)

    url = reverse("bi:kiosk_wallboard_display_list")
    resp = client_a.get(url, {"page": "1"})
    assert resp.status_code == 200
    assert len(resp.context["displays"]) == 20


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_create_get(client_a):
    """Test kiosk display create view GET returns 200 and form."""
    url = reverse("bi:kiosk_wallboard_display_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_create_post_success(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Test kiosk display create POST valid data redirects 302 and writes audit log."""
    url = reverse("bi:kiosk_wallboard_display_create")
    payload = {
        "name": "Operations Center Central Board",
        "location_description": "HQ 4th Floor NOC",
        "kiosk_slug": "hq-4f-noc-board",
        "access_passcode": "NOC9876",
        "is_public_kiosk": "on",
        "status": "active",
        "default_slide_duration_seconds": 45,
        "transition_effect": "fade",
        "theme": "dark_oled",
        "display_schedule": "continuous_24_7",
        "auto_refresh_data_interval_seconds": 180,
        "playlist_items_raw": json.dumps([
            {"type": "dashboard", "title": "NOC Alerts", "id": bi_dashboard_a.pk, "duration_seconds": 45}
        ]),
        "operating_hours_raw": json.dumps({"start": "00:00", "end": "23:59"}),
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = KioskWallboardDisplay.objects.get(kiosk_slug="hq-4f-noc-board")
    assert resp.url == reverse("bi:kiosk_wallboard_display_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.created_by == admin_user
    assert len(created.playlist_items) == 1

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_create_post_invalid(client_a):
    """Test kiosk display create POST invalid data returns 200 with form errors."""
    url = reverse("bi:kiosk_wallboard_display_create")
    resp = client_a.post(url, data={"name": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_detail_success(
    client_a, kiosk_wallboard_display_a
):
    """Test kiosk display detail view returns 200 and context items."""
    url = reverse("bi:kiosk_wallboard_display_detail", kwargs={"pk": kiosk_wallboard_display_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["display"] == kiosk_wallboard_display_a
    assert "playlist_items" in resp.context
    assert "operating_hours" in resp.context


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_detail_created_by_none(
    client_a, tenant_a
):
    """Test kiosk display detail view renders without 500 when created_by is None."""
    disp = _embeddedmobilebi_create_kiosk_display(tenant_a, user=None, name="System Kiosk")
    url = reverse("bi:kiosk_wallboard_display_detail", kwargs={"pk": disp.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "System" in resp.content.decode()


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_edit_get(client_a, kiosk_wallboard_display_a):
    """Test kiosk display edit GET returns 200 and form."""
    url = reverse("bi:kiosk_wallboard_display_edit", kwargs={"pk": kiosk_wallboard_display_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["display"] == kiosk_wallboard_display_a


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_edit_post_success(
    client_a, tenant_a, admin_user, kiosk_wallboard_display_a
):
    """Test kiosk display edit POST updates record, logs audit, and redirects."""
    url = reverse("bi:kiosk_wallboard_display_edit", kwargs={"pk": kiosk_wallboard_display_a.pk})
    payload = {
        "name": "HQ Operations Wallboard Updated",
        "location_description": "Relocated to West Lobby",
        "kiosk_slug": kiosk_wallboard_display_a.kiosk_slug,
        "access_passcode": kiosk_wallboard_display_a.access_passcode,
        "is_public_kiosk": "on",
        "status": "active",
        "default_slide_duration_seconds": 60,
        "transition_effect": "slide_horizontal",
        "theme": "dark_navy",
        "display_schedule": "business_hours",
        "auto_refresh_data_interval_seconds": 600,
        "playlist_items_raw": json.dumps(kiosk_wallboard_display_a.playlist_items),
        "operating_hours_raw": "{}",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:kiosk_wallboard_display_detail", kwargs={"pk": kiosk_wallboard_display_a.pk})

    kiosk_wallboard_display_a.refresh_from_db()
    assert kiosk_wallboard_display_a.name == "HQ Operations Wallboard Updated"
    assert kiosk_wallboard_display_a.theme == "dark_navy"
    assert kiosk_wallboard_display_a.default_slide_duration_seconds == 60

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(kiosk_wallboard_display_a.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_delete_post_success(
    client_a, tenant_a, admin_user
):
    """Test kiosk display delete POST removes record, logs audit, and redirects to list."""
    disp = _embeddedmobilebi_create_kiosk_display(tenant_a, user=admin_user, name="To Delete Wallboard")
    url = reverse("bi:kiosk_wallboard_display_delete", kwargs={"pk": disp.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:kiosk_wallboard_display_list")
    assert not KioskWallboardDisplay.objects.filter(pk=disp.pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(disp.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_delete_get_not_allowed(
    client_a, kiosk_wallboard_display_a
):
    """Test kiosk display delete GET returns 405 Method Not Allowed."""
    url = reverse("bi:kiosk_wallboard_display_delete", kwargs={"pk": kiosk_wallboard_display_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert KioskWallboardDisplay.objects.filter(pk=kiosk_wallboard_display_a.pk).exists()


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_player_authenticated_tenant(
    client_a, kiosk_wallboard_display_a
):
    """Test authenticated tenant client access to player view."""
    url = reverse("bi:kiosk_wallboard_display_player", kwargs={"pk": kiosk_wallboard_display_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["display"] == kiosk_wallboard_display_a
    assert "playlist_json" in resp.context


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_player_superuser_access(
    db, kiosk_wallboard_display_a
):
    """Test superuser with tenant=None can access any display player."""
    super_user = User.objects.create_superuser(
        username="global_admin",
        email="super@admin.com",
        password="SuperPassword123!",
    )
    c = Client()
    c.force_login(super_user)

    url = reverse("bi:kiosk_wallboard_display_player", kwargs={"pk": kiosk_wallboard_display_a.pk})
    resp = c.get(url)
    assert resp.status_code == 200
    assert resp.context["display"] == kiosk_wallboard_display_a


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_player_public_passcode_and_fallback_slide(
    anon_client, tenant_a
):
    """Test anonymous public kiosk player access with passcode and fallback slide."""
    public_disp = _embeddedmobilebi_create_kiosk_display(
        tenant_a,
        name="Public Lobby Board",
        is_public_kiosk=True,
        access_passcode="LOBBY123",
        playlist_items=[],  # Empty playlist to verify fallback slide logic
    )
    url = reverse("bi:kiosk_wallboard_display_player", kwargs={"pk": public_disp.pk})

    # Wrong passcode -> 404
    resp_wrong = anon_client.get(url, {"passcode": "WRONG_PASS"})
    assert resp_wrong.status_code == 404

    # Correct passcode -> 200 and fallback slide
    resp_ok = anon_client.get(url, {"passcode": "LOBBY123"})
    assert resp_ok.status_code == 200
    assert len(resp_ok.context["playlist_items"]) == 1
    assert resp_ok.context["playlist_items"][0]["title"] == "Public Lobby Board"


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_heartbeat_post_success(
    client_a, kiosk_wallboard_display_a
):
    """Test heartbeat endpoint atomic update with authenticated client."""
    url = reverse("bi:kiosk_wallboard_display_heartbeat", kwargs={"pk": kiosk_wallboard_display_a.pk})
    resp = client_a.post(url, HTTP_USER_AGENT="NavKioskDevice/1.0", REMOTE_ADDR="192.168.1.50")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["display_number"] == kiosk_wallboard_display_a.number
    assert "last_heartbeat_at" in data

    kiosk_wallboard_display_a.refresh_from_db()
    assert kiosk_wallboard_display_a.last_heartbeat_at is not None
    assert kiosk_wallboard_display_a.device_ip_address == "192.168.1.50"
    assert "NavKioskDevice" in kiosk_wallboard_display_a.device_user_agent


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_heartbeat_get_not_allowed(
    client_a, kiosk_wallboard_display_a
):
    """Test heartbeat requires POST; GET returns 405."""
    url = reverse("bi:kiosk_wallboard_display_heartbeat", kwargs={"pk": kiosk_wallboard_display_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_heartbeat_public_passcode(
    anon_client, tenant_a
):
    """Test anonymous public kiosk heartbeat with passcode."""
    disp = _embeddedmobilebi_create_kiosk_display(
        tenant_a,
        is_public_kiosk=True,
        access_passcode="HEARTBEAT99",
    )
    url = reverse("bi:kiosk_wallboard_display_heartbeat", kwargs={"pk": disp.pk})
    resp = anon_client.post(url, {"passcode": "HEARTBEAT99"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.django_db
def test_embeddedmobilebi_views_kiosk_display_heartbeat_denied_404(
    anon_client, kiosk_wallboard_display_a
):
    """Test heartbeat access without proper passcode returns 404."""
    url = reverse("bi:kiosk_wallboard_display_heartbeat", kwargs={"pk": kiosk_wallboard_display_a.pk})
    resp = anon_client.post(url, {"passcode": "INVALID_PASS"})
    assert resp.status_code == 404
    assert resp.json()["status"] == "error"


# ==============================================================================
# 3. MobileBiConfiguration View Tests
# ==============================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_list_get_and_stats(
    client_a, mobile_bi_config_a, mobile_bi_config_b
):
    """Test mobile configuration list view returns 200 and context stats."""
    url = reverse("bi:mobile_bi_config_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "configs" in resp.context
    assert "mobile_bi_configs" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["active_count"] >= 1
    assert "offline_enabled_count" in resp.context
    assert "status_choices" in resp.context
    assert "preset_choices" in resp.context
    assert "digest_choices" in resp.context

    item_pks = [c.pk for c in resp.context["configs"]]
    assert mobile_bi_config_a.pk in item_pks
    assert mobile_bi_config_b.pk not in item_pks


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_list_search(
    client_a, tenant_a, admin_user
):
    """Test searching mobile configurations by name and target user username."""
    cfg = _embeddedmobilebi_create_mobile_config(
        tenant_a,
        user=admin_user,
        target_user=admin_user,
        name="FieldSalesAgentMobileProfile",
    )
    url = reverse("bi:mobile_bi_config_list")

    resp_name = client_a.get(url, {"q": "FieldSalesAgent"})
    assert resp_name.status_code == 200
    assert any(c.pk == cfg.pk for c in resp_name.context["configs"])

    resp_user = client_a.get(url, {"q": admin_user.username})
    assert resp_user.status_code == 200
    assert any(c.pk == cfg.pk for c in resp_user.context["configs"])


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_list_filters(
    client_a, tenant_a, admin_user
):
    """Test filtering mobile configurations by status, preset, and digest."""
    cfg = _embeddedmobilebi_create_mobile_config(
        tenant_a,
        user=admin_user,
        name="Filterable Profile",
        status="paused",
        touch_layout_preset="compact",
        push_digest_frequency="daily_morning",
    )
    url = reverse("bi:mobile_bi_config_list")

    resp_status = client_a.get(url, {"status": "paused"})
    assert resp_status.status_code == 200
    assert all(c.status == "paused" for c in resp_status.context["configs"])

    resp_preset = client_a.get(url, {"preset": "compact"})
    assert resp_preset.status_code == 200
    assert all(c.touch_layout_preset == "compact" for c in resp_preset.context["configs"])

    resp_digest = client_a.get(url, {"digest": "daily_morning"})
    assert resp_digest.status_code == 200
    assert all(c.push_digest_frequency == "daily_morning" for c in resp_digest.context["configs"])


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_list_pagination(
    client_a, tenant_a, admin_user
):
    """Test mobile configurations pagination at 20 items."""
    bulk = [
        MobileBiConfiguration(
            tenant=tenant_a,
            number=f"MOB-PAG-{i:05d}",
            name=f"Bulk Profile {i}",
            touch_layout_preset="comfortable",
            push_digest_frequency="weekly",
            status="active",
            created_by=admin_user,
        )
        for i in range(25)
    ]
    MobileBiConfiguration.objects.bulk_create(bulk)

    url = reverse("bi:mobile_bi_config_list")
    resp = client_a.get(url, {"page": "1"})
    assert resp.status_code == 200
    assert len(resp.context["configs"]) == 20


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_create_get(client_a):
    """Test mobile config create view GET returns 200 and form."""
    url = reverse("bi:mobile_bi_config_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_create_post_success_and_default_flip(
    client_a, tenant_a, admin_user, mobile_bi_config_a, bi_dashboard_a
):
    """Test create mobile profile with is_default_profile resets prior default."""
    assert mobile_bi_config_a.is_default_profile is True

    url = reverse("bi:mobile_bi_config_create")
    payload = {
        "name": "New Global Default Mobile Profile",
        "target_user": str(admin_user.pk),
        "is_default_profile": "on",
        "status": "active",
        "offline_caching_enabled": "on",
        "cache_max_age_hours": 24,
        "max_cache_storage_mb": 500,
        "sync_on_wifi_only": "on",
        "touch_layout_preset": "comfortable",
        "enable_push_insights": "on",
        "push_digest_frequency": "daily_morning",
        "require_biometric_lock": "on",
        "inactivity_lock_minutes": 5,
        "pinned_dashboard_ids_raw": json.dumps([bi_dashboard_a.pk]),
        "pinned_report_ids_raw": "[]",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = MobileBiConfiguration.objects.get(name="New Global Default Mobile Profile")
    assert resp.url == reverse("bi:mobile_bi_config_detail", kwargs={"pk": created.pk})
    assert created.is_default_profile is True

    # Previous default flipped to False
    mobile_bi_config_a.refresh_from_db()
    assert mobile_bi_config_a.is_default_profile is False

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_create_post_invalid(client_a):
    """Test mobile config create POST invalid data returns 200 with form errors."""
    url = reverse("bi:mobile_bi_config_create")
    resp = client_a.post(url, data={"name": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_detail_success_and_pinned_items(
    client_a, mobile_bi_config_a, bi_dashboard_a
):
    """Test mobile config detail view renders pinned dashboards and reports."""
    url = reverse("bi:mobile_bi_config_detail", kwargs={"pk": mobile_bi_config_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["config"] == mobile_bi_config_a
    assert "pinned_dashboards" in resp.context
    assert any(d.pk == bi_dashboard_a.pk for d in resp.context["pinned_dashboards"])


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_detail_created_by_none(
    client_a, tenant_a
):
    """Test mobile config detail view renders without 500 when created_by is None."""
    cfg = _embeddedmobilebi_create_mobile_config(tenant_a, user=None, name="System Profile")
    url = reverse("bi:mobile_bi_config_detail", kwargs={"pk": cfg.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "System" in resp.content.decode()


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_edit_get(client_a, mobile_bi_config_a):
    """Test mobile config edit GET returns 200 and form."""
    url = reverse("bi:mobile_bi_config_edit", kwargs={"pk": mobile_bi_config_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["config"] == mobile_bi_config_a


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_edit_post_success_and_default_flip(
    client_a, tenant_a, admin_user, mobile_bi_config_a
):
    """Test edit mobile profile updates fields, resets other defaults, and logs audit."""
    other_default = _embeddedmobilebi_create_mobile_config(
        tenant_a, user=admin_user, name="Other Default Profile", is_default_profile=True
    )
    mobile_bi_config_a.is_default_profile = False
    mobile_bi_config_a.save()

    url = reverse("bi:mobile_bi_config_edit", kwargs={"pk": mobile_bi_config_a.pk})
    payload = {
        "name": "Executive Mobile Profile Updated",
        "target_user": str(admin_user.pk),
        "is_default_profile": "on",
        "status": "active",
        "offline_caching_enabled": "on",
        "cache_max_age_hours": 18,
        "max_cache_storage_mb": 400,
        "sync_on_wifi_only": "",
        "touch_layout_preset": "compact",
        "enable_push_insights": "on",
        "push_digest_frequency": "weekly",
        "require_biometric_lock": "on",
        "inactivity_lock_minutes": 20,
        "pinned_dashboard_ids_raw": "[]",
        "pinned_report_ids_raw": "[]",
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:mobile_bi_config_detail", kwargs={"pk": mobile_bi_config_a.pk})

    mobile_bi_config_a.refresh_from_db()
    assert mobile_bi_config_a.name == "Executive Mobile Profile Updated"
    assert mobile_bi_config_a.is_default_profile is True
    assert mobile_bi_config_a.touch_layout_preset == "compact"

    # Other default flipped to False
    other_default.refresh_from_db()
    assert other_default.is_default_profile is False

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(mobile_bi_config_a.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_delete_post_success(
    client_a, tenant_a, admin_user
):
    """Test mobile config delete POST removes record, logs audit, and redirects to list."""
    cfg = _embeddedmobilebi_create_mobile_config(tenant_a, user=admin_user, name="To Delete Profile")
    url = reverse("bi:mobile_bi_config_delete", kwargs={"pk": cfg.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:mobile_bi_config_list")
    assert not MobileBiConfiguration.objects.filter(pk=cfg.pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(cfg.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_mobile_config_delete_get_not_allowed(
    client_a, mobile_bi_config_a
):
    """Test mobile config delete GET returns 405 Method Not Allowed."""
    url = reverse("bi:mobile_bi_config_delete", kwargs={"pk": mobile_bi_config_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert MobileBiConfiguration.objects.filter(pk=mobile_bi_config_a.pk).exists()


# ==============================================================================
# 4. EmbedApiToken View Tests
# ==============================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_list_get_and_stats(
    client_a, embed_api_token_a, embed_api_token_b
):
    """Test API token list view returns 200, context statistics, and filters by tenant."""
    url = reverse("bi:embed_api_token_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "tokens" in resp.context
    assert "embed_api_tokens" in resp.context
    assert resp.context["total_count"] >= 1
    assert resp.context["active_count"] >= 1
    assert "revoked_count" in resp.context
    assert "status_choices" in resp.context

    item_pks = [t.pk for t in resp.context["tokens"]]
    assert embed_api_token_a.pk in item_pks
    assert embed_api_token_b.pk not in item_pks


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_list_search(
    client_a, tenant_a, admin_user, embedded_analytics_config_a
):
    """Test searching API tokens by name, number, and token prefix."""
    token = _embeddedmobilebi_create_api_token(
        tenant_a,
        config=embedded_analytics_config_a,
        user=admin_user,
        name="UniqueSearchTokenAlpha",
        token_prefix="eapi_live_uniq99",
    )
    url = reverse("bi:embed_api_token_list")

    resp_name = client_a.get(url, {"q": "SearchTokenAlpha"})
    assert resp_name.status_code == 200
    assert any(t.pk == token.pk for t in resp_name.context["tokens"])

    resp_prefix = client_a.get(url, {"q": "uniq99"})
    assert resp_prefix.status_code == 200
    assert any(t.pk == token.pk for t in resp_prefix.context["tokens"])


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_list_filter(
    client_a, tenant_a, admin_user, embedded_analytics_config_a
):
    """Test filtering API tokens by status."""
    token = _embeddedmobilebi_create_api_token(
        tenant_a,
        config=embedded_analytics_config_a,
        user=admin_user,
        name="Revoked Filter Token",
        status="revoked",
    )
    url = reverse("bi:embed_api_token_list")

    resp = client_a.get(url, {"status": "revoked"})
    assert resp.status_code == 200
    assert all(t.status == "revoked" for t in resp.context["tokens"])


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_list_pagination(
    client_a, tenant_a, admin_user, embedded_analytics_config_a
):
    """Test API token pagination at 20 items."""
    bulk = [
        EmbedApiToken(
            tenant=tenant_a,
            number=f"EAPI-PAG-{i:05d}",
            name=f"Bulk Token {i}",
            embedded_config=embedded_analytics_config_a,
            token_prefix=f"eapi_live_{i}",
            token_hash=hashlib.sha256(f"secret_{i}".encode()).hexdigest(),
            status="active",
            created_by=admin_user,
        )
        for i in range(25)
    ]
    EmbedApiToken.objects.bulk_create(bulk)

    url = reverse("bi:embed_api_token_list")
    resp = client_a.get(url, {"page": "1"})
    assert resp.status_code == 200
    assert len(resp.context["tokens"]) == 20


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_create_get(client_a):
    """Test token create view GET returns 200 and form."""
    url = reverse("bi:embed_api_token_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_create_post_success_and_hash(
    client_a, tenant_a, admin_user, embedded_analytics_config_a
):
    """Test token creation generates secret in session, stores SHA-256 hash in DB, and logs audit."""
    url = reverse("bi:embed_api_token_create")
    payload = {
        "name": "Integration Service SDK Key",
        "status": "active",
        "embedded_config": str(embedded_analytics_config_a.pk),
        "allowed_ip_ranges": "192.168.10.0/24",
        "rate_limit_rpm": 240,
        "expires_at": "",
        "scopes_raw": "read:dashboard, embed:render, query:data",
        "injected_rls_context_raw": json.dumps({"region": "LATAM"}),
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = EmbedApiToken.objects.get(name="Integration Service SDK Key")
    assert resp.url == reverse("bi:embed_api_token_detail", kwargs={"pk": created.pk})
    assert created.tenant == tenant_a
    assert created.created_by == admin_user
    assert created.token_prefix.startswith("eapi_live_")

    # One-time secret key stored in session
    session_secret = client_a.session.get("newly_generated_token")
    assert session_secret is not None
    assert session_secret.startswith(created.token_prefix)

    # Hash in DB matches SHA-256 of secret
    expected_hash = hashlib.sha256(session_secret.encode("utf-8")).hexdigest()
    assert created.token_hash == expected_hash

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        object_id=str(created.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_create_post_invalid(client_a):
    """Test token create POST invalid data returns 200 with form errors."""
    url = reverse("bi:embed_api_token_create")
    resp = client_a.post(url, data={"name": ""})
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_detail_one_time_reveal_banner(
    client_a, embed_api_token_a
):
    """Test token detail view reveals plaintext key once from session, then clears it."""
    # Inject one-time secret into session
    session = client_a.session
    raw_key = f"{embed_api_token_a.token_prefix}secret1234567890"
    session["newly_generated_token"] = raw_key
    session.save()

    url = reverse("bi:embed_api_token_detail", kwargs={"pk": embed_api_token_a.pk})

    # First GET: key is revealed in banner
    resp1 = client_a.get(url)
    assert resp1.status_code == 200
    assert resp1.context["new_key"] == raw_key
    assert raw_key in resp1.content.decode()
    assert "Save Your Plaintext API Secret Key Now" in resp1.content.decode()
    assert "js_sdk_snippet" in resp1.context
    assert "curl_snippet" in resp1.context

    # Second GET: key is popped from session, banner absent
    resp2 = client_a.get(url)
    assert resp2.status_code == 200
    assert resp2.context["new_key"] is None
    assert "Save Your Plaintext API Secret Key Now" not in resp2.content.decode()


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_detail_created_by_none(
    client_a, tenant_a
):
    """Test token detail view renders without 500 when created_by is None."""
    token = _embeddedmobilebi_create_api_token(tenant_a, user=None, name="System API Token")
    url = reverse("bi:embed_api_token_detail", kwargs={"pk": token.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "System" in resp.content.decode()


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_edit_get(client_a, embed_api_token_a):
    """Test token edit GET returns 200 and form."""
    url = reverse("bi:embed_api_token_edit", kwargs={"pk": embed_api_token_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["token"] == embed_api_token_a


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_edit_post_success(
    client_a, tenant_a, admin_user, embed_api_token_a, embedded_analytics_config_a
):
    """Test token edit POST updates attributes, logs audit, and redirects."""
    url = reverse("bi:embed_api_token_edit", kwargs={"pk": embed_api_token_a.pk})
    payload = {
        "name": "Acme Production SDK Key Updated",
        "status": "active",
        "embedded_config": str(embedded_analytics_config_a.pk),
        "allowed_ip_ranges": "10.0.0.0/16",
        "rate_limit_rpm": 300,
        "expires_at": "",
        "scopes_raw": "read:dashboard, read:report",
        "injected_rls_context_raw": json.dumps({"department": "Engineering"}),
    }
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:embed_api_token_detail", kwargs={"pk": embed_api_token_a.pk})

    embed_api_token_a.refresh_from_db()
    assert embed_api_token_a.name == "Acme Production SDK Key Updated"
    assert embed_api_token_a.rate_limit_rpm == 300
    assert embed_api_token_a.allowed_ip_ranges == "10.0.0.0/16"

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="update",
        object_id=str(embed_api_token_a.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_delete_post_success(
    client_a, tenant_a, admin_user
):
    """Test token delete POST removes record, logs audit, and redirects to list."""
    token = _embeddedmobilebi_create_api_token(tenant_a, user=admin_user, name="To Delete Token")
    url = reverse("bi:embed_api_token_delete", kwargs={"pk": token.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:embed_api_token_list")
    assert not EmbedApiToken.objects.filter(pk=token.pk).exists()

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=str(token.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_delete_get_not_allowed(client_a, embed_api_token_a):
    """Test token delete GET returns 405 Method Not Allowed."""
    url = reverse("bi:embed_api_token_delete", kwargs={"pk": embed_api_token_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405
    assert EmbedApiToken.objects.filter(pk=embed_api_token_a.pk).exists()


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_revoke_post_success(
    client_a, tenant_a, admin_user, embed_api_token_a
):
    """Test token revoke POST changes status to revoked, logs audit, and redirects."""
    assert embed_api_token_a.status == "active"
    url = reverse("bi:embed_api_token_revoke", kwargs={"pk": embed_api_token_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:embed_api_token_detail", kwargs={"pk": embed_api_token_a.pk})

    embed_api_token_a.refresh_from_db()
    assert embed_api_token_a.status == "revoked"

    audit = AuditLog.objects.filter(
        tenant=tenant_a,
        action="revoke",
        object_id=str(embed_api_token_a.pk),
    ).first()
    assert audit is not None


@pytest.mark.django_db
def test_embeddedmobilebi_views_token_revoke_get_not_allowed(client_a, embed_api_token_a):
    """Test token revoke GET returns 405 Method Not Allowed."""
    url = reverse("bi:embed_api_token_revoke", kwargs={"pk": embed_api_token_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 405


# ==============================================================================
# 5. Multi-tenancy IDOR & Permissions Tests
# ==============================================================================


@pytest.mark.django_db
def test_embeddedmobilebi_views_cross_tenant_idor_protection(
    client_a,
    embedded_analytics_config_b,
    kiosk_wallboard_display_b,
    mobile_bi_config_b,
    embed_api_token_b,
):
    """Test client A attempting to access tenant B resources returns 404."""
    # 1. Embedded Config
    assert client_a.get(reverse("bi:embedded_analytics_config_detail", kwargs={"pk": embedded_analytics_config_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:embedded_analytics_config_edit", kwargs={"pk": embedded_analytics_config_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:embedded_analytics_config_delete", kwargs={"pk": embedded_analytics_config_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:embedded_analytics_config_preview", kwargs={"pk": embedded_analytics_config_b.pk})).status_code == 404

    # 2. Kiosk Display
    assert client_a.get(reverse("bi:kiosk_wallboard_display_detail", kwargs={"pk": kiosk_wallboard_display_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:kiosk_wallboard_display_edit", kwargs={"pk": kiosk_wallboard_display_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:kiosk_wallboard_display_delete", kwargs={"pk": kiosk_wallboard_display_b.pk})).status_code == 404

    # 3. Mobile Config
    assert client_a.get(reverse("bi:mobile_bi_config_detail", kwargs={"pk": mobile_bi_config_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:mobile_bi_config_edit", kwargs={"pk": mobile_bi_config_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:mobile_bi_config_delete", kwargs={"pk": mobile_bi_config_b.pk})).status_code == 404

    # 4. API Token
    assert client_a.get(reverse("bi:embed_api_token_detail", kwargs={"pk": embed_api_token_b.pk})).status_code == 404
    assert client_a.get(reverse("bi:embed_api_token_edit", kwargs={"pk": embed_api_token_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:embed_api_token_delete", kwargs={"pk": embed_api_token_b.pk})).status_code == 404
    assert client_a.post(reverse("bi:embed_api_token_revoke", kwargs={"pk": embed_api_token_b.pk})).status_code == 404


@pytest.mark.django_db
def test_embeddedmobilebi_views_non_admin_permission_denied(
    tenant_a,
    embedded_analytics_config_a,
    kiosk_wallboard_display_a,
    mobile_bi_config_a,
    embed_api_token_a,
):
    """Test regular tenant member without is_tenant_admin is denied (403) from mutation views."""
    member_user = _embeddedmobilebi_create_member_user(tenant_a, username="member_non_admin")
    member_client = Client()
    member_client.force_login(member_user)

    # Reads are permitted for tenant members
    assert member_client.get(reverse("bi:embedded_analytics_config_list")).status_code == 200
    assert member_client.get(reverse("bi:embedded_analytics_config_detail", kwargs={"pk": embedded_analytics_config_a.pk})).status_code == 200

    # Mutations are rejected with 403 PermissionDenied
    assert member_client.get(reverse("bi:embedded_analytics_config_create")).status_code == 403
    assert member_client.get(reverse("bi:embedded_analytics_config_edit", kwargs={"pk": embedded_analytics_config_a.pk})).status_code == 403
    assert member_client.post(reverse("bi:embedded_analytics_config_delete", kwargs={"pk": embedded_analytics_config_a.pk})).status_code == 403

    assert member_client.get(reverse("bi:kiosk_wallboard_display_create")).status_code == 403
    assert member_client.post(reverse("bi:kiosk_wallboard_display_delete", kwargs={"pk": kiosk_wallboard_display_a.pk})).status_code == 403

    assert member_client.get(reverse("bi:mobile_bi_config_create")).status_code == 403
    assert member_client.post(reverse("bi:mobile_bi_config_delete", kwargs={"pk": mobile_bi_config_a.pk})).status_code == 403

    assert member_client.get(reverse("bi:embed_api_token_create")).status_code == 403
    assert member_client.post(reverse("bi:embed_api_token_revoke", kwargs={"pk": embed_api_token_a.pk})).status_code == 403


@pytest.mark.django_db
def test_embeddedmobilebi_views_anonymous_redirect_to_login(
    anon_client,
    embedded_analytics_config_a,
    kiosk_wallboard_display_a,
    mobile_bi_config_a,
    embed_api_token_a,
):
    """Test anonymous user accessing protected endpoints is redirected to login (302)."""
    endpoints = [
        reverse("bi:embedded_analytics_config_list"),
        reverse("bi:embedded_analytics_config_create"),
        reverse("bi:embedded_analytics_config_detail", kwargs={"pk": embedded_analytics_config_a.pk}),
        reverse("bi:embedded_analytics_config_preview", kwargs={"pk": embedded_analytics_config_a.pk}),
        reverse("bi:kiosk_wallboard_display_list"),
        reverse("bi:kiosk_wallboard_display_create"),
        reverse("bi:kiosk_wallboard_display_detail", kwargs={"pk": kiosk_wallboard_display_a.pk}),
        reverse("bi:mobile_bi_config_list"),
        reverse("bi:mobile_bi_config_create"),
        reverse("bi:mobile_bi_config_detail", kwargs={"pk": mobile_bi_config_a.pk}),
        reverse("bi:embed_api_token_list"),
        reverse("bi:embed_api_token_create"),
        reverse("bi:embed_api_token_detail", kwargs={"pk": embed_api_token_a.pk}),
    ]
    for url in endpoints:
        resp = anon_client.get(url)
        assert resp.status_code == 302
        assert "/accounts/login/" in resp.url or "/login/" in resp.url
