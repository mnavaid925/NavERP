"""HRM 3.31 Payroll Reports — Tax views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PayrollReports._helpers import _report_financial_year
from apps.hrm.models import (
    EmployeeProfile,
    InvestmentDeclaration,
    InvestmentDeclarationLine,
    TaxComputation,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department
from apps.hrm.views.PayrollReports._helpers import _report_financial_year


@tenant_admin_required
def tax_report(request):
    tenant = request.tenant
    dept = _report_department(request, tenant)
    regime = (request.GET.get("regime") or "").strip()
    fy, fy_choices = _report_financial_year(request, tenant)
    ctx = {"department": dept, "department_choices": _dept_choices(tenant),
           "financial_year": fy, "financial_year_choices": fy_choices, "regime": regime,
           "rows": [], "total_payable": 0, "total_paid": 0, "avg_payable": 0, "by_regime": [],
           "decl_status": [], "not_filed": 0, "by_section": []}
    if tenant is not None and fy:
        comps = (TaxComputation.objects.filter(tenant=tenant, financial_year=fy)
                 .select_related("employee__party", "employee__employment__org_unit",
                                 "declaration", "statutory_return")
                 .order_by("employee__party__name"))
        if dept:
            comps = comps.filter(employee__employment__org_unit=dept)
        if regime in ("old", "new"):
            comps = comps.filter(declaration__regime_elected=regime)
        rows = list(comps)
        ctx["rows"] = rows  # reused by both the TDS table and the Form 16 register (statutory_return link)
        agg = comps.aggregate(p=Sum("tax_payable"), y=Sum("tax_paid_ytd"))
        ctx["total_payable"] = agg["p"] or 0
        ctx["total_paid"] = agg["y"] or 0
        ctx["avg_payable"] = round((agg["p"] or 0) / len(rows), 2) if rows else 0
        regime_labels = dict(InvestmentDeclaration.REGIME_CHOICES)
        ctx["by_regime"] = [
            {"name": regime_labels.get(r["declaration__regime_elected"], r["declaration__regime_elected"] or "—"),
             "count": r["c"]}
            for r in comps.values("declaration__regime_elected").annotate(c=Count("id")).order_by("-c")]
        # Declaration status funnel + "not filed" — tenant+FY scope (independent of dept/regime).
        decls = InvestmentDeclaration.objects.filter(tenant=tenant, financial_year=fy)
        status_labels = dict(InvestmentDeclaration.STATUS_CHOICES)
        ctx["decl_status"] = [
            {"name": status_labels.get(r["status"], r["status"]), "count": r["c"]}
            for r in decls.values("status").annotate(c=Count("id")).order_by("status")]
        ctx["not_filed"] = (EmployeeProfile.objects.filter(tenant=tenant)
                            .exclude(pk__in=decls.values("employee_id")).count())
        section_labels = dict(InvestmentDeclarationLine.SECTION_CODE_CHOICES)
        ctx["by_section"] = [
            {"name": section_labels.get(r["section_code"], r["section_code"]),
             "declared": r["d"] or 0, "verified": r["v"] or 0}
            for r in (InvestmentDeclarationLine.objects.filter(tenant=tenant, declaration__financial_year=fy)
                      .values("section_code").annotate(d=Sum("declared_amount"), v=Sum("verified_amount"))
                      .order_by("section_code"))]
    return render(request, "hrm/reports/tax.html", ctx)
