from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.DataIntegration.CdcSyncConfigs import CdcSyncConfigForm
from apps.bi.models.DataIntegration.CdcSyncConfigs import CdcSyncConfig
from apps.bi.models.DataIntegration.IngestionPipelines import IngestionPipeline
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def cdc_sync_config_list(request):
    queryset = bi_scope(CdcSyncConfig.objects.all(), request)
    total_count = queryset.count()

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(pipeline__name__icontains=q)
            | Q(primary_key_fields__icontains=q)
            | Q(cursor_field__icontains=q)
        )

    capture_method = request.GET.get("capture_method", "").strip()
    if capture_method:
        queryset = queryset.filter(capture_method=capture_method)

    sync_mode = request.GET.get("sync_mode", "").strip()
    if sync_mode:
        queryset = queryset.filter(sync_mode=sync_mode)

    paginator = Paginator(queryset.select_related("pipeline", "pipeline__connector"), 20)
    page_number = request.GET.get("page")
    cdc_configs = paginator.get_page(page_number)

    context = {
        "cdc_configs": cdc_configs,
        "q": q,
        "capture_method": capture_method,
        "sync_mode": sync_mode,
        "method_choices": CdcSyncConfig.CAPTURE_METHOD_CHOICES,
        "mode_choices": CdcSyncConfig.SYNC_MODE_CHOICES,
        "total_count": total_count,
    }
    return render(request, "bi/data_integration/cdc_sync_config/list.html", context)


@login_required
def cdc_sync_config_detail(request, pk):
    config = bi_object(
        request,
        CdcSyncConfig,
        pk,
        select_related=("pipeline", "pipeline__connector"),
    )
    context = {
        "config": config,
        "pipeline": config.pipeline,
    }
    return render(request, "bi/data_integration/cdc_sync_config/detail.html", context)


@login_required
def cdc_sync_config_create(request):
    initial = {}
    pipeline_pk = request.GET.get("pipeline")
    if pipeline_pk:
        initial["pipeline"] = pipeline_pk

    if request.method == "POST":
        form = CdcSyncConfigForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            config = form.save()
            write_audit_log(
                request,
                action="create",
                model_name="CdcSyncConfig",
                object_id=config.pk,
                description=f"Created CDC Sync Config {config.number} for pipeline {config.pipeline.number}",
            )
            messages.success(request, f"CDC Sync Config {config.number} created successfully.")
            return redirect("bi:cdc_sync_config_detail", pk=config.pk)
    else:
        form = CdcSyncConfigForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "config": None,
        "is_edit": False,
    }
    return render(request, "bi/data_integration/cdc_sync_config/form.html", context)


@login_required
def cdc_sync_config_edit(request, pk):
    config = bi_object(request, CdcSyncConfig, pk)
    if request.method == "POST":
        form = CdcSyncConfigForm(request.POST, instance=config, tenant=request.tenant)
        if form.is_valid():
            config = form.save()
            write_audit_log(
                request,
                action="update",
                model_name="CdcSyncConfig",
                object_id=config.pk,
                description=f"Updated CDC Sync Config {config.number}",
            )
            messages.success(request, f"CDC Sync Config {config.number} updated successfully.")
            return redirect("bi:cdc_sync_config_detail", pk=config.pk)
    else:
        form = CdcSyncConfigForm(instance=config, tenant=request.tenant)

    context = {
        "form": form,
        "config": config,
        "is_edit": True,
    }
    return render(request, "bi/data_integration/cdc_sync_config/form.html", context)


@require_POST
@login_required
@tenant_admin_required
def cdc_sync_config_delete(request, pk):
    config = bi_object(request, CdcSyncConfig, pk)
    number = config.number
    pipeline_pk = config.pipeline_id
    config.delete()
    write_audit_log(
        request,
        action="delete",
        model_name="CdcSyncConfig",
        object_id=pk,
        description=f"Deleted CDC Sync Config {number}",
    )
    messages.success(request, f"CDC Sync Config {number} deleted successfully.")
    return redirect("bi:ingestion_pipeline_detail", pk=pipeline_pk)


@require_POST
@login_required
def cdc_sync_config_reset_cursor(request, pk):
    config = bi_object(request, CdcSyncConfig, pk)
    old_cursor = config.last_cursor_value
    config.last_cursor_value = ""
    config.last_checkpoint_at = None
    config.save(update_fields=["last_cursor_value", "last_checkpoint_at", "updated_at"])

    write_audit_log(
        request,
        action="reset_cursor",
        model_name="CdcSyncConfig",
        object_id=config.pk,
        description=f"Reset CDC cursor offset for {config.number} (previous cursor: {old_cursor})",
    )
    messages.success(request, f"High-water mark cursor for {config.number} has been reset to beginning.")
    return redirect("bi:cdc_sync_config_detail", pk=config.pk)
