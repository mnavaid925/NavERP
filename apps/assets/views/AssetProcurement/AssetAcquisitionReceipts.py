from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetProcurement.AssetAcquisitionReceipts import AssetAcquisitionReceiptForm
from apps.assets.models.AssetProcurement.AssetAcquisitionReceipts import AssetAcquisitionReceipt
from apps.assets.views._common import assets_object, assets_scope
from apps.core.utils import write_audit_log
from apps.scm.models import Location


@login_required
def asset_acquisition_receipt_list(request):
    """List dock asset receipts with condition, status, location filters and pagination."""
    queryset = assets_scope(AssetAcquisitionReceipt.objects.all(), request).select_related(
        "requisition", "purchase_order", "vendor", "receiving_location", "inspected_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(serial_number__icontains=q)
            | Q(model_number__icontains=q)
            | Q(manufacturer__icontains=q)
            | Q(tracking_number__icontains=q)
            | Q(carrier_name__icontains=q)
        )

    status = request.GET.get("status", "").strip()
    if status:
        queryset = queryset.filter(status=status)

    condition = request.GET.get("condition", "").strip()
    if condition:
        queryset = queryset.filter(condition_on_arrival=condition)

    location_id = request.GET.get("location", "").strip()
    if location_id:
        queryset = queryset.filter(receiving_location_id=location_id)

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    locations = Location.objects.filter(tenant=request.tenant, is_active=True)

    context = {
        "receipts": page_obj,
        "page_obj": page_obj,
        "status_choices": AssetAcquisitionReceipt.STATUS_CHOICES,
        "condition_choices": AssetAcquisitionReceipt.CONDITION_CHOICES,
        "locations": locations,
    }
    return render(request, "assets/asset_procurement/asset_acquisition_receipt/list.html", context)


@login_required
def asset_acquisition_receipt_detail(request, pk):
    """Display comprehensive details of an asset intake receipt."""
    receipt = assets_object(
        request,
        AssetAcquisitionReceipt,
        pk,
        select_related=(
            "requisition",
            "purchase_order",
            "vendor",
            "receiving_location",
            "inspected_by",
        ),
    )
    return render(
        request,
        "assets/asset_procurement/asset_acquisition_receipt/detail.html",
        {"receipt": receipt},
    )


@login_required
def asset_acquisition_receipt_create(request):
    """Log a new physical asset receipt on the dock or staging floor."""
    if request.method == "POST":
        form = AssetAcquisitionReceiptForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rcv = form.save(commit=False)
            rcv.tenant = request.tenant
            rcv.save()
            write_audit_log(
                request.user,
                rcv,
                "create",
                changes={"details": f"Received asset shipment {rcv.number} ({rcv.title}), serial: {rcv.serial_number}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Asset Receipt {rcv.number} logged successfully.")
            return redirect("assets:asset_acquisition_receipt_detail", pk=rcv.pk)
    else:
        form = AssetAcquisitionReceiptForm(tenant=request.tenant)

    return render(
        request,
        "assets/asset_procurement/asset_acquisition_receipt/form.html",
        {"form": form, "receipt": None, "is_edit": False},
    )


@login_required
def asset_acquisition_receipt_edit(request, pk):
    """Update details of an asset intake receipt."""
    receipt = assets_object(request, AssetAcquisitionReceipt, pk)

    if request.method == "POST":
        form = AssetAcquisitionReceiptForm(request.POST, instance=receipt, tenant=request.tenant)
        if form.is_valid():
            rcv = form.save()
            write_audit_log(
                request.user,
                rcv,
                "update",
                changes={"details": f"Updated asset receipt {rcv.number}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Asset Receipt {rcv.number} updated successfully.")
            return redirect("assets:asset_acquisition_receipt_detail", pk=rcv.pk)
    else:
        form = AssetAcquisitionReceiptForm(instance=receipt, tenant=request.tenant)

    return render(
        request,
        "assets/asset_procurement/asset_acquisition_receipt/form.html",
        {"form": form, "receipt": receipt, "is_edit": True},
    )


@login_required
@require_POST
def asset_acquisition_receipt_delete(request, pk):
    """Delete an asset intake receipt."""
    receipt = assets_object(request, AssetAcquisitionReceipt, pk)
    number = receipt.number
    write_audit_log(
        request.user,
        receipt,
        "delete",
        changes={"details": f"Deleted asset receipt {number}"},
        tenant=request.tenant,
    )
    receipt.delete()
    messages.success(request, f"Asset Receipt {number} was deleted.")
    return redirect("assets:asset_acquisition_receipt_list")


@login_required
@require_POST
def asset_acquisition_receipt_inspect(request, pk):
    """Inspect and accept a received asset shipment."""
    receipt = assets_object(request, AssetAcquisitionReceipt, pk)
    if not receipt.can_inspect_accept():
        messages.error(request, f"Receipt {receipt.number} cannot be accepted in state '{receipt.get_status_display()}'.")
        return redirect("assets:asset_acquisition_receipt_detail", pk=receipt.pk)

    notes = request.POST.get("inspection_notes", "").strip()
    if notes:
        existing = receipt.inspection_notes
        receipt.inspection_notes = f"{existing}\n[Accepted by {request.user.username}]: {notes}".strip()

    receipt.status = "accepted"
    receipt.inspected_by = request.user
    receipt.inspected_at = timezone.now()
    receipt.save(update_fields=["status", "inspected_by", "inspected_at", "inspection_notes", "updated_at"])

    write_audit_log(
        request.user,
        receipt,
        "update",
        changes={"action": "inspect_accept", "details": f"Inspected and accepted asset receipt {receipt.number}"},
        tenant=request.tenant,
    )
    messages.success(request, f"Asset Receipt {receipt.number} inspected and accepted.")
    return redirect("assets:asset_acquisition_receipt_detail", pk=receipt.pk)


@login_required
@require_POST
def asset_acquisition_receipt_quarantine(request, pk):
    """Place a received asset shipment in quarantine or on-hold."""
    receipt = assets_object(request, AssetAcquisitionReceipt, pk)
    if not receipt.can_quarantine():
        messages.error(request, f"Receipt {receipt.number} cannot be quarantined in state '{receipt.get_status_display()}'.")
        return redirect("assets:asset_acquisition_receipt_detail", pk=receipt.pk)

    reason = request.POST.get("quarantine_reason", "").strip()
    existing = receipt.inspection_notes
    receipt.inspection_notes = f"{existing}\n[Quarantined by {request.user.username}]: {reason}".strip()

    receipt.status = "quarantined"
    receipt.inspected_by = request.user
    receipt.inspected_at = timezone.now()
    receipt.save(update_fields=["status", "inspected_by", "inspected_at", "inspection_notes", "updated_at"])

    write_audit_log(
        request.user,
        receipt,
        "update",
        changes={"action": "quarantine", "details": f"Quarantined asset receipt {receipt.number}: {reason}"},
        tenant=request.tenant,
    )
    messages.warning(request, f"Asset Receipt {receipt.number} placed in quarantine.")
    return redirect("assets:asset_acquisition_receipt_detail", pk=receipt.pk)
