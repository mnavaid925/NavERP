import uuid
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.IntegrationApi.IntegrationSyncJobs import IntegrationSyncJobForm
from apps.ecommerce.models.IntegrationApi.EcommerceConnectors import EcommerceConnector
from apps.ecommerce.models.IntegrationApi.IntegrationSyncJobs import IntegrationSyncJob
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def integration_sync_job_list(request):
    qs = ecommerce_scope(IntegrationSyncJob.objects.all(), request).select_related("connector")

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(batch_id__icontains=search_query)
            | Q(connector__name__icontains=search_query)
            | Q(error_summary__icontains=search_query)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    entity_filter = request.GET.get("entity", "").strip()
    if entity_filter:
        qs = qs.filter(sync_entity=entity_filter)

    direction_filter = request.GET.get("direction", "").strip()
    if direction_filter:
        qs = qs.filter(direction=direction_filter)

    trigger_filter = request.GET.get("trigger", "").strip()
    if trigger_filter:
        qs = qs.filter(trigger_type=trigger_filter)

    connector_filter = request.GET.get("connector", "").strip()
    if connector_filter:
        qs = qs.filter(connector_id=connector_filter)

    stats = qs.aggregate(
        total_count=Count("id"),
        running_count=Count("id", filter=Q(status="running")),
        failed_count=Count("id", filter=Q(status="failed")),
        completed_count=Count("id", filter=Q(status="completed")),
    )
    total_count = stats["total_count"]
    running_count = stats["running_count"]
    failed_count = stats["failed_count"]
    completed_count = stats["completed_count"]

    connectors = ecommerce_scope(EcommerceConnector.objects.all(), request).order_by("name")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "sync_jobs": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "running_count": running_count,
        "failed_count": failed_count,
        "completed_count": completed_count,
        "connectors": connectors,
        "search_query": search_query,
        "q": search_query,
        "status_filter": status_filter,
        "entity_filter": entity_filter,
        "direction_filter": direction_filter,
        "trigger_filter": trigger_filter,
        "connector_filter": connector_filter,
        "status_choices": IntegrationSyncJob.STATUS_CHOICES,
        "entity_choices": IntegrationSyncJob.SYNC_ENTITY_CHOICES,
        "direction_choices": IntegrationSyncJob.DIRECTION_CHOICES,
        "trigger_choices": IntegrationSyncJob.TRIGGER_TYPE_CHOICES,
    }
    return render(request, "ecommerce/integration_api/integration_sync_job/list.html", context)


# Route alias
integrationsyncjob_list = integration_sync_job_list


@login_required
def integration_sync_job_detail(request, pk):
    sync_job = ecommerce_object(
        request,
        IntegrationSyncJob,
        pk,
        select_related=("connector", "triggered_by", "parent_job"),
    )
    child_retries = sync_job.child_retries.all().order_by("-created_at")[:20]

    context = {
        "sync_job": sync_job,
        "child_retries": child_retries,
    }
    return render(request, "ecommerce/integration_api/integration_sync_job/detail.html", context)


# Route alias
integrationsyncjob_detail = integration_sync_job_detail


@login_required
def integration_sync_job_create(request):
    if request.method == "POST":
        form = IntegrationSyncJobForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            sync_job = form.save(commit=False)
            sync_job.tenant = request.tenant
            sync_job.triggered_by = request.user
            if not sync_job.batch_id:
                sync_job.batch_id = str(uuid.uuid4())[:8]

            # Auto-execute simulation
            sync_job.status = "completed"
            sync_job.started_at = timezone.now()
            sync_job.finished_at = timezone.now()
            sync_job.duration_seconds = Decimal("1.25")
            sync_job.records_total = 10
            sync_job.records_processed = 10
            sync_job.records_succeeded = 10
            sync_job.records_failed = 0
            sync_job.save()

            write_audit_log(
                request.user,
                sync_job,
                "create",
                changes={
                    "connector": sync_job.connector.name,
                    "sync_entity": sync_job.sync_entity,
                    "status": sync_job.status,
                },
                tenant=request.tenant,
            )
            messages.success(request, f"Sync Job '{sync_job.number}' queued and executed successfully.")
            return redirect("ecommerce:integrationsyncjob_detail", pk=sync_job.pk)
    else:
        initial = {}
        connector_id = request.GET.get("connector")
        if connector_id:
            initial["connector"] = connector_id
        form = IntegrationSyncJobForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "sync_job": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/integration_api/integration_sync_job/form.html", context)


# Route alias
integrationsyncjob_create = integration_sync_job_create


@login_required
def integration_sync_job_edit(request, pk):
    sync_job = ecommerce_object(request, IntegrationSyncJob, pk)

    if request.method == "POST":
        form = IntegrationSyncJobForm(request.POST, instance=sync_job, tenant=request.tenant)
        if form.is_valid():
            sync_job = form.save()
            write_audit_log(
                request.user,
                sync_job,
                "update",
                changes={"status": sync_job.status, "sync_entity": sync_job.sync_entity},
                tenant=request.tenant,
            )
            messages.success(request, f"Sync Job '{sync_job.number}' updated successfully.")
            return redirect("ecommerce:integrationsyncjob_detail", pk=sync_job.pk)
    else:
        form = IntegrationSyncJobForm(instance=sync_job, tenant=request.tenant)

    context = {
        "form": form,
        "sync_job": sync_job,
        "is_edit": True,
    }
    return render(request, "ecommerce/integration_api/integration_sync_job/form.html", context)


# Route alias
integrationsyncjob_edit = integration_sync_job_edit


@login_required
@require_POST
def integration_sync_job_delete(request, pk):
    sync_job = ecommerce_object(request, IntegrationSyncJob, pk)
    number = sync_job.number
    write_audit_log(
        request.user,
        sync_job,
        "delete",
        changes={"number": number},
        tenant=request.tenant,
    )
    sync_job.delete()
    messages.success(request, f"Sync Job '{number}' deleted.")
    return redirect("ecommerce:integrationsyncjob_list")


# Route alias
integrationsyncjob_delete = integration_sync_job_delete


@login_required
@require_POST
def integration_sync_job_retry(request, pk):
    parent_job = ecommerce_object(request, IntegrationSyncJob, pk)

    retry_job = IntegrationSyncJob.objects.create(
        tenant=request.tenant,
        connector=parent_job.connector,
        sync_entity=parent_job.sync_entity,
        direction=parent_job.direction,
        status="completed",
        trigger_type="manual",
        batch_id=f"retry-{parent_job.batch_id or str(uuid.uuid4())[:8]}",
        records_total=parent_job.records_total or 5,
        records_processed=parent_job.records_total or 5,
        records_succeeded=parent_job.records_total or 5,
        records_failed=0,
        started_at=timezone.now(),
        finished_at=timezone.now(),
        duration_seconds=Decimal("0.85"),
        payload_preview=parent_job.payload_preview,
        retry_count=parent_job.retry_count + 1,
        max_retries=parent_job.max_retries,
        parent_job=parent_job,
        triggered_by=request.user,
    )

    write_audit_log(
        request.user,
        retry_job,
        "retry_sync",
        changes={"parent_job": parent_job.number, "new_job": retry_job.number},
        tenant=request.tenant,
    )
    messages.success(request, f"Retry job '{retry_job.number}' initiated and completed successfully.")
    return redirect("ecommerce:integrationsyncjob_detail", pk=retry_job.pk)


# Route alias
integrationsyncjob_retry = integration_sync_job_retry
