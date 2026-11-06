from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounting.models import Budget, BudgetLine, FiscalPeriod
from apps.bi.forms.OlapAnalysis.WhatIfScenarios import WhatIfScenarioForm
from apps.bi.models.OlapAnalysis.WhatIfScenarios import WhatIfScenario
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def what_if_scenario_list(request):
    qs = bi_scope(WhatIfScenario.objects.all(), request, owner_field="created_by").select_related(
        "cube", "baseline_budget", "fiscal_period", "created_by", "committed_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        simulated=Count("id", filter=Q(status="simulated")),
        approved=Count("id", filter=Q(status="approved")),
        committed=Count("id", filter=Q(status="committed")),
    )
    total_count = counts["total"] or 0
    simulated_count = counts["simulated"] or 0
    approved_count = counts["approved"] or 0
    committed_count = counts["committed"] or 0

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(slug__icontains=q)
            | Q(number__icontains=q)
            | Q(description__icontains=q)
        )

    period_id = request.GET.get("fiscal_period", "").strip()
    if period_id:
        if period_id.isdigit():
            qs = qs.filter(fiscal_period_id=int(period_id))
        else:
            qs = qs.none()

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    fiscal_periods = FiscalPeriod.objects.filter(tenant=request.tenant).order_by("-start_date")

    return render(
        request,
        "bi/olap_analysis/what_if_scenario/list.html",
        {
            "scenarios": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "simulated_count": simulated_count,
            "approved_count": approved_count,
            "committed_count": committed_count,
            "fiscal_periods": fiscal_periods,
            "status_choices": WhatIfScenario.STATUS_CHOICES,
        },
    )


@login_required
def what_if_scenario_detail(request, pk):
    scenario = bi_object(
        request,
        WhatIfScenario,
        pk,
        select_related=["cube", "baseline_budget", "fiscal_period", "created_by", "committed_by"],
    )
    writeback_cells = scenario.writeback_cells.filter(tenant=request.tenant).select_related(
        "gl_account", "org_unit"
    ).order_by("-created_at")

    return render(
        request,
        "bi/olap_analysis/what_if_scenario/detail.html",
        {
            "scenario": scenario,
            "writeback_cells": writeback_cells,
        },
    )


