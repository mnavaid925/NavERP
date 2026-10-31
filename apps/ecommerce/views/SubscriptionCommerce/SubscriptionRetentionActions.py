from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.SubscriptionCommerce.SubscriptionRetentionActions import SubscriptionRetentionActionForm
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionRetentionActions import SubscriptionRetentionAction
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def subscriptionretentionaction_list(request):
    qs = ecommerce_scope(SubscriptionRetentionAction.objects.all(), request).select_related(
        "subscription", "customer_profile__customer"
    )

    query = request.GET.get("q", "").strip()
    trigger_type = request.GET.get("trigger_type", "").strip()
    outcome = request.GET.get("outcome", "").strip()

    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(subscription__number__icontains=query)
            | Q(customer_profile__customer__name__icontains=query)
            | Q(customer_profile__number__icontains=query)
            | Q(notes__icontains=query)
        )

    if trigger_type:
        qs = qs.filter(trigger_type=trigger_type)

    if outcome:
        qs = qs.filter(outcome=outcome)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "retention_actions": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "trigger_type_choices": SubscriptionRetentionAction.TRIGGER_TYPE_CHOICES,
        "outcome_choices": SubscriptionRetentionAction.OUTCOME_CHOICES,
        "reason_choices": SubscriptionRetentionAction.REASON_CHOICES,
        "selected_trigger": trigger_type,
        "selected_outcome": outcome,
        "query": query,
        "q": query,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionretentionaction/list.html", context)


@login_required
def subscriptionretentionaction_detail(request, pk):
    action = ecommerce_object(request, SubscriptionRetentionAction, pk)

    context = {
        "retention_action": action,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionretentionaction/detail.html", context)


@login_required
@tenant_admin_required
def subscriptionretentionaction_create(request):
    if request.method == "POST":
        form = SubscriptionRetentionActionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            action = form.save(commit=False)
            action.tenant = request.tenant
            action.save()
            write_audit_log(
                request.user,
                action,
                "create",
                {"subscription": str(action.subscription), "number": action.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Retention record '{action.number}' logged.")
            return redirect("ecommerce:subscriptionretentionaction_detail", pk=action.pk)
    else:
        form = SubscriptionRetentionActionForm(tenant=request.tenant)

    context = {
        "form": form,
        "retention_action": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionretentionaction/form.html", context)


@login_required
@tenant_admin_required
def subscriptionretentionaction_edit(request, pk):
    action = ecommerce_object(request, SubscriptionRetentionAction, pk)
    if request.method == "POST":
        form = SubscriptionRetentionActionForm(request.POST, instance=action, tenant=request.tenant)
        if form.is_valid():
            action = form.save()
            write_audit_log(
                request.user,
                action,
                "update",
                {"subscription": str(action.subscription), "number": action.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Retention record '{action.number}' updated.")
            return redirect("ecommerce:subscriptionretentionaction_detail", pk=action.pk)
    else:
        form = SubscriptionRetentionActionForm(instance=action, tenant=request.tenant)

    context = {
        "form": form,
        "retention_action": action,
        "is_edit": True,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionretentionaction/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def subscriptionretentionaction_delete(request, pk):
    action = ecommerce_object(request, SubscriptionRetentionAction, pk)
    number = action.number
    action.delete()
    write_audit_log(
        request.user,
        action,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Retention action '{number}' deleted.")
    return redirect("ecommerce:subscriptionretentionaction_list")
