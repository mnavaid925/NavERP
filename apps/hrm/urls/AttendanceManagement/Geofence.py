"""HRM 3.9 Attendance Management — Geofence URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Geofences (3.9)
    path("geofences/", views.geofence_list, name="geofence_list"),
    path("geofences/add/", views.geofence_create, name="geofence_create"),
    path("geofences/<int:pk>/", views.geofence_detail, name="geofence_detail"),
    path("geofences/<int:pk>/edit/", views.geofence_edit, name="geofence_edit"),
    path("geofences/<int:pk>/delete/", views.geofence_delete, name="geofence_delete"),
]
