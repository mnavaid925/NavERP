"""Models package for apps.assets."""
from apps.assets.models._base import TenantNumbered, TenantOwned
from apps.assets.models.AssetClassification import (
    AssetCategory,
    AssetCriticalityAssessment,
    AssetModel,
    AssetSpecificationTemplate,
)
from apps.assets.models.AssetDepreciation import (
    AssetDepreciationSchedule,
    AssetRevaluation,
    AssetTransfer,
    CapitalizationPolicy,
)
from apps.assets.models.AssetInventoryTracking import (
    AssetAudit,
    AssetCustodyLog,
    AssetIncidentReport,
    AssetMovementLog,
)
from apps.assets.models.AssetMaintenance import (
    AssetMaintenanceLog,
    AssetMaintenanceRequest,
    AssetMaintenanceSchedule,
    AssetServiceContract,
)
from apps.assets.models.AssetProcurement import (
    AssetAcquisitionReceipt,
    AssetCapitalization,
    AssetRequisition,
    AssetTag,
)

__all__ = [
    "TenantOwned",
    "TenantNumbered",
    "AssetRequisition",
    "AssetAcquisitionReceipt",
    "AssetCapitalization",
    "AssetTag",
    "AssetAudit",
    "AssetMovementLog",
    "AssetCustodyLog",
    "AssetIncidentReport",
    "AssetCategory",
    "AssetModel",
    "AssetCriticalityAssessment",
    "AssetSpecificationTemplate",
    "AssetDepreciationSchedule",
    "AssetRevaluation",
    "AssetTransfer",
    "CapitalizationPolicy",
    "AssetMaintenanceRequest",
    "AssetMaintenanceSchedule",
    "AssetServiceContract",
    "AssetMaintenanceLog",
]
