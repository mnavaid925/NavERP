"""Security tests for the HRM module: IDOR (cross-tenant isolation), auth, CSRF,
mass-assignment, delete guards, photo upload validation."""
import datetime

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ IDOR — tenant A accessing tenant B records
class TestEmployeeProfileIDOR:
    def test_detail_cross_tenant_404(self, client_a, employee_b):
        resp = client_a.get(reverse("hrm:employee_detail", args=[employee_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, employee_b):
        resp = client_a.get(reverse("hrm:employee_edit", args=[employee_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, employee_b):
        resp = client_a.post(reverse("hrm:employee_edit", args=[employee_b.pk]), {
            "employee_type": "contract",
            "party": employee_b.party_id,
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, employee_b):
        resp = client_a.post(reverse("hrm:employee_delete", args=[employee_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_employees(self, client_a, employee_a, employee_b):
        resp = client_a.get(reverse("hrm:employee_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert employee_a.pk in pks
        assert employee_b.pk not in pks


class TestLeaveRequestIDOR:
    def test_detail_cross_tenant_404(self, client_a, leave_request_b):
        resp = client_a.get(reverse("hrm:leaverequest_detail", args=[leave_request_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, leave_request_b):
        resp = client_a.get(reverse("hrm:leaverequest_edit", args=[leave_request_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, leave_request_b):
        resp = client_a.post(reverse("hrm:leaverequest_delete", args=[leave_request_b.pk]))
        assert resp.status_code == 404

    def test_submit_cross_tenant_404(self, client_a, leave_request_b):
        resp = client_a.post(reverse("hrm:leaverequest_submit", args=[leave_request_b.pk]))
        assert resp.status_code == 404

    def test_approve_cross_tenant_404(self, client_a, leave_request_b):
        resp = client_a.post(reverse("hrm:leaverequest_approve", args=[leave_request_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_requests(self, client_a, draft_leave_request, leave_request_b):
        resp = client_a.get(reverse("hrm:leaverequest_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_leave_request.pk in pks
        assert leave_request_b.pk not in pks


class TestAttendanceRecordIDOR:
    def test_detail_cross_tenant_404(self, client_a, attendance_b):
        resp = client_a.get(reverse("hrm:attendancerecord_detail", args=[attendance_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, attendance_b):
        resp = client_a.get(reverse("hrm:attendancerecord_edit", args=[attendance_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, attendance_b):
        resp = client_a.post(reverse("hrm:attendancerecord_delete", args=[attendance_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_attendance(self, client_a, attendance_a, attendance_b):
        resp = client_a.get(reverse("hrm:attendancerecord_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert attendance_a.pk in pks
        assert attendance_b.pk not in pks


class TestDesignationIDOR:
    def test_detail_cross_tenant_404(self, client_a, designation_b):
        resp = client_a.get(reverse("hrm:designation_detail", args=[designation_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, designation_b):
        resp = client_a.get(reverse("hrm:designation_edit", args=[designation_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, designation_b):
        resp = client_a.post(reverse("hrm:designation_delete", args=[designation_b.pk]))
        assert resp.status_code == 404


class TestShiftIDOR:
    def test_detail_cross_tenant_404(self, client_a, shift_b):
        resp = client_a.get(reverse("hrm:shift_detail", args=[shift_b.pk]))
        assert resp.status_code == 404

    def test_edit_cross_tenant_404(self, client_a, shift_b):
        resp = client_a.get(reverse("hrm:shift_edit", args=[shift_b.pk]))
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, shift_b):
        resp = client_a.post(reverse("hrm:shift_delete", args=[shift_b.pk]))
        assert resp.status_code == 404


# ================================================================ Anonymous user → redirect
class TestAnonymousBlocked:
    @pytest.mark.parametrize("url_name,args", [
        ("hrm:hrm_overview", []),
        ("hrm:designation_list", []),
        ("hrm:employee_list", []),
        ("hrm:leavetype_list", []),
        ("hrm:leaveallocation_list", []),
        ("hrm:leaverequest_list", []),
        ("hrm:publicholiday_list", []),
        ("hrm:shift_list", []),
        ("hrm:shiftassignment_list", []),
        ("hrm:attendancerecord_list", []),
    ])
    def test_anon_redirected_to_login(self, client, url_name, args):
        resp = client.get(reverse(url_name, args=args))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


# ================================================================ Admin-only workflow actions
class TestLeaveWorkflowAdminOnly:
    """approve and reject require @tenant_admin_required; a non-admin user must be denied."""

    def test_non_admin_cannot_approve(self, member_client, pending_leave_request):
        """A non-admin member must get 403 (PermissionDenied) when trying to approve."""
        resp = member_client.post(
            reverse("hrm:leaverequest_approve", args=[pending_leave_request.pk])
        )
        assert resp.status_code == 403
        pending_leave_request.refresh_from_db()
        assert pending_leave_request.status == "pending"  # unchanged

    def test_non_admin_cannot_reject(self, member_client, pending_leave_request):
        """A non-admin member must get 403 when trying to reject."""
        resp = member_client.post(
            reverse("hrm:leaverequest_reject", args=[pending_leave_request.pk]),
            {"rejected_reason": "Attempt"}
        )
        assert resp.status_code == 403
        pending_leave_request.refresh_from_db()
        assert pending_leave_request.status == "pending"  # unchanged


# ================================================================ Mass-assignment guard
class TestMassAssignmentGuard:
    def test_create_with_spoofed_status_stays_draft(self, client_a, tenant_a, employee_a, leave_type_a, admin_user):
        """POST to leaverequest_create with status=approved + approver=<pk> must be ignored.
        The saved row must be draft with approver=None."""
        from apps.hrm.models import LeaveRequest
        resp = client_a.post(reverse("hrm:leaverequest_create"), {
            "employee": employee_a.pk,
            "leave_type": leave_type_a.pk,
            "start_date": "2026-11-01",
            "end_date": "2026-11-03",
            "reason": "Sneaky",
            "status": "approved",       # mass-assignment attempt
            "approver": admin_user.pk,  # mass-assignment attempt
        })
        assert resp.status_code == 302
        lr = LeaveRequest.objects.filter(
            tenant=tenant_a, employee=employee_a,
            start_date=datetime.date(2026, 11, 1)
        ).first()
        assert lr is not None
        assert lr.status == "draft"
        assert lr.approver is None


# ================================================================ CSRF enforcement on POST-only endpoints
class TestCSRFEnforcement:
    def test_leave_request_delete_enforces_csrf(self, admin_user, draft_leave_request):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:leaverequest_delete", args=[draft_leave_request.pk]))
        assert resp.status_code == 403

    def test_leave_request_approve_enforces_csrf(self, admin_user, pending_leave_request):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:leaverequest_approve", args=[pending_leave_request.pk]))
        assert resp.status_code == 403

    def test_shift_delete_enforces_csrf(self, admin_user, shift_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:shift_delete", args=[shift_a.pk]))
        assert resp.status_code == 403

    def test_designation_delete_enforces_csrf(self, admin_user, designation_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:designation_delete", args=[designation_a.pk]))
        assert resp.status_code == 403


# ================================================================ Photo upload validation
class TestPhotoValidation:
    def test_disallowed_extension_rejected(self, client_a, employee_a):
        """A .pdf photo upload must be rejected by clean_photo."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        fake_pdf = SimpleUploadedFile("resume.pdf", b"fake pdf content", content_type="application/pdf")
        resp = client_a.post(
            reverse("hrm:employee_edit", args=[employee_a.pk]),
            {
                "party": employee_a.party_id,
                "employee_type": "full_time",
                "gender": "female",
                "photo": fake_pdf,
            },
            format="multipart",
        )
        # Form should be invalid (re-renders the form) — not a redirect
        assert resp.status_code == 200
        form = resp.context.get("form")
        assert form is not None
        assert not form.is_valid() or "photo" in form.errors

    def test_oversize_photo_rejected(self, client_a, employee_a):
        """A photo larger than 5 MB must be rejected."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        big_image = SimpleUploadedFile(
            "big.jpg",
            b"\xff\xd8\xff\xe0" + b"x" * (5 * 1024 * 1024 + 1),  # > 5 MB JPEG-like
            content_type="image/jpeg",
        )
        resp = client_a.post(
            reverse("hrm:employee_edit", args=[employee_a.pk]),
            {
                "party": employee_a.party_id,
                "employee_type": "full_time",
                "gender": "female",
                "photo": big_image,
            },
            format="multipart",
        )
        assert resp.status_code == 200
        form = resp.context.get("form")
        assert form is not None
        assert not form.is_valid() or "photo" in form.errors


# ================================================================ Delete guards (product behaviour)
class TestDeleteGuards:
    def test_active_employee_cannot_be_deleted(self, client_a, employee_a):
        """employee_delete should refuse if employment.status == active."""
        from apps.hrm.models import EmployeeProfile
        pk = employee_a.pk
        client_a.post(reverse("hrm:employee_delete", args=[pk]))
        assert EmployeeProfile.objects.filter(pk=pk).exists()

    def test_inuse_leave_type_cannot_be_deleted(self, client_a, leave_type_a, leave_allocation_a):
        """A LeaveType with allocations must not be deletable."""
        from apps.hrm.models import LeaveType
        pk = leave_type_a.pk
        client_a.post(reverse("hrm:leavetype_delete", args=[pk]))
        assert LeaveType.objects.filter(pk=pk).exists()

    def test_inuse_shift_cannot_be_deleted(self, client_a, shift_a, employee_a):
        """A shift with assignments must not be deletable."""
        from apps.hrm.models import Shift, ShiftAssignment
        ShiftAssignment.objects.create(
            tenant=shift_a.tenant, employee=employee_a, shift=shift_a,
            effective_from=datetime.date(2026, 1, 1),
        )
        pk = shift_a.pk
        client_a.post(reverse("hrm:shift_delete", args=[pk]))
        assert Shift.objects.filter(pk=pk).exists()

    def test_inuse_designation_cannot_be_deleted(self, client_a, designation_a, employee_a):
        """A designation assigned to employees must not be deletable."""
        from apps.hrm.models import Designation
        pk = designation_a.pk
        client_a.post(reverse("hrm:designation_delete", args=[pk]))
        assert Designation.objects.filter(pk=pk).exists()
