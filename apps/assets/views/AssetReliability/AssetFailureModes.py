from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetReliability.AssetFailureModes import AssetFailureModeForm
from apps.assets.models import AssetCategory
from apps.assets.models.AssetReliability.AssetFailureModes import AssetFailureMode
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_failure_mode_list(request):
    qs = assets_scope(
        AssetFailureMode.objects.select_related(
            "fixed_asset",
            "operational_asset",
            "asset_category",
        ).defer("function_description", "failure_effect", "strategy_rationale", "mitigation_task"),
        request,
    )

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(component_subsystem__icontains=q)
            | Q(failure_mode__icontains=q)
            | Q(failure_cause__icontains=q)
            | Q(functional_failure__icontains=q)
            | Q(fixed_asset__number__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__tag_code__icontains=q)
            | Q(operational_asset__name__icontains=q)
        )

    # Filters
    risk_filter = request.GET.get("risk_level", "").strip()
    if risk_filter:
        qs = qs.filter(risk_level=risk_filter)

    strat_filter = request.GET.get("rcm_strategy", "").strip()
    if strat_filter:
        qs = qs.filter(rcm_strategy=strat_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    cat_filter = request.GET.get("category", "").strip()
    if cat_filter and cat_filter.isdigit():
        qs = qs.filter(asset_category_id=int(cat_filter))

    # KPI counts over tenant in a single roundtrip
    tenant_base = AssetFailureMode.objects.filter(tenant=request.tenant)
    stats = tenant_base.aggregate(
        total=Count("id"),
        extreme=Count("id", filter=Q(risk_level="extreme")),
        high=Count("id", filter=Q(risk_level="high")),
        cbm=Count("id", filter=Q(rcm_strategy="condition_based")),
    )
    total_failure_modes = stats["total"]
    extreme_risk_count = stats["extreme"]
    high_risk_count = stats["high"]
    cbm_strategy_count = stats["cbm"]

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "failure_modes": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "risk_level_choices": AssetFailureMode.RISK_LEVEL_CHOICES,
        "rcm_strategy_choices": AssetFailureMode.RCM_STRATEGY_CHOICES,
        "status_choices": AssetFailureMode.STATUS_CHOICES,
        "category_list": AssetCategory.objects.filter(tenant=request.tenant),
        "total_failure_modes": total_failure_modes,
        "extreme_risk_count": extreme_risk_count,
        "high_risk_count": high_risk_count,
        "cbm_strategy_count": cbm_strategy_count,
    }
    return render(request, "assets/assetreliability/asset_failure_mode/list.html", context)


@login_required
def asset_failure_mode_detail(request, pk):
    failure_mode = assets_object(
        request,
        AssetFailureMode,
        pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "linked_maintenance_schedule",
            "assessed_by",
        ],
    )
    return render(
        request,
        "assets/assetreliability/asset_failure_mode/detail.html",
        {"failure_mode": failure_mode},
    )


@login_required
def asset_failure_mode_create(request):
    if request.method == "POST":
        form = AssetFailureModeForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            fm = form.save(commit=False)
            fm.tenant = request.tenant
            if not fm.assessed_by:
                fm.assessed_by = request.user
            fm.save()
            write_audit_log(request.user, fm, "create", tenant=request.tenant)
            messages.success(request, f"FMEA Record {fm.number} created with RPN {fm.rpn}.")
            return redirect("assets:asset_failure_mode_detail", pk=fm.pk)
    else:
        form = AssetFailureModeForm(tenant=request.tenant)

    return render(
        request,
        "assets/assetreliability/asset_failure_mode/form.html",
        {"form": form, "failure_mode": None, "is_edit": False},
    )


@login_required
def asset_failure_mode_edit(request, pk):
    failure_mode = assets_object(request, AssetFailureMode, pk)
    if request.method == "POST":
        form = AssetFailureModeForm(request.POST, instance=failure_mode, tenant=request.tenant)
        if form.is_valid():
            failure_mode = form.save()
            write_audit_log(request.user, failure_mode, "update", tenant=request.tenant)
            messages.success(request, f"FMEA Record {failure_mode.number} updated (RPN {failure_mode.rpn}).")
            return redirect("assets:asset_failure_mode_detail", pk=failure_mode.pk)
    else:
        form = AssetFailureModeForm(instance=failure_mode, tenant=request.tenant)

    return render(
        request,
        "assets/assetreliability/asset_failure_mode/form.html",
        {"form": form, "failure_mode": failure_mode, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def asset_failure_mode_delete(request, pk):
    failure_mode = assets_object(request, AssetFailureMode, pk)
    number = failure_mode.number
    write_audit_log(request.user, failure_mode, "delete", tenant=request.tenant)
    failure_mode.delete()
    messages.success(request, f"FMEA Record {number} deleted successfully.")
    return redirect("assets:asset_failure_mode_list")


@login_required
@require_POST
def asset_failure_mode_activate(request, pk):
    failure_mode = assets_object(request, AssetFailureMode, pk)
    if failure_mode.status in ["draft", "superseded"]:
        failure_mode.status = "active"
        failure_mode.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, failure_mode, "update", tenant=request.tenant)
        messages.success(request, f"FMEA Record {failure_mode.number} marked as Active.")
    return redirect("assets:asset_failure_mode_detail", pk=failure_mode.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_failure_mode_archive(request, pk):
    failure_mode = assets_object(request, AssetFailureMode, pk)
    failure_mode.status = "archived"
    failure_mode.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, failure_mode, "update", tenant=request.tenant)
    messages.info(request, f"FMEA Record {failure_mode.number} moved to Archived.")
    return redirect("assets:asset_failure_mode_detail", pk=failure_mode.pk)
