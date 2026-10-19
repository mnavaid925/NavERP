"""Sales 8.10 — Incentive Compensation Security, Authorization & Audit Test Suite.

Covers:
1. Authentication & HTTP Method Restrictions:
   - Unauthenticated callers redirect to login across CRUD, actions, and boards.
   - Delete and state-changing action endpoints strictly reject GET requests with 405 Method Not Allowed.
2. Multi-Tenant IDOR Isolation (IDOR -> 404):
   - Tenant A admin and rep requesting Tenant B objects (plan, earning, statement, adjustment)
     across detail, edit, delete, approve, lock, resolve_dispute strictly return 404 Not Found.
   - List views and all 5 board views for Tenant A never leak Tenant B records.
3. Cross-Tenant Foreign Key Injection Defenses:
   - Form and view rejection of foreign tenant FKs across all 4 models.
   - Model clean() rejection when setting cross-tenant foreign keys directly.
4. Privileged AuthZ & Self-Approval Prevention:
   - Rep payee cannot approve own statement (commission_statement_approve returns 403) — regression for C2.
   - Non-admin or payee cannot lock statement (commission_statement_lock returns 403) — regression for C3.
   - Rep payee or claimant cannot resolve own dispute (commission_adjustment_resolve_dispute returns 403) — regression for C4.
   - Non-admin cannot execute batch generation (commission_statement_generate_batch returns 403) — regression for C9.
5. Horizontal Data Privacy (I8):
   - Regular sales rep can only view their own earnings and statements in list and detail views.
   - Regular rep cannot edit or mutate another rep's earning or statement (returns 404/403).
6. Mass Assignment Protection (C5):
   - Submitting status="approved" or status="paid" in form POSTs does not bypass workflow states.
7. CSRF Protection:
   - POST endpoints without CSRF token are rejected with 403 when CSRF is enforced.
8. Audit Logging Contracts (C1):
   - Verify create, edit, delete, approve, lock, dispute resolve, and batch generate operations
     write valid AuditLog entries without crashing.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounting.models import Currency
from apps.core.models import AuditLog, Party
from apps.crm.models import Opportunity, SalesQuota
from apps.sales.forms.IncentiveCompensation.CommissionAdjustments import CommissionAdjustmentForm
from apps.sales.forms.IncentiveCompensation.CommissionEarnings import CommissionEarningForm
from apps.sales.forms.IncentiveCompensation.CommissionPlans import CommissionPlanForm
from apps.sales.forms.IncentiveCompensation.CommissionStatements import CommissionStatementForm
from apps.sales.models.IncentiveCompensation.CommissionAdjustments import CommissionAdjustment
from apps.sales.models.IncentiveCompensation.CommissionEarnings import CommissionEarning
from apps.sales.models.IncentiveCompensation.CommissionPlans import CommissionPlan
from apps.sales.models.IncentiveCompensation.CommissionStatements import CommissionStatement
from apps.sales.tests.conftest import (
    _incentivecompensation_adjustment,
    _incentivecompensation_currency,
    _incentivecompensation_earning,
    _incentivecompensation_plan,
    _incentivecompensation_statement,
)
from apps.scm.models import SalesOrder

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_incentivecompensation_*)
# ==============================================================================


def _incentivecompensation_create_user(tenant, username, is_admin=False):
    """Helper creating an isolated test user scoped to tenant."""
    return User.objects.create_user(
        username=username,
        email=f"{username}@{tenant.slug}.example.com",
        password="TestPass123!",
        tenant=tenant,
        is_tenant_admin=is_admin,
    )


def _incentivecompensation_csrf_client(user):
    """Create a test client with CSRF protection enforced and user logged in."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    return client


def _incentivecompensation_party(tenant, name="Customer Organization"):
    """Helper creating a valid Party for tenant."""
    label = f"{int(timezone.now().timestamp() * 1000) % 100000}"
    return Party.objects.create(
        tenant=tenant,
        name=f"{name} {label}",
        kind="organization",
    )


def _incentivecompensation_opportunity(tenant, name="Enterprise Deal", amount=Decimal("120000.00"), **overrides):
    """Helper creating a CRM Opportunity scoped to tenant."""
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


def _incentivecompensation_sales_order(tenant, total=Decimal("50000.00"), **overrides):
    """Helper creating an SCM SalesOrder scoped to tenant."""
    customer = overrides.pop("customer", None) or _incentivecompensation_party(tenant)
    defaults = {
        "tenant": tenant,
        "customer": customer,
        "source_channel": "direct",
        "status": "confirmed",
        "credit_hold": False,
        "fraud_flag": False,
        "subtotal": total,
        "tax_total": Decimal("0.00"),
        "total": total,
    }
    defaults.update(overrides)
    return SalesOrder.objects.create(**defaults)


