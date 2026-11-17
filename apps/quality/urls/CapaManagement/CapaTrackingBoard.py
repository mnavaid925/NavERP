from django.urls import path

from apps.quality.views.CapaManagement import CapaTrackingBoard as views

urlpatterns = [
    path("capa/tracking-board/", views.capa_tracking_board, name="capa_tracking_board"),
    path("capa/tracking-board/export/", views.capa_tracking_board_export, name="capa_tracking_board_export"),
]
