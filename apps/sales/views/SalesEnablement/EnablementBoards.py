"""Sales 8.9 — Read-only derived boards for Sales Enablement.

Provides the 5 functional surfaces mapping directly to the NavERP.md feature bullets:
1. `sales_enablement_content_hub`: Content Repository & Search
2. `sales_playbook_board`: Sales Playbooks & Guidance
3. `sales_readiness_board`: Training & Certification Tracking
4. `sales_coaching_workbench`: Coaching & Call Recording
5. `sales_competitive_intelligence_library`: Competitive Intelligence Library
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.shortcuts import render

from apps.accounts.models import User
from apps.crm.models.ActivityManagement.CommunicationLogs import CommunicationLog
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import CompetitorProfile
from apps.sales.models.OpportunityOutcome.OpportunityOutcomes import OpportunityOutcome
from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline
from apps.sales.models.SalesEnablement.CoachingScorecards import CoachingScorecard
from apps.sales.models.SalesEnablement.EnablementContents import (
    CONTENT_TYPE_CHOICES,
    TARGET_PERSONA_CHOICES,
    TARGET_STAGE_CHOICES,
    EnablementContent,
)
from apps.sales.models.SalesEnablement.SalesCertifications import (
    CERTIFICATION_CATEGORY_CHOICES,
    SalesCertification,
)
from apps.sales.models.SalesEnablement.SalesPlaybooks import (
    SELLING_MOTION_CHOICES,
    SalesPlaybook,
)


@login_required
def sales_enablement_content_hub(request):
    tenant = request.tenant
    contents_qs = EnablementContent.objects.filter(tenant=tenant, is_active=True)

    total_contents = contents_qs.count()
    total_battlecards = contents_qs.filter(content_type="battle_card").count()
    total_client_facing = contents_qs.filter(is_client_facing=True).count()

    recent_contents = contents_qs.select_related("competitor", "document", "author").order_by("-created_at")[:6]
    popular_contents = contents_qs.order_by("-view_count", "-share_count")[:5]

    battlecards = contents_qs.filter(content_type="battle_card").select_related("competitor")[:4]
    decks = contents_qs.filter(content_type="pitch_deck")[:4]
    case_studies = contents_qs.filter(content_type="case_study")[:4]

    context = {
        "total_contents": total_contents,
        "total_battlecards": total_battlecards,
        "total_client_facing": total_client_facing,
        "recent_contents": recent_contents,
        "popular_contents": popular_contents,
        "battlecards": battlecards,
        "decks": decks,
        "case_studies": case_studies,
        "content_type_choices": CONTENT_TYPE_CHOICES,
        "stage_choices": TARGET_STAGE_CHOICES,
        "persona_choices": TARGET_PERSONA_CHOICES,
    }
    return render(request, "sales/salesenablement/boards/content_hub.html", context)


@login_required
def sales_playbook_board(request):
    tenant = request.tenant
    playbooks_qs = SalesPlaybook.objects.filter(tenant=tenant).select_related("pipeline", "owner")

    total_playbooks = playbooks_qs.count()
    total_published = playbooks_qs.filter(status="published").count()

    # Group playbooks by motion
    playbooks_by_motion = []
    for motion_code, motion_name in SELLING_MOTION_CHOICES:
        motion_items = playbooks_qs.filter(motion_type=motion_code)
        playbooks_by_motion.append({
            "code": motion_code,
            "name": motion_name,
            "count": motion_items.count(),
            "items": motion_items[:5],
        })

    pipelines = Pipeline.objects.filter(tenant=tenant, is_active=True)

    context = {
        "total_playbooks": total_playbooks,
        "total_published": total_published,
        "playbooks_by_motion": playbooks_by_motion,
        "pipelines": pipelines,
    }
    return render(request, "sales/salesenablement/boards/playbook_board.html", context)


@login_required
def sales_readiness_board(request):
    tenant = request.tenant
    certs_qs = SalesCertification.objects.filter(tenant=tenant)

    total_certifications = certs_qs.count()
    completed_count = certs_qs.filter(status="completed").count()
    in_progress_count = certs_qs.filter(status="enrolled").count()
    failed_count = certs_qs.filter(status="failed").count()

    completion_rate = int(round((completed_count / total_certifications * 100))) if total_certifications > 0 else 0

    # Rep readiness matrix
    reps = User.objects.filter(tenant=tenant, is_active=True).order_by("first_name", "username")
    rep_matrix = []
    for rep in reps:
        rep_certs = certs_qs.filter(rep=rep)
        rep_completed = rep_certs.filter(status="completed").count()
        rep_avg = rep_certs.filter(status="completed", score_percent__isnull=False).aggregate(avg=Avg("score_percent"))["avg"]
        rep_matrix.append({
            "rep": rep,
            "total": rep_certs.count(),
            "completed": rep_completed,
            "avg_score": round(rep_avg, 1) if rep_avg else None,
            "in_progress": rep_certs.filter(status="enrolled").count(),
        })

    context = {
        "total_certifications": total_certifications,
        "completed_count": completed_count,
        "in_progress_count": in_progress_count,
        "failed_count": failed_count,
        "completion_rate": completion_rate,
        "rep_matrix": rep_matrix,
        "categories": CERTIFICATION_CATEGORY_CHOICES,
    }
    return render(request, "sales/salesenablement/boards/readiness_board.html", context)


@login_required
def sales_coaching_workbench(request):
    tenant = request.tenant
    scorecards_qs = CoachingScorecard.objects.filter(tenant=tenant)

    total_evaluations = scorecards_qs.count()
    avg_score = scorecards_qs.aggregate(avg=Avg("overall_score"))["avg"]
    avg_overall_score = round(avg_score, 1) if avg_score else 0

    talk_avg = scorecards_qs.filter(talk_listen_ratio_percent__isnull=False).aggregate(avg=Avg("talk_listen_ratio_percent"))["avg"]
    avg_talk_ratio = round(talk_avg, 1) if talk_avg else 0

    recent_scorecards = scorecards_qs.select_related("coachee", "coach", "communication_log").order_by("-evaluated_on")[:6]

    # Find unreviewed recent communication logs
    reviewed_log_ids = scorecards_qs.values_list("communication_log_id", flat=True)
    unreviewed_logs = (
        CommunicationLog.objects.filter(tenant=tenant)
        .exclude(pk__in=reviewed_log_ids)
        .order_by("-occurred_at")[:6]
    )

    context = {
        "total_evaluations": total_evaluations,
        "avg_overall_score": avg_overall_score,
        "avg_talk_ratio": avg_talk_ratio,
        "recent_scorecards": recent_scorecards,
        "unreviewed_logs": unreviewed_logs,
    }
    return render(request, "sales/salesenablement/boards/coaching_workbench.html", context)


@login_required
def sales_competitive_intelligence_library(request):
    tenant = request.tenant
    competitors = CompetitorProfile.objects.filter(tenant=tenant).select_related("party").order_by("party__name")

    total_competitors = competitors.count()

    competitor_data = []
    for comp in competitors:
        battlecards = EnablementContent.objects.filter(
            tenant=tenant, competitor=comp, is_active=True
        )
        # Check 8.2 opportunity outcomes against this competitor if any
        outcomes = OpportunityOutcome.objects.filter(
            tenant=tenant, competitor=comp
        )
        wins = outcomes.filter(outcome="won").count()
        losses = outcomes.filter(outcome="lost").count()
        competitor_data.append({
            "profile": comp,
            "battlecards": battlecards,
            "wins": wins,
            "losses": losses,
        })

    context = {
        "total_competitors": total_competitors,
        "competitor_data": competitor_data,
    }
    return render(request, "sales/salesenablement/boards/competitive_intelligence_library.html", context)
