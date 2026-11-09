from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetMaintenance.AssetMaintenanceLogs import AssetMaintenanceLogForm
from apps.assets.models.AssetMaintenance.AssetMaintenanceLogs import AssetMaintenanceLog
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_maintenance_log_list(request):
    qs = AssetMaintenanceLog.objects.filter(tenant=request.tenant).select_related(
        "fixed_asset", "operational_asset", "lead_technician", "service_vendor", "expense_account"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
            | Q(parts_consumed_summary__icontains=q)
            | Q(action_taken__icontains=q)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_type = request.GET.get("maintenance_type", "").strip()
    if selected_type:
        qs = qs.filter(maintenance_type=selected_type)

    selected_failure = request.GET.get("failure_code", "").strip()
    if selected_failure:
        qs = qs.filter(failure_code=selected_failure)

    all_tenant_logs = AssetMaintenanceLog.objects.filter(tenant=request.tenant)
    agg = all_tenant_logs.aggregate(
        total_logs=Count("id"),
        posted_count=Count("id", filter=Q(status="posted")),
        total_downtime_hours=Sum("downtime_hours"),
        total_maintenance_cost=Sum("total_cost"),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "maintenance_logs": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": q,
        "status_choices": AssetMaintenanceLog.STATUS_CHOICES,
        "maintenance_type_choices": AssetMaintenanceLog.MAINTENANCE_TYPE_CHOICES,
        "failure_code_choices": AssetMaintenanceLog.FAILURE_CODE_CHOICES,
        "total_logs": agg["total_logs"] or 0,
        "posted_count": agg["posted_count"] or 0,
        "total_downtime_hours": agg["total_downtime_hours"] or Decimal("0.00"),
        "total_maintenance_cost": agg["total_maintenance_cost"] or Decimal("0.00"),
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_log/list.html", context)


@login_required
def asset_maintenance_log_detail(request, pk):
    obj = assets_object(
        request,
        AssetMaintenanceLog,
        pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "maintenance_request",
            "maintenance_schedule",
            "service_contract",
            "work_order",
            "lead_technician",
            "service_vendor",
            "expense_account",
            "approved_by",
        ],
    )
    context = {
        "maintenance_log": obj,
        "status_choices": AssetMaintenanceLog.STATUS_CHOICES,
        "maintenance_type_choices": AssetMaintenanceLog.MAINTENANCE_TYPE_CHOICES,
        "failure_code_choices": AssetMaintenanceLog.FAILURE_CODE_CHOICES,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_log/detail.html", context)


@login_required
def asset_maintenance_log_create(request):
    if request.method == "POST":
        form = AssetMaintenanceLogForm(request.POST, tenant=request.tenant)
        form.tenant = request.tenant
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not obj.lead_technician:
                obj.lead_technician = request.user
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Maintenance Service Log {obj.number} created successfully.")
            return redirect("assets:asset_maintenance_log_detail", pk=obj.pk)
    else:
        initial = {}
        for param in ["maintenance_request", "maintenance_schedule", "service_contract", "fixed_asset", "operational_asset"]:
            val = request.GET.get(param)
            if val:
                initial[param] = val
        form = AssetMaintenanceLogForm(initial=initial, tenant=request.tenant)
        form.tenant = request.tenant

    context = {
        "form": form,
        "maintenance_log": None,
        "is_edit": False,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_log/form.html", context)


@login_required
def asset_maintenance_log_edit(request, pk):
    obj = assets_object(request, AssetMaintenanceLog, pk)
    if request.method == "POST":
        form = AssetMaintenanceLogForm(request.POST, instance=obj, tenant=request.tenant)
        form.tenant = request.tenant
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Maintenance Log {obj.number} updated successfully.")
            return redirect("assets:asset_maintenance_log_detail", pk=obj.pk)
    else:
        form = AssetMaintenanceLogForm(instance=obj, tenant=request.tenant)
        form.tenant = request.tenant

    context = {
        "form": form,
        "maintenance_log": obj,
        "is_edit": True,
    }
    return render(request, "assets/asset_maintenance/asset_maintenance_log/form.html", context)


@require_POST
@tenant_admin_required
def asset_maintenance_log_delete(request, pk):
    obj = assets_object(request, AssetMaintenanceLog, pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Maintenance Log {number} deleted.")
    return redirect("assets:asset_maintenance_log_list")


@require_POST
@login_required
def asset_maintenance_log_submit_review(request, pk):
    obj = assets_object(request, AssetMaintenanceLog, pk)
    obj.submit_review()
    write_audit_log(request.user, obj, "update", changes={"action": "submit_review"}, tenant=request.tenant)
    messages.success(request, f"Log {obj.number} submitted for supervisory review.")
    return redirect("assets:asset_maintenance_log_detail", pk=obj.pk)


@require_POST
@login_required
def asset_maintenance_log_approve(request, pk):
    obj = assets_object(request, AssetMaintenanceLog, pk)
    obj.approve(request.user)
    write_audit_log(request.user, obj, "update", changes={"action": "approve"}, tenant=request.tenant)
    messages.success(request, f"Log {obj.number} approved.")
    return redirect("assets:asset_maintenance_log_detail", pk=obj.pk)


@require_POST
@tenant_admin_required
def asset_maintenance_log_post_gl(request, pk):
    obj = assets_object(request, AssetMaintenanceLog, pk)
    obj.post_to_gl(request.user)
    write_audit_log(request.user, obj, "update", changes={"action": "post_to_gl"}, tenant=request.tenant)
    messages.success(request, f"Maintenance Log {obj.number} posted to General Ledger and linked records updated.")
    return redirect("assets:asset_maintenance_log_detail", pk=obj.pk)
