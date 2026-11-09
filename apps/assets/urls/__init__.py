from django.urls import path

from apps.assets.urls.AssetClassification import (
    urlpatterns as asset_classification_urlpatterns,
)
from apps.assets.urls.AssetDepreciation import (
    urlpatterns as asset_depreciation_urlpatterns,
)
from apps.assets.urls.AssetInventoryTracking import (
    urlpatterns as asset_inventory_tracking_urlpatterns,
)
from apps.assets.urls.AssetProcurement import (
    urlpatterns as asset_procurement_urlpatterns,
)
from apps.assets.views.overview import overview

app_name = "assets"

urlpatterns = (
    [
        path("", overview, name="overview"),
    ]
    + asset_procurement_urlpatterns
    + asset_inventory_tracking_urlpatterns
    + asset_classification_urlpatterns
    + asset_depreciation_urlpatterns
)
