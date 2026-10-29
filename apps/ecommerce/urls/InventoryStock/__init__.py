from apps.ecommerce.urls.InventoryStock.BackorderPolicies import (
    urlpatterns as backorder_urls,
)
from apps.ecommerce.urls.InventoryStock.ChannelInventorySyncs import (
    urlpatterns as sync_urls,
)
from apps.ecommerce.urls.InventoryStock.FulfillmentCenters import (
    urlpatterns as center_urls,
)
from apps.ecommerce.urls.InventoryStock.InventoryAllocations import (
    urlpatterns as alloc_urls,
)
from apps.ecommerce.urls.InventoryStock.Operations import (
    urlpatterns as operations_urls,
)

urlpatterns = (
    operations_urls
    + center_urls
    + alloc_urls
    + backorder_urls
    + sync_urls
)
