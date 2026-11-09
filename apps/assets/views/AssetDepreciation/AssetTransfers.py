from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDepreciation.AssetTransfers import AssetTransferForm
from apps.assets.models.AssetDepreciation.AssetTransfers import AssetTransfer
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def transfer_list(request):
    qs = AssetTransfer.objects.filter(tenant=request.tenant).select_related(
        "fixed_asset",
        "operational_asset",
        "source_department",
        "destination_department",
        "source_location",
        "destination_location",
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(fixed_asset__number__icontains=q)
            | Q(reason__icontains=q)
        )

    selected_type = request.GET.get("type", "").strip()
    if selected_type:
        qs = qs.filter(transfer_type=selected_type)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    all_tenant_transfers = AssetTransfer.objects.filter(tenant=request.tenant)
    agg = all_tenant_transfers.aggregate(
        total=Count("id"),
        in_transit=Count("id", filter=Q(status="in_transit")),
        completed=Count("id", filter=Q(status="completed")),
        total_freight=Sum("transportation_cost"),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "transfers": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "transfer_type_choices": AssetTransfer.TRANSFER_TYPE_CHOICES,
        "status_choices": AssetTransfer.STATUS_CHOICES,
        "total_transfers": agg["total"] or 0,
        "in_transit_count": agg["in_transit"] or 0,
        "completed_count": agg["completed"] or 0,
        "total_transport_cost": agg["total_freight"] or Decimal("0.00"),
        "q": q,
        "selected_type": selected_type,
        "selected_status": selected_status,
    }
    return render(request, "assets/asset_depreciation/transfer/list.html", context)


@login_required
def transfer_detail(request, pk):
    transfer = assets_object(
        request,
        AssetTransfer,
        pk=pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "source_department",
            "source_location",
            "source_custodian",
            "source_expense_account",
            "destination_department",
            "destination_location",
            "destination_custodian",
            "destination_expense_account",
            "transferred_by",
            "received_by",
            "journal_entry",
        ],
    )
    context = {
        "transfer": transfer,
        "object": transfer,
    }
    return render(request, "assets/asset_depreciation/transfer/detail.html", context)


@login_required
def transfer_create(request):
    if request.method == "POST":
        form = AssetTransferForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.tenant = request.tenant
            transfer.save()
            transfer.capture_carrying_value()
            transfer.save()
            write_audit_log(request.user, transfer, "create", tenant=request.tenant)
            messages.success(
                request, f"Asset transfer order {transfer.number} created."
            )
            return redirect("assets:transfer_detail", pk=transfer.pk)
    else:
        form = AssetTransferForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "transfer": None,
        "object": None,
    }
    return render(request, "assets/asset_depreciation/transfer/form.html", context)


@login_required
def transfer_edit(request, pk):
    transfer = assets_object(request, AssetTransfer, pk=pk)
    if transfer.status == "completed":
        messages.error(request, "Completed transfers cannot be edited.")
        return redirect("assets:transfer_detail", pk=transfer.pk)

    if request.method == "POST":
        form = AssetTransferForm(
            request.POST, instance=transfer, tenant=request.tenant
        )
        if form.is_valid():
            transfer = form.save(commit=False)
            transfer.save()
            transfer.capture_carrying_value()
            transfer.save()
            write_audit_log(request.user, transfer, "update", tenant=request.tenant)
            messages.success(
                request, f"Asset transfer {transfer.number} updated successfully."
            )
            return redirect("assets:transfer_detail", pk=transfer.pk)
    else:
        form = AssetTransferForm(instance=transfer, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "transfer": transfer,
        "object": transfer,
    }
    return render(request, "assets/asset_depreciation/transfer/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def transfer_delete(request, pk):
    transfer = assets_object(request, AssetTransfer, pk=pk)
    if transfer.status == "completed":
        messages.error(request, "Cannot delete a completed transfer order.")
        return redirect("assets:transfer_detail", pk=transfer.pk)

    num = transfer.number
    transfer.delete()
    write_audit_log(request.user, transfer, "delete", tenant=request.tenant)
    messages.success(request, f"Asset transfer {num} deleted.")
    return redirect("assets:transfer_list")


@login_required
@require_POST
def transfer_dispatch(request, pk):
    transfer = assets_object(request, AssetTransfer, pk=pk)
    try:
        transfer.dispatch_transfer()
        write_audit_log(request.user, transfer, "dispatch", tenant=request.tenant)
        messages.success(request, f"Transfer {transfer.number} marked In Transit.")
    except ValidationError as exc:
        messages.error(request, str(exc.message if hasattr(exc, "message") else exc))

    return redirect("assets:transfer_detail", pk=transfer.pk)


@login_required
@require_POST
@tenant_admin_required
def transfer_complete(request, pk):
    transfer = assets_object(request, AssetTransfer, pk=pk)
    try:
        transfer.complete_transfer(user=request.user)
        write_audit_log(request.user, transfer, "complete", tenant=request.tenant)
        messages.success(
            request,
            f"Transfer {transfer.number} completed. Fixed asset allocations updated.",
        )
    except ValidationError as exc:
        messages.error(request, str(exc.message if hasattr(exc, "message") else exc))

    return redirect("assets:transfer_detail", pk=transfer.pk)
