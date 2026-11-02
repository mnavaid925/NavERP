"""Unit, route, context-contract, filter, and action tests for eCommerce 9.18 Fraud & Risk Management views.

Covers:
1. fraud_risk_hub: status 200, context variables present, KPI cards populated, tenant isolation.
2. FraudRule views: list (filtering, search, pagination), create (GET form, POST valid), detail (context variable rule),
   edit (GET form, POST update), delete (POST-only deletes object, GET rejected 405), IDOR 404.
3. TransactionRiskAssessment views: list (tier, decision, action filters, search, pagination), create, detail (context
   variable assessment), edit, delete (POST-only), IDOR 404.
4. ChargebackDispute views: list (stage, reason filters, search, pagination), create, detail (context variable dispute),
   edit, delete (POST-only), IDOR 404.
5. AccountSecurityAlert views: list (type, severity, status filters, search, pagination), create, detail (context
   variable alert), edit, delete (POST-only), IDOR 404.
6. Verify mutation endpoints execute write_audit_log successfully without TypeError (C1).

Conventions enforced:
- Test functions: test_fraudrisk_*
- Local helpers: _fraudrisk_*
"""
from decimal import Decimal
import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models import AuditLog, Party
from apps.ecommerce.models import (
    FraudRule,
    TransactionRiskAssessment,
    ChargebackDispute,
    AccountSecurityAlert,
    EcommerceOrder,
)
from apps.ecommerce.tests.conftest import (
    _fraudrisk_fraud_rule,
    _fraudrisk_transaction_risk_assessment,
    _fraudrisk_chargeback_dispute,
    _fraudrisk_account_security_alert,
    _ordermanagement_order,
)


pytestmark = pytest.mark.django_db


def _fraudrisk_get_currency_usd():
    """Local helper to fetch or create active USD currency."""
    currency = Currency.objects.filter(code="USD").first()
    if not currency:
        currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$", is_active=True)
    return currency


def _fraudrisk_create_order(tenant, party=None, currency=None):
    """Local helper to create an eCommerce order for tenant."""
    if currency is None:
        currency = _fraudrisk_get_currency_usd()
    if party is None:
        party = Party.objects.create(tenant=tenant, name="Test Customer")
    return _ordermanagement_order(tenant, customer=party, currency=currency)


# ==============================================================================
# 1. Fraud & Risk Hub Cockpit Tests
# ==============================================================================

def test_fraudrisk_hub_view(
    auth_client_a,
    tenant_a,
    ecom_fraud_rule_a,
    ecom_risk_assessment_a,
    ecom_chargeback_dispute_a,
    ecom_security_alert_a,
):
    """Test fraud risk cockpit hub returns 200 with all KPI counts and recent activity lists."""
    url = reverse("ecommerce:fraud_risk_hub")
    response = auth_client_a.get(url)
    assert response.status_code == 200

    expected_context_keys = [
        "total_rules",
        "active_rules",
        "total_assessments",
        "high_risk_assessments",
        "pending_reviews",
        "total_disputes",
        "open_disputes",
        "dispute_amount_total",
        "total_alerts",
        "open_alerts",
        "critical_alerts",
        "recent_assessments",
        "recent_disputes",
        "recent_alerts",
    ]
    for key in expected_context_keys:
        assert key in response.context, f"Missing expected hub context key: {key}"

    assert response.context["total_rules"] >= 1
    assert response.context["total_assessments"] >= 1
    assert response.context["total_disputes"] >= 1
    assert response.context["total_alerts"] >= 1
    assert len(response.context["recent_assessments"]) >= 1
    assert len(response.context["recent_disputes"]) >= 1
    assert len(response.context["recent_alerts"]) >= 1


def test_fraudrisk_hub_tenant_isolation(
    auth_client_a,
    tenant_a,
    tenant_b,
    ecom_fraud_rule_b,
    ecom_risk_assessment_b,
    ecom_chargeback_dispute_b,
    ecom_security_alert_b,
):
    """Test that Tenant A's hub view does not aggregate Tenant B's data."""
    url = reverse("ecommerce:fraud_risk_hub")
    response = auth_client_a.get(url)
    assert response.status_code == 200

    # Ensure Tenant B objects are excluded from recent lists for Tenant A
    for assessment in response.context["recent_assessments"]:
        assert assessment.tenant == tenant_a
    for dispute in response.context["recent_disputes"]:
        assert dispute.tenant == tenant_a
    for alert in response.context["recent_alerts"]:
        assert alert.tenant == tenant_a


# ==============================================================================
# 2. FraudRule Views Tests
# ==============================================================================

