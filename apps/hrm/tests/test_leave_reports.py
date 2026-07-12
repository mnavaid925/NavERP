"""Tests for HRM 3.30 Leave Reports sub-module: derived, read-only report views (no models).

Mirrors ``test_attendance_reports.py`` (3.29) / ``test_hr_reports.py`` (3.28) — same fixture
style, access-control + aggregate-correctness + IDOR + div-by-zero + query-count structure.

Covers all five ``@tenant_admin_required`` views in ``apps/hrm/views.py``
(``leave_reports_index``, ``leave_register_report``, ``leave_liability_report``,
``comp_off_report``, ``leave_trend_report``), which reuse the 3.28 report helpers
(``_report_department``/``_dept_choices``) plus the 3.30-local ``_report_year``/``_leave_years``/
``_annotated_allocations``/``_alloc_balance``:

  - Access control: anonymous -> redirect, non-admin member -> 403, tenant admin -> 200.
  - Rendering never 500s: no params / a full filter set / nonsensical params (``?year=abc``,
    ``?department=abc``, reversed date range, far-future dates).
  - Aggregate correctness against hand-verified fixtures: register (allocated/carried/used/
    encashed/balance per row; ``used_db`` matches ``LeaveAllocation.used_days``; ``?year`` scopes
    to the right year's allocations; totals), liability (only encashable leave types, balance>0
    rows only; an APPROVED encashment's rate wins over a REJECTED one with a different rate; a
    CTC/365 estimate fallback when no encashment rate but an active salary structure exists; a row
    with neither falls back to a ``None`` value, not a crash), comp_off (earned from
    OvertimeRequest(payout_method="comp_leave", approved) only; availed from approved LeaveRequest
    against a comp-off LeaveType; ``comp_types_configured`` False -> empty availed; by_employee
    keyed by employee_id), trend (total_days/requests/by_type/monthly trend over approved
    LeaveRequest in range).
  - Multi-tenant isolation: another tenant's leave/OT data never leaks into totals; a cross-tenant
    ``?department=`` pk is ignored.
  - Div-by-zero / empty tenant: every report renders 200 with zero/None KPIs.
  - Query-count ceilings on leave_register_report/leave_liability_report against a bulk (15-row)
    dataset (N+1 guard — proves ``used_db``/encashment-rate/CTC lookups are NOT per-row).
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db

REPORT_URL_NAMES = [
    "leave_reports_index",
    "leave_register_report",
    "leave_liability_report",
    "comp_off_report",
    "leave_trend_report",
]

DATE_SCOPED_URL_NAMES = ["comp_off_report", "leave_trend_report"]


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


# ------------------------------------------------------------------ 3.30 register-report fixtures
@pytest.fixture
def leave_register_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """Hand-verified register dataset for tenant_a, year Y = today.year (plus one allocation in
    Y-1 for the "?year selects the right year" proof):

      lt_annual (encashable), lt_sick (not encashable).
      emp1 (Reg One, dept_a) / lt_annual / Y: allocated=21, carried=3, encashed=2.
        Leave requests: 5d APPROVED (Feb) -> counts; 2d PENDING (Mar) -> excluded;
        1d REJECTED (Apr) -> excluded. used_db = 5. balance = 21-5-2 = 14.
      emp1 / lt_annual / Y-1: allocated=15, no carry/encash. 4d APPROVED (Jun, Y-1) -> used_db=4,
        balance=11 (isolates the ``?year`` filter from the Y row).
      emp2 (Reg Two, dept_a) / lt_annual / Y: allocated=18. 3d APPROVED (May) -> used_db=3,
        balance=15.
      emp2 / lt_sick / Y: allocated=10, no requests -> used_db=0, balance=10.
      emp3 (Reg Three, dept_sales_a) / lt_annual / Y: allocated=20, carried=1, no requests ->
        used_db=0, balance=20.

    Unfiltered totals (Y, 4 rows): allocated=21+18+10+20=69, used=5+3+0+0=8, balance=14+15+10+20=59.
    dept_a-only (emp1/AL, emp2/AL, emp2/SL): allocated=49, used=8, balance=39.
    dept_sales_a-only (emp3/AL): allocated=20, used=0, balance=20.
    """
    from apps.hrm.models import LeaveType, LeaveAllocation, LeaveRequest
    Y = today.year
    Yp = Y - 1

    lt_annual = LeaveType.objects.create(
        tenant=tenant_a, name="Annual Leave", code="AL", encashable=True,
        accrual_rule="annual", accrual_days=Decimal("21"))
    lt_sick = LeaveType.objects.create(
        tenant=tenant_a, name="Sick Leave", code="SL", encashable=False,
        accrual_rule="monthly", accrual_days=Decimal("1"))

    emp1 = _mk_employee(tenant_a, "Reg One", dept_a)
    emp2 = _mk_employee(tenant_a, "Reg Two", dept_a)
    emp3 = _mk_employee(tenant_a, "Reg Three", dept_sales_a)

    alloc1 = LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp1, leave_type=lt_annual, year=Y,
        allocated_days=Decimal("21"), carried_forward=Decimal("3"), encashed_days=Decimal("2"))
    alloc2 = LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp2, leave_type=lt_annual, year=Y, allocated_days=Decimal("18"))
    alloc3 = LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp2, leave_type=lt_sick, year=Y, allocated_days=Decimal("10"))
    alloc4 = LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp3, leave_type=lt_annual, year=Y,
        allocated_days=Decimal("20"), carried_forward=Decimal("1"))
    alloc_prev = LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp1, leave_type=lt_annual, year=Yp, allocated_days=Decimal("15"))

    def _lr(emp, lt, start, end, status):
        return LeaveRequest.objects.create(
            tenant=tenant_a, employee=emp, leave_type=lt, start_date=start, end_date=end, status=status)

    _lr(emp1, lt_annual, datetime.date(Y, 2, 1), datetime.date(Y, 2, 5), "approved")   # 5d
    _lr(emp1, lt_annual, datetime.date(Y, 3, 1), datetime.date(Y, 3, 2), "pending")    # 2d, excluded
    _lr(emp1, lt_annual, datetime.date(Y, 4, 1), datetime.date(Y, 4, 1), "rejected")   # 1d, excluded
    _lr(emp2, lt_annual, datetime.date(Y, 5, 1), datetime.date(Y, 5, 3), "approved")   # 3d
    _lr(emp1, lt_annual, datetime.date(Yp, 6, 1), datetime.date(Yp, 6, 4), "approved")  # 4d, Yp

    return {
        "Y": Y, "Yp": Yp, "lt_annual": lt_annual, "lt_sick": lt_sick,
        "emp1": emp1, "emp2": emp2, "emp3": emp3,
        "alloc1": alloc1, "alloc2": alloc2, "alloc3": alloc3, "alloc4": alloc4,
        "alloc_prev": alloc_prev,
    }


# ------------------------------------------------------------------ 3.30 liability-report fixtures
@pytest.fixture
def liability_data_a(db, tenant_a, dept_a, today):
    """Hand-verified liability dataset for tenant_a, year Y = today.year:

      lt_annual (encashable), lt_sick (NOT encashable).
      emp_rate / lt_annual: allocated=20, balance=20. An APPROVED LeaveEncashment sets rate=100.00;
        a REJECTED encashment with a DIFFERENT rate (500.00) must be ignored. value = 20*100=2000.00,
        estimate=False.
      emp_ctc / lt_annual: allocated=10, balance=10. No encashment; an ACTIVE EmployeeSalaryStructure
        (annual_ctc_amount=73000.00) -> CTC/365 = 200.00 fallback rate. value=10*200=2000.00,
        estimate=True.
      emp_none / lt_annual: allocated=5, balance=5. No encashment, no salary structure -> rate=None,
        value=None (row still included — balance>0 — but with a None value, not a crash).
      emp_sick / lt_sick: allocated=8, balance=8 — EXCLUDED (leave_type not encashable).
      emp_zero / lt_annual: allocated=5, encashed=5, balance=0 — EXCLUDED (balance<=0).

    Totals: liability_days = 20+10+5 = 35. liability_value = 2000+2000 (None row contributes 0) =
    4000.00. is_estimate = True (emp_ctc's fallback).
    """
    from apps.hrm.models import LeaveType, LeaveAllocation, LeaveEncashment, EmployeeSalaryStructure
    Y = today.year

    lt_annual = LeaveType.objects.create(
        tenant=tenant_a, name="Annual Leave", code="AL", encashable=True,
        accrual_rule="annual", accrual_days=Decimal("21"))
    lt_sick = LeaveType.objects.create(
        tenant=tenant_a, name="Sick Leave", code="SL", encashable=False,
        accrual_rule="monthly", accrual_days=Decimal("1"))

    emp_rate = _mk_employee(tenant_a, "Liab Rate", dept_a)
    emp_ctc = _mk_employee(tenant_a, "Liab CTC", dept_a)
    emp_none = _mk_employee(tenant_a, "Liab None", dept_a)
    emp_sick = _mk_employee(tenant_a, "Liab Sick", dept_a)
    emp_zero = _mk_employee(tenant_a, "Liab Zero", dept_a)

    LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp_rate, leave_type=lt_annual, year=Y, allocated_days=Decimal("20"))
    LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp_ctc, leave_type=lt_annual, year=Y, allocated_days=Decimal("10"))
    LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp_none, leave_type=lt_annual, year=Y, allocated_days=Decimal("5"))
    LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp_sick, leave_type=lt_sick, year=Y, allocated_days=Decimal("8"))
    LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp_zero, leave_type=lt_annual, year=Y,
        allocated_days=Decimal("5"), encashed_days=Decimal("5"))

    LeaveEncashment.objects.create(
        tenant=tenant_a, employee=emp_rate, leave_type=lt_annual, year=Y,
        days=Decimal("2"), rate_per_day=Decimal("100.00"), status="approved")
    LeaveEncashment.objects.create(   # rejected, different rate — must be ignored
        tenant=tenant_a, employee=emp_rate, leave_type=lt_annual, year=Y,
        days=Decimal("1"), rate_per_day=Decimal("500.00"), status="rejected")

    EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=emp_ctc, annual_ctc_amount=Decimal("73000.00"), status="active")

    return {
        "Y": Y, "lt_annual": lt_annual, "lt_sick": lt_sick,
        "emp_rate": emp_rate, "emp_ctc": emp_ctc, "emp_none": emp_none,
        "emp_sick": emp_sick, "emp_zero": emp_zero,
    }


@pytest.fixture
def liability_no_estimate_data_a(db, tenant_a, dept_a, today):
    """A single encashable allocation with a real (non-fallback) encashment rate and NO
    EmployeeSalaryStructure anywhere in the tenant — proves ``is_estimate`` stays False when the
    rate never falls back to the CTC estimate."""
    from apps.hrm.models import LeaveType, LeaveAllocation, LeaveEncashment
    Y = today.year
    lt = LeaveType.objects.create(
        tenant=tenant_a, name="Annual Leave", code="AL", encashable=True,
        accrual_rule="annual", accrual_days=Decimal("21"))
    emp = _mk_employee(tenant_a, "Solo Rate", dept_a)
    LeaveAllocation.objects.create(
        tenant=tenant_a, employee=emp, leave_type=lt, year=Y, allocated_days=Decimal("12"))
    LeaveEncashment.objects.create(
        tenant=tenant_a, employee=emp, leave_type=lt, year=Y,
        days=Decimal("1"), rate_per_day=Decimal("50.00"), status="approved")
    return {"Y": Y, "emp": emp, "lt": lt}


# ------------------------------------------------------------------ 3.30 comp-off-report fixtures
@pytest.fixture
def comp_off_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """Hand-verified comp-off dataset for tenant_a, all dated D = today - 10 days:

      Earned (OvertimeRequest, payout_method="comp_leave", status="approved"):
        emp_a1 (CO Alice, dept_a): 4h. emp_b1 (CO Bob, dept_a): 6h.
        emp_dup1/emp_dup2 (BOTH "CO Dup", dept_a): 3h / 5h — proves by_employee keys on employee_id.
        emp_sales1 (CO Sales, dept_sales_a): 2h.
      Excluded: emp_a1 10h REJECTED comp_leave; emp_a1 8h APPROVED but payout_method="pay".

      Availed (LeaveRequest, status="approved", leave_type=lt_comp — code/name contains "comp"):
        emp_a1: 1 day (D..D). emp_b1: 2 days (D..D+1). Excluded: emp_a1 1d PENDING.

    Unfiltered (5 earned rows): earned_count=5, earned_hours=4+6+3+5+2=20.
    dept_a-only (4 rows): earned_count=4, earned_hours=18. dept_sales_a-only (1 row): count=1, hours=2.
    availed_count=2, availed_days=1+2=3.
    """
    from apps.hrm.models import LeaveType, LeaveRequest, OvertimeRequest
    d = today - datetime.timedelta(days=10)

    lt_comp = LeaveType.objects.create(
        tenant=tenant_a, name="Compensatory Off", code="COMP", encashable=False, accrual_rule="none")

    emp_a1 = _mk_employee(tenant_a, "CO Alice", dept_a)
    emp_b1 = _mk_employee(tenant_a, "CO Bob", dept_a)
    emp_dup1 = _mk_employee(tenant_a, "CO Dup", dept_a)
    emp_dup2 = _mk_employee(tenant_a, "CO Dup", dept_a)
    emp_sales1 = _mk_employee(tenant_a, "CO Sales", dept_sales_a)

    def _ot(emp, hours, method, status):
        return OvertimeRequest.objects.create(
            tenant=tenant_a, employee=emp, date=d, hours_claimed=Decimal(str(hours)),
            payout_method=method, reason="Weekend coverage", status=status)

    _ot(emp_a1, 4, "comp_leave", "approved")
    _ot(emp_b1, 6, "comp_leave", "approved")
    _ot(emp_a1, 10, "comp_leave", "rejected")   # excluded: not approved
    _ot(emp_a1, 8, "pay", "approved")           # excluded: wrong payout method
    _ot(emp_dup1, 3, "comp_leave", "approved")
    _ot(emp_dup2, 5, "comp_leave", "approved")
    _ot(emp_sales1, 2, "comp_leave", "approved")

    LeaveRequest.objects.create(
        tenant=tenant_a, employee=emp_a1, leave_type=lt_comp, start_date=d, end_date=d, status="approved")
    LeaveRequest.objects.create(
        tenant=tenant_a, employee=emp_b1, leave_type=lt_comp,
        start_date=d, end_date=d + datetime.timedelta(days=1), status="approved")
    LeaveRequest.objects.create(   # pending — excluded from availed
        tenant=tenant_a, employee=emp_a1, leave_type=lt_comp, start_date=d, end_date=d, status="pending")

    return {
        "date": d, "date_from": d, "date_to": d, "lt_comp": lt_comp,
        "emp_a1": emp_a1, "emp_b1": emp_b1, "emp_dup1": emp_dup1, "emp_dup2": emp_dup2,
    }


@pytest.fixture
def comp_off_no_comp_type_data_a(db, tenant_a, dept_a, today):
    """One earned comp-leave OT claim but NO LeaveType whose name/code contains "comp" — proves
    ``comp_types_configured`` is False and ``availed_*`` stays empty, while ``earned_*`` still
    reflects the OvertimeRequest (the two are independent)."""
    from apps.hrm.models import OvertimeRequest
    d = today - datetime.timedelta(days=5)
    emp = _mk_employee(tenant_a, "NoComp Emp", dept_a)
    OvertimeRequest.objects.create(
        tenant=tenant_a, employee=emp, date=d, hours_claimed=Decimal("4"),
        payout_method="comp_leave", reason="Coverage", status="approved")
    return {"date": d, "date_from": d, "date_to": d}


# ------------------------------------------------------------------ 3.30 trend-report fixtures
@pytest.fixture
def trend_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """Hand-verified trend dataset for tenant_a, year Y = today.year:

      lt_annual, lt_sick LeaveTypes.
      emp1 (Trend Alice, dept_a) / lt_annual: 3d APPROVED, start Feb 1.
      emp2 (Trend Bob, dept_sales_a) / lt_sick: 1d APPROVED, start Mar 1.
      emp1 / lt_annual: 1d PENDING (excluded).
      emp_dup1/emp_dup2 (BOTH "Trend Twin", dept_a) / lt_annual: 2d APPROVED (Feb 1) /
        4d APPROVED (Mar 1) — two DIFFERENT employees sharing one party.name.

    requests=4, total_days=3+1+2+4=10. by_type: Annual Leave=3+2+4=9d, Sick Leave=1d.
    Monthly: Feb=3+2=5d, Mar=1+4=5d.
    dept_a-only: emp1, emp_dup1, emp_dup2 -> requests=3, total_days=3+2+4=9.
    dept_sales_a-only: emp2 -> requests=1, total_days=1.
    """
    from apps.hrm.models import LeaveType, LeaveRequest
    Y = today.year

    lt_annual = LeaveType.objects.create(
        tenant=tenant_a, name="Annual Leave", code="AL", encashable=True,
        accrual_rule="annual", accrual_days=Decimal("21"))
    lt_sick = LeaveType.objects.create(
        tenant=tenant_a, name="Sick Leave", code="SL", encashable=False,
        accrual_rule="monthly", accrual_days=Decimal("1"))

    emp1 = _mk_employee(tenant_a, "Trend Alice", dept_a)
    emp2 = _mk_employee(tenant_a, "Trend Bob", dept_sales_a)
    emp_dup1 = _mk_employee(tenant_a, "Trend Twin", dept_a)
    emp_dup2 = _mk_employee(tenant_a, "Trend Twin", dept_a)

    d1 = datetime.date(Y, 2, 1)
    d2 = datetime.date(Y, 3, 1)

    def _lr(emp, lt, start, end, status="approved"):
        return LeaveRequest.objects.create(
            tenant=tenant_a, employee=emp, leave_type=lt, start_date=start, end_date=end, status=status)

    _lr(emp1, lt_annual, d1, d1 + datetime.timedelta(days=2))                       # 3d Feb
    _lr(emp2, lt_sick, d2, d2)                                                      # 1d Mar
    _lr(emp1, lt_annual, d1, d1, status="pending")                                  # excluded
    _lr(emp_dup1, lt_annual, d1, d1 + datetime.timedelta(days=1))                   # 2d Feb
    _lr(emp_dup2, lt_annual, d2, d2 + datetime.timedelta(days=3))                   # 4d Mar

    return {
        "date_from": datetime.date(Y, 1, 1), "date_to": datetime.date(Y, 12, 31),
        "lt_annual": lt_annual, "lt_sick": lt_sick,
        "emp1": emp1, "emp2": emp2, "emp_dup1": emp_dup1, "emp_dup2": emp_dup2,
    }


# ------------------------------------------------------------------ Cross-tenant (isolation) fixtures
@pytest.fixture
def leave_allocation_b(db, tenant_b, employee_b, leave_type_b, today):
    """A LeaveAllocation belonging to tenant_b (IDOR / isolation tests)."""
    from apps.hrm.models import LeaveAllocation
    return LeaveAllocation.objects.create(
        tenant=tenant_b, employee=employee_b, leave_type=leave_type_b,
        year=today.year, allocated_days=Decimal("15"))


@pytest.fixture
def leave_request_b_approved(db, tenant_b, employee_b, leave_type_b, today):
    """An APPROVED LeaveRequest belonging to tenant_b (IDOR / isolation tests)."""
    from apps.hrm.models import LeaveRequest
    d = datetime.date(today.year, 2, 1)
    return LeaveRequest.objects.create(
        tenant=tenant_b, employee=employee_b, leave_type=leave_type_b,
        start_date=d, end_date=d + datetime.timedelta(days=1), status="approved")


@pytest.fixture
def overtime_comp_b(db, tenant_b, employee_b, today):
    """An APPROVED, payout_method="comp_leave" OvertimeRequest belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import OvertimeRequest
    d = today - datetime.timedelta(days=10)
    return OvertimeRequest.objects.create(
        tenant=tenant_b, employee=employee_b, date=d, hours_claimed=Decimal("5"),
        payout_method="comp_leave", reason="B coverage", status="approved")


# ------------------------------------------------------------------ Bulk (N+1 guard) fixtures
@pytest.fixture
def leave_register_bulk_data_a(db, tenant_a, dept_a, today):
    """15 employees, each with one LeaveAllocation + one approved LeaveRequest against the same
    encashable LeaveType — big enough that a per-row (N+1) ``used_days`` query pattern would blow
    past a tight query-count ceiling, while the annotated (``_used_days_subquery``) implementation
    stays flat."""
    from apps.hrm.models import LeaveType, LeaveAllocation, LeaveRequest
    Y = today.year
    lt = LeaveType.objects.create(
        tenant=tenant_a, name="Annual Leave", code="AL", encashable=True,
        accrual_rule="annual", accrual_days=Decimal("21"))
    for i in range(15):
        emp = _mk_employee(tenant_a, f"Bulk Emp {i}", dept_a)
        LeaveAllocation.objects.create(
            tenant=tenant_a, employee=emp, leave_type=lt, year=Y, allocated_days=Decimal("20"))
        LeaveRequest.objects.create(
            tenant=tenant_a, employee=emp, leave_type=lt,
            start_date=datetime.date(Y, 2, 1), end_date=datetime.date(Y, 2, 2), status="approved")
    return {"Y": Y, "lt": lt}


@pytest.fixture
def liability_bulk_data_a(db, tenant_a, dept_a, today):
    """15 employees, each with one encashable LeaveAllocation with a positive balance and its own
    APPROVED LeaveEncashment rate — proves the enc_rates dict is built in ONE query, not per row."""
    from apps.hrm.models import LeaveType, LeaveAllocation, LeaveEncashment
    Y = today.year
    lt = LeaveType.objects.create(
        tenant=tenant_a, name="Annual Leave", code="AL", encashable=True,
        accrual_rule="annual", accrual_days=Decimal("21"))
    for i in range(15):
        emp = _mk_employee(tenant_a, f"Bulk Liab {i}", dept_a)
        LeaveAllocation.objects.create(
            tenant=tenant_a, employee=emp, leave_type=lt, year=Y, allocated_days=Decimal("10"))
        LeaveEncashment.objects.create(
            tenant=tenant_a, employee=emp, leave_type=lt, year=Y,
            days=Decimal("1"), rate_per_day=Decimal("50.00"), status="approved")
    return {"Y": Y, "lt": lt}


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
    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_no_params_200(self, client_a, url_name):
        resp = client_a.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_nonsensical_params_never_500(self, client_a, url_name):
        bad_params = {
            "year": "abc", "department": "abc", "date_from": "not-a-date",
            "date_to": "2000-01-01", "leave_type": "abc",
        }
        resp = client_a.get(reverse(f"hrm:{url_name}"), bad_params)
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_far_future_params_never_500(self, client_a, url_name):
        resp = client_a.get(reverse(f"hrm:{url_name}"),
                             {"year": "9999", "date_from": "9999-01-01", "date_to": "9999-12-31"})
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", DATE_SCOPED_URL_NAMES)
    def test_reversed_date_range_clamped(self, client_a, today, url_name):
        future = today + datetime.timedelta(days=10)
        resp = client_a.get(reverse(f"hrm:{url_name}"),
                             {"date_from": future.isoformat(), "date_to": today.isoformat()})
        assert resp.status_code == 200
        assert resp.context["date_from"] == resp.context["date_to"] == today

    def test_register_full_filter_set(self, client_a, leave_register_data_a, dept_a):
        resp = client_a.get(reverse("hrm:leave_register_report"),
                             {"year": leave_register_data_a["Y"], "department": dept_a.pk})
        assert resp.status_code == 200

    def test_liability_full_filter_set(self, client_a, liability_data_a, dept_a):
        resp = client_a.get(reverse("hrm:leave_liability_report"),
                             {"year": liability_data_a["Y"], "department": dept_a.pk})
        assert resp.status_code == 200

    def test_comp_off_full_filter_set(self, client_a, comp_off_data_a, dept_a):
        resp = client_a.get(reverse("hrm:comp_off_report"),
                             {"date_from": comp_off_data_a["date_from"].isoformat(),
                              "date_to": comp_off_data_a["date_to"].isoformat(), "department": dept_a.pk})
        assert resp.status_code == 200

    def test_trend_full_filter_set(self, client_a, trend_data_a, dept_a):
        resp = client_a.get(reverse("hrm:leave_trend_report"),
                             {"date_from": trend_data_a["date_from"].isoformat(),
                              "date_to": trend_data_a["date_to"].isoformat(), "department": dept_a.pk,
                              "leave_type": trend_data_a["lt_annual"].pk})
        assert resp.status_code == 200


# ============================================================
# 3a. Leave register report — allocated/carried/used/encashed/balance, year scoping, used_db proof
# ============================================================

class TestLeaveRegisterReport:
    def test_rows_and_totals_unfiltered(self, client_a, leave_register_data_a):
        data = leave_register_data_a
        resp = client_a.get(reverse("hrm:leave_register_report"), {"year": data["Y"]})
        rows = {(r["employee"], r["leave_type"]): r for r in resp.context["rows"]}
        assert len(rows) == 4

        r1 = rows[("Reg One", "Annual Leave")]
        assert r1["allocated"] == Decimal("21")
        assert r1["carried"] == Decimal("3")
        assert r1["used"] == Decimal("5")
        assert r1["encashed"] == Decimal("2")
        assert r1["balance"] == Decimal("14")

        r2 = rows[("Reg Two", "Annual Leave")]
        assert r2["used"] == Decimal("3")
        assert r2["balance"] == Decimal("15")

        r3 = rows[("Reg Two", "Sick Leave")]
        assert r3["used"] == Decimal("0")
        assert r3["balance"] == Decimal("10")

        r4 = rows[("Reg Three", "Annual Leave")]
        assert r4["carried"] == Decimal("1")
        assert r4["used"] == Decimal("0")
        assert r4["balance"] == Decimal("20")

        totals = resp.context["totals"]
        assert totals["allocated"] == 69.0
        assert totals["used"] == 8.0
        assert totals["balance"] == 59.0

    def test_year_param_selects_right_years_allocations(self, client_a, leave_register_data_a):
        data = leave_register_data_a
        resp = client_a.get(reverse("hrm:leave_register_report"), {"year": data["Yp"]})
        rows = resp.context["rows"]
        assert len(rows) == 1
        assert rows[0]["employee"] == "Reg One"
        assert rows[0]["allocated"] == Decimal("15")
        assert rows[0]["used"] == Decimal("4")
        assert rows[0]["balance"] == Decimal("11")

    def test_used_db_matches_used_days_property(self, client_a, leave_register_data_a):
        from apps.hrm.models import LeaveAllocation
        data = leave_register_data_a
        resp = client_a.get(reverse("hrm:leave_register_report"), {"year": data["Y"]})
        fresh = LeaveAllocation.objects.get(pk=data["alloc1"].pk)
        row = next(r for r in resp.context["rows"]
                   if r["employee"] == "Reg One" and r["leave_type"] == "Annual Leave")
        assert row["used"] == fresh.used_days == Decimal("5")

    def test_department_filter_scopes_totals(self, client_a, leave_register_data_a, dept_a, dept_sales_a):
        data = leave_register_data_a
        resp = client_a.get(reverse("hrm:leave_register_report"),
                             {"year": data["Y"], "department": dept_a.pk})
        assert len(resp.context["rows"]) == 3
        totals = resp.context["totals"]
        assert totals["allocated"] == 49.0
        assert totals["used"] == 8.0
        assert totals["balance"] == 39.0

        resp2 = client_a.get(reverse("hrm:leave_register_report"),
                              {"year": data["Y"], "department": dept_sales_a.pk})
        assert len(resp2.context["rows"]) == 1
        assert resp2.context["totals"]["allocated"] == 20.0

    def test_no_year_param_defaults_to_current_year(self, client_a, leave_register_data_a, today):
        resp = client_a.get(reverse("hrm:leave_register_report"))
        assert resp.context["year"] == today.year


# ============================================================
# 3b. Leave liability report — encashable-only, balance>0-only, rate priority, CTC estimate
# ============================================================

class TestLeaveLiabilityReport:
    def test_only_encashable_and_positive_balance_rows(self, client_a, liability_data_a):
        data = liability_data_a
        resp = client_a.get(reverse("hrm:leave_liability_report"), {"year": data["Y"]})
        names = {r["employee"] for r in resp.context["rows"]}
        assert names == {"Liab Rate", "Liab CTC", "Liab None"}
        assert "Liab Sick" not in names   # non-encashable leave type
        assert "Liab Zero" not in names   # balance <= 0

    def test_approved_encashment_rate_wins_over_rejected(self, client_a, liability_data_a):
        data = liability_data_a
        resp = client_a.get(reverse("hrm:leave_liability_report"), {"year": data["Y"]})
        row = next(r for r in resp.context["rows"] if r["employee"] == "Liab Rate")
        assert row["rate"] == Decimal("100.00")   # NOT the rejected 500.00
        assert row["value"] == Decimal("2000.00")
        assert row["estimate"] is False

    def test_ctc_fallback_estimate_when_no_encashment_rate(self, client_a, liability_data_a):
        data = liability_data_a
        resp = client_a.get(reverse("hrm:leave_liability_report"), {"year": data["Y"]})
        row = next(r for r in resp.context["rows"] if r["employee"] == "Liab CTC")
        assert row["rate"] == Decimal("200.00")   # 73000.00 / 365
        assert row["value"] == Decimal("2000.00")
        assert row["estimate"] is True
        assert resp.context["is_estimate"] is True

    def test_no_rate_no_ctc_value_none_not_a_crash(self, client_a, liability_data_a):
        data = liability_data_a
        resp = client_a.get(reverse("hrm:leave_liability_report"), {"year": data["Y"]})
        row = next(r for r in resp.context["rows"] if r["employee"] == "Liab None")
        assert row["rate"] is None
        assert row["value"] is None
        assert row["estimate"] is False

    def test_liability_totals(self, client_a, liability_data_a):
        data = liability_data_a
        resp = client_a.get(reverse("hrm:leave_liability_report"), {"year": data["Y"]})
        assert resp.context["liability_days"] == 35.0
        assert resp.context["liability_value"] == 4000.0

    def test_is_estimate_false_when_no_fallback_used(self, client_a, liability_no_estimate_data_a):
        data = liability_no_estimate_data_a
        resp = client_a.get(reverse("hrm:leave_liability_report"), {"year": data["Y"]})
        assert resp.context["is_estimate"] is False
        row = resp.context["rows"][0]
        assert row["rate"] == Decimal("50.00")
        assert row["value"] == Decimal("600.00")   # balance 12 * rate 50

    def test_department_filter_scopes_rows(self, client_a, liability_data_a, dept_a):
        data = liability_data_a
        resp = client_a.get(reverse("hrm:leave_liability_report"),
                             {"year": data["Y"], "department": dept_a.pk})
        assert len(resp.context["rows"]) == 3   # all liability_data_a employees are in dept_a


# ============================================================
# 3c. Comp-off report — earned vs availed, comp_types_configured, employee_id keying
# ============================================================

class TestCompOffReport:
    def test_earned_hours_and_count_unfiltered(self, client_a, comp_off_data_a):
        data = comp_off_data_a
        resp = client_a.get(reverse("hrm:comp_off_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        assert resp.context["earned_count"] == 5
        assert resp.context["earned_hours"] == 20.0

    def test_rejected_and_wrong_payout_method_excluded(self, client_a, comp_off_data_a):
        data = comp_off_data_a
        resp = client_a.get(reverse("hrm:comp_off_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        assert resp.context["earned_hours"] < 20 + 10 + 8  # rejected(10h)/pay(8h) not counted

    def test_department_filter_scopes_earned(self, client_a, comp_off_data_a, dept_a, dept_sales_a):
        data = comp_off_data_a
        resp = client_a.get(reverse("hrm:comp_off_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat(),
                              "department": dept_a.pk})
        assert resp.context["earned_count"] == 4
        assert resp.context["earned_hours"] == 18.0

        resp2 = client_a.get(reverse("hrm:comp_off_report"),
                              {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat(),
                               "department": dept_sales_a.pk})
        assert resp2.context["earned_count"] == 1
        assert resp2.context["earned_hours"] == 2.0

    def test_availed_from_comp_leave_type_only(self, client_a, comp_off_data_a):
        data = comp_off_data_a
        resp = client_a.get(reverse("hrm:comp_off_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        assert resp.context["comp_types_configured"] is True
        assert resp.context["availed_count"] == 2
        assert resp.context["availed_days"] == 3.0

    def test_comp_types_not_configured_empty_availed(self, client_a, comp_off_no_comp_type_data_a):
        data = comp_off_no_comp_type_data_a
        resp = client_a.get(reverse("hrm:comp_off_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        assert resp.context["comp_types_configured"] is False
        assert resp.context["availed_count"] == 0
        assert resp.context["availed_days"] == 0
        # earned is independent of comp-type configuration
        assert resp.context["earned_count"] == 1
        assert resp.context["earned_hours"] == 4.0

    def test_by_employee_keyed_by_employee_id_not_name(self, client_a, comp_off_data_a):
        """Two employees sharing the SAME party.name ("CO Dup") must appear as TWO distinct
        by_employee rows with their own hours, never merged into one (mirrors the fixed
        overtime_report.by_employee / late_early_report.top_late pattern)."""
        data = comp_off_data_a
        resp = client_a.get(reverse("hrm:comp_off_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        dup_rows = [r for r in resp.context["by_employee"] if r["name"] == "CO Dup"]
        assert len(dup_rows) == 2
        assert {r["hours"] for r in dup_rows} == {3.0, 5.0}


# ============================================================
# 3d. Leave trend report — total_days/requests, by_type, monthly buckets, top_takers
# ============================================================

class TestLeaveTrendReport:
    def test_requests_and_total_days(self, client_a, trend_data_a):
        data = trend_data_a
        resp = client_a.get(reverse("hrm:leave_trend_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        assert resp.context["requests"] == 4
        assert resp.context["total_days"] == 10.0

    def test_by_type_breakdown(self, client_a, trend_data_a):
        data = trend_data_a
        resp = client_a.get(reverse("hrm:leave_trend_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        by_type = {r["name"]: r["days"] for r in resp.context["by_type"]}
        assert by_type == {"Annual Leave": 9.0, "Sick Leave": 1.0}

    def test_monthly_trend_buckets_by_start_date_month(self, client_a, trend_data_a):
        data = trend_data_a
        resp = client_a.get(reverse("hrm:leave_trend_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        import json
        values = json.loads(resp.context["trend_values"])
        assert values == [5.0, 5.0]   # Feb=3+2, Mar=1+4

    def test_department_filter_scopes_totals(self, client_a, trend_data_a, dept_a, dept_sales_a):
        data = trend_data_a
        resp = client_a.get(reverse("hrm:leave_trend_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat(),
                              "department": dept_a.pk})
        assert resp.context["requests"] == 3
        assert resp.context["total_days"] == 9.0

        resp2 = client_a.get(reverse("hrm:leave_trend_report"),
                              {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat(),
                               "department": dept_sales_a.pk})
        assert resp2.context["requests"] == 1
        assert resp2.context["total_days"] == 1.0

    def test_leave_type_filter_scopes_totals(self, client_a, trend_data_a):
        data = trend_data_a
        resp = client_a.get(reverse("hrm:leave_trend_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat(),
                              "leave_type": data["lt_sick"].pk})
        assert resp.context["requests"] == 1
        assert resp.context["total_days"] == 1.0

    def test_pending_request_excluded(self, client_a, trend_data_a):
        data = trend_data_a
        resp = client_a.get(reverse("hrm:leave_trend_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        assert resp.context["requests"] == 4   # the 1d PENDING request for emp1 is excluded

    def test_top_takers_keyed_by_employee_id_not_name(self, client_a, trend_data_a):
        """Two DIFFERENT employees who share the same party.name ("Trend Twin", 2d + 4d) must stay
        as two distinct 2d/4d rows rather than being merged into a single 6d row. leave_trend_report
        keys top_takers on employee_id (like overtime_report.by_employee / late_early_report.top_late
        / comp_off_report.by_employee), so same-named employees are counted separately."""
        data = trend_data_a
        resp = client_a.get(reverse("hrm:leave_trend_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        twin_rows = [r for r in resp.context["top_takers"] if r["name"] == "Trend Twin"]
        assert len(twin_rows) == 2
        assert {r["days"] for r in twin_rows} == {2.0, 4.0}


# ============================================================
# 4. Multi-tenant isolation / IDOR
# ============================================================

class TestMultiTenantIsolation:
    def test_register_excludes_other_tenant(self, client_a, leave_register_data_a, leave_allocation_b):
        data = leave_register_data_a
        resp = client_a.get(reverse("hrm:leave_register_report"), {"year": data["Y"]})
        assert len(resp.context["rows"]) == 4   # leave_allocation_b (tenant_b) never counted

    def test_liability_excludes_other_tenant(self, client_a, liability_data_a, leave_allocation_b):
        data = liability_data_a
        resp = client_a.get(reverse("hrm:leave_liability_report"), {"year": data["Y"]})
        assert len(resp.context["rows"]) == 3   # tenant_b's allocation never counted

    def test_comp_off_excludes_other_tenant(self, client_a, comp_off_data_a, overtime_comp_b):
        data = comp_off_data_a
        resp = client_a.get(reverse("hrm:comp_off_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        assert resp.context["earned_count"] == 5   # overtime_comp_b (tenant_b) never counted

    def test_trend_excludes_other_tenant(self, client_a, trend_data_a, leave_request_b_approved):
        data = trend_data_a
        resp = client_a.get(reverse("hrm:leave_trend_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat()})
        assert resp.context["requests"] == 4   # leave_request_b_approved (tenant_b) never counted

    def test_cross_tenant_department_pk_ignored_on_register(self, client_a, leave_register_data_a, dept_b):
        data = leave_register_data_a
        resp = client_a.get(reverse("hrm:leave_register_report"),
                             {"year": data["Y"], "department": dept_b.pk})
        assert resp.context["department"] is None
        assert len(resp.context["rows"]) == 4

    def test_cross_tenant_department_pk_ignored_on_trend(self, client_a, trend_data_a, dept_b):
        data = trend_data_a
        resp = client_a.get(reverse("hrm:leave_trend_report"),
                             {"date_from": data["date_from"].isoformat(), "date_to": data["date_to"].isoformat(),
                              "department": dept_b.pk})
        assert resp.context["department"] is None
        assert resp.context["requests"] == 4

    def test_tenant_b_admin_never_sees_tenant_a_register(self, client_b, leave_register_data_a):
        resp = client_b.get(reverse("hrm:leave_register_report"),
                             {"year": leave_register_data_a["Y"]})
        assert resp.context["rows"] == []

    def test_tenant_b_admin_never_sees_tenant_a_trend(self, client_b, trend_data_a):
        resp = client_b.get(reverse("hrm:leave_trend_report"))
        assert resp.context["requests"] == 0


# ============================================================
# 5. Div-by-zero — a fully empty tenant renders every report at 200 with zero/None KPIs
# ============================================================

class TestEmptyTenantDivByZero:
    def test_leave_reports_index_empty_tenant_tiles(self, client_a, tenant_a, today):
        resp = client_a.get(reverse("hrm:leave_reports_index"))
        assert resp.status_code == 200
        assert len(resp.context["tiles"]) == 5
        values = {t["label"]: t["value"] for t in resp.context["tiles"]}
        assert values[f"Allocated ({today.year})"] == "0.0d"
        assert values[f"Availed ({today.year})"] == "0.0d"
        assert values["On Leave Today"] == 0
        assert values["Pending Requests"] == 0

    def test_register_zero_kpis(self, client_a, tenant_a, today):
        resp = client_a.get(reverse("hrm:leave_register_report"))
        assert resp.status_code == 200
        assert resp.context["rows"] == []
        assert resp.context["totals"] == {"allocated": 0, "used": 0, "balance": 0}
        assert resp.context["year_choices"] == [today.year]

    def test_liability_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:leave_liability_report"))
        assert resp.status_code == 200
        assert resp.context["rows"] == []
        assert resp.context["liability_days"] == 0
        assert resp.context["liability_value"] == 0
        assert resp.context["is_estimate"] is False

    def test_comp_off_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:comp_off_report"))
        assert resp.status_code == 200
        assert resp.context["earned_hours"] == 0
        assert resp.context["earned_count"] == 0
        assert resp.context["availed_days"] == 0
        assert resp.context["availed_count"] == 0
        assert resp.context["by_employee"] == []
        assert resp.context["comp_types_configured"] is False

    def test_trend_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:leave_trend_report"))
        assert resp.status_code == 200
        assert resp.context["total_days"] == 0
        assert resp.context["requests"] == 0
        assert resp.context["by_type"] == []
        assert resp.context["top_takers"] == []

    def test_no_tenant_superuser_index_no_error(self, admin_user):
        """A tenant-less superuser (request.tenant is None) gets an empty tiles list, not a 500
        (mirrors the hr_reports_index / attendance_reports_index convention)."""
        from django.test import Client
        from apps.accounts.models import User
        superuser = User.objects.create_superuser(
            email="super_leave@example.com", username="super_leave", password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        resp = c.get(reverse("hrm:leave_reports_index"))
        assert resp.status_code == 200
        assert resp.context["tiles"] == []


# ============================================================
# 6. Query-count ceilings (N+1 guard) — a 15-row bulk dataset
# ============================================================

class TestQueryCounts:
    def test_leave_register_report_query_count_bounded(self, client_a, leave_register_bulk_data_a,
                                                        django_assert_max_num_queries):
        """15 allocations/requests — a per-row ``used_days`` N+1 pattern would push this well past
        20 queries; the annotated (``_used_days_subquery``) implementation stays flat."""
        with django_assert_max_num_queries(20):
            client_a.get(reverse("hrm:leave_register_report"),
                         {"year": leave_register_bulk_data_a["Y"]})

    def test_leave_liability_report_query_count_bounded(self, client_a, liability_bulk_data_a,
                                                         django_assert_max_num_queries):
        """15 allocations with their own encashment rate — a per-row rate lookup would push this
        well past 20 queries; the batched ``enc_rates``/``ctc`` dicts stay flat."""
        with django_assert_max_num_queries(20):
            client_a.get(reverse("hrm:leave_liability_report"),
                         {"year": liability_bulk_data_a["Y"]})
