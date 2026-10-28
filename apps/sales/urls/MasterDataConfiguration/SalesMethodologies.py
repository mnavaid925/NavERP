"""URL patterns for SalesMethodology entity."""
from django.urls import path
from apps.sales.views.MasterDataConfiguration.SalesMethodologies import (
    smd_create,
    smd_delete,
    smd_detail,
    smd_edit,
    smd_list,
)

urlpatterns = [
    path("master-data/methodologies/", smd_list, name="smd_list"),
    path("master-data/methodologies/create/", smd_create, name="smd_create"),
    path("master-data/methodologies/<int:pk>/", smd_detail, name="smd_detail"),
    path("master-data/methodologies/<int:pk>/edit/", smd_edit, name="smd_edit"),
    path("master-data/methodologies/<int:pk>/delete/", smd_delete, name="smd_delete"),
]
