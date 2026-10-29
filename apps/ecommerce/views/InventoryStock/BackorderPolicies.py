from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.InventoryStock.BackorderPolicies import BackorderPolicyForm
from apps.ecommerce.models.InventoryStock.BackorderPolicies import BackorderPolicy
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def backorderpolicy_list(request):
    qs = ecommerce_scope(
        BackorderPolicy.objects.select_related("variant", "variant__product"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    policy_type_filter = request.GET.get("policy_type", "").strip()
    active_filter = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(variant__sku__icontains=search_query)
            | Q(variant__name__icontains=search_query)
            | Q(variant__product__name__icontains=search_query)
            | Q(storefront_message__icontains=search_query)
        )

    if policy_type_filter:
        qs = qs.filter(policy_type=policy_type_filter)

    if active_filter in ("1", "true"):
        qs = qs.filter(is_active=True)
    elif active_filter in ("0", "false"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "policies": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "policy_type_filter": policy_type_filter,
        "active_filter": active_filter,
        "policy_type_choices": BackorderPolicy.POLICY_TYPE_CHOICES,
    }
    return render(request, "ecommerce/inventorystock/backorderpolicy/list.html", context)


@login_required
def backorderpolicy_detail(request, pk):
    policy = ecommerce_object(
        request,
        BackorderPolicy,
        pk,
        select_related=("variant", "variant__product"),
    )
    variant = policy.variant
    product = variant.product
    allocations = variant.inventory_allocations.select_related("fulfillment_center").all()

    context = {
        "policy": policy,
        "variant": variant,
        "product": product,
        "allocations": allocations,
    }
    return render(request, "ecommerce/inventorystock/backorderpolicy/detail.html", context)


@login_required
def backorderpolicy_create(request):
    initial_variant_id = request.GET.get("variant")
    initial_data = {}
    if initial_variant_id and initial_variant_id.isdigit():
        initial_data["variant"] = int(initial_variant_id)

    if request.method == "POST":
        form = BackorderPolicyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            policy = form.save(commit=False)
            policy.tenant = request.tenant
            policy.save()
            write_audit_log(
                request.user,
                policy,
                "create",
                {"sku": policy.variant.sku, "policy_type": policy.policy_type},
            )
            messages.success(request, f"Backorder policy for '{policy.variant.sku}' created successfully.")
            return redirect("ecommerce:backorderpolicy_detail", pk=policy.pk)
    else:
        form = BackorderPolicyForm(tenant=request.tenant, initial=initial_data)

    context = {
        "form": form,
        "is_create": True,
    }
    return render(request, "ecommerce/inventorystock/backorderpolicy/form.html", context)


@login_required
def backorderpolicy_edit(request, pk):
    policy = ecommerce_object(
        request,
        BackorderPolicy,
        pk,
        select_related=("variant", "variant__product"),
    )
    if request.method == "POST":
        form = BackorderPolicyForm(request.POST, instance=policy, tenant=request.tenant)
        if form.is_valid():
            policy = form.save()
            write_audit_log(
                request.user,
                policy,
                "update",
                {"sku": policy.variant.sku, "policy_type": policy.policy_type},
            )
            messages.success(request, f"Backorder policy for '{policy.variant.sku}' updated successfully.")
            return redirect("ecommerce:backorderpolicy_detail", pk=policy.pk)
    else:
        form = BackorderPolicyForm(instance=policy, tenant=request.tenant)

    context = {
        "form": form,
        "policy": policy,
        "is_create": False,
    }
    return render(request, "ecommerce/inventorystock/backorderpolicy/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def backorderpolicy_delete(request, pk):
    policy = ecommerce_object(request, BackorderPolicy, pk, select_related=("variant",))
    sku = policy.variant.sku
    policy.delete()
    write_audit_log(
        request.user,
        policy,
        "delete",
        {"sku": sku},
    )
    messages.success(request, f"Backorder policy for '{sku}' was deleted.")
    return redirect("ecommerce:backorderpolicy_list")
