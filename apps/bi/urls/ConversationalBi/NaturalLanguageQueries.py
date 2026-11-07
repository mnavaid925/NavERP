from django.urls import path

from apps.bi.views.ConversationalBi import NaturalLanguageQueries as views

urlpatterns = [
    path("natural-language-queries/", views.natural_language_query_list, name="natural_language_query_list"),
    path("natural-language-queries/create/", views.natural_language_query_create, name="natural_language_query_create"),
    path("natural-language-queries/<int:pk>/", views.natural_language_query_detail, name="natural_language_query_detail"),
    path("natural-language-queries/<int:pk>/edit/", views.natural_language_query_edit, name="natural_language_query_edit"),
    path("natural-language-queries/<int:pk>/delete/", views.natural_language_query_delete, name="natural_language_query_delete"),
    path("natural-language-queries/<int:pk>/rate/", views.natural_language_query_rate, name="natural_language_query_rate"),
]
