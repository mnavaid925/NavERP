"""Tests for HRM 3.28 HR Reports sub-module: derived, read-only report views (no models).

Covers all six ``@tenant_admin_required`` views in ``apps/hrm/views.py``
(``hr_reports_index``, ``headcount_report``, ``attrition_report``, ``diversity_report``,
``cost_report``, ``hiring_report``):

  - Access control: anonymous -> redirect, non-admin member -> 403, tenant admin -> 200
    (the headline control, tested for all six).
  - Rendering never 500s: no params / a full filter set / nonsensical params (reversed date
    range, non-digit department, far-future as_of, unknown cycle pk).
  - Aggregate correctness against hand-verified fixtures: headcount (active/joins/exits/
    by_designation budget+variance), attrition (SHRM turnover formula, voluntary/involuntary
    split), diversity (gender/age/tenure bucketing, avg_age None guard), cost (total/employer
    cost/by_component department scoping — the code-reviewer's fix; the no-cycle CTC/12
    estimate fallback), hiring (date-range-scoped hired set, offer-acceptance, funnel %).
  - Multi-tenant isolation: another tenant's data never leaks into totals; a cross-tenant
    ``?department=`` pk is ignored (falls back to "all", not empty).
  - Div-by-zero: an empty tenant renders every report at 200 with zero/None KPIs.
  - Query-count ceilings on headcount_report/cost_report (N+1 guard).
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db

REPORT_URL_NAMES = [
    "hr_reports_index",
    "headcount_report",
    "attrition_report",
    "diversity_report",
    "cost_report",
    "hiring_report",
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
def req_b(db, tenant_b):
    """A draft JobRequisition for tenant_b (isolation tests — mirrors test_recruitment.py)."""
    from apps.hrm.models import JobRequisition
    return JobRequisition.objects.create(
        tenant=tenant_b, title="Analyst B", headcount=1, req_type="standard",
        employment_type="full_time", reason_for_hire="new_headcount",
        posting_type="external", priority="low")


def _mk_employee(tenant, party_name, dept, designation=None, *, hired_on, gender="", dob=None,
                  employee_type="full_time", status="active"):
    """Build a Party + core.Employment + hrm.EmployeeProfile with fully-controlled attributes
    (the conftest employee_a/employee_a2 fixtures pin hired_on to a fixed 2023 date, which is
    unusable for "trailing window" report math — these need offsets relative to ``today``)."""
    from apps.core.models import Party, Employment
    from apps.hrm.models import EmployeeProfile
    party = Party.objects.create(tenant=tenant, kind="person", name=party_name)
    employment = Employment.objects.create(
        tenant=tenant, party=party, org_unit=dept, job_title="Staff",
        hired_on=hired_on, status=status,
    )
    return EmployeeProfile.objects.create(
        tenant=tenant, party=party, employment=employment, designation=designation,
        employee_type=employee_type, gender=gender, date_of_birth=dob,
    )


@pytest.fixture
def hc_data_a(db, tenant_a, dept_a, dept_sales_a, designation_a, today):
    """Hand-verified headcount/attrition/diversity dataset for tenant_a, window
    [today-100, today]:

      ACTIVE (4): e1 (dept_a/Engineering, designation_a, female, age 35, hired -500d — before
      the window), e2 (dept_a, designation_a, male, age 28, hired -50d — a JOIN), e3 (dept_sales/
      Sales, no designation, contract, hired -600d), e7 (dept_sales, hired -30d — a JOIN, so
      department-filtering demonstrably changes the join count: 2 unfiltered vs 1 for dept_a).

      TERMINATED + SeparationCase (3): e4 (resignation/voluntary, LWD -20d — IN window), e5
      (termination/involuntary, LWD -40d — IN window), e6 (layoff/involuntary, LWD -150d —
      OUTSIDE the window, proves date-range exclusion).

      designation_a.budgeted_headcount is set to 3 (active count on it is 2 -> variance -1).
    """
    from apps.hrm.models import SeparationCase
    designation_a.budgeted_headcount = 3
    designation_a.save(update_fields=["budgeted_headcount"])

    e1 = _mk_employee(tenant_a, "Alice Active", dept_a, designation_a,
                       hired_on=today - datetime.timedelta(days=500),
                       gender="female", dob=today.replace(year=today.year - 35))
    e2 = _mk_employee(tenant_a, "Ben Active", dept_a, designation_a,
                       hired_on=today - datetime.timedelta(days=50),
                       gender="male", dob=today.replace(year=today.year - 28))
    e3 = _mk_employee(tenant_a, "Cara Sales", dept_sales_a, None,
                       hired_on=today - datetime.timedelta(days=600),
                       employee_type="contract")
    e7 = _mk_employee(tenant_a, "Gita Sales", dept_sales_a, None,
                       hired_on=today - datetime.timedelta(days=30))
    e4 = _mk_employee(tenant_a, "Dan Departed", dept_a, designation_a,
                       hired_on=today - datetime.timedelta(days=400), status="terminated")
    e5 = _mk_employee(tenant_a, "Eve Departed", dept_a, designation_a,
                       hired_on=today - datetime.timedelta(days=380), status="terminated")
    e6 = _mk_employee(tenant_a, "Finn Departed", dept_a, designation_a,
                       hired_on=today - datetime.timedelta(days=450), status="terminated")

    sep4 = SeparationCase.objects.create(
        tenant=tenant_a, employee=e4, separation_type="resignation", exit_reason="better_opportunity",
        actual_last_working_day=today - datetime.timedelta(days=20))
    sep5 = SeparationCase.objects.create(
        tenant=tenant_a, employee=e5, separation_type="termination", exit_reason="performance",
        actual_last_working_day=today - datetime.timedelta(days=40))
    sep6 = SeparationCase.objects.create(
        tenant=tenant_a, employee=e6, separation_type="layoff", exit_reason="other",
        actual_last_working_day=today - datetime.timedelta(days=150))

    return {
        "e1": e1, "e2": e2, "e3": e3, "e7": e7, "e4": e4, "e5": e5, "e6": e6,
        "sep4": sep4, "sep5": sep5, "sep6": sep6,
        "date_from": today - datetime.timedelta(days=100), "date_to": today,
    }


@pytest.fixture
def payroll_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """Two employees on two different fixed-amount salary templates in two different
    departments, both payslipped in the SAME PayrollCycle — an "Engineering" employee
    (Basic 60000/yr, PF-EE 1200/yr, PF-ER 1200/yr) and a "Sales" employee (Basic 36000/yr,
    PF-EE 720/yr, PF-ER 720/yr). Hand-verified totals:

      unfiltered:  total_cost=8000.00, headcount=2, avg=4000.00, employer_cost=160.00,
                   by_component: earning=8000.00, statutory_deduction=320.00
      department=dept_a: total_cost=5000.00, headcount=1, avg=5000.00, employer_cost=100.00,
                   by_component: earning=5000.00, statutory_deduction=200.00
    """
    from apps.hrm.models import (PayComponent, SalaryStructureTemplate, SalaryStructureLine,
                                  EmployeeSalaryStructure, PayrollCycle, Payslip)

    tmpl_eng = SalaryStructureTemplate.objects.create(
        tenant=tenant_a, name="Engineering Structure", annual_ctc_amount=Decimal("62400"))
    basic_eng = PayComponent.objects.create(
        tenant=tenant_a, name="Basic Pay Eng", component_type="earning",
        calculation_type="fixed_amount", default_amount=Decimal("60000"))
    pf_ee_eng = PayComponent.objects.create(
        tenant=tenant_a, name="PF EE Eng", component_type="statutory_deduction",
        calculation_type="fixed_amount", default_amount=Decimal("1200"), contribution_side="employee")
    pf_er_eng = PayComponent.objects.create(
        tenant=tenant_a, name="PF ER Eng", component_type="statutory_deduction",
        calculation_type="fixed_amount", default_amount=Decimal("1200"), contribution_side="employer")
    SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl_eng, pay_component=basic_eng,
                                        amount=Decimal("60000"))
    SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl_eng, pay_component=pf_ee_eng,
                                        amount=Decimal("1200"))
    SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl_eng, pay_component=pf_er_eng,
                                        amount=Decimal("1200"))

    tmpl_sales = SalaryStructureTemplate.objects.create(
        tenant=tenant_a, name="Sales Structure", annual_ctc_amount=Decimal("36720"))
    basic_sales = PayComponent.objects.create(
        tenant=tenant_a, name="Basic Pay Sales", component_type="earning",
        calculation_type="fixed_amount", default_amount=Decimal("36000"))
    pf_ee_sales = PayComponent.objects.create(
        tenant=tenant_a, name="PF EE Sales", component_type="statutory_deduction",
        calculation_type="fixed_amount", default_amount=Decimal("720"), contribution_side="employee")
    pf_er_sales = PayComponent.objects.create(
        tenant=tenant_a, name="PF ER Sales", component_type="statutory_deduction",
        calculation_type="fixed_amount", default_amount=Decimal("720"), contribution_side="employer")
    SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl_sales, pay_component=basic_sales,
                                        amount=Decimal("36000"))
    SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl_sales, pay_component=pf_ee_sales,
                                        amount=Decimal("720"))
    SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl_sales, pay_component=pf_er_sales,
                                        amount=Decimal("720"))

    emp_eng = _mk_employee(tenant_a, "Pay Eng", dept_a, None, hired_on=today - datetime.timedelta(days=400))
    emp_sales = _mk_employee(tenant_a, "Pay Sales", dept_sales_a, None,
                              hired_on=today - datetime.timedelta(days=400))

    ess_eng = EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=emp_eng, template=tmpl_eng,
        annual_ctc_amount=Decimal("62400"), status="active")
    ess_sales = EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=emp_sales, template=tmpl_sales,
        annual_ctc_amount=Decimal("36720"), status="active")

    cycle = PayrollCycle.objects.create(
        tenant=tenant_a, period_start=today - datetime.timedelta(days=30), period_end=today,
        pay_date=today, cycle_type="regular", status="draft")

    ps_eng = Payslip.objects.create(tenant=tenant_a, cycle=cycle, employee=emp_eng,
                                     salary_structure=ess_eng, days_in_period=30, days_worked=30)
    ps_eng.recompute()
    ps_sales = Payslip.objects.create(tenant=tenant_a, cycle=cycle, employee=emp_sales,
                                       salary_structure=ess_sales, days_in_period=30, days_worked=30)
    ps_sales.recompute()

    return {"cycle": cycle, "emp_eng": emp_eng, "emp_sales": emp_sales,
            "ps_eng": ps_eng, "ps_sales": ps_sales}


@pytest.fixture
def estimate_salary_a(db, tenant_a, dept_a, today):
    """An active EmployeeSalaryStructure with NO PayrollCycle at all — exercises cost_report's
    is_estimate fallback path (annual CTC / 12)."""
    from apps.hrm.models import EmployeeSalaryStructure
    emp = _mk_employee(tenant_a, "Estimate Emp", dept_a, None,
                        hired_on=today - datetime.timedelta(days=400))
    return EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=emp, annual_ctc_amount=Decimal("120000"), status="active")


@pytest.fixture
def hiring_data_a(db, tenant_a, dept_a, today):
    """Hand-verified recruiting dataset for tenant_a, window [today-100, today]:

      req_filled: department=dept_a, created_at=-60d, filled_at=-10d (ttf=50, IN window).
      req_filled_out: filled_at=-200d (OUTSIDE window — excluded from filled_reqs/avg_ttf).
      req_open: status=posted, never filled (counts toward open_reqs).

      app1: candidate1 -> req_filled, applied -70d, stage=hired, hired_on=-20d (IN window;
            source=referral; tth=50).
      app2: candidate2 -> req_filled, applied -65d, stage=rejected (IN window).
      app3: candidate3 -> req_open, applied -150d (OUTSIDE window), stage=hired, hired_on=-140d
            (OUTSIDE window — proves the date-range-scoped hired set excludes it).
      app4: candidate4 -> req_open, applied -10d, stage=applied (still open; pads the funnel).
    """
    from apps.core.models import Party, PartyRole
    from apps.hrm.models import JobRequisition, CandidateProfile, JobApplication

    def _mk_candidate(name, email):
        party = Party.objects.create(tenant=tenant_a, kind="person", name=name)
        PartyRole.objects.create(tenant=tenant_a, party=party, role="candidate")
        first, _, last = name.partition(" ")
        return CandidateProfile.objects.create(
            tenant=tenant_a, party=party, first_name=first, last_name=last or "X", email=email)

    req_filled = JobRequisition.objects.create(
        tenant=tenant_a, title="Backend Dev", department=dept_a, headcount=1,
        req_type="standard", employment_type="full_time", reason_for_hire="new_headcount",
        posting_type="external", priority="medium")
    req_filled.status = "filled"
    req_filled.filled_at = timezone.now() - datetime.timedelta(days=10)
    req_filled.save(update_fields=["status", "filled_at", "updated_at"])
    JobRequisition.objects.filter(pk=req_filled.pk).update(
        created_at=timezone.now() - datetime.timedelta(days=60))
    req_filled.refresh_from_db()

    req_filled_out = JobRequisition.objects.create(
        tenant=tenant_a, title="Old Fill", department=dept_a, headcount=1,
        req_type="standard", employment_type="full_time", reason_for_hire="new_headcount",
        posting_type="external", priority="low")
    req_filled_out.status = "filled"
    req_filled_out.filled_at = timezone.now() - datetime.timedelta(days=200)
    req_filled_out.save(update_fields=["status", "filled_at", "updated_at"])

    req_open = JobRequisition.objects.create(
        tenant=tenant_a, title="Open Analyst", department=dept_a, headcount=1,
        req_type="standard", employment_type="full_time", reason_for_hire="new_headcount",
        posting_type="external", priority="medium")
    req_open.status = "posted"
    req_open.save(update_fields=["status", "updated_at"])

    cand1 = _mk_candidate("Cand One", "cand1@example.com")
    cand2 = _mk_candidate("Cand Two", "cand2@example.com")
    cand3 = _mk_candidate("Cand Three", "cand3@example.com")
    cand4 = _mk_candidate("Cand Four", "cand4@example.com")

    app1 = JobApplication.objects.create(tenant=tenant_a, candidate=cand1, requisition=req_filled,
                                          source="referral")
    app1.stage = "hired"
    app1.hired_on = today - datetime.timedelta(days=20)
    app1.save(update_fields=["stage", "hired_on", "updated_at"])
    JobApplication.objects.filter(pk=app1.pk).update(applied_at=timezone.now() - datetime.timedelta(days=70))

    app2 = JobApplication.objects.create(tenant=tenant_a, candidate=cand2, requisition=req_filled,
                                          source="linkedin")
    app2.stage = "rejected"
    app2.save(update_fields=["stage", "updated_at"])
    JobApplication.objects.filter(pk=app2.pk).update(applied_at=timezone.now() - datetime.timedelta(days=65))

    app3 = JobApplication.objects.create(tenant=tenant_a, candidate=cand3, requisition=req_open,
                                          source="indeed")
    app3.stage = "hired"
    app3.hired_on = today - datetime.timedelta(days=140)
    app3.save(update_fields=["stage", "hired_on", "updated_at"])
    JobApplication.objects.filter(pk=app3.pk).update(applied_at=timezone.now() - datetime.timedelta(days=150))

    app4 = JobApplication.objects.create(tenant=tenant_a, candidate=cand4, requisition=req_open,
                                          source="careers_page")
    JobApplication.objects.filter(pk=app4.pk).update(applied_at=timezone.now() - datetime.timedelta(days=10))

    for a in (app1, app2, app3, app4):
        a.refresh_from_db()

    return {
        "req_filled": req_filled, "req_filled_out": req_filled_out, "req_open": req_open,
        "app1": app1, "app2": app2, "app3": app3, "app4": app4,
        "date_from": today - datetime.timedelta(days=100), "date_to": today,
    }


def _qs(date_from=None, date_to=None, **extra):
    params = {}
    if date_from is not None:
        params["date_from"] = date_from.isoformat()
    if date_to is not None:
        params["date_to"] = date_to.isoformat()
    params.update(extra)
    return params


# ============================================================
# 1. Access control — the headline control, all six reports
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
    """Exercises every report with an empty tenant (no HR data at all — client_a has no
    employees/payroll/requisitions unless a data fixture is requested), and with nonsensical
    query params, to prove the views never 500."""

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_no_params_200(self, client_a, url_name):
        resp = client_a.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_nonsensical_params_never_500(self, client_a, url_name):
        bad_params = {
            "date_from": "not-a-date", "date_to": "2000-01-01",
            "department": "abc", "as_of": "9999-12-31",
            "cycle": "999999", "separation_type": "not_a_real_type",
        }
        resp = client_a.get(reverse(f"hrm:{url_name}"), bad_params)
        assert resp.status_code == 200

    def test_headcount_reversed_date_range_clamped(self, client_a, today):
        future = today + datetime.timedelta(days=10)
        resp = client_a.get(reverse("hrm:headcount_report"),
                             _qs(date_from=future, date_to=today))
        assert resp.status_code == 200
        assert resp.context["date_from"] == resp.context["date_to"] == today

    def test_attrition_reversed_date_range_clamped(self, client_a, today):
        future = today + datetime.timedelta(days=10)
        resp = client_a.get(reverse("hrm:attrition_report"),
                             _qs(date_from=future, date_to=today))
        assert resp.status_code == 200
        assert resp.context["date_from"] == resp.context["date_to"] == today

    def test_hiring_reversed_date_range_clamped(self, client_a, today):
        future = today + datetime.timedelta(days=10)
        resp = client_a.get(reverse("hrm:hiring_report"),
                             _qs(date_from=future, date_to=today))
        assert resp.status_code == 200
        assert resp.context["date_from"] == resp.context["date_to"] == today

    def test_diversity_far_future_as_of_no_error(self, client_a, hc_data_a):
        resp = client_a.get(reverse("hrm:diversity_report"), {"as_of": "9999-12-31"})
        assert resp.status_code == 200

    def test_cost_unknown_cycle_falls_back(self, client_a, payroll_data_a):
        resp = client_a.get(reverse("hrm:cost_report"), {"cycle": "999999"})
        assert resp.status_code == 200
        # Falls back to the most recent cycle (cycles[0]), not an empty/broken state.
        assert resp.context["cycle"] == payroll_data_a["cycle"]

    def test_headcount_full_filter_set(self, client_a, hc_data_a, dept_a, today):
        resp = client_a.get(reverse("hrm:headcount_report"),
                             _qs(date_from=hc_data_a["date_from"], date_to=today,
                                 department=dept_a.pk))
        assert resp.status_code == 200

    def test_attrition_full_filter_set(self, client_a, hc_data_a, dept_a, today):
        resp = client_a.get(reverse("hrm:attrition_report"),
                             _qs(date_from=hc_data_a["date_from"], date_to=today,
                                 department=dept_a.pk, separation_type="resignation"))
        assert resp.status_code == 200

    def test_diversity_full_filter_set(self, client_a, hc_data_a, dept_a, today):
        resp = client_a.get(reverse("hrm:diversity_report"),
                             {"as_of": today.isoformat(), "department": dept_a.pk})
        assert resp.status_code == 200

    def test_cost_full_filter_set(self, client_a, payroll_data_a, dept_a):
        resp = client_a.get(reverse("hrm:cost_report"),
                             {"department": dept_a.pk, "cycle": payroll_data_a["cycle"].pk})
        assert resp.status_code == 200

    def test_hiring_full_filter_set(self, client_a, hiring_data_a, dept_a, today):
        resp = client_a.get(reverse("hrm:hiring_report"),
                             _qs(date_from=hiring_data_a["date_from"], date_to=today,
                                 department=dept_a.pk))
        assert resp.status_code == 200


# ============================================================
# 3a. Headcount report — aggregate correctness
# ============================================================

class TestHeadcountReport:
    def test_active_count_unfiltered(self, client_a, hc_data_a):
        resp = client_a.get(reverse("hrm:headcount_report"))
        assert resp.context["active_count"] == 4  # e1, e2, e3, e7 (e4-e6 terminated)

    def test_active_count_department_filtered(self, client_a, hc_data_a, dept_a):
        resp = client_a.get(reverse("hrm:headcount_report"), {"department": dept_a.pk})
        assert resp.context["active_count"] == 2  # e1, e2 only

    def test_joins_and_exits_unfiltered_in_window(self, client_a, hc_data_a, today):
        resp = client_a.get(reverse("hrm:headcount_report"),
                             _qs(date_from=hc_data_a["date_from"], date_to=today))
        assert resp.context["joins"] == 2   # e2 (-50d), e7 (-30d)
        assert resp.context["exits"] == 2   # sep4 (-20d), sep5 (-40d); sep6 (-150d) excluded
        assert resp.context["net_change"] == 0

    def test_joins_department_filter_changes_count(self, client_a, hc_data_a, dept_a, today):
        """dept_a excludes e7 (Sales) from the join count — proves the filter is actually
        applied, not just accepted."""
        resp = client_a.get(reverse("hrm:headcount_report"),
                             _qs(date_from=hc_data_a["date_from"], date_to=today, department=dept_a.pk))
        assert resp.context["joins"] == 1
        assert resp.context["exits"] == 2
        assert resp.context["net_change"] == -1

    def test_exit_outside_window_excluded(self, client_a, hc_data_a, today):
        """sep6's LWD (-150d) sits outside a narrower [-60, 0] window."""
        resp = client_a.get(reverse("hrm:headcount_report"),
                             _qs(date_from=today - datetime.timedelta(days=60), date_to=today))
        assert resp.context["exits"] == 2  # sep4 (-20d), sep5 (-40d) only

    def test_by_department_breakdown(self, client_a, hc_data_a):
        resp = client_a.get(reverse("hrm:headcount_report"))
        by_dept = {r["employment__org_unit__name"]: r["count"] for r in resp.context["by_department"]}
        assert by_dept == {"Engineering": 2, "Sales": 2}

    def test_by_type_breakdown(self, client_a, hc_data_a):
        resp = client_a.get(reverse("hrm:headcount_report"))
        by_type = {r["name"]: r["count"] for r in resp.context["by_type"]}
        assert by_type == {"Full Time": 3, "Contract": 1}

    def test_by_designation_includes_budget_and_variance(self, client_a, hc_data_a, designation_a):
        resp = client_a.get(reverse("hrm:headcount_report"))
        by_desig = {r["name"]: r for r in resp.context["by_designation"]}
        row = by_desig[designation_a.name]
        assert row["count"] == 2
        assert row["budget"] == 3
        assert row["variance"] == -1
        unassigned = by_desig["Unassigned"]
        assert unassigned["count"] == 2
        assert unassigned["budget"] is None
        assert unassigned["variance"] is None

    def test_by_designation_department_filtered_excludes_unassigned(self, client_a, hc_data_a, dept_a):
        resp = client_a.get(reverse("hrm:headcount_report"), {"department": dept_a.pk})
        names = [r["name"] for r in resp.context["by_designation"]]
        assert "Unassigned" not in names

    def test_trend_is_valid_12_point_json(self, client_a, hc_data_a):
        import json
        resp = client_a.get(reverse("hrm:headcount_report"))
        labels = json.loads(resp.context["trend_labels"])
        values = json.loads(resp.context["trend_values"])
        assert len(labels) == len(values) == 12
        assert all(isinstance(v, int) for v in values)

    def test_department_choices_scoped_to_tenant(self, client_a, hc_data_a, dept_b):
        resp = client_a.get(reverse("hrm:headcount_report"))
        dept_ids = {d.pk for d in resp.context["department_choices"]}
        assert dept_b.pk not in dept_ids


