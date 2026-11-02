"""Security, IDOR isolation, foreign key protection, authentication gates, method safety,
mass assignment, and audit log forensics tests for eCommerce 9.18 Fraud & Risk Management.

Covers:
1. Multi-Tenant IDOR Isolation:
   - Cross-tenant detail access: Tenant A client requesting Tenant B FraudRule,
     TransactionRiskAssessment, ChargebackDispute, AccountSecurityAlert returns 404.
   - Cross-tenant edit access: Tenant A client requesting Tenant B edit (GET and POST) returns 404.
   - Cross-tenant delete access: Tenant A client POSTing to Tenant B delete returns 404 and does not delete.
   - List view isolation: Tenant A list views only display Tenant A records and exclude Tenant B.
2. Foreign FK Tampering Protection:
   - Form submissions attempting to inject foreign tenant PKs for `order`, `customer_party`,
     or `party` are rejected by `reject_foreign`.
3. Authentication Gates:
   - Unauthenticated / anonymous GET requests across all 9.18 endpoints redirect to login.
4. HTTP Method Safety:
   - GET requests to all 4 delete endpoints return 405 Method Not Allowed.
5. System Field Protection (Mass Assignment):
   - Attempted mass assignment of `tenant`, `number`, `analyst_user`, or system timestamps via POST is ignored.
6. Forensic Audit Logging:
   - Mutating operations (create, update, delete) write valid `AuditLog` records with correct action types.
   - Audit logs are strictly isolated per tenant.

Conventions enforced:
- pytestmark = pytest.mark.django_db
- Test functions: test_fraudrisk_*
- Local helpers: _fraudrisk_*
"""
from decimal import Decimal
import pytest
from django.urls import reverse

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models import AuditLog, Party
from apps.ecommerce.forms.FraudRisk.AccountSecurityAlerts import AccountSecurityAlertForm
from apps.ecommerce.forms.FraudRisk.ChargebackDisputes import ChargebackDisputeForm
from apps.ecommerce.forms.FraudRisk.TransactionRiskAssessments import TransactionRiskAssessmentForm
from apps.ecommerce.models import (
    FraudRule,
    TransactionRiskAssessment,
    ChargebackDispute,
    AccountSecurityAlert,
)
from apps.ecommerce.tests.conftest import _ordermanagement_order

pytestmark = pytest.mark.django_db


# ==============================================================================
# Local Test Helpers (_fraudrisk_*)
# ==============================================================================

def _fraudrisk_get_currency():
    """Local helper to fetch or create active USD currency."""
    currency = Currency.objects.filter(code="USD").first()
    if not currency:
        currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$", is_active=True)
    return currency


def _fraudrisk_valid_rule_data(**overrides):
    """Generate valid payload for FraudRule."""
    data = {
        "name": "Card Velocity Exceeded",
        "rule_code": "R-SEC-VEL-01",
        "rule_scope": "checkout",
        "rule_type": "velocity_orders",
        "condition_operator": "gt",
        "threshold_value": "5",
        "risk_score_impact": 30,
        "action_to_take": "flag_review",
        "priority": 10,
        "is_active": True,
        "description": "Trigger review on card velocity.",
    }
    data.update(overrides)
    return data


def _fraudrisk_valid_assessment_data(currency, order=None, customer_party=None, **overrides):
    """Generate valid payload for TransactionRiskAssessment."""
    data = {
        "order": order.pk if order else "",
        "customer_party": customer_party.pk if customer_party else "",
        "transaction_amount": "149.99",
        "currency": currency.pk,
        "risk_score": 45,
        "risk_tier": "medium",
        "recommended_action": "review",
        "actual_decision": "pending",
        "avs_result_code": "match",
        "cvv_result_code": "match",
        "ip_address": "198.51.100.42",
        "billing_country": "US",
        "ip_country": "US",
        "is_geo_mismatch": False,
        "is_proxy_or_vpn": False,
        "device_fingerprint": "dfp_sec_test_hash",
        "velocity_count_24h": 1,
        "risk_factors_summary": "Security test assessment",
        "analyst_notes": "Security test notes",
    }
    data.update(overrides)
    return data


