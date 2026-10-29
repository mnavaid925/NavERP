from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.OrderManagement.EcommerceOrders import EcommerceOrderForm
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def ecommerceorder_list(request):
    qs = ecommerce_scope(
        EcommerceOrder.objects.select_related("customer", "currency", "applied_coupon"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    payment_filter = request.GET.get("payment_status", "").strip()
    fulfillment_filter = request.GET.get("fulfillment_status", "").strip()
    fraud_filter = request.GET.get("fraud_risk_level", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(customer__name__icontains=search_query)
            | Q(guest_email__icontains=search_query)
            | Q(shipping_name__icontains=search_query)
            | Q(shipping_city__icontains=search_query)
        )

    if status_filter:
        qs = qs.filter(status=status_filter)

    if payment_filter:
        qs = qs.filter(payment_status=payment_filter)

    if fulfillment_filter:
        qs = qs.filter(fulfillment_status=fulfillment_filter)

    if fraud_filter:
        qs = qs.filter(fraud_risk_level=fraud_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "orders": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "current_q": search_query,
        "status_choices": EcommerceOrder.STATUS_CHOICES,
        "payment_status_choices": EcommerceOrder.PAYMENT_STATUS_CHOICES,
        "fulfillment_status_choices": EcommerceOrder.FULFILLMENT_STATUS_CHOICES,
        "fraud_risk_choices": EcommerceOrder.FRAUD_RISK_CHOICES,
        "current_status": status_filter,
        "current_payment": payment_filter,
        "current_fulfillment": fulfillment_filter,
        "current_fraud": fraud_filter,
    }
    return render(request, "ecommerce/ordermanagement/ecommerceorder/list.html", context)


@login_required
def ecommerceorder_detail(request, pk):
    order = ecommerce_object(
        request,
        EcommerceOrder,
        pk,
        select_related=("customer", "currency", "applied_coupon", "shipping_address", "billing_address"),
        prefetch_related=("lines__product", "lines__variant", "fulfillments__fulfillment_center", "returns"),
    )
    context = {
        "order": order,
        "lines": order.lines.all(),
        "fulfillments": order.fulfillments.all(),
        "returns": order.returns.all(),
    }
    return render(request, "ecommerce/ordermanagement/ecommerceorder/detail.html", context)


@login_required
def ecommerceorder_create(request):
    if request.method == "POST":
        form = EcommerceOrderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            order = form.save(commit=False)
            order.tenant = request.tenant
            order.save()
            order.recalculate_totals()
            write_audit_log(
                request.user,
                order,
                "create",
                {"number": order.number, "customer": order.customer.name, "total": str(order.total_amount)},
            )
            messages.success(request, f"eCommerce Order {order.number} created successfully.")
            return redirect("ecommerce:ecommerceorder_detail", pk=order.pk)
    else:
        form = EcommerceOrderForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/ordermanagement/ecommerceorder/form.html", context)


@login_required
def ecommerceorder_edit(request, pk):
    order = ecommerce_object(request, EcommerceOrder, pk)
    if request.method == "POST":
        form = EcommerceOrderForm(request.POST, instance=order, tenant=request.tenant)
        if form.is_valid():
            order = form.save()
            order.recalculate_totals()
            write_audit_log(
                request.user,
                order,
                "update",
                {"number": order.number, "status": order.status},
            )
            messages.success(request, f"Order {order.number} updated successfully.")
            return redirect("ecommerce:ecommerceorder_detail", pk=order.pk)
    else:
        form = EcommerceOrderForm(instance=order, tenant=request.tenant)

    context = {
        "form": form,
        "order": order,
        "is_edit": True,
    }
    return render(request, "ecommerce/ordermanagement/ecommerceorder/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def ecommerceorder_delete(request, pk):
    order = ecommerce_object(request, EcommerceOrder, pk)
    order_number = order.number
    order.delete()
    write_audit_log(
        request.user,
        None,
        "delete",
        {"number": order_number, "entity": "EcommerceOrder"},
    )
    messages.success(request, f"Order {order_number} has been deleted.")
    return redirect("ecommerce:ecommerceorder_list")


@login_required
@require_POST
def ecommerceorder_cancel(request, pk):
    order = ecommerce_object(request, EcommerceOrder, pk)
    reason = request.POST.get("cancellation_reason", "Customer requested cancellation").strip()
    if order.cancel_order(reason=reason):
        write_audit_log(
            request.user,
            order,
            "cancel",
            {"number": order.number, "reason": reason},
        )
        messages.success(request, f"Order {order.number} was cancelled.")
    else:
        messages.error(request, f"Order {order.number} cannot be cancelled in its current state ({order.get_status_display()}).")
    return redirect("ecommerce:ecommerceorder_detail", pk=order.pk)