# ============================================================
# 3b. Attrition report — SHRM turnover formula, voluntary/involuntary split
# ============================================================

class TestAttritionReport:
    def test_separations_count_in_window(self, client_a, hc_data_a, today):
        resp = client_a.get(reverse("hrm:attrition_report"),
                             _qs(date_from=hc_data_a["date_from"], date_to=today))
        assert resp.context["separations"] == 2  # sep4, sep5; sep6 outside window

    def test_turnover_matches_shrm_formula(self, client_a, hc_data_a, today):
        """avg_hc is hand-verified via _headcount_at semantics:
        headcount_at(date_from=-100d) = 5 hired - 1 separated(sep6, -150d<=-100d) = 4
        headcount_at(date_to=today)   = 7 hired - 3 separated(sep4,sep5,sep6)      = 4
        avg_hc = 4.0; days = 100; separations = 2.
        """
        date_from, date_to = hc_data_a["date_from"], today
        resp = client_a.get(reverse("hrm:attrition_report"), _qs(date_from=date_from, date_to=date_to))
        avg_hc = 4.0
        days = (date_to - date_from).days
        expected_turnover = round((2 / avg_hc) * (365 / days) * 100, 1)
        expected_retention = round(100 - expected_turnover, 1)
        assert resp.context["turnover"] == expected_turnover
        assert resp.context["retention"] == expected_retention

    def test_turnover_zero_when_avg_headcount_zero(self, client_a, tenant_a):
        """An empty tenant (no hires, no separations) -> avg_hc == 0 -> turnover guarded to 0.0,
        never a ZeroDivisionError."""
        resp = client_a.get(reverse("hrm:attrition_report"))
        assert resp.context["turnover"] == 0.0
        assert resp.context["retention"] == 100.0

    def test_voluntary_involuntary_split(self, client_a, hc_data_a, today):
        resp = client_a.get(reverse("hrm:attrition_report"),
                             _qs(date_from=hc_data_a["date_from"], date_to=today))
        # sep4=resignation (voluntary), sep5=termination (involuntary) -> 1/2 each = 50%.
        assert resp.context["voluntary_pct"] == 50.0
        assert resp.context["involuntary_pct"] == 50.0

    def test_separation_type_filter(self, client_a, hc_data_a, today):
        resp = client_a.get(reverse("hrm:attrition_report"),
                             _qs(date_from=hc_data_a["date_from"], date_to=today,
                                 separation_type="resignation"))
        assert resp.context["separations"] == 1
        assert resp.context["voluntary_pct"] == 100.0

    def test_by_department_and_by_reason(self, client_a, hc_data_a, today):
        resp = client_a.get(reverse("hrm:attrition_report"),
                             _qs(date_from=hc_data_a["date_from"], date_to=today))
        by_dept = {r["name"]: r["count"] for r in resp.context["by_department"]}
        assert by_dept == {"Engineering": 2}
        by_reason = {r["name"]: r["count"] for r in resp.context["by_reason"]}
        assert by_reason == {"Better Opportunity": 1, "Performance": 1}

    def test_by_tenure_bucketing(self, client_a, hc_data_a, today):
        """e4: hired -400d, LWD -20d -> tenure 380d (~1.04y) -> "1-2 yrs".
        e5: hired -380d, LWD -40d -> tenure 340d (~0.93y) -> "<1 yr"."""
        resp = client_a.get(reverse("hrm:attrition_report"),
                             _qs(date_from=hc_data_a["date_from"], date_to=today))
        by_tenure = {r["name"]: r["count"] for r in resp.context["by_tenure"]}
        assert by_tenure == {"1-2 yrs": 1, "<1 yr": 1}


