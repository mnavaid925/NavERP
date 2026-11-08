from django.urls import path

from apps.assets.urls.AssetProcurement import (
    urlpatterns as asset_procurement_urlpatterns,
)
from apps.assets.views.overview import overview

app_name = "assets"

urlpatterns = [
    path("", overview, name="overview"),
] + asset_procurement_urlpatterns
