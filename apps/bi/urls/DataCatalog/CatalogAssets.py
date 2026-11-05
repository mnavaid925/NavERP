from django.urls import path

from apps.bi.views.DataCatalog.CatalogAssets import (
    catalog_asset_list,
    catalog_asset_create,
    catalog_asset_detail,
    catalog_asset_edit,
    catalog_asset_delete,
    catalog_asset_certify,
    catalog_asset_deprecate,
)

urlpatterns = [
    path("catalog/assets/", catalog_asset_list, name="catalog_asset_list"),
    path("catalog/assets/create/", catalog_asset_create, name="catalog_asset_create"),
    path("catalog/assets/<int:pk>/", catalog_asset_detail, name="catalog_asset_detail"),
    path("catalog/assets/<int:pk>/edit/", catalog_asset_edit, name="catalog_asset_edit"),
    path("catalog/assets/<int:pk>/delete/", catalog_asset_delete, name="catalog_asset_delete"),
    path("catalog/assets/<int:pk>/certify/", catalog_asset_certify, name="catalog_asset_certify"),
    path("catalog/assets/<int:pk>/deprecate/", catalog_asset_deprecate, name="catalog_asset_deprecate"),
]