def _incentivecompensation_sales_quota(tenant, owner=None, target_amount=Decimal("250000.00"), **overrides):
    """Helper creating a CRM SalesQuota scoped to tenant."""
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
    """Valid POST payload for CommissionPlanForm."""
    label = f"{int(timezone.now().timestamp() * 1000) % 100000}"
    defaults = {
        "name": f"Security Suite Plan {label}",
        "code": f"SEC-PLAN-{label}",
        "description": "Baseline plan for security verification",
        "plan_type": "flat_revenue",
        "tier_mode": "not_applicable",
        "status": "active",
        "payout_frequency": "monthly",
        "effective_start": "2026-01-01",
        "effective_end": "2026-12-31",
        "currency": str(currency.pk),
        "target_region": "North America",
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
    """Valid POST payload for CommissionEarningForm."""
    defaults = {
        "plan": str(plan.pk),
        "payee": str(payee.pk),
        "credit_type": "direct",
        "split_percentage": "100.00",
        "deal_amount": "60000.00",
        "attainment_pct_at_close": "85.00",
        "applied_rate_pct": "10.00",
        "spif_amount": "250.00",
        "deal_currency": str(currency.pk),
        "exchange_rate": "1.000000",
        "earned_date": "2026-06-15",
    }
    defaults.update(overrides)
    return defaults


def _incentivecompensation_statement_payload(payee, plan, **overrides):
    """Valid POST payload for CommissionStatementForm."""
    label = f"{int(timezone.now().timestamp() * 1000) % 100000}"
    defaults = {
        "statement_number": f"STMT-SEC-{label}",
        "payee": str(payee.pk),
        "plan": str(plan.pk),
        "period_start": "2026-10-01",
        "period_end": "2026-10-31",
        "draw_advance_paid": "1000.00",
        "notes": "Security test statement",
    }
    defaults.update(overrides)
    return defaults


def _incentivecompensation_adjustment_payload(payee, **overrides):
    """Valid POST payload for CommissionAdjustmentForm."""
    defaults = {
        "payee": str(payee.pk),
        "adjustment_type": "manual_override",
        "amount": "300.00",
        "reason": "Security review discretionary adjustment",
        "effective_date": "2026-10-15",
    }
    defaults.update(overrides)
    return defaults


# ==============================================================================
# 1. Authentication & HTTP Method Restrictions
# ==============================================================================


def test_incentivecompensation_auth_redirects_unauthenticated(
    client, commission_plan_a, commission_earning_a, commission_statement_a, commission_adjustment_a
):
    """Unauthenticated calls across CRUD, boards, and action endpoints redirect to login."""
    routes = [
        # Boards
        ("GET", reverse("sales:sales_commission_plan_hub"), {}),
        ("GET", reverse("sales:sales_commission_earnings_dashboard"), {}),
        ("GET", reverse("sales:sales_commission_adjustment_workbench"), {}),
        ("GET", reverse("sales:sales_global_compensation_matrix"), {}),
        ("GET", reverse("sales:sales_commission_payout_processing"), {}),
        ("GET", reverse("sales:sales_commission_what_if_calc"), {}),
        # Plan CRUD
        ("GET", reverse("sales:commission_plan_list"), {}),
        ("GET", reverse("sales:commission_plan_create"), {}),
        ("POST", reverse("sales:commission_plan_create"), {"name": "Anon Plan"}),
        ("GET", reverse("sales:commission_plan_detail", kwargs={"pk": commission_plan_a.pk}), {}),
        ("GET", reverse("sales:commission_plan_edit", kwargs={"pk": commission_plan_a.pk}), {}),
        ("POST", reverse("sales:commission_plan_edit", kwargs={"pk": commission_plan_a.pk}), {"name": "Anon Edit"}),
        ("POST", reverse("sales:commission_plan_delete", kwargs={"pk": commission_plan_a.pk}), {}),
        # Earning CRUD
        ("GET", reverse("sales:commission_earning_list"), {}),
        ("GET", reverse("sales:commission_earning_create"), {}),
        ("POST", reverse("sales:commission_earning_create"), {}),
        ("GET", reverse("sales:commission_earning_detail", kwargs={"pk": commission_earning_a.pk}), {}),
        ("GET", reverse("sales:commission_earning_edit", kwargs={"pk": commission_earning_a.pk}), {}),
        ("POST", reverse("sales:commission_earning_edit", kwargs={"pk": commission_earning_a.pk}), {}),
        ("POST", reverse("sales:commission_earning_delete", kwargs={"pk": commission_earning_a.pk}), {}),
        # Statement CRUD & Actions
        ("GET", reverse("sales:commission_statement_list"), {}),
        ("GET", reverse("sales:commission_statement_create"), {}),
        ("POST", reverse("sales:commission_statement_create"), {}),
        ("GET", reverse("sales:commission_statement_detail", kwargs={"pk": commission_statement_a.pk}), {}),
        ("GET", reverse("sales:commission_statement_edit", kwargs={"pk": commission_statement_a.pk}), {}),
        ("POST", reverse("sales:commission_statement_edit", kwargs={"pk": commission_statement_a.pk}), {}),
        ("POST", reverse("sales:commission_statement_delete", kwargs={"pk": commission_statement_a.pk}), {}),
        ("POST", reverse("sales:commission_statement_approve", kwargs={"pk": commission_statement_a.pk}), {}),
        ("POST", reverse("sales:commission_statement_lock", kwargs={"pk": commission_statement_a.pk}), {}),
        ("POST", reverse("sales:commission_statement_generate_batch"), {}),
        # Adjustment CRUD & Actions
        ("GET", reverse("sales:commission_adjustment_list"), {}),
        ("GET", reverse("sales:commission_adjustment_create"), {}),
        ("POST", reverse("sales:commission_adjustment_create"), {}),
        ("GET", reverse("sales:commission_adjustment_detail", kwargs={"pk": commission_adjustment_a.pk}), {}),
        ("GET", reverse("sales:commission_adjustment_edit", kwargs={"pk": commission_adjustment_a.pk}), {}),
        ("POST", reverse("sales:commission_adjustment_edit", kwargs={"pk": commission_adjustment_a.pk}), {}),
        ("POST", reverse("sales:commission_adjustment_delete", kwargs={"pk": commission_adjustment_a.pk}), {}),
        ("POST", reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": commission_adjustment_a.pk}), {}),
    ]

    for method, url, data in routes:
        if method == "GET":
            resp = client.get(url)
        else:
            resp = client.post(url, data)
        assert resp.status_code == 302, f"Expected 302 redirect for {method} {url}, got {resp.status_code}"
        assert "/login" in resp["Location"], f"Expected /login redirect for {url}, got {resp['Location']}"


def test_incentivecompensation_http_method_not_allowed_on_delete_and_action_routes(
    client_a, commission_plan_a, commission_earning_a, commission_statement_a, commission_adjustment_a
):
    """GET requests to delete and state-changing action endpoints strictly return 405 Method Not Allowed."""
    routes_requiring_post = [
        reverse("sales:commission_plan_delete", kwargs={"pk": commission_plan_a.pk}),
        reverse("sales:commission_earning_delete", kwargs={"pk": commission_earning_a.pk}),
        reverse("sales:commission_statement_delete", kwargs={"pk": commission_statement_a.pk}),
        reverse("sales:commission_statement_approve", kwargs={"pk": commission_statement_a.pk}),
        reverse("sales:commission_statement_lock", kwargs={"pk": commission_statement_a.pk}),
        reverse("sales:commission_statement_generate_batch"),
        reverse("sales:commission_adjustment_delete", kwargs={"pk": commission_adjustment_a.pk}),
        reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": commission_adjustment_a.pk}),
    ]

    for url in routes_requiring_post:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET {url}, got {resp.status_code}"


# ==============================================================================
# 2. Multi-Tenant IDOR Isolation (IDOR -> 404)
# ==============================================================================


def test_incentivecompensation_idor_detail_views_return_404_for_foreign_tenant(
    client_a, member_client, commission_plan_b, commission_earning_b, commission_statement_b, commission_adjustment_b
):
    """Tenant A admin and member requesting Tenant B objects via detail views strictly return 404."""
    targets = [
        reverse("sales:commission_plan_detail", kwargs={"pk": commission_plan_b.pk}),
        reverse("sales:commission_earning_detail", kwargs={"pk": commission_earning_b.pk}),
        reverse("sales:commission_statement_detail", kwargs={"pk": commission_statement_b.pk}),
        reverse("sales:commission_adjustment_detail", kwargs={"pk": commission_adjustment_b.pk}),
    ]

    for url in targets:
        resp_admin = client_a.get(url)
        assert resp_admin.status_code == 404, f"Tenant A admin expected 404 for {url}, got {resp_admin.status_code}"

        resp_rep = member_client.get(url)
        assert resp_rep.status_code == 404, f"Tenant A rep expected 404 for {url}, got {resp_rep.status_code}"


def test_incentivecompensation_idor_edit_views_return_404_for_foreign_tenant(
    client_a, member_client, commission_plan_b, commission_earning_b, commission_statement_b, commission_adjustment_b
):
    """Tenant A admin and rep requesting Tenant B edit views (GET and POST) strictly return 404."""
    edit_targets = [
        reverse("sales:commission_plan_edit", kwargs={"pk": commission_plan_b.pk}),
        reverse("sales:commission_earning_edit", kwargs={"pk": commission_earning_b.pk}),
        reverse("sales:commission_statement_edit", kwargs={"pk": commission_statement_b.pk}),
        reverse("sales:commission_adjustment_edit", kwargs={"pk": commission_adjustment_b.pk}),
    ]

    for url in edit_targets:
        # GET
        assert client_a.get(url).status_code == 404, f"Admin GET {url} did not return 404"
        assert member_client.get(url).status_code == 404, f"Rep GET {url} did not return 404"

        # POST
        assert client_a.post(url, {"name": "Hacked", "amount": "9999"}).status_code == 404, f"Admin POST {url} did not return 404"
        assert member_client.post(url, {"name": "Hacked", "amount": "9999"}).status_code == 404, f"Rep POST {url} did not return 404"


def test_incentivecompensation_idor_delete_views_return_404_for_foreign_tenant(
    client_a, member_client, commission_plan_b, commission_earning_b, commission_statement_b, commission_adjustment_b
):
    """Tenant A users posting to delete Tenant B records strictly receive 404 (and records persist)."""
    delete_targets = [
        (reverse("sales:commission_plan_delete", kwargs={"pk": commission_plan_b.pk}), CommissionPlan, commission_plan_b.pk),
        (reverse("sales:commission_earning_delete", kwargs={"pk": commission_earning_b.pk}), CommissionEarning, commission_earning_b.pk),
        (reverse("sales:commission_statement_delete", kwargs={"pk": commission_statement_b.pk}), CommissionStatement, commission_statement_b.pk),
        (reverse("sales:commission_adjustment_delete", kwargs={"pk": commission_adjustment_b.pk}), CommissionAdjustment, commission_adjustment_b.pk),
    ]

    for url, model_cls, pk in delete_targets:
        resp = client_a.post(url)
        assert resp.status_code == 404, f"Expected 404 for delete {url}, got {resp.status_code}"
        assert model_cls.objects.filter(pk=pk).exists(), f"Foreign record {model_cls.__name__} {pk} was deleted!"


def test_incentivecompensation_idor_action_endpoints_return_404_for_foreign_tenant(
    client_a, member_client, commission_statement_b, commission_adjustment_b
):
    """Tenant A admin cannot approve, lock, or resolve disputes on Tenant B records (returns 404)."""
    approve_url = reverse("sales:commission_statement_approve", kwargs={"pk": commission_statement_b.pk})
    resp_approve = client_a.post(approve_url)
    assert resp_approve.status_code == 404

    lock_url = reverse("sales:commission_statement_lock", kwargs={"pk": commission_statement_b.pk})
    resp_lock = client_a.post(lock_url)
    assert resp_lock.status_code == 404

    dispute_url = reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": commission_adjustment_b.pk})
    resp_dispute = client_a.post(dispute_url, {"decision": "approve"})
    assert resp_dispute.status_code == 404


# ==============================================================================
# 3. Multi-Tenant List Views & Boards Leakage Prevention
# ==============================================================================


def test_incentivecompensation_list_views_never_leak_foreign_tenant_records(
    client_a,
    commission_plan_a,
    commission_plan_b,
    commission_earning_a,
    commission_earning_b,
    commission_statement_a,
    commission_statement_b,
    commission_adjustment_a,
    commission_adjustment_b,
):
    """List views for Tenant A contain Tenant A records and never leak Tenant B records."""
    # 1. Commission Plans List
    resp_plans = client_a.get(reverse("sales:commission_plan_list"))
    assert resp_plans.status_code == 200
    plan_list = list(resp_plans.context["object_list"])
    assert commission_plan_a in plan_list
    assert commission_plan_b not in plan_list

    # 2. Commission Earnings List
    resp_earnings = client_a.get(reverse("sales:commission_earning_list"))
    assert resp_earnings.status_code == 200
    earning_list = list(resp_earnings.context["object_list"])
    assert commission_earning_a in earning_list
    assert commission_earning_b not in earning_list

    # 3. Commission Statements List
    resp_stmts = client_a.get(reverse("sales:commission_statement_list"))
    assert resp_stmts.status_code == 200
    stmt_list = list(resp_stmts.context["object_list"])
    assert commission_statement_a in stmt_list
    assert commission_statement_b not in stmt_list

    # 4. Commission Adjustments List
    resp_adjs = client_a.get(reverse("sales:commission_adjustment_list"))
    assert resp_adjs.status_code == 200
    adj_list = list(resp_adjs.context["object_list"])
    assert commission_adjustment_a in adj_list
    assert commission_adjustment_b not in adj_list


def test_incentivecompensation_boards_never_leak_foreign_tenant_records(
    client_a,
    commission_plan_a,
    commission_plan_b,
    commission_earning_a,
    commission_earning_b,
    commission_adjustment_a,
    commission_adjustment_b,
):
    """All 5 derived board views scope metrics and records strictly to the active workspace."""
    # 1. Plan Hub
    resp_hub = client_a.get(reverse("sales:sales_commission_plan_hub"))
    assert resp_hub.status_code == 200
    plans = list(resp_hub.context["plans"])
    assert commission_plan_a in plans
    assert commission_plan_b not in plans

    # 2. Earnings Dashboard
    resp_dash = client_a.get(reverse("sales:sales_commission_earnings_dashboard"))
    assert resp_dash.status_code == 200
    recent = list(resp_dash.context["recent_earnings"])
    assert commission_earning_a in recent
    assert commission_earning_b not in recent

    # 3. Adjustment Workbench
    resp_wb = client_a.get(reverse("sales:sales_commission_adjustment_workbench"))
    assert resp_wb.status_code == 200
    disputes = list(resp_wb.context["active_disputes"])
    assert commission_adjustment_b not in disputes

    # 4. Global Compensation Matrix
    resp_matrix = client_a.get(reverse("sales:sales_global_compensation_matrix"))
    assert resp_matrix.status_code == 200
    reg_plans = [p for group in resp_matrix.context["regional_plans"].values() for p in group]
    assert commission_plan_a in reg_plans
    assert commission_plan_b not in reg_plans

    # 5. Payout Processing
    resp_payout = client_a.get(reverse("sales:sales_commission_payout_processing"))
    assert resp_payout.status_code == 200
    payout_plans = list(resp_payout.context["plans"])
    assert commission_plan_a in payout_plans
    assert commission_plan_b not in payout_plans


# ==============================================================================
# 4. Cross-Tenant Foreign Key Injection Defenses
# ==============================================================================


def test_incentivecompensation_fk_injection_commission_plan_rejects_foreign_fks(
    client_a, tenant_a, tenant_b, admin_b, icm_currency
):
    """CommissionPlanForm and create endpoint reject foreign tenant sales quota and owner."""
    foreign_quota = _incentivecompensation_sales_quota(tenant_b, target_amount=Decimal("300000.00"))

    # 1. Foreign sales_quota injection via form
    form_quota = CommissionPlanForm(
        data=_incentivecompensation_plan_payload(
            icm_currency,
            name="Injected Quota Plan",
            sales_quota=foreign_quota.pk,
        ),
        tenant=tenant_a,
    )
    assert not form_quota.is_valid()
    assert "sales_quota" in form_quota.errors

    # 2. Foreign owner injection via form
    form_owner = CommissionPlanForm(
        data=_incentivecompensation_plan_payload(
            icm_currency,
            name="Injected Owner Plan",
            owner=admin_b.pk,
        ),
        tenant=tenant_a,
    )
    assert not form_owner.is_valid()
    assert "owner" in form_owner.errors

    # 3. HTTP POST attempt via client_a
    resp = client_a.post(
        reverse("sales:commission_plan_create"),
        _incentivecompensation_plan_payload(
            icm_currency,
            name="HTTP Injected Plan",
            sales_quota=foreign_quota.pk,
            owner=admin_b.pk,
        ),
    )
    assert resp.status_code in (200, 400)
    assert not CommissionPlan.objects.filter(name="HTTP Injected Plan").exists()


def test_incentivecompensation_fk_injection_commission_earning_rejects_foreign_fks(
    client_a, tenant_a, tenant_b, admin_b, commission_plan_a, commission_plan_b, commission_earning_b, icm_currency
):
    """CommissionEarningForm and create endpoint reject foreign plan, payee, opportunity, order, and clawback_parent."""
    foreign_opp = _incentivecompensation_opportunity(tenant_b, name="Foreign Opp")
    foreign_order = _incentivecompensation_sales_order(tenant_b)

    # 1. Foreign plan injection
    f_plan = CommissionEarningForm(
        data=_incentivecompensation_earning_payload(commission_plan_b, admin_b, icm_currency),
        tenant=tenant_a,
    )
    assert not f_plan.is_valid()
    assert "plan" in f_plan.errors

    # 2. Foreign payee injection
    f_payee = CommissionEarningForm(
        data=_incentivecompensation_earning_payload(commission_plan_a, admin_b, icm_currency),
        tenant=tenant_a,
    )
    assert not f_payee.is_valid()
    assert "payee" in f_payee.errors

    # 3. Foreign opportunity injection
    f_opp = CommissionEarningForm(
        data=_incentivecompensation_earning_payload(
            commission_plan_a, admin_b, icm_currency, opportunity=foreign_opp.pk
        ),
        tenant=tenant_a,
    )
    assert not f_opp.is_valid()
    assert "opportunity" in f_opp.errors

    # 4. Foreign sales_order injection
    f_order = CommissionEarningForm(
        data=_incentivecompensation_earning_payload(
            commission_plan_a, admin_b, icm_currency, sales_order=foreign_order.pk
        ),
        tenant=tenant_a,
    )
    assert not f_order.is_valid()
    assert "sales_order" in f_order.errors

    # 5. Foreign clawback_parent injection
    f_parent = CommissionEarningForm(
        data=_incentivecompensation_earning_payload(
            commission_plan_a, admin_b, icm_currency, clawback_parent=commission_earning_b.pk
        ),
        tenant=tenant_a,
    )
    assert not f_parent.is_valid()
    assert "clawback_parent" in f_parent.errors

    # 6. HTTP POST attempt via client_a
    resp = client_a.post(
        reverse("sales:commission_earning_create"),
        _incentivecompensation_earning_payload(
            commission_plan_b, admin_b, icm_currency, deal_amount="99999.00"
        ),
    )
    assert resp.status_code in (200, 400)
    assert not CommissionEarning.objects.filter(deal_amount=Decimal("99999.00")).exists()


def test_incentivecompensation_fk_injection_commission_statement_rejects_foreign_fks(
    client_a, tenant_a, tenant_b, admin_b, commission_plan_a, commission_plan_b
):
    """CommissionStatementForm and create endpoint reject foreign plan and payee."""
    # 1. Foreign plan injection
    f_plan = CommissionStatementForm(
        data=_incentivecompensation_statement_payload(admin_b, commission_plan_b),
        tenant=tenant_a,
    )
    assert not f_plan.is_valid()
    assert "plan" in f_plan.errors

    # 2. Foreign payee injection
    f_payee = CommissionStatementForm(
        data=_incentivecompensation_statement_payload(admin_b, commission_plan_a),
        tenant=tenant_a,
    )
    assert not f_payee.is_valid()
    assert "payee" in f_payee.errors

    # 3. HTTP POST attempt via client_a
    resp = client_a.post(
        reverse("sales:commission_statement_create"),
        _incentivecompensation_statement_payload(admin_b, commission_plan_b, statement_number="STMT-INJECT-001"),
    )
    assert resp.status_code in (200, 400)
    assert not CommissionStatement.objects.filter(statement_number="STMT-INJECT-001").exists()


def test_incentivecompensation_fk_injection_commission_adjustment_rejects_foreign_fks(
    client_a, tenant_a, tenant_b, admin_b, commission_statement_b, commission_earning_b
):
    """CommissionAdjustmentForm and create endpoint reject foreign statement, earning, and payee."""
    # 1. Foreign statement injection
    f_stmt = CommissionAdjustmentForm(
        data=_incentivecompensation_adjustment_payload(admin_b, statement=commission_statement_b.pk),
        tenant=tenant_a,
    )
    assert not f_stmt.is_valid()
    assert "statement" in f_stmt.errors

    # 2. Foreign earning injection
    f_earn = CommissionAdjustmentForm(
        data=_incentivecompensation_adjustment_payload(admin_b, earning=commission_earning_b.pk),
        tenant=tenant_a,
    )
    assert not f_earn.is_valid()
    assert "earning" in f_earn.errors

    # 3. Foreign payee injection
    f_payee = CommissionAdjustmentForm(
        data=_incentivecompensation_adjustment_payload(admin_b),
        tenant=tenant_a,
    )
    assert not f_payee.is_valid()
    assert "payee" in f_payee.errors

    # 4. HTTP POST attempt via client_a
    resp = client_a.post(
        reverse("sales:commission_adjustment_create"),
        _incentivecompensation_adjustment_payload(
            admin_b,
            statement=commission_statement_b.pk,
            amount="777.00",
            reason="Injected Adjustment",
        ),
    )
    assert resp.status_code in (200, 400)
    assert not CommissionAdjustment.objects.filter(amount=Decimal("777.00")).exists()


def test_incentivecompensation_model_clean_rejects_cross_tenant_foreign_keys(
    tenant_a, tenant_b, admin_b, icm_currency, commission_plan_b, commission_earning_b, commission_statement_b
):
    """Direct model clean() enforcement strictly rejects cross-tenant foreign key linkages."""
    foreign_quota = _incentivecompensation_sales_quota(tenant_b)
    foreign_opp = _incentivecompensation_opportunity(tenant_b)

    # 1. CommissionPlan clean() isolation
    plan = CommissionPlan(
        tenant=tenant_a,
        name="Cross Tenant Plan",
        code="cross-plan",
        effective_start=date(2026, 1, 1),
        currency=icm_currency,
        sales_quota=foreign_quota,
    )
    with pytest.raises(ValidationError) as exc1:
        plan.clean()
    assert "sales_quota" in exc1.value.message_dict

    # 2. CommissionEarning clean() isolation
    earning = CommissionEarning(
        tenant=tenant_a,
        plan=commission_plan_b,
        payee=admin_b,
        deal_currency=icm_currency,
        earned_date=date(2026, 5, 10),
    )
    with pytest.raises(ValidationError) as exc2:
        earning.clean()
    assert "plan" in exc2.value.message_dict

    # 3. CommissionStatement clean() isolation
    stmt = CommissionStatement(
        tenant=tenant_a,
        statement_number="STMT-CLEAN-FAIL",
        payee=admin_b,
        plan=commission_plan_b,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
    )
    with pytest.raises(ValidationError) as exc3:
        stmt.clean()
    assert "payee" in exc3.value.message_dict or "plan" in exc3.value.message_dict

    # 4. CommissionAdjustment clean() isolation
    adj = CommissionAdjustment(
        tenant=tenant_a,
        payee=admin_b,
        earning=commission_earning_b,
        adjustment_type="manual_override",
        amount=Decimal("100.00"),
        effective_date=date(2026, 10, 15),
    )
    with pytest.raises(ValidationError) as exc4:
        adj.clean()
    assert "payee" in exc4.value.message_dict or "earning" in exc4.value.message_dict


# ==============================================================================
# 5. Privileged AuthZ & Self-Approval Prevention (C2, C3, C4, C9)
# ==============================================================================


def test_incentivecompensation_self_approval_prevention_on_statement_approve_c2(
    client_a, member_client, tenant_a, admin_user, member_user, commission_plan_a
):
    """Rep payee cannot approve own statement (commission_statement_approve returns 403) — regression for C2."""
    # Statement 1: Payee is member_user (regular rep)
    stmt_member = _incentivecompensation_statement(
        tenant_a, plan=commission_plan_a, payee=member_user, status="draft"
    )
    url_member = reverse("sales:commission_statement_approve", kwargs={"pk": stmt_member.pk})

    # Rep member attempts self-approval -> 403 Forbidden
    resp_rep = member_client.post(url_member)
    assert resp_rep.status_code == 403
    stmt_member.refresh_from_db()
    assert stmt_member.status == "draft"

    # Statement 2: Payee is admin_user (admin rep)
    stmt_admin = _incentivecompensation_statement(
        tenant_a, plan=commission_plan_a, payee=admin_user, status="draft"
    )
    url_admin = reverse("sales:commission_statement_approve", kwargs={"pk": stmt_admin.pk})

    # Admin user who is ALSO the payee attempts self-approval -> strictly 403 Forbidden
    resp_self_admin = client_a.post(url_admin)
    assert resp_self_admin.status_code == 403
    stmt_admin.refresh_from_db()
    assert stmt_admin.status == "draft"

    # Separate non-payee admin approves member statement -> succeeds (302)
    resp_approved = client_a.post(url_member)
    assert resp_approved.status_code == 302
    stmt_member.refresh_from_db()
    assert stmt_member.status == "approved"
    assert stmt_member.approved_by == admin_user


def test_incentivecompensation_privileged_authz_statement_lock_c3(
    client_a, member_client, tenant_a, admin_user, member_user, commission_plan_a
):
    """Non-admin or payee cannot lock statement (commission_statement_lock returns 403) — regression for C3."""
    # 1. Statement where payee is member_user, already approved
    stmt_member = _incentivecompensation_statement(
        tenant_a, plan=commission_plan_a, payee=member_user, status="approved"
    )
    url_member = reverse("sales:commission_statement_lock", kwargs={"pk": stmt_member.pk})

    # Non-admin regular rep attempts lock -> 403 Forbidden
    resp_rep = member_client.post(url_member)
    assert resp_rep.status_code == 403
    stmt_member.refresh_from_db()
    assert stmt_member.status == "approved"

    # 2. Statement where payee is admin_user, already approved
    stmt_admin = _incentivecompensation_statement(
        tenant_a, plan=commission_plan_a, payee=admin_user, status="approved"
    )
    url_admin = reverse("sales:commission_statement_lock", kwargs={"pk": stmt_admin.pk})

    # Admin user who is payee attempts to lock own statement -> strictly 403 Forbidden
    resp_self_admin = client_a.post(url_admin)
    assert resp_self_admin.status_code == 403
    stmt_admin.refresh_from_db()
    assert stmt_admin.status == "approved"

    # 3. Non-payee admin locks the approved member statement -> succeeds (302)
    resp_lock_success = client_a.post(url_member)
    assert resp_lock_success.status_code == 302
    stmt_member.refresh_from_db()
    assert stmt_member.status == "locked"
    assert stmt_member.locked_at is not None


def test_incentivecompensation_dispute_resolution_self_resolution_prevention_c4(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Rep payee or claimant cannot resolve own dispute (resolve_dispute returns 403) — regression for C4."""
    # Create a secondary admin who is neutral
    second_admin = _incentivecompensation_create_user(tenant_a, "second_admin", is_admin=True)
    second_admin_client = Client()
    second_admin_client.force_login(second_admin)

    # 1. Dispute where payee is member_user and claimant is member_user
    dispute_rep = _incentivecompensation_adjustment(
        tenant_a,
        payee=member_user,
        requested_by=member_user,
        status="disputed",
        dispute_comments="Rep claim: deal credit split was omitted.",
    )
    url_rep = reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": dispute_rep.pk})

    # Member user (non-admin) attempts dispute resolution -> 403 Forbidden
    resp_member = member_client.post(url_rep, {"decision": "approve"})
    assert resp_member.status_code == 403
    dispute_rep.refresh_from_db()
    assert dispute_rep.status == "disputed"

    # 2. Dispute where admin_user is the payee
    dispute_admin_payee = _incentivecompensation_adjustment(
        tenant_a,
        payee=admin_user,
        requested_by=member_user,
        status="disputed",
        dispute_comments="Admin rep commission disagreement.",
    )
    url_admin_payee = reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": dispute_admin_payee.pk})

    # admin_user cannot resolve because they are the payee -> 403 Forbidden
    resp_admin_payee = client_a.post(url_admin_payee, {"decision": "approve"})
    assert resp_admin_payee.status_code == 403
    dispute_admin_payee.refresh_from_db()
    assert dispute_admin_payee.status == "disputed"

    # 3. Dispute where admin_user is the requested_by (claimant)
    dispute_admin_claimant = _incentivecompensation_adjustment(
        tenant_a,
        payee=member_user,
        requested_by=admin_user,
        status="disputed",
        dispute_comments="Claimant admin dispute.",
    )
    url_admin_claimant = reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": dispute_admin_claimant.pk})

    # admin_user cannot resolve because they are requested_by -> 403 Forbidden
    resp_admin_claimant = client_a.post(url_admin_claimant, {"decision": "reject"})
    assert resp_admin_claimant.status_code == 403
    dispute_admin_claimant.refresh_from_db()
    assert dispute_admin_claimant.status == "disputed"

    # 4. Neutral uninvolved admin (second_admin) CAN resolve the dispute -> succeeds (302)
    resp_neutral = second_admin_client.post(url_admin_payee, {"decision": "approve", "resolution_notes": "Settled."})
    assert resp_neutral.status_code == 302
    dispute_admin_payee.refresh_from_db()
    assert dispute_admin_payee.status == "approved"
    assert dispute_admin_payee.approved_by == second_admin


def test_incentivecompensation_batch_generation_non_admin_forbidden_c9(
    client_a, member_client, tenant_a, commission_plan_a
):
    """Non-admin cannot execute batch generation (returns 403) — regression for C9."""
    url = reverse("sales:commission_statement_generate_batch")
    batch_payload = {
        "period_start": "2026-11-01",
        "period_end": "2026-11-30",
        "plan_id": str(commission_plan_a.pk),
    }

    # Regular sales rep attempts batch generation -> 403 Forbidden
    resp_rep = member_client.post(url, batch_payload)
    assert resp_rep.status_code == 403

    # Tenant admin executes batch generation -> succeeds (302 redirect)
    resp_admin = client_a.post(url, batch_payload)
    assert resp_admin.status_code == 302
    assert resp_admin["Location"] == reverse("sales:commission_statement_list")


# ==============================================================================
# 6. Horizontal Data Privacy (I8)
# ==============================================================================


def test_incentivecompensation_horizontal_privacy_rep_only_views_own_earnings(
    client_a, member_client, tenant_a, admin_user, member_user, commission_plan_a, icm_currency
):
    """Regular sales rep can only view their own earnings in list and detail views."""
    earning_member = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        currency=icm_currency,
        deal_amount=Decimal("45000.00"),
    )
    earning_other = _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=admin_user,
        currency=icm_currency,
        deal_amount=Decimal("95000.00"),
    )

    # List view isolation: member rep sees earning_member, NOT earning_other
    resp_list = member_client.get(reverse("sales:commission_earning_list"))
    assert resp_list.status_code == 200
    object_list = list(resp_list.context["object_list"])
    assert earning_member in object_list
    assert earning_other not in object_list

    # Admin list view sees both
    resp_admin_list = client_a.get(reverse("sales:commission_earning_list"))
    admin_list = list(resp_admin_list.context["object_list"])
    assert earning_member in admin_list
    assert earning_other in admin_list

    # Detail view isolation: member rep views own earning -> 200
    resp_own_detail = member_client.get(
        reverse("sales:commission_earning_detail", kwargs={"pk": earning_member.pk})
    )
    assert resp_own_detail.status_code == 200

    # Detail view isolation: member rep requests other rep's earning -> 404
    resp_other_detail = member_client.get(
        reverse("sales:commission_earning_detail", kwargs={"pk": earning_other.pk})
    )
    assert resp_other_detail.status_code == 404


def test_incentivecompensation_horizontal_privacy_rep_only_views_own_statements(
    client_a, member_client, tenant_a, admin_user, member_user, commission_plan_a
):
    """Regular sales rep can only view their own statements in list and detail views."""
    stmt_member = _incentivecompensation_statement(
        tenant_a, plan=commission_plan_a, payee=member_user
    )
    stmt_other = _incentivecompensation_statement(
        tenant_a, plan=commission_plan_a, payee=admin_user
    )

    # List view isolation: member rep sees stmt_member, NOT stmt_other
    resp_list = member_client.get(reverse("sales:commission_statement_list"))
    assert resp_list.status_code == 200
    object_list = list(resp_list.context["object_list"])
    assert stmt_member in object_list
    assert stmt_other not in object_list

    # Admin list view sees both
    resp_admin = client_a.get(reverse("sales:commission_statement_list"))
    admin_list = list(resp_admin.context["object_list"])
    assert stmt_member in admin_list
    assert stmt_other in admin_list

    # Detail view isolation: member rep views own statement -> 200
    resp_own = member_client.get(
        reverse("sales:commission_statement_detail", kwargs={"pk": stmt_member.pk})
    )
    assert resp_own.status_code == 200

    # Detail view isolation: member rep requests other rep's statement -> 404
    resp_other = member_client.get(
        reverse("sales:commission_statement_detail", kwargs={"pk": stmt_other.pk})
    )
    assert resp_other.status_code == 404


def test_incentivecompensation_horizontal_privacy_rep_only_views_own_adjustments(
    client_a, member_client, tenant_a, admin_user, member_user
):
    """Regular sales rep can only view their own adjustments in list and detail views."""
    adj_member = _incentivecompensation_adjustment(tenant_a, payee=member_user, amount=Decimal("150.00"))
    adj_other = _incentivecompensation_adjustment(tenant_a, payee=admin_user, amount=Decimal("250.00"))

    # List view isolation
    resp_list = member_client.get(reverse("sales:commission_adjustment_list"))
    assert resp_list.status_code == 200
    adj_list = list(resp_list.context["object_list"])
    assert adj_member in adj_list
    assert adj_other not in adj_list

    # Detail view isolation
    assert member_client.get(reverse("sales:commission_adjustment_detail", kwargs={"pk": adj_member.pk})).status_code == 200
    assert member_client.get(reverse("sales:commission_adjustment_detail", kwargs={"pk": adj_other.pk})).status_code == 404


def test_incentivecompensation_horizontal_privacy_rep_cannot_edit_or_mutate_other_rep_records(
    member_client, tenant_a, admin_user, commission_plan_a, icm_currency
):
    """Regular rep cannot edit or mutate another rep's earning or statement (returns 404 or 403)."""
    other_earning = _incentivecompensation_earning(
        tenant_a, plan=commission_plan_a, payee=admin_user, currency=icm_currency
    )
    other_stmt = _incentivecompensation_statement(
        tenant_a, plan=commission_plan_a, payee=admin_user
    )
    other_adj = _incentivecompensation_adjustment(
        tenant_a, payee=admin_user
    )

    # 1. Edit another rep's earning -> 404
    earn_edit_url = reverse("sales:commission_earning_edit", kwargs={"pk": other_earning.pk})
    assert member_client.get(earn_edit_url).status_code == 404
    assert member_client.post(earn_edit_url, {"deal_amount": "10.00"}).status_code == 404

    # 2. Delete another rep's earning -> 403 Forbidden
    earn_del_url = reverse("sales:commission_earning_delete", kwargs={"pk": other_earning.pk})
    assert member_client.post(earn_del_url).status_code == 403
    assert CommissionEarning.objects.filter(pk=other_earning.pk).exists()

    # 3. Edit another rep's statement -> 404
    stmt_edit_url = reverse("sales:commission_statement_edit", kwargs={"pk": other_stmt.pk})
    assert member_client.get(stmt_edit_url).status_code == 404
    assert member_client.post(stmt_edit_url, {"notes": "Tampered"}).status_code == 404

    # 4. Delete another rep's statement -> 403 Forbidden
    stmt_del_url = reverse("sales:commission_statement_delete", kwargs={"pk": other_stmt.pk})
    assert member_client.post(stmt_del_url).status_code == 403
    assert CommissionStatement.objects.filter(pk=other_stmt.pk).exists()

    # 5. Delete another rep's adjustment -> 403 Forbidden
    adj_del_url = reverse("sales:commission_adjustment_delete", kwargs={"pk": other_adj.pk})
    assert member_client.post(adj_del_url).status_code == 403
    assert CommissionAdjustment.objects.filter(pk=other_adj.pk).exists()

    # 6. Delete commission plan -> 403 Forbidden
    plan_del_url = reverse("sales:commission_plan_delete", kwargs={"pk": commission_plan_a.pk})
    assert member_client.post(plan_del_url).status_code == 403
    assert CommissionPlan.objects.filter(pk=commission_plan_a.pk).exists()


# ==============================================================================
# 7. Mass Assignment Protection (C5)
# ==============================================================================


def test_incentivecompensation_mass_assignment_protection_earning_status_c5(
    client_a, commission_plan_a, member_user, icm_currency
):
    """Submitting status='approved' or status='paid' on earning forms does not bypass workflow states."""
    # 1. Create: status parameter in POST payload is ignored
    payload_create = _incentivecompensation_earning_payload(
        commission_plan_a,
        member_user,
        icm_currency,
        deal_amount="75000.00",
        status="paid",  # Mass-assignment attempt
    )
    resp_create = client_a.post(reverse("sales:commission_earning_create"), payload_create)
    assert resp_create.status_code == 302

    created_earning = CommissionEarning.objects.get(deal_amount=Decimal("75000.00"))
    assert created_earning.status == "calculated", "Mass assignment vulnerability: earning created directly as 'paid'!"

    # 2. Edit: status parameter in POST payload cannot force transition to 'paid'
    payload_edit = _incentivecompensation_earning_payload(
        commission_plan_a,
        member_user,
        icm_currency,
        deal_amount="76000.00",
        status="approved",  # Mass-assignment attempt
    )
    resp_edit = client_a.post(
        reverse("sales:commission_earning_edit", kwargs={"pk": created_earning.pk}), payload_edit
    )
    assert resp_edit.status_code == 302

    created_earning.refresh_from_db()
    assert created_earning.status == "calculated", "Mass assignment vulnerability: earning edited directly to 'approved'!"


def test_incentivecompensation_mass_assignment_protection_statement_status_c5(
    client_a, commission_plan_a, member_user
):
    """Submitting status='approved' or status='locked' on statement forms does not bypass workflow states."""
    # 1. Create: status parameter in POST payload is ignored
    payload_create = _incentivecompensation_statement_payload(
        member_user,
        commission_plan_a,
        statement_number="STMT-MASS-01",
        status="locked",  # Mass-assignment attempt
    )
    resp_create = client_a.post(reverse("sales:commission_statement_create"), payload_create)
    assert resp_create.status_code == 302

    created_stmt = CommissionStatement.objects.get(statement_number="STMT-MASS-01")
    assert created_stmt.status == "draft", "Mass assignment vulnerability: statement created directly as 'locked'!"

    # 2. Edit: status parameter in POST payload cannot force transition to 'approved'
    payload_edit = _incentivecompensation_statement_payload(
        member_user,
        commission_plan_a,
        statement_number="STMT-MASS-01",
        status="approved",  # Mass-assignment attempt
    )
    resp_edit = client_a.post(
        reverse("sales:commission_statement_edit", kwargs={"pk": created_stmt.pk}), payload_edit
    )
    assert resp_edit.status_code == 302

    created_stmt.refresh_from_db()
    assert created_stmt.status == "draft", "Mass assignment vulnerability: statement edited directly to 'approved'!"


def test_incentivecompensation_mass_assignment_protection_adjustment_status_c5(
    client_a, member_user
):
    """Submitting status='approved' or status='applied' on adjustment forms does not bypass workflow states."""
    # 1. Create: status parameter in POST payload is ignored
    payload_create = _incentivecompensation_adjustment_payload(
        member_user,
        amount="888.00",
        status="applied",  # Mass-assignment attempt
    )
    resp_create = client_a.post(reverse("sales:commission_adjustment_create"), payload_create)
    assert resp_create.status_code == 302

    created_adj = CommissionAdjustment.objects.get(amount=Decimal("888.00"))
    assert created_adj.status == "draft", "Mass assignment vulnerability: adjustment created directly as 'applied'!"

    # 2. Edit: status parameter in POST payload cannot force transition to 'approved'
    payload_edit = _incentivecompensation_adjustment_payload(
        member_user,
        amount="889.00",
        status="approved",  # Mass-assignment attempt
    )
    resp_edit = client_a.post(
        reverse("sales:commission_adjustment_edit", kwargs={"pk": created_adj.pk}), payload_edit
    )
    assert resp_edit.status_code == 302

    created_adj.refresh_from_db()
    assert created_adj.status == "draft", "Mass assignment vulnerability: adjustment edited directly to 'approved'!"


# ==============================================================================
# 8. CSRF Protection
# ==============================================================================


def test_incentivecompensation_csrf_enforced_on_create_and_edit_endpoints(
    admin_user, commission_plan_a, commission_earning_a, commission_statement_a, commission_adjustment_a
):
    """Every create and edit form POST route strictly requires a valid CSRF token."""
    csrf_client = _incentivecompensation_csrf_client(admin_user)

    routes = [
        reverse("sales:commission_plan_create"),
        reverse("sales:commission_plan_edit", kwargs={"pk": commission_plan_a.pk}),
        reverse("sales:commission_earning_create"),
        reverse("sales:commission_earning_edit", kwargs={"pk": commission_earning_a.pk}),
        reverse("sales:commission_statement_create"),
        reverse("sales:commission_statement_edit", kwargs={"pk": commission_statement_a.pk}),
        reverse("sales:commission_adjustment_create"),
        reverse("sales:commission_adjustment_edit", kwargs={"pk": commission_adjustment_a.pk}),
    ]

    for url in routes:
        resp = csrf_client.post(url, {"name": "CSRF Attack", "amount": "100.00"})
        assert resp.status_code == 403, f"Expected 403 CSRF Forbidden for POST {url}, got {resp.status_code}"


def test_incentivecompensation_csrf_enforced_on_delete_endpoints(
    admin_user, commission_plan_a, commission_earning_a, commission_statement_a, commission_adjustment_a
):
    """Every delete POST endpoint strictly requires a valid CSRF token."""
    csrf_client = _incentivecompensation_csrf_client(admin_user)

    routes = [
        reverse("sales:commission_plan_delete", kwargs={"pk": commission_plan_a.pk}),
        reverse("sales:commission_earning_delete", kwargs={"pk": commission_earning_a.pk}),
        reverse("sales:commission_statement_delete", kwargs={"pk": commission_statement_a.pk}),
        reverse("sales:commission_adjustment_delete", kwargs={"pk": commission_adjustment_a.pk}),
    ]

    for url in routes:
        resp = csrf_client.post(url, {})
        assert resp.status_code == 403, f"Expected 403 CSRF Forbidden for POST {url}, got {resp.status_code}"


def test_incentivecompensation_csrf_enforced_on_action_endpoints(
    admin_user, commission_statement_a, commission_adjustment_a
):
    """Custom action POST routes strictly require a valid CSRF token."""
    csrf_client = _incentivecompensation_csrf_client(admin_user)

    routes = [
        reverse("sales:commission_statement_approve", kwargs={"pk": commission_statement_a.pk}),
        reverse("sales:commission_statement_lock", kwargs={"pk": commission_statement_a.pk}),
        reverse("sales:commission_statement_generate_batch"),
        reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": commission_adjustment_a.pk}),
    ]

    for url in routes:
        resp = csrf_client.post(url, {"decision": "approve"})
        assert resp.status_code == 403, f"Expected 403 CSRF Forbidden for POST {url}, got {resp.status_code}"


# ==============================================================================
# 9. Audit Logging Contracts (C1)
# ==============================================================================


def test_incentivecompensation_audit_logging_commission_plan_lifecycle(client_a, tenant_a, icm_currency):
    """CommissionPlan create, edit, and delete operations write valid AuditLog entries without crashing."""
    plan_ct = ContentType.objects.get_for_model(CommissionPlan)

    # 1. Create Plan
    payload_create = _incentivecompensation_plan_payload(icm_currency, name="Audited Plan")
    resp_create = client_a.post(reverse("sales:commission_plan_create"), payload_create)
    assert resp_create.status_code == 302

    plan = CommissionPlan.objects.get(name="Audited Plan")
    create_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=plan_ct,
        object_id=plan.pk,
        action="create",
    ).first()
    assert create_log is not None, "AuditLog entry missing for CommissionPlan create"
    assert create_log.changes.get("name") == "Audited Plan"

    # 2. Edit Plan
    payload_edit = _incentivecompensation_plan_payload(icm_currency, name="Audited Plan Updated")
    resp_edit = client_a.post(reverse("sales:commission_plan_edit", kwargs={"pk": plan.pk}), payload_edit)
    assert resp_edit.status_code == 302

    update_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=plan_ct,
        object_id=plan.pk,
        action="update",
    ).first()
    assert update_log is not None, "AuditLog entry missing for CommissionPlan update"
    assert update_log.changes.get("name") == "Audited Plan Updated"

    # 3. Delete Plan
    resp_del = client_a.post(reverse("sales:commission_plan_delete", kwargs={"pk": plan.pk}))
    assert resp_del.status_code == 302

    delete_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=plan_ct,
        object_id=plan.pk,
        action="delete",
    ).first()
    assert delete_log is not None, "AuditLog entry missing for CommissionPlan delete"
    assert not CommissionPlan.objects.filter(pk=plan.pk).exists()


