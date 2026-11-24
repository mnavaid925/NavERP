from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.RecordsManagement.DestructionCertificates import DestructionCertificateForm
from apps.documents.models.RecordsManagement.DestructionCertificates import DestructionCertificate
from apps.documents.models.RecordsManagement.RecordDeclarations import RecordDeclaration
from apps.documents.views._common import documents_object, documents_scope


@login_required
def destruction_certificate_list(request):
    qs = documents_scope(DestructionCertificate.objects.all(), request).select_related(
        "record_declaration", "authorized_by", "executed_by"
    )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_type = request.GET.get("disposition_type", "").strip()
    if current_type:
        qs = qs.filter(disposition_type=current_type)

    current_method = request.GET.get("destruction_method", "").strip()
    if current_method:
        qs = qs.filter(destruction_method=current_method)

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(document_title_snapshot__icontains=query)
            | Q(document_number_snapshot__icontains=query)
            | Q(schedule_name_snapshot__icontains=query)
            | Q(content_verification_hash__icontains=query)
            | Q(certificate_notes__icontains=query)
        )

    qs = qs.order_by("-created_at")
    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "certificates": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "status_choices": DestructionCertificate.CERTIFICATE_STATUS_CHOICES,
        "type_choices": DestructionCertificate.DISPOSITION_TYPE_CHOICES,
        "method_choices": DestructionCertificate.DESTRUCTION_METHOD_CHOICES,
        "current_status": current_status,
        "current_type": current_type,
        "query": query,
    }
    return render(request, "documents/records_management/destruction_certificate/list.html", context)


@login_required
def destruction_certificate_detail(request, pk):
    certificate = documents_object(
        request,
        DestructionCertificate,
        pk,
        select_related=("record_declaration", "authorized_by", "executed_by"),
    )

    context = {
        "certificate": certificate,
    }
    return render(request, "documents/records_management/destruction_certificate/detail.html", context)


@login_required
def destruction_certificate_create(request):
    initial = {}
    declaration_id = request.GET.get("declaration", "").strip()
    if declaration_id.isdigit():
        declaration = RecordDeclaration.objects.filter(tenant=request.tenant, pk=int(declaration_id)).first()
        if declaration:
            initial["record_declaration"] = declaration

    if request.method == "POST":
        form = DestructionCertificateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            certificate = form.save(commit=False)
            certificate.tenant = request.tenant
            certificate.save()
            write_audit_log(request.user, certificate, "create", tenant=request.tenant)
            messages.success(request, f"Destruction certificate {certificate.number} drafted for '{certificate.document_title_snapshot}'.")
            return redirect("documents:destruction_certificate_detail", pk=certificate.pk)
    else:
        form = DestructionCertificateForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
    }
    return render(request, "documents/records_management/destruction_certificate/form.html", context)


@login_required
@require_POST
def destruction_certificate_authorize(request, pk):
    certificate = documents_object(request, DestructionCertificate, pk)
    try:
        certificate.authorize(request.user)
        write_audit_log(request.user, certificate, "approve", tenant=request.tenant)
        messages.success(request, f"Disposition for certificate {certificate.number} authorized by {request.user.username}.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("documents:destruction_certificate_detail", pk=certificate.pk)


@login_required
@require_POST
def destruction_certificate_execute(request, pk):
    certificate = documents_object(request, DestructionCertificate, pk)
    try:
        certificate.execute_destruction(request.user)
        write_audit_log(request.user, certificate, "execute", tenant=request.tenant)
        messages.success(
            request,
            f"Destruction certificate {certificate.number} successfully executed. Record status updated to disposed.",
        )
    except ValueError as e:
        messages.error(request, str(e))
    return redirect("documents:destruction_certificate_detail", pk=certificate.pk)
