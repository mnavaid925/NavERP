"""Inventory 5.11 Stocktaking & Cycle Counting — PhysicalInventory routes (prefix ``physical-inventory``).

Lifecycle verbs are literal segments before the ``<int:pk>`` routes and each ends in
its own token, so none can shadow detail/edit/delete.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("physical-inventory/", views.physicalinventory_list, name="physicalinventory_list"),
    path("physical-inventory/add/", views.physicalinventory_create, name="physicalinventory_create"),
    path("physical-inventory/<int:pk>/start/", views.physicalinventory_start, name="physicalinventory_start"),
    path("physical-inventory/<int:pk>/reconcile/", views.physicalinventory_reconcile, name="physicalinventory_reconcile"),
    path("physical-inventory/<int:pk>/cancel/", views.physicalinventory_cancel, name="physicalinventory_cancel"),
    path("physical-inventory/<int:pk>/", views.physicalinventory_detail, name="physicalinventory_detail"),
    path("physical-inventory/<int:pk>/edit/", views.physicalinventory_edit, name="physicalinventory_edit"),
    path("physical-inventory/<int:pk>/delete/", views.physicalinventory_delete, name="physicalinventory_delete"),
]
