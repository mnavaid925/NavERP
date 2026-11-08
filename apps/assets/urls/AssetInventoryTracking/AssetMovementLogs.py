from django.urls import path

from apps.assets.views.AssetInventoryTracking.AssetMovementLogs import (
    asset_movement_log_cancel,
    asset_movement_log_create,
    asset_movement_log_delete,
    asset_movement_log_detail,
    asset_movement_log_dispatch,
    asset_movement_log_edit,
    asset_movement_log_list,
    asset_movement_log_receive,
)

urlpatterns = [
    path("inventory-tracking/movements/", asset_movement_log_list, name="asset_movement_log_list"),
    path("inventory-tracking/movements/create/", asset_movement_log_create, name="asset_movement_log_create"),
    path("inventory-tracking/movements/<int:pk>/", asset_movement_log_detail, name="asset_movement_log_detail"),
    path("inventory-tracking/movements/<int:pk>/edit/", asset_movement_log_edit, name="asset_movement_log_edit"),
    path("inventory-tracking/movements/<int:pk>/delete/", asset_movement_log_delete, name="asset_movement_log_delete"),
    path("inventory-tracking/movements/<int:pk>/dispatch/", asset_movement_log_dispatch, name="asset_movement_log_dispatch"),
    path("inventory-tracking/movements/<int:pk>/receive/", asset_movement_log_receive, name="asset_movement_log_receive"),
    path("inventory-tracking/movements/<int:pk>/cancel/", asset_movement_log_cancel, name="asset_movement_log_cancel"),
]
