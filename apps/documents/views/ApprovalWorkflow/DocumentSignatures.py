import hashlib
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.ApprovalWorkflow.DocumentSignatures import (
    DocumentSignatureForm,
    SignatureVerificationForm,
)
from apps.documents.models import DocumentSignature
from apps.documents.views._common import documents_object, documents_scope


@login_required
def signature_list(request):
    qs = documents_scope(
        DocumentSignature.objects.select_related("document", "version", "approval_request", "signer"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(signer_name__icontains=q)
            | Q(number__icontains=q)
            | Q(signature_token__icontains=q)
            | Q(document__title__icontains=q)
        )

    sig_type = request.GET.get("signature_type", "").strip()
    if sig_type:
        qs = qs.filter(signature_type=sig_type)

    meaning = request.GET.get("signature_meaning", "").strip()
    if meaning:
        qs = qs.filter(signature_meaning=meaning)

    valid_filter = request.GET.get("is_valid", "").strip()
    if valid_filter == "1":
        qs = qs.filter(is_valid=True)
    elif valid_filter == "0":
        qs = qs.filter(is_valid=False)

    total_count = qs.count()
    valid_count = qs.filter(is_valid=True).count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    signatures = paginator.get_page(page_number)

    context = {
        "signatures": signatures,
        "signature_type_choices": DocumentSignature.SIGNATURE_TYPE_CHOICES,
        "signature_meaning_choices": DocumentSignature.SIGNATURE_MEANING_CHOICES,
        "signature_type_css": DocumentSignature.SIGNATURE_TYPE_CSS,
        "signature_meaning_css": DocumentSignature.SIGNATURE_MEANING_CSS,
        "total_count": total_count,
        "valid_count": valid_count,
        "verify_form": SignatureVerificationForm(),
    }
    return render(request, "documents/approval_workflow/document_signature/list.html", context)


@login_required
def signature_detail(request, pk):
    signature = documents_object(
        request,
        DocumentSignature,
        pk,
        select_related=("document", "version", "approval_request", "signer"),
    )

    context = {
        "signature": signature,
        "signature_type_css": signature.signature_type_css_class,
        "signature_meaning_css": signature.signature_meaning_css_class,
    }
    return render(request, "documents/approval_workflow/document_signature/detail.html", context)


@login_required
def signature_create(request):
    if request.method == "POST":
        form = DocumentSignatureForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            sig = form.save(commit=False)
            sig.tenant = request.tenant
            sig.signer = request.user

            # Compute or bind document checksum
            if sig.version and sig.version.file_hash:
                sig.document_checksum = sig.version.file_hash
            else:
                raw_token = f"{sig.document.pk}:{sig.document.title}:{request.user.pk}"
                sig.document_checksum = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

            sig.ip_address = request.META.get("REMOTE_ADDR")
            sig.user_agent = request.META.get("HTTP_USER_AGENT", "")[:255]
            sig.is_valid = True
            sig.save()

            write_audit_log(request.user, sig, "sign", tenant=request.tenant)
            messages.success(request, f"Electronic signature {sig.number} successfully recorded and cryptographically bound.")
            return redirect("documents:signature_detail", pk=sig.pk)
    else:
        initial = {
            "signer_name": request.user.get_full_name() or request.user.username,
            "signer_email": request.user.email,
        }
        doc_id = request.GET.get("document")
        if doc_id and doc_id.isdigit():
            initial["document"] = doc_id
        req_id = request.GET.get("approval_request")
        if req_id and req_id.isdigit():
            initial["approval_request"] = req_id
        form = DocumentSignatureForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "signature": None,
        "is_edit": False,
    }
    return render(request, "documents/approval_workflow/document_signature/form.html", context)


@login_required
def signature_edit(request, pk):
    signature = documents_object(request, DocumentSignature, pk)
    if request.method == "POST":
        form = DocumentSignatureForm(request.POST, instance=signature, tenant=request.tenant)
        if form.is_valid():
            signature = form.save()
            write_audit_log(request.user, signature, "update", tenant=request.tenant)
            messages.success(request, f"Signature {signature.number} record updated.")
            return redirect("documents:signature_detail", pk=signature.pk)
    else:
        form = DocumentSignatureForm(instance=signature, tenant=request.tenant)

    context = {
        "form": form,
        "signature": signature,
        "is_edit": True,
    }
    return render(request, "documents/approval_workflow/document_signature/form.html", context)


@login_required
@require_POST
def signature_delete(request, pk):
    signature = documents_object(request, DocumentSignature, pk)
    number = signature.number
    write_audit_log(request.user, signature, "delete", tenant=request.tenant)
    signature.delete()
    messages.success(request, f"Signature record {number} deleted.")
    return redirect("documents:signature_list")


@login_required
def signature_manifest(request, pk):
    signature = documents_object(
        request,
        DocumentSignature,
        pk,
        select_related=("document", "version", "approval_request", "signer"),
    )

    context = {
        "signature": signature,
        "document": signature.document,
        "version": signature.version,
    }
    return render(request, "documents/approval_workflow/document_signature/manifest.html", context)


@login_required
def signature_verify(request, token=None):
    search_token = token or request.GET.get("token", "").strip()
    signature = None
    is_valid = False

    if search_token:
        try:
            signature = DocumentSignature.objects.select_related(
                "document", "version", "signer"
            ).get(tenant=request.tenant, signature_token=search_token)
            is_valid = signature.is_valid
        except DocumentSignature.DoesNotExist:
            signature = None
            is_valid = False

    context = {
        "signature": signature,
        "token": search_token,
        "is_valid": is_valid,
    }
    return render(request, "documents/approval_workflow/document_signature/verify.html", context)
