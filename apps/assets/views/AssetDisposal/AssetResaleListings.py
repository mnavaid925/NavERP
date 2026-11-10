from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDisposal.AssetResaleListings import (
    AssetResaleAcceptForm,
    AssetResaleBidForm,
    AssetResaleListingForm,
)
from apps.assets.models.AssetDisposal.AssetDisposalRequests import AssetDisposalRequest
from apps.assets.models.AssetDisposal.AssetResaleListings import AssetResaleListing
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def asset_resale_listing_list(request):
    qs = assets_scope(
        AssetResaleListing.objects.select_related(
            "disposal_request",
            "fixed_asset",
            "buyer",
            "broker_auctioneer",
            "managed_by",
        ).defer("terms_and_conditions"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(listing_reference__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(fixed_asset__number__icontains=q)
            | Q(buyer__name__icontains=q)
            | Q(buyer_contact_name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    channel_filter = request.GET.get("listing_channel", "").strip()
    if channel_filter:
        qs = qs.filter(listing_channel=channel_filter)

    payment_status_filter = request.GET.get("payment_status", "").strip()
    if payment_status_filter:
        qs = qs.filter(payment_status=payment_status_filter)

    base_tenant_qs = assets_scope(AssetResaleListing.objects.all(), request)
    total_listings = base_tenant_qs.count()
    active_listings_count = base_tenant_qs.filter(status__in=["listed", "bid_received", "negotiation"]).count()
    sold_count = base_tenant_qs.filter(status__in=["sold", "payment_received", "delivered"]).count()
    proceeds_agg = base_tenant_qs.aggregate(total=Sum("net_sale_proceeds"))
    total_realized_proceeds = proceeds_agg["total"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "resale_listings": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetResaleListing.STATUS_CHOICES,
        "channel_choices": AssetResaleListing.LISTING_CHANNEL_CHOICES,
        "payment_status_choices": AssetResaleListing.PAYMENT_STATUS_CHOICES,
        "total_listings": total_listings,
        "active_listings_count": active_listings_count,
        "sold_count": sold_count,
        "total_realized_proceeds": total_realized_proceeds,
    }
    return render(request, "assets/assetdisposal/asset_resale_listing/list.html", context)


@login_required
def asset_resale_listing_detail(request, pk):
    resale_listing = assets_object(
        request,
        AssetResaleListing,
        pk,
        select_related=[
            "disposal_request",
            "fixed_asset",
            "buyer",
            "broker_auctioneer",
            "managed_by",
            "bill_of_sale_document",
        ],
    )

    bid_form = AssetResaleBidForm()
    accept_form = AssetResaleAcceptForm(tenant=request.tenant, initial={
        "final_sale_amount": resale_listing.highest_bid_amount or resale_listing.asking_price or Decimal("0.00"),
        "commission_rate_percent": resale_listing.commission_rate_percent,
        "buyer": resale_listing.buyer,
        "buyer_contact_name": resale_listing.buyer_contact_name,
    })

    context = {
        "resale_listing": resale_listing,
        "bid_form": bid_form,
        "accept_form": accept_form,
    }
    return render(request, "assets/assetdisposal/asset_resale_listing/detail.html", context)


@login_required
def asset_resale_listing_create(request):
    if request.method == "POST":
        form = AssetResaleListingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                if not instance.managed_by:
                    instance.managed_by = request.user
                instance.calculate_settlement()
                if instance.status == "draft":
                    instance.status = "listed"
                instance.save()

                # Sync disposal request to in_progress if approved
                dr = instance.disposal_request
                if dr and dr.status == "approved":
                    dr.status = "in_progress"
                    dr.save(update_fields=["status", "updated_at"])

                write_audit_log(request.user, instance, "create", tenant=request.tenant)
            messages.success(request, f"Resale listing {instance.number} created successfully.")
            return redirect("assets:asset_resale_listing_detail", pk=instance.pk)
    else:
        initial = {}
        dr_id = request.GET.get("disposal_request")
        if dr_id and dr_id.isdigit():
            initial["disposal_request"] = int(dr_id)
            dr = assets_scope(AssetDisposalRequest.objects.all(), request).filter(pk=int(dr_id)).first()
            if dr and dr.fixed_asset:
                initial["fixed_asset"] = dr.fixed_asset.pk
                initial["asking_price"] = dr.estimated_residual_value or Decimal("0.00")
        form = AssetResaleListingForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "resale_listing": None,
        "is_edit": False,
    }
    return render(request, "assets/assetdisposal/asset_resale_listing/form.html", context)


@login_required
def asset_resale_listing_edit(request, pk):
    instance = assets_object(request, AssetResaleListing, pk)
    if instance.status in ["delivered", "cancelled"]:
        messages.error(request, f"Resale listing {instance.number} is {instance.get_status_display()} and cannot be edited.")
        return redirect("assets:asset_resale_listing_detail", pk=instance.pk)

    if request.method == "POST":
        form = AssetResaleListingForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.calculate_settlement()
                instance.save()
                write_audit_log(request.user, instance, "update", tenant=request.tenant)
            messages.success(request, f"Resale listing {instance.number} updated successfully.")
            return redirect("assets:asset_resale_listing_detail", pk=instance.pk)
    else:
        form = AssetResaleListingForm(instance=instance, tenant=request.tenant)

    context = {
        "form": form,
        "resale_listing": instance,
        "is_edit": True,
    }
    return render(request, "assets/assetdisposal/asset_resale_listing/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def asset_resale_listing_delete(request, pk):
    instance = assets_object(request, AssetResaleListing, pk)
    if instance.status in ["sold", "payment_received", "delivered"]:
        messages.error(request, f"Sold listing {instance.number} cannot be deleted.")
        return redirect("assets:asset_resale_listing_detail", pk=instance.pk)

    with transaction.atomic():
        write_audit_log(request.user, instance, "delete", tenant=request.tenant)
        instance.delete()
    messages.success(request, f"Resale listing {instance.number} deleted successfully.")
    return redirect("assets:asset_resale_listing_list")


@login_required
@require_POST
def asset_resale_listing_record_bid(request, pk):
    instance = assets_object(request, AssetResaleListing, pk)
    form = AssetResaleBidForm(request.POST)
    if form.is_valid():
        with transaction.atomic():
            bid = form.cleaned_data["bid_amount"]
            name = form.cleaned_data["bidder_name"]
            instance.highest_bid_amount = bid
            instance.buyer_contact_name = name
            if form.cleaned_data.get("bidder_email"):
                instance.buyer_contact_email = form.cleaned_data["bidder_email"]
            if form.cleaned_data.get("bidder_phone"):
                instance.buyer_contact_phone = form.cleaned_data["bidder_phone"]
            instance.status = "bid_received"
            instance.save(update_fields=[
                "highest_bid_amount",
                "buyer_contact_name",
                "buyer_contact_email",
                "buyer_contact_phone",
                "status",
                "updated_at",
            ])
            write_audit_log(request.user, instance, "update", tenant=request.tenant)
        messages.success(request, f"Bid of ${bid} recorded from {name} on listing {instance.number}.")
    else:
        messages.error(request, "Invalid bid input. Please verify the amount.")
    return redirect("assets:asset_resale_listing_detail", pk=instance.pk)


@login_required
@require_POST
def asset_resale_listing_accept_sale(request, pk):
    instance = assets_object(request, AssetResaleListing, pk)
    form = AssetResaleAcceptForm(request.tenant, request.POST)
    if form.is_valid():
        with transaction.atomic():
            instance.gross_sale_proceeds = form.cleaned_data["final_sale_amount"]
            instance.commission_rate_percent = form.cleaned_data["commission_rate_percent"]
            if form.cleaned_data.get("buyer"):
                instance.buyer = form.cleaned_data["buyer"]
            if form.cleaned_data.get("buyer_contact_name"):
                instance.buyer_contact_name = form.cleaned_data["buyer_contact_name"]
            instance.calculate_settlement()
            instance.status = "sold"
            instance.save(update_fields=[
                "gross_sale_proceeds",
                "commission_rate_percent",
                "commission_amount",
                "net_sale_proceeds",
                "buyer",
                "buyer_contact_name",
                "status",
                "updated_at",
            ])
            write_audit_log(request.user, instance, "update", tenant=request.tenant)
        messages.success(
            request,
            f"Sale awarded for ${instance.gross_sale_proceeds} (Net: ${instance.net_sale_proceeds}). Status changed to Sold."
        )
    else:
        messages.error(request, "Failed to award sale. Please check entered amounts.")
    return redirect("assets:asset_resale_listing_detail", pk=instance.pk)


@login_required
@require_POST
def asset_resale_listing_mark_paid(request, pk):
    instance = assets_object(request, AssetResaleListing, pk)
    with transaction.atomic():
        instance.payment_status = "paid"
        instance.payment_date = timezone.now().date()
        if instance.status == "sold":
            instance.status = "payment_received"
        instance.save(update_fields=["payment_status", "payment_date", "status", "updated_at"])

        # Synchronize gross sale proceeds to parent disposal request
        dr = instance.disposal_request
        if dr:
            dr.actual_gross_proceeds = (dr.actual_gross_proceeds or Decimal("0.00")) + instance.gross_sale_proceeds
            dr.actual_removal_cost = (dr.actual_removal_cost or Decimal("0.00")) + instance.commission_amount
            dr.calculate_gain_loss()
            dr.save(update_fields=["actual_gross_proceeds", "actual_removal_cost", "realized_gain_loss", "updated_at"])

        write_audit_log(request.user, instance, "update", tenant=request.tenant)
    messages.success(request, f"Remittance received and reconciled for listing {instance.number}. Proceeds synchronized to disposal request.")
    return redirect("assets:asset_resale_listing_detail", pk=instance.pk)


@login_required
@require_POST
def asset_resale_listing_mark_delivered(request, pk):
    instance = assets_object(request, AssetResaleListing, pk)
    with transaction.atomic():
        instance.pickup_delivery_date = timezone.now().date()
        instance.status = "delivered"
        instance.save(update_fields=["pickup_delivery_date", "status", "updated_at"])
        write_audit_log(request.user, instance, "update", tenant=request.tenant)
    messages.success(request, f"Asset collection / delivery logged for {instance.number}. Status marked as Delivered.")
    return redirect("assets:asset_resale_listing_detail", pk=instance.pk)
