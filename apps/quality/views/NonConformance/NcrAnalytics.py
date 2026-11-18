from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
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

    ncr_stats = ncr_qs.aggregate(
        total=Count("id"),
        open=Count("id", filter=~Q(status__in=["closed", "voided"])),
    )
    total_ncrs = ncr_stats["total"] or 0
    open_ncrs = ncr_stats["open"] or 0

    active_quarantines = containment_qs.filter(status="active").count()

    mrb_stats = mrb_qs.aggregate(
        pending=Count("id", filter=Q(status__in=["draft", "under_review"])),
        scrap=Sum("scrap_cost"),
        rework=Sum("rework_labor_cost"),
    )
    pending_mrbs = mrb_stats["pending"] or 0
    total_scrap_cost = mrb_stats["scrap"] or Decimal("0.00")
    total_rework_cost = mrb_stats["rework"] or Decimal("0.00")

    sev_counts = dict(ncr_qs.values("severity").annotate(c=Count("id")).values_list("severity", "c"))
    severity_breakdown = [
        {
            "severity": label,
            "count": sev_counts.get(val, 0),
            "css": NonConformanceReport.SEVERITY_CSS.get(val, "badge-slate"),
        }
        for val, label in NonConformanceReport.SEVERITY_CHOICES
    ]

    cat_counts = dict(ncr_qs.values("category").annotate(c=Count("id")).values_list("category", "c"))
    category_breakdown = [
        {
            "category": label,
            "count": cat_counts.get(val, 0),
            "css": NonConformanceReport.CATEGORY_CSS.get(val, "badge-slate"),
        }
        for val, label in NonConformanceReport.CATEGORY_CHOICES
    ]

    src_counts = dict(ncr_qs.values("source_type").annotate(c=Count("id")).values_list("source_type", "c"))
    source_breakdown = [
        {
            "source": label,
            "count": src_counts.get(val, 0),
            "css": NonConformanceReport.SOURCE_TYPE_CSS.get(val, "badge-slate"),
        }
        for val, label in NonConformanceReport.SOURCE_TYPE_CHOICES
    ]

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
