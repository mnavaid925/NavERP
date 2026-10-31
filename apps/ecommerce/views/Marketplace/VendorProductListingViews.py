from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.Marketplace.VendorProductListingForms import (
    ListingModerationForm,
    VendorProductListingForm,
)
from apps.ecommerce.models.Marketplace.MarketplaceVendors import MarketplaceVendor
from apps.ecommerce.models.Marketplace.VendorProductListings import VendorProductListing
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def vendorproductlisting_list(request):
    qs = ecommerce_scope(VendorProductListing.objects.all(), request).select_related(
        "vendor", "product", "variant", "reviewed_by"
    )

    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("moderation_status", "").strip()
    compliance_filter = request.GET.get("compliance_status", "").strip()
    condition_filter = request.GET.get("condition", "").strip()
    vendor_filter = request.GET.get("vendor", "").strip()

    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(seller_sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(product__name__icontains=query)
            | Q(vendor__store_name__icontains=query)
        )

    if status_filter:
        qs = qs.filter(moderation_status=status_filter)

    if compliance_filter:
        qs = qs.filter(compliance_status=compliance_filter)

    if condition_filter:
        qs = qs.filter(condition=condition_filter)

    if vendor_filter and vendor_filter.isdigit():
        qs = qs.filter(vendor_id=int(vendor_filter))

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    vendors = ecommerce_scope(MarketplaceVendor.objects.all(), request).only("id", "store_name").order_by("store_name")

    context = {
        "page_obj": page_obj,
        "listings": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "query": query,
        "search_query": query,
        "status_filter": status_filter,
        "compliance_filter": compliance_filter,
        "condition_filter": condition_filter,
        "vendor_filter": vendor_filter,
        "moderation_status_choices": VendorProductListing.MODERATION_STATUS_CHOICES,
        "compliance_status_choices": VendorProductListing.COMPLIANCE_STATUS_CHOICES,
        "condition_choices": VendorProductListing.CONDITION_CHOICES,
        "vendors": vendors,
    }
    return render(request, "ecommerce/marketplace/vendorproductlisting/list.html", context)


@login_required
def vendorproductlisting_detail(request, pk):
    listing = ecommerce_object(
        request,
        VendorProductListing,
        pk,
        select_related=("vendor", "product__primary_category", "variant", "reviewed_by"),
    )

    moderation_form = ListingModerationForm(
        initial={
            "moderation_status": listing.moderation_status,
            "compliance_status": listing.compliance_status,
            "moderator_notes": listing.moderator_notes,
            "rejection_reason": listing.rejection_reason,
        }
    )

    context = {
        "listing": listing,
        "moderation_form": moderation_form,
    }
    return render(request, "ecommerce/marketplace/vendorproductlisting/detail.html", context)


@login_required
@tenant_admin_required
def vendorproductlisting_create(request):
    if request.method == "POST":
        form = VendorProductListingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.tenant = request.tenant
            if not listing.submitted_at:
                listing.submitted_at = timezone.now()
            listing.save()
            write_audit_log(
                request.user,
                listing,
                "create",
                {"seller_sku": listing.seller_sku, "product": listing.product.name, "number": listing.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Vendor listing for '{listing.product.name}' created.")
            return redirect("ecommerce:vendorproductlisting_detail", pk=listing.pk)
    else:
        form = VendorProductListingForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/marketplace/vendorproductlisting/form.html", context)


@login_required
@tenant_admin_required
def vendorproductlisting_edit(request, pk):
    listing = ecommerce_object(request, VendorProductListing, pk)
    if request.method == "POST":
        form = VendorProductListingForm(request.POST, instance=listing, tenant=request.tenant)
        if form.is_valid():
            listing = form.save()
            write_audit_log(
                request.user,
                listing,
                "update",
                {"seller_sku": listing.seller_sku, "asking_price": str(listing.asking_price)},
                tenant=request.tenant,
            )
            messages.success(request, f"Vendor listing '{listing.seller_sku}' updated.")
            return redirect("ecommerce:vendorproductlisting_detail", pk=listing.pk)
    else:
        form = VendorProductListingForm(instance=listing, tenant=request.tenant)

    context = {
        "listing": listing,
        "form": form,
        "is_edit": True,
    }
    return render(request, "ecommerce/marketplace/vendorproductlisting/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def vendorproductlisting_delete(request, pk):
    listing = ecommerce_object(request, VendorProductListing, pk)
    seller_sku = listing.seller_sku
    number = listing.number

    write_audit_log(
        request.user,
        listing,
        "delete",
        {"seller_sku": seller_sku, "number": number},
        tenant=request.tenant,
    )
    listing.delete()
    messages.success(request, f"Vendor listing '{seller_sku}' deleted.")
    return redirect("ecommerce:vendorproductlisting_list")


@login_required
@tenant_admin_required
@require_POST
def vendorproductlisting_moderate(request, pk):
    listing = ecommerce_object(request, VendorProductListing, pk)
    form = ListingModerationForm(request.POST)
    if form.is_valid():
        listing.moderation_status = form.cleaned_data["moderation_status"]
        listing.compliance_status = form.cleaned_data["compliance_status"]
        listing.moderator_notes = form.cleaned_data["moderator_notes"]
        listing.rejection_reason = form.cleaned_data["rejection_reason"]
        listing.reviewed_at = timezone.now()
        listing.reviewed_by = request.user
        listing.save(
            update_fields=[
                "moderation_status",
                "compliance_status",
                "moderator_notes",
                "rejection_reason",
                "reviewed_at",
                "reviewed_by",
            ]
        )
        write_audit_log(
            request.user,
            listing,
            "moderate",
            {
                "moderation_status": listing.moderation_status,
                "compliance_status": listing.compliance_status,
                "reviewed_at": str(listing.reviewed_at),
            },
            tenant=request.tenant,
        )
        messages.success(request, f"Moderation decision for '{listing.seller_sku}' saved as {listing.get_moderation_status_display()}.")
    else:
        messages.error(request, "Invalid moderation submission.")
    return redirect("ecommerce:vendorproductlisting_detail", pk=pk)