def test_fraudrisk_rule_list_view_and_filters(auth_client_a, tenant_a, ecom_fraud_rule_a):
    """Test FraudRule list view context contract, choices, and GET filter parameters."""
    url = reverse("ecommerce:fraud_rule_list")
    response = auth_client_a.get(url)
    assert response.status_code == 200

    expected_context_keys = [
        "rules",
        "page_obj",
        "paginator",
        "is_paginated",
        "total_count",
        "active_count",
        "search_query",
        "scope_filter",
        "type_filter",
        "action_filter",
        "is_active_filter",
        "scope_choices",
        "type_choices",
        "action_choices",
    ]
    for key in expected_context_keys:
        assert key in response.context, f"Missing list context key: {key}"

    assert response.context["total_count"] >= 1
    assert len(response.context["rules"]) >= 1

    # Filter by scope
    res_scope = auth_client_a.get(url, {"scope": "checkout"})
    assert res_scope.status_code == 200
    assert len(res_scope.context["rules"]) >= 1

    # Filter by type
    res_type = auth_client_a.get(url, {"type": "velocity_orders"})
    assert res_type.status_code == 200
    assert len(res_type.context["rules"]) >= 1

    # Filter by action
    res_action = auth_client_a.get(url, {"action": "flag_review"})
    assert res_action.status_code == 200
    assert len(res_action.context["rules"]) >= 1

    # Filter by is_active ("1" and "0")
    res_active = auth_client_a.get(url, {"is_active": "1"})
    assert res_active.status_code == 200
    assert len(res_active.context["rules"]) >= 1

    res_inactive = auth_client_a.get(url, {"is_active": "0"})
    assert res_inactive.status_code == 200
    assert len(res_inactive.context["rules"]) == 0

    # Search query
    res_search = auth_client_a.get(url, {"q": "R-VEL-01"})
    assert res_search.status_code == 200
    assert len(res_search.context["rules"]) >= 1

    res_search_empty = auth_client_a.get(url, {"q": "NONEXISTENT_RULE_QUERY"})
    assert res_search_empty.status_code == 200
    assert len(res_search_empty.context["rules"]) == 0


def test_fraudrisk_rule_list_pagination(auth_client_a, tenant_a):
    """Test pagination when FraudRule records exceed page size of 15."""
    for i in range(16):
        _fraudrisk_fraud_rule(
            tenant_a,
            name=f"Paginated Rule {i:02d}",
            rule_code=f"R-PAG-{i:02d}",
        )
    url = reverse("ecommerce:fraud_rule_list")
    res_p1 = auth_client_a.get(url)
    assert res_p1.status_code == 200
    assert res_p1.context["is_paginated"] is True
    assert len(res_p1.context["rules"]) == 15

    res_p2 = auth_client_a.get(url, {"page": 2})
    assert res_p2.status_code == 200
    assert len(res_p2.context["rules"]) >= 1


def test_fraudrisk_rule_detail_view(auth_client_a, tenant_a, ecom_fraud_rule_a):
    """Test FraudRule detail view returns 200 with rule context variable."""
    url = reverse("ecommerce:fraud_rule_detail", kwargs={"pk": ecom_fraud_rule_a.pk})
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "rule" in response.context
    assert response.context["rule"] == ecom_fraud_rule_a


def test_fraudrisk_rule_create_view(auth_client_a, tenant_a):
    """Test FraudRule create GET form and valid POST creates rule and logs audit."""
    url = reverse("ecommerce:fraud_rule_create")
    res_get = auth_client_a.get(url)
    assert res_get.status_code == 200
    assert "form" in res_get.context
    assert res_get.context["is_edit"] is False

    post_data = {
        "name": "High Spend Order Shield",
        "rule_code": "R-SPEND-01",
        "rule_scope": "checkout",
        "rule_type": "amount_threshold",
        "condition_operator": "gt",
        "threshold_value": "5000",
        "risk_score_impact": 45,
        "action_to_take": "block",
        "priority": 5,
        "is_active": True,
        "description": "Block immediate dispatch of unusually high cart totals.",
    }
    res_post = auth_client_a.post(url, post_data)
    created_rule = FraudRule.objects.filter(tenant=tenant_a, rule_code="R-SPEND-01").first()
    assert created_rule is not None
    assert res_post.status_code == 302
    assert res_post.url == reverse("ecommerce:fraud_rule_detail", kwargs={"pk": created_rule.pk})
    assert created_rule.tenant == tenant_a
    assert created_rule.action_to_take == "block"

    # Verify write_audit_log executed without TypeError (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created_rule.pk)).first()
    assert audit is not None


def test_fraudrisk_rule_create_invalid_submission(auth_client_a, tenant_a):
    """Test invalid POST submission re-renders form with 200 and validation errors."""
    url = reverse("ecommerce:fraud_rule_create")
    # Empty threshold_value is invalid per clean_threshold_value
    post_data = {
        "name": "Invalid Rule",
        "rule_code": "R-ERR-01",
        "rule_scope": "checkout",
        "rule_type": "velocity_orders",
        "condition_operator": "gt",
        "threshold_value": "",
        "risk_score_impact": 20,
        "action_to_take": "flag_review",
        "priority": 10,
    }
    response = auth_client_a.post(url, post_data)
    assert response.status_code == 200
    assert "form" in response.context
    assert response.context["form"].errors


