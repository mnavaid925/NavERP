import csv
import json
import math
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.quality.forms.IncomingQuality.IncomingInspectionLots import (
    IncomingInspectionLotForm,
)
from apps.quality.models.IncomingQuality.IncomingInspectionLots import (
    IncomingInspectionLot,
)

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def incoming_inspection_lot_list(request):
    qs = IncomingInspectionLot.objects.filter(tenant=request.tenant).select_related(
        "supplier", "inspection_plan", "purchase_order", "goods_receipt_note", "inspector", "decided_by"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(lot_number__icontains=search_query)
            | Q(item_code__icontains=search_query)
            | Q(item_name__icontains=search_query)
            | Q(supplier__name__icontains=search_query)
            | Q(purchase_order__number__icontains=search_query)
            | Q(goods_receipt_note__number__icontains=search_query)
        )

    current_stage = request.GET.get("stage", "").strip()
    if current_stage:
        qs = qs.filter(stage=current_stage)

    current_decision = request.GET.get("decision", "").strip()
    if current_decision:
        qs = qs.filter(usage_decision=current_decision)

    current_supplier = request.GET.get("supplier", "").strip()
    if current_supplier.isdigit():
        qs = qs.filter(supplier_id=int(current_supplier))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    suppliers = list(
        Party.objects.filter(
            tenant=request.tenant, roles__role__in=("supplier", "vendor")
        ).only("id", "name").distinct().order_by("name")
    )

    context = {
        "lots": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "stage_choices": IncomingInspectionLot.STAGE_CHOICES,
        "usage_decision_choices": IncomingInspectionLot.USAGE_DECISION_CHOICES,
        "suppliers": suppliers,
        "current_stage": current_stage,
        "current_decision": current_decision,
        "current_supplier": current_supplier,
        "search_query": search_query,
    }
    return render(request, "quality/incoming_quality/incoming_inspection_lot/list.html", context)


@login_required
def incoming_inspection_lot_detail(request, pk):
    lot = get_object_or_404(
        IncomingInspectionLot.objects.filter(tenant=request.tenant).select_related(
            "supplier",
            "inspection_plan",
            "purchase_order",
            "goods_receipt_note",
            "inspector",
            "decided_by",
            "linked_ncr",
            "linked_deviation",
            "linked_containment",
            "linked_scar",
        ),
        pk=pk,
    )
    context = {
        "lot": lot,
        "obj": lot,
        "stage_css": IncomingInspectionLot.STAGE_CSS,
        "decision_css": IncomingInspectionLot.USAGE_DECISION_CSS,
        "usage_decision_choices": IncomingInspectionLot.USAGE_DECISION_CHOICES,
    }
    return render(request, "quality/incoming_quality/incoming_inspection_lot/detail.html", context)


@login_required
def incoming_inspection_lot_create(request):
    if request.method == "POST":
        form = IncomingInspectionLotForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            lot = form.save()
            write_audit_log(request.user, lot, "create", tenant=request.tenant)
            messages.success(request, f"Incoming inspection lot {lot.number} recorded successfully.")
            return redirect("quality:incoming_inspection_lot_detail", pk=lot.pk)
    else:
        form = IncomingInspectionLotForm(tenant=request.tenant)

    return render(
        request,
        "quality/incoming_quality/incoming_inspection_lot/form.html",
        {"form": form, "title": "Record Incoming Inspection Lot"},
    )


