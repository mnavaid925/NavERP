from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.bi.models.EtlPipelines.EtlPipelineRuns import EtlPipelineRun
from apps.bi.models.EtlPipelines.EtlPipelines import EtlPipeline
from apps.bi.views._common import bi_object, bi_scope, csv_export_response, csv_safe


@login_required
def etl_pipeline_run_list(request):
    queryset = bi_scope(EtlPipelineRun.objects.all(), request)

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(pipeline__name__icontains=q)
            | Q(error_message__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    trigger_filter = request.GET.get("trigger_type", "").strip()
    if trigger_filter:
        queryset = queryset.filter(trigger_type=trigger_filter)

    pipeline_filter = request.GET.get("pipeline_id", "").strip()
    if pipeline_filter and pipeline_filter.isdigit():
        queryset = queryset.filter(pipeline_id=int(pipeline_filter))

    if request.GET.get("export") == "csv":
        rows = [
            [
                csv_safe(r.number),
                csv_safe(r.pipeline.name),
                csv_safe(r.get_trigger_type_display()),
                csv_safe(r.get_status_display()),
                csv_safe(r.started_at.isoformat() if r.started_at else ""),
                csv_safe(r.duration_seconds),
                csv_safe(r.records_in),
                csv_safe(r.records_transformed),
                csv_safe(r.records_out),
                csv_safe(r.records_rejected),
                csv_safe("Yes" if r.sla_missed else "No"),
            ]
            for r in queryset.select_related("pipeline")
        ]
        return csv_export_response(
            request,
            filename="etl_runs.csv",
            headers=["Run Number", "Pipeline", "Trigger", "Status", "Started At", "Duration (s)", "Records In", "Transformed", "Records Out", "Rejected", "SLA Missed"],
            rows=rows,
        )

    base_scope = bi_scope(EtlPipelineRun.objects.all(), request)
    counts = base_scope.aggregate(
        total_count=Count("id"),
        success_count=Count("id", filter=Q(status="completed")),
        failed_count=Count("id", filter=Q(status__in=["failed", "timed_out"])),
    )
    total_count = counts["total_count"]
    success_count = counts["success_count"]
    failed_count = counts["failed_count"]

    paginator = Paginator(
        queryset.select_related("pipeline", "version"),
        20,
    )
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    pipelines = bi_scope(EtlPipeline.objects.all(), request).only("id", "name", "number").order_by("name")

    context = {
        "runs": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "status_filter": status_filter,
        "trigger_filter": trigger_filter,
        "pipeline_filter": pipeline_filter,
        "status_choices": EtlPipelineRun.STATUS_CHOICES,
        "trigger_type_choices": EtlPipelineRun.TRIGGER_TYPE_CHOICES,
        "pipelines": pipelines,
        "total_count": total_count,
        "success_count": success_count,
        "failed_count": failed_count,
    }
    return render(request, "bi/etl_pipelines/etl_pipeline_run/list.html", context)


@login_required
def etl_pipeline_run_detail(request, pk):
    run = bi_object(
        request,
        EtlPipelineRun,
        pk,
        select_related=("pipeline", "version"),
    )
    context = {
        "run": run,
        "pipeline": run.pipeline,
        "version": run.version,
    }
    return render(request, "bi/etl_pipelines/etl_pipeline_run/detail.html", context)
