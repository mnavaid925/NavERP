from apps.ecommerce.urls.IntegrationApi.EcommerceConnectors import (
    urlpatterns as connector_urls,
)
from apps.ecommerce.urls.IntegrationApi.IntegrationSyncJobs import (
    urlpatterns as sync_job_urls,
)
from apps.ecommerce.urls.IntegrationApi.WebhookSubscriptions import (
    urlpatterns as webhook_urls,
)
from apps.ecommerce.urls.IntegrationApi.ApiCredentials import (
    urlpatterns as api_credential_urls,
)

urlpatterns = [
    *connector_urls,
    *sync_job_urls,
    *webhook_urls,
    *api_credential_urls,
]
