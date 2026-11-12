from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q, Sum
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from apps.accounting.models.FixedAssets.FixedAssetsRegister import FixedAsset
from apps.assets.models.AssetAnalytics.AssetExecutiveScorecards import (
    AssetExecutiveScorecard,
)
from apps.assets.models.AssetAnalytics.AssetLifecycleCostAnalyses import (
    AssetLifecycleCostAnalysis,
)
from apps.assets.models.AssetAnalytics.AssetPortfolioScenarios import (
    AssetPortfolioScenario,
)
from apps.assets.models.AssetAnalytics.AssetReplacementPlans import AssetReplacementPlan
from apps.assets.models.AssetClassification.AssetCategories import AssetCategory
from apps.assets.models.AssetCompliance.AssetComplianceAudits import AssetComplianceAudit
from apps.assets.models.AssetCompliance.AssetComplianceIncidents import (
    AssetComplianceIncident,
)
from apps.assets.models.AssetReliability.AssetConditionAssessments import (
    AssetConditionAssessment,
)
from apps.assets.models.AssetRisk.AssetRiskRegisters import AssetRiskRegister
from apps.assets.views._common import assets_scope
from apps.assets.views.AssetAnalytics._helpers import (
    ZERO,
    csv_export_response,
    parse_pos_int,
)
from apps.core.models.OrgUnit import OrgUnit
from apps.scm.models.AssetManagement.Assets import Asset
from apps.scm.models.InventoryManagement.Locations import Location

_CRIT_COLS = ("critical", "high", "medium", "low")


