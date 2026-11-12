"""
Security, multi-tenant IDOR, RBAC, UI permission gating, SoD, mass-assignment,
workflow bypass, lock enforcement, CSRF, CSV formula-injection, and adversarial
input-hardening tests for Sub-module 11.14: Asset Analytics & Business Intelligence.
"""

from __future__ import annotations

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.contrib import admin as django_admin
from django.contrib.messages import get_messages
from django.test import Client, RequestFactory
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.admin import (
    AssetExecutiveScorecardAdmin,
    AssetLifecycleCostAnalysisAdmin,
    AssetPortfolioScenarioAdmin,
    AssetReplacementPlanAdmin,
)
from apps.assets.forms import (
    AssetExecutiveScorecardForm,
    AssetLifecycleCostAnalysisForm,
    AssetPortfolioScenarioForm,
    AssetReplacementPlanForm,
)
from apps.assets.models import (
    AssetExecutiveScorecard,
    AssetLifecycleCostAnalysis,
    AssetPortfolioScenario,
    AssetReplacementPlan,
)
from apps.assets.views.AssetAnalytics._helpers import csv_safe

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (_assetanalytics_*)
# =====================================================================


def _assetanalytics_messages(response):
    """Return queued Django flash message strings for a response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _assetanalytics_superuser_client():
    """Create and log in a platform superuser with tenant=None."""
    su = User.objects.create_superuser(
        email="platform_super_11_14_sec@naverp.test",
        username="platform_super_11_14_sec",
        password="TestPass123!",
        tenant=None,
    )
    client = Client()
    client.force_login(su)
    return su, client


def _assetanalytics_alcc_payload(currency=None, **overrides):
    data = {
        "title": "Security Test LCC Analysis",
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
        "notes": "Security test LCC notes.",
    }
    data.update(overrides)
    return data


def _assetanalytics_arpl_payload(currency=None, **overrides):
    next_year = timezone.localdate().year + 1
    data = {
        "title": "Security Test Replacement Plan",
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
        "notes": "Security test replacement notes.",
    }
    data.update(overrides)
    return data


def _assetanalytics_awif_payload(currency=None, **overrides):
    data = {
        "name": "Security Test What-If Scenario",
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
        "assumptions_summary": "Security test scenario assumptions.",
    }
    data.update(overrides)
    return data


def _assetanalytics_akpi_payload(currency=None, **overrides):
    today = timezone.localdate()
    data = {
        "title": "Security Test Executive Scorecard",
        "period_type": "quarterly",
        "period_start": (today - timedelta(days=90)).isoformat(),
        "period_end": today.isoformat(),
        "currency": currency.pk if currency else "",
        "target_asset_roi_pct": "12.00",
        "target_mcr_pct": "3.50",
        "target_compliance_rate_pct": "95.00",
        "annual_asset_return_amount": "45000.00",
        "executive_summary": "Security test executive summary.",
    }
    data.update(overrides)
    return data


def _assetanalytics_parse_csv_response(response):
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert response.get("X-Content-Type-Options") == "nosniff"
    assert "attachment;" in response.get("Content-Disposition", "")
    body = response.content.decode("utf-8")
    return list(csv.reader(io.StringIO(body)))


# =====================================================================
# 1. Unauthenticated Access (All 37 Routes -> 302 Login Redirect)
# =====================================================================


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize(
    "url_name,needs_pk",
    [
        # ALCC (8 routes)
        ("assets:asset_lifecycle_cost_analysis_list", False),
        ("assets:asset_lifecycle_cost_analysis_create", False),
        ("assets:asset_lifecycle_cost_analysis_export_csv", False),
        ("assets:asset_lifecycle_cost_analysis_detail", "lcc"),
        ("assets:asset_lifecycle_cost_analysis_edit", "lcc"),
        ("assets:asset_lifecycle_cost_analysis_delete", "lcc"),
        ("assets:asset_lifecycle_cost_analysis_populate", "lcc"),
        ("assets:asset_lifecycle_cost_analysis_transition", "lcc"),
        # ARPL (8 routes)
        ("assets:asset_replacement_plan_list", False),
        ("assets:asset_replacement_plan_create", False),
        ("assets:asset_replacement_plan_export_csv", False),
        ("assets:asset_replacement_plan_detail", "rpl"),
        ("assets:asset_replacement_plan_edit", "rpl"),
        ("assets:asset_replacement_plan_delete", "rpl"),
        ("assets:asset_replacement_plan_recalculate", "rpl"),
        ("assets:asset_replacement_plan_transition", "rpl"),
        # AWIF (8 routes)
        ("assets:asset_portfolio_scenario_list", False),
        ("assets:asset_portfolio_scenario_create", False),
        ("assets:asset_portfolio_scenario_export_csv", False),
        ("assets:asset_portfolio_scenario_detail", "awif"),
        ("assets:asset_portfolio_scenario_edit", "awif"),
        ("assets:asset_portfolio_scenario_delete", "awif"),
        ("assets:asset_portfolio_scenario_simulate", "awif"),
        ("assets:asset_portfolio_scenario_transition", "awif"),
        # AKPI (10 routes)
        ("assets:asset_executive_scorecard_list", False),
        ("assets:asset_executive_scorecard_create", False),
        ("assets:asset_executive_scorecard_export_csv", False),
        ("assets:asset_executive_scorecard_detail", "akpi"),
        ("assets:asset_executive_scorecard_edit", "akpi"),
        ("assets:asset_executive_scorecard_delete", "akpi"),
        ("assets:asset_executive_scorecard_compute", "akpi"),
        ("assets:asset_executive_scorecard_publish", "akpi"),
        ("assets:asset_executive_scorecard_approve", "akpi"),
        ("assets:asset_executive_scorecard_archive", "akpi"),
        # Dashboards & Comparison (3 routes)
        ("assets:portfolio_dashboard", False),
        ("assets:portfolio_dashboard_export_csv", False),
        ("assets:scenario_compare", False),
    ],
)
def test_assetanalytics_unauthenticated_redirects_to_login(
    method,
    url_name,
    needs_pk,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
):
    pk_map = {
        "lcc": analytics_lcc_a.pk,
        "rpl": analytics_rpl_a.pk,
        "awif": analytics_scenario_a.pk,
        "akpi": analytics_scorecard_a.pk,
    }
    url = reverse(url_name, args=[pk_map[needs_pk]]) if needs_pk else reverse(url_name)
    anon = Client()
    resp = getattr(anon, method)(url)
    assert resp.status_code == 302
    assert reverse(settings.LOGIN_URL) in resp["Location"]


# =====================================================================
# 2. Cross-Tenant IDOR & Tenant Data Isolation
# =====================================================================


@pytest.mark.parametrize(
    "url_name,entity_key,method",
    [
        # ALCC
        ("assets:asset_lifecycle_cost_analysis_detail", "lcc", "get"),
        ("assets:asset_lifecycle_cost_analysis_edit", "lcc", "get"),
        ("assets:asset_lifecycle_cost_analysis_edit", "lcc", "post"),
        ("assets:asset_lifecycle_cost_analysis_delete", "lcc", "post"),
        ("assets:asset_lifecycle_cost_analysis_populate", "lcc", "post"),
        ("assets:asset_lifecycle_cost_analysis_transition", "lcc", "post"),
        # ARPL
        ("assets:asset_replacement_plan_detail", "rpl", "get"),
        ("assets:asset_replacement_plan_edit", "rpl", "get"),
        ("assets:asset_replacement_plan_edit", "rpl", "post"),
        ("assets:asset_replacement_plan_delete", "rpl", "post"),
        ("assets:asset_replacement_plan_recalculate", "rpl", "post"),
        ("assets:asset_replacement_plan_transition", "rpl", "post"),
        # AWIF
        ("assets:asset_portfolio_scenario_detail", "awif", "get"),
        ("assets:asset_portfolio_scenario_edit", "awif", "get"),
        ("assets:asset_portfolio_scenario_edit", "awif", "post"),
        ("assets:asset_portfolio_scenario_delete", "awif", "post"),
        ("assets:asset_portfolio_scenario_simulate", "awif", "post"),
        ("assets:asset_portfolio_scenario_transition", "awif", "post"),
        # AKPI
        ("assets:asset_executive_scorecard_detail", "akpi", "get"),
        ("assets:asset_executive_scorecard_edit", "akpi", "get"),
        ("assets:asset_executive_scorecard_edit", "akpi", "post"),
        ("assets:asset_executive_scorecard_delete", "akpi", "post"),
        ("assets:asset_executive_scorecard_compute", "akpi", "post"),
        ("assets:asset_executive_scorecard_publish", "akpi", "post"),
        ("assets:asset_executive_scorecard_approve", "akpi", "post"),
        ("assets:asset_executive_scorecard_archive", "akpi", "post"),
    ],
)
def test_assetanalytics_cross_tenant_idor_returns_404_both_directions(
    url_name,
    entity_key,
    method,
    client_a,
    client_b,
    analytics_lcc_a,
    analytics_lcc_b,
    analytics_rpl_a,
    analytics_rpl_b,
    analytics_scenario_a,
    analytics_scenario_b,
    analytics_scorecard_a,
    analytics_scorecard_b,
):
    pairs = {
        "lcc": (analytics_lcc_a, analytics_lcc_b, AssetLifecycleCostAnalysis),
        "rpl": (analytics_rpl_a, analytics_rpl_b, AssetReplacementPlan),
        "awif": (analytics_scenario_a, analytics_scenario_b, AssetPortfolioScenario),
        "akpi": (analytics_scorecard_a, analytics_scorecard_b, AssetExecutiveScorecard),
    }
    rec_a, rec_b, model_cls = pairs[entity_key]

    # Tenant A requesting Tenant B's record -> 404
    url_b = reverse(url_name, args=[rec_b.pk])
    resp_ab = getattr(client_a, method)(url_b, data={"title": "Hijacked", "name": "Hijacked"})
    assert resp_ab.status_code == 404
    assert model_cls.objects.filter(pk=rec_b.pk).exists()

    # Tenant B requesting Tenant A's record -> 404
    url_a = reverse(url_name, args=[rec_a.pk])
    resp_ba = getattr(client_b, method)(url_a, data={"title": "Hijacked", "name": "Hijacked"})
    assert resp_ba.status_code == 404
    assert model_cls.objects.filter(pk=rec_a.pk).exists()


def test_assetanalytics_scenario_compare_cross_tenant_idor_returns_404(
    client_a,
    client_b,
    analytics_scenario_a,
    analytics_scenario_b,
):
    compare_url = reverse("assets:scenario_compare")

    # Tenant A requesting only Tenant B's scenario ID -> 404
    resp_ab = client_a.get(compare_url, {"scenarios": [str(analytics_scenario_b.pk)]})
    assert resp_ab.status_code == 404

    # Tenant B requesting only Tenant A's scenario ID -> 404
    resp_ba = client_b.get(compare_url, {"scenarios": [str(analytics_scenario_a.pk)]})
    assert resp_ba.status_code == 404

    # Mixed Tenant A + Tenant B IDs -> 200, only Tenant A scenario returned
    resp_mixed = client_a.get(
        compare_url,
        {"scenarios": [str(analytics_scenario_a.pk), str(analytics_scenario_b.pk)]},
    )
    assert resp_mixed.status_code == 200
    body = resp_mixed.content.decode("utf-8")
    assert [s.pk for s in resp_mixed.context["compared_scenarios"]] == [analytics_scenario_a.pk]
    assert analytics_scenario_a.number in body
    assert analytics_scenario_b.name not in body


def test_assetanalytics_list_dashboard_compare_and_csv_isolate_tenants(
    client_a,
    client_b,
    tenant_a,
    tenant_b,
    org_unit_a,
    org_unit_b,
    category_root_a,
    category_root_b,
    location_a,
    location_b,
    analytics_lcc_a,
    analytics_lcc_b,
    analytics_rpl_a,
    analytics_rpl_b,
    analytics_scenario_a,
    analytics_scenario_b,
    analytics_scorecard_a,
    analytics_scorecard_b,
):
    # List views
    checks = [
        (
            "assets:asset_lifecycle_cost_analysis_list",
            "analyses",
            analytics_lcc_a,
            analytics_lcc_b,
            analytics_lcc_a.title,
            analytics_lcc_b.title,
        ),
        (
            "assets:asset_replacement_plan_list",
            "plans",
            analytics_rpl_a,
            analytics_rpl_b,
            analytics_rpl_a.title,
            analytics_rpl_b.title,
        ),
        (
            "assets:asset_portfolio_scenario_list",
            "scenarios",
            analytics_scenario_a,
            analytics_scenario_b,
            analytics_scenario_a.name,
            analytics_scenario_b.name,
        ),
        (
            "assets:asset_executive_scorecard_list",
            "scorecards",
            analytics_scorecard_a,
            analytics_scorecard_b,
            analytics_scorecard_a.title,
            analytics_scorecard_b.title,
        ),
    ]
    for url_name, ctx_key, rec_a, rec_b, title_a, title_b in checks:
        resp_a = client_a.get(reverse(url_name))
        assert resp_a.status_code == 200
        assert all(obj.tenant_id == tenant_a.pk for obj in resp_a.context[ctx_key])
        assert rec_a.pk in [obj.pk for obj in resp_a.context[ctx_key]]
        assert rec_b.pk not in [obj.pk for obj in resp_a.context[ctx_key]]
        html_a = resp_a.content.decode("utf-8")
        assert rec_a.number in html_a
        assert title_b not in html_a
        assert org_unit_b.name not in html_a
        assert category_root_b.name not in html_a

        resp_b = client_b.get(reverse(url_name))
        assert resp_b.status_code == 200
        assert all(obj.tenant_id == tenant_b.pk for obj in resp_b.context[ctx_key])
        assert rec_b.pk in [obj.pk for obj in resp_b.context[ctx_key]]
        assert rec_a.pk not in [obj.pk for obj in resp_b.context[ctx_key]]
        html_b = resp_b.content.decode("utf-8")
        assert title_b in html_b
        assert title_a[:30] not in html_b
        assert org_unit_a.name not in html_b

    # Portfolio dashboard (default & with forged tenant_b filter params)
    dash_url = reverse("assets:portfolio_dashboard")
    dash_a = client_a.get(dash_url)
    assert dash_a.status_code == 200
    dash_html = dash_a.content.decode("utf-8")
    assert org_unit_b.name not in dash_html
    assert category_root_b.name not in dash_html
    assert location_b.name not in dash_html
    assert analytics_lcc_b.title not in dash_html
    assert analytics_scorecard_b.title not in dash_html

    dash_forged = client_a.get(
        dash_url,
        {
            "org_unit": str(org_unit_b.pk),
            "asset_category": str(category_root_b.pk),
            "location": str(location_b.pk),
        },
    )
    assert dash_forged.status_code == 200
    forged_html = dash_forged.content.decode("utf-8")
    assert analytics_lcc_b.title not in forged_html
    assert analytics_scorecard_b.title not in forged_html
    assert org_unit_a.name in forged_html

    # Default scenario compare
    cmp_a = client_a.get(reverse("assets:scenario_compare"))
    assert cmp_a.status_code == 200
    assert all(s.tenant_id == tenant_a.pk for s in cmp_a.context["all_scenarios"])
    cmp_html = cmp_a.content.decode("utf-8")
    assert analytics_scenario_a.number in cmp_html
    assert analytics_scenario_b.name not in cmp_html

    # All 5 CSV exports
    csv_checks = [
        ("assets:asset_lifecycle_cost_analysis_export_csv", analytics_lcc_a.title, analytics_lcc_b.title),
        ("assets:asset_replacement_plan_export_csv", analytics_rpl_a.title, analytics_rpl_b.title),
        ("assets:asset_portfolio_scenario_export_csv", analytics_scenario_a.name, analytics_scenario_b.name),
        ("assets:asset_executive_scorecard_export_csv", analytics_scorecard_a.title, analytics_scorecard_b.title),
        ("assets:portfolio_dashboard_export_csv", analytics_lcc_a.title, analytics_lcc_b.title),
    ]
    for url_name, own_marker, foreign_marker in csv_checks:
        resp_csv = client_a.get(reverse(url_name))
        _assetanalytics_parse_csv_response(resp_csv)
        text = resp_csv.content.decode("utf-8")
        assert own_marker in text
        assert foreign_marker not in text


def test_assetanalytics_cross_tenant_fk_injection_rejected_on_create_and_edit(
    client_a,
    currency_usd,
    fixed_asset_b,
    operational_asset_b,
    category_root_b,
    asset_model_b,
    org_unit_b,
    location_b,
    admin_b,
    analytics_lcc_a,
    analytics_lcc_b,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scenario_b,
    analytics_scorecard_a,
):
    # 1. ALCC create & edit with Tenant B FKs
    alcc_bad = _assetanalytics_alcc_payload(
        currency_usd,
        title="ALCC FK Injection Attempt",
        fixed_asset=str(fixed_asset_b.pk),
        operational_asset=str(operational_asset_b.pk),
        asset_category=str(category_root_b.pk),
        asset_model=str(asset_model_b.pk),
        org_unit=str(org_unit_b.pk),
        analyzed_by=str(admin_b.pk),
    )
    resp = client_a.post(reverse("assets:asset_lifecycle_cost_analysis_create"), data=alcc_bad)
    assert resp.status_code == 200
    assert not AssetLifecycleCostAnalysis.objects.filter(title="ALCC FK Injection Attempt").exists()

    resp_edit = client_a.post(
        reverse("assets:asset_lifecycle_cost_analysis_edit", args=[analytics_lcc_a.pk]),
        data=alcc_bad,
    )
    assert resp_edit.status_code == 200
    analytics_lcc_a.refresh_from_db()
    assert analytics_lcc_a.org_unit_id != org_unit_b.pk
    assert analytics_lcc_a.fixed_asset_id != fixed_asset_b.pk

    # 2. ARPL create & edit with Tenant B FKs
    arpl_bad = _assetanalytics_arpl_payload(
        currency_usd,
        title="ARPL FK Injection Attempt",
        fixed_asset=str(fixed_asset_b.pk),
        operational_asset=str(operational_asset_b.pk),
        asset_category=str(category_root_b.pk),
        asset_model=str(asset_model_b.pk),
        org_unit=str(org_unit_b.pk),
        location=str(location_b.pk),
        lifecycle_analysis=str(analytics_lcc_b.pk),
        planner=str(admin_b.pk),
    )
    resp = client_a.post(reverse("assets:asset_replacement_plan_create"), data=arpl_bad)
    assert resp.status_code == 200
    assert not AssetReplacementPlan.objects.filter(title="ARPL FK Injection Attempt").exists()

    resp_edit = client_a.post(
        reverse("assets:asset_replacement_plan_edit", args=[analytics_rpl_a.pk]),
        data=arpl_bad,
    )
    assert resp_edit.status_code == 200
    analytics_rpl_a.refresh_from_db()
    assert analytics_rpl_a.location_id != location_b.pk
    assert analytics_rpl_a.lifecycle_analysis_id != analytics_lcc_b.pk

    # 3. AWIF create & edit with Tenant B FKs
    awif_bad = _assetanalytics_awif_payload(
        currency_usd,
        name="AWIF FK Injection Attempt",
        scope_org_unit=str(org_unit_b.pk),
        scope_category=str(category_root_b.pk),
        baseline_scenario=str(analytics_scenario_b.pk),
        owner=str(admin_b.pk),
    )
    resp = client_a.post(reverse("assets:asset_portfolio_scenario_create"), data=awif_bad)
    assert resp.status_code == 200
    assert not AssetPortfolioScenario.objects.filter(name="AWIF FK Injection Attempt").exists()

    resp_edit = client_a.post(
        reverse("assets:asset_portfolio_scenario_edit", args=[analytics_scenario_a.pk]),
        data=awif_bad,
    )
    assert resp_edit.status_code == 200
    analytics_scenario_a.refresh_from_db()
    assert analytics_scenario_a.baseline_scenario_id != analytics_scenario_b.pk

    # 4. AKPI create & edit with Tenant B FKs
    akpi_bad = _assetanalytics_akpi_payload(
        currency_usd,
        title="AKPI FK Injection Attempt",
        org_unit=str(org_unit_b.pk),
        asset_category=str(category_root_b.pk),
        prepared_by=str(admin_b.pk),
    )
    resp = client_a.post(reverse("assets:asset_executive_scorecard_create"), data=akpi_bad)
    assert resp.status_code == 200
    assert not AssetExecutiveScorecard.objects.filter(title="AKPI FK Injection Attempt").exists()

    resp_edit = client_a.post(
        reverse("assets:asset_executive_scorecard_edit", args=[analytics_scorecard_a.pk]),
        data=akpi_bad,
    )
    assert resp_edit.status_code == 200
    analytics_scorecard_a.refresh_from_db()
    assert analytics_scorecard_a.prepared_by_id != admin_b.pk


# =====================================================================
# 3. RBAC & UI Permission Gating (member_client vs client_a)
# =====================================================================


@pytest.mark.parametrize(
    "url_name,entity_key,method",
    [
        # ALCC admin-only mutations
        ("assets:asset_lifecycle_cost_analysis_create", None, "get"),
        ("assets:asset_lifecycle_cost_analysis_create", None, "post"),
        ("assets:asset_lifecycle_cost_analysis_edit", "lcc", "get"),
        ("assets:asset_lifecycle_cost_analysis_edit", "lcc", "post"),
        ("assets:asset_lifecycle_cost_analysis_delete", "lcc", "post"),
        ("assets:asset_lifecycle_cost_analysis_populate", "lcc", "post"),
        ("assets:asset_lifecycle_cost_analysis_transition", "lcc", "post"),
        # ARPL admin-only mutations
        ("assets:asset_replacement_plan_create", None, "get"),
        ("assets:asset_replacement_plan_create", None, "post"),
        ("assets:asset_replacement_plan_edit", "rpl", "get"),
        ("assets:asset_replacement_plan_edit", "rpl", "post"),
        ("assets:asset_replacement_plan_delete", "rpl", "post"),
        ("assets:asset_replacement_plan_recalculate", "rpl", "post"),
        ("assets:asset_replacement_plan_transition", "rpl", "post"),
        # AWIF admin-only mutations
        ("assets:asset_portfolio_scenario_create", None, "get"),
        ("assets:asset_portfolio_scenario_create", None, "post"),
        ("assets:asset_portfolio_scenario_edit", "awif", "get"),
        ("assets:asset_portfolio_scenario_edit", "awif", "post"),
        ("assets:asset_portfolio_scenario_delete", "awif", "post"),
        ("assets:asset_portfolio_scenario_simulate", "awif", "post"),
        ("assets:asset_portfolio_scenario_transition", "awif", "post"),
        # AKPI admin-only mutations
        ("assets:asset_executive_scorecard_create", None, "get"),
        ("assets:asset_executive_scorecard_create", None, "post"),
        ("assets:asset_executive_scorecard_edit", "akpi", "get"),
        ("assets:asset_executive_scorecard_edit", "akpi", "post"),
        ("assets:asset_executive_scorecard_delete", "akpi", "post"),
        ("assets:asset_executive_scorecard_compute", "akpi", "post"),
        ("assets:asset_executive_scorecard_publish", "akpi", "post"),
        ("assets:asset_executive_scorecard_approve", "akpi_pub", "post"),
        ("assets:asset_executive_scorecard_archive", "akpi", "post"),
    ],
)
def test_assetanalytics_member_forbidden_403_on_admin_endpoints(
    url_name,
    entity_key,
    method,
    member_client,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
    analytics_scorecard_published_a,
):
    pk_map = {
        "lcc": analytics_lcc_a.pk,
        "rpl": analytics_rpl_a.pk,
        "awif": analytics_scenario_a.pk,
        "akpi": analytics_scorecard_a.pk,
        "akpi_pub": analytics_scorecard_published_a.pk,
    }
    url = reverse(url_name, args=[pk_map[entity_key]]) if entity_key else reverse(url_name)
    resp = getattr(member_client, method)(
        url,
        data={"title": "Member Mutate", "name": "Member Mutate", "target_status": "archived"},
    )
    assert resp.status_code == 403

    # Verify records were not deleted or transitioned
    assert AssetLifecycleCostAnalysis.objects.filter(pk=analytics_lcc_a.pk, status="draft").exists()
    assert AssetReplacementPlan.objects.filter(pk=analytics_rpl_a.pk, status="forecasted").exists()
    assert AssetPortfolioScenario.objects.filter(pk=analytics_scenario_a.pk, status="draft").exists()
    assert AssetExecutiveScorecard.objects.filter(pk=analytics_scorecard_a.pk, status="draft").exists()
    assert AssetExecutiveScorecard.objects.filter(pk=analytics_scorecard_published_a.pk, status="published").exists()


def test_assetanalytics_member_can_read_lists_details_dashboards_and_csv(
    member_client,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
):
    read_urls = [
        reverse("assets:asset_lifecycle_cost_analysis_list"),
        reverse("assets:asset_lifecycle_cost_analysis_detail", args=[analytics_lcc_a.pk]),
        reverse("assets:asset_replacement_plan_list"),
        reverse("assets:asset_replacement_plan_detail", args=[analytics_rpl_a.pk]),
        reverse("assets:asset_portfolio_scenario_list"),
        reverse("assets:asset_portfolio_scenario_detail", args=[analytics_scenario_a.pk]),
        reverse("assets:asset_executive_scorecard_list"),
        reverse("assets:asset_executive_scorecard_detail", args=[analytics_scorecard_a.pk]),
        reverse("assets:portfolio_dashboard"),
        reverse("assets:scenario_compare"),
    ]
    for url in read_urls:
        resp = member_client.get(url)
        assert resp.status_code == 200

    csv_urls = [
        reverse("assets:asset_lifecycle_cost_analysis_export_csv"),
        reverse("assets:asset_replacement_plan_export_csv"),
        reverse("assets:asset_portfolio_scenario_export_csv"),
        reverse("assets:asset_executive_scorecard_export_csv"),
        reverse("assets:portfolio_dashboard_export_csv"),
    ]
    for url in csv_urls:
        resp = member_client.get(url)
        _assetanalytics_parse_csv_response(resp)


def test_assetanalytics_ui_permission_gating_hides_admin_actions_for_member(
    client_a,
    member_client,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
    analytics_scorecard_published_a,
):
    # 1. List pages: Create/Edit/Delete hidden for member_client, visible for client_a
    list_cases = [
        (
            reverse("assets:asset_lifecycle_cost_analysis_list"),
            reverse("assets:asset_lifecycle_cost_analysis_create"),
            reverse("assets:asset_lifecycle_cost_analysis_edit", args=[analytics_lcc_a.pk]),
            reverse("assets:asset_lifecycle_cost_analysis_delete", args=[analytics_lcc_a.pk]),
        ),
        (
            reverse("assets:asset_replacement_plan_list"),
            reverse("assets:asset_replacement_plan_create"),
            reverse("assets:asset_replacement_plan_edit", args=[analytics_rpl_a.pk]),
            reverse("assets:asset_replacement_plan_delete", args=[analytics_rpl_a.pk]),
        ),
        (
            reverse("assets:asset_portfolio_scenario_list"),
            reverse("assets:asset_portfolio_scenario_create"),
            reverse("assets:asset_portfolio_scenario_edit", args=[analytics_scenario_a.pk]),
            reverse("assets:asset_portfolio_scenario_delete", args=[analytics_scenario_a.pk]),
        ),
        (
            reverse("assets:asset_executive_scorecard_list"),
            reverse("assets:asset_executive_scorecard_create"),
            reverse("assets:asset_executive_scorecard_edit", args=[analytics_scorecard_a.pk]),
            reverse("assets:asset_executive_scorecard_delete", args=[analytics_scorecard_a.pk]),
        ),
    ]
    for list_url, create_url, edit_url, delete_url in list_cases:
        member_html = member_client.get(list_url).content.decode("utf-8")
        assert create_url not in member_html
        assert edit_url not in member_html
        assert delete_url not in member_html

        admin_html = client_a.get(list_url).content.decode("utf-8")
        assert create_url in admin_html
        assert edit_url in admin_html
        assert delete_url in admin_html

    # 2. Detail pages: Sync/Recalculate/Simulate/Compute/Publish/Approve/Archive/Transition/Edit/Delete hidden for member
    detail_cases = [
        (
            reverse("assets:asset_lifecycle_cost_analysis_detail", args=[analytics_lcc_a.pk]),
            [
                reverse("assets:asset_lifecycle_cost_analysis_populate", args=[analytics_lcc_a.pk]),
                reverse("assets:asset_lifecycle_cost_analysis_transition", args=[analytics_lcc_a.pk]),
                reverse("assets:asset_lifecycle_cost_analysis_edit", args=[analytics_lcc_a.pk]),
                reverse("assets:asset_lifecycle_cost_analysis_delete", args=[analytics_lcc_a.pk]),
                "Sync Upstream Spend",
            ],
        ),
        (
            reverse("assets:asset_replacement_plan_detail", args=[analytics_rpl_a.pk]),
            [
                reverse("assets:asset_replacement_plan_recalculate", args=[analytics_rpl_a.pk]),
                reverse("assets:asset_replacement_plan_transition", args=[analytics_rpl_a.pk]),
                reverse("assets:asset_replacement_plan_edit", args=[analytics_rpl_a.pk]),
                reverse("assets:asset_replacement_plan_delete", args=[analytics_rpl_a.pk]),
                "Recalculate Scoring",
            ],
        ),
        (
            reverse("assets:asset_portfolio_scenario_detail", args=[analytics_scenario_a.pk]),
            [
                reverse("assets:asset_portfolio_scenario_simulate", args=[analytics_scenario_a.pk]),
                reverse("assets:asset_portfolio_scenario_transition", args=[analytics_scenario_a.pk]),
                reverse("assets:asset_portfolio_scenario_edit", args=[analytics_scenario_a.pk]),
                reverse("assets:asset_portfolio_scenario_delete", args=[analytics_scenario_a.pk]),
                "Run Simulation",
            ],
        ),
        (
            reverse("assets:asset_executive_scorecard_detail", args=[analytics_scorecard_a.pk]),
            [
                reverse("assets:asset_executive_scorecard_compute", args=[analytics_scorecard_a.pk]),
                reverse("assets:asset_executive_scorecard_publish", args=[analytics_scorecard_a.pk]),
                reverse("assets:asset_executive_scorecard_archive", args=[analytics_scorecard_a.pk]),
                reverse("assets:asset_executive_scorecard_edit", args=[analytics_scorecard_a.pk]),
                reverse("assets:asset_executive_scorecard_delete", args=[analytics_scorecard_a.pk]),
                "Compute Live KPIs",
                "Publish Snapshot",
            ],
        ),
        (
            reverse("assets:asset_executive_scorecard_detail", args=[analytics_scorecard_published_a.pk]),
            [
                reverse("assets:asset_executive_scorecard_approve", args=[analytics_scorecard_published_a.pk]),
                reverse("assets:asset_executive_scorecard_archive", args=[analytics_scorecard_published_a.pk]),
                "Board Approve",
            ],
        ),
    ]
    for detail_url, hidden_markers in detail_cases:
        member_html = member_client.get(detail_url).content.decode("utf-8")
        admin_html = client_a.get(detail_url).content.decode("utf-8")
        for marker in hidden_markers:
            assert marker not in member_html
            assert marker in admin_html


# =====================================================================
# 4. Superuser (tenant=None) Boundary (C1)
# =====================================================================


@pytest.mark.parametrize("method", ["get", "post"])
@pytest.mark.parametrize(
    "create_url_name",
    [
        "assets:asset_lifecycle_cost_analysis_create",
        "assets:asset_replacement_plan_create",
        "assets:asset_portfolio_scenario_create",
        "assets:asset_executive_scorecard_create",
    ],
)
def test_assetanalytics_superuser_tenant_none_create_redirects_cleanly(method, create_url_name):
    _, su_client = _assetanalytics_superuser_client()
    resp = getattr(su_client, method)(
        reverse(create_url_name),
        data={"title": "Should Redirect", "name": "Should Redirect"},
    )
    assert resp.status_code == 302
    assert resp["Location"] == reverse("assets:portfolio_dashboard")
    assert any("tenant workspace" in m.lower() for m in _assetanalytics_messages(resp))


def test_assetanalytics_forms_with_tenant_none_expose_zero_tenant_records(
    currency_usd,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    asset_model_a,
    org_unit_a,
    location_a,
    condition_assessment_a,
    analytics_lcc_a,
    requisition_a,
    analytics_scenario_a,
    admin_user,
):
    alcc_form = AssetLifecycleCostAnalysisForm(tenant=None)
    for fname in ("fixed_asset", "operational_asset", "asset_category", "asset_model", "org_unit", "analyzed_by"):
        assert alcc_form.fields[fname].queryset.count() == 0
    assert alcc_form.fields["currency"].queryset.filter(pk=currency_usd.pk).exists()

    arpl_form = AssetReplacementPlanForm(tenant=None)
    for fname in (
        "fixed_asset",
        "operational_asset",
        "asset_category",
        "asset_model",
        "org_unit",
        "location",
        "condition_assessment",
        "lifecycle_analysis",
        "capital_budget",
        "linked_requisition",
        "planner",
    ):
        assert arpl_form.fields[fname].queryset.count() == 0
    assert arpl_form.fields["currency"].queryset.filter(pk=currency_usd.pk).exists()

    awif_form = AssetPortfolioScenarioForm(tenant=None)
    for fname in ("scope_org_unit", "scope_category", "baseline_scenario", "owner"):
        assert awif_form.fields[fname].queryset.count() == 0
    assert awif_form.fields["currency"].queryset.filter(pk=currency_usd.pk).exists()

    akpi_form = AssetExecutiveScorecardForm(tenant=None)
    for fname in ("org_unit", "asset_category", "prepared_by"):
        assert akpi_form.fields[fname].queryset.count() == 0
    assert akpi_form.fields["currency"].queryset.filter(pk=currency_usd.pk).exists()


def test_assetanalytics_superuser_tenant_none_reads_leak_no_tenant_records(
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
):
    _, su_client = _assetanalytics_superuser_client()
    for url_name, leaked_number in [
        ("assets:asset_lifecycle_cost_analysis_list", analytics_lcc_a.number),
        ("assets:asset_replacement_plan_list", analytics_rpl_a.number),
        ("assets:asset_portfolio_scenario_list", analytics_scenario_a.number),
        ("assets:asset_executive_scorecard_list", analytics_scorecard_a.number),
        ("assets:portfolio_dashboard", analytics_lcc_a.number),
        ("assets:scenario_compare", analytics_scenario_a.number),
    ]:
        resp = su_client.get(reverse(url_name))
        assert resp.status_code == 200
        assert leaked_number not in resp.content.decode("utf-8")


# =====================================================================
# 5. Segregation of Duties (I2 — Executive Scorecard Board Approval)
# =====================================================================


def test_assetanalytics_scorecard_approve_blocks_self_approval_and_hides_button(
    client_a,
    admin_user,
    analytics_scorecard_a,
    analytics_scorecard_published_a,
):
    # Publish admin_user's own draft scorecard
    assert analytics_scorecard_a.prepared_by_id == admin_user.pk
    pub_resp = client_a.post(
        reverse("assets:asset_executive_scorecard_publish", args=[analytics_scorecard_a.pk])
    )
    assert pub_resp.status_code == 302
    analytics_scorecard_a.refresh_from_db()
    assert analytics_scorecard_a.status == "published"

    # Detail HTML must hide Board Approve button for the preparer (even though admin_user is tenant admin)
    detail_url = reverse("assets:asset_executive_scorecard_detail", args=[analytics_scorecard_a.pk])
    approve_url = reverse("assets:asset_executive_scorecard_approve", args=[analytics_scorecard_a.pk])
    detail_html = client_a.get(detail_url).content.decode("utf-8")
    assert approve_url not in detail_html
    assert "Board Approve" not in detail_html

    # Direct POST to approve by preparer must be blocked
    approve_resp = client_a.post(approve_url)
    assert approve_resp.status_code == 302
    analytics_scorecard_a.refresh_from_db()
    assert analytics_scorecard_a.status == "published"
    assert analytics_scorecard_a.approved_by is None
    assert any("segregation of duties" in m.lower() for m in _assetanalytics_messages(approve_resp))

    # Contrast: distinct tenant admin CAN see Board Approve & approve member_user's published scorecard
    other_detail_html = client_a.get(
        reverse("assets:asset_executive_scorecard_detail", args=[analytics_scorecard_published_a.pk])
    ).content.decode("utf-8")
    other_approve_url = reverse(
        "assets:asset_executive_scorecard_approve", args=[analytics_scorecard_published_a.pk]
    )
    assert other_approve_url in other_detail_html
    assert "Board Approve" in other_detail_html

    ok_resp = client_a.post(other_approve_url)
    assert ok_resp.status_code == 302
    analytics_scorecard_published_a.refresh_from_db()
    assert analytics_scorecard_published_a.status == "board_approved"
    assert analytics_scorecard_published_a.approved_by_id == admin_user.pk


# =====================================================================
# 6. Mass-Assignment, Workflow Bypass & Lock Enforcement (I3, I4, M1)
# =====================================================================


def test_assetanalytics_mass_assignment_cannot_forge_system_or_computed_fields(
    client_a,
    tenant_a,
    tenant_b,
    admin_user,
    currency_usd,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
):
    # 1. ALCC create & edit mass-assignment attempt
    alcc_payload = _assetanalytics_alcc_payload(
        currency_usd,
        title="Mass Assign ALCC",
        status="approved",
        tenant=str(tenant_b.pk),
        number="ALCC-FORGED-9999",
        total_lifecycle_cost="9999999.99",
        equivalent_annual_cost="888888.88",
        maintenance_to_rav_pct="99.99",
        opex_to_capex_ratio="50.00",
        economic_eol_year="2099",
        recommendation="dispose_retire",
    )
    resp = client_a.post(reverse("assets:asset_lifecycle_cost_analysis_create"), data=alcc_payload)
    assert resp.status_code == 302
    created_alcc = AssetLifecycleCostAnalysis.objects.get(title="Mass Assign ALCC")
    assert created_alcc.tenant_id == tenant_a.pk
    assert created_alcc.status == "draft"
    assert created_alcc.number.startswith("ALCC-")
    assert created_alcc.number != "ALCC-FORGED-9999"
    assert created_alcc.total_lifecycle_cost != Decimal("9999999.99")
    assert created_alcc.recommendation != "dispose_retire"

    client_a.post(
        reverse("assets:asset_lifecycle_cost_analysis_edit", args=[analytics_lcc_a.pk]),
        data={
            **_assetanalytics_alcc_payload(currency_usd, title="Edited ALCC"),
            "status": "approved",
            "tenant": str(tenant_b.pk),
            "number": "ALCC-FORGED-EDIT",
            "total_lifecycle_cost": "1.00",
        },
    )
    analytics_lcc_a.refresh_from_db()
    assert analytics_lcc_a.status == "draft"
    assert analytics_lcc_a.tenant_id == tenant_a.pk
    assert analytics_lcc_a.number != "ALCC-FORGED-EDIT"
    assert analytics_lcc_a.total_lifecycle_cost != Decimal("1.00")

    # 2. ARPL create & edit mass-assignment attempt
    arpl_payload = _assetanalytics_arpl_payload(
        currency_usd,
        title="Mass Assign ARPL",
        status="executed",
        tenant=str(tenant_b.pk),
        number="ARPL-FORGED-9999",
        priority_score="1.00",
        priority_band="low",
        fci_ratio_pct="999.00",
        inflation_adjusted_cost="1.00",
    )
    resp = client_a.post(reverse("assets:asset_replacement_plan_create"), data=arpl_payload)
    assert resp.status_code == 302
    created_arpl = AssetReplacementPlan.objects.get(title="Mass Assign ARPL")
    assert created_arpl.tenant_id == tenant_a.pk
    assert created_arpl.status == "forecasted"
    assert created_arpl.number != "ARPL-FORGED-9999"
    assert created_arpl.priority_band != "low"
    assert created_arpl.inflation_adjusted_cost > Decimal("1.00")

    client_a.post(
        reverse("assets:asset_replacement_plan_edit", args=[analytics_rpl_a.pk]),
        data={
            **_assetanalytics_arpl_payload(currency_usd, title="Edited ARPL"),
            "status": "approved",
            "priority_score": "0.00",
        },
    )
    analytics_rpl_a.refresh_from_db()
    assert analytics_rpl_a.status == "forecasted"
    assert analytics_rpl_a.priority_score > Decimal("0.00")

    # 3. AWIF create & edit mass-assignment attempt
    awif_payload = _assetanalytics_awif_payload(
        currency_usd,
        name="Mass Assign AWIF",
        status="adopted",
        tenant=str(tenant_b.pk),
        number="AWIF-FORGED-9999",
        simulated_capex_total="9999999.99",
        net_present_value="9999999.99",
    )
    resp = client_a.post(reverse("assets:asset_portfolio_scenario_create"), data=awif_payload)
    assert resp.status_code == 302
    created_awif = AssetPortfolioScenario.objects.get(name="Mass Assign AWIF")
    assert created_awif.tenant_id == tenant_a.pk
    assert created_awif.status == "draft"
    assert created_awif.number != "AWIF-FORGED-9999"
    assert created_awif.simulated_capex_total == Decimal("0.00")
    assert created_awif.net_present_value == Decimal("0.00")

    client_a.post(
        reverse("assets:asset_portfolio_scenario_edit", args=[analytics_scenario_a.pk]),
        data={
            **_assetanalytics_awif_payload(currency_usd, name="Edited AWIF"),
            "status": "adopted",
            "net_present_value": "777777.77",
        },
    )
    analytics_scenario_a.refresh_from_db()
    assert analytics_scenario_a.status == "draft"
    assert analytics_scenario_a.net_present_value == Decimal("0.00")

    # 4. AKPI create & edit mass-assignment attempt
    akpi_payload = _assetanalytics_akpi_payload(
        currency_usd,
        title="Mass Assign AKPI",
        status="board_approved",
        approved_by=str(admin_user.pk),
        rag_status="red",
        tenant=str(tenant_b.pk),
        number="AKPI-FORGED-9999",
        gross_replacement_value="9999999.99",
        asset_roi_pct="99.99",
    )
    resp = client_a.post(reverse("assets:asset_executive_scorecard_create"), data=akpi_payload)
    assert resp.status_code == 302
    created_akpi = AssetExecutiveScorecard.objects.get(title="Mass Assign AKPI")
    assert created_akpi.tenant_id == tenant_a.pk
    assert created_akpi.status == "draft"
    assert created_akpi.approved_by is None
    assert created_akpi.rag_status == "green"
    assert created_akpi.number != "AKPI-FORGED-9999"
    assert created_akpi.gross_replacement_value == Decimal("0.00")
    assert created_akpi.asset_roi_pct == Decimal("0.00")

    client_a.post(
        reverse("assets:asset_executive_scorecard_edit", args=[analytics_scorecard_a.pk]),
        data={
            **_assetanalytics_akpi_payload(currency_usd, title="Edited AKPI"),
            "status": "board_approved",
            "approved_by": str(admin_user.pk),
            "rag_status": "red",
        },
    )
    analytics_scorecard_a.refresh_from_db()
    assert analytics_scorecard_a.status == "draft"
    assert analytics_scorecard_a.approved_by is None
    assert analytics_scorecard_a.rag_status == "green"


def test_assetanalytics_illegal_workflow_transitions_rejected(
    client_a,
    analytics_lcc_a,
    analytics_lcc_locked_a,
    analytics_rpl_a,
    analytics_rpl_locked_a,
    analytics_scenario_a,
    analytics_scenario_locked_a,
    analytics_scorecard_a,
    analytics_scorecard_published_a,
):
    # ALCC illegal transitions
    for target in ("approved", "invalid_state"):
        resp = client_a.post(
            reverse("assets:asset_lifecycle_cost_analysis_transition", args=[analytics_lcc_a.pk]),
            data={"target_status": target},
        )
        assert resp.status_code == 302
        analytics_lcc_a.refresh_from_db()
        assert analytics_lcc_a.status == "draft"

    # ALCC approved -> draft/calculated/reviewed rejected, then archive and test archived -> calculated
    for target in ("draft", "calculated", "reviewed"):
        client_a.post(
            reverse("assets:asset_lifecycle_cost_analysis_transition", args=[analytics_lcc_locked_a.pk]),
            data={"target_status": target},
        )
        analytics_lcc_locked_a.refresh_from_db()
        assert analytics_lcc_locked_a.status == "approved"

    analytics_lcc_locked_a.status = "archived"
    analytics_lcc_locked_a.save(update_fields=["status"])
    client_a.post(
        reverse("assets:asset_lifecycle_cost_analysis_transition", args=[analytics_lcc_locked_a.pk]),
        data={"target_status": "calculated"},
    )
    analytics_lcc_locked_a.refresh_from_db()
    assert analytics_lcc_locked_a.status == "archived"

    # ARPL illegal transitions
    for target in ("scheduled", "executed", "bogus"):
        client_a.post(
            reverse("assets:asset_replacement_plan_transition", args=[analytics_rpl_a.pk]),
            data={"target_status": target},
        )
        analytics_rpl_a.refresh_from_db()
        assert analytics_rpl_a.status == "forecasted"

    analytics_rpl_locked_a.status = "executed"
    analytics_rpl_locked_a.save(update_fields=["status"])
    for target in ("proposed", "deferred", "cancelled"):
        client_a.post(
            reverse("assets:asset_replacement_plan_transition", args=[analytics_rpl_locked_a.pk]),
            data={"target_status": target},
        )
        analytics_rpl_locked_a.refresh_from_db()
        assert analytics_rpl_locked_a.status == "executed"

    # AWIF illegal transitions
    for target in ("recommended", "adopted", "bogus"):
        client_a.post(
            reverse("assets:asset_portfolio_scenario_transition", args=[analytics_scenario_a.pk]),
            data={"target_status": target},
        )
        analytics_scenario_a.refresh_from_db()
        assert analytics_scenario_a.status == "draft"

    for target in ("draft", "simulated", "recommended"):
        client_a.post(
            reverse("assets:asset_portfolio_scenario_transition", args=[analytics_scenario_locked_a.pk]),
            data={"target_status": target},
        )
        analytics_scenario_locked_a.refresh_from_db()
        assert analytics_scenario_locked_a.status == "adopted"

    # AKPI illegal workflow jumps: approve on draft, publish on published
    client_a.post(
        reverse("assets:asset_executive_scorecard_approve", args=[analytics_scorecard_a.pk])
    )
    analytics_scorecard_a.refresh_from_db()
    assert analytics_scorecard_a.status == "draft"

    client_a.post(
        reverse("assets:asset_executive_scorecard_publish", args=[analytics_scorecard_published_a.pk])
    )
    analytics_scorecard_published_a.refresh_from_db()
    assert analytics_scorecard_published_a.status == "published"


def test_assetanalytics_locked_records_cannot_be_edited_deleted_or_recomputed(
    client_a,
    currency_usd,
    analytics_lcc_locked_a,
    analytics_rpl_locked_a,
    analytics_scenario_locked_a,
    analytics_scorecard_published_a,
):
    # 1. Locked ALCC
    orig_lcc_title = analytics_lcc_locked_a.title
    assert client_a.get(
        reverse("assets:asset_lifecycle_cost_analysis_edit", args=[analytics_lcc_locked_a.pk])
    ).status_code == 302
    client_a.post(
        reverse("assets:asset_lifecycle_cost_analysis_edit", args=[analytics_lcc_locked_a.pk]),
        data=_assetanalytics_alcc_payload(currency_usd, title="Tampered Locked ALCC"),
    )
    client_a.post(
        reverse("assets:asset_lifecycle_cost_analysis_delete", args=[analytics_lcc_locked_a.pk])
    )
    client_a.post(
        reverse("assets:asset_lifecycle_cost_analysis_populate", args=[analytics_lcc_locked_a.pk])
    )
    analytics_lcc_locked_a.refresh_from_db()
    assert analytics_lcc_locked_a.title == orig_lcc_title
    assert analytics_lcc_locked_a.status == "approved"

    # 2. Locked ARPL
    orig_rpl_title = analytics_rpl_locked_a.title
    assert client_a.get(
        reverse("assets:asset_replacement_plan_edit", args=[analytics_rpl_locked_a.pk])
    ).status_code == 302
    client_a.post(
        reverse("assets:asset_replacement_plan_edit", args=[analytics_rpl_locked_a.pk]),
        data=_assetanalytics_arpl_payload(currency_usd, title="Tampered Locked ARPL"),
    )
    client_a.post(
        reverse("assets:asset_replacement_plan_delete", args=[analytics_rpl_locked_a.pk])
    )
    client_a.post(
        reverse("assets:asset_replacement_plan_recalculate", args=[analytics_rpl_locked_a.pk])
    )
    analytics_rpl_locked_a.refresh_from_db()
    assert analytics_rpl_locked_a.title == orig_rpl_title
    assert analytics_rpl_locked_a.status == "approved"

    # 3. Locked AWIF
    orig_awif_name = analytics_scenario_locked_a.name
    assert client_a.get(
        reverse("assets:asset_portfolio_scenario_edit", args=[analytics_scenario_locked_a.pk])
    ).status_code == 302
    client_a.post(
        reverse("assets:asset_portfolio_scenario_edit", args=[analytics_scenario_locked_a.pk]),
        data=_assetanalytics_awif_payload(currency_usd, name="Tampered Locked AWIF"),
    )
    client_a.post(
        reverse("assets:asset_portfolio_scenario_delete", args=[analytics_scenario_locked_a.pk])
    )
    client_a.post(
        reverse("assets:asset_portfolio_scenario_simulate", args=[analytics_scenario_locked_a.pk])
    )
    analytics_scenario_locked_a.refresh_from_db()
    assert analytics_scenario_locked_a.name == orig_awif_name
    assert analytics_scenario_locked_a.status == "adopted"

    # 4. Locked AKPI (published, board_approved, archived)
    orig_akpi_title = analytics_scorecard_published_a.title
    assert client_a.get(
        reverse("assets:asset_executive_scorecard_edit", args=[analytics_scorecard_published_a.pk])
    ).status_code == 302
    client_a.post(
        reverse("assets:asset_executive_scorecard_edit", args=[analytics_scorecard_published_a.pk]),
        data=_assetanalytics_akpi_payload(currency_usd, title="Tampered Locked AKPI"),
    )
    client_a.post(
        reverse("assets:asset_executive_scorecard_delete", args=[analytics_scorecard_published_a.pk])
    )
    client_a.post(
        reverse("assets:asset_executive_scorecard_compute", args=[analytics_scorecard_published_a.pk])
    )
    analytics_scorecard_published_a.refresh_from_db()
    assert analytics_scorecard_published_a.title == orig_akpi_title
    assert analytics_scorecard_published_a.status == "published"


def test_assetanalytics_django_admin_lock_permissions_and_readonly_fields(
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
    analytics_scorecard_published_a,
):
    su, _ = _assetanalytics_superuser_client()
    request = RequestFactory().get("/admin/")
    request.user = su

    akpi_admin = AssetExecutiveScorecardAdmin(AssetExecutiveScorecard, django_admin.site)
    # Draft scorecard is changeable/deletable by superuser
    assert akpi_admin.has_change_permission(request, obj=analytics_scorecard_a) is True
    assert akpi_admin.has_delete_permission(request, obj=analytics_scorecard_a) is True

    # Locked scorecards (published, board_approved, archived) are blocked in Django Admin
    for locked_status in ("published", "board_approved", "archived"):
        analytics_scorecard_published_a.status = locked_status
        assert akpi_admin.has_change_permission(request, obj=analytics_scorecard_published_a) is False
        assert akpi_admin.has_delete_permission(request, obj=analytics_scorecard_published_a) is False

    assert "status" in akpi_admin.get_readonly_fields(request, obj=analytics_scorecard_a)
    assert "approved_by" in akpi_admin.get_readonly_fields(request, obj=analytics_scorecard_a)

    # All 4 admins lock 'status' as readonly on existing objects
    alcc_admin = AssetLifecycleCostAnalysisAdmin(AssetLifecycleCostAnalysis, django_admin.site)
    arpl_admin = AssetReplacementPlanAdmin(AssetReplacementPlan, django_admin.site)
    awif_admin = AssetPortfolioScenarioAdmin(AssetPortfolioScenario, django_admin.site)
    assert "status" in alcc_admin.get_readonly_fields(request, obj=analytics_lcc_a)
    assert "status" in arpl_admin.get_readonly_fields(request, obj=analytics_rpl_a)
    assert "status" in awif_admin.get_readonly_fields(request, obj=analytics_scenario_a)


# =====================================================================
# 7. POST-Only Mutations, CSRF, CSV Formula Injection & Input Chaos
# =====================================================================


@pytest.mark.parametrize(
    "url_name,entity_key",
    [
        ("assets:asset_lifecycle_cost_analysis_delete", "lcc"),
        ("assets:asset_lifecycle_cost_analysis_populate", "lcc"),
        ("assets:asset_lifecycle_cost_analysis_transition", "lcc"),
        ("assets:asset_replacement_plan_delete", "rpl"),
        ("assets:asset_replacement_plan_recalculate", "rpl"),
        ("assets:asset_replacement_plan_transition", "rpl"),
        ("assets:asset_portfolio_scenario_delete", "awif"),
        ("assets:asset_portfolio_scenario_simulate", "awif"),
        ("assets:asset_portfolio_scenario_transition", "awif"),
        ("assets:asset_executive_scorecard_delete", "akpi"),
        ("assets:asset_executive_scorecard_compute", "akpi"),
        ("assets:asset_executive_scorecard_publish", "akpi"),
        ("assets:asset_executive_scorecard_approve", "akpi_pub"),
        ("assets:asset_executive_scorecard_archive", "akpi"),
    ],
)
def test_assetanalytics_get_on_post_only_mutations_returns_405_and_no_mutation(
    url_name,
    entity_key,
    client_a,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
    analytics_scorecard_published_a,
):
    pk_map = {
        "lcc": analytics_lcc_a.pk,
        "rpl": analytics_rpl_a.pk,
        "awif": analytics_scenario_a.pk,
        "akpi": analytics_scorecard_a.pk,
        "akpi_pub": analytics_scorecard_published_a.pk,
    }
    resp = client_a.get(reverse(url_name, args=[pk_map[entity_key]]))
    assert resp.status_code == 405

    assert AssetLifecycleCostAnalysis.objects.filter(pk=analytics_lcc_a.pk, status="draft").exists()
    assert AssetReplacementPlan.objects.filter(pk=analytics_rpl_a.pk, status="forecasted").exists()
    assert AssetPortfolioScenario.objects.filter(pk=analytics_scenario_a.pk, status="draft").exists()
    assert AssetExecutiveScorecard.objects.filter(pk=analytics_scorecard_a.pk, status="draft").exists()
    assert AssetExecutiveScorecard.objects.filter(pk=analytics_scorecard_published_a.pk, status="published").exists()


def test_assetanalytics_csrf_enforced_blocks_forged_post_without_token(
    admin_user,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
):
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    for url in [
        reverse("assets:asset_lifecycle_cost_analysis_delete", args=[analytics_lcc_a.pk]),
        reverse("assets:asset_replacement_plan_delete", args=[analytics_rpl_a.pk]),
        reverse("assets:asset_portfolio_scenario_delete", args=[analytics_scenario_a.pk]),
        reverse("assets:asset_executive_scorecard_delete", args=[analytics_scorecard_a.pk]),
        reverse("assets:asset_executive_scorecard_publish", args=[analytics_scorecard_a.pk]),
    ]:
        resp = csrf_client.post(url)
        assert resp.status_code == 403

    assert AssetLifecycleCostAnalysis.objects.filter(pk=analytics_lcc_a.pk).exists()
    assert AssetReplacementPlan.objects.filter(pk=analytics_rpl_a.pk).exists()
    assert AssetPortfolioScenario.objects.filter(pk=analytics_scenario_a.pk).exists()
    assert AssetExecutiveScorecard.objects.filter(pk=analytics_scorecard_a.pk, status="draft").exists()


def test_assetanalytics_csv_formula_injection_neutralized_across_all_5_exports(
    client_a,
    tenant_a,
):
    # Direct unit verification on dangerous prefixes
    for payload in ("=CMD()", "+SUM(1,2)", "-1+1", "@SUM(A1:A2)", "\t=1", "\r+1", "\n-1", " =CMD()"):
        assert csv_safe(payload).startswith("'")

    # 1. ALCC CSV export
    AssetLifecycleCostAnalysis.objects.create(
        tenant=tenant_a,
        number="=CMD()",
        title="+SUM(1,2)",
        analysis_date=timezone.localdate(),
    )
    alcc_rows = _assetanalytics_parse_csv_response(
        client_a.get(reverse("assets:asset_lifecycle_cost_analysis_export_csv"))
    )
    alcc_flat = [cell for row in alcc_rows[1:] for cell in row]
    assert "'=CMD()" in alcc_flat
    assert "'+SUM(1,2)" in alcc_flat
    assert "=CMD()" not in alcc_flat
    assert "+SUM(1,2)" not in alcc_flat

    # 2. ARPL CSV export
    AssetReplacementPlan.objects.create(
        tenant=tenant_a,
        title="-1+1",
        planned_replacement_year=timezone.localdate().year + 1,
    )
    arpl_rows = _assetanalytics_parse_csv_response(
        client_a.get(reverse("assets:asset_replacement_plan_export_csv"))
    )
    arpl_flat = [cell for row in arpl_rows[1:] for cell in row]
    assert "'-1+1" in arpl_flat
    assert "-1+1" not in arpl_flat

    # 3. AWIF CSV export
    AssetPortfolioScenario.objects.create(
        tenant=tenant_a,
        name="@SUM(A1:A2)",
        base_fiscal_year=timezone.localdate().year,
    )
    awif_rows = _assetanalytics_parse_csv_response(
        client_a.get(reverse("assets:asset_portfolio_scenario_export_csv"))
    )
    awif_flat = [cell for row in awif_rows[1:] for cell in row]
    assert "'@SUM(A1:A2)" in awif_flat
    assert "@SUM(A1:A2)" not in awif_flat

    # 4. AKPI CSV export
    today = timezone.localdate()
    AssetExecutiveScorecard.objects.create(
        tenant=tenant_a,
        title="=HYPERLINK(\"http://evil\",\"click\")",
        period_start=today - timedelta(days=30),
        period_end=today,
    )
    akpi_rows = _assetanalytics_parse_csv_response(
        client_a.get(reverse("assets:asset_executive_scorecard_export_csv"))
    )
    akpi_flat = [cell for row in akpi_rows[1:] for cell in row]
    assert "'=HYPERLINK(\"http://evil\",\"click\")" in akpi_flat
    assert "=HYPERLINK(\"http://evil\",\"click\")" not in akpi_flat

    # 5. Portfolio Dashboard CSV export (bad_actors emits f"{ba.number} - {ba.title}")
    dash_rows = _assetanalytics_parse_csv_response(
        client_a.get(reverse("assets:portfolio_dashboard_export_csv"))
    )
    dash_col2 = [row[1] for row in dash_rows[1:] if len(row) > 1]
    assert any(cell.startswith("'=CMD() - ") for cell in dash_col2)
    assert not any(cell.startswith("=CMD()") for cell in dash_col2)


def test_assetanalytics_adversarial_query_and_numeric_chaos_never_500s(
    client_a,
    currency_usd,
):
    chaos_params = {
        "q": "\x00'\"<>%s%n",
        "status": "invalid_choice_value",
        "lifecycle_stage": "bogus",
        "recommendation": "bogus",
        "funding_status": "bogus",
        "priority_band": "bogus",
        "replacement_strategy": "bogus",
        "scenario_type": "bogus",
        "period_type": "bogus",
        "rag_status": "bogus",
        "org_unit": "99999999999999999999",
        "scope_org_unit": "-999",
        "asset_category": "NaN",
        "scope_category": "Infinity",
        "location": "abc; DROP TABLE assets;",
        "fiscal_year": "99999",
        "planned_replacement_year": "99999999999999999999",
        "base_fiscal_year": "NaN",
        "page": "99999999999999999999",
    }

    for url_name in (
        "assets:asset_lifecycle_cost_analysis_list",
        "assets:asset_replacement_plan_list",
        "assets:asset_portfolio_scenario_list",
        "assets:asset_executive_scorecard_list",
        "assets:portfolio_dashboard",
        "assets:asset_lifecycle_cost_analysis_export_csv",
        "assets:asset_replacement_plan_export_csv",
        "assets:asset_portfolio_scenario_export_csv",
        "assets:asset_executive_scorecard_export_csv",
        "assets:portfolio_dashboard_export_csv",
    ):
        resp = client_a.get(reverse(url_name), data=chaos_params)
        assert resp.status_code == 200

    # scenario_compare with chaotic non-integer / out-of-range scenario params
    for bad_scenarios in (
        ["NaN", "Infinity", "-5", "abc"],
        ["99999999999999999999"],
    ):
        resp = client_a.get(reverse("assets:scenario_compare"), data={"scenarios": bad_scenarios})
        assert resp.status_code == 200

    # Adversarial numeric chaos in POST forms must fail cleanly with 200 (never 500)
    assert (
        client_a.post(
            reverse("assets:asset_lifecycle_cost_analysis_create"),
            data=_assetanalytics_alcc_payload(
                currency_usd,
                analysis_horizon_years="9999",
                discount_rate_pct="NaN",
                acquisition_capital_cost="Infinity",
            ),
        ).status_code
        == 200
    )
    assert (
        client_a.post(
            reverse("assets:asset_replacement_plan_create"),
            data=_assetanalytics_arpl_payload(
                currency_usd,
                planned_replacement_year="99999",
                criticality_weight="999",
                condition_score="NaN",
                estimated_replacement_cost="Infinity",
            ),
        ).status_code
        == 200
    )
    assert (
        client_a.post(
            reverse("assets:asset_portfolio_scenario_create"),
            data=_assetanalytics_awif_payload(
                currency_usd,
                horizon_years="9999",
                base_fiscal_year="99999",
                discount_rate_pct="NaN",
                fleet_growth_pct="Infinity",
            ),
        ).status_code
        == 200
    )
    assert (
        client_a.post(
            reverse("assets:asset_executive_scorecard_create"),
            data=_assetanalytics_akpi_payload(
                currency_usd,
                target_asset_roi_pct="NaN",
                target_mcr_pct="Infinity",
                target_compliance_rate_pct="150.00",
            ),
        ).status_code
        == 200
    )
