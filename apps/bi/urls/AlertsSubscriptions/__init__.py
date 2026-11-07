from apps.bi.urls.AlertsSubscriptions.BiAlertRules import (
    urlpatterns as alert_rule_urls,
)
from apps.bi.urls.AlertsSubscriptions.BiNotificationItems import (
    urlpatterns as notification_urls,
)
from apps.bi.urls.AlertsSubscriptions.DistributionBurstRuns import (
    urlpatterns as burst_run_urls,
)
from apps.bi.urls.AlertsSubscriptions.ReportSubscriptions import (
    urlpatterns as subscription_urls,
)

urlpatterns = (
    alert_rule_urls
    + subscription_urls
    + burst_run_urls
    + notification_urls
)
