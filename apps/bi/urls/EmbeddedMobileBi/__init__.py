from apps.bi.urls.EmbeddedMobileBi.EmbeddedAnalyticsConfigs import urlpatterns as embed_urls
from apps.bi.urls.EmbeddedMobileBi.KioskWallboardDisplays import urlpatterns as kiosk_urls
from apps.bi.urls.EmbeddedMobileBi.MobileBiConfigurations import urlpatterns as mobile_urls
from apps.bi.urls.EmbeddedMobileBi.EmbedApiTokens import urlpatterns as token_urls

urlpatterns = embed_urls + kiosk_urls + mobile_urls + token_urls
