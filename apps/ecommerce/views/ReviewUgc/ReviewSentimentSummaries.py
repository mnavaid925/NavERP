from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ReviewUgc.ReviewSentimentSummaries import ReviewSentimentSummaryForm
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ReviewUgc.ProductReviews import ProductReview
from apps.ecommerce.models.ReviewUgc.ReviewSentimentSummaries import ReviewSentimentSummary
from apps.ecommerce.views._common import ecommerce_object


@login_required
def reviewsentimentsummary_list(request):
    qs = ReviewSentimentSummary.objects.filter(tenant=request.tenant).select_related("product")

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(product__name__icontains=query)
            | Q(number__icontains=query)
            | Q(improvement_recommendation__icontains=query)
        )

    selected_product = request.GET.get("product", "").strip()
    if selected_product and selected_product.isdigit():
        qs = qs.filter(product_id=int(selected_product))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    products = CatalogProduct.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "summaries": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "products": products,
        "selected_product": selected_product,
        "query": query,
    }
    return render(
        request,
        "ecommerce/review_ugc/sentiment_summary/list.html",
        context,
    )


@login_required
def reviewsentimentsummary_detail(request, pk):
    summary = ecommerce_object(
        request,
        ReviewSentimentSummary,
        pk,
        select_related=("product",),
    )
    recent_reviews = ProductReview.objects.filter(
        tenant=request.tenant, product=summary.product, status="approved"
    ).order_by("-is_featured", "-created_at")[:10]

    return render(
        request,
        "ecommerce/review_ugc/sentiment_summary/detail.html",
        {
            "summary": summary,
            "recent_reviews": recent_reviews,
        },
    )


@login_required
def reviewsentimentsummary_create(request):
    if request.method == "POST":
        form = ReviewSentimentSummaryForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            summary = form.save(commit=False)
            summary.tenant = request.tenant
            summary.save()
            summary.recalculate()
            write_audit_log(
                request.user,
                summary,
                "create",
                {"number": summary.number, "product": summary.product.name},
                tenant=request.tenant,
            )
            messages.success(request, f"Review scorecard for {summary.product.name} initialized.")
            return redirect("ecommerce:reviewsentimentsummary_detail", pk=summary.pk)
    else:
        form = ReviewSentimentSummaryForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/review_ugc/sentiment_summary/form.html",
        {"form": form, "summary": None},
    )


@login_required
def reviewsentimentsummary_edit(request, pk):
    summary = ecommerce_object(request, ReviewSentimentSummary, pk)
    if request.method == "POST":
        form = ReviewSentimentSummaryForm(request.POST, instance=summary, tenant=request.tenant)
        if form.is_valid():
            summary = form.save()
            write_audit_log(
                request.user,
                summary,
                "update",
                {"improvement_recommendation": summary.improvement_recommendation[:100]},
                tenant=request.tenant,
            )
            messages.success(request, f"Review scorecard {summary.number} updated.")
            return redirect("ecommerce:reviewsentimentsummary_detail", pk=summary.pk)
    else:
        form = ReviewSentimentSummaryForm(instance=summary, tenant=request.tenant)

    return render(
        request,
        "ecommerce/review_ugc/sentiment_summary/form.html",
        {"form": form, "summary": summary},
    )


@login_required
@tenant_admin_required
@require_POST
def reviewsentimentsummary_delete(request, pk):
    summary = ecommerce_object(request, ReviewSentimentSummary, pk)
    number = summary.number
    pk_val = summary.pk
    summary.delete()
    write_audit_log(
        request.user,
        summary,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Review scorecard {number} deleted.")
    return redirect("ecommerce:reviewsentimentsummary_list")


@login_required
@tenant_admin_required
@require_POST
def reviewsentimentsummary_recalculate(request, pk):
    summary = ecommerce_object(request, ReviewSentimentSummary, pk)
    summary.recalculate()
    write_audit_log(
        request.user,
        summary,
        "recalc",
        {"action": "recalculate", "average_rating": str(summary.average_rating), "total_reviews": summary.total_reviews},
        tenant=request.tenant,
    )
    messages.success(request, f"Scorecard metrics recalculated: {summary.average_rating}★ across {summary.total_reviews} reviews.")
    return redirect("ecommerce:reviewsentimentsummary_detail", pk=summary.pk)
