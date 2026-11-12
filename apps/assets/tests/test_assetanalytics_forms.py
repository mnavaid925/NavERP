"""
Unit, validation, tenant-isolation, security, widget, and round-trip tests
for Sub-module 11.14: Asset Analytics & Business Intelligence Forms.

Covers AssetLifecycleCostAnalysisForm, AssetReplacementPlanForm,
AssetPortfolioScenarioForm, and AssetExecutiveScorecardForm:
1. Package root re-exports vs direct sub-package imports.
2. Meta.fields contract, strict security/system/computed field exclusions,
   and mass-assignment resistance.
3. Tenant FK queryset scoping (`scope_tenant_fields`), `tenant=None` empty
   queryset fail-closed safety (C1), global Currency filtering (`is_active=True`),
   and cross-tenant FK rejection (`reject_foreign`).
4. Validation rules, boundary values, date range checks, self-baseline check,
   negative-amount rejection, NaN/Infinity hardening, and `is_baseline` widget class.
5. Valid create and edit `save()` round-trips for all 4 forms.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django import forms
from django.utils import timezone

from apps.accounting.models import Budget, Currency
from apps.assets.forms import (
    AssetExecutiveScorecardForm,
    AssetLifecycleCostAnalysisForm,
    AssetPortfolioScenarioForm,
    AssetReplacementPlanForm,
    reject_foreign,
)
from apps.assets.forms.AssetAnalytics import (
    AssetExecutiveScorecardForm as DirectAssetExecutiveScorecardForm,
    AssetLifecycleCostAnalysisForm as DirectAssetLifecycleCostAnalysisForm,
    AssetPortfolioScenarioForm as DirectAssetPortfolioScenarioForm,
    AssetReplacementPlanForm as DirectAssetReplacementPlanForm,
)
from apps.assets.forms.AssetAnalytics._helpers import (
    scope_tenant_fields,
    validate_non_negative_fields,
)
from apps.assets.models import (
    AssetExecutiveScorecard,
    AssetLifecycleCostAnalysis,
    AssetPortfolioScenario,
    AssetReplacementPlan,
)

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Constants & Helpers (_assetanalytics_*)
# =====================================================================

_ASSETANALYTICS_ALCC_EXPECTED_FIELDS = [
    "title",
    "fixed_asset",
    "operational_asset",
    "asset_category",
    "asset_model",
    "org_unit",
    "currency",
    "analyzed_by",
    "analysis_date",
    "analysis_horizon_years",
    "discount_rate_pct",
    "lifecycle_stage",
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
    "notes",
]

_ASSETANALYTICS_ARPL_EXPECTED_FIELDS = [
    "title",
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
    "predicted_eol_date",
    "remaining_useful_life_months",
    "planned_replacement_year",
    "planned_quarter",
    "replacement_strategy",
    "funding_status",
    "condition_score",
    "criticality_weight",
    "failure_risk_score",
    "current_replacement_value",
    "deferred_maintenance_cost",
    "estimated_replacement_cost",
    "inflation_rate_pct",
    "estimated_salvage_recovery",
    "deferral_penalty_cost",
    "notes",
]

_ASSETANALYTICS_AWIF_EXPECTED_FIELDS = [
    "name",
    "scenario_type",
    "is_baseline",
    "base_fiscal_year",
    "horizon_years",
    "scope_org_unit",
    "scope_category",
    "currency",
    "baseline_scenario",
    "owner",
    "annual_capex_budget_limit",
    "discount_rate_pct",
    "inflation_rate_pct",
    "acceleration_months",
    "fleet_growth_pct",
    "consolidation_reduction_pct",
    "maintenance_efficiency_gain_pct",
    "assumptions_summary",
]

_ASSETANALYTICS_AKPI_EXPECTED_FIELDS = [
    "title",
    "period_type",
    "period_start",
    "period_end",
    "org_unit",
    "asset_category",
    "currency",
    "prepared_by",
    "target_asset_roi_pct",
    "target_mcr_pct",
    "target_compliance_rate_pct",
    "annual_asset_return_amount",
    "executive_summary",
]


def _assetanalytics_alcc_payload(currency=None, **overrides):
    data = {
        "title": "Chiller Plant #2 10-Year TCO Study",
        "currency": currency.pk if currency else "",
        "analysis_date": timezone.localdate().isoformat(),
        "analysis_horizon_years": "5",
        "discount_rate_pct": "8.00",
        "lifecycle_stage": "in_service",
        "acquisition_capital_cost": "100000.00",
        "installation_commissioning_cost": "10000.00",
        "preventive_maintenance_cost": "12000.00",
        "corrective_maintenance_cost": "6000.00",
        "service_contract_cost": "4000.00",
        "energy_utility_cost": "15000.00",
        "downtime_opportunity_cost": "2500.00",
        "insurance_compliance_cost": "3000.00",
        "accumulated_depreciation_cost": "20000.00",
        "expected_salvage_value": "8000.00",
        "warranty_insurance_recoveries": "1500.00",
        "current_replacement_value": "125000.00",
        "notes": "Baseline HVAC lifecycle cost evaluation.",
    }
    data.update(overrides)
    return data


def _assetanalytics_arpl_payload(currency=None, **overrides):
    next_year = timezone.localdate().year + 1
    data = {
        "title": "Cooling Tower #3 Capital Replacement Plan",
        "currency": currency.pk if currency else "",
        "predicted_eol_date": (timezone.localdate() + timedelta(days=365)).isoformat(),
        "remaining_useful_life_months": "12",
        "planned_replacement_year": str(next_year),
        "planned_quarter": "q2",
        "replacement_strategy": "technology_upgrade",
        "funding_status": "unfunded",
        "condition_score": "42.50",
        "criticality_weight": "8",
        "failure_risk_score": "68.00",
        "current_replacement_value": "150000.00",
        "deferred_maintenance_cost": "40000.00",
        "estimated_replacement_cost": "160000.00",
        "inflation_rate_pct": "4.00",
        "estimated_salvage_recovery": "10000.00",
        "deferral_penalty_cost": "7500.00",
        "notes": "Engineering replacement forecast.",
    }
    data.update(overrides)
    return data


def _assetanalytics_awif_payload(currency=None, **overrides):
    data = {
        "name": "FY2027 Accelerated Fleet Replacement",
        "scenario_type": "accelerated_replacement",
        "is_baseline": False,
        "base_fiscal_year": str(timezone.localdate().year),
        "horizon_years": "5",
        "currency": currency.pk if currency else "",
        "annual_capex_budget_limit": "450000.00",
        "discount_rate_pct": "8.00",
        "inflation_rate_pct": "4.00",
        "acceleration_months": "12",
        "fleet_growth_pct": "5.00",
        "consolidation_reduction_pct": "0.00",
        "maintenance_efficiency_gain_pct": "10.00",
        "assumptions_summary": "Accelerate high-risk machinery replacement by 12 months.",
    }
    data.update(overrides)
    return data


def _assetanalytics_akpi_payload(currency=None, **overrides):
    today = timezone.localdate()
    data = {
        "title": "FY2026 Q4 Board Asset Intelligence Scorecard",
        "period_type": "quarterly",
        "period_start": (today - timedelta(days=90)).isoformat(),
        "period_end": today.isoformat(),
        "currency": currency.pk if currency else "",
        "target_asset_roi_pct": "12.00",
        "target_mcr_pct": "3.50",
        "target_compliance_rate_pct": "95.00",
        "annual_asset_return_amount": "45000.00",
        "executive_summary": "Quarterly executive brief for board review.",
    }
    data.update(overrides)
    return data


# =====================================================================
# 1. Package Re-exports
# =====================================================================


def test_assetanalytics_package_reexports_match_direct_imports():
    import apps.assets.forms as forms_pkg
    import apps.assets.forms.AssetAnalytics as analytics_pkg

    assert AssetLifecycleCostAnalysisForm is DirectAssetLifecycleCostAnalysisForm
    assert AssetReplacementPlanForm is DirectAssetReplacementPlanForm
    assert AssetPortfolioScenarioForm is DirectAssetPortfolioScenarioForm
    assert AssetExecutiveScorecardForm is DirectAssetExecutiveScorecardForm

    expected_names = {
        "AssetLifecycleCostAnalysisForm",
        "AssetReplacementPlanForm",
        "AssetPortfolioScenarioForm",
        "AssetExecutiveScorecardForm",
    }
    assert expected_names.issubset(set(analytics_pkg.__all__))
    assert expected_names.issubset(set(forms_pkg.__all__))


# =====================================================================
# 2. Meta.fields & Strict Security Exclusions
# =====================================================================


def test_assetanalytics_alcc_meta_fields_and_exclusions(tenant_a):
    form = AssetLifecycleCostAnalysisForm(tenant=tenant_a)
    assert list(form.fields.keys()) == _ASSETANALYTICS_ALCC_EXPECTED_FIELDS

    excluded = {
        "tenant",
        "number",
        "status",
        "created_at",
        "updated_at",
        "total_lifecycle_cost",
        "equivalent_annual_cost",
        "maintenance_to_rav_pct",
        "opex_to_capex_ratio",
        "economic_eol_year",
        "recommendation",
    }
    assert excluded.isdisjoint(set(form.fields.keys()))


def test_assetanalytics_arpl_meta_fields_and_exclusions(tenant_a):
    form = AssetReplacementPlanForm(tenant=tenant_a)
    assert list(form.fields.keys()) == _ASSETANALYTICS_ARPL_EXPECTED_FIELDS

    excluded = {
        "tenant",
        "number",
        "status",
        "created_at",
        "updated_at",
        "priority_score",
        "priority_band",
        "fci_ratio_pct",
        "inflation_adjusted_cost",
    }
    assert excluded.isdisjoint(set(form.fields.keys()))


def test_assetanalytics_awif_meta_fields_and_exclusions(tenant_a):
    form = AssetPortfolioScenarioForm(tenant=tenant_a)
    assert list(form.fields.keys()) == _ASSETANALYTICS_AWIF_EXPECTED_FIELDS

    excluded = {
        "tenant",
        "number",
        "status",
        "created_at",
        "updated_at",
        "baseline_capex_total",
        "simulated_capex_total",
        "capex_variance_amount",
        "baseline_opex_maintenance",
        "simulated_opex_maintenance",
        "opex_savings_amount",
        "baseline_deferred_backlog",
        "simulated_deferred_backlog",
        "baseline_avg_health_score",
        "simulated_avg_health_score",
        "baseline_fci_pct",
        "simulated_fci_pct",
        "baseline_risk_exposure",
        "simulated_risk_exposure",
        "net_present_value",
        "payback_period_years",
        "benefit_cost_ratio",
    }
    assert excluded.isdisjoint(set(form.fields.keys()))


def test_assetanalytics_akpi_meta_fields_and_exclusions(tenant_a):
    form = AssetExecutiveScorecardForm(tenant=tenant_a)
    assert list(form.fields.keys()) == _ASSETANALYTICS_AKPI_EXPECTED_FIELDS

    excluded = {
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "status",
        "approved_by",
        "rag_status",
        "total_asset_count",
        "gross_replacement_value",
        "total_net_book_value",
        "total_maintenance_spend",
        "asset_roi_pct",
        "maintenance_cost_to_rav_pct",
        "planned_maintenance_ratio_pct",
        "portfolio_fci_pct",
        "capex_budget_utilization_pct",
        "fleet_availability_pct",
        "portfolio_oee_pct",
        "compliance_audit_pass_rate_pct",
        "open_compliance_incidents",
        "total_risk_exposure_amount",
        "unfunded_replacement_backlog",
    }
    assert excluded.isdisjoint(set(form.fields.keys()))


def test_assetanalytics_mass_assignment_ignored_on_save(tenant_a, tenant_b, admin_user, currency_usd):
    alcc_data = _assetanalytics_alcc_payload(
        currency=currency_usd,
        tenant=str(tenant_b.pk),
        number="ALCC-FORGED-9999",
        status="approved",
        total_lifecycle_cost="9999999.00",
        recommendation="dispose_retire",
    )
    alcc_form = AssetLifecycleCostAnalysisForm(data=alcc_data, tenant=tenant_a)
    assert alcc_form.is_valid(), alcc_form.errors
    alcc = alcc_form.save()
    assert alcc.tenant_id == tenant_a.pk
    assert alcc.number != "ALCC-FORGED-9999"
    assert alcc.status == "draft"
    assert alcc.total_lifecycle_cost != Decimal("9999999.00")

    arpl_data = _assetanalytics_arpl_payload(
        currency=currency_usd,
        tenant=str(tenant_b.pk),
        number="ARPL-FORGED-9999",
        status="executed",
        priority_score="999.99",
        priority_band="critical",
    )
    arpl_form = AssetReplacementPlanForm(data=arpl_data, tenant=tenant_a)
    assert arpl_form.is_valid(), arpl_form.errors
    arpl = arpl_form.save()
    assert arpl.tenant_id == tenant_a.pk
    assert arpl.number != "ARPL-FORGED-9999"
    assert arpl.status == "forecasted"

    awif_data = _assetanalytics_awif_payload(
        currency=currency_usd,
        tenant=str(tenant_b.pk),
        number="AWIF-FORGED-9999",
        status="adopted",
        net_present_value="888888.00",
    )
    awif_form = AssetPortfolioScenarioForm(data=awif_data, tenant=tenant_a)
    assert awif_form.is_valid(), awif_form.errors
    awif = awif_form.save()
    assert awif.tenant_id == tenant_a.pk
    assert awif.number != "AWIF-FORGED-9999"
    assert awif.status == "draft"
    assert awif.net_present_value == Decimal("0.00")

    akpi_data = _assetanalytics_akpi_payload(
        currency=currency_usd,
        tenant=str(tenant_b.pk),
        number="AKPI-FORGED-9999",
        status="board_approved",
        approved_by=str(admin_user.pk),
        rag_status="red",
        total_asset_count="9999",
        asset_roi_pct="99.99",
    )
    akpi_form = AssetExecutiveScorecardForm(data=akpi_data, tenant=tenant_a)
    assert akpi_form.is_valid(), akpi_form.errors
    akpi = akpi_form.save()
    assert akpi.tenant_id == tenant_a.pk
    assert akpi.number != "AKPI-FORGED-9999"
    assert akpi.status == "draft"
    assert akpi.approved_by is None
    assert akpi.rag_status == "green"
    assert akpi.total_asset_count == 0


# =====================================================================
# 3. Tenant FK Queryset Scoping, tenant=None Fail-Closed, & reject_foreign
# =====================================================================


def test_assetanalytics_alcc_tenant_scoping_and_none_safety(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    category_root_a,
    category_root_b,
    asset_model_a,
    asset_model_b,
    org_unit_a,
    org_unit_b,
    admin_user,
    admin_b,
    currency_usd,
):
    inactive_curr = Currency.objects.create(code="ZZZ", name="Inactive Test", symbol="Z", is_active=False)

    form_a = AssetLifecycleCostAnalysisForm(tenant=tenant_a)
    scoped_pairs = [
        ("fixed_asset", fixed_asset_a, fixed_asset_b),
        ("operational_asset", operational_asset_a, operational_asset_b),
        ("asset_category", category_root_a, category_root_b),
        ("asset_model", asset_model_a, asset_model_b),
        ("org_unit", org_unit_a, org_unit_b),
        ("analyzed_by", admin_user, admin_b),
    ]
    for field_name, obj_a, obj_b in scoped_pairs:
        qs = form_a.fields[field_name].queryset
        assert obj_a in qs
        assert obj_b not in qs

    curr_qs = form_a.fields["currency"].queryset
    assert currency_usd in curr_qs
    assert inactive_curr not in curr_qs

    form_none = AssetLifecycleCostAnalysisForm(tenant=None)
    for field_name, _obj_a, _obj_b in scoped_pairs:
        assert form_none.fields[field_name].queryset.count() == 0
    assert currency_usd in form_none.fields["currency"].queryset
    assert inactive_curr not in form_none.fields["currency"].queryset


def test_assetanalytics_arpl_tenant_scoping_and_none_safety(
    tenant_a,
    tenant_b,
    fixed_asset_a,
    fixed_asset_b,
    operational_asset_a,
    operational_asset_b,
    category_root_a,
    category_root_b,
    asset_model_a,
    asset_model_b,
    org_unit_a,
    org_unit_b,
    location_a,
    location_b,
    condition_assessment_a,
    condition_assessment_b,
    analytics_lcc_a,
    analytics_lcc_b,
    requisition_a,
    requisition_b,
    admin_user,
    admin_b,
    currency_usd,
):
    budget_a = Budget.objects.create(tenant=tenant_a, name="Acme CapEx FY26")
    budget_b = Budget.objects.create(tenant=tenant_b, name="Globex CapEx FY26")
    inactive_curr = Currency.objects.create(code="ZZY", name="Inactive Test 2", symbol="Y", is_active=False)

    form_a = AssetReplacementPlanForm(tenant=tenant_a)
    scoped_pairs = [
        ("fixed_asset", fixed_asset_a, fixed_asset_b),
        ("operational_asset", operational_asset_a, operational_asset_b),
        ("asset_category", category_root_a, category_root_b),
        ("asset_model", asset_model_a, asset_model_b),
        ("org_unit", org_unit_a, org_unit_b),
        ("location", location_a, location_b),
        ("condition_assessment", condition_assessment_a, condition_assessment_b),
        ("lifecycle_analysis", analytics_lcc_a, analytics_lcc_b),
        ("capital_budget", budget_a, budget_b),
        ("linked_requisition", requisition_a, requisition_b),
        ("planner", admin_user, admin_b),
    ]
    for field_name, obj_a, obj_b in scoped_pairs:
        qs = form_a.fields[field_name].queryset
        assert obj_a in qs
        assert obj_b not in qs

    assert currency_usd in form_a.fields["currency"].queryset
    assert inactive_curr not in form_a.fields["currency"].queryset

    form_none = AssetReplacementPlanForm(tenant=None)
    for field_name, _obj_a, _obj_b in scoped_pairs:
        assert form_none.fields[field_name].queryset.count() == 0
    assert currency_usd in form_none.fields["currency"].queryset


def test_assetanalytics_awif_tenant_scoping_and_none_safety(
    tenant_a,
    tenant_b,
    org_unit_a,
    org_unit_b,
    category_root_a,
    category_root_b,
    analytics_scenario_base_a,
    analytics_scenario_b,
    admin_user,
    admin_b,
    currency_usd,
):
    inactive_curr = Currency.objects.create(code="ZZX", name="Inactive Test 3", symbol="X", is_active=False)

    form_a = AssetPortfolioScenarioForm(tenant=tenant_a)
    scoped_pairs = [
        ("scope_org_unit", org_unit_a, org_unit_b),
        ("scope_category", category_root_a, category_root_b),
        ("baseline_scenario", analytics_scenario_base_a, analytics_scenario_b),
        ("owner", admin_user, admin_b),
    ]
    for field_name, obj_a, obj_b in scoped_pairs:
        qs = form_a.fields[field_name].queryset
        assert obj_a in qs
        assert obj_b not in qs

    assert currency_usd in form_a.fields["currency"].queryset
    assert inactive_curr not in form_a.fields["currency"].queryset

    form_none = AssetPortfolioScenarioForm(tenant=None)
    for field_name, _obj_a, _obj_b in scoped_pairs:
        assert form_none.fields[field_name].queryset.count() == 0
    assert currency_usd in form_none.fields["currency"].queryset


def test_assetanalytics_akpi_tenant_scoping_and_none_safety(
    tenant_a,
    tenant_b,
    org_unit_a,
    org_unit_b,
    category_root_a,
    category_root_b,
    admin_user,
    admin_b,
    currency_usd,
):
    inactive_curr = Currency.objects.create(code="ZZW", name="Inactive Test 4", symbol="W", is_active=False)

    form_a = AssetExecutiveScorecardForm(tenant=tenant_a)
    scoped_pairs = [
        ("org_unit", org_unit_a, org_unit_b),
        ("asset_category", category_root_a, category_root_b),
        ("prepared_by", admin_user, admin_b),
    ]
    for field_name, obj_a, obj_b in scoped_pairs:
        qs = form_a.fields[field_name].queryset
        assert obj_a in qs
        assert obj_b not in qs

    assert currency_usd in form_a.fields["currency"].queryset
    assert inactive_curr not in form_a.fields["currency"].queryset

    form_none = AssetExecutiveScorecardForm(tenant=None)
    for field_name, _obj_a, _obj_b in scoped_pairs:
        assert form_none.fields[field_name].queryset.count() == 0
    assert currency_usd in form_none.fields["currency"].queryset


def test_assetanalytics_reject_foreign_blocks_cross_tenant_fks_all_forms(
    tenant_a,
    tenant_b,
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
    currency_usd,
):
    budget_b = Budget.objects.create(tenant=tenant_b, name="Globex Foreign Budget")

    alcc_foreign = {
        "fixed_asset": fixed_asset_b,
        "operational_asset": operational_asset_b,
        "asset_category": category_root_b,
        "asset_model": asset_model_b,
        "org_unit": org_unit_b,
        "analyzed_by": admin_b,
    }
    for field_name, obj_b in alcc_foreign.items():
        bound_form = AssetLifecycleCostAnalysisForm(
            data=_assetanalytics_alcc_payload(currency=currency_usd, **{field_name: str(obj_b.pk)}),
            tenant=tenant_a,
        )
        assert not bound_form.is_valid()
        assert field_name in bound_form.errors

        probe_form = AssetLifecycleCostAnalysisForm(tenant=tenant_a)
        probe_form.cleaned_data = {}
        reject_foreign(probe_form, {field_name: obj_b}, list(AssetLifecycleCostAnalysisForm._TENANT_FIELDS.keys()))
        assert field_name in probe_form.errors
        assert "another workspace" in str(probe_form.errors[field_name])

    arpl_foreign = {
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
    for field_name, obj_b in arpl_foreign.items():
        bound_form = AssetReplacementPlanForm(
            data=_assetanalytics_arpl_payload(currency=currency_usd, **{field_name: str(obj_b.pk)}),
            tenant=tenant_a,
        )
        assert not bound_form.is_valid()
        assert field_name in bound_form.errors

        probe_form = AssetReplacementPlanForm(tenant=tenant_a)
        probe_form.cleaned_data = {}
        reject_foreign(probe_form, {field_name: obj_b}, list(AssetReplacementPlanForm._TENANT_FIELDS.keys()))
        assert field_name in probe_form.errors
        assert "another workspace" in str(probe_form.errors[field_name])

    awif_foreign = {
        "scope_org_unit": org_unit_b,
        "scope_category": category_root_b,
        "baseline_scenario": analytics_scenario_b,
        "owner": admin_b,
    }
    for field_name, obj_b in awif_foreign.items():
        bound_form = AssetPortfolioScenarioForm(
            data=_assetanalytics_awif_payload(currency=currency_usd, **{field_name: str(obj_b.pk)}),
            tenant=tenant_a,
        )
        assert not bound_form.is_valid()
        assert field_name in bound_form.errors

        probe_form = AssetPortfolioScenarioForm(tenant=tenant_a)
        probe_form.cleaned_data = {}
        reject_foreign(probe_form, {field_name: obj_b}, list(AssetPortfolioScenarioForm._TENANT_FIELDS.keys()))
        assert field_name in probe_form.errors
        assert "another workspace" in str(probe_form.errors[field_name])

    akpi_foreign = {
        "org_unit": org_unit_b,
        "asset_category": category_root_b,
        "prepared_by": admin_b,
    }
    for field_name, obj_b in akpi_foreign.items():
        bound_form = AssetExecutiveScorecardForm(
            data=_assetanalytics_akpi_payload(currency=currency_usd, **{field_name: str(obj_b.pk)}),
            tenant=tenant_a,
        )
        assert not bound_form.is_valid()
        assert field_name in bound_form.errors

        probe_form = AssetExecutiveScorecardForm(tenant=tenant_a)
        probe_form.cleaned_data = {}
        reject_foreign(probe_form, {field_name: obj_b}, list(AssetExecutiveScorecardForm._TENANT_FIELDS.keys()))
        assert field_name in probe_form.errors
        assert "another workspace" in str(probe_form.errors[field_name])


def test_assetanalytics_global_currency_accepted_with_tenant_a(tenant_a, currency_usd):
    for form_cls, payload_fn in [
        (AssetLifecycleCostAnalysisForm, _assetanalytics_alcc_payload),
        (AssetReplacementPlanForm, _assetanalytics_arpl_payload),
        (AssetPortfolioScenarioForm, _assetanalytics_awif_payload),
        (AssetExecutiveScorecardForm, _assetanalytics_akpi_payload),
    ]:
        form = form_cls(data=payload_fn(currency=currency_usd), tenant=tenant_a)
        assert form.is_valid(), f"{form_cls.__name__} failed with global currency: {form.errors}"


def test_assetanalytics_scope_tenant_fields_helper_behavior(tenant_a, tenant_b, org_unit_a, org_unit_b, currency_usd):
    from apps.core.models import OrgUnit

    class _ProbeForm(forms.Form):
        org_unit = forms.ModelChoiceField(queryset=OrgUnit.objects.none(), required=False)
        currency = forms.ModelChoiceField(queryset=Currency.objects.none(), required=False)

    form = _ProbeForm()
    form.tenant = tenant_a
    scope_tenant_fields(
        form,
        {"org_unit": OrgUnit},
        global_querysets={"currency": Currency.objects.filter(is_active=True)},
    )
    assert org_unit_a in form.fields["org_unit"].queryset
    assert org_unit_b not in form.fields["org_unit"].queryset
    assert currency_usd in form.fields["currency"].queryset

    form.tenant = None
    scope_tenant_fields(
        form,
        {"org_unit": OrgUnit},
        global_querysets={"currency": Currency.objects.filter(is_active=True)},
    )
    assert form.fields["org_unit"].queryset.count() == 0
    assert currency_usd in form.fields["currency"].queryset


def test_assetanalytics_validate_non_negative_fields_helper():
    class _ProbeForm(forms.Form):
        cost = forms.DecimalField(required=False)

    form = _ProbeForm(data={"cost": "-1.00"})
    assert form.is_valid()
    validate_non_negative_fields(form, form.cleaned_data, ("cost",))
    assert "cost" in form.errors


# =====================================================================
# 4. Validation Rules & Negative-Input Hardening
# =====================================================================


@pytest.mark.parametrize("horizon", ["0", "-1", "51"])
def test_assetanalytics_alcc_horizon_out_of_bounds_rejected(tenant_a, currency_usd, horizon):
    form = AssetLifecycleCostAnalysisForm(
        data=_assetanalytics_alcc_payload(currency=currency_usd, analysis_horizon_years=horizon),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "analysis_horizon_years" in form.errors


@pytest.mark.parametrize("horizon", ["1", "50"])
def test_assetanalytics_alcc_horizon_boundary_accepted(tenant_a, currency_usd, horizon):
    form = AssetLifecycleCostAnalysisForm(
        data=_assetanalytics_alcc_payload(currency=currency_usd, analysis_horizon_years=horizon),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("rate", ["-0.01", "100.01"])
def test_assetanalytics_alcc_discount_rate_out_of_bounds_rejected(tenant_a, currency_usd, rate):
    form = AssetLifecycleCostAnalysisForm(
        data=_assetanalytics_alcc_payload(currency=currency_usd, discount_rate_pct=rate),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "discount_rate_pct" in form.errors


@pytest.mark.parametrize("rate", ["0.00", "100.00"])
def test_assetanalytics_alcc_discount_rate_boundary_accepted(tenant_a, currency_usd, rate):
    form = AssetLifecycleCostAnalysisForm(
        data=_assetanalytics_alcc_payload(currency=currency_usd, discount_rate_pct=rate),
        tenant=tenant_a,
    )
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("field_name", AssetLifecycleCostAnalysisForm._MONETARY_FIELDS)
def test_assetanalytics_alcc_negative_monetary_buckets_rejected(tenant_a, currency_usd, field_name):
    form = AssetLifecycleCostAnalysisForm(
        data=_assetanalytics_alcc_payload(currency=currency_usd, **{field_name: "-0.01"}),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert field_name in form.errors


@pytest.mark.parametrize("bad_num", ["NaN", "nan", "Infinity", "-Infinity", "inf"])
def test_assetanalytics_alcc_nan_infinity_rejected(tenant_a, currency_usd, bad_num):
    for field_name in ("discount_rate_pct", "acquisition_capital_cost", "current_replacement_value"):
        form = AssetLifecycleCostAnalysisForm(
            data=_assetanalytics_alcc_payload(currency=currency_usd, **{field_name: bad_num}),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert field_name in form.errors


@pytest.mark.parametrize(
    ("field_name", "invalid_vals", "valid_vals"),
    [
        ("criticality_weight", ["0", "11"], ["1", "10"]),
        ("condition_score", ["-0.01", "100.01"], ["0.00", "100.00"]),
        ("failure_risk_score", ["-0.01", "100.01"], ["0.00", "100.00"]),
        ("inflation_rate_pct", ["-0.01", "50.01"], ["0.00", "50.00"]),
        ("planned_replacement_year", ["1999", "2101"], ["2000", "2100"]),
        ("remaining_useful_life_months", ["-1", "1201"], ["0", "1200"]),
    ],
)
def test_assetanalytics_arpl_range_bounds(tenant_a, currency_usd, field_name, invalid_vals, valid_vals):
    for val in invalid_vals:
        form = AssetReplacementPlanForm(
            data=_assetanalytics_arpl_payload(currency=currency_usd, **{field_name: val}),
            tenant=tenant_a,
        )
        assert not form.is_valid(), f"{field_name}={val} unexpectedly valid"
        assert field_name in form.errors

    for val in valid_vals:
        form = AssetReplacementPlanForm(
            data=_assetanalytics_arpl_payload(currency=currency_usd, **{field_name: val}),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"{field_name}={val} failed: {form.errors}"


@pytest.mark.parametrize("field_name", AssetReplacementPlanForm._MONETARY_FIELDS)
def test_assetanalytics_arpl_negative_monetary_fields_rejected(tenant_a, currency_usd, field_name):
    form = AssetReplacementPlanForm(
        data=_assetanalytics_arpl_payload(currency=currency_usd, **{field_name: "-0.01"}),
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert field_name in form.errors


@pytest.mark.parametrize("bad_num", ["NaN", "Infinity", "-Infinity"])
def test_assetanalytics_arpl_nan_infinity_rejected(tenant_a, currency_usd, bad_num):
    for field_name in ("condition_score", "failure_risk_score", "inflation_rate_pct", "estimated_replacement_cost"):
        form = AssetReplacementPlanForm(
            data=_assetanalytics_arpl_payload(currency=currency_usd, **{field_name: bad_num}),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert field_name in form.errors


def test_assetanalytics_awif_cannot_reference_self_as_baseline(
    tenant_a,
    currency_usd,
    analytics_scenario_base_a,
):
    edit_form = AssetPortfolioScenarioForm(instance=analytics_scenario_base_a, tenant=tenant_a)
    assert analytics_scenario_base_a not in edit_form.fields["baseline_scenario"].queryset

    bound_form = AssetPortfolioScenarioForm(
        data=_assetanalytics_awif_payload(
            currency=currency_usd,
            baseline_scenario=str(analytics_scenario_base_a.pk),
        ),
        instance=analytics_scenario_base_a,
        tenant=tenant_a,
    )
    assert not bound_form.is_valid()
    assert "baseline_scenario" in bound_form.errors

    # Also verify explicit clean() guard directly when queryset is bypassed
    bypass_form = AssetPortfolioScenarioForm(
        data=_assetanalytics_awif_payload(currency=currency_usd),
        instance=analytics_scenario_base_a,
        tenant=tenant_a,
    )
    bypass_form.fields["baseline_scenario"].queryset = AssetPortfolioScenario.objects.filter(tenant=tenant_a)
    bypass_form.data = _assetanalytics_awif_payload(
        currency=currency_usd,
        baseline_scenario=str(analytics_scenario_base_a.pk),
    )
    assert not bypass_form.is_valid()
    assert "cannot reference itself" in str(bypass_form.errors["baseline_scenario"])


@pytest.mark.parametrize(
    ("field_name", "invalid_vals", "valid_vals"),
    [
        ("horizon_years", ["0", "31"], ["1", "30"]),
        ("base_fiscal_year", ["1999", "2101"], ["2000", "2100"]),
        ("annual_capex_budget_limit", ["-0.01"], ["0.00"]),
        ("discount_rate_pct", ["-0.01", "100.01"], ["0.00", "100.00"]),
        ("inflation_rate_pct", ["-0.01", "50.01"], ["0.00", "50.00"]),
        ("acceleration_months", ["-61", "121"], ["-60", "120"]),
        ("fleet_growth_pct", ["-95.01", "500.01"], ["-95.00", "500.00"]),
        ("consolidation_reduction_pct", ["-0.01", "100.01"], ["0.00", "100.00"]),
        ("maintenance_efficiency_gain_pct", ["-0.01", "100.01"], ["0.00", "100.00"]),
    ],
)
def test_assetanalytics_awif_range_bounds(tenant_a, currency_usd, field_name, invalid_vals, valid_vals):
    for val in invalid_vals:
        form = AssetPortfolioScenarioForm(
            data=_assetanalytics_awif_payload(currency=currency_usd, **{field_name: val}),
            tenant=tenant_a,
        )
        assert not form.is_valid(), f"{field_name}={val} unexpectedly valid"
        assert field_name in form.errors

    for val in valid_vals:
        form = AssetPortfolioScenarioForm(
            data=_assetanalytics_awif_payload(currency=currency_usd, **{field_name: val}),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"{field_name}={val} failed: {form.errors}"


@pytest.mark.parametrize("bad_num", ["NaN", "Infinity", "-Infinity"])
def test_assetanalytics_awif_nan_infinity_rejected(tenant_a, currency_usd, bad_num):
    for field_name in ("annual_capex_budget_limit", "discount_rate_pct", "fleet_growth_pct"):
        form = AssetPortfolioScenarioForm(
            data=_assetanalytics_awif_payload(currency=currency_usd, **{field_name: bad_num}),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert field_name in form.errors


def test_assetanalytics_awif_is_baseline_widget_class(tenant_a):
    form = AssetPortfolioScenarioForm(tenant=tenant_a)
    widget = form.fields["is_baseline"].widget
    assert isinstance(widget, forms.CheckboxInput)
    classes = widget.attrs.get("class", "").split()
    assert "form-check" in classes


def test_assetanalytics_akpi_period_end_before_start_rejected(tenant_a, currency_usd):
    today = timezone.localdate()
    invalid_form = AssetExecutiveScorecardForm(
        data=_assetanalytics_akpi_payload(
            currency=currency_usd,
            period_start=today.isoformat(),
            period_end=(today - timedelta(days=1)).isoformat(),
        ),
        tenant=tenant_a,
    )
    assert not invalid_form.is_valid()
    assert "period_end" in invalid_form.errors

    equal_form = AssetExecutiveScorecardForm(
        data=_assetanalytics_akpi_payload(
            currency=currency_usd,
            period_start=today.isoformat(),
            period_end=today.isoformat(),
        ),
        tenant=tenant_a,
    )
    assert equal_form.is_valid(), equal_form.errors


@pytest.mark.parametrize(
    ("field_name", "invalid_vals", "valid_vals"),
    [
        ("target_compliance_rate_pct", ["-0.01", "100.01"], ["0.00", "100.00"]),
        ("target_mcr_pct", ["-0.01", "100.01"], ["0.00", "100.00"]),
    ],
)
def test_assetanalytics_akpi_target_percentage_bounds(tenant_a, currency_usd, field_name, invalid_vals, valid_vals):
    for val in invalid_vals:
        form = AssetExecutiveScorecardForm(
            data=_assetanalytics_akpi_payload(currency=currency_usd, **{field_name: val}),
            tenant=tenant_a,
        )
        assert not form.is_valid(), f"{field_name}={val} unexpectedly valid"
        assert field_name in form.errors

    for val in valid_vals:
        form = AssetExecutiveScorecardForm(
            data=_assetanalytics_akpi_payload(currency=currency_usd, **{field_name: val}),
            tenant=tenant_a,
        )
        assert form.is_valid(), f"{field_name}={val} failed: {form.errors}"


@pytest.mark.parametrize("bad_num", ["NaN", "Infinity", "-Infinity"])
def test_assetanalytics_akpi_nan_infinity_rejected(tenant_a, currency_usd, bad_num):
    for field_name in ("target_asset_roi_pct", "target_mcr_pct", "target_compliance_rate_pct"):
        form = AssetExecutiveScorecardForm(
            data=_assetanalytics_akpi_payload(currency=currency_usd, **{field_name: bad_num}),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert field_name in form.errors


# =====================================================================
# 5. Valid Save Round-Trips (Create & Edit) for All 4 Forms
# =====================================================================


def test_assetanalytics_alcc_save_round_trip(
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    asset_model_a,
    org_unit_a,
    admin_user,
    currency_usd,
):
    payload = _assetanalytics_alcc_payload(
        currency=currency_usd,
        fixed_asset=str(fixed_asset_a.pk),
        operational_asset=str(operational_asset_a.pk),
        asset_category=str(category_root_a.pk),
        asset_model=str(asset_model_a.pk),
        org_unit=str(org_unit_a.pk),
        analyzed_by=str(admin_user.pk),
    )
    form = AssetLifecycleCostAnalysisForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()

    assert obj.pk is not None
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("ALCC-")
    assert obj.status == "draft"
    assert obj.currency_id == currency_usd.pk
    assert AssetLifecycleCostAnalysis.objects.filter(pk=obj.pk, tenant=tenant_a).exists()

    edit_payload = _assetanalytics_alcc_payload(
        currency=currency_usd,
        title="Updated Chiller Plant #2 TCO Study",
        analysis_horizon_years="10",
    )
    edit_form = AssetLifecycleCostAnalysisForm(data=edit_payload, instance=obj, tenant=tenant_a)
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save()
    updated.refresh_from_db()
    assert updated.pk == obj.pk
    assert updated.number == obj.number
    assert updated.title == "Updated Chiller Plant #2 TCO Study"
    assert updated.analysis_horizon_years == 10


def test_assetanalytics_arpl_save_round_trip(
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    asset_model_a,
    org_unit_a,
    location_a,
    condition_assessment_a,
    analytics_lcc_a,
    requisition_a,
    admin_user,
    currency_usd,
):
    budget_a = Budget.objects.create(tenant=tenant_a, name="Acme CapEx FY27")
    payload = _assetanalytics_arpl_payload(
        currency=currency_usd,
        fixed_asset=str(fixed_asset_a.pk),
        operational_asset=str(operational_asset_a.pk),
        asset_category=str(category_root_a.pk),
        asset_model=str(asset_model_a.pk),
        org_unit=str(org_unit_a.pk),
        location=str(location_a.pk),
        condition_assessment=str(condition_assessment_a.pk),
        lifecycle_analysis=str(analytics_lcc_a.pk),
        capital_budget=str(budget_a.pk),
        linked_requisition=str(requisition_a.pk),
        planner=str(admin_user.pk),
    )
    form = AssetReplacementPlanForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()

    assert obj.pk is not None
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("ARPL-")
    assert obj.status == "forecasted"
    assert obj.capital_budget_id == budget_a.pk
    assert AssetReplacementPlan.objects.filter(pk=obj.pk, tenant=tenant_a).exists()

    edit_payload = _assetanalytics_arpl_payload(
        currency=currency_usd,
        title="Revised Cooling Tower #3 Replacement Plan",
        criticality_weight="10",
    )
    edit_form = AssetReplacementPlanForm(data=edit_payload, instance=obj, tenant=tenant_a)
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save()
    updated.refresh_from_db()
    assert updated.pk == obj.pk
    assert updated.number == obj.number
    assert updated.title == "Revised Cooling Tower #3 Replacement Plan"
    assert updated.criticality_weight == 10


def test_assetanalytics_awif_save_round_trip(
    tenant_a,
    org_unit_a,
    category_root_a,
    analytics_scenario_base_a,
    admin_user,
    currency_usd,
):
    payload = _assetanalytics_awif_payload(
        currency=currency_usd,
        scope_org_unit=str(org_unit_a.pk),
        scope_category=str(category_root_a.pk),
        baseline_scenario=str(analytics_scenario_base_a.pk),
        owner=str(admin_user.pk),
    )
    form = AssetPortfolioScenarioForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()

    assert obj.pk is not None
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("AWIF-")
    assert obj.status == "draft"
    assert obj.baseline_scenario_id == analytics_scenario_base_a.pk
    assert AssetPortfolioScenario.objects.filter(pk=obj.pk, tenant=tenant_a).exists()

    edit_payload = _assetanalytics_awif_payload(
        currency=currency_usd,
        name="Updated FY2027 Fleet Consolidation",
        is_baseline=True,
        horizon_years="7",
    )
    edit_form = AssetPortfolioScenarioForm(data=edit_payload, instance=obj, tenant=tenant_a)
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save()
    updated.refresh_from_db()
    assert updated.pk == obj.pk
    assert updated.number == obj.number
    assert updated.name == "Updated FY2027 Fleet Consolidation"
    assert updated.is_baseline is True
    assert updated.horizon_years == 7


def test_assetanalytics_akpi_save_round_trip(
    tenant_a,
    org_unit_a,
    category_root_a,
    admin_user,
    currency_usd,
):
    payload = _assetanalytics_akpi_payload(
        currency=currency_usd,
        org_unit=str(org_unit_a.pk),
        asset_category=str(category_root_a.pk),
        prepared_by=str(admin_user.pk),
    )
    form = AssetExecutiveScorecardForm(data=payload, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()

    assert obj.pk is not None
    assert obj.tenant_id == tenant_a.pk
    assert obj.number.startswith("AKPI-")
    assert obj.status == "draft"
    assert obj.rag_status == "green"
    assert obj.approved_by is None
    assert AssetExecutiveScorecard.objects.filter(pk=obj.pk, tenant=tenant_a).exists()

    edit_payload = _assetanalytics_akpi_payload(
        currency=currency_usd,
        title="Updated Board Executive Scorecard",
        target_asset_roi_pct="15.00",
    )
    edit_form = AssetExecutiveScorecardForm(data=edit_payload, instance=obj, tenant=tenant_a)
    assert edit_form.is_valid(), edit_form.errors
    updated = edit_form.save()
    updated.refresh_from_db()
    assert updated.pk == obj.pk
    assert updated.number == obj.number
    assert updated.title == "Updated Board Executive Scorecard"
    assert updated.target_asset_roi_pct == Decimal("15.00")
