"""Projects 7.18 — ProjectSyncJob views."""
from django.core.paginator import Paginator
from django.db.models import Count, Q

from apps.projects.forms.IntegrationApiHub.SyncJobs import ProjectSyncJobForm
from apps.projects.models.IntegrationApiHub.Connectors import ProjectIntegrationConnector
from apps.projects.models.IntegrationApiHub.SyncJobs import ProjectSyncJob
from apps.projects.models.IntegrationApiHub.SyncRuns import ProjectSyncRun
from apps.projects.views._common import *


@login_required
def syj_list(request):
    qs = ProjectSyncJob.objects.filter(tenant=request.tenant).select_related("connector")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(number__icontains=q))
    connector_id = request.GET.get("connector", "").strip()
    if connector_id and connector_id.isdigit():
        qs = qs.filter(connector_id=connector_id)
    entity_scope = request.GET.get("entity_scope", "").strip()
    if entity_scope:
        qs = qs.filter(entity_scope=entity_scope)
    trigger_mode = request.GET.get("trigger_mode", "").strip()
    if trigger_mode:
        qs = qs.filter(trigger_mode=trigger_mode)
    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("active", "true", "1"):
        qs = qs.filter(is_active=True)
    elif is_active in ("inactive", "false", "0"):
        qs = qs.filter(is_active=False)

    counts = ProjectSyncJob.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        inactive=Count("id", filter=Q(is_active=False)),
    )
    runs_total = ProjectSyncRun.objects.filter(tenant=request.tenant).count()

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/integrationapihub/syncjob/list.html",
        {
            "jobs": page_obj.object_list,
            "page_obj": page_obj,
            "connectors": ProjectIntegrationConnector.objects.filter(tenant=request.tenant),
            "entity_choices": ProjectSyncJob.SYNC_ENTITY_CHOICES,
            "trigger_choices": ProjectSyncJob.TRIGGER_MODE_CHOICES,
            "conflict_choices": ProjectSyncJob.CONFLICT_POLICY_CHOICES,
            "status_choices": ProjectSyncRun.RUN_STATUS_CHOICES,
            "q": q,
            "connector_id": connector_id,
            "entity_scope": entity_scope,
            "trigger_mode": trigger_mode,
            "is_active": is_active,
            "stats": {
                "total": counts["total"] or 0,
                "active": counts["active"] or 0,
                "inactive": counts["inactive"] or 0,
                "runs_total": runs_total,
            },
        },
    )


@login_required
def syj_detail(request, pk):
    job = get_object_or_404(
        ProjectSyncJob.objects.select_related("connector"), pk=pk, tenant=request.tenant
    )
    runs = ProjectSyncRun.objects.filter(tenant=request.tenant, job=job).order_by("-started_at")[:20]
    return render(
        request,
        "projects/integrationapihub/syncjob/detail.html",
        {"job": job, "runs": runs, "connector": job.connector},
    )


def _syj_save(request, form, action):
    obj = form.save(commit=False)
    obj.tenant = request.tenant
    obj.save()
    form.save_m2m()
    write_audit_log(request.user, obj, action)
    return obj


@login_required
def syj_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    initial = None
    connector_id = request.GET.get("connector", "").strip()
    if connector_id.isdigit():
        connector = ProjectIntegrationConnector.objects.filter(
            tenant=request.tenant, pk=connector_id
        ).first()
        if connector is not None:
            initial = {"connector": connector}
    form = ProjectSyncJobForm(
        request.POST or None, tenant=request.tenant, initial=initial
    )
    if request.method == "POST" and form.is_valid():
        obj = _syj_save(request, form, "create")
        messages.success(request, f"Sync job {obj.number} created.")
        return redirect("projects:syj_detail", pk=obj.pk)
    return render(request, "projects/integrationapihub/syncjob/form.html", {"form": form})


@login_required
def syj_edit(request, pk):
    job = get_object_or_404(ProjectSyncJob, pk=pk, tenant=request.tenant)
    form = ProjectSyncJobForm(request.POST or None, instance=job, tenant=request.tenant)
    if request.method == "POST" and form.is_valid():
        obj = _syj_save(request, form, "update")
        messages.success(request, f"Sync job {obj.number} updated.")
        return redirect("projects:syj_detail", pk=obj.pk)
    return render(
        request,
        "projects/integrationapihub/syncjob/form.html",
        {"form": form, "is_edit": True, "job": job},
    )


@login_required
@require_POST
@tenant_admin_required
def syj_delete(request, pk):
    job = get_object_or_404(ProjectSyncJob, pk=pk, tenant=request.tenant)
    number = job.number
    job.delete()
    write_audit_log(request.user, None, "delete", changes={"sync_job": number}, tenant=request.tenant)
    messages.success(request, f"Sync job {number} deleted.")
    return redirect("projects:syj_list")


@login_required
@require_POST
def syj_toggle_active(request, pk):
    job = get_object_or_404(ProjectSyncJob, pk=pk, tenant=request.tenant)
    job.is_active = not job.is_active
    job.save(update_fields=["is_active", "updated_at"])
    write_audit_log(request.user, job, "toggle", changes={"is_active": job.is_active})
    return redirect("projects:syj_detail", pk=job.pk)


@login_required
@require_POST
def syj_run(request, pk):
    """Rehearse the job: records a 'simulated' run and bumps its counters. Performs NO outbound HTTP."""
    job = get_object_or_404(ProjectSyncJob.objects.select_related("connector"), pk=pk, tenant=request.tenant)
    now = timezone.now()
    ProjectSyncRun.record(
        job=job,
        status="simulated",
        trigger_source="manual",
        triggered_by=request.user,
        started_at=now,
        finished_at=now,
        error_message="Simulated run — no outbound request was made.",
    )
    job.run_count += 1
    job.last_run_at = now
    job.last_status = "simulated"
    job.save(update_fields=["run_count", "last_run_at", "last_status", "updated_at"])
    write_audit_log(request.user, job, "run")
    messages.info(request, f"Simulated run recorded for {job.number} (no request was sent).")
    return redirect("projects:syj_detail", pk=job.pk)

