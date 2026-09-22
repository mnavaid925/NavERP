"""Projects 7.18 — computed integration boards (no new tables)."""
from django.core.paginator import Paginator
from django.db.models import Count, Q

from apps.projects.models.IntegrationApiHub.Connectors import ProjectIntegrationConnector
from apps.projects.models.IntegrationApiHub.FieldMappings import ConnectorFieldMapping
from apps.projects.models.IntegrationApiHub.SyncJobs import ProjectSyncJob
from apps.projects.models.IntegrationApiHub.SyncRuns import ProjectSyncRun
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views.IntegrationApiHub.SyncRuns import _run_filters
from apps.projects.views._common import *


@login_required
def integration_hub(request):
    """The hub landing: connector health by domain, today's sync activity, and recent runs."""
    tenant = request.tenant
    connectors = ProjectIntegrationConnector.objects.filter(tenant=tenant).select_related("project", "owner")

    conn_counts = connectors.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        connected=Count("id", filter=Q(status="connected")),
        error=Count("id", filter=Q(status="error")),
    )
    # ONE cross-tab GROUP BY instead of a per-domain count loop + two separate pivots.
    pivot_rows = list(
        connectors.values("domain", "status").annotate(c=Count("id"))
    )
    by_status = {}
    by_domain = {}
    for row in pivot_rows:
        by_status[row["status"]] = by_status.get(row["status"], 0) + row["c"]
        by_domain[row["domain"]] = by_domain.get(row["domain"], 0) + row["c"]

    domains = []
    for value, label in ProjectIntegrationConnector.DOMAIN_CHOICES:
        total = connected = failing = 0
        for row in pivot_rows:
            if row["domain"] != value:
                continue
            total += row["c"]
            if row["status"] == "connected":
                connected += row["c"]
            elif row["status"] == "error":
                failing += row["c"]
        domains.append({
            "value": value,
            "label": label,
            "total": total,
            "connected": connected,
            "failing": failing,
        })

    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    runs_agg = ProjectSyncRun.objects.filter(tenant=tenant).aggregate(
        runs_today=Count("id", filter=Q(started_at__gte=today_start)),
        failed_today=Count("id", filter=Q(status="failed", started_at__gte=today_start)),
    )
    runs_today = runs_agg["runs_today"] or 0
    failed_today = runs_agg["failed_today"] or 0
    jobs_active = ProjectSyncJob.objects.filter(tenant=tenant, is_active=True).count()
    mappings_total = ConnectorFieldMapping.objects.filter(tenant=tenant).count()
    credentials_due = connectors.filter(is_active=True, status__in=("error", "disconnected")).count()

    recent_runs = ProjectSyncRun.objects.filter(tenant=tenant).select_related("job", "job__connector")[:10]

    return render(
        request,
        "projects/integrationapihub/boards/integration_hub.html",
        {
            "stats": {
                "connectors_total": conn_counts["total"] or 0,
                "by_domain": by_domain,
                "by_status": by_status,
                "runs_today": runs_today,
                "failed_today": failed_today,
                "jobs_active": jobs_active,
                "mappings_total": mappings_total,
                "credentials_due": credentials_due,
            },
            "domains": domains,
            "connectors": connectors.order_by("-created_at")[:50],
            "recent_runs": recent_runs,
            "projects": Project.objects.filter(tenant=tenant),
        },
    )


@login_required
def sync_monitor(request):
    """A live heat table over the sync-run log with the shared run filters."""
    tenant = request.tenant
    qs = ProjectSyncRun.objects.filter(tenant=tenant).select_related("job", "job__connector")
    qs, filters = _run_filters(request, qs)

    scope = ProjectSyncRun.objects.filter(tenant=tenant)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    counts = scope.aggregate(
        total=Count("id"),
        failed=Count("id", filter=Q(status="failed")),
        success=Count("id", filter=Q(status="success")),
        simulated=Count("id", filter=Q(status="simulated")),
        failed_today=Count("id", filter=Q(status="failed", started_at__gte=today_start)),
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {
        "runs": page_obj.object_list,
        "page_obj": page_obj,
        "jobs": ProjectSyncJob.objects.filter(tenant=tenant),
        "connectors": ProjectIntegrationConnector.objects.filter(tenant=tenant),
        "status_choices": ProjectSyncRun.RUN_STATUS_CHOICES,
        "stats": {
            "total": counts["total"] or 0,
            "failed": counts["failed"] or 0,
            "success": counts["success"] or 0,
            "simulated": counts["simulated"] or 0,
            "failed_today": counts["failed_today"] or 0,
        },
    }
    ctx.update(filters)
    return render(request, "projects/integrationapihub/boards/sync_monitor.html", ctx)
