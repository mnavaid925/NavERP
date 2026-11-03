from apps.bi.models._base import TenantNumbered, TenantOwned
from apps.bi.models.DataIntegration.CdcSyncConfigs import CdcSyncConfig
from apps.bi.models.DataIntegration.DataSourceConnectors import DataSourceConnector
from apps.bi.models.DataIntegration.IngestionPipelines import IngestionPipeline
from apps.bi.models.DataIntegration.IngestionRuns import IngestionRun

__all__ = [
    "TenantOwned",
    "TenantNumbered",
    "DataSourceConnector",
    "IngestionPipeline",
    "CdcSyncConfig",
    "IngestionRun",
]