# ============================================================
# 3c. Diversity report — gender/age/tenure bucketing
# ============================================================

class TestDiversityReport:
    def test_total_and_gender_split(self, client_a, hc_data_a):
        resp = client_a.get(reverse("hrm:diversity_report"))
        assert resp.context["total"] == 4
        by_gender = {r["name"]: r["count"] for r in resp.context["by_gender"]}
        assert by_gender == {"Female": 1, "Male": 1, "Not Specified": 2}

    def test_avg_age_computed_from_dob_only(self, client_a, hc_data_a):
        resp = client_a.get(reverse("hrm:diversity_report"))
        assert resp.context["avg_age"] == 31.5  # (35 + 28) / 2 — e3/e7 have no DOB

    def test_avg_age_none_when_no_dobs(self, client_a, hc_data_a, dept_sales_a):
        """Filtering to the Sales department (e3, e7 — neither has a DOB) must yield
        avg_age=None, never a ZeroDivisionError or a bogus 0."""
        resp = client_a.get(reverse("hrm:diversity_report"), {"department": dept_sales_a.pk})
        assert resp.context["total"] == 2
        assert resp.context["avg_age"] is None

    def test_age_band_bucketing(self, client_a, hc_data_a):
        resp = client_a.get(reverse("hrm:diversity_report"))
        by_age = {r["name"]: r["count"] for r in resp.context["by_age"]}
        assert by_age == {"35-44": 1, "25-34": 1, "Unknown": 2}

    def test_tenure_band_bucketing_and_avg(self, client_a, hc_data_a, today):
        """e1:500d->1-2yrs, e2:50d-><1yr, e3:600d->1-2yrs, e7:30d-><1yr."""
        resp = client_a.get(reverse("hrm:diversity_report"))
        by_tenure = {r["name"]: r["count"] for r in resp.context["by_tenure"]}
        assert by_tenure == {"<1 yr": 2, "1-2 yrs": 2}
        expected_avg_tenure = round((500 + 50 + 600 + 30) / 4 / 365.25, 1)
        assert resp.context["avg_tenure"] == expected_avg_tenure

    def test_crosstab_by_department_and_gender(self, client_a, hc_data_a):
        resp = client_a.get(reverse("hrm:diversity_report"))
        genders = resp.context["genders"]
        crosstab = {row["dept"]: dict(zip(genders, row["counts"])) for row in resp.context["crosstab"]}
        assert crosstab["Engineering"].get("Female", 0) == 1
        assert crosstab["Engineering"].get("Male", 0) == 1
        assert crosstab["Sales"].get("Not Specified", 0) == 2


