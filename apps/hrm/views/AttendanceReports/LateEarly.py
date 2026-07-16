"""HRM 3.29 Attendance Reports — LateEarly views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.AttendanceReports._helpers import _DOW_LABELS, _attendance_base
from apps.hrm.views.AttendanceReports._helpers import _DOW_LABELS, _attendance_base
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department, _report_period


@tenant_admin_required
def late_early_report(request):
    tenant = request.tenant
    date_from, date_to = _report_period(request)
    dept = _report_department(request, tenant)
    ctx = {"date_from": date_from, "date_to": date_to, "department": dept,
           "department_choices": _dept_choices(tenant), "considered": 0, "late_count": 0,
           "early_count": 0, "avg_late_min": None, "avg_early_min": None, "top_late": [],
           "dow_labels": json.dumps(_DOW_LABELS), "dow_late": "[]", "dow_early": "[]"}
    if tenant is not None:
        rows = list(_attendance_base(tenant, date_from, date_to, dept)
                    .filter(check_in__isnull=False, shift__isnull=False)
                    .select_related("shift", "employee__party"))
        late_mins, early_mins = [], []
        emp_late, dow_late, dow_early = {}, [0] * 7, [0] * 7
        for r in rows:
            sh = r.shift
            if r.check_in and sh and sh.start_time:
                lm = ((r.check_in.hour * 60 + r.check_in.minute)
                      - (sh.start_time.hour * 60 + sh.start_time.minute + sh.grace_minutes))
                if lm > 0:
                    late_mins.append(lm)
                    dow_late[r.date.weekday()] += 1
                    e = emp_late.setdefault(r.employee_id, {"name": r.employee.party.name, "count": 0})
                    e["count"] += 1
            if r.check_out and sh and sh.end_time:
                em = ((sh.end_time.hour * 60 + sh.end_time.minute - sh.grace_minutes)
                      - (r.check_out.hour * 60 + r.check_out.minute))
                if em > 0:
                    early_mins.append(em)
                    dow_early[r.date.weekday()] += 1
        ctx["considered"] = len(rows)
        ctx["late_count"], ctx["early_count"] = len(late_mins), len(early_mins)
        ctx["avg_late_min"] = round(sum(late_mins) / len(late_mins)) if late_mins else None
        ctx["avg_early_min"] = round(sum(early_mins) / len(early_mins)) if early_mins else None
        ctx["top_late"] = sorted(emp_late.values(), key=lambda x: -x["count"])[:10]
        ctx["dow_late"], ctx["dow_early"] = json.dumps(dow_late), json.dumps(dow_early)
    return render(request, "hrm/reports/late_early.html", ctx)
