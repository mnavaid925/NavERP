from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.SubscriptionCommerce.CustomerSubscriptions import CustomerSubscriptionForm
from apps.ecommerce.models.SubscriptionCommerce.CustomerSubscriptions import CustomerSubscription
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlan
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def customersubscription_list(request):
    qs = ecommerce_scope(CustomerSubscription.objects.all(), request).select_related(
        "customer_profile__customer", "customer_profile__user", "plan", "product", "variant"
    )

    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    plan_id = request.GET.get("plan", "").strip()

    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(customer_profile__customer__name__icontains=query)
            | Q(customer_profile__number__icontains=query)
            | Q(product__name__icontains=query)
            | Q(shipping_address_line__icontains=query)
        )

    if status:
        qs = qs.filter(status=status)

    if plan_id and plan_id.isdigit():
        qs = qs.filter(plan_id=int(plan_id))

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    tenant_plans = ecommerce_scope(SubscriptionPlan.objects.all(), request).filter(is_active=True).order_by("name")

    context = {
        "subscriptions": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "status_choices": CustomerSubscription.STATUS_CHOICES,
        "plans": tenant_plans,
        "selected_status": status,
        "selected_plan": plan_id,
        "query": query,
        "q": query,
    }
    return render(request, "ecommerce/subscriptioncommerce/customersubscription/list.html", context)


@login_required
def customersubscription_detail(request, pk):
    subscription = ecommerce_object(request, CustomerSubscription, pk)
    retention_actions = subscription.retention_actions.all().order_by("-created_at")[:10]

    context = {
        "subscription": subscription,
        "retention_actions": retention_actions,
    }
    return render(request, "ecommerce/subscriptioncommerce/customersubscription/detail.html", context)


@login_required
@tenant_admin_required
def customersubscription_create(request):
    if request.method == "POST":
        form = CustomerSubscriptionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            subscription = form.save(commit=False)
            subscription.tenant = request.tenant
            subscription.save()
            write_audit_log(
                request.user,
                subscription,
                "create",
                {"customer": str(subscription.customer_profile), "number": subscription.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Customer subscription '{subscription.number}' created.")
            return redirect("ecommerce:customersubscription_detail", pk=subscription.pk)
    else:
        form = CustomerSubscriptionForm(tenant=request.tenant)

    context = {
        "form": form,
        "subscription": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/subscriptioncommerce/customersubscription/form.html", context)


@login_required
@tenant_admin_required
def customersubscription_edit(request, pk):
    subscription = ecommerce_object(request, CustomerSubscription, pk)
    if request.method == "POST":
        form = CustomerSubscriptionForm(request.POST, instance=subscription, tenant=request.tenant)
        if form.is_valid():
            subscription = form.save()
            write_audit_log(
                request.user,
                subscription,
                "update",
                {"customer": str(subscription.customer_profile), "number": subscription.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Subscription '{subscription.number}' updated.")
            return redirect("ecommerce:customersubscription_detail", pk=subscription.pk)
    else:
        form = CustomerSubscriptionForm(instance=subscription, tenant=request.tenant)

    context = {
        "form": form,
        "subscription": subscription,
        "is_edit": True,
    }
    return render(request, "ecommerce/subscriptioncommerce/customersubscription/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def customersubscription_delete(request, pk):
    subscription = ecommerce_object(request, CustomerSubscription, pk)
    number = subscription.number
    customer = str(subscription.customer_profile)
    subscription.delete()
    write_audit_log(
        request.user,
        subscription,
        "delete",
        {"customer": customer, "number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Subscription '{number}' deleted.")
    return redirect("ecommerce:customersubscription_list")
