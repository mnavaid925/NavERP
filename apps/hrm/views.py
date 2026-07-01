"""HRM (Module 3) views — function-based, ``@login_required``, tenant-scoped.

Full CRUD for the nine HRM models via the shared ``apps.core.crud`` helpers (search +
int-FK-guarded filters + windowed pagination + audit), plus:
  * an HRM overview (3.1) with headcount / today's attendance / pending-leave / holiday widgets,
  * a rich employee profile (leave balances, recent attendance, current shift),
  * the leave-request workflow actions (submit / approve / reject / cancel),
  * delete guards on records that anchor others (active employee, in-use leave type/shift).
"""
import secrets
from datetime import date as _date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import (Avg, Count, DecimalField, ExpressionWrapper, F, OuterRef, Q, Subquery, Sum)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from django.conf import settings
from django.core.mail import send_mail

from apps.core.crud import crud_create, crud_delete, crud_detail, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.models import Employment, OrgUnit, Party, PartyRole
from apps.core.utils import write_audit_log

from .services import (
    apply_template_to_requisition,
    compute_leave_encashment,
    generate_approval_chain,
    generate_clearance_checklist,
    generate_offer_approval_chain,
    generate_preboarding_checklist,
    generate_tasks_from_template,
)

from .forms import (
    AssetAllocationForm,
    AttendanceRecordForm,
    ClearanceItemForm,
    CostCenterProfileForm,
    DepartmentProfileForm,
    DesignationForm,
    EmployeeDocumentForm,
    EmployeeLifecycleEventForm,
    EmployeeProfileForm,
    ExitInterviewForm,
    FinalSettlementForm,
    JobDescriptionTemplateForm,
    JobGradeForm,
    JobRequisitionForm,
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
    RequisitionApprovalForm,
    SeparationCaseForm,
    ShiftAssignmentForm,
    ShiftForm,
)
from .forms import (  # 3.6 Candidate Management
    CandidateEmailTemplateForm,
    CandidateProfileForm,
    CandidateSkillForm,
    CandidateTagForm,
    JobApplicationForm,
    PublicApplicationForm,
)
from .forms import (  # 3.7 Interview Process
    FeedbackCriterionForm,
    InterviewFeedbackForm,
    InterviewForm,
    InterviewPanelistForm,
)
from .forms import (  # 3.8 Offer Management
    BackgroundVerificationForm,
    OfferApprovalForm,
    OfferForm,
    OfferLetterTemplateForm,
    PreboardingItemForm,
)
from .models import (
    APPLICATION_STAGE_CHOICES,
    APPLICATION_TERMINAL_STAGES,
    CANDIDATE_GENDER_CHOICES,
    CANDIDATE_SOURCE_CHOICES,
    CANDIDATE_STATUS_CHOICES,
    COMMUNICATION_CHANNEL_CHOICES,
    DELIVERY_STATUS_CHOICES,
    EMAIL_TEMPLATE_TYPE_CHOICES,
    EMPLOYMENT_TYPE_CHOICES,
    JR_STATUS_CHOICES,
    LIFECYCLE_EVENT_TYPE_CHOICES,
    PHASE_CHOICES,
    PRIORITY_CHOICES,
    QUALIFICATION_CHOICES,
    REJECTION_REASON_CHOICES,
    REQ_TYPE_CHOICES,
    TASK_CATEGORY_CHOICES,
    CandidateCommunication,
    CandidateEmailTemplate,
    CandidateProfile,
    CandidateSkill,
    CandidateTag,
    JobApplication,
    AssetAllocation,
    AttendanceRecord,
    ClearanceItem,
    CostCenterProfile,
    DepartmentProfile,
    Designation,
    EmployeeDocument,
    EmployeeLifecycleEvent,
    EmployeeProfile,
    ExitInterview,
    FinalSettlement,
    JobDescriptionTemplate,
    JobGrade,
    JobRequisition,
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
    RequisitionApproval,
    SeparationCase,
    Shift,
    ShiftAssignment,
)
from .models import (  # 3.7 Interview Process
    INTERVIEW_MODE_CHOICES,
    INTERVIEW_STATUS_CHOICES,
    INTERVIEW_TERMINAL_STATUSES,
    PANELIST_ROLE_CHOICES,
    RECOMMENDATION_CHOICES,
    RSVP_STATUS_CHOICES,
    VIDEO_PROVIDER_CHOICES,
    FeedbackCriterion,
    Interview,
    InterviewFeedback,
    InterviewPanelist,
)
from .models import (  # 3.8 Offer Management
    BGV_CHECK_TYPE_CHOICES,
    BGV_RESULT_CHOICES,
    BGV_STATUS_CHOICES,
    BGV_VENDOR_CHOICES,
    OFFER_DECLINE_REASON_CHOICES,
    OFFER_STATUS_CHOICES,
    PREBOARDING_DOC_TYPE_CHOICES,
    PREBOARDING_STATUS_CHOICES,
    SIGNATURE_STATUS_CHOICES,
    BackgroundVerification,
    Offer,
    OfferApproval,
    OfferLetterTemplate,
    PreboardingItem,
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
             "present_today": 0, "absent_today": 0,
             "open_requisitions": 0, "active_applications": 0, "new_candidates": 0}
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
        # 3.6 recruiting pipeline at a glance.
        stats["open_requisitions"] = JobRequisition.objects.filter(tenant=tenant, status="posted").count()
        stats["active_applications"] = (JobApplication.objects.filter(tenant=tenant)
                                        .exclude(stage__in=APPLICATION_TERMINAL_STAGES).count())
        stats["new_candidates"] = CandidateProfile.objects.filter(
            tenant=tenant, created_at__year=today.year, created_at__month=today.month).count()
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
        Designation.objects.filter(tenant=request.tenant).select_related("department", "job_grade")
        .annotate(employee_count=Count("employees")).order_by("name"),
        "hrm/organization/designation/list.html",
        search_fields=["name", "grade", "job_grade__name", "department__name"],
        filters=[("is_active", "is_active", False), ("department", "department_id", True),
                 ("job_grade", "job_grade_id", True)],
        extra_context={
            "departments": OrgUnit.objects.filter(tenant=request.tenant, kind="department").order_by("name"),
            "job_grades": JobGrade.objects.filter(tenant=request.tenant, is_active=True).order_by("level_order", "name"),
        },
    )


@login_required
def designation_create(request):
    return crud_create(request, form_class=DesignationForm,
                       template="hrm/organization/designation/form.html",
                       success_url="hrm:designation_list")


@login_required
def designation_detail(request, pk):
    obj = get_object_or_404(
        Designation.objects.select_related("department", "job_grade")
        .annotate(employee_count=Count("employees")), pk=pk, tenant=request.tenant)
    return render(request, "hrm/organization/designation/detail.html", {
        "obj": obj,
        "employees": EmployeeProfile.objects.filter(tenant=request.tenant, designation=obj)
        .select_related("party")[:50],
        "employee_count": obj.employee_count,
    })


@login_required
def designation_edit(request, pk):
    return crud_edit(request, model=Designation, pk=pk, form_class=DesignationForm,
                     template="hrm/organization/designation/form.html",
                     success_url="hrm:designation_list")


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


