"""Tests for HRM 3.32 Analytics Dashboard sub-module.

Mirrors ``test_payroll_reports.py`` (3.31) / ``test_leave_reports.py`` (3.30) — same fixture
style, access-control + aggregate-correctness + IDOR + div-by-zero + query-count structure —
plus model/form/compute-layer unit tests for the 2 models (``HRDashboard``/``HRDashboardWidget``)
and the ``apps/hrm/analytics.py`` compute layer that don't exist in the pure-report sub-modules.

Covers:
  - Models: ``HRDashboard``/``HRDashboardWidget`` defaults, auto-number (``HRD-#####``),
    ``__str__``, ``widget_count`` property.
  - Forms: ``HRDashboardForm`` drops ``is_shared``/``is_default`` for a non-admin (``can_share``);
    ``owner``/``tenant``/``number`` are never form fields. ``HRDashboardWidgetForm.clean()``
    rejects a metric x chart_type mismatch.
  - ``apps/hrm/analytics.py`` compute layer: ``compute_widget`` scalar/series/table shapes, the
    unknown-metric error path, the target_value <= 0 div-by-zero guard, ``allowed_charts``,
    the ``WIDGET_METRICS``/``WIDGET_METRIC_CHOICES`` sync assert, and ``_attrition_risk_scores``
    (band mapping, tenure/attendance/leave/probation/review weighting, bounded query count).
  - Access control: the 3 derived ``@tenant_admin_required`` views (anonymous 302, non-admin 403,
    admin 200); dashboard CRUD is ``@login_required`` (both admin and non-admin get 200 on the
    list).
  - Ownership/authorization (the key surface for this sub-module): a private dashboard is
    owner-or-admin only (403 for anyone else); a shared dashboard is any-tenant-user-readable;
    edit/delete/widget CRUD/move are owner-or-admin gated; cross-tenant pks 404; a non-admin
    POSTing ``is_shared``/``is_default`` on create can never publish/default the dashboard (the
    form drops those fields) and can never set another user as ``owner``.
  - Derived-view aggregate correctness (hand-verified fixtures): executive_dashboard's 6 tiles +
    3 alerts; predictive_analytics's hiring-needs gap/net_need; benchmarking's 4-row scorecard
    with current/prior/delta and RAG (vs.-prior and vs.-target branches).
  - Multi-tenant isolation + empty-tenant div-by-zero guards + query-count ceilings (N+1 guard),
    including a regression guard that ``hr_dashboard_list``'s query count does not grow with the
    number of dashboards (the ``widget_total`` annotation).
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

DERIVED_URL_NAMES = ["executive_dashboard", "predictive_analytics", "benchmarking"]


# ============================================================
# Shared fixtures / helpers
# ============================================================

@pytest.fixture
def today():
    from django.utils import timezone
    return timezone.localdate()


def _mk_employee(tenant, name, dept, *, hired_on, status="active", designation=None, gender="",
                  confirmed_on=None, probation_end_date=None):
    """Build a Party + core.Employment + hrm.EmployeeProfile with fully-controlled attributes."""
    from apps.core.models import Party, Employment
    from apps.hrm.models import EmployeeProfile
    party = Party.objects.create(tenant=tenant, kind="person", name=name)
    employment = Employment.objects.create(
        tenant=tenant, party=party, org_unit=dept, job_title="Staff",
        hired_on=hired_on, status=status,
    )
    return EmployeeProfile.objects.create(
        tenant=tenant, party=party, employment=employment, designation=designation,
        employee_type="full_time", gender=gender,
        confirmed_on=confirmed_on, probation_end_date=probation_end_date,
    )


@pytest.fixture
def other_user(db, tenant_a):
    """A second non-admin tenant_a user, distinct from ``member_user`` — used as a same-tenant
    non-owner/non-admin for ownership-authorization tests."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email="other@acme.com", username="other_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )


@pytest.fixture
def other_client(db, other_user):
    c = Client()
    c.force_login(other_user)
    return c


@pytest.fixture
def private_dashboard_a(db, tenant_a, member_user):
    """A non-shared HRDashboard owned by member_user (non-admin) — the IDOR/authorization anchor."""
    from apps.hrm.models import HRDashboard
    return HRDashboard.objects.create(
        tenant=tenant_a, name="My Private Dash", owner=member_user, is_shared=False)


@pytest.fixture
def shared_dashboard_a(db, tenant_a, member_user):
    """A shared HRDashboard owned by member_user — any tenant_a user may view it."""
    from apps.hrm.models import HRDashboard
    return HRDashboard.objects.create(
        tenant=tenant_a, name="Team Dash", owner=member_user, is_shared=True)


@pytest.fixture
def dashboard_b(db, tenant_b, admin_b):
    """An HRDashboard belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import HRDashboard
    return HRDashboard.objects.create(tenant=tenant_b, name="Globex Dash", owner=admin_b)


@pytest.fixture
def widget_a(db, tenant_a, private_dashboard_a):
    """An HRDashboardWidget on private_dashboard_a."""
    from apps.hrm.models import HRDashboardWidget
    return HRDashboardWidget.objects.create(
        tenant=tenant_a, dashboard=private_dashboard_a, title="Headcount",
        metric="kpi_headcount", chart_type="kpi", position=0)


@pytest.fixture
def widget_b(db, tenant_b, dashboard_b):
    """An HRDashboardWidget belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import HRDashboardWidget
    return HRDashboardWidget.objects.create(
        tenant=tenant_b, dashboard=dashboard_b, title="Headcount B",
        metric="kpi_headcount", chart_type="kpi", position=0)


