from django.urls import path

from apps.assets.views.MobileAssetManagement import AssetGeofenceEvents as views

urlpatterns = [
    path("mobile/geofence/", views.asset_geofence_event_list, name="asset_geofence_event_list"),
    path("mobile/geofence/create/", views.asset_geofence_event_create, name="asset_geofence_event_create"),
    path("mobile/geofence/<int:pk>/", views.asset_geofence_event_detail, name="asset_geofence_event_detail"),
    path("mobile/geofence/<int:pk>/edit/", views.asset_geofence_event_edit, name="asset_geofence_event_edit"),
    path("mobile/geofence/<int:pk>/delete/", views.asset_geofence_event_delete, name="asset_geofence_event_delete"),
]
