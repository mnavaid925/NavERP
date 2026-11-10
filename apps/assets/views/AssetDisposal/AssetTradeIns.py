from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDisposal.AssetTradeIns import AssetTradeInForm
from apps.assets.models.AssetDisposal.AssetDisposalRequests import AssetDisposalRequest
from apps.assets.models.AssetDisposal.AssetTradeIns import AssetTradeIn
from apps.assets.views._common import assets_object, assets_scope
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log


@login_required
def asset_trade_in_list(request):
    qs = assets_scope(
        AssetTradeIn.objects.select_related(
            "disposal_request",
            "retired_fixed_asset",
            "vendor",
            "replacement_fixed_asset",
            "authorized_by",
        ).defer("notes"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(agreement_number__icontains=q)
            | Q(retired_fixed_asset__name__icontains=q)
            | Q(retired_fixed_asset__number__icontains=q)
            | Q(vendor__name__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    vendor_filter = request.GET.get("vendor", "").strip()
    if vendor_filter and vendor_filter.isdigit():
        qs = qs.filter(vendor_id=int(vendor_filter))

    base_tenant_qs = assets_scope(AssetTradeIn.objects.all(), request)
    kpi_agg = base_tenant_qs.aggregate(
        total_trade_ins=Count("id"),
        pending_handover=Count("id", filter=Q(status__in=["proposed", "negotiated", "accepted"])),
        settled_count=Count("id", filter=Q(status="credit_settled")),
        total_trade_credit=Sum("net_credit_applied"),
    )
    total_trade_ins = kpi_agg["total_trade_ins"] or 0
    pending_handover_count = kpi_agg["pending_handover"] or 0
    settled_count = kpi_agg["settled_count"] or 0
    total_trade_credit = kpi_agg["total_trade_credit"] or Decimal("0.00")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "trade_ins": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": AssetTradeIn.STATUS_CHOICES,
        "vendor_list": Party.objects.filter(tenant=request.tenant),
        "total_trade_ins": total_trade_ins,
        "pending_handover_count": pending_handover_count,
        "settled_count": settled_count,
        "total_trade_credit": total_trade_credit,
    }
    return render(request, "assets/assetdisposal/asset_trade_in/list.html", context)


@login_required
def asset_trade_in_detail(request, pk):
    trade_in = assets_object(
        request,
        AssetTradeIn,
        pk,
        select_related=[
            "disposal_request",
            "retired_fixed_asset",
            "vendor",
            "replacement_requisition",
            "replacement_fixed_asset",
            "authorized_by",
            "agreement_document",
        ],
    )

    context = {
        "trade_in": trade_in,
    }
    return render(request, "assets/assetdisposal/asset_trade_in/detail.html", context)


@login_required
def asset_trade_in_create(request):
    if request.method == "POST":
        form = AssetTradeInForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.tenant = request.tenant
                if not instance.authorized_by:
                    instance.authorized_by = request.user
                instance.calculate_trade_credit()
                if instance.status == "draft":
                    instance.status = "proposed"
                instance.save()

                # Sync disposal request to in_progress if approved
                dr = instance.disposal_request
                if dr and dr.status == "approved":
                    dr.status = "in_progress"
                    dr.save(update_fields=["status", "updated_at"])

                write_audit_log(request.user, instance, "create", tenant=request.tenant)
            messages.success(request, f"Trade-in agreement {instance.number} created successfully.")
            return redirect("assets:asset_trade_in_detail", pk=instance.pk)
    else:
        initial = {}
        dr_id = request.GET.get("disposal_request")
        if dr_id and dr_id.isdigit():
            initial["disposal_request"] = int(dr_id)
            dr = assets_scope(AssetDisposalRequest.objects.all(), request).filter(pk=int(dr_id)).first()
            if dr and dr.fixed_asset:
                initial["retired_fixed_asset"] = dr.fixed_asset.pk
                initial["trade_in_allowance"] = dr.estimated_residual_value or Decimal("0.00")
        form = AssetTradeInForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "trade_in": None,
        "is_edit": False,
    }
    return render(request, "assets/assetdisposal/asset_trade_in/form.html", context)


@login_required
def asset_trade_in_edit(request, pk):
    instance = assets_object(request, AssetTradeIn, pk)
    if instance.status in ["credit_settled", "cancelled"]:
        messages.error(request, f"Trade-in {instance.number} is {instance.get_status_display()} and cannot be modified.")
        return redirect("assets:asset_trade_in_detail", pk=instance.pk)

    if request.method == "POST":
        form = AssetTradeInForm(request.POST, instance=instance, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                instance = form.save(commit=False)
                instance.calculate_trade_credit()
                instance.save()
                write_audit_log(request.user, instance, "update", tenant=request.tenant)
            messages.success(request, f"Trade-in agreement {instance.number} updated successfully.")
            return redirect("assets:asset_trade_in_detail", pk=instance.pk)
    else:
        form = AssetTradeInForm(instance=instance, tenant=request.tenant)

    context = {
        "form": form,
        "trade_in": instance,
        "is_edit": True,
    }
    return render(request, "assets/assetdisposal/asset_trade_in/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def asset_trade_in_delete(request, pk):
    instance = assets_object(request, AssetTradeIn, pk)
    if instance.status in ["equipment_surrendered", "credit_settled"]:
        messages.error(request, f"Trade-in {instance.number} has already executed physical handover or credit settlement.")
        return redirect("assets:asset_trade_in_detail", pk=instance.pk)

    with transaction.atomic():
        write_audit_log(request.user, instance, "delete", tenant=request.tenant)
        instance.delete()
    messages.success(request, f"Trade-in record {instance.number} deleted successfully.")
    return redirect("assets:asset_trade_in_list")


@login_required
@require_POST
def asset_trade_in_surrender(request, pk):
    instance = assets_object(request, AssetTradeIn, pk)
    if instance.status == "equipment_surrendered":
        messages.info(request, f"Equipment for trade-in {instance.number} has already been surrendered.")
        return redirect("assets:asset_trade_in_detail", pk=instance.pk)
    if instance.status not in ["draft", "proposed", "negotiated", "accepted"]:
        messages.warning(request, f"Trade-in {instance.number} cannot be surrendered from {instance.get_status_display()}.")
        return redirect("assets:asset_trade_in_detail", pk=instance.pk)

    with transaction.atomic():
        instance.surrendered_at = timezone.now()
        instance.status = "equipment_surrendered"
        instance.save(update_fields=["surrendered_at", "status", "updated_at"])
        write_audit_log(request.user, instance, "update", tenant=request.tenant)
    messages.success(request, f"Equipment physical handover confirmed for trade-in {instance.number}.")
    return redirect("assets:asset_trade_in_detail", pk=instance.pk)


@login_required
@require_POST
def asset_trade_in_settle(request, pk):
    instance = assets_object(request, AssetTradeIn, pk)
    if instance.status == "credit_settled":
        messages.info(request, f"Trade-in {instance.number} has already been settled.")
        return redirect("assets:asset_trade_in_detail", pk=instance.pk)
    if instance.status not in ["accepted", "equipment_surrendered"]:
        messages.warning(request, f"Trade-in {instance.number} must be accepted or equipment surrendered before credit settlement.")
        return redirect("assets:asset_trade_in_detail", pk=instance.pk)

    with transaction.atomic():
        instance.settled_at = timezone.now()
        instance.status = "credit_settled"
        instance.calculate_trade_credit()
        instance.save(update_fields=["settled_at", "status", "net_credit_applied", "net_cash_outflow", "updated_at"])

        # Sync trade credit to parent disposal request actual_gross_proceeds
        dr = instance.disposal_request
        if dr:
            dr.actual_gross_proceeds = (dr.actual_gross_proceeds or Decimal("0.00")) + instance.net_credit_applied
            dr.calculate_gain_loss()
            dr.save(update_fields=["actual_gross_proceeds", "realized_gain_loss", "updated_at"])

        write_audit_log(request.user, instance, "update", tenant=request.tenant)
    messages.success(
        request,
        f"Trade allowance of ${instance.net_credit_applied} settled against new purchase. "
        f"Proceeds synchronized to disposal request."
    )
    return redirect("assets:asset_trade_in_detail", pk=instance.pk)
