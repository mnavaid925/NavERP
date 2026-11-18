import csv
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
from apps.quality.forms.IncomingQuality.QualityReturnAuthorizations import (
    QualityReturnAuthorizationForm,
)
from apps.quality.models.IncomingQuality.QualityReturnAuthorizations import (
    QualityReturnAuthorization,
)

PAGE_SIZE = 15

ALLOWED_TRANSITIONS = {
    "draft": {"rma_requested", "cancelled"},
    "rma_requested": {"rma_approved", "cancelled"},
    "rma_approved": {"shipped_to_vendor", "cancelled"},
    "shipped_to_vendor": {"received_by_vendor", "cancelled"},
    "received_by_vendor": {"settled_closed", "cancelled"},
    "settled_closed": set(),
    "cancelled": set(),
}


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def quality_return_authorization_list(request):
    qs = QualityReturnAuthorization.objects.filter(tenant=request.tenant).select_related(
        "supplier", "inspection_lot", "assigned_coordinator"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(vendor_rma_number__icontains=search_query)
            | Q(inspection_lot__number__icontains=search_query)
            | Q(inspection_lot__lot_number__icontains=search_query)
            | Q(supplier__name__icontains=search_query)
            | Q(carrier__icontains=search_query)
            | Q(tracking_number__icontains=search_query)
            | Q(debit_memo_number__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_disposition = request.GET.get("disposition", "").strip()
    if current_disposition:
        qs = qs.filter(disposition_type=current_disposition)

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
        "rmas": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "status_choices": QualityReturnAuthorization.STATUS_CHOICES,
        "disposition_choices": QualityReturnAuthorization.DISPOSITION_TYPE_CHOICES,
        "suppliers": suppliers,
        "current_status": current_status,
        "current_disposition": current_disposition,
        "current_supplier": current_supplier,
        "search_query": search_query,
    }
    return render(request, "quality/incoming_quality/quality_return_authorization/list.html", context)


@login_required
def quality_return_authorization_detail(request, pk):
    rma = get_object_or_404(
        QualityReturnAuthorization.objects.filter(tenant=request.tenant).select_related(
            "supplier", "inspection_lot", "assigned_coordinator", "linked_ncr", "linked_scar"
        ),
        pk=pk,
    )
    context = {
        "rma": rma,
        "obj": rma,
        "status_css": QualityReturnAuthorization.STATUS_CSS,
        "disp_css": QualityReturnAuthorization.DISPOSITION_CSS,
    }
    return render(request, "quality/incoming_quality/quality_return_authorization/detail.html", context)


@login_required
def quality_return_authorization_create(request):
    if request.method == "POST":
        form = QualityReturnAuthorizationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rma = form.save()
            write_audit_log(request.user, rma, "create", tenant=request.tenant)
            messages.success(request, f"Quality Return Authorization {rma.number} created successfully.")
            return redirect("quality:quality_return_authorization_detail", pk=rma.pk)
    else:
        form = QualityReturnAuthorizationForm(tenant=request.tenant)

    return render(
        request,
        "quality/incoming_quality/quality_return_authorization/form.html",
        {"form": form, "title": "Initiate Quality Return Authorization"},
    )


@login_required
def quality_return_authorization_edit(request, pk):
    rma = get_object_or_404(QualityReturnAuthorization.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = QualityReturnAuthorizationForm(request.POST, instance=rma, tenant=request.tenant)
        if form.is_valid():
            rma = form.save()
            write_audit_log(request.user, rma, "update", tenant=request.tenant)
            messages.success(request, f"Quality Return Authorization {rma.number} updated successfully.")
            return redirect("quality:quality_return_authorization_detail", pk=rma.pk)
    else:
        form = QualityReturnAuthorizationForm(instance=rma, tenant=request.tenant)

    return render(
        request,
        "quality/incoming_quality/quality_return_authorization/form.html",
        {"form": form, "rma": rma, "obj": rma, "title": f"Edit {rma.number}"},
    )


@require_POST
@login_required
@tenant_admin_required
def quality_return_authorization_delete(request, pk):
    rma = get_object_or_404(QualityReturnAuthorization.objects.filter(tenant=request.tenant), pk=pk)
    num = rma.number
    write_audit_log(request.user, rma, "delete", tenant=request.tenant)
    rma.delete()
    messages.success(request, f"Quality Return Authorization {num} was deleted.")
    return redirect("quality:quality_return_authorization_list")


@require_POST
@login_required
def quality_return_authorization_advance(request, pk):
    rma = get_object_or_404(QualityReturnAuthorization.objects.filter(tenant=request.tenant), pk=pk)
    next_status = request.POST.get("next_status", "").strip()

    valid_statuses = dict(QualityReturnAuthorization.STATUS_CHOICES)
    allowed = ALLOWED_TRANSITIONS.get(rma.status, set())
    if next_status in valid_statuses and next_status in allowed:
        rma.status = next_status
        if next_status == "shipped_to_vendor" and not rma.shipped_date:
            rma.shipped_date = timezone.now().date()
        elif next_status == "received_by_vendor" and not rma.vendor_receipt_date:
            rma.vendor_receipt_date = timezone.now().date()
        elif next_status == "settled_closed" and not rma.settlement_date:
            rma.settlement_date = timezone.now().date()
            if rma.settled_amount == 0 and rma.estimated_credit_value > 0:
                rma.settled_amount = rma.estimated_credit_value

        rma.save()
        write_audit_log(request.user, rma, "advance", tenant=request.tenant)
        messages.success(request, f"RMA {rma.number} advanced to '{valid_statuses[next_status]}'.")
    else:
        messages.error(request, f"Transition from '{rma.get_status_display()}' to '{valid_statuses.get(next_status, next_status)}' is not allowed.")

    return redirect("quality:quality_return_authorization_detail", pk=rma.pk)


@login_required
def quality_return_authorization_export(request):
    qs = QualityReturnAuthorization.objects.filter(tenant=request.tenant).select_related("supplier", "inspection_lot")

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(vendor_rma_number__icontains=search_query)
            | Q(inspection_lot__lot_number__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="quality_return_authorizations.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "RMA Number",
        "Vendor RMA #",
        "Inspection Lot",
        "Supplier",
        "Return Reason",
        "Disposition Type",
        "Return Quantity",
        "UOM",
        "Estimated Credit",
        "Status",
        "Carrier",
        "Tracking #",
        "Debit Memo #",
        "Settled Amount",
        "Created At",
    ])

    for r in qs:
        writer.writerow([
            _csv_safe(r.number),
            _csv_safe(r.vendor_rma_number),
            _csv_safe(r.inspection_lot.number if r.inspection_lot else ""),
            _csv_safe(r.supplier.name if r.supplier else ""),
            _csv_safe(r.get_return_reason_display()),
            _csv_safe(r.get_disposition_type_display()),
            _csv_safe(r.return_quantity),
            _csv_safe(r.unit_of_measure),
            _csv_safe(r.estimated_credit_value),
            _csv_safe(r.get_status_display()),
            _csv_safe(r.carrier),
            _csv_safe(r.tracking_number),
            _csv_safe(r.debit_memo_number),
            _csv_safe(r.settled_amount),
            _csv_safe(r.created_at.strftime("%Y-%m-%d")),
        ])

    return response
