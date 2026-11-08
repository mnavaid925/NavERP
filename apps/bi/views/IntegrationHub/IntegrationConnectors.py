from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.IntegrationHub.IntegrationConnectors import IntegrationConnectorForm
from apps.bi.models.IntegrationHub.IntegrationConnectors import IntegrationConnector
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def integration_connector_list(request):
    qs = bi_scope(IntegrationConnector.objects.all(), request).select_related("created_by")

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        error=Count("id", filter=Q(status="error") | Q(health_status="unreachable")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    error_count = counts["error"] or 0

    # Search query
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(slug__icontains=q)
            | Q(description__icontains=q)
        )

    # Filters
    connector_type = request.GET.get("connector_type", "").strip()
    if connector_type:
        qs = qs.filter(connector_type=connector_type)

    target_system = request.GET.get("target_system", "").strip()
    if target_system:
        qs = qs.filter(target_system=target_system)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "connectors": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "error_count": error_count,
        "search_query": q,
        "connector_type": connector_type,
        "target_system": target_system,
        "status": status,
        "type_choices": IntegrationConnector.CONNECTOR_TYPE_CHOICES,
        "target_choices": IntegrationConnector.TARGET_SYSTEM_CHOICES,
        "status_choices": IntegrationConnector.STATUS_CHOICES,
    }
    return render(
        request,
        "bi/integration_hub/integration_connector/list.html",
        context,
    )


@login_required
def integration_connector_detail(request, pk):
    connector = bi_object(
        request,
        IntegrationConnector,
        pk,
        select_related=("created_by",),
    )
    context = {
        "connector": connector,
    }
    return render(
        request,
        "bi/integration_hub/integration_connector/detail.html",
        context,
    )


@login_required
def integration_connector_create(request):
    if request.method == "POST":
        form = IntegrationConnectorForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            connector = form.save(commit=False)
            connector.tenant = request.tenant
            connector.created_by = request.user
            connector.save()

            write_audit_log(
                request.user,
                connector,
                "create",
                tenant=request.tenant,
            )
            messages.success(request, f"Integration connector '{connector.name}' created successfully.")
            return redirect("bi:integration_connector_detail", pk=connector.pk)
    else:
        form = IntegrationConnectorForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_create": True,
    }
    return render(
        request,
        "bi/integration_hub/integration_connector/form.html",
        context,
    )


@login_required
def integration_connector_edit(request, pk):
    connector = bi_object(request, IntegrationConnector, pk)

    if request.method == "POST":
        form = IntegrationConnectorForm(
            request.POST,
            instance=connector,
            tenant=request.tenant,
        )
        if form.is_valid():
            connector = form.save()
            write_audit_log(
                request.user,
                connector,
                "update",
                tenant=request.tenant,
            )
            messages.success(request, f"Integration connector '{connector.name}' updated successfully.")
            return redirect("bi:integration_connector_detail", pk=connector.pk)
    else:
        form = IntegrationConnectorForm(
            instance=connector,
            tenant=request.tenant,
        )

    context = {
        "form": form,
        "connector": connector,
        "is_create": False,
    }
    return render(
        request,
        "bi/integration_hub/integration_connector/form.html",
        context,
    )


@login_required
@require_POST
def integration_connector_delete(request, pk):
    connector = bi_object(request, IntegrationConnector, pk)
    name = connector.name
    write_audit_log(
        request.user,
        connector,
        "delete",
        tenant=request.tenant,
    )
    connector.delete()

    messages.success(request, f"Integration connector '{name}' deleted successfully.")
    return redirect("bi:integration_connector_list")


@login_required
@require_POST
def integration_connector_ping(request, pk):
    connector = bi_object(request, IntegrationConnector, pk)
    connector.last_heartbeat_at = timezone.now()
    connector.health_status = "healthy"
    connector.status = "active"
    connector.error_message = ""
    connector.total_messages_processed = F("total_messages_processed") + 1
    connector.updated_at = timezone.now()
    connector.save(
        update_fields=[
            "last_heartbeat_at",
            "health_status",
            "status",
            "error_message",
            "total_messages_processed",
            "updated_at",
        ]
    )

    write_audit_log(
        request.user,
        connector,
        "action",
        changes={"health_status": "healthy"},
        tenant=request.tenant,
    )
    messages.success(request, f"Heartbeat ping successful for '{connector.name}'. Channel is healthy.")
    return redirect("bi:integration_connector_detail", pk=connector.pk)