def _build_portfolio_context(request):
    tenant = request.tenant
    org_unit_id = parse_pos_int(request.GET.get("org_unit"))
    cat_id = parse_pos_int(request.GET.get("asset_category"))
    loc_id = parse_pos_int(request.GET.get("location"))
    base_year = parse_pos_int(request.GET.get("fiscal_year")) or timezone.localdate().year
    if not (2000 <= base_year <= 2100):
        base_year = timezone.localdate().year

    scm_qs = assets_scope(Asset.objects.all(), request).exclude(
        status__in=["retired", "disposed"]
    )
    if org_unit_id:
        scm_qs = scm_qs.filter(org_unit_id=org_unit_id)
    if loc_id:
        scm_qs = scm_qs.filter(location_id=loc_id)

    fa_qs = FixedAsset.objects.filter(tenant=tenant).exclude(status="disposed")
    if org_unit_id or loc_id:
        fa_qs = fa_qs.filter(
            pk__in=scm_qs.exclude(fixed_asset_id__isnull=True).values("fixed_asset_id")
        )

    alcc_qs = assets_scope(AssetLifecycleCostAnalysis.objects.all(), request).exclude(
        status="archived"
    )
    arpl_qs = assets_scope(AssetReplacementPlan.objects.all(), request).exclude(
        status__in=["executed", "cancelled"]
    )
    cond_qs = AssetConditionAssessment.objects.filter(tenant=tenant).exclude(status="archived")
    risk_qs = AssetRiskRegister.objects.filter(tenant=tenant).exclude(status="closed")
    audit_qs = AssetComplianceAudit.objects.filter(tenant=tenant).exclude(status="cancelled")
    inc_qs = AssetComplianceIncident.objects.filter(tenant=tenant).exclude(
        status__in=["resolved", "closed"]
    )
    akpi_qs = assets_scope(AssetExecutiveScorecard.objects.all(), request).exclude(
        status="archived"
    )

    if org_unit_id:
        alcc_qs = alcc_qs.filter(org_unit_id=org_unit_id)
        arpl_qs = arpl_qs.filter(org_unit_id=org_unit_id)
        cond_qs = cond_qs.filter(operational_asset__org_unit_id=org_unit_id)
        risk_qs = risk_qs.filter(asset__org_unit_id=org_unit_id)
        audit_qs = audit_qs.filter(asset__org_unit_id=org_unit_id)
        inc_qs = inc_qs.filter(asset__org_unit_id=org_unit_id)
        akpi_qs = akpi_qs.filter(org_unit_id=org_unit_id)

    if cat_id:
        alcc_qs = alcc_qs.filter(asset_category_id=cat_id)
        arpl_qs = arpl_qs.filter(asset_category_id=cat_id)
        cond_qs = cond_qs.filter(asset_category_id=cat_id)
        risk_qs = risk_qs.filter(category_id=cat_id)
        akpi_qs = akpi_qs.filter(asset_category_id=cat_id)

    if loc_id:
        alcc_qs = alcc_qs.filter(operational_asset__location_id=loc_id)
        arpl_qs = arpl_qs.filter(location_id=loc_id)
        cond_qs = cond_qs.filter(operational_asset__location_id=loc_id)
        risk_qs = risk_qs.filter(asset__location_id=loc_id)
        audit_qs = audit_qs.filter(asset__location_id=loc_id)
        inc_qs = inc_qs.filter(asset__location_id=loc_id)

    fa_agg = fa_qs.aggregate(
        cnt=Count("id"),
        acq=Sum("acquisition_cost"),
        dep=Sum("accumulated_depreciation"),
    )
    scm_cnt = scm_qs.count()
    total_assets = scm_cnt if scm_cnt > 0 else (fa_agg["cnt"] or 0)
    total_acq = fa_agg["acq"] or ZERO
    total_nbv = max(ZERO, total_acq - (fa_agg["dep"] or ZERO))

    alcc_agg = alcc_qs.aggregate(
        total_tco=Sum("total_lifecycle_cost"),
        total_crv=Sum("current_replacement_value"),
    )
    arpl_agg = arpl_qs.aggregate(
        total_crv=Sum("current_replacement_value"),
        total_deferred=Sum("deferred_maintenance_cost"),
        five_yr_capex=Sum(
            "inflation_adjusted_cost",
            filter=Q(planned_replacement_year__range=(base_year, base_year + 4)),
        ),
        unfunded_backlog=Sum("inflation_adjusted_cost", filter=Q(funding_status="unfunded")),
    )
    total_crv = arpl_agg["total_crv"] or alcc_agg["total_crv"] or total_acq or ZERO
    deferred_total = arpl_agg["total_deferred"] or ZERO
    fci_pct = ((deferred_total / total_crv) * Decimal("100.00")).quantize(Decimal("0.01")) if total_crv > ZERO else ZERO

    avg_health_raw = cond_qs.aggregate(avg_h=Avg("health_score"))["avg_h"]
    avg_health = Decimal(str(avg_health_raw)).quantize(Decimal("0.01")) if avg_health_raw is not None else ZERO

    open_incidents_count = inc_qs.count()

    # Asset Health Heat Map Matrix (Condition Grade x Asset Criticality)
    matrix_map = {
        key: {"grade": key, "label": label, "counts": {c: 0 for c in _CRIT_COLS}, "total": 0}
        for key, label in AssetConditionAssessment.CONDITION_GRADE_CHOICES
    }
    seen_assets = set()
    for assess in (
        cond_qs.order_by("-assessment_date", "-id")
        .values("id", "operational_asset_id", "condition_grade", "operational_asset__criticality")
        .iterator(chunk_size=500)
    ):
        dedupe_key = ("op", assess["operational_asset_id"]) if assess["operational_asset_id"] else ("ca", assess["id"])
        if dedupe_key in seen_assets:
            continue
        seen_assets.add(dedupe_key)
        crit = assess["operational_asset__criticality"] or "medium"
        if crit not in _CRIT_COLS:
            crit = "medium"
        row = matrix_map.get(assess["condition_grade"])
        if row:
            row["counts"][crit] += 1
            row["total"] += 1
    health_matrix = list(matrix_map.values())

    bad_actors = list(
        alcc_qs.select_related("operational_asset", "fixed_asset", "asset_category", "currency")
        .only(
            "id",
            "number",
            "title",
            "total_lifecycle_cost",
            "equivalent_annual_cost",
            "maintenance_to_rav_pct",
            "recommendation",
            "operational_asset__id",
            "operational_asset__name",
            "fixed_asset__id",
            "fixed_asset__name",
            "asset_category__id",
            "asset_category__name",
            "currency__id",
            "currency__code",
            "currency__symbol",
        )
        .order_by("-maintenance_to_rav_pct", "-total_lifecycle_cost")[:5]
    )

    # 5-Year CapEx Forecast by Year
    forecast_rows_qs = (
        arpl_qs.filter(planned_replacement_year__range=(base_year, base_year + 4))
        .values("planned_replacement_year")
        .annotate(
            planned_cost=Sum("estimated_replacement_cost"),
            inflation_cost=Sum("inflation_adjusted_cost"),
            funded_cost=Sum("inflation_adjusted_cost", filter=Q(funding_status="budget_allocated")),
            unfunded_cost=Sum("inflation_adjusted_cost", filter=Q(funding_status="unfunded")),
            plan_count=Count("id"),
        )
    )
    forecast_by_yr = {r["planned_replacement_year"]: r for r in forecast_rows_qs}
    capex_forecast_years = []
    for yr in range(base_year, base_year + 5):
        r = forecast_by_yr.get(yr, {})
        capex_forecast_years.append(
            {
                "year": yr,
                "planned_cost": r.get("planned_cost") or ZERO,
                "inflation_cost": r.get("inflation_cost") or ZERO,
                "funded_cost": r.get("funded_cost") or ZERO,
                "unfunded_cost": r.get("unfunded_cost") or ZERO,
                "plan_count": r.get("plan_count") or 0,
            }
        )

    risk_grouped = {
        r["inherent_risk_level"]: r
        for r in risk_qs.values("inherent_risk_level").annotate(
            cnt=Count("id"), exposure=Sum("financial_exposure_amount")
        )
    }
    open_risk_exposure = ZERO
    risk_posture_rows = []
    for level_key, level_label in AssetRiskRegister.RISK_LEVEL_CHOICES:
        r = risk_grouped.get(level_key, {})
        exp = r.get("exposure") or ZERO
        open_risk_exposure += exp
        risk_posture_rows.append(
            {
                "level": level_key,
                "label": level_label,
                "badge_class": AssetRiskRegister.RISK_LEVEL_CSS.get(level_key, "badge-slate"),
                "count": r.get("cnt") or 0,
                "exposure": exp,
            }
        )
    for level_key, r in risk_grouped.items():
        if level_key not in {k for k, _ in AssetRiskRegister.RISK_LEVEL_CHOICES}:
            open_risk_exposure += r.get("exposure") or ZERO

    audit_agg = audit_qs.aggregate(
        total_audits=Count("id"),
        total_cp=Sum("total_checkpoints"),
        passed_cp=Sum("passed_checkpoints"),
    )
    tot_cp = audit_agg["total_cp"] or 0
    pass_rate_pct = (
        ((Decimal(audit_agg["passed_cp"] or 0) / Decimal(tot_cp)) * Decimal("100.00")).quantize(Decimal("0.01"))
        if tot_cp > 0
        else ZERO
    )

    recent_scorecards = list(
        akpi_qs.select_related("currency")
        .only(
            "id",
            "number",
            "title",
            "period_start",
            "period_end",
            "rag_status",
            "status",
            "asset_roi_pct",
            "maintenance_cost_to_rav_pct",
            "portfolio_fci_pct",
            "currency__id",
            "currency__code",
            "currency__symbol",
        )
        .order_by("-period_end", "-id")[:5]
    )
    latest_scorecard = recent_scorecards[0] if recent_scorecards else None

    kpis = {
        "total_assets": total_assets,
        "total_acquisition_value": total_acq,
        "total_nbv": total_nbv,
        "total_crv": total_crv,
        "total_tco_all": alcc_agg["total_tco"] or ZERO,
        "avg_health_score": avg_health,
        "portfolio_fci_pct": fci_pct,
        "open_risk_exposure": open_risk_exposure,
        "open_incidents_count": open_incidents_count,
        "five_year_capex_demand": arpl_agg["five_yr_capex"] or ZERO,
        "unfunded_backlog_total": arpl_agg["unfunded_backlog"] or ZERO,
        "latest_scorecard": latest_scorecard,
    }

    cur_year = timezone.localdate().year
    fiscal_years = list(range(cur_year - 1, cur_year + 5))

    return {
        "org_units": OrgUnit.objects.filter(tenant=tenant).only("id", "name").order_by("name"),
        "categories": AssetCategory.objects.filter(tenant=tenant).only("id", "name").order_by("name"),
        "locations": Location.objects.filter(tenant=tenant, is_active=True).only("id", "name").order_by("name"),
        "fiscal_years": fiscal_years,
        "selected_fiscal_year": base_year,
        "kpis": kpis,
        "health_matrix": health_matrix,
        "bad_actors": bad_actors,
        "capex_forecast_years": capex_forecast_years,
        "risk_posture_rows": risk_posture_rows,
        "compliance_summary": {
            "total_audits": audit_agg["total_audits"] or 0,
            "pass_rate_pct": pass_rate_pct,
            "open_incidents": open_incidents_count,
        },
        "recent_scorecards": recent_scorecards,
    }


