from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.models import Employment
from apps.core.utils import write_audit_log
from apps.documents.forms.SecurityAccessControl.DocumentAccessPermissions import DocumentAccessPermissionForm
from apps.documents.models.SecurityAccessControl.DocumentAccessPermissions import DocumentAccessPermission
from apps.documents.models.StorageRepository.DocumentFolders import DocumentFolder
from apps.documents.models.VersionControl.Documents import Document
from apps.documents.views._common import documents_object, documents_scope

User = get_user_model()
PAGE_SIZE = 15


@login_required
def permission_list(request):
    qs = documents_scope(DocumentAccessPermission.objects.all(), request).select_related(
        "document", "folder", "user", "org_unit", "created_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(role_name__icontains=q)
            | Q(notes__icontains=q)
            | Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(document__title__icontains=q)
            | Q(folder__name__icontains=q)
        )

    grantee_type = request.GET.get("grantee_type", "").strip()
    if grantee_type:
        qs = qs.filter(grantee_type=grantee_type)

    permission_level = request.GET.get("permission_level", "").strip()
    if permission_level:
        qs = qs.filter(permission_level=permission_level)

    is_active_val = request.GET.get("is_active", "").strip()
    if is_active_val == "1":
        qs = qs.filter(is_active=True)
    elif is_active_val == "0":
        qs = qs.filter(is_active=False)

    doc_id = request.GET.get("document", "").strip()
    if doc_id.isdigit():
        qs = qs.filter(document_id=int(doc_id))

    folder_id = request.GET.get("folder", "").strip()
    if folder_id.isdigit():
        qs = qs.filter(folder_id=int(folder_id))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "permissions": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "paginator": paginator,
        "search_query": q,
        "grantee_type": grantee_type,
        "permission_level": permission_level,
        "is_active": is_active_val,
        "document": doc_id,
        "folder": folder_id,
        "grantee_choices": DocumentAccessPermission.GRANTEE_TYPE_CHOICES,
        "level_choices": DocumentAccessPermission.PERMISSION_LEVEL_CHOICES,
    }
    return render(
        request,
        "documents/security_access_control/document_access_permission/list.html",
        context,
    )


@login_required
def permission_detail(request, pk):
    permission = documents_object(
        request,
        DocumentAccessPermission,
        pk,
        select_related=("document", "folder", "user", "org_unit", "created_by", "inherited_from_folder"),
    )

    context = {
        "permission": permission,
        "document": permission.document,
        "folder": permission.folder,
        "grantee": permission.grantee_display,
    }
    return render(
        request,
        "documents/security_access_control/document_access_permission/detail.html",
        context,
    )


@tenant_admin_required
def permission_create(request):
    if request.method == "POST":
        form = DocumentAccessPermissionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            permission = form.save(commit=False)
            permission.tenant = request.tenant
            permission.created_by = request.user
            permission.save()
            write_audit_log(request.user, permission, "create", tenant=request.tenant)
            messages.success(request, f"Permission {permission.number} granted successfully.")
            return redirect(reverse("documents:permission_detail", kwargs={"pk": permission.pk}))
    else:
        initial = {}
        if request.GET.get("document_id", "").isdigit():
            initial["document"] = int(request.GET.get("document_id"))
        if request.GET.get("folder_id", "").isdigit():
            initial["folder"] = int(request.GET.get("folder_id"))
        form = DocumentAccessPermissionForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(
        request,
        "documents/security_access_control/document_access_permission/form.html",
        context,
    )


@tenant_admin_required
def permission_edit(request, pk):
    permission = documents_object(request, DocumentAccessPermission, pk)
    if request.method == "POST":
        form = DocumentAccessPermissionForm(request.POST, instance=permission, tenant=request.tenant)
        if form.is_valid():
            permission = form.save()
            write_audit_log(request.user, permission, "update", tenant=request.tenant)
            messages.success(request, f"Permission {permission.number} updated successfully.")
            return redirect(reverse("documents:permission_detail", kwargs={"pk": permission.pk}))
    else:
        form = DocumentAccessPermissionForm(instance=permission, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "permission": permission,
    }
    return render(
        request,
        "documents/security_access_control/document_access_permission/form.html",
        context,
    )


