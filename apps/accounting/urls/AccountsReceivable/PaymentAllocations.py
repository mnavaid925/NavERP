"""Accounting 2.4 Accounts Receivable — PaymentAllocations URL patterns (split from apps/accounting/urls.py)."""
from django.urls import path

from apps.accounting import views


urlpatterns = [
    path("allocations/", views.allocation_list, name="allocation_list"),
    path("allocations/add/", views.allocation_create, name="allocation_create"),
    path("allocations/<int:pk>/", views.allocation_detail, name="allocation_detail"),
    path("allocations/<int:pk>/edit/", views.allocation_edit, name="allocation_edit"),
    path("allocations/<int:pk>/delete/", views.allocation_delete, name="allocation_delete"),
]
