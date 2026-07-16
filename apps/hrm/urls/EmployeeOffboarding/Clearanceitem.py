"""HRM 3.4 Employee Offboarding — Clearanceitem URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # Clearance Items (3.4) — CRUD + workflow
    path("clearance/", views.clearanceitem_list, name="clearanceitem_list"),
    path("clearance/add/", views.clearanceitem_create, name="clearanceitem_create"),
    path("clearance/<int:pk>/", views.clearanceitem_detail, name="clearanceitem_detail"),
    path("clearance/<int:pk>/edit/", views.clearanceitem_edit, name="clearanceitem_edit"),
    path("clearance/<int:pk>/delete/", views.clearanceitem_delete, name="clearanceitem_delete"),
    path("clearance/<int:pk>/mark-cleared/", views.clearanceitem_mark_cleared, name="clearanceitem_mark_cleared"),
    path("clearance/<int:pk>/mark-na/", views.clearanceitem_mark_na, name="clearanceitem_mark_na"),
    path("clearance/<int:pk>/reject/", views.clearanceitem_reject, name="clearanceitem_reject"),
]
