"""HRM 3.37 Compensation & Benefits — Employeebenefitenrollment URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("compensation/enrollments/", views.employeebenefitenrollment_list, name="employeebenefitenrollment_list"),
    path("compensation/enrollments/add/", views.employeebenefitenrollment_create, name="employeebenefitenrollment_create"),
    path("compensation/enrollments/<int:pk>/", views.employeebenefitenrollment_detail, name="employeebenefitenrollment_detail"),
    path("compensation/enrollments/<int:pk>/edit/", views.employeebenefitenrollment_edit, name="employeebenefitenrollment_edit"),
    path("compensation/enrollments/<int:pk>/delete/", views.employeebenefitenrollment_delete, name="employeebenefitenrollment_delete"),
    path("compensation/enrollments/<int:pk>/enroll/", views.employeebenefitenrollment_enroll, name="employeebenefitenrollment_enroll"),
    path("compensation/enrollments/<int:pk>/waive/", views.employeebenefitenrollment_waive, name="employeebenefitenrollment_waive"),
    path("compensation/enrollments/<int:pk>/terminate/", views.employeebenefitenrollment_terminate, name="employeebenefitenrollment_terminate"),
]
