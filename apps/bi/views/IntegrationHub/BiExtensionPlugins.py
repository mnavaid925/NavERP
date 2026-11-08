from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.IntegrationHub.BiExtensionPlugins import BiExtensionPluginForm
from apps.bi.models.IntegrationHub.BiExtensionPlugins import BiExtensionPlugin
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def bi_extension_plugin_list(request):
    qs = bi_scope(BiExtensionPlugin.objects.all(), request)

    counts = qs.aggregate(
        total=Count("id"),
        enabled=Count("id", filter=Q(status="enabled")),
        verified=Count("id", filter=Q(is_verified=True)),
    )
    total_count = counts["total"] or 0
    enabled_count = counts["enabled"] or 0
    verified_count = counts["verified"] or 0

    # Search query
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(plugin_identifier__icontains=q)
            | Q(author_name__icontains=q)
            | Q(description__icontains=q)
        )

    # Filters
    plugin_type = request.GET.get("plugin_type", "").strip()
    if plugin_type:
        qs = qs.filter(plugin_type=plugin_type)

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "plugins": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "enabled_count": enabled_count,
        "verified_count": verified_count,
        "search_query": q,
        "plugin_type": plugin_type,
        "category": category,
        "status": status,
        "type_choices": BiExtensionPlugin.PLUGIN_TYPE_CHOICES,
        "category_choices": BiExtensionPlugin.CATEGORY_CHOICES,
        "status_choices": BiExtensionPlugin.STATUS_CHOICES,
    }
    return render(
        request,
        "bi/integration_hub/bi_extension_plugin/list.html",
        context,
    )


@login_required
def bi_extension_plugin_detail(request, pk):
    plugin = bi_object(
        request,
        BiExtensionPlugin,
        pk,
        select_related=("installed_by",),
    )
    context = {
        "plugin": plugin,
    }
    return render(
        request,
        "bi/integration_hub/bi_extension_plugin/detail.html",
        context,
    )


@login_required
def bi_extension_plugin_create(request):
    if request.method == "POST":
        form = BiExtensionPluginForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            plugin = form.save(commit=False)
            plugin.tenant = request.tenant
            plugin.installed_by = request.user
            plugin.save()

            write_audit_log(
                request.user,
                plugin,
                "create",
                tenant=request.tenant,
            )
            messages.success(
                request,
                f"Extension plugin '{plugin.name}' registered successfully.",
            )
            return redirect("bi:bi_extension_plugin_detail", pk=plugin.pk)
    else:
        form = BiExtensionPluginForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_create": True,
    }
    return render(
        request,
        "bi/integration_hub/bi_extension_plugin/form.html",
        context,
    )


@login_required
def bi_extension_plugin_edit(request, pk):
    plugin = bi_object(request, BiExtensionPlugin, pk)
    if plugin.is_system_plugin:
        messages.error(request, "System-bundled extension plugins cannot be modified.")
        return redirect("bi:bi_extension_plugin_detail", pk=plugin.pk)

    if request.method == "POST":
        form = BiExtensionPluginForm(
            request.POST,
            instance=plugin,
            tenant=request.tenant,
        )
        if form.is_valid():
            plugin = form.save()
            write_audit_log(
                request.user,
                plugin,
                "update",
                tenant=request.tenant,
            )
            messages.success(
                request,
                f"Extension plugin '{plugin.name}' updated successfully.",
            )
            return redirect("bi:bi_extension_plugin_detail", pk=plugin.pk)
    else:
        form = BiExtensionPluginForm(
            instance=plugin,
            tenant=request.tenant,
        )

    context = {
        "form": form,
        "plugin": plugin,
        "is_create": False,
    }
    return render(
        request,
        "bi/integration_hub/bi_extension_plugin/form.html",
        context,
    )


@login_required
@require_POST
def bi_extension_plugin_delete(request, pk):
    plugin = bi_object(request, BiExtensionPlugin, pk)
    if plugin.is_system_plugin:
        messages.error(request, "System-bundled extension plugins cannot be deleted.")
        return redirect("bi:bi_extension_plugin_detail", pk=plugin.pk)

    name = plugin.name
    write_audit_log(
        request.user,
        plugin,
        "delete",
        tenant=request.tenant,
    )
    plugin.delete()

    messages.success(request, f"Extension plugin '{name}' uninstalled successfully.")
    return redirect("bi:bi_extension_plugin_list")


@login_required
@require_POST
def bi_extension_plugin_toggle(request, pk):
    plugin = bi_object(request, BiExtensionPlugin, pk)
    if plugin.status == "enabled":
        plugin.status = "disabled"
    else:
        plugin.status = "enabled"
    plugin.save(update_fields=["status"])

    write_audit_log(
        request.user,
        plugin,
        "action",
        changes={"status": plugin.status},
        tenant=request.tenant,
    )
    messages.success(
        request,
        f"Plugin '{plugin.name}' status changed to {plugin.get_status_display()}.",
    )
    return redirect("bi:bi_extension_plugin_detail", pk=plugin.pk)
