from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.InventoryStock.InventoryAllocations import InventoryAllocationForm, StockAdjustmentActionForm
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.InventoryStock.InventoryAllocations import InventoryAllocation
from apps.ecommerce.models.ProductCatalog.Variants import ProductVariant
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def inventoryallocation_list(request):
    qs = ecommerce_scope(
        InventoryAllocation.objects.select_related("product", "variant", "fulfillment_center"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    center_filter = request.GET.get("center", "").strip()
    low_stock_filter = request.GET.get("low_stock", "").strip()

    if search_query:
        qs = qs.filter(
            Q(product__name__icontains=search_query)
            | Q(variant__sku__icontains=search_query)
            | Q(variant__name__icontains=search_query)
            | Q(fulfillment_center__name__icontains=search_query)
            | Q(fulfillment_center__code__icontains=search_query)
            | Q(zone_bin__icontains=search_query)
        )

    # Int filter guard (L11)
    if center_filter.isdigit():
        qs = qs.filter(fulfillment_center_id=int(center_filter))

    if low_stock_filter in ("1", "true"):
        qs = qs.filter(is_low_stock_alert=True)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    centers = ecommerce_scope(FulfillmentCenter.objects.filter(is_active=True), request)

    context = {
        "allocations": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "center_filter": center_filter,
        "low_stock_filter": low_stock_filter,
        "centers": centers,
    }
    return render(request, "ecommerce/inventorystock/inventoryallocation/list.html", context)


@login_required
def inventoryallocation_detail(request, pk):
    allocation = ecommerce_object(
        request,
        InventoryAllocation,
        pk,
        select_related=("product", "variant", "fulfillment_center"),
    )
    variant = allocation.variant
    product = allocation.product
    center = allocation.fulfillment_center

    backorder_policy = getattr(variant, "backorder_policy", None)
    channel_syncs = variant.channel_syncs.select_related("fulfillment_center").all()

    context = {
        "allocation": allocation,
        "variant": variant,
        "product": product,
        "center": center,
        "backorder_policy": backorder_policy,
        "channel_syncs": channel_syncs,
    }
    return render(request, "ecommerce/inventorystock/inventoryallocation/detail.html", context)


@login_required
def inventoryallocation_create(request):
    initial_center_id = request.GET.get("center")
    initial_variant_id = request.GET.get("variant")
    initial_data = {}
    if initial_center_id and initial_center_id.isdigit():
        initial_data["fulfillment_center"] = int(initial_center_id)
    if initial_variant_id and initial_variant_id.isdigit():
        try:
            var = ecommerce_scope(ProductVariant.objects.select_related("product"), request).get(pk=int(initial_variant_id))
            initial_data["variant"] = var.pk
            initial_data["product"] = var.product_id
        except ProductVariant.DoesNotExist:
            pass

    if request.method == "POST":
        form = InventoryAllocationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            alloc = form.save(commit=False)
            alloc.tenant = request.tenant
            alloc.save()
            write_audit_log(
                request.tenant,
                request.user,
                "CREATE",
                "InventoryAllocation",
                alloc.pk,
                f"Allocated SKU {alloc.variant.sku} at center {alloc.fulfillment_center.code}",
            )
            messages.success(request, f"Inventory allocation for '{alloc.variant.sku}' created.")
            return redirect("ecommerce:inventoryallocation_detail", pk=alloc.pk)
    else:
        form = InventoryAllocationForm(tenant=request.tenant, initial=initial_data)

    context = {
        "form": form,
        "is_create": True,
    }
    return render(request, "ecommerce/inventorystock/inventoryallocation/form.html", context)


@login_required
def inventoryallocation_edit(request, pk):
    alloc = ecommerce_object(
        request,
        InventoryAllocation,
        pk,
        select_related=("product", "variant", "fulfillment_center"),
    )
    if request.method == "POST":
        form = InventoryAllocationForm(request.POST, instance=alloc, tenant=request.tenant)
        if form.is_valid():
            alloc = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "UPDATE",
                "InventoryAllocation",
                alloc.pk,
                f"Updated allocation for SKU {alloc.variant.sku} at center {alloc.fulfillment_center.code}",
            )
            messages.success(request, f"Inventory allocation for '{alloc.variant.sku}' updated.")
            return redirect("ecommerce:inventoryallocation_detail", pk=alloc.pk)
    else:
        form = InventoryAllocationForm(instance=alloc, tenant=request.tenant)

    context = {
        "form": form,
        "allocation": alloc,
        "is_create": False,
    }
    return render(request, "ecommerce/inventorystock/inventoryallocation/form.html", context)


@login_required
def inventoryallocation_adjust(request, pk):
    alloc = ecommerce_object(
        request,
        InventoryAllocation,
        pk,
        select_related=("product", "variant", "fulfillment_center"),
    )
    if request.method == "POST":
        form = StockAdjustmentActionForm(request.POST)
        if form.is_valid():
            adj_type = form.cleaned_data["adjustment_type"]
            adj_qty = form.cleaned_data["adjustment_quantity"]
            reason = form.cleaned_data["reason_notes"]

            if alloc.quantity_on_hand + adj_qty < 0:
                form.add_error(
                    "adjustment_quantity",
                    f"Adjustment of {adj_qty:+d} would result in negative on-hand quantity ({alloc.quantity_on_hand + adj_qty}). Current on-hand is {alloc.quantity_on_hand}.",
                )
            else:
                before_qty = alloc.quantity_on_hand
                alloc.quantity_on_hand += adj_qty
                alloc.last_counted_at = timezone.now()
                alloc.save()

                write_audit_log(
                    request.tenant,
                    request.user,
                    "UPDATE",
                    "InventoryAllocation",
                    alloc.pk,
                    f"Adjusted stock for {alloc.variant.sku} ({adj_type}): {before_qty} -> {alloc.quantity_on_hand} ({adj_qty:+d}). Reason: {reason}",
                )
                messages.success(
                    request,
                    f"Stock adjusted by {adj_qty:+d} units (New on-hand: {alloc.quantity_on_hand}).",
                )
                return redirect("ecommerce:inventoryallocation_detail", pk=alloc.pk)
    else:
        form = StockAdjustmentActionForm()

    context = {
        "form": form,
        "allocation": alloc,
    }
    return render(request, "ecommerce/inventorystock/inventoryallocation/adjust.html", context)


@login_required
@tenant_admin_required
@require_POST
def inventoryallocation_delete(request, pk):
    alloc = ecommerce_object(request, InventoryAllocation, pk, select_related=("variant", "fulfillment_center"))
    sku = alloc.variant.sku
    center_code = alloc.fulfillment_center.code
    alloc.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "DELETE",
        "InventoryAllocation",
        pk,
        f"Deleted allocation for {sku} @ {center_code}",
    )
    messages.success(request, f"Allocation for '{sku}' at '{center_code}' was deleted.")
    return redirect("ecommerce:inventoryallocation_list")
