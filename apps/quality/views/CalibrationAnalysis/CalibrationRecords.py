import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.CalibrationAnalysis.CalibrationRecords import CalibrationRecordForm
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.CalibrationAnalysis.CalibrationRecords import CalibrationRecord
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def calibration_record_list(request):
    qs = quality_scope(CalibrationRecord.objects.all(), request).select_related(
        "gage", "service_vendor", "calibrated_by_user", "approved_by"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(gage__gage_id__icontains=search_query)
            | Q(gage__name__icontains=search_query)
            | Q(certificate_number__icontains=search_query)
            | Q(technician_name__icontains=search_query)
        )

    result_filter = request.GET.get("overall_result", "").strip()
    if result_filter:
        qs = qs.filter(overall_result=result_filter)

    type_filter = request.GET.get("calibration_type", "").strip()
    if type_filter:
        qs = qs.filter(calibration_type=type_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    total_calibrations = qs.count()
    oot_count = quality_scope(CalibrationRecord.objects.all(), request).filter(
        overall_result="fail_out_of_tolerance"
    ).count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "calibration_records": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "result_filter": result_filter,
        "type_filter": type_filter,
        "status_filter": status_filter,
        "result_choices": CalibrationRecord.OVERALL_RESULT_CHOICES,
        "type_choices": CalibrationRecord.CALIBRATION_TYPE_CHOICES,
        "status_choices": CalibrationRecord.STATUS_CHOICES,
        "total_calibrations": total_calibrations,
        "oot_count": oot_count,
    }
    return render(request, "quality/calibrationanalysis/calibration_record/list.html", context)


@login_required
def calibration_record_detail(request, pk):
    record = quality_object(
        request, CalibrationRecord, pk,
        select_related=("gage", "service_vendor", "calibrated_by_user", "approved_by"),
        prefetch_related=("standards_used", "oot_investigations")
    )
    standards_list = record.standards_used.all()
    oot_investigation = record.oot_investigations.filter(tenant=request.tenant).first()

    context = {
        "calibration_record": record,
        "obj": record,
        "standards_list": standards_list,
        "oot_investigation": oot_investigation,
    }
    return render(request, "quality/calibrationanalysis/calibration_record/detail.html", context)


@login_required
def calibration_record_create(request):
    initial = {}
    gage_pk = request.GET.get("gage")
    if gage_pk and gage_pk.isdigit():
        initial["gage"] = gage_pk

    if request.method == "POST":
        form = CalibrationRecordForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            record = form.save(commit=False)
            record.tenant = request.tenant
            record.save()
            form.save_m2m()

            # Synchronize gage calibration status and next due date
            gage = record.gage
            gage.last_calibration_date = record.calibration_date
            gage.last_calibration_result = record.get_overall_result_display()
            if gage.calibration_interval_days:
                gage.next_calibration_due = record.calibration_date + timedelta(days=gage.calibration_interval_days)

            if record.overall_result == "fail_out_of_tolerance":
                gage.status = "quarantined_oot"
            elif record.overall_result in ("pass", "pass_with_limitations"):
                gage.status = "active_in_service"
            gage.save()

            write_audit_log(request.user, record, "create", tenant=request.tenant)
            messages.success(request, f"Calibration record {record.number} created.")
            return redirect("quality:calibration_record_detail", pk=record.pk)
    else:
        form = CalibrationRecordForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "calibration_record": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "quality/calibrationanalysis/calibration_record/form.html", context)


@login_required
def calibration_record_edit(request, pk):
    record = quality_object(request, CalibrationRecord, pk)
    if request.method == "POST":
        form = CalibrationRecordForm(request.POST, instance=record, tenant=request.tenant)
        if form.is_valid():
            record = form.save()
            write_audit_log(request.user, record, "update", tenant=request.tenant)
            messages.success(request, f"Calibration record {record.number} updated.")
            return redirect("quality:calibration_record_detail", pk=record.pk)
    else:
        form = CalibrationRecordForm(instance=record, tenant=request.tenant)

    context = {
        "form": form,
        "calibration_record": record,
        "obj": record,
        "is_edit": True,
    }
    return render(request, "quality/calibrationanalysis/calibration_record/form.html", context)


@require_POST
@login_required
@tenant_admin_required
def calibration_record_delete(request, pk):
    record = quality_object(request, CalibrationRecord, pk)
    number = record.number
    write_audit_log(request.user, record, "delete", tenant=request.tenant)
    record.delete()
    messages.success(request, f"Calibration record {number} deleted.")
    return redirect("quality:calibration_record_list")


@login_required
def calibration_record_export_csv(request):
    qs = quality_scope(CalibrationRecord.objects.all(), request).select_related("gage").order_by("-calibration_date")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="calibration_records.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Record Number", "Gage Tag", "Gage Name", "Date", "Type",
        "As-Found", "As-Left", "Result", "Uncertainty U", "TUR", "Certificate #"
    ])
    for r in qs:
        writer.writerow([
            _csv_safe(r.number),
            _csv_safe(r.gage.gage_id),
            _csv_safe(r.gage.name),
            _csv_safe(r.calibration_date.isoformat() if r.calibration_date else ""),
            _csv_safe(r.get_calibration_type_display()),
            _csv_safe(r.get_as_found_condition_display()),
            _csv_safe(r.get_as_left_condition_display()),
            _csv_safe(r.get_overall_result_display()),
            _csv_safe(str(r.expanded_uncertainty)),
            _csv_safe(str(r.test_uncertainty_ratio)),
            _csv_safe(r.certificate_number),
        ])
    return response