def test_fraudrisk_rule_edit_view(auth_client_a, tenant_a, ecom_fraud_rule_a):
    """Test FraudRule edit GET form and valid POST update."""
    url = reverse("ecommerce:fraud_rule_edit", kwargs={"pk": ecom_fraud_rule_a.pk})
    res_get = auth_client_a.get(url)
    assert res_get.status_code == 200
    assert "form" in res_get.context
    assert res_get.context["is_edit"] is True
    assert res_get.context["rule"] == ecom_fraud_rule_a

    post_data = {
        "name": "Updated Velocity Rule",
        "rule_code": ecom_fraud_rule_a.rule_code,
        "rule_scope": ecom_fraud_rule_a.rule_scope,
        "rule_type": ecom_fraud_rule_a.rule_type,
        "condition_operator": "gte",
        "threshold_value": "4",
        "risk_score_impact": 55,
        "action_to_take": "block",
        "priority": 2,
        "is_active": True,
        "description": "Updated rule threshold and stricter action.",
    }
    res_post = auth_client_a.post(url, post_data)
    assert res_post.status_code == 302
    assert res_post.url == reverse("ecommerce:fraud_rule_detail", kwargs={"pk": ecom_fraud_rule_a.pk})

    ecom_fraud_rule_a.refresh_from_db()
    assert ecom_fraud_rule_a.name == "Updated Velocity Rule"
    assert ecom_fraud_rule_a.condition_operator == "gte"
    assert ecom_fraud_rule_a.threshold_value == "4"
    assert ecom_fraud_rule_a.risk_score_impact == 55
    assert ecom_fraud_rule_a.action_to_take == "block"

    # Verify write_audit_log executed on update (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(ecom_fraud_rule_a.pk)).first()
    assert audit is not None


def test_fraudrisk_rule_delete_view(auth_client_a, tenant_a):
    """Test FraudRule delete rejects GET with 405, and POST deletes rule with audit log."""
    rule = _fraudrisk_fraud_rule(tenant_a, name="Temporary Rule", rule_code="R-DEL-01")
    url = reverse("ecommerce:fraud_rule_delete", kwargs={"pk": rule.pk})

    # GET must be rejected with 405 Method Not Allowed
    res_get = auth_client_a.get(url)
    assert res_get.status_code == 405

    # POST deletes rule
    res_post = auth_client_a.post(url)
    assert res_post.status_code == 302
    assert res_post.url == reverse("ecommerce:fraud_rule_list")
    assert not FraudRule.objects.filter(pk=rule.pk).exists()

    # Verify write_audit_log executed on delete (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(rule.pk)).first()
    assert audit is not None


def test_fraudrisk_rule_tenant_isolation_idor(auth_client_a, tenant_b, ecom_fraud_rule_b):
    """Test cross-tenant IDOR access to FraudRule detail/edit/delete returns 404."""
    url_detail = reverse("ecommerce:fraud_rule_detail", kwargs={"pk": ecom_fraud_rule_b.pk})
    url_edit = reverse("ecommerce:fraud_rule_edit", kwargs={"pk": ecom_fraud_rule_b.pk})
    url_delete = reverse("ecommerce:fraud_rule_delete", kwargs={"pk": ecom_fraud_rule_b.pk})

    assert auth_client_a.get(url_detail).status_code == 404
    assert auth_client_a.get(url_edit).status_code == 404
    assert auth_client_a.post(url_edit, {"name": "Hacked"}).status_code == 404
    assert auth_client_a.post(url_delete).status_code == 404


# ==============================================================================
# 3. TransactionRiskAssessment Views Tests
# ==============================================================================

def test_fraudrisk_assessment_list_view_and_filters(auth_client_a, tenant_a, ecom_risk_assessment_a):
    """Test TransactionRiskAssessment list view context, choices, and GET filters."""
    url = reverse("ecommerce:transaction_risk_assessment_list")
    response = auth_client_a.get(url)
    assert response.status_code == 200

    expected_context_keys = [
        "assessments",
        "page_obj",
        "paginator",
        "is_paginated",
        "total_count",
        "search_query",
        "tier_filter",
        "action_filter",
        "decision_filter",
        "tier_choices",
        "action_choices",
        "decision_choices",
    ]
    for key in expected_context_keys:
        assert key in response.context, f"Missing assessment list context key: {key}"

    assert response.context["total_count"] >= 1
    assert len(response.context["assessments"]) >= 1

    # Filter by risk tier
    res_tier = auth_client_a.get(url, {"tier": "medium"})
    assert res_tier.status_code == 200
    assert len(res_tier.context["assessments"]) >= 1

    # Filter by recommended action
    res_action = auth_client_a.get(url, {"action": "review"})
    assert res_action.status_code == 200
    assert len(res_action.context["assessments"]) >= 1

    # Filter by actual decision
    res_dec = auth_client_a.get(url, {"decision": "pending"})
    assert res_dec.status_code == 200
    assert len(res_dec.context["assessments"]) >= 1

    # Search query
    res_search = auth_client_a.get(url, {"q": "198.51.100.42"})
    assert res_search.status_code == 200
    assert len(res_search.context["assessments"]) >= 1


