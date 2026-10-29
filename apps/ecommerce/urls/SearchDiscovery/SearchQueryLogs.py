from django.urls import path

from apps.ecommerce.views.SearchDiscovery import SearchQueryLogs as views

urlpatterns = [
    path(
        "search-discovery/query-logs/",
        views.searchquerylog_list,
        name="searchquerylog_list",
    ),
    path(
        "search-discovery/query-logs/<int:pk>/",
        views.searchquerylog_detail,
        name="searchquerylog_detail",
    ),
    path(
        "search-discovery/query-logs/<int:pk>/delete/",
        views.searchquerylog_delete,
        name="searchquerylog_delete",
    ),
]
