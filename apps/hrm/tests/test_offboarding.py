"""Comprehensive tests for HRM 3.4 Employee Offboarding sub-module.

Covers:
  - Models: SeparationCase (LWD derivation, all_mandatory_cleared), ExitInterview
            (average_rating, validator bounds), ClearanceItem (department_display),
            FinalSettlement (net_payable).
  - Services: generate_clearance_checklist (idempotency, IT asset link, requires_kt),
              compute_leave_encashment (query count).
  - Views / CRUD: full lifecycle (draft→submit→approve→clearance→cleared→settlement→paid
                  →completed→relieving/experience letters), workflow guards (out-of-order
                  transitions blocked), clearanceitem_mark_cleared asset-return logic.
  - Multi-tenant isolation (IDOR): cross-tenant pk → 404.
  - Permissions: @tenant_admin_required actions → 403/redirect for non-admin member.
  - Form security: status / workflow fields absent from every offboarding form.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ============================================================
# Offboarding-specific fixtures (reuse root + hrm conftest)
# ============================================================

@pytest.fixture
def sep_draft_a(db, tenant_a, employee_a):
    """A draft SeparationCase for employee_a, tenant_a."""
    from apps.hrm.models import SeparationCase
    return SeparationCase.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        separation_type="resignation",
        exit_reason="better_opportunity",
        notice_period_days=30,
        notice_start_date=datetime.date(2026, 7, 1),
        requires_kt=True,
    )


@pytest.fixture
def sep_pending_a(db, tenant_a, employee_a):
    """A pending_approval SeparationCase for employee_a."""
    from apps.hrm.models import SeparationCase
    case = SeparationCase.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        separation_type="resignation",
        notice_period_days=30,
        notice_start_date=datetime.date(2026, 7, 1),
        requires_kt=True,
    )
    # Advance to pending without using the view (direct field write + save with update_fields).
    case.status = "pending_approval"
    case.submitted_at = timezone.now()
    case.save(update_fields=["status", "submitted_at", "updated_at"])
    return case


@pytest.fixture
def sep_in_clearance_a(db, tenant_a, employee_a, admin_user):
    """A SeparationCase already in_clearance (checklist generated) for employee_a."""
    from apps.hrm.models import SeparationCase
    from apps.hrm.services import generate_clearance_checklist
    case = SeparationCase.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        separation_type="resignation",
        notice_period_days=30,
        notice_start_date=datetime.date(2026, 7, 1),
        requires_kt=True,
    )
    case.status = "in_clearance"
    case.approver = admin_user
    case.approved_at = timezone.now()
    case.save(update_fields=["status", "approver", "approved_at", "updated_at"])
    generate_clearance_checklist(case)
    return case


@pytest.fixture
def sep_b(db, tenant_b, employee_b):
    """A SeparationCase for tenant_b (IDOR tests)."""
    from apps.hrm.models import SeparationCase
    return SeparationCase.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        separation_type="resignation",
        notice_period_days=14,
        notice_start_date=datetime.date(2026, 8, 1),
    )


@pytest.fixture
def exit_interview_a(db, tenant_a, sep_in_clearance_a, admin_user):
    """A scheduled ExitInterview for sep_in_clearance_a."""
    from apps.hrm.models import ExitInterview
    return ExitInterview.objects.create(
        tenant=tenant_a,
        case=sep_in_clearance_a,
        interviewer=admin_user,
        scheduled_at=timezone.make_aware(datetime.datetime(2026, 7, 20, 10, 0)),
        mode="in_person",
    )


@pytest.fixture
def exit_interview_b(db, tenant_b, sep_b):
    """An ExitInterview for tenant_b (IDOR tests)."""
    from apps.hrm.models import ExitInterview
    return ExitInterview.objects.create(
        tenant=tenant_b,
        case=sep_b,
        mode="video",
    )


@pytest.fixture
def clearance_item_a(db, tenant_a, sep_in_clearance_a):
    """A single pending clearance item on sep_in_clearance_a for manual tests."""
    from apps.hrm.models import ClearanceItem
    return ClearanceItem.objects.filter(
        tenant=tenant_a, case=sep_in_clearance_a
    ).first()


@pytest.fixture
def clearance_item_b(db, tenant_b, sep_b):
    """A clearance item on tenant_b's case (IDOR tests)."""
    from apps.hrm.models import ClearanceItem
    return ClearanceItem.objects.create(
        tenant=tenant_b,
        case=sep_b,
        department="hr",
        description="Return company laptop",
    )


@pytest.fixture
def sep_cleared_a(db, tenant_a, employee_a, admin_user):
    """A SeparationCase in 'cleared' status (all clearance items resolved)."""
    from apps.hrm.models import SeparationCase, ClearanceItem
    from apps.hrm.services import generate_clearance_checklist
    case = SeparationCase.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        separation_type="resignation",
        notice_period_days=30,
        notice_start_date=datetime.date(2026, 7, 1),
        requires_kt=False,
    )
    case.status = "in_clearance"
    case.approver = admin_user
    case.approved_at = timezone.now()
    case.save(update_fields=["status", "approver", "approved_at", "updated_at"])
    generate_clearance_checklist(case)
    # Mark all items cleared
    ClearanceItem.objects.filter(tenant=tenant_a, case=case).update(
        status="cleared",
        cleared_at=timezone.now(),
    )
    case.status = "cleared"
    case.save(update_fields=["status", "updated_at"])
    return case


@pytest.fixture
def settlement_draft_a(db, tenant_a, sep_cleared_a):
    """A draft FinalSettlement for sep_cleared_a."""
    from apps.hrm.models import FinalSettlement
    return FinalSettlement.objects.create(
        tenant=tenant_a,
        case=sep_cleared_a,
        prorata_salary=Decimal("5000.00"),
        leave_encashment_amount=Decimal("2000.00"),
        notice_recovery_amount=Decimal("500.00"),
    )


@pytest.fixture
def settlement_b(db, tenant_b, sep_b):
    """A FinalSettlement for tenant_b (IDOR tests)."""
    from apps.hrm.models import FinalSettlement
    return FinalSettlement.objects.create(
        tenant=tenant_b,
        case=sep_b,
    )


@pytest.fixture
def issued_asset_a(db, tenant_a, employee_a, admin_user):
    """An issued AssetAllocation for employee_a (used in clearance tests)."""
    from apps.hrm.models import AssetAllocation
    return AssetAllocation.objects.create(
        tenant=tenant_a,
        employee=employee_a,
        asset_name="MacBook Pro",
        asset_category="laptop",
        serial_number="MBP-9999",
        status="issued",
        issued_at=timezone.now(),
        issued_by=admin_user,
    )


@pytest.fixture
def issued_asset_b(db, tenant_b, employee_b):
    """An issued AssetAllocation for employee_b (IDOR tests)."""
    from apps.hrm.models import AssetAllocation
    return AssetAllocation.objects.create(
        tenant=tenant_b,
        employee=employee_b,
        asset_name="Dell XPS",
        asset_category="laptop",
        status="issued",
        issued_at=timezone.now(),
    )


# ============================================================
# Model Tests
# ============================================================

