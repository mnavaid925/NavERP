"""Tests for HRM 3.31 Payroll Reports sub-module: derived, read-only report views (no models).

Mirrors ``test_leave_reports.py`` (3.30) / ``test_attendance_reports.py`` (3.29) /
``test_hr_reports.py`` (3.28) — same fixture style, access-control + aggregate-correctness + IDOR
+ div-by-zero + query-count structure.

Covers all six ``@tenant_admin_required`` views in ``apps/hrm/views.py``
(``payroll_reports_index``, ``salary_register_report``, ``tax_report``, ``statutory_report``,
``ctc_report``, ``cost_center_report``), which sit on top of the built payroll engine
(``PayrollCycle``/``Payslip``/``PayslipLine``/``EmployeeSalaryStructure``/``TaxComputation``/
``InvestmentDeclaration``/``StatutoryReturn``/``EmployeeStatutoryIdentifier``/
``CostCenterProfile``/``DepartmentProfile``) plus the 3.31-local helpers (``_fy_choices``/
``_report_financial_year``/``_cc_choices``/``_report_cost_center``/``_grade_choices``/
``_report_job_grade``) and the reused 3.28 ``_report_department``/``_dept_choices``:

  - Access control: anonymous -> redirect, non-admin member -> 403, tenant admin -> 200.
  - Rendering never 500s: no params / a full filter set / nonsensical params (non-digit
    department/cycle/grade/cost_center, a Unicode-superscript department pk, an unknown financial
    year / scheme, reversed date range on the one date-scoped report).
  - Aggregate correctness against hand-verified fixtures: salary_register (latest-cycle default,
    totals footer, ``?cycle``/``?department``/``?on_hold`` scoping, by-component grouping), tax
    (payable/paid totals, avg-payable div-by-zero guard, not-filed count independent of
    dept/regime filters, by-regime/by-section, Form-16 linked-vs-pending split), statutory
    (per-scheme register — a tds_form16 return never leaks into the pf/esi/pt/lwf schemes —
    emp/empr/headcount sums, overdue count, coverage counts, masked-identifier rendering), ctc
    (total/avg/headcount over active structures, per-employee ``resolved_amount(own_ctc)`` pct-line
    proof, dept/grade filters), cost_center (the department->cost-centre attribution fold via
    ``DepartmentProfile.cost_center``, the Unassigned bucket, distinct-employee headcount across
    cycles, budget-year scoping, ``variance`` None when no budget, profile-less cost-centre pk
    falls back to all).
  - Multi-tenant isolation: another tenant's payroll/tax/statutory/cost-centre data never leaks
    into totals; a cross-tenant ``?cycle``/``?department``/``?grade``/``?cost_center`` pk is
    ignored (falls back to the tenant's own default, never an error, never a leak).
  - Div-by-zero / empty tenant: every report renders 200 with zero/empty KPIs on a tenant with no
    payroll data.
  - Query-count ceilings (N+1 guard), including ctc_report's per-template line caching exercised
    across >=2 templates x >=3 employees.
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db

REPORT_URL_NAMES = [
    "payroll_reports_index",
    "salary_register_report",
    "tax_report",
    "statutory_report",
    "ctc_report",
    "cost_center_report",
]

DATE_SCOPED_URL_NAMES = ["statutory_report"]


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
def dept_empty_a(db, tenant_a):
    """A third OrgUnit department with no payroll/tax data of its own — used for the
    avg-payable/div-by-zero-within-a-populated-FY proof."""
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, kind="department", name="Empty Dept")


def _mk_employee(tenant, name, dept):
    """Build a Party + core.Employment + hrm.EmployeeProfile with a controlled name/department
    (the conftest employee_a fixture is a single fixed employee — these tests need many)."""
    from apps.core.models import Party, Employment
    from apps.hrm.models import EmployeeProfile
    party = Party.objects.create(tenant=tenant, kind="person", name=name)
    employment = Employment.objects.create(
        tenant=tenant, party=party, org_unit=dept, job_title="Staff", status="active")
    return EmployeeProfile.objects.create(
        tenant=tenant, party=party, employment=employment, employee_type="full_time")


@pytest.fixture
def grade_b(db, tenant_b):
    """A JobGrade belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import JobGrade
    return JobGrade.objects.create(tenant=tenant_b, name="B1", level_order=1)


# ------------------------------------------------------------------ 3.31 salary-register fixtures
@pytest.fixture
def salary_register_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """Two PayrollCycles for tenant_a — ``cycle_old`` (pay_date -60d) and ``cycle_new`` (pay_date
    -1d, the latest -> the default selection). ``cycle_new`` carries 4 Payslips (explicit
    gross/ded/net/lop/arrears/bonus/on_hold — NOT recomputed) + PayslipLine rows per payslip
    (earning + employee/employer statutory_deduction) for the by-component breakdown:

      ps1 (emp1, dept_a):      gross=5000 ded=500 net=4500 lop=100 arrears=50 bonus=200
      ps2 (emp2, dept_a):      gross=6000 ded=600 net=5400
      ps3 (emp3, dept_sales_a):gross=4000 ded=400 net=3600
      ps_hold (emp_hold, dept_a, on_hold=True): gross=3000 ded=300 net=2700

    Unfiltered totals (4 rows): gross=18000 ded=1800 net=16200 lop=100 arrears=50 bonus=200.
    dept_a-only (ps1,ps2,ps_hold): gross=14000 ded=1400 net=12600.
    on_hold=1: ps_hold only.
    by_component unfiltered: earning=4700+5800+3800+2700=17000;
      statutory_deduction=(300+350)+(400+450)+(200+220)+(150+175)=2245.
    dept_a by_component: earning=4700+5800+2700=13200; statutory_deduction=650+850+325=1825.

    ``cycle_old`` carries a single Payslip (``ps_old``, emp1): gross=4800 ded=480 net=4320, no
    lines (empty by_component) — proves ``?cycle`` selects a DIFFERENT dataset.
    """
    from apps.hrm.models import PayrollCycle, Payslip, PayslipLine

    cycle_old = PayrollCycle.objects.create(
        tenant=tenant_a, period_start=today - datetime.timedelta(days=90),
        period_end=today - datetime.timedelta(days=61), pay_date=today - datetime.timedelta(days=60),
        cycle_type="regular", status="locked")
    cycle_new = PayrollCycle.objects.create(
        tenant=tenant_a, period_start=today - datetime.timedelta(days=30),
        period_end=today, pay_date=today - datetime.timedelta(days=1),
        cycle_type="regular", status="locked")

    emp1 = _mk_employee(tenant_a, "Reg Emp One", dept_a)
    emp2 = _mk_employee(tenant_a, "Reg Emp Two", dept_a)
    emp3 = _mk_employee(tenant_a, "Reg Emp Three", dept_sales_a)
    emp_hold = _mk_employee(tenant_a, "Reg Emp Hold", dept_a)

    def _ps(cycle, emp, gross, ded, net, lop=0, arrears=0, bonus=0, on_hold=False):
        return Payslip.objects.create(
            tenant=tenant_a, cycle=cycle, employee=emp,
            gross_pay=Decimal(str(gross)), total_deductions=Decimal(str(ded)), net_pay=Decimal(str(net)),
            lop_amount=Decimal(str(lop)), arrears_amount=Decimal(str(arrears)), bonus_amount=Decimal(str(bonus)),
            on_hold=on_hold)

    ps1 = _ps(cycle_new, emp1, 5000, 500, 4500, lop=100, arrears=50, bonus=200)
    ps2 = _ps(cycle_new, emp2, 6000, 600, 5400)
    ps3 = _ps(cycle_new, emp3, 4000, 400, 3600)
    ps_hold = _ps(cycle_new, emp_hold, 3000, 300, 2700, on_hold=True)
    ps_old = _ps(cycle_old, emp1, 4800, 480, 4320)

    def _line(ps, name, ctype, amount, side=""):
        return PayslipLine.objects.create(
            tenant=tenant_a, payslip=ps, component_name=name, component_type=ctype,
            amount=Decimal(str(amount)), contribution_side=side)

    _line(ps1, "Basic", "earning", 4700)
    _line(ps1, "PF EE", "statutory_deduction", 300, "employee")
    _line(ps1, "PF ER", "statutory_deduction", 350, "employer")
    _line(ps2, "Basic", "earning", 5800)
    _line(ps2, "PF EE", "statutory_deduction", 400, "employee")
    _line(ps2, "PF ER", "statutory_deduction", 450, "employer")
    _line(ps3, "Basic", "earning", 3800)
    _line(ps3, "PF EE", "statutory_deduction", 200, "employee")
    _line(ps3, "PF ER", "statutory_deduction", 220, "employer")
    _line(ps_hold, "Basic", "earning", 2700)
    _line(ps_hold, "PF EE", "statutory_deduction", 150, "employee")
    _line(ps_hold, "PF ER", "statutory_deduction", 175, "employer")

    return {
        "cycle_old": cycle_old, "cycle_new": cycle_new,
        "emp1": emp1, "emp2": emp2, "emp3": emp3, "emp_hold": emp_hold,
        "ps1": ps1, "ps2": ps2, "ps3": ps3, "ps_hold": ps_hold, "ps_old": ps_old,
    }


