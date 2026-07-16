"""HRM 3.12 Holiday Management — Holidaypolicy URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Holiday Policies (3.12)
    path("holiday-policies/", views.holidaypolicy_list, name="holidaypolicy_list"),
    path("holiday-policies/add/", views.holidaypolicy_create, name="holidaypolicy_create"),
    path("holiday-policies/<int:pk>/", views.holidaypolicy_detail, name="holidaypolicy_detail"),
    path("holiday-policies/<int:pk>/edit/", views.holidaypolicy_edit, name="holidaypolicy_edit"),
    path("holiday-policies/<int:pk>/delete/", views.holidaypolicy_delete, name="holidaypolicy_delete"),
]
