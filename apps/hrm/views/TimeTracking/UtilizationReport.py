"""HRM 3.11 Time Tracking — UtilizationReport views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    TimesheetEntry,
)
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._helpers import _parse_iso_date


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
