"""Tests for CRM sub-module 1.6 — Analytics & Reporting.

Covers:
  - AnalyticsDashboard (DASH- number, __str__, tenant scoping, widget_count)
  - DashboardWidget (child, position/metric/chart_type/date_range/size/target_value)
  - AnalyticsReport (RPT- number, __str__, last_run_at editable=False)
  - ReportSnapshot (child, summary/data JSON defaults)
  - analytics.range_bounds: all range keys including "all" → (None, None)
  - compute_widget: scalar, series, table, gauge, unknown metric error dict
  - Division-by-zero guards: win_rate with 0 closed opps; funnel with 0 entered
  - compute_report for all 4 types: shape + JSON-serializable round-trip
  - Forms: DashboardWidgetForm.clean rejects incompatible chart_type
  - Forms: AnalyticsReportForm.clean rejects invalid group_by per report_type
  - Forms: AnalyticsDashboardForm(can_share=False) drops is_shared/is_default
  - Views CRUD: list (200), create, edit, delete; dashboard_detail, report_detail
  - report_snapshot POST creates ReportSnapshot + redirects to snapshot_detail
  - report_favorite POST toggles is_favorite
  - widget_move POST reorders via bulk_update
  - Multi-tenant IDOR: cross-tenant pk → 404
  - Permission: non-admin member cannot set is_shared via POST (form drops it)
  - Auth: anonymous → redirect to login
"""
import json
import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ===================================================================== Fixtures

@pytest.fixture
def dashboard_a(db, tenant_a, admin_user):
    from apps.crm.models import AnalyticsDashboard
    return AnalyticsDashboard.objects.create(
        tenant=tenant_a,
        name="Sales Overview",
        owner=admin_user,
        layout="two",
    )


@pytest.fixture
def dashboard_b(db, tenant_b, admin_b):
    from apps.crm.models import AnalyticsDashboard
    return AnalyticsDashboard.objects.create(
        tenant=tenant_b,
        name="Globex Dashboard",
        owner=admin_b,
        layout="one",
    )


@pytest.fixture
def widget_a(db, tenant_a, dashboard_a):
    """A KPI scalar widget on dashboard_a."""
    from apps.crm.models import DashboardWidget
    return DashboardWidget.objects.create(
        tenant=tenant_a,
        dashboard=dashboard_a,
        title="Open Pipeline",
        metric="kpi_open_pipeline",
        chart_type="kpi",
        date_range="all",
        size="medium",
        position=0,
    )


@pytest.fixture
def widget_series(db, tenant_a, dashboard_a):
    """A series chart widget on dashboard_a."""
    from apps.crm.models import DashboardWidget
    return DashboardWidget.objects.create(
        tenant=tenant_a,
        dashboard=dashboard_a,
        title="Pipeline by Stage",
        metric="pipeline_by_stage",
        chart_type="bar",
        date_range="all",
        size="large",
        position=1,
    )


@pytest.fixture
def widget_table(db, tenant_a, dashboard_a):
    """A table widget on dashboard_a."""
    from apps.crm.models import DashboardWidget
    return DashboardWidget.objects.create(
        tenant=tenant_a,
        dashboard=dashboard_a,
        title="Top Performers",
        metric="top_performers",
        chart_type="table",
        date_range="all",
        size="full",
        position=2,
    )


@pytest.fixture
def widget_b(db, tenant_b, dashboard_b):
    from apps.crm.models import DashboardWidget
    return DashboardWidget.objects.create(
        tenant=tenant_b,
        dashboard=dashboard_b,
        title="Globex Pipeline",
        metric="kpi_open_pipeline",
        chart_type="kpi",
        date_range="all",
        size="medium",
        position=0,
    )


@pytest.fixture
def report_a(db, tenant_a, admin_user):
    from apps.crm.models import AnalyticsReport
    return AnalyticsReport.objects.create(
        tenant=tenant_a,
        name="Q1 Activity",
        report_type="sales_activity",
        date_range="all",
        group_by="month",
        owner=admin_user,
    )


@pytest.fixture
def report_b(db, tenant_b, admin_b):
    from apps.crm.models import AnalyticsReport
    return AnalyticsReport.objects.create(
        tenant=tenant_b,
        name="Globex Report",
        report_type="funnel",
        date_range="all",
        group_by="stage",
        owner=admin_b,
    )


@pytest.fixture
def snapshot_a(db, tenant_a, report_a, admin_user):
    from apps.crm.models import ReportSnapshot
    return ReportSnapshot.objects.create(
        tenant=tenant_a,
        report=report_a,
        title="Q1 Activity — 2026-01-01 00:00",
        generated_by=admin_user,
        summary=[{"label": "Total", "value": "5"}],
        data={"columns": ["Col1"], "rows": [[1]], "chart_type": "bar",
              "chart_label": "X", "chart_labels": ["A"], "chart_data": [1]},
    )


@pytest.fixture
def snapshot_b(db, tenant_b, report_b, admin_b):
    from apps.crm.models import ReportSnapshot
    return ReportSnapshot.objects.create(
        tenant=tenant_b,
        report=report_b,
        title="Globex — 2026-01-01",
        generated_by=admin_b,
    )


# ===================================================================== Model Tests

class TestAnalyticsDashboardModel:
    """AnalyticsDashboard — DASH- number, __str__, tenant scoping."""

    def test_number_format(self, tenant_a, admin_user):
        from apps.crm.models import AnalyticsDashboard
        d = AnalyticsDashboard.objects.create(tenant=tenant_a, name="My Board", owner=admin_user)
        assert d.number == "DASH-00001"

    def test_sequential_per_tenant(self, tenant_a, admin_user):
        from apps.crm.models import AnalyticsDashboard
        d1 = AnalyticsDashboard.objects.create(tenant=tenant_a, name="First", owner=admin_user)
        d2 = AnalyticsDashboard.objects.create(tenant=tenant_a, name="Second", owner=admin_user)
        assert d1.number == "DASH-00001"
        assert d2.number == "DASH-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b, admin_user, admin_b):
        from apps.crm.models import AnalyticsDashboard
        a = AnalyticsDashboard.objects.create(tenant=tenant_a, name="A", owner=admin_user)
        b = AnalyticsDashboard.objects.create(tenant=tenant_b, name="B", owner=admin_b)
        assert a.number == "DASH-00001"
        assert b.number == "DASH-00001"

    def test_str_contains_number_and_name(self, dashboard_a):
        s = str(dashboard_a)
        assert "DASH-00001" in s
        assert "Sales Overview" in s

    def test_is_shared_default_false(self, dashboard_a):
        assert dashboard_a.is_shared is False

    def test_is_default_default_false(self, dashboard_a):
        assert dashboard_a.is_default is False

    def test_widget_count_zero_initially(self, dashboard_a):
        assert dashboard_a.widget_count == 0

    def test_widget_count_increments(self, dashboard_a, widget_a):
        dashboard_a.refresh_from_db()
        assert dashboard_a.widget_count == 1

    def test_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import AnalyticsDashboard
        from django.db import IntegrityError
        AnalyticsDashboard.objects.create(tenant=tenant_a, name="First")
        with pytest.raises(IntegrityError):
            AnalyticsDashboard.objects.create(tenant=tenant_a, name="Dup", number="DASH-00001")