class TestSeparationCaseModel:
    """Auto-numbering, LWD derivation, all_mandatory_cleared, __str__."""

    def test_number_prefix(self, sep_draft_a):
        assert sep_draft_a.number.startswith("SEP-")

    def test_number_format_first(self, sep_draft_a):
        assert sep_draft_a.number == "SEP-00001"

    def test_str_contains_number_and_status(self, sep_draft_a):
        s = str(sep_draft_a)
        assert "SEP-00001" in s
        assert "Draft" in s

    def test_expected_lwd_derived_on_save(self, sep_draft_a):
        """notice_start_date + notice_period_days must be persisted as expected_last_working_day."""
        sep_draft_a.refresh_from_db()
        assert sep_draft_a.expected_last_working_day == datetime.date(2026, 7, 31)  # 2026-07-01 + 30

    def test_expected_lwd_recomputed_after_period_change_via_update_fields(self, sep_draft_a):
        """The fix: changing notice_period_days and saving with update_fields=['notice_period_days']
        must also persist the freshly-derived expected_last_working_day (the save() hook adds
        'expected_last_working_day' to the list automatically)."""
        sep_draft_a.notice_period_days = 60
        sep_draft_a.save(update_fields=["notice_period_days", "updated_at"])
        sep_draft_a.refresh_from_db()
        assert sep_draft_a.expected_last_working_day == datetime.date(2026, 8, 30)  # 2026-07-01 + 60

    def test_expected_lwd_none_when_no_start_date(self, tenant_a, employee_a):
        from apps.hrm.models import SeparationCase
        case = SeparationCase.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            notice_period_days=30,
            # no notice_start_date
        )
        assert case.expected_last_working_day is None

    def test_all_mandatory_cleared_true_when_no_mandatory_items(self, sep_in_clearance_a):
        """An in-clearance case with no mandatory items should show as cleared."""
        from apps.hrm.models import ClearanceItem
        # Mark all mandatory items not_applicable to exclude them from blocking
        ClearanceItem.objects.filter(
            tenant=sep_in_clearance_a.tenant,
            case=sep_in_clearance_a,
            is_mandatory=True,
        ).update(status="not_applicable")
        sep_in_clearance_a.refresh_from_db()
        assert sep_in_clearance_a.all_mandatory_cleared is True

    def test_all_mandatory_cleared_false_when_pending_mandatory(self, sep_in_clearance_a):
        """At least one pending mandatory item → False."""
        assert sep_in_clearance_a.all_mandatory_cleared is False

    def test_all_mandatory_cleared_true_when_all_mandatory_cleared(self, sep_in_clearance_a):
        from apps.hrm.models import ClearanceItem
        ClearanceItem.objects.filter(
            tenant=sep_in_clearance_a.tenant,
            case=sep_in_clearance_a,
            is_mandatory=True,
        ).update(status="cleared")
        sep_in_clearance_a.refresh_from_db()
        assert sep_in_clearance_a.all_mandatory_cleared is True

    def test_all_mandatory_cleared_respects_not_applicable(self, sep_in_clearance_a):
        """not_applicable also satisfies the gate."""
        from apps.hrm.models import ClearanceItem
        ClearanceItem.objects.filter(
            tenant=sep_in_clearance_a.tenant,
            case=sep_in_clearance_a,
            is_mandatory=True,
        ).update(status="not_applicable")
        sep_in_clearance_a.refresh_from_db()
        assert sep_in_clearance_a.all_mandatory_cleared is True

    def test_status_default_draft(self, sep_draft_a):
        assert sep_draft_a.status == "draft"

    def test_status_choices(self):
        from apps.hrm.models import SeparationCase
        keys = [k for k, _ in SeparationCase.STATUS_CHOICES]
        for expected in ("draft", "pending_approval", "in_clearance", "cleared",
                         "settled", "completed", "rejected", "withdrawn"):
            assert expected in keys

    def test_number_isolated_per_tenant(self, tenant_a, tenant_b, employee_a, employee_b):
        from apps.hrm.models import SeparationCase
        cA = SeparationCase.objects.create(
            tenant=tenant_a, employee=employee_a, notice_period_days=30,
            notice_start_date=datetime.date(2026, 7, 1))
        cB = SeparationCase.objects.create(
            tenant=tenant_b, employee=employee_b, notice_period_days=14,
            notice_start_date=datetime.date(2026, 8, 1))
        assert cA.number == "SEP-00001"
        assert cB.number == "SEP-00001"

    def test_letter_ready_statuses(self):
        from apps.hrm.models import SeparationCase
        assert set(SeparationCase.LETTER_READY_STATUSES) == {"cleared", "settled", "completed"}


class TestExitInterviewModel:
    """average_rating, validator bounds, __str__, EI_STATUS_CHOICES."""

    def test_number_prefix(self, exit_interview_a):
        assert exit_interview_a.number.startswith("EI-")

    def test_str_contains_number(self, exit_interview_a):
        s = str(exit_interview_a)
        assert "EI-" in s

    def test_average_rating_none_when_all_null(self, exit_interview_a):
        assert exit_interview_a.average_rating is None

    def test_average_rating_single_value(self, exit_interview_a):
        exit_interview_a.rating_overall = 4
        assert exit_interview_a.average_rating == 4.0

    def test_average_rating_mixed(self, exit_interview_a):
        exit_interview_a.rating_job_satisfaction = 3
        exit_interview_a.rating_management = 5
        exit_interview_a.rating_overall = 4
        expected = round((3 + 5 + 4) / 3, 1)
        assert exit_interview_a.average_rating == expected

    def test_average_rating_all_filled(self, exit_interview_a):
        for field, _ in exit_interview_a.RATING_FIELDS:
            setattr(exit_interview_a, field, 3)
        assert exit_interview_a.average_rating == 3.0

    def test_rating_validator_rejects_zero(self, exit_interview_a):
        exit_interview_a.rating_overall = 0
        with pytest.raises(ValidationError):
            exit_interview_a.full_clean()

    def test_rating_validator_rejects_six(self, exit_interview_a):
        exit_interview_a.rating_overall = 6
        with pytest.raises(ValidationError):
            exit_interview_a.full_clean()

    def test_rating_validator_accepts_one(self, exit_interview_a):
        exit_interview_a.rating_overall = 1
        # full_clean must not raise (only check rating_overall field)
        try:
            exit_interview_a.full_clean()
        except ValidationError as e:
            assert "rating_overall" not in e.message_dict

    def test_rating_validator_accepts_five(self, exit_interview_a):
        exit_interview_a.rating_overall = 5
        try:
            exit_interview_a.full_clean()
        except ValidationError as e:
            assert "rating_overall" not in e.message_dict

    def test_status_default_scheduled(self, exit_interview_a):
        assert exit_interview_a.status == "scheduled"

    def test_ei_status_choices(self):
        from apps.hrm.models import ExitInterview
        keys = [k for k, _ in ExitInterview.EI_STATUS_CHOICES]
        assert set(keys) == {"scheduled", "completed", "skipped", "no_show"}


class TestClearanceItemModel:
    """department_display, CLEARANCE_STATUS_CHOICES, __str__."""

    def test_str_contains_dept_and_desc(self, clearance_item_a):
        s = str(clearance_item_a)
        assert "Pending" in s  # status display

    def test_department_display_standard(self, clearance_item_a):
        """For a non-custom department, department_display returns the Choice label."""
        clearance_item_a.department = "hr"
        clearance_item_a.department_label = ""
        assert clearance_item_a.department_display == "HR"

    def test_department_display_custom_with_label(self, clearance_item_a):
        clearance_item_a.department = "custom"
        clearance_item_a.department_label = "Library Clearance"
        assert clearance_item_a.department_display == "Library Clearance"

    def test_department_display_custom_without_label_falls_back(self, clearance_item_a):
        clearance_item_a.department = "custom"
        clearance_item_a.department_label = ""
        # Falls back to choice label "Custom"
        assert clearance_item_a.department_display == "Custom"

    def test_status_default_pending(self, clearance_item_a):
        assert clearance_item_a.status == "pending"

    def test_status_choices(self):
        from apps.hrm.models import ClearanceItem
        keys = [k for k, _ in ClearanceItem.CLEARANCE_STATUS_CHOICES]
        assert set(keys) == {"pending", "in_progress", "cleared", "not_applicable", "rejected"}

    def test_resolved_statuses_constant(self):
        from apps.hrm.models import ClearanceItem
        assert set(ClearanceItem.RESOLVED_STATUSES) == {"cleared", "not_applicable"}


