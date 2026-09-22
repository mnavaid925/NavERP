"""Projects 7.18 — ProjectIntegrationConnector views."""
import secrets

from django.core.paginator import Paginator
from django.db.models import Count, Q

from apps.projects.forms.IntegrationApiHub.Connectors import (
    ConnectorTestForm,
    ProjectIntegrationConnectorForm,
)
from apps.projects.models.IntegrationApiHub.Connectors import ProjectIntegrationConnector
from apps.projects.models.IntegrationApiHub.FieldMappings import ConnectorFieldMapping
from apps.projects.models.IntegrationApiHub.SyncJobs import ProjectSyncJob
from apps.projects.models.IntegrationApiHub.SyncRuns import ProjectSyncRun
from apps.projects.models.ProjectInitiation.Projects import Project
from apps.projects.views._common import *


@login_required
def ixc_list(request, domain=None):
    """Connector register with search/filters/pagination; shared by the five domain routes."""
    qs = ProjectIntegrationConnector.objects.filter(tenant=request.tenant).select_related(
        "project", "owner", "notify_webhook"
    )
    if domain:
        qs = qs.filter(domain=domain)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(number__icontains=q) | Q(remote_scope_ref__icontains=q)
        )
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)
    provider = request.GET.get("provider", "").strip()
    if provider:
        qs = qs.filter(provider=provider)
    project_id = request.GET.get("project", "").strip()
    if project_id and project_id.isdigit():
        qs = qs.filter(project_id=project_id)
    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("active", "true", "1"):
        qs = qs.filter(is_active=True)
    elif is_active in ("inactive", "false", "0"):
        qs = qs.filter(is_active=False)

    scope = ProjectIntegrationConnector.objects.filter(tenant=request.tenant)
    if domain:
        scope = scope.filter(domain=domain)
    counts = scope.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        connected=Count("id", filter=Q(status="connected")),
        error=Count("id", filter=Q(status="error")),
        unverified=Count("id", filter=Q(status="unverified")),
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/integrationapihub/connector/list.html",
        {
            "connectors": page_obj.object_list,
            "page_obj": page_obj,
            "projects": Project.objects.filter(tenant=request.tenant),
            "domain_choices": ProjectIntegrationConnector.DOMAIN_CHOICES,
            "provider_choices": ProjectIntegrationConnector.PROVIDER_CHOICES,
            "status_choices": ProjectIntegrationConnector.STATUS_CHOICES,
            "domain": domain,
            "q": q,
            "status": status,
            "provider": provider,
            "project_id": project_id,
            "is_active": is_active,
            "stats": {
                "total": counts["total"] or 0,
                "active": counts["active"] or 0,
                "connected": counts["connected"] or 0,
                "error": counts["error"] or 0,
                "unverified": counts["unverified"] or 0,
                "due_rotation": 0,
            },
        },
    )


@login_required
def ixc_detail(request, pk):
    """Detail view for a connector with mappings, jobs, recent runs and the test form."""
    connector = get_object_or_404(
        ProjectIntegrationConnector.objects.select_related("project", "owner", "notify_webhook"),
        pk=pk,
        tenant=request.tenant,
    )
    mappings = ConnectorFieldMapping.objects.filter(tenant=request.tenant, connector=connector)[:20]
    jobs = ProjectSyncJob.objects.filter(tenant=request.tenant, connector=connector)
    recent_runs = ProjectSyncRun.objects.filter(
        tenant=request.tenant, job__connector=connector
    ).order_by("-started_at")[:15]

    revealed_credential = None
    reveal_data = request.session.pop("_ixc_cred_reveal", None)
    if reveal_data and reveal_data.get("pk") == connector.pk:
        revealed_credential = reveal_data.get("credential")

    return render(
        request,
        "projects/integrationapihub/connector/detail.html",
        {
            "connector": connector,
            "mappings": mappings,
            "jobs": jobs,
            "recent_runs": recent_runs,
            "test_form": ConnectorTestForm(),
            "revealed_credential": revealed_credential,
        },
    )


def _ixc_save(request, form, obj, action):
    """Persist a connector form and write the audit row."""
    obj = form.save(commit=False)
    obj.tenant = request.tenant
    obj.save()
    form.save_m2m()
    write_audit_log(request.user, obj, action)
    return obj