class TestDashboardWidgetModel:
    """DashboardWidget — child model, positional ordering, __str__."""

    def test_str_contains_title_and_chart_type_display(self, widget_a):
        s = str(widget_a)
        assert "Open Pipeline" in s
        assert "KPI Card" in s  # get_chart_type_display() for "kpi"

    def test_default_position_zero(self, dashboard_a, tenant_a):
        from apps.crm.models import DashboardWidget
        w = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a,
            title="New", metric="kpi_new_leads", chart_type="kpi", date_range="all")
        assert w.position == 0

    def test_target_value_nullable(self, dashboard_a, tenant_a):
        from apps.crm.models import DashboardWidget
        w = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a,
            title="No target", metric="kpi_open_pipeline", chart_type="kpi",
            date_range="all", target_value=None)
        assert w.target_value is None

    def test_ordering_by_position_then_id(self, dashboard_a, tenant_a):
        from apps.crm.models import DashboardWidget
        w1 = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a, title="Z", metric="kpi_new_leads",
            chart_type="kpi", date_range="all", position=10)
        w2 = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a, title="A", metric="kpi_open_cases",
            chart_type="kpi", date_range="all", position=0)
        order = list(DashboardWidget.objects.filter(dashboard=dashboard_a).values_list("title", flat=True))
        assert order[0] == "A"   # position 0 first


class TestAnalyticsReportModel:
    """AnalyticsReport — RPT- number, __str__, last_run_at editable=False."""

    def test_number_format(self, tenant_a):
        from apps.crm.models import AnalyticsReport
        r = AnalyticsReport.objects.create(tenant=tenant_a, name="My Report", report_type="funnel")
        assert r.number == "RPT-00001"

    def test_sequential_per_tenant(self, tenant_a):
        from apps.crm.models import AnalyticsReport
        r1 = AnalyticsReport.objects.create(tenant=tenant_a, name="First")
        r2 = AnalyticsReport.objects.create(tenant=tenant_a, name="Second")
        assert r1.number == "RPT-00001"
        assert r2.number == "RPT-00002"

    def test_per_tenant_isolation(self, tenant_a, tenant_b):
        from apps.crm.models import AnalyticsReport
        a = AnalyticsReport.objects.create(tenant=tenant_a, name="A")
        b = AnalyticsReport.objects.create(tenant=tenant_b, name="B")
        assert a.number == "RPT-00001"
        assert b.number == "RPT-00001"

    def test_str_contains_number_and_name(self, report_a):
        s = str(report_a)
        assert "RPT-00001" in s
        assert "Q1 Activity" in s

    def test_last_run_at_default_none(self, report_a):
        assert report_a.last_run_at is None

    def test_last_run_at_not_in_form_fields(self):
        """last_run_at is editable=False — not exposed via AnalyticsReportForm."""
        from apps.crm.forms import AnalyticsReportForm
        assert "last_run_at" not in AnalyticsReportForm.Meta.fields

    def test_is_favorite_default_false(self, report_a):
        assert report_a.is_favorite is False

    def test_unique_together_tenant_number(self, tenant_a):
        from apps.crm.models import AnalyticsReport
        from django.db import IntegrityError
        AnalyticsReport.objects.create(tenant=tenant_a, name="First")
        with pytest.raises(IntegrityError):
            AnalyticsReport.objects.create(tenant=tenant_a, name="Dup", number="RPT-00001")


class TestReportSnapshotModel:
    """ReportSnapshot — summary/data JSON defaults, __str__."""

    def test_summary_default_list(self, tenant_a, report_a):
        from apps.crm.models import ReportSnapshot
        snap = ReportSnapshot.objects.create(
            tenant=tenant_a, report=report_a, title="Empty snapshot")
        assert snap.summary == []
        assert isinstance(snap.summary, list)

    def test_data_default_dict(self, tenant_a, report_a):
        from apps.crm.models import ReportSnapshot
        snap = ReportSnapshot.objects.create(
            tenant=tenant_a, report=report_a, title="Empty snapshot data")
        assert snap.data == {}
        assert isinstance(snap.data, dict)

    def test_str_contains_title_and_datetime(self, snapshot_a):
        s = str(snapshot_a)
        assert "Q1 Activity" in s
        # generated_at shows date portion in the __str__ format
        assert str(snapshot_a.generated_at.year) in s

    def test_snapshot_carries_tenant(self, snapshot_a, tenant_a):
        assert snapshot_a.tenant == tenant_a

    def test_ordering_newest_first(self, tenant_a, report_a):
        from apps.crm.models import ReportSnapshot
        from django.utils import timezone
        now = timezone.now()
        s1 = ReportSnapshot.objects.create(tenant=tenant_a, report=report_a, title="Old")
        s2 = ReportSnapshot.objects.create(tenant=tenant_a, report=report_a, title="New")
        # Force distinct generated_at so ordering is deterministic even on SQLite
        # which may resolve timestamps at the same microsecond in fast CI runs.
        ReportSnapshot.objects.filter(pk=s1.pk).update(
            generated_at=now - datetime.timedelta(seconds=60))
        ReportSnapshot.objects.filter(pk=s2.pk).update(
            generated_at=now)
        snaps = list(ReportSnapshot.objects.filter(report=report_a).values_list("title", flat=True))
        # "New" should come before "Old" (ordering = ["-generated_at"])
        assert snaps.index("New") <= snaps.index("Old")


# ===================================================================== Compute Layer Tests

class TestRangeBounds:
    """range_bounds translates keys into (start, end) — end is always None."""

    def test_all_returns_none_none(self):
        from apps.crm.analytics import range_bounds
        start, end = range_bounds("all")
        assert start is None
        assert end is None

    def test_last_7_returns_approx_7_days(self):
        from apps.crm.analytics import range_bounds
        start, end = range_bounds("last_7")
        assert end is None
        delta = timezone.now() - start
        assert 6 <= delta.days <= 7

    def test_last_30_returns_approx_30_days(self):
        from apps.crm.analytics import range_bounds
        start, end = range_bounds("last_30")
        assert end is None
        delta = timezone.now() - start
        assert 29 <= delta.days <= 30

    def test_last_90_returns_approx_90_days(self):
        from apps.crm.analytics import range_bounds
        start, end = range_bounds("last_90")
        assert end is None
        delta = timezone.now() - start
        assert 89 <= delta.days <= 90

    def test_quarter_start_is_first_of_quarter_month(self):
        from apps.crm.analytics import range_bounds
        start, end = range_bounds("quarter")
        assert end is None
        assert start.month in (1, 4, 7, 10)
        assert start.day == 1

    def test_year_start_is_jan_1(self):
        from apps.crm.analytics import range_bounds
        start, end = range_bounds("year")
        assert end is None
        assert start.month == 1
        assert start.day == 1

    def test_unknown_key_returns_none_none(self):
        from apps.crm.analytics import range_bounds
        start, end = range_bounds("bogus_range")
        assert start is None
        assert end is None


