"""Projects 7.13 Agile & Scrum Management — Velocity & Team Health Report.

Realizes NavERP 7.13 bullet 5:
- Retrospectives & Team Health (sprint retrospective boards, action item tracking, team sentiment surveys)
"""
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.projects.models.AgileScrumManagement.SprintRetrospectives import SprintRetrospective
from apps.projects.models.AgileScrumManagement.Sprints import Sprint


@login_required
def velocity_report(request):
    """Historical velocity tracking, team throughput analytics, and retrospective sentiment health."""
    tenant = request.tenant

    completed_sprints_qs = (
        Sprint.objects.filter(tenant=tenant, status="completed")
        .select_related("project", "scrum_master")
        .prefetch_related("tasks")
        .order_by("-completed_at", "-end_date")
    )
    completed_sprints = list(completed_sprints_qs)

    total_delivered_points = sum(s.completed_points for s in completed_sprints)
    sprint_count = len(completed_sprints)
    avg_velocity = (
        round(Decimal(total_delivered_points) / Decimal(sprint_count), 1)
        if sprint_count > 0
        else Decimal("0.0")
    )

    sentiment_history_qs = (
        SprintRetrospective.objects.filter(tenant=tenant)
        .select_related("sprint", "sprint__project", "conducted_by")
        .order_by("-conducted_date", "-created_at")
    )
    sentiment_history = list(sentiment_history_qs)

    total_sentiment = sum(r.sentiment_score for r in sentiment_history)
    retro_count = len(sentiment_history)
    avg_sentiment = (
        round(total_sentiment / Decimal(retro_count), 1)
        if retro_count > 0
        else Decimal("0.0")
    )

    context = {
        "completed_sprints": completed_sprints,
        "avg_velocity": avg_velocity,
        "total_delivered_points": total_delivered_points,
        "sentiment_history": sentiment_history,
        "avg_sentiment": avg_sentiment,
        "retro_count": retro_count,
        "sprint_count": sprint_count,
    }
    return render(request, "projects/agile/velocity.html", context)