# ============================================================
# 3d. Cost report — total/employer cost, department scoping fix, estimate fallback
# ============================================================

class TestCostReport:
    def test_total_cost_unfiltered(self, client_a, payroll_data_a):
        resp = client_a.get(reverse("hrm:cost_report"))
        assert resp.context["total_cost"] == Decimal("8000.00")
        assert resp.context["headcount"] == 2
        assert resp.context["avg_cost"] == Decimal("4000.00")
        assert resp.context["is_estimate"] is False

    def test_employer_cost_and_by_component_unfiltered(self, client_a, payroll_data_a):
        resp = client_a.get(reverse("hrm:cost_report"))
        assert resp.context["employer_cost"] == Decimal("160.00")
        by_comp = {r["name"]: r["total"] for r in resp.context["by_component"]}
        assert by_comp["Earning"] == Decimal("8000.00")
        assert by_comp["Statutory Deduction"] == Decimal("320.00")

    def test_department_filter_scopes_total_cost(self, client_a, payroll_data_a, dept_a):
        resp = client_a.get(reverse("hrm:cost_report"), {"department": dept_a.pk})
        assert resp.context["total_cost"] == Decimal("5000.00")
        assert resp.context["headcount"] == 1

    def test_department_filter_scopes_employer_cost_and_by_component(self, client_a, payroll_data_a, dept_a):
        """The code-reviewer's fix: PayslipLine query must honor the same ?department scope as
        the payslip totals — before the fix, employer_cost/by_component stayed tenant-wide
        (160.00 / 320.00) even when a department filter was applied."""
        resp = client_a.get(reverse("hrm:cost_report"), {"department": dept_a.pk})
        assert resp.context["employer_cost"] == Decimal("100.00")
        by_comp = {r["name"]: r["total"] for r in resp.context["by_component"]}
        assert by_comp["Earning"] == Decimal("5000.00")
        assert by_comp["Statutory Deduction"] == Decimal("200.00")

    def test_cycle_selector_defaults_to_most_recent(self, client_a, payroll_data_a):
        resp = client_a.get(reverse("hrm:cost_report"))
        assert resp.context["cycle"] == payroll_data_a["cycle"]

    def test_explicit_cycle_selection(self, client_a, payroll_data_a):
        resp = client_a.get(reverse("hrm:cost_report"), {"cycle": payroll_data_a["cycle"].pk})
        assert resp.context["cycle"] == payroll_data_a["cycle"]

    def test_no_cycle_falls_back_to_ctc_estimate(self, client_a, estimate_salary_a):
        resp = client_a.get(reverse("hrm:cost_report"))
        assert resp.context["cycle"] is None
        assert resp.context["is_estimate"] is True
        assert resp.context["total_cost"] == Decimal("10000.00")  # 120000 / 12
        assert resp.context["headcount"] == 1
        assert resp.context["avg_cost"] == Decimal("10000.00")

    def test_no_cycle_no_salary_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:cost_report"))
        assert resp.context["cycle"] is None
        assert resp.context["is_estimate"] is False
        assert resp.context["total_cost"] == 0
        assert resp.context["headcount"] == 0