def test_fraudrisk_assessment_list_pagination(auth_client_a, tenant_a):
    """Test TransactionRiskAssessment pagination when exceeding 15 records."""
    currency = _fraudrisk_get_currency_usd()
    party = Party.objects.create(tenant=tenant_a, name="Paginated Party")
    for i in range(16):
        _fraudrisk_transaction_risk_assessment(
            tenant_a,
            customer_party=party,
            currency=currency,
            risk_score=20 + i,
        )
    url = reverse("ecommerce:transaction_risk_assessment_list")
    res_p1 = auth_client_a.get(url)
    assert res_p1.status_code == 200
    assert res_p1.context["is_paginated"] is True
    assert len(res_p1.context["assessments"]) == 15

    res_p2 = auth_client_a.get(url, {"page": 2})
    assert res_p2.status_code == 200
    assert len(res_p2.context["assessments"]) >= 1


def test_fraudrisk_assessment_detail_view(auth_client_a, tenant_a, ecom_risk_assessment_a):
    """Test TransactionRiskAssessment detail view returns 200 with assessment context variable."""
    url = reverse("ecommerce:transaction_risk_assessment_detail", kwargs={"pk": ecom_risk_assessment_a.pk})
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "assessment" in response.context
    assert response.context["assessment"] == ecom_risk_assessment_a


def test_fraudrisk_assessment_create_view(auth_client_a, tenant_a, user_a):
    """Test TransactionRiskAssessment create view GET form and POST with analyst auto-assignment."""
    url = reverse("ecommerce:transaction_risk_assessment_create")
    res_get = auth_client_a.get(url)
    assert res_get.status_code == 200
    assert "form" in res_get.context
    assert res_get.context["is_edit"] is False

    currency = _fraudrisk_get_currency_usd()
    party = Party.objects.create(tenant=tenant_a, name="High Risk Buyer")
    order = _fraudrisk_create_order(tenant_a, party=party, currency=currency)

    post_data = {
        "order": order.pk,
        "customer_party": party.pk,
        "user": user_a.pk,
        "transaction_amount": "349.50",
        "currency": currency.pk,
        "risk_score": 75,
        "risk_tier": "high",
        "recommended_action": "review",
        "actual_decision": "approved_manual",
        "avs_result_code": "partial",
        "cvv_result_code": "match",
        "ip_address": "198.51.100.99",
        "billing_country": "US",
        "ip_country": "CA",
        "is_geo_mismatch": True,
        "is_proxy_or_vpn": False,
        "device_fingerprint": "dfp_manual_review_hash",
        "velocity_count_24h": 3,
        "risk_factors_summary": "Cross-border order with elevated risk score.",
        "analyst_notes": "Customer identity verified via secondary call.",
    }
    res_post = auth_client_a.post(url, post_data)
    assert res_post.status_code == 302
    created = TransactionRiskAssessment.objects.filter(tenant=tenant_a, ip_address="198.51.100.99").first()
    assert created is not None
    assert res_post.url == reverse("ecommerce:transaction_risk_assessment_detail", kwargs={"pk": created.pk})
    # Manual decision auto-assigns analyst_user and reviewed_at
    assert created.analyst_user == user_a
    assert created.reviewed_at is not None

    # Verify write_audit_log executed on create (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created.pk)).first()
    assert audit is not None


def test_fraudrisk_assessment_edit_view(auth_client_a, tenant_a, user_a, ecom_risk_assessment_a):
    """Test TransactionRiskAssessment edit GET form and POST update with analyst decision transition."""
    url = reverse("ecommerce:transaction_risk_assessment_edit", kwargs={"pk": ecom_risk_assessment_a.pk})
    res_get = auth_client_a.get(url)
    assert res_get.status_code == 200
    assert "form" in res_get.context
    assert res_get.context["is_edit"] is True
    assert res_get.context["assessment"] == ecom_risk_assessment_a

    currency = _fraudrisk_get_currency_usd()
    post_data = {
        "transaction_amount": "149.99",
        "currency": currency.pk,
        "risk_score": 90,
        "risk_tier": "critical",
        "recommended_action": "reject",
        "actual_decision": "declined_manual",
        "avs_result_code": "no_match",
        "cvv_result_code": "no_match",
        "ip_address": ecom_risk_assessment_a.ip_address,
        "billing_country": "US",
        "ip_country": "RU",
        "is_geo_mismatch": True,
        "is_proxy_or_vpn": True,
        "device_fingerprint": ecom_risk_assessment_a.device_fingerprint,
        "velocity_count_24h": 5,
        "risk_factors_summary": "Confirmed compromised card.",
        "analyst_notes": "Declined manually after cardholder fraud dispute notice.",
    }
    res_post = auth_client_a.post(url, post_data)
    assert res_post.status_code == 302
    assert res_post.url == reverse("ecommerce:transaction_risk_assessment_detail", kwargs={"pk": ecom_risk_assessment_a.pk})

    ecom_risk_assessment_a.refresh_from_db()
    assert ecom_risk_assessment_a.actual_decision == "declined_manual"
    assert ecom_risk_assessment_a.analyst_user == user_a
    assert ecom_risk_assessment_a.reviewed_at is not None

    # Verify write_audit_log executed on update (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(ecom_risk_assessment_a.pk)).first()
    assert audit is not None


