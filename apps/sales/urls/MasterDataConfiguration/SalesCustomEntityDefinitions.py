"""URL patterns for SalesCustomEntityDefinition entity."""
from django.urls import path
from apps.sales.views.MasterDataConfiguration.SalesCustomEntityDefinitions import (
    sco_create,
    sco_delete,
    sco_detail,
    sco_edit,
    sco_list,
)

urlpatterns = [
    path("master-data/custom-entities/", sco_list, name="sco_list"),
    path("master-data/custom-entities/create/", sco_create, name="sco_create"),
    path("master-data/custom-entities/<int:pk>/", sco_detail, name="sco_detail"),
    path("master-data/custom-entities/<int:pk>/edit/", sco_edit, name="sco_edit"),
    path("master-data/custom-entities/<int:pk>/delete/", sco_delete, name="sco_delete"),
]