class TestComputeWidget:
    """compute_widget — scalar, series, table, gauge, error cases, division-by-zero."""

    def test_unknown_metric_returns_error_dict(self, tenant_a, dashboard_a):
        from apps.crm.models import DashboardWidget
        from apps.crm.analytics import compute_widget
        w = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a,
            title="Bad", metric="nonexistent_metric", chart_type="kpi",
            date_range="all")
        result = compute_widget(w)
        assert result["kind"] == "scalar"
        assert result["value"] == 0
        assert result["display"] == "—"
        assert "error" in result

    def test_scalar_metric_returns_kind_value_display(self, tenant_a, widget_a):
        from apps.crm.analytics import compute_widget
        result = compute_widget(widget_a)
        assert result["kind"] == "scalar"
        assert "value" in result
        assert "display" in result
        assert isinstance(result["value"], float)

    def test_scalar_metric_returns_max_and_pct(self, tenant_a, widget_a):
        from apps.crm.analytics import compute_widget
        result = compute_widget(widget_a)
        assert "max" in result
        assert "pct" in result
        assert 0 <= result["pct"] <= 100

    def test_series_metric_returns_labels_and_data(self, tenant_a, widget_series):
        from apps.crm.analytics import compute_widget
        result = compute_widget(widget_series)
        assert result["kind"] == "series"
        assert "labels" in result
        assert "data" in result
        assert isinstance(result["labels"], list)
        assert isinstance(result["data"], list)

    def test_table_metric_returns_columns_and_rows(self, tenant_a, widget_table):
        from apps.crm.analytics import compute_widget
        result = compute_widget(widget_table)
        assert result["kind"] == "table"
        assert "columns" in result
        assert "rows" in result
        assert isinstance(result["columns"], list)
        assert isinstance(result["rows"], list)

    def test_gauge_uses_target_value_as_max(self, tenant_a, dashboard_a):
        from apps.crm.models import DashboardWidget
        from apps.crm.analytics import compute_widget
        w = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a,
            title="Gauge Test", metric="kpi_open_pipeline", chart_type="gauge",
            date_range="all", target_value="100000.00")
        result = compute_widget(w)
        assert result["max"] == 100000.0

    def test_win_rate_zero_closed_no_division_error(self, tenant_a, dashboard_a):
        """_r_win_rate with 0 closed opportunities must not raise ZeroDivisionError."""
        from apps.crm.models import DashboardWidget
        from apps.crm.analytics import compute_widget
        # No opportunities created → 0 closed
        w = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a,
            title="Win Rate", metric="kpi_win_rate", chart_type="kpi",
            date_range="all")
        result = compute_widget(w)
        assert result["kind"] == "scalar"
        assert result["value"] == 0.0

    def test_pct_capped_at_100(self, tenant_a, dashboard_a):
        """When value exceeds target, pct must be capped at 100."""
        from apps.crm.models import DashboardWidget, Opportunity
        from apps.core.models import Party
        from apps.crm.analytics import compute_widget
        # Create an opportunity so pipeline value > 0
        account = Party.objects.create(tenant=tenant_a, kind="organization", name="Acme")
        Opportunity.objects.create(
            tenant=tenant_a, name="Big Deal", account=account,
            stage="prospecting", amount="500000.00", probability=50)
        w = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a,
            title="Pipeline", metric="kpi_open_pipeline", chart_type="gauge",
            date_range="all", target_value="1.00")  # tiny target → pct would blow past 100
        result = compute_widget(w)
        assert result["pct"] <= 100

    def test_kpi_open_pipeline_empty_db_returns_zero(self, tenant_a, widget_a):
        """No opportunities → value=0.0, display='$0'."""
        from apps.crm.analytics import compute_widget
        result = compute_widget(widget_a)
        assert result["value"] == 0.0

    def test_series_labels_length_equals_data_length(self, tenant_a, widget_series):
        from apps.crm.analytics import compute_widget
        result = compute_widget(widget_series)
        assert len(result["labels"]) == len(result["data"])

    def test_intrinsic_max_for_win_rate(self, tenant_a, dashboard_a):
        """_r_win_rate has intrinsic_max=100; empty DB → max should be 100."""
        from apps.crm.models import DashboardWidget
        from apps.crm.analytics import compute_widget
        w = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a,
            title="WR", metric="kpi_win_rate", chart_type="kpi", date_range="all")
        result = compute_widget(w)
        assert result["max"] == 100


class TestComputeReport:
    """compute_report — all 4 types return expected shape and are JSON-serializable."""

    REQUIRED_KEYS = {"summary", "columns", "rows", "chart_type", "chart_label",
                     "chart_labels", "chart_data"}

    def _make_report(self, tenant, report_type, group_by="month"):
        from apps.crm.models import AnalyticsReport
        return AnalyticsReport.objects.create(
            tenant=tenant, name=f"Test {report_type}",
            report_type=report_type, date_range="all", group_by=group_by)

    def test_sales_activity_shape(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "sales_activity", group_by="month")
        result = compute_report(r)
        assert self.REQUIRED_KEYS.issubset(result.keys())
        assert isinstance(result["summary"], list)
        assert isinstance(result["rows"], list)

    def test_sales_activity_json_serializable(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "sales_activity", group_by="month")
        result = compute_report(r)
        # Must not raise
        serialized = json.dumps(result)
        restored = json.loads(serialized)
        assert restored["chart_type"] == "line"

    def test_sales_performance_shape(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "sales_performance", group_by="owner")
        result = compute_report(r)
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_sales_performance_json_serializable(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "sales_performance", group_by="owner")
        result = compute_report(r)
        serialized = json.dumps(result)
        restored = json.loads(serialized)
        assert restored["chart_type"] == "bar"

    def test_funnel_shape(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "funnel", group_by="stage")
        result = compute_report(r)
        assert self.REQUIRED_KEYS.issubset(result.keys())
        # Funnel has 5 stages (prospecting → closed_won)
        assert len(result["rows"]) == 5

    def test_funnel_json_serializable(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "funnel", group_by="stage")
        result = compute_report(r)
        json.dumps(result)  # must not raise

    def test_funnel_zero_entered_no_division_error(self, tenant_a):
        """Funnel with 0 opportunities must not raise ZeroDivisionError."""
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "funnel", group_by="stage")
        result = compute_report(r)
        # Win Conversion summary entry should be "0%" not an error
        conv = next((s["value"] for s in result["summary"] if "Conversion" in s["label"]), None)
        assert conv == "0%"

    def test_service_shape(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "service", group_by="priority")
        result = compute_report(r)
        assert self.REQUIRED_KEYS.issubset(result.keys())

    def test_service_json_serializable(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "service", group_by="priority")
        result = compute_report(r)
        json.dumps(result)  # must not raise

    def test_service_with_no_cases_returns_zero_total(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "service", group_by="priority")
        result = compute_report(r)
        total_entry = next((s["value"] for s in result["summary"] if s["label"] == "Total Cases"), None)
        assert total_entry == "0"

    def test_unknown_report_type_returns_empty_shape(self, tenant_a):
        from apps.crm.analytics import compute_report
        from apps.crm.models import AnalyticsReport
        r = AnalyticsReport.objects.create(
            tenant=tenant_a, name="Unknown", report_type="sales_activity")
        # monkeypatch the type directly without form validation
        r.report_type = "nonexistent"
        result = compute_report(r)
        assert result["summary"] == []
        assert result["columns"] == []
        assert result["rows"] == []

    def test_sales_activity_summary_has_three_items(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "sales_activity")
        result = compute_report(r)
        assert len(result["summary"]) == 3

    def test_funnel_summary_has_three_items(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "funnel", group_by="stage")
        result = compute_report(r)
        assert len(result["summary"]) == 3  # Entered, Won, Win Conversion

    def test_service_summary_has_four_items(self, tenant_a):
        from apps.crm.analytics import compute_report
        r = self._make_report(tenant_a, "service", group_by="priority")
        result = compute_report(r)
        assert len(result["summary"]) == 4  # Total, Resolved%, Avg Resolution, Avg CSAT

    def test_funnel_with_data_does_not_crash(self, tenant_a):
        """Create an opportunity in every stage and verify funnel rows sum correctly."""
        from apps.core.models import Party
        from apps.crm.models import Opportunity
        from apps.crm.analytics import compute_report
        account = Party.objects.create(tenant=tenant_a, kind="organization", name="Funnel Co")
        for stage in ("prospecting", "qualification", "proposal", "negotiation", "closed_won"):
            Opportunity.objects.create(
                tenant=tenant_a, name=f"Deal {stage}", account=account,
                stage=stage, amount="1000.00", probability=50)
        r = self._make_report(tenant_a, "funnel", group_by="stage")
        result = compute_report(r)
        assert len(result["rows"]) == 5
        # Prospecting row should have count >= other rows (cumulative)
        prospecting_count = result["rows"][0][1]
        won_count = result["rows"][-1][1]
        assert prospecting_count >= won_count


