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

