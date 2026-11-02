"""Tests for eCommerce 9.18 Fraud & Risk Management Models.

Covers:
1. test_fraudrisk_model_fields_contract: Assert field names match FRAUDRISK_MODEL_FIELDS for all 4 models.
2. test_fraudrisk_model_choices_contract: Assert choice tuples match FRAUDRISK_CHOICES.
3. test_fraudrisk_model_numbering_and_str: Assert TenantNumbered prefixes (EFRR-, ETRA-, ECBD-, EASA-) and string representations.
4. test_fraudrisk_model_tenant_isolation_and_uniqueness: Assert unique tenant numbering constraint and tenant isolation.
5. test_fraudrisk_model_defaults_and_cascade: Assert default values, foreign key cascades, and nullable behaviors.
6. test_fraudrisk_model_meta_indexes: Assert composite index ["tenant", "-created_at"] exists on TransactionRiskAssessment, ChargebackDispute, and AccountSecurityAlert.
"""
from decimal import Decimal
import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models import Party
from apps.ecommerce.models import (
    FraudRule,
    TransactionRiskAssessment,
    ChargebackDispute,
    AccountSecurityAlert,
)
from apps.ecommerce.tests.conftest import (
    FRAUDRISK_MODEL_FIELDS,
    FRAUDRISK_CHOICES,
    _fraudrisk_fraud_rule,
    _fraudrisk_transaction_risk_assessment,
    _fraudrisk_chargeback_dispute,
    _fraudrisk_account_security_alert,
    _ordermanagement_order,
)


pytestmark = pytest.mark.django_db


# ==============================================================================
# 1. Model Fields Contract Tests
# ==============================================================================

def test_fraudrisk_model_fields_contract():
    """Verify all 4 Fraud & Risk models contain expected fields from the contract."""
    for model_cls, model_name in [
        (FraudRule, "FraudRule"),
        (TransactionRiskAssessment, "TransactionRiskAssessment"),
        (ChargebackDispute, "ChargebackDispute"),
        (AccountSecurityAlert, "AccountSecurityAlert"),
    ]:
        field_names = {f.name for f in model_cls._meta.get_fields()}
        expected_fields = FRAUDRISK_MODEL_FIELDS[model_name]
        for field in expected_fields:
            assert field in field_names, f"Model {model_name} missing contract field: '{field}'"


# ==============================================================================
# 2. Model Choices Contract Tests
# ==============================================================================

def test_fraudrisk_model_choices_contract():
    """Verify choices on all models match contract constants in FRAUDRISK_CHOICES."""
    model_mapping = {
        "FraudRule": FraudRule,
        "TransactionRiskAssessment": TransactionRiskAssessment,
        "ChargebackDispute": ChargebackDispute,
        "AccountSecurityAlert": AccountSecurityAlert,
    }
    for model_name, field_dict in FRAUDRISK_CHOICES.items():
        model_cls = model_mapping[model_name]
        for field_name, expected_choices in field_dict.items():
            field_obj = model_cls._meta.get_field(field_name)
            assert tuple(field_obj.choices) == expected_choices, (
                f"Choices mismatch for {model_name}.{field_name}"
            )


# ==============================================================================
# 3. Model Numbering and __str__ Tests
# ==============================================================================

