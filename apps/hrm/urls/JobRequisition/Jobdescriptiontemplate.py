"""HRM 3.5 Job Requisition — Jobdescriptiontemplate URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Job Description Templates (3.5) — CRUD
    path("job-templates/", views.jobdescriptiontemplate_list, name="jobdescriptiontemplate_list"),
    path("job-templates/add/", views.jobdescriptiontemplate_create, name="jobdescriptiontemplate_create"),
    path("job-templates/<int:pk>/", views.jobdescriptiontemplate_detail, name="jobdescriptiontemplate_detail"),
    path("job-templates/<int:pk>/edit/", views.jobdescriptiontemplate_edit, name="jobdescriptiontemplate_edit"),
    path("job-templates/<int:pk>/delete/", views.jobdescriptiontemplate_delete, name="jobdescriptiontemplate_delete"),
]
