"""HRM 3.32 Analytics Dashboard — Predictive views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    EmployeeProfile,
    JobRequisition,
    SeparationCase,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _attrition_risk_scores


@tenant_admin_required
def predictive_analytics(request):
    tenant = request.tenant
    dept = _report_department(request, tenant)
    ctx = {"department": dept, "department_choices": _dept_choices(tenant), "risk_rows": [],
           "avg_risk": 0.0, "band_counts": {}, "risk_by_department": [], "hiring_rows": []}
    if tenant is not None:
        today = timezone.localdate()
        scores = _attrition_risk_scores(tenant, dept)
        if scores:
            ctx["avg_risk"] = round(sum(s["score"] for s in scores) / len(scores), 1)
            bc = Counter(s["band"] for s in scores)
            ctx["band_counts"] = {b: bc.get(b, 0) for b in ("Low", "Medium", "High", "Critical")}
            ctx["risk_rows"] = sorted(scores, key=lambda s: s["score"], reverse=True)[:25]
            by_dept = {}
            for s in scores:
                d = by_dept.setdefault(s["department_name"], {"count": 0, "sum": 0, "hi": 0})
                d["count"] += 1
                d["sum"] += s["score"]
                if s["band"] in ("High", "Critical"):
                    d["hi"] += 1
            ctx["risk_by_department"] = sorted(
                [{"name": k, "count": v["count"], "avg_score": round(v["sum"] / v["count"], 1),
                  "high_or_critical_count": v["hi"]} for k, v in by_dept.items()],
                key=lambda r: r["avg_score"], reverse=True)
        # Hiring-needs projection — 3 grouped dicts, no N+1.
        desigs = Designation.objects.filter(tenant=tenant, budgeted_headcount__isnull=False).select_related("department")
        if dept:
            desigs = desigs.filter(department=dept)
        filled_by = {r["designation_id"]: r["c"] for r in EmployeeProfile.objects.filter(
            tenant=tenant, employment__status="active").values("designation_id").annotate(c=Count("id"))}
        exits_by = {r["employee__designation_id"]: r["c"] for r in SeparationCase.objects.filter(
            tenant=tenant, actual_last_working_day__gte=today - timedelta(days=365),
            actual_last_working_day__lte=today).values("employee__designation_id").annotate(c=Count("id"))}
        reqs_by = {r["designation_id"]: r["c"] for r in JobRequisition.objects.filter(
            tenant=tenant, status__in=("approved", "posted")).values("designation_id").annotate(c=Count("id"))}
        rows = []
        for d in desigs:
            filled = filled_by.get(d.pk, 0)
            gap = (d.budgeted_headcount or 0) - filled
            trailing_exits = exits_by.get(d.pk, 0)
            projected = round(trailing_exits / 4)
            rows.append({"designation": d.name,
                         "department": d.department.name if d.department_id else "-",
                         "budgeted": d.budgeted_headcount, "filled": filled, "gap": gap,
                         "trailing_exits": trailing_exits, "projected_exits": projected,
                         "open_reqs": reqs_by.get(d.pk, 0), "net_need": max(0, gap) + projected})
        ctx["hiring_rows"] = sorted(rows, key=lambda r: r["net_need"], reverse=True)
    return render(request, "hrm/analytics/predictive.html", ctx)
