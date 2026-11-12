"""Module 11.18 IT Asset Management (ITAM) forms package."""

from apps.assets.forms.ItAssetManagement.CloudAssetSubscriptions import (
    CloudAssetSubscriptionForm,
)
from apps.assets.forms.ItAssetManagement.CmdbRelationships import CmdbRelationshipForm
from apps.assets.forms.ItAssetManagement.ItHardwareAssets import ItHardwareAssetForm
from apps.assets.forms.ItAssetManagement.SoftwareLicenses import SoftwareLicenseForm

__all__ = [
    "ItHardwareAssetForm",
    "SoftwareLicenseForm",
    "CloudAssetSubscriptionForm",
    "CmdbRelationshipForm",
]
