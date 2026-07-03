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
