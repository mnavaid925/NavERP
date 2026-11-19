import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.FinalQuality.FinalInspectionLots import FinalInspectionLotForm
from apps.quality.models.FinalQuality.FinalInspectionLots import FinalInspectionLot

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.startswith(("=", "+", "-", "@", "\t", "\r")) or s.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


@login_required
def final_inspection_lot_list(request):
    qs = FinalInspectionLot.objects.filter(tenant=request.tenant)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(item_code__icontains=q)
            | Q(item_name__icontains=q)
            | Q(lot_number__icontains=q)
            | Q(sales_order_number__icontains=q)
            | Q(work_order_number__icontains=q)
        )

    stage = request.GET.get("stage", "").strip()
    if stage:
        qs = qs.filter(inspection_stage=stage)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    decision = request.GET.get("decision", "").strip()
    if decision:
        qs = qs.filter(usage_decision=decision)

    on_hold = request.GET.get("on_hold", "").strip()
    if on_hold == "1":
        qs = qs.filter(is_on_hold=True)
    elif on_hold == "0":
        qs = qs.filter(is_on_hold=False)

    stats = FinalInspectionLot.objects.filter(tenant=request.tenant).aggregate(
        total_count=Count("id"),
        accepted_count=Count("id", filter=Q(usage_decision__in=["accepted", "accepted_with_concession"])),
        hold_count=Count("id", filter=Q(is_on_hold=True)),
        rejected_count=Count("id", filter=Q(usage_decision="rejected_mrb")),
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "inspection_lots": page_obj,
        "paginator": paginator,
        "q": q,
        "stage": stage,
        "status": status,
        "decision": decision,
        "on_hold": on_hold,
        "stage_choices": FinalInspectionLot.INSPECTION_STAGE_CHOICES,
        "status_choices": FinalInspectionLot.STATUS_CHOICES,
        "decision_choices": FinalInspectionLot.USAGE_DECISION_CHOICES,
        "total_count": stats["total_count"] or 0,
        "accepted_count": stats["accepted_count"] or 0,
        "hold_count": stats["hold_count"] or 0,
        "rejected_count": stats["rejected_count"] or 0,
        "STAGE_CSS": FinalInspectionLot.STAGE_CSS,
        "STATUS_CSS": FinalInspectionLot.STATUS_CSS,
        "DECISION_CSS": FinalInspectionLot.USAGE_DECISION_CSS,
    }
    return render(request, "quality/finalquality/final_inspection_lot/list.html", context)


@login_required
def final_inspection_lot_detail(request, pk):
    lot = get_object_or_404(
        FinalInspectionLot.objects.filter(tenant=request.tenant).select_related(
            "customer", "sales_order", "work_order", "inspection_plan",
            "non_conformance", "process_deviation", "inspector", "decision_by"
        ),
        pk=pk,
    )
    context = {
        "lot": lot,
        "STAGE_CSS": FinalInspectionLot.STAGE_CSS,
        "STATUS_CSS": FinalInspectionLot.STATUS_CSS,
        "DECISION_CSS": FinalInspectionLot.USAGE_DECISION_CSS,
    }
    return render(request, "quality/finalquality/final_inspection_lot/detail.html", context)


@login_required
def final_inspection_lot_create(request):
    if request.method == "POST":
        form = FinalInspectionLotForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            lot = form.save(commit=False)
            lot.tenant = request.tenant
            lot.save()
            form.save_m2m()
            write_audit_log(request.user, lot, "create", tenant=request.tenant)
            messages.success(request, f"Final inspection lot {lot.number} created successfully.")
            return redirect("quality:final_inspection_lot_detail", pk=lot.pk)
    else:
        form = FinalInspectionLotForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "lot": None,
        "title": "New Final Inspection Lot",
    }
    return render(request, "quality/finalquality/final_inspection_lot/form.html", context)


@login_required
def final_inspection_lot_edit(request, pk):
    lot = get_object_or_404(FinalInspectionLot, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = FinalInspectionLotForm(request.POST, instance=lot, tenant=request.tenant)
        if form.is_valid():
            lot = form.save()
            write_audit_log(request.user, lot, "update", tenant=request.tenant)
            messages.success(request, f"Final inspection lot {lot.number} updated successfully.")
            return redirect("quality:final_inspection_lot_detail", pk=lot.pk)
    else:
        form = FinalInspectionLotForm(instance=lot, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "lot": lot,
        "title": f"Edit Final Inspection Lot: {lot.number}",
    }
    return render(request, "quality/finalquality/final_inspection_lot/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def final_inspection_lot_delete(request, pk):
    lot = get_object_or_404(FinalInspectionLot, pk=pk, tenant=request.tenant)
    number = lot.number
    write_audit_log(request.user, lot, "delete", tenant=request.tenant)
    lot.delete()
    messages.success(request, f"Inspection lot {number} deleted successfully.")
    return redirect("quality:final_inspection_lot_list")


@login_required
@require_POST
@tenant_admin_required
def final_inspection_lot_toggle_hold(request, pk):
    lot = get_object_or_404(FinalInspectionLot, pk=pk, tenant=request.tenant)
    reason = request.POST.get("hold_reason", "").strip()
    if lot.is_on_hold:
        lot.is_on_hold = False
        action = "release"
        msg = f"Inspection lot {lot.number} removed from hold."
    else:
        if not reason:
            messages.error(request, "A non-empty hold reason is mandatory when placing an inspection lot on hold.")
            return redirect("quality:final_inspection_lot_detail", pk=lot.pk)
        lot.is_on_hold = True
        lot.hold_reason = reason
        action = "hold"
        msg = f"Inspection lot {lot.number} placed on hold."
    lot.save()
    write_audit_log(request.user, lot, action, tenant=request.tenant)
    messages.success(request, msg)
    return redirect("quality:final_inspection_lot_detail", pk=lot.pk)


@login_required
def final_inspection_lot_export(request):
    write_audit_log(request.user, None, "export", changes={"model": "FinalInspectionLot"}, tenant=request.tenant)
    qs = FinalInspectionLot.objects.filter(tenant=request.tenant).order_by("-created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="final_inspection_lots.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Lot Number",
        "Title",
        "Stage",
        "Status",
        "Usage Decision",
        "Item Code",
        "Item Name",
        "Batch/Lot",
        "Lot Quantity",
        "Sample Size",
        "Units Passed",
        "Units Rejected",
        "On Hold",
        "Hold Reason",
        "Inspection Date",
    ])
    for item in qs:
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.title),
            _csv_safe(item.get_inspection_stage_display()),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.get_usage_decision_display()),
            _csv_safe(item.item_code),
            _csv_safe(item.item_name),
            _csv_safe(item.lot_number),
            _csv_safe(item.lot_quantity),
            _csv_safe(item.sample_size_inspected),
            _csv_safe(item.units_passed),
            _csv_safe(item.units_rejected),
            "Yes" if item.is_on_hold else "No",
            _csv_safe(item.hold_reason),
            _csv_safe(item.inspection_date),
        ])

    return response
