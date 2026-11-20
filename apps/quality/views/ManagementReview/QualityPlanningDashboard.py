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
    tenant = request.tenant
    today = timezone.now().date()
    current_year = today.year

    # Objectives KPI metrics
    obj_qs = quality_scope(QualityObjective.objects.all(), request)
    total_objectives = obj_qs.count()
    obj_stats = obj_qs.aggregate(
        on_track=Count("id", filter=Q(rag_status="green") | Q(status__in=["on_track", "achieved"])),
        at_risk=Count("id", filter=Q(rag_status="amber") | Q(status="at_risk")),
        behind=Count("id", filter=Q(rag_status="red") | Q(status="behind")),
        achieved=Count("id", filter=Q(status="achieved")),
    )
    objectives_on_track = obj_stats["on_track"]
    objectives_at_risk = obj_stats["at_risk"]
    objectives_behind = obj_stats["behind"]
    objectives_achieved = obj_stats["achieved"]

    objective_achievement_rate = (
        int((objectives_achieved / total_objectives) * 100) if total_objectives > 0 else 0
    )

    rag_distribution = {
        "green": obj_qs.filter(rag_status="green").count(),
        "amber": obj_qs.filter(rag_status="amber").count(),
        "red": obj_qs.filter(rag_status="red").count(),
        "neutral": obj_qs.filter(rag_status="neutral").count(),
    }

    category_counts = []
    for cat_val, cat_label in QualityObjective.CATEGORY_CHOICES:
        cnt = obj_qs.filter(category=cat_val).count()
        if cnt > 0 or total_objectives < 10:
            category_counts.append({
                "category": cat_val,
                "label": cat_label,
                "count": cnt,
                "badge_class": QualityObjective.CATEGORY_CSS.get(cat_val, "badge-info"),
            })

    # Management Reviews KPI metrics
    rev_qs = quality_scope(ManagementReview.objects.all(), request).select_related("executive_sponsor", "lead_facilitator")
    total_reviews = rev_qs.count()
    scheduled_reviews = rev_qs.filter(status="scheduled").count()
    reviews_approved_this_year = rev_qs.filter(status="approved", scheduled_date__year=current_year).count()

    upcoming_reviews = rev_qs.filter(status__in=["scheduled", "in_preparation"]).order_by("scheduled_date")[:5]
    recent_reviews = rev_qs.order_by("-scheduled_date")[:5]

    # Review Actions KPI metrics
    act_qs = quality_scope(ManagementReviewAction.objects.all(), request).select_related("assignee", "management_review")
    total_actions = act_qs.count()
    open_actions = act_qs.filter(status__in=["open", "in_progress", "pending_verification"]).count()
    overdue_actions = act_qs.filter(status__in=["open", "in_progress", "pending_verification"], due_date__lt=today).count()
    completed_actions = act_qs.filter(status="completed").count()

    action_closure_rate = (
        int((completed_actions / total_actions) * 100) if total_actions > 0 else 0
    )

    urgent_actions = act_qs.filter(status__in=["open", "in_progress", "pending_verification"]).order_by("due_date", "-priority")[:6]

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
        "total_reviews": total_reviews,
        "scheduled_reviews": scheduled_reviews,
        "reviews_approved_this_year": reviews_approved_this_year,
        "upcoming_reviews": upcoming_reviews,
        "recent_reviews": recent_reviews,
        "total_actions": total_actions,
        "open_actions": open_actions,
        "overdue_actions": overdue_actions,
        "completed_actions": completed_actions,
        "action_closure_rate": action_closure_rate,
        "urgent_actions": urgent_actions,
    }
    return render(request, "quality/managementreview/quality_planning_dashboard.html", context)
