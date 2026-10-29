from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST


from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.InventoryStock.ChannelInventorySyncs import ChannelInventorySyncForm
from apps.ecommerce.models.InventoryStock.ChannelInventorySyncs import ChannelInventorySync
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def channelinventorysync_list(request):
    qs = ecommerce_scope(
        ChannelInventorySync.objects.select_related("variant", "variant__product", "fulfillment_center"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    channel_type_filter = request.GET.get("channel_type", "").strip()
    sync_status_filter = request.GET.get("sync_status", "").strip()

    if search_query:
        qs = qs.filter(
            Q(channel_name__icontains=search_query)
            | Q(variant__sku__icontains=search_query)
            | Q(variant__name__icontains=search_query)
            | Q(fulfillment_center__name__icontains=search_query)
        )

    if channel_type_filter:
        qs = qs.filter(channel_type=channel_type_filter)

    if sync_status_filter:
        qs = qs.filter(sync_status=sync_status_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "syncs": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "channel_type_filter": channel_type_filter,
        "sync_status_filter": sync_status_filter,
        "channel_type_choices": ChannelInventorySync.CHANNEL_TYPE_CHOICES,
        "sync_status_choices": ChannelInventorySync.SYNC_STATUS_CHOICES,
    }
    return render(request, "ecommerce/inventorystock/channelinventorysync/list.html", context)


@login_required
def channelinventorysync_detail(request, pk):
    sync = ecommerce_object(
        request,
        ChannelInventorySync,
        pk,
        select_related=("variant", "variant__product", "fulfillment_center"),
    )
    variant = sync.variant
    center = sync.fulfillment_center
    allocations = variant.inventory_allocations.select_related("fulfillment_center").all()

    context = {
        "sync": sync,
        "variant": variant,
        "center": center,
        "allocations": allocations,
    }
    return render(request, "ecommerce/inventorystock/channelinventorysync/detail.html", context)



@login_required
def channelinventorysync_create(request):
    initial_variant_id = request.GET.get("variant")
    initial_data = {}
    if initial_variant_id and initial_variant_id.isdigit():
        initial_data["variant"] = int(initial_variant_id)

    if request.method == "POST":
        form = ChannelInventorySyncForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            sync = form.save(commit=False)
            sync.tenant = request.tenant
            sync.last_synced_quantity = sync.calculate_sync_quantity()
            sync.last_synced_at = timezone.now()
            sync.save()
            write_audit_log(
                request.tenant,
                request.user,
                "CREATE",
                "ChannelInventorySync",
                sync.pk,
                f"Created inventory sync feed {sync.channel_name} for SKU {sync.variant.sku} (Qty: {sync.last_synced_quantity})",
            )
            messages.success(request, f"Channel sync feed '{sync.channel_name}' created.")
            return redirect("ecommerce:channelinventorysync_detail", pk=sync.pk)
    else:
        form = ChannelInventorySyncForm(tenant=request.tenant, initial=initial_data)

    context = {
        "form": form,
        "is_create": True,
    }
    return render(request, "ecommerce/inventorystock/channelinventorysync/form.html", context)


@login_required
def channelinventorysync_edit(request, pk):
    sync = ecommerce_object(
        request,
        ChannelInventorySync,
        pk,
        select_related=("variant", "fulfillment_center"),
    )
    if request.method == "POST":
        form = ChannelInventorySyncForm(request.POST, instance=sync, tenant=request.tenant)
        if form.is_valid():
            sync = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "UPDATE",
                "ChannelInventorySync",
                sync.pk,
                f"Updated sync feed {sync.channel_name} for SKU {sync.variant.sku}",
            )
            messages.success(request, f"Channel sync feed '{sync.channel_name}' updated.")
            return redirect("ecommerce:channelinventorysync_detail", pk=sync.pk)
    else:
        form = ChannelInventorySyncForm(instance=sync, tenant=request.tenant)

    context = {
        "form": form,
        "sync": sync,
        "is_create": False,
    }
    return render(request, "ecommerce/inventorystock/channelinventorysync/form.html", context)


@login_required
@require_POST
def channelinventorysync_trigger(request, pk):
    sync = ecommerce_object(
        request,
        ChannelInventorySync,
        pk,
        select_related=("variant", "fulfillment_center"),
    )
    new_qty = sync.calculate_sync_quantity()
    sync.last_synced_quantity = new_qty
    sync.last_synced_at = timezone.now()
    sync.sync_status = "synced"
    sync.error_message = ""
    sync.save()

    write_audit_log(
        request.tenant,
        request.user,
        "UPDATE",
        "ChannelInventorySync",
        sync.pk,
        f"Manually pushed stock sync for {sync.channel_name}: {new_qty} units broadcasted",
    )
    messages.success(request, f"Broadcasted {new_qty} units to channel '{sync.channel_name}'.")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER")
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("ecommerce:channelinventorysync_detail", pk=sync.pk)



@login_required
@tenant_admin_required
@require_POST
def channelinventorysync_delete(request, pk):
    sync = ecommerce_object(request, ChannelInventorySync, pk, select_related=("variant",))
    channel_name = sync.channel_name
    sku = sync.variant.sku
    sync.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "DELETE",
        "ChannelInventorySync",
        pk,
        f"Deleted channel sync {channel_name} for {sku}",
    )
    messages.success(request, f"Channel sync '{channel_name}' was removed.")
    return redirect("ecommerce:channelinventorysync_list")
