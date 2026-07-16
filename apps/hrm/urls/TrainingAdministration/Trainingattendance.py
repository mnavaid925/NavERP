"""HRM 3.24 Training Administration — Trainingattendance URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Attendance
    path("training-attendance/", views.trainingattendance_list, name="trainingattendance_list"),
    path("training-attendance/add/", views.trainingattendance_create, name="trainingattendance_create"),
    path("training-attendance/<int:pk>/", views.trainingattendance_detail, name="trainingattendance_detail"),
    path("training-attendance/<int:pk>/edit/", views.trainingattendance_edit, name="trainingattendance_edit"),
    path("training-attendance/<int:pk>/delete/", views.trainingattendance_delete, name="trainingattendance_delete"),
]
