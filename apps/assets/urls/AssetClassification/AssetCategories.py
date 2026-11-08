from django.urls import path

from apps.assets.views.AssetClassification.AssetCategories import (
    asset_category_create,
    asset_category_delete,
    asset_category_detail,
    asset_category_edit,
    asset_category_list,
)

urlpatterns = [
    path("classification/categories/", asset_category_list, name="asset_category_list"),
    path("classification/categories/create/", asset_category_create, name="asset_category_create"),
    path("classification/categories/<int:pk>/", asset_category_detail, name="asset_category_detail"),
    path("classification/categories/<int:pk>/edit/", asset_category_edit, name="asset_category_edit"),
    path("classification/categories/<int:pk>/delete/", asset_category_delete, name="asset_category_delete"),
]