def _fraudrisk_valid_dispute_data(currency, order, customer_party=None, **overrides):
    """Generate valid payload for ChargebackDispute."""
    data = {
        "order": order.pk,
        "customer_party": customer_party.pk if customer_party else "",
        "currency": currency.pk,
        "dispute_amount": "120.00",
        "dispute_fee": "15.00",
        "gateway_dispute_id": "dp_sec_dispute_918",
        "payment_method_type": "credit_card",
        "card_brand": "Visa",
        "reason_category": "fraudulent",
        "reason_code": "10.4",
        "stage": "needs_response",
        "evidence_summary": "Delivery signature on file",
        "representment_notes": "Contesting chargeback",
        "outcome_notes": "Pending gateway response",
    }
    data.update(overrides)
    return data


def _fraudrisk_valid_alert_data(party=None, **overrides):
    """Generate valid payload for AccountSecurityAlert."""
    data = {
        "party": party.pk if party else "",
        "alert_type": "credential_stuffing",
        "severity": "high",
        "status": "new",
        "automated_action_taken": "challenge_mfa",
        "ip_address": "203.0.113.88",
        "location_info": "Bucharest, Romania",
        "user_agent": "Mozilla/5.0 Security Test",
        "incident_details": "10 failed login attempts within 60s",
        "investigation_notes": "Investigating incident",
    }
    data.update(overrides)
    return data


# ==============================================================================
# 1. Multi-Tenant IDOR Isolation Tests (Cross-Tenant 404s)
# ==============================================================================

def test_fraudrisk_idor_fraud_rule_detail(auth_client_a, ecom_fraud_rule_b):
    """Tenant A client requesting Tenant B FraudRule detail returns 404."""
    url = reverse("ecommerce:fraud_rule_detail", args=[ecom_fraud_rule_b.pk])
    assert auth_client_a.get(url).status_code == 404


def test_fraudrisk_idor_fraud_rule_edit(auth_client_a, ecom_fraud_rule_b):
    """Tenant A client requesting Tenant B FraudRule edit returns 404 on GET and POST."""
    url = reverse("ecommerce:fraud_rule_edit", args=[ecom_fraud_rule_b.pk])
    assert auth_client_a.get(url).status_code == 404
    assert auth_client_a.post(url, {"name": "Tampered Rule Name"}).status_code == 404

    ecom_fraud_rule_b.refresh_from_db()
    assert ecom_fraud_rule_b.name != "Tampered Rule Name"


def test_fraudrisk_idor_fraud_rule_delete(auth_client_a, ecom_fraud_rule_b):
    """Tenant A client POSTing to Tenant B FraudRule delete returns 404 and does not delete."""
    url = reverse("ecommerce:fraud_rule_delete", args=[ecom_fraud_rule_b.pk])
    assert auth_client_a.post(url).status_code == 404
    assert FraudRule.objects.filter(pk=ecom_fraud_rule_b.pk).exists() is True


def test_fraudrisk_idor_risk_assessment_detail(auth_client_a, ecom_risk_assessment_b):
    """Tenant A client requesting Tenant B TransactionRiskAssessment detail returns 404."""
    url = reverse("ecommerce:transaction_risk_assessment_detail", args=[ecom_risk_assessment_b.pk])
    assert auth_client_a.get(url).status_code == 404


def test_fraudrisk_idor_risk_assessment_edit(auth_client_a, ecom_risk_assessment_b):
    """Tenant A client requesting Tenant B TransactionRiskAssessment edit returns 404 on GET and POST."""
    url = reverse("ecommerce:transaction_risk_assessment_edit", args=[ecom_risk_assessment_b.pk])
    assert auth_client_a.get(url).status_code == 404
    assert auth_client_a.post(url, {"analyst_notes": "Tampered Analyst Notes"}).status_code == 404

    ecom_risk_assessment_b.refresh_from_db()
    assert ecom_risk_assessment_b.analyst_notes != "Tampered Analyst Notes"


