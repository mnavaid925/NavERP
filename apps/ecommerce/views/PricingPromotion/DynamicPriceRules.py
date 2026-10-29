from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.PricingPromotion.DynamicPriceRules import DynamicPriceRuleForm
from apps.ecommerce.models.PricingPromotion.DynamicPriceRules import DynamicPriceRule
from apps.ecommerce.models.ProductCatalog.StoreCategories import StoreCategory
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def dynamicpricerule_list(request):
    qs = ecommerce_scope(
        DynamicPriceRule.objects.select_related("category", "product", "variant"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    rule_type_filter = request.GET.get("rule_type", "").strip()
    scope_filter = request.GET.get("scope", "").strip()
    segment_filter = request.GET.get("customer_segment", "").strip()
    active_filter = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(category__name__icontains=search_query)
            | Q(product__name__icontains=search_query)
            | Q(variant__sku__icontains=search_query)
        )

    if rule_type_filter:
        qs = qs.filter(rule_type=rule_type_filter)

    if scope_filter:
        qs = qs.filter(scope=scope_filter)

    if segment_filter:
        qs = qs.filter(customer_segment=segment_filter)

    if active_filter in ("1", "true"):
        qs = qs.filter(is_active=True)
    elif active_filter in ("0", "false"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    categories = StoreCategory.objects.filter(tenant=request.tenant)

    context = {
        "rules": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "current_q": search_query,
        "rule_type_filter": rule_type_filter,
        "current_type": rule_type_filter,
        "scope_filter": scope_filter,
        "current_scope": scope_filter,
        "segment_filter": segment_filter,
        "current_segment": segment_filter,
        "active_filter": active_filter,
        "rule_type_choices": DynamicPriceRule.RULE_TYPE_CHOICES,
        "scope_choices": DynamicPriceRule.SCOPE_CHOICES,
        "segment_choices": DynamicPriceRule.CUSTOMER_SEGMENT_CHOICES,
        "categories": categories,
    }
    return render(request, "ecommerce/pricingpromotion/dynamicpricerule/list.html", context)


@login_required
def dynamicpricerule_detail(request, pk):
    rule = ecommerce_object(
        request,
        DynamicPriceRule,
        pk,
        select_related=("category", "product", "variant"),
    )
    context = {
        "rule": rule,
    }
    return render(request, "ecommerce/pricingpromotion/dynamicpricerule/detail.html", context)


@login_required
def dynamicpricerule_create(request):
    if request.method == "POST":
        form = DynamicPriceRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            rule.save()
            write_audit_log(
                request.user,
                rule,
                "create",
                {"name": rule.name, "rule_type": rule.rule_type},
            )
            messages.success(request, f"Dynamic price rule '{rule.name}' created successfully.")
            return redirect("ecommerce:dynamicpricerule_detail", pk=rule.pk)
    else:
        form = DynamicPriceRuleForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/pricingpromotion/dynamicpricerule/form.html", context)


@login_required
def dynamicpricerule_edit(request, pk):
    rule = ecommerce_object(
        request,
        DynamicPriceRule,
        pk,
        select_related=("category", "product", "variant"),
    )
    if request.method == "POST":
        form = DynamicPriceRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            rule = form.save()
            write_audit_log(
                request.user,
                rule,
                "update",
                {"name": rule.name, "rule_type": rule.rule_type},
            )
            messages.success(request, f"Dynamic price rule '{rule.name}' updated successfully.")
            return redirect("ecommerce:dynamicpricerule_detail", pk=rule.pk)
    else:
        form = DynamicPriceRuleForm(instance=rule, tenant=request.tenant)

    context = {
        "form": form,
        "rule": rule,
        "is_edit": True,
    }
    return render(request, "ecommerce/pricingpromotion/dynamicpricerule/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def dynamicpricerule_delete(request, pk):
    rule = ecommerce_object(request, DynamicPriceRule, pk)
    name = rule.name
    number = rule.number
    rule.delete()
    write_audit_log(
        request.user,
        rule,
        "delete",
        {"name": name, "number": number},
    )
    messages.success(request, f"Dynamic price rule '{name}' ({number}) was deleted.")
    return redirect("ecommerce:dynamicpricerule_list")
