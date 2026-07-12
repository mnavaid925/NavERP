"""Tests for HRM 3.29 Attendance Reports sub-module: derived, read-only report views (no models).

Mirrors ``test_hr_reports.py`` (3.28) — same fixture style, access-control + aggregate-correctness
+ IDOR + div-by-zero + query-count structure.

Covers all five ``@tenant_admin_required`` views in ``apps/hrm/views.py``
(``attendance_reports_index``, ``attendance_summary_report``, ``late_early_report``,
``absenteeism_report``, ``overtime_report``), which reuse the 3.28 report helpers
(``_report_period``/``_report_department``/``_dept_choices``) plus the 3.29-local
``_attendance_base``/``_attendance_pe_tracked``/``_fold_att``:

  - Access control: anonymous -> redirect, non-admin member -> 403, tenant admin -> 200.
  - Rendering never 500s: no params / a full filter set / nonsensical params (reversed date
    range, non-digit department, far-future dates).
  - Aggregate correctness against hand-verified fixtures: attendance_summary (present-equivalent
    attendance_pct = present + regularized + 0.5*half_day over tracked = total - holiday -
    on_leave; status_rows; by_department; the tracked==0 div-by-zero guard), late_early (late/early
    minute math against a shift's start/end + grace_minutes; the code-reviewer's top_late fix —
    keyed by employee_id so two same-named employees are two distinct rows), absenteeism
    (absence_rate; frequent absentees), overtime (default excludes draft/rejected/cancelled;
    ?status= scopes to exactly that status; status_rows always reflects the full pre-filter mix;
    pay_equiv_hours = sum(hours * multiplier); by_employee keyed by employee_id).
  - Multi-tenant isolation: another tenant's attendance/overtime never leaks into totals; a
    cross-tenant ``?department=`` pk is ignored (falls back to "all", not empty).
  - Div-by-zero: an empty tenant renders every report at 200 with zero/None KPIs.
  - Query-count ceilings on attendance_summary_report/overtime_report (N+1 guard).
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db

REPORT_URL_NAMES = [
    "attendance_reports_index",
    "attendance_summary_report",
    "late_early_report",
    "absenteeism_report",
    "overtime_report",
]

DATE_SCOPED_URL_NAMES = [
    "attendance_summary_report",
    "late_early_report",
    "absenteeism_report",
    "overtime_report",
]


# ============================================================
# Shared fixtures / helpers
# ============================================================

@pytest.fixture
def today():
    return timezone.localdate()


@pytest.fixture
def dept_sales_a(db, tenant_a):
    """A second OrgUnit department for tenant_a — differentiates department-scoping tests."""
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, kind="department", name="Sales")


@pytest.fixture
def dept_only_leave_a(db, tenant_a):
    """A third OrgUnit department used ONLY for the tracked==0 (holiday/on_leave-only) fixture."""
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, kind="department", name="OnlyLeave")


def _mk_employee(tenant, name, dept):
    """Build a Party + core.Employment + hrm.EmployeeProfile with a controlled name/department
    (the conftest employee_a fixture is a single fixed employee — these tests need many, with
    duplicate names to prove employee_id-keyed grouping)."""
    from apps.core.models import Party, Employment
    from apps.hrm.models import EmployeeProfile
    party = Party.objects.create(tenant=tenant, kind="person", name=name)
    employment = Employment.objects.create(
        tenant=tenant, party=party, org_unit=dept, job_title="Staff", status="active")
    return EmployeeProfile.objects.create(
        tenant=tenant, party=party, employment=employment, employee_type="full_time")


def _qs(date_from=None, date_to=None, **extra):
    params = {}
    if date_from is not None:
        params["date_from"] = date_from.isoformat()
    if date_to is not None:
        params["date_to"] = date_to.isoformat()
    params.update(extra)
    return params


@pytest.fixture
def att_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """Hand-verified attendance dataset for tenant_a, all dated D0 = today-40 (plus one extra
    absence for emp_ab1 on D0-1, for the "frequent absentee" proof):

      dept_a (Engineering, 7 records: 6 on D0 + 1 extra on D0-1):
        emp_p1: present, emp_p2: present, emp_ab1: absent (D0) + absent (D0-1, 2nd occurrence),
        emp_half: half_day, emp_holiday: holiday, emp_leave: on_leave.
      dept_sales_a (Sales, 3 records on D0):
        emp_p3: present, emp_ab2: absent, emp_reg: regularized.

    Unfiltered totals (10 records): present=3, absent=3, half_day=1, holiday=1, on_leave=1,
    regularized=1 -> tracked = 10-1-1 = 8; present_equivalent = 3+1+0.5*1 = 4.5.
    dept_a-only (7 records: emp_p1, emp_p2, emp_ab1 x2, emp_half, emp_holiday, emp_leave):
    tracked = 7-1-1 = 5; present_equivalent = 2+0.5*1 = 2.5.
    dept_sales_a-only (3 records): tracked = 3; present_equivalent = 1+1 = 2.
    """
    from apps.hrm.models import AttendanceRecord
    d0 = today - datetime.timedelta(days=40)
    d0_prev = d0 - datetime.timedelta(days=1)

    emp_p1 = _mk_employee(tenant_a, "Present One", dept_a)
    emp_p2 = _mk_employee(tenant_a, "Present Two", dept_a)
    emp_p3 = _mk_employee(tenant_a, "Present Three", dept_sales_a)
    emp_ab1 = _mk_employee(tenant_a, "Absent One", dept_a)
    emp_ab2 = _mk_employee(tenant_a, "Absent Two", dept_sales_a)
    emp_half = _mk_employee(tenant_a, "Half Day Emp", dept_a)
    emp_holiday = _mk_employee(tenant_a, "Holiday Emp", dept_a)
    emp_leave = _mk_employee(tenant_a, "Leave Emp", dept_a)
    emp_reg = _mk_employee(tenant_a, "Regularized Emp", dept_sales_a)

    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_p1, date=d0, status="present")
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_p2, date=d0, status="present")
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_p3, date=d0, status="present")
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_ab1, date=d0, status="absent")
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_ab1, date=d0_prev, status="absent")
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_ab2, date=d0, status="absent")
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_half, date=d0, status="half_day")
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_holiday, date=d0, status="holiday")
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_leave, date=d0, status="on_leave")
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_reg, date=d0, status="regularized")

    return {
        "d0": d0, "d0_prev": d0_prev, "date_from": d0_prev, "date_to": d0,
        "emp_ab1": emp_ab1, "emp_ab2": emp_ab2,
    }


@pytest.fixture
def only_nonworking_data_a(db, tenant_a, dept_only_leave_a, today):
    """Two records, BOTH holiday/on_leave, in a distinct department — filtering the summary/
    absenteeism reports to this department yields tracked == 0, proving the div-by-zero guard
    (attendance_pct/absence_rate == 0.0, never a crash)."""
    from apps.hrm.models import AttendanceRecord
    d0 = today - datetime.timedelta(days=40)
    emp_hol = _mk_employee(tenant_a, "Holiday Only", dept_only_leave_a)
    emp_lv = _mk_employee(tenant_a, "Leave Only", dept_only_leave_a)
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_hol, date=d0, status="holiday")
    AttendanceRecord.objects.create(tenant=tenant_a, employee=emp_lv, date=d0, status="on_leave")
    return {"dept": dept_only_leave_a, "date": d0}


@pytest.fixture
def late_data_a(db, tenant_a, dept_a, shift_a, today):
    """Hand-verified late/early dataset for tenant_a, all dated D1 = today-20, all against
    ``shift_a`` (start 09:00, end 18:00, grace_minutes=15 — late threshold 09:15, early-checkout
    threshold 17:45):

      emp_ontime:  check_in 09:10 (on time), check_out 18:00 (on time).
      emp_late30:  check_in 09:45 -> 30 min late; check_out 18:00 (on time).
      emp_early25: check_in 09:05 (on time); check_out 17:20 -> 25 min early.
      emp_sam1/emp_sam2: BOTH named "Sam Late" (two different EmployeeProfile rows) — proves
        top_late is keyed by employee_id, not name. sam1 check_in 09:35 -> 20 min late;
        sam2 check_in 09:25 -> 10 min late. Both check_out 18:00 (on time).

    late_count=3 (late30, sam1, sam2); early_count=1 (early25); considered=5 (all 5 rows have
    both check_in and a shift). avg_late_min = mean(30, 20, 10) = 20; avg_early_min = 25.
    """
    from apps.hrm.models import AttendanceRecord
    d1 = today - datetime.timedelta(days=20)

    emp_ontime = _mk_employee(tenant_a, "On Time Emp", dept_a)
    emp_late30 = _mk_employee(tenant_a, "Late Thirty", dept_a)
    emp_early25 = _mk_employee(tenant_a, "Early TwentyFive", dept_a)
    emp_sam1 = _mk_employee(tenant_a, "Sam Late", dept_a)
    emp_sam2 = _mk_employee(tenant_a, "Sam Late", dept_a)

    def _rec(emp, check_in, check_out):
        return AttendanceRecord.objects.create(
            tenant=tenant_a, employee=emp, date=d1, shift=shift_a,
            check_in=check_in, check_out=check_out, status="present")

    _rec(emp_ontime, datetime.time(9, 10), datetime.time(18, 0))
    _rec(emp_late30, datetime.time(9, 45), datetime.time(18, 0))
    _rec(emp_early25, datetime.time(9, 5), datetime.time(17, 20))
    _rec(emp_sam1, datetime.time(9, 35), datetime.time(18, 0))
    _rec(emp_sam2, datetime.time(9, 25), datetime.time(18, 0))

    return {
        "date": d1, "date_from": d1, "date_to": d1,
        "emp_late30": emp_late30, "emp_sam1": emp_sam1, "emp_sam2": emp_sam2,
    }


@pytest.fixture
def ot_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """Hand-verified overtime dataset for tenant_a, all dated D = today-15:

      dept_a: ot1 APPROVED 4h@1.5x (pay 6.0), ot2 APPROVED 2h@2.0x (pay 4.0),
              ot4 REJECTED 10h@1.5x (excluded by default), ot5 DRAFT 8h@1.5x (excluded by
              default), dup1/dup2: TWO employees both named "Ollie OT" (proves by_employee is
              keyed on employee_id, not name) -- dup1 APPROVED 5h@1.5x (pay 7.5), dup2 APPROVED
              7h@1.5x (pay 10.5).
      dept_sales_a: ot3 PENDING 3h@1.5x (pay 4.5) -- pending is NOT excluded by default,
                    ot6 CANCELLED 6h@1.5x (excluded by default).

    DEFAULT (no ?status): rows = ot1, ot2, ot3, dup1, dup2 (5) -> total_hours=21.0,
      pay_equiv_hours=32.5, claims=5.
    ?status=approved: rows = ot1, ot2, dup1, dup2 (4) -> total_hours=18.0, pay_equiv_hours=28.0.
    status_rows (full pre-filter mix, regardless of ?status): approved=4, pending=1, rejected=1,
      draft=1, cancelled=1 (6 total).
    """
    from apps.hrm.models import OvertimeRequest
    d = today - datetime.timedelta(days=15)

    def _ot(emp, hours, mult, status):
        return OvertimeRequest.objects.create(
            tenant=tenant_a, employee=emp, date=d, hours_claimed=Decimal(str(hours)),
            multiplier=Decimal(str(mult)), payout_method="pay", reason="Release support",
            status=status)

    emp_alice = _mk_employee(tenant_a, "OT Alice", dept_a)
    emp_bob = _mk_employee(tenant_a, "OT Bob", dept_a)
    emp_cara = _mk_employee(tenant_a, "OT Cara", dept_sales_a)
    emp_dan = _mk_employee(tenant_a, "OT Dan", dept_a)
    emp_eve = _mk_employee(tenant_a, "OT Eve", dept_a)
    emp_finn = _mk_employee(tenant_a, "OT Finn", dept_sales_a)
    emp_dup1 = _mk_employee(tenant_a, "Ollie OT", dept_a)
    emp_dup2 = _mk_employee(tenant_a, "Ollie OT", dept_a)

    _ot(emp_alice, 4, "1.50", "approved")
    _ot(emp_bob, 2, "2.00", "approved")
    _ot(emp_cara, 3, "1.50", "pending")
    _ot(emp_dan, 10, "1.50", "rejected")
    _ot(emp_eve, 8, "1.50", "draft")
    _ot(emp_finn, 6, "1.50", "cancelled")
    _ot(emp_dup1, 5, "1.50", "approved")
    _ot(emp_dup2, 7, "1.50", "approved")

    return {
        "date": d, "date_from": d, "date_to": d,
        "emp_dup1": emp_dup1, "emp_dup2": emp_dup2,
    }


# ============================================================
# 1. Access control — the headline control, all five reports
# ============================================================

class TestAccessControl:
    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_anonymous_redirects_to_login(self, client, url_name):
        resp = client.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_non_admin_member_forbidden(self, member_client, url_name):
        resp = member_client.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 403

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_tenant_admin_ok(self, client_a, url_name):
        resp = client_a.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 200


# ============================================================
# 2. Rendering — never a 500, with no params / full filters / nonsense
# ============================================================

class TestRenderingNeverErrors:
    """Exercises every report with an empty tenant (client_a has no attendance/OT data unless a
    data fixture is requested) and with nonsensical query params, to prove the views never 500."""

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_no_params_200(self, client_a, url_name):
        resp = client_a.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_nonsensical_params_never_500(self, client_a, url_name):
        bad_params = {
            "date_from": "not-a-date", "date_to": "2000-01-01",
            "department": "abc", "status": "not_a_real_status",
        }
        resp = client_a.get(reverse(f"hrm:{url_name}"), bad_params)
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_far_future_dates_never_500(self, client_a, url_name):
        resp = client_a.get(reverse(f"hrm:{url_name}"),
                             {"date_from": "9999-01-01", "date_to": "9999-12-31"})
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", DATE_SCOPED_URL_NAMES)
    def test_reversed_date_range_clamped(self, client_a, today, url_name):
        future = today + datetime.timedelta(days=10)
        resp = client_a.get(reverse(f"hrm:{url_name}"), _qs(date_from=future, date_to=today))
        assert resp.status_code == 200
        assert resp.context["date_from"] == resp.context["date_to"] == today

    def test_attendance_summary_full_filter_set(self, client_a, att_data_a, dept_a):
        resp = client_a.get(reverse("hrm:attendance_summary_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"],
                                 department=dept_a.pk))
        assert resp.status_code == 200

    def test_late_early_full_filter_set(self, client_a, late_data_a, dept_a):
        resp = client_a.get(reverse("hrm:late_early_report"),
                             _qs(date_from=late_data_a["date_from"], date_to=late_data_a["date_to"],
                                 department=dept_a.pk))
        assert resp.status_code == 200

    def test_absenteeism_full_filter_set(self, client_a, att_data_a, dept_a):
        resp = client_a.get(reverse("hrm:absenteeism_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"],
                                 department=dept_a.pk))
        assert resp.status_code == 200

    def test_overtime_full_filter_set(self, client_a, ot_data_a, dept_a):
        resp = client_a.get(reverse("hrm:overtime_report"),
                             _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"],
                                 department=dept_a.pk, status="approved"))
        assert resp.status_code == 200


# ============================================================
# 3a. Attendance summary report — status mix, present-equivalent %, by-department, div-by-zero
# ============================================================

class TestAttendanceSummaryReport:
    def test_status_rows_and_totals_unfiltered(self, client_a, att_data_a):
        resp = client_a.get(reverse("hrm:attendance_summary_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"]))
        assert resp.context["total"] == 10
        assert resp.context["tracked"] == 8
        counts = {r["name"]: r["count"] for r in resp.context["status_rows"]}
        assert counts == {"Present": 3, "Absent": 3, "Half Day": 1, "Holiday": 1,
                           "On Leave": 1, "Regularized": 1}

    def test_attendance_pct_present_equivalent_formula(self, client_a, att_data_a):
        resp = client_a.get(reverse("hrm:attendance_summary_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"]))
        pe = 3 + 1 + 0.5 * 1  # present + regularized + 0.5*half_day
        tracked = 8
        expected_pct = round(pe / tracked * 100, 1)
        assert resp.context["attendance_pct"] == expected_pct

    def test_department_filter_scopes_totals(self, client_a, att_data_a, dept_a):
        resp = client_a.get(reverse("hrm:attendance_summary_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"],
                                 department=dept_a.pk))
        assert resp.context["total"] == 7  # emp_p1, emp_p2, emp_ab1 x2, emp_half, emp_holiday, emp_leave
        assert resp.context["tracked"] == 5  # 7 - holiday(1) - on_leave(1)
        pe = 2 + 0.5 * 1  # emp_p1, emp_p2 + half emp_half
        expected_pct = round(pe / 5 * 100, 1)
        assert resp.context["attendance_pct"] == expected_pct

    def test_by_department_breakdown(self, client_a, att_data_a, dept_a, dept_sales_a):
        resp = client_a.get(reverse("hrm:attendance_summary_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"]))
        by_dept = {r["name"]: r for r in resp.context["by_department"]}
        eng = by_dept["Engineering"]
        assert eng["tracked"] == 5
        assert eng["attendance_pct"] == round(2.5 / 5 * 100, 1)
        sales = by_dept["Sales"]
        assert sales["tracked"] == 3
        assert sales["attendance_pct"] == round(2 / 3 * 100, 1)

    def test_tracked_zero_guarded_not_a_crash(self, client_a, att_data_a, only_nonworking_data_a):
        resp = client_a.get(reverse("hrm:attendance_summary_report"),
                             _qs(date_from=only_nonworking_data_a["date"],
                                 date_to=only_nonworking_data_a["date"],
                                 department=only_nonworking_data_a["dept"].pk))
        assert resp.status_code == 200
        assert resp.context["tracked"] == 0
        assert resp.context["attendance_pct"] == 0.0


# ============================================================
# 3b. Late/early report — minute math against shift start/end + grace, top_late employee_id keying
# ============================================================

class TestLateEarlyReport:
    def test_considered_and_counts(self, client_a, late_data_a):
        resp = client_a.get(reverse("hrm:late_early_report"),
                             _qs(date_from=late_data_a["date_from"], date_to=late_data_a["date_to"]))
        assert resp.context["considered"] == 5
        assert resp.context["late_count"] == 3
        assert resp.context["early_count"] == 1

    def test_avg_late_and_early_minutes(self, client_a, late_data_a):
        resp = client_a.get(reverse("hrm:late_early_report"),
                             _qs(date_from=late_data_a["date_from"], date_to=late_data_a["date_to"]))
        assert resp.context["avg_late_min"] == round((30 + 20 + 10) / 3)
        assert resp.context["avg_early_min"] == 25

    def test_on_time_employee_not_counted_late(self, client_a, late_data_a):
        resp = client_a.get(reverse("hrm:late_early_report"),
                             _qs(date_from=late_data_a["date_from"], date_to=late_data_a["date_to"]))
        top_late_names = [r["name"] for r in resp.context["top_late"]]
        assert "On Time Emp" not in top_late_names
        assert "Early TwentyFive" not in top_late_names

    def test_top_late_keyed_by_employee_id_not_name(self, client_a, late_data_a):
        """The code-reviewer's fix: two employees who share the SAME party.name ("Sam Late") must
        appear as TWO distinct top_late rows (count=1 each), never merged into one row (count=2)."""
        resp = client_a.get(reverse("hrm:late_early_report"),
                             _qs(date_from=late_data_a["date_from"], date_to=late_data_a["date_to"]))
        sam_rows = [r for r in resp.context["top_late"] if r["name"] == "Sam Late"]
        assert len(sam_rows) == 2
        assert all(r["count"] == 1 for r in sam_rows)
        assert len(resp.context["top_late"]) == 3  # late30 + sam1 + sam2


# ============================================================
# 3c. Absenteeism report — absence rate, frequent absentees
# ============================================================

class TestAbsenteeismReport:
    def test_absent_days_tracked_and_rate(self, client_a, att_data_a):
        resp = client_a.get(reverse("hrm:absenteeism_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"]))
        assert resp.context["absent_days"] == 3
        assert resp.context["tracked"] == 8
        assert resp.context["absence_rate"] == round(3 / 8 * 100, 1)

    def test_frequent_absentees_sorted_by_count(self, client_a, att_data_a):
        resp = client_a.get(reverse("hrm:absenteeism_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"]))
        frequent = resp.context["frequent"]
        assert frequent[0] == {"name": "Absent One", "count": 2}
        names_counts = {r["name"]: r["count"] for r in frequent}
        assert names_counts["Absent Two"] == 1

    def test_department_filter_scopes_absence_rate(self, client_a, att_data_a, dept_a):
        resp = client_a.get(reverse("hrm:absenteeism_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"],
                                 department=dept_a.pk))
        assert resp.context["absent_days"] == 2  # emp_ab1 x2 only (emp_ab2 is Sales)
        assert resp.context["tracked"] == 5

    def test_tracked_zero_guarded_not_a_crash(self, client_a, only_nonworking_data_a):
        resp = client_a.get(reverse("hrm:absenteeism_report"),
                             _qs(date_from=only_nonworking_data_a["date"],
                                 date_to=only_nonworking_data_a["date"],
                                 department=only_nonworking_data_a["dept"].pk))
        assert resp.status_code == 200
        assert resp.context["tracked"] == 0
        assert resp.context["absence_rate"] == 0.0
        assert resp.context["frequent"] == []


# ============================================================
# 3d. Overtime report — default excludes draft/rejected/cancelled, ?status scoping, pay-equivalent
# ============================================================

class TestOvertimeReport:
    def test_default_excludes_draft_rejected_cancelled(self, client_a, ot_data_a):
        resp = client_a.get(reverse("hrm:overtime_report"),
                             _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"]))
        assert resp.context["claims"] == 5
        assert resp.context["total_hours"] == 21.0
        assert resp.context["pay_equiv_hours"] == 32.5

    def test_rejected_claim_not_counted_by_default(self, client_a, ot_data_a):
        """10h REJECTED claim must not inflate total_hours/pay_equiv_hours under the default
        (no ?status) view."""
        resp = client_a.get(reverse("hrm:overtime_report"),
                             _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"]))
        assert resp.context["total_hours"] < 21 + 10  # rejected 10h excluded
        by_emp_names = {r["name"] for r in resp.context["by_employee"]}
        assert "OT Dan" not in by_emp_names  # OT Dan's claim was rejected

    def test_status_approved_filter_scopes_totals(self, client_a, ot_data_a):
        resp = client_a.get(reverse("hrm:overtime_report"),
                             _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"],
                                 status="approved"))
        assert resp.context["claims"] == 4
        assert resp.context["total_hours"] == 18.0
        assert resp.context["pay_equiv_hours"] == 28.0

    def test_status_rows_reflect_full_mix_even_when_filtered(self, client_a, ot_data_a):
        """status_rows must show the FULL status distribution (computed from the pre-filter
        scope), even when ?status=approved narrows the headline figures."""
        resp = client_a.get(reverse("hrm:overtime_report"),
                             _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"],
                                 status="approved"))
        status_counts = {r["name"]: r["count"] for r in resp.context["status_rows"]}
        assert status_counts == {"Approved": 4, "Pending": 1, "Rejected": 1,
                                  "Draft": 1, "Cancelled": 1}

    def test_pay_equivalent_hours_is_hours_times_multiplier(self, client_a, ot_data_a):
        resp = client_a.get(reverse("hrm:overtime_report"),
                             _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"],
                                 status="approved"))
        # ot1 4h@1.5 + ot2 2h@2.0 + dup1 5h@1.5 + dup2 7h@1.5 = 6 + 4 + 7.5 + 10.5 = 28.0
        assert resp.context["pay_equiv_hours"] == 28.0

    def test_by_employee_keyed_by_employee_id_not_name(self, client_a, ot_data_a):
        """The code-reviewer's fix: two employees who share the SAME party.name ("Ollie OT") must
        appear as TWO distinct by_employee rows with their own hours, never merged into one."""
        resp = client_a.get(reverse("hrm:overtime_report"),
                             _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"]))
        ollie_rows = [r for r in resp.context["by_employee"] if r["name"] == "Ollie OT"]
        assert len(ollie_rows) == 2
        assert {r["hours"] for r in ollie_rows} == {5.0, 7.0}

    def test_by_department_scopes_hours(self, client_a, ot_data_a, dept_a, dept_sales_a):
        resp = client_a.get(reverse("hrm:overtime_report"),
                             _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"]))
        by_dept = {r["name"]: r["hours"] for r in resp.context["by_department"]}
        assert by_dept["Engineering"] == 18.0  # ot1(4) + ot2(2) + dup1(5) + dup2(7) — all dept_a
        assert by_dept["Sales"] == 3.0  # ot3(3), pending included by default


# ============================================================
# 4. Multi-tenant isolation / IDOR
# ============================================================

class TestMultiTenantIsolation:
    def test_attendance_summary_excludes_other_tenant(self, client_a, att_data_a, attendance_b):
        resp = client_a.get(reverse("hrm:attendance_summary_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"]))
        assert resp.context["total"] == 10  # attendance_b (tenant_b) never counted

    def test_overtime_excludes_other_tenant(self, client_a, ot_data_a, overtime_b):
        resp = client_a.get(reverse("hrm:overtime_report"),
                             _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"]))
        assert resp.context["claims"] == 5  # overtime_b (tenant_b, pending) never counted

    def test_cross_tenant_department_pk_ignored_on_summary(self, client_a, att_data_a, dept_b):
        resp = client_a.get(reverse("hrm:attendance_summary_report"),
                             _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"],
                                 department=dept_b.pk))
        assert resp.context["department"] is None
        assert resp.context["total"] == 10

    def test_cross_tenant_department_pk_ignored_on_overtime(self, client_a, ot_data_a, dept_b):
        resp = client_a.get(reverse("hrm:overtime_report"),
                             _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"],
                                 department=dept_b.pk))
        assert resp.context["department"] is None
        assert resp.context["claims"] == 5

    def test_tenant_b_admin_never_sees_tenant_a_attendance(self, client_b, att_data_a):
        resp = client_b.get(reverse("hrm:attendance_summary_report"))
        assert resp.context["total"] == 0

    def test_tenant_b_admin_never_sees_tenant_a_overtime(self, client_b, ot_data_a):
        resp = client_b.get(reverse("hrm:overtime_report"))
        assert resp.context["claims"] == 0


# ============================================================
# 5. Div-by-zero — a fully empty tenant renders every report at 200 with zero/None KPIs
# ============================================================

class TestEmptyTenantDivByZero:
    """client_a's tenant_a has no attendance/OT data at all unless a data fixture is explicitly
    requested — every one of the five reports must render 200 with safe zero/None defaults, never
    a ZeroDivisionError."""

    def test_attendance_reports_index_empty_tenant_tiles(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:attendance_reports_index"))
        assert resp.status_code == 200
        assert len(resp.context["tiles"]) == 5
        values = {t["label"]: t["value"] for t in resp.context["tiles"]}
        assert values["Attendance % (30d)"] == "0.0%"
        assert values["Absence % (30d)"] == "0.0%"

    def test_attendance_summary_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:attendance_summary_report"))
        assert resp.status_code == 200
        assert resp.context["total"] == 0
        assert resp.context["tracked"] == 0
        assert resp.context["attendance_pct"] == 0.0
        assert resp.context["status_rows"] == []
        assert resp.context["by_department"] == []

    def test_late_early_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:late_early_report"))
        assert resp.status_code == 200
        assert resp.context["considered"] == 0
        assert resp.context["late_count"] == 0
        assert resp.context["early_count"] == 0
        assert resp.context["avg_late_min"] is None
        assert resp.context["avg_early_min"] is None
        assert resp.context["top_late"] == []

    def test_absenteeism_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:absenteeism_report"))
        assert resp.status_code == 200
        assert resp.context["absent_days"] == 0
        assert resp.context["tracked"] == 0
        assert resp.context["absence_rate"] == 0.0
        assert resp.context["frequent"] == []

    def test_overtime_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:overtime_report"))
        assert resp.status_code == 200
        assert resp.context["claims"] == 0
        assert resp.context["total_hours"] == 0
        assert resp.context["pay_equiv_hours"] == 0
        assert resp.context["by_employee"] == []
        assert resp.context["status_rows"] == []

    def test_no_tenant_superuser_index_no_error(self, admin_user):
        """A tenant-less superuser (request.tenant is None) gets an empty tiles list, not a 500
        (mirrors the hr_reports_index / celebrations-view convention)."""
        from django.test import Client
        from apps.accounts.models import User
        superuser = User.objects.create_superuser(
            email="super_att@example.com", username="super_att", password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        resp = c.get(reverse("hrm:attendance_reports_index"))
        assert resp.status_code == 200
        assert resp.context["tiles"] == []


# ============================================================
# 6. Query-count ceilings (N+1 guard)
# ============================================================

class TestQueryCounts:
    def test_attendance_summary_report_query_count_bounded(self, client_a, att_data_a,
                                                            django_assert_max_num_queries):
        with django_assert_max_num_queries(25):
            client_a.get(reverse("hrm:attendance_summary_report"),
                         _qs(date_from=att_data_a["date_from"], date_to=att_data_a["date_to"]))

    def test_overtime_report_query_count_bounded(self, client_a, ot_data_a,
                                                 django_assert_max_num_queries):
        with django_assert_max_num_queries(25):
            client_a.get(reverse("hrm:overtime_report"),
                         _qs(date_from=ot_data_a["date_from"], date_to=ot_data_a["date_to"]))
