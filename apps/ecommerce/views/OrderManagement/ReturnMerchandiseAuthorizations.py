from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.OrderManagement.ReturnMerchandiseAuthorizations import ReturnMerchandiseAuthorizationForm
from apps.ecommerce.models.OrderManagement.EcommerceOrders import EcommerceOrder
from apps.ecommerce.models.OrderManagement.ReturnMerchandiseAuthorizations import ReturnMerchandiseAuthorization
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def returnmerchandiseauthorization_list(request):
    qs = ecommerce_scope(
        ReturnMerchandiseAuthorization.objects.select_related("order", "customer", "restocking_center"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    type_filter = request.GET.get("return_type", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(order__number__icontains=search_query)
            | Q(customer__name__icontains=search_query)
            | Q(return_tracking_number__icontains=search_query)
        )

    if status_filter:
        qs = qs.filter(status=status_filter)

    if type_filter:
        qs = qs.filter(return_type=type_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "returns": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "current_q": search_query,
        "status_choices": ReturnMerchandiseAuthorization.RMA_STATUS_CHOICES,
        "return_type_choices": ReturnMerchandiseAuthorization.RETURN_TYPE_CHOICES,
        "reason_choices": ReturnMerchandiseAuthorization.RETURN_REASON_CHOICES,
        "current_status": status_filter,
        "current_type": type_filter,
    }
    return render(request, "ecommerce/ordermanagement/returnmerchandiseauthorization/list.html", context)


@login_required
def returnmerchandiseauthorization_detail(request, pk):
    rma = ecommerce_object(
        request,
        ReturnMerchandiseAuthorization,
        pk,
        select_related=("order", "customer", "restocking_center"),
    )
    return render(request, "ecommerce/ordermanagement/returnmerchandiseauthorization/detail.html", {"rma": rma})


@login_required
def returnmerchandiseauthorization_create(request):
    initial_data = {}
    order_id = request.GET.get("order")
    if order_id:
        try:
            order = EcommerceOrder.objects.get(pk=order_id, tenant=request.tenant)
            initial_data["order"] = order
            initial_data["customer"] = order.customer
        except EcommerceOrder.DoesNotExist:
            pass

    if request.method == "POST":
        form = ReturnMerchandiseAuthorizationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rma = form.save(commit=False)
            rma.tenant = request.tenant
            rma.save()
            write_audit_log(
                request.user,
                rma,
                "create",
                {"number": rma.number, "order": rma.order.number, "type": rma.return_type},
            )
            messages.success(request, f"RMA {rma.number} initiated successfully.")
            return redirect("ecommerce:returnmerchandiseauthorization_detail", pk=rma.pk)
    else:
        form = ReturnMerchandiseAuthorizationForm(initial=initial_data, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/ordermanagement/returnmerchandiseauthorization/form.html", context)


@login_required
def returnmerchandiseauthorization_edit(request, pk):
    rma = ecommerce_object(request, ReturnMerchandiseAuthorization, pk)
    if request.method == "POST":
        form = ReturnMerchandiseAuthorizationForm(request.POST, instance=rma, tenant=request.tenant)
        if form.is_valid():
            rma = form.save()
            write_audit_log(
                request.user,
                rma,
                "update",
                {"number": rma.number, "status": rma.status, "refund_status": rma.refund_status},
            )
            messages.success(request, f"RMA {rma.number} updated successfully.")
            return redirect("ecommerce:returnmerchandiseauthorization_detail", pk=rma.pk)
    else:
        form = ReturnMerchandiseAuthorizationForm(instance=rma, tenant=request.tenant)

    context = {
        "form": form,
        "rma": rma,
        "is_edit": True,
    }
    return render(request, "ecommerce/ordermanagement/returnmerchandiseauthorization/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def returnmerchandiseauthorization_delete(request, pk):
    rma = ecommerce_object(request, ReturnMerchandiseAuthorization, pk)
    rma_number = rma.number
    rma.delete()
    write_audit_log(
        request.user,
        None,
        "delete",
        {"number": rma_number, "entity": "ReturnMerchandiseAuthorization"},
    )
    messages.success(request, f"RMA {rma_number} was deleted.")
    return redirect("ecommerce:returnmerchandiseauthorization_list")


@login_required
@require_POST
def returnmerchandiseauthorization_complete(request, pk):
    rma = ecommerce_object(request, ReturnMerchandiseAuthorization, pk)
    rma.complete_settlement()
    write_audit_log(
        request.user,
        rma,
        "complete",
        {"number": rma.number, "refund": str(rma.refund_amount)},
    )
    messages.success(request, f"RMA {rma.number} settlement completed.")
    return redirect("ecommerce:returnmerchandiseauthorization_detail", pk=rma.pk)
