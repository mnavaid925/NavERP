"""Tests for HRM models: auto-numbering, __str__, properties, save() logic, clean() guards."""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

pytestmark = pytest.mark.django_db


# ================================================================ Auto-numbering
class TestAutoNumbering:
    def test_employee_profile_number_format(self, employee_a):
        assert employee_a.number.startswith("EMP-")
        assert len(employee_a.number) == 9  # EMP-00001

    def test_employee_profile_number_is_emp_00001(self, employee_a):
        assert employee_a.number == "EMP-00001"

    def test_employee_profile_sequential(self, tenant_a, person_a, person_a2):
        from apps.core.models import Employment
        from apps.hrm.models import EmployeeProfile
        emp1 = EmployeeProfile.objects.create(tenant=tenant_a, party=person_a, employee_type="full_time")
        emp2 = EmployeeProfile.objects.create(tenant=tenant_a, party=person_a2, employee_type="full_time")
        assert emp1.number == "EMP-00001"
        assert emp2.number == "EMP-00002"

    def test_employee_profile_per_tenant_isolation(self, tenant_a, tenant_b, person_a, person_b):
        from apps.hrm.models import EmployeeProfile
        eA = EmployeeProfile.objects.create(tenant=tenant_a, party=person_a, employee_type="full_time")
        eB = EmployeeProfile.objects.create(tenant=tenant_b, party=person_b, employee_type="full_time")
        assert eA.number == "EMP-00001"
        assert eB.number == "EMP-00001"

    def test_leave_allocation_number_format(self, leave_allocation_a):
        assert leave_allocation_a.number.startswith("LA-")
        assert leave_allocation_a.number == "LA-00001"

    def test_leave_request_number_format(self, draft_leave_request):
        assert draft_leave_request.number.startswith("LR-")
        assert draft_leave_request.number == "LR-00001"

    def test_attendance_number_format(self, attendance_a):
        assert attendance_a.number.startswith("ATT-")
        assert attendance_a.number == "ATT-00001"

    def test_number_not_reassigned_on_resave(self, employee_a):
        original = employee_a.number
        employee_a.mobile = "+1-555-9999"
        employee_a.save()
        employee_a.refresh_from_db()
        assert employee_a.number == original

    def test_unique_together_tenant_number(self, tenant_a, employee_a, person_a2):
        from apps.hrm.models import EmployeeProfile
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            EmployeeProfile.objects.create(
                tenant=tenant_a, party=person_a2,
                number="EMP-00001",
                employee_type="full_time",
            )


# ================================================================ EmployeeProfile
class TestEmployeeProfile:
    def test_str_contains_number_and_name(self, employee_a):
        s = str(employee_a)
        assert "EMP-00001" in s
        assert "Alice Smith" in s

    def test_name_property(self, employee_a):
        assert employee_a.name == "Alice Smith"

    def test_department_property_via_employment(self, employee_a, dept_a):
        assert employee_a.department == dept_a

    def test_department_property_none_without_employment(self, tenant_a, person_a2):
        from apps.hrm.models import EmployeeProfile
        emp = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a2, employee_type="full_time"
        )
        assert emp.department is None

    def test_manager_property_via_employment(self, tenant_a, person_a, person_a2, dept_a):
        from apps.core.models import Employment
        from apps.hrm.models import EmployeeProfile
        mgr_employment = Employment.objects.create(
            tenant=tenant_a, party=person_a2, org_unit=dept_a,
            job_title="Manager", status="active"
        )
        # Update employment_a manager
        emp_obj = EmployeeProfile.objects.create(tenant=tenant_a, party=person_a, employee_type="full_time")
        emp_obj.employment = Employment.objects.create(
            tenant=tenant_a, party=person_a, org_unit=dept_a,
            manager=person_a2, status="active"
        )
        emp_obj.save()
        emp_obj.refresh_from_db()
        # Access via refreshed object to trigger property
        assert emp_obj.manager == person_a2

    def test_manager_property_none_without_employment(self, tenant_a, person_a2):
        from apps.hrm.models import EmployeeProfile
        emp = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a2, employee_type="full_time"
        )
        assert emp.manager is None

    def test_masked_bank_account_last_4(self, employee_a):
        # bank_account = "123456789012" → last 4 = "9012"
        masked = employee_a.masked_bank_account()
        assert masked == "••••9012"
        assert "123456789012" not in masked

    def test_masked_bank_account_short(self, tenant_a, person_a2):
        from apps.hrm.models import EmployeeProfile
        emp = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a2, employee_type="full_time", bank_account="12"
        )
        assert emp.masked_bank_account() == "••••"

    def test_masked_bank_account_empty(self, tenant_a, person_a2):
        from apps.hrm.models import EmployeeProfile
        emp = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a2, employee_type="full_time", bank_account=""
        )
        assert emp.masked_bank_account() == ""

    def test_employee_type_choices(self):
        from apps.hrm.models import EmployeeProfile
        keys = [k for k, _ in EmployeeProfile.EMPLOYEE_TYPE_CHOICES]
        for expected in ("full_time", "part_time", "contract", "intern", "consultant"):
            assert expected in keys

    def test_gender_choices(self):
        from apps.hrm.models import EmployeeProfile
        keys = [k for k, _ in EmployeeProfile.GENDER_CHOICES]
        for expected in ("male", "female", "other", "prefer_not_to_say"):
            assert expected in keys

    def test_blood_group_choices(self):
        from apps.hrm.models import EmployeeProfile
        keys = [k for k, _ in EmployeeProfile.BLOOD_GROUP_CHOICES]
        for expected in ("A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"):
            assert expected in keys


