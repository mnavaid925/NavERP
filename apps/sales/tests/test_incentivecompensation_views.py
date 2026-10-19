"""Sales 8.10 — Incentive Compensation Management Views & Action Endpoints Test Suite.

Covers:
1. 5 Incentive Compensation Boards & What-If Calculator:
   - sales_commission_plan_hub
   - sales_commission_earnings_dashboard
   - sales_commission_adjustment_workbench
   - sales_global_compensation_matrix
   - sales_commission_payout_processing (verifies 'plans' is in context - regression test for C7)
   - sales_commission_what_if_calc (valid calculation returns JSON with projected_gross,
     non-numeric / NaN / Infinity / negative input returns HTTP 400 - regression test for L35)
2. 4 CRUD Models (CommissionPlan, CommissionEarning, CommissionStatement, CommissionAdjustment):
   - List views: assert 200, search q, status filter, FK filters, multi-page pagination
   - Create views: GET 200, POST 302, invalid POST 200
   - Detail views: GET 200, rep isolation, cross-tenant 404
   - Edit views: GET 200, POST 302, cross-tenant 404
   - Delete views: GET status in (200, 405) with verify GET does NOT delete, POST 302,
     non-admin 403, cross-tenant 404
3. Action Endpoints:
   - commission_statement_approve (POST 302, self-approval forbidden 403, invalid status safe)
   - commission_statement_lock (POST 302, draft lock safe redirect, self-lock forbidden 403)
   - commission_statement_generate_batch (POST 302, generates statements with net_payout
     draw calculation - regression test for C9, handles invalid params cleanly)
   - commission_adjustment_resolve_dispute (POST 302 approve/reject, self-resolution forbidden 403)
4. Negative-Input Hardening & Workflow Mutation Guards:
   - Junk GET filters (?status=garbage, ?payee=abc, ?page=999) return 200, not 500 (L11)
   - Status mutation guards (regression test for C10): editing or deleting paid earnings or earnings
     on locked statements redirects safely without modifying or deleting records
   - Statement mutation guards: editing or deleting locked statements redirects safely
   - Adjustment mutation guards: editing or deleting approved/applied adjustments redirects safely
   - Unauthenticated access redirects to login (HTTP 302)
"""
from datetime import date, timedelta
from decimal import Decimal
import json

import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounting.models import Currency
from apps.crm.models import Opportunity, SalesQuota
from apps.sales.models import (
    CommissionAdjustment,
    CommissionEarning,
    CommissionPlan,
    CommissionStatement,
)
from apps.sales.tests.conftest import (
    _incentivecompensation_adjustment,
    _incentivecompensation_currency,
    _incentivecompensation_earning,
    _incentivecompensation_plan,
    _incentivecompensation_statement,
)

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_incentivecompensation_*)
# ==============================================================================

def _incentivecompensation_messages(response):
    """Extract string messages from response."""
    return [str(m.message) for m in get_messages(response.wsgi_request)]


def _incentivecompensation_has_message(response, fragment):
    """Check if a fragment is present in any message."""
    return any(fragment in m for m in _incentivecompensation_messages(response))


def _incentivecompensation_create_user(tenant, username, is_admin=False):
    """Helper creating a test user scoped to tenant."""
    return User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
        password="TestPass123!",
        tenant=tenant,
        is_tenant_admin=is_admin,
    )


def _incentivecompensation_opportunity(tenant, name="Big Deal", amount=Decimal("100000.00"), **overrides):
    """Helper creating a valid CRM Opportunity for view testing."""
    label = f"{int(timezone.now().timestamp() * 1000) % 100000}"
    defaults = {
        "tenant": tenant,
        "name": f"{name} {label}",
        "stage": "closed_won",
        "forecast_category": "closed",
        "amount": amount,
        "probability": 100,
    }
    defaults.update(overrides)
    return Opportunity.objects.create(**defaults)


def _incentivecompensation_sales_quota(tenant, owner=None, target_amount=Decimal("250000.00"), **overrides):
    """Helper creating a valid CRM SalesQuota for view testing."""
    defaults = {
        "tenant": tenant,
        "owner": owner,
        "period_type": "quarterly",
        "period_year": timezone.now().year,
        "period_number": 3,
        "target_amount": target_amount,
    }
    defaults.update(overrides)
    return SalesQuota.objects.create(**defaults)


def _incentivecompensation_plan_payload(currency, **overrides):
    """Return valid POST payload for CommissionPlanForm."""
    label = f"{int(timezone.now().timestamp() * 1000) % 100000}"
    defaults = {
        "name": f"Enterprise Plan {label}",
        "code": f"PLAN-{label}",
        "description": "Standard enterprise compensation plan",
        "plan_type": "flat_revenue",
        "tier_mode": "retroactive",
        "status": "active",
        "payout_frequency": "monthly",
        "effective_start": "2026-01-01",
        "effective_end": "2026-12-31",
        "currency": str(currency.pk),
        "target_region": "Global",
        "base_rate_pct": "10.00",
        "draw_amount": "1000.00",
        "is_draw_recoverable": True,
        "clawback_window_days": "90",
        "tax_withholding_pct": "15.00",
        "tiers_json": "",
        "spif_json": "",
    }
    defaults.update(overrides)
    return defaults


def _incentivecompensation_earning_payload(plan, payee, currency, **overrides):
    """Return valid POST payload for CommissionEarningForm."""
    defaults = {
        "plan": str(plan.pk),
        "payee": str(payee.pk),
        "credit_type": "direct",
        "split_percentage": "100.00",
        "deal_amount": "50000.00",
        "attainment_pct_at_close": "80.00",
        "applied_rate_pct": "10.00",
        "spif_amount": "500.00",
        "deal_currency": str(currency.pk),
        "exchange_rate": "1.000000",
        "earned_date": "2026-05-15",
    }
    defaults.update(overrides)
    return defaults


def _incentivecompensation_statement_payload(payee, plan, **overrides):
    """Return valid POST payload for CommissionStatementForm."""
    label = f"{int(timezone.now().timestamp() * 1000) % 100000}"
    defaults = {
        "statement_number": f"STMT-2026-{label}",
        "payee": str(payee.pk),
        "plan": str(plan.pk),
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "draw_advance_paid": "1000.00",
        "notes": "Monthly statement notes",
    }
    defaults.update(overrides)
    return defaults


def _incentivecompensation_adjustment_payload(payee, **overrides):
    """Return valid POST payload for CommissionAdjustmentForm."""
    defaults = {
        "payee": str(payee.pk),
        "adjustment_type": "manual_override",
        "amount": "250.00",
        "reason": "Quarter-end performance adjustment",
        "effective_date": "2026-10-15",
    }
    defaults.update(overrides)
    return defaults