@login_required
def incoming_inspection_lot_edit(request, pk):
    lot = get_object_or_404(IncomingInspectionLot.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = IncomingInspectionLotForm(request.POST, instance=lot, tenant=request.tenant)
        if form.is_valid():
            lot = form.save()
            write_audit_log(request.user, lot, "update", tenant=request.tenant)
            messages.success(request, f"Incoming inspection lot {lot.number} updated successfully.")
            return redirect("quality:incoming_inspection_lot_detail", pk=lot.pk)
    else:
        form = IncomingInspectionLotForm(instance=lot, tenant=request.tenant)

    return render(
        request,
        "quality/incoming_quality/incoming_inspection_lot/form.html",
        {"form": form, "lot": lot, "obj": lot, "title": f"Edit {lot.number}"},
    )


@require_POST
@login_required
@tenant_admin_required
def incoming_inspection_lot_delete(request, pk):
    lot = get_object_or_404(IncomingInspectionLot.objects.filter(tenant=request.tenant), pk=pk)
    num = lot.number
    write_audit_log(request.user, lot, "delete", tenant=request.tenant)
    lot.delete()
    messages.success(request, f"Incoming inspection lot {num} was deleted.")
    return redirect("quality:incoming_inspection_lot_list")


@require_POST
@login_required
def incoming_inspection_lot_record_sample(request, pk):
    lot = get_object_or_404(IncomingInspectionLot.objects.filter(tenant=request.tenant), pk=pk)

    if lot.stage in ("completed", "cancelled"):
        messages.error(request, f"Cannot record samples for lot {lot.number}: lot is already {lot.get_stage_display()}.")
        return redirect("quality:incoming_inspection_lot_detail", pk=lot.pk)

    reading_val = request.POST.get("reading_value", "").strip()
    characteristic = request.POST.get("characteristic", "General CTQ").strip()
    is_pass_raw = request.POST.get("is_pass", "true").lower() == "true"

    if reading_val:
        try:
            val_float = float(reading_val)
            if not math.isfinite(val_float):
                raise ValueError("Non-finite measurement value.")
            measurements = list(lot.measurements_data or [])
            sample_no = len(measurements) + 1
            measurements.append({
                "sample_no": sample_no,
                "characteristic": characteristic,
                "value": val_float,
                "is_pass": is_pass_raw,
            })
            lot.measurements_data = measurements
            lot.inspected_quantity = len(measurements)
            if lot.stage == "pending_receipt":
                lot.stage = "in_inspection"
            if not lot.inspection_date:
                lot.inspection_date = timezone.now().date()
            if not lot.inspector:
                lot.inspector = request.user

            lot.recalculate_spc(characteristic_name=characteristic)
            lot.save()

            write_audit_log(request.user, lot, "sample", tenant=request.tenant)
            messages.success(request, f"Sample #{sample_no} recorded for {characteristic}: {val_float}")
        except ValueError:
            messages.error(request, "Invalid numeric value for sample measurement.")

    return redirect("quality:incoming_inspection_lot_detail", pk=lot.pk)


@require_POST
@login_required
def incoming_inspection_lot_make_decision(request, pk):
    lot = get_object_or_404(IncomingInspectionLot.objects.filter(tenant=request.tenant), pk=pk)

    if lot.stage in ("completed", "cancelled") or lot.usage_decision != "pending":
        messages.error(request, f"Usage decision for lot {lot.number} has already been finalized.")
        return redirect("quality:incoming_inspection_lot_detail", pk=lot.pk)

    decision = request.POST.get("usage_decision", "").strip()
    decision_notes = request.POST.get("decision_notes", "").strip()

    valid_decisions = dict(IncomingInspectionLot.USAGE_DECISION_CHOICES)
    if decision in valid_decisions and decision != "pending":
        lot.usage_decision = decision
        lot.usage_decision_notes = decision_notes
        lot.decided_by = request.user
        lot.decided_at = timezone.now()

        if decision in ("accepted", "skip_lot_passed"):
            lot.stage = "completed"
            if lot.accepted_quantity == 0:
                lot.accepted_quantity = lot.lot_quantity
        elif decision == "accepted_with_deviation":
            lot.stage = "completed"
        elif decision == "quarantined":
            lot.stage = "under_mrb"
            if lot.quarantine_quantity == 0:
                lot.quarantine_quantity = lot.lot_quantity
        elif decision == "rejected":
            lot.stage = "completed"
            if lot.rejected_quantity == 0:
                lot.rejected_quantity = lot.lot_quantity

        lot.save()
        write_audit_log(request.user, lot, "decide", tenant=request.tenant)
        messages.success(request, f"Usage decision '{valid_decisions[decision]}' applied to {lot.number}.")
    else:
        messages.error(request, "Invalid usage decision choice.")

    return redirect("quality:incoming_inspection_lot_detail", pk=lot.pk)


@login_required
def incoming_inspection_lot_export(request):
    qs = IncomingInspectionLot.objects.filter(tenant=request.tenant).select_related("supplier", "inspection_plan")

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(lot_number__icontains=search_query)
            | Q(item_code__icontains=search_query)
            | Q(item_name__icontains=search_query)
        )

    current_stage = request.GET.get("stage", "").strip()
    if current_stage:
        qs = qs.filter(stage=current_stage)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="incoming_inspection_lots.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Lot Number",
        "Vendor Lot #",
        "Item Code",
        "Item Name",
        "Supplier",
        "Lot Quantity",
        "Sample Size",
        "Inspected Qty",
        "Critical Defects",
        "Major Defects",
        "Minor Defects",
        "Stage",
        "Usage Decision",
        "Mean",
        "Std Dev",
        "Cpk",
        "Receipt Date",
        "Created At",
    ])

    for l in qs.iterator(chunk_size=1000):
        writer.writerow([
            _csv_safe(l.number),
            _csv_safe(l.lot_number),
            _csv_safe(l.item_code),
            _csv_safe(l.item_name),
            _csv_safe(l.supplier.name if l.supplier else ""),
            _csv_safe(l.lot_quantity),
            _csv_safe(l.sample_size),
            _csv_safe(l.inspected_quantity),
            _csv_safe(l.critical_defects),
            _csv_safe(l.major_defects),
            _csv_safe(l.minor_defects),
            _csv_safe(l.get_stage_display()),
            _csv_safe(l.get_usage_decision_display()),
            _csv_safe(l.spc_mean),
            _csv_safe(l.spc_std_dev),
            _csv_safe(l.spc_cpk),
            _csv_safe(l.receipt_date.strftime("%Y-%m-%d") if l.receipt_date else ""),
            _csv_safe(l.created_at.strftime("%Y-%m-%d")),
        ])

    return response
