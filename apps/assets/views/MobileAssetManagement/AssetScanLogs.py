from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.MobileAssetManagement.AssetScanLogs import AssetScanLogForm
from apps.assets.models.MobileAssetManagement.AssetScanLogs import AssetScanLog
from apps.assets.views._common import assets_object, assets_scope
from apps.core.utils import write_audit_log


@login_required
def asset_scan_log_list(request):
    qs = assets_scope(
        AssetScanLog.objects.select_related("asset", "scanned_by"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(raw_payload__icontains=q)
            | Q(device_info__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__code__icontains=q)
            | Q(scanned_by__first_name__icontains=q)
            | Q(scanned_by__last_name__icontains=q)
            | Q(scanned_by__username__icontains=q)
        )

    match_filter = request.GET.get("match_status", "").strip()
    if match_filter:
        qs = qs.filter(match_status=match_filter)

    method_filter = request.GET.get("scan_method", "").strip()
    if method_filter:
        qs = qs.filter(scan_method=method_filter)

    context_filter = request.GET.get("scan_context", "").strip()
    if context_filter:
        qs = qs.filter(scan_context=context_filter)

    metrics = AssetScanLog.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        matched=Count("id", filter=Q(match_status="matched")),
        not_found=Count("id", filter=Q(match_status="not_found")),
        rfid=Count("id", filter=Q(scan_method="bluetooth_rfid")),
    )
    total_scans = metrics["total"]
    matched_count = metrics["matched"]
    not_found_count = metrics["not_found"]
    rfid_count = metrics["rfid"]

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/mobileassetmanagement/asset_scan_log/list.html",
        {
            "scans": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "match_choices": AssetScanLog.MATCH_STATUS_CHOICES,
            "method_choices": AssetScanLog.SCAN_METHOD_CHOICES,
            "context_choices": AssetScanLog.SCAN_CONTEXT_CHOICES,
            "total_scans": total_scans,
            "matched_count": matched_count,
            "not_found_count": not_found_count,
            "rfid_count": rfid_count,
        },
    )


@login_required
def asset_scan_log_create(request):
    if request.method == "POST":
        form = AssetScanLogForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            scan = form.save(commit=False)
            scan.tenant = request.tenant
            if not scan.scanned_by_id:
                scan.scanned_by = request.user
            scan.save()
            write_audit_log(request.user, scan, "create", tenant=request.tenant)
            messages.success(request, f"Scan log {scan.number} recorded successfully.")
            return redirect("assets:asset_scan_log_detail", pk=scan.pk)
    else:
        initial = {"scanned_by": request.user, "scanned_at": timezone.now()}
        form = AssetScanLogForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/mobileassetmanagement/asset_scan_log/form.html",
        {"form": form, "title": "Record Mobile Scan"},
    )


@login_required
def asset_scan_log_detail(request, pk):
    scan = assets_object(
        request,
        AssetScanLog,
        pk,
        select_related=["asset", "scanned_by"],
    )
    return render(
        request,
        "assets/mobileassetmanagement/asset_scan_log/detail.html",
        {"scan": scan},
    )


@login_required
def asset_scan_log_edit(request, pk):
    scan = assets_object(request, AssetScanLog, pk)
    if request.method == "POST":
        form = AssetScanLogForm(request.POST, instance=scan, tenant=request.tenant)
        if form.is_valid():
            scan = form.save()
            write_audit_log(request.user, scan, "update", tenant=request.tenant)
            messages.success(request, f"Scan log {scan.number} updated successfully.")
            return redirect("assets:asset_scan_log_detail", pk=scan.pk)
    else:
        form = AssetScanLogForm(instance=scan, tenant=request.tenant)

    return render(
        request,
        "assets/mobileassetmanagement/asset_scan_log/form.html",
        {"form": form, "scan": scan, "title": f"Edit Scan Log: {scan.number}"},
    )


@login_required
@require_POST
def asset_scan_log_delete(request, pk):
    scan = assets_object(request, AssetScanLog, pk)
    number = scan.number
    try:
        with transaction.atomic():
            write_audit_log(request.user, scan, "delete", tenant=request.tenant)
            scan.delete()
        messages.success(request, f"Scan log {number} deleted successfully.")
    except ProtectedError:
        messages.error(request, f"Cannot delete scan log {number}: dependent records exist.")
    return redirect("assets:asset_scan_log_list")
