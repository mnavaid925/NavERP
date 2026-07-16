"""HRM 3.28 HR Reports — Cost views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department
from apps.hrm.models import (
    EmployeeSalaryStructure,
    PayrollCycle,
    Payslip,
    PayslipLine,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department


@tenant_admin_required
def cost_report(request):
    tenant = request.tenant
    dept = _report_department(request, tenant)
    ctx = {"department": dept, "department_choices": _dept_choices(tenant), "cycle": None,
           "cycle_choices": PayrollCycle.objects.none(), "is_estimate": False, "total_cost": 0,
           "avg_cost": 0, "employer_cost": 0, "by_department": [], "by_component": [],
           "trend_labels": "[]", "trend_values": "[]", "headcount": 0}
    if tenant is not None:
        cycles = list(PayrollCycle.objects.filter(tenant=tenant).order_by("-pay_date"))  # one query
        ctx["cycle_choices"] = cycles
        cycle_pk = (request.GET.get("cycle") or "").strip()
        cycle = next((c for c in cycles if str(c.pk) == cycle_pk), None) or (cycles[0] if cycles else None)
        ctx["cycle"] = cycle
        if cycle is not None:
            payslips = Payslip.objects.filter(tenant=tenant, cycle=cycle)
            if dept:
                payslips = payslips.filter(employee__employment__org_unit=dept)
            ctx["total_cost"] = payslips.aggregate(t=Sum("gross_pay"))["t"] or 0
            ctx["headcount"] = payslips.count()
            ctx["avg_cost"] = round(ctx["total_cost"] / ctx["headcount"], 2) if ctx["headcount"] else 0
            # Lines must honor the same ?department scope as the payslip totals above.
            line_qs = PayslipLine.objects.filter(payslip__cycle=cycle, payslip__tenant=tenant)
            if dept:
                line_qs = line_qs.filter(payslip__employee__employment__org_unit=dept)
            ctx["employer_cost"] = (line_qs.filter(contribution_side="employer")
                                    .aggregate(t=Sum("amount"))["t"] or 0)
            ctx["by_department"] = list(payslips.values("employee__employment__org_unit__name")
                                        .annotate(total=Sum("gross_pay")).order_by("-total"))
            comp_labels = dict(PayslipLine._meta.get_field("component_type").choices)
            ctx["by_component"] = [
                {"name": comp_labels.get(r["component_type"], r["component_type"]), "total": r["total"]}
                for r in line_qs.values("component_type").annotate(total=Sum("amount")).order_by("-total")]
            recent = list(reversed(cycles[:12]))  # cycles is already sorted -pay_date; no extra query
            ctx["trend_labels"] = json.dumps([c.pay_date.strftime("%b %Y") for c in recent])
            ctx["trend_values"] = json.dumps([float(c.total_gross) for c in recent])
        else:
            annual = (EmployeeSalaryStructure.objects.filter(tenant=tenant, status="active")
                      .aggregate(t=Sum("annual_ctc_amount"))["t"] or 0)
            hc = EmployeeSalaryStructure.objects.filter(tenant=tenant, status="active").count()
            if annual:
                ctx["is_estimate"] = True
                ctx["total_cost"] = round(annual / 12, 2)
                ctx["headcount"] = hc
                ctx["avg_cost"] = round(ctx["total_cost"] / hc, 2) if hc else 0
    return render(request, "hrm/reports/cost.html", ctx)
