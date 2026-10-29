from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.PricingPromotion.CompetitorPriceMonitors import CompetitorPriceMonitorForm
from apps.ecommerce.models.PricingPromotion.CompetitorPriceMonitors import CompetitorPriceMonitor
from apps.ecommerce.models.ProductCatalog.ProductVariants import ProductVariant
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def competitorpricemonitor_list(request):
    qs = ecommerce_scope(
        CompetitorPriceMonitor.objects.select_related("product", "variant", "variant__product"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    strategy_filter = request.GET.get("strategy", "").strip()
    status_filter = request.GET.get("status", "").strip()

    if search_query:
        qs = qs.filter(
            Q(competitor_name__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(variant__sku__icontains=search_query)
            | Q(product__name__icontains=search_query)
        )

    if strategy_filter:
        qs = qs.filter(match_strategy=strategy_filter)

    if status_filter:
        qs = qs.filter(status=status_filter)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    variants = ProductVariant.objects.filter(tenant=request.tenant).select_related("product")

    context = {
        "monitors": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "current_q": search_query,
        "strategy_filter": strategy_filter,
        "current_strategy": strategy_filter,
        "status_filter": status_filter,
        "current_status": status_filter,
        "strategy_choices": CompetitorPriceMonitor.STRATEGY_CHOICES,
        "status_choices": CompetitorPriceMonitor.STATUS_CHOICES,
        "variants": variants,
    }
    return render(request, "ecommerce/pricingpromotion/competitorpricemonitor/list.html", context)


@login_required
def competitorpricemonitor_detail(request, pk):
    monitor = ecommerce_object(
        request,
        CompetitorPriceMonitor,
        pk,
        select_related=("product", "variant", "variant__product"),
    )
    context = {
        "monitor": monitor,
    }
    return render(request, "ecommerce/pricingpromotion/competitorpricemonitor/detail.html", context)


@login_required
def competitorpricemonitor_create(request):
    if request.method == "POST":
        form = CompetitorPriceMonitorForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            monitor = form.save(commit=False)
            monitor.tenant = request.tenant
            monitor.save()
            write_audit_log(
                request.tenant,
                request.user,
                "CREATE",
                "CompetitorPriceMonitor",
                monitor.pk,
                f"Created competitor price monitor for {monitor.competitor_name} - {monitor.variant.sku}",
            )
            messages.success(request, f"Competitor price monitor for '{monitor.competitor_name}' created.")
            return redirect("ecommerce:competitorpricemonitor_detail", pk=monitor.pk)
    else:
        form = CompetitorPriceMonitorForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "ecommerce/pricingpromotion/competitorpricemonitor/form.html", context)


@login_required
def competitorpricemonitor_edit(request, pk):
    monitor = ecommerce_object(
        request,
        CompetitorPriceMonitor,
        pk,
        select_related=("product", "variant"),
    )
    if request.method == "POST":
        form = CompetitorPriceMonitorForm(request.POST, instance=monitor, tenant=request.tenant)
        if form.is_valid():
            monitor = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "UPDATE",
                "CompetitorPriceMonitor",
                monitor.pk,
                f"Updated competitor price monitor {monitor.number}",
            )
            messages.success(request, f"Competitor monitor '{monitor.number}' updated successfully.")
            return redirect("ecommerce:competitorpricemonitor_detail", pk=monitor.pk)
    else:
        form = CompetitorPriceMonitorForm(instance=monitor, tenant=request.tenant)

    context = {
        "form": form,
        "monitor": monitor,
        "is_edit": True,
    }
    return render(request, "ecommerce/pricingpromotion/competitorpricemonitor/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def competitorpricemonitor_delete(request, pk):
    monitor = ecommerce_object(request, CompetitorPriceMonitor, pk)
    comp = monitor.competitor_name
    number = monitor.number
    monitor.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "DELETE",
        "CompetitorPriceMonitor",
        pk,
        f"Deleted competitor monitor {number} ({comp})",
    )
    messages.success(request, f"Competitor monitor '{number}' was deleted.")
    return redirect("ecommerce:competitorpricemonitor_list")


@login_required
@tenant_admin_required
@require_POST
def competitorpricemonitor_sync(request, pk):
    monitor = ecommerce_object(request, CompetitorPriceMonitor, pk, select_related=("variant",))
    monitor.last_scraped_at = timezone.now()
    if monitor.is_margin_risk:
        monitor.status = "margin_suppressed"
    elif not monitor.is_in_stock:
        monitor.status = "out_of_stock"
    else:
        monitor.status = "active"
    monitor.save()

    write_audit_log(
        request.tenant,
        request.user,
        "UPDATE",
        "CompetitorPriceMonitor",
        monitor.pk,
        f"Synchronized price check for {monitor.competitor_name} - {monitor.variant.sku}",
    )
    messages.success(request, f"Simulated live price scrape completed for {monitor.competitor_name}.")
    return redirect("ecommerce:competitorpricemonitor_detail", pk=monitor.pk)
