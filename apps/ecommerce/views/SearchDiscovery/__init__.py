from apps.ecommerce.views.SearchDiscovery.SearchConsole import (
    search_analytics,
    search_autocomplete,
    search_console,
)
from apps.ecommerce.views.SearchDiscovery.SearchFacetConfigs import (
    searchfacetconfig_create,
    searchfacetconfig_delete,
    searchfacetconfig_detail,
    searchfacetconfig_edit,
    searchfacetconfig_list,
    searchfacetconfig_toggle,
)
from apps.ecommerce.views.SearchDiscovery.SearchMerchandisingRules import (
    searchmerchandisingrule_create,
    searchmerchandisingrule_delete,
    searchmerchandisingrule_detail,
    searchmerchandisingrule_edit,
    searchmerchandisingrule_list,
    searchmerchandisingrule_toggle,
)
from apps.ecommerce.views.SearchDiscovery.SearchQueryLogs import (
    searchquerylog_delete,
    searchquerylog_detail,
    searchquerylog_list,
)
from apps.ecommerce.views.SearchDiscovery.SearchSynonyms import (
    searchsynonym_create,
    searchsynonym_delete,
    searchsynonym_detail,
    searchsynonym_edit,
    searchsynonym_list,
    searchsynonym_toggle,
)

__all__ = [
    "searchsynonym_list",
    "searchsynonym_detail",
    "searchsynonym_create",
    "searchsynonym_edit",
    "searchsynonym_delete",
    "searchsynonym_toggle",
    "searchfacetconfig_list",
    "searchfacetconfig_detail",
    "searchfacetconfig_create",
    "searchfacetconfig_edit",
    "searchfacetconfig_delete",
    "searchfacetconfig_toggle",
    "searchmerchandisingrule_list",
    "searchmerchandisingrule_detail",
    "searchmerchandisingrule_create",
    "searchmerchandisingrule_edit",
    "searchmerchandisingrule_delete",
    "searchmerchandisingrule_toggle",
    "searchquerylog_list",
    "searchquerylog_detail",
    "searchquerylog_delete",
    "search_console",
    "search_autocomplete",
    "search_analytics",
]