# ------------------------------------------------------------------ _attrition_risk_scores fixture
@pytest.fixture
def risk_data_a(db, tenant_a, dept_a, shift_a, leave_type_a, today):
    """Four active employees, each pinned to a specific attrition-risk band by hand-verified
    weighted-sum components (weights: tenure 0-30, attendance 0-25, leave 0-20, probation 0-15,
    review-gap 0-10):

      old_emp (Low, score 0): 10+ yrs tenure (0 pts), confirmed (0 prob pts), no attendance/leave
        records (0 pts), reviewed within the last year (0 review pts).
      mid_emp (Medium, score 30): 3-5 yrs tenure (10 pts), confirmed (0 prob pts), 4 present
        punches with 1 late (25% late rate -> attendance_pts = round(0*0.8+25*0.4) = 10), no leave
        (0 pts), never reviewed (10 pts).
      new_emp (High, score 55): <1 yr tenure (30 pts), no attendance records (0 pts), no leave
        (0 pts), probation ending in 20 days (15 pts), never reviewed (10 pts).
      critical_emp (Critical, score 100, clipped): <1 yr tenure (30 pts), 5/5 absent (100%
        absence rate -> attendance_pts = min(25, round(100*0.8)) = 25), 5 recent approved leave
        requests (leave_pts = min(20, 5*4) = 20), probation ending in 20 days (15 pts), never
        reviewed (10 pts).
    """
    from apps.hrm.models import AttendanceRecord, LeaveRequest, ReviewCycle, PerformanceReview
    from django.utils import timezone as tz

    old_emp = _mk_employee(
        tenant_a, "Old Confirmed", dept_a, hired_on=today - datetime.timedelta(days=4100),
        confirmed_on=today - datetime.timedelta(days=3900))
    mid_emp = _mk_employee(
        tenant_a, "Mid Tenure", dept_a, hired_on=today - datetime.timedelta(days=1500),
        confirmed_on=today - datetime.timedelta(days=1400))
    new_emp = _mk_employee(
        tenant_a, "New Hire", dept_a, hired_on=today - datetime.timedelta(days=30),
        probation_end_date=today + datetime.timedelta(days=20))
    critical_emp = _mk_employee(
        tenant_a, "Critical Risk", dept_a, hired_on=today - datetime.timedelta(days=20),
        probation_end_date=today + datetime.timedelta(days=20))

    # mid_emp: 3 on-time + 1 late punch (shift starts 9:00, grace 15min -> late threshold 9:15).
    for d in (5, 10, 15):
        AttendanceRecord.objects.create(
            tenant=tenant_a, employee=mid_emp, date=today - datetime.timedelta(days=d),
            status="present", shift=shift_a,
            check_in=datetime.time(9, 0), check_out=datetime.time(18, 0))
    AttendanceRecord.objects.create(
        tenant=tenant_a, employee=mid_emp, date=today - datetime.timedelta(days=20),
        status="present", shift=shift_a,
        check_in=datetime.time(9, 30), check_out=datetime.time(18, 0))

    # critical_emp: 5/5 absent within the 90-day window.
    for d in range(1, 6):
        AttendanceRecord.objects.create(
            tenant=tenant_a, employee=critical_emp, date=today - datetime.timedelta(days=d),
            status="absent")

    # critical_emp: 5 recent approved leave requests (caps leave_pts at 20).
    for i in range(5):
        LeaveRequest.objects.create(
            tenant=tenant_a, employee=critical_emp, leave_type=leave_type_a,
            start_date=today - datetime.timedelta(days=10 + i),
            end_date=today - datetime.timedelta(days=10 + i), status="approved")

    # old_emp: reviewed (shared) within the last year -> review_pts = 0.
    cycle = ReviewCycle.objects.create(tenant=tenant_a, name="Annual 2026")
    PerformanceReview.objects.create(
        tenant=tenant_a, cycle=cycle, subject=old_emp, reviewer=old_emp,
        review_type="self", status="shared", submitted_at=tz.now())

    return {"old": old_emp, "mid": mid_emp, "new": new_emp, "critical": critical_emp}


# ------------------------------------------------------------------ benchmarking fixture
@pytest.fixture
def benchmark_data_a(db, tenant_a, dept_a, today):
    """Hand-verified tenant_a dataset for ``benchmarking`` over the window
    [date_from=today-30, date_to=today] (prior window [today-61, today-31]):

      10 EmployeeProfiles total: base1-3 (hired -1000d, active, never separated), leaver
      (hired -1000d, terminated, SeparationCase LWD=-5d — inside the CURRENT window only),
      filled1-2 (hired -1000d, active, never separated), exit1-4 (hired -1000d, terminated,
      SeparationCase LWD=-100d — outside BOTH windows, a constant headcount offset).

      headcount_at(today)=5, headcount_at(today-30)=6, headcount_at(today-31)=6,
      headcount_at(today-61)=6 -> hc_cur=5, hc_prior=6, delta=-1 (-16.7%).
      seps_count_cur=1 (leaver only), seps_count_prior=0 -> at_cur=221.2, at_prior=0.0,
      delta=221.2, delta_pct=None (prior 0), rag="red" (down-is-good, prior falsy).

      base1 attendance: current window 2 present + 1 absent (ab_cur=33.3%); prior window
      1 present + 1 absent (ab_prior=50.0%) -> rag="green" (cur <= prior).

      Payroll: one cycle paid -10d (gross 5000, current window), one paid -40d (gross 3000,
      prior window) -> gp_cur=5000, gp_prior=3000, delta=2000 (+66.7%).
    """
    from apps.hrm.models import SeparationCase, AttendanceRecord, PayrollCycle, Payslip

    base = [_mk_employee(tenant_a, f"Base {n}", dept_a, hired_on=today - datetime.timedelta(days=1000))
            for n in ("One", "Two", "Three")]
    leaver = _mk_employee(tenant_a, "Leaver", dept_a,
                           hired_on=today - datetime.timedelta(days=1000), status="terminated")
    SeparationCase.objects.create(
        tenant=tenant_a, employee=leaver, separation_type="resignation",
        actual_last_working_day=today - datetime.timedelta(days=5))

    filled = [_mk_employee(tenant_a, f"Filled {n}", dept_a, hired_on=today - datetime.timedelta(days=1000))
              for n in ("One", "Two")]
    exits = [_mk_employee(tenant_a, f"Bench Exit {i}", dept_a,
                           hired_on=today - datetime.timedelta(days=1000), status="terminated")
             for i in range(1, 5)]
    for e in exits:
        SeparationCase.objects.create(
            tenant=tenant_a, employee=e, separation_type="layoff",
            actual_last_working_day=today - datetime.timedelta(days=100))

    emp = base[0]
    for d, status in ((3, "present"), (10, "present"), (15, "absent")):
        AttendanceRecord.objects.create(
            tenant=tenant_a, employee=emp, date=today - datetime.timedelta(days=d), status=status)
    for d, status in ((40, "present"), (50, "absent")):
        AttendanceRecord.objects.create(
            tenant=tenant_a, employee=emp, date=today - datetime.timedelta(days=d), status=status)

    cycle_cur = PayrollCycle.objects.create(
        tenant=tenant_a, period_start=today - datetime.timedelta(days=40),
        period_end=today - datetime.timedelta(days=11), pay_date=today - datetime.timedelta(days=10),
        cycle_type="regular", status="locked")
    cycle_prior = PayrollCycle.objects.create(
        tenant=tenant_a, period_start=today - datetime.timedelta(days=70),
        period_end=today - datetime.timedelta(days=41), pay_date=today - datetime.timedelta(days=40),
        cycle_type="regular", status="locked")
    Payslip.objects.create(tenant=tenant_a, cycle=cycle_cur, employee=emp, gross_pay=Decimal("5000"))
    Payslip.objects.create(tenant=tenant_a, cycle=cycle_prior, employee=emp, gross_pay=Decimal("3000"))

    return {"base": base, "leaver": leaver, "filled": filled, "exits": exits, "emp": emp,
            "date_from": today - datetime.timedelta(days=30), "date_to": today}


