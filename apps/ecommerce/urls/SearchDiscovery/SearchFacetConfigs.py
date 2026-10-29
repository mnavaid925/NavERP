from django.urls import path

from apps.ecommerce.views.SearchDiscovery import SearchFacetConfigs as views

urlpatterns = [
    path(
        "search-discovery/facet-configs/",
        views.searchfacetconfig_list,
        name="searchfacetconfig_list",
    ),
    path(
        "search-discovery/facet-configs/create/",
        views.searchfacetconfig_create,
        name="searchfacetconfig_create",
    ),
    path(
        "search-discovery/facet-configs/<int:pk>/",
        views.searchfacetconfig_detail,
        name="searchfacetconfig_detail",
    ),
    path(
        "search-discovery/facet-configs/<int:pk>/edit/",
        views.searchfacetconfig_edit,
        name="searchfacetconfig_edit",
    ),
    path(
        "search-discovery/facet-configs/<int:pk>/delete/",
        views.searchfacetconfig_delete,
        name="searchfacetconfig_delete",
    ),
    path(
        "search-discovery/facet-configs/<int:pk>/toggle/",
        views.searchfacetconfig_toggle,
        name="searchfacetconfig_toggle",
    ),
]
