"""URL patterns for Furniture & Fixture Tracking / IMAC (11.17)."""

from django.urls import path

from apps.assets.views.SpaceFacilityAsset import AssetFurnitureFixtures as views

urlpatterns = [
    path(
        "furniture-fixtures/",
        views.asset_furniture_fixture_list,
        name="asset_furniture_fixture_list",
    ),
    path(
        "furniture-fixtures/create/",
        views.asset_furniture_fixture_create,
        name="asset_furniture_fixture_create",
    ),
    path(
        "furniture-fixtures/export-csv/",
        views.asset_furniture_fixture_export_csv,
        name="asset_furniture_fixture_export_csv",
    ),
    path(
        "furniture-fixtures/<int:pk>/",
        views.asset_furniture_fixture_detail,
        name="asset_furniture_fixture_detail",
    ),
    path(
        "furniture-fixtures/<int:pk>/edit/",
        views.asset_furniture_fixture_edit,
        name="asset_furniture_fixture_edit",
    ),
    path(
        "furniture-fixtures/<int:pk>/delete/",
        views.asset_furniture_fixture_delete,
        name="asset_furniture_fixture_delete",
    ),
    path(
        "furniture-fixtures/<int:pk>/request-move/",
        views.asset_furniture_fixture_request_move,
        name="asset_furniture_fixture_request_move",
    ),
    path(
        "furniture-fixtures/<int:pk>/schedule-reconfig/",
        views.asset_furniture_fixture_schedule_reconfig,
        name="asset_furniture_fixture_schedule_reconfig",
    ),
    path(
        "furniture-fixtures/<int:pk>/complete-move/",
        views.asset_furniture_fixture_complete_move,
        name="asset_furniture_fixture_complete_move",
    ),
    path(
        "furniture-fixtures/<int:pk>/retire/",
        views.asset_furniture_fixture_retire,
        name="asset_furniture_fixture_retire",
    ),
]