def test_fraudrisk_model_numbering_and_str(tenant_a, user_a):
    """Test TenantNumbered sequencing prefixes and __str__ for all 4 models."""
    party_a = Party.objects.filter(tenant=tenant_a).first()
    if not party_a:
        party_a = Party.objects.create(tenant=tenant_a, name="Acme Test Party")

    # 1. FraudRule (Prefix: EFRR-)
    rule = _fraudrisk_fraud_rule(
        tenant_a,
        name="Suspicious Velocity Check",
        rule_scope="checkout",
    )
    assert rule.number.startswith("EFRR-")
    assert rule.number in str(rule)
    assert "Suspicious Velocity Check" in str(rule)
    assert "Checkout / Payment" in str(rule)

    # 2. TransactionRiskAssessment (Prefix: ETRA-)
    assessment = _fraudrisk_transaction_risk_assessment(
        tenant_a,
        customer_party=party_a,
        risk_score=75,
        risk_tier="high",
    )
    assert assessment.number.startswith("ETRA-")
    assert assessment.number in str(assessment)
    assert "75" in str(assessment)
    assert "High Risk" in str(assessment)

    # 3. ChargebackDispute (Prefix: ECBD-)
    order = _ordermanagement_order(tenant_a, customer=party_a)
    dispute = _fraudrisk_chargeback_dispute(
        tenant_a,
        order=order,
        customer_party=party_a,
        dispute_amount=Decimal("250.00"),
        reason_category="fraudulent",
    )
    assert dispute.number.startswith("ECBD-")
    assert dispute.number in str(dispute)
    assert "Fraudulent" in str(dispute)
    assert "250.00" in str(dispute)

    # 4. AccountSecurityAlert (Prefix: EASA-)
    alert = _fraudrisk_account_security_alert(
        tenant_a,
        party=party_a,
        user=user_a,
        alert_type="credential_stuffing",
        severity="critical",
    )
    assert alert.number.startswith("EASA-")
    assert alert.number in str(alert)
    assert "Credential Stuffing" in str(alert)
    assert "Critical" in str(alert)


# ==============================================================================
# 4. Tenant Isolation and Uniqueness Tests
# ==============================================================================

def test_fraudrisk_model_tenant_isolation_and_uniqueness(tenant_a, tenant_b, user_a, user_b):
    """Test tenant isolation and unique numbering constraint per tenant."""
    party_a = Party.objects.create(tenant=tenant_a, name="Acme Security Party")
    party_b = Party.objects.create(tenant=tenant_b, name="Globex Security Party")

    rule_a = _fraudrisk_fraud_rule(tenant_a, name="Acme Only Rule")
    rule_b = _fraudrisk_fraud_rule(tenant_b, name="Globex Only Rule")

    # Tenant isolation queries
    tenant_a_rules = FraudRule.objects.filter(tenant=tenant_a)
    assert rule_a in tenant_a_rules
    assert rule_b not in tenant_a_rules

    tenant_b_rules = FraudRule.objects.filter(tenant=tenant_b)
    assert rule_b in tenant_b_rules
    assert rule_a not in tenant_b_rules

    assessment_a = _fraudrisk_transaction_risk_assessment(tenant_a, customer_party=party_a)
    assessment_b = _fraudrisk_transaction_risk_assessment(tenant_b, customer_party=party_b)

    assert assessment_a in TransactionRiskAssessment.objects.filter(tenant=tenant_a)
    assert assessment_b not in TransactionRiskAssessment.objects.filter(tenant=tenant_a)

    dispute_a = _fraudrisk_chargeback_dispute(tenant_a, customer_party=party_a)
    dispute_b = _fraudrisk_chargeback_dispute(tenant_b, customer_party=party_b)

    assert dispute_a in ChargebackDispute.objects.filter(tenant=tenant_a)
    assert dispute_b not in ChargebackDispute.objects.filter(tenant=tenant_a)

    alert_a = _fraudrisk_account_security_alert(tenant_a, party=party_a, user=user_a)
    alert_b = _fraudrisk_account_security_alert(tenant_b, party=party_b, user=user_b)

    assert alert_a in AccountSecurityAlert.objects.filter(tenant=tenant_a)
    assert alert_b not in AccountSecurityAlert.objects.filter(tenant=tenant_a)

    # Unique constraint on (tenant, number)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FraudRule.objects.create(
                tenant=tenant_a,
                number=rule_a.number,
                name="Duplicate Number Rule",
                threshold_value="5",
            )

    # Cross-tenant same number is allowed
    cross_tenant_rule = FraudRule.objects.create(
        tenant=tenant_b,
        number=rule_a.number,
        name="Cross-Tenant Reused Number Rule",
        threshold_value="5",
    )
    assert cross_tenant_rule.pk is not None
    assert cross_tenant_rule.number == rule_a.number
    assert cross_tenant_rule.tenant != rule_a.tenant


# ==============================================================================
# 5. Defaults and Cascade Tests
# ==============================================================================

