"""HRM 3.32 Analytics Dashboard — Executive views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeProfile,
    JobRequisition,
    LeaveRequest,
    PayrollCycle,
    StatutoryReturn,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department, _report_period
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _headcount_trend_series, _turnover_rate


@tenant_admin_required
def executive_dashboard(request):
    tenant = request.tenant
    date_from, date_to = _report_period(request)  # drives the attrition-window calc below
    dept = _report_department(request, tenant)
    ctx = {"department": dept, "department_choices": _dept_choices(tenant), "tiles": [], "alerts": []}
    if tenant is not None:
        today = timezone.localdate()
        active = EmployeeProfile.objects.filter(tenant=tenant, employment__status="active")
        if dept:
            active = active.filter(employment__org_unit=dept)
        headcount = active.count()
        hc_labels, hc_values = _headcount_trend_series(tenant, today, months=6)
        # Avg tenure (dept-filtered)
        hired = active.filter(employment__hired_on__isnull=False).values_list("employment__hired_on", flat=True)
        tenures = [(today - h).days / 365.25 for h in hired]
        avg_tenure = round(sum(tenures) / len(tenures), 1) if tenures else 0.0
        open_reqs = JobRequisition.objects.filter(tenant=tenant, status__in=("approved", "posted"))
        if dept:
            open_reqs = open_reqs.filter(department=dept)
        open_reqs_n = open_reqs.count()
        turnover = _turnover_rate(tenant, date_from, date_to)
        # Latest payroll cycle (tenant-wide totals by construction)
        cycles = list(PayrollCycle.objects.filter(tenant=tenant).order_by("-pay_date")[:12])
        latest = cycles[0] if cycles else None
        gross = float(latest.total_gross) if latest else 0.0
        pay_recent = list(reversed(cycles))
        pending_leave = LeaveRequest.objects.filter(tenant=tenant, status="pending").count()
        overdue_stat = StatutoryReturn.objects.filter(tenant=tenant, status="pending", due_date__lt=today).count()
        ctx["tiles"] = [
            {"label": "Active Headcount", "value": headcount, "url": "hrm:headcount_report", "icon": "users",
             "trend_labels": json.dumps(hc_labels), "trend_values": json.dumps(hc_values)},
            {"label": "Attrition Rate (12mo)", "value": f"{turnover:.1f}%", "url": "hrm:attrition_report", "icon": "trending-down"},
            {"label": "Open Requisitions", "value": open_reqs_n, "url": "hrm:hiring_report", "icon": "briefcase"},
            {"label": "Avg Tenure (yrs)", "value": f"{avg_tenure:.1f}", "url": "hrm:diversity_report", "icon": "clock"},
            {"label": "Gross Payroll (latest)", "value": f"{gross:,.0f}", "url": "hrm:cost_report", "icon": "banknote",
             "trend_labels": json.dumps([c.pay_date.strftime("%b %Y") for c in pay_recent]),
             "trend_values": json.dumps([float(c.total_gross) for c in pay_recent])},
            {"label": "Pending Approvals", "value": pending_leave + overdue_stat, "url": "hrm:leave_reports_index", "icon": "clock"},
        ]
        expiring_prob = EmployeeProfile.objects.filter(
            tenant=tenant, confirmed_on__isnull=True, probation_end_date__gte=today,
            probation_end_date__lte=today + timedelta(days=30)).count()
        ctx["alerts"] = [
            {"label": "Overdue Statutory Returns", "count": overdue_stat, "url": "hrm:statutory_report",
             "severity": "red" if overdue_stat else "muted"},
            {"label": "Pending Leave Requests", "count": pending_leave, "url": "hrm:leave_trend_report",
             "severity": "amber" if pending_leave else "muted"},
            {"label": "Expiring Probations (30d)", "count": expiring_prob, "url": "hrm:employee_list",
             "severity": "amber" if expiring_prob else "muted"},
        ]
    return render(request, "hrm/analytics/executive.html", ctx)
