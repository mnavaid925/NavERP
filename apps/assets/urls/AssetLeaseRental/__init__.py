from apps.assets.urls.AssetLeaseRental.AssetLeaseBuyAnalyses import urlpatterns as buy_analysis_patterns
from apps.assets.urls.AssetLeaseRental.AssetLeaseContracts import urlpatterns as contract_patterns
from apps.assets.urls.AssetLeaseRental.AssetLeaseModifications import urlpatterns as modification_patterns
from apps.assets.urls.AssetLeaseRental.AssetLeaseSchedules import urlpatterns as schedule_patterns

urlpatterns = contract_patterns + schedule_patterns + modification_patterns + buy_analysis_patterns
