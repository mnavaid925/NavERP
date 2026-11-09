from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetDepreciation.CapitalizationPolicies import CapitalizationPolicyForm
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetDepreciation.CapitalizationPolicies import CapitalizationPolicy
from apps.assets.views._common import assets_object
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def capitalization_policy_list(request):
    qs = CapitalizationPolicy.objects.filter(tenant=request.tenant).select_related(
        "category", "default_cip_account", "default_expense_account"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(applicable_gaap_standard__icontains=q)
            | Q(policy_notes__icontains=q)
        )

    selected_scope = request.GET.get("scope", "").strip()
    if selected_scope:
        qs = qs.filter(policy_scope=selected_scope)

    selected_category = request.GET.get("category", "").strip()
    if selected_category and selected_category.isdigit():
        qs = qs.filter(category_id=int(selected_category))

    all_tenant_policies = CapitalizationPolicy.objects.filter(tenant=request.tenant)
    agg = all_tenant_policies.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        safe_harbor=Count("id", filter=Q(de_minimis_safe_harbor=True)),
        overrides=Count("id", filter=Q(policy_scope="category_override")),
    )

    categories = AssetCategory.objects.filter(tenant=request.tenant, is_active=True).order_by("code")

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "policies": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "scope_choices": CapitalizationPolicy.POLICY_SCOPE_CHOICES,
        "categories": categories,
        "total_policies": agg["total"] or 0,
        "active_count": agg["active"] or 0,
        "safe_harbor_count": agg["safe_harbor"] or 0,
        "override_count": agg["overrides"] or 0,
        "q": q,
        "selected_scope": selected_scope,
        "selected_category": selected_category,
    }
    return render(
        request, "assets/asset_depreciation/capitalization_policy/list.html", context
    )


@login_required
def capitalization_policy_detail(request, pk):
    policy = assets_object(
        request,
        CapitalizationPolicy,
        pk=pk,
        select_related=["category", "default_cip_account", "default_expense_account"],
    )

    eval_result = None
    eval_cost = request.GET.get("eval_cost", "").strip()
    eval_life = request.GET.get("eval_life", "").strip()
    if eval_cost:
        try:
            classification, reason = policy.evaluate_asset(eval_cost, eval_life or 12)
            eval_result = {
                "classification": classification,
                "reason": reason,
                "cost": eval_cost,
                "life": eval_life or "12",
            }
        except (ValueError, TypeError):
            eval_result = None

    context = {
        "policy": policy,
        "object": policy,
        "eval_result": eval_result,
        "eval_cost": eval_cost,
        "eval_life": eval_life,
    }
    return render(
        request, "assets/asset_depreciation/capitalization_policy/detail.html", context
    )


@login_required
def capitalization_policy_create(request):
    if request.method == "POST":
        form = CapitalizationPolicyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.tenant = request.tenant
            policy.save()
            write_audit_log(request.user, policy, "create", tenant=request.tenant)
            messages.success(
                request, f"Capitalization policy {policy.number} created successfully."
            )
            return redirect("assets:capitalization_policy_detail", pk=policy.pk)
    else:
        form = CapitalizationPolicyForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "policy": None,
        "object": None,
    }
    return render(
        request, "assets/asset_depreciation/capitalization_policy/form.html", context
    )


@login_required
def capitalization_policy_edit(request, pk):
    policy = assets_object(request, CapitalizationPolicy, pk=pk)

    if request.method == "POST":
        form = CapitalizationPolicyForm(
            request.POST, instance=policy, tenant=request.tenant
        )
        if form.is_valid():
            policy = form.save(commit=False)
            policy.save()
            write_audit_log(request.user, policy, "update", tenant=request.tenant)
            messages.success(
                request, f"Capitalization policy {policy.number} updated successfully."
            )
            return redirect("assets:capitalization_policy_detail", pk=policy.pk)
    else:
        form = CapitalizationPolicyForm(instance=policy, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "policy": policy,
        "object": policy,
    }
    return render(
        request, "assets/asset_depreciation/capitalization_policy/form.html", context
    )


@login_required
@require_POST
@tenant_admin_required
def capitalization_policy_delete(request, pk):
    policy = assets_object(request, CapitalizationPolicy, pk=pk)
    num = policy.number
    policy.delete()
    write_audit_log(request.user, policy, "delete", tenant=request.tenant)
    messages.success(request, f"Capitalization policy {num} deleted.")
    return redirect("assets:capitalization_policy_list")
