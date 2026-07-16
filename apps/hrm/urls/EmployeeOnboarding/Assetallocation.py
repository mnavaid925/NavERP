"""HRM 3.3 Employee Onboarding — Assetallocation URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Asset Allocations (3.3) — CRUD + issue/return
    path("assets/", views.assetallocation_list, name="assetallocation_list"),
    path("assets/add/", views.assetallocation_create, name="assetallocation_create"),
    path("assets/<int:pk>/", views.assetallocation_detail, name="assetallocation_detail"),
    path("assets/<int:pk>/edit/", views.assetallocation_edit, name="assetallocation_edit"),
    path("assets/<int:pk>/delete/", views.assetallocation_delete, name="assetallocation_delete"),
    path("assets/<int:pk>/issue/", views.assetallocation_issue, name="assetallocation_issue"),
    path("assets/<int:pk>/return/", views.assetallocation_return, name="assetallocation_return"),
]
