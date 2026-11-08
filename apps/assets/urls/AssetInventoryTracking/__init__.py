from apps.assets.urls.AssetInventoryTracking.AssetAudits import urlpatterns as audit_urls
from apps.assets.urls.AssetInventoryTracking.AssetCustodyLogs import urlpatterns as custody_urls
from apps.assets.urls.AssetInventoryTracking.AssetIncidentReports import urlpatterns as incident_urls
from apps.assets.urls.AssetInventoryTracking.AssetMovementLogs import urlpatterns as movement_urls

urlpatterns = audit_urls + movement_urls + custody_urls + incident_urls
