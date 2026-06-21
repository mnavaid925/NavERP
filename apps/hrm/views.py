"""HRM (Module 3) views — function-based, ``@login_required``, tenant-scoped.

Full CRUD for the nine HRM models via the shared ``apps.core.crud`` helpers (search +
int-FK-guarded filters + windowed pagination + audit), plus:
  * an HRM overview (3.1) with headcount / today's attendance / pending-leave / holiday widgets,
  * a rich employee profile (leave balances, recent attendance, current shift),
  * the leave-request workflow actions (submit / approve / reject / cancel),
  * delete guards on records that anchor others (active employee, in-use leave type/shift).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.models import Employment, OrgUnit
from apps.core.utils import write_audit_log

from .forms import (
    AttendanceRecordForm,
    DesignationForm,
    EmployeeProfileForm,
    LeaveAllocationForm,
    LeaveRequestForm,
    LeaveTypeForm,
    PublicHolidayForm,
    ShiftAssignmentForm,
    ShiftForm,
)
from .models import (
    AttendanceRecord,
    Designation,
    EmployeeProfile,
    LeaveAllocation,
    LeaveRequest,
    LeaveType,
    PublicHoliday,
    Shift,
    ShiftAssignment,
)


# ============================================================ HRM Overview (3.1)
@login_required
def hrm_overview(request):
    tenant = request.tenant
    stats = {"employees": 0, "new_this_month": 0, "on_leave_today": 0,
             "present_today": 0, "absent_today": 0}
    pending_requests, upcoming_holidays = [], []
    if tenant is not None:
        today = timezone.localdate()
        employees = EmployeeProfile.objects.filter(tenant=tenant)
        stats["employees"] = employees.count()
        stats["new_this_month"] = employees.filter(
            created_at__year=today.year, created_at__month=today.month).count()
        stats["on_leave_today"] = LeaveRequest.objects.filter(
            tenant=tenant, status="approved", start_date__lte=today, end_date__gte=today).count()
        att_today = AttendanceRecord.objects.filter(tenant=tenant, date=today)
        stats["present_today"] = att_today.filter(status="present").count()
        stats["absent_today"] = att_today.filter(status="absent").count()
        pending_requests = (LeaveRequest.objects.filter(tenant=tenant, status="pending")
                            .select_related("employee__party", "leave_type")
                            .order_by("start_date")[:10])
        upcoming_holidays = (PublicHoliday.objects.filter(tenant=tenant, date__gte=today)
                             .order_by("date")[:5])
    return render(request, "hrm/hrm_overview.html", {
        "stats": stats,
        "pending_requests": pending_requests,
        "upcoming_holidays": upcoming_holidays,
    })


# ============================================================ Designations (3.2)
@login_required
def designation_list(request):
    return crud_list(
        request,
        Designation.objects.filter(tenant=request.tenant).select_related("department")
        .annotate(employee_count=Count("employees")).order_by("name"),
        "hrm/designation_list.html",
        search_fields=["name", "grade", "department__name"],
        filters=[("is_active", "is_active", False), ("department", "department_id", True)],
        extra_context={"departments": OrgUnit.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def designation_create(request):
    return crud_create(request, form_class=DesignationForm, template="hrm/designation_form.html",
                       success_url="hrm:designation_list")


@login_required
def designation_detail(request, pk):
    obj = get_object_or_404(Designation.objects.select_related("department"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/designation_detail.html", {
        "obj": obj,
        "employees": EmployeeProfile.objects.filter(tenant=request.tenant, designation=obj)
        .select_related("party")[:50],
        "employee_count": EmployeeProfile.objects.filter(tenant=request.tenant, designation=obj).count(),
    })


@login_required
def designation_edit(request, pk):
    return crud_edit(request, model=Designation, pk=pk, form_class=DesignationForm,
                     template="hrm/designation_form.html", success_url="hrm:designation_list")


@login_required
@require_POST
def designation_delete(request, pk):
    return crud_delete(request, model=Designation, pk=pk, success_url="hrm:designation_list")


# ============================================================ Employee Profiles (3.1)
@login_required
def employee_list(request):
    return crud_list(
        request,
        EmployeeProfile.objects.filter(tenant=request.tenant)
        .select_related("party", "employment", "employment__org_unit", "designation"),
        "hrm/employee_list.html",
        search_fields=["number", "party__name", "personal_email", "mobile"],
        filters=[("employee_type", "employee_type", False),
                 ("designation", "designation_id", True),
                 ("status", "employment__status", False)],
        extra_context={"employee_type_choices": EmployeeProfile.EMPLOYEE_TYPE_CHOICES,
                       "designations": Designation.objects.filter(tenant=request.tenant).order_by("name"),
                       "status_choices": Employment.STATUS_CHOICES},
    )


@login_required
def employee_create(request):
    return crud_create(request, form_class=EmployeeProfileForm, template="hrm/employee_form.html",
                       success_url="hrm:employee_list")


@login_required
def employee_detail(request, pk):
    obj = get_object_or_404(
        EmployeeProfile.objects.select_related(
            "party", "employment", "employment__org_unit", "employment__manager", "designation"),
        pk=pk, tenant=request.tenant)
    year = timezone.localdate().year
    allocations = (LeaveAllocation.objects.filter(tenant=request.tenant, employee=obj, year=year)
                   .select_related("leave_type"))
    balances = [{
        "leave_type": a.leave_type,
        "allocated": a.allocated_days,
        "used": a.used_days,
        "balance": a.balance,
    } for a in allocations]
    return render(request, "hrm/employee_detail.html", {
        "obj": obj,
        "year": year,
        "balances": balances,
        "recent_attendance": AttendanceRecord.objects.filter(tenant=request.tenant, employee=obj)
        .select_related("shift").order_by("-date")[:10],
        "current_shift": ShiftAssignment.objects.filter(tenant=request.tenant, employee=obj)
        .select_related("shift").order_by("-effective_from").first(),
        "recent_leaves": LeaveRequest.objects.filter(tenant=request.tenant, employee=obj)
        .select_related("leave_type").order_by("-start_date")[:10],
    })


@login_required
def employee_edit(request, pk):
    return crud_edit(request, model=EmployeeProfile, pk=pk, form_class=EmployeeProfileForm,
                     template="hrm/employee_form.html", success_url="hrm:employee_list")


@login_required
@require_POST
def employee_delete(request, pk):
    obj = get_object_or_404(
        EmployeeProfile.objects.select_related("employment"), pk=pk, tenant=request.tenant)
    # Guard: don't delete an actively-employed person — terminate the Employment first.
    if obj.employment_id and obj.employment.status == "active":
        messages.error(request, "Cannot delete an active employee — set their employment to "
                                "terminated/on-leave first.")
        return redirect("hrm:employee_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Employee deleted.")
    return redirect("hrm:employee_list")


# ============================================================ Leave Types (3.10)
@login_required
def leavetype_list(request):
    return crud_list(
        request,
        LeaveType.objects.filter(tenant=request.tenant),
        "hrm/leavetype_list.html",
        search_fields=["name", "code"],
        filters=[("is_active", "is_active", False), ("is_paid", "is_paid", False),
                 ("accrual_rule", "accrual_rule", False)],
        extra_context={"accrual_choices": LeaveType.ACCRUAL_CHOICES},
    )


@login_required
def leavetype_create(request):
    return crud_create(request, form_class=LeaveTypeForm, template="hrm/leavetype_form.html",
                       success_url="hrm:leavetype_list")


@login_required
def leavetype_detail(request, pk):
    obj = get_object_or_404(LeaveType, pk=pk, tenant=request.tenant)
    year = timezone.localdate().year
    return render(request, "hrm/leavetype_detail.html", {
        "obj": obj,
        "year": year,
        "allocation_count": LeaveAllocation.objects.filter(
            tenant=request.tenant, leave_type=obj, year=year).count(),
        "request_count": LeaveRequest.objects.filter(tenant=request.tenant, leave_type=obj).count(),
    })


@login_required
def leavetype_edit(request, pk):
    return crud_edit(request, model=LeaveType, pk=pk, form_class=LeaveTypeForm,
                     template="hrm/leavetype_form.html", success_url="hrm:leavetype_list")


@login_required
@require_POST
def leavetype_delete(request, pk):
    obj = get_object_or_404(LeaveType, pk=pk, tenant=request.tenant)
    # Guard: a leave type still referenced by allocations or requests cannot be removed.
    if (LeaveAllocation.objects.filter(tenant=request.tenant, leave_type=obj).exists()
            or LeaveRequest.objects.filter(tenant=request.tenant, leave_type=obj).exists()):
        messages.error(request, "Cannot delete a leave type that has allocations or requests. "
                                "Deactivate it instead.")
        return redirect("hrm:leavetype_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Leave type deleted.")
    return redirect("hrm:leavetype_list")


# ============================================================ Leave Allocations (3.10)
@login_required
def leaveallocation_list(request):
    return crud_list(
        request,
        LeaveAllocation.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "leave_type"),
        "hrm/leaveallocation_list.html",
        search_fields=["number", "employee__party__name", "leave_type__name"],
        filters=[("status", "status", False), ("year", "year", True),
                 ("employee", "employee_id", True), ("leave_type", "leave_type_id", True)],
        extra_context={"status_choices": LeaveAllocation.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name"),
                       "leave_types": LeaveType.objects.filter(tenant=request.tenant).order_by("name"),
                       "current_year": timezone.localdate().year},
    )


@login_required
def leaveallocation_create(request):
    return crud_create(request, form_class=LeaveAllocationForm,
                       template="hrm/leaveallocation_form.html", success_url="hrm:leaveallocation_list")


@login_required
def leaveallocation_detail(request, pk):
    obj = get_object_or_404(
        LeaveAllocation.objects.select_related("employee__party", "leave_type"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/leaveallocation_detail.html", {
        "obj": obj,
        "requests": LeaveRequest.objects.filter(
            tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type,
            start_date__year=obj.year).order_by("-start_date")[:20],
    })


@login_required
def leaveallocation_edit(request, pk):
    return crud_edit(request, model=LeaveAllocation, pk=pk, form_class=LeaveAllocationForm,
                     template="hrm/leaveallocation_form.html", success_url="hrm:leaveallocation_list")


@login_required
@require_POST
def leaveallocation_delete(request, pk):
    return crud_delete(request, model=LeaveAllocation, pk=pk, success_url="hrm:leaveallocation_list")


# ============================================================ Leave Requests (3.10)
@login_required
def leaverequest_list(request):
    return crud_list(
        request,
        LeaveRequest.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "leave_type", "approver"),
        "hrm/leaverequest_list.html",
        search_fields=["number", "employee__party__name", "reason"],
        filters=[("status", "status", False), ("employee", "employee_id", True),
                 ("leave_type", "leave_type_id", True)],
        extra_context={"status_choices": LeaveRequest.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name"),
                       "leave_types": LeaveType.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def leaverequest_create(request):
    return crud_create(request, form_class=LeaveRequestForm, template="hrm/leaverequest_form.html",
                       success_url="hrm:leaverequest_list")


@login_required
def leaverequest_detail(request, pk):
    obj = get_object_or_404(
        LeaveRequest.objects.select_related("employee__party", "leave_type", "approver"),
        pk=pk, tenant=request.tenant)
    allocation = LeaveAllocation.objects.filter(
        tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type,
        year=obj.start_date.year).first()
    return render(request, "hrm/leaverequest_detail.html", {
        "obj": obj,
        "allocation": allocation,
    })


@login_required
def leaverequest_edit(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    # Only an open (draft/pending) request is editable — a decided one is locked.
    if obj.status not in LeaveRequest.OPEN_STATUSES:
        messages.error(request, "Only a draft or pending leave request can be edited.")
        return redirect("hrm:leaverequest_detail", pk=obj.pk)
    return crud_edit(request, model=LeaveRequest, pk=pk, form_class=LeaveRequestForm,
                     template="hrm/leaverequest_form.html", success_url="hrm:leaverequest_list")


@login_required
@require_POST
def leaverequest_delete(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    if obj.status in ("approved", "rejected"):
        messages.error(request, "A decided leave request cannot be deleted — cancel it instead.")
        return redirect("hrm:leaverequest_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Leave request deleted.")
    return redirect("hrm:leaverequest_list")


@login_required
@require_POST
def leaverequest_submit(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Leave request {obj.number} submitted for approval.")
    return redirect("hrm:leaverequest_detail", pk=obj.pk)


@tenant_admin_required  # approving leave is a privileged manager/admin action, not self-service
@require_POST
def leaverequest_approve(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "approved"
        obj.approver = request.user
        obj.approved_at = timezone.now()
        obj.save(update_fields=["status", "approver", "approved_at", "updated_at"])
        # Reflect the approval on any existing attendance rows in the leave window.
        AttendanceRecord.objects.filter(
            tenant=request.tenant, employee=obj.employee,
            date__gte=obj.start_date, date__lte=obj.end_date).update(status="on_leave")
        write_audit_log(request.user, obj, "update", {"action": "approve"})
        messages.success(request, f"Leave request {obj.number} approved.")
    return redirect("hrm:leaverequest_detail", pk=obj.pk)


@tenant_admin_required  # rejecting leave is a privileged manager/admin action
@require_POST
def leaverequest_reject(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approver = request.user
        obj.rejected_reason = request.POST.get("rejected_reason", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "rejected_reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Leave request {obj.number} rejected.")
    return redirect("hrm:leaverequest_detail", pk=obj.pk)


@login_required
@require_POST
def leaverequest_cancel(request, pk):
    obj = get_object_or_404(LeaveRequest, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "pending", "approved"):
        obj.status = "cancelled"
        obj.cancelled_reason = request.POST.get("cancelled_reason", "").strip()[:2000]
        obj.save(update_fields=["status", "cancelled_reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Leave request {obj.number} cancelled.")
    return redirect("hrm:leaverequest_detail", pk=obj.pk)


# ============================================================ Public Holidays (3.12)
@login_required
def publicholiday_list(request):
    qs = PublicHoliday.objects.filter(tenant=request.tenant)
    year = request.GET.get("year", "").strip()
    if year.isdigit():
        qs = qs.filter(date__year=int(year))
    years = sorted({d.year for d in PublicHoliday.objects.filter(tenant=request.tenant)
                    .values_list("date", flat=True)}, reverse=True)
    today_year = timezone.localdate().year
    for y in (today_year, today_year + 1):
        if y not in years:
            years.append(y)
    years = sorted(set(years), reverse=True)
    return crud_list(
        request, qs, "hrm/publicholiday_list.html",
        search_fields=["name"],
        filters=[("is_optional", "is_optional", False)],
        extra_context={"year_choices": years},
    )


@login_required
def publicholiday_create(request):
    return crud_create(request, form_class=PublicHolidayForm,
                       template="hrm/publicholiday_form.html", success_url="hrm:publicholiday_list")


@login_required
def publicholiday_detail(request, pk):
    obj = get_object_or_404(PublicHoliday, pk=pk, tenant=request.tenant)
    return render(request, "hrm/publicholiday_detail.html", {"obj": obj})


@login_required
def publicholiday_edit(request, pk):
    return crud_edit(request, model=PublicHoliday, pk=pk, form_class=PublicHolidayForm,
                     template="hrm/publicholiday_form.html", success_url="hrm:publicholiday_list")


@login_required
@require_POST
def publicholiday_delete(request, pk):
    return crud_delete(request, model=PublicHoliday, pk=pk, success_url="hrm:publicholiday_list")


# ============================================================ Shifts (3.9)
@login_required
def shift_list(request):
    return crud_list(
        request,
        Shift.objects.filter(tenant=request.tenant)
        .annotate(assignment_count=Count("assignments")).order_by("name"),
        "hrm/shift_list.html",
        search_fields=["name"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def shift_create(request):
    return crud_create(request, form_class=ShiftForm, template="hrm/shift_form.html",
                       success_url="hrm:shift_list")


@login_required
def shift_detail(request, pk):
    obj = get_object_or_404(Shift, pk=pk, tenant=request.tenant)
    return render(request, "hrm/shift_detail.html", {
        "obj": obj,
        "assignments": ShiftAssignment.objects.filter(tenant=request.tenant, shift=obj)
        .select_related("employee__party").order_by("-effective_from")[:50],
    })


@login_required
def shift_edit(request, pk):
    return crud_edit(request, model=Shift, pk=pk, form_class=ShiftForm,
                     template="hrm/shift_form.html", success_url="hrm:shift_list")


@login_required
@require_POST
def shift_delete(request, pk):
    obj = get_object_or_404(Shift, pk=pk, tenant=request.tenant)
    if ShiftAssignment.objects.filter(tenant=request.tenant, shift=obj).exists():
        messages.error(request, "Cannot delete a shift that has assignments. Deactivate it instead.")
        return redirect("hrm:shift_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Shift deleted.")
    return redirect("hrm:shift_list")


# ============================================================ Shift Assignments (3.9)
@login_required
def shiftassignment_list(request):
    return crud_list(
        request,
        ShiftAssignment.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "shift"),
        "hrm/shiftassignment_list.html",
        search_fields=["employee__party__name", "shift__name"],
        filters=[("shift", "shift_id", True), ("employee", "employee_id", True)],
        extra_context={"shifts": Shift.objects.filter(tenant=request.tenant).order_by("name"),
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def shiftassignment_create(request):
    return crud_create(request, form_class=ShiftAssignmentForm,
                       template="hrm/shiftassignment_form.html", success_url="hrm:shiftassignment_list")


@login_required
def shiftassignment_detail(request, pk):
    obj = get_object_or_404(
        ShiftAssignment.objects.select_related("employee__party", "shift"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/shiftassignment_detail.html", {"obj": obj})


@login_required
def shiftassignment_edit(request, pk):
    return crud_edit(request, model=ShiftAssignment, pk=pk, form_class=ShiftAssignmentForm,
                     template="hrm/shiftassignment_form.html", success_url="hrm:shiftassignment_list")


@login_required
@require_POST
def shiftassignment_delete(request, pk):
    return crud_delete(request, model=ShiftAssignment, pk=pk, success_url="hrm:shiftassignment_list")


# ============================================================ Attendance (3.9)
@login_required
def attendancerecord_list(request):
    qs = (AttendanceRecord.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "shift"))
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return crud_list(
        request, qs, "hrm/attendancerecord_list.html",
        search_fields=["number", "employee__party__name", "notes"],
        filters=[("status", "status", False), ("source", "source", False),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": AttendanceRecord.STATUS_CHOICES,
                       "source_choices": AttendanceRecord.SOURCE_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
        per_page=30,
    )


@login_required
def attendancerecord_create(request):
    return crud_create(request, form_class=AttendanceRecordForm,
                       template="hrm/attendancerecord_form.html", success_url="hrm:attendancerecord_list")


@login_required
def attendancerecord_detail(request, pk):
    obj = get_object_or_404(
        AttendanceRecord.objects.select_related("employee__party", "shift"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendancerecord_detail.html", {"obj": obj})


@login_required
def attendancerecord_edit(request, pk):
    return crud_edit(request, model=AttendanceRecord, pk=pk, form_class=AttendanceRecordForm,
                     template="hrm/attendancerecord_form.html", success_url="hrm:attendancerecord_list")


@login_required
@require_POST
def attendancerecord_delete(request, pk):
    return crud_delete(request, model=AttendanceRecord, pk=pk, success_url="hrm:attendancerecord_list")
