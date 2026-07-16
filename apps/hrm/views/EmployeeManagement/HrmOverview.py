"""HRM 3.1 Employee Management — HrmOverview views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    APPLICATION_TERMINAL_STAGES,
    Announcement,
    AttendanceRecord,
    AttendanceRegularization,
    CandidateProfile,
    EmployeeProfile,
    JobApplication,
    JobRequisition,
    LeaveEncashment,
    LeaveRequest,
    Objective,
    OvertimeRequest,
    PerformanceReview,
    PublicHoliday,
    Timesheet,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _is_admin


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
        # Exclude terminated employees so the tile's population matches the celebrations page it links to.
        stats["birthdays_this_month"] = (employees.exclude(employment__status="terminated")
                                         .filter(date_of_birth__month=today.month).count())
        # Audience-scope the pinned count for a non-admin viewer so the tile doesn't disclose the count
        # of announcements targeted at other departments/designations (security-reviewer, Low).
        pinned_qs = Announcement.objects.filter(tenant=tenant, status="published", is_pinned=True)
        if not _is_admin(request.user):
            profile = _current_employee_profile(request)
            dept_id = profile.employment.org_unit_id if (profile and profile.employment_id) else None
            desig_id = profile.designation_id if profile else None
            audience_q = Q(audience_type="all")
            if dept_id is not None:
                audience_q |= Q(audience_type="department", target_department_id=dept_id)
            if desig_id is not None:
                audience_q |= Q(audience_type="designation", target_designation_id=desig_id)
            pinned_qs = pinned_qs.filter(
                Q(expires_at__isnull=True) | Q(expires_at__gte=today)).filter(audience_q)
        stats["pinned_announcements"] = pinned_qs.count()
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
