"""Unit tests for Sub-module 10.8 Dashboards & Visualization models.

Models covered:
- BiDashboard (BDSH)
- BiDashboardWidget (BDWG)
- BiDashboardBookmark (BDBM)
- BiDashboardFilter (BDFL)
"""
import pytest
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
    """Test BiDashboard creation, BDSH- prefix, default field values, and str."""
    dashboard = BiDashboard.objects.create(
        tenant=tenant_a,
        title="Revenue Analysis 2026",
        slug="revenue-analysis-2026",
        description="Comprehensive quarterly revenue review",
        category="finance",
        created_by=admin_user,
    )
    assert dashboard.NUMBER_PREFIX == "BDSH"
    assert dashboard.number.startswith("BDSH-")
    assert dashboard.title == "Revenue Analysis 2026"
    assert dashboard.slug == "revenue-analysis-2026"
    assert dashboard.theme == "slate_corporate"
    assert dashboard.layout_type == "grid_12"
    assert dashboard.refresh_interval_seconds == 0
    assert dashboard.is_published is False
    assert dashboard.is_default is False
    assert dashboard.is_template is False
    assert dashboard.is_kiosk_enabled is False
    assert dashboard.is_active is True
    assert str(dashboard) == f"{dashboard.title} ({dashboard.number})"
    assert dashboard.badge_theme == "badge-slate"
    assert dashboard.badge_category == "badge-green"
    assert dashboard.get_absolute_url() == f"/bi/dashboards/{dashboard.pk}/"


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
def test_dashboards_dashboard_choices():
    """Test choices sets on BiDashboard model."""
    categories = _dashboards_choice_keys(BiDashboard.CATEGORY_CHOICES)
    assert "executive" in categories
    assert "finance" in categories
    assert "sales_crm" in categories
    assert "operations" in categories

    themes = _dashboards_choice_keys(BiDashboard.THEME_CHOICES)
    assert "slate_corporate" in themes
    assert "indigo_modern" in themes
    assert "dark_observability" in themes

    layouts = _dashboards_choice_keys(BiDashboard.LAYOUT_TYPE_CHOICES)
    assert "grid_12" in layouts
    assert "executive_summary" in layouts


# ---------------------------------------------------------------------------
# 2. BiDashboardWidget Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dashboards_widget_creation_and_autonumber(tenant_a, bi_dashboard_a):
    """Test BiDashboardWidget creation, BDWG- prefix, and default coordinates."""
    widget = BiDashboardWidget.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        title="Net Margin Trend",
        widget_type="line",
    )
    assert widget.NUMBER_PREFIX == "BDWG"
    assert widget.number.startswith("BDWG-")
    assert widget.pos_x == 0
    assert widget.pos_y == 0
    assert widget.width_cols == 4
    assert widget.height_rows == 4
    assert widget.chart_config_json == {}
    assert widget.badge_widget_type == "badge-info"
    assert str(widget) == f"{widget.title} ({widget.number}) [Line Trend Chart]"


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
    """Test BiDashboardBookmark creation, BDBM- prefix, and string representation."""
    bm = BiDashboardBookmark.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        user=admin_user,
        name="EMEA Sales Directors",
        filter_state_json={"region": "EMEA"},
        crossfilter_state_json={"tier": "Enterprise"},
        is_shared=True,
    )
    assert bm.NUMBER_PREFIX == "BDBM"
    assert bm.number.startswith("BDBM-")
    assert bm.filter_state_json == {"region": "EMEA"}
    assert bm.crossfilter_state_json == {"tier": "Enterprise"}
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
    """Test BiDashboardFilter creation, BDFL- prefix, and string format."""
    filt = BiDashboardFilter.objects.create(
        tenant=tenant_a,
        dashboard=bi_dashboard_a,
        filter_label="Customer Tier",
        filter_key="customer_tier",
        filter_type="dropdown",
        default_value="All",
        options_source="static_list",
        static_options_json=[{"value": "All", "label": "All Tiers"}, {"value": "Gold", "label": "Gold"}],
        order=2,
    )
    assert filt.NUMBER_PREFIX == "BDFL"
    assert filt.number.startswith("BDFL-")
    assert filt.filter_label == "Customer Tier"
    assert filt.filter_key == "customer_tier"
    assert filt.badge_filter_type == "badge-info"
    assert str(filt) == f"{filt.filter_label} ({filt.filter_key}) [{filt.number}]"


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