# ===================================================================== Form Tests

class TestDashboardWidgetFormClean:
    """DashboardWidgetForm.clean() rejects chart_type incompatible with metric."""

    def _make_form(self, metric, chart_type, tenant):
        from apps.crm.forms import DashboardWidgetForm
        data = {
            "title": "Test Widget",
            "metric": metric,
            "chart_type": chart_type,
            "date_range": "all",
            "size": "medium",
            "target_value": "",
        }
        return DashboardWidgetForm(data, tenant=tenant)

    def test_scalar_metric_with_table_chart_is_invalid(self, tenant_a):
        form = self._make_form("kpi_open_pipeline", "table", tenant_a)
        assert not form.is_valid()
        assert "chart_type" in form.errors

    def test_scalar_metric_with_kpi_chart_is_valid(self, tenant_a):
        form = self._make_form("kpi_open_pipeline", "kpi", tenant_a)
        assert form.is_valid(), form.errors

    def test_scalar_metric_with_gauge_chart_is_valid(self, tenant_a):
        form = self._make_form("kpi_open_pipeline", "gauge", tenant_a)
        assert form.is_valid(), form.errors

    def test_series_metric_with_bar_chart_is_valid(self, tenant_a):
        form = self._make_form("pipeline_by_stage", "bar", tenant_a)
        assert form.is_valid(), form.errors

    def test_series_metric_with_kpi_chart_is_invalid(self, tenant_a):
        form = self._make_form("pipeline_by_stage", "kpi", tenant_a)
        assert not form.is_valid()
        assert "chart_type" in form.errors

    def test_table_metric_with_table_chart_is_valid(self, tenant_a):
        form = self._make_form("top_performers", "table", tenant_a)
        assert form.is_valid(), form.errors

    def test_table_metric_with_bar_chart_is_invalid(self, tenant_a):
        form = self._make_form("top_performers", "bar", tenant_a)
        assert not form.is_valid()
        assert "chart_type" in form.errors

    def test_error_message_lists_allowed_charts(self, tenant_a):
        form = self._make_form("kpi_open_pipeline", "table", tenant_a)
        form.is_valid()
        err = str(form.errors["chart_type"])
        # Should mention the valid types
        assert "kpi" in err or "gauge" in err


class TestAnalyticsReportFormClean:
    """AnalyticsReportForm.clean() enforces valid group_by per report_type."""

    def _make_form(self, report_type, group_by, tenant, name="My Report"):
        from apps.crm.forms import AnalyticsReportForm
        data = {
            "name": name,
            "description": "",
            "report_type": report_type,
            "date_range": "all",
            "group_by": group_by,
            "is_favorite": False,
        }
        return AnalyticsReportForm(data, tenant=tenant)

    def test_service_rejects_owner_groupby(self, tenant_a):
        form = self._make_form("service", "owner", tenant_a)
        assert not form.is_valid()
        assert "group_by" in form.errors

    def test_service_accepts_priority_groupby(self, tenant_a):
        form = self._make_form("service", "priority", tenant_a)
        assert form.is_valid(), form.errors

    def test_service_accepts_month_groupby(self, tenant_a):
        form = self._make_form("service", "month", tenant_a)
        assert form.is_valid(), form.errors

    def test_service_accepts_week_groupby(self, tenant_a):
        form = self._make_form("service", "week", tenant_a)
        assert form.is_valid(), form.errors

    def test_sales_activity_rejects_stage_groupby(self, tenant_a):
        form = self._make_form("sales_activity", "stage", tenant_a)
        assert not form.is_valid()
        assert "group_by" in form.errors

    def test_sales_activity_accepts_month_groupby(self, tenant_a):
        form = self._make_form("sales_activity", "month", tenant_a)
        assert form.is_valid(), form.errors

    def test_funnel_accepts_stage_groupby(self, tenant_a):
        form = self._make_form("funnel", "stage", tenant_a)
        assert form.is_valid(), form.errors

    def test_funnel_rejects_owner_groupby(self, tenant_a):
        form = self._make_form("funnel", "owner", tenant_a)
        assert not form.is_valid()
        assert "group_by" in form.errors

    def test_sales_performance_accepts_owner_groupby(self, tenant_a):
        form = self._make_form("sales_performance", "owner", tenant_a)
        assert form.is_valid(), form.errors

    def test_sales_performance_rejects_month_groupby(self, tenant_a):
        form = self._make_form("sales_performance", "month", tenant_a)
        assert not form.is_valid()
        assert "group_by" in form.errors

    def test_error_message_includes_allowed_groupings(self, tenant_a):
        form = self._make_form("service", "owner", tenant_a)
        form.is_valid()
        err = str(form.errors["group_by"])
        # Should list month, week, or priority in the error
        assert any(kw in err for kw in ("Month", "Week", "Priority", "month", "week", "priority"))


