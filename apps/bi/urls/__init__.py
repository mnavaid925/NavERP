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
from apps.bi.urls.DataQuality import (
    urlpatterns as data_quality_urlpatterns,
)
from apps.bi.urls.DataWarehouse import (
    urlpatterns as warehouse_urlpatterns,
)
from apps.bi.urls.MasterData import (
    urlpatterns as master_data_urlpatterns,
)
from apps.bi.urls.DataCatalog import (
    urlpatterns as data_catalog_urlpatterns,
)
from apps.bi.urls.Dashboards import (
    urlpatterns as dashboards_urlpatterns,
)
from apps.bi.urls.OlapAnalysis import (
    urlpatterns as olap_analysis_urlpatterns,
)
from apps.bi.urls.PredictiveAnalytics import (
    urlpatterns as predictive_analytics_urlpatterns,
)
from apps.bi.urls.AiAugmentedAnalytics import (
    urlpatterns as ai_augmented_analytics_urlpatterns,
)
from apps.bi.urls.ConversationalBi import (
    urlpatterns as conversational_bi_urlpatterns,
)
from apps.bi.urls.PerformanceScorecards import (
    urlpatterns as performance_scorecards_urlpatterns,
)
from apps.bi.urls.OperationalReporting import (
    urlpatterns as operational_reporting_urlpatterns,
)
from apps.bi.urls.SelfServiceAnalytics import (
    urlpatterns as self_service_urlpatterns,
)
from apps.bi.urls.SemanticLayer import (
    urlpatterns as semantic_urlpatterns,
)
from apps.bi.urls.EtlPipelines.EtlPipelineRuns import (
    urlpatterns as etl_runs_urlpatterns,
)
from apps.bi.urls.EtlPipelines.EtlPipelines import (
    urlpatterns as etl_pipeline_urlpatterns,
)
from apps.bi.urls.EtlPipelines.EtlPipelineVersions import (
    urlpatterns as etl_versions_urlpatterns,
)
from apps.bi.urls.EtlPipelines.TransformationSteps import (
    urlpatterns as etl_steps_urlpatterns,
)
from apps.bi.views.DataIntegration.DataIntegrationHub import data_integration_hub

app_name = "bi"

urlpatterns = (
    [
        path("", data_integration_hub, name="data_integration_hub"),
        path("hub/", data_integration_hub, name="data_integration_hub_alias"),
    ]
    + connector_urlpatterns
    + pipeline_urlpatterns
    + cdc_urlpatterns
    + run_urlpatterns
    + etl_pipeline_urlpatterns
    + etl_steps_urlpatterns
    + etl_versions_urlpatterns
    + etl_runs_urlpatterns
    + warehouse_urlpatterns
    + semantic_urlpatterns
    + data_quality_urlpatterns
    + master_data_urlpatterns
    + data_catalog_urlpatterns
    + dashboards_urlpatterns
    + operational_reporting_urlpatterns
    + self_service_urlpatterns
    + performance_scorecards_urlpatterns
    + olap_analysis_urlpatterns
    + predictive_analytics_urlpatterns
    + ai_augmented_analytics_urlpatterns
    + conversational_bi_urlpatterns
)