def test_fraudrisk_idor_risk_assessment_delete(auth_client_a, ecom_risk_assessment_b):
    """Tenant A client POSTing to Tenant B TransactionRiskAssessment delete returns 404 and does not delete."""
    url = reverse("ecommerce:transaction_risk_assessment_delete", args=[ecom_risk_assessment_b.pk])
    assert auth_client_a.post(url).status_code == 404
    assert TransactionRiskAssessment.objects.filter(pk=ecom_risk_assessment_b.pk).exists() is True


def test_fraudrisk_idor_chargeback_dispute_detail(auth_client_a, ecom_chargeback_dispute_b):
    """Tenant A client requesting Tenant B ChargebackDispute detail returns 404."""
    url = reverse("ecommerce:chargeback_dispute_detail", args=[ecom_chargeback_dispute_b.pk])
    assert auth_client_a.get(url).status_code == 404


def test_fraudrisk_idor_chargeback_dispute_edit(auth_client_a, ecom_chargeback_dispute_b):
    """Tenant A client requesting Tenant B ChargebackDispute edit returns 404 on GET and POST."""
    url = reverse("ecommerce:chargeback_dispute_edit", args=[ecom_chargeback_dispute_b.pk])
    assert auth_client_a.get(url).status_code == 404
    assert auth_client_a.post(url, {"evidence_summary": "Tampered Evidence"}).status_code == 404

    ecom_chargeback_dispute_b.refresh_from_db()
    assert ecom_chargeback_dispute_b.evidence_summary != "Tampered Evidence"


def test_fraudrisk_idor_chargeback_dispute_delete(auth_client_a, ecom_chargeback_dispute_b):
    """Tenant A client POSTing to Tenant B ChargebackDispute delete returns 404 and does not delete."""
    url = reverse("ecommerce:chargeback_dispute_delete", args=[ecom_chargeback_dispute_b.pk])
    assert auth_client_a.post(url).status_code == 404
    assert ChargebackDispute.objects.filter(pk=ecom_chargeback_dispute_b.pk).exists() is True


def test_fraudrisk_idor_security_alert_detail(auth_client_a, ecom_security_alert_b):
    """Tenant A client requesting Tenant B AccountSecurityAlert detail returns 404."""
    url = reverse("ecommerce:account_security_alert_detail", args=[ecom_security_alert_b.pk])
    assert auth_client_a.get(url).status_code == 404


def test_fraudrisk_idor_security_alert_edit(auth_client_a, ecom_security_alert_b):
    """Tenant A client requesting Tenant B AccountSecurityAlert edit returns 404 on GET and POST."""
    url = reverse("ecommerce:account_security_alert_edit", args=[ecom_security_alert_b.pk])
    assert auth_client_a.get(url).status_code == 404
    assert auth_client_a.post(url, {"investigation_notes": "Tampered Notes"}).status_code == 404

    ecom_security_alert_b.refresh_from_db()
    assert ecom_security_alert_b.investigation_notes != "Tampered Notes"


def test_fraudrisk_idor_security_alert_delete(auth_client_a, ecom_security_alert_b):
    """Tenant A client POSTing to Tenant B AccountSecurityAlert delete returns 404 and does not delete."""
    url = reverse("ecommerce:account_security_alert_delete", args=[ecom_security_alert_b.pk])
    assert auth_client_a.post(url).status_code == 404
    assert AccountSecurityAlert.objects.filter(pk=ecom_security_alert_b.pk).exists() is True


def test_fraudrisk_tenant_isolation_in_lists(
    auth_client_a,
    ecom_fraud_rule_a,
    ecom_fraud_rule_b,
    ecom_risk_assessment_a,
    ecom_risk_assessment_b,
    ecom_chargeback_dispute_a,
    ecom_chargeback_dispute_b,
    ecom_security_alert_a,
    ecom_security_alert_b,
):
    """Tenant A sees only its own records; Tenant B records are strictly excluded from list views."""
    # Rules list
    res_rules = auth_client_a.get(reverse("ecommerce:fraud_rule_list"))
    rule_pks = {r.pk for r in res_rules.context["rules"]}
    assert ecom_fraud_rule_a.pk in rule_pks
    assert ecom_fraud_rule_b.pk not in rule_pks

    # Assessments list
    res_assessments = auth_client_a.get(reverse("ecommerce:transaction_risk_assessment_list"))
    assessment_pks = {a.pk for a in res_assessments.context["assessments"]}
    assert ecom_risk_assessment_a.pk in assessment_pks
    assert ecom_risk_assessment_b.pk not in assessment_pks

    # Disputes list
    res_disputes = auth_client_a.get(reverse("ecommerce:chargeback_dispute_list"))
    dispute_pks = {d.pk for d in res_disputes.context["disputes"]}
    assert ecom_chargeback_dispute_a.pk in dispute_pks
    assert ecom_chargeback_dispute_b.pk not in dispute_pks

    # Alerts list
    res_alerts = auth_client_a.get(reverse("ecommerce:account_security_alert_list"))
    alert_pks = {al.pk for al in res_alerts.context["alerts"]}
    assert ecom_security_alert_a.pk in alert_pks
    assert ecom_security_alert_b.pk not in alert_pks


