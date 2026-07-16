"""HRM 3.30 Leave Reports — LeaveIndex views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.LeaveReports._helpers import _annotated_allocations
from apps.hrm.models import (
    LeaveRequest,
)
from apps.hrm.views.LeaveReports._helpers import _annotated_allocations


@tenant_admin_required
def leave_reports_index(request):
    tenant = request.tenant
    tiles = []
    if tenant is not None:
        today = timezone.localdate()
        year = today.year
        agg = _annotated_allocations(tenant, year).aggregate(a=Sum("allocated_days"), u=Sum("used_db"))
        total_alloc = float(agg["a"] or 0)
        total_used = float(agg["u"] or 0)
        on_leave = LeaveRequest.objects.filter(tenant=tenant, status="approved",
                                               start_date__lte=today, end_date__gte=today).count()
        pending = LeaveRequest.objects.filter(tenant=tenant, status="pending").count()
        tiles = [
            {"label": f"Allocated ({year})", "value": f"{total_alloc:.1f}d", "url": "hrm:leave_register_report", "icon": "calendar"},
            {"label": f"Availed ({year})", "value": f"{total_used:.1f}d", "url": "hrm:leave_register_report", "icon": "calendar-check"},
            {"label": "On Leave Today", "value": on_leave, "url": "hrm:leave_trend_report", "icon": "plane"},
            {"label": "Pending Requests", "value": pending, "url": "hrm:leave_trend_report", "icon": "clock"},
            {"label": "Leave Liability", "value": "View", "url": "hrm:leave_liability_report", "icon": "landmark"},
        ]
    return render(request, "hrm/reports/leave_index.html", {"tiles": tiles})