# ------------------------------------------------------------------ 3.31 tax-report fixtures
@pytest.fixture
def tax_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """Hand-verified tax dataset for tenant_a, FY "2024-25":

      emp1 (dept_a, old regime):   TaxComputation payable=50000 paid=20000, no Form16 link.
      emp2 (dept_a, new regime):   TaxComputation payable=30000 paid=10000, Form16 LINKED
                                    (statutory_return set).
      emp3 (dept_sales_a, old):    TaxComputation payable=20000 paid=5000, no Form16 link.
      emp_no_decl (dept_a):        NO declaration for the FY -> counts toward not_filed.

    Totals: total_payable=100000 total_paid=35000 avg_payable=33333.33.
    by_regime: old=2 (emp1,emp3), new=1 (emp2). decl_status: submitted=3. not_filed=1.
    by_section: 80c declared=150000 verified=90000 (decl2's line has verified_amount=None ->
      None-safe, contributes 0); hra declared=20000 verified=15000.
    Form16 register: linked=1 (emp2), pending=2 (emp1, emp3).
    """
    from apps.hrm.models import InvestmentDeclaration, InvestmentDeclarationLine, TaxComputation, StatutoryReturn

    FY = "2024-25"
    emp1 = _mk_employee(tenant_a, "Tax Emp One", dept_a)
    emp2 = _mk_employee(tenant_a, "Tax Emp Two", dept_a)
    emp3 = _mk_employee(tenant_a, "Tax Emp Three", dept_sales_a)
    emp_no_decl = _mk_employee(tenant_a, "Tax Emp NoDecl", dept_a)

    decl1 = InvestmentDeclaration.objects.create(
        tenant=tenant_a, employee=emp1, financial_year=FY, regime_elected="old", status="submitted")
    decl2 = InvestmentDeclaration.objects.create(
        tenant=tenant_a, employee=emp2, financial_year=FY, regime_elected="new", status="submitted")
    decl3 = InvestmentDeclaration.objects.create(
        tenant=tenant_a, employee=emp3, financial_year=FY, regime_elected="old", status="submitted")

    comp1 = TaxComputation.objects.create(
        tenant=tenant_a, employee=emp1, declaration=decl1, financial_year=FY,
        computation_type="final", tax_payable=Decimal("50000"), tax_paid_ytd=Decimal("20000"),
        monthly_tds_amount=Decimal("2500"))
    # sr_form16 is FILED (not pending) and carries no due_date, so it never affects the
    # payroll_reports_index "Overdue Statutory" tile in cross-fixture tests.
    sr_form16 = StatutoryReturn.objects.create(
        tenant=tenant_a, scheme="tds_form16", period_type="annual",
        period_start=datetime.date(2024, 4, 1), period_end=datetime.date(2025, 3, 31),
        employee=emp2, status="filed")
    comp2 = TaxComputation.objects.create(
        tenant=tenant_a, employee=emp2, declaration=decl2, financial_year=FY,
        computation_type="final", tax_payable=Decimal("30000"), tax_paid_ytd=Decimal("10000"),
        monthly_tds_amount=Decimal("1500"), statutory_return=sr_form16)
    comp3 = TaxComputation.objects.create(
        tenant=tenant_a, employee=emp3, declaration=decl3, financial_year=FY,
        computation_type="final", tax_payable=Decimal("20000"), tax_paid_ytd=Decimal("5000"),
        monthly_tds_amount=Decimal("1000"))

    InvestmentDeclarationLine.objects.create(
        tenant=tenant_a, declaration=decl1, section_code="80c",
        declared_amount=Decimal("100000"), verified_amount=Decimal("90000"))
    InvestmentDeclarationLine.objects.create(
        tenant=tenant_a, declaration=decl2, section_code="80c",
        declared_amount=Decimal("50000"))
    InvestmentDeclarationLine.objects.create(
        tenant=tenant_a, declaration=decl3, section_code="hra",
        declared_amount=Decimal("20000"), verified_amount=Decimal("15000"))

    return {
        "FY": FY, "emp1": emp1, "emp2": emp2, "emp3": emp3, "emp_no_decl": emp_no_decl,
        "decl1": decl1, "decl2": decl2, "decl3": decl3,
        "comp1": comp1, "comp2": comp2, "comp3": comp3, "sr_form16": sr_form16,
    }


@pytest.fixture
def tax_computation_b_matching_fy(db, tenant_b, employee_b):
    """A TaxComputation belonging to tenant_b, same FY "2024-25" as ``tax_data_a`` — proves
    strict tenant scoping (not just "different FY happens not to collide")."""
    from apps.hrm.models import InvestmentDeclaration, TaxComputation
    decl_b = InvestmentDeclaration.objects.create(
        tenant=tenant_b, employee=employee_b, financial_year="2024-25", regime_elected="old",
        status="submitted")
    return TaxComputation.objects.create(
        tenant=tenant_b, employee=employee_b, declaration=decl_b, financial_year="2024-25",
        computation_type="final", tax_payable=Decimal("99999"), tax_paid_ytd=Decimal("99999"),
        monthly_tds_amount=Decimal("9999"))


