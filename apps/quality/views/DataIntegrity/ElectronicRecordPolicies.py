from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.DataIntegrity.ElectronicRecordPolicies import ElectronicRecordPolicyForm
from apps.quality.models.DataIntegrity.ElectronicRecordPolicies import ElectronicRecordPolicy
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 20


@login_required
def electronic_record_policy_list(request):
    base_qs = quality_scope(
        ElectronicRecordPolicy.objects.all(),
        request,
    )

    stats = base_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        part11=Count("id", filter=Q(is_part_11_regulated=True)),
        legal_holds=Count("id", filter=Q(legal_hold=True)),
    )
    total_count = stats["total"]
    active_count = stats["active"]
    part11_count = stats["part11"]
    legal_hold_count = stats["legal_holds"]

    qs = base_qs.select_related("system", "governing_sop", "system_owner", "qa_approver")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(number__icontains=q)
            | Q(record_type_name__icontains=q)
            | Q(target_model_name__icontains=q)
        )

    category_selected = request.GET.get("category", "").strip()
    if category_selected:
        qs = qs.filter(record_category=category_selected)

    status_selected = request.GET.get("status", "").strip()
    if status_selected:
        qs = qs.filter(status=status_selected)

    part11_selected = request.GET.get("part11", "").strip()
    if part11_selected == "1":
        qs = qs.filter(is_part_11_regulated=True)
    elif part11_selected == "0":
        qs = qs.filter(is_part_11_regulated=False)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "policies": page_obj.object_list,
        "total_count": total_count,
        "active_count": active_count,
        "part11_count": part11_count,
        "legal_hold_count": legal_hold_count,
        "category_choices": ElectronicRecordPolicy.RECORD_CATEGORY_CHOICES,
        "status_choices": ElectronicRecordPolicy.STATUS_CHOICES,
        "q": q,
        "category_selected": category_selected,
        "status_selected": status_selected,
        "part11_selected": part11_selected,
    }
    return render(
        request,
        "quality/data_integrity/electronic_record_policy/list.html",
        context,
    )


@login_required
def electronic_record_policy_detail(request, pk):
    policy = quality_object(
        request,
        ElectronicRecordPolicy,
        pk,
        select_related=("system", "governing_sop", "system_owner", "qa_approver"),
    )
    return render(
        request,
        "quality/data_integrity/electronic_record_policy/detail.html",
        {"policy": policy},
    )


@login_required
def electronic_record_policy_create(request):
    if request.method == "POST":
        form = ElectronicRecordPolicyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                policy = form.save(commit=False)
                policy.tenant = request.tenant
                policy.save()
                write_audit_log(request.user, policy, "create", tenant=request.tenant)
            messages.success(request, f"Electronic Record Policy {policy.number} created successfully.")
            return redirect("quality:electronic_record_policy_detail", pk=policy.pk)
    else:
        form = ElectronicRecordPolicyForm(tenant=request.tenant)

    return render(
        request,
        "quality/data_integrity/electronic_record_policy/form.html",
        {"form": form, "policy": None, "is_edit": False},
    )


@login_required
def electronic_record_policy_edit(request, pk):
    policy = quality_object(request, ElectronicRecordPolicy, pk)
    if request.method == "POST":
        form = ElectronicRecordPolicyForm(request.POST, instance=policy, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                policy = form.save()
                write_audit_log(request.user, policy, "update", tenant=request.tenant)
            messages.success(request, f"Electronic Record Policy {policy.number} updated successfully.")
            return redirect("quality:electronic_record_policy_detail", pk=policy.pk)
    else:
        form = ElectronicRecordPolicyForm(instance=policy, tenant=request.tenant)

    return render(
        request,
        "quality/data_integrity/electronic_record_policy/form.html",
        {"form": form, "policy": policy, "is_edit": True},
    )


@require_POST
@login_required
@tenant_admin_required
def electronic_record_policy_delete(request, pk):
    policy = quality_object(request, ElectronicRecordPolicy, pk)
    num = policy.number
    with transaction.atomic():
        write_audit_log(request.user, policy, "delete", tenant=request.tenant)
        policy.delete()
    messages.success(request, f"Electronic Record Policy {num} deleted.")
    return redirect("quality:electronic_record_policy_list")