class TestFinalSettlementModel:
    """net_payable, total_earnings, total_deductions, __str__, FNF_STATUS_CHOICES."""

    def test_number_prefix(self, settlement_draft_a):
        assert settlement_draft_a.number.startswith("FNF-")

    def test_str_contains_number(self, settlement_draft_a):
        s = str(settlement_draft_a)
        assert "FNF-" in s

    def test_net_payable_basic(self, settlement_draft_a):
        # prorata=5000, leave=2000 earnings; notice_recovery=500 deduction
        # total_earnings = 5000 + 2000 = 7000, total_deductions = 500
        assert settlement_draft_a.net_payable == Decimal("6500.00")

    def test_net_payable_mixed_values(self, tenant_a, sep_cleared_a):
        from apps.hrm.models import FinalSettlement
        fnf = FinalSettlement.objects.create(
            tenant=tenant_a,
            case=sep_cleared_a,
            prorata_salary=Decimal("10000.00"),
            leave_encashment_amount=Decimal("3000.00"),
            gratuity_amount=Decimal("5000.00"),
            bonus_amount=Decimal("2000.00"),
            reimbursement_amount=Decimal("500.00"),
            other_income=Decimal("100.00"),
            notice_recovery_amount=Decimal("1000.00"),
            loan_recovery=Decimal("500.00"),
            asset_deduction=Decimal("200.00"),
            advance_recovery=Decimal("300.00"),
            tax_deduction=Decimal("1500.00"),
            professional_tax=Decimal("50.00"),
            other_deduction=Decimal("50.00"),
        )
        expected_earnings = Decimal("10000.00") + Decimal("3000.00") + Decimal("5000.00") + Decimal("2000.00") + Decimal("500.00") + Decimal("100.00")
        expected_deductions = Decimal("1000.00") + Decimal("500.00") + Decimal("200.00") + Decimal("300.00") + Decimal("1500.00") + Decimal("50.00") + Decimal("50.00")
        assert fnf.total_earnings == expected_earnings
        assert fnf.total_deductions == expected_deductions
        assert fnf.net_payable == expected_earnings - expected_deductions

    def test_status_default_draft(self, settlement_draft_a):
        assert settlement_draft_a.status == "draft"

    def test_fnf_status_choices(self):
        from apps.hrm.models import FinalSettlement
        keys = [k for k, _ in FinalSettlement.FNF_STATUS_CHOICES]
        assert set(keys) == {"draft", "computed", "hr_approved", "finance_approved", "paid", "cancelled"}

    def test_unique_case_constraint(self, tenant_a, sep_cleared_a, settlement_draft_a):
        """A second settlement for the same case raises IntegrityError."""
        from apps.hrm.models import FinalSettlement
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            FinalSettlement.objects.create(tenant=tenant_a, case=sep_cleared_a)


# ============================================================
# Service Tests
# ============================================================

class TestGenerateClearanceChecklist:
    """generate_clearance_checklist: idempotency, expected lines, IT asset, requires_kt."""

    def test_creates_default_lines(self, sep_pending_a, admin_user):
        from apps.hrm.models import SeparationCase, ClearanceItem
        from apps.hrm.services import generate_clearance_checklist
        sep_pending_a.status = "in_clearance"
        sep_pending_a.save(update_fields=["status", "updated_at"])
        count = generate_clearance_checklist(sep_pending_a)
        # Default lines from _CLEARANCE_LINES: it, hr, finance, admin, manager, legal = 6
        assert count == 6
        assert ClearanceItem.objects.filter(
            tenant=sep_pending_a.tenant, case=sep_pending_a
        ).count() == 6

    def test_idempotent_second_call_returns_zero(self, sep_in_clearance_a):
        from apps.hrm.services import generate_clearance_checklist
        second = generate_clearance_checklist(sep_in_clearance_a)
        assert second == 0

    def test_idempotent_no_duplicates(self, sep_in_clearance_a):
        from apps.hrm.models import ClearanceItem
        from apps.hrm.services import generate_clearance_checklist
        generate_clearance_checklist(sep_in_clearance_a)
        count = ClearanceItem.objects.filter(
            tenant=sep_in_clearance_a.tenant, case=sep_in_clearance_a
        ).count()
        assert count == 6

    def test_it_line_linked_to_issued_asset(
        self, tenant_a, employee_a, admin_user, issued_asset_a
    ):
        """The IT clearance line is linked to the employee's issued asset."""
        from apps.hrm.models import SeparationCase, ClearanceItem
        from apps.hrm.services import generate_clearance_checklist
        case = SeparationCase.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            notice_period_days=30,
            notice_start_date=datetime.date(2026, 7, 1),
            requires_kt=True,
        )
        case.status = "in_clearance"
        case.approver = admin_user
        case.approved_at = timezone.now()
        case.save(update_fields=["status", "approver", "approved_at", "updated_at"])
        generate_clearance_checklist(case)
        it_line = ClearanceItem.objects.get(tenant=tenant_a, case=case, department="it")
        assert it_line.asset_allocation_id == issued_asset_a.pk

    def test_it_line_no_asset_when_none_issued(self, sep_in_clearance_a):
        """If no asset is issued to the employee, IT line has no linked asset."""
        from apps.hrm.models import ClearanceItem
        # sep_in_clearance_a was created without an issued asset fixture
        it_line = ClearanceItem.objects.filter(
            tenant=sep_in_clearance_a.tenant, case=sep_in_clearance_a, department="it"
        ).first()
        if it_line:
            assert it_line.asset_allocation_id is None

    def test_manager_line_mandatory_when_requires_kt_true(self, sep_in_clearance_a):
        """Manager/KT line is mandatory when requires_kt=True."""
        from apps.hrm.models import ClearanceItem
        assert sep_in_clearance_a.requires_kt is True
        manager_line = ClearanceItem.objects.filter(
            tenant=sep_in_clearance_a.tenant,
            case=sep_in_clearance_a,
            department="manager"
        ).first()
        assert manager_line is not None
        assert manager_line.is_mandatory is True

    def test_manager_line_not_mandatory_when_requires_kt_false(
        self, tenant_a, employee_a, admin_user
    ):
        """Manager/KT line is not mandatory when requires_kt=False."""
        from apps.hrm.models import SeparationCase, ClearanceItem
        from apps.hrm.services import generate_clearance_checklist
        case = SeparationCase.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            notice_period_days=30,
            notice_start_date=datetime.date(2026, 7, 1),
            requires_kt=False,
        )
        case.status = "in_clearance"
        case.approver = admin_user
        case.approved_at = timezone.now()
        case.save(update_fields=["status", "approver", "approved_at", "updated_at"])
        generate_clearance_checklist(case)
        manager_line = ClearanceItem.objects.get(
            tenant=tenant_a, case=case, department="manager"
        )
        assert manager_line.is_mandatory is False

    def test_it_and_hr_and_finance_are_mandatory(self, sep_in_clearance_a):
        from apps.hrm.models import ClearanceItem
        for dept in ("it", "hr", "finance"):
            line = ClearanceItem.objects.get(
                tenant=sep_in_clearance_a.tenant, case=sep_in_clearance_a, department=dept
            )
            assert line.is_mandatory is True, f"{dept} should be mandatory"


