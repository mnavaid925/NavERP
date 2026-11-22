from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.VersionControl.DocumentBranches import (
    BranchMergeForm,
    DocumentBranchForm,
)
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.models.VersionControl.DocumentBranches import DocumentBranch
from apps.documents.models.VersionControl.DocumentVersions import DocumentVersion
from apps.documents.views._common import documents_object, documents_scope


@login_required
def document_branch_list(request):
    qs = documents_scope(
        DocumentBranch.objects.select_related("document", "base_version", "created_by", "merged_by").defer(
            "base_version__extracted_text"
        ),
        request,
    )

    doc_id = request.GET.get("document", "").strip()
    if doc_id and doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    branch_type = request.GET.get("branch_type", "").strip()
    if branch_type:
        qs = qs.filter(branch_type=branch_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(document__title__icontains=q)
            | Q(number__icontains=q)
        )

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    documents = Document.objects.filter(tenant=request.tenant).order_by("title")

    context = {
        "page_obj": page_obj,
        "branches": page_obj.object_list,
        "status_choices": DocumentBranch.STATUS_CHOICES,
        "branch_type_choices": DocumentBranch.BRANCH_TYPE_CHOICES,
        "documents": documents,
    }
    return render(request, "documents/version_control/document_branch/list.html", context)


@login_required
def document_branch_detail(request, pk):
    branch = documents_object(
        request,
        DocumentBranch,
        pk,
        select_related=("document", "base_version", "created_by", "merged_by", "merged_into_version"),
    )

    branch_versions = branch.versions.select_related("author").order_by("-created_at")

    context = {
        "branch": branch,
        "obj": branch,
        "document": branch.document,
        "branch_versions": branch_versions,
    }
    return render(request, "documents/version_control/document_branch/detail.html", context)


@login_required
def document_branch_create(request):
    doc_id = request.GET.get("document", "").strip()
    initial = {}
    if doc_id and doc_id.isdigit():
        doc = documents_scope(Document.objects.all(), request).filter(pk=int(doc_id)).first()
        if doc:
            initial["document"] = doc
            base = doc.versions.order_by("-created_at").first()
            if base:
                initial["base_version"] = base

    if request.method == "POST":
        form = DocumentBranchForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            branch = form.save(commit=False)
            branch.tenant = request.tenant
            if not branch.created_by_id:
                branch.created_by = request.user
            branch.save()
            write_audit_log(request.user, branch, "fork", tenant=request.tenant)
            messages.success(request, f"Revision branch '{branch.name}' created.")
            return redirect("documents:document_branch_detail", pk=branch.pk)
    else:
        form = DocumentBranchForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "branch": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "documents/version_control/document_branch/form.html", context)


