from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.PerformanceScorecards.ScorecardKpiAssignments import (
    ScorecardKpiAssignmentForm,
    ScorecardKpiRecordActualForm,
)
from apps.bi.models.PerformanceScorecards.PerformanceScorecards import PerformanceScorecard
from apps.bi.models.PerformanceScorecards.ScorecardKpiAssignments import ScorecardKpiAssignment
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def scorecard_kpi_assignment_list(request):
    qs = bi_scope(ScorecardKpiAssignment.objects.all(), request).select_related(
        "scorecard", "kpi", "objective"
    )

    counts = qs.aggregate(
        total=Count("id"),
        on_track=Count("id", filter=Q(rag_status="green")),
        improving=Count("id", filter=Q(trend_direction="improving")),
        critical=Count("id", filter=Q(rag_status="red")),
    )
    total_count = counts["total"] or 0
    on_track_count = counts["on_track"] or 0
    improving_count = counts["improving"] or 0
    critical_count = counts["critical"] or 0

    # Filters
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(kpi__name__icontains=q)
            | Q(kpi__code__icontains=q)
            | Q(scorecard__name__icontains=q)
            | Q(objective__name__icontains=q)
        )

    scorecard_id = request.GET.get("scorecard", "").strip()
    if scorecard_id:
        qs = qs.filter(scorecard_id=scorecard_id)

    perspective = request.GET.get("perspective", "").strip()
    if perspective:
        qs = qs.filter(perspective=perspective)

    rag_status = request.GET.get("rag_status", "").strip()
    if rag_status:
        qs = qs.filter(rag_status=rag_status)

    trend_direction = request.GET.get("trend_direction", "").strip()
    if trend_direction:
        qs = qs.filter(trend_direction=trend_direction)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page")
    assignments = paginator.get_page(page_number)

    scorecards = PerformanceScorecard.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "assignments": assignments,
        "scorecards": scorecards,
        "perspective_choices": ScorecardKpiAssignment.PERSPECTIVE_CHOICES,
        "rag_choices": ScorecardKpiAssignment.RAG_STATUS_CHOICES,
        "trend_choices": ScorecardKpiAssignment.TREND_CHOICES,
        "stats": {
            "total": total_count,
            "on_track": on_track_count,
            "improving": improving_count,
            "critical": critical_count,
        },
    }
    return render(request, "bi/kpi_performance_scorecards/scorecard_kpi_assignment/list.html", context)


@login_required
def scorecard_kpi_assignment_detail(request, pk):
    assignment = bi_object(
        request,
        ScorecardKpiAssignment,
        pk,
        select_related=("scorecard", "kpi", "objective"),
    )
    context = {
        "assignment": assignment,
    }
    return render(request, "bi/kpi_performance_scorecards/scorecard_kpi_assignment/detail.html", context)


@login_required
@tenant_admin_required
def scorecard_kpi_assignment_create(request):
    initial = {}
    scorecard_id = request.GET.get("scorecard")
    if scorecard_id:
        initial["scorecard"] = scorecard_id
    perspective = request.GET.get("perspective")
    if perspective:
        initial["perspective"] = perspective

    if request.method == "POST":
        form = ScorecardKpiAssignmentForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.tenant = request.tenant
            assignment.save()
            assignment.scorecard.recalculate_performance()

            write_audit_log(
                request.user,
                assignment,
                "create",
                changes={"summary": f"Assigned KPI {assignment.kpi.name} to Scorecard {assignment.scorecard.name}"},
                tenant=request.tenant,
            )
            messages.success(request, f"KPI '{assignment.kpi.name}' assigned to scorecard.")
            return redirect(assignment.scorecard.get_absolute_url())
    else:
        form = ScorecardKpiAssignmentForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "assignment": None,
        "is_edit": False,
    }
    return render(request, "bi/kpi_performance_scorecards/scorecard_kpi_assignment/form.html", context)


@login_required
@tenant_admin_required
def scorecard_kpi_assignment_edit(request, pk):
    assignment = bi_object(request, ScorecardKpiAssignment, pk, select_related=("scorecard", "kpi"))
    if request.method == "POST":
        form = ScorecardKpiAssignmentForm(request.POST, instance=assignment, tenant=request.tenant)
        if form.is_valid():
            assignment = form.save()
            assignment.scorecard.recalculate_performance()

            write_audit_log(
                request.user,
                assignment,
                "update",
                changes={"summary": f"Updated KPI Assignment {assignment.number} ({assignment.kpi.name})"},
                tenant=request.tenant,
            )
            messages.success(request, f"KPI assignment updated.")
            return redirect(assignment.scorecard.get_absolute_url())
    else:
        form = ScorecardKpiAssignmentForm(instance=assignment, tenant=request.tenant)

    context = {
        "form": form,
        "assignment": assignment,
        "is_edit": True,
    }
    return render(request, "bi/kpi_performance_scorecards/scorecard_kpi_assignment/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def scorecard_kpi_assignment_delete(request, pk):
    assignment = bi_object(request, ScorecardKpiAssignment, pk, select_related=("scorecard", "kpi"))
    sc = assignment.scorecard
    kpi_name = assignment.kpi.name
    write_audit_log(
        request.user,
        assignment,
        "delete",
        changes={"summary": f"Removed KPI {kpi_name} from Scorecard {sc.name}"},
        tenant=request.tenant,
    )
    assignment.delete()
    sc.recalculate_performance()
    messages.success(request, f"KPI '{kpi_name}' removed from scorecard.")
    return redirect(sc.get_absolute_url())


@login_required
@tenant_admin_required
def scorecard_kpi_assignment_record_actual(request, pk):
    assignment = bi_object(request, ScorecardKpiAssignment, pk, select_related=("scorecard", "kpi"))
    if request.method == "POST":
        form = ScorecardKpiRecordActualForm(request.POST, instance=assignment)
        if form.is_valid():
            assignment = form.save()
            assignment.scorecard.recalculate_performance()

            write_audit_log(
                request.user,
                assignment,
                "update",
                changes={"summary": f"Recorded actual value {assignment.actual_value} for {assignment.kpi.name} on {assignment.scorecard.name}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Recorded actual measurement ({assignment.actual_value}) for '{assignment.kpi.name}'.")
            return redirect(assignment.scorecard.get_absolute_url())
    else:
        form = ScorecardKpiRecordActualForm(instance=assignment)

    context = {
        "assignment": assignment,
        "form": form,
    }
    return render(request, "bi/kpi_performance_scorecards/scorecard_kpi_assignment/record_actual.html", context)
