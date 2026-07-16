"""HRM 3.28 HR Reports — Headcount views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.HRReports._helpers import _dept_choices, _month_end, _report_department, _report_period
from apps.hrm.models import (
    Designation,
    EmployeeProfile,
    SeparationCase,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _month_end, _report_department, _report_period


@tenant_admin_required
def headcount_report(request):
    tenant = request.tenant
    today = timezone.localdate()
    date_from, date_to = _report_period(request)
    dept = _report_department(request, tenant)
    ctx = {"date_from": date_from, "date_to": date_to, "department": dept,
           "department_choices": _dept_choices(tenant), "active_count": 0, "joins": 0, "exits": 0,
           "net_change": 0, "by_department": [], "by_designation": [], "by_type": [],
           "trend_labels": "[]", "trend_values": "[]"}
    if tenant is not None:
        active = EmployeeProfile.objects.filter(tenant=tenant, employment__status="active")
        if dept:
            active = active.filter(employment__org_unit=dept)
        ctx["active_count"] = active.count()
        joins = EmployeeProfile.objects.filter(
            tenant=tenant, employment__hired_on__gte=date_from, employment__hired_on__lte=date_to)
        exits = SeparationCase.objects.filter(
            tenant=tenant, actual_last_working_day__gte=date_from, actual_last_working_day__lte=date_to)
        if dept:
            joins = joins.filter(employment__org_unit=dept)
            exits = exits.filter(employee__employment__org_unit=dept)
        ctx["joins"], ctx["exits"] = joins.count(), exits.count()
        ctx["net_change"] = ctx["joins"] - ctx["exits"]
        ctx["by_department"] = list(active.values("employment__org_unit__name")
                                    .annotate(count=Count("id")).order_by("-count"))
        budgets = {d.id: d.budgeted_headcount for d in Designation.objects.filter(tenant=tenant)}
        by_designation = []
        for r in (active.values("designation__id", "designation__name")
                  .annotate(count=Count("id")).order_by("-count")):
            budget = budgets.get(r["designation__id"])
            by_designation.append({
                "name": r["designation__name"] or "Unassigned", "count": r["count"], "budget": budget,
                "variance": (r["count"] - budget) if budget is not None else None})
        ctx["by_designation"] = by_designation
        type_labels = dict(EmployeeProfile.EMPLOYEE_TYPE_CHOICES)
        ctx["by_type"] = [
            {"name": type_labels.get(r["employee_type"], r["employee_type"] or "—"), "count": r["count"]}
            for r in active.values("employee_type").annotate(count=Count("id")).order_by("-count")]
        # 12-month headcount trend in 2 queries: sort all hire dates + per-employee first-separation
        # dates once, then bisect per month (was ~24 COUNTs via _headcount_at called 12x).
        hire_dates = sorted(EmployeeProfile.objects.filter(
            tenant=tenant, employment__hired_on__isnull=False)
            .values_list("employment__hired_on", flat=True))
        sep_dates = sorted(SeparationCase.objects.filter(
            tenant=tenant, actual_last_working_day__isnull=False).values("employee_id")
            .annotate(first=Min("actual_last_working_day")).values_list("first", flat=True))
        labels, values = [], []
        for i in range(11, -1, -1):
            m_end = _month_end(today, i)
            labels.append(m_end.strftime("%b %Y"))
            values.append(max(0, bisect.bisect_right(hire_dates, m_end) - bisect.bisect_right(sep_dates, m_end)))
        ctx["trend_labels"], ctx["trend_values"] = json.dumps(labels), json.dumps(values)
    return render(request, "hrm/reports/headcount.html", ctx)
