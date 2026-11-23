from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.SecurityAccessControl.DocumentDrmPolicies import DocumentDrmPolicyForm
from apps.documents.models.SecurityAccessControl.DocumentDrmPolicies import DocumentDrmPolicy
from apps.documents.views._common import documents_object, documents_scope

PAGE_SIZE = 15


@login_required
def drm_policy_list(request):
    qs = documents_scope(DocumentDrmPolicy.objects.all(), request).select_related(
        "target_document", "target_folder", "created_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
            | Q(target_document__title__icontains=q)
        )

    classification = request.GET.get("classification", "").strip()
    if classification:
        qs = qs.filter(classification=classification)

    is_revoked_val = request.GET.get("is_revoked", "").strip()
    if is_revoked_val == "1":
        qs = qs.filter(is_revoked=True)
    elif is_revoked_val == "0":
        qs = qs.filter(is_revoked=False)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "policies": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "paginator": paginator,
        "search_query": q,
        "classification": classification,
        "is_revoked": is_revoked_val,
        "classification_choices": DocumentDrmPolicy.CLASSIFICATION_CHOICES,
    }
    return render(
        request,
        "documents/security_access_control/document_drm_policy/list.html",
        context,
    )


@login_required
def drm_policy_detail(request, pk):
    policy = documents_object(
        request,
        DocumentDrmPolicy,
        pk,
        select_related=("target_document", "target_folder", "created_by"),
    )

    context = {
        "policy": policy,
    }
    return render(
        request,
        "documents/security_access_control/document_drm_policy/detail.html",
        context,
    )


@tenant_admin_required
def drm_policy_create(request):
    if request.method == "POST":
        form = DocumentDrmPolicyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.tenant = request.tenant
            policy.created_by = request.user
            policy.save()
            write_audit_log(request.user, policy, "create", tenant=request.tenant)
            messages.success(request, f"DRM Policy {policy.name} configured successfully.")
            return redirect(reverse("documents:drm_policy_detail", kwargs={"pk": policy.pk}))
    else:
        form = DocumentDrmPolicyForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(
        request,
        "documents/security_access_control/document_drm_policy/form.html",
        context,
    )


@tenant_admin_required
def drm_policy_edit(request, pk):
    policy = documents_object(request, DocumentDrmPolicy, pk)
    if request.method == "POST":
        form = DocumentDrmPolicyForm(request.POST, instance=policy, tenant=request.tenant)
        if form.is_valid():
            policy = form.save()
            write_audit_log(request.user, policy, "update", tenant=request.tenant)
            messages.success(request, f"DRM Policy {policy.name} updated successfully.")
            return redirect(reverse("documents:drm_policy_detail", kwargs={"pk": policy.pk}))
    else:
        form = DocumentDrmPolicyForm(instance=policy, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "policy": policy,
    }
    return render(
        request,
        "documents/security_access_control/document_drm_policy/form.html",
        context,
    )


@tenant_admin_required
@require_POST
def drm_policy_delete(request, pk):
    policy = documents_object(request, DocumentDrmPolicy, pk)
    name = policy.name
    write_audit_log(request.user, policy, "delete", tenant=request.tenant)
    policy.delete()
    messages.success(request, f"DRM Policy {name} deleted.")
    return redirect(reverse("documents:drm_policy_list"))


@tenant_admin_required
@require_POST
def drm_kill_switch(request, pk):
    """Emergency kill switch: instantly invalidates policy and revokes all active document access."""
    policy = documents_object(request, DocumentDrmPolicy, pk)
    reason = request.POST.get("reason", "").strip() or "Emergency administrative revocation"
    policy.revoke(user=request.user, reason=reason)
    write_audit_log(request.user, policy, "revoke", tenant=request.tenant)
    messages.warning(
        request,
        f"EMERGENCY KILL SWITCH ENGAGED: DRM Policy '{policy.name}' has been revoked. All active access has been terminated.",
    )
    return redirect(reverse("documents:drm_policy_detail", kwargs={"pk": policy.pk}))