@login_required
def what_if_scenario_create(request):
    cube_id = request.GET.get("cube")
    initial = {}
    if cube_id and str(cube_id).isdigit():
        from apps.bi.models.OlapAnalysis.OlapCubes import OlapCube
        cube = get_object_or_404(OlapCube, pk=cube_id, tenant=request.tenant)
        initial["cube"] = cube

    if request.method == "POST":
        form = WhatIfScenarioForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            scenario = form.save(commit=False)
            scenario.tenant = request.tenant
            scenario.created_by = request.user
            scenario.save()
            write_audit_log(request.user, scenario, "create", changes={"name": scenario.name, "number": scenario.number}, tenant=request.tenant)
            messages.success(request, f"What-If Scenario '{scenario.name}' ({scenario.number}) created successfully.")
            return redirect("bi:what_if_scenario_simulate", pk=scenario.pk)
    else:
        form = WhatIfScenarioForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "bi/olap_analysis/what_if_scenario/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def what_if_scenario_edit(request, pk):
    scenario = bi_object(request, WhatIfScenario, pk)
    if scenario.status == "committed":
        messages.error(request, f"What-If Scenario '{scenario.name}' is committed and cannot be edited.")
        return redirect("bi:what_if_scenario_detail", pk=scenario.pk)
    if request.method == "POST":
        form = WhatIfScenarioForm(request.POST, instance=scenario, tenant=request.tenant)
        if form.is_valid():
            scenario = form.save()
            write_audit_log(request.user, scenario, "update", changes={"name": scenario.name, "number": scenario.number}, tenant=request.tenant)
            messages.success(request, f"What-If Scenario '{scenario.name}' updated successfully.")
            return redirect("bi:what_if_scenario_detail", pk=scenario.pk)
    else:
        form = WhatIfScenarioForm(instance=scenario, tenant=request.tenant)

    return render(
        request,
        "bi/olap_analysis/what_if_scenario/form.html",
        {
            "form": form,
            "scenario": scenario,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def what_if_scenario_delete(request, pk):
    scenario = bi_object(request, WhatIfScenario, pk)
    if scenario.status == "committed":
        messages.error(request, f"What-If Scenario '{scenario.name}' is committed and cannot be deleted.")
        return redirect("bi:what_if_scenario_detail", pk=scenario.pk)
    name = scenario.name
    number = scenario.number
    scenario.delete()
    write_audit_log(request.user, scenario, "delete", changes={"name": name, "number": number}, tenant=request.tenant)
    messages.success(request, f"What-If Scenario '{name}' ({number}) deleted successfully.")
    return redirect("bi:what_if_scenario_list")


@login_required
def what_if_scenario_simulate(request, pk):
    scenario = bi_object(
        request,
        WhatIfScenario,
        pk,
        select_related=["cube", "baseline_budget", "fiscal_period", "created_by"],
    )
    writeback_cells = scenario.writeback_cells.filter(tenant=request.tenant).select_related(
        "gl_account", "org_unit"
    ).order_by("created_at")

    aggregates = writeback_cells.aggregate(
        base_tot=Sum("baseline_value"),
        adj_tot=Sum("adjusted_value"),
        var_tot=Sum("variance_amount"),
    )
    baseline_total = aggregates["base_tot"] or Decimal("0.00")
    adjusted_total = aggregates["adj_tot"] or Decimal("0.00")
    variance_total = aggregates["var_tot"] or Decimal("0.00")

    # Update summary figures on scenario
    if (
        scenario.total_baseline_amount != baseline_total
        or scenario.total_adjusted_amount != adjusted_total
        or scenario.total_variance_amount != variance_total
    ):
        scenario.total_baseline_amount = baseline_total
        scenario.total_adjusted_amount = adjusted_total
        scenario.total_variance_amount = variance_total
        if scenario.status == "draft" and writeback_cells.exists():
            scenario.status = "simulated"
        scenario.save(update_fields=[
            "total_baseline_amount",
            "total_adjusted_amount",
            "total_variance_amount",
            "status",
            "updated_at",
        ])

    return render(
        request,
        "bi/olap_analysis/what_if_scenario/simulate.html",
        {
            "scenario": scenario,
            "writeback_cells": writeback_cells,
            "baseline_total": baseline_total,
            "adjusted_total": adjusted_total,
            "variance_total": variance_total,
            "driver_parameters": scenario.driver_parameters,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def what_if_scenario_commit(request, pk):
    scenario = bi_object(
        request,
        WhatIfScenario,
        pk,
        select_related=["baseline_budget", "fiscal_period"],
    )

    if scenario.status == "committed":
        messages.warning(request, f"Scenario '{scenario.name}' is already committed.")
        return redirect("bi:what_if_scenario_detail", pk=scenario.pk)

    with transaction.atomic():
        # Update writeback cells to committed
        scenario.writeback_cells.filter(tenant=request.tenant, is_committed=False).update(
            is_committed=True,
            updated_at=timezone.now(),
        )

        scenario.status = "committed"
        scenario.committed_at = timezone.now()
        scenario.committed_by = request.user
        scenario.save(update_fields=["status", "committed_at", "committed_by", "updated_at"])

        write_audit_log(
            request.user,
            scenario,
            "commit",
            changes={
                "committed_at": str(scenario.committed_at),
                "total_adjusted_amount": str(scenario.total_adjusted_amount),
                "total_variance_amount": str(scenario.total_variance_amount),
            },
            tenant=request.tenant,
        )

    messages.success(request, f"Scenario '{scenario.name}' successfully committed to budget writeback ledger!")
    return redirect("bi:what_if_scenario_detail", pk=scenario.pk)
