"""Sales 8.18 — SalesIntegrationConnector views."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import paginate
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.IntegrationApiHub.Connectors import SalesIntegrationConnectorForm
from apps.sales.models.IntegrationApiHub.Connectors import (
    AUTH_METHOD_CHOICES,
    CATEGORY_CHOICES,
    ENVIRONMENT_CHOICES,
    HEALTH_STATUS_CHOICES,
    PROVIDER_CHOICES,
    SalesIntegrationConnector,
)


@login_required
def sic_list(request):
    tenant = request.tenant
    qs = SalesIntegrationConnector.objects.filter(tenant=tenant)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(remote_scope_ref__icontains=q)
            | Q(notes__icontains=q)
        )

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    provider = request.GET.get("provider", "").strip()
    if provider:
        qs = qs.filter(provider=provider)

    health_status = request.GET.get("health_status", "").strip()
    if health_status:
        qs = qs.filter(health_status=health_status)

    page_obj = paginate(request, qs, per_page=15)
    paginator = page_obj.paginator

    context = {
        "connectors": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "category": category,
        "provider": provider,
        "health_status": health_status,
        "category_choices": CATEGORY_CHOICES,
        "provider_choices": PROVIDER_CHOICES,
        "health_choices": HEALTH_STATUS_CHOICES,
    }
    return render(request, "sales/integrationapihub/connectors/list.html", context)


@login_required
def sic_detail(request, pk):
    connector = get_object_or_404(
        SalesIntegrationConnector.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    field_mappings = connector.field_mappings.all()
    sync_jobs = connector.sync_jobs.all()
    recent_runs = connector.sync_runs.all()[:10]

    context = {
        "connector": connector,
        "field_mappings": field_mappings,
        "sync_jobs": sync_jobs,
        "recent_runs": recent_runs,
    }
    return render(request, "sales/integrationapihub/connectors/detail.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sic_create(request):
    tenant = request.tenant
    if request.method == "POST":
        form = SalesIntegrationConnectorForm(request.POST, tenant=tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = tenant
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=tenant)
            messages.success(request, f"Integration connector '{obj.name}' created.")
            return redirect("sales:sic_detail", pk=obj.pk)
    else:
        form = SalesIntegrationConnectorForm(tenant=tenant)

    context = {
        "form": form,
        "is_edit": False,
        "connector": None,
    }
    return render(request, "sales/integrationapihub/connectors/form.html", context)


@login_required
@tenant_admin_required
@transaction.atomic
def sic_edit(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesIntegrationConnector.objects.filter(tenant=tenant), pk=pk)
    if request.method == "POST":
        form = SalesIntegrationConnectorForm(request.POST, instance=obj, tenant=tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=tenant)
            messages.success(request, f"Integration connector '{obj.name}' updated.")
            return redirect("sales:sic_detail", pk=obj.pk)
    else:
        form = SalesIntegrationConnectorForm(instance=obj, tenant=tenant)

    context = {
        "form": form,
        "is_edit": True,
        "connector": obj,
    }
    return render(request, "sales/integrationapihub/connectors/form.html", context)


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def sic_delete(request, pk):
    tenant = request.tenant
    obj = get_object_or_404(SalesIntegrationConnector.objects.filter(tenant=tenant), pk=pk)
    name = obj.name
    write_audit_log(request.user, obj, "delete", tenant=tenant)
    obj.delete()
    messages.success(request, f"Integration connector '{name}' deleted.")
    return redirect("sales:sic_list")


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def sic_test(request, pk):
    """Simulated ping/health diagnostic test. Zero outbound HTTP."""
    tenant = request.tenant
    obj = get_object_or_404(SalesIntegrationConnector.objects.filter(tenant=tenant), pk=pk)

    from apps.sales.models.IntegrationApiHub.SyncRuns import SalesSyncRun

    obj.last_health_check_at = timezone.now()
    if obj.is_active:
        obj.health_status = "connected"
        obj.last_error_message = ""
    else:
        obj.health_status = "offline"
        obj.last_error_message = "Connector is currently inactive/paused."
    obj.save(update_fields=["last_health_check_at", "health_status", "last_error_message"])

    # Create audit run log
    run = SalesSyncRun(
        tenant=tenant,
        connector=obj,
        run_type="test_ping",
        status="simulated",
        finished_at=timezone.now(),
        records_read=1,
        records_written=1,
        summary_payload={"ping_ms": 35, "result": "simulated_healthy_response", "provider": obj.provider},
        triggered_by=request.user,
    )
    run.save()

    write_audit_log(request.user, obj, "test", tenant=tenant)
    messages.success(request, f"Simulated test ping successful for '{obj.name}'. Status set to '{obj.get_health_status_display()}'.")
    return redirect("sales:sic_detail", pk=obj.pk)
