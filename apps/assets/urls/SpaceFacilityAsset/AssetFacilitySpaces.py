"""URL patterns for Facility Spaces & Floor Plan Mapping (11.17)."""

from django.urls import path

from apps.assets.views.SpaceFacilityAsset import AssetFacilitySpaces as views

urlpatterns = [
    path("spaces/", views.asset_facility_space_list, name="asset_facility_space_list"),
    path("spaces/create/", views.asset_facility_space_create, name="asset_facility_space_create"),
    path(
        "spaces/export-csv/",
        views.asset_facility_space_export_csv,
        name="asset_facility_space_export_csv",
    ),
    path(
        "spaces/<int:pk>/",
        views.asset_facility_space_detail,
        name="asset_facility_space_detail",
    ),
    path(
        "spaces/<int:pk>/edit/",
        views.asset_facility_space_edit,
        name="asset_facility_space_edit",
    ),
    path(
        "spaces/<int:pk>/delete/",
        views.asset_facility_space_delete,
        name="asset_facility_space_delete",
    ),
    path(
        "spaces/<int:pk>/floor-plan/",
        views.asset_facility_space_floor_plan_download,
        name="asset_facility_space_floor_plan_download",
    ),
    path(
        "spaces/<int:pk>/recalculate-utilization/",
        views.asset_facility_space_recalculate_utilization,
        name="asset_facility_space_recalculate_utilization",
    ),
    path(
        "spaces/<int:pk>/mark-renovation/",
        views.asset_facility_space_mark_under_renovation,
        name="asset_facility_space_mark_under_renovation",
    ),
    path(
        "spaces/<int:pk>/activate/",
        views.asset_facility_space_activate,
        name="asset_facility_space_activate",
    ),
    path(
        "spaces/<int:pk>/decommission/",
        views.asset_facility_space_decommission,
        name="asset_facility_space_decommission",
    ),
]
