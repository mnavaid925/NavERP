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
from apps.quality.forms.DocumentControl.DocumentAcknowledgments import DocumentAcknowledgmentForm
from apps.quality.forms.DocumentControl.ElectronicSignatures import ElectronicSignatureForm
from apps.quality.models.DocumentControl.DocumentAcknowledgments import DocumentAcknowledgment
from apps.quality.models.DocumentControl.ElectronicSignatures import ElectronicSignatureRecord
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


@login_required
def document_acknowledgment_list(request):
    qs = quality_scope(DocumentAcknowledgment.objects.all(), request).select_related(
        "document", "user", "employee"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(number__icontains=q)
            | Q(document__number__icontains=q)
            | Q(document__title__icontains=q)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    today = timezone.now().date()
    stats = qs.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status="pending")),
        acknowledged=Count("id", filter=Q(status="acknowledged")),
        overdue=Count("id", filter=Q(status="pending", due_date__lt=today)),
    )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "acknowledgments": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "q": q,
        "status_choices": DocumentAcknowledgment.STATUS_CHOICES,
        "stats": stats,
    }
    return render(request, "quality/documentcontrol/document_acknowledgment/list.html", context)


@login_required
def document_acknowledgment_create(request):
    if request.method == "POST":
        form = DocumentAcknowledgmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                ack = form.save(commit=False)
                ack.tenant = request.tenant
                ack.save()
                write_audit_log(request.user, ack, "create", tenant=request.tenant)
            messages.success(request, f"Acknowledgment requirement {ack.number} issued to {ack.user.username}.")
            return redirect("quality:document_acknowledgment_detail", pk=ack.pk)
    else:
        doc_id = request.GET.get("document", "")
        initial = {}
        if doc_id and doc_id.isdigit():
            initial["document"] = int(doc_id)
        form = DocumentAcknowledgmentForm(tenant=request.tenant, initial=initial)

    return render(
        request,
        "quality/documentcontrol/document_acknowledgment/form.html",
        {"form": form, "title": "Assign Document Acknowledgment", "action": "Assign Acknowledgment"},
    )


@login_required
def document_acknowledgment_detail(request, pk):
    ack = quality_object(
        request,
        DocumentAcknowledgment,
        pk,
        select_related=[
            "document",
            "document__department",
            "document__owner",
            "user",
            "employee",
            "signature_record",
        ],
    )

    can_sign = (
        ack.status == "pending"
        and (request.user == ack.user or request.user.is_superuser or getattr(request.user, "is_tenant_admin", False))
    )

    context = {
        "acknowledgment": ack,
        "document": ack.document,
        "signature": ack.signature_record,
        "can_sign": can_sign,
    }
    return render(request, "quality/documentcontrol/document_acknowledgment/detail.html", context)


@login_required
def document_acknowledgment_edit(request, pk):
    ack = quality_object(request, DocumentAcknowledgment, pk)
    if ack.status == "acknowledged":
        messages.error(request, f"Acknowledgment {ack.number} has already been signed and is locked.")
        return redirect("quality:document_acknowledgment_detail", pk=ack.pk)

    if request.method == "POST":
        form = DocumentAcknowledgmentForm(request.POST, instance=ack, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                ack = form.save()
                write_audit_log(request.user, ack, "update", tenant=request.tenant)
            messages.success(request, f"Acknowledgment {ack.number} updated.")
            return redirect("quality:document_acknowledgment_detail", pk=ack.pk)
    else:
        form = DocumentAcknowledgmentForm(instance=ack, tenant=request.tenant)

    return render(
        request,
        "quality/documentcontrol/document_acknowledgment/form.html",
        {"form": form, "acknowledgment": ack, "title": f"Edit {ack.number}", "action": "Save Changes"},
    )


@login_required
@require_POST
@tenant_admin_required
def document_acknowledgment_delete(request, pk):
    ack = quality_object(request, DocumentAcknowledgment, pk)
    if ack.status == "acknowledged":
        messages.error(request, "Cannot delete an executed quality acknowledgment record.")
        return redirect("quality:document_acknowledgment_detail", pk=ack.pk)

    with transaction.atomic():
        write_audit_log(request.user, ack, "delete", tenant=request.tenant)
        ack.delete()
    messages.success(request, f"Acknowledgment {ack.number} deleted.")
    return redirect("quality:document_acknowledgment_list")


@login_required
def document_acknowledgment_sign(request, pk):
    ack = quality_object(request, DocumentAcknowledgment, pk, select_related=["document", "user"])
    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    if request.user != ack.user and not is_admin:
        messages.error(request, "You are not authorized to sign this acknowledgment on behalf of another user.")
        return redirect("quality:document_acknowledgment_detail", pk=ack.pk)

    if ack.status == "acknowledged":
        messages.info(request, "This document acknowledgment has already been signed.")
        return redirect("quality:document_acknowledgment_detail", pk=ack.pk)

    if request.method == "POST":
        form = ElectronicSignatureForm(request.POST, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                legal_name = request.user.get_full_name() or request.user.username
                sig = ElectronicSignatureRecord(
                    tenant=request.tenant,
                    document=ack.document,
                    signer=request.user,
                    signer_name=legal_name,
                    signer_title=form.cleaned_data.get("signer_title", ""),
                    signature_meaning="acknowledgment",
                    document_revision=ack.document_revision,
                    comments=form.cleaned_data.get("comments", "Read, understood, and adherence agreement confirmed."),
                    ip_address=request.META.get("REMOTE_ADDR"),
                )
                sig.save()

                ack.status = "acknowledged"
                ack.acknowledged_at = timezone.now()
                ack.signature_record = sig
                ack.save(update_fields=["status", "acknowledged_at", "signature_record", "updated_at"])

                write_audit_log(request.user, ack, "ack", tenant=request.tenant)
                write_audit_log(request.user, sig, "sign", tenant=request.tenant)

            messages.success(request, f"Successfully executed read-and-acknowledge sign-off for {ack.document.number}.")
            return redirect("quality:document_acknowledgment_detail", pk=ack.pk)
    else:
        form = ElectronicSignatureForm(
            user=request.user,
            initial={"signature_meaning": "acknowledgment", "comments": "I have read, understood, and agree to adhere to this procedure."},
        )

    return render(
        request,
        "quality/documentcontrol/electronic_signature/form.html",
        {"form": form, "document": ack.document, "title": f"Acknowledge & Sign {ack.document.number} Rev {ack.document_revision}"},
    )


@login_required
def document_acknowledgment_export(request):
    qs = quality_scope(DocumentAcknowledgment.objects.all(), request).select_related("document", "user")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="document_acknowledgments.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow(["Number", "Document", "Revision", "User", "Due Date", "Status", "Acknowledged At"])
    for a in qs:
        writer.writerow([
            csv_safe(a.number),
            csv_safe(a.document.number if a.document else ""),
            csv_safe(a.document_revision),
            csv_safe(a.user.username if a.user else ""),
            csv_safe(a.due_date),
            csv_safe(a.get_status_display()),
            csv_safe(a.acknowledged_at.strftime("%Y-%m-%d %H:%M:%S") if a.acknowledged_at else ""),
        ])
    return response
