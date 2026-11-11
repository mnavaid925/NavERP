from django.urls import path

from apps.assets.views.IntegrationApiHub import AssetGisMappings as views

urlpatterns = [
    path(
        "integration/gis-mappings/",
        views.mapping_list,
        name="asset_gis_mapping_list",
    ),
    path(
        "integration/gis-mappings/create/",
        views.mapping_create,
        name="asset_gis_mapping_create",
    ),
    path(
        "integration/gis-mappings/<int:pk>/",
        views.mapping_detail,
        name="asset_gis_mapping_detail",
    ),
    path(
        "integration/gis-mappings/<int:pk>/edit/",
        views.mapping_edit,
        name="asset_gis_mapping_edit",
    ),
    path(
        "integration/gis-mappings/<int:pk>/delete/",
        views.mapping_delete,
        name="asset_gis_mapping_delete",
    ),
    path(
        "integration/gis-mappings/<int:pk>/verify/",
        views.verify_spatial_sync,
        name="asset_gis_mapping_verify_sync",
    ),
]
