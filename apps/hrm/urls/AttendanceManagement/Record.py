"""HRM 3.9 Attendance Management — Record URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Attendance (3.9)
    path("attendance/", views.attendancerecord_list, name="attendancerecord_list"),
    path("attendance/add/", views.attendancerecord_create, name="attendancerecord_create"),
    path("attendance/<int:pk>/", views.attendancerecord_detail, name="attendancerecord_detail"),
    path("attendance/<int:pk>/edit/", views.attendancerecord_edit, name="attendancerecord_edit"),
    path("attendance/<int:pk>/delete/", views.attendancerecord_delete, name="attendancerecord_delete"),
]
