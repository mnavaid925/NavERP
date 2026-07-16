"""HRM 3.1 Employee Management — Detail views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.EmployeeManagement._helpers import _is_hr_admin
from apps.hrm.models import (
    AttendanceRecord,
    EmployeeDocument,
    EmployeeLifecycleEvent,
    EmployeeProfile,
    LeaveAllocation,
    LeaveRequest,
    ShiftAssignment,
)
from apps.hrm.views.EmployeeManagement._helpers import _is_hr_admin
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._helpers import _used_days_subquery


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
