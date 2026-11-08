from apps.bi.urls.IntegrationHub.BiExtensionPlugins import (
    urlpatterns as bi_extension_plugin_urls,
)
from apps.bi.urls.IntegrationHub.BiWebhookSubscriptions import (
    urlpatterns as bi_webhook_subscription_urls,
)
from apps.bi.urls.IntegrationHub.IntegrationConnectors import (
    urlpatterns as integration_connector_urls,
)
from apps.bi.urls.IntegrationHub.WarehouseSyncEndpoints import (
    urlpatterns as warehouse_sync_endpoint_urls,
)

urlpatterns = (
    integration_connector_urls
    + warehouse_sync_endpoint_urls
    + bi_webhook_subscription_urls
    + bi_extension_plugin_urls
)
