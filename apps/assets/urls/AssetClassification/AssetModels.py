from django.urls import path

from apps.assets.views.AssetClassification.AssetModels import (
    asset_model_create,
    asset_model_delete,
    asset_model_detail,
    asset_model_edit,
    asset_model_list,
)

urlpatterns = [
    path("classification/models/", asset_model_list, name="asset_model_list"),
    path("classification/models/create/", asset_model_create, name="asset_model_create"),
    path("classification/models/<int:pk>/", asset_model_detail, name="asset_model_detail"),
    path("classification/models/<int:pk>/edit/", asset_model_edit, name="asset_model_edit"),
    path("classification/models/<int:pk>/delete/", asset_model_delete, name="asset_model_delete"),
]