# ------------------------------------------------------------------ predictive_analytics fixture
@pytest.fixture
def hiring_needs_data_a(db, tenant_a, dept_a, today):
    """A Designation (budgeted_headcount=5) with 2 active filled slots and 4 trailing-year exits,
    plus 1 posted JobRequisition -> gap=3, projected_exits=round(4/4)=1, net_need=4, open_reqs=1."""
    from apps.hrm.models import Designation, SeparationCase, JobRequisition

    desig = Designation.objects.create(
        tenant=tenant_a, name="Backend Engineer", department=dept_a, budgeted_headcount=5)

    filled = [_mk_employee(tenant_a, f"Hire Filled {n}", dept_a,
                            hired_on=today - datetime.timedelta(days=500), designation=desig)
              for n in ("One", "Two")]
    exits = [_mk_employee(tenant_a, f"Hire Exit {i}", dept_a,
                           hired_on=today - datetime.timedelta(days=500), designation=desig,
                           status="terminated")
             for i in range(1, 5)]
    for e in exits:
        SeparationCase.objects.create(
            tenant=tenant_a, employee=e, separation_type="resignation",
            actual_last_working_day=today - datetime.timedelta(days=100))

    JobRequisition.objects.create(
        tenant=tenant_a, title="Backend Engineer Opening", designation=desig, department=dept_a,
        headcount=1, req_type="standard", employment_type="full_time",
        reason_for_hire="new_headcount", posting_type="external", priority="medium",
        status="posted")

    return {"designation": desig, "filled": filled, "exits": exits}


# ------------------------------------------------------------------ executive_dashboard alerts fixture
@pytest.fixture
def alerts_data_a(db, tenant_a, dept_a, today):
    """One overdue StatutoryReturn, one pending LeaveRequest, one employee with an expiring
    (30d) probation -> executive_dashboard's 3 alerts each read count=1."""
    from apps.hrm.models import StatutoryReturn, LeaveRequest, LeaveType

    StatutoryReturn.objects.create(
        tenant=tenant_a, scheme="pf", period_type="monthly",
        period_start=today - datetime.timedelta(days=60), period_end=today - datetime.timedelta(days=31),
        due_date=today - datetime.timedelta(days=5), status="pending")

    emp = _mk_employee(tenant_a, "Probation Soon", dept_a,
                        hired_on=today - datetime.timedelta(days=60),
                        probation_end_date=today + datetime.timedelta(days=10))

    leave_type = LeaveType.objects.create(
        tenant=tenant_a, name="Casual", code="CL", is_paid=True,
        accrual_rule="annual", accrual_days=Decimal("10"))
    LeaveRequest.objects.create(
        tenant=tenant_a, employee=emp, leave_type=leave_type,
        start_date=today + datetime.timedelta(days=5), end_date=today + datetime.timedelta(days=6),
        status="pending")

    return {"employee": emp}


# ============================================================
# 1. Models
# ============================================================

class TestModels:
    def test_hrdashboard_defaults(self, tenant_a, admin_user):
        from apps.hrm.models import HRDashboard
        d = HRDashboard.objects.create(tenant=tenant_a, name="Dash", owner=admin_user)
        assert d.is_shared is False
        assert d.is_default is False
        assert d.layout == "two"
        assert d.number.startswith("HRD-")
        assert str(d) == f"{d.number} · {d.name}"

    def test_hrdashboard_number_auto_increments_per_tenant(self, tenant_a, admin_user):
        from apps.hrm.models import HRDashboard
        d1 = HRDashboard.objects.create(tenant=tenant_a, name="D1", owner=admin_user)
        d2 = HRDashboard.objects.create(tenant=tenant_a, name="D2", owner=admin_user)
        assert d1.number == "HRD-00001"
        assert d2.number == "HRD-00002"

    def test_widget_count_property(self, tenant_a, admin_user):
        from apps.hrm.models import HRDashboard, HRDashboardWidget
        d = HRDashboard.objects.create(tenant=tenant_a, name="Dash", owner=admin_user)
        assert d.widget_count == 0
        HRDashboardWidget.objects.create(tenant=tenant_a, dashboard=d, title="W1")
        HRDashboardWidget.objects.create(tenant=tenant_a, dashboard=d, title="W2")
        assert d.widget_count == 2

    def test_hrdashboardwidget_defaults_and_str(self, tenant_a, admin_user):
        from apps.hrm.models import HRDashboard, HRDashboardWidget
        d = HRDashboard.objects.create(tenant=tenant_a, name="Dash", owner=admin_user)
        w = HRDashboardWidget.objects.create(tenant=tenant_a, dashboard=d, title="Headcount")
        assert w.metric == "kpi_headcount"
        assert w.chart_type == "kpi"
        assert w.date_range == "last_90"
        assert w.size == "medium"
        assert w.position == 0
        assert str(w) == f"Headcount ({w.get_chart_type_display()})"


