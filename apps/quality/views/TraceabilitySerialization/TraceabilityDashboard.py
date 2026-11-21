import csv

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.core.utils import write_audit_log
from apps.quality.models.TraceabilitySerialization.BatchRecords import BatchRecord
from apps.quality.models.TraceabilitySerialization.DeviceIdentifiers import DeviceIdentifier
from apps.quality.models.TraceabilitySerialization.ProductRecalls import ProductRecall
from apps.quality.models.TraceabilitySerialization.SerializedItems import SerializedItem
from apps.quality.views._common import _csv_safe, quality_scope


@login_required
def traceability_dashboard(request):
    batch_qs = quality_scope(BatchRecord.objects.all(), request)
    serialized_qs = quality_scope(SerializedItem.objects.all(), request)
    recall_qs = quality_scope(ProductRecall.objects.all(), request)
    udi_qs = quality_scope(DeviceIdentifier.objects.all(), request)

    total_batches = batch_qs.count()
    released_batches = batch_qs.filter(status="released").count()
    quarantined_batches = batch_qs.filter(Q(status="quarantined") | Q(is_quarantined=True)).count()

    total_serialized = serialized_qs.count()
    commissioned_units = serialized_qs.filter(commissioning_status="commissioned").count()
    active_recalls = recall_qs.exclude(status__in=["completed", "terminated"]).count()

    recent_batch_records = batch_qs.select_related("supervisor", "qa_reviewer")[:5]
    recent_serialized_items = serialized_qs.select_related("parent_container", "batch_record")[:5]
    recent_recalls = recall_qs[:5]
    udi_devices = udi_qs[:5]

    # Genealogy trace search query
    trace_query = request.GET.get("trace", "").strip()
    trace_results = None
    if trace_query:
        matched_items = serialized_qs.filter(
            Q(serial_number__icontains=trace_query)
            | Q(lot_number__icontains=trace_query)
            | Q(sscc_code__icontains=trace_query)
        ).select_related("parent_container", "batch_record", "custodian", "location_unit", "shipment")[:20]
        trace_results = matched_items

    context = {
        "total_batches": total_batches,
        "released_batches": released_batches,
        "quarantined_batches": quarantined_batches,
        "total_serialized": total_serialized,
        "commissioned_units": commissioned_units,
        "active_recalls": active_recalls,
        "recent_batch_records": recent_batch_records,
        "recent_serialized_items": recent_serialized_items,
        "recent_recalls": recent_recalls,
        "udi_devices": udi_devices,
        "trace_query": trace_query,
        "trace_results": trace_results,
    }
    return render(request, "quality/traceabilityserialization/traceability_dashboard.html", context)


@login_required
def traceability_export_csv(request):
    serialized_qs = quality_scope(SerializedItem.objects.all(), request).select_related(
        "batch_record", "parent_container"
    )

    response = HttpResponse(content_type="text/csv")
    timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
    response["Content-Disposition"] = f'attachment; filename="traceability_serialization_{timestamp}.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Serial Number",
        "GTIN / DI",
        "Item Code",
        "Item Name",
        "Lot Number",
        "Packaging Level",
        "Parent Container SN",
        "SSCC Code",
        "Commissioning Status",
        "EPCIS State",
        "Cold Chain Required",
        "Batch Record Number",
    ])

    for item in serialized_qs:
        writer.writerow([
            _csv_safe(item.serial_number),
            _csv_safe(item.gtin_or_di),
            _csv_safe(item.item_code),
            _csv_safe(item.item_name),
            _csv_safe(item.lot_number),
            _csv_safe(item.get_packaging_level_display()),
            _csv_safe(item.parent_container.serial_number if item.parent_container else ""),
            _csv_safe(item.sscc_code),
            _csv_safe(item.get_commissioning_status_display()),
            _csv_safe(item.get_epcis_state_display()),
            "Yes" if item.is_cold_chain else "No",
            _csv_safe(item.batch_record.number if item.batch_record else ""),
        ])

    return response