class TestAnalyticsDashboardFormCanShare:
    """AnalyticsDashboardForm(can_share=False) drops is_shared and is_default fields."""

    def test_can_share_true_includes_is_shared(self, tenant_a):
        from apps.crm.forms import AnalyticsDashboardForm
        form = AnalyticsDashboardForm(tenant=tenant_a, can_share=True)
        assert "is_shared" in form.fields

    def test_can_share_true_includes_is_default(self, tenant_a):
        from apps.crm.forms import AnalyticsDashboardForm
        form = AnalyticsDashboardForm(tenant=tenant_a, can_share=True)
        assert "is_default" in form.fields

    def test_can_share_false_drops_is_shared(self, tenant_a):
        from apps.crm.forms import AnalyticsDashboardForm
        form = AnalyticsDashboardForm(tenant=tenant_a, can_share=False)
        assert "is_shared" not in form.fields

    def test_can_share_false_drops_is_default(self, tenant_a):
        from apps.crm.forms import AnalyticsDashboardForm
        form = AnalyticsDashboardForm(tenant=tenant_a, can_share=False)
        assert "is_default" not in form.fields

    def test_can_share_default_is_true(self, tenant_a):
        """Default (can_share not passed) should behave as can_share=True."""
        from apps.crm.forms import AnalyticsDashboardForm
        form = AnalyticsDashboardForm(tenant=tenant_a)
        assert "is_shared" in form.fields


# ===================================================================== View Tests

class TestDashboardListView:
    def test_anonymous_redirects_to_login(self, client):
        url = reverse("crm:dashboard_list")
        response = client.get(url)
        assert response.status_code == 302
        assert "/auth/login/" in response["Location"] or "login" in response["Location"]

    def test_returns_200_for_authenticated(self, client_a):
        url = reverse("crm:dashboard_list")
        response = client_a.get(url)
        assert response.status_code == 200

    def test_shows_own_tenant_dashboards(self, client_a, dashboard_a):
        url = reverse("crm:dashboard_list")
        response = client_a.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert "Sales Overview" in content

    def test_does_not_show_other_tenant_dashboards(self, client_a, dashboard_b):
        url = reverse("crm:dashboard_list")
        response = client_a.get(url)
        content = response.content.decode()
        assert "Globex Dashboard" not in content

    def test_search_filter_works(self, client_a, dashboard_a):
        url = reverse("crm:dashboard_list") + "?q=Sales"
        response = client_a.get(url)
        assert response.status_code == 200
        assert "Sales Overview" in response.content.decode()

    def test_search_filter_excludes_non_matching(self, client_a, dashboard_a):
        url = reverse("crm:dashboard_list") + "?q=zzznomatch"
        response = client_a.get(url)
        assert response.status_code == 200
        assert "Sales Overview" not in response.content.decode()


class TestDashboardCreateView:
    def test_get_returns_200(self, client_a):
        url = reverse("crm:dashboard_create")
        response = client_a.get(url)
        assert response.status_code == 200

    def test_post_creates_dashboard(self, client_a, tenant_a):
        from apps.crm.models import AnalyticsDashboard
        url = reverse("crm:dashboard_create")
        data = {
            "name": "New Dashboard",
            "description": "Test description",
            "layout": "two",
            "is_shared": False,
            "is_default": False,
        }
        response = client_a.post(url, data)
        assert AnalyticsDashboard.objects.filter(tenant=tenant_a, name="New Dashboard").exists()

    def test_post_redirects_to_detail(self, client_a, tenant_a):
        from apps.crm.models import AnalyticsDashboard
        url = reverse("crm:dashboard_create")
        data = {"name": "Redirect Test", "layout": "one"}
        response = client_a.post(url, data)
        obj = AnalyticsDashboard.objects.filter(tenant=tenant_a, name="Redirect Test").first()
        assert obj is not None
        assert response.status_code == 302
        assert str(obj.pk) in response["Location"]

    def test_dashboard_assigned_to_request_tenant(self, client_a, tenant_a):
        from apps.crm.models import AnalyticsDashboard
        url = reverse("crm:dashboard_create")
        data = {"name": "Tenant Check", "layout": "two"}
        client_a.post(url, data)
        obj = AnalyticsDashboard.objects.filter(name="Tenant Check").first()
        assert obj is not None
        assert obj.tenant == tenant_a


class TestDashboardDetailView:
    def test_returns_200(self, client_a, dashboard_a):
        url = reverse("crm:dashboard_detail", args=[dashboard_a.pk])
        response = client_a.get(url)
        assert response.status_code == 200

    def test_renders_widgets(self, client_a, dashboard_a, widget_a):
        url = reverse("crm:dashboard_detail", args=[dashboard_a.pk])
        response = client_a.get(url)
        assert response.status_code == 200
        assert "Open Pipeline" in response.content.decode()

    def test_cross_tenant_returns_404(self, client_a, dashboard_b):
        url = reverse("crm:dashboard_detail", args=[dashboard_b.pk])
        response = client_a.get(url)
        assert response.status_code == 404


class TestDashboardEditView:
    def test_get_returns_200(self, client_a, dashboard_a):
        url = reverse("crm:dashboard_edit", args=[dashboard_a.pk])
        response = client_a.get(url)
        assert response.status_code == 200

    def test_post_updates_dashboard(self, client_a, dashboard_a):
        url = reverse("crm:dashboard_edit", args=[dashboard_a.pk])
        data = {"name": "Updated Dashboard", "layout": "three"}
        client_a.post(url, data)
        dashboard_a.refresh_from_db()
        assert dashboard_a.name == "Updated Dashboard"

    def test_cross_tenant_returns_404(self, client_a, dashboard_b):
        url = reverse("crm:dashboard_edit", args=[dashboard_b.pk])
        response = client_a.get(url)
        assert response.status_code == 404


class TestDashboardDeleteView:
    def test_post_deletes_dashboard(self, client_a, dashboard_a):
        from apps.crm.models import AnalyticsDashboard
        pk = dashboard_a.pk
        url = reverse("crm:dashboard_delete", args=[pk])
        client_a.post(url)
        assert not AnalyticsDashboard.objects.filter(pk=pk).exists()

    def test_post_redirects_to_list(self, client_a, dashboard_a):
        url = reverse("crm:dashboard_delete", args=[dashboard_a.pk])
        response = client_a.post(url)
        assert response.status_code == 302

    def test_get_does_not_delete(self, client_a, dashboard_a):
        from apps.crm.models import AnalyticsDashboard
        pk = dashboard_a.pk
        url = reverse("crm:dashboard_delete", args=[pk])
        client_a.get(url)  # GET should not delete
        # NOTE: crud_delete is @require_POST so GET redirects or 405
        # The important thing is the object still exists after a GET
        assert AnalyticsDashboard.objects.filter(pk=pk).exists()

    def test_cross_tenant_returns_404(self, client_a, dashboard_b):
        url = reverse("crm:dashboard_delete", args=[dashboard_b.pk])
        response = client_a.post(url)
        assert response.status_code == 404


