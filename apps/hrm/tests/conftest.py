"""HRM app test fixtures.

Reuses the shared root conftest (tenant_a, tenant_b, admin_user, admin_b,
client_a, client_b, member_user, member_client) and adds HRM-specific records:
Party persons, Employment, OrgUnit department, Designation, EmployeeProfile,
LeaveType, LeaveAllocation, LeaveRequest, Shift, AttendanceRecord.
"""
import datetime
from decimal import Decimal

import pytest
from django.utils import timezone


# ------------------------------------------------------------------ Core spine helpers
@pytest.fixture
def dept_a(db, tenant_a):
    """An OrgUnit department for tenant_a."""
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_a, kind="department", name="Engineering")


@pytest.fixture
def dept_b(db, tenant_b):
    """An OrgUnit department for tenant_b."""
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant_b, kind="department", name="Engineering B")


@pytest.fixture
def person_a(db, tenant_a):
    """A person Party for tenant_a (the employee's identity)."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="person", name="Alice Smith")


@pytest.fixture
def person_b(db, tenant_b):
    """A person Party for tenant_b."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, kind="person", name="Bob Jones")


@pytest.fixture
def person_a2(db, tenant_a):
    """A second person Party for tenant_a (used for manager / extra employees)."""
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, kind="person", name="Carol White")


@pytest.fixture
def employment_a(db, tenant_a, person_a, dept_a):
    """An Employment for person_a in tenant_a."""
    from apps.core.models import Employment
    return Employment.objects.create(
        tenant=tenant_a,
        party=person_a,
        org_unit=dept_a,
        job_title="Software Engineer",
        hired_on=datetime.date(2023, 1, 1),
        status="active",
    )


@pytest.fixture
def employment_b(db, tenant_b, person_b, dept_b):
    """An Employment for person_b in tenant_b."""
    from apps.core.models import Employment
    return Employment.objects.create(
        tenant=tenant_b,
        party=person_b,
        org_unit=dept_b,
        job_title="Analyst",
        status="active",
    )


# ------------------------------------------------------------------ Designation fixtures
@pytest.fixture
def designation_a(db, tenant_a, dept_a):
    """A Designation for tenant_a."""
    from apps.hrm.models import Designation
    return Designation.objects.create(
        tenant=tenant_a,
        name="Software Engineer",
        grade="L2",
        department=dept_a,
        min_salary=Decimal("60000"),
        max_salary=Decimal("90000"),
    )


@pytest.fixture
def designation_b(db, tenant_b):
    """A Designation for tenant_b."""
    from apps.hrm.models import Designation
    return Designation.objects.create(
        tenant=tenant_b,
        name="Analyst B",
        grade="L1",
    )


# ------------------------------------------------------------------ EmployeeProfile fixtures
@pytest.fixture
def employee_a(db, tenant_a, person_a, employment_a, designation_a):
    """An EmployeeProfile for tenant_a."""
    from apps.hrm.models import EmployeeProfile
    return EmployeeProfile.objects.create(
        tenant=tenant_a,
        party=person_a,
        employment=employment_a,
        designation=designation_a,
        employee_type="full_time",
        gender="female",
        date_of_birth=datetime.date(1990, 5, 15),
        bank_name="First Bank",
        bank_account="123456789012",
        bank_routing="DEMO0001",
        personal_email="alice@example.com",
        mobile="+1-555-0100",
        emergency_contact_name="Bob Smith",
        emergency_contact_phone="+1-555-9999",
        emergency_contact_relation="Spouse",
    )


@pytest.fixture
def employee_a2(db, tenant_a, person_a2, dept_a, designation_a):
    """A second EmployeeProfile for tenant_a (used for 3.14 payroll multi-employee cycle/CTC tests)."""
    from apps.core.models import Employment
    from apps.hrm.models import EmployeeProfile
    employment = Employment.objects.create(
        tenant=tenant_a,
        party=person_a2,
        org_unit=dept_a,
        job_title="Senior Software Engineer",
        hired_on=datetime.date(2023, 1, 1),
        status="active",
    )
    return EmployeeProfile.objects.create(
        tenant=tenant_a,
        party=person_a2,
        employment=employment,
        designation=designation_a,
        employee_type="full_time",
    )


@pytest.fixture
def employee_b(db, tenant_b, person_b, employment_b, designation_b):
    """An EmployeeProfile for tenant_b (used in IDOR tests)."""
    from apps.hrm.models import EmployeeProfile
    return EmployeeProfile.objects.create(
        tenant=tenant_b,
        party=person_b,
        employment=employment_b,
        designation=designation_b,
        employee_type="full_time",
    )


# ------------------------------------------------------------------ LeaveType fixtures
@pytest.fixture
def leave_type_a(db, tenant_a):
    """An annual LeaveType for tenant_a."""
    from apps.hrm.models import LeaveType
    return LeaveType.objects.create(
        tenant=tenant_a,
        name="Annual Leave",
        code="AL",
        is_paid=True,
        accrual_rule="annual",
        accrual_days=Decimal("21"),
        max_balance=Decimal("30"),
        max_carry_forward=Decimal("5"),
        encashable=True,
    )


@pytest.fixture
def leave_type_b(db, tenant_b):
    """A LeaveType for tenant_b (IDOR tests)."""
    from apps.hrm.models import LeaveType
    return LeaveType.objects.create(
        tenant=tenant_b,
        name="Sick Leave B",
        code="SLB",
        is_paid=True,
        accrual_rule="monthly",
        accrual_days=Decimal("1.5"),
    )


# ------------------------------------------------------------------ LeaveAllocation fixtures
@pytest.fixture
def leave_allocation_a(db, tenant_a, employee_a, leave_type_a):
    """A leave allocation for employee_a/tenant_a, current year."""
    from apps.hrm.models import LeaveAllocation
    return LeaveAllocation.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        leave_type=leave_type_a,
        year=2026,
        allocated_days=Decimal("21"),
        status="active",
    )


# ------------------------------------------------------------------ LeaveRequest fixtures
@pytest.fixture
def draft_leave_request(db, tenant_a, employee_a, leave_type_a):
    """A draft leave request for employee_a, tenant_a."""
    from apps.hrm.models import LeaveRequest
    return LeaveRequest.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        leave_type=leave_type_a,
        start_date=datetime.date(2026, 7, 1),
        end_date=datetime.date(2026, 7, 3),
        reason="Vacation",
        status="draft",
    )


@pytest.fixture
def pending_leave_request(db, tenant_a, employee_a, leave_type_a):
    """A pending leave request for employee_a, tenant_a."""
    from apps.hrm.models import LeaveRequest
    lr = LeaveRequest.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        leave_type=leave_type_a,
        start_date=datetime.date(2026, 8, 1),
        end_date=datetime.date(2026, 8, 5),
        reason="Rest",
        status="pending",
    )
    return lr


@pytest.fixture
def leave_request_b(db, tenant_b, employee_b, leave_type_b):
    """A draft leave request belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import LeaveRequest
    return LeaveRequest.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        leave_type=leave_type_b,
        start_date=datetime.date(2026, 9, 1),
        end_date=datetime.date(2026, 9, 2),
        reason="Rest B",
        status="draft",
    )


# ------------------------------------------------------------------ Shift fixtures
@pytest.fixture
def shift_a(db, tenant_a):
    """A morning shift for tenant_a."""
    from apps.hrm.models import Shift
    return Shift.objects.create(
        tenant=tenant_a,
        name="Morning Shift",
        start_time=datetime.time(9, 0),
        end_time=datetime.time(18, 0),
        grace_minutes=15,
        is_default=True,
    )


@pytest.fixture
def shift_b(db, tenant_b):
    """A shift for tenant_b (IDOR tests)."""
    from apps.hrm.models import Shift
    return Shift.objects.create(
        tenant=tenant_b,
        name="Morning B",
        start_time=datetime.time(9, 0),
        end_time=datetime.time(17, 0),
        grace_minutes=10,
    )


# ------------------------------------------------------------------ AttendanceRecord fixtures
@pytest.fixture
def attendance_a(db, tenant_a, employee_a, shift_a):
    """An attendance record for employee_a, tenant_a."""
    from apps.hrm.models import AttendanceRecord
    return AttendanceRecord.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        date=datetime.date(2026, 6, 16),
        check_in=datetime.time(9, 5),
        check_out=datetime.time(18, 0),
        shift=shift_a,
        status="present",
        source="web",
    )


@pytest.fixture
def attendance_b(db, tenant_b, employee_b, shift_b):
    """An attendance record for employee_b, tenant_b (IDOR tests)."""
    from apps.hrm.models import AttendanceRecord
    return AttendanceRecord.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        date=datetime.date(2026, 6, 16),
        check_in=datetime.time(9, 0),
        check_out=datetime.time(17, 0),
        shift=shift_b,
        status="present",
        source="web",
    )


# ------------------------------------------------------------------ PublicHoliday fixtures
@pytest.fixture
def holiday_a(db, tenant_a):
    """A non-optional public holiday for tenant_a on 2026-07-04."""
    from apps.hrm.models import PublicHoliday
    return PublicHoliday.objects.create(
        tenant=tenant_a,
        date=datetime.date(2026, 7, 4),
        name="Founders Day",
        is_optional=False,
    )


# ------------------------------------------------------------------ 3.12 Holiday Management fixtures
@pytest.fixture
def optional_holiday_a(db, tenant_a):
    """An optional (floating) public holiday for tenant_a, same year as holiday_a."""
    from apps.hrm.models import PublicHoliday
    return PublicHoliday.objects.create(
        tenant=tenant_a,
        date=datetime.date(2026, 10, 20),
        name="Diwali",
        is_optional=True,
    )


@pytest.fixture
def optional_holiday_a2(db, tenant_a):
    """A second optional (floating) public holiday for tenant_a, same year."""
    from apps.hrm.models import PublicHoliday
    return PublicHoliday.objects.create(
        tenant=tenant_a,
        date=datetime.date(2026, 12, 24),
        name="Christmas Eve",
        is_optional=True,
    )


@pytest.fixture
def optional_holiday_b(db, tenant_b):
    """An optional public holiday belonging to tenant_b (IDOR / isolation tests)."""
    from apps.hrm.models import PublicHoliday
    return PublicHoliday.objects.create(
        tenant=tenant_b,
        date=datetime.date(2026, 10, 20),
        name="Diwali B",
        is_optional=True,
    )


@pytest.fixture
def default_holiday_policy_a(db, tenant_a):
    """The tenant-wide default HolidayPolicy for tenant_a — quota=1."""
    from apps.hrm.models import HolidayPolicy
    return HolidayPolicy.objects.create(
        tenant=tenant_a,
        name="Company Default",
        is_default=True,
        floating_holiday_quota=1,
    )


@pytest.fixture
def holiday_policy_b(db, tenant_b):
    """A HolidayPolicy belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import HolidayPolicy
    return HolidayPolicy.objects.create(
        tenant=tenant_b,
        name="Globex Default",
        is_default=True,
        floating_holiday_quota=2,
    )