# ------------------------------------------------------------------ 3.31 statutory-report fixtures
@pytest.fixture
def statutory_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """Hand-verified statutory dataset for tenant_a, all ``period_start`` within the default
    trailing-365-day window:

      sr_pf1: scheme=pf period_start=-60d FILED  emp=1000 empr=1200 hc=5 due=-40d (filed -> not overdue)
      sr_pf2: scheme=pf period_start=-90d PENDING emp=800  empr=900  hc=4 due=-70d (OVERDUE)
      sr_esi1: scheme=esi period_start=-60d PENDING emp=200 empr=300 hc=5 due=+10d (not overdue — future)
      sr_pt1: scheme=pt period_start=-45d PAID emp=100 empr=0 hc=5 due=-50d (paid -> not overdue)
      sr_lwf1: scheme=lwf period_start=-50d PENDING emp=50 empr=150 hc=5 due=-20d (OVERDUE)
      sr_form16: scheme=tds_form16 PENDING due=-10d — must NEVER appear in the pf/esi/pt/lwf
        register regardless of ?scheme (tds_form16 is not a selectable STAT_SCHEMES value).

    Default (?scheme=pf): rows=[sr_pf1, sr_pf2]; emp_total=1800 empr_total=2100 headcount_total=9
      overdue=1 (sr_pf2 only).
    ?scheme=esi: emp=200 empr=300 hc=5 overdue=0. ?scheme=pt: emp=100 empr=0 hc=5 overdue=0.
    ?scheme=lwf: emp=50 empr=150 hc=5 overdue=1.

    Two EmployeeStatutoryIdentifier rows for the masked-ID + coverage-count proof: ident1 (full
    UAN/PF/ESI, both applicable), ident2 (UAN/PF only, esi_number blank, esi NOT applicable).
    coverage: pf=2 esi=1 total=2.
    """
    from apps.hrm.models import StatutoryReturn, EmployeeStatutoryIdentifier

    sr_pf1 = StatutoryReturn.objects.create(
        tenant=tenant_a, scheme="pf", period_type="monthly",
        period_start=today - datetime.timedelta(days=60), period_end=today - datetime.timedelta(days=30),
        employee_contribution_total=Decimal("1000"), employer_contribution_total=Decimal("1200"),
        headcount=5, status="filed", due_date=today - datetime.timedelta(days=40))
    sr_pf2 = StatutoryReturn.objects.create(
        tenant=tenant_a, scheme="pf", period_type="monthly",
        period_start=today - datetime.timedelta(days=90), period_end=today - datetime.timedelta(days=60),
        employee_contribution_total=Decimal("800"), employer_contribution_total=Decimal("900"),
        headcount=4, status="pending", due_date=today - datetime.timedelta(days=70))
    sr_esi1 = StatutoryReturn.objects.create(
        tenant=tenant_a, scheme="esi", period_type="monthly",
        period_start=today - datetime.timedelta(days=60), period_end=today - datetime.timedelta(days=30),
        employee_contribution_total=Decimal("200"), employer_contribution_total=Decimal("300"),
        headcount=5, status="pending", due_date=today + datetime.timedelta(days=10))
    sr_pt1 = StatutoryReturn.objects.create(
        tenant=tenant_a, scheme="pt", period_type="monthly",
        period_start=today - datetime.timedelta(days=45), period_end=today - datetime.timedelta(days=15),
        employee_contribution_total=Decimal("100"), employer_contribution_total=Decimal("0"),
        headcount=5, status="paid", due_date=today - datetime.timedelta(days=50))
    sr_lwf1 = StatutoryReturn.objects.create(
        tenant=tenant_a, scheme="lwf", period_type="half_yearly",
        period_start=today - datetime.timedelta(days=50), period_end=today + datetime.timedelta(days=130),
        employee_contribution_total=Decimal("50"), employer_contribution_total=Decimal("150"),
        headcount=5, status="pending", due_date=today - datetime.timedelta(days=20))
    sr_form16 = StatutoryReturn.objects.create(
        tenant=tenant_a, scheme="tds_form16", period_type="annual",
        period_start=today - datetime.timedelta(days=60), period_end=today + datetime.timedelta(days=300),
        employee_contribution_total=Decimal("9999"), employer_contribution_total=Decimal("9999"),
        headcount=99, status="pending", due_date=today - datetime.timedelta(days=10))

    emp1 = _mk_employee(tenant_a, "Stat Emp One", dept_a)
    emp2 = _mk_employee(tenant_a, "Stat Emp Two", dept_sales_a)
    ident1 = EmployeeStatutoryIdentifier.objects.create(
        tenant=tenant_a, employee=emp1, uan_number="111122223333", pf_number="KA/BLR/000111",
        esi_number="3111111111", is_pf_applicable=True, is_esi_applicable=True)
    ident2 = EmployeeStatutoryIdentifier.objects.create(
        tenant=tenant_a, employee=emp2, uan_number="444455556666", pf_number="MH/PUN/000222",
        esi_number="", is_pf_applicable=True, is_esi_applicable=False)

    return {
        "sr_pf1": sr_pf1, "sr_pf2": sr_pf2, "sr_esi1": sr_esi1, "sr_pt1": sr_pt1, "sr_lwf1": sr_lwf1,
        "sr_form16": sr_form16, "emp1": emp1, "emp2": emp2, "ident1": ident1, "ident2": ident2,
    }


# ------------------------------------------------------------------ 3.31 ctc-report fixtures
@pytest.fixture
def ctc_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """Hand-verified CTC dataset for tenant_a:

      tmpl_shared (job_grade=L1): line1 FIXED "Basic Shared" 60000 (ignores employee ctc), line2
        PCT-OF-CTC "Variable Shared" 20% (resolves against the EMPLOYEE's own annual_ctc_amount).
        emp1 (dept_a) assigned ctc=200000 -> line1=60000 line2=0.20*200000=40000 (row total via
          the two lines = 100000, though the row's displayed ``annual_ctc`` is just 200000).
        emp2 (dept_a) assigned ctc=50000  -> line1=60000 line2=0.20*50000=10000.
      tmpl_sales (job_grade=L2): line FIXED "Basic Sales" 50000.
        emp3 (dept_sales_a) assigned ctc=90000 -> line=50000 (fixed, ignores ctc).
      emp4_superseded: an EmployeeSalaryStructure with status="superseded" (annual_ctc=999999) —
        must NEVER be counted (status != "active").

    total_ctc=200000+50000+90000=340000 headcount=3 avg_ctc=113333.33.
    Component mix (earning only): emp1(60000+40000)+emp2(60000+10000)+emp3(50000) = 220000 — this
      is the ``resolved_amount(own_ctc)`` proof: a regression that resolved the pct line off the
      TEMPLATE's own annual_ctc_amount (100000) instead of each employee's assigned ctc would sum
      to 230000 (20000+20000 for both pct lines) instead of 220000 (40000+10000).
    dept_a-only: emp1,emp2 -> total=250000 headcount=2. dept_sales_a-only: emp3 -> total=90000 hc=1.
    grade L1-only: emp1,emp2 -> headcount=2 total=250000. grade L2-only: emp3 -> headcount=1 total=90000.
    """
    from apps.hrm.models import (JobGrade, PayComponent, SalaryStructureTemplate, SalaryStructureLine,
                                  EmployeeSalaryStructure)

    grade_l1 = JobGrade.objects.create(tenant=tenant_a, name="L1", level_order=1)
    grade_l2 = JobGrade.objects.create(tenant=tenant_a, name="L2", level_order=2)

    tmpl_shared = SalaryStructureTemplate.objects.create(
        tenant=tenant_a, name="Shared Template", annual_ctc_amount=Decimal("100000"), job_grade=grade_l1)
    basic_pc = PayComponent.objects.create(
        tenant=tenant_a, name="Basic Shared", component_type="earning", calculation_type="fixed_amount",
        default_amount=Decimal("60000"))
    var_pc = PayComponent.objects.create(
        tenant=tenant_a, name="Variable Shared", component_type="earning", calculation_type="pct_of_ctc")
    SalaryStructureLine.objects.create(
        tenant=tenant_a, template=tmpl_shared, pay_component=basic_pc, amount=Decimal("60000"), sequence=1)
    SalaryStructureLine.objects.create(
        tenant=tenant_a, template=tmpl_shared, pay_component=var_pc, percentage=Decimal("20"), sequence=2)

    tmpl_sales = SalaryStructureTemplate.objects.create(
        tenant=tenant_a, name="Sales Template", annual_ctc_amount=Decimal("90000"), job_grade=grade_l2)
    basic_sales_pc = PayComponent.objects.create(
        tenant=tenant_a, name="Basic Sales", component_type="earning", calculation_type="fixed_amount",
        default_amount=Decimal("50000"))
    SalaryStructureLine.objects.create(
        tenant=tenant_a, template=tmpl_sales, pay_component=basic_sales_pc, amount=Decimal("50000"), sequence=1)

    emp1 = _mk_employee(tenant_a, "CTC Emp One", dept_a)
    emp2 = _mk_employee(tenant_a, "CTC Emp Two", dept_a)
    emp3 = _mk_employee(tenant_a, "CTC Emp Three", dept_sales_a)
    emp4_superseded = _mk_employee(tenant_a, "CTC Emp Superseded", dept_a)

    ess1 = EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=emp1, template=tmpl_shared, annual_ctc_amount=Decimal("200000"), status="active")
    ess2 = EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=emp2, template=tmpl_shared, annual_ctc_amount=Decimal("50000"), status="active")
    ess3 = EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=emp3, template=tmpl_sales, annual_ctc_amount=Decimal("90000"), status="active")
    ess4 = EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=emp4_superseded, annual_ctc_amount=Decimal("999999"), status="superseded")

    return {
        "grade_l1": grade_l1, "grade_l2": grade_l2, "tmpl_shared": tmpl_shared, "tmpl_sales": tmpl_sales,
        "emp1": emp1, "emp2": emp2, "emp3": emp3, "emp4_superseded": emp4_superseded,
        "ess1": ess1, "ess2": ess2, "ess3": ess3, "ess4": ess4,
    }


