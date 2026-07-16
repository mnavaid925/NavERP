"""HRM 3.19 Performance Review — Reviewcycle views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PerformanceReview._helpers import _visible_reviews_q
from apps.hrm.models import (
    ReviewCycle,
)
from apps.hrm.forms import (
    ReviewCycleForm,
)
from apps.hrm.views.PerformanceReview._helpers import _visible_reviews_q


# ---------------------------------------------------------------- ReviewCycle (3.19.1 Review Cycles)
@login_required
def reviewcycle_list(request):
    return crud_list(
        request,
        # Explicit order_by — the Count() GROUP BY otherwise drops Meta.ordering (paginator warning).
        ReviewCycle.objects.filter(tenant=request.tenant).select_related("goal_period")
        .annotate(num_reviews=Count("reviews")).order_by("-self_review_start", "name"),
        "hrm/performance/reviewcycle/list.html",
        search_fields=("name",),
        filters=[("status", "status", False), ("cycle_type", "cycle_type", False)],
        extra_context={
            "status_choices": ReviewCycle.STATUS_CHOICES,
            "cycle_type_choices": ReviewCycle.CYCLE_TYPE_CHOICES,
        },
    )


@login_required
def reviewcycle_create(request):
    return crud_create(request, form_class=ReviewCycleForm,
                       template="hrm/performance/reviewcycle/form.html",
                       success_url="hrm:reviewcycle_list")


@login_required
def reviewcycle_detail(request, pk):
    obj = get_object_or_404(
        ReviewCycle.objects.select_related("goal_period"), pk=pk, tenant=request.tenant)
    reviews_qs = (obj.reviews.select_related("subject__party", "reviewer__party", "template")
                  .prefetch_related("ratings"))  # effective_rating reads ratings — avoid per-row N+1
    # Confidentiality: a non-admin sees only reviews they're the subject or reviewer of (not the
    # whole tenant's roster of who-is-rated-what). Admins see the full cycle.
    vq = _visible_reviews_q(request)
    if vq is not None:
        reviews_qs = reviews_qs.filter(vq)
    reviews = list(reviews_qs.order_by("review_type", "subject__party__name"))
    # Phase-progress summary (single pass over the already-fetched reviews — no extra queries).
    phase_counts = {"draft": 0, "submitted": 0, "shared": 0, "acknowledged": 0}
    for r in reviews:
        phase_counts[r.status] = phase_counts.get(r.status, 0) + 1
    # Next phase for the Advance button.
    order = ReviewCycle.PHASE_ORDER
    idx = order.index(obj.status) if obj.status in order else 0
    next_phase = order[idx + 1] if idx + 1 < len(order) else None
    next_phase_label = dict(ReviewCycle.STATUS_CHOICES).get(next_phase) if next_phase else None
    return render(request, "hrm/performance/reviewcycle/detail.html", {
        "obj": obj,
        "reviews": reviews,
        "phase_counts": phase_counts,
        "next_phase_label": next_phase_label,
    })


@login_required
def reviewcycle_edit(request, pk):
    return crud_edit(request, model=ReviewCycle, pk=pk, form_class=ReviewCycleForm,
                     template="hrm/performance/reviewcycle/form.html",
                     success_url="hrm:reviewcycle_list")


@login_required
@require_POST
def reviewcycle_delete(request, pk):
    obj = get_object_or_404(ReviewCycle, pk=pk, tenant=request.tenant)
    # cycle is PROTECT on PerformanceReview — pre-check for a friendly message.
    if obj.reviews.exists():
        messages.error(request, "This review cycle has reviews and cannot be deleted.")
        return redirect("hrm:reviewcycle_detail", pk=obj.pk)
    return crud_delete(request, model=ReviewCycle, pk=pk, success_url="hrm:reviewcycle_list")


@tenant_admin_required
@require_POST
def reviewcycle_advance_phase(request, pk):
    obj = get_object_or_404(ReviewCycle, pk=pk, tenant=request.tenant)
    order = ReviewCycle.PHASE_ORDER
    idx = order.index(obj.status) if obj.status in order else 0
    if idx + 1 < len(order):
        obj.status = order[idx + 1]
        obj.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "advance_phase", "to": obj.status})
        messages.success(request, f"Cycle '{obj.name}' advanced to {obj.get_status_display()}.")
    else:
        messages.error(request, "This cycle is already closed.")
    return redirect("hrm:reviewcycle_detail", pk=obj.pk)