# ==============================================================================
# 2. Foreign FK Tampering Protection Tests (reject_foreign)
# ==============================================================================

def test_fraudrisk_fk_tampering_risk_assessment(auth_client_a, tenant_a, tenant_b):
    """Cross-tenant ForeignKeys for order and customer_party are rejected by reject_foreign."""
    currency = _fraudrisk_get_currency()
    party_b = Party.objects.create(tenant=tenant_b, name="Tenant B Foreign Party")
    order_b = _ordermanagement_order(tenant_b, customer=party_b, currency=currency)

    # 1. Form direct validation
    post_data = _fraudrisk_valid_assessment_data(
        currency=currency,
        order=order_b,
        customer_party=party_b,
    )
    form = TransactionRiskAssessmentForm(data=post_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "order" in form.errors
    assert "customer_party" in form.errors

    # 2. POST injection attempt through create view
    url = reverse("ecommerce:transaction_risk_assessment_create")
    resp = auth_client_a.post(url, post_data)
    # Form fails validation and re-renders form with 200 (not 302 redirect)
    assert resp.status_code == 200
    assert not TransactionRiskAssessment.objects.filter(tenant=tenant_a, order=order_b).exists()
    assert not TransactionRiskAssessment.objects.filter(tenant=tenant_a, customer_party=party_b).exists()


def test_fraudrisk_fk_tampering_chargeback_dispute(auth_client_a, tenant_a, tenant_b):
    """Cross-tenant ForeignKeys for order and customer_party on disputes are rejected."""
    currency = _fraudrisk_get_currency()
    party_b = Party.objects.create(tenant=tenant_b, name="Tenant B Dispute Party")
    order_b = _ordermanagement_order(tenant_b, customer=party_b, currency=currency)

    # 1. Form direct validation
    post_data = _fraudrisk_valid_dispute_data(
        currency=currency,
        order=order_b,
        customer_party=party_b,
    )
    form = ChargebackDisputeForm(data=post_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "order" in form.errors
    assert "customer_party" in form.errors

    # 2. POST injection attempt through create view
    url = reverse("ecommerce:chargeback_dispute_create")
    resp = auth_client_a.post(url, post_data)
    assert resp.status_code == 200
    assert not ChargebackDispute.objects.filter(tenant=tenant_a, order=order_b).exists()
    assert not ChargebackDispute.objects.filter(tenant=tenant_a, customer_party=party_b).exists()


def test_fraudrisk_fk_tampering_security_alert(auth_client_a, tenant_a, tenant_b):
    """Cross-tenant ForeignKey for party on security alerts is rejected."""
    party_b = Party.objects.create(tenant=tenant_b, name="Tenant B Alert Party")

    # 1. Form direct validation
    post_data = _fraudrisk_valid_alert_data(party=party_b)
    form = AccountSecurityAlertForm(data=post_data, tenant=tenant_a)
    assert not form.is_valid()
    assert "party" in form.errors

    # 2. POST injection attempt through create view
    url = reverse("ecommerce:account_security_alert_create")
    resp = auth_client_a.post(url, post_data)
    assert resp.status_code == 200
    assert not AccountSecurityAlert.objects.filter(tenant=tenant_a, party=party_b).exists()


# ==============================================================================
# 3. Authentication Gates Tests (Anonymous Redirects)
# ==============================================================================

def test_fraudrisk_unauthenticated_redirects(
    client,
    ecom_fraud_rule_a,
    ecom_risk_assessment_a,
    ecom_chargeback_dispute_a,
    ecom_security_alert_a,
):
    """Anonymous requests to all 9.18 endpoints redirect to login (302)."""
    endpoints = [
        # Hub
        reverse("ecommerce:fraud_risk_hub"),
        # FraudRules
        reverse("ecommerce:fraud_rule_list"),
        reverse("ecommerce:fraud_rule_create"),
        reverse("ecommerce:fraud_rule_detail", args=[ecom_fraud_rule_a.pk]),
        reverse("ecommerce:fraud_rule_edit", args=[ecom_fraud_rule_a.pk]),
        reverse("ecommerce:fraud_rule_delete", args=[ecom_fraud_rule_a.pk]),
        # TransactionRiskAssessments
        reverse("ecommerce:transaction_risk_assessment_list"),
        reverse("ecommerce:transaction_risk_assessment_create"),
        reverse("ecommerce:transaction_risk_assessment_detail", args=[ecom_risk_assessment_a.pk]),
        reverse("ecommerce:transaction_risk_assessment_edit", args=[ecom_risk_assessment_a.pk]),
        reverse("ecommerce:transaction_risk_assessment_delete", args=[ecom_risk_assessment_a.pk]),
        # ChargebackDisputes
        reverse("ecommerce:chargeback_dispute_list"),
        reverse("ecommerce:chargeback_dispute_create"),
        reverse("ecommerce:chargeback_dispute_detail", args=[ecom_chargeback_dispute_a.pk]),
        reverse("ecommerce:chargeback_dispute_edit", args=[ecom_chargeback_dispute_a.pk]),
        reverse("ecommerce:chargeback_dispute_delete", args=[ecom_chargeback_dispute_a.pk]),
        # AccountSecurityAlerts
        reverse("ecommerce:account_security_alert_list"),
        reverse("ecommerce:account_security_alert_create"),
        reverse("ecommerce:account_security_alert_detail", args=[ecom_security_alert_a.pk]),
        reverse("ecommerce:account_security_alert_edit", args=[ecom_security_alert_a.pk]),
        reverse("ecommerce:account_security_alert_delete", args=[ecom_security_alert_a.pk]),
    ]

    for url in endpoints:
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 redirect for {url}, got {resp.status_code}"
        assert "/accounts/login/" in resp.url or "/login/" in resp.url


# ==============================================================================
# 4. HTTP Method Safety Tests (@require_POST)
# ==============================================================================

def test_fraudrisk_method_safety_delete_endpoints_reject_get(
    auth_client_a,
    ecom_fraud_rule_a,
    ecom_risk_assessment_a,
    ecom_chargeback_dispute_a,
    ecom_security_alert_a,
):
    """GET requests to all 4 delete endpoints return 405 Method Not Allowed."""
    delete_endpoints = [
        reverse("ecommerce:fraud_rule_delete", args=[ecom_fraud_rule_a.pk]),
        reverse("ecommerce:transaction_risk_assessment_delete", args=[ecom_risk_assessment_a.pk]),
        reverse("ecommerce:chargeback_dispute_delete", args=[ecom_chargeback_dispute_a.pk]),
        reverse("ecommerce:account_security_alert_delete", args=[ecom_security_alert_a.pk]),
    ]

    for url in delete_endpoints:
        resp = auth_client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 Method Not Allowed for GET {url}, got {resp.status_code}"


# ==============================================================================
# 5. System Field Protection Tests (Mass Assignment Hardening)
# ==============================================================================

def test_fraudrisk_system_field_protection_fraud_rule(auth_client_a, tenant_a, tenant_b):
    """Attempted mass assignment of tenant, number, and timestamps via POST is ignored."""
    payload = _fraudrisk_valid_rule_data(
        name="Mass Assignment Hardened Rule",
        rule_code="R-MASS-01",
        tenant=tenant_b.pk,
        number="MALICIOUS-NUM-999",
        created_at="2020-01-01T00:00:00Z",
        updated_at="2020-01-01T00:00:00Z",
    )
    url = reverse("ecommerce:fraud_rule_create")
    resp = auth_client_a.post(url, payload)
    assert resp.status_code == 302

    created_rule = FraudRule.objects.get(tenant=tenant_a, rule_code="R-MASS-01")
    assert created_rule.tenant == tenant_a
    assert created_rule.number.startswith("EFRR-")
    assert created_rule.number != "MALICIOUS-NUM-999"


def test_fraudrisk_system_field_protection_risk_assessment(auth_client_a, tenant_a, tenant_b, user_b):
    """Attempted mass assignment of tenant, number, analyst_user, and timestamps is ignored."""
    currency = _fraudrisk_get_currency()
    payload = _fraudrisk_valid_assessment_data(
        currency=currency,
        device_fingerprint="dfp_mass_assign_test",
        tenant=tenant_b.pk,
        number="MALICIOUS-ASSESS-999",
        analyst_user=user_b.pk,
        reviewed_at="2020-01-01T00:00:00Z",
    )
    url = reverse("ecommerce:transaction_risk_assessment_create")
    resp = auth_client_a.post(url, payload)
    assert resp.status_code == 302

    created_assessment = TransactionRiskAssessment.objects.get(
        tenant=tenant_a,
        device_fingerprint="dfp_mass_assign_test",
    )
    assert created_assessment.tenant == tenant_a
    assert created_assessment.number.startswith("ETRA-")
    assert created_assessment.number != "MALICIOUS-ASSESS-999"
    assert created_assessment.analyst_user is None
    assert created_assessment.reviewed_at is None


def test_fraudrisk_system_field_protection_chargeback_dispute(auth_client_a, tenant_a, tenant_b):
    """Attempted mass assignment of tenant, number, and timestamps on disputes is ignored."""
    currency = _fraudrisk_get_currency()
    party_a = Party.objects.create(tenant=tenant_a, name="Acme Dispute Party")
    order_a = _ordermanagement_order(tenant_a, customer=party_a, currency=currency)

    payload = _fraudrisk_valid_dispute_data(
        currency=currency,
        order=order_a,
        customer_party=party_a,
        gateway_dispute_id="dp_sec_mass_918",
        tenant=tenant_b.pk,
        number="MALICIOUS-DISPUTE-999",
        resolved_at="2020-01-01T00:00:00Z",
        representment_submitted_at="2020-01-01T00:00:00Z",
    )
    url = reverse("ecommerce:chargeback_dispute_create")
    resp = auth_client_a.post(url, payload)
    assert resp.status_code == 302

    created_dispute = ChargebackDispute.objects.get(tenant=tenant_a, gateway_dispute_id="dp_sec_mass_918")
    assert created_dispute.tenant == tenant_a
    assert created_dispute.number.startswith("ECBD-")
    assert created_dispute.number != "MALICIOUS-DISPUTE-999"
    assert created_dispute.resolved_at is None
    assert created_dispute.representment_submitted_at is None


def test_fraudrisk_system_field_protection_security_alert(auth_client_a, tenant_a, tenant_b, user_b):
    """Attempted mass assignment of tenant, number, and resolved_by on alerts is ignored."""
    party_a = Party.objects.create(tenant=tenant_a, name="Acme Alert Party")
    payload = _fraudrisk_valid_alert_data(
        party=party_a,
        incident_details="Mass assignment alert test incident",
        tenant=tenant_b.pk,
        number="MALICIOUS-ALERT-999",
        resolved_by=user_b.pk,
        resolved_at="2020-01-01T00:00:00Z",
    )
    url = reverse("ecommerce:account_security_alert_create")
    resp = auth_client_a.post(url, payload)
    assert resp.status_code == 302

    created_alert = AccountSecurityAlert.objects.get(
        tenant=tenant_a,
        incident_details="Mass assignment alert test incident",
    )
    assert created_alert.tenant == tenant_a
    assert created_alert.number.startswith("EASA-")
    assert created_alert.number != "MALICIOUS-ALERT-999"
    assert created_alert.resolved_by is None
    assert created_alert.resolved_at is None


# ==============================================================================
# 6. Forensic Audit Logging Tests
# ==============================================================================

def test_fraudrisk_audit_log_fraud_rule_lifecycle(auth_client_a, tenant_a, admin_user):
    """AuditLog records create, update, and delete actions for FraudRule."""
    # 1. CREATE
    create_url = reverse("ecommerce:fraud_rule_create")
    payload = _fraudrisk_valid_rule_data(name="Audit Lifecycle Rule", rule_code="R-AUD-RULE-01")
    resp_create = auth_client_a.post(create_url, payload)
    assert resp_create.status_code == 302

    rule = FraudRule.objects.get(tenant=tenant_a, rule_code="R-AUD-RULE-01")
    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=rule.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("name") == "Audit Lifecycle Rule"

    # 2. UPDATE
    edit_url = reverse("ecommerce:fraud_rule_edit", args=[rule.pk])
    payload["name"] = "Audit Lifecycle Rule Updated"
    resp_edit = auth_client_a.post(edit_url, payload)
    assert resp_edit.status_code == 302

    rule.refresh_from_db()
    assert rule.name == "Audit Lifecycle Rule Updated"

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=rule.pk,
    ).first()
    assert log_update is not None
    assert log_update.changes.get("name") == "Audit Lifecycle Rule Updated"

    # 3. DELETE
    delete_url = reverse("ecommerce:fraud_rule_delete", args=[rule.pk])
    resp_delete = auth_client_a.post(delete_url)
    assert resp_delete.status_code == 302
    assert not FraudRule.objects.filter(pk=rule.pk).exists()

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=rule.pk,
    ).first()
    assert log_delete is not None
    assert log_delete.changes.get("name") == "Audit Lifecycle Rule Updated"


