from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.PerformanceScorecards.PerformanceScorecards import (
    PerformanceScorecardForm,
    PerformanceScorecardRecalculateForm,
)
from apps.bi.models.PerformanceScorecards.PerformanceScorecards import PerformanceScorecard
from apps.bi.models.PerformanceScorecards.StrategicObjectives import StrategicObjective
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log


@login_required
def performance_scorecard_list(request):
    qs = bi_scope(PerformanceScorecard.objects.all(), request, owner_field="owner").select_related(
        "org_unit", "owner"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        on_track=Count("id", filter=Q(overall_rag_status="green")),
        needs_attention=Count("id", filter=Q(overall_rag_status="amber")),
        critical=Count("id", filter=Q(overall_rag_status="red")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    on_track_count = counts["on_track"] or 0
    needs_attention_count = counts["needs_attention"] or 0
    critical_count = counts["critical"] or 0

    # Filters
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    scorecard_type = request.GET.get("scorecard_type", "").strip()
    if scorecard_type:
        qs = qs.filter(scorecard_type=scorecard_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    rag_status = request.GET.get("rag_status", "").strip()
    if rag_status:
        qs = qs.filter(overall_rag_status=rag_status)

    review_period = request.GET.get("review_period", "").strip()
    if review_period:
        qs = qs.filter(review_period=review_period)

    fiscal_year = request.GET.get("fiscal_year", "").strip()
    if fiscal_year:
        qs = qs.filter(fiscal_year=fiscal_year)

    org_unit = request.GET.get("org_unit", "").strip()
    if org_unit:
        qs = qs.filter(org_unit_id=org_unit)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    scorecards = paginator.get_page(page_number)

    org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "scorecards": scorecards,
        "type_choices": PerformanceScorecard.SCORECARD_TYPE_CHOICES,
        "status_choices": PerformanceScorecard.STATUS_CHOICES,
        "rag_choices": PerformanceScorecard.RAG_STATUS_CHOICES,
        "period_choices": PerformanceScorecard.PERIOD_CHOICES,
        "org_units": org_units,
        "stats": {
            "total": total_count,
            "active": active_count,
            "on_track": on_track_count,
            "needs_attention": needs_attention_count,
            "critical": critical_count,
        },
    }
    return render(request, "bi/kpi_performance_scorecards/performance_scorecard/list.html", context)


@login_required
def performance_scorecard_detail(request, pk):
    scorecard = bi_object(
        request,
        PerformanceScorecard,
        pk,
        select_related=("org_unit", "owner"),
        prefetch_related=("kpi_assignments__kpi", "kpi_assignments__objective"),
    )

    all_kpis = scorecard.kpi_assignments.select_related("kpi", "objective").order_by("sort_order", "kpi__name")
    financial_kpis = [k for k in all_kpis if k.perspective == "financial"]
    customer_kpis = [k for k in all_kpis if k.perspective == "customer"]
    process_kpis = [k for k in all_kpis if k.perspective == "internal_process"]
    learning_kpis = [k for k in all_kpis if k.perspective == "learning_growth"]

    perspective_summary = scorecard.get_perspective_summary()

    context = {
        "scorecard": scorecard,
        "financial_kpis": financial_kpis,
        "customer_kpis": customer_kpis,
        "process_kpis": process_kpis,
        "learning_kpis": learning_kpis,
        "perspective_summary": perspective_summary,
        "recalculate_form": PerformanceScorecardRecalculateForm(),
    }
    return render(request, "bi/kpi_performance_scorecards/performance_scorecard/detail.html", context)


@login_required
@tenant_admin_required
def performance_scorecard_create(request):
    if request.method == "POST":
        form = PerformanceScorecardForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            scorecard = form.save(commit=False)
            scorecard.tenant = request.tenant
            if not scorecard.owner:
                scorecard.owner = request.user
            scorecard.save()
            write_audit_log(
                request.user,
                scorecard,
                "create",
                changes={"summary": f"Created Scorecard {scorecard.number} ({scorecard.name})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Scorecard '{scorecard.name}' created.")
            return redirect(scorecard.get_absolute_url())
    else:
        form = PerformanceScorecardForm(tenant=request.tenant)

    context = {
        "form": form,
        "scorecard": None,
        "is_edit": False,
    }
    return render(request, "bi/kpi_performance_scorecards/performance_scorecard/form.html", context)


@login_required
@tenant_admin_required
def performance_scorecard_edit(request, pk):
    scorecard = bi_object(request, PerformanceScorecard, pk)
    if request.method == "POST":
        form = PerformanceScorecardForm(request.POST, instance=scorecard, tenant=request.tenant)
        if form.is_valid():
            scorecard = form.save()
            scorecard.recalculate_performance()
            write_audit_log(
                request.user,
                scorecard,
                "update",
                changes={"summary": f"Updated Scorecard {scorecard.number} ({scorecard.name})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Scorecard '{scorecard.name}' updated.")
            return redirect(scorecard.get_absolute_url())
    else:
        form = PerformanceScorecardForm(instance=scorecard, tenant=request.tenant)

    context = {
        "form": form,
        "scorecard": scorecard,
        "is_edit": True,
    }
    return render(request, "bi/kpi_performance_scorecards/performance_scorecard/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def performance_scorecard_delete(request, pk):
    scorecard = bi_object(request, PerformanceScorecard, pk)
    sc_name = scorecard.name
    sc_num = scorecard.number
    write_audit_log(
        request.user,
        scorecard,
        "delete",
        changes={"summary": f"Deleted Scorecard {sc_num} ({sc_name})"},
        tenant=request.tenant,
    )
    scorecard.delete()
    messages.success(request, f"Scorecard '{sc_name}' deleted.")
    return redirect("bi:performance_scorecard_list")


@login_required
@require_POST
def performance_scorecard_recalculate(request, pk):
    scorecard = bi_object(request, PerformanceScorecard, pk)
    scorecard.recalculate_performance()
    write_audit_log(
        request.user,
        scorecard,
        "update",
        changes={"summary": f"Recalculated Scorecard {scorecard.number} index ({scorecard.overall_score}% - {scorecard.overall_rag_status})"},
        tenant=request.tenant,
    )
    messages.success(request, f"Scorecard '{scorecard.name}' recalculated (Score: {scorecard.overall_score}%).")
    return redirect(scorecard.get_absolute_url())


@login_required
def performance_scorecard_strategy_map(request, pk):
    scorecard = bi_object(request, PerformanceScorecard, pk, select_related=("org_unit", "owner"))

    objectives = bi_scope(StrategicObjective.objects.all(), request).select_related(
        "parent_objective", "owner"
    ).prefetch_related("child_objectives", "scorecard_kpis__kpi").order_by("sort_order", "name")

    financial_objectives = [o for o in objectives if o.perspective == "financial"]
    customer_objectives = [o for o in objectives if o.perspective == "customer"]
    process_objectives = [o for o in objectives if o.perspective == "internal_process"]
    learning_objectives = [o for o in objectives if o.perspective == "learning_growth"]

    total_objs = len(objectives)
    achieved_objs = sum(1 for o in objectives if o.status == "achieved")
    on_track_objs = sum(1 for o in objectives if o.rag_status == "green")

    context = {
        "scorecard": scorecard,
        "financial_objectives": financial_objectives,
        "customer_objectives": customer_objectives,
        "process_objectives": process_objectives,
        "learning_objectives": learning_objectives,
        "strategy_stats": {
            "total_objectives": total_objs,
            "achieved": achieved_objs,
            "on_track": on_track_objs,
        },
    }
    return render(request, "bi/kpi_performance_scorecards/performance_scorecard/strategy_map.html", context)
