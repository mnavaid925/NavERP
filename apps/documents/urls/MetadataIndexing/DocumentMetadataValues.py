from django.urls import path
from apps.documents.views.MetadataIndexing import DocumentMetadataValues as views

urlpatterns = [
    path("metadata/", views.metadata_value_list, name="metadata_value_list"),
    path("metadata/create/", views.metadata_value_create, name="metadata_value_create"),
    path("metadata/<int:pk>/", views.metadata_value_detail, name="metadata_value_detail"),
    path("metadata/<int:pk>/edit/", views.metadata_value_edit, name="metadata_value_edit"),
    path("metadata/<int:pk>/delete/", views.metadata_value_delete, name="metadata_value_delete"),
    path("metadata/<int:pk>/validate/", views.metadata_value_validate, name="metadata_value_validate"),
]