@pytest.fixture
def ctc_bulk_data_a(db, tenant_a, dept_a, today):
    """2 distinct SalaryStructureTemplates x 3 employees each (6 total) — big enough that a
    per-employee (N+1) template-lines lookup would blow past a tight query-count ceiling, while
    ``ctc_report``'s ``template_lines`` cache (keyed by template_id, not employee_id) stays flat."""
    from apps.hrm.models import PayComponent, SalaryStructureTemplate, SalaryStructureLine, EmployeeSalaryStructure
    templates = []
    for t in range(2):
        tmpl = SalaryStructureTemplate.objects.create(
            tenant=tenant_a, name=f"Bulk Template {t}", annual_ctc_amount=Decimal("100000"))
        pc = PayComponent.objects.create(
            tenant=tenant_a, name=f"Basic Bulk {t}", component_type="earning",
            calculation_type="fixed_amount", default_amount=Decimal("50000"))
        SalaryStructureLine.objects.create(tenant=tenant_a, template=tmpl, pay_component=pc, amount=Decimal("50000"))
        templates.append(tmpl)
        for e in range(3):
            emp = _mk_employee(tenant_a, f"Bulk CTC Emp {t}-{e}", dept_a)
            EmployeeSalaryStructure.objects.create(
                tenant=tenant_a, employee=emp, template=tmpl,
                annual_ctc_amount=Decimal("100000"), status="active")
    return {"templates": templates}


# ------------------------------------------------------------------ 3.31 cost-center-report fixtures
@pytest.fixture
def cost_center_data_a(db, tenant_a, dept_a, dept_sales_a, today):
    """The attribution-fold dataset for tenant_a, budget year Y = today.year:

      dept_a -> DepartmentProfile.cost_center -> cc_eng (CostCenterProfile budget_annual=10000).
      dept_sales_a has NO DepartmentProfile mapping -> its spend lands in Unassigned.
      cc_marketing: a SECOND CostCenterProfile with budget_annual=None (no department maps to it
        -> actual=0, but ``variance`` must render None, not a phantom negative).
      cc_no_profile: a cost-centre OrgUnit with NO CostCenterProfile — a profile-less pk passed as
        ``?cost_center`` must resolve to None (fall back to "all"), never a 500/empty-filter.

      cycle1 (Y, Jan): emp_cc1 gross=5000 (employer PF=400); emp_cc2 gross=2000 (employer PF=150);
        emp_cc3 (dept_sales_a) gross=1500 (employer PF=100).
      cycle2 (Y, Feb): emp_cc1 gross=3000 (employer PF=240) — SAME employee, second cycle, same
        year -> proves headcount is DISTINCT-employee, not row count.
      cycle_prev_year (Y-1): emp_cc1 gross=9999 (employer PF=999) — must be EXCLUDED by the
        budget-year scope.

    cc_eng actual: gross=5000+2000+3000=10000 headcount=2 (emp_cc1,emp_cc2) employer=400+150+240=790.
      budget=10000 -> variance=0 variance_pct=0.0.
    Unassigned (dept_sales_a): gross=1500 headcount=1 employer=100.
    """
    from apps.core.models import OrgUnit
    from apps.hrm.models import DepartmentProfile, CostCenterProfile, PayrollCycle, Payslip, PayslipLine

    Y = today.year

    cc_eng = OrgUnit.objects.create(tenant=tenant_a, kind="cost_center", name="Engineering CC")
    DepartmentProfile.objects.create(tenant=tenant_a, org_unit=dept_a, cost_center=cc_eng)
    cc_profile_eng = CostCenterProfile.objects.create(
        tenant=tenant_a, org_unit=cc_eng, budget_annual=Decimal("10000"), budget_year=Y)

    cc_marketing = OrgUnit.objects.create(tenant=tenant_a, kind="cost_center", name="Marketing CC")
    cc_profile_marketing = CostCenterProfile.objects.create(
        tenant=tenant_a, org_unit=cc_marketing, budget_annual=None, budget_year=None)

    cc_no_profile = OrgUnit.objects.create(tenant=tenant_a, kind="cost_center", name="No Profile CC")

    cycle1 = PayrollCycle.objects.create(
        tenant=tenant_a, period_start=datetime.date(Y, 1, 1), period_end=datetime.date(Y, 1, 31),
        pay_date=datetime.date(Y, 1, 15), cycle_type="regular", status="locked")
    cycle2 = PayrollCycle.objects.create(
        tenant=tenant_a, period_start=datetime.date(Y, 2, 1), period_end=datetime.date(Y, 2, 28),
        pay_date=datetime.date(Y, 2, 15), cycle_type="regular", status="locked")
    cycle_prev_year = PayrollCycle.objects.create(
        tenant=tenant_a, period_start=datetime.date(Y - 1, 12, 1), period_end=datetime.date(Y - 1, 12, 31),
        pay_date=datetime.date(Y - 1, 12, 15), cycle_type="regular", status="locked")

    emp_cc1 = _mk_employee(tenant_a, "CC Emp One", dept_a)
    emp_cc2 = _mk_employee(tenant_a, "CC Emp Two", dept_a)
    emp_cc3 = _mk_employee(tenant_a, "CC Emp Three", dept_sales_a)

    def _ps(cycle, emp, gross):
        return Payslip.objects.create(tenant=tenant_a, cycle=cycle, employee=emp, gross_pay=Decimal(str(gross)))

    def _line(ps, amount):
        return PayslipLine.objects.create(
            tenant=tenant_a, payslip=ps, component_name="PF ER", component_type="statutory_deduction",
            amount=Decimal(str(amount)), contribution_side="employer")

    ps1 = _ps(cycle1, emp_cc1, 5000); _line(ps1, 400)
    ps2 = _ps(cycle2, emp_cc1, 3000); _line(ps2, 240)
    ps3 = _ps(cycle1, emp_cc2, 2000); _line(ps3, 150)
    ps_sales = _ps(cycle1, emp_cc3, 1500); _line(ps_sales, 100)
    ps_prev = _ps(cycle_prev_year, emp_cc1, 9999); _line(ps_prev, 999)

    return {
        "Y": Y, "cc_eng": cc_eng, "cc_profile_eng": cc_profile_eng,
        "cc_marketing": cc_marketing, "cc_profile_marketing": cc_profile_marketing,
        "cc_no_profile": cc_no_profile,
        "emp_cc1": emp_cc1, "emp_cc2": emp_cc2, "emp_cc3": emp_cc3,
        "cycle1": cycle1, "cycle2": cycle2, "cycle_prev_year": cycle_prev_year,
    }


