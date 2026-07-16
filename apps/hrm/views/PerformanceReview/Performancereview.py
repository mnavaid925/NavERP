"""HRM 3.19 Performance Review — Performancereview views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.PerformanceReview._helpers import _can_edit_review, _can_view_review, _is_admin, _is_reviewer, _visible_reviews_q
from apps.hrm.models import (
    EmployeeProfile,
    Objective,
    PerformanceReview,
    ReviewCycle,
)
from apps.hrm.forms import (
    CalibrationForm,
    PerformanceReviewForm,
    ReviewRatingForm,
)
from apps.hrm.views.GoalSetting._helpers import _current_employee_profile
from apps.hrm.views.PerformanceReview._helpers import _can_edit_review, _can_view_review, _is_admin, _is_reviewer, _visible_reviews_q


# ---------------------------------------------- PerformanceReview (3.19.2/3.19.3/3.19.4 the review row)
@login_required
def performancereview_list(request):
    qs = (PerformanceReview.objects.filter(tenant=request.tenant)
          .select_related("cycle", "template", "subject__party", "reviewer__party")
          .prefetch_related("ratings"))
    # Confidentiality: a non-admin sees only reviews they're the subject or reviewer of — the
    # tenant-wide reviews roster (who-is-rated-what) is admin-only.
    profile = _current_employee_profile(request)
    vq = _visible_reviews_q(request)
    if vq is not None:
        qs = qs.filter(vq)
    if request.GET.get("mine") == "1":
        qs = qs.filter(Q(subject=profile) | Q(reviewer=profile)) if profile is not None else qs.none()
    return crud_list(
        request, qs,
        "hrm/performance/performancereview/list.html",
        search_fields=("number", "subject__party__name", "reviewer__party__name"),
        filters=[("cycle", "cycle_id", True), ("review_type", "review_type", False),
                 ("status", "status", False), ("subject", "subject_id", True),
                 ("reviewer", "reviewer_id", True)],
        extra_context={
            "review_type_choices": PerformanceReview.REVIEW_TYPE_CHOICES,
            "status_choices": PerformanceReview.STATUS_CHOICES,
            "cycles": ReviewCycle.objects.filter(tenant=request.tenant).order_by("-self_review_start"),
            "employees": (EmployeeProfile.objects.filter(tenant=request.tenant)
                          .select_related("party").order_by("party__name")),
            "mine": request.GET.get("mine") == "1",
            # For gating the row Edit button to who can actually edit (draft + reviewer/admin).
            "is_admin": _is_admin(request.user),
            "current_profile_id": profile.pk if profile is not None else None,
        },
    )


@login_required
def performancereview_create(request):
    return crud_create(request, form_class=PerformanceReviewForm,
                       template="hrm/performance/performancereview/form.html",
                       success_url="hrm:performancereview_list")


@login_required
def performancereview_detail(request, pk):
    obj = get_object_or_404(
        PerformanceReview.objects.select_related(
            "cycle__goal_period", "template", "subject__party", "reviewer__party", "acknowledged_by__party")
        .prefetch_related("ratings"),
        pk=pk, tenant=request.tenant)
    # Confidentiality: only the subject, the reviewer, or a tenant admin may view a review.
    if not _can_view_review(request, obj):
        raise PermissionDenied("You do not have access to this review.")
    ratings = list(obj.ratings.all())
    profile = _current_employee_profile(request)
    is_admin = _is_admin(request.user)
    is_reviewer = profile is not None and profile.pk == obj.reviewer_id
    is_subject = profile is not None and profile.pk == obj.subject_id
    # Private manager notes: reviewer or admin only — never the subject-only viewer.
    show_private = is_admin or is_reviewer
    # Anonymised peer/upward feedback hides the reviewer from the subject (admin/reviewer still see it).
    show_reviewer = not (obj.is_anonymous and obj.review_type in ("peer", "upward")
                         and not (is_admin or is_reviewer))
    # Goal-review section: the subject's Objectives for the cycle's aligned OKR period.
    goal_objectives = []
    if obj.template and obj.template.include_goals and obj.goal_period is not None:
        goal_objectives = (Objective.objects.filter(
            tenant=request.tenant, owner=obj.subject, goal_period=obj.goal_period)
            .prefetch_related("key_results").order_by("title"))
    return render(request, "hrm/performance/performancereview/detail.html", {
        "obj": obj,
        "ratings": ratings,
        "show_private": show_private,
        "show_reviewer": show_reviewer,
        "is_subject": is_subject,
        "is_reviewer": is_reviewer,
        "can_edit": obj.status == "draft" and (is_admin or is_reviewer),
        "goal_objectives": goal_objectives,
        "rating_form": ReviewRatingForm(tenant=request.tenant),
    })


@login_required
def performancereview_edit(request, pk):
    obj = get_object_or_404(PerformanceReview, pk=pk, tenant=request.tenant)
    # Gate: only the reviewer or a tenant admin, and only while draft — keeps private_notes hidden
    # from the subject and locks content once the review is submitted.
    if not _can_edit_review(request, obj):
        messages.error(request, "Only the reviewer or a tenant admin can edit this review, and only while it is a draft.")
        return redirect("hrm:performancereview_detail", pk=obj.pk)
    return crud_edit(request, model=PerformanceReview, pk=pk, form_class=PerformanceReviewForm,
                     template="hrm/performance/performancereview/form.html",
                     success_url="hrm:performancereview_list")


@login_required
@require_POST
def performancereview_delete(request, pk):
    obj = get_object_or_404(PerformanceReview, pk=pk, tenant=request.tenant)
    # A tenant admin may delete any review; a reviewer may delete only their own still-draft review.
    # No one else can — protects the acknowledged audit trail from silent removal.
    if not (_is_admin(request.user) or (obj.status == "draft" and _is_reviewer(request, obj))):
        messages.error(request, "Only a tenant admin (or the reviewer, while draft) can delete this review.")
        return redirect("hrm:performancereview_detail", pk=obj.pk)
    return crud_delete(request, model=PerformanceReview, pk=pk, success_url="hrm:performancereview_list")


@login_required
@require_POST
def performancereview_submit(request, pk):
    obj = get_object_or_404(PerformanceReview, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if not (_is_admin(request.user) or (profile is not None and profile.pk == obj.reviewer_id)):
        raise PermissionDenied("Only the reviewer (or a tenant admin) can submit this review.")
    if obj.status == "draft":
        obj.status = "submitted"
        obj.submitted_at = timezone.now()
        # Snapshot the manager's rating at submission time (pre-calibration audit anchor).
        if obj.review_type == "manager" and obj.manager_rating is None:
            obj.manager_rating = obj.overall_rating
        obj.save(update_fields=["status", "submitted_at", "manager_rating", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "submit"})
        messages.success(request, f"Review {obj.number} submitted.")
    else:
        messages.error(request, "Only a draft review can be submitted.")
    return redirect("hrm:performancereview_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def performancereview_share(request, pk):
    obj = get_object_or_404(PerformanceReview, pk=pk, tenant=request.tenant)
    if obj.status == "submitted":
        obj.status = "shared"
        obj.shared_at = timezone.now()
        obj.save(update_fields=["status", "shared_at", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "share"})
        messages.success(request, f"Review {obj.number} shared with the employee.")
    else:
        messages.error(request, "Only a submitted review can be shared.")
    return redirect("hrm:performancereview_detail", pk=obj.pk)


@login_required
@require_POST
def performancereview_acknowledge(request, pk):
    obj = get_object_or_404(PerformanceReview, pk=pk, tenant=request.tenant)
    profile = _current_employee_profile(request)
    if profile is None or profile.pk != obj.subject_id:
        raise PermissionDenied("Only the review subject can acknowledge their review.")
    if obj.status == "shared":
        obj.status = "acknowledged"
        obj.acknowledged_at = timezone.now()
        obj.acknowledged_by = profile
        obj.save(update_fields=["status", "acknowledged_at", "acknowledged_by", "updated_at"])
        write_audit_log(request.user, obj, "update", {"action": "acknowledge"})
        messages.success(request, "Review acknowledged.")
    else:
        messages.error(request, "Only a shared review can be acknowledged.")
    return redirect("hrm:performancereview_detail", pk=obj.pk)


@tenant_admin_required
def performancereview_calibrate(request, pk):
    obj = get_object_or_404(
        PerformanceReview.objects.select_related("subject__party"), pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = CalibrationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, obj, "update", {"action": "calibrate"})
            messages.success(request, f"Calibration saved for {obj.number}.")
            return redirect("hrm:performancereview_detail", pk=obj.pk)
    else:
        form = CalibrationForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/performance/performancereview/calibrate.html", {
        "form": form, "obj": obj})
