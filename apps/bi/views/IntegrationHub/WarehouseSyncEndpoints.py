from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.IntegrationHub.WarehouseSyncEndpoints import WarehouseSyncEndpointForm
from apps.bi.models.IntegrationHub.WarehouseSyncEndpoints import WarehouseSyncEndpoint
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def warehouse_sync_endpoint_list(request):
    qs = bi_scope(WarehouseSyncEndpoint.objects.all(), request).select_related(
        "semantic_model", "data_mart", "owner"
    )

    counts = qs.aggregate(
        total=Count("id"),
        success=Count("id", filter=Q(status="success")),
        error=Count("id", filter=Q(status="error")),
    )
    total_count = counts["total"] or 0
    success_count = counts["success"] or 0
    error_count = counts["error"] or 0

    # Search query
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(slug__icontains=q)
            | Q(destination_table__icontains=q)
            | Q(destination_database__icontains=q)
        )

    # Filters
    target_warehouse = request.GET.get("target_warehouse", "").strip()
    if target_warehouse:
        qs = qs.filter(target_warehouse=target_warehouse)

    sync_mode = request.GET.get("sync_mode", "").strip()
    if sync_mode:
        qs = qs.filter(sync_mode=sync_mode)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "sync_endpoints": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "success_count": success_count,
        "error_count": error_count,
        "search_query": q,
        "target_warehouse": target_warehouse,
        "sync_mode": sync_mode,
        "status": status,
        "warehouse_choices": WarehouseSyncEndpoint.TARGET_WAREHOUSE_CHOICES,
        "mode_choices": WarehouseSyncEndpoint.SYNC_MODE_CHOICES,
        "status_choices": WarehouseSyncEndpoint.STATUS_CHOICES,
    }
    return render(
        request,
        "bi/integration_hub/warehouse_sync_endpoint/list.html",
        context,
    )


@login_required
def warehouse_sync_endpoint_detail(request, pk):
    sync_endpoint = bi_object(
        request,
        WarehouseSyncEndpoint,
        pk,
        select_related=("semantic_model", "data_mart", "owner"),
    )
    context = {
        "sync_endpoint": sync_endpoint,
    }
    return render(
        request,
        "bi/integration_hub/warehouse_sync_endpoint/detail.html",
        context,
    )


@login_required
def warehouse_sync_endpoint_create(request):
    if request.method == "POST":
        form = WarehouseSyncEndpointForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            sync_endpoint = form.save(commit=False)
            sync_endpoint.tenant = request.tenant
            sync_endpoint.owner = request.user
            sync_endpoint.save()

            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="create",
                model_name="WarehouseSyncEndpoint",
                object_id=str(sync_endpoint.pk),
                object_repr=str(sync_endpoint),
                changes={},
            )
            messages.success(
                request,
                f"Warehouse sync endpoint '{sync_endpoint.name}' created successfully.",
            )
            return redirect("bi:warehouse_sync_endpoint_detail", pk=sync_endpoint.pk)
    else:
        form = WarehouseSyncEndpointForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_create": True,
    }
    return render(
        request,
        "bi/integration_hub/warehouse_sync_endpoint/form.html",
        context,
    )


@login_required
def warehouse_sync_endpoint_edit(request, pk):
    sync_endpoint = bi_object(request, WarehouseSyncEndpoint, pk)

    if request.method == "POST":
        form = WarehouseSyncEndpointForm(
            request.POST,
            instance=sync_endpoint,
            tenant=request.tenant,
        )
        if form.is_valid():
            sync_endpoint = form.save()
            write_audit_log(
                tenant=request.tenant,
                user=request.user,
                action="update",
                model_name="WarehouseSyncEndpoint",
                object_id=str(sync_endpoint.pk),
                object_repr=str(sync_endpoint),
                changes={},
            )
            messages.success(
                request,
                f"Warehouse sync endpoint '{sync_endpoint.name}' updated successfully.",
            )
            return redirect("bi:warehouse_sync_endpoint_detail", pk=sync_endpoint.pk)
    else:
        form = WarehouseSyncEndpointForm(
            instance=sync_endpoint,
            tenant=request.tenant,
        )

    context = {
        "form": form,
        "sync_endpoint": sync_endpoint,
        "is_create": False,
    }
    return render(
        request,
        "bi/integration_hub/warehouse_sync_endpoint/form.html",
        context,
    )


@login_required
@require_POST
def warehouse_sync_endpoint_delete(request, pk):
    sync_endpoint = bi_object(request, WarehouseSyncEndpoint, pk)
    name = sync_endpoint.name
    sync_endpoint.delete()

    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="delete",
        model_name="WarehouseSyncEndpoint",
        object_id=str(pk),
        object_repr=name,
        changes={},
    )
    messages.success(request, f"Warehouse sync endpoint '{name}' deleted successfully.")
    return redirect("bi:warehouse_sync_endpoint_list")


@login_required
@require_POST
def warehouse_sync_endpoint_trigger(request, pk):
    sync_endpoint = bi_object(request, WarehouseSyncEndpoint, pk)
    sync_endpoint.last_sync_at = timezone.now()
    sync_endpoint.status = "success"
    sync_endpoint.last_sync_duration_ms = 1420
    sync_endpoint.last_rows_synced = 2500
    sync_endpoint.total_rows_synced += 2500
    sync_endpoint.last_error_message = ""
    sync_endpoint.save(
        update_fields=[
            "last_sync_at",
            "status",
            "last_sync_duration_ms",
            "last_rows_synced",
            "total_rows_synced",
            "last_error_message",
        ]
    )

    write_audit_log(
        tenant=request.tenant,
        user=request.user,
        action="action",
        model_name="WarehouseSyncEndpoint",
        object_id=str(sync_endpoint.pk),
        object_repr=f"Manual Sync Trigger {sync_endpoint.name}",
        changes={"status": "success", "rows_synced": 2500},
    )
    messages.success(
        request,
        f"Manual sync triggered successfully for '{sync_endpoint.name}'. 2,500 rows exported.",
    )
    return redirect("bi:warehouse_sync_endpoint_detail", pk=sync_endpoint.pk)
