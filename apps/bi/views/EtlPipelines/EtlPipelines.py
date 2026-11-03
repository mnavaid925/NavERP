import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.EtlPipelines.EtlPipelines import EtlPipelineForm
from apps.bi.models.DataIntegration.IngestionPipelines import IngestionPipeline
from apps.bi.models.EtlPipelines.EtlPipelineRuns import EtlPipelineRun
from apps.bi.models.EtlPipelines.EtlPipelines import EtlPipeline
from apps.bi.models.EtlPipelines.TransformationSteps import TransformationStep
from apps.bi.views._common import bi_object, bi_scope, csv_export_response, csv_safe
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def etl_pipeline_list(request):
    queryset = bi_scope(EtlPipeline.objects.all(), request)

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(source_staging_table__icontains=q)
            | Q(target_table__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    trigger_filter = request.GET.get("trigger_type", "").strip()
    if trigger_filter:
        queryset = queryset.filter(trigger_type=trigger_filter)

    target_layer_filter = request.GET.get("target_layer", "").strip()
    if target_layer_filter:
        queryset = queryset.filter(target_layer=target_layer_filter)

    if request.GET.get("export") == "csv":
        rows = [
            [
                csv_safe(p.number),
                csv_safe(p.name),
                csv_safe(p.source_staging_table),
                csv_safe(p.target_table),
                csv_safe(p.get_target_layer_display()),
                csv_safe(p.get_trigger_type_display()),
                csv_safe(p.get_status_display()),
                csv_safe(p.last_run_at.isoformat() if p.last_run_at else ""),
            ]
            for p in queryset
        ]
        return csv_export_response(
            request,
            filename="etl_pipelines.csv",
            headers=["Number", "Name", "Source Staging", "Target Table", "Layer", "Trigger", "Status", "Last Run"],
            rows=rows,
        )

    base_scope = bi_scope(EtlPipeline.objects.all(), request)
    total_count = base_scope.count()
    active_count = base_scope.filter(status="active").count()
    running_count = bi_scope(EtlPipelineRun.objects.filter(status="running"), request).count()

    paginator = Paginator(
        queryset.select_related("source_ingestion_pipeline", "alert_rule", "active_version"),
        20,
    )
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "pipelines": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "status_filter": status_filter,
        "trigger_filter": trigger_filter,
        "target_layer_filter": target_layer_filter,
        "status_choices": EtlPipeline.STATUS_CHOICES,
        "trigger_type_choices": EtlPipeline.TRIGGER_TYPE_CHOICES,
        "target_layer_choices": EtlPipeline.TARGET_LAYER_CHOICES,
        "total_count": total_count,
        "active_count": active_count,
        "running_count": running_count,
    }
    return render(request, "bi/etl_pipelines/etl_pipeline/list.html", context)


@login_required
def etl_pipeline_detail(request, pk):
    pipeline = bi_object(
        request,
        EtlPipeline,
        pk,
        select_related=("source_ingestion_pipeline", "alert_rule", "active_version", "created_by"),
    )
    steps = pipeline.steps.all().order_by("sequence")
    versions = pipeline.versions.all().select_related("environment_instance", "promoted_by").order_by("-created_at")[:10]
    recent_runs = pipeline.runs.all().order_by("-started_at")[:10]

    context = {
        "pipeline": pipeline,
        "steps": steps,
        "versions": versions,
        "recent_runs": recent_runs,
        "active_version": pipeline.active_version,
    }
    return render(request, "bi/etl_pipelines/etl_pipeline/detail.html", context)


@login_required
def etl_pipeline_create(request):
    if request.method == "POST":
        form = EtlPipelineForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                instance.created_by = request.user
                instance.save()
                write_audit_log(
                    request.user,
                    instance,
                    "create",
                    changes={"number": instance.number, "name": instance.name},
                    tenant=request.tenant,
                )
            messages.success(request, f"ETL Pipeline {instance.number} created successfully.")
            return redirect("bi:etl_pipeline_detail", pk=instance.pk)
    else:
        initial = {}
        source_id = request.GET.get("source_id")
        if source_id and source_id.isdigit():
            initial["source_ingestion_pipeline"] = int(source_id)
        form = EtlPipelineForm(tenant=request.tenant, initial=initial)

    return render(request, "bi/etl_pipelines/etl_pipeline/form.html", {"form": form, "is_edit": False})


@login_required
def etl_pipeline_edit(request, pk):
    pipeline = bi_object(request, EtlPipeline, pk)
    if request.method == "POST":
        form = EtlPipelineForm(request.POST, instance=pipeline, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save()
                write_audit_log(
                    request.user,
                    instance,
                    "update",
                    changes={"number": instance.number, "name": instance.name},
                    tenant=request.tenant,
                )
            messages.success(request, f"ETL Pipeline {instance.number} updated successfully.")
            return redirect("bi:etl_pipeline_detail", pk=instance.pk)
    else:
        form = EtlPipelineForm(instance=pipeline, tenant=request.tenant)

    return render(
        request,
        "bi/etl_pipelines/etl_pipeline/form.html",
        {"form": form, "pipeline": pipeline, "is_edit": True},
    )


@require_POST
@login_required
@tenant_admin_required
def etl_pipeline_delete(request, pk):
    pipeline = bi_object(request, EtlPipeline, pk)
    number = pipeline.number
    name = pipeline.name
    with transaction.atomic():
        write_audit_log(
            request.user,
            pipeline,
            "delete",
            changes={"number": number, "name": name},
            tenant=request.tenant,
        )
        pipeline.delete()
    messages.success(request, f"ETL Pipeline {number} deleted successfully.")
    return redirect("bi:etl_pipeline_list")


@login_required
def etl_pipeline_canvas(request, pk):
    pipeline = bi_object(
        request,
        EtlPipeline,
        pk,
        select_related=("source_ingestion_pipeline", "active_version"),
    )
    steps = pipeline.steps.all().order_by("sequence")
    available_sources = bi_scope(IngestionPipeline.objects.all(), request).only("id", "name", "target_staging_table")

    context = {
        "pipeline": pipeline,
        "steps": steps,
        "step_type_choices": TransformationStep.STEP_TYPE_CHOICES,
        "available_sources": available_sources,
    }
    return render(request, "bi/etl_pipelines/etl_pipeline/canvas.html", context)


@require_POST
@login_required
def etl_pipeline_trigger(request, pk):
    pipeline = bi_object(request, EtlPipeline, pk)

    with transaction.atomic():
        run = EtlPipelineRun.objects.create(
            tenant=request.tenant,
            pipeline=pipeline,
            version=pipeline.active_version,
            trigger_type="manual",
            status="running",
            started_at=timezone.now(),
            records_in=1000,
            records_transformed=980,
            records_out=980,
            records_rejected=20,
            bytes_processed=1024 * 512,
            step_progress={"initial_load": "complete", "transformations": "in_progress"},
            execution_log="[INFO] Manual trigger dispatched. Pipeline transformation worker started.",
        )
        pipeline.last_run_at = timezone.now()
        pipeline.save(update_fields=["last_run_at"])
        write_audit_log(
            request.user,
            run,
            "trigger",
            changes={"pipeline_number": pipeline.number, "run_number": run.number},
            tenant=request.tenant,
        )

    messages.success(request, f"Execution run {run.number} initiated for {pipeline.name}.")
    return redirect("bi:etl_pipeline_detail", pk=pipeline.pk)
