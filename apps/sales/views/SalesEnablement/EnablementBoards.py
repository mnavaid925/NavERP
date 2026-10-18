"""Sales 8.9 — Read-only derived boards for Sales Enablement.

Provides the 5 functional surfaces mapping directly to the NavERP.md feature bullets:
1. `sales_enablement_content_hub`: Content Repository & Search
2. `sales_playbook_board`: Sales Playbooks & Guidance
3. `sales_readiness_board`: Training & Certification Tracking
4. `sales_coaching_workbench`: Coaching & Call Recording
5. `sales_competitive_intelligence_library`: Competitive Intelligence Library
"""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.shortcuts import render
from django.utils import timezone

from apps.accounts.models import User
from apps.crm.models.ActivityManagement.CommunicationLogs import CommunicationLog
from apps.sales.models.CompetitiveIntelligence.CompetitiveIntelligence import CompetitorProfile
from apps.sales.models.OpportunityOutcomes.OpportunityOutcomes import OpportunityOutcome
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

    recent_contents = contents_qs.select_related("competitor__party", "document", "author").order_by("-created_at")[:6]
    popular_contents = contents_qs.order_by("-view_count", "-share_count")[:5]

    battlecards = contents_qs.filter(content_type="battle_card").select_related("competitor__party")[:4]
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
        "sheets": case_studies,
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

    # Group playbooks by motion in-memory
    items_by_motion = {}
    for pb in playbooks_qs.order_by("-updated_at"):
        items_by_motion.setdefault(pb.motion_type, []).append(pb)

    playbooks_by_motion = []
    for motion_code, motion_name in SELLING_MOTION_CHOICES:
        motion_items = items_by_motion.get(motion_code, [])
        playbooks_by_motion.append({
            "code": motion_code,
            "name": motion_name,
            "count": len(motion_items),
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

    today = timezone.now().date()
    expiring_soon_count = certs_qs.filter(
        status="completed",
        expires_at__isnull=False,
        expires_at__gte=today,
        expires_at__lte=today + timedelta(days=30),
    ).count()

    certifications_summary = {
        "total": total_certifications,
        "completed": completed_count,
        "in_progress": in_progress_count,
        "failed": failed_count,
        "completion_rate": completion_rate,
        "expiring_soon": expiring_soon_count,
    }

    # Rep readiness matrix
    reps = User.objects.filter(tenant=tenant, is_active=True).order_by("first_name", "username")
    rep_stats = (
        certs_qs.values("rep")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            in_progress=Count("id", filter=Q(status="enrolled")),
            avg_score=Avg("score_percent", filter=Q(status="completed", score_percent__isnull=False)),
        )
    )
    stats_by_rep = {s["rep"]: s for s in rep_stats}

    rep_matrix = []
    for rep in reps:
        stats = stats_by_rep.get(rep.pk, {})
        avg_val = stats.get("avg_score")
        rep_matrix.append({
            "rep": rep,
            "total": stats.get("total", 0),
            "completed": stats.get("completed", 0),
            "avg_score": round(avg_val, 1) if avg_val is not None else None,
            "in_progress": stats.get("in_progress", 0),
        })

    context = {
        "total_certifications": total_certifications,
        "completed_count": completed_count,
        "in_progress_count": in_progress_count,
        "failed_count": failed_count,
        "completion_rate": completion_rate,
        "rep_matrix": rep_matrix,
        "rep_readiness_matrix": rep_matrix,
        "certifications_summary": certifications_summary,
        "expiring_soon_count": expiring_soon_count,
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

    rubric_avgs = scorecards_qs.aggregate(
        discovery=Avg("discovery_score"),
        value_prop=Avg("value_prop_score"),
        objection=Avg("objection_handling_score"),
        next_steps=Avg("next_steps_score"),
    )
    strengths_distribution = {
        "discovery": round(rubric_avgs["discovery"], 1) if rubric_avgs["discovery"] else 0,
        "value_prop": round(rubric_avgs["value_prop"], 1) if rubric_avgs["value_prop"] else 0,
        "objection_handling": round(rubric_avgs["objection"], 1) if rubric_avgs["objection"] else 0,
        "next_steps": round(rubric_avgs["next_steps"], 1) if rubric_avgs["next_steps"] else 0,
    }

    recent_scorecards = scorecards_qs.select_related("coachee", "coach", "communication_log").order_by("-evaluated_on")[:6]

    # Find unreviewed recent communication logs
    reviewed_log_ids = scorecards_qs.values_list("communication_log_id", flat=True)
    unreviewed_logs = (
        CommunicationLog.objects.filter(tenant=tenant)
        .exclude(pk__in=reviewed_log_ids)
        .select_related("owner", "party")
        .order_by("-occurred_at")[:6]
    )

    context = {
        "total_evaluations": total_evaluations,
        "avg_overall_score": avg_overall_score,
        "avg_talk_ratio": avg_talk_ratio,
        "talk_ratio_avg": avg_talk_ratio,
        "recent_scorecards": recent_scorecards,
        "unreviewed_logs": unreviewed_logs,
        "strengths_distribution": strengths_distribution,
    }
    return render(request, "sales/salesenablement/boards/coaching_workbench.html", context)


@login_required
def sales_competitive_intelligence_library(request):
    tenant = request.tenant
    competitors = list(CompetitorProfile.objects.filter(tenant=tenant).select_related("party").order_by("party__name"))

    total_competitors = len(competitors)
    competitor_ids = [comp.pk for comp in competitors]

    all_battlecards = EnablementContent.objects.filter(
        tenant=tenant, competitor_id__in=competitor_ids, is_active=True
    ).order_by("title")
    battlecards_by_comp = {}
    for bc in all_battlecards:
        battlecards_by_comp.setdefault(bc.competitor_id, []).append(bc)

    outcome_stats = (
        OpportunityOutcome.objects.filter(
            tenant=tenant,
            competitor_link__competitor_profile_id__in=competitor_ids,
        )
        .values("competitor_link__competitor_profile")
        .annotate(
            wins=Count("id", filter=Q(result="won")),
            losses=Count("id", filter=Q(result="lost")),
        )
    )
    outcomes_by_comp = {
        s["competitor_link__competitor_profile"]: s
        for s in outcome_stats
    }

    competitor_data = []
    for comp in competitors:
        bcs = battlecards_by_comp.get(comp.pk, [])
        outcomes = outcomes_by_comp.get(comp.pk, {})
        competitor_data.append({
            "profile": comp,
            "battlecards": bcs,
            "wins": outcomes.get("wins", 0),
            "losses": outcomes.get("losses", 0),
        })

    total_wins = sum(c["wins"] for c in competitor_data)
    total_losses = sum(c["losses"] for c in competitor_data)
    total_outcomes = total_wins + total_losses
    win_loss_outcomes = {
        "total": total_outcomes,
        "wins": total_wins,
        "losses": total_losses,
        "win_rate": int(round((total_wins / total_outcomes * 100))) if total_outcomes > 0 else 0,
    }

    context = {
        "total_competitors": total_competitors,
        "competitor_data": competitor_data,
        "competitors_with_battlecards": competitor_data,
        "win_loss_outcomes": win_loss_outcomes,
    }
    return render(request, "sales/salesenablement/boards/competitive_intelligence_library.html", context)


