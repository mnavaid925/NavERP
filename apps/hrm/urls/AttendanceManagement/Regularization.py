"""HRM 3.9 Attendance Management — Regularization URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Attendance Regularization (3.9)
    path("regularizations/", views.attendanceregularization_list, name="attendanceregularization_list"),
    path("regularizations/add/", views.attendanceregularization_create, name="attendanceregularization_create"),
    path("regularizations/<int:pk>/", views.attendanceregularization_detail, name="attendanceregularization_detail"),
    path("regularizations/<int:pk>/edit/", views.attendanceregularization_edit, name="attendanceregularization_edit"),
    path("regularizations/<int:pk>/delete/", views.attendanceregularization_delete, name="attendanceregularization_delete"),
    path("regularizations/<int:pk>/submit/", views.attendanceregularization_submit, name="attendanceregularization_submit"),
    path("regularizations/<int:pk>/approve/", views.attendanceregularization_approve, name="attendanceregularization_approve"),
    path("regularizations/<int:pk>/reject/", views.attendanceregularization_reject, name="attendanceregularization_reject"),
    path("regularizations/<int:pk>/cancel/", views.attendanceregularization_cancel, name="attendanceregularization_cancel"),
]
