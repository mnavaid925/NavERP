"""URL patterns for Vehicle Service Schedules (11.19)."""

from django.urls import path

from apps.assets.views.FleetVehicleManagement import VehicleServiceSchedules as views

urlpatterns = [
    path("vehicle-service-schedules/", views.vehicle_service_schedule_list, name="vehicle_service_schedule_list"),
    path("vehicle-service-schedules/export/", views.vehicle_service_schedule_export, name="vehicle_service_schedule_export"),
    path("vehicle-service-schedules/create/", views.vehicle_service_schedule_create, name="vehicle_service_schedule_create"),
    path("vehicle-service-schedules/<int:pk>/", views.vehicle_service_schedule_detail, name="vehicle_service_schedule_detail"),
    path("vehicle-service-schedules/<int:pk>/edit/", views.vehicle_service_schedule_edit, name="vehicle_service_schedule_edit"),
    path("vehicle-service-schedules/<int:pk>/delete/", views.vehicle_service_schedule_delete, name="vehicle_service_schedule_delete"),
    path("vehicle-service-schedules/<int:pk>/complete/", views.vehicle_service_schedule_complete, name="vehicle_service_schedule_complete"),
    path("vehicle-service-schedules/<int:pk>/in-service/", views.vehicle_service_schedule_mark_in_service, name="vehicle_service_schedule_mark_in_service"),
    path("vehicle-service-schedules/<int:pk>/pause/", views.vehicle_service_schedule_pause, name="vehicle_service_schedule_pause"),
]