@pytest.fixture
def cost_center_data_b(db, tenant_b, dept_b, today):
    """A genuine payroll + cost-centre-mapped dataset for tenant_b — proves tenant_a's
    cost_center_report totals never include it (not merely that a cross-tenant pk fails to
    resolve)."""
    from apps.core.models import OrgUnit
    from apps.hrm.models import DepartmentProfile, CostCenterProfile, PayrollCycle, Payslip

    Y = today.year
    cc_b = OrgUnit.objects.create(tenant=tenant_b, kind="cost_center", name="Globex Eng CC")
    DepartmentProfile.objects.create(tenant=tenant_b, org_unit=dept_b, cost_center=cc_b)
    CostCenterProfile.objects.create(tenant=tenant_b, org_unit=cc_b, budget_annual=Decimal("50000"), budget_year=Y)
    cycle_b = PayrollCycle.objects.create(
        tenant=tenant_b, period_start=datetime.date(Y, 1, 1), period_end=datetime.date(Y, 1, 31),
        pay_date=datetime.date(Y, 1, 15), cycle_type="regular", status="locked")
    emp_b = _mk_employee(tenant_b, "Globex CC Emp", dept_b)
    Payslip.objects.create(tenant=tenant_b, cycle=cycle_b, employee=emp_b, gross_pay=Decimal("99999"))
    return {"cc_b": cc_b}


def _qs(**extra):
    return {k: v for k, v in extra.items() if v is not None}


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
    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_no_params_200(self, client_a, url_name):
        resp = client_a.get(reverse(f"hrm:{url_name}"))
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_nonsensical_params_never_500(self, client_a, url_name):
        bad_params = {
            "department": "abc", "cycle": "abc", "financial_year": "9999-99", "scheme": "zzz",
            "status": "not_a_real_status", "grade": "abc", "cost_center": "abc", "year": "abc",
            "date_from": "not-a-date", "date_to": "2000-01-01", "regime": "bogus", "on_hold": "1",
        }
        resp = client_a.get(reverse(f"hrm:{url_name}"), bad_params)
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", REPORT_URL_NAMES)
    def test_far_future_params_never_500(self, client_a, url_name):
        resp = client_a.get(reverse(f"hrm:{url_name}"),
                             {"year": "9999", "financial_year": "9999-99", "cycle": "999999",
                              "grade": "999999", "cost_center": "999999",
                              "date_from": "9999-01-01", "date_to": "9999-12-31"})
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", ["salary_register_report", "tax_report", "ctc_report"])
    def test_unicode_superscript_department_never_500(self, client_a, url_name):
        """Regression guard: ``isdecimal()`` (not ``isdigit()``) rejects a Unicode superscript
        like "²" — ``int("²")`` would ValueError and 500 if the guard regressed to isdigit()."""
        resp = client_a.get(reverse(f"hrm:{url_name}"), {"department": "²"})
        assert resp.status_code == 200

    def test_ctc_unicode_superscript_grade_never_500(self, client_a):
        resp = client_a.get(reverse("hrm:ctc_report"), {"grade": "²"})
        assert resp.status_code == 200

    def test_cost_center_unicode_superscript_never_500(self, client_a):
        resp = client_a.get(reverse("hrm:cost_center_report"), {"cost_center": "²"})
        assert resp.status_code == 200

    @pytest.mark.parametrize("url_name", DATE_SCOPED_URL_NAMES)
    def test_reversed_date_range_clamped(self, client_a, today, url_name):
        future = today + datetime.timedelta(days=10)
        resp = client_a.get(reverse(f"hrm:{url_name}"),
                             {"date_from": future.isoformat(), "date_to": today.isoformat()})
        assert resp.status_code == 200
        assert resp.context["date_from"] == resp.context["date_to"] == today

    def test_salary_register_full_filter_set(self, client_a, salary_register_data_a, dept_a):
        resp = client_a.get(reverse("hrm:salary_register_report"),
                             {"cycle": salary_register_data_a["cycle_new"].pk, "department": dept_a.pk,
                              "on_hold": "1"})
        assert resp.status_code == 200

    def test_tax_full_filter_set(self, client_a, tax_data_a, dept_a):
        resp = client_a.get(reverse("hrm:tax_report"),
                             {"financial_year": tax_data_a["FY"], "department": dept_a.pk, "regime": "old"})
        assert resp.status_code == 200

    def test_statutory_full_filter_set(self, client_a, statutory_data_a):
        resp = client_a.get(reverse("hrm:statutory_report"),
                             {"scheme": "pf", "status": "pending",
                              "date_from": (timezone.localdate() - datetime.timedelta(days=200)).isoformat(),
                              "date_to": timezone.localdate().isoformat()})
        assert resp.status_code == 200

    def test_ctc_full_filter_set(self, client_a, ctc_data_a, dept_a):
        resp = client_a.get(reverse("hrm:ctc_report"),
                             {"department": dept_a.pk, "grade": ctc_data_a["grade_l1"].pk})
        assert resp.status_code == 200

    def test_cost_center_full_filter_set(self, client_a, cost_center_data_a):
        resp = client_a.get(reverse("hrm:cost_center_report"),
                             {"cost_center": cost_center_data_a["cc_eng"].pk,
                              "year": cost_center_data_a["Y"]})
        assert resp.status_code == 200


# ============================================================
# 3a. payroll_reports_index — tiles reflect the latest cycle + pending Form16 + overdue
# ============================================================

class TestPayrollReportsIndex:
    def test_tiles_reflect_latest_cycle(self, client_a, salary_register_data_a):
        resp = client_a.get(reverse("hrm:payroll_reports_index"))
        values = {t["label"]: t["value"] for t in resp.context["tiles"]}
        assert values["Latest Cycle Headcount"] == 4
        assert values["Latest Cycle Gross"] == "18,000"
        assert values["Latest Cycle Net"] == "16,200"

    def test_tiles_pending_form16_and_overdue(self, client_a, tax_data_a, statutory_data_a):
        resp = client_a.get(reverse("hrm:payroll_reports_index"))
        values = {t["label"]: t["value"] for t in resp.context["tiles"]}
        assert values["Pending Form 16"] == 2  # comp1, comp3 have no statutory_return link
        assert values["Overdue Statutory"] == 3  # sr_pf2 + sr_lwf1 + sr_form16 (all pending & overdue)


# ============================================================
# 3b. salary_register_report
# ============================================================