class TestWidgetCRUDViews:
    def test_widget_create_get_200(self, client_a, dashboard_a):
        url = reverse("crm:widget_create", args=[dashboard_a.pk])
        response = client_a.get(url)
        assert response.status_code == 200

    def test_widget_create_post_creates_widget(self, client_a, tenant_a, dashboard_a):
        from apps.crm.models import DashboardWidget
        url = reverse("crm:widget_create", args=[dashboard_a.pk])
        data = {
            "title": "My KPI Widget",
            "metric": "kpi_new_leads",
            "chart_type": "kpi",
            "date_range": "last_30",
            "size": "medium",
            "target_value": "",
        }
        client_a.post(url, data)
        assert DashboardWidget.objects.filter(
            tenant=tenant_a, dashboard=dashboard_a, title="My KPI Widget").exists()

    def test_widget_create_cross_tenant_dashboard_404(self, client_a, dashboard_b):
        url = reverse("crm:widget_create", args=[dashboard_b.pk])
        response = client_a.get(url)
        assert response.status_code == 404

    def test_widget_edit_get_200(self, client_a, widget_a):
        url = reverse("crm:widget_edit", args=[widget_a.pk])
        response = client_a.get(url)
        assert response.status_code == 200

    def test_widget_edit_post_updates_title(self, client_a, widget_a):
        url = reverse("crm:widget_edit", args=[widget_a.pk])
        data = {
            "title": "Updated Widget",
            "metric": "kpi_open_pipeline",
            "chart_type": "kpi",
            "date_range": "all",
            "size": "medium",
            "target_value": "",
        }
        client_a.post(url, data)
        widget_a.refresh_from_db()
        assert widget_a.title == "Updated Widget"

    def test_widget_edit_cross_tenant_404(self, client_a, widget_b):
        url = reverse("crm:widget_edit", args=[widget_b.pk])
        response = client_a.get(url)
        assert response.status_code == 404

    def test_widget_delete_removes_widget(self, client_a, widget_a):
        from apps.crm.models import DashboardWidget
        pk = widget_a.pk
        url = reverse("crm:widget_delete", args=[pk])
        client_a.post(url)
        assert not DashboardWidget.objects.filter(pk=pk).exists()

    def test_widget_delete_cross_tenant_404(self, client_a, widget_b):
        url = reverse("crm:widget_delete", args=[widget_b.pk])
        response = client_a.post(url)
        assert response.status_code == 404


class TestWidgetMoveView:
    """widget_move POST reorders widgets via bulk_update."""

    def test_move_down_swaps_positions(self, client_a, tenant_a, dashboard_a):
        from apps.crm.models import DashboardWidget
        w1 = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a, title="First",
            metric="kpi_new_leads", chart_type="kpi", date_range="all", position=0)
        w2 = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a, title="Second",
            metric="kpi_open_cases", chart_type="kpi", date_range="all", position=1)
        url = reverse("crm:widget_move", args=[w1.pk, "down"])
        client_a.post(url)
        w1.refresh_from_db()
        w2.refresh_from_db()
        assert w1.position > w2.position

    def test_move_up_swaps_positions(self, client_a, tenant_a, dashboard_a):
        from apps.crm.models import DashboardWidget
        w1 = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a, title="First2",
            metric="kpi_new_leads", chart_type="kpi", date_range="all", position=0)
        w2 = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a, title="Second2",
            metric="kpi_open_cases", chart_type="kpi", date_range="all", position=1)
        url = reverse("crm:widget_move", args=[w2.pk, "up"])
        client_a.post(url)
        w1.refresh_from_db()
        w2.refresh_from_db()
        assert w2.position < w1.position

    def test_move_first_widget_up_is_noop(self, client_a, tenant_a, dashboard_a):
        from apps.crm.models import DashboardWidget
        w1 = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a, title="First3",
            metric="kpi_new_leads", chart_type="kpi", date_range="all", position=0)
        original_position = w1.position
        url = reverse("crm:widget_move", args=[w1.pk, "up"])
        client_a.post(url)
        w1.refresh_from_db()
        assert w1.position == original_position

    def test_move_redirects_to_dashboard_detail(self, client_a, tenant_a, dashboard_a):
        from apps.crm.models import DashboardWidget
        w1 = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a, title="MoveTo",
            metric="kpi_new_leads", chart_type="kpi", date_range="all", position=0)
        w2 = DashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard_a, title="MoveFrom",
            metric="kpi_open_cases", chart_type="kpi", date_range="all", position=1)
        url = reverse("crm:widget_move", args=[w1.pk, "down"])
        response = client_a.post(url)
        assert response.status_code == 302
        assert str(dashboard_a.pk) in response["Location"]

    def test_widget_move_cross_tenant_404(self, client_a, widget_b):
        url = reverse("crm:widget_move", args=[widget_b.pk, "down"])
        response = client_a.post(url)
        assert response.status_code == 404


class TestReportListView:
    def test_anonymous_redirects_to_login(self, client):
        url = reverse("crm:report_list")
        response = client.get(url)
        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_returns_200(self, client_a):
        url = reverse("crm:report_list")
        response = client_a.get(url)
        assert response.status_code == 200

    def test_shows_own_tenant_reports(self, client_a, report_a):
        url = reverse("crm:report_list")
        response = client_a.get(url)
        assert "Q1 Activity" in response.content.decode()

    def test_does_not_show_other_tenant_reports(self, client_a, report_b):
        url = reverse("crm:report_list")
        response = client_a.get(url)
        assert "Globex Report" not in response.content.decode()

    def test_search_works(self, client_a, report_a):
        url = reverse("crm:report_list") + "?q=Q1"
        response = client_a.get(url)
        assert "Q1 Activity" in response.content.decode()


class TestReportCreateView:
    def test_get_returns_200(self, client_a):
        url = reverse("crm:report_create")
        response = client_a.get(url)
        assert response.status_code == 200

    def test_post_creates_report(self, client_a, tenant_a):
        from apps.crm.models import AnalyticsReport
        url = reverse("crm:report_create")
        data = {
            "name": "New Report",
            "description": "",
            "report_type": "funnel",
            "date_range": "last_90",
            "group_by": "stage",
            "is_favorite": False,
        }
        client_a.post(url, data)
        assert AnalyticsReport.objects.filter(tenant=tenant_a, name="New Report").exists()

    def test_report_assigned_to_request_tenant(self, client_a, tenant_a):
        from apps.crm.models import AnalyticsReport
        url = reverse("crm:report_create")
        data = {
            "name": "Tenant Check Report",
            "report_type": "sales_activity",
            "date_range": "all",
            "group_by": "month",
        }
        client_a.post(url, data)
        obj = AnalyticsReport.objects.filter(name="Tenant Check Report").first()
        assert obj is not None
        assert obj.tenant == tenant_a


class TestReportDetailView:
    def test_returns_200_and_stamps_last_run_at(self, client_a, report_a):
        url = reverse("crm:report_detail", args=[report_a.pk])
        response = client_a.get(url)
        assert response.status_code == 200
        report_a.refresh_from_db()
        assert report_a.last_run_at is not None

    def test_cross_tenant_returns_404(self, client_a, report_b):
        url = reverse("crm:report_detail", args=[report_b.pk])
        response = client_a.get(url)
        assert response.status_code == 404

    def test_renders_result_context(self, client_a, report_a):
        url = reverse("crm:report_detail", args=[report_a.pk])
        response = client_a.get(url)
        assert "result" in response.context


