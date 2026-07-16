"""HRM 3.28 HR Reports — Hiring views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department, _report_period
from apps.hrm.models import (
    APPLICATION_STAGE_CHOICES,
    JobApplication,
    JobRequisition,
)
from apps.hrm.views.HRReports._helpers import _dept_choices, _report_department, _report_period


@tenant_admin_required
def hiring_report(request):
    tenant = request.tenant
    date_from, date_to = _report_period(request)
    dept = _report_department(request, tenant)
    ctx = {"date_from": date_from, "date_to": date_to, "department": dept,
           "department_choices": _dept_choices(tenant), "open_reqs": 0, "filled_reqs": 0,
           "avg_ttf": None, "avg_tth": None, "offer_accept": None, "by_source": [], "funnel": [],
           "by_department": []}
    if tenant is not None:
        reqs = JobRequisition.objects.filter(tenant=tenant)
        if dept:
            reqs = reqs.filter(department=dept)
        ctx["open_reqs"] = reqs.filter(status__in=("approved", "posted")).count()
        filled = list(reqs.filter(filled_at__isnull=False,
                                  filled_at__date__gte=date_from, filled_at__date__lte=date_to))
        ctx["filled_reqs"] = len(filled)
        ttf = [(r.filled_at.date() - r.created_at.date()).days for r in filled if r.filled_at and r.created_at]
        ctx["avg_ttf"] = round(sum(ttf) / len(ttf)) if ttf else None
        apps = JobApplication.objects.filter(tenant=tenant)
        if dept:
            apps = apps.filter(requisition__department=dept)
        hired = apps.filter(stage="hired", hired_on__gte=date_from, hired_on__lte=date_to)
        tth = [(a.hired_on - a.applied_at.date()).days for a in hired if a.hired_on and a.applied_at]
        ctx["avg_tth"] = round(sum(tth) / len(tth)) if tth else None
        # Offer-acceptance approximation (no stage-history ledger): both legs use the SAME window —
        # applications submitted in the range that have since reached a terminal hired/rejected stage.
        decided = apps.filter(applied_at__date__gte=date_from, applied_at__date__lte=date_to)
        hired_dec = decided.filter(stage="hired").count()
        rejected_dec = decided.filter(stage="rejected").count()
        denom = hired_dec + rejected_dec
        ctx["offer_accept"] = round(hired_dec / denom * 100, 1) if denom else None
        source_labels = dict(apps.model._meta.get_field("source").choices)
        ctx["by_source"] = [
            {"name": source_labels.get(r["source"], r["source"]), "count": r["count"]}
            for r in hired.values("source").annotate(count=Count("id")).order_by("-count")]
        stage_counts = {r["stage"]: r["count"] for r in apps.values("stage").annotate(count=Count("id"))}
        applied_total = sum(stage_counts.values()) or 1
        ctx["funnel"] = [{"name": lbl, "count": stage_counts.get(code, 0),
                          "pct": round(stage_counts.get(code, 0) / applied_total * 100, 1)}
                         for code, lbl in APPLICATION_STAGE_CHOICES if stage_counts.get(code)]
        ctx["by_department"] = list(hired.values("requisition__department__name")
                                    .annotate(count=Count("id")).order_by("-count"))
    return render(request, "hrm/reports/hiring.html", ctx)
