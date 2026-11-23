from django.urls import path

from apps.documents import views

urlpatterns = [
    path("saved-searches/", views.document_saved_search_list, name="document_saved_search_list"),
    path("saved-searches/create/", views.document_saved_search_create, name="document_saved_search_create"),
    path("saved-searches/<int:pk>/", views.document_saved_search_detail, name="document_saved_search_detail"),
    path("saved-searches/<int:pk>/edit/", views.document_saved_search_edit, name="document_saved_search_edit"),
    path("saved-searches/<int:pk>/delete/", views.document_saved_search_delete, name="document_saved_search_delete"),
    path("saved-searches/<int:pk>/run/", views.document_saved_search_run, name="document_saved_search_run"),
    path("saved-searches/<int:pk>/toggle-pin/", views.document_saved_search_toggle_pin, name="document_saved_search_toggle_pin"),
]
