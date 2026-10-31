from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ReviewUgc.ProductReviews import ProductReviewForm, ProductReviewModerationForm
from apps.ecommerce.models.ProductCatalog.CatalogProducts import CatalogProduct
from apps.ecommerce.models.ReviewUgc.ProductReviews import ProductReview
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def productreview_list(request):
    qs = ProductReview.objects.filter(tenant=request.tenant).select_related(
        "product", "variant", "customer", "order"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(body__icontains=query)
            | Q(reviewer_name__icontains=query)
            | Q(number__icontains=query)
            | Q(product__name__icontains=query)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_rating = request.GET.get("rating", "").strip()
    if selected_rating and selected_rating.isdigit():
        qs = qs.filter(rating=int(selected_rating))

    selected_sentiment = request.GET.get("sentiment", "").strip()
    if selected_sentiment:
        qs = qs.filter(sentiment=selected_sentiment)

    selected_product = request.GET.get("product", "").strip()
    if selected_product and selected_product.isdigit():
        qs = qs.filter(product_id=int(selected_product))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    products = CatalogProduct.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "reviews": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "status_choices": ProductReview.STATUS_CHOICES,
        "rating_choices": ProductReview.RATING_CHOICES,
        "sentiment_choices": ProductReview.SENTIMENT_CHOICES,
        "products": products,
        "selected_status": selected_status,
        "selected_rating": selected_rating,
        "selected_sentiment": selected_sentiment,
        "selected_product": selected_product,
        "query": query,
    }
    return render(request, "ecommerce/review_ugc/product_review/list.html", context)


@login_required
def productreview_detail(request, pk):
    review = ecommerce_object(
        request,
        ProductReview,
        pk,
        select_related=("product", "variant", "customer", "order", "moderated_by"),
    )
    return render(request, "ecommerce/review_ugc/product_review/detail.html", {"review": review})


@login_required
def productreview_create(request):
    if request.method == "POST":
        form = ProductReviewForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            review = form.save(commit=False)
            review.tenant = request.tenant
            review.save()
            write_audit_log(
                request.user,
                review,
                "create",
                {"number": review.number, "product": review.product.name, "rating": review.rating},
                tenant=request.tenant,
            )
            messages.success(request, f"Review {review.number} submitted successfully.")
            return redirect("ecommerce:productreview_detail", pk=review.pk)
    else:
        form = ProductReviewForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/review_ugc/product_review/form.html",
        {"form": form, "review": None},
    )


@login_required
def productreview_edit(request, pk):
    review = ecommerce_object(request, ProductReview, pk)
    if request.method == "POST":
        form = ProductReviewForm(request.POST, instance=review, tenant=request.tenant)
        if form.is_valid():
            review = form.save()
            write_audit_log(
                request.user,
                review,
                "update",
                {"status": review.status, "rating": review.rating},
                tenant=request.tenant,
            )
            messages.success(request, f"Review {review.number} updated successfully.")
            return redirect("ecommerce:productreview_detail", pk=review.pk)
    else:
        form = ProductReviewForm(instance=review, tenant=request.tenant)

    return render(
        request,
        "ecommerce/review_ugc/product_review/form.html",
        {"form": form, "review": review},
    )


@login_required
@require_POST
def productreview_delete(request, pk):
    review = ecommerce_object(request, ProductReview, pk)
    number = review.number
    review_pk = review.pk
    review.delete()
    write_audit_log(
        request.user,
        review,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    messages.success(request, f"Review {number} deleted.")
    return redirect("ecommerce:productreview_list")


@login_required
def productreview_moderate(request, pk):
    review = ecommerce_object(request, ProductReview, pk)
    if request.method == "POST":
        form = ProductReviewModerationForm(request.POST, instance=review, tenant=request.tenant)
        if form.is_valid():
            review = form.save(commit=False)
            review.moderated_by = request.user
            if review.merchant_response and not review.merchant_response_at:
                review.merchant_response_at = timezone.now()
            review.save()
            write_audit_log(
                request.user,
                review,
                "moderate",
                {"status": review.status, "moderation_note": review.moderation_note},
                tenant=request.tenant,
            )
            messages.success(request, f"Review {review.number} moderation status updated.")
            return redirect("ecommerce:productreview_detail", pk=review.pk)
    else:
        form = ProductReviewModerationForm(instance=review, tenant=request.tenant)

    return render(
        request,
        "ecommerce/review_ugc/product_review/form.html",
        {"form": form, "review": review, "is_moderation": True},
    )
