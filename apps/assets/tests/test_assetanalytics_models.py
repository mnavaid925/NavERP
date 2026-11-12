"""
Unit tests for Sub-module 11.14: Asset Analytics & Business Intelligence Models.
Covers AssetLifecycleCostAnalysis [ALCC-], AssetReplacementPlan [ARPL-],
AssetPortfolioScenario [AWIF-], AssetExecutiveScorecard [AKPI-],
package re-exports, auto-numbering, badge CSS validation, deterministic
metric/simulation/KPI engines, scope/tenant isolation, bounds validation,
and cross-tenant FK rejection.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounting.models import Budget, FixedAsset
from apps.assets.models import (
    AssetCapitalization,
    AssetComplianceAudit,
    AssetComplianceIncident,
    AssetDepreciationSchedule,
    AssetDisposalRequest,
    AssetDowntimeLog,
    AssetEnergyReading,
    AssetExecutiveScorecard,
    AssetInsuranceClaim,
    AssetInsurancePolicy,
    AssetLifecycleCostAnalysis,
    AssetMaintenanceLog,
    AssetOeeRecord,
    AssetPortfolioScenario,
    AssetReplacementPlan,
    AssetResaleListing,
    AssetRiskRegister,
    AssetScrapSalvage,
    AssetServiceContract,
    AssetWarrantyClaim,
)
from apps.assets.models import __all__ as assets_models_all
from apps.assets.models.AssetAnalytics import (
    AssetExecutiveScorecard as DirectAssetExecutiveScorecard,
    AssetLifecycleCostAnalysis as DirectAssetLifecycleCostAnalysis,
    AssetPortfolioScenario as DirectAssetPortfolioScenario,
    AssetReplacementPlan as DirectAssetReplacementPlan,
    __all__ as analytics_pkg_all,
)
from apps.assets.models.AssetAnalytics._validators import (
    add_field_error,
    cap_decimal,
    q2,
    validate_tenant_fks,
)
from apps.core.models import OrgUnit
from apps.scm.models import Asset

pytestmark = pytest.mark.django_db

_assetanalytics_VALID_BADGE_CLASSES = {
    "badge-green",
    "badge-red",
    "badge-amber",
    "badge-info",
    "badge-muted",
    "badge-slate",
}


# =====================================================================
# Module-level Helpers (Must start with _assetanalytics_*)
# =====================================================================


def _assetanalytics_make_lcc(tenant, title="Pump Lifecycle Study", **kwargs):
    data = {
        "tenant": tenant,
        "title": title,
        "analysis_date": timezone.localdate(),
        "analysis_horizon_years": 5,
        "discount_rate_pct": Decimal("8.00"),
        "lifecycle_stage": "in_service",
        "status": "draft",
    }
    data.update(kwargs)
    return AssetLifecycleCostAnalysis(**data)


def _assetanalytics_make_rpl(tenant, title="Pump Replacement Plan", **kwargs):
    data = {
        "tenant": tenant,
        "title": title,
        "remaining_useful_life_months": 12,
        "planned_replacement_year": timezone.localdate().year + 1,
        "planned_quarter": "q1",
        "replacement_strategy": "like_for_like",
        "funding_status": "unfunded",
        "status": "forecasted",
        "condition_score": Decimal("50.00"),
        "criticality_weight": 5,
        "failure_risk_score": Decimal("50.00"),
        "inflation_rate_pct": Decimal("4.00"),
    }
    data.update(kwargs)
    return AssetReplacementPlan(**data)


def _assetanalytics_make_scenario(tenant, name="BAU Portfolio Scenario", **kwargs):
    data = {
        "tenant": tenant,
        "name": name,
        "scenario_type": "baseline_bau",
        "base_fiscal_year": timezone.localdate().year,
        "horizon_years": 5,
        "status": "draft",
    }
    data.update(kwargs)
    return AssetPortfolioScenario(**data)


def _assetanalytics_make_scorecard(tenant, title="Q1 Executive Scorecard", **kwargs):
    today = timezone.localdate()
    data = {
        "tenant": tenant,
        "title": title,
        "period_type": "quarterly",
        "period_start": today - timedelta(days=90),
        "period_end": today,
        "status": "draft",
    }
    data.update(kwargs)
    return AssetExecutiveScorecard(**data)


# =====================================================================
# 1. Package Re-exports & Validators
# =====================================================================


def test_assetanalytics_package_reexports():
    assert AssetLifecycleCostAnalysis is DirectAssetLifecycleCostAnalysis
    assert AssetReplacementPlan is DirectAssetReplacementPlan
    assert AssetPortfolioScenario is DirectAssetPortfolioScenario
    assert AssetExecutiveScorecard is DirectAssetExecutiveScorecard
    for name in (
        "AssetLifecycleCostAnalysis",
        "AssetReplacementPlan",
        "AssetPortfolioScenario",
        "AssetExecutiveScorecard",
    ):
        assert name in analytics_pkg_all
        assert name in assets_models_all


def test_assetanalytics_validator_helpers():
    assert q2(None) == Decimal("0.00")
    assert q2("12.345") == Decimal("12.35")
    assert cap_decimal(Decimal("123456.78")) == Decimal("99999.99")
    assert cap_decimal(Decimal("-123456.78")) == Decimal("-99999.99")

    errors = {}
    add_field_error(errors, "field_a", "Err 1")
    add_field_error(errors, "field_a", "Err 2")
    assert errors["field_a"] == ["Err 1", "Err 2"]

    errors_str = {"field_b": "Existing"}
    add_field_error(errors_str, "field_b", "Second")
    assert errors_str["field_b"] == ["Existing", "Second"]

    unscoped = AssetLifecycleCostAnalysis(title="Missing Tenant")
    err_no_tenant = {}
    validate_tenant_fks(unscoped, err_no_tenant, ["org_unit"])
    assert "__all__" in err_no_tenant


# =====================================================================
# 2. Auto-numbering, Unique Constraints, __str__, Badge CSS
# =====================================================================


def test_assetanalytics_auto_numbering_prefixes_and_str(
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
):
    assert analytics_lcc_a.number.startswith("ALCC-")
    assert analytics_rpl_a.number.startswith("ARPL-")
    assert analytics_scenario_a.number.startswith("AWIF-")
    assert analytics_scorecard_a.number.startswith("AKPI-")

    assert str(analytics_lcc_a) == f"{analytics_lcc_a.number} — {analytics_lcc_a.title}"
    assert str(analytics_rpl_a) == f"{analytics_rpl_a.number} — {analytics_rpl_a.title}"
    assert str(analytics_scenario_a) == f"{analytics_scenario_a.number} — {analytics_scenario_a.name}"
    assert str(analytics_scorecard_a) == f"{analytics_scorecard_a.number} — {analytics_scorecard_a.title}"


def test_assetanalytics_unique_number_per_tenant_and_cross_tenant_reuse(
    tenant_a,
    tenant_b,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
):
    cases = [
        (AssetLifecycleCostAnalysis, analytics_lcc_a, {"title": "Dup LCC"}),
        (AssetReplacementPlan, analytics_rpl_a, {"title": "Dup RPL"}),
        (AssetPortfolioScenario, analytics_scenario_a, {"name": "Dup AWIF"}),
        (
            AssetExecutiveScorecard,
            analytics_scorecard_a,
            {
                "title": "Dup AKPI",
                "period_start": analytics_scorecard_a.period_start,
                "period_end": analytics_scorecard_a.period_end,
            },
        ),
    ]
    for model_cls, existing, extra in cases:
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                model_cls.objects.create(tenant=tenant_a, number=existing.number, **extra)

        other = model_cls.objects.create(tenant=tenant_b, number=existing.number, **extra)
        assert other.number == existing.number
        assert other.tenant_id == tenant_b.id


def test_assetanalytics_badge_css_classes_are_valid_theme_classes():
    css_dicts = [
        AssetLifecycleCostAnalysis.STATUS_CSS,
        AssetLifecycleCostAnalysis.LIFECYCLE_STAGE_CSS,
        AssetLifecycleCostAnalysis.RECOMMENDATION_CSS,
        AssetReplacementPlan.STATUS_CSS,
        AssetReplacementPlan.FUNDING_STATUS_CSS,
        AssetReplacementPlan.PRIORITY_BAND_CSS,
        AssetPortfolioScenario.STATUS_CSS,
        AssetPortfolioScenario.SCENARIO_TYPE_CSS,
        AssetExecutiveScorecard.STATUS_CSS,
        AssetExecutiveScorecard.RAG_STATUS_CSS,
    ]
    for mapping in css_dicts:
        assert mapping
        for key, css_class in mapping.items():
            assert css_class in _assetanalytics_VALID_BADGE_CLASSES, (
                f"Invalid badge CSS class {css_class!r} for key {key!r}"
            )

    assert set(k for k, _ in AssetLifecycleCostAnalysis.STATUS_CHOICES) == set(AssetLifecycleCostAnalysis.STATUS_CSS)
    assert set(k for k, _ in AssetLifecycleCostAnalysis.LIFECYCLE_STAGE_CHOICES) == set(
        AssetLifecycleCostAnalysis.LIFECYCLE_STAGE_CSS
    )
    assert set(k for k, _ in AssetLifecycleCostAnalysis.RECOMMENDATION_CHOICES) == set(
        AssetLifecycleCostAnalysis.RECOMMENDATION_CSS
    )
    assert set(k for k, _ in AssetReplacementPlan.STATUS_CHOICES) == set(AssetReplacementPlan.STATUS_CSS)
    assert set(k for k, _ in AssetReplacementPlan.FUNDING_STATUS_CHOICES) == set(
        AssetReplacementPlan.FUNDING_STATUS_CSS
    )
    assert set(k for k, _ in AssetReplacementPlan.PRIORITY_BAND_CHOICES) == set(
        AssetReplacementPlan.PRIORITY_BAND_CSS
    )
    assert set(k for k, _ in AssetPortfolioScenario.STATUS_CHOICES) == set(AssetPortfolioScenario.STATUS_CSS)
    assert set(k for k, _ in AssetPortfolioScenario.SCENARIO_TYPE_CHOICES) == set(
        AssetPortfolioScenario.SCENARIO_TYPE_CSS
    )
    assert set(k for k, _ in AssetExecutiveScorecard.STATUS_CHOICES) == set(AssetExecutiveScorecard.STATUS_CSS)
    assert set(k for k, _ in AssetExecutiveScorecard.RAG_STATUS_CHOICES) == set(
        AssetExecutiveScorecard.RAG_STATUS_CSS
    )


def test_assetanalytics_badge_properties_and_unknown_fallback(tenant_a):
    lcc = _assetanalytics_make_lcc(tenant_a, status="reviewed", lifecycle_stage="late_life", recommendation="overhaul_refurbish")
    assert lcc.status_badge_class == "badge-amber"
    assert lcc.lifecycle_stage_badge_class == "badge-amber"
    assert lcc.recommendation_badge_class == "badge-info"
    lcc.status = "nonexistent"
    assert lcc.status_badge_class == "badge-slate"

    rpl = _assetanalytics_make_rpl(tenant_a, status="approved", funding_status="budget_allocated", priority_band="critical")
    assert rpl.status_badge_class == "badge-green"
    assert rpl.funding_status_badge_class == "badge-green"
    assert rpl.priority_band_badge_class == "badge-red"
    rpl.priority_band = "nonexistent"
    assert rpl.priority_band_badge_class == "badge-slate"

    scen = _assetanalytics_make_scenario(tenant_a, status="recommended", scenario_type="budget_constrained")
    assert scen.status_badge_class == "badge-green"
    assert scen.scenario_type_badge_class == "badge-red"
    scen.scenario_type = "nonexistent"
    assert scen.scenario_type_badge_class == "badge-slate"

    sc = _assetanalytics_make_scorecard(tenant_a, status="published", rag_status="amber")
    assert sc.status_badge_class == "badge-info"
    assert sc.rag_status_badge_class == "badge-amber"
    sc.rag_status = "nonexistent"
    assert sc.rag_status_badge_class == "badge-slate"


# =====================================================================
# 3. AssetLifecycleCostAnalysis
# =====================================================================


def test_assetanalytics_lcc_recalculate_exact_tco_crf_eac_and_ratios(tenant_a):
    today = timezone.localdate()
    lcc = _assetanalytics_make_lcc(
        tenant_a,
        analysis_date=today,
        analysis_horizon_years=5,
        discount_rate_pct=Decimal("10.00"),
        acquisition_capital_cost=Decimal("100000.00"),
        installation_commissioning_cost=Decimal("20000.00"),
        preventive_maintenance_cost=Decimal("10000.00"),
        corrective_maintenance_cost=Decimal("6000.00"),
        service_contract_cost=Decimal("4000.00"),
        energy_utility_cost=Decimal("8000.00"),
        downtime_opportunity_cost=Decimal("5000.00"),
        insurance_compliance_cost=Decimal("2000.00"),
        expected_salvage_value=Decimal("12000.00"),
        warranty_insurance_recoveries=Decimal("3000.00"),
        current_replacement_value=Decimal("200000.00"),
    )
    lcc.recalculate_metrics()

    # CapEx=120,000; Maint=20,000; OpEx=35,000; Recoveries=15,000 -> TCO=140,000
    assert lcc.total_capex_amount == Decimal("120000.00")
    assert lcc.total_maintenance_amount == Decimal("20000.00")
    assert lcc.total_opex_amount == Decimal("35000.00")
    assert lcc.total_recoveries_amount == Decimal("15000.00")
    assert lcc.total_lifecycle_cost == Decimal("140000.00")

    # CRF(r=0.10, n=5) = 0.10*(1.1^5)/((1.1^5)-1) = 0.161051 / 0.61051
    r = Decimal("0.10")
    comp = (Decimal("1.00") + r) ** 5
    expected_eac = q2(Decimal("140000.00") * ((r * comp) / (comp - Decimal("1.00"))))
    assert lcc.equivalent_annual_cost == expected_eac
    assert lcc.maintenance_to_rav_pct == Decimal("10.00")
    assert lcc.opex_to_capex_ratio == Decimal("0.29")
    assert lcc.recommendation == "retain_operate"
    assert lcc.economic_eol_year == today.year + 5


def test_assetanalytics_lcc_recalculate_zero_discount_zero_denominators_and_tco_floor(tenant_a):
    lcc = _assetanalytics_make_lcc(
        tenant_a,
        analysis_horizon_years=4,
        discount_rate_pct=Decimal("0.00"),
        acquisition_capital_cost=Decimal("0.00"),
        installation_commissioning_cost=Decimal("0.00"),
        preventive_maintenance_cost=Decimal("20000.00"),
        expected_salvage_value=Decimal("5000.00"),
        current_replacement_value=Decimal("0.00"),
    )
    lcc.recalculate_metrics()
    # TCO = 15000, 0% discount -> EAC = 15000 / 4 = 3750.00
    assert lcc.total_lifecycle_cost == Decimal("15000.00")
    assert lcc.equivalent_annual_cost == Decimal("3750.00")
    assert lcc.maintenance_to_rav_pct == Decimal("0.00")
    assert lcc.opex_to_capex_ratio == Decimal("0.00")

    # Recoveries exceeding costs floor TCO at 0.00
    lcc.expected_salvage_value = Decimal("50000.00")
    lcc.recalculate_metrics()
    assert lcc.total_lifecycle_cost == Decimal("0.00")
    assert lcc.equivalent_annual_cost == Decimal("0.00")


def test_assetanalytics_lcc_recommendation_branches_and_eol_year(tenant_a):
    today = timezone.localdate()
    base_year = today.year

    # 1. retain_operate: mcr < 25%, ratio < 1.50, in_service
    lcc = _assetanalytics_make_lcc(
        tenant_a,
        analysis_date=today,
        analysis_horizon_years=6,
        lifecycle_stage="in_service",
        acquisition_capital_cost=Decimal("100000.00"),
        preventive_maintenance_cost=Decimal("10000.00"),
        current_replacement_value=Decimal("100000.00"),
    )
    lcc.recalculate_metrics()
    assert lcc.recommendation == "retain_operate"
    assert lcc.economic_eol_year == base_year + 6

    # 2. overhaul_refurbish via mcr >= 25%
    lcc.preventive_maintenance_cost = Decimal("25000.00")
    lcc.recalculate_metrics()
    assert lcc.recommendation == "overhaul_refurbish"
    assert lcc.economic_eol_year == base_year + 6

    # 2b. overhaul_refurbish via lifecycle_stage == "late_life" even with low mcr
    lcc.preventive_maintenance_cost = Decimal("5000.00")
    lcc.lifecycle_stage = "late_life"
    lcc.recalculate_metrics()
    assert lcc.recommendation == "overhaul_refurbish"
    assert lcc.economic_eol_year == base_year + 6

    # 3. schedule_replacement via mcr >= 50%
    lcc.lifecycle_stage = "in_service"
    lcc.preventive_maintenance_cost = Decimal("50000.00")
    lcc.recalculate_metrics()
    assert lcc.recommendation == "schedule_replacement"
    assert lcc.economic_eol_year == base_year + 1

    # 3b. schedule_replacement via opex_to_capex_ratio >= 1.50
    lcc.preventive_maintenance_cost = Decimal("10000.00")
    lcc.energy_utility_cost = Decimal("140000.00")
    lcc.recalculate_metrics()
    assert lcc.opex_to_capex_ratio == Decimal("1.50")
    assert lcc.recommendation == "schedule_replacement"
    assert lcc.economic_eol_year == base_year + 1

    # 3c. schedule_replacement via end_of_life with mcr < 60%
    lcc.energy_utility_cost = Decimal("0.00")
    lcc.preventive_maintenance_cost = Decimal("59000.00")
    lcc.lifecycle_stage = "end_of_life"
    lcc.recalculate_metrics()
    assert lcc.recommendation == "schedule_replacement"
    assert lcc.economic_eol_year == base_year + 1

    # 4. dispose_retire via end_of_life/disposed AND mcr >= 60%
    lcc.preventive_maintenance_cost = Decimal("60000.00")
    lcc.lifecycle_stage = "end_of_life"
    lcc.recalculate_metrics()
    assert lcc.recommendation == "dispose_retire"
    assert lcc.economic_eol_year == base_year

    lcc.lifecycle_stage = "disposed"
    lcc.recalculate_metrics()
    assert lcc.recommendation == "dispose_retire"
    assert lcc.economic_eol_year == base_year


def test_assetanalytics_lcc_populate_from_asset_records_aggregation_and_isolation(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    asset_model_a,
    capitalization_a,
    capitalization_b,
    service_contract_a,
    service_contract_b,
    maintenance_log_a,
    maintenance_log_b,
    downtime_log_a,
    downtime_log_b,
    energy_reading_a,
    energy_reading_b,
    insurance_policy_a,
    insurance_policy_b,
    compliance_incident_a,
    compliance_incident_b,
    warranty_claim_a,
    warranty_claim_b,
    insurance_claim_a,
    insurance_claim_b,
    disposal_request_a,
    disposal_request_b,
    resale_listing_a,
    resale_listing_b,
    scrap_salvage_a,
    scrap_salvage_b,
    expense_account_a,
    accum_account_a,
    expense_account_b,
    accum_account_b,
    admin_user,
    vendor_party_a,
):
    today = timezone.localdate()

    # Link capitalization_a to fixed_asset_a & operational_asset_a and mark capitalized
    capitalization_a.fixed_asset = fixed_asset_a
    capitalization_a.operational_asset = operational_asset_a
    capitalization_a.status = "capitalized"
    capitalization_a.save()  # total_cost_basis = 125000.00, installation_cost = 1500.00

    # Tenant B capitalization must never leak
    capitalization_b.fixed_asset = fixed_asset_b
    capitalization_b.operational_asset = operational_asset_b
    capitalization_b.status = "capitalized"
    capitalization_b.save()

    # Posted depreciation for tenant A (1800.00), tenant B posted (833.33) must not leak
    AssetDepreciationSchedule.objects.create(
        tenant=tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        fiscal_year=today.year,
        period_number=1,
        period_frequency="monthly",
        schedule_date=today,
        depreciation_method="straight_line",
        starting_book_value=Decimal("120000.00"),
        depreciation_amount=Decimal("1800.00"),
        accumulated_depreciation_after=Decimal("1800.00"),
        ending_book_value=Decimal("118200.00"),
        expense_account=expense_account_a,
        accumulated_account=accum_account_a,
        status="posted",
    )
    AssetDepreciationSchedule.objects.create(
        tenant=tenant_b,
        fixed_asset=fixed_asset_b,
        operational_asset=operational_asset_b,
        fiscal_year=today.year,
        period_number=1,
        period_frequency="monthly",
        schedule_date=today,
        depreciation_method="straight_line",
        starting_book_value=Decimal("45000.00"),
        depreciation_amount=Decimal("833.33"),
        accumulated_depreciation_after=Decimal("833.33"),
        ending_book_value=Decimal("44166.67"),
        expense_account=expense_account_b,
        accumulated_account=accum_account_b,
        status="posted",
    )

    # Draft maintenance log must be excluded; create a posted PM log + posted CM log
    AssetMaintenanceLog.objects.create(
        tenant=tenant_a,
        maintenance_type="preventive_service",
        service_date=today,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        lead_technician=admin_user,
        service_vendor=vendor_party_a,
        labor_cost=Decimal("1000.00"),
        parts_cost=Decimal("500.00"),
        action_taken="Scheduled preventive service completed.",
        expense_account=expense_account_a,
        status="completed",
    )
    maintenance_log_a.status = "completed"  # corrective_repair, 800.00
    maintenance_log_a.save()
    maintenance_log_b.status = "completed"  # tenant B, must not leak
    maintenance_log_b.save()

    # Energy reading must be validated to be included
    energy_reading_a.status = "validated"
    energy_reading_a.save()
    energy_reading_b.status = "validated"
    energy_reading_b.save()

    # Warranty & insurance claims must be in approved/settled statuses
    warranty_claim_a.approved_amount = Decimal("2200.00")
    warranty_claim_a.claim_status = "approved"
    warranty_claim_a.save()
    warranty_claim_b.approved_amount = Decimal("9999.00")
    warranty_claim_b.claim_status = "approved"
    warranty_claim_b.save()

    insurance_claim_a.settlement_payout_amount = Decimal("4000.00")
    insurance_claim_a.claim_status = "settled_paid"
    insurance_claim_a.save()
    insurance_claim_b.settlement_payout_amount = Decimal("8888.00")
    insurance_claim_b.claim_status = "settled_paid"
    insurance_claim_b.save()

    # Scrap salvage settled
    scrap_salvage_a.status = "settled"
    scrap_salvage_a.save()  # net_salvage_recovery = 2050.00
    scrap_salvage_b.status = "settled"
    scrap_salvage_b.save()

    # Resale listing_a is already sold (net_sale_proceeds = 34675.00); disposal_request_a has residual 35000.00
    lcc = _assetanalytics_make_lcc(
        tenant_a,
        fixed_asset=fixed_asset_a,
        operational_asset=operational_asset_a,
        asset_model=asset_model_a,
        status="draft",
    )
    lcc.save()
    lcc.populate_from_asset_records()
    lcc.refresh_from_db()

    assert lcc.status == "calculated"
    assert lcc.acquisition_capital_cost == Decimal("123500.00")  # 125000 - 1500
    assert lcc.installation_commissioning_cost == Decimal("1500.00")
    assert lcc.preventive_maintenance_cost == Decimal("1500.00")
    assert lcc.corrective_maintenance_cost == Decimal("800.00")
    assert lcc.service_contract_cost == Decimal("12000.00")
    assert lcc.energy_utility_cost == Decimal("41.40")
    assert lcc.downtime_opportunity_cost == Decimal("450.00")
    # Insurance policy (12000.00) + compliance incident fine (5000.00) = 17000.00
    assert lcc.insurance_compliance_cost == Decimal("17000.00")
    assert lcc.accumulated_depreciation_cost == Decimal("1800.00")
    assert lcc.expected_salvage_value == Decimal("35000.00")
    # Warranty (2200) + Insurance (4000) + Resale (34675) + Scrap (2050) = 42925.00
    assert lcc.warranty_insurance_recoveries == Decimal("42925.00")
    # CRV filled from asset_model_a.estimated_replacement_cost
    assert lcc.current_replacement_value == Decimal("175000.00")


def test_assetanalytics_lcc_populate_fallbacks_no_assets_and_guards(
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
):
    # Fallback to FixedAsset acquisition_cost / accumulated_depreciation / salvage_value when no AssetCapitalization
    fixed_asset_a.accumulated_depreciation = Decimal("24000.00")
    fixed_asset_a.save()
    lcc_fa = _assetanalytics_make_lcc(tenant_a, fixed_asset=fixed_asset_a, status="reviewed")
    lcc_fa.save()
    lcc_fa.populate_from_asset_records()
    assert lcc_fa.status == "reviewed"  # non-draft preserved
    assert lcc_fa.acquisition_capital_cost == Decimal("120000.00")
    assert lcc_fa.accumulated_depreciation_cost == Decimal("24000.00")
    assert lcc_fa.expected_salvage_value == Decimal("12000.00")
    assert lcc_fa.current_replacement_value == Decimal("120000.00")

    # Fallback to scm.Asset.purchase_cost when only operational_asset linked
    operational_asset_a.purchase_cost = Decimal("55000.00")
    operational_asset_a.save()
    lcc_op = _assetanalytics_make_lcc(tenant_a, operational_asset=operational_asset_a, status="draft")
    lcc_op.save()
    lcc_op.populate_from_asset_records()
    assert lcc_op.status == "calculated"
    assert lcc_op.acquisition_capital_cost == Decimal("55000.00")

    # No linked assets still transitions draft -> calculated
    lcc_none = _assetanalytics_make_lcc(
        tenant_a,
        acquisition_capital_cost=Decimal("10000.00"),
        status="draft",
    )
    lcc_none.save()
    lcc_none.populate_from_asset_records()
    assert lcc_none.status == "calculated"
    assert lcc_none.total_lifecycle_cost == Decimal("10000.00")

    # Locked statuses raise ValidationError
    for locked_status in ("approved", "archived"):
        lcc_locked = _assetanalytics_make_lcc(tenant_a, status=locked_status)
        assert lcc_locked.is_locked is True
        with pytest.raises(ValidationError):
            lcc_locked.populate_from_asset_records()

    # None tenant_id returns early without crashing
    lcc_no_tenant = AssetLifecycleCostAnalysis(title="No Tenant")
    assert lcc_no_tenant.populate_from_asset_records() is None


def test_assetanalytics_lcc_bounds_and_monetary_validation(tenant_a):
    # Valid extremes pass
    valid_min = _assetanalytics_make_lcc(
        tenant_a,
        analysis_horizon_years=1,
        discount_rate_pct=Decimal("0.00"),
    )
    valid_min.full_clean()

    valid_max = _assetanalytics_make_lcc(
        tenant_a,
        analysis_horizon_years=50,
        discount_rate_pct=Decimal("100.00"),
    )
    valid_max.full_clean()

    # Horizon out of range
    for bad_horizon in (0, 51):
        bad = _assetanalytics_make_lcc(tenant_a, analysis_horizon_years=bad_horizon)
        with pytest.raises(ValidationError) as exc_info:
            bad.full_clean()
        assert "analysis_horizon_years" in exc_info.value.message_dict

    # Discount rate out of range
    for bad_rate in (Decimal("-0.01"), Decimal("100.01")):
        bad = _assetanalytics_make_lcc(tenant_a, discount_rate_pct=bad_rate)
        with pytest.raises(ValidationError) as exc_info:
            bad.full_clean()
        assert "discount_rate_pct" in exc_info.value.message_dict

    # Every monetary bucket rejects negatives
    monetary_fields = (
        "acquisition_capital_cost",
        "installation_commissioning_cost",
        "preventive_maintenance_cost",
        "corrective_maintenance_cost",
        "service_contract_cost",
        "energy_utility_cost",
        "downtime_opportunity_cost",
        "insurance_compliance_cost",
        "accumulated_depreciation_cost",
        "expected_salvage_value",
        "warranty_insurance_recoveries",
        "current_replacement_value",
    )
    for fname in monetary_fields:
        bad = _assetanalytics_make_lcc(tenant_a, **{fname: Decimal("-1.00")})
        with pytest.raises(ValidationError) as exc_info:
            bad.full_clean()
        assert fname in exc_info.value.message_dict


# =====================================================================
# 4. AssetReplacementPlan
# =====================================================================


def test_assetanalytics_rpl_recalculate_fci_priority_inflation_and_net_capital(tenant_a):
    current_year = timezone.localdate().year
    rpl = _assetanalytics_make_rpl(
        tenant_a,
        planned_replacement_year=current_year + 2,
        condition_score=Decimal("20.00"),
        criticality_weight=9,
        failure_risk_score=Decimal("80.00"),
        current_replacement_value=Decimal("200000.00"),
        deferred_maintenance_cost=Decimal("50000.00"),
        estimated_replacement_cost=Decimal("100000.00"),
        inflation_rate_pct=Decimal("5.00"),
        estimated_salvage_recovery=Decimal("10000.00"),
    )
    rpl.recalculate_metrics()

    # FCI = 50,000 / 200,000 * 100 = 25.00%
    assert rpl.fci_ratio_pct == Decimal("25.00")
    # Priority = (100 - 20)*0.40 + 80*0.35 + (9*10)*0.25 = 32 + 28 + 22.5 = 82.50 -> critical
    assert rpl.priority_score == Decimal("82.50")
    assert rpl.priority_band == "critical"
    # Inflation adjusted = 100,000 * (1.05)^2 = 110,250.00
    assert rpl.inflation_adjusted_cost == Decimal("110250.00")
    assert rpl.net_capital_requirement == Decimal("100250.00")


def test_assetanalytics_rpl_priority_band_thresholds_and_linked_autofill(
    tenant_a,
    condition_assessment_a,
    analytics_lcc_a,
):
    current_year = timezone.localdate().year
    # Critical: >= 75
    p_crit = _assetanalytics_make_rpl(
        tenant_a,
        condition_score=Decimal("0.00"),
        failure_risk_score=Decimal("50.00"),
        criticality_weight=7,
    )
    p_crit.recalculate_metrics()  # 40 + 17.5 + 17.5 = 75.00
    assert p_crit.priority_score == Decimal("75.00")
    assert p_crit.priority_band == "critical"

    # High: 50 .. 74.99
    p_high = _assetanalytics_make_rpl(
        tenant_a,
        condition_score=Decimal("50.00"),
        failure_risk_score=Decimal("50.00"),
        criticality_weight=5,
    )
    p_high.recalculate_metrics()  # 20 + 17.5 + 12.5 = 50.00
    assert p_high.priority_score == Decimal("50.00")
    assert p_high.priority_band == "high"

    # Medium: 25 .. 49.99
    p_med = _assetanalytics_make_rpl(
        tenant_a,
        condition_score=Decimal("80.00"),
        failure_risk_score=Decimal("20.00"),
        criticality_weight=4,
    )
    p_med.recalculate_metrics()  # 8 + 7 + 10 = 25.00
    assert p_med.priority_score == Decimal("25.00")
    assert p_med.priority_band == "medium"

    # Low: < 25
    p_low = _assetanalytics_make_rpl(
        tenant_a,
        condition_score=Decimal("95.00"),
        failure_risk_score=Decimal("10.00"),
        criticality_weight=1,
        current_replacement_value=Decimal("0.00"),
        deferred_maintenance_cost=Decimal("5000.00"),
        planned_replacement_year=current_year - 1,  # years_out clamped to 0
        estimated_replacement_cost=Decimal("1000.00"),
        estimated_salvage_recovery=Decimal("5000.00"),
    )
    p_low.recalculate_metrics()  # 2 + 3.5 + 2.5 = 8.00
    assert p_low.priority_score == Decimal("8.00")
    assert p_low.priority_band == "low"
    assert p_low.fci_ratio_pct == Decimal("0.00")
    assert p_low.inflation_adjusted_cost == Decimal("1000.00")
    assert p_low.net_capital_requirement == Decimal("0.00")

    # Linked condition_assessment (health_score=82) and lifecycle_analysis (CRV=140000) auto-fill
    p_linked = _assetanalytics_make_rpl(
        tenant_a,
        condition_assessment=condition_assessment_a,
        lifecycle_analysis=analytics_lcc_a,
        condition_score=Decimal("50.00"),
        current_replacement_value=Decimal("0.00"),
    )
    p_linked.recalculate_metrics()
    assert p_linked.condition_score == Decimal("82.00")
    assert p_linked.current_replacement_value == Decimal("140000.00")


def test_assetanalytics_rpl_transitions_and_lock_statuses(tenant_a):
    expected_transitions = {
        "forecasted": {"proposed", "approved", "deferred", "cancelled"},
        "proposed": {"approved", "deferred", "cancelled"},
        "approved": {"scheduled", "deferred", "cancelled"},
        "scheduled": {"executed", "deferred", "cancelled"},
        "deferred": {"proposed", "cancelled"},
        "executed": set(),
        "cancelled": set(),
    }
    assert AssetReplacementPlan.ALLOWED_TRANSITIONS == expected_transitions
    assert AssetReplacementPlan.LOCKED_STATUSES == {"approved", "scheduled", "executed", "cancelled"}

    for status, _ in AssetReplacementPlan.STATUS_CHOICES:
        rpl = _assetanalytics_make_rpl(tenant_a, status=status)
        assert rpl.is_locked is (status in {"approved", "scheduled", "executed", "cancelled"})


def test_assetanalytics_rpl_bounds_and_monetary_validation(tenant_a):
    # Valid extremes
    _assetanalytics_make_rpl(
        tenant_a,
        criticality_weight=1,
        condition_score=Decimal("0.00"),
        failure_risk_score=Decimal("0.00"),
        inflation_rate_pct=Decimal("0.00"),
        planned_replacement_year=2000,
        remaining_useful_life_months=0,
    ).full_clean()
    _assetanalytics_make_rpl(
        tenant_a,
        criticality_weight=10,
        condition_score=Decimal("100.00"),
        failure_risk_score=Decimal("100.00"),
        inflation_rate_pct=Decimal("50.00"),
        planned_replacement_year=2100,
        remaining_useful_life_months=1200,
    ).full_clean()

    invalid_cases = [
        ("criticality_weight", 0),
        ("criticality_weight", 11),
        ("condition_score", Decimal("-0.01")),
        ("condition_score", Decimal("100.01")),
        ("failure_risk_score", Decimal("-0.01")),
        ("failure_risk_score", Decimal("100.01")),
        ("inflation_rate_pct", Decimal("-0.01")),
        ("inflation_rate_pct", Decimal("50.01")),
        ("planned_replacement_year", 1999),
        ("planned_replacement_year", 2101),
        ("remaining_useful_life_months", 1201),
        ("current_replacement_value", Decimal("-1.00")),
        ("deferred_maintenance_cost", Decimal("-1.00")),
        ("estimated_replacement_cost", Decimal("-1.00")),
        ("estimated_salvage_recovery", Decimal("-1.00")),
        ("deferral_penalty_cost", Decimal("-1.00")),
    ]
    for field, val in invalid_cases:
        bad = _assetanalytics_make_rpl(tenant_a, **{field: val})
        with pytest.raises(ValidationError) as exc_info:
            bad.full_clean()
        assert field in exc_info.value.message_dict


# =====================================================================
# 5. AssetPortfolioScenario
# =====================================================================


def test_assetanalytics_scenario_run_simulation_bau_and_scope_isolation(
    tenant_a,
    tenant_b,
    org_unit_a,
    category_root_a,
    category_child_a,
    analytics_rpl_a,
    analytics_rpl_b,
    analytics_lcc_a,
    analytics_lcc_b,
    condition_assessment_a,
    condition_assessment_b,
    asset_risk_register_a,
    asset_risk_register_b,
    operational_asset_a,
):
    # Ensure operational_asset_a belongs to org_unit_a so cond_qs and risk_qs include it
    operational_asset_a.org_unit = org_unit_a
    operational_asset_a.save()

    # Out-of-scope org_unit & category records in tenant_a must be excluded when scoped
    other_org = OrgUnit.objects.create(tenant=tenant_a, name="Other Plant", kind="department")
    out_of_scope_rpl = _assetanalytics_make_rpl(
        tenant_a,
        title="Out of scope RPL",
        org_unit=other_org,
        asset_category=category_child_a,
        estimated_replacement_cost=Decimal("999999.00"),
        current_replacement_value=Decimal("999999.00"),
        deferred_maintenance_cost=Decimal("999999.00"),
    )
    out_of_scope_rpl.save()

    scen = _assetanalytics_make_scenario(
        tenant_a,
        name="Scoped BAU Scenario",
        scenario_type="baseline_bau",
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
        horizon_years=5,
        discount_rate_pct=Decimal("8.00"),
        status="draft",
    )
    scen.save()
    scen.run_simulation()
    scen.refresh_from_db()

    assert scen.status == "simulated"
    # Baseline reads only analytics_rpl_a (not out_of_scope_rpl, not analytics_rpl_b)
    assert scen.baseline_capex_total == analytics_rpl_a.inflation_adjusted_cost
    assert scen.simulated_capex_total == analytics_rpl_a.inflation_adjusted_cost
    assert scen.capex_variance_amount == Decimal("0.00")
    assert scen.baseline_opex_maintenance == analytics_lcc_a.total_maintenance_amount
    assert scen.simulated_opex_maintenance == analytics_lcc_a.total_maintenance_amount
    assert scen.opex_savings_amount == Decimal("0.00")
    assert scen.baseline_deferred_backlog == analytics_rpl_a.deferred_maintenance_cost
    assert scen.simulated_deferred_backlog == analytics_rpl_a.deferred_maintenance_cost
    assert scen.baseline_avg_health_score == Decimal("82.00")
    assert scen.simulated_avg_health_score == Decimal("82.00")
    assert scen.baseline_risk_exposure == Decimal("50000.00")
    assert scen.simulated_risk_exposure == Decimal("50000.00")
    assert scen.net_present_value == Decimal("0.00")
    assert scen.payback_period_years == Decimal("0.00")
    assert scen.benefit_cost_ratio == Decimal("0.00")


def test_assetanalytics_scenario_all_strategy_types_and_npv_payback_bcr(
    tenant_a,
    org_unit_a,
    category_root_a,
    analytics_rpl_a,
    analytics_lcc_a,
    condition_assessment_a,
    asset_risk_register_a,
    operational_asset_a,
):
    operational_asset_a.org_unit = org_unit_a
    operational_asset_a.save()

    # 1. accelerated_replacement: higher CapEx, lower OpEx, lower backlog, higher health, lower risk, positive benefits
    accel = _assetanalytics_make_scenario(
        tenant_a,
        name="Accelerated Scenario",
        scenario_type="accelerated_replacement",
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
        horizon_years=5,
        discount_rate_pct=Decimal("8.00"),
        acceleration_months=12,
        maintenance_efficiency_gain_pct=Decimal("10.00"),
        status="under_review",
    )
    accel.save()
    accel.run_simulation()
    assert accel.status == "under_review"  # non-draft preserved
    assert accel.simulated_capex_total > accel.baseline_capex_total
    assert accel.simulated_opex_maintenance < accel.baseline_opex_maintenance
    assert accel.opex_savings_amount > Decimal("0.00")
    assert accel.simulated_deferred_backlog < accel.baseline_deferred_backlog
    assert accel.simulated_avg_health_score == Decimal("91.50")  # 82 + 9.50
    assert accel.simulated_risk_exposure == Decimal("35000.00")  # 50000 * 0.70
    assert accel.payback_period_years > Decimal("0.00")
    assert accel.benefit_cost_ratio > Decimal("0.00")

    # 2. fleet_expansion
    exp = _assetanalytics_make_scenario(
        tenant_a,
        scenario_type="fleet_expansion",
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
        fleet_growth_pct=Decimal("20.00"),
    )
    exp.save()
    exp.run_simulation()
    assert exp.simulated_capex_total == q2(exp.baseline_capex_total * Decimal("1.20"))
    assert exp.simulated_avg_health_score == Decimal("85.50")

    # 3. site_consolidation
    consol = _assetanalytics_make_scenario(
        tenant_a,
        scenario_type="site_consolidation",
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
        consolidation_reduction_pct=Decimal("20.00"),
    )
    consol.save()
    consol.run_simulation()
    assert consol.simulated_capex_total == q2(consol.baseline_capex_total * Decimal("0.80"))
    assert consol.simulated_avg_health_score == Decimal("86.00")

    # 4. budget_constrained WITH annual_capex_budget_limit capping sim_capex
    b_capped = _assetanalytics_make_scenario(
        tenant_a,
        scenario_type="budget_constrained",
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
        horizon_years=5,
        annual_capex_budget_limit=Decimal("20000.00"),  # ceiling = 100,000 < ~161,200
    )
    b_capped.save()
    b_capped.run_simulation()
    assert b_capped.simulated_capex_total == Decimal("100000.00")
    assert b_capped.simulated_deferred_backlog > b_capped.baseline_deferred_backlog
    assert b_capped.simulated_avg_health_score == Decimal("77.50")  # 82 - 4.50

    # 5. budget_constrained WITHOUT budget limit (0.00 -> 75% capex, +25% unmet backlog)
    b_uncapped = _assetanalytics_make_scenario(
        tenant_a,
        scenario_type="budget_constrained",
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
        annual_capex_budget_limit=Decimal("0.00"),
    )
    b_uncapped.save()
    b_uncapped.run_simulation()
    assert b_uncapped.simulated_capex_total == q2(b_uncapped.baseline_capex_total * Decimal("0.75"))

    # 6. deferred_maintenance_impact
    def_maint = _assetanalytics_make_scenario(
        tenant_a,
        scenario_type="deferred_maintenance_impact",
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
    )
    def_maint.save()
    def_maint.run_simulation()
    assert def_maint.simulated_capex_total == q2(def_maint.baseline_capex_total * Decimal("0.60"))
    assert def_maint.simulated_opex_maintenance == q2(def_maint.baseline_opex_maintenance * Decimal("1.18"))
    assert def_maint.simulated_avg_health_score == Decimal("74.00")  # 82 - 8.00

    # 7. sustainability_retrofit
    retro = _assetanalytics_make_scenario(
        tenant_a,
        scenario_type="sustainability_retrofit",
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
    )
    retro.save()
    retro.run_simulation()
    assert retro.simulated_capex_total == q2(retro.baseline_capex_total * Decimal("1.12"))
    assert retro.simulated_avg_health_score == Decimal("88.00")  # 82 + 6.00


def test_assetanalytics_scenario_baseline_fallback_lock_and_validation(
    tenant_a,
    analytics_scenario_base_a,
    analytics_scenario_locked_a,
):
    # Locked scenario raises ValidationError on run_simulation
    assert analytics_scenario_locked_a.is_locked is True
    with pytest.raises(ValidationError):
        analytics_scenario_locked_a.run_simulation()

    archived = _assetanalytics_make_scenario(tenant_a, status="archived")
    assert archived.is_locked is True
    with pytest.raises(ValidationError):
        archived.run_simulation()

    # None tenant_id returns early without crashing
    assert AssetPortfolioScenario(name="No Tenant").run_simulation() is None

    # Self-reference baseline_scenario raises ValidationError
    analytics_scenario_base_a.baseline_scenario = analytics_scenario_base_a
    with pytest.raises(ValidationError) as exc_info:
        analytics_scenario_base_a.full_clean()
    assert "baseline_scenario" in exc_info.value.message_dict
    analytics_scenario_base_a.baseline_scenario = None

    # Fallback to baseline_scenario when tenant has no active plans/LCC in a brand-new org_unit
    empty_org = OrgUnit.objects.create(tenant=tenant_a, name="Empty Org", kind="department")
    derived = _assetanalytics_make_scenario(
        tenant_a,
        name="Derived From Baseline",
        scope_org_unit=empty_org,
        baseline_scenario=analytics_scenario_base_a,
    )
    derived.save()
    derived.run_simulation()
    assert derived.baseline_capex_total == analytics_scenario_base_a.baseline_capex_total
    assert derived.baseline_opex_maintenance == analytics_scenario_base_a.baseline_opex_maintenance

    # Fallback to annual_capex_budget_limit * horizon when no plans and no baseline
    budget_only = _assetanalytics_make_scenario(
        tenant_a,
        name="Budget Limit Fallback",
        scope_org_unit=empty_org,
        horizon_years=4,
        annual_capex_budget_limit=Decimal("50000.00"),
    )
    budget_only.save()
    budget_only.run_simulation()
    assert budget_only.baseline_capex_total == Decimal("200000.00")
    assert budget_only.baseline_opex_maintenance == Decimal("40000.00")  # 20% of base_capex

    # Bounds validation
    valid_min = _assetanalytics_make_scenario(
        tenant_a,
        horizon_years=1,
        acceleration_months=-60,
        fleet_growth_pct=Decimal("-95.00"),
        consolidation_reduction_pct=Decimal("0.00"),
        maintenance_efficiency_gain_pct=Decimal("0.00"),
        base_fiscal_year=2000,
    )
    valid_min.full_clean()

    valid_max = _assetanalytics_make_scenario(
        tenant_a,
        horizon_years=30,
        acceleration_months=120,
        fleet_growth_pct=Decimal("500.00"),
        consolidation_reduction_pct=Decimal("100.00"),
        maintenance_efficiency_gain_pct=Decimal("100.00"),
        base_fiscal_year=2100,
    )
    valid_max.full_clean()

    invalid_cases = [
        ("horizon_years", 0),
        ("horizon_years", 31),
        ("acceleration_months", -61),
        ("acceleration_months", 121),
        ("fleet_growth_pct", Decimal("-95.01")),
        ("fleet_growth_pct", Decimal("500.01")),
        ("consolidation_reduction_pct", Decimal("-0.01")),
        ("consolidation_reduction_pct", Decimal("100.01")),
        ("maintenance_efficiency_gain_pct", Decimal("-0.01")),
        ("maintenance_efficiency_gain_pct", Decimal("100.01")),
        ("base_fiscal_year", 1999),
        ("base_fiscal_year", 2101),
        ("annual_capex_budget_limit", Decimal("-1.00")),
        ("discount_rate_pct", Decimal("-0.01")),
        ("discount_rate_pct", Decimal("100.01")),
        ("inflation_rate_pct", Decimal("-0.01")),
        ("inflation_rate_pct", Decimal("50.01")),
    ]
    for field, val in invalid_cases:
        bad = _assetanalytics_make_scenario(tenant_a, **{field: val})
        with pytest.raises(ValidationError) as exc_info:
            bad.full_clean()
        assert field in exc_info.value.message_dict


# =====================================================================
# 6. AssetExecutiveScorecard
# =====================================================================


def test_assetanalytics_scorecard_period_bounds_and_lock_statuses(tenant_a):
    today = timezone.localdate()

    # period_end == period_start passes
    same_day = _assetanalytics_make_scorecard(tenant_a, period_start=today, period_end=today)
    same_day.full_clean()

    # period_end < period_start fails
    bad_period = _assetanalytics_make_scorecard(
        tenant_a,
        period_start=today,
        period_end=today - timedelta(days=1),
    )
    with pytest.raises(ValidationError) as exc_info:
        bad_period.full_clean()
    assert "period_end" in exc_info.value.message_dict

    for bad_mcr in (Decimal("-0.01"), Decimal("100.01")):
        bad = _assetanalytics_make_scorecard(tenant_a, target_mcr_pct=bad_mcr)
        with pytest.raises(ValidationError) as exc_info:
            bad.full_clean()
        assert "target_mcr_pct" in exc_info.value.message_dict

    for bad_comp in (Decimal("-0.01"), Decimal("100.01")):
        bad = _assetanalytics_make_scorecard(tenant_a, target_compliance_rate_pct=bad_comp)
        with pytest.raises(ValidationError) as exc_info:
            bad.full_clean()
        assert "target_compliance_rate_pct" in exc_info.value.message_dict

    for st in ("published", "board_approved", "archived"):
        locked = _assetanalytics_make_scorecard(tenant_a, status=st)
        assert locked.is_locked is True
        with pytest.raises(ValidationError):
            locked.compute_from_live_portfolio()

    assert _assetanalytics_make_scorecard(tenant_a, status="draft").is_locked is False
    assert AssetExecutiveScorecard(title="No Tenant").compute_from_live_portfolio() is None


def test_assetanalytics_scorecard_compute_isolation_org_category_period_and_tenant(
    tenant_a,
    tenant_b,
    org_unit_a,
    org_unit_b,
    category_root_a,
    category_child_a,
    location_a,
    asset_account_a,
    accum_account_a,
    expense_account_a,
    compliance_framework_a,
    vendor_party_a,
    admin_user,
    admin_b,
    asset_risk_register_b,
    compliance_incident_b,
):
    today = timezone.localdate()
    p_start = today - timedelta(days=30)
    p_end = today
    out_of_period_date = today - timedelta(days=60)

    other_org = OrgUnit.objects.create(tenant=tenant_a, name="Secondary Org", kind="department")

    # In-scope FixedAsset & scm.Asset (org_unit_a)
    fa_in = FixedAsset.objects.create(
        tenant=tenant_a,
        name="In-Scope CNC",
        category="Machinery",
        acquisition_cost=Decimal("100000.00"),
        accumulated_depreciation=Decimal("20000.00"),
        salvage_value=Decimal("5000.00"),
        useful_life_months=60,
        method="straight_line",
        status="active",
        asset_account=asset_account_a,
        accumulated_account=accum_account_a,
        expense_account=expense_account_a,
        in_service_date=p_start,
    )
    op_in = Asset.objects.create(
        tenant=tenant_a,
        code="AST-IN-01",
        name="In-Scope Operational Asset",
        asset_type="machine",
        location=location_a,
        org_unit=org_unit_a,
        fixed_asset=fa_in,
    )

    # Out-of-scope FixedAsset & scm.Asset (other_org) -> must NOT leak into org_unit_a scorecard
    fa_other = FixedAsset.objects.create(
        tenant=tenant_a,
        name="Other Org Press",
        category="Machinery",
        acquisition_cost=Decimal("500000.00"),
        accumulated_depreciation=Decimal("50000.00"),
        salvage_value=Decimal("10000.00"),
        useful_life_months=60,
        method="straight_line",
        status="active",
        asset_account=asset_account_a,
        accumulated_account=accum_account_a,
        expense_account=expense_account_a,
        in_service_date=p_start,
    )
    op_other = Asset.objects.create(
        tenant=tenant_a,
        code="AST-OTHER-01",
        name="Other Org Asset",
        asset_type="machine",
        location=location_a,
        org_unit=other_org,
        fixed_asset=fa_other,
    )

    # Replacement plans: 1 in-scope (org_unit_a + category_root_a), 1 wrong category, 1 wrong org_unit
    rpl_in = _assetanalytics_make_rpl(
        tenant_a,
        title="In-Scope Plan",
        org_unit=org_unit_a,
        asset_category=category_root_a,
        funding_status="unfunded",
        current_replacement_value=Decimal("200000.00"),
        deferred_maintenance_cost=Decimal("20000.00"),
        estimated_replacement_cost=Decimal("100000.00"),
        planned_replacement_year=today.year,
    )
    rpl_in.save()

    rpl_wrong_cat = _assetanalytics_make_rpl(
        tenant_a,
        title="Wrong Category Plan",
        org_unit=org_unit_a,
        asset_category=category_child_a,
        funding_status="unfunded",
        current_replacement_value=Decimal("900000.00"),
        deferred_maintenance_cost=Decimal("900000.00"),
        estimated_replacement_cost=Decimal("900000.00"),
        planned_replacement_year=today.year,
    )
    rpl_wrong_cat.save()

    rpl_wrong_org = _assetanalytics_make_rpl(
        tenant_a,
        title="Wrong Org Plan",
        org_unit=other_org,
        asset_category=category_root_a,
        funding_status="unfunded",
        current_replacement_value=Decimal("800000.00"),
        deferred_maintenance_cost=Decimal("800000.00"),
        estimated_replacement_cost=Decimal("800000.00"),
        planned_replacement_year=today.year,
    )
    rpl_wrong_org.save()

    # Maintenance logs: 1 PM in-period in-org (2000), 1 CM in-period in-org (1000),
    # 1 out-of-period (9999), 1 wrong org (9999)
    AssetMaintenanceLog.objects.create(
        tenant=tenant_a,
        maintenance_type="preventive_service",
        service_date=today - timedelta(days=5),
        fixed_asset=fa_in,
        operational_asset=op_in,
        lead_technician=admin_user,
        service_vendor=vendor_party_a,
        labor_cost=Decimal("2000.00"),
        action_taken="In-period PM service completed.",
        expense_account=expense_account_a,
        status="completed",
    )
    AssetMaintenanceLog.objects.create(
        tenant=tenant_a,
        maintenance_type="corrective_repair",
        service_date=today - timedelta(days=2),
        fixed_asset=fa_in,
        operational_asset=op_in,
        lead_technician=admin_user,
        service_vendor=vendor_party_a,
        labor_cost=Decimal("1000.00"),
        action_taken="In-period CM repair completed.",
        expense_account=expense_account_a,
        status="completed",
    )
    AssetMaintenanceLog.objects.create(
        tenant=tenant_a,
        maintenance_type="corrective_repair",
        service_date=out_of_period_date,
        fixed_asset=fa_in,
        operational_asset=op_in,
        lead_technician=admin_user,
        service_vendor=vendor_party_a,
        labor_cost=Decimal("9999.00"),
        action_taken="Out-of-period CM repair.",
        expense_account=expense_account_a,
        status="completed",
    )
    AssetMaintenanceLog.objects.create(
        tenant=tenant_a,
        maintenance_type="corrective_repair",
        service_date=today - timedelta(days=1),
        fixed_asset=fa_other,
        operational_asset=op_other,
        lead_technician=admin_user,
        service_vendor=vendor_party_a,
        labor_cost=Decimal("9999.00"),
        action_taken="Other org CM repair.",
        expense_account=expense_account_a,
        status="completed",
    )

    # Capitalizations: in-period in-org (50,000), out-of-period (77,777)
    AssetCapitalization.objects.create(
        tenant=tenant_a,
        asset_name="In-Period Cap",
        title="In-Period Cap",
        fixed_asset=fa_in,
        operational_asset=op_in,
        purchase_cost=Decimal("50000.00"),
        useful_life_months=60,
        in_service_date=today - timedelta(days=10),
        status="capitalized",
    )
    AssetCapitalization.objects.create(
        tenant=tenant_a,
        asset_name="Out-of-Period Cap",
        title="Out-of-Period Cap",
        fixed_asset=fa_in,
        operational_asset=op_in,
        purchase_cost=Decimal("77777.00"),
        useful_life_months=60,
        in_service_date=out_of_period_date,
        status="capitalized",
    )

    # OEE: in-period in-org (avail=90, oee=80), out-of-period (avail=10, oee=10), wrong org (avail=10, oee=10)
    AssetOeeRecord.objects.create(
        tenant=tenant_a,
        operational_asset=op_in,
        recorded_by=admin_user,
        record_date=today - timedelta(days=3),
        planned_production_time_minutes=Decimal("100.00"),
        operating_time_minutes=Decimal("90.00"),
        ideal_cycle_time_seconds=Decimal("60.00"),
        total_units_produced=80,
        good_units_produced=80,
    )
    AssetOeeRecord.objects.create(
        tenant=tenant_a,
        operational_asset=op_in,
        recorded_by=admin_user,
        record_date=out_of_period_date,
        planned_production_time_minutes=Decimal("100.00"),
        operating_time_minutes=Decimal("10.00"),
        ideal_cycle_time_seconds=Decimal("60.00"),
        total_units_produced=10,
        good_units_produced=10,
    )
    AssetOeeRecord.objects.create(
        tenant=tenant_a,
        operational_asset=op_other,
        recorded_by=admin_user,
        record_date=today - timedelta(days=3),
        planned_production_time_minutes=Decimal("100.00"),
        operating_time_minutes=Decimal("10.00"),
        ideal_cycle_time_seconds=Decimal("60.00"),
        total_units_produced=10,
        good_units_produced=10,
    )

    # Compliance Audits: in-period in-org (40/40 = 100%), out-of-period (0/100)
    AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        title="In-Period Audit",
        framework=compliance_framework_a,
        asset=op_in,
        audit_date=today - timedelta(days=5),
        total_checkpoints=40,
        passed_checkpoints=40,
        status="completed",
    )
    AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        title="Old Audit",
        framework=compliance_framework_a,
        asset=op_in,
        audit_date=out_of_period_date,
        total_checkpoints=100,
        passed_checkpoints=0,
        status="completed",
    )

    # Open incidents: 0 for op_in, 1 open for op_other (must not leak), 1 open in tenant_b (must not leak)
    AssetComplianceIncident.objects.create(
        tenant=tenant_a,
        title="Other Org Open Incident",
        incident_date=timezone.now(),
        discovery_date=today,
        asset=op_other,
        status="open",
    )

    # Risk register: in-scope (15,000), wrong category (99,000), wrong org (99,000)
    AssetRiskRegister.objects.create(
        tenant=tenant_a,
        title="In-Scope Risk",
        asset=op_in,
        category=category_root_a,
        financial_exposure_amount=Decimal("15000.00"),
        status="identified",
    )
    AssetRiskRegister.objects.create(
        tenant=tenant_a,
        title="Wrong Cat Risk",
        asset=op_in,
        category=category_child_a,
        financial_exposure_amount=Decimal("99000.00"),
        status="identified",
    )
    AssetRiskRegister.objects.create(
        tenant=tenant_a,
        title="Wrong Org Risk",
        asset=op_other,
        category=category_root_a,
        financial_exposure_amount=Decimal("99000.00"),
        status="identified",
    )

    scorecard = _assetanalytics_make_scorecard(
        tenant_a,
        period_start=p_start,
        period_end=p_end,
        org_unit=org_unit_a,
        asset_category=category_root_a,
        target_asset_roi_pct=Decimal("12.00"),
        target_mcr_pct=Decimal("3.50"),
        target_compliance_rate_pct=Decimal("95.00"),
        annual_asset_return_amount=Decimal("16000.00"),  # 16k / 80k NBV = 20% ROI >= 12%
        status="draft",
    )
    scorecard.save()
    scorecard.compute_from_live_portfolio()
    scorecard.refresh_from_db()

    assert scorecard.total_asset_count == 1
    assert scorecard.total_net_book_value == Decimal("80000.00")  # 100k - 20k
    assert scorecard.gross_replacement_value == Decimal("200000.00")
    assert scorecard.unfunded_replacement_backlog == Decimal("100000.00")
    assert scorecard.portfolio_fci_pct == Decimal("10.00")  # 20k / 200k
    assert scorecard.total_maintenance_spend == Decimal("3000.00")  # 2k + 1k
    assert scorecard.maintenance_cost_to_rav_pct == Decimal("1.50")  # 3k / 200k <= 3.50
    assert scorecard.planned_maintenance_ratio_pct == Decimal("50.00")  # 1/2
    assert scorecard.annual_asset_return_amount == Decimal("16000.00")  # explicit override preserved
    assert scorecard.asset_roi_pct == Decimal("20.00")
    assert scorecard.capex_budget_utilization_pct == Decimal("50.00")  # 50k / 100k
    assert scorecard.fleet_availability_pct == Decimal("90.00")
    assert scorecard.portfolio_oee_pct == Decimal("80.00")
    assert scorecard.compliance_audit_pass_rate_pct == Decimal("100.00")
    assert scorecard.open_compliance_incidents == 0
    assert scorecard.total_risk_exposure_amount == Decimal("15000.00")
    assert scorecard.rag_status == "green"


def test_assetanalytics_scorecard_rag_grading_and_recovery_return_computation(
    tenant_a,
    org_unit_a,
    category_root_a,
    location_a,
    asset_account_a,
    accum_account_a,
    expense_account_a,
    compliance_framework_a,
    disposal_request_a,
    fixed_asset_a,
    operational_asset_a,
    vendor_party_a,
    admin_user,
):
    today = timezone.localdate()
    p_start = today - timedelta(days=30)
    p_end = today

    operational_asset_a.org_unit = org_unit_a
    operational_asset_a.fixed_asset = fixed_asset_a
    operational_asset_a.save()
    disposal_request_a.cost_center = org_unit_a
    disposal_request_a.category = category_root_a
    disposal_request_a.save()

    # Resale within period & org_unit & category -> 8,640.00 return
    AssetResaleListing.objects.create(
        tenant=tenant_a,
        disposal_request=disposal_request_a,
        fixed_asset=fixed_asset_a,
        buyer=vendor_party_a,
        managed_by=admin_user,
        listing_date=today - timedelta(days=5),
        net_sale_proceeds=Decimal("8640.00"),
        status="sold",
    )
    # Out-of-period resale must be ignored
    AssetResaleListing.objects.create(
        tenant=tenant_a,
        disposal_request=disposal_request_a,
        fixed_asset=fixed_asset_a,
        buyer=vendor_party_a,
        managed_by=admin_user,
        listing_date=today - timedelta(days=90),
        net_sale_proceeds=Decimal("50000.00"),
        status="sold",
    )

    # NBV = 120k - 0 = 120k -> ROI = 8640 / 120000 * 100 = 7.20% (< target 12.00% -> 1 miss)
    # MCR = 0 / 120000 = 0% (<= 3.50% -> 0 misses)
    sc = _assetanalytics_make_scorecard(
        tenant_a,
        period_start=p_start,
        period_end=p_end,
        org_unit=org_unit_a,
        asset_category=category_root_a,
        annual_asset_return_amount=Decimal("0.00"),
        target_asset_roi_pct=Decimal("12.00"),
        target_mcr_pct=Decimal("3.50"),
        target_compliance_rate_pct=Decimal("95.00"),
    )
    sc.save()
    sc.compute_from_live_portfolio()
    assert sc.annual_asset_return_amount == Decimal("8640.00")
    assert sc.asset_roi_pct == Decimal("7.20")
    assert sc.rag_status == "amber"  # 1 miss

    # Add failed compliance audit -> 2 misses -> red
    AssetComplianceAudit.objects.create(
        tenant=tenant_a,
        title="Failed Audit",
        framework=compliance_framework_a,
        asset=operational_asset_a,
        audit_date=today - timedelta(days=2),
        total_checkpoints=20,
        passed_checkpoints=10,  # 50% < 95%
        status="completed",
    )
    sc.annual_asset_return_amount = Decimal("0.00")
    sc.compute_from_live_portfolio()
    assert sc.compliance_audit_pass_rate_pct == Decimal("50.00")
    assert sc.rag_status == "red"

    # Fix misses (high return & low target compliance) -> 0 misses, but 3 open incidents -> red
    sc.annual_asset_return_amount = Decimal("30000.00")
    sc.target_compliance_rate_pct = Decimal("40.00")
    for idx in range(3):
        AssetComplianceIncident.objects.create(
            tenant=tenant_a,
            title=f"Open Incident {idx}",
            incident_date=timezone.now(),
            discovery_date=today,
            asset=operational_asset_a,
            status="open",
        )
    sc.compute_from_live_portfolio()
    assert sc.open_compliance_incidents == 3
    assert sc.rag_status == "red"

    # Close 2 incidents leaving 1 open incident -> 0 misses + 1 open incident -> amber
    for inc in AssetComplianceIncident.objects.filter(tenant=tenant_a, asset=operational_asset_a)[:2]:
        inc.status = "closed"
        inc.save()
    sc.compute_from_live_portfolio()
    assert sc.open_compliance_incidents == 1
    assert sc.rag_status == "amber"


# =====================================================================
# 7. Cross-Tenant FK Rejection & Global Currency Allowance
# =====================================================================


def test_assetanalytics_cross_tenant_fk_rejection_and_global_currency(
    tenant_a,
    tenant_b,
    currency_usd,
    fixed_asset_b,
    operational_asset_b,
    category_root_b,
    asset_model_b,
    org_unit_b,
    location_b,
    condition_assessment_b,
    analytics_lcc_b,
    requisition_b,
    analytics_scenario_b,
    admin_b,
):
    budget_b = Budget.objects.create(tenant=tenant_b, name="Globex CapEx Budget")

    # Global accounting.Currency is allowed on tenant_a models
    _assetanalytics_make_lcc(tenant_a, currency=currency_usd).full_clean()
    _assetanalytics_make_rpl(tenant_a, currency=currency_usd).full_clean()
    _assetanalytics_make_scenario(tenant_a, currency=currency_usd).full_clean()
    _assetanalytics_make_scorecard(tenant_a, currency=currency_usd).full_clean()

    # 1. AssetLifecycleCostAnalysis cross-tenant FKs
    lcc_foreign = {
        "fixed_asset": fixed_asset_b,
        "operational_asset": operational_asset_b,
        "asset_category": category_root_b,
        "asset_model": asset_model_b,
        "org_unit": org_unit_b,
        "analyzed_by": admin_b,
    }
    for fname, foreign_obj in lcc_foreign.items():
        obj = _assetanalytics_make_lcc(tenant_a, **{fname: foreign_obj})
        with pytest.raises(ValidationError) as exc_info:
            obj.full_clean()
        assert fname in exc_info.value.message_dict

    # 2. AssetReplacementPlan cross-tenant FKs
    rpl_foreign = {
        "fixed_asset": fixed_asset_b,
        "operational_asset": operational_asset_b,
        "asset_category": category_root_b,
        "asset_model": asset_model_b,
        "org_unit": org_unit_b,
        "location": location_b,
        "condition_assessment": condition_assessment_b,
        "lifecycle_analysis": analytics_lcc_b,
        "capital_budget": budget_b,
        "linked_requisition": requisition_b,
        "planner": admin_b,
    }
    for fname, foreign_obj in rpl_foreign.items():
        obj = _assetanalytics_make_rpl(tenant_a, **{fname: foreign_obj})
        with pytest.raises(ValidationError) as exc_info:
            obj.full_clean()
        assert fname in exc_info.value.message_dict

    # 3. AssetPortfolioScenario cross-tenant FKs
    scen_foreign = {
        "scope_org_unit": org_unit_b,
        "scope_category": category_root_b,
        "baseline_scenario": analytics_scenario_b,
        "owner": admin_b,
    }
    for fname, foreign_obj in scen_foreign.items():
        obj = _assetanalytics_make_scenario(tenant_a, **{fname: foreign_obj})
        with pytest.raises(ValidationError) as exc_info:
            obj.full_clean()
        assert fname in exc_info.value.message_dict

    # 4. AssetExecutiveScorecard cross-tenant FKs
    scorecard_foreign = {
        "org_unit": org_unit_b,
        "asset_category": category_root_b,
        "prepared_by": admin_b,
        "approved_by": admin_b,
    }
    for fname, foreign_obj in scorecard_foreign.items():
        obj = _assetanalytics_make_scorecard(tenant_a, **{fname: foreign_obj})
        with pytest.raises(ValidationError) as exc_info:
            obj.full_clean()
        assert fname in exc_info.value.message_dict