def test_incentivecompensation_audit_logging_commission_earning_lifecycle(
    client_a, tenant_a, commission_plan_a, member_user, icm_currency
):
    """CommissionEarning create, edit, and delete operations write valid AuditLog entries without crashing."""
    earning_ct = ContentType.objects.get_for_model(CommissionEarning)

    # 1. Create Earning
    payload_create = _incentivecompensation_earning_payload(
        commission_plan_a, member_user, icm_currency, deal_amount="55500.00"
    )
    resp_create = client_a.post(reverse("sales:commission_earning_create"), payload_create)
    assert resp_create.status_code == 302

    earning = CommissionEarning.objects.get(deal_amount=Decimal("55500.00"))
    create_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=earning_ct,
        object_id=earning.pk,
        action="create",
    ).first()
    assert create_log is not None, "AuditLog entry missing for CommissionEarning create"
    assert "gross" in create_log.changes

    # 2. Edit Earning
    payload_edit = _incentivecompensation_earning_payload(
        commission_plan_a, member_user, icm_currency, deal_amount="58000.00"
    )
    resp_edit = client_a.post(reverse("sales:commission_earning_edit", kwargs={"pk": earning.pk}), payload_edit)
    assert resp_edit.status_code == 302

    update_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=earning_ct,
        object_id=earning.pk,
        action="update",
    ).first()
    assert update_log is not None, "AuditLog entry missing for CommissionEarning update"

    # 3. Delete Earning
    resp_del = client_a.post(reverse("sales:commission_earning_delete", kwargs={"pk": earning.pk}))
    assert resp_del.status_code == 302

    delete_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=earning_ct,
        object_id=earning.pk,
        action="delete",
    ).first()
    assert delete_log is not None, "AuditLog entry missing for CommissionEarning delete"
    assert not CommissionEarning.objects.filter(pk=earning.pk).exists()


