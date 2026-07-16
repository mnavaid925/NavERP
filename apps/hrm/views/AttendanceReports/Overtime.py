"""HRM 3.29 Attendance Reports — Overtime views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    OvertimeRequest,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department, _report_period


@tenant_admin_required
def overtime_report(request):
    tenant = request.tenant
    date_from, date_to = _report_period(request)
    dept = _report_department(request, tenant)
    status = (request.GET.get("status") or "").strip()
    ctx = {"date_from": date_from, "date_to": date_to, "department": dept, "status": status,
           "department_choices": _dept_choices(tenant), "status_choices": OvertimeRequest.STATUS_CHOICES,
           "total_hours": 0, "pay_equiv_hours": 0, "claims": 0, "by_employee": [], "by_department": [],
           "status_rows": [], "trend_labels": "[]", "trend_values": "[]"}
    if tenant is not None:
        scoped = OvertimeRequest.objects.filter(tenant=tenant, date__gte=date_from, date__lte=date_to)
        if dept:
            scoped = scoped.filter(employee__employment__org_unit=dept)
        # Status Mix reflects the FULL distribution (before the status filter / default exclusion).
        status_labels = dict(OvertimeRequest.STATUS_CHOICES)
        ctx["status_rows"] = [{"name": status_labels.get(r["status"], r["status"]), "count": r["count"]}
                              for r in scoped.values("status").annotate(count=Count("id")).order_by("-count")]
        # Headline figures: the picked status, else exclude non-real claims (draft/rejected/cancelled)
        # so a rejected/cancelled claim can't inflate the reported OT hours by default.
        base = (scoped.filter(status=status) if status
                else scoped.exclude(status__in=("draft", "rejected", "cancelled")))
        rows = list(base.select_related("employee__party", "employee__employment__org_unit"))
        ctx["claims"] = len(rows)
        ctx["total_hours"] = round(sum(float(r.hours_claimed or 0) for r in rows), 2)
        ctx["pay_equiv_hours"] = round(sum(float(r.overtime_pay_equivalent_hours) for r in rows), 2)
        emp, dep = {}, {}
        for r in rows:
            e = emp.setdefault(r.employee_id, {"name": r.employee.party.name, "hours": 0.0})
            e["hours"] += float(r.hours_claimed or 0)
            unit = (r.employee.employment.org_unit.name
                    if (r.employee.employment and r.employee.employment.org_unit_id) else "Unassigned")
            dep[unit] = dep.get(unit, 0) + float(r.hours_claimed or 0)
        ctx["by_employee"] = sorted(({"name": v["name"], "hours": round(v["hours"], 2)} for v in emp.values()),
                                    key=lambda x: -x["hours"])[:15]
        ctx["by_department"] = sorted(({"name": k, "hours": round(v, 2)} for k, v in dep.items()),
                                      key=lambda x: -x["hours"])
        monthly = {r["m"]: r["h"] for r in base.annotate(m=TruncMonth("date"))
                   .values("m").annotate(h=Sum("hours_claimed"))}
        months = sorted(monthly)
        ctx["trend_labels"] = json.dumps([m.strftime("%b %Y") for m in months])
        ctx["trend_values"] = json.dumps([float(monthly[m] or 0) for m in months])
    return render(request, "hrm/reports/overtime.html", ctx)
