from django.urls import path

from apps.bi.views.ConversationalBi import SearchDiscoveryIndexes as views

urlpatterns = [
    path("search-discovery/", views.search_discovery_index_list, name="search_discovery_index_list"),
    path("search-discovery/create/", views.search_discovery_index_create, name="search_discovery_index_create"),
    path("search-discovery/hub/", views.search_discovery_hub, name="search_discovery_hub"),
    path("search-discovery/<int:pk>/", views.search_discovery_index_detail, name="search_discovery_index_detail"),
    path("search-discovery/<int:pk>/edit/", views.search_discovery_index_edit, name="search_discovery_index_edit"),
    path("search-discovery/<int:pk>/delete/", views.search_discovery_index_delete, name="search_discovery_index_delete"),
    path("search-discovery/<int:pk>/reweight/", views.search_discovery_index_reweight, name="search_discovery_index_reweight"),
]
