"""Module 11.18 IT Asset Management (ITAM) models package."""

from apps.assets.models.ItAssetManagement.CloudAssetSubscriptions import (
    CloudAssetSubscription,
)
from apps.assets.models.ItAssetManagement.CmdbRelationships import CmdbRelationship
from apps.assets.models.ItAssetManagement.ItHardwareAssets import ItHardwareAsset
from apps.assets.models.ItAssetManagement.SoftwareLicenses import SoftwareLicense

__all__ = [
    "ItHardwareAsset",
    "SoftwareLicense",
    "CloudAssetSubscription",
    "CmdbRelationship",
]
