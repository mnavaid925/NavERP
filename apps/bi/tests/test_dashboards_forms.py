"""Unit tests for Sub-module 10.8 Dashboards & Visualization forms.

Forms covered:
- BiDashboardForm
- BiDashboardDuplicateForm
- BiDashboardWidgetForm
- BiDashboardWidgetPositionForm
- BiDashboardBookmarkForm
- BiDashboardFilterForm
"""
import pytest

from apps.bi.forms.Dashboards import (
    BiDashboardBookmarkForm,
    BiDashboardDuplicateForm,
    BiDashboardFilterForm,
    BiDashboardForm,
    BiDashboardWidgetForm,
    BiDashboardWidgetPositionForm,
)
from apps.bi.models import BiDashboard, BiDashboardBookmark, BiDashboardFilter


# ---------------------------------------------------------------------------
# 1. BiDashboardForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_dashboard_form_valid_auto_slug(tenant_a):
    """Test valid dashboard form submission with empty slug auto-slugifying."""
    form_data = {
        "title": "Executive Global KPI Matrix",
        "slug": "",  # Empty to test auto-slugification (I8)
        "category": "executive",
        "layout_type": "grid_12",
        "refresh_interval_seconds": 60,
        "theme": "navy_slate",
        "role_required": "all",
        "description": "Enterprise executive board monitor",
        "is_active": True,
    }
    form = BiDashboardForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.slug == "executive-global-kpi-matrix"
    assert "is_published" not in form.fields  # I18 mass assignment guard


@pytest.mark.django_db
def test_dashboards_dashboard_form_duplicate_slug_rejected(tenant_a, bi_dashboard_a):
    """Test that form clean() rejects existing slug for the same tenant."""
    form_data = {
        "title": "Duplicate Executive Slug",
        "slug": bi_dashboard_a.slug,
        "category": "financial",
        "layout_type": "grid_12",
        "theme": "light",
        "is_active": True,
    }
    form = BiDashboardForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "slug" in form.errors


@pytest.mark.django_db
def test_dashboards_dashboard_form_duplicate_slug_allowed_cross_tenant(tenant_b, bi_dashboard_a):
    """Test that same slug is permitted across different tenants."""
    form_data = {
        "title": "Globex Duplicate Slug",
        "slug": bi_dashboard_a.slug,
        "category": "operational",
        "layout_type": "grid_12",
        "theme": "dark",
        "is_active": True,
    }
    form = BiDashboardForm(data=form_data, tenant=tenant_b)
    assert form.is_valid(), form.errors


# ---------------------------------------------------------------------------
# 2. BiDashboardDuplicateForm Tests
# ---------------------------------------------------------------------------


def test_dashboards_duplicate_form_validation():
    """Test duplicate dashboard clone parameters."""
    form_valid = BiDashboardDuplicateForm(
        data={
            "new_title": "Executive Clone 2027",
            "new_slug": "executive-clone-2027",
            "copy_widgets": True,
            "copy_filters": True,
        }
    )
    assert form_valid.is_valid(), form_valid.errors

    form_invalid = BiDashboardDuplicateForm(data={})
    assert not form_invalid.is_valid()
    assert "new_title" in form_invalid.errors


# ---------------------------------------------------------------------------
# 3. BiDashboardWidgetForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_widget_form_valid(tenant_a, bi_dashboard_a):
    """Test valid widget creation via form."""
    form_data = {
        "dashboard": bi_dashboard_a.pk,
        "title": "ARR Growth Rate",
        "subtitle": "Trailing twelve months",
        "widget_type": "kpi_card",
        "aggregation_type": "sum",
        "pos_x": 0,
        "pos_y": 0,
        "width_cols": 4,
        "height_rows": 2,
        "refresh_interval_seconds": 0,
        "sort_order": 1,
        "is_active": True,
    }
    form = BiDashboardWidgetForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_dashboards_widget_form_reject_foreign_dashboard(tenant_a, bi_dashboard_b):
    """Test that reject_foreign rejects dashboard belonging to another tenant."""
    form_data = {
        "dashboard": bi_dashboard_b.pk,  # Tenant B dashboard
        "title": "Cross Tenant Widget",
        "widget_type": "kpi_card",
        "pos_x": 0,
        "pos_y": 0,
        "width_cols": 4,
        "height_rows": 2,
        "is_active": True,
    }
    form = BiDashboardWidgetForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dashboard" in form.errors


