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

from apps.core.utils import write_audit_log
from apps.quality.forms.DocumentControl.ElectronicSignatures import ElectronicSignatureForm
from apps.quality.models.DocumentControl.ControlledDocuments import ControlledDocument
from apps.quality.models.DocumentControl.DocumentChangeOrders import DocumentChangeOrder
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
def electronic_signature_list(request):
    qs = quality_scope(ElectronicSignatureRecord.objects.all(), request).select_related(
        "document", "change_order", "signer"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(signer_name__icontains=q)
            | Q(number__icontains=q)
            | Q(document__number__icontains=q)
            | Q(document__title__icontains=q)
            | Q(comments__icontains=q)
        )

    meaning_filter = request.GET.get("meaning", "").strip()
    if meaning_filter:
        qs = qs.filter(signature_meaning=meaning_filter)

    stats = {
        "total": qs.count(),
        "approvals": qs.filter(
            signature_meaning__in=["quality_approval", "management_approval", "ccb_approval"]
        ).count(),
        "reviews": qs.filter(signature_meaning__in=["authored", "reviewed"]).count(),
        "acknowledgments": qs.filter(signature_meaning="acknowledgment").count(),
    }

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "signatures": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": paginator.count,
        "q": q,
        "meaning_choices": ElectronicSignatureRecord.MEANING_CHOICES,
        "stats": stats,
    }
    return render(request, "quality/documentcontrol/electronic_signature/list.html", context)


@login_required
def electronic_signature_detail(request, pk):
    sig = quality_object(
        request,
        ElectronicSignatureRecord,
        pk,
        select_related=[
            "document",
            "document__department",
            "document__owner",
            "change_order",
            "signer",
        ],
    )

    is_valid_hash = sig.signature_hash == sig.generate_hash()

    context = {
        "signature": sig,
        "document": sig.document,
        "change_order": sig.change_order,
        "is_valid_hash": is_valid_hash,
    }
    return render(request, "quality/documentcontrol/electronic_signature/detail.html", context)


@login_required
def controlled_document_sign(request, pk):
    doc = quality_object(request, ControlledDocument, pk)
    if doc.is_locked:
        messages.error(request, f"Document {doc.number} Rev {doc.revision} is '{doc.get_lifecycle_state_display()}' and locked against signature execution.")
        return redirect("quality:controlled_document_detail", pk=doc.pk)

    if request.method == "POST":
        form = ElectronicSignatureForm(request.POST, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                legal_name = request.user.get_full_name() or request.user.username
                sig = ElectronicSignatureRecord(
                    tenant=request.tenant,
                    document=doc,
                    signer=request.user,
                    signer_name=legal_name,
                    signer_title=form.cleaned_data.get("signer_title", ""),
                    signature_meaning=form.cleaned_data["signature_meaning"],
                    document_revision=doc.revision,
                    comments=form.cleaned_data.get("comments", ""),
                    ip_address=request.META.get("REMOTE_ADDR"),
                )
                sig.save()
                write_audit_log(request.user, sig, "sign", tenant=request.tenant)

            messages.success(request, f"Electronic signature successfully executed for {doc.number} Rev {doc.revision}.")
            return redirect("quality:controlled_document_detail", pk=doc.pk)
    else:
        form = ElectronicSignatureForm(user=request.user)

    return render(
        request,
        "quality/documentcontrol/electronic_signature/form.html",
        {"form": form, "document": doc, "title": f"Execute Electronic Signature on {doc.number}"},
    )


@login_required
def electronic_signature_verify(request, pk):
    sig = quality_object(
        request,
        ElectronicSignatureRecord,
        pk,
        select_related=["document", "signer"],
    )
    is_valid = sig.signature_hash == sig.generate_hash()
    if is_valid:
        messages.success(request, f"Signature {sig.number} SHA-256 digest verified as authentic and tamper-free.")
    else:
        messages.error(request, f"Warning: Signature {sig.number} digest does not match recorded state!")
    return redirect("quality:electronic_signature_detail", pk=sig.pk)


@login_required
def electronic_signature_export(request):
    qs = quality_scope(ElectronicSignatureRecord.objects.all(), request).select_related("document", "signer")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="electronic_signatures.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow(["Signature Number", "Document", "Revision", "Signer Name", "Title", "Meaning", "Timestamp", "SHA-256 Digest", "IP Address"])
    for sig in qs:
        writer.writerow([
            csv_safe(sig.number),
            csv_safe(sig.document.number if sig.document else ""),
            csv_safe(sig.document_revision),
            csv_safe(sig.signer_name),
            csv_safe(sig.signer_title),
            csv_safe(sig.get_signature_meaning_display()),
            csv_safe(sig.signature_timestamp.strftime("%Y-%m-%d %H:%M:%S") if sig.signature_timestamp else ""),
            csv_safe(sig.signature_hash),
            csv_safe(sig.ip_address),
        ])
    return response