# ================================================================ Designation
class TestDesignation:
    def test_str_with_grade(self, designation_a):
        s = str(designation_a)
        assert "Software Engineer" in s
        assert "L2" in s

    def test_str_without_grade(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation.objects.create(tenant=tenant_a, name="Junior Dev", grade="")
        assert str(d) == "Junior Dev"

    def test_clean_rejects_min_gt_max(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation(
            tenant=tenant_a, name="Bad Grade",
            min_salary=Decimal("100000"), max_salary=Decimal("50000")
        )
        with pytest.raises(ValidationError) as exc_info:
            d.clean()
        assert "max_salary" in exc_info.value.message_dict

    def test_clean_accepts_equal_min_max(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation(
            tenant=tenant_a, name="Fixed Pay",
            min_salary=Decimal("80000"), max_salary=Decimal("80000")
        )
        # Should not raise
        d.clean()

    def test_clean_accepts_min_none(self, tenant_a):
        from apps.hrm.models import Designation
        d = Designation(tenant=tenant_a, name="No Range", min_salary=None, max_salary=None)
        d.clean()  # no error

    def test_unique_together_tenant_name(self, tenant_a, designation_a):
        from apps.hrm.models import Designation
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            Designation.objects.create(tenant=tenant_a, name="Software Engineer")


# ================================================================ LeaveType
class TestLeaveType:
    def test_str(self, leave_type_a):
        s = str(leave_type_a)
        assert "Annual Leave" in s
        assert "AL" in s

    def test_clean_requires_accrual_days_when_accruing(self, tenant_a):
        from apps.hrm.models import LeaveType
        lt = LeaveType(
            tenant=tenant_a, name="Bad LT", code="BLT",
            accrual_rule="monthly", accrual_days=Decimal("0")
        )
        with pytest.raises(ValidationError) as exc_info:
            lt.clean()
        assert "accrual_days" in exc_info.value.message_dict

    def test_clean_allows_zero_when_no_accrual(self, tenant_a):
        from apps.hrm.models import LeaveType
        lt = LeaveType(
            tenant=tenant_a, name="Unpaid", code="UPL",
            accrual_rule="none", accrual_days=Decimal("0")
        )
        lt.clean()  # no error

    def test_clean_rejects_negative_accrual_days(self, tenant_a):
        from apps.hrm.models import LeaveType
        lt = LeaveType(
            tenant=tenant_a, name="Neg LT", code="NLT",
            accrual_rule="annual", accrual_days=Decimal("-1")
        )
        with pytest.raises(ValidationError):
            lt.clean()

    def test_accrual_choices(self):
        from apps.hrm.models import LeaveType
        keys = [k for k, _ in LeaveType.ACCRUAL_CHOICES]
        assert set(keys) == {"none", "monthly", "annual"}


# ================================================================ LeaveAllocation
class TestLeaveAllocation:
    def test_str(self, leave_allocation_a, leave_type_a, employee_a):
        s = str(leave_allocation_a)
        assert "LA-00001" in s

    def test_used_days_zero_when_no_requests(self, leave_allocation_a):
        assert leave_allocation_a.used_days == Decimal("0")

    def test_used_days_counts_only_approved(self, tenant_a, leave_allocation_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveRequest
        # Create a pending request - should NOT count
        LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 3, 1), end_date=datetime.date(2026, 3, 3),
            status="pending"
        )
        leave_allocation_a._used_days_cache = None  # reset cache
        if hasattr(leave_allocation_a, "_used_days_cache"):
            del leave_allocation_a._used_days_cache
        assert leave_allocation_a.used_days == Decimal("0")

    def test_used_days_counts_approved_in_same_year(self, tenant_a, leave_allocation_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveRequest
        # 3 days approved in 2026 (the allocation year)
        LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 3, 1), end_date=datetime.date(2026, 3, 3),
            reason="Test", status="approved"
        )
        # Refresh to clear cache
        alloc = type(leave_allocation_a).objects.get(pk=leave_allocation_a.pk)
        assert alloc.used_days == Decimal("3")

    def test_balance_equals_allocated_minus_used(self, tenant_a, leave_allocation_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveRequest
        LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 4, 1), end_date=datetime.date(2026, 4, 2),
            status="approved"
        )
        alloc = type(leave_allocation_a).objects.get(pk=leave_allocation_a.pk)
        # allocated=21, used=2, balance=19
        assert alloc.balance == Decimal("19")

    def test_status_choices(self):
        from apps.hrm.models import LeaveAllocation
        keys = [k for k, _ in LeaveAllocation.STATUS_CHOICES]
        assert set(keys) == {"draft", "active", "expired"}


