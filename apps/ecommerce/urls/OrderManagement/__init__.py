from apps.ecommerce.urls.OrderManagement.EcommerceOrders import urlpatterns as orders_urls
from apps.ecommerce.urls.OrderManagement.OrderFulfillments import urlpatterns as fulfillments_urls
from apps.ecommerce.urls.OrderManagement.OrderRoutingRules import urlpatterns as routing_urls
from apps.ecommerce.urls.OrderManagement.ReturnMerchandiseAuthorizations import urlpatterns as returns_urls

urlpatterns = orders_urls + routing_urls + fulfillments_urls + returns_urls
