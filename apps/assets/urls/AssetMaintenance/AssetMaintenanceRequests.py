from django.urls import path

from apps.assets.views.AssetMaintenance import AssetMaintenanceRequests as views

urlpatterns = [
    path("requests/", views.asset_maintenance_request_list, name="asset_maintenance_request_list"),
    path("requests/create/", views.asset_maintenance_request_create, name="asset_maintenance_request_create"),
    path("requests/<int:pk>/", views.asset_maintenance_request_detail, name="asset_maintenance_request_detail"),
    path("requests/<int:pk>/edit/", views.asset_maintenance_request_edit, name="asset_maintenance_request_edit"),
    path("requests/<int:pk>/delete/", views.asset_maintenance_request_delete, name="asset_maintenance_request_delete"),
    path("requests/<int:pk>/triage/", views.asset_maintenance_request_triage, name="asset_maintenance_request_triage"),
    path("requests/<int:pk>/dispatch/", views.asset_maintenance_request_dispatch, name="asset_maintenance_request_dispatch"),
    path("requests/<int:pk>/start/", views.asset_maintenance_request_start, name="asset_maintenance_request_start"),
    path("requests/<int:pk>/resolve/", views.asset_maintenance_request_resolve, name="asset_maintenance_request_resolve"),
    path("requests/<int:pk>/close/", views.asset_maintenance_request_close, name="asset_maintenance_request_close"),
    path("requests/<int:pk>/reject/", views.asset_maintenance_request_reject, name="asset_maintenance_request_reject"),
]