def test_incentivecompensation_audit_logging_commission_statement_lifecycle_and_actions(
    client_a, tenant_a, commission_plan_a, member_user
):
    """CommissionStatement create, edit, approve, lock, and delete operations write valid AuditLog entries."""
    stmt_ct = ContentType.objects.get_for_model(CommissionStatement)

    # 1. Create Statement
    payload_create = _incentivecompensation_statement_payload(
        member_user, commission_plan_a, statement_number="STMT-AUDIT-01"
    )
    resp_create = client_a.post(reverse("sales:commission_statement_create"), payload_create)
    assert resp_create.status_code == 302

    stmt = CommissionStatement.objects.get(statement_number="STMT-AUDIT-01")
    create_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=stmt_ct,
        object_id=stmt.pk,
        action="create",
    ).first()
    assert create_log is not None, "AuditLog missing for statement create"

    # 2. Edit Statement
    payload_edit = _incentivecompensation_statement_payload(
        member_user, commission_plan_a, statement_number="STMT-AUDIT-01", notes="Updated notes"
    )
    resp_edit = client_a.post(reverse("sales:commission_statement_edit", kwargs={"pk": stmt.pk}), payload_edit)
    assert resp_edit.status_code == 302

    edit_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=stmt_ct,
        object_id=stmt.pk,
        action="update",
        changes__statement_number="STMT-AUDIT-01",
    ).first()
    assert edit_log is not None, "AuditLog missing for statement edit"

    # 3. Approve Statement
    resp_approve = client_a.post(reverse("sales:commission_statement_approve", kwargs={"pk": stmt.pk}))
    assert resp_approve.status_code == 302

    approve_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=stmt_ct,
        object_id=stmt.pk,
        action="update",
        changes__action="approve",
    ).first()
    assert approve_log is not None, "AuditLog missing for statement approve"

    # 4. Lock Statement
    resp_lock = client_a.post(reverse("sales:commission_statement_lock", kwargs={"pk": stmt.pk}))
    assert resp_lock.status_code == 302

    lock_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=stmt_ct,
        object_id=stmt.pk,
        action="update",
        changes__action="lock",
    ).first()
    assert lock_log is not None, "AuditLog missing for statement lock"

    # 5. Delete Statement (create fresh draft statement to test delete audit)
    del_stmt = _incentivecompensation_statement(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        statement_number="STMT-AUDIT-DEL",
        period_start=date(2026, 8, 1),
        period_end=date(2026, 8, 31),
        status="draft",
    )
    resp_del = client_a.post(reverse("sales:commission_statement_delete", kwargs={"pk": del_stmt.pk}))
    assert resp_del.status_code == 302

    del_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=stmt_ct,
        object_id=del_stmt.pk,
        action="delete",
    ).first()
    assert del_log is not None, "AuditLog missing for statement delete"
    assert not CommissionStatement.objects.filter(pk=del_stmt.pk).exists()