class TestComputeLeaveEncashment:
    """compute_leave_encashment: sums encashable allocations, bounded queries."""

    def test_zero_when_no_allocations(self, employee_a):
        from apps.hrm.services import compute_leave_encashment
        days, amount = compute_leave_encashment(employee_a)
        assert days == Decimal("0")
        assert amount == Decimal("0")

    def test_sums_encashable_allocations(self, employee_a, tenant_a, leave_type_a, leave_allocation_a):
        """leave_type_a is encashable with 21 days allocated, 0 used → 21 encashable days."""
        from apps.hrm.services import compute_leave_encashment
        days, amount = compute_leave_encashment(employee_a)
        assert days == Decimal("21")

    def test_amount_uses_designation_min_salary(self, employee_a, tenant_a, leave_type_a, leave_allocation_a):
        """amount = days * (min_salary / 30)."""
        from apps.hrm.services import compute_leave_encashment
        days, amount = compute_leave_encashment(employee_a)
        # designation_a.min_salary = 60000 (from conftest)
        expected_amount = (days * (Decimal("60000") / Decimal("30"))).quantize(Decimal("0.01"))
        assert amount == expected_amount

    def test_excludes_non_encashable_leave(self, tenant_a, employee_a):
        """Non-encashable leave types are not summed."""
        from apps.hrm.models import LeaveType, LeaveAllocation
        from apps.hrm.services import compute_leave_encashment
        non_enc = LeaveType.objects.create(
            tenant=tenant_a, name="Sick Leave", code="SL", encashable=False,
            accrual_rule="none",
        )
        LeaveAllocation.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=non_enc,
            year=timezone.localdate().year, allocated_days=Decimal("10"), status="active"
        )
        days, _ = compute_leave_encashment(employee_a)
        # Only 0 days (no encashable allocation) → no non-encashable sick days counted
        assert days == Decimal("0")

    def test_bounded_query_count(self, employee_a, tenant_a, leave_type_a, leave_allocation_a, django_assert_max_num_queries):
        """The service must not run more than 5 queries for a simple encashable allocation."""
        from apps.hrm.services import compute_leave_encashment
        with django_assert_max_num_queries(5):
            compute_leave_encashment(employee_a)

    def test_no_amount_when_no_min_salary(self, tenant_a, employee_a):
        """If designation has no min_salary, amount is 0 but days are still counted."""
        from apps.hrm.models import LeaveType, LeaveAllocation, Designation
        from apps.hrm.services import compute_leave_encashment
        # Remove designation salary band
        if employee_a.designation_id and employee_a.designation:
            employee_a.designation.min_salary = None
            employee_a.designation.save(update_fields=["min_salary", "updated_at"])
        enc_type = LeaveType.objects.create(
            tenant=tenant_a, name="Flex Leave", code="FL", encashable=True,
            accrual_rule="annual", accrual_days=Decimal("10"),
        )
        LeaveAllocation.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=enc_type,
            year=timezone.localdate().year, allocated_days=Decimal("5"), status="active"
        )
        days, amount = compute_leave_encashment(employee_a)
        assert days > 0
        assert amount == Decimal("0")


# ============================================================
# View / CRUD / Workflow Tests
# ============================================================