@login_required
def portfolio_dashboard(request):
    context = _build_portfolio_context(request)
    return render(
        request,
        "assets/assetanalytics/portfolio_dashboard/dashboard.html",
        context,
    )


@login_required
def portfolio_dashboard_export_csv(request):
    context = _build_portfolio_context(request)
    headers = ["Section", "Item / Year", "Metric 1", "Metric 2", "Metric 3", "Metric 4"]
    rows = []
    for ba in context["bad_actors"]:
        rows.append(
            [
                "Top TCO Bad Actor",
                f"{ba.number} - {ba.title}",
                f"TCO: {ba.total_lifecycle_cost:.2f}",
                f"EAC: {ba.equivalent_annual_cost:.2f}",
                f"MCR: {ba.maintenance_to_rav_pct:.2f}%",
                ba.get_recommendation_display(),
            ]
        )
    for yr_row in context["capex_forecast_years"]:
        rows.append(
            [
                "5-Yr CapEx Forecast",
                str(yr_row["year"]),
                f"Plans: {yr_row['plan_count']}",
                f"Base: {yr_row['planned_cost']:.2f}",
                f"Escalated: {yr_row['inflation_cost']:.2f}",
                f"Unfunded: {yr_row['unfunded_cost']:.2f}",
            ]
        )
    return csv_export_response(filename="portfolio-analytics.csv", headers=headers, rows=rows)


