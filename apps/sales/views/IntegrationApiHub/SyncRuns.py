"""Sales 8.18 — SalesSyncRun views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import as_db_int, paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.models.IntegrationApiHub.Connectors import SalesIntegrationConnector
from apps.sales.models.IntegrationApiHub.SyncJobs import SalesSyncJob
from apps.sales.models.IntegrationApiHub.SyncRuns import (
    RUN_TYPE_CHOICES,
    STATUS_CHOICES,
    SalesSyncRun,
)


@login_required
def ssr_list(request):
    tenant = request.tenant
    qs = (
        SalesSyncRun.objects.filter(tenant=tenant)
        .select_related("connector", "job", "triggered_by")
        .order_by("-started_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(error_log__icontains=q)
            | Q(connector__name__icontains=q)
            | Q(job__name__icontains=q)
        )

    connector_id = as_db_int(request.GET.get("connector", "").strip())
    if connector_id:
        qs = qs.filter(connector_id=connector_id)

    job_id = as_db_int(request.GET.get("job", "").strip())
    if job_id:
        qs = qs.filter(job_id=job_id)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    run_type = request.GET.get("run_type", "").strip()
    if run_type:
        qs = qs.filter(run_type=run_type)

    page_obj = paginate(request, qs, per_page=20)
    paginator = page_obj.paginator
    connectors = SalesIntegrationConnector.objects.filter(tenant=tenant)
    jobs = SalesSyncJob.objects.filter(tenant=tenant)

    context = {
        "runs": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "connector_id": connector_id,
        "job_id": job_id,
        "status": status,
        "run_type": run_type,
        "connectors": connectors,
        "jobs": jobs,
        "status_choices": STATUS_CHOICES,
        "run_type_choices": RUN_TYPE_CHOICES,
    }
    return render(request, "sales/integrationapihub/syncruns/list.html", context)


@login_required
def ssr_detail(request, pk):
    run = get_object_or_404(
        SalesSyncRun.objects.filter(tenant=request.tenant).select_related(
            "connector", "job", "triggered_by"
        ),
        pk=pk,
    )
    context = {"run": run}
    return render(request, "sales/integrationapihub/syncruns/detail.html", context)


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def ssr_delete(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesSyncRun.objects.filter(tenant=tenant), pk=pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=tenant)
    obj.delete()
    messages.success(request, f"Sync run log '{number}' deleted.")
    return redirect("sales:ssr_list")