# ============================================================ Job Grades (3.2)
@login_required
def jobgrade_list(request):
    return crud_list(
        request,
        JobGrade.objects.filter(tenant=request.tenant)
        .annotate(designation_count=Count("designations")).order_by("level_order", "name"),
        "hrm/organization/jobgrade/list.html",
        search_fields=["name", "description"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def jobgrade_create(request):
    return crud_create(request, form_class=JobGradeForm,
                       template="hrm/organization/jobgrade/form.html",
                       success_url="hrm:jobgrade_list")


@login_required
def jobgrade_detail(request, pk):
    obj = get_object_or_404(
        JobGrade.objects.annotate(designation_count=Count("designations")),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/organization/jobgrade/detail.html", {
        "obj": obj,
        "designations": Designation.objects.filter(tenant=request.tenant, job_grade=obj)
        .select_related("department")[:50],
        "designation_count": obj.designation_count,
    })


@login_required
def jobgrade_edit(request, pk):
    return crud_edit(request, model=JobGrade, pk=pk, form_class=JobGradeForm,
                     template="hrm/organization/jobgrade/form.html",
                     success_url="hrm:jobgrade_list")


@login_required
@require_POST
def jobgrade_delete(request, pk):
    obj = get_object_or_404(JobGrade, pk=pk, tenant=request.tenant)
    if Designation.objects.filter(tenant=request.tenant, job_grade=obj).exists():
        messages.error(request, "Cannot delete a grade assigned to designations. "
                                "Deactivate it instead.")
        return redirect("hrm:jobgrade_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Job grade deleted.")
    return redirect("hrm:jobgrade_list")


# ============================================================ Departments (3.2 — OrgUnit companion)
@login_required
def department_list(request):
    return crud_list(
        request,
        DepartmentProfile.objects.filter(tenant=request.tenant)
        .select_related("org_unit", "org_unit__parent", "head__party", "cost_center")
        .annotate(employee_count=Count(
            "org_unit__employments",
            filter=Q(org_unit__employments__status="active"))).order_by("org_unit__name"),
        "hrm/organization/department/list.html",
        search_fields=["org_unit__name", "code", "description"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def department_create(request):
    return crud_create(request, form_class=DepartmentProfileForm,
                       template="hrm/organization/department/form.html",
                       success_url="hrm:department_list")


@login_required
def department_detail(request, pk):
    obj = get_object_or_404(
        DepartmentProfile.objects.select_related(
            "org_unit", "org_unit__parent", "head__party", "cost_center"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/organization/department/detail.html", {
        "obj": obj,
        "designations": Designation.objects.filter(tenant=request.tenant, department=obj.org_unit)
        .select_related("job_grade")[:50],
        # Only currently-employed staff count as "in" the department (matches the delete guard).
        "employees": EmployeeProfile.objects.filter(
            tenant=request.tenant, employment__org_unit=obj.org_unit, employment__status="active")
        .select_related("party", "designation")[:50],
    })


@login_required
def department_edit(request, pk):
    return crud_edit(request, model=DepartmentProfile, pk=pk, form_class=DepartmentProfileForm,
                     template="hrm/organization/department/form.html",
                     success_url="hrm:department_list")


@login_required
@require_POST
def department_delete(request, pk):
    obj = get_object_or_404(DepartmentProfile, pk=pk, tenant=request.tenant)
    # Guard: don't strip a department's HR profile while staff are still posted to the OrgUnit.
    if Employment.objects.filter(tenant=request.tenant, org_unit=obj.org_unit, status="active").exists():
        messages.error(request, "Cannot delete a department profile while employees are assigned. "
                                "Deactivate it instead.")
        return redirect("hrm:department_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()  # removes only the HRM companion; the core.OrgUnit node is untouched.
    messages.success(request, "Department profile deleted.")
    return redirect("hrm:department_list")


# ============================================================ Cost Centers (3.2 — OrgUnit companion)
@login_required
def costcenter_list(request):
    return crud_list(
        request,
        CostCenterProfile.objects.filter(tenant=request.tenant)
        .select_related("org_unit", "org_unit__parent", "owner__party").order_by("org_unit__name"),
        "hrm/organization/costcenter/list.html",
        search_fields=["org_unit__name", "code", "description"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def costcenter_create(request):
    return crud_create(request, form_class=CostCenterProfileForm,
                       template="hrm/organization/costcenter/form.html",
                       success_url="hrm:costcenter_list")


@login_required
def costcenter_detail(request, pk):
    obj = get_object_or_404(
        CostCenterProfile.objects.select_related("org_unit", "org_unit__parent", "owner__party"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/organization/costcenter/detail.html", {
        "obj": obj,
        "mapped_departments": DepartmentProfile.objects.filter(
            tenant=request.tenant, cost_center=obj.org_unit)
        .select_related("org_unit", "head__party")[:50],
    })


@login_required
def costcenter_edit(request, pk):
    return crud_edit(request, model=CostCenterProfile, pk=pk, form_class=CostCenterProfileForm,
                     template="hrm/organization/costcenter/form.html",
                     success_url="hrm:costcenter_list")


@login_required
@require_POST
def costcenter_delete(request, pk):
    obj = get_object_or_404(CostCenterProfile, pk=pk, tenant=request.tenant)
    if DepartmentProfile.objects.filter(tenant=request.tenant, cost_center=obj.org_unit).exists():
        messages.error(request, "Cannot delete a cost center mapped to departments. "
                                "Unmap them or deactivate it instead.")
        return redirect("hrm:costcenter_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Cost center profile deleted.")
    return redirect("hrm:costcenter_list")


# ============================================================ Org Chart & Company Setup (3.2 — derived)
@login_required
def org_chart(request):
    """Reporting-line / department-grouped org chart, DERIVED from ``core.Employment.manager``
    (single-parent chain) and ``OrgUnit`` — no model. ``?view=reporting|department`` toggles mode."""
    tenant = request.tenant
    view_mode = "department" if request.GET.get("view") == "department" else "reporting"
    CAP = 500  # an org chart loads ALL employees (no pagination); guard against a runaway tenant.
    tree_nodes, dept_groups, total, capped = [], [], 0, False
    if tenant is not None:
        employees = list(
            EmployeeProfile.objects.filter(tenant=tenant)
            .exclude(employment__status="terminated")  # keep active/on-leave/unassigned, drop exited
            .select_related("party", "employment", "employment__org_unit", "employment__manager",
                            "designation", "designation__job_grade")
            .order_by("party__name")[:CAP + 1])
        capped = len(employees) > CAP
        if capped:
            employees = employees[:CAP]
        total = len(employees)
        # Map a manager Party -> the EmployeeProfile rows that report to it.
        by_party = {e.party_id: e for e in employees}
        children = {}
        roots = []
        for e in employees:
            mgr_party = e.employment.manager_id if e.employment_id else None
            if mgr_party and mgr_party in by_party and by_party[mgr_party].pk != e.pk:
                children.setdefault(mgr_party, []).append(e)
            else:
                roots.append(e)
        # Iterative DFS into a flat (employee, depth) list — cycle-guarded AND recursion-free in
        # Python too, so a very deep manager chain can't raise RecursionError (review C1).
        seen = set()
        stack = [(root, 0) for root in reversed(roots)]
        while stack:
            emp, depth = stack.pop()
            if emp.pk in seen:
                continue
            seen.add(emp.pk)
            tree_nodes.append({"emp": emp, "depth": depth})
            for child in reversed(children.get(emp.party_id, [])):
                stack.append((child, depth + 1))
        # Any employee not reached (cycle) is appended at depth 0 so none are dropped.
        for e in employees:
            if e.pk not in seen:
                tree_nodes.append({"emp": e, "depth": 0})

        # Department-grouped mode.
        groups = {}
        for e in employees:
            unit = e.employment.org_unit if e.employment_id else None
            key = unit.name if unit else "Unassigned"
            groups.setdefault(key, []).append(e)
        dept_groups = [{"name": name, "employees": groups[name]} for name in sorted(groups)]
    return render(request, "hrm/organization/org_chart.html", {
        "tree_nodes": tree_nodes,
        "dept_groups": dept_groups,
        "view_mode": view_mode,
        "total": total,
        "capped": capped,
        "cap": CAP,
    })


@login_required
def company_setup(request):
    """Read-only company overview (3.2 Company Setup) — the company ``OrgUnit`` node plus the
    branding the Tenants module (Module 0) owns. Branding edits stay in ``tenants:brandingsetting_list``."""
    from apps.tenants.models import BrandingSetting

    tenant = request.tenant
    company_unit = branding = None
    departments = cost_centers = 0
    if tenant is not None:
        company_unit = OrgUnit.objects.filter(tenant=tenant, kind="company").first()
        branding = BrandingSetting.objects.filter(tenant=tenant).first()
        departments = OrgUnit.objects.filter(tenant=tenant, kind="department").count()
        cost_centers = OrgUnit.objects.filter(tenant=tenant, kind="cost_center").count()
    return render(request, "hrm/organization/company_setup.html", {
        "company_unit": company_unit,
        "branding": branding,
        "departments": departments,
        "cost_centers": cost_centers,
    })


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
        # Confidential documents only surface on the hub for tenant admins.
        "documents": (EmployeeDocument.objects.filter(tenant=request.tenant, employee=obj)
                      if _is_hr_admin(request.user)
                      else EmployeeDocument.objects.filter(tenant=request.tenant, employee=obj,
                                                           is_confidential=False))
        .order_by("-created_at")[:10],
        "lifecycle_events": EmployeeLifecycleEvent.objects.filter(tenant=request.tenant, employee=obj)
        .select_related("from_designation", "to_designation", "from_department", "to_department")
        .order_by("-effective_date")[:10],
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
        "hrm/leave/type/list.html",
        search_fields=["name", "code"],
        filters=[("is_active", "is_active", False), ("is_paid", "is_paid", False),
                 ("accrual_rule", "accrual_rule", False)],
        extra_context={"accrual_choices": LeaveType.ACCRUAL_CHOICES},
    )


@login_required
def leavetype_create(request):
    return crud_create(request, form_class=LeaveTypeForm, template="hrm/leave/type/form.html",
                       success_url="hrm:leavetype_list")


@login_required
def leavetype_detail(request, pk):
    obj = get_object_or_404(LeaveType, pk=pk, tenant=request.tenant)
    year = timezone.localdate().year
    return render(request, "hrm/leave/type/detail.html", {
        "obj": obj,
        "year": year,
        "allocation_count": LeaveAllocation.objects.filter(
            tenant=request.tenant, leave_type=obj, year=year).count(),
        "request_count": LeaveRequest.objects.filter(tenant=request.tenant, leave_type=obj).count(),
    })


@login_required
def leavetype_edit(request, pk):
    return crud_edit(request, model=LeaveType, pk=pk, form_class=LeaveTypeForm,
                     template="hrm/leave/type/form.html", success_url="hrm:leavetype_list")


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
        "hrm/leave/allocation/list.html",
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
                       template="hrm/leave/allocation/form.html", success_url="hrm:leaveallocation_list")


@login_required
def leaveallocation_detail(request, pk):
    obj = get_object_or_404(
        LeaveAllocation.objects.select_related("employee__party", "leave_type"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/leave/allocation/detail.html", {
        "obj": obj,
        "requests": LeaveRequest.objects.filter(
            tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type,
            start_date__year=obj.year).order_by("-start_date")[:20],
    })


@login_required
def leaveallocation_edit(request, pk):
    return crud_edit(request, model=LeaveAllocation, pk=pk, form_class=LeaveAllocationForm,
                     template="hrm/leave/allocation/form.html", success_url="hrm:leaveallocation_list")


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
        "hrm/leave/request/list.html",
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
    return crud_create(request, form_class=LeaveRequestForm, template="hrm/leave/request/form.html",
                       success_url="hrm:leaverequest_list")


@login_required
def leaverequest_detail(request, pk):
    obj = get_object_or_404(
        LeaveRequest.objects.select_related("employee__party", "leave_type", "approver"),
        pk=pk, tenant=request.tenant)
    allocation = LeaveAllocation.objects.filter(
        tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type,
        year=obj.start_date.year).first()
    return render(request, "hrm/leave/request/detail.html", {
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
                     template="hrm/leave/request/form.html", success_url="hrm:leaverequest_list")


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
        request, qs, "hrm/holiday/publicholiday/list.html",
        search_fields=["name"],
        filters=[("is_optional", "is_optional", False)],
        extra_context={"year_choices": years},
    )


@login_required
def publicholiday_create(request):
    return crud_create(request, form_class=PublicHolidayForm,
                       template="hrm/holiday/publicholiday/form.html", success_url="hrm:publicholiday_list")


@login_required
def publicholiday_detail(request, pk):
    obj = get_object_or_404(PublicHoliday, pk=pk, tenant=request.tenant)
    return render(request, "hrm/holiday/publicholiday/detail.html", {"obj": obj})


@login_required
def publicholiday_edit(request, pk):
    return crud_edit(request, model=PublicHoliday, pk=pk, form_class=PublicHolidayForm,
                     template="hrm/holiday/publicholiday/form.html", success_url="hrm:publicholiday_list")


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
        "hrm/attendance/shift/list.html",
        search_fields=["name"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def shift_create(request):
    return crud_create(request, form_class=ShiftForm, template="hrm/attendance/shift/form.html",
                       success_url="hrm:shift_list")


@login_required
def shift_detail(request, pk):
    obj = get_object_or_404(Shift, pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/shift/detail.html", {
        "obj": obj,
        "assignments": ShiftAssignment.objects.filter(tenant=request.tenant, shift=obj)
        .select_related("employee__party").order_by("-effective_from")[:50],
    })


@login_required
def shift_edit(request, pk):
    return crud_edit(request, model=Shift, pk=pk, form_class=ShiftForm,
                     template="hrm/attendance/shift/form.html", success_url="hrm:shift_list")


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
        "hrm/attendance/shiftassignment/list.html",
        search_fields=["employee__party__name", "shift__name"],
        filters=[("shift", "shift_id", True), ("employee", "employee_id", True)],
        extra_context={"shifts": Shift.objects.filter(tenant=request.tenant).order_by("name"),
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def shiftassignment_create(request):
    return crud_create(request, form_class=ShiftAssignmentForm,
                       template="hrm/attendance/shiftassignment/form.html", success_url="hrm:shiftassignment_list")


@login_required
def shiftassignment_detail(request, pk):
    obj = get_object_or_404(
        ShiftAssignment.objects.select_related("employee__party", "shift"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/shiftassignment/detail.html", {"obj": obj})


@login_required
def shiftassignment_edit(request, pk):
    return crud_edit(request, model=ShiftAssignment, pk=pk, form_class=ShiftAssignmentForm,
                     template="hrm/attendance/shiftassignment/form.html", success_url="hrm:shiftassignment_list")


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
        request, qs, "hrm/attendance/record/list.html",
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
                       template="hrm/attendance/record/form.html", success_url="hrm:attendancerecord_list")


@login_required
def attendancerecord_detail(request, pk):
    obj = get_object_or_404(
        AttendanceRecord.objects.select_related("employee__party", "shift"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/record/detail.html", {"obj": obj})


@login_required
def attendancerecord_edit(request, pk):
    return crud_edit(request, model=AttendanceRecord, pk=pk, form_class=AttendanceRecordForm,
                     template="hrm/attendance/record/form.html", success_url="hrm:attendancerecord_list")


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
        "hrm/onboarding/template/list.html",
        search_fields=["number", "name", "designation__name"],
        filters=[("is_active", "is_active", False), ("designation", "designation_id", True)],
        extra_context={"designations": Designation.objects.filter(tenant=request.tenant).order_by("name")},
    )


@login_required
def onboardingtemplate_create(request):
    return crud_create(request, form_class=OnboardingTemplateForm,
                       template="hrm/onboarding/template/form.html",
                       success_url="hrm:onboardingtemplate_list")


@login_required
def onboardingtemplate_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTemplate.objects.select_related("designation"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/template/detail.html", {
        "obj": obj,
        "tasks": obj.template_tasks.order_by("phase", "order", "title"),
        "program_count": OnboardingProgram.objects.filter(tenant=request.tenant, template=obj).count(),
    })


@login_required
def onboardingtemplate_edit(request, pk):
    return crud_edit(request, model=OnboardingTemplate, pk=pk, form_class=OnboardingTemplateForm,
                     template="hrm/onboarding/template/form.html",
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
        "hrm/onboarding/templatetask/list.html",
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
                       template="hrm/onboarding/templatetask/form.html",
                       success_url="hrm:onboardingtemplatetask_list")


@login_required
def onboardingtemplatetask_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTemplateTask.objects.select_related("template"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/templatetask/detail.html", {"obj": obj})


@login_required
def onboardingtemplatetask_edit(request, pk):
    return crud_edit(request, model=OnboardingTemplateTask, pk=pk,
                     form_class=OnboardingTemplateTaskForm,
                     template="hrm/onboarding/templatetask/form.html",
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
        "hrm/onboarding/program/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False), ("employee", "employee_id", True)],
        extra_context={"status_choices": OnboardingProgram.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def onboardingprogram_create(request):
    return crud_create(request, form_class=OnboardingProgramForm,
                       template="hrm/onboarding/program/form.html",
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
    return render(request, "hrm/onboarding/program/detail.html", {
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
                     template="hrm/onboarding/program/form.html",
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
        "hrm/onboarding/task/list.html",
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
                       template="hrm/onboarding/task/form.html",
                       success_url="hrm:onboardingtask_list")


@login_required
def onboardingtask_detail(request, pk):
    obj = get_object_or_404(
        OnboardingTask.objects.select_related("program__employee__party", "assignee", "completed_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/task/detail.html", {"obj": obj})


@login_required
def onboardingtask_edit(request, pk):
    obj = get_object_or_404(OnboardingTask, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.error(request, "Reopen this task before editing it.")
        return redirect("hrm:onboardingtask_detail", pk=obj.pk)
    return crud_edit(request, model=OnboardingTask, pk=pk, form_class=OnboardingTaskForm,
                     template="hrm/onboarding/task/form.html", success_url="hrm:onboardingtask_list")


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
        "hrm/onboarding/document/list.html",
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
                       template="hrm/onboarding/document/form.html",
                       success_url="hrm:onboardingdocument_list")


@login_required
def onboardingdocument_detail(request, pk):
    obj = get_object_or_404(
        OnboardingDocument.objects.select_related("program__employee__party"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/document/detail.html", {"obj": obj})


@login_required
def onboardingdocument_edit(request, pk):
    return crud_edit(request, model=OnboardingDocument, pk=pk, form_class=OnboardingDocumentForm,
                     template="hrm/onboarding/document/form.html",
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
        "hrm/onboarding/assetallocation/list.html",
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
                       template="hrm/onboarding/assetallocation/form.html",
                       success_url="hrm:assetallocation_list")


@login_required
def assetallocation_detail(request, pk):
    obj = get_object_or_404(
        AssetAllocation.objects.select_related("employee__party", "program", "issued_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/assetallocation/detail.html", {"obj": obj})


@login_required
def assetallocation_edit(request, pk):
    return crud_edit(request, model=AssetAllocation, pk=pk, form_class=AssetAllocationForm,
                     template="hrm/onboarding/assetallocation/form.html", success_url="hrm:assetallocation_list")


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
        "hrm/onboarding/orientationsession/list.html",
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
                       template="hrm/onboarding/orientationsession/form.html",
                       success_url="hrm:orientationsession_list")


@login_required
def orientationsession_detail(request, pk):
    obj = get_object_or_404(
        OrientationSession.objects.select_related("employee__party", "program", "facilitator"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/onboarding/orientationsession/detail.html", {"obj": obj})


@login_required
def orientationsession_edit(request, pk):
    return crud_edit(request, model=OrientationSession, pk=pk, form_class=OrientationSessionForm,
                     template="hrm/onboarding/orientationsession/form.html",
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
        "hrm/offboarding/separationcase/list.html",
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
        request, SeparationCaseForm, "hrm/offboarding/separationcase/form.html",
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
    return render(request, "hrm/offboarding/separationcase/detail.html", {
        "obj": obj,
        "clearance_items": clearance_items,
        "clearance_total": clearance_total,
        "clearance_done": clearance_done,
        "clearance_progress": clearance_progress,
        "all_mandatory_cleared": all_mandatory_cleared,
        "exit_interview": obj.exit_interviews.select_related("interviewer").first(),
        "settlement": obj.final_settlements.first(),
    })


@login_required
def separationcase_edit(request, pk):
    obj = get_object_or_404(SeparationCase, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "pending_approval"):
        messages.error(request, "Only a draft or pending separation case can be edited.")
        return redirect("hrm:separationcase_detail", pk=obj.pk)
    return crud_edit(request, model=SeparationCase, pk=pk, form_class=SeparationCaseForm,
                     template="hrm/offboarding/separationcase/form.html",
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


@login_required
def offboarding_letters(request):
    """Landing page for the relieving/experience letters (the 'Experience Letter' sidebar bullet).
    Lists every separation case that has reached a letter-ready status (cleared/settled/completed),
    each row offering the two letter actions + showing whether each was already generated. The letters
    themselves are per-case print views — there is no standalone letter record."""
    qs = (SeparationCase.objects
          .filter(tenant=request.tenant, status__in=SeparationCase.LETTER_READY_STATUSES)
          .select_related("employee__party", "employee__designation"))
    letter_status_choices = [(s, lbl) for s, lbl in SeparationCase.STATUS_CHOICES
                             if s in SeparationCase.LETTER_READY_STATUSES]
    return crud_list(
        request, qs, "hrm/offboarding/letters.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": letter_status_choices},
    )


# ---------------------------------------------------------- Exit Interviews (3.4)
@login_required
def exitinterview_list(request):
    return crud_list(
        request,
        ExitInterview.objects.filter(tenant=request.tenant)
        .select_related("case__employee__party", "interviewer"),
        "hrm/offboarding/exitinterview/list.html",
        search_fields=["number", "case__employee__party__name", "case__number"],
        filters=[("status", "status", False), ("mode", "mode", False)],
        extra_context={"status_choices": ExitInterview.EI_STATUS_CHOICES,
                       "mode_choices": ExitInterview.MODE_CHOICES},
    )


@login_required
def exitinterview_create(request):
    return _offboarding_create(
        request, ExitInterviewForm, "hrm/offboarding/exitinterview/form.html",
        lambda obj: ("hrm:separationcase_detail", obj.case_id))


@login_required
def exitinterview_detail(request, pk):
    obj = get_object_or_404(
        ExitInterview.objects.select_related("case__employee__party", "interviewer"),
        pk=pk, tenant=request.tenant)
    ratings = [(label, getattr(obj, field)) for field, label in ExitInterview.RATING_FIELDS]
    return render(request, "hrm/offboarding/exitinterview/detail.html",
                  {"obj": obj, "ratings": ratings})


@login_required
def exitinterview_edit(request, pk):
    obj = get_object_or_404(ExitInterview, pk=pk, tenant=request.tenant)
    if obj.status == "completed":
        messages.error(request, "A completed exit interview cannot be edited.")
        return redirect("hrm:exitinterview_detail", pk=obj.pk)
    return crud_edit(request, model=ExitInterview, pk=pk, form_class=ExitInterviewForm,
                     template="hrm/offboarding/exitinterview/form.html",
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


@tenant_admin_required  # closing out an exit interview is a privileged HR action (terminal + audited)
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


@tenant_admin_required  # skipping an exit interview is a privileged HR action
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
        "hrm/offboarding/clearanceitem/list.html",
        search_fields=["description", "case__employee__party__name", "case__number"],
        filters=[("status", "status", False), ("department", "department", False),
                 ("case", "case_id", True)],
        extra_context={"status_choices": ClearanceItem.CLEARANCE_STATUS_CHOICES,
                       "dept_choices": ClearanceItem.CLEARANCE_DEPT_CHOICES,
                       "cases": SeparationCase.objects.filter(tenant=request.tenant)
                       .select_related("employee__party").order_by("-created_at")},
    )


@login_required
def clearanceitem_create(request):
    return _offboarding_create(
        request, ClearanceItemForm, "hrm/offboarding/clearanceitem/form.html",
        lambda obj: ("hrm:separationcase_detail", obj.case_id))


@login_required
def clearanceitem_detail(request, pk):
    obj = get_object_or_404(
        ClearanceItem.objects.select_related(
            "case__employee__party", "assigned_to", "cleared_by", "asset_allocation"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/offboarding/clearanceitem/detail.html", {"obj": obj})


@login_required
def clearanceitem_edit(request, pk):
    obj = get_object_or_404(ClearanceItem, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "in_progress"):
        messages.error(request, "Only a pending clearance item can be edited.")
        return redirect("hrm:clearanceitem_detail", pk=obj.pk)
    return crud_edit(request, model=ClearanceItem, pk=pk, form_class=ClearanceItemForm,
                     template="hrm/offboarding/clearanceitem/form.html",
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


@tenant_admin_required  # resolving a clearance line gates the case — privileged HR action (no
@require_POST           # per-department role yet, so admin-only mirrors clearanceitem_reject)
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


@tenant_admin_required  # marking a clearance line N/A also gates the case — privileged HR action
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
        "hrm/offboarding/finalsettlement/list.html",
        search_fields=["number", "case__employee__party__name", "case__number"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": FinalSettlement.FNF_STATUS_CHOICES},
    )


@login_required
def finalsettlement_create(request):
    return _offboarding_create(
        request, FinalSettlementForm, "hrm/offboarding/finalsettlement/form.html",
        lambda obj: ("hrm:separationcase_detail", obj.case_id))


@login_required
def finalsettlement_detail(request, pk):
    obj = get_object_or_404(
        FinalSettlement.objects.select_related("case__employee__party"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/offboarding/finalsettlement/detail.html", {"obj": obj})


@login_required
def finalsettlement_edit(request, pk):
    obj = get_object_or_404(FinalSettlement, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "computed"):
        messages.error(request, "Only a draft or computed settlement can be edited.")
        return redirect("hrm:finalsettlement_detail", pk=obj.pk)
    return crud_edit(request, model=FinalSettlement, pk=pk, form_class=FinalSettlementForm,
                     template="hrm/offboarding/finalsettlement/form.html",
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
    # Require a computed settlement — approving a raw draft would formally rubber-stamp un-computed
    # (often zero) leave-encashment/gratuity figures. Run Compute first (then edit other lines).
    if obj.status == "computed":
        obj.status = "hr_approved"
        obj.hr_approved_by = request.user
        obj.hr_approved_at = timezone.now()
        obj.save(update_fields=["status", "hr_approved_by", "hr_approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "hr_approve"})
        messages.success(request, f"Settlement {obj.number} HR-approved.")
    else:
        messages.error(request, "Run Compute first — only a computed settlement can be HR-approved.")
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


# ============================================================ 3.1 Employee Management (completion)
def _is_hr_admin(user):
    """A tenant admin (or superuser) may view confidential personnel documents."""
    return user.is_superuser or getattr(user, "is_tenant_admin", False)


def _employee_child_create(request, form_class, template, *, stamp_initiated_by=False):
    """Shared create for the employee child entities (documents / lifecycle events): tenant guard,
    ``?employee=<pk>`` pre-fill (these pages are reached from the employee detail hub), save + audit,
    then redirect back to the employee detail hub. Mirrors ``_offboarding_create``.

    Contract: every caller MUST be ``@login_required``."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    # Validate the ?employee= pk once so the template's Cancel link can't NoReverseMatch on
    # crafted input (e.g. ?employee=abc).
    emp_pk = request.GET.get("employee", "").strip()
    cancel_employee = emp_pk if emp_pk.isdigit() else None
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if stamp_initiated_by:
                obj.initiated_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect("hrm:employee_detail", pk=obj.employee_id)
    else:
        form = form_class(tenant=request.tenant,
                          initial={"employee": emp_pk} if cancel_employee else None)
    return render(request, template, {"form": form, "is_edit": False,
                                      "cancel_employee": cancel_employee})


# ---------------------------------------------------------- Employee Documents (3.1)
@login_required
def employee_document_list(request):
    qs = EmployeeDocument.objects.filter(tenant=request.tenant).select_related("employee__party")
    # Confidential documents are visible only to tenant admins.
    if not _is_hr_admin(request.user):
        qs = qs.exclude(is_confidential=True)
    return crud_list(
        request,
        qs,
        "hrm/employee/document/list.html",
        search_fields=["number", "title", "document_number", "employee__party__name"],
        filters=[("document_type", "document_type", False),
                 ("verification_status", "verification_status", False),
                 ("employee", "employee_id", True)],
        extra_context={"document_type_choices": EmployeeDocument.DOCUMENT_TYPE_CHOICES,
                       "verification_status_choices": EmployeeDocument.VERIFICATION_STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def employee_document_create(request):
    return _employee_child_create(request, EmployeeDocumentForm, "hrm/employee/document/form.html")


@login_required
def employee_document_detail(request, pk):
    obj = get_object_or_404(
        EmployeeDocument.objects.select_related("employee__party", "verified_by"),
        pk=pk, tenant=request.tenant)
    if obj.is_confidential and not _is_hr_admin(request.user):
        raise PermissionDenied("This document is marked confidential.")
    return render(request, "hrm/employee/document/detail.html", {"obj": obj})


@login_required
def employee_document_edit(request, pk):
    obj = get_object_or_404(EmployeeDocument, pk=pk, tenant=request.tenant)
    if obj.is_confidential and not _is_hr_admin(request.user):
        raise PermissionDenied("This document is marked confidential.")
    # A verified document is locked — reject it first to re-open for editing.
    if obj.verification_status == "verified":
        messages.error(request, "A verified document cannot be edited. Reject it first.")
        return redirect("hrm:employee_document_detail", pk=obj.pk)
    return crud_edit(request, model=EmployeeDocument, pk=pk, form_class=EmployeeDocumentForm,
                     template="hrm/employee/document/form.html", success_url="hrm:employee_document_list")


@login_required
@require_POST
def employee_document_delete(request, pk):
    obj = get_object_or_404(EmployeeDocument, pk=pk, tenant=request.tenant)
    if obj.is_confidential and not _is_hr_admin(request.user):
        raise PermissionDenied("This document is marked confidential.")
    if obj.verification_status == "verified":
        messages.error(request, "A verified document cannot be deleted. Reject it first.")
        return redirect("hrm:employee_document_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Document deleted.")
    return redirect("hrm:employee_document_list")


@tenant_admin_required  # verifying a personnel document is a privileged HR action
@require_POST
def employee_document_mark_verified(request, pk):
    obj = get_object_or_404(EmployeeDocument, pk=pk, tenant=request.tenant)
    if obj.verification_status == "pending":
        obj.verification_status = "verified"
        obj.verified_by = request.user
        obj.verified_at = timezone.now()
        obj.save(update_fields=["verification_status", "verified_by", "verified_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_verified"})
        messages.success(request, f"Document {obj.number} verified.")
    else:
        messages.error(request, "Only a pending document can be verified.")
    return redirect("hrm:employee_document_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def employee_document_reject(request, pk):
    obj = get_object_or_404(EmployeeDocument, pk=pk, tenant=request.tenant)
    if obj.verification_status in ("pending", "verified"):
        obj.verification_status = "rejected"
        obj.verified_by = None
        obj.verified_at = None
        obj.save(update_fields=["verification_status", "verified_by", "verified_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Document {obj.number} rejected.")
    else:
        messages.error(request, "This document is already rejected.")
    return redirect("hrm:employee_document_detail", pk=obj.pk)


# ---------------------------------------------------------- Employee Lifecycle Events (3.1)
@login_required
def employee_lifecycle_list(request):
    return crud_list(
        request,
        EmployeeLifecycleEvent.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "from_designation", "to_designation"),
        "hrm/employee/lifecycle/list.html",
        search_fields=["number", "employee__party__name", "reason", "notes"],
        filters=[("event_type", "event_type", False), ("employee", "employee_id", True)],
        extra_context={"event_type_choices": LIFECYCLE_EVENT_TYPE_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@tenant_admin_required  # lifecycle events are authoritative HR records (promotion/salary/separation)
def employee_lifecycle_create(request):
    return _employee_child_create(request, EmployeeLifecycleEventForm,
                                  "hrm/employee/lifecycle/form.html", stamp_initiated_by=True)


@login_required
def employee_lifecycle_detail(request, pk):
    obj = get_object_or_404(
        EmployeeLifecycleEvent.objects.select_related(
            "employee__party", "from_designation", "to_designation", "from_department",
            "to_department", "from_manager__party", "to_manager__party", "initiated_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/employee/lifecycle/detail.html", {"obj": obj})


@tenant_admin_required
def employee_lifecycle_edit(request, pk):
    return crud_edit(request, model=EmployeeLifecycleEvent, pk=pk,
                     form_class=EmployeeLifecycleEventForm,
                     template="hrm/employee/lifecycle/form.html",
                     success_url="hrm:employee_lifecycle_list")


@tenant_admin_required
@require_POST
def employee_lifecycle_delete(request, pk):
    return crud_delete(request, model=EmployeeLifecycleEvent, pk=pk,
                       success_url="hrm:employee_lifecycle_list")


# ============================================================ 3.5 Job Requisition
# Job Description Templates — reusable JD library (copy-on-apply onto a requisition).
@login_required
def jobdescriptiontemplate_list(request):
    return crud_list(
        request,
        JobDescriptionTemplate.objects.filter(tenant=request.tenant).select_related("designation"),
        "hrm/recruitment/jobdescriptiontemplate/list.html",
        search_fields=["number", "name", "jd_summary", "designation__name"],
        filters=[("is_active", "is_active", False), ("designation", "designation_id", True)],
        extra_context={"designations": Designation.objects.filter(tenant=request.tenant, is_active=True)
                       .order_by("name")},
    )


@tenant_admin_required  # the shared JD template library is HR-config — admin-managed
def jobdescriptiontemplate_create(request):
    return crud_create(request, form_class=JobDescriptionTemplateForm,
                       template="hrm/recruitment/jobdescriptiontemplate/form.html",
                       success_url="hrm:jobdescriptiontemplate_list")


@login_required
def jobdescriptiontemplate_detail(request, pk):
    obj = get_object_or_404(
        JobDescriptionTemplate.objects.select_related("designation"), pk=pk, tenant=request.tenant)
    linked_reqs = (JobRequisition.objects.filter(tenant=request.tenant, template=obj)
                   .order_by("-created_at")[:10])
    return render(request, "hrm/recruitment/jobdescriptiontemplate/detail.html",
                  {"obj": obj, "linked_reqs": linked_reqs})


@tenant_admin_required  # the shared JD template library is HR-config — admin-managed
def jobdescriptiontemplate_edit(request, pk):
    return crud_edit(request, model=JobDescriptionTemplate, pk=pk,
                     form_class=JobDescriptionTemplateForm,
                     template="hrm/recruitment/jobdescriptiontemplate/form.html",
                     success_url="hrm:jobdescriptiontemplate_list")


@tenant_admin_required  # the shared JD template library is HR-config — admin-managed
@require_POST
def jobdescriptiontemplate_delete(request, pk):
    obj = get_object_or_404(JobDescriptionTemplate, pk=pk, tenant=request.tenant)
    # Guard: a template referenced by requisitions is kept for the record — deactivate instead.
    if JobRequisition.objects.filter(tenant=request.tenant, template=obj).exists():
        messages.error(request, "Cannot delete a template used by requisitions. Deactivate it instead.")
        return redirect("hrm:jobdescriptiontemplate_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Job description template deleted.")
    return redirect("hrm:jobdescriptiontemplate_list")


# Job Requisitions — the hub record + its approval-chain state machine.
@login_required
def jobrequisition_list(request):
    return crud_list(
        request,
        JobRequisition.objects.filter(tenant=request.tenant)
        .select_related("designation", "department", "hiring_manager__party", "recruiter__party"),
        "hrm/recruitment/jobrequisition/list.html",
        search_fields=["number", "title", "location", "designation__name"],
        filters=[("status", "status", False), ("priority", "priority", False),
                 ("department", "department_id", True), ("hiring_manager", "hiring_manager_id", True),
                 ("req_type", "req_type", False), ("employment_type", "employment_type", False)],
        extra_context={"status_choices": JR_STATUS_CHOICES,
                       "priority_choices": PRIORITY_CHOICES,
                       "req_type_choices": REQ_TYPE_CHOICES,
                       "employment_type_choices": EMPLOYMENT_TYPE_CHOICES,
                       "departments": OrgUnit.objects.filter(tenant=request.tenant, kind="department")
                       .order_by("name"),
                       "hiring_managers": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@tenant_admin_required  # a requisition authorizes headcount + budget — authoritative HR record
def jobrequisition_create(request):
    # Custom create (not crud_create) so the "Save & Apply Template" button can copy the selected
    # template's JD body onto the new requisition in the same request.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = JobRequisitionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            if request.POST.get("apply_template") and obj.template_id:
                apply_template_to_requisition(obj, obj.template)
                messages.success(request, f"Requisition {obj.number} created; "
                                 f"template '{obj.template.name}' applied.")
            else:
                messages.success(request, f"Requisition {obj.number} created.")
            return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    else:
        form = JobRequisitionForm(tenant=request.tenant)
    return render(request, "hrm/recruitment/jobrequisition/form.html",
                  {"form": form, "is_edit": False})


@login_required
def jobrequisition_detail(request, pk):
    obj = get_object_or_404(
        JobRequisition.objects.select_related(
            "designation__job_grade", "job_grade", "department", "cost_center",
            "hiring_manager__party", "recruiter__party", "template"),
        pk=pk, tenant=request.tenant)
    approvals = list(obj.approvals.select_related("approver", "decided_by").order_by("step_order"))
    approved_count = sum(1 for a in approvals if a.status == "approved")
    total_count = len(approvals)
    approval_progress = int(round(approved_count / total_count * 100)) if total_count else 0
    # Current pending step (lowest order) computed from the already-fetched list (no extra query).
    current_step = next((a for a in approvals if a.status == "pending"), None)
    # 3.6 — surface the applicants on the requisition hub (was a dead-end before Candidate Management).
    applications = list(obj.applications.select_related("candidate").order_by("-applied_at")[:10])
    application_count = obj.applications.count()
    return render(request, "hrm/recruitment/jobrequisition/detail.html", {
        "obj": obj,
        "approvals": approvals,
        "approved_count": approved_count,
        "total_count": total_count,
        "approval_progress": approval_progress,
        "current_step": current_step,
        "applications": applications,
        "application_count": application_count,
        "approval_form": RequisitionApprovalForm(tenant=request.tenant),
        "is_hr_admin": _is_hr_admin(request.user),  # gates the admin-only action UI in the template
        "jd_templates": JobDescriptionTemplate.objects.filter(tenant=request.tenant, is_active=True)
        .only("id", "name").order_by("name"),  # dropdown uses pk+name only (skip the jd_* TEXT cols)
        "can_submit": obj.status in ("draft", "rejected"),
        "can_approve": obj.status == "pending_approval",
        "can_post": obj.status == "approved",
        "can_hold": obj.status in ("approved", "posted"),
        "can_fill": obj.status in ("posted", "on_hold"),
        "can_cancel": obj.status not in ("filled", "cancelled"),
        "can_edit": obj.status in ("draft", "rejected"),
    })


@tenant_admin_required  # a requisition authorizes headcount + budget — authoritative HR record
def jobrequisition_edit(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    # Only a draft or rejected req is editable — once it's in the approval flow its terms are locked.
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "Only a draft or rejected requisition can be edited.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    return crud_edit(request, model=JobRequisition, pk=pk, form_class=JobRequisitionForm,
                     template="hrm/recruitment/jobrequisition/form.html",
                     success_url="hrm:jobrequisition_list")


@tenant_admin_required  # a requisition authorizes headcount + budget — authoritative HR record
@require_POST
def jobrequisition_delete(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    # Only a draft req is deletable — once submitted it is cancelled (keeps the audit trail).
    if obj.status != "draft":
        messages.error(request, "Only a draft requisition can be deleted. Cancel it instead.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Requisition deleted.")
    return redirect("hrm:jobrequisition_list")


# --- Approval chain steps (inline on the requisition hub; admin-only, steps only before submit) ---
@tenant_admin_required
@require_POST
def approval_add(request, jr_pk):
    req = get_object_or_404(JobRequisition, pk=jr_pk, tenant=request.tenant)
    if req.status != "draft":
        messages.error(request, "Approval steps can only be added while the requisition is a draft.")
        return redirect("hrm:jobrequisition_detail", pk=req.pk)
    form = RequisitionApprovalForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        step = form.save(commit=False)
        step.tenant = request.tenant
        step.requisition = req
        step.status = "pending"
        try:
            step.save()
        except IntegrityError:
            messages.error(request, f"An approval step #{step.step_order} already exists.")
            return redirect("hrm:jobrequisition_detail", pk=req.pk)
        write_audit_log(request.user, step, "create", {"action": "add_approval_step",
                                                        "step": step.step_order})
        messages.success(request, f"Approval step #{step.step_order} added.")
    else:
        messages.error(request, "Could not add the approval step — check the step order and approver.")
    return redirect("hrm:jobrequisition_detail", pk=req.pk)


@tenant_admin_required
@require_POST
def approval_delete(request, pk):
    step = get_object_or_404(RequisitionApproval.objects.select_related("requisition"),
                             pk=pk, tenant=request.tenant)
    req = step.requisition
    if req.status != "draft":
        messages.error(request, "Approval steps can only be removed while the requisition is a draft.")
        return redirect("hrm:jobrequisition_detail", pk=req.pk)
    write_audit_log(request.user, step, "delete", {"action": "remove_approval_step",
                                                   "step": step.step_order})
    step.delete()
    messages.success(request, "Approval step removed.")
    return redirect("hrm:jobrequisition_detail", pk=req.pk)


# --- Workflow state-machine actions (all privileged; the form never sets these fields) ---
@tenant_admin_required
@require_POST
def jobrequisition_submit(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    # A rejected requisition can be edited and re-submitted (mirrors the editable-when-rejected guard).
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "Only a draft or rejected requisition can be submitted.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    with transaction.atomic():
        # On re-submit of a rejected req, reset the prior chain so it re-approves from the top.
        if obj.status == "rejected":
            obj.approvals.update(status="pending", decided_at=None, decided_by=None, comments="")
        generate_approval_chain(obj)  # idempotent: builds the default chain only when none exist
        obj.status = "pending_approval"
        obj.submitted_at = timezone.now()
        obj.save(update_fields=["status", "submitted_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit", "to": obj.status})
    messages.success(request, f"Requisition {obj.number} submitted for approval.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_approve_step(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(request, "Only a requisition pending approval can be approved.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    step = obj.approvals.filter(status="pending").order_by("step_order").first()
    if step is None:
        messages.error(request, "No pending approval step to approve.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    with transaction.atomic():
        step.status = "approved"
        step.decided_at = timezone.now()
        step.decided_by = request.user
        step.save(update_fields=["status", "decided_at", "decided_by", "updated_at"])
        # When the last pending step clears, the whole requisition is approved.
        if not obj.approvals.filter(status="pending").exists():
            obj.status = "approved"
            obj.approved_at = timezone.now()
            obj.save(update_fields=["status", "approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update",
                        {"action": "approve_step", "step": step.step_order, "to": obj.status})
    if obj.status == "approved":
        messages.success(request, f"Final approval recorded — {obj.number} is approved.")
    else:
        messages.success(request, f"Approval step #{step.step_order} approved.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_reject(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(request, "Only a requisition pending approval can be rejected.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    step = obj.approvals.filter(status="pending").order_by("step_order").first()
    with transaction.atomic():
        if step is not None:
            step.status = "rejected"
            step.decided_at = timezone.now()
            step.decided_by = request.user
            step.comments = request.POST.get("comments", "").strip()[:2000]
            step.save(update_fields=["status", "decided_at", "decided_by", "comments", "updated_at"])
        obj.status = "rejected"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Requisition {obj.number} rejected.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_return(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(request, "Only a requisition pending approval can be returned for revision.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    step = obj.approvals.filter(status="pending").order_by("step_order").first()
    with transaction.atomic():
        if step is not None:
            step.status = "returned"
            step.decided_at = timezone.now()
            step.decided_by = request.user
            step.comments = request.POST.get("comments", "").strip()[:2000]
            step.save(update_fields=["status", "decided_at", "decided_by", "comments", "updated_at"])
        # Reset the chain so a fresh submit re-approves from the top, and reopen the req for editing.
        obj.approvals.exclude(pk=step.pk if step else None).update(
            status="pending", decided_at=None, decided_by=None, comments="")
        obj.status = "draft"
        obj.submitted_at = None
        obj.save(update_fields=["status", "submitted_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "return"})
    messages.success(request, f"Requisition {obj.number} returned for revision.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_post(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved requisition can be posted.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    obj.status = "posted"
    obj.posted_at = timezone.now()
    fields = ["status", "posted_at", "updated_at"]
    # Mint the public careers-portal token once (3.6) so the posted opening gets a shareable apply URL.
    if not obj.public_token:
        obj.public_token = secrets.token_urlsafe(32)
        fields.append("public_token")
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": "post"})
    messages.success(request, f"Requisition {obj.number} posted.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_hold(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status not in ("approved", "posted"):
        messages.error(request, "Only an approved or posted requisition can be placed on hold.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    obj.status = "on_hold"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "hold"})
    messages.success(request, f"Requisition {obj.number} placed on hold.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_mark_filled(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status not in ("posted", "on_hold"):
        messages.error(request, "Only a posted or on-hold requisition can be marked filled.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    obj.status = "filled"
    obj.filled_at = timezone.now()
    obj.save(update_fields=["status", "filled_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "fill"})
    messages.success(request, f"Requisition {obj.number} marked filled.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_cancel(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status in ("filled", "cancelled"):
        messages.error(request, "This requisition can no longer be cancelled.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Requisition {obj.number} cancelled.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def jobrequisition_apply_template(request, pk):
    obj = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    if obj.status not in ("draft", "rejected"):
        messages.error(request, "A template can only be applied to a draft or rejected requisition.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    template_id = request.POST.get("template_id", "").strip()
    if not template_id.isdigit():
        messages.error(request, "Select a template to apply.")
        return redirect("hrm:jobrequisition_detail", pk=obj.pk)
    tmpl = get_object_or_404(JobDescriptionTemplate, pk=int(template_id), tenant=request.tenant)
    apply_template_to_requisition(obj, tmpl)
    write_audit_log(request.user, obj, "update", {"action": "apply_template", "template": tmpl.name})
    messages.success(request, f"Template '{tmpl.name}' applied to {obj.number}.")
    return redirect("hrm:jobrequisition_detail", pk=obj.pk)


# Fields copied when a requisition is cloned (everything except workflow-owned + identity columns).
# FKs are copied by ``<name>_id`` so no extra query is needed; plain columns by attribute.
_JR_CLONE_FK_FIELDS = ["designation", "job_grade", "template", "department", "cost_center",
                       "hiring_manager", "recruiter"]
_JR_CLONE_PLAIN_FIELDS = ["title", "location", "headcount", "req_type", "employment_type",
                          "reason_for_hire", "is_replacement_for", "posting_type",
                          "target_start_date", "priority", "salary_min", "salary_max",
                          "salary_currency", "estimated_annual_cost", "hiring_cost_budget",
                          "jd_summary", "jd_responsibilities", "jd_requirements",
                          "jd_nice_to_have", "notes"]


@tenant_admin_required  # cloning creates a new requisition — authoritative HR record
@require_POST
def jobrequisition_clone(request, pk):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before cloning records.")
        return redirect("dashboard:home")
    source = get_object_or_404(JobRequisition, pk=pk, tenant=request.tenant)
    new_req = JobRequisition(tenant=request.tenant)  # status defaults to draft; *_at stamps stay null
    for field in _JR_CLONE_FK_FIELDS:
        setattr(new_req, f"{field}_id", getattr(source, f"{field}_id"))
    for field in _JR_CLONE_PLAIN_FIELDS:
        setattr(new_req, field, getattr(source, field))
    new_req.save()
    write_audit_log(request.user, new_req, "create", {"cloned_from": source.number})
    messages.success(request, f"Requisition cloned from {source.number} as {new_req.number}.")
    return redirect("hrm:jobrequisition_detail", pk=new_req.pk)


# ===========================================================================
# 3.6 Candidate Management — candidates, applications, tags, email templates,
# communications, and the public career portal.
# ===========================================================================

# Stage → the auto-send template type fired when an application advances into that stage.
_STAGE_AUTO_TEMPLATE = {
    "screening": "shortlisted",
    "phone_screen": "phone_screen_invite",
    "assessment": "assessment_invite",
    "interview": "interview_invite",
    "offer": "offer",
}


def _user_display(user):
    if user is None:
        return ""
    return user.get_full_name() or user.get_username()


def _apply_merge(text, ctx):
    for key, value in ctx.items():
        text = text.replace(key, str(value))
    return text


def _send_candidate_email(application, *, template=None, template_type=None, subject=None, body=None,
                          sent_by=None):
    """Render merge fields, send a candidate email (console backend in dev), and log an append-only
    ``CandidateCommunication``. Honors ``do_not_contact`` (skips, returns None). Resolves a template by
    instance or by an active type. Returns the logged row, or None when nothing was sent."""
    candidate = application.candidate
    if candidate.do_not_contact:
        return None
    tenant = application.tenant
    if template is None and template_type:
        template = (CandidateEmailTemplate.objects
                    .filter(tenant=tenant, template_type=template_type, is_active=True)
                    .order_by("pk").first())
    if subject is None and template is not None:
        subject = template.subject
    if body is None and template is not None:
        body = template.body_html
    if not body:
        return None
    ctx = {
        "{{candidate_name}}": candidate.name,
        "{{job_title}}": application.requisition.title,
        "{{company_name}}": getattr(tenant, "name", ""),
        "{{recruiter_name}}": _user_display(sent_by) or "the hiring team",
        "{{application_number}}": application.number or "",
    }
    subject = _apply_merge(subject or "", ctx)
    body = _apply_merge(body, ctx)
    status = "sent"
    try:
        sent = send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [candidate.email])
        status = "sent" if sent else "failed"
    except Exception:  # never let a mail/transport failure 500 the request — log it as failed instead
        status = "failed"
    return CandidateCommunication.objects.create(
        tenant=tenant, candidate=candidate, application=application, template=template,
        channel="email", direction="outbound", subject=subject[:500], body=body,
        sent_by=sent_by, delivery_status=status)


def _auto_send_for_stage(application, stage, sent_by):
    """Fire the matching ``is_auto_send`` template (if any) for a stage transition."""
    template_type = _STAGE_AUTO_TEMPLATE.get(stage)
    if not template_type:
        return
    template = (CandidateEmailTemplate.objects
                .filter(tenant=application.tenant, template_type=template_type,
                        is_active=True, is_auto_send=True)
                .order_by("pk").first())
    if template is not None:
        _send_candidate_email(application, template=template, sent_by=sent_by)


# --------------------------------------------------------------- Candidates (3.6) CRUD + hub
@login_required
def candidate_list(request):
    # The Count annotation's GROUP BY already collapses the skill/tag join-filter rows to one per
    # candidate; .distinct() makes that explicit so the list stays unique even if the annotation changes.
    qs = (CandidateProfile.objects.filter(tenant=request.tenant)
          .select_related("party").prefetch_related("tags", "skills")
          .annotate(application_count=Count("applications", distinct=True))
          .order_by("-created_at").distinct())
    return crud_list(
        request, qs, "hrm/candidates/candidate/list.html",
        search_fields=["first_name", "last_name", "email", "phone", "current_job_title",
                       "current_employer", "skill_set", "resume_text", "number"],
        filters=[("status", "status", False), ("source", "source", False),
                 ("gender", "gender", False), ("qualification", "highest_qualification", False),
                 ("tag", "tags__id", True), ("skill", "skills__skill_name__icontains", False)],
        extra_context={
            "status_choices": CANDIDATE_STATUS_CHOICES,
            "source_choices": CANDIDATE_SOURCE_CHOICES,
            "gender_choices": CANDIDATE_GENDER_CHOICES,
            "qualification_choices": QUALIFICATION_CHOICES,
            "tags": CandidateTag.objects.filter(tenant=request.tenant).only("pk", "name", "color"),
        },
    )


@login_required
def candidate_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = CandidateProfileForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            cd = form.cleaned_data
            with transaction.atomic():
                party = Party.objects.create(
                    tenant=request.tenant, kind="person",
                    name=f"{cd['first_name']} {cd['last_name']}".strip())
                PartyRole.objects.create(tenant=request.tenant, party=party, role="candidate")
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                obj.party = party
                # Stamp the consent timestamp when a staff member records consent (the public apply
                # flow does the same), so a ticked consent is never left undated.
                if obj.gdpr_consent and not obj.gdpr_consent_date:
                    obj.gdpr_consent_date = timezone.now()
                obj.save()
                form.save_m2m()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Candidate {obj.number} created.")
            return redirect("hrm:candidate_detail", pk=obj.pk)
    else:
        form = CandidateProfileForm(tenant=request.tenant)
    return render(request, "hrm/candidates/candidate/form.html", {"form": form, "is_edit": False})


@login_required
def candidate_detail(request, pk):
    obj = get_object_or_404(
        CandidateProfile.objects.filter(tenant=request.tenant).select_related("party", "sourced_by"),
        pk=pk)
    applications = (obj.applications.select_related("requisition").order_by("-applied_at")[:25])
    communications = (obj.communications.select_related("template", "sent_by").order_by("-sent_at")[:20])
    return render(request, "hrm/candidates/candidate/detail.html", {
        "obj": obj,
        "skills": obj.skills.all(),
        "applications": applications,
        "communications": communications,
        "candidate_tags": obj.tags.all(),
        "all_tags": CandidateTag.objects.filter(tenant=request.tenant),
        "skill_form": CandidateSkillForm(tenant=request.tenant),
    })


@login_required
def candidate_edit(request, pk):
    obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = CandidateProfileForm(request.POST, request.FILES, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            # Stamp the consent timestamp the first time consent is recorded via the staff form.
            if obj.gdpr_consent and not obj.gdpr_consent_date:
                obj.gdpr_consent_date = timezone.now()
                obj.save(update_fields=["gdpr_consent_date"])
            # Keep the Party display name in sync with the denormalized candidate name.
            new_name = obj.name
            if obj.party_id and obj.party.name != new_name:
                obj.party.name = new_name
                obj.party.save(update_fields=["name"])
            write_audit_log(request.user, obj, "update")
            messages.success(request, "Candidate updated.")
            return redirect("hrm:candidate_detail", pk=obj.pk)
    else:
        form = CandidateProfileForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/candidates/candidate/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required  # destructive — cascades the Party, its roles, applications and communications
@require_POST
def candidate_delete(request, pk):
    obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant)
                            .select_related("party"), pk=pk)
    party = obj.party
    with transaction.atomic():
        # Audit inside the transaction so the row only survives if the delete commits.
        write_audit_log(request.user, obj, "delete")
        # The candidate Party is dedicated (minted per candidate); deleting it cascades the profile,
        # its PartyRole, skills, applications and communications in one shot.
        if party_has_only_candidate_role(party):
            party.delete()
        else:
            obj.delete()
    messages.success(request, "Candidate deleted.")
    return redirect("hrm:candidate_list")


def party_has_only_candidate_role(party):
    roles = set(party.roles.filter(tenant=party.tenant_id).values_list("role", flat=True))
    return roles <= {"candidate"}


@login_required
@require_POST
def candidate_mark_hired(request, pk):
    obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    obj.status = "hired"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "mark_hired"})
    messages.success(request, f"{obj.name} marked as hired.")
    return redirect("hrm:candidate_detail", pk=obj.pk)


@tenant_admin_required  # contact-suppression is an authoritative HR decision
@require_POST
def candidate_blacklist(request, pk):
    obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    obj.status = "blacklisted"
    obj.do_not_contact = True
    obj.save(update_fields=["status", "do_not_contact", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "blacklist"})
    messages.success(request, f"{obj.name} blacklisted and marked do-not-contact.")
    return redirect("hrm:candidate_detail", pk=obj.pk)


@tenant_admin_required  # inverse of blacklist — same authoritative bar
@require_POST
def candidate_restore(request, pk):
    obj = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    obj.status = "active"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "restore"})
    messages.success(request, f"{obj.name} restored to active.")
    return redirect("hrm:candidate_detail", pk=obj.pk)


@login_required
@require_POST
def candidate_skill_add(request, pk):
    candidate = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    form = CandidateSkillForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        cd = form.cleaned_data
        CandidateSkill.objects.get_or_create(
            candidate=candidate, skill_name=cd["skill_name"],
            defaults={"tenant": request.tenant, "proficiency": cd["proficiency"],
                      "source": cd["source"]})
        messages.success(request, "Skill added.")
    else:
        messages.error(request, "Enter a skill name.")
    return redirect("hrm:candidate_detail", pk=candidate.pk)


@login_required
@require_POST
def candidate_skill_delete(request, pk, skill_pk):
    candidate = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    skill = get_object_or_404(CandidateSkill, pk=skill_pk, candidate=candidate, tenant=request.tenant)
    skill.delete()
    messages.success(request, "Skill removed.")
    return redirect("hrm:candidate_detail", pk=candidate.pk)


@login_required
@require_POST
def candidate_tag_add(request, pk):
    candidate = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    tag = get_object_or_404(CandidateTag, pk=request.POST.get("tag"), tenant=request.tenant)
    candidate.tags.add(tag)
    messages.success(request, f'Tag "{tag.name}" added.')
    return redirect("hrm:candidate_detail", pk=candidate.pk)


@login_required
@require_POST
def candidate_tag_remove(request, pk, tag_pk):
    candidate = get_object_or_404(CandidateProfile.objects.filter(tenant=request.tenant), pk=pk)
    tag = get_object_or_404(CandidateTag, pk=tag_pk, tenant=request.tenant)
    candidate.tags.remove(tag)
    messages.success(request, f'Tag "{tag.name}" removed.')
    return redirect("hrm:candidate_detail", pk=candidate.pk)


# --------------------------------------------------------------- Job Applications (3.6)
@login_required
def application_list(request):
    qs = (JobApplication.objects.filter(tenant=request.tenant)
          .select_related("candidate", "requisition", "referred_by__party"))
    return crud_list(
        request, qs, "hrm/candidates/application/list.html",
        search_fields=["number", "candidate__first_name", "candidate__last_name",
                       "candidate__email", "requisition__title", "requisition__number"],
        filters=[("stage", "stage", False), ("source", "source", False),
                 ("requisition", "requisition_id", True), ("candidate", "candidate_id", True)],
        extra_context={
            "stage_choices": APPLICATION_STAGE_CHOICES,
            "source_choices": CANDIDATE_SOURCE_CHOICES,
            "requisitions": JobRequisition.objects.filter(tenant=request.tenant).only("pk", "number", "title"),
            "candidates": CandidateProfile.objects.filter(tenant=request.tenant)
            .only("pk", "first_name", "last_name", "number"),
        },
    )


@login_required
def application_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = JobApplicationForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Application {obj.number} created.")
            # Land on the new application so the recruiter can immediately work its pipeline.
            return redirect("hrm:application_detail", pk=obj.pk)
    else:
        # Pre-select the candidate/requisition when arriving from a candidate hub or a requisition hub.
        form = JobApplicationForm(tenant=request.tenant, initial={
            "candidate": request.GET.get("candidate") or None,
            "requisition": request.GET.get("requisition") or None,
        })
    return render(request, "hrm/candidates/application/form.html", {"form": form, "is_edit": False})


@login_required
def application_detail(request, pk):
    obj = get_object_or_404(
        JobApplication.objects.filter(tenant=request.tenant)
        .select_related("candidate__party", "requisition", "referred_by__party"), pk=pk)
    return render(request, "hrm/candidates/application/detail.html", {
        "obj": obj,
        "communications": obj.communications.select_related("template", "sent_by").order_by("-sent_at")[:50],
        "email_templates": CandidateEmailTemplate.objects.filter(tenant=request.tenant, is_active=True),
        "stage_choices": APPLICATION_STAGE_CHOICES,
        "rejection_reason_choices": REJECTION_REASON_CHOICES,
    })


@login_required
def application_edit(request, pk):
    return crud_edit(
        request, model=JobApplication, pk=pk, form_class=JobApplicationForm,
        template="hrm/candidates/application/form.html",
        success_url="hrm:application_list")


@login_required
@require_POST
def application_delete(request, pk):
    return crud_delete(request, model=JobApplication, pk=pk, success_url="hrm:application_list")


@login_required
@require_POST
def application_advance_stage(request, pk):
    obj = get_object_or_404(
        JobApplication.objects.filter(tenant=request.tenant).select_related("candidate", "requisition"),
        pk=pk)
    new_stage = request.POST.get("new_stage", "")
    valid = dict(APPLICATION_STAGE_CHOICES)
    if new_stage not in valid:
        messages.error(request, "Invalid stage.")
        return redirect("hrm:application_detail", pk=obj.pk)
    if obj.stage in APPLICATION_TERMINAL_STAGES:
        messages.error(request, "This application is closed. Reopen it before changing the stage.")
        return redirect("hrm:application_detail", pk=obj.pk)
    obj.stage = new_stage
    obj.stage_changed_at = timezone.now()
    fields = ["stage", "stage_changed_at", "updated_at"]
    if new_stage == "hired":
        obj.hired_on = _date.today()
        fields.append("hired_on")
        if obj.candidate.status != "hired":
            obj.candidate.status = "hired"
            obj.candidate.save(update_fields=["status", "updated_at"])
    obj.save(update_fields=fields)
    write_audit_log(request.user, obj, "update", {"action": "advance_stage", "stage": new_stage})
    _auto_send_for_stage(obj, new_stage, request.user)
    messages.success(request, f"Application moved to {valid[new_stage]}.")
    return redirect("hrm:application_detail", pk=obj.pk)


@login_required
@require_POST
def application_reject(request, pk):
    obj = get_object_or_404(
        JobApplication.objects.filter(tenant=request.tenant).select_related("candidate", "requisition"),
        pk=pk)
    if obj.stage in APPLICATION_TERMINAL_STAGES:
        messages.error(request, "This application is already closed.")
        return redirect("hrm:application_detail", pk=obj.pk)
    reason = request.POST.get("rejection_reason", "")
    if reason and reason not in dict(REJECTION_REASON_CHOICES):
        reason = "other"
    obj.stage = "rejected"
    obj.stage_changed_at = timezone.now()
    obj.rejection_reason = reason
    obj.rejection_notes = request.POST.get("rejection_notes", "").strip()
    obj.save(update_fields=["stage", "stage_changed_at", "rejection_reason", "rejection_notes", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject", "reason": reason})
    template = (CandidateEmailTemplate.objects
                .filter(tenant=request.tenant, template_type="rejection", is_active=True, is_auto_send=True)
                .order_by("pk").first())
    if template is not None:
        _send_candidate_email(obj, template=template, sent_by=request.user)
    messages.success(request, "Application rejected.")
    return redirect("hrm:application_detail", pk=obj.pk)


@login_required
@require_POST
def application_withdraw(request, pk):
    obj = get_object_or_404(JobApplication.objects.filter(tenant=request.tenant), pk=pk)
    if obj.stage in APPLICATION_TERMINAL_STAGES:
        messages.error(request, "This application is already closed.")
        return redirect("hrm:application_detail", pk=obj.pk)
    obj.stage = "withdrawn"
    obj.stage_changed_at = timezone.now()
    obj.save(update_fields=["stage", "stage_changed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "withdraw"})
    messages.success(request, "Application withdrawn.")
    return redirect("hrm:application_detail", pk=obj.pk)


@login_required
@require_POST
def application_hold(request, pk):
    obj = get_object_or_404(
        JobApplication.objects.filter(tenant=request.tenant).select_related("candidate", "requisition"),
        pk=pk)
    if obj.stage in APPLICATION_TERMINAL_STAGES:
        messages.error(request, "This application is already closed.")
        return redirect("hrm:application_detail", pk=obj.pk)
    obj.stage = "on_hold"
    obj.stage_changed_at = timezone.now()
    obj.save(update_fields=["stage", "stage_changed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "hold"})
    template = (CandidateEmailTemplate.objects
                .filter(tenant=request.tenant, template_type="on_hold", is_active=True, is_auto_send=True)
                .order_by("pk").first())
    if template is not None:
        _send_candidate_email(obj, template=template, sent_by=request.user)
    messages.success(request, "Application placed on hold.")
    return redirect("hrm:application_detail", pk=obj.pk)


@login_required
@require_POST
def application_send_email(request, pk):
    obj = get_object_or_404(
        JobApplication.objects.filter(tenant=request.tenant).select_related("candidate", "requisition"),
        pk=pk)
    if obj.candidate.do_not_contact:
        messages.error(request, "This candidate is marked do-not-contact; email not sent.")
        return redirect("hrm:application_detail", pk=obj.pk)
    template = None
    template_id = request.POST.get("template_id")
    if template_id:
        template = CandidateEmailTemplate.objects.filter(
            tenant=request.tenant, pk=template_id).first()
    subject = request.POST.get("subject", "").strip() or None
    body = request.POST.get("body", "").strip() or None
    if not body and template is None:
        messages.error(request, "Pick a template or write a message body.")
        return redirect("hrm:application_detail", pk=obj.pk)
    comm = _send_candidate_email(obj, template=template, subject=subject, body=body, sent_by=request.user)
    if comm is None:
        messages.error(request, "Nothing to send.")
    else:
        write_audit_log(request.user, comm, "create", {"to": obj.candidate.email})
        messages.success(request, f"Email sent to {obj.candidate.name}.")
    return redirect("hrm:application_detail", pk=obj.pk)


# --------------------------------------------------------------- Candidate Tags (3.6)
@login_required
def candidatetag_list(request):
    return crud_list(
        request, CandidateTag.objects.filter(tenant=request.tenant)
        .annotate(candidate_count=Count("candidates", distinct=True)).order_by("name"),
        "hrm/candidates/tag/list.html",
        search_fields=["name", "description"])


@login_required
def candidatetag_create(request):
    return crud_create(request, form_class=CandidateTagForm, template="hrm/candidates/tag/form.html",
                       success_url="hrm:candidatetag_list")


@login_required
def candidatetag_edit(request, pk):
    return crud_edit(request, model=CandidateTag, pk=pk, form_class=CandidateTagForm,
                     template="hrm/candidates/tag/form.html", success_url="hrm:candidatetag_list")


@login_required
@require_POST
def candidatetag_delete(request, pk):
    return crud_delete(request, model=CandidateTag, pk=pk, success_url="hrm:candidatetag_list")


# --------------------------------------------------------------- Candidate Email Templates (3.6)
@login_required
def emailtemplate_list(request):
    return crud_list(
        request, CandidateEmailTemplate.objects.filter(tenant=request.tenant),
        "hrm/candidates/emailtemplate/list.html",
        search_fields=["name", "subject", "number"],
        filters=[("type", "template_type", False), ("active", "is_active", False)],
        extra_context={"type_choices": EMAIL_TEMPLATE_TYPE_CHOICES})


@tenant_admin_required  # templates auto-fire to external candidate emails — admin-authored only
def emailtemplate_create(request):
    return crud_create(request, form_class=CandidateEmailTemplateForm,
                       template="hrm/candidates/emailtemplate/form.html",
                       success_url="hrm:emailtemplate_list")


@login_required
def emailtemplate_detail(request, pk):
    return crud_detail(request, model=CandidateEmailTemplate, pk=pk,
                       template="hrm/candidates/emailtemplate/detail.html")


@tenant_admin_required  # templates auto-fire to external candidate emails — admin-authored only
def emailtemplate_edit(request, pk):
    return crud_edit(request, model=CandidateEmailTemplate, pk=pk, form_class=CandidateEmailTemplateForm,
                     template="hrm/candidates/emailtemplate/form.html",
                     success_url="hrm:emailtemplate_list")


@tenant_admin_required
@require_POST
def emailtemplate_delete(request, pk):
    return crud_delete(request, model=CandidateEmailTemplate, pk=pk, success_url="hrm:emailtemplate_list")


# --------------------------------------------------------------- Candidate Communications (3.6, read-only)
@login_required
def communication_list(request):
    return crud_list(
        request, CandidateCommunication.objects.filter(tenant=request.tenant)
        .select_related("candidate", "application", "sent_by"),
        "hrm/candidates/communication/list.html",
        search_fields=["number", "subject", "body", "candidate__first_name", "candidate__last_name"],
        filters=[("channel", "channel", False), ("status", "delivery_status", False),
                 ("candidate", "candidate_id", True)],
        extra_context={
            "channel_choices": COMMUNICATION_CHANNEL_CHOICES,
            "delivery_status_choices": DELIVERY_STATUS_CHOICES,
            "candidates": CandidateProfile.objects.filter(tenant=request.tenant)
            .only("pk", "first_name", "last_name", "number"),
        })


@login_required
def communication_detail(request, pk):
    return crud_detail(request, model=CandidateCommunication, pk=pk,
                       template="hrm/candidates/communication/detail.html",
                       select_related=("candidate", "application", "template", "sent_by"))


# --------------------------------------------------------------- Public career portal (3.6, UNAUTHENTICATED)
# WARNING: these two views are intentionally login-free. The requisition's unguessable public_token is
# the bearer credential. Add per-IP rate-limiting (django-ratelimit) / WAF throttling in production to
# stop scripted application floods. CSRF is enforced by the form's {% csrf_token %}; tenant-authored
# text is rendered ESCAPED by the templates.
def careers_list(request):
    """Public job board for ONE tenant, resolved via ``?tenant=<slug>`` (no cross-tenant listing)."""
    slug = request.GET.get("tenant", "").strip()
    tenant_obj = None
    requisitions = JobRequisition.objects.none()
    # Anonymous visitors pin the tenant via ?tenant=<slug>; a logged-in staff member with no slug
    # sees their own workspace's openings (so the sidebar "Public Careers Page" link isn't blank).
    if not slug and getattr(request, "tenant", None) is not None:
        tenant_obj = request.tenant
        slug = request.tenant.slug
    elif slug:
        from apps.core.models import Tenant
        tenant_obj = Tenant.objects.filter(slug=slug, is_active=True).first()
    if tenant_obj is not None:
        requisitions = (JobRequisition.objects
                        .filter(tenant=tenant_obj, status="posted",
                                posting_type__in=["external", "both"])
                        .exclude(public_token__isnull=True)  # only tokenized openings have a working Apply link
                        .select_related("department", "designation").order_by("-posted_at"))
    return render(request, "hrm/candidates/careers_list.html", {
        "tenant_obj": tenant_obj, "slug": slug, "requisitions": requisitions,
        "submitted": request.GET.get("submitted") == "1"})


def careers_apply(request, token):
    """Public application page for one posted requisition (resolved by its public_token)."""
    req = get_object_or_404(
        JobRequisition.objects.select_related("tenant", "department"),
        public_token=token, status="posted")
    form = PublicApplicationForm()
    if request.method == "POST":
        form = PublicApplicationForm(request.POST, request.FILES)
        if form.is_valid():
            cd = form.cleaned_data
            with transaction.atomic():
                candidate = (CandidateProfile.objects
                             .filter(tenant=req.tenant, email__iexact=cd["email"]).first())
                if candidate is None:
                    party = Party.objects.create(
                        tenant=req.tenant, kind="person",
                        name=f"{cd['first_name']} {cd['last_name']}".strip())
                    PartyRole.objects.create(tenant=req.tenant, party=party, role="candidate")
                    candidate = CandidateProfile.objects.create(
                        tenant=req.tenant, party=party, first_name=cd["first_name"],
                        last_name=cd["last_name"], email=cd["email"], phone=cd["phone"],
                        linkedin_url=cd["linkedin_url"], city=cd["city"], source=cd["source"],
                        resume_file=cd["resume_file"])
                if cd["gdpr_consent"] and not candidate.gdpr_consent:
                    candidate.gdpr_consent = True
                    candidate.gdpr_consent_date = timezone.now()
                    candidate.save(update_fields=["gdpr_consent", "gdpr_consent_date", "updated_at"])
                application, created = JobApplication.objects.get_or_create(
                    tenant=req.tenant, candidate=candidate, requisition=req,
                    defaults={"source": "careers_page", "cover_letter_text": cd["cover_letter_text"]})
            if not created:
                messages.info(request, "You have already applied for this position.")
            else:
                write_audit_log(None, application, "create", {"via": "careers_portal"})
                # Reuse the already-loaded requisition so the merge-render doesn't refetch it.
                application.requisition = req
                _send_candidate_email(application, template_type="application_received", sent_by=None)
            return redirect(f"{reverse('hrm:careers_apply', args=[token])}?submitted=1")
    return render(request, "hrm/candidates/careers_apply.html", {
        "req": req, "form": form, "submitted": request.GET.get("submitted") == "1"})


# ============================================================ 3.7 Interview Process
# Interviews hang off the 3.6 JobApplication spine. Invites/reminders to the CANDIDATE reuse the 3.6
# _send_candidate_email pipeline (honors do_not_contact + logs CandidateCommunication); the panel
# feedback request emails internal panelist Users directly (best-effort). Status is workflow-owned —
# only the action POSTs below mutate it. Live calendar/Zoom/Teams/Meet/SMS dispatch is deferred.
def _interview_detail_lines(interview):
    """Compose the interview-specific lines appended to an invite/reminder email body (the template
    body's merge fields cover candidate/job; these literal lines carry the schedule + link)."""
    lines = [
        f"Interview: {interview.title} (Round {interview.round_number})",
        f"When: {interview.scheduled_at:%Y-%m-%d %H:%M} ({interview.duration_minutes} min)",
        f"Mode: {interview.get_mode_display()}",
    ]
    if interview.location:
        lines.append(f"Location: {interview.location}")
    if interview.meeting_url:
        lines.append(f"Meeting link: {interview.meeting_url}")
    return "\n".join(lines)


def _send_interview_email(interview, *, template_type, default_subject, sent_by):
    """Send an interview invite/reminder to the candidate, reusing the 3.6 candidate-email pipeline +
    append-only log. Resolves the matching active CandidateEmailTemplate (if any) for the body, then
    appends the interview specifics. Returns the logged CandidateCommunication, or None (do_not_contact
    / nothing to send)."""
    application = interview.application
    template = (CandidateEmailTemplate.objects
                .filter(tenant=interview.tenant, template_type=template_type, is_active=True)
                .order_by("pk").first())
    base_body = template.body_html if template is not None else ""
    body = (base_body + "\n\n" if base_body else "") + _interview_detail_lines(interview)
    subject = template.subject if template is not None else default_subject
    return _send_candidate_email(application, template=template, subject=subject, body=body, sent_by=sent_by)


def _interview_or_404(request, pk):
    return get_object_or_404(
        Interview.objects.filter(tenant=request.tenant)
        .select_related("application__candidate", "application__requisition"), pk=pk)


def _form_changes(form):
    """Compact {field: new_value} of changed fields for the audit log (the 3.7/3.8 forms carry no
    sensitive fields, so no redaction needed — mirrors apps.core.crud._changed)."""
    return {name: str(form.cleaned_data.get(name))[:200] for name in getattr(form, "changed_data", [])}


# --------------------------------------------------------------- Interviews (3.7) CRUD + hub
@login_required
def interview_list(request):
    qs = (Interview.objects.filter(tenant=request.tenant)
          .select_related("application__candidate", "application__requisition")
          .annotate(panelist_count=Count("panelists", distinct=True))
          .order_by("-scheduled_at"))  # explicit ordering after annotate (paginator needs it)
    return crud_list(
        request, qs, "hrm/interview/interview/list.html",
        search_fields=["number", "title", "application__candidate__first_name",
                       "application__candidate__last_name", "application__requisition__title",
                       "application__number"],
        filters=[("status", "status", False), ("mode", "mode", False),
                 ("application", "application_id", True)],
        extra_context={
            "status_choices": INTERVIEW_STATUS_CHOICES,
            "mode_choices": INTERVIEW_MODE_CHOICES,
            "applications": JobApplication.objects.filter(tenant=request.tenant)
            .select_related("candidate", "requisition").order_by("-applied_at")[:200],
        },
    )


@login_required
def interview_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = InterviewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.scheduled_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Interview {obj.number} scheduled.")
            return redirect("hrm:interview_detail", pk=obj.pk)
    else:
        # Pre-select the application when arriving from an application/candidate hub.
        form = InterviewForm(tenant=request.tenant,
                             initial={"application": request.GET.get("application") or None})
    return render(request, "hrm/interview/interview/form.html", {"form": form, "is_edit": False})


@login_required
def interview_detail(request, pk):
    obj = get_object_or_404(
        Interview.objects.filter(tenant=request.tenant)
        .select_related("application__candidate", "application__requisition", "scheduled_by"), pk=pk)
    panelists = obj.panelists.select_related("interviewer").all()
    feedback_entries = (obj.feedback_entries.select_related("submitted_by", "panelist__interviewer")
                        .annotate(avg_rating=Avg("criteria__rating")).order_by("-created_at"))
    return render(request, "hrm/interview/interview/detail.html", {
        "obj": obj,
        "panelists": panelists,
        "feedback_entries": feedback_entries,
        "panelist_form": InterviewPanelistForm(tenant=request.tenant),
        "rsvp_choices": RSVP_STATUS_CHOICES,
    })


@login_required
def interview_edit(request, pk):
    # `status`/`scheduled_by`/reminder stamps aren't on the form, so they're preserved. Land back on the
    # detail hub (not the list) so the user can keep managing the panel/status after editing.
    obj = get_object_or_404(Interview.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = InterviewForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", _form_changes(form))
            messages.success(request, "Interview updated.")
            return redirect("hrm:interview_detail", pk=obj.pk)
    else:
        form = InterviewForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/interview/interview/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required  # destructive — cascades panelists, scorecards and criteria; matches the
@require_POST           # admin-only delete button in the templates (security-review #2)
def interview_delete(request, pk):
    return crud_delete(request, model=Interview, pk=pk, success_url="hrm:interview_list")


def _transition_interview(request, pk, new_status, success_msg):
    obj = _interview_or_404(request, pk)
    if obj.status in INTERVIEW_TERMINAL_STATUSES:
        messages.error(request, "This interview is closed. Reschedule it to reopen.")
        return redirect("hrm:interview_detail", pk=obj.pk)
    obj.status = new_status
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": f"status:{new_status}"})
    messages.success(request, success_msg)
    return redirect("hrm:interview_detail", pk=obj.pk)


@login_required
@require_POST
def interview_confirm(request, pk):
    return _transition_interview(request, pk, "confirmed", "Interview confirmed.")


@login_required
@require_POST
def interview_start(request, pk):
    return _transition_interview(request, pk, "in_progress", "Interview marked in progress.")


@login_required
@require_POST
def interview_complete(request, pk):
    return _transition_interview(request, pk, "completed", "Interview completed.")


@login_required
@require_POST
def interview_cancel(request, pk):
    return _transition_interview(request, pk, "cancelled", "Interview cancelled.")


@login_required
@require_POST
def interview_no_show(request, pk):
    return _transition_interview(request, pk, "no_show", "Interview marked as no-show.")


@login_required
@require_POST
def interview_reschedule(request, pk):
    obj = _interview_or_404(request, pk)
    raw = request.POST.get("scheduled_at", "").strip()
    dt = parse_datetime(raw) if raw else None
    if dt is None:
        messages.error(request, "Enter a valid new date and time to reschedule.")
        return redirect("hrm:interview_detail", pk=obj.pk)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    obj.scheduled_at = dt
    obj.status = "rescheduled"  # reopens a closed round so it can proceed again
    obj.save(update_fields=["scheduled_at", "status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reschedule", "scheduled_at": dt.isoformat()})
    if dt < timezone.now():
        messages.warning(request, "Interview rescheduled — note the new time is in the past.")
    else:
        messages.success(request, "Interview rescheduled.")
    return redirect("hrm:interview_detail", pk=obj.pk)


@login_required
@require_POST
def interview_panelist_add(request, pk):
    interview = _interview_or_404(request, pk)
    form = InterviewPanelistForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        cd = form.cleaned_data
        _, created = InterviewPanelist.objects.get_or_create(
            interview=interview, interviewer=cd["interviewer"],
            defaults={"tenant": request.tenant, "role": cd["role"],
                      "briefing_notes": cd["briefing_notes"]})
        if created:
            messages.success(request, "Panelist added.")
        else:
            messages.info(request, "That interviewer is already on the panel.")
    else:
        messages.error(request, "Select an interviewer to add to the panel.")
    return redirect("hrm:interview_detail", pk=interview.pk)


@login_required
@require_POST
def interview_panelist_remove(request, pk, panelist_pk):
    interview = _interview_or_404(request, pk)
    panelist = get_object_or_404(InterviewPanelist, pk=panelist_pk, interview=interview, tenant=request.tenant)
    panelist.delete()
    messages.success(request, "Panelist removed.")
    return redirect("hrm:interview_detail", pk=interview.pk)


@login_required
@require_POST
def interview_panelist_rsvp(request, pk, panelist_pk):
    interview = _interview_or_404(request, pk)
    panelist = get_object_or_404(InterviewPanelist, pk=panelist_pk, interview=interview, tenant=request.tenant)
    new_rsvp = request.POST.get("rsvp_status", "")
    if new_rsvp not in dict(RSVP_STATUS_CHOICES):
        messages.error(request, "Invalid RSVP status.")
        return redirect("hrm:interview_detail", pk=interview.pk)
    panelist.rsvp_status = new_rsvp
    panelist.save(update_fields=["rsvp_status", "updated_at"])
    messages.success(request, "RSVP updated.")
    return redirect("hrm:interview_detail", pk=interview.pk)


@login_required
@require_POST
def interview_send_invite(request, pk):
    interview = _interview_or_404(request, pk)
    if interview.application.candidate.do_not_contact:
        messages.error(request, "This candidate is marked do-not-contact; invite not sent.")
        return redirect("hrm:interview_detail", pk=interview.pk)
    comm = _send_interview_email(interview, template_type="interview_invite",
                                 default_subject="Interview Invitation", sent_by=request.user)
    # The panel is invited alongside the candidate — stamp not-yet-notified seats.
    interview.panelists.filter(notified_at__isnull=True).update(notified_at=timezone.now())
    if comm is None:
        messages.error(request, "Nothing sent — the candidate has no email or is do-not-contact.")
    else:
        write_audit_log(request.user, comm, "create",
                        {"to": interview.application.candidate.email, "kind": "interview_invite"})
        messages.success(request, f"Invite sent to {interview.application.candidate.name}.")
    return redirect("hrm:interview_detail", pk=interview.pk)


@login_required
@require_POST
def interview_send_reminder(request, pk):
    interview = _interview_or_404(request, pk)
    if interview.application.candidate.do_not_contact:
        messages.error(request, "This candidate is marked do-not-contact; reminder not sent.")
        return redirect("hrm:interview_detail", pk=interview.pk)
    comm = _send_interview_email(interview, template_type="interview_reminder",
                                 default_subject="Interview Reminder", sent_by=request.user)
    if comm is None:
        messages.error(request, "Nothing sent — the candidate has no email or is do-not-contact.")
    else:
        interview.reminder_sent_at = timezone.now()
        interview.save(update_fields=["reminder_sent_at", "updated_at"])
        write_audit_log(request.user, comm, "create",
                        {"to": interview.application.candidate.email, "kind": "interview_reminder"})
        messages.success(request, "Reminder sent to the candidate.")
    return redirect("hrm:interview_detail", pk=interview.pk)


@login_required
@require_POST
def interview_request_feedback(request, pk):
    """Nudge the panel to submit their scorecards — emails the panelist Users directly (best-effort) and
    stamps ``feedback_reminder_sent_at``. Internal email only; SMS/automated dispatch deferred."""
    interview = _interview_or_404(request, pk)
    emails = [p.interviewer.email for p in interview.panelists.select_related("interviewer")
              if p.interviewer.email]
    if emails:
        candidate_name = interview.application.candidate.name
        subject = f"Please submit your scorecard — {interview.title}"
        body = (f"You interviewed {candidate_name} ({interview.title}, Round {interview.round_number}).\n"
                f"Please submit your interview feedback / scorecard in NavERP HRM.")
        try:
            send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, emails, fail_silently=True)
        except Exception:  # never let a transport failure 500 the request
            pass
    interview.feedback_reminder_sent_at = timezone.now()
    interview.save(update_fields=["feedback_reminder_sent_at", "updated_at"])
    write_audit_log(request.user, interview, "update",
                    {"action": "request_feedback", "panelists": len(emails)})
    messages.success(request, f"Feedback requested from {len(emails)} panelist(s).")
    return redirect("hrm:interview_detail", pk=interview.pk)


# --------------------------------------------------------------- Interview Feedback / Scorecards (3.7)
@login_required
def interviewfeedback_list(request):
    qs = (InterviewFeedback.objects.filter(tenant=request.tenant)
          .select_related("interview__application__candidate", "submitted_by")
          .annotate(avg_rating=Avg("criteria__rating"),
                    criteria_count=Count("criteria", distinct=True))
          .order_by("-created_at"))  # explicit ordering after annotate (paginator needs it)
    return crud_list(
        request, qs, "hrm/interview/interviewfeedback/list.html",
        search_fields=["number", "summary", "interview__title",
                       "interview__application__candidate__first_name",
                       "interview__application__candidate__last_name"],
        filters=[("recommendation", "overall_recommendation", False),
                 ("submitted", "is_submitted", False),
                 ("interview", "interview_id", True)],
        extra_context={
            "recommendation_choices": RECOMMENDATION_CHOICES,
            "interviews": Interview.objects.filter(tenant=request.tenant).order_by("-scheduled_at")[:200],
        },
    )


@login_required
def interviewfeedback_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = InterviewFeedbackForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            # Scorecards are created as drafts; submission is the dedicated submit action (stamps
            # submitted_by/at), so there's no submission metadata to set here.
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Scorecard {obj.number} created.")
            return redirect("hrm:interviewfeedback_detail", pk=obj.pk)
    else:
        form = InterviewFeedbackForm(tenant=request.tenant,
                                     initial={"interview": request.GET.get("interview") or None})
    return render(request, "hrm/interview/interviewfeedback/form.html", {"form": form, "is_edit": False})


@login_required
def interviewfeedback_detail(request, pk):
    obj = get_object_or_404(
        InterviewFeedback.objects.filter(tenant=request.tenant)
        .select_related("interview__application__candidate", "submitted_by", "panelist__interviewer"), pk=pk)
    return render(request, "hrm/interview/interviewfeedback/detail.html", {
        "obj": obj,
        "criteria": obj.criteria.all(),
        "avg_rating": obj.criteria.aggregate(avg=Avg("rating"))["avg"],
        "criterion_form": FeedbackCriterionForm(tenant=request.tenant),
    })


@login_required
def interviewfeedback_edit(request, pk):
    obj = get_object_or_404(InterviewFeedback.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = InterviewFeedbackForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            # `is_submitted` isn't on the form, so editing a submitted card can't un-submit it.
            obj = form.save()
            write_audit_log(request.user, obj, "update", _form_changes(form))
            messages.success(request, "Scorecard updated.")
            return redirect("hrm:interviewfeedback_detail", pk=obj.pk)
    else:
        form = InterviewFeedbackForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/interview/interviewfeedback/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required  # a submitted scorecard is an auditable attestation; admin-only delete to match
@require_POST           # the template's gated delete button (security-review #2)
def interviewfeedback_delete(request, pk):
    return crud_delete(request, model=InterviewFeedback, pk=pk, success_url="hrm:interviewfeedback_list")


@login_required
@require_POST
def interviewfeedback_submit(request, pk):
    obj = get_object_or_404(InterviewFeedback.objects.filter(tenant=request.tenant), pk=pk)
    if not obj.is_submitted:
        obj.is_submitted = True
        obj.submitted_at = timezone.now()
        obj.submitted_by = request.user
        obj.save(update_fields=["is_submitted", "submitted_at", "submitted_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, "Scorecard submitted.")
    else:
        messages.info(request, "This scorecard is already submitted.")
    return redirect("hrm:interviewfeedback_detail", pk=obj.pk)


@login_required
@require_POST
def feedbackcriterion_add(request, pk):
    feedback = get_object_or_404(InterviewFeedback.objects.filter(tenant=request.tenant), pk=pk)
    form = FeedbackCriterionForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        cd = form.cleaned_data
        FeedbackCriterion.objects.create(
            tenant=request.tenant, feedback=feedback, criterion_name=cd["criterion_name"],
            rating=cd["rating"], notes=cd["notes"])
        messages.success(request, "Criterion added.")
    else:
        messages.error(request, "Enter a criterion name and a rating of 1–5.")
    return redirect("hrm:interviewfeedback_detail", pk=feedback.pk)


@login_required
@require_POST
def feedbackcriterion_delete(request, pk, criterion_pk):
    feedback = get_object_or_404(InterviewFeedback.objects.filter(tenant=request.tenant), pk=pk)
    crit = get_object_or_404(FeedbackCriterion, pk=criterion_pk, feedback=feedback, tenant=request.tenant)
    crit.delete()
    messages.success(request, "Criterion removed.")
    return redirect("hrm:interviewfeedback_detail", pk=feedback.pk)


# ============================================================ Offer Management (3.8)
# Offers hang off the 3.6 JobApplication spine; the approval chain + status machine mirror 3.5
# JobRequisition; offer/pre-boarding emails reuse the 3.6 _send_candidate_email pipeline.

def _offer_or_404(request, pk):
    return get_object_or_404(
        Offer.objects.filter(tenant=request.tenant)
        .select_related("application__candidate", "application__requisition", "offer_letter_template"), pk=pk)


# --------------------------------------------------------------- Offer Letter Templates (3.8)
@login_required
def offerlettertemplate_list(request):
    return crud_list(
        request, OfferLetterTemplate.objects.filter(tenant=request.tenant),
        "hrm/offer/offerlettertemplate/list.html",
        search_fields=["number", "name", "body_html"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def offerlettertemplate_create(request):
    return crud_create(request, form_class=OfferLetterTemplateForm,
                       template="hrm/offer/offerlettertemplate/form.html",
                       success_url="hrm:offerlettertemplate_list")


@login_required
def offerlettertemplate_detail(request, pk):
    return crud_detail(request, model=OfferLetterTemplate, pk=pk,
                       template="hrm/offer/offerlettertemplate/detail.html")


@login_required
def offerlettertemplate_edit(request, pk):
    return crud_edit(request, model=OfferLetterTemplate, pk=pk, form_class=OfferLetterTemplateForm,
                     template="hrm/offer/offerlettertemplate/form.html",
                     success_url="hrm:offerlettertemplate_list")


@tenant_admin_required
@require_POST
def offerlettertemplate_delete(request, pk):
    return crud_delete(request, model=OfferLetterTemplate, pk=pk,
                       success_url="hrm:offerlettertemplate_list")


# --------------------------------------------------------------- Offers (3.8) CRUD + hub
@login_required
def offer_list(request):
    qs = (Offer.objects.filter(tenant=request.tenant)
          .select_related("application__candidate", "application__requisition")
          .order_by("-created_at"))
    return crud_list(
        request, qs, "hrm/offer/offer/list.html",
        search_fields=["number", "application__candidate__first_name",
                       "application__candidate__last_name", "application__requisition__title"],
        filters=[("status", "status", False), ("signature_status", "signature_status", False),
                 ("currency", "currency", False)],
        extra_context={
            "status_choices": OFFER_STATUS_CHOICES,
            "signature_status_choices": SIGNATURE_STATUS_CHOICES,
        },
    )


@login_required
def offer_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = OfferForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            # Default the currency from the requisition's salary_currency when the recruiter left it blank.
            if not obj.currency:
                obj.currency = obj.application.requisition.salary_currency or "USD"
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Offer {obj.number} created.")
            return redirect("hrm:offer_detail", pk=obj.pk)
    else:
        form = OfferForm(tenant=request.tenant,
                         initial={"application": request.GET.get("application") or None})
    return render(request, "hrm/offer/offer/form.html", {"form": form, "is_edit": False})


@login_required
def offer_detail(request, pk):
    obj = get_object_or_404(
        Offer.objects.filter(tenant=request.tenant)
        .select_related("application__candidate", "application__requisition", "offer_letter_template",
                        "created_by", "extended_by"), pk=pk)
    approvals = obj.approvals.select_related("approver", "decided_by").all()
    background_checks = obj.background_checks.select_related("initiated_by").all()
    preboarding_items = obj.preboarding_items.select_related("verified_by").all()
    approved = sum(1 for s in approvals if s.status == "approved")
    all_approved = len(approvals) > 0 and approved == len(approvals)
    return render(request, "hrm/offer/offer/detail.html", {
        "obj": obj,
        "approvals": approvals,
        "background_checks": background_checks,
        "preboarding_items": preboarding_items,
        "approval_progress": (approved, len(approvals)),
        "all_approved": all_approved,
        "approval_form": OfferApprovalForm(tenant=request.tenant),
        "preboarding_form": PreboardingItemForm(tenant=request.tenant),
        "decline_reason_choices": OFFER_DECLINE_REASON_CHOICES,
    })


@login_required
def offer_edit(request, pk):
    # Editable only while a draft (mirrors jobrequisition_edit locking during the approval flow). Editing is
    # locked once submitted because the approval chain — including the executive-step comp threshold — is
    # built at submit time and not recomputed; a comp change under approval would silently invalidate it.
    # A pending-approval offer is reopened for edits via reject-step (back to draft). `status` and the
    # workflow stamps aren't on the form, so they're preserved.
    obj = get_object_or_404(Offer.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status != "draft":
        messages.error(request, "Only a draft offer can be edited. Reject the approval to reopen it for changes.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    if request.method == "POST":
        form = OfferForm(request.POST, request.FILES, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.currency:
                obj.currency = obj.application.requisition.salary_currency or "USD"
            obj.save()
            write_audit_log(request.user, obj, "update", _form_changes(form))
            messages.success(request, "Offer updated.")
            return redirect("hrm:offer_detail", pk=obj.pk)
    else:
        form = OfferForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/offer/offer/form.html", {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required  # destructive — cascades approvals/background-checks/preboarding items; admin-only
@require_POST           # and only while a draft (mirrors jobrequisition_delete)
def offer_delete(request, pk):
    obj = get_object_or_404(Offer.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status != "draft":
        messages.error(request, "Only a draft offer can be deleted.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Offer deleted.")
    return redirect("hrm:offer_list")


# --- Offer approval-chain steps (inline on the offer hub; admin-only, steps only before submit) ---
@tenant_admin_required
@require_POST
def offerapproval_add(request, pk):
    offer = get_object_or_404(Offer, pk=pk, tenant=request.tenant)
    if offer.status != "draft":
        messages.error(request, "Approval steps can only be added while the offer is a draft.")
        return redirect("hrm:offer_detail", pk=offer.pk)
    form = OfferApprovalForm(request.POST, tenant=request.tenant)
    if form.is_valid():
        step = form.save(commit=False)
        step.tenant = request.tenant
        step.offer = offer
        step.status = "pending"
        try:
            step.save()
        except IntegrityError:
            messages.error(request, f"An approval step #{step.step_order} already exists.")
            return redirect("hrm:offer_detail", pk=offer.pk)
        write_audit_log(request.user, step, "create",
                        {"action": "add_offer_approval_step", "step": step.step_order})
        messages.success(request, f"Approval step #{step.step_order} added.")
    else:
        messages.error(request, "Could not add the approval step — check the step order and approver.")
    return redirect("hrm:offer_detail", pk=offer.pk)


@tenant_admin_required
@require_POST
def offerapproval_delete(request, pk):
    step = get_object_or_404(OfferApproval.objects.select_related("offer"), pk=pk, tenant=request.tenant)
    offer = step.offer
    if offer.status != "draft":
        messages.error(request, "Approval steps can only be removed while the offer is a draft.")
        return redirect("hrm:offer_detail", pk=offer.pk)
    write_audit_log(request.user, step, "delete",
                    {"action": "remove_offer_approval_step", "step": step.step_order})
    step.delete()
    messages.success(request, "Approval step removed.")
    return redirect("hrm:offer_detail", pk=offer.pk)


# --- Offer workflow state-machine actions (all privileged; the form never sets these fields) ---
@tenant_admin_required
@require_POST
def offer_submit(request, pk):
    obj = get_object_or_404(Offer, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.error(request, "Only a draft offer can be submitted for approval.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    with transaction.atomic():
        generate_offer_approval_chain(obj)  # idempotent: builds the default chain only when none exist
        # Reset any prior decisions so a re-submit (after a rejected step reopened the offer to draft)
        # re-approves cleanly from the top — otherwise a step left at "rejected" would never return to
        # pending and offer_approve_step would flip the offer to approved once the other steps cleared,
        # skipping it. Mirrors jobrequisition_submit's rejected-resubmit chain reset.
        obj.approvals.update(status="pending", decided_at=None, decided_by=None, comments="")
        obj.status = "pending_approval"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit", "to": obj.status})
    messages.success(request, f"Offer {obj.number} submitted for approval.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def offer_approve_step(request, pk):
    obj = get_object_or_404(Offer, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(request, "Only an offer pending approval can be approved.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    step = obj.approvals.filter(status="pending").order_by("step_order").first()
    if step is None:
        messages.error(request, "No pending approval step to approve.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    with transaction.atomic():
        step.status = "approved"
        step.decided_at = timezone.now()
        step.decided_by = request.user
        step.save(update_fields=["status", "decided_at", "decided_by", "updated_at"])
        # When the last pending step clears, the whole offer is approved.
        if not obj.approvals.filter(status="pending").exists():
            obj.status = "approved"
            obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update",
                        {"action": "approve_step", "step": step.step_order, "to": obj.status})
    if obj.status == "approved":
        messages.success(request, f"Final approval recorded — {obj.number} is approved.")
    else:
        messages.success(request, f"Approval step #{step.step_order} approved.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def offer_reject_step(request, pk):
    # A rejected step reopens the offer to draft (mirrors jobrequisition_return) rather than inventing a
    # terminal "rejected" status — OFFER_STATUS_CHOICES stays exactly as researched. The chain is reset so
    # a fresh submit re-approves from the top.
    obj = get_object_or_404(Offer, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(request, "Only an offer pending approval can be rejected.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    step = obj.approvals.filter(status="pending").order_by("step_order").first()
    with transaction.atomic():
        if step is not None:
            step.status = "rejected"
            step.decided_at = timezone.now()
            step.decided_by = request.user
            step.comments = request.POST.get("comments", "").strip()[:2000]
            step.save(update_fields=["status", "decided_at", "decided_by", "comments", "updated_at"])
        # Reset the rest of the chain and reopen for revision.
        obj.approvals.exclude(pk=step.pk if step else None).update(
            status="pending", decided_at=None, decided_by=None, comments="")
        obj.status = "draft"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject_step"})
    messages.success(request, f"Offer {obj.number} sent back for revision.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def offer_extend(request, pk):
    # The P0 "approval blocks extension" gate: an offer can only be extended once fully approved.
    obj = _offer_or_404(request, pk)
    if obj.status != "approved":
        messages.error(request, "Only a fully-approved offer can be extended to the candidate.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    obj.status = "extended"
    obj.extended_by = request.user
    obj.extended_at = timezone.now()
    if obj.signature_status == "not_sent":
        obj.signature_status = "sent"
    obj.save(update_fields=["status", "extended_by", "extended_at", "signature_status", "updated_at"])
    # Email the candidate the offer (reuses the existing "offer" template-type + append-only log).
    comm = _send_candidate_email(obj.application, template_type="offer", sent_by=request.user)
    write_audit_log(request.user, obj, "update", {"action": "extend"})
    if comm is None:
        messages.warning(request, f"Offer {obj.number} extended — but no email was sent "
                                  "(candidate has no email or is do-not-contact).")
    else:
        messages.success(request, f"Offer {obj.number} extended to {obj.application.candidate.name}.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@login_required
@require_POST
def offer_accept(request, pk):
    # Marks the candidate's acceptance: advances the application to "hired" (existing 3.6 fields), raises
    # the pre-boarding checklist, and logs an acceptance communication. A regular tenant user can record
    # this (it's data entry of the candidate's response, not an authority action).
    obj = _offer_or_404(request, pk)
    if obj.status != "extended":
        messages.error(request, "Only an extended offer can be marked accepted.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    with transaction.atomic():
        obj.status = "accepted"
        obj.accepted_at = timezone.now()
        if obj.signature_status in ("not_sent", "sent", "viewed"):
            obj.signature_status = "signed"
        obj.save(update_fields=["status", "accepted_at", "signature_status", "updated_at"])
        # Drive the recruiting pipeline to hired (reuse existing JobApplication fields — no schema change).
        app = obj.application
        app.stage = "hired"
        app.hired_on = _date.today()
        app.stage_changed_at = timezone.now()
        app.save(update_fields=["stage", "hired_on", "stage_changed_at", "updated_at"])
        # TODO (3.3 hand-off): full onboarding (OnboardingProgram) is created from its own entry points on
        # the join date; pre-boarding here only collects pre-start documents.
        generate_preboarding_checklist(obj)
        write_audit_log(request.user, obj, "update", {"action": "accept", "application": app.number})
    _send_candidate_email(obj.application, template_type="offer",
                          subject="Offer Accepted — Welcome Aboard",
                          body=f"Dear {obj.application.candidate.name},\n\nThank you for accepting our offer "
                               f"for {obj.application.requisition.title}. We'll be in touch with pre-boarding "
                               f"next steps.", sent_by=request.user)
    messages.success(request, f"Offer {obj.number} accepted — {obj.application.candidate.name} marked hired.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@login_required
@require_POST
def offer_decline(request, pk):
    obj = _offer_or_404(request, pk)
    if obj.status != "extended":
        messages.error(request, "Only an extended offer can be marked declined.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    reason = request.POST.get("decline_reason", "").strip()
    if reason not in dict(OFFER_DECLINE_REASON_CHOICES):
        messages.error(request, "Select a valid decline reason.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    obj.status = "declined"
    obj.declined_at = timezone.now()
    obj.decline_reason = reason
    obj.decline_notes = request.POST.get("decline_notes", "").strip()[:2000]
    obj.save(update_fields=["status", "declined_at", "decline_reason", "decline_notes", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "decline", "reason": reason})
    messages.success(request, f"Offer {obj.number} marked declined.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@tenant_admin_required  # rescinding a live offer is a sensitive HR action
@require_POST
def offer_rescind(request, pk):
    obj = _offer_or_404(request, pk)
    if obj.status not in ("pending_approval", "approved", "extended"):
        messages.error(request, "Only a pending, approved or extended offer can be rescinded.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    obj.status = "rescinded"
    obj.rescinded_at = timezone.now()
    obj.save(update_fields=["status", "rescinded_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "rescind"})
    messages.success(request, f"Offer {obj.number} rescinded.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def offer_expire(request, pk):
    # Manual "let it lapse" action, available once an extended offer is past its response deadline
    # (automated cron expiry is deferred, mirroring the manual-action convention throughout HRM).
    obj = _offer_or_404(request, pk)
    if obj.status != "extended":
        messages.error(request, "Only an extended offer can be expired.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    if not obj.is_overdue:
        messages.error(request, "This offer's response deadline hasn't passed yet.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    obj.status = "expired"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "expire"})
    messages.success(request, f"Offer {obj.number} marked expired.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@login_required
@require_POST
def offer_send_email(request, pk):
    # Ad-hoc resend of the offer-letter email at any non-terminal status.
    obj = _offer_or_404(request, pk)
    if obj.is_closed:
        messages.error(request, "This offer is closed — no email sent.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    if obj.application.candidate.do_not_contact:
        messages.error(request, "This candidate is marked do-not-contact; email not sent.")
        return redirect("hrm:offer_detail", pk=obj.pk)
    comm = _send_candidate_email(obj.application, template_type="offer", sent_by=request.user)
    if comm is None:
        messages.error(request, "Nothing sent — the candidate has no email or is do-not-contact.")
    else:
        write_audit_log(request.user, comm, "create",
                        {"to": obj.application.candidate.email, "kind": "offer"})
        messages.success(request, f"Offer email sent to {obj.application.candidate.name}.")
    return redirect("hrm:offer_detail", pk=obj.pk)


@login_required
def offer_letter_print(request, pk):
    """Server-rendered printable offer letter (3.8). Merges the chosen ``OfferLetterTemplate.body_html``
    tokens against the offer/candidate/tenant (reusing ``_apply_merge``), falling back to a generated body
    when no template is linked. Pure read/render — an offer letter can be reprinted freely (mirrors the
    offboarding relieving/experience letters)."""
    obj = _offer_or_404(request, pk)
    candidate = obj.application.candidate
    hiring_manager = obj.requisition.hiring_manager
    ctx = {
        "{{candidate_name}}": candidate.name,
        "{{job_title}}": obj.requisition.title,
        "{{base_salary}}": f"{obj.base_salary:,.2f}",
        "{{currency}}": obj.currency,
        "{{start_date}}": obj.start_date.strftime("%B %d, %Y") if obj.start_date else "",
        "{{company_name}}": getattr(request.tenant, "name", ""),
        "{{hiring_manager_name}}": (hiring_manager.party.name if hiring_manager else "the hiring team"),
    }
    if obj.offer_letter_template:
        letter_body = _apply_merge(obj.offer_letter_template.body_html, ctx)
    else:
        letter_body = (
            f"Dear {candidate.name},\n\nWe are delighted to offer you the position of "
            f"{obj.requisition.title} at {ctx['{{company_name}}']}. Your annual base salary will be "
            f"{obj.currency} {obj.base_salary:,.2f}, with a proposed start date of "
            f"{ctx['{{start_date}}'] or 'a date to be confirmed'}.\n\nWe look forward to welcoming you "
            f"to the team.\n\nSincerely,\n{ctx['{{hiring_manager_name}}']}")
    return render(request, "hrm/offer/offer_letter.html", {
        "offer": obj,
        "application": obj.application,
        "candidate": candidate,
        "letter_body": letter_body,
        "today": timezone.localdate(),
    })


# --------------------------------------------------------------- Background Verification (3.8)
@login_required
def backgroundverification_list(request):
    qs = (BackgroundVerification.objects.filter(tenant=request.tenant)
          .select_related("offer__application__candidate").order_by("-created_at"))
    return crud_list(
        request, qs, "hrm/offer/backgroundverification/list.html",
        search_fields=["number", "offer__number", "offer__application__candidate__first_name",
                       "offer__application__candidate__last_name"],
        filters=[("status", "status", False), ("check_type", "check_type", False),
                 ("vendor", "vendor", False)],
        extra_context={
            "status_choices": BGV_STATUS_CHOICES,
            "check_type_choices": BGV_CHECK_TYPE_CHOICES,
            "vendor_choices": BGV_VENDOR_CHOICES,
        },
    )


@login_required
def backgroundverification_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = BackgroundVerificationForm(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Background check {obj.number} created.")
            return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    else:
        form = BackgroundVerificationForm(tenant=request.tenant,
                                          initial={"offer": request.GET.get("offer") or None})
    return render(request, "hrm/offer/backgroundverification/form.html", {"form": form, "is_edit": False})


@login_required
def backgroundverification_detail(request, pk):
    obj = get_object_or_404(
        BackgroundVerification.objects.filter(tenant=request.tenant)
        .select_related("offer__application__candidate", "initiated_by"), pk=pk)
    return render(request, "hrm/offer/backgroundverification/detail.html", {
        "obj": obj,
        "status_choices": BGV_STATUS_CHOICES,
        "result_choices": BGV_RESULT_CHOICES,
    })


@login_required
def backgroundverification_edit(request, pk):
    # Locked once completed (mirrors offer_edit / jobrequisition_edit) — a completed check's vendor/type/
    # consent/report is an audited record, not re-editable.
    obj = get_object_or_404(BackgroundVerification.objects.filter(tenant=request.tenant), pk=pk)
    if obj.status == "completed":
        messages.error(request, "A completed background check can no longer be edited.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    return crud_edit(request, model=BackgroundVerification, pk=pk, form_class=BackgroundVerificationForm,
                     template="hrm/offer/backgroundverification/form.html",
                     success_url="hrm:backgroundverification_list")


@tenant_admin_required
@require_POST
def backgroundverification_delete(request, pk):
    return crud_delete(request, model=BackgroundVerification, pk=pk,
                       success_url="hrm:backgroundverification_list")


def _bgv_or_404(request, pk):
    return get_object_or_404(
        BackgroundVerification.objects.filter(tenant=request.tenant)
        .select_related("offer__application__candidate"), pk=pk)


@login_required
@require_POST
def backgroundverification_initiate(request, pk):
    # Consent-before-initiation gate (the Checkr/BambooHR "candidate must authorize" finding).
    obj = _bgv_or_404(request, pk)
    if obj.status not in ("not_started", "consent_pending"):
        messages.error(request, "This check has already been initiated.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    if not obj.consent_given:
        obj.status = "consent_pending"
        obj.save(update_fields=["status", "updated_at"])
        messages.error(request, "Candidate consent is required before initiating the check.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    obj.status = "initiated"
    obj.initiated_at = timezone.now()
    obj.initiated_by = request.user
    if obj.consent_date is None:
        obj.consent_date = timezone.now()
    obj.save(update_fields=["status", "initiated_at", "initiated_by", "consent_date", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "initiate", "vendor": obj.vendor})
    messages.success(request, f"Background check {obj.number} initiated.")
    return redirect("hrm:backgroundverification_detail", pk=obj.pk)


@login_required
@require_POST
def backgroundverification_mark_status(request, pk):
    # Manual stand-in for the deferred vendor webhook: move the check through its intermediate statuses.
    obj = _bgv_or_404(request, pk)
    new_status = request.POST.get("status", "")
    allowed = {"in_progress", "action_needed", "ready_for_review"}
    if new_status not in allowed:
        messages.error(request, "Invalid status transition.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    if obj.status in ("not_started", "consent_pending"):
        messages.error(request, "Initiate the check before updating its progress.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    obj.status = new_status
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": f"status:{new_status}"})
    messages.success(request, "Background-check status updated.")
    return redirect("hrm:backgroundverification_detail", pk=obj.pk)


@login_required
@require_POST
def backgroundverification_complete(request, pk):
    obj = _bgv_or_404(request, pk)
    if obj.status == "completed":
        messages.info(request, "This check is already completed.")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    result = request.POST.get("result", "")
    if result not in dict(BGV_RESULT_CHOICES):
        messages.error(request, "Select a valid result (Clear / Consider / Not Applicable).")
        return redirect("hrm:backgroundverification_detail", pk=obj.pk)
    obj.status = "completed"
    obj.result = result
    obj.completed_at = timezone.now()
    obj.save(update_fields=["status", "result", "completed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "complete", "result": result})
    messages.success(request, f"Background check {obj.number} completed ({obj.get_result_display()}).")
    return redirect("hrm:backgroundverification_detail", pk=obj.pk)


# --------------------------------------------------------------- Pre-boarding Items (3.8, inline on offer)
def _preboarding_or_404(request, pk):
    return get_object_or_404(
        PreboardingItem.objects.filter(tenant=request.tenant).select_related("offer__application__candidate"),
        pk=pk)


@login_required
@require_POST
def preboardingitem_add(request, pk):
    offer = get_object_or_404(Offer, pk=pk, tenant=request.tenant)
    # Pre-boarding is only meaningful before/at joining — don't add items to a dead offer.
    if offer.is_closed and offer.status != "accepted":
        messages.error(request, "Pre-boarding items can't be added to a declined, rescinded or expired offer.")
        return redirect("hrm:offer_detail", pk=offer.pk)
    form = PreboardingItemForm(request.POST, request.FILES, tenant=request.tenant)
    if form.is_valid():
        item = form.save(commit=False)
        item.tenant = request.tenant
        item.offer = offer
        item.save()
        messages.success(request, "Pre-boarding item added.")
    else:
        messages.error(request, "Could not add the pre-boarding item — check the document type.")
    return redirect("hrm:offer_detail", pk=offer.pk)


@login_required
@require_POST
def preboardingitem_delete(request, pk):
    item = _preboarding_or_404(request, pk)
    offer_pk = item.offer_id
    item.delete()
    messages.success(request, "Pre-boarding item removed.")
    return redirect("hrm:offer_detail", pk=offer_pk)


@login_required
@require_POST
def preboardingitem_mark_submitted(request, pk):
    item = _preboarding_or_404(request, pk)
    if item.status not in ("pending", "rejected"):
        messages.error(request, "Only a pending or rejected pre-boarding item can be (re)submitted.")
        return redirect("hrm:offer_detail", pk=item.offer_id)
    item.status = "submitted"
    item.submitted_at = timezone.now()
    item.verified_by = None  # clear any stale verification from a prior reject so history stays consistent
    item.verified_at = None
    item.save(update_fields=["status", "submitted_at", "verified_by", "verified_at", "updated_at"])
    messages.success(request, "Pre-boarding item marked submitted.")
    return redirect("hrm:offer_detail", pk=item.offer_id)


@tenant_admin_required  # verifying/rejecting a submitted document is a privileged HR action
@require_POST
def preboardingitem_verify(request, pk):
    item = _preboarding_or_404(request, pk)
    item.status = "verified"
    item.verified_by = request.user
    item.verified_at = timezone.now()
    item.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
    write_audit_log(request.user, item, "update", {"action": "verify_preboarding"})
    messages.success(request, "Pre-boarding item verified.")
    return redirect("hrm:offer_detail", pk=item.offer_id)


@tenant_admin_required
@require_POST
def preboardingitem_reject(request, pk):
    item = _preboarding_or_404(request, pk)
    item.status = "rejected"
    item.verified_by = request.user
    item.verified_at = timezone.now()
    item.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])
    write_audit_log(request.user, item, "update", {"action": "reject_preboarding"})
    messages.success(request, "Pre-boarding item rejected — the candidate can re-submit.")
    return redirect("hrm:offer_detail", pk=item.offer_id)


@login_required
@require_POST
def preboardingitem_send_invite(request, pk):
    # Reuses the 3.6 candidate-email pipeline for a pre-boarding document-collection nudge (manual action;
    # scheduled dispatch deferred). Stamps reminder_sent_at, honoring do_not_contact via the helper.
    item = _preboarding_or_404(request, pk)
    candidate = item.offer.application.candidate
    if candidate.do_not_contact:
        messages.error(request, "This candidate is marked do-not-contact; invite not sent.")
        return redirect("hrm:offer_detail", pk=item.offer_id)
    body = (f"Dear {candidate.name},\n\nPlease upload your {item.get_document_type_display()} to complete "
            f"pre-boarding for your upcoming start. Reply to this email if you have any questions.")
    comm = _send_candidate_email(item.offer.application, template_type="general",
                                 subject="Pre-boarding — document requested", body=body, sent_by=request.user)
    if comm is None:
        messages.error(request, "Nothing sent — the candidate has no email or is do-not-contact.")
    else:
        item.reminder_sent_at = timezone.now()
        item.save(update_fields=["reminder_sent_at", "updated_at"])
        write_audit_log(request.user, comm, "create",
                        {"to": candidate.email, "kind": "preboarding_invite"})
        messages.success(request, "Pre-boarding invite sent to the candidate.")
    return redirect("hrm:offer_detail", pk=item.offer_id)
