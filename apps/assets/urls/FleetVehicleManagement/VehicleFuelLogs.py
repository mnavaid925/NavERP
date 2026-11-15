"""URL patterns for Vehicle Fuel Logs (11.19)."""

from django.urls import path

from apps.assets.views.FleetVehicleManagement import VehicleFuelLogs as views

urlpatterns = [
    path("vehicle-fuel-logs/", views.vehicle_fuel_log_list, name="vehicle_fuel_log_list"),
    path("vehicle-fuel-logs/export/", views.vehicle_fuel_log_export, name="vehicle_fuel_log_export"),
    path("vehicle-fuel-logs/create/", views.vehicle_fuel_log_create, name="vehicle_fuel_log_create"),
    path("vehicle-fuel-logs/<int:pk>/", views.vehicle_fuel_log_detail, name="vehicle_fuel_log_detail"),
    path("vehicle-fuel-logs/<int:pk>/edit/", views.vehicle_fuel_log_edit, name="vehicle_fuel_log_edit"),
    path("vehicle-fuel-logs/<int:pk>/delete/", views.vehicle_fuel_log_delete, name="vehicle_fuel_log_delete"),
]
