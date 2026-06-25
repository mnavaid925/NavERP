"""HRM (Module 3) views — function-based, ``@login_required``, tenant-scoped.

Full CRUD for the nine HRM models via the shared ``apps.core.crud`` helpers (search +
int-FK-guarded filters + windowed pagination + audit), plus:
  * an HRM overview (3.1) with headcount / today's attendance / pending-leave / holiday widgets,
  * a rich employee profile (leave balances, recent attendance, current shift),
  * the leave-request workflow actions (submit / approve / reject / cancel),
  * delete guards on records that anchor others (active employee, in-use leave type/shift).
"""
from datetime import date as _date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import (Count, DecimalField, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.models import Employment, OrgUnit
from apps.core.utils import write_audit_log

from .services import (
    compute_leave_encashment,
    generate_clearance_checklist,
    generate_tasks_from_template,
)

from .forms import (
    AssetAllocationForm,
    AttendanceRecordForm,
    ClearanceItemForm,
    DesignationForm,
    EmployeeProfileForm,
    ExitInterviewForm,
    FinalSettlementForm,
    LeaveAllocationForm,
    LeaveRequestForm,
    LeaveTypeForm,
    OnboardingDocumentForm,
    OnboardingProgramForm,
    OnboardingTaskForm,
    OnboardingTemplateForm,
    OnboardingTemplateTaskForm,
    OrientationSessionForm,
    PublicHolidayForm,
    SeparationCaseForm,
    ShiftAssignmentForm,
    ShiftForm,
)
from .models import (
    PHASE_CHOICES,
    TASK_CATEGORY_CHOICES,
    AssetAllocation,
    AttendanceRecord,
    ClearanceItem,
    Designation,
    EmployeeProfile,
    ExitInterview,
    FinalSettlement,
    LeaveAllocation,
    LeaveRequest,
    LeaveType,
    OnboardingDocument,
    OnboardingProgram,
    OnboardingTask,
    OnboardingTemplate,
    OnboardingTemplateTask,
    OrientationSession,
    PublicHoliday,
    SeparationCase,
    Shift,
    ShiftAssignment,
)


_DEC = DecimalField(max_digits=7, decimal_places=2)


def _parse_iso_date(value):
    """Return a date for a ``YYYY-MM-DD`` string, or None for blank/malformed input."""
    try:
        return _date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def _used_days_subquery():
    """Correlated sub-select of approved leave-days for a LeaveAllocation's
    (tenant, employee, leave_type, start-year) window — pushes the per-row aggregate the
    ``LeaveAllocation.used_days`` property would otherwise run into one SQL pass."""
    inner = (LeaveRequest.objects
             .filter(tenant=OuterRef("tenant"), employee=OuterRef("employee"),
                     leave_type=OuterRef("leave_type"), status="approved",
                     start_date__year=OuterRef("year"))
             .values("employee").annotate(s=Sum("days")).values("s"))
    return Coalesce(Subquery(inner, output_field=_DEC), Decimal("0"), output_field=_DEC)


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
        "hrm/designation/list.html",
        search_fields=["name", "grade", "department__name"],
        filters=[("is_active", "is_active", False), ("department", "department_id", True)],
        extra_context={"departments": OrgUnit.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def designation_create(request):
    return crud_create(request, form_class=DesignationForm, template="hrm/designation/form.html",
                       success_url="hrm:designation_list")


@login_required
def designation_detail(request, pk):
    obj = get_object_or_404(Designation.objects.select_related("department"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/designation/detail.html", {
        "obj": obj,
        "employees": EmployeeProfile.objects.filter(tenant=request.tenant, designation=obj)
        .select_related("party")[:50],
        "employee_count": EmployeeProfile.objects.filter(tenant=request.tenant, designation=obj).count(),
    })


@login_required
def designation_edit(request, pk):
    return crud_edit(request, model=Designation, pk=pk, form_class=DesignationForm,
                     template="hrm/designation/form.html", success_url="hrm:designation_list")


@login_required
@require_POST
def designation_delete(request, pk):
    obj = get_object_or_404(Designation, pk=pk, tenant=request.tenant)
    # Guard: deleting a designation in use would silently de-designate employees (SET_NULL).
    if EmployeeProfile.objects.filter(tenant=request.tenant, designation=obj).exists():
        messages.error(request, "Cannot delete a designation assigned to employees. "
                                "Deactivate it instead.")
        return redirect("hrm:designation_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Designation deleted.")
    return redirect("hrm:designation_list")


# ============================================================ Employee Profiles (3.1)
@login_required
def employee_list(request):
    return crud_list(
        request,
        EmployeeProfile.objects.filter(tenant=request.tenant)
        .select_related("party", "employment", "employment__org_unit", "designation"),
        "hrm/employee/list.html",
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
    return crud_create(request, form_class=EmployeeProfileForm, template="hrm/employee/form.html",
                       success_url="hrm:employee_list")


@login_required
def employee_detail(request, pk):
    obj = get_object_or_404(
        EmployeeProfile.objects.select_related(
            "party", "employment", "employment__org_unit", "employment__manager", "designation"),
        pk=pk, tenant=request.tenant)
    year = timezone.localdate().year
    allocations = (LeaveAllocation.objects.filter(tenant=request.tenant, employee=obj, year=year)
                   .select_related("leave_type").annotate(used_days_db=_used_days_subquery()))
    balances = [{
        "leave_type": a.leave_type,
        "allocated": a.allocated_days,
        "used": a.used_days_db,
        "balance": (a.allocated_days or Decimal("0")) - a.used_days_db,
    } for a in allocations]
    return render(request, "hrm/employee/detail.html", {
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
                     template="hrm/employee/form.html", success_url="hrm:employee_list")


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
        "hrm/leave/type_list.html",
        search_fields=["name", "code"],
        filters=[("is_active", "is_active", False), ("is_paid", "is_paid", False),
                 ("accrual_rule", "accrual_rule", False)],
        extra_context={"accrual_choices": LeaveType.ACCRUAL_CHOICES},
    )


@login_required
def leavetype_create(request):
    return crud_create(request, form_class=LeaveTypeForm, template="hrm/leave/type_form.html",
                       success_url="hrm:leavetype_list")


@login_required
def leavetype_detail(request, pk):
    obj = get_object_or_404(LeaveType, pk=pk, tenant=request.tenant)
    year = timezone.localdate().year
    return render(request, "hrm/leave/type_detail.html", {
        "obj": obj,
        "year": year,
        "allocation_count": LeaveAllocation.objects.filter(
            tenant=request.tenant, leave_type=obj, year=year).count(),
        "request_count": LeaveRequest.objects.filter(tenant=request.tenant, leave_type=obj).count(),
    })


@login_required
def leavetype_edit(request, pk):
    return crud_edit(request, model=LeaveType, pk=pk, form_class=LeaveTypeForm,
                     template="hrm/leave/type_form.html", success_url="hrm:leavetype_list")


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
    used_subq = _used_days_subquery()
    return crud_list(
        request,
        LeaveAllocation.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "leave_type")
        .annotate(used_days_db=used_subq)
        .annotate(balance_db=ExpressionWrapper(F("allocated_days") - F("used_days_db"), output_field=_DEC)),
        "hrm/leave/allocation_list.html",
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
                       template="hrm/leave/allocation_form.html", success_url="hrm:leaveallocation_list")


@login_required
def leaveallocation_detail(request, pk):
    obj = get_object_or_404(
        LeaveAllocation.objects.select_related("employee__party", "leave_type"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/leave/allocation_detail.html", {
        "obj": obj,
        "requests": LeaveRequest.objects.filter(
            tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type,
            start_date__year=obj.year).order_by("-start_date")[:20],
    })


@login_required
def leaveallocation_edit(request, pk):
    return crud_edit(request, model=LeaveAllocation, pk=pk, form_class=LeaveAllocationForm,
                     template="hrm/leave/allocation_form.html", success_url="hrm:leaveallocation_list")


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
        "hrm/leave/request_list.html",
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
    return crud_create(request, form_class=LeaveRequestForm, template="hrm/leave/request_form.html",
                       success_url="hrm:leaverequest_list")


@login_required
def leaverequest_detail(request, pk):
    obj = get_object_or_404(
        LeaveRequest.objects.select_related("employee__party", "leave_type", "approver"),
        pk=pk, tenant=request.tenant)
    allocation = LeaveAllocation.objects.filter(
        tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type,
        year=obj.start_date.year).first()
    return render(request, "hrm/leave/request_detail.html", {
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
                     template="hrm/leave/request_form.html", success_url="hrm:leaverequest_list")


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
        touched = AttendanceRecord.objects.filter(
            tenant=request.tenant, employee=obj.employee,
            date__gte=obj.start_date, date__lte=obj.end_date).update(status="on_leave")
        write_audit_log(request.user, obj, "update", {
            "action": "approve",
            "attendance_set_on_leave": f"{obj.start_date}..{obj.end_date} ({touched} rows)"})
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
        was_approved = obj.status == "approved"
        with transaction.atomic():
            obj.status = "cancelled"
            obj.cancelled_reason = request.POST.get("cancelled_reason", "").strip()[:2000]
            obj.save(update_fields=["status", "cancelled_reason", "updated_at"])
            # Undo the on-leave marking that approval applied, so attendance reports stay correct
            # (inverse of leaverequest_approve). Only touch rows we put into on_leave.
            reverted = 0
            if was_approved:
                reverted = AttendanceRecord.objects.filter(
                    tenant=request.tenant, employee=obj.employee, status="on_leave",
                    date__gte=obj.start_date, date__lte=obj.end_date).update(status="present")
        write_audit_log(request.user, obj, "update", {
            "action": "cancel", "attendance_reverted_rows": reverted})
        messages.success(request, f"Leave request {obj.number} cancelled.")
    return redirect("hrm:leaverequest_detail", pk=obj.pk)


# ============================================================ Public Holidays (3.12)
@login_required
def publicholiday_list(request):
    qs = PublicHoliday.objects.filter(tenant=request.tenant)
    year = request.GET.get("year", "").strip()
    if year.isdigit():
        qs = qs.filter(date__year=int(year))
    years = sorted(PublicHoliday.objects.filter(tenant=request.tenant)
                   .values_list("date__year", flat=True).distinct().order_by(), reverse=True)
    today_year = timezone.localdate().year
    for y in (today_year, today_year + 1):
        if y not in years:
            years.append(y)
    years = sorted(set(years), reverse=True)
    return crud_list(
        request, qs, "hrm/holiday/publicholiday_list.html",
        search_fields=["name"],
        filters=[("is_optional", "is_optional", False)],
        extra_context={"year_choices": years},
    )


@login_required
def publicholiday_create(request):
    return crud_create(request, form_class=PublicHolidayForm,
                       template="hrm/holiday/publicholiday_form.html", success_url="hrm:publicholiday_list")


@login_required
def publicholiday_detail(request, pk):
    obj = get_object_or_404(PublicHoliday, pk=pk, tenant=request.tenant)
    return render(request, "hrm/holiday/publicholiday_detail.html", {"obj": obj})


@login_required
def publicholiday_edit(request, pk):
    return crud_edit(request, model=PublicHoliday, pk=pk, form_class=PublicHolidayForm,
                     template="hrm/holiday/publicholiday_form.html", success_url="hrm:publicholiday_list")


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
        "hrm/attendance/shift_list.html",
        search_fields=["name"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def shift_create(request):
    return crud_create(request, form_class=ShiftForm, template="hrm/attendance/shift_form.html",
                       success_url="hrm:shift_list")


@login_required
def shift_detail(request, pk):
    obj = get_object_or_404(Shift, pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/shift_detail.html", {
        "obj": obj,
        "assignments": ShiftAssignment.objects.filter(tenant=request.tenant, shift=obj)
        .select_related("employee__party").order_by("-effective_from")[:50],
    })


@login_required
def shift_edit(request, pk):
    return crud_edit(request, model=Shift, pk=pk, form_class=ShiftForm,
                     template="hrm/attendance/shift_form.html", success_url="hrm:shift_list")


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
        "hrm/attendance/shiftassignment_list.html",
        search_fields=["employee__party__name", "shift__name"],
        filters=[("shift", "shift_id", True), ("employee", "employee_id", True)],
        extra_context={"shifts": Shift.objects.filter(tenant=request.tenant).order_by("name"),
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def shiftassignment_create(request):
    return crud_create(request, form_class=ShiftAssignmentForm,
                       template="hrm/attendance/shiftassignment_form.html", success_url="hrm:shiftassignment_list")


@login_required
def shiftassignment_detail(request, pk):
    obj = get_object_or_404(
        ShiftAssignment.objects.select_related("employee__party", "shift"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/shiftassignment_detail.html", {"obj": obj})


@login_required
def shiftassignment_edit(request, pk):
    return crud_edit(request, model=ShiftAssignment, pk=pk, form_class=ShiftAssignmentForm,
                     template="hrm/attendance/shiftassignment_form.html", success_url="hrm:shiftassignment_list")


@login_required
@require_POST
def shiftassignment_delete(request, pk):
    return crud_delete(request, model=ShiftAssignment, pk=pk, success_url="hrm:shiftassignment_list")


# ============================================================ Attendance (3.9)
@login_required
def attendancerecord_list(request):
    qs = (AttendanceRecord.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "shift"))
    # Parse the date-range GET params defensively — a malformed string passed straight to
    # .filter(date__gte=...) would raise a 500 (ValueError/DataError); ignore bad input instead.
    date_from = _parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = _parse_iso_date(request.GET.get("date_to", "").strip())
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return crud_list(
        request, qs, "hrm/attendance/record_list.html",
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
                       template="hrm/attendance/record_form.html", success_url="hrm:attendancerecord_list")


@login_required
def attendancerecord_detail(request, pk):
    obj = get_object_or_404(
        AttendanceRecord.objects.select_related("employee__party", "shift"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/record_detail.html", {"obj": obj})


@login_required
def attendancerecord_edit(request, pk):
    return crud_edit(request, model=AttendanceRecord, pk=pk, form_class=AttendanceRecordForm,
                     template="hrm/attendance/record_form.html", success_url="hrm:attendancerecord_list")


@login_required
@require_POST
def attendancerecord_delete(request, pk):
    return crud_delete(request, model=AttendanceRecord, pk=pk, success_url="hrm:attendancerecord_list")


# ============================================================ Onboarding Templates (3.3)
@login_required
def onboardingtemplate_list(request):
    return crud_list(
        request,
        OnboardingTemplate.objects.filter(tenant=request.tenant).select_related("designation")
        .annotate(task_count=Count("template_tasks")).order_by("name"),
        "hrm/onboarding/template_list.html",
        search_fields=["number", "name", "designation__name"],
        filters=[("is_active", "is_active", False), ("designation", "designation_id", True)],
        extra_context={"designations": Designation.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def onboardingtemplate_create(request):
    return crud_create(request, form_class=OnboardingTemplateForm,
                       template="hrm/onboarding/template_form.html",
                       success_url="hrm:onboardingtemplate_list")


@login_required
def onboardingtemplate_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTemplate.objects.select_related("designation"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/template_detail.html", {
        "obj": obj,
        "tasks": obj.template_tasks.order_by("phase", "order", "title"),
        "program_count": OnboardingProgram.objects.filter(tenant=request.tenant, template=obj).count(),
    })


@login_required
def onboardingtemplate_edit(request, pk):
    return crud_edit(request, model=OnboardingTemplate, pk=pk, form_class=OnboardingTemplateForm,
                     template="hrm/onboarding/template_form.html",
                     success_url="hrm:onboardingtemplate_list")


@login_required
@require_POST
def onboardingtemplate_delete(request, pk):
    obj = get_object_or_404(OnboardingTemplate, pk=pk, tenant=request.tenant)
    # Guard: a template still referenced by programs is kept (SET_NULL would orphan the link).
    if OnboardingProgram.objects.filter(tenant=request.tenant, template=obj).exists():
        messages.error(request, "Cannot delete a template that has onboarding programs. "
                                "Deactivate it instead.")
        return redirect("hrm:onboardingtemplate_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Onboarding template deleted.")
    return redirect("hrm:onboardingtemplate_list")


# ============================================================ Onboarding Template Tasks (3.3)
@login_required
def onboardingtemplatetask_list(request):
    return crud_list(
        request,
        OnboardingTemplateTask.objects.filter(tenant=request.tenant).select_related("template"),
        "hrm/onboarding/templatetask_list.html",
        search_fields=["title", "description", "template__name"],
        filters=[("template", "template_id", True), ("phase", "phase", False),
                 ("task_category", "task_category", False)],
        extra_context={"templates": OnboardingTemplate.objects.filter(tenant=request.tenant).order_by("name"),
                       "phase_choices": PHASE_CHOICES,
                       "category_choices": TASK_CATEGORY_CHOICES},
    )


@login_required
def onboardingtemplatetask_create(request):
    return crud_create(request, form_class=OnboardingTemplateTaskForm,
                       template="hrm/onboarding/templatetask_form.html",
                       success_url="hrm:onboardingtemplatetask_list")


@login_required
def onboardingtemplatetask_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTemplateTask.objects.select_related("template"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/templatetask_detail.html", {"obj": obj})


@login_required
def onboardingtemplatetask_edit(request, pk):
    return crud_edit(request, model=OnboardingTemplateTask, pk=pk,
                     form_class=OnboardingTemplateTaskForm,
                     template="hrm/onboarding/templatetask_form.html",
                     success_url="hrm:onboardingtemplatetask_list")


@login_required
@require_POST
def onboardingtemplatetask_delete(request, pk):
    return crud_delete(request, model=OnboardingTemplateTask, pk=pk,
                       success_url="hrm:onboardingtemplatetask_list")


# ============================================================ Onboarding Programs (3.3)
@login_required
def onboardingprogram_list(request):
    return crud_list(
        request,
        OnboardingProgram.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "buddy__party", "template")
        .annotate(tasks_total=Count("tasks", distinct=True),
                  tasks_done=Count("tasks", filter=Q(tasks__status__in=("completed", "skipped")),
                                   distinct=True))
        .order_by("-start_date"),  # explicit — aggregate annotation drops Meta ordering (pagination guard)
        "hrm/onboarding/program_list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False), ("employee", "employee_id", True)],
        extra_context={"status_choices": OnboardingProgram.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def onboardingprogram_create(request):
    return crud_create(request, form_class=OnboardingProgramForm,
                       template="hrm/onboarding/program_form.html",
                       success_url="hrm:onboardingprogram_list")


@login_required
def onboardingprogram_detail(request, pk):
    obj = get_object_or_404(
        OnboardingProgram.objects.select_related("employee__party", "buddy__party", "template"),
        pk=pk, tenant=request.tenant)
    tasks = list(obj.tasks.select_related("assignee").order_by("phase", "order", "due_date", "title"))
    # Group tasks by phase, preserving the canonical PHASE_CHOICES order.
    phase_labels = dict(PHASE_CHOICES)
    grouped = {}
    for t in tasks:
        grouped.setdefault(t.phase, []).append(t)
    tasks_by_phase = [{"phase": p, "label": phase_labels.get(p, p), "tasks": grouped[p]}
                      for p, _ in PHASE_CHOICES if p in grouped]
    # Progress from the already-fetched list (matches OnboardingProgram.progress) — avoids the two
    # extra COUNT queries the model property would run on a page that has the tasks in hand.
    done = sum(1 for t in tasks if t.status in ("completed", "skipped"))
    progress = int(round(done / len(tasks) * 100)) if tasks else 0
    return render(request, "hrm/onboarding/program_detail.html", {
        "obj": obj,
        "progress": progress,
        "tasks_by_phase": tasks_by_phase,
        "task_count": len(tasks),
        "documents": obj.documents.order_by("document_type", "title"),
        "assets": obj.assets.order_by("-created_at"),  # sub-table shows issued_at, not issued_by
        "sessions": obj.orientation_sessions.select_related("facilitator").order_by("scheduled_at"),
    })


@login_required
def onboardingprogram_edit(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status in ("completed", "cancelled"):
        messages.error(request, "A completed or cancelled program cannot be edited.")
        return redirect("hrm:onboardingprogram_detail", pk=obj.pk)
    return crud_edit(request, model=OnboardingProgram, pk=pk, form_class=OnboardingProgramForm,
                     template="hrm/onboarding/program_form.html",
                     success_url="hrm:onboardingprogram_list")


@login_required
@require_POST
def onboardingprogram_delete(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    # Only a draft or cancelled program is deletable — an active/completed one has live records.
    if obj.status not in ("draft", "cancelled"):
        messages.error(request, "Only a draft or cancelled program can be deleted. Cancel it first.")
        return redirect("hrm:onboardingprogram_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Onboarding program deleted.")
    return redirect("hrm:onboardingprogram_list")


@login_required
@require_POST
def onboardingprogram_activate(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        with transaction.atomic():
            obj.status = "active"
            obj.save(update_fields=["status", "updated_at"])
            created = generate_tasks_from_template(obj)
        write_audit_log(request.user, obj, "update",
                        {"action": "activate", "tasks_generated": created})
        messages.success(request, f"Onboarding program {obj.number} activated"
                         + (f" — {created} task(s) generated." if created else "."))
        # A program with no template (and so no generated tasks) starts empty — nudge HR to add some.
        if not created and not obj.template_id:
            messages.warning(request, "No template attached — add onboarding tasks manually.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.pk)


@login_required
@require_POST
def onboardingprogram_generate_tasks(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "active"):
        if not obj.template_id:
            messages.error(request, "This program has no template to generate tasks from.")
        else:
            with transaction.atomic():
                created = generate_tasks_from_template(obj)
            write_audit_log(request.user, obj, "update",
                            {"action": "generate_tasks", "tasks_generated": created})
            if created:
                messages.success(request, f"{created} task(s) generated from the template.")
            else:
                messages.info(request, "No new tasks — they were already generated.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.pk)


@tenant_admin_required  # closing out an onboarding is a privileged HR/admin action
@require_POST
def onboardingprogram_complete(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status == "active":
        obj.status = "completed"
        obj.completed_at = timezone.now()
        obj.save(update_fields=["status", "completed_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, f"Onboarding program {obj.number} marked complete.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.pk)


@tenant_admin_required  # cancelling an onboarding is a privileged HR/admin action
@require_POST
def onboardingprogram_cancel(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "active"):
        obj.status = "cancelled"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Onboarding program {obj.number} cancelled.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.pk)


# ============================================================ Onboarding Tasks (3.3)
@login_required
def onboardingtask_list(request):
    return crud_list(
        request,
        OnboardingTask.objects.filter(tenant=request.tenant)
        .select_related("program", "assignee"),  # rows show program.number + assignee.username only
        "hrm/onboarding/task_list.html",
        search_fields=["title", "description", "assignee__username", "program__number"],
        filters=[("program", "program_id", True), ("status", "status", False),
                 ("phase", "phase", False), ("task_category", "task_category", False)],
        extra_context={"status_choices": OnboardingTask.STATUS_CHOICES,
                       "phase_choices": PHASE_CHOICES,
                       "category_choices": TASK_CATEGORY_CHOICES,
                       "programs": OnboardingProgram.objects.filter(tenant=request.tenant)
                       .select_related("employee__party").order_by("-start_date")},
        per_page=30,
    )


@login_required
def onboardingtask_create(request):
    return crud_create(request, form_class=OnboardingTaskForm,
                       template="hrm/onboarding/task_form.html",
                       success_url="hrm:onboardingtask_list")


@login_required
def onboardingtask_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTask.objects.select_related("program__employee__party", "assignee", "completed_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/task_detail.html", {"obj": obj})


@login_required
def onboardingtask_edit(request, pk):
    obj = get_object_or_404(OnboardingTask, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.error(request, "Reopen this task before editing it.")
        return redirect("hrm:onboardingtask_detail", pk=obj.pk)
    return crud_edit(request, model=OnboardingTask, pk=pk, form_class=OnboardingTaskForm,
                     template="hrm/onboarding/task_form.html", success_url="hrm:onboardingtask_list")


@login_required
@require_POST
def onboardingtask_delete(request, pk):
    return crud_delete(request, model=OnboardingTask, pk=pk, success_url="hrm:onboardingtask_list")


@login_required
@require_POST
def onboardingtask_complete(request, pk):
    obj = get_object_or_404(OnboardingTask.objects.select_related("program"), pk=pk, tenant=request.tenant)
    if obj.status != "completed":
        obj.status = "completed"
        obj.completed_at = timezone.now()
        obj.completed_by = request.user
        obj.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, f"Task '{obj.title}' marked complete.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.program_id)


@login_required
@require_POST
def onboardingtask_reopen(request, pk):
    obj = get_object_or_404(OnboardingTask.objects.select_related("program"), pk=pk, tenant=request.tenant)
    if obj.status in ("completed", "skipped"):
        obj.status = "pending"
        obj.completed_at = None
        obj.completed_by = None
        obj.save(update_fields=["status", "completed_at", "completed_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reopen"})
        messages.success(request, f"Task '{obj.title}' reopened.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.program_id)


@login_required
@require_POST
def onboardingtask_skip(request, pk):
    obj = get_object_or_404(OnboardingTask.objects.select_related("program"), pk=pk, tenant=request.tenant)
    if obj.status in ("pending", "in_progress"):
        obj.status = "skipped"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "skip"})
        messages.success(request, f"Task '{obj.title}' skipped.")
    return redirect("hrm:onboardingprogram_detail", pk=obj.program_id)


# ============================================================ Onboarding Documents (3.3)
@login_required
def onboardingdocument_list(request):
    return crud_list(
        request,
        OnboardingDocument.objects.filter(tenant=request.tenant)
        .select_related("program"),  # rows show program.number only
        "hrm/onboarding/document_list.html",
        search_fields=["title", "description", "external_ref", "program__number"],
        filters=[("program", "program_id", True), ("document_type", "document_type", False),
                 ("esign_status", "esign_status", False)],
        extra_context={"type_choices": OnboardingDocument.DOCUMENT_TYPE_CHOICES,
                       "esign_choices": OnboardingDocument.ESIGN_STATUS_CHOICES,
                       "programs": OnboardingProgram.objects.filter(tenant=request.tenant)
                       .select_related("employee__party").order_by("-start_date")},
    )


@login_required
def onboardingdocument_create(request):
    return crud_create(request, form_class=OnboardingDocumentForm,
                       template="hrm/onboarding/document_form.html",
                       success_url="hrm:onboardingdocument_list")


@login_required
def onboardingdocument_detail(request, pk):
    obj = get_object_or_404(
        OnboardingDocument.objects.select_related("program__employee__party"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/document_detail.html", {"obj": obj})


@login_required
def onboardingdocument_edit(request, pk):
    return crud_edit(request, model=OnboardingDocument, pk=pk, form_class=OnboardingDocumentForm,
                     template="hrm/onboarding/document_form.html",
                     success_url="hrm:onboardingdocument_list")


@login_required
@require_POST
def onboardingdocument_delete(request, pk):
    return crud_delete(request, model=OnboardingDocument, pk=pk,
                       success_url="hrm:onboardingdocument_list")


@login_required
@require_POST
def onboardingdocument_mark_signed(request, pk):
    obj = get_object_or_404(OnboardingDocument, pk=pk, tenant=request.tenant)
    # A document that needs no signature can't be "signed" — keeps the e-sign trail meaningful.
    if obj.esign_status == "not_required":
        messages.error(request, "This document does not require a signature.")
    elif obj.esign_status != "signed":
        obj.esign_status = "signed"
        obj.signed_at = timezone.now()
        obj.save(update_fields=["esign_status", "signed_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_signed"})
        messages.success(request, f"Document '{obj.title}' marked signed.")
    return redirect("hrm:onboardingdocument_detail", pk=obj.pk)


# ============================================================ Asset Allocations (3.3)
@login_required
def assetallocation_list(request):
    return crud_list(
        request,
        AssetAllocation.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "program", "issued_by"),
        "hrm/onboarding/assetallocation_list.html",
        search_fields=["number", "asset_name", "serial_number", "asset_tag"],
        filters=[("employee", "employee_id", True), ("status", "status", False),
                 ("asset_category", "asset_category", False)],
        extra_context={"status_choices": AssetAllocation.STATUS_CHOICES,
                       "category_choices": AssetAllocation.ASSET_CATEGORY_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def assetallocation_create(request):
    return crud_create(request, form_class=AssetAllocationForm,
                       template="hrm/onboarding/assetallocation_form.html",
                       success_url="hrm:assetallocation_list")


@login_required
def assetallocation_detail(request, pk):
    obj = get_object_or_404(
        AssetAllocation.objects.select_related("employee__party", "program", "issued_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/assetallocation_detail.html", {"obj": obj})


@login_required
def assetallocation_edit(request, pk):
    return crud_edit(request, model=AssetAllocation, pk=pk, form_class=AssetAllocationForm,
                     template="hrm/onboarding/assetallocation_form.html", success_url="hrm:assetallocation_list")


@login_required
@require_POST
def assetallocation_delete(request, pk):
    obj = get_object_or_404(AssetAllocation, pk=pk, tenant=request.tenant)
    # Guard: an issued asset should be returned before its allocation record is removed.
    if obj.status == "issued":
        messages.error(request, "Return this asset before deleting its allocation.")
        return redirect("hrm:assetallocation_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Asset allocation deleted.")
    return redirect("hrm:assetallocation_list")


@login_required
@require_POST
def assetallocation_issue(request, pk):
    obj = get_object_or_404(AssetAllocation, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "issued"
        obj.issued_at = timezone.now()
        obj.issued_by = request.user
        obj.save(update_fields=["status", "issued_at", "issued_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "issue"})
        messages.success(request, f"Asset {obj.number} issued.")
    return redirect("hrm:assetallocation_detail", pk=obj.pk)


@login_required
@require_POST
def assetallocation_return(request, pk):
    obj = get_object_or_404(AssetAllocation, pk=pk, tenant=request.tenant)
    if obj.status == "issued":
        obj.status = "returned"
        obj.returned_at = timezone.now()
        obj.save(update_fields=["status", "returned_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "return"})
        messages.success(request, f"Asset {obj.number} returned.")
    return redirect("hrm:assetallocation_detail", pk=obj.pk)


# ============================================================ Orientation Sessions (3.3)
@login_required
def orientationsession_list(request):
    return crud_list(
        request,
        OrientationSession.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "program", "facilitator"),
        "hrm/onboarding/orientationsession_list.html",
        search_fields=["title", "location", "facilitator__username", "facilitator_name"],
        filters=[("employee", "employee_id", True), ("session_type", "session_type", False),
                 ("attendance_status", "attendance_status", False)],
        extra_context={"type_choices": OrientationSession.SESSION_TYPE_CHOICES,
                       "attendance_choices": OrientationSession.ATTENDANCE_STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def orientationsession_create(request):
    return crud_create(request, form_class=OrientationSessionForm,
                       template="hrm/onboarding/orientationsession_form.html",
                       success_url="hrm:orientationsession_list")


@login_required
def orientationsession_detail(request, pk):
    obj = get_object_or_404(
        OrientationSession.objects.select_related("employee__party", "program", "facilitator"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/orientationsession_detail.html", {"obj": obj})


@login_required
def orientationsession_edit(request, pk):
    return crud_edit(request, model=OrientationSession, pk=pk, form_class=OrientationSessionForm,
                     template="hrm/onboarding/orientationsession_form.html",
                     success_url="hrm:orientationsession_list")


@login_required
@require_POST
def orientationsession_delete(request, pk):
    return crud_delete(request, model=OrientationSession, pk=pk,
                       success_url="hrm:orientationsession_list")


@login_required
@require_POST
def orientationsession_mark_attended(request, pk):
    obj = get_object_or_404(OrientationSession, pk=pk, tenant=request.tenant)
    # A cancelled session is immutable — don't let attendance be back-filled onto it.
    if obj.attendance_status == "cancelled":
        messages.error(request, "A cancelled session cannot be marked attended.")
    elif obj.attendance_status != "attended":
        obj.attendance_status = "attended"
        obj.save(update_fields=["attendance_status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_attended"})
        messages.success(request, f"Session '{obj.title}' marked attended.")
    return redirect("hrm:orientationsession_detail", pk=obj.pk)


@login_required
@require_POST
def orientationsession_mark_missed(request, pk):
    obj = get_object_or_404(OrientationSession, pk=pk, tenant=request.tenant)
    if obj.attendance_status == "cancelled":
        messages.error(request, "A cancelled session cannot be marked missed.")
    elif obj.attendance_status != "missed":
        obj.attendance_status = "missed"
        obj.save(update_fields=["attendance_status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_missed"})
        messages.success(request, f"Session '{obj.title}' marked missed.")
    return redirect("hrm:orientationsession_detail", pk=obj.pk)


# ============================================================ 3.4 Employee Offboarding
def _offboarding_create(request, form_class, template, redirect_resolver):
    """Shared create for the offboarding models: tenant guard, ``?case=<pk>`` pre-fill (the child
    create pages are reached from the case hub), save + audit, then redirect via
    ``redirect_resolver(obj)`` → ``(view_name, pk)``. Mirrors ``apps.core.crud.crud_create`` but adds
    the initial-case pre-fill and a pk-aware redirect (crud_create can only redirect to a bare name).

    Contract: every caller MUST be ``@login_required`` (this helper writes an audit row with
    ``request.user`` and assumes an authenticated session)."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            view_name, pk = redirect_resolver(obj)
            return redirect(view_name, pk=pk)
    else:
        initial = {}
        case_pk = request.GET.get("case", "").strip()
        if case_pk.isdigit():
            initial["case"] = case_pk
        form = form_class(tenant=request.tenant, initial=initial or None)
    return render(request, template, {"form": form, "is_edit": False})


# ---------------------------------------------------------- Separation Cases (3.4)
@login_required
def separationcase_list(request):
    return crud_list(
        request,
        SeparationCase.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "approver"),
        "hrm/offboarding/separationcase_list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False), ("separation_type", "separation_type", False),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": SeparationCase.STATUS_CHOICES,
                       "separation_type_choices": SeparationCase.SEPARATION_TYPE_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def separationcase_create(request):
    return _offboarding_create(
        request, SeparationCaseForm, "hrm/offboarding/separationcase_form.html",
        lambda obj: ("hrm:separationcase_detail", obj.pk))


@login_required
def separationcase_detail(request, pk):
    obj = get_object_or_404(
        SeparationCase.objects.select_related(
            "employee__party", "employee__employment", "employee__employment__org_unit",
            "employee__designation", "approver"),
        pk=pk, tenant=request.tenant)
    clearance_items = list(obj.clearance_items
                           .select_related("assigned_to", "cleared_by", "asset_allocation"))
    clearance_total = len(clearance_items)
    clearance_done = sum(1 for c in clearance_items
                         if c.status in ClearanceItem.RESOLVED_STATUSES)
    clearance_progress = int(round(clearance_done / clearance_total * 100)) if clearance_total else 0
    # all-mandatory-cleared computed from the already-fetched list (avoids the property's extra query)
    all_mandatory_cleared = not any(
        c.is_mandatory and c.status not in ClearanceItem.RESOLVED_STATUSES for c in clearance_items)
    return render(request, "hrm/offboarding/separationcase_detail.html", {
        "obj": obj,
        "clearance_items": clearance_items,
        "clearance_total": clearance_total,
        "clearance_done": clearance_done,
        "clearance_progress": clearance_progress,
        "all_mandatory_cleared": all_mandatory_cleared,
        "exit_interview": obj.exit_interviews.select_related("interviewer").first(),
        "settlement": obj.final_settlements.first(),
        "rating_fields": ExitInterview.RATING_FIELDS,
    })


@login_required
def separationcase_edit(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "pending_approval"):
        messages.error(request, "Only a draft or pending separation case can be edited.")
        return redirect("hrm:separationcase_detail", pk=obj.pk)
    return crud_edit(request, model=SeparationCase, pk=pk, form_class=SeparationCaseForm,
                     template="hrm/offboarding/separationcase_form.html",
                     success_url="hrm:separationcase_list")


@login_required
@require_POST
def separationcase_delete(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    # Only a draft case is deletable — a submitted one is withdrawn (keeps the audit trail).
    if obj.status != "draft":
        messages.error(request, "Only a draft separation case can be deleted. Withdraw it instead.")
        return redirect("hrm:separationcase_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Separation case deleted.")
    return redirect("hrm:separationcase_list")


@login_required
@require_POST
def separationcase_submit(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending_approval"
        if obj.submitted_at is None:
            obj.submitted_at = timezone.now()
        obj.save(update_fields=["status", "submitted_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Separation case {obj.number} submitted for approval.")
    else:
        messages.error(request, "Only a draft case can be submitted.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


@tenant_admin_required  # approving a separation is a privileged HR/admin action
@require_POST
def separationcase_approve(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status == "pending_approval":
        with transaction.atomic():
            obj.status = "in_clearance"
            obj.approver = request.user
            obj.approved_at = timezone.now()
            obj.save(update_fields=["status", "approver", "approved_at", "updated_at"])
            created = generate_clearance_checklist(obj)  # auto-build the department checklist
            write_audit_log(request.user, obj, "update",
                            {"action": "approve", "clearance_items": created})
        messages.success(request, f"Separation case {obj.number} approved — "
                         f"{created} clearance item(s) created.")
    else:
        messages.error(request, "Only a case pending approval can be approved.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def separationcase_reject(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status == "pending_approval":
        obj.status = "rejected"
        obj.rejection_reason = request.POST.get("reason", "").strip()[:2000]
        obj.save(update_fields=["status", "rejection_reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Separation case {obj.number} rejected.")
    else:
        messages.error(request, "Only a case pending approval can be rejected.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


@login_required
@require_POST
def separationcase_withdraw(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "pending_approval"):
        obj.status = "withdrawn"
        obj.withdrawal_reason = request.POST.get("reason", "").strip()[:2000]
        obj.save(update_fields=["status", "withdrawal_reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "withdraw"})
        messages.success(request, f"Separation case {obj.number} withdrawn.")
    else:
        messages.error(request, "Only a draft or pending case can be withdrawn.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def separationcase_mark_cleared(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status != "in_clearance":
        messages.error(request, "Only a case in clearance can be marked cleared.")
    elif not obj.all_mandatory_cleared:
        messages.error(request, "All mandatory clearance items must be cleared or marked N/A first.")
    else:
        obj.status = "cleared"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_cleared"})
        messages.success(request, f"Separation case {obj.number} fully cleared.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def separationcase_complete(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status in ("cleared", "settled"):
        obj.status = "completed"
        if obj.actual_last_working_day is None:
            posted = _parse_iso_date(request.POST.get("actual_last_working_day", "").strip())
            obj.actual_last_working_day = (posted or obj.expected_last_working_day
                                           or timezone.localdate())
        obj.save(update_fields=["status", "actual_last_working_day", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, f"Separation case {obj.number} completed.")
    else:
        messages.error(request, "A case must be cleared (and settled) before completion.")
    return redirect("hrm:separationcase_detail", pk=obj.pk)


def _generate_letter(request, pk, *, kind, template):
    """Shared relieving/experience letter generator: gate on a cleared case, stamp the
    generated-at/by once, then render the print-ready letter (Content-Disposition: inline)."""
    obj = get_object_or_404(
        SeparationCase.objects.select_related(
            "employee__party", "employee__employment", "employee__employment__org_unit",
            "employee__designation"),
        pk=pk, tenant=request.tenant)
    if obj.status not in SeparationCase.LETTER_READY_STATUSES:
        messages.error(request, "Letters can only be generated once the case is cleared.")
        return redirect("hrm:separationcase_detail", pk=obj.pk)
    if kind == "relieving" and obj.relieving_letter_generated_at is None:
        obj.relieving_letter_generated_at = timezone.now()
        obj.relieving_letter_generated_by = request.user
        obj.save(update_fields=["relieving_letter_generated_at",
                                "relieving_letter_generated_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "generate_relieving_letter"})
    elif kind == "experience" and obj.experience_letter_generated_at is None:
        obj.experience_letter_generated_at = timezone.now()
        obj.experience_letter_generated_by = request.user
        obj.save(update_fields=["experience_letter_generated_at",
                                "experience_letter_generated_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "generate_experience_letter"})
    emp = obj.employee
    response = render(request, template, {
        "case": obj,
        "employee": emp,
        "employment": emp.employment if emp.employment_id else None,
        "tenant": request.tenant,
        "today": timezone.localdate(),
    })
    response["Content-Disposition"] = "inline"
    return response


@login_required
@require_POST
def separationcase_generate_relieving_letter(request, pk):
    return _generate_letter(request, pk, kind="relieving",
                            template="hrm/offboarding/relieving_letter.html")


@login_required
@require_POST
def separationcase_generate_experience_letter(request, pk):
    return _generate_letter(request, pk, kind="experience",
                            template="hrm/offboarding/experience_letter.html")


# ---------------------------------------------------------- Exit Interviews (3.4)
@login_required
def exitinterview_list(request):
    return crud_list(
        request,
        ExitInterview.objects.filter(tenant=request.tenant)
        .select_related("case__employee__party", "interviewer"),
        "hrm/offboarding/exitinterview_list.html",
        search_fields=["number", "case__employee__party__name", "case__number"],
        filters=[("status", "status", False), ("mode", "mode", False)],
        extra_context={"status_choices": ExitInterview.EI_STATUS_CHOICES,
                       "mode_choices": ExitInterview.MODE_CHOICES},
    )


@login_required
def exitinterview_create(request):
    return _offboarding_create(
        request, ExitInterviewForm, "hrm/offboarding/exitinterview_form.html",
        lambda obj: ("hrm:separationcase_detail", obj.case_id))


@login_required
def exitinterview_detail(request, pk):
    obj = get_object_or_404(
        ExitInterview.objects.select_related("case__employee__party", "interviewer"),
        pk=pk, tenant=request.tenant)
    ratings = [(label, getattr(obj, field)) for field, label in ExitInterview.RATING_FIELDS]
    return render(request, "hrm/offboarding/exitinterview_detail.html",
                  {"obj": obj, "ratings": ratings})


@login_required
def exitinterview_edit(request, pk):
    obj = get_object_or_404(ExitInterview, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.error(request, "A completed exit interview cannot be edited.")
        return redirect("hrm:exitinterview_detail", pk=obj.pk)
    return crud_edit(request, model=ExitInterview, pk=pk, form_class=ExitInterviewForm,
                     template="hrm/offboarding/exitinterview_form.html",
                     success_url="hrm:exitinterview_list")


@login_required
@require_POST
def exitinterview_delete(request, pk):
    obj = get_object_or_404(ExitInterview, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.error(request, "A completed exit interview cannot be deleted.")
        return redirect("hrm:exitinterview_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Exit interview deleted.")
    return redirect("hrm:exitinterview_list")


@login_required
@require_POST
def exitinterview_complete(request, pk):
    obj = get_object_or_404(ExitInterview, pk=pk, tenant=request.tenant)
    if obj.status == "scheduled":
        obj.status = "completed"
        obj.conducted_at = timezone.now()
        obj.save(update_fields=["status", "conducted_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, f"Exit interview {obj.number} marked completed.")
    else:
        messages.error(request, "Only a scheduled interview can be completed.")
    return redirect("hrm:exitinterview_detail", pk=obj.pk)


@login_required
@require_POST
def exitinterview_skip(request, pk):
    obj = get_object_or_404(ExitInterview, pk=pk, tenant=request.tenant)
    if obj.status == "scheduled":
        obj.status = "skipped"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "skip"})
        messages.success(request, f"Exit interview {obj.number} skipped.")
    else:
        messages.error(request, "Only a scheduled interview can be skipped.")
    return redirect("hrm:exitinterview_detail", pk=obj.pk)


# ---------------------------------------------------------- Clearance Items (3.4)
@login_required
def clearanceitem_list(request):
    return crud_list(
        request,
        ClearanceItem.objects.filter(tenant=request.tenant)
        .select_related("case__employee__party", "assigned_to", "cleared_by"),
        "hrm/offboarding/clearanceitem_list.html",
        search_fields=["description", "case__employee__party__name", "case__number"],
        filters=[("status", "status", False), ("department", "department", False)],
        extra_context={"status_choices": ClearanceItem.CLEARANCE_STATUS_CHOICES,
                       "dept_choices": ClearanceItem.CLEARANCE_DEPT_CHOICES},
    )


@login_required
def clearanceitem_create(request):
    return _offboarding_create(
        request, ClearanceItemForm, "hrm/offboarding/clearanceitem_form.html",
        lambda obj: ("hrm:separationcase_detail", obj.case_id))


@login_required
def clearanceitem_detail(request, pk):
    obj = get_object_or_404(
        ClearanceItem.objects.select_related(
            "case__employee__party", "assigned_to", "cleared_by", "asset_allocation"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/offboarding/clearanceitem_detail.html", {"obj": obj})


@login_required
def clearanceitem_edit(request, pk):
    obj = get_object_or_404(ClearanceItem, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "in_progress"):
        messages.error(request, "Only a pending clearance item can be edited.")
        return redirect("hrm:clearanceitem_detail", pk=obj.pk)
    return crud_edit(request, model=ClearanceItem, pk=pk, form_class=ClearanceItemForm,
                     template="hrm/offboarding/clearanceitem_form.html",
                     success_url="hrm:clearanceitem_list")


@login_required
@require_POST
def clearanceitem_delete(request, pk):
    obj = get_object_or_404(ClearanceItem, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending clearance item can be deleted.")
        return redirect("hrm:clearanceitem_detail", pk=obj.pk)
    case_id = obj.case_id
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Clearance item deleted.")
    return redirect("hrm:separationcase_detail", pk=case_id)


@login_required
@require_POST
def clearanceitem_mark_cleared(request, pk):
    obj = get_object_or_404(
        ClearanceItem.objects.select_related("case", "asset_allocation"), pk=pk, tenant=request.tenant)
    if obj.status in ("pending", "in_progress"):
        with transaction.atomic():
            obj.status = "cleared"
            obj.cleared_by = request.user
            obj.cleared_at = timezone.now()
            obj.save(update_fields=["status", "cleared_by", "cleared_at", "updated_at"])
            # Returning the linked asset is part of clearing its line — keep the two in one txn.
            # Only return an asset that actually belongs to this case's employee (guard against a
            # mis-linked allocation from another employee being silently marked returned).
            returned = None
            if (obj.asset_allocation_id and obj.asset_allocation.status == "issued"
                    and obj.asset_allocation.employee_id == obj.case.employee_id):
                obj.asset_allocation.status = "returned"
                obj.asset_allocation.returned_at = timezone.now()
                obj.asset_allocation.save(update_fields=["status", "returned_at", "updated_at"])
                returned = obj.asset_allocation.number
        write_audit_log(request.user, obj, "update",
                        {"action": "mark_cleared", "asset_returned": returned})
        messages.success(request, "Clearance item cleared."
                         + (f" Asset {returned} returned." if returned else ""))
    else:
        messages.error(request, "This clearance item cannot be cleared in its current state.")
    return redirect("hrm:separationcase_detail", pk=obj.case_id)


@login_required
@require_POST
def clearanceitem_mark_na(request, pk):
    obj = get_object_or_404(ClearanceItem.objects.select_related("case"), pk=pk, tenant=request.tenant)
    if obj.status in ("pending", "in_progress"):
        obj.status = "not_applicable"
        obj.cleared_by = request.user
        obj.cleared_at = timezone.now()
        obj.save(update_fields=["status", "cleared_by", "cleared_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_na"})
        messages.success(request, "Clearance item marked not applicable.")
    else:
        messages.error(request, "This clearance item cannot be changed in its current state.")
    return redirect("hrm:separationcase_detail", pk=obj.case_id)


@tenant_admin_required  # rejecting a clearance line is a privileged action (blocks the gate)
@require_POST
def clearanceitem_reject(request, pk):
    obj = get_object_or_404(ClearanceItem.objects.select_related("case"), pk=pk, tenant=request.tenant)
    # Only an open line can be rejected (failed clearance) — a resolved one stays resolved.
    if obj.status in ("pending", "in_progress"):
        obj.status = "rejected"
        obj.cleared_by = None
        obj.cleared_at = None
        obj.save(update_fields=["status", "cleared_by", "cleared_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, "Clearance item rejected.")
    else:
        messages.error(request, "Only a pending or in-progress clearance item can be rejected.")
    return redirect("hrm:separationcase_detail", pk=obj.case_id)


# ---------------------------------------------------------- Final Settlements (3.4)
@login_required
def finalsettlement_list(request):
    return crud_list(
        request,
        FinalSettlement.objects.filter(tenant=request.tenant)
        .select_related("case__employee__party"),
        "hrm/offboarding/finalsettlement_list.html",
        search_fields=["number", "case__employee__party__name", "case__number"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": FinalSettlement.FNF_STATUS_CHOICES},
    )


@login_required
def finalsettlement_create(request):
    return _offboarding_create(
        request, FinalSettlementForm, "hrm/offboarding/finalsettlement_form.html",
        lambda obj: ("hrm:separationcase_detail", obj.case_id))


@login_required
def finalsettlement_detail(request, pk):
    obj = get_object_or_404(
        FinalSettlement.objects.select_related("case__employee__party"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/offboarding/finalsettlement_detail.html", {"obj": obj})


@login_required
def finalsettlement_edit(request, pk):
    obj = get_object_or_404(FinalSettlement, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "computed"):
        messages.error(request, "Only a draft or computed settlement can be edited.")
        return redirect("hrm:finalsettlement_detail", pk=obj.pk)
    return crud_edit(request, model=FinalSettlement, pk=pk, form_class=FinalSettlementForm,
                     template="hrm/offboarding/finalsettlement_form.html",
                     success_url="hrm:finalsettlement_list")


@login_required
@require_POST
def finalsettlement_delete(request, pk):
    obj = get_object_or_404(FinalSettlement, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft settlement can be deleted.")
        return redirect("hrm:finalsettlement_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Settlement deleted.")
    return redirect("hrm:finalsettlement_list")


@tenant_admin_required  # computing F&F (pulling leave/gratuity) is a privileged HR/finance action
@require_POST
def finalsettlement_compute(request, pk):
    obj = get_object_or_404(
        FinalSettlement.objects.select_related("case__employee__designation",
                                               "case__employee__employment"),
        pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft settlement can be computed.")
        return redirect("hrm:finalsettlement_detail", pk=obj.pk)
    employee = obj.case.employee
    days, amount = compute_leave_encashment(employee)
    obj.leave_encashment_days = days
    obj.leave_encashment_amount = amount
    # Gratuity: ≥5 years of service (best-effort from employment.hired_on + designation band).
    employment = employee.employment if employee.employment_id else None
    if (employment and employment.hired_on and employee.designation_id
            and employee.designation and employee.designation.min_salary):
        years = (timezone.localdate() - employment.hired_on).days / 365.25
        if years >= 5:
            obj.gratuity_eligible = True
            basic = employee.designation.min_salary
            obj.gratuity_amount = (basic * Decimal("15") * Decimal(str(round(years, 2)))
                                   / Decimal("26")).quantize(Decimal("0.01"))
    obj.status = "computed"
    obj.save(update_fields=["leave_encashment_days", "leave_encashment_amount",
                            "gratuity_eligible", "gratuity_amount", "status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "compute"})
    messages.success(request, f"Settlement {obj.number} computed — net payable {obj.net_payable}.")
    return redirect("hrm:finalsettlement_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def finalsettlement_hr_approve(request, pk):
    obj = get_object_or_404(FinalSettlement, pk=pk, tenant=request.tenant)
    if obj.status in ("computed", "draft"):
        obj.status = "hr_approved"
        obj.hr_approved_by = request.user
        obj.hr_approved_at = timezone.now()
        obj.save(update_fields=["status", "hr_approved_by", "hr_approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "hr_approve"})
        messages.success(request, f"Settlement {obj.number} HR-approved.")
    else:
        messages.error(request, "Only a draft or computed settlement can be HR-approved.")
    return redirect("hrm:finalsettlement_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def finalsettlement_finance_approve(request, pk):
    obj = get_object_or_404(FinalSettlement, pk=pk, tenant=request.tenant)
    if obj.status == "hr_approved":
        obj.status = "finance_approved"
        obj.finance_approved_by = request.user
        obj.finance_approved_at = timezone.now()
        obj.save(update_fields=["status", "finance_approved_by", "finance_approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "finance_approve"})
        messages.success(request, f"Settlement {obj.number} finance-approved.")
    else:
        messages.error(request, "Only an HR-approved settlement can be finance-approved.")
    return redirect("hrm:finalsettlement_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def finalsettlement_mark_paid(request, pk):
    obj = get_object_or_404(FinalSettlement.objects.select_related("case"), pk=pk, tenant=request.tenant)
    if obj.status in ("hr_approved", "finance_approved"):
        with transaction.atomic():
            obj.status = "paid"
            obj.paid_at = timezone.localdate()
            obj.save(update_fields=["status", "paid_at", "updated_at"])
            # Mark the parent case settled once its F&F is paid (only advances from 'cleared').
            case = obj.case
            if case.status == "cleared":
                case.status = "settled"
                case.save(update_fields=["status", "updated_at"])
                write_audit_log(request.user, case, "update",
                                {"action": "settled_via_fnf", "settlement": obj.number})
            write_audit_log(request.user, obj, "update", {"action": "mark_paid"})
        messages.success(request, f"Settlement {obj.number} marked paid.")
    else:
        messages.error(request, "Only an approved settlement can be marked paid.")
    return redirect("hrm:finalsettlement_detail", pk=obj.pk)
