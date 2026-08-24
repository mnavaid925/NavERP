"""Inventory 5.17 — InventoryReportSnapshot [IRS-] routes.

The literal ``generate`` route precedes ``<int:pk>`` so it can never be eaten by
the detail converter. No edit route exists: a snapshot is immutable evidence.
Delete is POST-only and admin-gated at the view.
"""
from django.urls import path

from apps.inventory import views

urlpatterns = [
    path("snapshots/", views.snapshot_list, name="snapshot_list"),
    path("snapshots/generate/", views.snapshot_generate, name="snapshot_generate"),
    path("snapshots/<int:pk>/", views.snapshot_detail, name="snapshot_detail"),
    path("snapshots/<int:pk>/delete/", views.snapshot_delete, name="snapshot_delete"),
]
