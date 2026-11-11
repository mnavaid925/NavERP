from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.MobileAssetManagement.MobileAssetInspections import MobileAssetInspectionForm
from apps.assets.models.MobileAssetManagement.MobileAssetInspections import MobileAssetInspection
from apps.assets.views._common import assets_object, assets_scope
from apps.core.utils import write_audit_log


@login_required
def mobile_asset_inspection_list(request):
    qs = assets_scope(
        MobileAssetInspection.objects.select_related("asset", "fixed_asset", "inspector"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(asset__name__icontains=q)
            | Q(asset__code__icontains=q)
            | Q(inspector__first_name__icontains=q)
            | Q(inspector__last_name__icontains=q)
            | Q(inspector__username__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    result_filter = request.GET.get("overall_result", "").strip()
    if result_filter:
        qs = qs.filter(overall_result=result_filter)

    type_filter = request.GET.get("inspection_type", "").strip()
    if type_filter:
        qs = qs.filter(inspection_type=type_filter)

    metrics = MobileAssetInspection.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        passed=Count("id", filter=Q(overall_result="pass")),
        failed=Count("id", filter=Q(overall_result__in=["fail", "critical_hazard"])),
        offline=Count("id", filter=Q(is_offline_captured=True)),
    )
    total_inspections = metrics["total"]
    passed_count = metrics["passed"]
    failed_count = metrics["failed"]
    offline_captured_count = metrics["offline"]

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assets/mobileassetmanagement/mobile_asset_inspection/list.html",
        {
            "inspections": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": MobileAssetInspection.STATUS_CHOICES,
            "result_choices": MobileAssetInspection.OVERALL_RESULT_CHOICES,
            "type_choices": MobileAssetInspection.INSPECTION_TYPE_CHOICES,
            "total_inspections": total_inspections,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "offline_captured_count": offline_captured_count,
        },
    )


@login_required
def mobile_asset_inspection_create(request):
    if request.method == "POST":
        form = MobileAssetInspectionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            inspection = form.save(commit=False)
            inspection.tenant = request.tenant
            if not inspection.inspector_id:
                inspection.inspector = request.user
            inspection.save()
            write_audit_log(request.user, inspection, "create", tenant=request.tenant)
            messages.success(request, f"Mobile inspection {inspection.number} created successfully.")
            return redirect("assets:mobile_asset_inspection_detail", pk=inspection.pk)
    else:
        initial = {"inspector": request.user, "inspection_date": timezone.now()}
        form = MobileAssetInspectionForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "assets/mobileassetmanagement/mobile_asset_inspection/form.html",
        {"form": form, "title": "New Mobile Inspection"},
    )


@login_required
def mobile_asset_inspection_detail(request, pk):
    inspection = assets_object(
        request,
        MobileAssetInspection,
        pk,
        select_related=["asset", "fixed_asset", "inspector"],
    )
    return render(
        request,
        "assets/mobileassetmanagement/mobile_asset_inspection/detail.html",
        {"inspection": inspection},
    )


@login_required
def mobile_asset_inspection_edit(request, pk):
    inspection = assets_object(request, MobileAssetInspection, pk)
    if request.method == "POST":
        form = MobileAssetInspectionForm(request.POST, instance=inspection, tenant=request.tenant)
        if form.is_valid():
            inspection = form.save()
            write_audit_log(request.user, inspection, "update", tenant=request.tenant)
            messages.success(request, f"Mobile inspection {inspection.number} updated successfully.")
            return redirect("assets:mobile_asset_inspection_detail", pk=inspection.pk)
    else:
        form = MobileAssetInspectionForm(instance=inspection, tenant=request.tenant)

    return render(
        request,
        "assets/mobileassetmanagement/mobile_asset_inspection/form.html",
        {"form": form, "inspection": inspection, "title": f"Edit Inspection: {inspection.number}"},
    )


@login_required
@require_POST
def mobile_asset_inspection_delete(request, pk):
    inspection = assets_object(request, MobileAssetInspection, pk)
    number = inspection.number
    write_audit_log(request.user, inspection, "delete", tenant=request.tenant)
    inspection.delete()
    messages.success(request, f"Mobile inspection {number} deleted successfully.")
    return redirect("assets:mobile_asset_inspection_list")
