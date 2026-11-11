from apps.assets.urls.MobileAssetManagement.AssetGeofenceEvents import urlpatterns as geofence_patterns
from apps.assets.urls.MobileAssetManagement.AssetScanLogs import urlpatterns as scan_patterns
from apps.assets.urls.MobileAssetManagement.FieldWorkOrders import urlpatterns as work_order_patterns
from apps.assets.urls.MobileAssetManagement.MobileAssetInspections import urlpatterns as inspection_patterns

urlpatterns = inspection_patterns + work_order_patterns + scan_patterns + geofence_patterns
