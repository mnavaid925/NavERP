from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetReliability.AssetCalibrationRecords import AssetCalibrationRecordForm
from apps.assets.models.AssetReliability.AssetCalibrationRecords import AssetCalibrationRecord
from apps.assets.views._common import assets_object, assets_scope
from apps.core.models import Party
from apps.core.utils import write_audit_log


@login_required
def asset_calibration_record_list(request):
    qs = assets_scope(
        AssetCalibrationRecord.objects.select_related(
            "fixed_asset",
            "operational_asset",
            "calibrated_by",
            "service_vendor",
            "certificate_document",
        ),
        request,
    )

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(instrument_tag__icontains=q)
            | Q(reference_standard_used__icontains=q)
            | Q(certificate_number__icontains=q)
            | Q(fixed_asset__asset_number__icontains=q)
            | Q(operational_asset__asset_tag__icontains=q)
        )

    # Filters
    result_filter = request.GET.get("calibration_result", "").strip()
    if result_filter:
        qs = qs.filter(calibration_result=result_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    vendor_filter = request.GET.get("vendor", "").strip()
    if vendor_filter:
        qs = qs.filter(service_vendor_id=vendor_filter)

    # KPI counts over tenant
    today = timezone.now().date()
    tenant_base = AssetCalibrationRecord.objects.filter(tenant=request.tenant)
    total_calibrations = tenant_base.count()
    passed_count = tenant_base.filter(calibration_result__in=["pass", "pass_with_adjustment"]).count()
    failed_count = tenant_base.filter(calibration_result="fail_out_of_tolerance").count()
    overdue_count = tenant_base.filter(Q(status="expired") | Q(next_due_date__lt=today)).count()

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    vendor_list = Party.objects.filter(
        tenant=request.tenant,
        roles__role="vendor",
    ).distinct()

    context = {
        "calibration_records": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "calibration_result_choices": AssetCalibrationRecord.CALIBRATION_RESULT_CHOICES,
        "status_choices": AssetCalibrationRecord.STATUS_CHOICES,
        "tolerance_unit_choices": AssetCalibrationRecord.TOLERANCE_UNIT_CHOICES,
        "vendor_list": vendor_list,
        "total_calibrations": total_calibrations,
        "passed_count": passed_count,
        "failed_count": failed_count,
        "overdue_count": overdue_count,
    }
    return render(request, "assets/assetreliability/asset_calibration_record/list.html", context)


@login_required
def asset_calibration_record_detail(request, pk):
    calibration = assets_object(
        request,
        AssetCalibrationRecord,
        pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "calibrated_by",
            "service_vendor",
            "certificate_document",
        ],
    )
    return render(
        request,
        "assets/assetreliability/asset_calibration_record/detail.html",
        {"calibration": calibration},
    )


@login_required
def asset_calibration_record_create(request):
    if request.method == "POST":
        form = AssetCalibrationRecordForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cal = form.save(commit=False)
            cal.tenant = request.tenant
            if not cal.calibrated_by and not cal.service_vendor:
                cal.calibrated_by = request.user
            cal.save()
            write_audit_log(request.user, cal, "create", tenant=request.tenant)
            messages.success(request, f"Calibration Record {cal.number} created successfully.")
            return redirect("assets:asset_calibration_record_detail", pk=cal.pk)
    else:
        initial = {"calibration_date": timezone.now().date()}
        form = AssetCalibrationRecordForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/assetreliability/asset_calibration_record/form.html",
        {"form": form, "calibration": None, "is_edit": False},
    )


@login_required
def asset_calibration_record_edit(request, pk):
    calibration = assets_object(request, AssetCalibrationRecord, pk)
    if request.method == "POST":
        form = AssetCalibrationRecordForm(request.POST, instance=calibration, tenant=request.tenant)
        if form.is_valid():
            calibration = form.save()
            write_audit_log(request.user, calibration, "update", tenant=request.tenant)
            messages.success(request, f"Calibration Record {calibration.number} updated successfully.")
            return redirect("assets:asset_calibration_record_detail", pk=calibration.pk)
    else:
        form = AssetCalibrationRecordForm(instance=calibration, tenant=request.tenant)

    return render(
        request,
        "assets/assetreliability/asset_calibration_record/form.html",
        {"form": form, "calibration": calibration, "is_edit": True},
    )


@login_required
@require_POST
def asset_calibration_record_delete(request, pk):
    calibration = assets_object(request, AssetCalibrationRecord, pk)
    number = calibration.number
    write_audit_log(request.user, calibration, "delete", tenant=request.tenant)
    calibration.delete()
    messages.success(request, f"Calibration Record {number} deleted successfully.")
    return redirect("assets:asset_calibration_record_list")


@login_required
@require_POST
def asset_calibration_record_quarantine(request, pk):
    calibration = assets_object(request, AssetCalibrationRecord, pk)
    calibration.calibration_result = "quarantined"
    calibration.status = "voided"
    calibration.save(update_fields=["calibration_result", "status", "updated_at"])
    write_audit_log(request.user, calibration, "update", tenant=request.tenant)
    messages.error(request, f"Instrument {calibration.instrument_tag} ({calibration.number}) Quarantined / Out of Service.")
    return redirect("assets:asset_calibration_record_detail", pk=calibration.pk)
