"""HRM 3.30 Leave Reports — LeaveLiability views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.LeaveReports._helpers import _alloc_balance, _annotated_allocations, _leave_years, _report_year
from apps.hrm.models import (
    EmployeeSalaryStructure,
    LeaveEncashment,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department
from apps.hrm.views.LeaveReports._helpers import _alloc_balance, _annotated_allocations, _leave_years, _report_year


@tenant_admin_required
def leave_liability_report(request):
    tenant = request.tenant
    year = _report_year(request)
    dept = _report_department(request, tenant)
    ctx = {"year": year, "department": dept, "department_choices": _dept_choices(tenant),
           "year_choices": [year], "rows": [], "liability_days": 0, "liability_value": 0,
           "is_estimate": False}
    if tenant is not None:
        qs = _annotated_allocations(tenant, year).filter(leave_type__encashable=True)
        if dept:
            qs = qs.filter(employee__employment__org_unit=dept)
        # rate fallback: latest APPROVED/PAID per-(employee,type) encashment rate, else CTC/365 estimate,
        # else days-only. Only real (approved/paid) encashments set an authoritative rate; a stable
        # -year, -id ordering + setdefault picks the most recent one (never a draft/rejected rate).
        enc_rates = {}
        for e in (LeaveEncashment.objects.filter(tenant=tenant, status__in=("approved", "paid"))
                  .order_by("employee_id", "leave_type_id", "-year", "-id")):
            enc_rates.setdefault((e.employee_id, e.leave_type_id), e.rate_per_day)
        ctc = {s.employee_id: (s.annual_ctc_amount / Decimal("365"))
               for s in EmployeeSalaryStructure.objects.filter(tenant=tenant, status="active")
               if s.annual_ctc_amount}
        rows, total_days, total_value, any_estimate = [], Decimal("0"), Decimal("0"), False
        for a in qs:
            bal = _alloc_balance(a)
            if bal <= 0:
                continue
            estimate = False
            rate = enc_rates.get((a.employee_id, a.leave_type_id))
            if rate is None:  # a genuine 0 encashment rate is honored; only a missing rate falls back
                rate = ctc.get(a.employee_id)
                estimate = rate is not None
            value = (bal * rate) if rate else None
            any_estimate = any_estimate or estimate
            total_days += bal
            if value is not None:
                total_value += value
            rows.append({"employee": a.employee.party.name, "leave_type": a.leave_type.name,
                         "balance": bal, "rate": rate, "value": value, "estimate": estimate})
        rows.sort(key=lambda r: -(float(r["value"]) if r["value"] else 0))
        ctx["rows"] = rows
        ctx["liability_days"] = round(float(total_days), 1)
        ctx["liability_value"] = round(float(total_value), 2)
        ctx["is_estimate"] = any_estimate
        ctx["year_choices"] = _leave_years(tenant, year)
    return render(request, "hrm/reports/leave_liability.html", ctx)
