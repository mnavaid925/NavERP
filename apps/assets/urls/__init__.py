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
from apps.assets.urls.AssetMaintenance import (
    urlpatterns as asset_maintenance_urlpatterns,
)
from apps.assets.urls.AssetPerformance import (
    urlpatterns as asset_performance_urlpatterns,
)
from apps.assets.urls.AssetProcurement import (
    urlpatterns as asset_procurement_urlpatterns,
)
from apps.assets.urls.AssetDisposal import (
    urlpatterns as asset_disposal_urlpatterns,
)
from apps.assets.urls.AssetLeaseRental import (
    urlpatterns as asset_lease_rental_urlpatterns,
)
from apps.assets.urls.AssetReliability import (
    urlpatterns as asset_reliability_urlpatterns,
)
from apps.assets.urls.AssetWarrantyInsurance import (
    urlpatterns as asset_warranty_insurance_urlpatterns,
)
from apps.assets.urls.AssetCompliance import (
    urlpatterns as asset_compliance_urlpatterns,
)
from apps.assets.urls.AssetRisk import (
    urlpatterns as asset_risk_urlpatterns,
)
from apps.assets.urls.MobileAssetManagement import (
    urlpatterns as mobile_asset_management_urlpatterns,
)
from apps.assets.urls.IntegrationApiHub import (
    urlpatterns as integration_api_hub_urlpatterns,
)
from apps.assets.urls.AssetAnalytics import (
    urlpatterns as asset_analytics_urlpatterns,
)
from apps.assets.urls.AssetDocumentKnowledge import (
    urlpatterns as asset_document_knowledge_urlpatterns,
)
from apps.assets.urls.SpaceFacilityAsset import (
    urlpatterns as space_facility_asset_urlpatterns,
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
    + asset_maintenance_urlpatterns
    + asset_performance_urlpatterns
    + asset_reliability_urlpatterns
    + asset_warranty_insurance_urlpatterns
    + asset_disposal_urlpatterns
    + asset_lease_rental_urlpatterns
    + asset_compliance_urlpatterns
    + asset_risk_urlpatterns
    + mobile_asset_management_urlpatterns
    + integration_api_hub_urlpatterns
    + asset_analytics_urlpatterns
    + asset_document_knowledge_urlpatterns
    + space_facility_asset_urlpatterns
)
