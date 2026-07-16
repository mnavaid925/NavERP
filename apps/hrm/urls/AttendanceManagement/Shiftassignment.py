"""HRM 3.9 Attendance Management — Shiftassignment URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Shift Assignments (3.9)
    path("shift-assignments/", views.shiftassignment_list, name="shiftassignment_list"),
    path("shift-assignments/add/", views.shiftassignment_create, name="shiftassignment_create"),
    path("shift-assignments/<int:pk>/", views.shiftassignment_detail, name="shiftassignment_detail"),
    path("shift-assignments/<int:pk>/edit/", views.shiftassignment_edit, name="shiftassignment_edit"),
    path("shift-assignments/<int:pk>/delete/", views.shiftassignment_delete, name="shiftassignment_delete"),
]