@pytest.fixture
def pending_election_a(db, tenant_a, employee_a, optional_holiday_a, default_holiday_policy_a):
    """A pending FloatingHolidayElection for employee_a/tenant_a."""
    from apps.hrm.models import FloatingHolidayElection
    return FloatingHolidayElection.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        holiday=optional_holiday_a,
        status="pending",
    )


@pytest.fixture
def election_b(db, tenant_b, employee_b, optional_holiday_b, holiday_policy_b):
    """A pending FloatingHolidayElection belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import FloatingHolidayElection
    return FloatingHolidayElection.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        holiday=optional_holiday_b,
        status="pending",
    )


# ------------------------------------------------------------------ 3.11 Time Tracking fixtures
@pytest.fixture
def project_a(db, tenant_a):
    """An accounting.Project for tenant_a (2.9 job-costing spine, optional FK on TimesheetEntry)."""
    from apps.accounting.models_advanced import Project
    return Project.objects.create(
        tenant=tenant_a, name="Website Revamp", budget_amount=Decimal("50000"),
    )


@pytest.fixture
def project_b(db, tenant_b):
    """An accounting.Project for tenant_b (IDOR tests)."""
    from apps.accounting.models_advanced import Project
    return Project.objects.create(
        tenant=tenant_b, name="Globex Migration", budget_amount=Decimal("20000"),
    )


@pytest.fixture
def draft_timesheet_a(db, tenant_a, employee_a):
    """A draft Timesheet for employee_a, tenant_a — period 2026-06-01..2026-06-07."""
    from apps.hrm.models import Timesheet
    return Timesheet.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        period_start=datetime.date(2026, 6, 1),
        period_end=datetime.date(2026, 6, 7),
        status="draft",
    )


@pytest.fixture
def pending_timesheet_a(db, draft_timesheet_a):
    """A pending Timesheet for employee_a (submitted)."""
    draft_timesheet_a.status = "pending"
    draft_timesheet_a.save(update_fields=["status", "updated_at"])
    return draft_timesheet_a


@pytest.fixture
def timesheet_entry_a(db, tenant_a, draft_timesheet_a, project_a):
    """A billable TimesheetEntry on draft_timesheet_a: 2026-06-02, 8h @ 50/h, billable."""
    from apps.hrm.models import TimesheetEntry
    entry = TimesheetEntry.objects.create(
        tenant=tenant_a, timesheet=draft_timesheet_a, date=datetime.date(2026, 6, 2),
        project=project_a, task_description="Design review", hours=Decimal("8"),
        is_billable=True, billable_rate=Decimal("50"),
    )
    draft_timesheet_a.refresh_totals()
    return entry


@pytest.fixture
def timesheet_b(db, tenant_b, employee_b):
    """A draft Timesheet belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import Timesheet
    return Timesheet.objects.create(
        tenant=tenant_b, employee=employee_b,
        period_start=datetime.date(2026, 6, 1), period_end=datetime.date(2026, 6, 7),
        status="pending",
    )


@pytest.fixture
def timesheet_entry_b(db, tenant_b, timesheet_b):
    """A TimesheetEntry belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TimesheetEntry
    entry = TimesheetEntry.objects.create(
        tenant=tenant_b, timesheet=timesheet_b, date=datetime.date(2026, 6, 2),
        hours=Decimal("4"), is_billable=True, billable_rate=Decimal("40"),
    )
    timesheet_b.refresh_totals()
    return entry


@pytest.fixture
def draft_overtime_a(db, tenant_a, employee_a):
    """A draft OvertimeRequest for employee_a, tenant_a: 3h @ 1.5x on 2026-06-02."""
    from apps.hrm.models import OvertimeRequest
    return OvertimeRequest.objects.create(
        tenant=tenant_a, employee=employee_a, date=datetime.date(2026, 6, 2),
        hours_claimed=Decimal("3"), multiplier=Decimal("1.50"),
        payout_method="pay", reason="Production release support", status="draft",
    )


@pytest.fixture
def pending_overtime_a(db, draft_overtime_a):
    """A pending OvertimeRequest for employee_a (submitted)."""
    draft_overtime_a.status = "pending"
    draft_overtime_a.save(update_fields=["status", "updated_at"])
    return draft_overtime_a


@pytest.fixture
def overtime_b(db, tenant_b, employee_b):
    """A pending OvertimeRequest belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import OvertimeRequest
    return OvertimeRequest.objects.create(
        tenant=tenant_b, employee=employee_b, date=datetime.date(2026, 6, 2),
        hours_claimed=Decimal("2"), multiplier=Decimal("1.50"),
        payout_method="pay", reason="Support B", status="pending",
    )


# ------------------------------------------------------------------ 3.13 Salary Structure fixtures
@pytest.fixture
def pay_component_a(db, tenant_a):
    """A fixed-amount 'Basic Pay' PayComponent for tenant_a."""
    from apps.hrm.models import PayComponent
    return PayComponent.objects.create(
        tenant=tenant_a, name="Basic Pay", component_type="earning",
        calculation_type="fixed_amount", default_amount=Decimal("50000"),
    )


@pytest.fixture
def pay_component_b(db, tenant_b):
    """A PayComponent belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import PayComponent
    return PayComponent.objects.create(
        tenant=tenant_b, name="Basic Pay B", component_type="earning",
        calculation_type="fixed_amount", default_amount=Decimal("40000"),
    )


@pytest.fixture
def salary_template_a(db, tenant_a):
    """A SalaryStructureTemplate for tenant_a — no lines yet."""
    from apps.hrm.models import SalaryStructureTemplate
    return SalaryStructureTemplate.objects.create(
        tenant=tenant_a, name="Engineering L2", annual_ctc_amount=Decimal("120000"),
    )


@pytest.fixture
def salary_template_b(db, tenant_b):
    """A SalaryStructureTemplate belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import SalaryStructureTemplate
    return SalaryStructureTemplate.objects.create(
        tenant=tenant_b, name="Analyst L1 B", annual_ctc_amount=Decimal("60000"),
    )


@pytest.fixture
def salary_line_a(db, tenant_a, salary_template_a, pay_component_a):
    """A SalaryStructureLine on salary_template_a referencing pay_component_a."""
    from apps.hrm.models import SalaryStructureLine
    return SalaryStructureLine.objects.create(
        tenant=tenant_a, template=salary_template_a, pay_component=pay_component_a,
        amount=Decimal("55000"),
    )


@pytest.fixture
def salary_line_b(db, tenant_b, salary_template_b, pay_component_b):
    """A SalaryStructureLine belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import SalaryStructureLine
    return SalaryStructureLine.objects.create(
        tenant=tenant_b, template=salary_template_b, pay_component=pay_component_b,
        amount=Decimal("40000"),
    )


@pytest.fixture
def active_salary_structure_a(db, tenant_a, employee_a, salary_template_a):
    """An active EmployeeSalaryStructure assignment for employee_a/tenant_a."""
    from apps.hrm.models import EmployeeSalaryStructure
    return EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=employee_a, template=salary_template_a,
        annual_ctc_amount=Decimal("120000"), status="active",
    )


@pytest.fixture
def superseded_salary_structure_a(db, tenant_a, employee_a):
    """A superseded (read-only history) EmployeeSalaryStructure for employee_a/tenant_a."""
    from apps.hrm.models import EmployeeSalaryStructure
    return EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=employee_a,
        annual_ctc_amount=Decimal("100000"), status="superseded",
    )


@pytest.fixture
def employee_salary_structure_b(db, tenant_b, employee_b):
    """An active EmployeeSalaryStructure belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import EmployeeSalaryStructure
    return EmployeeSalaryStructure.objects.create(
        tenant=tenant_b, employee=employee_b,
        annual_ctc_amount=Decimal("90000"), status="active",
    )