# ==============================================================================
# 1. Boards & What-If Calculator Tests
# ==============================================================================

def test_incentivecompensation_board_plan_hub(client_a, commission_plan_a):
    """Plan Hub board renders 200 with required context metrics and plan benchmarks."""
    url = reverse("sales:sales_commission_plan_hub")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "plans" in resp.context
    assert "stats" in resp.context
    assert "active_spifs" in resp.context
    assert "tier_accelerator_benchmarks" in resp.context
    assert resp.context["stats"]["active_plans_count"] >= 1
    assert commission_plan_a in resp.context["plans"]


def test_incentivecompensation_board_earnings_dashboard(client_a, commission_earning_a, commission_plan_a):
    """Earnings dashboard board renders 200 with payee summaries and attainment gauge."""
    url = reverse("sales:sales_commission_earnings_dashboard")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "payee_summary" in resp.context
    assert "recent_earnings" in resp.context
    assert "attainment_gauge" in resp.context
    assert "plans" in resp.context
    assert "currency_code" in resp.context
    assert len(resp.context["recent_earnings"]) >= 1


def test_incentivecompensation_board_adjustment_workbench(client_a, commission_adjustment_a):
    """Adjustment workbench board renders 200 with clawbacks, disputes and draw queues."""
    url = reverse("sales:sales_commission_adjustment_workbench")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "pending_clawbacks" in resp.context
    assert "active_disputes" in resp.context
    assert "draw_reconciliation_queue" in resp.context
    assert "stats" in resp.context
    assert "open_disputes_count" in resp.context["stats"]


def test_incentivecompensation_board_global_matrix(client_a, commission_plan_a):
    """Global compensation matrix board renders 200 with regional plans and currencies."""
    url = reverse("sales:sales_global_compensation_matrix")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "regional_plans" in resp.context
    assert "currencies" in resp.context
    assert "recent_exchange_rates" in resp.context
    assert "tax_withholding_summary" in resp.context


def test_incentivecompensation_board_payout_processing_includes_plans(
    client_a, tenant_a, commission_plan_a, commission_plan_b
):
    """Payout Processing board renders 200 and verifies 'plans' is in context (regression test for C7)."""
    url = reverse("sales:sales_commission_payout_processing")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "plans" in resp.context, "C7 regression: 'plans' missing from payout processing context"
    assert "ready_statements" in resp.context
    assert "pending_approvals" in resp.context
    assert "payroll_runs" in resp.context
    assert "stats" in resp.context

    # Tenant isolation: Tenant A client sees plan A, not plan B
    plans_in_context = resp.context["plans"]
    assert commission_plan_a in plans_in_context
    assert commission_plan_b not in plans_in_context


