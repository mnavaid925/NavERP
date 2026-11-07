from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.EmbeddedMobileBi.MobileBiConfigurations import MobileBiConfigurationForm
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.EmbeddedMobileBi.MobileBiConfigurations import MobileBiConfiguration
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def mobile_bi_config_list(request):
    qs = bi_scope(MobileBiConfiguration.objects.all(), request).select_related(
        "target_user", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        offline_enabled=Count("id", filter=Q(offline_caching_enabled=True)),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    offline_enabled_count = counts["offline_enabled"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(target_user__username__icontains=q)
            | Q(target_user__first_name__icontains=q)
            | Q(target_user__last_name__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    preset = request.GET.get("preset", "").strip()
    if preset:
        qs = qs.filter(touch_layout_preset=preset)

    digest = request.GET.get("digest", "").strip()
    if digest:
        qs = qs.filter(push_digest_frequency=digest)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "configs": page_obj,
        "mobile_bi_configs": page_obj,
        "total_count": total_count,
        "active_count": active_count,
        "offline_enabled_count": offline_enabled_count,
        "status_choices": MobileBiConfiguration.STATUS_CHOICES,
        "preset_choices": MobileBiConfiguration.TOUCH_PRESET_CHOICES,
        "digest_choices": MobileBiConfiguration.DIGEST_FREQUENCY_CHOICES,
    }
    return render(
        request,
        "bi/embedded_mobile_bi/mobilebiconfiguration/list.html",
        context,
    )


@login_required
@tenant_admin_required
def mobile_bi_config_create(request):
    if request.method == "POST":
        form = MobileBiConfigurationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                config = form.save(commit=False)
                config.tenant = request.tenant
                config.created_by = request.user
                if config.is_default_profile:
                    MobileBiConfiguration.objects.filter(
                        tenant=request.tenant, is_default_profile=True
                    ).update(is_default_profile=False)
                config.save()
                write_audit_log(
                    request.user,
                    config,
                    "create",
                    tenant=request.tenant,
                )
            messages.success(request, f"Mobile profile '{config.name}' created successfully.")
            return redirect("bi:mobile_bi_config_detail", pk=config.pk)
    else:
        form = MobileBiConfigurationForm(tenant=request.tenant)

    return render(
        request,
        "bi/embedded_mobile_bi/mobilebiconfiguration/form.html",
        {"form": form, "title": "New Mobile BI Configuration Profile"},
    )


@login_required
def mobile_bi_config_detail(request, pk):
    config = bi_object(
        request,
        MobileBiConfiguration,
        pk,
        select_related=("target_user", "created_by"),
    )

    dash_ids = config.pinned_dashboard_ids if isinstance(config.pinned_dashboard_ids, list) else []
    rep_ids = config.pinned_report_ids if isinstance(config.pinned_report_ids, list) else []

    pinned_dashboards = (
        BiDashboard.objects.filter(tenant=request.tenant, id__in=dash_ids).only("id", "title", "number")
        if dash_ids
        else []
    )
    pinned_reports = (
        ReportDefinition.objects.filter(tenant=request.tenant, id__in=rep_ids).only("id", "name", "number")
        if rep_ids
        else []
    )

    context = {
        "config": config,
        "pinned_dashboards": pinned_dashboards,
        "pinned_reports": pinned_reports,
    }
    return render(
        request,
        "bi/embedded_mobile_bi/mobilebiconfiguration/detail.html",
        context,
    )


@login_required
@tenant_admin_required
def mobile_bi_config_edit(request, pk):
    config = bi_object(request, MobileBiConfiguration, pk)

    if request.method == "POST":
        form = MobileBiConfigurationForm(request.POST, instance=config, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                if form.cleaned_data.get("is_default_profile"):
                    MobileBiConfiguration.objects.filter(
                        tenant=request.tenant, is_default_profile=True
                    ).exclude(pk=config.pk).update(is_default_profile=False)
                config = form.save()
                write_audit_log(
                    request.user,
                    config,
                    "update",
                    tenant=request.tenant,
                )
            messages.success(request, f"Mobile profile '{config.name}' updated successfully.")
            return redirect("bi:mobile_bi_config_detail", pk=config.pk)
    else:
        form = MobileBiConfigurationForm(instance=config, tenant=request.tenant)

    return render(
        request,
        "bi/embedded_mobile_bi/mobilebiconfiguration/form.html",
        {"form": form, "config": config, "title": f"Edit {config.name}"},
    )


@login_required
@tenant_admin_required
@require_POST
def mobile_bi_config_delete(request, pk):
    config = bi_object(request, MobileBiConfiguration, pk)
    with transaction.atomic():
        write_audit_log(
            request.user,
            config,
            "delete",
            tenant=request.tenant,
        )
        config.delete()
    messages.success(request, "Mobile profile removed.")
    return redirect("bi:mobile_bi_config_list")
