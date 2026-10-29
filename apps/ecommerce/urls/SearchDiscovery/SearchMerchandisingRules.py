from django.urls import path

from apps.ecommerce.views.SearchDiscovery import SearchMerchandisingRules as views

urlpatterns = [
    path(
        "search-discovery/merchandising-rules/",
        views.searchmerchandisingrule_list,
        name="searchmerchandisingrule_list",
    ),
    path(
        "search-discovery/merchandising-rules/create/",
        views.searchmerchandisingrule_create,
        name="searchmerchandisingrule_create",
    ),
    path(
        "search-discovery/merchandising-rules/<int:pk>/",
        views.searchmerchandisingrule_detail,
        name="searchmerchandisingrule_detail",
    ),
    path(
        "search-discovery/merchandising-rules/<int:pk>/edit/",
        views.searchmerchandisingrule_edit,
        name="searchmerchandisingrule_edit",
    ),
    path(
        "search-discovery/merchandising-rules/<int:pk>/delete/",
        views.searchmerchandisingrule_delete,
        name="searchmerchandisingrule_delete",
    ),
    path(
        "search-discovery/merchandising-rules/<int:pk>/toggle/",
        views.searchmerchandisingrule_toggle,
        name="searchmerchandisingrule_toggle",
    ),
]
