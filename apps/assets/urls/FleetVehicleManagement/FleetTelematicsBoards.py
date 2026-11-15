"""URL patterns for Fleet Telematics Board (11.19)."""

from django.urls import path

from apps.assets.views.FleetVehicleManagement import FleetTelematicsBoards as views

urlpatterns = [
    path("fleet-telematics/board/", views.fleet_telematics_board, name="fleet_telematics_board"),
]
