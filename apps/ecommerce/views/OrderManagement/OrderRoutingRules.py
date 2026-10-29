from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.OrderManagement.OrderRoutingRules import OrderRoutingRuleForm
from apps.ecommerce.models.OrderManagement.OrderRoutingRules import OrderRoutingRule
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def orderroutingrule_list(request):
    qs = ecommerce_scope(
        OrderRoutingRule.objects.select_related("preferred_fulfillment_center"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    strategy_filter = request.GET.get("strategy", "").strip()
    active_filter = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(destination_country__icontains=search_query)
            | Q(destination_region__icontains=search_query)
        )

    if strategy_filter:
        qs = qs.filter(strategy=strategy_filter)

    if active_filter in ("1", "true"):
        qs = qs.filter(is_active=True)
    elif active_filter in ("0", "false"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "rules": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "current_q": search_query,
        "strategy_choices": OrderRoutingRule.ROUTING_STRATEGY_CHOICES,
        "current_strategy": strategy_filter,
        "current_status": active_filter,
    }
    return render(request, "ecommerce/ordermanagement/orderroutingrule/list.html", context)


@login_required
def orderroutingrule_detail(request, pk):
    rule = ecommerce_object(
        request,
        OrderRoutingRule,
        pk,
        select_related=("preferred_fulfillment_center",),
    )
    return render(request, "ecommerce/ordermanagement/orderroutingrule/detail.html", {"rule": rule})


@login_required
def orderroutingrule_create(request):
    if request.method == "POST":
        form = OrderRoutingRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            rule.save()
            write_audit_log(
                request.user,
                rule,
                "create",
                {"name": rule.name, "strategy": rule.strategy, "priority": rule.priority},
            )
            messages.success(request, f"Routing rule '{rule.name}' created successfully.")
            return redirect("ecommerce:orderroutingrule_detail", pk=rule.pk)
    else:
        form = OrderRoutingRuleForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/ordermanagement/orderroutingrule/form.html", context)


@login_required
def orderroutingrule_edit(request, pk):
    rule = ecommerce_object(request, OrderRoutingRule, pk)
    if request.method == "POST":
        form = OrderRoutingRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            rule = form.save()
            write_audit_log(
                request.user,
                rule,
                "update",
                {"name": rule.name, "strategy": rule.strategy, "is_active": rule.is_active},
            )
            messages.success(request, f"Routing rule '{rule.name}' updated successfully.")
            return redirect("ecommerce:orderroutingrule_detail", pk=rule.pk)
    else:
        form = OrderRoutingRuleForm(instance=rule, tenant=request.tenant)

    context = {
        "form": form,
        "rule": rule,
        "is_edit": True,
    }
    return render(request, "ecommerce/ordermanagement/orderroutingrule/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def orderroutingrule_delete(request, pk):
    rule = ecommerce_object(request, OrderRoutingRule, pk)
    rule_name = rule.name
    rule.delete()
    write_audit_log(
        request.user,
        None,
        "delete",
        {"name": rule_name, "entity": "OrderRoutingRule"},
    )
    messages.success(request, f"Routing rule '{rule_name}' was deleted.")
    return redirect("ecommerce:orderroutingrule_list")
