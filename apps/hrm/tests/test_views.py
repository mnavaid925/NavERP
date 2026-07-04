"""Tests for HRM views: CRUD, list/filter, detail, delete guards, leave workflow."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ HRM Overview
class TestHRMOverview:
    def test_overview_200(self, client_a):
        resp = client_a.get(reverse("hrm:hrm_overview"))
        assert resp.status_code == 200

    def test_overview_has_stats_context(self, client_a):
        resp = client_a.get(reverse("hrm:hrm_overview"))
        assert "stats" in resp.context
        stats = resp.context["stats"]
        for key in ("employees", "new_this_month", "on_leave_today", "present_today", "absent_today"):
            assert key in stats

    def test_overview_has_pending_requests(self, client_a):
        resp = client_a.get(reverse("hrm:hrm_overview"))
        assert "pending_requests" in resp.context

    def test_overview_has_upcoming_holidays(self, client_a):
        resp = client_a.get(reverse("hrm:hrm_overview"))
        assert "upcoming_holidays" in resp.context

    def test_overview_anon_redirect(self, client):
        resp = client.get(reverse("hrm:hrm_overview"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_overview_counts_employees(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:hrm_overview"))
        assert resp.context["stats"]["employees"] >= 1


# ================================================================ Designations
class TestDesignationListView:
    def test_list_200(self, client_a, designation_a):
        resp = client_a.get(reverse("hrm:designation_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, designation_a):
        resp = client_a.get(reverse("hrm:designation_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert designation_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, designation_a, designation_b):
        resp = client_a.get(reverse("hrm:designation_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert designation_b.pk not in pks

    def test_search_filter(self, client_a, designation_a, tenant_a):
        from apps.hrm.models import Designation
        Designation.objects.create(tenant=tenant_a, name="Marketing Director", grade="M2")
        resp = client_a.get(reverse("hrm:designation_list") + "?q=Software")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert designation_a.pk in pks


class TestDesignationCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:designation_create"))
        assert resp.status_code == 200

    def test_post_creates_with_tenant(self, client_a, tenant_a, dept_a):
        from apps.hrm.models import Designation
        resp = client_a.post(reverse("hrm:designation_create"), {
            "name": "Product Manager",
            "grade": "M1",
            "is_active": "on",
            "department": dept_a.pk,
            "min_salary": "80000",
            "max_salary": "120000",
        })
        assert resp.status_code == 302
        assert Designation.objects.filter(tenant=tenant_a, name="Product Manager").exists()

    def test_anon_redirect(self, client):
        resp = client.get(reverse("hrm:designation_create"))
        assert resp.status_code == 302


class TestDesignationDetailView:
    def test_detail_200(self, client_a, designation_a):
        resp = client_a.get(reverse("hrm:designation_detail", args=[designation_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj_context(self, client_a, designation_a):
        resp = client_a.get(reverse("hrm:designation_detail", args=[designation_a.pk]))
        assert resp.context["obj"].pk == designation_a.pk


class TestDesignationEditView:
    def test_get_200(self, client_a, designation_a):
        resp = client_a.get(reverse("hrm:designation_edit", args=[designation_a.pk]))
        assert resp.status_code == 200

    def test_post_updates(self, client_a, designation_a):
        resp = client_a.post(reverse("hrm:designation_edit", args=[designation_a.pk]), {
            "name": "Senior Software Engineer",
            "grade": "L3",
            "is_active": "on",
            "min_salary": "90000",
            "max_salary": "130000",
        })
        assert resp.status_code == 302
        designation_a.refresh_from_db()
        assert designation_a.name == "Senior Software Engineer"


class TestDesignationDeleteView:
    def test_post_deletes(self, client_a, designation_a):
        from apps.hrm.models import Designation
        pk = designation_a.pk
        # No employees linked — safe to delete
        resp = client_a.post(reverse("hrm:designation_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Designation.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, designation_a):
        resp = client_a.get(reverse("hrm:designation_delete", args=[designation_a.pk]))
        assert resp.status_code == 405

    def test_cannot_delete_in_use_designation(self, client_a, designation_a, employee_a):
        """Designation used by employees must NOT be deletable."""
        from apps.hrm.models import Designation
        pk = designation_a.pk
        resp = client_a.post(reverse("hrm:designation_delete", args=[pk]))
        # Should redirect (not delete) because the designation is in use
        assert resp.status_code == 302
        assert Designation.objects.filter(pk=pk).exists()


# ================================================================ Employees
class TestEmployeeListView:
    def test_list_200(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert employee_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, employee_a, employee_b):
        resp = client_a.get(reverse("hrm:employee_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert employee_b.pk not in pks

    def test_search_filter(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_list") + "?q=Alice")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert employee_a.pk in pks

    def test_context_has_employee_type_choices(self, client_a):
        resp = client_a.get(reverse("hrm:employee_list"))
        assert "employee_type_choices" in resp.context

    def test_context_has_status_choices(self, client_a):
        resp = client_a.get(reverse("hrm:employee_list"))
        assert "status_choices" in resp.context


class TestEmployeeCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:employee_create"))
        assert resp.status_code == 200

    def test_post_creates_employee(self, client_a, tenant_a, person_a2):
        from apps.hrm.models import EmployeeProfile
        resp = client_a.post(reverse("hrm:employee_create"), {
            "party": person_a2.pk,
            "employee_type": "full_time",
            "gender": "female",
        })
        assert resp.status_code == 302
        assert EmployeeProfile.objects.filter(tenant=tenant_a, party=person_a2).exists()

    def test_created_employee_has_auto_number(self, client_a, tenant_a, person_a2):
        from apps.hrm.models import EmployeeProfile
        client_a.post(reverse("hrm:employee_create"), {
            "party": person_a2.pk,
            "employee_type": "full_time",
        })
        emp = EmployeeProfile.objects.filter(tenant=tenant_a, party=person_a2).first()
        assert emp is not None
        assert emp.number.startswith("EMP-")


class TestEmployeeDetailView:
    def test_detail_200(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj_context(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_a.pk]))
        assert resp.context["obj"].pk == employee_a.pk

    def test_detail_has_balances(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_a.pk]))
        assert "balances" in resp.context

    def test_detail_has_recent_attendance(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_a.pk]))
        assert "recent_attendance" in resp.context

    def test_detail_has_recent_leaves(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_a.pk]))
        assert "recent_leaves" in resp.context


class TestEmployeeEditView:
    def test_get_200(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_edit", args=[employee_a.pk]))
        assert resp.status_code == 200

    def test_post_updates(self, client_a, employee_a):
        resp = client_a.post(reverse("hrm:employee_edit", args=[employee_a.pk]), {
            "party": employee_a.party_id,
            "employee_type": "part_time",
            "gender": "female",
        })
        assert resp.status_code == 302
        employee_a.refresh_from_db()
        assert employee_a.employee_type == "part_time"


class TestEmployeeDeleteView:
    def test_post_deletes_inactive_employee(self, client_a, tenant_a, person_a2):
        """Can delete an employee with no active employment."""
        from apps.hrm.models import EmployeeProfile
        emp = EmployeeProfile.objects.create(
            tenant=tenant_a, party=person_a2, employee_type="full_time"
        )
        pk = emp.pk
        resp = client_a.post(reverse("hrm:employee_delete", args=[pk]))
        assert resp.status_code == 302
        assert not EmployeeProfile.objects.filter(pk=pk).exists()

    def test_cannot_delete_active_employee(self, client_a, employee_a):
        """Active employment guard: employee with active employment must not be deleted."""
        from apps.hrm.models import EmployeeProfile
        pk = employee_a.pk
        resp = client_a.post(reverse("hrm:employee_delete", args=[pk]))
        # Should redirect back — not delete
        assert resp.status_code == 302
        assert EmployeeProfile.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, employee_a):
        resp = client_a.get(reverse("hrm:employee_delete", args=[employee_a.pk]))
        assert resp.status_code == 405


# ================================================================ Leave Types
class TestLeaveTypeListView:
    def test_list_200(self, client_a, leave_type_a):
        resp = client_a.get(reverse("hrm:leavetype_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, leave_type_a):
        resp = client_a.get(reverse("hrm:leavetype_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert leave_type_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, leave_type_a, leave_type_b):
        resp = client_a.get(reverse("hrm:leavetype_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert leave_type_b.pk not in pks


class TestLeaveTypeCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:leavetype_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.hrm.models import LeaveType
        resp = client_a.post(reverse("hrm:leavetype_create"), {
            "name": "Paternity Leave",
            "code": "PL",
            "is_paid": "on",
            "accrual_rule": "none",
            "accrual_days": "0",
            "max_balance": "0",
            "max_carry_forward": "0",
            "is_active": "on",
        })
        assert resp.status_code == 302
        assert LeaveType.objects.filter(tenant=tenant_a, code="PL").exists()


class TestLeaveTypeDetailView:
    def test_detail_200(self, client_a, leave_type_a):
        resp = client_a.get(reverse("hrm:leavetype_detail", args=[leave_type_a.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj(self, client_a, leave_type_a):
        resp = client_a.get(reverse("hrm:leavetype_detail", args=[leave_type_a.pk]))
        assert resp.context["obj"].pk == leave_type_a.pk


class TestLeaveTypeDeleteView:
    def test_post_deletes_unused(self, client_a, tenant_a):
        from apps.hrm.models import LeaveType
        lt = LeaveType.objects.create(
            tenant=tenant_a, name="Unused LT", code="ULT",
            accrual_rule="none", accrual_days=Decimal("0")
        )
        pk = lt.pk
        resp = client_a.post(reverse("hrm:leavetype_delete", args=[pk]))
        assert resp.status_code == 302
        assert not LeaveType.objects.filter(pk=pk).exists()

    def test_cannot_delete_in_use_leave_type(self, client_a, leave_type_a, leave_allocation_a):
        """A leave type with allocations must not be deletable."""
        from apps.hrm.models import LeaveType
        pk = leave_type_a.pk
        resp = client_a.post(reverse("hrm:leavetype_delete", args=[pk]))
        assert resp.status_code == 302
        assert LeaveType.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, leave_type_a):
        resp = client_a.get(reverse("hrm:leavetype_delete", args=[leave_type_a.pk]))
        assert resp.status_code == 405


# ================================================================ Leave Allocations
class TestLeaveAllocationListView:
    def test_list_200(self, client_a, leave_allocation_a):
        resp = client_a.get(reverse("hrm:leaveallocation_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, leave_allocation_a):
        resp = client_a.get(reverse("hrm:leaveallocation_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert leave_allocation_a.pk in pks

    def test_list_has_used_days_db_annotation(self, client_a, leave_allocation_a):
        resp = client_a.get(reverse("hrm:leaveallocation_list"))
        obj_list = resp.context["object_list"]
        # All returned objects should have used_days_db annotation
        for obj in obj_list:
            assert hasattr(obj, "used_days_db")


class TestLeaveAllocationCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:leaveallocation_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveAllocation
        resp = client_a.post(reverse("hrm:leaveallocation_create"), {
            "employee": employee_a.pk,
            "leave_type": leave_type_a.pk,
            "year": 2025,
            "allocated_days": "15.00",
            "status": "active",
        })
        assert resp.status_code == 302
        assert LeaveAllocation.objects.filter(
            tenant=tenant_a, employee=employee_a, year=2025
        ).exists()


class TestLeaveAllocationDetailView:
    def test_detail_200(self, client_a, leave_allocation_a):
        resp = client_a.get(reverse("hrm:leaveallocation_detail", args=[leave_allocation_a.pk]))
        assert resp.status_code == 200


class TestLeaveAllocationEditView:
    def test_get_200(self, client_a, leave_allocation_a):
        resp = client_a.get(reverse("hrm:leaveallocation_edit", args=[leave_allocation_a.pk]))
        assert resp.status_code == 200

    def test_post_updates(self, client_a, leave_allocation_a):
        resp = client_a.post(reverse("hrm:leaveallocation_edit", args=[leave_allocation_a.pk]), {
            "employee": leave_allocation_a.employee_id,
            "leave_type": leave_allocation_a.leave_type_id,
            "year": 2026,
            "allocated_days": "25.00",
            "status": "active",
        })
        assert resp.status_code == 302
        leave_allocation_a.refresh_from_db()
        assert leave_allocation_a.allocated_days == Decimal("25.00")


class TestLeaveAllocationDeleteView:
    def test_post_deletes(self, client_a, leave_allocation_a):
        from apps.hrm.models import LeaveAllocation
        pk = leave_allocation_a.pk
        resp = client_a.post(reverse("hrm:leaveallocation_delete", args=[pk]))
        assert resp.status_code == 302
        assert not LeaveAllocation.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, leave_allocation_a):
        resp = client_a.get(reverse("hrm:leaveallocation_delete", args=[leave_allocation_a.pk]))
        assert resp.status_code == 405


# ================================================================ Leave Requests
class TestLeaveRequestListView:
    def test_list_200(self, client_a, draft_leave_request):
        resp = client_a.get(reverse("hrm:leaverequest_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, draft_leave_request):
        resp = client_a.get(reverse("hrm:leaverequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_leave_request.pk in pks

    def test_list_excludes_other_tenant(self, client_a, draft_leave_request, leave_request_b):
        resp = client_a.get(reverse("hrm:leaverequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert leave_request_b.pk not in pks

    def test_status_filter(self, client_a, draft_leave_request, pending_leave_request):
        resp = client_a.get(reverse("hrm:leaverequest_list") + "?status=draft")
        statuses = [obj.status for obj in resp.context["object_list"]]
        assert all(s == "draft" for s in statuses)

    def test_context_has_status_choices(self, client_a):
        resp = client_a.get(reverse("hrm:leaverequest_list"))
        assert "status_choices" in resp.context


class TestLeaveRequestCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:leaverequest_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveRequest
        resp = client_a.post(reverse("hrm:leaverequest_create"), {
            "employee": employee_a.pk,
            "leave_type": leave_type_a.pk,
            "start_date": "2026-10-01",
            "end_date": "2026-10-03",
            "reason": "Vacation trip",
        })
        assert resp.status_code == 302
        assert LeaveRequest.objects.filter(
            tenant=tenant_a, employee=employee_a,
            start_date=datetime.date(2026, 10, 1)
        ).exists()

    def test_new_request_starts_as_draft(self, client_a, tenant_a, employee_a, leave_type_a):
        from apps.hrm.models import LeaveRequest
        client_a.post(reverse("hrm:leaverequest_create"), {
            "employee": employee_a.pk,
            "leave_type": leave_type_a.pk,
            "start_date": "2026-10-01",
            "end_date": "2026-10-03",
            "reason": "Test",
        })
        lr = LeaveRequest.objects.filter(
            tenant=tenant_a, employee=employee_a,
            start_date=datetime.date(2026, 10, 1)
        ).first()
        assert lr is not None
        assert lr.status == "draft"
        assert lr.approver is None


class TestLeaveRequestDetailView:
    def test_detail_200(self, client_a, draft_leave_request):
        resp = client_a.get(reverse("hrm:leaverequest_detail", args=[draft_leave_request.pk]))
        assert resp.status_code == 200

    def test_detail_has_obj(self, client_a, draft_leave_request):
        resp = client_a.get(reverse("hrm:leaverequest_detail", args=[draft_leave_request.pk]))
        assert resp.context["obj"].pk == draft_leave_request.pk


class TestLeaveRequestDeleteView:
    def test_post_deletes_draft(self, client_a, draft_leave_request):
        from apps.hrm.models import LeaveRequest
        pk = draft_leave_request.pk
        resp = client_a.post(reverse("hrm:leaverequest_delete", args=[pk]))
        assert resp.status_code == 302
        assert not LeaveRequest.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, draft_leave_request):
        resp = client_a.get(reverse("hrm:leaverequest_delete", args=[draft_leave_request.pk]))
        assert resp.status_code == 405


# ================================================================ Leave Workflow
class TestLeaveWorkflow:
    def test_submit_transitions_draft_to_pending(self, client_a, draft_leave_request):
        resp = client_a.post(
            reverse("hrm:leaverequest_submit", args=[draft_leave_request.pk])
        )
        assert resp.status_code == 302
        draft_leave_request.refresh_from_db()
        assert draft_leave_request.status == "pending"

    def test_submit_requires_post(self, client_a, draft_leave_request):
        # submit is @require_POST
        resp = client_a.get(
            reverse("hrm:leaverequest_submit", args=[draft_leave_request.pk])
        )
        assert resp.status_code == 405

    def test_approve_transitions_pending_to_approved(self, client_a, admin_user, pending_leave_request):
        resp = client_a.post(
            reverse("hrm:leaverequest_approve", args=[pending_leave_request.pk])
        )
        assert resp.status_code == 302
        pending_leave_request.refresh_from_db()
        assert pending_leave_request.status == "approved"
        assert pending_leave_request.approver == admin_user
        assert pending_leave_request.approved_at is not None

    def test_approve_sets_attendance_to_on_leave(self, client_a, tenant_a, employee_a, pending_leave_request, shift_a):
        from apps.hrm.models import AttendanceRecord
        # Create an attendance record within the leave window
        att = AttendanceRecord.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            date=pending_leave_request.start_date,
            check_in=datetime.time(9, 0),
            check_out=datetime.time(18, 0),
            shift=shift_a,
            status="present",
            source="web",
        )
        client_a.post(reverse("hrm:leaverequest_approve", args=[pending_leave_request.pk]))
        att.refresh_from_db()
        assert att.status == "on_leave"

    def test_reject_transitions_pending_to_rejected(self, client_a, pending_leave_request):
        resp = client_a.post(
            reverse("hrm:leaverequest_reject", args=[pending_leave_request.pk]),
            {"rejected_reason": "Understaffed"}
        )
        assert resp.status_code == 302
        pending_leave_request.refresh_from_db()
        assert pending_leave_request.status == "rejected"
        assert pending_leave_request.rejected_reason == "Understaffed"

    def test_reject_saves_approver(self, client_a, admin_user, pending_leave_request):
        client_a.post(
            reverse("hrm:leaverequest_reject", args=[pending_leave_request.pk]),
            {"rejected_reason": "No quota"}
        )
        pending_leave_request.refresh_from_db()
        assert pending_leave_request.approver == admin_user

    def test_cancel_approved_reverts_attendance(self, client_a, tenant_a, employee_a, pending_leave_request, shift_a):
        from apps.hrm.models import AttendanceRecord
        # Approve first
        att = AttendanceRecord.objects.create(
            tenant=tenant_a,
            employee=employee_a,
            date=pending_leave_request.start_date,
            check_in=datetime.time(9, 0),
            check_out=datetime.time(18, 0),
            shift=shift_a,
            status="present",
            source="web",
        )
        client_a.post(reverse("hrm:leaverequest_approve", args=[pending_leave_request.pk]))
        att.refresh_from_db()
        assert att.status == "on_leave"  # sanity check

        # Now cancel
        client_a.post(
            reverse("hrm:leaverequest_cancel", args=[pending_leave_request.pk]),
            {"cancelled_reason": "Changed plans"}
        )
        pending_leave_request.refresh_from_db()
        assert pending_leave_request.status == "cancelled"
        att.refresh_from_db()
        assert att.status == "present"  # reverted

    def test_cancel_draft_request(self, client_a, draft_leave_request):
        resp = client_a.post(
            reverse("hrm:leaverequest_cancel", args=[draft_leave_request.pk]),
            {"cancelled_reason": "No longer needed"}
        )
        assert resp.status_code == 302
        draft_leave_request.refresh_from_db()
        assert draft_leave_request.status == "cancelled"


# ================================================================ Shifts
class TestShiftListView:
    def test_list_200(self, client_a, shift_a):
        resp = client_a.get(reverse("hrm:shift_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, shift_a):
        resp = client_a.get(reverse("hrm:shift_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert shift_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, shift_a, shift_b):
        resp = client_a.get(reverse("hrm:shift_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert shift_b.pk not in pks


class TestShiftCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:shift_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.hrm.models import Shift
        resp = client_a.post(reverse("hrm:shift_create"), {
            "name": "Evening Shift",
            "start_time": "14:00",
            "end_time": "22:00",
            "grace_minutes": 10,
            "is_default": "",
            "is_active": "on",
        })
        assert resp.status_code == 302
        assert Shift.objects.filter(tenant=tenant_a, name="Evening Shift").exists()


class TestShiftDetailView:
    def test_detail_200(self, client_a, shift_a):
        resp = client_a.get(reverse("hrm:shift_detail", args=[shift_a.pk]))
        assert resp.status_code == 200


class TestShiftDeleteView:
    def test_post_deletes_unassigned_shift(self, client_a, tenant_a):
        from apps.hrm.models import Shift
        s = Shift.objects.create(
            tenant=tenant_a, name="Temp Shift",
            start_time=datetime.time(10, 0), end_time=datetime.time(19, 0)
        )
        pk = s.pk
        resp = client_a.post(reverse("hrm:shift_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Shift.objects.filter(pk=pk).exists()

    def test_cannot_delete_assigned_shift(self, client_a, shift_a, employee_a):
        from apps.hrm.models import Shift, ShiftAssignment
        ShiftAssignment.objects.create(
            tenant=shift_a.tenant,
            employee=employee_a,
            shift=shift_a,
            effective_from=datetime.date(2026, 1, 1),
        )
        pk = shift_a.pk
        resp = client_a.post(reverse("hrm:shift_delete", args=[pk]))
        assert resp.status_code == 302
        assert Shift.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, shift_a):
        resp = client_a.get(reverse("hrm:shift_delete", args=[shift_a.pk]))
        assert resp.status_code == 405


# ================================================================ Shift Assignments
class TestShiftAssignmentListView:
    def test_list_200(self, client_a, employee_a, shift_a):
        from apps.hrm.models import ShiftAssignment
        ShiftAssignment.objects.create(
            tenant=shift_a.tenant, employee=employee_a, shift=shift_a,
            effective_from=datetime.date(2026, 1, 1)
        )
        resp = client_a.get(reverse("hrm:shiftassignment_list"))
        assert resp.status_code == 200


class TestShiftAssignmentCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:shiftassignment_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a, employee_a, shift_a):
        from apps.hrm.models import ShiftAssignment
        resp = client_a.post(reverse("hrm:shiftassignment_create"), {
            "employee": employee_a.pk,
            "shift": shift_a.pk,
            "effective_from": "2026-02-01",
            "effective_to": "",
        })
        assert resp.status_code == 302
        assert ShiftAssignment.objects.filter(
            tenant=tenant_a, employee=employee_a, shift=shift_a,
            effective_from=datetime.date(2026, 2, 1)
        ).exists()


# ================================================================ Attendance Records
class TestAttendanceListView:
    def test_list_200(self, client_a, attendance_a):
        resp = client_a.get(reverse("hrm:attendancerecord_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, attendance_a):
        resp = client_a.get(reverse("hrm:attendancerecord_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert attendance_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, attendance_a, attendance_b):
        resp = client_a.get(reverse("hrm:attendancerecord_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert attendance_b.pk not in pks

    def test_status_filter(self, client_a, attendance_a, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRecord
        AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a,
            date=datetime.date(2026, 6, 17),
            status="absent", source="web",
        )
        resp = client_a.get(reverse("hrm:attendancerecord_list") + "?status=present")
        statuses = [obj.status for obj in resp.context["object_list"]]
        assert all(s == "present" for s in statuses)

    def test_context_has_status_choices(self, client_a):
        resp = client_a.get(reverse("hrm:attendancerecord_list"))
        assert "status_choices" in resp.context


class TestAttendanceCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:attendancerecord_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a, employee_a, shift_a):
        from apps.hrm.models import AttendanceRecord
        resp = client_a.post(reverse("hrm:attendancerecord_create"), {
            "employee": employee_a.pk,
            "date": "2026-07-10",
            "check_in": "09:00",
            "check_out": "18:00",
            "shift": shift_a.pk,
            "status": "present",
            "source": "web",
        })
        assert resp.status_code == 302
        assert AttendanceRecord.objects.filter(
            tenant=tenant_a, employee=employee_a,
            date=datetime.date(2026, 7, 10)
        ).exists()


class TestAttendanceDetailView:
    def test_detail_200(self, client_a, attendance_a):
        resp = client_a.get(reverse("hrm:attendancerecord_detail", args=[attendance_a.pk]))
        assert resp.status_code == 200


class TestAttendanceDeleteView:
    def test_post_deletes(self, client_a, attendance_a):
        from apps.hrm.models import AttendanceRecord
        pk = attendance_a.pk
        resp = client_a.post(reverse("hrm:attendancerecord_delete", args=[pk]))
        assert resp.status_code == 302
        assert not AttendanceRecord.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, attendance_a):
        resp = client_a.get(reverse("hrm:attendancerecord_delete", args=[attendance_a.pk]))
        assert resp.status_code == 405


# ================================================================ Public Holidays
class TestPublicHolidayListView:
    def test_list_200(self, client_a, holiday_a):
        resp = client_a.get(reverse("hrm:publicholiday_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, holiday_a):
        resp = client_a.get(reverse("hrm:publicholiday_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert holiday_a.pk in pks


class TestPublicHolidayCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:publicholiday_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.hrm.models import PublicHoliday
        resp = client_a.post(reverse("hrm:publicholiday_create"), {
            "date": "2026-12-25",
            "name": "Christmas Day",
            "is_optional": "",
            "category": "national",
        })
        assert resp.status_code == 302
        assert PublicHoliday.objects.filter(tenant=tenant_a, name="Christmas Day").exists()


class TestPublicHolidayDeleteView:
    def test_post_deletes(self, client_a, holiday_a):
        from apps.hrm.models import PublicHoliday
        pk = holiday_a.pk
        resp = client_a.post(reverse("hrm:publicholiday_delete", args=[pk]))
        assert resp.status_code == 302
        assert not PublicHoliday.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, holiday_a):
        resp = client_a.get(reverse("hrm:publicholiday_delete", args=[holiday_a.pk]))
        assert resp.status_code == 405


class TestPublicHolidayDetailAndEdit:
    def test_detail_200(self, client_a, holiday_a):
        resp = client_a.get(reverse("hrm:publicholiday_detail", args=[holiday_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200(self, client_a, holiday_a):
        resp = client_a.get(reverse("hrm:publicholiday_edit", args=[holiday_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, holiday_a):
        resp = client_a.post(reverse("hrm:publicholiday_edit", args=[holiday_a.pk]), {
            "date": "2026-07-04",
            "name": "Independence Day",
            "is_optional": "",
            "category": "national",
        })
        assert resp.status_code == 302
        holiday_a.refresh_from_db()
        assert holiday_a.name == "Independence Day"

    def test_year_filter(self, client_a, holiday_a):
        """year GET param filters holidays by year."""
        resp = client_a.get(reverse("hrm:publicholiday_list") + "?year=2026")
        assert resp.status_code == 200
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert holiday_a.pk in pks


# ================================================================ Shift Assignments (extra coverage)
class TestShiftAssignmentDetailAndEdit:
    def test_detail_200(self, client_a, employee_a, shift_a):
        from apps.hrm.models import ShiftAssignment
        sa = ShiftAssignment.objects.create(
            tenant=shift_a.tenant, employee=employee_a, shift=shift_a,
            effective_from=datetime.date(2026, 3, 1),
        )
        resp = client_a.get(reverse("hrm:shiftassignment_detail", args=[sa.pk]))
        assert resp.status_code == 200
        assert resp.context["obj"].pk == sa.pk

    def test_edit_get_200(self, client_a, employee_a, shift_a):
        from apps.hrm.models import ShiftAssignment
        sa = ShiftAssignment.objects.create(
            tenant=shift_a.tenant, employee=employee_a, shift=shift_a,
            effective_from=datetime.date(2026, 3, 2),
        )
        resp = client_a.get(reverse("hrm:shiftassignment_edit", args=[sa.pk]))
        assert resp.status_code == 200

    def test_delete_removes_assignment(self, client_a, employee_a, shift_a):
        from apps.hrm.models import ShiftAssignment
        sa = ShiftAssignment.objects.create(
            tenant=shift_a.tenant, employee=employee_a, shift=shift_a,
            effective_from=datetime.date(2026, 3, 3),
        )
        pk = sa.pk
        resp = client_a.post(reverse("hrm:shiftassignment_delete", args=[pk]))
        assert resp.status_code == 302
        assert not ShiftAssignment.objects.filter(pk=pk).exists()


# ================================================================ LeaveRequest edit locked guard
class TestLeaveRequestEditLocked:
    def test_edit_open_request_get_200(self, client_a, draft_leave_request):
        """A draft leave request should render the edit form."""
        resp = client_a.get(reverse("hrm:leaverequest_edit", args=[draft_leave_request.pk]))
        assert resp.status_code == 200

    def test_edit_open_request_post_updates(self, client_a, draft_leave_request):
        """A draft leave request edit POST should update the record."""
        resp = client_a.post(reverse("hrm:leaverequest_edit", args=[draft_leave_request.pk]), {
            "employee": draft_leave_request.employee_id,
            "leave_type": draft_leave_request.leave_type_id,
            "start_date": "2026-07-07",
            "end_date": "2026-07-09",
            "reason": "Updated reason",
        })
        assert resp.status_code == 302
        draft_leave_request.refresh_from_db()
        assert draft_leave_request.reason == "Updated reason"

    def test_edit_approved_redirects_with_error(self, client_a, tenant_a, employee_a, leave_type_a, admin_user):
        """An approved leave request must redirect (not render the form) when edit is attempted."""
        from apps.hrm.models import LeaveRequest
        from django.utils import timezone
        lr = LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 9, 10), end_date=datetime.date(2026, 9, 12),
            status="approved", approver=admin_user, approved_at=timezone.now(),
        )
        resp = client_a.get(reverse("hrm:leaverequest_edit", args=[lr.pk]))
        # Should redirect to detail page (not render the edit form)
        assert resp.status_code == 302

    def test_edit_rejected_redirects_with_error(self, client_a, tenant_a, employee_a, leave_type_a, admin_user):
        """A rejected leave request must also redirect when edit is attempted."""
        from apps.hrm.models import LeaveRequest
        lr = LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 9, 15), end_date=datetime.date(2026, 9, 16),
            status="rejected", approver=admin_user,
        )
        resp = client_a.get(reverse("hrm:leaverequest_edit", args=[lr.pk]))
        assert resp.status_code == 302


# ================================================================ LeaveRequest delete guard (approved/rejected)
class TestLeaveRequestDeleteGuard:
    def test_cannot_delete_approved_request(self, client_a, tenant_a, employee_a, leave_type_a, admin_user):
        """An approved request cannot be deleted — must cancel instead."""
        from apps.hrm.models import LeaveRequest
        from django.utils import timezone
        lr = LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 10, 10), end_date=datetime.date(2026, 10, 12),
            status="approved", approver=admin_user, approved_at=timezone.now(),
        )
        pk = lr.pk
        resp = client_a.post(reverse("hrm:leaverequest_delete", args=[pk]))
        assert resp.status_code == 302
        assert LeaveRequest.objects.filter(pk=pk).exists()

    def test_cannot_delete_rejected_request(self, client_a, tenant_a, employee_a, leave_type_a, admin_user):
        """A rejected request cannot be deleted."""
        from apps.hrm.models import LeaveRequest
        lr = LeaveRequest.objects.create(
            tenant=tenant_a, employee=employee_a, leave_type=leave_type_a,
            start_date=datetime.date(2026, 10, 15), end_date=datetime.date(2026, 10, 16),
            status="rejected", approver=admin_user,
        )
        pk = lr.pk
        resp = client_a.post(reverse("hrm:leaverequest_delete", args=[pk]))
        assert resp.status_code == 302
        assert LeaveRequest.objects.filter(pk=pk).exists()


# ================================================================ Leave Type edit
class TestLeaveTypeEditView:
    def test_post_updates(self, client_a, leave_type_a):
        resp = client_a.post(reverse("hrm:leavetype_edit", args=[leave_type_a.pk]), {
            "name": "Annual Leave Updated",
            "code": "ALU",
            "is_paid": "on",
            "accrual_rule": "annual",
            "accrual_days": "21",
            "max_balance": "30",
            "max_carry_forward": "5",
            "is_active": "on",
        })
        assert resp.status_code == 302
        leave_type_a.refresh_from_db()
        assert leave_type_a.name == "Annual Leave Updated"


# ================================================================ Attendance date-range filter
class TestAttendanceDateRangeFilter:
    def test_date_from_filter(self, client_a, attendance_a, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRecord
        # attendance_a is on 2026-06-16; create one earlier
        AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a,
            date=datetime.date(2026, 6, 10),
            status="present", source="web",
        )
        resp = client_a.get(reverse("hrm:attendancerecord_list") + "?date_from=2026-06-15")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert attendance_a.pk in pks

    def test_date_to_filter(self, client_a, attendance_a, tenant_a, employee_a):
        from apps.hrm.models import AttendanceRecord
        # attendance_a is on 2026-06-16; filter up to 2026-06-15 → should exclude it
        AttendanceRecord.objects.create(
            tenant=tenant_a, employee=employee_a,
            date=datetime.date(2026, 6, 14),
            status="present", source="web",
        )
        resp = client_a.get(reverse("hrm:attendancerecord_list") + "?date_to=2026-06-15")
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert attendance_a.pk not in pks


# ================================================================ Holiday Policies (3.12)
class TestHolidayPolicyListView:
    def test_list_200(self, client_a, default_holiday_policy_a):
        resp = client_a.get(reverse("hrm:holidaypolicy_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, default_holiday_policy_a):
        resp = client_a.get(reverse("hrm:holidaypolicy_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert default_holiday_policy_a.pk in pks


class TestHolidayPolicyCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:holidaypolicy_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.hrm.models import HolidayPolicy
        resp = client_a.post(reverse("hrm:holidaypolicy_create"), {
            "name": "Remote Staff Policy",
            "location": "",
            "org_unit": "",
            "employee_type": "",
            "designation": "",
            "is_default": "",
            "floating_holiday_quota": "2",
            "holidays": [],
            "is_active": "on",
            "description": "",
        })
        assert resp.status_code == 302
        assert HolidayPolicy.objects.filter(tenant=tenant_a, name="Remote Staff Policy").exists()


class TestHolidayPolicyDetailAndEdit:
    def test_detail_200(self, client_a, default_holiday_policy_a):
        resp = client_a.get(reverse("hrm:holidaypolicy_detail", args=[default_holiday_policy_a.pk]))
        assert resp.status_code == 200

    def test_detail_context(self, client_a, default_holiday_policy_a):
        resp = client_a.get(reverse("hrm:holidaypolicy_detail", args=[default_holiday_policy_a.pk]))
        assert "obj" in resp.context
        assert "policy_holidays" in resp.context
        assert "recent_elections" in resp.context

    def test_edit_get_200(self, client_a, default_holiday_policy_a):
        resp = client_a.get(reverse("hrm:holidaypolicy_edit", args=[default_holiday_policy_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, default_holiday_policy_a):
        resp = client_a.post(
            reverse("hrm:holidaypolicy_edit", args=[default_holiday_policy_a.pk]), {
                "name": "Company Default Updated",
                "location": "",
                "org_unit": "",
                "employee_type": "",
                "designation": "",
                "is_default": "on",
                "floating_holiday_quota": "3",
                "holidays": [],
                "is_active": "on",
                "description": "",
            })
        assert resp.status_code == 302
        default_holiday_policy_a.refresh_from_db()
        assert default_holiday_policy_a.name == "Company Default Updated"
        assert default_holiday_policy_a.floating_holiday_quota == 3


class TestHolidayPolicyDeleteView:
    def test_post_deletes(self, client_a, default_holiday_policy_a):
        from apps.hrm.models import HolidayPolicy
        pk = default_holiday_policy_a.pk
        resp = client_a.post(reverse("hrm:holidaypolicy_delete", args=[pk]))
        assert resp.status_code == 302
        assert not HolidayPolicy.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, default_holiday_policy_a):
        resp = client_a.get(reverse("hrm:holidaypolicy_delete", args=[default_holiday_policy_a.pk]))
        assert resp.status_code == 405


# ================================================================ Floating Holiday Elections (3.12)
class TestFloatingHolidayElectionListView:
    def test_list_200(self, client_a, pending_election_a):
        resp = client_a.get(reverse("hrm:floatingholidayelection_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, pending_election_a):
        resp = client_a.get(reverse("hrm:floatingholidayelection_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pending_election_a.pk in pks

    def test_list_has_status_choices(self, client_a, pending_election_a):
        resp = client_a.get(reverse("hrm:floatingholidayelection_list"))
        assert "status_choices" in resp.context


class TestFloatingHolidayElectionCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:floatingholidayelection_create"))
        assert resp.status_code == 200

    def test_post_creates_and_auto_resolves_policy(
        self, client_a, tenant_a, employee_a, optional_holiday_a, default_holiday_policy_a
    ):
        from apps.hrm.models import FloatingHolidayElection
        resp = client_a.post(reverse("hrm:floatingholidayelection_create"), {
            "employee": employee_a.pk,
            "holiday": optional_holiday_a.pk,
            "policy": "",
            "note": "",
        })
        assert resp.status_code == 302
        election = FloatingHolidayElection.objects.filter(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a
        ).first()
        assert election is not None
        assert election.status == "pending"
        assert election.policy_id == default_holiday_policy_a.pk

    def test_post_non_optional_holiday_rejected(self, client_a, employee_a, holiday_a):
        """Electing a non-optional holiday must fail form validation (clean() ValidationError),
        re-rendering the form rather than redirecting."""
        from apps.hrm.models import FloatingHolidayElection
        resp = client_a.post(reverse("hrm:floatingholidayelection_create"), {
            "employee": employee_a.pk,
            "holiday": holiday_a.pk,
            "policy": "",
            "note": "",
        })
        # holiday_a isn't in the form's optional-only queryset, so this is an invalid-choice form error.
        assert resp.status_code == 200
        assert not FloatingHolidayElection.objects.filter(employee=employee_a, holiday=holiday_a).exists()

    def test_post_exceeding_quota_rejected(
        self, client_a, tenant_a, employee_a, optional_holiday_a, optional_holiday_a2,
        default_holiday_policy_a
    ):
        from apps.hrm.models import FloatingHolidayElection
        FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a, status="pending",
        )
        resp = client_a.post(reverse("hrm:floatingholidayelection_create"), {
            "employee": employee_a.pk,
            "holiday": optional_holiday_a2.pk,
            "policy": "",
            "note": "",
        })
        assert resp.status_code == 200  # form re-rendered with the quota ValidationError
        form = resp.context.get("form")
        assert form is not None and not form.is_valid()
        assert not FloatingHolidayElection.objects.filter(
            employee=employee_a, holiday=optional_holiday_a2
        ).exists()


class TestFloatingHolidayElectionDetailAndEdit:
    def test_detail_200(self, client_a, pending_election_a):
        resp = client_a.get(reverse("hrm:floatingholidayelection_detail", args=[pending_election_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200_when_pending(self, client_a, pending_election_a):
        resp = client_a.get(reverse("hrm:floatingholidayelection_edit", args=[pending_election_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_when_pending(self, client_a, pending_election_a, employee_a, optional_holiday_a):
        resp = client_a.post(
            reverse("hrm:floatingholidayelection_edit", args=[pending_election_a.pk]), {
                "employee": employee_a.pk,
                "holiday": optional_holiday_a.pk,
                "policy": "",
                "note": "Updated note",
            })
        assert resp.status_code == 302
        pending_election_a.refresh_from_db()
        assert pending_election_a.note == "Updated note"

    def test_edit_blocked_when_approved(
        self, client_a, tenant_a, employee_a, optional_holiday_a, default_holiday_policy_a
    ):
        """A decided (approved) election is locked — edit redirects to detail, row unchanged."""
        from apps.hrm.models import FloatingHolidayElection
        election = FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a, status="approved",
        )
        resp = client_a.post(
            reverse("hrm:floatingholidayelection_edit", args=[election.pk]), {
                "employee": employee_a.pk,
                "holiday": optional_holiday_a.pk,
                "policy": "",
                "note": "Sneaky edit",
            })
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:floatingholidayelection_detail", args=[election.pk])
        election.refresh_from_db()
        assert election.note != "Sneaky edit"


class TestFloatingHolidayElectionDeleteView:
    def test_post_deletes_when_pending(self, client_a, pending_election_a):
        from apps.hrm.models import FloatingHolidayElection
        pk = pending_election_a.pk
        resp = client_a.post(reverse("hrm:floatingholidayelection_delete", args=[pk]))
        assert resp.status_code == 302
        assert not FloatingHolidayElection.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, pending_election_a):
        resp = client_a.get(reverse("hrm:floatingholidayelection_delete", args=[pending_election_a.pk]))
        assert resp.status_code == 405

    def test_delete_blocked_when_approved(
        self, client_a, tenant_a, employee_a, optional_holiday_a
    ):
        """A decided (approved) election cannot be deleted via direct POST."""
        from apps.hrm.models import FloatingHolidayElection
        election = FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a, status="approved",
        )
        resp = client_a.post(reverse("hrm:floatingholidayelection_delete", args=[election.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:floatingholidayelection_detail", args=[election.pk])
        assert FloatingHolidayElection.objects.filter(pk=election.pk).exists()


class TestFloatingHolidayElectionApproveReject:
    def test_approve_sets_status_and_approver(self, client_a, admin_user, pending_election_a):
        resp = client_a.post(
            reverse("hrm:floatingholidayelection_approve", args=[pending_election_a.pk])
        )
        assert resp.status_code == 302
        pending_election_a.refresh_from_db()
        assert pending_election_a.status == "approved"
        assert pending_election_a.approved_by_id == admin_user.pk
        assert pending_election_a.approved_at is not None

    def test_reject_sets_status_and_note(self, client_a, admin_user, pending_election_a):
        resp = client_a.post(
            reverse("hrm:floatingholidayelection_reject", args=[pending_election_a.pk]),
            {"note": "Insufficient coverage"},
        )
        assert resp.status_code == 302
        pending_election_a.refresh_from_db()
        assert pending_election_a.status == "rejected"
        assert pending_election_a.approved_by_id == admin_user.pk
        assert pending_election_a.note == "Insufficient coverage"

    def test_approve_get_not_allowed(self, client_a, pending_election_a):
        resp = client_a.get(reverse("hrm:floatingholidayelection_approve", args=[pending_election_a.pk]))
        assert resp.status_code == 405

    def test_reject_get_not_allowed(self, client_a, pending_election_a):
        resp = client_a.get(reverse("hrm:floatingholidayelection_reject", args=[pending_election_a.pk]))
        assert resp.status_code == 405

    def test_approve_already_decided_is_noop(self, client_a, tenant_a, employee_a, optional_holiday_a):
        """Approving an already-rejected election must not flip it back to approved (only acts on pending)."""
        from apps.hrm.models import FloatingHolidayElection
        election = FloatingHolidayElection.objects.create(
            tenant=tenant_a, employee=employee_a, holiday=optional_holiday_a, status="rejected",
        )
        resp = client_a.post(reverse("hrm:floatingholidayelection_approve", args=[election.pk]))
        assert resp.status_code == 302
        election.refresh_from_db()
        assert election.status == "rejected"


class TestFloatingHolidayElectionPermissions:
    def test_non_admin_cannot_approve(self, member_client, pending_election_a):
        resp = member_client.post(
            reverse("hrm:floatingholidayelection_approve", args=[pending_election_a.pk])
        )
        assert resp.status_code == 403
        pending_election_a.refresh_from_db()
        assert pending_election_a.status == "pending"

    def test_non_admin_cannot_reject(self, member_client, pending_election_a):
        resp = member_client.post(
            reverse("hrm:floatingholidayelection_reject", args=[pending_election_a.pk]),
            {"note": "Attempt"},
        )
        assert resp.status_code == 403
        pending_election_a.refresh_from_db()
        assert pending_election_a.status == "pending"


class TestHolidayPolicyQueryCount:
    def test_detail_bounded_queries(self, client_a, default_holiday_policy_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:holidaypolicy_detail", args=[default_holiday_policy_a.pk]))


class TestFloatingHolidayElectionQueryCount:
    def test_list_bounded_queries(self, client_a, pending_election_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:floatingholidayelection_list"))


# ================================================================ Pay Components (3.13)
class TestPayComponentListView:
    def test_list_200(self, client_a, pay_component_a):
        resp = client_a.get(reverse("hrm:paycomponent_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, pay_component_a):
        resp = client_a.get(reverse("hrm:paycomponent_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pay_component_a.pk in pks


class TestPayComponentCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:paycomponent_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.hrm.models import PayComponent
        resp = client_a.post(reverse("hrm:paycomponent_create"), {
            "name": "House Rent Allowance",
            "code": "HRA",
            "component_type": "earning",
            "variable_subtype": "",
            "calculation_type": "pct_of_basic",
            "default_amount": "",
            "default_percentage": "40",
            "frequency": "monthly",
            "is_taxable": "on",
            "include_in_ctc": "on",
            "contribution_side": "employee",
            "annual_cap_amount": "",
            "requires_bill": "",
            "is_active": "on",
            "display_order": "0",
            "description": "",
        })
        assert resp.status_code == 302
        pc = PayComponent.objects.filter(tenant=tenant_a, name="House Rent Allowance").first()
        assert pc is not None
        assert pc.calculation_type == "pct_of_basic"


class TestPayComponentDetailAndEdit:
    def test_detail_200(self, client_a, pay_component_a):
        resp = client_a.get(reverse("hrm:paycomponent_detail", args=[pay_component_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200(self, client_a, pay_component_a):
        resp = client_a.get(reverse("hrm:paycomponent_edit", args=[pay_component_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, pay_component_a):
        resp = client_a.post(
            reverse("hrm:paycomponent_edit", args=[pay_component_a.pk]), {
                "name": "Basic Pay Updated",
                "code": "",
                "component_type": "earning",
                "variable_subtype": "",
                "calculation_type": "fixed_amount",
                "default_amount": "60000",
                "default_percentage": "",
                "frequency": "monthly",
                "is_taxable": "on",
                "include_in_ctc": "on",
                "contribution_side": "employee",
                "annual_cap_amount": "",
                "requires_bill": "",
                "is_active": "on",
                "display_order": "0",
                "description": "",
            })
        assert resp.status_code == 302
        pay_component_a.refresh_from_db()
        assert pay_component_a.name == "Basic Pay Updated"
        assert pay_component_a.default_amount == Decimal("60000")


class TestPayComponentDeleteView:
    def test_post_deletes(self, client_a, pay_component_a):
        from apps.hrm.models import PayComponent
        pk = pay_component_a.pk
        resp = client_a.post(reverse("hrm:paycomponent_delete", args=[pk]))
        assert resp.status_code == 302
        assert not PayComponent.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, pay_component_a):
        resp = client_a.get(reverse("hrm:paycomponent_delete", args=[pay_component_a.pk]))
        assert resp.status_code == 405

    def test_inuse_component_cannot_be_deleted(self, client_a, pay_component_a, salary_line_a):
        """A PayComponent referenced by a SalaryStructureLine (PROTECT FK) must not be deletable —
        the friendly-message guard, not a raw ProtectedError 500."""
        from apps.hrm.models import PayComponent
        pk = pay_component_a.pk
        resp = client_a.post(reverse("hrm:paycomponent_delete", args=[pk]))
        assert resp.status_code == 302
        assert PayComponent.objects.filter(pk=pk).exists()


# ================================================================ Salary Structure Templates (3.13)
class TestSalaryStructureTemplateListView:
    def test_list_200(self, client_a, salary_template_a):
        resp = client_a.get(reverse("hrm:salarystructuretemplate_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, salary_template_a):
        resp = client_a.get(reverse("hrm:salarystructuretemplate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert salary_template_a.pk in pks


class TestSalaryStructureTemplateCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:salarystructuretemplate_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.hrm.models import SalaryStructureTemplate
        resp = client_a.post(reverse("hrm:salarystructuretemplate_create"), {
            "name": "Sales L1",
            "job_grade": "",
            "annual_ctc_amount": "75000",
            "currency": "USD",
            "is_active": "on",
            "description": "",
        })
        assert resp.status_code == 302
        tmpl = SalaryStructureTemplate.objects.filter(tenant=tenant_a, name="Sales L1").first()
        assert tmpl is not None
        assert tmpl.number.startswith("SST-")


class TestSalaryStructureTemplateDetailAndEdit:
    def test_detail_200(self, client_a, salary_template_a):
        resp = client_a.get(reverse("hrm:salarystructuretemplate_detail", args=[salary_template_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, salary_template_a):
        resp = client_a.get(reverse("hrm:salarystructuretemplate_detail", args=[salary_template_a.pk]))
        assert "obj" in resp.context
        assert "lines" in resp.context
        assert "ctc_total" in resp.context
        assert "line_form" in resp.context

    def test_detail_renders_derived_ctc_total(self, client_a, salary_template_a, salary_line_a):
        """salary_line_a is a fixed 55000 amount line -> ctc_total must equal that resolved sum."""
        resp = client_a.get(reverse("hrm:salarystructuretemplate_detail", args=[salary_template_a.pk]))
        assert resp.context["ctc_total"] == Decimal("55000")

    def test_edit_get_200(self, client_a, salary_template_a):
        resp = client_a.get(reverse("hrm:salarystructuretemplate_edit", args=[salary_template_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, salary_template_a):
        resp = client_a.post(
            reverse("hrm:salarystructuretemplate_edit", args=[salary_template_a.pk]), {
                "name": "Engineering L2 Updated",
                "job_grade": "",
                "annual_ctc_amount": "130000",
                "currency": "USD",
                "is_active": "on",
                "description": "",
            })
        assert resp.status_code == 302
        salary_template_a.refresh_from_db()
        assert salary_template_a.name == "Engineering L2 Updated"
        assert salary_template_a.annual_ctc_amount == Decimal("130000")


class TestSalaryStructureTemplateDeleteView:
    def test_post_deletes(self, client_a, salary_template_a):
        from apps.hrm.models import SalaryStructureTemplate
        pk = salary_template_a.pk
        resp = client_a.post(reverse("hrm:salarystructuretemplate_delete", args=[pk]))
        assert resp.status_code == 302
        assert not SalaryStructureTemplate.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, salary_template_a):
        resp = client_a.get(reverse("hrm:salarystructuretemplate_delete", args=[salary_template_a.pk]))
        assert resp.status_code == 405


# ------------------------------------------------------ Inline Salary Structure Lines (3.13)
class TestSalaryStructureLineAddView:
    def test_valid_post_creates_line(self, client_a, tenant_a, salary_template_a, pay_component_a):
        from apps.hrm.models import SalaryStructureLine
        resp = client_a.post(
            reverse("hrm:salarystructureline_add", args=[salary_template_a.pk]), {
                "pay_component": pay_component_a.pk,
                "calculation_type": "",
                "amount": "60000",
                "percentage": "",
                "sequence": "1",
            })
        assert resp.status_code == 302
        line = SalaryStructureLine.objects.filter(
            tenant=tenant_a, template=salary_template_a, pay_component=pay_component_a).first()
        assert line is not None
        assert line.amount == Decimal("60000")

    def test_duplicate_pay_component_rerenders_with_form_error_no_new_row(
        self, client_a, tenant_a, salary_template_a, pay_component_a, salary_line_a
    ):
        """salary_line_a already references pay_component_a on this template — a 2nd POST with the
        same component must re-render 200 with a pay_component form error, no new row, no
        IntegrityError 500 (the duplicate-line bug fix, locked in)."""
        from apps.hrm.models import SalaryStructureLine
        resp = client_a.post(
            reverse("hrm:salarystructureline_add", args=[salary_template_a.pk]), {
                "pay_component": pay_component_a.pk,
                "calculation_type": "",
                "amount": "99999",
                "percentage": "",
                "sequence": "2",
            })
        assert resp.status_code == 200
        form = resp.context.get("line_form")
        assert form is not None and not form.is_valid()
        assert "pay_component" in form.errors
        assert SalaryStructureLine.objects.filter(
            tenant=tenant_a, template=salary_template_a, pay_component=pay_component_a).count() == 1

    def test_get_not_allowed(self, client_a, salary_template_a):
        resp = client_a.get(reverse("hrm:salarystructureline_add", args=[salary_template_a.pk]))
        assert resp.status_code == 405


class TestSalaryStructureLineEditView:
    def test_get_200(self, client_a, salary_line_a):
        resp = client_a.get(reverse("hrm:salarystructureline_edit", args=[salary_line_a.pk]))
        assert resp.status_code == 200

    def test_post_updates(self, client_a, salary_line_a, pay_component_a):
        resp = client_a.post(
            reverse("hrm:salarystructureline_edit", args=[salary_line_a.pk]), {
                "pay_component": pay_component_a.pk,
                "calculation_type": "",
                "amount": "70000",
                "percentage": "",
                "sequence": "3",
            })
        assert resp.status_code == 302
        salary_line_a.refresh_from_db()
        assert salary_line_a.amount == Decimal("70000")
        assert salary_line_a.sequence == 3


class TestSalaryStructureLineDeleteView:
    def test_post_deletes_and_updates_ctc_total(self, client_a, salary_template_a, salary_line_a):
        from apps.hrm.models import SalaryStructureLine
        pk = salary_line_a.pk
        resp = client_a.post(reverse("hrm:salarystructureline_delete", args=[pk]))
        assert resp.status_code == 302
        assert not SalaryStructureLine.objects.filter(pk=pk).exists()
        salary_template_a.refresh_from_db()
        assert salary_template_a.computed_ctc_total == Decimal("0")

    def test_get_not_allowed(self, client_a, salary_line_a):
        resp = client_a.get(reverse("hrm:salarystructureline_delete", args=[salary_line_a.pk]))
        assert resp.status_code == 405


# ================================================================ Employee Salary Structures (3.13)
class TestEmployeeSalaryStructureListView:
    def test_list_200(self, client_a, active_salary_structure_a):
        resp = client_a.get(reverse("hrm:employeesalarystructure_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, active_salary_structure_a):
        resp = client_a.get(reverse("hrm:employeesalarystructure_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert active_salary_structure_a.pk in pks


class TestEmployeeSalaryStructureCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:employeesalarystructure_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a, employee_a, salary_template_a):
        from apps.hrm.models import EmployeeSalaryStructure
        resp = client_a.post(reverse("hrm:employeesalarystructure_create"), {
            "employee": employee_a.pk,
            "template": salary_template_a.pk,
            "annual_ctc_amount": "125000",
            "effective_from": "2026-07-01",
            "effective_to": "",
            "status": "active",
            "notes": "",
        })
        assert resp.status_code == 302
        ess = EmployeeSalaryStructure.objects.filter(tenant=tenant_a, employee=employee_a).first()
        assert ess is not None
        assert ess.number.startswith("ESS-")

    def test_post_second_active_rerenders_with_clean_error_no_row(
        self, client_a, tenant_a, employee_a, active_salary_structure_a
    ):
        from apps.hrm.models import EmployeeSalaryStructure
        resp = client_a.post(reverse("hrm:employeesalarystructure_create"), {
            "employee": employee_a.pk,
            "template": "",
            "annual_ctc_amount": "99000",
            "effective_from": "2026-07-01",
            "effective_to": "",
            "status": "active",
            "notes": "",
        })
        assert resp.status_code == 200
        form = resp.context.get("form")
        assert form is not None and not form.is_valid()
        assert EmployeeSalaryStructure.objects.filter(
            tenant=tenant_a, employee=employee_a, annual_ctc_amount=Decimal("99000")).count() == 0


class TestEmployeeSalaryStructureDetailAndEdit:
    def test_detail_200(self, client_a, active_salary_structure_a):
        resp = client_a.get(reverse("hrm:employeesalarystructure_detail", args=[active_salary_structure_a.pk]))
        assert resp.status_code == 200

    def test_edit_get_200(self, client_a, active_salary_structure_a):
        resp = client_a.get(reverse("hrm:employeesalarystructure_edit", args=[active_salary_structure_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates(self, client_a, active_salary_structure_a, employee_a):
        resp = client_a.post(
            reverse("hrm:employeesalarystructure_edit", args=[active_salary_structure_a.pk]), {
                "employee": employee_a.pk,
                "template": "",
                "annual_ctc_amount": "150000",
                "effective_from": "2026-07-01",
                "effective_to": "",
                "status": "active",
                "notes": "Raise",
            })
        assert resp.status_code == 302
        active_salary_structure_a.refresh_from_db()
        assert active_salary_structure_a.annual_ctc_amount == Decimal("150000")
        assert active_salary_structure_a.notes == "Raise"

    def test_edit_blocked_when_superseded(self, client_a, superseded_salary_structure_a, employee_a):
        """A superseded assignment is read-only history — GET and POST both redirect to detail,
        row unchanged."""
        resp_get = client_a.get(
            reverse("hrm:employeesalarystructure_edit", args=[superseded_salary_structure_a.pk]))
        assert resp_get.status_code == 302
        assert resp_get.url == reverse(
            "hrm:employeesalarystructure_detail", args=[superseded_salary_structure_a.pk])

        resp_post = client_a.post(
            reverse("hrm:employeesalarystructure_edit", args=[superseded_salary_structure_a.pk]), {
                "employee": employee_a.pk,
                "template": "",
                "annual_ctc_amount": "999999",
                "effective_from": "2026-07-01",
                "effective_to": "",
                "status": "active",
                "notes": "Sneaky edit",
            })
        assert resp_post.status_code == 302
        assert resp_post.url == reverse(
            "hrm:employeesalarystructure_detail", args=[superseded_salary_structure_a.pk])
        superseded_salary_structure_a.refresh_from_db()
        assert superseded_salary_structure_a.annual_ctc_amount == Decimal("100000")
        assert superseded_salary_structure_a.notes != "Sneaky edit"


class TestEmployeeSalaryStructureDeleteView:
    def test_post_deletes(self, client_a, active_salary_structure_a):
        from apps.hrm.models import EmployeeSalaryStructure
        pk = active_salary_structure_a.pk
        resp = client_a.post(reverse("hrm:employeesalarystructure_delete", args=[pk]))
        assert resp.status_code == 302
        assert not EmployeeSalaryStructure.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, active_salary_structure_a):
        resp = client_a.get(reverse("hrm:employeesalarystructure_delete", args=[active_salary_structure_a.pk]))
        assert resp.status_code == 405

    def test_delete_blocked_when_superseded(self, client_a, superseded_salary_structure_a):
        from apps.hrm.models import EmployeeSalaryStructure
        pk = superseded_salary_structure_a.pk
        resp = client_a.post(reverse("hrm:employeesalarystructure_delete", args=[pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:employeesalarystructure_detail", args=[pk])
        assert EmployeeSalaryStructure.objects.filter(pk=pk).exists()


class TestSalaryStructureTemplateQueryCount:
    def test_detail_bounded_queries(self, client_a, salary_template_a, salary_line_a, django_assert_max_num_queries):
        # Session/tenant-middleware overhead adds a few queries on top of the view's own handful
        # (template fetch, lines fetch, line_form's tenant-scoped pay_component queryset, etc.) — this
        # ceiling still catches an N+1 regression (e.g. a per-line query) while tolerating that overhead.
        with django_assert_max_num_queries(12):
            client_a.get(reverse("hrm:salarystructuretemplate_detail", args=[salary_template_a.pk]))


# ================================================================ Payroll Cycles (3.14)
class TestPayrollCycleListView:
    def test_list_200(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_cycle_a.pk in pks

    def test_list_filter_by_status(self, client_a, draft_cycle_a):
        from apps.hrm.models import PayrollCycle
        approved = PayrollCycle.objects.create(
            tenant=draft_cycle_a.tenant, period_start=datetime.date(2026, 5, 1),
            period_end=datetime.date(2026, 5, 31), pay_date=datetime.date(2026, 6, 1),
            status="approved",
        )
        resp = client_a.get(reverse("hrm:payrollcycle_list"), {"status": "approved"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert approved.pk in pks
        assert draft_cycle_a.pk not in pks

    def test_list_filter_by_cycle_type(self, client_a, draft_cycle_a):
        from apps.hrm.models import PayrollCycle
        bonus = PayrollCycle.objects.create(
            tenant=draft_cycle_a.tenant, period_start=datetime.date(2026, 5, 1),
            period_end=datetime.date(2026, 5, 31), pay_date=datetime.date(2026, 6, 1),
            cycle_type="bonus",
        )
        resp = client_a.get(reverse("hrm:payrollcycle_list"), {"cycle_type": "bonus"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert bonus.pk in pks
        assert draft_cycle_a.pk not in pks

    def test_list_has_status_and_cycle_type_choices(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_list"))
        assert "status_choices" in resp.context
        assert "cycle_type_choices" in resp.context


class TestPayrollCycleCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("hrm:payrollcycle_create"))
        assert resp.status_code == 200

    def test_post_creates(self, client_a, tenant_a):
        from apps.hrm.models import PayrollCycle
        resp = client_a.post(reverse("hrm:payrollcycle_create"), {
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "pay_date": "2026-07-01",
            "cycle_type": "regular",
            "notes": "",
        })
        assert resp.status_code == 302
        cycle = PayrollCycle.objects.filter(tenant=tenant_a).first()
        assert cycle is not None
        assert cycle.number.startswith("PRC-")
        assert cycle.tenant_id == tenant_a.pk


class TestPayrollCycleDetailAndEdit:
    def test_detail_200(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_detail", args=[draft_cycle_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_detail", args=[draft_cycle_a.pk]))
        assert "obj" in resp.context
        assert "payslips" in resp.context
        assert "totals" in resp.context

    def test_edit_get_200_when_draft(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_edit", args=[draft_cycle_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_updates_when_draft(self, client_a, draft_cycle_a):
        resp = client_a.post(reverse("hrm:payrollcycle_edit", args=[draft_cycle_a.pk]), {
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "pay_date": "2026-07-05",
            "cycle_type": "regular",
            "notes": "Updated notes",
        })
        assert resp.status_code == 302
        draft_cycle_a.refresh_from_db()
        assert draft_cycle_a.pay_date == datetime.date(2026, 7, 5)
        assert draft_cycle_a.notes == "Updated notes"

    def test_edit_blocked_when_not_draft(self, client_a, draft_cycle_a):
        draft_cycle_a.status = "approved"
        draft_cycle_a.save(update_fields=["status"])
        resp_get = client_a.get(reverse("hrm:payrollcycle_edit", args=[draft_cycle_a.pk]))
        assert resp_get.status_code == 302
        assert resp_get.url == reverse("hrm:payrollcycle_detail", args=[draft_cycle_a.pk])

        resp_post = client_a.post(reverse("hrm:payrollcycle_edit", args=[draft_cycle_a.pk]), {
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "pay_date": "2026-09-09",
            "cycle_type": "regular",
            "notes": "Sneaky",
        })
        assert resp_post.status_code == 302
        assert resp_post.url == reverse("hrm:payrollcycle_detail", args=[draft_cycle_a.pk])
        draft_cycle_a.refresh_from_db()
        assert draft_cycle_a.pay_date != datetime.date(2026, 9, 9)
        assert draft_cycle_a.notes != "Sneaky"


class TestPayrollCycleDeleteView:
    def test_post_deletes_when_draft(self, client_a, draft_cycle_a):
        from apps.hrm.models import PayrollCycle
        pk = draft_cycle_a.pk
        resp = client_a.post(reverse("hrm:payrollcycle_delete", args=[pk]))
        assert resp.status_code == 302
        assert not PayrollCycle.objects.filter(pk=pk).exists()

    def test_get_not_allowed(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_delete", args=[draft_cycle_a.pk]))
        assert resp.status_code == 405

    def test_delete_blocked_when_locked(self, client_a, draft_cycle_a):
        from apps.hrm.models import PayrollCycle
        draft_cycle_a.status = "locked"
        draft_cycle_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:payrollcycle_delete", args=[draft_cycle_a.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:payrollcycle_detail", args=[draft_cycle_a.pk])
        assert PayrollCycle.objects.filter(pk=draft_cycle_a.pk).exists()


class TestPayrollCycleGenerateView:
    def test_generate_creates_payslip_per_active_structure(
        self, client_a, tenant_a, draft_cycle_a, employee_a, active_structure_in_window_a,
        payroll_component_lines_a,
    ):
        from apps.hrm.models import Payslip
        resp = client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        assert resp.status_code == 302
        payslip = Payslip.objects.filter(tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a).first()
        assert payslip is not None
        assert payslip.salary_structure_id == active_structure_in_window_a.pk
        assert payslip.lines.exists()

    def test_generate_only_active_structures(
        self, client_a, tenant_a, draft_cycle_a, employee_a, active_structure_in_window_a,
        superseded_salary_structure_a, payroll_component_lines_a,
    ):
        from apps.hrm.models import Payslip
        client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        assert Payslip.objects.filter(tenant=tenant_a, cycle=draft_cycle_a).count() == 1

    def test_regenerate_preserves_manual_inputs(
        self, client_a, tenant_a, draft_cycle_a, employee_a, active_structure_in_window_a,
        payroll_component_lines_a,
    ):
        from apps.hrm.models import Payslip
        client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        payslip = Payslip.objects.get(tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a)
        payslip.arrears_amount = Decimal("777")
        payslip.on_hold = True
        payslip.days_worked = 20
        payslip.save(update_fields=["arrears_amount", "on_hold", "days_worked"])

        # Re-generate deletes and rebuilds each Payslip row (new pk) — re-fetch by employee rather
        # than refresh_from_db() the stale instance; manual inputs must still survive the rebuild.
        client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        regenerated = Payslip.objects.get(tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a)
        assert regenerated.arrears_amount == Decimal("777")
        assert regenerated.on_hold is True
        assert regenerated.days_worked == 20

    def test_generate_blocked_when_not_draft(
        self, client_a, tenant_a, draft_cycle_a, employee_a, active_structure_in_window_a,
        payroll_component_lines_a,
    ):
        from apps.hrm.models import Payslip
        draft_cycle_a.status = "approved"
        draft_cycle_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        assert resp.status_code == 302
        assert not Payslip.objects.filter(tenant=tenant_a, cycle=draft_cycle_a).exists()

    def test_generate_excludes_future_effective_from(
        self, client_a, tenant_a, draft_cycle_a, employee_a, salary_template_a, payroll_component_lines_a,
    ):
        """A structure whose effective_from is AFTER the cycle's period_end must be excluded from the
        effective-date window."""
        from apps.hrm.models import EmployeeSalaryStructure, Payslip
        EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, template=salary_template_a,
            annual_ctc_amount=Decimal("120000"), status="active",
            effective_from=datetime.date(2026, 12, 1),
        )
        resp = client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        assert resp.status_code == 302
        assert not Payslip.objects.filter(tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a).exists()

    def test_get_not_allowed(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        assert resp.status_code == 405


class TestPayrollCycleWorkflow:
    def test_submit_regular_goes_to_pending_approval(
        self, client_a, draft_cycle_a, employee_a, active_structure_in_window_a, payroll_component_lines_a,
    ):
        client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        resp = client_a.post(reverse("hrm:payrollcycle_submit", args=[draft_cycle_a.pk]))
        assert resp.status_code == 302
        draft_cycle_a.refresh_from_db()
        assert draft_cycle_a.status == "pending_approval"
        assert draft_cycle_a.submitted_by_id is not None
        assert draft_cycle_a.submitted_at is not None

    def test_submit_bonus_cycle_goes_straight_to_approved(
        self, client_a, tenant_a, employee_a, active_structure_in_window_a, payroll_component_lines_a,
    ):
        from apps.hrm.models import PayrollCycle
        bonus_cycle = PayrollCycle.objects.create(
            tenant=tenant_a, period_start=datetime.date(2026, 6, 1),
            period_end=datetime.date(2026, 6, 30), pay_date=datetime.date(2026, 7, 1),
            cycle_type="bonus",
        )
        client_a.post(reverse("hrm:payrollcycle_generate", args=[bonus_cycle.pk]))
        resp = client_a.post(reverse("hrm:payrollcycle_submit", args=[bonus_cycle.pk]))
        assert resp.status_code == 302
        bonus_cycle.refresh_from_db()
        assert bonus_cycle.status == "approved"

    def test_submit_blocked_without_payslips(self, client_a, draft_cycle_a):
        resp = client_a.post(reverse("hrm:payrollcycle_submit", args=[draft_cycle_a.pk]))
        assert resp.status_code == 302
        draft_cycle_a.refresh_from_db()
        assert draft_cycle_a.status == "draft"

    def test_submit_get_not_allowed(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_submit", args=[draft_cycle_a.pk]))
        assert resp.status_code == 405

    def test_approve_by_tenant_admin(self, client_a, admin_user, draft_cycle_a, employee_a,
                                      active_structure_in_window_a, payroll_component_lines_a):
        client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        client_a.post(reverse("hrm:payrollcycle_submit", args=[draft_cycle_a.pk]))
        resp = client_a.post(reverse("hrm:payrollcycle_approve", args=[draft_cycle_a.pk]))
        assert resp.status_code == 302
        draft_cycle_a.refresh_from_db()
        assert draft_cycle_a.status == "approved"
        assert draft_cycle_a.approved_by_id == admin_user.pk
        assert draft_cycle_a.approved_at is not None

    def test_reject_by_tenant_admin_stores_reason(
        self, client_a, admin_user, draft_cycle_a, employee_a, active_structure_in_window_a,
        payroll_component_lines_a,
    ):
        client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        client_a.post(reverse("hrm:payrollcycle_submit", args=[draft_cycle_a.pk]))
        resp = client_a.post(reverse("hrm:payrollcycle_reject", args=[draft_cycle_a.pk]), {
            "rejection_reason": "Missing headcount for new hires",
        })
        assert resp.status_code == 302
        draft_cycle_a.refresh_from_db()
        assert draft_cycle_a.status == "rejected"
        assert draft_cycle_a.rejection_reason == "Missing headcount for new hires"

    def test_approve_get_not_allowed(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_approve", args=[draft_cycle_a.pk]))
        assert resp.status_code == 405

    def test_reject_get_not_allowed(self, client_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payrollcycle_reject", args=[draft_cycle_a.pk]))
        assert resp.status_code == 405

    def test_non_admin_cannot_approve(self, member_client, draft_cycle_a):
        resp = member_client.post(reverse("hrm:payrollcycle_approve", args=[draft_cycle_a.pk]))
        assert resp.status_code == 403

    def test_non_admin_cannot_lock(self, member_client, draft_cycle_a):
        draft_cycle_a.status = "approved"
        draft_cycle_a.save(update_fields=["status"])
        resp = member_client.post(reverse("hrm:payrollcycle_lock", args=[draft_cycle_a.pk]))
        assert resp.status_code == 403
        draft_cycle_a.refresh_from_db()
        assert draft_cycle_a.status == "approved"


class TestPayrollCycleLockView:
    """The accounting hand-off — the most important test in the 3.14 suite: penny reconciliation
    between the HRM PayrollCycle's payslip totals and the accounting.PayrollRun it creates."""

    def _approved_cycle_with_payslips(self, client_a, tenant_a, draft_cycle_a, employee_a, employee_a2,
                                       salary_template_a):
        """Builds a template with an earning + employee-side statutory + employer-side statutory line,
        generates payslips for two employees on different CTCs, then submits+approves the cycle."""
        from apps.hrm.models import PayComponent, SalaryStructureLine, EmployeeSalaryStructure
        basic = PayComponent.objects.create(
            tenant=tenant_a, name="Basic Pay", component_type="earning",
            calculation_type="fixed_amount", default_amount=Decimal("60000"),
        )
        pf_ee = PayComponent.objects.create(
            tenant=tenant_a, name="PF Employee", component_type="statutory_deduction",
            calculation_type="fixed_amount", default_amount=Decimal("1200"),
            contribution_side="employee",
        )
        pf_er = PayComponent.objects.create(
            tenant=tenant_a, name="PF Employer", component_type="statutory_deduction",
            calculation_type="fixed_amount", default_amount=Decimal("1200"),
            contribution_side="employer",
        )
        SalaryStructureLine.objects.create(tenant=tenant_a, template=salary_template_a, pay_component=basic, amount=Decimal("60000"))
        SalaryStructureLine.objects.create(tenant=tenant_a, template=salary_template_a, pay_component=pf_ee, amount=Decimal("1200"))
        SalaryStructureLine.objects.create(tenant=tenant_a, template=salary_template_a, pay_component=pf_er, amount=Decimal("1200"))

        EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a, template=salary_template_a,
            annual_ctc_amount=Decimal("120000"), status="active",
            effective_from=datetime.date(2026, 5, 1),
        )
        EmployeeSalaryStructure.objects.create(
            tenant=tenant_a, employee=employee_a2, template=salary_template_a,
            annual_ctc_amount=Decimal("240000"), status="active",
            effective_from=datetime.date(2026, 5, 1),
        )
        client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        client_a.post(reverse("hrm:payrollcycle_submit", args=[draft_cycle_a.pk]))
        client_a.post(reverse("hrm:payrollcycle_approve", args=[draft_cycle_a.pk]))
        draft_cycle_a.refresh_from_db()
        assert draft_cycle_a.status == "approved"
        return draft_cycle_a

    def test_lock_creates_accounting_run_with_penny_reconciliation(
        self, client_a, tenant_a, draft_cycle_a, employee_a, employee_a2, salary_template_a,
    ):
        from apps.hrm.models import Payslip, PayslipLine
        from django.db.models import Sum
        cycle = self._approved_cycle_with_payslips(
            client_a, tenant_a, draft_cycle_a, employee_a, employee_a2, salary_template_a)

        resp = client_a.post(reverse("hrm:payrollcycle_lock", args=[cycle.pk]))
        assert resp.status_code == 302
        cycle.refresh_from_db()
        assert cycle.status == "locked"
        assert cycle.accounting_payroll_run is not None

        run = cycle.accounting_payroll_run
        payslip_totals = Payslip.objects.filter(cycle=cycle).aggregate(
            g=Sum("gross_pay"), n=Sum("net_pay"))
        employer_lines_total = PayslipLine.objects.filter(
            payslip__cycle=cycle, component_type="statutory_deduction", contribution_side="employer",
        ).aggregate(s=Sum("amount"))["s"]

        assert run.gross_wages == payslip_totals["g"]
        assert run.employer_tax == employer_lines_total
        # Penny reconciliation: the accounting run's derived net_pay must equal Σ payslip.net_pay.
        assert run.net_pay == payslip_totals["n"]

    def test_lock_run_stays_draft_no_journal_entry(
        self, client_a, tenant_a, draft_cycle_a, employee_a, employee_a2, salary_template_a,
    ):
        """HRM posts no GL — the created accounting.PayrollRun stays draft with no JournalEntry."""
        cycle = self._approved_cycle_with_payslips(
            client_a, tenant_a, draft_cycle_a, employee_a, employee_a2, salary_template_a)
        client_a.post(reverse("hrm:payrollcycle_lock", args=[cycle.pk]))
        cycle.refresh_from_db()
        run = cycle.accounting_payroll_run
        assert run.status == "draft"
        assert run.journal_entry is None

    def test_lock_blocked_when_not_approved(self, client_a, draft_cycle_a):
        resp = client_a.post(reverse("hrm:payrollcycle_lock", args=[draft_cycle_a.pk]))
        assert resp.status_code == 302
        draft_cycle_a.refresh_from_db()
        assert draft_cycle_a.status == "draft"
        assert draft_cycle_a.accounting_payroll_run is None

    def test_relock_impossible_no_second_run(
        self, client_a, tenant_a, draft_cycle_a, employee_a, employee_a2, salary_template_a,
    ):
        from apps.accounting.models import PayrollRun as AccountingPayrollRun
        cycle = self._approved_cycle_with_payslips(
            client_a, tenant_a, draft_cycle_a, employee_a, employee_a2, salary_template_a)
        client_a.post(reverse("hrm:payrollcycle_lock", args=[cycle.pk]))
        cycle.refresh_from_db()
        first_run_pk = cycle.accounting_payroll_run_id
        # Second lock attempt — cycle is now 'locked', not 'approved', so it must be a no-op.
        resp = client_a.post(reverse("hrm:payrollcycle_lock", args=[cycle.pk]))
        assert resp.status_code == 302
        cycle.refresh_from_db()
        assert cycle.accounting_payroll_run_id == first_run_pk
        assert AccountingPayrollRun.objects.filter(tenant=tenant_a).count() == 1

    def test_locked_cycle_blocks_generate_edit_delete(self, client_a, tenant_a, draft_cycle_a,
                                                       employee_a, active_structure_in_window_a,
                                                       payroll_component_lines_a):
        from apps.hrm.models import Payslip, PayrollCycle
        client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        payslip_count_before = Payslip.objects.filter(tenant=tenant_a, cycle=draft_cycle_a).count()
        draft_cycle_a.status = "locked"
        draft_cycle_a.save(update_fields=["status"])

        resp_generate = client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        assert resp_generate.status_code == 302
        # Generate is a no-op on a locked cycle — payslip count unchanged.
        assert Payslip.objects.filter(tenant=tenant_a, cycle=draft_cycle_a).count() == payslip_count_before

        resp_edit = client_a.get(reverse("hrm:payrollcycle_edit", args=[draft_cycle_a.pk]))
        assert resp_edit.status_code == 302
        assert resp_edit.url == reverse("hrm:payrollcycle_detail", args=[draft_cycle_a.pk])

        resp_delete = client_a.post(reverse("hrm:payrollcycle_delete", args=[draft_cycle_a.pk]))
        assert resp_delete.status_code == 302
        assert PayrollCycle.objects.filter(pk=draft_cycle_a.pk).exists()

    def test_locked_cycle_blocks_payslip_edit_and_hold(self, client_a, admin_user, tenant_a, draft_cycle_a,
                                                         employee_a, active_structure_in_window_a,
                                                         payroll_component_lines_a):
        from apps.hrm.models import Payslip
        client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))
        payslip = Payslip.objects.get(tenant=tenant_a, cycle=draft_cycle_a, employee=employee_a)
        draft_cycle_a.status = "locked"
        draft_cycle_a.save(update_fields=["status"])

        resp_edit = client_a.get(reverse("hrm:payslip_edit", args=[payslip.pk]))
        assert resp_edit.status_code == 302
        resp_hold = client_a.post(reverse("hrm:payslip_hold", args=[payslip.pk]), {"hold_reason": "x"})
        assert resp_hold.status_code == 302
        payslip.refresh_from_db()
        assert payslip.on_hold is False


