from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.AnalyticsBi.ProductMerchandisingMetrics import ProductMerchandisingMetricForm
from apps.ecommerce.models.AnalyticsBi.ProductMerchandisingMetrics import ProductMerchandisingMetric
from apps.ecommerce.views._common import ecommerce_object


@login_required
def productmerchandisingmetric_list(request):
    qs = ProductMerchandisingMetric.objects.filter(tenant=request.tenant).select_related(
        "product", "variant"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(product__name__icontains=query)
            | Q(variant__sku__icontains=query)
        )

    selected_velocity_tier = request.GET.get("velocity_tier", "").strip()
    if selected_velocity_tier:
        qs = qs.filter(velocity_tier=selected_velocity_tier)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "ecommerce/analytics_bi/product_merchandising_metric/list.html",
        {
            "metrics": page_obj,
            "velocity_tier_choices": ProductMerchandisingMetric.VELOCITY_TIER_CHOICES,
            "selected_velocity_tier": selected_velocity_tier,
            "query": query,
            "page_obj": page_obj,
            "paginator": paginator,
        },
    )


@login_required
def productmerchandisingmetric_detail(request, pk):
    metric = ecommerce_object(
        request,
        ProductMerchandisingMetric,
        pk,
        select_related=("product", "variant"),
    )
    return render(
        request,
        "ecommerce/analytics_bi/product_merchandising_metric/detail.html",
        {"metric": metric},
    )


@login_required
def productmerchandisingmetric_create(request):
    if request.tenant is None:
        messages.error(request, "Select or switch to a workspace first.")
        return redirect("ecommerce:productmerchandisingmetric_list")
    if request.method == "POST":
        form = ProductMerchandisingMetricForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            metric = form.save(commit=False)
            metric.tenant = request.tenant
            metric.recalculate_metrics()
            metric.save()
            write_audit_log(
                request.user,
                metric,
                "create",
                {"number": metric.number, "product": metric.product.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Merchandising metric {metric.number} created successfully.")
            return redirect("ecommerce:productmerchandisingmetric_detail", pk=metric.pk)
    else:
        form = ProductMerchandisingMetricForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/analytics_bi/product_merchandising_metric/form.html",
        {"form": form, "metric": None},
    )


@login_required
def productmerchandisingmetric_edit(request, pk):
    metric = ecommerce_object(
        request,
        ProductMerchandisingMetric,
        pk,
        select_related=("product", "variant"),
    )
    if request.method == "POST":
        form = ProductMerchandisingMetricForm(
            request.POST, instance=metric, tenant=request.tenant
        )
        if form.is_valid():
            m = form.save(commit=False)
            submitted_tier = form.cleaned_data.get("velocity_tier")
            m.recalculate_metrics()
            if submitted_tier:
                m.velocity_tier = submitted_tier
            m.save()
            write_audit_log(
                request.user,
                metric,
                "update",
                {"number": metric.number},
                tenant=request.tenant,
            )
            messages.success(request, f"Merchandising metric {metric.number} updated successfully.")
            return redirect("ecommerce:productmerchandisingmetric_detail", pk=metric.pk)
    else:
        form = ProductMerchandisingMetricForm(instance=metric, tenant=request.tenant)

    return render(
        request,
        "ecommerce/analytics_bi/product_merchandising_metric/form.html",
        {"form": form, "metric": metric},
    )


@require_POST
@login_required
@tenant_admin_required
def productmerchandisingmetric_delete(request, pk):
    metric = ecommerce_object(request, ProductMerchandisingMetric, pk)
    number = metric.number
    write_audit_log(
        request.user,
        metric,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    metric.delete()
    messages.success(request, f"Merchandising metric {number} was deleted.")
    return redirect("ecommerce:productmerchandisingmetric_list")


@require_POST
@login_required
@tenant_admin_required
def productmerchandisingmetric_reclassify(request):
    """Reclassifies velocity tiers for all merchandising metrics."""
    if request.tenant is None:
        messages.error(request, "Select or switch to a workspace first.")
        return redirect("ecommerce:productmerchandisingmetric_list")
    metrics = list(ProductMerchandisingMetric.objects.filter(tenant=request.tenant))
    with transaction.atomic():
        for m in metrics:
            m.recalculate_metrics()
        ProductMerchandisingMetric.objects.bulk_update(
            metrics,
            ["velocity_tier", "gross_margin_pct", "return_rate_pct", "conversion_rate_pct"],
            batch_size=500,
        )
    count = len(metrics)

    write_audit_log(
        request.user,
        None,
        "reclass",
        f"Reclassified {count} products",
        tenant=request.tenant,
    )
    messages.success(request, f"Reclassified velocity tiers and margins across {count} merchandise records.")
    return redirect("ecommerce:productmerchandisingmetric_list")
