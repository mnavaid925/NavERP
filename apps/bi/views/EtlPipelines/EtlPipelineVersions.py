from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.EtlPipelines.EtlPipelineVersions import EtlPipelineVersionForm
from apps.bi.models.EtlPipelines.EtlPipelines import EtlPipeline
from apps.bi.models.EtlPipelines.EtlPipelineVersions import EtlPipelineVersion
from apps.bi.views._common import bi_object, bi_scope, csv_export_response, csv_safe
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def etl_pipeline_version_list(request):
    queryset = bi_scope(EtlPipelineVersion.objects.all(), request).defer("dag_definition")

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(version_number__icontains=q)
            | Q(number__icontains=q)
            | Q(changelog__icontains=q)
            | Q(pipeline__name__icontains=q)
        )

    environment_filter = request.GET.get("environment", "").strip()
    if environment_filter:
        queryset = queryset.filter(environment=environment_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    pipeline_filter = request.GET.get("pipeline_id", "").strip()
    if pipeline_filter and pipeline_filter.isdigit():
        queryset = queryset.filter(pipeline_id=int(pipeline_filter))

    if request.GET.get("export") == "csv":
        rows = [
            [
                csv_safe(v.number),
                csv_safe(v.pipeline.name),
                csv_safe(v.version_number),
                csv_safe(v.get_environment_display()),
                csv_safe(v.get_status_display()),
                csv_safe(v.promoted_by.username if v.promoted_by else ""),
                csv_safe(v.promoted_at.isoformat() if v.promoted_at else ""),
            ]
            for v in queryset.select_related("pipeline", "promoted_by")
        ]
        return csv_export_response(
            request,
            filename="pipeline_versions.csv",
            headers=["Version ID", "Pipeline", "Version Number", "Environment", "Status", "Promoted By", "Promoted At"],
            rows=rows,
        )

    paginator = Paginator(
        queryset.select_related("pipeline", "environment_instance", "promoted_by"),
        20,
    )
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    pipelines = bi_scope(EtlPipeline.objects.all(), request).only("id", "name", "number").order_by("name")

    context = {
        "versions": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "q": q,
        "environment_filter": environment_filter,
        "status_filter": status_filter,
        "pipeline_filter": pipeline_filter,
        "environment_choices": EtlPipelineVersion.ENVIRONMENT_CHOICES,
        "status_choices": EtlPipelineVersion.STATUS_CHOICES,
        "pipelines": pipelines,
    }
    return render(request, "bi/etl_pipelines/etl_pipeline_version/list.html", context)


@login_required
def etl_pipeline_version_detail(request, pk):
    version = bi_object(
        request,
        EtlPipelineVersion,
        pk,
        select_related=("pipeline", "environment_instance", "promoted_by", "rollback_source"),
    )
    context = {
        "version": version,
        "pipeline": version.pipeline,
        "environment_instance": version.environment_instance,
        "promoted_by": version.promoted_by,
    }
    return render(request, "bi/etl_pipelines/etl_pipeline_version/detail.html", context)


@login_required
def etl_pipeline_version_create(request):
    pipeline_id = request.GET.get("pipeline") or request.GET.get("pipeline_id")
    if request.method == "POST":
        form = EtlPipelineVersionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                instance.save()
                write_audit_log(
                    request.user,
                    instance,
                    "create",
                    changes={"version_number": instance.version_number, "number": instance.number},
                    tenant=request.tenant,
                )
            messages.success(request, f"Pipeline Version {instance.version_number} created successfully.")
            return redirect("bi:etl_pipeline_version_detail", pk=instance.pk)
    else:
        initial = {}
        if pipeline_id and pipeline_id.isdigit():
            initial["pipeline"] = int(pipeline_id)
        form = EtlPipelineVersionForm(tenant=request.tenant, initial=initial)

    return render(request, "bi/etl_pipelines/etl_pipeline_version/form.html", {"form": form, "is_edit": False})


@login_required
def etl_pipeline_version_edit(request, pk):
    version = bi_object(request, EtlPipelineVersion, pk, select_related=("pipeline",))
    if request.method == "POST":
        form = EtlPipelineVersionForm(request.POST, instance=version, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save()
                write_audit_log(
                    request.user,
                    instance,
                    "update",
                    changes={"version_number": instance.version_number, "number": instance.number},
                    tenant=request.tenant,
                )
            messages.success(request, f"Pipeline Version {instance.version_number} updated successfully.")
            return redirect("bi:etl_pipeline_version_detail", pk=instance.pk)
    else:
        form = EtlPipelineVersionForm(instance=version, tenant=request.tenant)

    return render(
        request,
        "bi/etl_pipelines/etl_pipeline_version/form.html",
        {"form": form, "version": version, "is_edit": True},
    )


@require_POST
@login_required
@tenant_admin_required
def etl_pipeline_version_delete(request, pk):
    version = bi_object(request, EtlPipelineVersion, pk, select_related=("pipeline",))
    pipeline_pk = version.pipeline_id
    version_number = version.version_number

    if version.pipeline.active_version_id == version.pk or (version.environment == "production" and version.status == "published"):
        messages.error(
            request,
            f"Cannot delete Version {version_number}: it is the active production version. Reassign or promote another version before deletion.",
        )
        next_param = request.GET.get("next") or request.POST.get("next")
        if next_param == "list":
            return redirect("bi:etl_pipeline_version_list")
        return redirect("bi:etl_pipeline_detail", pk=pipeline_pk)

    with transaction.atomic():
        write_audit_log(
            request.user,
            version,
            "delete",
            changes={"version_number": version_number, "number": version.number},
            tenant=request.tenant,
        )
        version.delete()
    messages.success(request, f"Pipeline Version {version_number} deleted successfully.")
    next_param = request.GET.get("next") or request.POST.get("next")
    if next_param == "list":
        return redirect("bi:etl_pipeline_version_list")
    return redirect("bi:etl_pipeline_detail", pk=pipeline_pk)


@require_POST
@login_required
@tenant_admin_required
def etl_pipeline_version_promote(request, pk):
    version = bi_object(request, EtlPipelineVersion, pk, select_related=("pipeline",))
    target_env = request.POST.get("target_environment", "production")
    if target_env not in dict(EtlPipelineVersion.ENVIRONMENT_CHOICES):
        messages.error(request, f"Invalid target environment: {target_env}")
        return redirect("bi:etl_pipeline_version_detail", pk=version.pk)

    with transaction.atomic():
        version.environment = target_env
        version.status = "published"
        version.promoted_by = request.user
        version.promoted_at = timezone.now()
        version.save(update_fields=["environment", "status", "promoted_by", "promoted_at"])

        if target_env == "production":
            version.pipeline.active_version = version
            version.pipeline.save(update_fields=["active_version"])

        write_audit_log(
            request.user,
            version,
            "promote",
            changes={"version_number": version.version_number, "target_env": target_env},
            tenant=request.tenant,
        )

    messages.success(request, f"Version {version.version_number} successfully promoted to {target_env.title()}.")
    return redirect("bi:etl_pipeline_version_detail", pk=version.pk)
