from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.documents.forms.SecurityAccessControl.WatermarkPolicies import WatermarkPolicyForm
from apps.documents.models.SecurityAccessControl.WatermarkPolicies import WatermarkPolicy
from apps.documents.views._common import documents_object, documents_scope

PAGE_SIZE = 15


@login_required
def watermark_list(request):
    qs = documents_scope(WatermarkPolicy.objects.all(), request).select_related(
        "department", "created_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(watermark_text__icontains=q)
            | Q(description__icontains=q)
        )

    classification = request.GET.get("classification", "").strip()
    if classification:
        qs = qs.filter(classification=classification)

    is_active_val = request.GET.get("is_active", "").strip()
    if is_active_val == "1":
        qs = qs.filter(is_active=True)
    elif is_active_val == "0":
        qs = qs.filter(is_active=False)

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
        "is_active": is_active_val,
        "classification_choices": WatermarkPolicy.CLASSIFICATION_CHOICES,
    }
    return render(
        request,
        "documents/security_access_control/watermark_policy/list.html",
        context,
    )


@login_required
def watermark_detail(request, pk):
    policy = documents_object(
        request,
        WatermarkPolicy,
        pk,
        select_related=("department", "created_by"),
    )
    ip_addr = request.META.get("REMOTE_ADDR", "127.0.0.1")
    sample_text = policy.render_watermark(user=request.user, ip_address=ip_addr)

    context = {
        "policy": policy,
        "sample_watermark_text": sample_text,
    }
    return render(
        request,
        "documents/security_access_control/watermark_policy/detail.html",
        context,
    )


@tenant_admin_required
def watermark_create(request):
    if request.method == "POST":
        form = WatermarkPolicyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.tenant = request.tenant
            policy.created_by = request.user
            policy.save()
            write_audit_log(request.user, policy, "create", tenant=request.tenant)
            messages.success(request, f"Watermark policy {policy.name} created successfully.")
            return redirect(reverse("documents:watermark_detail", kwargs={"pk": policy.pk}))
    else:
        form = WatermarkPolicyForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(
        request,
        "documents/security_access_control/watermark_policy/form.html",
        context,
    )


@tenant_admin_required
def watermark_edit(request, pk):
    policy = documents_object(request, WatermarkPolicy, pk)
    if request.method == "POST":
        form = WatermarkPolicyForm(request.POST, instance=policy, tenant=request.tenant)
        if form.is_valid():
            policy = form.save()
            write_audit_log(request.user, policy, "update", tenant=request.tenant)
            messages.success(request, f"Watermark policy {policy.name} updated successfully.")
            return redirect(reverse("documents:watermark_detail", kwargs={"pk": policy.pk}))
    else:
        form = WatermarkPolicyForm(instance=policy, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "policy": policy,
    }
    return render(
        request,
        "documents/security_access_control/watermark_policy/form.html",
        context,
    )


@tenant_admin_required
@require_POST
def watermark_delete(request, pk):
    policy = documents_object(request, WatermarkPolicy, pk)
    name = policy.name
    write_audit_log(request.user, policy, "delete", tenant=request.tenant)
    policy.delete()
    messages.success(request, f"Watermark policy {name} deleted.")
    return redirect(reverse("documents:watermark_list"))


@login_required
def watermark_preview(request):
    """Interactive preview canvas for visual watermark verification."""
    policy_id = request.GET.get("policy_id", "").strip()
    policy = None
    if policy_id.isdigit():
        policy = WatermarkPolicy.objects.filter(tenant=request.tenant, pk=int(policy_id)).first()

    ip_addr = request.META.get("REMOTE_ADDR", "127.0.0.1")
    if policy:
        preview_text = policy.render_watermark(user=request.user, ip_address=ip_addr)
        opacity = policy.opacity_percent
        angle = policy.rotation_angle
        position = policy.position
        classification = policy.get_classification_display()
    else:
        preview_text = f"CONFIDENTIAL | {request.user.get_full_name() or request.user.username} | {ip_addr}"
        opacity = 25
        angle = -45
        position = "diagonal_center"
        classification = "Confidential"

    context = {
        "policy": policy,
        "preview_text": preview_text,
        "opacity": opacity,
        "angle": angle,
        "position": position,
        "classification": classification,
        "policies": WatermarkPolicy.objects.filter(tenant=request.tenant, is_active=True).order_by("priority"),
    }
    return render(
        request,
        "documents/security_access_control/watermark_policy/preview.html",
        context,
    )
