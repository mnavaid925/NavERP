from django.urls import path

from apps.documents import views

urlpatterns = [
    path("search-synonyms/", views.document_search_synonym_list, name="document_search_synonym_list"),
    path("search-synonyms/create/", views.document_search_synonym_create, name="document_search_synonym_create"),
    path("search-synonyms/<int:pk>/", views.document_search_synonym_detail, name="document_search_synonym_detail"),
    path("search-synonyms/<int:pk>/edit/", views.document_search_synonym_edit, name="document_search_synonym_edit"),
    path("search-synonyms/<int:pk>/delete/", views.document_search_synonym_delete, name="document_search_synonym_delete"),
]
