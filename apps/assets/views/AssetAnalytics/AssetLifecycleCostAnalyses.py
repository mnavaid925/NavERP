from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, ProtectedError, Q, Sum
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.assets.forms.AssetAnalytics.AssetLifecycleCostAnalyses import (
    AssetLifecycleCostAnalysisForm,
)
from apps.assets.models.AssetAnalytics.AssetLifecycleCostAnalyses import (
    AssetLifecycleCostAnalysis,
)
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.views._common import assets_object, assets_scope
from apps.assets.views.AssetAnalytics._helpers import (
    ZERO,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
)
from apps.core.decorators import tenant_admin_required
from apps.core.models.OrgUnit import OrgUnit
from apps.core.utils import write_audit_log


def _filter_alcc_queryset(request):
    qs = assets_scope(
        AssetLifecycleCostAnalysis.objects.select_related(
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "asset_model",
            "org_unit",
            "currency",
            "analyzed_by",
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
        )
    qs = apply_choice_filter(
        qs,
        request,
        "status",
        allowed_values={k for k, _ in AssetLifecycleCostAnalysis.STATUS_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "lifecycle_stage",
        allowed_values={k for k, _ in AssetLifecycleCostAnalysis.LIFECYCLE_STAGE_CHOICES},
    )
    qs = apply_choice_filter(
        qs,
        request,
        "recommendation",
        allowed_values={k for k, _ in AssetLifecycleCostAnalysis.RECOMMENDATION_CHOICES},
    )
    qs = apply_fk_filter(qs, request, "asset_category")
    qs = apply_fk_filter(qs, request, "org_unit")
    return qs


@login_required
def asset_lifecycle_cost_analysis_list(request):
    qs = _filter_alcc_queryset(request)

    metrics = AssetLifecycleCostAnalysis.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        avg_tco=Avg("total_lifecycle_cost"),
        total_tco=Sum("total_lifecycle_cost"),
        replace_candidates=Count(
            "id", filter=Q(recommendation__in=["schedule_replacement", "dispose_retire"])
        ),
    )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    categories = AssetCategory.objects.filter(tenant=request.tenant).order_by("name")
    org_units = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    return render(
        request,
        "assets/assetanalytics/asset_lifecycle_cost_analysis/list.html",
        {
            "analyses": page_obj,
            "page_obj": page_obj,
            "paginator": paginator,
            "is_paginated": page_obj.has_other_pages(),
            "status_choices": AssetLifecycleCostAnalysis.STATUS_CHOICES,
            "stage_choices": AssetLifecycleCostAnalysis.LIFECYCLE_STAGE_CHOICES,
            "recommendation_choices": AssetLifecycleCostAnalysis.RECOMMENDATION_CHOICES,
            "categories": categories,
            "org_units": org_units,
            "total_analyses": metrics["total"] or 0,
            "avg_tco": (metrics["avg_tco"] or ZERO).quantize(Decimal("0.01")),
            "replace_candidates_count": metrics["replace_candidates"] or 0,
            "total_tco_value": metrics["total_tco"] or ZERO,
        },
    )


@login_required
def asset_lifecycle_cost_analysis_detail(request, pk):
    analysis = assets_object(
        request,
        AssetLifecycleCostAnalysis,
        pk,
        select_related=[
            "fixed_asset",
            "operational_asset",
            "asset_category",
            "asset_model",
            "org_unit",
            "currency",
            "analyzed_by",
        ],
    )
    return render(
        request,
        "assets/assetanalytics/asset_lifecycle_cost_analysis/detail.html",
        {
            "analysis": analysis,
            "total_capex": analysis.total_capex_amount,
            "total_maint": analysis.total_maintenance_amount,
            "total_opex": analysis.total_opex_amount,
            "total_recoveries": analysis.total_recoveries_amount,
        },
    )


@login_required
@tenant_admin_required
def asset_lifecycle_cost_analysis_create(request):
    if request.method == "POST":
        form = AssetLifecycleCostAnalysisForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                analysis = form.save(commit=False)
                analysis.tenant = request.tenant
                if not analysis.analyzed_by_id:
                    analysis.analyzed_by = request.user
                analysis.save()
                write_audit_log(request.user, analysis, "create", tenant=request.tenant)
            messages.success(request, f"Lifecycle cost analysis '{analysis.number}' created successfully.")
            return redirect("assets:asset_lifecycle_cost_analysis_detail", pk=analysis.pk)
    else:
        form = AssetLifecycleCostAnalysisForm(
            tenant=request.tenant,
            initial={"analyzed_by": request.user},
        )

    return render(
        request,
        "assets/assetanalytics/asset_lifecycle_cost_analysis/form.html",
        {
            "form": form,
            "analysis": None,
            "is_edit": False,
        },
    )


@login_required
@tenant_admin_required
def asset_lifecycle_cost_analysis_edit(request, pk):
    analysis = assets_object(request, AssetLifecycleCostAnalysis, pk)
    if request.method == "POST":
        form = AssetLifecycleCostAnalysisForm(request.POST, instance=analysis, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                analysis = form.save()
                write_audit_log(request.user, analysis, "update", tenant=request.tenant)
            messages.success(request, f"Lifecycle cost analysis '{analysis.number}' updated successfully.")
            return redirect("assets:asset_lifecycle_cost_analysis_detail", pk=analysis.pk)
    else:
        form = AssetLifecycleCostAnalysisForm(instance=analysis, tenant=request.tenant)

    return render(
        request,
        "assets/assetanalytics/asset_lifecycle_cost_analysis/form.html",
        {
            "form": form,
            "analysis": analysis,
            "is_edit": True,
        },
    )


@login_required
@tenant_admin_required
@require_POST
def asset_lifecycle_cost_analysis_delete(request, pk):
    analysis = assets_object(request, AssetLifecycleCostAnalysis, pk)
    try:
        with transaction.atomic():
            write_audit_log(request.user, analysis, "delete", tenant=request.tenant)
            analysis.delete()
        messages.success(request, "Lifecycle cost analysis deleted successfully.")
    except ProtectedError:
        messages.error(request, "Cannot delete analysis because downstream replacement plans reference it.")
    return redirect("assets:asset_lifecycle_cost_analysis_list")


@login_required
@tenant_admin_required
@require_POST
def asset_lifecycle_cost_analysis_populate(request, pk):
    analysis = assets_object(request, AssetLifecycleCostAnalysis, pk)
    with transaction.atomic():
        analysis.populate_from_asset_records(save=True)
        write_audit_log(request.user, analysis, "populate", tenant=request.tenant)
    messages.success(
        request,
        f"Aggregated upstream spend and recalculated TCO metrics for '{analysis.number}'.",
    )
    return redirect("assets:asset_lifecycle_cost_analysis_detail", pk=analysis.pk)


@login_required
@tenant_admin_required
@require_POST
def asset_lifecycle_cost_analysis_transition(request, pk):
    analysis = assets_object(request, AssetLifecycleCostAnalysis, pk)
    target_status = request.POST.get("target_status", "").strip()
    allowed_targets = {"calculated", "reviewed", "approved", "archived"}
    if target_status not in allowed_targets:
        messages.error(request, "Invalid target lifecycle analysis status requested.")
        return redirect("assets:asset_lifecycle_cost_analysis_detail", pk=analysis.pk)
    if analysis.status == target_status:
        messages.info(request, f"Analysis '{analysis.number}' is already in '{analysis.get_status_display()}' status.")
        return redirect("assets:asset_lifecycle_cost_analysis_detail", pk=analysis.pk)
    with transaction.atomic():
        analysis.status = target_status
        analysis.save(update_fields=["status", "updated_at"])
        write_audit_log(request.user, analysis, "update", tenant=request.tenant)
    messages.success(request, f"Analysis '{analysis.number}' transitioned to '{analysis.get_status_display()}'.")
    return redirect("assets:asset_lifecycle_cost_analysis_detail", pk=analysis.pk)


@login_required
def asset_lifecycle_cost_analysis_export_csv(request):
    qs = _filter_alcc_queryset(request)
    headers = [
        "Number",
        "Title",
        "Category",
        "Org Unit",
        "Analysis Date",
        "Stage",
        "Status",
        "Total CapEx",
        "Total OpEx",
        "Recoveries",
        "Net Lifecycle TCO",
        "Equivalent Annual Cost",
        "Maint / RAV %",
        "OpEx / CapEx",
        "Economic EOL Year",
        "Recommendation",
    ]
    rows = (
        [
            a.number,
            a.title,
            a.asset_category.name if a.asset_category else "",
            a.org_unit.name if a.org_unit else "",
            a.analysis_date.isoformat() if a.analysis_date else "",
            a.get_lifecycle_stage_display(),
            a.get_status_display(),
            f"{a.total_capex_amount:.2f}",
            f"{a.total_opex_amount:.2f}",
            f"{a.total_recoveries_amount:.2f}",
            f"{a.total_lifecycle_cost:.2f}",
            f"{a.equivalent_annual_cost:.2f}",
            f"{a.maintenance_to_rav_pct:.2f}",
            f"{a.opex_to_capex_ratio:.2f}",
            a.economic_eol_year or "",
            a.get_recommendation_display(),
        ]
        for a in qs
    )
    return csv_export_response(filename="alcc-analyses.csv", headers=headers, rows=rows)