def test_fraudrisk_assessment_delete_view(auth_client_a, tenant_a):
    """Test TransactionRiskAssessment delete rejects GET with 405, and POST deletes assessment."""
    assessment = _fraudrisk_transaction_risk_assessment(tenant_a, risk_score=15)
    url = reverse("ecommerce:transaction_risk_assessment_delete", kwargs={"pk": assessment.pk})

    # GET rejected with 405
    assert auth_client_a.get(url).status_code == 405

    # POST deletes
    res_post = auth_client_a.post(url)
    assert res_post.status_code == 302
    assert res_post.url == reverse("ecommerce:transaction_risk_assessment_list")
    assert not TransactionRiskAssessment.objects.filter(pk=assessment.pk).exists()

    # Verify write_audit_log executed on delete (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(assessment.pk)).first()
    assert audit is not None


def test_fraudrisk_assessment_tenant_isolation_idor(auth_client_a, tenant_b, ecom_risk_assessment_b):
    """Test cross-tenant IDOR access to TransactionRiskAssessment returns 404."""
    url_detail = reverse("ecommerce:transaction_risk_assessment_detail", kwargs={"pk": ecom_risk_assessment_b.pk})
    url_edit = reverse("ecommerce:transaction_risk_assessment_edit", kwargs={"pk": ecom_risk_assessment_b.pk})
    url_delete = reverse("ecommerce:transaction_risk_assessment_delete", kwargs={"pk": ecom_risk_assessment_b.pk})

    assert auth_client_a.get(url_detail).status_code == 404
    assert auth_client_a.get(url_edit).status_code == 404
    assert auth_client_a.post(url_edit, {"risk_score": 10}).status_code == 404
    assert auth_client_a.post(url_delete).status_code == 404


# ==============================================================================
# 4. ChargebackDispute Views Tests
# ==============================================================================

def test_fraudrisk_chargeback_dispute_list_view_and_filters(auth_client_a, tenant_a, ecom_chargeback_dispute_a):
    """Test ChargebackDispute list view context contract, choices, and GET filters."""
    url = reverse("ecommerce:chargeback_dispute_list")
    response = auth_client_a.get(url)
    assert response.status_code == 200

    expected_context_keys = [
        "disputes",
        "page_obj",
        "paginator",
        "is_paginated",
        "total_count",
        "search_query",
        "stage_filter",
        "reason_filter",
        "stage_choices",
        "reason_choices",
    ]
    for key in expected_context_keys:
        assert key in response.context, f"Missing dispute list context key: {key}"

    assert response.context["total_count"] >= 1
    assert len(response.context["disputes"]) >= 1

    # Filter by stage
    res_stage = auth_client_a.get(url, {"stage": "needs_response"})
    assert res_stage.status_code == 200
    assert len(res_stage.context["disputes"]) >= 1

    # Filter by reason category
    res_reason = auth_client_a.get(url, {"reason": "fraudulent"})
    assert res_reason.status_code == 200
    assert len(res_reason.context["disputes"]) >= 1

    # Search query
    res_search = auth_client_a.get(url, {"q": "dp_test_918"})
    assert res_search.status_code == 200
    assert len(res_search.context["disputes"]) >= 1


def test_fraudrisk_chargeback_dispute_list_pagination(auth_client_a, tenant_a):
    """Test ChargebackDispute pagination when records exceed 15."""
    currency = _fraudrisk_get_currency_usd()
    party = Party.objects.create(tenant=tenant_a, name="Disputing Party Group")
    for i in range(16):
        order = _fraudrisk_create_order(tenant_a, party=party, currency=currency)
        _fraudrisk_chargeback_dispute(
            tenant_a,
            order=order,
            customer_party=party,
            currency=currency,
            gateway_dispute_id=f"dp_pag_{i:02d}",
        )
    url = reverse("ecommerce:chargeback_dispute_list")
    res_p1 = auth_client_a.get(url)
    assert res_p1.status_code == 200
    assert res_p1.context["is_paginated"] is True
    assert len(res_p1.context["disputes"]) == 15

    res_p2 = auth_client_a.get(url, {"page": 2})
    assert res_p2.status_code == 200
    assert len(res_p2.context["disputes"]) >= 1


def test_fraudrisk_chargeback_dispute_detail_view(auth_client_a, tenant_a, ecom_chargeback_dispute_a):
    """Test ChargebackDispute detail view returns 200 with dispute context variable."""
    url = reverse("ecommerce:chargeback_dispute_detail", kwargs={"pk": ecom_chargeback_dispute_a.pk})
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "dispute" in response.context
    assert response.context["dispute"] == ecom_chargeback_dispute_a


