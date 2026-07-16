"""HRM 3.19 Performance Review — CalibrationBoard URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Calibration board (report view — ?cycle=<id>)
    path("calibration/", views.calibration_board, name="calibration_board"),
]
