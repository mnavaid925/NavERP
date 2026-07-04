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


class TestHolidayPolicyIDOR:
    def test_detail_cross_tenant_404(self, client_a, holiday_policy_b):
        resp = client_a.get(reverse("hrm:holidaypolicy_detail", args=[holiday_policy_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, holiday_policy_b):
        resp = client_a.get(reverse("hrm:holidaypolicy_edit", args=[holiday_policy_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, holiday_policy_b):
        resp = client_a.post(reverse("hrm:holidaypolicy_edit", args=[holiday_policy_b.pk]), {
            "name": "Hijacked", "floating_holiday_quota": "9",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, holiday_policy_b):
        resp = client_a.post(reverse("hrm:holidaypolicy_delete", args=[holiday_policy_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_policies(self, client_a, default_holiday_policy_a, holiday_policy_b):
        resp = client_a.get(reverse("hrm:holidaypolicy_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert default_holiday_policy_a.pk in pks
        assert holiday_policy_b.pk not in pks


class TestFloatingHolidayElectionIDOR:
    def test_detail_cross_tenant_404(self, client_a, election_b):
        resp = client_a.get(reverse("hrm:floatingholidayelection_detail", args=[election_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, election_b):
        resp = client_a.get(reverse("hrm:floatingholidayelection_edit", args=[election_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, election_b):
        resp = client_a.post(reverse("hrm:floatingholidayelection_edit", args=[election_b.pk]), {
            "employee": election_b.employee_id, "holiday": election_b.holiday_id, "note": "Hijacked",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, election_b):
        resp = client_a.post(reverse("hrm:floatingholidayelection_delete", args=[election_b.pk]))
        assert resp.status_code == 404

    def test_approve_cross_tenant_404(self, client_a, election_b):
        resp = client_a.post(reverse("hrm:floatingholidayelection_approve", args=[election_b.pk]))
        assert resp.status_code == 404

    def test_reject_cross_tenant_404(self, client_a, election_b):
        resp = client_a.post(reverse("hrm:floatingholidayelection_reject", args=[election_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_elections(self, client_a, pending_election_a, election_b):
        resp = client_a.get(reverse("hrm:floatingholidayelection_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pending_election_a.pk in pks
        assert election_b.pk not in pks


class TestPayComponentIDOR:
    def test_detail_cross_tenant_404(self, client_a, pay_component_b):
        resp = client_a.get(reverse("hrm:paycomponent_detail", args=[pay_component_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, pay_component_b):
        resp = client_a.get(reverse("hrm:paycomponent_edit", args=[pay_component_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, pay_component_b):
        resp = client_a.post(reverse("hrm:paycomponent_edit", args=[pay_component_b.pk]), {
            "name": "Hijacked", "component_type": "earning", "calculation_type": "fixed_amount",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, pay_component_b):
        resp = client_a.post(reverse("hrm:paycomponent_delete", args=[pay_component_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_components(self, client_a, pay_component_a, pay_component_b):
        resp = client_a.get(reverse("hrm:paycomponent_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert pay_component_a.pk in pks
        assert pay_component_b.pk not in pks


class TestSalaryStructureTemplateIDOR:
    def test_detail_cross_tenant_404(self, client_a, salary_template_b):
        resp = client_a.get(reverse("hrm:salarystructuretemplate_detail", args=[salary_template_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, salary_template_b):
        resp = client_a.get(reverse("hrm:salarystructuretemplate_edit", args=[salary_template_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, salary_template_b):
        resp = client_a.post(reverse("hrm:salarystructuretemplate_edit", args=[salary_template_b.pk]), {
            "name": "Hijacked", "annual_ctc_amount": "1", "currency": "USD",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, salary_template_b):
        resp = client_a.post(reverse("hrm:salarystructuretemplate_delete", args=[salary_template_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_templates(self, client_a, salary_template_a, salary_template_b):
        resp = client_a.get(reverse("hrm:salarystructuretemplate_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert salary_template_a.pk in pks
        assert salary_template_b.pk not in pks


class TestSalaryStructureLineIDOR:
    def test_add_post_cross_tenant_template_404(self, client_a, salary_template_b, pay_component_b):
        resp = client_a.post(
            reverse("hrm:salarystructureline_add", args=[salary_template_b.pk]), {
                "pay_component": pay_component_b.pk, "amount": "1000", "sequence": "1",
            })
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, salary_line_b):
        resp = client_a.get(reverse("hrm:salarystructureline_edit", args=[salary_line_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, salary_line_b, pay_component_b):
        resp = client_a.post(reverse("hrm:salarystructureline_edit", args=[salary_line_b.pk]), {
            "pay_component": pay_component_b.pk, "amount": "9999", "sequence": "1",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, salary_line_b):
        resp = client_a.post(reverse("hrm:salarystructureline_delete", args=[salary_line_b.pk]))
        assert resp.status_code == 404


class TestEmployeeSalaryStructureIDOR:
    def test_detail_cross_tenant_404(self, client_a, employee_salary_structure_b):
        resp = client_a.get(reverse("hrm:employeesalarystructure_detail", args=[employee_salary_structure_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, employee_salary_structure_b):
        resp = client_a.get(reverse("hrm:employeesalarystructure_edit", args=[employee_salary_structure_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, employee_salary_structure_b):
        resp = client_a.post(
            reverse("hrm:employeesalarystructure_edit", args=[employee_salary_structure_b.pk]), {
                "employee": employee_salary_structure_b.employee_id,
                "annual_ctc_amount": "1", "effective_from": "2026-07-01", "status": "active",
            })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, employee_salary_structure_b):
        resp = client_a.post(reverse("hrm:employeesalarystructure_delete", args=[employee_salary_structure_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_assignments(self, client_a, active_salary_structure_a, employee_salary_structure_b):
        resp = client_a.get(reverse("hrm:employeesalarystructure_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert active_salary_structure_a.pk in pks
        assert employee_salary_structure_b.pk not in pks


# ================================================================ Payroll Processing IDOR (3.14)
class TestPayrollCycleIDOR:
    def test_detail_cross_tenant_404(self, client_a, cycle_b):
        resp = client_a.get(reverse("hrm:payrollcycle_detail", args=[cycle_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, cycle_b):
        resp = client_a.get(reverse("hrm:payrollcycle_edit", args=[cycle_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, cycle_b):
        resp = client_a.post(reverse("hrm:payrollcycle_edit", args=[cycle_b.pk]), {
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "pay_date": "2026-07-01",
            "cycle_type": "regular",
            "notes": "",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, cycle_b):
        resp = client_a.post(reverse("hrm:payrollcycle_delete", args=[cycle_b.pk]))
        assert resp.status_code == 404

    def test_generate_cross_tenant_404(self, client_a, cycle_b):
        resp = client_a.post(reverse("hrm:payrollcycle_generate", args=[cycle_b.pk]))
        assert resp.status_code == 404

    def test_submit_cross_tenant_404(self, client_a, cycle_b):
        resp = client_a.post(reverse("hrm:payrollcycle_submit", args=[cycle_b.pk]))
        assert resp.status_code == 404

    def test_approve_cross_tenant_404(self, client_a, cycle_b):
        resp = client_a.post(reverse("hrm:payrollcycle_approve", args=[cycle_b.pk]))
        assert resp.status_code == 404

    def test_reject_cross_tenant_404(self, client_a, cycle_b):
        resp = client_a.post(reverse("hrm:payrollcycle_reject", args=[cycle_b.pk]))
        assert resp.status_code == 404

    def test_lock_cross_tenant_404(self, client_a, cycle_b):
        resp = client_a.post(reverse("hrm:payrollcycle_lock", args=[cycle_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_cycles(self, client_a, draft_cycle_a, cycle_b):
        resp = client_a.get(reverse("hrm:payrollcycle_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert draft_cycle_a.pk in pks
        assert cycle_b.pk not in pks


class TestPayslipIDOR:
    def test_detail_cross_tenant_404(self, client_a, payslip_b):
        resp = client_a.get(reverse("hrm:payslip_detail", args=[payslip_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, payslip_b):
        resp = client_a.get(reverse("hrm:payslip_edit", args=[payslip_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, payslip_b):
        resp = client_a.post(reverse("hrm:payslip_edit", args=[payslip_b.pk]), {
            "days_worked": "30", "lop_days": "0", "arrears_amount": "0", "bonus_amount": "0",
        })
        assert resp.status_code == 404

    def test_hold_cross_tenant_404(self, client_a, payslip_b):
        resp = client_a.post(reverse("hrm:payslip_hold", args=[payslip_b.pk]), {"hold_reason": "x"})
        assert resp.status_code == 404

    def test_release_cross_tenant_404(self, client_a, payslip_b):
        resp = client_a.post(reverse("hrm:payslip_release", args=[payslip_b.pk]))
        assert resp.status_code == 404

    def test_list_excludes_b_payslips(self, client_a, payslip_a, payslip_b):
        resp = client_a.get(reverse("hrm:payslip_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert payslip_a.pk in pks
        assert payslip_b.pk not in pks


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
        ("hrm:holidaypolicy_list", []),
        ("hrm:floatingholidayelection_list", []),
        ("hrm:paycomponent_list", []),
        ("hrm:salarystructuretemplate_list", []),
        ("hrm:employeesalarystructure_list", []),
        ("hrm:payrollcycle_list", []),
        ("hrm:payslip_list", []),
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

    def test_holidaypolicy_delete_enforces_csrf(self, admin_user, default_holiday_policy_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:holidaypolicy_delete", args=[default_holiday_policy_a.pk]))
        assert resp.status_code == 403

    def test_floatingholidayelection_approve_enforces_csrf(self, admin_user, pending_election_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:floatingholidayelection_approve", args=[pending_election_a.pk]))
        assert resp.status_code == 403

    def test_payrollcycle_delete_enforces_csrf(self, admin_user, draft_cycle_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payrollcycle_delete", args=[draft_cycle_a.pk]))
        assert resp.status_code == 403

    def test_payrollcycle_lock_enforces_csrf(self, admin_user, draft_cycle_a):
        draft_cycle_a.status = "approved"
        draft_cycle_a.save(update_fields=["status"])
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("hrm:payrollcycle_lock", args=[draft_cycle_a.pk]))
        assert resp.status_code == 403
        draft_cycle_a.refresh_from_db()
        assert draft_cycle_a.status == "approved"


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