def test_fraudrisk_audit_log_risk_assessment_lifecycle(auth_client_a, tenant_a, admin_user):
    """AuditLog records create, update, and delete actions for TransactionRiskAssessment."""
    currency = _fraudrisk_get_currency()

    # 1. CREATE
    create_url = reverse("ecommerce:transaction_risk_assessment_create")
    payload = _fraudrisk_valid_assessment_data(
        currency=currency,
        device_fingerprint="dfp_audit_assess_01",
    )
    resp_create = auth_client_a.post(create_url, payload)
    assert resp_create.status_code == 302

    assessment = TransactionRiskAssessment.objects.get(
        tenant=tenant_a,
        device_fingerprint="dfp_audit_assess_01",
    )
    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=assessment.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("actual_decision") == "pending"
    assert log_create.changes.get("risk_score") == 45

    # 2. UPDATE
    edit_url = reverse("ecommerce:transaction_risk_assessment_edit", args=[assessment.pk])
    payload["actual_decision"] = "approved_manual"
    payload["analyst_notes"] = "Verified customer identity manually."
    resp_edit = auth_client_a.post(edit_url, payload)
    assert resp_edit.status_code == 302

    assessment.refresh_from_db()
    assert assessment.actual_decision == "approved_manual"

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=assessment.pk,
    ).first()
    assert log_update is not None
    assert log_update.changes.get("actual_decision") == "approved_manual"

    # 3. DELETE
    delete_url = reverse("ecommerce:transaction_risk_assessment_delete", args=[assessment.pk])
    resp_delete = auth_client_a.post(delete_url)
    assert resp_delete.status_code == 302
    assert not TransactionRiskAssessment.objects.filter(pk=assessment.pk).exists()

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=assessment.pk,
    ).first()
    assert log_delete is not None
    assert log_delete.changes.get("number") == assessment.number