# ================================================================ LeaveRequest.save() / clean()
class TestLeaveRequest:
    def test_days_computed_on_save(self, draft_leave_request):
        # 2026-07-01 to 2026-07-03 = 3 days, no holidays in window
        assert draft_leave_request.days == Decimal("3")

    def test_days_excludes_non_optional_holidays(self, tenant_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveRequest, PublicHoliday
        # Holiday on 2026-07-04 (non-optional) falls in the range 2026-07-01..2026-07-05
        PublicHoliday.objects.create(
            tenant=tenant_a, date=datetime.date(2026, 7, 4),
            name="Founders Day", is_optional=False
        )
        lr = LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 7, 5),
            status="draft"
        )
        # 5 days range - 1 non-optional holiday = 4 days
        assert lr.days == Decimal("4")

    def test_days_does_not_exclude_optional_holidays(self, tenant_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveRequest, PublicHoliday
        # Optional holiday — should NOT be excluded
        PublicHoliday.objects.create(
            tenant=tenant_a, date=datetime.date(2026, 7, 4),
            name="Optional Holiday", is_optional=True
        )
        lr = LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 7, 1), end_date=datetime.date(2026, 7, 5),
            status="draft"
        )
        assert lr.days == Decimal("5")

    def test_clean_rejects_end_before_start(self, tenant_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveRequest
        lr = LeaveRequest(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 7, 5),
            end_date=datetime.date(2026, 7, 3),
        )
        with pytest.raises(ValidationError) as exc_info:
            lr.clean()
        assert "end_date" in exc_info.value.message_dict

    def test_clean_accepts_same_day(self, tenant_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveRequest
        lr = LeaveRequest(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 7, 1),
            end_date=datetime.date(2026, 7, 1),
        )
        lr.clean()  # should not raise

    def test_status_choices(self):
        from apps.hrm.models import LeaveRequest
        keys = [k for k, _ in LeaveRequest.STATUS_CHOICES]
        for expected in ("draft", "pending", "approved", "rejected", "cancelled"):
            assert expected in keys

    def test_str(self, draft_leave_request):
        s = str(draft_leave_request)
        assert "LR-00001" in s

    def test_days_single_day(self, tenant_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveRequest
        lr = LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 5, 1),
            end_date=datetime.date(2026, 5, 1),
            status="draft"
        )
        assert lr.days == Decimal("1")