@login_required
def document_branch_edit(request, pk):
    branch = documents_object(request, DocumentBranch, pk)
    if request.method == "POST":
        form = DocumentBranchForm(request.POST, instance=branch, tenant=request.tenant)
        if form.is_valid():
            branch = form.save()
            write_audit_log(request.user, branch, "update", tenant=request.tenant)
            messages.success(request, f"Branch '{branch.name}' updated.")
            return redirect("documents:document_branch_detail", pk=branch.pk)
    else:
        form = DocumentBranchForm(instance=branch, tenant=request.tenant)

    context = {
        "form": form,
        "branch": branch,
        "obj": branch,
        "is_edit": True,
    }
    return render(request, "documents/version_control/document_branch/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def document_branch_delete(request, pk):
    branch = documents_object(request, DocumentBranch, pk)
    doc_pk = branch.document_id
    name = branch.name
    write_audit_log(request.user, branch, "delete", tenant=request.tenant)
    branch.delete()
    messages.success(request, f"Branch '{name}' deleted.")
    return redirect("documents:document_detail", pk=doc_pk)


@login_required
def document_branch_merge(request, pk):
    branch = documents_object(request, DocumentBranch, pk)
    document = branch.document

    if branch.status != "active":
        messages.error(request, f"Branch '{branch.name}' is already {branch.get_status_display().lower()}.")
        return redirect("documents:document_branch_detail", pk=branch.pk)

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    is_author_or_owner = (branch.created_by == request.user) or (document.owner == request.user)
    if not (is_admin or is_author_or_owner):
        messages.error(request, "Only the branch creator, document owner, or a tenant administrator can merge this branch.")
        return redirect("documents:document_branch_detail", pk=branch.pk)

    if document.is_locked:
        locked_by_str = getattr(document.locked_by, "username", "another user")
        messages.error(
            request,
            f"Document '{document.number}' is currently checked out by {locked_by_str} and cannot be merged.",
        )
        return redirect("documents:document_branch_detail", pk=branch.pk)

    if request.method == "POST":
        form = BranchMergeForm(request.POST, request.FILES)
        if form.is_valid():
            strategy = form.cleaned_data["merge_strategy"]
            summary = form.cleaned_data["change_summary"]
            notes = form.cleaned_data.get("merge_notes", "")
            file = form.cleaned_data.get("file")
            extracted_text = form.cleaned_data.get("extracted_text", "")

            # Calculate version number based on strategy
            if strategy == "new_minor_version":
                major = document.current_version_no
                minor = document.versions.count() + 1
                label = f"{major}.{minor}"
            else:  # new_major_version or replace_content
                major = document.current_version_no + 1
                minor = 0
                label = f"{major}.0"

            base = branch.base_version

            with transaction.atomic():
                doc = Document.objects.select_for_update().get(pk=document.pk, tenant=request.tenant)
                if doc.is_locked:
                    locked_by_str = getattr(doc.locked_by, "username", "another user")
                    messages.error(
                        request,
                        f"Document '{doc.number}' is currently checked out by {locked_by_str} and cannot be merged.",
                    )
                    return redirect("documents:document_branch_detail", pk=branch.pk)

                merged_ver = DocumentVersion.objects.create(
                    tenant=request.tenant,
                    document=doc,
                    version_label=label,
                    major_number=major,
                    minor_number=minor,
                    patch_number=0,
                    version_type="branch_merge",
                    file=file or base.file,
                    file_name=file.name if file else base.file_name,
                    extracted_text=extracted_text or base.extracted_text,
                    change_summary=f"[Merged from {branch.name}] {summary}"[:500],
                    is_official=True,
                    status="approved",
                    author=request.user,
                    branch=branch,
                )

                branch.status = "merged"
                branch.merged_at = timezone.now()
                branch.merged_by = request.user
                branch.merged_into_version = merged_ver
                branch.merge_strategy = strategy
                branch.merge_notes = notes
                branch.save(
                    update_fields=[
                        "status",
                        "merged_at",
                        "merged_by",
                        "merged_into_version",
                        "merge_strategy",
                        "merge_notes",
                        "updated_at",
                    ]
                )

                doc.current_version_label = label
                doc.current_version_no = major
                doc.save(update_fields=["current_version_label", "current_version_no", "updated_at"])

            write_audit_log(request.user, branch, "merge", tenant=request.tenant)
            messages.success(request, f"Branch '{branch.name}' successfully merged into mainline as v{label}.")
            return redirect("documents:document_detail", pk=doc.pk)
    else:
        form = BranchMergeForm(
            initial={
                "change_summary": f"Merge changes from branch {branch.name}",
                "extracted_text": branch.base_version.extracted_text if branch.base_version else "",
            }
        )

    context = {
        "form": form,
        "branch": branch,
        "document": document,
    }
    return render(request, "documents/version_control/document_branch/merge_modal.html", context)


@login_required
@require_POST
def document_branch_abandon(request, pk):
    branch = documents_object(request, DocumentBranch, pk)
    document = branch.document

    if branch.status != "active":
        messages.info(request, f"Branch '{branch.name}' is already {branch.get_status_display().lower()}.")
        return redirect("documents:document_branch_detail", pk=branch.pk)

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    is_author_or_owner = (branch.created_by == request.user) or (document.owner == request.user)
    if not (is_admin or is_author_or_owner):
        messages.error(request, "Only the branch creator, document owner, or a tenant administrator can abandon this branch.")
        return redirect("documents:document_branch_detail", pk=branch.pk)

    if document.is_locked:
        locked_by_str = getattr(document.locked_by, "username", "another user")
        messages.error(
            request,
            f"Document '{document.number}' is currently checked out by {locked_by_str} and branch cannot be modified.",
        )
        return redirect("documents:document_branch_detail", pk=branch.pk)

    branch.status = "abandoned"
    branch.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, branch, "abandon", tenant=request.tenant)
    messages.info(request, f"Branch '{branch.name}' has been abandoned.")
    return redirect("documents:document_branch_detail", pk=branch.pk)
