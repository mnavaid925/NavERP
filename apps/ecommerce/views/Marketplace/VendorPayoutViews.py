from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.Marketplace.VendorPayoutForms import (
    PayoutApprovalForm,
    VendorPayoutForm,
)
from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor
from apps.ecommerce.models.Marketplace.VendorPayouts import VendorPayout
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def vendorpayout_list(request):
    qs = ecommerce_scope(VendorPayout.objects.all(), request).select_related("vendor", "approved_by")

    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("payout_status", "").strip()
    method_filter = request.GET.get("payout_method", "").strip()
    vendor_filter = request.GET.get("vendor", "").strip()

    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(reference_code__icontains=query)
            | Q(vendor__store_name__icontains=query)
            | Q(notes__icontains=query)
        )

    if status_filter:
        qs = qs.filter(payout_status=status_filter)

    if method_filter:
        qs = qs.filter(payout_method=method_filter)

    if vendor_filter and vendor_filter.isdigit():
        qs = qs.filter(vendor_id=int(vendor_filter))

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    vendors = ecommerce_scope(MarketplaceVendor.objects.all(), request).order_by("store_name")

    context = {
        "page_obj": page_obj,
        "payouts": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "query": query,
        "search_query": query,
        "status_filter": status_filter,
        "method_filter": method_filter,
        "vendor_filter": vendor_filter,
        "payout_status_choices": VendorPayout.PAYOUT_STATUS_CHOICES,
        "payout_method_choices": VendorPayout.PAYOUT_METHOD_CHOICES,
        "vendors": vendors,
    }
    return render(request, "ecommerce/marketplace/vendorpayout/list.html", context)


@login_required
def vendorpayout_detail(request, pk):
    payout = ecommerce_object(
        request,
        VendorPayout,
        pk,
        select_related=("vendor", "approved_by"),
    )

    settled_suborders = payout.sub_orders.select_related("order").order_by("-created_at")

    approval_form = PayoutApprovalForm(
        initial={
            "payout_status": payout.payout_status,
            "reference_code": payout.reference_code,
            "notes": payout.notes,
        }
    )

    context = {
        "payout": payout,
        "settled_suborders": settled_suborders,
        "approval_form": approval_form,
    }
    return render(request, "ecommerce/marketplace/vendorpayout/detail.html", context)


@login_required
@tenant_admin_required
def vendorpayout_create(request):
    if request.method == "POST":
        form = VendorPayoutForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            payout = form.save(commit=False)
            payout.tenant = request.tenant
            payout.save()
            write_audit_log(
                request.user,
                payout,
                "create",
                {"number": payout.number, "vendor": payout.vendor.store_name, "net_amount": str(payout.net_payout_amount)},
                tenant=request.tenant,
            )
            messages.success(request, f"Vendor payout batch '{payout.number}' created.")
            return redirect("ecommerce:vendorpayout_detail", pk=payout.pk)
    else:
        form = VendorPayoutForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/marketplace/vendorpayout/form.html", context)


@login_required
@tenant_admin_required
def vendorpayout_edit(request, pk):
    payout = ecommerce_object(request, VendorPayout, pk)
    if request.method == "POST":
        form = VendorPayoutForm(request.POST, instance=payout, tenant=request.tenant)
        if form.is_valid():
            payout = form.save()
            write_audit_log(
                request.user,
                payout,
                "update",
                {"number": payout.number, "status": payout.payout_status},
                tenant=request.tenant,
            )
            messages.success(request, f"Vendor payout batch '{payout.number}' updated.")
            return redirect("ecommerce:vendorpayout_detail", pk=payout.pk)
    else:
        form = VendorPayoutForm(instance=payout, tenant=request.tenant)

    context = {
        "payout": payout,
        "form": form,
        "is_edit": True,
    }
    return render(request, "ecommerce/marketplace/vendorpayout/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def vendorpayout_delete(request, pk):
    payout = ecommerce_object(request, VendorPayout, pk)
    number = payout.number

    if payout.payout_status == "completed":
        messages.error(request, f"Cannot delete payout batch '{number}' because it has already been disbursed.")
        return redirect("ecommerce:vendorpayout_detail", pk=pk)

    # Detach linked sub-orders
    payout.sub_orders.update(payout=None, payout_status="accrued")
    payout.delete()

    write_audit_log(
        request.user,
        payout,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Payout batch '{number}' deleted.")
    return redirect("ecommerce:vendorpayout_list")


@login_required
@tenant_admin_required
@require_POST
def vendorpayout_approve(request, pk):
    payout = ecommerce_object(request, VendorPayout, pk)
    payout.payout_status = "processing"
    payout.approved_by = request.user
    payout.save(update_fields=["payout_status", "approved_by"])
    write_audit_log(
        request.user,
        payout,
        "approve",
        {"status": "processing", "approved_by": request.user.username},
        tenant=request.tenant,
    )
    messages.success(request, f"Payout batch '{payout.number}' approved for processing.")
    return redirect("ecommerce:vendorpayout_detail", pk=pk)


@login_required
@tenant_admin_required
@require_POST
def vendorpayout_execute(request, pk):
    payout = ecommerce_object(request, VendorPayout, pk)
    reference = request.POST.get("reference_code", "").strip() or payout.reference_code
    payout.payout_status = "completed"
    payout.reference_code = reference
    payout.processed_at = timezone.now()
    payout.save(update_fields=["payout_status", "reference_code", "processed_at"])

    # Update all linked sub-orders to paid status
    payout.sub_orders.update(payout_status="paid")

    write_audit_log(
        request.user,
        payout,
        "execute_disbursement",
        {"status": "completed", "reference_code": reference, "processed_at": str(payout.processed_at)},
        tenant=request.tenant,
    )
    messages.success(request, f"Payout batch '{payout.number}' marked completed & disbursed.")
    return redirect("ecommerce:vendorpayout_detail", pk=pk)
