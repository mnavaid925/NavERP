"""HRM 3.40 Workforce Planning — Workforceplan URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("workforce/plans/", views.workforceplan_list, name="workforceplan_list"),
    path("workforce/plans/add/", views.workforceplan_create, name="workforceplan_create"),
    path("workforce/plans/<int:pk>/", views.workforceplan_detail, name="workforceplan_detail"),
    path("workforce/plans/<int:pk>/edit/", views.workforceplan_edit, name="workforceplan_edit"),
    path("workforce/plans/<int:pk>/delete/", views.workforceplan_delete, name="workforceplan_delete"),
]
