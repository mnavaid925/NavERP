"""Accounting 2.7 Inventory & Cost Management — CostAllocations URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    # 2.7 Cost allocation
    path("cost-allocations/", views.cost_allocation_list, name="cost_allocation_list"),
    path("cost-allocations/add/", views.cost_allocation_create, name="cost_allocation_create"),
    path("cost-allocations/<int:pk>/", views.cost_allocation_detail, name="cost_allocation_detail"),
    path("cost-allocations/<int:pk>/edit/", views.cost_allocation_edit, name="cost_allocation_edit"),
    path("cost-allocations/<int:pk>/delete/", views.cost_allocation_delete, name="cost_allocation_delete"),
    path("cost-allocations/<int:pk>/post/", views.cost_allocation_post, name="cost_allocation_post"),
]
