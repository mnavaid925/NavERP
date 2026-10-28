"""Sales 8.18 — Integration & API Hub Dashboard & Category Views."""
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse

from apps.sales.models.IntegrationApiHub.Connectors import SalesIntegrationConnector
from apps.sales.models.IntegrationApiHub.SyncJobs import SalesSyncJob
from apps.sales.models.IntegrationApiHub.SyncRuns import SalesSyncRun


@login_required
def hub_dashboard(request):
    tenant = request.tenant
    connectors_qs = SalesIntegrationConnector.objects.filter(tenant=tenant)
    jobs_qs = SalesSyncJob.objects.filter(tenant=tenant)
    runs_qs = SalesSyncRun.objects.filter(tenant=tenant)

    connector_stats = connectors_qs.aggregate(
        total=Count("id"),
        healthy=Count("id", filter=Q(health_status="connected")),
    )
    connectors_count = connector_stats["total"] or 0
    healthy_count = connector_stats["healthy"] or 0

    job_stats = jobs_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
    )
    jobs_count = job_stats["total"] or 0
    active_jobs_count = job_stats["active"] or 0

    runs_count = runs_qs.count()

    category_counts_dict = dict(
        connectors_qs.values_list("category").annotate(total=Count("id"))
    )
    erp_count = category_counts_dict.get("erp", 0)
    marketing_count = category_counts_dict.get("marketing", 0)
    communication_count = category_counts_dict.get("communication", 0)
    bi_count = category_counts_dict.get("bi_warehouse", 0)
    esignature_count = category_counts_dict.get("esignature", 0)

    recent_runs = runs_qs.select_related("connector", "job").order_by("-started_at")[:8]
    erp_connectors = connectors_qs.filter(category="erp")
    marketing_connectors = connectors_qs.filter(category="marketing")
    communication_connectors = connectors_qs.filter(category="communication")
    bi_connectors = connectors_qs.filter(category="bi_warehouse")
    esignature_connectors = connectors_qs.filter(category="esignature")

    context = {
        "connectors_count": connectors_count,
        "jobs_count": jobs_count,
        "runs_count": runs_count,
        "healthy_count": healthy_count,
        "active_jobs_count": active_jobs_count,
        "recent_runs": recent_runs,
        "erp_connectors": erp_connectors,
        "marketing_connectors": marketing_connectors,
        "communication_connectors": communication_connectors,
        "bi_connectors": bi_connectors,
        "esignature_connectors": esignature_connectors,
        "erp_count": erp_count,
        "marketing_count": marketing_count,
        "communication_count": communication_count,
        "bi_count": bi_count,
        "esignature_count": esignature_count,
        "category_counts": category_counts_dict,
    }
    return render(request, "sales/integrationapihub/hub_dashboard.html", context)


@login_required
def sic_erp_list(request):
    return redirect(f"{reverse('sales:sic_list')}?category=erp")


@login_required
def sic_marketing_list(request):
    return redirect(f"{reverse('sales:sic_list')}?category=marketing")


@login_required
def sic_communication_list(request):
    return redirect(f"{reverse('sales:sic_list')}?category=communication")


@login_required
def sic_bi_list(request):
    return redirect(f"{reverse('sales:sic_list')}?category=bi_warehouse")


@login_required
def sic_esignature_list(request):
    return redirect(f"{reverse('sales:sic_list')}?category=esignature")
