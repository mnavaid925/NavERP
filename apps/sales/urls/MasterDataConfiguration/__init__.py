from .Overview import urlpatterns as overview_urls
from .SalesPriceBookEntries import urlpatterns as pbe_urls
from .SalesCustomEntityDefinitions import urlpatterns as sco_urls
from .SalesMethodologies import urlpatterns as smd_urls
from .SalesRegionalSettings import urlpatterns as srg_urls

urlpatterns = overview_urls + pbe_urls + sco_urls + smd_urls + srg_urls