def test_fraudrisk_model_defaults_and_cascade(tenant_a, user_a):
    """Test model field defaults, nullable foreign keys, and protect/cascade behaviors."""
    # Test FraudRule defaults
    rule = FraudRule.objects.create(
        tenant=tenant_a,
        name="Minimal Rule",
        threshold_value="100",
    )
    assert rule.rule_code == ""
    assert rule.rule_scope == "checkout"
    assert rule.rule_type == "velocity_orders"
    assert rule.condition_operator == "gt"
    assert rule.risk_score_impact == 20
    assert rule.action_to_take == "flag_review"
    assert rule.priority == 10
    assert rule.is_active is True
    assert rule.description == ""

    # Test TransactionRiskAssessment defaults and SET_NULL on user deletion
    currency = Currency.objects.filter(code="USD").first()
    if not currency:
        currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$")

    assessment = TransactionRiskAssessment.objects.create(
        tenant=tenant_a,
        currency=currency,
        user=user_a,
    )
    assert assessment.transaction_amount == Decimal("0.00")
    assert assessment.risk_score == 0
    assert assessment.risk_tier == "low"
    assert assessment.recommended_action == "approve"
    assert assessment.actual_decision == "pending"
    assert assessment.avs_result_code == "not_checked"
    assert assessment.cvv_result_code == "not_checked"
    assert assessment.billing_country == ""
    assert assessment.ip_country == ""
    assert assessment.is_geo_mismatch is False
    assert assessment.is_proxy_or_vpn is False
    assert assessment.device_fingerprint == ""
    assert assessment.velocity_count_24h == 1
    assert assessment.risk_factors_summary == ""
    assert assessment.analyst_notes == ""
    assert assessment.reviewed_at is None
    assert assessment.order is None
    assert assessment.customer_party is None
    assert assessment.user == user_a

    # Test currency PROTECT constraint on TransactionRiskAssessment
    with pytest.raises(ProtectedError):
        currency.delete()

    # Test ChargebackDispute defaults and PROTECT constraints
    order = _ordermanagement_order(tenant_a)
    dispute = ChargebackDispute.objects.create(
        tenant=tenant_a,
        order=order,
        currency=currency,
    )
    assert dispute.dispute_amount == Decimal("0.00")
    assert dispute.dispute_fee == Decimal("15.00")
    assert dispute.gateway_dispute_id == ""
    assert dispute.payment_method_type == "credit_card"
    assert dispute.card_brand == ""
    assert dispute.reason_category == "fraudulent"
    assert dispute.reason_code == ""
    assert dispute.stage == "needs_response"
    assert dispute.evidence_due_date is None
    assert dispute.evidence_summary == ""
    assert dispute.representment_notes == ""
    assert dispute.outcome_notes == ""

    # Order is PROTECT on ChargebackDispute
    with pytest.raises(ProtectedError):
        order.delete()

    # Test AccountSecurityAlert defaults
    alert = AccountSecurityAlert.objects.create(
        tenant=tenant_a,
        user=user_a,
    )
    assert alert.alert_type == "suspicious_login"
    assert alert.severity == "medium"
    assert alert.status == "new"
    assert alert.automated_action_taken == "none"
    assert alert.ip_address is None
    assert alert.location_info == ""
    assert alert.user_agent == ""
    assert alert.incident_details == ""
    assert alert.assigned_investigator is None
    assert alert.investigation_notes == ""
    assert alert.resolved_by is None
    assert alert.resolved_at is None


# ==============================================================================
# 6. Meta Indexes Tests
# ==============================================================================

def test_fraudrisk_model_meta_indexes():
    """Verify composite index ['tenant', '-created_at'] exists on target risk models."""
    target_models = [
        TransactionRiskAssessment,
        ChargebackDispute,
        AccountSecurityAlert,
    ]
    for model_cls in target_models:
        index_fields_list = [list(idx.fields) for idx in model_cls._meta.indexes]
        assert ["tenant", "-created_at"] in index_fields_list, (
            f"Model {model_cls.__name__} missing composite index ['tenant', '-created_at']. "
            f"Existing indexes: {index_fields_list}"
        )
