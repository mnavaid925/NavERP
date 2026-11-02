from apps.ecommerce.urls.FraudRisk.FraudRules import (
    urlpatterns as fraud_rule_urls,
)
from apps.ecommerce.urls.FraudRisk.TransactionRiskAssessments import (
    urlpatterns as assessment_urls,
)
from apps.ecommerce.urls.FraudRisk.ChargebackDisputes import (
    urlpatterns as dispute_urls,
)
from apps.ecommerce.urls.FraudRisk.AccountSecurityAlerts import (
    urlpatterns as alert_urls,
)

urlpatterns = [
    *fraud_rule_urls,
    *assessment_urls,
    *dispute_urls,
    *alert_urls,
]
