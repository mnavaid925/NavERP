from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Max, ProtectedError, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetAnalytics.AssetPortfolioScenarios import (
    AssetPortfolioScenarioForm,
)
from apps.assets.models.AssetAnalytics.AssetPortfolioScenarios import (
    AssetPortfolioScenario,
)
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.AssetAnalytics._helpers import (
    PAGE_SIZE,
    ZERO,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    parse_pos_int,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log


_AWIF_SELECT_RELATED = (
    "scope_org_unit",
    "scope_category",
    "currency",
    "baseline_scenario",
    "owner",
)


def _filter_awif_queryset(request):
    qs = assets_scope(
        AssetPortfolioScenario.objects.select_related(*_AWIF_SELECT_RELATED).defer("assumptions_summary"),
        request,
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(name__icontains=q)
            | Q(scope_org_unit__name__icontains=q)
            | Q(scope_category__name__icontains=q)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={k for k, _ in AssetPortfolioScenario.STATUS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "scenario_type",
        allowed_values={k for k, _ in AssetPortfolioScenario.SCENARIO_TYPE_CHOICES},
    )
    yr_val = parse_pos_int(request.GET.get("base_fiscal_year"))
    if yr_val is not None:
        qs = qs.filter(base_fiscal_year=yr_val)
    qs = apply_fk_filter(qs, request, "scope_org_unit")
    qs = apply_fk_filter(qs, request, "scope_category")
    return qs


@login_required
def asset_portfolio_scenario_list(request):
    qs = _filter_awif_queryset(request)

    metrics = AssetPortfolioScenario.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        simulated=Count("id", filter=Q(status__in=["simulated", "under_review", "recommended", "adopted"])),
        adopted=Count("id", filter=Q(status="adopted")),
        best_npv=Max("net_present_value"),
    )

    paginator = Paginator(qs, PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    cur_year = timezone.localdate().year
    db_years = set(
        AssetPortfolioScenario.objects.filter(tenant=request.tenant).values_list(
            "base_fiscal_year", flat=True
        )
    )
    years = sorted(db_years | {cur_year, cur_year + 1})

    org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")
    categories = AssetCategory.objects.filter(tenant=request.tenant).order_by("name")

    return render(
        request,
        "assets/assetanalytics/asset_portfolio_scenario/list.html",
        {
            "scenarios": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": AssetPortfolioScenario.STATUS_CHOICES,
            "type_choices": AssetPortfolioScenario.SCENARIO_TYPE_CHOICES,
            "years": years,
            "org_units": org_units,
            "categories": categories,
            "total_scenarios": metrics["total"] or 0,
            "simulated_count": metrics["simulated"] or 0,
            "adopted_count": metrics["adopted"] or 0,
            "best_npv": metrics["best_npv"] or ZERO,
        },
    )


@login_required
def asset_portfolio_scenario_detail(request, pk):
    scenario = assets_object(
        request,
        AssetPortfolioScenario,
        pk,
        select_related=_AWIF_SELECT_RELATED,
    )
    return render(
        request,
        "assets/assetanalytics/asset_portfolio_scenario/detail.html",
        {"scenario": scenario},
    )


@login_required
@tenant_admin_required
def asset_portfolio_scenario_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating a portfolio scenario.")
        return redirect("assets:portfolio_dashboard")
    if request.method == "POST":
        form = AssetPortfolioScenarioForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                scenario = form.save(commit=False)
                scenario.tenant = request.tenant
                if not scenario.owner_id:
                    scenario.owner = request.user
                scenario.save()
                write_audit_log(request.user, scenario, "create", tenant=request.tenant)
            messages.success(request, f"What-if scenario '{scenario.number}' created successfully.")
            return redirect("assets:asset_portfolio_scenario_detail", pk=scenario.pk)
    else:
        form = AssetPortfolioScenarioForm(tenant=request.tenant, initial={"owner": request.user})

    return render(
        request,
        "assets/assetanalytics/asset_portfolio_scenario/form.html",
        {"form": form, "scenario": None, "is_edit": False},
    )


@login_required
@tenant_admin_required
def asset_portfolio_scenario_edit(request, pk):
    scenario = assets_object(request, AssetPortfolioScenario, pk)
    if scenario.is_locked:
        messages.error(
            request,
            f"Scenario '{scenario.number}' is locked ({scenario.get_status_display()}) and cannot be edited.",
        )
        return redirect("assets:asset_portfolio_scenario_detail", pk=scenario.pk)
    if request.method == "POST":
        form = AssetPortfolioScenarioForm(request.POST, instance=scenario, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                scenario = form.save()
                write_audit_log(request.user, scenario, "update", tenant=request.tenant)
            messages.success(request, f"What-if scenario '{scenario.number}' updated successfully.")
            return redirect("assets:asset_portfolio_scenario_detail", pk=scenario.pk)
    else:
        form = AssetPortfolioScenarioForm(instance=scenario, tenant=request.tenant)

    return render(
        request,
        "assets/assetanalytics/asset_portfolio_scenario/form.html",
        {"form": form, "scenario": scenario, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def asset_portfolio_scenario_delete(request, pk):
    scenario = assets_object(request, AssetPortfolioScenario, pk)
    if scenario.is_locked:
        messages.error(
            request,
            f"Scenario '{scenario.number}' is locked ({scenario.get_status_display()}) and cannot be deleted.",
        )
        return redirect("assets:asset_portfolio_scenario_detail", pk=scenario.pk)
    try:
        with transaction.atomic():
            write_audit_log(request.user, scenario, "delete", tenant=request.tenant)
            scenario.delete()
        messages.success(request, "Portfolio scenario deleted successfully.")
    except ProtectedError:
        messages.error(request, "Cannot delete scenario because derived scenarios depend on it.")
    return redirect("assets:asset_portfolio_scenario_list")


@login_required
@tenant_admin_required
@require_POST
def asset_portfolio_scenario_simulate(request, pk):
    scenario = assets_object(
        request,
        AssetPortfolioScenario,
        pk,
        select_related=("baseline_scenario", "currency"),
    )
    if scenario.is_locked:
        messages.error(
            request,
            f"Scenario '{scenario.number}' is locked ({scenario.get_status_display()}) and cannot be re-simulated.",
        )
        return redirect("assets:asset_portfolio_scenario_detail", pk=scenario.pk)
    with transaction.atomic():
        scenario.run_simulation(save=True)
        write_audit_log(
            request.user,
            scenario,
            "update",
            changes={"action": "simulate", "status": scenario.status},
            tenant=request.tenant,
        )
    messages.success(
        request,
        f"Simulation completed for '{scenario.number}': Simulated CapEx ${scenario.simulated_capex_total:,.2f}, NPV ${scenario.net_present_value:,.2f}.",
    )
    return redirect("assets:asset_portfolio_scenario_detail", pk=scenario.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_portfolio_scenario_transition(request, pk):
    scenario = assets_object(request, AssetPortfolioScenario, pk)
    target_status = request.POST.get("target_status", "").strip()
    status_labels = dict(AssetPortfolioScenario.STATUS_CHOICES)
    if target_status not in status_labels:
        messages.error(request, "Invalid target scenario status.")
        return redirect("assets:asset_portfolio_scenario_detail", pk=scenario.pk)
    if scenario.status == target_status:
        messages.info(request, f"Scenario '{scenario.number}' is already '{scenario.get_status_display()}'.")
        return redirect("assets:asset_portfolio_scenario_detail", pk=scenario.pk)
    allowed_next = AssetPortfolioScenario.ALLOWED_TRANSITIONS.get(scenario.status, set())
    if target_status not in allowed_next:
        messages.error(
            request,
            f"Cannot transition scenario '{scenario.number}' from '{scenario.get_status_display()}' to '{status_labels[target_status]}'.",
        )
        return redirect("assets:asset_portfolio_scenario_detail", pk=scenario.pk)
    with transaction.atomic():
        scenario.status = target_status
        scenario.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user,
            scenario,
            "update",
            changes={"action": "transition", "status": scenario.status},
            tenant=request.tenant,
        )
    messages.success(request, f"Scenario '{scenario.number}' transitioned to '{scenario.get_status_display()}'.")
    return redirect("assets:asset_portfolio_scenario_detail", pk=scenario.pk)


@login_required
def asset_portfolio_scenario_export_csv(request):
    qs = _filter_awif_queryset(request)
    headers = [
        "Number",
        "Name",
        "Scenario Type",
        "Fiscal Year",
        "Horizon (Yrs)",
        "Status",
        "Baseline CapEx",
        "Simulated CapEx",
        "CapEx Variance",
        "Baseline OpEx",
        "Simulated OpEx",
        "OpEx Savings",
        "Simulated FCI %",
        "Simulated Avg Health",
        "NPV",
        "Payback (Yrs)",
        "BCR",
    ]
    rows = (
        [
            s.number,
            s.name,
            s.get_scenario_type_display(),
            s.base_fiscal_year,
            s.horizon_years,
            s.get_status_display(),
            f"{s.baseline_capex_total:.2f}",
            f"{s.simulated_capex_total:.2f}",
            f"{s.capex_variance_amount:.2f}",
            f"{s.baseline_opex_maintenance:.2f}",
            f"{s.simulated_opex_maintenance:.2f}",
            f"{s.opex_savings_amount:.2f}",
            f"{s.simulated_fci_pct:.2f}",
            f"{s.simulated_avg_health_score:.2f}",
            f"{s.net_present_value:.2f}",
            f"{s.payback_period_years:.2f}",
            f"{s.benefit_cost_ratio:.2f}",
        ]
        for s in qs[:10000].iterator(chunk_size=500)
    )
    return csv_export_response(filename="awif-scenarios.csv", headers=headers, rows=rows)