class TestSalaryRegisterReport:
    def test_defaults_to_latest_cycle_by_pay_date(self, client_a, salary_register_data_a):
        resp = client_a.get(reverse("hrm:salary_register_report"))
        assert resp.context["cycle"] == salary_register_data_a["cycle_new"]

    def test_totals_footer_unfiltered(self, client_a, salary_register_data_a):
        resp = client_a.get(reverse("hrm:salary_register_report"))
        assert len(resp.context["rows"]) == 4
        totals = resp.context["totals"]
        assert totals["gross"] == Decimal("18000")
        assert totals["ded"] == Decimal("1800")
        assert totals["net"] == Decimal("16200")
        assert totals["lop"] == Decimal("100")
        assert totals["arrears"] == Decimal("50")
        assert totals["bonus"] == Decimal("200")

    def test_cycle_param_selects_right_cycle(self, client_a, salary_register_data_a):
        data = salary_register_data_a
        resp = client_a.get(reverse("hrm:salary_register_report"), {"cycle": data["cycle_old"].pk})
        assert resp.context["cycle"] == data["cycle_old"]
        assert resp.context["rows"] == [data["ps_old"]]
        assert resp.context["totals"]["gross"] == Decimal("4800")
        assert resp.context["by_component"] == []  # ps_old has no PayslipLine rows

    def test_department_filter_scopes_rows_and_totals(self, client_a, salary_register_data_a, dept_a):
        resp = client_a.get(reverse("hrm:salary_register_report"), {"department": dept_a.pk})
        assert len(resp.context["rows"]) == 3  # ps1, ps2, ps_hold
        totals = resp.context["totals"]
        assert totals["gross"] == Decimal("14000")
        assert totals["ded"] == Decimal("1400")
        assert totals["net"] == Decimal("12600")

    def test_on_hold_filter_shows_only_on_hold(self, client_a, salary_register_data_a):
        data = salary_register_data_a
        resp = client_a.get(reverse("hrm:salary_register_report"), {"on_hold": "1"})
        assert resp.context["rows"] == [data["ps_hold"]]
        assert resp.context["totals"]["gross"] == Decimal("3000")

    def test_by_component_groups_payslip_lines_by_type(self, client_a, salary_register_data_a):
        resp = client_a.get(reverse("hrm:salary_register_report"))
        by_comp = {r["type"]: r["total"] for r in resp.context["by_component"]}
        assert by_comp["earning"] == Decimal("17000")
        assert by_comp["statutory_deduction"] == Decimal("2245")
        names = {r["name"] for r in resp.context["by_component"]}
        assert names == {"Earning", "Statutory Deduction"}

    def test_by_component_honors_department_scope(self, client_a, salary_register_data_a, dept_a):
        resp = client_a.get(reverse("hrm:salary_register_report"), {"department": dept_a.pk})
        by_comp = {r["type"]: r["total"] for r in resp.context["by_component"]}
        assert by_comp["earning"] == Decimal("13200")
        assert by_comp["statutory_deduction"] == Decimal("1825")


# ============================================================
# 3c. tax_report
# ============================================================

class TestTaxReport:
    def test_totals_unfiltered(self, client_a, tax_data_a):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"), {"financial_year": data["FY"]})
        assert resp.context["total_payable"] == Decimal("100000")
        assert resp.context["total_paid"] == Decimal("35000")
        assert resp.context["avg_payable"] == Decimal("33333.33")
        assert len(resp.context["rows"]) == 3

    def test_defaults_to_latest_financial_year(self, client_a, tax_data_a):
        resp = client_a.get(reverse("hrm:tax_report"))
        assert resp.context["financial_year"] == tax_data_a["FY"]

    def test_by_regime_split(self, client_a, tax_data_a):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"), {"financial_year": data["FY"]})
        by_regime = {r["name"]: r["count"] for r in resp.context["by_regime"]}
        assert by_regime == {"Old Regime": 2, "New Regime": 1}

    def test_decl_status_and_not_filed(self, client_a, tax_data_a):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"), {"financial_year": data["FY"]})
        decl_status = {r["name"]: r["count"] for r in resp.context["decl_status"]}
        assert decl_status == {"Submitted": 3}
        assert resp.context["not_filed"] == 1

    def test_not_filed_independent_of_department_and_regime_filters(self, client_a, tax_data_a, dept_a):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"),
                             {"financial_year": data["FY"], "department": dept_a.pk, "regime": "old"})
        assert resp.context["not_filed"] == 1

    def test_by_section_declared_and_verified_none_safe(self, client_a, tax_data_a):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"), {"financial_year": data["FY"]})
        by_section = {r["name"]: (r["declared"], r["verified"]) for r in resp.context["by_section"]}
        assert by_section["Section 80C"] == (Decimal("150000"), Decimal("90000"))
        assert by_section["HRA Exemption"] == (Decimal("20000"), Decimal("15000"))

    def test_form16_linked_vs_pending_split(self, client_a, tax_data_a):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"), {"financial_year": data["FY"]})
        rows = resp.context["rows"]
        linked = [r for r in rows if r.statutory_return_id]
        pending = [r for r in rows if not r.statutory_return_id]
        assert len(linked) == 1
        assert linked[0].pk == data["comp2"].pk
        assert len(pending) == 2
        assert {r.pk for r in pending} == {data["comp1"].pk, data["comp3"].pk}

    def test_department_filter_scopes_totals(self, client_a, tax_data_a, dept_a, dept_sales_a):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"), {"financial_year": data["FY"], "department": dept_a.pk})
        assert resp.context["total_payable"] == Decimal("80000")
        assert len(resp.context["rows"]) == 2

        resp2 = client_a.get(reverse("hrm:tax_report"),
                              {"financial_year": data["FY"], "department": dept_sales_a.pk})
        assert resp2.context["total_payable"] == Decimal("20000")
        assert len(resp2.context["rows"]) == 1

    def test_regime_filter_scopes_totals(self, client_a, tax_data_a):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"), {"financial_year": data["FY"], "regime": "old"})
        assert resp.context["total_payable"] == Decimal("70000")
        resp2 = client_a.get(reverse("hrm:tax_report"), {"financial_year": data["FY"], "regime": "new"})
        assert resp2.context["total_payable"] == Decimal("30000")

    def test_avg_payable_guarded_when_department_excludes_all_rows(self, client_a, tax_data_a, dept_empty_a):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"),
                             {"financial_year": data["FY"], "department": dept_empty_a.pk})
        assert resp.context["rows"] == []
        assert resp.context["avg_payable"] == 0


# ============================================================
# 3d. statutory_report
# ============================================================

class TestStatutoryReport:
    def test_default_scheme_is_pf(self, client_a, statutory_data_a):
        resp = client_a.get(reverse("hrm:statutory_report"))
        assert resp.context["scheme"] == "pf"
        data = statutory_data_a
        assert {r.pk for r in resp.context["rows"]} == {data["sr_pf1"].pk, data["sr_pf2"].pk}

    def test_pf_totals_and_overdue(self, client_a, statutory_data_a):
        resp = client_a.get(reverse("hrm:statutory_report"), {"scheme": "pf"})
        assert resp.context["emp_total"] == Decimal("1800")
        assert resp.context["empr_total"] == Decimal("2100")
        assert resp.context["headcount_total"] == 9
        assert resp.context["overdue"] == 1

    def test_esi_scheme_scopes_rows(self, client_a, statutory_data_a):
        data = statutory_data_a
        resp = client_a.get(reverse("hrm:statutory_report"), {"scheme": "esi"})
        assert [r.pk for r in resp.context["rows"]] == [data["sr_esi1"].pk]
        assert resp.context["emp_total"] == Decimal("200")
        assert resp.context["overdue"] == 0  # due_date is in the future

    def test_pt_scheme_paid_not_overdue(self, client_a, statutory_data_a):
        resp = client_a.get(reverse("hrm:statutory_report"), {"scheme": "pt"})
        assert resp.context["overdue"] == 0

    def test_lwf_scheme_pending_overdue(self, client_a, statutory_data_a):
        resp = client_a.get(reverse("hrm:statutory_report"), {"scheme": "lwf"})
        assert resp.context["overdue"] == 1

    def test_tds_form16_never_appears_in_any_selectable_scheme(self, client_a, statutory_data_a):
        data = statutory_data_a
        for scheme in ("pf", "esi", "pt", "lwf", "tds_form16", "tds_24q"):
            resp = client_a.get(reverse("hrm:statutory_report"), {"scheme": scheme})
            pks = {r.pk for r in resp.context["rows"]}
            assert data["sr_form16"].pk not in pks

    def test_status_filter_scopes_pf_register(self, client_a, statutory_data_a):
        data = statutory_data_a
        resp = client_a.get(reverse("hrm:statutory_report"), {"scheme": "pf", "status": "pending"})
        assert [r.pk for r in resp.context["rows"]] == [data["sr_pf2"].pk]

    def test_coverage_counts(self, client_a, statutory_data_a):
        resp = client_a.get(reverse("hrm:statutory_report"))
        assert resp.context["coverage"] == {"pf": 2, "esi": 1, "total": 2}

    def test_masked_identifiers_never_leak_raw_values(self, client_a, statutory_data_a):
        data = statutory_data_a
        resp = client_a.get(reverse("hrm:statutory_report"))
        content = resp.content.decode()
        # Raw sensitive values must NEVER appear in the rendered response.
        assert "111122223333" not in content
        assert "KA/BLR/000111" not in content
        assert "3111111111" not in content
        assert "444455556666" not in content
        assert "MH/PUN/000222" not in content
        # Masked forms (last-4 only) must be present instead.
        assert data["ident1"].masked_uan_number() in content
        assert data["ident1"].masked_pf_number() in content
        assert data["ident1"].masked_esi_number() in content
        assert data["ident2"].masked_uan_number() in content