def test_incentivecompensation_audit_logging_statement_batch_generation(
    client_a, tenant_a, commission_plan_a, member_user, icm_currency
):
    """Batch statement generation writes a valid AuditLog entry detailing created count and parameters."""
    # Ensure unattached earning exists in target period
    _incentivecompensation_earning(
        tenant_a,
        plan=commission_plan_a,
        payee=member_user,
        currency=icm_currency,
        deal_amount=Decimal("50000.00"),
        earned_date=date(2026, 12, 10),
    )

    url = reverse("sales:commission_statement_generate_batch")
    batch_payload = {
        "period_start": "2026-12-01",
        "period_end": "2026-12-31",
        "plan_id": str(commission_plan_a.pk),
    }

    resp = client_a.post(url, batch_payload)
    assert resp.status_code == 302

    batch_log = AuditLog.objects.filter(
        tenant=tenant_a,
        action="create",
        changes__action="batch_generate_statements",
    ).order_by("-at").first()

    assert batch_log is not None, "AuditLog entry missing for batch statement generation"
    assert batch_log.changes.get("plan_id") == commission_plan_a.pk
    assert batch_log.changes.get("created_count") >= 1


def test_incentivecompensation_audit_logging_commission_adjustment_lifecycle_and_dispute(
    client_a, tenant_a, member_user, admin_user
):
    """CommissionAdjustment create, edit, dispute resolution, and delete operations write valid AuditLog entries."""
    adj_ct = ContentType.objects.get_for_model(CommissionAdjustment)

    # 1. Create Adjustment
    payload_create = _incentivecompensation_adjustment_payload(member_user, amount="420.00")
    resp_create = client_a.post(reverse("sales:commission_adjustment_create"), payload_create)
    assert resp_create.status_code == 302

    adj = CommissionAdjustment.objects.get(amount=Decimal("420.00"))
    create_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=adj_ct,
        object_id=adj.pk,
        action="create",
    ).first()
    assert create_log is not None, "AuditLog missing for adjustment create"

    # 2. Edit Adjustment
    payload_edit = _incentivecompensation_adjustment_payload(member_user, amount="450.00")
    resp_edit = client_a.post(reverse("sales:commission_adjustment_edit", kwargs={"pk": adj.pk}), payload_edit)
    assert resp_edit.status_code == 302

    edit_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=adj_ct,
        object_id=adj.pk,
        action="update",
        changes__amount="450.00",
    ).first()
    assert edit_log is not None, "AuditLog missing for adjustment edit"

    # 3. Resolve Dispute on Adjustment
    # Set status to disputed and requested_by to member_user so admin_user can resolve
    adj.status = "disputed"
    adj.requested_by = member_user
    adj.save()

    resolve_url = reverse("sales:commission_adjustment_resolve_dispute", kwargs={"pk": adj.pk})
    resp_resolve = client_a.post(resolve_url, {"decision": "approve", "resolution_notes": "Claim verified."})
    assert resp_resolve.status_code == 302

    dispute_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=adj_ct,
        object_id=adj.pk,
        action="update",
        changes__action="dispute_approve",
    ).first()
    assert dispute_log is not None, "AuditLog missing for dispute resolution"
    assert dispute_log.changes.get("notes") == "Claim verified."

    # 4. Delete Adjustment (create a separate draft adjustment to delete)
    del_adj = _incentivecompensation_adjustment(tenant_a, payee=member_user, status="draft", amount=Decimal("111.00"))
    resp_del = client_a.post(reverse("sales:commission_adjustment_delete", kwargs={"pk": del_adj.pk}))
    assert resp_del.status_code == 302

    del_log = AuditLog.objects.filter(
        tenant=tenant_a,
        content_type=adj_ct,
        object_id=del_adj.pk,
        action="delete",
    ).first()
    assert del_log is not None, "AuditLog missing for adjustment delete"
    assert not CommissionAdjustment.objects.filter(pk=del_adj.pk).exists()
