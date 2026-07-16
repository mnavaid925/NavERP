"""HRM 3.31 Payroll Reports — Statutory views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    EmployeeStatutoryIdentifier,
    StatutoryReturn,
)
from apps.hrm.views.HRReports._helpers import _report_period


@tenant_admin_required
def statutory_report(request):
    tenant = request.tenant
    # Only the social-security schemes here; the two tds_* schemes belong to tax_report.
    STAT_SCHEMES = [("pf", "Provident Fund"), ("esi", "ESI"),
                    ("pt", "Professional Tax"), ("lwf", "Labour Welfare Fund")]
    scheme = (request.GET.get("scheme") or "pf").strip()
    if scheme not in {k for k, _ in STAT_SCHEMES}:
        scheme = "pf"
    date_from, date_to = _report_period(request)
    status = (request.GET.get("status") or "").strip()
    ctx = {"scheme": scheme, "scheme_choices": STAT_SCHEMES, "date_from": date_from,
           "date_to": date_to, "status": status, "status_choices": StatutoryReturn.STATUS_CHOICES,
           "rows": [], "emp_total": 0, "empr_total": 0, "headcount_total": 0, "overdue": 0,
           "identifiers": [], "coverage": {"pf": 0, "esi": 0, "total": 0}}
    if tenant is not None:
        today = timezone.localdate()
        returns = (StatutoryReturn.objects.filter(tenant=tenant, scheme=scheme,
                                                  period_start__gte=date_from, period_start__lte=date_to)
                   .select_related("cycle", "employee__party").order_by("-period_start"))
        if status:
            returns = returns.filter(status=status)
        ctx["rows"] = list(returns)
        agg = returns.aggregate(e=Sum("employee_contribution_total"),
                                r=Sum("employer_contribution_total"), h=Sum("headcount"))
        ctx["emp_total"] = agg["e"] or 0
        ctx["empr_total"] = agg["r"] or 0
        ctx["headcount_total"] = agg["h"] or 0  # sum of per-return snapshots, not a distinct-employee count
        # DB form of StatutoryReturn.is_overdue — never call the Python @property in a loop.
        ctx["overdue"] = returns.filter(Q(status="pending") & Q(due_date__lt=today)).count()
        # Employee statutory coverage — render ONLY masked_*() identifiers (hard security rule).
        idents = list(EmployeeStatutoryIdentifier.objects.filter(tenant=tenant)
                      .select_related("employee__party").order_by("employee__party__name"))
        ctx["identifiers"] = idents
        # Coverage counts derived from the already-materialized list — 0 extra queries (the table
        # renders every identifier row unpaginated anyway, so it is all in memory here).
        ctx["coverage"] = {"pf": sum(1 for i in idents if i.is_pf_applicable),
                           "esi": sum(1 for i in idents if i.is_esi_applicable),
                           "total": len(idents)}
    return render(request, "hrm/reports/statutory.html", ctx)
