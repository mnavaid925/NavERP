from apps.ecommerce.urls.MobileCommerce.MobileAppConfigs import urlpatterns as app_config_urls
from apps.ecommerce.urls.MobileCommerce.MobileDeviceRegistrations import urlpatterns as device_urls
from apps.ecommerce.urls.MobileCommerce.MobileHub import urlpatterns as hub_urls
from apps.ecommerce.urls.MobileCommerce.MobileLocationRules import urlpatterns as location_urls
from apps.ecommerce.urls.MobileCommerce.MobilePushCampaigns import urlpatterns as push_urls

urlpatterns = (
    hub_urls
    + app_config_urls
    + device_urls
    + push_urls
    + location_urls
)
