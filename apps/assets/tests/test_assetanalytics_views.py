"""
View, workflow, filter, pagination, CSV export, computed dashboard, navigation,
and query-budget tests for Sub-module 11.14: Asset Analytics & Business Intelligence.
"""

from __future__ import annotations

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.accounting.models import Currency, FixedAsset
from apps.accounts.models import User
from apps.assets.models import (
    AssetCategory,
    AssetConditionAssessment,
    AssetExecutiveScorecard,
    AssetLifecycleCostAnalysis,
    AssetPortfolioScenario,
    AssetReplacementPlan,
    AssetRiskRegister,
)
from apps.assets.templatetags.asset_analytics_tags import fmt_money
from apps.assets.views.AssetAnalytics._helpers import (
    PAGE_SIZE,
    apply_choice_filter,
    apply_fk_filter,
    csv_export_response,
    csv_safe,
    parse_pos_int,
)
from apps.core.models import AuditLog, OrgUnit
from apps.core.navigation import LIVE_LINKS
from apps.scm.models import Asset, Location

pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (_assetanalytics_*)
# =====================================================================


def _assetanalytics_messages(response):
    """Return queued Django flash message strings for a response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _assetanalytics_assert_no_template_leaks(html):
    """Ensure rendered HTML has no leaked Django template comment markers."""
    assert "{#" not in html
    assert "{% comment" not in html


def _assetanalytics_superuser_client():
    """Create and log in a tenant-less platform superuser (tenant=None)."""
    su = User.objects.create_superuser(
        email="platform_super_11_14_views@naverp.test",
        username="platform_super_11_14_views",
        password="TestPass123!",
        tenant=None,
    )
    client = Client()
    client.force_login(su)
    return client


def _assetanalytics_audit_logs_for(obj, action=None):
    ct = ContentType.objects.get_for_model(obj.__class__)
    qs = AuditLog.objects.filter(content_type=ct, object_id=obj.pk)
    if action:
        qs = qs.filter(action=action)
    return qs


def _assetanalytics_make_alcc(tenant, title="ALCC Study", **kwargs):
    data = {
        "tenant": tenant,
        "title": title,
        "analysis_date": timezone.localdate(),
        "analysis_horizon_years": 5,
        "discount_rate_pct": Decimal("8.00"),
        "lifecycle_stage": "in_service",
        "status": "draft",
        "acquisition_capital_cost": Decimal("50000.00"),
        "current_replacement_value": Decimal("60000.00"),
    }
    data.update(kwargs)
    obj = AssetLifecycleCostAnalysis(**data)
    obj.save()
    return obj


def _assetanalytics_make_arpl(tenant, title="ARPL Plan", **kwargs):
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
        "current_replacement_value": Decimal("100000.00"),
        "deferred_maintenance_cost": Decimal("25000.00"),
        "estimated_replacement_cost": Decimal("105000.00"),
        "inflation_rate_pct": Decimal("4.00"),
    }
    data.update(kwargs)
    obj = AssetReplacementPlan(**data)
    obj.save()
    return obj


def _assetanalytics_make_awif(tenant, name="AWIF Scenario", **kwargs):
    data = {
        "tenant": tenant,
        "name": name,
        "scenario_type": "baseline_bau",
        "base_fiscal_year": timezone.localdate().year,
        "horizon_years": 5,
        "status": "draft",
    }
    data.update(kwargs)
    obj = AssetPortfolioScenario(**data)
    obj.save()
    return obj


def _assetanalytics_make_akpi(tenant, title="AKPI Scorecard", **kwargs):
    today = timezone.localdate()
    data = {
        "tenant": tenant,
        "title": title,
        "period_type": "quarterly",
        "period_start": today - timedelta(days=90),
        "period_end": today,
        "status": "draft",
        "rag_status": "green",
    }
    data.update(kwargs)
    obj = AssetExecutiveScorecard(**data)
    obj.save()
    return obj


def _assetanalytics_alcc_post(currency=None, **overrides):
    data = {
        "title": "Cooling Plant TCO Evaluation",
        "currency": str(currency.pk) if currency else "",
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
        "notes": "Baseline HVAC lifecycle study.",
    }
    data.update(overrides)
    return data


def _assetanalytics_arpl_post(currency=None, **overrides):
    data = {
        "title": "Substation Transformer Replacement",
        "currency": str(currency.pk) if currency else "",
        "predicted_eol_date": (timezone.localdate() + timedelta(days=365)).isoformat(),
        "remaining_useful_life_months": "12",
        "planned_replacement_year": str(timezone.localdate().year + 1),
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


def _assetanalytics_awif_post(currency=None, **overrides):
    data = {
        "name": "FY2027 Fleet Modernization Scenario",
        "scenario_type": "accelerated_replacement",
        "base_fiscal_year": str(timezone.localdate().year),
        "horizon_years": "5",
        "currency": str(currency.pk) if currency else "",
        "annual_capex_budget_limit": "450000.00",
        "discount_rate_pct": "8.00",
        "inflation_rate_pct": "4.00",
        "acceleration_months": "12",
        "fleet_growth_pct": "5.00",
        "consolidation_reduction_pct": "0.00",
        "maintenance_efficiency_gain_pct": "10.00",
        "assumptions_summary": "Accelerate critical asset replacement by 12 months.",
    }
    data.update(overrides)
    return data


def _assetanalytics_akpi_post(currency=None, **overrides):
    today = timezone.localdate()
    data = {
        "title": "Q4 Board Executive Asset Scorecard",
        "period_type": "quarterly",
        "period_start": (today - timedelta(days=90)).isoformat(),
        "period_end": today.isoformat(),
        "currency": str(currency.pk) if currency else "",
        "target_asset_roi_pct": "12.00",
        "target_mcr_pct": "3.50",
        "target_compliance_rate_pct": "95.00",
        "annual_asset_return_amount": "45000.00",
        "executive_summary": "Quarterly board asset performance brief.",
    }
    data.update(overrides)
    return data


def _assetanalytics_parse_csv_response(response):
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert response["Content-Disposition"].startswith('attachment; filename="')
    assert response["X-Content-Type-Options"] == "nosniff"
    text = response.content.decode("utf-8")
    return list(csv.reader(io.StringIO(text)))


# =====================================================================
# 1. _helpers.py & fmt_money Template Tag Tests
# =====================================================================


def test_assetanalytics_parse_pos_int_bounds_and_invalid_inputs():
    # Valid inputs
    assert parse_pos_int("1") == 1
    assert parse_pos_int(" 42 ") == 42
    assert parse_pos_int(7) == 7
    assert parse_pos_int("2147483647") == 2_147_483_647

    # Rejected inputs: None, empty, 0, > 32-bit int, > 10 chars, non-ASCII, non-digits
    assert parse_pos_int(None) is None
    assert parse_pos_int("") is None
    assert parse_pos_int("   ") is None
    assert parse_pos_int("0") is None
    assert parse_pos_int("0000") is None
    assert parse_pos_int("-5") is None
    assert parse_pos_int("abc") is None
    assert parse_pos_int("12.34") is None
    assert parse_pos_int("1e3") is None
    assert parse_pos_int("12345678901") is None  # > 10 chars
    assert parse_pos_int("2147483648") is None  # > 2_147_483_647
    assert parse_pos_int("9999999999") is None
    assert parse_pos_int("١٢٣") is None  # non-ASCII Arabic-Indic digits
    assert parse_pos_int("12é") is None


def test_assetanalytics_apply_choice_filter_ignores_unrecognized_and_filters_valid(
    tenant_a, analytics_lcc_a, analytics_lcc_locked_a
):
    rf = RequestFactory()
    base_qs = AssetLifecycleCostAnalysis.objects.filter(tenant=tenant_a)
    allowed = {k for k, _ in AssetLifecycleCostAnalysis.STATUS_CHOICES}
    assert base_qs.count() == 2

    # Blank parameter returns qs unchanged
    req_empty = rf.get("/analytics/lifecycle-cost/")
    assert apply_choice_filter(base_qs, req_empty, "status", allowed_values=allowed).count() == 2

    # Unrecognized GET choice value MUST be ignored (returns qs unchanged — GAP-assets-11.16-04 / L11)
    req_junk = rf.get("/analytics/lifecycle-cost/?status=invalid_nonexistent_status")
    junk_qs = apply_choice_filter(base_qs, req_junk, "status", allowed_values=allowed)
    assert list(junk_qs.order_by("pk")) == list(base_qs.order_by("pk"))

    # Exact valid value filters strictly (L44)
    req_draft = rf.get("/analytics/lifecycle-cost/?status=draft")
    draft_qs = apply_choice_filter(base_qs, req_draft, "status", allowed_values=allowed)
    assert list(draft_qs) == [analytics_lcc_a]

    req_approved = rf.get("/analytics/lifecycle-cost/?status=approved")
    approved_qs = apply_choice_filter(base_qs, req_approved, "status", allowed_values=allowed)
    assert list(approved_qs) == [analytics_lcc_locked_a]

    # field_name override works
    req_stage = rf.get("/analytics/lifecycle-cost/?stage=late_life")
    stage_allowed = {k for k, _ in AssetLifecycleCostAnalysis.LIFECYCLE_STAGE_CHOICES}
    stage_qs = apply_choice_filter(
        base_qs, req_stage, "stage", field_name="lifecycle_stage", allowed_values=stage_allowed
    )
    assert list(stage_qs) == [analytics_lcc_locked_a]


def test_assetanalytics_apply_fk_filter_valid_and_junk(
    tenant_a, category_root_a, category_child_a
):
    rf = RequestFactory()
    a1 = _assetanalytics_make_alcc(tenant_a, title="Cat Root Study", asset_category=category_root_a)
    a2 = _assetanalytics_make_alcc(tenant_a, title="Cat Child Study", asset_category=category_child_a)
    base_qs = AssetLifecycleCostAnalysis.objects.filter(pk__in=[a1.pk, a2.pk])

    req_valid = rf.get(f"/analytics/lifecycle-cost/?asset_category={category_child_a.pk}")
    assert list(apply_fk_filter(base_qs, req_valid, "asset_category")) == [a2]

    for junk in ("abc", "0", "-1", "99999999999", "١٢"):
        req_junk = rf.get(f"/analytics/lifecycle-cost/?asset_category={junk}")
        assert apply_fk_filter(base_qs, req_junk, "asset_category").count() == 2


def test_assetanalytics_csv_safe_and_export_response():
    assert csv_safe(None) == ""
    assert csv_safe("Pump 101") == "Pump 101"
    assert csv_safe("=CMD()") == "'=CMD()"
    assert csv_safe("+1+1") == "'+1+1"
    assert csv_safe("-100") == "'-100"
    assert csv_safe("@SUM(A1)") == "'@SUM(A1)"
    assert csv_safe("   =HYPERLINK()") == "'   =HYPERLINK()"
    assert csv_safe("\tcmd") == "'\tcmd"
    assert csv_safe("\rcmd") == "'\rcmd"
    assert csv_safe("\ncmd") == "'\ncmd"

    resp = csv_export_response(
        filename='bad/../name"test.csv',
        headers=["Name", "=Header"],
        rows=[["=Evil", "+Formula"], ["-Minus", "@At"]],
    )
    assert resp["X-Content-Type-Options"] == "nosniff"
    assert 'attachment; filename="bad..nametest.csv"' == resp["Content-Disposition"]
    parsed = list(csv.reader(io.StringIO(resp.content.decode("utf-8"))))
    assert parsed == [
        ["Name", "'=Header"],
        ["'=Evil", "'+Formula"],
        ["'-Minus", "'@At"],
    ]


def test_assetanalytics_fmt_money_dynamic_currency_and_leading_minus(db):
    eur, _ = Currency.objects.get_or_create(
        code="EUR", defaults={"name": "Euro", "symbol": "€", "is_active": True}
    )
    chf, _ = Currency.objects.get_or_create(
        code="CHF", defaults={"name": "Swiss Franc", "symbol": "", "is_active": True}
    )

    assert fmt_money(Decimal("1234.56")) == "$1,234.56"
    assert fmt_money(Decimal("-1234.56"), eur) == "-€1,234.56"
    assert fmt_money(Decimal("500.00"), eur, negate=True) == "-€500.00"
    assert fmt_money(Decimal("-42.10"), chf) == "-CHF 42.10"
    assert fmt_money(Decimal("-0.004"), eur) == "€0.00"
    assert fmt_money(None) == "$0.00"


# =====================================================================
# 2. ALCC (AssetLifecycleCostAnalysis) Views, Filters, Pagination, Workflows, CSV
# =====================================================================


def test_assetanalytics_alcc_list_filters_empty_and_pagination(
    client_a,
    tenant_a,
    tenant_b,
    analytics_lcc_a,
    analytics_lcc_locked_a,
    analytics_lcc_b,
    category_root_a,
    category_child_a,
    org_unit_a,
):
    # Extra distinct record for filter differentiation
    other_ou = OrgUnit.objects.create(tenant=tenant_a, name="Plant 2 Finishing", kind="department")
    extra = _assetanalytics_make_alcc(
        tenant_a,
        title="Finishing Compressor Study",
        asset_category=category_child_a,
        org_unit=other_ou,
        lifecycle_stage="end_of_life",
        status="reviewed",
        preventive_maintenance_cost=Decimal("50000.00"),
        current_replacement_value=Decimal("60000.00"),
    )

    url = reverse("assets:asset_lifecycle_cost_analysis_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    html = resp.content.decode()
    _assetanalytics_assert_no_template_leaks(html)

    # Context contract verification
    for key in (
        "analyses",
        "page_obj",
        "paginator",
        "is_paginated",
        "status_choices",
        "stage_choices",
        "recommendation_choices",
        "categories",
        "org_units",
        "total_analyses",
        "avg_tco",
        "replace_candidates_count",
        "total_tco_value",
    ):
        assert key in resp.context

    assert analytics_lcc_a.number in html
    assert analytics_lcc_a.title in html
    assert analytics_lcc_b.title not in html
    assert analytics_lcc_b not in resp.context["page_obj"].object_list
    assert resp.context["total_analyses"] == 3

    # Search filter (?q=)
    r_q = client_a.get(url, {"q": extra.number})
    assert list(r_q.context["page_obj"]) == [extra]
    assert extra.title in r_q.content.decode()
    assert analytics_lcc_a.title not in r_q.content.decode()

    # Choice filters (?status=, ?lifecycle_stage=, ?recommendation=)
    r_st = client_a.get(url, {"status": "approved"})
    assert list(r_st.context["page_obj"]) == [analytics_lcc_locked_a]

    r_stg = client_a.get(url, {"lifecycle_stage": "end_of_life"})
    assert list(r_stg.context["page_obj"]) == [extra]

    r_rec = client_a.get(url, {"recommendation": "dispose_retire"})
    assert list(r_rec.context["page_obj"]) == [extra]

    # FK filters (?asset_category=, ?org_unit=)
    r_cat = client_a.get(url, {"asset_category": category_child_a.pk})
    assert list(r_cat.context["page_obj"]) == [extra]

    r_ou = client_a.get(url, {"org_unit": other_ou.pk})
    assert list(r_ou.context["page_obj"]) == [extra]

    # Junk params ignored without 500
    r_junk = client_a.get(
        url,
        {
            "status": "junk_status",
            "lifecycle_stage": "junk_stage",
            "recommendation": "junk_rec",
            "asset_category": "notanint",
            "org_unit": "99999999999",
        },
    )
    assert r_junk.status_code == 200
    assert r_junk.context["paginator"].count == 3

    # Empty state rendering
    r_empty = client_a.get(url, {"q": "NO_SUCH_ALCC_STUDY_XYZ"})
    assert r_empty.status_code == 200
    assert r_empty.context["paginator"].count == 0
    _assetanalytics_assert_no_template_leaks(r_empty.content.decode())

    # Pagination at PAGE_SIZE = 15 (create 14 more -> total 17)
    for i in range(14):
        _assetanalytics_make_alcc(tenant_a, title=f"Paginated ALCC Study {i:02d}")

    r_p1 = client_a.get(url)
    assert r_p1.status_code == 200
    assert r_p1.context["is_paginated"] is True
    assert r_p1.context["paginator"].num_pages == 2
    assert len(r_p1.context["page_obj"]) == PAGE_SIZE

    r_p2 = client_a.get(url, {"page": 2})
    assert r_p2.status_code == 200
    assert r_p2.context["page_obj"].number == 2
    assert len(r_p2.context["page_obj"]) == 2

    # Out-of-range page handled gracefully
    r_p999 = client_a.get(url, {"page": 999})
    assert r_p999.status_code == 200
    assert r_p999.context["page_obj"].number == 2


def test_assetanalytics_alcc_crud_dynamic_currency_and_lock(
    client_a, tenant_a, admin_user, currency_usd, analytics_lcc_locked_a
):
    eur, _ = Currency.objects.get_or_create(
        code="EUR", defaults={"name": "Euro", "symbol": "€", "is_active": True}
    )

    # Create GET
    create_url = reverse("assets:asset_lifecycle_cost_analysis_create")
    r_get = client_a.get(create_url)
    assert r_get.status_code == 200
    assert r_get.context["is_edit"] is False
    assert r_get.context["analysis"] is None
    _assetanalytics_assert_no_template_leaks(r_get.content.decode())

    # Create POST with EUR currency & non-zero salvage value
    r_post = client_a.post(
        create_url,
        data=_assetanalytics_alcc_post(
            currency=eur,
            title="Euro Chiller Lifecycle Study",
            expected_salvage_value="8500.00",
        ),
    )
    assert r_post.status_code == 302
    created = AssetLifecycleCostAnalysis.objects.get(
        tenant=tenant_a, title="Euro Chiller Lifecycle Study"
    )
    assert created.analyzed_by == admin_user
    assert _assetanalytics_audit_logs_for(created, action="create").exists()

    # Tenant=None superuser blocked on create
    su_client = _assetanalytics_superuser_client()
    r_su = su_client.get(create_url)
    assert r_su.status_code == 302
    assert r_su.url == reverse("assets:portfolio_dashboard")

    # Detail GET + context keys + dynamic currency leading '-' sign
    detail_url = reverse("assets:asset_lifecycle_cost_analysis_detail", args=[created.pk])
    r_det = client_a.get(detail_url)
    assert r_det.status_code == 200
    for key in ("analysis", "total_capex", "total_maint", "total_opex", "total_recoveries"):
        assert key in r_det.context
    det_html = r_det.content.decode()
    _assetanalytics_assert_no_template_leaks(det_html)
    assert created.number in det_html
    assert created.title in det_html
    assert "-€8,500.00" in det_html

    # Edit GET & POST on unlocked
    edit_url = reverse("assets:asset_lifecycle_cost_analysis_edit", args=[created.pk])
    r_edit_get = client_a.get(edit_url)
    assert r_edit_get.status_code == 200
    assert r_edit_get.context["is_edit"] is True
    assert r_edit_get.context["analysis"] == created

    r_edit_post = client_a.post(
        edit_url,
        data=_assetanalytics_alcc_post(currency=currency_usd, title="Updated Euro Chiller Study"),
    )
    assert r_edit_post.status_code == 302
    created.refresh_from_db()
    assert created.title == "Updated Euro Chiller Study"
    assert _assetanalytics_audit_logs_for(created, action="update").exists()

    # Edit & Delete blocked on locked record
    locked_edit = reverse(
        "assets:asset_lifecycle_cost_analysis_edit", args=[analytics_lcc_locked_a.pk]
    )
    r_locked_get = client_a.get(locked_edit)
    assert r_locked_get.status_code == 302
    assert r_locked_get.url == reverse(
        "assets:asset_lifecycle_cost_analysis_detail", args=[analytics_lcc_locked_a.pk]
    )
    r_locked_post = client_a.post(
        locked_edit, data=_assetanalytics_alcc_post(title="Should Not Update")
    )
    assert r_locked_post.status_code == 302
    analytics_lcc_locked_a.refresh_from_db()
    assert analytics_lcc_locked_a.title != "Should Not Update"

    locked_del = reverse(
        "assets:asset_lifecycle_cost_analysis_delete", args=[analytics_lcc_locked_a.pk]
    )
    r_locked_del = client_a.post(locked_del)
    assert r_locked_del.status_code == 302
    assert AssetLifecycleCostAnalysis.objects.filter(pk=analytics_lcc_locked_a.pk).exists()

    # Delete GET -> 405; POST on unlocked -> deleted + AuditLog
    del_url = reverse("assets:asset_lifecycle_cost_analysis_delete", args=[created.pk])
    assert client_a.get(del_url).status_code == 405
    r_del = client_a.post(del_url)
    assert r_del.status_code == 302
    assert r_del.url == reverse("assets:asset_lifecycle_cost_analysis_list")
    assert not AssetLifecycleCostAnalysis.objects.filter(pk=created.pk).exists()
    assert _assetanalytics_audit_logs_for(created, action="delete").exists()


def test_assetanalytics_alcc_workflows_populate_and_transitions(
    client_a, analytics_lcc_a, analytics_lcc_locked_a
):
    detail_url = reverse("assets:asset_lifecycle_cost_analysis_detail", args=[analytics_lcc_a.pk])
    populate_url = reverse("assets:asset_lifecycle_cost_analysis_populate", args=[analytics_lcc_a.pk])
    trans_url = reverse("assets:asset_lifecycle_cost_analysis_transition", args=[analytics_lcc_a.pk])

    # Populate draft -> calculated
    r_pop = client_a.post(populate_url)
    assert r_pop.status_code == 302
    assert r_pop.url == detail_url
    analytics_lcc_a.refresh_from_db()
    assert analytics_lcc_a.status == "calculated"
    assert _assetanalytics_audit_logs_for(analytics_lcc_a, action="update").filter(
        changes__action="populate"
    ).exists()

    # Locked populate blocked
    r_pop_locked = client_a.post(
        reverse("assets:asset_lifecycle_cost_analysis_populate", args=[analytics_lcc_locked_a.pk])
    )
    assert r_pop_locked.status_code == 302
    assert any("locked" in m.lower() for m in _assetanalytics_messages(r_pop_locked))

    # Valid transitions: draft -> reviewed, and calculated -> approved -> archived
    fresh = _assetanalytics_make_alcc(analytics_lcc_a.tenant, title="Transition Test ALCC")
    fresh_trans = reverse("assets:asset_lifecycle_cost_analysis_transition", args=[fresh.pk])

    # Invalid draft -> approved rejected
    r_bad = client_a.post(fresh_trans, {"target_status": "approved"})
    assert r_bad.status_code == 302
    fresh.refresh_from_db()
    assert fresh.status == "draft"

    # Valid draft -> reviewed -> approved -> archived
    client_a.post(fresh_trans, {"target_status": "reviewed"})
    fresh.refresh_from_db()
    assert fresh.status == "reviewed"

    client_a.post(fresh_trans, {"target_status": "approved"})
    fresh.refresh_from_db()
    assert fresh.status == "approved"

    client_a.post(fresh_trans, {"target_status": "archived"})
    fresh.refresh_from_db()
    assert fresh.status == "archived"

    # Invalid archived -> calculated rejected
    r_arch_bad = client_a.post(fresh_trans, {"target_status": "calculated"})
    assert r_arch_bad.status_code == 302
    fresh.refresh_from_db()
    assert fresh.status == "archived"

    # Invalid choice & same status handled cleanly
    client_a.post(trans_url, {"target_status": "bogus"})
    client_a.post(trans_url, {"target_status": "calculated"})
    analytics_lcc_a.refresh_from_db()
    assert analytics_lcc_a.status == "calculated"


# =====================================================================
# 3. ARPL (AssetReplacementPlan) Views, Filters, Pagination, Workflows, CSV
# =====================================================================


def test_assetanalytics_arpl_list_filters_empty_and_pagination(
    client_a,
    tenant_a,
    analytics_rpl_a,
    analytics_rpl_locked_a,
    analytics_rpl_b,
    category_child_a,
    location_a2,
):
    other_ou = OrgUnit.objects.create(tenant=tenant_a, name="Facility North", kind="department")
    target_yr = timezone.localdate().year + 3
    extra = _assetanalytics_make_arpl(
        tenant_a,
        title="North Chiller Replacement",
        asset_category=category_child_a,
        org_unit=other_ou,
        location=location_a2,
        planned_replacement_year=target_yr,
        replacement_strategy="consolidate_retire",
        funding_status="requested",
        status="proposed",
        condition_score=Decimal("10.00"),
        criticality_weight=10,
        failure_risk_score=Decimal("95.00"),
    )

    url = reverse("assets:asset_replacement_plan_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    html = resp.content.decode()
    _assetanalytics_assert_no_template_leaks(html)
    for key in (
        "plans",
        "page_obj",
        "paginator",
        "is_paginated",
        "status_choices",
        "funding_choices",
        "priority_choices",
        "strategy_choices",
        "years",
        "org_units",
        "categories",
        "locations",
        "total_plans",
        "critical_plans_count",
        "unfunded_plans_value",
        "total_capex_forecast",
    ):
        assert key in resp.context
    assert analytics_rpl_a.number in html
    assert analytics_rpl_a.title in html
    assert analytics_rpl_b.title not in html
    assert analytics_rpl_b not in resp.context["page_obj"].object_list

    # Filter checks
    assert list(client_a.get(url, {"q": extra.number}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"status": "proposed"}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"funding_status": "requested"}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"priority_band": extra.priority_band}).context["page_obj"])
    assert list(client_a.get(url, {"replacement_strategy": "consolidate_retire"}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"planned_replacement_year": target_yr}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"org_unit": other_ou.pk}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"asset_category": category_child_a.pk}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"location": location_a2.pk}).context["page_obj"]) == [extra]

    # Junk params ignored cleanly
    r_junk = client_a.get(
        url,
        {
            "status": "junk",
            "funding_status": "junk",
            "priority_band": "junk",
            "replacement_strategy": "junk",
            "planned_replacement_year": "notayear",
            "org_unit": "abc",
            "asset_category": "0",
            "location": "-5",
        },
    )
    assert r_junk.status_code == 200
    assert r_junk.context["paginator"].count == 3

    # Empty state
    r_empty = client_a.get(url, {"q": "NO_MATCHING_ARPL_XYZ"})
    assert r_empty.status_code == 200
    assert r_empty.context["paginator"].count == 0
    _assetanalytics_assert_no_template_leaks(r_empty.content.decode())

    # Pagination at PAGE_SIZE = 15
    for i in range(14):
        _assetanalytics_make_arpl(tenant_a, title=f"Paginated ARPL {i:02d}")
    r_p1 = client_a.get(url)
    assert r_p1.context["is_paginated"] is True
    assert r_p1.context["paginator"].num_pages == 2
    assert len(r_p1.context["page_obj"]) == PAGE_SIZE
    r_p2 = client_a.get(url, {"page": 2})
    assert r_p2.status_code == 200
    assert len(r_p2.context["page_obj"]) == 2
    assert client_a.get(url, {"page": 999}).status_code == 200


def test_assetanalytics_arpl_crud_and_lock(
    client_a, tenant_a, admin_user, currency_usd, analytics_rpl_locked_a
):
    create_url = reverse("assets:asset_replacement_plan_create")
    r_get = client_a.get(create_url)
    assert r_get.status_code == 200
    assert r_get.context["is_edit"] is False
    assert r_get.context["plan"] is None
    _assetanalytics_assert_no_template_leaks(r_get.content.decode())

    r_post = client_a.post(create_url, data=_assetanalytics_arpl_post(currency=currency_usd))
    assert r_post.status_code == 302
    created = AssetReplacementPlan.objects.get(
        tenant=tenant_a, title="Substation Transformer Replacement"
    )
    assert created.planner == admin_user
    assert _assetanalytics_audit_logs_for(created, action="create").exists()

    # Detail
    r_det = client_a.get(reverse("assets:asset_replacement_plan_detail", args=[created.pk]))
    assert r_det.status_code == 200
    assert r_det.context["plan"] == created
    det_html = r_det.content.decode()
    _assetanalytics_assert_no_template_leaks(det_html)
    assert created.number in det_html
    assert created.title in det_html

    # Edit unlocked
    edit_url = reverse("assets:asset_replacement_plan_edit", args=[created.pk])
    assert client_a.get(edit_url).status_code == 200
    r_edit = client_a.post(
        edit_url,
        data=_assetanalytics_arpl_post(currency=currency_usd, title="Updated Transformer Plan"),
    )
    assert r_edit.status_code == 302
    created.refresh_from_db()
    assert created.title == "Updated Transformer Plan"

    # Locked edit & delete blocked
    assert (
        client_a.get(
            reverse("assets:asset_replacement_plan_edit", args=[analytics_rpl_locked_a.pk])
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_replacement_plan_delete", args=[analytics_rpl_locked_a.pk])
        ).status_code
        == 302
    )
    assert AssetReplacementPlan.objects.filter(pk=analytics_rpl_locked_a.pk).exists()

    # Delete unlocked
    del_url = reverse("assets:asset_replacement_plan_delete", args=[created.pk])
    assert client_a.get(del_url).status_code == 405
    r_del = client_a.post(del_url)
    assert r_del.status_code == 302
    assert not AssetReplacementPlan.objects.filter(pk=created.pk).exists()
    assert _assetanalytics_audit_logs_for(created, action="delete").exists()


def test_assetanalytics_arpl_workflows_recalculate_and_transitions(
    client_a, analytics_rpl_a, analytics_rpl_locked_a
):
    recalc_url = reverse("assets:asset_replacement_plan_recalculate", args=[analytics_rpl_a.pk])
    # Mutate raw input without calling save() recalculate so we verify recalculate action
    AssetReplacementPlan.objects.filter(pk=analytics_rpl_a.pk).update(
        estimated_replacement_cost=Decimal("200000.00"),
        inflation_adjusted_cost=Decimal("0.00"),
    )
    r_recalc = client_a.post(recalc_url)
    assert r_recalc.status_code == 302
    analytics_rpl_a.refresh_from_db()
    assert analytics_rpl_a.inflation_adjusted_cost > Decimal("200000.00")
    assert _assetanalytics_audit_logs_for(analytics_rpl_a, action="update").filter(
        changes__action="recalculate"
    ).exists()

    # Locked recalculate blocked
    r_locked_rec = client_a.post(
        reverse("assets:asset_replacement_plan_recalculate", args=[analytics_rpl_locked_a.pk])
    )
    assert r_locked_rec.status_code == 302
    assert any("locked" in m.lower() for m in _assetanalytics_messages(r_locked_rec))

    # Full transition chain: forecasted -> proposed -> approved -> scheduled -> executed
    trans_url = reverse("assets:asset_replacement_plan_transition", args=[analytics_rpl_a.pk])
    # Invalid forecasted -> executed rejected
    client_a.post(trans_url, {"target_status": "executed"})
    analytics_rpl_a.refresh_from_db()
    assert analytics_rpl_a.status == "forecasted"

    for next_status in ("proposed", "approved", "scheduled", "executed"):
        client_a.post(trans_url, {"target_status": next_status})
        analytics_rpl_a.refresh_from_db()
        assert analytics_rpl_a.status == next_status

    # Terminal executed -> forecasted rejected & locked edit/delete/recalc blocked
    client_a.post(trans_url, {"target_status": "forecasted"})
    analytics_rpl_a.refresh_from_db()
    assert analytics_rpl_a.status == "executed"
    assert (
        client_a.get(
            reverse("assets:asset_replacement_plan_edit", args=[analytics_rpl_a.pk])
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_replacement_plan_delete", args=[analytics_rpl_a.pk])
        ).status_code
        == 302
    )
    assert client_a.post(recalc_url).status_code == 302


# =====================================================================
# 4. AWIF (AssetPortfolioScenario) Views, Filters, Pagination, Workflows, CSV
# =====================================================================


def test_assetanalytics_awif_list_filters_empty_and_pagination(
    client_a,
    tenant_a,
    analytics_scenario_base_a,
    analytics_scenario_a,
    analytics_scenario_locked_a,
    analytics_scenario_b,
    category_child_a,
):
    other_ou = OrgUnit.objects.create(tenant=tenant_a, name="R&D Campus", kind="department")
    target_yr = timezone.localdate().year + 2
    extra = _assetanalytics_make_awif(
        tenant_a,
        name="R&D Green Retrofit Scenario",
        scenario_type="sustainability_retrofit",
        base_fiscal_year=target_yr,
        scope_org_unit=other_ou,
        scope_category=category_child_a,
        status="under_review",
    )

    url = reverse("assets:asset_portfolio_scenario_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    html = resp.content.decode()
    _assetanalytics_assert_no_template_leaks(html)
    for key in (
        "scenarios",
        "page_obj",
        "paginator",
        "is_paginated",
        "status_choices",
        "type_choices",
        "years",
        "org_units",
        "categories",
        "total_scenarios",
        "simulated_count",
        "adopted_count",
        "best_npv",
    ):
        assert key in resp.context
    assert analytics_scenario_a.number in html
    assert analytics_scenario_base_a.name in html
    assert "Accelerated Replacement" in html
    assert escape(analytics_scenario_b.name) not in html
    assert analytics_scenario_b not in resp.context["page_obj"].object_list

    # Filters
    assert list(client_a.get(url, {"q": extra.number}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"status": "under_review"}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"scenario_type": "sustainability_retrofit"}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"base_fiscal_year": target_yr}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"scope_org_unit": other_ou.pk}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"scope_category": category_child_a.pk}).context["page_obj"]) == [extra]

    # Junk params ignored
    r_junk = client_a.get(
        url,
        {
            "status": "junk",
            "scenario_type": "junk",
            "base_fiscal_year": "abc",
            "scope_org_unit": "99999999999",
            "scope_category": "-1",
        },
    )
    assert r_junk.status_code == 200
    assert r_junk.context["paginator"].count == 4

    # Empty state
    r_empty = client_a.get(url, {"q": "NO_MATCHING_AWIF_XYZ"})
    assert r_empty.status_code == 200
    assert r_empty.context["paginator"].count == 0
    _assetanalytics_assert_no_template_leaks(r_empty.content.decode())

    # Pagination at PAGE_SIZE = 15
    for i in range(13):
        _assetanalytics_make_awif(tenant_a, name=f"Paginated Scenario {i:02d}")
    r_p1 = client_a.get(url)
    assert r_p1.context["is_paginated"] is True
    assert r_p1.context["paginator"].num_pages == 2
    assert len(r_p1.context["page_obj"]) == PAGE_SIZE
    r_p2 = client_a.get(url, {"page": 2})
    assert r_p2.status_code == 200
    assert len(r_p2.context["page_obj"]) == 2
    assert client_a.get(url, {"page": 999}).status_code == 200


def test_assetanalytics_awif_crud_and_lock(
    client_a, tenant_a, admin_user, currency_usd, analytics_scenario_locked_a
):
    create_url = reverse("assets:asset_portfolio_scenario_create")
    r_get = client_a.get(create_url)
    assert r_get.status_code == 200
    assert r_get.context["is_edit"] is False
    assert r_get.context["scenario"] is None
    _assetanalytics_assert_no_template_leaks(r_get.content.decode())

    r_post = client_a.post(create_url, data=_assetanalytics_awif_post(currency=currency_usd))
    assert r_post.status_code == 302
    created = AssetPortfolioScenario.objects.get(
        tenant=tenant_a, name="FY2027 Fleet Modernization Scenario"
    )
    assert created.owner == admin_user
    assert _assetanalytics_audit_logs_for(created, action="create").exists()

    # Detail
    r_det = client_a.get(reverse("assets:asset_portfolio_scenario_detail", args=[created.pk]))
    assert r_det.status_code == 200
    assert r_det.context["scenario"] == created
    det_html = r_det.content.decode()
    _assetanalytics_assert_no_template_leaks(det_html)
    assert created.number in det_html
    assert created.name in det_html

    # Edit unlocked
    edit_url = reverse("assets:asset_portfolio_scenario_edit", args=[created.pk])
    assert client_a.get(edit_url).status_code == 200
    r_edit = client_a.post(
        edit_url,
        data=_assetanalytics_awif_post(currency=currency_usd, name="Updated Fleet Modernization"),
    )
    assert r_edit.status_code == 302
    created.refresh_from_db()
    assert created.name == "Updated Fleet Modernization"

    # Locked edit & delete blocked
    assert (
        client_a.get(
            reverse("assets:asset_portfolio_scenario_edit", args=[analytics_scenario_locked_a.pk])
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_portfolio_scenario_delete", args=[analytics_scenario_locked_a.pk])
        ).status_code
        == 302
    )
    assert AssetPortfolioScenario.objects.filter(pk=analytics_scenario_locked_a.pk).exists()

    # Delete unlocked
    del_url = reverse("assets:asset_portfolio_scenario_delete", args=[created.pk])
    assert client_a.get(del_url).status_code == 405
    r_del = client_a.post(del_url)
    assert r_del.status_code == 302
    assert not AssetPortfolioScenario.objects.filter(pk=created.pk).exists()
    assert _assetanalytics_audit_logs_for(created, action="delete").exists()


def test_assetanalytics_awif_workflows_simulate_and_transitions(
    client_a, analytics_scenario_a, analytics_scenario_locked_a
):
    sim_url = reverse("assets:asset_portfolio_scenario_simulate", args=[analytics_scenario_a.pk])
    trans_url = reverse("assets:asset_portfolio_scenario_transition", args=[analytics_scenario_a.pk])

    # Simulate: draft -> simulated
    r_sim = client_a.post(sim_url)
    assert r_sim.status_code == 302
    analytics_scenario_a.refresh_from_db()
    assert analytics_scenario_a.status == "simulated"
    assert _assetanalytics_audit_logs_for(analytics_scenario_a, action="update").filter(
        changes__action="simulate"
    ).exists()

    # Locked simulate blocked
    r_sim_locked = client_a.post(
        reverse("assets:asset_portfolio_scenario_simulate", args=[analytics_scenario_locked_a.pk])
    )
    assert r_sim_locked.status_code == 302
    assert any("locked" in m.lower() for m in _assetanalytics_messages(r_sim_locked))

    # Invalid simulated -> adopted rejected
    client_a.post(trans_url, {"target_status": "adopted"})
    analytics_scenario_a.refresh_from_db()
    assert analytics_scenario_a.status == "simulated"

    # Valid chain: simulated -> under_review -> recommended -> adopted -> archived
    for next_status in ("under_review", "recommended", "adopted", "archived"):
        client_a.post(trans_url, {"target_status": next_status})
        analytics_scenario_a.refresh_from_db()
        assert analytics_scenario_a.status == next_status

    # Invalid archived -> simulated rejected
    client_a.post(trans_url, {"target_status": "simulated"})
    analytics_scenario_a.refresh_from_db()
    assert analytics_scenario_a.status == "archived"

    # Locked edit/delete/simulate blocked on archived
    assert (
        client_a.get(
            reverse("assets:asset_portfolio_scenario_edit", args=[analytics_scenario_a.pk])
        ).status_code
        == 302
    )
    assert (
        client_a.post(
            reverse("assets:asset_portfolio_scenario_delete", args=[analytics_scenario_a.pk])
        ).status_code
        == 302
    )
    assert client_a.post(sim_url).status_code == 302


# =====================================================================
# 5. AKPI (AssetExecutiveScorecard) Views, Filters, Pagination, Workflows, CSV
# =====================================================================


def test_assetanalytics_akpi_list_filters_empty_and_pagination(
    client_a,
    tenant_a,
    analytics_scorecard_a,
    analytics_scorecard_published_a,
    analytics_scorecard_b,
    category_child_a,
):
    other_ou = OrgUnit.objects.create(tenant=tenant_a, name="Corporate HQ", kind="department")
    extra = _assetanalytics_make_akpi(
        tenant_a,
        title="Annual Red Alert Scorecard",
        period_type="annual",
        rag_status="red",
        status="board_approved",
        org_unit=other_ou,
        asset_category=category_child_a,
    )

    url = reverse("assets:asset_executive_scorecard_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    html = resp.content.decode()
    _assetanalytics_assert_no_template_leaks(html)
    for key in (
        "scorecards",
        "page_obj",
        "paginator",
        "is_paginated",
        "status_choices",
        "period_choices",
        "rag_choices",
        "org_units",
        "categories",
        "total_scorecards",
        "green_count",
        "board_approved_count",
        "avg_roi_pct",
    ):
        assert key in resp.context
    assert analytics_scorecard_a.number in html
    assert analytics_scorecard_a.title in html
    assert analytics_scorecard_b.title not in html
    assert analytics_scorecard_b not in resp.context["page_obj"].object_list
    assert resp.context["board_approved_count"] == 1

    # Filters
    assert list(client_a.get(url, {"q": extra.number}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"status": "board_approved"}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"period_type": "annual"}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"rag_status": "red"}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"org_unit": other_ou.pk}).context["page_obj"]) == [extra]
    assert list(client_a.get(url, {"asset_category": category_child_a.pk}).context["page_obj"]) == [extra]

    # Junk params ignored cleanly
    r_junk = client_a.get(
        url,
        {
            "status": "junk",
            "period_type": "junk",
            "rag_status": "junk",
            "org_unit": "abc",
            "asset_category": "99999999999",
        },
    )
    assert r_junk.status_code == 200
    assert r_junk.context["paginator"].count == 3

    # Empty state
    r_empty = client_a.get(url, {"q": "NO_MATCHING_AKPI_XYZ"})
    assert r_empty.status_code == 200
    assert r_empty.context["paginator"].count == 0
    _assetanalytics_assert_no_template_leaks(r_empty.content.decode())

    # Pagination at PAGE_SIZE = 15
    for i in range(14):
        _assetanalytics_make_akpi(tenant_a, title=f"Paginated Scorecard {i:02d}")
    r_p1 = client_a.get(url)
    assert r_p1.context["is_paginated"] is True
    assert r_p1.context["paginator"].num_pages == 2
    assert len(r_p1.context["page_obj"]) == PAGE_SIZE
    r_p2 = client_a.get(url, {"page": 2})
    assert r_p2.status_code == 200
    assert len(r_p2.context["page_obj"]) == 2
    assert client_a.get(url, {"page": 999}).status_code == 200


def test_assetanalytics_akpi_crud_and_is_locked(
    client_a, tenant_a, admin_user, currency_usd, analytics_scorecard_published_a
):
    create_url = reverse("assets:asset_executive_scorecard_create")
    r_get = client_a.get(create_url)
    assert r_get.status_code == 200
    assert r_get.context["is_edit"] is False
    assert r_get.context["scorecard"] is None
    _assetanalytics_assert_no_template_leaks(r_get.content.decode())

    r_post = client_a.post(create_url, data=_assetanalytics_akpi_post(currency=currency_usd))
    assert r_post.status_code == 302
    created = AssetExecutiveScorecard.objects.get(
        tenant=tenant_a, title="Q4 Board Executive Asset Scorecard"
    )
    assert created.prepared_by == admin_user
    assert _assetanalytics_audit_logs_for(created, action="create").exists()

    # Detail
    r_det = client_a.get(reverse("assets:asset_executive_scorecard_detail", args=[created.pk]))
    assert r_det.status_code == 200
    assert r_det.context["scorecard"] == created
    det_html = r_det.content.decode()
    _assetanalytics_assert_no_template_leaks(det_html)
    assert created.number in det_html
    assert created.title in det_html

    # Edit unlocked
    edit_url = reverse("assets:asset_executive_scorecard_edit", args=[created.pk])
    assert client_a.get(edit_url).status_code == 200
    r_edit = client_a.post(
        edit_url,
        data=_assetanalytics_akpi_post(currency=currency_usd, title="Updated Q4 Scorecard"),
    )
    assert r_edit.status_code == 302
    created.refresh_from_db()
    assert created.title == "Updated Q4 Scorecard"

    # AKPI.is_locked blocks edit & delete when published
    assert analytics_scorecard_published_a.is_locked is True
    assert (
        client_a.get(
            reverse(
                "assets:asset_executive_scorecard_edit", args=[analytics_scorecard_published_a.pk]
            )
        ).status_code
        == 302
    )
    r_locked_del = client_a.post(
        reverse(
            "assets:asset_executive_scorecard_delete", args=[analytics_scorecard_published_a.pk]
        )
    )
    assert r_locked_del.status_code == 302
    assert any("locked" in m.lower() for m in _assetanalytics_messages(r_locked_del))
    assert AssetExecutiveScorecard.objects.filter(pk=analytics_scorecard_published_a.pk).exists()

    # Delete unlocked
    del_url = reverse("assets:asset_executive_scorecard_delete", args=[created.pk])
    assert client_a.get(del_url).status_code == 405
    r_del = client_a.post(del_url)
    assert r_del.status_code == 302
    assert not AssetExecutiveScorecard.objects.filter(pk=created.pk).exists()
    assert _assetanalytics_audit_logs_for(created, action="delete").exists()


def test_assetanalytics_akpi_workflows_compute_publish_approve_sod_and_archive(
    client_a,
    admin_user,
    analytics_scorecard_a,
    analytics_scorecard_published_a,
    fixed_asset_a,
):
    # Compute allowed on draft
    r_comp = client_a.post(
        reverse("assets:asset_executive_scorecard_compute", args=[analytics_scorecard_a.pk])
    )
    assert r_comp.status_code == 302
    analytics_scorecard_a.refresh_from_db()
    assert analytics_scorecard_a.total_net_book_value >= Decimal("0.00")
    assert _assetanalytics_audit_logs_for(analytics_scorecard_a, action="update").filter(
        changes__action="compute"
    ).exists()

    # Compute rejected on locked published scorecard
    r_comp_locked = client_a.post(
        reverse(
            "assets:asset_executive_scorecard_compute", args=[analytics_scorecard_published_a.pk]
        )
    )
    assert r_comp_locked.status_code == 302
    assert any("locked" in m.lower() for m in _assetanalytics_messages(r_comp_locked))

    # Publish: draft -> published
    r_pub = client_a.post(
        reverse("assets:asset_executive_scorecard_publish", args=[analytics_scorecard_a.pk])
    )
    assert r_pub.status_code == 302
    analytics_scorecard_a.refresh_from_db()
    assert analytics_scorecard_a.status == "published"

    # Re-publish non-draft rejected
    r_repub = client_a.post(
        reverse("assets:asset_executive_scorecard_publish", args=[analytics_scorecard_a.pk])
    )
    assert r_repub.status_code == 302

    # SoD check on approve: prepared_by == admin_user (request.user) MUST be blocked
    r_sod = client_a.post(
        reverse("assets:asset_executive_scorecard_approve", args=[analytics_scorecard_a.pk])
    )
    assert r_sod.status_code == 302
    analytics_scorecard_a.refresh_from_db()
    assert analytics_scorecard_a.status == "published"
    assert analytics_scorecard_a.approved_by is None
    assert any("segregation" in m.lower() for m in _assetanalytics_messages(r_sod))

    # Approve succeeds when prepared_by != request.user (analytics_scorecard_published_a prepared by member_user)
    r_app = client_a.post(
        reverse(
            "assets:asset_executive_scorecard_approve", args=[analytics_scorecard_published_a.pk]
        )
    )
    assert r_app.status_code == 302
    analytics_scorecard_published_a.refresh_from_db()
    assert analytics_scorecard_published_a.status == "board_approved"
    assert analytics_scorecard_published_a.approved_by == admin_user

    # Approve non-published (e.g. draft) rejected
    draft_sc = _assetanalytics_make_akpi(analytics_scorecard_a.tenant, title="Draft Only")
    r_app_draft = client_a.post(
        reverse("assets:asset_executive_scorecard_approve", args=[draft_sc.pk])
    )
    assert r_app_draft.status_code == 302
    draft_sc.refresh_from_db()
    assert draft_sc.status == "draft"

    # Archive
    r_arch = client_a.post(
        reverse(
            "assets:asset_executive_scorecard_archive", args=[analytics_scorecard_published_a.pk]
        )
    )
    assert r_arch.status_code == 302
    analytics_scorecard_published_a.refresh_from_db()
    assert analytics_scorecard_published_a.status == "archived"

    # Archiving already-archived stays archived gracefully
    r_arch2 = client_a.post(
        reverse(
            "assets:asset_executive_scorecard_archive", args=[analytics_scorecard_published_a.pk]
        )
    )
    assert r_arch2.status_code == 302


# =====================================================================
# 6. CSV Exports (all 5 endpoints + formula-injection neutralization)
# =====================================================================


def test_assetanalytics_csv_exports_and_formula_neutralization(
    client_a,
    tenant_a,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scenario_a,
    analytics_scorecard_a,
):
    # Seed formula-injection payloads in each entity + bad actor for dashboard
    _assetanalytics_make_alcc(
        tenant_a,
        title="=CMD('calc')",
        preventive_maintenance_cost=Decimal("50000.00"),
        current_replacement_value=Decimal("10000.00"),
    )
    _assetanalytics_make_arpl(tenant_a, title="+1+1 Payload")
    _assetanalytics_make_awif(tenant_a, name="-100 Payload")
    _assetanalytics_make_akpi(tenant_a, title="@SUM(A1) Payload")

    alcc_rows = _assetanalytics_parse_csv_response(
        client_a.get(reverse("assets:asset_lifecycle_cost_analysis_export_csv"))
    )
    assert any("'=CMD('calc')" in row for row in alcc_rows[1:])

    arpl_rows = _assetanalytics_parse_csv_response(
        client_a.get(reverse("assets:asset_replacement_plan_export_csv"))
    )
    assert any("'+1+1 Payload" in row for row in arpl_rows[1:])

    awif_rows = _assetanalytics_parse_csv_response(
        client_a.get(reverse("assets:asset_portfolio_scenario_export_csv"))
    )
    assert any("'-100 Payload" in row for row in awif_rows[1:])

    akpi_rows = _assetanalytics_parse_csv_response(
        client_a.get(reverse("assets:asset_executive_scorecard_export_csv"))
    )
    assert any("'@SUM(A1) Payload" in row for row in akpi_rows[1:])

    dash_rows = _assetanalytics_parse_csv_response(
        client_a.get(reverse("assets:portfolio_dashboard_export_csv"))
    )
    assert dash_rows[0] == ["Section", "Item / Year", "Metric 1", "Metric 2", "Metric 3", "Metric 4"]
    assert any("Top TCO Bad Actor" == row[0] for row in dash_rows[1:])
    assert any("5-Yr CapEx Forecast" == row[0] for row in dash_rows[1:])


# =====================================================================
# 7. Computed PortfolioDashboards (portfolio_dashboard & scenario_compare)
# =====================================================================


def test_assetanalytics_portfolio_dashboard_filters_c2_m2_and_fiscal_year(
    client_a,
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    category_child_a,
    org_unit_a,
    location_a,
    location_a2,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scorecard_a,
):
    # Link operational_asset_a -> fixed_asset_a & org_unit_a so C2 FixedAsset PK lookup works
    operational_asset_a.fixed_asset = fixed_asset_a
    operational_asset_a.org_unit = org_unit_a
    operational_asset_a.save(update_fields=["fixed_asset", "org_unit"])

    # Second org unit & asset at location_a2 to verify location / org_unit / category scoping
    other_ou = OrgUnit.objects.create(tenant=tenant_a, name="Auxiliary Warehouse", kind="department")
    fa2 = FixedAsset.objects.create(
        tenant=tenant_a,
        name="Secondary Pump FA",
        category="Machinery",
        acquisition_cost=Decimal("40000.00"),
        salvage_value=Decimal("4000.00"),
        useful_life_months=60,
        method="straight_line",
        status="active",
        in_service_date=timezone.localdate() - timedelta(days=30),
    )
    op2 = Asset.objects.create(
        tenant=tenant_a,
        code="AST-ACME-02",
        name="Secondary Pump",
        asset_type="machinery",
        location=location_a2,
        org_unit=other_ou,
        fixed_asset=fa2,
    )
    alcc_loc2 = _assetanalytics_make_alcc(
        tenant_a,
        title="Bay 2 Secondary Pump TCO",
        fixed_asset=fa2,
        operational_asset=op2,
        asset_category=category_child_a,
        org_unit=other_ou,
        acquisition_capital_cost=Decimal("30000.00"),
    )

    url = reverse("assets:portfolio_dashboard")
    r_base = client_a.get(url)
    assert r_base.status_code == 200
    _assetanalytics_assert_no_template_leaks(r_base.content.decode())
    for key in (
        "org_units",
        "categories",
        "locations",
        "fiscal_years",
        "selected_fiscal_year",
        "kpis",
        "health_matrix",
        "bad_actors",
        "capex_forecast_years",
        "risk_posture_rows",
        "compliance_summary",
        "recent_scorecards",
    ):
        assert key in r_base.context

    # ?location=<location_a.pk> resolves FixedAsset PK via scm_qs (C2) & filters alcc_qs (M2)
    r_loc1 = client_a.get(url, {"location": location_a.pk})
    assert r_loc1.status_code == 200
    assert r_loc1.context["kpis"]["total_acquisition_value"] == fixed_asset_a.acquisition_cost
    assert analytics_lcc_a in r_loc1.context["bad_actors"]
    assert alcc_loc2 not in r_loc1.context["bad_actors"]

    r_loc2 = client_a.get(url, {"location": location_a2.pk})
    assert r_loc2.status_code == 200
    assert r_loc2.context["kpis"]["total_acquisition_value"] == fa2.acquisition_cost
    assert r_loc2.context["bad_actors"] == [alcc_loc2]

    # ?org_unit= filter
    r_ou = client_a.get(url, {"org_unit": other_ou.pk})
    assert r_ou.status_code == 200
    assert r_ou.context["bad_actors"] == [alcc_loc2]

    # ?asset_category= filter
    r_cat = client_a.get(url, {"asset_category": category_child_a.pk})
    assert r_cat.status_code == 200
    assert r_cat.context["bad_actors"] == [alcc_loc2]

    # ?fiscal_year= bounded 2000..2100 + out-of-range/junk fallback
    r_fy = client_a.get(url, {"fiscal_year": 2030})
    assert r_fy.status_code == 200
    assert r_fy.context["selected_fiscal_year"] == 2030
    assert [row["year"] for row in r_fy.context["capex_forecast_years"]] == [
        2030,
        2031,
        2032,
        2033,
        2034,
    ]

    cur_year = timezone.localdate().year
    for bad_fy in ("1999", "2101", "99999999999", "notayear"):
        r_bad_fy = client_a.get(
            url,
            {
                "fiscal_year": bad_fy,
                "org_unit": "junk",
                "asset_category": "0",
                "location": "-5",
            },
        )
        assert r_bad_fy.status_code == 200
        assert r_bad_fy.context["selected_fiscal_year"] == cur_year


def test_assetanalytics_scenario_compare_selection_and_404(
    client_a,
    tenant_a,
    analytics_scenario_base_a,
    analytics_scenario_a,
    analytics_scenario_locked_a,
    analytics_scenario_b,
):
    url = reverse("assets:scenario_compare")

    # Default: top 4 tenant scenarios, excludes tenant B
    r_default = client_a.get(url)
    assert r_default.status_code == 200
    html = r_default.content.decode()
    _assetanalytics_assert_no_template_leaks(html)
    for key in ("all_scenarios", "compared_scenarios", "selected_ids", "baseline_scenario"):
        assert key in r_default.context
    assert analytics_scenario_b not in r_default.context["all_scenarios"]
    assert r_default.context["baseline_scenario"] == analytics_scenario_base_a
    assert len(r_default.context["compared_scenarios"]) == 3

    # Explicit multi-select preserves order
    r_sel = client_a.get(
        url,
        {"scenarios": [str(analytics_scenario_a.pk), str(analytics_scenario_base_a.pk)]},
    )
    assert r_sel.status_code == 200
    assert r_sel.context["compared_scenarios"] == [
        analytics_scenario_a,
        analytics_scenario_base_a,
    ]

    # Junk non-numeric scenarios param returns empty comparison (no 500)
    r_junk = client_a.get(url, {"scenarios": "notanint"})
    assert r_junk.status_code == 200
    assert r_junk.context["compared_scenarios"] == []

    # Valid int(s) with 0 tenant matches (non-existent or foreign tenant) -> 404
    assert client_a.get(url, {"scenarios": "999999"}).status_code == 404
    assert client_a.get(url, {"scenarios": str(analytics_scenario_b.pk)}).status_code == 404


# =====================================================================
# 8. Query-Count Ceiling Checks (django_assert_max_num_queries)
# =====================================================================


def test_assetanalytics_list_views_constant_queries_and_budget(
    client_a,
    tenant_a,
    category_root_a,
    org_unit_a,
    location_a,
    currency_usd,
    admin_user,
    django_assert_max_num_queries,
):
    # Seed 1 record of each
    _assetanalytics_make_alcc(
        tenant_a,
        title="Budget ALCC 0",
        asset_category=category_root_a,
        org_unit=org_unit_a,
        currency=currency_usd,
        analyzed_by=admin_user,
    )
    _assetanalytics_make_arpl(
        tenant_a,
        title="Budget ARPL 0",
        asset_category=category_root_a,
        org_unit=org_unit_a,
        location=location_a,
        currency=currency_usd,
        planner=admin_user,
    )
    _assetanalytics_make_awif(
        tenant_a,
        name="Budget AWIF 0",
        scope_org_unit=org_unit_a,
        scope_category=category_root_a,
        currency=currency_usd,
        owner=admin_user,
    )
    _assetanalytics_make_akpi(
        tenant_a,
        title="Budget AKPI 0",
        org_unit=org_unit_a,
        asset_category=category_root_a,
        currency=currency_usd,
        prepared_by=admin_user,
    )

    list_urls = [
        reverse("assets:asset_lifecycle_cost_analysis_list"),
        reverse("assets:asset_replacement_plan_list"),
        reverse("assets:asset_portfolio_scenario_list"),
        reverse("assets:asset_executive_scorecard_list"),
    ]
    # Warm session/auth
    client_a.get(list_urls[0])

    small_counts = {}
    for u in list_urls:
        with CaptureQueriesContext(connection) as ctx:
            with django_assert_max_num_queries(16):
                r = client_a.get(u)
                assert r.status_code == 200
        small_counts[u] = len(ctx)

    # Scale to 12+ rows per entity — query count must stay flat (O(1))
    for i in range(1, 13):
        _assetanalytics_make_alcc(
            tenant_a,
            title=f"Budget ALCC {i}",
            asset_category=category_root_a,
            org_unit=org_unit_a,
            currency=currency_usd,
            analyzed_by=admin_user,
        )
        _assetanalytics_make_arpl(
            tenant_a,
            title=f"Budget ARPL {i}",
            asset_category=category_root_a,
            org_unit=org_unit_a,
            location=location_a,
            currency=currency_usd,
            planner=admin_user,
        )
        _assetanalytics_make_awif(
            tenant_a,
            name=f"Budget AWIF {i}",
            scope_org_unit=org_unit_a,
            scope_category=category_root_a,
            currency=currency_usd,
            owner=admin_user,
        )
        _assetanalytics_make_akpi(
            tenant_a,
            title=f"Budget AKPI {i}",
            org_unit=org_unit_a,
            asset_category=category_root_a,
            currency=currency_usd,
            prepared_by=admin_user,
        )

    for u in list_urls:
        with CaptureQueriesContext(connection) as ctx:
            with django_assert_max_num_queries(16):
                r = client_a.get(u)
                assert r.status_code == 200
        assert len(ctx) == small_counts[u]


def test_assetanalytics_portfolio_dashboard_query_budget(
    client_a,
    tenant_a,
    fixed_asset_a,
    operational_asset_a,
    category_root_a,
    org_unit_a,
    location_a,
    analytics_lcc_a,
    analytics_rpl_a,
    analytics_scorecard_a,
    django_assert_max_num_queries,
):
    dash_url = reverse("assets:portfolio_dashboard")
    # Warm session/auth
    client_a.get(dash_url)

    with django_assert_max_num_queries(25):
        resp = client_a.get(dash_url)
        assert resp.status_code == 200


# =====================================================================
# 9. Live Sidebar Navigation Check (LIVE_LINKS["11.14"])
# =====================================================================


def test_assetanalytics_live_links_navigation_11_14(client_a):
    links_11_14 = LIVE_LINKS.get("11.14", {})
    assert len(links_11_14) >= 5
    for label, route in links_11_14.items():
        path = reverse(route)
        resp = client_a.get(path)
        assert resp.status_code == 200, f"LIVE_LINKS['11.14'][{label!r}] -> {route} failed"
        _assetanalytics_assert_no_template_leaks(resp.content.decode())
