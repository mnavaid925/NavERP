from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.Marketplace.MarketplaceVendorForms import (
    MarketplaceVendorForm,
    VendorKycVerificationForm,
    VendorSuspensionForm,
)
from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def marketplacevendor_list(request):
    qs = ecommerce_scope(MarketplaceVendor.objects.all(), request).select_related("party", "owner_user")

    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    kyc_filter = request.GET.get("kyc_status", "").strip()
    commission_filter = request.GET.get("commission_type", "").strip()

    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(store_name__icontains=query)
            | Q(slug__icontains=query)
            | Q(party__name__icontains=query)
            | Q(support_email__icontains=query)
        )

    if status_filter:
        qs = qs.filter(status=status_filter)

    if kyc_filter:
        qs = qs.filter(kyc_status=kyc_filter)

    if commission_filter:
        qs = qs.filter(commission_type=commission_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "vendors": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "query": query,
        "status_filter": status_filter,
        "kyc_filter": kyc_filter,
        "commission_filter": commission_filter,
        "status_choices": MarketplaceVendor.STATUS_CHOICES,
        "kyc_status_choices": MarketplaceVendor.KYC_STATUS_CHOICES,
        "commission_type_choices": MarketplaceVendor.COMMISSION_TYPE_CHOICES,
    }
    return render(request, "ecommerce/marketplace/marketplacevendor/list.html", context)


@login_required
def marketplacevendor_detail(request, pk):
    vendor = ecommerce_object(
        request,
        MarketplaceVendor,
        pk,
        select_related=("party", "owner_user", "suspended_by"),
    )

    listings = vendor.product_listings.select_related("product", "variant").order_by("-created_at")[:10]
    sub_orders = vendor.sub_orders.select_related("order").order_by("-created_at")[:10]
    payouts = vendor.payouts.order_by("-period_end")[:10]
    disputes = vendor.sub_orders.exclude(dispute_status="none").order_by("-updated_at")[:10]

    kyc_form = VendorKycVerificationForm(
        initial={
            "kyc_status": vendor.kyc_status,
            "kyc_document_type": vendor.kyc_document_type,
            "kyc_notes": vendor.kyc_notes,
        }
    )
    suspend_form = VendorSuspensionForm(initial={"suspension_reason": vendor.suspension_reason})

    context = {
        "vendor": vendor,
        "listings": listings,
        "sub_orders": sub_orders,
        "payouts": payouts,
        "disputes": disputes,
        "kyc_form": kyc_form,
        "suspend_form": suspend_form,
    }
    return render(request, "ecommerce/marketplace/marketplacevendor/detail.html", context)


@login_required
@tenant_admin_required
def marketplacevendor_create(request):
    if request.method == "POST":
        form = MarketplaceVendorForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            vendor = form.save(commit=False)
            vendor.tenant = request.tenant
            vendor.save()
            write_audit_log(
                request.user,
                vendor,
                "create",
                {"store_name": vendor.store_name, "number": vendor.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Marketplace vendor '{vendor.store_name}' registered successfully.")
            return redirect("ecommerce:marketplacevendor_detail", pk=vendor.pk)
    else:
        form = MarketplaceVendorForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/marketplace/marketplacevendor/form.html", context)


@login_required
@tenant_admin_required
def marketplacevendor_edit(request, pk):
    vendor = ecommerce_object(request, MarketplaceVendor, pk)
    if request.method == "POST":
        form = MarketplaceVendorForm(request.POST, instance=vendor, tenant=request.tenant)
        if form.is_valid():
            vendor = form.save()
            write_audit_log(
                request.user,
                vendor,
                "update",
                {"store_name": vendor.store_name, "status": vendor.status},
                tenant=request.tenant,
            )
            messages.success(request, f"Marketplace vendor '{vendor.store_name}' updated.")
            return redirect("ecommerce:marketplacevendor_detail", pk=vendor.pk)
    else:
        form = MarketplaceVendorForm(instance=vendor, tenant=request.tenant)

    context = {
        "vendor": vendor,
        "form": form,
        "is_edit": True,
    }
    return render(request, "ecommerce/marketplace/marketplacevendor/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def marketplacevendor_delete(request, pk):
    vendor = ecommerce_object(request, MarketplaceVendor, pk)
    store_name = vendor.store_name
    number = vendor.number

    # Prevent deleting vendors with active sub-orders or listings
    if vendor.sub_orders.exists() or vendor.product_listings.exists():
        messages.error(request, f"Cannot delete vendor '{store_name}' because related sub-orders or listings exist.")
        return redirect("ecommerce:marketplacevendor_detail", pk=pk)

    write_audit_log(
        request.user,
        vendor,
        "delete",
        {"store_name": store_name, "number": number},
        tenant=request.tenant,
    )
    vendor.delete()
    messages.success(request, f"Marketplace vendor '{store_name}' deleted.")
    return redirect("ecommerce:marketplacevendor_list")


@login_required
@tenant_admin_required
@require_POST
def marketplacevendor_verify_kyc(request, pk):
    vendor = ecommerce_object(request, MarketplaceVendor, pk)
    form = VendorKycVerificationForm(request.POST)
    if form.is_valid():
        vendor.kyc_status = form.cleaned_data["kyc_status"]
        vendor.kyc_document_type = form.cleaned_data["kyc_document_type"]
        vendor.kyc_notes = form.cleaned_data["kyc_notes"]
        if vendor.kyc_status == "verified":
            vendor.kyc_verified_at = timezone.now()
            if vendor.status in ("draft", "submitted", "under_review"):
                vendor.status = "approved"
        vendor.save(update_fields=["kyc_status", "kyc_document_type", "kyc_notes", "kyc_verified_at", "status"])
        write_audit_log(
            request.user,
            vendor,
            "verify_kyc",
            {"kyc_status": vendor.kyc_status, "verified_at": str(vendor.kyc_verified_at)},
            tenant=request.tenant,
        )
        messages.success(request, f"KYC verification status for '{vendor.store_name}' updated to {vendor.get_kyc_status_display()}.")
    else:
        messages.error(request, "Invalid KYC verification form submission.")
    return redirect("ecommerce:marketplacevendor_detail", pk=pk)


@login_required
@tenant_admin_required
@require_POST
def marketplacevendor_suspend(request, pk):
    vendor = ecommerce_object(request, MarketplaceVendor, pk)
    action = request.POST.get("action", "suspend")
    if action == "reinstate":
        vendor.status = "active"
        vendor.suspension_reason = ""
        vendor.suspended_at = None
        vendor.suspended_by = None
        vendor.save(update_fields=["status", "suspension_reason", "suspended_at", "suspended_by"])
        write_audit_log(request.user, vendor, "reinstate", {"status": "active"}, tenant=request.tenant)
        messages.success(request, f"Vendor '{vendor.store_name}' has been reinstated to active status.")
    else:
        form = VendorSuspensionForm(request.POST)
        if form.is_valid():
            vendor.status = "suspended"
            vendor.suspension_reason = form.cleaned_data["suspension_reason"]
            vendor.suspended_at = timezone.now()
            vendor.suspended_by = request.user
            vendor.save(update_fields=["status", "suspension_reason", "suspended_at", "suspended_by"])
            write_audit_log(
                request.user,
                vendor,
                "suspend",
                {"reason": vendor.suspension_reason, "suspended_at": str(vendor.suspended_at)},
                tenant=request.tenant,
            )
            messages.warning(request, f"Vendor '{vendor.store_name}' has been suspended.")
        else:
            messages.error(request, "Please provide a valid suspension reason.")
    return redirect("ecommerce:marketplacevendor_detail", pk=pk)