class TestReportEditView:
    def test_get_returns_200(self, client_a, report_a):
        url = reverse("crm:report_edit", args=[report_a.pk])
        response = client_a.get(url)
        assert response.status_code == 200

    def test_post_updates_report(self, client_a, report_a):
        url = reverse("crm:report_edit", args=[report_a.pk])
        data = {
            "name": "Updated Report",
            "description": "",
            "report_type": "sales_activity",
            "date_range": "last_30",
            "group_by": "week",
            "is_favorite": False,
        }
        client_a.post(url, data)
        report_a.refresh_from_db()
        assert report_a.name == "Updated Report"

    def test_cross_tenant_returns_404(self, client_a, report_b):
        url = reverse("crm:report_edit", args=[report_b.pk])
        response = client_a.get(url)
        assert response.status_code == 404


class TestReportDeleteView:
    def test_post_deletes_report(self, client_a, report_a):
        from apps.crm.models import AnalyticsReport
        pk = report_a.pk
        url = reverse("crm:report_delete", args=[pk])
        client_a.post(url)
        assert not AnalyticsReport.objects.filter(pk=pk).exists()

    def test_cross_tenant_returns_404(self, client_a, report_b):
        url = reverse("crm:report_delete", args=[report_b.pk])
        response = client_a.post(url)
        assert response.status_code == 404


class TestReportFavoriteView:
    def test_favorite_toggles_on(self, client_a, report_a):
        assert report_a.is_favorite is False
        url = reverse("crm:report_favorite", args=[report_a.pk])
        client_a.post(url)
        report_a.refresh_from_db()
        assert report_a.is_favorite is True

    def test_favorite_toggles_off(self, client_a, report_a):
        report_a.is_favorite = True
        report_a.save(update_fields=["is_favorite", "updated_at"])
        url = reverse("crm:report_favorite", args=[report_a.pk])
        client_a.post(url)
        report_a.refresh_from_db()
        assert report_a.is_favorite is False

    def test_favorite_redirects_to_report_detail(self, client_a, report_a):
        url = reverse("crm:report_favorite", args=[report_a.pk])
        response = client_a.post(url)
        assert response.status_code == 302
        assert str(report_a.pk) in response["Location"]

    def test_cross_tenant_returns_404(self, client_a, report_b):
        url = reverse("crm:report_favorite", args=[report_b.pk])
        response = client_a.post(url)
        assert response.status_code == 404


class TestReportSnapshotView:
    """report_snapshot POST creates a ReportSnapshot atomically and redirects."""

    def test_post_creates_snapshot(self, client_a, tenant_a, report_a):
        from apps.crm.models import ReportSnapshot
        url = reverse("crm:report_snapshot", args=[report_a.pk])
        response = client_a.post(url)
        assert ReportSnapshot.objects.filter(tenant=tenant_a, report=report_a).exists()

    def test_post_redirects_to_snapshot_detail(self, client_a, report_a):
        from apps.crm.models import ReportSnapshot
        url = reverse("crm:report_snapshot", args=[report_a.pk])
        response = client_a.post(url)
        assert response.status_code == 302
        snap = ReportSnapshot.objects.filter(report=report_a).first()
        assert snap is not None
        assert str(snap.pk) in response["Location"]

    def test_snapshot_stores_summary_list(self, client_a, tenant_a, report_a):
        from apps.crm.models import ReportSnapshot
        url = reverse("crm:report_snapshot", args=[report_a.pk])
        client_a.post(url)
        snap = ReportSnapshot.objects.filter(report=report_a).first()
        assert isinstance(snap.summary, list)

    def test_snapshot_stores_data_dict(self, client_a, tenant_a, report_a):
        from apps.crm.models import ReportSnapshot
        url = reverse("crm:report_snapshot", args=[report_a.pk])
        client_a.post(url)
        snap = ReportSnapshot.objects.filter(report=report_a).first()
        assert isinstance(snap.data, dict)
        assert "columns" in snap.data

    def test_snapshot_stamps_last_run_at_on_report(self, client_a, report_a):
        url = reverse("crm:report_snapshot", args=[report_a.pk])
        client_a.post(url)
        report_a.refresh_from_db()
        assert report_a.last_run_at is not None

    def test_snapshot_generated_by_is_request_user(self, client_a, report_a, admin_user):
        from apps.crm.models import ReportSnapshot
        url = reverse("crm:report_snapshot", args=[report_a.pk])
        client_a.post(url)
        snap = ReportSnapshot.objects.filter(report=report_a).first()
        assert snap.generated_by == admin_user

    def test_cross_tenant_returns_404(self, client_a, report_b):
        url = reverse("crm:report_snapshot", args=[report_b.pk])
        response = client_a.post(url)
        assert response.status_code == 404

    def test_snapshot_title_contains_report_name(self, client_a, report_a):
        from apps.crm.models import ReportSnapshot
        url = reverse("crm:report_snapshot", args=[report_a.pk])
        client_a.post(url)
        snap = ReportSnapshot.objects.filter(report=report_a).first()
        assert "Q1 Activity" in snap.title


class TestSnapshotDetailView:
    def test_returns_200(self, client_a, snapshot_a):
        url = reverse("crm:snapshot_detail", args=[snapshot_a.pk])
        response = client_a.get(url)
        assert response.status_code == 200

    def test_cross_tenant_returns_404(self, client_a, snapshot_b):
        url = reverse("crm:snapshot_detail", args=[snapshot_b.pk])
        response = client_a.get(url)
        assert response.status_code == 404

    def test_context_has_obj(self, client_a, snapshot_a):
        url = reverse("crm:snapshot_detail", args=[snapshot_a.pk])
        response = client_a.get(url)
        assert "obj" in response.context
        assert response.context["obj"] == snapshot_a


class TestSnapshotDeleteView:
    def test_post_deletes_snapshot(self, client_a, snapshot_a):
        from apps.crm.models import ReportSnapshot
        pk = snapshot_a.pk
        url = reverse("crm:snapshot_delete", args=[pk])
        client_a.post(url)
        assert not ReportSnapshot.objects.filter(pk=pk).exists()

    def test_post_redirects_to_report_detail(self, client_a, snapshot_a, report_a):
        url = reverse("crm:snapshot_delete", args=[snapshot_a.pk])
        response = client_a.post(url)
        assert response.status_code == 302
        assert str(report_a.pk) in response["Location"]

    def test_cross_tenant_returns_404(self, client_a, snapshot_b):
        url = reverse("crm:snapshot_delete", args=[snapshot_b.pk])
        response = client_a.post(url)
        assert response.status_code == 404


# ===================================================================== Security Tests

