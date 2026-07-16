"""HRM 3.28 HR Reports — HrIndex views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.HRReports._helpers import _headcount_at
from apps.hrm.models import (
    EmployeeProfile,
    EmployeeSalaryStructure,
    JobRequisition,
    PayrollCycle,
    SeparationCase,
)
from apps.hrm.views.HRReports._helpers import _headcount_at
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _date


@tenant_admin_required
def hr_reports_index(request):
    """HR Reports landing — 5 KPI tiles linking to each drill-in report (trailing-12-month basis)."""
    tenant = request.tenant
    today = timezone.localdate()
    tiles = []
    if tenant is not None:
        active = EmployeeProfile.objects.filter(tenant=tenant, employment__status="active")
        active_count = active.count()
        year_start = _date(today.year, 1, 1)
        seps_ytd = SeparationCase.objects.filter(
            tenant=tenant, actual_last_working_day__gte=year_start, actual_last_working_day__lte=today).count()
        avg_hc = (_headcount_at(tenant, year_start) + active_count) / 2 or 0
        days = max(1, (today - year_start).days)
        attrition = round((seps_ytd / avg_hc) * (365 / days) * 100, 1) if avg_hc else 0.0
        female = active.filter(gender="female").count()
        gender_pct = round(female / active_count * 100, 1) if active_count else 0.0
        latest_cycle = PayrollCycle.objects.filter(tenant=tenant).order_by("-pay_date").first()
        if latest_cycle is not None:
            mtd_cost = latest_cycle.total_gross
        else:
            annual = (EmployeeSalaryStructure.objects.filter(tenant=tenant, status="active")
                      .aggregate(t=Sum("annual_ctc_amount"))["t"] or 0)
            mtd_cost = round(annual / 12, 2)
        filled = JobRequisition.objects.filter(
            tenant=tenant, filled_at__isnull=False, filled_at__date__gte=today - timedelta(days=365))
        ttf = [(r.filled_at.date() - r.created_at.date()).days for r in filled if r.filled_at and r.created_at]
        avg_ttf = round(sum(ttf) / len(ttf)) if ttf else None
        tiles = [
            {"label": "Active Headcount", "value": active_count, "url": "hrm:headcount_report", "icon": "users"},
            {"label": "Attrition (YTD, annualized)", "value": f"{attrition}%", "url": "hrm:attrition_report", "icon": "user-minus"},
            {"label": "Female %", "value": f"{gender_pct}%", "url": "hrm:diversity_report", "icon": "pie-chart"},
            {"label": "Latest Payroll Cost", "value": f"{mtd_cost:,.0f}", "url": "hrm:cost_report", "icon": "banknote"},
            {"label": "Avg Time-to-Fill", "value": (f"{avg_ttf} days" if avg_ttf is not None else "—"),
             "url": "hrm:hiring_report", "icon": "user-plus"},
        ]
    return render(request, "hrm/reports/hr_index.html", {"tiles": tiles})
