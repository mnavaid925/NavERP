from django.urls import path

from apps.assets.views.MobileAssetManagement import AssetScanLogs as views

urlpatterns = [
    path("mobile/scans/", views.asset_scan_log_list, name="asset_scan_log_list"),
    path("mobile/scans/create/", views.asset_scan_log_create, name="asset_scan_log_create"),
    path("mobile/scans/<int:pk>/", views.asset_scan_log_detail, name="asset_scan_log_detail"),
    path("mobile/scans/<int:pk>/edit/", views.asset_scan_log_edit, name="asset_scan_log_edit"),
    path("mobile/scans/<int:pk>/delete/", views.asset_scan_log_delete, name="asset_scan_log_delete"),
]