@tenant_admin_required
@require_POST
def permission_delete(request, pk):
    permission = documents_object(request, DocumentAccessPermission, pk)
    num = permission.number
    write_audit_log(request.user, permission, "delete", tenant=request.tenant)
    permission.delete()
    messages.success(request, f"Permission {num} deleted.")
    return redirect(reverse("documents:permission_list"))


@login_required
def permission_simulate(request):
    """Interactive simulator to evaluate effective document capabilities for a specific user."""
    docs_qs = Document.objects.filter(tenant=request.tenant)
    users_qs = User.objects.filter(tenant=request.tenant)
    documents = docs_qs.only("id", "number", "title", "classification").order_by("title")[:200]
    users = users_qs.only("id", "username", "first_name", "last_name").order_by("username")[:200]

    target_document = None
    target_user = None
    simulated = False
    effective_capabilities = {
        "can_read": False,
        "can_write": False,
        "can_delete": False,
        "can_download": False,
        "can_print": False,
        "can_share": False,
        "reason": "No matching active ACL permissions found for this user/document combination.",
        "matched_rules": [],
    }

    doc_id = request.GET.get("document", "").strip()
    user_id = request.GET.get("user", "").strip()

    if doc_id.isdigit() and user_id.isdigit():
        simulated = True
        target_document = get_object_or_404(docs_qs, pk=int(doc_id))
        target_user = get_object_or_404(users_qs, pk=int(user_id))

        # Check tenant admin or superuser
        if getattr(target_user, "is_tenant_admin", False) or getattr(target_user, "is_superuser", False):
            effective_capabilities = {
                "can_read": True,
                "can_write": True,
                "can_delete": True,
                "can_download": True,
                "can_print": True,
                "can_share": True,
                "reason": "User is a Tenant Administrator with full unrestricted control.",
                "matched_rules": ["Tenant Admin Bypass"],
            }
        elif target_document.owner_id == target_user.id:
            effective_capabilities = {
                "can_read": True,
                "can_write": True,
                "can_delete": True,
                "can_download": True,
                "can_print": True,
                "can_share": True,
                "reason": "User is the primary author/owner of this document.",
                "matched_rules": [f"Document Owner ({target_user.username})"],
            }
        else:
            # Evaluate ACLs
            target_party = getattr(target_user, "party", None)
            emp = (
                Employment.objects.filter(tenant=request.tenant, party=target_party).order_by("-id").first()
                if target_party
                else None
            )
            user_dept = emp.org_unit if emp else None
            now = timezone.now()

            q_rule = Q(document=target_document)
            folder_id = getattr(target_document, "folder_id", None)
            if folder_id:
                q_rule |= Q(folder_id=folder_id)

            rules = DocumentAccessPermission.objects.filter(
                tenant=request.tenant,
                is_active=True,
            ).filter(q_rule).filter(
                Q(grantee_type="tenant_wide")
                | Q(grantee_type="user", user=target_user)
                | (Q(grantee_type="org_unit", org_unit=user_dept) if user_dept else Q(pk__in=[]))
            )

            matched_rules = []
            for r in rules:
                if r.valid_from and now < r.valid_from:
                    continue
                if r.valid_until and now > r.valid_until:
                    continue
                matched_rules.append(f"{r.number} ({r.get_grantee_type_display()}: {r.get_permission_level_display()})")
                if r.can_read:
                    effective_capabilities["can_read"] = True
                if r.can_write:
                    effective_capabilities["can_write"] = True
                if r.can_delete:
                    effective_capabilities["can_delete"] = True
                if r.can_download:
                    effective_capabilities["can_download"] = True
                if r.can_print:
                    effective_capabilities["can_print"] = True
                if r.can_share:
                    effective_capabilities["can_share"] = True

            effective_capabilities["matched_rules"] = matched_rules
            if matched_rules:
                effective_capabilities["reason"] = f"Aggregated from {len(matched_rules)} matching access rule(s)."

        write_audit_log(request.user, target_document, "simulate", tenant=request.tenant)

    context = {
        "documents": documents,
        "users": users,
        "simulated": simulated,
        "target_document": target_document,
        "target_user": target_user,
        "effective_capabilities": effective_capabilities,
    }
    return render(
        request,
        "documents/security_access_control/document_access_permission/simulate.html",
        context,
    )
