"""HRM 3.29 Attendance Reports — Absenteeism views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.AttendanceReports._helpers import _ATT_NON_WORKING, _attendance_base
from apps.hrm.views.AttendanceReports._helpers import _ATT_NON_WORKING, _attendance_base
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department, _report_period


@tenant_admin_required
def absenteeism_report(request):
    tenant = request.tenant
    date_from, date_to = _report_period(request)
    dept = _report_department(request, tenant)
    ctx = {"date_from": date_from, "date_to": date_to, "department": dept,
           "department_choices": _dept_choices(tenant), "absent_days": 0, "tracked": 0,
           "absence_rate": 0.0, "frequent": [], "trend_labels": "[]", "trend_values": "[]"}
    if tenant is not None:
        base = _attendance_base(tenant, date_from, date_to, dept)
        counts = {r["status"]: r["count"] for r in base.values("status").annotate(count=Count("id"))}
        tracked = sum(counts.values()) - counts.get("holiday", 0) - counts.get("on_leave", 0)
        absent = counts.get("absent", 0)
        ctx["absent_days"], ctx["tracked"] = absent, tracked
        ctx["absence_rate"] = round(absent / tracked * 100, 1) if tracked else 0.0
        ctx["frequent"] = [
            {"name": r["employee__party__name"], "count": r["count"]}
            for r in base.filter(status="absent").values("employee__party__name")
            .annotate(count=Count("id")).order_by("-count")[:10]]
        monthly = {}
        for r in base.annotate(m=TruncMonth("date")).values("m", "status").annotate(count=Count("id")):
            d = monthly.setdefault(r["m"], {"absent": 0, "tracked": 0})
            if r["status"] not in _ATT_NON_WORKING:
                d["tracked"] += r["count"]
            if r["status"] == "absent":
                d["absent"] += r["count"]
        months = sorted(monthly)
        ctx["trend_labels"] = json.dumps([m.strftime("%b %Y") for m in months])
        ctx["trend_values"] = json.dumps([round(monthly[m]["absent"] / monthly[m]["tracked"] * 100, 1)
                                          if monthly[m]["tracked"] else 0 for m in months])
    return render(request, "hrm/reports/absenteeism.html", ctx)
