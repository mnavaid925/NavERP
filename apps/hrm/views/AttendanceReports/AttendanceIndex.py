"""HRM 3.29 Attendance Reports — AttendanceIndex views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.AttendanceReports._helpers import _attendance_base
from apps.hrm.models import (
    OvertimeRequest,
)
from apps.hrm.views.AttendanceReports._helpers import _attendance_base


@tenant_admin_required
def attendance_reports_index(request):
    tenant = request.tenant
    tiles = []
    if tenant is not None:
        today = timezone.localdate()
        start = today - timedelta(days=30)
        counts = {r["status"]: r["count"] for r in _attendance_base(tenant, start, today, None)
                  .values("status").annotate(count=Count("id"))}
        total = sum(counts.values())
        tracked = total - counts.get("holiday", 0) - counts.get("on_leave", 0)
        present_equiv = counts.get("present", 0) + counts.get("regularized", 0) + 0.5 * counts.get("half_day", 0)
        att_pct = round(present_equiv / tracked * 100, 1) if tracked else 0.0
        absent_pct = round(counts.get("absent", 0) / tracked * 100, 1) if tracked else 0.0
        ot_hours = (OvertimeRequest.objects.filter(tenant=tenant, date__gte=start, date__lte=today)
                    .exclude(status__in=("draft", "rejected", "cancelled"))
                    .aggregate(h=Sum("hours_claimed"))["h"] or 0)
        tiles = [
            {"label": "Attendance % (30d)", "value": f"{att_pct}%", "url": "hrm:attendance_summary_report", "icon": "calendar-check"},
            {"label": "Absence % (30d)", "value": f"{absent_pct}%", "url": "hrm:absenteeism_report", "icon": "user-x"},
            {"label": "OT Hours (30d)", "value": f"{float(ot_hours):.1f}", "url": "hrm:overtime_report", "icon": "timer"},
            {"label": "Late / Early", "value": "View", "url": "hrm:late_early_report", "icon": "clock"},
            {"label": "Utilization", "value": "View", "url": "hrm:timesheet_utilization_report", "icon": "gauge"},
        ]
    return render(request, "hrm/reports/attendance_index.html", {"tiles": tiles})
