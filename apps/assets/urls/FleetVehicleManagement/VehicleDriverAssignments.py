"""URL patterns for Vehicle Driver Assignments (11.19)."""

from django.urls import path

from apps.assets.views.FleetVehicleManagement import VehicleDriverAssignments as views

urlpatterns = [
    path("vehicle-driver-assignments/", views.vehicle_driver_assignment_list, name="vehicle_driver_assignment_list"),
    path("vehicle-driver-assignments/export/", views.vehicle_driver_assignment_export, name="vehicle_driver_assignment_export"),
    path("vehicle-driver-assignments/create/", views.vehicle_driver_assignment_create, name="vehicle_driver_assignment_create"),
    path("vehicle-driver-assignments/<int:pk>/", views.vehicle_driver_assignment_detail, name="vehicle_driver_assignment_detail"),
    path("vehicle-driver-assignments/<int:pk>/edit/", views.vehicle_driver_assignment_edit, name="vehicle_driver_assignment_edit"),
    path("vehicle-driver-assignments/<int:pk>/delete/", views.vehicle_driver_assignment_delete, name="vehicle_driver_assignment_delete"),
    path("vehicle-driver-assignments/<int:pk>/complete/", views.vehicle_driver_assignment_complete, name="vehicle_driver_assignment_complete"),
    path("vehicle-driver-assignments/<int:pk>/revoke/", views.vehicle_driver_assignment_revoke, name="vehicle_driver_assignment_revoke"),
    path("vehicle-driver-assignments/<int:pk>/incident/", views.vehicle_driver_assignment_record_incident, name="vehicle_driver_assignment_record_incident"),
]
