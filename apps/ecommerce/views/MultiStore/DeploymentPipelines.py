from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MultiStore.DeploymentPipelines import DeploymentPipelineForm
from apps.ecommerce.models.MultiStore.DeploymentPipelines import DeploymentPipeline
from apps.ecommerce.models.MultiStore.PlatformEnvironments import PlatformEnvironment
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def deployment_pipeline_list(request):
    queryset = ecommerce_scope(
        DeploymentPipeline.objects.select_related("environment", "promoted_by"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(release_version__icontains=search_query)
            | Q(git_branch__icontains=search_query)
            | Q(git_commit_sha__icontains=search_query)
            | Q(number__icontains=search_query)
        )

    environment_filter = request.GET.get("environment", "").strip()
    if environment_filter:
        queryset = queryset.filter(environment_id=environment_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    strategy_filter = request.GET.get("strategy", "").strip()
    if strategy_filter:
        queryset = queryset.filter(deployment_strategy=strategy_filter)

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    environments = ecommerce_scope(PlatformEnvironment.objects.all(), request)

    context = {
        "deployment_pipelines": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "environment_filter": environment_filter,
        "status_filter": status_filter,
        "strategy_filter": strategy_filter,
        "status_choices": DeploymentPipeline.STATUS_CHOICES,
        "strategy_choices": DeploymentPipeline.STRATEGY_CHOICES,
        "environments": environments,
    }
    return render(request, "ecommerce/multi_store/deployment_pipeline/list.html", context)


@login_required
def deployment_pipeline_detail(request, pk):
    pipeline = ecommerce_object(
        request,
        DeploymentPipeline,
        pk=pk,
        select_related=("environment", "promoted_by"),
    )
    context = {
        "pipeline": pipeline,
    }
    return render(request, "ecommerce/multi_store/deployment_pipeline/detail.html", context)


@login_required
def deployment_pipeline_create(request):
    initial = {}
    environment_id = request.GET.get("environment")
    if environment_id:
        initial["environment"] = environment_id

    if request.method == "POST":
        form = DeploymentPipelineForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            pipeline = form.save(commit=False)
            pipeline.tenant = request.tenant
            pipeline.save()
            write_audit_log(
                request.user,
                "CREATE",
                pipeline,
                f"Created deployment pipeline '{pipeline.release_version}' for {pipeline.environment.name} ({pipeline.number})"
            )
            messages.success(request, f"Deployment pipeline '{pipeline.release_version}' created successfully.")
            return redirect("ecommerce:deployment_pipeline_detail", pk=pipeline.pk)
    else:
        form = DeploymentPipelineForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "pipeline": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/multi_store/deployment_pipeline/form.html", context)


@login_required
def deployment_pipeline_edit(request, pk):
    pipeline = ecommerce_object(request, DeploymentPipeline, pk=pk)
    if request.method == "POST":
        form = DeploymentPipelineForm(request.POST, instance=pipeline, tenant=request.tenant)
        if form.is_valid():
            pipeline = form.save()
            write_audit_log(
                request.user,
                "UPDATE",
                pipeline,
                f"Updated deployment pipeline '{pipeline.release_version}' ({pipeline.number})"
            )
            messages.success(request, f"Deployment pipeline '{pipeline.release_version}' updated.")
            return redirect("ecommerce:deployment_pipeline_detail", pk=pipeline.pk)
    else:
        form = DeploymentPipelineForm(instance=pipeline, tenant=request.tenant)

    context = {
        "form": form,
        "pipeline": pipeline,
        "is_edit": True,
    }
    return render(request, "ecommerce/multi_store/deployment_pipeline/form.html", context)


@login_required
@require_POST
def deployment_pipeline_delete(request, pk):
    pipeline = ecommerce_object(request, DeploymentPipeline, pk=pk)
    version = pipeline.release_version
    num = pipeline.number
    pipeline.delete()
    write_audit_log(
        request.user,
        "DELETE",
        None,
        f"Deleted deployment pipeline '{version}' ({num})"
    )
    messages.success(request, f"Deployment pipeline '{version}' deleted.")
    return redirect("ecommerce:deployment_pipeline_list")


@login_required
@require_POST
def deployment_promote(request, pk):
    pipeline = ecommerce_object(request, DeploymentPipeline, pk=pk, select_related=("environment",))
    pipeline.status = "promoted_active"
    pipeline.traffic_percentage = 100
    pipeline.promoted_at = timezone.now()
    pipeline.promoted_by = request.user
    pipeline.save()

    # Update parent environment active slot if target_slot is blue or green
    if pipeline.target_slot in ["blue", "green"]:
        pipeline.environment.current_active_slot = pipeline.target_slot
        pipeline.environment.status = "healthy"
        pipeline.environment.save()

    write_audit_log(
        request.user,
        "EXECUTE",
        pipeline,
        f"Promoted deployment '{pipeline.release_version}' to active 100% traffic on slot {pipeline.target_slot} ({pipeline.number})"
    )
    messages.success(request, f"Release '{pipeline.release_version}' promoted to active live traffic.")
    return redirect("ecommerce:deployment_pipeline_detail", pk=pipeline.pk)


@login_required
@require_POST
def deployment_rollback(request, pk):
    pipeline = ecommerce_object(request, DeploymentPipeline, pk=pk, select_related=("environment",))
    pipeline.status = "rolled_back"
    pipeline.traffic_percentage = 0
    pipeline.save()

    write_audit_log(
        request.user,
        "EXECUTE",
        pipeline,
        f"Rolled back deployment '{pipeline.release_version}' on {pipeline.environment.name} ({pipeline.number})"
    )
    messages.warning(request, f"Release '{pipeline.release_version}' rolled back.")
    return redirect("ecommerce:deployment_pipeline_detail", pk=pipeline.pk)
