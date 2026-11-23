from django.urls import path
from apps.documents.views.MetadataIndexing import MetadataSchemas as views

urlpatterns = [
    path("schemas/", views.metadata_schema_list, name="metadata_schema_list"),
    path("schemas/create/", views.metadata_schema_create, name="metadata_schema_create"),
    path("schemas/<int:pk>/", views.metadata_schema_detail, name="metadata_schema_detail"),
    path("schemas/<int:pk>/edit/", views.metadata_schema_edit, name="metadata_schema_edit"),
    path("schemas/<int:pk>/delete/", views.metadata_schema_delete, name="metadata_schema_delete"),
]