class TestMultiTenantIsolation:
    """Cross-tenant IDOR: tenant-A user requesting tenant-B pk must get 404."""

    def test_dashboard_detail_idor(self, client_a, dashboard_b):
        url = reverse("crm:dashboard_detail", args=[dashboard_b.pk])
        assert client_a.get(url).status_code == 404

    def test_dashboard_edit_idor(self, client_a, dashboard_b):
        url = reverse("crm:dashboard_edit", args=[dashboard_b.pk])
        assert client_a.get(url).status_code == 404

    def test_dashboard_delete_idor(self, client_a, dashboard_b):
        url = reverse("crm:dashboard_delete", args=[dashboard_b.pk])
        assert client_a.post(url).status_code == 404

    def test_widget_create_idor(self, client_a, dashboard_b):
        url = reverse("crm:widget_create", args=[dashboard_b.pk])
        assert client_a.get(url).status_code == 404

    def test_widget_edit_idor(self, client_a, widget_b):
        url = reverse("crm:widget_edit", args=[widget_b.pk])
        assert client_a.get(url).status_code == 404

    def test_widget_delete_idor(self, client_a, widget_b):
        url = reverse("crm:widget_delete", args=[widget_b.pk])
        assert client_a.post(url).status_code == 404

    def test_widget_move_idor(self, client_a, widget_b):
        url = reverse("crm:widget_move", args=[widget_b.pk, "down"])
        assert client_a.post(url).status_code == 404

    def test_report_detail_idor(self, client_a, report_b):
        url = reverse("crm:report_detail", args=[report_b.pk])
        assert client_a.get(url).status_code == 404

    def test_report_edit_idor(self, client_a, report_b):
        url = reverse("crm:report_edit", args=[report_b.pk])
        assert client_a.get(url).status_code == 404

    def test_report_delete_idor(self, client_a, report_b):
        url = reverse("crm:report_delete", args=[report_b.pk])
        assert client_a.post(url).status_code == 404

    def test_report_favorite_idor(self, client_a, report_b):
        url = reverse("crm:report_favorite", args=[report_b.pk])
        assert client_a.post(url).status_code == 404

    def test_report_snapshot_idor(self, client_a, report_b):
        url = reverse("crm:report_snapshot", args=[report_b.pk])
        assert client_a.post(url).status_code == 404

    def test_snapshot_detail_idor(self, client_a, snapshot_b):
        url = reverse("crm:snapshot_detail", args=[snapshot_b.pk])
        assert client_a.get(url).status_code == 404

    def test_snapshot_delete_idor(self, client_a, snapshot_b):
        url = reverse("crm:snapshot_delete", args=[snapshot_b.pk])
        assert client_a.post(url).status_code == 404


class TestAnonymousAccess:
    """All analytics views redirect unauthenticated requests to login."""

    def _assert_redirects_to_login(self, client, url):
        response = client.get(url)
        assert response.status_code == 302
        assert "login" in response["Location"]

    def test_dashboard_list_anonymous(self, client):
        self._assert_redirects_to_login(client, reverse("crm:dashboard_list"))

    def test_dashboard_create_anonymous(self, client):
        self._assert_redirects_to_login(client, reverse("crm:dashboard_create"))

    def test_report_list_anonymous(self, client):
        self._assert_redirects_to_login(client, reverse("crm:report_list"))

    def test_report_create_anonymous(self, client):
        self._assert_redirects_to_login(client, reverse("crm:report_create"))


class TestNonAdminCannotShareDashboard:
    """A non-admin member POSTing dashboard_create with is_shared=True must NOT set the flag."""

    def test_member_cannot_set_is_shared(self, member_client, tenant_a):
        from apps.crm.models import AnalyticsDashboard
        url = reverse("crm:dashboard_create")
        data = {
            "name": "Private Member Board",
            "layout": "two",
            "is_shared": True,   # attempted privilege escalation
            "is_default": True,
        }
        member_client.post(url, data)
        obj = AnalyticsDashboard.objects.filter(tenant=tenant_a, name="Private Member Board").first()
        assert obj is not None
        # is_shared must be False because the form drops it for non-admins
        assert obj.is_shared is False

    def test_member_cannot_set_is_default(self, member_client, tenant_a):
        from apps.crm.models import AnalyticsDashboard
        url = reverse("crm:dashboard_create")
        data = {
            "name": "Member Default Board",
            "layout": "one",
            "is_shared": True,
            "is_default": True,
        }
        member_client.post(url, data)
        obj = AnalyticsDashboard.objects.filter(tenant=tenant_a, name="Member Default Board").first()
        assert obj is not None
        assert obj.is_default is False

    def test_admin_can_set_is_shared(self, client_a, tenant_a):
        from apps.crm.models import AnalyticsDashboard
        url = reverse("crm:dashboard_create")
        data = {
            "name": "Shared Admin Board",
            "layout": "two",
            "is_shared": True,
            "is_default": False,
        }
        client_a.post(url, data)
        obj = AnalyticsDashboard.objects.filter(tenant=tenant_a, name="Shared Admin Board").first()
        assert obj is not None
        assert obj.is_shared is True


class TestQueryCountGuardrails:
    """Ensure widget_move uses bulk_update (single statement) and funnel runs in <=2 queries."""

    def test_funnel_report_limited_queries(self, django_assert_num_queries, tenant_a):
        """_compute_funnel should use a single grouped query on Opportunity."""
        from apps.crm.analytics import _compute_funnel
        from apps.crm.models import AnalyticsReport
        r = AnalyticsReport.objects.create(
            tenant=tenant_a, name="Funnel QC", report_type="funnel",
            date_range="all", group_by="stage")
        # Allow up to 2 queries (Django may add a savepoint or similar)
        with django_assert_num_queries(1):
            _compute_funnel(r, tenant_a, None, None)

    def test_widget_move_uses_bulk_update(self, client_a, tenant_a, dashboard_a):
        """widget_move should use bulk_update — the position UPDATE count must not grow with N widgets."""
        from apps.crm.models import DashboardWidget
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        # Create 8 widgets (larger N to make the N+1 pattern obvious if present)
        widgets = []
        for i in range(8):
            w = DashboardWidget.objects.create(
                tenant=tenant_a, dashboard=dashboard_a,
                title=f"BulkW{i}", metric="kpi_new_leads",
                chart_type="kpi", date_range="all", position=i)
            widgets.append(w)

        # Move the last widget up — if bulk_update is used, there is exactly 1 UPDATE for positions.
        url = reverse("crm:widget_move", args=[widgets[-1].pk, "up"])
        with CaptureQueriesContext(connection) as ctx:
            client_a.post(url)

        update_sqls = [q["sql"] for q in ctx.captured_queries
                       if q["sql"].upper().startswith("UPDATE") and "crm_dashboardwidget" in q["sql"].lower()]
        # bulk_update emits a single UPDATE per changed field via CASE WHEN.
        # With N=8, a naive loop would issue up to 7 individual UPDATEs.
        # We assert at most 2 UPDATEs (one for position via bulk_update, possibly one for audit).
        assert len(update_sqls) <= 2, (
            f"Expected at most 2 UPDATE statements (bulk_update), got {len(update_sqls)}: "
            f"{update_sqls}"
        )