def test_fraudrisk_audit_log_chargeback_dispute_lifecycle(auth_client_a, tenant_a, admin_user):
    """AuditLog records create, update, and delete actions for ChargebackDispute."""
    currency = _fraudrisk_get_currency()
    party_a = Party.objects.create(tenant=tenant_a, name="Acme Dispute Party")
    order_a = _ordermanagement_order(tenant_a, customer=party_a, currency=currency)

    # 1. CREATE
    create_url = reverse("ecommerce:chargeback_dispute_create")
    payload = _fraudrisk_valid_dispute_data(
        currency=currency,
        order=order_a,
        customer_party=party_a,
        gateway_dispute_id="dp_audit_dispute_01",
    )
    resp_create = auth_client_a.post(create_url, payload)
    assert resp_create.status_code == 302

    dispute = ChargebackDispute.objects.get(tenant=tenant_a, gateway_dispute_id="dp_audit_dispute_01")
    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=dispute.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("stage") == "needs_response"
    assert log_create.changes.get("dispute_amount") == "120.00"

    # 2. UPDATE
    edit_url = reverse("ecommerce:chargeback_dispute_edit", args=[dispute.pk])
    payload["stage"] = "under_review"
    payload["representment_notes"] = "Submitted signed delivery proof."
    resp_edit = auth_client_a.post(edit_url, payload)
    assert resp_edit.status_code == 302

    dispute.refresh_from_db()
    assert dispute.stage == "under_review"

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=dispute.pk,
    ).first()
    assert log_update is not None
    assert log_update.changes.get("stage") == "under_review"

    # 3. DELETE
    delete_url = reverse("ecommerce:chargeback_dispute_delete", args=[dispute.pk])
    resp_delete = auth_client_a.post(delete_url)
    assert resp_delete.status_code == 302
    assert not ChargebackDispute.objects.filter(pk=dispute.pk).exists()

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=dispute.pk,
    ).first()
    assert log_delete is not None
    assert log_delete.changes.get("number") == dispute.number


