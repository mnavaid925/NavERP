"""HRM 3.2 Organizational Structure — Jobgrade URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Job Grades (3.2)
    path("job-grades/", views.jobgrade_list, name="jobgrade_list"),
    path("job-grades/add/", views.jobgrade_create, name="jobgrade_create"),
    path("job-grades/<int:pk>/", views.jobgrade_detail, name="jobgrade_detail"),
    path("job-grades/<int:pk>/edit/", views.jobgrade_edit, name="jobgrade_edit"),
    path("job-grades/<int:pk>/delete/", views.jobgrade_delete, name="jobgrade_delete"),
]
