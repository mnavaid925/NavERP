from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounting.models import FixedAsset
from apps.assets.forms.AssetPerformance.AssetDowntimeLogs import (
    AssetDowntimeLogForm,
    AssetDowntimeLogResolveForm,
)
from apps.assets.models.AssetPerformance.AssetDowntimeLogs import AssetDowntimeLog
from apps.assets.views._common import assets_object
from apps.core.utils import write_audit_log


@login_required
def asset_downtime_log_list(request):
    qs = AssetDowntimeLog.objects.filter(tenant=request.tenant).select_related(
        "fixed_asset", "operational_asset", "maintenance_request", "work_order", "department", "logged_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(root_cause_code__icontains=q)
            | Q(failure_description__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
            | Q(resolution_notes__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_category = request.GET.get("category", "").strip()
    if selected_category:
        qs = qs.filter(downtime_category=selected_category)

    selected_impact = request.GET.get("impact", "").strip()
    if selected_impact:
        qs = qs.filter(impact_level=selected_impact)

    fixed_asset_id = request.GET.get("fixed_asset", "").strip()
    if fixed_asset_id.isdigit():
        qs = qs.filter(fixed_asset_id=int(fixed_asset_id))

    all_tenant_logs = AssetDowntimeLog.objects.filter(tenant=request.tenant)
    agg = all_tenant_logs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
        total_duration=Sum("duration_minutes"),
        total_cost=Sum("total_downtime_cost"),
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    fixed_assets = FixedAsset.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "status": selected_status,
        "category": selected_category,
        "impact": selected_impact,
        "fixed_asset_id": fixed_asset_id,
        "status_choices": AssetDowntimeLog.STATUS_CHOICES,
        "category_choices": AssetDowntimeLog.DOWNTIME_CATEGORY_CHOICES,
        "impact_choices": AssetDowntimeLog.IMPACT_LEVEL_CHOICES,
        "fixed_assets": fixed_assets,
        "status_css": AssetDowntimeLog.STATUS_CSS,
        "category_css": AssetDowntimeLog.CATEGORY_CSS,
        "impact_css": AssetDowntimeLog.IMPACT_CSS,
        "agg": agg,
    }
    return render(request, "assets/asset_performance/asset_downtime_log/list.html", context)


@login_required
def asset_downtime_log_detail(request, pk):
    log = assets_object(
        request,
        AssetDowntimeLog,
        pk,
        select_related=["fixed_asset", "operational_asset", "maintenance_request", "work_order", "department", "logged_by"],
    )
    context = {
        "log": log,
        "status_css": AssetDowntimeLog.STATUS_CSS,
        "category_css": AssetDowntimeLog.CATEGORY_CSS,
        "impact_css": AssetDowntimeLog.IMPACT_CSS,
    }
    return render(request, "assets/asset_performance/asset_downtime_log/detail.html", context)


@login_required
def asset_downtime_log_create(request):
    if request.method == "POST":
        form = AssetDowntimeLogForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            log = form.save(commit=False)
            log.tenant = request.tenant
            if not log.logged_by:
                log.logged_by = request.user
            log.save()
            write_audit_log(request.user, log, "create", tenant=request.tenant)
            messages.success(request, f"Downtime event {log.number} logged successfully.")
            return redirect("assets:asset_downtime_log_detail", pk=log.pk)
    else:
        initial = {
            "started_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "logged_by": request.user.pk,
        }
        fixed_asset_id = request.GET.get("fixed_asset")
        if fixed_asset_id and fixed_asset_id.isdigit():
            initial["fixed_asset"] = int(fixed_asset_id)
        form = AssetDowntimeLogForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "log": None,
        "is_edit": False,
    }
    return render(request, "assets/asset_performance/asset_downtime_log/form.html", context)


@login_required
def asset_downtime_log_edit(request, pk):
    log = assets_object(request, AssetDowntimeLog, pk)
    if request.method == "POST":
        form = AssetDowntimeLogForm(request.POST, instance=log, tenant=request.tenant)
        if form.is_valid():
            log = form.save()
            write_audit_log(request.user, log, "update", tenant=request.tenant)
            messages.success(request, f"Downtime event {log.number} updated successfully.")
            return redirect("assets:asset_downtime_log_detail", pk=log.pk)
    else:
        form = AssetDowntimeLogForm(instance=log, tenant=request.tenant)

    context = {
        "form": form,
        "log": log,
        "is_edit": True,
    }
    return render(request, "assets/asset_performance/asset_downtime_log/form.html", context)


@login_required
@require_POST
def asset_downtime_log_delete(request, pk):
    log = assets_object(request, AssetDowntimeLog, pk)
    number = log.number
    write_audit_log(request.user, log, "delete", tenant=request.tenant)
    log.delete()
    messages.success(request, f"Downtime event {number} deleted.")
    return redirect("assets:asset_downtime_log_list")


@login_required
def asset_downtime_log_resolve(request, pk):
    log = assets_object(request, AssetDowntimeLog, pk)
    if log.status != "active":
        messages.error(request, f"Downtime event {log.number} cannot be resolved because it is currently {log.get_status_display().lower()}.")
        return redirect("assets:asset_downtime_log_detail", pk=log.pk)
    if request.method == "POST":
        form = AssetDowntimeLogResolveForm(request.POST, instance=log)
        if form.is_valid():
            log = form.save(commit=False)
            log.status = "resolved"
            if not log.ended_at:
                log.ended_at = timezone.now()
            log.save()
            write_audit_log(request.user, log, "resolve", tenant=request.tenant)
            messages.success(request, f"Downtime event {log.number} resolved. Duration: {log.duration_minutes} min.")
            return redirect("assets:asset_downtime_log_detail", pk=log.pk)
    else:
        initial = {
            "ended_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
            "hourly_cost_rate": log.hourly_cost_rate,
            "resolution_notes": log.resolution_notes,
        }
        form = AssetDowntimeLogResolveForm(instance=log, initial=initial)

    context = {
        "form": form,
        "log": log,
    }
    return render(request, "assets/asset_performance/asset_downtime_log/resolve.html", context)