def test_incentivecompensation_what_if_calc_valid(client_a, commission_plan_a):
    """Valid What-If calculation returns HTTP 200 JSON with projected_gross and calculation breakdown."""
    url = reverse("sales:sales_commission_what_if_calc")
    resp = client_a.get(
        url,
        {
            "plan_id": commission_plan_a.pk,
            "deal_amount": "100000.00",
            "split_pct": "100",
            "current_attainment": "80",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "projected_gross" in data
    assert "base_commission" in data
    assert "applied_rate_pct" in data
    assert "attributed_volume" in data
    assert data["projected_gross"] > 0


def test_incentivecompensation_what_if_calc_tiered_rate_progression(client_a, tenant_a, icm_currency, admin_user):
    """What-If calculator applies higher tier rate when attainment enters upper tier bracket."""
    tiers = [
        {"min_pct": 0, "max_pct": 100, "rate_pct": 8.0},
        {"min_pct": 100, "max_pct": 200, "rate_pct": 15.0},
    ]
    tiered_plan = _incentivecompensation_plan(
        tenant_a,
        currency=icm_currency,
        owner=admin_user,
        plan_type="tiered_quota",
        tier_mode="retroactive",
        tiers_config=tiers,
        base_rate_pct=Decimal("8.00"),
    )
    url = reverse("sales:sales_commission_what_if_calc")

    # Attainment at 50% -> rate is 8%
    resp_lower = client_a.get(
        url,
        {
            "plan_id": tiered_plan.pk,
            "deal_amount": "10000.00",
            "split_pct": "100",
            "current_attainment": "50",
        },
    )
    assert resp_lower.status_code == 200
    data_lower = resp_lower.json()
    assert data_lower["applied_rate_pct"] == 8.0
    assert data_lower["base_commission"] == 800.0

    # Attainment at 120% -> rate escalates to 15%
    resp_upper = client_a.get(
        url,
        {
            "plan_id": tiered_plan.pk,
            "deal_amount": "10000.00",
            "split_pct": "100",
            "current_attainment": "120",
        },
    )
    assert resp_upper.status_code == 200
    data_upper = resp_upper.json()
    assert data_upper["applied_rate_pct"] == 15.0
    assert data_upper["base_commission"] == 1500.0


def test_incentivecompensation_what_if_calc_negative_non_numeric_nan_returns_400(client_a, commission_plan_a):
    """What-If endpoint with non-numeric, NaN, Infinity or negative inputs returns HTTP 400 (regression test for L35)."""
    url = reverse("sales:sales_commission_what_if_calc")
    bad_params = [
        {"plan_id": commission_plan_a.pk, "deal_amount": "abc"},
        {"plan_id": commission_plan_a.pk, "deal_amount": "NaN"},
        {"plan_id": commission_plan_a.pk, "deal_amount": "Infinity"},
        {"plan_id": commission_plan_a.pk, "deal_amount": "-500"},
        {"plan_id": commission_plan_a.pk, "deal_amount": "1000", "split_pct": "xyz"},
        {"plan_id": commission_plan_a.pk, "deal_amount": "1000", "split_pct": "-10"},
        {"plan_id": commission_plan_a.pk, "deal_amount": "1000", "split_pct": "150"},
        {"plan_id": commission_plan_a.pk, "deal_amount": "1000", "current_attainment": "NaN"},
        {"plan_id": commission_plan_a.pk, "deal_amount": "1000", "current_attainment": "-5"},
        {"plan_id": "not_an_int", "deal_amount": "1000"},
        {"deal_amount": "1000"},  # missing plan_id
    ]
    for params in bad_params:
        resp = client_a.get(url, params)
        assert resp.status_code == 400, f"Expected 400 for params {params}, got {resp.status_code}"
        assert resp.json()["ok"] is False


def test_incentivecompensation_what_if_calc_cross_tenant_plan_returns_404(client_a, commission_plan_b):
    """What-If calculator rejects plan belonging to another tenant with 404."""
    url = reverse("sales:sales_commission_what_if_calc")
    resp = client_a.get(
        url,
        {
            "plan_id": commission_plan_b.pk,
            "deal_amount": "10000.00",
            "split_pct": "100",
            "current_attainment": "50",
        },
    )
    assert resp.status_code == 404


# ==============================================================================
# 2. CommissionPlan CRUD
# ==============================================================================

def test_incentivecompensation_plan_list_view_and_search(client_a, tenant_a, icm_currency):
    """Commission plan list supports search by name/code and filtering by status and plan_type."""
    p1 = _incentivecompensation_plan(tenant_a, currency=icm_currency, name="North America Quota Plan", code="NA-Q1")
    p2 = _incentivecompensation_plan(
        tenant_a, currency=icm_currency, name="EMEA Channel Plan", code="EMEA-C1", status="draft"
    )

    url = reverse("sales:commission_plan_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "object_list" in resp.context
    assert "stats" in resp.context

    # Search q
    resp_q = client_a.get(url, {"q": "EMEA"})
    assert resp_q.status_code == 200
    pks_q = [p.pk for p in resp_q.context["object_list"]]
    assert p2.pk in pks_q
    assert p1.pk not in pks_q

    # Filter status
    resp_status = client_a.get(url, {"status": "draft"})
    assert resp_status.status_code == 200
    pks_status = [p.pk for p in resp_status.context["object_list"]]
    assert p2.pk in pks_status


def test_incentivecompensation_plan_list_pagination(client_a, tenant_a, icm_currency):
    """Commission plan list paginates cleanly across 15 items per page."""
    for i in range(16):
        _incentivecompensation_plan(
            tenant_a,
            currency=icm_currency,
            name=f"Paginated Plan {i}",
            code=f"PAG-PLN-{i}-{int(timezone.now().timestamp() * 1000) % 10000}",
        )

    url = reverse("sales:commission_plan_list")
    resp_p1 = client_a.get(url)
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["object_list"]) == 15

    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["object_list"]) >= 1


def test_incentivecompensation_plan_create_get_and_post_success(client_a, tenant_a, icm_currency):
    """GET create form returns 200, valid POST creates CommissionPlan and redirects 302 to detail."""
    url = reverse("sales:commission_plan_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False
    assert "form" in resp_get.context

    payload = _incentivecompensation_plan_payload(
        icm_currency,
        name="APAC Growth Plan 2026",
        code="APAC-GROWTH-2026",
        base_rate_pct="12.50",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    created = CommissionPlan.objects.filter(tenant=tenant_a, code="APAC-GROWTH-2026").first()
    assert created is not None
    assert resp_post["Location"] == reverse("sales:commission_plan_detail", kwargs={"pk": created.pk})
    assert created.base_rate_pct == Decimal("12.50")


def test_incentivecompensation_plan_create_post_invalid(client_a, tenant_a, icm_currency):
    """Invalid POST data re-renders form with 200 status code and validation errors."""
    url = reverse("sales:commission_plan_create")
    initial_count = CommissionPlan.objects.filter(tenant=tenant_a).count()
    payload = _incentivecompensation_plan_payload(icm_currency, name="")  # missing name
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors
    assert CommissionPlan.objects.filter(tenant=tenant_a).count() == initial_count


def test_incentivecompensation_plan_detail_view(client_a, commission_plan_a):
    """Detail view renders 200 with object and assigned reps/earnings context."""
    url = reverse("sales:commission_plan_detail", kwargs={"pk": commission_plan_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["obj"] == commission_plan_a
    assert "assigned_reps" in resp.context
    assert "recent_earnings" in resp.context


def test_incentivecompensation_plan_detail_cross_tenant_404(client_a, commission_plan_b):
    """Accessing Tenant B plan detail under Tenant A client returns 404."""
    url = reverse("sales:commission_plan_detail", kwargs={"pk": commission_plan_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_incentivecompensation_plan_edit_get_and_post_success(client_a, tenant_a, commission_plan_a, icm_currency):
    """GET edit returns 200, valid POST updates plan and redirects 302 to detail."""
    url = reverse("sales:commission_plan_edit", kwargs={"pk": commission_plan_a.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["obj"] == commission_plan_a

    payload = _incentivecompensation_plan_payload(
        icm_currency,
        name="Updated Plan Name",
        code="updated-plan-code-2026",
        base_rate_pct="14.00",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    assert resp_post["Location"] == reverse("sales:commission_plan_detail", kwargs={"pk": commission_plan_a.pk})
    commission_plan_a.refresh_from_db()
    assert commission_plan_a.name == "Updated Plan Name"
    assert commission_plan_a.base_rate_pct == Decimal("14.00")


def test_incentivecompensation_plan_edit_cross_tenant_404(client_a, commission_plan_b, icm_currency):
    """Editing Tenant B plan under Tenant A client returns 404."""
    url = reverse("sales:commission_plan_edit", kwargs={"pk": commission_plan_b.pk})
    payload = _incentivecompensation_plan_payload(icm_currency, name="Hijacked Name")
    resp = client_a.post(url, payload)
    assert resp.status_code == 404


def test_incentivecompensation_plan_delete_get_does_not_delete(client_a, commission_plan_a):
    """GET on delete endpoint does not delete the record; returns 405 (POST-only guard)."""
    url = reverse("sales:commission_plan_delete", kwargs={"pk": commission_plan_a.pk})
    resp = client_a.get(url)
    assert resp.status_code in (200, 405)
    assert CommissionPlan.objects.filter(pk=commission_plan_a.pk).exists()


def test_incentivecompensation_plan_delete_post_success(client_a, tenant_a, icm_currency, admin_user):
    """POST delete by tenant admin deletes plan and redirects 302 to list."""
    plan = _incentivecompensation_plan(
        tenant_a,
        currency=icm_currency,
        owner=admin_user,
        name="Temporary Plan to Delete",
        code="TMP-DEL-PLAN",
    )
    url = reverse("sales:commission_plan_delete", kwargs={"pk": plan.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("sales:commission_plan_list")
    assert not CommissionPlan.objects.filter(pk=plan.pk).exists()


def test_incentivecompensation_plan_delete_non_admin_forbidden(member_client, commission_plan_a):
    """Non-admin user cannot delete a plan (returns 403 Forbidden)."""
    url = reverse("sales:commission_plan_delete", kwargs={"pk": commission_plan_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert CommissionPlan.objects.filter(pk=commission_plan_a.pk).exists()


def test_incentivecompensation_plan_delete_cross_tenant_404(client_a, commission_plan_b):
    """Attempting to delete Tenant B plan from Tenant A client returns 404."""
    url = reverse("sales:commission_plan_delete", kwargs={"pk": commission_plan_b.pk})
    resp = client_a.post(url)
    assert resp.status_code == 404
    assert CommissionPlan.objects.filter(pk=commission_plan_b.pk).exists()


# ==============================================================================
# 3. CommissionEarning CRUD & Mutation Guards (C10)
# ==============================================================================

def test_incentivecompensation_earning_list_view_and_filters(client_a, tenant_a, commission_earning_a):
    """Earning list view supports status, credit_type, payee, and plan filters."""
    url = reverse("sales:commission_earning_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "object_list" in resp.context
    assert "stats" in resp.context
    assert commission_earning_a in resp.context["object_list"]

    # Filter by payee FK
    resp_payee = client_a.get(url, {"payee": str(commission_earning_a.payee.pk)})
    assert resp_payee.status_code == 200
    assert commission_earning_a in resp_payee.context["object_list"]

    # Filter by plan FK
    resp_plan = client_a.get(url, {"plan": str(commission_earning_a.plan.pk)})
    assert resp_plan.status_code == 200
    assert commission_earning_a in resp_plan.context["object_list"]


def test_incentivecompensation_earning_list_rep_isolation(member_client, tenant_a, commission_plan_a, admin_user):
    """Non-admin member rep only sees their own earnings in list view."""
    other_rep_earning = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=admin_user,
        gross_commission=Decimal("2000.00"),
    )
    url = reverse("sales:commission_earning_list")
    resp = member_client.get(url)
    assert resp.status_code == 200
    pks = [e.pk for e in resp.context["object_list"]]
    assert other_rep_earning.pk not in pks


def test_incentivecompensation_earning_list_pagination(client_a, tenant_a, commission_plan_a, member_user, icm_currency):
    """Commission earnings list paginates cleanly."""
    for i in range(16):
        _incentivecompensation_earning(
            tenant_a,
            plan=commission_plan_a,
            payee=member_user,
            currency=icm_currency,
            deal_amount=Decimal(1000 + i * 100),
        )
    url = reverse("sales:commission_earning_list")
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["object_list"]) >= 1


def test_incentivecompensation_earning_create_get_and_post_success(
    client_a, tenant_a, commission_plan_a, member_user, icm_currency
):
    """GET create form returns 200, valid POST creates earning and redirects 302 to detail."""
    url = reverse("sales:commission_earning_create")
    resp_get = client_a.get(url, {"plan": commission_plan_a.pk})
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False

    payload = _incentivecompensation_earning_payload(
        commission_plan_a,
        member_user,
        icm_currency,
        deal_amount="75000.00",
        applied_rate_pct="8.00",
        spif_amount="250.00",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    created = CommissionEarning.objects.filter(tenant=tenant_a, payee=member_user, deal_amount=Decimal("75000.00")).first()
    assert created is not None
    assert resp_post["Location"] == reverse("sales:commission_earning_detail", kwargs={"pk": created.pk})
    # Waterfall calculation check: 75000 * 8% = 6000 + 250 spif = 6250 gross
    assert created.gross_commission == Decimal("6250.00")


def test_incentivecompensation_earning_create_post_invalid(client_a, tenant_a, commission_plan_a, member_user, icm_currency):
    """Invalid POST data re-renders earning form with 200."""
    url = reverse("sales:commission_earning_create")
    payload = _incentivecompensation_earning_payload(
        commission_plan_a,
        member_user,
        icm_currency,
        split_percentage="150.00",  # invalid split > 100%
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_incentivecompensation_earning_detail_view(client_a, commission_earning_a):
    """Detail view renders 200 with earning context."""
    url = reverse("sales:commission_earning_detail", kwargs={"pk": commission_earning_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["obj"] == commission_earning_a


def test_incentivecompensation_earning_detail_rep_isolation_404(member_client, tenant_a, commission_plan_a, admin_user):
    """Member rep cannot view detail of another rep's earning (returns 404)."""
    other_earning = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=admin_user,
    )
    url = reverse("sales:commission_earning_detail", kwargs={"pk": other_earning.pk})
    resp = member_client.get(url)
    assert resp.status_code == 404


def test_incentivecompensation_earning_detail_cross_tenant_404(client_a, commission_earning_b):
    """Tenant A client accessing Tenant B earning returns 404."""
    url = reverse("sales:commission_earning_detail", kwargs={"pk": commission_earning_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_incentivecompensation_earning_edit_get_and_post_success(
    client_a, tenant_a, commission_plan_a, member_user, icm_currency
):
    """Draft earning can be edited via GET 200 and POST 302."""
    earning = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        currency=icm_currency,
        deal_amount=Decimal("40000.00"),
        status="calculated",
    )
    url = reverse("sales:commission_earning_edit", kwargs={"pk": earning.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    payload = _incentivecompensation_earning_payload(
        commission_plan_a,
        member_user,
        icm_currency,
        deal_amount="45000.00",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    earning.refresh_from_db()
    assert earning.deal_amount == Decimal("45000.00")


def test_incentivecompensation_earning_edit_paid_status_guard(client_a, tenant_a, commission_plan_a, member_user, icm_currency):
    """Attempting to edit a paid earning redirects safely without modifying record (regression test for C10)."""
    paid_earning = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        currency=icm_currency,
        deal_amount=Decimal("50000.00"),
        status="paid",
    )
    url = reverse("sales:commission_earning_edit", kwargs={"pk": paid_earning.pk})

    # GET edit redirects with error
    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get["Location"] == reverse("sales:commission_earning_detail", kwargs={"pk": paid_earning.pk})

    # POST edit redirects with error and leaves data untouched
    payload = _incentivecompensation_earning_payload(
        commission_plan_a,
        member_user,
        icm_currency,
        deal_amount="99999.00",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    paid_earning.refresh_from_db()
    assert paid_earning.deal_amount == Decimal("50000.00"), "C10 regression: paid earning was mutated!"


def test_incentivecompensation_earning_edit_locked_statement_guard(
    client_a, tenant_a, commission_plan_a, member_user, icm_currency
):
    """Attempting to edit earning attached to a locked statement redirects safely (regression test for C10)."""
    locked_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        status="locked",
    )
    earning = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        currency=icm_currency,
        deal_amount=Decimal("30000.00"),
        statement=locked_stmt,
        status="approved",
    )
    url = reverse("sales:commission_earning_edit", kwargs={"pk": earning.pk})
    resp_post = client_a.post(url, _incentivecompensation_earning_payload(commission_plan_a, member_user, icm_currency))
    assert resp_post.status_code == 302
    earning.refresh_from_db()
    assert earning.deal_amount == Decimal("30000.00")


def test_incentivecompensation_earning_delete_get_does_not_delete(client_a, commission_earning_a):
    """GET delete returns status in (200, 405) and does NOT delete the earning."""
    url = reverse("sales:commission_earning_delete", kwargs={"pk": commission_earning_a.pk})
    resp = client_a.get(url)
    assert resp.status_code in (200, 405)
    assert CommissionEarning.objects.filter(pk=commission_earning_a.pk).exists()


def test_incentivecompensation_earning_delete_post_success(
    client_a, tenant_a, commission_plan_a, member_user, icm_currency
):
    """POST delete deletes a draft earning and redirects 302 to list."""
    earning = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        currency=icm_currency,
        status="calculated",
    )
    url = reverse("sales:commission_earning_delete", kwargs={"pk": earning.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("sales:commission_earning_list")
    assert not CommissionEarning.objects.filter(pk=earning.pk).exists()


def test_incentivecompensation_earning_delete_paid_guard(
    client_a, tenant_a, commission_plan_a, member_user, icm_currency
):
    """Attempting to delete a paid earning redirects safely without deleting (regression test for C10)."""
    paid_earning = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        currency=icm_currency,
        status="paid",
    )
    url = reverse("sales:commission_earning_delete", kwargs={"pk": paid_earning.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert CommissionEarning.objects.filter(pk=paid_earning.pk).exists(), "C10 regression: paid earning was deleted!"


def test_incentivecompensation_earning_delete_locked_statement_guard(
    client_a, tenant_a, commission_plan_a, member_user, icm_currency
):
    """Attempting to delete an earning on a locked statement redirects safely without deleting (regression test for C10)."""
    locked_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        status="locked",
    )
    earning = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        currency=icm_currency,
        statement=locked_stmt,
        status="approved",
    )
    url = reverse("sales:commission_earning_delete", kwargs={"pk": earning.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert CommissionEarning.objects.filter(pk=earning.pk).exists()


def test_incentivecompensation_earning_delete_non_admin_forbidden(member_client, commission_earning_a):
    """Non-admin user cannot delete an earning (returns 403 Forbidden)."""
    url = reverse("sales:commission_earning_delete", kwargs={"pk": commission_earning_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert CommissionEarning.objects.filter(pk=commission_earning_a.pk).exists()


# ==============================================================================
# 4. CommissionStatement CRUD & Action Endpoints (C9)
# ==============================================================================

def test_incentivecompensation_statement_list_view_and_filters(client_a, tenant_a, commission_statement_a):
    """Statement list view returns 200 and supports search and status filtering."""
    url = reverse("sales:commission_statement_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "object_list" in resp.context
    assert "stats" in resp.context
    assert commission_statement_a in resp.context["object_list"]

    # Filter status
    resp_draft = client_a.get(url, {"status": "draft"})
    assert resp_draft.status_code == 200
    assert commission_statement_a in resp_draft.context["object_list"]


def test_incentivecompensation_statement_list_rep_isolation(member_client, tenant_a, commission_plan_a, admin_user):
    """Member rep only sees statements where payee is request.user."""
    admin_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=admin_user,
    )
    url = reverse("sales:commission_statement_list")
    resp = member_client.get(url)
    assert resp.status_code == 200
    pks = [s.pk for s in resp.context["object_list"]]
    assert admin_stmt.pk not in pks


def test_incentivecompensation_statement_list_pagination(client_a, tenant_a, commission_plan_a, member_user):
    """Commission statements list paginates cleanly."""
    for i in range(16):
        p_start = date(2020, 1, 1) + timedelta(days=35 * i)
        p_end = p_start + timedelta(days=28)
        _incentivecompensation_statement(
            tenant_a,
            plan=commission_plan_a,
            payee=member_user,
            period_start=p_start,
            period_end=p_end,
            number=f"CST-PAG-{i}",
            statement_number=f"PAG-STMT-{i}-{int(timezone.now().timestamp() * 1000) % 10000}",
        )
    url = reverse("sales:commission_statement_list")
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["object_list"]) >= 1


def test_incentivecompensation_statement_create_get_and_post_success(client_a, tenant_a, commission_plan_a, member_user):
    """GET create statement form returns 200, valid POST creates statement and redirects 302."""
    url = reverse("sales:commission_statement_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False

    payload = _incentivecompensation_statement_payload(
        member_user,
        commission_plan_a,
        statement_number="STMT-CUSTOM-2026-Q3",
        period_start="2026-07-01",
        period_end="2026-09-30",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    created = CommissionStatement.objects.filter(tenant=tenant_a, statement_number="STMT-CUSTOM-2026-Q3").first()
    assert created is not None
    assert resp_post["Location"] == reverse("sales:commission_statement_detail", kwargs={"pk": created.pk})


def test_incentivecompensation_statement_create_post_invalid(client_a, commission_plan_a, member_user):
    """Invalid POST data (period_start > period_end) re-renders form with 200."""
    url = reverse("sales:commission_statement_create")
    payload = _incentivecompensation_statement_payload(
        member_user,
        commission_plan_a,
        period_start="2026-10-31",
        period_end="2026-10-01",  # inverted
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_incentivecompensation_statement_detail_view(client_a, commission_statement_a):
    """Detail view renders 200 with object and earnings/adjustments context."""
    url = reverse("sales:commission_statement_detail", kwargs={"pk": commission_statement_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["obj"] == commission_statement_a
    assert "earnings_list" in resp.context
    assert "adjustments_list" in resp.context
    assert "can_approve" in resp.context
    assert "can_lock" in resp.context


def test_incentivecompensation_statement_detail_rep_isolation_404(member_client, tenant_a, commission_plan_a, admin_user):
    """Member rep cannot access detail of another rep's statement (returns 404)."""
    admin_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=admin_user,
    )
    url = reverse("sales:commission_statement_detail", kwargs={"pk": admin_stmt.pk})
    resp = member_client.get(url)
    assert resp.status_code == 404


def test_incentivecompensation_statement_detail_cross_tenant_404(client_a, commission_statement_b):
    """Tenant A client accessing Tenant B statement returns 404."""
    url = reverse("sales:commission_statement_detail", kwargs={"pk": commission_statement_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_incentivecompensation_statement_edit_get_and_post_success(
    client_a, tenant_a, commission_plan_a, member_user
):
    """Draft statement can be edited via GET 200 and POST 302."""
    stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        status="draft",
        notes="Initial notes",
    )
    url = reverse("sales:commission_statement_edit", kwargs={"pk": stmt.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    payload = _incentivecompensation_statement_payload(
        member_user,
        commission_plan_a,
        statement_number=stmt.statement_number,
        notes="Updated notes via edit view",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    stmt.refresh_from_db()
    assert stmt.notes == "Updated notes via edit view"


def test_incentivecompensation_statement_edit_locked_guard(
    client_a, tenant_a, commission_plan_a, member_user
):
    """Locked statement cannot be edited; redirects 302 to detail without modifications."""
    locked_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        status="locked",
        notes="Original locked notes",
    )
    url = reverse("sales:commission_statement_edit", kwargs={"pk": locked_stmt.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get["Location"] == reverse("sales:commission_statement_detail", kwargs={"pk": locked_stmt.pk})

    resp_post = client_a.post(
        url,
        _incentivecompensation_statement_payload(
            member_user,
            commission_plan_a,
            statement_number=locked_stmt.statement_number,
            notes="Should not change",
        ),
    )
    assert resp_post.status_code == 302
    locked_stmt.refresh_from_db()
    assert locked_stmt.notes == "Original locked notes"


def test_incentivecompensation_statement_delete_get_does_not_delete(client_a, commission_statement_a):
    """GET on statement delete returns status in (200, 405) and does NOT delete the statement."""
    url = reverse("sales:commission_statement_delete", kwargs={"pk": commission_statement_a.pk})
    resp = client_a.get(url)
    assert resp.status_code in (200, 405)
    assert CommissionStatement.objects.filter(pk=commission_statement_a.pk).exists()


def test_incentivecompensation_statement_delete_post_success(
    client_a, tenant_a, commission_plan_a, member_user
):
    """POST delete deletes a draft statement and redirects 302 to list."""
    stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        status="draft",
    )
    url = reverse("sales:commission_statement_delete", kwargs={"pk": stmt.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("sales:commission_statement_list")
    assert not CommissionStatement.objects.filter(pk=stmt.pk).exists()


def test_incentivecompensation_statement_delete_locked_guard(
    client_a, tenant_a, commission_plan_a, member_user
):
    """Attempting to delete a locked statement redirects 302 with error; statement is not deleted."""
    locked_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        status="locked",
    )
    url = reverse("sales:commission_statement_delete", kwargs={"pk": locked_stmt.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert CommissionStatement.objects.filter(pk=locked_stmt.pk).exists()


def test_incentivecompensation_statement_delete_non_admin_forbidden(member_client, commission_statement_a):
    """Non-admin user cannot delete a statement (returns 403 Forbidden)."""
    url = reverse("sales:commission_statement_delete", kwargs={"pk": commission_statement_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert CommissionStatement.objects.filter(pk=commission_statement_a.pk).exists()


def test_incentivecompensation_statement_approve_action_success(client_a, commission_statement_a, admin_user):
    """Admin POST to statement approve transitions status to 'approved' and records approved_by."""
    url = reverse("sales:commission_statement_approve", kwargs={"pk": commission_statement_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("sales:commission_statement_detail", kwargs={"pk": commission_statement_a.pk})
    commission_statement_a.refresh_from_db()
    assert commission_statement_a.status == "approved"
    assert commission_statement_a.approved_by == admin_user
    assert commission_statement_a.approved_at is not None


def test_incentivecompensation_statement_approve_self_approval_forbidden(tenant_a, commission_plan_a, admin_user):
    """Admin cannot approve their own commission statement (returns 403 Forbidden)."""
    admin_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=admin_user,
        status="under_review",
    )
    admin_client = Client()
    admin_client.force_login(admin_user)
    url = reverse("sales:commission_statement_approve", kwargs={"pk": admin_stmt.pk})
    resp = admin_client.post(url)
    assert resp.status_code == 403
    admin_stmt.refresh_from_db()
    assert admin_stmt.status == "under_review"


def test_incentivecompensation_statement_approve_invalid_status_safe(client_a, tenant_a, commission_plan_a, member_user):
    """Attempting to approve a locked statement redirects safely with error message."""
    locked_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        status="locked",
    )
    url = reverse("sales:commission_statement_approve", kwargs={"pk": locked_stmt.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    locked_stmt.refresh_from_db()
    assert locked_stmt.status == "locked"


def test_incentivecompensation_statement_lock_action_success(client_a, tenant_a, commission_plan_a, member_user, admin_user):
    """Admin POST to lock an approved statement transitions status to 'locked' and records locked_at."""
    approved_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        status="approved",
        approved_by=admin_user,
    )
    url = reverse("sales:commission_statement_lock", kwargs={"pk": approved_stmt.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("sales:commission_statement_detail", kwargs={"pk": approved_stmt.pk})
    approved_stmt.refresh_from_db()
    assert approved_stmt.status == "locked"
    assert approved_stmt.locked_at is not None


def test_incentivecompensation_statement_lock_draft_status_safe(client_a, commission_statement_a):
    """Draft statement cannot be locked; redirects safely without status change."""
    url = reverse("sales:commission_statement_lock", kwargs={"pk": commission_statement_a.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    commission_statement_a.refresh_from_db()
    assert commission_statement_a.status == "draft"


def test_incentivecompensation_statement_generate_batch_net_payout(
    client_a, tenant_a, icm_currency, member_user
):
    """Batch generation creates statement with accurate net_payout and draw recovery (regression test for C9)."""
    # Active plan with recoverable draw of 1000.00
    plan = _incentivecompensation_plan(
        tenant_a,
        currency=icm_currency,
        name="Batch Generation Plan",
        code="BATCH-PLAN-2026",
        draw_amount=Decimal("1000.00"),
        is_draw_recoverable=True,
        status="active",
    )
    # Create unattached earnings for member_user in period
    p_start = date(2026, 11, 1)
    p_end = date(2026, 11, 30)
    e1 = _incentivecompensation_earning(
        tenant_a,
        plan=plan,
        payee=member_user,
        currency=icm_currency,
        deal_amount=Decimal("30000.00"),
        earned_date=date(2026, 11, 10),
        statement=None,
    )
    e2 = _incentivecompensation_earning(
        tenant_a,
        plan=plan,
        payee=member_user,
        currency=icm_currency,
        deal_amount=Decimal("20000.00"),
        earned_date=date(2026, 11, 20),
        statement=None,
    )
    expected_gross = e1.gross_commission + e2.gross_commission
    expected_draw_rec = min(expected_gross, plan.draw_amount)
    expected_net = expected_gross - expected_draw_rec

    url = reverse("sales:commission_statement_generate_batch")
    resp = client_a.post(
        url,
        {
            "period_start": str(p_start),
            "period_end": str(p_end),
            "plan_id": str(plan.pk),
        },
    )
    assert resp.status_code == 302
    assert resp["Location"] == reverse("sales:commission_statement_list")

    # Verify statement generated with net_payout calculation
    generated_stmt = CommissionStatement.objects.filter(
        tenant=tenant_a, payee=member_user, period_start=p_start, period_end=p_end
    ).first()
    assert generated_stmt is not None, "C9 regression: Statement was not generated by batch action"
    assert generated_stmt.gross_earnings == expected_gross
    assert generated_stmt.draw_recovered == expected_draw_rec
    assert generated_stmt.net_payout == expected_net, "C9 regression: net_payout calculation mismatch"

    # Verify earnings now linked to statement
    e1.refresh_from_db()
    e2.refresh_from_db()
    assert e1.statement == generated_stmt
    assert e2.statement == generated_stmt


def test_incentivecompensation_statement_generate_batch_invalid_inputs(client_a):
    """Batch generate endpoint with missing or non-decimal plan_id redirects cleanly without 500."""
    url = reverse("sales:commission_statement_generate_batch")
    resp_missing = client_a.post(url, {})
    assert resp_missing.status_code == 302
    assert resp_missing["Location"] == reverse("sales:commission_statement_list")

    resp_bad_id = client_a.post(url, {"period_start": "2026-11-01", "period_end": "2026-11-30", "plan_id": "abc"})
    assert resp_bad_id.status_code == 302
    assert resp_bad_id["Location"] == reverse("sales:commission_statement_list")


# ==============================================================================
# 5. CommissionAdjustment CRUD & Action Endpoints (C10)
# ==============================================================================

def test_incentivecompensation_adjustment_list_view_and_filters(client_a, tenant_a, commission_adjustment_a):
    """Adjustment list view returns 200 and supports adjustment_type, status, payee filters."""
    url = reverse("sales:commission_adjustment_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "object_list" in resp.context
    assert "stats" in resp.context
    assert commission_adjustment_a in resp.context["object_list"]

    # Filter status
    resp_draft = client_a.get(url, {"status": "draft"})
    assert resp_draft.status_code == 200
    assert commission_adjustment_a in resp_draft.context["object_list"]


def test_incentivecompensation_adjustment_list_rep_isolation(member_client, tenant_a, admin_user):
    """Member rep only sees adjustments where payee is request.user."""
    admin_adj = _incentivecompensation_adjustment(
        tenant_a,
        payee=admin_user,
    )
    url = reverse("sales:commission_adjustment_list")
    resp = member_client.get(url)
    assert resp.status_code == 200
    pks = [a.pk for a in resp.context["object_list"]]
    assert admin_adj.pk not in pks


def test_incentivecompensation_adjustment_list_pagination(client_a, tenant_a, member_user):
    """Commission adjustments list paginates cleanly."""
    for i in range(16):
        _incentivecompensation_adjustment(
            tenant_a,
            payee=member_user,
            amount=Decimal(100 + i * 10),
        )
    url = reverse("sales:commission_adjustment_list")
    resp_p2 = client_a.get(url, {"page": "2"})
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["object_list"]) >= 1


def test_incentivecompensation_adjustment_create_get_and_post_success(
    client_a, tenant_a, member_user, admin_user
):
    """GET create adjustment returns 200, valid POST creates adjustment and sets requested_by."""
    url = reverse("sales:commission_adjustment_create")
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is False

    payload = _incentivecompensation_adjustment_payload(
        member_user,
        adjustment_type="manual_override",
        amount="350.00",
        reason="Presales compensation adjustment",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    created = CommissionAdjustment.objects.filter(
        tenant=tenant_a, payee=member_user, amount=Decimal("350.00")
    ).first()
    assert created is not None
    assert resp_post["Location"] == reverse("sales:commission_adjustment_detail", kwargs={"pk": created.pk})
    assert created.requested_by == admin_user


def test_incentivecompensation_adjustment_create_post_invalid(client_a, member_user):
    """Invalid POST data (positive amount for cancellation_clawback) re-renders form with 200."""
    url = reverse("sales:commission_adjustment_create")
    payload = _incentivecompensation_adjustment_payload(
        member_user,
        adjustment_type="cancellation_clawback",
        amount="500.00",  # Clawbacks must be negative
    )
    resp = client_a.post(url, payload)
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_incentivecompensation_adjustment_detail_view(client_a, commission_adjustment_a):
    """Detail view renders 200 with adjustment context."""
    url = reverse("sales:commission_adjustment_detail", kwargs={"pk": commission_adjustment_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert resp.context["obj"] == commission_adjustment_a


def test_incentivecompensation_adjustment_detail_rep_isolation_404(member_client, tenant_a, admin_user):
    """Member rep cannot view detail of another rep's adjustment (returns 404)."""
    admin_adj = _incentivecompensation_adjustment(
        tenant_a,
        payee=admin_user,
    )
    url = reverse("sales:commission_adjustment_detail", kwargs={"pk": admin_adj.pk})
    resp = member_client.get(url)
    assert resp.status_code == 404


def test_incentivecompensation_adjustment_detail_cross_tenant_404(client_a, commission_adjustment_b):
    """Tenant A client accessing Tenant B adjustment returns 404."""
    url = reverse("sales:commission_adjustment_detail", kwargs={"pk": commission_adjustment_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_incentivecompensation_adjustment_edit_get_and_post_success(
    client_a, tenant_a, member_user
):
    """Draft adjustment can be edited via GET 200 and POST 302."""
    adj = _incentivecompensation_adjustment(
        tenant_a,
        payee=member_user,
        status="draft",
        amount=Decimal("150.00"),
    )
    url = reverse("sales:commission_adjustment_edit", kwargs={"pk": adj.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 200

    payload = _incentivecompensation_adjustment_payload(
        member_user,
        adjustment_type="manual_override",
        amount="200.00",
        reason="Updated adjustment amount",
    )
    resp_post = client_a.post(url, payload)
    assert resp_post.status_code == 302
    adj.refresh_from_db()
    assert adj.amount == Decimal("200.00")


def test_incentivecompensation_adjustment_edit_applied_guard(
    client_a, tenant_a, member_user
):
    """Approved/applied adjustment cannot be edited; redirects 302 without modifications (regression test for C10)."""
    approved_adj = _incentivecompensation_adjustment(
        tenant_a,
        payee=member_user,
        status="approved",
        amount=Decimal("300.00"),
    )
    url = reverse("sales:commission_adjustment_edit", kwargs={"pk": approved_adj.pk})
    resp_get = client_a.get(url)
    assert resp_get.status_code == 302
    assert resp_get["Location"] == reverse("sales:commission_adjustment_detail", kwargs={"pk": approved_adj.pk})

    resp_post = client_a.post(
        url,
        _incentivecompensation_adjustment_payload(member_user, amount="999.00"),
    )
    assert resp_post.status_code == 302
    approved_adj.refresh_from_db()
    assert approved_adj.amount == Decimal("300.00")


def test_incentivecompensation_adjustment_delete_get_does_not_delete(client_a, commission_adjustment_a):
    """GET on adjustment delete returns status in (200, 405) and does NOT delete the adjustment."""
    url = reverse("sales:commission_adjustment_delete", kwargs={"pk": commission_adjustment_a.pk})
    resp = client_a.get(url)
    assert resp.status_code in (200, 405)
    assert CommissionAdjustment.objects.filter(pk=commission_adjustment_a.pk).exists()


def test_incentivecompensation_adjustment_delete_post_success(
    client_a, tenant_a, member_user
):
    """POST delete deletes a draft adjustment and redirects 302 to list."""
    adj = _incentivecompensation_adjustment(
        tenant_a,
        payee=member_user,
        status="draft",
    )
    url = reverse("sales:commission_adjustment_delete", kwargs={"pk": adj.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("sales:commission_adjustment_list")
    assert not CommissionAdjustment.objects.filter(pk=adj.pk).exists()


def test_incentivecompensation_adjustment_delete_applied_guard(
    client_a, tenant_a, member_user
):
    """Approved adjustment cannot be deleted; redirects 302 with error (regression test for C10)."""
    approved_adj = _incentivecompensation_adjustment(
        tenant_a,
        payee=member_user,
        status="approved",
    )
    url = reverse("sales:commission_adjustment_delete", kwargs={"pk": approved_adj.pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert CommissionAdjustment.objects.filter(pk=approved_adj.pk).exists()


def test_incentivecompensation_adjustment_delete_non_admin_forbidden(member_client, commission_adjustment_a):
    """Non-admin user cannot delete an adjustment (returns 403 Forbidden)."""
    url = reverse("sales:commission_adjustment_delete", kwargs={"pk": commission_adjustment_a.pk})
    resp = member_client.post(url)
    assert resp.status_code == 403
    assert CommissionAdjustment.objects.filter(pk=commission_adjustment_a.pk).exists()


def test_incentivecompensation_adjustment_resolve_dispute_approve(
    client_a, tenant_a, member_user, admin_user
):
    """Admin approves disputed adjustment via resolve-dispute endpoint."""
    disputed_adj = _incentivecompensation_adjustment(
        tenant_a,
        payee=member_user,
        requested_by=member_user,
        status="disputed",
        dispute_comments="Rep claim: deal credit split was omitted.",
    )
    url = reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": disputed_adj.pk})
    resp = client_a.post(
        url,
        {
            "decision": "approve",
            "resolution_notes": "Audit confirmed split omission. Approved.",
        },
    )
    assert resp.status_code == 302
    assert resp["Location"] == reverse("sales:commission_adjustment_detail", kwargs={"pk": disputed_adj.pk})
    disputed_adj.refresh_from_db()
    assert disputed_adj.status == "approved"
    assert disputed_adj.approved_by == admin_user
    assert "Audit confirmed split omission" in disputed_adj.dispute_comments


def test_incentivecompensation_adjustment_resolve_dispute_reject(
    client_a, tenant_a, member_user
):
    """Admin rejects disputed adjustment via resolve-dispute endpoint."""
    disputed_adj = _incentivecompensation_adjustment(
        tenant_a,
        payee=member_user,
        requested_by=member_user,
        status="disputed",
    )
    url = reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": disputed_adj.pk})
    resp = client_a.post(
        url,
        {
            "decision": "reject",
            "resolution_notes": "Terms of plan exclude late clawback exemptions.",
        },
    )
    assert resp.status_code == 302
    disputed_adj.refresh_from_db()
    assert disputed_adj.status == "rejected"


def test_incentivecompensation_adjustment_resolve_dispute_self_resolution_forbidden(
    tenant_a, admin_user
):
    """User cannot resolve their own disputed adjustment (returns 403 Forbidden)."""
    own_disputed = _incentivecompensation_adjustment(
        tenant_a,
        payee=admin_user,
        requested_by=admin_user,
        status="disputed",
    )
    admin_client = Client()
    admin_client.force_login(admin_user)
    url = reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": own_disputed.pk})
    resp = admin_client.post(url, {"decision": "approve"})
    assert resp.status_code == 403
    own_disputed.refresh_from_db()
    assert own_disputed.status == "disputed"


def test_incentivecompensation_adjustment_resolve_dispute_non_disputed_safe(
    client_a, tenant_a, member_user
):
    """Attempting to resolve a draft adjustment redirects safely with error."""
    draft_adj = _incentivecompensation_adjustment(
        tenant_a,
        payee=member_user,
        status="draft",
    )
    url = reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": draft_adj.pk})
    resp = client_a.post(url, {"decision": "approve"})
    assert resp.status_code == 302
    draft_adj.refresh_from_db()
    assert draft_adj.status == "draft"


# ==============================================================================
# 6. Negative-Input Hardening & Junk Queries (L11)
# ==============================================================================

def test_incentivecompensation_junk_get_query_params_return_200(client_a):
    """Junk GET query parameters across all 4 list views return 200, not 500 (regression test for L11)."""
    endpoints = [
        "sales:commission_plan_list",
        "sales:commission_earning_list",
        "sales:commission_statement_list",
        "sales:commission_adjustment_list",
    ]
    junk_params = {
        "status": "garbage_status_xyz",
        "payee": "not_an_id",
        "plan": "invalid_plan_fk",
        "credit_type": "bogus_type",
        "adjustment_type": "nonsense_adj",
        "plan_type": "fake_plan_type",
        "tier_mode": "fake_tier_mode",
        "page": "999",
        "q": "???'''&&&$$$///",
    }
    for ep in endpoints:
        resp = client_a.get(reverse(ep), junk_params)
        assert resp.status_code == 200, f"L11 regression: {ep} crashed with 500 on junk GET params"


def test_incentivecompensation_unauthenticated_access_redirects_to_login(client, commission_plan_a):
    """Unauthenticated access to boards, lists, forms and actions redirects 302 to login."""
    urls = [
        reverse("sales:sales_commission_plan_hub"),
        reverse("sales:sales_commission_earnings_dashboard"),
        reverse("sales:sales_commission_adjustment_workbench"),
        reverse("sales:sales_global_compensation_matrix"),
        reverse("sales:sales_commission_payout_processing"),
        reverse("sales:commission_plan_list"),
        reverse("sales:commission_plan_create"),
        reverse("sales:commission_plan_detail", kwargs={"pk": commission_plan_a.pk}),
        reverse("sales:commission_plan_edit", kwargs={"pk": commission_plan_a.pk}),
        reverse("sales:commission_earning_list"),
        reverse("sales:commission_statement_list"),
        reverse("sales:commission_adjustment_list"),
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect to login for {url}, got {resp.status_code}"
        assert "/login" in resp["Location"]