# ============================================================
# 2. Forms
# ============================================================

class TestDashboardFormFieldExclusions:
    def test_can_share_false_drops_privileged_fields(self, tenant_a):
        from apps.hrm.forms import HRDashboardForm
        form = HRDashboardForm(tenant=tenant_a, can_share=False)
        assert "is_shared" not in form.fields
        assert "is_default" not in form.fields

    def test_can_share_true_keeps_privileged_fields(self, tenant_a):
        from apps.hrm.forms import HRDashboardForm
        form = HRDashboardForm(tenant=tenant_a, can_share=True)
        assert "is_shared" in form.fields
        assert "is_default" in form.fields

    def test_system_fields_never_form_fields(self, tenant_a):
        from apps.hrm.forms import HRDashboardForm
        form = HRDashboardForm(tenant=tenant_a, can_share=True)
        for f in ("owner", "tenant", "number", "created_at", "updated_at"):
            assert f not in form.fields


class TestWidgetFormValidation:
    def test_incompatible_metric_chart_invalid(self, tenant_a):
        from apps.hrm.forms import HRDashboardWidgetForm
        form = HRDashboardWidgetForm(data={
            "title": "Risk", "metric": "top_attrition_risk_employees", "chart_type": "line",
            "date_range": "last_90", "size": "medium", "target_value": "",
        }, tenant=tenant_a)
        assert not form.is_valid()
        assert "chart_type" in form.errors

    def test_compatible_metric_chart_valid(self, tenant_a):
        from apps.hrm.forms import HRDashboardWidgetForm
        form = HRDashboardWidgetForm(data={
            "title": "Risk", "metric": "top_attrition_risk_employees", "chart_type": "table",
            "date_range": "last_90", "size": "medium", "target_value": "",
        }, tenant=tenant_a)
        assert form.is_valid(), form.errors

    def test_system_fields_never_form_fields(self, tenant_a):
        from apps.hrm.forms import HRDashboardWidgetForm
        form = HRDashboardWidgetForm(tenant=tenant_a)
        for f in ("tenant", "dashboard", "position", "created_at", "updated_at"):
            assert f not in form.fields


# ============================================================
# 3. compute_widget / analytics compute-layer correctness
# ============================================================

class TestComputeWidgetBasics:
    def test_scalar_kpi_headcount(self, tenant_a, employee_a, employee_a2):
        from apps.hrm.models import HRDashboard, HRDashboardWidget
        from apps.hrm.analytics import compute_widget
        dashboard = HRDashboard.objects.create(tenant=tenant_a, name="D")
        widget = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard, title="HC", metric="kpi_headcount",
            chart_type="kpi", date_range="all")
        result = compute_widget(widget)
        assert result["kind"] == "scalar"
        assert result["value"] == 2.0
        assert result["display"] == "2"
        assert result["pct"] == 100

    def test_series_gender_split(self, tenant_a, employee_a, today):
        from apps.hrm.models import HRDashboard, HRDashboardWidget
        from apps.hrm.analytics import compute_widget
        # employee_a (conftest) is gender="female"; add a male employee.
        _mk_employee(tenant_a, "Male Employee", None, hired_on=today, gender="male")
        dashboard = HRDashboard.objects.create(tenant=tenant_a, name="D")
        widget = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard, title="Gender", metric="gender_split",
            chart_type="pie", date_range="all")
        result = compute_widget(widget)
        assert result["kind"] == "series"
        assert set(result["labels"]) == {"Male", "Female"}
        assert sum(result["data"]) == 2

    def test_table_top_attrition_risk_employees(self, tenant_a, risk_data_a):
        from apps.hrm.models import HRDashboard, HRDashboardWidget
        from apps.hrm.analytics import compute_widget
        dashboard = HRDashboard.objects.create(tenant=tenant_a, name="D")
        widget = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard, title="Risk",
            metric="top_attrition_risk_employees", chart_type="table", date_range="all")
        result = compute_widget(widget)
        assert result["kind"] == "table"
        assert result["columns"] == ["Employee", "Department", "Tenure (yrs)", "Risk Score", "Risk Band"]
        scores = [row[3] for row in result["rows"]]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == 100
        assert result["rows"][0][4] == "Critical"
        assert scores[-1] == 0
        assert result["rows"][-1][4] == "Low"

    def test_unknown_metric_returns_error_without_raising(self, tenant_a):
        from apps.hrm.models import HRDashboard, HRDashboardWidget
        from apps.hrm.analytics import compute_widget
        dashboard = HRDashboard.objects.create(tenant=tenant_a, name="D")
        widget = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard, title="Bogus", metric="not_a_real_metric",
            chart_type="kpi", date_range="all")
        result = compute_widget(widget)
        assert result == {"kind": "scalar", "value": 0, "display": "-", "error": "Unknown metric"}

    def test_allowed_charts_matches_widget_metrics(self):
        from apps.hrm.analytics import WIDGET_METRICS, allowed_charts
        for metric, meta in WIDGET_METRICS.items():
            assert allowed_charts(metric) == meta["charts"]
        assert allowed_charts("bogus_metric") == []

    def test_widget_metrics_in_sync_with_choices(self):
        from apps.hrm.analytics import WIDGET_METRICS
        from apps.hrm.models import WIDGET_METRIC_CHOICES
        assert {k for k, _ in WIDGET_METRIC_CHOICES} == set(WIDGET_METRICS)


