from django.urls import path

from apps.ecommerce.views.SearchDiscovery import SearchSynonyms as views

urlpatterns = [
    path(
        "search-discovery/synonyms/",
        views.searchsynonym_list,
        name="searchsynonym_list",
    ),
    path(
        "search-discovery/synonyms/create/",
        views.searchsynonym_create,
        name="searchsynonym_create",
    ),
    path(
        "search-discovery/synonyms/<int:pk>/",
        views.searchsynonym_detail,
        name="searchsynonym_detail",
    ),
    path(
        "search-discovery/synonyms/<int:pk>/edit/",
        views.searchsynonym_edit,
        name="searchsynonym_edit",
    ),
    path(
        "search-discovery/synonyms/<int:pk>/delete/",
        views.searchsynonym_delete,
        name="searchsynonym_delete",
    ),
    path(
        "search-discovery/synonyms/<int:pk>/toggle/",
        views.searchsynonym_toggle,
        name="searchsynonym_toggle",
    ),
]
