from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.PredictiveAnalytics.OptimizationScenarios import OptimizationScenarioForm
from apps.bi.models.PredictiveAnalytics.OptimizationScenarios import OptimizationScenario
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def optimization_scenario_list(request):
    qs = bi_scope(OptimizationScenario.objects.all(), request, owner_field="owner").select_related(
        "kpi_definition", "owner"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        optimal=Count("id", filter=Q(solver_status="optimal")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    optimal_count = counts["optimal"] or 0

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(slug__icontains=q)
            | Q(number__icontains=q)
            | Q(target_metric_name__icontains=q)
            | Q(description__icontains=q)
        )

    solver_status = request.GET.get("solver_status", "").strip()
    if solver_status:
        qs = qs.filter(solver_status=solver_status)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    return render(
        request,
        "bi/predictive_analytics/optimization_scenario/list.html",
        {
            "optimization_scenarios": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "active_count": active_count,
            "optimal_count": optimal_count,
            "solver_status_choices": OptimizationScenario.SOLVER_STATUS_CHOICES,
            "status_choices": OptimizationScenario.STATUS_CHOICES,
        },
    )


@login_required
def optimization_scenario_detail(request, pk):
    scenario = bi_object(
        request,
        OptimizationScenario,
        pk,
        select_related=["kpi_definition", "owner"],
    )

    return render(
        request,
        "bi/predictive_analytics/optimization_scenario/detail.html",
        {
            "scenario_obj": scenario,
        },
    )


@login_required
def optimization_scenario_create(request):
    if request.method == "POST":
        form = OptimizationScenarioForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            scenario = form.save(commit=False)
            scenario.tenant = request.tenant
            scenario.owner = request.user
            scenario.save()
            write_audit_log(request.user, scenario, "create", changes={"name": scenario.name, "number": scenario.number}, tenant=request.tenant)
            messages.success(request, f"Optimization Scenario '{scenario.name}' ({scenario.number}) created successfully.")
            return redirect("bi:optimization_scenario_detail", pk=scenario.pk)
    else:
        form = OptimizationScenarioForm(tenant=request.tenant)

    return render(
        request,
        "bi/predictive_analytics/optimization_scenario/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def optimization_scenario_edit(request, pk):
    scenario = bi_object(request, OptimizationScenario, pk)
    if request.method == "POST":
        form = OptimizationScenarioForm(request.POST, instance=scenario, tenant=request.tenant)
        if form.is_valid():
            scenario = form.save()
            write_audit_log(request.user, scenario, "update", changes={"name": scenario.name, "number": scenario.number}, tenant=request.tenant)
            messages.success(request, f"Optimization Scenario '{scenario.name}' updated successfully.")
            return redirect("bi:optimization_scenario_detail", pk=scenario.pk)
    else:
        form = OptimizationScenarioForm(instance=scenario, tenant=request.tenant)

    return render(
        request,
        "bi/predictive_analytics/optimization_scenario/form.html",
        {
            "form": form,
            "scenario_obj": scenario,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def optimization_scenario_delete(request, pk):
    scenario = bi_object(request, OptimizationScenario, pk)
    name = scenario.name
    number = scenario.number
    scenario.delete()
    write_audit_log(request.user, scenario, "delete", changes={"name": name, "number": number}, tenant=request.tenant)
    messages.success(request, f"Optimization Scenario '{name}' ({number}) deleted successfully.")
    return redirect("bi:optimization_scenario_list")


@login_required
@require_POST
def optimization_scenario_solve(request, pk):
    scenario = bi_object(request, OptimizationScenario, pk)
    scenario.solve_scenario()
    write_audit_log(
        request.user,
        scenario,
        "solve",
        changes={
            "optimal_value": str(scenario.optimal_value),
            "projected_lift_percentage": str(scenario.projected_lift_percentage),
        },
        tenant=request.tenant,
    )
    messages.success(
        request,
        f"Prescriptive solver completed for '{scenario.name}'. Optimal Solution: {scenario.optimal_value} ({scenario.projected_lift_percentage}% projected lift).",
    )
    return redirect("bi:optimization_scenario_detail", pk=scenario.pk)