class TestComputeWidgetTargetGuard:
    def test_zero_target_no_div_by_zero(self, tenant_a, employee_a):
        from apps.hrm.models import HRDashboard, HRDashboardWidget
        from apps.hrm.analytics import compute_widget
        dashboard = HRDashboard.objects.create(tenant=tenant_a, name="D")
        widget = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard, title="HC", metric="kpi_headcount",
            chart_type="kpi", date_range="all", target_value=Decimal("0"))
        result = compute_widget(widget)
        assert 0 <= result["pct"] <= 100

    def test_negative_target_ignored(self, tenant_a, employee_a):
        from apps.hrm.models import HRDashboard, HRDashboardWidget
        from apps.hrm.analytics import compute_widget
        dashboard = HRDashboard.objects.create(tenant=tenant_a, name="D")
        widget = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=dashboard, title="HC", metric="kpi_headcount",
            chart_type="kpi", date_range="all", target_value=Decimal("-5"))
        result = compute_widget(widget)
        assert 0 <= result["pct"] <= 100

    def test_zero_value_zero_target_no_crash(self, tenant_b):
        from apps.hrm.models import HRDashboard, HRDashboardWidget
        from apps.hrm.analytics import compute_widget
        dashboard = HRDashboard.objects.create(tenant=tenant_b, name="D")
        widget = HRDashboardWidget.objects.create(
            tenant=tenant_b, dashboard=dashboard, title="HC", metric="kpi_headcount",
            chart_type="kpi", date_range="all", target_value=Decimal("0"))
        result = compute_widget(widget)
        assert result["value"] == 0.0
        assert result["pct"] == 0


class TestAttritionRiskScores:
    def test_new_employee_scores_higher_than_tenured(self, tenant_a, risk_data_a):
        from apps.hrm.analytics import _attrition_risk_scores
        scores = {s["employee_id"]: s for s in _attrition_risk_scores(tenant_a)}
        assert scores[risk_data_a["new"].pk]["score"] > scores[risk_data_a["old"].pk]["score"]

    def test_bands_map_correctly(self, tenant_a, risk_data_a):
        from apps.hrm.analytics import _attrition_risk_scores
        scores = {s["employee_id"]: s for s in _attrition_risk_scores(tenant_a)}
        assert scores[risk_data_a["old"].pk]["score"] == 0
        assert scores[risk_data_a["old"].pk]["band"] == "Low"
        assert scores[risk_data_a["mid"].pk]["score"] == 30
        assert scores[risk_data_a["mid"].pk]["band"] == "Medium"
        assert scores[risk_data_a["new"].pk]["score"] == 55
        assert scores[risk_data_a["new"].pk]["band"] == "High"
        assert scores[risk_data_a["critical"].pk]["score"] == 100
        assert scores[risk_data_a["critical"].pk]["band"] == "Critical"

    def test_empty_tenant_returns_empty_list(self, tenant_b):
        from apps.hrm.analytics import _attrition_risk_scores
        assert _attrition_risk_scores(tenant_b) == []

    def test_bounded_query_count(self, tenant_a, risk_data_a, django_assert_max_num_queries):
        from apps.hrm.analytics import _attrition_risk_scores
        with django_assert_max_num_queries(6):
            _attrition_risk_scores(tenant_a)


# ============================================================
# 4. Access control — derived views + dashboard list
# ============================================================

class TestDerivedViewsAccessControl:
    @pytest.mark.parametrize("url_name", DERIVED_URL_NAMES)
    def test_anonymous_redirects_to_login(self, client, url_name):
        resp = client.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    @pytest.mark.parametrize("url_name", DERIVED_URL_NAMES)
    def test_non_admin_member_forbidden(self, member_client, url_name):
        resp = member_client.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 403

    @pytest.mark.parametrize("url_name", DERIVED_URL_NAMES)
    def test_tenant_admin_ok(self, client_a, url_name):
        resp = client_a.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 200


