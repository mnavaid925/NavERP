from apps.assets.urls.IntegrationApiHub.AssetGisMappings import (
    urlpatterns as gis_mapping_urls,
)
from apps.assets.urls.IntegrationApiHub.AssetGlSyncBatches import (
    urlpatterns as gl_sync_batch_urls,
)
from apps.assets.urls.IntegrationApiHub.AssetIntegrationConnectors import (
    urlpatterns as connector_urls,
)
from apps.assets.urls.IntegrationApiHub.AssetTelemetryStreams import (
    urlpatterns as telemetry_stream_urls,
)

urlpatterns = (
    connector_urls
    + telemetry_stream_urls
    + gl_sync_batch_urls
    + gis_mapping_urls
)
