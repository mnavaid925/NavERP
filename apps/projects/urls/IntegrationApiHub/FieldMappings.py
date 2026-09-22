"""Projects 7.18 — ConnectorFieldMapping URL patterns."""
from django.urls import path

from apps.projects.views.IntegrationApiHub import FieldMappings as views

urlpatterns = [
    path("integration/mappings/", views.ixm_list, name="ixm_list"),
    path("integration/mappings/add/", views.ixm_create, name="ixm_create"),
    path("integration/mappings/<int:pk>/", views.ixm_detail, name="ixm_detail"),
    path("integration/mappings/<int:pk>/edit/", views.ixm_edit, name="ixm_edit"),
    path("integration/mappings/<int:pk>/delete/", views.ixm_delete, name="ixm_delete"),
]