# ============================================================
# 3e. ctc_report
# ============================================================

class TestCtcReport:
    def test_totals_unfiltered(self, client_a, ctc_data_a):
        resp = client_a.get(reverse("hrm:ctc_report"))
        assert resp.context["total_ctc"] == Decimal("340000")
        assert resp.context["headcount"] == 3
        assert resp.context["avg_ctc"] == Decimal("113333.33")

    def test_superseded_structure_excluded(self, client_a, ctc_data_a):
        resp = client_a.get(reverse("hrm:ctc_report"))
        names = {r["employee"] for r in resp.context["rows"]}
        assert "CTC Emp Superseded" not in names

    def test_component_mix_uses_each_employees_own_ctc(self, client_a, ctc_data_a):
        """Locks in ``resolved_amount(own_ctc)``: emp1 (ctc=200000) and emp2 (ctc=50000) share
        ``tmpl_shared`` but their pct-of-ctc line resolves DIFFERENTLY (40000 vs 10000) — the
        earning mix total is 220000, NOT 230000 (which is what a regression resolving the pct
        line off the template's own annual_ctc_amount for both employees would produce)."""
        import json
        resp = client_a.get(reverse("hrm:ctc_report"))
        labels = json.loads(resp.context["mix_labels"])
        values = json.loads(resp.context["mix_values"])
        mix = dict(zip(labels, values))
        assert mix == {"Earning": 220000.0}

    def test_department_filter_scopes_totals(self, client_a, ctc_data_a, dept_a, dept_sales_a):
        resp = client_a.get(reverse("hrm:ctc_report"), {"department": dept_a.pk})
        assert resp.context["headcount"] == 2
        assert resp.context["total_ctc"] == Decimal("250000")

        resp2 = client_a.get(reverse("hrm:ctc_report"), {"department": dept_sales_a.pk})
        assert resp2.context["headcount"] == 1
        assert resp2.context["total_ctc"] == Decimal("90000")

    def test_grade_filter_scopes_totals(self, client_a, ctc_data_a):
        data = ctc_data_a
        resp = client_a.get(reverse("hrm:ctc_report"), {"grade": data["grade_l1"].pk})
        assert resp.context["headcount"] == 2
        assert resp.context["total_ctc"] == Decimal("250000")

        resp2 = client_a.get(reverse("hrm:ctc_report"), {"grade": data["grade_l2"].pk})
        assert resp2.context["headcount"] == 1
        assert resp2.context["total_ctc"] == Decimal("90000")


# ============================================================
# 3f. cost_center_report
# ============================================================

class TestCostCenterReport:
    def test_cc_eng_actual_matches_department_attribution(self, client_a, cost_center_data_a):
        resp = client_a.get(reverse("hrm:cost_center_report"), {"year": cost_center_data_a["Y"]})
        rows = {r["name"]: r for r in resp.context["rows"]}
        eng = rows["Engineering CC"]
        assert eng["actual"] == Decimal("10000")
        assert eng["headcount"] == 2
        assert eng["employer"] == Decimal("790")
        assert eng["budget"] == Decimal("10000")
        assert eng["variance"] == Decimal("0")
        assert eng["variance_pct"] == 0.0

    def test_headcount_is_distinct_employee_across_cycles(self, client_a, cost_center_data_a):
        """emp_cc1 has TWO payslips (cycle1 + cycle2, same year) — Engineering CC's headcount must
        still be 2 (emp_cc1, emp_cc2), not 3."""
        resp = client_a.get(reverse("hrm:cost_center_report"), {"year": cost_center_data_a["Y"]})
        eng = next(r for r in resp.context["rows"] if r["name"] == "Engineering CC")
        assert eng["headcount"] == 2

    def test_prev_year_payroll_excluded_by_budget_year_scope(self, client_a, cost_center_data_a):
        """The 9999-gross prev-year payslip must not inflate the current year's actual."""
        resp = client_a.get(reverse("hrm:cost_center_report"), {"year": cost_center_data_a["Y"]})
        eng = next(r for r in resp.context["rows"] if r["name"] == "Engineering CC")
        assert eng["actual"] == Decimal("10000")  # not 10000+9999

    def test_unassigned_bucket_for_unmapped_department(self, client_a, cost_center_data_a):
        resp = client_a.get(reverse("hrm:cost_center_report"), {"year": cost_center_data_a["Y"]})
        unassigned = resp.context["unassigned"]
        assert unassigned["gross"] == Decimal("1500")
        assert unassigned["hc"] == 1
        assert unassigned["employer"] == Decimal("100")

    def test_variance_none_when_budget_annual_is_none(self, client_a, cost_center_data_a):
        resp = client_a.get(reverse("hrm:cost_center_report"), {"year": cost_center_data_a["Y"]})
        marketing = next(r for r in resp.context["rows"] if r["name"] == "Marketing CC")
        assert marketing["budget"] is None
        assert marketing["variance"] is None
        assert marketing["variance_pct"] is None

    def test_cost_center_filter_scopes_rows_and_hides_unassigned(self, client_a, cost_center_data_a):
        data = cost_center_data_a
        resp = client_a.get(reverse("hrm:cost_center_report"),
                             {"cost_center": data["cc_eng"].pk, "year": data["Y"]})
        assert len(resp.context["rows"]) == 1
        assert resp.context["rows"][0]["name"] == "Engineering CC"
        assert resp.context["unassigned"] is None  # only surfaced on the unfiltered view

    def test_profile_less_cost_center_pk_falls_back_to_all(self, client_a, cost_center_data_a):
        data = cost_center_data_a
        resp = client_a.get(reverse("hrm:cost_center_report"),
                             {"cost_center": data["cc_no_profile"].pk, "year": data["Y"]})
        assert resp.context["cost_center"] is None
        assert len(resp.context["rows"]) == 2  # Engineering CC + Marketing CC

    def test_budget_year_default_is_current_year(self, client_a, cost_center_data_a, today):
        resp = client_a.get(reverse("hrm:cost_center_report"))
        assert resp.context["budget_year"] == today.year


# ============================================================
# 4. Multi-tenant isolation / IDOR
# ============================================================