@login_required
def scenario_compare(request):
    all_scenarios = list(
        assets_scope(
            AssetPortfolioScenario.objects.select_related(
                "scope_org_unit", "scope_category", "currency", "baseline_scenario", "owner"
            ),
            request,
        ).order_by("-is_baseline", "-base_fiscal_year", "-id")
    )

    raw_selected = [s for s in request.GET.getlist("scenarios") if (s or "").strip()]
    parsed_ids = []
    for item in raw_selected:
        val = parse_pos_int(item)
        if val is not None and val not in parsed_ids:
            parsed_ids.append(val)

    if raw_selected:
        if not parsed_ids:
            compared_scenarios = []
            selected_ids = []
        else:
            parsed_set = set(parsed_ids)
            by_id = {s.pk: s for s in all_scenarios if s.pk in parsed_set}
            if not by_id:
                raise Http404("Requested scenarios do not exist in this workspace.")
            compared_scenarios = [by_id[pk] for pk in parsed_ids if pk in by_id]
            selected_ids = [s.pk for s in compared_scenarios]
    else:
        compared_scenarios = all_scenarios[:4]
        selected_ids = [s.pk for s in compared_scenarios]

    baseline_scenario = next((s for s in compared_scenarios if s.is_baseline), None) or (
        next((s for s in all_scenarios if s.is_baseline), None)
    )

    return render(
        request,
        "assets/assetanalytics/portfolio_dashboard/scenario_compare.html",
        {
            "all_scenarios": all_scenarios,
            "compared_scenarios": compared_scenarios,
            "selected_ids": selected_ids,
            "baseline_scenario": baseline_scenario,
        },
    )
