"""CRM 1.8 Project & Delivery Management — ResourceAllocation URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    # Resource Allocation (1.8) — capacity bookings + workload board + Kanban
    path("resource-allocations/", views.resourceallocation_list, name="resourceallocation_list"),
    path("resource-allocations/add/", views.resourceallocation_create, name="resourceallocation_create"),
    path("resource-allocations/<int:pk>/", views.resourceallocation_detail, name="resourceallocation_detail"),
    path("resource-allocations/<int:pk>/edit/", views.resourceallocation_edit, name="resourceallocation_edit"),
    path("resource-allocations/<int:pk>/delete/", views.resourceallocation_delete, name="resourceallocation_delete"),
    path("workload/", views.resource_workload, name="resource_workload"),
]
