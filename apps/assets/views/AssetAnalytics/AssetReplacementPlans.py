from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetAnalytics.AssetReplacementPlans import (
    AssetReplacementPlanForm,
)
from apps.assets.models.AssetAnalytics.AssetReplacementPlans import AssetReplacementPlan
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.AssetAnalytics._helpers import (
    ZERO,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    parse_pos_int,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log
from apps.scm.models.InventoryManagement.Locations import Location


def _filter_arpl_queryset(request):
    qs = assets_scope(
        AssetReplacementPlan.objects.select_related(
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "asset_model",
            "org_unit",
            "location",
            "currency",
            "capital_budget",
            "linked_requisition",
            "planner",
        ).defer("notes"),
        request,
    )
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(title__icontains=q)
            | Q(fixed_asset__name__icontains=q)
            | Q(operational_asset__name__icontains=q)
            | Q(asset_category__name__icontains=q)
            | Q(location__name__icontains=q)
        )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={k for k, _ in AssetReplacementPlan.STATUS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "funding_status",
        allowed_values={k for k, _ in AssetReplacementPlan.FUNDING_STATUS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "priority_band",
        allowed_values={k for k, _ in AssetReplacementPlan.PRIORITY_BAND_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "replacement_strategy",
        allowed_values={k for k, _ in AssetReplacementPlan.STRATEGY_CHOICES},
    )
    year_val = parse_pos_int(request.GET.get("planned_replacement_year"))
    if year_val is not None:
        qs = qs.filter(planned_replacement_year=year_val)
    qs = apply_fk_filter(qs, request, "org_unit")
    qs = apply_fk_filter(qs, request, "asset_category")
    qs = apply_fk_filter(qs, request, "location")
    return qs


@login_required
def asset_replacement_plan_list(request):
    qs = _filter_arpl_queryset(request)

    metrics = AssetReplacementPlan.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        critical=Count("id", filter=Q(priority_band="critical")),
        unfunded=Sum("inflation_adjusted_cost", filter=Q(funding_status="unfunded")),
        total_forecast=Sum("inflation_adjusted_cost"),
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    cur_year = timezone.localdate().year
    db_years = set(
        AssetReplacementPlan.objects.filter(tenant=request.tenant).values_list(
            "planned_replacement_year", flat=True
        )
    )
    years = sorted(db_years | {cur_year + i for i in range(6)})

    categories = AssetCategory.objects.filter(tenant=request.tenant).order_by("name")
    org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")
    locations = Location.objects.filter(tenant=request.tenant, is_active=True).order_by("name")

    return render(
        request,
        "assets/assetanalytics/asset_replacement_plan/list.html",
        {
            "plans": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": AssetReplacementPlan.STATUS_CHOICES,
            "funding_choices": AssetReplacementPlan.FUNDING_STATUS_CHOICES,
            "priority_choices": AssetReplacementPlan.PRIORITY_BAND_CHOICES,
            "strategy_choices": AssetReplacementPlan.STRATEGY_CHOICES,
            "years": years,
            "org_units": org_units,
            "categories": categories,
            "locations": locations,
            "total_plans": metrics["total"] or 0,
            "critical_plans_count": metrics["critical"] or 0,
            "unfunded_plans_value": metrics["unfunded"] or ZERO,
            "total_capex_forecast": metrics["total_forecast"] or ZERO,
        },
    )


@login_required
def asset_replacement_plan_detail(request, pk):
    plan = assets_object(
        request,
        AssetReplacementPlan,
        pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "asset_model",
            "org_unit",
            "location",
            "currency",
            "condition_assessment",
            "lifecycle_analysis",
            "capital_budget",
            "linked_requisition",
            "planner",
        ],
    )
    return render(
        request,
        "assets/assetanalytics/asset_replacement_plan/detail.html",
        {"plan": plan},
    )


@login_required
@tenant_admin_required
def asset_replacement_plan_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating a replacement plan.")
        return redirect("assets:portfolio_dashboard")
    if request.method == "POST":
        form = AssetReplacementPlanForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                plan = form.save(commit=False)
                plan.tenant = request.tenant
                if not plan.planner_id:
                    plan.planner = request.user
                plan.save()
                write_audit_log(request.user, plan, "create", tenant=request.tenant)
            messages.success(request, f"Replacement plan '{plan.number}' created successfully.")
            return redirect("assets:asset_replacement_plan_detail", pk=plan.pk)
    else:
        form = AssetReplacementPlanForm(tenant=request.tenant, initial={"planner": request.user})

    return render(
        request,
        "assets/assetanalytics/asset_replacement_plan/form.html",
        {"form": form, "plan": None, "is_edit": False},
    )


@login_required
@tenant_admin_required
def asset_replacement_plan_edit(request, pk):
    plan = assets_object(request, AssetReplacementPlan, pk)
    if request.method == "POST":
        form = AssetReplacementPlanForm(request.POST, instance=plan, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                plan = form.save()
                write_audit_log(request.user, plan, "update", tenant=request.tenant)
            messages.success(request, f"Replacement plan '{plan.number}' updated successfully.")
            return redirect("assets:asset_replacement_plan_detail", pk=plan.pk)
    else:
        form = AssetReplacementPlanForm(instance=plan, tenant=request.tenant)

    return render(
        request,
        "assets/assetanalytics/asset_replacement_plan/form.html",
        {"form": form, "plan": plan, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def asset_replacement_plan_delete(request, pk):
    plan = assets_object(request, AssetReplacementPlan, pk)
    try:
        with transaction.atomic():
            write_audit_log(request.user, plan, "delete", tenant=request.tenant)
            plan.delete()
        messages.success(request, "Replacement plan deleted successfully.")
    except ProtectedError:
        messages.error(request, "Cannot delete replacement plan because dependent records exist.")
    return redirect("assets:asset_replacement_plan_list")


@login_required
@tenant_admin_required
@require_POST
def asset_replacement_plan_recalculate(request, pk):
    plan = assets_object(request, AssetReplacementPlan, pk)
    with transaction.atomic():
        plan.recalculate_metrics()
        plan.save()
        write_audit_log(request.user, plan, "compute", tenant=request.tenant)
    messages.success(
        request,
        f"Recalculated FCI ({plan.fci_ratio_pct:.2f}%), priority ({plan.priority_score:.1f}), and inflation forecast for '{plan.number}'.",
    )
    return redirect("assets:asset_replacement_plan_detail", pk=plan.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_replacement_plan_transition(request, pk):
    plan = assets_object(request, AssetReplacementPlan, pk)
    target_status = request.POST.get("target_status", "").strip()
    allowed_targets = {"proposed", "approved", "scheduled", "executed", "deferred", "cancelled"}
    if target_status not in allowed_targets:
        messages.error(request, "Invalid target replacement plan status.")
        return redirect("assets:asset_replacement_plan_detail", pk=plan.pk)
    if plan.status == target_status:
        messages.info(request, f"Plan '{plan.number}' is already '{plan.get_status_display()}'.")
        return redirect("assets:asset_replacement_plan_detail", pk=plan.pk)
    with transaction.atomic():
        plan.status = target_status
        plan.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, plan, "update", tenant=request.tenant)
    messages.success(request, f"Replacement plan '{plan.number}' moved to '{plan.get_status_display()}'.")
    return redirect("assets:asset_replacement_plan_detail", pk=plan.pk)


@login_required
def asset_replacement_plan_export_csv(request):
    qs = _filter_arpl_queryset(request)
    headers = [
        "Number",
        "Title",
        "Category",
        "Org Unit",
        "Location",
        "Target Year",
        "Quarter",
        "Strategy",
        "Priority Score",
        "Priority Band",
        "FCI %",
        "Base Est Cost",
        "Inflation Adjusted Cost",
        "Funding Status",
        "Status",
    ]
    rows = (
        [
            p.number,
            p.title,
            p.asset_category.name if p.asset_category else "",
            p.org_unit.name if p.org_unit else "",
            p.location.name if p.location else "",
            p.planned_replacement_year,
            p.get_planned_quarter_display(),
            p.get_replacement_strategy_display(),
            f"{p.priority_score:.2f}",
            p.get_priority_band_display(),
            f"{p.fci_ratio_pct:.2f}",
            f"{p.estimated_replacement_cost:.2f}",
            f"{p.inflation_adjusted_cost:.2f}",
            p.get_funding_status_display(),
            p.get_status_display(),
        ]
        for p in qs
    )
    return csv_export_response(filename="arpl-replacement-plans.csv", headers=headers, rows=rows)
