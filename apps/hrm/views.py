"""HRM (Module 3) views — function-based, ``@login_required``, tenant-scoped.

Full CRUD for the nine HRM models via the shared ``apps.core.crud`` helpers (search +
int-FK-guarded filters + windowed pagination + audit), plus:
  * an HRM overview (3.1) with headcount / today's attendance / pending-leave / holiday widgets,
  * a rich employee profile (leave balances, recent attendance, current shift),
  * the leave-request workflow actions (submit / approve / reject / cancel),
  * delete guards on records that anchor others (active employee, in-use leave type/shift).
"""
import secrets
from datetime import date as _date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import (Avg, Count, DecimalField, ExpressionWrapper, F, OuterRef, Prefetch, ProtectedError, Q, Subquery, Sum)
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_POST

from django.conf import settings
from django.core.mail import send_mail

from apps.core.crud import _changed, crud_create, crud_delete, crud_detail, crud_edit, crud_list
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
    AttendanceRegularizationForm,
    ClearanceItemForm,
    CostCenterProfileForm,
    DepartmentProfileForm,
    DesignationForm,
    EmployeeDocumentForm,
    EmployeeLifecycleEventForm,
    EmployeeProfileForm,
    ExitInterviewForm,
    FinalSettlementForm,
    GeoFenceForm,
    JobDescriptionTemplateForm,
    JobGradeForm,
    JobRequisitionForm,
    LeaveAllocationForm,
    LeaveEncashmentForm,
    LeaveRequestForm,
    LeaveTypeForm,
    OvertimeRequestForm,
    TimesheetEntryForm,
    TimesheetForm,
    OnboardingDocumentForm,
    OnboardingProgramForm,
    OnboardingTaskForm,
    OnboardingTemplateForm,
    OnboardingTemplateTaskForm,
    OrientationSessionForm,
    PublicHolidayForm,
    HolidayPolicyForm,
    FloatingHolidayElectionForm,
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
from .forms import (  # 3.13 Salary Structure
    EmployeeSalaryStructureForm,
    PayComponentForm,
    SalaryStructureLineForm,
    SalaryStructureTemplateForm,
)
from .forms import (  # 3.14 Payroll Processing
    PayrollCycleForm,
    PayslipForm,
)
from .forms import (  # 3.15 Statutory Compliance
    EmployeeStatutoryIdentifierForm,
    StatutoryConfigForm,
    StatutoryReturnForm,
    StatutoryStateRuleForm,
)
from .forms import (  # 3.16 Tax & Investment
    InvestmentDeclarationForm,
    InvestmentDeclarationLineForm,
    InvestmentProofForm,
    TaxComputationForm,
    TaxRegimeConfigForm,
    TaxSlabBandForm,
)
from .forms import (  # 3.17 Payout & Reports
    BankReconciliationForm,
    PayoutBatchForm,
)
from .forms import (  # 3.18 Goal Setting
    GoalCheckInForm,
    GoalPeriodForm,
    KeyResultForm,
    ObjectiveForm,
)
from .forms import (  # 3.19 Performance Review
    CalibrationForm,
    PerformanceReviewForm,
    ReviewCycleForm,
    ReviewRatingForm,
    ReviewTemplateForm,
)
from .forms import (  # 3.20 Continuous Feedback
    FeedbackForm,
    KudosBadgeForm,
    MeetingActionItemForm,
    OneOnOneMeetingForm,
)
from .forms import (  # 3.21 Performance Improvement
    CoachingNoteForm,
    PIPCheckInForm,
    PIPCloseForm,
    PerformanceImprovementPlanForm,
    WarningAcknowledgeForm,
    WarningLetterForm,
)
from .forms import (  # 3.22 Training Management
    TrainingCourseForm,
    TrainingSessionForm,
)
from .forms import (  # 3.23 Learning Management (LMS)
    LearningContentItemForm,
    LearningPathForm,
    LearningPathItemForm,
    LearningProgressForm,
)
from .forms import (  # 3.24 Training Administration
    TrainingAttendanceForm,
    TrainingCertificateForm,
    TrainingFeedbackForm,
    TrainingNominationForm,
)
from .forms import (  # 3.25 Personal Information (Self-Service)
    BankAccountChangeForm,
    EmergencyContactForm,
    EmployeeBankAccountForm,
    EmployeeProfileMyInfoForm,
    FamilyMemberChangeForm,
    FamilyMemberForm,
    ProfileFieldChangeForm,
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
    AttendanceRegularization,
    ClearanceItem,
    CostCenterProfile,
    DepartmentProfile,
    Designation,
    EmployeeDocument,
    EmployeeLifecycleEvent,
    EmployeeProfile,
    ExitInterview,
    FinalSettlement,
    GeoFence,
    JobDescriptionTemplate,
    JobGrade,
    JobRequisition,
    LeaveAllocation,
    LeaveEncashment,
    LeaveRequest,
    LeaveType,
    OvertimeRequest,
    Timesheet,
    TimesheetEntry,
    OnboardingDocument,
    OnboardingProgram,
    OnboardingTask,
    OnboardingTemplate,
    OnboardingTemplateTask,
    OrientationSession,
    PublicHoliday,
    HolidayPolicy,
    FloatingHolidayElection,
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
    BGV_MANUAL_TRANSITION_STATUSES,
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
from .models import (  # 3.13 Salary Structure
    EmployeeSalaryStructure,
    PayComponent,
    SalaryStructureLine,
    SalaryStructureTemplate,
)
from .models import (  # 3.14 Payroll Processing
    Payslip,
    PayslipLine,
    PayrollCycle,
)
from .models import (  # 3.15 Statutory Compliance
    INDIAN_STATE_CHOICES,
    EmployeeStatutoryIdentifier,
    StatutoryConfig,
    StatutoryReturn,
    StatutoryStateRule,
)
from .models import (  # 3.16 Tax & Investment
    InvestmentDeclaration,
    InvestmentDeclarationLine,
    InvestmentProof,
    TaxComputation,
    TaxRegimeConfig,
    TaxSlabBand,
)
from .models import (  # 3.17 Payout & Reports
    BankReconciliation,
    PayoutBatch,
    PayoutPayment,
    PayslipDistribution,
)
from .models import (  # 3.18 Goal Setting
    GoalCheckIn,
    GoalPeriod,
    KeyResult,
    Objective,
)
from .models import (  # 3.19 Performance Review
    PerformanceReview,
    ReviewCycle,
    ReviewRating,
    ReviewTemplate,
)
from .models import (  # 3.20 Continuous Feedback
    Feedback,
    KudosBadge,
    MeetingActionItem,
    OneOnOneMeeting,
)
from .models import (  # 3.21 Performance Improvement
    CoachingNote,
    PIPCheckIn,
    PerformanceImprovementPlan,
    WarningLetter,
)
from .models import (  # 3.22 Training Management
    TrainingCourse,
    TrainingSession,
)
from .models import (  # 3.23 Learning Management (LMS)
    LearningContentItem,
    LearningPath,
    LearningPathItem,
    LearningProgress,
)
from .models import (  # 3.24 Training Administration
    TrainingAttendance,
    TrainingCertificate,
    TrainingFeedback,
    TrainingNomination,
)
from .models import (  # 3.25 Personal Information (Self-Service)
    EmergencyContact,
    EmployeeBankAccount,
    EmployeeInfoChangeRequest,
    FamilyMember,
    _json_safe,
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
             "present_today": 0, "absent_today": 0, "pending_regularizations": 0,
             "pending_encashments": 0, "pending_timesheets": 0, "pending_overtime": 0,
             "open_requisitions": 0, "active_applications": 0, "new_candidates": 0,
             "active_objectives": 0, "open_reviews": 0,
             "birthdays_this_month": 0, "pinned_announcements": 0}
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
        stats["pending_regularizations"] = AttendanceRegularization.objects.filter(
            tenant=tenant, status="pending").count()
        stats["pending_encashments"] = LeaveEncashment.objects.filter(
            tenant=tenant, status="pending").count()
        stats["pending_timesheets"] = Timesheet.objects.filter(tenant=tenant, status="pending").count()
        stats["pending_overtime"] = OvertimeRequest.objects.filter(tenant=tenant, status="pending").count()
        # 3.6 recruiting pipeline at a glance.
        stats["open_requisitions"] = JobRequisition.objects.filter(tenant=tenant, status="posted").count()
        stats["active_applications"] = (JobApplication.objects.filter(tenant=tenant)
                                        .exclude(stage__in=APPLICATION_TERMINAL_STAGES).count())
        stats["new_candidates"] = CandidateProfile.objects.filter(
            tenant=tenant, created_at__year=today.year, created_at__month=today.month).count()
        # 3.18 goal setting — objectives currently in flight.
        stats["active_objectives"] = Objective.objects.filter(tenant=tenant, status="active").count()
        # 3.19 performance review — reviews not yet acknowledged (in flight).
        stats["open_reviews"] = PerformanceReview.objects.filter(
            tenant=tenant).exclude(status="acknowledged").count()
        # 3.27 communication hub — celebrations this month + pinned company announcements.
        stats["birthdays_this_month"] = employees.filter(date_of_birth__month=today.month).count()
        stats["pinned_announcements"] = Announcement.objects.filter(
            tenant=tenant, status="published", is_pinned=True).count()
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
        .annotate(balance_db=ExpressionWrapper(
            F("allocated_days") - F("used_days_db") - F("encashed_days"), output_field=_DEC)),
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
        "encashments": LeaveEncashment.objects.filter(
            tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type,
            year=obj.year).order_by("-created_at")[:20],
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
        # Approval mutates two models (the request + its attendance rows); wrap them so an
        # interrupted approve can't leave the request approved while attendance stays unsynced.
        # Mirrors the inverse leaverequest_cancel, which already runs under transaction.atomic().
        with transaction.atomic():
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


# ============================================================ Leave Encashment (3.10)
@login_required
def leaveencashment_list(request):
    return crud_list(
        request,
        LeaveEncashment.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "leave_type", "approver"),
        "hrm/leave/encashment/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False), ("employee", "employee_id", True),
                 ("leave_type", "leave_type_id", True)],
        extra_context={"status_choices": LeaveEncashment.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name"),
                       "leave_types": LeaveType.objects.filter(tenant=request.tenant, encashable=True).order_by("name")},
    )


@login_required
def leaveencashment_create(request):
    return crud_create(request, form_class=LeaveEncashmentForm,
                       template="hrm/leave/encashment/form.html", success_url="hrm:leaveencashment_list")


@login_required
def leaveencashment_detail(request, pk):
    obj = get_object_or_404(
        LeaveEncashment.objects.select_related("employee__party", "leave_type", "approver"),
        pk=pk, tenant=request.tenant)
    allocation = LeaveAllocation.objects.filter(
        tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type, year=obj.year).first()
    return render(request, "hrm/leave/encashment/detail.html", {"obj": obj, "allocation": allocation})


