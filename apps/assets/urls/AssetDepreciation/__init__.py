from apps.assets.urls.AssetDepreciation.AssetDepreciationSchedules import urlpatterns as schedule_urls
from apps.assets.urls.AssetDepreciation.AssetRevaluations import urlpatterns as revaluation_urls
from apps.assets.urls.AssetDepreciation.AssetTransfers import urlpatterns as transfer_urls
from apps.assets.urls.AssetDepreciation.CapitalizationPolicies import urlpatterns as policy_urls

urlpatterns = (
    schedule_urls
    + revaluation_urls
    + transfer_urls
    + policy_urls
)