# ------------------------------------------------------------------ 3.14 Payroll Processing fixtures
@pytest.fixture
def active_structure_in_window_a(db, tenant_a, employee_a, salary_template_a):
    """An active EmployeeSalaryStructure for employee_a whose effective_from (2026-05-01) is safely
    BEFORE draft_cycle_a's period_start (2026-06-01) — unlike ``active_salary_structure_a`` (which
    defaults effective_from to "today"), this is guaranteed to fall inside the payrollcycle_generate
    effective-date window regardless of the environment's current date."""
    from apps.hrm.models import EmployeeSalaryStructure
    return EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=employee_a, template=salary_template_a,
        annual_ctc_amount=Decimal("120000"), status="active",
        effective_from=datetime.date(2026, 5, 1),
    )


@pytest.fixture
def payroll_component_lines_a(db, tenant_a, salary_template_a):
    """Populates salary_template_a with a Basic Pay (fixed 60000/yr) earning line so payslip
    generation/recompute has a non-zero, deterministic basis."""
    from apps.hrm.models import PayComponent, SalaryStructureLine
    basic = PayComponent.objects.create(
        tenant=tenant_a, name="Basic Pay", component_type="earning",
        calculation_type="fixed_amount", default_amount=Decimal("60000"),
    )
    SalaryStructureLine.objects.create(
        tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"),
    )
    return basic


@pytest.fixture
def draft_cycle_a(db, tenant_a):
    """A draft PayrollCycle for tenant_a — period 2026-06-01..2026-06-30, pay_date 2026-07-01."""
    from apps.hrm.models import PayrollCycle
    return PayrollCycle.objects.create(
        tenant=tenant_a,
        period_start=datetime.date(2026, 6, 1),
        period_end=datetime.date(2026, 6, 30),
        pay_date=datetime.date(2026, 7, 1),
        cycle_type="regular",
        status="draft",
    )


@pytest.fixture
def cycle_b(db, tenant_b):
    """A draft PayrollCycle belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import PayrollCycle
    return PayrollCycle.objects.create(
        tenant=tenant_b,
        period_start=datetime.date(2026, 6, 1),
        period_end=datetime.date(2026, 6, 30),
        pay_date=datetime.date(2026, 7, 1),
        cycle_type="regular",
        status="draft",
    )


@pytest.fixture
def payslip_a(db, tenant_a, draft_cycle_a, employee_a, active_structure_in_window_a, payroll_component_lines_a):
    """A recomputed Payslip for employee_a within draft_cycle_a."""
    from apps.hrm.models import Payslip
    payslip = Payslip.objects.create(
        tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a,
        salary_structure=active_structure_in_window_a, days_in_period=30, days_worked=30,
    )
    payslip.recompute()
    return payslip


@pytest.fixture
def payslip_b(db, tenant_b, cycle_b, employee_b, employee_salary_structure_b):
    """A Payslip belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import Payslip
    payslip = Payslip.objects.create(
        tenant=tenant_b, cycle=cycle_b, employee=employee_b,
        salary_structure=employee_salary_structure_b, days_in_period=30, days_worked=30,
    )
    payslip.recompute()
    return payslip


# ------------------------------------------------------------------ 3.15 Statutory Compliance fixtures
@pytest.fixture
def statutory_config_a(db, tenant_a):
    """The StatutoryConfig singleton for tenant_a (get-or-create via for_tenant())."""
    from apps.hrm.models import StatutoryConfig
    return StatutoryConfig.for_tenant(tenant_a)


@pytest.fixture
def statutory_config_b(db, tenant_b):
    """The StatutoryConfig singleton for tenant_b (IDOR / isolation tests)."""
    from apps.hrm.models import StatutoryConfig
    return StatutoryConfig.for_tenant(tenant_b)


@pytest.fixture
def pt_rule_a(db, tenant_a):
    """A valid Professional Tax StatutoryStateRule for tenant_a — Karnataka, 15000-20000 slab."""
    from apps.hrm.models import StatutoryStateRule
    return StatutoryStateRule.objects.create(
        tenant=tenant_a, state="Karnataka", scheme="pt",
        income_from=Decimal("15000"), income_to=Decimal("20000"),
        pt_monthly_amount=Decimal("200"),
    )


@pytest.fixture
def lwf_rule_a(db, tenant_a):
    """A valid, active Labour Welfare Fund StatutoryStateRule for tenant_a — Maharashtra."""
    from apps.hrm.models import StatutoryStateRule
    return StatutoryStateRule.objects.create(
        tenant=tenant_a, state="Maharashtra", scheme="lwf",
        lwf_employee_contribution=Decimal("12"), lwf_employer_contribution=Decimal("36"),
        lwf_periodicity="half_yearly", is_active=True,
    )


@pytest.fixture
def state_rule_b(db, tenant_b):
    """A valid PT StatutoryStateRule belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import StatutoryStateRule
    return StatutoryStateRule.objects.create(
        tenant=tenant_b, state="Karnataka", scheme="pt",
        income_from=Decimal("15000"), income_to=Decimal("20000"),
        pt_monthly_amount=Decimal("200"),
    )


@pytest.fixture
def statutory_identifier_a(db, tenant_a, employee_a):
    """An EmployeeStatutoryIdentifier for employee_a/tenant_a with a full UAN/PF/ESI set."""
    from apps.hrm.models import EmployeeStatutoryIdentifier
    return EmployeeStatutoryIdentifier.objects.create(
        tenant=tenant_a, employee=employee_a,
        uan_number="123456789012", pf_number="KN/BLR/001234",
        esi_number="3111234567", pt_state="Karnataka",
    )


@pytest.fixture
def statutory_identifier_b(db, tenant_b, employee_b):
    """An EmployeeStatutoryIdentifier belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import EmployeeStatutoryIdentifier
    return EmployeeStatutoryIdentifier.objects.create(
        tenant=tenant_b, employee=employee_b,
        uan_number="987654321098", pf_number="MH/PUN/005678",
        esi_number="3119876543", pt_state="Maharashtra",
    )


