from django.urls import path

from apps.ecommerce.views.SearchDiscovery import SearchConsole as views

urlpatterns = [
    path(
        "search-discovery/console/",
        views.search_console,
        name="search_console",
    ),
    path(
        "search-discovery/autocomplete/",
        views.search_autocomplete,
        name="search_autocomplete",
    ),
    path(
        "search-discovery/analytics/",
        views.search_analytics,
        name="search_analytics",
    ),
]