# ================================================================ Payslips (3.14)
class TestPayslipListView:
    def test_list_200(self, client_a, payslip_a):
        resp = client_a.get(reverse("hrm:payslip_list"))
        assert resp.status_code == 200

    def test_list_shows_own(self, client_a, payslip_a):
        resp = client_a.get(reverse("hrm:payslip_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert payslip_a.pk in pks

    def test_list_filter_on_hold(self, client_a, payslip_a):
        payslip_a.on_hold = True
        payslip_a.save(update_fields=["on_hold"])
        resp = client_a.get(reverse("hrm:payslip_list"), {"on_hold": "True"})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert payslip_a.pk in pks

        resp2 = client_a.get(reverse("hrm:payslip_list"), {"on_hold": "False"})
        pks2 = [obj.pk for obj in resp2.context["object_list"]]
        assert payslip_a.pk not in pks2

    def test_list_filter_by_cycle(self, client_a, payslip_a, draft_cycle_a):
        resp = client_a.get(reverse("hrm:payslip_list"), {"cycle": draft_cycle_a.pk})
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert payslip_a.pk in pks

    def test_list_has_cycles_context(self, client_a, payslip_a):
        resp = client_a.get(reverse("hrm:payslip_list"))
        assert "cycles" in resp.context


class TestPayslipDetailView:
    def test_detail_200(self, client_a, payslip_a):
        resp = client_a.get(reverse("hrm:payslip_detail", args=[payslip_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_keys(self, client_a, payslip_a):
        resp = client_a.get(reverse("hrm:payslip_detail", args=[payslip_a.pk]))
        assert "obj" in resp.context
        assert "lines" in resp.context
        assert len(resp.context["lines"]) > 0


class TestPayslipEditView:
    def test_edit_get_200_when_draft_cycle(self, client_a, payslip_a):
        resp = client_a.get(reverse("hrm:payslip_edit", args=[payslip_a.pk]))
        assert resp.status_code == 200

    def test_edit_post_with_arrears_recomputes(self, client_a, payslip_a):
        original_gross = payslip_a.gross_pay
        resp = client_a.post(reverse("hrm:payslip_edit", args=[payslip_a.pk]), {
            "days_worked": "30",
            "lop_days": "0",
            "arrears_amount": "150",
            "bonus_amount": "0",
        })
        assert resp.status_code == 302
        payslip_a.refresh_from_db()
        assert payslip_a.arrears_amount == Decimal("150")
        assert payslip_a.gross_pay == original_gross + Decimal("150.00")
        assert payslip_a.lines.filter(component_type="arrears").exists()

    def test_edit_blocked_when_cycle_not_draft(self, client_a, payslip_a, draft_cycle_a):
        draft_cycle_a.status = "approved"
        draft_cycle_a.save(update_fields=["status"])
        resp = client_a.get(reverse("hrm:payslip_edit", args=[payslip_a.pk]))
        assert resp.status_code == 302
        assert resp.url == reverse("hrm:payslip_detail", args=[payslip_a.pk])


class TestPayslipHoldRelease:
    def test_hold_by_tenant_admin(self, client_a, payslip_a):
        resp = client_a.post(reverse("hrm:payslip_hold", args=[payslip_a.pk]), {"hold_reason": "Pending dispute"})
        assert resp.status_code == 302
        payslip_a.refresh_from_db()
        assert payslip_a.on_hold is True
        assert payslip_a.hold_reason == "Pending dispute"

    def test_release_by_tenant_admin(self, client_a, payslip_a):
        client_a.post(reverse("hrm:payslip_hold", args=[payslip_a.pk]), {"hold_reason": "x"})
        resp = client_a.post(reverse("hrm:payslip_release", args=[payslip_a.pk]))
        assert resp.status_code == 302
        payslip_a.refresh_from_db()
        assert payslip_a.on_hold is False
        payslip_a.refresh_from_db()
        assert payslip_a.released_at is not None

    def test_non_admin_cannot_hold(self, member_client, payslip_a):
        resp = member_client.post(reverse("hrm:payslip_hold", args=[payslip_a.pk]), {"hold_reason": "x"})
        assert resp.status_code == 403
        payslip_a.refresh_from_db()
        assert payslip_a.on_hold is False

    def test_non_admin_cannot_release(self, client_a, member_client, payslip_a):
        client_a.post(reverse("hrm:payslip_hold", args=[payslip_a.pk]), {"hold_reason": "x"})
        resp = member_client.post(reverse("hrm:payslip_release", args=[payslip_a.pk]))
        assert resp.status_code == 403
        payslip_a.refresh_from_db()
        assert payslip_a.on_hold is True

    def test_hold_blocked_when_cycle_locked(self, client_a, payslip_a, draft_cycle_a):
        draft_cycle_a.status = "locked"
        draft_cycle_a.save(update_fields=["status"])
        resp = client_a.post(reverse("hrm:payslip_hold", args=[payslip_a.pk]), {"hold_reason": "x"})
        assert resp.status_code == 302
        payslip_a.refresh_from_db()
        assert payslip_a.on_hold is False


class TestPayrollCycleQueryCount:
    def test_generate_bounded_queries(
        self, client_a, draft_cycle_a, employee_a, active_structure_in_window_a,
        payroll_component_lines_a, django_assert_max_num_queries,
    ):
        # Locks in the O(N) FK-cache-warm behavior of payrollcycle_generate (one query set per
        # structure, not per structure-times-lines) — this is a single-employee cycle so the ceiling
        # is generous but still catches a gross N+1 regression.
        with django_assert_max_num_queries(30):
            client_a.post(reverse("hrm:payrollcycle_generate", args=[draft_cycle_a.pk]))

    def test_detail_bounded_queries(self, client_a, payslip_a, draft_cycle_a, django_assert_max_num_queries):
        with django_assert_max_num_queries(15):
            client_a.get(reverse("hrm:payrollcycle_detail", args=[draft_cycle_a.pk]))