@login_required
def leaveencashment_edit(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status not in LeaveEncashment.OPEN_STATUSES:
        messages.error(request, "Only a draft or pending encashment can be edited.")
        return redirect("hrm:leaveencashment_detail", pk=obj.pk)
    return crud_edit(request, model=LeaveEncashment, pk=pk, form_class=LeaveEncashmentForm,
                     template="hrm/leave/encashment/form.html", success_url="hrm:leaveencashment_list")


@login_required
@require_POST
def leaveencashment_delete(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status not in LeaveEncashment.OPEN_STATUSES:
        messages.error(request, "A decided encashment cannot be deleted — cancel it instead.")
        return redirect("hrm:leaveencashment_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Encashment deleted.")
    return redirect("hrm:leaveencashment_list")


@login_required
@require_POST
def leaveencashment_submit(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Encashment {obj.number} submitted for approval.")
    return redirect("hrm:leaveencashment_detail", pk=obj.pk)


@tenant_admin_required  # approving an encashment consumes leave balance — privileged manager/admin action
@require_POST
def leaveencashment_approve(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        alloc = (LeaveAllocation.objects
                 .filter(tenant=request.tenant, employee=obj.employee, leave_type=obj.leave_type, year=obj.year)
                 .first())
        available = alloc.balance if alloc else Decimal("0")
        # Re-check balance at approval time — a pending request could exceed the balance if another
        # encashment was approved after it was raised.
        if obj.days > available:
            messages.error(request, f"Cannot approve — only {available} day(s) available to encash.")
            return redirect("hrm:leaveencashment_detail", pk=obj.pk)
        with transaction.atomic():
            obj.status = "approved"
            obj.approver = request.user
            obj.approved_at = timezone.now()
            obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
            obj.save(update_fields=["status", "approver", "approved_at", "decision_note", "updated_at"])
            # Encashment consumes leave: record it in encashed_days (NOT by shrinking allocated_days,
            # which the accrual engine recomputes — that would silently restore the cashed-out days).
            if alloc:
                alloc.encashed_days = (alloc.encashed_days or Decimal("0")) + obj.days
                alloc.save(update_fields=["encashed_days", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve", "days_consumed": str(obj.days)})
        messages.success(request, f"Encashment {obj.number} approved ({obj.days} day(s) consumed).")
    return redirect("hrm:leaveencashment_detail", pk=obj.pk)


@tenant_admin_required  # rejecting is a privileged manager/admin action
@require_POST
def leaveencashment_reject(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approver = request.user
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Encashment {obj.number} rejected.")
    return redirect("hrm:leaveencashment_detail", pk=obj.pk)


@tenant_admin_required  # recording the payout is a privileged finance/admin action
@require_POST
def leaveencashment_mark_paid(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    if obj.status == "approved":
        obj.status = "paid"
        obj.paid_on = timezone.localdate()
        obj.payment_reference = request.POST.get("payment_reference", "").strip()[:100]
        obj.save(update_fields=["status", "paid_on", "payment_reference", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "mark_paid", "reference": obj.payment_reference})
        messages.success(request, f"Encashment {obj.number} marked paid.")
    return redirect("hrm:leaveencashment_detail", pk=obj.pk)


@login_required
@require_POST
def leaveencashment_cancel(request, pk):
    obj = get_object_or_404(LeaveEncashment, pk=pk, tenant=request.tenant)
    # Cancellable only before a decision — an approved one already consumed balance (final).
    if obj.status in ("draft", "pending"):
        obj.status = "cancelled"
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Encashment {obj.number} cancelled.")
    return redirect("hrm:leaveencashment_detail", pk=obj.pk)


# ============================================================ Leave Policy engine (3.10)
def _policy_year(request):
    """Resolve the ?year / POSTed year param to an int, defaulting to the current year. Bounded to
    a sane window so an oversized all-digit string can't overflow PositiveSmallIntegerField and raise
    an unhandled DB error/500 (security-review: DoS / stack-trace leak if DEBUG)."""
    raw = (request.POST.get("year") or request.GET.get("year") or "").strip()
    if raw.isdigit():
        year = int(raw)
        if 2000 <= year <= 2100:
            return year
    return timezone.localdate().year


def _accrual_target(leave_type, year, current_year, current_month):
    """Days accrued for a leave type by ``year``: annual → the full grant; monthly → the per-month
    rate × elapsed months (12 for a past year, the current month for the current year)."""
    rate = leave_type.accrual_days or Decimal("0")
    if leave_type.accrual_rule == "annual":
        return rate
    if leave_type.accrual_rule == "monthly":
        if year > current_year:
            months = 0          # nothing has accrued yet for a future year
        elif year < current_year:
            months = 12         # a past year has fully accrued
        else:
            months = current_month
        return rate * Decimal(months)
    return Decimal("0")  # "none"


@login_required
def leave_policy(request):
    """Standalone Leave Policy page (no model, mirrors ``org_chart``): each ``LeaveType``'s accrual /
    carry-forward / encashment config for a selected year + admin run actions that mutate allocations."""
    tenant = request.tenant
    year = _policy_year(request)
    leave_types = (LeaveType.objects.filter(tenant=tenant).order_by("name")
                   if tenant is not None else LeaveType.objects.none())
    rows_by_type = {}
    active_employees = 0
    if tenant is not None:
        for r in (LeaveAllocation.objects.filter(tenant=tenant, year=year)
                  .values("leave_type_id")
                  .annotate(n=Count("pk"), total=Sum("allocated_days"), carried=Sum("carried_forward"))):
            rows_by_type[r["leave_type_id"]] = r
        active_employees = (EmployeeProfile.objects.filter(tenant=tenant)
                            .exclude(employment__status="terminated").count())
    policy_rows = [{
        "lt": lt,
        "alloc_count": rows_by_type.get(lt.pk, {}).get("n", 0),
        "total_days": rows_by_type.get(lt.pk, {}).get("total") or Decimal("0"),
        "carried": rows_by_type.get(lt.pk, {}).get("carried") or Decimal("0"),
    } for lt in leave_types]
    return render(request, "hrm/leave/policy.html", {
        "policy_rows": policy_rows,
        "year": year,
        "next_year": year + 1,
        "prev_year": year - 1,
        "active_employees": active_employees,
        "current_year": timezone.localdate().year,
    })


@tenant_admin_required  # accrual mutates every employee's entitlement — privileged
@require_POST
def leave_accrual_run(request):
    tenant = request.tenant
    year = _policy_year(request)
    today = timezone.localdate()
    ZERO = Decimal("0")
    employees = list(EmployeeProfile.objects.filter(tenant=tenant).exclude(employment__status="terminated"))
    leave_types = list(LeaveType.objects.filter(tenant=tenant, is_active=True).exclude(accrual_rule="none"))
    touched = 0
    with transaction.atomic():
        for lt in leave_types:
            target = _accrual_target(lt, year, today.year, today.month)
            cap = lt.max_balance or ZERO
            for emp in employees:
                alloc, _ = LeaveAllocation.objects.get_or_create(
                    tenant=tenant, employee=emp, leave_type=lt, year=year,
                    defaults={"allocated_days": ZERO, "status": "active"})
                total = target + (alloc.carried_forward or ZERO)
                if cap > ZERO:
                    total = min(total, cap)
                if alloc.allocated_days != total or alloc.status != "active":
                    alloc.allocated_days = total
                    alloc.status = "active"
                    alloc.save(update_fields=["allocated_days", "status", "updated_at"])
                    touched += 1
    # AuditLog.action is a 10-char choices field (create/update/delete) — keep the verb in `changes`.
    write_audit_log(request.user, None, "update",
                    changes={"action": "leave_accrual_run", "year": year, "allocations_updated": touched},
                    tenant=tenant)
    messages.success(request, f"Accrual run for {year}: {touched} allocation(s) updated "
                              f"across {len(leave_types)} accruing leave type(s).")
    return redirect(f"{reverse('hrm:leave_policy')}?year={year}")


@tenant_admin_required  # carry-forward mutates next-year entitlements — privileged
@require_POST
def leave_carryforward_run(request):
    tenant = request.tenant
    year = _policy_year(request)
    dest_year = year + 1
    ZERO = Decimal("0")
    leave_types = list(LeaveType.objects.filter(tenant=tenant, is_active=True, max_carry_forward__gt=0))
    type_ids = [lt.pk for lt in leave_types]
    cf_cap = {lt.pk: (lt.max_carry_forward or ZERO) for lt in leave_types}
    bal_cap = {lt.pk: (lt.max_balance or ZERO) for lt in leave_types}  # dest-year total cap
    # Source-year approved usage per (employee, leave_type) in one grouped query (avoids per-row N+1).
    used_map = {}
    for r in (LeaveRequest.objects.filter(tenant=tenant, status="approved", start_date__year=year,
                                          leave_type_id__in=type_ids)
              .values("employee_id", "leave_type_id").annotate(s=Sum("days"))):
        used_map[(r["employee_id"], r["leave_type_id"])] = r["s"] or ZERO
    touched = 0
    with transaction.atomic():
        for src in (LeaveAllocation.objects
                    .filter(tenant=tenant, year=year, leave_type_id__in=type_ids)):
            used = used_map.get((src.employee_id, src.leave_type_id), ZERO)
            # Net out both taken (LeaveRequest) and cashed-out (LeaveEncashment) days — a day already
            # encashed must not also be carried forward (a type can be both encashable + carriable).
            balance = (src.allocated_days or ZERO) - used - (src.encashed_days or ZERO)
            carry = min(max(balance, ZERO), cf_cap.get(src.leave_type_id, ZERO))
            dst, _ = LeaveAllocation.objects.get_or_create(
                tenant=tenant, employee_id=src.employee_id, leave_type_id=src.leave_type_id, year=dest_year,
                defaults={"allocated_days": ZERO, "status": "active"})
            # Replace this run's own prior contribution instead of double-adding (idempotent).
            new_total = (dst.allocated_days or ZERO) - (dst.carried_forward or ZERO) + carry
            cap = bal_cap.get(src.leave_type_id, ZERO)
            if cap > ZERO:
                new_total = min(new_total, cap)  # never push the dest-year total past max_balance
            if dst.allocated_days != new_total or dst.carried_forward != carry or dst.status != "active":
                dst.allocated_days = new_total
                dst.carried_forward = carry
                dst.status = "active"
                dst.save(update_fields=["allocated_days", "carried_forward", "status", "updated_at"])
                touched += 1
    write_audit_log(request.user, None, "update",
                    changes={"action": "leave_carryforward_run", "from_year": year, "to_year": dest_year,
                             "allocations_updated": touched}, tenant=tenant)
    messages.success(request, f"Carry-forward {year} → {dest_year}: {touched} allocation(s) updated.")
    return redirect(f"{reverse('hrm:leave_policy')}?year={dest_year}")


# ============================================================ Timesheets (3.11)
@login_required
def timesheet_list(request):
    qs = (Timesheet.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "approver"))
    date_from = _parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = _parse_iso_date(request.GET.get("date_to", "").strip())
    if date_from:
        qs = qs.filter(period_start__gte=date_from)
    if date_to:
        qs = qs.filter(period_start__lte=date_to)
    return crud_list(
        request, qs, "hrm/timetracking/timesheet/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False), ("employee", "employee_id", True)],
        extra_context={"status_choices": Timesheet.STATUS_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def timesheet_create(request):
    return crud_create(request, form_class=TimesheetForm, template="hrm/timetracking/timesheet/form.html",
                       success_url="hrm:timesheet_list")


@login_required
def timesheet_detail(request, pk):
    obj = get_object_or_404(
        Timesheet.objects.select_related("employee__party", "approver"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/timetracking/timesheet/detail.html", {
        "obj": obj,
        "entries": obj.entries.select_related("project").order_by("date"),
        "entry_form": TimesheetEntryForm(tenant=request.tenant),
        "can_edit_entries": obj.status in Timesheet.OPEN_STATUSES,
    })


@login_required
def timesheet_edit(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status not in Timesheet.OPEN_STATUSES:
        messages.error(request, "Only a draft or pending timesheet can be edited.")
        return redirect("hrm:timesheet_detail", pk=obj.pk)
    return crud_edit(request, model=Timesheet, pk=pk, form_class=TimesheetForm,
                     template="hrm/timetracking/timesheet/form.html", success_url="hrm:timesheet_list")


@login_required
@require_POST
def timesheet_delete(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status not in Timesheet.OPEN_STATUSES:
        messages.error(request, "A decided timesheet cannot be deleted — cancel it instead.")
        return redirect("hrm:timesheet_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Timesheet deleted.")
    return redirect("hrm:timesheet_list")


@login_required
@require_POST
def timesheet_submit(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Timesheet {obj.number} submitted for approval.")
    return redirect("hrm:timesheet_detail", pk=obj.pk)


@tenant_admin_required  # approving a timesheet is a privileged manager/admin action
@require_POST
def timesheet_approve(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.refresh_totals(save=False)  # final recompute of the derived totals before locking
        obj.status = "approved"
        obj.approver = request.user
        obj.approved_at = timezone.now()
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "approved_at", "decision_note",
                                "total_hours", "billable_hours", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve", "total_hours": str(obj.total_hours)})
        messages.success(request, f"Timesheet {obj.number} approved.")
    return redirect("hrm:timesheet_detail", pk=obj.pk)


@tenant_admin_required  # rejecting a timesheet is a privileged manager/admin action
@require_POST
def timesheet_reject(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approver = request.user
        obj.rejected_reason = request.POST.get("rejected_reason", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "rejected_reason", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Timesheet {obj.number} rejected.")
    return redirect("hrm:timesheet_detail", pk=obj.pk)


@login_required
@require_POST
def timesheet_cancel(request, pk):
    obj = get_object_or_404(Timesheet, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "pending"):
        obj.status = "cancelled"
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Timesheet {obj.number} cancelled.")
    return redirect("hrm:timesheet_detail", pk=obj.pk)


# --- TimesheetEntry: inline child rows managed on the timesheet hub (locked once approved) ---
@login_required
@require_POST
def timesheetentry_add(request, ts_pk):
    ts = get_object_or_404(Timesheet, pk=ts_pk, tenant=request.tenant)
    if ts.status not in Timesheet.OPEN_STATUSES:
        messages.error(request, "Cannot modify entries on a decided timesheet.")
        return redirect("hrm:timesheet_detail", pk=ts.pk)
    # Preset tenant+timesheet on the instance so the model clean()'s date-in-period check runs on validate.
    form = TimesheetEntryForm(request.POST,
                              instance=TimesheetEntry(tenant=request.tenant, timesheet=ts),
                              tenant=request.tenant)
    if form.is_valid():
        form.save()
        ts.refresh_totals()
        write_audit_log(request.user, ts, "update", {"action": "entry_add"})
        messages.success(request, "Entry added.")
        return redirect("hrm:timesheet_detail", pk=ts.pk)
    # Re-render the hub with the bound, errored add-form so field errors + typed input are preserved.
    return render(request, "hrm/timetracking/timesheet/detail.html", {
        "obj": ts,
        "entries": ts.entries.select_related("project").order_by("date"),
        "entry_form": form,
        "can_edit_entries": True,
    })


@login_required
def timesheetentry_edit(request, pk):
    entry = get_object_or_404(TimesheetEntry.objects.select_related("timesheet"), pk=pk, tenant=request.tenant)
    ts = entry.timesheet
    if ts.status not in Timesheet.OPEN_STATUSES:
        messages.error(request, "Cannot modify entries on a decided timesheet.")
        return redirect("hrm:timesheet_detail", pk=ts.pk)
    if request.method == "POST":
        form = TimesheetEntryForm(request.POST, instance=entry, tenant=request.tenant)
        if form.is_valid():
            form.save()
            ts.refresh_totals()
            write_audit_log(request.user, ts, "update", {"action": "entry_edit"})
            messages.success(request, "Entry updated.")
            return redirect("hrm:timesheet_detail", pk=ts.pk)
    else:
        form = TimesheetEntryForm(instance=entry, tenant=request.tenant)
    return render(request, "hrm/timetracking/timesheetentry/form.html",
                  {"form": form, "obj": entry, "timesheet": ts, "is_edit": True})


@login_required
@require_POST
def timesheetentry_delete(request, pk):
    entry = get_object_or_404(TimesheetEntry.objects.select_related("timesheet"), pk=pk, tenant=request.tenant)
    ts = entry.timesheet
    if ts.status not in Timesheet.OPEN_STATUSES:
        messages.error(request, "Cannot modify entries on a decided timesheet.")
        return redirect("hrm:timesheet_detail", pk=ts.pk)
    entry.delete()
    ts.refresh_totals()
    write_audit_log(request.user, ts, "update", {"action": "entry_delete"})
    messages.success(request, "Entry removed.")
    return redirect("hrm:timesheet_detail", pk=ts.pk)


# ============================================================ Overtime Requests (3.11)
@login_required
def overtimerequest_list(request):
    qs = (OvertimeRequest.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "approver", "timesheet"))
    date_from = _parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = _parse_iso_date(request.GET.get("date_to", "").strip())
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)
    return crud_list(
        request, qs, "hrm/timetracking/overtimerequest/list.html",
        search_fields=["number", "employee__party__name", "reason"],
        filters=[("status", "status", False), ("payout_method", "payout_method", False),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": OvertimeRequest.STATUS_CHOICES,
                       "payout_choices": OvertimeRequest.PAYOUT_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def overtimerequest_create(request):
    return crud_create(request, form_class=OvertimeRequestForm,
                       template="hrm/timetracking/overtimerequest/form.html", success_url="hrm:overtimerequest_list")


@login_required
def overtimerequest_detail(request, pk):
    obj = get_object_or_404(
        OvertimeRequest.objects.select_related("employee__party", "approver", "timesheet"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/timetracking/overtimerequest/detail.html", {"obj": obj})


@login_required
def overtimerequest_edit(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status not in OvertimeRequest.OPEN_STATUSES:
        messages.error(request, "Only a draft or pending overtime request can be edited.")
        return redirect("hrm:overtimerequest_detail", pk=obj.pk)
    return crud_edit(request, model=OvertimeRequest, pk=pk, form_class=OvertimeRequestForm,
                     template="hrm/timetracking/overtimerequest/form.html", success_url="hrm:overtimerequest_list")


@login_required
@require_POST
def overtimerequest_delete(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status not in OvertimeRequest.OPEN_STATUSES:
        messages.error(request, "A decided overtime request cannot be deleted — cancel it instead.")
        return redirect("hrm:overtimerequest_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Overtime request deleted.")
    return redirect("hrm:overtimerequest_list")


@login_required
@require_POST
def overtimerequest_submit(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Overtime request {obj.number} submitted for approval.")
    return redirect("hrm:overtimerequest_detail", pk=obj.pk)


@tenant_admin_required  # approving overtime is a privileged manager/admin action
@require_POST
def overtimerequest_approve(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "approved"
        obj.approver = request.user
        obj.approved_at = timezone.now()
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "approved_at", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve"})
        messages.success(request, f"Overtime request {obj.number} approved.")
    return redirect("hrm:overtimerequest_detail", pk=obj.pk)


@tenant_admin_required  # rejecting overtime is a privileged manager/admin action
@require_POST
def overtimerequest_reject(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approver = request.user
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Overtime request {obj.number} rejected.")
    return redirect("hrm:overtimerequest_detail", pk=obj.pk)


@login_required
@require_POST
def overtimerequest_cancel(request, pk):
    obj = get_object_or_404(OvertimeRequest, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "pending"):
        obj.status = "cancelled"
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Overtime request {obj.number} cancelled.")
    return redirect("hrm:overtimerequest_detail", pk=obj.pk)


# ============================================================ Time Tracking reports (3.11)
@login_required
def timesheet_utilization_report(request):
    """Per-employee billable-hours ÷ total-hours over APPROVED timesheets (derived, no model).
    Optional ``?date_from``/``?date_to`` bound by the timesheet period start."""
    tenant = request.tenant
    rows = []
    date_from = _parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = _parse_iso_date(request.GET.get("date_to", "").strip())
    if tenant is not None:
        qs = TimesheetEntry.objects.filter(tenant=tenant, timesheet__status="approved")
        if date_from:
            qs = qs.filter(timesheet__period_start__gte=date_from)
        if date_to:
            qs = qs.filter(timesheet__period_start__lte=date_to)
        for d in (qs.values("timesheet__employee_id", "timesheet__employee__party__name")
                  .annotate(total=Sum("hours"), billable=Sum("hours", filter=Q(is_billable=True)))
                  .order_by("timesheet__employee__party__name")):
            total = d["total"] or Decimal("0")
            billable = d["billable"] or Decimal("0")
            pct = (billable / total * 100).quantize(Decimal("0.1")) if total else Decimal("0")
            rows.append({"employee": d["timesheet__employee__party__name"],
                         "total": total, "billable": billable, "utilization": pct})
    return render(request, "hrm/timetracking/utilization_report.html", {"rows": rows})


@login_required
def project_time_report(request):
    """Per-``accounting.Project`` logged hours vs budget (derived, no model).
    Optional ``?date_from``/``?date_to`` bound by the entry date."""
    tenant = request.tenant
    rows = []
    date_from = _parse_iso_date(request.GET.get("date_from", "").strip())
    date_to = _parse_iso_date(request.GET.get("date_to", "").strip())
    if tenant is not None:
        qs = TimesheetEntry.objects.filter(tenant=tenant, project__isnull=False)
        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        # Alias the aggregates away from the `hours` field name — an annotation named `hours` would
        # shadow the field and make the second Sum("hours", ...) raise "hours is an aggregate".
        for d in (qs.values("project__number", "project__name", "project__budget_amount")
                  .annotate(logged=Sum("hours"), billable=Sum("hours", filter=Q(is_billable=True)))
                  .order_by("project__name")):
            rows.append({"number": d["project__number"], "name": d["project__name"],
                         "budget": d["project__budget_amount"] or Decimal("0"),
                         "hours": d["logged"] or Decimal("0"),
                         "billable_hours": d["billable"] or Decimal("0")})
    return render(request, "hrm/timetracking/project_time_report.html", {"rows": rows})


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
        filters=[("is_optional", "is_optional", False), ("category", "category", False)],
        extra_context={"year_choices": years, "category_choices": PublicHoliday.CATEGORY_CHOICES},
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


# ============================================================ Holiday Policies (3.12)
@login_required
def holidaypolicy_list(request):
    return crud_list(
        request,
        HolidayPolicy.objects.filter(tenant=request.tenant).select_related("org_unit", "designation"),
        "hrm/holiday/holidaypolicy/list.html",
        search_fields=["name", "location"],
        filters=[("is_active", "is_active", False), ("employee_type", "employee_type", False),
                 ("org_unit", "org_unit_id", True), ("designation", "designation_id", True)],
        extra_context={
            "employee_type_choices": EmployeeProfile.EMPLOYEE_TYPE_CHOICES,
            "org_units": OrgUnit.objects.filter(tenant=request.tenant).order_by("name"),
            "designations": Designation.objects.filter(tenant=request.tenant).order_by("name"),
        },
    )


@login_required
def holidaypolicy_create(request):
    return crud_create(request, form_class=HolidayPolicyForm,
                       template="hrm/holiday/holidaypolicy/form.html", success_url="hrm:holidaypolicy_list")


@login_required
def holidaypolicy_detail(request, pk):
    obj = get_object_or_404(
        HolidayPolicy.objects.select_related("org_unit", "designation").prefetch_related("holidays"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/holiday/holidaypolicy/detail.html", {
        "obj": obj,
        # .all() (not .order_by) serves from the prefetch_related cache above; PublicHoliday.Meta
        # already orders by date, so this stays date-sorted with zero extra queries.
        "policy_holidays": obj.holidays.all(),
        "recent_elections": (obj.elections.select_related("employee__party", "holiday")
                             .all()[:10]),
    })


@login_required
def holidaypolicy_edit(request, pk):
    return crud_edit(request, model=HolidayPolicy, pk=pk, form_class=HolidayPolicyForm,
                     template="hrm/holiday/holidaypolicy/form.html", success_url="hrm:holidaypolicy_list")


@login_required
@require_POST
def holidaypolicy_delete(request, pk):
    return crud_delete(request, model=HolidayPolicy, pk=pk, success_url="hrm:holidaypolicy_list")


# ============================================================ Floating Holiday Elections (3.12)
@login_required
def floatingholidayelection_list(request):
    return crud_list(
        request,
        FloatingHolidayElection.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "holiday", "policy"),
        "hrm/holiday/floatingholidayelection/list.html",
        search_fields=["employee__party__name", "holiday__name"],
        filters=[("status", "status", False), ("employee", "employee_id", True),
                 ("holiday", "holiday_id", True)],
        extra_context={
            "status_choices": FloatingHolidayElection.STATUS_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "holidays": (PublicHoliday.objects.filter(tenant=request.tenant, is_optional=True)
                         .order_by("date")),
        },
    )


@login_required
def floatingholidayelection_create(request):
    return crud_create(request, form_class=FloatingHolidayElectionForm,
                       template="hrm/holiday/floatingholidayelection/form.html",
                       success_url="hrm:floatingholidayelection_list")


@login_required
def floatingholidayelection_detail(request, pk):
    obj = get_object_or_404(
        FloatingHolidayElection.objects.select_related(
            "employee__party", "holiday", "policy", "approved_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/holiday/floatingholidayelection/detail.html", {"obj": obj})


@login_required
def floatingholidayelection_edit(request, pk):
    obj = get_object_or_404(FloatingHolidayElection, pk=pk, tenant=request.tenant)
    # Only a pending election is editable — a decided (approved/rejected) one is locked so a direct
    # POST can't silently rewrite the employee/holiday/note of a record that's already been decided.
    if obj.status != "pending":
        messages.error(request, "Only a pending floating-holiday election can be edited.")
        return redirect("hrm:floatingholidayelection_detail", pk=obj.pk)
    return crud_edit(request, model=FloatingHolidayElection, pk=pk, form_class=FloatingHolidayElectionForm,
                     template="hrm/holiday/floatingholidayelection/form.html",
                     success_url="hrm:floatingholidayelection_list")


@login_required
@require_POST
def floatingholidayelection_delete(request, pk):
    obj = get_object_or_404(FloatingHolidayElection, pk=pk, tenant=request.tenant)
    # A decided election is locked — its approval history must not be silently deleted via a direct POST.
    if obj.status != "pending":
        messages.error(request, "A decided floating-holiday election cannot be deleted.")
        return redirect("hrm:floatingholidayelection_detail", pk=obj.pk)
    return crud_delete(request, model=FloatingHolidayElection, pk=pk,
                       success_url="hrm:floatingholidayelection_list")


@tenant_admin_required  # approving a floating-holiday election is a privileged manager/admin action
@require_POST
def floatingholidayelection_approve(request, pk):
    obj = get_object_or_404(FloatingHolidayElection, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "approved"
        obj.approved_by = request.user
        obj.approved_at = timezone.now()
        obj.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve"})
        messages.success(request, "Floating-holiday election approved.")
    return redirect("hrm:floatingholidayelection_detail", pk=obj.pk)


@tenant_admin_required  # rejecting a floating-holiday election is a privileged manager/admin action
@require_POST
def floatingholidayelection_reject(request, pk):
    obj = get_object_or_404(FloatingHolidayElection, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approved_by = request.user
        reason = request.POST.get("note", "").strip()[:2000]
        if reason:
            obj.note = reason
        obj.save(update_fields=["status", "approved_by", "note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, "Floating-holiday election rejected.")
    return redirect("hrm:floatingholidayelection_detail", pk=obj.pk)


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
          .select_related("employee__party", "shift", "geofence"))
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
        AttendanceRecord.objects.select_related("employee__party", "shift", "geofence"), pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/record/detail.html", {
        "obj": obj,
        "regularizations": obj.regularizations.select_related("approver").order_by("-created_at"),
    })


@login_required
def attendancerecord_edit(request, pk):
    return crud_edit(request, model=AttendanceRecord, pk=pk, form_class=AttendanceRecordForm,
                     template="hrm/attendance/record/form.html", success_url="hrm:attendancerecord_list")


@login_required
@require_POST
def attendancerecord_delete(request, pk):
    return crud_delete(request, model=AttendanceRecord, pk=pk, success_url="hrm:attendancerecord_list")


# ============================================================ Geofences (3.9)
@login_required
def geofence_list(request):
    return crud_list(
        request,
        GeoFence.objects.filter(tenant=request.tenant)
        .annotate(punch_count=Count("attendance_records")).order_by("name"),
        "hrm/attendance/geofence/list.html",
        search_fields=["name", "address"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def geofence_create(request):
    return crud_create(request, form_class=GeoFenceForm, template="hrm/attendance/geofence/form.html",
                       success_url="hrm:geofence_list")


@login_required
def geofence_detail(request, pk):
    obj = get_object_or_404(GeoFence, pk=pk, tenant=request.tenant)
    # Materialise the punches and prime each row's geofence FK cache with the zone we already hold
    # — the template calls rec.geo_status() per row (touches rec.geofence); without this each row
    # would fire its own SELECT (Django caches the FK per-instance, not per-value).
    recent_punches = list(AttendanceRecord.objects.filter(tenant=request.tenant, geofence=obj)
                          .select_related("employee__party").order_by("-date")[:20])
    for rec in recent_punches:
        rec.geofence = obj
    return render(request, "hrm/attendance/geofence/detail.html", {
        "obj": obj,
        "recent_punches": recent_punches,
    })


@login_required
def geofence_edit(request, pk):
    return crud_edit(request, model=GeoFence, pk=pk, form_class=GeoFenceForm,
                     template="hrm/attendance/geofence/form.html", success_url="hrm:geofence_list")


@login_required
@require_POST
def geofence_delete(request, pk):
    obj = get_object_or_404(GeoFence, pk=pk, tenant=request.tenant)
    # Preserve the geo-audit trail on existing punches: block delete while any reference it.
    if AttendanceRecord.objects.filter(tenant=request.tenant, geofence=obj).exists():
        messages.error(request, "Cannot delete a geofence linked to attendance records. Deactivate it instead.")
        return redirect("hrm:geofence_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Geofence deleted.")
    return redirect("hrm:geofence_list")


# ============================================================ Attendance Regularization (3.9)
@login_required
def attendanceregularization_list(request):
    return crud_list(
        request,
        AttendanceRegularization.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "attendance_record", "approver"),
        "hrm/attendance/regularization/list.html",
        search_fields=["number", "employee__party__name", "reason"],
        filters=[("status", "status", False), ("reason_type", "reason_type", False),
                 ("employee", "employee_id", True)],
        extra_context={"status_choices": AttendanceRegularization.STATUS_CHOICES,
                       "reason_type_choices": AttendanceRegularization.REASON_TYPE_CHOICES,
                       "employees": EmployeeProfile.objects.filter(tenant=request.tenant)
                       .select_related("party").order_by("party__name")},
    )


@login_required
def attendanceregularization_create(request):
    return crud_create(request, form_class=AttendanceRegularizationForm,
                       template="hrm/attendance/regularization/form.html",
                       success_url="hrm:attendanceregularization_list")


@login_required
def attendanceregularization_detail(request, pk):
    obj = get_object_or_404(
        AttendanceRegularization.objects.select_related("employee__party", "attendance_record", "approver"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/attendance/regularization/detail.html", {"obj": obj})


@login_required
def attendanceregularization_edit(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    # Only an open (draft/pending) request is editable — a decided one is locked.
    if obj.status not in AttendanceRegularization.OPEN_STATUSES:
        messages.error(request, "Only a draft or pending regularization can be edited.")
        return redirect("hrm:attendanceregularization_detail", pk=obj.pk)
    return crud_edit(request, model=AttendanceRegularization, pk=pk, form_class=AttendanceRegularizationForm,
                     template="hrm/attendance/regularization/form.html",
                     success_url="hrm:attendanceregularization_list")


@login_required
@require_POST
def attendanceregularization_delete(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    if obj.status in ("approved", "rejected"):
        messages.error(request, "A decided regularization cannot be deleted — cancel it instead.")
        return redirect("hrm:attendanceregularization_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Regularization deleted.")
    return redirect("hrm:attendanceregularization_list")


@login_required
@require_POST
def attendanceregularization_submit(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Regularization {obj.number} submitted for approval.")
    return redirect("hrm:attendanceregularization_detail", pk=obj.pk)


@tenant_admin_required  # approving a regularization rewrites an attendance punch — privileged action
@require_POST
def attendanceregularization_approve(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        with transaction.atomic():
            # Resolve the punch to correct: the explicitly linked one, else an existing row for
            # (employee, date), else materialise a fresh regularized punch (handles a request raised
            # before any attendance row existed — the workflow always produces a corrected record).
            rec = obj.attendance_record
            if rec is None:
                rec = (AttendanceRecord.objects
                       .filter(tenant=request.tenant, employee=obj.employee, date=obj.date)
                       .first())
                if rec is None:
                    rec = AttendanceRecord(tenant=request.tenant, employee=obj.employee, date=obj.date)
            if obj.requested_check_in is not None:
                rec.check_in = obj.requested_check_in
            if obj.requested_check_out is not None:
                rec.check_out = obj.requested_check_out
            rec.status = "regularized"
            rec.source = "manual"
            rec.save()  # save() recomputes hours_worked + assigns an ATT- number when newly created
            obj.status = "approved"
            obj.approver = request.user
            obj.approved_at = timezone.now()
            obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
            obj.attendance_record = rec  # link back so the audit trail records which punch was fixed
            obj.save(update_fields=["status", "approver", "approved_at", "decision_note",
                                    "attendance_record", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve", "applied": f"record {rec.number} → regularized"})
        messages.success(request, f"Regularization {obj.number} approved (record {rec.number} → regularized).")
    return redirect("hrm:attendanceregularization_detail", pk=obj.pk)


@tenant_admin_required  # rejecting is a privileged manager/admin action
@require_POST
def attendanceregularization_reject(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.approver = request.user
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "approver", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Regularization {obj.number} rejected.")
    return redirect("hrm:attendanceregularization_detail", pk=obj.pk)


@login_required
@require_POST
def attendanceregularization_cancel(request, pk):
    obj = get_object_or_404(AttendanceRegularization, pk=pk, tenant=request.tenant)
    # Cancellable only before a decision — an approved one already rewrote the punch (final).
    if obj.status in ("draft", "pending"):
        obj.status = "cancelled"
        obj.decision_note = request.POST.get("decision_note", "").strip()[:2000]
        obj.save(update_fields=["status", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Regularization {obj.number} cancelled.")
    return redirect("hrm:attendanceregularization_detail", pk=obj.pk)


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
        .select_related("application__candidate", "application__requisition__hiring_manager__party",
                        "offer_letter_template"), pk=pk)


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
        # The manual-transition subset the "Update Status" dropdown offers (kept in lockstep with the
        # view guard below via the shared BGV_MANUAL_TRANSITION_STATUSES constant).
        "transition_status_choices": [(v, lbl) for v, lbl in BGV_STATUS_CHOICES
                                      if v in BGV_MANUAL_TRANSITION_STATUSES],
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


@tenant_admin_required  # running a background check is a privileged HR/compliance action
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


@tenant_admin_required  # advancing a compliance check is a privileged HR action
@require_POST
def backgroundverification_mark_status(request, pk):
    # Manual stand-in for the deferred vendor webhook: move the check through its intermediate statuses.
    obj = _bgv_or_404(request, pk)
    new_status = request.POST.get("status", "")
    if new_status not in BGV_MANUAL_TRANSITION_STATUSES:
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


@tenant_admin_required  # stamping the Clear/Consider verdict is a hire-relevant compliance decision
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


@tenant_admin_required  # destructive — dropping a required compliance item is a privileged HR action
@require_POST
def preboardingitem_delete(request, pk):
    item = _preboarding_or_404(request, pk)
    offer_pk = item.offer_id
    write_audit_log(request.user, item, "delete", {"action": "remove_preboarding_item"})
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


# ============================================================ Pay Components (3.13)
@login_required
def paycomponent_list(request):
    return crud_list(
        request,
        PayComponent.objects.filter(tenant=request.tenant),
        "hrm/salary/paycomponent/list.html",
        search_fields=["name", "code", "description"],
        filters=[("component_type", "component_type", False), ("calculation_type", "calculation_type", False),
                 ("frequency", "frequency", False), ("is_active", "is_active", False)],
        extra_context={
            "component_type_choices": PayComponent.COMPONENT_TYPE_CHOICES,
            "calculation_type_choices": PayComponent.CALCULATION_TYPE_CHOICES,
            "frequency_choices": PayComponent.FREQUENCY_CHOICES,
        },
    )


@login_required
def paycomponent_create(request):
    return crud_create(request, form_class=PayComponentForm,
                       template="hrm/salary/paycomponent/form.html", success_url="hrm:paycomponent_list")


@login_required
def paycomponent_detail(request, pk):
    obj = get_object_or_404(PayComponent, pk=pk, tenant=request.tenant)
    return render(request, "hrm/salary/paycomponent/detail.html", {
        "obj": obj,
        # Templates whose breakdown references this component (PROTECT FK → default reverse accessor).
        "usage_lines": (obj.salarystructureline_set.select_related("template")
                        .order_by("template__name")[:10]),
    })


@login_required
def paycomponent_edit(request, pk):
    return crud_edit(request, model=PayComponent, pk=pk, form_class=PayComponentForm,
                     template="hrm/salary/paycomponent/form.html", success_url="hrm:paycomponent_list")


@login_required
@require_POST
def paycomponent_delete(request, pk):
    # SalaryStructureLine.pay_component is PROTECT — guard so an in-use component gives a friendly
    # message instead of a raw ProtectedError 500.
    obj = get_object_or_404(PayComponent, pk=pk, tenant=request.tenant)
    if obj.salarystructureline_set.exists():
        messages.error(request, "This component is used by one or more salary structures — remove those lines first.")
        return redirect("hrm:paycomponent_detail", pk=obj.pk)
    return crud_delete(request, model=PayComponent, pk=pk, success_url="hrm:paycomponent_list")


# ============================================================ Salary Structure Templates (3.13)
@login_required
def salarystructuretemplate_list(request):
    return crud_list(
        request,
        SalaryStructureTemplate.objects.filter(tenant=request.tenant).select_related("job_grade"),
        "hrm/salary/salarystructuretemplate/list.html",
        search_fields=["name", "number"],
        filters=[("job_grade", "job_grade_id", True), ("is_active", "is_active", False)],
        extra_context={"job_grades": JobGrade.objects.filter(tenant=request.tenant).order_by("level_order", "name")},
    )


@login_required
def salarystructuretemplate_create(request):
    return crud_create(request, form_class=SalaryStructureTemplateForm,
                       template="hrm/salary/salarystructuretemplate/form.html",
                       success_url="hrm:salarystructuretemplate_list")


@login_required
def salarystructuretemplate_detail(request, pk):
    obj = get_object_or_404(
        SalaryStructureTemplate.objects.select_related("job_grade"), pk=pk, tenant=request.tenant)
    lines = list(obj.lines.select_related("pay_component").order_by("sequence", "id"))
    return render(request, "hrm/salary/salarystructuretemplate/detail.html", {
        "obj": obj,
        "lines": lines,
        # Compute the CTC total once from the already-fetched lines (avoids the computed_ctc_total
        # property re-issuing its own lines query for each of the two places the template shows it).
        "ctc_total": sum((ln.resolved_amount() for ln in lines), Decimal("0")),
        "line_form": SalaryStructureLineForm(tenant=request.tenant),
    })


@login_required
def salarystructuretemplate_edit(request, pk):
    return crud_edit(request, model=SalaryStructureTemplate, pk=pk, form_class=SalaryStructureTemplateForm,
                     template="hrm/salary/salarystructuretemplate/form.html",
                     success_url="hrm:salarystructuretemplate_list")


@login_required
@require_POST
def salarystructuretemplate_delete(request, pk):
    return crud_delete(request, model=SalaryStructureTemplate, pk=pk,
                       success_url="hrm:salarystructuretemplate_list")


# ------------------------------------------------------ Salary Structure Lines (inline on the template)
@login_required
@require_POST
def salarystructureline_add(request, template_pk):
    template = get_object_or_404(SalaryStructureTemplate, pk=template_pk, tenant=request.tenant)
    # Preset tenant+template on the instance so the form's clean() duplicate check sees the template
    # during validation and form.save() persists the right FK (mirrors timesheetentry_add).
    form = SalaryStructureLineForm(
        request.POST,
        instance=SalaryStructureLine(tenant=request.tenant, template=template),
        tenant=request.tenant)
    if form.is_valid():
        form.save()
        write_audit_log(request.user, template, "update", {"action": "line_add"})
        messages.success(request, "Component line added.")
        return redirect("hrm:salarystructuretemplate_detail", pk=template.pk)
    # Re-render the detail hub with the bound, errored add-form (field errors + typed input preserved).
    lines = list(template.lines.select_related("pay_component").order_by("sequence", "id"))
    return render(request, "hrm/salary/salarystructuretemplate/detail.html", {
        "obj": template,
        "lines": lines,
        "ctc_total": sum((ln.resolved_amount() for ln in lines), Decimal("0")),
        "line_form": form,
    })


@login_required
def salarystructureline_edit(request, pk):
    line = get_object_or_404(SalaryStructureLine.objects.select_related("template"), pk=pk, tenant=request.tenant)
    template = line.template
    if request.method == "POST":
        form = SalaryStructureLineForm(request.POST, instance=line, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, template, "update", {"action": "line_edit"})
            messages.success(request, "Component line updated.")
            return redirect("hrm:salarystructuretemplate_detail", pk=template.pk)
    else:
        form = SalaryStructureLineForm(instance=line, tenant=request.tenant)
    return render(request, "hrm/salary/salarystructuretemplate/line_form.html",
                  {"form": form, "obj": line, "template": template, "is_edit": True})


@login_required
@require_POST
def salarystructureline_delete(request, pk):
    line = get_object_or_404(SalaryStructureLine.objects.select_related("template"), pk=pk, tenant=request.tenant)
    template_pk = line.template_id
    write_audit_log(request.user, line.template, "update", {"action": "line_delete"})
    line.delete()
    messages.success(request, "Component line removed.")
    return redirect("hrm:salarystructuretemplate_detail", pk=template_pk)


# ============================================================ Employee Salary Structures (3.13)
@login_required
def employeesalarystructure_list(request):
    return crud_list(
        request,
        EmployeeSalaryStructure.objects.filter(tenant=request.tenant)
        .select_related("employee__party", "template"),
        "hrm/salary/employeesalarystructure/list.html",
        search_fields=["employee__party__name", "number"],
        filters=[("status", "status", False), ("employee", "employee_id", True),
                 ("template", "template_id", True)],
        extra_context={
            "status_choices": EmployeeSalaryStructure.STATUS_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "templates": SalaryStructureTemplate.objects.filter(tenant=request.tenant).order_by("name"),
        },
    )


@login_required
def employeesalarystructure_create(request):
    return crud_create(request, form_class=EmployeeSalaryStructureForm,
                       template="hrm/salary/employeesalarystructure/form.html",
                       success_url="hrm:employeesalarystructure_list")


@login_required
def employeesalarystructure_detail(request, pk):
    obj = get_object_or_404(
        EmployeeSalaryStructure.objects.select_related("employee__party", "template"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/salary/employeesalarystructure/detail.html", {"obj": obj})


@login_required
def employeesalarystructure_edit(request, pk):
    obj = get_object_or_404(EmployeeSalaryStructure, pk=pk, tenant=request.tenant)
    # A superseded (historical) assignment is read-only — compensation history must not be silently
    # rewritten via a direct POST (a payroll run may depend on it). Only the active one is editable.
    if obj.status == "superseded":
        messages.error(request, "A superseded salary assignment is read-only history and cannot be edited.")
        return redirect("hrm:employeesalarystructure_detail", pk=obj.pk)
    return crud_edit(request, model=EmployeeSalaryStructure, pk=pk, form_class=EmployeeSalaryStructureForm,
                     template="hrm/salary/employeesalarystructure/form.html",
                     success_url="hrm:employeesalarystructure_list")


@login_required
@require_POST
def employeesalarystructure_delete(request, pk):
    obj = get_object_or_404(EmployeeSalaryStructure, pk=pk, tenant=request.tenant)
    if obj.status == "superseded":
        messages.error(request, "A superseded salary assignment is read-only history and cannot be deleted.")
        return redirect("hrm:employeesalarystructure_detail", pk=obj.pk)
    return crud_delete(request, model=EmployeeSalaryStructure, pk=pk,
                       success_url="hrm:employeesalarystructure_list")


# ============================================================ Payroll Cycles (3.14)
@login_required
def payrollcycle_list(request):
    return crud_list(
        request,
        PayrollCycle.objects.filter(tenant=request.tenant),
        "hrm/payroll/payrollcycle/list.html",
        search_fields=["number", "notes"],
        filters=[("status", "status", False), ("cycle_type", "cycle_type", False)],
        extra_context={
            "status_choices": PayrollCycle.STATUS_CHOICES,
            "cycle_type_choices": PayrollCycle.CYCLE_TYPE_CHOICES,
        },
    )


@login_required
def payrollcycle_create(request):
    return crud_create(request, form_class=PayrollCycleForm,
                       template="hrm/payroll/payrollcycle/form.html", success_url="hrm:payrollcycle_list")


@login_required
def payrollcycle_detail(request, pk):
    obj = get_object_or_404(
        PayrollCycle.objects.select_related("accounting_payroll_run", "submitted_by", "approved_by"),
        pk=pk, tenant=request.tenant)
    payslips = obj.payslips.select_related("employee__party").order_by("employee__party__name")
    return render(request, "hrm/payroll/payrollcycle/detail.html", {
        "obj": obj,
        "payslips": payslips,
        # one aggregate query for the three totals shown on the summary panel
        "totals": obj.payslips.aggregate(g=Sum("gross_pay"), d=Sum("total_deductions"), n=Sum("net_pay")),
    })


@login_required
def payrollcycle_edit(request, pk):
    obj = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    # Only a draft cycle's header is editable; once submitted/approved/locked it's read-only.
    if obj.status != "draft":
        messages.error(request, "Only a draft payroll cycle can be edited.")
        return redirect("hrm:payrollcycle_detail", pk=obj.pk)
    return crud_edit(request, model=PayrollCycle, pk=pk, form_class=PayrollCycleForm,
                     template="hrm/payroll/payrollcycle/form.html", success_url="hrm:payrollcycle_list")


@login_required
@require_POST
def payrollcycle_delete(request, pk):
    obj = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, "A locked payroll cycle cannot be deleted.")
        return redirect("hrm:payrollcycle_detail", pk=obj.pk)
    return crud_delete(request, model=PayrollCycle, pk=pk, success_url="hrm:payrollcycle_list")


@login_required
@require_POST
def payrollcycle_generate(request, pk):
    """(Re)generate payslips for every employee with an active salary structure — draft cycles only."""
    cycle = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if cycle.status != "draft":
        messages.error(request, "Payslips can only be (re)generated while the cycle is a draft.")
        return redirect("hrm:payrollcycle_detail", pk=cycle.pk)
    days_in = ((cycle.period_end - cycle.period_start).days + 1
               if cycle.period_end and cycle.period_start else 30)
    with transaction.atomic():
        # Preserve HR manual inputs (arrears/bonus/hold/days/lop) across a re-generate, keyed by employee.
        preserved = {p.employee_id: p for p in cycle.payslips.all()}
        cycle.payslips.all().delete()  # safe re-run while draft (cascades the lines)
        structures = (EmployeeSalaryStructure.objects
                      .filter(tenant=request.tenant, status="active", effective_from__lte=cycle.period_end)
                      .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=cycle.period_start))
                      .select_related("employee__party", "template"))
        count = 0
        for structure in structures:
            prev = preserved.get(structure.employee_id)
            payslip = Payslip.objects.create(
                tenant=request.tenant, cycle=cycle, employee=structure.employee,
                salary_structure=structure, days_in_period=days_in,
                days_worked=min(prev.days_worked, days_in) if prev else days_in,
                lop_days=prev.lop_days if prev else Decimal("0"),
                arrears_amount=prev.arrears_amount if prev else Decimal("0"),
                bonus_amount=prev.bonus_amount if prev else Decimal("0"),
                on_hold=prev.on_hold if prev else False,
                hold_reason=prev.hold_reason if prev else "")
            payslip.recompute()
            count += 1
    write_audit_log(request.user, cycle, "update", {"action": "generate", "headcount": count})
    messages.success(request, f"Generated {count} payslip(s) for {cycle.number}.")
    return redirect("hrm:payrollcycle_detail", pk=cycle.pk)


@login_required
@require_POST
def payrollcycle_submit(request, pk):
    cycle = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if cycle.status == "draft":
        if not cycle.payslips.exists():
            messages.error(request, "Generate payslips before submitting the cycle.")
            return redirect("hrm:payrollcycle_detail", pk=cycle.pk)
        # Off-cycle / bonus runs skip the approval step and go straight to approved (Gusto convention);
        # locking is always a separate explicit action, never implicit.
        cycle.status = "approved" if cycle.cycle_type != "regular" else "pending_approval"
        cycle.submitted_by = request.user
        cycle.submitted_at = timezone.now()
        cycle.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
        write_audit_log(request.user, cycle, "update", {"action": "submit", "to": cycle.status})
        messages.success(request, f"Cycle {cycle.number} submitted ({cycle.get_status_display()}).")
    return redirect("hrm:payrollcycle_detail", pk=cycle.pk)


@tenant_admin_required  # approving payroll is a privileged finance/admin action
@require_POST
def payrollcycle_approve(request, pk):
    cycle = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if cycle.status == "pending_approval":
        cycle.status = "approved"
        cycle.approved_by = request.user
        cycle.approved_at = timezone.now()
        cycle.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        write_audit_log(request.user, cycle, "update", {"action": "approve"})
        messages.success(request, f"Cycle {cycle.number} approved.")
    return redirect("hrm:payrollcycle_detail", pk=cycle.pk)


@tenant_admin_required
@require_POST
def payrollcycle_reject(request, pk):
    cycle = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if cycle.status == "pending_approval":
        cycle.status = "rejected"
        cycle.approved_by = request.user
        cycle.rejection_reason = request.POST.get("rejection_reason", "").strip()[:2000]
        cycle.save(update_fields=["status", "approved_by", "rejection_reason", "updated_at"])
        write_audit_log(request.user, cycle, "update", {"action": "reject"})
        messages.success(request, f"Cycle {cycle.number} rejected.")
    return redirect("hrm:payrollcycle_detail", pk=cycle.pk)


@tenant_admin_required
@require_POST
def payrollcycle_lock(request, pk):
    """Lock an approved cycle and hand the rolled-up totals to accounting: create an
    ``accounting.PayrollRun`` (draft) for the GL. HRM NEVER builds a JournalEntry (L29) — accounting's
    own ``payroll_run_post`` posts the balanced entry from that row."""
    cycle = get_object_or_404(PayrollCycle, pk=pk, tenant=request.tenant)
    if cycle.status != "approved":
        messages.error(request, "Only an approved cycle can be locked.")
        return redirect("hrm:payrollcycle_detail", pk=cycle.pk)
    # Lazy import keeps accounting a runtime (not module-load) dependency.
    from apps.accounting.models import PayrollRun as AccountingPayrollRun
    lines = PayslipLine.objects.filter(payslip__cycle=cycle)

    def _sum(qs):
        return qs.aggregate(s=Sum("amount"))["s"] or Decimal("0")

    gross = cycle.payslips.aggregate(s=Sum("gross_pay"))["s"] or Decimal("0")
    statutory = lines.filter(component_type="statutory_deduction")
    # Mirror recompute()'s bucketing exactly — only employer-side is excluded from net; employee/both/
    # blank all reduce net — so the accounting run's derived net_pay reconciles with Σ payslip.net_pay.
    employee_tax = _sum(statutory.exclude(contribution_side="employer"))
    employer_tax = _sum(statutory.filter(contribution_side="employer"))
    deductions = _sum(lines.filter(component_type="voluntary_deduction").exclude(contribution_side="employer"))
    with transaction.atomic():
        run = AccountingPayrollRun.objects.create(
            tenant=request.tenant, period_start=cycle.period_start, period_end=cycle.period_end,
            pay_date=cycle.pay_date, headcount=cycle.payslips.count(),
            gross_wages=gross, employee_tax=employee_tax, employer_tax=employer_tax,
            benefits=Decimal("0"), deductions=deductions)
        cycle.accounting_payroll_run = run
        cycle.status = "locked"
        cycle.save(update_fields=["accounting_payroll_run", "status", "updated_at"])
    write_audit_log(request.user, cycle, "update",
                    {"action": "lock", "accounting_payroll_run": run.number})
    messages.success(request, f"Cycle {cycle.number} locked — created accounting run {run.number}. "
                              f"Post it from Accounting → Payroll to generate the GL entry.")
    return redirect("hrm:payrollcycle_detail", pk=cycle.pk)


# ------------------------------------------------------------ Payslips (3.14)
@login_required
def payslip_list(request):
    qs = Payslip.objects.filter(tenant=request.tenant).select_related("employee__party", "cycle")
    on_hold = request.GET.get("on_hold", "").strip()
    if on_hold in ("True", "False"):
        qs = qs.filter(on_hold=(on_hold == "True"))
    return crud_list(
        request, qs, "hrm/payroll/payslip/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("cycle", "cycle_id", True)],
        extra_context={"cycles": PayrollCycle.objects.filter(tenant=request.tenant)},
    )


@login_required
def payslip_detail(request, pk):
    obj = get_object_or_404(
        Payslip.objects.select_related("employee__party", "cycle", "salary_structure"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/payroll/payslip/detail.html", {"obj": obj, "lines": obj.lines.all()})


@login_required
def payslip_edit(request, pk):
    # select_related the structure+template too so the recompute() after save() doesn't re-fetch them.
    obj = get_object_or_404(
        Payslip.objects.select_related("cycle", "salary_structure__template"), pk=pk, tenant=request.tenant)
    # Payslip inputs are editable only while the cycle is a draft; recompute after every change.
    if obj.cycle.status != "draft":
        messages.error(request, "A payslip can only be edited while its cycle is a draft.")
        return redirect("hrm:payslip_detail", pk=obj.pk)
    if request.method == "POST":
        form = PayslipForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            obj.recompute()
            write_audit_log(request.user, obj, "update", {"action": "edit"})
            messages.success(request, "Payslip updated.")
            return redirect("hrm:payslip_detail", pk=obj.pk)
    else:
        form = PayslipForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/payroll/payslip/form.html", {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required  # holding an employee's pay is a privileged action
@require_POST
def payslip_hold(request, pk):
    obj = get_object_or_404(Payslip.objects.select_related("cycle"), pk=pk, tenant=request.tenant)
    if obj.cycle.is_locked:
        messages.error(request, "A locked cycle's payslips cannot be held.")
        return redirect("hrm:payslip_detail", pk=obj.pk)
    obj.on_hold = True
    obj.hold_reason = request.POST.get("hold_reason", "").strip()[:2000]
    obj.save(update_fields=["on_hold", "hold_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "hold"})
    messages.success(request, "Payslip put on hold.")
    return redirect("hrm:payslip_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def payslip_release(request, pk):
    obj = get_object_or_404(Payslip.objects.select_related("cycle"), pk=pk, tenant=request.tenant)
    if obj.cycle.is_locked:
        messages.error(request, "A locked cycle's payslips cannot be modified.")
        return redirect("hrm:payslip_detail", pk=obj.pk)
    obj.on_hold = False
    obj.released_at = timezone.now()
    obj.save(update_fields=["on_hold", "released_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "release"})
    messages.success(request, "Payslip hold released.")
    return redirect("hrm:payslip_detail", pk=obj.pk)


# ======================= 3.15 Statutory Compliance =======================
# Config singleton (detail + edit only) · state-wise PT/LWF rules · per-employee
# identifiers · the shared StatutoryReturn register with its aggregation engine
# (statutoryreturn_generate) + filing/payment workflow + compliance calendar.

# ---------------------------------------------- StatutoryConfig (tenant singleton)
@login_required
def statutoryconfig_detail(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace to view statutory configuration.")
        return redirect("dashboard:home")
    config = StatutoryConfig.for_tenant(request.tenant)
    return render(request, "hrm/statutory/statutoryconfig/detail.html", {"obj": config})


@tenant_admin_required  # editing PF/ESI codes, TAN, PAN and rates is privileged org-wide config
def statutoryconfig_edit(request):
    # Dedicated get-or-create-then-edit view: crud_edit takes a pk, but this model is a per-tenant
    # settings singleton reached without one — so the row is resolved via for_tenant() here.
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace to edit statutory configuration.")
        return redirect("dashboard:home")
    config = StatutoryConfig.for_tenant(request.tenant)
    if request.method == "POST":
        form = StatutoryConfigForm(request.POST, instance=config, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, config, "update", {"action": "edit_config"})
            messages.success(request, "Statutory configuration updated.")
            return redirect("hrm:statutoryconfig_detail")
    else:
        form = StatutoryConfigForm(instance=config, tenant=request.tenant)
    return render(request, "hrm/statutory/statutoryconfig/form.html",
                  {"form": form, "obj": config, "is_edit": True})


# ---------------------------------------------- StatutoryStateRule (PT + LWF slabs)
@login_required
def statutorystaterule_list(request):
    return crud_list(
        request,
        StatutoryStateRule.objects.filter(tenant=request.tenant),
        "hrm/statutory/statutorystaterule/list.html",
        search_fields=["state", "registration_number"],
        filters=[("scheme", "scheme", False), ("state", "state", False),
                 ("is_active", "is_active", False)],
        extra_context={
            "scheme_choices": StatutoryStateRule.SCHEME_CHOICES,
            "state_choices": INDIAN_STATE_CHOICES,
        },
    )


@login_required
def statutorystaterule_create(request):
    return crud_create(request, form_class=StatutoryStateRuleForm,
                       template="hrm/statutory/statutorystaterule/form.html",
                       success_url="hrm:statutorystaterule_list")


@login_required
def statutorystaterule_detail(request, pk):
    return crud_detail(request, model=StatutoryStateRule, pk=pk,
                       template="hrm/statutory/statutorystaterule/detail.html")


@login_required
def statutorystaterule_edit(request, pk):
    return crud_edit(request, model=StatutoryStateRule, pk=pk, form_class=StatutoryStateRuleForm,
                     template="hrm/statutory/statutorystaterule/form.html",
                     success_url="hrm:statutorystaterule_list")


@login_required
@require_POST
def statutorystaterule_delete(request, pk):
    return crud_delete(request, model=StatutoryStateRule, pk=pk,
                       success_url="hrm:statutorystaterule_list")


# ---------------------------------------- EmployeeStatutoryIdentifier (UAN/PF/ESI)
@login_required
def employeestatutoryidentifier_list(request):
    return crud_list(
        request,
        EmployeeStatutoryIdentifier.objects.filter(tenant=request.tenant).select_related("employee__party"),
        "hrm/statutory/employeestatutoryidentifier/list.html",
        search_fields=["employee__party__name", "uan_number", "pf_number", "esi_number"],
        filters=[("pt_state", "pt_state", False), ("is_pf_applicable", "is_pf_applicable", False),
                 ("is_esi_applicable", "is_esi_applicable", False)],
        extra_context={"state_choices": INDIAN_STATE_CHOICES},
    )


@login_required
def employeestatutoryidentifier_create(request):
    return crud_create(request, form_class=EmployeeStatutoryIdentifierForm,
                       template="hrm/statutory/employeestatutoryidentifier/form.html",
                       success_url="hrm:employeestatutoryidentifier_list")


@login_required
def employeestatutoryidentifier_detail(request, pk):
    return crud_detail(request, model=EmployeeStatutoryIdentifier, pk=pk,
                       template="hrm/statutory/employeestatutoryidentifier/detail.html",
                       select_related=("employee__party",))


@login_required
def employeestatutoryidentifier_edit(request, pk):
    return crud_edit(request, model=EmployeeStatutoryIdentifier, pk=pk,
                     form_class=EmployeeStatutoryIdentifierForm,
                     template="hrm/statutory/employeestatutoryidentifier/form.html",
                     success_url="hrm:employeestatutoryidentifier_list")


@login_required
@require_POST
def employeestatutoryidentifier_delete(request, pk):
    return crud_delete(request, model=EmployeeStatutoryIdentifier, pk=pk,
                       success_url="hrm:employeestatutoryidentifier_list")


# ------------------------------------------------- StatutoryReturn (register/challan)
@login_required
def statutoryreturn_list(request):
    # No select_related — the list template renders only scalar fields (scheme/period/totals/status/
    # due_date), never obj.cycle or obj.employee, so joining them would be dead over-fetch.
    qs = StatutoryReturn.objects.filter(tenant=request.tenant)
    return crud_list(
        request, qs, "hrm/statutory/statutoryreturn/list.html",
        search_fields=["number", "registration_number_used", "notes"],
        filters=[("scheme", "scheme", False), ("status", "status", False),
                 ("period_type", "period_type", False)],
        extra_context={
            "scheme_choices": StatutoryReturn.SCHEME_CHOICES,
            "status_choices": StatutoryReturn.STATUS_CHOICES,
            "period_type_choices": StatutoryReturn.PERIOD_TYPE_CHOICES,
        },
    )


@login_required
def statutoryreturn_create(request):
    return crud_create(request, form_class=StatutoryReturnForm,
                       template="hrm/statutory/statutoryreturn/form.html",
                       success_url="hrm:statutoryreturn_list")


@login_required
def statutoryreturn_detail(request, pk):
    return crud_detail(request, model=StatutoryReturn, pk=pk,
                       template="hrm/statutory/statutoryreturn/detail.html",
                       select_related=("cycle", "employee__party"))


@login_required
def statutoryreturn_edit(request, pk):
    obj = get_object_or_404(StatutoryReturn, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, "Only a pending return can be edited.")
        return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
    return crud_edit(request, model=StatutoryReturn, pk=pk, form_class=StatutoryReturnForm,
                     template="hrm/statutory/statutoryreturn/form.html",
                     success_url="hrm:statutoryreturn_list")


@login_required
@require_POST
def statutoryreturn_delete(request, pk):
    obj = get_object_or_404(StatutoryReturn, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, "Only a pending return can be deleted.")
        return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
    return crud_delete(request, model=StatutoryReturn, pk=pk, success_url="hrm:statutoryreturn_list")


@tenant_admin_required  # aggregating/filing statutory returns is a privileged finance action
@require_POST
def statutoryreturn_generate(request, pk):
    """(Re)aggregate the return's contribution totals from the period's PayslipLine rows — the key
    domain action (mirrors payrollcycle_generate: create the metadata, then generate from payroll).
    Only a pending return can be re-aggregated; the model's recompute() does the roll-up."""
    obj = get_object_or_404(StatutoryReturn, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, "Only a pending return can be (re)aggregated.")
        return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
    obj.recompute()
    write_audit_log(request.user, obj, "update", {
        "action": "generate", "headcount": obj.headcount,
        "employee_total": str(obj.employee_contribution_total),
        "employer_total": str(obj.employer_contribution_total)})
    messages.success(request,
        f"Aggregated {obj.get_scheme_display()} return {obj.number}: employee "
        f"{obj.employee_contribution_total}, employer {obj.employer_contribution_total}, "
        f"headcount {obj.headcount}.")
    return redirect("hrm:statutoryreturn_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def statutoryreturn_mark_filed(request, pk):
    obj = get_object_or_404(StatutoryReturn, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending return can be marked filed.")
        return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
    obj.status = "filed"
    obj.filed_on = timezone.localdate()
    obj.save(update_fields=["status", "filed_on", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "mark_filed"})
    messages.success(request, f"Return {obj.number} marked filed.")
    return redirect("hrm:statutoryreturn_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def statutoryreturn_mark_paid(request, pk):
    obj = get_object_or_404(StatutoryReturn, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "filed"):
        messages.error(request, "Only a pending or filed return can be marked paid.")
        return redirect("hrm:statutoryreturn_detail", pk=obj.pk)
    obj.paid_on = timezone.localdate()
    obj.payment_reference = request.POST.get("payment_reference", "").strip()[:100]
    # Paid after the due date → recorded as Late, not Paid (RazorpayX/saral PayPack convention).
    obj.status = "late" if (obj.due_date and obj.paid_on > obj.due_date) else "paid"
    obj.save(update_fields=["status", "paid_on", "payment_reference", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "mark_paid", "status": obj.status})
    messages.success(request, f"Return {obj.number} marked {obj.get_status_display()}.")
    return redirect("hrm:statutoryreturn_detail", pk=obj.pk)


# --------------------------------------------------- Compliance calendar (cross-cutting)
@login_required
def statutory_compliance_calendar(request):
    """Read-only cross-scheme due-date calendar over StatutoryReturn (no new model). Groups returns
    into Overdue / Pending / Filed / Settled buckets; supports the same scheme/status GET filters as
    the return list. Grouped (not paginated) since it's a calendar overview."""
    # No select_related — the calendar rows render only scalar fields, never cycle/employee.
    qs = StatutoryReturn.objects.filter(tenant=request.tenant).order_by("due_date", "scheme")
    scheme = request.GET.get("scheme", "").strip()
    if scheme:
        qs = qs.filter(scheme=scheme)
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)
    buckets = {"overdue": [], "pending": [], "filed": [], "settled": []}
    for r in qs:
        if r.is_overdue:
            buckets["overdue"].append(r)
        elif r.status == "pending":
            buckets["pending"].append(r)
        elif r.status == "filed":
            buckets["filed"].append(r)
        else:  # paid / late — settled (a "late" row is paid-but-late, flagged in the template)
            buckets["settled"].append(r)
    # An ordered list of buckets so the template iterates directly (no custom dict-lookup filter).
    bucket_list = [
        {"label": "Overdue", "icon": "alarm-clock", "tone": "red", "rows": buckets["overdue"]},
        {"label": "Pending", "icon": "hourglass", "tone": "amber", "rows": buckets["pending"]},
        {"label": "Filed", "icon": "file-check", "tone": "info", "rows": buckets["filed"]},
        {"label": "Settled", "icon": "check-circle", "tone": "green", "rows": buckets["settled"]},
    ]
    return render(request, "hrm/statutory/compliance_calendar.html", {
        "bucket_list": bucket_list,
        "scheme_choices": StatutoryReturn.SCHEME_CHOICES,
        "status_choices": StatutoryReturn.STATUS_CHOICES,
    })


# ========================= 3.16 Tax & Investment =========================
# TaxRegimeConfig (+ inline TaxSlabBand) · regime comparison · InvestmentDeclaration
# (+ inline lines) · InvestmentProof upload/verify · TaxComputation (recompute engine
# + Form 16 tie-in) · form16_partb report.

# --------------------------------------------------- TaxRegimeConfig (+ inline slab bands)
@login_required
def taxregimeconfig_list(request):
    return crud_list(
        request, TaxRegimeConfig.objects.filter(tenant=request.tenant),
        "hrm/tax/taxregimeconfig/list.html",
        search_fields=["financial_year", "tax_law_reference"],
        filters=[("financial_year", "financial_year", False), ("regime", "regime", False)],
        extra_context={"regime_choices": TaxRegimeConfig.REGIME_CHOICES},
    )


@login_required
def taxregimeconfig_create(request):
    return crud_create(request, form_class=TaxRegimeConfigForm,
                       template="hrm/tax/taxregimeconfig/form.html", success_url="hrm:taxregimeconfig_list")


@login_required
def taxregimeconfig_detail(request, pk):
    obj = get_object_or_404(TaxRegimeConfig, pk=pk, tenant=request.tenant)
    return render(request, "hrm/tax/taxregimeconfig/detail.html", {
        "obj": obj,
        "slab_bands": obj.slab_bands.order_by("sequence", "income_from"),
        "band_form": TaxSlabBandForm(tenant=request.tenant),
    })


@login_required
def taxregimeconfig_edit(request, pk):
    return crud_edit(request, model=TaxRegimeConfig, pk=pk, form_class=TaxRegimeConfigForm,
                     template="hrm/tax/taxregimeconfig/form.html", success_url="hrm:taxregimeconfig_list")


@login_required
@require_POST
def taxregimeconfig_delete(request, pk):
    return crud_delete(request, model=TaxRegimeConfig, pk=pk, success_url="hrm:taxregimeconfig_list")


@login_required
@require_POST
def taxslabband_create(request, config_pk):
    config = get_object_or_404(TaxRegimeConfig, pk=config_pk, tenant=request.tenant)
    form = TaxSlabBandForm(request.POST,
                           instance=TaxSlabBand(tenant=request.tenant, config=config),
                           tenant=request.tenant)
    if form.is_valid():
        form.save()
        write_audit_log(request.user, config, "update", {"action": "slab_add"})
        messages.success(request, "Slab band added.")
    else:
        messages.error(request, "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    return redirect("hrm:taxregimeconfig_detail", pk=config.pk)


@login_required
def taxslabband_edit(request, config_pk, pk):
    config = get_object_or_404(TaxRegimeConfig, pk=config_pk, tenant=request.tenant)
    band = get_object_or_404(TaxSlabBand, pk=pk, tenant=request.tenant, config=config)
    if request.method == "POST":
        form = TaxSlabBandForm(request.POST, instance=band, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, config, "update", {"action": "slab_edit"})
            messages.success(request, "Slab band updated.")
            return redirect("hrm:taxregimeconfig_detail", pk=config.pk)
    else:
        form = TaxSlabBandForm(instance=band, tenant=request.tenant)
    return render(request, "hrm/tax/taxregimeconfig/band_form.html",
                  {"form": form, "obj": band, "config": config, "is_edit": True})


@login_required
@require_POST
def taxslabband_delete(request, config_pk, pk):
    config = get_object_or_404(TaxRegimeConfig, pk=config_pk, tenant=request.tenant)
    band = get_object_or_404(TaxSlabBand, pk=pk, tenant=request.tenant, config=config)
    band.delete()
    write_audit_log(request.user, config, "update", {"action": "slab_delete"})
    messages.success(request, "Slab band removed.")
    return redirect("hrm:taxregimeconfig_detail", pk=config.pk)


def _computation_breakdown(obj):
    """The derived tax breakdown for a TaxComputation, computed once (each property fires queries)."""
    return {
        "gross": obj.gross_annual_income,
        "hra_exemption": obj.hra_exemption,
        "chapter_via": obj.total_chapter_via_deductions,
        "capped_sections": obj.capped_sections,
        "taxable_old": obj.taxable_income_old,
        "taxable_new": obj.taxable_income_new,
        "tax_old": obj.tax_old_regime,
        "tax_new": obj.tax_new_regime,
        "cheaper": obj.cheaper_regime,
        "savings": abs(obj.tax_old_regime - obj.tax_new_regime),
    }


@login_required
def tax_regime_comparison(request):
    """Read-only old-vs-new comparison for a chosen TaxComputation (no new model)."""
    comp = None
    comp_id = request.GET.get("computation", "").strip()
    if comp_id.isdigit():
        comp = (TaxComputation.objects.filter(tenant=request.tenant, pk=comp_id)
                .select_related("employee__party", "declaration").first())
    ctx = {
        "comp": comp,
        "computations": (TaxComputation.objects.filter(tenant=request.tenant)
                         .select_related("employee__party").order_by("-financial_year")),
    }
    if comp is not None:
        ctx["breakdown"] = _computation_breakdown(comp)
    return render(request, "hrm/tax/regime_comparison.html", ctx)


# --------------------------------------------- InvestmentDeclaration (+ inline lines)
@login_required
def investmentdeclaration_list(request):
    return crud_list(
        request,
        InvestmentDeclaration.objects.filter(tenant=request.tenant).select_related("employee__party"),
        "hrm/tax/investmentdeclaration/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("financial_year", "financial_year", False), ("regime_elected", "regime_elected", False),
                 ("status", "status", False), ("employee", "employee_id", True)],
        extra_context={
            "status_choices": InvestmentDeclaration.STATUS_CHOICES,
            "regime_choices": InvestmentDeclaration.REGIME_CHOICES,
            "employees": EmployeeProfile.objects.filter(tenant=request.tenant).select_related("party"),
        },
    )


@login_required
def investmentdeclaration_create(request):
    return crud_create(request, form_class=InvestmentDeclarationForm,
                       template="hrm/tax/investmentdeclaration/form.html",
                       success_url="hrm:investmentdeclaration_list")


@login_required
def investmentdeclaration_detail(request, pk):
    obj = get_object_or_404(
        InvestmentDeclaration.objects.select_related("employee__party"), pk=pk, tenant=request.tenant)
    lines = obj.lines.order_by("section_code")
    # Flat proofs list (across all lines) so the proofs table can use a single {% empty %} — a nested
    # loop can't tell "no lines" from "lines but no proofs".
    proofs = (InvestmentProof.objects.filter(declaration_line__declaration=obj)
              .select_related("declaration_line")
              .order_by("declaration_line__section_code", "-created_at"))
    return render(request, "hrm/tax/investmentdeclaration/detail.html", {
        "obj": obj,
        "lines": lines,
        "proofs": proofs,
        "line_form": InvestmentDeclarationLineForm(tenant=request.tenant),
    })


@login_required
def investmentdeclaration_edit(request, pk):
    obj = get_object_or_404(InvestmentDeclaration, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft declaration can be edited.")
        return redirect("hrm:investmentdeclaration_detail", pk=obj.pk)
    return crud_edit(request, model=InvestmentDeclaration, pk=pk, form_class=InvestmentDeclarationForm,
                     template="hrm/tax/investmentdeclaration/form.html",
                     success_url="hrm:investmentdeclaration_list")


@login_required
@require_POST
def investmentdeclaration_delete(request, pk):
    obj = get_object_or_404(InvestmentDeclaration, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft declaration can be deleted.")
        return redirect("hrm:investmentdeclaration_detail", pk=obj.pk)
    # TaxComputation.declaration is PROTECT — pre-check for a friendly message (mirrors paycomponent_delete).
    if obj.tax_computations.exists():
        messages.error(request, "This declaration has a linked tax computation and cannot be deleted.")
        return redirect("hrm:investmentdeclaration_detail", pk=obj.pk)
    return crud_delete(request, model=InvestmentDeclaration, pk=pk,
                       success_url="hrm:investmentdeclaration_list")


@login_required
@require_POST
def investmentdeclaration_submit(request, pk):
    obj = get_object_or_404(InvestmentDeclaration, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "submitted"
        obj.submitted_at = timezone.now()
        obj.save(update_fields=["status", "submitted_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Declaration {obj.number} submitted.")
    return redirect("hrm:investmentdeclaration_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def investmentdeclaration_lock(request, pk):
    obj = get_object_or_404(InvestmentDeclaration, pk=pk, tenant=request.tenant)
    if obj.status == "submitted":
        obj.status = "locked"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "lock"})
        messages.success(request, f"Declaration {obj.number} locked.")
    return redirect("hrm:investmentdeclaration_detail", pk=obj.pk)


@login_required
@require_POST
def investmentdeclarationline_create(request, declaration_pk):
    declaration = get_object_or_404(InvestmentDeclaration, pk=declaration_pk, tenant=request.tenant)
    if not declaration.is_editable:
        messages.error(request, "Lines can only be added while the declaration is a draft.")
        return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    form = InvestmentDeclarationLineForm(
        request.POST,
        instance=InvestmentDeclarationLine(tenant=request.tenant, declaration=declaration),
        tenant=request.tenant)
    if form.is_valid():
        try:
            # Savepoint so a duplicate-section IntegrityError rolls back only this insert instead of
            # poisoning the whole request transaction (which would 500/400 the end-of-request commit).
            with transaction.atomic():
                form.save()
            write_audit_log(request.user, declaration, "update", {"action": "line_add"})
            messages.success(request, "Declaration line added.")
        except IntegrityError:
            messages.error(request, "A line for that section already exists on this declaration.")
    else:
        messages.error(request, "; ".join(f"{k}: {v[0]}" for k, v in form.errors.items()))
    return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)


@login_required
def investmentdeclarationline_edit(request, declaration_pk, pk):
    declaration = get_object_or_404(InvestmentDeclaration, pk=declaration_pk, tenant=request.tenant)
    line = get_object_or_404(InvestmentDeclarationLine, pk=pk, tenant=request.tenant, declaration=declaration)
    if not declaration.is_editable:
        messages.error(request, "Lines can only be edited while the declaration is a draft.")
        return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    if request.method == "POST":
        form = InvestmentDeclarationLineForm(request.POST, instance=line, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, declaration, "update", {"action": "line_edit"})
            messages.success(request, "Declaration line updated.")
            return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    else:
        form = InvestmentDeclarationLineForm(instance=line, tenant=request.tenant)
    return render(request, "hrm/tax/investmentdeclaration/line_form.html",
                  {"form": form, "obj": line, "declaration": declaration, "is_edit": True})


@login_required
@require_POST
def investmentdeclarationline_delete(request, declaration_pk, pk):
    declaration = get_object_or_404(InvestmentDeclaration, pk=declaration_pk, tenant=request.tenant)
    line = get_object_or_404(InvestmentDeclarationLine, pk=pk, tenant=request.tenant, declaration=declaration)
    if not declaration.is_editable:
        messages.error(request, "Lines can only be removed while the declaration is a draft.")
        return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    line.delete()
    write_audit_log(request.user, declaration, "update", {"action": "line_delete"})
    messages.success(request, "Declaration line removed.")
    return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)


# ------------------------------------------------------ InvestmentProof (upload + verify)
def _proof_window_open(declaration):
    """True when the declaration's proof window is currently open (proofs upload even after the
    declaration itself is locked — the proof window is deliberately later than the declaration one)."""
    today = timezone.localdate()
    if declaration.proof_window_open and today < declaration.proof_window_open:
        return False
    if declaration.proof_window_close and today > declaration.proof_window_close:
        return False
    return True


@login_required
def investmentproof_upload(request, line_pk):
    line = get_object_or_404(
        InvestmentDeclarationLine.objects.select_related("declaration"), pk=line_pk, tenant=request.tenant)
    declaration = line.declaration
    # Gate on the PROOF window (not is_editable) — proofs are typically uploaded after the declaration
    # is locked. If no window is configured, allow (draft/open by default).
    if not _proof_window_open(declaration):
        messages.error(request, "The proof-submission window for this declaration is not open.")
        return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    if request.method == "POST":
        form = InvestmentProofForm(
            request.POST, request.FILES,
            instance=InvestmentProof(tenant=request.tenant, declaration_line=line),
            tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, declaration, "update", {"action": "proof_upload"})
            messages.success(request, "Proof uploaded.")
            return redirect("hrm:investmentdeclaration_detail", pk=declaration.pk)
    else:
        form = InvestmentProofForm(tenant=request.tenant)
    return render(request, "hrm/tax/investmentproof/form.html",
                  {"form": form, "line": line, "declaration": declaration})


@login_required
def investmentproof_list(request):
    return crud_list(
        request,
        InvestmentProof.objects.filter(tenant=request.tenant)
        .select_related("declaration_line__declaration__employee__party"),
        "hrm/tax/investmentproof/list.html",
        search_fields=["title"],
        filters=[("verification_status", "verification_status", False)],
        extra_context={"verification_status_choices": InvestmentProof.VERIFICATION_STATUS_CHOICES},
    )


@login_required
def investmentproof_detail(request, pk):
    obj = get_object_or_404(
        InvestmentProof.objects.select_related(
            "declaration_line__declaration__employee__party", "verified_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/tax/investmentproof/detail.html", {"obj": obj})


def _set_proof_status(request, pk, status, *, reason=""):
    obj = get_object_or_404(
        InvestmentProof.objects.select_related("declaration_line"), pk=pk, tenant=request.tenant)
    # Only a pending/on-hold proof can be (re)decided — a verified/rejected proof is terminal and is not
    # re-transitioned via a stray POST (matches the template, which only exposes the buttons then).
    if obj.verification_status not in ("pending", "on_hold"):
        messages.error(request, "This proof has already been decided.")
        return obj, False
    obj.verification_status = status
    obj.verified_by = request.user
    obj.verified_at = timezone.now()
    obj.rejection_reason = reason
    obj.save(update_fields=["verification_status", "verified_by", "verified_at",
                            "rejection_reason", "updated_at"])
    # Roll the parent line's verified_amount up from its verified proofs.
    obj.declaration_line.recompute_verified()
    write_audit_log(request.user, obj, "update", {"action": f"proof_{status}"})
    return obj, True


@tenant_admin_required
@require_POST
def investmentproof_verify(request, pk):
    obj, changed = _set_proof_status(request, pk, "verified")
    if changed:
        messages.success(request, "Proof verified.")
    return redirect("hrm:investmentproof_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def investmentproof_reject(request, pk):
    obj, changed = _set_proof_status(request, pk, "rejected",
                                     reason=request.POST.get("rejection_reason", "").strip()[:2000])
    if changed:
        messages.success(request, "Proof rejected.")
    return redirect("hrm:investmentproof_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def investmentproof_on_hold(request, pk):
    obj, changed = _set_proof_status(request, pk, "on_hold",
                                     reason=request.POST.get("rejection_reason", "").strip()[:2000])
    if changed:
        messages.success(request, "Proof put on hold.")
    return redirect("hrm:investmentproof_detail", pk=obj.pk)


# ---------------------------------------------- TaxComputation (engine + Form 16 tie-in)
@login_required
def taxcomputation_list(request):
    return crud_list(
        request,
        # No declaration join — the list template renders only scalar fields + employee.party.name;
        # declaration is loaded on the detail/form16_partb views where it's actually shown.
        TaxComputation.objects.filter(tenant=request.tenant).select_related("employee__party"),
        "hrm/tax/taxcomputation/list.html",
        search_fields=["number", "employee__party__name"],
        filters=[("financial_year", "financial_year", False),
                 ("computation_type", "computation_type", False), ("employee", "employee_id", True)],
        extra_context={
            "computation_type_choices": TaxComputation.COMPUTATION_TYPE_CHOICES,
            "employees": EmployeeProfile.objects.filter(tenant=request.tenant).select_related("party"),
        },
    )


@login_required
def taxcomputation_create(request):
    return crud_create(request, form_class=TaxComputationForm,
                       template="hrm/tax/taxcomputation/form.html", success_url="hrm:taxcomputation_list")


@login_required
def taxcomputation_detail(request, pk):
    obj = get_object_or_404(
        TaxComputation.objects.select_related("employee__party", "declaration", "statutory_return"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/tax/taxcomputation/detail.html", {
        "obj": obj,
        "breakdown": _computation_breakdown(obj),
        "lines": obj.declaration.lines.all(),
    })


@login_required
def taxcomputation_edit(request, pk):
    return crud_edit(request, model=TaxComputation, pk=pk, form_class=TaxComputationForm,
                     template="hrm/tax/taxcomputation/form.html", success_url="hrm:taxcomputation_list")


@login_required
@require_POST
def taxcomputation_delete(request, pk):
    return crud_delete(request, model=TaxComputation, pk=pk, success_url="hrm:taxcomputation_list")


@tenant_admin_required
@require_POST
def taxcomputation_generate(request, pk):
    """(Re)run the tax engine — mirrors statutoryreturn_generate's idempotent re-aggregate pattern."""
    obj = get_object_or_404(TaxComputation, pk=pk, tenant=request.tenant)
    try:
        obj.recompute()
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("hrm:taxcomputation_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "update",
                    {"action": "generate", "tax_payable": str(obj.tax_payable)})
    messages.success(request,
        f"Computed {obj.number}: tax payable {obj.tax_payable}, paid YTD {obj.tax_paid_ytd}, "
        f"monthly TDS {obj.monthly_tds_amount}.")
    return redirect("hrm:taxcomputation_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def taxcomputation_link_form16(request, pk):
    obj = get_object_or_404(TaxComputation, pk=pk, tenant=request.tenant)
    ret = obj.link_form16(request.user)
    write_audit_log(request.user, obj, "update", {"action": "link_form16", "return": ret.number})
    messages.success(request,
        f"Linked Form 16 register row {ret.number} (Part A). Open Form 16 Part B for the full certificate.")
    return redirect("hrm:taxcomputation_detail", pk=obj.pk)


@login_required
def form16_partb(request, pk):
    """Form 16 Part B data/report view (PDF rendering deferred). Part A fields come from the linked
    StatutoryReturn + StatutoryConfig; Part B from this computation + its declaration lines."""
    obj = get_object_or_404(
        TaxComputation.objects.select_related("employee__party", "declaration", "statutory_return"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/tax/form16_partb.html", {
        "obj": obj,
        "config": StatutoryConfig.objects.filter(tenant=request.tenant).first(),
        "breakdown": _computation_breakdown(obj),
        "lines": obj.declaration.lines.all(),
    })


# ========================= 3.17 Payout & Reports =========================
# PayoutBatch (generate/approve/disburse from a locked cycle) + inline PayoutPayment
# mark-paid/failed/retry · PayslipDistribution send/view/download · BankReconciliation
# reconcile · payment_register + payout_exceptions reports.

def _recompute_batch_status(batch):
    """Re-derive a disbursed batch's status from its CURRENT payments: any failed/returned →
    partially_disbursed, else disbursed. Only applies post-disburse (a draft/approved batch keeps its
    status; a reconciled batch stays reconciled). The one place the derivation lives."""
    if batch.status not in ("disbursed", "partially_disbursed"):
        return
    has_failed = batch._current_payments().filter(status__in=["failed", "returned"]).exists()
    new_status = "partially_disbursed" if has_failed else "disbursed"
    if batch.status != new_status:
        batch.status = new_status
        batch.save(update_fields=["status", "updated_at"])


# ------------------------------------------------------------ PayoutBatch (+ workflow)
@login_required
def payoutbatch_list(request):
    # Annotate the list summary columns so the page is ONE query, not one _totals() aggregate per row.
    # All aggregates traverse the same `payments` relation filtered to current (non-retried) rows — a
    # current payment has no `retries`, so its LEFT JOIN yields exactly one row: no Sum fan-out. The
    # aliases avoid clashing with the model's @property (which the detail page still uses).
    _current = Q(payments__retries__isnull=True)
    qs = (PayoutBatch.objects.filter(tenant=request.tenant).select_related("cycle")
          .annotate(
              list_headcount=Count("payments", filter=_current, distinct=True),
              list_paid=Count("payments", filter=_current & Q(payments__status="paid"), distinct=True),
              list_total=Sum("payments__net_amount", filter=_current)))
    return crud_list(
        request,
        qs,
        "hrm/payout/payoutbatch/list.html",
        search_fields=["number", "cycle__number"],
        filters=[("status", "status", False), ("bank_file_format", "bank_file_format", False),
                 ("cycle", "cycle_id", True)],
        extra_context={
            "status_choices": PayoutBatch.STATUS_CHOICES,
            "bank_file_format_choices": PayoutBatch.BANK_FILE_FORMAT_CHOICES,
            "cycles": PayrollCycle.objects.filter(tenant=request.tenant, status="locked"),
        },
    )


@login_required
def payoutbatch_create(request):
    return crud_create(request, form_class=PayoutBatchForm,
                       template="hrm/payout/payoutbatch/form.html", success_url="hrm:payoutbatch_list")


@login_required
def payoutbatch_detail(request, pk):
    obj = get_object_or_404(PayoutBatch.objects.select_related("cycle"), pk=pk, tenant=request.tenant)
    payments = (obj.payments.select_related("employee__party", "retry_of")
                .order_by("employee__party__name"))
    return render(request, "hrm/payout/payoutbatch/detail.html", {
        "obj": obj,
        "payments": payments,
        "reconciliations": obj.reconciliations.order_by("-statement_date"),
    })


@login_required
def payoutbatch_edit(request, pk):
    obj = get_object_or_404(PayoutBatch, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft payout batch can be edited.")
        return redirect("hrm:payoutbatch_detail", pk=obj.pk)
    return crud_edit(request, model=PayoutBatch, pk=pk, form_class=PayoutBatchForm,
                     template="hrm/payout/payoutbatch/form.html", success_url="hrm:payoutbatch_list")


@login_required
@require_POST
def payoutbatch_delete(request, pk):
    obj = get_object_or_404(PayoutBatch, pk=pk, tenant=request.tenant)
    if not obj.is_editable:
        messages.error(request, "Only a draft payout batch can be deleted.")
        return redirect("hrm:payoutbatch_detail", pk=obj.pk)
    if obj.reconciliations.exists():
        messages.error(request, "This batch has a reconciliation and cannot be deleted.")
        return redirect("hrm:payoutbatch_detail", pk=obj.pk)
    return crud_delete(request, model=PayoutBatch, pk=pk, success_url="hrm:payoutbatch_list")


@tenant_admin_required
@require_POST
def payoutbatch_generate(request, pk):
    """(Re)generate one PayoutPayment per payslip of the batch's LOCKED cycle — draft-only. On-hold
    payslips are included as zero-action ``on_hold`` rows for audit completeness. Snapshots net_pay +
    the employee's MASKED bank details (never the raw account)."""
    batch = get_object_or_404(PayoutBatch.objects.select_related("cycle"), pk=pk, tenant=request.tenant)
    if not batch.cycle.is_locked:
        messages.error(request, "The payroll cycle must be locked before generating a payout batch.")
        return redirect("hrm:payoutbatch_detail", pk=batch.pk)
    if batch.status != "draft":
        messages.error(request, "Payments can only be (re)generated while the batch is a draft.")
        return redirect("hrm:payoutbatch_detail", pk=batch.pk)
    with transaction.atomic():
        batch.payments.all().delete()  # draft-only → no paid/failed rows to preserve
        count = 0
        for ps in batch.cycle.payslips.select_related("employee__party"):
            emp = ps.employee
            PayoutPayment.objects.create(
                tenant=request.tenant, batch=batch, payslip=ps, employee=emp,
                net_amount=ps.net_pay,
                bank_name_snapshot=emp.bank_name,
                bank_account_last4_snapshot=emp.masked_bank_account(),
                bank_routing_snapshot=emp.masked_bank_routing(),
                status="on_hold" if ps.on_hold else "pending")
            count += 1
        batch.generated_by = request.user
        batch.generated_at = timezone.now()
        batch.save(update_fields=["generated_by", "generated_at", "updated_at"])
    write_audit_log(request.user, batch, "update", {"action": "generate", "headcount": count})
    messages.success(request, f"Generated {count} payment(s) for {batch.number}.")
    return redirect("hrm:payoutbatch_detail", pk=batch.pk)


@tenant_admin_required
@require_POST
def payoutbatch_approve(request, pk):
    batch = get_object_or_404(PayoutBatch, pk=pk, tenant=request.tenant)
    if batch.status == "draft":
        if not batch.payments.exists():
            messages.error(request, "Generate payments before approving the batch.")
            return redirect("hrm:payoutbatch_detail", pk=batch.pk)
        batch.status = "approved"
        batch.approved_by = request.user
        batch.approved_at = timezone.now()
        batch.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        write_audit_log(request.user, batch, "update", {"action": "approve"})
        messages.success(request, f"Batch {batch.number} approved.")
    return redirect("hrm:payoutbatch_detail", pk=batch.pk)


@tenant_admin_required
@require_POST
def payoutbatch_disburse(request, pk):
    """Mark an approved batch as sent to the bank: pending payments → processing (initiated_at stamped).
    The actual bank-file export is deferred. Mark each payment paid/failed as the bank confirms."""
    batch = get_object_or_404(PayoutBatch, pk=pk, tenant=request.tenant)
    if batch.status != "approved":
        messages.error(request, "Only an approved batch can be disbursed.")
        return redirect("hrm:payoutbatch_detail", pk=batch.pk)
    now = timezone.now()
    with transaction.atomic():
        batch.payments.filter(status="pending").update(status="processing", initiated_at=now)
        batch.status = "disbursed"
        batch.disbursed_at = now
        batch.save(update_fields=["status", "disbursed_at", "updated_at"])
        _recompute_batch_status(batch)
    write_audit_log(request.user, batch, "update", {"action": "disburse"})
    messages.success(request, f"Batch {batch.number} disbursed — mark each payment paid/failed as the bank confirms.")
    return redirect("hrm:payoutbatch_detail", pk=batch.pk)


# ---------------------------------------------------------- PayoutPayment actions
@tenant_admin_required
@require_POST
def payoutpayment_mark_paid(request, pk):
    payment = get_object_or_404(PayoutPayment.objects.select_related("batch"), pk=pk, tenant=request.tenant)
    if payment.status not in ("pending", "processing"):
        messages.error(request, "Only a pending/processing payment can be marked paid.")
        return redirect("hrm:payoutbatch_detail", pk=payment.batch_id)
    payment.status = "paid"
    payment.paid_on = timezone.now()
    payment.transaction_reference = request.POST.get("transaction_reference", "").strip()[:64]
    with transaction.atomic():
        payment.save(update_fields=["status", "paid_on", "transaction_reference", "updated_at"])
        _recompute_batch_status(payment.batch)
    write_audit_log(request.user, payment, "update", {"action": "mark_paid"})
    messages.success(request, "Payment marked paid.")
    return redirect("hrm:payoutbatch_detail", pk=payment.batch_id)


@tenant_admin_required
@require_POST
def payoutpayment_mark_failed(request, pk):
    payment = get_object_or_404(PayoutPayment.objects.select_related("batch"), pk=pk, tenant=request.tenant)
    if payment.status not in ("pending", "processing"):
        messages.error(request, "Only a pending/processing payment can be marked failed.")
        return redirect("hrm:payoutbatch_detail", pk=payment.batch_id)
    payment.status = "failed"
    payment.failure_reason = request.POST.get("failure_reason", "").strip()[:2000]
    with transaction.atomic():
        payment.save(update_fields=["status", "failure_reason", "updated_at"])
        _recompute_batch_status(payment.batch)
    write_audit_log(request.user, payment, "update", {"action": "mark_failed"})
    messages.success(request, "Payment marked failed.")
    return redirect("hrm:payoutbatch_detail", pk=payment.batch_id)


@tenant_admin_required
@require_POST
def payoutpayment_retry(request, pk):
    """Re-initiate a failed/returned payment as a NEW row (retry_of → the original, preserving history),
    re-snapshotting the employee's CURRENT bank details (in case they were corrected)."""
    original = get_object_or_404(
        PayoutPayment.objects.select_related("batch", "employee"), pk=pk, tenant=request.tenant)
    if original.status not in ("failed", "returned"):
        messages.error(request, "Only a failed/returned payment can be retried.")
        return redirect("hrm:payoutbatch_detail", pk=original.batch_id)
    emp = original.employee
    with transaction.atomic():
        PayoutPayment.objects.create(
            tenant=request.tenant, batch=original.batch, payslip=original.payslip, employee=emp,
            net_amount=original.net_amount,
            bank_name_snapshot=emp.bank_name,
            bank_account_last4_snapshot=emp.masked_bank_account(),
            bank_routing_snapshot=emp.masked_bank_routing(),
            payment_method=original.payment_method, status="pending", retry_of=original)
        _recompute_batch_status(original.batch)
    write_audit_log(request.user, original, "update", {"action": "retry"})
    messages.success(request, "Retry payment created (pending). Mark it paid once the bank confirms.")
    return redirect("hrm:payoutbatch_detail", pk=original.batch_id)


# ---------------------------------------------------------- PayslipDistribution
@login_required
def payslipdistribution_list(request):
    return crud_list(
        request,
        # No payslip__cycle join — the list renders only payslip.number + employee.party.name; the cycle
        # filter is an _id lookup and the ordering join is added by the ORM independently.
        PayslipDistribution.objects.filter(tenant=request.tenant)
        .select_related("payslip__employee__party"),
        "hrm/payout/payslipdistribution/list.html",
        search_fields=["payslip__number", "payslip__employee__party__name"],
        filters=[("status", "status", False), ("delivery_channel", "delivery_channel", False),
                 ("cycle", "payslip__cycle_id", True)],
        extra_context={
            "status_choices": PayslipDistribution.STATUS_CHOICES,
            "delivery_channel_choices": PayslipDistribution.DELIVERY_CHANNEL_CHOICES,
            "cycles": PayrollCycle.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def payslipdistribution_detail(request, pk):
    obj = get_object_or_404(
        PayslipDistribution.objects.select_related("payslip__employee__party", "sent_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/payout/payslipdistribution/detail.html", {"obj": obj})


def _mark_sent(dist, user):
    emp = dist.payslip.employee
    dist.sent_to_email = emp.work_email or emp.personal_email or ""
    dist.status = "sent"
    dist.sent_at = timezone.now()
    dist.sent_by = user
    dist.save(update_fields=["sent_to_email", "status", "sent_at", "sent_by", "updated_at"])


@tenant_admin_required
@require_POST
def payslipdistribution_send(request, pk):
    """Mark one payslip's distribution as sent (actual PDF+SMTP deferred). Soft-warns if the payslip's
    payout isn't paid yet (Deel's payment-before-payslip ordering — a warning, not a hard block)."""
    dist = get_object_or_404(
        PayslipDistribution.objects.select_related("payslip__employee"), pk=pk, tenant=request.tenant)
    _mark_sent(dist, request.user)
    if not PayoutPayment.objects.filter(
            tenant=request.tenant, payslip=dist.payslip, status="paid").exists():
        messages.warning(request, "Payslip sent, but this employee's payout is not yet marked paid.")
    else:
        messages.success(request, "Payslip marked sent.")
    write_audit_log(request.user, dist, "update", {"action": "send"})
    return redirect("hrm:payslipdistribution_detail", pk=dist.pk)


@tenant_admin_required
@require_POST
def payslipdistribution_send_cycle(request):
    """Bulk: ensure a distribution row exists for every payslip of the POSTed cycle and mark them sent."""
    cycle_id = request.POST.get("cycle", "").strip()
    if not cycle_id.isdigit():
        messages.error(request, "Select a cycle to distribute.")
        return redirect("hrm:payslipdistribution_list")
    cycle = get_object_or_404(PayrollCycle, pk=int(cycle_id), tenant=request.tenant)
    count = 0
    with transaction.atomic():
        for ps in cycle.payslips.select_related("employee").all():
            _mark_sent(PayslipDistribution.for_payslip(ps), request.user)
            count += 1
    write_audit_log(request.user, cycle, "update", {"action": "distribute_payslips", "count": count})
    messages.success(request, f"Marked {count} payslip(s) sent for {cycle.number}.")
    return redirect("hrm:payslipdistribution_list")


@login_required
@require_POST
def payslipdistribution_mark_viewed(request, pk):
    # SECURITY NOTE (accepted, tracked): no User<->EmployeeProfile link exists yet, so this can't be
    # scoped to "the payslip's own employee". Intentionally left @login_required (NOT
    # @tenant_admin_required) — it discloses no data and only bumps a status/timestamp already readable
    # by any tenant user via payslipdistribution_detail. When a real ESS portal + user<->employee link
    # lands, replace the tenant filter with an ownership filter (dist.payslip.employee.user==request.user)
    # rather than gating by admin role. Forward-only.
    dist = get_object_or_404(PayslipDistribution, pk=pk, tenant=request.tenant)
    if dist.status in ("pending", "sent"):
        dist.status = "viewed"
    dist.viewed_at = timezone.now()
    dist.save(update_fields=["status", "viewed_at", "updated_at"])
    return redirect("hrm:payslipdistribution_detail", pk=dist.pk)


@login_required
@require_POST
def payslipdistribution_mark_downloaded(request, pk):
    dist = get_object_or_404(PayslipDistribution, pk=pk, tenant=request.tenant)
    dist.status = "downloaded"  # terminal signal — always advances
    dist.downloaded_at = timezone.now()
    dist.save(update_fields=["status", "downloaded_at", "updated_at"])
    return redirect("hrm:payslipdistribution_detail", pk=dist.pk)


# ---------------------------------------------------------- BankReconciliation
@login_required
def bankreconciliation_list(request):
    return crud_list(
        request,
        # List renders only batch.number — no batch__cycle join (detail keeps it, where cycle IS shown).
        BankReconciliation.objects.filter(tenant=request.tenant).select_related("batch"),
        "hrm/payout/bankreconciliation/list.html",
        search_fields=["number", "batch__number", "statement_reference"],
        filters=[("status", "status", False), ("batch", "batch_id", True)],
        extra_context={
            "status_choices": BankReconciliation.STATUS_CHOICES,
            "batches": PayoutBatch.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def bankreconciliation_create(request):
    return crud_create(request, form_class=BankReconciliationForm,
                       template="hrm/payout/bankreconciliation/form.html",
                       success_url="hrm:bankreconciliation_list")


@login_required
def bankreconciliation_detail(request, pk):
    obj = get_object_or_404(
        BankReconciliation.objects.select_related("batch__cycle", "reconciled_by"),
        pk=pk, tenant=request.tenant)
    exceptions = (obj.batch._current_payments().filter(status__in=["failed", "returned"])
                  .select_related("employee__party"))
    return render(request, "hrm/payout/bankreconciliation/detail.html",
                  {"obj": obj, "exceptions": exceptions})


@login_required
def bankreconciliation_edit(request, pk):
    obj = get_object_or_404(BankReconciliation, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "in_progress"):
        messages.error(request, "A reconciled/closed reconciliation can no longer be edited.")
        return redirect("hrm:bankreconciliation_detail", pk=obj.pk)
    return crud_edit(request, model=BankReconciliation, pk=pk, form_class=BankReconciliationForm,
                     template="hrm/payout/bankreconciliation/form.html",
                     success_url="hrm:bankreconciliation_list")


@login_required
@require_POST
def bankreconciliation_delete(request, pk):
    obj = get_object_or_404(BankReconciliation, pk=pk, tenant=request.tenant)
    if obj.status not in ("pending", "in_progress"):
        messages.error(request, "A reconciled/closed reconciliation can no longer be deleted.")
        return redirect("hrm:bankreconciliation_detail", pk=obj.pk)
    return crud_delete(request, model=BankReconciliation, pk=pk, success_url="hrm:bankreconciliation_list")


@tenant_admin_required
@require_POST
def bankreconciliation_reconcile(request, pk):
    recon = get_object_or_404(
        BankReconciliation.objects.select_related("batch"), pk=pk, tenant=request.tenant)
    recon.recompute()  # sets matched/unmatched + status + reconciled_at
    recon.reconciled_by = request.user
    recon.save(update_fields=["reconciled_by", "updated_at"])
    # On a full match, flip the batch itself to reconciled (batch-level only, no payment changes).
    if recon.status == "reconciled" and recon.batch.status in ("disbursed", "partially_disbursed"):
        recon.batch.status = "reconciled"
        recon.batch.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, recon, "update", {"action": "reconcile", "status": recon.status})
    messages.success(request,
        f"Reconciliation {recon.number}: {recon.matched_count} matched, {recon.unmatched_count} "
        f"unmatched ({recon.get_status_display()}).")
    return redirect("hrm:bankreconciliation_detail", pk=recon.pk)


# ---------------------------------------------------------- Reports (no new model)
@login_required
def payment_register(request, pk):
    """Bank-advice / payment-register report over one batch's current payments — by status, by method,
    plus the per-employee advice rows (masked accounts, amount, UTR)."""
    batch = get_object_or_404(PayoutBatch.objects.select_related("cycle"), pk=pk, tenant=request.tenant)
    cur = batch._current_payments()
    payments = cur.select_related("employee__party").order_by("employee__party__name")
    by_status = list(cur.values("status").annotate(c=Count("id"), a=Sum("net_amount")).order_by("status"))
    by_method = list(cur.values("payment_method").annotate(c=Count("id"), a=Sum("net_amount"))
                     .order_by("payment_method"))
    # Attach human labels (the group-by loses get_*_display).
    status_labels = dict(PayoutPayment.STATUS_CHOICES)
    method_labels = dict(PayoutPayment.PAYMENT_METHOD_CHOICES)
    for r in by_status:
        r["label"] = status_labels.get(r["status"], r["status"])
    for r in by_method:
        r["label"] = method_labels.get(r["payment_method"], r["payment_method"])
    return render(request, "hrm/payout/payment_register.html", {
        "batch": batch, "payments": payments, "by_status": by_status, "by_method": by_method})


@login_required
def payout_exceptions(request):
    """Failed/returned payments not yet retried, across all batches — the exception/follow-up report."""
    qs = (PayoutPayment.objects.filter(
            tenant=request.tenant, status__in=["failed", "returned"], retries__isnull=True)
          .select_related("batch__cycle", "employee__party").order_by("-batch__created_at"))
    batch_id = request.GET.get("batch", "").strip()
    if batch_id.isdigit():
        qs = qs.filter(batch_id=int(batch_id))
    return render(request, "hrm/payout/exceptions.html", {
        "payments": qs, "batches": PayoutBatch.objects.filter(tenant=request.tenant)})


# ============================================================ 3.18 Goal Setting (Performance Mgmt)
def _current_employee_profile(request):
    """Resolve the logged-in user's ``EmployeeProfile`` (via ``User.party`` → reverse O2O), or
    ``None`` for a user with no linked party/profile (e.g. the superuser). Django's reverse-O2O
    ``RelatedObjectDoesNotExist`` subclasses ``AttributeError``, so ``getattr(..., None)`` is safe."""
    party = getattr(request.user, "party", None)
    if party is None:
        return None
    return getattr(party, "employee_profile", None)


# ---------------------------------------------------------------- GoalPeriod (3.18.4 Goal Timeline)
@login_required
def goalperiod_list(request):
    return crud_list(
        request,
        # O(1) objective count per row via annotation (no N+1 on GoalPeriod.objective_count).
        # Explicit order_by — the Count() GROUP BY otherwise drops Meta.ordering (paginator warning).
        GoalPeriod.objects.filter(tenant=request.tenant)
        .annotate(num_objectives=Count("objectives")).order_by("-start_date", "name"),
        "hrm/performance/goalperiod/list.html",
        search_fields=("name",),
        filters=[("status", "status", False), ("period_type", "period_type", False)],
        extra_context={
            "status_choices": GoalPeriod.STATUS_CHOICES,
            "period_type_choices": GoalPeriod.PERIOD_TYPE_CHOICES,
        },
    )


@login_required
def goalperiod_create(request):
    return crud_create(request, form_class=GoalPeriodForm,
                       template="hrm/performance/goalperiod/form.html",
                       success_url="hrm:goalperiod_list")


@login_required
def goalperiod_detail(request, pk):
    # Prefetch objectives + their key results so avg_progress_pct / per-objective progress_pct
    # stay a bounded number of queries (not N+1 across objectives).
    obj = get_object_or_404(
        GoalPeriod.objects.prefetch_related(
            Prefetch("objectives",
                     queryset=Objective.objects.filter(tenant=request.tenant)
                     .select_related("owner__party", "goal_period", "department")
                     .prefetch_related("key_results"))),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/performance/goalperiod/detail.html", {
        "obj": obj,
        "objectives": obj.objectives.all(),  # prefetched above
    })


@login_required
def goalperiod_edit(request, pk):
    return crud_edit(request, model=GoalPeriod, pk=pk, form_class=GoalPeriodForm,
                     template="hrm/performance/goalperiod/form.html",
                     success_url="hrm:goalperiod_list")


@login_required
@require_POST
def goalperiod_delete(request, pk):
    obj = get_object_or_404(GoalPeriod, pk=pk, tenant=request.tenant)
    # goal_period is PROTECT on Objective — pre-check for a friendly message instead of a 500.
    if obj.objectives.exists():
        messages.error(request, "This goal period has objectives and cannot be deleted.")
        return redirect("hrm:goalperiod_detail", pk=obj.pk)
    return crud_delete(request, model=GoalPeriod, pk=pk, success_url="hrm:goalperiod_list")


@tenant_admin_required
@require_POST
def goalperiod_activate(request, pk):
    obj = get_object_or_404(GoalPeriod, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "closed"):
        obj.status = "active"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "activate"})
        messages.success(request, f"Goal period '{obj.name}' activated.")
    else:
        messages.error(request, "Only a draft or closed goal period can be activated.")
    return redirect("hrm:goalperiod_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def goalperiod_close(request, pk):
    obj = get_object_or_404(GoalPeriod, pk=pk, tenant=request.tenant)
    if obj.status == "active":
        obj.status = "closed"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "close"})
        messages.success(request, f"Goal period '{obj.name}' closed.")
    else:
        messages.error(request, "Only an active goal period can be closed.")
    return redirect("hrm:goalperiod_detail", pk=obj.pk)


# ---------------------------------------------------------- Objective (3.18.1/3.18.2/3.18.3 the "O")
@login_required
def objective_list(request):
    qs = (Objective.objects.filter(tenant=request.tenant)
          .select_related("owner__party", "goal_period", "department", "parent_objective")
          .prefetch_related("key_results"))
    # ?mine=1 — my own objectives + my direct reports' (via the derived reporting line), 3.18.2.
    if request.GET.get("mine") == "1":
        profile = _current_employee_profile(request)
        if profile is not None:
            qs = qs.filter(Q(owner=profile) | Q(owner__employment__manager=profile.party))
        else:
            qs = qs.none()
    return crud_list(
        request, qs,
        "hrm/performance/objective/list.html",
        search_fields=("title", "number", "owner__party__name"),
        filters=[("status", "status", False), ("scope", "scope", False),
                 ("target_type", "target_type", False), ("goal_period", "goal_period_id", True),
                 ("owner", "owner_id", True), ("department", "department_id", True)],
        extra_context={
            "status_choices": Objective.STATUS_CHOICES,
            "scope_choices": Objective.SCOPE_CHOICES,
            "target_type_choices": Objective.TARGET_TYPE_CHOICES,
            "goal_periods": GoalPeriod.objects.filter(tenant=request.tenant).order_by("-start_date"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "departments": OrgUnit.objects.filter(tenant=request.tenant, kind="department").order_by("name"),
            "mine": request.GET.get("mine") == "1",
        },
    )


@login_required
def objective_tree(request):
    """Alignment/cascade tree (3.18.2) — top-level objectives with nested children, bounded depth.
    Prefetches three levels so the recursive template stays query-bounded."""
    # goal_period is in select_related because health_status falls back to the period window when an
    # objective's own start/due are null (the common case) — else it re-queries per node (N+1).
    grandchild = Prefetch("child_objectives",
                          queryset=Objective.objects.filter(tenant=request.tenant)
                          .select_related("owner__party", "goal_period").prefetch_related("key_results"))
    child = Prefetch("child_objectives",
                     queryset=Objective.objects.filter(tenant=request.tenant)
                     .select_related("owner__party", "goal_period").prefetch_related("key_results", grandchild))
    top = (Objective.objects.filter(tenant=request.tenant, parent_objective__isnull=True)
           .select_related("owner__party", "goal_period")
           .prefetch_related("key_results", child))
    period_id = request.GET.get("goal_period", "").strip()
    if period_id.isdigit():
        top = top.filter(goal_period_id=int(period_id))
    return render(request, "hrm/performance/objective/tree.html", {
        "objectives": top,
        "goal_periods": GoalPeriod.objects.filter(tenant=request.tenant).order_by("-start_date"),
        # Matches the 3 prefetched levels above (company→department→individual) — a 4th level would
        # fall outside the prefetch and re-query per node.
        "tree_max_depth": 3,
    })


@login_required
def objective_create(request):
    return crud_create(request, form_class=ObjectiveForm,
                       template="hrm/performance/objective/form.html",
                       success_url="hrm:objective_list")


@login_required
def objective_detail(request, pk):
    obj = get_object_or_404(
        Objective.objects.select_related("owner__party", "goal_period", "department", "parent_objective__owner__party")
        .prefetch_related("key_results"),
        pk=pk, tenant=request.tenant)
    key_results = list(obj.key_results.all())
    for kr in key_results:
        kr.objective = obj  # wire the parent so kr.health_status doesn't re-query goal_period
    child_objectives = (obj.child_objectives.filter(tenant=request.tenant)
                        .select_related("owner__party", "goal_period")  # goal_period: health_status fallback
                        .prefetch_related("key_results").order_by("title"))
    recent_checkins = (GoalCheckIn.objects.filter(tenant=request.tenant, key_result__objective=obj)
                       .select_related("key_result", "created_by__party")
                       .order_by("-checkin_date", "-created_at")[:20])
    return render(request, "hrm/performance/objective/detail.html", {
        "obj": obj,
        "key_results": key_results,
        "child_objectives": child_objectives,
        "recent_checkins": recent_checkins,
        "kr_form": KeyResultForm(tenant=request.tenant),
    })


@login_required
def objective_edit(request, pk):
    return crud_edit(request, model=Objective, pk=pk, form_class=ObjectiveForm,
                     template="hrm/performance/objective/form.html",
                     success_url="hrm:objective_list")


@login_required
@require_POST
def objective_delete(request, pk):
    # child_objectives are SET_NULL, key_results (+ their check-ins) CASCADE — a clean delete.
    return crud_delete(request, model=Objective, pk=pk, success_url="hrm:objective_list")


# ------------------------------------------------------------- KeyResult (3.18.1/3.18.3 the "KR")
@login_required
def keyresult_create(request, objective_pk):
    objective = get_object_or_404(Objective, pk=objective_pk, tenant=request.tenant)
    if request.method == "POST":
        form = KeyResultForm(request.POST,
                             instance=KeyResult(tenant=request.tenant, objective=objective),
                             tenant=request.tenant)
        if form.is_valid():
            kr = form.save()
            write_audit_log(request.user, kr, "create")
            messages.success(request, "Key result added.")
            return redirect("hrm:objective_detail", pk=objective.pk)
    else:
        # Default the weight to an equal split among existing siblings (overridable — Lattice pattern).
        sibling_count = objective.key_results.count()
        default_weight = (Decimal("100") / (sibling_count + 1)).quantize(Decimal("0.01"))
        form = KeyResultForm(instance=KeyResult(tenant=request.tenant, objective=objective),
                             initial={"weight": default_weight}, tenant=request.tenant)
    return render(request, "hrm/performance/keyresult/form.html", {
        "form": form, "is_edit": False, "objective": objective})


@login_required
def keyresult_detail(request, pk):
    kr = get_object_or_404(
        KeyResult.objects.select_related("objective__goal_period", "objective__owner__party"),
        pk=pk, tenant=request.tenant)
    checkins = kr.checkins.select_related("created_by__party").order_by("-checkin_date", "-created_at")
    return render(request, "hrm/performance/keyresult/detail.html", {
        "obj": kr,
        "objective": kr.objective,
        "checkins": checkins,
        "checkin_form": GoalCheckInForm(tenant=request.tenant),
    })


@login_required
def keyresult_edit(request, pk):
    kr = get_object_or_404(KeyResult.objects.select_related("objective"), pk=pk, tenant=request.tenant)
    objective = kr.objective
    if request.method == "POST":
        form = KeyResultForm(request.POST, instance=kr, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, kr, "update")
            messages.success(request, "Key result updated.")
            return redirect("hrm:objective_detail", pk=objective.pk)
    else:
        form = KeyResultForm(instance=kr, tenant=request.tenant)
    return render(request, "hrm/performance/keyresult/form.html", {
        "form": form, "is_edit": True, "obj": kr, "objective": objective})


@login_required
@require_POST
def keyresult_delete(request, pk):
    kr = get_object_or_404(KeyResult.objects.select_related("objective"), pk=pk, tenant=request.tenant)
    objective_pk = kr.objective_id
    write_audit_log(request.user, kr, "delete")
    kr.delete()
    messages.success(request, "Key result deleted.")
    return redirect("hrm:objective_detail", pk=objective_pk)


# ---------------------------------------------------------- GoalCheckIn (3.18.5 Goal Tracking log)
@login_required
def goalcheckin_list(request):
    return crud_list(
        request,
        GoalCheckIn.objects.filter(tenant=request.tenant)
        .select_related("key_result", "created_by__party"),  # template uses key_result.title only
        "hrm/performance/goalcheckin/list.html",
        search_fields=("number", "key_result__title", "comment"),
        filters=[("confidence", "confidence", False), ("key_result", "key_result_id", True)],
        extra_context={
            "confidence_choices": GoalCheckIn.CONFIDENCE_CHOICES,
            "key_results": (KeyResult.objects.filter(tenant=request.tenant)
                            .select_related("objective").order_by("title")),
        },
    )


@login_required
def goalcheckin_create(request, keyresult_pk):
    kr = get_object_or_404(KeyResult.objects.select_related("objective"), pk=keyresult_pk, tenant=request.tenant)
    if request.method == "POST":
        checkin = GoalCheckIn(tenant=request.tenant, key_result=kr,
                              created_by=_current_employee_profile(request))
        form = GoalCheckInForm(request.POST, instance=checkin, tenant=request.tenant)
        if form.is_valid():
            form.save()  # GoalCheckIn.save() advances key_result.current_value
            write_audit_log(request.user, kr, "update", {"action": "check_in"})
            messages.success(request, "Check-in logged.")
            return redirect("hrm:keyresult_detail", pk=kr.pk)
    else:
        form = GoalCheckInForm(instance=GoalCheckIn(tenant=request.tenant, key_result=kr),
                               tenant=request.tenant)
    return render(request, "hrm/performance/goalcheckin/form.html", {
        "form": form, "is_edit": False, "key_result": kr, "objective": kr.objective})


@login_required
def goalcheckin_detail(request, pk):
    return crud_detail(request, model=GoalCheckIn, pk=pk,
                       template="hrm/performance/goalcheckin/detail.html",
                       select_related=("key_result__objective", "created_by__party"))


@login_required
@require_POST
def goalcheckin_delete(request, pk):
    obj = get_object_or_404(GoalCheckIn.objects.select_related("key_result"), pk=pk, tenant=request.tenant)
    kr_pk = obj.key_result_id
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Check-in deleted.")
    return redirect("hrm:keyresult_detail", pk=kr_pk)


# ============================================================ 3.19 Performance Review (Performance Mgmt)
def _is_admin(user):
    """Tenant-admin-or-superuser check (mirrors apps.core.decorators.tenant_admin_required)."""
    return user.is_superuser or getattr(user, "is_tenant_admin", False)


def _is_reviewer(request, review):
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == review.reviewer_id


def _can_edit_review(request, review):
    """A review (and its competency ratings) is editable ONLY by the reviewer or a tenant admin,
    and ONLY while it's still a draft. This protects the manager ``private_notes`` confidentiality
    boundary (the subject must never reach the edit form to read them) and the submit→share→
    acknowledge audit trail (content is locked once submitted)."""
    return review.status == "draft" and (_is_admin(request.user) or _is_reviewer(request, review))


def _can_view_review(request, review):
    """Who may view a review's content: a tenant admin, the reviewer (their authored review), or
    the subject. Everyone else is denied — performance reviews are CONFIDENTIAL, not company-open
    the way 3.18 OKRs are (a curious employee must not read who is rated what across the tenant)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk in (review.subject_id, review.reviewer_id)


def _visible_reviews_q(request):
    """A ``Q`` restricting review rosters/lists to what the requester may see (their own subject or
    reviewer rows). Returns ``None`` for a tenant admin (no restriction)."""
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(pk__in=[])  # a tenant-less / employee-less user sees nothing
    return Q(subject=profile) | Q(reviewer=profile)


# ---------------------------------------------------------------- ReviewCycle (3.19.1 Review Cycles)
@login_required
def reviewcycle_list(request):
    return crud_list(
        request,
        # Explicit order_by — the Count() GROUP BY otherwise drops Meta.ordering (paginator warning).
        ReviewCycle.objects.filter(tenant=request.tenant).select_related("goal_period")
        .annotate(num_reviews=Count("reviews")).order_by("-self_review_start", "name"),
        "hrm/performance/reviewcycle/list.html",
        search_fields=("name",),
        filters=[("status", "status", False), ("cycle_type", "cycle_type", False)],
        extra_context={
            "status_choices": ReviewCycle.STATUS_CHOICES,
            "cycle_type_choices": ReviewCycle.CYCLE_TYPE_CHOICES,
        },
    )


@login_required
def reviewcycle_create(request):
    return crud_create(request, form_class=ReviewCycleForm,
                       template="hrm/performance/reviewcycle/form.html",
                       success_url="hrm:reviewcycle_list")


@login_required
def reviewcycle_detail(request, pk):
    obj = get_object_or_404(
        ReviewCycle.objects.select_related("goal_period"), pk=pk, tenant=request.tenant)
    reviews_qs = (obj.reviews.select_related("subject__party", "reviewer__party", "template")
                  .prefetch_related("ratings"))  # effective_rating reads ratings — avoid per-row N+1
    # Confidentiality: a non-admin sees only reviews they're the subject or reviewer of (not the
    # whole tenant's roster of who-is-rated-what). Admins see the full cycle.
    vq = _visible_reviews_q(request)
    if vq is not None:
        reviews_qs = reviews_qs.filter(vq)
    reviews = list(reviews_qs.order_by("review_type", "subject__party__name"))
    # Phase-progress summary (single pass over the already-fetched reviews — no extra queries).
    phase_counts = {"draft": 0, "submitted": 0, "shared": 0, "acknowledged": 0}
    for r in reviews:
        phase_counts[r.status] = phase_counts.get(r.status, 0) + 1
    # Next phase for the Advance button.
    order = ReviewCycle.PHASE_ORDER
    idx = order.index(obj.status) if obj.status in order else 0
    next_phase = order[idx + 1] if idx + 1 < len(order) else None
    next_phase_label = dict(ReviewCycle.STATUS_CHOICES).get(next_phase) if next_phase else None
    return render(request, "hrm/performance/reviewcycle/detail.html", {
        "obj": obj,
        "reviews": reviews,
        "phase_counts": phase_counts,
        "next_phase_label": next_phase_label,
    })


@login_required
def reviewcycle_edit(request, pk):
    return crud_edit(request, model=ReviewCycle, pk=pk, form_class=ReviewCycleForm,
                     template="hrm/performance/reviewcycle/form.html",
                     success_url="hrm:reviewcycle_list")


@login_required
@require_POST
def reviewcycle_delete(request, pk):
    obj = get_object_or_404(ReviewCycle, pk=pk, tenant=request.tenant)
    # cycle is PROTECT on PerformanceReview — pre-check for a friendly message.
    if obj.reviews.exists():
        messages.error(request, "This review cycle has reviews and cannot be deleted.")
        return redirect("hrm:reviewcycle_detail", pk=obj.pk)
    return crud_delete(request, model=ReviewCycle, pk=pk, success_url="hrm:reviewcycle_list")


@tenant_admin_required
@require_POST
def reviewcycle_advance_phase(request, pk):
    obj = get_object_or_404(ReviewCycle, pk=pk, tenant=request.tenant)
    order = ReviewCycle.PHASE_ORDER
    idx = order.index(obj.status) if obj.status in order else 0
    if idx + 1 < len(order):
        obj.status = order[idx + 1]
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "advance_phase", "to": obj.status})
        messages.success(request, f"Cycle '{obj.name}' advanced to {obj.get_status_display()}.")
    else:
        messages.error(request, "This cycle is already closed.")
    return redirect("hrm:reviewcycle_detail", pk=obj.pk)


# ------------------------------------------------------- ReviewTemplate (3.19.3/3.19.4 form definition)
@login_required
def reviewtemplate_list(request):
    return crud_list(
        request,
        ReviewTemplate.objects.filter(tenant=request.tenant),
        "hrm/performance/reviewtemplate/list.html",
        search_fields=("name", "number"),
        filters=[("review_type", "review_type", False), ("is_active", "is_active", False)],
        extra_context={"review_type_choices": ReviewTemplate.REVIEW_TYPE_CHOICES},
    )


@login_required
def reviewtemplate_create(request):
    return crud_create(request, form_class=ReviewTemplateForm,
                       template="hrm/performance/reviewtemplate/form.html",
                       success_url="hrm:reviewtemplate_list")


@login_required
def reviewtemplate_detail(request, pk):
    return crud_detail(request, model=ReviewTemplate, pk=pk,
                       template="hrm/performance/reviewtemplate/detail.html")


@login_required
def reviewtemplate_edit(request, pk):
    return crud_edit(request, model=ReviewTemplate, pk=pk, form_class=ReviewTemplateForm,
                     template="hrm/performance/reviewtemplate/form.html",
                     success_url="hrm:reviewtemplate_list")


@login_required
@require_POST
def reviewtemplate_delete(request, pk):
    # template is SET_NULL on PerformanceReview — delete succeeds (historical reviews keep their
    # data, just lose the template link). No pre-check needed.
    return crud_delete(request, model=ReviewTemplate, pk=pk, success_url="hrm:reviewtemplate_list")


# ---------------------------------------------- PerformanceReview (3.19.2/3.19.3/3.19.4 the review row)
@login_required
def performancereview_list(request):
    qs = (PerformanceReview.objects.filter(tenant=request.tenant)
          .select_related("cycle", "template", "subject__party", "reviewer__party")
          .prefetch_related("ratings"))
    # Confidentiality: a non-admin sees only reviews they're the subject or reviewer of — the
    # tenant-wide reviews roster (who-is-rated-what) is admin-only.
    profile = _current_employee_profile(request)
    vq = _visible_reviews_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    if request.GET.get("mine") == "1":
        qs = qs.filter(Q(subject=profile) | Q(reviewer=profile)) if profile is not None else qs.none()
    return crud_list(
        request, qs,
        "hrm/performance/performancereview/list.html",
        search_fields=("number", "subject__party__name", "reviewer__party__name"),
        filters=[("cycle", "cycle_id", True), ("review_type", "review_type", False),
                 ("status", "status", False), ("subject", "subject_id", True),
                 ("reviewer", "reviewer_id", True)],
        extra_context={
            "review_type_choices": PerformanceReview.REVIEW_TYPE_CHOICES,
            "status_choices": PerformanceReview.STATUS_CHOICES,
            "cycles": ReviewCycle.objects.filter(tenant=request.tenant).order_by("-self_review_start"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "mine": request.GET.get("mine") == "1",
            # For gating the row Edit button to who can actually edit (draft + reviewer/admin).
            "is_admin": _is_admin(request.user),
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def performancereview_create(request):
    return crud_create(request, form_class=PerformanceReviewForm,
                       template="hrm/performance/performancereview/form.html",
                       success_url="hrm:performancereview_list")


@login_required
def performancereview_detail(request, pk):
    obj = get_object_or_404(
        PerformanceReview.objects.select_related(
            "cycle__goal_period", "template", "subject__party", "reviewer__party", "acknowledged_by__party")
        .prefetch_related("ratings"),
        pk=pk, tenant=request.tenant)
    # Confidentiality: only the subject, the reviewer, or a tenant admin may view a review.
    if not _can_view_review(request, obj):
        raise PermissionDenied("You do not have access to this review.")
    ratings = list(obj.ratings.all())
    profile = _current_employee_profile(request)
    is_admin = _is_admin(request.user)
    is_reviewer = profile is not None and profile.pk == obj.reviewer_id
    is_subject = profile is not None and profile.pk == obj.subject_id
    # Private manager notes: reviewer or admin only — never the subject-only viewer.
    show_private = is_admin or is_reviewer
    # Anonymised peer/upward feedback hides the reviewer from the subject (admin/reviewer still see it).
    show_reviewer = not (obj.is_anonymous and obj.review_type in ("peer", "upward")
                         and not (is_admin or is_reviewer))
    # Goal-review section: the subject's Objectives for the cycle's aligned OKR period.
    goal_objectives = []
    if obj.template and obj.template.include_goals and obj.goal_period is not None:
        goal_objectives = (Objective.objects.filter(
            tenant=request.tenant, owner=obj.subject, goal_period=obj.goal_period)
            .prefetch_related("key_results").order_by("title"))
    return render(request, "hrm/performance/performancereview/detail.html", {
        "obj": obj,
        "ratings": ratings,
        "show_private": show_private,
        "show_reviewer": show_reviewer,
        "is_subject": is_subject,
        "is_reviewer": is_reviewer,
        "can_edit": obj.status == "draft" and (is_admin or is_reviewer),
        "goal_objectives": goal_objectives,
        "rating_form": ReviewRatingForm(tenant=request.tenant),
    })


@login_required
def performancereview_edit(request, pk):
    obj = get_object_or_404(PerformanceReview, pk=pk, tenant=request.tenant)
    # Gate: only the reviewer or a tenant admin, and only while draft — keeps private_notes hidden
    # from the subject and locks content once the review is submitted.
    if not _can_edit_review(request, obj):
        messages.error(request, "Only the reviewer or a tenant admin can edit this review, and only while it is a draft.")
        return redirect("hrm:performancereview_detail", pk=obj.pk)
    return crud_edit(request, model=PerformanceReview, pk=pk, form_class=PerformanceReviewForm,
                     template="hrm/performance/performancereview/form.html",
                     success_url="hrm:performancereview_list")


@login_required
@require_POST
def performancereview_delete(request, pk):
    obj = get_object_or_404(PerformanceReview, pk=pk, tenant=request.tenant)
    # A tenant admin may delete any review; a reviewer may delete only their own still-draft review.
    # No one else can — protects the acknowledged audit trail from silent removal.
    if not (_is_admin(request.user) or (obj.status == "draft" and _is_reviewer(request, obj))):
        messages.error(request, "Only a tenant admin (or the reviewer, while draft) can delete this review.")
        return redirect("hrm:performancereview_detail", pk=obj.pk)
    return crud_delete(request, model=PerformanceReview, pk=pk, success_url="hrm:performancereview_list")


@login_required
@require_POST
def performancereview_submit(request, pk):
    obj = get_object_or_404(PerformanceReview, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == obj.reviewer_id)):
        raise PermissionDenied("Only the reviewer (or a tenant admin) can submit this review.")
    if obj.status == "draft":
        obj.status = "submitted"
        obj.submitted_at = timezone.now()
        # Snapshot the manager's rating at submission time (pre-calibration audit anchor).
        if obj.review_type == "manager" and obj.manager_rating is None:
            obj.manager_rating = obj.overall_rating
        obj.save(update_fields=["status", "submitted_at", "manager_rating", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Review {obj.number} submitted.")
    else:
        messages.error(request, "Only a draft review can be submitted.")
    return redirect("hrm:performancereview_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def performancereview_share(request, pk):
    obj = get_object_or_404(PerformanceReview, pk=pk, tenant=request.tenant)
    if obj.status == "submitted":
        obj.status = "shared"
        obj.shared_at = timezone.now()
        obj.save(update_fields=["status", "shared_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "share"})
        messages.success(request, f"Review {obj.number} shared with the employee.")
    else:
        messages.error(request, "Only a submitted review can be shared.")
    return redirect("hrm:performancereview_detail", pk=obj.pk)


@login_required
@require_POST
def performancereview_acknowledge(request, pk):
    obj = get_object_or_404(PerformanceReview, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if profile is None or profile.pk != obj.subject_id:
        raise PermissionDenied("Only the review subject can acknowledge their review.")
    if obj.status == "shared":
        obj.status = "acknowledged"
        obj.acknowledged_at = timezone.now()
        obj.acknowledged_by = profile
        obj.save(update_fields=["status", "acknowledged_at", "acknowledged_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "acknowledge"})
        messages.success(request, "Review acknowledged.")
    else:
        messages.error(request, "Only a shared review can be acknowledged.")
    return redirect("hrm:performancereview_detail", pk=obj.pk)


@tenant_admin_required
def performancereview_calibrate(request, pk):
    obj = get_object_or_404(
        PerformanceReview.objects.select_related("subject__party"), pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = CalibrationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, obj, "update", {"action": "calibrate"})
            messages.success(request, f"Calibration saved for {obj.number}.")
            return redirect("hrm:performancereview_detail", pk=obj.pk)
    else:
        form = CalibrationForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/performance/performancereview/calibrate.html", {
        "form": form, "obj": obj})


@tenant_admin_required
def calibration_board(request):
    """Report view (no model) — a cycle's manager reviews sorted by effective rating for
    side-by-side calibration. ?cycle=<id> selects the cycle."""
    cycles = ReviewCycle.objects.filter(tenant=request.tenant).order_by("-self_review_start")
    cycle = None
    reviews = []
    cycle_id = request.GET.get("cycle", "").strip()
    if cycle_id.isdigit():
        cycle = ReviewCycle.objects.filter(tenant=request.tenant, pk=int(cycle_id)).first()
    if cycle is None:
        cycle = cycles.first()
    if cycle is not None:
        reviews = list(PerformanceReview.objects.filter(
            tenant=request.tenant, cycle=cycle, review_type="manager")
            .select_related("subject__party", "reviewer__party")
            .prefetch_related("ratings"))
        # Sort by effective rating (calibrated-or-overall) desc; None ratings sort last.
        # BUG FIX: `ZERO` was referenced without a local definition or import — every review with
        # no ratings yet (effective_rating is None, the common state for a brand-new manager
        # review) raised NameError and 500'd this entire view.
        ZERO = Decimal("0")
        reviews.sort(key=lambda r: (r.effective_rating is None,
                                    -(r.effective_rating or ZERO)))
    return render(request, "hrm/performance/calibration_board.html", {
        "cycles": cycles, "cycle": cycle, "reviews": reviews})


# ------------------------------------------------------- ReviewRating (3.19.3 per-competency lines)
@login_required
def reviewrating_create(request, review_pk):
    review = get_object_or_404(PerformanceReview, pk=review_pk, tenant=request.tenant)
    if not _can_edit_review(request, review):
        messages.error(request, "Ratings can only be changed on a draft review, by the reviewer or a tenant admin.")
        return redirect("hrm:performancereview_detail", pk=review.pk)
    if request.method == "POST":
        form = ReviewRatingForm(request.POST,
                                instance=ReviewRating(tenant=request.tenant, review=review),
                                tenant=request.tenant)
        if form.is_valid():
            try:
                with transaction.atomic():
                    rating = form.save()
                write_audit_log(request.user, rating, "create")
                messages.success(request, "Rating added.")
            except IntegrityError:
                messages.error(request, "Could not add that rating.")
            return redirect("hrm:performancereview_detail", pk=review.pk)
    else:
        sibling_count = review.ratings.count()
        default_weight = (Decimal("100") / (sibling_count + 1)).quantize(Decimal("0.01"))
        form = ReviewRatingForm(instance=ReviewRating(tenant=request.tenant, review=review),
                                initial={"weight": default_weight}, tenant=request.tenant)
    return render(request, "hrm/performance/reviewrating/form.html", {
        "form": form, "is_edit": False, "review": review})


@login_required
def reviewrating_detail(request, pk):
    rating = get_object_or_404(
        ReviewRating.objects.select_related("review__subject__party", "review__reviewer__party"),
        pk=pk, tenant=request.tenant)
    review = rating.review
    # Confidentiality: a rating is viewable only by the review's subject, reviewer, or a tenant admin.
    if not _can_view_review(request, review):
        raise PermissionDenied("You do not have access to this rating.")
    return render(request, "hrm/performance/reviewrating/detail.html", {
        "obj": rating, "review": review, "can_edit": _can_edit_review(request, review)})


@login_required
def reviewrating_edit(request, pk):
    rating = get_object_or_404(ReviewRating.objects.select_related("review"), pk=pk, tenant=request.tenant)
    review = rating.review
    if not _can_edit_review(request, review):
        messages.error(request, "Ratings can only be changed on a draft review, by the reviewer or a tenant admin.")
        return redirect("hrm:performancereview_detail", pk=review.pk)
    if request.method == "POST":
        form = ReviewRatingForm(request.POST, instance=rating, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, rating, "update")
            messages.success(request, "Rating updated.")
            return redirect("hrm:performancereview_detail", pk=review.pk)
    else:
        form = ReviewRatingForm(instance=rating, tenant=request.tenant)
    return render(request, "hrm/performance/reviewrating/form.html", {
        "form": form, "is_edit": True, "obj": rating, "review": review})


@login_required
@require_POST
def reviewrating_delete(request, pk):
    rating = get_object_or_404(ReviewRating.objects.select_related("review"), pk=pk, tenant=request.tenant)
    review = rating.review
    if not _can_edit_review(request, review):
        messages.error(request, "Ratings can only be changed on a draft review, by the reviewer or a tenant admin.")
        return redirect("hrm:performancereview_detail", pk=review.pk)
    write_audit_log(request.user, rating, "delete")
    rating.delete()
    messages.success(request, "Rating deleted.")
    return redirect("hrm:performancereview_detail", pk=review.pk)


# =========================================================================
# 3.20 Continuous Feedback (Performance Management) — real-time feedback + 1:1
# meetings + a computed feedback dashboard. Reuses _current_employee_profile /
# _is_admin from the 3.19 section (never redefined). Confidentiality clones 3.19
# field-for-field: OneOnOneMeeting.manager_private_notes is manager-only (never
# rendered employee-side, and the edit form that holds it is manager/admin-gated,
# per L20), and an anonymous Feedback masks its giver on read for non-admin/
# non-giver viewers.
# =========================================================================
def _can_view_feedback(request, feedback):
    """Who may view a Feedback row: a tenant admin, the giver, or the receiver — plus ANY employee
    for a public-feed row (giver still masked if anonymous), or a team-mate sharing the receiver's
    org unit for a team-visibility row. Private rows are otherwise confidential (mirrors
    _can_view_review)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    if profile is not None and profile.pk in (feedback.giver_id, feedback.receiver_id):
        return True
    if feedback.visibility == "public":
        return True
    if feedback.visibility == "team" and profile is not None and profile.employment_id:
        recv = feedback.receiver
        recv_org = recv.employment.org_unit_id if recv.employment_id else None
        return recv_org is not None and recv_org == profile.employment.org_unit_id
    return False


def _visible_feedback_q(request):
    """A ``Q`` restricting feedback lists to what the requester may see: public rows OR their own
    given/received rows OR team-visible rows sharing the receiver's org unit. ``None`` for a tenant
    admin (no restriction) — same contract as _visible_reviews_q."""
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(visibility="public")  # a tenant-less/employee-less user sees only the public feed
    cond = Q(visibility="public") | Q(giver=profile) | Q(receiver=profile)
    org_id = profile.employment.org_unit_id if profile.employment_id else None
    if org_id is not None:
        cond |= Q(visibility="team", receiver__employment__org_unit_id=org_id)
    return cond


def _can_edit_feedback(request, feedback):
    """A Feedback row is editable ONLY by the giver (never the receiver) or a tenant admin, and only
    while it is still open (content locks once acknowledged, or once a request has been responded to)
    — mirrors _can_edit_review's status-lock-plus-author-check shape."""
    if feedback.status in ("acknowledged", "responded"):
        return False
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == feedback.giver_id


def _feedback_giver_display(request, feedback):
    """The giver name to render — 'Anonymous' for a non-admin/non-giver viewer of an anonymous row,
    else the real party name (or '—' when the giver FK is null)."""
    profile = _current_employee_profile(request)
    is_giver = profile is not None and profile.pk == feedback.giver_id
    if feedback.giver_anonymized and not (_is_admin(request.user) or is_giver):
        return "Anonymous"
    return feedback.giver.party.name if feedback.giver_id else "—"


def _can_view_meeting(request, meeting):
    """A 1:1 is inherently two-party — only its manager, its employee, or a tenant admin may view it."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk in (meeting.manager_id, meeting.employee_id)


def _visible_meetings_q(request):
    """A ``Q`` restricting the 1:1 list to the requester's own meetings (as manager or employee).
    ``None`` for a tenant admin (no restriction)."""
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(pk__in=[])
    return Q(manager=profile) | Q(employee=profile)


def _can_manage_meeting(request, meeting):
    """Manager-or-admin — for the complete/cancel/edit actions and the private-notes read gate. The
    employee side collaborates via action items + the shared read view but never reaches the edit
    form (which holds manager_private_notes)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == meeting.manager_id


def _can_manage_action_item(request, item):
    """Edit/delete/toggle an action item: an admin, or a MEETING PARTICIPANT (per _can_view_meeting)
    who is the item's owner or the meeting's manager. Requiring meeting access — not owner_id alone —
    closes the gap where an item assigned to an outsider would grant them mutate rights on a 1:1 they
    can't even view (edit rights must never be broader than view rights)."""
    if _is_admin(request.user):
        return True
    if not _can_view_meeting(request, item.meeting):
        return False
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk in (item.owner_id, item.meeting.manager_id)


# ------------------------------------------------------------ KudosBadge (3.20 recognition catalog)
@login_required
def kudosbadge_list(request):
    return crud_list(
        request,
        # Explicit order_by — the Count() GROUP BY otherwise drops Meta.ordering (paginator warning).
        KudosBadge.objects.filter(tenant=request.tenant)
        .annotate(num_feedback=Count("feedback_items")).order_by("name"),
        "hrm/performance/kudosbadge/list.html",
        search_fields=("name", "linked_value"),
        filters=[("is_active", "is_active", False)],
    )


@login_required
def kudosbadge_create(request):
    return crud_create(request, form_class=KudosBadgeForm,
                       template="hrm/performance/kudosbadge/form.html",
                       success_url="hrm:kudosbadge_list")


@login_required
def kudosbadge_detail(request, pk):
    obj = get_object_or_404(KudosBadge, pk=pk, tenant=request.tenant)
    # Confidentiality: a badge's award list must NOT leak private/team feedback recipients to an
    # outsider — filter the recent awards through the SAME visibility gate as feedback_list, so each
    # viewer sees only the badge-carrying feedback they're allowed to (public / own / team).
    recent_qs = obj.feedback_items.filter(tenant=request.tenant).select_related("receiver__party")
    vq = _visible_feedback_q(request)
    if vq is not None:
        recent_qs = recent_qs.filter(vq)
    recent = list(recent_qs.order_by("-created_at")[:10])
    return render(request, "hrm/performance/kudosbadge/detail.html",
                  {"obj": obj, "recent_feedback": recent})


@login_required
def kudosbadge_edit(request, pk):
    return crud_edit(request, model=KudosBadge, pk=pk, form_class=KudosBadgeForm,
                     template="hrm/performance/kudosbadge/form.html",
                     success_url="hrm:kudosbadge_list")


@login_required
@require_POST
def kudosbadge_delete(request, pk):
    return crud_delete(request, model=KudosBadge, pk=pk, success_url="hrm:kudosbadge_list")


# ------------------------------------------------------------ Feedback (3.20 real-time + request-pull)
@login_required
def feedback_list(request):
    qs = (Feedback.objects.filter(tenant=request.tenant)
          .select_related("giver__party", "receiver__party", "badge"))  # the list row only needs these
    vq = _visible_feedback_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    profile = _current_employee_profile(request)
    is_admin = _is_admin(request.user)
    # Given/received/requested cuts (mirror ?mine=1 on performancereview_list).
    if request.GET.get("given") == "1":
        qs = qs.filter(giver=profile) if profile is not None else qs.none()
    if request.GET.get("received") == "1":
        qs = qs.filter(receiver=profile) if profile is not None else qs.none()
    if request.GET.get("requested") == "1":
        qs = qs.filter(status="requested")
    if request.GET.get("is_anonymous") == "1":
        qs = qs.filter(is_anonymous=True)
    # Only an admin may search by giver name — otherwise a non-admin could correlate an anonymous
    # giver by searching their real name and seeing the masked row surface (an info leak).
    search = ["number", "message", "receiver__party__name"]
    if is_admin:
        search.append("giver__party__name")
    return crud_list(
        request, qs,
        "hrm/performance/feedback/list.html",
        search_fields=tuple(search),
        filters=[("feedback_type", "feedback_type", False), ("visibility", "visibility", False),
                 ("status", "status", False), ("receiver", "receiver_id", True),
                 ("badge", "badge_id", True)],
        extra_context={
            "feedback_type_choices": Feedback.FEEDBACK_TYPE_CHOICES,
            "visibility_choices": Feedback.VISIBILITY_CHOICES,
            "status_choices": Feedback.STATUS_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "badges": KudosBadge.objects.filter(tenant=request.tenant, is_active=True).order_by("name"),
            "is_admin": is_admin,
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def feedback_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    giver = _current_employee_profile(request)
    # Responding to a pull-request? ?respond_to=<pk> links the new row back at the 'requested' ask.
    respond_id = request.GET.get("respond_to") or request.POST.get("respond_to")
    respond_to = None
    if respond_id and str(respond_id).isdigit():
        respond_to = Feedback.objects.filter(
            tenant=request.tenant, pk=int(respond_id), status="requested").first()
        # Only the person who was ASKED (the request's receiver) — or an admin — may respond.
        if respond_to is not None and not _is_admin(request.user):
            if giver is None or giver.pk != respond_to.receiver_id:
                respond_to = None
    if request.method == "POST":
        form = FeedbackForm(request.POST, tenant=request.tenant, viewer_profile=giver)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.giver = giver
            if respond_to is not None:
                obj.requested_from = respond_to
                obj.status = "given"
            elif obj.feedback_type == "request":
                obj.status = "requested"
            else:
                obj.status = "given"
            # giver is set server-side (after form validation) — run the model's giver!=receiver guard.
            try:
                obj.clean()
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                obj.save()
                # Close the answered request so it can't be re-answered and drops out of the pending
                # "Requests" views — the response row carries the content forward via requested_from.
                if respond_to is not None and respond_to.status == "requested":
                    respond_to.status = "responded"
                    respond_to.save(update_fields=["status", "updated_at"])
                    write_audit_log(request.user, respond_to, "update", {"action": "responded"})
                write_audit_log(request.user, obj, "create")
                messages.success(request, f"Feedback {obj.number} created.")
                return redirect("hrm:feedback_detail", pk=obj.pk)
    else:
        initial = {}
        if respond_to is not None:
            initial = {"receiver": respond_to.giver_id, "feedback_type": "appreciation"}
        form = FeedbackForm(tenant=request.tenant, initial=initial, viewer_profile=giver)
    return render(request, "hrm/performance/feedback/form.html",
                  {"form": form, "is_edit": False, "respond_to": respond_to})


@login_required
def feedback_detail(request, pk):
    obj = get_object_or_404(
        Feedback.objects.select_related(
            "giver__party", "receiver__party", "badge", "related_objective",
            "related_review", "requested_from"),  # detail only shows related_review.number, not its subject
        pk=pk, tenant=request.tenant)
    if not _can_view_feedback(request, obj):
        raise PermissionDenied("You do not have access to this feedback.")
    profile = _current_employee_profile(request)
    is_receiver = profile is not None and profile.pk == obj.receiver_id
    is_giver = profile is not None and profile.pk == obj.giver_id
    return render(request, "hrm/performance/feedback/detail.html", {
        "obj": obj,
        "giver_display": _feedback_giver_display(request, obj),
        "can_edit": _can_edit_feedback(request, obj),
        "is_receiver": is_receiver,
        "is_giver": is_giver,
        # The recipient acknowledges given feedback; the person asked responds to a request.
        "can_acknowledge": is_receiver and obj.status == "given",
        "can_respond": is_receiver and obj.status == "requested",
    })


@login_required
def feedback_edit(request, pk):
    obj = get_object_or_404(Feedback, pk=pk, tenant=request.tenant)
    if not _can_edit_feedback(request, obj):
        messages.error(request, "Only the giver or a tenant admin can edit this feedback, and only before it is acknowledged.")
        return redirect("hrm:feedback_detail", pk=obj.pk)
    return crud_edit(request, model=Feedback, pk=pk, form_class=FeedbackForm,
                     template="hrm/performance/feedback/form.html",
                     success_url="hrm:feedback_list")


@login_required
@require_POST
def feedback_delete(request, pk):
    obj = get_object_or_404(Feedback, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    # A tenant admin may delete any; the giver may delete only their own, still-unacknowledged row.
    if not (_is_admin(request.user)
            or (obj.status != "acknowledged" and profile is not None and profile.pk == obj.giver_id)):
        messages.error(request, "Only a tenant admin (or the giver, before acknowledgement) can delete this feedback.")
        return redirect("hrm:feedback_detail", pk=obj.pk)
    return crud_delete(request, model=Feedback, pk=pk, success_url="hrm:feedback_list")


@login_required
@require_POST
def feedback_acknowledge(request, pk):
    obj = get_object_or_404(Feedback, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == obj.receiver_id)):
        raise PermissionDenied("Only the recipient can acknowledge this feedback.")
    if obj.status == "given":
        obj.status = "acknowledged"
        obj.acknowledged_at = timezone.now()
        obj.save(update_fields=["status", "acknowledged_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "acknowledge"})
        messages.success(request, f"Feedback {obj.number} acknowledged.")
    else:
        messages.error(request, "Only given feedback can be acknowledged.")
    return redirect("hrm:feedback_detail", pk=obj.pk)


@login_required
def feedback_respond(request, pk):
    """Turn a 'requested' ask into a response — a thin redirect to the create form pre-wired with
    ?respond_to=<pk> (the create view sets requested_from + status='given')."""
    ask = get_object_or_404(Feedback, pk=pk, tenant=request.tenant, status="requested")
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == ask.receiver_id)):
        raise PermissionDenied("Only the person asked can respond to this feedback request.")
    return redirect(f"{reverse('hrm:feedback_create')}?respond_to={ask.pk}")


@login_required
def feedback_dashboard(request):
    """Computed view (NO model) — a given/received/requested feedback summary for one employee, plus
    a per-type breakdown and a 30-day received-velocity count. Every employee sees their OWN
    dashboard; a tenant admin can view any via ?employee=<pk>. All ORM aggregation, no stored column
    (mirrors Objective.progress_pct / calibration_board)."""
    is_admin = _is_admin(request.user)
    target = _current_employee_profile(request)
    employees = None
    if is_admin:
        employees = (EmployeeProfile.objects.filter(tenant=request.tenant)
                     .select_related("party").order_by("party__name"))
        emp_id = request.GET.get("employee", "").strip()
        if emp_id.isdigit():
            target = (EmployeeProfile.objects.filter(tenant=request.tenant, pk=int(emp_id))
                      .select_related("party").first())
        elif target is None:
            target = employees.first()
    base = (Feedback.objects.filter(tenant=request.tenant)
            .select_related("giver__party", "receiver__party"))  # dashboard rows don't render the badge
    given = received = requested = []
    given_by_type = received_by_type = []
    given_count = received_count = requested_count = recent_30d_received = 0
    if target is not None:
        done = ("given", "acknowledged")
        given = list(base.filter(giver=target, status__in=done).order_by("-created_at")[:10])
        received = list(base.filter(receiver=target, status__in=done).order_by("-created_at")[:10])
        requested = list(base.filter(giver=target, status="requested").order_by("-created_at")[:10])
        type_labels = dict(Feedback.FEEDBACK_TYPE_CHOICES)
        given_by_type = [
            {"type": type_labels.get(r["feedback_type"], r["feedback_type"]), "count": r["c"]}
            for r in base.filter(giver=target, status__in=done)
            .values("feedback_type").annotate(c=Count("pk")).order_by("-c")]
        received_by_type = [
            {"type": type_labels.get(r["feedback_type"], r["feedback_type"]), "count": r["c"]}
            for r in base.filter(receiver=target, status__in=done)
            .values("feedback_type").annotate(c=Count("pk")).order_by("-c")]
        given_count = sum(x["count"] for x in given_by_type)
        received_count = sum(x["count"] for x in received_by_type)
        requested_count = base.filter(giver=target, status="requested").count()
        cutoff = timezone.now() - timedelta(days=30)
        recent_30d_received = base.filter(
            receiver=target, status__in=done, created_at__gte=cutoff).count()
    return render(request, "hrm/performance/feedback_dashboard.html", {
        "target": target,
        "employees": employees,
        "is_admin": is_admin,
        "given": given,
        "received": received,
        "requested": requested,
        "given_by_type": given_by_type,
        "received_by_type": received_by_type,
        "given_count": given_count,
        "received_count": received_count,
        "requested_count": requested_count,
        "recent_30d_received": recent_30d_received,
    })


# ------------------------------------------------------------ OneOnOneMeeting (3.20 1:1 meetings)
@login_required
def oneononemeeting_list(request):
    profile = _current_employee_profile(request)
    qs = (OneOnOneMeeting.objects.filter(tenant=request.tenant)
          .select_related("manager__party", "employee__party", "related_objective")
          .annotate(num_actions=Count("action_items")))
    vq = _visible_meetings_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    return crud_list(
        request,
        # Explicit order_by — the Count() GROUP BY otherwise drops Meta.ordering (paginator warning).
        qs.order_by("-scheduled_at"),
        "hrm/performance/oneononemeeting/list.html",
        search_fields=("number", "manager__party__name", "employee__party__name"),
        filters=[("status", "status", False), ("manager", "manager_id", True),
                 ("employee", "employee_id", True)],
        extra_context={
            "status_choices": OneOnOneMeeting.STATUS_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            # For gating the row manage buttons (edit/delete/complete/cancel) to the manager/admin.
            "is_admin": _is_admin(request.user),
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def oneononemeeting_create(request):
    return crud_create(request, form_class=OneOnOneMeetingForm,
                       template="hrm/performance/oneononemeeting/form.html",
                       success_url="hrm:oneononemeeting_list")


@login_required
def oneononemeeting_detail(request, pk):
    obj = get_object_or_404(
        OneOnOneMeeting.objects.select_related("manager__party", "employee__party", "related_objective"),
        pk=pk, tenant=request.tenant)
    if not _can_view_meeting(request, obj):
        raise PermissionDenied("You do not have access to this 1:1 meeting.")
    can_manage = _can_manage_meeting(request, obj)  # manager or admin
    action_items = list(obj.action_items.select_related("owner__party")
                        .order_by("status", "due_date", "description"))
    profile = _current_employee_profile(request)
    return render(request, "hrm/performance/oneononemeeting/detail.html", {
        "obj": obj,
        "show_private": can_manage,   # manager_private_notes block is gated on this
        "can_manage": can_manage,
        "action_items": action_items,
        "current_profile_id": profile.pk if profile is not None else None,
        "action_form": MeetingActionItemForm(tenant=request.tenant),
    })


@login_required
def oneononemeeting_edit(request, pk):
    obj = get_object_or_404(OneOnOneMeeting, pk=pk, tenant=request.tenant)
    # Manager/admin only — the edit form exposes manager_private_notes, so the employee must never
    # reach it (L20: masking the read view is not enough; keep the field's holder off the bound form
    # for anyone who shouldn't read it). The employee collaborates via action items + the read view.
    if not _can_manage_meeting(request, obj):
        messages.error(request, "Only the meeting's manager or a tenant admin can edit a 1:1.")
        return redirect("hrm:oneononemeeting_detail", pk=obj.pk)
    return crud_edit(request, model=OneOnOneMeeting, pk=pk, form_class=OneOnOneMeetingForm,
                     template="hrm/performance/oneononemeeting/form.html",
                     success_url="hrm:oneononemeeting_list")


@login_required
@require_POST
def oneononemeeting_delete(request, pk):
    obj = get_object_or_404(OneOnOneMeeting, pk=pk, tenant=request.tenant)
    if not _can_manage_meeting(request, obj):
        messages.error(request, "Only the meeting's manager or a tenant admin can delete a 1:1.")
        return redirect("hrm:oneononemeeting_detail", pk=obj.pk)
    return crud_delete(request, model=OneOnOneMeeting, pk=pk, success_url="hrm:oneononemeeting_list")


@login_required
@require_POST
def oneononemeeting_complete(request, pk):
    obj = get_object_or_404(OneOnOneMeeting, pk=pk, tenant=request.tenant)
    if not _can_manage_meeting(request, obj):
        raise PermissionDenied("Only the meeting's manager or a tenant admin can complete a 1:1.")
    if obj.status == "scheduled":
        obj.status = "completed"
        obj.completed_at = timezone.now()
        obj.save(update_fields=["status", "completed_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "complete"})
        messages.success(request, f"1:1 {obj.number} marked completed.")
    else:
        messages.error(request, "Only a scheduled 1:1 can be completed.")
    return redirect("hrm:oneononemeeting_detail", pk=obj.pk)


@login_required
@require_POST
def oneononemeeting_cancel(request, pk):
    obj = get_object_or_404(OneOnOneMeeting, pk=pk, tenant=request.tenant)
    if not _can_manage_meeting(request, obj):
        raise PermissionDenied("Only the meeting's manager or a tenant admin can cancel a 1:1.")
    if obj.status == "scheduled":
        obj.status = "cancelled"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"1:1 {obj.number} cancelled.")
    else:
        messages.error(request, "Only a scheduled 1:1 can be cancelled.")
    return redirect("hrm:oneononemeeting_detail", pk=obj.pk)


# ------------------------------------------------------------ MeetingActionItem (3.20 nested child)
@login_required
def meetingactionitem_create(request, meeting_pk):
    meeting = get_object_or_404(OneOnOneMeeting, pk=meeting_pk, tenant=request.tenant)
    if not _can_view_meeting(request, meeting):  # either party or admin may add an action item
        raise PermissionDenied("You do not have access to this 1:1 meeting.")
    if request.method == "POST":
        form = MeetingActionItemForm(
            request.POST, instance=MeetingActionItem(tenant=request.tenant, meeting=meeting),
            tenant=request.tenant)
        if form.is_valid():
            try:
                with transaction.atomic():
                    item = form.save()
                write_audit_log(request.user, item, "create")
                messages.success(request, "Action item added.")
            except IntegrityError:
                messages.error(request, "Could not add that action item.")
            return redirect("hrm:oneononemeeting_detail", pk=meeting.pk)
    else:
        form = MeetingActionItemForm(
            instance=MeetingActionItem(tenant=request.tenant, meeting=meeting), tenant=request.tenant)
    return render(request, "hrm/performance/meetingactionitem/form.html", {
        "form": form, "is_edit": False, "meeting": meeting})


@login_required
def meetingactionitem_detail(request, pk):
    item = get_object_or_404(
        MeetingActionItem.objects.select_related(
            "meeting__manager__party", "meeting__employee__party", "owner__party"),
        pk=pk, tenant=request.tenant)
    if not _can_view_meeting(request, item.meeting):
        raise PermissionDenied("You do not have access to this action item.")
    return render(request, "hrm/performance/meetingactionitem/detail.html", {
        "obj": item, "meeting": item.meeting,
        # Gate the Edit/Delete affordances to who can actually mutate it (owner/manager/admin).
        "can_manage": _can_manage_action_item(request, item),
    })


@login_required
def meetingactionitem_edit(request, pk):
    item = get_object_or_404(MeetingActionItem.objects.select_related("meeting"), pk=pk, tenant=request.tenant)
    if not _can_manage_action_item(request, item):
        raise PermissionDenied("Only the item's owner, the meeting's manager, or an admin can edit this action item.")
    if request.method == "POST":
        form = MeetingActionItemForm(request.POST, instance=item, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, item, "update")
            messages.success(request, "Action item updated.")
            return redirect("hrm:oneononemeeting_detail", pk=item.meeting_id)
    else:
        form = MeetingActionItemForm(instance=item, tenant=request.tenant)
    return render(request, "hrm/performance/meetingactionitem/form.html", {
        "form": form, "is_edit": True, "obj": item, "meeting": item.meeting})


@login_required
@require_POST
def meetingactionitem_delete(request, pk):
    item = get_object_or_404(MeetingActionItem.objects.select_related("meeting"), pk=pk, tenant=request.tenant)
    meeting = item.meeting
    if not _can_manage_action_item(request, item):
        messages.error(request, "Only the item's owner, the meeting's manager, or an admin can delete this action item.")
        return redirect("hrm:oneononemeeting_detail", pk=meeting.pk)
    write_audit_log(request.user, item, "delete")
    item.delete()
    messages.success(request, "Action item deleted.")
    return redirect("hrm:oneononemeeting_detail", pk=meeting.pk)


@login_required
@require_POST
def meetingactionitem_toggle(request, pk):
    item = get_object_or_404(MeetingActionItem.objects.select_related("meeting"), pk=pk, tenant=request.tenant)
    meeting = item.meeting
    # The item's owner, the meeting's manager, or an admin may flip its state.
    if not _can_manage_action_item(request, item):
        raise PermissionDenied("Only the owner, the meeting's manager, or an admin can update this action item.")
    if item.status == "open":
        item.status, item.completed_at = "done", timezone.now()
    else:
        item.status, item.completed_at = "open", None
    item.save(update_fields=["status", "completed_at", "updated_at"])
    write_audit_log(request.user, item, "update", {"action": "toggle", "to": item.status})
    messages.success(request, f"Action item marked {item.get_status_display().lower()}.")
    return redirect("hrm:oneononemeeting_detail", pk=meeting.pk)


# =========================================================================
# 3.21 Performance Improvement (Performance Management) — PIPs + progressive
# warning letters + manager-only coaching notes. The 4th/FINAL Performance-
# Management sub-module. Reuses _current_employee_profile / _is_admin from the
# 3.19 section. CONFIDENTIALITY is the crux: PIPs/warnings are subject-or-
# issuer-or-admin only (no team/public tier); CoachingNote is coach/admin ONLY
# — the coached employee is NEVER a viewer (the strictest gate in the cluster).
# =========================================================================
def _can_view_pip(request, pip):
    """A PIP is confidential — visible only to the subject, the owning manager, or a tenant admin
    (mirrors _can_view_review; NO team/public tier)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk in (pip.subject_id, pip.manager_id)


def _visible_pips_q(request):
    """A ``Q`` restricting PIP lists to the subject's or manager's own rows. ``None`` for a tenant admin."""
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(pk__in=[])
    return Q(subject=profile) | Q(manager=profile)


def _can_edit_pip(request, pip):
    """A PIP's content is editable ONLY by the manager or a tenant admin, and ONLY while it's a draft
    (locks once submitted for HR approval — protects the acknowledge/HR-approval audit trail). The
    subject is NEVER an editor (mirrors _can_edit_review)."""
    if pip.status != "draft":
        return False
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == pip.manager_id


def _can_view_warning(request, letter):
    """Visible only to the recipient, the issuer, or a tenant admin (subject-or-issuer-or-admin)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk in (letter.issued_to_id, letter.issued_by_id)


def _visible_warnings_q(request):
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(pk__in=[])
    return Q(issued_to=profile) | Q(issued_by=profile)


def _can_edit_warning(request, letter):
    """Editable only by the issuer or admin, only while draft (locks once issued). The recipient is
    never an editor."""
    if letter.status != "draft":
        return False
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == letter.issued_by_id


def _can_view_coaching(request, note):
    """THE STRICTEST GATE: a coaching note is visible ONLY to its coach (author) or a tenant admin —
    the coached ``employee`` is EXCLUDED at every stage (clones OneOnOneMeeting.manager_private_notes at
    the whole-model level)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == note.coach_id


def _visible_coaching_q(request):
    """A ``Q`` restricting coaching notes to the coach's own rows — the ``employee`` leg is DELIBERATELY
    omitted (the subject must never see notes about themselves). ``None`` for a tenant admin."""
    if _is_admin(request.user):
        return None
    profile = _current_employee_profile(request)
    if profile is None:
        return Q(pk__in=[])
    return Q(coach=profile)


def _can_edit_coaching(request, note):
    """Coach-or-admin only (edit rights never broader than view rights — the _can_manage_action_item
    lesson from 3.20)."""
    return _can_view_coaching(request, note)


# ------------------------------------------------------------ PerformanceImprovementPlan (3.21 PIPs)
@login_required
def pip_list(request):
    qs = (PerformanceImprovementPlan.objects.filter(tenant=request.tenant)
          .select_related("subject__party", "manager__party")
          .annotate(num_checkins=Count("checkins")))
    vq = _visible_pips_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    profile = _current_employee_profile(request)
    return crud_list(
        request,
        qs.order_by("-start_date", "number"),
        "hrm/performance/pip/list.html",
        search_fields=("number", "subject__party__name", "manager__party__name"),
        filters=[("status", "status", False), ("outcome", "outcome", False),
                 ("subject", "subject_id", True), ("manager", "manager_id", True)],
        extra_context={
            "status_choices": PerformanceImprovementPlan.STATUS_CHOICES,
            "outcome_choices": PerformanceImprovementPlan.OUTCOME_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "is_admin": _is_admin(request.user),
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def pip_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    profile = _current_employee_profile(request)
    if request.method == "POST":
        form = PerformanceImprovementPlanForm(request.POST, tenant=request.tenant, viewer_profile=profile, viewer_is_admin=_is_admin(request.user))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"PIP {obj.number} created.")
            return redirect("hrm:pip_detail", pk=obj.pk)
    else:
        form = PerformanceImprovementPlanForm(tenant=request.tenant, viewer_profile=profile, viewer_is_admin=_is_admin(request.user))
    return render(request, "hrm/performance/pip/form.html", {"form": form, "is_edit": False})


@login_required
def pip_detail(request, pk):
    obj = get_object_or_404(
        PerformanceImprovementPlan.objects.select_related(
            "subject__party", "manager__party", "triggering_review",
            "acknowledged_by__party", "hr_approved_by__party"),
        pk=pk, tenant=request.tenant)
    if not _can_view_pip(request, obj):
        raise PermissionDenied("You do not have access to this performance improvement plan.")
    checkins = list(obj.checkins.order_by("checkin_date"))
    profile = _current_employee_profile(request)
    is_admin = _is_admin(request.user)
    is_subject = profile is not None and profile.pk == obj.subject_id
    is_manager = profile is not None and profile.pk == obj.manager_id
    pip_open = obj.status != "closed"
    return render(request, "hrm/performance/pip/detail.html", {
        "obj": obj,
        "checkins": checkins,
        "can_edit": _can_edit_pip(request, obj),
        "is_admin": is_admin,
        "is_subject": is_subject,
        "is_manager": is_manager,
        # subject/manager/admin may LOG a check-in (open plan); only manager/admin may edit/delete one.
        "can_add_checkin": pip_open and _can_view_pip(request, obj),
        "can_manage_checkin": pip_open and (is_admin or is_manager),
        "checkin_form": PIPCheckInForm(tenant=request.tenant),
    })


@login_required
def pip_edit(request, pk):
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    if not _can_edit_pip(request, obj):
        messages.error(request, "Only the manager or a tenant admin can edit a PIP, and only while it is a draft.")
        return redirect("hrm:pip_detail", pk=obj.pk)
    return crud_edit(request, model=PerformanceImprovementPlan, pk=pk, form_class=PerformanceImprovementPlanForm,
                     template="hrm/performance/pip/form.html", success_url="hrm:pip_list")


@login_required
@require_POST
def pip_delete(request, pk):
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user)
            or (obj.status == "draft" and profile is not None and profile.pk == obj.manager_id)):
        messages.error(request, "Only a tenant admin (or the manager, while draft) can delete this PIP.")
        return redirect("hrm:pip_detail", pk=obj.pk)
    return crud_delete(request, model=PerformanceImprovementPlan, pk=pk, success_url="hrm:pip_list")


@login_required
@require_POST
def pip_submit(request, pk):
    """The manager submits a draft PIP for HR approval (draft -> pending_hr_approval)."""
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == obj.manager_id)):
        raise PermissionDenied("Only the manager (or a tenant admin) can submit this PIP.")
    if obj.status == "draft":
        obj.status = "pending_hr_approval"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"PIP {obj.number} submitted for HR approval.")
    else:
        messages.error(request, "Only a draft PIP can be submitted.")
    return redirect("hrm:pip_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def pip_hr_approve(request, pk):
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    if obj.status in ("draft", "pending_hr_approval"):
        obj.status = "active"
        obj.hr_approved_at = timezone.now()
        obj.hr_approved_by = _current_employee_profile(request)
        obj.save(update_fields=["status", "hr_approved_at", "hr_approved_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "hr_approve"})
        messages.success(request, f"PIP {obj.number} approved and activated.")
    else:
        messages.error(request, "Only a draft or pending PIP can be approved.")
    return redirect("hrm:pip_detail", pk=obj.pk)


@login_required
@require_POST
def pip_acknowledge(request, pk):
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == obj.subject_id)):
        raise PermissionDenied("Only the plan's subject can acknowledge it.")
    if obj.status == "active" and obj.acknowledged_at is None:
        obj.acknowledged_at = timezone.now()
        obj.acknowledged_by = profile
        obj.save(update_fields=["acknowledged_at", "acknowledged_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "acknowledge"})
        messages.success(request, "Plan acknowledged.")
    else:
        messages.error(request, "Only an active, not-yet-acknowledged plan can be acknowledged.")
    return redirect("hrm:pip_detail", pk=obj.pk)


@tenant_admin_required
def pip_close(request, pk):
    obj = get_object_or_404(
        PerformanceImprovementPlan.objects.select_related("subject__party"), pk=pk, tenant=request.tenant)
    if obj.status != "active":
        messages.error(request, "Only an active plan can be closed.")
        return redirect("hrm:pip_detail", pk=obj.pk)
    if request.method == "POST":
        obj.status = "closed"  # set before validation so the model's outcome-iff-closed clean() passes
        form = PIPCloseForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if not obj.outcome_date:
                obj.outcome_date = timezone.localdate()
            obj.save()
            write_audit_log(request.user, obj, "update", {"action": "close", "outcome": obj.outcome})
            messages.success(request, f"PIP {obj.number} closed ({obj.get_outcome_display()}).")
            return redirect("hrm:pip_detail", pk=obj.pk)
    else:
        form = PIPCloseForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/performance/pip/close.html", {"form": form, "obj": obj})


@tenant_admin_required
@require_POST
def pip_extend(request, pk):
    obj = get_object_or_404(PerformanceImprovementPlan, pk=pk, tenant=request.tenant)
    if obj.status != "active":
        messages.error(request, "Only an active plan can be extended.")
        return redirect("hrm:pip_detail", pk=obj.pk)
    raw = (request.POST.get("extended_end_date") or "").strip()
    try:
        parsed = _date.fromisoformat(raw) if raw else None
    except ValueError:
        parsed = None
    if parsed is None or parsed <= (obj.extended_end_date or obj.end_date):
        messages.error(request, "Enter a new end date later than the plan's current end date.")
        return redirect("hrm:pip_detail", pk=obj.pk)
    obj.extended_end_date = parsed
    obj.save(update_fields=["extended_end_date", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "extend", "to": str(parsed)})
    messages.success(request, f"PIP {obj.number} extended to {parsed}.")
    return redirect("hrm:pip_detail", pk=obj.pk)


def _can_edit_checkin(request, checkin):
    """Edit/delete a PIP check-in: the plan's manager or a tenant admin ONLY (the subject may LOG
    check-ins to self-report, but must never rewrite/delete the manager's entries — the check-in
    trail is the disciplinary record the outcome rests on), and only while the plan isn't closed."""
    pip = checkin.pip
    if pip.status == "closed":
        return False
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and profile.pk == pip.manager_id


# ------------------------------------------------------------ PIPCheckIn (nested under a PIP)
@login_required
def pipcheckin_create(request, pip_pk):
    pip = get_object_or_404(PerformanceImprovementPlan, pk=pip_pk, tenant=request.tenant)
    if not _can_view_pip(request, pip):   # subject/manager/admin may log a check-in
        raise PermissionDenied("You do not have access to this plan.")
    if pip.status == "closed":
        messages.error(request, "This plan is closed — check-ins can no longer be added.")
        return redirect("hrm:pip_detail", pk=pip.pk)
    if request.method == "POST":
        form = PIPCheckInForm(request.POST,
                              instance=PIPCheckIn(tenant=request.tenant, pip=pip), tenant=request.tenant)
        if form.is_valid():
            try:
                with transaction.atomic():
                    ci = form.save(commit=False)
                    ci.completed_at = timezone.now()  # a logged check-in records a held checkpoint
                    ci.save()
                write_audit_log(request.user, ci, "create")
                messages.success(request, "Check-in logged.")
            except IntegrityError:
                messages.error(request, "Could not log that check-in.")
            return redirect("hrm:pip_detail", pk=pip.pk)
    else:
        form = PIPCheckInForm(instance=PIPCheckIn(tenant=request.tenant, pip=pip), tenant=request.tenant)
    return render(request, "hrm/performance/pipcheckin/form.html", {"form": form, "is_edit": False, "pip": pip})


@login_required
def pipcheckin_detail(request, pk):
    item = get_object_or_404(
        PIPCheckIn.objects.select_related("pip__subject__party", "pip__manager__party"), pk=pk, tenant=request.tenant)
    if not _can_view_pip(request, item.pip):
        raise PermissionDenied("You do not have access to this check-in.")
    return render(request, "hrm/performance/pipcheckin/detail.html",
                  {"obj": item, "pip": item.pip, "can_manage_checkin": _can_edit_checkin(request, item)})


@login_required
def pipcheckin_edit(request, pk):
    item = get_object_or_404(PIPCheckIn.objects.select_related("pip"), pk=pk, tenant=request.tenant)
    if not _can_edit_checkin(request, item):
        messages.error(request, "Only the plan's manager or a tenant admin can edit a check-in, and not once the plan is closed.")
        return redirect("hrm:pip_detail", pk=item.pip_id)
    if request.method == "POST":
        form = PIPCheckInForm(request.POST, instance=item, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, item, "update")
            messages.success(request, "Check-in updated.")
            return redirect("hrm:pip_detail", pk=item.pip_id)
    else:
        form = PIPCheckInForm(instance=item, tenant=request.tenant)
    return render(request, "hrm/performance/pipcheckin/form.html",
                  {"form": form, "is_edit": True, "obj": item, "pip": item.pip})


@login_required
@require_POST
def pipcheckin_delete(request, pk):
    item = get_object_or_404(PIPCheckIn.objects.select_related("pip"), pk=pk, tenant=request.tenant)
    pip = item.pip
    if not _can_edit_checkin(request, item):
        messages.error(request, "Only the plan's manager or a tenant admin can delete a check-in, and not once the plan is closed.")
        return redirect("hrm:pip_detail", pk=pip.pk)
    write_audit_log(request.user, item, "delete")
    item.delete()
    messages.success(request, "Check-in deleted.")
    return redirect("hrm:pip_detail", pk=pip.pk)


# ------------------------------------------------------------ WarningLetter (3.21 progressive discipline)
@login_required
def warningletter_list(request):
    qs = (WarningLetter.objects.filter(tenant=request.tenant)
          .select_related("issued_to__party", "issued_by__party", "related_pip"))
    vq = _visible_warnings_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    profile = _current_employee_profile(request)
    return crud_list(
        request, qs.order_by("-incident_date", "number"),
        "hrm/performance/warningletter/list.html",
        search_fields=("number", "issued_to__party__name", "description"),
        filters=[("level", "level", False), ("category", "category", False),
                 ("status", "status", False), ("issued_to", "issued_to_id", True)],
        extra_context={
            "level_choices": WarningLetter.LEVEL_CHOICES,
            "category_choices": WarningLetter.CATEGORY_CHOICES,
            "status_choices": WarningLetter.STATUS_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "is_admin": _is_admin(request.user),
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def warningletter_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    profile = _current_employee_profile(request)
    if request.method == "POST":
        form = WarningLetterForm(request.POST, tenant=request.tenant, viewer_profile=profile, viewer_is_admin=_is_admin(request.user))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Warning letter {obj.number} created.")
            return redirect("hrm:warningletter_detail", pk=obj.pk)
    else:
        form = WarningLetterForm(tenant=request.tenant, viewer_profile=profile, viewer_is_admin=_is_admin(request.user))
    return render(request, "hrm/performance/warningletter/form.html", {"form": form, "is_edit": False})


@login_required
def warningletter_detail(request, pk):
    obj = get_object_or_404(
        WarningLetter.objects.select_related(
            "issued_to__party", "issued_by__party", "related_pip", "acknowledged_by__party"),
        pk=pk, tenant=request.tenant)
    if not _can_view_warning(request, obj):
        raise PermissionDenied("You do not have access to this warning letter.")
    # Prior-warnings escalation context, scoped to what THIS viewer may see (never the full history).
    # No select_related — the prior-warnings table renders only local fields (number/level/category/date).
    prior = obj.prior_warnings
    vq = _visible_warnings_q(request)
    if vq is not None:
        prior = prior.filter(vq)
    profile = _current_employee_profile(request)
    is_recipient = profile is not None and profile.pk == obj.issued_to_id
    return render(request, "hrm/performance/warningletter/detail.html", {
        "obj": obj,
        "prior_warnings": list(prior[:10]),
        "can_edit": _can_edit_warning(request, obj),
        "is_admin": _is_admin(request.user),
        "is_recipient": is_recipient,
        "can_acknowledge": is_recipient and obj.status == "issued",
        "ack_form": WarningAcknowledgeForm(tenant=request.tenant),
    })


@login_required
def warningletter_edit(request, pk):
    obj = get_object_or_404(WarningLetter, pk=pk, tenant=request.tenant)
    if not _can_edit_warning(request, obj):
        messages.error(request, "Only the issuer or a tenant admin can edit a warning letter, and only while it is a draft.")
        return redirect("hrm:warningletter_detail", pk=obj.pk)
    return crud_edit(request, model=WarningLetter, pk=pk, form_class=WarningLetterForm,
                     template="hrm/performance/warningletter/form.html", success_url="hrm:warningletter_list")


@login_required
@require_POST
def warningletter_delete(request, pk):
    obj = get_object_or_404(WarningLetter, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user)
            or (obj.status == "draft" and profile is not None and profile.pk == obj.issued_by_id)):
        messages.error(request, "Only a tenant admin (or the issuer, while draft) can delete this warning letter.")
        return redirect("hrm:warningletter_detail", pk=obj.pk)
    return crud_delete(request, model=WarningLetter, pk=pk, success_url="hrm:warningletter_list")


@tenant_admin_required
@require_POST
def warningletter_issue(request, pk):
    obj = get_object_or_404(WarningLetter, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "issued"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "issue"})
        messages.success(request, f"Warning letter {obj.number} issued.")
    else:
        messages.error(request, "Only a draft warning letter can be issued.")
    return redirect("hrm:warningletter_detail", pk=obj.pk)


@login_required
@require_POST
def warningletter_acknowledge(request, pk):
    obj = get_object_or_404(WarningLetter, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == obj.issued_to_id)):
        raise PermissionDenied("Only the recipient can acknowledge this warning letter.")
    if obj.status != "issued":
        messages.error(request, "Only an issued warning letter can be acknowledged.")
        return redirect("hrm:warningletter_detail", pk=obj.pk)
    form = WarningAcknowledgeForm(request.POST, instance=obj, tenant=request.tenant)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.status = "acknowledged"
        obj.acknowledged_at = timezone.now()
        obj.acknowledged_by = profile
        obj.save(update_fields=["employee_response", "status", "acknowledged_at", "acknowledged_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "acknowledge"})
        messages.success(request, "Warning letter acknowledged.")
    return redirect("hrm:warningletter_detail", pk=obj.pk)


@login_required
def warningletter_print(request, pk):
    obj = get_object_or_404(
        WarningLetter.objects.select_related("issued_to__party", "issued_by__party", "tenant", "related_pip"),
        pk=pk, tenant=request.tenant)
    if not _can_view_warning(request, obj):
        raise PermissionDenied("You do not have access to this warning letter.")
    return render(request, "hrm/performance/warningletter/print.html", {"obj": obj})


# ------------------------------------------------------------ CoachingNote (3.21 — coach/admin ONLY)
@login_required
def coachingnote_list(request):
    qs = (CoachingNote.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "coach__party", "related_pip"))
    vq = _visible_coaching_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    return crud_list(
        request, qs.order_by("-note_date", "-created_at"),
        "hrm/performance/coachingnote/list.html",
        search_fields=("number", "content", "employee__party__name"),
        filters=[("category", "category", False), ("employee", "employee_id", True)],
        extra_context={
            "category_choices": CoachingNote.CATEGORY_CHOICES,
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
        },
    )


@login_required
def coachingnote_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    coach = _current_employee_profile(request)
    if coach is None:
        messages.error(request, "Your account isn't linked to an employee profile, so you can't author a coaching note.")
        return redirect("hrm:coachingnote_list")
    if request.method == "POST":
        form = CoachingNoteForm(request.POST, tenant=request.tenant, viewer_profile=coach, viewer_is_admin=_is_admin(request.user))
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.coach = coach   # server-set — never form-typed (a user can't log a note as someone else)
            try:
                obj.clean()     # coach set server-side (after form validation) — run employee!=coach guard
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                obj.save()
                write_audit_log(request.user, obj, "create")
                messages.success(request, f"Coaching note {obj.number} logged.")
                return redirect("hrm:coachingnote_detail", pk=obj.pk)
    else:
        form = CoachingNoteForm(tenant=request.tenant, viewer_profile=coach, viewer_is_admin=_is_admin(request.user))
    return render(request, "hrm/performance/coachingnote/form.html", {"form": form, "is_edit": False})


@login_required
def coachingnote_detail(request, pk):
    obj = get_object_or_404(
        CoachingNote.objects.select_related("employee__party", "coach__party", "related_pip"),
        pk=pk, tenant=request.tenant)
    if not _can_view_coaching(request, obj):
        raise PermissionDenied("You do not have access to this coaching note.")
    return render(request, "hrm/performance/coachingnote/detail.html", {"obj": obj})


@login_required
def coachingnote_edit(request, pk):
    obj = get_object_or_404(CoachingNote, pk=pk, tenant=request.tenant)
    if not _can_edit_coaching(request, obj):
        messages.error(request, "Only the coach (author) or a tenant admin can edit this coaching note.")
        return redirect("hrm:coachingnote_detail", pk=obj.pk)
    return crud_edit(request, model=CoachingNote, pk=pk, form_class=CoachingNoteForm,
                     template="hrm/performance/coachingnote/form.html", success_url="hrm:coachingnote_list")


@login_required
@require_POST
def coachingnote_delete(request, pk):
    obj = get_object_or_404(CoachingNote, pk=pk, tenant=request.tenant)
    if not _can_edit_coaching(request, obj):
        messages.error(request, "Only the coach (author) or a tenant admin can delete this coaching note.")
        return redirect("hrm:coachingnote_detail", pk=obj.pk)
    return crud_delete(request, model=CoachingNote, pk=pk, success_url="hrm:coachingnote_list")


# ============================================================================
# 3.22 Training Management — the training catalog (TrainingCourse) + scheduled
# occurrences (TrainingSession) + a Training Calendar view. Ordinary tenant-scoped
# CRUD (no confidentiality gate). Reuses hrm.EmployeeProfile (instructor), core.Party
# (external vendor), accounting.Currency (cost). See models.py 3.22 section.
# ============================================================================

# ------------------------------------------------------------ TrainingCourse (3.22 Training Catalog)
@login_required
def trainingcourse_list(request):
    qs = (TrainingCourse.objects.filter(tenant=request.tenant)
          .select_related("prerequisite_course")
          .annotate(session_count=Count("sessions", distinct=True)))
    return crud_list(
        request, qs.order_by("title"),
        "hrm/training/trainingcourse/list.html",
        search_fields=("number", "title", "description"),
        filters=[("category", "category", False), ("provider_type", "provider_type", False),
                 ("delivery_mode", "delivery_mode", False), ("is_certification", "is_certification", False),
                 ("is_active", "is_active", False)],
        extra_context={
            "category_choices": TrainingCourse.CATEGORY_CHOICES,
            "provider_type_choices": TrainingCourse.PROVIDER_TYPE_CHOICES,
            "delivery_mode_choices": TrainingCourse.DELIVERY_MODE_CHOICES,
        },
    )


@login_required
def trainingcourse_create(request):
    return crud_create(request, form_class=TrainingCourseForm,
                       template="hrm/training/trainingcourse/form.html",
                       success_url="hrm:trainingcourse_list")


@login_required
def trainingcourse_detail(request, pk):
    obj = get_object_or_404(
        TrainingCourse.objects.select_related("prerequisite_course"), pk=pk, tenant=request.tenant)
    # The sessions sub-table shows the instructor (or external name), not the vendor — no external_vendor JOIN.
    sessions = (obj.sessions.select_related("instructor_employee__party")
                .order_by("-start_datetime")[:20])
    return render(request, "hrm/training/trainingcourse/detail.html", {
        "obj": obj,
        "sessions": sessions,
        "unlocks": obj.unlocks.order_by("title"),   # courses that require THIS one as a prerequisite
        "content_items": obj.content_items.all(),   # 3.23 LMS lessons (Meta-ordered by sequence)
    })


@login_required
def trainingcourse_edit(request, pk):
    return crud_edit(request, model=TrainingCourse, pk=pk, form_class=TrainingCourseForm,
                     template="hrm/training/trainingcourse/form.html", success_url="hrm:trainingcourse_list")


@login_required
@require_POST
def trainingcourse_delete(request, pk):
    obj = get_object_or_404(TrainingCourse, pk=pk, tenant=request.tenant)
    try:
        with transaction.atomic():
            write_audit_log(request.user, obj, "delete")
            obj.delete()
    except ProtectedError:
        # course is PROTECT-referenced by TrainingSession (3.22) AND by LearningPathItem / LearningProgress
        # (3.23) — name all three so the admin knows what to clear first, not just sessions.
        messages.error(request, "This course is referenced by training sessions, learning paths, learner "
                                 "progress, or certificates and can't be deleted. Remove those references first.")
        return redirect("hrm:trainingcourse_detail", pk=obj.pk)
    messages.success(request, "Deleted successfully.")
    return redirect("hrm:trainingcourse_list")


# ------------------------------------------------------------ TrainingSession (3.22 Classroom/Virtual/External)
@login_required
def trainingsession_list(request):
    # currency is only rendered on the detail page, not this list — keep it off the list JOIN.
    qs = (TrainingSession.objects.filter(tenant=request.tenant)
          .select_related("course", "instructor_employee__party", "external_vendor"))
    return crud_list(
        request, qs.order_by("-start_datetime", "number"),
        "hrm/training/trainingsession/list.html",
        search_fields=("number", "course__title", "venue_name", "instructor_employee__party__name",
                       "external_instructor_name", "external_vendor__name"),
        filters=[("status", "status", False), ("delivery_mode", "delivery_mode", False),
                 ("course", "course_id", True), ("instructor_employee", "instructor_employee_id", True)],
        extra_context={
            "status_choices": TrainingSession.STATUS_CHOICES,
            "delivery_mode_choices": TrainingSession.DELIVERY_MODE_CHOICES,
            "courses": TrainingCourse.objects.filter(tenant=request.tenant).order_by("title"),
            "instructors": (EmployeeProfile.objects.filter(tenant=request.tenant)
                            .select_related("party").order_by("party__name")),
        },
    )


@login_required
def trainingsession_create(request):
    return crud_create(request, form_class=TrainingSessionForm,
                       template="hrm/training/trainingsession/form.html",
                       success_url="hrm:trainingsession_list")


@login_required
def trainingsession_detail(request, pk):
    obj = get_object_or_404(
        TrainingSession.objects.select_related(
            "course", "instructor_employee__party", "external_vendor", "currency"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/training/trainingsession/detail.html", {
        "obj": obj,
        # 3.24 cross-touch — this session's nominations + attendance roster.
        "nominations": obj.nominations.select_related("employee__party").all(),
        "attendance": obj.attendance_records.select_related("employee__party").all(),
    })


@login_required
def trainingsession_edit(request, pk):
    return crud_edit(request, model=TrainingSession, pk=pk, form_class=TrainingSessionForm,
                     template="hrm/training/trainingsession/form.html", success_url="hrm:trainingsession_list")


@login_required
@require_POST
def trainingsession_delete(request, pk):
    obj = get_object_or_404(TrainingSession, pk=pk, tenant=request.tenant)
    try:
        with transaction.atomic():
            write_audit_log(request.user, obj, "delete")
            obj.delete()
    except ProtectedError:
        # 3.24 added TrainingNomination.session + TrainingAttendance.session as PROTECT children.
        messages.error(request, "This session has nominations or attendance records and can't be deleted. "
                                "Remove those first.")
        return redirect("hrm:trainingsession_detail", pk=obj.pk)
    messages.success(request, "Deleted successfully.")
    return redirect("hrm:trainingsession_list")


# ------------------------------------------------------------ Training Calendar (3.22 upcoming sessions)
@login_required
def training_calendar(request):
    """A date-grouped view over TrainingSession (the Training Calendar bullet). Defaults to the
    upcoming lens (from today) and never shows cancelled sessions; optional ?delivery_mode / ?status
    / ?from / ?to GET filters narrow it. Bounded by the date range — no pagination."""
    qs = (TrainingSession.objects.filter(tenant=request.tenant)
          .select_related("course", "instructor_employee__party")
          .exclude(status="cancelled"))
    mode = request.GET.get("delivery_mode", "").strip()
    status = request.GET.get("status", "").strip()
    if mode:
        qs = qs.filter(delivery_mode=mode)
    if status:
        qs = qs.filter(status=status)
    # ?from defaults to today (the "upcoming" lens); ?to is an optional upper bound.
    from_date = parse_date(request.GET.get("from", "").strip() or "") or timezone.localdate()
    to_date = parse_date(request.GET.get("to", "").strip() or "")
    qs = qs.filter(start_datetime__date__gte=from_date)
    if to_date:
        qs = qs.filter(start_datetime__date__lte=to_date)

    sessions_by_date = {}
    for s in qs.order_by("start_datetime", "number")[:200]:
        sessions_by_date.setdefault(timezone.localtime(s.start_datetime).date(), []).append(s)
    return render(request, "hrm/training/calendar.html", {
        "sessions_by_date": list(sessions_by_date.items()),   # [(date, [session, ...]), ...]
        "delivery_mode_choices": TrainingSession.DELIVERY_MODE_CHOICES,
        # The calendar unconditionally excludes cancelled sessions, so offering "Cancelled" as a
        # filter option would be a dead choice that always returns nothing — drop it from the dropdown.
        "status_choices": [(v, lbl) for v, lbl in TrainingSession.STATUS_CHOICES if v != "cancelled"],
        "from_date": from_date,
        "to_date": to_date,
    })


# ============================================================================
# 3.23 Learning Management (LMS) — self-paced digital learning on top of the 3.22
# TrainingCourse catalog: content items (lessons + light assessments), role-based
# learning paths, per-employee progress, a computed gamification leaderboard, and a
# manager team-progress rollup. Ordinary tenant-scoped CRUD (no confidentiality gate).
# ============================================================================

# ------------------------------------------------------------ LearningContentItem (3.23 Course Content)
@login_required
def learningcontentitem_create(request, course_pk):
    """Nested under a course (mirrors pipcheckin_create) — tenant+course set on the instance BEFORE
    validation, so no crud_create tenant-timing gotcha. Redirects to the course so the lesson shows."""
    course = get_object_or_404(TrainingCourse, pk=course_pk, tenant=request.tenant)
    if request.method == "POST":
        form = LearningContentItemForm(
            request.POST, request.FILES,
            instance=LearningContentItem(tenant=request.tenant, course=course), tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Content added.")
            return redirect("hrm:trainingcourse_detail", pk=course.pk)
    else:
        form = LearningContentItemForm(
            instance=LearningContentItem(tenant=request.tenant, course=course), tenant=request.tenant)
    return render(request, "hrm/lms/learningcontentitem/form.html",
                  {"form": form, "is_edit": False, "course": course})


@login_required
def learningcontentitem_list(request):
    qs = LearningContentItem.objects.filter(tenant=request.tenant).select_related("course")
    return crud_list(
        request, qs.order_by("course", "sequence"),
        "hrm/lms/learningcontentitem/list.html",
        search_fields=("title", "description", "course__title"),
        filters=[("content_type", "content_type", False), ("course", "course_id", True),
                 ("is_required", "is_required", False)],
        extra_context={
            "content_type_choices": LearningContentItem.CONTENT_TYPE_CHOICES,
            "courses": TrainingCourse.objects.filter(tenant=request.tenant).order_by("title"),
        },
    )


@login_required
def learningcontentitem_detail(request, pk):
    return crud_detail(request, model=LearningContentItem, pk=pk,
                       template="hrm/lms/learningcontentitem/detail.html", select_related=("course",))


@login_required
def learningcontentitem_edit(request, pk):
    return crud_edit(request, model=LearningContentItem, pk=pk, form_class=LearningContentItemForm,
                     template="hrm/lms/learningcontentitem/form.html",
                     success_url="hrm:learningcontentitem_list")


@login_required
@require_POST
def learningcontentitem_delete(request, pk):
    return crud_delete(request, model=LearningContentItem, pk=pk, success_url="hrm:learningcontentitem_list")


# ------------------------------------------------------------ LearningPath (3.23 Learning Paths)
@login_required
def learningpath_list(request):
    qs = (LearningPath.objects.filter(tenant=request.tenant)
          .select_related("target_designation", "target_department")
          .annotate(item_count=Count("items", distinct=True)))
    return crud_list(
        request, qs.order_by("title"),
        "hrm/lms/learningpath/list.html",
        search_fields=("number", "title", "description"),
        filters=[("is_mandatory", "is_mandatory", False), ("is_active", "is_active", False),
                 ("target_designation", "target_designation_id", True),
                 ("target_department", "target_department_id", True)],
        extra_context={
            "designations": Designation.objects.filter(tenant=request.tenant).order_by("name"),
            "departments": OrgUnit.objects.filter(tenant=request.tenant, kind="department").order_by("name"),
        },
    )


@login_required
def learningpath_create(request):
    return crud_create(request, form_class=LearningPathForm,
                       template="hrm/lms/learningpath/form.html", success_url="hrm:learningpath_list")


@login_required
def learningpath_detail(request, pk):
    obj = get_object_or_404(
        LearningPath.objects.select_related("target_designation", "target_department"),
        pk=pk, tenant=request.tenant)
    items = obj.items.select_related("course").order_by("sequence")
    return render(request, "hrm/lms/learningpath/detail.html", {"obj": obj, "items": items})


@login_required
def learningpath_edit(request, pk):
    return crud_edit(request, model=LearningPath, pk=pk, form_class=LearningPathForm,
                     template="hrm/lms/learningpath/form.html", success_url="hrm:learningpath_list")


@login_required
@require_POST
def learningpath_delete(request, pk):
    # LearningPathItem.path is CASCADE (items die with the path); LearningProgress.learning_path is
    # SET_NULL — so no ProtectedError concern here, plain crud_delete is safe.
    return crud_delete(request, model=LearningPath, pk=pk, success_url="hrm:learningpath_list")


# ------------------------------------------------------------ LearningPathItem (nested under a path)
@login_required
def learningpathitem_create(request, path_pk):
    path = get_object_or_404(LearningPath, pk=path_pk, tenant=request.tenant)
    if request.method == "POST":
        form = LearningPathItemForm(
            request.POST, instance=LearningPathItem(tenant=request.tenant, path=path), tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Course added to the path.")
            return redirect("hrm:learningpath_detail", pk=path.pk)
    else:
        form = LearningPathItemForm(
            instance=LearningPathItem(tenant=request.tenant, path=path), tenant=request.tenant)
    return render(request, "hrm/lms/learningpathitem/form.html",
                  {"form": form, "is_edit": False, "path": path})


@login_required
def learningpathitem_list(request):
    qs = LearningPathItem.objects.filter(tenant=request.tenant).select_related("path", "course")
    return crud_list(
        request, qs.order_by("path", "sequence"),
        "hrm/lms/learningpathitem/list.html",
        search_fields=("path__title", "course__title"),
        filters=[("path", "path_id", True), ("course", "course_id", True),
                 ("is_mandatory", "is_mandatory", False)],
        extra_context={
            "paths": LearningPath.objects.filter(tenant=request.tenant).order_by("title"),
            "courses": TrainingCourse.objects.filter(tenant=request.tenant).order_by("title"),
        },
    )


@login_required
def learningpathitem_detail(request, pk):
    # course__prerequisite_course: the detail template shows the course's prerequisite title (2nd FK hop).
    return crud_detail(request, model=LearningPathItem, pk=pk,
                       template="hrm/lms/learningpathitem/detail.html",
                       select_related=("path", "course", "course__prerequisite_course"))


@login_required
def learningpathitem_edit(request, pk):
    return crud_edit(request, model=LearningPathItem, pk=pk, form_class=LearningPathItemForm,
                     template="hrm/lms/learningpathitem/form.html", success_url="hrm:learningpathitem_list")


@login_required
@require_POST
def learningpathitem_delete(request, pk):
    item = get_object_or_404(LearningPathItem, pk=pk, tenant=request.tenant)
    path_id = item.path_id
    write_audit_log(request.user, item, "delete")
    item.delete()
    messages.success(request, "Course removed from the path.")
    return redirect("hrm:learningpath_detail", pk=path_id)


# ------------------------------------------------------------ LearningProgress (3.23 Progress Tracking)
@login_required
def learningprogress_list(request):
    qs = (LearningProgress.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "course", "learning_path"))
    return crud_list(
        request, qs.order_by("-updated_at"),
        "hrm/lms/learningprogress/list.html",
        search_fields=("employee__party__name", "course__title"),
        filters=[("status", "status", False), ("course", "course_id", True),
                 ("employee", "employee_id", True), ("learning_path", "learning_path_id", True)],
        extra_context={
            "status_choices": LearningProgress.STATUS_CHOICES,
            "courses": TrainingCourse.objects.filter(tenant=request.tenant).order_by("title"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "paths": LearningPath.objects.filter(tenant=request.tenant).order_by("title"),
        },
    )


@login_required
def learningprogress_create(request):
    return crud_create(request, form_class=LearningProgressForm,
                       template="hrm/lms/learningprogress/form.html", success_url="hrm:learningprogress_list")


@login_required
def learningprogress_detail(request, pk):
    return crud_detail(request, model=LearningProgress, pk=pk,
                       template="hrm/lms/learningprogress/detail.html",
                       select_related=("employee__party", "course", "learning_path"),
                       extra_context={"is_admin": _is_admin(request.user)})   # gate the admin-only Issue-Certificate


@login_required
def learningprogress_edit(request, pk):
    return crud_edit(request, model=LearningProgress, pk=pk, form_class=LearningProgressForm,
                     template="hrm/lms/learningprogress/form.html", success_url="hrm:learningprogress_list")


@login_required
@require_POST
def learningprogress_delete(request, pk):
    return crud_delete(request, model=LearningProgress, pk=pk, success_url="hrm:learningprogress_list")


# ------------------------------------------------------------ Gamification leaderboard (3.23, computed)
# Point thresholds -> level tier (a computed feature, no stored table). Lowest-first; the level is the
# highest threshold the learner's total points meet.
_LMS_LEVEL_THRESHOLDS = [(0, "Bronze"), (150, "Silver"), (400, "Gold"), (800, "Platinum")]


def _lms_level_for_points(points):
    level = _LMS_LEVEL_THRESHOLDS[0][1]
    for threshold, name in _LMS_LEVEL_THRESHOLDS:
        if points >= threshold:
            level = name
    return level


@login_required
def learning_leaderboard(request):
    """Gamification leaderboard — learners ranked by total points (summed over their LearningProgress),
    with a computed level tier. A DERIVED aggregate query, not a stored table."""
    rows = list(
        LearningProgress.objects.filter(tenant=request.tenant)
        .values("employee_id", "employee__party__name")
        .annotate(total_points=Sum("points_earned"),
                  courses_completed=Count("id", filter=Q(status="completed")),
                  courses_enrolled=Count("id"))
        .order_by("-total_points", "employee__party__name"))
    for i, row in enumerate(rows, start=1):
        row["rank"] = i
        row["level"] = _lms_level_for_points(row["total_points"] or 0)
    return render(request, "hrm/lms/leaderboard.html", {"leaderboard_rows": rows})


# ------------------------------------------------------------ Team progress rollup (3.23, manager view)
@login_required
def learning_team_progress(request):
    """Manager rollup — the logged-in manager's own + direct-reports' learning progress (reuses the
    3.18 goal-ownership reporting-line filter). Optional ?status=/?course= GET filters."""
    profile = _current_employee_profile(request)
    if profile is None:
        messages.error(request, "Your account isn't linked to an employee profile.")
        return redirect("dashboard:home")
    qs = (LearningProgress.objects.filter(tenant=request.tenant)
          .filter(Q(employee=profile) | Q(employee__employment__manager=profile.party))
          .select_related("employee__party", "course", "learning_path"))
    status = request.GET.get("status", "").strip()
    course = request.GET.get("course", "").strip()
    if status:
        qs = qs.filter(status=status)
    if course.isdigit():
        qs = qs.filter(course_id=int(course))
    qs = qs.order_by("employee__party__name", "course__title")
    rows = list(qs)
    summary = {
        "total": len(rows),
        "completed": sum(1 for r in rows if r.status == "completed"),
        "in_progress": sum(1 for r in rows if r.status == "in_progress"),
    }
    return render(request, "hrm/lms/team_progress.html", {
        "progress_rows": rows,
        "summary": summary,
        "status_choices": LearningProgress.STATUS_CHOICES,
        "courses": TrainingCourse.objects.filter(tenant=request.tenant).order_by("title"),
    })


# ============================================================================
# 3.24 Training Administration — nomination (+ approval workflow), attendance,
# post-training feedback, certificates, and a computed training-budget view. The
# operational layer over 3.22 sessions + 3.23 LMS progress. Ordinary tenant CRUD;
# nomination decisions mirror the LeaveRequest approve/reject manager gating.
# ============================================================================

# ------------------------------------------------------------ TrainingNomination (3.24 Nomination)
def _can_decide_nomination(request, obj):
    """A tenant admin OR the nominee's own manager may approve/reject (per the reporting line)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return bool(profile is not None and obj.employee.employment_id
                and obj.employee.employment.manager_id == profile.party_id)


@login_required
def trainingnomination_list(request):
    qs = (TrainingNomination.objects.filter(tenant=request.tenant)
          .select_related("session__course", "employee__party"))
    return crud_list(
        request, qs.order_by("-created_at"),
        "hrm/trainingadmin/trainingnomination/list.html",
        search_fields=("number", "session__course__title", "employee__party__name", "justification"),
        filters=[("status", "status", False), ("nomination_type", "nomination_type", False),
                 ("session", "session_id", True), ("employee", "employee_id", True)],
        extra_context={
            "status_choices": TrainingNomination.STATUS_CHOICES,
            "nomination_type_choices": TrainingNomination.NOMINATION_TYPE_CHOICES,
            "sessions": TrainingSession.objects.filter(tenant=request.tenant).select_related("course").order_by("-start_datetime"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
        },
    )


@login_required
def trainingnomination_create(request):
    return crud_create(request, form_class=TrainingNominationForm,
                       template="hrm/trainingadmin/trainingnomination/form.html",
                       success_url="hrm:trainingnomination_list")


@login_required
def trainingnomination_detail(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related(
            "session__course", "employee__party", "employee__employment", "nominated_by__party", "approver__party"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/trainingadmin/trainingnomination/detail.html", {
        "obj": obj, "can_decide": _can_decide_nomination(request, obj), "is_admin": _is_admin(request.user)})


@login_required
def trainingnomination_edit(request, pk):
    obj = get_object_or_404(TrainingNomination, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending nomination can be edited.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    return crud_edit(request, model=TrainingNomination, pk=pk, form_class=TrainingNominationForm,
                     template="hrm/trainingadmin/trainingnomination/form.html",
                     success_url="hrm:trainingnomination_list")


@login_required
@require_POST
def trainingnomination_delete(request, pk):
    obj = get_object_or_404(TrainingNomination, pk=pk, tenant=request.tenant)
    if obj.status in ("approved", "waitlisted"):
        messages.error(request, "A decided nomination can't be deleted — cancel or withdraw it instead.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    return crud_delete(request, model=TrainingNomination, pk=pk, success_url="hrm:trainingnomination_list")


@login_required
@require_POST
def trainingnomination_approve(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related("session__course", "employee__party", "employee__employment"),
        pk=pk, tenant=request.tenant)
    if not _can_decide_nomination(request, obj):
        messages.error(request, "Only a tenant admin or the nominee's manager can decide this nomination.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    if obj.status != "pending":
        messages.error(request, "Only a pending nomination can be approved.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    if not obj.session.is_full:
        obj.status = "approved"
    elif obj.session.waitlist_enabled:
        obj.status = "waitlisted"
        messages.info(request, "The session is full — the nominee was waitlisted.")
    else:
        messages.error(request, "The session is full and waitlisting is disabled.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    obj.approver = _current_employee_profile(request)
    obj.approved_at = timezone.now()
    obj.save(update_fields=["status", "approver", "approved_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "approve", "status": obj.status})
    messages.success(request, f"Nomination {obj.number} {obj.get_status_display().lower()}.")
    return redirect("hrm:trainingnomination_detail", pk=obj.pk)


@login_required
@require_POST
def trainingnomination_reject(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related("session__course", "employee__party", "employee__employment"),
        pk=pk, tenant=request.tenant)
    if not _can_decide_nomination(request, obj):
        messages.error(request, "Only a tenant admin or the nominee's manager can decide this nomination.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    if obj.status not in ("pending", "waitlisted"):
        messages.error(request, "Only a pending or waitlisted nomination can be rejected.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    obj.status = "rejected"
    obj.rejected_reason = request.POST.get("rejected_reason", "").strip()
    obj.approver = _current_employee_profile(request)
    obj.save(update_fields=["status", "rejected_reason", "approver", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Nomination {obj.number} rejected.")
    return redirect("hrm:trainingnomination_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def trainingnomination_waitlist(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related("session__course", "employee__party"),
        pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending nomination can be waitlisted.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    obj.status = "waitlisted"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "waitlist"})
    messages.success(request, f"Nomination {obj.number} waitlisted.")
    return redirect("hrm:trainingnomination_detail", pk=obj.pk)


@login_required
@require_POST
def trainingnomination_cancel(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related("session__course", "employee__party", "employee__employment"),
        pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    can_cancel = _can_decide_nomination(request, obj) or (
        profile is not None and obj.nominated_by_id == profile.pk)
    if not can_cancel:
        messages.error(request, "Only the nominator, the nominee's manager, or an admin can cancel this nomination.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    if obj.status not in ("pending", "approved", "waitlisted"):
        messages.error(request, "This nomination can't be cancelled in its current state.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    obj.status = "cancelled"
    obj.cancelled_reason = request.POST.get("cancelled_reason", "").strip()
    obj.save(update_fields=["status", "cancelled_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, f"Nomination {obj.number} cancelled.")
    return redirect("hrm:trainingnomination_detail", pk=obj.pk)


@login_required
@require_POST
def trainingnomination_withdraw(request, pk):
    obj = get_object_or_404(
        TrainingNomination.objects.select_related("session__course", "employee__party"),
        pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (profile is not None and profile.pk == obj.employee_id):
        messages.error(request, "Only the nominee can withdraw their own nomination.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    if obj.status not in ("pending", "approved", "waitlisted"):
        messages.error(request, "This nomination can't be withdrawn in its current state.")
        return redirect("hrm:trainingnomination_detail", pk=obj.pk)
    obj.status = "withdrawn"
    obj.cancelled_reason = request.POST.get("cancelled_reason", "").strip()
    obj.save(update_fields=["status", "cancelled_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "withdraw"})
    messages.success(request, f"Nomination {obj.number} withdrawn.")
    return redirect("hrm:trainingnomination_detail", pk=obj.pk)


# ------------------------------------------------------------ TrainingAttendance (3.24 Attendance)
@login_required
def trainingattendance_list(request):
    qs = (TrainingAttendance.objects.filter(tenant=request.tenant)
          .select_related("session__course", "employee__party"))
    return crud_list(
        request, qs.order_by("-session__start_datetime", "employee__party__name"),
        "hrm/trainingadmin/trainingattendance/list.html",
        search_fields=("session__course__title", "employee__party__name", "notes"),
        filters=[("attendance_status", "attendance_status", False),
                 ("completion_status", "completion_status", False),
                 ("session", "session_id", True), ("employee", "employee_id", True)],
        extra_context={
            "attendance_status_choices": TrainingAttendance.ATTENDANCE_STATUS_CHOICES,
            "completion_status_choices": TrainingAttendance.COMPLETION_STATUS_CHOICES,
            "sessions": TrainingSession.objects.filter(tenant=request.tenant).select_related("course").order_by("-start_datetime"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
        },
    )


@login_required
def trainingattendance_create(request):
    return crud_create(request, form_class=TrainingAttendanceForm,
                       template="hrm/trainingadmin/trainingattendance/form.html",
                       success_url="hrm:trainingattendance_list")


@login_required
def trainingattendance_detail(request, pk):
    obj = get_object_or_404(
        TrainingAttendance.objects.select_related("session__course", "employee__party", "nomination"),
        pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    return render(request, "hrm/trainingadmin/trainingattendance/detail.html", {
        "obj": obj, "is_admin": _is_admin(request.user),
        "current_profile_id": profile.pk if profile is not None else None,
        "feedback": obj.feedback.first()})


@login_required
def trainingattendance_edit(request, pk):
    return crud_edit(request, model=TrainingAttendance, pk=pk, form_class=TrainingAttendanceForm,
                     template="hrm/trainingadmin/trainingattendance/form.html",
                     success_url="hrm:trainingattendance_list")


@login_required
@require_POST
def trainingattendance_delete(request, pk):
    obj = get_object_or_404(TrainingAttendance, pk=pk, tenant=request.tenant)
    # Deleting would CASCADE its feedback and orphan (SET_NULL) any issued certificate — block it.
    if obj.feedback.exists() or obj.certificates_issued.exists():
        messages.error(request, "This attendance record has feedback or a certificate linked — remove those first.")
        return redirect("hrm:trainingattendance_detail", pk=obj.pk)
    return crud_delete(request, model=TrainingAttendance, pk=pk, success_url="hrm:trainingattendance_list")


# ------------------------------------------------------------ TrainingFeedback (3.24 Training Feedback)
def _can_manage_feedback(request, feedback):
    """The attendee (the giver) OR a tenant admin — mirrors 3.20 _can_edit_feedback (giver/admin).
    Without this, any tenant user could edit/delete or unmask anyone's feedback."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return bool(profile is not None and profile.pk == feedback.attendance.employee_id)


@login_required
def trainingfeedback_create(request, attendance_pk):
    """Nested under an attendance record. The form's (tenant, attendance) duplicate guard queries the
    DB directly, so setting instance.attendance before validation is enough."""
    attendance = get_object_or_404(
        TrainingAttendance.objects.select_related("session__course", "employee__party"),
        pk=attendance_pk, tenant=request.tenant)
    # Only the attendee (or an admin) may leave feedback for their own attendance.
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == attendance.employee_id)):
        messages.error(request, "Only the attendee or a tenant admin can leave feedback for this attendance.")
        return redirect("hrm:trainingattendance_detail", pk=attendance.pk)
    if request.method == "POST":
        form = TrainingFeedbackForm(
            request.POST, instance=TrainingFeedback(tenant=request.tenant, attendance=attendance),
            tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Feedback submitted.")
            return redirect("hrm:trainingattendance_detail", pk=attendance.pk)
    else:
        form = TrainingFeedbackForm(
            instance=TrainingFeedback(tenant=request.tenant, attendance=attendance), tenant=request.tenant)
    return render(request, "hrm/trainingadmin/trainingfeedback/form.html",
                  {"form": form, "is_edit": False, "attendance": attendance})


@login_required
def trainingfeedback_list(request):
    qs = (TrainingFeedback.objects.filter(tenant=request.tenant)
          .select_related("attendance__session__course", "attendance__employee__party"))
    profile = _current_employee_profile(request)
    return crud_list(
        request, qs.order_by("-created_at"),
        "hrm/trainingadmin/trainingfeedback/list.html",
        search_fields=("attendance__session__course__title", "comments"),
        filters=[("would_recommend", "would_recommend", False), ("session", "attendance__session_id", True)],
        extra_context={
            "sessions": TrainingSession.objects.filter(tenant=request.tenant).select_related("course").order_by("-start_datetime"),
            "is_admin": _is_admin(request.user),
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def trainingfeedback_detail(request, pk):
    profile = _current_employee_profile(request)
    return crud_detail(request, model=TrainingFeedback, pk=pk,
                       template="hrm/trainingadmin/trainingfeedback/detail.html",
                       select_related=("attendance__session__course", "attendance__employee__party"),
                       extra_context={"is_admin": _is_admin(request.user),
                                      "current_profile_id": profile.pk if profile is not None else None})


@login_required
def trainingfeedback_edit(request, pk):
    obj = get_object_or_404(TrainingFeedback.objects.select_related("attendance"), pk=pk, tenant=request.tenant)
    if not _can_manage_feedback(request, obj):
        messages.error(request, "Only the attendee or a tenant admin can edit this feedback.")
        return redirect("hrm:trainingfeedback_detail", pk=obj.pk)
    return crud_edit(request, model=TrainingFeedback, pk=pk, form_class=TrainingFeedbackForm,
                     template="hrm/trainingadmin/trainingfeedback/form.html",
                     success_url="hrm:trainingfeedback_list")


@login_required
@require_POST
def trainingfeedback_delete(request, pk):
    obj = get_object_or_404(TrainingFeedback.objects.select_related("attendance"), pk=pk, tenant=request.tenant)
    if not _can_manage_feedback(request, obj):
        messages.error(request, "Only the attendee or a tenant admin can delete this feedback.")
        return redirect("hrm:trainingfeedback_detail", pk=obj.pk)
    return crud_delete(request, model=TrainingFeedback, pk=pk, success_url="hrm:trainingfeedback_list")


# ------------------------------------------------------------ TrainingCertificate (3.24 Certificates)
@login_required
def trainingcertificate_list(request):
    qs = (TrainingCertificate.objects.filter(tenant=request.tenant)
          .select_related("employee__party", "course"))
    return crud_list(
        request, qs.order_by("-issued_on"),
        "hrm/trainingadmin/trainingcertificate/list.html",
        search_fields=("number", "title", "verification_code", "employee__party__name", "course__title"),
        filters=[("status", "status", False), ("course", "course_id", True), ("employee", "employee_id", True)],
        extra_context={
            "status_choices": TrainingCertificate.STATUS_CHOICES,
            "courses": TrainingCourse.objects.filter(tenant=request.tenant, is_certification=True).order_by("title"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "is_admin": _is_admin(request.user),   # gate the admin-only Issue/Edit/Delete buttons
        },
    )


# Issuing/editing a certificate mints/alters a real credential — tenant-admin only (revoke already is).
# An employee must not be able to self-mark a completed attendance and self-issue a verifiable cert.
@tenant_admin_required
def trainingcertificate_create(request):
    return crud_create(request, form_class=TrainingCertificateForm,
                       template="hrm/trainingadmin/trainingcertificate/form.html",
                       success_url="hrm:trainingcertificate_list")


def _issue_certificate(request, *, employee_id, course, source_attendance=None, source_progress=None):
    """Shared body for the two 'issue from ...' convenience routes — pre-fills the form and saves."""
    initial = {"employee": employee_id, "course": course.pk, "issued_on": timezone.localdate(),
               "title": course.certification_name or course.title}
    if source_attendance is not None:
        initial["source_attendance"] = source_attendance.pk
    if source_progress is not None:
        initial["source_progress"] = source_progress.pk
    if request.method == "POST":
        form = TrainingCertificateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Certificate {obj.number} issued.")
            return redirect("hrm:trainingcertificate_detail", pk=obj.pk)
    else:
        form = TrainingCertificateForm(initial=initial, tenant=request.tenant)
    return render(request, "hrm/trainingadmin/trainingcertificate/form.html",
                  {"form": form, "is_edit": False})


@tenant_admin_required
def trainingcertificate_issue_from_attendance(request, attendance_pk):
    att = get_object_or_404(
        TrainingAttendance.objects.select_related("session__course"), pk=attendance_pk, tenant=request.tenant)
    if att.completion_status != "completed" or not att.session.course.is_certification:
        messages.error(request, "A certificate can only be issued from a completed session on a certification course.")
        return redirect("hrm:trainingattendance_detail", pk=att.pk)
    existing = att.certificates_issued.first()
    if existing is not None:
        messages.info(request, "A certificate has already been issued from this attendance record.")
        return redirect("hrm:trainingcertificate_detail", pk=existing.pk)
    return _issue_certificate(request, employee_id=att.employee_id, course=att.session.course,
                              source_attendance=att)


@tenant_admin_required
def trainingcertificate_issue_from_progress(request, progress_pk):
    prog = get_object_or_404(
        LearningProgress.objects.select_related("course"), pk=progress_pk, tenant=request.tenant)
    if prog.status != "completed" or not prog.course.is_certification:
        messages.error(request, "A certificate can only be issued from completed progress on a certification course.")
        return redirect("hrm:learningprogress_detail", pk=prog.pk)
    existing = prog.certificates_issued.first()
    if existing is not None:
        messages.info(request, "A certificate has already been issued from this progress record.")
        return redirect("hrm:trainingcertificate_detail", pk=existing.pk)
    return _issue_certificate(request, employee_id=prog.employee_id, course=prog.course,
                              source_progress=prog)


@login_required
def trainingcertificate_detail(request, pk):
    return crud_detail(request, model=TrainingCertificate, pk=pk,
                       template="hrm/trainingadmin/trainingcertificate/detail.html",
                       select_related=("employee__party", "course", "source_attendance__session", "source_progress"),
                       extra_context={"is_admin": _is_admin(request.user)})


@tenant_admin_required
def trainingcertificate_edit(request, pk):
    obj = get_object_or_404(TrainingCertificate, pk=pk, tenant=request.tenant)
    if obj.status == "revoked":
        messages.error(request, "A revoked certificate can't be edited.")
        return redirect("hrm:trainingcertificate_detail", pk=obj.pk)
    return crud_edit(request, model=TrainingCertificate, pk=pk, form_class=TrainingCertificateForm,
                     template="hrm/trainingadmin/trainingcertificate/form.html",
                     success_url="hrm:trainingcertificate_list")


@tenant_admin_required
@require_POST
def trainingcertificate_delete(request, pk):
    obj = get_object_or_404(TrainingCertificate, pk=pk, tenant=request.tenant)
    if obj.status == "issued":
        messages.error(request, "An issued certificate can't be deleted — revoke it instead.")
        return redirect("hrm:trainingcertificate_detail", pk=obj.pk)
    return crud_delete(request, model=TrainingCertificate, pk=pk, success_url="hrm:trainingcertificate_list")


@tenant_admin_required
@require_POST
def trainingcertificate_revoke(request, pk):
    obj = get_object_or_404(
        TrainingCertificate.objects.select_related("employee__party"), pk=pk, tenant=request.tenant)
    if obj.status != "issued":
        messages.error(request, "Only an issued certificate can be revoked.")
        return redirect("hrm:trainingcertificate_detail", pk=obj.pk)
    obj.status = "revoked"
    obj.revoked_reason = request.POST.get("revoked_reason", "").strip()
    obj.save(update_fields=["status", "revoked_reason", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "revoke"})
    messages.success(request, f"Certificate {obj.number} revoked.")
    return redirect("hrm:trainingcertificate_detail", pk=obj.pk)


@login_required
def trainingcertificate_print(request, pk):
    obj = get_object_or_404(
        TrainingCertificate.objects.select_related("employee__party", "course", "tenant"),
        pk=pk, tenant=request.tenant)
    return render(request, "hrm/trainingadmin/trainingcertificate/print.html", {"obj": obj})


# ------------------------------------------------------------ Training Budget (3.24, computed view)
@login_required
def training_budget(request):
    """Computed training-cost view (no model) — the year's training spend (estimated vs actual, and
    by course) vs the allocated cost-center budget for that year. Aggregates over TrainingSession
    costs (3.22) + CostCenterProfile.budget_annual (3.2)."""
    tenant = request.tenant
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", "") or today.year)
    except (TypeError, ValueError):
        year = today.year
    years = sorted({d.year for d in TrainingSession.objects.filter(tenant=tenant).dates("start_datetime", "year")},
                   reverse=True)
    if today.year not in years:
        years = sorted(set(years + [today.year]), reverse=True)

    sessions = TrainingSession.objects.filter(tenant=tenant, start_datetime__year=year)
    totals = sessions.aggregate(estimated=Sum("estimated_cost"), actual=Sum("actual_cost"))
    allocated = (CostCenterProfile.objects.filter(tenant=tenant, budget_year=year)
                 .aggregate(total=Sum("budget_annual"))["total"]) or Decimal("0")
    by_course = list(sessions.values("course__title")
                     .annotate(sessions=Count("id"), estimated=Sum("estimated_cost"), actual=Sum("actual_cost"))
                     .order_by("-actual"))
    total_actual = totals["actual"] or Decimal("0")
    utilization = round(float(total_actual) / float(allocated) * 100, 1) if allocated else None
    return render(request, "hrm/trainingadmin/budget.html", {
        "year": year, "years": years,
        "total_estimated": totals["estimated"] or Decimal("0"),
        "total_actual": total_actual,
        "total_allocated": allocated,
        "utilization": utilization,
        "by_course": by_course,
    })


# ============================================================ 3.25 Personal Information (Self-Service)
# The Employee Self-Service layer over EmployeeProfile: a "my info" hub the employee edits directly
# (address/personal email/mobile/photo), three CHILD tables (emergency contacts / bank accounts /
# family members) with admin CRUD + per-employee self-scoping, and a maker-checker change-request
# workflow for the sensitive fields. Reuses the existing _current_employee_profile / _is_admin
# helpers. Direct self-edit: emergency contacts + the my_info contact fields. Admin-gated writes:
# bank accounts + family members (an employee proposes those via a change request only).

def _require_own_profile(request):
    """Resolve the requester's own EmployeeProfile, or return ``(None, redirect)`` for a user with no
    linked employee record (e.g. the superuser) — the ESS hub pages only make sense with a profile."""
    profile = _current_employee_profile(request)
    if profile is None:
        messages.error(request,
                        "Your account isn't linked to an employee record, so there's no personal info to show.")
        return None, redirect("hrm:hrm_overview")
    return profile, None


def _can_manage_own_child(request, obj):
    """A self-service row (emergency contact / bank account / family member / change request) is
    manageable by a tenant admin or by the employee who owns it (mirrors _can_edit_review's shape)."""
    if _is_admin(request.user):
        return True
    profile = _current_employee_profile(request)
    return profile is not None and obj.employee_id == profile.pk


def _ss_scope(request, qs):
    """Restrict a self-service queryset: an admin sees the whole tenant; a plain employee sees only
    their own rows; an employee-less user sees nothing."""
    if _is_admin(request.user):
        return qs
    profile = _current_employee_profile(request)
    if profile is None:
        return qs.none()
    return qs.filter(employee=profile)


def _ss_employees(request):
    """The tenant's employee dropdown for the admin filter/picker (party-joined, name-ordered)."""
    return (EmployeeProfile.objects.filter(tenant=request.tenant)
            .select_related("party").order_by("party__name"))


def _is_own_change_request(request, obj):
    """Maker-checker separation: the acting user is the MAKER (submitted it) or the SUBJECT (their own
    record), so they must NOT also be the CHECKER who approves/rejects it."""
    if obj.requested_by_id and obj.requested_by_id == request.user.id:
        return True
    profile = _current_employee_profile(request)
    return profile is not None and obj.employee_id == profile.pk


# ---------------------------------------------------------------- My Info hub (Profile/Contact)
@login_required
def my_info(request):
    """The employee's self-service landing page: read-only employment context, the direct-edit
    contact fields, the masked sensitive fields (each with a 'Request a Change' link), roster
    summaries, and the requester's recent change requests."""
    profile, redirect_resp = _require_own_profile(request)
    if redirect_resp:
        return redirect_resp
    # Employment.manager is a FK straight to core.Party (not EmployeeProfile), so the path stops at
    # employment__manager — and the profile.manager property returns that Party (use .name, not .party.name).
    profile = (EmployeeProfile.objects
               .select_related("party", "designation",
                               "employment__org_unit", "employment__manager")
               .get(pk=profile.pk))
    return render(request, "hrm/selfservice/my_info.html", {
        "profile": profile,
        "emergency_contacts": list(profile.emergency_contacts.all()[:3]),
        "bank_accounts": list(profile.bank_accounts.all()[:3]),
        "family_members": list(profile.family_members.all()[:3]),
        # The hub's mini-list renders only number/type/status/date — no FK columns, so no join needed.
        "my_requests": list(profile.info_change_requests.all()[:5]),
    })


@login_required
def my_info_edit(request):
    """Direct-edit the non-sensitive contact subset (address / personal email / mobile / photo)."""
    profile, redirect_resp = _require_own_profile(request)
    if redirect_resp:
        return redirect_resp
    if request.method == "POST":
        form = EmployeeProfileMyInfoForm(request.POST, request.FILES, instance=profile, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", {"action": "self_update_contact"})
            messages.success(request, "Your contact information was updated.")
            return redirect("hrm:my_info")
    else:
        form = EmployeeProfileMyInfoForm(instance=profile, tenant=request.tenant)
    return render(request, "hrm/selfservice/my_info_edit.html",
                  {"form": form, "profile": profile, "is_edit": True})


# ---------------------------------------------------------------- Shared self-service child CRUD
def _ss_child_create(request, form_class, template, list_url):
    """Create a self-service child row: a non-admin creates for THEMSELVES; an admin may target
    ``?employee=<id>`` (GET) or ``employee_pk`` (POST). Mirrors _employee_child_create."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    is_admin = _is_admin(request.user)
    own = _current_employee_profile(request)
    target = own
    if is_admin:
        emp_pk = (request.GET.get("employee", "") or request.POST.get("employee_pk", "")).strip()
        if emp_pk.isdigit():
            target = EmployeeProfile.objects.filter(tenant=request.tenant, pk=int(emp_pk)).first() or own
    if target is None:
        messages.error(request, "Select an employee to attach this record to.")
        return redirect(list_url)
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.employee = target
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Created successfully.")
            return redirect(list_url)
    else:
        form = form_class(tenant=request.tenant)
    return render(request, template, {
        "form": form, "is_edit": False, "is_admin": is_admin,
        "target_employee": target, "employees": _ss_employees(request) if is_admin else None,
    })


def _ss_child_edit(request, model, pk, form_class, template, detail_url):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only edit your own records.")
        return redirect(detail_url, pk=obj.pk)
    if request.method == "POST":
        form = form_class(request.POST, request.FILES, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            # changes=_changed(form) redacts account_number (etc.) per _SENSITIVE_AUDIT_FIELDS.
            write_audit_log(request.user, obj, "update", changes=_changed(form))
            messages.success(request, "Updated successfully.")
            return redirect(detail_url, pk=obj.pk)
    else:
        form = form_class(instance=obj, tenant=request.tenant)
    return render(request, template, {
        "form": form, "obj": obj, "is_edit": True, "is_admin": _is_admin(request.user),
        "target_employee": obj.employee, "employees": None,
    })


def _ss_child_detail(request, model, pk, template, select_related=()):
    qs = model.objects.filter(tenant=request.tenant)
    if select_related:
        qs = qs.select_related(*select_related)
    obj = get_object_or_404(qs, pk=pk)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This record belongs to another employee.")
    # `is_own` lets a detail template hide review actions on the viewer's OWN row (e.g. the 3.26
    # self-approval guard: an admin can't approve/reject their own request). Harmless extra context
    # for the 3.25 child templates, which don't reference it.
    profile = _current_employee_profile(request)
    is_own = profile is not None and obj.employee_id == profile.pk
    return render(request, template,
                  {"obj": obj, "is_admin": _is_admin(request.user), "is_own": is_own})


def _ss_child_delete(request, model, pk, list_url):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only delete your own records.")
        return redirect(list_url)
    if request.method == "POST":
        # A GenericForeignKey gives no referential integrity on the TARGET row's deletion, so a
        # pending change request pointing at this row would be left dangling (unapprovable). Auto-cancel
        # any such request so nothing is silently orphaned (a no-op for EmergencyContact — never a target).
        ct = ContentType.objects.get_for_model(model)
        cancelled = EmployeeInfoChangeRequest.objects.filter(
            tenant=obj.tenant, content_type=ct, object_id=obj.pk, status="pending"
        ).update(status="cancelled", decision_note="Auto-cancelled: the target record was deleted.")
        write_audit_log(request.user, obj, "delete")
        obj.delete()
        msg = "Deleted successfully."
        if cancelled:
            msg += f" {cancelled} pending change request(s) targeting it were cancelled."
        messages.success(request, msg)
    return redirect(list_url)


# ---------------------------------------------------------------- Emergency Contacts (direct self-edit)
@login_required
def emergencycontact_list(request):
    qs = _ss_scope(request, EmergencyContact.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin}
    filters = [("is_primary", "is_primary", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/selfservice/emergencycontact/list.html",
                     search_fields=("name", "relationship", "phone", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def emergencycontact_create(request):
    return _ss_child_create(request, EmergencyContactForm,
                            "hrm/selfservice/emergencycontact/form.html", "hrm:emergencycontact_list")


@login_required
def emergencycontact_detail(request, pk):
    return _ss_child_detail(request, EmergencyContact, pk,
                            "hrm/selfservice/emergencycontact/detail.html", select_related=("employee__party",))


@login_required
def emergencycontact_edit(request, pk):
    return _ss_child_edit(request, EmergencyContact, pk, EmergencyContactForm,
                          "hrm/selfservice/emergencycontact/form.html", "hrm:emergencycontact_detail")


@login_required
@require_POST
def emergencycontact_delete(request, pk):
    return _ss_child_delete(request, EmergencyContact, pk, "hrm:emergencycontact_list")


# ---------------------------------------------------------------- Bank Accounts (admin-gated writes)
@login_required
def employeebankaccount_list(request):
    qs = _ss_scope(request, EmployeeBankAccount.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "verification_status_choices": EmployeeBankAccount.VERIFICATION_STATUS_CHOICES,
             "account_type_choices": EmployeeBankAccount.ACCOUNT_TYPE_CHOICES,
             "status_choices": EmployeeBankAccount.STATUS_CHOICES}
    filters = [("verification_status", "verification_status", False),
               ("account_type", "account_type", False),
               ("status", "status", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/selfservice/employeebankaccount/list.html",
                     search_fields=("bank_name", "account_holder_name", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def employeebankaccount_detail(request, pk):
    return _ss_child_detail(request, EmployeeBankAccount, pk,
                            "hrm/selfservice/employeebankaccount/detail.html", select_related=("employee__party",))


@tenant_admin_required
def employeebankaccount_create(request):
    return _ss_child_create(request, EmployeeBankAccountForm,
                            "hrm/selfservice/employeebankaccount/form.html", "hrm:employeebankaccount_list")


@tenant_admin_required
def employeebankaccount_edit(request, pk):
    return _ss_child_edit(request, EmployeeBankAccount, pk, EmployeeBankAccountForm,
                          "hrm/selfservice/employeebankaccount/form.html", "hrm:employeebankaccount_detail")


@tenant_admin_required
@require_POST
def employeebankaccount_delete(request, pk):
    return _ss_child_delete(request, EmployeeBankAccount, pk, "hrm:employeebankaccount_list")


@tenant_admin_required
@require_POST
def employeebankaccount_verify(request, pk):
    obj = get_object_or_404(EmployeeBankAccount, pk=pk, tenant=request.tenant)
    if obj.verification_status == "pending":
        obj.verification_status = "verified"
        obj.save(update_fields=["verification_status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "verify"})
        messages.success(request, "Bank account verified.")
    else:
        messages.error(request, "Only a pending account can be verified.")
    return redirect("hrm:employeebankaccount_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def employeebankaccount_reject(request, pk):
    obj = get_object_or_404(EmployeeBankAccount, pk=pk, tenant=request.tenant)
    if obj.verification_status in ("pending", "verified"):
        obj.verification_status = "rejected"
        obj.save(update_fields=["verification_status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, "Bank account rejected.")
    else:
        messages.error(request, "This account is already rejected.")
    return redirect("hrm:employeebankaccount_detail", pk=obj.pk)


# ---------------------------------------------------------------- Family Members (admin-gated writes)
@login_required
def familymember_list(request):
    qs = _ss_scope(request, FamilyMember.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin, "relationship_choices": FamilyMember.RELATIONSHIP_CHOICES}
    filters = [("relationship", "relationship", False), ("is_dependent", "is_dependent", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/selfservice/familymember/list.html",
                     search_fields=("name", "occupation", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def familymember_detail(request, pk):
    return _ss_child_detail(request, FamilyMember, pk,
                            "hrm/selfservice/familymember/detail.html", select_related=("employee__party",))


@tenant_admin_required
def familymember_create(request):
    return _ss_child_create(request, FamilyMemberForm,
                            "hrm/selfservice/familymember/form.html", "hrm:familymember_list")


@tenant_admin_required
def familymember_edit(request, pk):
    return _ss_child_edit(request, FamilyMember, pk, FamilyMemberForm,
                          "hrm/selfservice/familymember/form.html", "hrm:familymember_detail")


@tenant_admin_required
@require_POST
def familymember_delete(request, pk):
    return _ss_child_delete(request, FamilyMember, pk, "hrm:familymember_list")


# ---------------------------------------------------------------- Change Requests (maker-checker)
_CHANGE_FORMS = {"profile_field": ProfileFieldChangeForm, "bank": BankAccountChangeForm,
                 "family": FamilyMemberChangeForm}
_BANK_CR_FIELDS = ["bank_name", "account_holder_name", "account_number", "routing_number",
                   "account_type", "split_percentage"]
_FAMILY_CR_FIELDS = ["name", "relationship", "date_of_birth", "gender", "occupation", "phone",
                     "is_dependent", "is_minor", "guardian_name", "guardian_relationship",
                     "is_nominee", "nominee_percentage"]


def _assemble_change_request(request, employee, req_type, form):
    """Build (unsaved) an EmployeeInfoChangeRequest from a validated sub-form: resolve
    content_type/object_id server-side (never trusting the client) and snapshot the old→new
    field_changes JSON."""
    cd = form.cleaned_data
    cr = EmployeeInfoChangeRequest(tenant=request.tenant, employee=employee, request_type=req_type,
                                   reason=cd.get("reason", ""), requested_by=request.user)
    if req_type == "profile_field":
        field = cd["field_name"]
        old = employee.party.name if field == "legal_name" else getattr(employee, field, None)
        cr.content_type = ContentType.objects.get_for_model(EmployeeProfile)
        cr.object_id = employee.pk
        cr.field_changes = {field: {"old": _json_safe(old), "new": _json_safe(cd["new_value"])}}
    else:
        existing = cd.get("existing_account") if req_type == "bank" else cd.get("existing_member")
        model = EmployeeBankAccount if req_type == "bank" else FamilyMember
        fields = _BANK_CR_FIELDS if req_type == "bank" else _FAMILY_CR_FIELDS
        cr.content_type = ContentType.objects.get_for_model(model)
        cr.object_id = existing.pk if existing else None
        cr.field_changes = {
            f: {"old": _json_safe(getattr(existing, f, None)) if existing else None,
                "new": _json_safe(cd.get(f))}
            for f in fields
        }
    return cr


# Change-request diff keys whose raw value must be masked when rendered (the field_changes JSON stores
# the plaintext account/routing number; every other surface uses masked_account_number()).
_SENSITIVE_DIFF_FIELDS = frozenset({"account_number", "routing_number"})


def _mask_diff_value(field, value):
    if value and field in _SENSITIVE_DIFF_FIELDS:
        return EmployeeBankAccount._mask_last4(value)
    return value


def _resolve_cr_employee(request, is_admin, own):
    """Resolve the subject employee for a change request: admins may target ?employee/employee_pk,
    everyone else is forced to themselves."""
    if is_admin:
        emp_pk = (request.GET.get("employee", "") or request.POST.get("employee_pk", "")).strip()
        if emp_pk.isdigit():
            return EmployeeProfile.objects.filter(tenant=request.tenant, pk=int(emp_pk)).first() or own
    return own


@login_required
def changerequest_list(request):
    # The list renders only obj.employee.party.name (admin col) + local fields — requested_by/
    # reviewed_by are shown on the detail page, not here.
    qs = _ss_scope(request, EmployeeInfoChangeRequest.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "status_choices": EmployeeInfoChangeRequest.STATUS_CHOICES,
             "request_type_choices": EmployeeInfoChangeRequest.REQUEST_TYPE_CHOICES}
    filters = [("status", "status", False), ("request_type", "request_type", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/selfservice/changerequest/list.html",
                     search_fields=("number", "employee__party__name", "reason"),
                     filters=filters, extra_context=extra)


@login_required
def changerequest_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    is_admin = _is_admin(request.user)
    own = _current_employee_profile(request)
    employee = _resolve_cr_employee(request, is_admin, own)
    if employee is None:
        messages.error(request, "No employee record to raise a change request against.")
        return redirect("hrm:changerequest_list")

    req_type = (request.POST.get("request_type") or request.GET.get("type") or "profile_field").strip()
    if req_type not in _CHANGE_FORMS:
        req_type = "profile_field"

    def build(data=None):
        if req_type == "profile_field":
            initial = None
            if data is None:
                fld = request.GET.get("field", "").strip()
                if fld in EmployeeInfoChangeRequest.SENSITIVE_PROFILE_FIELDS:
                    initial = {"field_name": fld}
            return ProfileFieldChangeForm(data, initial=initial)
        return _CHANGE_FORMS[req_type](data, employee=employee, tenant=request.tenant)

    if request.method == "POST":
        form = build(request.POST)
        if form.is_valid():
            cr = _assemble_change_request(request, employee, req_type, form)
            try:
                cr.clean()  # anti-tamper safety net (own-record only); number is set in save()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                cr.save()
                write_audit_log(request.user, cr, "create")
                messages.success(request, f"Change request {cr.number} submitted for review.")
                return redirect("hrm:changerequest_detail", pk=cr.pk)
    else:
        form = build()
    return render(request, "hrm/selfservice/changerequest/form.html", {
        "form": form, "is_edit": False, "request_type": req_type, "employee": employee,
        "is_admin": is_admin,
        "request_type_choices": EmployeeInfoChangeRequest.REQUEST_TYPE_CHOICES,
        "employees": _ss_employees(request) if is_admin else None,
    })


@login_required
def changerequest_detail(request, pk):
    obj = get_object_or_404(
        EmployeeInfoChangeRequest.objects.select_related(
            "employee__party", "requested_by", "reviewed_by", "content_type"),
        pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This change request belongs to another employee.")
    diffs = [{"field": k.replace("_", " ").title(),
              "old": _mask_diff_value(k, (v or {}).get("old")),
              "new": _mask_diff_value(k, (v or {}).get("new"))}
             for k, v in (obj.field_changes or {}).items()]
    return render(request, "hrm/selfservice/changerequest/detail.html", {
        "obj": obj, "diffs": diffs, "is_admin": _is_admin(request.user),
        "can_manage": _can_manage_own_child(request, obj),
        # Maker-checker: an admin who is the maker/subject may NOT review their own request, so the
        # Approve/Reject controls are hidden for them (the view would bounce them anyway).
        "is_own": _is_own_change_request(request, obj),
    })


@login_required
def changerequest_edit(request, pk):
    obj = get_object_or_404(EmployeeInfoChangeRequest, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only edit your own requests.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    if obj.status != "pending":
        messages.error(request, "Only a pending change request can be edited.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    req_type, employee = obj.request_type, obj.employee

    # Pre-fill the sub-form from the stored proposal (the "new" values).
    if req_type == "profile_field":
        (fname, change), = (obj.field_changes or {"": {}}).items()
        initial = {"field_name": fname, "new_value": (change or {}).get("new"), "reason": obj.reason}
    else:
        initial = {k: (v or {}).get("new") for k, v in (obj.field_changes or {}).items()}
        initial["reason"] = obj.reason
        if obj.object_id:
            initial["existing_account" if req_type == "bank" else "existing_member"] = obj.object_id

    def build(data=None):
        if req_type == "profile_field":
            return ProfileFieldChangeForm(data, initial=None if data else initial)
        return _CHANGE_FORMS[req_type](data, initial=None if data else initial,
                                       employee=employee, tenant=request.tenant)

    if request.method == "POST":
        form = build(request.POST)
        if form.is_valid():
            rebuilt = _assemble_change_request(request, employee, req_type, form)
            try:
                rebuilt.clean()
            except ValidationError as exc:
                messages.error(request, "; ".join(exc.messages))
            else:
                obj.field_changes = rebuilt.field_changes
                obj.content_type = rebuilt.content_type
                obj.object_id = rebuilt.object_id
                obj.reason = rebuilt.reason
                obj.save(update_fields=["field_changes", "content_type", "object_id", "reason", "updated_at"])
                write_audit_log(request.user, obj, "update")
                messages.success(request, "Change request updated.")
                return redirect("hrm:changerequest_detail", pk=obj.pk)
    else:
        form = build()
    return render(request, "hrm/selfservice/changerequest/form.html", {
        "form": form, "is_edit": True, "obj": obj, "request_type": req_type, "employee": employee,
        "is_admin": _is_admin(request.user),
        "request_type_choices": EmployeeInfoChangeRequest.REQUEST_TYPE_CHOICES, "employees": None,
    })


@login_required
@require_POST
def changerequest_delete(request, pk):
    obj = get_object_or_404(EmployeeInfoChangeRequest, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only delete your own requests.")
        return redirect("hrm:changerequest_list")
    if obj.status != "pending":
        messages.error(request, "Only a pending change request can be deleted.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Change request deleted.")
    return redirect("hrm:changerequest_list")


@login_required
@require_POST
def changerequest_cancel(request, pk):
    obj = get_object_or_404(EmployeeInfoChangeRequest, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only cancel your own requests.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    if obj.status != "pending":
        messages.error(request, "Only a pending change request can be cancelled.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    obj.status = "cancelled"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "cancel"})
    messages.success(request, "Change request cancelled.")
    return redirect("hrm:changerequest_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def changerequest_approve(request, pk):
    # select_related so apply() doesn't re-fetch self.employee / .party for the legal_name write.
    obj = get_object_or_404(
        EmployeeInfoChangeRequest.objects.select_related("employee__party", "content_type"),
        pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending change request can be approved.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    if _is_own_change_request(request, obj):
        messages.error(request, "You can't review your own change request — another admin must approve or reject it.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    try:
        obj.apply(request.user)
    except ValidationError as exc:
        messages.error(request, f"Could not apply this change: {'; '.join(exc.messages)}")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    write_audit_log(request.user, obj, "update", {"action": "approve"})
    messages.success(request, f"Change request {obj.number} approved and applied.")
    return redirect("hrm:changerequest_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def changerequest_reject(request, pk):
    obj = get_object_or_404(EmployeeInfoChangeRequest, pk=pk, tenant=request.tenant)
    if obj.status != "pending":
        messages.error(request, "Only a pending change request can be rejected.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    if _is_own_change_request(request, obj):
        messages.error(request, "You can't review your own change request — another admin must approve or reject it.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    note = (request.POST.get("decision_note") or "").strip()
    if not note:
        messages.error(request, "A reason is required to reject a change request.")
        return redirect("hrm:changerequest_detail", pk=obj.pk)
    obj.status = "rejected"
    obj.decision_note = note
    obj.reviewed_by = request.user
    obj.reviewed_at = timezone.now()
    obj.save(update_fields=["status", "decision_note", "reviewed_by", "reviewed_at", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "reject"})
    messages.success(request, f"Change request {obj.number} rejected.")
    return redirect("hrm:changerequest_detail", pk=obj.pk)


# =============================================================================================
# 3.26 Request Management (Self-Service)
# =============================================================================================
# The employee-facing request portal. THREE new request types — DocumentRequest / IdCardRequest /
# AssetRequest — each on the draft -> pending -> approved/rejected/cancelled (+ fulfillment tail)
# lifecycle, reusing the shared self-service helpers verbatim (_ss_child_create/_edit/_detail/_delete,
# _ss_scope, _ss_employees, _can_manage_own_child, _require_own_profile). The other two 3.26 bullets
# (Leave Requests, Attendance Regularization) reuse the existing 3.10/3.9 views; the My Requests hub
# links to all five. A 3.26-only _is_own_hr_request guard blocks self-approval (mirrors 3.25's
# _is_own_change_request); reject requires a decision_note.
from .models import (  # noqa: E402  — 3.26 Request Management (Self-Service)
    AssetRequest,
    DocumentRequest,
    IdCardRequest,
)
from .forms import (  # noqa: E402  — 3.26 Request Management (Self-Service)
    AssetRequestForm,
    DocumentFulfillForm,
    DocumentRequestForm,
    IdCardRequestForm,
)


def _is_own_hr_request(request, obj):
    """3.26 self-approval guard: the acting user is the request's SUBMITTER (the `employee`), so
    they must NOT also be the approver/rejecter — a different admin must review it. `employee` IS
    the submitter on all three request models, so there's no separate requested_by leg to check."""
    profile = _current_employee_profile(request)
    return profile is not None and obj.employee_id == profile.pk


# ---- Shared workflow helpers (used by all three 3.26 request models) ------------------------
def _hr_request_submit(request, model, pk, detail_url):
    """draft -> pending, gated to the owning employee or an admin (stricter than the older
    leaverequest_submit, which has no ownership gate — 3.26 follows the 3.25 _can_manage_own_child
    convention)."""
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only submit your own requests.")
        return redirect(detail_url, pk=obj.pk)
    if obj.status == "draft":
        obj.status = "pending"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Request {obj.number} submitted for approval.")
    else:
        messages.error(request, "Only a draft request can be submitted.")
    return redirect(detail_url, pk=obj.pk)


def _hr_request_cancel(request, model, pk, detail_url):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only cancel your own requests.")
        return redirect(detail_url, pk=obj.pk)
    if obj.status in obj.OPEN_STATUSES:
        obj.status = "cancelled"
        obj.decision_note = (request.POST.get("decision_note") or "").strip()[:2000]
        obj.save(update_fields=["status", "decision_note", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "cancel"})
        messages.success(request, f"Request {obj.number} cancelled.")
    else:
        messages.error(request, "Only a draft or pending request can be cancelled.")
    return redirect(detail_url, pk=obj.pk)


def _hr_request_approve(request, model, pk, detail_url):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if _is_own_hr_request(request, obj):
        messages.error(request, "You can't approve your own request — another admin must review it.")
        return redirect(detail_url, pk=obj.pk)
    if obj.status == "pending":
        obj.status = "approved"
        obj.approver = request.user
        obj.approved_at = timezone.now()
        obj.save(update_fields=["status", "approver", "approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "approve"})
        messages.success(request, f"Request {obj.number} approved.")
    else:
        messages.error(request, "Only a pending request can be approved.")
    return redirect(detail_url, pk=obj.pk)


def _hr_request_reject(request, model, pk, detail_url):
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if _is_own_hr_request(request, obj):
        messages.error(request, "You can't reject your own request — another admin must review it.")
        return redirect(detail_url, pk=obj.pk)
    note = (request.POST.get("decision_note") or "").strip()
    if not note:
        messages.error(request, "A reason is required to reject a request.")
        return redirect(detail_url, pk=obj.pk)
    if obj.status == "pending":
        obj.status = "rejected"
        obj.decision_note = note[:2000]
        obj.approver = request.user
        obj.approved_at = timezone.now()
        obj.save(update_fields=["status", "decision_note", "approver", "approved_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "reject"})
        messages.success(request, f"Request {obj.number} rejected.")
    else:
        messages.error(request, "Only a pending request can be rejected.")
    return redirect(detail_url, pk=obj.pk)


def _hr_request_edit(request, model, pk, form_class, template, detail_url):
    """Edit only while OPEN (draft/pending) — a decided request is locked — then delegate to the
    shared ownership-gated _ss_child_edit. Ownership is checked BEFORE the status branch so a
    non-owner can't read another employee's request state off the differing flash message."""
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only edit your own records.")
        return redirect(detail_url, pk=obj.pk)
    if obj.status not in obj.OPEN_STATUSES:
        messages.error(request, "A decided request can no longer be edited.")
        return redirect(detail_url, pk=obj.pk)
    return _ss_child_edit(request, model, pk, form_class, template, detail_url)


def _hr_request_delete(request, model, pk, list_url):
    """Delete only a still-open request (a decided/closed row is preserved for the audit trail).
    Ownership is checked BEFORE the status branch so a non-owner can't read another employee's
    request state off the differing flash message."""
    obj = get_object_or_404(model, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        messages.error(request, "You can only delete your own records.")
        return redirect(list_url)
    if obj.status not in obj.OPEN_STATUSES:
        messages.error(request, "A decided request can no longer be deleted.")
        return redirect(list_url)
    return _ss_child_delete(request, model, pk, list_url)


# ---- Document Requests ----------------------------------------------------------------------
@login_required
def documentrequest_list(request):
    qs = _ss_scope(request, DocumentRequest.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "status_choices": DocumentRequest.STATUS_CHOICES,
             "document_type_choices": DocumentRequest.DOCUMENT_TYPE_CHOICES}
    filters = [("status", "status", False), ("document_type", "document_type", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/requests/documentrequest/list.html",
                     search_fields=("number", "purpose", "addressed_to", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def documentrequest_create(request):
    return _ss_child_create(request, DocumentRequestForm,
                            "hrm/requests/documentrequest/form.html", "hrm:documentrequest_list")


@login_required
def documentrequest_detail(request, pk):
    return _ss_child_detail(request, DocumentRequest, pk, "hrm/requests/documentrequest/detail.html",
                            select_related=("employee__party", "approver"))


@login_required
def documentrequest_edit(request, pk):
    return _hr_request_edit(request, DocumentRequest, pk, DocumentRequestForm,
                            "hrm/requests/documentrequest/form.html", "hrm:documentrequest_detail")


@login_required
@require_POST
def documentrequest_delete(request, pk):
    return _hr_request_delete(request, DocumentRequest, pk, "hrm:documentrequest_list")


@login_required
@require_POST
def documentrequest_submit(request, pk):
    return _hr_request_submit(request, DocumentRequest, pk, "hrm:documentrequest_detail")


@login_required
@require_POST
def documentrequest_cancel(request, pk):
    return _hr_request_cancel(request, DocumentRequest, pk, "hrm:documentrequest_detail")


@tenant_admin_required
@require_POST
def documentrequest_approve(request, pk):
    return _hr_request_approve(request, DocumentRequest, pk, "hrm:documentrequest_detail")


@tenant_admin_required
@require_POST
def documentrequest_reject(request, pk):
    return _hr_request_reject(request, DocumentRequest, pk, "hrm:documentrequest_detail")


@tenant_admin_required
@require_POST
def documentrequest_fulfill(request, pk):
    """approved -> fulfilled; optionally attach the signed letter (validated by DocumentFulfillForm)."""
    obj = get_object_or_404(DocumentRequest, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved request can be fulfilled.")
        return redirect("hrm:documentrequest_detail", pk=obj.pk)
    form = DocumentFulfillForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "; ".join(form.errors.get("output_file", ["Invalid upload."])))
        return redirect("hrm:documentrequest_detail", pk=obj.pk)
    obj.status = "fulfilled"
    obj.fulfilled_at = timezone.now()
    update_fields = ["status", "fulfilled_at", "updated_at"]
    uploaded = form.cleaned_data.get("output_file")
    if uploaded:
        obj.output_file = uploaded
        update_fields.append("output_file")
    obj.save(update_fields=update_fields)
    write_audit_log(request.user, obj, "update", {"action": "fulfill"})
    messages.success(request, f"Document request {obj.number} marked fulfilled.")
    return redirect("hrm:documentrequest_detail", pk=obj.pk)


# ---- ID Card Requests -----------------------------------------------------------------------
@login_required
def idcardrequest_list(request):
    qs = _ss_scope(request, IdCardRequest.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "status_choices": IdCardRequest.STATUS_CHOICES,
             "request_type_choices": IdCardRequest.REQUEST_TYPE_CHOICES,
             "reason_type_choices": IdCardRequest.REASON_TYPE_CHOICES}
    filters = [("status", "status", False), ("request_type", "request_type", False),
               ("reason_type", "reason_type", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/requests/idcardrequest/list.html",
                     search_fields=("number", "reason", "delivery_location", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def idcardrequest_create(request):
    return _ss_child_create(request, IdCardRequestForm,
                            "hrm/requests/idcardrequest/form.html", "hrm:idcardrequest_list")


@login_required
def idcardrequest_detail(request, pk):
    return _ss_child_detail(request, IdCardRequest, pk, "hrm/requests/idcardrequest/detail.html",
                            select_related=("employee__party", "approver"))


@login_required
def idcardrequest_edit(request, pk):
    return _hr_request_edit(request, IdCardRequest, pk, IdCardRequestForm,
                            "hrm/requests/idcardrequest/form.html", "hrm:idcardrequest_detail")


@login_required
@require_POST
def idcardrequest_delete(request, pk):
    return _hr_request_delete(request, IdCardRequest, pk, "hrm:idcardrequest_list")


@login_required
@require_POST
def idcardrequest_submit(request, pk):
    return _hr_request_submit(request, IdCardRequest, pk, "hrm:idcardrequest_detail")


@login_required
@require_POST
def idcardrequest_cancel(request, pk):
    return _hr_request_cancel(request, IdCardRequest, pk, "hrm:idcardrequest_detail")


@tenant_admin_required
@require_POST
def idcardrequest_approve(request, pk):
    return _hr_request_approve(request, IdCardRequest, pk, "hrm:idcardrequest_detail")


@tenant_admin_required
@require_POST
def idcardrequest_reject(request, pk):
    return _hr_request_reject(request, IdCardRequest, pk, "hrm:idcardrequest_detail")


@tenant_admin_required
@require_POST
def idcardrequest_issue(request, pk):
    """approved -> issued; requires a non-blank card_number (stamped with issued_at)."""
    obj = get_object_or_404(IdCardRequest, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved request can be issued.")
        return redirect("hrm:idcardrequest_detail", pk=obj.pk)
    card_number = (request.POST.get("card_number") or "").strip()
    if not card_number:
        messages.error(request, "A card number is required to issue the ID card.")
        return redirect("hrm:idcardrequest_detail", pk=obj.pk)
    obj.status = "issued"
    obj.card_number = card_number[:100]
    obj.issued_at = timezone.now()
    obj.save(update_fields=["status", "card_number", "issued_at", "updated_at"])
    # Don't copy the badge/card number into the audit metadata — it's already stored on the row and
    # is the kind of physical-access identifier the codebase redacts elsewhere (_SENSITIVE_AUDIT_FIELDS).
    write_audit_log(request.user, obj, "update", {"action": "issue"})
    messages.success(request, f"ID card request {obj.number} issued (card {obj.card_number}).")
    return redirect("hrm:idcardrequest_detail", pk=obj.pk)


# ---- Asset Requests -------------------------------------------------------------------------
@login_required
def assetrequest_list(request):
    qs = _ss_scope(request, AssetRequest.objects.filter(tenant=request.tenant)
                   .select_related("employee__party"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "status_choices": AssetRequest.STATUS_CHOICES,
             "asset_category_choices": AssetAllocation.ASSET_CATEGORY_CHOICES,
             "priority_choices": AssetRequest.PRIORITY_CHOICES}
    filters = [("status", "status", False), ("asset_category", "asset_category", False),
               ("priority", "priority", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/requests/assetrequest/list.html",
                     search_fields=("number", "asset_name", "justification", "employee__party__name"),
                     filters=filters, extra_context=extra)


@login_required
def assetrequest_create(request):
    return _ss_child_create(request, AssetRequestForm,
                            "hrm/requests/assetrequest/form.html", "hrm:assetrequest_list")


@login_required
def assetrequest_detail(request, pk):
    return _ss_child_detail(request, AssetRequest, pk, "hrm/requests/assetrequest/detail.html",
                            select_related=("employee__party", "approver", "allocation"))


@login_required
def assetrequest_edit(request, pk):
    return _hr_request_edit(request, AssetRequest, pk, AssetRequestForm,
                            "hrm/requests/assetrequest/form.html", "hrm:assetrequest_detail")


@login_required
@require_POST
def assetrequest_delete(request, pk):
    return _hr_request_delete(request, AssetRequest, pk, "hrm:assetrequest_list")


@login_required
@require_POST
def assetrequest_submit(request, pk):
    return _hr_request_submit(request, AssetRequest, pk, "hrm:assetrequest_detail")


@login_required
@require_POST
def assetrequest_cancel(request, pk):
    return _hr_request_cancel(request, AssetRequest, pk, "hrm:assetrequest_detail")


@tenant_admin_required
@require_POST
def assetrequest_approve(request, pk):
    return _hr_request_approve(request, AssetRequest, pk, "hrm:assetrequest_detail")


@tenant_admin_required
@require_POST
def assetrequest_reject(request, pk):
    return _hr_request_reject(request, AssetRequest, pk, "hrm:assetrequest_detail")


@tenant_admin_required
@require_POST
def assetrequest_fulfill(request, pk):
    """approved -> fulfilled; create + link an AssetAllocation (program=None) inside one atomic txn
    so the request and its issued allocation are written together (never a half-fulfilled request)."""
    obj = get_object_or_404(AssetRequest, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an approved request can be fulfilled.")
        return redirect("hrm:assetrequest_detail", pk=obj.pk)
    with transaction.atomic():
        allocation = AssetAllocation.objects.create(
            tenant=request.tenant, program=None, employee=obj.employee,
            asset_name=obj.asset_name, asset_category=obj.asset_category,
            status="issued", issued_at=timezone.now(), issued_by=request.user,
            serial_number=(request.POST.get("serial_number") or "").strip()[:100],
            asset_tag=(request.POST.get("asset_tag") or "").strip()[:100])
        obj.allocation = allocation
        obj.status = "fulfilled"
        obj.save(update_fields=["allocation", "status", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "fulfill", "allocation": allocation.number})
    messages.success(request, f"Asset request {obj.number} fulfilled — issued {allocation.number}.")
    return redirect("hrm:assetrequest_detail", pk=obj.pk)


# ---- My Requests hub ------------------------------------------------------------------------
@login_required
def my_requests(request):
    """3.26 self-service hub: the employee's open/total counts + five most-recent rows across all
    five request types, with deep links to each type's list/create. Leave Requests and Attendance
    Regularization reuse the existing 3.10/3.9 models (no new table)."""
    profile, redirect_resp = _require_own_profile(request)
    if redirect_resp:
        return redirect_resp
    tiles = []
    for label, model, list_name, create_name, detail_name, icon in [
        ("Leave Requests", LeaveRequest, "hrm:leaverequest_list",
         "hrm:leaverequest_create", "hrm:leaverequest_detail", "calendar-days"),
        ("Attendance Regularization", AttendanceRegularization, "hrm:attendanceregularization_list",
         "hrm:attendanceregularization_create", "hrm:attendanceregularization_detail", "clock"),
        ("Document Requests", DocumentRequest, "hrm:documentrequest_list",
         "hrm:documentrequest_create", "hrm:documentrequest_detail", "file-text"),
        ("ID Card Requests", IdCardRequest, "hrm:idcardrequest_list",
         "hrm:idcardrequest_create", "hrm:idcardrequest_detail", "credit-card"),
        ("Asset Requests", AssetRequest, "hrm:assetrequest_list",
         "hrm:assetrequest_create", "hrm:assetrequest_detail", "laptop"),
    ]:
        # "My Requests" is always the VIEWER's own rows — scope to their profile directly rather than
        # via _ss_scope (which returns the whole tenant for an admin; the per-type list pages are where
        # an admin sees everyone). `profile` is guaranteed non-None here by _require_own_profile above.
        qs = model.objects.filter(tenant=request.tenant, employee=profile)
        # One conditional aggregate instead of two COUNT round trips per tile.
        counts = qs.aggregate(total=Count("pk"),
                              open=Count("pk", filter=Q(status__in=model.OPEN_STATUSES)))
        tiles.append({
            "label": label,
            "list_url_name": list_name,
            "create_url_name": create_name,
            "detail_url_name": detail_name,
            "icon": icon,
            "open_count": counts["open"],
            "total_count": counts["total"],
            # qs is already scoped to `profile`, so the recent rows need no employee join.
            "recent": list(qs[:5]),
        })
    return render(request, "hrm/requests/my_requests.html", {
        "tiles": tiles, "is_admin": _is_admin(request.user), "profile": profile,
    })


# =============================================================================================
# 3.27 Communication Hub
# =============================================================================================
# Announcements (admin-authored, audience-targeted), a derived Celebrations view (no model),
# Surveys (admin authors + employees respond once), and Suggestions (employee idea box, admin
# reviewed — reuses the 3.26 _hr_request_* helpers verbatim). Help Desk is deferred to 3.36.
from .models import (  # noqa: E402  — 3.27 Communication Hub
    Announcement,
    Suggestion,
    Survey,
    SurveyResponse,
)
from .forms import (  # noqa: E402  — 3.27 Communication Hub
    AnnouncementForm,
    SuggestionForm,
    SurveyForm,
    build_survey_response_form,
)


# ---- Celebrations (Birthday/Anniversary — derived, no model) --------------------------------
def _next_occurrence(d, today):
    """The next date on/after `today` that lands on d's month/day (Feb-29 falls back to Mar-1)."""
    for year in (today.year, today.year + 1):
        try:
            candidate = _date(year, d.month, d.day)
        except ValueError:  # Feb 29 in a non-leap year
            candidate = _date(year, 3, 1)
        if candidate >= today:
            return candidate
    return today


def _days_until(d, today):
    return (_next_occurrence(d, today) - today).days


def _is_number(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


@login_required
def celebrations(request):
    """Upcoming birthdays + work anniversaries — DERIVED (no model) from EmployeeProfile.date_of_birth
    and core.Employment.hired_on, mirroring org_chart's no-table, capped, Python-bucketed shape."""
    tenant = request.tenant
    try:
        window = int(request.GET.get("window", 30))
    except (TypeError, ValueError):
        window = 30
    window = max(1, min(window, 90))
    CAP = 500
    today = timezone.localdate()
    birthdays, anniversaries = [], []
    if tenant is not None:
        emps = list(
            EmployeeProfile.objects.filter(tenant=tenant)
            .exclude(employment__status="terminated")
            .select_related("party", "employment", "employment__org_unit")[:CAP])
        for e in emps:
            dept = e.employment.org_unit.name if (e.employment_id and e.employment.org_unit_id) else "—"
            if e.date_of_birth:
                days = _days_until(e.date_of_birth, today)
                if days <= window:
                    birthdays.append({"emp": e, "dept": dept,
                                      "date": _next_occurrence(e.date_of_birth, today), "days": days})
            hired = e.employment.hired_on if e.employment_id else None
            if hired and hired <= today:
                occ = _next_occurrence(hired, today)
                days = (occ - today).days
                years = occ.year - hired.year
                if days <= window and years >= 1:
                    anniversaries.append({"emp": e, "dept": dept, "date": occ, "days": days, "years": years})
        birthdays.sort(key=lambda r: r["days"])
        anniversaries.sort(key=lambda r: r["days"])
    return render(request, "hrm/communication/celebrations.html", {
        "birthdays": birthdays, "anniversaries": anniversaries, "window": window,
    })


# ---- Announcements --------------------------------------------------------------------------
def _announcement_targets(request, obj):
    """Is this published announcement targeted at the viewer? all → everyone; department/designation →
    the viewer's own department/designation only (a viewer with no profile matches only `all`)."""
    if obj.audience_type == "all":
        return True
    profile = _current_employee_profile(request)
    if profile is None:
        return False
    if obj.audience_type == "department":
        dept_id = profile.employment.org_unit_id if profile.employment_id else None
        return dept_id is not None and obj.target_department_id == dept_id
    if obj.audience_type == "designation":
        return profile.designation_id is not None and obj.target_designation_id == profile.designation_id
    return False


@login_required
def announcement_list(request):
    qs = (Announcement.objects.filter(tenant=request.tenant)
          .select_related("target_department", "target_designation", "author"))
    is_admin = _is_admin(request.user)
    if is_admin:
        extra = {"is_admin": True,
                 "status_choices": Announcement.STATUS_CHOICES,
                 "category_choices": Announcement.CATEGORY_CHOICES,
                 "audience_type_choices": Announcement.AUDIENCE_TYPE_CHOICES}
        filters = [("status", "status", False), ("category", "category", False),
                   ("audience_type", "audience_type", False)]
        return crud_list(request, qs, "hrm/communication/announcement/list.html",
                         search_fields=("number", "title", "body"), filters=filters, extra_context=extra)
    # Employee feed: only published, un-expired announcements targeted at the viewer.
    today = timezone.localdate()
    qs = qs.filter(status="published").filter(Q(expires_at__isnull=True) | Q(expires_at__gte=today))
    profile = _current_employee_profile(request)
    dept_id = profile.employment.org_unit_id if (profile and profile.employment_id) else None
    desig_id = profile.designation_id if profile else None
    # Only add the department/designation clause when the viewer actually HAS one — otherwise a None id
    # degrades to `target_* IS NULL`, which would match an orphaned-target announcement (its FK was
    # SET_NULL'd by deleting the OrgUnit/Designation) that _announcement_targets then 403s on click.
    audience_q = Q(audience_type="all")
    if dept_id is not None:
        audience_q |= Q(audience_type="department", target_department_id=dept_id)
    if desig_id is not None:
        audience_q |= Q(audience_type="designation", target_designation_id=desig_id)
    qs = qs.filter(audience_q)
    return crud_list(request, qs, "hrm/communication/announcement/list.html",
                     search_fields=("number", "title", "body"), extra_context={"is_admin": False})


@login_required
def announcement_detail(request, pk):
    obj = get_object_or_404(
        Announcement.objects.select_related("target_department", "target_designation", "author"),
        pk=pk, tenant=request.tenant)
    if not _is_admin(request.user):
        today = timezone.localdate()
        published_ok = obj.status == "published" and (obj.expires_at is None or obj.expires_at >= today)
        if not published_ok or not _announcement_targets(request, obj):
            raise PermissionDenied("This announcement isn't available to you.")
    return render(request, "hrm/communication/announcement/detail.html",
                  {"obj": obj, "is_admin": _is_admin(request.user)})


@tenant_admin_required
def announcement_create(request):
    if request.tenant is None:  # the superuser has tenant=None — don't create an orphan row (IntegrityError)
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = AnnouncementForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.author = request.user  # stamped server-side, never a form field
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Announcement {obj.number} created.")
            return redirect("hrm:announcement_detail", pk=obj.pk)
    else:
        form = AnnouncementForm(tenant=request.tenant)
    return render(request, "hrm/communication/announcement/form.html", {"form": form, "is_edit": False})


@tenant_admin_required
def announcement_edit(request, pk):
    return crud_edit(request, model=Announcement, pk=pk, form_class=AnnouncementForm,
                     template="hrm/communication/announcement/form.html", success_url="hrm:announcement_list")


@tenant_admin_required
@require_POST
def announcement_delete(request, pk):
    return crud_delete(request, model=Announcement, pk=pk, success_url="hrm:announcement_list")


@tenant_admin_required
@require_POST
def announcement_publish(request, pk):
    obj = get_object_or_404(Announcement, pk=pk, tenant=request.tenant)
    if obj.status == "draft":
        obj.status = "published"
        obj.published_at = timezone.now()
        obj.save(update_fields=["status", "published_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "publish"})
        messages.success(request, f"Announcement {obj.number} published.")
    else:
        messages.error(request, "Only a draft announcement can be published.")
    return redirect("hrm:announcement_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def announcement_archive(request, pk):
    obj = get_object_or_404(Announcement, pk=pk, tenant=request.tenant)
    if obj.status == "published":
        obj.status = "archived"
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "archive"})
        messages.success(request, f"Announcement {obj.number} archived.")
    else:
        messages.error(request, "Only a published announcement can be archived.")
    return redirect("hrm:announcement_detail", pk=obj.pk)


# ---- Surveys --------------------------------------------------------------------------------
@login_required
def survey_list(request):
    # Explicit order_by — annotate() drops the Meta ordering, so pagination needs one (avoids the
    # UnorderedObjectListWarning + inconsistent pages).
    qs = (Survey.objects.filter(tenant=request.tenant)
          .annotate(response_count=Count("responses")).order_by("-created_at"))
    is_admin = _is_admin(request.user)
    if not is_admin:
        qs = qs.filter(status__in=("open", "closed"))  # employees don't see drafts
    extra = {"is_admin": is_admin, "status_choices": Survey.STATUS_CHOICES}
    profile = _current_employee_profile(request)
    extra["responded_ids"] = set(
        SurveyResponse.objects.filter(tenant=request.tenant, employee=profile).values_list("survey_id", flat=True)
    ) if profile is not None else set()
    filters = [("status", "status", False)] if is_admin else []
    return crud_list(request, qs, "hrm/communication/survey/list.html",
                     search_fields=("number", "title", "description"), filters=filters, extra_context=extra)


@login_required
def survey_detail(request, pk):
    survey = get_object_or_404(
        Survey.objects.annotate(response_count=Count("responses")), pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request.user)
    if not is_admin and survey.status == "draft":
        raise PermissionDenied("This survey isn't available yet.")
    profile = _current_employee_profile(request)
    has_responded = bool(profile) and SurveyResponse.objects.filter(
        tenant=request.tenant, survey=survey, employee=profile).exists()
    return render(request, "hrm/communication/survey/detail.html",
                  {"obj": survey, "is_admin": is_admin, "has_responded": has_responded})


@tenant_admin_required
def survey_create(request):
    if request.tenant is None:  # the superuser has tenant=None — don't create an orphan row (IntegrityError)
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = SurveyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.author = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Survey {obj.number} created.")
            return redirect("hrm:survey_detail", pk=obj.pk)
    else:
        form = SurveyForm(tenant=request.tenant)
    return render(request, "hrm/communication/survey/form.html", {"form": form, "is_edit": False})


@tenant_admin_required
def survey_edit(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    if survey.status != "draft":
        messages.error(request, "Only a draft survey can be edited (it has no responses yet).")
        return redirect("hrm:survey_detail", pk=survey.pk)
    return crud_edit(request, model=Survey, pk=pk, form_class=SurveyForm,
                     template="hrm/communication/survey/form.html", success_url="hrm:survey_list")


@tenant_admin_required
@require_POST
def survey_delete(request, pk):
    # Status guard at the VIEW layer (not just the template) — deleting an opened/closed survey would
    # CASCADE-delete every SurveyResponse already collected. Only a draft (no responses) is deletable.
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    if survey.status != "draft":
        messages.error(request, "Only a draft survey can be deleted (an opened survey has responses).")
        return redirect("hrm:survey_detail", pk=survey.pk)
    return crud_delete(request, model=Survey, pk=pk, success_url="hrm:survey_list")


@tenant_admin_required
@require_POST
def survey_open(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    if survey.status != "draft":
        messages.error(request, "Only a draft survey can be opened.")
    elif not survey.questions:
        messages.error(request, "Add at least one question before opening the survey.")
    else:
        survey.status = "open"
        survey.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, survey, "update", {"action": "open"})
        messages.success(request, f"Survey {survey.number} is now open for responses.")
    return redirect("hrm:survey_detail", pk=survey.pk)


@tenant_admin_required
@require_POST
def survey_close(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    if survey.status == "open":
        survey.status = "closed"
        survey.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, survey, "update", {"action": "close"})
        messages.success(request, f"Survey {survey.number} is now closed.")
    else:
        messages.error(request, "Only an open survey can be closed.")
    return redirect("hrm:survey_detail", pk=survey.pk)


@login_required
def survey_respond(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    profile, redirect_resp = _require_own_profile(request)
    if redirect_resp:
        return redirect_resp
    if survey.status != "open":
        messages.error(request, "This survey isn't open for responses.")
        return redirect("hrm:survey_detail", pk=survey.pk)
    if SurveyResponse.objects.filter(tenant=request.tenant, survey=survey, employee=profile).exists():
        messages.info(request, "You've already responded to this survey.")
        return redirect("hrm:survey_detail", pk=survey.pk)
    form_class = build_survey_response_form(survey.questions)
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            answers = {str(i): form.cleaned_data.get(f"q_{i}") for i in range(len(survey.questions or []))}
            try:
                SurveyResponse.objects.create(
                    tenant=request.tenant, survey=survey, employee=profile, answers=answers)
            except IntegrityError:
                # respond-once race (double-click / duplicate tab) — the unique_together caught it.
                messages.info(request, "You've already responded to this survey.")
                return redirect("hrm:survey_detail", pk=survey.pk)
            write_audit_log(request.user, survey, "update", {"action": "respond"})
            messages.success(request, "Thanks — your response was recorded.")
            return redirect("hrm:survey_detail", pk=survey.pk)
    else:
        form = form_class()
    return render(request, "hrm/communication/survey/respond.html", {"survey": survey, "form": form})


@tenant_admin_required
def survey_results(request, pk):
    survey = get_object_or_404(Survey, pk=pk, tenant=request.tenant)
    responses = list(survey.responses.select_related("employee__party"))
    results = []
    for idx, q in enumerate(survey.questions or []):
        key, qtype = str(idx), q.get("type")
        entry = {"text": q.get("text", ""), "type": qtype}
        if qtype == "rating":
            nums = [float(r.answers.get(key)) for r in responses
                    if r.answers and _is_number(r.answers.get(key))]
            entry["average"] = round(sum(nums) / len(nums), 2) if nums else None
            entry["count"] = len(nums)
        elif qtype == "single_choice":
            counts = {}
            for r in responses:
                v = (r.answers or {}).get(key)
                if v:
                    counts[v] = counts.get(v, 0) + 1
            entry["choices"] = [{"option": o, "count": counts.get(o, 0)} for o in (q.get("options") or [])]
        else:  # text — when anonymous, never attach the respondent's identity
            entry["answers"] = [
                {"text": (r.answers or {}).get(key),
                 "who": (None if survey.is_anonymous else r.employee.party.name)}
                for r in responses if (r.answers or {}).get(key)]
        results.append(entry)
    return render(request, "hrm/communication/survey/results.html",
                  {"survey": survey, "results": results, "response_count": len(responses)})


# ---- Suggestions (employee idea box — reuses the 3.26 _hr_request_* helpers verbatim) --------
@login_required
def suggestion_list(request):
    qs = _ss_scope(request, Suggestion.objects.filter(tenant=request.tenant)
                   .select_related("employee__party", "approver"))
    is_admin = _is_admin(request.user)
    extra = {"is_admin": is_admin,
             "status_choices": Suggestion.STATUS_CHOICES,
             "category_choices": Suggestion.CATEGORY_CHOICES}
    filters = [("status", "status", False), ("category", "category", False)]
    if is_admin:
        filters.append(("employee", "employee_id", True))
        extra["employees"] = _ss_employees(request)
    return crud_list(request, qs, "hrm/communication/suggestion/list.html",
                     search_fields=("number", "title", "body"), filters=filters, extra_context=extra)


@login_required
def suggestion_create(request):
    return _ss_child_create(request, SuggestionForm,
                            "hrm/communication/suggestion/form.html", "hrm:suggestion_list")


@login_required
def suggestion_detail(request, pk):
    return _ss_child_detail(request, Suggestion, pk, "hrm/communication/suggestion/detail.html",
                            select_related=("employee__party", "approver"))


@login_required
def suggestion_edit(request, pk):
    return _hr_request_edit(request, Suggestion, pk, SuggestionForm,
                            "hrm/communication/suggestion/form.html", "hrm:suggestion_detail")


@login_required
@require_POST
def suggestion_delete(request, pk):
    return _hr_request_delete(request, Suggestion, pk, "hrm:suggestion_list")


@login_required
@require_POST
def suggestion_submit(request, pk):
    return _hr_request_submit(request, Suggestion, pk, "hrm:suggestion_detail")


@login_required
@require_POST
def suggestion_cancel(request, pk):
    return _hr_request_cancel(request, Suggestion, pk, "hrm:suggestion_detail")


@tenant_admin_required
@require_POST
def suggestion_approve(request, pk):
    return _hr_request_approve(request, Suggestion, pk, "hrm:suggestion_detail")


@tenant_admin_required
@require_POST
def suggestion_reject(request, pk):
    return _hr_request_reject(request, Suggestion, pk, "hrm:suggestion_detail")


@tenant_admin_required
@require_POST
def suggestion_implement(request, pk):
    """approved -> implemented; stamps implemented_at + an optional implementation_note."""
    obj = get_object_or_404(Suggestion, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(request, "Only an accepted suggestion can be marked implemented.")
        return redirect("hrm:suggestion_detail", pk=obj.pk)
    obj.status = "implemented"
    obj.implemented_at = timezone.now()
    obj.implementation_note = (request.POST.get("implementation_note") or "").strip()[:2000]
    obj.save(update_fields=["status", "implemented_at", "implementation_note", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "implement"})
    messages.success(request, f"Suggestion {obj.number} marked implemented.")
    return redirect("hrm:suggestion_detail", pk=obj.pk)
