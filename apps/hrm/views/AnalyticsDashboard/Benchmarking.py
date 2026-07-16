"""HRM 3.32 Analytics Dashboard — Benchmarking views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.AnalyticsDashboard._helpers import _bench_target
from apps.hrm.models import (
    EmployeeProfile,
    PayrollCycle,
    Payslip,
)
from apps.hrm.views.AnalyticsDashboard._helpers import _bench_target
from apps.hrm.views.HRReports._helpers import _dept_choices, _headcount_at, _report_department, _report_period
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _present_absent_counts, _turnover_rate


@tenant_admin_required
def benchmarking(request):
    tenant = request.tenant
    date_from, date_to = _report_period(request)
    dept = _report_department(request, tenant)
    period_days = max(1, (date_to - date_from).days)
    prior_to = date_from - timedelta(days=1)
    prior_from = prior_to - timedelta(days=period_days)
    ctx = {"date_from": date_from, "date_to": date_to, "department": dept,
           "department_choices": _dept_choices(tenant), "prior_from": prior_from, "prior_to": prior_to,
           "scorecard": [], "pay_equity": [],
           "target_attrition_rate": request.GET.get("target_attrition_rate", ""),
           "target_absenteeism_rate": request.GET.get("target_absenteeism_rate", "")}
    if tenant is not None:
        def _delta(cur, prior):
            d = cur - prior
            return d, (round(d / prior * 100, 1) if prior else None)

        def _down_good_rag(cur, prior):
            if cur <= prior:
                return "green"
            return "amber" if prior and cur <= prior * 1.10 else "red"

        def _vs_target_rag(cur, target):
            if target <= 0:
                return "info"
            ratio = cur / target
            return "green" if ratio <= 1.05 else "amber" if ratio <= 1.15 else "red"

        # Headcount
        hc_cur, hc_prior = _headcount_at(tenant, date_to), _headcount_at(tenant, prior_to)
        hc_d, hc_dp = _delta(hc_cur, hc_prior)
        # Attrition (reuse the headcounts already computed above to avoid re-querying _headcount_at)
        at_cur = _turnover_rate(tenant, date_from, date_to, hc_to=hc_cur)
        at_prior = _turnover_rate(tenant, prior_from, prior_to, hc_to=hc_prior)
        at_d, at_dp = _delta(at_cur, at_prior)
        t_att = _bench_target(request, "target_attrition_rate")
        at_rag = _vs_target_rag(at_cur, t_att) if t_att is not None else _down_good_rag(at_cur, at_prior)
        # Absenteeism
        ab_a, ab_t = _present_absent_counts(tenant, date_from, date_to, dept)
        ab_cur = round(ab_a / ab_t * 100, 1) if ab_t else 0.0
        pa_a, pa_t = _present_absent_counts(tenant, prior_from, prior_to, dept)
        ab_prior = round(pa_a / pa_t * 100, 1) if pa_t else 0.0
        ab_d, ab_dp = _delta(ab_cur, ab_prior)
        t_abs = _bench_target(request, "target_absenteeism_rate")
        ab_rag = _vs_target_rag(ab_cur, t_abs) if t_abs is not None else _down_good_rag(ab_cur, ab_prior)
        # Gross payroll (cycles paid in each window)
        gp_cur = float(Payslip.objects.filter(tenant=tenant, cycle__pay_date__gte=date_from,
                                              cycle__pay_date__lte=date_to).aggregate(s=Sum("gross_pay"))["s"] or 0)
        gp_prior = float(Payslip.objects.filter(tenant=tenant, cycle__pay_date__gte=prior_from,
                                               cycle__pay_date__lte=prior_to).aggregate(s=Sum("gross_pay"))["s"] or 0)
        gp_d, gp_dp = _delta(gp_cur, gp_prior)
        ctx["scorecard"] = [
            {"label": "Headcount", "current": hc_cur, "prior": hc_prior, "delta": hc_d, "delta_pct": hc_dp,
             "rag": "info", "fmt": "int"},
            {"label": "Attrition Rate (%)", "current": at_cur, "prior": at_prior, "delta": at_d,
             "delta_pct": at_dp, "rag": at_rag, "fmt": "pct"},
            {"label": "Absenteeism Rate (%)", "current": ab_cur, "prior": ab_prior, "delta": ab_d,
             "delta_pct": ab_dp, "rag": ab_rag, "fmt": "pct"},
            {"label": "Gross Payroll ($)", "current": gp_cur, "prior": gp_prior, "delta": gp_d,
             "delta_pct": gp_dp, "rag": "info", "fmt": "money"},
        ]
        # Pay-equity mini-table from the latest cycle
        latest = PayrollCycle.objects.filter(tenant=tenant).order_by("-pay_date").first()
        if latest is not None:
            gender_labels = dict(EmployeeProfile.GENDER_CHOICES)
            for r in (Payslip.objects.filter(tenant=tenant, cycle=latest)
                      .values("employee__gender", "employee__employment__org_unit__name")
                      .annotate(avg_gross=Avg("gross_pay"), headcount=Count("employee_id", distinct=True))
                      .order_by("employee__employment__org_unit__name")):
                ctx["pay_equity"].append({
                    "gender": gender_labels.get(r["employee__gender"], "Not specified"),
                    "department": r["employee__employment__org_unit__name"] or "Unassigned",
                    "avg_gross": r["avg_gross"] or 0, "headcount": r["headcount"]})
    return render(request, "hrm/analytics/benchmarking.html", ctx)
