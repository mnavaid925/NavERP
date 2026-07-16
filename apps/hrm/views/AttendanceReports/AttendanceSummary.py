"""HRM 3.29 Attendance Reports — AttendanceSummary views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.AttendanceReports._helpers import _attendance_base, _attendance_pe_tracked, _fold_att
from apps.hrm.models import (
    AttendanceRecord,
)
from apps.hrm.views.AttendanceReports._helpers import _attendance_base, _attendance_pe_tracked, _fold_att
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department, _report_period


@tenant_admin_required
def attendance_summary_report(request):
    tenant = request.tenant
    date_from, date_to = _report_period(request)
    dept = _report_department(request, tenant)
    ctx = {"date_from": date_from, "date_to": date_to, "department": dept,
           "department_choices": _dept_choices(tenant), "status_rows": [], "total": 0, "tracked": 0,
           "attendance_pct": 0.0, "by_department": [], "trend_labels": "[]", "trend_values": "[]"}
    if tenant is not None:
        base = _attendance_base(tenant, date_from, date_to, dept)
        status_labels = dict(AttendanceRecord.STATUS_CHOICES)
        counts = {r["status"]: r["count"] for r in base.values("status").annotate(count=Count("id"))}
        total = sum(counts.values())
        pe, tracked = _attendance_pe_tracked(counts)
        ctx["total"], ctx["tracked"] = total, tracked
        ctx["attendance_pct"] = round(pe / tracked * 100, 1) if tracked else 0.0
        ctx["status_rows"] = [{"name": status_labels.get(s, s), "count": counts[s],
                               "pct": round(counts[s] / total * 100, 1) if total else 0}
                              for s in sorted(counts, key=lambda s: -counts[s])]
        dept_data = {}
        for r in base.values("employee__employment__org_unit__name", "status").annotate(count=Count("id")):
            _fold_att(dept_data.setdefault(r["employee__employment__org_unit__name"] or "Unassigned",
                                           {"present": 0.0, "tracked": 0}), r["status"], r["count"])
        ctx["by_department"] = sorted(
            ({"name": k, "tracked": v["tracked"],
              "attendance_pct": round(v["present"] / v["tracked"] * 100, 1) if v["tracked"] else 0}
             for k, v in dept_data.items()), key=lambda x: -x["tracked"])
        monthly = {}
        for r in base.annotate(m=TruncMonth("date")).values("m", "status").annotate(count=Count("id")):
            _fold_att(monthly.setdefault(r["m"], {"present": 0.0, "tracked": 0}), r["status"], r["count"])
        months = sorted(monthly)
        ctx["trend_labels"] = json.dumps([m.strftime("%b %Y") for m in months])
        ctx["trend_values"] = json.dumps([round(monthly[m]["present"] / monthly[m]["tracked"] * 100, 1)
                                          if monthly[m]["tracked"] else 0 for m in months])
    return render(request, "hrm/reports/attendance_summary.html", ctx)
