from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render

from apps.quality.models.NonConformance.MrbDispositions import MrbDisposition
from apps.quality.models.NonConformance.NonConformanceReports import NonConformanceReport
from apps.quality.models.NonConformance.QuarantineContainments import QuarantineContainment
from apps.quality.views._common import quality_scope


@login_required
def ncr_analytics_dashboard(request):
    ncr_qs = quality_scope(NonConformanceReport.objects.all(), request)
    containment_qs = quality_scope(QuarantineContainment.objects.all(), request)
    mrb_qs = quality_scope(MrbDisposition.objects.all(), request)

    total_ncrs = ncr_qs.count()
    open_ncrs = ncr_qs.exclude(status__in=["closed", "voided"]).count()
    active_quarantines = containment_qs.filter(status="active").count()
    pending_mrbs = mrb_qs.filter(status__in=["draft", "under_review"]).count()

    total_scrap_cost = mrb_qs.aggregate(s=Sum("scrap_cost"))["s"] or Decimal("0.00")
    total_rework_cost = mrb_qs.aggregate(s=Sum("rework_labor_cost"))["s"] or Decimal("0.00")

    severity_breakdown = []
    for val, label in NonConformanceReport.SEVERITY_CHOICES:
        count = ncr_qs.filter(severity=val).count()
        css = NonConformanceReport.SEVERITY_CSS.get(val, "badge-slate")
        severity_breakdown.append({"severity": label, "count": count, "css": css})

    category_breakdown = []
    for val, label in NonConformanceReport.CATEGORY_CHOICES:
        count = ncr_qs.filter(category=val).count()
        css = NonConformanceReport.CATEGORY_CSS.get(val, "badge-slate")
        category_breakdown.append({"category": label, "count": count, "css": css})

    source_breakdown = []
    for val, label in NonConformanceReport.SOURCE_TYPE_CHOICES:
        count = ncr_qs.filter(source_type=val).count()
        css = NonConformanceReport.SOURCE_TYPE_CSS.get(val, "badge-slate")
        source_breakdown.append({"source": label, "count": count, "css": css})

    recent_ncrs = ncr_qs.select_related("initiator", "owner").order_by("-created_at")[:10]

    context = {
        "total_ncrs": total_ncrs,
        "open_ncrs": open_ncrs,
        "active_quarantines": active_quarantines,
        "pending_mrbs": pending_mrbs,
        "total_scrap_cost": total_scrap_cost,
        "total_rework_cost": total_rework_cost,
        "severity_breakdown": severity_breakdown,
        "category_breakdown": category_breakdown,
        "source_breakdown": source_breakdown,
        "recent_ncrs": recent_ncrs,
    }
    return render(request, "quality/nonconformance/ncr_analytics_dashboard.html", context)
