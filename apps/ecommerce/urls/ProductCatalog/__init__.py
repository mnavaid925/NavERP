from apps.ecommerce.urls.ProductCatalog.BulkOperations import (
    urlpatterns as bulk_urls,
)
from apps.ecommerce.urls.ProductCatalog.CatalogProducts import (
    urlpatterns as product_urls,
)
from apps.ecommerce.urls.ProductCatalog.Overview import urlpatterns as overview_urls
from apps.ecommerce.urls.ProductCatalog.ProductRelationships import (
    urlpatterns as relationship_urls,
)
from apps.ecommerce.urls.ProductCatalog.ProductVariants import (
    urlpatterns as variant_urls,
)
from apps.ecommerce.urls.ProductCatalog.StoreCategories import (
    urlpatterns as category_urls,
)

# Literal routes before <int:pk> patterns
urlpatterns = (
    overview_urls
    + bulk_urls
    + category_urls
    + product_urls
    + variant_urls
    + relationship_urls
)
