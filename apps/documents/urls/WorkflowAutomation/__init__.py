from apps.documents.urls.WorkflowAutomation.DocumentProcessDefinitions import (
    urlpatterns as process_definition_patterns,
)
from apps.documents.urls.WorkflowAutomation.DocumentProcessInstances import (
    urlpatterns as process_instance_patterns,
)
from apps.documents.urls.WorkflowAutomation.DocumentRoutingRules import (
    urlpatterns as routing_rule_patterns,
)
from apps.documents.urls.WorkflowAutomation.DocumentWebhookTriggers import (
    urlpatterns as webhook_trigger_patterns,
)
from apps.documents.urls.WorkflowAutomation.WorkflowAnalytics import (
    urlpatterns as workflow_analytics_patterns,
)

urlpatterns = (
    process_definition_patterns
    + routing_rule_patterns
    + process_instance_patterns
    + webhook_trigger_patterns
    + workflow_analytics_patterns
)
