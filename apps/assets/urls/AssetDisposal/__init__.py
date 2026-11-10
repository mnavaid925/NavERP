"""AssetDisposal urls package."""
from apps.assets.urls.AssetDisposal.AssetDisposalRequests import urlpatterns as request_patterns
from apps.assets.urls.AssetDisposal.AssetResaleListings import urlpatterns as resale_patterns
from apps.assets.urls.AssetDisposal.AssetScrapSalvages import urlpatterns as scrap_patterns
from apps.assets.urls.AssetDisposal.AssetTradeIns import urlpatterns as trade_in_patterns

urlpatterns = (
    request_patterns
    + resale_patterns
    + trade_in_patterns
    + scrap_patterns
)
