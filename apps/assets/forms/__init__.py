"""Forms package for apps.assets."""
from apps.assets.forms._common import TenantUniqueMixin, reject_foreign
from apps.assets.forms.AssetInventoryTracking import (
    AssetAuditForm,
    AssetCustodyLogForm,
    AssetIncidentReportForm,
    AssetMovementLogForm,
)
from apps.assets.forms.AssetProcurement import (
    AssetAcquisitionReceiptForm,
    AssetCapitalizationForm,
    AssetRequisitionForm,
    AssetTagForm,
)

__all__ = [
    "TenantUniqueMixin",
    "reject_foreign",
    "AssetRequisitionForm",
    "AssetAcquisitionReceiptForm",
    "AssetCapitalizationForm",
    "AssetTagForm",
    "AssetAuditForm",
    "AssetMovementLogForm",
    "AssetCustodyLogForm",
    "AssetIncidentReportForm",
]
