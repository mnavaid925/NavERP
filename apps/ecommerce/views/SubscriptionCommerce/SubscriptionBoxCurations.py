from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.SubscriptionCommerce.SubscriptionBoxCurations import SubscriptionBoxCurationForm
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionBoxCurations import SubscriptionBoxCuration
from apps.ecommerce.models.SubscriptionCommerce.SubscriptionPlans import SubscriptionPlan
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def subscriptionboxcuration_list(request):
    qs = ecommerce_scope(SubscriptionBoxCuration.objects.all(), request).select_related(
        "plan", "primary_product"
    )

    query = request.GET.get("q", "").strip()
    plan_id = request.GET.get("plan", "").strip()
    status = request.GET.get("status", "").strip()

    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(name__icontains=query)
            | Q(code__icontains=query)
            | Q(cycle_identifier__icontains=query)
            | Q(theme_title__icontains=query)
            | Q(preference_tag__icontains=query)
        )

    if plan_id and plan_id.isdigit():
        qs = qs.filter(plan_id=int(plan_id))

    if status in ("1", "true", "True", "active"):
        qs = qs.filter(is_active=True)
    elif status in ("0", "false", "False", "inactive"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    plans = ecommerce_scope(SubscriptionPlan.objects.all(), request).order_by("name")

    context = {
        "curations": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "plans": plans,
        "selected_plan": plan_id,
        "selected_status": status,
        "query": query,
        "q": query,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionboxcuration/list.html", context)


@login_required
def subscriptionboxcuration_detail(request, pk):
    curation = ecommerce_object(request, SubscriptionBoxCuration, pk)

    context = {
        "curation": curation,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionboxcuration/detail.html", context)


@login_required
@tenant_admin_required
def subscriptionboxcuration_create(request):
    if request.method == "POST":
        form = SubscriptionBoxCurationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            curation = form.save(commit=False)
            curation.tenant = request.tenant
            curation.save()
            write_audit_log(
                request.user,
                curation,
                "create",
                {"name": curation.name, "number": curation.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Box curation '{curation.name}' created.")
            return redirect("ecommerce:subscriptionboxcuration_detail", pk=curation.pk)
    else:
        form = SubscriptionBoxCurationForm(tenant=request.tenant)

    context = {
        "form": form,
        "curation": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionboxcuration/form.html", context)


@login_required
@tenant_admin_required
def subscriptionboxcuration_edit(request, pk):
    curation = ecommerce_object(request, SubscriptionBoxCuration, pk)
    if request.method == "POST":
        form = SubscriptionBoxCurationForm(request.POST, instance=curation, tenant=request.tenant)
        if form.is_valid():
            curation = form.save()
            write_audit_log(
                request.user,
                curation,
                "update",
                {"name": curation.name, "number": curation.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Box curation '{curation.name}' updated.")
            return redirect("ecommerce:subscriptionboxcuration_detail", pk=curation.pk)
    else:
        form = SubscriptionBoxCurationForm(instance=curation, tenant=request.tenant)

    context = {
        "form": form,
        "curation": curation,
        "is_edit": True,
    }
    return render(request, "ecommerce/subscriptioncommerce/subscriptionboxcuration/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def subscriptionboxcuration_delete(request, pk):
    curation = ecommerce_object(request, SubscriptionBoxCuration, pk)
    name = curation.name
    number = curation.number
    curation.delete()
    write_audit_log(
        request.user,
        curation,
        "delete",
        {"name": name, "number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Box curation '{name}' ({number}) deleted.")
    return redirect("ecommerce:subscriptionboxcuration_list")
