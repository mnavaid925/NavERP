"""Sales 8.15 — ContractSubscriptionManagement URLs package."""
from apps.sales.urls.ContractSubscriptionManagement.ContractObligations import (
    urlpatterns as obligation_urls,
)
from apps.sales.urls.ContractSubscriptionManagement.ContractSubscriptionWorkspaces import (
    urlpatterns as workspace_urls,
)
from apps.sales.urls.ContractSubscriptionManagement.CustomerContracts import (
    urlpatterns as contract_urls,
)
from apps.sales.urls.ContractSubscriptionManagement.CustomerSubscriptions import (
    urlpatterns as subscription_urls,
)
from apps.sales.urls.ContractSubscriptionManagement.RenewalAutomations import (
    urlpatterns as renewal_urls,
)
from apps.sales.urls.ContractSubscriptionManagement.UsageMeterRecords import (
    urlpatterns as usage_urls,
)

# Literal routes before pk routes (first-match-wins)
urlpatterns = (
    workspace_urls
    + renewal_urls
    + contract_urls
    + subscription_urls
    + usage_urls
    + obligation_urls
)
