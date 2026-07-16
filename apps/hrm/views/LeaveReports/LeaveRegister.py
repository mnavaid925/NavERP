"""HRM 3.30 Leave Reports — LeaveRegister views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.LeaveReports._helpers import _alloc_balance, _annotated_allocations, _leave_years, _report_year
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department
from apps.hrm.views.LeaveReports._helpers import _alloc_balance, _annotated_allocations, _leave_years, _report_year


@tenant_admin_required
def leave_register_report(request):
    tenant = request.tenant
    year = _report_year(request)
    dept = _report_department(request, tenant)
    ctx = {"year": year, "department": dept, "department_choices": _dept_choices(tenant),
           "year_choices": [year], "rows": [], "totals": {"allocated": 0, "used": 0, "balance": 0}}
    if tenant is not None:
        qs = _annotated_allocations(tenant, year)
        if dept:
            qs = qs.filter(employee__employment__org_unit=dept)
        rows = [{"employee": a.employee.party.name, "leave_type": a.leave_type.name,
                 "allocated": a.allocated_days, "carried": a.carried_forward,
                 "used": a.used_db, "encashed": a.encashed_days, "balance": _alloc_balance(a)} for a in qs]
        rows.sort(key=lambda r: (r["employee"], r["leave_type"]))
        ctx["rows"] = rows
        ctx["totals"] = {"allocated": round(sum(float(r["allocated"] or 0) for r in rows), 1),
                         "used": round(sum(float(r["used"] or 0) for r in rows), 1),
                         "balance": round(sum(float(r["balance"] or 0) for r in rows), 1)}
        ctx["year_choices"] = _leave_years(tenant, year)
    return render(request, "hrm/reports/leave_register.html", ctx)