class TestMultiTenantIsolation:
    def test_salary_register_excludes_other_tenant_cycle(self, client_a, salary_register_data_a, cycle_b):
        resp = client_a.get(reverse("hrm:salary_register_report"))
        cycle_pks = {c.pk for c in resp.context["cycle_choices"]}
        assert cycle_b.pk not in cycle_pks

    def test_salary_register_cross_tenant_cycle_pk_falls_back_to_default(
            self, client_a, salary_register_data_a, cycle_b):
        resp = client_a.get(reverse("hrm:salary_register_report"), {"cycle": cycle_b.pk})
        assert resp.context["cycle"] == salary_register_data_a["cycle_new"]

    def test_salary_register_cross_tenant_department_pk_ignored(self, client_a, salary_register_data_a, dept_b):
        resp = client_a.get(reverse("hrm:salary_register_report"), {"department": dept_b.pk})
        assert resp.context["department"] is None
        assert len(resp.context["rows"]) == 4

    def test_tax_excludes_other_tenant_even_with_matching_fy(
            self, client_a, tax_data_a, tax_computation_b_matching_fy):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"), {"financial_year": data["FY"]})
        assert resp.context["total_payable"] == Decimal("100000")
        assert len(resp.context["rows"]) == 3

    def test_tax_cross_tenant_department_pk_ignored(self, client_a, tax_data_a, dept_b):
        data = tax_data_a
        resp = client_a.get(reverse("hrm:tax_report"), {"financial_year": data["FY"], "department": dept_b.pk})
        assert resp.context["department"] is None
        assert resp.context["total_payable"] == Decimal("100000")

    def test_statutory_excludes_other_tenant(self, client_a, statutory_data_a, statutory_return_b):
        resp = client_a.get(reverse("hrm:statutory_report"), {"scheme": "pf"})
        assert resp.context["emp_total"] == Decimal("1800")  # statutory_return_b never counted

    def test_ctc_excludes_other_tenant(self, client_a, ctc_data_a, employee_salary_structure_b):
        resp = client_a.get(reverse("hrm:ctc_report"))
        assert resp.context["headcount"] == 3
        assert resp.context["total_ctc"] == Decimal("340000")

    def test_ctc_cross_tenant_grade_pk_ignored(self, client_a, ctc_data_a, grade_b):
        resp = client_a.get(reverse("hrm:ctc_report"), {"grade": grade_b.pk})
        assert resp.context["grade"] is None
        assert resp.context["headcount"] == 3

    def test_ctc_cross_tenant_department_pk_ignored(self, client_a, ctc_data_a, dept_b):
        resp = client_a.get(reverse("hrm:ctc_report"), {"department": dept_b.pk})
        assert resp.context["department"] is None
        assert resp.context["headcount"] == 3

    def test_cost_center_excludes_other_tenant(self, client_a, cost_center_data_a, cost_center_data_b):
        data = cost_center_data_a
        resp = client_a.get(reverse("hrm:cost_center_report"), {"year": data["Y"]})
        eng = next(r for r in resp.context["rows"] if r["name"] == "Engineering CC")
        assert eng["actual"] == Decimal("10000")  # tenant_b's 99999 never folds in
        assert resp.context["total_actual"] == Decimal("10000")

    def test_cost_center_cross_tenant_pk_ignored(self, client_a, cost_center_data_a, cost_center_data_b):
        resp = client_a.get(reverse("hrm:cost_center_report"),
                             {"cost_center": cost_center_data_b["cc_b"].pk, "year": cost_center_data_a["Y"]})
        assert resp.context["cost_center"] is None
        assert len(resp.context["rows"]) == 2

    def test_tenant_b_admin_never_sees_tenant_a_salary_register(self, client_b, salary_register_data_a):
        resp = client_b.get(reverse("hrm:salary_register_report"))
        assert resp.context["cycle"] is None
        assert resp.context["rows"] == []

    def test_tenant_b_admin_never_sees_tenant_a_ctc(self, client_b, ctc_data_a):
        resp = client_b.get(reverse("hrm:ctc_report"))
        assert resp.context["headcount"] == 0


# ============================================================
# 5. Div-by-zero — a fully empty tenant renders every report at 200 with zero/empty KPIs
# ============================================================

class TestEmptyTenantDivByZero:
    def test_payroll_reports_index_empty_tenant_tiles(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:payroll_reports_index"))
        assert resp.status_code == 200
        assert len(resp.context["tiles"]) == 5
        values = {t["label"]: t["value"] for t in resp.context["tiles"]}
        assert values["Latest Cycle Headcount"] == 0
        assert values["Pending Form 16"] == 0
        assert values["Overdue Statutory"] == 0

    def test_salary_register_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:salary_register_report"))
        assert resp.status_code == 200
        assert resp.context["cycle"] is None
        assert resp.context["rows"] == []
        assert resp.context["totals"] == {}
        assert resp.context["by_component"] == []

    def test_tax_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:tax_report"))
        assert resp.status_code == 200
        assert resp.context["financial_year"] == ""
        assert resp.context["rows"] == []
        assert resp.context["total_payable"] == 0
        assert resp.context["total_paid"] == 0
        assert resp.context["avg_payable"] == 0
        assert resp.context["not_filed"] == 0
        assert resp.context["by_regime"] == []
        assert resp.context["by_section"] == []

    def test_statutory_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:statutory_report"))
        assert resp.status_code == 200
        assert resp.context["rows"] == []
        assert resp.context["emp_total"] == 0
        assert resp.context["empr_total"] == 0
        assert resp.context["headcount_total"] == 0
        assert resp.context["overdue"] == 0
        assert resp.context["identifiers"] == []
        assert resp.context["coverage"] == {"pf": 0, "esi": 0, "total": 0}

    def test_ctc_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:ctc_report"))
        assert resp.status_code == 200
        assert resp.context["rows"] == []
        assert resp.context["total_ctc"] == 0
        assert resp.context["avg_ctc"] == 0
        assert resp.context["headcount"] == 0

    def test_cost_center_zero_kpis(self, client_a, tenant_a):
        resp = client_a.get(reverse("hrm:cost_center_report"))
        assert resp.status_code == 200
        assert resp.context["rows"] == []
        assert resp.context["total_budget"] == 0
        assert resp.context["total_actual"] == 0
        assert resp.context["unassigned"] is None

    def test_no_tenant_superuser_index_no_error(self, admin_user):
        """A tenant-less superuser (request.tenant is None) gets an empty tiles list, not a 500
        (mirrors the leave/attendance/hr_reports_index convention)."""
        from django.test import Client
        from apps.accounts.models import User
        superuser = User.objects.create_superuser(
            email="super_payroll@example.com", username="super_payroll", password="TestPass123!")
        c = Client()
        c.force_login(superuser)
        resp = c.get(reverse("hrm:payroll_reports_index"))
        assert resp.status_code == 200
        assert resp.context["tiles"] == []


# ============================================================
# 6. Query-count ceilings (N+1 guard)
# ============================================================

class TestQueryCounts:
    def test_salary_register_report_query_count_bounded(self, client_a, salary_register_data_a,
                                                         django_assert_max_num_queries):
        with django_assert_max_num_queries(25):
            client_a.get(reverse("hrm:salary_register_report"))

    def test_tax_report_query_count_bounded(self, client_a, tax_data_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(25):
            client_a.get(reverse("hrm:tax_report"), {"financial_year": tax_data_a["FY"]})

    def test_statutory_report_query_count_bounded(self, client_a, statutory_data_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(25):
            client_a.get(reverse("hrm:statutory_report"))

    def test_ctc_report_query_count_bounded_across_multiple_templates(
            self, client_a, ctc_bulk_data_a, django_assert_max_num_queries):
        """2 templates x 3 employees each (6 structs) — a per-employee template-lines lookup would
        add extra queries per employee beyond the first two; the ``template_lines`` cache (keyed
        by template_id) keeps this flat regardless of headcount."""
        with django_assert_max_num_queries(25):
            client_a.get(reverse("hrm:ctc_report"))

    def test_cost_center_report_query_count_bounded(self, client_a, cost_center_data_a,
                                                     django_assert_max_num_queries):
        with django_assert_max_num_queries(25):
            client_a.get(reverse("hrm:cost_center_report"), {"year": cost_center_data_a["Y"]})
