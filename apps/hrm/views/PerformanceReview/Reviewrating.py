"""HRM 3.19 Performance Review — Reviewrating views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PerformanceReview._helpers import _can_edit_review, _can_view_review
from apps.hrm.models import (
    PerformanceReview,
    ReviewRating,
)
from apps.hrm.forms import (
    ReviewRatingForm,
)
from apps.hrm.views.PerformanceReview._helpers import _can_edit_review, _can_view_review


# ------------------------------------------------------- ReviewRating (3.19.3 per-competency lines)
@login_required
def reviewrating_create(request, review_pk):
    review = get_object_or_404(PerformanceReview, pk=review_pk, tenant=request.tenant)
    if not _can_edit_review(request, review):
        messages.error(request, "Ratings can only be changed on a draft review, by the reviewer or a tenant admin.")
        return redirect("hrm:performancereview_detail", pk=review.pk)
    if request.method == "POST":
        form = ReviewRatingForm(request.POST,
                                instance=ReviewRating(tenant=request.tenant, review=review),
                                tenant=request.tenant)
        if form.is_valid():
            try:
                with transaction.atomic():
                    rating = form.save()
                write_audit_log(request.user, rating, "create")
                messages.success(request, "Rating added.")
            except IntegrityError:
                messages.error(request, "Could not add that rating.")
            return redirect("hrm:performancereview_detail", pk=review.pk)
    else:
        sibling_count = review.ratings.count()
        default_weight = (Decimal("100") / (sibling_count + 1)).quantize(Decimal("0.01"))
        form = ReviewRatingForm(instance=ReviewRating(tenant=request.tenant, review=review),
                                initial={"weight": default_weight}, tenant=request.tenant)
    return render(request, "hrm/performance/reviewrating/form.html", {
        "form": form, "is_edit": False, "review": review})


@login_required
def reviewrating_detail(request, pk):
    rating = get_object_or_404(
        ReviewRating.objects.select_related("review__subject__party", "review__reviewer__party"),
        pk=pk, tenant=request.tenant)
    review = rating.review
    # Confidentiality: a rating is viewable only by the review's subject, reviewer, or a tenant admin.
    if not _can_view_review(request, review):
        raise PermissionDenied("You do not have access to this rating.")
    return render(request, "hrm/performance/reviewrating/detail.html", {
        "obj": rating, "review": review, "can_edit": _can_edit_review(request, review)})


@login_required
def reviewrating_edit(request, pk):
    rating = get_object_or_404(ReviewRating.objects.select_related("review"), pk=pk, tenant=request.tenant)
    review = rating.review
    if not _can_edit_review(request, review):
        messages.error(request, "Ratings can only be changed on a draft review, by the reviewer or a tenant admin.")
        return redirect("hrm:performancereview_detail", pk=review.pk)
    if request.method == "POST":
        form = ReviewRatingForm(request.POST, instance=rating, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, rating, "update")
            messages.success(request, "Rating updated.")
            return redirect("hrm:performancereview_detail", pk=review.pk)
    else:
        form = ReviewRatingForm(instance=rating, tenant=request.tenant)
    return render(request, "hrm/performance/reviewrating/form.html", {
        "form": form, "is_edit": True, "obj": rating, "review": review})


@login_required
@require_POST
def reviewrating_delete(request, pk):
    rating = get_object_or_404(ReviewRating.objects.select_related("review"), pk=pk, tenant=request.tenant)
    review = rating.review
    if not _can_edit_review(request, review):
        messages.error(request, "Ratings can only be changed on a draft review, by the reviewer or a tenant admin.")
        return redirect("hrm:performancereview_detail", pk=review.pk)
    write_audit_log(request.user, rating, "delete")
    rating.delete()
    messages.success(request, "Rating deleted.")
    return redirect("hrm:performancereview_detail", pk=review.pk)
