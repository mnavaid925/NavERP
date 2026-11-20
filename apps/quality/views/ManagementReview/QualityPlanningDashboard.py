from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.quality.models.ManagementReview.ManagementReviewActions import ManagementReviewAction
from apps.quality.models.ManagementReview.ManagementReviews import ManagementReview
from apps.quality.models.ManagementReview.QualityObjectives import QualityObjective
from apps.quality.views._common import quality_scope


@login_required
def quality_planning_dashboard(request):
    today = timezone.now().date()
    current_year = today.year

    # Objectives KPI metrics (single aggregate query)
    obj_qs = quality_scope(QualityObjective.objects.all(), request)
    obj_stats = obj_qs.aggregate(
        total=Count("id"),
        on_track=Count("id", filter=Q(rag_status="green") | Q(status__in=["on_track", "achieved"])),
        at_risk=Count("id", filter=Q(rag_status="amber") | Q(status="at_risk")),
        behind=Count("id", filter=Q(rag_status="red") | Q(status="behind")),
        achieved=Count("id", filter=Q(status="achieved")),
        rag_green=Count("id", filter=Q(rag_status="green")),
        rag_amber=Count("id", filter=Q(rag_status="amber")),
        rag_red=Count("id", filter=Q(rag_status="red")),
        rag_neutral=Count("id", filter=Q(rag_status="neutral")),
    )
    total_objectives = obj_stats["total"] or 0
    objectives_on_track = obj_stats["on_track"] or 0
    objectives_at_risk = obj_stats["at_risk"] or 0
    objectives_behind = obj_stats["behind"] or 0
    objectives_achieved = obj_stats["achieved"] or 0

    objective_achievement_rate = (
        int((objectives_achieved / total_objectives) * 100) if total_objectives > 0 else 0
    )

    rag_distribution = {
        "green": obj_stats["rag_green"] or 0,
        "amber": obj_stats["rag_amber"] or 0,
        "red": obj_stats["rag_red"] or 0,
        "neutral": obj_stats["rag_neutral"] or 0,
    }

    # Objectives by category (single group-by query)
    cat_counts_map = {
        row["category"]: row["count"]
        for row in obj_qs.values("category").annotate(count=Count("id"))
    }
    category_counts = []
    for cat_val, cat_label in QualityObjective.CATEGORY_CHOICES:
        cnt = cat_counts_map.get(cat_val, 0)
        if cnt > 0 or total_objectives < 10:
            category_counts.append({
                "category": cat_val,
                "label": cat_label,
                "count": cnt,
                "badge_class": QualityObjective.CATEGORY_CSS.get(cat_val, "badge-info"),
            })
    objectives_by_category = category_counts

    # Management Reviews KPI metrics (single aggregate query)
    rev_qs = quality_scope(ManagementReview.objects.all(), request)
    rev_stats = rev_qs.aggregate(
        total=Count("id"),
        scheduled=Count("id", filter=Q(status="scheduled")),
        approved_this_year=Count("id", filter=Q(status="approved", scheduled_date__year=current_year)),
    )
    total_reviews = rev_stats["total"] or 0
    scheduled_reviews = rev_stats["scheduled"] or 0
    reviews_approved_this_year = rev_stats["approved_this_year"] or 0

    upcoming_reviews = (
        rev_qs.filter(status__in=["scheduled", "in_preparation"])
        .select_related("executive_sponsor", "lead_facilitator")
        .order_by("scheduled_date")[:5]
    )

    # Review Actions KPI metrics (single aggregate query)
    act_qs = quality_scope(ManagementReviewAction.objects.all(), request)
    act_stats = act_qs.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=["open", "in_progress", "pending_verification"])),
        overdue=Count("id", filter=Q(status__in=["open", "in_progress", "pending_verification"], due_date__lt=today)),
        completed=Count("id", filter=Q(status="completed")),
    )
    total_actions = act_stats["total"] or 0
    open_actions = act_stats["open"] or 0
    overdue_actions = act_stats["overdue"] or 0
    completed_actions = act_stats["completed"] or 0

    action_closure_rate = (
        int((completed_actions / total_actions) * 100) if total_actions > 0 else 0
    )

    urgent_actions = (
        act_qs.filter(status__in=["open", "in_progress", "pending_verification"])
        .select_related("assignee", "management_review")
        .order_by("due_date", "-priority")[:5]
    )

    context = {
        "current_year": current_year,
        "total_objectives": total_objectives,
        "objectives_on_track": objectives_on_track,
        "objectives_at_risk": objectives_at_risk,
        "objectives_behind": objectives_behind,
        "objectives_achieved": objectives_achieved,
        "objective_achievement_rate": objective_achievement_rate,
        "rag_distribution": rag_distribution,
        "category_counts": category_counts,
        "objectives_by_category": objectives_by_category,
        "total_reviews": total_reviews,
        "scheduled_reviews": scheduled_reviews,
        "reviews_approved_this_year": reviews_approved_this_year,
        "upcoming_reviews": upcoming_reviews,
        "total_actions": total_actions,
        "open_actions": open_actions,
        "overdue_actions": overdue_actions,
        "completed_actions": completed_actions,
        "action_closure_rate": action_closure_rate,
        "urgent_actions": urgent_actions,
    }
    return render(request, "quality/managementreview/quality_planning_dashboard.html", context)
