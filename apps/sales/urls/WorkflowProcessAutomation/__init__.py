from .SalesAlertTriggers import urlpatterns as alert_trigger_urls
from .SalesApprovalDecisions import urlpatterns as approval_decision_urls
from .SalesAssignmentRules import urlpatterns as assignment_rule_urls
from .SalesProcessDefinitions import urlpatterns as process_urls

urlpatterns = process_urls + assignment_rule_urls + approval_decision_urls + alert_trigger_urls
