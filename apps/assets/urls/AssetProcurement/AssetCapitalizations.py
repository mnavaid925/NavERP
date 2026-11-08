from django.urls import path

from apps.assets.views.AssetProcurement.AssetCapitalizations import (
    asset_capitalization_create,
    asset_capitalization_delete,
    asset_capitalization_detail,
    asset_capitalization_edit,
    asset_capitalization_execute,
    asset_capitalization_list,
    asset_capitalization_reverse,
)

urlpatterns = [
    path("capitalizations/", asset_capitalization_list, name="asset_capitalization_list"),
    path("capitalizations/create/", asset_capitalization_create, name="asset_capitalization_create"),
    path("capitalizations/<int:pk>/", asset_capitalization_detail, name="asset_capitalization_detail"),
    path("capitalizations/<int:pk>/edit/", asset_capitalization_edit, name="asset_capitalization_edit"),
    path("capitalizations/<int:pk>/delete/", asset_capitalization_delete, name="asset_capitalization_delete"),
    path("capitalizations/<int:pk>/execute/", asset_capitalization_execute, name="asset_capitalization_execute"),
    path("capitalizations/<int:pk>/reverse/", asset_capitalization_reverse, name="asset_capitalization_reverse"),
]