def test_fraudrisk_audit_log_security_alert_lifecycle(auth_client_a, tenant_a, admin_user):
    """AuditLog records create, update, and delete actions for AccountSecurityAlert."""
    party_a = Party.objects.create(tenant=tenant_a, name="Acme Alert Audit Party")

    # 1. CREATE
    create_url = reverse("ecommerce:account_security_alert_create")
    payload = _fraudrisk_valid_alert_data(
        party=party_a,
        incident_details="Audit log lifecycle alert test",
    )
    resp_create = auth_client_a.post(create_url, payload)
    assert resp_create.status_code == 302

    alert = AccountSecurityAlert.objects.get(
        tenant=tenant_a,
        incident_details="Audit log lifecycle alert test",
    )
    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=alert.pk,
    ).first()
    assert log_create is not None
    assert log_create.changes.get("alert_type") == "credential_stuffing"
    assert log_create.changes.get("status") == "new"

    # 2. UPDATE
    edit_url = reverse("ecommerce:account_security_alert_edit", args=[alert.pk])
    payload["status"] = "investigating"
    payload["investigation_notes"] = "Contacted user to confirm login legitimacy."
    resp_edit = auth_client_a.post(edit_url, payload)
    assert resp_edit.status_code == 302

    alert.refresh_from_db()
    assert alert.status == "investigating"

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=alert.pk,
    ).first()
    assert log_update is not None
    assert log_update.changes.get("status") == "investigating"

    # 3. DELETE
    delete_url = reverse("ecommerce:account_security_alert_delete", args=[alert.pk])
    resp_delete = auth_client_a.post(delete_url)
    assert resp_delete.status_code == 302
    assert not AccountSecurityAlert.objects.filter(pk=alert.pk).exists()

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=alert.pk,
    ).first()
    assert log_delete is not None
    assert log_delete.changes.get("number") == alert.number


def test_fraudrisk_audit_log_tenant_isolation(
    auth_client_a,
    auth_client_b,
    tenant_a,
    tenant_b,
    admin_user,
):
    """AuditLog records created by Tenant A actions are isolated and not visible under Tenant B."""
    create_url = reverse("ecommerce:fraud_rule_create")
    payload = _fraudrisk_valid_rule_data(name="Tenant Isolation Audit Rule", rule_code="R-AUD-ISO-01")
    resp = auth_client_a.post(create_url, payload)
    assert resp.status_code == 302

    rule = FraudRule.objects.get(tenant=tenant_a, rule_code="R-AUD-ISO-01")

    # Assert Tenant A log exists
    log_a = AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=rule.pk).first()
    assert log_a is not None
    assert log_a.tenant == tenant_a

    # Assert Tenant B has no audit logs for Tenant A's created entity
    log_b = AuditLog.objects.filter(tenant=tenant_b, object_id=rule.pk).first()
    assert log_b is None