def test_fraudrisk_chargeback_dispute_create_view(auth_client_a, tenant_a):
    """Test ChargebackDispute create view GET form and POST valid creation with representment date setting."""
    url = reverse("ecommerce:chargeback_dispute_create")
    res_get = auth_client_a.get(url)
    assert res_get.status_code == 200
    assert "form" in res_get.context
    assert res_get.context["is_edit"] is False

    currency = _fraudrisk_get_currency_usd()
    party = Party.objects.create(tenant=tenant_a, name="Disputing Client")
    order = _fraudrisk_create_order(tenant_a, party=party, currency=currency)

    post_data = {
        "order": order.pk,
        "customer_party": party.pk,
        "currency": currency.pk,
        "dispute_amount": "280.00",
        "dispute_fee": "15.00",
        "gateway_dispute_id": "dp_stripe_live_case_001",
        "payment_method_type": "credit_card",
        "card_brand": "Visa",
        "reason_category": "fraudulent",
        "reason_code": "10.4",
        "stage": "representment_submitted",
        "evidence_due_date": "2026-12-15",
        "evidence_summary": "Delivery signature tracking confirmed by FedEx.",
        "representment_notes": "Official rebuttal letter submitted with IP audit trail.",
    }
    res_post = auth_client_a.post(url, post_data)
    assert res_post.status_code == 302
    created = ChargebackDispute.objects.filter(tenant=tenant_a, gateway_dispute_id="dp_stripe_live_case_001").first()
    assert created is not None
    assert res_post.url == reverse("ecommerce:chargeback_dispute_detail", kwargs={"pk": created.pk})
    # Stage representment_submitted automatically sets representment_submitted_at
    assert created.representment_submitted_at is not None

    # Verify write_audit_log executed on create (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created.pk)).first()
    assert audit is not None


def test_fraudrisk_chargeback_dispute_edit_view(auth_client_a, tenant_a, ecom_chargeback_dispute_a):
    """Test ChargebackDispute edit GET form and POST update with resolution timestamp setting."""
    url = reverse("ecommerce:chargeback_dispute_edit", kwargs={"pk": ecom_chargeback_dispute_a.pk})
    res_get = auth_client_a.get(url)
    assert res_get.status_code == 200
    assert "form" in res_get.context
    assert res_get.context["is_edit"] is True
    assert res_get.context["dispute"] == ecom_chargeback_dispute_a

    currency = _fraudrisk_get_currency_usd()
    post_data = {
        "order": ecom_chargeback_dispute_a.order.pk,
        "currency": currency.pk,
        "dispute_amount": str(ecom_chargeback_dispute_a.dispute_amount),
        "dispute_fee": str(ecom_chargeback_dispute_a.dispute_fee),
        "gateway_dispute_id": ecom_chargeback_dispute_a.gateway_dispute_id,
        "payment_method_type": "credit_card",
        "card_brand": "Visa",
        "reason_category": "fraudulent",
        "reason_code": "10.4",
        "stage": "won",
        "evidence_summary": "Rebuttal pack delivered.",
        "representment_notes": "Accepted by issuing bank.",
        "outcome_notes": "Dispute won in full; dispute fee credited back.",
    }
    res_post = auth_client_a.post(url, post_data)
    assert res_post.status_code == 302
    assert res_post.url == reverse("ecommerce:chargeback_dispute_detail", kwargs={"pk": ecom_chargeback_dispute_a.pk})

    ecom_chargeback_dispute_a.refresh_from_db()
    assert ecom_chargeback_dispute_a.stage == "won"
    # Transitioning to "won" sets resolved_at
    assert ecom_chargeback_dispute_a.resolved_at is not None

    # Verify write_audit_log executed on update (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(ecom_chargeback_dispute_a.pk)).first()
    assert audit is not None


def test_fraudrisk_chargeback_dispute_delete_view(auth_client_a, tenant_a):
    """Test ChargebackDispute delete rejects GET with 405, and POST deletes dispute."""
    dispute = _fraudrisk_chargeback_dispute(tenant_a, gateway_dispute_id="dp_to_delete_999")
    url = reverse("ecommerce:chargeback_dispute_delete", kwargs={"pk": dispute.pk})

    # GET rejected with 405
    assert auth_client_a.get(url).status_code == 405

    # POST deletes
    res_post = auth_client_a.post(url)
    assert res_post.status_code == 302
    assert res_post.url == reverse("ecommerce:chargeback_dispute_list")
    assert not ChargebackDispute.objects.filter(pk=dispute.pk).exists()

    # Verify write_audit_log executed on delete (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(dispute.pk)).first()
    assert audit is not None


def test_fraudrisk_chargeback_dispute_tenant_isolation_idor(auth_client_a, tenant_b, ecom_chargeback_dispute_b):
    """Test cross-tenant IDOR access to ChargebackDispute returns 404."""
    url_detail = reverse("ecommerce:chargeback_dispute_detail", kwargs={"pk": ecom_chargeback_dispute_b.pk})
    url_edit = reverse("ecommerce:chargeback_dispute_edit", kwargs={"pk": ecom_chargeback_dispute_b.pk})
    url_delete = reverse("ecommerce:chargeback_dispute_delete", kwargs={"pk": ecom_chargeback_dispute_b.pk})

    assert auth_client_a.get(url_detail).status_code == 404
    assert auth_client_a.get(url_edit).status_code == 404
    assert auth_client_a.post(url_edit, {"stage": "won"}).status_code == 404
    assert auth_client_a.post(url_delete).status_code == 404


# ==============================================================================
# 5. AccountSecurityAlert Views Tests
# ==============================================================================