class TestDashboardListAccess:
    def test_anonymous_redirects_to_login(self, client):
        resp = client.get(reverse("hrm:hr_dashboard_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_admin_ok(self, client_a):
        resp = client_a.get(reverse("hrm:hr_dashboard_list"))
        assert resp.status_code == 200

    def test_non_admin_ok(self, member_client):
        resp = member_client.get(reverse("hrm:hr_dashboard_list"))
        assert resp.status_code == 200


# ============================================================
# 5. Ownership / authorization — the key surface for this sub-module
# ============================================================

class TestDashboardDetailAuthorization:
    def test_owner_sees_own_private_dashboard(self, member_client, private_dashboard_a):
        resp = member_client.get(reverse("hrm:hr_dashboard_detail", args=[private_dashboard_a.pk]))
        assert resp.status_code == 200

    def test_admin_sees_any_dashboard(self, client_a, private_dashboard_a):
        resp = client_a.get(reverse("hrm:hr_dashboard_detail", args=[private_dashboard_a.pk]))
        assert resp.status_code == 200

    def test_non_owner_non_admin_forbidden_on_private(self, other_client, private_dashboard_a):
        resp = other_client.get(reverse("hrm:hr_dashboard_detail", args=[private_dashboard_a.pk]))
        assert resp.status_code == 403

    def test_non_owner_non_admin_allowed_on_shared(self, other_client, shared_dashboard_a):
        resp = other_client.get(reverse("hrm:hr_dashboard_detail", args=[shared_dashboard_a.pk]))
        assert resp.status_code == 200

    def test_cross_tenant_pk_404(self, client_a, dashboard_b):
        resp = client_a.get(reverse("hrm:hr_dashboard_detail", args=[dashboard_b.pk]))
        assert resp.status_code == 404


class TestDashboardWriteAuthorization:
    def test_edit_non_owner_non_admin_forbidden(self, other_client, private_dashboard_a):
        resp = other_client.get(reverse("hrm:hr_dashboard_edit", args=[private_dashboard_a.pk]))
        assert resp.status_code == 403

    def test_edit_owner_allowed(self, member_client, private_dashboard_a):
        resp = member_client.get(reverse("hrm:hr_dashboard_edit", args=[private_dashboard_a.pk]))
        assert resp.status_code == 200

    def test_edit_admin_allowed(self, client_a, private_dashboard_a):
        resp = client_a.get(reverse("hrm:hr_dashboard_edit", args=[private_dashboard_a.pk]))
        assert resp.status_code == 200

    def test_edit_cross_tenant_pk_404(self, client_a, dashboard_b):
        resp = client_a.get(reverse("hrm:hr_dashboard_edit", args=[dashboard_b.pk]))
        assert resp.status_code == 404

    def test_delete_non_owner_non_admin_forbidden(self, other_client, private_dashboard_a):
        from apps.hrm.models import HRDashboard
        resp = other_client.post(reverse("hrm:hr_dashboard_delete", args=[private_dashboard_a.pk]))
        assert resp.status_code == 403
        assert HRDashboard.objects.filter(pk=private_dashboard_a.pk).exists()

    def test_delete_owner_allowed(self, member_client, private_dashboard_a):
        from apps.hrm.models import HRDashboard
        resp = member_client.post(reverse("hrm:hr_dashboard_delete", args=[private_dashboard_a.pk]))
        assert resp.status_code == 302
        assert not HRDashboard.objects.filter(pk=private_dashboard_a.pk).exists()

    def test_delete_cross_tenant_pk_404(self, client_a, dashboard_b):
        from apps.hrm.models import HRDashboard
        resp = client_a.post(reverse("hrm:hr_dashboard_delete", args=[dashboard_b.pk]))
        assert resp.status_code == 404
        assert HRDashboard.objects.filter(pk=dashboard_b.pk).exists()


class TestWidgetAuthorization:
    def test_create_non_owner_non_admin_forbidden(self, other_client, private_dashboard_a):
        resp = other_client.get(reverse("hrm:hr_widget_create", args=[private_dashboard_a.pk]))
        assert resp.status_code == 403

    def test_create_owner_allowed(self, member_client, private_dashboard_a):
        resp = member_client.get(reverse("hrm:hr_widget_create", args=[private_dashboard_a.pk]))
        assert resp.status_code == 200

    def test_create_cross_tenant_dashboard_404(self, client_a, dashboard_b):
        resp = client_a.get(reverse("hrm:hr_widget_create", args=[dashboard_b.pk]))
        assert resp.status_code == 404

    def test_edit_non_owner_non_admin_forbidden(self, other_client, widget_a):
        resp = other_client.get(reverse("hrm:hr_widget_edit", args=[widget_a.pk]))
        assert resp.status_code == 403

    def test_edit_owner_allowed(self, member_client, widget_a):
        resp = member_client.get(reverse("hrm:hr_widget_edit", args=[widget_a.pk]))
        assert resp.status_code == 200

    def test_edit_cross_tenant_pk_404(self, client_a, widget_b):
        resp = client_a.get(reverse("hrm:hr_widget_edit", args=[widget_b.pk]))
        assert resp.status_code == 404

    def test_delete_non_owner_non_admin_forbidden(self, other_client, widget_a):
        from apps.hrm.models import HRDashboardWidget
        resp = other_client.post(reverse("hrm:hr_widget_delete", args=[widget_a.pk]))
        assert resp.status_code == 403
        assert HRDashboardWidget.objects.filter(pk=widget_a.pk).exists()

    def test_delete_owner_allowed(self, member_client, widget_a):
        from apps.hrm.models import HRDashboardWidget
        resp = member_client.post(reverse("hrm:hr_widget_delete", args=[widget_a.pk]))
        assert resp.status_code == 302
        assert not HRDashboardWidget.objects.filter(pk=widget_a.pk).exists()

    def test_delete_cross_tenant_pk_404(self, client_a, widget_b):
        resp = client_a.post(reverse("hrm:hr_widget_delete", args=[widget_b.pk]))
        assert resp.status_code == 404

    def test_move_non_owner_non_admin_forbidden(self, other_client, widget_a):
        resp = other_client.post(reverse("hrm:hr_widget_move", args=[widget_a.pk, "up"]))
        assert resp.status_code == 403

    def test_move_owner_allowed(self, member_client, widget_a):
        resp = member_client.post(reverse("hrm:hr_widget_move", args=[widget_a.pk, "up"]))
        assert resp.status_code == 302

    def test_move_cross_tenant_pk_404(self, client_a, widget_b):
        resp = client_a.post(reverse("hrm:hr_widget_move", args=[widget_b.pk, "up"]))
        assert resp.status_code == 404


class TestPrivilegeEscalation:
    def test_non_admin_create_cannot_publish_or_default(self, member_client, tenant_a, member_user):
        from apps.hrm.models import HRDashboard
        resp = member_client.post(reverse("hrm:hr_dashboard_create"), {
            "name": "Sneaky Dash", "description": "", "layout": "two",
            "is_shared": "on", "is_default": "on",
        })
        assert resp.status_code == 302
        dash = HRDashboard.objects.get(tenant=tenant_a, name="Sneaky Dash")
        assert dash.is_shared is False
        assert dash.is_default is False
        assert dash.owner_id == member_user.pk

    def test_admin_create_can_publish_and_default(self, client_a, tenant_a, admin_user):
        from apps.hrm.models import HRDashboard
        resp = client_a.post(reverse("hrm:hr_dashboard_create"), {
            "name": "Admin Dash", "description": "", "layout": "two",
            "is_shared": "on", "is_default": "on",
        })
        assert resp.status_code == 302
        dash = HRDashboard.objects.get(tenant=tenant_a, name="Admin Dash")
        assert dash.is_shared is True
        assert dash.is_default is True
        assert dash.owner_id == admin_user.pk

    def test_owner_always_the_creator(self, member_client, tenant_a, member_user):
        from apps.hrm.models import HRDashboard
        resp = member_client.post(reverse("hrm:hr_dashboard_create"), {
            "name": "Owner Test", "description": "", "layout": "one",
        })
        assert resp.status_code == 302
        dash = HRDashboard.objects.get(tenant=tenant_a, name="Owner Test")
        assert dash.owner_id == member_user.pk


class TestWidgetMove:
    def test_move_up_swaps_positions(self, client_a, tenant_a, private_dashboard_a):
        from apps.hrm.models import HRDashboardWidget
        w0 = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=private_dashboard_a, title="W0", position=0)
        w1 = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=private_dashboard_a, title="W1", position=1)
        w2 = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=private_dashboard_a, title="W2", position=2)

        resp = client_a.post(reverse("hrm:hr_widget_move", args=[w2.pk, "up"]))
        assert resp.status_code == 302

        w0.refresh_from_db()
        w1.refresh_from_db()
        w2.refresh_from_db()
        assert w0.position == 0
        assert w2.position == 1
        assert w1.position == 2
        assert sorted([w0.position, w1.position, w2.position]) == [0, 1, 2]

    def test_move_first_up_is_noop(self, client_a, tenant_a, private_dashboard_a):
        from apps.hrm.models import HRDashboardWidget
        w0 = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=private_dashboard_a, title="W0", position=0)
        w1 = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=private_dashboard_a, title="W1", position=1)
        resp = client_a.post(reverse("hrm:hr_widget_move", args=[w0.pk, "up"]))
        assert resp.status_code == 302
        w0.refresh_from_db()
        w1.refresh_from_db()
        assert w0.position == 0
        assert w1.position == 1

    def test_move_last_down_is_noop(self, client_a, tenant_a, private_dashboard_a):
        from apps.hrm.models import HRDashboardWidget
        w0 = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=private_dashboard_a, title="W0", position=0)
        w1 = HRDashboardWidget.objects.create(
            tenant=tenant_a, dashboard=private_dashboard_a, title="W1", position=1)
        resp = client_a.post(reverse("hrm:hr_widget_move", args=[w1.pk, "down"]))
        assert resp.status_code == 302
        w0.refresh_from_db()
        w1.refresh_from_db()
        assert w0.position == 0
        assert w1.position == 1


