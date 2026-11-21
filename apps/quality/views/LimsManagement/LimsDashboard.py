import csv
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.quality.models.LimsManagement.LabSamples import LabSample
from apps.quality.models.LimsManagement.LabSpecifications import LabSpecification
from apps.quality.models.LimsManagement.LabTestWorksheets import LabTestWorksheet
from apps.quality.models.LimsManagement.OosInvestigations import OosInvestigation
from apps.quality.views._common import _csv_safe, quality_scope


@login_required
def lims_dashboard(request):
    sample_qs = quality_scope(LabSample.objects.all(), request)
    spec_qs = quality_scope(LabSpecification.objects.all(), request)
    worksheet_qs = quality_scope(LabTestWorksheet.objects.all(), request)
    oos_qs = quality_scope(OosInvestigation.objects.all(), request)

    today = timezone.now().date()
    in_30_days = today + timedelta(days=30)

    total_samples = sample_qs.count()
    samples_in_testing = sample_qs.filter(status="in_testing").count()

    pending_worksheets = worksheet_qs.filter(status__in=["assigned", "in_progress", "review_pending"]).count()
    open_oos_count = oos_qs.filter(status__in=["open", "retest_authorized", "root_cause_found"]).count()

    expiring_reagents_count = worksheet_qs.filter(
        Q(reagent_expiry_date__lte=in_30_days, reagent_expiry_date__gte=today)
        | Q(standards_expiry_date__lte=in_30_days, standards_expiry_date__gte=today)
    ).count()

    recent_samples = sample_qs.select_related("sampled_by", "received_by")[:5]
    recent_worksheets = worksheet_qs.select_related("sample", "specification", "assigned_analyst")[:5]
    recent_oos = oos_qs.select_related("sample", "test_worksheet")[:5]

    context = {
        "total_samples": total_samples,
        "samples_in_testing": samples_in_testing,
        "pending_worksheets": pending_worksheets,
        "open_oos_count": open_oos_count,
        "expiring_reagents_count": expiring_reagents_count,
        "recent_samples": recent_samples,
        "recent_worksheets": recent_worksheets,
        "recent_oos": recent_oos,
    }
    return render(request, "quality/lims_management/lims_dashboard.html", context)


@login_required
def lims_export_csv(request):
    write_audit_log(request.user, LabTestWorksheet(), "export", tenant=request.tenant)

    worksheet_qs = quality_scope(LabTestWorksheet.objects.all(), request).select_related(
        "sample", "specification", "assigned_analyst", "instrument"
    )

    response = HttpResponse(content_type="text/csv")
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    response["Content-Disposition"] = f'attachment; filename="lims_telemetry_{timestamp}.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Worksheet Number",
        "Worksheet Title",
        "Sample ID",
        "Sample Name",
        "Specification ID",
        "Parameter Name",
        "Numeric Result",
        "Unit",
        "Within Specification",
        "Status",
        "Disposition",
        "Instrument Name",
        "Reagent Lot Number",
        "Assigned Analyst",
    ])

    for w in worksheet_qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(w.number),
            _csv_safe(w.title),
            _csv_safe(w.sample.number),
            _csv_safe(w.sample.sample_name),
            _csv_safe(w.specification.number),
            _csv_safe(w.specification.target_parameter_name),
            _csv_safe(w.numeric_result),
            _csv_safe(w.specification.parameter_unit),
            "Yes" if w.is_within_specification else "No",
            _csv_safe(w.get_status_display()),
            _csv_safe(w.get_disposition_display()),
            _csv_safe(w.instrument.name if w.instrument else w.instrument_name),
            _csv_safe(w.reagent_lot_number),
            _csv_safe(w.assigned_analyst.username if w.assigned_analyst else ""),
        ])

    return response
