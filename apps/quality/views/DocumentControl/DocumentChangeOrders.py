import csv
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.DocumentControl.DocumentChangeOrders import DocumentChangeOrderForm
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


@login_required
def document_change_order_list(request):
    qs = quality_scope(DocumentChangeOrder.objects.all(), request).select_related("document", "requested_by")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(document__number__icontains=q)
            | Q(document__title__icontains=q)
            | Q(reason_for_change__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    priority_filter = request.GET.get("priority", "").strip()
    if priority_filter:
        qs = qs.filter(priority=priority_filter)

    type_filter = request.GET.get("change_type", "").strip()
    if type_filter:
        qs = qs.filter(change_type=type_filter)

    stats = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=~Q(status__in=["implemented", "cancelled", "rejected"])),
        ccb_pending=Count("id", filter=Q(status="ccb_review")),
        approved=Count("id", filter=Q(status="approved")),
        implemented=Count("id", filter=Q(status="implemented")),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "change_orders": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "q": q,
        "status_choices": DocumentChangeOrder.STATUS_CHOICES,
        "priority_choices": DocumentChangeOrder.PRIORITY_CHOICES,
        "change_type_choices": DocumentChangeOrder.CHANGE_TYPE_CHOICES,
        "stats": stats,
    }
    return render(request, "quality/documentcontrol/document_change_order/list.html", context)


@login_required
def document_change_order_create(request):
    if request.method == "POST":
        form = DocumentChangeOrderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                dco = form.save(commit=False)
                dco.tenant = request.tenant
                dco.requested_by = request.user
                dco.save()
                write_audit_log(request.user, dco, "create", tenant=request.tenant)
            messages.success(request, f"Document Change Order {dco.number} created.")
            return redirect("quality:document_change_order_detail", pk=dco.pk)
    else:
        doc_id = request.GET.get("document", "")
        initial = {}
        if doc_id and doc_id.isdigit():
            initial["document"] = int(doc_id)
        form = DocumentChangeOrderForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "quality/documentcontrol/document_change_order/form.html",
        {"form": form, "title": "Create Document Change Order", "action": "Create DCO"},
    )


@login_required
def document_change_order_detail(request, pk):
    dco = quality_object(
        request,
        DocumentChangeOrder,
        pk,
        select_related=[
            "document",
            "document__department",
            "document__owner",
            "requested_by",
            "ccb_decision_by",
        ],
    )

    signatures = dco.signatures.all().select_related("signer")

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    can_edit = dco.status in {"draft", "submitted"}
    can_submit = dco.status == "draft"
    can_ccb_approve = is_admin and dco.status in {"submitted", "in_assessment", "ccb_review"}

    context = {
        "change_order": dco,
        "document": dco.document,
        "signatures": signatures,
        "is_admin": is_admin,
        "can_edit": can_edit,
        "can_submit": can_submit,
        "can_ccb_approve": can_ccb_approve,
    }
    return render(request, "quality/documentcontrol/document_change_order/detail.html", context)


@login_required
def document_change_order_edit(request, pk):
    dco = quality_object(request, DocumentChangeOrder, pk)
    if dco.status in {"approved", "implemented", "rejected", "cancelled"}:
        messages.error(request, f"DCO {dco.number} is '{dco.get_status_display()}' and cannot be edited.")
        return redirect("quality:document_change_order_detail", pk=dco.pk)

    if request.method == "POST":
        form = DocumentChangeOrderForm(request.POST, instance=dco, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                dco = form.save()
                write_audit_log(request.user, dco, "update", tenant=request.tenant)
            messages.success(request, f"Change Order {dco.number} updated.")
            return redirect("quality:document_change_order_detail", pk=dco.pk)
    else:
        form = DocumentChangeOrderForm(instance=dco, tenant=request.tenant)

    return render(
        request,
        "quality/documentcontrol/document_change_order/form.html",
        {"form": form, "change_order": dco, "title": f"Edit {dco.number}", "action": "Save Changes"},
    )


@login_required
@require_POST
def document_change_order_delete(request, pk):
    dco = quality_object(request, DocumentChangeOrder, pk)
    if dco.status != "draft":
        messages.error(request, "Only draft change orders can be deleted.")
        return redirect("quality:document_change_order_detail", pk=dco.pk)

    with transaction.atomic():
        write_audit_log(request.user, dco, "delete", tenant=request.tenant)
        dco.delete()
    messages.success(request, f"DCO {dco.number} deleted.")
    return redirect("quality:document_change_order_list")


@login_required
@require_POST
def document_change_order_submit(request, pk):
    dco = quality_object(request, DocumentChangeOrder, pk)
    if dco.status != "draft":
        messages.error(request, "Only draft change orders can be submitted.")
        return redirect("quality:document_change_order_detail", pk=dco.pk)

    with transaction.atomic():
        dco.status = "ccb_review"
        dco.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, dco, "submit", tenant=request.tenant)

    messages.success(request, f"DCO {dco.number} submitted to Change Control Board.")
    return redirect("quality:document_change_order_detail", pk=dco.pk)


@login_required
@require_POST
@tenant_admin_required
def document_change_order_ccb_decision(request, pk):
    dco = quality_object(request, DocumentChangeOrder, pk)
    if dco.status not in {"submitted", "in_assessment", "ccb_review"}:
        messages.error(request, f"Cannot record CCB determination on change order in '{dco.get_status_display()}' status.")
        return redirect("quality:document_change_order_detail", pk=dco.pk)

    decision = request.POST.get("decision", "").strip()
    notes = request.POST.get("closure_notes", "").strip()

    if decision not in {"approved", "rejected", "waived"}:
        messages.error(request, "Invalid CCB decision provided.")
        return redirect("quality:document_change_order_detail", pk=dco.pk)

    today = timezone.now().date()
    with transaction.atomic():
        dco.ccb_decision = decision
        dco.ccb_decision_date = today
        dco.ccb_decision_by = request.user
        dco.closure_notes = notes

        if decision == "approved":
            dco.status = "approved"
        elif decision == "rejected":
            dco.status = "rejected"
            dco.closed_at = timezone.now()
        else:
            dco.status = "approved"

        dco.save()
        write_audit_log(request.user, dco, "ccb_dec", tenant=request.tenant)

    messages.success(request, f"CCB decision '{decision}' recorded for {dco.number}.")
    return redirect("quality:document_change_order_detail", pk=dco.pk)


@login_required
def document_change_order_export(request):
    qs = quality_scope(DocumentChangeOrder.objects.all(), request).select_related("document", "requested_by")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="document_change_orders.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow(["Number", "Title", "Type", "Priority", "Document", "Target Rev", "Status", "CCB Decision", "Requested By", "Target Effective Date"])
    for dco in qs:
        writer.writerow([
            csv_safe(dco.number),
            csv_safe(dco.title),
            csv_safe(dco.get_change_type_display()),
            csv_safe(dco.get_priority_display()),
            csv_safe(dco.document.number if dco.document else ""),
            csv_safe(dco.target_revision),
            csv_safe(dco.get_status_display()),
            csv_safe(dco.get_ccb_decision_display()),
            csv_safe(dco.requested_by.username if dco.requested_by else ""),
            csv_safe(dco.target_effective_date),
        ])
    return response
