from django.urls import path
from apps.documents.views.MetadataIndexing import TaxonomyTerms as views

urlpatterns = [
    path("taxonomy/", views.taxonomy_term_list, name="taxonomy_term_list"),
    path("taxonomy/tree/", views.taxonomy_term_tree, name="taxonomy_term_tree"),
    path("taxonomy/create/", views.taxonomy_term_create, name="taxonomy_term_create"),
    path("taxonomy/<int:pk>/", views.taxonomy_term_detail, name="taxonomy_term_detail"),
    path("taxonomy/<int:pk>/edit/", views.taxonomy_term_edit, name="taxonomy_term_edit"),
    path("taxonomy/<int:pk>/delete/", views.taxonomy_term_delete, name="taxonomy_term_delete"),
]
