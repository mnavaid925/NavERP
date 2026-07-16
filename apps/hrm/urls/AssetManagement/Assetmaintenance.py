"""HRM 3.33 Asset Management — Assetmaintenance URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    path("asset-maintenance/", views.assetmaintenance_list, name="assetmaintenance_list"),
    path("asset-maintenance/add/", views.assetmaintenance_create, name="assetmaintenance_create"),
    path("asset-maintenance/<int:pk>/", views.assetmaintenance_detail, name="assetmaintenance_detail"),
    path("asset-maintenance/<int:pk>/edit/", views.assetmaintenance_edit, name="assetmaintenance_edit"),
    path("asset-maintenance/<int:pk>/delete/", views.assetmaintenance_delete, name="assetmaintenance_delete"),
    path("asset-maintenance/<int:pk>/complete/", views.assetmaintenance_complete, name="assetmaintenance_complete"),
]
