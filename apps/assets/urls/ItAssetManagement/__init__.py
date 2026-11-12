"""Module 11.18 IT Asset Management (ITAM) URLs package."""

from apps.assets.urls.ItAssetManagement.CloudAssetSubscriptions import (
    urlpatterns as cloud_urlpatterns,
)
from apps.assets.urls.ItAssetManagement.CmdbImpactAnalyses import (
    urlpatterns as cmdb_impact_urlpatterns,
)
from apps.assets.urls.ItAssetManagement.CmdbRelationships import (
    urlpatterns as cmdb_urlpatterns,
)
from apps.assets.urls.ItAssetManagement.ItHardwareAssets import (
    urlpatterns as hw_urlpatterns,
)
from apps.assets.urls.ItAssetManagement.ItRefreshBoards import (
    urlpatterns as refresh_urlpatterns,
)
from apps.assets.urls.ItAssetManagement.SoftwareLicenses import (
    urlpatterns as sw_urlpatterns,
)

urlpatterns = (
    refresh_urlpatterns
    + cmdb_impact_urlpatterns
    + hw_urlpatterns
    + sw_urlpatterns
    + cloud_urlpatterns
    + cmdb_urlpatterns
)
