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
from apps.assets.models.AssetPerformance import (
    AssetDowntimeLog,
    AssetEnergyReading,
    AssetOeeRecord,
    AssetPerformanceScorecard,
)
from apps.assets.models.AssetProcurement import (
    AssetAcquisitionReceipt,
    AssetCapitalization,
    AssetRequisition,
    AssetTag,
)
from apps.assets.models.AssetReliability import (
    AssetCalibrationRecord,
    AssetConditionAssessment,
    AssetFailureMode,
    AssetTelemetryReading,
)
from apps.assets.models.AssetDisposal import (
    AssetDisposalRequest,
    AssetResaleListing,
    AssetScrapSalvage,
    AssetTradeIn,
)
from apps.assets.models.AssetWarrantyInsurance import (
    AssetInsuranceClaim,
    AssetInsurancePolicy,
    AssetWarranty,
    AssetWarrantyClaim,
)
from apps.assets.models.AssetLeaseRental import (
    AssetLeaseBuyAnalysis,
    AssetLeaseContract,
    AssetLeaseModification,
    AssetLeaseSchedule,
)
from apps.assets.models.AssetCompliance import (
    AssetComplianceAudit,
    AssetComplianceFramework,
    AssetComplianceIncident,
    AssetPermitLicense,
)
from apps.assets.models.AssetRisk import (
    AssetBusinessContinuityPlan,
    AssetCyberSecurityProfile,
    AssetRiskMitigationAction,
    AssetRiskRegister,
)
from apps.assets.models.MobileAssetManagement import (
    AssetGeofenceEvent,
    AssetScanLog,
    FieldWorkOrder,
    MobileAssetInspection,
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
    "AssetDowntimeLog",
    "AssetOeeRecord",
    "AssetEnergyReading",
    "AssetPerformanceScorecard",
    "AssetConditionAssessment",
    "AssetTelemetryReading",
    "AssetFailureMode",
    "AssetCalibrationRecord",
    "AssetWarranty",
    "AssetWarrantyClaim",
    "AssetInsurancePolicy",
    "AssetInsuranceClaim",
    "AssetDisposalRequest",
    "AssetResaleListing",
    "AssetTradeIn",
    "AssetScrapSalvage",
    "AssetLeaseContract",
    "AssetLeaseSchedule",
    "AssetLeaseModification",
    "AssetLeaseBuyAnalysis",
    "AssetComplianceFramework",
    "AssetComplianceAudit",
    "AssetPermitLicense",
    "AssetComplianceIncident",
    "AssetRiskRegister",
    "AssetBusinessContinuityPlan",
    "AssetCyberSecurityProfile",
    "AssetRiskMitigationAction",
    "MobileAssetInspection",
    "FieldWorkOrder",
    "AssetScanLog",
    "AssetGeofenceEvent",
]
