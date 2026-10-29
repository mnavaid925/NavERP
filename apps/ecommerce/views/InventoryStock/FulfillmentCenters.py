from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.InventoryStock.FulfillmentCenters import FulfillmentCenterForm
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def fulfillmentcenter_list(request):
    qs = ecommerce_scope(FulfillmentCenter.objects.select_related("location"), request)

    search_query = request.GET.get("q", "").strip()
    center_type_filter = request.GET.get("center_type", "").strip()
    is_active_filter = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(city__icontains=search_query)
            | Q(state__icontains=search_query)
        )

    if center_type_filter:
        qs = qs.filter(center_type=center_type_filter)

    if is_active_filter in ("true", "1"):
        qs = qs.filter(is_active=True)
    elif is_active_filter in ("false", "0"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "centers": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "center_type_filter": center_type_filter,
        "is_active_filter": is_active_filter,
        "center_type_choices": FulfillmentCenter.CENTER_TYPE_CHOICES,
    }
    return render(request, "ecommerce/inventorystock/fulfillmentcenter/list.html", context)


@login_required
def fulfillmentcenter_detail(request, pk):
    center = ecommerce_object(request, FulfillmentCenter, pk, select_related=("location",))
    allocations = center.inventory_allocations.select_related("product", "variant").all()[:50]
    sync_channels = center.channel_syncs.select_related("variant").all()[:50]

    context = {
        "center": center,
        "allocations": allocations,
        "sync_channels": sync_channels,
    }
    return render(request, "ecommerce/inventorystock/fulfillmentcenter/detail.html", context)


@login_required
def fulfillmentcenter_create(request):
    if request.method == "POST":
        form = FulfillmentCenterForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            center = form.save(commit=False)
            center.tenant = request.tenant
            center.save()
            write_audit_log(
                request.tenant,
                request.user,
                "CREATE",
                "FulfillmentCenter",
                center.pk,
                f"Created fulfillment center {center.name} ({center.code})",
            )
            messages.success(request, f"Fulfillment center '{center.name}' created successfully.")
            return redirect("ecommerce:fulfillmentcenter_detail", pk=center.pk)
    else:
        form = FulfillmentCenterForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_create": True,
    }
    return render(request, "ecommerce/inventorystock/fulfillmentcenter/form.html", context)


@login_required
def fulfillmentcenter_edit(request, pk):
    center = ecommerce_object(request, FulfillmentCenter, pk)
    if request.method == "POST":
        form = FulfillmentCenterForm(request.POST, instance=center, tenant=request.tenant)
        if form.is_valid():
            center = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "UPDATE",
                "FulfillmentCenter",
                center.pk,
                f"Updated fulfillment center {center.name} ({center.code})",
            )
            messages.success(request, f"Fulfillment center '{center.name}' updated successfully.")
            return redirect("ecommerce:fulfillmentcenter_detail", pk=center.pk)
    else:
        form = FulfillmentCenterForm(instance=center, tenant=request.tenant)

    context = {
        "form": form,
        "center": center,
        "is_create": False,
    }
    return render(request, "ecommerce/inventorystock/fulfillmentcenter/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def fulfillmentcenter_delete(request, pk):
    center = ecommerce_object(request, FulfillmentCenter, pk)
    name = center.name
    center.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "DELETE",
        "FulfillmentCenter",
        pk,
        f"Deleted fulfillment center {name}",
    )
    messages.success(request, f"Fulfillment center '{name}' was deleted.")
    return redirect("ecommerce:fulfillmentcenter_list")
