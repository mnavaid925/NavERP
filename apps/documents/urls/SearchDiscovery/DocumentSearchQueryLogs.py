from django.urls import path

from apps.documents import views

urlpatterns = [
    path("search-logs/", views.document_search_query_log_list, name="document_search_query_log_list"),
    path("search-logs/analytics/", views.document_search_analytics, name="document_search_analytics"),
    path("search-logs/<int:pk>/", views.document_search_query_log_detail, name="document_search_query_log_detail"),
    path("search-logs/<int:pk>/delete/", views.document_search_query_log_delete, name="document_search_query_log_delete"),
]
