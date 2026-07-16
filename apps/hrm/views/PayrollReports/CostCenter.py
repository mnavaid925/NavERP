"""HRM 3.31 Payroll Reports — CostCenter views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PayrollReports._helpers import _cc_choices, _report_cost_center
from apps.hrm.models import (
    CostCenterProfile,
    DepartmentProfile,
    Payslip,
    PayslipLine,
)
from apps.hrm.views.LeaveReports._helpers import _report_year
from apps.hrm.views.PayrollReports._helpers import _cc_choices, _report_cost_center


@tenant_admin_required
def cost_center_report(request):
    tenant = request.tenant
    cc = _report_cost_center(request, tenant)
    budget_year = _report_year(request)   # reused verbatim — safe int default to the current year
    ctx = {"cost_center": cc, "cost_center_choices": _cc_choices(tenant), "budget_year": budget_year,
           "rows": [], "unassigned": None, "total_budget": 0, "total_actual": 0}
    if tenant is not None:
        # 3 grouped queries + a Python fold (no per-cost-centre N+1):
        profiles = list(CostCenterProfile.objects.filter(tenant=tenant)
                        .select_related("org_unit", "owner__party").order_by("org_unit__name"))
        cc_ids = {p.org_unit_id for p in profiles}
        dept_to_cc = dict(DepartmentProfile.objects.filter(tenant=tenant, cost_center__isnull=False)
                          .values_list("org_unit_id", "cost_center_id"))
        org_gross = {r["employee__employment__org_unit_id"]: r for r in
                     (Payslip.objects.filter(tenant=tenant, cycle__pay_date__year=budget_year)
                      .values("employee__employment__org_unit_id")
                      .annotate(gross=Sum("gross_pay"), hc=Count("employee_id", distinct=True)))}
        org_employer = {r["payslip__employee__employment__org_unit_id"]: r["employer"] for r in
                        (PayslipLine.objects.filter(tenant=tenant,
                                                    payslip__cycle__pay_date__year=budget_year,
                                                    contribution_side="employer")
                         .values("payslip__employee__employment__org_unit_id")
                         .annotate(employer=Sum("amount")))}
        cc_actual = {}   # cost-centre org_unit_id (with a profile) -> {gross, hc, employer}
        unassigned = {"gross": Decimal("0"), "hc": 0, "employer": Decimal("0")}
        for org_id, row in org_gross.items():
            cc_id = org_id if org_id in cc_ids else dept_to_cc.get(org_id)
            target = (cc_actual.setdefault(cc_id, {"gross": Decimal("0"), "hc": 0, "employer": Decimal("0")})
                      if cc_id in cc_ids else unassigned)
            target["gross"] += row["gross"] or Decimal("0")
            target["hc"] += row["hc"] or 0
            target["employer"] += org_employer.get(org_id) or Decimal("0")
        if cc:
            profiles = [p for p in profiles if p.org_unit_id == cc.pk]
        rows = []
        total_budget = Decimal("0")
        total_actual = Decimal("0")
        for p in profiles:
            actual = cc_actual.get(p.org_unit_id, {"gross": Decimal("0"), "hc": 0, "employer": Decimal("0")})
            has_budget = p.budget_annual is not None
            budget = p.budget_annual or Decimal("0")
            # No budget set -> variance/variance_pct are None (rendered "—"), not a phantom negative
            # against a zero budget sitting next to a "no budget" cell.
            variance = (p.budget_annual - actual["gross"]) if has_budget else None
            rows.append({
                "name": p.org_unit.name, "code": p.code,
                "owner": p.owner.name if p.owner_id else "—",
                "budget": p.budget_annual, "budget_year": p.budget_year,
                "actual": actual["gross"], "headcount": actual["hc"], "employer": actual["employer"],
                "variance": variance,
                "variance_pct": round(variance / budget * 100, 1) if (has_budget and budget) else None,
                "budget_mismatch": p.budget_year is not None and p.budget_year != budget_year})
            total_budget += budget
            total_actual += actual["gross"]
        ctx["rows"] = rows
        ctx["total_budget"] = total_budget
        ctx["total_actual"] = total_actual
        if not cc and (unassigned["gross"] or unassigned["employer"] or unassigned["hc"]):
            ctx["unassigned"] = unassigned
    return render(request, "hrm/reports/cost_center.html", ctx)
