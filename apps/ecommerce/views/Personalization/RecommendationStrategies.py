from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.Personalization.RecommendationStrategies import RecommendationStrategyForm
from apps.ecommerce.models.Personalization.RecommendationStrategies import RecommendationStrategy
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def recommendationstrategy_list(request):
    qs = ecommerce_scope(RecommendationStrategy.objects.all(), request).select_related(
        "target_segment", "target_category"
    )

    search_query = request.GET.get("q", "").strip()
    algorithm = request.GET.get("algorithm", "").strip()
    placement = request.GET.get("placement", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    if algorithm:
        qs = qs.filter(algorithm=algorithm)

    if placement:
        qs = qs.filter(placement=placement)

    if is_active in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif is_active in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "strategies": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "search_query": search_query,
        "selected_algorithm": algorithm,
        "selected_placement": placement,
        "selected_active": is_active,
        "algorithm_choices": RecommendationStrategy.ALGORITHM_CHOICES,
        "placement_choices": RecommendationStrategy.PLACEMENT_CHOICES,
    }
    return render(request, "ecommerce/personalization/recommendationstrategy/list.html", context)


@login_required
def recommendationstrategy_detail(request, pk):
    strategy = ecommerce_object(request, RecommendationStrategy, pk)
    context = {
        "strategy": strategy,
    }
    return render(request, "ecommerce/personalization/recommendationstrategy/detail.html", context)


@login_required
@tenant_admin_required
def recommendationstrategy_create(request):
    if request.method == "POST":
        form = RecommendationStrategyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            strategy = form.save(commit=False)
            strategy.tenant = request.tenant
            strategy.save()
            write_audit_log(
                request.user,
                strategy,
                "create",
                {"name": strategy.name, "number": strategy.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Recommendation strategy '{strategy.name}' created.")
            return redirect("ecommerce:recommendationstrategy_detail", pk=strategy.pk)
    else:
        form = RecommendationStrategyForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/personalization/recommendationstrategy/form.html", context)


@login_required
@tenant_admin_required
def recommendationstrategy_edit(request, pk):
    strategy = ecommerce_object(request, RecommendationStrategy, pk)
    if request.method == "POST":
        form = RecommendationStrategyForm(request.POST, instance=strategy, tenant=request.tenant)
        if form.is_valid():
            strategy = form.save()
            write_audit_log(
                request.user,
                strategy,
                "update",
                {"name": strategy.name, "number": strategy.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Recommendation strategy '{strategy.name}' updated.")
            return redirect("ecommerce:recommendationstrategy_detail", pk=strategy.pk)
    else:
        form = RecommendationStrategyForm(instance=strategy, tenant=request.tenant)

    context = {
        "form": form,
        "strategy": strategy,
        "is_edit": True,
    }
    return render(request, "ecommerce/personalization/recommendationstrategy/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def recommendationstrategy_delete(request, pk):
    strategy = ecommerce_object(request, RecommendationStrategy, pk)
    name = strategy.name
    number = strategy.number
    strategy.delete()
    write_audit_log(
        request.user,
        strategy,
        "delete",
        {"name": name, "number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Recommendation strategy '{name}' deleted.")
    return redirect("ecommerce:recommendationstrategy_list")


@login_required
@tenant_admin_required
@require_POST
def recommendationstrategy_toggle(request, pk):
    strategy = ecommerce_object(request, RecommendationStrategy, pk)
    strategy.is_active = not strategy.is_active
    strategy.save(update_fields=["is_active", "updated_at"])
    state = "activated" if strategy.is_active else "deactivated"
    write_audit_log(
        request.user,
        strategy,
        "update",
        {"is_active": strategy.is_active, "number": strategy.number},
        tenant=request.tenant,
    )
    messages.success(request, f"Recommendation strategy '{strategy.name}' {state}.")
    return redirect("ecommerce:recommendationstrategy_detail", pk=strategy.pk)
