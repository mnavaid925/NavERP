"""URL patterns for SalesRegionalSetting entity."""
from django.urls import path
from apps.sales.views.MasterDataConfiguration.SalesRegionalSettings import (
    srg_create,
    srg_delete,
    srg_detail,
    srg_edit,
    srg_list,
)

urlpatterns = [
    path("master-data/regional-settings/", srg_list, name="srg_list"),
    path("master-data/regional-settings/create/", srg_create, name="srg_create"),
    path("master-data/regional-settings/<int:pk>/", srg_detail, name="srg_detail"),
    path("master-data/regional-settings/<int:pk>/edit/", srg_edit, name="srg_edit"),
    path("master-data/regional-settings/<int:pk>/delete/", srg_delete, name="srg_delete"),
]