def test_fraudrisk_security_alert_list_view_and_filters(auth_client_a, tenant_a, ecom_security_alert_a):
    """Test AccountSecurityAlert list view context contract, choices, and GET filters."""
    url = reverse("ecommerce:account_security_alert_list")
    response = auth_client_a.get(url)
    assert response.status_code == 200

    expected_context_keys = [
        "alerts",
        "page_obj",
        "paginator",
        "is_paginated",
        "total_count",
        "search_query",
        "type_filter",
        "severity_filter",
        "status_filter",
        "type_choices",
        "severity_choices",
        "status_choices",
    ]
    for key in expected_context_keys:
        assert key in response.context, f"Missing alert list context key: {key}"

    assert response.context["total_count"] >= 1
    assert len(response.context["alerts"]) >= 1

    # Filter by alert type
    res_type = auth_client_a.get(url, {"type": "credential_stuffing"})
    assert res_type.status_code == 200
    assert len(res_type.context["alerts"]) >= 1

    # Filter by severity
    res_sev = auth_client_a.get(url, {"severity": "high"})
    assert res_sev.status_code == 200
    assert len(res_sev.context["alerts"]) >= 1

    # Filter by status
    res_st = auth_client_a.get(url, {"status": "new"})
    assert res_st.status_code == 200
    assert len(res_st.context["alerts"]) >= 1

    # Search query
    res_search = auth_client_a.get(url, {"q": "203.0.113.88"})
    assert res_search.status_code == 200
    assert len(res_search.context["alerts"]) >= 1


def test_fraudrisk_security_alert_list_pagination(auth_client_a, tenant_a, user_a):
    """Test AccountSecurityAlert pagination when records exceed 15."""
    party = Party.objects.create(tenant=tenant_a, name="Alert Target Party")
    for i in range(16):
        _fraudrisk_account_security_alert(
            tenant_a,
            party=party,
            user=user_a,
            ip_address=f"203.0.113.{i:02d}",
        )
    url = reverse("ecommerce:account_security_alert_list")
    res_p1 = auth_client_a.get(url)
    assert res_p1.status_code == 200
    assert res_p1.context["is_paginated"] is True
    assert len(res_p1.context["alerts"]) == 15

    res_p2 = auth_client_a.get(url, {"page": 2})
    assert res_p2.status_code == 200
    assert len(res_p2.context["alerts"]) >= 1


def test_fraudrisk_security_alert_detail_view(auth_client_a, tenant_a, ecom_security_alert_a):
    """Test AccountSecurityAlert detail view returns 200 with alert context variable."""
    url = reverse("ecommerce:account_security_alert_detail", kwargs={"pk": ecom_security_alert_a.pk})
    response = auth_client_a.get(url)
    assert response.status_code == 200
    assert "alert" in response.context
    assert response.context["alert"] == ecom_security_alert_a


def test_fraudrisk_security_alert_create_view(auth_client_a, tenant_a, user_a):
    """Test AccountSecurityAlert create view GET form and POST valid creation with resolution handling."""
    url = reverse("ecommerce:account_security_alert_create")
    res_get = auth_client_a.get(url)
    assert res_get.status_code == 200
    assert "form" in res_get.context
    assert res_get.context["is_edit"] is False

    party = Party.objects.create(tenant=tenant_a, name="Targeted Account")
    post_data = {
        "user": user_a.pk,
        "party": party.pk,
        "alert_type": "brute_force",
        "severity": "medium",
        "status": "resolved_legitimate",
        "automated_action_taken": "none",
        "ip_address": "198.51.100.22",
        "location_info": "Austin, TX, US",
        "user_agent": "Mozilla/5.0 Test Agent",
        "incident_details": "Customer fat-fingered password 4 times.",
        "assigned_investigator": user_a.pk,
        "investigation_notes": "User confirmed legitimate attempts after phone call.",
    }
    res_post = auth_client_a.post(url, post_data)
    assert res_post.status_code == 302
    created = AccountSecurityAlert.objects.filter(tenant=tenant_a, ip_address="198.51.100.22").first()
    assert created is not None
    assert res_post.url == reverse("ecommerce:account_security_alert_detail", kwargs={"pk": created.pk})
    # Status resolved_legitimate automatically sets resolved_at and resolved_by
    assert created.resolved_at is not None
    assert created.resolved_by == user_a

    # Verify write_audit_log executed on create (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=str(created.pk)).first()
    assert audit is not None


def test_fraudrisk_security_alert_edit_view(auth_client_a, tenant_a, user_a, ecom_security_alert_a):
    """Test AccountSecurityAlert edit GET form and POST update with threat mitigation timestamp."""
    url = reverse("ecommerce:account_security_alert_edit", kwargs={"pk": ecom_security_alert_a.pk})
    res_get = auth_client_a.get(url)
    assert res_get.status_code == 200
    assert "form" in res_get.context
    assert res_get.context["is_edit"] is True
    assert res_get.context["alert"] == ecom_security_alert_a

    post_data = {
        "alert_type": ecom_security_alert_a.alert_type,
        "severity": "critical",
        "status": "confirmed_threat",
        "automated_action_taken": "lock_account",
        "ip_address": ecom_security_alert_a.ip_address,
        "location_info": "Bucharest, Romania",
        "user_agent": "Mozilla/5.0 Botnet Client",
        "incident_details": "Account takeover attempt detected and confirmed.",
        "assigned_investigator": user_a.pk,
        "investigation_notes": "Sessions terminated and password reset enforced.",
    }
    res_post = auth_client_a.post(url, post_data)
    assert res_post.status_code == 302
    assert res_post.url == reverse("ecommerce:account_security_alert_detail", kwargs={"pk": ecom_security_alert_a.pk})

    ecom_security_alert_a.refresh_from_db()
    assert ecom_security_alert_a.status == "confirmed_threat"
    assert ecom_security_alert_a.severity == "critical"
    assert ecom_security_alert_a.resolved_at is not None
    assert ecom_security_alert_a.resolved_by == user_a

    # Verify write_audit_log executed on update (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=str(ecom_security_alert_a.pk)).first()
    assert audit is not None


