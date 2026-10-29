from apps.ecommerce.urls.InventoryStock import urlpatterns as _inventorystock_urls
from apps.ecommerce.urls.PricingPromotion import urlpatterns as _pricingpromotion_urls
from apps.ecommerce.urls.ProductCatalog import urlpatterns as _productcatalog_urls

app_name = "ecommerce"

urlpatterns = list(_productcatalog_urls) + list(_inventorystock_urls) + list(_pricingpromotion_urls)

