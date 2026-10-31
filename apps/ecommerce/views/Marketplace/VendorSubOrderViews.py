from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.Marketplace.VendorSubOrderForms import (
    SubOrderDisputeForm,
    SubOrderFulfillmentForm,
    SubOrderReviewForm,
    VendorSubOrderForm,
)
from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor
from apps.ecommerce.models.Marketplace.VendorSubOrders import VendorSubOrder
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def vendorsuborder_list(request):
    qs = ecommerce_scope(VendorSubOrder.objects.all(), request).select_related("vendor", "order", "payout")

    query = request.GET.get("q", "").strip()
    fulfillment_filter = request.GET.get("fulfillment_status", "").strip()
    sla_filter = request.GET.get("sla_status", "").strip()
    payout_filter = request.GET.get("payout_status", "").strip()
    dispute_filter = request.GET.get("dispute_status", "").strip()
    vendor_filter = request.GET.get("vendor", "").strip()

    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(order__number__icontains=query)
            | Q(tracking_number__icontains=query)
            | Q(vendor__store_name__icontains=query)
            | Q(carrier_name__icontains=query)
        )

    if fulfillment_filter:
        qs = qs.filter(fulfillment_status=fulfillment_filter)

    if sla_filter:
        qs = qs.filter(sla_status=sla_filter)

    if payout_filter:
        qs = qs.filter(payout_status=payout_filter)

    if dispute_filter:
        qs = qs.filter(dispute_status=dispute_filter)

    if vendor_filter and vendor_filter.isdigit():
        qs = qs.filter(vendor_id=int(vendor_filter))

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    vendors = ecommerce_scope(MarketplaceVendor.objects.all(), request).only("id", "store_name").order_by("store_name")

    context = {
        "page_obj": page_obj,
        "sub_orders": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "query": query,
        "search_query": query,
        "fulfillment_filter": fulfillment_filter,
        "sla_filter": sla_filter,
        "payout_filter": payout_filter,
        "dispute_filter": dispute_filter,
        "vendor_filter": vendor_filter,
        "fulfillment_status_choices": VendorSubOrder.FULFILLMENT_STATUS_CHOICES,
        "sla_status_choices": VendorSubOrder.SLA_STATUS_CHOICES,
        "payout_status_choices": VendorSubOrder.PAYOUT_STATUS_CHOICES,
        "dispute_status_choices": VendorSubOrder.DISPUTE_STATUS_CHOICES,
        "vendors": vendors,
    }
    return render(request, "ecommerce/marketplace/vendorsuborder/list.html", context)


@login_required
def vendorsuborder_detail(request, pk):
    sub_order = ecommerce_object(
        request,
        VendorSubOrder,
        pk,
        select_related=("vendor", "order__customer", "payout"),
    )

    # Order line items from parent order
    order_lines = sub_order.order.lines.select_related("product", "variant").all() if hasattr(sub_order.order, "lines") else []

    fulfillment_form = SubOrderFulfillmentForm(
        initial={
            "fulfillment_status": sub_order.fulfillment_status,
            "carrier_name": sub_order.carrier_name,
            "tracking_number": sub_order.tracking_number,
            "tracking_url": sub_order.tracking_url,
        }
    )

    dispute_form = SubOrderDisputeForm(
        initial={
            "dispute_status": sub_order.dispute_status,
            "dispute_reason": sub_order.dispute_reason,
            "dispute_notes": sub_order.dispute_notes,
        }
    )

    review_form = SubOrderReviewForm(
        initial={
            "customer_rating": sub_order.customer_rating or 5,
            "customer_feedback": sub_order.customer_feedback,
            "seller_response": sub_order.seller_response,
        }
    )

    context = {
        "sub_order": sub_order,
        "order_lines": order_lines,
        "fulfillment_form": fulfillment_form,
        "dispute_form": dispute_form,
        "review_form": review_form,
    }
    return render(request, "ecommerce/marketplace/vendorsuborder/detail.html", context)


@login_required
@tenant_admin_required
def vendorsuborder_create(request):
    if request.method == "POST":
        form = VendorSubOrderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            sub_order = form.save(commit=False)
            sub_order.tenant = request.tenant
            sub_order.save()
            write_audit_log(
                request.user,
                sub_order,
                "create",
                {"number": sub_order.number, "order": sub_order.order.number, "vendor": sub_order.vendor.store_name},
                tenant=request.tenant,
            )
            messages.success(request, f"Vendor sub-order '{sub_order.number}' created.")
            return redirect("ecommerce:vendorsuborder_detail", pk=sub_order.pk)
    else:
        form = VendorSubOrderForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/marketplace/vendorsuborder/form.html", context)


