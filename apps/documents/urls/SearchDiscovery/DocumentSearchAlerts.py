from django.urls import path

from apps.documents import views

urlpatterns = [
    path("search-alerts/", views.document_search_alert_list, name="document_search_alert_list"),
    path("search-alerts/create/", views.document_search_alert_create, name="document_search_alert_create"),
    path("search-alerts/<int:pk>/", views.document_search_alert_detail, name="document_search_alert_detail"),
    path("search-alerts/<int:pk>/edit/", views.document_search_alert_edit, name="document_search_alert_edit"),
    path("search-alerts/<int:pk>/delete/", views.document_search_alert_delete, name="document_search_alert_delete"),
    path("search-alerts/<int:pk>/toggle-active/", views.document_search_alert_toggle_active, name="document_search_alert_toggle_active"),
    path("search-alerts/<int:pk>/run-check/", views.document_search_alert_run_check, name="document_search_alert_run_check"),
]
