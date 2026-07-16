"""HRM 3.31 Payroll Reports — SalaryRegister views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    PayrollCycle,
    Payslip,
    PayslipLine,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department


@tenant_admin_required
def salary_register_report(request):
    tenant = request.tenant
    dept = _report_department(request, tenant)
    on_hold = (request.GET.get("on_hold") or "").strip() == "1"
    ctx = {"department": dept, "department_choices": _dept_choices(tenant), "cycle": None,
           "cycle_choices": PayrollCycle.objects.none(), "on_hold": on_hold, "rows": [],
           "totals": {}, "by_component": []}
    if tenant is not None:
        cycles = list(PayrollCycle.objects.filter(tenant=tenant).order_by("-pay_date"))  # one query
        ctx["cycle_choices"] = cycles
        cycle_pk = (request.GET.get("cycle") or "").strip()
        cycle = next((c for c in cycles if str(c.pk) == cycle_pk), None) or (cycles[0] if cycles else None)
        ctx["cycle"] = cycle
        if cycle is not None:
            payslips = (Payslip.objects.filter(tenant=tenant, cycle=cycle)
                        .select_related("employee__party", "employee__employment__org_unit")
                        .order_by("employee__party__name"))
            if dept:
                payslips = payslips.filter(employee__employment__org_unit=dept)
            if on_hold:
                payslips = payslips.filter(on_hold=True)
            ctx["rows"] = list(payslips)
            ctx["totals"] = payslips.aggregate(
                gross=Sum("gross_pay"), ded=Sum("total_deductions"), net=Sum("net_pay"),
                arrears=Sum("arrears_amount"), bonus=Sum("bonus_amount"), lop=Sum("lop_amount"))
            # Cycle-wide component-type breakdown honoring the same dept/on_hold scope — ONE query.
            comp_labels = dict(PayslipLine._meta.get_field("component_type").choices)
            line_qs = PayslipLine.objects.filter(payslip__tenant=tenant, payslip__cycle=cycle)
            if dept:
                line_qs = line_qs.filter(payslip__employee__employment__org_unit=dept)
            if on_hold:
                line_qs = line_qs.filter(payslip__on_hold=True)
            ctx["by_component"] = [
                {"name": comp_labels.get(r["component_type"], r["component_type"]),
                 "type": r["component_type"], "total": r["total"]}
                for r in line_qs.values("component_type").annotate(total=Sum("amount")).order_by("-total")]
    return render(request, "hrm/reports/salary_register.html", ctx)
