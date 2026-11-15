"""URL patterns for Fleet Vehicle management (11.19)."""

from django.urls import path

from apps.assets.views.FleetVehicleManagement import FleetVehicles as views

urlpatterns = [
    path("fleet-vehicles/", views.fleet_vehicle_list, name="fleet_vehicle_list"),
    path("fleet-vehicles/export/", views.fleet_vehicle_export, name="fleet_vehicle_export"),
    path("fleet-vehicles/create/", views.fleet_vehicle_create, name="fleet_vehicle_create"),
    path("fleet-vehicles/<int:pk>/", views.fleet_vehicle_detail, name="fleet_vehicle_detail"),
    path("fleet-vehicles/<int:pk>/edit/", views.fleet_vehicle_edit, name="fleet_vehicle_edit"),
    path("fleet-vehicles/<int:pk>/delete/", views.fleet_vehicle_delete, name="fleet_vehicle_delete"),
    path("fleet-vehicles/<int:pk>/activate/", views.fleet_vehicle_activate, name="fleet_vehicle_activate"),
    path("fleet-vehicles/<int:pk>/in-shop/", views.fleet_vehicle_mark_in_shop, name="fleet_vehicle_mark_in_shop"),
    path("fleet-vehicles/<int:pk>/loaner/", views.fleet_vehicle_mark_loaner, name="fleet_vehicle_mark_loaner"),
    path("fleet-vehicles/<int:pk>/out-of-service/", views.fleet_vehicle_mark_out_of_service, name="fleet_vehicle_mark_out_of_service"),
    path("fleet-vehicles/<int:pk>/decommission/", views.fleet_vehicle_decommission, name="fleet_vehicle_decommission"),
    path("fleet-vehicles/<int:pk>/ping-telemetry/", views.fleet_vehicle_ping_telemetry, name="fleet_vehicle_ping_telemetry"),
]
