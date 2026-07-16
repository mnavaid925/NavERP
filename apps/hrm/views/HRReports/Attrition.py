"""HRM 3.28 HR Reports — Attrition views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.HRReports._helpers import _dept_choices, _headcount_at, _month_end, _report_department, _report_period, _tenure_band
from apps.hrm.models import (
    SeparationCase,
)
from apps.hrm.views.HRReports.Tenures import TENURE_BANDS
from apps.hrm.views.HRReports.Voluntarys import VOLUNTARY_SEPARATION_TYPES
from apps.hrm.views.HRReports._helpers import _dept_choices, _headcount_at, _month_end, _report_department, _report_period, _tenure_band
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _date


@tenant_admin_required
def attrition_report(request):
    tenant = request.tenant
    date_from, date_to = _report_period(request)
    dept = _report_department(request, tenant)
    sep_type = (request.GET.get("separation_type") or "").strip()
    ctx = {"date_from": date_from, "date_to": date_to, "department": dept, "separation_type": sep_type,
           "department_choices": _dept_choices(tenant),
           "separation_type_choices": SeparationCase.SEPARATION_TYPE_CHOICES,
           "separations": 0, "turnover": 0.0, "voluntary_pct": 0.0, "involuntary_pct": 0.0,
           "retention": 100.0, "by_department": [], "by_reason": [], "by_tenure": [],
           "trend_labels": "[]", "trend_values": "[]"}
    if tenant is not None:
        seps = SeparationCase.objects.filter(
            tenant=tenant, actual_last_working_day__gte=date_from, actual_last_working_day__lte=date_to)
        if dept:
            seps = seps.filter(employee__employment__org_unit=dept)
        if sep_type:
            seps = seps.filter(separation_type=sep_type)
        seps = seps.select_related("employee__employment", "employee__employment__org_unit")
        rows = list(seps)
        total = len(rows)
        ctx["separations"] = total
        avg_hc = (_headcount_at(tenant, date_from) + _headcount_at(tenant, date_to)) / 2
        days = max(1, (date_to - date_from).days)
        ctx["turnover"] = round((total / avg_hc) * (365 / days) * 100, 1) if avg_hc else 0.0
        ctx["retention"] = round(100 - ctx["turnover"], 1)
        vol = sum(1 for r in rows if r.separation_type in VOLUNTARY_SEPARATION_TYPES)
        ctx["voluntary_pct"] = round(vol / total * 100, 1) if total else 0.0
        ctx["involuntary_pct"] = round((total - vol) / total * 100, 1) if total else 0.0
        dept_counts, reason_counts, tenure_counts = {}, {}, {b: 0 for b in TENURE_BANDS}
        for r in rows:
            emp = r.employee
            unit = emp.employment.org_unit.name if (emp.employment and emp.employment.org_unit_id) else "Unassigned"
            dept_counts[unit] = dept_counts.get(unit, 0) + 1
            reason = r.get_exit_reason_display() if r.exit_reason else "Unspecified"
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            hired = emp.employment.hired_on if emp.employment else None
            days_t = (r.actual_last_working_day - hired).days if (hired and r.actual_last_working_day) else None
            tenure_counts[_tenure_band(days_t)] += 1
        ctx["by_department"] = sorted(({"name": k, "count": v} for k, v in dept_counts.items()),
                                      key=lambda x: -x["count"])
        ctx["by_reason"] = sorted(({"name": k, "count": v} for k, v in reason_counts.items()),
                                  key=lambda x: -x["count"])
        ctx["by_tenure"] = [{"name": b, "count": tenure_counts[b]} for b in TENURE_BANDS if tenure_counts[b]]
        labels, values = [], []
        n_months = min(12, max(1, days // 30 + 1))
        for i in range(n_months - 1, -1, -1):
            m_end = _month_end(date_to, i)  # anchor on the selected period end, not today
            m_start = _date(m_end.year, m_end.month, 1)
            labels.append(m_end.strftime("%b %Y"))
            values.append(sum(1 for r in rows if r.actual_last_working_day
                              and m_start <= r.actual_last_working_day <= m_end))
        ctx["trend_labels"], ctx["trend_values"] = json.dumps(labels), json.dumps(values)
    return render(request, "hrm/reports/attrition.html", ctx)
