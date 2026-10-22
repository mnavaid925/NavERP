from .FieldCheckIns import urlpatterns as checkin_urls
from .FieldSalesRoutes import urlpatterns as route_urls
from .MobileDealAlerts import urlpatterns as alert_urls
from .MobileDeviceSessions import urlpatterns as device_urls
from .MobileSalesDashboards import urlpatterns as dashboard_urls

urlpatterns = route_urls + checkin_urls + device_urls + alert_urls + dashboard_urls
