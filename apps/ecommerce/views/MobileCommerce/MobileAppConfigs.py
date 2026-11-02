import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MobileCommerce.MobileAppConfigs import MobileAppConfigForm
from apps.ecommerce.models.MobileCommerce.MobileAppConfigs import MobileAppConfig
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def mobileappconfig_list(request):
    qs = ecommerce_scope(MobileAppConfig.objects.all(), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(app_name__icontains=q)
            | Q(short_name__icontains=q)
            | Q(number__icontains=q)
        )

    is_active_filter = request.GET.get("is_active", "").strip()
    if is_active_filter in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif is_active_filter in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

    pwa_filter = request.GET.get("enable_pwa", "").strip()
    if pwa_filter in ("1", "true", "True"):
        qs = qs.filter(enable_pwa=True)
    elif pwa_filter in ("0", "false", "False"):
        qs = qs.filter(enable_pwa=False)

    total_count = ecommerce_scope(MobileAppConfig.objects.all(), request).count()
    active_count = ecommerce_scope(MobileAppConfig.objects.filter(is_active=True), request).count()
    pwa_count = ecommerce_scope(MobileAppConfig.objects.filter(enable_pwa=True), request).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "configs": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "pwa_count": pwa_count,
        "q": q,
        "selected_is_active": is_active_filter,
        "selected_enable_pwa": pwa_filter,
    }
    return render(request, "ecommerce/mobile/mobile_app_config/list.html", context)


@login_required
def mobileappconfig_detail(request, pk):
    config = ecommerce_object(request, MobileAppConfig, pk)
    manifest_json_str = config.generate_manifest_json()

    context = {
        "config": config,
        "object": config,
        "manifest_json_str": manifest_json_str,
    }
    return render(request, "ecommerce/mobile/mobile_app_config/detail.html", context)


@login_required
@tenant_admin_required
def mobileappconfig_create(request):
    if request.method == "POST":
        form = MobileAppConfigForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            config = form.save(commit=False)
            config.tenant = request.tenant
            config.save()
            write_audit_log(
                user=request.user,
                obj=config,
                action="CREATE",
                changes={"name": config.short_name},
                tenant=request.tenant,
            )
            messages.success(request, f"Mobile App Config '{config.short_name}' created successfully.")
            return redirect("ecommerce:mobileappconfig_detail", pk=config.pk)
    else:
        form = MobileAppConfigForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/mobile/mobile_app_config/form.html", context)


@login_required
@tenant_admin_required
def mobileappconfig_edit(request, pk):
    config = ecommerce_object(request, MobileAppConfig, pk)
    if request.method == "POST":
        form = MobileAppConfigForm(request.POST, instance=config, tenant=request.tenant)
        if form.is_valid():
            config = form.save()
            write_audit_log(
                user=request.user,
                obj=config,
                action="UPDATE",
                changes={"name": config.short_name},
                tenant=request.tenant,
            )
            messages.success(request, f"Mobile App Config '{config.short_name}' updated successfully.")
            return redirect("ecommerce:mobileappconfig_detail", pk=config.pk)
    else:
        form = MobileAppConfigForm(instance=config, tenant=request.tenant)

    context = {
        "form": form,
        "config": config,
        "object": config,
        "is_edit": True,
    }
    return render(request, "ecommerce/mobile/mobile_app_config/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def mobileappconfig_delete(request, pk):
    config = ecommerce_object(request, MobileAppConfig, pk)
    number = config.number
    name = config.short_name
    write_audit_log(
        user=request.user,
        obj=config,
        action="DELETE",
        changes={"number": number, "name": name},
        tenant=request.tenant,
    )
    config.delete()
    messages.success(request, f"Mobile App Config '{name}' ({number}) deleted.")
    return redirect("ecommerce:mobileappconfig_list")


def pwa_manifest_json(request):
    """Serve dynamically generated Web App Manifest for current tenant."""
    tenant = getattr(request, "tenant", None)
    if tenant:
        config = MobileAppConfig.objects.filter(tenant=tenant, is_active=True).first()
    else:
        config = None

    if config:
        manifest_data = config.generate_manifest_dict()
    else:
        manifest_data = {
            "name": "NavERP Mobile Store",
            "short_name": "NavERP Store",
            "start_url": "/",
            "display": "standalone",
            "theme_color": "#2563EB",
            "background_color": "#FFFFFF",
            "icons": [
                {"src": "/static/img/icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/img/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        }

    return HttpResponse(
        json.dumps(manifest_data, indent=2),
        content_type="application/manifest+json",
    )
