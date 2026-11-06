from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.OlapAnalysis.WritebackCells import ScenarioWritebackCellForm
from apps.bi.models.OlapAnalysis.WhatIfScenarios import WhatIfScenario
from apps.bi.models.OlapAnalysis.WritebackCells import ScenarioWritebackCell
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def writeback_cell_list(request):
    qs = bi_scope(ScenarioWritebackCell.objects.all(), request, owner_field="created_by").select_related(
        "scenario", "gl_account", "org_unit", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        committed=Count("id", filter=Q(is_committed=True)),
        pending=Count("id", filter=Q(is_committed=False)),
        net_var=Sum("variance_amount"),
    )
    total_count = counts["total"] or 0
    committed_count = counts["committed"] or 0
    pending_count = counts["pending"] or 0
    net_variance = counts["net_var"] or Decimal("0.00")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(scenario__name__icontains=q)
            | Q(gl_account__name__icontains=q)
            | Q(gl_account__code__icontains=q)
            | Q(commentary__icontains=q)
        )

    scenario_id = request.GET.get("scenario", "").strip()
    if scenario_id:
        if scenario_id.isdigit():
            qs = qs.filter(scenario_id=int(scenario_id))
        else:
            qs = qs.none()

    spread_method = request.GET.get("spread_method", "").strip()
    if spread_method:
        qs = qs.filter(spread_method=spread_method)

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page", 1))

    scenarios = WhatIfScenario.objects.filter(tenant=request.tenant).order_by("-created_at")

    return render(
        request,
        "bi/olap_analysis/writeback_cell/list.html",
        {
            "cells": page_obj.object_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "committed_count": committed_count,
            "pending_count": pending_count,
            "net_variance": net_variance,
            "scenarios": scenarios,
            "spread_method_choices": ScenarioWritebackCell.SPREAD_METHOD_CHOICES,
        },
    )


@login_required
def writeback_cell_detail(request, pk):
    cell = bi_object(
        request,
        ScenarioWritebackCell,
        pk,
        select_related=["scenario", "gl_account", "org_unit", "committed_budget_line", "created_by"],
    )
    return render(
        request,
        "bi/olap_analysis/writeback_cell/detail.html",
        {
            "cell": cell,
        },
    )


@login_required
def writeback_cell_create(request):
    scenario_id = request.GET.get("scenario")
    initial = {}
    if scenario_id and str(scenario_id).isdigit():
        scenario = get_object_or_404(WhatIfScenario, pk=scenario_id, tenant=request.tenant)
        initial["scenario"] = scenario

    if request.method == "POST":
        form = ScenarioWritebackCellForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            cell = form.save(commit=False)
            cell.tenant = request.tenant
            cell.created_by = request.user
            cell.save()
            write_audit_log(request.user, cell, "create", changes={"number": cell.number, "scenario": cell.scenario.name}, tenant=request.tenant)
            messages.success(request, f"Writeback Cell '{cell.number}' created successfully.")
            return redirect("bi:what_if_scenario_simulate", pk=cell.scenario.pk)
    else:
        form = ScenarioWritebackCellForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "bi/olap_analysis/writeback_cell/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def writeback_cell_edit(request, pk):
    cell = bi_object(request, ScenarioWritebackCell, pk)
    if request.method == "POST":
        form = ScenarioWritebackCellForm(request.POST, instance=cell, tenant=request.tenant)
        if form.is_valid():
            cell = form.save()
            write_audit_log(request.user, cell, "update", changes={"number": cell.number}, tenant=request.tenant)
            messages.success(request, f"Writeback Cell '{cell.number}' updated successfully.")
            return redirect("bi:what_if_scenario_simulate", pk=cell.scenario.pk)
    else:
        form = ScenarioWritebackCellForm(instance=cell, tenant=request.tenant)

    return render(
        request,
        "bi/olap_analysis/writeback_cell/form.html",
        {
            "form": form,
            "cell": cell,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def writeback_cell_delete(request, pk):
    cell = bi_object(request, ScenarioWritebackCell, pk)
    scenario_pk = cell.scenario.pk
    number = cell.number
    cell.delete()
    write_audit_log(request.user, cell, "delete", changes={"number": number}, tenant=request.tenant)
    messages.success(request, f"Writeback Cell '{number}' deleted successfully.")
    return redirect("bi:what_if_scenario_simulate", pk=scenario_pk)