@pytest.fixture
def pf_component_lines_a(db, tenant_a, salary_template_a):
    """Populates salary_template_a with Basic Pay (60000/yr earning) + employee-side PF (1200/yr,
    'Provident Fund - Employee') + employer-side PF (1200/yr, 'Provident Fund - Employer') so a
    recomputed Payslip has real statutory_deduction PayslipLine rows for StatutoryReturn.recompute()
    to aggregate (scheme keyword 'provident' matches both PF lines)."""
    from apps.hrm.models import PayComponent, SalaryStructureLine
    basic = PayComponent.objects.create(
        tenant=tenant_a, name="Basic Pay", component_type="earning",
        calculation_type="fixed_amount", default_amount=Decimal("60000"),
    )
    pf_ee = PayComponent.objects.create(
        tenant=tenant_a, name="Provident Fund - Employee", component_type="statutory_deduction",
        calculation_type="fixed_amount", default_amount=Decimal("1200"),
        contribution_side="employee",
    )
    pf_er = PayComponent.objects.create(
        tenant=tenant_a, name="Provident Fund - Employer", component_type="statutory_deduction",
        calculation_type="fixed_amount", default_amount=Decimal("1200"),
        contribution_side="employer",
    )
    SalaryStructureLine.objects.create(
        tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"))
    SalaryStructureLine.objects.create(
        tenant=tenant_a, template=salary_template_a, pay_component=pf_ee, amount=Decimal("1200"))
    SalaryStructureLine.objects.create(
        tenant=tenant_a, template=salary_template_a, pay_component=pf_er, amount=Decimal("1200"))
    return basic, pf_ee, pf_er


@pytest.fixture
def payslip_with_pf_a(db, tenant_a, draft_cycle_a, employee_a, active_structure_in_window_a,
                       pf_component_lines_a):
    """A recomputed Payslip for employee_a within draft_cycle_a whose salary structure produces
    Basic Pay + employee-side PF + employer-side PF lines (for StatutoryReturn aggregation tests)."""
    from apps.hrm.models import Payslip
    payslip = Payslip.objects.create(
        tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a,
        salary_structure=active_structure_in_window_a, days_in_period=30, days_worked=30,
    )
    payslip.recompute()
    return payslip


@pytest.fixture
def pending_statutory_return_a(db, tenant_a, draft_cycle_a):
    """A pending, unaggregated PF StatutoryReturn for tenant_a scoped to draft_cycle_a."""
    from apps.hrm.models import StatutoryReturn
    return StatutoryReturn.objects.create(
        tenant=tenant_a, scheme="pf", period_type="monthly",
        period_start=draft_cycle_a.period_start, period_end=draft_cycle_a.period_end,
        cycle=draft_cycle_a, due_date=datetime.date(2026, 7, 15),
    )


@pytest.fixture
def statutory_return_b(db, tenant_b, cycle_b):
    """A pending PF StatutoryReturn belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import StatutoryReturn
    return StatutoryReturn.objects.create(
        tenant=tenant_b, scheme="pf", period_type="monthly",
        period_start=cycle_b.period_start, period_end=cycle_b.period_end,
        cycle=cycle_b, due_date=datetime.date(2026, 7, 15),
    )


# ------------------------------------------------------------------ 3.16 Tax & Investment fixtures
@pytest.fixture
def new_regime_config_a(db, tenant_a):
    """FY 2025-26 NEW-regime TaxRegimeConfig for tenant_a — mirrors the seeded demo (std ded 75000,
    cess 4%, 87A rebate <=1200000 up to 60000) with its 7-band slab table."""
    from apps.hrm.models import TaxRegimeConfig, TaxSlabBand
    cfg = TaxRegimeConfig.objects.create(
        tenant=tenant_a, financial_year="2025-26", regime="new",
        standard_deduction=Decimal("75000.00"), cess_rate=Decimal("4.00"),
        rebate_income_threshold=Decimal("1200000.00"), rebate_max_tax=Decimal("60000.00"),
        is_default_regime=True,
    )
    bands = [(0, 400000, 0), (400000, 800000, 5), (800000, 1200000, 10),
             (1200000, 1600000, 15), (1600000, 2000000, 20), (2000000, 2400000, 25),
             (2400000, None, 30)]
    for i, (lo, hi, rate) in enumerate(bands, start=1):
        TaxSlabBand.objects.create(
            tenant=tenant_a, config=cfg, income_from=Decimal(lo),
            income_to=(Decimal(hi) if hi is not None else None), rate_percent=Decimal(rate), sequence=i)
    return cfg


@pytest.fixture
def old_regime_config_a(db, tenant_a):
    """FY 2025-26 OLD-regime TaxRegimeConfig for tenant_a — mirrors the seeded demo (std ded 50000,
    cess 4%, 87A rebate <=500000 up to 12500) with its 4-band slab table."""
    from apps.hrm.models import TaxRegimeConfig, TaxSlabBand
    cfg = TaxRegimeConfig.objects.create(
        tenant=tenant_a, financial_year="2025-26", regime="old",
        standard_deduction=Decimal("50000.00"), cess_rate=Decimal("4.00"),
        rebate_income_threshold=Decimal("500000.00"), rebate_max_tax=Decimal("12500.00"),
        is_default_regime=False,
    )
    bands = [(0, 250000, 0), (250000, 500000, 5), (500000, 1000000, 20), (1000000, None, 30)]
    for i, (lo, hi, rate) in enumerate(bands, start=1):
        TaxSlabBand.objects.create(
            tenant=tenant_a, config=cfg, income_from=Decimal(lo),
            income_to=(Decimal(hi) if hi is not None else None), rate_percent=Decimal(rate), sequence=i)
    return cfg


@pytest.fixture
def regime_config_b(db, tenant_b):
    """A NEW-regime TaxRegimeConfig belonging to tenant_b (IDOR tests), with one slab band."""
    from apps.hrm.models import TaxRegimeConfig, TaxSlabBand
    cfg = TaxRegimeConfig.objects.create(
        tenant=tenant_b, financial_year="2025-26", regime="new",
        standard_deduction=Decimal("75000.00"), cess_rate=Decimal("4.00"),
        rebate_income_threshold=Decimal("1200000.00"), rebate_max_tax=Decimal("60000.00"),
        is_default_regime=True,
    )
    TaxSlabBand.objects.create(
        tenant=tenant_b, config=cfg, income_from=Decimal("0"), income_to=Decimal("400000"),
        rate_percent=Decimal("0"), sequence=1)
    return cfg


@pytest.fixture
def slab_band_b(db, regime_config_b):
    """The single TaxSlabBand belonging to tenant_b's regime_config_b (IDOR tests)."""
    return regime_config_b.slab_bands.first()


@pytest.fixture
def tax_salary_lines_a(db, tenant_a, salary_template_a):
    """Populates salary_template_a with BASIC (60000/yr fixed) + HRA (30000/yr fixed) earning lines —
    matches the seeded demo structure so the HRA-exemption 3-way min + gross income are hand-verifiable
    (BASIC 60000, HRA 30000, annual_ctc_amount 120000)."""
    from apps.hrm.models import PayComponent, SalaryStructureLine
    basic = PayComponent.objects.create(
        tenant=tenant_a, name="Basic", code="BASIC", component_type="earning",
        calculation_type="fixed_amount", default_amount=None, default_percentage=Decimal("40"),
    )
    # calculation_type overridden to fixed_amount at the LINE level below (mirrors the seeder).
    basic.calculation_type = "pct_of_ctc"
    basic.save(update_fields=["calculation_type"])
    hra = PayComponent.objects.create(
        tenant=tenant_a, name="House Rent Allowance", code="HRA", component_type="earning",
        calculation_type="pct_of_basic", default_amount=None, default_percentage=Decimal("50"),
    )
    SalaryStructureLine.objects.create(
        tenant=tenant_a, template=salary_template_a, pay_component=basic,
        calculation_type="fixed_amount", amount=Decimal("60000"), sequence=1)
    SalaryStructureLine.objects.create(
        tenant=tenant_a, template=salary_template_a, pay_component=hra,
        calculation_type="fixed_amount", amount=Decimal("30000"), sequence=2)
    return basic, hra


@pytest.fixture
def tax_structure_a(db, tenant_a, employee_a, salary_template_a, tax_salary_lines_a):
    """An active EmployeeSalaryStructure for employee_a on salary_template_a (annual_ctc_amount
    120000) with the BASIC+HRA lines from tax_salary_lines_a — the engine's gross-income basis."""
    from apps.hrm.models import EmployeeSalaryStructure
    return EmployeeSalaryStructure.objects.create(
        tenant=tenant_a, employee=employee_a, template=salary_template_a,
        annual_ctc_amount=Decimal("120000"), status="active",
        effective_from=datetime.date(2025, 4, 1),
    )


@pytest.fixture
def tax_declaration_a(db, tenant_a, employee_a):
    """A submitted old-regime InvestmentDeclaration for employee_a/tenant_a FY 2025-26 — mirrors the
    seeded demo (mid-year joiner, previous_employer_income=800000) so gross = 120000 (CTC) + 800000 =
    920000. Proof window open-ended (opens Dec 2025, no close date) so it is ALWAYS "currently open"
    regardless of the test environment's real-world date — used for both upload-window-open tests and
    (via an explicit proof_window_close override in the recompute-gate tests) the final-computation
    gate tests."""
    from apps.hrm.models import InvestmentDeclaration
    return InvestmentDeclaration.objects.create(
        tenant=tenant_a, employee=employee_a, financial_year="2025-26", regime_elected="old",
        status="submitted",
        declaration_window_open=datetime.date(2025, 4, 1),
        declaration_window_close=datetime.date(2025, 6, 30),
        proof_window_open=datetime.date(2025, 12, 1),
        proof_window_close=None,
        previous_employer_income=Decimal("800000.00"), previous_employer_tds=Decimal("0.00"),
    )


@pytest.fixture
def draft_declaration_a(db, tenant_a, employee_a):
    """A draft InvestmentDeclaration for employee_a/tenant_a (editable, no lines) — used for
    submit/edit/delete/line-CRUD tests that need the draft (is_editable) state. A DIFFERENT financial
    year from tax_declaration_a's "2025-26" (same employee) so the two fixtures can coexist under the
    (tenant, employee, financial_year) unique_together without colliding."""
    from apps.hrm.models import InvestmentDeclaration
    return InvestmentDeclaration.objects.create(
        tenant=tenant_a, employee=employee_a, financial_year="2024-25", regime_elected="old",
        status="draft",
    )


@pytest.fixture
def declaration_b(db, tenant_b, employee_b):
    """A draft InvestmentDeclaration belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import InvestmentDeclaration
    return InvestmentDeclaration.objects.create(
        tenant=tenant_b, employee=employee_b, financial_year="2025-26", regime_elected="old",
        status="draft",
    )


@pytest.fixture
def line_80c_a(db, tenant_a, tax_declaration_a):
    """The 80C InvestmentDeclarationLine on tax_declaration_a — declared 150000 (over the 150000 cap
    boundary; bump in individual tests to exercise capped_sections)."""
    from apps.hrm.models import InvestmentDeclarationLine
    return InvestmentDeclarationLine.objects.create(
        tenant=tenant_a, declaration=tax_declaration_a, section_code="80c",
        declared_amount=Decimal("150000.00"),
    )


@pytest.fixture
def line_hra_a(db, tenant_a, tax_declaration_a):
    """The HRA InvestmentDeclarationLine on tax_declaration_a — monthly rent 15000, metro city (mirrors
    the seeded demo)."""
    from apps.hrm.models import InvestmentDeclarationLine
    return InvestmentDeclarationLine.objects.create(
        tenant=tenant_a, declaration=tax_declaration_a, section_code="hra",
        declared_amount=Decimal("0.00"), monthly_rent_amount=Decimal("15000.00"), is_metro_city=True,
    )


@pytest.fixture
def line_b(db, tenant_b, declaration_b):
    """An InvestmentDeclarationLine belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import InvestmentDeclarationLine
    return InvestmentDeclarationLine.objects.create(
        tenant=tenant_b, declaration=declaration_b, section_code="80c", declared_amount=Decimal("50000.00"),
    )


@pytest.fixture
def verified_proof_80c_a(db, tenant_a, line_80c_a, admin_user):
    """A verified InvestmentProof on line_80c_a — amount 150000, rolled into verified_amount."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.hrm.models import InvestmentProof
    proof = InvestmentProof.objects.create(
        tenant=tenant_a, declaration_line=line_80c_a,
        file=SimpleUploadedFile("lic_receipt.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        title="LIC Premium Receipt", amount=Decimal("150000.00"),
        verification_status="verified", verified_by=admin_user, verified_at=timezone.now(),
    )
    line_80c_a.verified_amount = Decimal("150000.00")
    line_80c_a.save(update_fields=["verified_amount"])
    return proof


@pytest.fixture
def pending_proof_80c_a(db, tenant_a, line_80c_a):
    """A pending (undecided) InvestmentProof on line_80c_a."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.hrm.models import InvestmentProof
    return InvestmentProof.objects.create(
        tenant=tenant_a, declaration_line=line_80c_a,
        file=SimpleUploadedFile("receipt.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        title="Receipt", amount=Decimal("150000.00"),
    )


@pytest.fixture
def proof_b(db, tenant_b, line_b):
    """An InvestmentProof belonging to tenant_b (IDOR tests)."""
    from django.core.files.uploadedfile import SimpleUploadedFile
    from apps.hrm.models import InvestmentProof
    return InvestmentProof.objects.create(
        tenant=tenant_b, declaration_line=line_b,
        file=SimpleUploadedFile("receipt_b.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        title="Receipt B", amount=Decimal("50000.00"),
    )


@pytest.fixture
def tax_computation_a(db, tenant_a, employee_a, tax_declaration_a, tax_structure_a,
                       line_80c_a, line_hra_a, old_regime_config_a, new_regime_config_a):
    """A 'final' TaxComputation for employee_a/tax_declaration_a, recomputed — the hand-verifiable
    demo case (gross 920000, old regime -> 52520.00, new regime -> 0.00). tax_declaration_a's proof
    window has no close date (open-ended), so the final-computation gate passes unconditionally."""
    from apps.hrm.models import TaxComputation
    comp = TaxComputation.objects.create(
        tenant=tenant_a, employee=employee_a, declaration=tax_declaration_a,
        computation_type="final", remaining_pay_periods=6,
    )
    comp.recompute()
    return comp


@pytest.fixture
def computation_b(db, tenant_b, employee_b, declaration_b, employee_salary_structure_b):
    """A provisional TaxComputation belonging to tenant_b (IDOR tests). Not recomputed (no regime
    config seeded for tenant_b), so tax_payable stays 0 — fine, only used for IDOR pk probes."""
    from apps.hrm.models import TaxComputation
    return TaxComputation.objects.create(
        tenant=tenant_b, employee=employee_b, declaration=declaration_b,
        financial_year=declaration_b.financial_year, computation_type="provisional",
    )


# ------------------------------------------------------------------ 3.17 Payout & Reports fixtures
@pytest.fixture
def locked_cycle_a(db, tenant_a, employee_a, employee_a2, active_structure_in_window_a,
                    payroll_component_lines_a):
    """A LOCKED PayrollCycle for tenant_a with two recomputed Payslips (employee_a, employee_a2) —
    the pre-req for generating a PayoutBatch. employee_a2 has no active salary structure so its
    payslip recomputes to zero lines but is still a valid (tenant, cycle, employee) row. Built as
    DRAFT so Payslip.recompute() is allowed, then flipped to locked afterwards (recompute() forbids
    a locked cycle's payslips)."""
    from apps.hrm.models import PayrollCycle, Payslip
    cycle = PayrollCycle.objects.create(
        tenant=tenant_a,
        period_start=datetime.date(2026, 6, 1),
        period_end=datetime.date(2026, 6, 30),
        pay_date=datetime.date(2026, 7, 1),
        cycle_type="regular",
        status="draft",
    )
    ps1 = Payslip.objects.create(
        tenant=tenant_a, cycle=cycle, employee=employee_a,
        salary_structure=active_structure_in_window_a, days_in_period=30, days_worked=30,
    )
    ps1.recompute()
    ps2 = Payslip.objects.create(
        tenant=tenant_a, cycle=cycle, employee=employee_a2, days_in_period=30, days_worked=30,
    )
    ps2.recompute()
    cycle.status = "locked"
    cycle.save(update_fields=["status", "updated_at"])
    return cycle


@pytest.fixture
def locked_cycle_with_hold_a(db, locked_cycle_a):
    """locked_cycle_a with its second payslip (employee_a2) flagged on_hold, for on_hold-snapshot
    generation tests."""
    ps2 = locked_cycle_a.payslips.exclude(employee__party__name="Alice Smith").first()
    ps2.on_hold = True
    ps2.hold_reason = "Pending manager sign-off"
    ps2.save(update_fields=["on_hold", "hold_reason", "updated_at"])
    return locked_cycle_a


@pytest.fixture
def cycle_b_locked(db, tenant_b, employee_b, employee_salary_structure_b):
    """A LOCKED PayrollCycle for tenant_b with one recomputed Payslip (IDOR tests). Built as draft,
    recomputed, then locked (mirrors locked_cycle_a)."""
    from apps.hrm.models import PayrollCycle, Payslip
    cycle = PayrollCycle.objects.create(
        tenant=tenant_b,
        period_start=datetime.date(2026, 6, 1),
        period_end=datetime.date(2026, 6, 30),
        pay_date=datetime.date(2026, 7, 1),
        cycle_type="regular",
        status="draft",
    )
    ps = Payslip.objects.create(
        tenant=tenant_b, cycle=cycle, employee=employee_b,
        salary_structure=employee_salary_structure_b, days_in_period=30, days_worked=30,
    )
    ps.recompute()
    cycle.status = "locked"
    cycle.save(update_fields=["status", "updated_at"])
    return cycle


@pytest.fixture
def payout_batch_a(db, tenant_a, locked_cycle_a):
    """A draft PayoutBatch for tenant_a over locked_cycle_a — no payments generated yet."""
    from apps.hrm.models import PayoutBatch
    return PayoutBatch.objects.create(tenant=tenant_a, cycle=locked_cycle_a)


@pytest.fixture
def generated_batch_a(db, tenant_a, admin_user, payout_batch_a):
    """payout_batch_a after payoutbatch_generate-equivalent: one PayoutPayment per payslip of its
    cycle, snapshot net_pay + masked bank details, on_hold payslips -> status on_hold."""
    from django.utils import timezone as tz
    from apps.hrm.models import PayoutPayment
    batch = payout_batch_a
    for ps in batch.cycle.payslips.select_related("employee").all():
        emp = ps.employee
        PayoutPayment.objects.create(
            tenant=tenant_a, batch=batch, payslip=ps, employee=emp,
            net_amount=ps.net_pay,
            bank_name_snapshot=emp.bank_name,
            bank_account_last4_snapshot=emp.masked_bank_account(),
            bank_routing_snapshot=emp.masked_bank_routing(),
            status="on_hold" if ps.on_hold else "pending",
        )
    batch.generated_by = admin_user
    batch.generated_at = tz.now()
    batch.save(update_fields=["generated_by", "generated_at", "updated_at"])
    return batch


@pytest.fixture
def batch_b(db, tenant_b, cycle_b_locked):
    """A draft PayoutBatch belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import PayoutBatch
    return PayoutBatch.objects.create(tenant=tenant_b, cycle=cycle_b_locked)


@pytest.fixture
def payment_b(db, tenant_b, batch_b):
    """A pending PayoutPayment belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import PayoutPayment
    ps = batch_b.cycle.payslips.first()
    emp = ps.employee
    return PayoutPayment.objects.create(
        tenant=tenant_b, batch=batch_b, payslip=ps, employee=emp,
        net_amount=ps.net_pay,
        bank_name_snapshot=emp.bank_name,
        bank_account_last4_snapshot=emp.masked_bank_account(),
        bank_routing_snapshot=emp.masked_bank_routing(),
        status="pending",
    )


@pytest.fixture
def distribution_b(db, tenant_b, payment_b):
    """A pending PayslipDistribution belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import PayslipDistribution
    return PayslipDistribution.for_payslip(payment_b.payslip)


@pytest.fixture
def reconciliation_b(db, tenant_b, batch_b):
    """A pending BankReconciliation belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import BankReconciliation
    return BankReconciliation.objects.create(
        tenant=tenant_b, batch=batch_b, statement_date=datetime.date(2026, 7, 2),
    )


# ------------------------------------------------------------------ 3.18 Goal Setting fixtures
@pytest.fixture
def goal_period_a(db, tenant_a):
    """An active GoalPeriod for tenant_a — Q3 2026, 2026-07-01..2026-09-30."""
    from apps.hrm.models import GoalPeriod
    return GoalPeriod.objects.create(
        tenant=tenant_a, name="Q3 2026", period_type="quarterly",
        start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 30),
        status="active",
    )


@pytest.fixture
def goal_period_b(db, tenant_b):
    """An active GoalPeriod belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import GoalPeriod
    return GoalPeriod.objects.create(
        tenant=tenant_b, name="Q3 2026 B", period_type="quarterly",
        start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 30),
        status="active",
    )


@pytest.fixture
def objective_a(db, tenant_a, employee_a, goal_period_a):
    """An active Objective for employee_a/tenant_a, no key results yet."""
    from apps.hrm.models import Objective
    return Objective.objects.create(
        tenant=tenant_a, title="Grow revenue", owner=employee_a, goal_period=goal_period_a,
        scope="individual", target_type="committed", status="active",
    )


@pytest.fixture
def objective_b(db, tenant_b, employee_b, goal_period_b):
    """An active Objective belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import Objective
    return Objective.objects.create(
        tenant=tenant_b, title="Grow revenue B", owner=employee_b, goal_period=goal_period_b,
        scope="individual", target_type="committed", status="active",
    )


@pytest.fixture
def key_result_a(db, tenant_a, objective_a):
    """A numeric KeyResult on objective_a — start 0, target 100, current 60 (60% progress), weight 70."""
    from apps.hrm.models import KeyResult
    return KeyResult.objects.create(
        tenant=tenant_a, objective=objective_a, title="Close 100 new deals",
        metric_type="numeric", start_value=Decimal("0"), target_value=Decimal("100"),
        current_value=Decimal("60"), weight=Decimal("70"), status="in_progress",
    )


@pytest.fixture
def key_result_b(db, tenant_b, objective_b):
    """A numeric KeyResult belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import KeyResult
    return KeyResult.objects.create(
        tenant=tenant_b, objective=objective_b, title="Close 50 new deals B",
        metric_type="numeric", start_value=Decimal("0"), target_value=Decimal("50"),
        current_value=Decimal("10"), weight=Decimal("100"), status="in_progress",
    )


@pytest.fixture
def goal_checkin_a(db, tenant_a, key_result_a, employee_a):
    """A GoalCheckIn against key_result_a for tenant_a."""
    from apps.hrm.models import GoalCheckIn
    return GoalCheckIn.objects.create(
        tenant=tenant_a, key_result=key_result_a, checkin_date=datetime.date(2026, 7, 15),
        value_at_checkin=Decimal("60"), confidence="on_track", created_by=employee_a,
    )


@pytest.fixture
def goal_checkin_b(db, tenant_b, key_result_b, employee_b):
    """A GoalCheckIn belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import GoalCheckIn
    return GoalCheckIn.objects.create(
        tenant=tenant_b, key_result=key_result_b, checkin_date=datetime.date(2026, 7, 15),
        value_at_checkin=Decimal("10"), confidence="on_track", created_by=employee_b,
    )


# ------------------------------------------------------------------ 3.19 Performance Review fixtures
@pytest.fixture
def review_cycle_a(db, tenant_a, goal_period_a):
    """A draft ReviewCycle for tenant_a — H1 2026, aligned to goal_period_a (Q3 2026 OKR window)."""
    from apps.hrm.models import ReviewCycle
    return ReviewCycle.objects.create(
        tenant=tenant_a, name="H1 2026 Performance Review", cycle_type="half_yearly",
        status="draft", goal_period=goal_period_a,
        self_review_start=datetime.date(2026, 7, 1), self_review_end=datetime.date(2026, 7, 15),
        manager_review_start=datetime.date(2026, 7, 16), manager_review_end=datetime.date(2026, 7, 31),
        calibration_date=datetime.date(2026, 8, 5), results_release_date=datetime.date(2026, 8, 10),
    )


@pytest.fixture
def review_cycle_b(db, tenant_b):
    """A draft ReviewCycle belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import ReviewCycle
    return ReviewCycle.objects.create(
        tenant=tenant_b, name="H1 2026 Performance Review B", cycle_type="half_yearly", status="draft",
    )


@pytest.fixture
def review_template_a(db, tenant_a):
    """An active manager-type ReviewTemplate for tenant_a — 5-point scale, includes goals."""
    from apps.hrm.models import ReviewTemplate
    return ReviewTemplate.objects.create(
        tenant=tenant_a, name="Manager Review Form", review_type="manager",
        rating_scale_max=5, include_goals=True, is_active=True,
    )


@pytest.fixture
def review_template_b(db, tenant_b):
    """An active ReviewTemplate belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import ReviewTemplate
    return ReviewTemplate.objects.create(
        tenant=tenant_b, name="Manager Review Form B", review_type="manager",
        rating_scale_max=5, is_active=True,
    )


@pytest.fixture
def performance_review_a(db, tenant_a, review_cycle_a, review_template_a, employee_a, employee_a2):
    """A draft manager PerformanceReview for tenant_a — subject=employee_a, reviewer=employee_a2
    (a distinct EmployeeProfile so `reviewer != subject` on a non-self review)."""
    from apps.hrm.models import PerformanceReview
    return PerformanceReview.objects.create(
        tenant=tenant_a, cycle=review_cycle_a, template=review_template_a,
        subject=employee_a, reviewer=employee_a2, review_type="manager", status="draft",
        private_notes="Confidential: needs coaching on delegation.",
    )


@pytest.fixture
def performance_review_b(db, tenant_b, review_cycle_b, review_template_b, employee_b):
    """A draft self-review PerformanceReview belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import PerformanceReview
    return PerformanceReview.objects.create(
        tenant=tenant_b, cycle=review_cycle_b, template=review_template_b,
        subject=employee_b, reviewer=employee_b, review_type="self", status="draft",
    )


@pytest.fixture
def review_rating_a(db, tenant_a, performance_review_a):
    """A ReviewRating on performance_review_a — competency criterion, rating 4.00 @ weight 100."""
    from apps.hrm.models import ReviewRating
    return ReviewRating.objects.create(
        tenant=tenant_a, review=performance_review_a, criterion_label="Communication",
        criterion_category="competency", rating_value=Decimal("4.00"), weight=Decimal("100"),
    )


@pytest.fixture
def review_rating_b(db, tenant_b, performance_review_b):
    """A ReviewRating belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import ReviewRating
    return ReviewRating.objects.create(
        tenant=tenant_b, review=performance_review_b, criterion_label="Communication B",
        criterion_category="competency", rating_value=Decimal("3.00"), weight=Decimal("100"),
    )


# ------------------------------------------------------------------ 3.20 Continuous Feedback fixtures
@pytest.fixture
def kudos_badge_a(db, tenant_a):
    """An active KudosBadge for tenant_a — "Team Player"."""
    from apps.hrm.models import KudosBadge
    return KudosBadge.objects.create(
        tenant=tenant_a, name="Team Player", linked_value="Collaboration", is_active=True,
    )


@pytest.fixture
def kudos_badge_b(db, tenant_b):
    """An active KudosBadge belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import KudosBadge
    return KudosBadge.objects.create(tenant=tenant_b, name="Team Player B", is_active=True)


@pytest.fixture
def feedback_a(db, tenant_a, employee_a2, employee_a):
    """A private, given kudos Feedback for tenant_a — giver=employee_a2, receiver=employee_a."""
    from apps.hrm.models import Feedback
    return Feedback.objects.create(
        tenant=tenant_a, giver=employee_a2, receiver=employee_a,
        feedback_type="kudos", visibility="private", status="given",
        message="Great work on the release!",
    )


@pytest.fixture
def feedback_b(db, tenant_b, employee_b):
    """A private, given Feedback belonging to tenant_b (IDOR tests) — self-giver-less (giver=None)."""
    from apps.hrm.models import Feedback
    return Feedback.objects.create(
        tenant=tenant_b, receiver=employee_b,
        feedback_type="kudos", visibility="private", status="given",
        message="Nice job B!",
    )


@pytest.fixture
def outsider_employee_a(db, tenant_a):
    """A THIRD EmployeeProfile in tenant_a — neither giver nor receiver of feedback_a / participant
    of oneonone_a, and NOT in dept_a (a distinct org unit) so it also fails the "team" visibility
    check. Used to build a non-admin user who must be denied access to confidential rows they're
    not party to (mirrors the 3.19 outsider_employee_a fixture)."""
    from apps.core.models import Employment, OrgUnit, Party
    from apps.hrm.models import EmployeeProfile
    other_dept = OrgUnit.objects.create(tenant=tenant_a, kind="department", name="Sales")
    party = Party.objects.create(tenant=tenant_a, kind="person", name="Dana Outsider")
    employment = Employment.objects.create(
        tenant=tenant_a, party=party, org_unit=other_dept, job_title="Analyst", status="active")
    return EmployeeProfile.objects.create(
        tenant=tenant_a, party=party, employment=employment, employee_type="full_time")


@pytest.fixture
def teammate_employee_a(db, tenant_a, dept_a):
    """A FOURTH EmployeeProfile in tenant_a sharing employee_a's org unit (dept_a) — used for the
    "team" visibility tests (a colleague in the same department as the receiver)."""
    from apps.core.models import Employment, Party
    from apps.hrm.models import EmployeeProfile
    party = Party.objects.create(tenant=tenant_a, kind="person", name="Eve Teammate")
    employment = Employment.objects.create(
        tenant=tenant_a, party=party, org_unit=dept_a, job_title="Engineer", status="active")
    return EmployeeProfile.objects.create(
        tenant=tenant_a, party=party, employment=employment, employee_type="full_time")


@pytest.fixture
def oneonone_a(db, tenant_a, employee_a2, employee_a):
    """A scheduled OneOnOneMeeting for tenant_a — manager=employee_a2, employee=employee_a, with
    manager-only private notes."""
    from apps.hrm.models import OneOnOneMeeting
    return OneOnOneMeeting.objects.create(
        tenant=tenant_a, manager=employee_a2, employee=employee_a,
        scheduled_at=datetime.datetime(2026, 7, 10, 14, 0, tzinfo=datetime.timezone.utc),
        agenda="Career growth check-in",
        manager_private_notes="Confidential: flight risk, discuss retention plan.",
    )


@pytest.fixture
def oneonone_b(db, tenant_b, employee_b):
    """A scheduled OneOnOneMeeting belonging to tenant_b (IDOR tests) — manager=employee=employee_b
    is disallowed by clean(), so build a second tenant_b EmployeeProfile as the manager."""
    from apps.core.models import Employment, Party
    from apps.hrm.models import EmployeeProfile, OneOnOneMeeting
    party = Party.objects.create(tenant=tenant_b, kind="person", name="Manager B")
    employment = Employment.objects.create(
        tenant=tenant_b, party=party, job_title="Manager", status="active")
    manager_b = EmployeeProfile.objects.create(
        tenant=tenant_b, party=party, employment=employment, employee_type="full_time")
    return OneOnOneMeeting.objects.create(
        tenant=tenant_b, manager=manager_b, employee=employee_b,
        scheduled_at=datetime.datetime(2026, 7, 10, 14, 0, tzinfo=datetime.timezone.utc),
    )


@pytest.fixture
def action_item_a(db, tenant_a, oneonone_a, employee_a):
    """An open MeetingActionItem on oneonone_a, owned by employee_a (the meeting's employee side)."""
    from apps.hrm.models import MeetingActionItem
    return MeetingActionItem.objects.create(
        tenant=tenant_a, meeting=oneonone_a, description="Set up mentorship pairing",
        owner=employee_a, status="open",
    )


@pytest.fixture
def action_item_b(db, tenant_b, oneonone_b, employee_b):
    """An open MeetingActionItem belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import MeetingActionItem
    return MeetingActionItem.objects.create(
        tenant=tenant_b, meeting=oneonone_b, description="Action item B", owner=employee_b, status="open",
    )


# ------------------------------------------------------------------ 3.21 Performance Improvement fixtures
@pytest.fixture
def pip_draft_a(db, tenant_a, employee_a, employee_a2):
    """A draft PerformanceImprovementPlan for tenant_a — subject=employee_a, manager=employee_a2,
    window 2026-07-01..2026-09-29 (30/60/90-day style)."""
    from apps.hrm.models import PerformanceImprovementPlan
    return PerformanceImprovementPlan.objects.create(
        tenant=tenant_a, subject=employee_a, manager=employee_a2, status="draft",
        performance_issue="Missed 3 consecutive sprint deadlines.",
        expected_standards="Deliver committed sprint items on time.",
        improvement_goals="Complete all assigned stories within the sprint window for 60 days.",
        measurement_criteria="Sprint velocity + on-time delivery rate reviewed bi-weekly.",
        start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 29),
    )


@pytest.fixture
def pip_active_a(db, pip_draft_a):
    """pip_draft_a flipped to active (as if HR-approved) — for check-in/close/extend/acknowledge tests."""
    pip_draft_a.status = "active"
    pip_draft_a.hr_approved_at = timezone.now()
    pip_draft_a.save(update_fields=["status", "hr_approved_at", "updated_at"])
    return pip_draft_a


@pytest.fixture
def pip_b(db, tenant_b, employee_b):
    """A draft PerformanceImprovementPlan belonging to tenant_b (IDOR tests) — needs a second
    tenant_b EmployeeProfile as manager (subject != manager per clean())."""
    from apps.core.models import Employment, Party
    from apps.hrm.models import EmployeeProfile, PerformanceImprovementPlan
    party = Party.objects.create(tenant=tenant_b, kind="person", name="Manager B PIP")
    employment = Employment.objects.create(
        tenant=tenant_b, party=party, job_title="Manager", status="active")
    manager_b = EmployeeProfile.objects.create(
        tenant=tenant_b, party=party, employment=employment, employee_type="full_time")
    return PerformanceImprovementPlan.objects.create(
        tenant=tenant_b, subject=employee_b, manager=manager_b, status="draft",
        performance_issue="Issue B", expected_standards="Standards B",
        improvement_goals="Goals B", measurement_criteria="Criteria B",
        start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 9, 29),
    )


@pytest.fixture
def pipcheckin_a(db, tenant_a, pip_active_a):
    """A PIPCheckIn on pip_active_a, on_track."""
    from apps.hrm.models import PIPCheckIn
    return PIPCheckIn.objects.create(
        tenant=tenant_a, pip=pip_active_a, checkin_date=datetime.date(2026, 7, 15),
        progress_rating="on_track", progress_notes="Good progress this fortnight.",
        completed_at=timezone.now(),
    )


@pytest.fixture
def pipcheckin_b(db, tenant_b, pip_b):
    """A PIPCheckIn belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import PIPCheckIn
    return PIPCheckIn.objects.create(
        tenant=tenant_b, pip=pip_b, checkin_date=datetime.date(2026, 7, 15),
        progress_rating="on_track", completed_at=timezone.now(),
    )


@pytest.fixture
def warning_draft_a(db, tenant_a, employee_a, employee_a2):
    """A draft WarningLetter for tenant_a — issued_to=employee_a, issued_by=employee_a2."""
    from apps.hrm.models import WarningLetter
    return WarningLetter.objects.create(
        tenant=tenant_a, issued_to=employee_a, issued_by=employee_a2,
        level="verbal", category="attendance", incident_date=datetime.date(2026, 6, 1),
        description="Arrived over an hour late three times this month.",
        status="draft",
    )


@pytest.fixture
def warning_issued_a(db, warning_draft_a):
    """warning_draft_a flipped to issued — for acknowledge/print/IDOR-workflow tests."""
    warning_draft_a.status = "issued"
    warning_draft_a.save(update_fields=["status", "updated_at"])
    return warning_draft_a


@pytest.fixture
def warning_b(db, tenant_b, employee_b):
    """A draft WarningLetter belonging to tenant_b (IDOR tests) — needs a second tenant_b
    EmployeeProfile as issuer (issued_to != issued_by per clean())."""
    from apps.core.models import Employment, Party
    from apps.hrm.models import EmployeeProfile, WarningLetter
    party = Party.objects.create(tenant=tenant_b, kind="person", name="Issuer B")
    employment = Employment.objects.create(
        tenant=tenant_b, party=party, job_title="Manager", status="active")
    issuer_b = EmployeeProfile.objects.create(
        tenant=tenant_b, party=party, employment=employment, employee_type="full_time")
    return WarningLetter.objects.create(
        tenant=tenant_b, issued_to=employee_b, issued_by=issuer_b,
        level="verbal", category="conduct", incident_date=datetime.date(2026, 6, 1),
        description="Incident B", status="draft",
    )


@pytest.fixture
def coaching_note_a(db, tenant_a, employee_a, employee_a2):
    """A CoachingNote for tenant_a — employee=employee_a (coached), coach=employee_a2 (author)."""
    from apps.hrm.models import CoachingNote
    return CoachingNote.objects.create(
        tenant=tenant_a, employee=employee_a, coach=employee_a2,
        note_date=datetime.date(2026, 7, 5), category="skill_development",
        content="Discussed prioritization techniques; employee receptive to feedback.",
    )


@pytest.fixture
def coaching_note_b(db, tenant_b, employee_b):
    """A CoachingNote belonging to tenant_b (IDOR tests) — needs a second tenant_b EmployeeProfile
    as coach (employee != coach per clean())."""
    from apps.core.models import Employment, Party
    from apps.hrm.models import CoachingNote, EmployeeProfile
    party = Party.objects.create(tenant=tenant_b, kind="person", name="Coach B")
    employment = Employment.objects.create(
        tenant=tenant_b, party=party, job_title="Manager", status="active")
    coach_b = EmployeeProfile.objects.create(
        tenant=tenant_b, party=party, employment=employment, employee_type="full_time")
    return CoachingNote.objects.create(
        tenant=tenant_b, employee=employee_b, coach=coach_b,
        note_date=datetime.date(2026, 7, 5), category="other", content="Note B",
    )


# ------------------------------------------------------------------ 3.22 Training Management fixtures
@pytest.fixture
def training_course_a(db, tenant_a):
    """A classroom, non-certification TrainingCourse for tenant_a — "Advanced Python"."""
    from apps.hrm.models import TrainingCourse
    return TrainingCourse.objects.create(
        tenant=tenant_a, title="Advanced Python", category="technical",
        delivery_mode="classroom", duration_hours=Decimal("16"), default_capacity=20,
    )


@pytest.fixture
def training_course_b(db, tenant_b):
    """A TrainingCourse belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TrainingCourse
    return TrainingCourse.objects.create(
        tenant=tenant_b, title="Advanced Python B", category="technical",
        delivery_mode="classroom", duration_hours=Decimal("8"),
    )


@pytest.fixture
def training_session_a(db, tenant_a, training_course_a, employee_a):
    """A scheduled classroom TrainingSession for tenant_a — 2026-07-20 09:00-17:00, Room 101,
    instructor=employee_a."""
    from apps.hrm.models import TrainingSession
    return TrainingSession.objects.create(
        tenant=tenant_a, course=training_course_a, delivery_mode="classroom", status="scheduled",
        start_datetime=datetime.datetime(2026, 7, 20, 9, 0, tzinfo=datetime.timezone.utc),
        end_datetime=datetime.datetime(2026, 7, 20, 17, 0, tzinfo=datetime.timezone.utc),
        venue_name="Room 101", instructor_employee=employee_a, capacity=20,
    )


@pytest.fixture
def training_session_b(db, tenant_b, training_course_b, employee_b):
    """A scheduled classroom TrainingSession belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TrainingSession
    return TrainingSession.objects.create(
        tenant=tenant_b, course=training_course_b, delivery_mode="classroom", status="scheduled",
        start_datetime=datetime.datetime(2026, 7, 20, 9, 0, tzinfo=datetime.timezone.utc),
        end_datetime=datetime.datetime(2026, 7, 20, 17, 0, tzinfo=datetime.timezone.utc),
        venue_name="Room B", instructor_employee=employee_b, capacity=15,
    )


# ------------------------------------------------------------------ 3.23 Learning Management (LMS) fixtures
@pytest.fixture
def content_item_a(db, tenant_a, training_course_a):
    """A required "video" LearningContentItem on training_course_a, sequence 1."""
    from apps.hrm.models import LearningContentItem
    return LearningContentItem.objects.create(
        tenant=tenant_a, course=training_course_a, title="Intro Video",
        content_type="video", sequence=1, video_url="https://example.com/intro.mp4",
    )


@pytest.fixture
def content_item_b(db, tenant_b, training_course_b):
    """A LearningContentItem belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import LearningContentItem
    return LearningContentItem.objects.create(
        tenant=tenant_b, course=training_course_b, title="Intro Video B",
        content_type="video", sequence=1, video_url="https://example.com/intro-b.mp4",
    )


@pytest.fixture
def learning_path_a(db, tenant_a):
    """A LearningPath for tenant_a — "Engineering Onboarding" — no items yet."""
    from apps.hrm.models import LearningPath
    return LearningPath.objects.create(tenant=tenant_a, title="Engineering Onboarding")


@pytest.fixture
def learning_path_b(db, tenant_b):
    """A LearningPath belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import LearningPath
    return LearningPath.objects.create(tenant=tenant_b, title="Engineering Onboarding B")


@pytest.fixture
def path_item_a(db, tenant_a, learning_path_a, training_course_a):
    """A LearningPathItem linking learning_path_a -> training_course_a at sequence 1."""
    from apps.hrm.models import LearningPathItem
    return LearningPathItem.objects.create(
        tenant=tenant_a, path=learning_path_a, course=training_course_a, sequence=1,
    )


@pytest.fixture
def path_item_b(db, tenant_b, learning_path_b, training_course_b):
    """A LearningPathItem belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import LearningPathItem
    return LearningPathItem.objects.create(
        tenant=tenant_b, path=learning_path_b, course=training_course_b, sequence=1,
    )


@pytest.fixture
def learning_progress_a(db, tenant_a, employee_a, training_course_a):
    """A not_started LearningProgress for employee_a/training_course_a, tenant_a."""
    from apps.hrm.models import LearningProgress
    return LearningProgress.objects.create(
        tenant=tenant_a, employee=employee_a, course=training_course_a,
    )


@pytest.fixture
def learning_progress_b(db, tenant_b, employee_b, training_course_b):
    """A LearningProgress belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import LearningProgress
    return LearningProgress.objects.create(
        tenant=tenant_b, employee=employee_b, course=training_course_b,
    )


# ------------------------------------------------------------------ 3.24 Training Administration fixtures
@pytest.fixture
def nomination_a(db, tenant_a, training_session_a, employee_a):
    """A pending TrainingNomination for employee_a on training_session_a, tenant_a."""
    from apps.hrm.models import TrainingNomination
    return TrainingNomination.objects.create(
        tenant=tenant_a, session=training_session_a, employee=employee_a, nomination_type="self",
    )


@pytest.fixture
def nomination_b(db, tenant_b, training_session_b, employee_b):
    """A pending TrainingNomination belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TrainingNomination
    return TrainingNomination.objects.create(
        tenant=tenant_b, session=training_session_b, employee=employee_b, nomination_type="self",
    )


@pytest.fixture
def training_attendance_a(db, tenant_a, training_session_a, employee_a):
    """A 'present' TrainingAttendance for employee_a on training_session_a, tenant_a (not_completed)."""
    from apps.hrm.models import TrainingAttendance
    return TrainingAttendance.objects.create(
        tenant=tenant_a, session=training_session_a, employee=employee_a, attendance_status="present",
    )


@pytest.fixture
def training_attendance_b(db, tenant_b, training_session_b, employee_b):
    """A TrainingAttendance belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TrainingAttendance
    return TrainingAttendance.objects.create(
        tenant=tenant_b, session=training_session_b, employee=employee_b, attendance_status="present",
    )


@pytest.fixture
def training_feedback_a(db, tenant_a, training_attendance_a):
    """Feedback for training_attendance_a, tenant_a — overall 5 / content 4 / trainer 5."""
    from apps.hrm.models import TrainingFeedback
    return TrainingFeedback.objects.create(
        tenant=tenant_a, attendance=training_attendance_a,
        overall_rating=5, content_rating=4, trainer_rating=5,
    )


@pytest.fixture
def training_feedback_b(db, tenant_b, training_attendance_b):
    """A TrainingFeedback belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TrainingFeedback
    return TrainingFeedback.objects.create(
        tenant=tenant_b, attendance=training_attendance_b,
        overall_rating=4, content_rating=4, trainer_rating=4,
    )


@pytest.fixture
def cert_course_a(db, tenant_a):
    """A certification-granting TrainingCourse for tenant_a — 12-month validity."""
    from apps.hrm.models import TrainingCourse
    return TrainingCourse.objects.create(
        tenant=tenant_a, title="Certified Safety Training", category="safety",
        is_certification=True, certification_name="Safety Certification",
        certification_validity_months=12,
    )


@pytest.fixture
def cert_course_b(db, tenant_b):
    """A certification-granting TrainingCourse belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TrainingCourse
    return TrainingCourse.objects.create(
        tenant=tenant_b, title="Certified Safety Training B", category="safety",
        is_certification=True, certification_name="Safety Certification B",
        certification_validity_months=12,
    )


@pytest.fixture
def training_certificate_a(db, tenant_a, employee_a, cert_course_a):
    """An issued TrainingCertificate for employee_a/cert_course_a, tenant_a — issued 2026-07-01."""
    from apps.hrm.models import TrainingCertificate
    return TrainingCertificate.objects.create(
        tenant=tenant_a, employee=employee_a, course=cert_course_a,
        issued_on=datetime.date(2026, 7, 1),
    )


@pytest.fixture
def training_certificate_b(db, tenant_b, employee_b, cert_course_b):
    """A TrainingCertificate belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import TrainingCertificate
    return TrainingCertificate.objects.create(
        tenant=tenant_b, employee=employee_b, course=cert_course_b,
        issued_on=datetime.date(2026, 7, 1),
    )


# ------------------------------------------------------------------ 3.25 Personal Information (Self-Service) fixtures
@pytest.fixture
def emergency_contact_a(db, tenant_a, employee_a):
    """A primary EmergencyContact for employee_a, tenant_a."""
    from apps.hrm.models import EmergencyContact
    return EmergencyContact.objects.create(
        tenant=tenant_a, employee=employee_a, name="Carol White", relationship="Sibling",
        phone="+1-555-0101", is_primary=True,
    )


@pytest.fixture
def emergency_contact_b(db, tenant_b, employee_b):
    """An EmergencyContact belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import EmergencyContact
    return EmergencyContact.objects.create(
        tenant=tenant_b, employee=employee_b, name="Dana Lee", relationship="Friend",
        phone="+1-555-0202",
    )


@pytest.fixture
def bank_account_a(db, tenant_a, employee_a):
    """A checking EmployeeBankAccount for employee_a, tenant_a — 16-digit account_number so
    masking (last-4) is unambiguous."""
    from apps.hrm.models import EmployeeBankAccount
    return EmployeeBankAccount.objects.create(
        tenant=tenant_a, employee=employee_a, bank_name="First Bank",
        account_holder_name="Alice Smith", account_number="9988776655001122",
        routing_number="DEMO00998877", account_type="checking",
    )


@pytest.fixture
def bank_account_b(db, tenant_b, employee_b):
    """An EmployeeBankAccount belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import EmployeeBankAccount
    return EmployeeBankAccount.objects.create(
        tenant=tenant_b, employee=employee_b, bank_name="Globex Bank",
        account_holder_name="Bob Jones", account_number="1122334455006677",
        routing_number="DEMO00110022", account_type="savings",
    )


@pytest.fixture
def family_member_a(db, tenant_a, employee_a):
    """A dependent (spouse) FamilyMember for employee_a, tenant_a."""
    from apps.hrm.models import FamilyMember
    return FamilyMember.objects.create(
        tenant=tenant_a, employee=employee_a, name="John Smith", relationship="spouse",
        is_dependent=True,
    )


@pytest.fixture
def family_member_b(db, tenant_b, employee_b):
    """A FamilyMember belonging to tenant_b (IDOR tests)."""
    from apps.hrm.models import FamilyMember
    return FamilyMember.objects.create(
        tenant=tenant_b, employee=employee_b, name="Jane Jones", relationship="spouse",
    )


@pytest.fixture
def change_request_a(db, tenant_a, employee_a):
    """A pending profile_field EmployeeInfoChangeRequest for employee_a, tenant_a — proposes a new
    national_id. ``old`` matches employee_a's actual (blank) national_id so ``apply()`` succeeds
    without tripping the lost-update guard. ``requested_by`` is a THIRD user (neither client_a/
    admin_user nor employee_a's own login) so maker-checker self-approval tests aren't accidentally
    satisfied by the shared admin_user/client_a fixtures."""
    from django.contrib.contenttypes.models import ContentType
    from apps.accounts.models import User
    from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
    maker = User.objects.create_user(
        email="maker_icr@acme.com", username="maker_icr_acme", password="TestPass123!",
        tenant=tenant_a, is_tenant_admin=False,
    )
    ct = ContentType.objects.get_for_model(EmployeeProfile)
    return EmployeeInfoChangeRequest.objects.create(
        tenant=tenant_a, employee=employee_a, content_type=ct, object_id=employee_a.pk,
        request_type="profile_field",
        field_changes={"national_id": {"old": "", "new": "AB1234567"}},
        requested_by=maker,
    )


@pytest.fixture
def change_request_b(db, tenant_b, employee_b):
    """A pending profile_field EmployeeInfoChangeRequest belonging to tenant_b (IDOR tests)."""
    from django.contrib.contenttypes.models import ContentType
    from apps.hrm.models import EmployeeInfoChangeRequest, EmployeeProfile
    ct = ContentType.objects.get_for_model(EmployeeProfile)
    return EmployeeInfoChangeRequest.objects.create(
        tenant=tenant_b, employee=employee_b, content_type=ct, object_id=employee_b.pk,
        request_type="profile_field",
        field_changes={"national_id": {"old": "", "new": "XY7654321"}},
    )

