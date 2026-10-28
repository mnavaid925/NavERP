"""Sales 8.18 — SalesSyncJob views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.IntegrationApiHub.SyncJobs import SalesSyncJobForm
from apps.sales.models.IntegrationApiHub.Connectors import SalesIntegrationConnector
from apps.sales.models.IntegrationApiHub.SyncJobs import (
    ENTITY_SCOPE_CHOICES,
    STATUS_CHOICES,
    SalesSyncJob,
)


@login_required
def ssj_list(request):
    tenant = request.tenant
    qs = SalesSyncJob.objects.filter(tenant=tenant).select_related("connector")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(filter_expression__icontains=q)
            | Q(connector__name__icontains=q)
        )

    connector_id = as_db_int(request.GET.get("connector", "").strip())
    if connector_id:
        qs = qs.filter(connector_id=connector_id)

    entity_scope = request.GET.get("entity_scope", "").strip()
    if entity_scope:
        qs = qs.filter(entity_scope=entity_scope)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    page_obj = paginate(request, qs, per_page=15)
    paginator = page_obj.paginator
    connectors = SalesIntegrationConnector.objects.filter(tenant=tenant)

    context = {
        "jobs": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "connector_id": connector_id,
        "entity_scope": entity_scope,
        "status": status,
        "connectors": connectors,
        "scope_choices": ENTITY_SCOPE_CHOICES,
        "status_choices": STATUS_CHOICES,
    }
    return render(request, "sales/integrationapihub/syncjobs/list.html", context)


@login_required
def ssj_detail(request, pk):
    job = get_object_or_404(
        SalesSyncJob.objects.filter(tenant=request.tenant).select_related("connector"),
        pk=pk,
    )
    recent_runs = job.sync_runs.all()[:15]
    context = {
        "job": job,
        "recent_runs": recent_runs,
    }
    return render(request, "sales/integrationapihub/syncjobs/detail.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def ssj_create(request):
    tenant = request.tenant
    initial = {}
    conn_param = as_db_int(request.GET.get("connector", "").strip())
    if conn_param:
        initial["connector"] = conn_param

    if request.method == "POST":
        form = SalesSyncJobForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=tenant)
            messages.success(request, f"Sync job '{obj.name}' created.")
            return redirect("sales:ssj_detail", pk=obj.pk)
    else:
        form = SalesSyncJobForm(tenant=tenant, initial=initial)

    context = {
        "form": form,
        "is_edit": False,
        "job": None,
    }
    return render(request, "sales/integrationapihub/syncjobs/form.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def ssj_edit(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesSyncJob.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = SalesSyncJobForm(request.POST, instance=obj, tenant=tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=tenant)
            messages.success(request, f"Sync job '{obj.name}' updated.")
            return redirect("sales:ssj_detail", pk=obj.pk)
    else:
        form = SalesSyncJobForm(instance=obj, tenant=tenant)

    context = {
        "form": form,
        "is_edit": True,
        "job": obj,
    }
    return render(request, "sales/integrationapihub/syncjobs/form.html", context)


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def ssj_delete(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesSyncJob.objects.filter(tenant=tenant), pk=pk)
    name = obj.name
    write_audit_log(request.user, obj, "delete", tenant=tenant)
    obj.delete()
    messages.success(request, f"Sync job '{name}' deleted.")
    return redirect("sales:ssj_list")


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def ssj_trigger(request, pk):
    """Trigger an honest simulated execution run for this sync job. Zero outbound HTTP."""
    tenant = request.tenant
    job = get_object_or_404(
        SalesSyncJob.objects.filter(tenant=tenant).select_related("connector"),
        pk=pk,
    )

    from apps.sales.models.IntegrationApiHub.SyncRuns import SalesSyncRun

    now = timezone.now()
    job.last_run_at = now
    job.total_runs_count += 1
    job.total_records_synced += 5
    job.save(update_fields=["last_run_at", "total_runs_count", "total_records_synced", "updated_at"])

    run = SalesSyncRun(
        tenant=tenant,
        connector=job.connector,
        job=job,
        run_type="manual",
        status="simulated",
        started_at=now,
        finished_at=now,
        records_read=5,
        records_written=5,
        records_failed=0,
        records_skipped=0,
        summary_payload={
            "job_name": job.name,
            "entity_scope": job.entity_scope,
            "direction": job.sync_direction,
            "conflict_policy": job.conflict_policy,
            "simulated": True,
        },
        triggered_by=request.user,
    )
    run.save()

    write_audit_log(request.user, job, "run", tenant=tenant)
    messages.success(request, f"Simulated sync execution run '{run.number}' triggered successfully for job '{job.name}'.")
    return redirect("sales:ssj_detail", pk=job.pk)