def test_fraudrisk_security_alert_delete_view(auth_client_a, tenant_a):
    """Test AccountSecurityAlert delete rejects GET with 405, and POST deletes alert."""
    alert = _fraudrisk_account_security_alert(tenant_a, ip_address="203.0.113.250")
    url = reverse("ecommerce:account_security_alert_delete", kwargs={"pk": alert.pk})

    # GET rejected with 405
    assert auth_client_a.get(url).status_code == 405

    # POST deletes
    res_post = auth_client_a.post(url)
    assert res_post.status_code == 302
    assert res_post.url == reverse("ecommerce:account_security_alert_list")
    assert not AccountSecurityAlert.objects.filter(pk=alert.pk).exists()

    # Verify write_audit_log executed on delete (C1)
    audit = AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=str(alert.pk)).first()
    assert audit is not None


def test_fraudrisk_security_alert_tenant_isolation_idor(auth_client_a, tenant_b, ecom_security_alert_b):
    """Test cross-tenant IDOR access to AccountSecurityAlert returns 404."""
    url_detail = reverse("ecommerce:account_security_alert_detail", kwargs={"pk": ecom_security_alert_b.pk})
    url_edit = reverse("ecommerce:account_security_alert_edit", kwargs={"pk": ecom_security_alert_b.pk})
    url_delete = reverse("ecommerce:account_security_alert_delete", kwargs={"pk": ecom_security_alert_b.pk})

    assert auth_client_a.get(url_detail).status_code == 404
    assert auth_client_a.get(url_edit).status_code == 404
    assert auth_client_a.post(url_edit, {"status": "dismissed"}).status_code == 404
    assert auth_client_a.post(url_delete).status_code == 404


# ==============================================================================
# 6. write_audit_log Verification (C1)
# ==============================================================================

def test_fraudrisk_write_audit_log_execution_integrity(auth_client_a, tenant_a):
    """Verify that mutation endpoints across all 4 models execute write_audit_log without TypeError."""
    audit_count_before = AuditLog.objects.filter(tenant=tenant_a).count()

    # 1. Create FraudRule
    res_rule = auth_client_a.post(
        reverse("ecommerce:fraud_rule_create"),
        {
            "name": "Audit Test Rule",
            "rule_code": "R-AUD-01",
            "rule_scope": "checkout",
            "rule_type": "amount_threshold",
            "condition_operator": "gt",
            "threshold_value": "1000",
            "risk_score_impact": 10,
            "action_to_take": "allow",
            "priority": 1,
            "is_active": True,
            "description": "Rule for audit log testing",
        },
    )
    assert res_rule.status_code == 302

    # 2. Create Assessment
    currency = _fraudrisk_get_currency_usd()
    res_assessment = auth_client_a.post(
        reverse("ecommerce:transaction_risk_assessment_create"),
        {
            "transaction_amount": "99.00",
            "currency": currency.pk,
            "risk_score": 10,
            "risk_tier": "low",
            "recommended_action": "approve",
            "actual_decision": "approved_auto",
            "avs_result_code": "match",
            "cvv_result_code": "match",
            "ip_address": "198.51.100.5",
            "billing_country": "US",
            "ip_country": "US",
            "velocity_count_24h": 1,
        },
    )
    assert res_assessment.status_code == 302

    # 3. Create Dispute
    order = _fraudrisk_create_order(tenant_a, currency=currency)
    res_dispute = auth_client_a.post(
        reverse("ecommerce:chargeback_dispute_create"),
        {
            "order": order.pk,
            "currency": currency.pk,
            "dispute_amount": "50.00",
            "dispute_fee": "15.00",
            "gateway_dispute_id": "dp_audit_test_99",
            "payment_method_type": "credit_card",
            "card_brand": "Visa",
            "reason_category": "other",
            "reason_code": "00",
            "stage": "inquiry",
            "evidence_summary": "Initial inquiry",
        },
    )
    assert res_dispute.status_code == 302

    # 4. Create Alert
    res_alert = auth_client_a.post(
        reverse("ecommerce:account_security_alert_create"),
        {
            "alert_type": "suspicious_login",
            "severity": "low",
            "status": "new",
            "automated_action_taken": "none",
            "ip_address": "198.51.100.6",
            "location_info": "Dallas, TX",
            "user_agent": "Mozilla/5.0 Test",
            "incident_details": "New login detected",
        },
    )
    assert res_alert.status_code == 302

    audit_count_after = AuditLog.objects.filter(tenant=tenant_a).count()
    assert audit_count_after >= audit_count_before + 4
