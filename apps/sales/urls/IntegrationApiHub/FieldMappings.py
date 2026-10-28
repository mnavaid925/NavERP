"""Sales 8.18 — SalesFieldMapping URL patterns."""
from django.urls import path

from apps.sales.views.IntegrationApiHub.FieldMappings import (
    sfm_create,
    sfm_delete,
    sfm_detail,
    sfm_edit,
    sfm_list,
)

urlpatterns = [
    path("mappings/", sfm_list, name="sfm_list"),
    path("mappings/create/", sfm_create, name="sfm_create"),
    path("mappings/<int:pk>/", sfm_detail, name="sfm_detail"),
    path("mappings/<int:pk>/edit/", sfm_edit, name="sfm_edit"),
    path("mappings/<int:pk>/delete/", sfm_delete, name="sfm_delete"),
]
