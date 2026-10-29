from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.OrderManagement.OrderFulfillments import OrderFulfillmentForm
from apps.ecommerce.models.InventoryStock.FulfillmentCenters import FulfillmentCenter
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder
from apps.ecommerce.models.OrderManagement.OrderFulfillments import OrderFulfillment
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def orderfulfillment_list(request):
    qs = ecommerce_scope(
        OrderFulfillment.objects.select_related("order", "fulfillment_center"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    center_filter = request.GET.get("center", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(carrier_name__icontains=search_query)
            | Q(tracking_number__icontains=search_query)
            | Q(order__number__icontains=search_query)
        )

    if status_filter:
        qs = qs.filter(status=status_filter)

    if center_filter:
        qs = qs.filter(fulfillment_center_id=center_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "fulfillments": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "current_q": search_query,
        "status_choices": OrderFulfillment.PACKAGE_STATUS_CHOICES,
        "centers": FulfillmentCenter.objects.filter(tenant=request.tenant, is_active=True),
        "current_status": status_filter,
        "current_center": center_filter,
    }
    return render(request, "ecommerce/ordermanagement/orderfulfillment/list.html", context)


@login_required
def orderfulfillment_detail(request, pk):
    fulfillment = ecommerce_object(
        request,
        OrderFulfillment,
        pk,
        select_related=("order", "fulfillment_center"),
    )
    return render(request, "ecommerce/ordermanagement/orderfulfillment/detail.html", {"fulfillment": fulfillment})


@login_required
def orderfulfillment_create(request):
    initial_data = {}
    order_id = request.GET.get("order")
    if order_id:
        try:
            order = EcommerceOrder.objects.get(pk=order_id, tenant=request.tenant)
            initial_data["order"] = order
        except EcommerceOrder.DoesNotExist:
            pass

    if request.method == "POST":
        form = OrderFulfillmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            fulfillment = form.save(commit=False)
            fulfillment.tenant = request.tenant
            fulfillment.save()
            write_audit_log(
                request.user,
                fulfillment,
                "create",
                {"number": fulfillment.number, "order": fulfillment.order.number, "carrier": fulfillment.carrier_name},
            )
            messages.success(request, f"Fulfillment package {fulfillment.number} created successfully.")
            return redirect("ecommerce:orderfulfillment_detail", pk=fulfillment.pk)
    else:
        form = OrderFulfillmentForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/ordermanagement/orderfulfillment/form.html", context)


@login_required
def orderfulfillment_edit(request, pk):
    fulfillment = ecommerce_object(request, OrderFulfillment, pk)
    if request.method == "POST":
        form = OrderFulfillmentForm(request.POST, instance=fulfillment, tenant=request.tenant)
        if form.is_valid():
            fulfillment = form.save()
            write_audit_log(
                request.user,
                fulfillment,
                "update",
                {"number": fulfillment.number, "status": fulfillment.status, "tracking": fulfillment.tracking_number},
            )
            messages.success(request, f"Fulfillment {fulfillment.number} updated successfully.")
            return redirect("ecommerce:orderfulfillment_detail", pk=fulfillment.pk)
    else:
        form = OrderFulfillmentForm(instance=fulfillment, tenant=request.tenant)

    context = {
        "form": form,
        "fulfillment": fulfillment,
        "is_edit": True,
    }
    return render(request, "ecommerce/ordermanagement/orderfulfillment/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def orderfulfillment_delete(request, pk):
    fulfillment = ecommerce_object(request, OrderFulfillment, pk)
    ful_number = fulfillment.number
    fulfillment.delete()
    write_audit_log(
        request.user,
        None,
        "delete",
        {"number": ful_number, "entity": "OrderFulfillment"},
    )
    messages.success(request, f"Fulfillment {ful_number} was deleted.")
    return redirect("ecommerce:orderfulfillment_list")


@login_required
@require_POST
def orderfulfillment_ship(request, pk):
    fulfillment = ecommerce_object(request, OrderFulfillment, pk)
    fulfillment.mark_shipped()
    order = fulfillment.order
    all_shipped = not order.fulfillments.exclude(status__in=("shipped", "in_transit", "out_for_delivery", "delivered")).exists()
    if all_shipped:
        order.status = "fulfilled"
        order.fulfillment_status = "fulfilled"
        order.save(update_fields=["status", "fulfillment_status"])
    write_audit_log(
        request.user,
        fulfillment,
        "ship",
        {"number": fulfillment.number, "status": "shipped"},
    )
    messages.success(request, f"Fulfillment package {fulfillment.number} marked as shipped.")
    return redirect("ecommerce:orderfulfillment_detail", pk=fulfillment.pk)