@login_required
def ixc_create(request):
    form = ProjectIntegrationConnectorForm(request.POST or None, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        obj = _ixc_save(request, form, None, "create")
        messages.success(request, f"Connector {obj.number} created.")
        return redirect("projects:ixc_detail", pk=obj.pk)
    return render(request, "projects/integrationapihub/connector/form.html", {"form": form})


@login_required
def ixc_edit(request, pk):
    connector = get_object_or_404(ProjectIntegrationConnector, pk=pk, tenant=request.tenant)
    form = ProjectIntegrationConnectorForm(
        request.POST or None, instance=connector, tenant=request.tenant
    )
    if request.method == "POST" and form.is_valid():
        obj = _ixc_save(request, form, connector, "update")
        messages.success(request, f"Connector {obj.number} updated.")
        return redirect("projects:ixc_detail", pk=obj.pk)
    return render(
        request,
        "projects/integrationapihub/connector/form.html",
        {"form": form, "is_edit": True, "connector": connector},
    )


@login_required
@require_POST
@tenant_admin_required
def ixc_delete(request, pk):
    connector = get_object_or_404(ProjectIntegrationConnector, pk=pk, tenant=request.tenant)
    number = connector.number
    connector.delete()
    write_audit_log(request.user, None, "delete", changes={"connector": number}, tenant=request.tenant)
    messages.success(request, f"Connector {number} deleted.")
    return redirect("projects:ixc_list")


@login_required
@require_POST
@tenant_admin_required
def ixc_rotate_credential(request, pk):
    connector = get_object_or_404(ProjectIntegrationConnector, pk=pk, tenant=request.tenant)
    new_secret = secrets.token_hex(32)
    connector.set_credential(new_secret)
    connector.save(update_fields=["credential", "updated_at"])
    request.session["_ixc_cred_reveal"] = {"pk": connector.pk, "credential": new_secret}
    write_audit_log(request.user, connector, "rotate")
    messages.success(request, f"Credential rotated for {connector.number}. It is shown once below.")
    return redirect("projects:ixc_detail", pk=connector.pk)


@login_required
@require_POST
def ixc_test(request, pk):
    """Simulated connection test: records a 'simulated' run on the connector's first job, no HTTP."""
    connector = get_object_or_404(ProjectIntegrationConnector, pk=pk, tenant=request.tenant)
    job = ProjectSyncJob.objects.filter(tenant=request.tenant, connector=connector).first()
    if job is None:
        messages.warning(request, "Create a sync job for this connector before running a test.")
        return redirect("projects:ixc_detail", pk=connector.pk)
    ProjectSyncRun.record(
        job=job,
        status="simulated",
        trigger_source="manual",
        triggered_by=request.user,
        error_message="Simulated connection test — no outbound request was made.",
    )
    connector.last_sync_at = timezone.now()
    connector.save(update_fields=["last_sync_at", "updated_at"])
    write_audit_log(request.user, connector, "test")
    messages.info(request, f"Simulated test recorded for {connector.number} (no request was sent).")
    return redirect("projects:ixc_detail", pk=connector.pk)


@login_required
@require_POST
def ixc_toggle_active(request, pk):
    connector = get_object_or_404(ProjectIntegrationConnector, pk=pk, tenant=request.tenant)
    connector.is_active = not connector.is_active
    connector.save(update_fields=["is_active", "updated_at"])
    write_audit_log(request.user, connector, "toggle", changes={"is_active": connector.is_active})
    return redirect("projects:ixc_detail", pk=connector.pk)



@login_required
def connector_health(request, pk):
    """One connector's health lens: status, run outcome, and the registers that drive it."""
    connector = get_object_or_404(
        ProjectIntegrationConnector.objects.select_related("project", "owner", "notify_webhook"),
        pk=pk,
        tenant=request.tenant,
    )
    jobs = ProjectSyncJob.objects.filter(tenant=request.tenant, connector=connector)
    mappings = ConnectorFieldMapping.objects.filter(tenant=request.tenant, connector=connector)
    runs = ProjectSyncRun.objects.filter(tenant=request.tenant, job__connector=connector)
    recent_runs = runs.order_by("-started_at")[:15]
    total_runs = runs.count()
    failed_runs = runs.filter(status="failed").count()
    success_runs = runs.filter(status="success").count()
    success_rate = round((success_runs / total_runs) * 100) if total_runs else 0

    return render(
        request,
        "projects/integrationapihub/boards/connector_health.html",
        {
            "connector": connector,
            "recent_runs": recent_runs,
            "jobs": jobs,
            "mappings": mappings,
            "stats": {
                "total_runs": total_runs,
                "failed_runs": failed_runs,
                "success_rate": success_rate,
                "last_success_at": connector.last_success_at,
            },
        },
    )

