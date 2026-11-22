from collections import defaultdict
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.models import OrgUnit
from apps.core.utils import write_audit_log
from apps.documents.forms.StorageRepository.DocumentFolders import DocumentFolderForm
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.views._common import documents_object, documents_scope


@login_required
def folder_list(request):
    qs = documents_scope(
        DocumentFolder.objects.select_related("parent", "department", "owner"),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(path__icontains=q)
            | Q(description__icontains=q)
        )

    is_virtual = request.GET.get("is_virtual", "").strip()
    if is_virtual == "1":
        qs = qs.filter(is_virtual=True)
    elif is_virtual == "0":
        qs = qs.filter(is_virtual=False)

    department_id = request.GET.get("department", "").strip()
    if department_id and department_id.isdigit():
        qs = qs.filter(department_id=int(department_id))

    status = request.GET.get("status", "").strip()
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    total_count = qs.count()

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "folders": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "is_virtual": is_virtual,
        "department": department_id,
        "departments": departments,
        "status": status,
        "total_count": total_count,
    }
    return render(request, "documents/storage_repository/document_folder/list.html", context)


@login_required
def folder_tree(request):
    all_folders = list(
        DocumentFolder.objects.filter(
            tenant=request.tenant,
            is_active=True,
        )
        .select_related("owner", "department")
        .order_by("name")
    )

    children_by_parent = defaultdict(list)
    root_folders = []
    for folder in all_folders:
        if folder.parent_id is None:
            root_folders.append(folder)
        else:
            children_by_parent[folder.parent_id].append(folder)

    for folder in all_folders:
        folder._prefetched_objects_cache = {"children": children_by_parent.get(folder.id, [])}

    # Build nested tree dict for client rendering in memory
    def build_tree(folder):
        children = children_by_parent.get(folder.id, [])
        return {
            "id": folder.id,
            "number": folder.number,
            "name": folder.name,
            "path": folder.path,
            "color_code": folder.color_code,
            "icon_name": folder.icon_name,
            "is_virtual": folder.is_virtual,
            "children": [build_tree(child) for child in children],
        }

    tree_data = [build_tree(f) for f in root_folders]

    context = {
        "root_folders": root_folders,
        "tree_json": json.dumps(tree_data),
    }
    return render(request, "documents/storage_repository/document_folder/tree.html", context)


@login_required
def folder_create(request):
    if request.method == "POST":
        form = DocumentFolderForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                folder = form.save(commit=False)
                folder.tenant = request.tenant
                if not folder.owner_id:
                    folder.owner = request.user
                folder.save()
                write_audit_log(request.user, folder, "create", tenant=request.tenant)
            messages.success(request, f"Folder '{folder.name}' created successfully.")
            return redirect("documents:folder_detail", pk=folder.pk)
    else:
        parent_id = request.GET.get("parent")
        initial = {}
        if parent_id and parent_id.isdigit():
            initial["parent"] = int(parent_id)
        form = DocumentFolderForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "title": "Create Document Folder",
    }
    return render(request, "documents/storage_repository/document_folder/form.html", context)


@login_required
def folder_detail(request, pk):
    folder = documents_object(
        request,
        DocumentFolder,
        pk,
        select_related=("parent", "department", "owner"),
    )
    subfolders = folder.children.filter(tenant=request.tenant, is_active=True).select_related("owner", "department").order_by("name")

    # Document list inside folder (either virtual query or direct match)
    docs_qs = Document.objects.filter(tenant=request.tenant)
    if folder.is_virtual:
        criteria = folder.criteria_dict
        if "classification" in criteria:
            docs_qs = docs_qs.filter(classification=criteria["classification"])
        if "document_type" in criteria:
            docs_qs = docs_qs.filter(document_type=criteria["document_type"])
        if "status" in criteria:
            docs_qs = docs_qs.filter(status=criteria["status"])
    else:
        # Match documents by tag or path
        docs_qs = docs_qs.filter(
            Q(tags__icontains=folder.slug) | Q(description__icontains=folder.name)
        )

    docs_qs = docs_qs.select_related("owner", "department").order_by("-created_at")
    total_files = docs_qs.count()

    paginator = Paginator(docs_qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "folder": folder,
        "subfolders": subfolders,
        "documents": page_obj.object_list,
        "page_obj": page_obj,
        "total_files": total_files,
        "total_bytes": total_files * 1024 * 1024,  # Est. aggregate bytes
    }
    return render(request, "documents/storage_repository/document_folder/detail.html", context)


@login_required
def folder_edit(request, pk):
    folder = documents_object(request, DocumentFolder, pk)
    if request.method == "POST":
        form = DocumentFolderForm(request.POST, instance=folder, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                folder = form.save()
                write_audit_log(request.user, folder, "update", tenant=request.tenant)
            messages.success(request, f"Folder '{folder.name}' updated successfully.")
            return redirect("documents:folder_detail", pk=folder.pk)
    else:
        form = DocumentFolderForm(instance=folder, tenant=request.tenant)

    context = {
        "form": form,
        "folder": folder,
        "is_edit": True,
        "title": f"Edit Folder — {folder.name}",
    }
    return render(request, "documents/storage_repository/document_folder/form.html", context)


@require_POST
@login_required
def folder_delete(request, pk):
    folder = documents_object(request, DocumentFolder, pk)
    if folder.is_system:
        messages.error(request, "Protected system folders cannot be deleted.")
        return redirect("documents:folder_detail", pk=folder.pk)

    if folder.owner_id and folder.owner_id != request.user.id and not (
        request.user.is_superuser
        or getattr(request.user, "is_tenant_admin", False)
        or getattr(request, "is_tenant_admin", False)
    ):
        messages.error(
            request,
            "You do not have permission to delete this folder. Only the folder owner or tenant administrator can delete it.",
        )
        return redirect("documents:folder_detail", pk=folder.pk)

    if folder.children.filter(tenant=request.tenant, is_active=True).exists():
        messages.error(request, "Cannot delete folder containing active subfolders. Move or delete subfolders first.")
        return redirect("documents:folder_detail", pk=folder.pk)

    name = folder.name
    with transaction.atomic():
        write_audit_log(request.user, folder, "delete", tenant=request.tenant)
        folder.delete()
    messages.success(request, f"Folder '{name}' deleted successfully.")
    return redirect("documents:folder_list")
