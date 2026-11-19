from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render

from apps.core.models import Party
from apps.quality.models.CalibrationAnalysis.CalibrationRecords import CalibrationRecord
from apps.quality.views._common import quality_scope

PAGE_SIZE = 15


@login_required
def calibration_vendor_directory(request):
    search_query = request.GET.get("q", "").strip()

    # Vendors that have performed calibrations or are accredited labs
    vendors_qs = Party.objects.filter(tenant=request.tenant).filter(
        Q(roles__role__in=["vendor", "supplier"]) | Q(calibrations_performed__isnull=False)
    ).distinct().annotate(
        calibration_events_count=Count(
            "calibrations_performed",
            filter=Q(calibrations_performed__tenant=request.tenant),
            distinct=True,
        )
    ).order_by("-calibration_events_count", "name")

    if search_query:
        vendors_qs = vendors_qs.filter(
            Q(name__icontains=search_query)
            | Q(tax_id__icontains=search_query)
        )

    paginator = Paginator(vendors_qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)
    total_vendors = page_obj.paginator.count
    accredited_count = total_vendors

    context = {
        "vendors": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "total_vendors": total_vendors,
        "accredited_count": accredited_count,
    }
    return render(request, "quality/calibrationanalysis/calibration_vendor_directory.html", context)
