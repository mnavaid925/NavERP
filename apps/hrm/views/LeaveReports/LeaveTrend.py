"""HRM 3.30 Leave Reports — LeaveTrend views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    LeaveRequest,
    LeaveType,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department, _report_period


@tenant_admin_required
def leave_trend_report(request):
    tenant = request.tenant
    date_from, date_to = _report_period(request)
    dept = _report_department(request, tenant)
    ltype = (request.GET.get("leave_type") or "").strip()
    ctx = {"date_from": date_from, "date_to": date_to, "department": dept,
           "department_choices": _dept_choices(tenant), "leave_type": ltype,
           "leave_type_choices": (LeaveType.objects.filter(tenant=tenant, is_active=True).order_by("name")
                                  if tenant is not None else LeaveType.objects.none()),
           "total_days": 0, "requests": 0, "by_type": [], "top_takers": [],
           "trend_labels": "[]", "trend_values": "[]"}
    if tenant is not None:
        base = LeaveRequest.objects.filter(tenant=tenant, status="approved",
                                           start_date__gte=date_from, start_date__lte=date_to)
        if dept:
            base = base.filter(employee__employment__org_unit=dept)
        if ltype.isdecimal() and len(ltype) <= 18 and LeaveType.objects.filter(tenant=tenant, pk=int(ltype)).exists():
            # Validate the leave-type pk belongs to this tenant before filtering (IDOR-safe,
            # mirrors _report_department's ownership check) — a foreign pk is ignored, not applied.
            base = base.filter(leave_type_id=int(ltype))
        ctx["requests"] = base.count()
        ctx["total_days"] = round(float(base.aggregate(t=Sum("days"))["t"] or 0), 1)
        ctx["by_type"] = [{"name": r["leave_type__name"], "days": round(float(r["d"] or 0), 1)}
                          for r in base.values("leave_type__name").annotate(d=Sum("days")).order_by("-d")]
        ctx["top_takers"] = [{"name": r["employee__party__name"], "days": round(float(r["d"] or 0), 1)}
                             for r in base.values("employee_id", "employee__party__name")
                             .annotate(d=Sum("days")).order_by("-d")[:10]]
        monthly = {r["m"]: r["d"] for r in base.annotate(m=TruncMonth("start_date"))
                   .values("m").annotate(d=Sum("days"))}
        months = sorted(monthly)
        ctx["trend_labels"] = json.dumps([m.strftime("%b %Y") for m in months])
        ctx["trend_values"] = json.dumps([float(monthly[m] or 0) for m in months])
    return render(request, "hrm/reports/leave_trend.html", ctx)
