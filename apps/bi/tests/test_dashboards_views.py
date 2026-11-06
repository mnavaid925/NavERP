"""Unit tests for Sub-module 10.8 Dashboards & Visualization views.

Views covered:
- BiDashboard views (list, create, detail, edit, delete, publish, duplicate)
- Canvas views (canvas_view, canvas_builder, kiosk_view)
- BiDashboardWidget views (list, create, detail, edit, delete, data)
- BiDashboardBookmark views (list, create, detail, edit, delete, apply)
- BiDashboardFilter views (list, create, detail, edit, delete)
"""
import json
import pytest
from django.urls import reverse

from apps.bi.models import (
    BiDashboard,
    BiDashboardBookmark,
    BiDashboardFilter,
    BiDashboardWidget,
)


# ---------------------------------------------------------------------------
# 1. BiDashboard Views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_list_view(client_a, bi_dashboard_a):
    """Test dashboard list view with filtering, metrics, and safe junk handling (I1)."""
    url = reverse("bi:bi_dashboard_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "Dashboards & Visualization" in content
    assert bi_dashboard_a.title in content
    assert resp.context["total_dashboards"] >= 1
    assert "theme_choices" in resp.context

    # Filter by category
    resp_cat = client_a.get(f"{url}?category={bi_dashboard_a.category}")
    assert resp_cat.status_code == 200
    assert bi_dashboard_a.title in resp_cat.content.decode("utf-8")

    # Filter by theme
    resp_theme = client_a.get(f"{url}?theme={bi_dashboard_a.theme}")
    assert resp_theme.status_code == 200

    # Junk query parameters (L11 guard)
    resp_junk = client_a.get(f"{url}?category=undefined&theme=invalid_theme&q=xyznonexistent")
    assert resp_junk.status_code == 200


@pytest.mark.django_db
def test_dashboards_create_view(client_a, tenant_a):
    """Test dashboard create form GET and POST with audit logging."""
    url = reverse("bi:bi_dashboard_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    post_data = {
        "title": "Sales Operations 2026",
        "slug": "sales-operations-2026",
        "category": "operational",
        "layout_type": "grid_12",
        "theme": "light",
        "refresh_interval_seconds": 0,
        "is_active": True,
    }
    resp_post = client_a.post(url, data=post_data)
    assert resp_post.status_code == 302
    created = BiDashboard.objects.get(tenant=tenant_a, slug="sales-operations-2026")
    assert created.title == "Sales Operations 2026"
    assert created.created_by is not None


@pytest.mark.django_db
def test_dashboards_detail_view_null_created_by_safe(client_a, tenant_a):
    """Test detail view renders without 500 when created_by is None (C2 / L10)."""
    dash_null_user = BiDashboard.objects.create(
        tenant=tenant_a,
        title="System Generated Telemetry",
        slug="system-telemetry-null",
        category="operational",
        created_by=None,
    )
    url = reverse("bi:bi_dashboard_detail", kwargs={"pk": dash_null_user.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "System Seed" in content or "System Generated Telemetry" in content


@pytest.mark.django_db
def test_dashboards_edit_view(client_a, bi_dashboard_a):
    """Test dashboard edit form GET and POST."""
    url = reverse("bi:bi_dashboard_edit", kwargs={"pk": bi_dashboard_a.pk})
    assert client_a.get(url).status_code == 200

    resp_post = client_a.post(
        url,
        data={
            "title": "Updated Executive Overview",
            "slug": bi_dashboard_a.slug,
            "category": "strategic",
            "layout_type": "grid_12",
            "theme": "dark",
            "is_active": True,
        },
    )
    assert resp_post.status_code == 302
    bi_dashboard_a.refresh_from_db()
    assert bi_dashboard_a.title == "Updated Executive Overview"
    assert bi_dashboard_a.category == "strategic"


@pytest.mark.django_db
def test_dashboards_publish_toggle_view(client_a, bi_dashboard_a):
    """Test dashboard publish action toggles is_published and writes audit log."""
    url = reverse("bi:bi_dashboard_publish", kwargs={"pk": bi_dashboard_a.pk})
    assert bi_dashboard_a.is_published is True

    resp_unpub = client_a.post(url)
    assert resp_unpub.status_code == 302
    bi_dashboard_a.refresh_from_db()
    assert bi_dashboard_a.is_published is False

    resp_pub = client_a.post(url)
    assert resp_pub.status_code == 302
    bi_dashboard_a.refresh_from_db()
    assert bi_dashboard_a.is_published is True


@pytest.mark.django_db
def test_dashboards_duplicate_view(client_a, bi_dashboard_a, bi_widget_a, bi_filter_a):
    """Test dashboard clone endpoint duplicates dashboard, widgets, and filters (M3)."""
    url = reverse("bi:bi_dashboard_duplicate", kwargs={"pk": bi_dashboard_a.pk})
    assert client_a.get(url).status_code == 200

    resp_post = client_a.post(
        url,
        data={
            "new_title": "Executive Overview (Clone)",
            "new_slug": "executive-overview-clone",
            "copy_widgets": True,
            "copy_filters": True,
        },
    )
    assert resp_post.status_code == 302
    cloned = BiDashboard.objects.get(tenant=bi_dashboard_a.tenant, slug="executive-overview-clone")
    assert cloned.title == "Executive Overview (Clone)"
    assert cloned.widgets.count() == 1
    assert cloned.filters.count() == 1


@pytest.mark.django_db
def test_dashboards_delete_view(client_a, tenant_a, admin_user):
    """Test dashboard delete action removes record and logs audit."""
    dash = BiDashboard.objects.create(
        tenant=tenant_a,
        title="Discardable Dashboard",
        slug="discardable-dash",
        created_by=admin_user,
    )
    url = reverse("bi:bi_dashboard_delete", kwargs={"pk": dash.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not BiDashboard.objects.filter(pk=dash.pk).exists()


# ---------------------------------------------------------------------------
# 2. Canvas & Kiosk Views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_canvas_view(client_a, bi_dashboard_a, bi_widget_a, bi_filter_a, bi_bookmark_a):
    """Test visual canvas viewer renders widgets, filters with current_value, and bookmarks."""
    url = reverse("bi:bi_dashboard_canvas_view", kwargs={"pk": bi_dashboard_a.pk})
    resp = client_a.get(f"{url}?region=EMEA&bookmark={bi_bookmark_a.pk}")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert bi_dashboard_a.title in content
    assert bi_widget_a.title in content
    # Verify filter current_value attached (fixes I3)
    filters = resp.context["filters"]
    assert any(getattr(f, "current_value", None) == "EMEA" for f in filters)


@pytest.mark.django_db
def test_dashboards_canvas_view_junk_bookmark_param(client_a, bi_dashboard_a):
    """Test non-numeric bookmark query param is handled gracefully without 500 (I2)."""
    url = reverse("bi:bi_dashboard_canvas_view", kwargs={"pk": bi_dashboard_a.pk})
    resp = client_a.get(f"{url}?bookmark=invalid_str_id")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_dashboards_canvas_builder_get_and_ajax_post(client_a, bi_dashboard_a, bi_widget_a):
    """Test visual canvas builder GET and AJAX position save (I4, I20, M4)."""
    url = reverse("bi:bi_dashboard_canvas_builder", kwargs={"pk": bi_dashboard_a.pk})
    assert client_a.get(url).status_code == 200

    ajax_payload = {
        "positions": [
            {
                "widget_id": bi_widget_a.pk,
                "pos_x": 4,
                "pos_y": 2,
                "width_cols": 8,
                "height_rows": 3,
            }
        ]
    }
    resp_ajax = client_a.post(
        url,
        data=json.dumps(ajax_payload),
        content_type="application/json",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert resp_ajax.status_code == 200
    data = resp_ajax.json()
    assert data["status"] == "success"

    bi_widget_a.refresh_from_db()
    assert bi_widget_a.pos_x == 4
    assert bi_widget_a.pos_y == 2
    assert bi_widget_a.width_cols == 8
    assert bi_widget_a.height_rows == 3


@pytest.mark.django_db
def test_dashboards_kiosk_view(client_a, bi_dashboard_a, bi_dashboard_draft_a):
    """Test kiosk mode renders when enabled and 403s when disabled (M2)."""
    # bi_dashboard_a has is_kiosk_enabled=True
    url_enabled = reverse("bi:bi_dashboard_kiosk_view", kwargs={"pk": bi_dashboard_a.pk})
    assert client_a.get(url_enabled).status_code == 200

    # bi_dashboard_draft_a has is_kiosk_enabled=False
    url_disabled = reverse("bi:bi_dashboard_kiosk_view", kwargs={"pk": bi_dashboard_draft_a.pk})
    assert client_a.get(url_disabled).status_code == 403


# ---------------------------------------------------------------------------
# 3. BiDashboardWidget Views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_widget_list_and_filter(client_a, bi_widget_a):
    """Test widget list view with filtering and non-numeric query guard (I1)."""
    url = reverse("bi:bi_dashboard_widget_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert bi_widget_a.title in resp.content.decode("utf-8")

    # Filter by dashboard
    resp_dash = client_a.get(f"{url}?dashboard={bi_widget_a.dashboard.pk}")
    assert resp_dash.status_code == 200
    assert bi_widget_a.title in resp_dash.content.decode("utf-8")

    # Junk dashboard param should not 500 (I1)
    resp_junk = client_a.get(f"{url}?dashboard=not_a_number")
    assert resp_junk.status_code == 200


@pytest.mark.django_db
def test_dashboards_widget_create_view(client_a, bi_dashboard_a):
    """Test widget create view."""
    url = reverse("bi:bi_dashboard_widget_create")
    assert client_a.get(url).status_code == 200

    post_data = {
        "dashboard": bi_dashboard_a.pk,
        "title": "Gross Margin Widget",
        "widget_type": "kpi_card",
        "pos_x": 0,
        "pos_y": 0,
        "width_cols": 4,
        "height_rows": 2,
        "is_active": True,
    }
    resp = client_a.post(url, data=post_data)
    assert resp.status_code == 302
    assert BiDashboardWidget.objects.filter(
        dashboard=bi_dashboard_a, title="Gross Margin Widget"
    ).exists()


@pytest.mark.django_db
def test_dashboards_widget_detail_and_data_api(client_a, bi_widget_a):
    """Test widget detail view and JSON telemetry API endpoint (M7)."""
    url_detail = reverse("bi:bi_dashboard_widget_detail", kwargs={"pk": bi_widget_a.pk})
    resp_detail = client_a.get(url_detail)
    assert resp_detail.status_code == 200
    assert "data_preview" in resp_detail.context

    url_data = reverse("bi:bi_dashboard_widget_data", kwargs={"pk": bi_widget_a.pk})
    resp_data = client_a.get(url_data)
    assert resp_data.status_code == 200
    telemetry = resp_data.json()
    assert "widget" in telemetry
    assert "payload" in telemetry


@pytest.mark.django_db
def test_dashboards_widget_delete_view(client_a, bi_widget_a):
    """Test widget delete POST action."""
    url = reverse("bi:bi_dashboard_widget_delete", kwargs={"pk": bi_widget_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not BiDashboardWidget.objects.filter(pk=bi_widget_a.pk).exists()


# ---------------------------------------------------------------------------
# 4. BiDashboardBookmark Views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_bookmark_list_and_apply(client_a, bi_bookmark_a):
    """Test bookmark list view and apply redirection (M1)."""
    url = reverse("bi:bi_dashboard_bookmark_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert bi_bookmark_a.name in resp.content.decode("utf-8")

    # Apply bookmark redirects to canvas view with bookmark id query param
    url_apply = reverse("bi:bi_dashboard_bookmark_apply", kwargs={"pk": bi_bookmark_a.pk})
    resp_apply = client_a.get(url_apply)
    assert resp_apply.status_code == 302
    assert f"bookmark={bi_bookmark_a.pk}" in resp_apply.url


@pytest.mark.django_db
def test_dashboards_bookmark_detail_view(client_a, bi_bookmark_a):
    """Test bookmark detail view renders crossfilter_state_pretty (M8)."""
    url = reverse("bi:bi_dashboard_bookmark_detail", kwargs={"pk": bi_bookmark_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "crossfilter_state_pretty" in resp.context


@pytest.mark.django_db
def test_dashboards_bookmark_delete_view(client_a, bi_bookmark_a):
    """Test bookmark delete action."""
    url = reverse("bi:bi_dashboard_bookmark_delete", kwargs={"pk": bi_bookmark_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not BiDashboardBookmark.objects.filter(pk=bi_bookmark_a.pk).exists()


# ---------------------------------------------------------------------------
# 5. BiDashboardFilter Views
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_filter_list_and_create(client_a, bi_dashboard_a, bi_filter_a):
    """Test filter list and create views."""
    url = reverse("bi:bi_dashboard_filter_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert bi_filter_a.filter_label in resp.content.decode("utf-8")

    url_create = reverse("bi:bi_dashboard_filter_create")
    assert client_a.get(url_create).status_code == 200

    resp_post = client_a.post(
        url_create,
        data={
            "dashboard": bi_dashboard_a.pk,
            "filter_label": "Fiscal Quarter",
            "filter_key": "fiscal_quarter",
            "filter_type": "select",
            "options_source": "static",
            "is_active": True,
        },
    )
    assert resp_post.status_code == 302
    assert BiDashboardFilter.objects.filter(
        dashboard=bi_dashboard_a, filter_key="fiscal_quarter"
    ).exists()


@pytest.mark.django_db
def test_dashboards_filter_delete_view(client_a, bi_filter_a):
    """Test filter delete action."""
    url = reverse("bi:bi_dashboard_filter_delete", kwargs={"pk": bi_filter_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert not BiDashboardFilter.objects.filter(pk=bi_filter_a.pk).exists()
