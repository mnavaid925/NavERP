"""URL patterns for IT Hardware Assets (11.18)."""

from django.urls import path

from apps.assets.views.ItAssetManagement import ItHardwareAssets as views

urlpatterns = [
    path("it-hardware/", views.it_hardware_asset_list, name="it_hardware_asset_list"),
    path("it-hardware/create/", views.it_hardware_asset_create, name="it_hardware_asset_create"),
    path("it-hardware/export-csv/", views.it_hardware_asset_export_csv, name="it_hardware_asset_export_csv"),
    path("it-hardware/<int:pk>/", views.it_hardware_asset_detail, name="it_hardware_asset_detail"),
    path("it-hardware/<int:pk>/edit/", views.it_hardware_asset_edit, name="it_hardware_asset_edit"),
    path("it-hardware/<int:pk>/delete/", views.it_hardware_asset_delete, name="it_hardware_asset_delete"),
    path("it-hardware/<int:pk>/deploy/", views.it_hardware_asset_deploy, name="it_hardware_asset_deploy"),
    path("it-hardware/<int:pk>/stock/", views.it_hardware_asset_move_to_stock, name="it_hardware_asset_move_to_stock"),
    path("it-hardware/<int:pk>/repair/", views.it_hardware_asset_send_to_repair, name="it_hardware_asset_send_to_repair"),
    path("it-hardware/<int:pk>/loaner/", views.it_hardware_asset_move_to_loaner, name="it_hardware_asset_move_to_loaner"),
    path("it-hardware/<int:pk>/flag-refresh/", views.it_hardware_asset_flag_for_refresh, name="it_hardware_asset_flag_for_refresh"),
    path("it-hardware/<int:pk>/sanitize/", views.it_hardware_asset_mark_sanitized, name="it_hardware_asset_mark_sanitized"),
    path("it-hardware/<int:pk>/retire/", views.it_hardware_asset_retire, name="it_hardware_asset_retire"),
]
