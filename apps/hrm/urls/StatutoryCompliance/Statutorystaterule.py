"""HRM 3.15 Statutory Compliance — Statutorystaterule URL patterns (split from apps/hrm/urls.py)."""
from django.urls import path

from apps.hrm import views


urlpatterns = [
    # State-wise PT + LWF slab/rate rules — CRUD
    path("statutory-state-rules/", views.statutorystaterule_list, name="statutorystaterule_list"),
    path("statutory-state-rules/add/", views.statutorystaterule_create, name="statutorystaterule_create"),
    path("statutory-state-rules/<int:pk>/", views.statutorystaterule_detail, name="statutorystaterule_detail"),
    path("statutory-state-rules/<int:pk>/edit/", views.statutorystaterule_edit, name="statutorystaterule_edit"),
    path("statutory-state-rules/<int:pk>/delete/", views.statutorystaterule_delete, name="statutorystaterule_delete"),
]
