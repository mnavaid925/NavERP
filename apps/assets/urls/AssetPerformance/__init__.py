from apps.assets.urls.AssetPerformance.AssetDowntimeLogs import urlpatterns as downtime_urls
from apps.assets.urls.AssetPerformance.AssetEnergyReadings import urlpatterns as energy_urls
from apps.assets.urls.AssetPerformance.AssetOeeRecords import urlpatterns as oee_urls
from apps.assets.urls.AssetPerformance.AssetPerformanceScorecards import urlpatterns as scorecard_urls

urlpatterns = downtime_urls + oee_urls + energy_urls + scorecard_urls