class TestSeparationCaseViews:
    """CRUD list/create/detail/edit/delete."""

    def test_list_200(self, client_a, sep_draft_a):
        resp = client_a.get(reverse("hrm:separationcase_list"))
        assert resp.status_code == 200

    def test_list_contains_own(self, client_a, sep_draft_a):
        resp = client_a.get(reverse("hrm:separationcase_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert sep_draft_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, sep_draft_a, sep_b):
        resp = client_a.get(reverse("hrm:separationcase_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert sep_b.pk not in pks

    def test_create_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:separationcase_create"))
        assert resp.status_code == 200

    def test_create_post_creates_with_correct_tenant(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import SeparationCase
        resp = client_a.post(reverse("hrm:separationcase_create"), {
            "employee": employee_a.pk,
            "separation_type": "resignation",
            "exit_reason": "better_opportunity",
            "notice_period_days": 30,
            "notice_start_date": "2026-07-01",
            "notice_buyout_type": "none",
            "requires_kt": "on",
            "notes": "",
        })
        assert resp.status_code == 302
        assert SeparationCase.objects.filter(tenant=tenant_a, employee=employee_a).exists()

    def test_detail_200(self, client_a, sep_draft_a):
        resp = client_a.get(reverse("hrm:separationcase_detail", args=[sep_draft_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, sep_draft_a):
        resp = client_a.get(reverse("hrm:separationcase_detail", args=[sep_draft_a.pk]))
        for key in ("obj", "clearance_items", "clearance_total", "all_mandatory_cleared", "settlement"):
            assert key in resp.context, f"context missing key: {key}"

    def test_edit_get_200_on_draft(self, client_a, sep_draft_a):
        resp = client_a.get(reverse("hrm:separationcase_edit", args=[sep_draft_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_saves(self, client_a, sep_draft_a):
        from apps.hrm.models import SeparationCase
        resp = client_a.post(reverse("hrm:separationcase_edit", args=[sep_draft_a.pk]), {
            "employee": sep_draft_a.employee_id,
            "separation_type": "termination",
            "exit_reason": "performance",
            "notice_period_days": 14,
            "notice_start_date": "2026-07-01",
            "notice_buyout_type": "none",
            "requires_kt": "",
            "notes": "",
        })
        assert resp.status_code == 302
        sep_draft_a.refresh_from_db()
        assert sep_draft_a.separation_type == "termination"

    def test_delete_draft_removes_row(self, client_a, tenant_a, employee_a):
        from apps.hrm.models import SeparationCase
        case = SeparationCase.objects.create(
            tenant=tenant_a, employee=employee_a, notice_period_days=30,
            notice_start_date=datetime.date(2026, 9, 1),
        )
        pk = case.pk
        resp = client_a.post(reverse("hrm:separationcase_delete", args=[pk]))
        assert resp.status_code == 302
        assert not SeparationCase.objects.filter(pk=pk).exists()

    def test_delete_non_draft_blocked(self, client_a, sep_pending_a):
        from apps.hrm.models import SeparationCase
        resp = client_a.post(reverse("hrm:separationcase_delete", args=[sep_pending_a.pk]))
        assert resp.status_code == 302
        assert SeparationCase.objects.filter(pk=sep_pending_a.pk).exists()

    def test_anon_redirect_to_login(self, client):
        resp = client.get(reverse("hrm:separationcase_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestSeparationCaseWorkflow:
    """Full lifecycle: draft→submit→approve→clearance→cleared→complete; workflow guards."""

    def test_submit_changes_status(self, client_a, sep_draft_a):
        resp = client_a.post(reverse("hrm:separationcase_submit", args=[sep_draft_a.pk]))
        assert resp.status_code == 302
        sep_draft_a.refresh_from_db()
        assert sep_draft_a.status == "pending_approval"

    def test_submit_stamps_submitted_at(self, client_a, sep_draft_a):
        client_a.post(reverse("hrm:separationcase_submit", args=[sep_draft_a.pk]))
        sep_draft_a.refresh_from_db()
        assert sep_draft_a.submitted_at is not None

    def test_submit_non_draft_is_noop(self, client_a, sep_pending_a):
        """Submitting an already-pending case must not change its status."""
        client_a.post(reverse("hrm:separationcase_submit", args=[sep_pending_a.pk]))
        sep_pending_a.refresh_from_db()
        assert sep_pending_a.status == "pending_approval"

    def test_approve_changes_status_to_in_clearance(self, client_a, sep_pending_a):
        resp = client_a.post(reverse("hrm:separationcase_approve", args=[sep_pending_a.pk]))
        assert resp.status_code == 302
        sep_pending_a.refresh_from_db()
        assert sep_pending_a.status == "in_clearance"

    def test_approve_generates_clearance_checklist(self, client_a, sep_pending_a):
        from apps.hrm.models import ClearanceItem
        client_a.post(reverse("hrm:separationcase_approve", args=[sep_pending_a.pk]))
        count = ClearanceItem.objects.filter(
            tenant=sep_pending_a.tenant, case=sep_pending_a
        ).count()
        assert count == 6  # 6 default lines

    def test_approve_stamps_approver(self, client_a, sep_pending_a, admin_user):
        client_a.post(reverse("hrm:separationcase_approve", args=[sep_pending_a.pk]))
        sep_pending_a.refresh_from_db()
        assert sep_pending_a.approver_id == admin_user.pk
        assert sep_pending_a.approved_at is not None

    def test_approve_non_pending_is_noop(self, client_a, sep_draft_a):
        """Approving a draft case (not pending_approval) is a no-op."""
        resp = client_a.post(reverse("hrm:separationcase_approve", args=[sep_draft_a.pk]))
        assert resp.status_code == 302
        sep_draft_a.refresh_from_db()
        assert sep_draft_a.status == "draft"

    def test_reject_changes_status(self, client_a, sep_pending_a):
        resp = client_a.post(reverse("hrm:separationcase_reject", args=[sep_pending_a.pk]),
                             {"reason": "Insufficient notice"})
        assert resp.status_code == 302
        sep_pending_a.refresh_from_db()
        assert sep_pending_a.status == "rejected"
        assert "Insufficient notice" in sep_pending_a.rejection_reason

    def test_withdraw_changes_status(self, client_a, sep_draft_a):
        resp = client_a.post(reverse("hrm:separationcase_withdraw", args=[sep_draft_a.pk]),
                             {"reason": "Changed mind"})
        assert resp.status_code == 302
        sep_draft_a.refresh_from_db()
        assert sep_draft_a.status == "withdrawn"

    def test_mark_cleared_blocked_when_mandatory_pending(self, client_a, sep_in_clearance_a):
        """mark-cleared must fail when mandatory items are still pending."""
        resp = client_a.post(reverse("hrm:separationcase_mark_cleared", args=[sep_in_clearance_a.pk]))
        assert resp.status_code == 302
        sep_in_clearance_a.refresh_from_db()
        assert sep_in_clearance_a.status == "in_clearance"

    def test_mark_cleared_succeeds_when_all_mandatory_resolved(
        self, client_a, sep_in_clearance_a
    ):
        from apps.hrm.models import ClearanceItem
        ClearanceItem.objects.filter(
            tenant=sep_in_clearance_a.tenant, case=sep_in_clearance_a, is_mandatory=True
        ).update(status="cleared")
        resp = client_a.post(
            reverse("hrm:separationcase_mark_cleared", args=[sep_in_clearance_a.pk])
        )
        assert resp.status_code == 302
        sep_in_clearance_a.refresh_from_db()
        assert sep_in_clearance_a.status == "cleared"

    def test_complete_from_cleared(self, client_a, sep_cleared_a):
        resp = client_a.post(reverse("hrm:separationcase_complete", args=[sep_cleared_a.pk]))
        assert resp.status_code == 302
        sep_cleared_a.refresh_from_db()
        assert sep_cleared_a.status == "completed"

    def test_complete_from_in_clearance_blocked(self, client_a, sep_in_clearance_a):
        """Complete requires cleared or settled — in_clearance is not valid."""
        resp = client_a.post(reverse("hrm:separationcase_complete", args=[sep_in_clearance_a.pk]))
        assert resp.status_code == 302
        sep_in_clearance_a.refresh_from_db()
        assert sep_in_clearance_a.status == "in_clearance"


class TestSeparationCaseLetters:
    """Relieving and experience letter generation — stamp once, 200 response."""

    def test_relieving_letter_200(self, client_a, sep_cleared_a):
        resp = client_a.post(
            reverse("hrm:separationcase_relieving_letter", args=[sep_cleared_a.pk])
        )
        assert resp.status_code == 200

    def test_relieving_letter_stamps_generated_at(self, client_a, sep_cleared_a):
        client_a.post(reverse("hrm:separationcase_relieving_letter", args=[sep_cleared_a.pk]))
        sep_cleared_a.refresh_from_db()
        assert sep_cleared_a.relieving_letter_generated_at is not None

    def test_relieving_letter_blocked_before_cleared(self, client_a, sep_in_clearance_a):
        resp = client_a.post(
            reverse("hrm:separationcase_relieving_letter", args=[sep_in_clearance_a.pk])
        )
        # Should redirect to detail with an error message
        assert resp.status_code == 302
        sep_in_clearance_a.refresh_from_db()
        assert sep_in_clearance_a.relieving_letter_generated_at is None

    def test_experience_letter_200(self, client_a, sep_cleared_a):
        resp = client_a.post(
            reverse("hrm:separationcase_experience_letter", args=[sep_cleared_a.pk])
        )
        assert resp.status_code == 200

    def test_experience_letter_stamps_generated_at(self, client_a, sep_cleared_a):
        client_a.post(reverse("hrm:separationcase_experience_letter", args=[sep_cleared_a.pk]))
        sep_cleared_a.refresh_from_db()
        assert sep_cleared_a.experience_letter_generated_at is not None

    def test_letter_generated_by_stamped(self, client_a, sep_cleared_a, admin_user):
        client_a.post(reverse("hrm:separationcase_relieving_letter", args=[sep_cleared_a.pk]))
        sep_cleared_a.refresh_from_db()
        assert sep_cleared_a.relieving_letter_generated_by_id == admin_user.pk


class TestExitInterviewViews:
    """CRUD list/create/detail/edit/delete + complete/skip workflow."""

    def test_list_200(self, client_a, exit_interview_a):
        resp = client_a.get(reverse("hrm:exitinterview_list"))
        assert resp.status_code == 200

    def test_list_excludes_other_tenant(self, client_a, exit_interview_a, exit_interview_b):
        resp = client_a.get(reverse("hrm:exitinterview_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert exit_interview_b.pk not in pks

    def test_detail_200(self, client_a, exit_interview_a):
        resp = client_a.get(reverse("hrm:exitinterview_detail", args=[exit_interview_a.pk]))
        assert resp.status_code == 200

    def test_complete_changes_status(self, client_a, exit_interview_a):
        resp = client_a.post(reverse("hrm:exitinterview_complete", args=[exit_interview_a.pk]))
        assert resp.status_code == 302
        exit_interview_a.refresh_from_db()
        assert exit_interview_a.status == "completed"

    def test_complete_stamps_conducted_at(self, client_a, exit_interview_a):
        client_a.post(reverse("hrm:exitinterview_complete", args=[exit_interview_a.pk]))
        exit_interview_a.refresh_from_db()
        assert exit_interview_a.conducted_at is not None

    def test_complete_already_completed_is_noop(self, client_a, exit_interview_a):
        # Complete it first
        client_a.post(reverse("hrm:exitinterview_complete", args=[exit_interview_a.pk]))
        exit_interview_a.refresh_from_db()
        first_conducted_at = exit_interview_a.conducted_at
        # Try to complete again — must remain completed (no status regression)
        client_a.post(reverse("hrm:exitinterview_complete", args=[exit_interview_a.pk]))
        exit_interview_a.refresh_from_db()
        assert exit_interview_a.status == "completed"
        assert exit_interview_a.conducted_at == first_conducted_at

    def test_skip_changes_status(self, client_a, exit_interview_a):
        resp = client_a.post(reverse("hrm:exitinterview_skip", args=[exit_interview_a.pk]))
        assert resp.status_code == 302
        exit_interview_a.refresh_from_db()
        assert exit_interview_a.status == "skipped"

    def test_skip_already_completed_is_noop(self, client_a, exit_interview_a):
        """Skipping a completed interview must not change its status."""
        client_a.post(reverse("hrm:exitinterview_complete", args=[exit_interview_a.pk]))
        client_a.post(reverse("hrm:exitinterview_skip", args=[exit_interview_a.pk]))
        exit_interview_a.refresh_from_db()
        assert exit_interview_a.status == "completed"

    def test_delete_removes_scheduled(self, client_a, tenant_a, sep_in_clearance_a, admin_user):
        from apps.hrm.models import ExitInterview
        ei = ExitInterview.objects.create(
            tenant=tenant_a,
            case=sep_in_clearance_a,
            interviewer=admin_user,
            mode="phone",
        )
        pk = ei.pk
        resp = client_a.post(reverse("hrm:exitinterview_delete", args=[pk]))
        assert resp.status_code == 302
        assert not ExitInterview.objects.filter(pk=pk).exists()

    def test_delete_completed_blocked(self, client_a, exit_interview_a):
        from apps.hrm.models import ExitInterview
        client_a.post(reverse("hrm:exitinterview_complete", args=[exit_interview_a.pk]))
        resp = client_a.post(reverse("hrm:exitinterview_delete", args=[exit_interview_a.pk]))
        assert resp.status_code == 302
        assert ExitInterview.objects.filter(pk=exit_interview_a.pk).exists()


class TestClearanceItemViews:
    """CRUD + mark_cleared (with asset return) + mark_na + reject workflow."""

    def test_list_200(self, client_a, clearance_item_a):
        resp = client_a.get(reverse("hrm:clearanceitem_list"))
        assert resp.status_code == 200

    def test_list_excludes_other_tenant(self, client_a, clearance_item_a, clearance_item_b):
        resp = client_a.get(reverse("hrm:clearanceitem_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert clearance_item_b.pk not in pks

    def test_detail_200(self, client_a, clearance_item_a):
        resp = client_a.get(reverse("hrm:clearanceitem_detail", args=[clearance_item_a.pk]))
        assert resp.status_code == 200

    def test_mark_cleared_changes_status(self, client_a, clearance_item_a):
        resp = client_a.post(reverse("hrm:clearanceitem_mark_cleared", args=[clearance_item_a.pk]))
        assert resp.status_code == 302
        clearance_item_a.refresh_from_db()
        assert clearance_item_a.status == "cleared"

    def test_mark_cleared_stamps_cleared_at_and_by(self, client_a, clearance_item_a, admin_user):
        client_a.post(reverse("hrm:clearanceitem_mark_cleared", args=[clearance_item_a.pk]))
        clearance_item_a.refresh_from_db()
        assert clearance_item_a.cleared_at is not None
        assert clearance_item_a.cleared_by_id == admin_user.pk

    def test_mark_cleared_with_issued_asset_returns_asset(
        self, client_a, tenant_a, employee_a, admin_user, issued_asset_a, sep_in_clearance_a
    ):
        """Clearing a line linked to an issued asset of the same employee flips the asset to returned."""
        from apps.hrm.models import ClearanceItem, AssetAllocation
        # Link issued_asset_a to the IT clearance line
        it_line = ClearanceItem.objects.filter(
            tenant=tenant_a, case=sep_in_clearance_a, department="it"
        ).first()
        assert it_line is not None
        it_line.asset_allocation = issued_asset_a
        it_line.save(update_fields=["asset_allocation", "updated_at"])
        client_a.post(reverse("hrm:clearanceitem_mark_cleared", args=[it_line.pk]))
        issued_asset_a.refresh_from_db()
        assert issued_asset_a.status == "returned"
        assert issued_asset_a.returned_at is not None

    def test_mark_cleared_does_not_return_asset_of_different_employee(
        self, client_a, tenant_a, employee_a, employee_b, admin_user, sep_in_clearance_a
    ):
        """If the linked asset belongs to a different employee, it must NOT be returned."""
        from apps.hrm.models import ClearanceItem, AssetAllocation
        # Create an issued asset for employee_b (the wrong employee)
        other_asset = AssetAllocation.objects.create(
            tenant=tenant_a,
            employee=employee_b,
            asset_name="Wrong Laptop",
            asset_category="laptop",
            status="issued",
            issued_at=timezone.now(),
            issued_by=admin_user,
        )
        it_line = ClearanceItem.objects.filter(
            tenant=tenant_a, case=sep_in_clearance_a, department="it"
        ).first()
        assert it_line is not None
        it_line.asset_allocation = other_asset
        it_line.save(update_fields=["asset_allocation", "updated_at"])
        client_a.post(reverse("hrm:clearanceitem_mark_cleared", args=[it_line.pk]))
        other_asset.refresh_from_db()
        # Must NOT have been returned (different employee guard)
        assert other_asset.status == "issued"

    def test_mark_na_changes_status(self, client_a, clearance_item_a):
        resp = client_a.post(reverse("hrm:clearanceitem_mark_na", args=[clearance_item_a.pk]))
        assert resp.status_code == 302
        clearance_item_a.refresh_from_db()
        assert clearance_item_a.status == "not_applicable"

    def test_reject_changes_status(self, client_a, clearance_item_a):
        resp = client_a.post(reverse("hrm:clearanceitem_reject", args=[clearance_item_a.pk]))
        assert resp.status_code == 302
        clearance_item_a.refresh_from_db()
        assert clearance_item_a.status == "rejected"

    def test_reject_cleared_item_is_noop(self, client_a, clearance_item_a):
        """Cannot reject an already-cleared item."""
        clearance_item_a.status = "cleared"
        clearance_item_a.save(update_fields=["status", "updated_at"])
        client_a.post(reverse("hrm:clearanceitem_reject", args=[clearance_item_a.pk]))
        clearance_item_a.refresh_from_db()
        assert clearance_item_a.status == "cleared"

    def test_reject_not_applicable_item_is_noop(self, client_a, clearance_item_a):
        """Cannot reject a not_applicable item."""
        clearance_item_a.status = "not_applicable"
        clearance_item_a.save(update_fields=["status", "updated_at"])
        client_a.post(reverse("hrm:clearanceitem_reject", args=[clearance_item_a.pk]))
        clearance_item_a.refresh_from_db()
        assert clearance_item_a.status == "not_applicable"

    def test_delete_pending_removes_row(self, client_a, tenant_a, sep_in_clearance_a):
        from apps.hrm.models import ClearanceItem
        item = ClearanceItem.objects.create(
            tenant=tenant_a,
            case=sep_in_clearance_a,
            department="admin",
            description="Return ID card",
            is_mandatory=False,
        )
        pk = item.pk
        resp = client_a.post(reverse("hrm:clearanceitem_delete", args=[pk]))
        assert resp.status_code == 302
        assert not ClearanceItem.objects.filter(pk=pk).exists()

    def test_delete_cleared_blocked(self, client_a, clearance_item_a):
        from apps.hrm.models import ClearanceItem
        clearance_item_a.status = "cleared"
        clearance_item_a.save(update_fields=["status", "updated_at"])
        resp = client_a.post(reverse("hrm:clearanceitem_delete", args=[clearance_item_a.pk]))
        assert resp.status_code == 302
        assert ClearanceItem.objects.filter(pk=clearance_item_a.pk).exists()


class TestFinalSettlementViews:
    """CRUD + compute/hr_approve/finance_approve/mark_paid workflow."""

    def test_list_200(self, client_a, settlement_draft_a):
        resp = client_a.get(reverse("hrm:finalsettlement_list"))
        assert resp.status_code == 200

    def test_list_excludes_other_tenant(self, client_a, settlement_draft_a, settlement_b):
        resp = client_a.get(reverse("hrm:finalsettlement_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert settlement_b.pk not in pks

    def test_detail_200(self, client_a, settlement_draft_a):
        resp = client_a.get(reverse("hrm:finalsettlement_detail", args=[settlement_draft_a.pk]))
        assert resp.status_code == 200

    def test_compute_changes_status(self, client_a, settlement_draft_a):
        resp = client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        assert resp.status_code == 302
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.status == "computed"

    def test_hr_approve_blocked_on_draft(self, client_a, settlement_draft_a):
        """HR approve must be blocked on a draft (uncomputed) settlement."""
        resp = client_a.post(reverse("hrm:finalsettlement_hr_approve", args=[settlement_draft_a.pk]))
        assert resp.status_code == 302
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.status == "draft"

    def test_hr_approve_after_compute(self, client_a, settlement_draft_a):
        client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        resp = client_a.post(reverse("hrm:finalsettlement_hr_approve", args=[settlement_draft_a.pk]))
        assert resp.status_code == 302
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.status == "hr_approved"

    def test_hr_approve_stamps_approver(self, client_a, settlement_draft_a, admin_user):
        client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        client_a.post(reverse("hrm:finalsettlement_hr_approve", args=[settlement_draft_a.pk]))
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.hr_approved_by_id == admin_user.pk
        assert settlement_draft_a.hr_approved_at is not None

    def test_finance_approve_after_hr_approve(self, client_a, settlement_draft_a):
        client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        client_a.post(reverse("hrm:finalsettlement_hr_approve", args=[settlement_draft_a.pk]))
        resp = client_a.post(
            reverse("hrm:finalsettlement_finance_approve", args=[settlement_draft_a.pk])
        )
        assert resp.status_code == 302
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.status == "finance_approved"

    def test_finance_approve_blocked_on_draft(self, client_a, settlement_draft_a):
        resp = client_a.post(
            reverse("hrm:finalsettlement_finance_approve", args=[settlement_draft_a.pk])
        )
        assert resp.status_code == 302
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.status == "draft"

    def test_mark_paid_after_hr_approve(self, client_a, settlement_draft_a):
        client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        client_a.post(reverse("hrm:finalsettlement_hr_approve", args=[settlement_draft_a.pk]))
        resp = client_a.post(reverse("hrm:finalsettlement_mark_paid", args=[settlement_draft_a.pk]))
        assert resp.status_code == 302
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.status == "paid"
        assert settlement_draft_a.paid_at is not None

    def test_mark_paid_advances_case_to_settled(self, client_a, settlement_draft_a, sep_cleared_a):
        client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        client_a.post(reverse("hrm:finalsettlement_hr_approve", args=[settlement_draft_a.pk]))
        client_a.post(reverse("hrm:finalsettlement_mark_paid", args=[settlement_draft_a.pk]))
        sep_cleared_a.refresh_from_db()
        assert sep_cleared_a.status == "settled"

    def test_delete_draft_removes_row(self, client_a, tenant_a, sep_cleared_a):
        from apps.hrm.models import FinalSettlement
        fnf = FinalSettlement.objects.create(tenant=tenant_a, case=sep_cleared_a)
        pk = fnf.pk
        resp = client_a.post(reverse("hrm:finalsettlement_delete", args=[pk]))
        assert resp.status_code == 302
        assert not FinalSettlement.objects.filter(pk=pk).exists()

    def test_delete_non_draft_blocked(self, client_a, settlement_draft_a):
        from apps.hrm.models import FinalSettlement
        # advance to computed
        client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        resp = client_a.post(reverse("hrm:finalsettlement_delete", args=[settlement_draft_a.pk]))
        assert resp.status_code == 302
        assert FinalSettlement.objects.filter(pk=settlement_draft_a.pk).exists()

    def test_edit_blocked_after_hr_approve(self, client_a, settlement_draft_a):
        client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        client_a.post(reverse("hrm:finalsettlement_hr_approve", args=[settlement_draft_a.pk]))
        resp = client_a.get(reverse("hrm:finalsettlement_edit", args=[settlement_draft_a.pk]))
        # Should redirect to detail (not 200 form page)
        assert resp.status_code == 302


# ============================================================
# Multi-Tenant Isolation (IDOR)
# ============================================================

class TestOffboardingIDOR:
    """Cross-tenant IDOR: any object belonging to tenant_b → 404 for tenant_a client."""

    def test_separation_case_detail_idor(self, client_a, sep_b):
        resp = client_a.get(reverse("hrm:separationcase_detail", args=[sep_b.pk]))
        assert resp.status_code == 404

    def test_separation_case_edit_idor(self, client_a, sep_b):
        resp = client_a.get(reverse("hrm:separationcase_edit", args=[sep_b.pk]))
        assert resp.status_code == 404

    def test_separation_case_delete_idor(self, client_a, sep_b):
        resp = client_a.post(reverse("hrm:separationcase_delete", args=[sep_b.pk]))
        assert resp.status_code == 404

    def test_separation_case_submit_idor(self, client_a, sep_b):
        resp = client_a.post(reverse("hrm:separationcase_submit", args=[sep_b.pk]))
        assert resp.status_code == 404

    def test_separation_case_approve_idor(self, client_a, sep_b):
        resp = client_a.post(reverse("hrm:separationcase_approve", args=[sep_b.pk]))
        assert resp.status_code == 404

    def test_exit_interview_detail_idor(self, client_a, exit_interview_b):
        resp = client_a.get(reverse("hrm:exitinterview_detail", args=[exit_interview_b.pk]))
        assert resp.status_code == 404

    def test_exit_interview_complete_idor(self, client_a, exit_interview_b):
        resp = client_a.post(reverse("hrm:exitinterview_complete", args=[exit_interview_b.pk]))
        assert resp.status_code == 404

    def test_clearance_item_detail_idor(self, client_a, clearance_item_b):
        resp = client_a.get(reverse("hrm:clearanceitem_detail", args=[clearance_item_b.pk]))
        assert resp.status_code == 404

    def test_clearance_item_mark_cleared_idor(self, client_a, clearance_item_b):
        resp = client_a.post(reverse("hrm:clearanceitem_mark_cleared", args=[clearance_item_b.pk]))
        assert resp.status_code == 404

    def test_clearance_item_mark_na_idor(self, client_a, clearance_item_b):
        resp = client_a.post(reverse("hrm:clearanceitem_mark_na", args=[clearance_item_b.pk]))
        assert resp.status_code == 404

    def test_settlement_detail_idor(self, client_a, settlement_b):
        resp = client_a.get(reverse("hrm:finalsettlement_detail", args=[settlement_b.pk]))
        assert resp.status_code == 404

    def test_settlement_compute_idor(self, client_a, settlement_b):
        resp = client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_b.pk]))
        assert resp.status_code == 404

    def test_settlement_hr_approve_idor(self, client_a, settlement_b):
        resp = client_a.post(reverse("hrm:finalsettlement_hr_approve", args=[settlement_b.pk]))
        assert resp.status_code == 404


# ============================================================
# Permission / @tenant_admin_required Tests
# ============================================================

class TestOffboardingAdminPermissions:
    """@tenant_admin_required actions must return 403 or redirect for a non-admin member."""

    def test_approve_blocked_for_member(self, member_client, sep_pending_a):
        resp = member_client.post(reverse("hrm:separationcase_approve", args=[sep_pending_a.pk]))
        assert resp.status_code in (302, 403)
        sep_pending_a.refresh_from_db()
        assert sep_pending_a.status == "pending_approval"

    def test_reject_blocked_for_member(self, member_client, sep_pending_a):
        resp = member_client.post(reverse("hrm:separationcase_reject", args=[sep_pending_a.pk]))
        assert resp.status_code in (302, 403)
        sep_pending_a.refresh_from_db()
        assert sep_pending_a.status == "pending_approval"

    def test_mark_cleared_blocked_for_member(self, member_client, sep_in_clearance_a):
        resp = member_client.post(
            reverse("hrm:separationcase_mark_cleared", args=[sep_in_clearance_a.pk])
        )
        assert resp.status_code in (302, 403)

    def test_complete_blocked_for_member(self, member_client, sep_cleared_a):
        resp = member_client.post(
            reverse("hrm:separationcase_complete", args=[sep_cleared_a.pk])
        )
        assert resp.status_code in (302, 403)
        sep_cleared_a.refresh_from_db()
        assert sep_cleared_a.status == "cleared"

    def test_exitinterview_complete_blocked_for_member(self, member_client, exit_interview_a):
        resp = member_client.post(
            reverse("hrm:exitinterview_complete", args=[exit_interview_a.pk])
        )
        assert resp.status_code in (302, 403)
        exit_interview_a.refresh_from_db()
        assert exit_interview_a.status == "scheduled"

    def test_exitinterview_skip_blocked_for_member(self, member_client, exit_interview_a):
        resp = member_client.post(
            reverse("hrm:exitinterview_skip", args=[exit_interview_a.pk])
        )
        assert resp.status_code in (302, 403)
        exit_interview_a.refresh_from_db()
        assert exit_interview_a.status == "scheduled"

    def test_clearanceitem_mark_cleared_blocked_for_member(self, member_client, clearance_item_a):
        resp = member_client.post(
            reverse("hrm:clearanceitem_mark_cleared", args=[clearance_item_a.pk])
        )
        assert resp.status_code in (302, 403)
        clearance_item_a.refresh_from_db()
        assert clearance_item_a.status == "pending"

    def test_clearanceitem_mark_na_blocked_for_member(self, member_client, clearance_item_a):
        resp = member_client.post(
            reverse("hrm:clearanceitem_mark_na", args=[clearance_item_a.pk])
        )
        assert resp.status_code in (302, 403)
        clearance_item_a.refresh_from_db()
        assert clearance_item_a.status == "pending"

    def test_clearanceitem_reject_blocked_for_member(self, member_client, clearance_item_a):
        resp = member_client.post(
            reverse("hrm:clearanceitem_reject", args=[clearance_item_a.pk])
        )
        assert resp.status_code in (302, 403)
        clearance_item_a.refresh_from_db()
        assert clearance_item_a.status == "pending"

    def test_finalsettlement_compute_blocked_for_member(self, member_client, settlement_draft_a):
        resp = member_client.post(
            reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk])
        )
        assert resp.status_code in (302, 403)
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.status == "draft"

    def test_finalsettlement_hr_approve_blocked_for_member(
        self, client_a, member_client, settlement_draft_a
    ):
        # First compute via admin
        client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        resp = member_client.post(
            reverse("hrm:finalsettlement_hr_approve", args=[settlement_draft_a.pk])
        )
        assert resp.status_code in (302, 403)
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.status == "computed"

    def test_finalsettlement_finance_approve_blocked_for_member(
        self, client_a, member_client, settlement_draft_a
    ):
        client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        client_a.post(reverse("hrm:finalsettlement_hr_approve", args=[settlement_draft_a.pk]))
        resp = member_client.post(
            reverse("hrm:finalsettlement_finance_approve", args=[settlement_draft_a.pk])
        )
        assert resp.status_code in (302, 403)
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.status == "hr_approved"

    def test_finalsettlement_mark_paid_blocked_for_member(
        self, client_a, member_client, settlement_draft_a
    ):
        client_a.post(reverse("hrm:finalsettlement_compute", args=[settlement_draft_a.pk]))
        client_a.post(reverse("hrm:finalsettlement_hr_approve", args=[settlement_draft_a.pk]))
        resp = member_client.post(
            reverse("hrm:finalsettlement_mark_paid", args=[settlement_draft_a.pk])
        )
        assert resp.status_code in (302, 403)
        settlement_draft_a.refresh_from_db()
        assert settlement_draft_a.status == "hr_approved"


# ============================================================
# Form Security Tests
# ============================================================

class TestSeparationCaseFormSecurity:
    """Workflow / auto-computed fields must not appear in SeparationCaseForm."""

    def test_status_not_a_form_field(self):
        from apps.hrm.forms import SeparationCaseForm
        assert "status" not in SeparationCaseForm().fields

    def test_submitted_at_not_a_form_field(self):
        from apps.hrm.forms import SeparationCaseForm
        assert "submitted_at" not in SeparationCaseForm().fields

    def test_approver_not_a_form_field(self):
        from apps.hrm.forms import SeparationCaseForm
        assert "approver" not in SeparationCaseForm().fields

    def test_approved_at_not_a_form_field(self):
        from apps.hrm.forms import SeparationCaseForm
        assert "approved_at" not in SeparationCaseForm().fields

    def test_expected_lwd_not_a_form_field(self):
        from apps.hrm.forms import SeparationCaseForm
        assert "expected_last_working_day" not in SeparationCaseForm().fields

    def test_relieving_letter_generated_at_not_a_form_field(self):
        from apps.hrm.forms import SeparationCaseForm
        assert "relieving_letter_generated_at" not in SeparationCaseForm().fields

    def test_experience_letter_generated_at_not_a_form_field(self):
        from apps.hrm.forms import SeparationCaseForm
        assert "experience_letter_generated_at" not in SeparationCaseForm().fields

    def test_crafted_post_cannot_set_status(self, client_a, tenant_a, employee_a):
        """A POST with status='approved' must result in a draft case (status cannot be injected)."""
        from apps.hrm.models import SeparationCase
        client_a.post(reverse("hrm:separationcase_create"), {
            "employee": employee_a.pk,
            "separation_type": "resignation",
            "exit_reason": "better_opportunity",
            "notice_period_days": 30,
            "notice_start_date": "2026-07-01",
            "notice_buyout_type": "none",
            "requires_kt": "",
            "notes": "",
            "status": "in_clearance",  # injection attempt
        })
        case = SeparationCase.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert case is not None
        assert case.status == "draft"


class TestExitInterviewFormSecurity:
    """status and conducted_at must not appear in ExitInterviewForm."""

    def test_status_not_a_form_field(self):
        from apps.hrm.forms import ExitInterviewForm
        assert "status" not in ExitInterviewForm().fields

    def test_conducted_at_not_a_form_field(self):
        from apps.hrm.forms import ExitInterviewForm
        assert "conducted_at" not in ExitInterviewForm().fields


class TestClearanceItemFormSecurity:
    """status, cleared_by, cleared_at must not appear in ClearanceItemForm."""

    def test_status_not_a_form_field(self):
        from apps.hrm.forms import ClearanceItemForm
        assert "status" not in ClearanceItemForm().fields

    def test_cleared_by_not_a_form_field(self):
        from apps.hrm.forms import ClearanceItemForm
        assert "cleared_by" not in ClearanceItemForm().fields

    def test_cleared_at_not_a_form_field(self):
        from apps.hrm.forms import ClearanceItemForm
        assert "cleared_at" not in ClearanceItemForm().fields


class TestFinalSettlementFormSecurity:
    """status, hr/finance approval stamps, paid_at, gl_posted must not be in FinalSettlementForm."""

    def test_status_not_a_form_field(self):
        from apps.hrm.forms import FinalSettlementForm
        assert "status" not in FinalSettlementForm().fields

    def test_hr_approved_by_not_a_form_field(self):
        from apps.hrm.forms import FinalSettlementForm
        assert "hr_approved_by" not in FinalSettlementForm().fields

    def test_hr_approved_at_not_a_form_field(self):
        from apps.hrm.forms import FinalSettlementForm
        assert "hr_approved_at" not in FinalSettlementForm().fields

    def test_finance_approved_by_not_a_form_field(self):
        from apps.hrm.forms import FinalSettlementForm
        assert "finance_approved_by" not in FinalSettlementForm().fields

    def test_finance_approved_at_not_a_form_field(self):
        from apps.hrm.forms import FinalSettlementForm
        assert "finance_approved_at" not in FinalSettlementForm().fields

    def test_paid_at_not_a_form_field(self):
        from apps.hrm.forms import FinalSettlementForm
        assert "paid_at" not in FinalSettlementForm().fields

    def test_gl_posted_not_a_form_field(self):
        from apps.hrm.forms import FinalSettlementForm
        assert "gl_posted" not in FinalSettlementForm().fields

    def test_duplicate_case_rejected_by_form(self, tenant_a, sep_cleared_a, settlement_draft_a):
        """A second FinalSettlement for the same case must fail form validation."""
        from apps.hrm.forms import FinalSettlementForm
        form = FinalSettlementForm(
            data={"case": sep_cleared_a.pk, "settlement_date": "", "notes": "",
                  "prorata_salary": "0", "leave_encashment_days": "0",
                  "leave_encashment_amount": "0", "gratuity_eligible": "",
                  "gratuity_amount": "0", "bonus_amount": "0", "reimbursement_amount": "0",
                  "other_income": "0", "notice_recovery_amount": "0", "loan_recovery": "0",
                  "asset_deduction": "0", "advance_recovery": "0", "tax_deduction": "0",
                  "professional_tax": "0", "other_deduction": "0"},
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "case" in form.errors