class TestCSRFEnforcement:
    def test_dashboard_delete_enforces_csrf(self, admin_user, private_dashboard_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:hr_dashboard_delete", args=[private_dashboard_a.pk]))
        assert resp.status_code == 403

    def test_widget_delete_enforces_csrf(self, admin_user, widget_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:hr_widget_delete", args=[widget_a.pk]))
        assert resp.status_code == 403

    def test_widget_move_enforces_csrf(self, admin_user, widget_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:hr_widget_move", args=[widget_a.pk, "up"]))
        assert resp.status_code == 403


# ============================================================
# 6. Dashboard list — multi-tenant isolation + N+1 regression guard
# ============================================================

class TestDashboardListIsolation:
    def test_excludes_other_tenant_dashboards(self, client_a, dashboard_b):
        resp = client_a.get(reverse("hrm:hr_dashboard_list"))
        ids = {o.pk for o in resp.context["object_list"]}
        assert dashboard_b.pk not in ids

    def test_own_and_shared_visible_others_private_hidden(
            self, client_a, tenant_a, admin_user, private_dashboard_a, shared_dashboard_a):
        from apps.hrm.models import HRDashboard
        own = HRDashboard.objects.create(tenant=tenant_a, name="Admin Own", owner=admin_user)
        resp = client_a.get(reverse("hrm:hr_dashboard_list"))
        ids = {o.pk for o in resp.context["object_list"]}
        assert own.pk in ids
        assert shared_dashboard_a.pk in ids
        # member_user's PRIVATE dashboard is not admin_user's own and not shared -> not listed
        # (the list has no admin bypass, unlike the detail/edit/delete views).
        assert private_dashboard_a.pk not in ids

    def test_list_query_count_does_not_grow_with_dashboard_count(self, client_a, tenant_a, admin_user):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        from apps.hrm.models import HRDashboard, HRDashboardWidget

        for i in range(2):
            d = HRDashboard.objects.create(tenant=tenant_a, name=f"D{i}", owner=admin_user)
            HRDashboardWidget.objects.create(tenant=tenant_a, dashboard=d, title="W1")
            HRDashboardWidget.objects.create(tenant=tenant_a, dashboard=d, title="W2")
        with CaptureQueriesContext(connection) as small_ctx:
            resp = client_a.get(reverse("hrm:hr_dashboard_list"))
        assert resp.status_code == 200
        small_count = len(small_ctx.captured_queries)

        for i in range(2, 12):
            d = HRDashboard.objects.create(tenant=tenant_a, name=f"D{i}", owner=admin_user)
            HRDashboardWidget.objects.create(tenant=tenant_a, dashboard=d, title="W1")
            HRDashboardWidget.objects.create(tenant=tenant_a, dashboard=d, title="W2")
        with CaptureQueriesContext(connection) as large_ctx:
            resp = client_a.get(reverse("hrm:hr_dashboard_list"))
        assert resp.status_code == 200
        large_count = len(large_ctx.captured_queries)

        assert large_count == small_count


# ============================================================
# 7. executive_dashboard — 6 tiles + 3 alerts
# ============================================================

class TestExecutiveDashboard:
    def test_tiles_and_alerts_structure(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:executive_dashboard"))
        assert resp.status_code == 200
        tiles = resp.context["tiles"]
        assert len(tiles) == 6
        assert [t["label"] for t in tiles] == [
            "Active Headcount", "Attrition Rate (12mo)", "Open Requisitions",
            "Avg Tenure (yrs)", "Gross Payroll (latest)", "Pending Approvals",
        ]
        assert len(resp.context["alerts"]) == 3

    def test_alerts_counts_and_severities(self, client_a, alerts_data_a):
        resp = client_a.get(reverse("hrm:executive_dashboard"))
        alerts = {a["label"]: a for a in resp.context["alerts"]}
        assert alerts["Overdue Statutory Returns"]["count"] == 1
        assert alerts["Overdue Statutory Returns"]["severity"] == "red"
        assert alerts["Pending Leave Requests"]["count"] == 1
        assert alerts["Pending Leave Requests"]["severity"] == "amber"
        assert alerts["Expiring Probations (30d)"]["count"] == 1
        assert alerts["Expiring Probations (30d)"]["severity"] == "amber"
        tiles = {t["label"]: t for t in resp.context["tiles"]}
        assert tiles["Pending Approvals"]["value"] == 2

    def test_empty_tenant_zero_valued_tiles(self, client_b):
        resp = client_b.get(reverse("hrm:executive_dashboard"))
        assert resp.status_code == 200
        assert len(resp.context["tiles"]) == 6
        assert resp.context["tiles"][0]["value"] == 0
        alerts = {a["label"]: a for a in resp.context["alerts"]}
        assert alerts["Overdue Statutory Returns"]["count"] == 0
        assert alerts["Overdue Statutory Returns"]["severity"] == "muted"

    def test_cross_tenant_department_ignored(self, client_a, dept_b, employee_a):
        resp = client_a.get(reverse("hrm:executive_dashboard"), {"department": dept_b.pk})
        assert resp.status_code == 200
        assert resp.context["department"] is None

    def test_query_count_bounded(self, client_a, benchmark_data_a, django_assert_max_num_queries):
        # Measured 24 (2 PayrollCycles -> 2 total_gross aggregates in the trend loop, plus
        # session/auth/tenant-resolution overhead) — a generous-but-real ceiling.
        with django_assert_max_num_queries(26):
            client_a.get(reverse("hrm:executive_dashboard"))


# ============================================================
# 8. predictive_analytics — hiring-needs gap/net_need
# ============================================================

class TestPredictiveAnalytics:
    def test_hiring_needs_row(self, client_a, hiring_needs_data_a):
        resp = client_a.get(reverse("hrm:predictive_analytics"))
        assert resp.status_code == 200
        rows = {r["designation"]: r for r in resp.context["hiring_rows"]}
        row = rows["Backend Engineer"]
        assert row["budgeted"] == 5
        assert row["filled"] == 2
        assert row["gap"] == 3
        assert row["trailing_exits"] == 4
        assert row["projected_exits"] == 1
        assert row["open_reqs"] == 1
        assert row["net_need"] == 4

    def test_empty_tenant_zero_rows(self, client_b):
        resp = client_b.get(reverse("hrm:predictive_analytics"))
        assert resp.status_code == 200
        assert resp.context["hiring_rows"] == []
        assert resp.context["risk_rows"] == []
        assert resp.context["avg_risk"] == 0.0
        assert resp.context["band_counts"] == {}

    def test_cross_tenant_department_ignored(self, client_a, dept_b, hiring_needs_data_a):
        resp = client_a.get(reverse("hrm:predictive_analytics"), {"department": dept_b.pk})
        assert resp.status_code == 200
        assert resp.context["department"] is None

    def test_query_count_bounded(self, client_a, hiring_needs_data_a, django_assert_max_num_queries):
        # Measured 17 (incl. session/auth/tenant-resolution overhead) — a generous-but-real ceiling.
        with django_assert_max_num_queries(19):
            client_a.get(reverse("hrm:predictive_analytics"))


# ============================================================
# 9. benchmarking — 4-row scorecard + RAG (vs.-prior and vs.-target)
# ============================================================

class TestBenchmarking:
    def test_scorecard_structure_and_values(self, client_a, benchmark_data_a):
        date_from, date_to = benchmark_data_a["date_from"], benchmark_data_a["date_to"]
        resp = client_a.get(reverse("hrm:benchmarking"),
                             {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()})
        assert resp.status_code == 200
        assert len(resp.context["scorecard"]) == 4
        rows = {r["label"]: r for r in resp.context["scorecard"]}

        hc = rows["Headcount"]
        assert hc["current"] == 5
        assert hc["prior"] == 6
        assert hc["delta"] == -1
        assert hc["delta_pct"] == -16.7
        assert hc["rag"] == "info"

        at = rows["Attrition Rate (%)"]
        assert at["current"] == 221.2
        assert at["prior"] == 0.0
        assert at["delta"] == 221.2
        assert at["delta_pct"] is None
        assert at["rag"] == "red"

        ab = rows["Absenteeism Rate (%)"]
        assert ab["current"] == 33.3
        assert ab["prior"] == 50.0
        assert ab["rag"] == "green"

        gp = rows["Gross Payroll ($)"]
        assert gp["current"] == 5000.0
        assert gp["prior"] == 3000.0
        assert gp["delta"] == 2000.0
        assert gp["delta_pct"] == 66.7
        assert gp["rag"] == "info"

    def test_attrition_rag_vs_target(self, client_a, benchmark_data_a):
        date_from, date_to = benchmark_data_a["date_from"], benchmark_data_a["date_to"]
        params = {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}

        resp = client_a.get(reverse("hrm:benchmarking"), {**params, "target_attrition_rate": "1000"})
        rows = {r["label"]: r for r in resp.context["scorecard"]}
        assert rows["Attrition Rate (%)"]["rag"] == "green"

        resp = client_a.get(reverse("hrm:benchmarking"), {**params, "target_attrition_rate": "200"})
        rows = {r["label"]: r for r in resp.context["scorecard"]}
        assert rows["Attrition Rate (%)"]["rag"] == "amber"

        resp = client_a.get(reverse("hrm:benchmarking"), {**params, "target_attrition_rate": "-5"})
        rows = {r["label"]: r for r in resp.context["scorecard"]}
        assert rows["Attrition Rate (%)"]["rag"] == "info"

    def test_empty_tenant_zero_scorecard(self, client_b):
        resp = client_b.get(reverse("hrm:benchmarking"))
        assert resp.status_code == 200
        rows = {r["label"]: r for r in resp.context["scorecard"]}
        assert rows["Headcount"]["current"] == 0
        assert rows["Attrition Rate (%)"]["current"] == 0.0
        assert rows["Absenteeism Rate (%)"]["current"] == 0.0

    def test_cross_tenant_department_ignored(self, client_a, dept_b, benchmark_data_a):
        resp = client_a.get(reverse("hrm:benchmarking"), {"department": dept_b.pk})
        assert resp.status_code == 200
        assert resp.context["department"] is None

    def test_query_count_bounded(self, client_a, benchmark_data_a, django_assert_max_num_queries):
        # Measured 24 (2 PayrollCycles in each of the current/prior windows contribute extra
        # aggregates, plus session/auth/tenant-resolution overhead) — generous-but-real ceiling.
        date_from, date_to = benchmark_data_a["date_from"], benchmark_data_a["date_to"]
        with django_assert_max_num_queries(26):
            client_a.get(reverse("hrm:benchmarking"),
                         {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()})
