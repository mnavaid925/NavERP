"""HRM 3.10 Leave Management — Allocation URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Leave Allocations (3.10)
    path("leave-allocations/", views.leaveallocation_list, name="leaveallocation_list"),
    path("leave-allocations/add/", views.leaveallocation_create, name="leaveallocation_create"),
    path("leave-allocations/<int:pk>/", views.leaveallocation_detail, name="leaveallocation_detail"),
    path("leave-allocations/<int:pk>/edit/", views.leaveallocation_edit, name="leaveallocation_edit"),
    path("leave-allocations/<int:pk>/delete/", views.leaveallocation_delete, name="leaveallocation_delete"),
]
