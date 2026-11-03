from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.EtlPipelines.TransformationSteps import TransformationStepForm
from apps.bi.models.EtlPipelines.EtlPipelines import EtlPipeline
from apps.bi.models.EtlPipelines.TransformationSteps import TransformationStep
from apps.bi.views._common import bi_object, bi_scope, csv_export_response, csv_safe
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def transformation_step_list(request):
    queryset = bi_scope(TransformationStep.objects.all(), request)

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    step_type_filter = request.GET.get("step_type", "").strip()
    if step_type_filter:
        queryset = queryset.filter(step_type=step_type_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    pipeline_filter = request.GET.get("pipeline_id", "").strip()
    if pipeline_filter and pipeline_filter.isdigit():
        queryset = queryset.filter(pipeline_id=int(pipeline_filter))

    if request.GET.get("export") == "csv":
        rows = [
            [
                csv_safe(s.number),
                csv_safe(s.pipeline.name),
                csv_safe(s.sequence),
                csv_safe(s.name),
                csv_safe(s.get_step_type_display()),
                csv_safe(s.get_status_display()),
                csv_safe("Yes" if s.is_blocking else "No"),
            ]
            for s in queryset.select_related("pipeline")
        ]
        return csv_export_response(
            request,
            filename="transformation_steps.csv",
            headers=["Step Number", "Pipeline", "Seq", "Name", "Type", "Status", "Blocking"],
            rows=rows,
        )

    total_count = queryset.count()
    paginator = Paginator(
        queryset.select_related("pipeline", "mapping_template"),
        20,
    )
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    pipelines = bi_scope(EtlPipeline.objects.all(), request).only("id", "name", "number").order_by("name")

    context = {
        "steps": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "step_type_filter": step_type_filter,
        "status_filter": status_filter,
        "pipeline_filter": pipeline_filter,
        "step_type_choices": TransformationStep.STEP_TYPE_CHOICES,
        "status_choices": TransformationStep.STATUS_CHOICES,
        "pipelines": pipelines,
        "total_count": total_count,
    }
    return render(request, "bi/etl_pipelines/transformation_step/list.html", context)


@login_required
def transformation_step_detail(request, pk):
    step = bi_object(
        request,
        TransformationStep,
        pk,
        select_related=("pipeline", "mapping_template"),
    )
    context = {
        "step": step,
        "pipeline": step.pipeline,
        "mapping_template": step.mapping_template,
    }
    return render(request, "bi/etl_pipelines/transformation_step/detail.html", context)


@login_required
def transformation_step_create(request):
    pipeline_id = request.GET.get("pipeline") or request.GET.get("pipeline_id")
    if request.method == "POST":
        form = TransformationStepForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                instance.save()
                write_audit_log(
                    request.tenant,
                    request.user,
                    "bi.transformation_step.create",
                    f"Created Transformation Step {instance.number} (#{instance.sequence} {instance.name})",
                )
            messages.success(request, f"Transformation Step {instance.number} created successfully.")
            return redirect("bi:transformation_step_detail", pk=instance.pk)
    else:
        initial = {}
        if pipeline_id and pipeline_id.isdigit():
            initial["pipeline"] = int(pipeline_id)
        form = TransformationStepForm(tenant=request.tenant, initial=initial)

    pipeline = None
    if pipeline_id and pipeline_id.isdigit():
        pipeline = bi_scope(EtlPipeline.objects.all(), request).filter(pk=int(pipeline_id)).first()

    return render(
        request,
        "bi/etl_pipelines/transformation_step/form.html",
        {"form": form, "is_edit": False, "pipeline": pipeline},
    )


@login_required
def transformation_step_edit(request, pk):
    step = bi_object(request, TransformationStep, pk, select_related=("pipeline",))
    if request.method == "POST":
        form = TransformationStepForm(request.POST, instance=step, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save()
                write_audit_log(
                    request.tenant,
                    request.user,
                    "bi.transformation_step.update",
                    f"Updated Transformation Step {instance.number} ({instance.name})",
                )
            messages.success(request, f"Transformation Step {instance.number} updated successfully.")
            return redirect("bi:transformation_step_detail", pk=instance.pk)
    else:
        form = TransformationStepForm(instance=step, tenant=request.tenant)

    return render(
        request,
        "bi/etl_pipelines/transformation_step/form.html",
        {"form": form, "step": step, "is_edit": True, "pipeline": step.pipeline},
    )


@require_POST
@login_required
@tenant_admin_required
def transformation_step_delete(request, pk):
    step = bi_object(request, TransformationStep, pk, select_related=("pipeline",))
    pipeline_pk = step.pipeline_id
    number = step.number
    name = step.name
    with transaction.atomic():
        step.delete()
        write_audit_log(
            request.tenant,
            request.user,
            "bi.transformation_step.delete",
            f"Deleted Transformation Step {number} ({name})",
        )
    messages.success(request, f"Transformation Step {number} deleted successfully.")
    return redirect("bi:etl_pipeline_detail", pk=pipeline_pk)
