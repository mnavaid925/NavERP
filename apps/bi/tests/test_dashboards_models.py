"""Unit tests for Sub-module 10.8 Dashboards & Visualization models.

Models covered:
- BiDashboard (BDSH)
- BiDashboardWidget (BWID)
- BiDashboardBookmark (BBMK)
- BiDashboardFilter (BFIL)
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.bi.models import (
    BiDashboard,
    BiDashboardBookmark,
    BiDashboardFilter,
    BiDashboardWidget,
)


def _dashboards_choice_keys(choices_tuple):
    """Helper to extract keys from model choices tuple."""
    return [c[0] for c in choices_tuple]


# ---------------------------------------------------------------------------
# 1. BiDashboard Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_dashboard_creation_and_autonumber(tenant_a, admin_user):
    """Test BiDashboard creation, BDSH- prefix, and default field values."""
    dashboard = BiDashboard.objects.create(
        tenant=tenant_a,
        title="Revenue Analysis 2026",
        description="Comprehensive quarterly revenue review",
        category="financial",
        created_by=admin_user,
    )
    assert dashboard.NUMBER_PREFIX == "BDSH"
    assert dashboard.number.startswith("BDSH-")
    assert dashboard.title == "Revenue Analysis 2026"
    assert dashboard.slug == "revenue-analysis-2026"
    assert dashboard.theme == "light"
    assert dashboard.layout_type == "grid_12"
    assert dashboard.refresh_cadence == "manual"
    assert dashboard.auto_refresh_seconds == 0
    assert dashboard.is_published is False
    assert dashboard.is_favorite is False
    assert dashboard.is_kiosk_enabled is False
    assert dashboard.is_active is True
    assert str(dashboard) == f"{dashboard.number} - Revenue Analysis 2026"


@pytest.mark.django_db
def test_dashboards_dashboard_unique_tenant_slug(tenant_a, tenant_b, admin_user, admin_user_b):
    """Test that slug is unique per tenant, but same slug is permitted across tenants."""
    BiDashboard.objects.create(
        tenant=tenant_a,
        title="Ops Pulse",
        slug="ops-pulse",
        created_by=admin_user,
    )

    # Reusing same slug within tenant_a must raise IntegrityError
    with pytest.raises(IntegrityError):
        BiDashboard.objects.create(
            tenant=tenant_a,
            title="Ops Pulse Duplicate",
            slug="ops-pulse",
            created_by=admin_user,
        )

    # Same slug in tenant_b must succeed
    dash_b = BiDashboard.objects.create(
        tenant=tenant_b,
        title="Ops Pulse Globex",
        slug="ops-pulse",
        created_by=admin_user_b,
    )
    assert dash_b.slug == "ops-pulse"
    assert dash_b.tenant == tenant_b


@pytest.mark.django_db
def test_dashboards_dashboard_clean_auto_slugify(tenant_a, admin_user):
    """Test that clean() generates a sanitized slug if left empty."""
    dashboard = BiDashboard(
        tenant=tenant_a,
        title="Supply Chain & Logistics Pulse 2026!",
        slug="",
        created_by=admin_user,
    )
    dashboard.clean()
    assert dashboard.slug == "supply-chain-logistics-pulse-2026"


@pytest.mark.django_db
def test_dashboards_dashboard_choices():
    """Test choices sets on BiDashboard model."""
    categories = _dashboards_choice_keys(BiDashboard.CATEGORY_CHOICES)
    assert "executive" in categories
    assert "financial" in categories
    assert "operational" in categories
    assert "strategic" in categories

    themes = _dashboards_choice_keys(BiDashboard.THEME_CHOICES)
    assert "light" in themes
    assert "dark" in themes
    assert "navy_slate" in themes

    layouts = _dashboards_choice_keys(BiDashboard.LAYOUT_CHOICES)
    assert "grid_12" in layouts
    assert "canvas_freeform" in layouts


# ---------------------------------------------------------------------------
# 2. BiDashboardWidget Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_widget_creation_and_autonumber(tenant_a, bi_dashboard_a, admin_user):
    """Test BiDashboardWidget creation, BWID- prefix, and default coordinates."""
    widget = BiDashboardWidget.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        title="Net Margin Trend",
        widget_type="line_trend",
        created_by=admin_user,
    )
    assert widget.NUMBER_PREFIX == "BWID"
    assert widget.number.startswith("BWID-")
    assert widget.pos_x == 0
    assert widget.pos_y == 0
    assert widget.width_cols == 6
    assert widget.height_rows == 4
    assert widget.color_scheme == "primary"
    assert widget.chart_config == {}
    assert str(widget) == f"{widget.number} - Net Margin Trend (Line Trend)"


@pytest.mark.django_db
def test_dashboards_widget_clean_bounds_validation(tenant_a, bi_dashboard_a, admin_user):
    """Test widget position validation in clean(): pos_x + width_cols <= 12."""
    # Exceeding 12 grid columns must fail
    widget_invalid = BiDashboardWidget(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        title="Oversized Widget",
        widget_type="bar_chart",
        pos_x=10,
        width_cols=4,  # 10 + 4 = 14 > 12
        created_by=admin_user,
    )
    with pytest.raises(ValidationError):
        widget_invalid.clean()

    # Valid coordinates within 12 columns
    widget_valid = BiDashboardWidget(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        title="Fitted Widget",
        widget_type="bar_chart",
        pos_x=6,
        width_cols=6,  # 6 + 6 = 12 <= 12
        created_by=admin_user,
    )
    widget_valid.clean()  # should not raise


@pytest.mark.django_db
def test_dashboards_widget_cascade_delete_with_dashboard(tenant_a, admin_user):
    """Test that deleting a dashboard cascades to all its widgets."""
    dash = BiDashboard.objects.create(
        tenant=tenant_a,
        title="Ephemeral Dashboard",
        slug="ephemeral-dashboard",
        created_by=admin_user,
    )
    widget = BiDashboardWidget.objects.create(
        tenant=tenant_a,
        dashboard=dash,
        title="Ephemeral Widget",
        widget_type="kpi_card",
        created_by=admin_user,
    )
    dash_id = dash.id
    widget_id = widget.id

    dash.delete()
    assert not BiDashboard.objects.filter(id=dash_id).exists()
    assert not BiDashboardWidget.objects.filter(id=widget_id).exists()


# ---------------------------------------------------------------------------
# 3. BiDashboardBookmark Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_bookmark_creation_and_autonumber(tenant_a, bi_dashboard_a, admin_user):
    """Test BiDashboardBookmark creation, BBMK- prefix, and string representation."""
    bm = BiDashboardBookmark.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        user=admin_user,
        name="EMEA Sales Directors",
        filters_payload={"region": "EMEA"},
        crossfilter_state={"tier": "Enterprise"},
        is_shared=True,
    )
    assert bm.NUMBER_PREFIX == "BBMK"
    assert bm.number.startswith("BBMK-")
    assert bm.filters_payload == {"region": "EMEA"}
    assert bm.crossfilter_state == {"tier": "Enterprise"}
    assert bm.is_shared is True
    # Verify M10: __str__ does not traverse FK to avoid N+1
    assert str(bm) == f"{bm.name} ({bm.number})"


@pytest.mark.django_db
def test_dashboards_bookmark_unique_tenant_dashboard_user_name(tenant_a, bi_dashboard_a, admin_user):
    """Test user-scoped uniqueness constraint for dashboard bookmarks."""
    BiDashboardBookmark.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        user=admin_user,
        name="Fiscal Q1",
    )

    with pytest.raises(IntegrityError):
        BiDashboardBookmark.objects.create(
            tenant=tenant_a,
            dashboard=bi_dashboard_a,
            user=admin_user,
            name="Fiscal Q1",
        )


# ---------------------------------------------------------------------------
# 4. BiDashboardFilter Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_filter_creation_and_autonumber(tenant_a, bi_dashboard_a):
    """Test BiDashboardFilter creation, BFIL- prefix, and auto-slugified filter_key."""
    filt = BiDashboardFilter.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        filter_label="Customer Tier",
        filter_key="customer_tier",
        filter_type="select",
        default_value="All",
        options_source="static",
        static_options=[{"value": "All", "label": "All Tiers"}, {"value": "Gold", "label": "Gold"}],
        display_order=2,
    )
    assert filt.NUMBER_PREFIX == "BFIL"
    assert filt.number.startswith("BFIL-")
    assert filt.filter_label == "Customer Tier"
    assert filt.filter_key == "customer_tier"
    assert filt.is_global is True
    assert str(filt) == "Customer Tier (customer_tier)"


@pytest.mark.django_db
def test_dashboards_filter_clean_auto_slugify_key(tenant_a, bi_dashboard_a):
    """Test that clean() generates filter_key from filter_label if empty."""
    filt = BiDashboardFilter(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        filter_label="Shipping Country / Region",
        filter_key="",
        filter_type="select",
    )
    filt.clean()
    assert filt.filter_key == "shipping_country_region"


@pytest.mark.django_db
def test_dashboards_filter_unique_dashboard_key(tenant_a, bi_dashboard_a):
    """Test that filter_key is unique per dashboard within the tenant."""
    BiDashboardFilter.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        filter_label="Segment A",
        filter_key="segment",
    )

    with pytest.raises(IntegrityError):
        BiDashboardFilter.objects.create(
            tenant=tenant_a,
            dashboard=bi_dashboard_a,
            filter_label="Segment B",
            filter_key="segment",
        )
