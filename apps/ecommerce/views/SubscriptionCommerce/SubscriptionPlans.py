from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlanForm
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlan
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def subscriptionplan_list(request):
    qs = ecommerce_scope(SubscriptionPlan.objects.all(), request).select_related("target_product")

    query = request.GET.get("q", "").strip()
    plan_type = request.GET.get("plan_type", "").strip()
    frequency = request.GET.get("frequency", "").strip()
    status = request.GET.get("status", "").strip()

    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(description__icontains=query)
        )

    if plan_type:
        qs = qs.filter(plan_type=plan_type)

    if frequency:
        qs = qs.filter(frequency=frequency)

    if status in ("1", "true", "True", "active"):
        qs = qs.filter(is_active=True)
    elif status in ("0", "false", "False", "inactive"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "plans": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "plan_type_choices": SubscriptionPlan.PLAN_TYPE_CHOICES,
        "frequency_choices": SubscriptionPlan.FREQUENCY_CHOICES,
        "selected_plan_type": plan_type,
        "selected_frequency": frequency,
        "selected_status": status,
        "query": query,
        "q": query,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionplan/list.html", context)


@login_required
def subscriptionplan_detail(request, pk):
    plan = ecommerce_object(request, SubscriptionPlan, pk)
    active_subscriptions = plan.subscriptions.filter(status="active").select_related("customer_profile", "product")[:20]
    active_curations = plan.curations.filter(is_active=True).select_related("primary_product")[:10]

    context = {
        "plan": plan,
        "active_subscriptions": active_subscriptions,
        "active_curations": active_curations,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionplan/detail.html", context)


@login_required
@tenant_admin_required
def subscriptionplan_create(request):
    if request.method == "POST":
        form = SubscriptionPlanForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            plan = form.save(commit=False)
            plan.tenant = request.tenant
            plan.save()
            write_audit_log(
                request.user,
                plan,
                "create",
                {"name": plan.name, "number": plan.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Subscription plan '{plan.name}' created.")
            return redirect("ecommerce:subscriptionplan_detail", pk=plan.pk)
    else:
        form = SubscriptionPlanForm(tenant=request.tenant)

    context = {
        "form": form,
        "plan": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionplan/form.html", context)


@login_required
@tenant_admin_required
def subscriptionplan_edit(request, pk):
    plan = ecommerce_object(request, SubscriptionPlan, pk)
    if request.method == "POST":
        form = SubscriptionPlanForm(request.POST, instance=plan, tenant=request.tenant)
        if form.is_valid():
            plan = form.save()
            write_audit_log(
                request.user,
                plan,
                "update",
                {"name": plan.name, "number": plan.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Subscription plan '{plan.name}' updated.")
            return redirect("ecommerce:subscriptionplan_detail", pk=plan.pk)
    else:
        form = SubscriptionPlanForm(instance=plan, tenant=request.tenant)

    context = {
        "form": form,
        "plan": plan,
        "is_edit": True,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionplan/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def subscriptionplan_delete(request, pk):
    plan = ecommerce_object(request, SubscriptionPlan, pk)
    name = plan.name
    number = plan.number
    plan.delete()
    write_audit_log(
        request.user,
        plan,
        "delete",
        {"name": name, "number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Subscription plan '{name}' ({number}) deleted.")
    return redirect("ecommerce:subscriptionplan_list")
