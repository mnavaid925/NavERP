"""Tests for eCommerce 9.18 Fraud & Risk Management Forms.

Covers:
1. test_fraudrisk_forms_field_exclusions: assert tenant, number, created_at, updated_at,
   reviewed_at, resolved_at, and excluded attribution fields (analyst_user, resolved_by)
   are NOT in form fields.
2. test_fraudrisk_fraud_rule_form_validation: valid submission, invalid inputs (missing
   required fields, empty threshold value, priority bounds).
3. test_fraudrisk_transaction_risk_assessment_form_validation: valid submission, score validation
   (0-100), user queryset tenant scoping (asserting foreign tenant user is not in queryset, I1),
   negative transaction amount, and reject_foreign validation when submitting foreign order/party (I2).
4. test_fraudrisk_chargeback_dispute_form_validation: valid submission, negative amount/fee validations,
   and reject_foreign cross-tenant rejection for foreign customer party and order (I2).
5. test_fraudrisk_account_security_alert_form_validation: valid submission, user/investigator tenant
   scoping (I1), and reject_foreign cross-tenant rejection for foreign party (I2).

Conventions enforced:
- Test functions: test_fraudrisk_*
- Local helpers: _fraudrisk_*
"""
from decimal import Decimal
import pytest

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models.Party import Party
from apps.ecommerce.forms.FraudRisk import (
    FraudRuleForm,
    TransactionRiskAssessmentForm,
    ChargebackDisputeForm,
    AccountSecurityAlertForm,
)
from apps.ecommerce.forms._common import reject_foreign
from apps.ecommerce.models import (
    FraudRule,
    TransactionRiskAssessment,
    ChargebackDispute,
    AccountSecurityAlert,
)
from apps.ecommerce.tests.conftest import _ordermanagement_order


pytestmark = pytest.mark.django_db


def _fraudrisk_get_currency_usd():
    """Local helper to fetch or create active USD currency."""
    currency = Currency.objects.filter(code="USD").first()
    if not currency:
        currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$", is_active=True)
    return currency


# ==============================================================================
# 1. Form Field Exclusions Test
# ==============================================================================

def test_fraudrisk_forms_field_exclusions(tenant_a):
    """Assert tenant, number, created_at, updated_at, reviewed_at, resolved_at,
    and excluded attribution fields (analyst_user, resolved_by) are NOT in form fields."""
    rule_form = FraudRuleForm(tenant=tenant_a)
    for field in ["tenant", "number", "created_at", "updated_at"]:
        assert field not in rule_form.fields, f"{field} exposed in FraudRuleForm"

    assessment_form = TransactionRiskAssessmentForm(tenant=tenant_a)
    for field in ["tenant", "number", "created_at", "updated_at", "reviewed_at", "analyst_user"]:
        assert field not in assessment_form.fields, f"{field} exposed in TransactionRiskAssessmentForm"

    dispute_form = ChargebackDisputeForm(tenant=tenant_a)
    for field in ["tenant", "number", "created_at", "updated_at", "representment_submitted_at", "resolved_at"]:
        assert field not in dispute_form.fields, f"{field} exposed in ChargebackDisputeForm"

    alert_form = AccountSecurityAlertForm(tenant=tenant_a)
    for field in ["tenant", "number", "created_at", "updated_at", "resolved_at", "resolved_by"]:
        assert field not in alert_form.fields, f"{field} exposed in AccountSecurityAlertForm"


# ==============================================================================
# 2. FraudRuleForm Validation Test
# ==============================================================================

