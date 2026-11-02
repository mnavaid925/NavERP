from apps.ecommerce.views.FraudRisk.FraudRules import (
    fraud_risk_hub,
    fraud_rule_list,
    fraud_rule_detail,
    fraud_rule_create,
    fraud_rule_edit,
    fraud_rule_delete,
)
from apps.ecommerce.views.FraudRisk.TransactionRiskAssessments import (
    transaction_risk_assessment_list,
    transaction_risk_assessment_detail,
    transaction_risk_assessment_create,
    transaction_risk_assessment_edit,
    transaction_risk_assessment_delete,
)
from apps.ecommerce.views.FraudRisk.ChargebackDisputes import (
    chargeback_dispute_list,
    chargeback_dispute_detail,
    chargeback_dispute_create,
    chargeback_dispute_edit,
    chargeback_dispute_delete,
)
from apps.ecommerce.views.FraudRisk.AccountSecurityAlerts import (
    account_security_alert_list,
    account_security_alert_detail,
    account_security_alert_create,
    account_security_alert_edit,
    account_security_alert_delete,
)

__all__ = [
    "fraud_risk_hub",
    "fraud_rule_list",
    "fraud_rule_detail",
    "fraud_rule_create",
    "fraud_rule_edit",
    "fraud_rule_delete",
    "transaction_risk_assessment_list",
    "transaction_risk_assessment_detail",
    "transaction_risk_assessment_create",
    "transaction_risk_assessment_edit",
    "transaction_risk_assessment_delete",
    "chargeback_dispute_list",
    "chargeback_dispute_detail",
    "chargeback_dispute_create",
    "chargeback_dispute_edit",
    "chargeback_dispute_delete",
    "account_security_alert_list",
    "account_security_alert_detail",
    "account_security_alert_create",
    "account_security_alert_edit",
    "account_security_alert_delete",
]
