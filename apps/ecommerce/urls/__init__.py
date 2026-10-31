from apps.ecommerce.urls.CartCheckout import urlpatterns as _cartcheckout_urls
from apps.ecommerce.urls.CustomerProfile import urlpatterns as _customerprofile_urls
from apps.ecommerce.urls.InventoryStock import urlpatterns as _inventorystock_urls
from apps.ecommerce.urls.MarketingCampaign import urlpatterns as _marketingcampaign_urls
from apps.ecommerce.urls.Marketplace import urlpatterns as _marketplace_urls
from apps.ecommerce.urls.OrderManagement import urlpatterns as _ordermanagement_urls
from apps.ecommerce.urls.Personalization import urlpatterns as _personalization_urls
from apps.ecommerce.urls.PricingPromotion import urlpatterns as _pricingpromotion_urls
from apps.ecommerce.urls.ProductCatalog import urlpatterns as _productcatalog_urls
from apps.ecommerce.urls.SearchDiscovery import urlpatterns as _searchdiscovery_urls
from apps.ecommerce.urls.ReviewUgc import urlpatterns as _reviewugc_urls
from apps.ecommerce.urls.SubscriptionCommerce import urlpatterns as _subscriptioncommerce_urls

app_name = "ecommerce"

urlpatterns = (
    list(_productcatalog_urls)
    + list(_inventorystock_urls)
    + list(_pricingpromotion_urls)
    + list(_cartcheckout_urls)
    + list(_ordermanagement_urls)
    + list(_customerprofile_urls)
    + list(_searchdiscovery_urls)
    + list(_personalization_urls)
    + list(_marketingcampaign_urls)
    + list(_marketplace_urls)
    + list(_subscriptioncommerce_urls)
    + list(_reviewugc_urls)
)


