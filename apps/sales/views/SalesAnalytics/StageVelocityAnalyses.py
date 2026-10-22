"""Sales 8.12 — Views for `StageVelocityAnalysis`.

Function-based views over the 8.12 Stage Velocity Analysis record. Every
queryset is tenant-scoped, every write is audit-logged, and every integer FK
filter is guarded by ``_pk_filter`` (``.isdigit()`` plus a 64-bit range bound) so
a hand-edited URL is ignored rather than a 500 (L11).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.SalesAnalytics.StageVelocityAnalyses import StageVelocityAnalysisForm
from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline, PipelineStage
from apps.sales.models.SalesAnalytics.StageVelocityAnalyses import (
    VELOCITY_STATUS_CHOICES,
    StageVelocityAnalysis,
)
from apps.sales.views.SalesAnalytics._helpers import _pk_filter


@login_required
def stage_velocity_analysis_list(request):
    qs = StageVelocityAnalysis.objects.filter(tenant=request.tenant).select_related(
        "pipeline",
        "pipeline_stage",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(pipeline__name__icontains=q)
            | Q(pipeline_stage__name__icontains=q)
            | Q(recommendation__icontains=q)
            | Q(notes__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    pipeline_id = request.GET.get("pipeline", "").strip()
    pipeline_pk = _pk_filter(pipeline_id)
    if pipeline_pk is not None:
        qs = qs.filter(pipeline_id=pipeline_pk)

    stage_id = request.GET.get("pipeline_stage", "").strip()
    stage_pk = _pk_filter(stage_id)
    if stage_pk is not None:
        qs = qs.filter(pipeline_stage_id=stage_pk)

    bottleneck = request.GET.get("bottleneck", "").strip()
    if bottleneck in {"1", "true"}:
        qs = qs.filter(is_bottleneck=True)

    stats = qs.aggregate(
        total_count=Count("id"),
        bottleneck_count=Count("id", filter=Q(is_bottleneck=True)),
        draft_count=Count("id", filter=Q(status="draft")),
        reviewed_count=Count("id", filter=Q(status="reviewed")),
        approved_count=Count("id", filter=Q(status="approved")),
    )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    pipelines = Pipeline.objects.filter(tenant=request.tenant, is_active=True).order_by("name")
    pipeline_stages = (
        PipelineStage.objects.filter(tenant=request.tenant, is_active=True)
        .select_related("pipeline")
        .order_by("pipeline__name", "sequence")
    )

    context = {
        "analyses": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "status_choices": VELOCITY_STATUS_CHOICES,
        "pipelines": pipelines,
        "pipeline_stages": pipeline_stages,
        "stats": stats,
        "active_filters": {
            "q": q,
            "status": status,
            "pipeline": pipeline_id,
            "pipeline_stage": stage_id,
            "bottleneck": bottleneck,
        },
    }
    return render(request, "sales/salesanalytics/stagevelocityanalysis/list.html", context)


@login_required
def stage_velocity_analysis_detail(request, pk):
    obj = get_object_or_404(
        StageVelocityAnalysis.objects.filter(tenant=request.tenant).select_related(
            "pipeline",
            "pipeline_stage__pipeline",
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/salesanalytics/stagevelocityanalysis/detail.html",
        {"obj": obj, "analysis": obj},
    )


@tenant_admin_required
def stage_velocity_analysis_create(request):
    if request.method == "POST":
        form = StageVelocityAnalysisForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                f"Recorded stage velocity analysis {obj.number} for {obj.pipeline_stage}",
                tenant=request.tenant,
            )
            messages.success(request, f"Stage velocity analysis {obj.number} created successfully.")
            return redirect("sales:stage_velocity_analysis_detail", pk=obj.pk)
    else:
        form = StageVelocityAnalysisForm(tenant=request.tenant)

    return render(
        request,
        "sales/salesanalytics/stagevelocityanalysis/form.html",
        {"form": form, "obj": None, "is_edit": False},
    )


@tenant_admin_required
def stage_velocity_analysis_edit(request, pk):
    obj = get_object_or_404(
        StageVelocityAnalysis.objects.filter(tenant=request.tenant).select_related(
            "pipeline",
            "pipeline_stage__pipeline",
        ),
        pk=pk,
    )
    if request.method == "POST":
        form = StageVelocityAnalysisForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                f"Updated stage velocity analysis {obj.number} for {obj.pipeline_stage}",
                tenant=request.tenant,
            )
            messages.success(request, f"Stage velocity analysis {obj.number} updated successfully.")
            return redirect("sales:stage_velocity_analysis_detail", pk=obj.pk)
    else:
        form = StageVelocityAnalysisForm(instance=obj, tenant=request.tenant)

    return render(
        request,
        "sales/salesanalytics/stagevelocityanalysis/form.html",
        {"form": form, "obj": obj, "is_edit": True},
    )


@require_POST
@tenant_admin_required
def stage_velocity_analysis_delete(request, pk):
    obj = get_object_or_404(
        StageVelocityAnalysis.objects.filter(tenant=request.tenant).select_related(
            "pipeline",
            "pipeline_stage__pipeline",
        ),
        pk=pk,
    )
    number = obj.number
    stage_name = str(obj.pipeline_stage) if obj.pipeline_stage_id else "—"
    write_audit_log(
        request.user,
        obj,
        "delete",
        f"Deleted stage velocity analysis {number} for {stage_name}",
        tenant=request.tenant,
    )
    obj.delete()
    messages.success(request, f"Stage velocity analysis {number} deleted.")
    return redirect("sales:stage_velocity_analysis_list")
