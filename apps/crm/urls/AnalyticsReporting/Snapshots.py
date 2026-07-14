"""CRM 1.6 Analytics & Reporting — Snapshots URL patterns (split from apps/crm/urls.py)."""
from django.urls import path

from apps.crm import views


urlpatterns = [
    path("snapshots/<int:pk>/", views.snapshot_detail, name="snapshot_detail"),
    path("snapshots/<int:pk>/delete/", views.snapshot_delete, name="snapshot_delete"),
]
