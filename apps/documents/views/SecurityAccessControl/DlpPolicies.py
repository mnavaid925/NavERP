from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.SecurityAccessControl.DlpPolicies import DlpPolicyForm
from apps.documents.models.SecurityAccessControl.DlpPolicies import DlpPolicy
from apps.documents.views._common import documents_object, documents_scope

PAGE_SIZE = 15


@login_required
def dlp_policy_list(request):
    qs = documents_scope(DlpPolicy.objects.all(), request).select_related("created_by")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    rule_type = request.GET.get("rule_type", "").strip()
    if rule_type:
        qs = qs.filter(rule_type=rule_type)

    severity = request.GET.get("severity", "").strip()
    if severity:
        qs = qs.filter(severity=severity)

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
        "rule_type": rule_type,
        "severity": severity,
        "is_active": is_active_val,
        "rule_choices": DlpPolicy.RULE_TYPE_CHOICES,
        "severity_choices": DlpPolicy.SEVERITY_CHOICES,
    }
    return render(
        request,
        "documents/security_access_control/dlp_policy/list.html",
        context,
    )


@login_required
def dlp_policy_detail(request, pk):
    policy = documents_object(request, DlpPolicy, pk, select_related=("created_by",))
    incidents = policy.incidents.select_related("document", "triggered_by").order_by("-created_at")[:15]

    context = {
        "policy": policy,
        "incidents": incidents,
    }
    return render(
        request,
        "documents/security_access_control/dlp_policy/detail.html",
        context,
    )


@login_required
def dlp_policy_create(request):
    if request.method == "POST":
        form = DlpPolicyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.tenant = request.tenant
            policy.created_by = request.user
            policy.save()
            write_audit_log(request.user, policy, "create", tenant=request.tenant)
            messages.success(request, f"DLP Policy '{policy.name}' configured successfully.")
            return redirect(reverse("documents:dlp_policy_detail", kwargs={"pk": policy.pk}))
    else:
        form = DlpPolicyForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(
        request,
        "documents/security_access_control/dlp_policy/form.html",
        context,
    )


@login_required
def dlp_policy_edit(request, pk):
    policy = documents_object(request, DlpPolicy, pk)
    if request.method == "POST":
        form = DlpPolicyForm(request.POST, instance=policy, tenant=request.tenant)
        if form.is_valid():
            policy = form.save()
            write_audit_log(request.user, policy, "update", tenant=request.tenant)
            messages.success(request, f"DLP Policy '{policy.name}' updated successfully.")
            return redirect(reverse("documents:dlp_policy_detail", kwargs={"pk": policy.pk}))
    else:
        form = DlpPolicyForm(instance=policy, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "policy": policy,
    }
    return render(
        request,
        "documents/security_access_control/dlp_policy/form.html",
        context,
    )


@login_required
@require_POST
def dlp_policy_delete(request, pk):
    policy = documents_object(request, DlpPolicy, pk)
    name = policy.name
    write_audit_log(request.user, policy, "delete", tenant=request.tenant)
    policy.delete()
    messages.success(request, f"DLP Policy '{name}' deleted.")
    return redirect(reverse("documents:dlp_policy_list"))
