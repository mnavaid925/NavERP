from apps.ecommerce.urls.SearchDiscovery.SearchConsole import urlpatterns as console_urls
from apps.ecommerce.urls.SearchDiscovery.SearchFacetConfigs import (
    urlpatterns as facet_urls,
)
from apps.ecommerce.urls.SearchDiscovery.SearchMerchandisingRules import (
    urlpatterns as merchandising_urls,
)
from apps.ecommerce.urls.SearchDiscovery.SearchQueryLogs import (
    urlpatterns as querylog_urls,
)
from apps.ecommerce.urls.SearchDiscovery.SearchSynonyms import (
    urlpatterns as synonym_urls,
)

urlpatterns = (
    synonym_urls
    + facet_urls
    + merchandising_urls
    + querylog_urls
    + console_urls
)
