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

from .services import generate_tasks_from_template

from .forms import (
    AssetAllocationForm,
    AttendanceRecordForm,
    DesignationForm,
    EmployeeProfileForm,
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
    ShiftAssignmentForm,
    ShiftForm,
)
from .models import (
    PHASE_CHOICES,
    TASK_CATEGORY_CHOICES,
    AssetAllocation,
    AttendanceRecord,
    Designation,
    EmployeeProfile,
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
                   .select_related("leave_type").annotate(used_days_db=_used_days_subquery()))
    balances = [{
        "leave_type": a.leave_type,
        "allocated": a.allocated_days,
        "used": a.used_days_db,
        "balance": (a.allocated_days or Decimal("0")) - a.used_days_db,
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
    used_subq = _used_days_subquery()
    return crud_list(
        request,
        LeaveAllocation.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "leave_type")
        .annotate(used_days_db=used_subq)
        .annotate(balance_db=ExpressionWrapper(F("allocated_days") - F("used_days_db"), output_field=_DEC)),
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
    # Parse the date-range GET params defensively — a malformed string passed straight to
    # .filter(date__gte=...) would raise a 500 (ValueError/DataError); ignore bad input instead.
    date_from = _parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = _parse_iso_date(request.GET.get("date_to", "").strip())
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


# ============================================================ Onboarding Templates (3.3)
@login_required
def onboardingtemplate_list(request):
    return crud_list(
        request,
        OnboardingTemplate.objects.filter(tenant=request.tenant).select_related("designation")
        .annotate(task_count=Count("template_tasks")).order_by("name"),
        "hrm/onboardingtemplate_list.html",
        search_fields=["number", "name", "designation__name"],
        filters=[("is_active", "is_active", False), ("designation", "designation_id", True)],
        extra_context={"designations": Designation.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def onboardingtemplate_create(request):
    return crud_create(request, form_class=OnboardingTemplateForm,
                       template="hrm/onboardingtemplate_form.html",
                       success_url="hrm:onboardingtemplate_list")


@login_required
def onboardingtemplate_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTemplate.objects.select_related("designation"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboardingtemplate_detail.html", {
        "obj": obj,
        "tasks": obj.template_tasks.order_by("phase", "order", "title"),
        "program_count": OnboardingProgram.objects.filter(tenant=request.tenant, template=obj).count(),
    })


@login_required
def onboardingtemplate_edit(request, pk):
    return crud_edit(request, model=OnboardingTemplate, pk=pk, form_class=OnboardingTemplateForm,
                     template="hrm/onboardingtemplate_form.html",
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
        "hrm/onboardingtemplatetask_list.html",
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
                       template="hrm/onboardingtemplatetask_form.html",
                       success_url="hrm:onboardingtemplatetask_list")


@login_required
def onboardingtemplatetask_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTemplateTask.objects.select_related("template"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboardingtemplatetask_detail.html", {"obj": obj})


@login_required
def onboardingtemplatetask_edit(request, pk):
    return crud_edit(request, model=OnboardingTemplateTask, pk=pk,
                     form_class=OnboardingTemplateTaskForm,
                     template="hrm/onboardingtemplatetask_form.html",
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
        "hrm/onboardingprogram_list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False), ("employee", "employee_id", True)],
        extra_context={"status_choices": OnboardingProgram.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def onboardingprogram_create(request):
    return crud_create(request, form_class=OnboardingProgramForm,
                       template="hrm/onboardingprogram_form.html",
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
    return render(request, "hrm/onboardingprogram_detail.html", {
        "obj": obj,
        "progress": progress,
        "tasks_by_phase": tasks_by_phase,
        "task_count": len(tasks),
        "documents": obj.documents.order_by("document_type", "title"),
        "assets": obj.assets.select_related("issued_by").order_by("-created_at"),
        "sessions": obj.orientation_sessions.select_related("facilitator").order_by("scheduled_at"),
        "today": timezone.localdate(),
    })


@login_required
def onboardingprogram_edit(request, pk):
    obj = get_object_or_404(OnboardingProgram, pk=pk, tenant=request.tenant)
    if obj.status in ("completed", "cancelled"):
        messages.error(request, "A completed or cancelled program cannot be edited.")
        return redirect("hrm:onboardingprogram_detail", pk=obj.pk)
    return crud_edit(request, model=OnboardingProgram, pk=pk, form_class=OnboardingProgramForm,
                     template="hrm/onboardingprogram_form.html",
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
        .select_related("program__employee__party", "assignee"),
        "hrm/onboardingtask_list.html",
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
                       template="hrm/onboardingtask_form.html",
                       success_url="hrm:onboardingtask_list")


@login_required
def onboardingtask_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTask.objects.select_related("program__employee__party", "assignee", "completed_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboardingtask_detail.html", {"obj": obj, "today": timezone.localdate()})


@login_required
def onboardingtask_edit(request, pk):
    obj = get_object_or_404(OnboardingTask, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.error(request, "Reopen this task before editing it.")
        return redirect("hrm:onboardingtask_detail", pk=obj.pk)
    return crud_edit(request, model=OnboardingTask, pk=pk, form_class=OnboardingTaskForm,
                     template="hrm/onboardingtask_form.html", success_url="hrm:onboardingtask_list")


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
        .select_related("program__employee__party"),
        "hrm/onboardingdocument_list.html",
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
                       template="hrm/onboardingdocument_form.html",
                       success_url="hrm:onboardingdocument_list")


@login_required
def onboardingdocument_detail(request, pk):
    obj = get_object_or_404(
        OnboardingDocument.objects.select_related("program__employee__party"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboardingdocument_detail.html", {"obj": obj})


@login_required
def onboardingdocument_edit(request, pk):
    return crud_edit(request, model=OnboardingDocument, pk=pk, form_class=OnboardingDocumentForm,
                     template="hrm/onboardingdocument_form.html",
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
        "hrm/assetallocation_list.html",
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
                       template="hrm/assetallocation_form.html",
                       success_url="hrm:assetallocation_list")


@login_required
def assetallocation_detail(request, pk):
    obj = get_object_or_404(
        AssetAllocation.objects.select_related("employee__party", "program", "issued_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/assetallocation_detail.html", {"obj": obj})


@login_required
def assetallocation_edit(request, pk):
    return crud_edit(request, model=AssetAllocation, pk=pk, form_class=AssetAllocationForm,
                     template="hrm/assetallocation_form.html", success_url="hrm:assetallocation_list")


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
        "hrm/orientationsession_list.html",
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
                       template="hrm/orientationsession_form.html",
                       success_url="hrm:orientationsession_list")


@login_required
def orientationsession_detail(request, pk):
    obj = get_object_or_404(
        OrientationSession.objects.select_related("employee__party", "program", "facilitator"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/orientationsession_detail.html", {"obj": obj})


@login_required
def orientationsession_edit(request, pk):
    return crud_edit(request, model=OrientationSession, pk=pk, form_class=OrientationSessionForm,
                     template="hrm/orientationsession_form.html",
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
