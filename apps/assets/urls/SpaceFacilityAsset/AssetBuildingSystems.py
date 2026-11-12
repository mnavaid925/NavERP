"""URL patterns for HVAC & Building Systems (11.17)."""

from django.urls import path

from apps.assets.views.SpaceFacilityAsset import AssetBuildingSystems as views

urlpatterns = [
    path(
        "building-systems/",
        views.asset_building_system_list,
        name="asset_building_system_list",
    ),
    path(
        "building-systems/create/",
        views.asset_building_system_create,
        name="asset_building_system_create",
    ),
    path(
        "building-systems/export-csv/",
        views.asset_building_system_export_csv,
        name="asset_building_system_export_csv",
    ),
    path(
        "building-systems/<int:pk>/",
        views.asset_building_system_detail,
        name="asset_building_system_detail",
    ),
    path(
        "building-systems/<int:pk>/edit/",
        views.asset_building_system_edit,
        name="asset_building_system_edit",
    ),
    path(
        "building-systems/<int:pk>/delete/",
        views.asset_building_system_delete,
        name="asset_building_system_delete",
    ),
    path(
        "building-systems/<int:pk>/evaluate-comfort/",
        views.asset_building_system_evaluate_comfort,
        name="asset_building_system_evaluate_comfort",
    ),
    path(
        "building-systems/<int:pk>/record-inspection/",
        views.asset_building_system_record_inspection,
        name="asset_building_system_record_inspection",
    ),
    path(
        "building-systems/<int:pk>/flag-maintenance/",
        views.asset_building_system_flag_maintenance,
        name="asset_building_system_flag_maintenance",
    ),
    path(
        "building-systems/<int:pk>/restore-operational/",
        views.asset_building_system_restore_operational,
        name="asset_building_system_restore_operational",
    ),
    path(
        "building-systems/<int:pk>/decommission/",
        views.asset_building_system_decommission,
        name="asset_building_system_decommission",
    ),
]