def test_fraudrisk_fraud_rule_form_validation(tenant_a):
    """Test FraudRuleForm valid submission and invalid inputs (missing required fields,
    empty threshold, priority bounds)."""
    # 1. Valid submission
    valid_data = {
        "name": "High Velocity Orders Rule",
        "rule_code": "R-VEL-01",
        "rule_scope": "checkout",
        "rule_type": "velocity_orders",
        "condition_operator": "gt",
        "threshold_value": "5",
        "risk_score_impact": 25,
        "action_to_take": "flag_review",
        "priority": 10,
        "is_active": True,
        "description": "Trigger manual review if rapid purchases detected.",
    }
    form = FraudRuleForm(data=valid_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    rule = form.save()
    assert rule.pk is not None
    assert rule.tenant == tenant_a
    assert rule.name == "High Velocity Orders Rule"
    assert rule.rule_code == "R-VEL-01"
    assert rule.threshold_value == "5"
    assert rule.risk_score_impact == 25
    assert rule.priority == 10

    # 2. Missing required field (name)
    data_missing = valid_data.copy()
    data_missing["name"] = ""
    form_missing = FraudRuleForm(data=data_missing, tenant=tenant_a)
    assert not form_missing.is_valid()
    assert "name" in form_missing.errors

    # 3. Empty or whitespace-only threshold_value
    data_empty_thresh = valid_data.copy()
    data_empty_thresh["threshold_value"] = "   "
    form_empty_thresh = FraudRuleForm(data=data_empty_thresh, tenant=tenant_a)
    assert not form_empty_thresh.is_valid()
    assert "threshold_value" in form_empty_thresh.errors

    # 4. Priority lower than 1 (bound check)
    data_prio_zero = valid_data.copy()
    data_prio_zero["priority"] = 0
    form_prio_zero = FraudRuleForm(data=data_prio_zero, tenant=tenant_a)
    assert not form_prio_zero.is_valid()
    assert "priority" in form_prio_zero.errors
    assert "must be 1 or higher" in str(form_prio_zero.errors["priority"])

    data_prio_neg = valid_data.copy()
    data_prio_neg["priority"] = -5
    form_prio_neg = FraudRuleForm(data=data_prio_neg, tenant=tenant_a)
    assert not form_prio_neg.is_valid()
    assert "priority" in form_prio_neg.errors


# ==============================================================================
# 3. TransactionRiskAssessmentForm Validation Test
# ==============================================================================

def test_fraudrisk_transaction_risk_assessment_form_validation(tenant_a, tenant_b, user_a, user_b):
    """Test TransactionRiskAssessmentForm valid submission, score validation (0-100),
    user queryset tenant scoping (asserting foreign tenant user is not in queryset, I1),
    negative transaction amount, and reject_foreign validation on foreign order/party (I2)."""
    # 1. User queryset tenant scoping (I1)
    form_unbound = TransactionRiskAssessmentForm(tenant=tenant_a)
    assert user_a in form_unbound.fields["user"].queryset
    assert user_b not in form_unbound.fields["user"].queryset

    # 2. Valid submission
    party_a = Party.objects.create(tenant=tenant_a, name="Acme Customer Party")
    order_a = _ordermanagement_order(tenant_a, customer=party_a)
    currency = _fraudrisk_get_currency_usd()

    valid_data = {
        "order": order_a.pk,
        "customer_party": party_a.pk,
        "user": user_a.pk,
        "transaction_amount": "249.99",
        "currency": currency.pk,
        "risk_score": 60,
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
        "device_fingerprint": "dfp_alpha_001",
        "velocity_count_24h": 2,
        "risk_factors_summary": "Moderate velocity from recognized IP",
        "analyst_notes": "Queued for routine review",
    }
    form = TransactionRiskAssessmentForm(data=valid_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assessment = form.save()
    assert assessment.pk is not None
    assert assessment.tenant == tenant_a
    assert assessment.risk_score == 60
    assert assessment.transaction_amount == Decimal("249.99")
    assert assessment.order == order_a
    assert assessment.customer_party == party_a

    # 3. Score validation: > 100 or < 0
    data_score_high = valid_data.copy()
    data_score_high["risk_score"] = 101
    form_score_high = TransactionRiskAssessmentForm(data=data_score_high, tenant=tenant_a)
    assert not form_score_high.is_valid()
    assert "risk_score" in form_score_high.errors
    assert "between 0 and 100" in str(form_score_high.errors["risk_score"])

    data_score_neg = valid_data.copy()
    data_score_neg["risk_score"] = -1
    form_score_neg = TransactionRiskAssessmentForm(data=data_score_neg, tenant=tenant_a)
    assert not form_score_neg.is_valid()
    assert "risk_score" in form_score_neg.errors
    assert "between 0 and 100" in str(form_score_neg.errors["risk_score"])

    # 4. Negative transaction amount validation
    data_amt_neg = valid_data.copy()
    data_amt_neg["transaction_amount"] = "-15.00"
    form_amt_neg = TransactionRiskAssessmentForm(data=data_amt_neg, tenant=tenant_a)
    assert not form_amt_neg.is_valid()
    assert "transaction_amount" in form_amt_neg.errors
    assert "cannot be negative" in str(form_amt_neg.errors["transaction_amount"])

    # 5. reject_foreign validation: foreign order (I2)
    party_b = Party.objects.create(tenant=tenant_b, name="Globex Foreign Customer")
    order_b = _ordermanagement_order(tenant_b, customer=party_b)

    data_foreign_order = valid_data.copy()
    data_foreign_order["order"] = order_b.pk
    form_foreign_order = TransactionRiskAssessmentForm(data=data_foreign_order, tenant=tenant_a)
    assert not form_foreign_order.is_valid()
    assert "order" in form_foreign_order.errors

    # 6. reject_foreign validation: foreign customer_party (I2)
    data_foreign_party = valid_data.copy()
    data_foreign_party["customer_party"] = party_b.pk
    form_foreign_party = TransactionRiskAssessmentForm(data=data_foreign_party, tenant=tenant_a)
    assert not form_foreign_party.is_valid()
    assert "customer_party" in form_foreign_party.errors

    # Direct reject_foreign check to verify error message contract
    bound_form = TransactionRiskAssessmentForm(data=valid_data, tenant=tenant_a)
    assert bound_form.is_valid()
    test_cleaned = {"order": order_b, "customer_party": party_b}
    reject_foreign(bound_form, test_cleaned, ["order", "customer_party"])
    assert "That record belongs to another workspace." in bound_form.errors["order"]
    assert "That record belongs to another workspace." in bound_form.errors["customer_party"]


# ==============================================================================
# 4. ChargebackDisputeForm Validation Test
# ==============================================================================

def test_fraudrisk_chargeback_dispute_form_validation(tenant_a, tenant_b):
    """Test ChargebackDisputeForm valid submission, negative amount/fee validations,
    and reject_foreign cross-tenant rejection for foreign customer party and order (I2)."""
    party_a = Party.objects.create(tenant=tenant_a, name="Acme Dispute Customer")
    order_a = _ordermanagement_order(tenant_a, customer=party_a)
    currency = _fraudrisk_get_currency_usd()

    # 1. Valid submission
    valid_data = {
        "order": order_a.pk,
        "customer_party": party_a.pk,
        "currency": currency.pk,
        "dispute_amount": "385.00",
        "dispute_fee": "15.00",
        "gateway_dispute_id": "dp_stripe_cb_9921",
        "payment_method_type": "credit_card",
        "card_brand": "Visa",
        "reason_category": "fraudulent",
        "reason_code": "10.4",
        "stage": "needs_response",
        "evidence_due_date": "2026-11-28",
        "evidence_summary": "Carrier proof of delivery to cardholder address.",
        "representment_notes": "Submitting signed receipt and AVS confirmation.",
        "outcome_notes": "",
    }
    form = ChargebackDisputeForm(data=valid_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    dispute = form.save()
    assert dispute.pk is not None
    assert dispute.tenant == tenant_a
    assert dispute.dispute_amount == Decimal("385.00")
    assert dispute.dispute_fee == Decimal("15.00")
    assert dispute.reason_code == "10.4"
    assert dispute.order == order_a

    # 2. Negative dispute_amount validation
    data_neg_dispute = valid_data.copy()
    data_neg_dispute["dispute_amount"] = "-50.00"
    form_neg_dispute = ChargebackDisputeForm(data=data_neg_dispute, tenant=tenant_a)
    assert not form_neg_dispute.is_valid()
    assert "dispute_amount" in form_neg_dispute.errors
    assert "cannot be negative" in str(form_neg_dispute.errors["dispute_amount"])

    # 3. Negative dispute_fee validation
    data_neg_fee = valid_data.copy()
    data_neg_fee["dispute_fee"] = "-5.00"
    form_neg_fee = ChargebackDisputeForm(data=data_neg_fee, tenant=tenant_a)
    assert not form_neg_fee.is_valid()
    assert "dispute_fee" in form_neg_fee.errors
    assert "cannot be negative" in str(form_neg_fee.errors["dispute_fee"])

    # 4. reject_foreign validation: foreign order and foreign customer party (I2)
    party_b = Party.objects.create(tenant=tenant_b, name="Globex Dispute Customer")
    order_b = _ordermanagement_order(tenant_b, customer=party_b)

    data_fo = valid_data.copy()
    data_fo["order"] = order_b.pk
    form_fo = ChargebackDisputeForm(data=data_fo, tenant=tenant_a)
    assert not form_fo.is_valid()
    assert "order" in form_fo.errors

    data_fp = valid_data.copy()
    data_fp["customer_party"] = party_b.pk
    form_fp = ChargebackDisputeForm(data=data_fp, tenant=tenant_a)
    assert not form_fp.is_valid()
    assert "customer_party" in form_fp.errors

    # Direct reject_foreign check
    bound_form = ChargebackDisputeForm(data=valid_data, tenant=tenant_a)
    assert bound_form.is_valid()
    test_cleaned = {"order": order_b, "customer_party": party_b}
    reject_foreign(bound_form, test_cleaned, ["order", "customer_party"])
    assert "That record belongs to another workspace." in bound_form.errors["order"]
    assert "That record belongs to another workspace." in bound_form.errors["customer_party"]


# ==============================================================================
# 5. AccountSecurityAlertForm Validation Test
# ==============================================================================

def test_fraudrisk_account_security_alert_form_validation(tenant_a, tenant_b, user_a, user_b):
    """Test AccountSecurityAlertForm valid submission, user/investigator tenant scoping (I1),
    and reject_foreign cross-tenant rejection for foreign party (I2)."""
    # 1. User & assigned_investigator tenant scoping (I1)
    form_unbound = AccountSecurityAlertForm(tenant=tenant_a)
    assert user_a in form_unbound.fields["user"].queryset
    assert user_b not in form_unbound.fields["user"].queryset
    assert user_a in form_unbound.fields["assigned_investigator"].queryset
    assert user_b not in form_unbound.fields["assigned_investigator"].queryset

    party_a = Party.objects.create(tenant=tenant_a, name="Acme Alert Customer")
    party_b = Party.objects.create(tenant=tenant_b, name="Globex Foreign Alert Party")
    assert party_a in form_unbound.fields["party"].queryset
    assert party_b not in form_unbound.fields["party"].queryset

    # 2. Valid submission
    valid_data = {
        "user": user_a.pk,
        "party": party_a.pk,
        "alert_type": "credential_stuffing",
        "severity": "critical",
        "status": "investigating",
        "automated_action_taken": "challenge_mfa",
        "ip_address": "203.0.113.195",
        "location_info": "Kyiv, Ukraine",
        "user_agent": "Mozilla/5.0 Security Scanner Bot",
        "incident_details": "15 failed password attempts in 60s from botnet IP.",
        "assigned_investigator": user_a.pk,
        "investigation_notes": "Notified user and required password reset.",
    }
    form = AccountSecurityAlertForm(data=valid_data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    alert = form.save()
    assert alert.pk is not None
    assert alert.tenant == tenant_a
    assert alert.alert_type == "credential_stuffing"
    assert alert.severity == "critical"
    assert alert.user == user_a
    assert alert.party == party_a

    # 3. reject_foreign validation: foreign party (I2)
    data_fp = valid_data.copy()
    data_fp["party"] = party_b.pk
    form_fp = AccountSecurityAlertForm(data=data_fp, tenant=tenant_a)
    assert not form_fp.is_valid()
    assert "party" in form_fp.errors

    # Direct reject_foreign check
    bound_form = AccountSecurityAlertForm(data=valid_data, tenant=tenant_a)
    assert bound_form.is_valid()
    test_cleaned = {"party": party_b}
    reject_foreign(bound_form, test_cleaned, ["party"])
    assert "That record belongs to another workspace." in bound_form.errors["party"]
