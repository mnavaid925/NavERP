from apps.ecommerce.urls.Marketplace.MarketplaceConsole import (
    urlpatterns as console_patterns,
)
from apps.ecommerce.urls.Marketplace.MarketplaceVendors import (
    urlpatterns as vendor_patterns,
)
from apps.ecommerce.urls.Marketplace.VendorPayouts import (
    urlpatterns as payout_patterns,
)
from apps.ecommerce.urls.Marketplace.VendorProductListings import (
    urlpatterns as listing_patterns,
)
from apps.ecommerce.urls.Marketplace.VendorSubOrders import (
    urlpatterns as suborder_patterns,
)

urlpatterns = (
    console_patterns
    + vendor_patterns
    + listing_patterns
    + suborder_patterns
    + payout_patterns
)
