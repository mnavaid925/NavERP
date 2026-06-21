"""HRM app test fixtures.

Reuses the shared root conftest (tenant_a, tenant_b, admin_user, admin_b,
client_a, client_b, member_user, member_client) and adds HRM-specific records:
Party persons, Employment, OrgUnit department, Designation, EmployeeProfile,
LeaveType, LeaveAllocation, LeaveRequest, Shift, AttendanceRecord.
"""
import datetime
from decimal import Decimal

import pytest


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
