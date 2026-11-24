from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.documents.forms.VersionControl.Documents import DocumentForm
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.views._common import documents_object, documents_scope


@login_required
def document_list(request):
    qs = documents_scope(
        Document.objects.select_related("owner", "department", "locked_by"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
            | Q(tags__icontains=q)
        )

    doc_type = request.GET.get("document_type", "").strip()
    if doc_type:
        qs = qs.filter(document_type=doc_type)

    classification = request.GET.get("classification", "").strip()
    if classification:
        qs = qs.filter(classification=classification)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    department_id = request.GET.get("department", "").strip()
    if department_id and department_id.isdigit():
        qs = qs.filter(department_id=int(department_id))

    is_locked = request.GET.get("is_locked", "").strip()
    if is_locked == "1":
        qs = qs.filter(is_locked=True)
    elif is_locked == "0":
        qs = qs.filter(is_locked=False)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")
    stats = Document.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        locked=Count("id", filter=Q(is_locked=True)),
    )
    total_documents_count = stats["total"] or 0
    active_locks_count = stats["locked"] or 0

    context = {
        "page_obj": page_obj,
        "documents": page_obj.object_list,
        "document_type_choices": Document.DOCUMENT_TYPE_CHOICES,
        "classification_choices": Document.CLASSIFICATION_CHOICES,
        "status_choices": Document.STATUS_CHOICES,
        "departments": departments,
        "department_choices": departments,
        "total_documents_count": total_documents_count,
        "active_locks_count": active_locks_count,
    }
    return render(request, "documents/version_control/document/list.html", context)


@login_required
def document_detail(request, pk):
    document = documents_object(
        request,
        Document,
        pk,
        select_related=("owner", "department", "locked_by"),
    )

    active_lock = document.locks.filter(status="active").first()
    versions = (
        document.versions.select_related("author", "branch", "restored_from_version")
        .defer("extracted_text")
        .order_by("-created_at", "-major_number", "-minor_number", "-patch_number")
    )
    branches = document.branches.select_related("created_by", "base_version").order_by("-created_at")
    lock_history = document.locks.select_related("locked_by", "unlocked_by").order_by("-checked_out_at")[:10]

    context = {
        "document": document,
        "obj": document,
        "versions": versions,
        "active_lock": active_lock,
        "branches": branches,
        "lock_history": lock_history,
    }
    return render(request, "documents/version_control/document/detail.html", context)


@login_required
def document_create(request):
    if request.method == "POST":
        form = DocumentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            document = form.save(commit=False)
            document.tenant = request.tenant
            if not document.owner_id:
                document.owner = request.user
            document.save()
            write_audit_log(request.user, document, "create", tenant=request.tenant)
            messages.success(request, f"Document '{document.title}' created successfully.")
            return redirect("documents:document_detail", pk=document.pk)
    else:
        form = DocumentForm(tenant=request.tenant, initial={"owner": request.user})

    context = {
        "form": form,
        "document": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "documents/version_control/document/form.html", context)


@login_required
def document_edit(request, pk):
    document = documents_object(request, Document, pk)
    if request.method == "POST":
        form = DocumentForm(request.POST, instance=document, tenant=request.tenant)
        if form.is_valid():
            document = form.save()
            write_audit_log(request.user, document, "update", tenant=request.tenant)
            messages.success(request, f"Document '{document.title}' updated successfully.")
            return redirect("documents:document_detail", pk=document.pk)
    else:
        form = DocumentForm(instance=document, tenant=request.tenant)

    context = {
        "form": form,
        "document": document,
        "obj": document,
        "is_edit": True,
    }
    return render(request, "documents/version_control/document/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def document_delete(request, pk):
    document = documents_object(request, Document, pk)
    if document.legal_holds.filter(is_active=True).exists():
        messages.error(request, "Cannot delete document: An active legal hold is in place.")
        return redirect("documents:document_detail", pk=document.pk)
    if document.record_declarations.filter(is_locked=True).exists():
        messages.error(request, "Cannot delete document: It is an immutable official record.")
        return redirect("documents:document_detail", pk=document.pk)
    title = document.title
    write_audit_log(request.user, document, "delete", tenant=request.tenant)
    document.delete()
    messages.success(request, f"Document '{title}' deleted successfully.")
    return redirect("documents:document_list")