# ================================================================ AttendanceRecord.save() / is_late()
class TestAttendanceRecord:
    def test_hours_worked_computed_normal(self, attendance_a):
        # 09:05 -> 18:00 = 8h55m = 8.9167 hours
        # but attendance_a has check_in=09:05, check_out=18:00
        # seconds = (18*60 - 9*60 - 5) * 60 = (1080 - 545) * 60 = 535 * 60 = 32100
        # hours = 32100 / 3600 = 8.916... → quantize to 0.01
        # Actually: 18:00 - 09:05 = 8h55m = 8 + 55/60 = 8.9167 hours
        assert attendance_a.hours_worked == Decimal("8.92")

    def test_hours_worked_overnight_shift(self, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord
        # Night shift: check_in=21:00, check_out=06:00 next day → 9 hours
        att = AttendanceRecord.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            date=datetime.date(2026, 6, 17),
            check_in=datetime.time(21, 0),
            check_out=datetime.time(6, 0),
            shift=shift_a,
            status="present",
            source="web",
        )
        # (06:00 - 21:00) raw = -54000 sec → +24*3600 = 32400 sec = 9.0 hours
        assert att.hours_worked == Decimal("9.00")

    def test_hours_worked_zero_when_no_checkin(self, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            date=datetime.date(2026, 6, 18),
            check_in=None,
            check_out=None,
            shift=shift_a,
            status="absent",
            source="web",
        )
        assert att.hours_worked == Decimal("0")

    def test_is_late_true_past_grace(self, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord
        # Shift start 09:00, grace=15min. Check-in at 09:20 → late (20 > 15)
        att = AttendanceRecord.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            date=datetime.date(2026, 6, 20),
            check_in=datetime.time(9, 20),
            check_out=datetime.time(18, 0),
            shift=shift_a,
            status="present",
            source="web",
        )
        assert att.is_late() is True

    def test_is_late_false_within_grace(self, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord
        # Check-in 09:10, grace=15 → not late (10 <= 15)
        att = AttendanceRecord.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            date=datetime.date(2026, 6, 21),
            check_in=datetime.time(9, 10),
            check_out=datetime.time(18, 0),
            shift=shift_a,
            status="present",
            source="web",
        )
        assert att.is_late() is False

    def test_is_late_false_when_no_shift(self, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            date=datetime.date(2026, 6, 22),
            check_in=datetime.time(10, 0),
            check_out=datetime.time(18, 0),
            shift=None,
            status="present",
            source="web",
        )
        assert att.is_late() is False

    def test_is_late_false_when_no_checkin(self, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord
        att = AttendanceRecord.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            date=datetime.date(2026, 6, 23),
            check_in=None,
            check_out=None,
            shift=shift_a,
            status="absent",
            source="web",
        )
        assert att.is_late() is False

    def test_status_choices(self):
        from apps.hrm.models import AttendanceRecord
        keys = [k for k, _ in AttendanceRecord.STATUS_CHOICES]
        for expected in ("present", "absent", "half_day", "on_leave", "holiday", "regularized"):
            assert expected in keys

    def test_str(self, attendance_a):
        s = str(attendance_a)
        assert "ATT-00001" in s


# ================================================================ Shift
class TestShift:
    def test_str(self, shift_a):
        s = str(shift_a)
        assert "Morning Shift" in s
        assert "09:00" in s

    def test_unique_together_tenant_name(self, tenant_a, shift_a):
        from apps.hrm.models import Shift
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            Shift.objects.create(
                tenant=tenant_a, name="Morning Shift",
                start_time=datetime.time(8, 0), end_time=datetime.time(17, 0)
            )


# ================================================================ PublicHoliday
class TestPublicHoliday:
    def test_str(self, holiday_a):
        s = str(holiday_a)
        assert "2026-07-04" in s
        assert "Founders Day" in s

    def test_unique_together(self, tenant_a, holiday_a):
        from apps.hrm.models import PublicHoliday
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            PublicHoliday.objects.create(
                tenant=tenant_a, date=datetime.date(2026, 7, 4), name="Founders Day"
            )


# ================================================================ LeaveAllocation.used_days_db annotation
class TestLeaveAllocationAnnotation:
    """Verify the _used_days_subquery() annotation (used in views) matches the property."""

    def test_used_days_db_annotation_matches_property(
        self, tenant_a, employee_a, leave_type_a, leave_allocation_a
    ):
        from decimal import Decimal
        from apps.hrm.models import LeaveRequest, LeaveAllocation
        from apps.hrm.views import _used_days_subquery

        # Create an approved request so used_days > 0
        LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 6, 1), end_date=datetime.date(2026, 6, 3),
            status="approved"
        )

        annotated = LeaveAllocation.objects.filter(
            pk=leave_allocation_a.pk
        ).annotate(used_days_db=_used_days_subquery()).first()

        alloc_fresh = LeaveAllocation.objects.get(pk=leave_allocation_a.pk)
        assert annotated.used_days_db == alloc_fresh.used_days
