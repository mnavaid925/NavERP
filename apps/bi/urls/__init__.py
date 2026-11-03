from django.urls import path

from apps.bi.urls.DataIntegration.CdcSyncConfigs import (
    urlpatterns as cdc_urlpatterns,
)
from apps.bi.urls.DataIntegration.DataSourceConnectors import (
    urlpatterns as connector_urlpatterns,
)
from apps.bi.urls.DataIntegration.IngestionPipelines import (
    urlpatterns as pipeline_urlpatterns,
)
from apps.bi.urls.DataIntegration.IngestionRuns import (
    urlpatterns as run_urlpatterns,
)
from apps.bi.views.DataIntegration.DataIntegrationHub import data_integration_hub

app_name = "bi"

urlpatterns = [
    path("", data_integration_hub, name="data_integration_hub"),
    path("hub/", data_integration_hub, name="data_integration_hub_alias"),
] + connector_urlpatterns + pipeline_urlpatterns + cdc_urlpatterns + run_urlpatterns
