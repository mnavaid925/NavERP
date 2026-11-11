from apps.assets.views.MobileAssetManagement.AssetGeofenceEvents import (
    asset_geofence_event_create,
    asset_geofence_event_delete,
    asset_geofence_event_detail,
    asset_geofence_event_edit,
    asset_geofence_event_list,
)
from apps.assets.views.MobileAssetManagement.AssetScanLogs import (
    asset_scan_log_create,
    asset_scan_log_delete,
    asset_scan_log_detail,
    asset_scan_log_edit,
    asset_scan_log_list,
)
from apps.assets.views.MobileAssetManagement.FieldWorkOrders import (
    field_work_order_create,
    field_work_order_delete,
    field_work_order_detail,
    field_work_order_edit,
    field_work_order_list,
)
from apps.assets.views.MobileAssetManagement.MobileAssetInspections import (
    mobile_asset_inspection_create,
    mobile_asset_inspection_delete,
    mobile_asset_inspection_detail,
    mobile_asset_inspection_edit,
    mobile_asset_inspection_list,
)

__all__ = [
    "mobile_asset_inspection_list",
    "mobile_asset_inspection_create",
    "mobile_asset_inspection_detail",
    "mobile_asset_inspection_edit",
    "mobile_asset_inspection_delete",
    "field_work_order_list",
    "field_work_order_create",
    "field_work_order_detail",
    "field_work_order_edit",
    "field_work_order_delete",
    "asset_scan_log_list",
    "asset_scan_log_create",
    "asset_scan_log_detail",
    "asset_scan_log_edit",
    "asset_scan_log_delete",
    "asset_geofence_event_list",
    "asset_geofence_event_create",
    "asset_geofence_event_detail",
    "asset_geofence_event_edit",
    "asset_geofence_event_delete",
]

