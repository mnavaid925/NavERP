"""Models package for apps.assets."""
from apps.assets.models._base import TenantNumbered, TenantOwned
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
]