@pytest.mark.django_db
def test_dashboards_widget_form_grid_overflow_rejected(tenant_a, bi_dashboard_a):
    """Test pos_x + width_cols > 12 is caught during validation."""
    form_data = {
        "dashboard": bi_dashboard_a.pk,
        "title": "Overflow Widget",
        "widget_type": "bar_chart",
        "pos_x": 10,
        "pos_y": 0,
        "width_cols": 4,  # 10 + 4 = 14 > 12
        "height_rows": 2,
        "is_active": True,
    }
    form = BiDashboardWidgetForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "width_cols" in form.errors or "pos_x" in form.errors or "__all__" in form.errors


# ---------------------------------------------------------------------------
# 4. BiDashboardWidgetPositionForm Tests
# ---------------------------------------------------------------------------


def test_dashboards_widget_position_form():
    """Test coordinate parsing and validation in position form."""
    form_valid = BiDashboardWidgetPositionForm(
        data={"pos_x": 4, "pos_y": 2, "width_cols": 4, "height_rows": 3}
    )
    assert form_valid.is_valid(), form_valid.errors

    form_invalid = BiDashboardWidgetPositionForm(
        data={"pos_x": -1, "pos_y": 2, "width_cols": 15, "height_rows": 0}
    )
    assert not form_invalid.is_valid()


# ---------------------------------------------------------------------------
# 5. BiDashboardBookmarkForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_bookmark_form_valid(tenant_a, bi_dashboard_a, admin_user):
    """Test bookmark creation with user context (I12)."""
    form_data = {
        "dashboard": bi_dashboard_a.pk,
        "name": "Western Pipeline View",
        "description": "Filtered for Western Region",
        "is_default": False,
        "is_shared": True,
        "is_active": True,
    }
    form = BiDashboardBookmarkForm(data=form_data, tenant=tenant_a, user=admin_user)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_dashboards_bookmark_form_duplicate_name_rejected(
    tenant_a, bi_dashboard_a, bi_bookmark_a, admin_user
):
    """Test duplicate bookmark name for same user is caught by clean() (I12)."""
    form_data = {
        "dashboard": bi_dashboard_a.pk,
        "name": bi_bookmark_a.name,  # Same name for same user
        "is_active": True,
    }
    form = BiDashboardBookmarkForm(data=form_data, tenant=tenant_a, user=admin_user)
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_dashboards_bookmark_form_reject_foreign_dashboard(tenant_a, bi_dashboard_b, admin_user):
    """Test reject_foreign prevents binding bookmark to foreign tenant dashboard."""
    form_data = {
        "dashboard": bi_dashboard_b.pk,  # Tenant B dashboard
        "name": "IDOR Bookmark",
        "is_active": True,
    }
    form = BiDashboardBookmarkForm(data=form_data, tenant=tenant_a, user=admin_user)
    assert not form.is_valid()
    assert "dashboard" in form.errors


# ---------------------------------------------------------------------------
# 6. BiDashboardFilterForm Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_filter_form_auto_slug_key(tenant_a, bi_dashboard_a):
    """Test that filter_key is auto-slugified from filter_label when blank (I9)."""
    form_data = {
        "dashboard": bi_dashboard_a.pk,
        "filter_label": "Global Currency Code",
        "filter_key": "",  # Blank to test auto-slugification
        "filter_type": "select",
        "target_field": "currency",
        "default_value": "USD",
        "options_source": "static",
        "order": 1,
        "is_required": False,
        "is_active": True,
    }
    form = BiDashboardFilterForm(data=form_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    instance = form.save(commit=False)
    instance.tenant = tenant_a
    instance.save()
    assert instance.filter_key == "global_currency_code"


@pytest.mark.django_db
def test_dashboards_filter_form_duplicate_key_rejected(tenant_a, bi_dashboard_a, bi_filter_a):
    """Test duplicate filter_key for same dashboard is rejected."""
    form_data = {
        "dashboard": bi_dashboard_a.pk,
        "filter_label": "Duplicate Region Filter",
        "filter_key": bi_filter_a.filter_key,
        "filter_type": "select",
        "options_source": "static",
        "is_active": True,
    }
    form = BiDashboardFilterForm(data=form_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "filter_key" in form.errors