# ============================================================
# 3e. Hiring report — date-range-scoped hires, offer-accept, funnel
# ============================================================

class TestHiringReport:
    def test_open_and_filled_reqs(self, client_a, hiring_data_a, today):
        resp = client_a.get(reverse("hrm:hiring_report"),
                             _qs(date_from=hiring_data_a["date_from"], date_to=today))
        assert resp.context["open_reqs"] == 1     # req_open (posted)
        assert resp.context["filled_reqs"] == 1   # req_filled only; req_filled_out (-200d) excluded
        assert resp.context["avg_ttf"] == 50

    def test_source_of_hire_excludes_out_of_range_hire(self, client_a, hiring_data_a, today):
        """app3 (source=indeed) was hired -140d, outside the [-100, 0] window — must NOT appear
        in by_source (only app1/referral, hired -20d, is in range)."""
        resp = client_a.get(reverse("hrm:hiring_report"),
                             _qs(date_from=hiring_data_a["date_from"], date_to=today))
        by_source = {r["name"]: r["count"] for r in resp.context["by_source"]}
        assert by_source == {"Employee Referral": 1}
        assert "Indeed" not in by_source

    def test_avg_time_to_hire(self, client_a, hiring_data_a, today):
        resp = client_a.get(reverse("hrm:hiring_report"),
                             _qs(date_from=hiring_data_a["date_from"], date_to=today))
        assert resp.context["avg_tth"] == 50  # app1: hired -20d, applied -70d

    def test_offer_accept_over_same_window(self, client_a, hiring_data_a, today):
        """decided = applications APPLIED within the window: app1(hired), app2(rejected), app4
        (still open) all applied in-range; app3 applied -150d, out of range, excluded.
        hired_dec=1 (app1), rejected_dec=1 (app2) -> 50.0%."""
        resp = client_a.get(reverse("hrm:hiring_report"),
                             _qs(date_from=hiring_data_a["date_from"], date_to=today))
        assert resp.context["offer_accept"] == 50.0

    def test_offer_accept_none_when_no_decided(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:hiring_report"))
        assert resp.context["offer_accept"] is None

    def test_funnel_percent_of_total(self, client_a, hiring_data_a, today):
        """funnel is NOT date-scoped — it's built from ALL applications (department-filtered
        only): hired=2 (app1+app3), rejected=1 (app2), applied=1 (app4); total=4."""
        resp = client_a.get(reverse("hrm:hiring_report"),
                             _qs(date_from=hiring_data_a["date_from"], date_to=today))
        funnel = {r["name"]: (r["count"], r["pct"]) for r in resp.context["funnel"]}
        assert funnel["Hired"] == (2, 50.0)
        assert funnel["Rejected"] == (1, 25.0)
        assert funnel["Applied"] == (1, 25.0)

    def test_by_department_from_hired_set(self, client_a, hiring_data_a, today):
        resp = client_a.get(reverse("hrm:hiring_report"),
                             _qs(date_from=hiring_data_a["date_from"], date_to=today))
        by_dept = {r["requisition__department__name"]: r["count"] for r in resp.context["by_department"]}
        assert by_dept == {"Engineering": 1}


# ============================================================
# 4. Multi-tenant isolation / IDOR
# ============================================================

class TestMultiTenantIsolation:
    def test_headcount_excludes_other_tenant(self, client_a, hc_data_a, employee_b):
        resp = client_a.get(reverse("hrm:headcount_report"))
        assert resp.context["active_count"] == 4  # employee_b (tenant_b) never counted

    def test_diversity_excludes_other_tenant(self, client_a, hc_data_a, employee_b):
        resp = client_a.get(reverse("hrm:diversity_report"))
        assert resp.context["total"] == 4

    def test_cost_excludes_other_tenant(self, client_a, payroll_data_a, payslip_b):
        resp = client_a.get(reverse("hrm:cost_report"))
        assert resp.context["total_cost"] == Decimal("8000.00")

    def test_hiring_excludes_other_tenant(self, client_a, hiring_data_a, req_b, today):
        resp = client_a.get(reverse("hrm:hiring_report"),
                             _qs(date_from=hiring_data_a["date_from"], date_to=today))
        assert resp.context["open_reqs"] == 1

    def test_cross_tenant_department_pk_ignored_falls_back_to_all(self, client_a, hc_data_a, dept_b):
        """A tenant-B department pk passed on a tenant-A request must NOT scope/leak — it should
        resolve to None (not found in tenant_a) and the report falls back to unfiltered totals."""
        resp = client_a.get(reverse("hrm:headcount_report"), {"department": dept_b.pk})
        assert resp.context["department"] is None
        assert resp.context["active_count"] == 4

    def test_cross_tenant_department_pk_ignored_on_cost_report(self, client_a, payroll_data_a, dept_b):
        resp = client_a.get(reverse("hrm:cost_report"), {"department": dept_b.pk})
        assert resp.context["department"] is None
        assert resp.context["total_cost"] == Decimal("8000.00")

    def test_tenant_b_admin_never_sees_tenant_a_data(self, client_b, hc_data_a):
        resp = client_b.get(reverse("hrm:headcount_report"))
        assert resp.context["active_count"] == 0


# ============================================================
# 5. Div-by-zero — a fully empty tenant renders every report at 200 with zero/None KPIs
# ============================================================

class TestEmptyTenantDivByZero:
    """client_a's tenant_a has no HR data at all unless a data fixture is explicitly requested —
    every one of the six reports must render 200 with safe zero/None defaults, never a
    ZeroDivisionError."""

    def test_hr_reports_index_empty_tiles(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:hr_reports_index"))
        assert resp.status_code == 200
        assert len(resp.context["tiles"]) == 5

    def test_headcount_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:headcount_report"))
        assert resp.status_code == 200
        assert resp.context["active_count"] == 0
        assert resp.context["joins"] == 0
        assert resp.context["exits"] == 0
        assert resp.context["net_change"] == 0
        assert resp.context["by_department"] == []
        assert resp.context["by_designation"] == []

    def test_attrition_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:attrition_report"))
        assert resp.status_code == 200
        assert resp.context["separations"] == 0
        assert resp.context["turnover"] == 0.0
        assert resp.context["retention"] == 100.0
        assert resp.context["voluntary_pct"] == 0.0
        assert resp.context["involuntary_pct"] == 0.0

    def test_diversity_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:diversity_report"))
        assert resp.status_code == 200
        assert resp.context["total"] == 0
        assert resp.context["avg_age"] is None
        assert resp.context["avg_tenure"] is None
        assert resp.context["by_gender"] == []

    def test_cost_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:cost_report"))
        assert resp.status_code == 200
        assert resp.context["total_cost"] == 0
        assert resp.context["is_estimate"] is False
        assert resp.context["cycle"] is None
        assert resp.context["headcount"] == 0

    def test_hiring_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:hiring_report"))
        assert resp.status_code == 200
        assert resp.context["open_reqs"] == 0
        assert resp.context["filled_reqs"] == 0
        assert resp.context["avg_ttf"] is None
        assert resp.context["offer_accept"] is None
        assert resp.context["funnel"] == []

    def test_no_tenant_superuser_index_no_error(self, admin_user):
        """A tenant-less superuser (request.tenant is None) gets an empty tiles list, not a
        500 (mirrors the celebrations-view convention in 3.27)."""
        from django.test import Client
        from apps.accounts.models import User
        superuser = User.objects.create_superuser(
            email="super_hr@example.com", username="super_hr", password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        resp = c.get(reverse("hrm:hr_reports_index"))
        assert resp.status_code == 200
        assert resp.context["tiles"] == []


# ============================================================
# 6. Query-count ceilings (N+1 guard)
# ============================================================

class TestQueryCounts:
    def test_headcount_report_query_count_bounded(self, client_a, hc_data_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(25):
            client_a.get(reverse("hrm:headcount_report"))

    def test_cost_report_query_count_bounded(self, client_a, payroll_data_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(25):
            client_a.get(reverse("hrm:cost_report"))
