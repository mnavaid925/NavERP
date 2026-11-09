from apps.assets.urls.AssetMaintenance.AssetMaintenanceLogs import urlpatterns as log_urls
from apps.assets.urls.AssetMaintenance.AssetMaintenanceRequests import urlpatterns as request_urls
from apps.assets.urls.AssetMaintenance.AssetMaintenanceSchedules import urlpatterns as schedule_urls
from apps.assets.urls.AssetMaintenance.AssetServiceContracts import urlpatterns as contract_urls

urlpatterns = request_urls + schedule_urls + contract_urls + log_urls
