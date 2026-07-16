"""HRM 3.30 Leave Reports — CompOff views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    LeaveRequest,
    LeaveType,
    OvertimeRequest,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department, _report_period


@tenant_admin_required
def comp_off_report(request):
    tenant = request.tenant
    date_from, date_to = _report_period(request)
    dept = _report_department(request, tenant)
    ctx = {"date_from": date_from, "date_to": date_to, "department": dept,
           "department_choices": _dept_choices(tenant), "earned_hours": 0, "earned_count": 0,
           "availed_days": 0, "availed_count": 0, "by_employee": [], "comp_types_configured": False}
    if tenant is not None:
        earned = OvertimeRequest.objects.filter(
            tenant=tenant, payout_method="comp_leave", status="approved",
            date__gte=date_from, date__lte=date_to)
        if dept:
            earned = earned.filter(employee__employment__org_unit=dept)
        earned_rows = list(earned.select_related("employee__party"))
        ctx["earned_count"] = len(earned_rows)
        ctx["earned_hours"] = round(sum(float(r.hours_claimed or 0) for r in earned_rows), 2)
        comp_types = LeaveType.objects.filter(tenant=tenant).filter(
            Q(code__icontains="comp") | Q(name__icontains="comp"))
        ctx["comp_types_configured"] = comp_types.exists()
        if comp_types.exists():
            availed = LeaveRequest.objects.filter(
                tenant=tenant, status="approved", leave_type__in=comp_types,
                start_date__gte=date_from, start_date__lte=date_to)
            if dept:
                availed = availed.filter(employee__employment__org_unit=dept)
            ctx["availed_count"] = availed.count()
            ctx["availed_days"] = round(float(availed.aggregate(t=Sum("days"))["t"] or 0), 2)
        emp = {}
        for r in earned_rows:
            e = emp.setdefault(r.employee_id, {"name": r.employee.party.name, "hours": 0.0})
            e["hours"] += float(r.hours_claimed or 0)
        ctx["by_employee"] = sorted(({"name": v["name"], "hours": round(v["hours"], 2)} for v in emp.values()),
                                    key=lambda x: -x["hours"])[:15]
    return render(request, "hrm/reports/comp_off.html", ctx)