@login_required
@tenant_admin_required
def vendorsuborder_edit(request, pk):
    sub_order = ecommerce_object(request, VendorSubOrder, pk)
    if request.method == "POST":
        form = VendorSubOrderForm(request.POST, instance=sub_order, tenant=request.tenant)
        if form.is_valid():
            sub_order = form.save()
            write_audit_log(
                request.user,
                sub_order,
                "update",
                {"fulfillment_status": sub_order.fulfillment_status, "payout_status": sub_order.payout_status},
                tenant=request.tenant,
            )
            messages.success(request, f"Vendor sub-order '{sub_order.number}' updated.")
            return redirect("ecommerce:vendorsuborder_detail", pk=sub_order.pk)
    else:
        form = VendorSubOrderForm(instance=sub_order, tenant=request.tenant)

    context = {
        "sub_order": sub_order,
        "form": form,
        "is_edit": True,
    }
    return render(request, "ecommerce/marketplace/vendorsuborder/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def vendorsuborder_delete(request, pk):
    sub_order = ecommerce_object(request, VendorSubOrder, pk)
    number = sub_order.number

    if sub_order.payout_id or sub_order.payout_status == "paid":
        messages.error(request, f"Cannot delete sub-order '{number}' because it is linked to a settled payout.")
        return redirect("ecommerce:vendorsuborder_detail", pk=pk)

    write_audit_log(
        request.user,
        sub_order,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    sub_order.delete()

    messages.success(request, f"Vendor sub-order '{number}' deleted.")
    return redirect("ecommerce:vendorsuborder_list")


@login_required
@tenant_admin_required
@require_POST
def vendorsuborder_fulfill(request, pk):
    sub_order = ecommerce_object(
        request,
        VendorSubOrder,
        pk,
        select_related=("vendor", "order"),
    )
    form = SubOrderFulfillmentForm(request.POST)
    if form.is_valid():
        sub_order.fulfillment_status = form.cleaned_data["fulfillment_status"]
        sub_order.carrier_name = form.cleaned_data["carrier_name"]
        sub_order.tracking_number = form.cleaned_data["tracking_number"]
        sub_order.tracking_url = form.cleaned_data["tracking_url"]
        now = timezone.now()
        if sub_order.fulfillment_status in ("shipped", "delivered") and not sub_order.dispatched_at:
            sub_order.dispatched_at = now
        if sub_order.fulfillment_status == "delivered" and not sub_order.delivered_at:
            sub_order.delivered_at = now
        sub_order.save()
        write_audit_log(
            request.user,
            sub_order,
            "fulfill",
            {"status": sub_order.fulfillment_status, "carrier": sub_order.carrier_name, "tracking": sub_order.tracking_number},
            tenant=request.tenant,
        )
        messages.success(request, f"Fulfillment updated for sub-order '{sub_order.number}'.")
    else:
        messages.error(request, "Invalid fulfillment update submission.")
    return redirect("ecommerce:vendorsuborder_detail", pk=pk)


@login_required
@tenant_admin_required
@require_POST
@transaction.atomic
def vendorsuborder_dispute(request, pk):
    sub_order = ecommerce_object(
        request,
        VendorSubOrder,
        pk,
        select_related=("vendor", "order"),
    )
    form = SubOrderDisputeForm(request.POST)
    if form.is_valid():
        sub_order.dispute_status = form.cleaned_data["dispute_status"]
        sub_order.dispute_reason = form.cleaned_data["dispute_reason"]
        sub_order.dispute_notes = form.cleaned_data["dispute_notes"]
        if sub_order.dispute_status in ("resolved_merchant", "resolved_customer"):
            sub_order.dispute_resolved_at = timezone.now()
            if sub_order.dispute_status == "resolved_customer":
                sub_order.payout_status = "refunded"
            elif sub_order.payout_status == "withheld_dispute":
                sub_order.payout_status = "accrued"
        elif sub_order.dispute_status in ("disputed", "under_investigation"):
            sub_order.payout_status = "withheld_dispute"
        sub_order.save()
        write_audit_log(
            request.user,
            sub_order,
            "dispute",
            {"dispute_status": sub_order.dispute_status, "payout_status": sub_order.payout_status},
            tenant=request.tenant,
        )
        messages.success(request, f"Dispute state updated for sub-order '{sub_order.number}'.")
    else:
        messages.error(request, "Invalid dispute form submission.")
    return redirect("ecommerce:vendorsuborder_detail", pk=pk)
