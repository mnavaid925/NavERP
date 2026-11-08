from django.urls import path

from apps.assets.views.AssetInventoryTracking.AssetCustodyLogs import (
    asset_custody_log_checkin,
    asset_custody_log_create,
    asset_custody_log_delete,
    asset_custody_log_detail,
    asset_custody_log_edit,
    asset_custody_log_extend,
    asset_custody_log_list,
    asset_custody_log_mark_lost,
)

urlpatterns = [
    path("inventory-tracking/custody/", asset_custody_log_list, name="asset_custody_log_list"),
    path("inventory-tracking/custody/create/", asset_custody_log_create, name="asset_custody_log_create"),
    path("inventory-tracking/custody/<int:pk>/", asset_custody_log_detail, name="asset_custody_log_detail"),
    path("inventory-tracking/custody/<int:pk>/edit/", asset_custody_log_edit, name="asset_custody_log_edit"),
    path("inventory-tracking/custody/<int:pk>/delete/", asset_custody_log_delete, name="asset_custody_log_delete"),
    path("inventory-tracking/custody/<int:pk>/checkin/", asset_custody_log_checkin, name="asset_custody_log_checkin"),
    path("inventory-tracking/custody/<int:pk>/extend/", asset_custody_log_extend, name="asset_custody_log_extend"),
    path("inventory-tracking/custody/<int:pk>/mark-lost/", asset_custody_log_mark_lost, name="asset_custody_log_mark_lost"),
]
