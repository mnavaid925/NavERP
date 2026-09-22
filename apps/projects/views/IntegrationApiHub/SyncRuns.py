"""Projects 7.18 — ProjectSyncRun views (append-only: list + detail + retry)."""
from datetime import datetime, time as dt_time, timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q

from apps.projects.models.IntegrationApiHub.Connectors import ProjectIntegrationConnector
from apps.projects.models.IntegrationApiHub.SyncJobs import ProjectSyncJob
from apps.projects.models.IntegrationApiHub.SyncRuns import SYNC_BACKOFF_SECONDS, ProjectSyncRun
from apps.projects.views._common import *


def _run_filters(request, qs):
    """Apply the shared run filters; `date_from`/`date_to` widen into a started_at datetime range."""
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(error_message__icontains=q))
    job_id = request.GET.get("job", "").strip()
    if job_id and job_id.isdigit():
        qs = qs.filter(job_id=job_id)
    connector_id = request.GET.get("connector", "").strip()
    if connector_id and connector_id.isdigit():
        qs = qs.filter(job__connector_id=connector_id)
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)
    trigger_source = request.GET.get("trigger_source", "").strip()
    if trigger_source:
        qs = qs.filter(trigger_source=trigger_source)
    date_from = request.GET.get("date_from", "").strip()
    if date_from:
        try:
            d = datetime.strptime(date_from, "%Y-%m-%d").date()
            qs = qs.filter(started_at__gte=timezone.make_aware(datetime.combine(d, dt_time.min)))
        except ValueError:
            pass
    date_to = request.GET.get("date_to", "").strip()
    if date_to:
        try:
            d = datetime.strptime(date_to, "%Y-%m-%d").date()
            qs = qs.filter(started_at__lte=timezone.make_aware(datetime.combine(d, dt_time.max)))
        except ValueError:
            pass
    return qs, {
        "q": q,
        "job_id": job_id,
        "connector_id": connector_id,
        "status": status,
        "trigger_source": trigger_source,
        "date_from": date_from,
        "date_to": date_to,
    }


@login_required
def syr_list(request):
    qs = ProjectSyncRun.objects.filter(tenant=request.tenant).select_related("job", "job__connector")
    qs, filters = _run_filters(request, qs)

    scope = ProjectSyncRun.objects.filter(tenant=request.tenant)
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    counts = scope.aggregate(
        pending=Count("id", filter=Q(status="pending")),
        running=Count("id", filter=Q(status="running")),
        failed=Count("id", filter=Q(status="failed")),
        partial=Count("id", filter=Q(status="partial")),
        simulated=Count("id", filter=Q(status="simulated")),
        failed_today=Count("id", filter=Q(status="failed", started_at__gte=today_start)),
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {
        "runs": page_obj.object_list,
        "page_obj": page_obj,
        "jobs": ProjectSyncJob.objects.filter(tenant=request.tenant),
        "connectors": ProjectIntegrationConnector.objects.filter(tenant=request.tenant),
        "status_choices": ProjectSyncRun.RUN_STATUS_CHOICES,
        "trigger_choices": ProjectSyncRun.TRIGGER_SOURCE_CHOICES,
        "stats": {
            "pending": counts["pending"] or 0,
            "running": counts["running"] or 0,
            "failed": counts["failed"] or 0,
            "partial": counts["partial"] or 0,
            "simulated": counts["simulated"] or 0,
            "failed_today": counts["failed_today"] or 0,
        },
    }
    ctx.update(filters)
    return render(request, "projects/integrationapihub/syncrun/list.html", ctx)


@login_required
def syr_detail(request, pk):
    run = get_object_or_404(
        ProjectSyncRun.objects.select_related("job", "job__connector", "triggered_by"),
        pk=pk,
        tenant=request.tenant,
    )
    return render(request, "projects/integrationapihub/syncrun/detail.html", {"run": run})


@login_required
@require_POST
@tenant_admin_required
def syr_retry(request, pk):
    """Requeue a failed/partial run: pending + attempt bump + backoff stamp. Performs NO HTTP."""
    run = get_object_or_404(ProjectSyncRun, pk=pk, tenant=request.tenant)
    run.status = "pending"
    run.attempt_no += 1
    slot = SYNC_BACKOFF_SECONDS[min(run.attempt_no, len(SYNC_BACKOFF_SECONDS) - 1)]
    run.next_retry_at = timezone.now() + timedelta(seconds=slot)
    run.save(update_fields=["status", "attempt_no", "next_retry_at", "updated_at"])
    write_audit_log(request.user, run, "retry", changes={"attempt_no": run.attempt_no})
    messages.success(request, f"Run {run.number} requeued (attempt {run.attempt_no}).")
    return redirect("projects:syr_detail", pk=run.pk)
