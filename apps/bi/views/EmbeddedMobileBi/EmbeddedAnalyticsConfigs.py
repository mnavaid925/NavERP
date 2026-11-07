from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.EmbeddedMobileBi.EmbeddedAnalyticsConfigs import EmbeddedAnalyticsConfigForm
from apps.bi.models.EmbeddedMobileBi.EmbeddedAnalyticsConfigs import EmbeddedAnalyticsConfig
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def embedded_analytics_config_list(request):
    qs = bi_scope(EmbeddedAnalyticsConfig.objects.all(), request).select_related(
        "dashboard", "report", "semantic_model", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        iframe=Count("id", filter=Q(embedding_mode="iframe")),
        component=Count("id", filter=Q(embedding_mode="web_component")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    iframe_count = counts["iframe"] or 0
    component_count = counts["component"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(slug__icontains=q)
            | Q(description__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    target_type = request.GET.get("target_type", "").strip()
    if target_type:
        qs = qs.filter(target_type=target_type)

    embedding_mode = request.GET.get("embedding_mode", "").strip()
    if embedding_mode:
        qs = qs.filter(embedding_mode=embedding_mode)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "configs": page_obj,
        "embedded_analytics_configs": page_obj,
        "total_count": total_count,
        "active_count": active_count,
        "iframe_count": iframe_count,
        "component_count": component_count,
        "status_choices": EmbeddedAnalyticsConfig.STATUS_CHOICES,
        "target_type_choices": EmbeddedAnalyticsConfig.TARGET_TYPE_CHOICES,
        "embedding_mode_choices": EmbeddedAnalyticsConfig.EMBEDDING_MODE_CHOICES,
    }
    return render(
        request,
        "bi/embedded_mobile_bi/embeddedanalyticsconfig/list.html",
        context,
    )


@login_required
@tenant_admin_required
def embedded_analytics_config_create(request):
    if request.method == "POST":
        form = EmbeddedAnalyticsConfigForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                config = form.save(commit=False)
                config.tenant = request.tenant
                config.created_by = request.user
                config.save()
                write_audit_log(
                    request,
                    action="CREATE",
                    instance=config,
                    description=f"Created embedded analytics config {config.number} ({config.name})",
                )
            messages.success(request, f"Embedded configuration '{config.name}' created successfully.")
            return redirect("bi:embedded_analytics_config_detail", pk=config.pk)
    else:
        form = EmbeddedAnalyticsConfigForm(tenant=request.tenant)

    return render(
        request,
        "bi/embedded_mobile_bi/embeddedanalyticsconfig/form.html",
        {"form": form, "title": "New Embedded Analytics Configuration"},
    )


@login_required
def embedded_analytics_config_detail(request, pk):
    config = bi_object(
        request,
        EmbeddedAnalyticsConfig,
        pk,
        select_related=("dashboard", "report", "semantic_model", "created_by"),
    )

    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"
    embed_url = f"{scheme}://{host}/bi/embedded-configs/{config.pk}/preview/"

    iframe_snippet = (
        f'<iframe\n'
        f'  src="{embed_url}"\n'
        f'  width="100%"\n'
        f'  height="650px"\n'
        f'  frameborder="0"\n'
        f'  allowtransparency="true"\n'
        f'  sandbox="allow-scripts allow-same-origin allow-popups"\n'
        f'></iframe>'
    )

    web_component_snippet = (
        f'<script src="{scheme}://{host}/static/js/nav-bi-embed.js"></script>\n'
        f'<nav-bi-embed\n'
        f'  config-id="{config.number}"\n'
        f'  mode="{config.embedding_mode}"\n'
        f'  theme="{config.theme_mode}"\n'
        f'  endpoint="{scheme}://{host}"\n'
        f'></nav-bi-embed>'
    )

    curl_snippet = (
        f'curl -X GET "{scheme}://{host}/api/v1/bi/embed/{config.slug}/data" \\\n'
        f'  -H "Authorization: Bearer <YOUR_API_TOKEN>" \\\n'
        f'  -H "Content-Type: application/json"'
    )

    context = {
        "config": config,
        "iframe_snippet": iframe_snippet,
        "web_component_snippet": web_component_snippet,
        "curl_snippet": curl_snippet,
        "embed_url": embed_url,
    }
    return render(
        request,
        "bi/embedded_mobile_bi/embeddedanalyticsconfig/detail.html",
        context,
    )


@login_required
@tenant_admin_required
def embedded_analytics_config_edit(request, pk):
    config = bi_object(request, EmbeddedAnalyticsConfig, pk)

    if request.method == "POST":
        form = EmbeddedAnalyticsConfigForm(request.POST, instance=config, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                config = form.save()
                write_audit_log(
                    request,
                    action="UPDATE",
                    instance=config,
                    description=f"Updated embedded analytics config {config.number}",
                )
            messages.success(request, f"Configuration '{config.name}' updated successfully.")
            return redirect("bi:embedded_analytics_config_detail", pk=config.pk)
    else:
        form = EmbeddedAnalyticsConfigForm(instance=config, tenant=request.tenant)

    return render(
        request,
        "bi/embedded_mobile_bi/embeddedanalyticsconfig/form.html",
        {"form": form, "config": config, "title": f"Edit {config.name}"},
    )


@login_required
@tenant_admin_required
@require_POST
def embedded_analytics_config_delete(request, pk):
    config = bi_object(request, EmbeddedAnalyticsConfig, pk)
    with transaction.atomic():
        write_audit_log(
            request,
            action="DELETE",
            instance=config,
            description=f"Deleted embedded analytics config {config.number}",
        )
        config.delete()
    messages.success(request, "Embedded configuration removed.")
    return redirect("bi:embedded_analytics_config_list")


@login_required
def embedded_analytics_config_preview(request, pk):
    config = bi_object(
        request,
        EmbeddedAnalyticsConfig,
        pk,
        select_related=("dashboard", "report", "semantic_model"),
    )

    # Telemetry increment
    EmbeddedAnalyticsConfig.objects.filter(pk=config.pk).update(
        view_count=config.view_count + 1,
        last_accessed_at=timezone.now(),
    )

    context = {
        "config": config,
        "target": config.dashboard or config.report or config.semantic_model,
    }
    return render(
        request,
        "bi/embedded_mobile_bi/embeddedanalyticsconfig/preview.html",
        context,
    )
